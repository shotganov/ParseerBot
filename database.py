import sqlite3
import math
from datetime import datetime
import json

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('database_new.db', check_same_thread=False)
        self.create_tables()
        self.initialize_iphone_configs()

        if not self.get_system_config("wb_authorization"):
            self.set_system_config("wb_authorization", "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3Njc2MzI5MjUsInVzZXIiOiI1NDU4NDA2MiIsInNoYXJkX2tleSI6IjYiLCJjbGllbnRfaWQiOiJ3YiIsInNlc3Npb25faWQiOiJmMmE3NWRjMThjODU0YTNkOGIxNDdlMTY4Mzc0NmJiZSIsInZhbGlkYXRpb25fa2V5IjoiMDJjYWY3OTU4Y2RiNTU5MjRiMTc3MzQ3MGZmOWIxNjliN2JjMzcxZmMxMmMzYTA5OTg4M2Y5OGU4NjMwZTVhNyIsInBob25lIjoiSmI5N1U0UTdYa1pBT1I4SWMrUFVkZz09IiwidXNlcl9yZWdpc3RyYXRpb25fZHQiOjE2OTUwNDgzMzksInZlcnNpb24iOjJ9.T6nkWSC7XyRuhvcMajMTxXk2SitYQg8OnO-4uepAWaTYEnw5U8KwQgQxP-yI9DrES7BI1Kt0T0pRmYNlH2Is5p2tNpUQ7de4QPRsUH9X674hbKXuofb2SZBYN5VaPy57gBvSUyyMJrNbbhGQejZg4-m9CI8Jn8PNcEUSNlMSymsTYrrVY1jRdymbTuMb5_qri7kWnhEmy02hDPrQN6XcBYKGwCuk5_bIwPWTC3Po1v3Cs0u65NMQzb1T6SO-Ji0TTzFs4x_nfr75q3lOZJEry-5iqMzlcB4NdA6wIBmyegfHFeeSJ4ZZikJkqqI93jJJ0jRooimk8-FMUnR5Pl0jcQ")
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Обновленная таблица user_settings без колонок цен
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                discount_percent INTEGER DEFAULT 10,
                price_threshold INTEGER DEFAULT 50,
                is_active BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Новая таблица для хранения цен продуктов is_active BOOLEAN DEFAULT 0,
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_product_prices (
                user_id INTEGER,
                product_type TEXT NOT NULL,  -- 'iphone_16_128', 'iphone_16_pro_256', 'ps5_slim_disk'
                max_price INTEGER NOT NULL,
                PRIMARY KEY (user_id, product_type),
                FOREIGN KEY (user_id) REFERENCES user_settings (user_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_notifications (
                user_id INTEGER,
                product_id INTEGER,
                current_price INTEGER,
                discount_percent INTEGER DEFAULT 10,
                in_stock INTEGER DEFAULT 1,            -- ✅ НОВОЕ (1 = в наличии, 0 = нет)
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, product_id),
                FOREIGN KEY (user_id) REFERENCES user_settings (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS temp_data (
                user_id INTEGER PRIMARY KEY,
                waiting_for_price INTEGER DEFAULT 0,
                product_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 
        cursor.execute('''
          CREATE TABLE IF NOT EXISTS search_configs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              product_name TEXT NOT NULL,
              product_type TEXT NOT NULL,
              search_queries TEXT NOT NULL,    -- JSON список запросов
              include_keywords TEXT NOT NULL,  -- ✅ НОВОЕ: JSON список обязательных слов
              exclude_keywords TEXT NOT NULL,  -- JSON список исключений
              filters TEXT,
              is_active BOOLEAN DEFAULT 1,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
          )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # is_active BOOLEAN DEFAULT 1,
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_custom_links (
                user_id INTEGER,
                product_id INTEGER NOT NULL,  -- nm-артикул из ссылки
                initial_price INTEGER NOT NULL,   -- макс. цена, при которой уведомлять
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, product_id),
                FOREIGN KEY (user_id) REFERENCES user_settings (user_id)
            )
        ''')
        
        self.conn.commit()
    
    def initialize_iphone_configs(self):
      """Инициализирует конфиги для iPhone 16 и 16 Pro с обязательными словами"""
      cursor = self.conn.cursor()
      
      # Проверяем, есть ли уже конфиги
      cursor.execute('SELECT COUNT(*) FROM search_configs WHERE product_type LIKE "iphone%"')
      if cursor.fetchone()[0] == 0:
          print("🔄 Инициализация конфигов для товаров...")
          
          iphone_17_256_config = {
              'product_name': 'iPhone 17 256Gb',
              'product_type': 'iphone_17_256',
              'search_queries': json.dumps([
                  "iPhone 17 256"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "iphone", "17"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "15", "14", "13", "11", "10", "xs", "xr", "16",
                  "plus", "pro", "iphone 12",
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный", "актив",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                  "512", "пonepжaнный"
              ], ensure_ascii=False),
              'filters' : '',
          }

          iphone_17_pro_256_config = {
              'product_name': 'iPhone 17 Pro 256Gb',
              'product_type': 'iphone_17_pro_256',
              'search_queries': json.dumps([
                  "iPhone 17 Pro 256"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "iphone", "17", "pro"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "15", "14", "13", "11", "10", "xs", "xr", "16",
                  "plus", "max", "12", #"esim+esim", "esim only", "only esim",
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный", "актив",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                  "512", "пonepжaнный"
              ], ensure_ascii=False),
              'filters' : '',
          }

          iphone_17_pro_max_256_config = {
              'product_name': 'iPhone 17 Pro Max 256Gb',
              'product_type': 'iphone_17_pro_max_256',
              'search_queries': json.dumps([
                  "iPhone 17 Pro Max 256"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "iphone", "17", "pro", "max"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "15", "14", "13", "11", "10", "xs", "xr", "16",
                  "plus", "12", #esim+esim", "esim only", "only esim",
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный", "актив",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                  "512", "пonepжaнный"
              ], ensure_ascii=False),
              'filters' : '',
          }

          # iPhone 16 128GB
          iphone_16_128_config = {
              'product_name': 'iPhone 16 128Gb',
              'product_type': 'iphone_16_128',
              'search_queries': json.dumps([
                  "iPhone 16 128"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "iphone", "16", "128"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "15", "14", "13", "11", "10", "xs", "xr", "7",
                  "16e", "16 e", "16е", "16 е", "plus", "16 cn", "16 CN", "pro", "iphone 12",
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный", "актив",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                  "256", "512", "пonepжaнный"
              ], ensure_ascii=False),
              'filters' : '',
          }
          
          # iPhone 16 256GB
          iphone_16_256_config = {
              'product_name': 'iPhone 16 256Gb',
              'product_type': 'iphone_16_256',
              'search_queries': json.dumps([
                  "iPhone 16 256"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "iphone", "16", "256"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                "15", "14", "13", "11", "10", "xs", "xr", "7",
                "16e", "16 e", "16е", "16 е", "plus", "16 cn", "16 CN", "pro", 
                "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный", "актив",
                "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                "128", "512", "пonepжaнный"
              ], ensure_ascii=False),
              'filters' : '',
          }
          
          # iPhone 16 Pro 128GB
          iphone_16_pro_128_config = {
              'product_name': 'iPhone 16 Pro 128Gb',
              'product_type': 'iphone_16_pro_128', 
              'search_queries': json.dumps([
                  "iPhone 16 Pro 128"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "iphone", "16", "pro", "128"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "15", "14", "13", "11", "xr", "xs", "7",
                  "16e", "16 e", "16е", "16 е", "plus", "pro max", "16 128", "16 256", "16 512",
                  "Air", "iphone 16 s", 
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный", "актив", 
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка!", "обменка", "обменный",
                  "256", "512", "1tb", "пonepжaнный"
              ], ensure_ascii=False),
              'filters' : '',
          }
          
          # iPhone 16 Pro 256GB
          iphone_16_pro_256_config = {
              'product_name': 'iPhone 16 Pro 256Gb',
              'product_type': 'iphone_16_pro_256', 
              'search_queries': json.dumps([
                  "iPhone 16 Pro 256"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "iphone", "16", "pro", "256"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "15", "14", "13", "11", "xr", "xs", "7",
                  "16e", "16 e", "16е", "16 е", "plus", "pro max", "16 128", "16 256", "16 512",
                  "Air", "iphone 16 s",
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный", "актив",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                  "128", "512", "1tb", "пonepжaнный"
              ], ensure_ascii=False),
              'filters' : '',
          }

          # iPhone 16 Pro Max 256GB
          iphone_16_pro_max_256_config = {
              'product_name': 'iPhone 16 Pro Max 256Gb',
              'product_type': 'iphone_16_pro_max_256',
              'search_queries': json.dumps([
                  "iPhone 16 Pro Max 256"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "iphone", "16", "pro", "max", "256"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "15", "14", "13", "11", "7",
                  "16e", "16 e", "16е", "16 е", "plus", "16 128", "16 256", "16 512",
                  "Air", "16 pro 128", "16 pro 256", "16 pro 512", "16 pro 1tb", "iphone 16 s", "актив",
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный", 
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                  "128", "512", "1tb", "ПonepЖaнHый"
              ], ensure_ascii=False),
              'filters' : '',
          }

          samsung_s25_ultra_256_config = {
              'product_name': 'Samsung S25 Ultra 256Gb',
              'product_type': 'samsung_s25_ultra_256',
              'search_queries': json.dumps([
                  "Samsung S25 Ultra 256"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "s25", "ultra", "256"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "актив", "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный", 
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                  "128", "512", "1tb", "ПonepЖaнHый"
              ], ensure_ascii=False),
              'filters' : '',
          }


          # PS5 Slim
          ps5_slim_disk_config = {
              'product_name': 'PlayStation 5 Slim',
              'product_type': 'ps5_slim_disk',
              'search_queries': json.dumps([
                  "playstation 5 slim", "playstation 5 slim blue-ray"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "5", "slim"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "digital", "digital edition", "digital version",
                  "без дисковода", "без привода", "бездисковый", "бездисковая",
                  "без диска", "цифровая", "цифровой", "цифровое", "цифровой версии", "4", "4 slim", "ssd-диск", "витринная",
              ], ensure_ascii=False),
              'filters' : '',
          }

          # PS5 Pro
          ps5_pro_config = {
              'product_name': 'PlayStation 5 Pro',
              'product_type': 'ps5_pro',
              'search_queries': json.dumps([
                  "playstation 5 pro"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "5", "pro"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "4 slim", "4 pro", "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "подержанная", "восстановленная", "отремонтированная", "обменная",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный", "ssd-диск", "витринная"
              ], ensure_ascii=False),
              'filters' : '',
          }

          rtx_5060_config = {
              'product_name': 'Rtx 5060',
              'product_type': 'rtx_5060',
              'search_queries': json.dumps([
                  "rtx 5060"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "5060"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "подержанная", "восстановленная", "отремонтированная", "обменная",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный","витринная"
              ], ensure_ascii=False),
              'filters' : '',
          }

          rtx_5060_ti_8_config = {
              'product_name': 'Rtx 5060 Ti 8Gb',
              'product_type': 'rtx_5060_ti_8',
              'search_queries': json.dumps([
                  "rtx 5060 ti 8gb"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "5060", "8"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "подержанная", "восстановленная", "отремонтированная", "обменная",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный","витринная"
              ], ensure_ascii=False),
              'filters' : '',
          }

          rtx_5060_ti_16_config = {
              'product_name': 'Rtx 5060 Ti 16Gb',
              'product_type': 'rtx_5060_ti_16',
              'search_queries': json.dumps([
                  "rtx 5060 ti 16gb"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "5060", "16"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "подержанная", "восстановленная", "отремонтированная", "обменная",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный","витринная"
              ], ensure_ascii=False),
              'filters' : '',
          }

          rtx_5070_config = {
              'product_name': 'Rtx 5070',
              'product_type': 'rtx_5070',
              'search_queries': json.dumps([
                  "rtx 5070"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "5070"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "подержанная", "восстановленная", "отремонтированная", "обменная",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный","витринная"
              ], ensure_ascii=False),
              'filters' : '',
          }

          # Вставляем конфиги
          configs = [
              iphone_17_256_config, iphone_17_pro_256_config, iphone_17_pro_max_256_config,
              iphone_16_128_config, iphone_16_256_config, 
              iphone_16_pro_128_config, iphone_16_pro_256_config, 
              iphone_16_pro_max_256_config, 
              ps5_slim_disk_config, ps5_pro_config,
              rtx_5060_config, rtx_5060_ti_8_config, rtx_5060_ti_16_config, rtx_5070_config
          ]
          
          for config in configs:
              cursor.execute('''
                  INSERT OR REPLACE INTO search_configs 
                  (product_name, product_type, search_queries, include_keywords, exclude_keywords, filters)
                  VALUES (?, ?, ?, ?, ?, ?)
              ''', (
                  config['product_name'],
                  config['product_type'],
                  config['search_queries'],
                  config['include_keywords'],
                  config['exclude_keywords'],
                  config['filters']
              ))
          
          self.conn.commit()
          print(f"✅ Конфиги для {len(configs)} товаров инициализированы с обязательными словами")

    def add_custom_link(self, user_id: int, product_id: int, initial_price: int):
      cursor = self.conn.cursor()
      cursor.execute('SELECT 1 FROM user_settings WHERE user_id = ?', (user_id,))
      if not cursor.fetchone():
          cursor.execute('INSERT INTO user_settings (user_id) VALUES (?)', (user_id,))
      cursor.execute('''
          INSERT OR REPLACE INTO user_custom_links (user_id, product_id, initial_price)
          VALUES (?, ?, ?)
      ''', (user_id, product_id, initial_price))
      self.conn.commit()

    def delete_custom_link(self, user_id: int, product_id: int):
      """ПОЛНОСТЬЮ удаляет кастомную ссылку из БД"""
      cursor = self.conn.cursor()
      cursor.execute('DELETE FROM user_custom_links WHERE user_id = ? AND product_id = ?', (user_id, product_id))
      self.conn.commit()

    def get_user_custom_links(self, user_id: int):
      cursor = self.conn.cursor()
      cursor.execute('''
          SELECT product_id, initial_price
          FROM user_custom_links
          WHERE user_id = ?
      ''', (user_id,))
      return {row[0]: row[1] for row in cursor.fetchall()}

    def cleanup_old_custom_links(self, days=30):
      """Удаляет custom links старше N дней (по умолчанию 30)"""
      cursor = self.conn.cursor()
      cursor.execute('DELETE FROM user_custom_links WHERE created_at < datetime("now", ?)', (f"-{days} days",))
      deleted = cursor.rowcount
      self.conn.commit()
      return deleted

    def get_all_users_tracking_custom_link(self, product_id: int):
        """Получает всех пользователей, отслеживающих конкретный артикул"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ucl.user_id, ucl.initial_price, us.discount_percent, us.price_threshold
            FROM user_custom_links ucl
            JOIN user_settings us ON ucl.user_id = us.user_id
            WHERE ucl.product_id = ? AND us.is_active = 1
        ''', (product_id,))
        return cursor.fetchall()

    def set_system_config(self, key: str, value: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO system_config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        self.conn.commit()

    def get_system_config(self, key: str, default: str = None) -> str:
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM system_config WHERE key = ?', (key,))
        result = cursor.fetchone()
        return result[0] if result else default

    def set_user_search_active(self, user_id, active):
      """Включает/выключает поиск для пользователя (обновляет is_active в ОБОИХ таблицах)"""
      cursor = self.conn.cursor()
      # Обновляем стандартные товары
      cursor.execute('''
          UPDATE user_settings SET is_active = ? WHERE user_id = ?
      ''', (active, user_id))

      self.conn.commit()

    def get_user_search_active(self, user_id):
      cursor = self.conn.cursor()
      # Проверяем активность в ЛЮБОЙ таблице отслеживания
      cursor.execute('''
          SELECT 1 FROM user_settings 
          WHERE user_id = ? AND is_active = 1
      ''', (user_id,))

      return cursor.fetchone() is not None

    def get_users_with_any_active_tracking(self):
      """Возвращает всех пользователей, у которых есть хоть одно активное отслеживание (стандартное или кастомное)"""
      cursor = self.conn.cursor()
      cursor.execute('''
          SELECT DISTINCT user_id FROM (
              SELECT user_id FROM user_settings WHERE is_active = 1
          )
      ''')
      return [row[0] for row in cursor.fetchall()]
    
    def set_user_product_price(self, user_id, product_type, price):
      """Устанавливает максимальную цену для конкретного товара пользователя"""
      cursor = self.conn.cursor()
      
      cursor.execute('''
          INSERT OR REPLACE INTO user_product_prices 
          (user_id, product_type, max_price) 
          VALUES (?, ?, ?)
      ''', (user_id, product_type, price)) 
      
      # Создаем запись в user_settings если её нет
      cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
      if not cursor.fetchone():
          cursor.execute('''
              INSERT INTO user_settings (user_id, discount_percent, price_threshold, is_active)
              VALUES (?, 10, 50, 0)
          ''', (user_id,))
      
      self.conn.commit()

    def get_all_user_product_prices(self, user_id):
      """Получает все цены товаров пользователя с информацией о активности"""
      cursor = self.conn.cursor()

      cursor.execute('''
          SELECT sc.product_name, upp.product_type, upp.max_price
          FROM user_product_prices upp
          INNER JOIN search_configs sc ON sc.product_type = upp.product_type
          WHERE upp.user_id = ?
      ''', (user_id,))

      return {
          row[1]: {  # product_type как ключ
              'product_name': row[0],  # product_name
              'price': row[2],         # max_price
          } 
          for row in cursor.fetchall()
      }

    def get_user_product_price(self, user_id: int, product_type: str) -> int | None:
      cursor = self.conn.cursor()
      cursor.execute(
          "SELECT max_price FROM user_product_prices WHERE user_id = ? AND product_type = ?",
          (user_id, product_type)
      )
      row = cursor.fetchone()
      return int(row[0]) if row else None

    
    def get_all_user_custom_links(self, user_id: int):
      """Возвращает ВСЕ кастомные ссылки пользователя (для отображения в меню)"""
      cursor = self.conn.cursor()
      cursor.execute('''
          SELECT product_id, initial_price
          FROM user_custom_links
          WHERE user_id = ?
      ''', (user_id,))
      return {row[0]: {'price': row[1] } for row in cursor.fetchall()}

    # Обновленные методы для обратной совместимости
    def get_user_settings(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT discount_percent, price_threshold FROM user_settings WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return (10, 50) if not result else (result[0], result[1])

    def set_user_threshold(self, user_id, threshold):
        """Установка общего автоматического порога для пользователя"""
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            cursor.execute('UPDATE user_settings SET price_threshold = ? WHERE user_id = ?', (threshold, user_id))
        else:
            cursor.execute('INSERT INTO user_settings (user_id, price_threshold) VALUES (?, ?)', 
                          (user_id, threshold))
        
        self.conn.commit()
    
    def set_user_discount(self, user_id, discount_percent):
        """Установка процента скидки для пользователя с обновлением истории уведомлений"""
        cursor = self.conn.cursor()
        
        # Получаем старую скидку
        old_discount = 10  # значение по умолчанию
        cursor.execute('SELECT discount_percent FROM user_settings WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            old_discount = result[0]
        
        # Обновляем настройки пользователя
        cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            cursor.execute('UPDATE user_settings SET discount_percent = ? WHERE user_id = ?', 
                          (discount_percent, user_id))
        else:
            cursor.execute('INSERT INTO user_settings (user_id, discount_percent) VALUES (?, ?)', 
                          (user_id, discount_percent))
        
        self.conn.commit()
        
        # Если скидка изменилась, обновляем историю уведомлений
        if old_discount != discount_percent:
            self.update_discount_in_notifications(user_id, discount_percent)

    def get_all_users(self):
        """Получает всех пользователей с их настройками"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT us.user_id, us.discount_percent, us.price_threshold
            FROM user_settings us
        ''')
        return cursor.fetchall()

    # Старые методы (оставляем для обратной совместимости, но они теперь используют новую таблицу)

    def set_user_price(self, user_id, product_type, price):
        """Совместимость со старым кодом - использует новую таблицу"""
        self.set_user_product_price(user_id, product_type, price)

    def delete_user_product_price(self, user_id, product_type): 
      """Удаляет запись о цене товара для конкретного пользователя и типа товара""" 
      cursor = self.conn.cursor() 
      
      # Удаляем запись 
      cursor.execute(''' 
          DELETE FROM user_product_prices WHERE user_id = ? AND product_type = ? ''', 
          (user_id, product_type)) 
      
      self.conn.commit() 
      
      # Возвращаем True если была удалена хотя бы одна запись 
      
      return cursor.rowcount > 0

    def get_search_config(self, product_type):
      """Получает конфиг для конкретного типа продукта с обязательными словами"""
      cursor = self.conn.cursor()
      cursor.execute(
          'SELECT product_name, search_queries, include_keywords, exclude_keywords FROM search_configs WHERE product_type = ? AND is_active = 1',
          (product_type,)
      )
      result = cursor.fetchone()
      
      if result:
          return {
              'product_name': result[0],
              'search_queries': json.loads(result[1]),
              'include_keywords': json.loads(result[2]),  # ✅ Добавляем обязательные слова
              'exclude_keywords': json.loads(result[3]),
          }
      return None

    def get_all_search_configs(self):
        """Получает все активные конфиги для поиска с обязательными словами"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT product_type, product_name, search_queries, include_keywords, exclude_keywords, filters FROM search_configs WHERE is_active = 1'
        )
        
        configs = {}
        for row in cursor.fetchall():
            configs[row[0]] = {
                'product_name': row[1],
                'search_queries': json.loads(row[2]),
                'include_keywords': json.loads(row[3]),  
                'exclude_keywords': json.loads(row[4]),
                'filters' : row[5],
            }
        return configs

    def get_product_config_by_name(self, product_name):
        """Получает конфиг по названию продукта"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT product_type, product_name, search_queries, exclude_keywords FROM search_configs WHERE product_name = ? AND is_active = 1',
            (product_name,)
        )
        result = cursor.fetchone()
        
        if result:
            return {
                'product_type': result[0],
                'product_name': result[1],
                'search_queries': json.loads(result[2]),
                'include_keywords': json.loads(result[3]),
                'exclude_keywords': json.loads(result[4]),
            }
        return None

    def get_available_products(self):
        """Получает список всех доступных продуктов"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT product_type, product_name FROM search_configs WHERE is_active = 1 ORDER BY product_name'
        )
        return cursor.fetchall()

    def set_waiting_for_price(self, user_id, waiting_for_price, product_type=None):
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT * FROM temp_data WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            cursor.execute('UPDATE temp_data SET waiting_for_price = ?, product_type = ? WHERE user_id = ?', 
                          (waiting_for_price, product_type, user_id))
        else:
            cursor.execute('INSERT INTO temp_data (user_id, waiting_for_price, product_type) VALUES (?, ?, ?)', 
                          (user_id, waiting_for_price, product_type))
        
        self.conn.commit()
    
    def get_waiting_for_price(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT waiting_for_price, product_type FROM temp_data WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result if result else (0, None)
    
    def clear_waiting_for_price(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM temp_data WHERE user_id = ?', (user_id,))
        self.conn.commit()
    
    def is_product_sent_recently(self, user_id, product_id, hours=24):
        """Проверяем, отправлялось ли уведомление за последние hours часов"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 1 FROM product_notifications 
            WHERE user_id = ? AND product_id = ? AND last_updated > datetime('now', ?)
        ''', (user_id, product_id, f'-{hours} hours'))
        return cursor.fetchone() is not None
    
    def save_notification(self, user_id, product_id, current_price, discount_percent):
        """
        Сохраняем/обновляем уведомление только если нужно отправлять
        Возвращает: (should_send, previous_price, price_dropped)
        """
        current_price_int = math.floor(current_price)
        
        cursor = self.conn.cursor()
        
        # Ищем существующую запись
        cursor.execute('''
            SELECT current_price 
            FROM product_notifications 
            WHERE user_id = ? AND product_id = ?
        ''', (user_id, product_id))
        result = cursor.fetchone()
        
        if result:
            # Запись существует
            existing_price = result[0]
            price_dropped = current_price_int < existing_price
            
            if price_dropped:
                # Цена упала - обновляем запись
                cursor.execute('''
                    UPDATE product_notifications 
                    SET current_price = ?, 
                        discount_percent = ?,
                        in_stock = 1,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND product_id = ?
                ''', (current_price_int, discount_percent, user_id, product_id))


                
                self.conn.commit()
                print(f"📉 Цена обновлена для товара {product_id}: {existing_price} → {current_price_int}")
                return True, existing_price, True   
            else:
                return False, existing_price, False
                
        else:
            cursor.execute('''
                INSERT INTO product_notifications 
                (user_id, product_id, current_price, discount_percent, in_stock)
                VALUES (?, ?, ?, ?, 1)
            ''', (user_id, product_id, current_price_int, discount_percent))

            self.conn.commit()
            print(f"🆕 Новый товар {product_id} добавлен, цена: {current_price_int}")
            return True, None, False
        
        
    def get_user_notified_product_ids(self, user_id: int):
        """Какие товары уже есть в product_notifications (то есть мы их уже слали пользователю)"""
        cur = self.conn.cursor()
        cur.execute('SELECT product_id FROM product_notifications WHERE user_id = ?', (user_id,))
        return {row[0] for row in cur.fetchall()}
    
    def get_user_out_of_stock_product_ids(self, user_id: int):
        cur = self.conn.cursor()
        cur.execute('SELECT product_id FROM product_notifications WHERE user_id = ? AND in_stock = 0', (user_id,))
        return {row[0] for row in cur.fetchall()}

    def update_in_stock(self, user_id: int, product_id: int, in_stock: int):
        """
        Возвращает (changed, became_in_stock)
        became_in_stock=True только при переходе 0 -> 1
        """
        cur = self.conn.cursor()
        cur.execute(
            'SELECT in_stock FROM product_notifications WHERE user_id = ? AND product_id = ?',
            (user_id, product_id)
        )
        row = cur.fetchone()
        if not row:
            return False, False

        old = int(row[0]) if row[0] is not None else 1
        new = 1 if in_stock else 0
        if old == new:
            return False, False

        cur.execute('''
            UPDATE product_notifications
            SET in_stock = ?, last_updated = CURRENT_TIMESTAMP
            WHERE user_id = ? AND product_id = ?
        ''', (new, user_id, product_id))
        self.conn.commit()

        return True, (old == 0 and new == 1)
    
    def get_previous_price(self, user_id, product_id):
        """Получаем предыдущую цену товара (теперь это просто current_price из БД)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT current_price FROM product_notifications 
            WHERE user_id = ? AND product_id = ?
        ''', (user_id, product_id))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_price_history(self, user_id, product_id, limit=10):
        """Получаем историю цен для товара (для аналитики)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT price, last_updated, discount_percent, price_changed, previous_price
            FROM product_notifications 
            WHERE user_id = ? AND product_id = ? 
            ORDER BY last_updated DESC 
            LIMIT ?
        ''', (user_id, product_id, limit))
        return cursor.fetchall()
    
    def cleanup_old_records(self, hours=24):
        """Очистка записей старше указанного количества часов"""
        cursor = self.conn.cursor()
        
        # Удаляем старые уведомления
        cursor.execute('DELETE FROM product_notifications WHERE last_updated < datetime("now", ?)', 
                      (f"-{hours} hours",))
        notifications_deleted = cursor.rowcount
        
        cursor.execute('DELETE FROM temp_data WHERE created_at < datetime("now", ?)', 
                      ("-1 hours",))
        temp_deleted = cursor.rowcount
        
        self.conn.commit()
        return notifications_deleted + temp_deleted
    
    def update_discount_in_notifications(self, user_id, new_discount_percent):
        """Обновляет процент скидки во всех уведомлениях пользователя"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE product_notifications 
                SET discount_percent = ?
                WHERE user_id = ?
            ''', (new_discount_percent, user_id))
            
            updated_count = cursor.rowcount
            self.conn.commit()
            
            print(f"✅ Обновлены скидки для {updated_count} товаров пользователя {user_id}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении скидки в уведомлениях: {e}")
            self.conn.rollback()
            return False
    
    def is_user_waiting_for_input(self, user_id):
        """Проверяет, ожидает ли пользователь ввода (установка цены, порога или скидки)"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT waiting_for_price FROM temp_data WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result is not None and result[0] == 1
    
    def close(self):
        """Закрывает соединение с базой данных"""
        if self.conn:
            self.conn.close()


if __name__ == "__main__":
    database = Database()
    
    # Тест новых методов
    # user_id = 12345
    # database.set_user_product_price(user_id, 'iphone_16_128', 80000) 
    # database.add_custom_link(user_id, 1, 50000)
    # database.add_custom_link(user_id, 2, 40000)
    # # price = database.get_user_product_price(user_id, 'iphone_16_128')
    # # print(f"Цена iPhone 16 128: {price}")
    
    # # all_prices = database.get_all_user_product_prices(user_id)
    # # print(f"Все цены пользователя: {all_prices}")
    
    # # users_tracking = database.get_users_tracking_product('iphone_16_128')
    # # print(f"Пользователи отслеживающие iPhone 16 128: {users_tracking}")

    # result = database.get_all_user_custom_links(user_id)
    # database.set_user_search_active(user_id, False)

    # user_products = database.get_all_user_product_prices(user_id)
    # custom_links = database.get_all_user_custom_links(user_id)
    # print(user_products)
    # print(custom_links)