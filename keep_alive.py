# keep_alive.py
import os
import json
import threading
import urllib.parse
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

import config
from sessions import (
    create_session, get_session, delete_session,
    verify_telegram_init_data, verify_telegram_widget_data
)
from database import sync_set_user_onboarded

log = logging.getLogger("api_server")


class ApiHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _extract_token(self) -> str | None:
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        parsed_url = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed_url.query)
        if "token" in qs:
            return qs["token"][0].strip()
        return None

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("", "/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(b"OK")
            return

        if path == "/api/auth/session":
            token = self._extract_token()
            if not token:
                self._send_json(401, {"ok": False, "authenticated": False, "error": "No token provided"})
                return
            session_data = get_session(token)
            if not session_data:
                self._send_json(401, {"ok": False, "authenticated": False, "error": "Invalid or expired session"})
                return
            self._send_json(200, {"ok": True, "authenticated": True, "session": session_data})
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            req_data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            self._send_json(400, {"ok": False, "error": "Invalid JSON body"})
            return

        # 1. Telegram Auth Endpoint
        if path == "/api/auth/telegram":
            bot_token = config.BOT_TOKEN or os.getenv("BOT_TOKEN", "")
            if not bot_token:
                self._send_json(500, {"ok": False, "error": "Server bot token not configured"})
                return

            init_data = req_data.get("initData", "")
            widget_data = req_data.get("widgetData")

            verified_user = None
            if init_data:
                verified_user = verify_telegram_init_data(init_data, bot_token)
            elif widget_data:
                verified_user = verify_telegram_widget_data(widget_data, bot_token)

            if not verified_user or not verified_user.get("id"):
                self._send_json(401, {
                    "ok": False,
                    "error": "Telegram authentication failed. Invalid cryptographic signature."
                })
                return

            uid = int(verified_user["id"])
            try:
                sync_set_user_onboarded(uid)
            except Exception as e_db:
                log.warning("Database sync onboard error: %s", e_db)

            session = create_session(uid, verified_user)
            self._send_json(200, {
                "ok": True,
                "authenticated": True,
                "session_token": session["session_id"],
                "user": session
            })
            return

        # 2. Session Validation Endpoint
        if path == "/api/auth/session":
            token = self._extract_token() or req_data.get("token")
            if not token:
                self._send_json(401, {"ok": False, "authenticated": False, "error": "No token provided"})
                return
            session_data = get_session(token)
            if not session_data:
                self._send_json(401, {"ok": False, "authenticated": False, "error": "Invalid or expired session"})
                return
            self._send_json(200, {"ok": True, "authenticated": True, "session": session_data})
            return

        # 3. Logout Endpoint
        if path == "/api/auth/logout":
            token = self._extract_token() or req_data.get("token")
            if token:
                delete_session(token)
            self._send_json(200, {"ok": True, "message": "Session terminated successfully"})
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def log_message(self, format, *args):
        # Silence routine access logs
        return


def start_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), ApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return port
