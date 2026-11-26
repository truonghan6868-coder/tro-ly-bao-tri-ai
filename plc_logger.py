import os
import sqlite3
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import snap7
from snap7.util import get_real


# 1. Nạp cấu hình từ file .env
load_dotenv()
PLC_IP = os.getenv("PLC_IP", "192.168.0.1")
PLC_RACK = int(os.getenv("PLC_RACK", 0))
PLC_SLOT = int(os.getenv("PLC_SLOT", 1))
DB_NUMBER = int(os.getenv("PLC_DB_NUMBER", 3))
DB_FILE = "bao_tri_ai.db"

# Timeout & chính sách thử lại khi kết nối PLC
PLC_TIMEOUT_MS = int(os.getenv("PLC_TIMEOUT_MS", 3000))       # timeout ping/send/recv (ms)
PLC_RETRY_SO_LAN = int(os.getenv("PLC_RETRY_SO_LAN", 3))      # số lần thử nhanh khi khởi động
PLC_RETRY_CHO_DAU = int(os.getenv("PLC_RETRY_CHO_DAU", 2))    # backoff khởi điểm (giây)
PLC_RETRY_CHO_TOI_DA = int(os.getenv("PLC_RETRY_CHO_TOI_DA", 60))  # backoff tối đa (giây)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Ngưỡng cảnh báo mặc định & Vị trí máy của trạm
NGUONG_TEMP1 = float(os.getenv("NGUONG_TEMP1", 80.0))
NGUONG_TEMP2 = float(os.getenv("NGUONG_TEMP2", 80.0))
NGUONG_CURRENT = float(os.getenv("NGUONG_CURRENT", 65.0))
VI_TRI_MAY_TRAM = os.getenv("VI_TRI_MAY_TRAM", "Cụm Lô ép (Press Roll - 75kW)")

# Biến theo dõi trạng thái lỗi 2 chiều & chống spam
dang_bi_loi = False
thoi_diem_bat_dau_loi = None
thoi_diem_canh_bao_cuoi = 0
THOI_GIAN_NGHI_CANH_BAO = 300  # Nhắc lại sau mỗi 5 phút nếu lỗi chưa khắc phục
ngay_da_nhac_pm = ""

# Trạng thái kết nối PLC (dùng cho cảnh báo mất kết nối / phục hồi)
dang_mat_ket_noi = False
thoi_diem_mat_ket_noi = None


