import aiohttp
import asyncio
from datetime import datetime, timedelta
import math
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import logging
import re
import random
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = "8459198512:AAGT_naxAdmepRFAkQMDuG-fmRgbFrTVtSg"
#BOT_TOKEN = "7998443497:AAGnYx7to86c-7H7HWcrXQFr4UDuj9ocQ3U"
ADMIN_USER_ID = 300446433
IPHONE_16_MIN_THRESHOLD = 10
COUNTER = 0
MAX_COUNTER = 3

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
    """
    Забирает товары из WB search по конфигу и сразу фильтрует по include/exclude.
    Возвращает список products (как в WB JSON).
    """
    products: list[dict] = []
    seen_ids: set[int] = set()

    search_queries = config.get("search_queries", [])
    filter = config['filters']
    if filter: filter = "&" + filter
    include_keywords = [k.lower() for k in config.get("include_keywords", [])]
    exclude_keywords = [k.lower() for k in config.get("exclude_keywords", [])]

    for query in range(len(search_queries)):
        
        url = (
            "https://search.wb.ru/exactmatch/ru/common/v18/search"
            f"?ab_testid=no_action&ab_testing=false&appType=1&curr=rub&dest=123589415{filter}"
            f"&hide_dtype=11&inheritFilters=false&lang=ru&page=1&query={search_queries[query]}"
            "&resultset=catalog&sort=priceup&spp=30&suppressSpellcheck=false&uclusters=0"
        )

        try:
            async with session.get(url, headers=get_headers_from_db(), timeout=10) as resp:
                text = await resp.text()
                if not text.strip():
                    print(f"⚠️ Пустой ответ WB search для '{search_queries[query]}'")
                    continue
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    print(f"❌ JSON decode error WB search для '{search_queries[query]}'")
                    continue
        except asyncio.TimeoutError:
            print(f"⏰ Timeout WB search для '{search_queries[query]}'")
            continue
        except Exception as e:
            print(f"❌ Ошибка WB search для '{search_queries[query]}': {e}")
            continue

        items = data.get("products") or []
        if not items:
            print(f"ℹ️ WB search: нет товаров для '{search_queries[query]}'")
            continue

        added = 0
        for p in items:
            pid = p.get("id")
            if not pid or pid in seen_ids:
                continue

            name_lower = str(p.get("name", "")).lower()

            # include: ВСЕ слова должны быть в названии
            if any(k not in name_lower for k in include_keywords):
                continue
            # exclude: НИ ОДНО слово не должно быть в названии
            if any(k in name_lower for k in exclude_keywords):
                continue

            seen_ids.add(pid)
            products.append(p)
            added += 1

        print(f"✅ WB search '{search_queries[query]}': получили {len(items)}, добавили {added}")

    print(f"📦 Итого по конфигу: {len(products)} товаров")
    return products



def should_include_product(name_lower: str, product_type: str, config: dict) -> bool:
    """
    Универсальная проверка товара по конфигу.
    include — все слова должны присутствовать
    exclude — ни одно слово не должно присутствовать
    """
    include_keywords = [k.lower() for k in config.get("include_keywords", [])]
    exclude_keywords = [k.lower() for k in config.get("exclude_keywords", [])]

    if any(k not in name_lower for k in include_keywords):
        return False
    if any(k in name_lower for k in exclude_keywords):
        return False
    
    if "iphone" in product_type:
        return check_for_nano_sim_plus_Esim(name_lower)

    return True

def check_for_nano_sim_plus_Esim(name_lower: str) -> bool:
    """
    Проверка на наличие нано-сим + Есим в названии товара.
    Или если они отсутствуют в названии тоже добавляем товар.
    """

    name_replaced = name_lower.replace("esim", "").replace("e-sim", "")

    if len(name_replaced) == len(name_lower) or "sim" in name_replaced:
      return True
    
    return False

# =========================
# 1) DETALKA + CACHE (base_price only)
# =========================

