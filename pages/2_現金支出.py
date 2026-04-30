import streamlit as st
import pandas as pd
from datetime import date
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import add_cash_expense, get_cash_expenses, upload_expense_photo

st.set_page_config(page_title="現金支出", page_icon="💸", layout="centered")
st.title("💸 現金支出登記")

# ── 占位員工名單（之後改）──
STAFF = ["老闆", "阿芳", "阿衍", "阿展", "阿柔", "阿珍", "阿宇"]
EXPENSE_TYPES = ["進貨支付", "雜支", "預付款", "退費", "薪水", "固定支出"]

today = str(date.today())

st.caption(f"📅 今天：{today}（系統會自動帶入）")
st.markdown("---")

# ─── 表單區 ───────────────────────────────────
st.subheader("📝 新增支出")

with st.form("expense_form", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        purpose = st.text_input("🏷️ 用途（任打）", placeholder="例：紅茶進貨、油錢、垃圾袋")
        amount = st.number_input("💰 金額（元）", min_value=0.0, step=10.0, value=0.0)
    with c2:
        handler = st.selectbox("👤 經手人", STAFF)
        etype = st.selectbox("📎 類型", EXPENSE_TYPES)

    note = st.text_area("📝 備註（選填）", placeholder="例：明天早上要付", height=70)

    st.markdown("**📸 拍照存證（兩張都必填）**")
    c3, c4 = st.columns(2)
    with c3:
        receipt = st.file_uploader("發票 / 收據", type=['jpg', 'jpeg', 'png', 'pdf'],
                                   key="receipt_file")
        if receipt:
            st.image(receipt, caption="發票預覽", use_container_width=True)
    with c4:
        detail = st.file_uploader("明細 / 訂貨單", type=['jpg', 'jpeg', 'png', 'pdf'],
                                  key="detail_file")
        if detail:
            st.image(detail, caption="明細預覽", use_container_width=True)

    submitted = st.form_submit_button("✅ 送出", type="primary", use_container_width=True)

    if submitted:
        # 驗證
        errors = []
        if not purpose.strip():
            errors.append("用途不能空白")
        if amount <= 0:
            errors.append("金額要 > 0")
        if not receipt:
            errors.append("請上傳發票")
        if not detail:
            errors.append("請上傳明細")

        if errors:
            for e in errors:
                st.error(f"❌ {e}")
        else:
            with st.spinner("上傳中..."):
                # 上傳照片
                receipt_url = upload_expense_photo(receipt.getvalue(), receipt.name)
                detail_url = upload_expense_photo(detail.getvalue(), detail.name)

                if not receipt_url or not detail_url:
                    st.error("❌ 照片上傳失敗，請確認 Supabase Storage 的 expense-photos bucket 是否存在且為 Public")
                else:
                    # 寫入資料庫
                    record = {
                        "expense_date": today,
                        "expense_type": etype,
                        "purpose": purpose.strip(),
                        "amount": float(amount),
                        "handler": handler,
                        "receipt_url": receipt_url,
                        "detail_url": detail_url,
                        "note": note.strip() if note else None,
                        "status": "approved",
                    }
                    result = add_cash_expense(record)
                    if result:
                        st.success(f"✅ 已登記！{etype} ${amount:,.0f} · 經手人：{handler}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ 寫入資料庫失敗")

# ─── 今日記錄 ───────────────────────────────────
st.markdown("---")
st.subheader(f"📋 今日支出記錄")

today_records = get_cash_expenses(today)
if today_records:
    total = sum(float(r.get('amount') or 0) for r in today_records)
    st.metric("📊 今日支出合計", f"${total:,.0f}", f"{len(today_records)} 筆")

    for r in today_records:
        with st.expander(f"💵 {r.get('expense_type')} · ${float(r.get('amount') or 0):,.0f} · {r.get('purpose')}"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**經手人**：{r.get('handler') or '—'}")
                st.markdown(f"**類型**：{r.get('expense_type') or '—'}")
                st.markdown(f"**金額**：${float(r.get('amount') or 0):,.0f}")
                st.markdown(f"**用途**：{r.get('purpose') or '—'}")
                if r.get('note'):
                    st.markdown(f"**備註**：{r['note']}")
                st.caption(f"建立：{r.get('created_at', '')[:19]}")
            with c2:
                if r.get('receipt_url'):
                    st.markdown("**發票照片**")
                    st.image(r['receipt_url'], use_container_width=True)
                if r.get('detail_url'):
                    st.markdown("**明細照片**")
                    st.image(r['detail_url'], use_container_width=True)
else:
    st.caption("今天還沒有支出記錄")

# ─── 近 7 天總覽 ─────────────────────────────────
st.markdown("---")
st.subheader("📅 近期記錄（最新 50 筆）")
recent = get_cash_expenses(limit=50)
if recent:
    df = pd.DataFrame(recent)
    df = df[['expense_date', 'expense_type', 'purpose', 'amount', 'handler']].copy()
    df.columns = ['日期', '類型', '用途', '金額', '經手人']
    df['金額'] = df['金額'].apply(lambda x: f"${float(x or 0):,.0f}")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.caption("尚無記錄")
