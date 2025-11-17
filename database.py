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
            self.set_system_config("wb_authorization", "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3NjE1NzE2MTgsInVzZXIiOiI1NDU4NDA2MiIsInNoYXJkX2tleSI6IjYiLCJjbGllbnRfaWQiOiJ3YiIsInNlc3Npb25faWQiOiJhZjJjOGI2ZDYxNDc0OTNhODkzYTlkNTY2Y2M0YWU3MyIsInZhbGlkYXRpb25fa2V5IjoiMjViNDExMjQwODdiMzM4YTFkMDBiOWVmYTZhYzlkOGZkYmVlZDRlNDcyMGVlMjQ2ZDdmM2YwMGI5YjFjODAxZCIsInBob25lIjoiSmI5N1U0UTdYa1pBT1I4SWMrUFVkZz09IiwidXNlcl9yZWdpc3RyYXRpb25fZHQiOjE2OTUwNDgzMzksInZlcnNpb24iOjJ9.JRRx-xVmOPm4021i8-RcLd1u3mKy0mAd8Gr182I-a-kf-WPDBRuu1sSUxg-A9xApUsdmZuWVvFIBdFVZHrP16EJkS88ObNJjKtguTf72QDfjn3pcua95vONpV_tOovviYUeN7vr9OgaX9mMEMcDOOdaR__mZMLEVUkkuBx54zblej_xQMtpW6wAYMiqnFi0tIKwR2Csfe_6w0nPUS3PQQ1opbmoH8kXrgbRzDD144Ib73NZo8rwc3BVOkg4a8tINQGuLxInpK8e5F4KN92HGRJdkCD_twsULXMiloZsWA42Biv1uPVCTtt0jr_thSgEpdBb3YfD-aYsZKT9oSkD1uQ")
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Обновленная таблица user_settings без колонок цен
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                discount_percent INTEGER DEFAULT 10,
                price_threshold INTEGER DEFAULT 50,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Новая таблица для хранения цен продуктов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_product_prices (
                user_id INTEGER,
                product_type TEXT NOT NULL,  -- 'iphone_16_128', 'iphone_16_pro_256', 'ps5_slim_disk'
                max_price INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
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
        
        cursor.execute('''
          CREATE TABLE IF NOT EXISTS search_configs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              product_name TEXT NOT NULL,
              product_type TEXT NOT NULL,
              search_queries TEXT NOT NULL,    -- JSON список запросов
              include_keywords TEXT NOT NULL,  -- ✅ НОВОЕ: JSON список обязательных слов
              exclude_keywords TEXT NOT NULL,  -- JSON список исключений
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

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_custom_links (
                user_id INTEGER,
                product_id INTEGER NOT NULL,  -- nm-артикул из ссылки
                initial_price INTEGER NOT NULL,   -- макс. цена, при которой уведомлять
                is_active BOOLEAN DEFAULT 1,
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
          
          # iPhone 16 128GB
          iphone_16_128_config = {
              'product_name': 'iPhone 16 128',
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
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                  "256", "512", "пonepжaнный"
              ], ensure_ascii=False),
          }
          
          # iPhone 16 256GB
          iphone_16_256_config = {
              'product_name': 'iPhone 16 256',
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
                "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный",
                "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                "128", "512", "пonepжaнный"
              ], ensure_ascii=False),
          }
          
          # iPhone 16 Pro 128GB
          iphone_16_pro_128_config = {
              'product_name': 'iPhone 16 Pro 128',
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
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка!", "обменка", "обменный",
                  "256", "512", "1tb", "пonepжaнный"
              ], ensure_ascii=False),
          }
          
          # iPhone 16 Pro 256GB
          iphone_16_pro_256_config = {
              'product_name': 'iPhone 16 Pro 256',
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
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                  "128", "512", "1tb", "пonepжaнный"
              ], ensure_ascii=False),
          }

          # iPhone 16 Pro Max
          iphone_16_pro_max_config = {
              'product_name': 'iPhone 16 Pro Max',
              'product_type': 'iphone_16_pro_max',
              'search_queries': json.dumps([
                  "iPhone 16 Pro Max"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "iphone", "16", "pro", "max"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "15", "14", "13", "11", "7",
                  "16e", "16 e", "16е", "16 е", "plus", "16 128", "16 256", "16 512",
                  "Air", "16 pro 128", "16 pro 256", "16 pro 512", "16 pro 1tb", "iphone 16 s",
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                  "128", "ПonepЖaнHый"
              ], ensure_ascii=False),
          }

          # iPhone 16 Pro Max 256GB
          iphone_16_pro_max_256_config = {
              'product_name': 'iPhone 16 Pro Max 256',
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
                  "Air", "16 pro 128", "16 pro 256", "16 pro 512", "16 pro 1tb", "iphone 16 s",
                  "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "витринный",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
                  "128", "512", "1tb", "ПonepЖaнHый"
              ], ensure_ascii=False),
          }


          # PS5 Slim
          ps5_slim_disk_config = {
              'product_name': 'PlayStation 5 Slim',
              'product_type': 'ps5_slim_disk',
              'search_queries': json.dumps([
                  "playstation 5 slim"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "playstation", "5", "slim"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "digital", "digital edition", "digital version",
                  "без дисковода", "без привода", "бездисковый", "бездисковая",
                  "без диска", "цифровая", "цифровой", "цифровое", "цифровой версии", "4", "4 slim", "ssd-диск", "витринная",
              ], ensure_ascii=False),
          }

          # PS5 Pro
          ps5_pro_config = {
              'product_name': 'PlayStation 5 Pro',
              'product_type': 'ps5_pro',
              'search_queries': json.dumps([
                  "playstation 5 pro"
              ], ensure_ascii=False),
              'include_keywords': json.dumps([  # ✅ Обязательные слова
                  "playstation", "5", "pro"
              ], ensure_ascii=False),
              'exclude_keywords': json.dumps([
                  "4 slim", "4 pro", "5 slim", "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "подержанная", "восстановленная", "отремонтированная", "обменная",
                  "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный", "ssd-диск", "витринная"
              ], ensure_ascii=False),
          }

          # Вставляем конфиги
          configs = [
              iphone_16_128_config, iphone_16_256_config, 
              iphone_16_pro_128_config, iphone_16_pro_256_config, 
              iphone_16_pro_max_config, iphone_16_pro_max_256_config, 
              ps5_slim_disk_config, ps5_pro_config
          ]
          
          for config in configs:
              cursor.execute('''
                  INSERT OR REPLACE INTO search_configs 
                  (product_name, product_type, search_queries, include_keywords, exclude_keywords)
                  VALUES (?, ?, ?, ?, ?)
              ''', (
                  config['product_name'],
                  config['product_type'],
                  config['search_queries'],
                  config['include_keywords'],
                  config['exclude_keywords']
              ))
          
          self.conn.commit()
          print(f"✅ Конфиги для {len(configs)} товаров инициализированы с обязательными словами")

    def add_custom_link(self, user_id: int, product_id: int, initial_price: int):
      cursor = self.conn.cursor()
      cursor.execute('SELECT 1 FROM user_settings WHERE user_id = ?', (user_id,))
      if not cursor.fetchone():
          cursor.execute('INSERT INTO user_settings (user_id) VALUES (?)', (user_id,))
      cursor.execute('''
          INSERT OR REPLACE INTO user_custom_links (user_id, product_id, initial_price, is_active)
          VALUES (?, ?, ?, 0)
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
          WHERE user_id = ? AND is_active = 1
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
            WHERE ucl.product_id = ? AND ucl.is_active = 1
        ''', (product_id,))
        return cursor.fetchall()

    def deactivate_custom_link(self, user_id: int, product_id: int):
        """Отключает отслеживание кастомной ссылки"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE user_custom_links SET is_active = 0
            WHERE user_id = ? AND product_id = ?
        ''', (user_id, product_id))
        self.conn.commit()

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
          UPDATE user_product_prices SET is_active = ? WHERE user_id = ?
      ''', (active, user_id))
      # Обновляем кастомные ссылки
      cursor.execute('''
          UPDATE user_custom_links SET is_active = ? WHERE user_id = ?
      ''', (active, user_id))
      self.conn.commit()

    def get_user_search_active(self, user_id):
      cursor = self.conn.cursor()
      # Проверяем активность в ЛЮБОЙ таблице отслеживания
      cursor.execute('''
          SELECT 1 FROM user_product_prices 
          WHERE user_id = ? AND is_active = 1 AND max_price > 0
          UNION
          SELECT 1 FROM user_custom_links 
          WHERE user_id = ? AND is_active = 1
          LIMIT 1
      ''', (user_id, user_id))
      return cursor.fetchone() is not None

    def get_users_with_active_search(self):
        """Получает всех пользователей с активным поиском"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT user_id FROM user_product_prices 
            WHERE is_active = 1 AND max_price > 0
        ''')
        return [row[0] for row in cursor.fetchall()]

    def get_users_with_any_active_tracking(self):
      """Возвращает всех пользователей, у которых есть хоть одно активное отслеживание (стандартное или кастомное)"""
      cursor = self.conn.cursor()
      cursor.execute('''
          SELECT DISTINCT user_id FROM (
              SELECT user_id FROM user_product_prices WHERE is_active = 1 AND max_price > 0
              UNION
              SELECT user_id FROM user_custom_links WHERE is_active = 1
          )
      ''')
      return [row[0] for row in cursor.fetchall()]
    
    def set_user_product_price(self, user_id, product_type, price):
      """Устанавливает максимальную цену для конкретного товара пользователя"""
      cursor = self.conn.cursor()
      
      # Проверяем, активен ли поиск у пользователя
      is_search_active = self.get_user_search_active(user_id)
      
      cursor.execute('''
          INSERT OR REPLACE INTO user_product_prices 
          (user_id, product_type, max_price, is_active) 
          VALUES (?, ?, ?, ?)
      ''', (user_id, product_type, price, is_search_active))  # is_active зависит от статуса поиска
      
      # Создаем запись в user_settings если её нет
      cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
      if not cursor.fetchone():
          cursor.execute('''
              INSERT INTO user_settings (user_id, discount_percent, price_threshold)
              VALUES (?, 10, 50)
          ''', (user_id,))
      
      self.conn.commit()

    def get_user_product_price(self, user_id, product_type):
        """Получает максимальную цену для конкретного товара пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT max_price FROM user_product_prices 
            WHERE user_id = ? AND product_type = ? AND is_active = 1
        ''', (user_id, product_type))
        result = cursor.fetchone()
        return result[0] if result else 0

    def get_all_user_product_prices(self, user_id):
      """Получает все цены товаров пользователя с информацией о активности"""
      cursor = self.conn.cursor()
      cursor.execute('''
          SELECT product_type, max_price, is_active 
          FROM user_product_prices 
          WHERE user_id = ?
      ''', (user_id,))
      return {row[0]: {'price': row[1], 'active': bool(row[2])} for row in cursor.fetchall()}
    
    def get_all_user_custom_links(self, user_id: int):
      """Возвращает ВСЕ кастомные ссылки пользователя (для отображения в меню)"""
      cursor = self.conn.cursor()
      cursor.execute('''
          SELECT product_id, initial_price, is_active
          FROM user_custom_links
          WHERE user_id = ?
      ''', (user_id,))
      return {row[0]: {'price': row[1], 'active': bool(row[2])} for row in cursor.fetchall()}

    def get_active_user_product_prices(self, user_id):
      """Получает только активные цены товаров пользователя (для обратной совместимости)"""
      cursor = self.conn.cursor()
      cursor.execute('''
          SELECT product_type, max_price 
          FROM user_product_prices 
          WHERE user_id = ? AND is_active = 1
      ''', (user_id,))
      return {row[0]: row[1] for row in cursor.fetchall()}

    def get_users_tracking_product(self, product_type):
        """Получает всех пользователей, отслеживающих конкретный товар"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT up.user_id, up.max_price, us.discount_percent, us.price_threshold
            FROM user_product_prices up
            JOIN user_settings us ON up.user_id = us.user_id
            WHERE up.product_type = ? AND up.is_active = 1 AND up.max_price > 0
        ''', (product_type,))
        return cursor.fetchall()

    def deactivate_user_product(self, user_id, product_type):
        """Деактивирует отслеживание товара для пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE user_product_prices 
            SET is_active = 0 
            WHERE user_id = ? AND product_type = ?
        ''', (user_id, product_type))
        self.conn.commit()

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

    # Остальные методы остаются без изменений

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
            'SELECT product_type, product_name, search_queries, include_keywords, exclude_keywords FROM search_configs WHERE is_active = 1'
        )
        
        configs = {}
        for row in cursor.fetchall():
            configs[row[0]] = {
                'product_name': row[1],
                'search_queries': json.loads(row[2]),
                'include_keywords': json.loads(row[3]),  # ✅ Добавляем обязательные слова
                'exclude_keywords': json.loads(row[4]),
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
                        last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND product_id = ?
                ''', (current_price_int, discount_percent, user_id, product_id))
                
                self.conn.commit()
                print(f"📉 Цена обновлена для товара {product_id}: {existing_price} → {current_price_int}")
                return True, existing_price, True   
            else:
                return False, existing_price, False
                
        else:
            # Новая запись - товар увидели впервые
            cursor.execute('''
                INSERT INTO product_notifications 
                (user_id, product_id, current_price, discount_percent)
                VALUES (?, ?, ?, ?)
            ''', (user_id, product_id, current_price_int, discount_percent))
            
            self.conn.commit()
            print(f"🆕 Новый товар {product_id} добавлен, цена: {current_price_int}")
            return True, None, False
    
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
    user_id = 12345
    database.set_user_product_price(user_id, 'iphone_16_128', 80000)
    database.set_user_product_price(user_id, 'ps5_slim_disk', 50000)
    
    price = database.get_user_product_price(user_id, 'iphone_16_128')
    print(f"Цена iPhone 16 128: {price}")
    
    all_prices = database.get_all_user_product_prices(user_id)
    print(f"Все цены пользователя: {all_prices}")
    
    users_tracking = database.get_users_tracking_product('iphone_16_128')
    print(f"Пользователи отслеживающие iPhone 16 128: {users_tracking}")