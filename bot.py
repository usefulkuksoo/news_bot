import os, requests, asyncio, re
from telegram import Bot

# [강화된 유사도 검사] 글자 단위(Character-level) 비교 방식
def is_similar(a, b):
    def clean_for_comparison(text):
        # 1. HTML 태그 및 엔티티 제거
        text = re.sub(r'<.*?>|&\w+;', '', text)
        # 2. [단독], [속보], (종합) 등 대괄호/괄호와 그 안의 내용 삭제
        text = re.sub(r'\[.*?\]|\(.*?\)', '', text)
        # 3. 한글, 영문, 숫자만 남기고 공백까지 싹 제거 (핵심!)
        return re.sub(r'[^가-힣a-zA-Z0-9]', '', text)

    a_clean = clean_for_comparison(a)
    b_clean = clean_for_comparison(b)

    if not a_clean or not b_clean:
        return 0

    # 글자 단위로 셋(set) 생성
    set_a = set(a_clean)
    set_b = set(b_clean)

    # 겹치는 글자 수 계산
    overlap = len(set_a & set_b)
    # 두 제목 중 짧은 쪽 글자 수 대비 겹치는 비율 계산
    # (0.35~0.4 정도면 띄어쓰기나 단어 한두 개 차이는 중복으로 잡아냅니다)
    return overlap / min(len(set_a), len(set_b))

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
                "재개발", "개발행위허가제한", "고속도로", "주민공람","신통기획",
                "지구단위계획"]
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

        if 'items' not in res:
            print(f"[{kw}] 응답 이상: {res}")
            continue

        category_entries = []

        for item in res['items']:
            if len(category_entries) >= 5:
                break

            # 순수 제목 추출 (비교용)
            title = re.sub(r'<.*?>', '', item['title']).replace('&quot;', '"').replace('&amp;', '&')

            # 유사도 검사 기준을 0.35로 설정 (더 깐깐하게 거름)
            is_duplicate = any(
                is_similar(title, existing) > 0.35
                for existing in (old_titles + new_titles)
            )

            if not is_duplicate:
                title_safe = escape_html(title)
                entry = f"📍 {title_safe}\n   🔗 {item['link']}\n"
                category_entries.append(entry)
                new_titles.append(title)

        if category_entries:
            kw_header = f"\n🔹 <b>{escape_html(kw)}</b>\n"
            combined_category_text = kw_header + "\n".join(category_entries) + "\n"

            if len(current_message) + len(combined_category_text) > 3800:
                messages.append(current_message)
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
