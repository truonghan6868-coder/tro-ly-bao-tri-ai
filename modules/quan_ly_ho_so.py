import io
import os
from datetime import datetime
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
import requests
import streamlit as st


def _lay_headers_supabase():
    url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    headers = {
        "apikey": key_du_an,
        "Authorization": f"Bearer {key_du_an}",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    return url_du_an, headers


def lay_danh_sach_ho_so_cloud():
    url_du_an, headers = _lay_headers_supabase()
    endpoint = f"{url_du_an}/rest/v1/ho_so_bao_tri?select=*&order=id.desc"
    res = requests.get(endpoint, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


def tao_ho_so_moi_cloud(ten_ho_so, cum_thiet_bi, trang_thai, nguoi_phu_trach):
    url_du_an, headers = _lay_headers_supabase()
    headers["Prefer"] = "return=representation"
    endpoint = f"{url_du_an}/rest/v1/ho_so_bao_tri"
    thoi_gian_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "ten_ho_so": ten_ho_so,
        "cum_thiet_bi": cum_thiet_bi,
        "trang_thai": trang_thai,
        "nguoi_phu_trach": nguoi_phu_trach,
        "ngay_tao": thoi_gian_now,
        "cap_nhat_cuoi": thoi_gian_now
    }
    res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
    res.raise_for_status()
    du_lieu = res.json()
    return du_lieu.pop(0) if du_lieu else None


def cap_nhat_trang_thai_ho_so(ho_so_id, trang_thai_moi):
    url_du_an, headers = _lay_headers_supabase()
    endpoint = f"{url_du_an}/rest/v1/ho_so_bao_tri?id=eq.{ho_so_id}"
    payload = {
        "trang_thai": trang_thai_moi,
        "cap_nhat_cuoi": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    res = requests.patch(endpoint, json=payload, headers=headers, timeout=10)
    res.raise_for_status()


def xoa_ho_so_cloud(ho_so_id):
    url_du_an, headers = _lay_headers_supabase()
    endpoint = f"{url_du_an}/rest/v1/ho_so_bao_tri?id=eq.{ho_so_id}"
    res = requests.delete(endpoint, headers=headers, timeout=10)
    res.raise_for_status()


def tai_lich_su_tin_nhan_cloud(ho_so_id):
    url_du_an, headers = _lay_headers_supabase()
    endpoint = f"{url_du_an}/rest/v1/lich_su_chat_bao_tri?ho_so_id=eq.{ho_so_id}&select=*&order=id.asc"
    res = requests.get(endpoint, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


def luu_tin_nhan_cloud(ho_so_id, vai_tro, noi_dung):
    url_du_an, headers = _lay_headers_supabase()
    headers["Prefer"] = "return=minimal"
    endpoint = f"{url_du_an}/rest/v1/lich_su_chat_bao_tri"
    payload = {
        "ho_so_id": ho_so_id,
        "vai_tro": vai_tro,
        "noi_dung": noi_dung,
        "thoi_gian": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
    res.raise_for_status()


def tao_bien_ban_word_chuan_iso(thong_tin_ho_so, danh_sach_tin_nhan, tom_tat_ai=""):
    """Tạo file Word (.docx) chuẩn biểu mẫu Biên bản Xử lý Sự cố / Bảo trì nhà máy."""
    doc = Document()

    # Tiêu đề biểu mẫu
    tieu_de = doc.add_heading("BIÊN BẢN CHẨN ĐOÁN SỰ CỐ & BẢO TRÌ THIẾT BỊ", level=1)
    tieu_de.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph(f"Mã hồ sơ: #{thong_tin_ho_so.get('id')}  |  Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Bảng thông tin chung
    bang_info = doc.add_table(rows=5, cols=2)
    bang_info.style = "Table Grid"
    cac_dong_info = [
        ("Tên hồ sơ / Sự cố:", str(thong_tin_ho_so.get("ten_ho_so", ""))),
        ("Cụm thiết bị / Dây chuyền:", str(thong_tin_ho_so.get("cum_thiet_bi", ""))),
        ("Trạng thái xử lý hiện tại:", str(thong_tin_ho_so.get("trang_thai", ""))),
        ("Kỹ thuật viên phụ trách:", str(thong_tin_ho_so.get("nguoi_phu_trach", ""))),
        ("Thời điểm khởi tạo:", str(thong_tin_ho_so.get("ngay_tao", "")))
    ]
    for idx, (nhan, gia_tri) in enumerate(cac_dong_info):
        bang_info.cell(idx, 0).text = nhan
        bang_info.cell(idx, 1).text = gia_tri

    doc.add_paragraph("")

    # Phần 1: Tóm tắt kỹ thuật chuẩn hóa (Nếu có)
    if tom_tat_ai:
        doc.add_heading("I. TÓM TẮT KỸ THUẬT & PHƯƠNG ÁN XỬ LÝ (CHUẨN HÓA ISO)", level=2)
        p_tom_tat = doc.add_paragraph(tom_tat_ai)
        p_tom_tat.paragraph_format.space_after = Pt(8)

    # Phần 2: Chi tiết quá trình phân tích & Tra cứu với Trợ lý AI
    doc.add_heading("II. NHẬT KÝ PHÂN TÍCH THÔNG SỐ & CHẨN ĐOÁN CHI TIẾT", level=2)
    for tin in danh_sach_tin_nhan:
        nguoi_gui = "👷 KỸ THUẬT VIÊN" if tin.get("vai_tro") == "user" else "🤖 TRỢ LÝ AI BẢO TRÌ"
        p_header = doc.add_paragraph()
        run_h = p_header.add_run(f"[{tin.get('thoi_gian', '')}] {nguoi_gui}:")
        run_h.bold = True

        p_body = doc.add_paragraph(str(tin.get("noi_dung", "")))
        p_body.paragraph_format.left_indent = Pt(12)

    # Phần 3: Khung chữ ký xác nhận hiện trường
    doc.add_paragraph("")
    doc.add_heading("III. XÁC NHẬN HOÀN THÀNH & NGHIỆM THU BÀN GIAO", level=2)
    bang_ky = doc.add_table(rows=2, cols=3)
    bang_ky.style = "Table Grid"
    headers_ky = ["NGƯỜI LẬP BIÊN BẢN", "TRƯỞNG CA VẬN HÀNH", "TRƯỞNG BỘ PHẬN BẢO TRÌ"]
    for i, h_text in enumerate(headers_ky):
        cell_h = bang_ky.cell(0, i)
        cell_h.text = h_text
        cell_h.paragraphs.alignment = WD_ALIGN_PARAGRAPH.CENTER

        cell_b = bang_ky.cell(1, i)
        cell_b.text = "\n\n\n(Ký và ghi rõ họ tên)"
        cell_b.paragraphs.alignment = WD_ALIGN_PARAGRAPH.CENTER

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def hien_thi_sidebar_ho_so_cloud(client_gemini=None, ten_model="gemini-2.5-flash-lite"):
    """Hiển thị toàn bộ khu vực Quản lý Hồ sơ Bảo trì Đám mây trên Sidebar."""
    st.subheader("🗂️ Quản lý Hồ sơ Bảo trì (Cloud)")

    try:
        danh_sach_hs = lay_danh_sach_ho_so_cloud()
    except Exception as e:
        st.error(f"Lỗi kết nối bảng hồ sơ Supabase: {e}")
        return None, []

    if not danh_sach_hs:
        hs_moi = tao_ho_so_moi_cloud("Hồ sơ Bảo trì Mặc định", "Toàn dây chuyền Máy Xeo", "🟡 Đang theo dõi", "Tổ Điện - TĐH")
        danh_sach_hs = [hs_moi] if hs_moi else []

    # Lọc hồ sơ theo trạng thái
    bo_loc_tt = st.selectbox("🔍 Lọc theo trạng thái", [
        "Tất cả hồ sơ",
        "🔴 Đang xử lý",
        "🟡 Đang theo dõi",
        "🟢 Đã hoàn thành"
    ])
    if bo_loc_tt != "Tất cả hồ sơ":
        ds_hien_thi = [hs for hs in danh_sach_hs if hs.get("trang_thai") == bo_loc_tt]
        if not ds_hien_thi:
            ds_hien_thi = danh_sach_hs
    else:
        ds_hien_thi = danh_sach_hs

    map_ho_so = {f"{hs['trang_thai']} | #{hs['id']} - {hs['ten_ho_so']}": hs for hs in ds_hien_thi}
    nhan_da_chon = st.selectbox("📂 Chọn hồ sơ làm việc:", list(map_ho_so.keys()))
    ho_so_hien_tai = map_ho_so[nhan_da_chon]
    ho_so_id = ho_so_hien_tai["id"]

    # Cho phép đổi nhanh trạng thái của hồ sơ đang mở
    cac_trang_thai = ["🔴 Đang xử lý", "🟡 Đang theo dõi", "🟢 Đã hoàn thành"]
    idx_tt = cac_trang_thai.index(ho_so_hien_tai["trang_thai"]) if ho_so_hien_tai["trang_thai"] in cac_trang_thai else 0
    trang_thai_moi = st.selectbox("🚦 Cập nhật trạng thái hồ sơ:", cac_trang_thai, index=idx_tt)
    if trang_thai_moi != ho_so_hien_tai["trang_thai"]:
        cap_nhat_trang_thai_ho_so(ho_so_id, trang_thai_moi)
        st.toast(f"Đã chuyển trạng thái sang {trang_thai_moi}")
        st.rerun()

    # Ngăn tạo hồ sơ sự cố mới
    with st.expander("➕ Tạo Hồ Sơ Sự Cố / Bảo Trì Mới", expanded=False):
        with st.form("form_tao_ho_so_cloud", clear_on_submit=True):
            ten_moi = st.text_input("Tên sự cố / Hạng mục", placeholder="VD: Quá nhiệt ổ bi Lô ép 1")
            cum_moi = st.selectbox("Cụm thiết bị", [
                "Toàn dây chuyền Máy Xeo",
                "Cụm Lô ép (Press Roll - 75kW)",
                "Hệ thống Biến tần ABB ACS880",
                "Khu vực Sấy & Chuẩn bị bột",
                "Hệ thống Bơm chân không"
            ])
            nguoi_pt = st.text_input("Người phụ trách", placeholder="VD: Kỹ thuật Điện")
            tt_khoi_tao = st.selectbox("Mức độ / Trạng thái", cac_trang_thai)
            if st.form_submit_button("✅ Khởi tạo hồ sơ", use_container_width=True):
                if ten_moi.strip():
                    tao_ho_so_moi_cloud(ten_moi.strip(), cum_moi, tt_khoi_tao, nguoi_pt.strip() or "Tổ Bảo Trì")
                    st.success("Đã tạo hồ sơ mới trên Cloud!")
                    st.rerun()
                else:
                    st.warning("Vui lòng nhập tên hồ sơ!")

    # Tải lịch sử tin nhắn của hồ sơ hiện tại
    try:
        lich_su_tin = tai_lich_su_tin_nhan_cloud(ho_so_id)
    except Exception:
        lich_su_tin = []

    # Khu vực xuất 2 loại Biên bản Word (.docx)
    if lich_su_tin:
        st.markdown("---")
        st.markdown("**📄 Xuất Hồ Sơ Kỹ Thuật (Word):**")

        # Nút 1: AI tự động tóm tắt thành Biên bản chuẩn ISO
        if client_gemini and st.button("✨ AI Tóm tắt & Tạo Biên bản ISO", use_container_width=True):
            with st.spinner("AI đang tổng hợp biên bản kỹ thuật chuẩn ISO..."):
                try:
                    noi_dung_gop = "\n".join([f"{t['vai_tro']}: {t['noi_dung']}" for t in lich_su_tin])
                    prompt_tom_tat = (
                        "Hãy tổng hợp toàn bộ lịch sử trao đổi bảo trì dưới đây thành một bản tóm tắt kỹ thuật ngắn gọn, "
                        "chuyên nghiệp chuẩn ISO gồm 4 mục rõ ràng (dùng gạch đầu dòng thuần túy, không dùng ký tự markdown rườm rà):\n"
                        "1. Hiện tượng & Thông số bất thường ghi nhận\n"
                        "2. Nguyên nhân gốc rễ đã chẩn đoán\n"
                        "3. Biện pháp khắc phục & Vật tư thay thế đề xuất\n"
                        "4. Khuyến nghị phòng ngừa tái diễn cho ca sau\n\n"
                        f"DỮ LIỆU TRAO ĐỔI:\n{noi_dung_gop}"
                    )
                    res_ai = client_gemini.models.generate_content(model=ten_model, contents=prompt_tom_tat)
                    st.session_state[f"tom_tat_iso_{ho_so_id}"] = res_ai.text
                    st.success("Đã tạo xong bản tóm tắt chuẩn ISO! Bấm nút tải bên dưới.")
                except Exception as e_ai:
                    st.error(f"Lỗi AI tóm tắt: {e_ai}")

        tom_tat_da_co = st.session_state.get(f"tom_tat_iso_{ho_so_id}", "")
        file_word_bytes = tao_bien_ban_word_chuan_iso(ho_so_hien_tai, lich_su_tin, tom_tat_da_co)
        st.download_button(
            label="📥 Tải Biên Bản Word (.docx)",
            data=file_word_bytes,
            file_name=f"Bien_Ban_Bao_Tri_HS{ho_so_id}_{datetime.now().strftime('%Y%m%d')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
            use_container_width=True
        )

    # Nút xóa hồ sơ hiện tại (nếu có nhiều hơn 1 hồ sơ)
    if len(danh_sach_hs) > 1:
        with st.expander("🗑️ Xóa hồ sơ này", expanded=False):
            if st.button("Xác nhận xóa vĩnh viễn", type="secondary", use_container_width=True):
                xoa_ho_so_cloud(ho_so_id)
                st.rerun()

    return ho_so_id, lich_su_tin
