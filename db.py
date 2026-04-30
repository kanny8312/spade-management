import streamlit as st
import httpx
from datetime import datetime

def _headers():
    key = st.secrets["SUPABASE_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def _url(table):
    return f"{st.secrets['SUPABASE_URL'].rstrip('/')}/rest/v1/{table}"

def _get(table, params=None):
    try:
        r = httpx.get(_url(table), headers=_headers(), params=params or {})
        if r.status_code == 200:
            return r.json()
        return []
    except Exception:
        return []

def _post(table, data):
    try:
        r = httpx.post(_url(table), headers=_headers(), json=data)
        return r.json() if r.status_code in (200, 201) else None
    except Exception:
        return None

def _patch(table, data, eq_filter):
    try:
        params = {k: f"eq.{v}" for k, v in eq_filter.items()}
        r = httpx.patch(_url(table), headers=_headers(), params=params, json=data)
        return r.status_code in (200, 204)
    except Exception:
        return False

# ── 原物料 ──────────────────────────────────────
def get_materials():
    return _get("raw_materials", {"order": "category,name"})

def get_material(name):
    results = _get("raw_materials", {"name": f"eq.{name}"})
    return results[0] if results else None

def update_stock(name, new_stock, note="盤點調整"):
    m = get_material(name)
    old_stock = float(m["current_stock"] or 0) if m else 0
    _patch("raw_materials", {
        "current_stock": new_stock,
        "updated_at": datetime.utcnow().isoformat()
    }, {"name": name})
    _post("inventory_logs", {
        "material_name": name,
        "old_stock": old_stock,
        "new_stock": new_stock,
        "difference": float(new_stock) - old_stock,
        "note": note
    })

def update_safety_stock(name, val):
    _patch("raw_materials", {"safety_stock": val}, {"name": name})

def add_stock_in(name, quantity):
    m = get_material(name)
    if m:
        new_stock = float(m["current_stock"] or 0) + float(quantity)
        _patch("raw_materials", {
            "current_stock": new_stock,
            "updated_at": datetime.utcnow().isoformat()
        }, {"name": name})
        _post("stock_in_records", {
            "material_name": name,
            "quantity": quantity,
            "unit": m["unit"]
        })

def deduct_stock(name, quantity):
    """扣除庫存，允許扣到負數（用於銷售扣料）"""
    m = get_material(name)
    if m:
        new_stock = float(m["current_stock"] or 0) - float(quantity)
        _patch("raw_materials", {"current_stock": new_stock}, {"name": name})
        return True
    return False

# ── 茶葉規格 ─────────────────────────────────────
def get_tea_specs():
    return _get("tea_specs")

def get_recipes():
    return _get("product_recipes")

# ── 煮茶記錄 ─────────────────────────────────────
def get_brew_records(date_str):
    return _get("brew_records", {"record_date": f"eq.{date_str}"})

def add_brew_record(date_str, tea_name, water_ml, actual_yield_ml, leaves_g):
    _post("brew_records", {
        "record_date": date_str,
        "tea_name": tea_name,
        "water_used_ml": water_ml,
        "actual_yield_ml": actual_yield_ml,
        "leaves_used_g": leaves_g
    })
    deduct_stock(tea_name, leaves_g)

# ── 銷售記錄 ─────────────────────────────────────
def get_sales_records(date_str):
    return _get("sales_records", {"sale_date": f"eq.{date_str}"})

def get_sales_records_recent(days=30):
    """取得最近 N 天的銷售記錄"""
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days)).isoformat()
    return _get("sales_records", {
        "sale_date": f"gte.{since}",
        "order": "sale_date.desc"
    })

# ── 現金支出 ─────────────────────────────────────
def add_cash_expense(record):
    """新增一筆現金支出"""
    return _post("cash_expenses", record)

def get_cash_expenses(date_str=None, limit=100):
    """取得現金支出記錄；給日期則只取當日"""
    params = {"order": "created_at.desc", "limit": str(limit)}
    if date_str:
        params["expense_date"] = f"eq.{date_str}"
    return _get("cash_expenses", params)

def upload_expense_photo(file_bytes, filename):
    """上傳照片到 Supabase Storage 的 expense-photos bucket，回傳 public URL"""
    import time
    bucket = "expense-photos"
    # 加時間戳避免檔名衝突
    safe_name = f"{int(time.time()*1000)}_{filename}"
    url = f"{st.secrets['SUPABASE_URL'].rstrip('/')}/storage/v1/object/{bucket}/{safe_name}"
    headers = {
        "apikey": st.secrets["SUPABASE_KEY"],
        "Authorization": f"Bearer {st.secrets['SUPABASE_KEY']}",
        "Content-Type": "application/octet-stream",
    }
    try:
        r = httpx.post(url, headers=headers, content=file_bytes, timeout=30)
        if r.status_code in (200, 201):
            return f"{st.secrets['SUPABASE_URL'].rstrip('/')}/storage/v1/object/public/{bucket}/{safe_name}"
        return None
    except Exception as e:
        return None

# ── 交班 / 日報表 ─────────────────────────────────
def get_daily_report(date_str):
    """取得某日的交班記錄"""
    results = _get("daily_reports", {"report_date": f"eq.{date_str}"})
    return results[0] if results else None

def upsert_daily_report(record):
    """有就更新，沒就新增"""
    rdate = record.get('report_date')
    existing = get_daily_report(rdate)
    if existing:
        return _patch("daily_reports", record, {"report_date": rdate})
    return _post("daily_reports", record)

def get_daily_reports_month(year, month):
    """取得整月的交班記錄"""
    from datetime import date
    start = date(year, month, 1).isoformat()
    if month == 12:
        end = date(year + 1, 1, 1).isoformat()
    else:
        end = date(year, month + 1, 1).isoformat()
    url = f"{st.secrets['SUPABASE_URL'].rstrip('/')}/rest/v1/daily_reports"
    params = [
        ("report_date", f"gte.{start}"),
        ("report_date", f"lt.{end}"),
        ("order", "report_date.asc"),
    ]
    try:
        r = httpx.get(url, headers=_headers(), params=params)
        if r.status_code == 200:
            return r.json()
        return []
    except Exception:
        return []

def import_sales(records):
    _post("sales_records", records)

# ── 報廢記錄 ─────────────────────────────────────
def get_waste_records(date_str):
    return _get("waste_records", {"record_date": f"eq.{date_str}"})

def get_waste_records_recent(limit=200):
    return _get("waste_records", {"order": "record_date.desc", "limit": str(limit)})

def add_waste_record(date_str, material_name, amount, unit, reason="正常報廢"):
    _post("waste_records", {
        "record_date": date_str,
        "material_name": material_name,
        "waste_amount": amount,
        "unit": unit,
        "reason": reason
    })

# ── 庫存歷史 ─────────────────────────────────────
def get_inventory_logs(days=90):
    return _get("inventory_logs", {
        "order": "adjusted_at.desc",
        "limit": str(days * 5)
    })

def get_stock_in_records(days=90):
    return _get("stock_in_records", {
        "order": "received_date.desc",
        "limit": str(days * 5)
    })

# ── 訂貨 ─────────────────────────────────────────
def save_order(order_date_str, items):
    records = [
        {"order_date": order_date_str, "material_name": k,
         "quantity": v["qty"], "unit": v["unit"]}
        for k, v in items.items() if v["qty"] > 0
    ]
    if records:
        _post("order_records", records)