async def get_detailed_product_base(session, product_id: int) -> dict:
    """
    Детальная карточка WB. Всегда возвращает base_price (без скидки).

    dict:
    {
        "product_id": int,
        "base_price": int|None,         # цена без скидки
        "in_stock": bool|None,
        "total_qty": int|None,
        "name": str|None,
        "supplierRating": float|None
    }
    """
    result = {
        "product_id": product_id,
        "base_price": None,
        "in_stock": None,
        "total_qty": None,
        "name": None,
        "supplierRating": None,
    }

    url = (
        "https://u-card.wb.ru/cards/v4/list"
        f"?appType=1&curr=rub&dest=-1586348&spp=30&hide_dtype=11"
        f"&ab_testing=false&lang=ru&nm={product_id}&ignore_stocks=true"
    )

    try:
        async with session.get(url, headers=get_headers_without_auth(), timeout=7) as resp:
            text = await resp.text()
            try:
                r = json.loads(text)
            except json.JSONDecodeError:
                return result
        
        products = r.get("products") or []
        if not products:
            # карточка недоступна / товара нет
            result["in_stock"] = False
            result["total_qty"] = 0
            return result

        p = products[0]

        # meta
        result["name"] = p.get("name")
        result["supplierRating"] = p.get("supplierRating")

        # qty
        qty_raw = p.get("totalQuantity", None)
        if qty_raw is not None:
            try:
                qty = int(qty_raw)
                result["total_qty"] = qty
                result["in_stock"] = qty > 0
            except Exception:
                result["total_qty"] = None
                result["in_stock"] = None

        # base price (без скидки)
        try:
            base_price = math.floor(p["sizes"][0]["price"]["product"]) / 100
            result["base_price"] = int(base_price)
        except Exception:
            # цена может отсутствовать, но наличие мы уже знаем
            pass

        return result

    except asyncio.TimeoutError:
        print(f"⏰ Timeout детальной карточки {product_id}")
        return result
    except Exception as e:
        print(f"❌ Ошибка детальной карточки {product_id}: {e}")
        return result


async def get_product_details_cached(session, product_id: int, cache: dict) -> dict:
    """
    Возвращает деталку из кеша на прогон.
    cache: dict[int, dict]
    """
    if product_id in cache:
        return cache[product_id]

    info = await get_detailed_product_base(session, product_id)
    cache[product_id] = info
    return info


def calc_discounted_price(base_price: int | None, discount_percent: int) -> int | None:
    if base_price is None:
        return None
    return math.floor(base_price * (100 - int(discount_percent)) / 100)

def is_price_ok_for_user(discounted_price: int | None, max_price: int, threshold_percent: int) -> bool:
    if discounted_price is None:
        return False
    min_price = math.floor(max_price * (threshold_percent / 100)) if threshold_percent and threshold_percent > 0 else 0
    return (min_price < discounted_price < max_price)


# =========================
# 2) MESSAGES (same, ok)
# =========================

async def send_product_messages(application, user_id, products, title, max_products_per_message=15):
    if not products:
        return

    products.sort(key=lambda x: x.get("price", 10**18))
    chunks = [products[i:i + max_products_per_message] for i in range(0, len(products), max_products_per_message)]

    for idx, chunk in enumerate(chunks):
        msg = f"{title}\n\n"
        if len(chunks) > 1:
            msg += f"*Часть {idx + 1} из {len(chunks)}*\n\n"

        for product in chunk:
            qty = product.get("totalQuantity", "?")
            link = f"[{product['name']}]({product['link']})"

            if product.get("price_dropped") and product.get("previous_price"):
                prev = product["previous_price"]
                cur = product["price"]
                drop = prev - cur
                drop_pct = (drop / prev) * 100 if prev else 0

                msg += f"🔵 {link}\n"
                if product.get("supplier_rating") is not None:
                    msg += f"⭐ Рейтинг продавца: {product['supplier_rating']}\n"
                elif product.get("supplier"):
                    msg += f"🏪 Продавец: {product['supplier']}\n"

                msg += f"💰 Цена: {cur:,} руб. (была {prev:,} руб.)\n".replace(",", " ")
                msg += f"📉 Снижение: {drop:,} руб. ({drop_pct:.1f}%)\n".replace(",", " ")
            else:
                msg += f"🔵 {link} ({qty} шт)\n"
                if product.get("supplier_rating") is not None:
                    msg += f"⭐ Рейтинг продавца: {product['supplier_rating']}\n"
                elif product.get("supplier"):
                    msg += f"🏪 Продавец: {product['supplier']}\n"
                msg += f"💰 Цена: {product['price']:,} руб.\n".replace(",", " ")

            msg += "\n"

        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=msg,
                reply_markup=get_main_reply_keyboard() if idx == 0 else None,
                disable_web_page_preview=True,
                parse_mode="Markdown",
            )
        except Exception as e:
            print(f"❌ Ошибка отправки пользователю {user_id}: {e}")

    print(f"✅ Отправлено {len(chunks)} сообщений пользователю {user_id}")


