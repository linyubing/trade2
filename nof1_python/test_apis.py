#!/usr/bin/env python3
"""
快速测试脚本 - 检查所有关键 API 调用是否正常
用法: python test_apis.py
"""
import sys
import time

def test_lm_studio():
    print("=" * 50)
    print("[1/3] 测试 LM Studio API...")
    try:
        import requests
        url = "http://127.0.0.1:1234/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer lm-studio-local"
        }
        payload = {
            "model": "local-model",
            "messages": [{"role": "user", "content": "只用一句话回答：1+1=?"}],
            "max_tokens": 50,
            "temperature": 0.1
        }
        start = time.time()
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        elapsed = time.time() - start
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"].get("content", "")[:50]
            print(f"  ✅ LM Studio 正常! (耗时 {elapsed:.2f}s)")
            print(f"     模型: {data.get('model', 'unknown')}")
            print(f"     回复: {content}")
            return True
        else:
            print(f"  ❌ HTTP {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False


def test_binance_proxy():
    print("=" * 50)
    print("[2/3] 测试 Binance Testnet API (通过代理)...")
    try:
        import requests
        # 从 .env 读取代理配置
        proxy = None
        try:
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("HTTP_PROXY="):
                        proxy = line.strip().split("=", 1)[1].strip()
                    elif line.startswith("HTTPS_PROXY="):
                        if not proxy:
                            proxy = line.strip().split("=", 1)[1].strip()
        except Exception:
            pass

        print(f"     代理: {proxy or '(无)'}")

        # 测试1: ping (不需要代理也能通，但 testnet 需要)
        url = "https://testnet.binancefuture.com/fapi/v1/ping"
        proxies = {"http": proxy, "https": proxy} if proxy else None
        start = time.time()
        resp = requests.get(url, proxies=proxies, timeout=15)
        elapsed = time.time() - start

        if resp.status_code == 200:
            print(f"  ✅ Binance Testnet Ping 正常! (耗时 {elapsed:.2f}s)")
        else:
            print(f"  ⚠️  Ping 返回 {resp.status_code}")

        # 测试2: 获取 BTCUSDT 价格
        url2 = "https://testnet.binancefuture.com/fapi/v1/ticker/price?symbol=BTCUSDT"
        start2 = time.time()
        resp2 = requests.get(url2, proxies=proxies, timeout=15)
        elapsed2 = time.time() - start2

        if resp2.status_code == 200:
            data = resp2.json()
            print(f"  ✅ Binance Testnet 价格接口正常! (耗时 {elapsed2:.2f}s)")
            print(f"     BTCUSDT 价格: {data.get('price', 'N/A')}")
            return True
        else:
            print(f"  ❌ 价格接口失败 HTTP {resp2.status_code}: {resp2.text[:200]}")
            return False

    except Exception as e:
        print(f"  ❌ 错误: {e}")
        print("  💡 提示: 请确认代理软件(Clash/V2Ray)是否正常运行")
        return False


def test_database():
    print("=" * 50)
    print("[3/3] 测试 MySQL 数据库连接...")
    try:
        import pymysql
        # 从 .env 读取数据库配置
        db_url = ""
        try:
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("DATABASE_URL="):
                        db_url = line.strip().split("=", 1)[1].strip()
                        break
        except Exception:
            pass

        if not db_url:
            print("  ⚠️  未找到 DATABASE_URL 配置，跳过")
            return None

        # 解析 mysql+pymysql://user:pass@host:port/dbname
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        user = parsed.username or "root"
        password = parsed.password or ""
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 3306
        database = parsed.path.lstrip("/") or "btc_quant"

        start = time.time()
        conn = pymysql.connect(
            host=host, port=port,
            user=user, password=password,
            database=database,
            connect_timeout=5
        )
        elapsed = time.time() - start
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
        conn.close()

        if result:
            print(f"  ✅ MySQL 连接正常! (耗时 {elapsed:.2f}s)")
            print(f"     主机: {host}:{port}  数据库: {database}")
            return True
        else:
            print("  ❌ 查询返回空")
            return False
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False


def test_binance_via_python_binance():
    print("=" * 50)
    print("[Bonus] 测试 python-binance 库 (完整初始化)...")
    try:
        from binance.client import Client
        import requests

        proxy = None
        try:
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("HTTP_PROXY="):
                        proxy = line.strip().split("=", 1)[1].strip()
        except Exception:
            pass

        # monkey-patch ping
        Client.ping = lambda self: None

        requests_params = {"timeout": 30}
        if proxy:
            requests_params["proxies"] = {"http": proxy, "https": proxy}

        client = Client(
            api_key="test", api_secret="test",
            testnet=False,
            requests_params=requests_params
        )
        client.API_URL = "https://testnet.binance.vision/api"
        client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"

        if proxy:
            client.session.proxies = {"http": proxy, "https": proxy}

        start = time.time()
        server_time = client.get_server_time()
        elapsed = time.time() - start

        print(f"  ✅ python-binance 初始化正常! (耗时 {elapsed:.2f}s)")
        print(f"     服务器时间: {server_time['serverTime']}")
        return True
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False


if __name__ == "__main__":
    print("\n🚀 API 连通性快速测试\n")

    results = []

    r1 = test_lm_studio()
    results.append(("LM Studio API", r1))

    r2 = test_binance_proxy()
    results.append(("Binance Testnet API", r2))

    r3 = test_database()
    results.append(("MySQL Database", r3 if r3 is not None else "skipped"))

    r4 = test_binance_via_python_binance()
    results.append(("python-binance 库", r4))

    # 汇总
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    print("=" * 50)
    for name, result in results:
        if result == "skipped":
            print(f"  ⚠️  {name}: 跳过 (未配置)")
        elif result:
            print(f"  ✅ {name}: 正常")
        else:
            print(f"  ❌ {name}: 失败")

    print("\n💡 使用建议:")
    if not r1:
        print("  - LM Studio 未响应，请确认 LM Studio 已启动并加载了模型")
    if not r2:
        print("  - Binance API 不通，请确认代理软件正常运行 (Clash/V2Ray)")
        print("  - 检查 .env 中 HTTP_PROXY/HTTPS_PROXY 配置是否正确")
    if r3 is False:
        print("  - 数据库连不上，请确认 MySQL 已启动")

    print()
    sys.exit(0 if all([r1, r2, r3 is not False, r4]) else 1)
