import os
from datetime import datetime
import pandas as pd
import requests
import streamlit as st
from modules.quan_ly_ho_so import lay_danh_sach_ten_thiet_bi_cloud


def lay_danh_sach_ban_giao(limit=20):
    url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    endpoint = f"{url_du_an}/rest/v1/nhat_ky_ban_giao_ca?select=*&order=id.desc&limit={limit}"
    headers = {
        "apikey": key_du_an,
        "Authorization": f"Bearer {key_du_an}",
        "Cache-Control": "no-cache"
    }
    res = requests.get(endpoint, headers=headers, timeout=10)
    res.raise_for_status()
    return pd.DataFrame(res.json())


def ghi_nhat_ky_ban_giao(du_lieu):
    url_du_an = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key_du_an = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    endpoint = f"{url_du_an}/rest/v1/nhat_ky_ban_giao_ca"
    headers = {
        "apikey": key_du_an,
        "Authorization": f"Bearer {key_du_an}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    res = requests.post(endpoint, json=du_lieu, headers=headers, timeout=10)
    res.raise_for_status()


def hien_thi_so_ban_giao_ca():
    st.subheader("📒 Sổ Nhật Ký Bàn Giao Ca Điện Tử")

    gio_hien_tai = datetime.now().hour
    ca_mac_dinh = 0 if 7 <= gio_hien_tai < 19 else 1

    with st.form("form_ban_giao_ca", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ca_truc = st.selectbox("🕒 Ca bàn giao", [
                "☀️ Ca Ngày (07:00 - 19:00)",
                "🌙 Ca Đêm (19:00 - 07:00)"
            ], index=ca_mac_dinh)
            cum_thiet_bi = st.selectbox("⚙️ Cụm thiết bị chính", lay_danh_sach_ten_thiet_bi_cloud())

        with c2:
            nguoi_ban_giao = st.text_input("👷 Trưởng ca / Kỹ thuật giao", placeholder="VD: Nguyễn Văn A")
            nguoi_nhan_ca = st.text_input("👷 Trưởng ca / Kỹ thuật nhận", placeholder="VD: Trần Văn B")
        with c3:
            tinh_trang_may = st.selectbox("🚦 Tình trạng bàn giao", [
                "🟢 Hoạt động bình thường, ổn định",
                "🟡 Có lưu ý nhỏ / Cần theo dõi thêm",
                "🔴 Đang có sự cố / Chờ vật tư xử lý"
            ])

        noi_dung = st.text_area(
            "📝 Nội dung công việc đã thực hiện, thông số lưu ý & Hạng mục tồn đọng cho ca sau:",
            height=100,
            placeholder="VD: Đã vệ sinh cảm biến nhiệt độ 1, kiểm tra dòng biến tần lô ép ổn định 56A (40% tải). Ca sau lưu ý theo dõi thêm nhiệt độ gối trục bên truyền động..."
        )

        nut_luu = st.form_submit_button("💾 Lưu & Ký Xác Nhận Bàn Giao Ca", type="primary", use_container_width=True)

        if nut_luu:
            if not nguoi_ban_giao.strip() or not noi_dung.strip():
                st.warning("⚠️ Vui lòng nhập tên người bàn giao và nội dung công việc trước khi lưu!")
            else:
                try:
                    du_lieu_moi = {
                        "thoi_gian": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "ca_truc": ca_truc,
                        "nguoi_ban_giao": nguoi_ban_giao.strip(),
                        "nguoi_nhan_ca": nguoi_nhan_ca.strip() if nguoi_nhan_ca.strip() else "Chưa ký nhận",
                        "cum_thiet_bi": cum_thiet_bi,
                        "tinh_trang_may": tinh_trang_may,
                        "noi_dung_ban_giao": noi_dung.strip()
                    }
                    ghi_nhat_ky_ban_giao(du_lieu_moi)
                    st.success("✅ Đã lưu biên bản bàn giao ca lên hệ thống đám mây thành công!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi lưu nhật ký bàn giao: {e}")

    st.divider()
    st.markdown("**📜 Lịch sử bàn giao các ca gần nhất:**")

    try:
        df_lich_su = lay_danh_sach_ban_giao(limit=15)
        if not df_lich_su.empty:
            for _, dong in df_lich_su.iterrows():
                tieu_de_expander = (
                    f"{dong['tinh_trang_may']} | {dong['thoi_gian']} — {dong['ca_truc']} "
                    f"({dong['cum_thiet_bi']}) | Giao: {dong['nguoi_ban_giao']}"
                )
                with st.expander(tieu_de_expander, expanded=False):
                    st.markdown(f"**👷 Bàn giao:** {dong['nguoi_ban_giao']} ➡️ **Nhận ca:** {dong['nguoi_nhan_ca']}")
                    st.info(dong['noi_dung_ban_giao'])
        else:
            st.info("Chưa có dữ liệu bàn giao ca nào. Hãy nhập biên bản đầu tiên ở khung phía trên!")
    except Exception as e_load:
        st.warning(f"Không thể tải lịch sử bàn giao ca: {e_load}")
