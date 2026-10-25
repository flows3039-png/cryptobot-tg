# nft_parser.py
import re
import csv
import io
import logging
import urllib.parse
import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from database import is_nft_gift_seen, mark_nft_gift_seen, db_conn

log = logging.getLogger("nft_parser")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Арендные пулы и смарт-контракты аренды
RENTAL_PREFIXES = ("EQDYScI1", "UQDYScI1")

COLLECTIONS_BY_TIER = {
    "low": [
        "chillflame", "lunarsnake", "bdaycandle", "icecream", "instantramen",
        "lolpop", "vicecream", "freshsocks", "tamagadget", "xmasstocking"
    ],
    "mid": [
        "magicpotion", "cozymittens", "cloverpin", "trappedheart", "jellybunny",
        "kissedfrog", "prettypoesy", "spookycat", "santahat", "bunnymuffin"
    ],
    "high": [
        "artisanbrick", "timelessbook", "signetring", "heroichelmet", "winterwreath",
        "algorithmcup", "sharpflame", "vintagecigar", "plushpepe"
    ]
}

ALL_COLLECTIONS = (
    COLLECTIONS_BY_TIER["low"] +
    COLLECTIONS_BY_TIER["mid"] +
    COLLECTIONS_BY_TIER["high"]
)

# Кэш минимальных цен (Floor Price) по коллекциям для вычисления дисконта
COLLECTION_FLOORS = {
    "chillflame": 5.0, "lunarsnake": 5.0, "bdaycandle": 6.0, "icecream": 5.0,
    "instantramen": 5.0, "lolpop": 5.0, "vicecream": 5.0, "freshsocks": 6.0,
    "tamagadget": 6.5, "xmasstocking": 7.0, "magicpotion": 18.0, "cozymittens": 16.0,
    "cloverpin": 19.0, "trappedheart": 22.0, "jellybunny": 24.0, "kissedfrog": 20.0,
    "prettypoesy": 17.5, "spookycat": 25.0, "santahat": 21.0, "bunnymuffin": 15.0,
    "artisanbrick": 85.0, "timelessbook": 90.0, "signetring": 75.0, "heroichelmet": 190.0,
    "winterwreath": 60.0, "algorithmcup": 88.0, "sharpflame": 110.0, "vintagecigar": 65.0,
    "plushpepe": 7000.0
}

def is_real_username(username: str | None) -> bool:
    """Проверяет, что перед нами реальный Telegram юзернейм, а не адрес кошелька или смарт-контракт."""
    if not username:
        return False
    u = username.strip()
    if not u.startswith("@"):
        u = "@" + u
    raw_name = u[1:]
    
    if raw_name.startswith(("EQ", "UQ", "0:")):
        return False
    if "..." in raw_name or len(raw_name) < 4 or len(raw_name) > 32:
        return False
    if raw_name.lower().startswith(("contract", "wallet", "fragment", "null", "none")):
        return False

    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9_]{3,31}$", raw_name))

def check_special_serial(serial_num: int) -> str | None:
    """Определяет коллекционную ценность номера подарка."""
    if serial_num <= 0:
        return None
    s = str(serial_num)
    if serial_num < 100:
        return f"Двузначный #{serial_num}"
    if serial_num < 1000:
        return f"Трёхзначный #{serial_num}"
    if len(set(s)) == 1:
        return f"Одинаковые цифры #{serial_num}"
    if s == s[::-1] and len(s) >= 3:
        return f"Зеркальный палиндром #{serial_num}"
    if serial_num % 1000 == 0 or (serial_num > 100 and serial_num % 100 == 0):
        return f"Круглое число #{serial_num}"
    return None

