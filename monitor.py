import os
import sys
import asyncio
import httpx
import re
from datetime import datetime

# ==================== 🛠️ 生产级配置中心 ====================
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")
TARGET_USER = "serenityX"    # 👈 记得改成你实际要盯着的账号
CHECK_INTERVAL = 10          # 🔥 严格 10 秒刷新一次
LIFETIME = 21000             # 🔥 运行 5.8 小时自动优雅退出
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

async def fetch_latest_tweet_via_rss(username):
    """【健壮版】使用正则表达式精准剥离 XML 数据，100% 防止切片卡死"""
    url = f"https://rsshub.app{username}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200 and "<item>" in response.text:
                # 提取第一个 <item> 块（即最新一条推文）
                item_match = re.search(r'<item>(.*?)</item>', response.text, re.DOTALL)
                if item_match:
                    item_content = item_match.group(1)
                    
                    # 精准提取标题/文本
                    title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item_content)
                    title = title_match.group(1) if title_match else "查看原推文内容"
                    
                    # 精准提取链接
                    link_match = re.search(r'<link>(.*?)</link>', item_content)
                    link = link_match.group(1).strip() if link_match else f"https://x.com{username}"
                    
                    # 精准提取时间
                    date_match = re.search(r'<pubDate>(.*?)</pubDate>', item_content)
                    pub_date = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 剥离推文唯一 ID
                    tweet_id = link.split("/status/")[-1].strip() if "/status/" in link else str(hash(title))
                    
                    return {"id": tweet_id, "text": title, "url": link, "date": pub_date}
        except Exception as e:
            print(f"📡 备用公共节点网络波动: {e}")
    return None

async def main():
    if not FEISHU_WEBHOOK:
        print("❌ 错误：飞书 Webhook 环境变量未配置！")
        sys.exit(1)

    print(f"🎯 免登录雷达已开启，锁定目标: {TARGET_USER}")
    start_time = datetime.now()
    print(f"🛰️ 10秒级高频常驻守护进程已激活，本轮监听将持续 5.8 小时...")

    while (datetime.now() - start_time).total_seconds() < LIFETIME:
        tweet = await fetch_latest_tweet_via_rss(TARGET_USER)
        if tweet:
            latest_id = tweet["id"]
            last_id = get_last_seen_id()

            if last_id is None:
                save_last_seen_id(latest_id)
                print(f"📍 记忆库初始化成功！最新推文锚定为 ID: {latest_id}")
            
            elif str(latest_id) != str(last_id):
                print(f"🔥 捕获到新消息：{latest_id}")
                save_last_seen_id(latest_id)
                await send_to_feishu(tweet["text"], tweet["url"], tweet["date"])
        else:
            print("💤 未获取到有效数据，将在下一个10秒周期自动重试...")
        
        await asyncio.sleep(CHECK_INTERVAL)
        
    print("👋 本轮长循环安全期满，主动退出并请求下一班容器交接。")

if __name__ == "__main__":
    asyncio.run(main())
