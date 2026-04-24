import re

# 把 UberEats (U前綴) 和 Foodpanda (F前綴) 產品名稱對應回基本名稱
def normalize_name(raw_name: str):
    name = raw_name.strip()
    # 去除 U/F 前綴
    if name and name[0] in ('U', 'F') and len(name) > 1 and name[1] != ' ':
        name = name[1:].strip()
    # 從括號提取尺寸：U珍珠經典牧奶茶(L) → 名稱=珍珠經典牧奶茶, 尺寸=L
    size = ''
    m = re.search(r'\(([LM])\)$', name)
    if m:
        size = m.group(1)
        name = name[:m.start()].strip()
    # 珍珠經典牧奶茶 → 經典牧奶茶（珍珠是配料標籤，不是品名）
    name = name.replace('珍珠', '').strip()
    return name, size

def calculate_tea_consumption(sales_records, recipes):
    """從銷售記錄計算各茶種消耗量(ml)"""
    recipe_map = {}
    for r in recipes:
        key = (r['product_name'], r['size'] or '')
        recipe_map[key] = r

    consumption = {}
    for sale in sales_records:
        raw = sale.get('product_name', '')
        qty = int(sale.get('quantity', 0))
        size = sale.get('size', '') or ''

        name, extracted_size = normalize_name(raw)
        if not size:
            size = extracted_size

        recipe = recipe_map.get((name, size)) or recipe_map.get((name, ''))
        if recipe and recipe.get('tea_type') and recipe['tea_ml']:
            t = recipe['tea_type']
            consumption[t] = consumption.get(t, 0) + recipe['tea_ml'] * qty

    return consumption

def calculate_brew_yield(brew_records):
    """從煮茶記錄取得各茶種實際出湯量(ml)"""
    brewed = {}
    for r in brew_records:
        t = r['tea_name']
        ml = float(r.get('actual_yield_ml') or 0)
        brewed[t] = brewed.get(t, 0) + ml
    return brewed

def verify_tea(brew_records, waste_records, sales_records, recipes):
    """對帳：煮了多少 vs 賣出多少 vs 報廢多少"""
    brewed = calculate_brew_yield(brew_records)
    consumed = calculate_tea_consumption(sales_records, recipes)

    wasted = {}
    for r in waste_records:
        name = r['material_name']
        if r['unit'] == 'ml':
            wasted[name] = wasted.get(name, 0) + float(r['waste_amount'])

    all_teas = set(list(brewed.keys()) + list(consumed.keys()))
    results = {}
    for tea in all_teas:
        b = brewed.get(tea, 0)
        c = consumed.get(tea, 0)
        w = wasted.get(tea, 0)
        remaining = b - c
        diff = remaining - w
        threshold = max(b * 0.08, 100)
        results[tea] = {
            'brewed_ml': b,
            'consumed_ml': c,
            'waste_ml': w,
            'remaining_should_be': remaining,
            'diff': diff,
            'ok': abs(diff) <= threshold
        }
    return results
