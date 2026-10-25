# nft_parser.py
import re
import logging
import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

log = logging.getLogger("nft_parser")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

POPULAR_COLLECTIONS = [
    "chillflame", "lunarsnake", "bdaycandle", "icecream", "instantramen",
    "lolpop", "vicecream", "freshsocks", "tamagadget", "xmasstocking",
    "magicpotion", "cozymittens", "cloverpin", "trappedheart", "plushpepe",
    "artisanbrick", "timelessbook", "signetring", "heroichelmet", "algorithmcup"
]

async def resolve_wallet_username(client: httpx.AsyncClient, wallet_addr: str) -> str:
    """Пытается определить Telegram-юзернейм владельца TON-кошелька через TonAPI DNS и NFT Usernames."""
    if not wallet_addr:
        return "Не определен"
    
    clean_addr = wallet_addr.strip()
    
    # 1. Проверяем TON DNS (backresolve domains like username.t.me)
    try:
        r = await client.get(f"https://tonapi.io/v2/accounts/{clean_addr}/dns/backresolve", timeout=5)
        if r.status_code == 200:
            domains = r.json().get("domains", [])
            for dom in domains:
                if dom.endswith(".t.me"):
                    uname = dom[:-5]
                    return f"@{uname}"
                elif dom.endswith(".ton"):
                    uname = dom[:-4]
                    return f"@{uname}"
    except Exception as e:
        log.debug("DNS backresolve error: %s", e)

    # 2. Проверяем наличие Telegram Usernames NFT на кошельке
    try:
        r2 = await client.get(
            f"https://tonapi.io/v2/accounts/{clean_addr}/nfts",
            params={"collection": "0:b774d95eb20543f186c06b371ab88ad704f7e256130caf96184b2316eb25d4fe", "limit": 5},
            timeout=5
        )
        if r2.status_code == 200:
            nft_items = r2.json().get("nft_items", [])
            for item in nft_items:
                raw_name = (item.get("metadata") or {}).get("name", "")
                if raw_name:
                    uname = raw_name.lstrip("@").strip()
                    return f"@{uname}"
    except Exception as e:
        log.debug("Usernames NFT error: %s", e)

    # 3. Проверяем Telegram-юзернейм или имя в профиле TonAPI
    try:
        r3 = await client.get(f"https://tonapi.io/v2/accounts/{clean_addr}", timeout=5)
        if r3.status_code == 200:
            acc_data = r3.json()
            if acc_data.get("name"):
                return f"@{acc_data['name'].lstrip('@')}"
    except Exception as e:
        log.debug("Account profile error: %s", e)

    # Фолбэк на короткий адрес кошелька, если публичный ник скрыт
    short_addr = f"{clean_addr[:4]}...{clean_addr[-4:]}"
    return f"@{short_addr}"

async def parse_single_nft_gift(gift_input: str) -> dict | None:
    """Парсит подарок по ссылке или слагу (t.me/nft/... или fragment.com/gift/...)."""
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

    frag_url = f"https://fragment.com/gift/{slug}"
    tme_url = f"https://t.me/nft/{slug}"

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            r = await client.get(frag_url, timeout=10)
        except Exception as e:
            log.warning("Failed to fetch %s: %s", frag_url, e)
            return None

        if r.status_code != 200:
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

        # 2. Парсим владельца
        wallet_addr = None
        for tr in soup.find_all("tr"):
            if "Owner" in tr.get_text():
                a_wallet = tr.find("a", class_="tm-wallet") or tr.find("a", href=True)
                if a_wallet and a_wallet.get("href"):
                    href = a_wallet["href"]
                    m_addr = re.search(r'address/([a-zA-Z0-9_\-]+)', href)
                    if m_addr:
                        wallet_addr = m_addr.group(1)
                if not wallet_addr:
                    # Текстовый адрес
                    raw_t = tr.get_text(" ", strip=True).replace("Owner", "").strip()
                    wallet_addr = raw_t.replace(" ", "")
                break

        owner_username = await resolve_wallet_username(client, wallet_addr or "")

        return {
            "slug": slug,
            "link": tme_url,
            "frag_link": frag_url,
            "price": price_val,
            "wallet": wallet_addr,
            "owner": owner_username
        }

async def search_gifts_by_range(min_ton: float, max_ton: float, limit: int = 5) -> list[dict]:
    """Ищет подарки на Fragment в заданном ценовом диапазоне."""
    results = []
    seen_slugs = set()

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        # Проверяем общий список отсортированный по цене
        urls = [
            "https://fragment.com/gifts?sort=price_asc&filter=sale",
            "https://fragment.com/gifts?sort=listed&filter=sale"
        ]
        
        # Если диапазон средний или высокий, добавляем тематические коллекции
        if min_ton >= 10:
            for col in POPULAR_COLLECTIONS:
                urls.append(f"https://fragment.com/gifts/{col}?sort=price_asc&filter=sale")

        for u in urls:
            if len(results) >= limit:
                break
            try:
                r = await client.get(u, timeout=8)
                if r.status_code != 200:
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
                    if slug in seen_slugs:
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
                        seen_slugs.add(slug)
                        # Парсим детальную информацию о владельце
                        info = await parse_single_nft_gift(slug)
                        if info:
                            info["price"] = price_val if price_val > 0 else info["price"]
                            results.append(info)
            except Exception as e:
                log.warning("Range search error for %s: %s", u, e)
                continue

    return results
