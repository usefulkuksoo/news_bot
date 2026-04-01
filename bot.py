import os, requests, asyncio, re
from telegram import Bot

def is_similar(a, b):
    def clean(text):
        text = re.sub(r'<.*?>|&\w+;', '', text)
        return re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text).split()
    a_words, b_words = set(clean(a)), set(clean(b))
    if not a_words or not b_words:
        return 0
    return len(a_words & b_words) / min(len(a_words), len(b_words))

def escape_html(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

async def main():
    history_file = "seen_news.txt"
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            old_titles = [line.strip() for line in f if line.strip()]
    else:
        old_titles = []

    keywords = ["부동산 경매", "지구단위계획", "용도지역 변경", "역세권 개발",
                "재개발", "개발행위허가제한", "고속도로", "주민공람"]
    headers = {
        "X-Naver-Client-Id": os.environ['NAVER_ID'],
        "X-Naver-Client-Secret": os.environ['NAVER_SECRET']
    }

    new_titles = []
    messages = []
    current_message = "📢 오늘의 부동산 뉴스 브리핑\n"

    for kw in keywords:
        url = f"https://openapi.naver.com/v1/search/news.json?query={kw}&display=20&sort=sim"

        try:
            res = requests.get(url, headers=headers, timeout=10).json()
        except Exception as e:
            print(f"[{kw}] API 요청 실패: {e}")
            continue

        # ✅ 에러 응답 감지
        if 'items' not in res:
            print(f"[{kw}] 응답 이상: {res}")
            continue

        category_entries = []

        for item in res['items']:
            if len(category_entries) >= 5:
                break

            title = re.sub(r'<.*?>', '', item['title']).replace('&quot;', '"').replace('&amp;', '&')

            is_duplicate = any(
                is_similar(title, existing) > 0.4
                for existing in (old_titles + new_titles)
            )

            if not is_duplicate:
                # ✅ HTML 이스케이프 처리
                title_safe = escape_html(title)
                entry = f"📍 {title_safe}\n   🔗 {item['link']}\n"
                category_entries.append(entry)
                new_titles.append(title)

        if category_entries:
            kw_header = f"\n🔹 <b>{escape_html(kw)}</b>\n"
            combined_category_text = kw_header + "\n".join(category_entries) + "\n"

            if len(current_message) + len(combined_category_text) > 3800:
                messages.append(current_message)
                # ✅ 분할 시 헤더 유지
                current_message = f"📢 (계속)\n{combined_category_text}"
            else:
                current_message += combined_category_text

    if new_titles:
        messages.append(current_message)
        bot = Bot(token=os.environ['TELEGRAM_TOKEN'])
        for msg in messages:
            await bot.send_message(chat_id=os.environ['CHAT_ID'], text=msg, parse_mode='HTML')

        updated_history = list(dict.fromkeys(
            t.strip() for t in (new_titles + old_titles) if t.strip()
        ))[:1000]
        with open(history_file, "w", encoding="utf-8") as f:
            for t in updated_history:
                f.write(t + "\n")
    else:
        print("새로운 뉴스가 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())
