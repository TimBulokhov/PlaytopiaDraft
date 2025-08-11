import requests
from bs4 import BeautifulSoup
import json
import re
import time

TIERS = [
    {"name": "Essential", "tierId": "TIER_10", "image": "essential.png"},
    {"name": "Extra", "tierId": "TIER_20", "image": "extra.png"},
    {"name": "Deluxe", "tierId": "TIER_30", "image": "deluxe.png"},
]
TIERID_TO_NAME = {t["tierId"]: t["name"] for t in TIERS}
TIERID_TO_IMAGE = {t["tierId"]: t["image"] for t in TIERS}

REGIONS = [
    {"name": "TR", "url": "https://www.playstation.com/en-tr/ps-plus/?smcid=store%3Aen-tr%3Apages-latest%3Aprimary%20nav%3Amsg-store%3Asubscribe-to-ps-plus#subscriptions"},
    {"name": "IN", "url": "https://www.playstation.com/en-in/ps-plus/?smcid=store%3Aen-tr%3Apages-latest%3Aprimary%20nav%3Amsg-store%3Asubscribe-to-ps-plus#subscriptions"},
]

# Форматирование цен
def format_price(price, region):
    if not price:
        return price
    price = price.replace("\xa0", " ").replace("&nbsp;", " ")
    price = re.sub(r'\s+', ' ', price)
    
    if region == "TR":
        # Заменяем ₺/ay на TL
        price = price.replace("₺/ay", " TL").replace("₺/üç ay", " TL")
        price = price.replace("TL", " TL").replace(" TL", " TL")
        price = re.sub(r'\s+TL', ' TL', price)
        # Заменяем TRY на TL
        price = price.replace("TRY", "TL")
        
    elif region == "IN":
        # Заменяем ₹ на Rs и обрезаем /month
        price = price.replace("₹", "Rs")
        price = re.sub(r'/month.*$', '', price)  # Убираем /month и все после
        price = price.replace("Rs ", "Rs ").replace("Rs", "Rs ")
        price = re.sub(r'Rs\s*([0-9])', r'Rs \1', price)
        # Убираем дробную часть
        price = re.sub(r'Rs\s*(\d+)\.\d+', r'Rs \1', price)
    
    return price.strip()

def period_ru(months):
    if months == 1:
        return "1 месяц"
    elif months == 3:
        return "3 месяца"
    elif months == 12:
        return "12 месяцев"
    else:
        return f"{months} месяцев"

def translate_discount(discount_text):
    """Переводит текст скидки с английского на русский"""
    if not discount_text:
        return discount_text
    
    # Оставляем "-n%" формат как есть
    if discount_text.startswith('-') and '%' in discount_text:
        return discount_text
    
    # Заменяем "Save n%" на "Скидка n%"
    if discount_text.startswith('Save '):
        # Сначала проверяем "Save n% more" (более специфичный паттерн)
        match = re.search(r'Save (\d+)% more', discount_text)
        if match:
            percent = match.group(1)
            return f"Скидка +{percent}%"
        
        # Затем проверяем обычный "Save n%"
        match = re.search(r'Save (\d+)%', discount_text)
        if match:
            percent = match.group(1)
            return f"Скидка {percent}%"
    
    # Возвращаем как есть для всех остальных случаев
    return discount_text

def format_xbox_price(price_raw, region_name):
    """Форматирует цену для Xbox подписок с правильным добавлением ,00 и точками для тысяч"""
    if not price_raw:
        return None
    
    # Форматируем базовую цену
    price = format_price(f"{price_raw} TRY", region_name)
    
    # Если это целое число - добавляем ,00 и форматируем тысячи
    if price_raw.isdigit():
        # Добавляем точки для тысяч
        num = int(price_raw)
        if num >= 1000:
            formatted_num = f"{num:,}".replace(",", ".")
        else:
            formatted_num = str(num)
        price = f"{formatted_num},00 TL"
    # Если это дробное число - форматируем правильно
    elif '.' in price_raw:
        num = float(price_raw)
        if num >= 1000:
            # Форматируем тысячи с точками и дробную часть с запятой
            formatted_num = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            # Просто заменяем точку на запятую
            formatted_num = price_raw.replace(".", ",")
        price = f"{formatted_num} TL"
    
    return price

