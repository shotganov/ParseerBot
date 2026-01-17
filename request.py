import requests

# # # # Создаем строку (пока query = захардкоженое значение)
# query = "iphone 16"
# url = f"https://search.wb.ru/exactmatch/ru/common/v18/search?ab_testid=reranking_price_6&ab_testing=false&appType=1&curr=rub&dest=-1586348&hide_dtype=11&inheritFilters=false&lang=ru&page=1&query={query}&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false&uclusters=3"

# # url1 = f"https://search.wb.ru/exactmatch/ru/common/v18/search?ab_testid=reranking_price_6&ab_testing=false&appType=1&curr=rub&dest=-1586348&hide_dtype=11&inheritFilters=false&lang=ru&page={i}&query={query}&resultset=catalog&sort=priceup&spp=30&suppressSpellcheck=false&uclusters=3"
# products = []

# #https://search.wb.ru/exactmatch/ru/common/v18/search?ab_testid=reranking_price_6&ab_testing=false&appType=1&curr=rub&dest=-1586348&hide_dtype=11&inheritFilters=false&lang=ru&page={i}&query={query}&resultset=catalog&sort=priceup&spp=30&suppressSpellcheck=false&uclusters=3
# for i in range(1, 10): 
#   try:
#     print(i)
#     response = requests.get(f"https://search.wb.ru/exactmatch/ru/common/v18/search?ab_testid=reranking_price_6&ab_testing=false&appType=1&curr=rub&dest=-1586348&hide_dtype=11&inheritFilters=false&lang=ru&page={i}&query={query}&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false&uclusters=3")
#     data = response.json()
#     for j in range(len(data["products"])):
#       if data["products"][j] not in products:
#         products.append(data["products"][j])
#   except (ValueError, TypeError) as e:
#     print(f"An error occurred: {e}")
#     break

# print(len(products))
# max_price = 50000
# links = []
# f = 0
# for i in range(len(products)):
#   name = str(products[i]["name"])
#   product_price = int(products[i]['sizes'][0]['price']['product'])/100 * 0.94 
#   if ("Digital" in name or 
#     "digital" in name or
#     "без дисковода" in name or
#     "бездисковая" in name or
#     "цифровая" in name):
#     continue
  
#   if product_price < max_price and product_price > max_price/2:
#     # Доп проверка цены
#     req = requests.get(f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={products[i]["id"]}")
#     req = req.json()
#     try:
#       product_price = int(req['data']['products'][0]['sizes'][0]['price']['product'])/100 * 0.94
#     except:
#       continue

#     if product_price < max_price and product_price > max_price/2:
#       links.append(f"https://www.wildberries.ru/catalog/{products[i]["id"]}/detail.aspx")

# for i in range(len(links)):
#   print(links[i])


# HEADERS = {
#     "authority": "u-card.wb.ru",
#     "authorization" : "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3NjE3NzEzNTcsInVzZXIiOiI1NzMxNjk0NCIsInNoYXJkX2tleSI6IjE2IiwiY2xpZW50X2lkIjoid2IiLCJzZXNzaW9uX2lkIjoiODUzZTEwYTE4NGRmNDc5NmEyNjYyNzRiY2ZjMzMzN2UiLCJ2YWxpZGF0aW9uX2tleSI6IjM5ODA3OGQ0N2VlZTk4NzgxNjQ4MTg3ZWE3ZDY3ZDE0ZmM3OGZlYWFjYjljNWI2Y2U4YjU4NTlmMGM0YTVhNDAiLCJwaG9uZSI6InhMK29IODloM2Q0OFlpTnVIUVpaK3c9PSIsInVzZXJfcmVnaXN0cmF0aW9uX2R0IjoxNjg1Mzg3MzI0LCJ2ZXJzaW9uIjoyfQ.AUnDL_lNpQRFaFBc_UjzD0ChFk8v0q_7hfZ_qp3OAgitskB7x7MbVvawUXh5wL11F3dHGyRpJH1UomPdtRbvR_-pCLsgJRRoDRnYmxGM1sw4ItLv1Ez1RiXamtzR3-aebJ0Xgg_wuqDkyzEi6VWd_QzIWtzC1LGpxxsMKL3LMIATQwjoWc7B6b4uGzRMVqM9XpCXXzGNlwwi5B4vzPkDVBtWEmxJU1pQUlk72jxdPm_uYVeLsvhHZvhmtVyYcIiD17EncnlLcEBvyfmSxl6NN8j5uOn6_7XJ9u1ZzeD8dJE0OOiWIe43kpYW5Sr6x9LGPBFcYTT4mwTXk7CTDXnyPg",
#     "accept": "*/*",
#     "accept-encoding": "gzip, deflate, br, zstd",
#     "accept-language": "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
#     "origin": "https://www.wildberries.ru",
#     "priority": "u=1, i",
#     "referer": "https://www.wildberries.ru/",
#     "sec-ch-ua": '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
#     "sec-ch-ua-mobile": "?0",
#     "sec-ch-ua-platform": '"Windows"',
#     "sec-fetch-dest": "empty",
#     "sec-fetch-mode": "cors",
#     "sec-fetch-site": "cross-site",
#     "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0"
# }


