# ==================== 🛠️ 生产级配置中心 ====================
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")
TARGET_USER = "serenityX"    # 👈 锁定你要盯死的目标 ID
CHECK_INTERVAL = 10          # 🔥 严格 10 秒刷新一次
LIFETIME = 21000             # 🔥 运行 5.8 小时自动换班
# =======================================================

# 📡 【高连通开放 JSON 网关矩阵】专门对抗 302 登录风控
JSON_NODES = [
    "https://vxtwitter.com",         # 节点1：专门解析推文的高速中转网关
    "https://fxtwitter.com",         # 节点2：备用 FX 镜像解析网关
    "https://nitter.net"                 # 节点3：经典 Nitter 匿名网络节点
]

async def fetch_latest_tweet_via_rss(username):
    """【JSON 解析引擎】通过直接获取结构化数据，彻底解决 RSSHub 302 拦截问题"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for node in JSON_NODES:
        # 注意：这里改用直接请求最新推文 JSON 的 API 路径
        url = f"{node}/{username}/latest" if "api" in node else f"{node}/{username}/rss"
        print(f"🔄 正在通过高连通节点 [{node}] 尝试抓取实时动态...")
        
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=headers)
                
                # 情况 A：如果命中高连通的 JSON 节点
                if response.status_code == 200 and "application/json" in response.headers.get("content-type", "").lower():
                    data = response.json()
                    # 兼容不同镜像返回的 JSON 数据格式
                    tweet_data = data.get("tweet") or data.get("tweets", [{}])[0]
                    if tweet_data:
                        tweet_id = tweet_data.get("id_str") or str(tweet_data.get("id"))
                        text = tweet_data.get("text") or tweet_data.get("description", "查看原推文内容")
                        link = f"https://x.com{username}/status/{tweet_id}"
                        pub_date = tweet_data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        print(f"✅ 开放 JSON 节点 [{node}] 通道畅通！")
                        return {"id": tweet_id, "text": text, "url": link, "date": pub_date}
                
                # 情况 B：如果是传统的 Nitter RSS 节点
                elif response.status_code == 200 and "<item>" in response.text:
                    item_match = re.search(r'<item>(.*?)</item>', response.text, re.DOTALL)
                    if item_match:
                        item_content = item_match.group(1)
                        title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item_content) or re.search(r'<title>(.*?)</title>', item_content)
                        title = title_match.group(1) if title_match else "查看原推文内容"
                        link_match = re.search(r'<link>(.*?)</link>', item_content)
                        link = link_match.group(1).strip() if link_match else f"https://x.com{username}"
                        date_match = re.search(r'<pubDate>(.*?)</pubDate>', item_content)
                        pub_date = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        tweet_id = link.split("/status/")[-1].strip() if "/status/" in link else str(hash(title))
                        
                        print(f"✅ RSS 备份节点 [{node}] 通道畅通！")
                        return {"id": tweet_id, "text": title, "url": link, "date": pub_date}
                        
                print(f"⚠ 节点 [{node}] 返回了无效格式或状态码: {response.status_code}，切流...")
                
            except Exception as e:
                print(f"❌ 节点 [{node}] 连接发生异常: {e}，正在切换下一组热备...")
                
    print("🚨 警告：本轮高频探测中全网热备节点均未能建立连通。")
    return None
