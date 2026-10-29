# more.py
import os
import secrets
import aiosqlite
import re
import httpx
import time
import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, FSInputFile, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
    LinkPreviewOptions
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import CURRENCIES, _e
from database import (
    create_check, activate_check,
    get_balance, get_all_balances, DB_PATH,
    InsufficientFunds, CheckError,
    update_check_message, get_check_message,
    get_check_business_conn,
    create_quote, execute_swap,
    get_mid_prices
)
from keyboards import (
    checks_menu_kb, check_manage_kb, check_activated_kb,
    currency_select_kb, cryptopay_menu_kb,
    swap_from_kb, swap_to_kb, check_activated_user_kb,
    update_user_chat_menu_button
)
from check_logger import log_check_error

log = logging.getLogger("check_image")

router = Router()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from image_gen import fetch_check_image

class CheckFSM(StatesGroup):
    waiting_amount = State()
    waiting_activate_pass = State()

class SwapFSM(StatesGroup):
    waiting_amount = State()

# --- ФУНКЦИЯ ДЛЯ РЕДАКТИРОВАНИЯ СООБЩЕНИЯ ЧЕКА (BUSINESS / INLINE / CHAT) ---
async def finalize_business_check(bot, cid: str, new_text: str, disabled_kb) -> bool:
    raw = await get_check_message(cid)
    bcid = await get_check_business_conn(cid)
    log.info("finalize cid=%s raw=%r bcid=%r", cid, raw, bcid)

    if not raw:
        log.warning("no message mapping for check %s", cid)
        return False

    # 1. Inline message (no ':')
    if ":" not in raw:
        try:
            await bot.edit_message_caption(
                inline_message_id=raw,
                caption=new_text,
                parse_mode="HTML",
                reply_markup=disabled_kb,
            )
            return True
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return True
            try:
                await bot.edit_message_text(
                    inline_message_id=raw,
                    text=new_text,
                    parse_mode="HTML",
                    reply_markup=disabled_kb,
                )
                return True
            except Exception as ex:
                log.warning("Failed to edit inline message %s: %s", raw, ex)
                return False
        except Exception as ex:
            log.warning("Failed to edit inline message %s: %s", raw, ex)
            return False

    # 2. Chat message (chat_id:message_id) with or without business connection
    try:
        chat_id, message_id = map(int, raw.split(":", 1))
    except Exception as e:
        log.warning("Invalid raw message format %r for check %s: %s", raw, cid, e)
        return False

    kwargs = {
        "chat_id": chat_id,
        "message_id": message_id,
        "caption": new_text,
        "parse_mode": "HTML",
        "reply_markup": disabled_kb,
    }
    if bcid:
        kwargs["business_connection_id"] = bcid

    try:
        await bot.edit_message_caption(**kwargs)
        return True
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return True
        if "message to edit not found" in err or "business_connection_invalid" in err:
            log.warning("Message %s:%s cannot be edited: %s", chat_id, message_id, e)
            return False
        text_kwargs = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": new_text,
            "parse_mode": "HTML",
            "reply_markup": disabled_kb,
        }
        if bcid:
            text_kwargs["business_connection_id"] = bcid
        try:
            await bot.edit_message_text(**text_kwargs)
            return True
        except Exception:
            return False
    except Exception as e:
        log.warning("Error editing check message %s: %s", cid, e)
        return False

# --- ОБМЕН (SWAP) ---
@router.callback_query(F.data == "menu:swap")
async def cb_swap_menu(cb: CallbackQuery):
    try: await cb.message.delete()
    except: pass
    text = f"{_e('arrows_diff', '🔄')} <b>Обмен криптовалют</b>\n\nВыберите валюту, которую хотите <b>отдать</b>:"
    await cb.message.answer(text, reply_markup=swap_from_kb(), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("swap:from:"))
