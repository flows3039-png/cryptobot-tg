# extra_menus.py
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import (
    invoices_menu_kb, invoice_type_kb, invoice_currency_kb, invoice_manage_kb
)
from database import (
    create_invoice, get_invoice, pay_invoice,
    CheckError, InsufficientFunds, get_user
)

router = Router()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

E_SUBS = '<tg-emoji emoji-id="5312161417372142817">📢</tg-emoji>'
E_CONNECT = '<tg-emoji emoji-id="5309795500277403547">💼</tg-emoji>'
E_GIVEAWAY_1 = '<tg-emoji emoji-id="5361986358015463601">🎁</tg-emoji>'
E_GIVEAWAY_2 = '<tg-emoji emoji-id="5361914370068613491">🦋</tg-emoji>'

class InvoiceFSM(StatesGroup):
    waiting_type = State()
    waiting_currency = State()
    waiting_amount = State()
    waiting_desc = State()

# --- ПОДПИСКИ ---
@router.callback_query(F.data == "menu:subs")
async def cb_subs(cb: CallbackQuery):
    text = (
        f"{E_SUBS} Здесь вы можете управлять своими платными подписками.\n\n"
        f"{E_CONNECT} Подключите свой канал или группу, чтобы получать доход. Комиссия 5% включена в цену подписки. "
        "<a href=\"https://youtu.be/ваша_ссылка\">Смотреть видеоинструкцию ›</a>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍑 Подключить...", callback_data="subs:connect")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:main")]
    ])
    try: await cb.message.delete()
    except: pass
    
    video_path = os.path.join(BASE_DIR, "subs_video.mp4")
    if os.path.exists(video_path):
        await cb.message.answer_video(video=FSInputFile(video_path), caption=text, reply_markup=kb, parse_mode="HTML", show_caption_above_media=True, disable_web_page_preview=True)
    else:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()

@router.callback_query(F.data == "subs:connect")
async def cb_subs_connect(cb: CallbackQuery):
    text = (
        "<b>Чтобы подключить канал, выполните эти действия:</b>\n\n"
        "1. Добавьте @CryptoBotOfficialbot в качестве администратора вашего канала или группы.\n"
        "2. Затем перешлите сюда любое сообщение, отправленное от имени чата. Чтобы подключить группу, пришлите идентификатор чата."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить в канал ↗", url="https://t.me/CryptoBotOfficialbot?startchannel=true")],
        [InlineKeyboardButton(text="Добавить в группу +", url="https://t.me/CryptoBotOfficialbot?startgroup=true")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:subs")]
    ])
    try: await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    except: await cb.message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()

# --- СЧЕТА ---
@router.callback_query(F.data == "menu:invoices")
async def cb_invoices(cb: CallbackQuery):
    text = (
        "🧾 Здесь вы можете создать счёт для получения оплаты или сбора средств в криптовалюте. "
        "<a href=\"https://youtu.be/hOxI23ZFtVI\">Смотрите видеоинструкцию ›</a>\n\n"
        "Попробовать счета можно в @CryptoBotDonates."
    )
    kb = invoices_menu_kb()
    try: await cb.message.delete()
    except: pass
    
    video_path = os.path.join(BASE_DIR, "invoice_video.mp4")
    fallback_video = os.path.join(BASE_DIR, "subs_video.mp4")
    
    if os.path.exists(video_path):
        await cb.message.answer_video(video=FSInputFile(video_path), caption=text, reply_markup=kb, parse_mode="HTML", show_caption_above_media=True, disable_web_page_preview=True)
    elif os.path.exists(fallback_video):
        await cb.message.answer_video(video=FSInputFile(fallback_video), caption=text, reply_markup=kb, parse_mode="HTML", show_caption_above_media=True, disable_web_page_preview=True)
    else:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()

@router.callback_query(F.data == "invoice:create")
async def cb_invoice_create(cb: CallbackQuery):
    text = "<b>Выберите тип счёта:</b>\n\n" \
           "• <b>Одноразовый</b> — для получения оплаты от одного человека.\n" \
           "• <b>Многоразовый</b> — для сбора средств (ссылка будет активна, пока вы её не закроете)."
    kb = invoice_type_kb()
    try: await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except: await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("inv_type:"))
async def cb_invoice_type(cb: CallbackQuery, state: FSMContext):
    is_multi = cb.data.split(":")[1] == "multi"
    await state.update_data(is_multi=is_multi)
    
    text = "<b>Выберите валюту счёта:</b>"
    kb = invoice_currency_kb()
    try: await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except: await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("inv_cur:"))
async def cb_invoice_currency(cb: CallbackQuery, state: FSMContext):
    ticker = cb.data.split(":")[1]
    await state.update_data(ticker=ticker)
    await state.set_state(InvoiceFSM.waiting_amount)
    
    text = f"<b>Введите сумму счёта в {ticker}:</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="‹ Назад", callback_data="invoice:create")]
    ])
    try: await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except: await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.message(InvoiceFSM.waiting_amount)
async def cb_invoice_amount(msg: Message, state: FSMContext):
    try:
        amt = float(msg.text.replace(",", "."))
        if amt <= 0: raise ValueError
    except ValueError:
        await msg.answer("❌ Введите корректное число.")
        return
    
    await state.update_data(amount=amt)
    await state.set_state(InvoiceFSM.waiting_desc)
    
    text = "<b>Введите описание счёта</b> (например, «Донат на развитие»):"
    await msg.answer(text, parse_mode="HTML")