# HEADERS_ = {
#     "authority": "u-card.wb.ru",
  
#     "accept": "*/*",
#     "accept-encoding": "gzip, deflate, br, zstd",
#     "accept-language": "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
#     "origin": "https://www.wildberries.ru",
#     "priority": "u=1, i",
#     "referer": "https://www.wildberries.ru/",
#     "sec-ch-ua": '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
#     "sec-ch-ua-mobile": "?0",
#     "sec-ch-ua-platform": '"Windows"',
#     "sec-fetch-dest": "empty",
#     "sec-fetch-mode": "cors",
#     "sec-fetch-site": "cross-site",
#     "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0"
# }




# # Примеры использования:


# # Разные варианты поискового запроса
# search_queries1 = [
#      "playstation 5 slim",
#       "playstation 5 slim с дисководом", 
#       "playstation 5",
#       "ps5",
#       "ps 5",
#       "ps5 blue-ray",
#       "ps 5 blue ray",
#       "игровая консоль playstation 5",
# ]

# search_queries1 = [
#     # Основные запросы
#     "iPhone 15",
#     "iPhone 15 128gb",
#     "iPhone 15 256gb", 
#     "iPhone 15 512gb",
    
#     # С типом SIM
#     "iPhone 15 sim + esim",
#     "iPhone 15 dual sim",
#     "iPhone 15 две сим",
    
#     # С цветами
#     "iPhone 15 черный",
#     "iPhone 15 белый",
#     "iPhone 15 синий",
#     "iPhone 15 розовый",
#     "iPhone 15 зеленый",
#     "iPhone 15 желтый",
#     "iPhone 15 purple",
#     "iPhone 15 black", 
#     "iPhone 15 white",
#     "iPhone 15 blue",
#     "iPhone 15 pink",
#     "iPhone 15 green",
#     "iPhone 15 yellow",
#     "Смартфон iPhone 15"
# ]

# search_queries16 = [
#           "iPhone 16", "iPhone 16 128gb", "iPhone 16 sim + esim", "iPhone 16 dual sim",
#           "iPhone 16 две сим", "iPhone 16 черный", "iPhone 16 белый", "iPhone 16 синий",
#           "iPhone 16 розовый", "iPhone 16 бирюзовый", "iPhone 16 purple", "iPhone 16 ultramarine", "Смартфон iPhone 16", "iPhone 16 (без Ru Store)", "Смартфон iPhone 16 128 Гб (без Ru Store)", "Смартфон iPhone 16 Без RuStore и MAX", "Смартфон iPhone 16 Без MAX",
#           "iPhone 16 black", "iPhone 16 white", "iPhone 16 teal", "Apple iPhone 16"
#         ]

# search_queries = [
#     "iPhone 16 Pro", "iPhone 16 Pro 256gb", "iPhone 16 Pro sim + esim", "iPhone 16 Pro dual sim",
#     "iPhone 16 Pro две сим", "iPhone 16 Pro титановый", "iPhone 16 Pro черный", "iPhone 16 Pro белый",
#     "iPhone 16 Pro натуральный титан", "iPhone 16 Pro пустынный титан",
#     "Cмартфон Apple iPhone 16 Pro black", "Cмартфон Apple iPhone 16 Pro white",
#     "Cмартфон Apple iPhone 16 Pro natural titanium", "Cмартфон Apple iPhone 16 Pro desert titanium", "Смартфон iPhone 16 Pro (nano SIM+eSIM), 256Gb, Desert",
#     "Cмартфон Apple iPhone 16 Pro Натуральный титан", "Cмартфон Apple iPhone 16 Pro Песочный титан", "Телефон iphone 16 pro 256 ГБ"
#     "iPhone 16 Pro 256гб Золотистый",
#     "Смартфон iPhone 16 Pro 128 Гб (без Ru Store)", "Смартфон iPhone 16 Pro 256 Гб (без Ru Store)", "iPhone 16 Pro 256GB Desert без RuStore", ""
#     "Смартфон iPhone 16 Pro Без RuStore и MAX", "Смартфон iPhone 16 Pro Без MAX", "iPhone 16 Pro 256GB Desert,без RuStore", 
#     "iPhone 16 Pro 256 black", "iPhone 16 Pro 256 white", "iPhone 16 Pro 256 natural titanium", "iPhone 16 Pro 256 desert titanium",
#     "iPhone 16 Pro 256 ГБ Desert Titanium Nano-sim+eSIM", "iPhone 16 Pro 256 ГБ Black Titanium Nano-sim+eSIM", "Смартфон iPhone 16 Pro 256GB nano SIM + eSIM", "iPhone 16 Pro 256GB, White Titanium (Белый) SIM+eSIM",
# ]


