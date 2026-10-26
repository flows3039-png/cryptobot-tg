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

# Telegram Bot
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
    "active_sales": {}, # {gift_id: {"title": ..., "buy": ..., "sell": ..., "col_floor": ...}}
    "paused": False,
    "start_time": time.time()
}

def update_session_token(new_token: str):
    """Обновляет токен сессии на лету и сохраняет в .env"""
    global ACCESS_TOKEN
    ACCESS_TOKEN = new_token
    HEADERS["Cookie"] = f"access_token={ACCESS_TOKEN}; steamid={STEAM_ID}"
    HEADERS["Authorization"] = f"Bearer {ACCESS_TOKEN}"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base_dir, ".env")
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        has_tok = False
        new_lines = []
        for line in lines:
            if line.startswith("MRKT_ACCESS_TOKEN="):
                new_lines.append(f"MRKT_ACCESS_TOKEN={new_token}\n")
                has_tok = True
            else:
                new_lines.append(line)
        if not has_tok:
            new_lines.append(f"MRKT_ACCESS_TOKEN={new_token}\n")
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception:
        pass

# ==============================================================================
# TELEGRAM INTERACTIVE COMMAND CENTER
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

async def telegram_command_listener(session: aiohttp.ClientSession):
    """Двустороннее управление снайпером с телефона через Telegram"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    offset = 0
    updates_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/getUpdates"
    send_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

    while True:
        try:
            params = {"offset": offset, "timeout": 15}
            async with session.get(updates_url, params=params, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        msg = update.get("message")
                        if not msg:
                            continue
                        from_id = str(msg.get("from", {}).get("id"))
                        if from_id != TG_CHAT_ID:
                            continue
                        
                        raw_text = (msg.get("text") or "").strip()
                        if not raw_text:
                            continue
                        
                        parts = raw_text.split()
                        cmd = parts[0].lower()
                        args = parts[1:]

                        reply = ""
                        if cmd in ("/start", "/help"):
                            reply = (
                                "⚡ <b>MRKT SNIPER // MODRIX COMMAND CENTER</b>\n\n"
                                "▸ /status — статус сканера, аптайм и флор\n"
                                "▸ /balance — баланс аккаунта в реальном времени\n"
                                "▸ /trades — история сделок и профит\n"
                                "▸ /pause — поставить авто-выкуп на паузу\n"
                                "▸ /resume — возобновить снайпинг\n"
                                "▸ /setbuy &lt;ton&gt; — задать лимит выкупа\n"
                                "▸ /token &lt;token&gt; — обновить токен сессии"
                            )
                        elif cmd == "/status":
                            st = "⏸ ПАУЗА" if STATE.get("paused") else "▶ АКТИВЕН"
                            uptime_sec = int(time.time() - STATE.get("start_time", time.time()))
                            m, s = divmod(uptime_sec, 60)
                            h, m = divmod(m, 60)
                            reply = (
                                f"📊 <b>СТАТУС СНАЙПЕРА [{st}]</b>\n\n"
                                f"▸ <b>Аптайм:</b> {h}ч {m}м {s}с\n"
                                f"▸ <b>Проверок:</b> {STATE['total_scans']}\n"
                                f"▸ <b>Баланс:</b> {STATE['balance']:.4f} TON\n"
                                f"▸ <b>Флор маркета:</b> {STATE['market_floor']:.2f} TON\n"
                                f"▸ <b>Лимит выкупа:</b> &lt;= {STATE['max_buy_price']:.2f} TON\n"
                                f"▸ <b>Сделок:</b> {STATE['trades_count']}\n"
                                f"▸ <b>Профит:</b> +{STATE['total_profit_ton']:.2f} TON\n"
                                f"▸ <b>Активных лотов:</b> {len(STATE['active_sales'])}"
                            )
                        elif cmd == "/balance":
                            bal = await refresh_account_balance(session)
                            reply = f"💰 <b>ТЕКУЩИЙ БАЛАНС:</b> <code>{bal:.4f} TON</code>\nЛимит покупки: &lt;= {STATE['max_buy_price']:.2f} TON"
                        elif cmd == "/pause":
                            STATE["paused"] = True
                            reply = "⏸ <b>СНАЙПЕР ПРИОСТАНОВЛЕН.</b> Мониторинг рынка продолжается, но выкуп отключен."
                        elif cmd == "/resume":
                            STATE["paused"] = False
                            reply = "▶ <b>СНАЙПЕР ВОЗОБНОВЛЕН.</b> Авто-выкуп активен на полную мощность."
                        elif cmd == "/trades":
                            if not STATE["trades_count"]:
                                reply = "📈 <b>ИСТОРИЯ СДЕЛОК:</b> Сделок пока нет. Снайпер в ожидании целей."
                            else:
                                reply = (
                                    f"📈 <b>ИТОГИ ТОРГОВЛИ:</b>\n"
                                    f"▸ Сделок: {STATE['trades_count']}\n"
                                    f"▸ Чистая прибыль: <b>+{STATE['total_profit_ton']:.2f} TON</b>\n"
                                    f"▸ В продаже прямо сейчас: {len(STATE['active_sales'])} лотов"
                                )
                        elif cmd == "/setbuy":
                            if args:
                                try:
                                    val = float(args[0])
                                    STATE["max_buy_price"] = val
                                    reply = f"✔ <b>ЛИМИТ ВЫКУПА ИЗМЕНЕН:</b> &lt;= <code>{val:.2f} TON</code>"
                                except ValueError:
                                    reply = "✖ Неверный формат. Пример: <code>/setbuy 4.5</code>"
                            else:
                                reply = "✖ Укажи сумму: <code>/setbuy 4.5</code>"
                        elif cmd == "/token":
                            if args:
                                new_tok = args[0].strip()
                                update_session_token(new_tok)
                                reply = "✔ <b>ТОКЕН СЕССИИ ОБНОВЛЕН В ПАМЯТИ И .ENV</b>"
                            else:
                                reply = "✖ Укажи токен: <code>/token f63be...</code>"

                        if reply:
                            await session.post(send_url, json={"chat_id": TG_CHAT_ID, "text": reply, "parse_mode": "HTML"})
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(2)

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
# КОМПЛЕКСНЫЙ АНАЛИЗАТОР РЕДКОСТИ (НОМЕРА + ФОНЫ + МОДЕЛИ)
# ==============================================================================

def check_rare_number(num):
    """Анализ номера подарка на редкость"""
    if not num:
        return None, 1.0
    s = str(num).strip()
    if not s.isdigit():
        return None, 1.0
    n = int(s)

    if 1 <= n <= 99:
        return f"ТОП-{n} (ПЕРВАЯ СОТНЯ)", 1.70
    if len(s) >= 2 and len(set(s)) == 1:
        return f"ОДИНАКОВЫЕ ЦИФРЫ #{s}", 1.60
    if len(s) >= 3 and s == s[::-1]:
        return f"ЗЕРКАЛКА #{s}", 1.45
    if n in (100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 2000, 5000):
        return f"КРУГЛОЕ ЧИСЛО #{s}", 1.35

    return None, 1.0

def evaluate_gift_rarity(gift: dict):
    """
    Комплексная оценка редкости подарка:
    1. Номер
    2. Редкость фона (backdropRarityPerMille)
    3. Редкость модели (modelRarityPerMille)
    """
    labels = []
    multiplier = 1.0

    # 1. Номер
    num = gift.get("num") or gift.get("number")
    num_label, num_mult = check_rare_number(num)
    if num_label:
        labels.append(num_label)
        multiplier = max(multiplier, num_mult)

    # 2. Фон (в промилле, 15 = 1.5%)
    b_rpm = gift.get("backdropRarityPerMille")
    b_name = gift.get("backdropName") or "Фон"
    if b_rpm is not None and b_rpm > 0:
        if b_rpm <= 5:
            labels.append(f"МИФИЧЕСКИЙ ФОН {b_name} ({b_rpm/10:.1f}%)")
            multiplier = max(multiplier, 2.10)
        elif b_rpm <= 15:
            labels.append(f"ЭПИЧЕСКИЙ ФОН {b_name} ({b_rpm/10:.1f}%)")
            multiplier = max(multiplier, 1.65)
        elif b_rpm <= 30:
            labels.append(f"РЕДКИЙ ФОН {b_name} ({b_rpm/10:.1f}%)")
            multiplier = max(multiplier, 1.35)

    # 3. Модель
    m_rpm = gift.get("modelRarityPerMille")
    m_name = gift.get("modelName") or "Модель"
    if m_rpm is not None and m_rpm > 0:
        if m_rpm <= 5:
            labels.append(f"МИФИЧЕСКАЯ МОДЕЛЬ {m_name} ({m_rpm/10:.1f}%)")
            multiplier = max(multiplier, 2.00)
        elif m_rpm <= 20:
            labels.append(f"РЕДКАЯ МОДЕЛЬ {m_name} ({m_rpm/10:.1f}%)")
            multiplier = max(multiplier, 1.45)

    combined_label = " │ ".join(labels) if labels else None
    return combined_label, multiplier

def print_header():
    os.system("cls" if os.name == "nt" else "clear")
    tg_status = f"{C_GREEN}КОМАНДНЫЙ ЦЕНТР [ON]{RESET}" if TG_BOT_TOKEN else f"{C_GRAY}ОТКЛЮЧЕН{RESET}"
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
  {C_WHITE}ТЕЛЕГРАМ:{RESET}    {tg_status} │  {C_WHITE}УПРАВЛЕНИЕ:{RESET}  {C_CYAN}/status, /balance, /pause, /trades{RESET}
  {C_WHITE}МОДУЛИ:{RESET}      {C_GREEN}RARE-ATTRS [ON]{RESET}      │  {C_GREEN}SMART-FLOOR [ON]{RESET} │  {C_GREEN}AUTO-RELIST [ON]{RESET}
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
    """Обновляет баланс и автоматически пересчитывает лимит покупки"""
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
                
                save_trade_history({
                    "timestamp": datetime.now().isoformat(),
                    "gift_id": gift_id,
                    "title": title,
                    "buy_price": buy_price_ton,
                    "sell_price": optimal_sell_price,
                    "expected_profit": clean_profit,
                    "collection_floor": col_floor
                })

                tg_msg = (
                    f"📦 <b>АВТО-ЛИСТИНГ УСПЕШЕН</b>\n\n"
                    f"▸ <b>Подарок:</b> {title}\n"
                    f"▸ <b>Куплен за:</b> {buy_price_ton:.2f} TON\n"
                    f"▸ <b>Выставлен за:</b> {optimal_sell_price:.2f} TON\n"
                    f"▸ <b>Чистая прибыль:</b> +{clean_profit:.2f} TON\n"
                    f"▸ <b>Баланс:</b> {STATE['balance']:.2f} TON"
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
    if STATE.get("paused"):
        return

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

                tg_msg = (
                    f"⚡ <b>ПОДАРОК ВЫКУПЛЕН С РЫНКА!</b>\n\n"
                    f"▸ <b>Название:</b> {display_name}\n"
                    f"▸ <b>Скорость:</b> {elapsed_ms} мс\n"
                    f"▸ <b>Цена покупки:</b> {buy_price_ton:.2f} TON\n"
                    f"▸ <b>Флор коллекции:</b> {col_floor:.2f} TON\n"
                    f"▸ <b>План продажи:</b> {sell_est:.2f} TON\n"
                    f"▸ <b>Ожидаемый профит:</b> +{profit_est:.2f} TON"
                )
                if rarity_label:
                    tg_msg += f"\n▸ <b>Особенности:</b> {rarity_label}"

                asyncio.create_task(send_tg_notification(session, tg_msg))
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

        # Запуск фонового Telegram командного центра
        asyncio.create_task(telegram_command_listener(session))

        seen_ids = set()
        last_pulse_time = 0
        last_radar_time = time.time()
        last_adjust_time = time.time()
        scan_cycle = 0

        # Уведомление в Telegram о запуске
        if TG_BOT_TOKEN and TG_CHAT_ID:
            start_msg = (
                f"🟢 <b>MRKT SNIPER COMMAND CENTER АКТИВИРОВАН</b>\n\n"
                f"▸ <b>Баланс:</b> {STATE['balance']:.4f} TON\n"
                f"▸ <b>Лимит покупки:</b> &lt;= {STATE['max_buy_price']:.2f} TON\n"
                f"▸ <b>Текущий флор:</b> {STATE['market_floor']:.2f} TON\n"
                f"▸ <b>Модули:</b> Смарт-Флор, Редкие фоны/модели, Авто-листинг\n\n"
                f"<i>Напиши /help для просмотра доступных команд управления.</i>"
            )
            asyncio.create_task(send_tg_notification(session, start_msg))

        now_init = datetime.now().strftime("%H:%M:%S")
        print(f"  {C_GRAY}[{now_init}]{RESET} {C_GREEN}● ТОРГОВЫЙ ДВИЖОК АКТИВИРОВАН:{RESET} Двойное сканирование + Rarity Hunter + TG командный центр запущены...", flush=True)

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
                paused_tag = f" {C_RED}[ПАУЗА]{RESET}" if STATE.get("paused") else ""
                profit_info = f"│ {C_GREEN}Профит: +{STATE['total_profit_ton']:.2f} TON{RESET} " if STATE['total_profit_ton'] > 0 else ""
                print(f"  {C_GRAY}[{now_str}]{RESET} {C_CYAN}⚡ СКАНИРОВАНИЕ...{RESET}{paused_tag} {C_DARK}Проверок:{RESET} {C_WHITE}{STATE['total_scans']}{RESET} │ {C_DARK}Флор:{RESET} {C_YELLOW}{STATE['market_floor']:.2f} TON{RESET} │ {C_DARK}Выкуп до:{RESET} {C_GREEN}{STATE['max_buy_price']:.2f} TON{RESET} {profit_info}", flush=True)

            # 3. Периодическая проверка и смарт-корректировка выставленных лотов (раз в 5 минут)
            if current_time - last_adjust_time >= 300:
                last_adjust_time = current_time
                asyncio.create_task(check_and_adjust_sales(session))

            # 4. Двойное сканирование (дешевые + свежие поступления)
            if scan_cycle % 2 == 0:
                search_payload = {
                    "count": 15, "cursor": "",
                    "collectionNames": [], "modelNames": [], "backdropNames": [], "symbolNames": [],
                    "ordering": 2, "lowToHigh": True, "maxPrice": max_nano
                }
            else:
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
                                col_floor = (gift.get("floorPriceNanoTONsByCollection") or 0) / 1e9

                                if price_nano > max_nano:
                                    continue

                                seen_ids.add(gid)

                                # Оценка редкости (номера, фоны, модели)
                                rarity_label, multiplier = evaluate_gift_rarity(gift)

                                is_high_floor_deal = (col_floor >= price_ton * 1.15)
                                is_rare = (rarity_label is not None)
                                is_cheap = (price_nano <= max_nano)

                                if not STATE.get("paused") and (is_rare or is_high_floor_deal or is_cheap):
                                    asyncio.create_task(execute_buy(session, gift, rarity_label, multiplier))

                    elif resp.status == 401:
                        now_str = datetime.now().strftime("%H:%M:%S")
                        print(f"  {C_GRAY}[{now_str}]{RESET} {C_RED}✖ Ошибка 401: Сессия устарела. Обновите токен через /token <token> в Telegram.{RESET}", flush=True)
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
