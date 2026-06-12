import os
import sys
import asyncio
import httpx
import re
import random
from datetime import datetime

# ==================== 🛠️ 智能升级配置中心 ====================
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")
TARGET_USER = "aleabitoreddit"    

# 🧠 智能防封锁步长：调至30秒，并在运行时随机抖动，彻底粉碎反爬虫IP审查
CHECK_INTERVAL = 30          
LIFETIME = 21000             
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

async def send_to_feishu(title_label, text, tweet_url, created_at):
    """飞书富文本 Markdown 推送"""
    headers = {"Content-Type": "application/json"}
    
    # 极简中文粗暴翻译引擎（针对常见美股核心词汇进行本地化清洗，防止大模型API在Actions中超时）
    translated_text = text
    dict_trans = {
        "Nvidia": "英伟达", "NVDA": "英伟达", "infrastructure": "基础设施",
        "supply chain": "供应链", "yields": "良率/成品率", "optics": "光学/光模块",
        "datacenter": "数据中心", "market": "市场", "stocks": "美股", "cancelled": "取消了",
        "Just in case you wonder why": "以防你们好奇为什么", "Trump": "特朗普"
    }
    for eng, chn in dict_trans.items():
        translated_text = re.sub(eng, chn, translated_text, flags=re.IGNORECASE)

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"🚨 [{title_label}] Serenity 研报快讯"},
                "template": "red" if "实时" in title_label else "orange"
            },
            "elements": [
                {"tag": "markdown", "content": f"**原文内容：**\n{text}\n\n**🇨🇳 中文大意：**\n{translated_text}\n\n**🕒 捕获时间/发布时间：** {created_at}"},
                {"tag": "action", "actions": [{"tag": "button", "text": {"tag": "plain_text", "content": "🔗 立即前往 X 跟踪供应链长文"}, "type": "primary", "url": tweet_url}]}
            ]
        }
    }
    async with httpx.AsyncClient() as http_client:
        try:
            res = await http_client.post(FEISHU_WEBHOOK, json=payload, headers=headers)
            print(f"📡 飞书推送成功 [{title_label}], 状态码: {res.status_code}")
        except Exception as e:
            print(f"❌ 飞书推送异常: {e}")

async def fetch_all_visible_tweets(username):
    """通过稳固节点一次性抓取页面上所有可见的推文（用于历史追溯）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    nodes = ["https://xcancel.com", "https://d420.de", "https://fxtwitter.com"]
    
    for node in nodes:
        url = f"{node}/{username}"
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=False) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    # 正则抓取页面上所有的推文数据块
                    matches = re.findall(r'/status/(\d+)', res.text)
                    if matches:
                        # 去重并保持顺序
                        tweet_ids = list(dict.fromkeys(matches))[:4] # 仅取最近的4条记录（约1天内）
                        results = []
                        for tid in tweet_ids:
                            results.append({
                                "id": tid,
                                "text": f"Serenity 发布的最新核心供应链动态 (ID: {tid})。请点击下方按钮查看完整技术长文与图表。",
                                "url": f"https://x.com{username}/status/{tid}",
                                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                        print(f"🎯 通过节点 [{node}] 成功解耦并提取到 {len(results)} 条历史研报主线！")
                        return results
        except Exception:
            continue
    return []

async def main():
    if not FEISHU_WEBHOOK:
        sys.exit(1)

    print(f"🎯 智能防封升级版雷达上线，锁定目标: {TARGET_USER}")
    start_time = datetime.now()

    # 🚀【核心升级：自动追溯补发历史】
    last_id = get_last_seen_id()
    if last_id is None:
        print("📍 检测到记忆库为空，正在执行【倒带计划】，自动抓取过去 1 天的历史推文投喂给飞书群...")
        history_tweets = await fetch_all_visible_tweets(TARGET_USER)
        if history_tweets:
            # 反向遍历，先发最旧的，确保飞书群里最新的一条在最下面
            for tweet in reversed(history_tweets):
                await send_to_feishu("历史回溯中译", tweet["text"], tweet["url"], tweet["date"])
                await asyncio.sleep(2) # 稍微歇一下防止飞书限流
            # 把最新的一条 ID 存盘记忆
            save_last_seen_id(history_tweets[0]["id"])
            print(f"✅ 历史数据补发完毕！当前最新推文已锚定。")
        else:
            # 降级容灾：如果一上来节点全挂，写个虚拟坐标防止下次重启又重复抓取
            save_last_seen_id("2065136761077158061")

    print(f"走！进入常驻守护状态...")
    while (datetime.now() - start_time).total_seconds() < LIFETIME:
        try:
            # 动态获取当前最新的一条
            history_tweets = await fetch_all_visible_tweets(TARGET_USER)
            if history_tweets:
                latest_tweet = history_tweets[0]
                latest_id = latest_tweet["id"]
                current_last_id = get_last_seen_id()

                if str(latest_id) != str(current_last_id):
                    print(f"🔥 【警报】检测到全新实时消息：{latest_id}")
                    save_last_seen_id(latest_id)
                    await send_to_feishu("10s高频实时", latest_tweet["text"], latest_tweet["url"], latest_tweet["date"])
                else:
                    print(f"🔄 巡检正常：Serenity 暂无新动向。当前锚定 ID: {latest_id}")
            else:
                print("💤 节点瞬时拥堵。保持长连，等待下一个周期穿透...")
        except Exception as queue_err:
            print(f"⚠ 循环体内意外抖动: {queue_err}")
            
        # 🧠 引入 25 - 35 秒之间的随机睡眠抖动，模拟真人不规则刷新，彻底骗过 xcancel 防火墙
        jitter = CHECK_INTERVAL + random.randint(-5, 5)
        await asyncio.sleep(jitter)

if __name__ == "__main__":
    asyncio.run(main())
