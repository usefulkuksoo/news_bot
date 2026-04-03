import os
import re
import asyncio
import requests
from bs4 import BeautifulSoup
from telegram import Bot

# -------------------------------------------------
# 1️⃣ 중복 필터링 함수
# -------------------------------------------------
def is_similar(a: str, b: str) -> float:
    def clean(text: str) -> str:
        text = re.sub(r'<.*?>|&\w+;', '', text)          # HTML·엔티티 제거
        text = re.sub(r'$.*?$|$.*?$|\{.*?\}', '', text)  # 괄호 내용 제거
        return re.sub(r'[^가-힣a-zA-Z0-9]', '', text)     # 한·영·숫자만 남김
    a_c, b_c = clean(a), clean(b)
    if not a_c or not b_c:
        return 0.0
    set_a, set_b = set(a_c), set(b_c)
    return len(set_a & set_b) / min(len(set_a), len(set_b))


def escape_html(txt: str) -> str:
    return txt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# -------------------------------------------------
# 2️⃣ 지자체 고시·공고 수집 (김포·화성·양주·남양주)
# -------------------------------------------------
def get_combined_city_notices() -> list[dict]:
    target_keywords = [
        "지구단위계획", "지형도면", "용도지역", "도시관리계획", "변경",
        "주민공람", "공람공고", "보상계획", "손실보상", "토지보상",
        "실시계획", "인가", "개발행위", "구역지정", "도로", "수용"
    ]

    # ← 여기서 **실제 URL·베이스·CSS 셀렉터** 로 교체하세요
    cities = [
        {
            "name": "김포시",
            "url": "https://www.gimpo.go.kr/portal/selectBbsNttList.do?bbsNo=155&key=1138",
            "base_url": "https://www.gimpo.go.kr",
            "selector": "table.board-list tbody tr"
        },
        {
            "name": "화성시",
            "url": "https://www.hscity.go.kr/www/user/bbs/BD_selectBbsList.do?q_bbsCode=1019",
            "base_url": "https://www.hscity.go.kr",
            "selector": "table.table-list tbody tr"
        },
        {
            "name": "양주시",
            "url": "https://www.yangju.go.kr/www/selectBbsNttList.do?bbsNo=54&key=361",
            "base_url": "https://www.yangju.go.kr",
            "selector": "table.bbs-list tbody tr"
        },
        {
            "name": "남양주시",
            "url": "https://www.namyangju.go.kr/main/notice/1",
            "base_url": "https://www.namyangju.go.kr",
            "selector": "table.board-list tbody tr"
        }
    ]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    notices = []
    for city in cities:
        try:
            resp = requests.get(city["url"], headers=headers, timeout=15)
            resp.encoding = resp.apparent_encoding   # EUC‑KR 등 자동 감지
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select(city["selector"])

            for row in rows:
                title_elem = (
                    row.select_one("td.left a")
                    or row.select_one("td.subject a")
                    or row.select_one("a")
                )
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                matched = [kw for kw in target_keywords if kw in title]
                if not matched:
                    continue
                link = title_elem.get("href", "")
                full_link = (
                    city["base_url"] + link
                    if link.startswith("/")
                    else link
                )
                notices.append(
                    {
                        "city": city["name"],
                        "tag": f"#{matched[0]}",
                        "title": title,
                        "link": full_link,
                    }
                )
        except Exception as e:
            print(f"[⚠️] {city['name']} 고시 수집 실패: {e}")

    return notices


# -------------------------------------------------
# 3️⃣ 메인 실행 로직 (비동기)
# -------------------------------------------------
async def main():
    # ---- 히스토리(이미 본 기사·공고) 로드 ----
    history_file = "seen_news.txt"
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            old_titles = [line.strip() for line in f if line.strip()]
    else:
        old_titles = []

    # ---- 네이버 뉴스 키워드 리스트 ----
    keywords = [
        "부동산 경매", "지구단위계획", "용도지역 변경", "재개발", "고속도로", "주민공람",
        "경기일보 부동산", "경인일보 부동산", "중부일보 개발", "경기신문 신도시",
        "김포시 개발", "화성시 토지", "양주시 정비구역", "남양주시 보상",
    ]

    naver_headers = {
        "X-Naver-Client-Id": os.getenv("NAVER_ID", ""),
        "X-Naver-Client-Secret": os.getenv("NAVER_SECRET", ""),
    }

    new_titles = []   # 이번 실행에서 새로 발견한 제목
    messages = []     # 텔레그램에 보낼 메시지 블록 리스트
    current_msg = "📢 <b>오늘의 부동산 & 지역 뉴스 브리핑</b>\n"

    # ------------------- 파트 1 : 네이버 뉴스 -------------------
    for kw in keywords:
        api_url = (
            f"https://openapi.naver.com/v1/search/news?"
            f"query={requests.utils.quote(kw)}&display=15&sort=sim"
        )
        try:
            data = requests.get(api_url, headers=naver_headers, timeout=10).json()
            items = data.get("items", [])
        except Exception as e:
            print(f"[⚠️] 네이버 API 오류 ({kw}): {e}")
            continue

        for item in items[:5]:   # 최대 5개씩
            raw_title = re.sub(r'<.*?>', '', item.get("title", ""))
            title = (
                raw_title.replace("&quot;", '"')
                .replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
            )
            # 중복·유사도 검사
            if any(is_similar(title, old) > 0.35 for old in (old_titles + new_titles)):
                continue

            entry = f"📍 {escape_html(title)}\n   🔗 {item.get('link')}\n"
            current_msg += entry
            new_titles.append(title)

    # ------------------- 파트 2 : 지자체 고시 -------------------
    city_notices = get_combined_city_notices()
    if city_notices:
        current_msg += "\n🏛️ <b>지자체 핵심 고시 (김포·화성·양주·남양주)</b>\n"
        current_msg += "━━━━━━━━━━━━━━━━━━\n"
        cur_city = ""
        for n in city_notices:
            # 고시도 히스토리와 비교해 중복 방지
            if any(is_similar(n["title"], old) > 0.35 for old in (old_titles + new_titles)):
                continue
            if cur_city != n["city"]:
                current_msg += f"\n📍 <b>{n['city']}</b>\n"
                cur_city = n["city"]
            current_msg += (
                f"• {n['tag']} {escape_html(n['title'])}\n"
                f"  🔗 <a href='{n['link']}'>공고 보기</a>\n"
            )
            new_titles.append(n["title"])

    # ------------------- 파트 3 : 텔레그램 전송 -------------------
    if new_titles:          # 새 소식이 있으면 전송
        bot = Bot(token=os.getenv("TELEGRAM_TOKEN", ""))
        chat_id = os.getenv("CHAT_ID", "")
        await bot.send_message(
            chat_id=chat_id,
            text=current_msg,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        # 히스토리 파일 업데이트 (최신 1000개까지만 보관)
        combined = list(dict.fromkeys(new_titles + old_titles))[:1000]
        with open(history_file, "w", encoding="utf-8") as f:
            for line in combined:
                f.write(line + "\n")
    else:
        print("[ℹ️] 오늘은 새로운 뉴스·고시가 없습니다.")


if __name__ == "__main__":
    asyncio.run(main())
