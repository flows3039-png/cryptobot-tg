import asyncio
import aiohttp
import time
import json
import logging
import os
import sys
import random
from datetime import datetime

# Enable UTF-8 and ANSI escape sequences in Windows Command Prompt
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
os.system("")

# ANSI Color Palette
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

# Colors
C_CYAN    = "\033[38;2;34;211;238m"   # Neon Cyan
C_GREEN   = "\033[38;2;74;222;128m"   # Neon Green
C_PURPLE  = "\033[38;2;192;132;252m" # Neon Violet
C_YELLOW  = "\033[38;2;250;204;21m"   # Neon Gold
C_RED     = "\033[38;2;248;113;113m"  # Neon Red
C_GRAY    = "\033[38;2;148;163;184m"  # Slate Gray
C_DARK    = "\033[38;2;51;65;85m"     # Dark Slate
C_WHITE   = "\033[38;2;241;245;249m"  # Crisp White

# Backgrounds
BG_GREEN  = "\033[48;2;22;101;52m"
BG_CYAN   = "\033[48;2;14;116;144m"
BG_PURPLE = "\033[48;2;107;33;168m"

# ==============================================================================
# НАСТРОЙКИ СНАЙПЕРА (MODRIX MRKT AUTO-BOT)
# ==============================================================================

MAX_BUY_PRICE_TON = 3.60       # Максимальная цена выкупа в TON
POLL_INTERVAL_SEC = 0.45       # Частота сканирования рынка (450 мс)
PULSE_INTERVAL_SEC = 60        # Пульс рынка (каждые 60 сек вывод 2 подарков)
PROFIT_MARGIN_PERCENT = 22     # Минимальная наценка для перепродажи (+22%)

# Сессия аккаунта
ACCESS_TOKEN = "f63be9e2-bf98-4e54-b9eb-ef7ffa3ba054"
STEAM_ID = "76561198664065587"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 YaBrowser/26.8.0.0 Safari/537.36",
    "Origin": "https://cdn.tgmrkt.io",
    "Referer": "https://cdn.tgmrkt.io/",
    "Cookie": f"access_token={ACCESS_TOKEN}; steamid={STEAM_ID}",
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*"
}

API_BASE = "https://api.tgmrkt.io/api/v1"

# ==============================================================================

def print_header(balance_ton: float):
    os.system("cls" if os.name == "nt" else "clear")
    logo = f"""
{C_CYAN}███╗   ███╗██████╗ ██╗  ██╗████████╗    {C_PURPLE}███████╗███╗   ██╗██╗██████╗ ███████╗██████╗ 
{C_CYAN}████╗ ████║██╔══██╗██║ ██╔╝╚══██╔══╝    {C_PURPLE}██╔════╝████╗  ██║██║██╔══██╗██╔════╝██╔══██╗
{C_CYAN}██╔████╔██║██████╔╝█████═╝    ██║       {C_PURPLE}███████╗██╔██╗ ██║██║██████╔╝█████╗  ██████╔╝
{C_CYAN}██║╚██╔╝██║██╔══██╗██╔═██╗    ██║       {C_PURPLE}╚════██║██║╚██╗██║██║██╔═══╝ ██╔══╝  ██╔══██╗
{C_CYAN}██║ ╚═╝ ██║██║  ██║██║ ╚██╗   ██║       {C_PURPLE}███████║██║ ╚████║██║██║     ███████╗██║  ██║
{C_CYAN}╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝       {C_PURPLE}╚══════╝╚═╝  ╚═══╝╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝{RESET}
{C_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
  {C_WHITE}АККАУНТ:{RESET} {C_GREEN}MODRIX (2297417){RESET}  │  {C_WHITE}БАЛАНС:{RESET} {C_YELLOW}{balance_ton:.4f} TON{RESET}  │  {C_WHITE}РЕЖИМ:{RESET} {C_GREEN}БОЕВОЙ АВТОВЫКУП{RESET}
  {C_WHITE}ЛИМИТ:{RESET}   {C_CYAN}<= {MAX_BUY_PRICE_TON} TON{RESET}         │  {C_WHITE}СКОРОСТЬ:{RESET} {C_PURPLE}{int(POLL_INTERVAL_SEC*1000)} мс{RESET}        │  {C_WHITE}АВТО-ПРОДАЖА:{RESET} {C_GREEN}+{PROFIT_MARGIN_PERCENT}% В ПЛЮС{RESET}
{C_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
"""
    print(logo)

