import hashlib
import hmac
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler


def hash_password(password: str) -> str:
    """Hash a password or hash-string input using scrypt + random salt."""
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password/secret must be at least 8 characters.")
    salt = secrets.token_hex(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=16384,
        r=8,
        p=1,
    ).hex()
    return f"scrypt${salt}${derived}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Safely verify a candidate password against a stored scrypt hash."""
    try:
        scheme, salt, expected_hex = stored_hash.split("$", 2)
        if scheme != "scrypt":
            return False
        candidate_hex = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt.encode("utf-8"),
            n=16384,
            r=8,
            p=1,
        ).hex()
        return hmac.compare_digest(candidate_hex, expected_hex)
    except Exception:
        return False


def sign_session_token(username: str, secret: str) -> str:
    """Create an HMAC-signed token for authenticated sessions."""
    nonce = secrets.token_hex(12)
    msg = f"{username}:{nonce}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"{username}:{nonce}:{sig}"


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        action = data.get("action")
        secret = os.environ.get("AUTH_SECRET", "dev-only-change-in-prod")

        if action == "register":
            username = (data.get("username") or "").strip()
            password = data.get("password") or ""
            if not username:
                self._send_json(400, {"error": "Username is required"})
                return
            try:
                pw_hash = hash_password(password)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(201, {"username": username, "password_hash": pw_hash})

        elif action == "verify":
            username = (data.get("username") or "").strip()
            password = data.get("password") or ""
            stored_hash = data.get("password_hash") or ""
            ok = verify_password(password, stored_hash)
            if not ok:
                self._send_json(401, {"authenticated": False, "error": "Invalid credentials"})
                return
            token = sign_session_token(username or "user", secret)
            self._send_json(200, {"authenticated": True, "token": token})

        else:
            self._send_json(400, {"error": "Supported actions: register, verify"})

    def _send_json(self, status: int, payload: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))
