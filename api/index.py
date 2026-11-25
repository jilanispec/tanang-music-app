import hashlib
import hmac
import json
import os
import re
import secrets
from urllib.parse import parse_qs, urlparse
import requests
from flask import Flask, jsonify, make_response, request, send_from_directory

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="")

SEARCH_CACHE: dict[str, list[dict]] = {}
MEMORY_DB: dict[str, str] = {}

DEFAULT_CONFIG = {
    "version": "v2.0",
    "announcement_title": "Welcome to TANANG MUSIC 2.0",
    "announcement_body": "Search movies, hero hits, albums, and import YouTube or Spotify playlists.",
    "featured_query": "Telugu superhit songs",
    "maintenance_banner": "",
}


# ---------------------------------------------------------------------------
# Upstash Redis / Vercel KV REST Helper (with automatic in-memory fallback)
# ---------------------------------------------------------------------------
def _kv_headers():
    token = (
        os.environ.get("KV_REST_API_TOKEN")
        or os.environ.get("STORAGE_REST_API_TOKEN")
        or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    )
    url = (
        os.environ.get("KV_REST_API_URL")
        or os.environ.get("STORAGE_REST_API_URL")
        or os.environ.get("UPSTASH_REDIS_REST_URL")
    )
    if url and token:
        return url.rstrip("/"), {"Authorization": f"Bearer {token}"}
    return None, None


def kv_get(key: str):
    url, headers = _kv_headers()
    if url and headers:
        try:
            r = requests.get(f"{url}/get/{key}", headers=headers, timeout=6)
            if r.status_code == 200:
                val = r.json().get("result")
                if val is None:
                    return None
                return json.loads(val) if isinstance(val, str) else val
        except Exception:
            pass
    raw = MEMORY_DB.get(key)
    return json.loads(raw) if raw else None


def kv_set(key: str, value) -> bool:
    serialized = json.dumps(value)
    MEMORY_DB[key] = serialized
    url, headers = _kv_headers()
    if url and headers:
        try:
            r = requests.post(
                f"{url}/set/{key}",
                headers=headers,
                data=serialized.encode("utf-8"),
                timeout=6,
            )
            return r.status_code == 200
        except Exception:
            return False
    return True


# ---------------------------------------------------------------------------
# Password Hashing & Session Signing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def serve_home():
    return send_from_directory(PUBLIC_DIR, "index.html")


@app.route("/api/health", methods=["GET"])
def health():
    url, _ = _kv_headers()
    return jsonify({
        "status": "ok",
        "youtube_key_configured": bool(os.environ.get("YOUTUBE_API_KEY")),
        "auth_secret_configured": bool(os.environ.get("AUTH_SECRET")),
        "database_connected": bool(url),
    }), 200


@app.route("/api/auth", methods=["POST", "OPTIONS"])
def auth():
    if request.method == "OPTIONS":
        return make_response("", 204)

    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip().lower()
    secret = os.environ.get("AUTH_SECRET", "tanang-music-secret-key")
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""

    if not username:
        return jsonify({"error": "Username is required"}), 400

    user_key = f"tanang:user:{username}"

    if action == "register":
        display_name = (data.get("display_name") or username).strip()
        existing = kv_get(user_key)
        if existing:
            return jsonify({"error": "Username already taken. Please login."}), 409
        try:
            pw_hash = hash_password(password)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        user_record = {
            "username": username,
            "display_name": display_name,
            "password_hash": pw_hash,
        }
        kv_set(user_key, user_record)
        token = sign_session_token(username, secret)
        return jsonify({
            "authenticated": True,
            "username": username,
            "display_name": display_name,
            "token": token,
        }), 201

    if action in ("login", "verify"):
        record = kv_get(user_key)
        stored_hash = (record or {}).get("password_hash") or data.get("password_hash") or ""
        if not stored_hash or not verify_password(password, stored_hash):
            return jsonify({"authenticated": False, "error": "Invalid username or password"}), 401
        display_name = (record or {}).get("display_name") or username
        token = sign_session_token(username, secret)
        return jsonify({
            "authenticated": True,
            "username": username,
            "display_name": display_name,
            "token": token,
        }), 200

    return jsonify({"error": "Unsupported action"}), 400


