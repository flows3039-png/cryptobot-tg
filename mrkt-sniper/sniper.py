import asyncio
import aiohttp
import time
import json
import os
import sys
import random
from datetime import datetime

# Load environment variables (.env)
def load_env():
    # Try finding .env in script directory or parent directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, ".env"),
        os.path.join(os.path.dirname(base_dir), ".env")
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip()
                            if k and not os.environ.get(k):
                                os.environ[k] = v
            except Exception:
                pass

load_env()

# Enable UTF-8 and ANSI escape sequences in Windows Command Prompt
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
os.system("")

# ANSI Color Palette
RESET     = "\033[0m"
BOLD      = "\033[1m"
DIM       = "\033[2m"

C_CYAN    = "\033[38;2;34;211;238m"   # Neon Cyan
C_GREEN   = "\033[38;2;74;222;128m"   # Neon Green
C_PURPLE  = "\033[38;2;192;132;252m" # Neon Violet
C_YELLOW  = "\033[38;2;250;204;21m"   # Neon Gold
C_RED     = "\033[38;2;248;113;113m"  # Neon Red
C_GRAY    = "\033[38;2;148;163;184m"  # Slate Gray
C_DARK    = "\033[38;2;71;85;105m"    # Dark Slate
C_WHITE   = "\033[38;2;241;245;249m"  # Crisp White

# ==============================================================================
# НАСТРОЙКИ СНАЙПЕРА (MODRIX AUTO-FLIPPER ENGINE)
# ==============================================================================

POLL_INTERVAL_SEC      = 0.45       # Частота сканирования (450 мс)
PULSE_INTERVAL_SEC     = 45         # Пульс рынка (каждые 45 сек)
RADAR_INTERVAL_SEC     = 12         # Строка радара (каждые 12 сек)
MIN_PROFIT_PERCENT     = 20         # Минимальная базовая наценка при продаже (+20%)
MIN_DISCOUNT_PERCENT   = 12         # Минимальная скидка к флору для выкупа обычных лотов

# Сессия аккаунта
ACCESS_TOKEN = os.getenv("MRKT_ACCESS_TOKEN", "f63be9e2-bf98-4e54-b9eb-ef7ffa3ba054")
STEAM_ID     = os.getenv("MRKT_STEAM_ID", "76561198664065587")

# Telegram Bot уведомления
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID   = os.getenv("TG_CHAT_ID", "7162454634").strip()

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
TRADES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trades.json")

# Глобальное состояние торговли
STATE = {
    "balance": 3.6157,
    "max_buy_price": 3.56,
    "total_scans": 0,
    "trades_count": 0,
    "total_profit_ton": 0.0,
    "market_floor": 3.81,
    "active_sales": {} # {gift_id: {"title": ..., "buy": ..., "sell": ...}}
}

# ==============================================================================
# TELEGRAM NOTIFIER
# ==============================================================================