async def resolve_wallet_username(client: httpx.AsyncClient, wallet_addr: str) -> str | None:
    """Пытается определить настоящий Telegram-юзернейм владельца TON-кошелька."""
    if not wallet_addr:
        return None
    
    clean_addr = wallet_addr.strip()
    if clean_addr.startswith(RENTAL_PREFIXES):
        return None

    # 1. TON DNS (*.t.me или *.ton)
    try:
        r = await client.get(f"https://tonapi.io/v2/accounts/{clean_addr}/dns/backresolve", timeout=5)
        if r.status_code == 200:
            domains = r.json().get("domains", [])
            for dom in domains:
                if dom.endswith(".t.me"):
                    uname = dom[:-5]
                    cand = f"@{uname}"
                    if is_real_username(cand):
                        return cand
                elif dom.endswith(".ton"):
                    uname = dom[:-4]
                    cand = f"@{uname}"
                    if is_real_username(cand):
                        return cand
    except Exception as e:
        log.debug("DNS backresolve error: %s", e)

    # 2. Telegram Usernames NFT
    try:
        r2 = await client.get(
            f"https://tonapi.io/v2/accounts/{clean_addr}/nfts",
            params={"collection": "0:b774d95eb20543f186c06b371ab88ad704f7e256130caf96184b2316eb25d4fe", "limit": 3},
            timeout=5
        )
        if r2.status_code == 200:
            nft_items = r2.json().get("nft_items", [])
            for item in nft_items:
                raw_name = (item.get("metadata") or {}).get("name", "")
                if raw_name:
                    cand = f"@{raw_name.lstrip('@').strip()}"
                    if is_real_username(cand):
                        return cand
    except Exception as e:
        log.debug("Usernames NFT error: %s", e)

    # 3. TonAPI Account profile
    try:
        r3 = await client.get(f"https://tonapi.io/v2/accounts/{clean_addr}", timeout=5)
        if r3.status_code == 200:
            acc_data = r3.json()
            if acc_data.get("name"):
                cand = f"@{acc_data['name'].lstrip('@')}"
                if is_real_username(cand):
                    return cand
    except Exception as e:
        log.debug("Account profile error: %s", e)

    return None

async def get_holder_portfolio(client: httpx.AsyncClient, wallet_addr: str) -> dict:
    """Анализирует инвентарь владельца подарка: общее число NFT, кит или новичок."""
    if not wallet_addr or wallet_addr.startswith(RENTAL_PREFIXES):
        return {"total_nfts": 1, "tier": "Обычный юзер", "is_whale": False}
    try:
        r = await client.get(f"https://tonapi.io/v2/accounts/{wallet_addr}/nfts?limit=50", timeout=5)
        if r.status_code == 200:
            items = r.json().get("nft_items", [])
            count = len(items)
            if count >= 20:
                tier = "Крупный кит"
                is_whale = True
            elif count >= 5:
                tier = "Активный коллекционер"
                is_whale = False
            elif count == 1:
                tier = "Новичок (1 подарок)"
                is_whale = False
            else:
                tier = f"Владелец {count} NFT"
                is_whale = False
            return {"total_nfts": count, "tier": tier, "is_whale": is_whale}
    except Exception:
        pass
    return {"total_nfts": 1, "tier": "Обычный юзер", "is_whale": False}

