import os
import time
from datetime import datetime
import pandas as pd
from pypdf import PdfReader
import requests
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

from modules.quan_ly_ho_so import (
    hien_thi_sidebar_ho_so_cloud,
    luu_tin_nhan_cloud,
    tao_bien_ban_word_chuan_iso,
)
from modules.tab_bao_cao import hien_thi_tab_bao_cao
from modules.tab_giam_sat import hien_thi_tab_giam_sat

load_dotenv()
client = genai.Client()

#DANH_SACH_MODEL = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
DANH_SACH_MODEL = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]

st.set_page_config(page_title="Hệ thống AI Bảo trì Tự chủ", page_icon="🏭", layout="wide")

# --- BẢO MẬT: MÀN HÌNH ĐĂNG NHẬP NỘI BỘ ---
if "da_dang_nhap" not in st.session_state:
    st.session_state.da_dang_nhap = False

if not st.session_state.da_dang_nhap:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.title("🔒 Đăng nhập Hệ thống Bảo trì")
        st.info("Vui lòng nhập mật khẩu nội bộ tổ bảo trì để truy cập hệ thống AI.")
        mat_khau_nhap = st.text_input("Mật khẩu truy cập:", type="password")
        if st.button("Đăng nhập", use_container_width=True):
            mat_khau_dung = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD", "123456"))
            if mat_khau_nhap == mat_khau_dung:
                st.session_state.da_dang_nhap = True
                st.rerun()
            else:
                st.error("❌ Mật khẩu không chính xác!")
    st.stop()


def doc_du_lieu_bang(uploaded_file):
    ten_file = uploaded_file.name
    noi_dung_text = [f"\n--- DỮ LIỆU TỪ FILE: {ten_file} ---"]
    try:
        uploaded_file.seek(0)
        if ten_file.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            noi_dung_text.append(df.to_string(index=False))
        else:
            excel_data = pd.read_excel(uploaded_file, sheet_name=None)
            for ten_sheet, df in excel_data.items():
                noi_dung_text.append(f"\n[Sheet: {ten_sheet}]")
                noi_dung_text.append(df.to_string(index=False))
    except Exception as e:
        noi_dung_text.append(f"Lỗi khi đọc file {ten_file}: {e}")
    return "\n".join(noi_dung_text)


def doc_noi_dung_pdf(uploaded_file):
    ten_file = uploaded_file.name
    noi_dung_text = [f"\n--- NỘI DUNG TÀI LIỆU PDF: {ten_file} ---"]
    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)
        for so_trang, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text:
                noi_dung_text.append(f"[Trang {so_trang}]:\n{text}")
    except Exception as e:
        noi_dung_text.append(f"Lỗi đọc PDF {ten_file}: {e}")
    return "\n".join(noi_dung_text)


