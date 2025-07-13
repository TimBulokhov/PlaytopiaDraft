import requests
from bs4 import BeautifulSoup
import json
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

PLATFORMS = {
    'ps5': {'name': 'PS5', 'img': 'ps5.png'},
    'ps4': {'name': 'PS4', 'img': 'ps4.png'},
    'xbox': {'name': 'Xbox', 'img': 'xbox.png'},
}

def parse_playstation(url, platform):
    games = []
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    for li in soup.find_all('li', class_=re.compile('^psw-l-w-')):
        a = li.find('a', class_='psw-link')
        if not a:
            continue
        title = a.find('span', class_='psw-t-body')
        title = title.text.strip() if title else 'No title'
        img = a.find('img', class_=re.compile('psw-fade-in'))
        img_url = img['src'] if img else ''
        price = a.find('span', class_=re.compile('price'))
        if not price:
            price = a.find('span', class_=re.compile('psw-m-r-3'))
        price = price.text.strip() if price else '—'
        link = a['href'] if a.has_attr('href') else '#'
        games.append({
            'title': title,
            'img': img_url,
            'price': price,
            'link': 'https://store.playstation.com' + link,
            'platform': PLATFORMS[platform],
        })
    return games

def parse_xbox(url):
    games = []
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    for li in soup.find_all('li'):
        a = li.find('a', class_=re.compile('ProductCard-module__cardWrapper'))
        if not a:
            a = li.find('a', class_=re.compile('Button-module__buttonBase'))
        if not a:
            continue
        title = a.find('span', class_=re.compile('ProductCard-module__title'))
        title = title.text.strip() if title else 'No title'
        img = a.find('img')
        img_url = img['src'] if img else ''
        price = a.find('span', class_=re.compile('ProductCard-module__price'))
        if not price:
            price = a.find('span', class_=re.compile('Price-module__boldText'))
        price = price.text.strip() if price else '—'
        link = a['href'] if a.has_attr('href') else '#'
        games.append({
            'title': title,
            'img': img_url,
            'price': price,
            'link': link,
            'platform': PLATFORMS['xbox'],
        })
    return games

def main():
    all_games = []
    # PlayStation TR
    all_games += parse_playstation('https://store.playstation.com/en-tr/pages/browse/1', 'ps5')
    # PlayStation IN
    all_games += parse_playstation('https://store.playstation.com/en-in/pages/browse/1', 'ps4')
    # Xbox TR
    all_games += parse_xbox('https://www.xbox.com/tr-TR/games/browse')
    # Xbox IN
    all_games += parse_xbox('https://www.xbox.com/en-IN/games/browse')
    with open('parser/games.json', 'w', encoding='utf-8') as f:
        json.dump(all_games, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main() 