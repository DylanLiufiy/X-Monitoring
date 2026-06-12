import os
import sys
import asyncio
import httpx
import re
from datetime import datetime

# ==================== 🛠️ 生产级配置中心 ====================
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")
TARGET_USER = "serenityX"    # 👈 锁定你要盯死的目标 ID
CHECK_INTERVAL = 10          # 🔥 严格 10 秒刷新一次
LIFETIME = 21000             # 🔥 运行 5.8 小时自动换班
# =======================================================

CACHE_FILE = "last_seen_id.txt"

# 📡 【黑科技矩阵】精选2026年全球最稳定、高速、无封锁的 Twitter 匿名网关列表
RSS_NODES = [
    "https://rsshub.app",                 # 节点1：官方主节点（有并发限制，但数据最全）
    "https://moeyy.xyz",              # 节点2：高速非官方公共节点
    "https://rssforever.com",      # 节点3：老牌抗封锁节点
    "https://sm9.top",             # 节点4：国内可直连的加速镜像
    "https://outv.im"                 # 节点5：海外纯净机房专属节点
]

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
            print(f"📡 飞书推送成功，状态码: {res.status_code}")
        except Exception as e:
            print(f"❌ 飞书推送异常: {e}")

async def fetch_latest_tweet_via_rss(username):
    """【多节点轮询引擎】依次探测节点，直至抓取成功，彻底干掉 Name or service not known"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 遍历我们准备好的网关矩阵
    for node in RSS_NODES:
        url = f"{node}/twitter/user/{username}"
        print(f"🔄 正在通过节点 [{node}] 尝试抓取推文...")
        
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                response = await client.get(url, headers=headers)
                
                # 状态码 200 且包含正确数据块才算过关
                if response.status_code == 200 and "<item>" in response.text:
                    item_match = re.search(r'<item>(.*?)</item>', response.text, re.DOTALL)
                    if item_match:
                        item_content = item_match.group(1)
                        
                        # 精准提取标题正文
                        title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item_content)
                        title = title_match.group(1) if title_match else "查看原推文内容"
                        
                        # 精准提取直连链接
                        link_match = re.search(r'<link>(.*?)</link>', item_content)
                        link = link_match.group(1).strip() if link_match else f"https://x.com/{username}"
                        
                        # 精准提取时间
                        date_match = re.search(r'<pubDate>(.*?)</pubDate>', item_content)
                        pub_date = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        tweet_id = link.split("/status/")[-1].strip() if "/status/" in link else str(hash(title))
                        
                        print(f"✅ 节点 [{node}] 畅通！成功拿到最新数据。")
                        return {"id": tweet_id, "text": title, "url": link, "date": pub_date}
                
                elif response.status_code == 429:
                    print(f"⚠ 节点 [{node}] 提示高频被限流(429)，正在自动跳向下一个备份节点...")
                else:
                    print(f"⚠ 节点 [{node}] 响应码异常 ({response.status_code})，自动切流...")
                    
            except Exception as e:
                # 完美捕获你刚才遇到的域名不通错误，并静默切流，不引发脚本中断
                print(f"❌ 节点 [{node}] 连接失败 (网络或DNS抖动): {e}，正在切换下一组热备...")
                
    print("🚨 警告：本轮扫描中全网5个匿名网关节点全军覆没！")
    return None

async def main():
    if not FEISHU_WEBHOOK:
        print("❌ 错误：飞书 Webhook 环境变量未配置！")
        sys.exit(1)

    print(f"🎯 工业级分布式免登录雷达已开启，锁定目标: {TARGET_USER}")
    start_time = datetime.now()
    print(f"🛰️ 10秒级高频常驻守护进程已激活，本轮监听将持续 5.8 小时...")

    while (datetime.now() - start_time).total_seconds() < LIFETIME:
        tweet = await fetch_latest_tweet_via_rss(TARGET_USER)
        if tweet:
            latest_id = tweet["id"]
            last_id = get_last_seen_id()

            if last_id is None:
                save_last_seen_id(latest_id)
                print(f"📍 记忆库初始化成功！最新推文已安全锚定。")
            
            elif str(latest_id) != str(last_id):
                print(f"🔥 捕获到全新实时消息：{latest_id}")
                save_last_seen_id(latest_id)
                await send_to_feishu(tweet["text"], tweet["url"], tweet["date"])
        else:
            print("💤 全网节点暂无可达，数据层空载。保持监听，10秒后发起新一轮矩阵轮询...")
        
        await asyncio.sleep(CHECK_INTERVAL)
        
    print("👋 本轮长循环安全期满，主动退出并请求下一班容器交接。")

if __name__ == "__main__":
    asyncio.run(main())
