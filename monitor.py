import os
import sys
import asyncio
import httpx
import re
from datetime import datetime

# ==================== 🛠️ 生产级配置中心 ====================
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")

# 🔥【核心修正】修正为美股半导体大牛 Serenity 真正的 X 官方唯一 ID！
TARGET_USER = "aleabitoreddit"    

CHECK_INTERVAL = 10          # 严格 10 秒刷新一次
LIFETIME = 21000             # 运行 5.8 小时自动换班
# =======================================================

CACHE_FILE = "last_seen_id.txt"

def get_last_seen_id():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

def save_last_seen_id(tweet_id):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        f.write(str(tweet_id))

async def send_to_feishu(text, tweet_url, created_at):
    """飞书 Markdown 红色高亮通知卡片"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"🚨 [AI/半导体雷达] Serenity 刚刚发布了新研报"},
                "template": "red"
            },
            "elements": [
                {"tag": "markdown", "content": f"**📌 研报/动态内容：**\n{text}\n\n**🕒 捕获时间：** {created_at}"},
                {"tag": "action", "actions": [{"tag": "button", "text": {"tag": "plain_text", "content": "🔗 立即前往 X 跟踪供应链长文"}, "type": "primary", "url": tweet_url}]}
            ]
        }
    }
    async with httpx.AsyncClient() as http_client:
        try:
            res = await http_client.post(FEISHU_WEBHOOK, json=payload, headers=headers)
            print(f"📡 飞书群推送成功，状态码: {res.status_code}")
        except Exception as e:
            print(f"❌ 飞书推送异常: {e}")

async def fetch_tweet_by_raw_text(username):
    """【硬切片引擎】越过一切限流阻断，利用原生无头静态请求，直接硬剥离最新推文ID与正文"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    # 采用高可达性的开放中转层
    nodes = ["https://vxtwitter.com", "https://fxtwitter.com"]
    for node in nodes:
        url = f"{node}/{username}"
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200 and "status/" in res.text:
                    # 1. 提取全球唯一的推文状态号雪花ID
                    id_match = re.search(r'/status/(\d+)', res.text)
                    if id_match:
                        tweet_id = id_match.group(1)
                        
                        # 2. 尝试从网页元数据（Og-Description）中粗暴剥离出完整的正文
                        text_match = re.search(r'<meta property="og:description" content="(.*?)"', res.text)
                        text = text_match.group(1) if text_match else "发布了全新的产业动态，请点击下方按钮一键追踪详情"
                        
                        # 清洗一下 HTML 转移字符
                        text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&#39;", "'")
                        tweet_url = f"https://x.com/{username}/status/{tweet_id}"
                        
                        return {"id": tweet_id, "text": text, "url": tweet_url}
        except Exception as node_err:
            print(f"📡 边缘中转站 [{node}] 产生高频过载: {node_err}，正在请求后续后备通道...")
            
    return None

async def main():
    if not FEISHU_WEBHOOK:
        print("❌ 错误：飞书 Webhook 环境变量未配置！")
        sys.exit(1)

    print(f"🎯 真·Serenity 雷达已重置校准，正在死死盯防系统 ID: {TARGET_USER}")
    start_time = datetime.now()
    print(f"走！开始进入 10 秒级不间断死循环状态...")

    while (datetime.now() - start_time).total_seconds() < LIFETIME:
        try:
            tweet = await fetch_tweet_by_raw_text(TARGET_USER)
            if tweet:
                latest_id = tweet["id"]
                last_id = get_last_seen_id()

                if last_id is None:
                    save_last_seen_id(latest_id)
                    print(f"📍 【冷启动成功】记忆库已成功初始化！当前已把 Serenity 最新的推文 ID 锚定为: {latest_id}")
                elif str(latest_id) != str(last_id):
                    print(f"🔥 【警报】检测到大佬发布了全新供应链动态！新推文雪花 ID 为: {latest_id}")
                    save_last_seen_id(latest_id)
                    await send_to_feishu(tweet["text"], tweet["url"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                else:
                    print(f"✅ 10s周期巡检完毕：大牛未发推。ID保持为 ({latest_id})。")
            else:
                print("💤 边缘网络处于瞬时高压脱载状态。保持长连，10秒后发起新一轮穿透刷新...")
        except Exception as queue_err:
            print(f"⚠ 循环体内意外抖动: {queue_err}")
            
        await asyncio.sleep(CHECK_INTERVAL)
        
    print("👋 本轮 5.8 小时交接时间到，优雅退出。")

if __name__ == "__main__":
    asyncio.run(main())
