import io
import sqlite3
import time
from datetime import datetime
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()

DANH_SACH_MODEL = ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.8-flash"]
DB_FILE = "bao_tri_ai.db"

st.set_page_config(page_title="Hệ thống AI Bảo trì Tự chủ", page_icon="🏭", layout="wide")

import os

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
            # Lấy mật khẩu từ Streamlit Secrets hoặc file .env
            mat_khau_dung = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD", "123456"))
            if mat_khau_nhap == mat_khau_dung:
                st.session_state.da_dang_nhap = True
                st.rerun()
            else:
                st.error("❌ Mật khẩu không chính xác!")
    st.stop() # Chặn toàn bộ nội dung bên dưới nếu chưa đăng nhập


def khoi_tao_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS phien_lam_viec (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ten_phien TEXT NOT NULL,
            vai_tro TEXT,
            thoi_gian_tao TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS lich_su_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phien_id INTEGER,
            role TEXT,
            content TEXT,
            thoi_gian TEXT,
            FOREIGN KEY (phien_id) REFERENCES phien_lam_viec(id)
        )
    """)
    conn.commit()
    conn.close()

def tao_phien_moi(ten_phien, vai_tro):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    thoi_gian = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute(
        "INSERT INTO phien_lam_viec (ten_phien, vai_tro, thoi_gian_tao) VALUES (?, ?, ?)",
        (ten_phien, vai_tro, thoi_gian)
    )
    phien_id = c.lastrowid
    loi_chao = f"Đã khởi tạo hồ sơ **{ten_phien}** ở chế độ **{vai_tro}**. Hãy tải tài liệu PDF/Excel hoặc nhập triệu chứng thiết bị để bắt đầu."
    c.execute(
        "INSERT INTO lich_su_chat (phien_id, role, content, thoi_gian) VALUES (?, ?, ?, ?)",
        (phien_id, "assistant", loi_chao, thoi_gian)
    )
    conn.commit()
    conn.close()
    return phien_id

def lay_danh_sach_phien():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, ten_phien, vai_tro, thoi_gian_tao FROM phien_lam_viec ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def lay_tin_nhan_theo_phien(phien_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, role, content, thoi_gian FROM lich_su_chat WHERE phien_id = ? ORDER BY id ASC", (phien_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def luu_tin_nhan(phien_id, role, content):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    thoi_gian = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute(
        "INSERT INTO lich_su_chat (phien_id, role, content, thoi_gian) VALUES (?, ?, ?, ?)",
        (phien_id, role, content, thoi_gian)
    )
    conn.commit()
    conn.close()

def xoa_phien(phien_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM lich_su_chat WHERE phien_id = ?", (phien_id,))
    c.execute("DELETE FROM phien_lam_viec WHERE id = ?", (phien_id,))
    conn.commit()
    conn.close()

def doc_du_lieu_bang(uploaded_file):
    ten_file = uploaded_file.name
    noi_dung_text = [f"\n--- DỮ LIỆU TỪ FILE: {ten_file} ---"]
    try:
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

from pypdf import PdfReader

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

def tao_file_word_bieu_mau(ten_phien, vai_tro, danh_sach_tin_nhan, chi_mot_cau=None):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)

    p_header = doc.add_paragraph()
    p_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_header.add_run("BIÊN BẢN PHÂN TÍCH KỸ THUẬT & HƯỚNG DẪN BẢO TRÌ\n")
    run_title.bold = True
    run_title.font.size = Pt(14)
    run_title.font.color.rgb = RGBColor(0, 51, 102)

    run_sub = p_header.add_run("(Hệ thống Trợ lý AI Hỗ trợ Bảo trì Tự chủ - Autonomous Maintenance)")
    run_sub.italic = True
    run_sub.font.size = Pt(10)

    table = doc.add_table(rows=3, cols=2)
    table.style = "Table Grid"
    cells_data = [
        ("Hạng mục / Tên hồ sơ:", str(ten_phien)),
        ("Chuyên môn áp dụng:", str(vai_tro)),
        ("Ngày giờ xuất biên bản:", datetime.now().strftime("%d/%m/%Y - %H:%M"))
    ]
    for idx, (nhan, gia_tri) in enumerate(cells_data):
        c_trai, c_phai = table.rows[idx].cells
        c_trai.text = nhan
        for p in c_trai.paragraphs:
            for r in p.runs:
                r.bold = True
        c_phai.text = gia_tri

    doc.add_paragraph()

    if chi_mot_cau:
        p = doc.add_paragraph()
        r = p.add_run("NỘI DUNG PHÂN TÍCH & ĐỀ XUẤT XỬ LÝ:")
        r.bold = True
        r.font.color.rgb = RGBColor(0, 51, 102)
        for line in chi_mot_cau.split("\n"):
            clean_line = line.replace("**", "").replace("### ", "").replace("## ", "").replace("# ", "")
            doc.add_paragraph(clean_line)
    else:
        for _, role, content, thoi_gian in danh_sach_tin_nhan:
            p_role = doc.add_paragraph()
            nguoi_gui = f"KỸ SƯ / VẬN HÀNH ({thoi_gian}):" if role == "user" else f"TRỢ LÝ KỸ THUẬT AI ({thoi_gian}):"
            r_role = p_role.add_run(nguoi_gui)
            r_role.bold = True
            r_role.font.color.rgb = RGBColor(153, 0, 0) if role == "user" else RGBColor(0, 102, 51)
            for line in content.split("\n"):
                clean_line = line.replace("**", "").replace("### ", "").replace("## ", "").replace("# ", "")
                doc.add_paragraph(clean_line)
            doc.add_paragraph("_" * 60)

    doc.add_paragraph()
    sig_table = doc.add_table(rows=1, cols=2)
    o_trai, o_phai = sig_table.rows[0].cells
    o_trai.text = "NGƯỜI LẬP BIÊN BẢN\n(Ký và ghi rõ họ tên)"
    o_phai.text = "XÁC NHẬN TRƯỞNG CA / QUẢN ĐỐC\n(Ký và ghi rõ họ tên)"
    for cell in (o_trai, o_phai):
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

khoi_tao_db()

ds_phien = lay_danh_sach_phien()
if not ds_phien:
    tao_phien_moi("Hồ sơ Bảo trì Chung", "Bảo trì Tự chủ (CIL & Phát hiện bất thường)")
    ds_phien = lay_danh_sach_phien()

if "phien_hien_tai" not in st.session_state:
    st.session_state.phien_hien_tai = ds_phien[0][0]

with st.sidebar:
    st.header("🏭 Quản lý Hồ sơ Bảo trì")
    
    with st.expander("➕ Tạo hồ sơ sự cố / thiết bị mới", expanded=False):
        ten_phien_moi = st.text_input("Tên thiết bị / Sự cố:", placeholder="VD: Biến tần lô ép 75kW - Lỗi quá dòng")
        vai_tro_moi = st.selectbox(
            "Chuyên môn chính:",
            [
                "Bảo trì Tự chủ (CIL & Phát hiện bất thường)",
                "Kỹ sư Bảo trì & Chẩn đoán lỗi",
                "Chuyên gia Lập trình PLC / SCADA",
                "Phân tích Nhật ký Bảo trì & Số liệu",
                "Tra cứu Tài liệu Kỹ thuật (Manual)"
            ],
            key="select_vai_tro_moi"
        )
        if st.button("Tạo hồ sơ mới", use_container_width=True):
            if ten_phien_moi.strip():
                id_moi = tao_phien_moi(ten_phien_moi.strip(), vai_tro_moi)
                st.session_state.phien_hien_tai = id_moi
                st.rerun()
            else:
                st.warning("Vui lòng nhập tên thiết bị hoặc sự cố.")

    map_phien = {}
    for p_id, p_ten, p_vaitro, p_ngay in ds_phien:
        nhan = f"#{p_id} - {p_ten} ({p_ngay})"
        map_phien[nhan] = (p_id, p_ten, p_vaitro)
        
    danh_sach_nhan = list(map_phien.keys())
    index_mac_dinh = 0
    for i, (p_id, _, _, _) in enumerate(ds_phien):
        if p_id == st.session_state.phien_hien_tai:
            index_mac_dinh = i
            break

    nhan_duoc_chon = st.selectbox("📂 Hồ sơ đang mở (SQLite):", danh_sach_nhan, index=index_mac_dinh)
    id_hien_tai, ten_phien_hien_tai, vai_tro_hien_tai = map_phien[nhan_duoc_chon]
    st.session_state.phien_hien_tai = id_hien_tai

    st.divider()

    prompts_map = {
        "Bảo trì Tự chủ (CIL & Phát hiện bất thường)": "Bạn là chuyên gia triển khai Bảo trì Tự chủ (Autonomous Maintenance - TPM) trong nhà máy công nghiệp. Hãy hỗ trợ lập tiêu chuẩn Vệ sinh - Kiểm tra - Bôi trơn (CIL), nhận diện điểm bất thường (Fuguai) và hướng dẫn kiểm tra an toàn cho vận hành viên.",
        "Kỹ sư Bảo trì & Chẩn đoán lỗi": "Bạn là kỹ sư trưởng bảo trì điện và tự động hóa nhà máy. Hãy phân tích nguyên nhân gốc rễ, đưa ra các bước kiểm tra an toàn, thông số đo đạc thực tế và phương án khắc phục sự cố ngắn gọn, chính xác.",
        "Chuyên gia Lập trình PLC / SCADA": "Bạn là chuyên gia lập trình tự động hóa (Siemens PLC, Structured Text SCL, Ladder, SCADA, IoT). Hãy viết code tối ưu, có chú thích rõ ràng và hướng dẫn cấu hình truyền thông chuẩn xác.",
        "Phân tích Nhật ký Bảo trì & Số liệu": "Bạn là chuyên gia phân tích dữ liệu bảo trì dự đoán. Từ dữ liệu Excel/CSV cung cấp, hãy thống kê tần suất lỗi, chỉ ra thiết bị có nguy cơ hư hỏng cao và đề xuất kế hoạch bảo trì phòng ngừa."
    }
    system_prompt = prompts_map.get(vai_tro_hien_tai, "Bạn là trợ lý kỹ thuật chuyên đọc hiểu và trích xuất thông số từ nhiều tài liệu Manual PDF. Luôn ghi rõ tên tài liệu và mục liên quan.")

    st.subheader("📎 Nạp Tài liệu & Nhật ký")
    uploaded_files = st.file_uploader(
        "Chọn nhiều file PDF, Excel (.xlsx) hoặc CSV:",
        type=["pdf", "xlsx", "xls", "csv"],
        accept_multiple_files=True
    )
    if uploaded_files:
        st.success(f"Đang đính kèm {len(uploaded_files)} file:")
        for f in uploaded_files:
            st.caption(f"• {f.name}")

    st.divider()

    st.subheader("📥 Xuất Biên Bản & Quản Lý")
    tin_nhan_hien_tai = lay_tin_nhan_theo_phien(st.session_state.phien_hien_tai)
    
    if len(tin_nhan_hien_tai) > 1:
        word_buffer = tao_file_word_bieu_mau(ten_phien_hien_tai, vai_tro_hien_tai, tin_nhan_hien_tai)
        st.download_button(
            label="📘 Xuất toàn bộ hồ sơ ra Word (.docx)",
            data=word_buffer,
            file_name=f"Bien_ban_bao_tri_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )

    if len(ds_phien) > 1:
        if st.button("🗑️ Xóa hồ sơ đang mở", use_container_width=True):
            xoa_phien(st.session_state.phien_hien_tai)
            del st.session_state.phien_hien_tai
            st.rerun()

st.title(f"⚙️ {ten_phien_hien_tai}")
st.caption(f"Chế độ: **{vai_tro_hien_tai}** | Dữ liệu tự động lưu vào SQLite (`{DB_FILE}`)")

import requests
from modules.tab_giam_sat import hien_thi_tab_giam_sat
from modules.tab_bao_cao import hien_thi_tab_bao_cao

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
        "Cache-Control": "no-cache"
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
    "📊 3. Thống Kê & Báo Cáo Excel"
])

with tab_giam_sat:
    hien_thi_tab_giam_sat(df_plc, loi_ket_noi_plc, luu_tin_nhan)

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
                file_chon.seek(0) # Đưa con trỏ đọc file về đầu
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
                st.warning(f"Không thể vẽ biểu đồ từ cột đã chọn (hãy chọn cột chứa số liệu cho biểu đồ đường): {e}")

for idx, (msg_id, role, content, thoi_gian) in enumerate(tin_nhan_hien_tai):
    with st.chat_message(role):
        st.markdown(content)
        if role == "assistant" and idx > 0:
            single_word = tao_file_word_bieu_mau(ten_phien_hien_tai, vai_tro_hien_tai, [], chi_mot_cau=content)
            st.download_button(
                label="📄 Xuất phương án này ra biểu mẫu Word (.docx)",
                data=single_word,
                file_name=f"Phuong_an_xu_ly_{msg_id}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"word_btn_{msg_id}"
            )

prompt_tu_plc = st.session_state.pop("tu_dong_hoi_plc", None)
prompt_nhap_tay = st.chat_input("Nhập yêu cầu (VD: Lập bảng kiểm tra CIL hằng ngày cho cụm lô ép, hoặc phân tích lỗi từ file đính kèm)...")

if prompt := (prompt_tu_plc or prompt_nhap_tay):
    if not prompt_tu_plc:
        luu_tin_nhan(st.session_state.phien_hien_tai, "user", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Đang phân tích dữ liệu kỹ thuật và lưu vào cơ sở dữ liệu..."):
            noi_dung_gui = []
            du_lieu_tai_lieu_gop = []

            if uploaded_files:
                for file in uploaded_files:
                    if file.name.lower().endswith(".pdf"):
                        du_lieu_tai_lieu_gop.append(doc_noi_dung_pdf(file))
                    elif file.name.lower().endswith((".xlsx", ".xls", ".csv")):
                        du_lieu_tai_lieu_gop.append(doc_du_lieu_bang(file))

            ngu_canh_cu = "\n".join([f"{r}: {c}" for _, r, c, _ in tin_nhan_hien_tai[-6:]])
            cau_hoi_day_du = f"Lịch sử trao đổi gần đây:\n{ngu_canh_cu}\n\n"
            if du_lieu_tai_lieu_gop:
                cau_hoi_day_du += "Tài liệu kỹ thuật & Số liệu đính kèm:\n" + "\n".join(du_lieu_tai_lieu_gop) + "\n\n"
            cau_hoi_day_du += f"Yêu cầu hiện tại: {prompt}"

            noi_dung_gui.append(cau_hoi_day_du)

            cau_tra_loi = ""
            danh_sach_loi = []
            thoi_gian_cho = [3, 6, 10, 15]
            
            for lan_thu, ten_model in enumerate(DANH_SACH_MODEL):
                try:
                    response = client.models.generate_content(
                        model=ten_model,
                        contents=noi_dung_gui,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.2,
                        )
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





            luu_tin_nhan(st.session_state.phien_hien_tai, "assistant", cau_tra_loi)
            st.rerun()
