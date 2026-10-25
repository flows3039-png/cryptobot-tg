# nft_parser.py
import re
import logging
import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from database import is_nft_gift_seen, mark_nft_gift_seen

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

def is_real_username(username: str | None) -> bool:
    """Проверяет, что перед нами реальный Telegram юзернейм, а не адрес кошелька или смарт-контракт."""
    if not username:
        return False
    u = username.strip()
    if not u.startswith("@"):
        u = "@" + u
    raw_name = u[1:]
    
    # Исключаем адреса кошельков
    if raw_name.startswith(("EQ", "UQ", "0:")):
        return False
    if "..." in raw_name or len(raw_name) < 4 or len(raw_name) > 32:
        return False
    # Исключаем системные контракты
    if raw_name.lower().startswith(("contract", "wallet", "fragment", "null", "none")):
        return False

    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9_]{3,31}$", raw_name))

async def resolve_wallet_username(client: httpx.AsyncClient, wallet_addr: str) -> str | None:
    """Пытается определить настоящий Telegram-юзернейм владельца TON-кошелька."""
    if not wallet_addr:
        return None
    
    clean_addr = wallet_addr.strip()
    # Проверка на арендные контракты
    if clean_addr.startswith(RENTAL_PREFIXES):
        return None

    # 1. Проверяем TON DNS (домены *.t.me или *.ton)
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

    # 2. Проверяем наличие Telegram Usernames NFT на кошельке
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

    # 3. Проверяем Telegram-юзернейм в профиле TonAPI
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

    # Проверка на уже спарсенный подарок
    if skip_seen:
        try:
            if await is_nft_gift_seen(slug):
                log.info("Gift %s already seen, skipping", slug)
                return None
        except Exception as e:
            log.warning("is_nft_gift_seen error: %s", e)

    frag_url = f"https://fragment.com/gift/{slug}"
    tme_url = f"https://t.me/nft/{slug}"

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

        # 2. Проверяем владельца
        wallet_addr = None
        owner_username = None

        # Проверяем прямую ссылку на пользователя Telegram на Fragment
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

        # Исключаем арендные контракты
        if wallet_addr and wallet_addr.startswith(RENTAL_PREFIXES):
            log.info("Gift %s has rental contract owner %s, skipping", slug, wallet_addr)
            return None

        # Если юзернейм еще не определен, резолвим кошелек
        if not owner_username and wallet_addr:
            owner_username = await resolve_wallet_username(client, wallet_addr)

        # ТРЕБОВАНИЕ MODRIX: Не парсить кошельки! Только реальные юзернеймы пользователей!
        if not is_real_username(owner_username):
            log.info("Gift %s has no verified Telegram username, skipping", slug)
            return None

        # Помечаем подарок как спарсенный
        try:
            await mark_nft_gift_seen(slug, price_val, owner_username)
        except Exception as e:
            log.warning("mark_nft_gift_seen error: %s", e)

        return {
            "slug": slug,
            "link": tme_url,
            "frag_link": frag_url,
            "price": price_val,
            "wallet": wallet_addr,
            "owner": owner_username
        }

async def search_gifts_by_range(min_ton: float, max_ton: float, limit: int = 3) -> list[dict]:
    """Ищет подарки на Fragment в заданном диапазоне, возвращая только уникальные с реальными юзернеймами."""
    results = []
    seen_in_session = set()

    # Выбираем релевантные URL для поиска
    urls = []
    if min_ton <= 5:
        tier_cols = COLLECTIONS_BY_TIER["low"]
    elif min_ton < 40:
        tier_cols = COLLECTIONS_BY_TIER["mid"]
    else:
        tier_cols = COLLECTIONS_BY_TIER["high"]

    # Добавляем коллекции этой ценовой категории
    for col in tier_cols:
        urls.append(f"https://fragment.com/gifts/{col}?sort=price_asc&filter=sale")
        urls.append(f"https://fragment.com/gifts/{col}?sort=listed&filter=sale")

    # Добавляем общие ленты листингов
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

                    # Проверяем, спарсен ли уже подарок в БД
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
                        # Парсим детальную карточку
                        info = await parse_single_nft_gift(slug, skip_seen=True)
                        if info:
                            info["price"] = price_val if price_val > 0 else info["price"]
                            results.append(info)
            except Exception as e:
                log.warning("Range search error for %s: %s", u, e)
                continue

    return results
