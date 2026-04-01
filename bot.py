import os, requests, asyncio, re
from telegram import Bot

def is_similar(a, b):
    def clean(text):
        text = re.sub(r'\[.*?\]|\(.*?\)', '', text)
        return re.sub(r'[^가-힣a-zA-Z0-9]', '', text)
    a_clean, b_clean = clean(a), clean(b)
    set_a, set_b = set(a_clean), set(b_clean)
    if not set_a or not set_b: return 0
    return len(set_a & set_b) / min(len(set_a), len(set_b))

async def main():
    history_file = "seen_news.txt"
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            old_titles = [line.strip() for line in f.readlines()]
    else:
        old_titles = []

    # 키워드 리스트 (오타 수정 완료)
    keywords = ["부동산 경매", "지구단위계획", "용도지역 변경", "역세권 개발", "재개발", "개발행위허가제한", "고속도로", "주민공람"]
    headers = {
        "X-Naver-Client-Id": os.environ['NAVER_ID'], 
        "X-Naver-Client-Secret": os.environ['NAVER_SECRET']
    }
    
    new_titles = []
    messages = []
    current_message = f"📢 오늘의 부동산 뉴스 브리핑\n"

    for kw in keywords:
        url = f"https://openapi.naver.com/v1/search/news.json?query={kw}&display=20&sort=sim"
        res = requests.get(url, headers=headers).json()
        
        category_entries = []
        
        if 'items' in res:
            for item in res['items']:
                # [여기!] 숫자를 5로 바꾸면 카테고리당 5개씩 가져옵니다.
                if len(category_entries) >= 5: break 
                
                title = item['title'].replace('<b>','').replace('</b>','').replace('&quot;','"')
                
                is_duplicate = False
                for existing in (old_titles + new_titles):
                    if is_similar(title, existing) > 0.4: 
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    # 가독성을 위해 기사 사이에 공백을 살짝 주었습니다.
                    entry = f"📍 {title}\n   🔗 {item['link']}\n"
                    category_entries.append(entry)
                    new_titles.append(title)

        if category_entries:
            kw_header = f"\n🔹 **{kw}**\n"
            combined_category_text = kw_header + "\n".join(category_entries) + "\n"
            
            if len(current_message) + len(combined_category_text) > 3800:
                messages.append(current_message)
                current_message = combined_category_text
            else:
                current_message += combined_category_text
    
    if new_titles:
        messages.append(current_message)
        bot = Bot(token=os.environ['TELEGRAM_TOKEN'])
        for msg in messages:
            await bot.send_message(chat_id=os.environ['CHAT_ID'], text=msg, parse_mode='Markdown')
        
        updated_history = (new_titles + old_titles)[:1000]
        with open(history_file, "w", encoding="utf-8") as f:
            for t in updated_history:
                f.write(t + "\n")
    else:
        print("새로운 뉴스가 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())
