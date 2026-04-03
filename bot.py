import os, requests, asyncio, re
from bs4 import BeautifulSoup
from telegram import Bot

# -------------------------------------------------
# 1️⃣ 중복 및 유사도 검사 함수
# -------------------------------------------------
def is_similar(a, b):
    def clean_for_comparison(text):
        text = re.sub(r'<.*?>|&\w+;', '', text)
        text = re.sub(r'\[.*?\]|\(.*?\)', '', text)
        return re.sub(r'[^가-힣a-zA-Z0-9]', '', text)
    a_clean = clean_for_comparison(a)
    b_clean = clean_for_comparison(b)
    if not a_clean or not b_clean: return 0
    set_a, set_b = set(a_clean), set(b_clean)
    overlap = len(set_a & set_b)
    return overlap / min(len(set_a), len(set_b))

def escape_html(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# -------------------------------------------------
# 2️⃣ 지자체 고시공고 수집 (김포·화성·양주·남양주)
# -------------------------------------------------
def get_combined_city_notices():
    target_keywords = [
        "지구단위계획", "지형도면", "용도지역", "도시관리계획", "변경",
        "주민공람", "공람공고", "보상계획", "손실보상", "토지보상",
        "실시계획", "인가", "개발행위", "구역지정", "도로", "수용"
    ]
    cities = [
        {"name": "김포시", "url": "https://www.gimpo.go.kr/portal/selectBbsNttList.do?bbsNo=153&key=156", "base_url": "https://www.gimpo.go.kr", "selector": "table.board-list tbody tr"},
        {"name": "화성시", "url": "https://www.hscity.go.kr/www/user/bbs/BD_selectBbsList.do?q_bbsCode=1019", "base_url": "https://www.hscity.go.kr", "selector": "table.table-list tbody tr"},
        {"name": "양주시", "url": "https://www.yangju.go.kr/www/selectBbsNttList.do?bbsNo=42&key=197", "base_url": "https://www.yangju.go.kr", "selector": "table.bbs-list tbody tr"},
        {"name": "남양주시", "url": "https://www.nyj.go.kr/www/selectBbsNttList.do?bbsNo=131&key=465", "base_url": "https://www.nyj.go.kr", "selector": "table.board-list tbody tr"}
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    all_notices = []

    for city in cities:
        try:
            response = requests.get(city['url'], headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.select(city['selector'])
            for row in rows:
                title_elem = row.select_one('td.left a') or row.select_one('td.subject a') or row.select_one('a')
                if not title_elem: continue
                title = title_elem.get_text(strip=True)
                matched = [kw for kw in target_keywords if kw in title]
                if matched:
                    link = title_elem['href']
                    full_link = city['base_url'] + link if link.startswith('/') else link
                    all_notices.append({"city": city['name'], "tag": f"#{matched[0]}", "title": title, "link": full_link})
        except Exception as e:
            print(f"{city['name']} 수집 실패: {e}")
    return all_notices

# -------------------------------------------------
# 3️⃣ 메인 실행 로직
# -------------------------------------------------
async def main():
    history_file = "seen_news.txt"
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            old_titles = [line.strip() for line in f if line.strip()]
    else:
        old_titles = []

    # ✅ [전략적 키워드 구성] 큰 그물 + 정밀 갈고리 + 지방지 전용
    keywords = [
        # 1. 주제 중심 (전국구 모든 언론사 소식)
        "부동산 경매", "지구단위계획 결정", "용도지역 변경", "재개발 주민공람", "고속도로 보상",
        
        # 2. 지역별 큰 그물 (해당 지역의 '모든' 개발 소식 타겟)
        "김포 개발", "화성 개발", "양주 개발", "남양주 개발",
        
        # 3. 지역별 정밀 갈고리 (사용자님이 우려하신 '역세권' 등 보강)
        "김포 역세권", "화성 토지 보상", "양주 역세권", "왕숙지구 보상",
        
        # 4. 지방지 전용 (지방지들의 단독 보도 선점)
        "경기일보 부동산", "경인일보 부동산", "중부일보 부동산", "경기신문 부동산"
    ]
    
    local_press_map = {
        "경기일보": "kyeonggi.com",
        "경인일보": "kyeongin.com",
        "중부일보": "joongboo.com",
        "경기신문": "kgnews.co.kr"
    }

    naver_headers = {
        "X-Naver-Client-Id": os.environ.get('NAVER_ID', ''),
        "X-Naver-Client-Secret": os.environ.get('NAVER_SECRET', '')
    }

    new_titles = []
    messages = []
    current_message = "📢 <b>오늘의 부동산 뉴스 & 고시 브리핑</b>\n"

    # --- [파트 1] 네이버 뉴스 수집 ---
    for kw in keywords:
        # 최신순(date) 정렬로 2019년 뉴스 완벽 차단
        api_url = f"https://openapi.naver.com/v1/search/news.json?query={requests.utils.quote(kw)}&display=15&sort=date"
        try:
            res = requests.get(api_url, headers=naver_headers, timeout=10).json()
            if 'items' not in res: continue
            
            category_entries = []
            for item in res['items']:
                if len(category_entries) >= 5: break
                
                link = item.get('link', '')
                title = re.sub(r'<.*?>', '', item['title']).replace('&quot;', '"').replace('&amp;', '&')
                
                # 지방지 키워드일 경우 해당 도메인만 필터링
                target_press = next((name for name in local_press_map if name in kw), None)
                if target_press:
                    if local_press_map[target_press] not in link: continue

                # 중복 및 유사도 검사
                if not any(is_similar(title, existing) > 0.35 for existing in (old_titles + new_titles)):
                    category_entries.append(f"📍 {escape_html(title)}\n   🔗 {link}\n")
                    new_titles.append(title)
            
            if category_entries:
                kw_header = f"\n🔹 <b>{escape_html(kw)}</b>\n"
                combined = kw_header + "\n".join(category_entries) + "\n"
                if len(current_message) + len(combined) > 3800:
                    messages.append(current_message)
                    current_message = f"📢 (계속)\n{combined}"
                else:
                    current_message += combined
        except Exception as e:
            print(f"뉴스 수집 에러 ({kw}): {e}")

    # --- [파트 2] 지자체 고시공고 수집 ---
    city_notices = get_combined_city_notices()
    if city_notices:
        notice_text = "\n🏛️ <b>지자체 핵심 고시 (김포·화성·양주·남양주)</b>\n"
        notice_text += "━━━━━━━━━━━━━━━━━━\n"
        current_city = ""
        for n in city_notices:
            if any(is_similar(n["title"], old) > 0.35 for old in (old_titles + new_titles)): continue
            
            if current_city != n['city']:
                notice_text += f"\n📍 <b>{n['city']}</b>\n"
                current_city = n['city']
            notice_text += f"• {n['tag']} {escape_html(n['title'])}\n  🔗 <a href='{n['link']}'>공고보기</a>\n"
            new_titles.append(n["title"])
        
        if len(current_message) + len(notice_text) > 3800:
            messages.append(current_message)
            current_message = notice_text
        else:
            current_message += notice_text

    # --- [파트 3] 전송 및 저장 ---
    if new_titles:
        messages.append(current_message)
        bot = Bot(token=os.environ['TELEGRAM_TOKEN'])
        async with bot:
            for msg in messages:
                await bot.send_message(chat_id=os.environ['CHAT_ID'], text=msg, parse_mode='HTML', disable_web_page_preview=True)
        
        updated_history = list(dict.fromkeys(t.strip() for t in (new_titles + old_titles) if t.strip()))[:1000]
        with open(history_file, "w", encoding="utf-8") as f:
            for t in updated_history: f.write(t + "\n")
    else:
        print("새로운 소식이 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())
