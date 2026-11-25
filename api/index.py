import hashlib
import hmac
import os
import secrets
import requests
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="")

SEARCH_CACHE: dict[str, list[dict]] = {}


def hash_password(password: str) -> str:
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
    nonce = secrets.token_hex(12)
    msg = f"{username}:{nonce}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"{username}:{nonce}:{sig}"


@app.get("/")
def serve_home():
    return send_from_directory(PUBLIC_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "youtube_key_configured": bool(os.environ.get("YOUTUBE_API_KEY")),
        "auth_secret_configured": bool(os.environ.get("AUTH_SECRET")),
    })


@app.post("/api/auth")
def auth():
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    secret = os.environ.get("AUTH_SECRET", "dev-only-change-in-prod")

    if action == "register":
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username:
            return jsonify({"error": "Username is required"}), 400
        try:
            pw_hash = hash_password(password)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"username": username, "password_hash": pw_hash}), 201

    if action == "verify":
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        stored_hash = data.get("password_hash") or ""
        if not verify_password(password, stored_hash):
            return jsonify({"authenticated": False, "error": "Invalid credentials"}), 401
        token = sign_session_token(username or "user", secret)
        return jsonify({"authenticated": True, "token": token}), 200

    return jsonify({"error": "Supported actions: register, verify"}), 400


@app.get("/api/youtube_search")
def youtube_search():
    query = (request.args.get("q") or "").strip().lower()
    if not query:
        return jsonify({"error": "Missing query parameter 'q'"}), 400

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return jsonify({"error": "YOUTUBE_API_KEY is not configured"}), 500

    if query in SEARCH_CACHE:
        return jsonify({"cached": True, "tracks": SEARCH_CACHE[query]}), 200

    resp = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "part": "snippet",
            "type": "video",
            "videoCategoryId": "10",
            "maxResults": 8,
            "q": query,
            "key": api_key,
        },
        timeout=10,
    )

    if resp.status_code != 200:
        return jsonify({"error": "YouTube API request failed"}), resp.status_code

    items = resp.json().get("items", [])
    tracks = [
        {
            "videoId": item.get("id", {}).get("videoId"),
            "title": item.get("snippet", {}).get("title"),
            "artist": item.get("snippet", {}).get("channelTitle"),
            "thumbnail": (
                item.get("snippet", {}).get("thumbnails", {}).get("high", {}).get("url")
                or item.get("snippet", {}).get("thumbnails", {}).get("default", {}).get("url")
            ),
        }
        for item in items
        if item.get("id", {}).get("videoId")
    ]

    SEARCH_CACHE[query] = tracks
    return jsonify({"cached": False, "tracks": tracks}), 200
