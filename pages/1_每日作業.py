import streamlit as st
import pandas as pd
from datetime import date
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import (get_tea_specs, get_brew_records, add_brew_record,
                get_sales_records, import_sales, get_waste_records,
                add_waste_record, get_materials, get_recipes)
from calculations import verify_tea

st.set_page_config(page_title="每日作業", page_icon="📋", layout="centered")
st.title("📋 每日作業")

today = str(date.today())
tab1, tab2, tab3, tab4 = st.tabs(["🍵 煮茶備料", "📥 匯入銷售", "🗑️ 報廢記錄", "✅ 對帳結果"])

# ─── Tab1: 煮茶備料 ─────────────────────────────
with tab1:
    st.subheader("今日煮茶記錄")
    tea_specs = {t['tea_name']: t for t in get_tea_specs()}
    tea_names = list(tea_specs.keys())

    with st.form("brew_form"):
        tea = st.selectbox("茶種", tea_names)
        water = st.number_input("加水量 (ml)", min_value=1000, max_value=20000, step=500, value=3000)

        spec = tea_specs.get(tea, {})
        g_per_3000 = float(spec.get('grams_per_3000ml', 90))
        yield_rate = float(spec.get('yield_rate', 0.88))
        leaves_calc = round(g_per_3000 * water / 3000, 1)
        yield_calc = round(water * yield_rate, 0)

        st.info(f"📊 預估茶葉用量：**{leaves_calc} g** ／ 預估出湯量：**{yield_calc:.0f} ml**")

        actual_yield = st.number_input("實際出湯量 (ml)（撈完茶葉後量）",
                                       min_value=0, max_value=20000, step=100, value=int(yield_calc))
        submitted = st.form_submit_button("✅ 記錄")
        if submitted:
            add_brew_record(today, tea, water, actual_yield, leaves_calc)
            st.success(f"已記錄！茶葉扣除 {leaves_calc}g")
            st.rerun()

    st.markdown("---")
    st.markdown("**今日已記錄：**")
    brews = get_brew_records(today)
    if brews:
        df = pd.DataFrame(brews)[['tea_name', 'water_used_ml', 'actual_yield_ml', 'leaves_used_g']]
        df.columns = ['茶種', '加水量(ml)', '出湯量(ml)', '茶葉(g)']
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("今天還沒有記錄")

# ─── Tab2: 匯入銷售 ─────────────────────────────
with tab2:
    st.subheader("匯入肚肚銷售CSV")
    st.caption("從肚肚系統匯出「銷售統計」CSV，上傳到這裡")

    uploaded = st.file_uploader("選擇 CSV 檔案", type=['csv'])
    if uploaded:
        try:
            df = pd.read_csv(uploaded, encoding='utf-8-sig')
            st.write("**預覽（前10筆）：**")
            st.dataframe(df.head(10), use_container_width=True)

            # 欄位對應
            col_map = {}
            cols = list(df.columns)
            st.markdown("**確認欄位對應：**")
            c1, c2 = st.columns(2)
            with c1:
                col_map['product'] = st.selectbox("商品名稱欄位", cols,
                    index=cols.index('商品名稱') if '商品名稱' in cols else 0)
                col_map['size'] = st.selectbox("尺寸欄位", ['(無)'] + cols,
                    index=cols.index('價位名稱')+1 if '價位名稱' in cols else 0)
            with c2:
                col_map['qty'] = st.selectbox("銷售數量欄位", cols,
                    index=cols.index('銷售數量') if '銷售數量' in cols else 0)
                col_map['revenue'] = st.selectbox("金額欄位", ['(無)'] + cols,
                    index=cols.index('金額')+1 if '金額' in cols else 0)

            if st.button("📥 匯入"):
                records = []
                for _, row in df.iterrows():
                    name = str(row[col_map['product']])
                    if name in ('小計', '合計', '商品名稱', 'nan'):
                        continue
                    size = str(row[col_map['size']]) if col_map['size'] != '(無)' else ''
                    qty_raw = row[col_map['qty']]
                    try:
                        qty = int(float(str(qty_raw).replace(',', '')))
                    except:
                        continue
                    revenue = 0
                    if col_map['revenue'] != '(無)':
                        try:
                            revenue = float(str(row[col_map['revenue']]).replace(',', ''))
                        except:
                            pass
                    if qty > 0:
                        records.append({
                            "sale_date": today,
                            "product_name": name,
                            "size": size if size not in ('nan', 'None') else '',
                            "quantity": qty,
                            "revenue": revenue
                        })
                if records:
                    import_sales(records)
                    st.success(f"✅ 已匯入 {len(records)} 筆銷售記錄！")
                    st.rerun()
                else:
                    st.warning("沒有有效資料可匯入")
        except Exception as e:
            st.error(f"讀取失敗：{e}")

    st.markdown("---")
    sales = get_sales_records(today)
    st.caption(f"今日已匯入 {len(sales)} 筆銷售記錄")

# ─── Tab3: 報廢記錄 ─────────────────────────────
with tab3:
    st.subheader("報廢記錄")
    materials = get_materials()
    mat_names = [m['name'] for m in materials]
    mat_units = {m['name']: m['unit'] for m in materials}

    with st.form("waste_form"):
        mat = st.selectbox("品項", mat_names)
        unit = mat_units.get(mat, '')
        amount = st.number_input(f"報廢量 ({unit})", min_value=0.0, step=10.0)
        reason = st.selectbox("原因", ["正常報廢", "品管試茶", "製作失敗", "逾期", "其他"])
        if st.form_submit_button("記錄報廢"):
            if amount > 0:
                add_waste_record(today, mat, amount, unit, reason)
                st.success("✅ 已記錄！")
                st.rerun()

    st.markdown("---")
    wastes = get_waste_records(today)
    if wastes:
        df = pd.DataFrame(wastes)[['material_name', 'waste_amount', 'unit', 'reason']]
        df.columns = ['品項', '數量', '單位', '原因']
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("今天還沒有報廢記錄")

# ─── Tab4: 對帳結果 ─────────────────────────────
with tab4:
    st.subheader("茶湯對帳")
    brews = get_brew_records(today)
    wastes = get_waste_records(today)
    sales = get_sales_records(today)
    recipes = get_recipes()

    if not brews:
        st.info("請先填寫今日煮茶記錄")
    elif not sales:
        st.info("請先匯入今日銷售資料")
    else:
        results = verify_tea(brews, wastes, sales, recipes)
        if not results:
            st.warning("無法計算（配方資料不足）")
        else:
            for tea, r in results.items():
                status = "✅ 正常" if r['ok'] else "⚠️ 異常"
                color = "#e8f5e9" if r['ok'] else "#ffebee"
                border = "#4CAF50" if r['ok'] else "#F44336"
                diff_text = f"+{r['diff']:.0f}" if r['diff'] >= 0 else f"{r['diff']:.0f}"
                st.markdown(f"""
                <div style='background:{color};border-left:5px solid {border};
                     border-radius:8px;padding:12px;margin:6px 0'>
                  <b>{tea}</b> {status}<br>
                  煮了 <b>{r['brewed_ml']:.0f}ml</b> ／
                  銷售消耗 <b>{r['consumed_ml']:.0f}ml</b> ／
                  報廢 <b>{r['waste_ml']:.0f}ml</b><br>
                  <span style='color:#555;font-size:0.85rem'>
                  差異：{diff_text}ml
                  {'（在合理範圍內）' if r['ok'] else '（請確認是否有漏記）'}
                  </span>
                </div>""", unsafe_allow_html=True)