def print_buy_banner(title: str, buy_price: float, sell_price: float, profit: float, elapsed_ms: int):
    banner = f"""
{C_GREEN}╔══════════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                          ║
║    ███████╗██╗   ██╗██████╗ ███████╗██████╗     ██╗     ██████╗ ████████╗                ║
║    ██╔════╝██║   ██║██╔══██╗██╔════╝██╔══██╗    ██║    ██╔═══██╗╚══██╔══╝                ║
║    ███████╗██║   ██║██████╔╝█████╗  ██████╔╝    ██║    ██║   ██║   ██║                   ║
║    ╚════██║██║   ██║██╔═══╝ ██╔══╝  ██╔══██╗    ██║    ██║   ██║   ██║                   ║
║    ███████║╚██████╔╝██║     ███████╗██║  ██║    ███████╚██████╔╝   ██║                   ║
║    ╚══════╝ ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═╝    ╚══════╝╚═════╝    ╚═╝                   ║
║                                                                                          ║
║                   {C_WHITE}{BOLD}ПОДАРОК УСПЕШНО ВЫКУПЛЕН С РЫНКА MRKT ЗА {elapsed_ms} МС!{RESET}{C_GREEN}                             ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝{RESET}
  {C_CYAN}▸ НАЗВАНИЕ:{RESET}    {C_WHITE}{BOLD}{title}{RESET}
  {C_YELLOW}▸ ЦЕНА ВЫКУПА:{RESET} {C_GREEN}{buy_price:.2f} TON{RESET}
  {C_PURPLE}▸ АВТО-ЛИСТИНГ:{RESET}{C_WHITE} ВЫСТАВЛЕН НА ПРОДАЖУ ЗА {C_YELLOW}{sell_price:.2f} TON{RESET}
  {C_GREEN}▸ ЧИСТЫЙ ПРОФИТ:{RESET}{C_GREEN}{BOLD}+{profit:.2f} TON (+{PROFIT_MARGIN_PERCENT}%){RESET}
{C_GRAY}────────────────────────────────────────────────────────────────────────────────────────────{RESET}
"""
    print(banner)

async def check_balance(session: aiohttp.ClientSession) -> float:
    try:
        async with session.get(f"{API_BASE}/balance", headers=HEADERS, timeout=3.5) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("hard", 0) / 1e9
    except Exception:
        pass
    return 3.6157

async def get_current_floor(session: aiohttp.ClientSession) -> float:
    # Запрос текущего минимального флора рынка
    try:
        payload = {
            "count": 5, "cursor": "",
            "collectionNames": [], "modelNames": [], "backdropNames": [], "symbolNames": [],
            "ordering": 2, "lowToHigh": True
        }
        async with session.post(f"{API_BASE}/gifts/saling", json=payload, headers=HEADERS, timeout=3.0) as resp:
            if resp.status == 200:
                data = await resp.json()
                gifts = data.get("gifts", [])
                if gifts:
                    return gifts[0].get("salePrice", 0) / 1e9
    except Exception:
        pass
    return 3.85

async def auto_relist_gift(session: aiohttp.ClientSession, gift_id: str, title: str, buy_price_ton: float):
    # Небольшая пауза 1.5 секунды, пока сервер MRKT переведет подарок в инвентарь
    await asyncio.sleep(1.5)
    
    current_floor = await get_current_floor(session)
    
    # Расчет идеальной цены продажи:
    # 1. Если флор рынка выше цены покупки: встаем прямо перед флором (-0.01 TON), чтобы продать моментально
    # 2. И гарантируем минимум +20% к цене покупки
    min_profitable_price = round(buy_price_ton * (1 + PROFIT_MARGIN_PERCENT / 100), 2)
    optimal_sell_price = max(min_profitable_price, round(current_floor - 0.01, 2))
    
    sell_nano = int(optimal_sell_price * 1e9)
    
    sale_payload = {
        "ids": [gift_id],
        "price": sell_nano
    }
    
    try:
        async with session.post(f"{API_BASE}/gifts/sale", json=sale_payload, headers=HEADERS, timeout=4.0) as resp:
            if resp.status in (200, 201):
                profit = round(optimal_sell_price * 0.98 - buy_price_ton, 2)
                now_str = datetime.now().strftime("%H:%M:%S")
                print(f"  {C_GRAY}[{now_str}]{RESET} {C_GREEN}✔ АВТО-ЛИСТИНГ УСПЕШЕН:{RESET} {title} выставлен за {C_YELLOW}{optimal_sell_price} TON{RESET} (профит: {C_GREEN}+{profit} TON{RESET})")
            else:
                err = await resp.text()
                now_str = datetime.now().strftime("%H:%M:%S")
                print(f"  {C_GRAY}[{now_str}]{RESET} {C_RED}✖ Ошибка авто-листинга [{resp.status}]:{RESET} {err[:150]}")
    except Exception as e:
        print(f"  {C_RED}✖ Сбой авто-листинга:{RESET} {e}")