# 2. Khởi tạo bảng lưu dự phòng cục bộ trong SQLite
def khoi_tao_bang_plc():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS du_lieu_plc_db3 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thoi_gian TEXT,
            temp1 REAL,
            temp2 REAL,
            speed REAL,
            pressure REAL,
            motor_current REAL
        )
    """)
    conn.commit()
    conn.close()


def dong_bo_nguong_tu_cloud():
    """Tải ngưỡng cảnh báo mới nhất từ bảng cau_hinh_nguong trên Supabase."""
    global NGUONG_TEMP1, NGUONG_TEMP2, NGUONG_CURRENT
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        endpoint = f"{SUPABASE_URL}/rest/v1/cau_hinh_nguong"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Cache-Control": "no-cache"
        }
        params = {
            "vi_tri_may": f"eq.{VI_TRI_MAY_TRAM}",
            "select": "nguong_temp1,nguong_temp2,nguong_current"
        }
        res = requests.get(endpoint, headers=headers, params=params, timeout=8)
        res.raise_for_status()
        du_lieu = res.json()
        if du_lieu:
            ban_ghi = du_lieu.pop(0)
            NGUONG_TEMP1 = float(ban_ghi.get("nguong_temp1", NGUONG_TEMP1))
            NGUONG_TEMP2 = float(ban_ghi.get("nguong_temp2", NGUONG_TEMP2))
            NGUONG_CURRENT = float(ban_ghi.get("nguong_current", NGUONG_CURRENT))
    except Exception:
        pass


def gui_tin_nhan_telegram(noi_dung_tin_nhan, loai_thong_bao="Cảnh báo"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url_tg = "https://" + "api.telegram.org/bot" + f"{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": noi_dung_tin_nhan,
            "parse_mode": "HTML"
        }
        res = requests.post(url_tg, json=payload, timeout=10)
        res.raise_for_status()
        print(f"📲 Đã gửi tin nhắn Telegram ({loai_thong_bao}) thành công!")
    except Exception as e_tg:
        print(f"⚠️ Lỗi gửi Telegram: {e_tg}")


def dinh_dang_thoi_gian_su_co(tong_giay):
    tong_giay = int(tong_giay)
    gio = tong_giay // 3600
    phut = (tong_giay % 3600) // 60
    giay = tong_giay % 60
    if gio > 0:
        return f"{gio} giờ {phut} phút {giay} giây"
    elif phut > 0:
        return f"{phut} phút {giay} giây"
    else:
        return f"{giay} giây"


def kiem_tra_canh_bao_hai_chieu(temp1, temp2, speed, pressure, current):
    global dang_bi_loi, thoi_diem_bat_dau_loi, thoi_diem_canh_bao_cuoi

    danh_sach_loi = []
    if temp1 > NGUONG_TEMP1:
        danh_sach_loi.append(f"• <b>Nhiệt độ 1 quá cao:</b> {temp1:.1f}°C (Ngưỡng: {NGUONG_TEMP1}°C)")
    if temp2 > NGUONG_TEMP2:
        danh_sach_loi.append(f"• <b>Nhiệt độ 2 quá cao:</b> {temp2:.1f}°C (Ngưỡng: {NGUONG_TEMP2}°C)")
    if current > NGUONG_CURRENT:
        danh_sach_loi.append(f"• <b>Dòng điện động cơ quá tải:</b> {current:.2f} A (Ngưỡng: {NGUONG_CURRENT} A)")

    bay_gio = time.time()
    gio_hien_tai_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

    # TRƯỜNG HỢP 1: CÓ THÔNG SỐ VƯỢT NGƯỠNG
    if danh_sach_loi:
        chi_tiet_loi = "\n".join(danh_sach_loi)

        if not dang_bi_loi:
            dang_bi_loi = True
            thoi_diem_bat_dau_loi = bay_gio
            thoi_diem_canh_bao_cuoi = bay_gio

            tin_nhan_do = (
                f"🚨 <b>BÁO ĐỘNG ĐỎ: VƯỢT NGƯỠNG ({VI_TRI_MAY_TRAM})</b> 🚨\n"
                f"⏰ Thời điểm phát hiện: {gio_hien_tai_str}\n\n"
                f"{chi_tiet_loi}\n\n"
                f"📊 <b>Thông số tức thời:</b>\n"
                f"- Tốc độ: {speed:.1f} | Áp suất: {pressure:.2f}\n"
                f"👉 Kỹ thuật viên vui lòng kiểm tra thiết bị ngay!"
            )
            gui_tin_nhan_telegram(tin_nhan_do, "BÁO ĐỘNG ĐỎ")

        elif bay_gio - thoi_diem_canh_bao_cuoi >= THOI_GIAN_NGHI_CANH_BAO:
            thoi_diem_canh_bao_cuoi = bay_gio
            thoi_gian_da_loi = dinh_dang_thoi_gian_su_co(bay_gio - thoi_diem_bat_dau_loi)

            tin_nhan_nhac = (
                f"🟠 <b>NHẮC LẠI SỰ CỐ CHƯA KHẮC PHỤC ({VI_TRI_MAY_TRAM})</b> 🟠\n"
                f"⏳ Sự cố đã kéo dài: <b>{thoi_gian_da_loi}</b>\n\n"
                f"{chi_tiet_loi}\n"
                f"📊 Tốc độ: {speed:.1f} | Áp suất: {pressure:.2f}"
            )
            gui_tin_nhan_telegram(tin_nhan_nhac, "Nhắc lại sự cố")

    # TRƯỜNG HỢP 2: TẤT CẢ THÔNG SỐ ĐỀU AN TOÀN
    else:
        if dang_bi_loi:
            tong_thoi_gian_loi = dinh_dang_thoi_gian_su_co(bay_gio - thoi_diem_bat_dau_loi)
            dang_bi_loi = False
            thoi_diem_bat_dau_loi = None
            thoi_diem_canh_bao_cuoi = 0

            tin_nhan_xanh = (
                f"✅ <b>HỆ THỐNG ĐÃ AN TOÀN TRỞ LẠI ({VI_TRI_MAY_TRAM})</b> ✅\n"
                f"⏰ Thời điểm phục hồi: {gio_hien_tai_str}\n"
                f"⏱️ Tổng thời gian sự cố: <b>{tong_thoi_gian_loi}</b>\n\n"
                f"📊 <b>Thông số ổn định hiện tại:</b>\n"
                f"- Nhiệt độ 1: {temp1:.1f}°C | Nhiệt độ 2: {temp2:.1f}°C\n"
                f"- Dòng động cơ: {current:.2f} A\n"
                f"- Tốc độ: {speed:.1f} | Áp suất: {pressure:.2f}"
            )
            gui_tin_nhan_telegram(tin_nhan_xanh, "AN TOÀN TRỞ LẠI")

# Thêm 2 biến theo dõi này ở đầu tệp (dưới dòng ngay_da_nhac_pm = "")
thoi_diem_day_cloud_cuoi = 0
CHU_KY_DAY_CLOUD = 20  # Đẩy lên Supabase mỗi 20 giây nếu thông số ổn định
gia_tri_cloud_cuoi = {"temp1": 0.0, "temp2": 0.0, "current": 0.0}

def luu_va_day_du_lieu(temp1, temp2, speed, pressure, current):
    global thoi_diem_day_cloud_cuoi, gia_tri_cloud_cuoi
    thoi_gian = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    t1, t2, sp, pr, cur = round(temp1, 2), round(temp2, 2), round(speed, 2), round(pressure, 2), round(current, 2)

    # A. Luôn lưu đầy đủ 2 giây/mẫu vào SQLite cục bộ tại phòng điều khiển
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """INSERT INTO du_lieu_plc_db3 
           (thoi_gian, temp1, temp2, speed, pressure, motor_current) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (thoi_gian, t1, t2, sp, pr, cur)
    )
    conn.commit()
    conn.close()

    # B. Báo cáo theo ngoại lệ (Report by Exception) lên Supabase Cloud
    bay_gio = time.time()
    bien_dong_manh = (
        abs(t1 - gia_tri_cloud_cuoi["temp1"]) >= 1.5
        or abs(t2 - gia_tri_cloud_cuoi["temp2"]) >= 1.5
        or abs(cur - gia_tri_cloud_cuoi["current"]) >= 2.0
    )
    da_den_chu_ky = (bay_gio - thoi_diem_day_cloud_cuoi) >= CHU_KY_DAY_CLOUD

    if dang_bi_loi or bien_dong_manh or da_den_chu_ky:
        endpoint = f"{SUPABASE_URL}/rest/v1/du_lieu_plc_db3"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        du_lieu_cloud = {
            "thoi_gian": thoi_gian,
            "temp1": t1,
            "temp2": t2,
            "speed": sp,
            "pressure": pr,
            "motor_current": cur
        }
        res = requests.post(endpoint, json=du_lieu_cloud, headers=headers, timeout=10)
        res.raise_for_status()
        thoi_diem_day_cloud_cuoi = bay_gio
        gia_tri_cloud_cuoi = {"temp1": t1, "temp2": t2, "current": cur}


