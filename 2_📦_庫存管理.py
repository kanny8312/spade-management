import streamlit as st
import pandas as pd
from utils.db import get_materials, update_stock, get_inventory_logs

st.set_page_config(page_title="庫存管理", page_icon="📦", layout="centered")
st.title("📦 庫存管理")

# ─── 密碼驗證 ────────────────────────────────────
if 'admin_ok' not in st.session_state:
    st.session_state.admin_ok = False

if not st.session_state.admin_ok:
    st.markdown("🔒 **需要管理員密碼才能修改庫存**")
    pwd = st.text_input("請輸入密碼", type="password")
    if st.button("登入"):
        if pwd == st.secrets.get("ADMIN_PASSWORD", "8312"):
            st.session_state.admin_ok = True
            st.rerun()
        else:
            st.error("密碼錯誤！")
    st.stop()

st.success("✅ 已登入")
if st.button("登出"):
    st.session_state.admin_ok = False
    st.rerun()

st.markdown("---")

# ─── 盤點調整 ────────────────────────────────────
st.subheader("盤點調整庫存")
materials = get_materials()
cats = sorted(set(m['category'] for m in materials))
selected_cat = st.selectbox("篩選類別", ['全部'] + cats)
filtered = [m for m in materials if selected_cat == '全部' or m['category'] == selected_cat]

st.caption("修改數字後點「儲存」，會記錄新舊差異")

changes = {}
for m in filtered:
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        st.markdown(f"**{m['name']}** ({m['unit']})")
    with col2:
        new_val = st.number_input(
            f"{m['name']}",
            min_value=0.0,
            value=float(m['current_stock'] or 0),
            step=1.0,
            key=f"stock_{m['name']}",
            label_visibility="collapsed"
        )
    with col3:
        safety = float(m['safety_stock'] or 0)
        if new_val <= safety * 0.5:
            st.markdown("🔴")
        elif new_val <= safety:
            st.markdown("🟡")
        else:
            st.markdown("🟢")
    changes[m['name']] = {'new': new_val, 'old': float(m['current_stock'] or 0)}

if st.button("💾 儲存盤點結果", type="primary", use_container_width=True):
    updated = 0
    for name, v in changes.items():
        if v['new'] != v['old']:
            update_stock(name, v['new'], note="盤點調整")
            updated += 1
    if updated:
        st.success(f"✅ 已更新 {updated} 項庫存！")
        st.rerun()
    else:
        st.info("沒有變更")

# ─── 安全庫存設定 ─────────────────────────────────
st.markdown("---")
st.subheader("⚙️ 安全庫存設定")
st.caption("低於此數量會出現警示（不需密碼）")

from utils.db import get_supabase

with st.form("safety_form"):
    safety_changes = {}
    for m in filtered:
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"{m['name']} ({m['unit']})")
        with col2:
            safety_changes[m['name']] = st.number_input(
                m['name'], min_value=0.0,
                value=float(m['safety_stock'] or 0),
                step=1.0, key=f"safe_{m['name']}",
                label_visibility="collapsed"
            )
    if st.form_submit_button("儲存安全庫存"):
        sb = get_supabase()
        for name, val in safety_changes.items():
            sb.table("raw_materials").update({"safety_stock": val}).eq("name", name).execute()
        st.success("✅ 已儲存！")
        st.rerun()

# ─── 盤點歷史 ─────────────────────────────────────
st.markdown("---")
st.subheader("📜 盤點歷史（最近90天）")
logs = get_inventory_logs(90)
if logs:
    df = pd.DataFrame(logs)[['adjusted_at', 'material_name', 'old_stock', 'new_stock', 'difference', 'note']]
    df.columns = ['時間', '品項', '原數量', '新數量', '差異', '備註']
    df['時間'] = pd.to_datetime(df['時間']).dt.strftime('%m/%d %H:%M')
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.caption("尚無記錄")
