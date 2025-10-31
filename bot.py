import aiohttp
import asyncio
import sqlite3
import math
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import logging
import re
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

#BOT_TOKEN = "8459198512:AAGT_naxAdmepRFAkQMDuG-fmRgbFrTVtSg"
BOT_TOKEN = "7998443497:AAGnYx7to86c-7H7HWcrXQFr4UDuj9ocQ3U"

HEADERS_FIRST = {
    "authority": "u-card.wb.ru",
    "authorization" : "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3NjE1NzE2MTgsInVzZXIiOiI1NDU4NDA2MiIsInNoYXJkX2tleSI6IjYiLCJjbGllbnRfaWQiOiJ3YiIsInNlc3Npb25faWQiOiJhZjJjOGI2ZDYxNDc0OTNhODkzYTlkNTY2Y2M0YWU3MyIsInZhbGlkYXRpb25fa2V5IjoiMjViNDExMjQwODdiMzM4YTFkMDBiOWVmYTZhYzlkOGZkYmVlZDRlNDcyMGVlMjQ2ZDdmM2YwMGI5YjFjODAxZCIsInBob25lIjoiSmI5N1U0UTdYa1pBT1I4SWMrUFVkZz09IiwidXNlcl9yZWdpc3RyYXRpb25fZHQiOjE2OTUwNDgzMzksInZlcnNpb24iOjJ9.JRRx-xVmOPm4021i8-RcLd1u3mKy0mAd8Gr182I-a-kf-WPDBRuu1sSUxg-A9xApUsdmZuWVvFIBdFVZHrP16EJkS88ObNJjKtguTf72QDfjn3pcua95vONpV_tOovviYUeN7vr9OgaX9mMEMcDOOdaR__mZMLEVUkkuBx54zblej_xQMtpW6wAYMiqnFi0tIKwR2Csfe_6w0nPUS3PQQ1opbmoH8kXrgbRzDD144Ib73NZo8rwc3BVOkg4a8tINQGuLxInpK8e5F4KN92HGRJdkCD_twsULXMiloZsWA42Biv1uPVCTtt0jr_thSgEpdBb3YfD-aYsZKT9oSkD1uQ",
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
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0"
}

HEADERS_SECOND = HEADERS_FIRST.copy()
HEADERS_SECOND.pop("authorization", None)

# Инициализация базы данных
db = Database()

async def get_products_by_config(session, config):
    """Универсальная функция для получения товаров по конфигу из БД"""
    products = []
    product_ids = set()
    
    search_queries = config['search_queries']
    exclude_keywords = config['exclude_keywords']
    
    for search_query in search_queries:
        empty_page_count = 0
        max_empty_pages = 2
        count_not_find_products = 0
        max_count_not_find_products = 2
        
        for page in range(1, 100):
            try:
                url = f"https://search.wb.ru/exactmatch/ru/common/v18/search?ab_testid=no_action&ab_testing=false&appType=1&curr=rub&dest=123589415&hide_dtype=11&inheritFilters=false&lang=ru&page={page}&query={search_query}&resultset=catalog&sort=priceup&spp=30&suppressSpellcheck=false&uclusters=0"
               
                print(f"🔍 Запрос: {search_query}, страница {page}")
                
                async with session.get(url, headers=HEADERS_FIRST, timeout=10) as response:
                    response_text = await response.text()
                    
                    if not response_text.strip():
                        print(f"⚠️ Получена пустая страница для {search_query}, страница {page}")
                        empty_page_count += 1
                        if empty_page_count >= max_empty_pages:
                            print(f"🛑 Получено {empty_page_count} пустых страниц подряд, завершаем цикл для '{search_query}'")
                            break
                        continue
                    
                    try:
                        data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        print(f"❌ Ошибка парсинга JSON для {search_query}: {e}")
                        empty_page_count += 1
                        if empty_page_count >= max_empty_pages:
                            print(f"🛑 Получено {empty_page_count} ошибок JSON подряд, завершаем цикл для '{search_query}'")
                            break
                        continue
                
                empty_page_count = 0
                
                if max_count_not_find_products == count_not_find_products:
                    print(f"🛑 В ответе нет ключа 'products' для запроса более {max_count_not_find_products} раз")
                    break
                
                if "products" not in data:
                    print(f"❌ В ответе нет ключа 'products' для запроса: {search_query}")
                    count_not_find_products += 1
                    continue
                
                count_not_find_products = 0
                if not data["products"]:
                    print(f"ℹ️ Нет товаров на странице {page} для запроса: {search_query}")
                    break
                
                products_before = len(products)
                for product in data["products"]:
                    if product["id"] not in product_ids:
                        product_ids.add(product["id"])
                        products.append(product)
                
                products_added = len(products) - products_before
                print(f"✅ Найдено {len(data['products'])} товаров, добавлено {products_added} новых для '{search_query}'")
                
                if products_added == 0:
                    print(f"🛑 Не добавлено новых товаров на странице {page}, завершаем пагинацию для '{search_query}'")
                    break
                
                if len(data["products"]) < 100:
                    print(f"ℹ️ Меньше 100 товаров на странице {page}, завершаем пагинацию для '{search_query}'")
                    break
                    
            except asyncio.TimeoutError:
                print(f"⏰ Таймаут при запросе: {search_query}, страница {page}")
                empty_page_count += 1
                if empty_page_count >= max_empty_pages:
                    print(f"🛑 Получено {empty_page_count} таймаутов подряд, завершаем цикл для '{search_query}'")
                    break
            except Exception as e:
                print(f"❌ Ошибка при парсинге {search_query}: {e}")
                empty_page_count += 1
                if empty_page_count >= max_empty_pages:
                    print(f"🛑 Получено {empty_page_count} ошибок подряд, завершаем цикл для '{search_query}'")
                    break
    
    print(f"📦 Всего найдено {len(products)} товаров для конфига")
    return products

