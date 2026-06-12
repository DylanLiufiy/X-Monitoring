import os
import sys
import json
import asyncio
import httpx
from datetime import datetime
from twikit import Client

# ==================== 🛠️ 生产级配置中心 ====================
X_USERNAME = os.environ.get("X_USERNAME")
X_EMAIL = os.environ.get("X_EMAIL")
X_PASSWORD = os.environ.get("X_PASSWORD")
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")

TARGET_USER = "serenityX"
CHECK_INTERVAL = 10          # 🔥 严格 10 秒刷新一次
LIFETIME = 21000             # 🔥 运行 5.8 小时自动优雅退出，让位给下一个轮班容器
# =======================================================

client = Client('en-US')
CACHE_FILE = "last_seen_id.txt"
COOKIE_FILE = "cookies.json"

def get_last_seen_id():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

def save_last_seen_id(tweet_id):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        f.write(str(tweet_id))

async def send_to_feishu(text, tweet_url, created_at):
    """飞书 Markdown 高亮红卡推送"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"⚡ [10s实时] {TARGET_USER} 发布新动态"},
                "template": "red"
            },
            "elements": [
                {"tag": "markdown", "content": f"**📌 消息内容：**\n{text}\n\n**🕒 发布时间：** {created_at}"},
                {"tag": "action", "actions": [{"tag": "button", "text": {"tag": "plain_text", "content": "🔗 立即查看原文"}, "type": "primary", "url": tweet_url}]}
            ]
        }
    }
    async with httpx.AsyncClient() as http_client:
        try:
            res = await http_client.post(FEISHU_WEBHOOK, json=payload, headers=headers)
            print(f"📡 飞书推送结果: {res.status_code}")
        except Exception as e:
            print(f"❌ 飞书推送异常: {e}")

async def main():
    if not all([X_USERNAME, X_EMAIL, X_PASSWORD, FEISHU_WEBHOOK]):
        print("❌ 错误：GitHub Secrets 环境变量配置不完整！")
        sys.exit(1)

    print("🔐 正在初始化 X 平台登录状态...")
    try:
        if os.path.exists(COOKIE_FILE):
            client.load_cookies(COOKIE_FILE)
            print("🍪 成功从本地缓存加载 Cookie 绕过登录验证！")
        else:
            print("🔑 未检测到本地 Cookie，正在使用账号密码登录...")
            await client.login(auth_info_1=X_USERNAME, auth_info_2=X_EMAIL, password=X_PASSWORD)
            client.save_cookies(COOKIE_FILE)
            print("💾 首次登录成功，已成功将 Cookie 固化到本地")
    except Exception as e:
        print(f"❌ 登录遇到安全阻断: {e}")
        sys.exit(1)

    try:
        user = await client.get_user_by_screen_name(TARGET_USER)
        target_id = user.id
        print(f"🎯 成功锁定目标账号 ID: {target_id}")
    except Exception as e:
        print(f"❌ 无法解析目标用户名: {e}")
        return

    start_time = datetime.now()
    print(f"🛰️ 10秒级高频常驻守护进程已激活，本轮监听将持续 5.8 小时...")

    while (datetime.now() - start_time).total_seconds() < LIFETIME:
        try:
            tweets = await client.get_user_tweets(target_id, 'Tweets')
            if tweets:
                latest_tweet = tweets
                last_id = get_last_seen_id()

                if last_id is None:
                    save_last_seen_id(latest_tweet.id)
                    print(f"📍 记忆库初始化，最新推文锚定为 ID: {latest_tweet.id}")
                
                elif str(latest_tweet.id) != str(last_id):
                    print(f"🔥 捕获到新消息：{latest_tweet.id}")
                    save_last_seen_id(latest_tweet.id)
                    tweet_url = f"https://x.com{TARGET_USER}/status/{latest_tweet.id}"
                    await send_to_feishu(latest_tweet.text, tweet_url, latest_tweet.created_at)
                    
        except Exception as e:
            print(f"⚠ 高频检测产生正常抖动或被限流: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)
        
    print("👋 本轮长循环安全期满，主动退出并请求下一班容器交接。")

if __name__ == "__main__":
    asyncio.run(main())
