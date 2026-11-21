import os
from datetime import datetime
import altair as alt
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from modules.tab_ban_giao import hien_thi_so_ban_giao_ca


def lay_cau_hinh_nguong(vi_tri_may):
    """Tải cấu hình ngưỡng riêng của từng vị trí máy từ Supabase."""
    mac_dinh = {
        "nguong_temp1": 80.0,
        "nguong_temp2": 80.0,
        "nguong_current": 65.0,
        "dong_dinh_muc": 135.0,
        "nguong_press_min": 3.5,
        "nguoi_cap_nhat": "Mặc định",
        "thoi_gian_cap_nhat": ""
    }
    try:
        url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
        key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
        endpoint = f"{url_du_an}/rest/v1/cau_hinh_nguong"
        headers = {
            "apikey": key_du_an,
            "Authorization": f"Bearer {key_du_an}",
            "Cache-Control": "no-cache"
        }
        params = {"vi_tri_may": f"eq.{vi_tri_may}", "select": "*"}
        res = requests.get(endpoint, headers=headers, params=params, timeout=8)
        res.raise_for_status()
        du_lieu = res.json()
        if du_lieu:
             return du_lieu.pop(0)
    except Exception:
        pass
    return mac_dinh


def luu_cau_hinh_nguong(vi_tri_may, t1, t2, cur, dinh_muc, press_min, nguoi_sua):
    """Cập nhật ngưỡng mới lên Supabase Cloud."""
    url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    endpoint = f"{url_du_an}/rest/v1/cau_hinh_nguong"
    headers = {
        "apikey": key_du_an,
        "Authorization": f"Bearer {key_du_an}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    payload = {
        "vi_tri_may": vi_tri_may,
        "nguong_temp1": float(t1),
        "nguong_temp2": float(t2),
        "nguong_current": float(cur),
        "dong_dinh_muc": float(dinh_muc),
        "nguong_press_min": float(press_min),
        "nguoi_cap_nhat": nguoi_sua,
        "thoi_gian_cap_nhat": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
    res.raise_for_status()


def hien_thi_tab_giam_sat(df_plc, loi_ket_noi_plc, ham_luu_tin_nhan):
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

    # Thanh chọn Bối cảnh vận hành thực tế
    with st.container(border=True):
        st.markdown("**🏭 Bối cảnh vận hành hiện trường (Gửi kèm khi nhờ AI phân tích):**")
        bc1, bc2, bc3, bc4 = st.columns(4)
        with bc1:
            ca_truc = st.selectbox("🕒 Ca làm việc", danh_sach_ca, index=ca_mac_dinh)
        with bc2:
            vi_tri_may = st.selectbox("⚙️ Cụm / Vị trí máy", [
                "Cụm Lô ép (Press Roll - 75kW)",
                "Khu vực Sấy (Dryer)",
                "Hệ thống Bơm chân không",
                "Đo nồng độ bột (OC) / Bể khuấy"
            ])
        with bc3:
            trang_thai_may = st.selectbox("🚦 Trạng thái chạy", [
                "Đang chạy sản xuất",
                "Chạy không tải / Chạy thử",
                "Đang lên tốc độ",
                "Đang dừng bảo trì"
            ])
        with bc4:
            dinh_luong_giay = st.text_input("📄 Định lượng giấy (GSM)", value="125 GSM (OCC)")

    # Tải bộ ngưỡng động tương ứng với vị trí máy đang chọn
    cau_hinh = lay_cau_hinh_nguong(vi_tri_may)
    NG_T1 = float(cau_hinh.get("nguong_temp1", 80.0))
    NG_T2 = float(cau_hinh.get("nguong_temp2", 80.0))
    NG_CUR = float(cau_hinh.get("nguong_current", 65.0))
    DONG_DINH_MUC = float(cau_hinh.get("dong_dinh_muc", 135.0))
    NG_PRESS_MIN = float(cau_hinh.get("nguong_press_min", 3.5))

    # Ngăn cài đặt / điều chỉnh ngưỡng trực tiếp cho người vận hành
    with st.expander(f"⚙️ Cài đặt ngưỡng cảnh báo riêng cho: {vi_tri_may}", expanded=False):
        if cau_hinh.get("thoi_gian_cap_nhat"):
            st.caption(f"Cập nhật lần cuối bởi **{cau_hinh.get('nguoi_cap_nhat')}** lúc `{cau_hinh.get('thoi_gian_cap_nhat')}`")

        with st.form("form_cai_dat_nguong"):
            n1, n2, n3, n4, n5 = st.columns(5)
            with n1:
                in_t1 = st.number_input("🌡️ Ngưỡng Temp 1 (°C)", min_value=10.0, max_value=250.0, value=NG_T1, step=1.0)
            with n2:
                in_t2 = st.number_input("🌡️ Ngưỡng Temp 2 (°C)", min_value=10.0, max_value=250.0, value=NG_T2, step=1.0)
            with n3:
                in_cur = st.number_input("🔌 Ngưỡng Dòng báo (A)", min_value=5.0, max_value=500.0, value=NG_CUR, step=1.0)
            with n4:
                in_dm = st.number_input("⚡ Dòng định mức (A)", min_value=10.0, max_value=600.0, value=DONG_DINH_MUC, step=5.0)
            with n5:
                in_pr = st.number_input("⏲️ Áp suất tối thiểu", min_value=0.0, max_value=50.0, value=NG_PRESS_MIN, step=0.5)

            u1, u2 = st.columns(2)
            with u1:
                nguoi_sua = st.text_input("👷 Tên người điều chỉnh", placeholder="VD: Tổ trưởng Ca Ngày")
            with u2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                nut_luu_nguong = st.form_submit_button("💾 Lưu ngưỡng lên Cloud", type="primary", use_container_width=True)

            if nut_luu_nguong:
                if not nguoi_sua.strip():
                    st.warning("⚠️ Vui lòng nhập tên người điều chỉnh để lưu lịch sử!")
                else:
                    try:
                        luu_cau_hinh_nguong(vi_tri_may, in_t1, in_t2, in_cur, in_dm, in_pr, nguoi_sua.strip())
                        st.success(f"✅ Đã lưu ngưỡng mới cho '{vi_tri_may}'! Hệ thống cảnh báo sẽ tự đồng bộ sau vài giây.")
                        st.rerun()
                    except Exception as e_save:
                        st.error(f"Lỗi khi lưu ngưỡng: {e_save}")

    if not df_plc.empty:
        moi_nhat = df_plc.to_dict(orient="records").pop(0)

        t1_val = float(moi_nhat['temp1'])
        t2_val = float(moi_nhat['temp2'])
        sp_val = float(moi_nhat['speed'])
        pr_val = float(moi_nhat['pressure'])
        cur_val = float(moi_nhat['motor_current'])
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

                    # Nút gửi dữ liệu kèm bối cảnh sang Tab 2 cho AI phân tích
        if st.button("🤖 Gửi số liệu & Bối cảnh này sang Tab 2 để AI chẩn đoán", type="primary", use_container_width=True):
            du_lieu_tom_tat = df_plc.head(10).to_string(index=False)
            cau_hoi_plc = (
                f"THÔNG TIN BỐI CẢNH VẬN HÀNH HIỆN TRƯỜNG:\n"
                f"- Ca làm việc: {ca_truc}\n"
                f"- Cụm / Vị trí máy: {vi_tri_may}\n"
                f"- Ngưỡng cảnh báo đang cài đặt: Temp1 <= {NG_T1}°C, Temp2 <= {NG_T2}°C, Dòng <= {NG_CUR}A (Định mức {DONG_DINH_MUC}A), Áp suất >= {NG_PRESS_MIN}\n"
                f"- Trạng thái vận hành: {trang_thai_may}\n"
                f"- Sản phẩm đang chạy: {dinh_luong_giay}\n\n"
                f"10 MẪU THÔNG SỐ ĐO TỪ PLC SIEMENS (DB3):\n{du_lieu_tom_tat}\n\n"
                "Dựa trên bối cảnh vận hành, bộ ngưỡng cài đặt riêng của cụm máy và chuỗi số liệu PLC trên, hãy đánh giá tình trạng thiết bị, "
                "phân tích nguyên nhân nếu có bất thường và đề xuất hành động kiểm tra bảo trì tự chủ cụ thể."
            )
            ham_luu_tin_nhan(st.session_state.phien_hien_tai, "user", f"🔍 Yêu cầu AI phân tích vận hành ({vi_tri_may} - {ca_truc}).")
            st.session_state.tu_dong_hoi_plc = cau_hoi_plc
            st.rerun()
    else:
        st.warning(f"Đang chờ dữ liệu từ Supabase Cloud... ({loi_ket_noi_plc})")

    st.divider()
    hien_thi_so_ban_giao_ca()

