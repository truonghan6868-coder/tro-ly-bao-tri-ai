import os
from datetime import datetime
import altair as alt
import streamlit as st
from streamlit_autorefresh import st_autorefresh


def hien_thi_tab_giam_sat(df_plc, loi_ket_noi_plc, ham_luu_tin_nhan):
    # Tự động xác định ca trực theo khung 07h-19h và 19h-07h
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

    if not df_plc.empty:
        moi_nhat = df_plc.iloc[0]

        NG_T1 = float(os.getenv("NGUONG_TEMP1", 80.0))
        NG_T2 = float(os.getenv("NGUONG_TEMP2", 80.0))
        NG_CUR = float(os.getenv("NGUONG_CURRENT", 65.0))
        NG_PRESS_MIN = 3.5

        t1_val = float(moi_nhat['temp1'])
        t2_val = float(moi_nhat['temp2'])
        sp_val = float(moi_nhat['speed'])
        pr_val = float(moi_nhat['pressure'])
        cur_val = float(moi_nhat['motor_current'])

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
            delta=f"Thấp (<{NG_PRESS_MIN})" if pr_val < NG_PRESS_MIN else "Đạt áp suất",
            delta_color="inverse" if pr_val < NG_PRESS_MIN else "normal"
        )
        m5.metric(
            "🔌 Dòng động cơ", f"{cur_val:.2f} A",
            delta=f"Quá tải +{cur_val - NG_CUR:.1f}A" if cur_val > NG_CUR else f"Ổn định (Max {NG_CUR}A)",
            delta_color="inverse" if cur_val > NG_CUR else "normal"
        )

        st.divider()

                # Vẽ 4 biểu đồ xu hướng 30 mẫu mới nhất
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
            st.altair_chart(ve_bieu_do_chuan(df_bieu_do, ["temp1", "temp2"], "Nhiệt độ (°C)", 0, 120, ["#FF4B4B", "#FFA500"]), use_container_width=True)
        with r1_c2:
            st.markdown("**🔌 Biểu đồ Dòng điện Động cơ (A)**")
            st.altair_chart(ve_bieu_do_chuan(df_bieu_do, ["motor_current"], "Dòng điện (A)", 0, 150, ["#00CC96"]), use_container_width=True)

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
                f"- Trạng thái vận hành: {trang_thai_may}\n"
                f"- Sản phẩm đang chạy: {dinh_luong_giay}\n\n"
                f"10 MẪU THÔNG SỐ ĐO TỪ PLC SIEMENS (DB3):\n{du_lieu_tom_tat}\n\n"
                "Dựa trên bối cảnh vận hành thực tế và chuỗi số liệu PLC trên, hãy đánh giá tình trạng thiết bị, "
                "phân tích nguyên nhân nếu có bất thường và đề xuất hành động kiểm tra bảo trì tự chủ cụ thể cho công nhân/kỹ thuật viên."
            )
            ham_luu_tin_nhan(st.session_state.phien_hien_tai, "user", f"🔍 Yêu cầu AI phân tích vận hành ({vi_tri_may} - {ca_truc}).")
            st.session_state.tu_dong_hoi_plc = cau_hoi_plc
            st.rerun()
    else:
        st.warning(f"Đang chờ dữ liệu từ Supabase Cloud... ({loi_ket_noi_plc})")
