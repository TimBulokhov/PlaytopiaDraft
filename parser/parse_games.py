import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import re
import os
import time
import requests

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

GAMES_JSON = os.path.join(os.path.dirname(__file__), 'games.json')

async def fetch(session, url):
    async with session.get(url, headers=HEADERS, timeout=35) as resp:
        return await resp.text()

def map_langs(langs):
    result = []
    for lang in langs:
        if lang.lower().startswith('english'):
            result.append('Английский')
        elif lang.lower().startswith('russian'):
            result.append('Русский')
    return ', '.join(result)

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

async def get_game_details(session, game_url):
    try:
        html = await fetch(session, game_url)
        soup = BeautifulSoup(html, 'html.parser')
        # Дата выхода
        release_date = ''
        date_dd = soup.find('dd', {'data-qa': 'gameInfo#releaseInformation#releaseDate-value'})
        if date_dd:
            release_date = date_dd.text.strip()
        # Озвучка и субтитры для PS4/PS5
        voice_ps4 = ''
        voice_ps5 = ''
        subtitles_ps4 = ''
        subtitles_ps5 = ''
        # PS5 Voice
        voice_ps5_dd = soup.find('dd', {'data-qa': 'gameInfo#releaseInformation#ps5Voice-value'})
        if voice_ps5_dd:
            langs = [x.strip() for x in voice_ps5_dd.text.split(',') if x.strip()]
            voice_ps5 = map_langs(langs)
        # PS5 Subtitles
        subtitles_ps5_dd = soup.find('dd', {'data-qa': 'gameInfo#releaseInformation#ps5Subtitles-value'})
        if subtitles_ps5_dd:
            langs = [x.strip() for x in subtitles_ps5_dd.text.split(',') if x.strip()]
            subtitles_ps5 = map_langs(langs)
        # PS4 Voice
        voice_ps4_dd = soup.find('dd', {'data-qa': 'gameInfo#releaseInformation#ps4Voice-value'})
        if voice_ps4_dd:
            langs = [x.strip() for x in voice_ps4_dd.text.split(',') if x.strip()]
            voice_ps4 = map_langs(langs)
        # PS4 Subtitles
        subtitles_ps4_dd = soup.find('dd', {'data-qa': 'gameInfo#releaseInformation#ps4Subtitles-value'})
        if subtitles_ps4_dd:
            langs = [x.strip() for x in subtitles_ps4_dd.text.split(',') if x.strip()]
            subtitles_ps4 = map_langs(langs)
        # Если нет отдельных, ищем общее поле (старый вариант)
        if not (voice_ps4 or voice_ps5):
            voice_dd = soup.find('dd', {'data-qa': 'gameInfo#releaseInformation#voice-value'})
            if voice_dd:
                langs = [x.strip() for x in voice_dd.text.split(',') if x.strip()]
                mapped = map_langs(langs)
                voice_ps4 = mapped
                voice_ps5 = mapped
        if not (subtitles_ps4 or subtitles_ps5):
            subs_dd = soup.find('dd', {'data-qa': 'gameInfo#releaseInformation#subtitles-value'})
            if subs_dd:
                langs = [x.strip() for x in subs_dd.text.split(',') if x.strip()]
                mapped = map_langs(langs)
                subtitles_ps4 = mapped
                subtitles_ps5 = mapped
        # Платформы
        platforms = []
        platform_dd = soup.find('dd', {'data-qa': 'gameInfo#releaseInformation#platform-value'})
        if platform_dd:
            platforms = [x.strip() for x in platform_dd.text.split(',')]
        # --- Новый блок: ищем дополнительные подписки на детальной странице ---
        additional_subscription = ''
        offer_blocks = soup.find_all('div', class_=re.compile('psw-l-anchor'))
        for offer in offer_blocks:
            included_span = offer.find('span', string=re.compile('Included', re.I))
            if included_span:
                # Ищем иконку подписки
                icon_span = offer.find('span', class_=re.compile('psw-icon'))
                if icon_span:
                    icon_classes = icon_span.get('class', [])
                    if any('psw-icon--3rd-party-ubisoft-plus' in c for c in icon_classes):
                        additional_subscription = 'ubisoft'
                    elif any('psw-icon--3rd-party-gta-plus' in c for c in icon_classes):
                        additional_subscription = 'gtaplus'
                    elif any('psw-icon--3rd-party-ea' in c for c in icon_classes):
                        additional_subscription = 'eaplay'
                    elif any('psw-icon--ps-plus' in c for c in icon_classes):
                        additional_subscription = 'psplus'
        # --- Конец нового блока ---
        return release_date, voice_ps4, subtitles_ps4, voice_ps5, subtitles_ps5, platforms, additional_subscription
    except Exception:
        return '', '', '', '', '', [], ''

