import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import (get_inventory_logs, get_stock_in_records,
                get_waste_records_recent, get_sales_records_recent,
                get_materials)

st.set_page_config(page_title="報表", page_icon="📊", layout="centered")
st.title("📊 報表分析")

tab1, tab2, tab3, tab4 = st.tabs([
    "📉 庫存趨勢", "🧮 進出貨歷史", "🏆 報廢排行", "💰 月損益估算"
])

with tab1:
    st.subheader("庫存盤點趨勢（近90天）")
    logs = get_inventory_logs(90)
    if not logs:
        st.info("尚無盤點記錄")
    else:
        df = pd.DataFrame(logs)
        df['日期'] = pd.to_datetime(df['adjusted_at']).dt.date
        items = sorted(df['material_name'].unique())
        selected = st.multiselect("選擇品項", items, default=items[:3] if len(items) >= 3 else items)
        if selected:
            df2 = df[df['material_name'].isin(selected)]
            fig = px.line(df2, x='日期', y='new_stock', color='material_name',
                          labels={'new_stock': '庫存量', 'material_name': '品項'},
                          title="庫存變化")
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("進貨記錄（近90天）")
    sin = get_stock_in_records(90)
    if sin:
        df = pd.DataFrame(sin)[['received_date', 'material_name', 'quantity', 'unit']]
        df.columns = ['日期', '品項', '數量', '單位']
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("尚無進貨記錄")

    st.subheader("報廢記錄（近30天）")
    wastes = get_waste_records_recent(200)
    if wastes:
        df = pd.DataFrame(wastes)[['record_date', 'material_name', 'waste_amount', 'unit', 'reason']]
        df.columns = ['日期', '品項', '報廢量', '單位', '原因']
        st.dataframe(df, use_container_width=True, hide_index=True)

        # 報廢彙總
        st.markdown("**各品項報廢量彙總：**")
        summary = df.groupby('品項')['報廢量'].sum().reset_index().sort_values('報廢量', ascending=False)
        st.dataframe(summary, use_container_width=True, hide_index=True)
    else:
        st.info("尚無報廢記錄")

# ─── Tab3: 報廢排行 ──────────────────────────────
with tab3:
    st.subheader("🏆 報廢排行")
    n_days = st.selectbox("期間", [7, 30, 60, 90], index=1, format_func=lambda d: f"近 {d} 天")
    wastes = get_waste_records_recent(500)
    if not wastes:
        st.info("尚無報廢記錄")
    else:
        df_w = pd.DataFrame(wastes)
        df_w['日期'] = pd.to_datetime(df_w['record_date']).dt.date
        cutoff = date.today() - timedelta(days=n_days)
        df_w = df_w[df_w['日期'] >= cutoff]
        if df_w.empty:
            st.info(f"近 {n_days} 天沒有報廢記錄")
        else:
            # 取成本價
            mats = {m['name']: m for m in get_materials()}
            def cost_of(name):
                m = mats.get(name, {})
                return float(m.get('cost') or m.get('unit_cost') or m.get('cost_price') or 0)

            df_w['單價'] = df_w['material_name'].map(cost_of)
            df_w['金額'] = df_w['waste_amount'].astype(float) * df_w['單價']
            summary = df_w.groupby('material_name').agg(
                報廢次數=('waste_amount', 'count'),
                總報廢量=('waste_amount', 'sum'),
                損失金額=('金額', 'sum')
            ).reset_index().sort_values('損失金額', ascending=False)
            summary.columns = ['品項', '報廢次數', '總報廢量', '損失金額']
            summary['損失金額'] = summary['損失金額'].apply(lambda x: f"{x:,.1f}")
            st.dataframe(summary, use_container_width=True, hide_index=True)

            total_loss = df_w['金額'].sum()
            st.metric(f"近 {n_days} 天報廢總損失", f"{total_loss:,.0f} 元")

            # 原因分析
            st.markdown("**報廢原因分布**")
            reason_summary = df_w.groupby('reason').agg(
                次數=('waste_amount', 'count'),
                損失=('金額', 'sum')
            ).reset_index().sort_values('損失', ascending=False)
            reason_summary.columns = ['原因', '次數', '損失金額']
            reason_summary['損失金額'] = reason_summary['損失金額'].apply(lambda x: f"{x:,.1f}")
            st.dataframe(reason_summary, use_container_width=True, hide_index=True)

