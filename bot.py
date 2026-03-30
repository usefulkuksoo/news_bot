import os, requests, asyncio
from telegram import Bot

async def main():
    # 1. 뉴스 검색 키워드 (원하는 대로 수정 가능합니다)
    keywords = ["부동산 경매", "지구단위계획", "용도지역 변경", "역세권 개발"]
    news_text = "📢 오늘의 부동산 미래 가치 선점 뉴스\n\n"
    
    # GitHub Secrets에 저장한 열쇠들을 불러옵니다
    headers = {
        "X-Naver-Client-Id": os.environ['NAVER_ID'], 
        "X-Naver-Client-Secret": os.environ['NAVER_SECRET']
    }
    
    for kw in keywords:
        # 네이버 뉴스에서 키워드당 최근 뉴스 3개씩 가져오기
        url = f"https://openapi.naver.com/v1/search/news.json?query={kw}&display=3&sort=sim"
        res = requests.get(url, headers=headers).json()
        
        if 'items' in res:
            for item in res['items']:
                title = item['title'].replace('<b>','').replace('</b>','').replace('&quot;','"')
                news_text += f"🔹 {kw}\n- {title}\n- {item['link']}\n\n"

    # 2. 텔레그램으로 메시지 전송
    bot = Bot(token=os.environ['TELEGRAM_TOKEN'])
    await bot.send_message(chat_id=os.environ['CHAT_ID'], text=news_text)

if __name__ == "__main__":
    asyncio.run(main())
