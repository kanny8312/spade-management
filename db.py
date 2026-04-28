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
