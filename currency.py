# currency.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import update_user_setting, get_user
from keyboards import settings_kb

router = Router()

# --- ВЫБОР ЛОКАЛЬНОЙ ВАЛЮТЫ ---
@router.callback_query(F.data == "set:fiat")
async def cb_fiat_menu(cb: CallbackQuery):
    # Получаем текущую валюту пользователя
    user = await get_user(cb.from_user.id)
    current_fiat = user[3] if user else "USD"
    
    # Список всех валют
    fiats = ["RUB", "USD", "EUR", "BYN", "UAH", "GBP", "CNY", "KZT", "UZS", "GEL", "TRY", "AMD", "THB", "INR", "BRL", "IDR", "AZN", "AED", "PLN", "ILS", "KGS", "TJS", "LKR", "MDL"]
    
    # Функция для форматирования текста кнопки (добавляет точки, если валюта текущая)
    def f_text(f):
        return f"· {f} ·" if f == current_fiat else f
    
    # Строим сетку 4x6
    buttons = []
    row = []
    for i, f in enumerate(fiats):
        row.append(InlineKeyboardButton(text=f_text(f), callback_data=f"fiat:{f}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton(text="‹ Назад", callback_data="menu:settings")])
    
    text = "Выберите локальную валюту."
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- ОБРАБОТКА ВЫБОРА ВАЛЮТЫ ---
@router.callback_query(F.data.startswith("fiat:"))
async def cb_fiat_select(cb: CallbackQuery):
    currency = cb.data.split(":")[1]
    
    # Сохраняем валюту в БД
    await update_user_setting(cb.from_user.id, "fiat_currency", currency)
    
    # Получаем обновленные данные пользователя
    user = await get_user(cb.from_user.id)
    tz = user[2] if user else "Europe/Moscow"
    fiat = user[3] if user else "USD"
    
    # Формируем текст настроек
    text = (
        f"👤 <b>{cb.from_user.first_name}</b>\n\n"
        f"Часовой пояс: <b>{tz}</b>\n"
        f"Локальная валюта: <b>{fiat}</b>"
    )
    
    # Возвращаем в меню настроек с обновленными данными
    await cb.message.edit_text(text, reply_markup=settings_kb(fiat), parse_mode="HTML")
    await cb.answer(f"Валюта изменена на {currency}!")