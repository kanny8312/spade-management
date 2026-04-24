import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from utils.db import get_materials, add_stock_in, save_order

st.set_page_config(page_title="訂貨進貨", page_icon="🛒", layout="centered")
st.title("🛒 訂貨 & 進貨")

tab1, tab2 = st.tabs(["📝 建立訂單", "📦 登記進貨"])

# ─── Tab1: 訂貨 ──────────────────────────────────
with tab1:
    st.subheader("建立訂貨單")
    materials = get_materials()
    cats = sorted(set(m['category'] for m in materials))
    selected_cat = st.selectbox("篩選類別", ['全部'] + cats, key="order_cat")
    filtered = [m for m in materials if selected_cat == '全部' or m['category'] == selected_cat]

    order_items = {}
    st.markdown("**填入訂購數量（0表示不訂）：**")
    for m in filtered:
        col1, col2 = st.columns([3, 2])
        with col1:
            stock = float(m['current_stock'] or 0)
            safety = float(m['safety_stock'] or 0)
            ico = "🔴" if stock <= safety * 0.5 else ("🟡" if stock <= safety else "🟢")
            st.markdown(f"{ico} **{m['name']}** ({m['unit']})<br>"
                        f"<span style='color:gray;font-size:0.8rem'>庫存：{stock:,.0f}</span>",
                        unsafe_allow_html=True)
        with col2:
            qty = st.number_input(m['unit'], min_value=0.0, step=1.0,
                                  key=f"order_{m['name']}", label_visibility="collapsed")
        order_items[m['name']] = {'qty': qty, 'unit': m['unit']}

    active_orders = {k: v for k, v in order_items.items() if v['qty'] > 0}

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 儲存訂單", use_container_width=True) and active_orders:
            save_order(str(date.today()), active_orders)
            st.success("訂單已儲存！")

    with col2:
        if st.button("🖼️ 匯出圖片", use_container_width=True) and active_orders:
            img = _make_order_image(active_orders)
            buf = BytesIO()
            img.save(buf, format="PNG")
            st.download_button("⬇️ 下載訂貨單圖片", buf.getvalue(),
                               file_name=f"訂貨單_{date.today()}.png", mime="image/png")

    if active_orders:
        st.markdown("---")
        st.markdown("**本次訂購清單：**")
        for k, v in active_orders.items():
            st.write(f"• {k}：{v['qty']:,.0f} {v['unit']}")


def _make_order_image(items: dict) -> Image.Image:
    title = f"十杯茶飲  訂貨單  {date.today()}"
    rows = list(items.items())
    line_h = 40
    padding = 30
    header_h = 80
    footer_h = 30
    width = 600
    height = header_h + len(rows) * line_h + padding * 2 + footer_h

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 22)
        font_body = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 18)
        font_small = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 14)
    except Exception:
        font_title = font_body = font_small = ImageFont.load_default()

    # 標題
    draw.rectangle([0, 0, width, header_h], fill="#1a237e")
    draw.text((padding, 15), title, fill="white", font=font_title)
    draw.text((padding, 50), f"建單時間：{date.today()}", fill="#90caf9", font=font_small)

    # 表格標頭
    y = header_h + padding
    draw.text((padding, y), "品項", fill="#333", font=font_body)
    draw.text((350, y), "數量", fill="#333", font=font_body)
    draw.text((450, y), "單位", fill="#333", font=font_body)
    y += line_h
    draw.line([(padding, y-5), (width-padding, y-5)], fill="#ccc", width=1)

    for i, (name, v) in enumerate(rows):
        bg = "#f5f5f5" if i % 2 == 0 else "white"
        draw.rectangle([padding-5, y-5, width-padding+5, y+line_h-10], fill=bg)
        draw.text((padding, y), name, fill="#222", font=font_body)
        draw.text((350, y), f"{v['qty']:,.0f}", fill="#1565c0", font=font_body)
        draw.text((450, y), v['unit'], fill="#555", font=font_body)
        y += line_h

    draw.line([(padding, y), (width-padding, y)], fill="#ccc", width=1)
    y += 10
    draw.text((padding, y), f"共 {len(rows)} 項", fill="#888", font=font_small)

    return img


# ─── Tab2: 進貨 ──────────────────────────────────
with tab2:
    st.subheader("登記到貨")
    st.caption("貨到了在這裡輸入，庫存會自動增加")

    materials = get_materials()
    mat_names = [m['name'] for m in materials]
    mat_units = {m['name']: m['unit'] for m in materials}

    with st.form("stock_in_form"):
        mat = st.selectbox("品項", mat_names, key="si_mat")
        unit = mat_units.get(mat, '')
        qty = st.number_input(f"到貨數量 ({unit})", min_value=0.0, step=1.0)
        if st.form_submit_button("✅ 確認進貨"):
            if qty > 0:
                add_stock_in(mat, qty)
                st.success(f"✅ {mat} 進貨 {qty:,.0f} {unit}，庫存已更新！")
                st.rerun()