async def parse_single_nft_gift(gift_input: str, skip_seen: bool = True) -> dict | None:
    """Парсит конкретный подарок по ссылке или слагу, отфильтровывая кошельки и арендованные контракты."""
    slug = gift_input.strip()
    if "/" in slug:
        m = re.search(r'/(?:nft|gift)/([a-zA-Z0-9\-]+)', slug)
        if m:
            slug = m.group(1)
        else:
            slug = slug.split("/")[-1].split("?")[0]
            
    slug = slug.strip().lstrip("#")
    if not slug:
        return None

    if skip_seen:
        try:
            if await is_nft_gift_seen(slug):
                log.info("Gift %s already seen, skipping", slug)
                return None
        except Exception as e:
            log.warning("is_nft_gift_seen error: %s", e)

    frag_url = f"https://fragment.com/gift/{slug}"
    tme_url = f"https://t.me/nft/{slug}"

    # Определение коллекции и серийного номера
    col_name = slug.split("-")[0].lower()
    serial_match = re.search(r'-(\d+)$', slug)
    serial_num = int(serial_match.group(1)) if serial_match else 0
    special_serial = check_special_serial(serial_num)

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            r = await client.get(frag_url, timeout=8)
        except Exception as e:
            log.warning("Failed to fetch %s: %s", frag_url, e)
            return None

        if r.status_code != 200 or not BeautifulSoup:
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        
        # 1. Парсим цену продажи
        price_val = 0.0
        for div in soup.select(".tm-section-box, .tm-table tr, .table tr"):
            t = div.get_text(" | ", strip=True)
            if "Sell Price" in t:
                m_p = re.search(r'Sell Price[^\d]*([\d,]+(?:\.\d+)?)', t)
                if m_p:
                    try:
                        price_val = float(m_p.group(1).replace(",", ""))
                        break
                    except Exception:
                        pass
            elif "Sale price" in t or "Price" in t:
                m_p = re.search(r'([\d,]+(?:\.\d+)?)', t)
                if m_p:
                    try:
                        price_val = float(m_p.group(1).replace(",", ""))
                    except Exception:
                        pass

        # 2. Парсим редкие атрибуты
        rare_traits = []
        for row in soup.select(".tm-section-box tr, .table tr"):
            t = row.get_text(" ", strip=True)
            m_pct = re.search(r'([\w\s]+)\s+(\d+(?:\.\d+)?)\s*%', t)
            if m_pct:
                trait_name = m_pct.group(1).strip()
                pct = float(m_pct.group(2))
                if pct <= 2.0:
                    rare_traits.append(f"{trait_name} ({pct}%)")

        # 3. Проверяем владельца
        wallet_addr = None
        owner_username = None

        for a in soup.find_all("a", href=True):
            h = a["href"]
            if "t.me/" in h and not any(k in h for k in ["t.me/nft", "wallet.t.me", "t.me/fragment"]):
                m_u = re.search(r't\.me/([a-zA-Z0-9_]{4,})', h)
                if m_u:
                    cand = f"@{m_u.group(1)}"
                    if is_real_username(cand):
                        owner_username = cand
                        break

        for tr in soup.find_all("tr"):
            if "Owner" in tr.get_text():
                a_wallet = tr.find("a", class_="tm-wallet") or tr.find("a", href=True)
                if a_wallet and a_wallet.get("href"):
                    href = a_wallet["href"]
                    m_addr = re.search(r'address/([a-zA-Z0-9_\-]+)', href)
                    if m_addr:
                        wallet_addr = m_addr.group(1)
                if not wallet_addr:
                    raw_t = tr.get_text(" ", strip=True).replace("Owner", "").strip()
                    wallet_addr = raw_t.replace(" ", "")
                break

        if wallet_addr and wallet_addr.startswith(RENTAL_PREFIXES):
            log.info("Gift %s has rental contract owner %s, skipping", slug, wallet_addr)
            return None

        if not owner_username and wallet_addr:
            owner_username = await resolve_wallet_username(client, wallet_addr)

        if not is_real_username(owner_username):
            log.info("Gift %s has no verified Telegram username, skipping", slug)
            return None

        # 4. Анализ арбитража и портфолио
        floor_price = COLLECTION_FLOORS.get(col_name, price_val)
        discount_pct = 0.0
        est_profit = 0.0
        if floor_price > price_val and price_val > 0:
            discount_pct = round(((floor_price - price_val) / floor_price) * 100, 1)
            est_profit = round((floor_price * 0.95) - price_val, 2)

        portfolio = await get_holder_portfolio(client, wallet_addr or "")

        # Заготовка сообщения в ЛС владельцу
        gift_title = slug.replace("-", " #").title()
        offer_price = max(1.0, round(price_val * 0.85, 1))
        outreach_text = f"Привет! Увидел твой {gift_title} на Fragment. Заберу прямо сейчас за {offer_price:g} TON чек/криптобот без комиссий. Актуально?"
        outreach_url = f"https://t.me/{owner_username.lstrip('@')}?text={urllib.parse.quote(outreach_text)}"

        try:
            await mark_nft_gift_seen(slug, price_val, owner_username)
        except Exception as e:
            log.warning("mark_nft_gift_seen error: %s", e)

        return {
            "slug": slug,
            "title": gift_title,
            "link": tme_url,
            "frag_link": frag_url,
            "price": price_val,
            "wallet": wallet_addr,
            "owner": owner_username,
            "serial": serial_num,
            "special_serial": special_serial,
            "rare_traits": rare_traits,
            "floor_price": floor_price,
            "discount_pct": discount_pct,
            "est_profit": est_profit,
            "portfolio": portfolio,
            "outreach_url": outreach_url
        }

