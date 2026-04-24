import streamlit as st
import pandas as pd
import re
from datetime import date
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import (get_tea_specs, get_brew_records, add_brew_record,
                get_sales_records, import_sales, get_waste_records,
                add_waste_record, get_materials, get_recipes,
                deduct_stock, get_material)
from calculations import verify_tea

# ─── 扣庫存規則（待優化請改這裡）─────────────────────
# 商品分析：依杯型扣紙杯、吸管、封膜
PRODUCT_RULES = {
    'L': [('700ml紙杯', 1), ('粗吸管', 1), ('封膜', 1)],
    'M': [('500ml紙杯', 1), ('細吸管', 1), ('封膜', 1)],
}

# 熱門標籤：依標籤扣對應原料
# ⚠️ 待優化：牛奶、茶凍、雪霜的 L/M 量目前用平均值，等 POS 標籤分 L/M 後再修正
TAG_RULES = {
    # 配料（生重，每份）
    '珍珠':     [('珍珠(生)', 30)],   # ⚠️ 待優化：實際秤一平匙幾 g
    'QQ':       [('QQ(生)',   20)],   # ⚠️ 待優化：實際秤一匙幾 g
    # 牛奶（ml/杯，平均值）
    '初鹿':     [('初鹿', 175)],
    '主恩':     [('主恩', 175)],
    '大山':     [('大山', 175)],
    '橋頭':     [('橋頭', 175)],
    '柳營':     [('柳營', 175)],
    # 茶凍（ml/杯，平均值）
    '桂花清凍': [('桂花清凍', 190)],
    '鐵觀音凍': [('鐵觀音凍', 190)],
    '綠茶凍':   [('綠茶凍',   190)],
}

def detect_size(name):
    """從商品名稱判斷杯型 L 或 M"""
    n = str(name)
    if '(L)' in n or 'L)' in n.upper() or n.endswith('L'):
        return 'L'
    if '(M)' in n or 'M)' in n.upper() or n.endswith('M'):
        return 'M'
    return None

def extract_date_from_filename(fname):
    """從檔名抓日期：商品分析_2026年04月24日-...csv → 2026-04-24"""
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', fname)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return None

def is_product_csv(df):
    """判斷是不是商品分析 CSV"""
    cols = set(df.columns)
    return '類別' in cols or '類型' in cols