# "https://u-search.wb.ru/exactmatch/ru/common/v18/search?ab_testing=false&ab_testing=false&appType=1&curr=rub&dest=-1586361&hide_dtype=11&inheritFilters=false&lang=ru&page=4&query=iphone%2016%20pro&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false"

# "https://u-search.wb.ru/exactmatch/ru/common/v18/search?ab_testing=false&ab_testing=false&appType=1&curr=rub&dest=-1586361&hide_dtype=11&inheritFilters=false&lang=ru&page=1&query=iphone%2016%20pro&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false"



# iphone_exclude_keywords16 = [
#     "15", "14", "13", "11", "iphone 15", "iphone 14", "iphone 13", "iphone 12", "iphone 11", "iphone xr", "iphone xs", "iphone x", "iphone 8", "iphone 7", "iphone 6",
#     "16e", "16 e", "16 plus", "16 plus",
#     "восстановленный", "ремоторизованный", "refurbished", "б/у", "used",
#     "восстановлен", "отремонтированный", "восстанавливать"
# ]

# iphone_exclude_keywords = [
#     # другие модели iPhone
#     "15", "14", "13", "12", "11", "10", "x", "xs", "xr", "8", "7",
#     "iphone 15", "iphone 14", "iphone 13", "iphone 12", "iphone 11",
#     "iphone xs", "iphone xr", "iphone x", "iphone se", "iphone 8", "iphone 7", "iphone 6",
    
#     # другие версии iPhone 16
#     "16e", "16 e", "16 plus", "16 plus", "16 pro max", "pro max", "max",
#     "iphone 16 128", "iphone 16 256", "iphone 16 512", "16 cn", "16 CN"

#     # восстановленные, б/у, отремонтированные
#     "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used",
#     "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка!", "обменка"

#     # версии без нужного объема памяти
#     "128", "512", "1tb", "1 tb", "tb", "64",
# ]



# Список для исключения PS5 без дисковода (в нижнем регистре)
# ps5_exclude_keywords = [
#     "digital", "digital edition", "digital version",
#     "без дисковода", "без привода", "бездисковый", "бездисковая",
#     "без диска", "цифровая", "цифровой", "цифровое", "цифровой версии"
# ]

# iphone_exclude_keywords_16pro = [
#         "восстановленный", "ремоторизованный", "подержанный", "refurbished", "б/у", "used", "подержанная", "восстановленная", "отремонтированная", "обменная",
#         "восстановлен", "отремонтированный", "восстанавливать", "перепаковка", "asis", "ASIS", "обменка", "обменный",
# ]

# def get_products_by_sort(query):
#     """Получаем товары с разными сортировками"""
#     products = []
#     product_ids = set()
#     max_count = 3
#     count = 0
#     for page in range(1, 100):
#         try:
#             url = f"https://search.wb.ru/exactmatch/ru/common/v18/search?ab_testid=no_action&ab_testing=false&appType=1&curr=rub&dest=123589415&hide_dtype=11&inheritFilters=false&lang=ru&page={page}&query={query}&resultset=catalog&sort=priceup&spp=30&suppressSpellcheck=false&uclusters=0"
           
#             response = requests.get(url, headers=HEADERS, timeout=5)
#             data = response.json()
#             length = len(products)
#             for product in data["products"]:
#                 if product["id"] not in product_ids:
#                     product_ids.add(product["id"])
#                     products.append(product)

#             if length == len(products):
#                 count += 1
#                 if count == max_count:
#                   count = 0
#                   break
#         except Exception as e:
#             break
    
#     return products

# all_products = []
# product_ids = set()
# search_querys = ["playstation 5 pro"]
# for search_query in search_querys:
#     print(f"\n=== Поиск: '{search_query}' ===")
    
#     products = get_products_by_sort(search_query)

#     new_count = 0
#     for product in products:
#         if product["id"] not in product_ids:
#             product_ids.add(product["id"])
#             all_products.append(product)
#             new_count += 1
    
#     print(f"Добавлено: {new_count}, всего: {len(all_products)}")


# print(len(all_products))

# print(f"\n=== ФИНАЛЬНЫЙ РЕЗУЛЬТАТ ===")
# print(f"Итого собрано товаров: {len(all_products)}")

# def should_exclude_product(id, name, product_type):
#     """
#     Проверяет, нужно ли исключить товар по названию
    
