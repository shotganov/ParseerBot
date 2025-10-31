
import sqlite3
import math
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('price_monitor.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                ps5_price INTEGER DEFAULT 0,
                iphone_price INTEGER DEFAULT 0,
                discount_percent INTEGER DEFAULT 7,
                price_threshold INTEGER DEFAULT 50,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_notifications (
                user_id INTEGER,
                product_id INTEGER,
                current_price INTEGER,  
                discount_percent INTEGER DEFAULT 7,
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
        
        # cursor.execute('''
        #     CREATE INDEX IF NOT EXISTS idx_product_notifications_user_product 
        #     ON product_notifications (user_id, product_id, sent_at DESC)
        # ''')
        
        # cursor.execute('''
        #     CREATE INDEX IF NOT EXISTS idx_product_notifications_sent_at 
        #     ON product_notifications (sent_at)
        # ''')
        
        self.conn.commit()
    
    def get_user_settings(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT discount_percent, price_threshold FROM user_settings WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result if result else (0, 0, 7, 50)
    
    def set_user_price(self, user_id, product_type, price):
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            if product_type == 'ps5':
                cursor.execute('UPDATE user_settings SET ps5_price = ? WHERE user_id = ?', (price, user_id))
            else:
                cursor.execute('UPDATE user_settings SET iphone_price = ? WHERE user_id = ?', (price, user_id))
        else:
            if product_type == 'ps5':
                cursor.execute('INSERT INTO user_settings (user_id, ps5_price, discount_percent, price_threshold) VALUES (?, ?, ?, ?)', 
                              (user_id, price, 7, 50))
            else:
                cursor.execute('INSERT INTO user_settings (user_id, iphone_price, discount_percent, price_threshold) VALUES (?, ?, ?, ?)', 
                              (user_id, price, 7, 50))
        
        self.conn.commit()
    
    def set_user_threshold(self, user_id, threshold):
        """Установка общего автоматического порога для пользователя"""
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            cursor.execute('UPDATE user_settings SET price_threshold = ? WHERE user_id = ?', (threshold, user_id))
        else:
            cursor.execute('INSERT INTO user_settings (user_id, price_threshold, discount_percent) VALUES (?, ?, ?)', 
                          (user_id, threshold, 7))
        
        self.conn.commit()
    
    def set_user_discount(self, user_id, discount_percent):
        """Установка процента скидки для пользователя с обновлением истории уведомлений"""
        cursor = self.conn.cursor()
        
        # Получаем старую скидку
        old_discount = 7  # значение по умолчанию
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
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id, ps5_price, iphone_price, discount_percent, price_threshold FROM user_settings')
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
