import os, requests, asyncio, re
from telegram import Bot

# 중복 체크를 위한 유사도 함수 (기존 유지)
def is_similar(a, b):
    def clean(text):
        text = re.sub(r'\[.*?\]|\(.*?\)', '', text)
        return re.sub(r'[^가-힣a-zA-Z0-9]', '', text)
    a_clean, b_clean = clean(a), clean(b)
    set_a, set_b = set(a_clean), set(b_clean)
    if not set_a or not set_b: return 0
    return len(set_a & set_b) / min(len(set_a), len(set_b))

async def main():
    # 1. 과거에 보냈던 기사 제목 장부(seen_news.txt) 읽기
    history_file = "seen_news.txt"
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            old_titles = [line.strip() for line in f.readlines()]
    else:
        old_titles = []

    keywords = ["부동산 경매", "지구단위계획", "용도지역 변경", "역세권 개발", "주민공람"]
    headers = {
        "X-Naver-Client-Id": os.environ['NAVER_ID'], 
        "X-Naver-Client-Secret": os.environ['NAVER_SECRET']
    }
    
    new_titles = [] # 이번에 새로 보낼 기사들
    messages = []
    current_message = f"📢 오늘의 부동산 뉴스 브리핑\n\n"

    for kw in keywords:
        url = f"https://openapi.naver.com/v1/search/news.json?query={kw}&display=20&sort=sim"
        res = requests.get(url, headers=headers).json()
        
        count = 0 
        if 'items' in res:
            for item in res['items']:
                if count >= 3: break # 키워드당 3개씩만 (새로운 것 위주)
                
                title = item['title'].replace('<b>','').replace('</b>','').replace('&quot;','"')
                
                # [핵심] 이번 실행에서의 중복 + 과거 장부와의 중복 모두 체크
                is_duplicate = False
                for existing in (old_titles + new_titles):
                    if is_similar(title, existing) > 0.4: 
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    entry = f"🔹 {kw}\n- {title}\n- {item['link']}\n\n"
                    if len(current_message) + len(entry) > 3800:
                        messages.append(current_message)
                        current_message = entry
                    else:
                        current_message += entry
                    new_titles.append(title)
                    count += 1
    
    # 2. 새로운 기사가 있을 때만 전송하고 장부에 기록
    if new_titles:
        messages.append(current_message)
        bot = Bot(token=os.environ['TELEGRAM_TOKEN'])
        for msg in messages:
            await bot.send_message(chat_id=os.environ['CHAT_ID'], text=msg)
        
        # 장부에 새로운 제목들 추가 (최근 1000개만 유지)
        updated_history = (new_titles + old_titles)[:1000]
        with open(history_file, "w", encoding="utf-8") as f:
            for t in updated_history:
                f.write(t + "\n")
    else:
        print("새로운 뉴스가 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())
