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
                price_html = offer.get('price', {}).get('discountedPrice') or offer.get('price', {}).get('basePrice')
                if not price_html:
                    continue
                price = format_price(price_html, region["name"])
                plans.append({
                    "period": period,
                    "price": price
                })
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
    {"name": "TR", "url": "https://www.playstation.com/en-tr/games/ubisoft-plus-classics/"},
    {"name": "IN", "url": "https://www.playstation.com/en-in/games/ubisoft-plus-classics/"},
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
        title = soup.find("h3", string=re.compile("1-month subscription", re.I))
        price = None
        if title and title.parent:
            siblings = getattr(title.parent, 'find_next_siblings', lambda: [])()
            for sibling in siblings:
                if hasattr(sibling, 'find'):
                    price_tag = sibling.find(string=re.compile(r"(TL|Rs)"))
                    if price_tag and isinstance(price_tag, str):
                        price = price_tag.strip()
                        break
        if not price:
            # Альтернативный способ: ищем по всему документу только строки
            for string in soup.strings:
                if re.search(r'(TL|Rs)', string):
                    price = string.strip()
                    break
        price = format_price(price, region["name"])
        results.append({
            "service": "Ubisoft+ Classics",
            "region": region["name"],
            "image": "ubisoft.png",
            "plans": [{"period": "1 месяц", "price": price}]
        })
    return results

# GTA+
def parse_gtaplus():
    results = []
    urls = [
        ("TR", "https://store.playstation.com/en-tr/pages/subscriptions/", "TL"),
        ("IN", "https://store.playstation.com/en-in/pages/subscriptions/", "Rs")
    ]
    for region, url, currency in urls:
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {url}: {e}")
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        gta_block = None
        price = None
        # Ищем GTA+ по названию
        for a in soup.find_all("a", href=True):
            if a.text and "GTA+" in a.text:
                gta_block = a
                break
        if gta_block:
            # Ищем цену в дочерних элементах
            price_tag = gta_block.find(string=re.compile(rf'{currency}'))
            if price_tag:
                price = price_tag.strip()
            else:
                # Альтернативно ищем в details
                details = gta_block.find_next("section", class_="psw-product-tile__details")
                if details:
                    price_tag = details.find(string=re.compile(rf'{currency}'))
                    if price_tag:
                        price = price_tag.strip()
        if not price:
            # Альтернативный способ: ищем по всему документу только строки
            for string in soup.strings:
                if re.search(r'GTA\+.*?(\d+[.,\d]*\s*' + currency + ")", string, re.I):
                    m = re.search(r'(\d+[.,\d]*\s*' + currency + ")", string)
                    if m:
                        price = m.group(1)
                        break
        price = format_price(price, region)
        results.append({
            "service": "GTA+",
            "region": region,
            "image": "gtaplus.png",
            "plans": [{"period": "1 месяц", "price": price}]
        })
    return results

# EA Play
EAPLAY_URLS = [
    {"name": "TR", "url": "https://www.playstation.com/en-tr/games/ea-play/"},
    {"name": "IN", "url": "https://www.playstation.com/en-in/games/ea-play/"},
]
def parse_eaplay():
    results = []
    for region in EAPLAY_URLS:
        try:
            resp = requests.get(region["url"], timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Ошибка загрузки {region['url']}: {e}")
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        # Find all subscription blocks
        blocks = soup.find_all("div", class_="box--lightAlt")
        plans = []
        for block in blocks:
            # Period from h3
            h3 = block.find("h3")
            if not h3:
                continue
            period_text = h3.get_text(strip=True)
            # Normalize period
            if "1-month" in period_text:
                period = "1 месяц"
            elif "12-month" in period_text:
                period = "12 месяцев"
            else:
                continue
            # Find embedded JSON with price
            script = block.find("script", {"type": "application/json"})
            price = None
            if script:
                try:
                    data = json.loads(script.text)
                    # Try to get price from cache
                    cache = data.get("cache", {})
                    # Find GameCTA in cache
                    for v in cache.values():
                        if isinstance(v, dict) and v.get("__typename") == "GameCTA":
                            price = v.get("price", {}).get("basePrice") or v.get("price", {}).get("discountedPrice")
                            if price:
                                break
                except Exception as e:
                    print(f"Ошибка парсинга JSON в блоке EA Play: {e}")
            # Fallback: try to find price in visible text
            if not price:
                price_tag = block.find(string=re.compile(r'(TL|Rs)'))
                if price_tag:
                    price = price_tag.strip()
            price = format_price(price, region["name"])
            plans.append({"period": period, "price": price})
        results.append({
            "service": "EA Play",
            "region": region["name"],
            "image": "eaplay.png",
            "plans": plans
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