# =========================
# 3) BACK-IN-STOCK NOTIFY (needs base->discounted calc)
# =========================

async def notify_back_in_stock(application, user_id, product_id, info: dict, discounted_price: int):
    products = [{
        "id": product_id,
        "name": info.get("name") or f"Товар WB (артикул {product_id})",
        "price": discounted_price,
        "previous_price": None,
        "price_dropped": False,
        "link": f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx",
        "supplier": "—",
        "supplier_rating": info.get("supplierRating"),
        "totalQuantity": info.get("total_qty") if info.get("total_qty") is not None else "?",
    }]
    await send_product_messages(
        application,
        user_id,
        products,
        "✅ Товар снова появился в наличии:",
        max_products_per_message=15
    )

# =========================
# 4) FILTER FOR USER (uses cache+base_price; no get_detailed_product_price)
# =========================

async def filter_products_for_user(
    application,
    user_id,
    product_type,
    max_price,
    discount_percent,
    price_threshold,
    products,
    session,
    details_cache: dict,
):
    """
    Фильтрует товары по цене и отправляет уведомления о:
      - новом товаре
      - падении цены
    НЕ отправляет уведомления "снова в наличии" (это делает check_all_prices в 1 месте).
    """
    if db.is_user_waiting_for_input(user_id):
        return

    config = db.get_search_config(product_type)
    if not config:
        return

    min_price = math.floor(max_price * (price_threshold / 100)) if price_threshold > 0 else 0
    found = []

    for p in products:
        pid = p.get("id")
        if not pid:
            continue

        name = str(p.get("name", ""))
        name_lower = name.lower()
        if not should_include_product(name_lower, product_type, config):
            continue

        # грубая цена из выдачи — быстрый предварительный фильтр
        try:
            base_price_search = math.floor(p["sizes"][0]["price"]["product"]) / 100
        except Exception:
            continue

        approx_discounted = base_price_search * ((100 - discount_percent) / 100)
        if not (min_price < approx_discounted < max_price):
            continue

        # детальная карточка (через кеш)
        info = await get_product_details_cached(session, pid, details_cache)

        # если детально выяснили что товара НЕТ — ставим 0 и не шлём по цене
        if info.get("in_stock") is False:
            db.update_in_stock(user_id, pid, 0)
            continue

        detailed_discounted = calc_discounted_price(info.get("base_price"), discount_percent)
        if detailed_discounted is None:
            continue

        if not (min_price < detailed_discounted < max_price):
            continue

        should_send, prev_price, price_dropped = db.save_notification(
            user_id, pid, detailed_discounted, discount_percent
        )
        if not should_send:
            continue

        found.append({
            "id": pid,
            "name": name,
            "price": detailed_discounted,
            "previous_price": prev_price,
            "price_dropped": price_dropped,
            "link": f"https://www.wildberries.ru/catalog/{pid}/detail.aspx",
            "supplier": p.get("supplier", "—"),
            "supplier_rating": info.get("supplierRating", None),
            "totalQuantity": info.get("total_qty") if info.get("total_qty") is not None else p.get("totalQuantity", "?"),
        })

    if found:
        product_name = config.get("product_name", product_type)
        if "iphone" in product_type:
            title = f"📱 Найдены {product_name} по выгодным ценам:"
        elif "ps5" in product_type:
            title = f"🎮 Найдены {product_name} по выгодным ценам:"
        else:
            title = f"🖥 Найдены {product_name} по выгодным ценам:"

        await send_product_messages(application, user_id, found, title, max_products_per_message=15)


# =========================
# 5) CHECK ALL PRICES (single stock logic point + cache + base_price for customs)
# =========================

