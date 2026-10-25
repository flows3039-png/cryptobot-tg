# database.py
import aiosqlite
import asyncio
import time
import hashlib
import hmac
import secrets
import logging
import httpx
import random

DB_PATH = "cryptobot.db"
log = logging.getLogger(__name__)

class DB:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path, isolation_level=None)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self.conn.execute("PRAGMA busy_timeout=5000")

    def tx(self):
        return _Tx(self)

class _Tx:
    def __init__(self, db):
        self.db = db
    async def __aenter__(self):
        await self.db._lock.acquire()
        await self.db.conn.execute("BEGIN IMMEDIATE")
        return self.db.conn
    async def __aexit__(self, et, ev, tb):
        try:
            await self.db.conn.execute("ROLLBACK" if et else "COMMIT")
        finally:
            self.db._lock.release()

db_conn = DB(DB_PATH)

async def init_db():
    await db_conn.connect()
    async with db_conn.tx() as c:
        await c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT, timezone TEXT DEFAULT 'Europe/Moscow',
                fiat_currency TEXT DEFAULT 'USD', language TEXT DEFAULT 'ru', is_verified INTEGER DEFAULT 0, 
                phone TEXT, is_onboarded INTEGER DEFAULT 0, created_at INTEGER NOT NULL
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS balances (
                user_id INTEGER NOT NULL, asset TEXT NOT NULL, amount REAL DEFAULT 0.0, PRIMARY KEY (user_id, asset)
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                id TEXT PRIMARY KEY, creator_id INTEGER NOT NULL, asset TEXT NOT NULL,
                total_amount REAL NOT NULL, per_activation REAL NOT NULL, activations_limit INTEGER NOT NULL DEFAULT 1,
                activations_used INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'active',
                description TEXT, password_hash TEXT, password_salt TEXT, bound_user_id INTEGER,
                bound_username TEXT, inline_message_id TEXT, business_connection_id TEXT, created_at INTEGER NOT NULL, expires_at INTEGER
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS check_activations (
                check_id TEXT NOT NULL, user_id INTEGER NOT NULL, amount REAL NOT NULL, created_at INTEGER NOT NULL,
                PRIMARY KEY (check_id, user_id)
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, asset TEXT NOT NULL,
                delta REAL NOT NULL, kind TEXT NOT NULL, ref TEXT, created_at INTEGER NOT NULL
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, from_asset TEXT NOT NULL, to_asset TEXT NOT NULL,
                from_amount REAL NOT NULL, to_amount REAL NOT NULL, rate REAL NOT NULL,
                fee_bps INTEGER NOT NULL, expires_at INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'open'
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS p2p_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, fiat TEXT, crypto TEXT,
                price REAL, amount REAL, limits_min REAL, limits_max REAL, payment_method TEXT,
                status TEXT DEFAULT 'active', created_at INTEGER NOT NULL
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS business_connections (
                id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, is_enabled INTEGER DEFAULT 1
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS user_channels (
                chat_id INTEGER PRIMARY KEY, owner_id INTEGER, title TEXT, chat_type TEXT
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                notif_general_news INTEGER DEFAULT 1,
                notif_general_marketing INTEGER DEFAULT 1,
                notif_ref INTEGER DEFAULT 1,
                notif_cryptopay_invoice INTEGER DEFAULT 1,
                notif_cryptopay_withdraw INTEGER DEFAULT 1,
                notif_cryptopay_webhook INTEGER DEFAULT 1,
                notif_p2p_review INTEGER DEFAULT 1,
                notif_giveaway INTEGER DEFAULT 1,
                notif_owner_new_sub INTEGER DEFAULT 1,
                notif_owner_renew_sub INTEGER DEFAULT 1,
                notif_owner_cancel_sub INTEGER DEFAULT 1,
                notif_sub_renew INTEGER DEFAULT 1,
                notif_sub_low_balance INTEGER DEFAULT 1,
                notif_sub_cancel INTEGER DEFAULT 1,
                notif_qr_pay_own INTEGER DEFAULT 1,
                notif_qr_pay_other INTEGER DEFAULT 1
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id TEXT PRIMARY KEY, creator_id INTEGER NOT NULL, asset TEXT NOT NULL,
                amount REAL NOT NULL, description TEXT, is_multi INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active', paid_count INTEGER DEFAULT 0, created_at INTEGER NOT NULL
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS invoice_payments (
                invoice_id TEXT NOT NULL, payer_id INTEGER NOT NULL, amount REAL NOT NULL, created_at INTEGER NOT NULL,
                PRIMARY KEY (invoice_id, payer_id)
            )
        """)

# --- ПОЛЬЗОВАТЕЛИ ---
async def create_user(uid: int, uname: str = ""):
    async with db_conn.tx() as c:
        await c.execute("INSERT OR IGNORE INTO users (id, username, created_at) VALUES (?, ?, ?)", (uid, uname, int(time.time())))

async def get_user(uid: int):
    async with db_conn.tx() as c:
        async with c.execute("SELECT * FROM users WHERE id = ?", (uid,)) as cur:
            return await cur.fetchone()

async def save_phone(uid: int, phone: str):
    async with db_conn.tx() as c:
        await c.execute("UPDATE users SET phone = ?, is_onboarded = 1 WHERE id = ?", (phone, uid))

async def get_user_lang(uid: int) -> str:
    user = await get_user(uid)
    return user["language"] if user and "language" in user.keys() else "ru"

async def update_user_setting(uid: int, field: str, value: str):
    async with db_conn.tx() as c:
        if field == "timezone":
            await c.execute("UPDATE users SET timezone = ? WHERE id = ?", (value, uid))
        elif field == "fiat_currency":
            await c.execute("UPDATE users SET fiat_currency = ? WHERE id = ?", (value, uid))
        elif field == "language":
            await c.execute("UPDATE users SET language = ? WHERE id = ?", (value, uid))

# --- БАЛАНСЫ ---
async def get_balance(uid: int, cur: str) -> float:
    async with db_conn.tx() as c:
        async with c.execute("SELECT amount FROM balances WHERE user_id = ? AND asset = ?", (uid, cur)) as r:
            row = await r.fetchone()
            return row["amount"] if row else 0.0

async def get_all_balances(uid: int) -> dict:
    async with db_conn.tx() as c:
        async with c.execute("SELECT asset, amount FROM balances WHERE user_id = ?", (uid,)) as r:
            return {row["asset"]: row["amount"] for row in await r.fetchall()}

async def update_balance(uid: int, asset: str, amt: float):
    async with db_conn.tx() as c:
        await c.execute("""
            INSERT INTO balances (user_id, asset, amount) VALUES (?, ?, ?)
            ON CONFLICT(user_id, asset) DO UPDATE SET amount = amount + excluded.amount
        """, (uid, asset, amt))

async def set_balance(uid: int, asset: str, amt: float):
    async with db_conn.tx() as c:
        await c.execute("""
            INSERT INTO balances (user_id, asset, amount) VALUES (?, ?, ?)
            ON CONFLICT(user_id, asset) DO UPDATE SET amount = excluded.amount
        """, (uid, asset, amt))

# --- ЖУРНАЛ ---
async def log_tx(uid: int, kind: str, asset: str, amt: float, status: str = "success", details: str = ""):
    async with db_conn.tx() as c:
        await c.execute("INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (uid, asset, amt, kind, details, int(time.time())))

async def get_history(uid: int, limit: int = 10):
    async with db_conn.tx() as c:
        async with c.execute("SELECT kind, asset, delta, ref, created_at FROM ledger WHERE user_id = ? ORDER BY id DESC LIMIT ?", (uid, limit)) as r:
            return await r.fetchall()

# --- ЧЕКИ ---
class InsufficientFunds(Exception): pass
class DuplicateCheck(Exception): pass
class CheckError(Exception):
    def __init__(self, code): self.code = code

def hash_password(pw: str, salt: str) -> str:
    return hashlib.scrypt(pw.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()

def verify_password(pw: str, salt: str, expected: str) -> bool:
    return hmac.compare_digest(hash_password(pw, salt), expected)

async def create_check(uid: int, asset: str, total: float, limit: int = 1, password: str = None, inline_message_id: str = None, check_id: str = None) -> str:
    if not check_id:
        check_id = secrets.token_hex(4)
    now = int(time.time())
    per = total / limit
    
    pw_hash = pw_salt = None
    if password:
        pw_salt = secrets.token_hex(8)
        pw_hash = hash_password(password, pw_salt)

    async with db_conn.tx() as c:
        cur = await c.execute("UPDATE balances SET amount = amount - ? WHERE user_id=? AND asset=? AND amount >= ?", (total, uid, asset, total))
        if cur.rowcount == 0:
            raise InsufficientFunds()

        try:
            await c.execute(
                "INSERT INTO checks (id, creator_id, asset, total_amount, per_activation, activations_limit, password_hash, password_salt, inline_message_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (check_id, uid, asset, total, per, limit, pw_hash, pw_salt, inline_message_id, now)
            )
        except aiosqlite.IntegrityError:
            raise DuplicateCheck()

        await c.execute("INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?,?,?,?,?,?)", (uid, asset, -total, "check_create", check_id, now))
    return check_id

async def create_invoice(uid: int, asset: str, amount: float, description: str, is_multi: bool = False) -> str:
    invoice_id = secrets.token_hex(4)
    now = int(time.time())
    async with db_conn.tx() as c:
        await c.execute(
            "INSERT INTO invoices (id, creator_id, asset, amount, description, is_multi, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (invoice_id, uid, asset, amount, description, 1 if is_multi else 0, now)
        )
    return invoice_id

async def get_invoice(invoice_id: str) -> dict | None:
    async with db_conn.tx() as c:
        async with c.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def pay_invoice(invoice_id: str, payer_id: int) -> dict:
    now = int(time.time())
    async with db_conn.tx() as c:
        inv = await (await c.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,))).fetchone()
        if not inv:
            raise CheckError("not_found")
        if inv["status"] != "active":
            raise CheckError("exhausted")
        if inv["creator_id"] == payer_id:
            raise CheckError("own_invoice")
        
        if not inv["is_multi"]:
            cur_check = await (await c.execute("SELECT 1 FROM invoice_payments WHERE invoice_id=?", (invoice_id,))).fetchone()
            if cur_check:
                raise CheckError("already_paid")

        cur = await c.execute(
            "UPDATE balances SET amount = amount - ? WHERE user_id = ? AND asset = ? AND amount >= ?",
            (inv["amount"], payer_id, inv["asset"], inv["amount"])
        )
        if cur.rowcount == 0:
            raise InsufficientFunds()

        await c.execute(
            "INSERT INTO balances (user_id, asset, amount) VALUES (?, ?, ?) ON CONFLICT(user_id, asset) DO UPDATE SET amount = amount + excluded.amount",
            (inv["creator_id"], inv["asset"], inv["amount"])
        )

        try:
            await c.execute(
                "INSERT INTO invoice_payments (invoice_id, payer_id, amount, created_at) VALUES (?, ?, ?, ?)",
                (invoice_id, payer_id, inv["amount"], now)
            )
        except aiosqlite.IntegrityError:
            if not inv["is_multi"]:
                raise CheckError("already_paid")

        if not inv["is_multi"]:
            await c.execute("UPDATE invoices SET status = 'paid', paid_count = paid_count + 1 WHERE id = ?", (invoice_id,))
        else:
            await c.execute("UPDATE invoices SET paid_count = paid_count + 1 WHERE id = ?", (invoice_id,))

        await c.execute("INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (payer_id, inv["asset"], -inv["amount"], "invoice_pay", invoice_id, now))
        await c.execute("INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (inv["creator_id"], inv["asset"], inv["amount"], "invoice_receive", invoice_id, now))

        return dict(inv)

async def create_admin_fake_check(uid: int, asset: str, amt: float) -> str:
    check_id = secrets.token_hex(4)
    now = int(time.time())
    async with db_conn.tx() as c:
        await c.execute(
            "INSERT INTO checks (id, creator_id, asset, total_amount, per_activation, activations_limit, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (check_id, uid, asset, amt, amt, 1, now)
        )
        await c.execute(
            "INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, asset, 0, "admin_fake_check", check_id, now)
        )
    return check_id

async def activate_check(check_id: str, user_id: int, password: str = None, username: str = None) -> dict:
    now = int(time.time())
    async with db_conn.tx() as c:
        row = await (await c.execute("SELECT * FROM checks WHERE id=?", (check_id,))).fetchone()
        if not row: raise CheckError("not_found")
        if row["status"] != "active": raise CheckError("exhausted")

        if row["creator_id"] == user_id:
            raise CheckError("own_check")

        if row["bound_user_id"] and row["bound_user_id"] != user_id:
            raise CheckError("not_recipient")

        if row["bound_username"]:
            clean_bound = row["bound_username"].lower().lstrip("@")
            clean_user = (username or "").lower().lstrip("@")
            if not clean_user or clean_bound != clean_user:
                raise CheckError("not_recipient")
        
        if row["password_hash"]:
            if not password or not verify_password(password, row["password_salt"], row["password_hash"]):
                raise CheckError("bad_password")

        cur = await c.execute(
            "UPDATE checks SET activations_used = activations_used + 1, status = CASE WHEN activations_used + 1 >= activations_limit THEN 'exhausted' ELSE status END WHERE id=? AND status='active' AND activations_used < activations_limit",
            (check_id,)
        )
        if cur.rowcount == 0:
            raise CheckError("exhausted")

        try:
            await c.execute("INSERT INTO check_activations (check_id, user_id, amount, created_at) VALUES (?,?,?,?)", (check_id, user_id, row["per_activation"], now))
        except aiosqlite.IntegrityError:
            raise CheckError("already_activated")

        await c.execute("INSERT INTO balances (user_id, asset, amount) VALUES (?,?,?) ON CONFLICT(user_id, asset) DO UPDATE SET amount = amount + excluded.amount", (user_id, row["asset"], row["per_activation"]))
        await c.execute("INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?,?,?,?,?,?)", (user_id, row["asset"], row["per_activation"], "check_activate", check_id, now))

        return dict(row)

async def update_check_message(check_id: str, chat_id: int, message_id: int):
    async with db_conn.tx() as c:
        await c.execute("UPDATE checks SET inline_message_id = ? WHERE id = ?", (f"{chat_id}:{message_id}", check_id))

async def get_check_message(check_id: str):
    async with db_conn.tx() as c:
        async with c.execute("SELECT inline_message_id FROM checks WHERE id = ?", (check_id,)) as r:
            row = await r.fetchone()
            return row["inline_message_id"] if row else None

async def update_check_business_conn(check_id: str, bcid: str):
    async with db_conn.tx() as c:
        await c.execute("UPDATE checks SET business_connection_id = ? WHERE id = ?", (bcid, check_id))

async def get_check_business_conn(check_id: str):
    async with db_conn.tx() as c:
        async with c.execute("SELECT business_connection_id FROM checks WHERE id = ?", (check_id,)) as r:
            row = await r.fetchone()
            return row["business_connection_id"] if row else None

# --- ОБМЕН (SWAP) ---
async def get_mid_prices() -> dict:
    url = "https://api.coingecko.com/api/v3/simple/price?ids=tether,bitcoin,ethereum,solana,tron,dogecoin,litecoin,binancecoin,usd-coin,the-open-network&vs_currencies=usd"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, timeout=5)
            data = r.json()
            return {
                "USDT": data["tether"]["usd"], "BTC": data["bitcoin"]["usd"], "ETH": data["ethereum"]["usd"],
                "SOL": data["solana"]["usd"], "TRX": data["tron"]["usd"], "DOGE": data["dogecoin"]["usd"],
                "LTC": data["litecoin"]["usd"], "BNB": data["binancecoin"]["usd"], "USDC": data["usd-coin"]["usd"],
                "TON": data["the-open-network"]["usd"], "XAUT": 2000.0,
            }
        except:
            return {
                "USDT": 1.0, "BTC": 80000.0, "ETH": 2500.0, "SOL": 100.0, "TRX": 0.3,
                "DOGE": 0.08, "LTC": 60.0, "BNB": 700.0, "USDC": 1.0, "TON": 5.5, "XAUT": 2000.0
            }

async def create_quote(user_id: int, from_asset: str, to_asset: str, from_amount: float) -> dict:
    prices = await get_mid_prices()
    if from_asset not in prices or to_asset not in prices:
        raise ValueError("Неизвестная валюта")
    
    mid_rate = prices[from_asset] / prices[to_asset]
    fee_bps = 100 
    to_amount = from_amount * mid_rate * (1 - fee_bps / 10000)
    
    quote_id = secrets.token_urlsafe(9)
    now = int(time.time())
    
    async with db_conn.tx() as c:
        await c.execute(
            "INSERT INTO quotes (id, user_id, from_asset, to_asset, from_amount, to_amount, rate, fee_bps, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (quote_id, user_id, from_asset, to_asset, from_amount, to_amount, mid_rate, fee_bps, now + 15)
        )
    return {
        "id": quote_id, "from_asset": from_asset, "to_asset": to_asset,
        "from_amount": from_amount, "to_amount": to_amount, "rate": mid_rate,
        "fee_bps": fee_bps, "expires_at": now + 15
    }

async def execute_swap(user_id: int, quote_id: str) -> dict:
    now = int(time.time())
    async with db_conn.tx() as c:
        q = await (await c.execute("SELECT * FROM quotes WHERE id=? AND user_id=?", (quote_id, user_id))).fetchone()
        if not q or q["status"] != "open" or q["expires_at"] < now:
            raise CheckError("quote_expired")
        
        cur = await c.execute("UPDATE quotes SET status='used' WHERE id=? AND status='open'", (quote_id,))
        if cur.rowcount == 0: raise CheckError("quote_expired")
        
        cur = await c.execute("UPDATE balances SET amount=amount-? WHERE user_id=? AND asset=? AND amount>=?",
                              (q["from_amount"], user_id, q["from_asset"], q["from_amount"]))
        if cur.rowcount == 0: raise InsufficientFunds
        
        await c.execute("INSERT INTO balances (user_id, asset, amount) VALUES (?,?,?) ON CONFLICT(user_id, asset) DO UPDATE SET amount = amount + excluded.amount",
                        (user_id, q["to_asset"], q["to_amount"]))
        
        await c.execute("INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?,?,?,?,?,?)",
                        (user_id, q["from_asset"], -q["from_amount"], "swap_out", q["to_asset"], now))
        await c.execute("INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?,?,?,?,?,?)",
                        (user_id, q["to_asset"], q["to_amount"], "swap_in", q["from_asset"], now))
        
        return dict(q)

# --- P2P ---
async def create_p2p_order(uid: int, o_type: str, fiat: str, crypto: str, price: float, amt: float, lim_min: float, lim_max: float, pay: str):
    async with db_conn.tx() as c:
        await c.execute(
            "INSERT INTO p2p_orders (user_id, type, fiat, crypto, price, amount, limits_min, limits_max, payment_method, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, o_type, fiat, crypto, price, amt, lim_min, lim_max, pay, int(time.time()))
        )

async def get_p2p_orders(o_type: str, fiat: str, crypto: str):
    async with db_conn.tx() as c:
        async with c.execute(
            "SELECT id, user_id, price, amount, limits_min, limits_max, payment_method FROM p2p_orders WHERE type = ? AND fiat = ? AND crypto = ? AND status = 'active' ORDER BY price ASC",
            (o_type, fiat, crypto)
        ) as cur:
            return await cur.fetchall()

async def get_user_orders(uid: int):
    async with db_conn.tx() as c:
        async with c.execute(
            "SELECT id, type, fiat, crypto, price, amount, status FROM p2p_orders WHERE user_id = ? ORDER BY id DESC",
            (uid,)
        ) as cur:
            return await cur.fetchall()

async def generate_fake_orders():
    async with db_conn.tx() as c:
        async with c.execute("SELECT COUNT(*) as cnt FROM p2p_orders WHERE user_id < 1000000") as cur:
            row = await cur.fetchone()
            if row and row["cnt"] > 0:
                return

        fiats = ["USD", "EUR", "RUB"]
        crypto = "USDT"
        banks = ["Сбербанк", "Тинькофф", "Альфа-Банк", "ВТБ", "Райффайзен", "ЮMoney", "Revolut", "PayPal", "Wise", "Payeer"]
        
        rates = {
            "USD": (0.99, 1.02),
            "EUR": (0.91, 0.94),
            "RUB": (93.5, 98.0)
        }

        for fiat in fiats:
            min_r, max_r = rates.get(fiat, (0.99, 1.02))
            for _ in range(15):
                price = round(random.uniform(min_r, min_r + (max_r - min_r) * 0.48), 2)
                amt = random.choice([50.0, 100.0, 250.0, 500.0, 1000.0])
                lim_min = round(amt * price * 0.1, 2)
                lim_max = round(amt * price, 2)
                bank = random.choice(banks)
                user_id = random.randint(100000, 999999)
                
                await c.execute(
                    "INSERT INTO p2p_orders (user_id, type, fiat, crypto, price, amount, limits_min, limits_max, payment_method, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, "buy", fiat, crypto, price, amt, lim_min, lim_max, bank, int(time.time()))
                )
                
            for _ in range(15):
                price = round(random.uniform(min_r + (max_r - min_r) * 0.52, max_r), 2)
                amt = random.choice([50.0, 100.0, 250.0, 500.0, 1000.0])
                lim_min = round(amt * price * 0.1, 2)
                lim_max = round(amt * price, 2)
                bank = random.choice(banks)
                user_id = random.randint(100000, 999999)
                
                await c.execute(
                    "INSERT INTO p2p_orders (user_id, type, fiat, crypto, price, amount, limits_min, limits_max, payment_method, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, "sell", fiat, crypto, price, amt, lim_min, lim_max, bank, int(time.time()))
                )

# --- НАСТРОЙКИ УВЕДОМЛЕНИЙ ---
ALLOWED_SETTINGS = {
    "notif_general_news", "notif_general_marketing", "notif_ref",
    "notif_cryptopay_invoice", "notif_cryptopay_withdraw", "notif_cryptopay_webhook",
    "notif_p2p_review", "notif_giveaway", "notif_owner_new_sub",
    "notif_owner_renew_sub", "notif_owner_cancel_sub", "notif_sub_renew",
    "notif_sub_low_balance", "notif_sub_cancel", "notif_qr_pay_own",
    "notif_qr_pay_other"
}

async def get_user_settings(uid: int):
    async with db_conn.tx() as c:
        await c.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (uid,))
        async with c.execute("SELECT * FROM user_settings WHERE user_id = ?", (uid,)) as r:
            return await r.fetchone()

async def toggle_user_setting(uid: int, field: str):
    if field not in ALLOWED_SETTINGS:
        raise ValueError(f"Invalid setting field: {field}")
    async with db_conn.tx() as c:
        await c.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (uid,))
        async with c.execute(f"SELECT {field} FROM user_settings WHERE user_id = ?", (uid,)) as r:
            row = await r.fetchone()
            current = row[field] if row else 1
        new_val = 0 if current else 1
        await c.execute(f"UPDATE user_settings SET {field} = ? WHERE user_id = ?", (new_val, uid))
        return new_val

# --- БИЗНЕС ---
async def save_business_connection(bc_id: str, owner_id: int, enabled: bool):
    async with db_conn.tx() as c:
        await c.execute("""
            INSERT INTO business_connections (id, owner_id, is_enabled) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET is_enabled = excluded.is_enabled
        """, (bc_id, owner_id, int(enabled)))

# --- АДМИНЫ ---
async def add_admin(uid: int):
    async with db_conn.tx() as c:
        await c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (uid,))

async def is_admin(uid: int) -> bool:
    async with db_conn.tx() as c:
        async with c.execute("SELECT 1 FROM admins WHERE user_id = ?", (uid,)) as r:
            return bool(await r.fetchone())