import streamlit as st
import pandas as pd
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_materials, update_stock, get_inventory_logs, update_safety_stock

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
        for name, val in safety_changes.items():
            update_safety_stock(name, val)
        st.success("✅ 已儲存！")
        st.rerun()

# ─── 盤點損益報表 ─────────────────────────────────
st.markdown("---")
st.subheader("💰 盤點損益報表")
st.caption("把每次盤點的「實際 vs 賬面」差異 × 成本 = 短少/多出金額")

period_days = st.selectbox("期間", [7, 14, 30, 60, 90], index=2, format_func=lambda d: f"近 {d} 天")
logs_pl = get_inventory_logs(period_days)

if logs_pl:
    # 對應成本價（從 raw_materials 取，試多種欄位名）
    cost_map = {}
    cost_field = None
    for m in materials:
        for k in ('cost', 'unit_cost', 'cost_price', 'price', 'unit_price', 'cost_per_unit'):
            if k in m and m[k] is not None:
                cost_map[m['name']] = float(m[k] or 0)
                cost_field = k
                break

    # 如果都找不到 → 顯示警告 + 列出所有欄位
    if not cost_map and materials:
        st.error("❌ 找不到成本價欄位！raw_materials 實際欄位如下：")
        st.write(list(materials[0].keys()))
        st.info("請告訴我成本欄位叫什麼名字")

    rows = []
    total_loss = 0.0
    total_gain = 0.0
    for log in logs_pl:
        if log.get('note') != '盤點調整':
            continue
        mname = log['material_name']
        diff = float(log.get('difference') or 0)
        unit_cost = cost_map.get(mname, 0)
        amount = diff * unit_cost
        if amount < 0:
            total_loss += amount
        else:
            total_gain += amount
        rows.append({
            '時間': pd.to_datetime(log['adjusted_at']).strftime('%m/%d %H:%M'),
            '品項': mname,
            '原數量': f"{float(log.get('old_stock') or 0):,.1f}",
            '新數量': f"{float(log.get('new_stock') or 0):,.1f}",
            '差異': f"{diff:+,.1f}",
            '單價': f"{unit_cost:,.3f}",
            '金額': f"{amount:+,.1f}",
        })

    if rows:
        c1, c2, c3 = st.columns(3)
        c1.metric("📉 短少金額", f"{total_loss:,.0f} 元")
        c2.metric("📈 多出金額", f"+{total_gain:,.0f} 元")
        c3.metric("💵 淨損益", f"{(total_loss + total_gain):+,.0f} 元",
                  delta_color="inverse")

        # 各品項彙總
        st.markdown("**各品項彙總（短少最多排前面）**")
        df_logs = pd.DataFrame([{
            '品項': r['品項'],
            '差異': float(r['差異'].replace(',', '').replace('+', '')),
            '金額': float(r['金額'].replace(',', '').replace('+', '')),
        } for r in rows])
        summary = df_logs.groupby('品項').agg({'差異': 'sum', '金額': 'sum'}).reset_index()
        summary = summary.sort_values('金額', ascending=True)
        summary['差異'] = summary['差異'].apply(lambda x: f"{x:+,.1f}")
        summary['金額'] = summary['金額'].apply(lambda x: f"{x:+,.1f}")
        st.dataframe(summary, use_container_width=True, hide_index=True)

        with st.expander("📜 明細記錄"):
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(f"近 {period_days} 天沒有盤點調整記錄")
else:
    st.info("尚無盤點記錄")

# ─── 盤點歷史（全部）─────────────────────────────
st.markdown("---")
st.subheader("📜 盤點歷史（最近90天，含所有調整）")
logs = get_inventory_logs(90)
if logs:
    df = pd.DataFrame(logs)[['adjusted_at', 'material_name', 'old_stock', 'new_stock', 'difference', 'note']]
    df.columns = ['時間', '品項', '原數量', '新數量', '差異', '備註']
    df['時間'] = pd.to_datetime(df['時間']).dt.strftime('%m/%d %H:%M')
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.caption("尚無記錄")