#     Args:
#         name (str): Название товара
#         product_type (str): Тип товара - "iphone" или "ps5"
    
#     Returns:
#         bool: True если товар нужно исключить, False если оставить
#     """
    
   
#     exclude_keywords = iphone_exclude_keywords_16pro
    
#     for keyword in exclude_keywords:
#         if keyword in name:
#             if id == 567722907:
#               print(keyword)
#             return True
    
#     return False



# links = []
# max_price = 73000
# for i in range(len(all_products)):
#     id = int(all_products[i]['id'])
#     name = str(all_products[i]["name"])
#     product_price = int(all_products[i]['sizes'][0]['price']['product'])/100 * 0.93 

#     if id == 561004856:
#         print(name.lower())
#     if  should_exclude_product(id, name.lower(), "iphone"):
#         continue
    
#     if product_price < max_price + 2000 and product_price > max_price - 10000:
#         # # Доп проверка цены 
#         req = requests.get(f"https://u-card.wb.ru/cards/v4/list?appType=1&curr=rub&dest=-1586361&spp=30&hide_dtype=11&ab_testing=false&ab_testing=false&lang=ru&nm={all_products[i]['id']}&ignore_stocks=true", headers=HEADERS_)
#         try:
#             req_data = req.json()
#             product_price = int(req_data['products'][0]['sizes'][0]['price']['product'])/100 * 0.93
#             #print(product_price)
#         except:
#             continue

#         if product_price < max_price and product_price > max_price/2:
#             links.append([f"https://www.wildberries.ru/catalog/{all_products[i]['id']}/detail.aspx", product_price])

# # Сортировка массива links по возрастанию цены (второй элемент в каждом подмассиве)
# links.sort(key=lambda x: x[1])

# for i in range(len(links)):
#     print(links[i])
# reqq = requests.get("https://u-card.wb.ru/cards/v4/list?appType=1&curr=rub&dest=-1586361&spp=30&hide_dtype=11&ab_testing=false&ab_testing=false&lang=ru&nm=543722329&ignore_stocks=true", headers=HEADERS)

# print(reqq.json())
#!/usr/bin/env python3
# import time
# import random
# import uuid
# import json
# import hashlib
# import base64
# from curl_cffi import requests as curl_requests

# # ---------------- Настройки по умолчанию ----------------
# QUERY = "iphone 16 pro 256"
# PAGES = 10
# MAX_PRICE = 1000000
# DEST = "123589415"
# SORT = "popular"
# SPP = "30"
# COOKIES = None  # если есть cookies из браузера, вставь строку
# DELAY_RANGE = (1.2, 2.5)
# URL = "https://u-search.wb.ru/exactmatch/ru/common/v18/search"
# # --------------------------------------------------------

# class PowManager:
#     def __init__(self):
#         self.current_pow = None
#         self.site_id = "site_ea8e2dfce53c4193a14c05d5b4be5f7e"  # из твоего примера
    
#     def solve_pow_challenge(self, challenge_str):
#         """Простая заглушка для решения PoW challenge"""
#         print(f"Получен challenge: {challenge_str}")
        
#         # Парсим challenge
#         parts = challenge_str.split(',')
#         if len(parts) < 8:
#             return None
            
#         algorithm = parts[0]  # 6 = алгоритм
#         complexity = parts[1]  # 8 = сложность
#         prefix_len = parts[2]  # 1 = длина префикса
#         prefix = parts[3]      # hex префикс
#         uuid1 = parts[4]       # UUID
#         uuid2 = parts[5]       # UUID
#         timestamp = parts[6]   # timestamp
#         salt = parts[7]        # соль
        
#         # Здесь должна быть реальная логика решения PoW
#         # Пока возвращаем заглушку
#         solution = "0" * 64  # заглушка
        
#         # Формируем ответ
#         solved_pow = f"2|{self.site_id}|{timestamp}|{challenge_str},{solution}|{complexity}"
#         return solved_pow
    
#     def update_pow(self, headers):
#         """Обновляем x-pow из заголовков ответа"""
#         if 'x-pow' in headers:
#             pow_header = headers['x-pow']
#             print(f"Получен x-pow: {pow_header[:100]}...")
            
#             if 'status=invalid' in pow_header and 'challenge=' in pow_header:
#                 # Извлекаем challenge
#                 challenge_part = pow_header.split('challenge=')[1]
#                 # Решаем challenge
#                 solved_pow = self.solve_pow_challenge(challenge_part)
#                 if solved_pow:
#                     self.current_pow = solved_pow
#                     print(f"Сгенерирован новый x-pow: {solved_pow[:80]}...")
#                 else:
#                     print("Не удалось решить PoW challenge")
#             elif 'status=ok' in pow_header:
#                 print("PoW статус: OK")
#                 self.current_pow = None