def should_exclude_by_config(name_lower, exclude_keywords):
    """Проверяет исключения по конфигу из БД"""
    for keyword in exclude_keywords:
        if keyword in name_lower:
            return True
    return False

async def get_detailed_product_price(session, product_id, discount_percent=7):
    """Универсальная функция получения детальной цены товара"""
    try:
        discount_multiplier = (100 - discount_percent) / 100
        
        # Используем один URL для всех товаров
        url = f"https://u-card.wb.ru/cards/v4/list?appType=1&curr=rub&dest=-1586348&spp=30&hide_dtype=11&ab_testing=false&ab_testing=false&lang=ru&nm={product_id}&ignore_stocks=true"
        
        async with session.get(url, headers=HEADERS_SECOND, timeout=5) as response:
            response_text = await response.text()
            try:
                req_data = json.loads(response_text)
            except json.JSONDecodeError:
                return None
        
        # Универсальная обработка ответа
        if 'products' in req_data and len(req_data['products']) > 0:
            base_price = math.floor(req_data['products'][0]['sizes'][0]['price']['product'])/100
            discounted_price = base_price * discount_multiplier
            return math.floor(discounted_price)
        
        return None
        
    except Exception as e:
        print(f"❌ Ошибка при получении детальной цены для {product_id}: {e}")
        return None

async def send_product_messages(application, user_id, products, title, max_products_per_message=15):
    """Отправляет сообщения с товарами, разбивая на части по max_products_per_message"""
    if not products:
        return
    
    # Сортируем товары по цене
    products.sort(key=lambda x: x['price'])
    
    # Разбиваем товары на группы по max_products_per_message
    product_chunks = [products[i:i + max_products_per_message] for i in range(0, len(products), max_products_per_message)]
    
    for chunk_index, product_chunk in enumerate(product_chunks):
        message = f"{title}\n\n"
        
        # Добавляем информацию о номере части
        if len(product_chunks) > 1:
            message += f"*Часть {chunk_index + 1} из {len(product_chunks)}*\n\n"
        
        for product in product_chunk:
            if product['price_dropped'] and product['previous_price']:
                price_drop = product['previous_price'] - product['price']
                price_drop_percent = (price_drop / product['previous_price']) * 100
                message += f"🔵 {product['name']}\n"
                message += f"Цена: {product['price']:,} руб. (была {product['previous_price']:,} руб.)\n".replace(',', ' ')
                message += f"📉 Снижение: {price_drop:,} руб. ({price_drop_percent:.1f}%)\n".replace(',', ' ')
            else:
                message += f"🔵 {product['name']}\n💰 Цена: {product['price']:,} руб.\n".replace(',', ' ')
            message += f"🔗 {product['link']}\n\n"
        
        # Добавляем информацию об общем количестве товаров в последнем сообщении
        if chunk_index == len(product_chunks) - 1 and len(products) > len(product_chunk):
            message += f"*Всего найдено товаров: {len(products)}*"
        
        try:
            # Для первого сообщения добавляем клавиатуру, для остальных - без
            reply_markup = get_main_reply_keyboard() if chunk_index == 0 else None
            
            await application.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            print(f"❌ Ошибка отправки сообщения пользователю {user_id}: {e}")
    
    print(f"✅ Отправлено {len(product_chunks)} сообщений пользователю {user_id} о {len(products)} товарах")


