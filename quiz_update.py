import os
import base64
import requests
import html
from bs4 import BeautifulSoup, NavigableString, Tag

# ================= CONFIG =================
WP_URL = "https://blog.mexc.fm/wp-json/wp/v2/posts"
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
POST_ID = 323083  # <-- đổi thành ID bài Dropee cần update
CHECK_ANSWER = "Partnershipppp"  # <-- đáp án cũ dùng để đối chiếu

SOURCE1_URL = "https://miningcombo.com/dropee/"
SOURCE2_URL = "https://www.quiknotes.in/dropee-question-of-the-day-12-march-2026/"

# ================= HELPERS =================
def normalize(text: str) -> str:
    return (
        html.unescape(text or "")
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("–", "-")
        .replace("—", "-")
        .replace("\xa0", " ")
        .strip()
    )

def get_auth_headers():
    print("WP_USERNAME exists:", bool(WP_USERNAME))
    print("WP_APP_PASSWORD exists:", bool(WP_APP_PASSWORD))
    if WP_USERNAME:
        print("WP_USERNAME preview:", WP_USERNAME[:3] + "***")
    if WP_APP_PASSWORD:
        print("WP_APP_PASSWORD length:", len(WP_APP_PASSWORD))

    token = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    if not WP_USERNAME or not WP_APP_PASSWORD:
        raise RuntimeError("Thiếu WP_USERNAME hoặc WP_APP_PASSWORD trong biến môi trường")

    token = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def test_wp_auth():
    headers = get_auth_headers()

    for test_url in [
        "https://blog.mexc.fm/wp-json/",
        "https://blog.mexc.fm/wp-json/wp/v2/users/me",
        f"{WP_URL}/{POST_ID}",
    ]:
        r = requests.get(test_url, headers=headers, timeout=20)
        print("\nTEST URL:", test_url)
        print("STATUS:", r.status_code)
        print("BODY:", r.text[:800])

def next_tag_sibling(node: Tag):
    cur = node.next_sibling
    while cur:
        if isinstance(cur, Tag):
            return cur
        cur = cur.next_sibling
    return None

# ================ SCRAPE SITE 1 ================
def scrape_dropee_site1():
    url = SOURCE1_URL
    print(f"[+] Scraping Dropee from {url}")
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    target_h2 = None
    for h2 in soup.find_all("h2"):
        if "dropee question of the day" in normalize(h2.get_text(" ", strip=True)):
            target_h2 = h2
            break

    if not target_h2:
        raise RuntimeError("Không tìm thấy H2 chứa 'Dropee Question Of The Day' ở site1")

    p1 = next_tag_sibling(target_h2)
    p2 = next_tag_sibling(p1) if p1 else None

    if not p1 or p1.name != "p":
        raise RuntimeError("Không tìm thấy thẻ p thứ 1 ngay sau H2 ở site1")
    if not p2 or p2.name != "p":
        raise RuntimeError("Không tìm thấy thẻ p thứ 2 ngay sau H2 ở site1")

    q_text = p1.get_text(" ", strip=True)
    a_text = p2.get_text(" ", strip=True)

    question = q_text.replace("Question:", "", 1).strip()
    answer = a_text.replace("Answer:", "", 1).strip()

    print("[+] Scraped question and answer (site1)")
    print("   Q:", question)
    print("   A:", answer)
    return question, answer

# ================ SCRAPE SITE 2 ================
def scrape_dropee_site2():
    url = SOURCE2_URL
    print(f"[+] Scraping Dropee from {url}")
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    target_h3 = None
    for h3 in soup.find_all("h3"):
        if "here are dropee question of the day" in normalize(h3.get_text(" ", strip=True)):
            target_h3 = h3
            break

    if not target_h3:
        raise RuntimeError("Không tìm thấy H3 chứa 'Here are Dropee Question of the Day' ở site2")

    ul = next_tag_sibling(target_h3)
    if not ul or ul.name != "ul":
        raise RuntimeError("Không tìm thấy UL ngay sau H3 ở site2")

    lis = ul.find_all("li", recursive=False)
    if len(lis) < 2:
        raise RuntimeError("Không tìm thấy đủ 2 thẻ li trong UL ở site2")

    q_text = lis[0].get_text(" ", strip=True)
    a_text = lis[1].get_text(" ", strip=True)

    question = q_text.replace("Today's Question:", "", 1).replace("Today’s Question:", "", 1).strip()
    answer = a_text.replace("Answer:", "", 1).strip()

    print("[+] Scraped question and answer (site2)")
    print("   Q:", question)
    print("   A:", answer)
    return question, answer

