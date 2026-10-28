# keyboards.py
import config
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CURRENCIES, FIAT_CURRENCIES, FIAT_FLAGS, EMOJI

WEBAPP_URL = "https://flows3039-png.github.io/cryptobot-tg/"

def webapp_btn(text: str, emoji_key: str, subpath: str = "", balances: dict = None, user_id: int = None) -> InlineKeyboardButton:
    from aiogram.types import WebAppInfo
    import time
    params = []
    if subpath:
        params.append(f"tab={subpath}")
    if user_id:
        params.append(f"uid={user_id}")
    if balances is not None:
        b_parts = [f"{k}:{v:.4f}".rstrip('0').rstrip('.') if v != 0 else f"{k}:0" for k, v in balances.items()]
        if not b_parts:
            b_parts = ["USDT:0", "TON:0", "BTC:0"]
        params.append(f"b={','.join(b_parts)}")
    params.append(f"t={int(time.time())}")
    query = ("?" + "&".join(params)) if params else ""
    url = f"{WEBAPP_URL}{query}"
    return InlineKeyboardButton(
        text=text,
        web_app=WebAppInfo(url=url),
        icon_custom_emoji_id=EMOJI.get(emoji_key)
    )

async def update_user_chat_menu_button(bot, user_id: int, balances: dict = None):
    try:
        from aiogram.types import MenuButtonWebApp, WebAppInfo
        import time
        from database import get_all_balances
        if balances is None:
            balances = await get_all_balances(user_id)
        b_parts = [f"{k}:{v:.4f}".rstrip('0').rstrip('.') if v != 0 else f"{k}:0" for k, v in balances.items()]
        if not b_parts:
            b_parts = ["USDT:0", "TON:0", "BTC:0"]
        b_str = f"&b={','.join(b_parts)}"
        ts = int(time.time())
        url = f"{WEBAPP_URL}?tab=wallet&uid={user_id}{b_str}&t={ts}"
        await bot.set_chat_menu_button(
            chat_id=user_id,
            menu_button=MenuButtonWebApp(text="Кошелёк", web_app=WebAppInfo(url=url))
        )
    except Exception:
        pass

def btn(text: str, emoji_key: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
        icon_custom_emoji_id=EMOJI.get(emoji_key)
    )

def main_menu_inline(user_id: int = None, balances: dict = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [webapp_btn("Кошелёк", "wallet", "wallet", balances, user_id), webapp_btn("Обмен", "arrows_diff", "swap", balances, user_id)],
        [btn("P2P", "home_dollar", "menu:p2p"), webapp_btn("Биржа", "arrows_cycle", "exchange", balances, user_id)],
        [btn("Чеки", "check_btn", "menu:checks"), btn("Счета", "invoice_btn", "menu:invoices")],
        [btn("Crypto Pay", "pay", "menu:pay"), btn("Розыгрыши", "gift", "menu:giveaways")],
        [btn("Подписки", "megaphone", "menu:subs"), btn("Настройки", "settings", "menu:settings")]
    ])

# --- КОШЕЛЁК ---
def wallet_inline_kb_v2(user_id: int = None, balances: dict = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [webapp_btn("📱 Открыть WebApp Кошелёк", "wallet", "wallet", balances, user_id)],
        [InlineKeyboardButton(text="Пополнить", callback_data="wallet:dep", icon_custom_emoji_id="5318862055980177086"),
         InlineKeyboardButton(text="Отправить", callback_data="wallet:wdr", icon_custom_emoji_id="5319073291061730002")],
        [InlineKeyboardButton(text="История", callback_data="wallet:hist", icon_custom_emoji_id="5312103894875143512")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:main", icon_custom_emoji_id="5312212278374861302")]
    ])

def check_activated_user_kb(user_id: int, balances: dict = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [webapp_btn("Открыть кошелёк", "wallet", "wallet", balances, user_id)]
    ])

