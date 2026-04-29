import os
import time
import re
import pickle
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COOKIE_FILE = "threads_cookies.pkl"


# =========================
# Selenium 設定
# =========================
def setup_driver(headless=False):
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--start-maximized")
    options.add_argument("--lang=zh-TW")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    return driver


# =========================
# Cookie 登入功能
# =========================
def save_cookies(driver):
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(driver.get_cookies(), f)


def load_cookies(driver):
    if not os.path.exists(COOKIE_FILE):
        return False

    driver.get("https://www.threads.net/")
    time.sleep(3)

    with open(COOKIE_FILE, "rb") as f:
        cookies = pickle.load(f)

    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
        except:
            pass

    driver.refresh()
    time.sleep(5)
    return True


def login_threads_once():
    driver = setup_driver(headless=False)

    driver.get("https://www.threads.net/")
    time.sleep(5)

    print("請在跳出的 Chrome 視窗手動登入 Threads。")
    print("登入完成後，回到這個終端機按 Enter。")

    input("登入完成後請按 Enter...")

    save_cookies(driver)
    driver.quit()


# =========================
# 文字清理
# =========================
def clean_text(text):
    text = text.strip()
    text = re.sub(r"\s+", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def is_ui_text(text):
    ui_words = [
        "登入", "註冊", "Threads", "Instagram", "Meta",
        "搜尋", "查看更多", "回覆", "轉發", "分享",
        "隱私", "使用條款", "Cookie", "下載應用程式",
        "忘記密碼", "建立帳號", "通知", "首頁",
        "你的個人檔案", "活動", "設定"
    ]

    if text in ui_words:
        return True

    if len(text) < 6:
        return True

    if len(text) > 1000:
        return True

    if text.count("\n") > 18:
        return True

    return False


def is_duplicate_or_subset(text, seen_texts):
    for old in seen_texts[:]:
        if text == old:
            return True

        if text in old and len(text) < len(old) * 0.8:
            return True

        if old in text and len(old) < len(text) * 0.8:
            seen_texts.remove(old)
            return False

    return False


# =========================
# Threads 搜尋
# =========================
def search_threads_by_keyword(keyword, max_posts=10, scroll_times=15, headless=False):
    search_url = f"https://www.threads.net/search?q={keyword}"

    driver = setup_driver(headless=headless)

    has_cookie = load_cookies(driver)

    driver.get(search_url)
    time.sleep(8)

    posts = []
    seen_texts = []

    try:
        for i in range(scroll_times):
            elements = driver.find_elements(
                By.XPATH,
                "//article | //*[@role='article'] | //div[string-length(normalize-space()) > 15]"
            )

            for el in elements:
                try:
                    text = clean_text(el.text)
                except:
                    continue

                if not text:
                    continue

                if keyword not in text:
                    continue

                if is_ui_text(text):
                    continue

                if is_duplicate_or_subset(text, seen_texts):
                    continue

                seen_texts.append(text)

                posts.append({
                    "source": "Threads_Selenium_Login" if has_cookie else "Threads_Selenium_NoLogin",
                    "keyword": keyword,
                    "text": text,
                    "url": search_url
                })

                if len(posts) >= max_posts:
                    break

            if len(posts) >= max_posts:
                break

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

    finally:
        driver.quit()

    return posts[:max_posts]


# =========================
# 規則版 Summary
# =========================
def rule_based_summary(posts):
    texts = [p["text"] for p in posts]
    joined_text = "\n".join(texts)

    disaster_keywords = {
        "淹水": ["淹水", "積水", "水位", "抽水"],
        "停電": ["停電", "斷電", "電力"],
        "道路中斷": ["道路", "封路", "交通", "無法通行", "坍方"],
        "救援需求": ["受困", "救援", "物資", "砂包", "撤離"],
        "土石流": ["土石流", "坍方", "落石"],
        "颱風": ["颱風", "強風", "豪雨", "暴雨"]
    }

    detected_types = []

    for disaster_type, keywords in disaster_keywords.items():
        if any(k in joined_text for k in keywords):
            detected_types.append(disaster_type)

    if not detected_types:
        detected_types = ["未明確判斷"]

    needs = []

    if "砂包" in joined_text:
        needs.append("砂包")
    if "抽水" in joined_text:
        needs.append("抽水設備")
    if "受困" in joined_text or "救援" in joined_text:
        needs.append("救援人力")
    if "物資" in joined_text:
        needs.append("物資支援")
    if "封路" in joined_text or "無法通行" in joined_text:
        needs.append("交通管制")
    if "停電" in joined_text or "斷電" in joined_text:
        needs.append("電力搶修")

    if not needs:
        needs = ["尚未明確偵測"]

    confidence = min(1.0, 0.45 + 0.05 * len(posts))

    return {
        "災害類型": detected_types,
        "摘要": f"系統共擷取 {len(posts)} 筆 Threads 相關貼文。內容可能涉及 {', '.join(detected_types)}，建議進一步比對官方資料、新聞或現場回報。",
        "可能需求": needs,
        "可信度": round(confidence, 2),
        "資料來源": list(set([p["source"] for p in posts])),
        "限制說明": "此結果根據 Threads 公開或登入後可見貼文初步整理，仍需官方資料交叉驗證。"
    }


# =========================
# GPT Summary
# =========================
def gpt_summary(posts):
    if not OPENAI_API_KEY:
        return rule_based_summary(posts)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)

        texts = "\n\n".join(
            [f"{i + 1}. {p['text']}" for i, p in enumerate(posts)]
        )

        prompt = f"""
你是一個防災資訊分析助理。
請根據以下 Threads 公開貼文，整理成災情情報摘要。

請用 JSON 格式輸出，欄位包含：
- 災害類型
- 主要地點
- 摘要
- 可能需求
- 重複事件判斷
- 可信度分數 0 到 1
- 判斷依據
- 限制說明

Threads 貼文如下：
{texts}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是防災資料融合與災情摘要分析專家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        return response.choices[0].message.content

    except Exception as e:
        return {
            "錯誤": str(e),
            "fallback": rule_based_summary(posts)
        }


# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="Threads 災情 AI 摘要", layout="wide")

st.title("🌐 Threads 災情貼文搜尋 + AI 統整 MVP")

st.write("第一次使用請先登入 Threads，之後系統會儲存 cookie，下次搜尋會自動使用登入狀態。")

st.divider()

if st.button("第一次使用：登入 Threads 並儲存狀態"):
    with st.spinner("請在跳出的 Chrome 視窗登入 Threads，登入後回到終端機按 Enter。"):
        login_threads_once()

    st.success("Threads 登入狀態已儲存，下次搜尋會自動使用登入狀態。")

if os.path.exists(COOKIE_FILE):
    st.success("目前已偵測到 Threads 登入 cookie。")
else:
    st.warning("目前尚未偵測到 Threads 登入 cookie，搜尋結果可能較少。")

st.divider()

keyword = st.text_input("請輸入搜尋關鍵字", value="颱風")
max_posts = st.number_input("顯示貼文數量", min_value=1, max_value=50, value=10)

headless = st.checkbox("背景執行瀏覽器 headless", value=False)
use_gpt = st.checkbox("使用 GPT 做摘要，需要 OPENAI_API_KEY", value=False)

if st.button("開始搜尋並統整"):
    if not keyword.strip():
        st.error("請輸入關鍵字")
    else:
        with st.spinner("正在搜尋 Threads 貼文..."):
            posts = search_threads_by_keyword(
                keyword=keyword.strip(),
                max_posts=max_posts,
                scroll_times=15,
                headless=headless
            )

        if not posts:
            st.warning("沒有抓到貼文。可能原因：Threads 搜尋頁限制、cookie 失效、需要重新登入、公開資料不足，或頁面結構改變。")
        else:
            st.success(f"成功取得 {len(posts)} 筆貼文")

            df = pd.DataFrame(posts)

            st.subheader("📌 搜尋到的貼文")
            st.dataframe(df, use_container_width=True)

            safe_keyword = re.sub(r'[\\/:*?"<>|]', "_", keyword.strip())

            csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

            st.download_button(
                label="下載 CSV",
                data=csv,
                file_name=f"threads_{safe_keyword}.csv",
                mime="text/csv"
            )

            st.subheader("🧠 AI 統整結果")

            with st.spinner("AI 正在整理摘要..."):
                if use_gpt:
                    result = gpt_summary(posts)
                else:
                    result = rule_based_summary(posts)

            st.write(result)
