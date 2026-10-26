import asyncio
import os
import sys
import re
import time
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonCallback, KeyboardButtonUrl

# Enable UTF-8 in Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
os.system("")

# ANSI Color Palette
RESET     = "\033[0m"
BOLD      = "\033[1m"
C_CYAN    = "\033[38;2;34;211;238m"
C_GREEN   = "\033[38;2;74;222;128m"
C_PURPLE  = "\033[38;2;192;132;252m"
C_YELLOW  = "\033[38;2;250;204;21m"
C_RED     = "\033[38;2;248;113;113m"
C_GRAY    = "\033[38;2;148;163;184m"
C_DARK    = "\033[38;2;71;85;105m"
C_WHITE   = "\033[38;2;241;245;249m"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
SESSION_NAME = os.path.join(BASE_DIR, "xrocket_session")

def load_env():
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

def save_env_field(key: str, value: str):
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}\n")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

# Регулярные выражения для поиска чеков xRocket
XROCKET_PATTERNS = [
    re.compile(r"t\.me/(?:xrocket|ton_rocket_bot)\?start=([tmcw]_[a-zA-Z0-9_-]+)", re.IGNORECASE),
    re.compile(r"xrocket\.tg/start=([tmcw]_[a-zA-Z0-9_-]+)", re.IGNORECASE),
    re.compile(r"\b([tmcw]_[a-zA-Z0-9_-]{10,})\b")
]

PROCESSED_CHEQUES = set()
STATS = {
    "detected": 0,
    "claimed": 0,
    "failed": 0
}

def print_header(delay_sec: float, username: str):
    os.system("cls" if os.name == "nt" else "clear")
    logo = f"""
{C_CYAN}██╗  ██╗██████╗  ██████╗  ██████╗██╗  ██╗███████╗████████╗{RESET}
{C_CYAN}╚██╗██╔╝██╔══██╗██╔═══██╗██╔════╝██║ ██╔╝██╔════╝╚══██╔══╝{RESET}
{C_CYAN} ╚███╔╝ ██████╔╝██║   ██║██║     █████═╝ █████╗     ██║   {RESET}
{C_CYAN} ██╔██╗ ██╔══██╗██║   ██║██║     ██╔═██╗ ██╔══╝     ██║   {RESET}
{C_CYAN}██╔╝ ██╗██║  ██║╚██████╔╝╚██████╗██║ ╚██╗███████╗   ██║   {RESET}
{C_CYAN}╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   {RESET}
{C_PURPLE}            ● XROCKET CHEQUE SNIPER // MODRIX ●             {RESET}
{C_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
  {C_WHITE}АККАУНТ:{RESET}     {C_GREEN}{username}{RESET}
  {C_WHITE}ЦЕЛЕВОЙ БОТ:{RESET} {C_YELLOW}@xrocket{RESET}
  {C_WHITE}ТАЙМЕР:{RESET}      {C_CYAN}Задержка ровно {delay_sec:.1f} сек{RESET} (антифрод-обход)
  {C_WHITE}МОНИТОРИНГ:{RESET}  {C_GREEN}ВСЕ ЧАТЫ, КАНАЛЫ И ЛС [ON]{RESET}
  {C_WHITE}ВВОД:{RESET}        {C_WHITE}Вставь ссылку в консоль для ручной активации{RESET}
{C_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
"""
    print(logo, flush=True)

async def claim_cheque(client: TelegramClient, code: str, source_name: str, delay_sec: float):
    if code in PROCESSED_CHEQUES:
        return
    PROCESSED_CHEQUES.add(code)
    STATS["detected"] += 1

    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n{C_YELLOW}⚡ [{now}] ОБНАРУЖЕН ЧЕК XROCKET:{RESET} {C_WHITE}{code}{RESET}")
    print(f"  {C_GRAY}▸ Источник:{RESET} {C_CYAN}{source_name}{RESET}")
    print(f"  {C_GRAY}▸ Задержка:{RESET} {C_PURPLE}Ожидание ровно {delay_sec:.1f} сек...{RESET}", flush=True)

    # Точная задержка 6 секунд
    await asyncio.sleep(delay_sec)

    send_time = datetime.now().strftime("%H:%M:%S")
    print(f"  {C_GREEN}▸ [{send_time}] Отправка команды в @xrocket:{RESET} /start {code}", flush=True)

    try:
        # Отправка команды в личку @xrocket
        msg = await client.send_message("xrocket", f"/start {code}")

        # Ожидание ответа от бота (до 5 секунд)
        for _ in range(25):
            await asyncio.sleep(0.2)
            async for reply in client.iter_messages("xrocket", limit=3):
                if reply.id > msg.id:
                    reply_text = reply.text or ""
                    
                    # Проверяем наличие inline-кнопок для подтверждения
                    if reply.reply_markup and hasattr(reply.reply_markup, "rows"):
                        for row in reply.reply_markup.rows:
                            for btn in row.buttons:
                                if isinstance(btn, KeyboardButtonCallback):
                                    btn_text = btn.text.lower()
                                    # Кликаем на кнопку активации чека
                                    try:
                                        await reply.click(data=btn.data)
                                        print(f"  {C_CYAN}✔ [{datetime.now().strftime('%H:%M:%S')}] Нажата кнопка активации:{RESET} '{btn.text}'", flush=True)
                                    except Exception:
                                        try:
                                            await reply.click(0)
                                        except Exception:
                                            pass
                                    break

                    # Логирование результата
                    first_line = reply_text.strip().split("\n")[0] if reply_text else "Ответ получен"
                    if any(w in reply_text.lower() for w in ["получен", "активирован", "зачислен", "чек на сумму", "вы получили"]):
                        STATS["claimed"] += 1
                        print(f"  {C_GREEN}★ УСПЕХ: Чек активирован!{RESET} {C_WHITE}{first_line}{RESET}", flush=True)
                    elif any(w in reply_text.lower() for w in ["закончился", "не найден", "уже активирован", "пуст"]):
                        STATS["failed"] += 1
                        print(f"  {C_RED}✖ Чек пуст или исчерпан:{RESET} {C_GRAY}{first_line}{RESET}", flush=True)
                    elif "подпишитесь" in reply_text.lower():
                        print(f"  {C_YELLOW}⚠ Требуется подписка на канал для получения чека.{RESET}", flush=True)
                    else:
                        print(f"  {C_CYAN}● Ответ xRocket:{RESET} {first_line}", flush=True)
                    return

        print(f"  {C_GRAY}● Команда отправлена в @xrocket. Проверь диалог с ботом.{RESET}", flush=True)
    except Exception as e:
        STATS["failed"] += 1
        print(f"  {C_RED}✖ Ошибка при активации чека:{RESET} {e}", flush=True)

