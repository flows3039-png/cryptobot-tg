import asyncio
import os
import sys
import re
import time
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import MessageEntityTextUrl, Channel, Chat
from telethon.tl.functions.messages import StartBotRequest

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

# Официальные ключи приложения Telegram Desktop
OFFICIAL_APP_API_ID   = 2040
OFFICIAL_APP_API_HASH = "b1844651345ec3e5e7730e36422730e8"

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

# Регулярные выражения для поиска ссылок и кодов чеков xRocket
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

def print_header(username: str):
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
  {C_WHITE}СКОРОСТЬ:{RESET}    {C_GREEN}МОМЕНТАЛЬНО (0 мс задержки, турбо-клик){RESET}
  {C_WHITE}МОНИТОРИНГ:{RESET}  {C_GREEN}КАНАЛЫ + ЧАТЫ + КОММЕНТАРИИ ПОД ПОСТАМИ [ON]{RESET}
  {C_WHITE}ПАРСИНГ:{RESET}     {C_CYAN}ТЕКСТ + КНОПКИ ССЫЛОК + ГИПЕРССЫЛКИ [ON]{RESET}
  {C_WHITE}ИЗБРАННОЕ:{RESET}   {C_GREEN}АВТО-СОХРАНЕНИЕ ССЫЛОК [ON]{RESET}
{C_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
"""
    print(logo, flush=True)

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

def extract_cheque_code_from_message(message):
    """
    Глубокий парсинг сообщения:
    1. Текст сообщения
    2. URL-адреса инлайн-кнопок
    3. Гиперссылки внутри текста
    """
    if not message:
        return None

    # 1. Текст сообщения
    raw = message.raw_text or ""
    code = extract_cheque_code(raw)
    if code:
        return code

    # 2. Инлайн-кнопки (через высокоуровневое свойство buttons)
    if message.buttons:
        for row in message.buttons:
            for btn in row:
                url = getattr(btn, "url", None)
                if url:
                    code = extract_cheque_code(url)
                    if code:
                        return code

    # 3. Скрытые гиперссылки (MessageEntityTextUrl)
    if message.entities:
        for ent in message.entities:
            if isinstance(ent, MessageEntityTextUrl) and ent.url:
                code = extract_cheque_code(ent.url)
                if code:
                    return code

    return None

# Кэш сущности бота для моментального перехода без задержек
BOT_ENTITY = None

async def claim_cheque(client: TelegramClient, code: str, source_name: str):
    if code in PROCESSED_CHEQUES:
        return
    PROCESSED_CHEQUES.add(code)
    STATS["detected"] += 1

    t0 = time.perf_counter()
    full_link = f"https://t.me/xrocket?start={code}"
    now = datetime.now().strftime("%H:%M:%S")

    print(f"\n{C_YELLOW}⚡ [{now}] ОБНАРУЖЕН ЧЕК XROCKET:{RESET} {C_WHITE}{code}{RESET}")
    print(f"  {C_GRAY}▸ Ссылка:{RESET} {C_CYAN}{full_link}{RESET}")
    print(f"  {C_GRAY}▸ Источник:{RESET} {C_WHITE}{source_name}{RESET}")
    print(f"  {C_PURPLE}▸ Режим:{RESET} {C_GREEN}МОМЕНТАЛЬНЫЙ ПЕРЕХОД (0 МС ЗАДЕРЖКИ)...{RESET}", flush=True)

    # 1. Параллельно сохраняем в Избранное (в фоне, чтобы не отнимать миллисекунды)
    async def save_to_fav():
        try:
            fav_text = f"⚡ ЧЕК XROCKET:\n{full_link}\n(Источник: {source_name})"
            await client.send_message("me", fav_text)
        except Exception:
            pass
    asyncio.create_task(save_to_fav())

    # 2. Моментальный переход в @xrocket через MTProto StartBotRequest
    global BOT_ENTITY
    try:
        if BOT_ENTITY is None:
            BOT_ENTITY = await client.get_input_entity("xrocket")
        
        try:
            await client(StartBotRequest(bot=BOT_ENTITY, peer=BOT_ENTITY, start_param=code))
        except Exception:
            await client.send_message("xrocket", f"/start {code}")

        # 3. Высокоскоростной перехват ответа и клик по кнопке (опрос каждые 50 мс)
        for _ in range(60):
            await asyncio.sleep(0.05)
            async for reply in client.iter_messages("xrocket", limit=2):
                reply_text = reply.text or ""

                if reply.buttons:
                    for row in reply.buttons:
                        for btn in row:
                            try:
                                await btn.click()
                                ms = int((time.perf_counter() - t0) * 1000)
                                print(f"  {C_CYAN}✔ [{ms} мс] Нажата кнопка активации:{RESET} '{btn.text}'", flush=True)
                                break
                            except Exception:
                                pass

                first_line = reply_text.strip().split("\n")[0] if reply_text else "Ответ получен"
                if any(w in reply_text.lower() for w in ["получен", "активирован", "зачислен", "чек на сумму", "вы получили"]):
                    STATS["claimed"] += 1
                    ms = int((time.perf_counter() - t0) * 1000)
                    print(f"  {C_GREEN}★ [{ms} мс] УСПЕХ: Чек успешно активирован!{RESET} {C_WHITE}{first_line}{RESET}", flush=True)
                    return
                elif any(w in reply_text.lower() for w in ["закончился", "не найден", "уже активирован", "пуст"]):
                    STATS["failed"] += 1
                    ms = int((time.perf_counter() - t0) * 1000)
                    print(f"  {C_RED}✖ [{ms} мс] Чек пуст или исчерпан:{RESET} {C_GRAY}{first_line}{RESET}", flush=True)
                    return
                elif "подпишитесь" in reply_text.lower():
                    print(f"  {C_YELLOW}⚠ Требуется подписка на канал для получения чека.{RESET}", flush=True)
                    return

        print(f"  {C_GRAY}● Запрос в @xrocket отправлен.{RESET}", flush=True)
    except Exception as e:
        STATS["failed"] += 1
        print(f"  {C_RED}✖ Ошибка при активации:{RESET} {e}", flush=True)

async def console_input_loop(client: TelegramClient):
    """Позволяет вручную вставить ссылку на чек прямо в окно консоли"""
    loop = asyncio.get_event_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            code = extract_cheque_code(line.strip())
            if code:
                asyncio.create_task(claim_cheque(client, code, "Ручной ввод (консоль)"))
            else:
                print(f"  {C_GRAY}[i] В строке не найден чек xRocket (пример: https://t.me/xrocket?start=t_...){RESET}", flush=True)
        except Exception:
            break

async def main():
    env = load_env()
    api_id = int(env.get("TG_API_ID") or OFFICIAL_APP_API_ID)
    api_hash = env.get("TG_API_HASH") or OFFICIAL_APP_API_HASH

    print(f"\n{C_CYAN}[*] Авторизация через официальный Telegram Desktop (app_id: {api_id})...{RESET}")
    client = TelegramClient(
        SESSION_NAME,
        api_id=api_id,
        api_hash=api_hash,
        device_model="PC 64bit",
        system_version="Windows 11",
        app_version="5.8.3 x64",
        lang_code="ru",
        system_lang_code="ru-RU"
    )
    await client.start()

    me = await client.get_me()
    username = f"@{me.username}" if me.username else (me.first_name or "Пользователь")
    print_header(username)

    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"  {C_GRAY}[{now_str}]{RESET} {C_GREEN}● МОНИТОРИНГ ЧАТОВ, КАНАЛОВ И КОММЕНТАРИЕВ АКТИВИРОВАН.{RESET}", flush=True)
    print(f"  {C_GRAY}[{now_str}]{RESET} {C_CYAN}● Клиент: Официальный Telegram Desktop | Режим: 0 мс (турбо)...{RESET}\n", flush=True)

    @client.on(events.NewMessage())
    async def incoming_message_handler(event):
        # Игнорируем диалог с самим @xrocket
        if event.is_private and event.chat_id:
            try:
                chat = await event.get_chat()
                if getattr(chat, "username", "") == "xrocket":
                    return
            except Exception:
                pass

        code = extract_cheque_code_from_message(event.message)
        if code:
            source = "Личные сообщения"
            try:
                chat = await event.get_chat()
                chat_title = getattr(chat, "title", None) or getattr(chat, "username", None) or "Чат"
                
                # Проверяем, комментарий ли это под постом в канале
                if getattr(event.message, "reply_to", None):
                    source = f"Комментарии: {chat_title}"
                elif isinstance(chat, Channel):
                    source = f"Канал: {chat_title}"
                elif isinstance(chat, Chat):
                    source = f"Группа: {chat_title}"
                else:
                    source = chat_title
            except Exception:
                pass

            asyncio.create_task(claim_cheque(client, code, source))

    asyncio.create_task(console_input_loop(client))
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}Снайпер чеков остановлен.{RESET}")