# def random_user_agent():
#     ver = random.randint(120, 141)
#     return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ver}.0.0.0 Safari/537.36"

# def build_headers(pow_manager):
#     headers = {
#         "Accept": "*/*",
#         "Accept-Encoding": "gzip, deflate, br, zstd",
#         "Accept-Language": "ru,en;q=0.9",
#         "Origin": "https://www.wildberries.ru",
#         "Referer": f"https://www.wildberries.ru/catalog/0/search.aspx?sort={SORT}&search={QUERY.replace(' ', '+')}",
#         "User-Agent": random_user_agent(),
#         "x-queryid": f"qid{uuid.uuid4().hex}{random.randint(1000,9999)}",
#         "x-userid": "0",
#     }
#     if COOKIES:
#         headers["Cookie"] = COOKIES
    
#     # Добавляем актуальный x-pow если есть
#     if pow_manager.current_pow:
#         headers["x-pow"] = pow_manager.current_pow
#         print(f"Отправляем x-pow в запросе")
    
#     return headers

# def make_params(page):
#     return {
#         "ab_testing": "false",
#         "appType": "1",
#         "curr": "rub",
#         "dest": DEST,
#         "hide_dtype": "11",
#         "inheritFilters": "false",
#         "lang": "ru",
#         "page": str(page),
#         "query": QUERY,
#         "resultset": "catalog",
#         "sort": SORT,
#         "spp": SPP,
#         "suppressSpellcheck": "false",
#     }

# def parse_products(resp_json):
#     if not isinstance(resp_json, dict):
#         return []
#     data = resp_json.get("products")
#     if not data:
#         return []
#     return data or []

# def extract_item(p):
#     try:
#         price = p["sizes"][0]["price"]["total"] / 100
#     except:
#         price = None
#     return {
#         "id": p.get("id"),
#         "title": p.get("name"),
#         "price": price,
#         "rating": p.get("reviewRating"),
#         "reviews": p.get("feedbacks"),
#         "url": f"https://www.wildberries.ru/catalog/{p.get('id')}/detail.aspx"
#     }

# def print_response_headers(resp, page):
#     """Выводим заголовки ответа для анализа"""
#     print(f"\n[стр. {page}] Заголовки ответа:")
#     print("-" * 50)
#     for header, value in resp.headers.items():
#         if header.lower() == 'x-pow':
#             # Обрезаем длинный x-pow для читаемости
#             if len(value) > 100:
#                 print(f"{header}: {value[:100]}...")
#             else:
#                 print(f"{header}: {value}")
#         else:
#             print(f"{header}: {value}")
#     print("-" * 50)

# def collect():
#     unique = {}
#     last_count = 0
#     no_new_pages = 0
#     pow_manager = PowManager()

#     for page in range(1, PAGES + 1):
#         headers = build_headers(pow_manager)
#         params = make_params(page)

#         try:
#             resp = curl_requests.get(URL, params=params, headers=headers, timeout=15)
#         except Exception as e:
#             print(f"[стр. {page}] Ошибка запроса: {e}")
#             break

#         print(f"\n[стр. {page}] Статус: {resp.status_code}")
        
#         # Обновляем PoW из заголовков ответа
#         pow_manager.update_pow(resp.headers)
        
#         # Выводим заголовки ответа для анализа
#         print_response_headers(resp, page)
        
#         print("Snippet ответа:", resp.text[:300], "\n")

#         if resp.status_code != 200:
#             print(f"[стр. {page}] Статус {resp.status_code}, останавливаемся.")
#             break

#         try:
#             resp_json = resp.json()
#         except Exception:
#             print(f"[стр. {page}] Не удалось распарсить JSON")
#             break

#         products = parse_products(resp_json)
#         if not products:
#             print(f"[стр. {page}] Пустая выдача.")
#             break

#         added = 0
#         for p in products:
#             item = extract_item(p)
#             if item["price"] is not None and item["price"] * 0.93 > MAX_PRICE:
#                 continue
#             if item["id"] not in unique:
#                 unique[item["id"]] = item
#                 added += 1

#         total = len(unique)
#         print(f"[стр. {page}] Добавлено {added} новых товаров, всего {total}")

#         if total == last_count:
#             no_new_pages += 1
#         else:
#             no_new_pages = 0
#             last_count = total

#         if no_new_pages >= 3:
#             print("Новых товаров не появлялось 3 страницы подряд — выходим.")
#             break

#         time.sleep(random.uniform(*DELAY_RANGE))

#     return list(unique.values())

# if __name__ == "__main__":
#     print(f"Запускаем парсинг для запроса: '{QUERY}'\n")
#     results = collect()
#     print(f"\nВсего найдено товаров: {len(results)}")
#     if results:
#         filename = f"wb_{QUERY.replace(' ', '_')}.json"
#         with open(filename, "w", encoding="utf-8") as f:
#             json.dump(results, f, ensure_ascii=False, indent=2)
#         print(f"Сохранено в файл: {filename}")


