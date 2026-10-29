# sessions.py
import os
import json
import time
import secrets
import hmac
import hashlib
import urllib.parse
import logging

log = logging.getLogger("sessions")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")

os.makedirs(SESSIONS_DIR, exist_ok=True)

# Create .gitkeep in sessions dir
gitkeep_path = os.path.join(SESSIONS_DIR, ".gitkeep")
if not os.path.exists(gitkeep_path):
    try:
        with open(gitkeep_path, "w") as f:
            pass
    except Exception:
        pass


def _is_safe_token(token: str) -> bool:
    if not token or not isinstance(token, str):
        return False
    if len(token) != 64 or not all(c in "0123456789abcdefABCDEF" for c in token):
        return False
    return True


def create_session(user_id: int, user_info: dict = None, duration_days: int = 30) -> dict:
    if user_info is None:
        user_info = {}

    session_token = secrets.token_hex(32)
    now = int(time.time())
    expires_at = now + (duration_days * 86400)

    session_data = {
        "session_id": session_token,
        "user_id": int(user_id),
        "username": str(user_info.get("username", "") or ""),
        "first_name": str(user_info.get("first_name", "") or ""),
        "created_at": now,
        "expires_at": expires_at,
        "auth_method": "telegram"
    }

    session_file = os.path.join(SESSIONS_DIR, f"{session_token}.json")
    try:
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        log.info("Created persistent session %s for user %d", session_token[:8], user_id)
    except Exception as e:
        log.error("Failed to write session file: %s", e)

    return session_data


def get_session(session_token: str) -> dict | None:
    if not _is_safe_token(session_token):
        return None

    session_file = os.path.join(SESSIONS_DIR, f"{session_token}.json")
    if not os.path.exists(session_file):
        return None

    try:
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        now = int(time.time())
        if data.get("expires_at", 0) < now:
            try:
                os.remove(session_file)
            except Exception:
                pass
            return None

        return data
    except Exception as e:
        log.warning("Failed to read session %s: %s", session_token[:8], e)
        return None


def delete_session(session_token: str) -> bool:
    if not _is_safe_token(session_token):
        return False

    session_file = os.path.join(SESSIONS_DIR, f"{session_token}.json")
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
            log.info("Terminated session %s", session_token[:8])
            return True
        except Exception as e:
            log.error("Failed to delete session %s: %s", session_token[:8], e)
            return False
    return False


def verify_telegram_init_data(raw_init_data: str, bot_token: str) -> dict | None:
    if not raw_init_data or not bot_token:
        return None

    try:
        parsed = urllib.parse.parse_qs(raw_init_data, keep_blank_values=True)
        if "hash" not in parsed:
            return None
        received_hash = parsed["hash"][0]

        items = []
        for k, v in parsed.items():
            if k == "hash":
                continue
            items.append(f"{k}={v[0]}")
        items.sort()
        check_string = "\n".join(items)

        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        calc_hash = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calc_hash, received_hash):
            return None

        # Verify auth_date (allow up to 7 days for webapp session caching)
        auth_date = int(parsed.get("auth_date", ["0"])[0])
        now = int(time.time())
        if abs(now - auth_date) > 86400 * 7:
            return None

        user_raw = parsed.get("user", [None])[0]
        if user_raw:
            return json.loads(user_raw)
        return {}
    except Exception as e:
        log.warning("Telegram initData validation exception: %s", e)
        return None


def verify_telegram_widget_data(data: dict, bot_token: str) -> dict | None:
    if not data or not isinstance(data, dict) or not bot_token:
        return None

    try:
        received_hash = data.get("hash")
        if not received_hash:
            return None

        items = []
        for k, v in data.items():
            if k == "hash":
                continue
            items.append(f"{k}={v}")
        items.sort()
        check_string = "\n".join(items)

        secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
        calc_hash = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calc_hash, received_hash):
            return None

        auth_date = int(data.get("auth_date", 0))
        now = int(time.time())
        if abs(now - auth_date) > 86400 * 7:
            return None

        return {
            "id": int(data.get("id")),
            "first_name": str(data.get("first_name", "")),
            "username": str(data.get("username", ""))
        }
    except Exception as e:
        log.warning("Telegram widget data validation exception: %s", e)
        return None
