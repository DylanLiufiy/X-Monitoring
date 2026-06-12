import os
import sys
import asyncio
import httpx
import re
from datetime import datetime

# ==================== 🛠️ 生产级配置中心 ====================
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")

# 🎯 已彻底校准为大牛 Serenity 在 X 上的唯一真实路由 ID
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
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"🚨 [AI/半导体雷达] Serenity 发布了新动态"},
                "template": "red"
            },
            "elements": [
                {"tag": "markdown", "content": f"**📌 动态内容：**\n{text}\n\n**🕒 捕获时间：** {created_at}"},
                {"tag": "action", "actions": [{
                    "tag": "button", 
                    "text": {"tag": "plain_text", "content": "🔗 立即前往 X 跟踪供应链长文"}, 
                    "type": "primary", 
                    "url": tweet_url
                }]}
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
    """【硬切片捕获引擎】关闭自动重定向，直接捕获 302/200 报文中的雪花 ID，通杀任何反爬拦截"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 📡 【Debug 终极抗封锁节点矩阵】彻底干掉网关拥堵！
    nodes = [
        "https://vxtw.net",              # 最新抗封锁 JSON/HTML 双通道网关
        "https://fixupx.com",                # 极其稳定的老牌 X 中转路由
        "https://alexis.gg",          # 目前极速运行的高匿只读静态镜像
        "https://twiiit.com"                 # 全球分布式自动分流推特静态网关
    ]
    
    for node in nodes:
        url = f"{node}/{username}"
        try:
            # follow_redirects=False，彻底封死 Exceeded maximum allowed redirects 报错
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
                res = await client.get(url, headers=headers)
                
                # 情况一：如果触发 301/302 重定向，直接抓取 Location 报头里的真实推文链接
                if res.status_code == 301 or res.status_code == 302:
                    redirect_url = res.headers.get("Location", "")
                    if "status/" in redirect_url:
                        tweet_id = redirect_url.split("/status/")[-1].split("?")[0].strip()
                        return {
                            "id": tweet_id, 
                            "text": "捕获到大牛更新了产业研报，请点击下方按钮前往追踪", 
                            "url": f"https://x.com{username}/status/{tweet_id}"
                        }
                
                # 情况二：正常 200 返回，直接正则检索网页文本
                elif res.status_code == 200:
                    id_match = re.search(r'/status/(\d+)', res.text)
                    if id_match:
                        tweet_id = id_match.group(1)
                        text_match = re.search(r'<meta property="og:description" content="(.*?)"', res.text) or re.search(r'<title>(.*?)</title>', res.text)
                        text = text_match.group(1) if text_match else "发布了全新的产业动态，请点击下方按钮一键追踪详情"
                        text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&#39;", "'")
                        return {
                            "id": tweet_id, 
                            "text": text, 
                            "url": f"https://x.com{username}/status/{tweet_id}"
                        }
                        
        except Exception as node_err:
            print(f"📡 边缘节点 [{node}] 请求产生网络微调: {node_err}")
            
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
                    print(f"📍 【冷启动成功】由于目标更改为真实ID，记忆库已成功锚定！当前最新推文 ID 为: {latest_id}")
                elif str(latest_id) != str(last_id):
                    print(f"🔥 【警报】检测到大牛发布了全新供应链动态！新推文雪花 ID 为: {latest_id}")
                    save_last_seen_id(latest_id)
                    await send_to_feishu(tweet["text"], tweet["url"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                else:
                    print(f"🔄 巡检正常：Serenity 当前未发推。雪花 ID 稳定为 ({latest_id})。")
            else:
                print("💤 边缘中转网关瞬时拥堵。保持监听，10秒后发起新一轮穿透刷新...")
        except Exception as queue_err:
            print(f"⚠ 循环体内意外抖动: {queue_err}")
            
        await asyncio.sleep(CHECK_INTERVAL)
        
    print("👋 本轮 5.8 小时交接时间到，优雅退出。")

if __name__ == "__main__":
    asyncio.run(main())
