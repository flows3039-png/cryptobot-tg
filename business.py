# business.py
import re
import os
import asyncio
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

_bot_username = None
_prices_cache = {}
_prices_cache_time = 0

async def get_cached_bot_username(bot: Bot) -> str:
    global _bot_username
    if not _bot_username:
        try:
            me = await bot.get_me()
            _bot_username = me.username
        except Exception:
            return "CryptoBot"
    return _bot_username

async def get_cached_mid_prices() -> dict:
    global _prices_cache, _prices_cache_time
    import time
    now = time.time()
    if now - _prices_cache_time > 60 or not _prices_cache:
        try:
            _prices_cache = await get_mid_prices()
            _prices_cache_time = now
        except Exception:
            pass
    return _prices_cache

def fast_delete_message(bot: Bot, msg: Message):
    try:
        if msg.business_connection_id:
            asyncio.create_task(bot.delete_business_messages(
                business_connection_id=msg.business_connection_id,
                message_ids=[msg.message_id]
            ))
        else:
            asyncio.create_task(msg.delete())
    except Exception:
        pass

@router.business_connection()
async def on_business_connection(bc: BusinessConnection):
    await save_business_connection(bc.id, bc.user.id, bc.is_enabled)
    log.info("Business connection: %s for user %s, enabled=%s", bc.id, bc.user.id, bc.is_enabled)

@router.business_message(F.text.regexp(r"^/(?:ч|чек|c|check)(?:\s*|\s+.*)$", flags=re.IGNORECASE))
async def business_check_cmd(msg: Message, bot: Bot):
    # Моментальное фоновое удаление команды в первую миллисекунду
    fast_delete_message(bot, msg)

    text_raw = (msg.text or "").strip()
    match = re.match(r"^/(?:ч|чек|c|check)\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z]{2,10})(?:\s+(.+))?$", text_raw, flags=re.IGNORECASE)
    if not match:
        return

    amt_str = match.group(1)
    ticker_str = match.group(2)
    password = match.group(3).strip() if match.group(3) else None
    if not amt_str or not ticker_str:
        return

    try:
        amt = float(amt_str.replace(",", "."))
    except ValueError:
        return
    ticker = ticker_str.upper()
    if ticker not in CURRENCIES:
        return

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
        cid = await create_check(msg.from_user.id, ticker, amt, password=password)
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

    prices = await get_cached_mid_prices()
    price_usd = prices.get(ticker, 0) or CURRENCIES.get(ticker, {}).get("price_usd", 0)

    fiat_str = f"${amt * price_usd:.2f}"
    check_icon = '<tg-emoji emoji-id="5311998535032409760">🧾</tg-emoji>'
    usdt_icon = '<tg-emoji emoji-id="6035288280562404083">🪙</tg-emoji>' if ticker == "USDT" else ""
    text = f"{check_icon} Чек на {usdt_icon} {amt:g} {ticker} ({fiat_str})."

    bot_username = await get_cached_bot_username(bot)
    link = f"https://t.me/{bot_username}?start=check_{cid}"
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
