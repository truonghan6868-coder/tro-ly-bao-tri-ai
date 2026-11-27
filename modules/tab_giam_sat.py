

import os
from datetime import datetime
import altair as alt
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from modules.tab_ban_giao import hien_thi_so_ban_giao_ca

@st.cache_data(ttl=10, show_spinner=False)
def tai_toan_bo_cau_hinh():
    """Tải danh sách toàn bộ các điểm đo / biến tần từ Supabase."""
    mac_dinh = [{
        "vi_tri_may": "Cụm Lô ép (Press Roll - 75kW)",
        "loai_thiet_bi": "Cum_May_Chung",
        "db_number": 3,
        "byte_offset": 0,
        "nguong_temp1": 80.0,
        "nguong_temp2": 80.0,
        "nguong_current": 65.0,
        "dong_dinh_muc": 135.0,
        "nguong_press_min": 3.5,
        "kich_hoat": True,
        "nguoi_cap_nhat": "Mặc định",
        "thoi_gian_cap_nhat": ""
    }]
    try:
        url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
        key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
        endpoint = f"{url_du_an}/rest/v1/cau_hinh_nguong?select=*&order=db_number.asc,byte_offset.asc"
        headers = {
            "apikey": key_du_an,
            "Authorization": f"Bearer {key_du_an}",
            "Cache-Control": "no-cache"
        }
        res = requests.get(endpoint, headers=headers, timeout=8)
        res.raise_for_status()
        du_lieu = res.json()
        if du_lieu:
            return du_lieu
    except Exception:
        pass
    return mac_dinh


def luu_bang_cau_hinh_da_diem(df_da_sua, nguoi_sua):
    """Lưu đồng loạt toàn bộ thay đổi từ st.data_editor lên Supabase."""
    url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    endpoint = f"{url_du_an}/rest/v1/cau_hinh_nguong"
    headers = {
        "apikey": key_du_an,
        "Authorization": f"Bearer {key_du_an}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    thoi_gian_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    danh_sach_gui = []

    for _, row in df_da_sua.iterrows():
        ten_vi_tri = str(row.get("vi_tri_may", "")).strip()
        if not ten_vi_tri or ten_vi_tri == "None":
            continue
        danh_sach_gui.append({
            "vi_tri_may": ten_vi_tri,
            "loai_thiet_bi": str(row.get("loai_thiet_bi", "Cum_May_Chung")),
            "db_number": int(row.get("db_number", 3) or 3),
            "byte_offset": int(row.get("byte_offset", 0) or 0),
            "nguong_temp1": float(row.get("nguong_temp1", 80.0) or 80.0),
            "nguong_temp2": float(row.get("nguong_temp2", 80.0) or 80.0),
            "nguong_current": float(row.get("nguong_current", 65.0) or 65.0),
            "dong_dinh_muc": float(row.get("dong_dinh_muc", 135.0) or 135.0),
            "nguong_press_min": float(row.get("nguong_press_min", 3.5) or 3.5),
            "kich_hoat": bool(row.get("kich_hoat", True)),
            "nguoi_cap_nhat": nguoi_sua,
            "thoi_gian_cap_nhat": thoi_gian_now
        })

    if danh_sach_gui:
        res = requests.post(endpoint, json=danh_sach_gui, headers=headers, timeout=12)
        res.raise_for_status()

@st.cache_data(ttl=5, show_spinner=False)
def tai_du_lieu_theo_vi_tri(vi_tri_may, limit=50):

    """Lấy dữ liệu đo mới nhất của riêng vị trí máy đang chọn."""
    try:
        url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
        key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
        endpoint = f"{url_du_an}/rest/v1/du_lieu_plc_db3"
        headers = {
            "apikey": key_du_an,
            "Authorization": f"Bearer {key_du_an}",
            "Cache-Control": "no-cache"
        }
        params = {
            "vi_tri_may": f"eq.{vi_tri_may}",
            "select": "*",
            "order": "id.desc",
            "limit": str(limit)
        }
        res = requests.get(endpoint, headers=headers, params=params, timeout=8)
        res.raise_for_status()
        du_lieu = res.json()
        if du_lieu:
            return pd.DataFrame(du_lieu)
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=15, show_spinner=False)
def tai_su_kien_ket_noi(limit=15):
    """Lấy các sự kiện mất kết nối / phục hồi PLC gần nhất từ Supabase."""
    try:
        url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
        key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
        endpoint = f"{url_du_an}/rest/v1/su_kien_ket_noi_plc"
        headers = {
            "apikey": key_du_an,
            "Authorization": f"Bearer {key_du_an}",
            "Cache-Control": "no-cache"
        }
        params = {"select": "*", "order": "id.desc", "limit": str(limit)}
        res = requests.get(endpoint, headers=headers, params=params, timeout=8)
        res.raise_for_status()
        return pd.DataFrame(res.json())
    except Exception:
        return pd.DataFrame()


