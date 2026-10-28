# admin.py
import uuid
import os
import time
import datetime
import aiosqlite
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

from config import OWNER_ID, CURRENCIES, _e
from database import (
    update_balance, set_balance, log_tx, get_all_balances, 
    get_balance, DB_PATH, create_check,
    add_admin, remove_admin, get_all_admins, is_admin,
    create_admin_fake_check, create_admin_multicheck,
    get_db_stats, get_24h_stats, get_user_full_profile, is_regional_restriction_enabled, toggle_regional_restriction
)
from keyboards import (
    admin_menu_kb, admin_back_kb, multicheck_created_kb
)

router = Router()

class AdminFSM(StatesGroup):
    waiting_balance = State()
    waiting_set_balance = State()
    waiting_fake_check = State()
    waiting_multicheck = State()
    waiting_add_admin = State()
    waiting_del_admin = State()
    waiting_user_lookup = State()

async def check_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    return await is_admin(user_id)

async def edit_admin_msg(cb: CallbackQuery, text: str, reply_markup=None):
    try:
        if cb.message.photo:
            await cb.message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode="HTML")
        else:
            await cb.message.edit_text(text=text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")

# --- ВХОД В АДМИНКУ ---
@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if not await check_admin(msg.from_user.id):
        return
    reg_enabled = await is_regional_restriction_enabled()
    admin_banner_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_banner.png")
    text = (
        f"{_e('premium_clean', '⚡')} <b>Панель управления CryptoBot</b>\n\n"
        "Система управления балансами, чеками, аналитикой и правами администраторов.\n"
        "Выберите раздел для работы:"
    )
    if os.path.exists(admin_banner_path):
        from aiogram.types import FSInputFile
        await msg.answer_photo(
            photo=FSInputFile(admin_banner_path),
            caption=text,
            reply_markup=admin_menu_kb(reg_enabled),
            parse_mode="HTML"
        )
    else:
        await msg.answer(text, reply_markup=admin_menu_kb(reg_enabled), parse_mode="HTML")

# --- СТАТИСТИКА ЗА 24 ЧАСА ---
@router.callback_query(F.data == "admin:stats_24h")
async def cb_admin_stats_24h(cb: CallbackQuery):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    s = await get_24h_stats()
    
    vol_lines = []
    if s["volume_by_asset"]:
        for asset, total in s["volume_by_asset"].items():
            emoji = CURRENCIES.get(asset, {}).get("emoji", "🪙")
            vol_lines.append(f"• {emoji} <b>{asset}</b>: {total:,.2f}")
        vol_str = "\n".join(vol_lines)
    else:
        vol_str = "<i>за 24ч чеки не создавались</i>"

    text = (
        f"{_e('lightning', '⚡')} <b>Аналитика за последние 24 часа</b>\n\n"
        f"• Новых пользователей: <b>{s['new_users']}</b>\n"
        f"• Создано чеков: <b>{s['new_checks']}</b>\n"
        f"• Активаций чеков: <b>{s['activations_24h']}</b>\n"
        f"• Транзакций в реестре: <b>{s['tx_24h']}</b>\n\n"
        f"<b>Объем созданных чеков за 24ч:</b>\n{vol_str}"
    )
    await edit_admin_msg(cb, text, reply_markup=admin_back_kb())
    await cb.answer()

# --- ПРОСМОТР ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ ---
@router.callback_query(F.data == "admin:user_info")
async def cb_admin_user_lookup(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_user_lookup)
    text = (
        f"{_e('settings', '🔍')} <b>Поиск профиля пользователя</b>\n\n"
        "Отправьте Telegram ID пользователя для просмотра полной информации:"
    )
    await edit_admin_msg(cb, text, reply_markup=admin_back_kb())
    await cb.answer()

@router.message(AdminFSM.waiting_user_lookup)
async def proc_admin_user_lookup(msg: Message, state: FSMContext):
    if not await check_admin(msg.from_user.id):
        return
    raw = (msg.text or "").strip()
    try:
        uid = int(raw)
    except ValueError:
        await msg.answer("❌ Введите корректный числовой Telegram ID.")
        return

    profile = await get_user_full_profile(uid)
    if not profile:
        await msg.answer(f"❌ Пользователь с ID <code>{uid}</code> не найден в базе данных.", reply_markup=admin_menu_kb(), parse_mode="HTML")
        await state.clear()
        return

    created_dt = datetime.datetime.fromtimestamp(profile.get("created_at", time.time())).strftime("%d.%m.%Y %H:%M")
    uname = f"@{profile['username']}" if profile.get("username") else "<i>нет username</i>"
    phone = profile.get("phone") or "<i>не привязан</i>"
    lang = profile.get("language", "ru").upper()
    fiat = profile.get("fiat_currency", "USD")
    
    bals = profile.get("balances", {})
    if bals:
        bal_lines = [f"• {CURRENCIES.get(k, {}).get('emoji', '🪙')} <b>{k}</b>: {v:,.4f}" for k, v in bals.items()]
        bal_str = "\n".join(bal_lines)
    else:
        bal_str = "<i>все балансы нулевые</i>"

    text = (
        f"👤 <b>Профиль пользователя</b> <code>{uid}</code>\n\n"
        f"• Username: {uname}\n"
        f"• Телефон: <code>{phone}</code>\n"
        f"• Язык / Валюта: <b>{lang}</b> / <b>{fiat}</b>\n"
        f"• Регистрация: <b>{created_dt}</b>\n\n"
        f"<b>Активность по чекам:</b>\n"
        f"• Создано чеков: <b>{profile.get('checks_created', 0)}</b>\n"
        f"• Активировано чеков: <b>{profile.get('checks_activated', 0)}</b>\n\n"
        f"<b>Балансы:</b>\n{bal_str}"
    )

    action_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выдать баланс", callback_data="admin:bal"), InlineKeyboardButton(text="Установить баланс", callback_data="admin:set_bal")],
        [InlineKeyboardButton(text="‹ Назад в админ-панель", callback_data="admin:menu")]
    ])

    await msg.answer(text, reply_markup=action_kb, parse_mode="HTML")
    await state.clear()