@app.route("/api/user_data", methods=["GET", "POST", "OPTIONS"])
def user_data():
    if request.method == "OPTIONS":
        return make_response("", 204)

    if request.method == "GET":
        username = (request.args.get("username") or "").strip().lower()
        if not username:
            return jsonify({"error": "Username required"}), 400
        library = kv_get(f"tanang:lib:{username}") or {
            "liked": [],
            "favorites": [],
            "playlists": [],
        }
        return jsonify(library), 200

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    if not username:
        return jsonify({"error": "Username required"}), 400

    library = {
        "liked": data.get("liked", []),
        "favorites": data.get("favorites", []),
        "playlists": data.get("playlists", []),
    }
    kv_set(f"tanang:lib:{username}", library)
    return jsonify({"saved": True}), 200


@app.route("/api/app_config", methods=["GET", "POST", "OPTIONS"])
def app_config():
    if request.method == "OPTIONS":
        return make_response("", 204)

    if request.method == "GET":
        cfg = kv_get("tanang:app_config") or DEFAULT_CONFIG
        return jsonify(cfg), 200

    data = request.get_json(silent=True) or {}
    admin_key = (data.get("admin_key") or "").strip()
    expected_secret = os.environ.get("AUTH_SECRET", "")

    if not expected_secret or not hmac.compare_digest(admin_key, expected_secret):
        return jsonify({"error": "Invalid Admin Secret Key"}), 403

    current = kv_get("tanang:app_config") or dict(DEFAULT_CONFIG)
    current["version"] = (data.get("version") or current["version"]).strip()
    current["announcement_title"] = (data.get("announcement_title") or "").strip()
    current["announcement_body"] = (data.get("announcement_body") or "").strip()
    current["featured_query"] = (data.get("featured_query") or current["featured_query"]).strip()
    current["maintenance_banner"] = (data.get("maintenance_banner") or "").strip()

    kv_set("tanang:app_config", current)
    return jsonify({"updated": True, "config": current}), 200


def _yt_search_videos(query: str, api_key: str, max_results: int = 12) -> list[dict]:
    cache_key = f"vid:{max_results}:{query.lower()}"
    if cache_key in SEARCH_CACHE:
        return SEARCH_CACHE[cache_key]

    resp = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "part": "snippet",
            "type": "video",
            "videoCategoryId": "10",
            "maxResults": max_results,
            "q": query,
            "key": api_key,
        },
        timeout=10,
    )
    if resp.status_code != 200:
        return []

    tracks = []
    for item in resp.json().get("items", []):
        vid = item.get("id", {}).get("videoId")
        snip = item.get("snippet", {})
        if not vid:
            continue
        tracks.append({
            "videoId": vid,
            "title": snip.get("title", ""),
            "artist": snip.get("channelTitle", ""),
            "thumbnail": (
                snip.get("thumbnails", {}).get("high", {}).get("url")
                or snip.get("thumbnails", {}).get("default", {}).get("url")
            ),
            "kind": "song",
        })
    SEARCH_CACHE[cache_key] = tracks
    return tracks


@app.route("/api/youtube_search", methods=["GET"])
def youtube_search():
    raw_q = (request.args.get("q") or "").strip()
    filter_type = (request.args.get("filter") or "all").strip().lower()
    if not raw_q:
        return jsonify({"error": "Missing query parameter 'q'"}), 400

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return jsonify({"error": "Music search service is not configured"}), 500

    # Tailor search query by selected filter (Movie, Hero/Actor, Album, Playlist)
    if filter_type == "movie":
        search_q = f"{raw_q} movie full audio jukebox songs"
    elif filter_type == "hero":
        search_q = f"{raw_q} hit songs jukebox"
    elif filter_type == "album":
        search_q = f"{raw_q} full album audio songs"
    elif filter_type == "playlist":
        # Search YouTube playlists directly
        pl_cache = f"pl:{raw_q.lower()}"
        if pl_cache in SEARCH_CACHE:
            return jsonify({"cached": True, "tracks": SEARCH_CACHE[pl_cache]}), 200
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "type": "playlist",
                "maxResults": 8,
                "q": f"{raw_q} music playlist",
                "key": api_key,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({"error": "Search failed"}), resp.status_code
        playlists = []
        for item in resp.json().get("items", []):
            pid = item.get("id", {}).get("playlistId")
            snip = item.get("snippet", {})
            if not pid:
                continue
            playlists.append({
                "playlistId": pid,
                "title": snip.get("title", ""),
                "artist": snip.get("channelTitle", ""),
                "thumbnail": (
                    snip.get("thumbnails", {}).get("high", {}).get("url")
                    or snip.get("thumbnails", {}).get("default", {}).get("url")
                ),
                "kind": "playlist",
            })
        SEARCH_CACHE[pl_cache] = playlists
        return jsonify({"cached": False, "tracks": playlists}), 200
    else:
        search_q = raw_q

    tracks = _yt_search_videos(search_q, api_key, max_results=12)
    return jsonify({"cached": False, "tracks": tracks}), 200


