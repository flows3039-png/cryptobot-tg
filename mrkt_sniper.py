import asyncio
import aiohttp
import time
import json
import logging
import os
import sys
import winsound

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("MRKT-SNIPER")

# ========================================================
# НАСТРОЙКИ СНАЙПЕРА (MRKT GIFTS SNIPER)
# ========================================================

# Максимальная цена покупки в TON (с учетом текущего баланса 3.62 TON)
MAX_PRICE_TON = 3.60

# Режим реальной покупки:
# True  = РЕАЛЬНО отправляет запрос на покупку и тратит TON с баланса
# False = Тестовый режим (только мониторит и пишет в консоль, что нашел)
LIVE_BUY_MODE = True

# Интервал проверки рынка в секундах (0.4 сек = 400 мс для высокой скорости)
POLL_INTERVAL_SEC = 0.45

# Авторизация из сессии MRKT
ACCESS_TOKEN = "f63be9e2-bf98-4e54-b9eb-ef7ffa3ba054"
STEAM_ID = "76561198664065587"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 YaBrowser/26.8.0.0 Safari/537.36",
    "Origin": "https://cdn.tgmrkt.io",
    "Referer": "https://cdn.tgmrkt.io/",
    "Cookie": f"access_token={ACCESS_TOKEN}; steamid={STEAM_ID}",
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*"
}

API_BASE = "https://api.tgmrkt.io/api/v1"

# ========================================================

async def execute_buy(session: aiohttp.ClientSession, gift: dict):
    gift_id = gift.get("id")
    raw_price = gift.get("salePrice")
    ton_price = raw_price / 1e9 if raw_price > 1e6 else raw_price
    title = gift.get("title") or gift.get("name") or "NFT Gift"
    num = gift.get("num")

    display_name = f"{title} #{num}" if num else title
    log.info(f"===> ЦЕЛЬ ОБНАРУЖЕНА: {display_name} за {ton_price:.2f} TON! Запуск выкупа...")

    if not LIVE_BUY_MODE:
        log.info(f"[ТЕСТОВЫЙ РЕЖИМ] Выкуп пропущен (LIVE_BUY_MODE=False).")
        try:
            winsound.Beep(1000, 300)
        except Exception:
            pass
        return

    buy_payload = {
        "ids": [gift_id],
        "prices": {
            str(gift_id): raw_price
        }
    }

    t0 = time.perf_counter()
    try:
        async with session.post(f"{API_BASE}/gifts/buy", json=buy_payload, headers=HEADERS, timeout=4.0) as resp:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if resp.status in (200, 201):
                res_data = await resp.json()
                log.info(f"[УСПЕХ] ВЫКУПЛЕНО: {display_name} за {ton_price:.2f} TON! Время отклика: {elapsed_ms} мс!")
                try:
                    winsound.Beep(1500, 600)
                    winsound.Beep(2000, 600)
                except Exception:
                    pass
            else:
                err_text = await resp.text()
                log.warning(f"[ОШИБКА ВЫКУПА] Статус {resp.status} ({elapsed_ms} мс): {err_text[:200]}")
    except Exception as e:
        log.error(f"[СБОЙ СЕТИ] Ошибка при отправке выкупа: {e}")

async def check_balance(session: aiohttp.ClientSession):
    try:
        async with session.get(f"{API_BASE}/balance", headers=HEADERS, timeout=3.0) as resp:
            if resp.status == 200:
                data = await resp.json()
                hard = data.get("hard", 0)
                ton_bal = hard / 1e9
                return ton_bal
    except Exception:
        pass
    return None

async def run_sniper():
    print("=" * 65)
    print("       MRKT TELEGRAM GIFTS SNIPER (MODRIX EDITION)       ")
    print("=" * 65)
    print(f" [i] Макс. цена выкупа: {MAX_PRICE_TON} TON")
    print(f" [i] Режим автопокупки: {'АКТИВЕН (РЕАЛЬНЫЙ ВЫКУП)' if LIVE_BUY_MODE else 'ТЕСТ (ТОЛЬКО МОНИТОРИНГ)'}")
    print(f" [i] Частота сканирования: каждые {POLL_INTERVAL_SEC} сек")
    print("=" * 65)

    max_nano = int(MAX_PRICE_TON * 1e9)
    seen_ids = set()
    scan_count = 0

    conn = aiohttp.TCPConnector(limit=20, keepalive_timeout=60)
    async with aiohttp.ClientSession(connector=conn) as session:
        bal = await check_balance(session)
        if bal is not None:
            log.info(f"Баланс в MRKT: {bal:.4f} TON")
        else:
            log.warning("Не удалось получить баланс. Проверьте токен.")

        # Основной payload запроса к рынку
        payload = {
            "count": 15,
            "cursor": "",
            "collectionNames": [],
            "modelNames": [],
            "backdropNames": [],
            "symbolNames": [],
            "ordering": 2,       # Сортировка по цене
            "lowToHigh": True,   # Сначала самые дешевые
            "maxPrice": max_nano # Фильтр: только подарки до лимита
        }

        log.info("Снайпер перешел в боевой режим ожидания миспрайсов...")

        while True:
            scan_count += 1
            t_start = time.perf_counter()
            try:
                async with session.post(f"{API_BASE}/gifts/saling", json=payload, headers=HEADERS, timeout=3.5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        gifts = data.get("gifts", [])
                        
                        if gifts:
                            for gift in gifts:
                                gid = gift.get("id")
                                if gid in seen_ids:
                                    continue
                                seen_ids.add(gid)

                                price_nano = gift.get("salePrice", 0)
                                if price_nano <= max_nano:
                                    # Мгновенно запускаем таску на выкуп параллельно
                                    asyncio.create_task(execute_buy(session, gift))
                        else:
                            if scan_count % 30 == 0:
                                log.info(f"[Сканирование #{scan_count}] Лотов дешевле {MAX_PRICE_TON} TON пока нет. Мониторинг активен...")
                    elif resp.status == 401:
                        log.error("[401 Unauthorized] Сессия устарела. Требуется обновить access_token.")
                        await asyncio.sleep(5)
                    else:
                        log.warning(f"MRKT API вернул код {resp.status}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning(f"Ошибка запроса: {e}")

            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.05, POLL_INTERVAL_SEC - elapsed)
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    try:
        asyncio.run(run_sniper())
    except KeyboardInterrupt:
        print("\nСнайпер остановлен пользователем.")