async def search_gifts_by_range(min_ton: float, max_ton: float, limit: int = 3, rare_only: bool = False, serial_only: bool = False) -> list[dict]:
    """Ищет подарки на Fragment в заданном диапазоне с дополнительными фильтрами."""
    results = []
    seen_in_session = set()

    urls = []
    if min_ton <= 5:
        tier_cols = COLLECTIONS_BY_TIER["low"]
    elif min_ton < 40:
        tier_cols = COLLECTIONS_BY_TIER["mid"]
    else:
        tier_cols = COLLECTIONS_BY_TIER["high"]

    for col in tier_cols:
        urls.append(f"https://fragment.com/gifts/{col}?sort=price_asc&filter=sale")
        urls.append(f"https://fragment.com/gifts/{col}?sort=listed&filter=sale")

    urls.append("https://fragment.com/gifts?sort=listed&filter=sale")
    urls.append("https://fragment.com/gifts?sort=price_asc&filter=sale")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        for u in urls:
            if len(results) >= limit:
                break
            try:
                r = await client.get(u, timeout=7)
                if r.status_code != 200 or not BeautifulSoup:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.select("a[href*='/gift/']"):
                    if len(results) >= limit:
                        break
                    href = a.get("href", "")
                    m_slug = re.search(r'/gift/([a-zA-Z0-9\-]+)', href)
                    if not m_slug:
                        continue
                    slug = m_slug.group(1)
                    if slug in seen_in_session:
                        continue

                    if await is_nft_gift_seen(slug):
                        seen_in_session.add(slug)
                        continue

                    text = a.get_text(" ", strip=True)
                    m_price = re.search(r'([\d,]+(?:\.\d+)?)\s*(?:For sale|left)', text)
                    if not m_price:
                        m_price = re.search(r'([\d,]+(?:\.\d+)?)\s*TON', text, re.IGNORECASE)
                    if not m_price:
                        nums = re.findall(r'[\d,]+(?:\.\d+)?', text)
                        price_str = nums[-1] if nums else "0"
                    else:
                        price_str = m_price.group(1)

                    try:
                        price_val = float(price_str.replace(",", ""))
                    except Exception:
                        continue

                    if min_ton <= price_val <= max_ton:
                        seen_in_session.add(slug)
                        info = await parse_single_nft_gift(slug, skip_seen=True)
                        if info:
                            # Проверка фильтров редкости и красивого номера
                            if rare_only and not info["rare_traits"]:
                                continue
                            if serial_only and not info["special_serial"]:
                                continue

                            info["price"] = price_val if price_val > 0 else info["price"]
                            results.append(info)
            except Exception as e:
                log.warning("Range search error for %s: %s", u, e)
                continue

    return results

async def export_seen_gifts_csv() -> bytes:
    """Генерирует CSV-файл со всеми спарсенными подарками и владельцами."""
    async with db_conn.tx() as c:
        rows = await (await c.execute("SELECT slug, price, owner, created_at FROM seen_nft_gifts ORDER BY created_at DESC")).fetchall()
    
    out = io.StringIO()
    writer = csv.writer(out, delimiter=",")
    writer.writerow(["Slug", "Price TON", "Owner Username", "Telegram Link", "Fragment Link", "Timestamp"])
    for r in rows:
        slug = r["slug"]
        writer.writerow([
            slug,
            f"{r['price']:g}",
            r["owner"],
            f"https://t.me/nft/{slug}",
            f"https://fragment.com/gift/{slug}",
            r["created_at"]
        ])
    return out.getvalue().encode("utf-8-sig")