async def cb_swap_from(cb: CallbackQuery, state: FSMContext):
    ticker = cb.data.split(":")[2]
    bal = await get_balance(cb.from_user.id, ticker)
    if bal <= 0:
        await cb.answer(f"У вас нет средств в {ticker}!", show_alert=True)
        return
    await state.update_data(from_asset=ticker)
    await state.set_state(SwapFSM.waiting_amount)
    await cb.message.edit_text(
        f"{_e('arrows_diff', '🔄')} <b>Обмен</b>\n\nВы отдаете: <b>{ticker}</b>\n\nВыберите валюту, которую хотите <b>получить</b>:",
        reply_markup=swap_to_kb(ticker),
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data.startswith("swap:to:"))
async def cb_swap_to(cb: CallbackQuery, state: FSMContext):
    ticker = cb.data.split(":")[2]
    data = await state.get_data()
    from_asset = data.get("from_asset")
    await state.update_data(to_asset=ticker)
    await cb.message.edit_text(
        f"{_e('arrows_diff', '🔄')} <b>Обмен</b>\n\nМеняем: <b>{from_asset}</b> → <b>{ticker}</b>\n\nВведите сумму:",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(SwapFSM.waiting_amount)
async def process_swap_amount(msg: Message, state: FSMContext):
    try:
        amt = float((msg.text or "").replace(",", "."))
        if amt <= 0: raise ValueError
    except ValueError:
        await msg.answer("❌ Введите корректное число.")
        return

    data = await state.get_data()
    from_asset = data["from_asset"]
    to_asset = data["to_asset"]
    
    bal = await get_balance(msg.from_user.id, from_asset)
    if amt > bal:
        await msg.answer(f"❌ Недостаточно средств. Баланс: {bal:.4f} {from_asset}")
        return

    try:
        quote = await create_quote(msg.from_user.id, from_asset, to_asset, amt)
    except Exception as e:
        await msg.answer(f"❌ Ошибка получения курса: {e}")
        return

    text = (
        f"<b>Подтверждение обмена</b>\n\n"
        f"Вы отдаете: <b>{quote['from_amount']:.4f} {from_asset}</b>\n"
        f"Вы получаете: <b>{quote['to_amount']:.4f} {to_asset}</b>\n\n"
        f"Курс: 1 {from_asset} = {quote['rate']:.4f} {to_asset}\n"
        f"Комиссия: {quote['fee_bps'] / 100}%\n\n"
        f"<i>Курс зафиксирован на 15 секунд.</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить обмен", callback_data=f"swap_confirm:{quote['id']}", icon_custom_emoji_id="5825794181183836432")],
        [InlineKeyboardButton(text="Отмена", callback_data="menu:main", icon_custom_emoji_id="5778527486270770928")]
    ])
    
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data.startswith("swap_confirm:"))
async def cb_swap_confirm(cb: CallbackQuery):
    quote_id = cb.data.split(":")[1]
    try:
        res = await execute_swap(cb.from_user.id, quote_id)
        await cb.message.edit_text(
            f"✅ <b>Обмен выполнен!</b>\n\n"
            f"Вы обменяли {res['from_amount']:.4f} {res['from_asset']} на {res['to_amount']:.4f} {res['to_asset']}.",
            parse_mode="HTML"
        )
    except CheckError as e:
        await cb.message.edit_text("❌ Время действия курса истекло.")
    except InsufficientFunds:
        await cb.message.edit_text("❌ Недостаточно средств.")
    await cb.answer()

# --- ЧЕКИ ---
@router.callback_query(F.data.in_(["menu:checks", "more:checks"]))
async def cb_checks(cb: CallbackQuery):
    text = (
        "🧾 Здесь вы можете создать чек для мгновенной отправки криптовалюты любому пользователю. "
        "<a href=\"https://youtu.be/hOxI23ZFtVI\">Смотреть видеоинструкцию ›</a>"
    )
    kb = checks_menu_kb()
    try: await cb.message.delete()
    except: pass
    
    video_path = os.path.join(BASE_DIR, "check_video.mp4")
    photo_path = os.path.join(BASE_DIR, "check_banner.jpg")
    
    if os.path.exists(video_path):
        await cb.message.answer_video(video=FSInputFile(video_path), caption=text, parse_mode="HTML", reply_markup=kb, show_caption_above_media=True)
    elif os.path.exists(photo_path):
        await cb.message.answer_photo(photo=FSInputFile(photo_path), caption=text, parse_mode="HTML", reply_markup=kb, show_caption_above_media=True)
    else:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    await cb.answer()

