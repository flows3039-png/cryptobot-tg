# limits.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

# --- ГЛАВНОЕ МЕНЮ ЛИМИТОВ ---
@router.callback_query(F.data == "set:limits")
async def cb_limits_menu(cb: CallbackQuery):
    text = "Выберите раздел, чтобы посмотреть комиссии и лимиты."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👜 Кошелёк", callback_data="limit:wallet")],
        [InlineKeyboardButton(text="🐬 Биржа", callback_data="limit:exchange")],
        [InlineKeyboardButton(text="🍰 Crypto Pay", callback_data="limit:pay")],
        [InlineKeyboardButton(text="💠 P2P", callback_data="limit:p2p")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="menu:settings")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# ==================== КОШЕЛЁК ====================
@router.callback_query(F.data == "limit:wallet")
async def cb_limit_wallet(cb: CallbackQuery):
    text = "Выберите криптовалюту."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tether - USDT (TON, TRC20, SPL, ERC20, BEP20)", callback_data="limit:usdt")],
        [InlineKeyboardButton(text="Gram - TON (TON)", callback_data="limit:ton")],
        [InlineKeyboardButton(text="Solana - SOL (SPL)", callback_data="limit:sol")],
        [InlineKeyboardButton(text="TRON - TRX (TRC20)", callback_data="limit:trx")],
        [InlineKeyboardButton(text="Bitcoin - BTC (BTC)", callback_data="limit:btc")],
        [InlineKeyboardButton(text="Ethereum - ETH (ERC20)", callback_data="limit:eth")],
        [InlineKeyboardButton(text="Dogecoin - DOGE (DOGE)", callback_data="limit:doge")],
        [InlineKeyboardButton(text="Litecoin - LTC (LTC)", callback_data="limit:ltc")],
        [InlineKeyboardButton(text="Binance Coin - BNB (BEP20)", callback_data="limit:bnb")],
        [InlineKeyboardButton(text="USD Coin - USDC (ERC20, SPL, BEP20)", callback_data="limit:usdc")],
        [InlineKeyboardButton(text="Tether Gold - XAUT (ERC20)", callback_data="limit:xaut")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="set:limits")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- USDT (Выбор сети) ---
@router.callback_query(F.data == "limit:usdt")
async def cb_limit_usdt(cb: CallbackQuery):
    text = "Выберите сеть для USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="TON (TON)", callback_data="limit:usdt_ton")],
        [InlineKeyboardButton(text="Tron (TRC20)", callback_data="limit:usdt_trc20")],
        [InlineKeyboardButton(text="Solana (SPL)", callback_data="limit:usdt_spl")],
        [InlineKeyboardButton(text="Ethereum (ERC20)", callback_data="limit:usdt_erc20")],
        [InlineKeyboardButton(text="BNB Smart Chain (BEP20)", callback_data="limit:usdt_bep20")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="limit:wallet")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:usdt_ton")