async def check_all_prices(application):
    """
    FIX:
      - "back in stock" уведомление отправляем ТОЛЬКО если новая цена подходит под ограничения пользователя.
      - для этого хранится seen как pid -> set(product_type) (а не просто set pid).
      - деталка кешируется на прогон.
    """
    try:
        deleted = db.cleanup_old_records(hours=24)
        if deleted > 0:
            print(f"🗑️ Очищено {deleted} старых записей")

        last_cleanup = db.get_system_config("last_custom_cleanup")
        now = datetime.now()
        if not last_cleanup or (now - datetime.fromisoformat(last_cleanup)).days >= 30:
            deleted_custom = db.cleanup_old_custom_links(days=30)
            print(f"🧹 Очищено {deleted_custom} старых кастомных ссылок")
            db.set_system_config("last_custom_cleanup", now.isoformat())

        all_configs = db.get_all_search_configs()
        active_users = db.get_users_with_any_active_tracking()
        if not active_users:
            return

        # user -> {prices, discount, threshold}
        users_with_prices: dict[int, dict] = {}
        all_tracked_types: set[str] = set()

        for uid in active_users:
            up = db.get_all_user_product_prices(uid)
            user_prices = {pt: data["price"] for pt, data in up.items()}
            if user_prices:
                disc, thr = db.get_user_settings(uid)
                users_with_prices[uid] = {"prices": user_prices, "discount": disc, "threshold": thr}
                all_tracked_types.update(user_prices.keys())

        connector = aiohttp.TCPConnector(limit=20)
        async with aiohttp.ClientSession(connector=connector) as session:
            # кеш деталки на прогон
            details_cache: dict[int, dict] = {}

            # 1) сбор выдачи по всем tracked types
            all_products: dict[str, list[dict]] = {}
            for product_type in all_tracked_types:
                cfg = all_configs.get(product_type)
                if not cfg:
                    continue
                all_products[product_type] = await get_products_by_config(session, cfg)

            await check_wb_token_health(application, all_products)

            # 2) кастомные ссылки
            custom_links_by_user: dict[int, dict[int, int]] = {}
            custom_product_ids: set[int] = set()
            for uid in active_users:
                links = db.get_user_custom_links(uid)
                if links:
                    custom_links_by_user[uid] = links
                    custom_product_ids.update(links.keys())

            # base_price по кастомным артикулам (через кеш)
            custom_base_prices: dict[int, int] = {}
            if custom_product_ids:
                for pid in custom_product_ids:
                    info = await get_product_details_cached(session, pid, details_cache)
                    if info.get("base_price") is not None:
                        custom_base_prices[pid] = info["base_price"]

            # 3) seen_ids по пользователю (pid -> set(product_type)) + фильтрация по цене
            user_seen_map: dict[int, dict[int, set[str]]] = {uid: {} for uid in users_with_prices.keys()}

            for uid, udata in users_with_prices.items():
                if db.is_user_waiting_for_input(uid):
                    continue

                for product_type, max_price in udata["prices"].items():
                    if max_price <= 0:
                        continue

                    prods = all_products.get(product_type) or []
                    if not prods:
                        continue

                    # собираем seen_map (ПОСЛЕ include/exclude)
                    cfg = db.get_search_config(product_type)
                    if cfg:
                        for p in prods:
                            pid = p.get("id")
                            if not pid:
                                continue
                            name_lower = str(p.get("name", "")).lower()
                            if should_include_product(name_lower, product_type, cfg):
                                user_seen_map[uid].setdefault(pid, set()).add(product_type)

                    # фильтрация по цене (использует кеш деталки)
                    await filter_products_for_user(
                        application,
                        uid,
                        product_type,
                        max_price,
                        udata["discount"],
                        udata["threshold"],
                        prods,
                        session,
                        details_cache,
                    )

            # 4) кастом: уведомление только при снижении цены
            if custom_links_by_user and custom_base_prices:
                for uid, links in custom_links_by_user.items():
                    if db.is_user_waiting_for_input(uid):
                        continue
                    disc, _ = db.get_user_settings(uid)

                    found = []
                    for pid, initial_price in links.items():
                        base = custom_base_prices.get(pid)
                        if base is None:
                            continue

                        current_discounted = calc_discounted_price(base, disc)
                        if current_discounted is None:
                            continue

                        if current_discounted < initial_price:
                            should_send, prev_price, _ = db.save_notification(uid, pid, current_discounted, disc)
                            if should_send:
                                found.append({
                                    "id": pid,
                                    "name": f"Товар WB (артикул {pid})",
                                    "price": current_discounted,
                                    "previous_price": prev_price or initial_price,
                                    "price_dropped": True,
                                    "link": f"https://www.wildberries.ru/catalog/{pid}/detail.aspx",
                                    "supplier": "—",
                                    "supplier_rating": None,
                                    "totalQuantity": "?",
                                })

                    if found:
                        await send_product_messages(
                            application,
                            uid,
                            found,
                            "📉 Цена на отслеживаемый товар снизилась:",
                            max_products_per_message=15
                        )

            # 5) ЕДИНСТВЕННОЕ место логики наличия + уведомлений "снова в наличии"
            for uid in users_with_prices.keys():
                if db.is_user_waiting_for_input(uid):
                    continue

                seen_map = user_seen_map.get(uid, {})          # pid -> set(product_type)
                seen_ids = set(seen_map.keys())               # pid set
                notified = db.get_user_notified_product_ids(uid)
                out_of_stock = db.get_user_out_of_stock_product_ids(uid)

                disc = users_with_prices[uid]["discount"]
                thr = users_with_prices[uid]["threshold"]

                # A) исчез из выдачи -> проверка -> если qty==0 => in_stock=0
                missing = notified - seen_ids
                for pid in missing:
                    info = await get_product_details_cached(session, pid, details_cache)
                    if info.get("in_stock") is False:
                        db.update_in_stock(uid, pid, 0)

                # B) вернулся в выдачу, а в БД был in_stock=0 -> проверка -> 0->1
                #    уведомляем ТОЛЬКО если цена подходит под ограничения пользователя
                back_candidates = seen_ids & out_of_stock
                for pid in back_candidates:
                    info = await get_product_details_cached(session, pid, details_cache)
                    if info.get("in_stock") is not True:
                        continue

                    # отмечаем наличие (чтобы не дергать этот pid снова каждый прогон)
                    _, became = db.update_in_stock(uid, pid, 1)
                    if not became:
                        continue

                    discounted_price = calc_discounted_price(info.get("base_price"), disc)
                    if discounted_price is None:
                        continue

                    ok = False
                    for pt in seen_map.get(pid, set()):
                        max_price = users_with_prices[uid]["prices"].get(pt)
                        if not max_price:
                            continue
                        if is_price_ok_for_user(discounted_price, max_price, thr):
                            ok = True
                            break

                    if ok:
                        await notify_back_in_stock(application, uid, pid, info, discounted_price)
                    else:
                        print(f"ℹ️ {pid} снова в наличии у {uid}, но цена {discounted_price} не подходит под лимиты")

            print("✅ Проверка завершена")

    except Exception as e:
        print(f"❌ Ошибка в check_all_prices: {e}")
        import traceback
        traceback.print_exc()