@router.message(InvoiceFSM.waiting_desc)
async def cb_invoice_desc(msg: Message, state: FSMContext):
    desc = msg.text.strip()
    data = await state.get_data()
    
    ticker = data["ticker"]
    amt = data["amount"]
    is_multi = data["is_multi"]
    
    try:
        invoice_id = await create_invoice(msg.from_user.id, ticker, amt, desc, is_multi)
    except Exception as e:
        await msg.answer(f"❌ Ошибка создания счёта: {e}")
        return
    
    bot_info = await msg.bot.get_me()
    kb = invoice_manage_kb(invoice_id, amt, ticker, bot_username=bot_info.username)
    
    text = (
        f"✅ <b>Счёт создан!</b>\n\n"
        f"Описание: {desc}\n"
        f"Сумма: {amt:g} {ticker}\n"
        f"Тип: {'Многоразовый' if is_multi else 'Одноразовый'}"
    )
    
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.clear()

async def show_invoice_card(msg: Message, state: FSMContext):
    inv_id = ""
    if "invoice_" in msg.text:
        inv_id = msg.text.split("invoice_", 1)[1].strip()
    elif "inv_" in msg.text:
        inv_id = msg.text.split("inv_", 1)[1].strip()

    inv_id = inv_id.split()[0] if inv_id else ""
    if not inv_id:
        await msg.answer("❌ Неверная ссылка на счёт.")
        return

    inv = await get_invoice(inv_id)
    if not inv:
        await msg.answer("❌ Счёт не найден.")
        return
    if inv["status"] != "active":
        await msg.answer("❌ Этот счёт уже был оплачен или закрыт.")
        return

    creator = await get_user(inv["creator_id"])
    creator_name = f"@{creator['username']}" if creator and creator.get("username") else f"ID {inv['creator_id']}"

    text = (
        f"🧾 <b>Счёт на оплату</b>\n\n"
        f"Получатель: <b>{creator_name}</b>\n"
        f"Сумма: <b>{inv['amount']:g} {inv['asset']}</b>\n"
        f"Описание: <i>{inv['description'] or 'Без описания'}</i>\n\n"
        f"Нажмите кнопку ниже, чтобы оплатить со своего баланса кошелька."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Оплатить {inv['amount']:g} {inv['asset']}", callback_data=f"pay_inv:{inv_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu:main")]
    ])

    await msg.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("pay_inv:"))
async def cb_pay_invoice(cb: CallbackQuery):
    inv_id = cb.data.split("pay_inv:", 1)[1].strip()
    try:
        res = await pay_invoice(inv_id, cb.from_user.id)
        await cb.message.edit_text(
            f"✅ <b>Счёт успешно оплачен!</b>\n\n"
            f"Вы перевели <b>{res['amount']:g} {res['asset']}</b>.",
            parse_mode="HTML"
        )
        payer_name = f"@{cb.from_user.username}" if cb.from_user.username else f"ID {cb.from_user.id}"
        try:
            await cb.bot.send_message(
                chat_id=res["creator_id"],
                text=f"🔔 <b>Оплата по счёту #{inv_id}</b>\n\n"
                     f"Пользователь {payer_name} оплатил счёт на <b>{res['amount']:g} {res['asset']}</b>!",
                parse_mode="HTML"
            )
        except Exception:
            pass
    except CheckError as e:
        if e.code == "own_invoice":
            await cb.answer("❌ Вы не можете оплатить свой собственный счёт.", show_alert=True)
        elif e.code == "already_paid":
            await cb.answer("❌ Этот счёт уже был оплачен.", show_alert=True)
        elif e.code == "exhausted":
            await cb.answer("❌ Счёт уже оплачен или не активен.", show_alert=True)
        else:
            await cb.answer(f"❌ Ошибка: {e.code}", show_alert=True)
    except InsufficientFunds:
        await cb.answer("❌ Недостаточно средств на балансе кошелька.", show_alert=True)
    await cb.answer()

# --- РОЗЫГРЫШИ ---
@router.callback_query(F.data == "menu:giveaways")
async def cb_giveaways(cb: CallbackQuery):
    text = (
        f"{E_GIVEAWAY_1} Здесь вы можете создать розыгрыш криптовалюты среди подписчиков вашего канала, "
        "чтобы привлечь новую аудиторию, поощрить текущих подписчиков или прорекламировать канал.\n\n"
        f"{E_GIVEAWAY_2} Crypto Bot распределит криптовалюту случайным образом среди участников розыгрыша."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать розыгрыш", callback_data="gw:create")],
        [InlineKeyboardButton(text="Управление розыгрышами", callback_data="gw:manage")],
        [InlineKeyboardButton(text="Мой профиль", callback_data="gw:profile")],
        [InlineKeyboardButton(text="Оставить отзыв ↗", url="https://t.me/CryptoBotRU")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:main")]
    ])
    try: await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except: await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "gw:profile")
async def cb_gw_profile(cb: CallbackQuery):
    text = (
        "Здесь вы можете настроить отображение вашего профиля в списке победителей розыгрышей, в которых вы принимаете участие.\n\n"
        "Ваш Telegram-профиль будет показываться в списке победителей."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Скрыть профиль: Нет", callback_data="gw:toggle_hide")],
        [InlineKeyboardButton(text="История участия", callback_data="gw:history")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:giveaways")]
    ])
    try: await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except: await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.in_(["gw:create", "gw:manage", "gw:history", "gw:toggle_hide"]))
async def cb_gw_stub(cb: CallbackQuery):
    await cb.answer("Раздел в разработке.", show_alert=True)