async def cb_usdt_ton(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты USDT в сети TON – TON.\n\nКомиссия на вывод: 3.5 USDT\n\nЛимиты:\nПополнение: от 1 USDT\nВывод: от 1 USDT"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:usdt")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:usdt_trc20")
async def cb_usdt_trc20(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты USDT в сети Tron – TRC20.\n\nКомиссия на вывод на адреса с USDT: 5.5 USDT\nКомиссия на вывод на адреса без USDT: 8.5 USDT\n\nЛимиты:\nПополнение: от 1 USDT\nВывод: от 1 USDT"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:usdt")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:usdt_spl")
async def cb_usdt_spl(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты USDT в сети Solana – SPL.\n\nКомиссия на вывод: 3 USDT\n\nЛимиты:\nПополнение: от 1 USDT\nВывод: от 1 USDT"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:usdt")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:usdt_erc20")
async def cb_usdt_erc20(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты USDT в сети Ethereum – ERC20.\n\nКомиссия на вывод: 5 USDT\n\nЛимиты:\nПополнение: от 1 USDT\nВывод: от 0.01 USDT"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:usdt")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:usdt_bep20")
async def cb_usdt_bep20(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты USDT в сети BNB Smart Chain – BEP20.\n\nКомиссия на вывод: 3 USDT\n\nЛимиты:\nПополнение: от 1 USDT\nВывод: от 1 USDT"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:usdt")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- Другие монеты Кошелька ---
@router.callback_query(F.data == "limit:ton")
async def cb_ton(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты GRAM в сети TON – TON.\n\nКомиссия на вывод: 0.1 GRAM\n\nЛимиты:\nПополнение: от 0.1 GRAM\nВывод: от 0.0005 GRAM"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:wallet")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:sol")
async def cb_sol(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты SOL в сети Solana – SPL.\n\nКомиссия на вывод: 0.024 SOL\n\nЛимиты:\nПополнение: от 0.005 SOL\nВывод: от 0.005 SOL"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:wallet")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:trx")
async def cb_trx(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты TRX в сети TRON – TRC20.\n\nКомиссия на вывод: 15 TRX\n\nЛимиты:\nПополнение: от 10 TRX\nВывод: от 5 TRX"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:wallet")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:btc")
async def cb_btc(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты BTC в сети Bitcoin – BTC.\n\nКомиссия на вывод: 0.0003 BTC\n\nЛимиты:\nПополнение: от 0.00002 BTC\nВывод: от 0.001 BTC до 10 BTC"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:wallet")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:eth")
async def cb_eth(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты ETH в сети Ethereum – ERC20.\n\nКомиссия на вывод: 0.003 ETH\n\nЛимиты:\nПополнение: от 0.00007 ETH\nВывод: от 0.001 ETH"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:wallet")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:doge")
async def cb_doge(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты DOGE в сети DOGE – DOGE.\n\nКомиссия на вывод: 15 DOGE\n\nЛимиты:\nПополнение: от 5 DOGE\nВывод: от 1 DOGE до 1,000,000 DOGE"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:wallet")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:ltc")
async def cb_ltc(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты LTC в сети Litecoin – LTC.\n\nКомиссия на вывод: 0.015 LTC\n\nЛимиты:\nПополнение: от 0.0001 LTC\nВывод: от 0.01 LTC до 3,000 LTC"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:wallet")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:bnb")
async def cb_bnb(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты BNB в сети BNB Smart Chain – BEP20.\n\nКомиссия на вывод: 0.006 BNB\n\nЛимиты:\nПополнение: от 0.0002 BNB\nВывод: от 0.001 BNB"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:wallet")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# --- USDC (Выбор сети) ---
@router.callback_query(F.data == "limit:usdc")
async def cb_limit_usdc(cb: CallbackQuery):
    text = "Выберите сеть для USDC."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ethereum (ERC20)", callback_data="limit:usdc_erc20")],
        [InlineKeyboardButton(text="Solana (SPL)", callback_data="limit:usdc_spl")],
        [InlineKeyboardButton(text="BNB Smart Chain (BEP20)", callback_data="limit:usdc_bep20")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="limit:wallet")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:usdc_erc20")
async def cb_usdc_erc20(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты USDC в сети Ethereum – ERC20.\n\nКомиссия на вывод: 5 USDC\n\nЛимиты:\nПополнение: от 1 USDC\nВывод: от 0.01 USDC"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:usdc")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:usdc_spl")
async def cb_usdc_spl(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты USDC в сети Solana – SPL.\n\nКомиссия на вывод: 3 USDC\n\nЛимиты:\nПополнение: от 1 USDC\nВывод: от 1 USDC"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:usdc")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:usdc_bep20")
async def cb_usdc_bep20(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты USDC в сети BNB Smart Chain – BEP20.\n\nКомиссия на вывод: 5 USDC\n\nЛимиты:\nПополнение: от 1 USDC\nВывод: от 0.01 USDC"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:usdc")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:xaut")
async def cb_xaut(cb: CallbackQuery):
    text = "Просмотр комиссий и лимитов для монеты XAUT в сети Ethereum – ERC20.\n\nКомиссия на вывод: 0.002 XAUT\n\nЛимиты:\nПополнение: от 0.001 XAUT\nВывод: от 0.001 XAUT"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:wallet")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# ==================== БИРЖА (ОБМЕН) ====================