is_price_check_running = False


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

# async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Показывает главное меню"""
#     user_id = update.effective_user.id
#     discount_percent, price_threshold = db.get_user_settings(user_id)
    
#     # Получаем ВСЕ товары пользователя (включая неактивные)
#     user_products = db.get_all_user_product_prices(user_id)
    
#     # Получаем статус поиска
#     is_search_active = db.get_user_search_active(user_id)
#     search_status_icon = "🟢" if is_search_active else "🔴"
#     search_status_text = "активен" if is_search_active else "остановлен"
    
#     # Формируем информацию о установленных ценах
#     price_info = []

#     # 1. Стандартные товары
#     user_products = db.get_all_user_product_prices(user_id)
#     product_names = {
#         'iphone_16_128': 'iPhone 16 128Gb',
#         'iphone_16_256': 'iPhone 16 256Gb',
#         'iphone_16_pro_128': 'iPhone 16 Pro 128Gb',
#         'iphone_16_pro_256': 'iPhone 16 Pro 256Gb',
#         'iphone_16_pro_max': 'iPhone 16 Pro Max 256Gb',
#         'ps5_slim_disk': 'PlayStation 5 Slim',
#         'ps5_pro': 'PlayStation 5 Pro',
#     }
#     print(f"------------\n {user_products} ------------\n")
#     for product_type, product_data in user_products.items():
#         price = product_data['price']
#         if price > 0:
#             product_name = product_names.get(product_type, product_type)
#             price_info.append(f"• {product_name}: {price:,} руб.".replace(',', ' '))

#     all_custom_links = db.get_all_user_custom_links(user_id)
#     print(f"------------\n {all_custom_links} ------------\n")
#     for product_id, data in all_custom_links.items():
#         price_info.append(f"• Товар WB (артикул {product_id}): {data['price']:,} руб.".replace(',', ' '))

#     if not price_info:
#         price_info = ["Не установлены"]
        
#     keyboard = [
#         [InlineKeyboardButton("🤖 Парсер", callback_data="parser_menu")],
#         [InlineKeyboardButton("⚙️ Настройки", callback_data="settings_menu")],
#     ]
#     reply_markup = InlineKeyboardMarkup(keyboard)
    
