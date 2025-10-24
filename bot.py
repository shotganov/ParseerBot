import aiohttp
import asyncio
import sqlite3
import time
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import logging
import re

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

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
                product_id INTEGER,
                product_type TEXT,
                price INTEGER,  -- Изменено на INTEGER для хранения целых чисел
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_price_history_product_id 
            ON price_history (product_id, checked_at DESC)
        ''')
        
        self.conn.commit()
    
    def get_user_settings(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT ps5_price, iphone_price FROM user_settings WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result if result else (0, 0)
    
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
                cursor.execute('INSERT INTO user_settings (user_id, ps5_price) VALUES (?, ?)', (user_id, price))
            else:
                cursor.execute('INSERT INTO user_settings (user_id, iphone_price) VALUES (?, ?)', (user_id, price))
        
        self.conn.commit()
    
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
    
    def is_product_sent_recently(self, user_id, product_id, hours=6):
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
    
    def get_all_users(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id, ps5_price, iphone_price FROM user_settings')
        return cursor.fetchall()

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
    
    def get_previous_price(self, product_id):
        """Получаем предыдущую цену товара (последнюю записанную)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT price FROM price_history 
            WHERE product_id = ? 
            ORDER BY checked_at DESC 
            LIMIT 1
        ''', (product_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def save_price_if_changed(self, product_id, product_type, current_price):
        """
        Сохраняем цену ТОЛЬКО если она изменилась
        Возвращает: (price_changed, previous_price, price_dropped)
        """
        # Конвертируем цену в целое число
        current_price_int = int(round(current_price))
        previous_price = self.get_previous_price(product_id)
        
        # Если это первый раз видим товар - сохраняем
        if previous_price is None:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO price_history (product_id, product_type, price, checked_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (product_id, product_type, current_price_int))
            self.conn.commit()
            return True, None, False
        
        # Если цена не изменилась - ничего не делаем
        if current_price_int == previous_price:
            return False, previous_price, False
        
        # Если цена изменилась - сохраняем новую цену
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO price_history (product_id, product_type, price, checked_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (product_id, product_type, current_price_int))
        self.conn.commit()
        
        # Определяем, упала ли цена
        price_dropped = current_price_int < previous_price
        return True, previous_price, price_dropped

# Инициализация базы данных
db = Database()

# Списки для исключения
iphone_exclude_keywords = [
    "15", "14", "13", "11", "iphone 15", "iphone 14", "iphone 13", "iphone 12", "iphone 11", 
    "iphone xr", "iphone xs", "iphone x", "iphone 8", "iphone 7", "iphone 6",
    "16e", "16 e", "16 plus", "16 plus",
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
            "игровая консоль playstation 5",
        ]
    else:
        search_queries = [
            "iPhone 16", "iPhone 16 128gb", "iPhone 16 sim + esim", "iPhone 16 dual sim",
            "iPhone 16 две сим", "iPhone 16 черный", "iPhone 16 белый", "iPhone 16 синий",
            "iPhone 16 розовый", "iPhone 16 бирюзовый", "iPhone 16 purple", "iPhone 16 ultramarine",
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

async def get_detailed_product_price(session, product_id, product_type):
    """Асинхронно получаем детальную цену товара"""
    try:
        if product_type == "ps5":
            url = f"https://u-card.wb.ru/cards/v4/list?appType=1&curr=rub&dest=-1586348&spp=30&hide_dtype=11&ab_testing=false&ab_testing=false&lang=ru&nm={product_id}&ignore_stocks=true"
            async with session.get(url, headers=HEADERS, timeout=5) as response:
                response_text = await response.text()
                try:
                    req_data = json.loads(response_text)
                except json.JSONDecodeError:
                    return None
            
            if 'products' in req_data and len(req_data['products']) > 0:
                price = int(req_data['products'][0]['sizes'][0]['price']['product'])/100 * 0.93
                return int(round(price))  # Конвертируем в целое число
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
                price = int(req_data['data']['products'][0]['sizes'][0]['price']['product'])/100 * 0.93
                return int(round(price))  # Конвертируем в целое число
            return None
    except Exception as e:
        print(f"❌ Ошибка при получении детальной цены для {product_id}: {e}")
        return None

async def filter_products_for_user(application, user_id, user_ps5_price, user_iphone_price, all_ps5_products, all_iphone_products, session):
    """Фильтруем товары для конкретного пользователя"""
    found_ps5_products = []
    found_iphone_products = []
    
    # Фильтрация PS5
    if user_ps5_price > 0:
        print(f"🔍 Фильтрация PS5 для пользователя {user_id}, цена: {user_ps5_price}")
        for product in all_ps5_products:
            name = str(product["name"])
            initial_price = int(product['sizes'][0]['price']['product'])/100 * 0.93
            
            if should_exclude_product(name.lower(), "ps5"):
                continue
            
            if initial_price < user_ps5_price + 2000 and initial_price > user_ps5_price - 10000:
                detailed_price = await get_detailed_product_price(session, product['id'], 'ps5')
                if detailed_price and detailed_price < user_ps5_price and detailed_price > user_ps5_price/2:
                    
                    price_changed, previous_price, price_dropped = db.save_price_if_changed(product['id'], 'ps5', detailed_price)
                    never_sent = not db.is_product_sent_recently(user_id, product['id'])
                    
                    if never_sent or price_dropped:
                        print(f"✅ Найден подходящий PS5: {name} за {detailed_price} руб. "
                              f"({'цена упала' if price_dropped else 'новый товар'})")
                        
                        found_ps5_products.append({
                            'id': product['id'],
                            'name': name,
                            'price': detailed_price,
                            'previous_price': previous_price,
                            'price_dropped': price_dropped,
                            'link': f"https://www.wildberries.ru/catalog/{product['id']}/detail.aspx"
                        })
    
    # Фильтрация iPhone
    if user_iphone_price > 0:
        print(f"🔍 Фильтрация iPhone для пользователя {user_id}, цена: {user_iphone_price}")
        for product in all_iphone_products:
            name = str(product["name"])
            initial_price = int(product['sizes'][0]['price']['product'])/100 * 0.93
            
            if should_exclude_product(name.lower(), "iphone"):
                continue
            
            if initial_price < user_iphone_price and initial_price > user_iphone_price - 10000:
                detailed_price = await get_detailed_product_price(session, product['id'], 'iphone')
                if detailed_price and detailed_price < user_iphone_price and detailed_price > user_iphone_price/2:
                    
                    price_changed, previous_price, price_dropped = db.save_price_if_changed(product['id'], 'iphone', detailed_price)
                    never_sent = not db.is_product_sent_recently(user_id, product['id'])
                    
                    if never_sent or price_dropped:
                        print(f"✅ Найден подходящий iPhone: {name} за {detailed_price} руб. "
                              f"({'цена упала' if price_dropped else 'новый товар'})")
                        
                        found_iphone_products.append({
                            'id': product['id'],
                            'name': name,
                            'price': detailed_price,
                            'previous_price': previous_price,
                            'price_dropped': price_dropped,
                            'link': f"https://www.wildberries.ru/catalog/{product['id']}/detail.aspx"
                        })
    
    # Отправка уведомлений
    if found_ps5_products:
        message = "🎮 Найдены PS5 по выгодным ценам:\n\n"
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
            await application.bot.send_message(chat_id=user_id, text=message)
            
            for product in found_ps5_products:
                db.mark_product_sent(user_id, product['id'], 'ps5')
            
            print(f"✅ Отправлено уведомление пользователю {user_id} о {len(found_ps5_products)} PS5")
        except Exception as e:
            print(f"❌ Ошибка отправки сообщения пользователю {user_id}: {e}")
    
    if found_iphone_products:
        message = "📱 Найдены iPhone 16 по выгодным ценам:\n\n"
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
            await application.bot.send_message(chat_id=user_id, text=message)
            
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
            
            for user_id, ps5_price, iphone_price in users:
                if ps5_price > 0 or iphone_price > 0:
                    await filter_products_for_user(
                        application, user_id, ps5_price, iphone_price, 
                        all_ps5_products, all_iphone_products, session
                    )
            
            print("✅ Проверка цен завершена")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке цен: {e}")

async def price_checker_job(context):
    """Фоновая задача для проверки цен"""
    await check_all_prices(context.application)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user_id = update.effective_user.id
    ps5_price, iphone_price = db.get_user_settings(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🎮 Установить цену PS5", callback_data="set_ps5_price")],
        [InlineKeyboardButton("📱 Установить цену iPhone 16", callback_data="set_iphone_price")],
        [InlineKeyboardButton("📊 Мои текущие цены", callback_data="my_prices")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "🤖 Бот мониторинга цен на Wildberries\n\n"
        "Используйте кнопки ниже для настройки цен:\n\n"
        f"🎮 PS5: {ps5_price if ps5_price > 0 else 'не установлена'} руб.\n"
        f"📱 iPhone 16: {iphone_price if iphone_price > 0 else 'не установлена'} руб.\n\n"
        "Бот проверяет цены каждую минуту и пришлет уведомление, если найдет товары по вашим условиям."
    )
    
    try:
        await update.message.reply_text(message, reply_markup=reply_markup)
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "set_ps5_price":
        db.set_waiting_for_price(user_id, 1, 'ps5')
        await query.edit_message_text(
            "🎮 Установка цены для PS5\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "Пример: 50000\n\n"
            "Бот будет искать PS5 в диапазоне: (ваша_цена - 10000) - ваша_цена руб."
        )
    
    elif data == "set_iphone_price":
        db.set_waiting_for_price(user_id, 1, 'iphone')
        await query.edit_message_text(
            "📱 Установка цены для iPhone 16\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "Пример: 80000\n\n"
            "Бот будет искать iPhone 16 в диапазоне: (ваша_цена - 10000) - ваша_цена руб."
        )
    
    elif data == "my_prices":
        ps5_price, iphone_price = db.get_user_settings(user_id)
        
        keyboard = [
            [InlineKeyboardButton("🎮 Изменить цену PS5", callback_data="set_ps5_price")],
            [InlineKeyboardButton("📱 Изменить цену iPhone", callback_data="set_iphone_price")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "📊 Ваши текущие настройки:\n\n"
            f"🎮 PS5: {ps5_price if ps5_price > 0 else 'не установлена'} руб.\n"
            f"📱 iPhone 16: {iphone_price if iphone_price > 0 else 'не установлена'} руб.\n\n"
            "Условия поиска:\n"
            "- Цена < вашей максимальной цены\n"
            "- Цена > (ваша цена - 10000)\n" 
            "- После проверки: цена > половины вашей цены\n"
            "- Исключены цифровые версии PS5 и старые iPhone\n\n"
            "Бот проверяет цены каждую минуту!"
        )
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    elif data == "back_to_main":
        ps5_price, iphone_price = db.get_user_settings(user_id)
        
        keyboard = [
            [InlineKeyboardButton("🎮 Установить цену PS5", callback_data="set_ps5_price")],
            [InlineKeyboardButton("📱 Установить цену iPhone 16", callback_data="set_iphone_price")],
            [InlineKeyboardButton("📊 Мои текущие цены", callback_data="my_prices")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "🤖 Бот мониторинга цен на Wildberries\n\n"
            "Используйте кнопки ниже для настройки цен:\n\n"
            f"🎮 PS5: {ps5_price if ps5_price > 0 else 'не установлена'} руб.\n"
            f"📱 iPhone 16: {iphone_price if iphone_price > 0 else 'не установлена'} руб.\n\n"
            "Бот проверяет цены каждую минуту и пришлет уведомление, если найдет товары по вашим условиям."
        )
        await query.edit_message_text(message, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений для установки цен"""
    user_id = update.effective_user.id
    waiting_for_price, product_type = db.get_waiting_for_price(user_id)
    
    if waiting_for_price and product_type:
        text = update.message.text.strip()
        
        if not re.match(r'^\d+$', text):
            await update.message.reply_text(
                "❌ Пожалуйста, введите только цифры (без пробелов, букв и других символов)\n\n"
                "Пример: 50000"
            )
            return
        
        try:
            price = int(text)
            if price <= 0:
                await update.message.reply_text("❌ Цена должна быть положительным числом")
                return
                
            db.set_user_price(user_id, product_type, price)
            db.clear_waiting_for_price(user_id)
            
            product_name = "PS5" if product_type == "ps5" else "iPhone 16"
            product_emoji = "🎮" if product_type == "ps5" else "📱"
            
            keyboard = [
                [InlineKeyboardButton("🔙 На главную", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"{product_emoji} ✅ Максимальная цена для {product_name} установлена: {price:,} руб.\n\n".replace(',', ' ') +
                f"Бот будет искать {product_name} в диапазоне: {price-10000:,} - {price:,} руб.\n".replace(',', ' ') +
                "И присылать списком одним сообщением.",
                reply_markup=reply_markup
            )
            
        except ValueError:
            await update.message.reply_text("❌ Укажите корректную цену (только цифры)")
    else:
        await start(update, context)

async def my_prices_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /myprices для обратной совместимости"""
    user_id = update.effective_user.id
    ps5_price, iphone_price = db.get_user_settings(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🎮 Изменить цену PS5", callback_data="set_ps5_price")],
        [InlineKeyboardButton("📱 Изменить цену iPhone", callback_data="set_iphone_price")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "📊 Ваши текущие настройки:\n\n"
        f"🎮 PS5: {ps5_price if ps5_price > 0 else 'не установлена'} руб.\n"
        f"📱 iPhone 16: {iphone_price if iphone_price > 0 else 'не установлена'} руб.\n\n"
        "Условия поиска:\n"
        "- Цена < вашей максимальной цены\n"
        "- Цена > (ваша цена - 10000)\n" 
        "- После проверки: цена > половины вашей цены\n"
        "- Исключены цифровые версии PS5 и старые iPhone\n\n"
        "Бот проверяет цены каждую минуту!"
    )
    await update.message.reply_text(message, reply_markup=reply_markup)

def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myprices", my_prices_command))
    application.add_handler(CallbackQueryHandler(button_handler))
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
    
    print("🤖 Бот запущен с целыми ценами!")
    print("📊 Особенности:")
    print("- Цены сохраняются как целые числа")
    print("- В уведомлениях отображаются целые числа")
    print("- Форматирование с пробелами для тысяч")
    print("- Сохраняем цены только при изменении")
    
    application.run_polling()

if __name__ == "__main__":
    main()