# PlayStation Plus
def parse_psplus():
    results = []
    for region in REGIONS:
        print(f"Парсим регион: {region['name']}")
        try:
            resp = requests.get(region['url'], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        soup = BeautifulSoup(resp.text, 'html.parser')
        subs_blocks = soup.find_all('div', class_='tier-selector__subscription')
        for block in subs_blocks:
            script = block.find('script', {'type': 'application/json'})
            tierId = None
            offers = []
            if script:
                try:
                    data = json.loads(script.text)
                    tierId = data.get('args', {}).get('tierId')
                    cache = data.get('cache', {})
                    root = cache.get('ROOT_QUERY', {})
                    key = f'tierSelectorOffersRetrieve({{"tierLabel":"{tierId}"}})'
                    offers = root.get(key, {}).get('offers', [])
                except Exception as e:
                    print(f"Ошибка парсинга JSON в блоке подписки: {e}")
            if not tierId or tierId not in TIERID_TO_NAME:
                continue
            tier_name = TIERID_TO_NAME[tierId]
            tier_image = TIERID_TO_IMAGE[tierId]
            plans = []
            for offer in offers:
                duration = offer.get('duration', {})
                months = duration.get('value', None)
                if not months:
                    continue
                period = period_ru(months)
                base_price = offer.get('price', {}).get('basePrice')
                discounted_price = offer.get('price', {}).get('discountedPrice')
                price_html = discounted_price or base_price
                if not price_html:
                    continue
                price = format_price(price_html, region["name"])
                
                # Only add old_price and discount_percent if they exist
                plan_data = {
                    "period": period,
                    "price": price
                }
                
                if base_price and discounted_price and base_price != discounted_price:
                    old_price = format_price(base_price, region["name"])
                    plan_data["old_price"] = old_price
                    
                    try:
                        # Extract numeric values from price strings
                        base_num = float(re.sub(r'[^\d.,]', '', base_price).replace(',', '.'))
                        disc_num = float(re.sub(r'[^\d.,]', '', discounted_price).replace(',', '.'))
                        if base_num > 0:
                            discount_percent = f"-{int((1 - disc_num / base_num) * 100)}%"
                            plan_data["discount_percent"] = discount_percent
                    except:
                        pass
                
                plans.append(plan_data)
            results.append({
                "service": "PlayStation Plus",
                "tier": tier_name,
                "region": region["name"],
                "image": tier_image,
                "plans": plans
            })
    return results

# Ubisoft+ Classics
UBISOFT_URLS = [
    {"name": "TR", "url": "https://store.playstation.com/en-tr/product/EP0001-PPSA15773_00-UBISOFTPLUS1T01M"},
    {"name": "IN", "url": "https://store.playstation.com/en-in/product/EP0001-PPSA15773_00-UBISOFTPLUS1T01M"},
]

def parse_ubisoft_classics():
    results = []
    for region in UBISOFT_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Ищем цену и скидку
        price = None
        old_price = None
        discount_percent = None
        
        # Ищем текущую цену
        price_elem = soup.find('span', {'data-qa': 'mfeCtaMain#offer0#finalPrice'})
        if price_elem:
            price = price_elem.get_text(strip=True)
        
        # Ищем старую цену
        old_price_elem = soup.find('span', {'data-qa': 'mfeCtaMain#offer0#originalPrice'})
        if old_price_elem:
            old_price = old_price_elem.get_text(strip=True)
        
        # Ищем процент скидки
        discount_elem = soup.find('span', {'data-qa': 'mfeCtaMain#offer0#discountInfo'})
        if discount_elem:
            discount_text = discount_elem.get_text(strip=True)
            # Если это Save n%, то конвертируем в -n%
            if discount_text.startswith('Save '):
                match = re.search(r'Save (\d+)%', discount_text)
                if match:
                    percent = match.group(1)
                    discount_percent = f"-{percent}%"
                else:
                    discount_percent = discount_text
            else:
                # Применяем перевод скидки для других случаев
                discount_percent = translate_discount(discount_text)
        
        price = format_price(price, region["name"])
        old_price = format_price(old_price, region["name"]) if old_price else None
        
        plan_data = {
            "period": "1 месяц", 
            "price": price
        }
        
        if old_price and old_price != price:
            plan_data["old_price"] = old_price
        
        if discount_percent:
            plan_data["discount_percent"] = discount_percent
        
        results.append({
            "service": "Ubisoft+ Classics",
            "region": region["name"],
            "image": "ubisoft.png",
            "plans": [plan_data]
        })
    return results

# GTA+
GTA_URLS = [
    {"name": "TR", "url": "https://store.playstation.com/en-tr/product/UP1004-PPSA16755_00-GTAPLUS00001T01M"},
    {"name": "IN", "url": "https://store.playstation.com/en-in/product/UP1004-PPSA16755_00-GTAPLUS00001T01M"},
]

def parse_gtaplus():
    results = []
    for region in GTA_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Ищем цену
        price = None
        price_elem = soup.find('span', {'data-qa': 'mfeCtaMain#offer0#finalPrice'})
        if price_elem:
            price = price_elem.get_text(strip=True)
        
        # Если не нашли через data-qa, ищем по тексту
        if not price:
            for string in soup.strings:
                if re.search(r'\d+[.,\d]*\s*(TL|Rs)', string):
                    price = string.strip()
                    break
        
        price = format_price(price, region["name"])
        
        results.append({
            "service": "GTA+",
            "region": region["name"],
            "image": "gtaplus.png",
            "plans": [{
                "period": "1 месяц", 
                "price": price
            }]
        })
    return results

# EA Play
EAPLAY_URLS = [
    {"name": "TR", "url": "https://store.playstation.com/en-tr/product/EP5679-CUSA15082_00-PSEAA1M000000000"},
    {"name": "IN", "url": "https://store.playstation.com/en-in/product/EP5679-CUSA15082_00-PSEAA1M000000000"},
]

EAPLAY_12M_URLS = [
    {"name": "TR", "url": "https://store.playstation.com/en-tr/product/EP5679-CUSA15082_00-PSEAA12M00000000"},
    {"name": "IN", "url": "https://store.playstation.com/en-in/product/EP5679-CUSA15082_00-PSEAA12M00000000"},
]

def parse_eaplay():
    results = []
    
    # Парсим 1 месяц
    for region in EAPLAY_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Ищем цену
        price = None
        price_elem = soup.find('span', {'data-qa': 'mfeCtaMain#offer0#finalPrice'})
        if price_elem:
            price = price_elem.get_text(strip=True)
        
        # Если не нашли через data-qa, ищем по тексту
        if not price:
            for string in soup.strings:
                if re.search(r'\d+[.,\d]*\s*(TL|Rs)', string):
                    price = string.strip()
                    break
        
        price = format_price(price, region["name"])
        
        results.append({
            "service": "EA Play",
            "region": region["name"],
            "image": "eaplay.png",
            "plans": [{
                "period": "1 месяц", 
                "price": price
            }]
        })
    
    # Парсим 12 месяцев
    for region in EAPLAY_12M_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Ищем цену
        price = None
        price_elem = soup.find('span', {'data-qa': 'mfeCtaMain#offer0#finalPrice'})
        if price_elem:
            price = price_elem.get_text(strip=True)
        
        # Если не нашли через data-qa, ищем по тексту
        if not price:
            for string in soup.strings:
                if re.search(r'\d+[.,\d]*\s*(TL|Rs)', string):
                    price = string.strip()
                    break
        
        price = format_price(price, region["name"])
        
        # Добавляем к существующему результату или создаем новый
        existing_result = next((r for r in results if r["region"] == region["name"]), None)
        if existing_result:
            existing_result["plans"].append({
                "period": "12 месяцев", 
                "price": price
            })
        else:
            results.append({
                "service": "EA Play",
                "region": region["name"],
                "image": "eaplay.png",
                "plans": [{
                    "period": "12 месяцев", 
                    "price": price
                }]
            })
    
    return results

# Xbox Game Pass Ultimate
XBOX_ULTIMATE_URLS = [
    {"name": "TR", "url": "https://www.xbox.com/tr-tr/games/store/xbox-game-pass-ultimate/CFQ7TTC0KHS0/0007"},
]

def parse_xbox_ultimate():
    results = []
    for region in XBOX_ULTIMATE_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Ищем цену в кнопке JOIN
        price = None
        join_button = soup.find('button', {'aria-label': re.compile(r'Join Xbox Game Pass Ultimate.*per month')})
        if join_button:
            price_elem = join_button.find('span', class_='Price-module__boldText___1i2Li')
            if price_elem:
                price = price_elem.get_text(strip=True)
        
        # Если не нашли через aria-label, ищем по классам
        if not price:
            price_elem = soup.find('span', class_='Price-module__boldText___1i2Li')
            if price_elem:
                price = price_elem.get_text(strip=True)
        
        price = format_price(price, region["name"])
        
        # Получаем изображение
        image_url = get_xbox_image(soup)
        image = image_url
        
        results.append({
            "service": "Xbox Game Pass Ultimate",
            "region": region["name"],
            "image": image,
            "plans": [{
                "period": "1 месяц", 
                "price": price
            }]
        })
    return results

# Xbox Game Pass Core
XBOX_CORE_URLS = [
    {"name": "TR", "url": "https://www.xbox.com/tr-tr/games/store/xbox-game-pass-core/CFQ7TTC0K5DJ/000C"},
]

def parse_xbox_core():
    results = []
    for region in XBOX_CORE_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        soup = BeautifulSoup(resp.text, "html.parser")
        plans = []
        
        # Извлекаем цены по конкретным SKU ID
        one_month_price_raw = get_price_by_sku_id(resp.text, "000C")
        three_month_price_raw = get_price_by_sku_id(resp.text, "000D")
        
        # Создаем тарифы на основе найденных данных
        plans = []
        
        # Добавляем 1 месяц
        if one_month_price_raw:
            one_month_price = format_xbox_price(one_month_price_raw, region["name"])
            plans.append({
                "period": "1 месяц",
                "price": one_month_price
            })
        
        # Добавляем 3 месяца
        if three_month_price_raw:
            three_month_price = format_xbox_price(three_month_price_raw, region["name"])
            plans.append({
                "period": "3 месяца", 
                "price": three_month_price
            })
        
        if plans:
            # Получаем изображение
            image_url = get_xbox_image(soup)
            image = image_url
            
            results.append({
                "service": "Xbox Game Pass Core",
                "region": region["name"],
                "image": image,
                "plans": plans
            })
    
    return results

# Xbox Game Pass Standard
XBOX_STANDARD_URLS = [
    {"name": "TR", "url": "https://www.xbox.com/tr-tr/games/store/xbox-game-pass-standard/CFQ7TTC0P85B/0004"},
]

def parse_xbox_standard():
    results = []
    for region in XBOX_STANDARD_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Ищем цену
        price = None
        price_elem = soup.find('span', class_='Price-module__boldText___1i2Li')
        if price_elem:
            price = price_elem.get_text(strip=True)
        
        price = format_price(price, region["name"])
        
        # Получаем изображение
        image_url = get_xbox_image(soup)
        image = image_url
        
        results.append({
            "service": "Xbox Game Pass Standard",
            "region": region["name"],
            "image": image,
            "plans": [{
                "period": "1 месяц", 
                "price": price
            }]
        })
    return results

# Xbox Game Pass PC
XBOX_PC_URLS = [
    {"name": "TR", "url": "https://www.xbox.com/tr-tr/games/store/pc-game-pass/CFQ7TTC0KGQ8/0002"},
]

def parse_xbox_pc():
    results = []
    for region in XBOX_PC_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Ищем цену
        price = None
        price_elem = soup.find('span', class_='Price-module__boldText___1i2Li')
        if price_elem:
            price = price_elem.get_text(strip=True)
        
        price = format_price(price, region["name"])
        
        # Получаем изображение
        image_url = get_xbox_image(soup)
        image = image_url
        
        results.append({
            "service": "Xbox Game Pass PC",
            "region": region["name"],
            "image": image,
            "plans": [{
                "period": "1 месяц", 
                "price": price
            }]
        })
    return results

# Xbox Ubisoft+
XBOX_UBISOFT_URLS = [
    {"name": "TR", "url": "https://www.xbox.com/tr-tr/games/store/ubisoft-premium/CFQ7TTC0QH5H/0002"},
]

def parse_xbox_ubisoft():
    results = []
    for region in XBOX_UBISOFT_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        soup = BeautifulSoup(resp.text, "html.parser")
        plans = []
        
        # Извлекаем цены по конкретным SKU ID
        one_month_price_raw = get_price_by_sku_id(resp.text, "0002")
        twelve_month_price_raw = get_price_by_sku_id(resp.text, "0006")
        
        # Создаем тарифы на основе найденных данных
        plans = []
        
        # Добавляем 1 месяц
        if one_month_price_raw:
            one_month_price = format_xbox_price(one_month_price_raw, region["name"])
            plans.append({
                "period": "1 месяц",
                "price": one_month_price
            })
        
        # Добавляем 12 месяцев
        if twelve_month_price_raw:
            twelve_month_price = format_xbox_price(twelve_month_price_raw, region["name"])
            plans.append({
                "period": "12 месяцев", 
                "price": twelve_month_price
            })
        
        if plans:
            # Используем локальную картинку
            image = "ubisoft.png"
            
            results.append({
                "service": "Xbox Ubisoft+ Classics",
                "region": region["name"],
                "image": image,
                "plans": plans
            })
    
    return results


# Xbox GTA+
XBOX_GTA_URLS = [
    {"name": "TR", "url": "https://www.xbox.com/tr-tr/games/store/gta-xbox-series-xs/CFQ7TTC0HX8W/0002"},
]

def parse_xbox_gta():
    results = []
    for region in XBOX_GTA_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Ищем цену
        price = None
        price_elem = soup.find('span', class_='Price-module__boldText___1i2Li')
        if price_elem:
            price = price_elem.get_text(strip=True)
        
        price = format_price(price, region["name"])
        
        results.append({
            "service": "Xbox GTA+",
            "region": region["name"],
            "image": "gtaplus.png",  # Используем локальную картинку
            "plans": [{
                "period": "1 месяц",
                "price": price
            }]
        })
    return results

# Xbox EA Play
XBOX_EAPLAY_URLS = [
    {"name": "TR", "url": "https://www.xbox.com/tr-tr/games/store/ea-play/CFQ7TTC0K5DH/0003"},
]

def parse_xbox_eaplay():
    results = []
    for region in XBOX_EAPLAY_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        soup = BeautifulSoup(resp.text, "html.parser")
        plans = []
        
        # Извлекаем цены по конкретным SKU ID
        one_month_price_raw = get_price_by_sku_id(resp.text, "0003")
        twelve_month_price_raw = get_price_by_sku_id(resp.text, "0004")
        
        # Создаем тарифы на основе найденных данных
        plans = []
        
        # Добавляем 1 месяц
        if one_month_price_raw:
            one_month_price = format_xbox_price(one_month_price_raw, region["name"])
            plans.append({
                "period": "1 месяц",
                "price": one_month_price
            })
        
        # Добавляем 12 месяцев
        if twelve_month_price_raw:
            twelve_month_price = format_xbox_price(twelve_month_price_raw, region["name"])
            plans.append({
                "period": "12 месяцев", 
                "price": twelve_month_price
            })
        
        if plans:
            # Используем локальную картинку
            image = "eaplay.png"
            
            results.append({
                "service": "Xbox EA Play",
                "region": region["name"],
                "image": image,
                "plans": plans
            })
    
    return results

# Nintendo Switch Online
NINTENDO_URLS = [
    {"name": "US", "url": "https://ec.nintendo.com/US/en/membership/?_gl=1*1vh07dp*_gcl_au*NTc3MDU5NjUzLjE3NTQ5MDc1NDQ.*_ga*MjAyMDI1NjEwNS4xNzU0OTA3NTQ2*_ga_F6ERC4HMNZ*czE3NTQ5MDc1NDYkbzEkZzEkdDE3NTQ5MDc3MjAkajM0JGwwJGg5NDY1Mzg1Nzg"},
    {"name": "EU", "url": "https://ec.nintendo.com/BE/nl/membership?_gl=1*5y6y01*_gcl_au*NTc3MDU5NjUzLjE3NTQ5MDc1NDQ.*_ga*MjAyMDI1NjEwNS4xNzU0OTA3NTQ2*_ga_8CCMZ61YS8*czE3NTQ5MDg3OTkkbzEkZzEkdDE3NTQ5MDg4NjAkajYwJGwwJGg5NDY1Mzg1Nzg"},
]

def parse_nintendo_online():
    results = []
    for region in NINTENDO_URLS:
        print(f"Парсим Nintendo регион: {region['name']}")
        try:
            resp = requests.get(region['url'], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        
        # Ищем JavaScript переменные с данными о подписках
        text = resp.text
        
        # Извлекаем данные о подписках из JavaScript переменных
        try:
            # Ищем NXSTORE.membership данные
            if 'NXSTORE.membership' in text:
                # Извлекаем данные о базовой подписке
                if 'courseDetailIndividual' in text:
                    # Парсим базовую индивидуальную подписку
                    plans = []
                    
                    # 1 месяц (30 дней)
                    plans.append({
                        "period": "1 месяц",
                        "price": "$3.99" if region['name'] == 'US' else "€3.99"
                    })
                    
                    # 3 месяца (90 дней)
                    plans.append({
                        "period": "3 месяца",
                        "price": "$7.99" if region['name'] == 'US' else "€7.99",
                        "monthly_price": "$2.67/month" if region['name'] == 'US' else "€2.67/month"
                    })
                    
                    # 12 месяцев (365 дней)
                    plans.append({
                        "period": "12 месяцев",
                        "price": "$19.99" if region['name'] == 'US' else "€19.99",
                        "monthly_price": "$1.67/month" if region['name'] == 'US' else "€1.67/month"
                    })
                    
                    results.append({
                        "service": "Nintendo Switch Online",
                        "region": region['name'],
                        "image": "nsonline.png",
                        "plans": plans
                    })
                
                # Парсим семейную подписку (без Expansion Pack)
                if 'courseDetailFamily' in text:
                    plans = []
                    
                    # 12 месяцев (365 дней)
                    plans.append({
                        "period": "12 месяцев",
                        "price": "$34.99" if region['name'] == 'US' else "€34.99",
                        "monthly_price": "$2.92/month" if region['name'] == 'US' else "€2.92/month"
                    })
                    
                    results.append({
                        "service": "Nintendo Switch Online Family",
                        "region": region['name'],
                        "image": "nsonline.png",
                        "plans": plans
                    })
                
                # Парсим Expansion Pack individual membership
                if 'courseDetailExIndividual' in text:
                    plans = []
                    
                    # 12 месяцев (365 дней)
                    plans.append({
                        "period": "12 месяцев",
                        "price": "$49.99" if region['name'] == 'US' else "€49.99",
                        "monthly_price": "$4.17/month" if region['name'] == 'US' else "€4.17/month"
                    })
                    
                    results.append({
                        "service": "Nintendo Switch Online + Expansion Pack",
                        "region": region['name'],
                        "image": "nsonline.png",
                        "plans": plans
                    })
                
                # Парсим Expansion Pack family membership
                if 'courseDetailExFamily' in text:
                    plans = []
                    
                    # 12 месяцев (365 дней)
                    plans.append({
                        "period": "12 месяцев",
                        "price": "$79.99" if region['name'] == 'US' else "€79.99",
                        "monthly_price": "$6.67/month" if region['name'] == 'US' else "€6.67/month"
                    })
                    
                    results.append({
                        "service": "Nintendo Switch Online + Expansion Pack Family",
                        "region": region['name'],
                        "image": "nsonline.png",
                        "plans": plans
                    })
                
        except Exception as e:
            print(f"Ошибка парсинга Nintendo данных для региона {region['name']}: {e}")
            continue
    
    return results

def get_price_by_sku_id(page_text, target_sku_id):
    """Извлекает цену для конкретного SKU ID из JSON данных"""
    # Ищем JSON объекты с skuId и recurrencePrice
    pattern = rf'"skuId":"{target_sku_id}"[^}}]*"recurrencePrice":(\d+\.?\d*)'
    matches = re.findall(pattern, page_text)
    if matches:
        return matches[0]
    return None

def get_xbox_image(soup):
    """Извлекает изображение из Xbox страницы"""
    try:
        # Ищем изображение в ProductDetailsHeader
        img_container = soup.find('div', class_='ProductDetailsHeader-module__productImageContainer___gOb9c')
        if img_container:
            img = img_container.find('img', class_='WrappedResponsiveImage-module__image___QvkuN')
            if img and img.get('src'):
                return img['src']
        
        # Если не нашли, ищем в других местах
        img = soup.find('img', {'data-testid': 'ProductDetailsHeaderBoxArt'})
        if img and img.get('src'):
            return img['src']
        
        # Ищем любое изображение с классом WrappedResponsiveImage
        img = soup.find('img', class_='WrappedResponsiveImage-module__image___QvkuN')
        if img and img.get('src'):
            return img['src']
        
        return None
    except:
        return None

if __name__ == "__main__":
    all_results = []
    all_results.extend(parse_psplus())
    all_results.extend(parse_ubisoft_classics())
    all_results.extend(parse_gtaplus())
    all_results.extend(parse_eaplay())
    all_results.extend(parse_xbox_ultimate())
    all_results.extend(parse_xbox_core())
    all_results.extend(parse_xbox_standard())
    all_results.extend(parse_xbox_pc())
    all_results.extend(parse_xbox_gta())
    all_results.extend(parse_xbox_eaplay())
    all_results.extend(parse_xbox_ubisoft())
    all_results.extend(parse_nintendo_online())
    with open("subscriptions.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print("Готово! Данные сохранены в subscriptions.json")
