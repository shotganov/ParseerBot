import aiohttp
import asyncio
import sqlite3
import math
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import logging
import re

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 7998443497:AAGnYx7to86c-7H7HWcrXQFr4UDuj9ocQ3U
BOT_TOKEN = "8459198512:AAGT_naxAdmepRFAkQMDuG-fmRgbFrTVtSg"

HEADERS = {
    "authority": "u-card.wb.ru",
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
    "origin": "https://www.wildberries.ru",
    "priority": "u=1, i",
    "referer": "https://www.wildberries.ru/",
    "sec-ch-ua": '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0"
}

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
                price_threshold INTEGER DEFAULT 80,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_products (
                user_id INTEGER,
                product_id INTEGER,
                product_type TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, product_id)
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
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                product_id INTEGER,
                product_type TEXT,
                price INTEGER,
                discount_percent INTEGER DEFAULT 7,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user_settings (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_price_history_user_product 
            ON price_history (user_id, product_id, checked_at DESC)
        ''')
        
        self.conn.commit()
    
    def get_user_settings(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT ps5_price, iphone_price, discount_percent, price_threshold FROM user_settings WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result if result else (0, 0, 7, 80)
    
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
                              (user_id, price, 7, 80))
            else:
                cursor.execute('INSERT INTO user_settings (user_id, iphone_price, discount_percent, price_threshold) VALUES (?, ?, ?, ?)', 
                              (user_id, price, 7, 80))
        
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
        """Установка процента скидки для пользователя с обновлением истории цен"""
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
        
        # Если скидка изменилась, обновляем историю цен
        if old_discount != discount_percent:
            self.update_discount_in_price_history(user_id, discount_percent)
    
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
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 1 FROM sent_products 
            WHERE user_id = ? AND product_id = ? AND sent_at > datetime('now', ?)
        ''', (user_id, product_id, f'-{hours} hours'))
        return cursor.fetchone() is not None
    
    def mark_product_sent(self, user_id, product_id, product_type):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO sent_products (user_id, product_id, product_type, sent_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, product_id, product_type))
        self.conn.commit()

    def cleanup_old_records(self, hours=24):
        """Очистка записей старше указанного количества часов"""
        cursor = self.conn.cursor()
        
        cursor.execute('DELETE FROM sent_products WHERE sent_at < datetime("now", ?)', (f"-{hours} hours",))
        sent_deleted = cursor.rowcount
        
        cursor.execute('DELETE FROM price_history WHERE checked_at < datetime("now", ?)', ("-7 days",))
        price_deleted = cursor.rowcount
        
        cursor.execute('DELETE FROM temp_data WHERE created_at < datetime("now", ?)', ("-1 hours",))
        temp_deleted = cursor.rowcount
        
        self.conn.commit()
        return sent_deleted + price_deleted + temp_deleted
    
    def get_previous_price(self, user_id, product_id):
        """Получаем предыдущую цену товара для конкретного пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT price FROM price_history 
            WHERE user_id = ? AND product_id = ? 
            ORDER BY checked_at DESC 
            LIMIT 1
        ''', (user_id, product_id))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def save_price_if_changed(self, user_id, product_id, product_type, current_price, discount_percent):
        """
        Сохраняем или обновляем цену товара для пользователя
        Возвращает: (price_changed, previous_price, price_dropped)
        """
        current_price_int = math.floor(current_price)
        
        # Получаем последнюю запись для этого товара у пользователя
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT price, discount_percent FROM price_history 
            WHERE user_id = ? AND product_id = ? 
            ORDER BY checked_at DESC 
            LIMIT 1
        ''', (user_id, product_id))
        result = cursor.fetchone()
        
        if result is None:
            # Первая запись для этого товара у пользователя - просто вставляем
            cursor.execute('''
                INSERT INTO price_history (user_id, product_id, product_type, price, discount_percent, checked_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, product_id, product_type, current_price_int, discount_percent))
            self.conn.commit()
            return True, None, False
        
        previous_price, previous_discount = result
        
        # Если цена И скидка не изменились - ничего не делаем
        if current_price_int == previous_price and discount_percent == previous_discount:
            return False, previous_price, False
        
        # Если товар уже есть - ОБНОВЛЯЕМ существующую запись
        cursor.execute('''
            UPDATE price_history 
            SET price = ?, discount_percent = ?, checked_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND product_id = ? 
            AND id = (
                SELECT id FROM price_history 
                WHERE user_id = ? AND product_id = ? 
                ORDER BY checked_at DESC 
                LIMIT 1
            )
        ''', (current_price_int, discount_percent, user_id, product_id, user_id, product_id))
        
        self.conn.commit()
        
        price_dropped = current_price_int < previous_price
        return True, previous_price, price_dropped
    
    def update_discount_in_price_history(self, user_id, new_discount_percent):
        """Обновляет процент скидки в актуальных ценах пользователя"""
        cursor = self.conn.cursor()
        
        try:
            # Обновляем скидку только в последних записях каждого товара
            cursor.execute('''
                UPDATE price_history 
                SET discount_percent = ?
                WHERE user_id = ? 
                AND id IN (
                    SELECT ph.id
                    FROM price_history ph
                    INNER JOIN (
                        SELECT product_id, MAX(checked_at) as max_date
                        FROM price_history 
                        WHERE user_id = ?
                        GROUP BY product_id
                    ) latest ON ph.product_id = latest.product_id AND ph.checked_at = latest.max_date
                )
            ''', (new_discount_percent, user_id, user_id))
            
            updated_count = cursor.rowcount
            self.conn.commit()
            
            print(f"✅ Обновлены скидки для {updated_count} товаров пользователя {user_id}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении скидки в истории цен: {e}")
            self.conn.rollback()
            return False
    
    def is_user_waiting_for_input(self, user_id):
        """Проверяет, ожидает ли пользователь ввода (установка цены, порога или скидки)"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT waiting_for_price FROM temp_data WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result is not None and result[0] == 1