#     message = (
#         f"{search_status_icon} **Статус поиска:** {search_status_text}\n\n"
#         "⚙️ **Ваши текущие настройки:**\n"
#         f"💸 Скидка WB: {discount_percent}%\n"
#         f"📉 Авт. порог: {price_threshold}%\n\n"
#         "📦 **Отслеживаемые товары:**\n" +
#         "\n".join(f"• {info}" for info in price_info) +
#         "\n\n💡 **Выберите раздел:**"
#     )
    
#     if update.callback_query:
#         await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
#     else:
#         await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

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
        [InlineKeyboardButton("📱 iPhone", callback_data="show_iphone_menu")],
        [InlineKeyboardButton("🎮 PlayStation", callback_data="ps5_menu")],
        [InlineKeyboardButton("🖥 Видеокарты", callback_data="rtx_menu")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "📦 **Управление товарами**\n\n"
        "Выберите категорию для настройки:"
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

async def show_iphone_16_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора моделей iPhone"""
    keyboard = [
        [InlineKeyboardButton("iPhone 16 128Gb", callback_data="set_iphone_16_128")],
        [InlineKeyboardButton("iPhone 16 256Gb", callback_data="set_iphone_16_256")],
        [InlineKeyboardButton("iPhone 16 Pro 128Gb", callback_data="set_iphone_16_pro_128")],
        [InlineKeyboardButton("iPhone 16 Pro 256Gb", callback_data="set_iphone_16_pro_256")],
        [InlineKeyboardButton("iPhone 16 Pro Max 256Gb", callback_data="set_iphone_16_pro_max")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_iphone_items")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "📱 **Выбор модели iPhone**\n\n"
        "Выберите конкретную модель для настройки:"
    )
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_iphone_17_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора моделей iPhone"""
    keyboard = [
        [InlineKeyboardButton("iPhone 17 256Gb", callback_data="set_iphone_17_256")],
        [InlineKeyboardButton("iPhone 17 Pro 256Gb", callback_data="set_iphone_17_pro_256")],
        [InlineKeyboardButton("iPhone 17 Pro Max 256Gb", callback_data="set_iphone_17_pro_max_256")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_iphone_items")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "📱 **Выбор модели iPhone**\n\n"
        "Выберите конкретную модель для настройки:"
    )
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_iphone_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора моделей iPhone"""
    keyboard = [
        [InlineKeyboardButton("iPhone 16", callback_data="iphone_16_menu")],
        [InlineKeyboardButton("iPhone 17", callback_data="iphone_17_menu")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products_items")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "📱 **Выбор модели iPhone**\n\n"
        "Выберите конкретную модель для настройки:"
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
        "Выберите конкретную модель для настройки:"
    )
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_rtx_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню для PS5"""
    keyboard = [
        [InlineKeyboardButton("Rtx 5060", callback_data="set_rtx_5060")],
        [InlineKeyboardButton("Rtx 5060 Ti 8G", callback_data="set_rtx_5060_ti_8")],
        [InlineKeyboardButton("Rtx 5060 Ti 16G", callback_data="set_rtx_5060_ti_16")],
        [InlineKeyboardButton("Rtx 5070", callback_data="set_rtx_5070")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_products_items")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "🖥 **Видеокарты**\n\n"
        "Выберите конкретную модель для настройки:"
    )
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для кнопки Меню под клавиатурой"""
    await show_menu(update, context)

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
    
    price_info = []

    user_products = db.get_all_user_product_prices(user_id)

    for product_type, product_data in user_products.items():
        price = product_data['price']
        if price > 0:
            product_name = product_data['product_name']
            price_info.append(f"• {product_name}: {price:,} руб.".replace(',', ' '))

    all_custom_links = db.get_all_user_custom_links(user_id)
    for product_id, data in all_custom_links.items():
        link = f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx"
        price_info.append(
            f"• Товар WB (артикул [{product_id}]({link})): "
            f"{data['price']:,} руб.".replace(',', ' ')
        )


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
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)

async def handle_reply_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на Reply кнопки"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "⚙️ Меню":
        # Показываем главное меню
        await show_menu(update, context)

async def show_set_price_screen(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                product_type: str, product_title: str, back_cb: str, example_price: int):
    query = update.callback_query
    user_id = query.from_user.id

    current_price = db.get_user_product_price(user_id, product_type)  # None если не задано
    has_tracking = current_price is not None and current_price > 0

    current_line = "— не задана"
    if current_price is not None and current_price > 0:
        current_line = f"{current_price:,} руб.".replace(",", " ")

    reply_markup = build_price_screen_keyboard(back_cb, product_type, has_tracking)

    await query.edit_message_text(
        f"📌 **Текущая цена:** {current_line}\n\n"
        f"📱 **Установка цены для {product_title}**\n\n"
        "Введите максимальную цену в рублях (только цифры):\n\n"
        f"💡 **Пример:** {example_price}\n\n"
        "🔍 Бот будет искать товар в диапазоне согласно вашему автоматическому порогу.",
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


def build_price_screen_keyboard(back_cb: str, product_type: str, has_tracking: bool):
    row = [InlineKeyboardButton("⬅️ Назад", callback_data=back_cb)]

    if has_tracking:
        row.append(
            InlineKeyboardButton("❌ Не отслеживать", callback_data=f"del_item_{product_type}")
        )

    return InlineKeyboardMarkup([row])


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
        
        active_products_count = len(user_products)
        active_custom_count = len(custom_links)
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
    
    elif data == "show_iphone_menu":
        await show_iphone_menu(update, context)

    elif data == "iphone_16_menu":
        await show_iphone_16_menu(update, context)
    
    elif data == "iphone_17_menu":
        await show_iphone_17_menu(update, context)
    
    elif data == "ps5_menu":
        await show_ps5_menu(update, context)

    elif data == "rtx_menu":
        await show_rtx_menu(update, context)
    
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
        await show_set_price_screen(update, context, "iphone_16_128", "iPhone 16 128Gb", "back_to_iphone_16", 60000)

    elif data == "set_iphone_16_256":
        db.set_waiting_for_price(user_id, 1, 'iphone_16_256')  
        await show_set_price_screen(update, context, "iphone_16_256", "iPhone 16 256Gb", "back_to_iphone_16", 70000)  

    elif data == "set_iphone_16_pro_128":
        db.set_waiting_for_price(user_id, 1, 'iphone_16_pro_128')
        await show_set_price_screen(update, context, "iphone_16_pro_128", "iPhone 16 Pro 128Gb", "back_to_iphone_16", 80000) 

    elif data == "set_iphone_16_pro_256":
        db.set_waiting_for_price(user_id, 1, 'iphone_16_pro_256')
        await show_set_price_screen(update, context, "iphone_16_pro_256", "iPhone 16 Pro 256Gb", "back_to_iphone_16", 90000)

    elif data == "set_iphone_16_pro_max":
        db.set_waiting_for_price(user_id, 1, 'iphone_16_pro_max')
        await show_set_price_screen(update, context, "iphone_16_pro_max", "iPhone 16 Pro Max 256Gb", "back_to_iphone_16", 100000)

    elif data == "set_iphone_17_256":
      db.set_waiting_for_price(user_id, 1, 'iphone_17_256')
      await show_set_price_screen(update, context, "iphone_17_256", "iPhone 17 256Gb", "back_to_iphone_17", 70000)
    
    elif data == "set_iphone_17_pro_256":
      db.set_waiting_for_price(user_id, 1, 'iphone_17_pro_256')
      await show_set_price_screen(update, context, "iphone_17_pro_256", "iPhone 17 Pro 256Gb", "back_to_iphone_17", 100000)
    
    elif data == "set_iphone_17_pro_max_256":
      db.set_waiting_for_price(user_id, 1, 'iphone_17_pro_max_256')
      await show_set_price_screen(update, context, "iphone_17_pro_max_256", "iPhone 17 Pro Max 256Gb", "back_to_iphone_17", 110000)

    elif data == "set_ps5_slim_disk":
        db.set_waiting_for_price(user_id, 1, 'ps5_slim_disk')
        await show_set_price_screen(update, context, "ps5_slim_disk", "PlayStation 5 Slim Blue-Ray", "back_to_ps5", 50000)
    
    elif data == "set_ps5_pro":
        db.set_waiting_for_price(user_id, 1, 'ps5_pro')
        await show_set_price_screen(update, context, "ps5_pro", "PlayStation 5 Pro", "back_to_ps5", 70000)
    
    elif data == "set_rtx_5060":
        db.set_waiting_for_price(user_id, 1, 'rtx_5060')
        await show_set_price_screen(update, context, "rtx_5060", "Rtx 5060", "back_to_rtx", 30000)
    
    elif data == "set_rtx_5060_ti_8":
        db.set_waiting_for_price(user_id, 1, 'rtx_5060_ti_8')
        await show_set_price_screen(update, context, "rtx_5060_ti_8", "Rtx 5060 Ti 8G", "back_to_rtx", 35000)
    
    elif data == "set_rtx_5060_ti_16":
        db.set_waiting_for_price(user_id, 1, 'rtx_5060_ti_16')
        await show_set_price_screen(update, context, "rtx_5060_ti_16", "Rtx 5060 Ti 16G", "back_to_rtx", 40000)
    
    elif data == "set_rtx_5070":
        db.set_waiting_for_price(user_id, 1, 'rtx_5070')
        await show_set_price_screen(update, context, "rtx_5070", "Rtx 5070", "back_to_rtx", 50000)

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
    
    elif data.startswith("del_item_"):
      product_type = data.replace("del_item_", "", 1)

      deleted = db.delete_user_product_price(user_id, product_type)

      # Если удалили — можно очистить состояние ожидания ввода
      db.clear_waiting_for_price(user_id)

      if deleted:
          await query.answer("✅ Отслеживание удалено", show_alert=True)
      else:
          await query.answer("ℹ️ Этот товар уже не отслеживается", show_alert=True)

      # Опционально: если после удаления больше ничего не отслеживается — выключаем поиск
      user_products = db.get_all_user_product_prices(user_id)
      custom_links = db.get_all_user_custom_links(user_id)
      active_products_count = len([1 for _, d in user_products.items() if int(d.get("price", 0)) > 0])
      if active_products_count + len(custom_links) == 0:
          db.set_user_search_active(user_id, False)

      # Возвращаем пользователя туда, где он был логически:
      # если удаляет стандартный товар — логично вернуть в меню товаров (или айфонов/ps5)
      await show_products_items_menu(update, context)
    
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

    elif data == "back_to_iphone_items":
      await show_iphone_menu(update, context)

    elif data == "back_to_main":
        await show_menu(update, context)

    elif data == "back_to_settings":
        # Очищаем состояние ожидания ввода и возвращаем в меню настроек
        db.clear_waiting_for_price(user_id)
        await show_settings_menu(update, context)

    elif data == "back_to_iphone_16":
        # Очищаем состояние ожидания ввода и возвращаем в меню iPhone
        db.clear_waiting_for_price(user_id)
        await show_iphone_16_menu(update, context)
    
    elif data == "back_to_iphone_17":
        # Очищаем состояние ожидания ввода и возвращаем в меню iPhone
        db.clear_waiting_for_price(user_id)
        await show_iphone_17_menu(update, context)

    elif data == "back_to_ps5":
        # Очищаем состояние ожидания ввода и возвращаем в меню PS5
        db.clear_waiting_for_price(user_id)
        await show_ps5_menu(update, context)
    
    elif data == "back_to_rtx":
        # Очищаем состояние ожидания ввода и возвращаем в меню PS5
        db.clear_waiting_for_price(user_id)
        await show_rtx_menu(update, context)
    
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
                detailed_product_info = await get_detailed_product_base(session, product_id)
                if detailed_product_info["base_price"] is None:
                    await update.message.reply_text(
                        "❌ Не удалось получить цену. Попробуйте позже.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="products_links")]])
                    )
                    return
                # Применяем скидку пользователя
                current_price = math.floor(detailed_product_info["base_price"] * (100 - discount_percent) / 100)

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
            
            elif product_type in ['iphone_16_128', 'iphone_16_256', 'iphone_16_pro_128', 'iphone_16_pro_256', 'iphone_16_pro_max', 
                                  'iphone_17_256', 'iphone_17_pro_256', 'iphone_17_pro_max_256', 'ps5_slim_disk', 'ps5_pro', 
                                  'rtx_5060', 'rtx_5060_ti_8', 'rtx_5060_ti_16', 'rtx_5070']:
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
        job_queue.run_repeating(price_checker_job, interval=15, first=10)
        print("✅ JobQueue запущен")
    else:
        print("❌ JobQueue не доступен, используем альтернативный метод")
        async def run_checks():
            while True:
                await check_all_prices(application)
                await asyncio.sleep(15)

        asyncio.create_task(run_checks())
    
    print("🤖 Бот запущен!")
    application.run_polling()

if __name__ == "__main__":
    main()