# --- ВЫДАТЬ БАЛАНС ---
@router.callback_query(F.data == "admin:bal")
async def cb_admin_bal(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_balance)
    text = (
        f"{_e('dollar', '💰')} <b>Выдача баланса</b>\n\n"
        f"Введите <code>ID сумма ВАЛЮТА</code>\n"
        f"Например: <code>123456789 1000 USDT</code>"
    )
    await edit_admin_msg(cb, text, reply_markup=admin_back_kb())
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
    text = (
        f"{_e('settings', '✏️')} <b>Изменение баланса (Установка)</b>\n\n"
        f"Введите: <code>ID сумма ВАЛЮТА</code>\n"
        f"Или просто: <code>сумма ВАЛЮТА</code> (для изменения себе)\n\n"
        f"Например:\n"
        f"• <code>89000 USDT</code> — установит вам 89 000 USDT\n"
        f"• <code>{cb.from_user.id} 50000 USDT</code> — установит по ID"
    )
    await edit_admin_msg(cb, text, reply_markup=admin_back_kb())
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
    text = (
        f"{_e('fake', '🧾')} <b>Фейк-чек</b>\n\n"
        f"Введите <code>сумма ВАЛЮТА</code>\n"
        f"Например: <code>500 GRAM</code>\n\n"
        f"<i>Средства не списываются с вашего баланса.</i>"
    )
    await edit_admin_msg(cb, text, reply_markup=admin_back_kb())
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

# --- МУЛЬТИ-ЧЕК ---
@router.callback_query(F.data == "admin:multicheck")
async def cb_admin_multicheck(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_multicheck)
    text = (
        f"{_e('premium_clean', '⚡')} <b>Генерация мульти-чека</b>\n\n"
        "Введите параметры через пробел:\n"
        "<code>СУММА_НА_ОДНОГО КОЛ-ВО ВАЛЮТА [ПАРОЛЬ]</code>\n\n"
        "<b>Примеры:</b>\n"
        "• <code>5 10 USDT</code> — 10 человек по 5 USDT\n"
        "• <code>2.5 20 TON 7777</code> — 20 человек по 2.5 TON с паролем <code>7777</code>\n\n"
        "<i>Средства не списываются с вашего баланса.</i>"
    )
    await edit_admin_msg(cb, text, reply_markup=admin_back_kb())
    await cb.answer()

