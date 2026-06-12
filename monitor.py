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

async def fetch_latest_tweet_via_api(username):
    """【高性能免登录直连网关】支持全文本返回兼容，免疫任何302拦截"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 采用高连通的轻量解析网关
    nodes = ["https://api.vxtwitter.com", "https://api.fxtwitter.com"]
    for node in nodes:
        url = f"{node}/{username}/latest"
        print(f"🔄 正在向云端开放网关 [{node}] 发起探测...")
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    # 强行尝试进行 JSON 结构转化
                    try:
                        data = response.json()
                        tweet_data = data.get("tweet") or data.get("tweets", [{}])
                        if tweet_data:
                            tweet_id = tweet_data.get("id_str") or str(tweet_data.get("id"))
                            text = tweet_data.get("text") or tweet_data.get("description") or "查看原推文详情"
                            link = f"https://x.com/{username}/status/{tweet_id}"
                            pub_date = tweet_data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            return {"id": tweet_id, "text": text, "url": link, "date": pub_date}
                    except Exception:
                        # 兼容处理：如果节点返回了文本 HTML 包装，改用正则硬切片
                        text_content = response.text
                        id_match = re.search(r'"id_str":"(\d+)"', text_content)
                        if id_match:
                            tweet_id = id_match.group(1)
                            link = f"https://x.com/{username}/status/{tweet_id}"
                            return {"id": tweet_id, "text": "捕获到新动态，点击链接前往查看", "url": link, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            except Exception as e:
                print(f"⚠ 网关 [{node}] 产生轻微震荡: {e}，尝试下一组备用通道...")
    return None

async def main():
    if not FEISHU_WEBHOOK:
        print("❌ 错误：飞书 Webhook 环境变量未配置！")
        sys.exit(1)

    print(f"🎯 分布式免登录雷达重新校准启动，锁定目标: {TARGET_USER}")
    start_time = datetime.now()
    print(f"🛰️ 守护进程已进入强制监听状态...")

    # 核心修正：确保不管数据拿没拿到，10秒等待严格被包裹在 while 死循环内部
    while (datetime.now() - start_time).total_seconds() < LIFETIME:
        try:
            tweet = await fetch_latest_tweet_via_api(TARGET_USER)
            if tweet:
                latest_id = tweet["id"]
                last_id = get_last_seen_id()

                if last_id is None:
                    save_last_seen_id(latest_id)
                    print(f"📍 记忆库初始化成功！最新推文已锚定为 ID: {latest_id}")
                elif str(latest_id) != str(last_id):
                    print(f"🔥 捕获到全新实时消息：{latest_id}")
                    save_last_seen_id(latest_id)
                    await send_to_feishu(tweet["text"], tweet["url"], tweet["date"])
                else:
                    print(f"✅ 探测完毕：当前未发生推文变动，ID 保持一致 ({latest_id})。")
            else:
                print("💤 网关并发限流中，未获取到结构化切片。保持常驻，下一个10秒重新轮询...")
        except Exception as queue_err:
            print(f"⚠ 循环体内意外抖动: {queue_err}")
            
        # 🟢 【关键修正】这一行强制睡眠现在被提到了最外层，百分之百不会引发脚本意外提早退出了！
        await asyncio.sleep(CHECK_INTERVAL)
        
    print("👋 本轮长循环安全期满，主动退出并请求下一班容器交接。")

if __name__ == "__main__":
    asyncio.run(main())