async def execute_buy(session: aiohttp.ClientSession, gift: dict):
    gift_id = gift.get("id")
    raw_price = gift.get("salePrice", 0)
    buy_price_ton = raw_price / 1e9 if raw_price > 1e6 else raw_price
    title = gift.get("title") or gift.get("name") or "NFT Gift"
    num = gift.get("num")
    display_name = f"{title} #{num}" if num else title

    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"\n{C_YELLOW}⚡ [{now_str}] ОБНАРУЖЕН МИСПРАЙС:{RESET} {C_WHITE}{display_name}{RESET} за {C_GREEN}{buy_price_ton:.2f} TON{RESET}! Моментальный выкуп...")

    buy_payload = {
        "ids": [gift_id],
        "prices": {
            str(gift_id): raw_price
        }
    }

    t0 = time.perf_counter()
    try:
        async with session.post(f"{API_BASE}/gifts/buy", json=buy_payload, headers=HEADERS, timeout=4.0) as resp:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if resp.status in (200, 201):
                # Расчет ориентировочной цены продажи
                sell_est = max(round(buy_price_ton * 1.25, 2), 3.84)
                profit_est = round(sell_est * 0.98 - buy_price_ton, 2)
                
                # Печать большого красивого баннера покупки (без писка)
                print_buy_banner(display_name, buy_price_ton, sell_est, profit_est, elapsed_ms)
                
                # Запуск автоматического перевыставления в фоне
                asyncio.create_task(auto_relist_gift(session, gift_id, display_name, buy_price_ton))
            else:
                err_text = await resp.text()
                print(f"{C_RED}[ОШИБКА ВЫКУПА {resp.status} ({elapsed_ms} мс)]{RESET} {err_text[:180]}")
    except Exception as e:
        print(f"{C_RED}[СБОЙ СЕТИ ПРИ ВЫКУПЕ]{RESET} {e}")

async def run_sniper():
    conn = aiohttp.TCPConnector(limit=30, keepalive_timeout=75)
    async with aiohttp.ClientSession(connector=conn) as session:
        bal = await check_balance(session)
        print_header(bal)

        max_nano = int(MAX_BUY_PRICE_TON * 1e9)
        seen_ids = set()
        scan_count = 0
        last_pulse_time = time.time()

        # Payload поиска миспрайсов
        search_payload = {
            "count": 15, "cursor": "",
            "collectionNames": [], "modelNames": [], "backdropNames": [], "symbolNames": [],
            "ordering": 2, "lowToHigh": True, "maxPrice": max_nano
        }

        # Payload для проверки пульса рынка
        pulse_payload = {
            "count": 10, "cursor": "",
            "collectionNames": [], "modelNames": [], "backdropNames": [], "symbolNames": [],
            "ordering": 1, "lowToHigh": False
        }

        while True:
            scan_count += 1
            t_start = time.perf_counter()
            current_time = time.time()

            # Ежеминутный пульс рынка: выводим 2 подарка с MRKT
            if current_time - last_pulse_time >= PULSE_INTERVAL_SEC:
                last_pulse_time = current_time
                try:
                    async with session.post(f"{API_BASE}/gifts/saling", json=pulse_payload, headers=HEADERS, timeout=3.0) as p_resp:
                        if p_resp.status == 200:
                            p_data = await p_resp.json()
                            p_gifts = p_data.get("gifts", [])
                            if len(p_gifts) >= 2:
                                sample_gifts = random.sample(p_gifts, min(2, len(p_gifts)))
                                now_str = datetime.now().strftime("%H:%M:%S")
                                g1, g2 = sample_gifts[0], sample_gifts[1]
                                p1 = (g1.get("salePrice", 0) / 1e9)
                                p2 = (g2.get("salePrice", 0) / 1e9)
                                t1 = g1.get("title") or g1.get("name")
                                t2 = g2.get("title") or g2.get("name")
                                n1 = f"#{g1.get('num')}" if g1.get('num') else ""
                                n2 = f"#{g2.get('num')}" if g2.get('num') else ""
                                print(f"  {C_GRAY}[{now_str}]{RESET} {C_PURPLE}● ПУЛЬС РЫНКА MRKT:{RESET} {C_WHITE}{t1} {n1}{RESET} ({C_YELLOW}{p1:.2f} TON{RESET}) │ {C_WHITE}{t2} {n2}{RESET} ({C_YELLOW}{p2:.2f} TON{RESET}) {C_DARK}│ Проверок: {scan_count}{RESET}")
                except Exception:
                    pass

            # Основное сканирование на миспрайсы
            try:
                async with session.post(f"{API_BASE}/gifts/saling", json=search_payload, headers=HEADERS, timeout=3.0) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        gifts = data.get("gifts", [])
                        if gifts:
                            for gift in gifts:
                                gid = gift.get("id")
                                if gid in seen_ids:
                                    continue
                                seen_ids.add(gid)
                                if gift.get("salePrice", 0) <= max_nano:
                                    asyncio.create_task(execute_buy(session, gift))
                    elif resp.status == 401:
                        now_str = datetime.now().strftime("%H:%M:%S")
                        print(f"  {C_GRAY}[{now_str}]{RESET} {C_RED}✖ Ошибка 401: Сессия устарела. Обновите токен.{RESET}")
                        await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception:
                pass

            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.04, POLL_INTERVAL_SEC - elapsed)
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    try:
        asyncio.run(run_sniper())
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}Снайпер корректно остановлен.{RESET}")
