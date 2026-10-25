# exchange.py
import httpx
import json
import urllib.parse
from aiogram import Router, F
from aiogram.types import CallbackQuery, URLInputFile
from keyboards import exchange_menu_kb, exchange_back_kb

router = Router()

COINS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "TON": "the-open-network",
    "SOL": "solana"
}

@router.callback_query(F.data == "menu:exchange")
async def cb_exchange_menu(cb: CallbackQuery):
    text = (
        "📈 <b>Биржа</b>\n\n"
        "Здесь вы можете посмотреть графики и цены популярных криптовалют.\n"
        "Выберите монету, чтобы увидеть её график за последние 24 часа."
    )
    kb = exchange_menu_kb()
    try: await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except: await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("exch:"))
async def cb_exchange_chart(cb: CallbackQuery):
    ticker = cb.data.split(":")[1]
    coin_id = COINS.get(ticker, "bitcoin")
    
    await cb.answer("Загружаю график...")
    
    try:
        async with httpx.AsyncClient() as client:
            # Получаем текущую цену и изменение
            r = await client.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true", timeout=10)
            data = r.json()[coin_id]
            price = data["usd"]
            change_24h = data.get("usd_24h_change", 0)
            
            if change_24h > 0:
                arrow = "🟢 📈"
                color = "#00FF00"
                sign = "+"
            else:
                arrow = "🔴 📉"
                color = "#FF0000"
                sign = ""
                
            # Получаем историю цен (7 дней)
            r_hist = await client.get(f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=7", timeout=10)
            hist = r_hist.json()
            prices = [p[1] for p in hist["prices"]]
            
            # Прореживаем данные для графика
            step = max(1, len(prices) // 30)
            chart_data = prices[::step]
            
            # Конфиг графика для QuickChart
            chart_config = {
                "type": "line",
                "data": {
                    "labels": [str(i) for i in range(len(chart_data))],
                    "datasets": [{
                        "label": f"{ticker} (USD)",
                        "data": chart_data,
                        "borderColor": color,
                        "backgroundColor": "rgba(0,0,0,0)",
                        "fill": False,
                        "pointRadius": 0,
                        "borderWidth": 2
                    }]
                },
                "options": {
                    "title": {"display": True, "text": f"{ticker} - ${price:,.2f}", "fontColor": "#FFFFFF"},
                    "legend": {"display": False},
                    "scales": {
                        "xAxes": [{"gridLines": {"color": "#333"}}],
                        "yAxes": [{"gridLines": {"color": "#333"}}]
                    }
                }
            }
            
            chart_json = urllib.parse.quote(json.dumps(chart_config))
            chart_url = f"https://quickchart.io/chart?c={chart_json}&w=600&h=300&bkg=%231E1E2E"
            
            photo = URLInputFile(chart_url)
            
            text = (
                f"{arrow} <b>{ticker}</b>\n\n"
                f"💰 <b>Цена:</b> ${price:,.2f}\n"
                f"📊 <b>Изменение за 24ч:</b> <b>{sign}{change_24h:.2f}%</b>"
            )
            
            kb = exchange_back_kb()
            
            await cb.message.answer_photo(photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")
            await cb.message.delete()
            
    except Exception as e:
        await cb.message.answer(f"❌ Ошибка загрузки графика: {e}", reply_markup=exchange_back_kb())