def don_dep_du_lieu_cloud(so_ngay_giu_lai=7):
    try:
        moc_thoi_gian = (datetime.now() - timedelta(days=so_ngay_giu_lai)).strftime("%Y-%m-%d %H:%M:%S")
        endpoint = f"{SUPABASE_URL}/rest/v1/du_lieu_plc_db3?thoi_gian=lt.{moc_thoi_gian}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Prefer": "return=minimal"
        }
        res = requests.delete(endpoint, headers=headers, timeout=10)
        res.raise_for_status()
        print(f"🧹 Đã tự động dọn dẹp dữ liệu Cloud cũ hơn {so_ngay_giu_lai} ngày.")
    except Exception as e_clean:
        print(f"⚠️ Lỗi khi dọn dẹp dữ liệu cũ: {e_clean}")
def kiem_tra_nhac_lich_bao_duong_pm():
    global ngay_da_nhac_pm
    hom_nay_str = datetime.now().strftime("%Y-%m-%d")
    gio_phut = datetime.now().strftime("%H:%M")

    # Chỉ gửi nhắc việc 1 lần duy nhất mỗi ngày vào khung 07:30 sáng (đầu Ca Ngày)
    if gio_phut != "07:30" or ngay_da_nhac_pm == hom_nay_str:
        return

    try:
        endpoint = f"{SUPABASE_URL}/rest/v1/lich_bao_duong_pm?select=*"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Cache-Control": "no-cache"
        }
        res = requests.get(endpoint, headers=headers, timeout=10)
        res.raise_for_status()
        ds_pm = res.json()

        hom_nay_date = datetime.now().date()
        danh_sach_can_nhac = []

        for item in ds_pm:
            ngay_han = datetime.strptime(item["ngay_den_han"], "%Y-%m-%d").date()
            so_ngay = (ngay_han - hom_nay_date).days
            if so_ngay < 0:
                danh_sach_can_nhac.append(f"🔴 <b>QUÁ HẠN {abs(so_ngay)} NGÀY:</b> {item['hang_muc']} ({item['cum_thiet_bi']}) — Phụ trách: {item['nguoi_phu_trach']}")
            elif so_ngay <= 3:
                danh_sach_can_nhac.append(f"🟡 <b>SẮP ĐẾN HẠN (Còn {so_ngay} ngày):</b> {item['hang_muc']} ({item['cum_thiet_bi']}) — Hạn: {item['ngay_den_han']}")

        if danh_sach_can_nhac:
            noi_dung_nhac = (
                f"🗓️ <b>NHẮC VIỆC BẢO DƯỠNG ĐỊNH KỲ (PM / CIL) - {hom_nay_str}</b>\n\n"
                + "\n".join(danh_sach_can_nhac)
                + "\n\n👉 Sau khi thực hiện xong, vui lòng vào <b>Tab 3</b> trên Web bấm <b>'✅ Đã hoàn thành'</b> để hệ thống tính chu kỳ tiếp theo."
            )
            gui_tin_nhan_telegram(noi_dung_nhac, "Nhắc lịch bảo dưỡng PM")

        ngay_da_nhac_pm = hom_nay_str
    except Exception as e_pm:
        print(f"⚠️ Lỗi kiểm tra lịch PM: {e_pm}")


