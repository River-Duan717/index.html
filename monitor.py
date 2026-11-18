import os
import urllib.parse
import urllib.request
from playwright.sync_api import sync_playwright

# 手机推送密钥（通过 GitHub Secrets 环境变量安全读取）
BARK_KEY = os.getenv("BARK_KEY", "").strip()
SERVERCHAN_KEY = os.getenv("SERVERCHAN_KEY", "").strip()

# 需要巡检的官方订票页面配置
TARGETS = [
    {
        "name": "北海道中央巴士·札幌国际滑雪场预约套票",
        "url": "https://www.chuo-bus.co.jp/sightseeing/ski/sapporo-kokusai.php",
        "keywords": ["予約", "販売中", "12月", "申込"],
        "note": "检测到预约入口或冬季班次信息已更新，请立即锁定12/26、12/27、12/29往返座位！"
    },
    {
        "name": "札幌手稻滑雪场 Webket 早鸟票页面",
        "url": "https://webket.jp/pc/ticket/index?fc=00368&ac=8001",
        "keywords": ["購入", "販売中", "早割", "リフト"],
        "note": "检测到 Webket 电子票务页面已开放，请核对早鸟雪票及夜场券价格！"
    },
    {
        "name": "札幌盘溪滑雪场 Webket 购票页面",
        "url": "https://webket.jp/pc/ticket/index?fc=00289&ac=8001",
        "keywords": ["購入", "販売中", "早割", "パック"],
        "note": "检测到盘溪滑雪场线上购票通道已上线，可提前预订初级体验套票！"
    }
]


def send_notification(title: str, body: str, target_url: str):
    """支持 iOS Bark 与 微信 Server酱 双通道推送"""
    sent = False

    # 1. iOS Bark 推送（推荐：点击通知直接跳转官方订票页）
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

    # 2. 微信 Server酱 推送（安卓/通用推荐）
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
        print(f"[模拟通知 - 未配置密钥] {title} | {body} | {target_url}")


def run_check():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = context.new_page()

        for item in TARGETS:
            print(f"正在巡检: {item['name']} -> {item['url']}")
            try:
                page.goto(item["url"], wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)
                content = page.inner_text("body")

                matched = [kw for kw in item["keywords"] if kw in content]
                if matched:
                    title = f"🎿 放票预警：{item['name']}"
                    body = f"命中关键词 {matched}。{item['note']}"
                    send_notification(title, body, item["url"])
                else:
                    print(f"暂未命中放票关键词: {item['name']}")
            except Exception as e:
                print(f"访问失败 ({item['name']}): {e}")

        browser.close()


if __name__ == "__main__":
    run_check()
