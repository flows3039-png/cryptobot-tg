# menu_stubs.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import settings_kb, cryptopay_menu_kb
from database import get_user_lang
from locales import t

router = Router()

@router.callback_query(F.data == "menu:settings")
async def cb_menu_settings(cb: CallbackQuery):
    lang = await get_user_lang(cb.from_user.id)
    text = t(lang, "profile_text")
    try:
        await cb.message.edit_text(text, reply_markup=settings_kb(), parse_mode="HTML")
    except:
        await cb.message.answer(text, reply_markup=settings_kb(), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "menu:exchange")
async def cb_menu_exchange(cb: CallbackQuery):
    lang = await get_user_lang(cb.from_user.id)
    text = t(lang, "exchange_dev")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "back"), callback_data="menu:main")]])
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.in_(["menu:subs", "menu:giveaways"]))
async def cb_menu_subs(cb: CallbackQuery):
    lang = await get_user_lang(cb.from_user.id)
    text = t(lang, "subs_dev")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "back"), callback_data="menu:main")]])
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "set:ref")
async def cb_set_ref(cb: CallbackQuery):
    lang = await get_user_lang(cb.from_user.id)
    text = t(lang, "ref_text")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "back"), callback_data="menu:settings")]])
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "menu:pay")
async def cb_menu_pay(cb: CallbackQuery):
    # Оригинальный вид как на скриншоте
    text = "💳 <b>Crypto Pay</b>\n\nИнтеграция платежной системы."
    kb = cryptopay_menu_kb()
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()