async def send_tg_notification(session: aiohttp.ClientSession, message_text: str):
    """Отправляет мгновенное уведомление в Telegram MODRIX"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        async with session.post(url, json=payload, timeout=3.5) as resp:
            pass
    except Exception:
        pass

def save_trade_history(trade_entry: dict):
    """Сохраняет сделку в локальный trades.json"""
    try:
        trades = []
        if os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, "r", encoding="utf-8") as f:
                trades = json.load(f)
        trades.append(trade_entry)
        with open(TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(trades, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ==============================================================================
# АНАЛИЗАТОР РЕДКОСТИ И ФЛОРА КОЛЛЕКЦИЙ
# ==============================================================================

def check_rare_number(num):
    """Анализ номера подарка на редкость для премиальной наценки"""
    if not num:
        return None, 1.0
    s = str(num).strip()
    if not s.isdigit():
        return None, 1.0
    n = int(s)

    # 1. Первая сотня (#1 - #99)
    if 1 <= n <= 99:
        return f"ТОП-{n} (ПЕРВАЯ СОТНЯ)", 1.70  # +70% наценка

    # 2. Одинаковые цифры (#777, #111, #2222)
    if len(s) >= 2 and len(set(s)) == 1:
        return f"ОДИНАКОВЫЕ ЦИФРЫ #{s}", 1.60  # +60% наценка

    # 3. Зеркалка / Палиндром (#1221, #5005, #7887, #303)
    if len(s) >= 3 and s == s[::-1]:
        return f"ЗЕРКАЛКА #{s}", 1.45  # +45% наценка

    # 4. Круглые числа (#100, #500, #1000)
    if n in (100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 2000, 5000):
        return f"КРУГЛОЕ ЧИСЛО #{s}", 1.35  # +35% наценка

    return None, 1.0

def print_header():
    os.system("cls" if os.name == "nt" else "clear")
    tg_status = f"{C_GREEN}ПОДКЛЮЧЕН{RESET}" if TG_BOT_TOKEN else f"{C_GRAY}ОТКЛЮЧЕН{RESET}"
    logo = f"""
{C_CYAN}███╗   ███╗██████╗ ██╗  ██╗████████╗    {C_PURPLE}███████╗███╗   ██╗██╗██████╗ ███████╗██████╗ 
{C_CYAN}████╗ ████║██╔══██╗██║ ██╔╝╚══██╔══╝    {C_PURPLE}██╔════╝████╗  ██║██║██╔══██╗██╔════╝██╔══██╗
{C_CYAN}██╔████╔██║██████╔╝█████═╝    ██║       {C_PURPLE}███████╗██╔██╗ ██║██║██████╔╝█████╗  ██████╔╝
{C_CYAN}██║╚██╔╝██║██╔══██╗██╔═██╗    ██║       {C_PURPLE}╚════██║██║╚██╗██║██║██╔═══╝ ██╔══╝  ██╔══██╗
{C_CYAN}██║ ╚═╝ ██║██║  ██║██║ ╚██╗   ██║       {C_PURPLE}███████║██║ ╚████║██║██║     ███████╗██║  ██║
{C_CYAN}╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝       {C_PURPLE}╚══════╝╚═╝  ╚═══╝╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝{RESET}
{C_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
  {C_WHITE}АККАУНТ:{RESET}     {C_GREEN}MODRIX (2297417){RESET}     │  {C_WHITE}БАЛАНС:{RESET}      {C_YELLOW}{STATE['balance']:.4f} TON{RESET} (авто-разгон)
  {C_WHITE}МАКС. ВЫКУП:{RESET} {C_CYAN}<= {STATE['max_buy_price']:.2f} TON{RESET}        │  {C_WHITE}ФЛОР РЫНКА:{RESET}  {C_YELLOW}{STATE['market_floor']:.2f} TON{RESET}
  {C_WHITE}СКОРОСТЬ:{RESET}    {C_PURPLE}{int(POLL_INTERVAL_SEC*1000)} мс{RESET}               │  {C_WHITE}ПРИБЫЛЬ:{RESET}     {C_GREEN}+{STATE['total_profit_ton']:.2f} TON{RESET} ({STATE['trades_count']} сделок)
  {C_WHITE}ТЕЛЕГРАМ:{RESET}    {tg_status}             │  {C_WHITE}РЕЖИМ:{RESET}       {C_CYAN}МУЛЬТИ-СКАН (ФЛОР + СВЕЖИЕ){RESET}
  {C_WHITE}МОДУЛИ:{RESET}      {C_GREEN}RARE-HUNTER [ON]{RESET}     │  {C_GREEN}SMART-FLOOR [ON]{RESET} │  {C_GREEN}AUTO-RELIST [ON]{RESET}
{C_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
"""
    print(logo, flush=True)

def print_buy_banner(title: str, buy_price: float, sell_price: float, profit: float, rarity_label: str, col_floor: float, elapsed_ms: int):
    rarity_tag = f" {C_PURPLE}[{rarity_label}]{RESET}" if rarity_label else ""
    col_info = f" (Флор коллекции: {col_floor:.2f} TON)" if col_floor > 0 else ""
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
║                 {C_WHITE}{BOLD}ПОДАРОК УСПЕШНО ВЫКУПЛЕН С РЫНКА MRKT ЗА {elapsed_ms} МС!{RESET}{C_GREEN}                               ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝{RESET}
  {C_CYAN}▸ НАЗВАНИЕ:{RESET}    {C_WHITE}{BOLD}{title}{RESET}{rarity_tag}{col_info}
  {C_YELLOW}▸ ЦЕНА ВЫКУПА:{RESET} {C_GREEN}{buy_price:.2f} TON{RESET}
  {C_PURPLE}▸ АВТО-ЛИСТИНГ:{RESET}{C_WHITE} ВЫСТАВЛЕН НА ПРОДАЖУ ЗА {C_YELLOW}{sell_price:.2f} TON{RESET}
  {C_GREEN}▸ ЧИСТЫЙ ПРОФИТ:{RESET}{C_GREEN}{BOLD}+{profit:.2f} TON (после комиссии 2%){RESET}
{C_GRAY}────────────────────────────────────────────────────────────────────────────────────────────{RESET}
"""
    print(banner, flush=True)

async def refresh_account_balance(session: aiohttp.ClientSession):
    """Обновляет баланс и автоматически пересчитывает лимит покупки (авто-разгон)"""
    try:
        async with session.get(f"{API_BASE}/balance", headers=HEADERS, timeout=3.5) as resp:
            if resp.status == 200:
                data = await resp.json()
                bal = data.get("hard", 0) / 1e9
                STATE["balance"] = bal
                STATE["max_buy_price"] = max(1.0, round(bal - 0.05, 2))
                return bal
    except Exception:
        pass
    return STATE["balance"]

async def fetch_current_market_floor(session: aiohttp.ClientSession) -> float:
    """Опрашивает текущий флор рынка в реальном времени"""
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
                    f_ton = gifts[0].get("salePrice", 0) / 1e9
                    if f_ton > 0:
                        STATE["market_floor"] = f_ton
                        return f_ton
    except Exception:
        pass
    return STATE["market_floor"]

async def auto_relist_gift(session: aiohttp.ClientSession, gift_id: str, title: str, buy_price_ton: float, multiplier: float, col_floor: float):
    """Автоматически выставляет выкупленный подарок на продажу с максимальной прибылью"""
    await asyncio.sleep(0.3)
    
    # Умный расчет цены: если у этой коллекции высокий флор, берем его, а не дешевый глобальный флор
    target_floor = max(STATE["market_floor"], col_floor)
    base_sell = target_floor - 0.01 if target_floor > 0 else buy_price_ton * 1.22
    
    optimal_sell_price = round(max(buy_price_ton * 1.20, base_sell * multiplier), 2)
    sell_nano = int(optimal_sell_price * 1e9)

    sale_payload = {
        "ids": [gift_id],
        "price": sell_nano
    }

    try:
        async with session.post(f"{API_BASE}/gifts/sale", json=sale_payload, headers=HEADERS, timeout=4.0) as resp:
            now_str = datetime.now().strftime("%H:%M:%S")
            if resp.status in (200, 201):
                clean_profit = round(optimal_sell_price * 0.98 - buy_price_ton, 2)
                STATE["trades_count"] += 1
                STATE["total_profit_ton"] += clean_profit
                STATE["active_sales"][gift_id] = {
                    "title": title, "buy": buy_price_ton, "sell": optimal_sell_price, "col_floor": col_floor
                }
                print(f"  {C_GRAY}[{now_str}]{RESET} {C_GREEN}✔ АВТО-ЛИСТИНГ УСПЕШЕН:{RESET} {title} выставлен за {C_YELLOW}{optimal_sell_price:.2f} TON{RESET} (чистый плюс: {C_GREEN}+{clean_profit:.2f} TON{RESET})", flush=True)
                
                # Сохраняем в историю
                save_trade_history({
                    "timestamp": datetime.now().isoformat(),
                    "gift_id": gift_id,
                    "title": title,
                    "buy_price": buy_price_ton,
                    "sell_price": optimal_sell_price,
                    "expected_profit": clean_profit,
                    "collection_floor": col_floor
                })

                # Отправляем уведомление в Telegram
                tg_msg = (
                    f"📦 <b>АВТО-ЛИСТИНГ УСПЕШЕН</b>\n\n"
                    f"▸ <b>Подарок:</b> {title}\n"
                    f"▸ <b>Куплен за:</b> {buy_price_ton:.2f} TON\n"
                    f"▸ <b>Выставлен за:</b> {optimal_sell_price:.2f} TON\n"
                    f"▸ <b>Чистая прибыль:</b> +{clean_profit:.2f} TON\n"
                    f"▸ <b>Текущий баланс:</b> {STATE['balance']:.2f} TON"
                )
                asyncio.create_task(send_tg_notification(session, tg_msg))

                await refresh_account_balance(session)
            else:
                err = await resp.text()
                print(f"  {C_GRAY}[{now_str}]{RESET} {C_RED}✖ Ошибка авто-листинга [{resp.status}]:{RESET} {err[:140]}", flush=True)
    except Exception as e:
        print(f"  {C_RED}✖ Сбой авто-листинга:{RESET} {e}", flush=True)

async def check_and_adjust_sales(session: aiohttp.ClientSession):
    """Умная корректировка цен: если наш лот перебили, аккуратно двигаем цену на 0.01 TON ниже"""
    if not STATE["active_sales"]:
        return
    floor = await fetch_current_market_floor(session)
    for gid, item in list(STATE["active_sales"].items()):
        current_sell = item["sell"]
        buy_price = item["buy"]
        col_floor = item.get("col_floor", 0)
        reference_floor = col_floor if col_floor > 0 else floor

        min_allowed = round(buy_price * 1.15, 2)
        if reference_floor < current_sell and (reference_floor - 0.01) >= min_allowed:
            new_price = round(reference_floor - 0.01, 2)
            try:
                ch_payload = {"ids": [gid], "newPrice": int(new_price * 1e9)}
                async with session.post(f"{API_BASE}/gifts/sale/change-price", json=ch_payload, headers=HEADERS, timeout=3.0) as resp:
                    if resp.status in (200, 201):
                        now_str = datetime.now().strftime("%H:%M:%S")
                        item["sell"] = new_price
                        print(f"  {C_GRAY}[{now_str}]{RESET} {C_CYAN}⚡ СМАРТ-КОРРЕКТИРОВКА:{RESET} Цена {item['title']} снижена до {C_YELLOW}{new_price:.2f} TON{RESET}", flush=True)
                        
                        tg_msg = (
                            f"🔄 <b>СМАРТ-КОРРЕКТИРОВКА ЦЕНЫ</b>\n\n"
                            f"▸ <b>Подарок:</b> {item['title']}\n"
                            f"▸ <b>Новая цена:</b> {new_price:.2f} TON (первый в стакане)"
                        )
                        asyncio.create_task(send_tg_notification(session, tg_msg))
            except Exception:
                pass

async def execute_buy(session: aiohttp.ClientSession, gift: dict, rarity_label: str, multiplier: float):
    gift_id = gift.get("id")
    raw_price = gift.get("salePrice", 0)
    buy_price_ton = raw_price / 1e9 if raw_price > 1e6 else raw_price
    title = gift.get("title") or gift.get("name") or "NFT Gift"
    num = gift.get("num") or gift.get("number")
    display_name = f"{title} #{num}" if num else title
    col_floor = (gift.get("floorPriceNanoTONsByCollection") or 0) / 1e9

    now_str = datetime.now().strftime("%H:%M:%S")
    reason = f"[{rarity_label}]" if rarity_label else f"[Выгодный флор {col_floor:.2f} TON]" if col_floor > buy_price_ton * 1.15 else f"[Скидка к флору]"
    print(f"\n{C_YELLOW}⚡ [{now_str}] ЦЕЛЬ ОБНАРУЖЕНА {reason}:{RESET} {C_WHITE}{display_name}{RESET} за {C_GREEN}{buy_price_ton:.2f} TON{RESET}! Моментальный выкуп...", flush=True)

    buy_payload = {
        "ids": [gift_id],
        "prices": {str(gift_id): raw_price}
    }

    t0 = time.perf_counter()
    try:
        async with session.post(f"{API_BASE}/gifts/buy", json=buy_payload, headers=HEADERS, timeout=4.0) as resp:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if resp.status in (200, 201):
                target_floor = max(STATE["market_floor"], col_floor)
                base_sell = target_floor - 0.01 if target_floor > 0 else buy_price_ton * 1.22
                sell_est = round(max(buy_price_ton * 1.20, base_sell * multiplier), 2)
                profit_est = round(sell_est * 0.98 - buy_price_ton, 2)
                
                print_buy_banner(display_name, buy_price_ton, sell_est, profit_est, rarity_label, col_floor, elapsed_ms)

                # Мгновенный Telegram пуш о выкупе
                tg_msg = (
                    f"⚡ <b>ПОДАРОК ВЫКУПЛЕН С РЫНКА!</b>\n\n"
                    f"▸ <b>Название:</b> {display_name}\n"
                    f"▸ <b>Скорость:</b> {elapsed_ms} мс\n"
                    f"▸ <b>Цена покупки:</b> {buy_price_ton:.2f} TON\n"
                    f"▸ <b>Флор коллекции:</b> {col_floor:.2f} TON\n"
                    f"▸ <b>План продажи:</b> {sell_est:.2f} TON\n"
                    f"▸ <b>Ожидаемый профит:</b> +{profit_est:.2f} TON"
                )
                asyncio.create_task(send_tg_notification(session, tg_msg))

                # Автоматический перевыставление
                asyncio.create_task(auto_relist_gift(session, gift_id, display_name, buy_price_ton, multiplier, col_floor))
            else:
                err_text = await resp.text()
                print(f"{C_RED}[ОШИБКА ВЫКУПА {resp.status} ({elapsed_ms} мс)]{RESET} {err_text[:160]}", flush=True)
    except Exception as e:
        print(f"{C_RED}[СБОЙ СЕТИ ПРИ ВЫКУПЕ]{RESET} {e}", flush=True)

async def run_sniper():
    conn = aiohttp.TCPConnector(limit=30, keepalive_timeout=75)
    async with aiohttp.ClientSession(connector=conn) as session:
        await refresh_account_balance(session)
        await fetch_current_market_floor(session)
        print_header()

        seen_ids = set()
        last_pulse_time = 0
        last_radar_time = time.time()
        last_adjust_time = time.time()
        scan_cycle = 0

        # Приветственное уведомление в Telegram
        if TG_BOT_TOKEN and TG_CHAT_ID:
            start_msg = (
                f"🟢 <b>MRKT SNIPER АКТИВИРОВАН</b>\n\n"
                f"▸ <b>Аккаунт:</b> MODRIX (2297417)\n"
                f"▸ <b>Баланс:</b> {STATE['balance']:.4f} TON\n"
                f"▸ <b>Макс. выкуп:</b> &lt;= {STATE['max_buy_price']:.2f} TON\n"
                f"▸ <b>Текущий флор:</b> {STATE['market_floor']:.2f} TON\n"
                f"▸ <b>Модули:</b> Смарт-Флор, Редкие номера, Авто-листинг"
            )
            asyncio.create_task(send_tg_notification(session, start_msg))

        now_init = datetime.now().strftime("%H:%M:%S")
        print(f"  {C_GRAY}[{now_init}]{RESET} {C_GREEN}● ТОРГОВЫЙ ДВИЖОК АКТИВИРОВАН:{RESET} Двойное сканирование (флор + свежие) запущено...", flush=True)

        while True:
            STATE["total_scans"] += 1
            scan_cycle += 1
            t_start = time.perf_counter()
            current_time = time.time()

            max_nano = int(STATE["max_buy_price"] * 1e9)

            # 1. Пульс рынка (каждые 45 сек)
            if current_time - last_pulse_time >= PULSE_INTERVAL_SEC:
                last_pulse_time = current_time
                try:
                    p_load = {
                        "count": 10, "cursor": "",
                        "collectionNames": [], "modelNames": [], "backdropNames": [], "symbolNames": [],
                        "ordering": 2, "lowToHigh": True
                    }
                    async with session.post(f"{API_BASE}/gifts/saling", json=p_load, headers=HEADERS, timeout=3.0) as p_resp:
                        if p_resp.status == 200:
                            p_data = await p_resp.json()
                            p_gifts = p_data.get("gifts", [])
                            if p_gifts:
                                STATE["market_floor"] = p_gifts[0].get("salePrice", 0) / 1e9
                                sample = random.sample(p_gifts, min(2, len(p_gifts)))
                                now_str = datetime.now().strftime("%H:%M:%S")
                                g1, g2 = sample[0], sample[1]
                                p1 = g1.get("salePrice", 0) / 1e9
                                p2 = g2.get("salePrice", 0) / 1e9
                                t1 = g1.get("title") or g1.get("name")
                                t2 = g2.get("title") or g2.get("name")
                                n1 = f"#{g1.get('num') or g1.get('number')}" if (g1.get('num') or g1.get('number')) else ""
                                n2 = f"#{g2.get('num') or g2.get('number')}" if (g2.get('num') or g2.get('number')) else ""
                                print(f"  {C_GRAY}[{now_str}]{RESET} {C_PURPLE}● ПУЛЬС РЫНКА:{RESET} {C_WHITE}{t1} {n1}{RESET} ({C_YELLOW}{p1:.2f} TON{RESET}) │ {C_WHITE}{t2} {n2}{RESET} ({C_YELLOW}{p2:.2f} TON{RESET}) {C_DARK}│ Проверок: {STATE['total_scans']}{RESET}", flush=True)
                except Exception:
                    pass

            # 2. Строка радара (каждые 12 сек)
            if current_time - last_radar_time >= RADAR_INTERVAL_SEC:
                last_radar_time = current_time
                now_str = datetime.now().strftime("%H:%M:%S")
                profit_info = f"│ {C_GREEN}Профит: +{STATE['total_profit_ton']:.2f} TON{RESET} " if STATE['total_profit_ton'] > 0 else ""
                print(f"  {C_GRAY}[{now_str}]{RESET} {C_CYAN}⚡ СКАНИРОВАНИЕ...{RESET} {C_DARK}Проверок:{RESET} {C_WHITE}{STATE['total_scans']}{RESET} │ {C_DARK}Флор:{RESET} {C_YELLOW}{STATE['market_floor']:.2f} TON{RESET} │ {C_DARK}Выкуп до:{RESET} {C_GREEN}{STATE['max_buy_price']:.2f} TON{RESET} {profit_info}", flush=True)

            # 3. Периодическая проверка и смарт-корректировка выставленных лотов (раз в 5 минут)
            if current_time - last_adjust_time >= 300:
                last_adjust_time = current_time
                asyncio.create_task(check_and_adjust_sales(session))

            # 4. Двойное сканирование (чередуем поток дешевых лотов и свежих поступлений)
            if scan_cycle % 2 == 0:
                # Поток А: Самые дешевые лоты с лимитом цены
                search_payload = {
                    "count": 15, "cursor": "",
                    "collectionNames": [], "modelNames": [], "backdropNames": [], "symbolNames": [],
                    "ordering": 2, "lowToHigh": True, "maxPrice": max_nano
                }
            else:
                # Поток Б: Свежий рынок (включая дорогие коллекции, где кто-то слил за бесценок)
                search_payload = {
                    "count": 20, "cursor": "",
                    "collectionNames": [], "modelNames": [], "backdropNames": [], "symbolNames": [],
                    "ordering": 0, "lowToHigh": True
                }

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

                                price_nano = gift.get("salePrice", 0)
                                price_ton = price_nano / 1e9
                                num = gift.get("num") or gift.get("number")
                                col_floor = (gift.get("floorPriceNanoTONsByCollection") or 0) / 1e9

                                # Если лот дороже нашего баланса — пропускаем
                                if price_nano > max_nano:
                                    continue

                                seen_ids.add(gid)

                                # Анализ на редкий номер
                                rarity_label, multiplier = check_rare_number(num)

                                # Условия на выкуп:
                                # 1. Редкий номер (топ 1-99, 777, зеркалка)
                                # 2. Дорогая коллекция со сливом цены (флор коллекции сильно выше цены продажи)
                                # 3. Обычный лот ниже рынка
                                is_high_floor_deal = (col_floor >= price_ton * 1.15)
                                is_rare = (rarity_label is not None)
                                is_cheap = (price_nano <= max_nano)

                                if is_rare or is_high_floor_deal or is_cheap:
                                    asyncio.create_task(execute_buy(session, gift, rarity_label, multiplier))

                    elif resp.status == 401:
                        now_str = datetime.now().strftime("%H:%M:%S")
                        print(f"  {C_GRAY}[{now_str}]{RESET} {C_RED}✖ Ошибка 401: Сессия устарела. Обновите токен.{RESET}", flush=True)
                        await asyncio.sleep(6)
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
        print(f"\n{C_YELLOW}Снайпер корректно остановлен.{RESET}", flush=True)
