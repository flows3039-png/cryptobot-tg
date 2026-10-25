# business.py
import re
import os
import logging
from aiogram import Router, Bot, F
from aiogram.types import (
    Message, BusinessConnection, InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile
)
from database import (
    save_business_connection, get_balance, create_check, update_check_message,
    update_check_business_conn, get_mid_prices
)
from config import CURRENCIES, EMOJI
from check_logger import log_check_error
from image_gen import fetch_check_image

log = logging.getLogger("check_image")

router = Router()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@router.business_connection()
async def on_business_connection(bc: BusinessConnection):
    await save_business_connection(bc.id, bc.user.id, bc.is_enabled)
    log.info("Business connection: %s for user %s, enabled=%s", bc.id, bc.user.id, bc.is_enabled)

@router.business_message(F.text.regexp(r"^/чек\s+(\d+(?:[.,]\d+)?)\s+([a-zA-Z]{2,10})$"))
async def business_check_cmd(msg: Message, bot: Bot):
    match = re.match(r"^/чек\s+(\d+(?:[.,]\d+)?)\s+([a-zA-Z]{2,10})$", msg.text or "")
    if not match:
        return
    try:
        amt = float(match.group(1).replace(",", "."))
    except ValueError:
        return
    ticker = match.group(2).upper()
    if ticker not in CURRENCIES:
        return

    # Удаляем команду /чек без шума в логах, если нет прав
    try:
        if msg.business_connection_id:
            await bot.delete_business_messages(
                business_connection_id=msg.business_connection_id,
                message_ids=[msg.message_id]
            )
        else:
            await msg.delete()
    except Exception:
        pass

    bal = await get_balance(msg.from_user.id, ticker)
    if amt > bal:
        try:
            await bot.send_message(
                chat_id=msg.chat.id, 
                text=f"❌ Недостаточно средств. Баланс: {bal:.4f} {ticker}", 
                business_connection_id=msg.business_connection_id
            )
        except Exception:
            pass
        return

    try:
        cid = await create_check(msg.from_user.id, ticker, amt)
    except Exception as e:
        log_check_error(e, f"business_check_cmd: ошибка create_check для {msg.from_user.id}")
        try:
            await bot.send_message(
                chat_id=msg.chat.id, 
                text=f"❌ Ошибка: {e}", 
                business_connection_id=msg.business_connection_id
            )
        except Exception:
            pass
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

    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=check_{cid}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Получить {amt:g} {ticker}", url=link)]
    ])

    sent_msg = None
    try:
        img_bytes = await fetch_check_image(ticker, f"{amt:g}", f"{amt * price_usd:.2f}", check_id=cid)
        photo = BufferedInputFile(img_bytes, filename=f"check_{cid}.png")
        sent_msg = await bot.send_photo(
            chat_id=msg.chat.id,
            photo=photo,
            caption=text,
            reply_markup=kb,
            parse_mode="HTML",
            business_connection_id=msg.business_connection_id
        )
    except Exception as e:
        log.warning("business_check_cmd: отправка фото не удалась (%s), отправка текстом", e)
        try:
            sent_msg = await bot.send_message(
                chat_id=msg.chat.id, 
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
                business_connection_id=msg.business_connection_id
            )
        except Exception as ex:
            log_check_error(ex, f"business_check_cmd: ошибка отправки в чат {msg.chat.id}")
            return

    if sent_msg:
        await update_check_message(cid, msg.chat.id, sent_msg.message_id)
        if msg.business_connection_id:
            await update_check_business_conn(cid, msg.business_connection_id)
