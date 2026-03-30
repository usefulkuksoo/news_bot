import os, requests, asyncio
from telegram import Bot
from difflib import SequenceMatcher # 제목 유사도를 계산하는 도구

# 두 문장이 얼마나 비슷한지 측정하는 함수 (0~1 사이 값)
def is_similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

async def main():
    keywords = ["부동산 경매", "지구단위계획", "용도지역 변경", "역세권 개발","주민공람"]
    news_text = "📢 오늘의 부동산 미래 가치 선점 뉴스 (중복 제거)\n\n"
    
    headers = {
        "X-Naver-Client-Id": os.environ['NAVER_ID'], 
        "X-Naver-Client-Secret": os.environ['NAVER_SECRET']
    }
    
    # 이미 추가된 기사 제목들을 저장하는 리스트
    added_titles = []

    for kw in keywords:
        # 필터링을 위해 넉넉하게 20개를 가져옵니다.
        url = f"https://openapi.naver.com/v1/search/news.json?query={kw}&display=20&sort=sim"
        res = requests.get(url, headers=headers).json()
        
        count = 0 # 키워드당 채울 기사 개수 카운트
        if 'items' in res:
            for item in res['items']:
                if count >= 5: # 5개를 다 채웠으면 다음 키워드로
                    break
                
                # HTML 태그 제거 및 특수문자 정리
                title = item['title'].replace('<b>','').replace('</b>','').replace('&quot;','"')
                
                # [핵심] 기존에 담긴 기사들과 유사도 비교
                duplicate = False
                for existing_title in added_titles:
                    if is_similar(title, existing_title) > 0.7: # 70% 이상 비슷하면 중복으로 간주
                        duplicate = True
                        break
                
                if not duplicate:
                    news_text += f"🔹 {kw}\n- {title}\n- {item['link']}\n\n"
                    added_titles.append(title) # 비교를 위해 리스트에 저장
                    count += 1

    bot = Bot(token=os.environ['TELEGRAM_TOKEN'])
    await bot.send_message(chat_id=os.environ['CHAT_ID'], text=news_text)

if __name__ == "__main__":
    asyncio.run(main())
