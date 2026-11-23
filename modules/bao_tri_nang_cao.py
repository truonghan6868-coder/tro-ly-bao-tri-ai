import os
from datetime import datetime, timedelta
import pandas as pd
from pypdf import PdfReader
import requests
import streamlit as st
from modules.quan_ly_ho_so import lay_danh_sach_ten_thiet_bi_cloud


def _lay_cau_hinh_supabase():
    url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    headers = {
        "apikey": key_du_an,
        "Authorization": f"Bearer {key_du_an}",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }
    return url_du_an, headers


# =====================================================================
# 1. KHO TÀI LIỆU KỸ THUẬT DÙNG CHUNG (MANUAL LIBRARY)
# =====================================================================
@st.cache_data(ttl=15, show_spinner=False)
def tai_danh_sach_tai_lieu_cloud():
    url_du_an, headers = _lay_cau_hinh_supabase()
    endpoint = f"{url_du_an}/rest/v1/thu_vien_tai_lieu?select=*&order=id.desc"
    res = requests.get(endpoint, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


def luu_tai_lieu_len_thu_vien(uploaded_file, nguoi_tai="Tổ Bảo Trì"):
    ten_file = uploaded_file.name
    noi_dung_list = []
    uploaded_file.seek(0)

    if ten_file.lower().endswith(".pdf"):
        loai = "PDF Manual"
        reader = PdfReader(uploaded_file)
        for idx, page in enumerate(reader.pages, start=1):
            txt = page.extract_text()
            if txt:
                noi_dung_list.append(f"[Trang {idx}]: {txt}")
    elif ten_file.lower().endswith(".csv"):
        loai = "CSV Data"
        df = pd.read_csv(uploaded_file)
        noi_dung_list.append(df.to_string(index=False))
    else:
        loai = "Excel Sheet"
        excel_data = pd.read_excel(uploaded_file, sheet_name=None)
        for sheet, df in excel_data.items():
            noi_dung_list.append(f"[Sheet: {sheet}]\n{df.to_string(index=False)}")

    noi_dung_gop = "\n".join(noi_dung_list)[:60000]

    url_du_an, headers = _lay_cau_hinh_supabase()
    headers["Prefer"] = "return=minimal"
    endpoint = f"{url_du_an}/rest/v1/thu_vien_tai_lieu"
    payload = {
        "ten_tai_lieu": ten_file,
        "loai_file": loai,
        "noi_dung_trich_xuat": noi_dung_gop,
        "nguoi_tai_len": nguoi_tai,
        "ngay_tai_len": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    res = requests.post(endpoint, json=payload, headers=headers, timeout=15)
    res.raise_for_status()


def xoa_tai_lieu_thu_vien(doc_id):
    st.cache_data.clear()
    url_du_an, headers = _lay_cau_hinh_supabase()
    endpoint = f"{url_du_an}/rest/v1/thu_vien_tai_lieu?id=eq.{doc_id}"
    res = requests.delete(endpoint, headers=headers, timeout=10)
    res.raise_for_status()

def trich_loc_doan_tai_lieu_lien_quan(noi_dung_goc, tu_khoa_cau_hoi="", gioi_han_ky_tu=12000):
    if not noi_dung_goc:
        return ""
    if len(noi_dung_goc) <= gioi_han_ky_tu or not tu_khoa_cau_hoi.strip():
        return noi_dung_goc[:gioi_han_ky_tu]

    cac_tu_khoa = [w.lower() for w in tu_khoa_cau_hoi.split() if len(w) >= 2]
    cac_doan = noi_dung_goc.split("\n\n")
    doan_chon = []
    tong_ky_tu = 0

    for doan in cac_doan:
        doan_lower = doan.lower()
        if any(kw in doan_lower for kw in cac_tu_khoa):
            doan_chon.append(doan)
            tong_ky_tu += len(doan)
            if tong_ky_tu >= gioi_han_ky_tu:
                break

    if not doan_chon:
        return noi_dung_goc[:gioi_han_ky_tu]
    return "\n\n".join(doan_chon)

def hien_thi_kho_tai_lieu_dung_chung():
    st.subheader("📚 Kho Tài Liệu Kỹ Thuật Dùng Chung (Cloud Manual)")
    st.caption("Tài liệu lưu tại đây được dùng chung cho cả tổ bảo trì trên mọi điện thoại mà không cần tải lại mỗi lần truy cập.")

    with st.expander("➕ Tải thêm Tài liệu Kỹ thuật mới lên Kho Dùng Chung", expanded=False):
        with st.form("form_upload_thu_vien", clear_on_submit=True):
            file_moi = st.file_uploader("Chọn file PDF (Manual Biến tần, Sơ đồ mạch) hoặc Excel:", type=["pdf", "xlsx", "xls", "csv"])
            nguoi_gui = st.text_input("Người tải lên", value="Kỹ thuật Điện - TĐH")
            if st.form_submit_button("☁️ Lưu vào Kho Dùng Chung", type="primary"):
                if file_moi is not None:
                    with st.spinner("Đang trích xuất nội dung và lưu lên Cloud..."):
                        try:
                            luu_tai_lieu_len_thu_vien(file_moi, nguoi_gui)
                            st.cache_data.clear()
                            st.success(f"✅ Đã lưu '{file_moi.name}' vào Kho Dùng Chung!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi khi lưu tài liệu: {e}")
                else:
                    st.warning("Vui lòng chọn tệp trước khi bấm lưu!")

    try:
        ds_tai_lieu = tai_danh_sach_tai_lieu_cloud()
        if ds_tai_lieu:
            cac_ten_file = [f"#{d['id']} - {d['ten_tai_lieu']} ({d['ngay_tai_len']})" for d in ds_tai_lieu]
            chon_tra_cuu = st.multiselect(
                "📌 Chọn tài liệu trong kho để AI tự động tra cứu khi trả lời:",
                options=cac_ten_file,
                default=cac_ten_file[:2],
            )
            noi_dung_chon = []
            for d in ds_tai_lieu:
                nhan = f"#{d['id']} - {d['ten_tai_lieu']} ({d['ngay_tai_len']})"
                if nhan in chon_tra_cuu:
                    noi_dung_chon.append(f"\n=== TÀI LIỆU KHO DÙNG CHUNG: {d['ten_tai_lieu']} ===\n{d['noi_dung_trich_xuat']}")

            with st.expander(f"📋 Quản lý danh sách ({len(ds_tai_lieu)} tài liệu trong kho)", expanded=False):
                for d in ds_tai_lieu:
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"📄 **{d['ten_tai_lieu']}** — `{d['loai_file']}` (Bởi: {d['nguoi_tai_len']} | {d['ngay_tai_len']})")
                    if c2.button("🗑️ Xóa", key=f"del_doc_{d['id']}"):
                        xoa_tai_lieu_thu_vien(d["id"])
                        st.rerun()

            return "\n".join(noi_dung_chon)
        else:
            st.info("Kho tài liệu dùng chung đang trống. Hãy tải lên cuốn Manual đầu tiên ở khung phía trên!")
    except Exception as e_lib:
        st.warning(f"Không thể tải danh sách kho tài liệu: {e_lib}")
    return ""


# =====================================================================
# 2. HỆ THỐNG CHẨN ĐOÁN OFFLINE DỰ PHÒNG (EXPERT RULE ENGINE)
# =====================================================================
def chan_doan_offline_du_phong(cau_hoi, df_plc=None):
    """Tự động chẩn đoán dựa trên quy tắc chuyên gia khi mất Internet hoặc API Google quá tải."""
    ket_qua = [
        "⚠️ **[CHẾ ĐỘ CHẨN ĐOÁN OFFLINE DỰ PHÒNG]** *(Kích hoạt tự động do máy chủ AI trực tuyến đang gián đoạn)*\n",
        "### 1. Phân tích nhanh thông số đo thực tế từ hệ thống:"
    ]

    if df_plc is not None and not df_plc.empty:
        moi_nhat = df_plc.to_dict(orient="records").pop(0)
        t1 = float(moi_nhat.get("temp1", 0))
        t2 = float(moi_nhat.get("temp2", 0))
        cur = float(moi_nhat.get("motor_current", 0))
        spd = float(moi_nhat.get("speed", 0))
        prs = float(moi_nhat.get("pressure", 0))
        err_acs = int(moi_nhat.get("ma_loi_acs880", 0) or 0)

        ket_qua.append(f"- **Thông số hiện tại:** Temp1 = `{t1:.1f}°C`, Temp2 = `{t2:.1f}°C`, Dòng = `{cur:.2f}A`, Tốc độ = `{spd:.1f}`, Áp suất = `{prs:.2f}`.")

        phat_hien = []
        if t1 > 80 or t2 > 80:
            phat_hien.append("🔥 **Cảnh báo Quá nhiệt (>80°C):** Kiểm tra ngay lượng mỡ bôi trơn gối trục, kiểm tra quạt làm mát cưỡng bức động cơ và độ đồng tâm khớp nối.")
        if t1 < 25 and spd > 100:
            phat_hien.append("🔌 **Nghi ngờ đứt dây/hở mạch cảm biến Temp 1 (<25°C khi máy đang chạy):** Kiểm tra đầu cốt cảm biến Pt100 tại hộp đấu dây và ngõ vào Analog PLC.")
        if abs(t1 - t2) > 15:
            phat_hien.append("⚖️ **Cảnh báo Lệch nhiệt hai đầu trục (|T1 - T2| > 15°C):** Kiểm tra lực ép không đều hai bên lô ép hoặc khô mỡ một bên ổ bi.")
        if cur > 65:
            phat_hien.append("⚡ **Cảnh báo Dòng điện tăng cao (>65A):** Kiểm tra kẹt cơ khí lô ép, độ đặc bột giấy tăng đột ngột hoặc kẹt phanh cơ khí.")
        if prs < 3.5 and spd > 100:
            phat_hien.append("⏲️ **Cảnh báo Sụt áp suất (<3.5):** Kiểm tra rò rỉ đường ống khí nén/thủy lực, van điều áp hoặc lọc khí bị nghẹt.")
        if err_acs > 0:
            phat_hien.append(f"🚨 **Biến tần ABB ACS880 báo mã lỗi `0x{err_acs:04X}` ({err_acs}):** Kiểm tra màn hình điều khiển Assistant Control Panel trên mặt tủ, kiểm tra điện áp DC Bus và cách điện cáp động cơ trước khi Reset.")

        if not phat_hien:
            phat_hien.append("✅ Các thông số cơ bản hiện nằm trong vùng vận hành ổn định. Tiếp tục theo dõi theo tiêu chuẩn CIL hằng ca.")

        ket_qua.append("\n### 2. Khuyến nghị hành động tại hiện trường:")
        ket_qua.extend(phat_hien)
    else:
        ket_qua.append("- Chưa đọc được chuỗi số liệu PLC tức thời. Kỹ thuật viên vui lòng kiểm tra trực tiếp trên màn hình HMI tại tủ điện.")

    ket_qua.append("\n### 3. Quy trình kiểm tra an toàn 3 bước (Tiêu chuẩn TPM):")
    ket_qua.append("1. **Kiểm tra trực quan (Nghe - Nhìn - Ngửi):** Phát hiện tiếng rít ổ bi, mùi khét cách điện hoặc rung động bất thường.")
    ket_qua.append("2. **Đo kiểm điện & cơ:** Dùng ampe kìm đo cân bằng dòng 3 pha, dùng súng bắn nhiệt hồng ngoại đối chiếu lại nhiệt độ thực tế.")
    ket_qua.append("3. **Ghi nhận & Bàn giao:** Cập nhật kết quả vào **Sổ Nhật Ký Bàn Giao Ca** ở Tab 1 để ca sau theo dõi.")

    return "\n".join(ket_qua)


# =====================================================================
# 3. LỊCH BẢO DƯỠNG ĐỊNH KỲ (PM / CIL REMINDER)
# =====================================================================
def tai_lich_bao_duong_pm():
    url_du_an, headers = _lay_cau_hinh_supabase()
    endpoint = f"{url_du_an}/rest/v1/lich_bao_duong_pm?select=*&order=ngay_den_han.asc"
    res = requests.get(endpoint, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


def gui_nhac_viec_pm_telegram_thu_cong(ds_pm):
    """Gửi ngay danh sách công việc bảo dưỡng định kỳ lên Telegram khi trưởng bộ phận bấm nút."""
    tg_token = os.getenv("TELEGRAM_TOKEN") or st.secrets.get("TELEGRAM_TOKEN", "")
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID") or st.secrets.get("TELEGRAM_CHAT_ID", "")
    if not tg_token or not tg_chat_id:
        return False, "Chưa cấu hình TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID."

    hom_nay = datetime.now().date()
    dong_tin = [f"🗓️ <b>DANH SÁCH KIỂM TRA & BẢO DƯỠNG (PM / CIL) - {hom_nay.strftime('%d/%m/%Y')}</b>\n"]
    for item in ds_pm:
        ngay_han = datetime.strptime(item["ngay_den_han"], "%Y-%m-%d").date()
        so_ngay = (ngay_han - hom_nay).days
        if so_ngay < 0:
            tt = f"🔴 QUÁ HẠN {abs(so_ngay)} ngày"
        elif so_ngay <= 3:
            tt = f"🟡 SẮP ĐẾN HẠN (Còn {so_ngay} ngày)"
        else:
            tt = f"🟢 Còn {so_ngay} ngày (Hạn: {item['ngay_den_han']})"
        dong_tin.append(f"• <b>{item['hang_muc']}</b> [{item['cum_thiet_bi']}] — {tt} (Phụ trách: {item['nguoi_phu_trach']})")

    dong_tin.append("\n👉 Anh em bảo trì thực hiện xong nhớ vào <b>Tab 3</b> trên Web bấm <b>'✅ Đã hoàn thành'</b> nhé!")
    url_tg = "https://" + "api.telegram.org/bot" + f"{tg_token}/sendMessage"
    res = requests.post(url_tg, json={"chat_id": tg_chat_id, "text": "\n".join(dong_tin), "parse_mode": "HTML"}, timeout=10)
    res.raise_for_status()
    return True, "Đã gửi danh sách nhắc việc lên Telegram thành công!"


def hien_thi_lich_bao_duong_pm():
    col_tieu_de, col_nut_tg = st.columns([3, 1.3])
    with col_tieu_de:
        st.subheader("🗓️ Lịch Bảo Dưỡng Định Kỳ (PM / CIL)")
        st.caption("Tự động tính ngày đến hạn tiếp theo và nhắc việc qua Telegram lúc 07:30 sáng hằng ngày.")

    try:
        ds_pm = tai_lich_bao_duong_pm()
    except Exception as e_pm:
        st.warning(f"Không thể tải lịch bảo dưỡng PM: {e_pm}")
        return

    with col_nut_tg:
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        if st.button("📲 Gửi nhắc việc Telegram ngay", use_container_width=True, disabled=not bool(ds_pm)):
            try:
                ok, msg = gui_nhac_viec_pm_telegram_thu_cong(ds_pm)
                if ok:
                    st.toast(f"✅ {msg}")
                    st.success(msg)
                else:
                    st.warning(msg)
            except Exception as e_tg:
                st.error(f"Lỗi gửi Telegram: {e_tg}")

    with st.expander("➕ Thêm Hạng Mục Bảo Dưỡng Định Kỳ Mới", expanded=False):
        with st.form("form_them_pm", clear_on_submit=True):
            p1, p2, p3 = st.columns([2, 1.5, 1])
            with p1:
                hang_muc_moi = st.text_input("Tên hạng mục bảo dưỡng", placeholder="VD: Thay dầu hộp giảm tốc Lô ép")
            with p2:
                cum_tb_moi = st.selectbox("Cụm thiết bị", lay_danh_sach_ten_thiet_bi_cloud())
            with p3:
                chu_ky_moi = st.number_input("Chu kỳ (ngày)", min_value=1, max_value=365, value=30, step=1)

            p4, p5 = st.columns(2)
            with p4:
                nguoi_pt_moi = st.text_input("Tổ phụ trách", value="Tổ Cơ Khí")
            with p5:
                ghi_chu_moi = st.text_input("Tiêu chuẩn / Vật tư", placeholder="VD: Dầu bánh răng ISO VG 220")

            if st.form_submit_button("💾 Lưu hạng mục vào lịch PM", type="primary"):
                if hang_muc_moi.strip():
                    url_du_an, headers = _lay_cau_hinh_supabase()
                    headers["Prefer"] = "return=minimal"
                    hom_nay = datetime.now().date()
                    den_han = hom_nay + timedelta(days=int(chu_ky_moi))
                    payload = {
                        "hang_muc": hang_muc_moi.strip(),
                        "cum_thiet_bi": cum_tb_moi,
                        "chu_ky_ngay": int(chu_ky_moi),
                        "ngay_thuc_hien_cuoi": hom_nay.strftime("%Y-%m-%d"),
                        "ngay_den_han": den_han.strftime("%Y-%m-%d"),
                        "nguoi_phu_trach": nguoi_pt_moi.strip(),
                        "ghi_chu": ghi_chu_moi.strip(),
                    }
                    requests.post(f"{url_du_an}/rest/v1/lich_bao_duong_pm", json=payload, headers=headers, timeout=10).raise_for_status()
                    st.success("✅ Đã thêm hạng mục bảo dưỡng định kỳ!")
                    st.rerun()
                else:
                    st.warning("Vui lòng nhập tên hạng mục bảo dưỡng!")

    if ds_pm:
        hom_nay = datetime.now().date()
        for item in ds_pm:
            ngay_han = datetime.strptime(item["ngay_den_han"], "%Y-%m-%d").date()
            so_ngay_con_lai = (ngay_han - hom_nay).days

            if so_ngay_con_lai < 0:
                badge = f"🔴 QUÁ HẠN {abs(so_ngay_con_lai)} NGÀY"
            elif so_ngay_con_lai <= 3:
                badge = f"🟡 SẮP ĐẾN HẠN (Còn {so_ngay_con_lai} ngày)"
            else:
                badge = f"🟢 Còn {so_ngay_con_lai} ngày"

            with st.container(border=True):
                col_info, col_done, col_del = st.columns([3.3, 1.1, 0.5])
                with col_info:
                    st.markdown(f"**{badge} | {item['hang_muc']}** (`{item['cum_thiet_bi']}`)")
                    st.caption(
                        f"Chu kỳ: **{item['chu_ky_ngay']} ngày** | Làm gần nhất: `{item['ngay_thuc_hien_cuoi']}` | "
                        f"Hạn tiếp theo: **`{item['ngay_den_han']}`** | Phụ trách: **{item['nguoi_phu_trach']}** | Ghi chú: {item['ghi_chu']}"
                    )
                with col_done:
                    if st.button("✅ Hoàn thành", key=f"done_pm_{item['id']}", use_container_width=True):
                        url_du_an, headers = _lay_cau_hinh_supabase()
                        ngay_moi = hom_nay + timedelta(days=int(item["chu_ky_ngay"]))
                        payload_update = {
                            "ngay_thuc_hien_cuoi": hom_nay.strftime("%Y-%m-%d"),
                            "ngay_den_han": ngay_moi.strftime("%Y-%m-%d"),
                        }
                        requests.patch(
                            f"{url_du_an}/rest/v1/lich_bao_duong_pm?id=eq.{item['id']}",
                            json=payload_update,
                            headers=headers,
                            timeout=10,
                        ).raise_for_status()
                        st.toast(f"Đã cập nhật lịch tiếp theo: {ngay_moi.strftime('%Y-%m-%d')}")
                        st.rerun()
                with col_del:
                    if st.button("🗑️", key=f"del_pm_{item['id']}", help="Xóa hạng mục này", use_container_width=True):
                        url_du_an, headers = _lay_cau_hinh_supabase()
                        requests.delete(
                            f"{url_du_an}/rest/v1/lich_bao_duong_pm?id=eq.{item['id']}",
                            headers=headers,
                            timeout=10,
                        ).raise_for_status()
                        st.toast("Đã xóa hạng mục bảo dưỡng!")
                        st.rerun()
    else:
        st.info("Chưa có hạng mục bảo dưỡng định kỳ nào.")
