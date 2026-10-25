# wallet.py
import os
import secrets
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import CURRENCIES, _e
from database import (
    get_all_balances, get_balance, update_balance,
    log_tx, get_history, get_user
)
from keyboards import wallet_inline_kb_v2, wallet_currency_select_kb

router = Router()

class WalletFSM(StatesGroup):
    waiting_amount = State()
    waiting_address = State()

async def show_wallet(target, user_id: int, edit: bool = False):
    if not edit:
        try:
            await target.delete()
        except:
            pass

    balances = await get_all_balances(user_id)
    user = await get_user(user_id)
    fiat = user["fiat_currency"] if user else "USD"
    
    text = f"👛 <b>Ваш кошелёк</b>\n\n"

    display_coins = [
        ("USDT", "https://tether.to"),
        ("TON", "https://ton.org"),
        ("DOGE", "https://dogecoin.com"),
        ("XAUT", "https://gold.tether.to"),
        ("SOL", "https://solana.com"),
        ("ETH", "https://ethereum.org"),
        ("BTC", "https://bitcoin.org")
    ]

    total_usd = 0.0

    for ticker, url in display_coins:
        info = CURRENCIES.get(ticker, {})
        emoji_id = info.get("emoji_id", "🪙")
        amt = balances.get(ticker, 0.0)
        price_usd = info.get("price_usd", 0)
        usd_val = amt * price_usd
        total_usd += usd_val

        # Эмодзи отдельно, текст (ссылка) отдельно
        emoji_only = f'<tg-emoji emoji-id="{emoji_id}">🪙</tg-emoji>'
        coin_link = f'<a href="{url}"><b>{ticker}</b></a>'
        
        # Добавлен \n\n для отступа между валютами
        text += f"{emoji_only} {coin_link} — <b>{amt:.4f}</b>\n\n"

    text += f"💵 <b>Общий баланс:</b> ~${total_usd:.2f} {fiat}"
    
    kb = wallet_inline_kb_v2(user_id, balances)

    if edit:
        try:
            await target.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            await target.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)


# --- ВХОД ИЗ ГЛАВНОГО МЕНЮ ---
@router.callback_query(F.data == "menu:wallet")
async def cb_wallet_menu(cb: CallbackQuery):
    try: await cb.message.delete()
    except: pass
    await show_wallet(cb.message, cb.from_user.id, edit=False)
    await cb.answer()

@router.callback_query(F.data == "wallet:menu")
async def cb_wallet_menu_back(cb: CallbackQuery):
    try: await cb.message.delete()
    except: pass
    await show_wallet(cb.message, cb.from_user.id, edit=False)
    await cb.answer()


# --- ПОПОЛНЕНИЕ ---
@router.callback_query(F.data == "wallet:dep")
async def cb_dep(cb: CallbackQuery):
    await cb.message.edit_text(
        f"{_e('arrow_down', '📥')} <b>Пополнение</b>\n\nВыберите валюту:",
        reply_markup=wallet_currency_select_kb("dep"),
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data.startswith("wallet:dep:"))
async def cb_dep_currency(cb: CallbackQuery):
    ticker = cb.data.split(":")[2]
    fake_address = f"T{cb.from_user.id}X{ticker}Address123456789"
    
    text = (
        f"{_e('arrow_down', '📥')} <b>Пополнение {ticker}</b>\n\n"
        f"Отправьте {ticker} на этот адрес:\n"
        f"<code>{fake_address}</code>\n\n"
        f"{_e('danger', '⚠️')} Минимум 1 {ticker}. "
        f"Средства зачислятся после 2 подтверждений сети."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="‹ Назад", callback_data="wallet:menu")]
    ])
    
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()


# --- ОТПРАВКА (ВЫВОД) ---
@router.callback_query(F.data == "wallet:wdr")
async def cb_wdr(cb: CallbackQuery):
    await cb.message.edit_text(
        f"{_e('arrow_up', '📤')} <b>Отправка</b>\n\nВыберите валюту:",
        reply_markup=wallet_currency_select_kb("wdr"),
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data.startswith("wallet:wdr:"))
async def cb_wdr_currency(cb: CallbackQuery, state: FSMContext):
    ticker = cb.data.split(":")[2]
    bal = await get_balance(cb.from_user.id, ticker)
    if bal <= 0:
        await cb.answer(f"У вас нет средств в {ticker}!", show_alert=True)
        return

    await state.update_data(cur=ticker)
    await state.set_state(WalletFSM.waiting_amount)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="‹ Назад", callback_data="wallet:wdr")]
    ])
    
    await cb.message.edit_text(
        f"{_e('arrow_up', '📤')} <b>Отправка {ticker}</b>\n\n"
        f"Доступный баланс: <b>{bal:.4f} {ticker}</b>\n\nВведите сумму для отправки:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(WalletFSM.waiting_amount)
async def proc_wdr_amount(msg: Message, state: FSMContext):
    try:
        amt = float(msg.text.replace(",", "."))
        if amt <= 0: raise ValueError
    except (ValueError, AttributeError):
        await msg.answer("❌ Введите корректное число.")
        return

    data = await state.get_data()
    ticker = data["cur"]
    bal = await get_balance(msg.from_user.id, ticker)

    if amt > bal:
        await msg.answer(f"❌ Недостаточно средств. Ваш баланс: {bal:.4f} {ticker}")
        return

    await state.update_data(amt=amt)
    await state.set_state(WalletFSM.waiting_address)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet:menu")]
    ])
    
    await msg.answer(f"Введите адрес кошелька <b>{ticker}</b>, куда вывести средства:", reply_markup=kb, parse_mode="HTML")

@router.message(WalletFSM.waiting_address)
async def proc_wdr_address(msg: Message, state: FSMContext):
    address = msg.text.strip()
    if len(address) < 10:
        await msg.answer("❌ Слишком короткий адрес. Проверьте правильность.")
        return

    data = await state.get_data()
    ticker = data["cur"]
    amt = data["amt"]

    await update_balance(msg.from_user.id, ticker, -amt)
    await log_tx(msg.from_user.id, "withdraw", ticker, -amt, "success", f"To: {address}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="‹ В кошелёк", callback_data="wallet:menu")]
    ])

    await msg.answer(
        f"✅ <b>Заявка на отправку создана!</b>\n\n"
        f"Сумма: {amt} {ticker}\n"
        f"Адрес: <code>{address}</code>\n\n"
        f"Средства будут отправлены в течение 10 минут.",
        parse_mode="HTML", reply_markup=kb
    )
    await state.clear()


# --- ИСТОРИЯ ---
@router.callback_query(F.data == "wallet:hist")
async def cb_history(cb: CallbackQuery):
    rows = await get_history(cb.from_user.id, limit=10)
    text = f"{_e('message', '🧾')} <b>История транзакций</b>\n\n"

    if not rows:
        text += "У вас пока нет транзакций."
    else:
        type_names = {
            "deposit": "Пополнение",
            "withdraw": "Отправка",
            "swap": "Обмен",
            "check_create": "Создан чек",
            "check_activate": "Активирован чек",
            "admin_deposit": "Админ-начисление",
        }
        for kind, asset, delta, ref, created_at in rows:
            name = type_names.get(kind, kind)
            sign = "+" if delta > 0 else ""
            text += f"• {name}: {sign}{delta:.4f} {asset}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="‹ Назад", callback_data="wallet:menu")]
    ])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()