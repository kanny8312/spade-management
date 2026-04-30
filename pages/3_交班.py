import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from io import BytesIO
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import (get_daily_report, upsert_daily_report, get_daily_reports_month,
                get_cash_expenses, get_sales_records)

st.set_page_config(page_title="交班", page_icon="🌙", layout="centered")

# ─── CSS 美化 ─────────────────────────────────
st.markdown("""
<style>
.big-num { font-size: 2rem; font-weight: 700; }
.sec-title { font-size: 1.05rem; font-weight: 600; margin-top: 8px; }
.note-box { background:#f8f9fa; border-left:4px solid #6c757d; padding:8px 12px; border-radius:6px; margin:8px 0; font-size:0.9rem; }
.cash-card { background:#f0f7ff; border:1px solid #cfe2ff; border-radius:8px; padding:12px; margin:6px 0; }
</style>
""", unsafe_allow_html=True)

st.title("🌙 交班 / 日報表")

# ─── 占位員工名單 ──
STAFF = ["老闆", "阿芳", "阿衍", "阿展", "阿柔", "阿珍", "阿宇"]

# ─── 日期 + 狀態 ──
c1, c2 = st.columns([2, 1])
with c1:
    selected_date = st.date_input("📅 日期", value=date.today(), max_value=date.today())
report_date_str = str(selected_date)

existing = get_daily_report(report_date_str) or {}
status = existing.get('status', 'draft')
with c2:
    st.markdown(f"<div style='padding-top:28px'>"
                f"{'🔒 <b>已交班</b>' if status == 'closed' else '🟡 <b>交班中</b>'}"
                f"</div>", unsafe_allow_html=True)

st.markdown("---")

# ─── 自動帶昨日結餘當期初現金 ──
def _yesterday_closing(date_str):
    """取得昨日交班的『實際盤點現金』當今天期初現金"""
    yest = (datetime.fromisoformat(date_str) - timedelta(days=1)).date().isoformat()
    y = get_daily_report(yest)
    if y and y.get('actual_cash') is not None:
        return float(y['actual_cash'])
    return None

yesterday_cash = _yesterday_closing(report_date_str)

# ═══════════════════════════════════════════════
# 1️⃣ 匯入付款方式彙總（只要這 1 個）
# ═══════════════════════════════════════════════
with st.expander("1️⃣ 匯入付款方式彙總（自動填收入）",
                 expanded=not bool(existing)):
    st.caption("從肚肚匯出「付款方式彙總表」上傳，現金/LINE/外送會自動帶")
    pay_csv = st.file_uploader("💳 付款方式彙總", type=['csv'], key="pay_csv")

    if 'auto_data' not in st.session_state:
        st.session_state.auto_data = {}

    if pay_csv and st.button("📥 解析", use_container_width=True):
        auto = {}
        try:
            df = pd.read_csv(pay_csv, encoding='utf-8-sig', header=3)
            # 找「金額」那行（含「金額」關鍵字）
            row = df[df.iloc[:, 0].astype(str).str.contains('金額', na=False) &
                     ~df.iloc[:, 0].astype(str).str.contains('銷售量', na=False)]
            # 優先 Total，其次第一筆
            total_row = row[row.iloc[:, 0].astype(str).str.contains('Total', case=False, na=False)]
            if len(total_row) > 0:
                r = total_row.iloc[0]
            elif len(row) > 0:
                r = row.iloc[0]
            else:
                r = None

            if r is not None:
                def to_num(v):
                    try:
                        return float(str(v).replace(',', '').strip() or 0)
                    except:
                        return 0

                # 把所有名稱含關鍵字的欄位都加總（解決 Line Pay vs LINE Pay 重複欄位）
                def sum_cols(keyword):
                    total = 0
                    for col in df.columns:
                        if keyword.lower() in str(col).lower():
                            total += to_num(r.get(col, 0))
                    return total

                auto['cash_revenue'] = sum_cols('現金')
                auto['linepay_revenue'] = sum_cols('line pay')
                auto['ubereats_revenue'] = sum_cols('ubereats')
                auto['foodpanda_revenue'] = sum_cols('foodpanda')
                auto['pos_total'] = sum_cols('總計') or sum_cols('total')

                st.success(f"✅ 解析完成：現金 ${auto['cash_revenue']:,.0f}、"
                           f"LINE ${auto['linepay_revenue']:,.0f}、"
                           f"UE ${auto['ubereats_revenue']:,.0f}、"
                           f"FP ${auto['foodpanda_revenue']:,.0f}、"
                           f"POS ${auto['pos_total']:,.0f}")
            else:
                st.warning("找不到金額列，請確認 CSV 格式")
                st.write("欄位列表：", list(df.columns))
        except Exception as e:
            st.error(f"解析失敗：{e}")
        st.session_state.auto_data = auto