# 2b. Theo dõi sự kiện kết nối PLC để truy vết sau (mất kết nối / phục hồi)
def khoi_tao_bang_su_kien_ket_noi():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS su_kien_ket_noi_plc (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thoi_gian TEXT,
            su_kien TEXT,
            chi_tiet TEXT,
            thoi_gian_gian_doan_giay REAL
        )
    """)
    conn.commit()
    conn.close()


def ghi_su_kien_ket_noi(su_kien, chi_tiet="", thoi_gian_gian_doan_giay=None):
    """Ghi 1 sự kiện kết nối PLC vào SQLite cục bộ.

    su_kien: MAT_KET_NOI | KHOI_PHUC
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            """INSERT INTO su_kien_ket_noi_plc
               (thoi_gian, su_kien, chi_tiet, thoi_gian_gian_doan_giay)
               VALUES (?, ?, ?, ?)""",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                su_kien,
                str(chi_tiet),
                thoi_gian_gian_doan_giay,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e_sk:
        print(f"⚠️ Không ghi được sự kiện kết nối vào SQLite: {e_sk}")


def tao_client_plc():
    """Tạo client Snap7 mới và đặt timeout kết nối/đọc.

    Rack/slot được xử lý bên trong connect(); timeout đặt qua set_param()
    (PingTimeout / SendTimeout / RecvTimeout) để không bị treo khi PLC mất mạng.
    """
    client = snap7.client.Client()
    for ten_tham_so, gia_tri in (
        ("PingTimeout", PLC_TIMEOUT_MS),
        ("SendTimeout", PLC_TIMEOUT_MS),
        ("RecvTimeout", PLC_TIMEOUT_MS),
    ):
        so_hieu = getattr(snap7.types, ten_tham_so, None)
        if so_hieu is None:
            continue
        try:
            client.set_param(so_hieu, gia_tri)
        except Exception as e_param:
            print(f"⚠️ Không đặt được {ten_tham_so}={gia_tri}ms: {e_param}")
    return client