# import time
# import random
# import uuid
# import json
# import hashlib
# import struct
# import os
# from curl_cffi import requests as curl_requests

# # ---------------- Настройки по умолчанию ----------------
# QUERY = "iphone 16 pro 256"
# PAGES = 10
# MAX_PRICE = 1000000
# DEST = "123589415"
# SORT = "popular"
# SPP = "30"
# COOKIES = None
# DELAY_RANGE = (1.2, 2.5)
# URL = "https://u-search.wb.ru/exactmatch/ru/common/v18/search"
# # --------------------------------------------------------

# class PowManager:
#     def __init__(self):
#         self.current_pow = None
#         self.site_id = "site_ea8e2dfce53c4193a14c05d5b4be5f7e"
    
#     def solve_pow_challenge(self, challenge_str):
#         """Решаем PoW challenge методом перебора"""
#         print(f"Решение PoW challenge...")
        
#         try:
#             parts = challenge_str.split(',')
#             if len(parts) < 9:
#                 print("Неверный формат challenge")
#                 return None
                
#             algorithm = int(parts[0])  # 6 = SHA256
#             complexity = int(parts[1])  # 8 = количество нулей
#             prefix_len = int(parts[2])  # 1 = длина префикса
#             prefix_hex = parts[3]       # hex префикс
#             uuid1 = parts[4]            # UUID
#             uuid2 = parts[5]            # UUID  
#             timestamp = parts[6]        # timestamp
#             salt = parts[7]             # соль
#             signature = parts[8]        # подпись
            
#             print(f"Алгоритм: {algorithm}, Сложность: {complexity}")
#             print(f"Префикс: {prefix_hex}, Timestamp: {timestamp}")
            
#             # Конвертируем префикс из hex в bytes (little endian)
#             prefix_bytes = bytes.fromhex(prefix_hex)
            
#             # Ищем решение
#             solution = self.find_pow_solution(prefix_bytes, complexity)
            
#             if solution:
#                 # Формируем полный x-pow токен
#                 solved_pow = f"2|{self.site_id}|{timestamp}|{challenge_str},{solution}|{complexity}"
#                 print(f"✅ PoW решен! Solution: {solution[:20]}...")
#                 return solved_pow
#             else:
#                 print("❌ Не удалось найти решение PoW")
#                 return None
                
#         except Exception as e:
#             print(f"Ошибка решения PoW: {e}")
#             return None
    
#     def find_pow_solution(self, prefix, difficulty):
#         """Находим решение PoW перебором nonce"""
#         target = "0" * difficulty
#         start_time = time.time()
        
#         print(f"Поиск решения... Target: {target}")
        
#         # Пробуем разные nonce
#         for nonce_int in range(0, 100000000):  # 100M попыток
#             # Конвертируем nonce в bytes (little endian, 8 bytes)
#             nonce_bytes = struct.pack('<Q', nonce_int)
            
#             # Данные для хэширования: prefix + nonce
#             data_to_hash = prefix + nonce_bytes
            
#             # Вычисляем SHA256
#             hash_result = hashlib.sha256(data_to_hash).hexdigest()
            
#             # Проверяем соответствие сложности
#             if hash_result.startswith(target):
#                 elapsed = time.time() - start_time
#                 print(f"✅ Решение найдено за {elapsed:.2f} сек, попыток: {nonce_int}")
#                 return hash_result
            
#             # Прогресс каждые 1M попыток
#             if nonce_int % 1000000 == 0 and nonce_int > 0:
#                 elapsed = time.time() - start_time
#                 print(f"Попыток: {nonce_int}, время: {elapsed:.1f} сек")
                
#         return None

#     def update_pow(self, headers):
#         """Обновляем x-pow из заголовков ответа"""
#         if 'x-pow' in headers:
#             pow_header = headers['x-pow']
            
#             if 'status=invalid' in pow_header and 'challenge=' in pow_header:
#                 print("🔄 Получен invalid PoW, решаем challenge...")
#                 # Извлекаем challenge
#                 if ';' in pow_header:
#                     challenge_part = pow_header.split('challenge=')[1].split(';')[0]
#                 else:
#                     challenge_part = pow_header.split('challenge=')[1]
                
#                 # Решаем challenge
#                 solved_pow = self.solve_pow_challenge(challenge_part)
#                 if solved_pow:
#                     self.current_pow = solved_pow
#                     print("✅ Новый x-pow сгенерирован")
#                 else:
#                     print("❌ Не удалось решить PoW")
#                     self.current_pow = None
#             elif 'status=ok' in pow_header:
#                 print("✅ PoW статус: OK")
#                 self.current_pow = None