@router.message(AdminFSM.waiting_multicheck)
async def proc_admin_multicheck(msg: Message, state: FSMContext):
    if not await check_admin(msg.from_user.id):
        return
    try:
        parts = (msg.text or "").split()
        if len(parts) < 2:
            raise ValueError("Недостаточно аргументов")
        per_amt = float(parts[0].replace(",", "."))
        limit = int(parts[1])
        if per_amt <= 0 or limit <= 0:
            raise ValueError("Сумма и количество должны быть больше 0")

        asset = "USDT"
        password = None
        if len(parts) > 2:
            candidate = parts[2].upper()
            if candidate in CURRENCIES:
                asset = candidate
                if len(parts) > 3:
                    password = parts[3]
            else:
                password = parts[2]
                if len(parts) > 3 and parts[3].upper() in CURRENCIES:
                    asset = parts[3].upper()
    except (ValueError, IndexError):
        await msg.answer(
            "❌ Формат: <code>СУММА КОЛ-ВО ВАЛЮТА [ПАРОЛЬ]</code>\n"
            "Пример: <code>5 10 USDT</code> или <code>2.5 20 TON 7777</code>",
            parse_mode="HTML"
        )
        return

    try:
        cid = await create_admin_multicheck(msg.from_user.id, asset, per_amt, limit, password=password)
    except Exception as e:
        await msg.answer(f"❌ Ошибка БД: {e}")
        return

    bot_info = await msg.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=check_{cid}"
    total_budget = round(per_amt * limit, 8)
    pass_str = f"\nПароль: <code>{password}</code>" if password else ""

    await msg.answer(
        f"{_e('premium_clean', '⚡')} <b>Мульти-чек создан!</b>\n\n"
        f"На одного: <b>{per_amt} {asset}</b>\n"
        f"Количество активаций: <b>{limit}</b>\n"
        f"Общий фонд: <b>{total_budget:,.2f} {asset}</b>{pass_str}\n\n"
        f"Ссылка:\n<code>{link}</code>\n\n"
        f"<i>Баланс не был списан.</i>",
        reply_markup=multicheck_created_kb(link),
        parse_mode="HTML"
    )
    await state.clear()

@router.message(Command("multicheck", "мультичек"))
async def cmd_multicheck(msg: Message, state: FSMContext):
    if not await check_admin(msg.from_user.id):
        return
    args = (msg.text or "").split()[1:]
    if not args or len(args) < 2:
        await state.set_state(AdminFSM.waiting_multicheck)
        await msg.answer(
            f"{_e('premium_clean', '⚡')} <b>Генерация мульти-чека</b>\n\n"
            "Введите параметры через пробел:\n"
            "<code>СУММА_НА_ОДНОГО КОЛ-ВО ВАЛЮТА [ПАРОЛЬ]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>5 10 USDT</code> — 10 человек по 5 USDT\n"
            "• <code>2.5 20 TON 7777</code> — 20 человек по 2.5 TON с паролем <code>7777</code>\n\n"
            "<i>Баланс админа не списывается.</i>",
            parse_mode="HTML"
        )
        return
    try:
        per_amt = float(args[0].replace(",", "."))
        limit = int(args[1])
        if per_amt <= 0 or limit <= 0:
            raise ValueError
        asset = "USDT"
        password = None
        if len(args) > 2:
            candidate = args[2].upper()
            if candidate in CURRENCIES:
                asset = candidate
                if len(args) > 3:
                    password = args[3]
            else:
                password = args[2]
                if len(args) > 3 and args[3].upper() in CURRENCIES:
                    asset = args[3].upper()
        
        cid = await create_admin_multicheck(msg.from_user.id, asset, per_amt, limit, password=password)
        bot_info = await msg.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start=check_{cid}"
        total_budget = round(per_amt * limit, 8)
        pass_str = f"\nПароль: <code>{password}</code>" if password else ""
        await msg.answer(
            f"{_e('premium_clean', '⚡')} <b>Мульти-чек создан!</b>\n\n"
            f"На одного: <b>{per_amt} {asset}</b>\n"
            f"Количество активаций: <b>{limit}</b>\n"
            f"Общий фонд: <b>{total_budget:,.2f} {asset}</b>{pass_str}\n\n"
            f"Ссылка:\n<code>{link}</code>",
            reply_markup=multicheck_created_kb(link),
            parse_mode="HTML"
        )
    except Exception:
        await msg.answer("❌ Формат: <code>/multicheck 5 10 USDT [пароль]</code>", parse_mode="HTML")