def ket_noi_plc(so_lan_thu=None, cho_giay_dau=None, cho_giay_toi_da=None):
    """Kết nối tới PLC, tự thử lại với backoff luỹ thừa.

    so_lan_thu=None -> thử mãi cho tới khi thành công (không thoát script).
    Trả về True nếu kết nối được, False nếu đã hết số lần thử.
    """
    global plc
    cho_giay_dau = PLC_RETRY_CHO_DAU if cho_giay_dau is None else cho_giay_dau
    cho_giay_toi_da = PLC_RETRY_CHO_TOI_DA if cho_giay_toi_da is None else cho_giay_toi_da
    lan = 0
    cho = cho_giay_dau

    while so_lan_thu is None or lan < so_lan_thu:
        lan += 1
        try:
            if plc.get_connected():
                plc.disconnect()
        except Exception:
            pass
        try:
            plc.connect(PLC_IP, PLC_RACK, PLC_SLOT)
            if plc.get_connected():
                print(f"✅ Kết nối PLC thành công (lần thử {lan}).")
                return True
        except Exception as e_conn:
            print(f"⚠️ Lần thử {lan} thất bại: {e_conn}")
            try:
                plc.disconnect()
            except Exception:
                pass
            plc = tao_client_plc()  # tạo client mới để xoá trạng thái lỗi

        if so_lan_thu is not None and lan >= so_lan_thu:
            break
        print(f"   ↻ Thử lại sau {cho}s...")
        time.sleep(cho)
        cho = min(cho * 2, cho_giay_toi_da)

    return False


def khong_con_ket_noi():
    try:
        return not plc.get_connected()
    except Exception:
        return True


def xu_ly_mat_ket_noi(ly_do):
    """Ghi SQLite + cảnh báo Telegram khi mất kết nối (chỉ 1 lần mỗi đợt)."""
    global dang_mat_ket_noi, thoi_diem_mat_ket_noi
    if dang_mat_ket_noi:
        return
    dang_mat_ket_noi = True
    thoi_diem_mat_ket_noi = datetime.now()

    print(f"🔌 MẤT KẾT NỐI PLC: {ly_do}")
    ghi_su_kien_ket_noi("MAT_KET_NOI", ly_do)
    gui_tin_nhan_telegram(
        f"🔌 <b>MẤT KẾT NỐI PLC</b>\n"
        f"📍 Trạm: {VI_TRI_MAY_TRAM}\n"
        f"🌐 Địa chỉ: {PLC_IP} (rack {PLC_RACK}, slot {PLC_SLOT})\n"
        f"⚠️ Lý do: {ly_do}\n"
        f"⏰ Thời điểm: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}\n"
        f"🔁 Hệ thống đang tự động thử kết nối lại...",
        "MẤT KẾT NỐI PLC",
    )