def wallet_currency_select_kb(action: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for ticker, info in CURRENCIES.items():
        if ticker == "GRAM" or ticker == "USDC": 
            continue
        row.append(InlineKeyboardButton(
            text=ticker,
            callback_data=f"wallet:{action}:{ticker}",
            icon_custom_emoji_id=info.get("emoji_id")
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="‹ Назад", callback_data="wallet:menu", icon_custom_emoji_id="5312212278374861302")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- СТАРАЯ ФУНКЦИЯ ДЛЯ ЧЕКОВ ---
def currency_select_kb(action: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for ticker, info in CURRENCIES.items():
        if ticker == "GRAM": 
            continue
        row.append(InlineKeyboardButton(
            text=ticker,
            callback_data=f"wallet:{action}:{ticker}",
            icon_custom_emoji_id=info.get("emoji_id")
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([btn("Назад", "arrows_cycle2", "wallet:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- МЕНЮ ЧЕКОВ ---
def checks_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать чек", callback_data="check:create")],
        [InlineKeyboardButton(text="Создать из чата", switch_inline_query="check")], 
        [InlineKeyboardButton(text="Назад", callback_data="menu:main")]
    ])

def check_manage_kb(check_id: str, amount: float = 0, currency: str = "USDT") -> InlineKeyboardMarkup:
    amount_str = f"{amount:g}" if amount else ""
    claim_text = f"Забрать {amount_str} {currency}" if amount else "Забрать"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔹 {claim_text}", url=f"https://t.me/{config.BOT_USERNAME}?start=check_{check_id}")],
        [InlineKeyboardButton(text="Поделиться чеком", callback_data=f"check_share:{check_id}")],
        [InlineKeyboardButton(text="Удалить чек", callback_data=f"check_del:{check_id}")]
    ])

def check_activated_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Чек активирован", callback_data="noop")]
    ])

# --- СЧЕТА ---
def invoices_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать счёт", callback_data="invoice:create", icon_custom_emoji_id="5312043357311111246")],
        [InlineKeyboardButton(text="Создать счёт из чата", switch_inline_query="invoice")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:main")]
    ])

def invoice_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Одноразовый", callback_data="inv_type:single")],
        [InlineKeyboardButton(text="Многоразовый", callback_data="inv_type:multi")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:invoices")]
    ])

def invoice_currency_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="USDT", callback_data="inv_cur:USDT", icon_custom_emoji_id="5280846677673010353"),
         InlineKeyboardButton(text="TON", callback_data="inv_cur:TON", icon_custom_emoji_id="5265151230790884988")],
        [InlineKeyboardButton(text="BTC", callback_data="inv_cur:BTC", icon_custom_emoji_id="5280624271381520811"),
         InlineKeyboardButton(text="ETH", callback_data="inv_cur:ETH", icon_custom_emoji_id="5280613443768967293")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="invoice:create")]
    ])

def invoice_manage_kb(invoice_id: str, amount: float, currency: str, bot_username: str = "") -> InlineKeyboardMarkup:
    uname = bot_username or config.BOT_USERNAME
    link = f"https://t.me/{uname}?start=invoice_{invoice_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {amount:g} {currency}", url=link)],
        [InlineKeyboardButton(text="Поделиться счётом", url=f"https://t.me/share/url?url={link}")],
        [InlineKeyboardButton(text="‹ В меню счетов", callback_data="menu:invoices")]
    ])

# --- КЛАВИАТУРЫ ДЛЯ ОБМЕНА (SWAP) ---
def swap_from_kb() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for ticker, info in CURRENCIES.items():
        if ticker in ["GRAM", "USDC"]:
            continue
        row.append(InlineKeyboardButton(
            text=ticker,
            callback_data=f"swap:from:{ticker}",
            icon_custom_emoji_id=info.get("emoji_id")
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="‹ Назад", callback_data="menu:main", icon_custom_emoji_id="5312212278374861302")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def swap_to_kb(from_ticker: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for ticker, info in CURRENCIES.items():
        if ticker in ["GRAM", "USDC"] or ticker == from_ticker:
            continue
        row.append(InlineKeyboardButton(
            text=ticker,
            callback_data=f"swap:to:{ticker}",
            icon_custom_emoji_id=info.get("emoji_id")
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="‹ Назад", callback_data="menu:swap", icon_custom_emoji_id="5312212278374861302")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- БИРЖА (EXCHANGE) ---
def exchange_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 График BTC", callback_data="exch:BTC"),
         InlineKeyboardButton(text="📈 График ETH", callback_data="exch:ETH")],
        [InlineKeyboardButton(text="📈 График TON", callback_data="exch:TON"),
         InlineKeyboardButton(text="📈 График SOL", callback_data="exch:SOL")],
        [InlineKeyboardButton(text="🔄 Обменять", callback_data="menu:swap")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:main")]
    ])

def exchange_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="‹ Назад к бирже", callback_data="menu:exchange")]
    ])

# --- P2P ---
def p2p_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("Купить", "arrow_up", "p2p:buy"), btn("Продать", "arrow_down", "p2p:sell")],
        [btn("Мои сделки", "message", "p2p:my"), btn("Создать объявление", "plus", "p2p:create")],
        [btn("Назад", "arrows_cycle2", "menu:main")]
    ])