def is_tag_csv(df):
    """判斷是不是熱門標籤 CSV"""
    cols = set(df.columns)
    return '名稱' in cols and '數量' in cols and '類別' not in cols

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
    st.subheader("📥 匯入肚肚銷售（兩個 CSV）")
    st.caption("1️⃣ 商品分析（銷售）  2️⃣ 熱門標籤（去冰、珍珠、牛奶等）")

    with st.expander("⚠️ 待優化細節（記錄中）"):
        st.markdown("""
        - 🟤 **珍珠 30g/份、QQ 20g/份**：先用估值，之後實際秤一匙再修正
        - 🥛 **牛奶 175ml/杯**：用 L/M 平均值，等 POS 標籤改成 `L初鹿`/`M初鹿` 後分開算
        - 🍵 **茶凍 190ml/杯**：同上
        - 🍯 **糖、雪霜、茶葉 g**：第一版**不扣**，第二版再做
        """)

    c1, c2 = st.columns(2)
    with c1:
        sales_file = st.file_uploader("📊 商品分析 CSV", type=['csv'], key="sales")
    with c2:
        tag_file = st.file_uploader("🏷️ 熱門標籤 CSV", type=['csv'], key="tags")

    if sales_file or tag_file:
        # ── 日期檢查 ──
        files_to_check = [(f.name, extract_date_from_filename(f.name))
                          for f in [sales_file, tag_file] if f]
        date_ok = True
        for fname, fdate in files_to_check:
            if fdate is None:
                st.warning(f"⚠️ 無法從檔名抓日期：{fname}")
            elif fdate != today:
                st.error(f"❌ 檔案日期 {fdate} 不是今天 ({today})：{fname}")
                date_ok = False
            else:
                st.success(f"✅ {fname} 日期正確：{fdate}")

        # ── 解析兩個 CSV ──
        sales_df = None
        tag_df = None
        try:
            if sales_file:
                sales_df = pd.read_csv(sales_file, encoding='utf-8-sig')
                if not is_product_csv(sales_df):
                    st.warning("⚠️ 第 1 個檔案看起來不是商品分析（少了「類別」欄位）")
            if tag_file:
                tag_df = pd.read_csv(tag_file, encoding='utf-8-sig')
                if not is_tag_csv(tag_df):
                    st.warning("⚠️ 第 2 個檔案看起來不是熱門標籤")
        except Exception as e:
            st.error(f"讀取失敗：{e}")
            st.stop()

        # ── 預計扣料計算 ──
        deductions = {}  # {material_name: total_qty}
        skipped_products = []
        skipped_tags = []
        sales_records = []

        # 商品分析
        if sales_df is not None:
            for _, row in sales_df.iterrows():
                name = str(row.get('名稱', '')).strip()
                if name in ('', '小計', '合計', 'nan', '名稱'):
                    continue
                try:
                    qty = int(float(str(row.get('數量', 0)).replace(',', '')))
                except:
                    continue
                if qty <= 0:
                    continue
                size = detect_size(name)
                revenue = 0
                try:
                    revenue = float(str(row.get('總額', 0)).replace(',', ''))
                except:
                    pass
                sales_records.append({
                    "sale_date": today, "product_name": name,
                    "size": size or '', "quantity": qty, "revenue": revenue
                })
                if size and size in PRODUCT_RULES:
                    for mat, per in PRODUCT_RULES[size]:
                        deductions[mat] = deductions.get(mat, 0) + per * qty
                else:
                    skipped_products.append((name, qty))

        # 熱門標籤
        if tag_df is not None:
            for _, row in tag_df.iterrows():
                tname = str(row.get('名稱', '')).strip()
                if tname in ('', '小計', '合計', 'nan', '名稱'):
                    continue
                try:
                    qty = int(float(str(row.get('數量', 0)).replace(',', '')))
                except:
                    continue
                if qty <= 0:
                    continue
                # 比對標籤關鍵字
                matched = False
                for keyword, rules in TAG_RULES.items():
                    if keyword in tname:
                        for mat, per in rules:
                            deductions[mat] = deductions.get(mat, 0) + per * qty
                        matched = True
                        break
                if not matched:
                    skipped_tags.append((tname, qty))

        # ── 顯示扣料計畫 ──
        st.markdown("---")
        st.markdown("### 📦 預計扣庫存")
        if deductions:
            # 確認原料是否存在
            mats = {m['name']: m for m in get_materials()}
            rows = []
            missing = []
            for mname, qty in sorted(deductions.items()):
                if mname in mats:
                    cur = float(mats[mname]['current_stock'] or 0)
                    after = cur - qty
                    rows.append({
                        '品項': mname, '單位': mats[mname]['unit'],
                        '目前': f"{cur:,.0f}", '扣除': f"-{qty:,.0f}",
                        '扣後': f"{after:,.0f}"
                    })
                else:
                    missing.append((mname, qty))
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            if missing:
                st.error(f"❌ 找不到以下品項，請到 Supabase raw_materials 確認名稱（會被略過）：")
                st.write(missing)
        else:
            st.info("沒有可扣的庫存（可能兩個檔都沒上傳，或都沒比對到規則）")

        if skipped_products:
            with st.expander(f"⚠️ 略過的商品 ({len(skipped_products)} 筆，無法判斷 L/M)"):
                st.write(skipped_products)
        if skipped_tags:
            with st.expander(f"ℹ️ 沒比對到規則的標籤 ({len(skipped_tags)} 筆)"):
                st.write(skipped_tags)

        # ── 執行 ──
        if date_ok and (deductions or sales_records):
            if st.button("✅ 確認匯入並扣庫存", type="primary", use_container_width=True):
                # 1. 寫銷售記錄
                if sales_records:
                    import_sales(sales_records)
                # 2. 扣庫存
                ok_count = 0
                for mname, qty in deductions.items():
                    if deduct_stock(mname, qty):
                        ok_count += 1
                st.success(f"✅ 已匯入 {len(sales_records)} 筆銷售；扣除 {ok_count} 項庫存（允許負數）")
                st.balloons()
                st.rerun()

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
