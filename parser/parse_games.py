import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import re
import os

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

GAMES_JSON = os.path.join(os.path.dirname(__file__), 'games.json')

async def fetch(session, url):
    async with session.get(url, headers=HEADERS, timeout=20) as resp:
        return await resp.text()

def map_langs(langs):
    result = []
    for lang in langs:
        if lang.lower().startswith('english'):
            result.append('Английский')
        elif lang.lower().startswith('russian'):
            result.append('Русский')
    return ', '.join(result)

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
        return release_date, voice_ps4, subtitles_ps4, voice_ps5, subtitles_ps5, platforms
    except Exception:
        return '', '', '', '', '', []

async def parse_playstation_async(url, region):
    import requests
    games = []
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    cards = soup.find_all('li', class_=re.compile('^psw-l-w-'))
    game_links = []
    for li in cards:
        a = li.find('a', class_='psw-link')
        if not a:
            continue
        # Название только из <span class='psw-t-body'>
        title_tag = a.find('span', class_='psw-t-body')
        title = title_tag.text.strip() if title_tag else 'No title'
        # Картинка
        img_url = ''
        # Ищем img с data-qa, содержащим 'game-art#image#image'
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
        # Цена
        price = ''
        old_price = ''
        discount = ''
        # Парсим discount_percent из discount-badge
        discount_badge = li.find('div', {'data-qa': re.compile('discount-badge')})
        if discount_badge:
            span = discount_badge.find('span')
            if span and span.text.strip().startswith('-'):
                discount = span.text.strip()
        # Цена
        price_span = a.find('span', {'data-qa': re.compile('price#display-price')})
        if price_span:
            price = price_span.text.strip()
        # old_price только из <span data-qa='price#original-price'> или <s>
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
        if upsell_save:
            subscription = upsell_save.get_text(strip=True)
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
    for (full_link, title, img_url, price, old_price, discount, subscription, subscription_icon, region), (release_date, voice_ps4, subtitles_ps4, voice_ps5, subtitles_ps5, platforms) in zip(game_links, details_list):
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
        # Если только одна платформа, не добавляем вторую
        games.append(game)
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