# Инициализация базы данных
db = Database()

# Списки для исключения
iphone_exclude_keywords = [
    "15", "14", "13", "11", "iphone 15", "iphone 14", "iphone 13", "iphone 12", "iphone 11", 
    "iphone xr", "iphone xs", "iphone x", "iphone 8", "iphone 7", "iphone 6",
    "16e", "16 e", "16е", "16 е", "16plus", "16 plus", "asis", "iphone 16e", "iphone 16е",
    "восстановленный", "ремоторизованный", "refurbished", "б/у", "used",
    "восстановлен", "отремонтированный"
]

ps5_exclude_keywords = [
    "digital", "digital edition", "digital version",
    "без дисковода", "без привода", "бездисковый", "бездисковая",
    "без диска", "цифровая", "цифровой", "цифровое", "цифровой версии"
]

def should_exclude_product(name, product_type):
    name_lower = name.lower()
    exclude_keywords = ps5_exclude_keywords if product_type == "ps5" else iphone_exclude_keywords
    
    for keyword in exclude_keywords:
        if keyword in name_lower:
            return True
    return False

async def get_products_by_sort(session, product_type):
    """Асинхронно получаем список товаров"""
    products = []
    product_ids = set()
    
    search_queries = []
    if product_type == "ps5":
        search_queries = [
            "playstation 5 slim",
            "playstation 5 slim с дисководом", 
            "playstation 5",
            "ps5 blue-ray",
            "игровая консоль playstation 5",
        ]
    else:
        search_queries = [
            "iPhone 16", "iPhone 16 128gb", "iPhone 16 sim + esim", "iPhone 16 dual sim",
            "iPhone 16 две сим", "iPhone 16 черный", "iPhone 16 белый", "iPhone 16 синий",
            "iPhone 16 розовый", "iPhone 16 бирюзовый", "iPhone 16 purple", "iPhone 16 ultramarine", "Смартфон iPhone 16", 
            "iPhone 16 black", "iPhone 16 white", "iPhone 16 teal", "Apple iPhone 16"
        ]
    
    for search_query in search_queries:
        for page in range(1, 5):
            try:
                url = f"https://search.wb.ru/exactmatch/ru/common/v18/search?ab_testid=reranking_price_6&ab_testing=false&AppType=1&curr=rub&dest=-1586348&hide_dtype=11&inheritFilters=false&lang=ru&page={page}&query={search_query}&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false&uclusters=3"
               
                print(f"🔍 Запрос: {search_query}, страница {page}")
                
                async with session.get(url, timeout=10) as response:
                    response_text = await response.text()
                    
                    try:
                        data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        print(f"❌ Ошибка парсинга JSON для {search_query}: {e}")
                        continue
                
                if "products" not in data:
                    print(f"❌ В ответе нет ключа 'products' для запроса: {search_query}")
                    continue
                
                if not data["products"]:
                    print(f"ℹ️ Нет товаров для запроса: {search_query}")
                    continue
                
                for product in data["products"]:
                    if product["id"] not in product_ids:
                        product_ids.add(product["id"])
                        products.append(product)
                
                print(f"✅ Найдено {len(data['products'])} товаров для '{search_query}'")
                
                if len(data["products"]) < 100:
                    break
                    
            except asyncio.TimeoutError:
                print(f"⏰ Таймаут при запросе: {search_query}")
            except Exception as e:
                print(f"❌ Ошибка при парсинге {product_type}: {e}")
                break
    
    return products