# ================ UPDATE POST ================
def update_dropee_post(question, answer):
    headers = get_auth_headers()
    url = f"{WP_URL}/{POST_ID}"

    # 1) Fetch current post
    response = requests.get(url, headers=headers, timeout=20)
    print("🔎 Fetch status:", response.status_code)
    if response.status_code != 200:
        print("❌ Không lấy được post:", response.text[:500])
        return

    post = response.json()
    if "content" not in post or "rendered" not in post["content"]:
        print("❌ Không thấy content.rendered:", post)
        return

    old_content = post["content"]["rendered"]
    print("✍️ Lấy content.rendered, độ dài:", len(old_content))

    soup = BeautifulSoup(old_content, "html.parser")

    # 2) Tìm H2 mục tiêu
    target_h2 = None
    for h2 in soup.find_all("h2"):
        if "today's dropee question of the day for" in normalize(h2.get_text(" ", strip=True)) \
           or "today’s dropee question of the day for" in normalize(h2.get_text(" ", strip=True)):
            target_h2 = h2
            break

    if not target_h2:
        print("❌ Không tìm thấy H2 mục tiêu trong bài MEXC")
        print("Rendered snippet:", old_content[:4000])
        return

    # 3) Lấy p thứ 1, 2, 3 sau H2
    p_tags = []
    node = target_h2.next_sibling
    while node and len(p_tags) < 3:
        if isinstance(node, Tag) and node.name == "p":
            p_tags.append(node)
        node = node.next_sibling

    if len(p_tags) < 3:
        print("❌ Không tìm thấy đủ 3 thẻ p sau H2 mục tiêu")
        return

    p1, p2, p3 = p_tags[0], p_tags[1], p_tags[2]

    # 4) Ghi nội dung vào p thứ 2 và p thứ 3, không xóa/sửa cấu trúc p hiện tại
    # p2 format:
    # <p><strong>Today’s</strong> <strong>Dropee Question of the Day</strong> <strong>for March 10: </strong>What ...?</p>
    strongs_p2 = p2.find_all("strong")
    if len(strongs_p2) >= 3:
        p2.clear()
        s1 = soup.new_tag("strong")
        s1.string = "Today’s"
        s2 = soup.new_tag("strong")
        s2.string = "Dropee Question of the Day"
        s3 = soup.new_tag("strong")
        old_label = strongs_p2[2].get_text(" ", strip=True)
        s3.string = old_label if old_label else "for today:"

        p2.append(s1)
        p2.append(" ")
        p2.append(s2)
        p2.append(" ")
        p2.append(s3)
        p2.append(question)
    else:
        # fallback nếu p2 không đúng format strong như mong đợi
        p2.clear()
        s1 = soup.new_tag("strong")
        s1.string = "Today’s"
        s2 = soup.new_tag("strong")
        s2.string = "Dropee Question of the Day"
        s3 = soup.new_tag("strong")
        s3.string = "for today: "
        p2.append(s1)
        p2.append(" ")
        p2.append(s2)
        p2.append(" ")
        p2.append(s3)
        p2.append(question)

    # p3 format:
    # <p><strong>The correct answer for today’s Dropee question is:</strong> Team</p>
    strong_p3 = p3.find("strong")
    label_p3 = strong_p3.get_text(" ", strip=True) if strong_p3 else "The correct answer for today’s Dropee question is:"
    p3.clear()
    s_ans = soup.new_tag("strong")
    s_ans.string = label_p3
    p3.append(s_ans)
    p3.append(" ")
    p3.append(answer)

    new_content = str(soup)
    print("[+] New content length:", len(new_content))

    # 5) Update post
    payload = {
        "content": new_content,
        "status": "publish"
    }

    update = requests.post(url, headers=headers, json=payload, timeout=20)
    print("🚀 Update status:", update.status_code)
    print("📄 Update response:", update.text[:500])

    if update.status_code == 200:
        print("✅ Post updated & published thành công!")
    else:
        print("❌ Error khi update")

# ================ MAIN =================
if __name__ == "__main__":
    try:
        q1, a1 = scrape_dropee_site1()

        test_wp_auth()

        if a1.strip() != CHECK_ANSWER.strip():
            print("✅ Site1 answer khác CHECK_ANSWER -> Update ngay")
            update_dropee_post(q1, a1)
        else:
            print("⚠️ Site1 answer trùng CHECK_ANSWER -> Thử site2")
            try:
                q2, a2 = scrape_dropee_site2()
                if a2.strip() != CHECK_ANSWER.strip():
                    print("✅ Site2 answer khác CHECK_ANSWER -> Update")
                    update_dropee_post(q2, a2)
                else:
                    print("⚠️ Site2 answer cũng trùng CHECK_ANSWER -> Không update")
            except Exception as e:
                print("❌ Lỗi khi scrape site2:", e)

    except Exception as e:
        print("❌ Lỗi khi scrape site1:", e)