# ─── Tab4: 月損益估算 ─────────────────────────────
with tab4:
    st.subheader("💰 月損益估算")
    st.caption("⚠️ 不含人工、租金、水電 — 只算原物料相關")

    today = date.today()
    default_year = today.year
    default_month = today.month
    c1, c2 = st.columns(2)
    year = c1.number_input("年", 2024, 2030, default_year)
    month = c2.number_input("月", 1, 12, default_month)
    month_start = date(year, month, 1)
    next_month = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    days_in_month = (next_month - month_start).days

    # 1. 營業額（從 sales_records）
    days_back = (today - month_start).days + 1
    sales = get_sales_records_recent(days=max(days_back, 1))
    df_s = pd.DataFrame(sales) if sales else pd.DataFrame()
    revenue = 0
    if not df_s.empty:
        df_s['日期'] = pd.to_datetime(df_s['sale_date']).dt.date
        df_s = df_s[(df_s['日期'] >= month_start) & (df_s['日期'] < next_month)]
        revenue = df_s.get('revenue', pd.Series([0])).astype(float).sum()

    # 2. 進貨成本
    sin_records = get_stock_in_records(days=max(days_back, 1))
    df_sin = pd.DataFrame(sin_records) if sin_records else pd.DataFrame()
    mats = {m['name']: m for m in get_materials()}
    def cost_of(name):
        m = mats.get(name, {})
        return float(m.get('cost') or m.get('unit_cost') or m.get('cost_price') or 0)
    purchase_cost = 0
    if not df_sin.empty:
        df_sin['日期'] = pd.to_datetime(df_sin['received_date']).dt.date
        df_sin = df_sin[(df_sin['日期'] >= month_start) & (df_sin['日期'] < next_month)]
        df_sin['金額'] = df_sin.apply(
            lambda r: float(r.get('quantity') or 0) * cost_of(r.get('material_name')), axis=1)
        purchase_cost = df_sin['金額'].sum()

    # 3. 報廢損失
    wastes = get_waste_records_recent(500)
    waste_loss = 0
    if wastes:
        df_w = pd.DataFrame(wastes)
        df_w['日期'] = pd.to_datetime(df_w['record_date']).dt.date
        df_w = df_w[(df_w['日期'] >= month_start) & (df_w['日期'] < next_month)]
        df_w['金額'] = df_w.apply(
            lambda r: float(r.get('waste_amount') or 0) * cost_of(r.get('material_name')), axis=1)
        waste_loss = df_w['金額'].sum()

    # 4. 盤點短少（負差異 × 成本）
    logs = get_inventory_logs(days=max(days_back, 30))
    inv_loss = 0
    if logs:
        df_l = pd.DataFrame(logs)
        df_l['日期'] = pd.to_datetime(df_l['adjusted_at']).dt.date
        df_l = df_l[(df_l['日期'] >= month_start) & (df_l['日期'] < next_month)]
        df_l = df_l[df_l.get('note') == '盤點調整']
        df_l['金額'] = df_l.apply(
            lambda r: float(r.get('difference') or 0) * cost_of(r.get('material_name')), axis=1)
        inv_loss = df_l['金額'].sum()  # 負值 = 短少；正值 = 多出

    gross = revenue - purchase_cost - waste_loss + inv_loss   # inv_loss 含正負

    st.markdown(f"### {year} 年 {month} 月")
    c1, c2 = st.columns(2)
    c1.metric("📈 營業額", f"{revenue:,.0f} 元")
    c2.metric("📦 進貨成本", f"{purchase_cost:,.0f} 元")
    c1.metric("🗑️ 報廢損失", f"{waste_loss:,.0f} 元")
    c2.metric("📉 盤點短少", f"{-inv_loss:,.0f} 元" if inv_loss < 0 else f"+{inv_loss:,.0f} 元",
              delta_color="inverse")
    st.markdown("---")
    st.metric("💵 估算毛利", f"{gross:,.0f} 元",
              delta=f"{(gross/revenue*100 if revenue else 0):.1f}% 毛利率")
    st.caption("公式：毛利 = 營業額 − 進貨成本 − 報廢損失 + 盤點淨差")