async def get_detailed_product_price(session, product_id, product_type, discount_percent=7):
    """Асинхронно получаем детальную цену товара с учетом скидки пользователя"""
    try:
        discount_multiplier = (100 - discount_percent) / 100
        
        if product_type == "ps5":
            url = f"https://u-card.wb.ru/cards/v4/list?appType=1&curr=rub&dest=-1586348&spp=30&hide_dtype=11&ab_testing=false&ab_testing=false&lang=ru&nm={product_id}&ignore_stocks=true"
            async with session.get(url, headers=HEADERS, timeout=5) as response:
                response_text = await response.text()
                try:
                    req_data = json.loads(response_text)
                except json.JSONDecodeError:
                    return None
            
            if 'products' in req_data and len(req_data['products']) > 0:
                base_price = math.floor(req_data['products'][0]['sizes'][0]['price']['product'])/100
                discounted_price = base_price * discount_multiplier
                return math.floor(discounted_price)
            return None
        else:
            url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={product_id}"
            async with session.get(url, timeout=5) as response:
                response_text = await response.text()
                try:
                    req_data = json.loads(response_text)
                except json.JSONDecodeError:
                    return None
            
            if 'data' in req_data and 'products' in req_data['data'] and len(req_data['data']['products']) > 0:
                base_price = math.floor(req_data['data']['products'][0]['sizes'][0]['price']['product'])/100
                discounted_price = base_price * discount_multiplier
                return math.floor(discounted_price)
            return None
    except Exception as e:
        print(f"❌ Ошибка при получении детальной цены для {product_id}: {e}")
        return None