async def filter_products_for_user(application, user_id, product_type, max_price, 
                                 discount_percent, price_threshold, products, session):
    """Универсальная фильтрация товаров для пользователя по конкретному типу продукта"""
    
    if db.is_user_waiting_for_input(user_id):
        print(f"⏸️ Пользователь {user_id} ожидает ввода, пропускаем проверку цен")
        return
    
    found_products = []
    
    min_price = math.floor(max_price * (price_threshold / 100))
    print(f"🔍 Фильтрация {product_type} для пользователя {user_id}, цена: {max_price}, порог: {price_threshold}% (мин. {min_price} руб.)")
    
    # Получаем конфиг для этого типа продукта
    config = db.get_search_config(product_type)
    if not config:
        print(f"❌ Конфиг для {product_type} не найден")
        return
    
    exclude_keywords = config['exclude_keywords']
    
    for product in products:
        name = str(product["name"])
        base_price = math.floor(product['sizes'][0]['price']['product'])/100
        initial_discounted_price = base_price * ((100 - discount_percent) / 100)
        
        # Проверяем исключения по конфигу из БД
        if should_exclude_by_config(name.lower(), exclude_keywords):
            continue
        
        if initial_discounted_price < max_price and initial_discounted_price > min_price:
            # Определяем категорию для запроса детальной цены
            detailed_price = await get_detailed_product_price(session, product['id'], discount_percent)
            
            if detailed_price and detailed_price < max_price and detailed_price > max_price/2:
                
                should_send, previous_price, price_dropped = db.save_notification(
                    user_id, product['id'], detailed_price, discount_percent
                )
                
                if should_send:
                    print(f"✅ Найден подходящий {product_type}: {name} за {detailed_price} руб. "
                          f"({'цена упала' if price_dropped else 'новый товар'})")
                    
                    found_products.append({
                        'id': product['id'],
                        'name': name,
                        'price': detailed_price,
                        'previous_price': previous_price,
                        'price_dropped': price_dropped,
                        'link': f"https://www.wildberries.ru/catalog/{product['id']}/detail.aspx"
                    })
    
    # Отправка сообщений
    if found_products:
        product_name = config['product_name']
        # Определяем иконку по типу продукта
        if 'iphone' in product_type:
            title = f"📱 Найдены {product_name} по выгодным ценам:"
        elif 'ps5' in product_type:
            title = f"🎮 Найдены {product_name} по выгодным ценам:"
        else:
            title = f"🛍️ Найдены {product_name} по выгодным ценам:"
        
        await send_product_messages(
            application, 
            user_id, 
            found_products, 
            title,
            max_products_per_message=15
        )

