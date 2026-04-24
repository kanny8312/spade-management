import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

def get_materials():
    sb = get_supabase()
    return sb.table("raw_materials").select("*").order("category").order("name").execute().data

def get_material(name):
    sb = get_supabase()
    r = sb.table("raw_materials").select("*").eq("name", name).execute()
    return r.data[0] if r.data else None

def update_stock(name, new_stock, note="盤點調整"):
    sb = get_supabase()
    m = get_material(name)
    old_stock = m["current_stock"] if m else 0
    sb.table("raw_materials").update({
        "current_stock": new_stock,
        "updated_at": "now()"
    }).eq("name", name).execute()
    sb.table("inventory_logs").insert({
        "material_name": name,
        "old_stock": old_stock,
        "new_stock": new_stock,
        "difference": float(new_stock) - float(old_stock),
        "note": note
    }).execute()

def add_stock_in(name, quantity):
    sb = get_supabase()
    m = get_material(name)
    if m:
        new_stock = float(m["current_stock"] or 0) + float(quantity)
        sb.table("raw_materials").update({
            "current_stock": new_stock,
            "updated_at": "now()"
        }).eq("name", name).execute()
        sb.table("stock_in_records").insert({
            "material_name": name,
            "quantity": quantity,
            "unit": m["unit"]
        }).execute()

def deduct_stock(name, quantity):
    sb = get_supabase()
    m = get_material(name)
    if m:
        new_stock = max(0, float(m["current_stock"] or 0) - float(quantity))
        sb.table("raw_materials").update({"current_stock": new_stock}).eq("name", name).execute()

def get_tea_specs():
    sb = get_supabase()
    return sb.table("tea_specs").select("*").execute().data

def get_recipes():
    sb = get_supabase()
    return sb.table("product_recipes").select("*").execute().data

def get_brew_records(date_str):
    sb = get_supabase()
    return sb.table("brew_records").select("*").eq("record_date", date_str).execute().data

def add_brew_record(date_str, tea_name, water_ml, actual_yield_ml, leaves_g):
    sb = get_supabase()
    sb.table("brew_records").insert({
        "record_date": date_str,
        "tea_name": tea_name,
        "water_used_ml": water_ml,
        "actual_yield_ml": actual_yield_ml,
        "leaves_used_g": leaves_g
    }).execute()
    deduct_stock(tea_name, leaves_g)

def get_sales_records(date_str):
    sb = get_supabase()
    return sb.table("sales_records").select("*").eq("sale_date", date_str).execute().data

def import_sales(records):
    sb = get_supabase()
    sb.table("sales_records").insert(records).execute()

def get_waste_records(date_str):
    sb = get_supabase()
    return sb.table("waste_records").select("*").eq("record_date", date_str).execute().data

def add_waste_record(date_str, material_name, amount, unit, reason="正常報廢"):
    sb = get_supabase()
    sb.table("waste_records").insert({
        "record_date": date_str,
        "material_name": material_name,
        "waste_amount": amount,
        "unit": unit,
        "reason": reason
    }).execute()

def get_inventory_logs(days=90):
    sb = get_supabase()
    return sb.table("inventory_logs").select("*").order("adjusted_at", desc=True).limit(days * 5).execute().data

def get_stock_in_records(days=90):
    sb = get_supabase()
    return sb.table("stock_in_records").select("*").order("received_date", desc=True).limit(days * 5).execute().data

def save_order(order_date_str, items):
    sb = get_supabase()
    records = [{"order_date": order_date_str, "material_name": k, "quantity": v["qty"], "unit": v["unit"]}
               for k, v in items.items() if v["qty"] > 0]
    if records:
        sb.table("order_records").insert(records).execute()
