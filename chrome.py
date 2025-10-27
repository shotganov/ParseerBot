from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import re

def setup_driver():
    """Настройка Chrome драйвера"""
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def parse_wb_product_price(driver, url):
    """Парсинг цены товара с страницы Wildberries"""
    try:
        driver.get(url)
        
        # Ждем загрузки страницы
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Несколько стратегий для поиска цены
        price_selectors = [
            "//*[@data-tag='salePrice']",
            "//*[contains(@class, 'price-block')]//*[contains(@class, 'price')]",
            "//*[contains(@class, 'final-price')]",
            "//ins[contains(@class, 'price')]",
            "//*[contains(@class, 'j-final-price')]"
        ]
        
        price = None
        
        for selector in price_selectors:
            try:
                price_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                price_text = price_element.text.strip()
                
                # Извлекаем числа из текста (убираем символы валюты, пробелы и т.д.)
                price_match = re.search(r'(\d+[\s\d]*)', price_text.replace(' ', ''))
                if price_match:
                    price = int(price_match.group(1).replace(' ', ''))
                    break
                    
            except:
                continue
        
        # Если не нашли через XPath, попробуем через CSS селекторы
        if price is None:
            css_selectors = [
                ".price-block__final-price",
                ".final-price",
                "[data-tag='salePrice']",
                ".j-final-price"
            ]
            
            for css_selector in css_selectors:
                try:
                    price_element = driver.find_element(By.CSS_SELECTOR, css_selector)
                    price_text = price_element.text.strip()
                    price_match = re.search(r'(\d+[\s\d]*)', price_text.replace(' ', ''))
                    if price_match:
                        price = int(price_match.group(1).replace(' ', ''))
                        break
                except:
                    continue
        
        return price
        
    except Exception as e:
        print(f"Ошибка при парсинге {url}: {e}")
        return None

def parse_multiple_products(urls):
    """Парсинг цен для нескольких товаров"""
    driver = setup_driver()
    results = []
    
    try:
        for url in urls:
            print(f"Парсим: {url}")
            price = parse_wb_product_price(driver, url)
            
            if price:
                results.append({
                    'url': url,
                    'price': price,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                })
                print(f"Цена: {price} руб.")
            else:
                results.append({
                    'url': url,
                    'price': None,
                    'error': 'Цена не найдена',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                })
                print("Цена не найдена")
            
            print("-" * 50)
            time.sleep(2)  # Пауза между запросами
            
        return results
        
    finally:
        driver.quit()

# Пример использования
if __name__ == "__main__":
    # Список URL для парсинга
    product_urls = [
        "https://www.wildberries.ru/catalog/0/search.aspx?page=1&sort=priceup&search=iphone+16+pro+256",
    ]
    
    # Парсинг цен
    prices_data = parse_multiple_products(product_urls)
    
    # Вывод результатов
    print("\nРезультаты парсинга:")
    for item in prices_data:
        if item['price']:
            print(f"{item['url']} - {item['price']} руб.")
        else:
            print(f"{item['url']} - Ошибка: {item.get('error', 'Неизвестная ошибка')}")
    
    # Сортировка по цене (по возрастанию)
    sorted_results = sorted([item for item in prices_data if item['price']], 
                           key=lambda x: x['price'])
    
    print("\nОтсортировано по цене (возрастание):")
    for item in sorted_results:
        print(f"{item['price']} руб. - {item['url']}")