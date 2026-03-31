import os, requests, asyncio
from telegram import Bot
from difflib import SequenceMatcher

def is_similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

async def main():
    # 키워드 설정
    keywords = ["부동산 경매", "지구단위계획", "용도지역 변경", "역세권 개발", "주민공람", "도시개발", "재개발", "고속도로", " 개발행위허가제한지역"]
    
    headers = {
        "X-Naver-Client-Id": os.environ['NAVER_ID'], 
        "X-Naver-Client-Secret": os.environ['NAVER_SECRET']
    }
    
    added_titles = []
    messages = [] # 메시지들을 담을 리스트
    current_message = "📢 오늘의 부동산 미래 가치 선점 뉴스 (중복 제거)\n\n"

    for kw in keywords:
        url = f"https://openapi.naver.com/v1/search/news.json?query={kw}&display=10&sort=sim"
        res = requests.get(url, headers=headers).json()
        
        count = 0 
        if 'items' in res:
            for item in res['items']:
                if count >= 5: break
                
                # 제목 깔끔하게 정리 (태그 및 특수기호 변환)
                title = item['title'].replace('<b>','').replace('</b>','').replace('&quot;','"').replace('&amp;','&').replace('&lt;','<').replace('&gt;','>')
                
                duplicate = False
                for existing_title in added_titles:
                    if is_similar(title, existing_title) > 0.4: 
                        duplicate = True
                        break
                
                if not duplicate:
                    entry = f"🔹 {kw}\n- {title}\n- {item['link']}\n\n"
                    
                    # 텔레그램 글자수 제한(4000자) 체크
                    if len(current_message) + len(entry) > 3800:
                        messages.append(current_message)
                        current_message = entry
                    else:
                        current_message += entry
                        
                    added_titles.append(title)
                    count += 1
    
    messages.append(current_message) # 마지막 메시지 추가

    bot = Bot(token=os.environ['TELEGRAM_TOKEN'])
    
    # 생성된 모든 메시지 순차 전송
    for msg in messages:
        if msg.strip(): # 비어있지 않은 경우에만 전송
            await bot.send_message(chat_id=os.environ['CHAT_ID'], text=msg)

if __name__ == "__main__":
    asyncio.run(main())
