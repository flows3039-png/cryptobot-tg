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
    update_balance, set_balance, log_tx, get_all_balances, 
    get_balance, DB_PATH, create_check,
    add_admin, is_admin, create_admin_fake_check
)
from keyboards import admin_menu_kb, nft_parser_menu_kb, nft_found_actions_kb

router = Router()

class AdminFSM(StatesGroup):
    waiting_balance = State()
    waiting_set_balance = State()
    waiting_fake_check = State()
    waiting_add_admin = State()
    waiting_nft_range = State()
    waiting_nft_link = State()

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
    try:
        from keyboards import update_user_chat_menu_button
        await update_user_chat_menu_button(msg.bot, target_id)
    except Exception:
        pass
    
    await msg.answer(
        f"✅ Выдано <b>{amt} {asset}</b> пользователю <code>{target_id}</code>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )
    await state.clear()


# --- ИЗМЕНИТЬ БАЛАНС (УСТАНОВИТЬ) ---
@router.callback_query(F.data == "admin:set_bal")
async def cb_admin_set_bal(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_set_balance)
    await cb.message.edit_text(
        f"{_e('settings', '✏️')} <b>Изменение баланса (Установка)</b>\n\n"
        f"Введите: <code>ID сумма ВАЛЮТА</code>\n"
        f"Или просто: <code>сумма ВАЛЮТА</code> (для изменения себе)\n\n"
        f"Например:\n"
        f"• <code>89000 USDT</code> — установит вам 89 000 USDT\n"
        f"• <code>{cb.from_user.id} 50000 USDT</code> — установит по ID",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(AdminFSM.waiting_set_balance)
async def proc_admin_set_bal(msg: Message, state: FSMContext):
    if not await check_admin(msg.from_user.id):
        return
    try:
        parts = (msg.text or "").split()
        if len(parts) == 2:
            target_id = msg.from_user.id
            amt = float(parts[0].replace(",", "."))
            asset = parts[1].upper()
        elif len(parts) >= 3:
            target_id = int(parts[0])
            amt = float(parts[1].replace(",", "."))
            asset = parts[2].upper()
        else:
            raise ValueError

        if asset not in CURRENCIES:
            raise ValueError
    except (ValueError, IndexError):
        await msg.answer(
            "❌ Неверный формат.\nПример: <code>89000 USDT</code> или <code>123456789 50000 USDT</code>",
            parse_mode="HTML"
        )
        return

    await set_balance(target_id, asset, amt)
    await log_tx(target_id, "admin_set_balance", asset, amt, "success", f"Set by admin {msg.from_user.id}")

    try:
        from keyboards import update_user_chat_menu_button
        await update_user_chat_menu_button(msg.bot, target_id)
    except Exception:
        pass

    await msg.answer(
        f"✅ Баланс <b>{asset}</b> пользователя <code>{target_id}</code> успешно установлен на <b>{amt:,.2f}</b>!",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )
    await state.clear()

# --- ПРЯМЫЕ КОМАНДЫ /set_balance И /give_balance ---
@router.message(Command("set_balance", "setbalance"))
async def cmd_set_balance(msg: Message):
    if not await check_admin(msg.from_user.id):
        return
    args = (msg.text or "").split()[1:]
    if not args:
        await msg.answer("Формат: <code>/set_balance [ID] сумма ВАЛЮТА</code>\nПример: <code>/set_balance 89000 USDT</code>", parse_mode="HTML")
        return
    try:
        if len(args) == 2:
            target_id = msg.from_user.id
            amt = float(args[0].replace(",", "."))
            asset = args[1].upper()
        elif len(args) >= 3:
            target_id = int(args[0])
            amt = float(args[1].replace(",", "."))
            asset = args[2].upper()
        else:
            raise ValueError
        if asset not in CURRENCIES:
            raise ValueError
    except Exception:
        await msg.answer("❌ Ошибка в параметрах команды. Пример: <code>/set_balance 89000 USDT</code>", parse_mode="HTML")
        return

    await set_balance(target_id, asset, amt)
    await log_tx(target_id, "admin_set_balance", asset, amt, "success", f"Set via cmd by admin {msg.from_user.id}")

    try:
        from keyboards import update_user_chat_menu_button
        await update_user_chat_menu_button(msg.bot, target_id)
    except Exception:
        pass

    await msg.answer(f"✅ Баланс <b>{asset}</b> пользователя <code>{target_id}</code> изменен на <b>{amt:,.2f}</b>!", parse_mode="HTML")

@router.message(Command("give_balance", "givebalance"))
async def cmd_give_balance(msg: Message):
    if not await check_admin(msg.from_user.id):
        return
    args = (msg.text or "").split()[1:]
    if not args:
        await msg.answer("Формат: <code>/give_balance [ID] сумма ВАЛЮТА</code>\nПример: <code>/give_balance 1000 USDT</code>", parse_mode="HTML")
        return
    try:
        if len(args) == 2:
            target_id = msg.from_user.id
            amt = float(args[0].replace(",", "."))
            asset = args[1].upper()
        elif len(args) >= 3:
            target_id = int(args[0])
            amt = float(args[1].replace(",", "."))
            asset = args[2].upper()
        else:
            raise ValueError
        if asset not in CURRENCIES:
            raise ValueError
    except Exception:
        await msg.answer("❌ Ошибка в параметрах команды. Пример: <code>/give_balance 1000 USDT</code>", parse_mode="HTML")
        return

    await update_balance(target_id, asset, amt)
    await log_tx(target_id, "admin_deposit", asset, amt, "success", f"Given via cmd by admin {msg.from_user.id}")
    try:
        from keyboards import update_user_chat_menu_button
        await update_user_chat_menu_button(msg.bot, target_id)
    except Exception:
        pass
    await msg.answer(f"✅ Выдано <b>{amt:,.2f} {asset}</b> пользователю <code>{target_id}</code>!", parse_mode="HTML")

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

# --- NFT ПАРСЕР ПОДАРКОВ TELEGRAM ---
@router.callback_query(F.data == "admin:nft")
async def cb_admin_nft(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    text = (
        "🎁 <b>NFT-парсер подарков Telegram</b>\n\n"
        "Парсер в реальном времени мониторит рынок Fragment и сеть TON, "
        "вычисляет стоимость подарка и определяет юзернейм владельца.\n\n"
        "Выберите диапазон поиска или введите ссылку:"
    )
    await cb.message.edit_text(text, reply_markup=nft_parser_menu_kb(), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    await cb.message.edit_text(
        f"{_e('crypto', '👑')} <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data.startswith("nft:range:"))
async def cb_nft_range(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    range_key = cb.data.split("nft:range:", 1)[1]
    
    if range_key == "custom":
        await state.set_state(AdminFSM.waiting_nft_range)
        await cb.message.edit_text(
            "⚙️ <b>Поиск по своему диапазону цен</b>\n\n"
            "Введите минимальную и максимальную цену в TON через дефис или пробел (например: <code>10-30</code> или <code>50 150</code>):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Отмена", callback_data="admin:nft")]]),
            parse_mode="HTML"
        )
        await cb.answer()
        return

    ranges = {
        "low": (2.0, 5.0, "Лёгкий (2 – 5 TON)"),
        "mid": (15.0, 25.0, "Средний (15 – 25 TON)"),
        "high": (45.0, 100.0, "Высокий (45 – 100 TON)")
    }
    cfg = ranges.get(range_key)
    if not cfg:
        await cb.answer("Неверный диапазон", show_alert=True)
        return

    min_t, max_t, title = cfg
    await cb.answer()
    status_msg = await cb.message.answer(
        f"⏳ <b>Поиск NFT-подарков ({title})...</b>\n"
        "Парсер опрашивает листинги и определяет юзернеймы владельцев...",
        parse_mode="HTML"
    )

    from nft_parser import search_gifts_by_range
    gifts = await search_gifts_by_range(min_t, max_t, limit=3)
    try:
        await status_msg.delete()
    except Exception:
        pass

    if not gifts:
        await cb.message.answer(
            f"❌ В диапазоне <b>{title}</b> сейчас не найдено доступных лотов.",
            reply_markup=nft_parser_menu_kb(),
            parse_mode="HTML"
        )
        return

    for g in gifts:
        out_text = (
            f"Подарок {g['link']} был успешно найден!\n\n"
            f"Цена : {g['price']:g} TON\n\n"
            f"Владелец : {g['owner']}"
        )
        await cb.message.answer(
            out_text,
            reply_markup=nft_found_actions_kb(g["link"], range_key),
            disable_web_page_preview=False
        )

@router.message(AdminFSM.waiting_nft_range)
async def proc_nft_custom_range(msg: Message, state: FSMContext):
    if not await check_admin(msg.from_user.id):
        return
    nums = re.findall(r"[\d.]+", msg.text or "")
    if len(nums) < 2:
        await msg.answer("❌ Введите две цифры диапазона через дефис или пробел (например: <code>10-50</code>):", parse_mode="HTML")
        return
    try:
        min_t = float(nums[0])
        max_t = float(nums[1])
        if min_t > max_t:
            min_t, max_t = max_t, min_t
    except ValueError:
        await msg.answer("❌ Некорректные числа.")
        return

    await state.clear()
    status_msg = await msg.answer(f"⏳ <b>Поиск NFT-подарков в диапазоне {min_t:g} – {max_t:g} TON...</b>", parse_mode="HTML")
    from nft_parser import search_gifts_by_range
    gifts = await search_gifts_by_range(min_t, max_t, limit=3)
    try:
        await status_msg.delete()
    except Exception:
        pass

    if not gifts:
        await msg.answer(f"❌ В диапазоне <b>{min_t:g} – {max_t:g} TON</b> лотов не найдено.", reply_markup=nft_parser_menu_kb(), parse_mode="HTML")
        return

    for g in gifts:
        out_text = (
            f"Подарок {g['link']} был успешно найден!\n\n"
            f"Цена : {g['price']:g} TON\n\n"
            f"Владелец : {g['owner']}"
        )
        await msg.answer(out_text, reply_markup=nft_found_actions_kb(g["link"], "custom"), disable_web_page_preview=False)

@router.callback_query(F.data == "nft:check_link")
async def cb_nft_check_link(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_nft_link)
    await cb.message.edit_text(
        "🔍 <b>Проверка NFT-подарка по ссылке</b>\n\n"
        "Отправьте ссылку на подарок (например: <code>https://t.me/nft/chillflame-344906</code>) или его название/номер:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Отмена", callback_data="admin:nft")]]),
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(AdminFSM.waiting_nft_link)
async def proc_nft_link(msg: Message, state: FSMContext):
    if not await check_admin(msg.from_user.id):
        return
    raw_val = (msg.text or "").strip()
    status_msg = await msg.answer("⏳ <b>Парсинг данных NFT-подарка и определение владельца...</b>", parse_mode="HTML")
    from nft_parser import parse_single_nft_gift
    info = await parse_single_nft_gift(raw_val)
    try:
        await status_msg.delete()
    except Exception:
        pass

    if not info:
        await msg.answer("❌ Не удалось найти информацию о данном подарке. Проверьте правильность ссылки.", reply_markup=nft_parser_menu_kb())
        return

    await state.clear()
    out_text = (
        f"Подарок {info['link']} был успешно найден!\n\n"
        f"Цена : {info['price']:g} TON\n\n"
        f"Владелец : {info['owner']}"
    )
    await msg.answer(out_text, reply_markup=nft_found_actions_kb(info["link"]), disable_web_page_preview=False)