def hien_thi_su_kien_ket_noi():
    """Khối hiển thị lịch sử mất kết nối / phục hồi PLC do plc_logger.py đẩy lên."""
    df_su_kien = tai_su_kien_ket_noi()
    with st.expander("🔌 Lịch sử kết nối PLC (mất kết nối / phục hồi)", expanded=False):
        if df_su_kien.empty:
            st.caption("Chưa có sự kiện kết nối nào được ghi nhận.")
            return

        df_hien_thi = df_su_kien.copy()
        if "su_kien" in df_hien_thi.columns:
            nhan_su_kien = {"MAT_KET_NOI": "🔴 Mất kết nối", "KHOI_PHUC": "🟢 Phục hồi"}
            df_hien_thi["su_kien"] = df_hien_thi["su_kien"].map(
                lambda gia_tri: nhan_su_kien.get(gia_tri, gia_tri)
            )
        st.dataframe(df_hien_thi, use_container_width=True, hide_index=True)


def hien_thi_tab_giam_sat(df_plc_chung, loi_ket_noi_plc, ham_luu_tin_nhan):
    gio_hien_tai = datetime.now().hour
    ca_mac_dinh = 0 if 7 <= gio_hien_tai < 19 else 1
    danh_sach_ca = [
        "☀️ Ca Ngày (07:00 - 19:00)",
        "🌙 Ca Đêm (19:00 - 07:00)"
    ]

    # Thanh điều khiển làm mới
    c_ref1, c_ref2, _ = st.columns([1.3, 1.2, 2])
    with c_ref1:
        tu_dong_cap_nhat = st.toggle("⚡ Tự động cập nhật (5s)", value=True)
    with c_ref2:
        if st.button("🔄 Làm mới ngay", use_container_width=True):
            st.rerun()

    if tu_dong_cap_nhat and not st.session_state.get("tu_dong_hoi_plc"):
        st_autorefresh(interval=5000, key="plc_realtime_refresh")

    # Tải danh sách động toàn bộ vị trí máy từ Supabase
    danh_sach_cau_hinh = tai_toan_bo_cau_hinh()
    df_cau_hinh = pd.DataFrame(danh_sach_cau_hinh)
    danh_sach_ten_may = df_cau_hinh["vi_tri_may"].tolist()

    # Thanh chọn Bối cảnh vận hành thực tế
    with st.container(border=True):
        st.markdown("**🏭 Bối cảnh vận hành hiện trường (Tự động tải danh sách từ Cloud):**")
        bc1, bc2, bc3, bc4 = st.columns(4)
        with bc1:
            ca_truc = st.selectbox("🕒 Ca làm việc", danh_sach_ca, index=ca_mac_dinh)
        with bc2:
            vi_tri_may = st.selectbox("⚙️ Cụm / Vị trí máy", danh_sach_ten_may)
        with bc3:
            trang_thai_may = st.selectbox("🚦 Trạng thái chạy", [
                "Đang chạy sản xuất",
                "Chạy không tải / Chạy thử",
                "Đang lên tốc độ",
                "Đang dừng bảo trì"
            ])
        with bc4:
            dinh_luong_giay = st.text_input("📄 Định lượng giấy (GSM)", value="125 GSM (OCC)")

    # Lấy cấu hình của vị trí đang chọn
    dong_cau_hinh = df_cau_hinh[df_cau_hinh["vi_tri_may"] == vi_tri_may].to_dict(orient="records").pop(0)
    NG_T1 = float(dong_cau_hinh.get("nguong_temp1", 80.0))
    NG_T2 = float(dong_cau_hinh.get("nguong_temp2", 80.0))
    NG_CUR = float(dong_cau_hinh.get("nguong_current", 65.0))
    DONG_DINH_MUC = float(dong_cau_hinh.get("dong_dinh_muc", 135.0))
    NG_PRESS_MIN = float(dong_cau_hinh.get("nguong_press_min", 3.5))

    # BẢNG QUẢN LÝ ĐA ĐIỂM (st.data_editor) - Thêm/Sửa hàng loạt 10 vị trí & 28 biến tần ACS880
    with st.expander(f"⚙️ Quản lý & Cài đặt ngưỡng đa điểm ({len(df_cau_hinh)} vị trí đã khai báo)", expanded=False):
        st.caption("💡 Bấm trực tiếp vào ô để sửa ngưỡng, hoặc kéo xuống cuối bảng bấm dấu **(+)** để thêm vị trí máy / biến tần ABB ACS880 mới.")

        cac_cot_hien_thi = [
            "vi_tri_may", "loai_thiet_bi", "db_number", "byte_offset",
            "nguong_temp1", "nguong_temp2", "nguong_current", "dong_dinh_muc",
            "nguong_press_min", "kich_hoat"
        ]
        for col in cac_cot_hien_thi:
            if col not in df_cau_hinh.columns:
                df_cau_hinh[col] = None

        df_editor = st.data_editor(
            df_cau_hinh[cac_cot_hien_thi],
            num_rows="dynamic",
            use_container_width=True,
            key="editor_cau_hinh_da_diem",
            column_config={
                "vi_tri_may": st.column_config.TextColumn("Tên Vị Trí / Biến Tần", width="medium", required=True),
                "loai_thiet_bi": st.column_config.SelectboxColumn(
                    "Loại Thiết Bị",
                    options=["Cum_May_Chung", "ABB_ACS880"],
                    default="Cum_May_Chung"
                ),
                "db_number": st.column_config.NumberColumn("DB Số", min_value=1, max_value=999, step=1, default=3),
                "byte_offset": st.column_config.NumberColumn("Offset (Byte)", min_value=0, max_value=4000, step=2, default=0),
                "nguong_temp1": st.column_config.NumberColumn("Max T1 (°C)", min_value=10.0, max_value=250.0, step=1.0, default=80.0),
                "nguong_temp2": st.column_config.NumberColumn("Max T2 (°C)", min_value=10.0, max_value=250.0, step=1.0, default=80.0),
                "nguong_current": st.column_config.NumberColumn("Max Dòng (A)", min_value=1.0, max_value=1000.0, step=1.0, default=65.0),
                "dong_dinh_muc": st.column_config.NumberColumn("Định mức (A)", min_value=1.0, max_value=1000.0, step=5.0, default=135.0),
                "nguong_press_min": st.column_config.NumberColumn("Min Áp suất", min_value=0.0, max_value=100.0, step=0.5, default=3.5),
                "kich_hoat": st.column_config.CheckboxColumn("Giám sát", default=True)
            }
        )

        u1, u2 = st.columns(2)
        with u1:
            nguoi_sua_bang = st.text_input("👷 Tên kỹ sư / người cập nhật bảng", placeholder="VD: Kỹ thuật Điện - TĐH")
        with u2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("💾 Lưu toàn bộ bảng cấu hình đa điểm lên Cloud", type="primary", use_container_width=True):
                if not nguoi_sua_bang.strip():
                    st.warning("⚠️ Vui lòng nhập tên người cập nhật trước khi lưu!")
                else:

                    try:
                        luu_bang_cau_hinh_da_diem(df_editor, nguoi_sua_bang.strip())
                        st.cache_data.clear()
                        st.success("✅ Đã cập nhật toàn bộ danh sách vị trí & ngưỡng lên Supabase Cloud!")
                        st.rerun()
                    except Exception as e_bulk:
                        st.error(f"Lỗi khi lưu bảng cấu hình: {e_bulk}")

    # Lọc dữ liệu đo của đúng vị trí đang chọn (nếu chưa có dữ liệu riêng thì dùng dữ liệu chung)
    df_plc = tai_du_lieu_theo_vi_tri(vi_tri_may, limit=50)
    if df_plc.empty:
        df_plc = df_plc_chung

    if not df_plc.empty:
        moi_nhat = df_plc.to_dict(orient="records").pop(0)

        t1_val = float(moi_nhat.get('temp1', 0))
        t2_val = float(moi_nhat.get('temp2', 0))
        sp_val = float(moi_nhat.get('speed', 0))
        pr_val = float(moi_nhat.get('pressure', 0))

        cur_val = float(moi_nhat.get('motor_current', 0))
        phan_tram_tai = (cur_val / DONG_DINH_MUC) * 100 if DONG_DINH_MUC > 0 else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric(
            "🌡️ Nhiệt độ 1", f"{t1_val:.1f} °C",
            delta=f"Vượt +{t1_val - NG_T1:.1f}°C" if t1_val > NG_T1 else f"An toàn (Max {NG_T1}°C)",
            delta_color="inverse" if t1_val > NG_T1 else "normal"
        )
        m2.metric(
            "🌡️ Nhiệt độ 2", f"{t2_val:.1f} °C",
            delta=f"Vượt +{t2_val - NG_T2:.1f}°C" if t2_val > NG_T2 else f"An toàn (Max {NG_T2}°C)",
            delta_color="inverse" if t2_val > NG_T2 else "normal"
        )
        m3.metric(
            "⚡ Tốc độ", f"{sp_val:.1f}",
            delta="Đang chạy" if sp_val > 50 else "Dừng / Chậm",
            delta_color="normal" if sp_val > 50 else "off"
        )
        m4.metric(
            "⏲️ Áp suất", f"{pr_val:.2f}",
            delta=f"Thấp (<{NG_PRESS_MIN})" if pr_val < NG_PRESS_MIN else f"Đạt (>={NG_PRESS_MIN})",
            delta_color="inverse" if pr_val < NG_PRESS_MIN else "normal"
        )
        m5.metric(
            "🔌 Dòng động cơ", f"{cur_val:.2f} A ({phan_tram_tai:.0f}%)",
            delta=f"Quá tải +{cur_val - NG_CUR:.1f}A" if cur_val > NG_CUR else f"Ổn định (Max {NG_CUR}A)",
            delta_color="inverse" if cur_val > NG_CUR else "normal"
        )

        # Hiển thị thêm 3 đồng hồ Biến tần ABB ACS880 nếu vị trí này được khai báo là ABB_ACS880
        if dong_cau_hinh.get("loai_thiet_bi") == "ABB_ACS880":
            hz_val = float(moi_nhat.get('tan_so_hz', 0) or 0)
            tq_val = float(moi_nhat.get('momen_xoan', 0) or 0)
            err_code = int(moi_nhat.get('ma_loi_acs880', 0) or 0)

            b1, b2, b3 = st.columns(3)
            b1.metric("〰️ Tần số thực tế (ACS880)", f"{hz_val:.2f} Hz")
            b2.metric("🔄 Mô-men xoắn (Torque)", f"{tq_val:.1f} %")
            b3.metric(
                "🚨 Mã lỗi Biến tần (Fault Code)",
                f"0x{err_code:04X} ({err_code})" if err_code > 0 else "0 (Không lỗi)",
                delta="ĐANG BÁO LỖI BIẾN TẦN" if err_code > 0 else "Hoạt động bình thường",
                delta_color="inverse" if err_code > 0 else "normal"
            )

        st.divider()

        df_bieu_do = df_plc.head(30).iloc[::-1].copy()

        def ve_bieu_do_chuan(df, danh_sach_cot, don_vi, min_y, max_y, bang_mau):
            df_melt = df.melt(id_vars=["thoi_gian"], value_vars=danh_sach_cot, var_name="Thong_so", value_name="Gia_tri")
            return (
                alt.Chart(df_melt)
                .mark_line(point=True, strokeWidth=2.5)
                .encode(
                    x=alt.X("thoi_gian:N", title="Thời gian", axis=alt.Axis(labelAngle=-45, labelLimit=80)),
                    y=alt.Y("Gia_tri:Q", title=don_vi, scale=alt.Scale(domain=[min_y, max_y])),
                    color=alt.Color("Thong_so:N", title="Thông số", scale=alt.Scale(range=bang_mau)),
                    tooltip=["thoi_gian", "Thong_so", "Gia_tri"]
                )
                .properties(height=220)
            )

        r1_c1, r1_c2 = st.columns(2)
        with r1_c1:
            st.markdown("**🌡️ Biểu đồ Nhiệt độ (°C)**")
            st.altair_chart(ve_bieu_do_chuan(df_bieu_do, ["temp1", "temp2"], "Nhiệt độ (°C)", 0, 150, ["#FF4B4B", "#FFA500"]), use_container_width=True)
        with r1_c2:
            st.markdown("**🔌 Biểu đồ Dòng điện Động cơ (A)**")
            st.altair_chart(ve_bieu_do_chuan(df_bieu_do, ["motor_current"], "Dòng điện (A)", 0, 200, ["#00CC96"]), use_container_width=True)

        r2_c1, r2_c2 = st.columns(2)
        with r2_c1:
            st.markdown("**⚡ Biểu đồ Tốc độ**")
            st.altair_chart(ve_bieu_do_chuan(df_bieu_do, ["speed"], "Tốc độ", 0, 3000, ["#636EFA"]), use_container_width=True)
        with r2_c2:
            st.markdown("**⏲️ Biểu đồ Áp suất**")
            st.altair_chart(ve_bieu_do_chuan(df_bieu_do, ["pressure"], "Áp suất", 0, 15, ["#AB63FA"]), use_container_width=True)

        if st.button("🤖 Gửi số liệu & Bối cảnh này sang Tab 2 để AI chẩn đoán", type="primary", use_container_width=True):
            du_lieu_tom_tat = df_plc.head(10).to_string(index=False)
            cau_hoi_plc = (
                f"THÔNG TIN BỐI CẢNH VẬN HÀNH HIỆN TRƯỜNG:\n"
                f"- Ca làm việc: {ca_truc}\n"
                f"- Cụm / Vị trí máy: {vi_tri_may} (Loại: {dong_cau_hinh.get('loai_thiet_bi')})\n"
                f"- Ngưỡng cảnh báo: Temp1 <= {NG_T1}°C, Temp2 <= {NG_T2}°C, Dòng <= {NG_CUR}A (Định mức {DONG_DINH_MUC}A)\n"
                f"- Trạng thái vận hành: {trang_thai_may} | Sản phẩm: {dinh_luong_giay}\n\n"
                f"10 MẪU THÔNG SỐ ĐO TỪ PLC SIEMENS:\n{du_lieu_tom_tat}\n\n"
                "Hãy đánh giá tình trạng thiết bị, giải thích ý nghĩa mã lỗi biến tần ABB ACS880 (nếu ma_loi_acs880 > 0) "
                "và đề xuất quy trình kiểm tra bảo trì tự chủ cụ thể."
            )
            ham_luu_tin_nhan(st.session_state.phien_hien_tai, "user", f"🔍 Yêu cầu AI phân tích vận hành ({vi_tri_may} - {ca_truc}).")
            st.session_state.tu_dong_hoi_plc = cau_hoi_plc
            st.rerun()
    else:
        st.warning(f"Đang chờ dữ liệu từ Supabase Cloud... ({loi_ket_noi_plc})")

    st.divider()
    hien_thi_su_kien_ket_noi()
    hien_thi_so_ban_giao_ca()