@router.callback_query(F.data == "limit:exchange")
async def cb_limit_exchange(cb: CallbackQuery):
    text = "Выберите пару для просмотра комиссий и лимитов."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="TON/USDT", callback_data="limit:pair_ton")],
        [InlineKeyboardButton(text="SOL/USDT", callback_data="limit:pair_sol")],
        [InlineKeyboardButton(text="DOGE/USDT", callback_data="limit:pair_doge")],
        [InlineKeyboardButton(text="BTC/USDT", callback_data="limit:pair_btc")],
        [InlineKeyboardButton(text="ETH/USDT", callback_data="limit:pair_eth")],
        [InlineKeyboardButton(text="LTC/USDT", callback_data="limit:pair_ltc")],
        [InlineKeyboardButton(text="BNB/USDT", callback_data="limit:pair_bnb")],
        [InlineKeyboardButton(text="TRX/USDT", callback_data="limit:pair_trx")],
        [InlineKeyboardButton(text="USDC/USDT", callback_data="limit:pair_usdc")],
        [InlineKeyboardButton(text="XAUT/USDT", callback_data="limit:pair_xaut")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="set:limits")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:pair_ton")
async def cb_pair_ton(cb: CallbackQuery):
    text = "Комиссии и лимиты для пары TON/USDT.\n\nДля мейкеров: 0.5%\nДля тейкеров: 0.75%\n\nЛимиты обмена от 1 USDT до 100,000 USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:exchange")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:pair_sol")
async def cb_pair_sol(cb: CallbackQuery):
    text = "Комиссии и лимиты для пары SOL/USDT.\n\nДля мейкеров: 0.5%\nДля тейкеров: 0.75%\n\nЛимиты обмена от 0.001 USDT до 10,000 USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:exchange")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:pair_doge")
async def cb_pair_doge(cb: CallbackQuery):
    text = "Комиссии и лимиты для пары DOGE/USDT.\n\nДля мейкеров: 0.5%\nДля тейкеров: 0.75%\n\nЛимиты обмена от 1.2 USDT до 100,000 USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:exchange")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:pair_btc")
async def cb_pair_btc(cb: CallbackQuery):
    text = "Комиссии и лимиты для пары BTC/USDT.\n\nДля мейкеров: 0.5%\nДля тейкеров: 0.75%\n\nЛимиты обмена от 1 USDT до 100,000 USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:exchange")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:pair_eth")
async def cb_pair_eth(cb: CallbackQuery):
    text = "Комиссии и лимиты для пары ETH/USDT.\n\nДля мейкеров: 0.5%\nДля тейкеров: 0.75%\n\nЛимиты обмена от 1 USDT до 1,000,000 USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:exchange")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:pair_ltc")
async def cb_pair_ltc(cb: CallbackQuery):
    text = "Комиссии и лимиты для пары LTC/USDT.\n\nДля мейкеров: 0.5%\nДля тейкеров: 0.75%\n\nЛимиты обмена от 1 USDT до 100,000 USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:exchange")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:pair_bnb")
async def cb_pair_bnb(cb: CallbackQuery):
    text = "Комиссии и лимиты для пары BNB/USDT.\n\nДля мейкеров: 0.5%\nДля тейкеров: 0.75%\n\nЛимиты обмена от 1 USDT до 100,000 USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:exchange")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:pair_trx")
async def cb_pair_trx(cb: CallbackQuery):
    text = "Комиссии и лимиты для пары TRX/USDT.\n\nДля мейкеров: 0.5%\nДля тейкеров: 0.75%\n\nЛимиты обмена от 1 USDT до 1,350,000 USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:exchange")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:pair_usdc")
async def cb_pair_usdc(cb: CallbackQuery):
    text = "Комиссии и лимиты для пары USDC/USDT.\n\nДля мейкеров: 0.5%\nДля тейкеров: 0.75%\n\nЛимиты обмена от 1 USDT до 1,000,000 USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:exchange")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:pair_xaut")
async def cb_pair_xaut(cb: CallbackQuery):
    text = "Комиссии и лимиты для пары XAUT/USDT.\n\nДля мейкеров: 0.5%\nДля тейкеров: 0.75%\n\nЛимиты обмена от 1 USDT до 100,000 USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:exchange")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# ==================== CRYPTO PAY ====================
