import os
import re
import asyncio
import requests
from bs4 import BeautifulSoup
from telegram import Bot

# 1. 중복 필터링 함수
def is_similar(a, b):
    def clean(text):
        return re.sub(r'[^가-힣a-zA-Z0-9]', '', re.sub(r'<.*?>|&\w+;', '', text))
    a_clean, b_clean = clean(a), clean(b)
    if not a_clean or not b_clean: return 0
    set_a, set_b = set(a_clean), set(b_clean)
    return len(set_a & set_b) / min(len(set_a), len(set_b))

def escape_html(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# 2. 지자체 고시 수집
def get_combined_city_notices():
    target_keywords = ["지구단위계획", "용도지역", "변경", "주민공람", "보상계획", "토지보상", "실시계획", "인가"]
    cities = [
        {"name": "김포시", "url": "https://www.gimpo.go.kr/portal/selectBbsNttList.do?bbsNo=155&key=1138", "base_url": "https://www.gimpo.go.kr", "selector": "table.board-list tbody tr"},
        {"name": "화성시", "url": "https://www.hscity.go.kr/www/user/bbs/BD_selectBbsList.do?q_bbsCode=1019", "base_url": "https://www.hscity.go.kr", "selector": "table.table-list tbody tr"},
        {"name": "양주시", "url": "https://www.yangju.go.kr/www/selectBbsNttList.do?bbsNo=54&key=361", "base_url": "https://www.yangju.go.kr", "selector": "table.bbs-list tbody tr"},
        {"name": "남양주시", "url": "https://www.namyangju.go.kr/main/notice/1", "base_url": "https://www.namyangju.go.kr", "selector": "table.board-list tbody tr"}
    ]
    all_notices = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for city in cities:
        try:
            res = requests.get(city['url'], headers=headers, timeout=15)
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, 'html.parser')
            for row in soup.select(city['selector']):
                link_elem = row.select_one('a')
                if not link_elem: continue
                title = link_elem.get_text(strip=True)
                matched = [kw for kw in target_keywords if kw in title]
                if matched:
                    all_notices.append({"city": city['name'], "tag": f"#{matched[0]}", "title": title, "link": city['base_url'] + link_elem['href'] if link_elem['href'].startswith('/') else link_elem['href']})
        except: continue
    return all_notices

# 3. 메인 실행 함수
async def main():
    history_file = "seen_news.txt"
    old_titles = open(history_file, "r", encoding="utf-8").read().splitlines() if os.path.exists(history_file) else []
    keywords = ["부동산 경매", "지구단위계획", "경기일보 부동산", "김포시 개발", "화성시 토지", "남양주시 보상"]
    new_titles, messages = [], []
    current_msg = "📢 오늘의 부동산 & 지역 뉴스\n"

    # 네이버 뉴스
    headers = {"X-Naver-Client-Id": os.environ.get('NAVER_ID',''), "X-Naver-Client-Secret": os.environ.get('NAVER_SECRET','')}
    for kw in keywords:
        try:
            res = requests.get(f"https://openapi.naver.com/v1/search/news?query={kw}&display=10&sort=sim", headers=headers).json()
            for item in res.get('items', []):
                title = re.sub(r'<.*?>', '', item['title']).replace('&quot;', '"')
                if not any(is_similar(title, old) > 0.35 for old in (old_titles + new_titles)):
                    current_msg += f"📍 {escape_html(title)}\n   🔗 {item['link']}\n\n"
                    new_titles.append(title)
        except: continue

    # 지자체 고시
    notices = get_combined_city_notices()
    if notices:
        current_msg += "\n🏛️ 지자체 핵심 고시\n"
        for n in notices:
            if not any(is_similar(n['title'], old) > 0.35 for old in (old_titles + new_titles)):
                current_msg += f"• {n['tag']} {escape_html(n['title'])}\n  🔗 <a href='{n['link']}'>공고보기</a>\n"
                new_titles.append(n['title'])

    if new_titles:
        bot = Bot(token=os.environ.get('TELEGRAM_TOKEN',''))
        await bot.send_message(chat_id=os.environ.get('CHAT_ID',''), text=current_msg, parse_mode='HTML', disable_web_page_preview=True)
        with open(history_file, "w", encoding="utf-8") as f:
            f.write("\n".join((new_titles + old_titles)[:1000]))

if __name__ == "__main__":
    asyncio.run(main())