# --- СТАТИСТИКА БАЗЫ ---
@router.callback_query(F.data == "admin:all")
async def cb_admin_all(cb: CallbackQuery):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    stats = await get_db_stats()
    balances = await get_all_balances(cb.from_user.id)
    admins = await get_all_admins()
    admin_list_str = ", ".join(f"<code>{a}</code>" for a in admins) if admins else "<i>нет дополнительных админов</i>"
    text = (
        f"{_e('message', '📊')} <b>Статистика базы данных</b>\n\n"
        f"• Пользователей в базе: <b>{stats['users']}</b>\n"
        f"• Всего чеков: <b>{stats['checks_total']}</b> (активных: <b>{stats['checks_active']}</b>)\n"
        f"• Операций в реестре: <b>{stats['transactions']}</b>\n"
        f"• Назначенные администраторы: {admin_list_str}\n\n"
        f"<b>Балансы администратора:</b>\n"
    )
    if not balances:
        text += "<i>Баланс пуст</i>"
    else:
        for ticker, amt in balances.items():
            emoji = CURRENCIES.get(ticker, {}).get("emoji", "🪙")
            text += f"{emoji} <b>{ticker}</b>: {amt:,.4f}\n"

    await edit_admin_msg(cb, text, reply_markup=admin_back_kb())
    await cb.answer()

# --- ДОБАВИТЬ АДМИНА ---
@router.callback_query(F.data == "admin:add")
async def cb_admin_add(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Только главный владелец может добавлять админов.", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_add_admin)
    text = (
        "👑 <b>Добавление админа</b>\n\n"
        "Отправьте Telegram ID нового администратора (например, <code>5742263111</code>):"
    )
    await edit_admin_msg(cb, text, reply_markup=admin_back_kb())
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

# --- УДАЛИТЬ АДМИНА ---
@router.callback_query(F.data == "admin:del")
async def cb_admin_del(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Только главный владелец может снимать админов.", show_alert=True)
        return
    admins = await get_all_admins()
    if not admins:
        await cb.answer("Список администраторов пуст.", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_del_admin)
    list_str = "\n".join([f"• <code>{a}</code>" for a in admins])
    text = (
        "🗑 <b>Удаление администратора</b>\n\n"
        f"Текущие админы:\n{list_str}\n\n"
        "Отправьте Telegram ID админа, которого нужно снять:"
    )
    await edit_admin_msg(cb, text, reply_markup=admin_back_kb())
    await cb.answer()

@router.message(AdminFSM.waiting_del_admin)
async def proc_admin_del(msg: Message, state: FSMContext):
    if msg.from_user.id != OWNER_ID:
        return
    try:
        target_admin_id = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Отправьте корректный числовой ID.")
        return

    await remove_admin(target_admin_id)
    await msg.answer(
        f"✅ Администратор <code>{target_admin_id}</code> успешно снят!",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )
    await state.clear()

# --- ВОЗВРАТ В ГЛАВНОЕ МЕНЮ АДМИНКИ ---
@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    reg_enabled = await is_regional_restriction_enabled()
    admin_banner_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_banner.png")
    text = (
        f"{_e('premium_clean', '⚡')} <b>Панель управления CryptoBot</b>\n\n"
        "Система управления балансами, чеками, аналитикой и правами администраторов.\n"
        "Выберите раздел для работы:"
    )
    if cb.message.photo:
        try:
            await cb.message.edit_caption(caption=text, reply_markup=admin_menu_kb(reg_enabled), parse_mode="HTML")
            await cb.answer()
            return
        except Exception:
            pass

    if os.path.exists(admin_banner_path):
        from aiogram.types import FSInputFile
        await cb.message.answer_photo(
            photo=FSInputFile(admin_banner_path),
            caption=text,
            reply_markup=admin_menu_kb(reg_enabled),
            parse_mode="HTML"
        )
        try:
            await cb.message.delete()
        except Exception:
            pass
    else:
        await cb.message.edit_text(text, reply_markup=admin_menu_kb(reg_enabled), parse_mode="HTML")
    await cb.answer()

# --- ПЕРЕКЛЮЧЕНИЕ РЕГИОНАЛЬНОГО ОГРАНИЧЕНИЯ ---
@router.callback_query(F.data == "admin:toggle_reg")
async def cb_admin_toggle_reg(cb: CallbackQuery):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    new_state = await toggle_regional_restriction()
    state_str = "ВКЛЮЧЕНО" if new_state else "ВЫКЛЮЧЕНО"
    await cb.answer(f"Региональное ограничение: {state_str}", show_alert=True)
    try:
        await cb.message.edit_reply_markup(reply_markup=admin_menu_kb(new_state))
    except Exception:
        pass
