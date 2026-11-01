"""Capture the real web UI using synthetic fixtures and a fresh browser context.

Run a local web server on 18765 first. No production service is contacted.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "media"
OUT.mkdir(parents=True, exist_ok=True)
ARTICLES = [
    {"id": "demo-reading", "title": "从一篇文章开始，建立自己的理解", "category": "阅读方法", "desc": "演示内容：区分事实、解释与观点，再回到原始来源核实。", "source": "公开版合成示例", "read_time": "约 3 分钟"},
    {"id": "demo-question", "title": "把好奇心变成一个清楚的问题", "category": "AI 追问", "desc": "演示内容：先写下已知背景，再提出希望了解的具体问题。", "source": "公开版合成示例", "read_time": "约 4 分钟"},
    {"id": "demo-source", "title": "阅读之后，记得检查信息来源", "category": "信息素养", "desc": "演示内容：交叉核对发布机构、日期与上下文，不把生成回答当成新闻。", "source": "公开版合成示例", "read_time": "约 3 分钟"},
]

def route_request(route):
    url = route.request.url
    if "/api/" in url:
        data = []
        if "/today" in url:
            data = ARTICLES
        elif "daily-quote" in url:
            data = {"text": "让理解多一步，让判断有依据。", "source_title": "公开版界面演示", "plain_explanation": "此处为合成文案，不是新闻或名人引语。", "today_connection": "从来源出发，慢慢形成自己的判断。"}
        return route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body=json.dumps(data, ensure_ascii=False))
    if not url.startswith("http://127.0.0.1:") and not url.startswith("data:"):
        return route.abort()
    route.continue_()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    context.route("**/*", route_request)
    page = context.new_page()
    for name, path in [("today", "jianwen/index.html"), ("login", "jianwen/login.html"), ("home", "index.html")]:
        page.goto("http://127.0.0.1:18765/" + path + "?v=20261031-1", wait_until="networkidle")
        page.screenshot(path=str(OUT / (name + ".png")))
    context.close()
    browser.close()