def fiat_select_kb(action: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for fiat in FIAT_CURRENCIES:
        flag = FIAT_FLAGS.get(fiat, "🏳️")
        row.append(InlineKeyboardButton(text=f"{flag} {fiat}", callback_data=f"p2p:{action}:{fiat}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([btn("Назад", "arrows_cycle2", "p2p:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- CRYPTO PAY ---
def cryptopay_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть в приложении", callback_data="pay:app")],
        [InlineKeyboardButton(text="Создать приложение", callback_data="pay:create")],
        [InlineKeyboardButton(text="Документация API", url="https://help.cr.bot/en/articles/10279948-crypto-pay-api")],
        [InlineKeyboardButton(text="Чат для разработчиков", url="https://t.me/CryptoPayDevRu")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:main")]
    ])

# --- НАСТРОЙКИ ---
def settings_kb(current_fiat: str = "USD") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Рефералы", callback_data="set:ref"), InlineKeyboardButton(text="🔔 Уведомления", callback_data="set:notif")],
        [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="set:tz"), InlineKeyboardButton(text="🇷🇺 Язык бота", callback_data="set:lang")],
        [InlineKeyboardButton(text=f"🤑 Валюта бота · {current_fiat}", callback_data="set:fiat")],
        [InlineKeyboardButton(text="ℹ️ Комиссии и лимиты", callback_data="set:limits")],
        [InlineKeyboardButton(text="🏅 Конкурсы", callback_data="set:contests")],
        [InlineKeyboardButton(text="Справка Crypto Bot", url="https://help.cr.bot/ru/")],
        [InlineKeyboardButton(text="Что умеет Crypto Bot", url="https://t.me/CryptoBotTips")],
        [InlineKeyboardButton(text="Написать в поддержку", url="https://t.me/CryptoSupportBot")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:main")]
    ])

def referral_kb(ref_link: str, current_period: str = "all") -> InlineKeyboardMarkup:
    def p_text(period_key, text):
        return f"· {text} ·" if period_key == current_period else text
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=p_text("all", "За всё время"), callback_data="ref:all"), InlineKeyboardButton(text=p_text("yesterday", "За вчера"), callback_data="ref:yesterday")],
        [InlineKeyboardButton(text=p_text("week", "За неделю"), callback_data="ref:week"), InlineKeyboardButton(text=p_text("month", "За месяц"), callback_data="ref:month")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:settings")]
    ])

# --- АДМИН-ПАНЕЛЬ ---
def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить баланс", callback_data="admin:set_bal"), InlineKeyboardButton(text="Выдать баланс", callback_data="admin:bal")],
        [InlineKeyboardButton(text="Профиль юзера", callback_data="admin:user_info"), InlineKeyboardButton(text="Статистика 24ч", callback_data="admin:stats_24h")],
        [InlineKeyboardButton(text="Статистика базы", callback_data="admin:all")],
        [InlineKeyboardButton(text="Назначить админа", callback_data="admin:add"), InlineKeyboardButton(text="Снять админа", callback_data="admin:del")]
    ])

def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="‹ Назад в админ-панель", callback_data="admin:menu")]
    ])

def multicheck_created_kb(check_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Поделиться чеком", url=f"https://t.me/share/url?url={check_url}&text=Забирай%20мульти-чек!")],
        [InlineKeyboardButton(text="‹ Назад в админ-панель", callback_data="admin:menu")]
    ])

def nft_parser_menu_kb(auto_active: bool = False) -> InlineKeyboardMarkup:
    auto_btn_text = "Остановить авто-охоту" if auto_active else "Запустить авто-охоту 24/7"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Лёгкий (2 – 5 TON)", callback_data="nft:range:low"), InlineKeyboardButton(text="Средний (15 – 25 TON)", callback_data="nft:range:mid")],
        [InlineKeyboardButton(text="Высокий (45 – 100 TON)", callback_data="nft:range:high"), InlineKeyboardButton(text="Свой диапазон", callback_data="nft:range:custom")],
        [InlineKeyboardButton(text="Редкие узоры (<1%)", callback_data="nft:filter:rare"), InlineKeyboardButton(text="Красивые номера (#777)", callback_data="nft:filter:serial")],
        [InlineKeyboardButton(text=auto_btn_text, callback_data="nft:auto_toggle")],
        [InlineKeyboardButton(text="Проверить ссылку", callback_data="nft:check_link"), InlineKeyboardButton(text="Экспорт базы (CSV)", callback_data="nft:export_csv")],
        [InlineKeyboardButton(text="‹ Назад в админ-панель", callback_data="admin:menu")]
    ])

def nft_found_actions_kb(gift_url: str, outreach_url: str = None, range_key: str = None) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Открыть подарок", url=gift_url)]
    ]
    if outreach_url:
        buttons.append([InlineKeyboardButton(text="Написать владельцу в ЛС", url=outreach_url)])
    
    nav_row = []
    if range_key and range_key != "custom":
        nav_row.append(InlineKeyboardButton(text="Искать ещё", callback_data=f"nft:range:{range_key}"))
    nav_row.append(InlineKeyboardButton(text="‹ Меню парсера", callback_data="admin:nft"))
    buttons.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)