auto = st.session_state.get('auto_data', {})

def _get_val(field, default=0):
    """優先順序：已存交班 > CSV解析 > 預設"""
    if existing.get(field) is not None:
        return float(existing[field])
    if field in auto:
        return float(auto[field])
    return default

# ═══════════════════════════════════════════════
# 2️⃣ 收入（只顯示，不可編輯）
# ═══════════════════════════════════════════════
with st.expander("2️⃣ 💰 今日收入（自動，不可改）", expanded=True):
    cash_revenue = float(_get_val('cash_revenue'))
    linepay_revenue = float(_get_val('linepay_revenue'))
    ubereats_revenue = float(_get_val('ubereats_revenue'))
    foodpanda_revenue = float(_get_val('foodpanda_revenue'))
    other_revenue = float(_get_val('other_revenue'))
    pos_total = float(_get_val('pos_total'))

    if cash_revenue + linepay_revenue + ubereats_revenue + foodpanda_revenue == 0:
        st.warning("⚠️ 還沒匯入「付款方式彙總表」CSV，請先到上面匯入")
    else:
        c1, c2 = st.columns(2)
        c1.metric("💵 現金", f"${cash_revenue:,.0f}")
        c2.metric("📱 LINE Pay", f"${linepay_revenue:,.0f}")
        c1.metric("🛵 UberEats", f"${ubereats_revenue:,.0f}")
        c2.metric("🛵 foodpanda", f"${foodpanda_revenue:,.0f}")
        c1.metric("📊 POS 總額", f"${pos_total:,.0f}")

        total_revenue = (cash_revenue + linepay_revenue + ubereats_revenue
                         + foodpanda_revenue + other_revenue)
        st.markdown(f"<div class='cash-card'><span class='sec-title'>收入合計：</span>"
                    f"<span class='big-num'>${total_revenue:,.0f}</span></div>",
                    unsafe_allow_html=True)
        if pos_total > 0 and abs(total_revenue - pos_total) > 1:
            st.warning(f"⚠️ 收入合計 vs POS 差 ${total_revenue-pos_total:+,.0f}")

# ═══════════════════════════════════════════════
# 3️⃣ 現金支出
# ═══════════════════════════════════════════════
with st.expander("3️⃣ 💸 今日現金支出（從支出頁帶入）", expanded=True):
    today_expenses = [
        e for e in get_cash_expenses(report_date_str)
        if e.get('expense_type') != '預付款'
    ]
    if today_expenses:
        rows = [{
            '類型': e.get('expense_type'),
            '用途': e.get('purpose'),
            '金額': float(e.get('amount') or 0),
            '經手人': e.get('handler'),
        } for e in today_expenses]
        df = pd.DataFrame(rows)
        df['金額'] = df['金額'].apply(lambda x: f"${x:,.0f}")
        st.dataframe(df, use_container_width=True, hide_index=True)
        total_expense = sum(float(e.get('amount') or 0) for e in today_expenses)
        st.markdown(f"<div class='cash-card'>"
                    f"<span class='sec-title'>支出合計：</span>"
                    f"<span class='big-num'>−${total_expense:,.0f}</span></div>",
                    unsafe_allow_html=True)
    else:
        total_expense = 0
        st.caption("今天還沒有現金支出記錄。請到「💸 現金支出」頁登記")

