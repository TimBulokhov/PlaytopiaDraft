import requests
from bs4 import BeautifulSoup
import json
import re

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
        price = price.replace("TL", " TL").replace(" TL", " TL")
        price = re.sub(r'\s+TL', ' TL', price)
    if region == "IN":
        price = price.replace("Rs ", "Rs ").replace("Rs", "Rs ")
        price = re.sub(r'Rs\s*([0-9])', r'Rs \1', price)
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
    
    # Заменяем "Save n%" на "Скидка n%"
    if discount_text.startswith('Save '):
        # Извлекаем процент
        import re
        
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
    
    # Оставляем "-n%" формат как есть
    return discount_text

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
            # Применяем перевод скидки
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

if __name__ == "__main__":
    all_results = []
    all_results.extend(parse_psplus())
    all_results.extend(parse_ubisoft_classics())
    all_results.extend(parse_gtaplus())
    all_results.extend(parse_eaplay())
    with open("subscriptions.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print("Готово! Данные сохранены в subscriptions.json")