async def filter_products_for_user(application, user_id, user_ps5_price, user_iphone_price, discount_percent, price_threshold, all_ps5_products, all_iphone_products, session):
    """Фильтруем товары для конкретного пользователя с учетом его скидки и автоматического порога"""
    
    if db.is_user_waiting_for_input(user_id):
        print(f"⏸️ Пользователь {user_id} ожидает ввода, пропускаем проверку цен")
        return
    
    found_ps5_products = []
    found_iphone_products = []
    
    if user_ps5_price > 0:
        ps5_min_price = math.floor(user_ps5_price * (price_threshold / 100))
        print(f"🔍 Фильтрация PS5 для пользователя {user_id}, цена: {user_ps5_price}, порог: {price_threshold}% (мин. {ps5_min_price} руб.), скидка: {discount_percent}%")
        
        for product in all_ps5_products:
            name = str(product["name"])
            base_price = math.floor(product['sizes'][0]['price']['product'])/100
            initial_discounted_price = base_price * ((100 - discount_percent) / 100)
            
            if should_exclude_product(name.lower(), "ps5"):
                continue
            
            if initial_discounted_price < user_ps5_price + 2000 and initial_discounted_price > ps5_min_price:
                detailed_price = await get_detailed_product_price(session, product['id'], 'ps5', discount_percent)
                if detailed_price and detailed_price < user_ps5_price and detailed_price > user_ps5_price/2:
                    
                    # ИСПОЛЬЗУЕМ ОБНОВЛЕННЫЙ МЕТОД с user_id и discount_percent
                    price_changed, previous_price, price_dropped = db.save_price_if_changed(
                        user_id, product['id'], 'ps5', detailed_price, discount_percent
                    )
                    never_sent = not db.is_product_sent_recently(user_id, product['id'])
                    
                    if never_sent or price_dropped:
                        print(f"✅ Найден подходящий PS5: {name} за {detailed_price} руб. (со скидкой {discount_percent}%) "
                              f"({'цена упала' if price_dropped else 'новый товар'})")
                        
                        found_ps5_products.append({
                            'id': product['id'],
                            'name': name,
                            'price': detailed_price,
                            'previous_price': previous_price,
                            'price_dropped': price_dropped,
                            'link': f"https://www.wildberries.ru/catalog/{product['id']}/detail.aspx",
                            'discount_percent': discount_percent
                        })
    
    if user_iphone_price > 0:
        iphone_min_price = math.floor(user_iphone_price * (price_threshold / 100))
        print(f"🔍 Фильтрация iPhone для пользователя {user_id}, цена: {user_iphone_price}, порог: {price_threshold}% (мин. {iphone_min_price} руб.), скидка: {discount_percent}%")
        
        for product in all_iphone_products:
            name = str(product["name"])
            base_price = math.floor(product['sizes'][0]['price']['product'])/100
            initial_discounted_price = base_price * ((100 - discount_percent) / 100)
            
            if should_exclude_product(name.lower(), "iphone"):
                continue
            
            if initial_discounted_price < user_iphone_price and initial_discounted_price > iphone_min_price:
                detailed_price = await get_detailed_product_price(session, product['id'], 'iphone', discount_percent)
                if detailed_price and detailed_price < user_iphone_price and detailed_price > user_iphone_price/2:
                    
                    # ИСПОЛЬЗУЕМ ОБНОВЛЕННЫЙ МЕТОД с user_id и discount_percent
                    price_changed, previous_price, price_dropped = db.save_price_if_changed(
                        user_id, product['id'], 'iphone', detailed_price, discount_percent
                    )
                    never_sent = not db.is_product_sent_recently(user_id, product['id'])
                    
                    if never_sent or price_dropped:
                        print(f"✅ Найден подходящий iPhone: {name} за {detailed_price} руб. (со скидкой {discount_percent}%) "
                              f"({'цена упала' if price_dropped else 'новый товар'})")
                        
                        found_iphone_products.append({
                            'id': product['id'],
                            'name': name,
                            'price': detailed_price,
                            'previous_price': previous_price,
                            'price_dropped': price_dropped,
                            'link': f"https://www.wildberries.ru/catalog/{product['id']}/detail.aspx",
                            'discount_percent': discount_percent
                        })
    
    # СОРТИРОВКА ПО ВОЗРАСТАНИЮ ЦЕНЫ
    if found_ps5_products:
        found_ps5_products.sort(key=lambda x: x['price'])
    
    if found_iphone_products:
        found_iphone_products.sort(key=lambda x: x['price'])
    
    if found_ps5_products:
        message = "🎮 Найдены PS5 по выгодным ценам (отсортировано по возрастанию цены):\n\n"
        for product in found_ps5_products:
            if product['price_dropped'] and product['previous_price']:
                price_drop = product['previous_price'] - product['price']
                price_drop_percent = (price_drop / product['previous_price']) * 100
                message += f"📦 {product['name']}\n"
                message += f"💰 Цена: {product['price']:,} руб. (была {product['previous_price']:,} руб.)\n".replace(',', ' ')
                message += f"📉 Снижение: {price_drop:,} руб. ({price_drop_percent:.1f}%)\n".replace(',', ' ')
            else:
                message += f"📦 {product['name']}\n💰 Цена: {product['price']:,} руб.\n".replace(',', ' ')
            message += f"🔗 {product['link']}\n\n"
        
        try:
            await application.bot.send_message(chat_id=user_id, text=message, reply_markup=get_main_reply_keyboard())
            
            for product in found_ps5_products:
                db.mark_product_sent(user_id, product['id'], 'ps5')
            
            print(f"✅ Отправлено уведомление пользователю {user_id} о {len(found_ps5_products)} PS5")
        except Exception as e:
            print(f"❌ Ошибка отправки сообщения пользователю {user_id}: {e}")
    
    if found_iphone_products:
        message = "📱 Найдены iPhone 16 по выгодным ценам (отсортировано по возрастанию цены):\n\n"
        for product in found_iphone_products:
            if product['price_dropped'] and product['previous_price']:
                price_drop = product['previous_price'] - product['price']
                price_drop_percent = (price_drop / product['previous_price']) * 100
                message += f"📦 {product['name']}\n"
                message += f"💰 Цена: {product['price']:,} руб. (была {product['previous_price']:,} руб.)\n".replace(',', ' ')
                message += f"📉 Снижение: {price_drop:,} руб. ({price_drop_percent:.1f}%)\n".replace(',', ' ')
            else:
                message += f"📦 {product['name']}\n💰 Цена: {product['price']:,} руб.\n".replace(',', ' ')
            message += f"🔗 {product['link']}\n\n"
        
        try:
            await application.bot.send_message(chat_id=user_id, text=message, reply_markup=get_main_reply_keyboard())
            
            for product in found_iphone_products:
                db.mark_product_sent(user_id, product['id'], 'iphone')
            
            print(f"✅ Отправлено уведомление пользователю {user_id} о {len(found_iphone_products)} iPhone")
        except Exception as e:
            print(f"❌ Ошибка отправки сообщения пользователю {user_id}: {e}")