# --- THANH BÊN (SIDEBAR): QUẢN LÝ HỒ SƠ CLOUD & TÀI LIỆU ---
with st.sidebar:
    #ho_so_hien_tai_id, danh_sach_tin_nhan = hien_thi_sidebar_ho_so_cloud(client, "gemini-2.5-flash-lite")
    ho_so_hien_tai_id, danh_sach_tin_nhan = hien_thi_sidebar_ho_so_cloud(client, "gemini-3.5-flash-lite")

    st.session_state.phien_hien_tai = ho_so_hien_tai_id

    st.divider()

    vai_tro_hien_tai = st.selectbox(
        "🧠 Chế độ chuyên môn AI:",
        [
            "Kỹ sư Bảo trì & Chẩn đoán lỗi",
            "Bảo trì Tự chủ (CIL & Phát hiện bất thường)",
            "Chuyên gia Lập trình PLC / SCADA",
            "Phân tích Nhật ký Bảo trì & Số liệu",
            "Tra cứu Tài liệu Kỹ thuật (Manual)",
        ],
    )

    prompts_map = {
        "Bảo trì Tự chủ (CIL & Phát hiện bất thường)": (
            "Bạn là chuyên gia triển khai Bảo trì Tự chủ (Autonomous Maintenance - TPM) trong nhà máy công nghiệp. "
            "Hãy hỗ trợ lập tiêu chuẩn Vệ sinh - Kiểm tra - Bôi trơn (CIL), nhận diện điểm bất thường (Fuguai) "
            "và hướng dẫn kiểm tra an toàn cho vận hành viên."
        ),
        "Kỹ sư Bảo trì & Chẩn đoán lỗi": (
            "Bạn là kỹ sư trưởng bảo trì điện và tự động hóa nhà máy. Hãy phân tích nguyên nhân gốc rễ, "
            "đưa ra các bước kiểm tra an toàn, thông số đo đạc thực tế và phương án khắc phục sự cố ngắn gọn, chính xác."
        ),
        "Chuyên gia Lập trình PLC / SCADA": (
            "Bạn là chuyên gia lập trình tự động hóa (Siemens PLC, Structured Text SCL, Ladder, SCADA, IoT). "
            "Hãy viết code tối ưu, có chú thích rõ ràng và hướng dẫn cấu hình truyền thông chuẩn xác."
        ),
        "Phân tích Nhật ký Bảo trì & Số liệu": (
            "Bạn là chuyên gia phân tích dữ liệu bảo trì dự đoán. Từ dữ liệu Excel/CSV cung cấp, hãy thống kê "
            "tần suất lỗi, chỉ ra thiết bị có nguy cơ hư hỏng cao và đề xuất kế hoạch bảo trì phòng ngừa."
        ),
    }
    system_prompt = prompts_map.get(
        vai_tro_hien_tai,
        "Bạn là trợ lý kỹ thuật chuyên đọc hiểu và trích xuất thông số từ nhiều tài liệu Manual PDF. Luôn ghi rõ tên tài liệu và mục liên quan.",
    )

    st.divider()
    st.subheader("📎 Nạp Tài liệu & Nhật ký")
    uploaded_files = st.file_uploader(
        "Chọn nhiều file PDF, Excel (.xlsx) hoặc CSV:",
        type=["pdf", "xlsx", "xls", "csv"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        st.success(f"Đang đính kèm {len(uploaded_files)} file:")
        for f in uploaded_files:
            st.caption(f"• {f.name}")

# --- TIÊU ĐỀ CHÍNH ---
st.title(f"⚙️ Hồ sơ Bảo trì #{ho_so_hien_tai_id if ho_so_hien_tai_id else 1}")
st.caption(f"Chế độ AI: **{vai_tro_hien_tai}** | Đồng bộ trực tuyến thời gian thực qua Supabase Cloud")

# Lấy dữ liệu chung từ Supabase Cloud
df_plc = pd.DataFrame()
loi_ket_noi_plc = ""
try:
    url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    endpoint = f"{url_du_an}/rest/v1/du_lieu_plc_db3?select=thoi_gian,temp1,temp2,speed,pressure,motor_current&order=id.desc&limit=50"
    headers = {
        "apikey": key_du_an,
        "Authorization": f"Bearer {key_du_an}",
        "Cache-Control": "no-cache",
    }
    phan_hoi = requests.get(endpoint, headers=headers, timeout=10)
    phan_hoi.raise_for_status()
    df_plc = pd.DataFrame(phan_hoi.json())
except Exception as e_plc:
    loi_ket_noi_plc = str(e_plc)

# Chia giao diện thành 3 Tab chuyên biệt
tab_giam_sat, tab_ai_chat, tab_thong_ke = st.tabs([
    "📡 1. Bảng Điện Tử & Vận Hành Ca",
    "🤖 2. Trợ Lý AI & Chẩn Đoán",
    "📊 3. Thống Kê & Báo Cáo Excel",
])

with tab_giam_sat:
    hien_thi_tab_giam_sat(df_plc, loi_ket_noi_plc, luu_tin_nhan_cloud)

with tab_thong_ke:
    hien_thi_tab_bao_cao(df_plc)

with tab_ai_chat:
    # --- KHU VỰC TRỰC QUAN HÓA DỮ LIỆU EXCEL ---
    if uploaded_files:
        cac_file_excel = [f for f in uploaded_files if f.name.lower().endswith((".xlsx", ".xls", ".csv"))]
        if cac_file_excel:
            with st.expander("📊 Biểu đồ Phân tích Nhanh từ File Excel", expanded=True):
                file_chon = st.selectbox("Chọn file số liệu muốn vẽ biểu đồ:", cac_file_excel, format_func=lambda x: x.name)
                try:
                    file_chon.seek(0)
                    df_chart = pd.read_csv(file_chon) if file_chon.name.endswith(".csv") else pd.read_excel(file_chon)

                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        loai_bieu_do = st.selectbox("Loại biểu đồ:", ["Biểu đồ Cột (Thống kê tần suất)", "Biểu đồ Đường (Xu hướng thông số)"])
                    with col_b:
                        cot_x = st.selectbox("Chọn cột danh mục / thời gian:", df_chart.columns)
                    with col_c:
                        cot_y = st.selectbox("Chọn cột giá trị đo (nếu vẽ đường):", df_chart.columns)

                    if loai_bieu_do == "Biểu đồ Cột (Thống kê tần suất)":
                        thong_ke = df_chart[cot_x].value_counts()
                        st.bar_chart(thong_ke)
                    else:
                        du_lieu_ve = df_chart.set_index(cot_x)[cot_y]
                        st.line_chart(du_lieu_ve)
                except Exception as e:
                    st.warning(f"Không thể vẽ biểu đồ từ cột đã chọn: {e}")

    # --- HIỂN THỊ LỊCH SỬ HỘI THOẠI TỪ SUPABASE CLOUD ---
    for tin in danh_sach_tin_nhan:
        role = tin.get("vai_tro", "assistant")
        content = tin.get("noi_dung", "")
        msg_id = tin.get("id", 0)

        with st.chat_message(role):
            st.markdown(content)
            if role == "assistant":
                info_tam = {"id": ho_so_hien_tai_id, "ten_ho_so": f"Hồ sơ #{ho_so_hien_tai_id}", "cum_thiet_bi": "Dây chuyền Máy Xeo", "trang_thai": "Đang theo dõi", "nguoi_phu_trach": "Tổ Bảo Trì", "ngay_tao": ""}
                single_word = tao_bien_ban_word_chuan_iso(info_tam, [tin])
                st.download_button(
                    label="📄 Xuất phương án này ra biểu mẫu Word (.docx)",
                    data=single_word,
                    file_name=f"Phuong_an_xu_ly_{msg_id}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"word_btn_{msg_id}",
                )

    prompt_tu_plc = st.session_state.pop("tu_dong_hoi_plc", None)
    prompt_nhap_tay = st.chat_input("Nhập yêu cầu (VD: Lập bảng kiểm tra CIL hằng ngày cho cụm lô ép, hoặc phân tích lỗi từ file đính kèm)...")

    if prompt := (prompt_tu_plc or prompt_nhap_tay):
        if not prompt_tu_plc and ho_so_hien_tai_id:
            luu_tin_nhan_cloud(ho_so_hien_tai_id, "user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Đang phân tích dữ liệu kỹ thuật và lưu lên Cloud..."):
                noi_dung_gui = []
                du_lieu_tai_lieu_gop = []

                if uploaded_files:
                    for file in uploaded_files:
                        if file.name.lower().endswith(".pdf"):
                            du_lieu_tai_lieu_gop.append(doc_noi_dung_pdf(file))
                        elif file.name.lower().endswith((".xlsx", ".xls", ".csv")):
                            du_lieu_tai_lieu_gop.append(doc_du_lieu_bang(file))

                ngu_canh_cu = "\n".join([f"{t.get('vai_tro')}: {t.get('noi_dung')}" for t in danh_sach_tin_nhan[-6:]])
                cau_hoi_day_du = f"Lịch sử trao đổi gần đây:\n{ngu_canh_cu}\n\n"
                if du_lieu_tai_lieu_gop:
                    cau_hoi_day_du += "Tài liệu kỹ thuật & Số liệu đính kèm:\n" + "\n".join(du_lieu_tai_lieu_gop) + "\n\n"
                cau_hoi_day_du += f"Yêu cầu hiện tại: {prompt}"

                noi_dung_gui.append(cau_hoi_day_du)

                cau_tra_loi = ""
                danh_sach_loi = []
                thoi_gian_cho = [2, 4, 6]

                for lan_thu, ten_model in enumerate(DANH_SACH_MODEL):
                    try:
                        response = client.models.generate_content(
                            model=ten_model,
                            contents=noi_dung_gui,
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt,
                                temperature=0.2,
                            ),
                        )
                        cau_tra_loi = response.text
                        break
                    except Exception as e:
                        danh_sach_loi.append(f"- **Lần {lan_thu + 1} ({ten_model})**: {e}")
                        time.sleep(thoi_gian_cho[lan_thu])
                        continue

                if not cau_tra_loi:
                    chi_tiet = "\n".join(danh_sach_loi)
                    cau_tra_loi = f"⚠️ Máy chủ Google đang cao điểm. Chi tiết các lần thử:\n{chi_tiet}"

                if ho_so_hien_tai_id:
                    luu_tin_nhan_cloud(ho_so_hien_tai_id, "assistant", cau_tra_loi)
                st.rerun()