async def check_all_prices(application):
    """Оптимизированная проверка цен для всех пользователей с учетом статуса поиска"""
    try:
        deleted = db.cleanup_old_records(hours=24)
        if deleted > 0:
            print(f"🗑️ Очищено {deleted} старых записей")
            
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=connector) as session:
            print("🔄 Начинаем сбор товаров...")
            
            # 1. Получаем ВСЕ активные конфиги
            all_configs = db.get_all_search_configs()
            print(f"📋 Всего конфигов для поиска: {len(all_configs)}")
            
            # 2. Получаем только пользователей с активным поиском
            active_users = db.get_users_with_active_search()
            print(f"👥 Пользователей с активным поиском: {len(active_users)}")
            
            if not active_users:
                print("ℹ️ Нет пользователей с активным поиском, завершаем проверку")
                return
            
            # 3. Извлекаем отслеживаемые типы товаров для активных пользователей
            all_tracked_product_types = set()
            users_with_prices = {}
            
            for user_id in active_users:
                user_products = db.get_all_user_product_prices(user_id)
                user_prices = {product_type: data['price'] for product_type, data in user_products.items() if data['active']}
                if user_prices:
                    discount_percent, price_threshold = db.get_user_settings(user_id)
                    users_with_prices[user_id] = {
                        'prices': user_prices,
                        'discount': discount_percent,
                        'threshold': price_threshold
                    }
                    all_tracked_product_types.update(user_prices.keys())
            
            print(f"📦 Отслеживаемых типов товаров: {len(all_tracked_product_types)}")
            
            # 4. Собираем товары ТОЛЬКО для отслеживаемых типов
            all_products = {}
            for product_type in all_tracked_product_types:
                if product_type in all_configs:
                    config = all_configs[product_type]
                    print(f"🔍 Сбор товаров для {product_type}...")
                    products = await get_products_by_config(session, config)
                    all_products[product_type] = products
                    print(f"✅ Найдено {len(products)} товаров для {product_type}")
                else:
                    print(f"⚠️ Конфиг для {product_type} не найден в БД")
            
            # 5. Фильтруем товары для каждого активного пользователя
            print(f"🔍 Проверка цен для {len(users_with_prices)} пользователей...")
            
            for user_id, user_data in users_with_prices.items():
                # Проверяем, не ожидает ли пользователь ввода
                if db.is_user_waiting_for_input(user_id):
                    print(f"⏸️ Пропускаем пользователя {user_id} - ожидает ввода")
                    continue
                
                print(f"🔍 Проверка пользователя {user_id}, отслеживает {len(user_data['prices'])} товаров")
                
                # Для каждого отслеживаемого продукта пользователя
                for product_type, max_price in user_data['prices'].items():
                    if max_price > 0 and product_type in all_products:
                        await filter_products_for_user(
                            application, user_id, product_type, max_price, 
                            user_data['discount'], user_data['threshold'],
                            all_products[product_type], session
                        )
            
            print("✅ Проверка цен завершена")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке цен: {e}")
        import traceback
        traceback.print_exc()

is_price_check_running = False