def xu_ly_khoi_phuc():
    """Ghi SQLite + báo Telegram khi kết nối lại được, kèm thời gian gián đoạn."""
    global dang_mat_ket_noi, thoi_diem_mat_ket_noi
    if not dang_mat_ket_noi:
        return

    tong_giay = 0.0
    if thoi_diem_mat_ket_noi:
        tong_giay = (datetime.now() - thoi_diem_mat_ket_noi).total_seconds()
    dang_mat_ket_noi = False
    thoi_diem_mat_ket_noi = None

    print(f"✅ ĐÃ KẾT NỐI LẠI PLC (gián đoạn {dinh_dang_thoi_gian_su_co(tong_giay)}).")
    ghi_su_kien_ket_noi(
        "KHOI_PHUC",
        f"Gián đoạn {dinh_dang_thoi_gian_su_co(tong_giay)}",
        round(tong_giay, 1),
    )
    gui_tin_nhan_telegram(
        f"✅ <b>ĐÃ KẾT NỐI LẠI PLC</b>\n"
        f"📍 Trạm: {VI_TRI_MAY_TRAM}\n"
        f"⏱️ Tổng thời gian gián đoạn: <b>{dinh_dang_thoi_gian_su_co(tong_giay)}</b>\n"
        f"⏰ Thời điểm: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}",
        "KẾT NỐI LẠI PLC",
    )


# 3. Kết nối PLC và chạy vòng lặp đọc - ghi - cảnh báo 2 chiều
khoi_tao_bang_plc()
khoi_tao_bang_su_kien_ket_noi()
plc = tao_client_plc()

print(f"Đang kết nối tới PLC Siemens ({PLC_IP}) cho trạm [{VI_TRI_MAY_TRAM}]...")

# Thử nhanh vài lần; nếu vẫn thất bại thì báo Telegram rồi kiên trì thử lại (không thoát script)
if not ket_noi_plc(so_lan_thu=PLC_RETRY_SO_LAN):
    xu_ly_mat_ket_noi(
        f"Không kết nối được tới {PLC_IP} (rack {PLC_RACK}, slot {PLC_SLOT}) "
        f"sau {PLC_RETRY_SO_LAN} lần thử"
    )
    ket_noi_plc()          # thử mãi cho tới khi PLC lên nguồn / thông mạng
    xu_ly_khoi_phuc()

print("✅ Kết nối thành công! Hệ thống giám sát 2 chiều & đồng bộ ngưỡng đang chạy.\n")

dem_chu_ky = 0

try:
    while True:
        try:
            # Đồng bộ lại ngưỡng cảnh báo từ Supabase mỗi 60 giây (20 chu kỳ x 3s)
            if dem_chu_ky % 20 == 0:
                dong_bo_nguong_tu_cloud()
                kiem_tra_nhac_lich_bao_duong_pm()

            data = plc.db_read(DB_NUMBER, 0, 20)
            temp1 = get_real(data, 0)
            temp2 = get_real(data, 4)
            speed = get_real(data, 8)
            pressure = get_real(data, 12)
            motor_current = get_real(data, 16)

            # Kiểm tra cảnh báo 2 chiều (Báo lỗi & Báo phục hồi)
            kiem_tra_canh_bao_hai_chieu(temp1, temp2, speed, pressure, motor_current)

            # Lưu SQLite & Đẩy lên Cloud
            luu_va_day_du_lieu(temp1, temp2, speed, pressure, motor_current)

            gio = datetime.now().strftime("%H:%M:%S")
            trang_thai_text = "🔴 ĐANG LỖI" if dang_bi_loi else "🟢 AN TOÀN"
            print(
                f"[{gio}] {trang_thai_text} (Ngưỡng: {NGUONG_TEMP1}°C/{NGUONG_CURRENT}A) | "
                f"T1: {temp1:.1f}°C | T2: {temp2:.1f}°C | "
                f"Spd: {speed:.1f} | Prs: {pressure:.2f} | Cur: {motor_current:.2f} A"
            )

            dem_chu_ky += 1
            if dem_chu_ky >= 1000:
                don_dep_du_lieu_cloud(so_ngay_giu_lai=7)
                dem_chu_ky = 0

        except Exception as e_read:
            print(f"⚠️ Lỗi đọc/gửi dữ liệu: {e_read}")
            # Nếu nguyên nhân là mất kết nối PLC -> cảnh báo, ghi log và tự kết nối lại
            if khong_con_ket_noi():
                xu_ly_mat_ket_noi(e_read)
                if ket_noi_plc():
                    xu_ly_khoi_phuc()
                    dem_chu_ky = 0

        time.sleep(2)
finally:
    try:
        if plc.get_connected():
            plc.disconnect()
    except Exception:
        pass



