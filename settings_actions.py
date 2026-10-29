# settings_actions.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import update_user_setting, get_user, get_user_lang
from keyboards import settings_kb
from locales import t

router = Router()

@router.callback_query(F.data == "set:tz")
async def cb_set_tz(cb: CallbackQuery):
    lang = await get_user_lang(cb.from_user.id)
    text = t(lang, "tz_choose")
    buttons = [
        [InlineKeyboardButton(text="Москва (UTC+3)", callback_data="tz:Europe/Moscow")],
        [InlineKeyboardButton(text="Киев (UTC+2)", callback_data="tz:Europe/Kiev")],
        [InlineKeyboardButton(text="Алматы (UTC+6)", callback_data="tz:Asia/Almaty")],
        [InlineKeyboardButton(text="Ташкент (UTC+5)", callback_data="tz:Asia/Tashkent")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="menu:settings")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("tz:"))
async def cb_tz_selected(cb: CallbackQuery):
    tz = cb.data.split(":")[1]
    await update_user_setting(cb.from_user.id, "timezone", tz)
    
    lang = await get_user_lang(cb.from_user.id)
    user = await get_user(cb.from_user.id)
    current_fiat = user["fiat_currency"] if user else "USD"
    
    text = t(lang, "tz_changed", tz=tz)
    try:
        await cb.message.edit_text(text, reply_markup=settings_kb(current_fiat), parse_mode="HTML")
    except:
        await cb.message.answer(text, reply_markup=settings_kb(current_fiat), parse_mode="HTML")
    await cb.answer(t(lang, "settings_saved"))

@router.callback_query(F.data == "set:lang")
async def cb_set_lang(cb: CallbackQuery):
    lang = await get_user_lang(cb.from_user.id)
    text = t(lang, "lang_choose")
    buttons = [
        [InlineKeyboardButton(text="Русский", callback_data="lang:ru", icon_custom_emoji_id="5825794181183836432" if lang == "ru" else None)],
        [InlineKeyboardButton(text="English", callback_data="lang:en", icon_custom_emoji_id="5825794181183836432" if lang == "en" else None)],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="menu:settings")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("lang:"))
async def cb_lang_selected(cb: CallbackQuery):
    lang_code = cb.data.split(":")[1]
    await update_user_setting(cb.from_user.id, "language", lang_code)
    
    user = await get_user(cb.from_user.id)
    current_fiat = user["fiat_currency"] if user else "USD"
    
    text = t(lang_code, "lang_changed")
    try:
        await cb.message.edit_text(text, reply_markup=settings_kb(current_fiat), parse_mode="HTML")
    except:
        await cb.message.answer(text, reply_markup=settings_kb(current_fiat), parse_mode="HTML")
    await cb.answer(t(lang_code, "settings_saved"))

@router.callback_query(F.data == "set:contests")
async def cb_set_contests(cb: CallbackQuery):
    lang = await get_user_lang(cb.from_user.id)
    text = t(lang, "contests_text")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "back"), callback_data="menu:settings")]])
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    except:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()