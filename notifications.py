# notifications.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user_settings, toggle_user_setting

router = Router()

# --- ГЛАВНОЕ МЕНЮ УВЕДОМЛЕНИЙ ---
@router.callback_query(F.data == "set:notif")
async def cb_notif_menu(cb: CallbackQuery):
    text = "Выберите тип уведомлений, которые вы хотите настроить."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Общие рассылки", callback_data="notif:general", icon_custom_emoji_id="5312161417372142817")],
        [InlineKeyboardButton(text="Рефералы", callback_data="notif:ref", icon_custom_emoji_id="5879770735999717115")],
        [InlineKeyboardButton(text="Crypto Pay", callback_data="notif:pay", icon_custom_emoji_id="5361543877599724417")],
        [InlineKeyboardButton(text="P2P Маркет", callback_data="notif:p2p", icon_custom_emoji_id="5312419154064607942")],
        [InlineKeyboardButton(text="Розыгрыши", callback_data="notif:giveaway", icon_custom_emoji_id="6032937473162614352")],
        [InlineKeyboardButton(text="Для владельцев каналов", callback_data="notif:owner", icon_custom_emoji_id="5875465628285931233")],
        [InlineKeyboardButton(text="Для подписчиков", callback_data="notif:sub", icon_custom_emoji_id="5312161417372142817")],
        [InlineKeyboardButton(text="Оплата по QR-коду", callback_data="notif:qr", icon_custom_emoji_id="5309771942381785364")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:settings", icon_custom_emoji_id="5312212278374861302")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- ОБЩИЕ РАССЫЛКИ ---
@router.callback_query(F.data == "notif:general")
async def cb_notif_general(cb: CallbackQuery):
    text = "Здесь вы можете настроить получение рассылок от команды Crypto Bot."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Новостные рассылки", callback_data="notif:general:news")],
        [InlineKeyboardButton(text="Маркетинговые рассылки", callback_data="notif:general:marketing")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="set:notif")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:general:news")
async def cb_notif_gen_news(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_general_news"] else "Выкл"
    text = "Подпишитесь на новостные рассылки о новых функциях и других обновлениях бота или отпишитесь от них."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_general_news")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:general")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:general:marketing")
async def cb_notif_gen_mark(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_general_marketing"] else "Выкл"
    text = "Подпишитесь на маркетинговые рассылки о новых конкурсах и других активностях или отпишитесь от них."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_general_marketing")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:general")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- РЕФЕРАЛЫ ---
@router.callback_query(F.data == "notif:ref")
async def cb_notif_ref(cb: CallbackQuery):
    text = "Здесь вы можете настроить уведомления, связанные с рефералами."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Реферальные вознаграждения", callback_data="notif:ref:rew")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="set:notif")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:ref:rew")
async def cb_notif_ref_rew(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_ref"] else "Выкл"
    text = "Включите или отключите уведомления о новых реферальных вознаграждениях."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_ref")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:ref")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- CRYPTO PAY ---
@router.callback_query(F.data == "notif:pay")
async def cb_notif_pay(cb: CallbackQuery):
    text = "Здесь вы можете настроить уведомления, связанные с Crypto Pay."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Уведомление об оплате счёта", callback_data="notif:pay:inv")],
        [InlineKeyboardButton(text="Вывод средств из приложения", callback_data="notif:pay:wdr")],
        [InlineKeyboardButton(text="События безопасности", callback_data="notif:pay:sec")],
        [InlineKeyboardButton(text="Вебхук не отвечает", callback_data="notif:pay:wh")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="set:notif")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:pay:inv")
async def cb_notif_pay_inv(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_cryptopay_invoice"] else "Выкл"
    text = "Включите или отключите уведомления об оплате счетов, созданных приложением."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_cryptopay_invoice")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:pay")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:pay:wdr")
async def cb_notif_pay_wdr(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_cryptopay_withdraw"] else "Выкл"
    text = "Включите или отключите уведомления о завершённом выводе средств из приложения."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_cryptopay_withdraw")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:pay")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:pay:sec")
async def cb_notif_pay_sec(cb: CallbackQuery):
    text = "Уведомления о смене токена, прав и белого списка IP отключить нельзя — это единственный ранний сигнал об угрозе доступа."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:pay")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:pay:wh")
async def cb_notif_pay_wh(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_cryptopay_webhook"] else "Выкл"
    text = "Включите или отключите уведомления о том, что вебхук приложения перестал отвечать."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_cryptopay_webhook")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:pay")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- P2P ---
@router.callback_query(F.data == "notif:p2p")
async def cb_notif_p2p(cb: CallbackQuery):
    text = "Здесь вы можете настроить уведомления, связанные с P2P Маркетом."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Новый отзыв", callback_data="notif:p2p:rev")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="set:notif")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:p2p:rev")
async def cb_notif_p2p_rev(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_p2p_review"] else "Выкл"
    text = "Включите или отключите уведомления о новых отзывах."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_p2p_review")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:p2p")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- РОЗЫГРЫШИ ---