async def check_all_prices(application):
    """Асинхронная проверка цен для всех пользователей"""
    try:
        deleted = db.cleanup_old_records(hours=24)
        if deleted > 0:
            print(f"🗑️ Очищено {deleted} старых записей")
            
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=connector) as session:
            print("🔄 Начинаем сбор товаров...")
            
            all_ps5_products, all_iphone_products = await asyncio.gather(
                get_products_by_sort(session, "ps5"),
                get_products_by_sort(session, "iphone"),
                return_exceptions=True
            )
            
            if isinstance(all_ps5_products, Exception):
                print(f"❌ Ошибка при парсинге PS5: {all_ps5_products}")
                all_ps5_products = []
            if isinstance(all_iphone_products, Exception):
                print(f"❌ Ошибка при парсинге iPhone: {all_iphone_products}")
                all_iphone_products = []
            
            print(f"📦 Найдено {len(all_ps5_products)} PS5 и {len(all_iphone_products)} iPhone")
            
            users = db.get_all_users()
            print(f"👥 Обрабатываем {len(users)} пользователей")
            
            for user_id, ps5_price, iphone_price, discount_percent, price_threshold in users:
                # Проверяем, не ожидает ли пользователь ввода
                if db.is_user_waiting_for_input(user_id):
                    print(f"⏸️ Пропускаем пользователя {user_id} - ожидает ввода")
                    continue
                    
                if ps5_price > 0 or iphone_price > 0:
                    await filter_products_for_user(
                        application, user_id, ps5_price, iphone_price, discount_percent, price_threshold,
                        all_ps5_products, all_iphone_products, session
                    )
            
            print("✅ Проверка цен завершена")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке цен: {e}")