# def random_user_agent():
#     ver = random.randint(120, 141)
#     return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ver}.0.0.0 Safari/537.36"

# def build_headers(pow_manager):
#     headers = {
#         "Accept": "*/*",
#         "Accept-Encoding": "gzip, deflate, br, zstd",
#         "Accept-Language": "ru,en;q=0.9",
#         "Origin": "https://www.wildberries.ru",
#         "Referer": f"https://www.wildberries.ru/catalog/0/search.aspx?sort={SORT}&search={QUERY.replace(' ', '+')}",
#         "User-Agent": random_user_agent(),
#         "x-queryid": f"qid{uuid.uuid4().hex}{random.randint(1000,9999)}",
#         "x-userid": "0",
#     }
#     if COOKIES:
#         headers["Cookie"] = COOKIES
    
#     if pow_manager.current_pow:
#         headers["x-pow"] = pow_manager.current_pow
#         print(f"📤 Отправляем x-pow в запросе")
    
#     return headers

# def make_params(page):
#     return {
#         "ab_testing": "false",
#         "appType": "1",
#         "curr": "rub",
#         "dest": DEST,
#         "hide_dtype": "11",
#         "inheritFilters": "false",
#         "lang": "ru",
#         "page": str(page),
#         "query": QUERY,
#         "resultset": "catalog",
#         "sort": SORT,
#         "spp": SPP,
#         "suppressSpellcheck": "false",
#     }

# def parse_products(resp_json):
#     if not isinstance(resp_json, dict):
#         return []
#     data = resp_json.get("products")
#     if not data:
#         return []
#     return data or []

# def extract_item(p):
#     try:
#         price = p["sizes"][0]["price"]["total"] / 100
#     except:
#         price = None
#     return {
#         "id": p.get("id"),
#         "title": p.get("name"),
#         "price": price,
#         "rating": p.get("reviewRating"),
#         "reviews": p.get("feedbacks"),
#         "url": f"https://www.wildberries.ru/catalog/{p.get('id')}/detail.aspx"
#     }

# def print_response_headers(resp, page):
#     """Выводим заголовки ответа для анализа"""
#     print(f"\n[стр. {page}] Заголовки ответа:")
#     print("-" * 50)
#     for header, value in resp.headers.items():
#         if header.lower() == 'x-pow':
#             if len(value) > 100:
#                 print(f"{header}: {value[:100]}...")
#             else:
#                 print(f"{header}: {value}")
#         else:
#             print(f"{header}: {value}")
#     print("-" * 50)

# def collect():
#     unique = {}
#     last_count = 0
#     no_new_pages = 0
#     pow_manager = PowManager()

#     for page in range(1, PAGES + 1):
#         headers = build_headers(pow_manager)
#         params = make_params(page)

#         try:
#             print(f"\n📄 [стр. {page}] Отправляем запрос...")
#             resp = curl_requests.get(URL, params=params, headers=headers, timeout=30)
#         except Exception as e:
#             print(f"❌ [стр. {page}] Ошибка запроса: {e}")
#             break

#         print(f"📊 [стр. {page}] Статус: {resp.status_code}")
        
#         # Обновляем PoW из заголовков ответа
#         pow_manager.update_pow(resp.headers)
        
#         # Выводим заголовки ответа для анализа
#         print_response_headers(resp, page)
        
#         if resp.status_code != 200:
#             print(f"❌ [стр. {page}] Статус {resp.status_code}, останавливаемся.")
#             break

#         try:
#             resp_json = resp.json()
#         except Exception:
#             print(f"❌ [стр. {page}] Не удалось распарсить JSON")
#             break

#         products = parse_products(resp_json)
#         if not products:
#             print(f"⚠️ [стр. {page}] Пустая выдача.")
#             break

#         added = 0
#         for p in products:
#             item = extract_item(p)
#             if item["price"] is not None and item["price"] * 0.93 > MAX_PRICE:
#                 continue
#             if item["id"] not in unique:
#                 unique[item["id"]] = item
#                 added += 1

#         total = len(unique)
#         print(f"✅ [стр. {page}] Добавлено {added} новых товаров, всего {total}")

#         if total == last_count:
#             no_new_pages += 1
#             print(f"⚠️ Предупреждение: одинаковые товары ({no_new_pages}/3)")
#         else:
#             no_new_pages = 0
#             last_count = total

#         if no_new_pages >= 3:
#             print("🛑 Новых товаров не появлялось 3 страницы подряд — выходим.")
#             break

#         delay = random.uniform(*DELAY_RANGE)
#         print(f"⏳ Ждем {delay:.1f} сек...")
#         time.sleep(delay)

#     return list(unique.values())

