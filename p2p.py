# p2p.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import CURRENCIES, FIAT_CURRENCIES, FIAT_FLAGS
from database import get_p2p_orders, create_p2p_order, get_user_orders, generate_fake_orders

router = Router()

class P2PFSM(StatesGroup):
    waiting_crypto = State()
    waiting_fiat = State()
    waiting_price = State()
    waiting_amount = State()
    waiting_pay_method = State()
    waiting_limits = State()

# --- ГЛАВНОЕ МЕНЮ P2P ---
@router.callback_query(F.data.in_(["menu:p2p", "p2p:menu"]))
async def cb_p2p_menu(cb: CallbackQuery):
    text = (
        "🛒 <b>Здесь вы можете купить или продать криптовалюту.</b> "
        "Переводом на карту или электронный кошелек."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Купить", callback_data="p2p:buy"), InlineKeyboardButton(text="📉 Продать", callback_data="p2p:sell")],
        [InlineKeyboardButton(text="💼 Мои сделки", callback_data="p2p:my_deals")],
        [InlineKeyboardButton(text="🤝 Создать объявление", callback_data="p2p:create_ad")],
        [InlineKeyboardButton(text="⚙️ Оплата и валюта", callback_data="p2p:settings")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="p2p:profile")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:main")]
    ])
    
    try: await cb.message.delete()
    except: pass
    await cb.message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()

