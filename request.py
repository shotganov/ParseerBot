# import requests

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


import requests

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

# Инициализация базы данных
db = Database()


def get_products_by_sort(query):
    """Получаем товары с разными сортировками"""
    products = []
    product_ids = set()
    
    for page in range(1, 10):
        try:
            url = f"https://search.wb.ru/exactmatch/ru/common/v18/search?ab_testid=reranking_price_6&ab_testing=false&appType=1&curr=rub&dest=-1586348&hide_dtype=11&inheritFilters=false&lang=ru&page={page}&query={query}&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false&uclusters=3"
           
            response = requests.get(url)
            data = response.json()
            
            for product in data["products"]:
                if product["id"] not in product_ids:
                    product_ids.add(product["id"])
                    products.append(product)
            
            if len(data["products"]) < 100:
                break
                
        except Exception as e:
            break
    
    return products

# Разные варианты поискового запроса
search_queries1 = [
    "playstation 5 slim",
    "playstation 5 slim с дисководом",
    "playstation 5",
    "игровая консоль playstation 5",
]

search_queries = [
    # Основные запросы
    "iPhone 15",
    "iPhone 15 128gb",
    "iPhone 15 256gb", 
    "iPhone 15 512gb",
    
    # С типом SIM
    "iPhone 15 sim + esim",
    "iPhone 15 dual sim",
    "iPhone 15 две сим",
    
    # С цветами
    "iPhone 15 черный",
    "iPhone 15 белый",
    "iPhone 15 синий",
    "iPhone 15 розовый",
    "iPhone 15 зеленый",
    "iPhone 15 желтый",
    "iPhone 15 purple",
    "iPhone 15 black", 
    "iPhone 15 white",
    "iPhone 15 blue",
    "iPhone 15 pink",
    "iPhone 15 green",
    "iPhone 15 yellow",
    "Смартфон iPhone 15"
]

# Список для исключения ненужных iPhone (в нижнем регистре)
iphone_exclude_keywords = [
    "16", "14", "13", "11", "iphone 16", "iphone 14", "iphone 13", "iphone 12", "iphone 11", "iphone xr", "iphone xs", "iphone x", "iphone 8", "iphone 7", "iphone 6",
    "16e", "16 e", "16 plus", "16 plus",
    "восстановленный", "ремоторизованный", "refurbished", "б/у", "used",
    "восстановлен", "отремонтированный", "восстанавливать"
]

# Список для исключения PS5 без дисковода (в нижнем регистре)
ps5_exclude_keywords = [
    "digital", "digital edition", "digital version",
    "без дисковода", "без привода", "бездисковый", "бездисковая",
    "без диска", "цифровая", "цифровой", "цифровое", "цифровой версии"
]

all_products = []
product_ids = set()

for search_query in search_queries:
    print(f"\n=== Поиск: '{search_query}' ===")
    
    products = get_products_by_sort(search_query)
    
    # Добавляем только новые товары
    new_count = 0
    for product in products:
        if product["id"] not in product_ids:
            product_ids.add(product["id"])
            all_products.append(product)
            new_count += 1
    
    print(f"Добавлено: {new_count}, всего: {len(all_products)}")

print(f"\n=== ФИНАЛЬНЫЙ РЕЗУЛЬТАТ ===")
print(f"Итого собрано товаров: {len(all_products)}")

def should_exclude_product(name, product_type):
    """
    Проверяет, нужно ли исключить товар по названию
    
    Args:
        name (str): Название товара
        product_type (str): Тип товара - "iphone" или "ps5"
    
    Returns:
        bool: True если товар нужно исключить, False если оставить
    """
    
    if product_type == "ps5":
        exclude_keywords = ps5_exclude_keywords
    else:  # iphone
        exclude_keywords = iphone_exclude_keywords
    
    for keyword in exclude_keywords:
        if keyword in name:
            return True
    
    return False

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

links = []
max_price = 45000
for i in range(len(all_products)):
  name = str(all_products[i]["name"])
  product_price = int(all_products[i]['sizes'][0]['price']['product'])/100 * 0.93 
  if should_exclude_product(name.lower(), "iphone"):
    continue
  
  if 524901651 == all_products[i]["id"]:
     print(all_products[i])
  if product_price < max_price + 2000 and product_price > max_price - 10000:
    # Доп проверка цены 

    req = requests.get(f"https://u-card.wb.ru/cards/v4/list?appType=1&curr=rub&dest=-1586361&spp=30&hide_dtype=11&ab_testing=false&ab_testing=false&lang=ru&nm={all_products[i]['id']}&ignore_stocks=true", headers=HEADERS)
    req_data = req.json()
    try:
      product_price = int(req_data['products'][0]['sizes'][0]['price']['product'])/100 * 0.93
      #print(product_price)
    except:
      continue

    if product_price < max_price and product_price > max_price/2:
      links.append([f"https://www.wildberries.ru/catalog/{all_products[i]["id"]}/detail.aspx", product_price])

for i in range(len(links)):
  print(links[i])