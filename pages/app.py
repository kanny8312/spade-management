import streamlit as st
from datetime import date
from db import get_materials

st.set_page_config(page_title="十杯茶飲管理", page_icon="🧋", layout="centered")

st.markdown("""
<style>
div[data-testid="stAppViewContainer"] { max-width: 500px; margin: auto; }
.card { border-radius:10px; padding:14px; margin:6px 0; }
.card-ok   { background:#e8f5e9; border-left:5px solid #4CAF50; }
.card-warn { background:#fff8e1; border-left:5px solid #FF9800; }
.card-danger{ background:#ffebee; border-left:5px solid #F44336; }
.big-num { font-size:1.8rem; font-weight:bold; }
</style>
""", unsafe_allow_html=True)

st.title("🧋 十杯茶飲管理")
st.caption(f"📅 {date.today().strftime('%Y / %m / %d')}")

materials = get_materials()
if not materials:
    st.error("⚠️ 請先執行 supabase_setup.sql 建立資料庫！")
    st.stop()

# 類別篩選
cats = ['全部'] + sorted(set(m['category'] for m in materials))
col1, col2 = st.columns([2, 1])
with col1:
    selected_cat = st.selectbox("📂 類別", cats, label_visibility="collapsed")

# 材料導航（左右箭頭）
filtered = [m for m in materials if selected_cat == '全部' or m['category'] == selected_cat]

if 'mat_idx' not in st.session_state:
    st.session_state.mat_idx = 0
if st.session_state.mat_idx >= len(filtered):
    st.session_state.mat_idx = 0

idx = st.session_state.mat_idx
mat = filtered[idx]

st.markdown("---")
c1, c2, c3 = st.columns([1, 4, 1])
with c1:
    if st.button("◀", use_container_width=True, key="prev"):
        st.session_state.mat_idx = (idx - 1) % len(filtered)
        st.rerun()
with c2:
    st.markdown(f"<div style='text-align:center'><b style='font-size:1.2rem'>{mat['name']}</b><br>"
                f"<span style='color:gray;font-size:0.85rem'>{idx+1} / {len(filtered)} · {mat['category']}</span></div>",
                unsafe_allow_html=True)
with c3:
    if st.button("▶", use_container_width=True, key="next"):
        st.session_state.mat_idx = (idx + 1) % len(filtered)
        st.rerun()

# 選中的原料詳細
stock = float(mat['current_stock'] or 0)
safety = float(mat['safety_stock'] or 0)
ratio = stock / safety if safety > 0 else 2

if ratio <= 0.5:
    cls, status = "card-danger", "🔴 緊急補貨"
elif ratio <= 1.0:
    cls, status = "card-warn", "🟡 低於安全庫存"
else:
    cls, status = "card-ok", "🟢 正常"

st.markdown(f"""
<div class='card {cls}'>
  <div style='display:flex;justify-content:space-between;align-items:center'>
    <span style='font-size:1.1rem;font-weight:bold'>{mat['name']}</span>
    <span>{status}</span>
  </div>
  <div class='big-num'>{stock:,.0f} <span style='font-size:1rem;font-weight:normal'>{mat['unit']}</span></div>
  <div style='color:#666;font-size:0.85rem'>安全庫存：{safety:,.0f} {mat['unit']}</div>
</div>
""", unsafe_allow_html=True)

# 總覽列表
st.markdown("---")
st.markdown("### 📋 庫存總覽")

low = [m for m in materials if float(m['current_stock'] or 0) <= float(m['safety_stock'] or 0)]
if low:
    st.warning(f"⚠️ {len(low)} 項低於安全庫存！")

for m in filtered:
    s = float(m['current_stock'] or 0)
    sf = float(m['safety_stock'] or 0)
    r = s / sf if sf > 0 else 2
    if r <= 0.5:
        cls, ico = "card-danger", "🔴"
    elif r <= 1.0:
        cls, ico = "card-warn", "🟡"
    else:
        cls, ico = "card-ok", "🟢"
    st.markdown(f"""
    <div class='card {cls}'>
      <div style='display:flex;justify-content:space-between'>
        <b>{m['name']}</b>
        <span>{ico} {s:,.0f} {m['unit']}</span>
      </div>
      <div style='color:#888;font-size:0.8rem'>安全庫存：{sf:,.0f} {m['unit']}</div>
    </div>""", unsafe_allow_html=True)
