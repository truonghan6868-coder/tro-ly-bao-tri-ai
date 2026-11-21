import io
import os
from datetime import datetime, timedelta
import pandas as pd
import requests
import streamlit as st


def truy_xuat_du_lieu_lich_su(tu_thoi_diem, den_thoi_diem):
    url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    endpoint = f"{url_du_an}/rest/v1/du_lieu_plc_db3"

    headers = {
        "apikey": key_du_an,
        "Authorization": f"Bearer {key_du_an}",
        "Cache-Control": "no-cache"
    }
    # Dùng danh sách tuple để truyền đồng thời điều kiện >= và <= cho cột thoi_gian
    params = [
        ("select", "thoi_gian,temp1,temp2,speed,pressure,motor_current"),
        ("thoi_gian", f"gte.{tu_thoi_diem}"),
        ("thoi_gian", f"lte.{den_thoi_diem}"),
        ("order", "thoi_gian.asc"),
        ("limit", "5000")
    ]
    res = requests.get(endpoint, headers=headers, params=params, timeout=15)
    res.raise_for_status()
    return pd.DataFrame(res.json())


def hien_thi_tab_bao_cao(df_plc_mac_dinh):
    st.subheader("📊 Truy Xuất Lịch Sử Ca & Xuất Báo Cáo ISO")

    # 1. Khu vực bộ lọc tra cứu dữ liệu quá khứ trên Supabase
    with st.container(border=True):
        st.markdown("**🔍 Bộ lọc dữ liệu vận hành theo Ca trực & Ngày:**")
        f1, f2, f3, f4 = st.columns([1.2, 1.5, 1.3, 1.2])
        with f1:
            ngay_chon = st.date_input("📅 Chọn ngày", value=datetime.now().date())
        with f2:
            ca_chon = st.selectbox("🕒 Chọn khung ca", [
                "☀️ Ca Ngày (07:00 - 19:00)",
                "🌙 Ca Đêm (19:00 - 07:00 hôm sau)",
                "📆 Cả ngày (00:00 - 23:59)",
                "⚡ 50 mẫu mới nhất (Mặc định)"
            ])
        with f3:
            nguoi_lap = st.text_input("👷 Người lập báo cáo", value="Kỹ thuật Điện - TĐH")
        with f4:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            nut_loc = st.button("🔎 Truy xuất dữ liệu", type="primary", use_container_width=True)

    # Xác định dữ liệu hiển thị (Lọc theo ca hoặc dùng 50 mẫu mới nhất)
    df_bao_cao = pd.DataFrame()
    khoang_thoi_gian_str = "50 mẫu gần nhất"

    if ca_chon == "⚡ 50 mẫu mới nhất (Mặc định)" and not nut_loc:
        df_bao_cao = df_plc_mac_dinh.iloc[::-1].copy() if not df_plc_mac_dinh.empty else pd.DataFrame()
    else:
        ngay_str = ngay_chon.strftime("%Y-%m-%d")
        if "Ca Ngày" in ca_chon:
            tu_luc = f"{ngay_str} 07:00:00"
            den_luc = f"{ngay_str} 19:00:00"
        elif "Ca Đêm" in ca_chon:
            ngay_hom_sau = (ngay_chon + timedelta(days=1)).strftime("%Y-%m-%d")
            tu_luc = f"{ngay_str} 19:00:00"
            den_luc = f"{ngay_hom_sau} 07:00:00"
        elif "Cả ngày" in ca_chon:
            tu_luc = f"{ngay_str} 00:00:00"
            den_luc = f"{ngay_str} 23:59:59"
        else:
            tu_luc, den_luc = None, None

        if tu_luc and den_luc:
            khoang_thoi_gian_str = f"{tu_luc} đến {den_luc}"
            try:
                with st.spinner("Đang tải dữ liệu lịch sử từ Supabase Cloud..."):
                    df_bao_cao = truy_xuat_du_lieu_lich_su(tu_luc, den_luc)
            except Exception as e_loc:
                st.error(f"Lỗi truy xuất lịch sử Supabase: {e_loc}")
        else:
            df_bao_cao = df_plc_mac_dinh.iloc[::-1].copy() if not df_plc_mac_dinh.empty else pd.DataFrame()

    # 2. Hiển thị chỉ số KPI và Bảng thống kê
    if not df_bao_cao.empty:
        st.caption(f"📌 Đang hiển thị **{len(df_bao_cao)}** bản ghi dữ liệu ({khoang_thoi_gian_str})")

        NG_T1 = float(os.getenv("NGUONG_TEMP1", 80.0))
        NG_T2 = float(os.getenv("NGUONG_TEMP2", 80.0))
        NG_CUR = float(os.getenv("NGUONG_CURRENT", 65.0))
        dong_dinh_muc = 135.0  # Động cơ 75kW

        tai_trung_binh = (df_bao_cao['motor_current'].mean() / dong_dinh_muc) * 100
        so_lan_qua_nhiet = int(((df_bao_cao['temp1'] > NG_T1) | (df_bao_cao['temp2'] > NG_T2)).sum())
        so_lan_qua_dong = int((df_bao_cao['motor_current'] > NG_CUR).sum())

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("⚡ Tải trung bình (75kW)", f"{tai_trung_binh:.1f} %")
        kpi2.metric("🌡️ Nhiệt độ đỉnh (Max)", f"{max(df_bao_cao['temp1'].max(), df_bao_cao['temp2'].max()):.1f} °C")
        kpi3.metric("🔥 Số mẫu quá nhiệt", f"{so_lan_qua_nhiet} lần", delta="Cần kiểm tra" if so_lan_qua_nhiet > 0 else "An toàn", delta_color="inverse" if so_lan_qua_nhiet > 0 else "normal")
        kpi4.metric("⚠️ Số mẫu quá dòng", f"{so_lan_qua_dong} lần", delta="Cần kiểm tra" if so_lan_qua_dong > 0 else "An toàn", delta_color="inverse" if so_lan_qua_dong > 0 else "normal")

        st.divider()

        bang_thong_ke = pd.DataFrame({
            "Thông số giám sát": ["Nhiệt độ 1 (°C)", "Nhiệt độ 2 (°C)", "Tốc độ", "Áp suất", "Dòng động cơ (A)"],
            "Giá trị Min": [
                df_bao_cao['temp1'].min(), df_bao_cao['temp2'].min(),
                df_bao_cao['speed'].min(), df_bao_cao['pressure'].min(), df_bao_cao['motor_current'].min()
            ],
            "Giá trị Trung bình": [
                round(df_bao_cao['temp1'].mean(), 2), round(df_bao_cao['temp2'].mean(), 2),
                round(df_bao_cao['speed'].mean(), 2), round(df_bao_cao['pressure'].mean(), 2), round(df_bao_cao['motor_current'].mean(), 2)
            ],
            "Giá trị Max": [
                df_bao_cao['temp1'].max(), df_bao_cao['temp2'].max(),
                df_bao_cao['speed'].max(), df_bao_cao['pressure'].max(), df_bao_cao['motor_current'].max()
            ],
            "Ngưỡng an toàn": [f"<= {NG_T1} °C", f"<= {NG_T2} °C", "Theo công nghệ", ">= 3.5", f"<= {NG_CUR} A"]
        })
        st.dataframe(bang_thong_ke, use_container_width=True, hide_index=True)

        # 3. Xuất file Excel chuẩn lưu trữ hồ sơ ISO / Bảo trì
        bang_bia_iso = pd.DataFrame({
            "Hạng mục hồ sơ": [
                "Tên hệ thống / Thiết bị",
                "Khung ca trực",
                "Khoảng thời gian trích xuất",
                "Tổng số mẫu ghi nhận",
                "Người lập báo cáo",
                "Thời điểm xuất file"
            ],
            "Nội dung chi tiết": [
                "Hệ thống Giám sát PLC Siemens (DB3) - Máy Giấy",
                ca_chon,
                khoang_thoi_gian_str,
                f"{len(df_bao_cao)} mẫu",
                nguoi_lap,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
        })

        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
            bang_bia_iso.to_excel(writer, index=False, sheet_name='Thong_Tin_Ca_ISO')
            bang_thong_ke.to_excel(writer, index=False, sheet_name='Thong_Ke_Tong_Hop')
            df_bao_cao.to_excel(writer, index=False, sheet_name='Du_Lieu_Chi_Tiet_PLC')

        st.download_button(
            label="📥 Xuất báo cáo ca ra file Excel chuẩn ISO (.xlsx)",
            data=buffer_excel.getvalue(),
            file_name=f"Bao_Cao_Van_Hanh_Ca_{ngay_chon.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

        with st.expander("📋 Xem toàn bộ dữ liệu chi tiết trong ca"):
            st.dataframe(df_bao_cao, use_container_width=True, hide_index=True)
    else:
        st.info("Không tìm thấy bản ghi dữ liệu nào trong khoảng thời gian đã chọn. Hãy thử chọn ngày khác hoặc kiểm tra kết nối Supabase.")