# ═══════════════════════════════════════════════
# 4️⃣ 預付款
# ═══════════════════════════════════════════════
with st.expander("4️⃣ 🔮 預付款（明天用）", expanded=True):
    today_prepays = [
        e for e in get_cash_expenses(report_date_str)
        if e.get('expense_type') == '預付款'
    ]
    if today_prepays:
        rows = [{
            '用途': e.get('purpose'),
            '金額': float(e.get('amount') or 0),
            '經手人': e.get('handler'),
        } for e in today_prepays]
        df = pd.DataFrame(rows)
        df['金額'] = df['金額'].apply(lambda x: f"${x:,.0f}")
        st.dataframe(df, use_container_width=True, hide_index=True)
        total_prepay = sum(float(e.get('amount') or 0) for e in today_prepays)
        st.markdown(f"<div class='cash-card'>"
                    f"<span class='sec-title'>預付合計：</span>"
                    f"<span class='big-num'>−${total_prepay:,.0f}</span></div>",
                    unsafe_allow_html=True)
    else:
        total_prepay = 0
        st.caption("今天沒有預付款。要登記請到「💸 現金支出」選「預付款」類型")

# ═══════════════════════════════════════════════
# 5️⃣ 點錢（千百鈔）
# ═══════════════════════════════════════════════
with st.expander("5️⃣ 🪙 點錢（只算千百鈔）", expanded=True):
    c1, c2 = st.columns(2)
    cash_thousand_count = c1.number_input(
        "千鈔張數", min_value=0, step=1,
        value=int(_get_val('cash_thousand_count', 0)),
        key="cash_thousand_count"
    )
    cash_hundred_count = c2.number_input(
        "百鈔張數", min_value=0, step=1,
        value=int(_get_val('cash_hundred_count', 0)),
        key="cash_hundred_count"
    )
    actual_cash = cash_thousand_count * 1000 + cash_hundred_count * 100
    c1.markdown(f"× 1000 = **${cash_thousand_count*1000:,.0f}**")
    c2.markdown(f"× 100 = **${cash_hundred_count*100:,.0f}**")
    st.markdown(f"<div class='cash-card'>"
                f"<span class='sec-title'>實際盤點現金：</span>"
                f"<span class='big-num' style='color:#0d6efd'>${actual_cash:,.0f}</span>"
                f"</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
# 6️⃣ 現金對帳
# ═══════════════════════════════════════════════
with st.expander("6️⃣ ✅ 現金對帳", expanded=True):
    # 期初現金：優先 已存交班 > 昨日結餘 > 預設 24449（首次設定）
    INITIAL_OPENING = 11990.0
    if existing.get('opening_cash') is not None:
        default_opening = float(existing['opening_cash'])
    elif yesterday_cash is not None:
        default_opening = float(yesterday_cash)
        st.info(f"💡 自動帶入昨日（{(datetime.fromisoformat(report_date_str)-timedelta(days=1)).date()}）"
                f"結餘 **${yesterday_cash:,.0f}** 當期初現金")
    else:
        default_opening = INITIAL_OPENING
        st.info(f"💡 第一天使用，預設期初現金 **${INITIAL_OPENING:,.0f}**（之後會自動串接昨日結餘）")

    opening_cash = st.number_input(
        "期初現金（留存金）", value=default_opening,
        step=10.0, key="opening_cash"
    )
    expected_cash = opening_cash + cash_revenue - total_expense - total_prepay
    cash_diff = actual_cash - expected_cash

    st.markdown(f"""
    <div class='cash-card'>
      <table style='width:100%; font-size:0.95rem'>
        <tr><td>期初現金</td><td style='text-align:right'>${opening_cash:,.0f}</td></tr>
        <tr><td style='color:green'>+ 今日現金收入</td><td style='text-align:right;color:green'>+${cash_revenue:,.0f}</td></tr>
        <tr><td style='color:red'>− 現金支出</td><td style='text-align:right;color:red'>−${total_expense:,.0f}</td></tr>
        <tr><td style='color:red'>− 預付款</td><td style='text-align:right;color:red'>−${total_prepay:,.0f}</td></tr>
        <tr style='border-top:2px solid #999'><td><b>應有現金</b></td><td style='text-align:right'><b>${expected_cash:,.0f}</b></td></tr>
        <tr><td>實際盤點</td><td style='text-align:right'>${actual_cash:,.0f}</td></tr>
      </table>
    </div>
    """, unsafe_allow_html=True)

    # 差額紅綠燈
    if abs(cash_diff) <= 100:
        st.success(f"💚 差額 ${cash_diff:+,.0f}（在 ±$100 內，正常）")
    elif abs(cash_diff) <= 500:
        st.warning(f"🟡 差額 ${cash_diff:+,.0f}（請填差異原因）")
    else:
        st.error(f"🔴 差額 ${cash_diff:+,.0f}（超過 $500，務必確認）")

# ═══════════════════════════════════════════════
# 7️⃣ 文字 / 簽名
# ═══════════════════════════════════════════════
with st.expander("7️⃣ 📄 作廢發票 / 差異原因 / 備註", expanded=False):
    void_invoices = st.text_area("作廢發票編號（多筆用逗號隔開）",
                                  value=existing.get('void_invoices', '') or '',
                                  placeholder="YZ-23054012, YZ-23054013")
    diff_reason = st.text_area("差異原因（差額不為 0 時填）",
                                value=existing.get('diff_reason', '') or '',
                                placeholder="例：員工試喝、找錯零")
    note = st.text_area("備註",
                         value=existing.get('note', '') or '',
                         height=70)

with st.expander("8️⃣ 👤 交班人", expanded=False):
    handler_default = STAFF.index(existing.get('handler')) if existing.get('handler') in STAFF else 0
    handler = st.selectbox("交班人", STAFF, index=handler_default)

# ═══════════════════════════════════════════════
# 儲存按鈕
# ═══════════════════════════════════════════════
st.markdown("---")
record = {
    "report_date": report_date_str,
    "cash_revenue": cash_revenue,
    "linepay_revenue": linepay_revenue,
    "ubereats_revenue": ubereats_revenue,
    "foodpanda_revenue": foodpanda_revenue,
    "other_revenue": other_revenue,
    "pos_total": pos_total,
    "opening_cash": opening_cash,
    "cash_thousand_count": cash_thousand_count,
    "cash_hundred_count": cash_hundred_count,
    "actual_cash": actual_cash,
    "expected_cash": expected_cash,
    "cash_diff": cash_diff,
    "void_invoices": void_invoices.strip() or None,
    "diff_reason": diff_reason.strip() or None,
    "note": note.strip() or None,
    "handler": handler,
}

c1, c2 = st.columns(2)
if c1.button("💾 儲存草稿", use_container_width=True):
    record["status"] = "draft"
    if upsert_daily_report(record):
        st.success("✅ 已儲存草稿")
        st.rerun()
    else:
        st.error("❌ 儲存失敗")

if c2.button("🔒 完成交班", use_container_width=True, type="primary"):
    record["status"] = "closed"
    record["closed_at"] = datetime.utcnow().isoformat()
    if upsert_daily_report(record):
        st.success("✅ 已完成交班！")
        st.balloons()
        st.rerun()
    else:
        st.error("❌ 儲存失敗")

# ═══════════════════════════════════════════════
# 匯出
# ═══════════════════════════════════════════════
st.markdown("---")
st.subheader("📤 匯出 Excel")

def make_daily_excel(rec):
    """產生單日日報 Excel"""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        # 主表
        rows = [
            ["十杯茶飲店永和店營業日報表", ""],
            ["日期", rec['report_date']],
            ["交班人", rec.get('handler', '')],
            ["", ""],
            ["【今日收入】", ""],
            ["現金營業額(A)", f"{rec.get('cash_revenue', 0):,.0f}"],
            ["LINE Pay 營業額(L)", f"{rec.get('linepay_revenue', 0):,.0f}"],
            ["UberEats 營業額", f"{rec.get('ubereats_revenue', 0):,.0f}"],
            ["foodpanda 營業額", f"{rec.get('foodpanda_revenue', 0):,.0f}"],
            ["FP/UE 合計(FU)",
             f"{rec.get('ubereats_revenue', 0) + rec.get('foodpanda_revenue', 0):,.0f}"],
            ["其他收入", f"{rec.get('other_revenue', 0):,.0f}"],
            ["POS營業額(B)", f"{rec.get('pos_total', 0):,.0f}"],
            ["差值(C=A+L+FU-B)",
             f"{(rec.get('cash_revenue', 0)+rec.get('linepay_revenue', 0)+rec.get('ubereats_revenue', 0)+rec.get('foodpanda_revenue', 0)-rec.get('pos_total', 0)):,.0f}"],
            ["", ""],
            ["【現金對帳】", ""],
            ["期初現金（留存金）", f"{rec.get('opening_cash', 0):,.0f}"],
            ["千鈔張數", rec.get('cash_thousand_count', 0)],
            ["百鈔張數", rec.get('cash_hundred_count', 0)],
            ["實際盤點現金", f"{rec.get('actual_cash', 0):,.0f}"],
            ["應有現金", f"{rec.get('expected_cash', 0):,.0f}"],
            ["差額", f"{rec.get('cash_diff', 0):+,.0f}"],
            ["差異原因", rec.get('diff_reason', '') or ''],
            ["", ""],
            ["【其他】", ""],
            ["作廢發票", rec.get('void_invoices', '') or ''],
            ["備註", rec.get('note', '') or ''],
        ]
        df_main = pd.DataFrame(rows, columns=['項目', '內容'])
        df_main.to_excel(writer, sheet_name='日報', index=False)

        # 支出明細
        exps = get_cash_expenses(rec['report_date'])
        if exps:
            df_e = pd.DataFrame([{
                '類型': e.get('expense_type'),
                '用途': e.get('purpose'),
                '金額': float(e.get('amount') or 0),
                '經手人': e.get('handler'),
                '備註': e.get('note', '') or '',
            } for e in exps])
            df_e.to_excel(writer, sheet_name='支出明細', index=False)
    return buf.getvalue()

def make_monthly_excel(year, month):
    buf = BytesIO()
    reports = get_daily_reports_month(year, month)
    rows = []
    for r in reports:
        rows.append({
            '日期': r.get('report_date'),
            '營業額': r.get('pos_total', 0),
            '現金': r.get('cash_revenue', 0),
            'LINE Pay': r.get('linepay_revenue', 0),
            'UberEats': r.get('ubereats_revenue', 0),
            'foodpanda': r.get('foodpanda_revenue', 0),
            '期初現金': r.get('opening_cash', 0),
            '應有現金': r.get('expected_cash', 0),
            '實際現金': r.get('actual_cash', 0),
            '差額': r.get('cash_diff', 0),
            '差異原因': r.get('diff_reason', '') or '',
            '交班人': r.get('handler', ''),
            '狀態': '已交班' if r.get('status') == 'closed' else '草稿',
        })
    if rows:
        df = pd.DataFrame(rows)
        # 加合計列
        totals = {col: df[col].sum() if df[col].dtype.kind in 'biufc' else ''
                  for col in df.columns}
        totals['日期'] = '合計'
        df = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
    else:
        df = pd.DataFrame([{'訊息': '本月無記錄'}])
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=f"{year}-{month:02d}", index=False)
    return buf.getvalue()

c1, c2 = st.columns(2)
if record:
    daily_xlsx = make_daily_excel(record)
    c1.download_button(
        f"📅 匯出 {report_date_str} 日報",
        data=daily_xlsx,
        file_name=f"日報_{report_date_str}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with c2:
    today = date.today()
    target_year = st.number_input("年", 2024, 2030, today.year, key="exp_year",
                                   label_visibility="collapsed")
    target_month = st.number_input("月", 1, 12, today.month, key="exp_month",
                                    label_visibility="collapsed")
    monthly_xlsx = make_monthly_excel(int(target_year), int(target_month))
    st.download_button(
        f"📅 匯出 {int(target_year)}/{int(target_month)} 月報",
        data=monthly_xlsx,
        file_name=f"月報_{int(target_year)}-{int(target_month):02d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