def safe_get(url, headers, retries=3, delay=3):
    for i in range(retries):
        try:
            return requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса: {e}. Попытка {i+1}/{retries}")
            time.sleep(delay)
    return None

async def parse_playstation_async(url, region):
    games = []
    page = 1
    while page <= 3:
        page_url = re.sub(r'/browse/\d+', f'/browse/{page}', url)
        resp = safe_get(page_url, HEADERS)
        if resp is None:
            print(f"Не удалось получить страницу {page_url} после нескольких попыток")
            continue
        soup = BeautifulSoup(resp.text, 'html.parser')
        cards = soup.find_all('li', class_=re.compile('^psw-l-w-'))
        if not cards:
            break
        game_links = []
        for li in cards:
            a = li.find('a', class_='psw-link')
            if not a:
                continue
            title_tag = a.find('span', class_='psw-t-body')
            title = title_tag.text.strip() if title_tag else 'No title'
            # Картинка
            img_url = ''
            img_tag = a.find('img', {'data-qa': re.compile('game-art#image#image')})
            if img_tag:
                srcset = img_tag.get('srcset', '')
                if srcset:
                    srcset_items = [s.strip().split(' ')[0] for s in srcset.split(',')]
                    found_440 = [u for u in srcset_items if 'w=440' in u and 'thumb=false' in u]
                    found_230 = [u for u in srcset_items if 'w=230' in u and 'thumb=false' in u]
                    if found_440:
                        img_url = found_440[0]
                    elif found_230:
                        img_url = found_230[0]
                    else:
                        img_url = img_tag.get('src', '')
                else:
                    img_url = img_tag.get('src', '')
            price = ''
            old_price = ''
            discount = ''
            discount_badge = li.find('div', {'data-qa': re.compile('discount-badge')})
            if discount_badge:
                span = discount_badge.find('span')
                if span:
                    discount_text = span.text.strip()
                    # Применяем перевод скидки
                    discount = translate_discount(discount_text)
            price_span = a.find('span', {'data-qa': re.compile('price#display-price')})
            if price_span:
                price = price_span.text.strip()
            old_price_tag = a.find('span', {'data-qa': re.compile('price#original-price')})
            if not old_price_tag:
                old_price_tag = a.find('s')
            old_price = old_price_tag.text.strip() if old_price_tag else ''
            subscription = ''
            subscription_icon = ''
            upsell_save = a.find('span', {'data-qa': re.compile('service-upsell#descriptorText')})
            upsell_block = a.find_parent('div', class_='psw-service-upsell') or a.find('div', class_='psw-service-upsell')
            if upsell_block:
                if upsell_block.find('span', class_='psw-icon--3rd-party-ea'):
                    subscription_icon = 'eaplay'
                elif upsell_block.find('span', class_='psw-icon--ps-plus'):
                    subscription_icon = 'psplus'
                elif upsell_block.find('span', class_='psw-icon--3rd-party-gta-plus'):
                    subscription_icon = 'gtaplus'
            if upsell_save:
                subscription_text = upsell_save.get_text(strip=True)
                # Применяем перевод скидки к тексту подписки
                subscription = translate_discount(subscription_text)
            link = a.get('href')
            if not link:
                continue
            full_link = 'https://store.playstation.com' + link
            price_clean = price.strip().lower().replace(' ', '')
            if not price_clean or price_clean in ['free', 'бесплатно']:
                continue
            game_links.append((full_link, title, img_url, price, old_price, discount, subscription, subscription_icon, region))
        async with aiohttp.ClientSession() as session:
            tasks = [get_game_details(session, link) for link, *_ in game_links]
            details_list = await asyncio.gather(*tasks)
        new_games = []
        for (full_link, title, img_url, price, old_price, discount, subscription, subscription_icon, region), (release_date, voice_ps4, subtitles_ps4, voice_ps5, subtitles_ps5, platforms, additional_subscription) in zip(game_links, details_list):
            # Если на детальной странице найдена дополнительная подписка, добавляем её
            if additional_subscription and not subscription_icon:
                subscription_icon = additional_subscription
            elif additional_subscription and subscription_icon and additional_subscription != subscription_icon:
                # Если уже есть подписка, но найдена другая, объединяем
                subscription_icon = f"{subscription_icon},{additional_subscription}"
            
            # Заменяем "Included" на правильные названия подписок
            if subscription == "Included" and subscription_icon:
                if subscription_icon == "gtaplus":
                    subscription = "GTA+"
                elif subscription_icon == "ubisoft":
                    subscription = "Ubisoft+"
                elif subscription_icon == "eaplay":
                    subscription = "EA Play"
                elif subscription_icon == "psplus":
                    subscription = "Extra"  # или "Essential", "Deluxe" в зависимости от типа
                elif "," in subscription_icon:
                    # Для игр с несколькими подписками
                    icons = subscription_icon.split(",")
                    if "psplus" in icons:
                        subscription = "Extra"  # PS Plus всегда первый
                    else:
                        # Если нет PS Plus, берем первую подписку
                        first_icon = icons[0]
                        if first_icon == "gtaplus":
                            subscription = "GTA+"
                        elif first_icon == "ubisoft":
                            subscription = "Ubisoft+"
                        elif first_icon == "eaplay":
                            subscription = "EA Play"
            
            game = {
                'title': title,
                'img': img_url,
                'price': price,
                'old_price': old_price,
                'discount_percent': discount,
                'subscription': subscription,
                'subscription_icon': subscription_icon,
                'product_type': '',
                'link': full_link,
                'platforms': platforms,
                'region': region,
                'release_date': release_date
            }
            if 'PS4' in platforms:
                game['voice_ps4'] = voice_ps4
                game['subtitles_ps4'] = subtitles_ps4
            if 'PS5' in platforms:
                game['voice_ps5'] = voice_ps5
                game['subtitles_ps5'] = subtitles_ps5
            new_games.append(game)
        # После каждой страницы сразу обновляем файл, не затирая уже спарсанные игры
        try:
            if os.path.exists(GAMES_JSON):
                with open(GAMES_JSON, 'r', encoding='utf-8') as f:
                    current = json.load(f)
            else:
                current = []
            # Добавляем только новые игры, которых ещё нет (по ссылке)
            current_links = set(g['link'] for g in current)
            unique_new = [g for g in new_games if g['link'] not in current_links]
            current += unique_new
            with open(GAMES_JSON, 'w', encoding='utf-8') as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
            games += unique_new
        except Exception as e:
            print(f'Ошибка при записи в games.json: {e}')
        page += 1
        time.sleep(1)
    return games

async def main_async():
    all_games = []
    all_games += await parse_playstation_async('https://store.playstation.com/en-tr/pages/browse/1', 'tr')
    all_games += await parse_playstation_async('https://store.playstation.com/en-in/pages/browse/1', 'in')
    with open(GAMES_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_games, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    print('Парсинг запущен...')
    asyncio.run(main_async()) 