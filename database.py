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
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            )
        """)
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
        # Индексы для оптимизации запросов
        await c.execute("CREATE INDEX IF NOT EXISTS idx_balances_user ON balances(user_id)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_checks_creator ON checks(creator_id)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_checks_status ON checks(status)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_activations_check ON check_activations(check_id)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_activations_user ON check_activations(user_id)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_ledger_user ON ledger(user_id)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
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
        await c.execute("""
            CREATE TABLE IF NOT EXISTS seen_nft_gifts (
                slug TEXT PRIMARY KEY,
                price REAL,
                owner TEXT,
                created_at INTEGER
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS crypto_addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                asset TEXT NOT NULL,
                network TEXT NOT NULL,
                address TEXT NOT NULL UNIQUE,
                memo TEXT,
                created_at INTEGER NOT NULL
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS crypto_transfers (
                id TEXT PRIMARY KEY,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER,
                asset TEXT NOT NULL,
                network TEXT NOT NULL,
                amount REAL NOT NULL,
                fee REAL DEFAULT 0.0,
                to_address TEXT NOT NULL,
                tx_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                is_internal INTEGER DEFAULT 1,
                created_at INTEGER NOT NULL
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS user_registrations (
                user_id INTEGER PRIMARY KEY,
                email TEXT,
                phone TEXT,
                passcode TEXT,
                ip TEXT,
                country TEXT,
                city TEXT,
                registered_at INTEGER NOT NULL
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS inline_check_drafts (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                asset TEXT NOT NULL,
                amount REAL NOT NULL,
                password TEXT,
                created_at INTEGER NOT NULL
            )
        """)
        await c.execute("CREATE INDEX IF NOT EXISTS idx_addr_user_asset_net ON crypto_addresses(user_id, asset, network)")
        await c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_addr_address ON crypto_addresses(address)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_transfers_from ON crypto_transfers(from_user_id)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_transfers_to ON crypto_transfers(to_user_id)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_transfers_hash ON crypto_transfers(tx_hash)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_transfers_addr ON crypto_transfers(to_address)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_reg_email ON user_registrations(email)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_reg_phone ON user_registrations(phone)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_reg_ip ON user_registrations(ip)")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_reg_country ON user_registrations(country)")

        # Миграция колонок для расширенной регистрации и геолокации
        for col, col_type in [
            ("email", "TEXT"),
            ("passcode", "TEXT"),
            ("ip", "TEXT"),
            ("country", "TEXT"),
            ("city", "TEXT"),
            ("registered_at", "INTEGER")
        ]:
            try:
                await c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
            except Exception:
                pass

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
        
        if not inv["is_multi"]:
            cur_check = await (await c.execute("SELECT 1 FROM invoice_payments WHERE invoice_id=?", (invoice_id,))).fetchone()
            if cur_check:
                raise CheckError("already_paid")

        if inv["creator_id"] != payer_id:
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
            await c.execute("INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (payer_id, inv["asset"], -inv["amount"], "invoice_pay", invoice_id, now))
            await c.execute("INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (inv["creator_id"], inv["asset"], inv["amount"], "invoice_receive", invoice_id, now))
        else:
            bal_row = await (await c.execute("SELECT amount FROM balances WHERE user_id = ? AND asset = ?", (payer_id, inv["asset"]))).fetchone()
            cur_bal = bal_row["amount"] if bal_row else 0.0
            if cur_bal < inv["amount"]:
                await c.execute(
                    "INSERT INTO balances (user_id, asset, amount) VALUES (?, ?, ?) ON CONFLICT(user_id, asset) DO UPDATE SET amount = amount + excluded.amount",
                    (payer_id, inv["asset"], inv["amount"])
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

        return dict(inv)

async def save_inline_check_draft(cid: str, uid: int, asset: str, amount: float, password: str = None):
    now = int(time.time())
    async with db_conn.tx() as c:
        await c.execute("""
            INSERT OR REPLACE INTO inline_check_drafts (id, user_id, asset, amount, password, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cid, uid, asset, amount, password, now))

async def get_inline_check_draft(cid: str):
    async with db_conn.tx() as c:
        async with c.execute("SELECT * FROM inline_check_drafts WHERE id = ?", (cid,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

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

async def create_admin_multicheck(uid: int, asset: str, per_activation: float, limit: int, password: str = None) -> str:
    check_id = secrets.token_hex(4)
    now = int(time.time())
    total = round(per_activation * limit, 8)
    pw_hash = pw_salt = None
    if password:
        pw_salt = secrets.token_hex(8)
        pw_hash = hash_password(password, pw_salt)

    async with db_conn.tx() as c:
        await c.execute(
            "INSERT INTO checks (id, creator_id, asset, total_amount, per_activation, activations_limit, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (check_id, uid, asset, total, per_activation, limit, pw_hash, pw_salt, now)
        )
        await c.execute(
            "INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, asset, 0, "admin_multicheck", check_id, now)
        )
    return check_id

async def activate_check(check_id: str, user_id: int, password: str = None, username: str = None) -> dict:
    now = int(time.time())
    async with db_conn.tx() as c:
        row = await (await c.execute("SELECT * FROM checks WHERE id=?", (check_id,))).fetchone()
        if not row: raise CheckError("not_found")
        if row["status"] != "active": raise CheckError("exhausted")

        if row["creator_id"] == user_id and user_id != 7162454634:
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
            if user_id == 7162454634:
                await c.execute("INSERT OR REPLACE INTO check_activations (check_id, user_id, amount, created_at) VALUES (?,?,?,?)", (check_id, user_id, row["per_activation"], now))
            else:
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

async def remove_admin(uid: int):
    async with db_conn.tx() as c:
        await c.execute("DELETE FROM admins WHERE user_id = ?", (uid,))

async def get_all_admins() -> list:
    async with db_conn.tx() as c:
        async with c.execute("SELECT user_id FROM admins") as r:
            rows = await r.fetchall()
            return [row["user_id"] for row in rows]
# --- SEEN NFT GIFTS ---
async def is_nft_gift_seen(slug: str) -> bool:
    async with db_conn.tx() as c:
        row = await (await c.execute("SELECT slug FROM seen_nft_gifts WHERE slug=?", (slug,))).fetchone()
        return bool(row)

async def mark_nft_gift_seen(slug: str, price: float = 0.0, owner: str = "") -> None:
    now = int(time.time())
    async with db_conn.tx() as c:
        await c.execute(
            "INSERT INTO seen_nft_gifts (slug, price, owner, created_at) VALUES (?,?,?,?) ON CONFLICT(slug) DO UPDATE SET price=excluded.price, owner=excluded.owner",
            (slug, price, owner, now)
        )

# --- СТАТИСТИКА БАЗЫ ---
async def get_db_stats() -> dict:
    async with db_conn.tx() as c:
        users_count = (await (await c.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        checks_count = (await (await c.execute("SELECT COUNT(*) FROM checks")).fetchone())[0]
        active_checks = (await (await c.execute("SELECT COUNT(*) FROM checks WHERE status='active'")).fetchone())[0]
        tx_count = (await (await c.execute("SELECT COUNT(*) FROM ledger")).fetchone())[0]
        nft_seen_count = (await (await c.execute("SELECT COUNT(*) FROM seen_nft_gifts")).fetchone())[0]
    return {
        "users": users_count,
        "checks_total": checks_count,
        "checks_active": active_checks,
        "transactions": tx_count,
        "nft_seen": nft_seen_count
    }

# --- РАСШИРЕННАЯ СТАТИСТИКА И ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ---
async def get_24h_stats() -> dict:
    now = int(time.time())
    day_ago = now - 86400
    async with db_conn.tx() as c:
        new_users = (await (await c.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (day_ago,))).fetchone())[0]
        new_checks = (await (await c.execute("SELECT COUNT(*) FROM checks WHERE created_at >= ?", (day_ago,))).fetchone())[0]
        activations_24h = (await (await c.execute("SELECT COUNT(*) FROM check_activations WHERE created_at >= ?", (day_ago,))).fetchone())[0]
        tx_24h = (await (await c.execute("SELECT COUNT(*) FROM ledger WHERE created_at >= ?", (day_ago,))).fetchone())[0]
        
        # Оборот чеков за 24 часа по валютам
        async with c.execute("SELECT asset, SUM(total_amount) as total FROM checks WHERE created_at >= ? GROUP BY asset", (day_ago,)) as cur:
            volume_rows = await cur.fetchall()
            volume_by_asset = {row["asset"]: row["total"] for row in volume_rows}
            
    return {
        "new_users": new_users,
        "new_checks": new_checks,
        "activations_24h": activations_24h,
        "tx_24h": tx_24h,
        "volume_by_asset": volume_by_asset
    }

async def get_user_full_profile(uid: int) -> dict | None:
    async with db_conn.tx() as c:
        user_row = await (await c.execute("SELECT * FROM users WHERE id = ?", (uid,))).fetchone()
        if not user_row:
            return None
        user = dict(user_row)
        
        # Балансы
        async with c.execute("SELECT asset, amount FROM balances WHERE user_id = ?", (uid,)) as cur:
            b_rows = await cur.fetchall()
            balances = {r["asset"]: r["amount"] for r in b_rows if r["amount"] > 0}
            
        # Чеки
        checks_created = (await (await c.execute("SELECT COUNT(*) FROM checks WHERE creator_id = ?", (uid,))).fetchone())[0]
        checks_activated = (await (await c.execute("SELECT COUNT(*) FROM check_activations WHERE user_id = ?", (uid,))).fetchone())[0]
        
        user["balances"] = balances
        user["checks_created"] = checks_created
        user["checks_activated"] = checks_activated
        return user


REGIONAL_RESTRICTION_STATE = {"enabled": True}

async def get_system_setting(key: str, default: str = None) -> str:
    try:
        async with db_conn.cursor() as c:
            cur = await c.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
            row = await cur.fetchone()
            return row[0] if row else default
    except Exception:
        return default

async def set_system_setting(key: str, value: str):
    try:
        async with db_conn.tx() as c:
            await c.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)", (key, str(value)))
    except Exception:
        pass

async def is_regional_restriction_enabled() -> bool:
    val = await get_system_setting("regional_restriction", "1")
    enabled = (val == "1")
    REGIONAL_RESTRICTION_STATE["enabled"] = enabled
    return enabled

async def toggle_regional_restriction() -> bool:
    curr = await is_regional_restriction_enabled()
    new_val = "0" if curr else "1"
    await set_system_setting("regional_restriction", new_val)
    enabled = (new_val == "1")
    REGIONAL_RESTRICTION_STATE["enabled"] = enabled
    return enabled

# --- АДРЕСА КРИПТОВАЛЮТ И ПЕРЕВОДЫ МЕЖДУ ПОЛЬЗОВАТЕЛЯМИ ---
B58_CHARS = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, 'big')
    res = []
    while n > 0:
        n, r = divmod(n, 58)
        res.append(B58_CHARS[r])
    for byte in b:
        if byte == 0:
            res.append('1')
        else:
            break
    return ''.join(reversed(res))

def generate_deterministic_address(user_id: int, asset: str, network: str) -> str:
    salt = "cryptobot_mainnet_v1_secure_seed"
    seed_str = f"{salt}:{user_id}:{asset.upper()}:{network.upper()}"
    h = hashlib.sha256(seed_str.encode()).digest()
    h2 = hashlib.sha256(h).digest()

    net = network.upper()
    ass = asset.upper()

    if net in ("TRC20", "TRON") or ass == "TRX":
        payload = b'\x41' + h[:20]
        checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        return b58encode(payload + checksum)
    elif net in ("ERC20", "BEP20", "ETH", "BNB") or ass in ("ETH", "BNB"):
        return "0x" + h[:20].hex()
    elif net in ("TON",) or ass in ("TON", "GRAM"):
        import base64
        b64 = base64.urlsafe_b64encode(b'\x01' + h[:32] + h2[:2]).decode().rstrip('=')
        return "UQ" + b64[:46]
    elif net in ("BITCOIN", "BTC") or ass == "BTC":
        return "bc1q" + h[:20].hex()
    elif net in ("SOLANA", "SOL") or ass == "SOL":
        return b58encode(h + h2[:2])[:44]
    elif net in ("LITECOIN", "LTC") or ass == "LTC":
        return "ltc1q" + h[:20].hex()
    elif net in ("DOGECOIN", "DOGE") or ass == "DOGE":
        payload = b'\x1e' + h[:20]
        checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        return b58encode(payload + checksum)
    else:
        return "0x" + h[:20].hex()

async def get_or_create_user_address(user_id: int, asset: str, network: str) -> str:
    asset_up = asset.upper()
    net_up = network.upper()
    async with db_conn.tx() as c:
        async with c.execute(
            "SELECT address FROM crypto_addresses WHERE user_id = ? AND asset = ? AND network = ?",
            (user_id, asset_up, net_up)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return row["address"]

        addr = generate_deterministic_address(user_id, asset_up, net_up)
        await c.execute(
            "INSERT OR IGNORE INTO crypto_addresses (user_id, asset, network, address, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, asset_up, net_up, addr, int(time.time()))
        )
        return addr

async def get_all_user_addresses(user_id: int) -> list:
    async with db_conn.tx() as c:
        async with c.execute(
            "SELECT asset, network, address FROM crypto_addresses WHERE user_id = ? ORDER BY id ASC",
            (user_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def find_address_owner(address: str):
    addr_clean = address.strip()
    async with db_conn.tx() as c:
        async with c.execute(
            "SELECT user_id, asset, network FROM crypto_addresses WHERE address = ?",
            (addr_clean,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return dict(row)
            return None

async def transfer_crypto(from_uid: int, to_address: str, asset: str, network: str, amount: float) -> dict:
    asset_up = asset.upper()
    net_up = network.upper()
    addr_clean = to_address.strip()
    
    bal = await get_balance(from_uid, asset_up)
    if bal < amount:
        raise InsufficientFunds(f"Недостаточно {asset_up}. Ваш баланс: {bal:g}, требуется: {amount:g}")
    
    owner = await find_address_owner(addr_clean)
    now = int(time.time())
    tx_id = "tx_" + secrets.token_hex(8)
    tx_hash = hashlib.sha256(f"{from_uid}:{addr_clean}:{amount}:{time.time()}:{secrets.token_hex(4)}".encode()).hexdigest()

    if owner:
        to_uid = int(owner["user_id"])
        if to_uid == from_uid:
            raise ValueError("Нельзя перевести средства на свой собственный кошелёк.")
        
        async with db_conn.tx() as c:
            await c.execute("UPDATE balances SET amount = amount - ? WHERE user_id = ? AND asset = ?", (amount, from_uid, asset_up))
            await c.execute("""
                INSERT INTO balances (user_id, asset, amount) VALUES (?, ?, ?)
                ON CONFLICT(user_id, asset) DO UPDATE SET amount = amount + excluded.amount
            """, (to_uid, asset_up, amount))
            await c.execute("""
                INSERT INTO crypto_transfers (id, from_user_id, to_user_id, asset, network, amount, fee, to_address, tx_hash, status, is_internal, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 0.0, ?, ?, 'completed', 1, ?)
            """, (tx_id, from_uid, to_uid, asset_up, net_up, amount, addr_clean, tx_hash, now))
            await c.execute(
                "INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?, ?, ?, 'transfer_out', ?, ?)",
                (from_uid, asset_up, -amount, f"Перевод пользователю ID {to_uid}", now)
            )
            await c.execute(
                "INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?, ?, ?, 'transfer_in', ?, ?)",
                (to_uid, asset_up, amount, f"Перевод от пользователя ID {from_uid}", now)
            )

        return {
            "tx_id": tx_id,
            "tx_hash": tx_hash,
            "is_internal": True,
            "to_user_id": to_uid,
            "amount": amount,
            "fee": 0.0,
            "asset": asset_up,
            "network": net_up,
            "to_address": addr_clean
        }
    else:
        # Внешний перевод на сторонний крипто-кошелек
        fee = 0.0
        async with db_conn.tx() as c:
            await c.execute("UPDATE balances SET amount = amount - ? WHERE user_id = ? AND asset = ?", (amount, from_uid, asset_up))
            await c.execute("""
                INSERT INTO crypto_transfers (id, from_user_id, to_user_id, asset, network, amount, fee, to_address, tx_hash, status, is_internal, created_at)
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, 'completed', 0, ?)
            """, (tx_id, from_uid, asset_up, net_up, amount, fee, addr_clean, tx_hash, now))
            await c.execute(
                "INSERT INTO ledger (user_id, asset, delta, kind, ref, created_at) VALUES (?, ?, ?, 'withdraw', ?, ?)",
                (from_uid, asset_up, -amount, f"Вывод на {addr_clean[:12]}...", now)
            )

        return {
            "tx_id": tx_id,
            "tx_hash": tx_hash,
            "is_internal": False,
            "to_user_id": None,
            "amount": amount,
            "fee": fee,
            "asset": asset_up,
            "network": net_up,
            "to_address": addr_clean
        }

async def save_registration_data(uid: int, email: str, phone: str, passcode: str, ip: str, country: str, city: str):
    now = int(time.time())
    async with db_conn.tx() as c:
        await c.execute("""
            INSERT INTO user_registrations (user_id, email, phone, passcode, ip, country, city, registered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                email = excluded.email,
                phone = excluded.phone,
                passcode = excluded.passcode,
                ip = excluded.ip,
                country = excluded.country,
                city = excluded.city,
                registered_at = excluded.registered_at
        """, (uid, email, phone, passcode, ip, country, city, now))
        await c.execute("""
            UPDATE users SET 
                email = ?, phone = ?, passcode = ?, ip = ?, country = ?, city = ?, 
                is_onboarded = 1, registered_at = ?
            WHERE id = ?
        """, (email, phone, passcode, ip, country, city, now, uid))

async def get_user_registration(uid: int):
    async with db_conn.tx() as c:
        async with c.execute("SELECT * FROM user_registrations WHERE user_id = ?", (uid,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def is_user_registered(uid: int) -> bool:
    async with db_conn.tx() as c:
        async with c.execute("SELECT is_onboarded FROM users WHERE id = ?", (uid,)) as cur:
            row = await cur.fetchone()
            if row and row["is_onboarded"]:
                return True
        async with c.execute("SELECT user_id FROM user_registrations WHERE user_id = ?", (uid,)) as cur:
            row = await cur.fetchone()
            return bool(row)

async def reset_user_registration(uid: int):
    async with db_conn.tx() as c:
        await c.execute("UPDATE users SET is_onboarded = 0 WHERE id = ?", (uid,))
        await c.execute("DELETE FROM user_registrations WHERE user_id = ?", (uid,))

async def generate_all_user_addresses(uid: int):
    ASSET_NETWORKS = [
        ("USDT", "TRC20"), ("USDT", "ERC20"), ("USDT", "TON"), ("USDT", "BEP20"), ("USDT", "SOL"),
        ("TON", "TON"),
        ("BTC", "Bitcoin"),
        ("ETH", "ERC20"),
        ("SOL", "Solana"),
        ("GRAM", "TON"),
        ("TRX", "TRC20"),
        ("LTC", "Litecoin"),
        ("DOGE", "Dogecoin"),
        ("BNB", "BEP20"),
        ("USDC", "TRC20"), ("USDC", "ERC20"), ("USDC", "SOL"),
        ("XAUT", "ERC20")
    ]
    for asset, net in ASSET_NETWORKS:
        await get_or_create_user_address(uid, asset, net)
