"""
🧪 測試用 — 簡易現金支出登記（不用拍照）
正式版請用「💸 現金支出」頁
測試完可以刪除這個檔案
"""
import streamlit as st
import pandas as pd
from datetime import date
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import add_cash_expense, get_cash_expenses

st.set_page_config(page_title="測試支出", page_icon="🧪", layout="centered")
st.title("🧪 測試用 — 現金支出（無照片）")
st.warning("⚠️ 這是**測試頁**，不需要上傳發票。正式上線後請刪除此檔案。")

STAFF = ["老闆", "阿芳", "阿衍", "阿展", "阿柔", "阿珍", "阿宇"]
EXPENSE_TYPES = ["進貨支付", "雜支", "預付款", "退費", "薪水", "固定支出"]

# ── 表單 ──
with st.form("test_expense", clear_on_submit=True):
    # 日期可選，預設今天
    exp_date = st.date_input("📅 日期", value=date.today())

    c1, c2 = st.columns(2)
    purpose = c1.text_input("🏷️ 用途", placeholder="例：紅茶進貨")
    amount = c2.number_input("💰 金額", min_value=0.0, step=10.0)

    c3, c4 = st.columns(2)
    handler = c3.selectbox("👤 經手人", STAFF)
    etype = c4.selectbox("📎 類型", EXPENSE_TYPES)

    note = st.text_area("📝 備註（選填）", height=70)

    submitted = st.form_submit_button("✅ 送出（不檢查照片）", type="primary",
                                       use_container_width=True)

    if submitted:
        if not purpose.strip():
            st.error("❌ 用途不能空白")
        elif amount <= 0:
            st.error("❌ 金額要 > 0")
        else:
            record = {
                "expense_date": str(exp_date),
                "expense_type": etype,
                "purpose": purpose.strip(),
                "amount": float(amount),
                "handler": handler,
                "note": note.strip() if note else None,
                "status": "approved",
                # receipt_url / detail_url 都留空
            }
            result = add_cash_expense(record)
            if result:
                st.success(f"✅ 已登記：{etype} ${amount:,.0f} ({exp_date})")
                st.rerun()
            else:
                st.error("❌ 寫入失敗")

# ── 該日記錄 ──
st.markdown("---")
view_date = st.date_input("📅 查看哪天的記錄", value=date.today(), key="view_date")
records = get_cash_expenses(str(view_date))
if records:
    rows = [{
        '類型': r.get('expense_type'),
        '用途': r.get('purpose'),
        '金額': f"${float(r.get('amount') or 0):,.0f}",
        '經手人': r.get('handler'),
        '備註': r.get('note', '') or '',
    } for r in records]
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    total = sum(float(r.get('amount') or 0) for r in records)
    st.metric(f"📊 {view_date} 支出合計", f"${total:,.0f}", f"{len(records)} 筆")
else:
    st.caption(f"{view_date} 沒有記錄")