@router.callback_query(F.data == "limit:pay")
async def cb_limit_pay(cb: CallbackQuery):
    text = ("Комиссия зависит от оборота приложения за последние 30 дней.\n\n"
            "От 0 USD – 3%\n"
            "От 10,000 USD – 2.9%\n"
            "От 25,000 USD – 2.8%\n"
            "От 50,000 USD – 2.7%\n"
            "От 75,000 USD – 2.6%\n"
            "От 100,000 USD – 2.5%")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="set:limits")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# ==================== P2P ====================
@router.callback_query(F.data == "limit:p2p")
async def cb_limit_p2p(cb: CallbackQuery):
    text = "Выберите криптовалюту для просмотра комиссии и лимитов."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tether (USDT)", callback_data="limit:p2p_usdt")],
        [InlineKeyboardButton(text="Gram (GRAM)", callback_data="limit:p2p_gram")],
        [InlineKeyboardButton(text="Solana (SOL)", callback_data="limit:p2p_sol")],
        [InlineKeyboardButton(text="TRON (TRX)", callback_data="limit:p2p_trx")],
        [InlineKeyboardButton(text="Bitcoin (BTC)", callback_data="limit:p2p_btc")],
        [InlineKeyboardButton(text="Ethereum (ETH)", callback_data="limit:p2p_eth")],
        [InlineKeyboardButton(text="Dogecoin (DOGE)", callback_data="limit:p2p_doge")],
        [InlineKeyboardButton(text="Litecoin (LTC)", callback_data="limit:p2p_ltc")],
        [InlineKeyboardButton(text="Binance Coin (BNB)", callback_data="limit:p2p_bnb")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="set:limits")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:p2p_usdt")
async def cb_p2p_usdt(cb: CallbackQuery):
    text = "Комиссия и лимиты для монеты Tether (USDT).\n\nНа покупку: 0%\nНа продажу: 1%\n\nОбъём объявления: от 1 USDT до 100,000 USDT."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:p2p")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:p2p_gram")
async def cb_p2p_gram(cb: CallbackQuery):
    text = "Комиссия и лимиты для монеты Gram (GRAM).\n\nНа покупку: 0%\nНа продажу: 1%\n\nОбъём объявления: от 0.2 GRAM до 50,000 GRAM."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:p2p")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:p2p_sol")
async def cb_p2p_sol(cb: CallbackQuery):
    text = "Комиссия и лимиты для монеты Solana (SOL).\n\nНа покупку: 0%\nНа продажу: 1%\n\nОбъём объявления: от 0.007 SOL до 650 SOL."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:p2p")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:p2p_trx")
async def cb_p2p_trx(cb: CallbackQuery):
    text = "Комиссия и лимиты для монеты TRON (TRX).\n\nНа покупку: 0%\nНа продажу: 1%\n\nОбъём объявления: от 35 TRX до 1,250,000 TRX."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:p2p")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:p2p_btc")
async def cb_p2p_btc(cb: CallbackQuery):
    text = "Комиссия и лимиты для монеты Bitcoin (BTC).\n\nНа покупку: 0%\nНа продажу: 1%\n\nОбъём объявления: от 0.0001 BTC до 25 BTC."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:p2p")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:p2p_eth")
async def cb_p2p_eth(cb: CallbackQuery):
    text = "Комиссия и лимиты для монеты Ethereum (ETH).\n\nНа покупку: 0%\nНа продажу: 1%\n\nОбъём объявления: от 0.0003 ETH до 30 ETH."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:p2p")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:p2p_doge")
async def cb_p2p_doge(cb: CallbackQuery):
    text = "Комиссия и лимиты для монеты Dogecoin (DOGE).\n\nНа покупку: 0%\nНа продажу: 1%\n\nОбъём объявления: от 10 DOGE до 920,000 DOGE."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:p2p")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:p2p_ltc")
async def cb_p2p_ltc(cb: CallbackQuery):
    text = "Комиссия и лимиты для монеты Litecoin (LTC).\n\nНа покупку: 0%\nНа продажу: 1%\n\nОбъём объявления: от 0.02 LTC до 1,550 LTC."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:p2p")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "limit:p2p_bnb")
async def cb_p2p_bnb(cb: CallbackQuery):
    text = "Комиссия и лимиты для монеты Binance Coin (BNB).\n\nНа покупку: 0%\nНа продажу: 1%\n\nОбъём объявления: от 0.01 BNB до 450 BNB."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="limit:p2p")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()