# --- ВЫБОР ВАЛЮТЫ ---
@router.callback_query(F.data.in_(["p2p:buy", "p2p:sell"]))
async def cb_p2p_fiat(cb: CallbackQuery, state: FSMContext):
    action = cb.data.split(":")[1]
    await state.update_data(action=action)
    
    text = "💠 <b>Выберите валюту для покупки и продажи монет в P2P Маркете.</b>"
    
    buttons = []
    row = []
    for fiat in FIAT_CURRENCIES:
        flag = FIAT_FLAGS.get(fiat, "🏳️")
        row.append(InlineKeyboardButton(text=f"{flag} {fiat}", callback_data=f"p2p:pair:{action}:{fiat}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="‹ Назад", callback_data="p2p:menu")])
    
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await cb.answer()

# --- СПИСОК ОРДЕРОВ ---
@router.callback_query(F.data.startswith("p2p:pair:"))
async def cb_p2p_pair(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    action, fiat = parts[2], parts[3]
    flag = FIAT_FLAGS.get(fiat, "🏳️")
    
    await generate_fake_orders()
    
    orders = await get_p2p_orders(action, fiat, "USDT")
    
    text = f"{flag} <b>Ордера {action.upper()} USDT за {fiat}</b>\n\n"
    if not orders:
        text += "Нет активных объявлений.\n"
    
    if orders:
        for o in orders[:5]:
            oid, uid, price, amt, lmin, lmax, pay = o
            text += (
                f"👤 ID: <code>{uid}</code>\n"
                f"   Цена: <b>{price} {fiat}</b>\n"
                f"   Объём: {amt} USDT\n"
                f"   Лимиты: {lmin}–{lmax} {fiat}\n"
                f"   Оплата: {pay}\n\n"
            )
    
    text += "➕ Создайте своё объявление кнопкой ниже."
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать объявление", callback_data=f"p2p:create_ad:{action}:{fiat}")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="p2p:menu")]
    ])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

# --- СОЗДАНИЕ ОБЪЯВЛЕНИЯ (FSM) ---
@router.callback_query(F.data.startswith("p2p:create_ad"))
async def cb_p2p_create_ad(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    action = parts[2] if len(parts) > 2 else "buy"
    fiat = parts[3] if len(parts) > 3 else "USD"
    
    await state.update_data(action=action, fiat=fiat)
    await state.set_state(P2PFSM.waiting_price)
    
    text = (
        f"🤝 <b>Создание объявления на {action.upper()} USDT за {fiat}</b>\n\n"
        f"Шаг 1 из 4. Введите <b>цену за 1 USDT</b> в {fiat} (например, 1.01):"
    )
    try: await cb.message.edit_text(text, parse_mode="HTML")
    except: await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()

@router.message(P2PFSM.waiting_price)
async def p2p_waiting_price(msg: Message, state: FSMContext):
    try:
        price = float(msg.text.replace(",", "."))
        if price <= 0: raise ValueError
    except ValueError:
        await msg.answer("❌ Введите корректное число.")
        return
    
    await state.update_data(price=price)
    await state.set_state(P2PFSM.waiting_amount)
    
    data = await state.get_data()
    fiat = data["fiat"]
    await msg.answer(f"Шаг 2 из 4. Введите <b>объём</b> в USDT (например, 100):", parse_mode="HTML")

@router.message(P2PFSM.waiting_amount)
async def p2p_waiting_amount(msg: Message, state: FSMContext):
    try:
        amt = float(msg.text.replace(",", "."))
        if amt <= 0: raise ValueError
    except ValueError:
        await msg.answer("❌ Введите корректное число.")
        return
    
    await state.update_data(amount=amt)
    await state.set_state(P2PFSM.waiting_limits)
    
    await msg.answer("Шаг 3 из 4. Введите <b>лимиты</b> в формате: <code>10-100</code> (от 10 до 100):", parse_mode="HTML")

@router.message(P2PFSM.waiting_limits)
async def p2p_waiting_limits(msg: Message, state: FSMContext):
    try:
        parts = msg.text.replace(" ", "").split("-")
        lim_min = float(parts[0].replace(",", "."))
        lim_max = float(parts[1].replace(",", "."))
        if lim_min >= lim_max or lim_min <= 0: raise ValueError
    except:
        await msg.answer("❌ Неверный формат. Пример: <code>10-100</code>", parse_mode="HTML")
        return
    
    await state.update_data(lim_min=lim_min, lim_max=lim_max)
    await state.set_state(P2PFSM.waiting_pay_method)
    
    await msg.answer("Шаг 4 из 4. Введите <b>способ оплаты</b> (например, Сбербанк):", parse_mode="HTML")

@router.message(P2PFSM.waiting_pay_method)
async def p2p_waiting_pay(msg: Message, state: FSMContext):
    pay_method = msg.text.strip()
    if not pay_method:
        await msg.answer("❌ Введите название банка.")
        return
    
    data = await state.get_data()
    action = data["action"]
    fiat = data["fiat"]
    price = data["price"]
    amt = data["amount"]
    lim_min = data["lim_min"]
    lim_max = data["lim_max"]
    
    await create_p2p_order(msg.from_user.id, action, fiat, "USDT", price, amt, lim_min, lim_max, pay_method)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 К ордерам", callback_data=f"p2p:pair:{action}:{fiat}")],
        [InlineKeyboardButton(text="‹ В меню P2P", callback_data="p2p:menu")]
    ])
    await msg.answer(
        f"✅ <b>Объявление создано!</b>\n\n"
        f"Тип: {action.upper()}\n"
        f"Цена: {price} {fiat}\n"
        f"Объём: {amt} USDT\n"
        f"Лимиты: {lim_min}–{lim_max} {fiat}\n"
        f"Банк: {pay_method}",
        reply_markup=kb, parse_mode="HTML"
    )
    await state.clear()

# --- ОСТАЛЬНОЕ ---
@router.callback_query(F.data == "p2p:my_deals")
async def cb_p2p_my_deals(cb: CallbackQuery):
    text = "Здесь вы можете посмотреть свои сделки за всё время.\n\n<b>Количество подходящих сделок: 0</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад в P2P", callback_data="p2p:menu")]])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "p2p:settings")
async def cb_p2p_settings(cb: CallbackQuery):
    text = "Здесь вы можете выбрать валюту отображаемых объявлений или управлять своими способами оплаты."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="p2p:menu")]])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "p2p:profile")
async def cb_p2p_profile(cb: CallbackQuery):
    text = "⭐ <b>Ваш профиль</b>\n\n🏆 <b>0 сделок · 0% выполнено · $0</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="p2p:menu")]])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()