@app.route("/api/playlist_tracks", methods=["GET"])
def playlist_tracks():
    playlist_id = (request.args.get("id") or "").strip()
    if not playlist_id:
        return jsonify({"error": "Missing playlist ID"}), 400

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return jsonify({"error": "Search service not configured"}), 500

    cache_key = f"pl_items:{playlist_id}"
    if cache_key in SEARCH_CACHE:
        return jsonify({"tracks": SEARCH_CACHE[cache_key]}), 200

    resp = requests.get(
        "https://www.googleapis.com/youtube/v3/playlistItems",
        params={
            "part": "snippet",
            "maxResults": 25,
            "playlistId": playlist_id,
            "key": api_key,
        },
        timeout=10,
    )
    if resp.status_code != 200:
        return jsonify({"error": "Could not load playlist tracks"}), resp.status_code

    tracks = []
    for item in resp.json().get("items", []):
        snip = item.get("snippet", {})
        vid = snip.get("resourceId", {}).get("videoId")
        if not vid:
            continue
        tracks.append({
            "videoId": vid,
            "title": snip.get("title", ""),
            "artist": snip.get("videoOwnerChannelTitle") or snip.get("channelTitle", ""),
            "thumbnail": (
                snip.get("thumbnails", {}).get("high", {}).get("url")
                or snip.get("thumbnails", {}).get("default", {}).get("url")
            ),
            "kind": "song",
        })
    SEARCH_CACHE[cache_key] = tracks
    return jsonify({"tracks": tracks}), 200


@app.route("/api/import_playlist", methods=["POST", "OPTIONS"])
def import_playlist():
    if request.method == "OPTIONS":
        return make_response("", 204)

    data = request.get_json(silent=True) or {}
    raw_url = (data.get("url") or "").strip()
    custom_name = (data.get("name") or "").strip()

    if not raw_url:
        return jsonify({"error": "Please paste a YouTube or Spotify playlist link"}), 400

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return jsonify({"error": "Search service not configured"}), 500

    parsed = urlparse(raw_url)
    host = parsed.netloc.lower()

    # 1. YouTube Playlist URL (?list=PL...)
    if "youtube.com" in host or "youtu.be" in host:
        qs = parse_qs(parsed.query)
        pl_id = (qs.get("list") or [None])[0]
        if not pl_id:
            return jsonify({"error": "Invalid YouTube playlist URL (missing list= ID)"}), 400

        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/playlistItems",
            params={
                "part": "snippet",
                "maxResults": 25,
                "playlistId": pl_id,
                "key": api_key,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({"error": "Could not fetch YouTube playlist (make sure it is Public)"}), 400

        tracks = []
        for item in resp.json().get("items", []):
            snip = item.get("snippet", {})
            vid = snip.get("resourceId", {}).get("videoId")
            if not vid:
                continue
            tracks.append({
                "videoId": vid,
                "title": snip.get("title", ""),
                "artist": snip.get("videoOwnerChannelTitle") or snip.get("channelTitle", ""),
                "thumbnail": (
                    snip.get("thumbnails", {}).get("high", {}).get("url")
                    or snip.get("thumbnails", {}).get("default", {}).get("url")
                ),
            })
        return jsonify({
            "name": custom_name or "Imported YouTube Playlist",
            "tracks": tracks,
        }), 200

    # 2. Spotify Playlist / Album URL (extracts title & track names from public page metadata)
    if "spotify.com" in host:
        try:
            page = requests.get(
                raw_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            html = page.text
            title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            page_title = re.sub(r"\s*\|\s*Spotify.*$", "", title_match.group(1)).strip() if title_match else "Spotify Playlist"

            # Extract track/artist pairs from Spotify embed/open metadata
            track_names = re.findall(r'"name":"([^"]{2,80})"', html)
            seen = set()
            queries = []
            for name in track_names:
                clean = name.strip()
                if clean.lower() in seen or clean.lower() == page_title.lower():
                    continue
                seen.add(clean.lower())
                queries.append(clean)
                if len(queries) >= 12:
                    break

            if not queries:
                queries = [page_title]

            tracks = []
            for q_item in queries[:10]:
                matches = _yt_search_videos(f"{q_item} audio song", api_key, max_results=1)
                if matches:
                    tracks.append(matches[0])

            return jsonify({
                "name": custom_name or page_title,
                "tracks": tracks,
            }), 200
        except Exception:
            return jsonify({"error": "Could not read Spotify playlist link"}), 400

    return jsonify({"error": "Unsupported link. Paste a YouTube or Spotify playlist URL."}), 400
