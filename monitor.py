import hashlib
import json
import os
import urllib.parse
import urllib.request
from playwright.sync_api import sync_playwright

BARK_KEY = os.getenv("BARK_KEY", "").strip()
SERVERCHAN_KEY = os.getenv("SERVERCHAN_KEY", "").strip()
STATE_FILE = "monitor_state.json"

# 聚焦 11月下旬最核心的 2 个高价值目标
TARGETS = [
    {
        "name": "中央巴士-札幌國際滑雪場套票",
        "url": "https://teikan.chuo-bus.co.jp/course/16756",
        "keywords": ["予約", "空席", "申込", "2026"]
    },
    {
        "name": "盤溪滑雪場-SAJ新手大班課與套票",
        "url": "https://www.bankei.co.jp/school/",
        "keywords": ["予約", "受付", "レッスン", "2026"]
    },
    {
        "name": "手稻滑雪場-Webket電子雪票",
        "url": "https://webket.jp/pc/ticket/index?fc=00368&ac=8001",
        "keywords": ["購入", "チケット", "リフト", "初級"]
    }
]


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_notification(title: str, body: str, target_url: str):
    sent = False
    if BARK_KEY:
        t_enc = urllib.parse.quote(title)
        b_enc = urllib.parse.quote(body)
        u_enc = urllib.parse.quote(target_url)
        api = f"https://api.day.app/{BARK_KEY}/{t_enc}/{b_enc}?url={u_enc}&group=Hokkaido2026"
        try:
            urllib.request.urlopen(api, timeout=10)
            print(f"[Bark] 推送成功: {title}")
            sent = True
        except Exception as e:
            print(f"[Bark] 推送失败: {e}")

    if SERVERCHAN_KEY:
        api = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
        data = urllib.parse.urlencode({
            "title": title,
            "desp": f"{body}\n\n👉 [点击直达官方订票页]({target_url})"
        }).encode("utf-8")
        try:
            urllib.request.urlopen(api, data=data, timeout=10)
            print(f"[Server酱] 推送成功: {title}")
            sent = True
        except Exception as e:
            print(f"[Server酱] 推送失败: {e}")

    if not sent:
        print(f"[状态变更-未配置推送密钥] {title} | {body}")


def run_check():
    state = load_state()
    state_changed = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = context.new_page()

        for item in TARGETS:
            tid = item["id"]
            print(f"正在巡检: {item['name']}")
            try:
                page.goto(item["url"], wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)
                body_text = page.inner_text("body")

                # 提取匹配到的关键词及其周边核心文本特征，避免无关广告或时间戳引发误报
                matched_lines = []
                for line in body_text.splitlines():
                    clean_line = line.strip()
                    if clean_line and any(kw in clean_line for kw in item["watch_keywords"]):
                        matched_lines.append(clean_line)

                fingerprint_raw = "\n".join(sorted(set(matched_lines)))
                current_hash = hashlib.sha256(fingerprint_raw.encode("utf-8")).hexdigest()[:16]
                prev_hash = state.get(tid, {}).get("hash", "")

                if not matched_lines:
                    print(f"[{tid}] 页面暂未出现有效票务信息。")
                    continue

                if current_hash != prev_hash:
                    is_first = (prev_hash == "")
                    prefix = "🎯 首次监测到开放信息" if is_first else "🚨 页面票务状态已更新"
                    title = f"{prefix}：{item['name']}"
                    preview = " / ".join(matched_lines[:3])[:120]
                    body = f"{item['note']}\n关键内容：{preview}"

                    send_notification(title, body, item["url"])
                    state[tid] = {
                        "hash": current_hash,
                        "sample": preview
                    }
                    state_changed = True
                else:
                    print(f"[{tid}] 状态与上次完全一致，跳过重复推送。")

            except Exception as e:
                print(f"[{tid}] 访问异常: {e}")

        browser.close()

    if state_changed:
        save_state(state)
        print("已更新状态指纹文件 monitor_state.json")


if __name__ == "__main__":
    run_check()
