import os
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")


def test_threads_api():
    """測試 Threads Access Token 是否有效"""
    if not ACCESS_TOKEN:
        print("❌ 找不到 THREADS_ACCESS_TOKEN，請先在 .env 設定")
        return False

    url = "https://graph.threads.net/v1.0/me"

    params = {
        "fields": "id,username",
        "access_token": ACCESS_TOKEN
    }

    try:
        res = requests.get(url, params=params, timeout=20)

        print("\n========== Token 測試 ==========")
        print("Status Code:", res.status_code)
        print("Response:", res.text)

        if res.status_code == 200:
            print("✅ Token 有效，可以連到 Threads API")
            return True
        else:
            print("❌ Token 無效或權限不足")
            return False

    except requests.exceptions.RequestException as e:
        print("❌ Token 測試時發生連線錯誤")
        print(e)
        return False


def check_keyword_search_permission():
    """
    間接檢查 keyword_search 是否可用。
    注意：Threads API 沒有提供直接檢查 keyword_search 權限的端點。
    因此只能用測試查詢推估。
    """
    if not ACCESS_TOKEN:
        return False

    url = "https://graph.threads.net/v1.0/keyword_search"

    params = {
        "q": "test",
        "limit": 1,
        "fields": "id,text,permalink,timestamp,username",
        "access_token": ACCESS_TOKEN
    }

    try:
        res = requests.get(url, params=params, timeout=20)

        print("\n========== keyword_search 權限檢查 ==========")
        print("Status Code:", res.status_code)
        print("Response:", res.text)

        if res.status_code != 200:
            print("❌ keyword_search API 錯誤，可能是 endpoint、token 或權限問題")
            return False

        data = res.json()

        if "data" not in data:
            print("❌ 回應格式異常，沒有 data 欄位")
            return False

        if len(data["data"]) == 0:
            print("⚠️ API 有回應但資料為空，可能沒有 keyword_search 權限或搜尋限制")
            return False

        print("✅ keyword_search 可用")
        return True

    except requests.exceptions.RequestException as e:
        print("❌ keyword_search 權限檢查時發生連線錯誤")
        print(e)
        return False


def search_threads_api(keyword, limit=10):
    """使用 Threads Keyword Search API 搜尋貼文"""
    url = "https://graph.threads.net/v1.0/keyword_search"

    params = {
        "q": keyword,
        "limit": limit,
        "fields": "id,text,permalink,timestamp,username",
        "access_token": ACCESS_TOKEN
    }

    try:
        res = requests.get(url, params=params, timeout=20)

        print("\n========== Keyword Search 測試 ==========")
        print("Status Code:", res.status_code)
        print("Raw Response:")
        print(res.text)

        if res.status_code != 200:
            print("\n❌ keyword_search API 回應錯誤")
            return []

        data = res.json()
        posts = data.get("data", [])

        if len(posts) == 0:
            print("\n⚠️ API 有成功回應，但沒有取得貼文")
            print("可能原因：")
            print("1. keyword_search 權限尚未開通")
            print("2. 關鍵字沒有公開貼文結果")
            print("3. Threads API 搜尋功能限制")
            return []

        print(f"\n✅ 成功取得 {len(posts)} 筆 Threads 貼文")

        for post in posts:
            post["source"] = "Threads_API"

        return posts

    except requests.exceptions.RequestException as e:
        print("❌ 搜尋 Threads 時發生連線錯誤")
        print(e)
        return []


def search_threads_mock(keyword, limit=10):
    """當 Threads API 抓不到資料時，自動產生模擬資料"""
    print("\n========== 使用 Mock Threads 資料 ==========")
    print("⚠️ 因 API 無資料或權限限制，系統自動切換為模擬 Threads 貼文")

    mock_texts = [
        f"{keyword} 附近道路積水，車輛無法通行",
        f"{keyword} 一帶居民回報水位持續上升",
        f"看到有人說 {keyword} 附近需要砂包和抽水設備",
        f"{keyword} 周邊交通受阻，建議改道",
        f"{keyword} 低窪地區疑似淹水，現場狀況不明",
        f"{keyword} 有民眾表示地下道積水",
        f"{keyword} 附近需要志工協助搬運物資",
        f"{keyword} 災情資訊待確認，請勿靠近危險區域",
        f"{keyword} 周邊道路疑似封閉",
        f"{keyword} 有人回報停電與通訊不穩"
    ]

    posts = []

    for i, text in enumerate(mock_texts[:limit], start=1):
        posts.append({
            "id": f"mock_{i}",
            "text": text,
            "permalink": f"https://www.threads.net/mock/{i}",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "username": f"mock_user_{i}",
            "source": "Threads_Mock"
        })

    print(f"✅ 已產生 {len(posts)} 筆 mock 貼文")
    return posts


def search_threads(keyword, limit=10, use_mock_if_empty=True):
    """
    主搜尋函式：
    1. 優先使用 Threads API
    2. 如果 API 沒資料，且 use_mock_if_empty=True，就自動切換 mock
    """
    posts = []

    if ACCESS_TOKEN:
        posts = search_threads_api(keyword, limit=limit)
    else:
        print("⚠️ 沒有 THREADS_ACCESS_TOKEN，直接使用 mock 資料")

    if not posts and use_mock_if_empty:
        posts = search_threads_mock(keyword, limit=limit)

    return posts


def save_posts_to_csv(posts, keyword):
    """儲存搜尋結果為 CSV"""
    if not posts:
        print("❌ 沒有資料可以儲存")
        return None

    df = pd.DataFrame(posts)

    safe_keyword = (
        keyword.replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )

    output_file = f"threads_{safe_keyword}.csv"
    df.to_csv(output_file, index=False, encoding="utf-8-sig")

    print("\n========== 搜尋結果 ==========")
    print(df)
    print(f"\n✅ 已儲存：{output_file}")

    return output_file


if __name__ == "__main__":
    print("========== Threads 搜尋工具 ==========")

    token_ok = test_threads_api()

    if token_ok:
        keyword_permission = check_keyword_search_permission()

        if not keyword_permission:
            print("\n🚨 系統判斷：keyword_search 目前可能不可用")
            print("➡️ 後續搜尋若無資料，會自動切換成 mock 資料")
    else:
        print("\n🚨 Token 無效或不存在")
        print("➡️ 系統會直接使用 mock 資料")

    keyword = input("\n請輸入 Threads 搜尋關鍵字：").strip()

    if not keyword:
        print("❌ 關鍵字不可為空")
    else:
        posts = search_threads(keyword, limit=10, use_mock_if_empty=True)
        save_posts_to_csv(posts, keyword)