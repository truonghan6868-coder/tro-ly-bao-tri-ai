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

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Ngưỡng cảnh báo an toàn
NGUONG_TEMP1 = float(os.getenv("NGUONG_TEMP1", 80.0))
NGUONG_TEMP2 = float(os.getenv("NGUONG_TEMP2", 80.0))
NGUONG_CURRENT = float(os.getenv("NGUONG_CURRENT", 65.0))

# Biến theo dõi trạng thái lỗi 2 chiều & chống spam
dang_bi_loi = False
thoi_diem_bat_dau_loi = None
thoi_diem_canh_bao_cuoi = 0
THOI_GIAN_NGHI_CANH_BAO = 300  # Nhắc lại sau mỗi 5 phút nếu lỗi chưa khắc phục

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

def gui_tin_nhan_telegram(noi_dung_tin_nhan, loai_thong_bao="Cảnh báo"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        # Tách chuỗi URL để đảm bảo không bị lỗi định dạng
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
            # Chuyển trạng thái từ Bình thường -> Bị lỗi (Gửi Báo động đỏ ngay lập tức)
            dang_bi_loi = True
            thoi_diem_bat_dau_loi = bay_gio
            thoi_diem_canh_bao_cuoi = bay_gio

            tin_nhan_do = (
                f"🚨 <b>BÁO ĐỘNG ĐỎ: VƯỢT NGƯỠNG PLC SIEMENS (DB3)</b> 🚨\n"
                f"⏰ Thời điểm phát hiện: {gio_hien_tai_str}\n\n"
                f"{chi_tiet_loi}\n\n"
                f"📊 <b>Thông số tức thời:</b>\n"
                f"- Tốc độ: {speed:.1f} | Áp suất: {pressure:.2f}\n"
                f"👉 Kỹ thuật viên vui lòng kiểm tra thiết bị ngay!"
            )
            gui_tin_nhan_telegram(tin_nhan_do, "BÁO ĐỘNG ĐỎ")

        elif bay_gio - thoi_diem_canh_bao_cuoi >= THOI_GIAN_NGHI_CANH_BAO:
            # Đang bị lỗi kéo dài quá 5 phút -> Gửi tin nhắc lại
            thoi_diem_canh_bao_cuoi = bay_gio
            thoi_gian_da_loi = dinh_dang_thoi_gian_su_co(bay_gio - thoi_diem_bat_dau_loi)

            tin_nhan_nhac = (
                f"🟠 <b>NHẮC LẠI SỰ CỐ CHƯA KHẮC PHỤC (DB3)</b> 🟠\n"
                f"⏳ Sự cố đã kéo dài: <b>{thoi_gian_da_loi}</b>\n\n"
                f"{chi_tiet_loi}\n"
                f"📊 Tốc độ: {speed:.1f} | Áp suất: {pressure:.2f}"
            )
            gui_tin_nhan_telegram(tin_nhan_nhac, "Nhắc lại sự cố")

    # TRƯỜNG HỢP 2: TẤT CẢ THÔNG SỐ ĐỀU AN TOÀN
    else:
        if dang_bi_loi:
            # Chuyển trạng thái từ Bị lỗi -> An toàn trở lại (Gửi Báo xanh phục hồi)
            tong_thoi_gian_loi = dinh_dang_thoi_gian_su_co(bay_gio - thoi_diem_bat_dau_loi)
            dang_bi_loi = False
            thoi_diem_bat_dau_loi = None
            thoi_diem_canh_bao_cuoi = 0

            tin_nhan_xanh = (
                f"✅ <b>HỆ THỐNG ĐÃ AN TOÀN TRỞ LẠI (DB3)</b> ✅\n"
                f"⏰ Thời điểm phục hồi: {gio_hien_tai_str}\n"
                f"⏱️ Tổng thời gian sự cố: <b>{tong_thoi_gian_loi}</b>\n\n"
                f"📊 <b>Thông số ổn định hiện tại:</b>\n"
                f"- Nhiệt độ 1: {temp1:.1f}°C | Nhiệt độ 2: {temp2:.1f}°C\n"
                f"- Dòng động cơ: {current:.2f} A\n"
                f"- Tốc độ: {speed:.1f} | Áp suất: {pressure:.2f}"
            )
            gui_tin_nhan_telegram(tin_nhan_xanh, "AN TOÀN TRỞ LẠI")

def luu_va_day_du_lieu(temp1, temp2, speed, pressure, current):
    thoi_gian = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    t1, t2, sp, pr, cur = round(temp1, 2), round(temp2, 2), round(speed, 2), round(pressure, 2), round(current, 2)

    # A. Lưu dự phòng vào SQLite trên máy tính
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

    # B. Đẩy thẳng lên Supabase Cloud
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

# 3. Kết nối PLC và chạy vòng lặp đọc - ghi - cảnh báo 2 chiều
khoi_tao_bang_plc()
plc = snap7.client.Client()

print(f"Đang kết nối tới PLC Siemens ({PLC_IP}), Supabase & Telegram 2 chiều...")

try:
    plc.connect(PLC_IP, PLC_RACK, PLC_SLOT)
    if plc.get_connected():
        print("✅ Kết nối thành công! Hệ thống giám sát 2 chiều đang hoạt động.\n")
        dem_chu_ky = 0

        while True:
            try:
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
                    f"[{gio}] {trang_thai_text} | Temp1: {temp1:.1f}°C | Temp2: {temp2:.1f}°C | "
                    f"Speed: {speed:.1f} | Press: {pressure:.2f} | Current: {motor_current:.2f} A"
                )

                dem_chu_ky += 1
                if dem_chu_ky >= 1000:
                    don_dep_du_lieu_cloud(so_ngay_giu_lai=7)
                    dem_chu_ky = 0
                
            except Exception as e_read:
                print(f"⚠️ Lỗi đọc/gửi dữ liệu: {e_read}")
                
            time.sleep(3)
except Exception as e_conn:
    print(f"❌ Không thể kết nối tới PLC: {e_conn}")
finally:
    if plc.get_connected():
        plc.disconnect()

