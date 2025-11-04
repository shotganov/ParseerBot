import aiohttp
import asyncio
from datetime import datetime, timedelta
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

BOT_TOKEN = "8459198512:AAGT_naxAdmepRFAkQMDuG-fmRgbFrTVtSg"
#BOT_TOKEN = "7998443497:AAGnYx7to86c-7H7HWcrXQFr4UDuj9ocQ3U"
ADMIN_USER_ID = 300446433
IPHONE_16_MIN_THRESHOLD = 400
COUNTER = 0
MAX_COUNTER = 0

def get_headers_from_db():
    token = db.get_system_config("wb_authorization", None)
    base_headers = {
        "authority": "u-card.wb.ru",
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "ru,en;q=0.9,en-GB;q=8,en-US;q=7",
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
    if token:
        base_headers["authorization"] = f"Bearer {token}"
    return base_headers

def get_headers_without_auth():
    headers = get_headers_from_db()
    headers.pop("authorization", None)
    return headers

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
                
                async with session.get(url, headers=get_headers_from_db(), timeout=10) as response:
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
        
        async with session.get(url, headers=get_headers_without_auth(), timeout=5) as response:
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
          # Ссылка в названии
          product_link = f"[{product['name']}]({product['link']})"
          
          if product['price_dropped'] and product['previous_price']:
              price_drop = product['previous_price'] - product['price']
              price_drop_percent = (price_drop / product['previous_price']) * 100
              message += f"🔵 {product_link}\n"

              # Добавляем рейтинг продавца, если есть
              if product.get('supplier_rating') is not None:
                  rating = product['supplier_rating']
                  message += f"⭐ Рейтинг продавца: {rating}\n"
              elif product.get('supplier'):
                  message += f"🏪 Продавец: {product['supplier']}\n"

              message += f"💰 Цена: {product['price']:,} руб. (была {product['previous_price']:,} руб.)\n".replace(',', ' ')
              message += f"📉 Снижение: {price_drop:,} руб. ({price_drop_percent:.1f}%)\n".replace(',', ' ')
          else:
              message += f"🔵 {product_link}\n"
              # Добавляем рейтинг продавца, если есть
              if product.get('supplier_rating') is not None:
                  rating = product['supplier_rating']
                  message += f"⭐ Рейтинг продавца: {rating}\n"
              elif product.get('supplier'):
                  message += f"🏪 Продавец: {product['supplier']}\n"

              message += f"💰 Цена: {product['price']:,} руб.\n".replace(',', ' ')
              
          
          message += "\n"
        
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
                disable_web_page_preview=True,
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
                        'link': f"https://www.wildberries.ru/catalog/{product['id']}/detail.aspx",
                        'supplier': product.get('supplier', '—'),
                        'supplier_rating': product.get('supplierRating', None)
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

async def check_wb_token_health(application, all_products):
    global IPHONE_16_MIN_THRESHOLD, COUNTER, MAX_COUNTER
    product_type = 'iphone_16_128'
    if product_type not in all_products:
        print("ℹ️ iPhone 16 128Gb не отслеживается — проверка токена пропущена")
        return

    product_count = len(all_products[product_type])
    if product_count >= IPHONE_16_MIN_THRESHOLD:
        COUNTER = 0
        print(f"✅ Токен WB в порядке: найдено {product_count} iPhone 16 (128Gb)")
        return

    # === ПРОВЕРКА: прошло ли 30 минут с последнего уведомления? ===
    last_alert_str = db.get_system_config("last_token_alert_time")
    now = datetime.now()
    COUNTER += 1

    if last_alert_str:
        try:
            last_alert = datetime.fromisoformat(last_alert_str)
            if now - last_alert < timedelta(minutes=30):
                print("⏳ Уведомление уже отправлялось менее 30 минут назад — пропускаем")
                return
        except Exception as e:
            print(f"⚠️ Ошибка при разборе last_token_alert_time: {e}")

    

    if COUNTER == MAX_COUNTER:
      COUNTER = 0
      try:
          await application.bot.send_message(
              chat_id=ADMIN_USER_ID,
            text=(
                  "⚠️ Внимание, администратор!\n"
                  f"При поиске «iPhone 16 128Gb» найдено {product_count} товаров.\n"
                  f"Порог: {IPHONE_16_MIN_THRESHOLD}.\n\n"
                  "🔹 Вероятно, токен Wildberries устарел.\n"
                  "🔹 Обновите его в Настройках → «🔑 Изменить токен WB».\n\n"
                  "ℹ️ Уведомления приходят не чаще раза в 30 минут."
              )
          )
          print("✅ Уведомление админу отправлено")
          # === Сохраняем время отправки ===
          db.set_system_config("last_token_alert_time", now.isoformat())
      except Exception as e:
          print(f"❌ Не удалось отправить уведомление: {e}")

async def check_all_prices(application):
    """Проверка цен для всех пользователей + проверка токена WB + отслеживание кастомных ссылок без ввода цены"""
    try:
        # Очистка старых уведомлений
        deleted = db.cleanup_old_records(hours=24)
        if deleted > 0:
            print(f"🗑️ Очищено {deleted} старых записей")

        # Раз в 30 дней — очистка старых кастомных ссылок
        last_cleanup = db.get_system_config("last_custom_cleanup")
        now = datetime.now()
        if not last_cleanup or (now - datetime.fromisoformat(last_cleanup)).days >= 30:
            deleted_custom = db.cleanup_old_custom_links(days=30)
            print(f"🧹 Очищено {deleted_custom} старых кастомных ссылок")
            db.set_system_config("last_custom_cleanup", now.isoformat())

        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=connector) as session:
            print("🔄 Начинаем сбор товаров...")

            # 1. Стандартные категории (iPhone, PS5)
            all_configs = db.get_all_search_configs()
            active_users = db.get_users_with_any_active_tracking()
            if not active_users:
                print("ℹ️ Нет активных пользователей")
                return

            # Собираем отслеживаемые типы
            all_tracked_product_types = set()
            users_with_prices = {}
            for user_id in active_users:
                user_products = db.get_all_user_product_prices(user_id)
                user_prices = {pt: data['price'] for pt, data in user_products.items() if data['active']}
                if user_prices:
                    disc, thr = db.get_user_settings(user_id)
                    users_with_prices[user_id] = {'prices': user_prices, 'discount': disc, 'threshold': thr}
                    all_tracked_product_types.update(user_prices.keys())

            # Сбор по категориям
            all_products = {}
            for product_type in all_tracked_product_types:
                if product_type in all_configs:
                    config = all_configs[product_type]
                    products = await get_products_by_config(session, config)
                    all_products[product_type] = products
                    print(f"✅ Найдено {len(products)} товаров для {product_type}")

            # Проверка токена через iPhone 16
            await check_wb_token_health(application, all_products)

            # 2. Обработка КАСТОМНЫХ ссылок (без установки цены)
            custom_links_by_user = {}
            custom_product_ids = set()
            for user_id in active_users:
                links = db.get_user_custom_links(user_id)  # возвращает {product_id: initial_price}
                if links:
                    custom_links_by_user[user_id] = links
                    custom_product_ids.update(links.keys())

            # Получаем текущие цены по артикулам
            custom_current_prices = {}
            if custom_product_ids:
                print(f"🔍 Получение текущих цен для {len(custom_product_ids)} кастомных артикулов...")
                for pid in custom_product_ids:
                    raw_price = await get_detailed_product_price(session, pid, discount_percent=0)
                    if raw_price is not None:
                        custom_current_prices[pid] = raw_price

            # 3. Фильтрация стандартных товаров
            for user_id, user_data in users_with_prices.items():
                if db.is_user_waiting_for_input(user_id):
                    continue
                for product_type, max_price in user_data['prices'].items():
                    if max_price > 0 and product_type in all_products:
                        await filter_products_for_user(
                            application, user_id, product_type, max_price,
                            user_data['discount'], user_data['threshold'],
                            all_products[product_type], session
                        )

            # 4. Проверка кастомных товаров: уведомление ТОЛЬКО при снижении цены
            if custom_links_by_user and custom_current_prices:
                print("🔍 Проверка кастомных товаров на снижение цены...")
                for user_id, custom_links in custom_links_by_user.items():
                    if db.is_user_waiting_for_input(user_id):
                        continue
                    discount_percent, _ = db.get_user_settings(user_id)
                    found = []
                    for product_id, initial_price in custom_links.items():
                        if product_id not in custom_current_prices:
                            continue
                        current_base = custom_current_prices[product_id]
                        current_discounted = math.floor(current_base * (100 - discount_percent) / 100)

                        # Уведомляем, если цена упала ниже initial_price
                        if current_discounted < initial_price:
                            should_send, prev_price, price_dropped = db.save_notification(
                                user_id, product_id, current_discounted, discount_percent
                            )
                            if should_send:
                              found.append({
                                  'id': product_id,
                                  'name': f"Товар WB (артикул {product_id})",
                                  'price': current_discounted,
                                  'previous_price': prev_price or initial_price,
                                  'price_dropped': True,
                                  'link': f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx",
                                  'supplier': '—',  # для кастомных ссылок — неизвестен
                                  'supplier_rating': None
                              })
                    if found:
                        await send_product_messages(
                            application, user_id, found,
                            "📉 Цена на отслеживаемый товар снизилась:",
                            max_products_per_message=15
                        )

            print("✅ Проверка цен завершена")
    except Exception as e:
        print(f"❌ Ошибка в check_all_prices: {e}")
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

    # 1. Стандартные товары
    user_products = db.get_all_user_product_prices(user_id)
    product_names = {
        'iphone_16_128': 'iPhone 16 128Gb',
        'iphone_16_256': 'iPhone 16 256Gb',
        'iphone_16_pro_128': 'iPhone 16 Pro 128Gb',
        'iphone_16_pro_256': 'iPhone 16 Pro 256Gb',
        'iphone_16_pro_max': 'iPhone 16 Pro Max 256Gb',
        'ps5_slim_disk': 'PlayStation 5 Slim',
        'ps5_pro': 'PlayStation 5 Pro',
    }
    for product_type, product_data in user_products.items():
        price = product_data['price']
        if price > 0:
            product_name = product_names.get(product_type, product_type)
            price_info.append(f"• {product_name}: {price:,} руб.".replace(',', ' '))

    all_custom_links = db.get_all_user_custom_links(user_id)
    for product_id, data in all_custom_links.items():
        price_info.append(f"• Товар WB (артикул {product_id}): {data['price']:,} руб.".replace(',', ' '))

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
    """Показывает меню настроек (с кнопкой токена для админа)"""
    user_id = update.effective_user.id
    discount_percent, price_threshold = db.get_user_settings(user_id)
    
    keyboard = [
        [InlineKeyboardButton("💸 Настроить скидку", callback_data="set_discount")],
        [InlineKeyboardButton("📉 Настроить порог", callback_data="set_threshold")],
    ]
    
    # 🔑 Добавляем кнопку "Изменить токен", если пользователь — админ
    if user_id == ADMIN_USER_ID:
        keyboard.append([InlineKeyboardButton("🔑 Изменить токен WB", callback_data="set_wb_token")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        "**⚙️ Настройки**\n"
        "**Текущие значения:**\n"
        f"• 💸 Скидка WB: {discount_percent}%\n"
        f"• 📉 Автоматический порог: {price_threshold}%"
    )
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

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
    """Показывает меню выбора категорий товаров с разделением на товары и ссылки"""
    keyboard = [
        [InlineKeyboardButton("📦 Товары", callback_data="products_items")],
        [InlineKeyboardButton("🔗 Ссылки", callback_data="products_links")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_parser")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "📦 **Управление отслеживанием**\n\n"
        "**📦 Товары** - настройка цен для предустановленных категорий\n"
        "**🔗 Ссылки** - управление кастомными товарами по ссылкам\n\n"
        "Выберите раздел:"
    )
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_products_items_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню товаров (iPhone и PS5)"""
    keyboard = [
        [InlineKeyboardButton("📱 iPhone 16", callback_data="iphone_menu")],
        [InlineKeyboardButton("🎮 PlayStation", callback_data="ps5_menu")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "📦 **Управление товарами**\n\n"
        "Выберите категорию для настройки цен:"
    )
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_products_links_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления ссылками"""
    user_id = update.effective_user.id
    custom_links = db.get_all_user_custom_links(user_id)
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить", callback_data="add_custom_link")],
    ]
    
    # Добавляем кнопки для удаления только если есть ссылки
    if custom_links:
        keyboard.append([InlineKeyboardButton("🗑️ Удалить", callback_data="delete_custom_links")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Формируем информацию о текущих ссылках
    links_info = []
    for product_id, data in custom_links.items():
        links_info.append(f"Артикул {product_id}: {data['price']:,} руб.".replace(',', ' '))
    
    # Формируем описание действий динамически
    actions_text = "➕ Добавить** - отслеживать новый товар"
    
    # Добавляем описание удаления только если есть ссылки
    if custom_links:
        actions_text += "\n**🗑️ Удалить** - управление существующими ссылками"
    
    message = (
        "🔗 **Управление ссылками**\n\n"
        f"{actions_text}"
    )
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_delete_custom_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    """Показывает список кастомных товаров для удаления с пагинацией"""
    user_id = update.effective_user.id
    custom_links = db.get_all_user_custom_links(user_id)
    
    if not custom_links:
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products_links")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            "❌ У вас нет кастомных товаров для удаления", 
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return

    # Настройки пагинации
    ITEMS_PER_PAGE = 5
    total_items = len(custom_links)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    # Проверяем корректность страницы
    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1
    
    # Получаем элементы для текущей страницы
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_page_items = list(custom_links.items())[start_idx:end_idx]
    
    # Создаем клавиатуру
    keyboard = []
    
    # Добавляем кнопки товаров
    for product_id, data in current_page_items:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ Артикул {product_id} — {data['price']:,} руб.".replace(',', ' '),
                callback_data=f"del_custom_{product_id}"
            )
        ])
    
    # Добавляем кнопки пагинации
    pagination_buttons = []
    
    if total_pages > 1:
        # На ПЕРВОЙ странице - кнопка "Назад в меню" и "Вперед"
        if page == 0:
            pagination_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products_links"))
            pagination_buttons.append(InlineKeyboardButton("▶️", callback_data=f"delete_page_{page+1}"))
        
        # На ПОСЛЕДНЕЙ странице - только кнопка "Назад" (стрелка влево)
        elif page == total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton("◀️", callback_data=f"delete_page_{page-1}"))
        
        # На ПРОМЕЖУТОЧНЫХ страницах - обе стрелки
        else:
            pagination_buttons.append(InlineKeyboardButton("◀️", callback_data=f"delete_page_{page-1}"))
            pagination_buttons.append(InlineKeyboardButton("▶️", callback_data=f"delete_page_{page+1}"))
        
        if pagination_buttons:
            keyboard.append(pagination_buttons)
    else:
        # Если всего одна страница - только кнопка "Назад в меню"
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products_links")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Формируем сообщение
    message = (
        f"🗑️ **Удаление отслеживаемых товаров**\n\n"
        f"📋 Страница {page+1} из {total_pages}\n"
        f"📊 Всего товаров: {total_items}\n\n"
        "Выберите товар для удаления:"
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
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products_items")]
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
        [InlineKeyboardButton("PlayStation 5 Slim Blu-Ray", callback_data="set_ps5_slim_disk")],
         [InlineKeyboardButton("PlayStation 5 Pro", callback_data="set_ps5_pro")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products_items")]
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
    
    # Получаем статус поиска
    is_search_active = db.get_user_search_active(user_id)
    search_status_icon = "🟢" if is_search_active else "🔴"
    search_status_text = "активен" if is_search_active else "остановлен"
    
    # Формируем информацию о установленных ценах
    price_info = []

    # 1. Стандартные товары
    user_products = db.get_all_user_product_prices(user_id)
    product_names = {
        'iphone_16_128': 'iPhone 16 128Gb',
        'iphone_16_256': 'iPhone 16 256Gb',
        'iphone_16_pro_128': 'iPhone 16 Pro 128Gb',
        'iphone_16_pro_256': 'iPhone 16 Pro 256Gb',
        'iphone_16_pro_max': 'iPhone 16 Pro Max 256Gb',
        'ps5_slim_disk': 'PlayStation 5 Slim',
        'ps5_pro': 'PlayStation 5 Pro',
    }
    for product_type, product_data in user_products.items():
        price = product_data['price']
        if price > 0:
            product_name = product_names.get(product_type, product_type)
            price_info.append(f"• {product_name}: {price:,} руб.".replace(',', ' '))

    all_custom_links = db.get_all_user_custom_links(user_id)
    for product_id, data in all_custom_links.items():
        price_info.append(f"• Товар WB (артикул {product_id}): {data['price']:,} руб.".replace(',', ' '))

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


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline-кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Обработка управления поиском
    if data == "start_search":
        user_products = db.get_all_user_product_prices(user_id)
        custom_links = db.get_all_user_custom_links(user_id)
        
        active_products_count = sum(1 for product_data in user_products.values() if product_data['price'] > 0)
        active_custom_count = sum(1 for link_data in custom_links.values() if link_data['active'])
        total_tracked_items = active_products_count + active_custom_count
        
        if total_tracked_items == 0:
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            # ⚠️ Простое уведомление и возврат в меню
            print("Пытаюсь отправить")
            await query.edit_message_text("❌ Сначала добавьте товары для отслеживания!", reply_markup=reply_markup,
            parse_mode='Markdown')
            # Остаемся в текущем меню
            return
        else:
            db.set_user_search_active(user_id, True)
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
    
    elif data == "delete_custom_links":
        await show_delete_custom_menu(update, context, page=0)

    elif data.startswith("delete_page_"):
        # Обработка переключения страниц
        page = int(data.split("_")[2])
        await show_delete_custom_menu(update, context, page=page)

    elif data.startswith("del_custom_"):
        product_id = int(data.split("_")[2])
        db.delete_custom_link(user_id, product_id)
        await update.callback_query.answer("✅ Товар удалён из отслеживания", show_alert=True)
        
        # Получаем текущую страницу из контекста или начинаем с 0
        current_page = 0
        if context.user_data.get('current_delete_page'):
            current_page = context.user_data['current_delete_page']
        
        # Показываем обновленный список
        await show_delete_custom_menu(update, context, page=current_page)

    elif data == "current_page":
        # Просто обновляем текущую страницу
        await update.callback_query.answer(f"Страница {context.user_data.get('current_delete_page', 0) + 1}")

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
            "🎮 **Установка цены для PlayStation 5 Slim Blu-Ray**\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "💡 **Пример:** 50000\n\n"
            "🔍 Бот будет искать PS5 Slim Blu-Ray в диапазоне согласно вашему автоматическому порогу.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
     # Установка цены для PS5
    elif data == "set_ps5_pro":
        db.set_waiting_for_price(user_id, 1, 'ps5_pro')
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_ps5")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎮 **Установка цены для PlayStation 5 Pro**\n\n"
            "Введите максимальную цену в рублях (только цифры):\n\n"
            "💡 **Пример:** 50000\n\n"
            "🔍 Бот будет искать PS5 Pro с дисководом в диапазоне согласно вашему автоматическому порогу.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif data == "set_wb_token":
      if user_id != ADMIN_USER_ID:
          await query.answer("❌ Доступ запрещён", show_alert=True)
          return
      db.set_waiting_for_price(user_id, 1, 'wb_token')
      keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")]]
      reply_markup = InlineKeyboardMarkup(keyboard)
      await query.edit_message_text(
          "🔑 **Изменение токена Wildberries**\n"
          "Введите **новый токен авторизации**:\n\n",
          reply_markup=reply_markup,
          parse_mode='Markdown'
      )
    
    elif data == "add_custom_link":
      db.set_waiting_for_price(user_id, 1, 'custom_link')
      await query.edit_message_text(
          "🔗 **Отслеживание по ссылке**\n"
          "Вставьте **ссылку на товар Wildberries**:\n"
          "Пример: `https://www.wildberries.ru/catalog/61073258/detail.aspx`\n\n"
          "🔔 Вы получите уведомление, если цена **снизится**.",
          parse_mode='Markdown',
          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products_links")]])
      )
    
    elif data == "products_items":
        await show_products_items_menu(update, context)

    elif data == "products_links":
        await show_products_links_menu(update, context)

    elif data == "back_to_products":
        db.clear_waiting_for_price(user_id)
        await show_products_menu(update, context)

    elif data == "back_to_products_links":
      await show_products_links_menu(update, context)

    elif data == "back_to_products_items":
      await show_products_items_menu(update, context)

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
    """Обработчик текстовых сообщений для установки цен, порога, скидки, токена WB и кастомных ссылок"""
    user_id = update.effective_user.id
    waiting_for_price, product_type = db.get_waiting_for_price(user_id)
    
    if waiting_for_price and product_type:
        text = update.message.text.strip()
        
        # Обработка команды "назад" через текст
        if text.lower() in ['назад', 'back', 'отмена', 'cancel']:
            db.clear_waiting_for_price(user_id)
            await show_menu(update, context)
            return
        
        # === 1. Обработка ввода ссылки на товар ===
        # === Обработка ссылки на товар ===
        if product_type == 'custom_link':
            url = text.strip()
            match = re.search(r'/catalog/(\d+)', url)
            if not match:
                await update.message.reply_text(
                    "❌ Неверная ссылка. Пример:\n"
                    "`https://www.wildberries.ru/catalog/12345678/detail.aspx`",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_parser")]])
                )
                return

            product_id = int(match.group(1))

            # 🔸 Гарантируем наличие записи в user_settings
            cursor = db.conn.cursor()
            cursor.execute('SELECT 1 FROM user_settings WHERE user_id = ?', (user_id,))
            if not cursor.fetchone():
                cursor.execute(
                    'INSERT INTO user_settings (user_id, discount_percent, price_threshold) VALUES (?, 7, 50)',
                    (user_id,)
                )
                db.conn.commit()

            # 🔸 Получаем скидку пользователя
            discount_percent, _ = db.get_user_settings(user_id)

            # 🔸 Получаем базовую цену без скидки
            connector = aiohttp.TCPConnector(limit=5)
            async with aiohttp.ClientSession(connector=connector) as session:
                base_price = await get_detailed_product_price(session, product_id, discount_percent=0)
                if base_price is None:
                    await update.message.reply_text(
                        "❌ Не удалось получить цену. Попробуйте позже.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="products_links")]])
                    )
                    return
                # Применяем скидку пользователя
                current_price = math.floor(base_price * (100 - discount_percent) / 100)

            # Сохраняем как initial_price (уже со скидкой!)
            db.add_custom_link(user_id, product_id, current_price)
            db.clear_waiting_for_price(user_id)

            await update.message.reply_text(
                f"✅ Товар добавлен в отслеживание!\n"
                f"Артикул: `{product_id}`\n"
                f"Текущая цена (с учётом вашей скидки {discount_percent}%): {current_price:} руб.\n"
                f"🔔 Вы получите уведомление, если цена **снизится**.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="products_links")]])
            )
            return
        
       
        # === 3. Обработка ввода токена WB ===
        if product_type == 'wb_token':
            token = text.replace("Bearer", "").strip()
            if not token.startswith("eyJ"):
                keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "❌ Неверный формат токена. Он должен начинаться с `eyJ...`",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return
            db.set_system_config("wb_authorization", token)
            db.set_system_config("last_token_alert_time", "")
            db.clear_waiting_for_price(user_id)
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "✅ **Токен Wildberries успешно обновлён!**\nТаймер уведомлений о проблемах с токеном сброшен.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        # === 4. Обработка остальных числовых значений (скидка, порог, цены на iPhone/PS5) ===
        if not re.match(r'^\d+$', text):
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
                    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(
                        "❌ Скидка должна быть от 1% до 50%",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    return
                discount_percent, _ = db.get_user_settings(user_id)
                db.set_user_discount(user_id, value)
                db.clear_waiting_for_price(user_id)
                keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]]
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
                    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(
                        "❌ Порог должен быть от 0% до 100%",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    return
                db.set_user_threshold(user_id, value)
                db.clear_waiting_for_price(user_id)
                keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]]
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
            
            elif product_type in ['iphone_16_128', 'iphone_16_256', 'iphone_16_pro_128', 
                                'iphone_16_pro_256', 'iphone_16_pro_max', 'ps5_slim_disk', 'ps5_pro']:
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
                db.set_user_product_price(user_id, product_type, value)
                db.clear_waiting_for_price(user_id)
                config = db.get_search_config(product_type)
                product_name = config['product_name'] if config else product_type
                _, price_threshold = db.get_user_settings(user_id)
                if price_threshold > 0:
                    min_price = math.floor(value * (price_threshold / 100))
                    range_info = f"{min_price:,} - {value:,} руб.".replace(',', ' ')
                else:
                    range_info = f"от 0 до {value:,} руб.".replace(',', ' ')
                keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="products_items")]]
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
        # Если сообщение вне контекста — показываем меню
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
        job_queue.run_repeating(price_checker_job, interval=30, first=10)
        print("✅ JobQueue запущен")
    else:
        print("❌ JobQueue не доступен, используем альтернативный метод")
        async def run_checks():
            while True:
                await check_all_prices(application)
                await asyncio.sleep(30)
        asyncio.create_task(run_checks())
    
    print("🤖 Бот запущен!")
    application.run_polling()

if __name__ == "__main__":
    main()