@router.message(F.text.regexp(r"^/(?:ч|чек|c|check)(?:\s*|\s+.*)$", flags=re.IGNORECASE))
async def cmd_check_text(msg: Message):
    # Моментальное фоновое удаление команды в первую миллисекунду
    try:
        asyncio.create_task(msg.delete())
    except Exception:
        pass

    text_raw = (msg.text or "").strip()
    match = re.match(r"^/(?:ч|чек|c|check)\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z]{2,10})(?:\s+(.+))?$", text_raw, flags=re.IGNORECASE)
    if not match:
        await msg.answer("❌ Формат: <code>/ч 10 USDT [пароль]</code>", parse_mode="HTML")
        return

    amt_str = match.group(1)
    ticker_str = match.group(2)
    password = match.group(3).strip() if match.group(3) else None
    if not amt_str or not ticker_str:
        await msg.answer("❌ Формат: <code>/ч 10 USDT [пароль]</code>", parse_mode="HTML")
        return

    try:
        amt = float(amt_str.replace(",", "."))
    except ValueError:
        await msg.answer("❌ Введите корректную сумму.")
        return

    ticker = ticker_str.upper()
    if ticker not in CURRENCIES:
        await msg.answer(f"❌ Неизвестная валюта. Доступно: {', '.join(CURRENCIES.keys())}")
        return

    bal = await get_balance(msg.from_user.id, ticker)
    if amt > bal:
        await msg.answer(f"❌ Недостаточно средств. Баланс: {bal:.4f} {ticker}")
        return

    try:
        cid = await create_check(msg.from_user.id, ticker, amt, password=password)
    except InsufficientFunds:
        await msg.answer("❌ Недостаточно средств.")
        return
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")
        return

    try:
        prices = await get_mid_prices()
        price_usd = prices.get(ticker, 0)
    except Exception:
        price_usd = CURRENCIES.get(ticker, {}).get("price_usd", 0)
        
    fiat_str = f"${amt * price_usd:.2f}"
    check_icon = '<tg-emoji emoji-id="5311998535032409760">🧾</tg-emoji>'
    usdt_icon = '<tg-emoji emoji-id="6035288280562404083">🪙</tg-emoji>' if ticker == "USDT" else ""
    text = f"{check_icon} Чек на {usdt_icon} {amt:g} {ticker} ({fiat_str})."

    try:
        img_bytes = await fetch_check_image(ticker, f"{amt:g}", f"{amt * price_usd:.2f}", check_id=cid)
        photo = BufferedInputFile(img_bytes, filename=f"check_{cid}.png")
        sent_msg = await msg.answer_photo(
            photo=photo, 
            caption=text, 
            reply_markup=check_manage_kb(cid, amt, ticker), 
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        log.error(f"Ошибка отправки фото: {e}")
        await msg.answer(f"❌ Ошибка генерации чека: {e}")
        return

    if sent_msg:
        await update_check_message(cid, sent_msg.chat.id, sent_msg.message_id)

@router.callback_query(F.data == "check:create")
async def cb_check_create(cb: CallbackQuery):
    try: await cb.message.delete()
    except: pass
    await cb.message.answer(f"{_e('check_btn', '🧾')} <b>Создание чека</b>\n\nВыберите валюту:", reply_markup=currency_select_kb("check"), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("wallet:check:"))
async def cb_check_currency(cb: CallbackQuery, state: FSMContext):
    ticker = cb.data.split(":")[2]
    bal = await get_balance(cb.from_user.id, ticker)
    try:
        prices = await get_mid_prices()
        price_usd = prices.get(ticker, 0)
    except:
        price_usd = CURRENCIES.get(ticker, {}).get("price_usd", 0)

    if bal * price_usd < 0.02:
        try: await cb.message.delete()
        except: pass
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад к чекам", callback_data="menu:checks")]])
        await cb.message.answer("Недостаточно монет. Сумма одного чека не может быть меньше чем $0.02.", reply_markup=kb, parse_mode="HTML")
        await cb.answer()
        return
    await state.update_data(cur=ticker)
    await state.set_state(CheckFSM.waiting_amount)
    try: await cb.message.delete()
    except: pass
    await cb.message.answer(f"{_e('check_btn', '🧾')} <b>Чек в {ticker}</b>\n\nВаш баланс: <b>{bal:.4f} {ticker}</b>\n\nВведите сумму чека:", parse_mode="HTML")
    await cb.answer()

@router.message(CheckFSM.waiting_amount)
async def proc_check_amount(msg: Message, state: FSMContext):
    try:
        amt = float((msg.text or "").replace(",", "."))
        if amt <= 0: raise ValueError
    except ValueError:
        await msg.answer("❌ Введите корректное число.")
        return
    
    data = await state.get_data()
    ticker = data["cur"]
    bal = await get_balance(msg.from_user.id, ticker)
    if amt > bal:
        await msg.answer(f"❌ Недостаточно средств. Баланс: {bal:.4f} {ticker}")
        return

    await state.update_data(amt=amt)
    
    try:
        prices = await get_mid_prices()
        price_usd = prices.get(ticker, 0)
    except:
        price_usd = CURRENCIES.get(ticker, {}).get("price_usd", 0)
        
    fiat_str = f"${amt * price_usd:.2f}"
    
    check_icon = '<tg-emoji emoji-id="5311998535032409760">🧾</tg-emoji>'
    usdt_icon = '<tg-emoji emoji-id="6035288280562404083">🪙</tg-emoji>' if ticker == "USDT" else ""
    
    preview_text = (
        f"{check_icon} <b>Предпросмотр чека на {usdt_icon} {amt:g} {ticker} ({fiat_str})</b>\n\n"
        f"Проверьте, всё верно? Нажмите «Подтвердить», чтобы создать чек."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить", callback_data="check_confirm", icon_custom_emoji_id="5825794181183836432")],
        [InlineKeyboardButton(text="Отмена", callback_data="menu:main", icon_custom_emoji_id="5778527486270770928")]
    ])

    try:
        img_bytes = await fetch_check_image(ticker, f"{amt:g}", f"{amt * price_usd:.2f}")
        photo = BufferedInputFile(img_bytes, filename=f"preview_{ticker}.png")
        await msg.answer_photo(
            photo=photo, 
            caption=preview_text, 
            reply_markup=kb, 
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        log.error(f"Ошибка отправки фото (предпросмотр): {e}")
        await msg.answer(f"❌ Ошибка генерации картинки: {e}")

@router.callback_query(F.data == "check_confirm")
async def cb_check_confirm(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amt = data.get("amt")
    ticker = data.get("cur")
    
    if not amt or not ticker:
        await cb.answer("Ошибка: данные не найдены. Попробуйте снова.", show_alert=True)
        return

    try:
        cid = await create_check(cb.from_user.id, ticker, amt)
    except InsufficientFunds:
        await cb.answer("❌ Недостаточно средств.", show_alert=True)
        return
    except Exception as e:
        log_check_error(e, f"cb_check_confirm: ошибка create_check для {cb.from_user.id}")
        await cb.answer(f"❌ Ошибка: {e}", show_alert=True)
        return

    try:
        prices = await get_mid_prices()
        price_usd = prices.get(ticker, 0)
    except:
        price_usd = CURRENCIES.get(ticker, {}).get("price_usd", 0)
        
    fiat_str = f"${amt * price_usd:.2f}"
    check_icon = '<tg-emoji emoji-id="5311998535032409760">🧾</tg-emoji>'
    usdt_icon = '<tg-emoji emoji-id="6035288280562404083">🪙</tg-emoji>' if ticker == "USDT" else ""
    
    text = f"{check_icon} Чек на {usdt_icon} {amt:g} {ticker} ({fiat_str})."

    await cb.message.delete()
    
    try:
        img_bytes = await fetch_check_image(ticker, f"{amt:g}", f"{amt * price_usd:.2f}")
        photo = BufferedInputFile(img_bytes, filename=f"check_{cid}.png")
        sent_msg = await cb.message.answer_photo(
            photo=photo, 
            caption=text, 
            reply_markup=check_manage_kb(cid, amt, ticker), 
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        log.error(f"Ошибка отправки фото: {e}")
        await cb.message.answer(f"❌ Ошибка генерации чека: {e}")
        await cb.answer()
        return

    await update_check_message(cid, sent_msg.chat.id, sent_msg.message_id)
    await state.clear()
    await cb.answer()

async def notify_check_creator(bot: Bot, res: dict, activator_user) -> None:
    creator_id = res.get("creator_id")
    if not creator_id:
        return
    try:
        # имя со ссылкой на профиль
        name = activator_user.first_name or ""
        if activator_user.last_name:
            name += f" {activator_user.last_name}"
        if activator_user.username:
            user_link = f'<a href="https://t.me/{activator_user.username}">{name}</a>'
        else:
            user_link = f'<a href="tg://user?id={activator_user.id}">{name}</a>'

        check_icon = '<tg-emoji emoji-id="5311998535032409760">🧾</tg-emoji>'
        asset = res["asset"]
        amount = res["per_activation"]

        # эмодзи валюты
        if asset == "USDT":
            asset_icon = '<tg-emoji emoji-id="6035288280562404083">💚</tg-emoji>'
        else:
            from config import CURRENCIES
            cur_info = CURRENCIES.get(asset, {})
            emoji_id = cur_info.get("emoji_id", "")
            emoji_fb = cur_info.get("emoji", asset[0])
            asset_icon = f'<tg-emoji emoji-id="{emoji_id}">{emoji_fb}</tg-emoji>' if emoji_id else emoji_fb

        try:
            prices = await get_mid_prices()
            price_usd = prices.get(asset, 0)
        except Exception:
            from config import CURRENCIES
            price_usd = CURRENCIES.get(asset, {}).get("price_usd", 0)

        fiat_val = amount * price_usd

        notify_text = (
            f"{check_icon} {user_link} активировал(а) ваш чек и получил(а) "
            f"{asset_icon} {amount:g} {asset} (${fiat_val:.2f})."
        )
        await bot.send_message(creator_id, notify_text, parse_mode="HTML")
        try:
            creator_balances = await get_all_balances(creator_id)
            await update_user_chat_menu_button(bot, creator_id, creator_balances)
        except Exception:
            pass
    except Exception as e:
        log.warning("Could not notify check creator: %s", e)


async def activate_check_link(msg: Message, state: FSMContext):
    cid = msg.text.split("check_", 1)[1].strip()
    try:
        res = await activate_check(cid, msg.from_user.id, username=msg.from_user.username)
        used = res["activations_used"] + 1
        limit = res["activations_limit"]

        user_balances = await get_all_balances(msg.from_user.id)
        try:
            await update_user_chat_menu_button(msg.bot, msg.from_user.id, user_balances)
        except Exception as ex_mb:
            log.warning("Could not update chat menu button: %s", ex_mb)

        user_kb = check_activated_user_kb(msg.from_user.id, user_balances)
        if limit > 1:
            await msg.answer(f"✅ <b>Вы успешно активировали мульти-чек ({used}/{limit}) на {res['per_activation']} {res['asset']}!</b>", reply_markup=user_kb, parse_mode="HTML")
        else:
            await msg.answer(f"✅ <b>Вы успешно активировали чек на {res['per_activation']} {res['asset']}!</b>", reply_markup=user_kb, parse_mode="HTML")
        
        if used >= limit:
            new_text = f"✅ <b>Чек на {res['per_activation']} {res['asset']} активирован</b>" if limit == 1 else f"✅ <b>Мульти-чек на {res['total_amount']} {res['asset']} полностью активирован ({limit}/{limit})</b>"
            disabled_kb = check_activated_kb()
            await finalize_business_check(msg.bot, cid, new_text, disabled_kb)
        await notify_check_creator(msg.bot, res, msg.from_user)

    except CheckError as e:
        if e.code == "bad_password":
            await state.update_data(cid=cid)
            await state.set_state(CheckFSM.waiting_activate_pass)
            await msg.answer("Чтобы активировать чек, введите пароль:")
        elif e.code == "own_check":
            await msg.answer("❌ Вы не можете активировать свой собственный чек.")
        elif e.code == "not_recipient":
            await msg.answer("❌ Этот чек предназначен для другого пользователя.")
        elif e.code == "exhausted":
            await msg.answer("❌ Этот чек уже активирован.")
        elif e.code == "already_activated":
            await msg.answer("❌ Вы уже активировали этот чек.")
        elif e.code == "not_found":
            try:
                import main as main_mod
                from database import get_inline_check_draft, create_check
                draft = getattr(main_mod, "INLINE_CHECK_DRAFTS", {}).pop(cid, None)
                if not draft:
                    draft = await get_inline_check_draft(cid)
                if draft:
                    await create_check(uid=draft["user_id"], asset=draft["asset"], total=draft["amount"], limit=1, password=draft.get("password"), check_id=cid)
                    res = await activate_check(cid, msg.from_user.id, username=msg.from_user.username)
                    user_balances = await get_all_balances(msg.from_user.id)
                    try:
                        await update_user_chat_menu_button(msg.bot, msg.from_user.id, user_balances)
                    except Exception:
                        pass
                    user_kb = check_activated_user_kb(msg.from_user.id, user_balances)
                    await msg.answer(f"✅ <b>Вы успешно активировали чек на {res['per_activation']} {res['asset']}!</b>", reply_markup=user_kb, parse_mode="HTML")
                    new_text = f"✅ <b>Чек на {res['per_activation']} {res['asset']} активирован</b>"
                    disabled_kb = check_activated_kb()
                    await finalize_business_check(msg.bot, cid, new_text, disabled_kb)
                    await notify_check_creator(msg.bot, res, msg.from_user)
                    return
            except Exception as ex_recovery:
                log.warning("Recovery activation error: %s", ex_recovery)
            await msg.answer("❌ Чек не найден.")
        else:
            await msg.answer(f"❌ Ошибка: {e.code}")

@router.message(CheckFSM.waiting_activate_pass)
async def process_activate_pass(msg: Message, state: FSMContext):
    if msg.text and msg.text.startswith("/"):
        await state.clear()
        if msg.text.startswith("/start"):
            import main as main_mod
            await main_mod.cmd_start(msg, state)
            return
    data = await state.get_data()
    cid = data.get("cid")
    try:
        res = await activate_check(cid, msg.from_user.id, msg.text, username=msg.from_user.username)
        used = res["activations_used"] + 1
        limit = res["activations_limit"]

        user_balances = await get_all_balances(msg.from_user.id)
        try:
            await update_user_chat_menu_button(msg.bot, msg.from_user.id, user_balances)
        except Exception as ex_mb:
            log.warning("Could not update chat menu button: %s", ex_mb)

        user_kb = check_activated_user_kb(msg.from_user.id, user_balances)
        if limit > 1:
            await msg.answer(f"✅ <b>Вы успешно активировали мульти-чек ({used}/{limit}) на {res['per_activation']} {res['asset']}!</b>", reply_markup=user_kb, parse_mode="HTML")
        else:
            await msg.answer(f"✅ <b>Вы успешно активировали чек на {res['per_activation']} {res['asset']}!</b>", reply_markup=user_kb, parse_mode="HTML")
        
        if used >= limit:
            new_text = f"✅ <b>Чек на {res['per_activation']} {res['asset']} активирован</b>" if limit == 1 else f"✅ <b>Мульти-чек на {res['total_amount']} {res['asset']} полностью активирован ({limit}/{limit})</b>"
            disabled_kb = check_activated_kb()
            await finalize_business_check(msg.bot, cid, new_text, disabled_kb)
        await notify_check_creator(msg.bot, res, msg.from_user)

        await state.clear()
    except CheckError as e:
        if e.code == "bad_password":
            await msg.answer("❌ Неверный пароль. Чтобы активировать чек, введите пароль:")
        elif e.code == "own_check":
            await msg.answer("❌ Вы не можете активировать свой собственный чек.")
            await state.clear()
        elif e.code == "not_recipient":
            await msg.answer("❌ Этот чек предназначен для другого пользователя.")
            await state.clear()
        elif e.code == "exhausted":
            await msg.answer("❌ Этот чек уже активирован.")
            await state.clear()
        else:
            await msg.answer(f"❌ Ошибка: {e.code}")
            await state.clear()

@router.callback_query(F.data.startswith("check_"))
async def cb_check_actions(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    action, cid = parts[0], parts[1]
    bot_info = await cb.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=check_{cid}"
    if action == "check_share":
        await cb.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отправить", url=f"https://t.me/share/url?url={link}")],[InlineKeyboardButton(text="‹ Назад", callback_data=f"check_back:{cid}")]]))
        await cb.answer()
    elif action == "check_del":
        await cb.message.delete()
        await cb.answer("Чек удален.")
    else:
        await cb.answer()

@router.callback_query(F.data.in_(["menu:pay", "more:pay"]))
async def cb_crypto_pay(cb: CallbackQuery):
    text = (
        "🏝 Здесь вы можете интегрировать платёжную систему Crypto Pay в свои проекты. "
        "<a href=\"https://t.me/CryptoBotRU/60\">Подробнее ›</a>\n\n"
        "🛒 Принимайте и отправляйте оплату в криптовалюте с помощью нашего "
        "<a href=\"https://help.cr.bot/en/articles/10279948-crypto-pay-api\">API</a>. "
        "Попробовать пример интеграции можно в @CryptoPayTestBot."
    )
    kb = cryptopay_menu_kb()
    try: await cb.message.delete()
    except: pass
    
    video_path = os.path.join(BASE_DIR, "pay_video.mp4")
    photo_path = os.path.join(BASE_DIR, "pay_banner.jpg")
    
    if os.path.exists(video_path):
        await cb.message.answer_video(video=FSInputFile(video_path), caption=text, parse_mode="HTML", reply_markup=kb, show_caption_above_media=True, disable_web_page_preview=True)
    elif os.path.exists(photo_path):
        await cb.message.answer_photo(photo=FSInputFile(photo_path), caption=text, parse_mode="HTML", reply_markup=kb, show_caption_above_media=True, disable_web_page_preview=True)
    else:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    await cb.answer()