async def price_checker_job(context):
    """Фоновая задача для проверки цен"""
    await check_all_prices(context.application)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - показывает описание бота и основные кнопки"""
    user_id = update.effective_user.id
    ps5_price, iphone_price, discount_percent, price_threshold = db.get_user_settings(user_id)
    
    message = (
        "🤖 **Бот мониторинга цен на Wildberries**\n\n"
        "**Что умеет этот бот:**\n"
        "• Автоматически ищет PS5 и iPhone 16 по вашим ценам\n"
        "• Применяет скидку WB при расчете стоимости\n"
        "• Отслеживает снижение цен\n\n"
        "💡 **Как пользоваться:**\n"
        '1. Нажмите «🤖 **Парсер**» - чтобы настроить цены для поиска\n'
        '2. Нажмите «⚙️ **Настройки**» - чтобы изменить скидку и пороги\n'
        "3. Ждите уведомлений о найденных товарах!\n\n"
    )
    
    try:
        await update.message.reply_text(
            message, 
            parse_mode='Markdown',
            reply_markup=get_main_reply_keyboard()
        )
        # Отправляем кнопки для навигации
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения: {e}")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню"""
    user_id = update.effective_user.id
    ps5_price, iphone_price, discount_percent, price_threshold = db.get_user_settings(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🎮 Установить цену PS5", callback_data="set_ps5_price")],
        [InlineKeyboardButton("📱 Установить цену iPhone 16", callback_data="set_iphone_price")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "**Главное меню**\n\n"
        "⚙️ **Ваши текущие настройки:**\n"
        f"🎮 PS5: {ps5_price if ps5_price > 0 else 'Не установлена'} руб.\n"
        f"📱 iPhone 16: {iphone_price if iphone_price > 0 else 'Не установлена'} руб.\n"
        f"💸 Скидка WB: {discount_percent}%\n\n"
        "💡 **Выберите действие:**"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для кнопки Меню под клавиатурой"""
    await show_main_menu(update, context)

# Создаем Reply клавиатуру (постоянная клавиатура внизу)
def get_main_reply_keyboard():
    """Создает основную Reply клавиатуру"""
    keyboard = [
        [KeyboardButton("🤖 Парсер")],
        [KeyboardButton("⚙️ Настройки")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню настроек"""
    user_id = update.effective_user.id
    ps5_price, iphone_price, discount_percent, price_threshold = db.get_user_settings(user_id)
    
    keyboard = [
        [InlineKeyboardButton("💸 Установить скидку", callback_data="set_discount")],
        [InlineKeyboardButton("📉 Автоматический минимальный порог", callback_data="set_threshold")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "Выберите что хотите настроить:\n\n"
        f"💸 **Текущая скидка WB:** {discount_percent}%\n"
        f"📉 **Автоматический порог:** {price_threshold}%"
    )
    
    # Если это callback query (нажатие кнопки), редактируем сообщение
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        # Если это текстовое сообщение, отправляем новое
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_reply_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на Reply кнопки"""
    text = update.message.text
    
    if text == "🤖 Парсер":
        await show_main_menu(update, context)
    
    elif text == "⚙️ Настройки":
        await show_settings_menu(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline-кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "set_ps5_price":
        db.set_waiting_for_price(user_id, 1, 'ps5')
        await query.edit_message_text(
            "🎮 **Установка цены для PS5**\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "💡 **Пример:** 50000\n\n"
            "🔍 Бот будет искать PS5 в диапазоне согласно вашему автоматическому порогу.",
            parse_mode='Markdown'
        )
    
    elif data == "set_iphone_price":
        db.set_waiting_for_price(user_id, 1, 'iphone')
        await query.edit_message_text(
            "📱 **Установка цены для iPhone 16**\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "💡 **Пример:** 80000\n\n"
            "🔍 Бот будет искать iPhone 16 в диапазоне согласно вашему автоматическому порогу.",
            parse_mode='Markdown'
        )
    
    elif data == "set_discount":
        db.set_waiting_for_price(user_id, 1, 'discount')
        await query.edit_message_text(
            "🏷️ **Установка процента скидки**\n\n"
            "Введите процент скидки WB (только цифры):\n\n"
            "💡 **Пример:** 7\n\n"
            "ℹ️ Бот будет применять эту скидку при расчете итоговой цены.",
            parse_mode='Markdown'
        )
    
    elif data == "set_threshold":
        db.set_waiting_for_price(user_id, 1, 'threshold')
        await query.edit_message_text(
            "📉 **Автоматический минимальный порог**\n\n"
            "Эта функция избавляет вас от необходимости каждый раз вручную указывать диапазон цен.\n\n"
            "**Как это работает?**\n"
            "Вы задаете процент, и бот сам рассчитывает минимальную цену для отслеживания.\n\n"
            "**Например:**\n"
            "- Вы ставите порог: 70%\n"
            "- Добавляете товар с ценой: 10 000 ₽\n"
            "- Бот будет автоматически отслеживать его в диапазоне от 7 000 ₽ до 10 000 ₽.\n\n"
            "**Текущее значение:** 80%\n\n"
            "Введите процент от 0 до 100. Чтобы отключить, введите 0.",
            parse_mode='Markdown'
        )
    
    elif data == "back_to_main":
        await show_main_menu(update, context)
    elif data == "back_to_settings":
        await show_settings_menu(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений для установки цен, автоматического порога и скидки"""
    user_id = update.effective_user.id
    waiting_for_price, product_type = db.get_waiting_for_price(user_id)
    
    if waiting_for_price and product_type:
        text = update.message.text.strip()
        
        if not re.match(r'^\d+$', text):
            await update.message.reply_text(
                "❌ Пожалуйста, введите только цифры (без пробелов, букв и других символов)\n\n"
                "💡 **Пример:** 50000",
                reply_markup=get_main_reply_keyboard()
            )
            return
        
        try:
            value = int(text)
            
            if product_type == 'discount':
                if value <= 0 or value > 50:
                    await update.message.reply_text(
                        "❌ Скидка должна быть от 1% до 50%",
                        reply_markup=get_main_reply_keyboard()
                    )
                    return
                
                # Получаем старую скидку для информационного сообщения
                _, _, old_discount, _ = db.get_user_settings(user_id)
                    
                # Устанавливаем новую скидку (метод автоматически обновит историю цен)
                db.set_user_discount(user_id, value)
                db.clear_waiting_for_price(user_id)
                
                # Создаем inline-клавиатуру с кнопкой "На главную"
                keyboard = [
                    [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                message = (
                    f"✅ **Процент скидки изменен:** {old_discount}% → {value}%\n\n"
                    f"Теперь бот будет применять {value}% скидку при расчете цен.\n\n"
                )
                
                await update.message.reply_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
            elif product_type == 'threshold':
                if value < 0 or value > 100:
                    await update.message.reply_text(
                        "❌ Порог должен быть от 0% до 100%",
                        reply_markup=get_main_reply_keyboard()
                    )
                    return
                
                db.set_user_threshold(user_id, value)
                db.clear_waiting_for_price(user_id)
                
                # Создаем inline-клавиатуру с кнопкой "На главную"
                keyboard = [
                    [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                if value > 0:
                    
                    await update.message.reply_text(
                        f"✅ **Автоматический порог установлен:** {value}%\n\n"
                        f"Теперь бот будет искать товары в диапазоне от {value}% до 100% от указанной вами цены.",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        f"✅ **Автоматический порог отключен**\n\n"
                        f"Теперь бот будет искать товары от 0 до указанной вами цены.",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
            
            elif product_type in ['ps5', 'iphone']:
                if value <= 0:
                    await update.message.reply_text(
                        "❌ Цена должна быть положительным числом",
                        reply_markup=get_main_reply_keyboard()
                    )
                    return
                
                # Сохраняем цену
                db.set_user_price(user_id, product_type, value)
                db.clear_waiting_for_price(user_id)
                
                product_name = "PS5" if product_type == "ps5" else "iPhone 16"
                
                # Получаем текущий порог для отображения диапазона
                _, _, _, price_threshold = db.get_user_settings(user_id)
                
                if price_threshold > 0:
                    min_price = math.floor(value * (price_threshold / 100))
                    range_info = f"{min_price:,} - {value:,} руб.".replace(',', ' ')
                else:
                    range_info = f"от 0 до {value:,} руб.".replace(',', ' ')
                
                # Создаем inline-клавиатуру с кнопкой "На главную"
                keyboard = [
                    [InlineKeyboardButton("⬅️ На главную", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ **Максимальная цена для {product_name} установлена:** {value:,} руб.\n\n".replace(',', ' ') +
                    f"**Диапазон поиска:** {range_info}\n\n" +
                    f"🔍 Бот будет искать {product_name} в диапазоне: {range_info}\n",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
        except ValueError:
            await update.message.reply_text(
                "❌ Укажите корректное значение (только цифры)",
                reply_markup=get_main_reply_keyboard()
            )
    else:
        # Если пользователь отправил текст без контекста - показываем главное меню
        await show_main_menu(update, context)

def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_button))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик для Reply клавиатуры
    application.add_handler(MessageHandler(filters.Text(["🤖 Парсер", "⚙️ Настройки"]), handle_reply_keyboard))
    
    # Обработчик для текстовых сообщений (цен и скидок)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(price_checker_job, interval=60, first=10)
        print("✅ JobQueue запущен")
    else:
        print("❌ JobQueue не доступен, используем альтернативный метод")
        async def run_checks():
            while True:
                await check_all_prices(application)
                await asyncio.sleep(60)
        asyncio.create_task(run_checks())
    
    print("🤖 Бот запущен!")
    application.run_polling()

if __name__ == "__main__":
    main()