async def price_checker_job(context):
    """Фоновая задача для проверки цен"""
    global is_price_check_running
    
    if is_price_check_running:
        print("⏸️ Проверка цен уже выполняется, пропускаем этот запуск...")
        return
        
    try:
        is_price_check_running = True
        await check_all_prices(context.application)
    except Exception as e:
        print(f"❌ Ошибка в фоновой задаче: {e}")
    finally:
        is_price_check_running = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - показывает описание бота"""
    
    message = (
        "🤖 **Бот мониторинга цен на Wildberries**\n\n"
        "**Что умеет этот бот:**\n"
        "• Автоматически ищет PS5 и iPhone 16 по вашим ценам\n"
        "• Применяет скидку WB при расчете стоимости\n"
        "• Отслеживает снижение цен\n"
        "• **Управление поиском** - вы сами решаете, когда получать уведомления\n\n"
        "💡 **Как начать:**\n"
        '1. Нажмите «⚙️ Меню» - чтобы настроить бота\n'
        '2. Добавьте товары и установите цены\n'
        '3. Включите поиск и ждите уведомлений!\n\n'
        "🔕 *Поиск отключен по умолчанию. Включите его когда будете готовы.*"
    )
    
    try:
        await update.message.reply_text(
            message, 
            parse_mode='Markdown',
            reply_markup=get_main_reply_keyboard()
        )
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения: {e}")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню"""
    user_id = update.effective_user.id
    discount_percent, price_threshold = db.get_user_settings(user_id)
    
    # Получаем ВСЕ товары пользователя (включая неактивные)
    user_products = db.get_all_user_product_prices(user_id)
    
    # Получаем статус поиска
    is_search_active = db.get_user_search_active(user_id)
    search_status_icon = "🟢" if is_search_active else "🔴"
    search_status_text = "активен" if is_search_active else "остановлен"
    
    # Формируем информацию о установленных ценах
    price_info = []
    if user_products:
        product_names = {
            'iphone_16_128': 'iPhone 16 128Gb',
            'iphone_16_256': 'iPhone 16 256Gb',
            'iphone_16_pro_128': 'iPhone 16 Pro 128Gb',
            'iphone_16_pro_256': 'iPhone 16 Pro 256Gb',
            'iphone_16_pro_max': 'iPhone 16 Pro Max 256Gb',
            'ps5_slim_disk': 'PlayStation 5 Slim'
        }
        
        for product_type, product_data in user_products.items():
            price = product_data['price']
            if price > 0:
                product_name = product_names.get(product_type, product_type)
                # Убрали иконки статуса и эмодзи товаров, оставили только название и цену
                price_info.append(f"{product_name}: {price:,} руб.".replace(',', ' '))
    
    if not price_info:
        price_info = ["Не установлены"]
    
    keyboard = [
        [InlineKeyboardButton("🤖 Парсер", callback_data="parser_menu")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"{search_status_icon} **Статус поиска:** {search_status_text}\n\n"
        "⚙️ **Ваши текущие настройки:**\n"
        f"💸 Скидка WB: {discount_percent}%\n"
        f"📉 Авт. порог: {price_threshold}%\n\n"
        "📦 **Отслеживаемые товары:**\n" +
        "\n".join(f"• {info}" for info in price_info) +
        "\n\n💡 **Выберите раздел:**"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню настроек"""
    user_id = update.effective_user.id
    discount_percent, price_threshold = db.get_user_settings(user_id)
    
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

async def show_parser_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню парсера с кнопками управления поиском"""
    user_id = update.effective_user.id
    
    # Проверяем статус поиска из БД
    is_search_active = db.get_user_search_active(user_id)
    
    keyboard = []
    
    if is_search_active:
        keyboard.append([InlineKeyboardButton("⏹️ Остановить поиск", callback_data="stop_search")])
    else:
        keyboard.append([InlineKeyboardButton("🔍 Начать поиск", callback_data="start_search")])
    
    keyboard.extend([
        [InlineKeyboardButton("🤖 Парсер", callback_data="products_menu")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status_text = "🟢 Активен" if is_search_active else "🔴 Остановлен"
    
    message = (
        "🤖 **Меню парсера**\n\n"
        f"**Статус поиска:** {status_text}\n\n"
        "**Управление поиском:**\n"
        "• **🔍 Начать поиск** - запустить автоматический поиск товаров\n"
        "• **⏹️ Остановить поиск** - приостановить уведомления\n"
        "• **🤖 Парсер** - настроить цены для отслеживания\n\n"
        "💡 *Поиск работает в фоновом режиме и проверяет цены каждую минуту*"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_products_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора категорий товаров"""
    keyboard = [
        [InlineKeyboardButton("📱 iPhone 16", callback_data="iphone_menu")],
        [InlineKeyboardButton("🎮 PlayStation", callback_data="ps5_menu")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_parser")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "📦 **Выбор категории товаров**\n\n"
        "Выберите категорию для настройки цен:"
    )
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_iphone_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора моделей iPhone"""
    keyboard = [
        [InlineKeyboardButton("iPhone 16 128Gb", callback_data="set_iphone_16_128")],
        [InlineKeyboardButton("iPhone 16 256Gb", callback_data="set_iphone_16_256")],
        [InlineKeyboardButton("iPhone 16 Pro 128Gb", callback_data="set_iphone_16_pro_128")],
        [InlineKeyboardButton("iPhone 16 Pro 256Gb", callback_data="set_iphone_16_pro_256")],
        [InlineKeyboardButton("iPhone 16 Pro Max 256Gb", callback_data="set_iphone_16_pro_max")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "📱 **Выбор модели iPhone**\n\n"
        "Выберите конкретную модель для установки цены:"
    )
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_ps5_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню для PS5"""
    keyboard = [
        [InlineKeyboardButton("PlayStation 5 Slim с дисководом", callback_data="set_ps5_slim_disk")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "🎮 **PlayStation 5**\n\n"
        "Установите цену для PlayStation 5 Slim с дисководом:"
    )
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для кнопки Меню под клавиатурой"""
    await show_main_menu(update, context)

# Создаем Reply клавиатуру (постоянная клавиатура внизу)
def get_main_reply_keyboard():
    """Создает основную Reply клавиатуру"""
    keyboard = [
        [KeyboardButton("⚙️ Меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню с информацией и управлением"""
    user_id = update.effective_user.id
    discount_percent, price_threshold = db.get_user_settings(user_id)
    
    # Получаем ВСЕ товары пользователя
    user_products = db.get_all_user_product_prices(user_id)
    
    # Получаем статус поиска
    is_search_active = db.get_user_search_active(user_id)
    search_status_icon = "🟢" if is_search_active else "🔴"
    search_status_text = "активен" if is_search_active else "остановлен"
    
    # Формируем информацию о установленных ценах
    price_info = []
    if user_products:
        product_names = {
            'iphone_16_128': 'iPhone 16 128Gb',
            'iphone_16_256': 'iPhone 16 256Gb',
            'iphone_16_pro_128': 'iPhone 16 Pro 128Gb',
            'iphone_16_pro_256': 'iPhone 16 Pro 256Gb',
            'iphone_16_pro_max': 'iPhone 16 Pro Max 256Gb',
            'ps5_slim_disk': 'PlayStation 5 Slim'
        }
        
        for product_type, product_data in user_products.items():
          price = product_data['price']
          is_active = product_data['active']
          if price > 0:
              product_name = product_names.get(product_type, product_type)
              # Убираем status_icon и оставляем только название и цену
              price_info.append(f"• {product_name}: {price:,} руб.".replace(',', ' '))
    
    if not price_info:
        price_info = ["Не установлены"]
    
    # Создаем клавиатуру меню
    keyboard = []
    
    # Динамическая кнопка поиска (в зависимости от статуса)
    if is_search_active:
        keyboard.append([InlineKeyboardButton("⏹️ Остановить поиск", callback_data="stop_search")])
    else:
        keyboard.append([InlineKeyboardButton("🔍 Начать поиск", callback_data="start_search")])
    
    # Остальные кнопки
    keyboard.extend([
        [InlineKeyboardButton("🤖 Парсер", callback_data="products_menu")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings_menu")],
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"{search_status_icon} **Статус поиска:** {search_status_text}\n\n"
        "**Текущие настройки:**\n"
        f"• 💸 Скидка WB: {discount_percent}%\n"
        f"• 📉 Автоматический порог: {price_threshold}%\n\n"
        "**📦 Отслеживаемые товары:**\n" +
        "\n".join(f"{info}" for info in price_info) +
        "\n\n💡 *Выберите действие:*"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_reply_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на Reply кнопки"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "⚙️ Меню":
        # Показываем главное меню
        await show_menu(update, context)

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню настроек"""
    user_id = update.effective_user.id
    discount_percent, price_threshold = db.get_user_settings(user_id)
    
    keyboard = [
        [InlineKeyboardButton("💸 Настроить скидку", callback_data="set_discount")],
        [InlineKeyboardButton("📉 Настроить порог", callback_data="set_threshold")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "**⚙️ Настройки**\n\n"
        "**Текущие значения:**\n"
        f"• 💸 Скидка WB: {discount_percent}%\n"
        f"• 📉 Автоматический порог: {price_threshold}%\n\n"
        "Выберите что хотите настроить:"
    )
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline-кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Обработка управления поиском
    if data == "start_search":
        # Включаем поиск для пользователя
        db.set_user_search_active(user_id, True)
        
        # await query.edit_message_text(
        #     "🟢 **Поиск активирован!**\n\n"
        #     "Теперь бот будет присылать вам уведомления о найденных товарах.\n"
        #     "Следующая проверка цен произойдет в течение 5 минут.\n\n"
        #     "⚙️ *Вы можете остановить поиск в любой момент*",
        #     parse_mode='Markdown'
        # )
        # Показываем обновленное меню
        await show_menu(update, context)
    
    elif data == "stop_search":
        # Выключаем поиск для пользователя
        db.set_user_search_active(user_id, False)
        
        # await query.edit_message_text(
        #     "⏹️ **Поиск остановлен**\n\n"
        #     "Бот больше не будет присылать уведомления о найденных товарах.\n\n"
        #     "🔍 *Чтобы возобновить поиск, нажмите «Начать поиск»*",
        #     parse_mode='Markdown'
        # )
        # Показываем обновленное меню
        await show_menu(update, context)
    
    # Меню настроек
    elif data == "settings_menu":
        await show_settings_menu(update, context)
    
    elif data == "set_discount":
        db.set_waiting_for_price(user_id, 1, 'discount')
        
        # Создаем клавиатуру с кнопкой "Назад"
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🏷️ **Установка процента скидки**\n\n"
            "Введите процент скидки WB (только цифры):\n\n"
            "💡 **Пример:** 7\n\n"
            "ℹ️ Бот будет применять эту скидку при расчете итоговой цены.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # Настройка порога
    elif data == "set_threshold":
        db.set_waiting_for_price(user_id, 1, 'threshold')
        
        # Создаем клавиатуру с кнопкой "Назад"
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📉 **Автоматический минимальный порог**\n\n"
            "Эта функция избавляет вас от необходимости каждый раз вручную указывать диапазон цен.\n\n"
            "**Как это работает?**\n"
            "Вы задаете процент, и бот сам рассчитывает минимальную цену для отслеживания.\n\n"
            "**Например:**\n"
            "- Вы ставите порог: 30%\n"
            "- Добавляете товар с ценой: 10 000 ₽\n"
            "- Бот будет автоматически отслеживать его в диапазоне от 3 000 ₽ до 10 000 ₽.\n\n"
            "**Текущее значение:** 50%\n\n"
            "Введите процент от 0 до 100. Чтобы отключить, введите 0.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    # Меню товаров
    elif data == "products_menu":
        await show_products_menu(update, context)
    
    # Категории товаров
    elif data == "iphone_menu":
        await show_iphone_menu(update, context)
    
    elif data == "ps5_menu":
        await show_ps5_menu(update, context)
    
    # Установка цен для iPhone
    elif data == "set_iphone_16_128":
        db.set_waiting_for_price(user_id, 1, 'iphone_16_128')
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_iphone")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📱 **Установка цены для iPhone 16 128Gb**\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "💡 **Пример:** 80000\n\n"
            "🔍 Бот будет искать iPhone 16 128Gb в диапазоне согласно вашему автоматическому порогу.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif data == "set_iphone_16_256":
        db.set_waiting_for_price(user_id, 1, 'iphone_16_256')
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_iphone")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📱 **Установка цены для iPhone 16 256Gb**\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "💡 **Пример:** 90000\n\n"
            "🔍 Бот будет искать iPhone 16 256Gb в диапазоне согласно вашему автоматическому порогу.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif data == "set_iphone_16_pro_128":
        db.set_waiting_for_price(user_id, 1, 'iphone_16_pro_128')
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_iphone")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📱 **Установка цены для iPhone 16 Pro 128Gb**\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "💡 **Пример:** 100000\n\n"
            "🔍 Бот будет искать iPhone 16 Pro 128Gb в диапазоне согласно вашему автоматическому порогу.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif data == "set_iphone_16_pro_256":
        db.set_waiting_for_price(user_id, 1, 'iphone_16_pro_256')
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_iphone")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📱 **Установка цены для iPhone 16 Pro 256Gb**\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "💡 **Пример:** 110000\n\n"
            "🔍 Бот будет искать iPhone 16 Pro 256Gb в диапазоне согласно вашему автоматическому порогу.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif data == "set_iphone_16_pro_max":
        db.set_waiting_for_price(user_id, 1, 'iphone_16_pro_max')
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_iphone")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📱 **Установка цены для iPhone 16 Pro Max 256Gb**\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "💡 **Пример:** 120000\n\n"
            "🔍 Бот будет искать iPhone 16 Pro Max 256Gb в диапазоне согласно вашему автоматическому порогу.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # Установка цены для PS5
    elif data == "set_ps5_slim_disk":
        db.set_waiting_for_price(user_id, 1, 'ps5_slim_disk')
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_ps5")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎮 **Установка цены для PlayStation 5 Slim с дисководом**\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "💡 **Пример:** 50000\n\n"
            "🔍 Бот будет искать PS5 Slim с дисководом в диапазоне согласно вашему автоматическому порогу.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    # Кнопки навигации
    elif data == "back_to_products":
        await show_products_menu(update, context)

    elif data == "back_to_main":
        await show_menu(update, context)

    elif data == "back_to_settings":
        # Очищаем состояние ожидания ввода и возвращаем в меню настроек
        db.clear_waiting_for_price(user_id)
        await show_settings_menu(update, context)

    elif data == "back_to_iphone":
        # Очищаем состояние ожидания ввода и возвращаем в меню iPhone
        db.clear_waiting_for_price(user_id)
        await show_iphone_menu(update, context)

    elif data == "back_to_ps5":
        # Очищаем состояние ожидания ввода и возвращаем в меню PS5
        db.clear_waiting_for_price(user_id)
        await show_ps5_menu(update, context)
    
    # Обработка несуществующих команд
    else:
        await show_menu(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений для установки цен, автоматического порога и скидки"""
    user_id = update.effective_user.id
    waiting_for_price, product_type = db.get_waiting_for_price(user_id)
    
    if waiting_for_price and product_type:
        text = update.message.text.strip()
        
        # Обработка команды "назад" через текст
        if text.lower() in ['назад', 'back', 'отмена', 'cancel']:
            db.clear_waiting_for_price(user_id)
            await show_menu(update, context)
            return
        
        if not re.match(r'^\d+$', text):
            # Создаем клавиатуру с кнопкой "Назад" для сообщения об ошибке
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад", callback_data=f"back_to_{'settings' if product_type in ['discount', 'threshold'] else 'main'}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "❌ Пожалуйста, введите только цифры (без пробелов, букв и других символов)\n\n"
                "💡 **Пример:** 50000\n\n"
                "🔙 *Или нажмите «Назад» чтобы отменить*",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        try:
            value = int(text)
            
            if product_type == 'discount':
                if value <= 0 or value > 50:
                    keyboard = [
                        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        "❌ Скидка должна быть от 1% до 50%",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    return
                
                # Получаем старую скидку для информационного сообщения
                discount_percent, _ = db.get_user_settings(user_id)
                    
                # Устанавливаем новую скидку
                db.set_user_discount(user_id, value)
                db.clear_waiting_for_price(user_id)
                
                # Создаем inline-клавиатуру с кнопкой "На главную"
                keyboard = [
                    [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                message = (
                    f"✅ **Процент скидки изменен:** {discount_percent}% → {value}%\n\n"
                    f"Теперь бот будет применять {value}% скидку при расчете цен."
                )
                
                await update.message.reply_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
            elif product_type == 'threshold':
                if value < 0 or value > 100:
                    keyboard = [
                        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        "❌ Порог должен быть от 0% до 100%",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    return
                
                db.set_user_threshold(user_id, value)
                db.clear_waiting_for_price(user_id)
                
                # Создаем inline-клавиатуру с кнопкой "На главную"
                keyboard = [
                    [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
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
            
            # Обработка установки цен для товаров
            elif product_type in ['iphone_16_128', 'iphone_16_256', 'iphone_16_pro_128', 
                                'iphone_16_pro_256', 'iphone_16_pro_max', 'ps5_slim_disk']:
                if value <= 0:
                    keyboard = [
                        [InlineKeyboardButton("⬅️ Назад", callback_data=f"back_to_{'iphone' if 'iphone' in product_type else 'ps5'}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        "❌ Цена должна быть положительным числом",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    return
                
                # Сохраняем цену в новой таблице
                db.set_user_product_price(user_id, product_type, value)
                db.clear_waiting_for_price(user_id)
                
                # Получаем название продукта из конфига
                config = db.get_search_config(product_type)
                product_name = config['product_name'] if config else product_type
                
                # Получаем текущий порог для отображения диапазона
                _, price_threshold = db.get_user_settings(user_id)
                
                if price_threshold > 0:
                    min_price = math.floor(value * (price_threshold / 100))
                    range_info = f"{min_price:,} - {value:,} руб.".replace(',', ' ')
                else:
                    range_info = f"от 0 до {value:,} руб.".replace(',', ' ')
                
                # Создаем inline-клавиатуру с кнопкой "На главную"
                keyboard = [
                    [InlineKeyboardButton("⬅️ В меню", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ **Максимальная цена для {product_name} установлена:** {value:,} руб.\n\n".replace(',', ' ') +
                    f"**Диапазон поиска:** {range_info}\n\n" +
                    f"🔍 Бот будет искать {product_name} в диапазоне: {range_info}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
        except ValueError:
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад", callback_data=f"back_to_{'settings' if product_type in ['discount', 'threshold'] else 'main'}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "❌ Укажите корректное значение (только цифры)\n\n"
                "🔙 *Или нажмите «Назад» чтобы отменить*",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    else:
        # Если пользователь отправил текст без контекста - показываем главное меню
        await show_menu(update, context)

def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_button))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик для Reply клавиатуры
    application.add_handler(MessageHandler(filters.Text(["⚙️ Меню"]), handle_reply_keyboard))
    
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