import os
import sys
import asyncio
import httpx
import re
from datetime import datetime

# ==================== 🛠️ 生产级配置中心 ====================
# 从 GitHub Secrets 动态读取飞书群机器人的 Webhook 链接
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")

# 你真正想要实时监控的 X（原推特）账号用户名ID（去掉@符号）
TARGET_USER = "serenityX"    

# 扫描探测频率（单位：秒）。10秒代表高频真·实时扫描
CHECK_INTERVAL = 10          

# 单次脚本在 GitHub 云端持续运行的寿命（5.8小时），到期自动换班，无缝拼接24小时
LIFETIME = 21000             
# =======================================================

CACHE_FILE = "last_seen_id.txt"

def get_last_seen_id():
    """从本地状态文件中读取上一次成功抓取到的推文ID"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

def save_last_seen_id(tweet_id):
    """将最新抓取到的推文ID固化到状态文件中"""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        f.write(str(tweet_id))

async def send_to_feishu(text, tweet_url, created_at):
    """构建飞书 Markdown 高亮红卡样式，将消息实时弹窗推送到群内"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"⚡ [10s实时] {TARGET_USER} 发布新动态"},
                "template": "red" # 红色高亮，代表紧急高优信息
            },
            "elements": [
                {"tag": "markdown", "content": f"**📌 消息内容：**\n{text}\n\n**🕒 发布时间：** {created_at}"},
                {
                    "tag": "action", 
                    "actions": [{
                        "tag": "button", 
                        "text": {"tag": "plain_text", "content": "🔗 立即查看原文"}, 
                        "type": "primary", 
                        "url": tweet_url
                    }]
                }
            ]
        }
    }
    async with httpx.AsyncClient() as http_client:
        try:
            res = await http_client.post(FEISHU_WEBHOOK, json=payload, headers=headers)
            print(f"📡 飞书群推送触发，服务器返回状态码: {res.status_code}")
        except Exception as e:
            print(f"❌ 飞书网络推送异常: {e}")

async def fetch_latest_tweet_via_rss(username):
    """【黑科技核心】利用高速海外公共匿名网关直接拉取推文，免去账号密码登录步骤"""
    # 采用专门服务海外数据中心的高速抗封锁节点
    url = f"https://anyfeeder.com{username}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200 and "<item>" in response.text:
                # 1. 使用正则表达式精准截取最新发布的那一条推文数据块
                item_match = re.search(r'<item>(.*?)</item>', response.text, re.DOTALL)
                if item_match:
                    item_content = item_match.group(1)
                    
                    # 2. 剥离推文的内容正文
                    title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item_content)
                    title = title_match.group(1) if title_match else "点击按钮查看原推文详情"
                    
                    # 3. 提取推文的网页直连路径
                    link_match = re.search(r'<link>(.*?)</link>', item_content)
                    link = link_match.group(1).strip() if link_match else f"https://x.com{username}"
                    
                    # 4. 获取推文的发布时间
                    date_match = re.search(r'<pubDate>(.*?)</pubDate>', item_content)
                    pub_date = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 5. 从推文链接中切片分离出全球唯一的雪花 ID（用于增量去重新消息判别）
                    tweet_id = link.split("/status/")[-1].strip() if "/status/" in link else str(hash(title))
                    
                    return {"id": tweet_id, "text": title, "url": link, "date": pub_date}
        except Exception as e:
            print(f"📡 探测节点产生高频抖动（属正常现象，10秒后将自动重试）: {e}")
    return None

async def main():
    # 安全合规性验证：确保飞书群机器人地址被正确录入
    if not FEISHU_WEBHOOK:
        print("❌ 严重错误：未在 GitHub Secrets 中检测到 FEISHU_WEBHOOK 加密密钥！")
        sys.exit(1)

    print(f"🎯 免登录高频雷达初始化就绪，正在锁定目标: {TARGET_USER}")
    start_time = datetime.now()
    print(f"🛰️ 守护进程已常驻运行，本轮 10 秒级高频轮询预计将持续 5.8 小时...")

    # 进入5.8小时全自动化高频死循环阶段
    while (datetime.now() - start_time).total_seconds() < LIFETIME:
        tweet = await fetch_latest_tweet_via_rss(TARGET_USER)
        if tweet:
            latest_id = tweet["id"]
            last_id = get_last_seen_id()

            # 初始化：首次运行Actions时只做锚定记忆，不把历史发过的旧消息灌进飞书群
            if last_id is None:
                save_last_seen_id(latest_id)
                print(f"📍 记忆库完成首次初始化！最新一条推文成功锁定为 ID: {latest_id}")
            
            # 增量比对：发现最新一条推文的ID与上一次记录的不同，代表目标发了全新动态
            elif str(latest_id) != str(last_id):
                print(f"🔥 发现全新动态！新推文唯一标识符为: {latest_id}")
                save_last_seen_id(latest_id) # 立刻更新状态，防止因容器意外重启导致重复发信
                
                # 触发向你的飞书群发送实时高亮卡片通知
                await send_to_feishu(tweet["text"], tweet["url"], tweet["date"])
        else:
            print("💤 本周期未捕获到有效变动，保持长连接监听，10秒后重启扫描...")
        
        # 强制精准睡眠 10 秒，严格控制高频探测步长
        await asyncio.sleep(CHECK_INTERVAL)
        
    print("👋 本轮 5.8 小时常驻守护周期结束，脚本主动退出并请求下一班云端容器无缝交接。")

if __name__ == "__main__":
    asyncio.run(main())