def extract_cheque_code(text: str):
    if not text:
        return None
    for pat in XROCKET_PATTERNS:
        m = pat.search(text)
        if m:
            code = m.group(1)
            if code.startswith(("t_", "m_", "c_", "w_")):
                return code
    return None

async def console_input_loop(client: TelegramClient, delay_sec: float):
    """Позволяет вручную вставить ссылку на чек прямо в окно консоли"""
    loop = asyncio.get_event_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            code = extract_cheque_code(line.strip())
            if code:
                asyncio.create_task(claim_cheque(client, code, "Ручной ввод (консоль)", delay_sec))
            else:
                print(f"  {C_GRAY}[i] В строке не найден чек xRocket (пример: t_xxx или ссылка){RESET}", flush=True)
        except Exception:
            break

async def main():
    env = load_env()
    api_id = env.get("TG_API_ID")
    api_hash = env.get("TG_API_HASH")
    delay_sec = float(env.get("DELAY_SECONDS", 6.0))

    if not api_id or not api_hash:
        os.system("cls" if os.name == "nt" else "clear")
        print(f"{C_CYAN}=== НАСТРОЙКА XROCKET CHEQUE SNIPER ==={RESET}\n")
        print(f"{C_WHITE}Для работы юзербота нужны API_ID и API_HASH с сайта {C_CYAN}https://my.telegram.org{RESET}")
        print(f"{C_GRAY}1. Зайди на https://my.telegram.org и авторизуйся{RESET}")
        print(f"{C_GRAY}2. Нажми 'API development tools'{RESET}")
        print(f"{C_GRAY}3. Скопируй app api_id и api_hash сюда:\n{RESET}")

        api_id = input("Введите TG_API_ID: ").strip()
        api_hash = input("Введите TG_API_HASH: ").strip()

        if not api_id or not api_hash:
            print(f"{C_RED}Ошибка: API_ID и API_HASH обязательны.{RESET}")
            return

        save_env_field("TG_API_ID", api_id)
        save_env_field("TG_API_HASH", api_hash)
        save_env_field("DELAY_SECONDS", str(delay_sec))

    print(f"\n{C_CYAN}[*] Подключение к Telegram...{RESET}")
    client = TelegramClient(SESSION_NAME, int(api_id), api_hash)
    await client.start()

    me = await client.get_me()
    username = f"@{me.username}" if me.username else (me.first_name or "Пользователь")
    print_header(delay_sec, username)

    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"  {C_GRAY}[{now_str}]{RESET} {C_GREEN}● МОНИТОРИНГ ЧАТОВ АКТИВИРОВАН.{RESET} Ожидание чеков...", flush=True)

    @client.on(events.NewMessage())
    async def incoming_message_handler(event):
        # Игнорируем исходящие сообщения от самого бота в чат xrocket
        if event.is_private and event.chat_id:
            try:
                chat = await event.get_chat()
                if getattr(chat, "username", "") == "xrocket":
                    return
            except Exception:
                pass

        text = event.raw_text or ""
        code = extract_cheque_code(text)
        if code:
            source = "Личные сообщения"
            try:
                chat = await event.get_chat()
                source = getattr(chat, "title", None) or getattr(chat, "username", None) or "Чат"
            except Exception:
                pass
            asyncio.create_task(claim_cheque(client, code, source, delay_sec))

    # Фоновый ручной ввод из консоли
    asyncio.create_task(console_input_loop(client, delay_sec))

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}Снайпер чеков остановлен.{RESET}")