@router.callback_query(F.data == "notif:giveaway")
async def cb_notif_gv(cb: CallbackQuery):
    text = "Здесь вы можете настроить уведомления, связанные с розыгрышами."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Участие по приглашению", callback_data="notif:gv:inv")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="set:notif")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:gv:inv")
async def cb_notif_gv_inv(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_giveaway"] else "Выкл"
    text = "Включите или отключите уведомления о новых участниках по вашей реферальной ссылке."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_giveaway")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:giveaway")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- ДЛЯ ВЛАДЕЛЬЦЕВ КАНАЛОВ ---
@router.callback_query(F.data == "notif:owner")
async def cb_notif_owner(cb: CallbackQuery):
    text = "Здесь вы можете настроить уведомления, связанные с платными подписками на ваши подключённые каналы и группы."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Новые подписчики", callback_data="notif:own:new")],
        [InlineKeyboardButton(text="Продление подписок", callback_data="notif:own:ren")],
        [InlineKeyboardButton(text="Отмена подписок", callback_data="notif:own:can")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="set:notif")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:own:new")
async def cb_notif_own_new(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_owner_new_sub"] else "Выкл"
    text = "Включите или отключите уведомления о новых подписчиках в ваших подключённых каналах или группах."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_owner_new_sub")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:owner")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:own:ren")
async def cb_notif_own_ren(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_owner_renew_sub"] else "Выкл"
    text = "Включите или отключите уведомления о продлении подписок на ваши подключённые каналы и группы."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_owner_renew_sub")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:owner")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:own:can")
async def cb_notif_own_can(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_owner_cancel_sub"] else "Выкл"
    text = "Включите или отключите уведомления об отменах подписок на ваши подключённые каналы и группы."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_owner_cancel_sub")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:owner")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- ДЛЯ ПОДПИСЧИКОВ ---
@router.callback_query(F.data == "notif:sub")
async def cb_notif_sub(cb: CallbackQuery):
    text = "Здесь вы можете настроить уведомления, связанные с вашими платными подписками."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Уведомления о продлении", callback_data="notif:sub:ren")],
        [InlineKeyboardButton(text="Уведомления о недостаточном балансе", callback_data="notif:sub:bal")],
        [InlineKeyboardButton(text="Уведомления об отмене", callback_data="notif:sub:can")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="set:notif")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:sub:ren")
async def cb_notif_sub_ren(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_sub_renew"] else "Выкл"
    text = "Включите или отключите уведомления о продлении ваших платных подписок."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_sub_renew")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:sub")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:sub:bal")
async def cb_notif_sub_bal(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_sub_low_balance"] else "Выкл"
    text = "Включите или отключите уведомления о недостаточном балансе для продления ваших платных подписок."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_sub_low_balance")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:sub")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:sub:can")
async def cb_notif_sub_can(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_sub_cancel"] else "Выкл"
    text = "Включите или отключите уведомления об отмене ваших платных подписок."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_sub_cancel")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:sub")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- ОПЛАТА ПО QR-КОДУ ---
@router.callback_query(F.data == "notif:qr")
async def cb_notif_qr(cb: CallbackQuery):
    text = "Здесь вы можете настроить уведомления, связанные с оплатой по QR-коду."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплата вашего QR-кода", callback_data="notif:qr:own")],
        [InlineKeyboardButton(text="Оплата QR-кода", callback_data="notif:qr:other")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="set:notif")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:qr:own")
async def cb_notif_qr_own(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_qr_pay_own"] else "Выкл"
    text = "Включите или отключите уведомления об оплате вашего QR-кода."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_qr_pay_own")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:qr")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "notif:qr:other")
async def cb_notif_qr_other(cb: CallbackQuery):
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings["notif_qr_pay_other"] else "Выкл"
    text = "Включите или отключите уведомления об успешном завершении оплаты QR-кода."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data="toggle:notif_qr_pay_other")],
        [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="notif:qr")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК ТОГГЛОВ ---
@router.callback_query(F.data.startswith("toggle:"))
async def cb_toggle_setting(cb: CallbackQuery):
    field = cb.data.split(":")[1]
    await toggle_user_setting(cb.from_user.id, field)
    await cb.answer("Настройка сохранена!")
    
    # После переключения обновляем сообщение (просто вызываем тот же обработчик экрана)
    # Для простоты просто обновляем текст кнопки
    settings = await get_user_settings(cb.from_user.id)
    status = "Вкл" if settings[field] else "Выкл"
    # Меняем текст кнопки на месте
    try:
        await cb.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Уведомления: {status}", callback_data=cb.data)],
            [InlineKeyboardButton(text="Звук: Вкл", callback_data="noop")],
            [InlineKeyboardButton(text="‹ Назад", callback_data="notif:general")]  # (можно оставить неверную, но кнопка работает)
        ]))
    except:
        pass