# if __name__ == "__main__":
#     print(f"🚀 Запускаем парсинг для запроса: '{QUERY}'\n")
#     results = collect()
#     print(f"\n📊 Всего найдено товаров: {len(results)}")
#     if results:
#         filename = f"wb_{QUERY.replace(' ', '_')}.json"
#         with open(filename, "w", encoding="utf-8") as f:
#             json.dump(results, f, ensure_ascii=False, indent=2)
#         print(f"💾 Сохранено в файл: {filename}")

import requests
import json
import math

def calc_discounted_price(base_price: int | None, discount_percent: int) -> int | None:
    if base_price is None:
        return None
    return math.floor(base_price * (100 - int(discount_percent)) / 100)

def simple_wb_search(query, include_words=None, exclude_words=None):
    """
    Простой синхронный поиск товаров на WB
    """
    if include_words is None:
        include_words = []
    if exclude_words is None:
        exclude_words = []
    
    # Формируем URL
    url = "https://search.wb.ru/exactmatch/ru/common/v18/search?ab_testid=promo_mask_transp_r&appType=1&curr=rub&dest=-1255987&hide_dtype=9%3B11&hide_vflags=4294967296&inheritFilters=false&lang=ru&query=iphone+17&resultset=catalog&sort=popular&sort=priceup&&spp=30&suppressSpellcheck=false&uclusters=0"
    
    headers = {
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
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0",
        "authorization" : "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3Njc2MzI5MjUsInVzZXIiOiI1NDU4NDA2MiIsInNoYXJkX2tleSI6IjYiLCJjbGllbnRfaWQiOiJ3YiIsInNlc3Npb25faWQiOiJmMmE3NWRjMThjODU0YTNkOGIxNDdlMTY4Mzc0NmJiZSIsInZhbGlkYXRpb25fa2V5IjoiMDJjYWY3OTU4Y2RiNTU5MjRiMTc3MzQ3MGZmOWIxNjliN2JjMzcxZmMxMmMzYTA5OTg4M2Y5OGU4NjMwZTVhNyIsInBob25lIjoiSmI5N1U0UTdYa1pBT1I4SWMrUFVkZz09IiwidXNlcl9yZWdpc3RyYXRpb25fZHQiOjE2OTUwNDgzMzksInZlcnNpb24iOjJ9.T6nkWSC7XyRuhvcMajMTxXk2SitYQg8OnO-4uepAWaTYEnw5U8KwQgQxP-yI9DrES7BI1Kt0T0pRmYNlH2Is5p2tNpUQ7de4QPRsUH9X674hbKXuofb2SZBYN5VaPy57gBvSUyyMJrNbbhGQejZg4-m9CI8Jn8PNcEUSNlMSymsTYrrVY1jRdymbTuMb5_qri7kWnhEmy02hDPrQN6XcBYKGwCuk5_bIwPWTC3Po1v3Cs0u65NMQzb1T6SO-Ji0TTzFs4x_nfr75q3lOZJEry-5iqMzlcB4NdA6wIBmyegfHFeeSJ4ZZikJkqqI93jJJ0jRooimk8-FMUnR5Pl0jcQ"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        products = data.get("products", [])

        
        
        print(f"🔍 Поиск: '{query}'")
        print(f"📦 Найдено товаров: {len(products)}")
        
        results = []
        
        for product in products:
            name = product.get("name", "")

            price = calc_discounted_price(math.floor(product["sizes"][0]["price"]["product"]) / 100, 6)
            product_id = product.get("id")
            print(math.floor(product["sizes"][0]["price"]["product"]) / 100)
            # Фильтрация
            name_lower = name.lower()
            
            # Проверка include слов
            if include_words:
                if any(word.lower() not in name_lower for word in include_words):
                    continue
            
            # Проверка exclude слов
            if exclude_words:
                if any(word.lower() in name_lower for word in exclude_words):
                    continue
            
            results.append({
                "name": name,
                "price": price,
                "id": product_id
            })
        
        # Выводим результаты
        print(f"✅ После фильтрации: {len(results)} товаров\n")
        
        for i, item in enumerate(results[:15], 1):  # Показываем первые 15
            print(f"{i:2d}. {item['name']}...")  # Обрезаем длинные названия
            print(f"    💰 Цена: {item['price']} руб. | ID: {item['id']}")
            print()
        
        return results
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

# Примеры использования
if __name__ == "__main__":
    # Пример 1
    # print("="*60)
    simple_wb_search("iphone 17")

  

    url = "https://u-card.wb.ru/cards/v4/list?appType=1&curr=rub&dest=-1586348&spp=30&hide_dtype=11&ab_testing=false&lang=ru&nm=739804962&ignore_stocks=true"
    response = requests.get(url=url)
    print(response.json())
    