"""Fetch simple pages from www.mmec.edu.in and save extracted text into data/college_info/site_pages.json
This is a lightweight crawler: fetches the homepage and follows internal links (same domain) up to depth 1.
Use responsibly and obey robots.txt — this is intended for small-scale site scraping for your chatbot.
"""
import requests
from bs4 import BeautifulSoup
import json
import os
import urllib.parse

BASE = 'https://www.mmec.edu.in'
OUT_DIR = os.path.join('data', 'college_info')
PAGES_JSON = os.path.join(OUT_DIR, 'site_pages.json')

os.makedirs(OUT_DIR, exist_ok=True)


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    # remove scripts and styles
    for s in soup(['script','style','noscript']):
        s.decompose()
    text = soup.get_text(separator=' ', strip=True)
    # collapse whitespace
    return ' '.join(text.split())


def is_internal(link: str) -> bool:
    if not link: return False
    parsed = urllib.parse.urlparse(link)
    if parsed.netloc and 'mmec.edu.in' not in parsed.netloc:
        return False
    return True


def normalize_url(href: str, base: str) -> str:
    return urllib.parse.urljoin(base, href)


def fetch():
    session = requests.Session()
    to_visit = [BASE]
    visited = set()
    pages = []
    while to_visit:
        url = to_visit.pop(0)
        if url in visited: continue
        visited.add(url)
        try:
            r = session.get(url, timeout=15)
            if r.status_code != 200:
                continue
            text = extract_text(r.text)
            pages.append({'url': url, 'text': text})
            # parse links for depth 1
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                full = normalize_url(href, url)
                if is_internal(full) and full not in visited and full.startswith(BASE):
                    # limit to same domain and avoid query strings duplicates
                    parsed = urllib.parse.urlparse(full)
                    clean = parsed.scheme + '://' + parsed.netloc + parsed.path
                    if clean not in visited and len(visited) < 40:
                        to_visit.append(clean)
        except Exception as e:
            print('fetch error', url, e)
            continue
    # save pages
    with open(PAGES_JSON, 'w', encoding='utf-8') as f:
        json.dump(pages, f, indent=2, ensure_ascii=False)
    print(f'Fetched {len(pages)} pages. Saved to {PAGES_JSON}')

if __name__ == '__main__':
    fetch()
