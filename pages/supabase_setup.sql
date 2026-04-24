-- =============================================
-- 十杯茶飲管理系統 - Supabase 資料庫設定
-- 請在 Supabase SQL Editor 貼上全部執行
-- =============================================

-- 1. 原物料主表
CREATE TABLE IF NOT EXISTS raw_materials (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL,
  unit TEXT NOT NULL,
  current_stock DECIMAL DEFAULT 0,
  safety_stock DECIMAL DEFAULT 0,
  cost_per_unit DECIMAL DEFAULT 0,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 泡茶規格表
CREATE TABLE IF NOT EXISTS tea_specs (
  id SERIAL PRIMARY KEY,
  tea_name TEXT NOT NULL UNIQUE,
  grams_per_3000ml DECIMAL NOT NULL,
  yield_rate DECIMAL DEFAULT 0.88,
  brew_minutes INTEGER DEFAULT 10
);

-- 3. 產品配方表
CREATE TABLE IF NOT EXISTS product_recipes (
  id SERIAL PRIMARY KEY,
  product_name TEXT NOT NULL,
  size TEXT DEFAULT '',
  tea_type TEXT DEFAULT '',
  tea_ml DECIMAL DEFAULT 0,
  milk_ml DECIMAL DEFAULT 0
);

-- 4. 每日煮茶記錄
CREATE TABLE IF NOT EXISTS brew_records (
  id SERIAL PRIMARY KEY,
  record_date DATE NOT NULL DEFAULT CURRENT_DATE,
  tea_name TEXT NOT NULL,
  water_used_ml DECIMAL NOT NULL,
  actual_yield_ml DECIMAL,
  leaves_used_g DECIMAL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. 銷售記錄（從肚肚匯入）
CREATE TABLE IF NOT EXISTS sales_records (
  id SERIAL PRIMARY KEY,
  sale_date DATE NOT NULL,
  product_name TEXT NOT NULL,
  product_category TEXT DEFAULT '',
  size TEXT DEFAULT '',
  quantity INTEGER NOT NULL DEFAULT 0,
  revenue DECIMAL DEFAULT 0,
  platform TEXT DEFAULT '現場',
  imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. 報廢記錄
CREATE TABLE IF NOT EXISTS waste_records (
  id SERIAL PRIMARY KEY,
  record_date DATE NOT NULL DEFAULT CURRENT_DATE,
  material_name TEXT NOT NULL,
  waste_amount DECIMAL NOT NULL,
  unit TEXT NOT NULL,
  reason TEXT DEFAULT '正常報廢',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. 庫存調整記錄（盤點）
CREATE TABLE IF NOT EXISTS inventory_logs (
  id SERIAL PRIMARY KEY,
  adjusted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  material_name TEXT NOT NULL,
  old_stock DECIMAL DEFAULT 0,
  new_stock DECIMAL NOT NULL,
  difference DECIMAL,
  note TEXT DEFAULT '盤點調整'
);

-- 8. 進貨記錄
CREATE TABLE IF NOT EXISTS stock_in_records (
  id SERIAL PRIMARY KEY,
  received_date DATE NOT NULL DEFAULT CURRENT_DATE,
  material_name TEXT NOT NULL,
  quantity DECIMAL NOT NULL,
  unit TEXT DEFAULT '',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 9. 訂貨記錄
CREATE TABLE IF NOT EXISTS order_records (
  id SERIAL PRIMARY KEY,
  order_date DATE NOT NULL DEFAULT CURRENT_DATE,
  material_name TEXT NOT NULL,
  quantity DECIMAL NOT NULL,
  unit TEXT DEFAULT '',
  status TEXT DEFAULT '待進貨',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- 插入原物料資料
-- =============================================
INSERT INTO raw_materials (name, category, unit, safety_stock, cost_per_unit) VALUES
-- 茶葉
('紅茶',     '茶葉', 'g',  500,  0.267),
('綠茶',     '茶葉', 'g',  500,  0.420),
('清茶',     '茶葉', 'g',  500,  0.400),
('鐵觀音',   '茶葉', 'g',  500,  0.400),
('金萱',     '茶葉', 'g',  500,  1.000),
('伯爵',     '茶葉', 'g',  300,  0.340),
('鍋煮茶',   '茶葉', 'g',  300,  0.350),
-- 牛奶
('初鹿鮮奶', '牛奶', '瓶', 10,   85),
('主恩鮮奶', '牛奶', '瓶', 10,   70),
('大山鮮奶', '牛奶', '瓶', 5,    80),
('橋頭鮮奶', '牛奶', '瓶', 5,    65),
('柳營鮮奶', '牛奶', '瓶', 5,   130),
-- 配料
('珍珠(生)', '配料', 'g',  2000, 0.05),
('QQ(生)',   '配料', 'g',  1000, 0.07),
('鮮奶油',   '配料', 'g',  500,  0.75),
('洛神',     '配料', 'ml', 2000, 0.04),
('桂花釀',   '配料', 'ml', 500,  0.145),
('桂花清凍', '配料', 'ml', 1000, 0),
('鐵觀音凍', '配料', 'ml', 1000, 0),
('綠茶凍',   '配料', 'ml', 1000, 0),
-- 糖
('果糖',     '糖',   'ml', 3000, 0.03),
('黑糖',     '糖',   'g',  500,  0.033),
('蜂蜜',     '糖',   'ml', 500,  0.055),
('液態糖',   '糖',   'ml', 2000, 0.03),
('砂糖',     '糖',   'g',  1000, 0.01),
-- 粉類
('奶精粉',   '粉類', '包', 5,    30),
('可可粉',   '粉類', 'g',  200,  0.38),
('吉利丁',   '粉類', 'g',  100,  0.50),
-- 耗材
('500ml紙杯','耗材', '個', 200,  1.365),
('700ml紙杯','耗材', '個', 200,  1.659),
('細吸管',   '耗材', '支', 300,  0.151),
('粗吸管',   '耗材', '支', 300,  0.236),
('封膜',     '耗材', '個', 500,  0.17),
('購物袋(小)','耗材','個', 100,  1.0),
('購物袋(大)','耗材','個', 100,  2.0),
-- 其他
('多多',     '其他', '瓶', 10,   6.5),
('檸檬汁',   '其他', 'ml', 300,  0.137),
('海鹽',     '其他', 'g',  100,  0.05)
ON CONFLICT (name) DO NOTHING;

-- =============================================
-- 泡茶規格（每3000ml水用幾g茶葉）
-- =============================================
INSERT INTO tea_specs (tea_name, grams_per_3000ml, brew_minutes, yield_rate) VALUES
('紅茶',   90, 7,  0.88),
('綠茶',   81, 12, 0.88),
('清茶',   81, 7,  0.88),
('鐵觀音', 81, 10, 0.88),
('金萱',   90, 10, 0.88),
('伯爵',   57, 10, 0.88),
('鍋煮茶', 72, 20, 0.88)
ON CONFLICT (tea_name) DO NOTHING;

-- =============================================
-- 產品配方（每杯茶量ml）
-- =============================================
INSERT INTO product_recipes (product_name, size, tea_type, tea_ml, milk_ml) VALUES
-- 純萃原茶
('錫蘭紅茶',   'L', '紅茶',   250, 0),
('錫蘭紅茶',   'M', '紅茶',   200, 0),
('茉香綠茶',   'L', '綠茶',   300, 0),
('茉香綠茶',   'M', '綠茶',   220, 0),
('文山清茶',   'L', '清茶',   300, 0),
('文山清茶',   'M', '清茶',   220, 0),
('翠心金萱',   'L', '金萱',   300, 0),
('翠心金萱',   'M', '金萱',   220, 0),
('沉香鐵觀音', 'L', '鐵觀音', 300, 0),
('沉香鐵觀音', 'M', '鐵觀音', 220, 0),
('皇家伯爵',   'L', '伯爵',   300, 0),
('皇家伯爵',   'M', '伯爵',   220, 0),
-- 招牌牧奶茶
('經典牧奶茶',   'L', '紅茶',   200, 230),
('經典牧奶茶',   'M', '紅茶',   150, 180),
('鐵觀音牧奶茶', 'L', '鐵觀音', 200, 230),
('鐵觀音牧奶茶', 'M', '鐵觀音', 150, 180),
('桂花清牧奶茶', 'L', '清茶',   200, 230),
('桂花清牧奶茶', 'M', '清茶',   150, 180),
('茉香牧奶綠',   'L', '綠茶',   200, 230),
('茉香牧奶綠',   'M', '綠茶',   150, 180),
('伯爵牧奶茶',   'L', '伯爵',   200, 230),
('伯爵牧奶茶',   'M', '伯爵',   150, 180),
('金萱牧奶茶',   'L', '金萱',   200, 230),
('金萱牧奶茶',   'M', '金萱',   150, 180),
-- 手攪奶茶
('十杯奶茶',     '', '紅茶',   300, 0),
('十杯奶綠',     '', '綠茶',   300, 0),
('珍珠奶茶',     '', '紅茶',   250, 0),
('黑糖奶茶',     'L', '紅茶',  300, 0),
('黑糖奶茶',     'M', '紅茶',  220, 0),
('蜂蜜觀音奶茶', '', '鐵觀音', 300, 0),
('焙香觀音可可', 'L', '鐵觀音', 270, 130),
('焙香觀音可可', 'M', '鐵觀音', 200, 100),
-- 特調茶飲
('多多綠茶',   '', '綠茶', 250, 0),
('蜂蜜紅茶',   '', '紅茶', 250, 0),
('蜂蜜清茶',   '', '清茶', 250, 0),
('桂花清茶',   '', '清茶', 300, 0),
('翡翠檸檬',   '', '綠茶', 280, 0),
('蜂蜜檸檬',   '', '',     0,   0),
('洛神QQ清檸', '', '清茶',  90, 0),
-- 茶凍歐蕾
('桂花凍綠奶歐蕾', 'L', '綠茶',   160, 60),
('桂花凍綠奶歐蕾', 'M', '綠茶',   150, 50),
('觀音凍雙茶歐蕾', 'L', '鐵觀音', 160, 60),
('觀音凍雙茶歐蕾', 'M', '鐵觀音', 150, 50),
('茉香凍鍋煮歐蕾', 'L', '鍋煮茶', 160, 60),
('茉香凍鍋煮歐蕾', 'M', '鍋煮茶', 150, 50),
('茉香凍伯爵歐蕾', 'L', '伯爵',   160, 60),
('茉香凍伯爵歐蕾', 'M', '伯爵',   150, 50),
-- 海鹽黑糖奶蓋（雪霜）
('維也納紅茶', 'L', '紅茶',   270, 0),
('維也納紅茶', 'M', '紅茶',   200, 0),
('雪霜可可',   'L', '鐵觀音', 270, 0),
('雪霜可可',   'M', '鐵觀音', 200, 0),
('雪霜觀音',   'L', '鐵觀音', 270, 0),
('雪霜觀音',   'M', '鐵觀音', 200, 0),
('雪霜伯爵紅', 'L', '伯爵',   270, 0),
('雪霜伯爵紅', 'M', '伯爵',   200, 0);

-- =============================================
-- 關閉 RLS（讓程式可以直接存取）
-- =============================================
ALTER TABLE raw_materials    DISABLE ROW LEVEL SECURITY;
ALTER TABLE tea_specs        DISABLE ROW LEVEL SECURITY;
ALTER TABLE product_recipes  DISABLE ROW LEVEL SECURITY;
ALTER TABLE brew_records     DISABLE ROW LEVEL SECURITY;
ALTER TABLE sales_records    DISABLE ROW LEVEL SECURITY;
ALTER TABLE waste_records    DISABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_logs   DISABLE ROW LEVEL SECURITY;
ALTER TABLE stock_in_records DISABLE ROW LEVEL SECURITY;
ALTER TABLE order_records    DISABLE ROW LEVEL SECURITY;
