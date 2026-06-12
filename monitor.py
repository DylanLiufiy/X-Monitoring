import os
import sys
import json
import asyncio
import httpx
from datetime import datetime
from twikit import Client

# ==================== 🛠️ 生产级配置 ====================
X_USERNAME = os.environ.get("X_USERNAME")
X_EMAIL = os.environ.get("X_EMAIL")
X_PASSWORD = os.environ.get("X_PASSWORD")
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")

TARGET_USER = "serenityX"
CHECK_INTERVAL = 10          # 🔥 降级到 10 秒一次真·实时
LIFETIME = 21000             # 🔥 单次工作流运行 5.8 小时（约21000秒）后优雅退出，防止触碰GitHub 6小时强杀线
# =======================================================

client = Client('en-US')
CACHE_FILE = "last_seen_id.txt"

def get_last_seen_id():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return f.read().strip()
    return None

def save_last_seen_id(tweet_id):
    with open(CACHE_FILE, "w") as f:
        f.write(str(tweet_id))

async def send_to_feishu(text, tweet_url, created_at):
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"⚡ [10s实时] {TARGET_USER} 发推了！"},
                "template": "red" # 红色高亮紧急信号
            },
            "elements": [
                {"tag": "markdown", "content": f"**📌 消息内容：**\n{text}\n\n**🕒 发布时间：** {created_at}"},
                {"tag": "action", "actions": [{"tag": "button", "text": {"tag": "plain_text", "content": "🔗 立即查看"}, "type": "primary", "url": tweet_url}]}
            ]
        }
    }
    async with httpx.AsyncClient() as http_client:
        try:
            await http_client.post(FEISHU_WEBHOOK, json=payload, headers=headers)
        except Exception as e:
            print(f"❌ 飞书推送失败: {e}")

async def main():
    if not all([X_USERNAME, X_EMAIL, X_PASSWORD, FEISHU_WEBHOOK]):
        sys.exit(1)

    print("🔐 正在使用持久化方案登录 X...")
    try:
        if os.path.exists('cookies.json'):
            client.load_cookies('cookies.json')
        else:
            await client.login(auth_info_1=X_USERNAME, auth_info_2=X_EMAIL, password=X_PASSWORD)
            client.save_cookies('cookies.json')
    except Exception as e:
        print(f"❌ 登录阻断: {e}")
        sys.exit(1)

    try:
        user = await client.get_user_by_screen_name(TARGET_USER)
        target_id = user.id
    except Exception as e:
        print(f"❌ 无法锁定用户: {e}")
        return

    start_time = datetime.now()
    print(f"🛰️ 10秒级高频常驻监控已就绪，本轮守护进程将持续 5.8 小时...")

    # 无限死循环，直到达到5.8小时上限
    while (datetime.now() - start_time).total_seconds() < LIFETIME:
        try:
            tweets = await client.get_user_tweets(target_id, 'Tweets')
            if tweets:
                latest_tweet = tweets
                last_id = get_last_seen_id()

                if last_id is None:
                    save_last_seen_id(latest_tweet.id)
                    print(f"📍 初始化最新推文 ID: {latest_tweet.id}")
                
                elif str(latest_tweet.id) != str(last_id):
                    print(f"🔥 捕获到新动态: {latest_tweet.id}")
                    save_last_seen_id(latest_tweet.id)
                    tweet_url = f"https://x.com{TARGET_USER}/status/{latest_tweet.id}"
                    await send_to_feishu(latest_tweet.text, tweet_url, latest_tweet.created_at)
                    
        except Exception as e:
            print(f"⚠ 频率过高或网络抖动: {e}")
        
        # 精确控制 10 秒间隔
        await asyncio.sleep(CHECK_INTERVAL)
        
    print("👋 本轮长循环结束，将交棒给下一个 Actions 容器。")

if __name__ == "__main__":
    asyncio.run(main())
