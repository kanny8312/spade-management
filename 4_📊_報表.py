import streamlit as st
import pandas as pd
import plotly.express as px
from utils.db import get_inventory_logs, get_stock_in_records, get_supabase

st.set_page_config(page_title="報表", page_icon="📊", layout="centered")
st.title("📊 報表分析")

tab1, tab2 = st.tabs(["📉 庫存趨勢", "🧮 進出貨歷史"])

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
    sb = get_supabase()
    wastes = sb.table("waste_records").select("*").order("record_date", desc=True).limit(200).execute().data
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
