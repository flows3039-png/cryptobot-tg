# admin.py
import uuid
import os
import aiosqlite
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

from config import OWNER_ID, CURRENCIES, _e
from database import (
    update_balance, log_tx, get_all_balances, 
    get_balance, DB_PATH, create_check,
    add_admin, is_admin, create_admin_fake_check
)
from keyboards import admin_menu_kb

router = Router()

class AdminFSM(StatesGroup):
    waiting_balance = State()
    waiting_fake_check = State()
    waiting_add_admin = State()

async def check_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    return await is_admin(user_id)

# --- ВХОД В АДМИНКУ ---
@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if not await check_admin(msg.from_user.id):
        return
    await msg.answer(
        f"{_e('crypto', '👑')} <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )

# --- ВЫДАТЬ БАЛАНС ---
@router.callback_query(F.data == "admin:bal")
async def cb_admin_bal(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_balance)
    await cb.message.edit_text(
        f"{_e('dollar', '💰')} <b>Выдача баланса</b>\n\n"
        f"Введите <code>ID сумма ВАЛЮТА</code>\n"
        f"Например: <code>123456789 1000 USDT</code>",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(AdminFSM.waiting_balance)
async def proc_admin_bal(msg: Message, state: FSMContext):
    if not await check_admin(msg.from_user.id):
        return
    try:
        parts = (msg.text or "").split()
        target_id = int(parts[0])
        amt = float(parts[1].replace(",", "."))
        
        if len(parts) > 2:
            asset = parts[2].upper()
        else:
            asset = "USDT"
            
        if asset not in CURRENCIES:
            raise ValueError
    except (ValueError, IndexError):
        await msg.answer("❌ Формат: <code>123456789 1000 USDT</code>", parse_mode="HTML")
        return

    await update_balance(target_id, asset, amt)
    await log_tx(target_id, "admin_deposit", asset, amt, "success", f"By admin {msg.from_user.id}")
    
    await msg.answer(
        f"✅ Выдано <b>{amt} {asset}</b> пользователю <code>{target_id}</code>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )
    await state.clear()

# --- ФЕЙК-ЧЕК ---
@router.callback_query(F.data == "admin:fake")
async def cb_admin_fake(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_fake_check)
    await cb.message.edit_text(
        f"{_e('fake', '🧾')} <b>Фейк-чек</b>\n\n"
        f"Введите <code>сумма ВАЛЮТА</code>\n"
        f"Например: <code>500 GRAM</code>\n\n"
        f"<i>Средства не списываются с вашего баланса.</i>",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(AdminFSM.waiting_fake_check)
async def proc_admin_fake(msg: Message, state: FSMContext):
    if not await check_admin(msg.from_user.id):
        return
    try:
        parts = (msg.text or "").split()
        amt = float(parts[0].replace(",", "."))
        asset = parts[1].upper() if len(parts) > 1 else "USDT"
        
        if asset not in CURRENCIES:
            raise ValueError
    except (ValueError, IndexError):
        await msg.answer("❌ Формат: <code>500 USDT</code>", parse_mode="HTML")
        return

    try:
        cid = await create_admin_fake_check(msg.from_user.id, asset, amt)
    except Exception as e:
        await msg.answer(f"❌ Ошибка БД: {e}")
        return

    bot_info = await msg.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=check_{cid}"

    await msg.answer(
        f"👑 <b>Фейк-чек создан!</b>\n\n"
        f"Сумма: <b>{amt} {asset}</b>\n"
        f"Ссылка: <code>{link}</code>\n\n"
        f"<i>Баланс не был списан.</i>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )
    await state.clear()

# --- ВСЕ БАЛАНСЫ ---
@router.callback_query(F.data == "admin:all")
async def cb_admin_all(cb: CallbackQuery):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    balances = await get_all_balances(cb.from_user.id)
    text = f"{_e('message', '📊')} <b>Ваши балансы</b>\n\n"
    if not balances:
        text += "Пусто."
    else:
        for ticker, amt in balances.items():
            emoji = CURRENCIES.get(ticker, {}).get("emoji", "🪙")
            text += f"{emoji} <b>{ticker}</b>: {amt:.4f}\n"

    await cb.message.edit_text(
        text,
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )
    await cb.answer()

# --- ДОБАВИТЬ АДМИНА ---
@router.callback_query(F.data == "admin:add")
async def cb_admin_add(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Только главный владелец может добавлять админов.", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_add_admin)
    await cb.message.edit_text(
        "👑 <b>Добавление админа</b>\n\n"
        "Отправьте Telegram ID нового администратора (например, <code>5742263111</code>):",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(AdminFSM.waiting_add_admin)
async def proc_admin_add(msg: Message, state: FSMContext):
    if msg.from_user.id != OWNER_ID:
        return
    try:
        new_admin_id = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Отправьте корректный числовой ID.")
        return

    await add_admin(new_admin_id)
    await msg.answer(
        f"✅ Пользователь <code>{new_admin_id}</code> теперь администратор!",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )
    await state.clear()