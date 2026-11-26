from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import re
import secrets
from urllib.parse import parse_qs, urlparse

from flask import Flask, jsonify, make_response, request, send_from_directory
import requests

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="")

SEARCH_CACHE: dict[str, list[dict]] = {}
MEMORY_DB: dict[str, str] = {}

IST = timezone(timedelta(hours=5, minutes=30))

DEFAULT_CONFIG = {
    "version": "v2.3",
    "published_at": "Nov 25, 2026 · 06:35 PM IST",
    "announcement_title": "Welcome to TANANG MUSIC 2.3",
    "announcement_body": "Full playlist imports, 16:9 banners, and background playback enabled.",
    "show_ads": True,
    "slides": [
        {
            "title": "TANANG MUSIC",
            "image": "",
            "ad_url": "",
            "is_ad": False,
        }
    ],
}

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.tokhmi.xyz",
    "https://pipedapi.moomoo.me",
    "https://api.piped.yt",
]

SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


@app.route("/api/stream/<video_id>", methods=["GET"])
def get_audio_stream(video_id):
    vid = (video_id or "").strip()[:32]
    if not vid:
        return jsonify({"error": "Missing video id"}), 400

    for base in PIPED_INSTANCES:
        try:
            resp = requests.get(f"{base}/streams/{vid}", timeout=6)
            if resp.status_code != 200:
                continue
            data = resp.json()
            streams = data.get("audioStreams") or []
            m4a = [s for s in streams if "mp4" in (s.get("mimeType") or "")]
            chosen = sorted(m4a or streams, key=lambda x: x.get("bitrate", 0), reverse=True)
            if chosen and chosen[0].get("url"):
                return jsonify({
                    "audio_url": chosen[0]["url"],
                    "title": data.get("title", ""),
                    "thumbnail": data.get("thumbnailUrl", ""),
                }), 200
        except Exception:
            continue

    return jsonify({"error": "No stream available"}), 502


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
        if kv_get(user_key):
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
            "recent_queries": [],
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
        "recent_queries": data.get("recent_queries", [])[:10],
    }
    kv_set(f"tanang:lib:{username}", library)
    return jsonify({"saved": True}), 200


@app.route("/api/admin_verify", methods=["POST", "OPTIONS"])
def admin_verify():
    if request.method == "OPTIONS":
        return make_response("", 204)
    data = request.get_json(silent=True) or {}
    admin_key = (data.get("admin_key") or "").strip()
    expected = os.environ.get("AUTH_SECRET", "")
    if not expected or not hmac.compare_digest(admin_key, expected):
        return jsonify({"authorized": False, "error": "Invalid Admin Key"}), 403
    return jsonify({"authorized": True}), 200


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
    now_str = datetime.now(IST).strftime("%b %d, %Y · %I:%M %p IST")

    current["version"] = (data.get("version") or current.get("version", "v2.3")).strip()
    current["published_at"] = now_str
    current["announcement_title"] = (data.get("announcement_title") or current.get("announcement_title", "")).strip()
    current["announcement_body"] = (data.get("announcement_body") or current.get("announcement_body", "")).strip()
    current["show_ads"] = bool(data.get("show_ads", True))

    if isinstance(data.get("slides"), list):
        clean_slides = []
        for s in data["slides"]:
            if not isinstance(s, dict):
                continue
            image = (s.get("image") or "").strip()
            title = (s.get("title") or "").strip()
            ad_url = (s.get("ad_url") or "").strip()
            if not image and not title:
                continue
            clean_slides.append({
                "title": title,
                "image": image,
                "ad_url": ad_url,
                "is_ad": bool(s.get("is_ad", True)),
            })
        current["slides"] = clean_slides

    kv_set("tanang:app_config", current)
    return jsonify({"updated": True, "config": current}), 200


def _yt_search_videos(query: str, api_key: str, max_results: int = 12) -> list[dict]:
    cache_key = f"vid:{max_results}:{query.lower()}"
    if cache_key in SEARCH_CACHE:
        return SEARCH_CACHE[cache_key]

    try:
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
            timeout=8,
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
                    or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                ),
                "kind": "song",
            })
        if tracks:
            SEARCH_CACHE[cache_key] = tracks
        return tracks
    except Exception:
        return []


def _yt_search_playlists(query: str, api_key: str, max_results: int = 8) -> list[dict]:
    pl_cache = f"pl:{max_results}:{query.lower()}"
    if pl_cache in SEARCH_CACHE:
        return SEARCH_CACHE[pl_cache]

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "type": "playlist",
                "maxResults": max_results,
                "q": f"{query} music playlist",
                "key": api_key,
            },
            timeout=8,
        )
        if resp.status_code != 200:
            return []

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
        if playlists:
            SEARCH_CACHE[pl_cache] = playlists
        return playlists
    except Exception:
        return []


def _scrape_youtube_videos(query: str, max_results: int = 20) -> list[dict]:
    tracks: list[dict] = []
    try:
        resp = requests.get(
            "https://www.youtube.com/results",
            params={"search_query": query, "hl": "en"},
            headers=SEARCH_HEADERS,
            timeout=7,
        )
        if resp.status_code == 200:
            match = re.search(r"var ytInitialData = (\{.*?\});</script>", resp.text)
            if not match:
                match = re.search(r"ytInitialData\s*=\s*(\{.*?\});", resp.text)
            if match:
                data = json.loads(match.group(1))
                stack = [data]
                seen_ids = set()
                while stack and len(tracks) < max_results:
                    node = stack.pop()
                    if isinstance(node, dict):
                        if "videoRenderer" in node:
                            vr = node["videoRenderer"]
                            vid = vr.get("videoId", "")
                            if len(vid) == 11 and vid not in seen_ids:
                                seen_ids.add(vid)
                                title_runs = (vr.get("title") or {}).get("runs") or []
                                title = "".join(r.get("text", "") for r in title_runs).strip()
                                owner_runs = (vr.get("ownerText") or {}).get("runs") or []
                                artist = "".join(r.get("text", "") for r in owner_runs).strip() or "YouTube"
                                thumbs = ((vr.get("thumbnail") or {}).get("thumbnails")) or []
                                thumb = (
                                    thumbs[-1].get("url")
                                    if thumbs
                                    else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                                )
                                if title:
                                    tracks.append({
                                        "kind": "song",
                                        "videoId": vid,
                                        "title": title,
                                        "artist": artist,
                                        "thumbnail": thumb,
                                    })
                        for v in node.values():
                            if isinstance(v, (dict, list)):
                                stack.append(v)
                    elif isinstance(node, list):
                        for item in node:
                            if isinstance(item, (dict, list)):
                                stack.append(item)
    except Exception:
        pass

    if not tracks:
        for base in PIPED_INSTANCES:
            try:
                r = requests.get(f"{base}/search", params={"q": query, "filter": "videos"}, timeout=5)
                if r.status_code == 200:
                    for item in (r.json().get("items") or [])[:max_results]:
                        url = item.get("url") or ""
                        vid = url.split("v=")[-1].split("&")[0]
                        if len(vid) == 11 and item.get("title"):
                            tracks.append({
                                "kind": "song",
                                "videoId": vid,
                                "title": item.get("title"),
                                "artist": item.get("uploaderName") or "YouTube",
                                "thumbnail": item.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                            })
                    if tracks:
                        break
            except Exception:
                continue

    return tracks


def _fetch_full_youtube_playlist(playlist_id: str, api_key: str, max_tracks: int = 150) -> tuple[str, list[dict]]:
    pl_title = ""
    try:
        meta_resp = requests.get(
            "https://www.googleapis.com/youtube/v3/playlists",
            params={"part": "snippet", "id": playlist_id, "key": api_key},
            timeout=8,
        )
        if meta_resp.status_code == 200:
            items = meta_resp.json().get("items", [])
            if items:
                pl_title = (items[0].get("snippet", {}).get("title") or "").strip()
    except Exception:
        pass

    tracks: list[dict] = []
    page_token = None
    while len(tracks) < max_tracks:
        params = {
            "part": "snippet",
            "maxResults": 50,
            "playlistId": playlist_id,
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/playlistItems",
            params=params,
            timeout=10,
        )
        if resp.status_code != 200:
            break

        payload = resp.json()
        for item in payload.get("items", []):
            snip = item.get("snippet", {})
            vid = snip.get("resourceId", {}).get("videoId")
            title = snip.get("title", "")
            if not vid or title in ("Deleted video", "Private video"):
                continue
            tracks.append({
                "videoId": vid,
                "title": title,
                "artist": snip.get("videoOwnerChannelTitle") or snip.get("channelTitle", ""),
                "thumbnail": (
                    snip.get("thumbnails", {}).get("high", {}).get("url")
                    or snip.get("thumbnails", {}).get("default", {}).get("url")
                ),
                "kind": "song",
            })

        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return pl_title or "YouTube Playlist", tracks


@app.route("/api/youtube_search", methods=["GET"])
def youtube_search():
    query = (request.args.get("q") or "").strip()
    search_filter = (request.args.get("filter") or "all").strip().lower()
    if not query:
        return jsonify({"tracks": []}), 200

    effective_query = query
    if search_filter == "movie":
        effective_query = f"{query} movie song"
    elif search_filter == "hero":
        effective_query = f"{query} songs"
    elif search_filter == "album":
        effective_query = f"{query} full album songs"

    api_key = os.environ.get("YOUTUBE_API_KEY")
    tracks: list[dict] = []

    if search_filter == "playlist":
        if api_key:
            tracks = _yt_search_playlists(query, api_key, max_results=12)
        if not tracks:
            tracks = _scrape_youtube_videos(f"{query} playlist", max_results=15)
        return jsonify({"tracks": tracks}), 200

    if api_key:
        tracks = _yt_search_videos(effective_query, api_key, max_results=15)

    if not tracks:
        tracks = _scrape_youtube_videos(effective_query, max_results=20)

    return jsonify({"tracks": tracks}), 200


@app.route("/api/recommendations", methods=["GET"])
def recommendations():
    seed = (request.args.get("q") or "Telugu hit songs").strip()
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return jsonify({"playlists": []}), 200
    playlists = _yt_search_playlists(seed, api_key, max_results=8)
    return jsonify({"playlists": playlists}), 200


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

    _, tracks = _fetch_full_youtube_playlist(playlist_id, api_key, max_tracks=150)
    if not tracks:
        return jsonify({"error": "Could not load playlist tracks"}), 400

    SEARCH_CACHE[cache_key] = tracks
    return jsonify({"tracks": tracks}), 200


def _extract_spotify_tracks(spotify_url: str) -> tuple[str, list[str]]:
    parsed = urlparse(spotify_url)
    match = re.search(r"/(playlist|album)/([a-zA-Z0-9]+)", parsed.path)
    if not match:
        raise ValueError("Invalid Spotify playlist or album URL")

    kind, item_id = match.group(1), match.group(2)
    embed_url = f"https://open.spotify.com/embed/{kind}/{item_id}"

    resp = requests.get(embed_url, headers=SEARCH_HEADERS, timeout=10)
    html = resp.text

    playlist_title = ""
    queries: list[str] = []

    next_data_match = re.search(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if next_data_match:
        try:
            payload = json.loads(next_data_match.group(1))
            entity = (
                payload.get("props", {})
                .get("pageProps", {})
                .get("state", {})
                .get("data", {})
                .get("entity", {})
            )
            playlist_title = (entity.get("name") or entity.get("title") or "").strip()

            track_list = entity.get("trackList") or []
            for entry in track_list:
                t_title = (entry.get("title") or "").strip()
                t_sub = (entry.get("subtitle") or "").strip()
                if t_title:
                    queries.append(f"{t_title} {t_sub}".strip())
        except Exception:
            pass

    if not playlist_title:
        try:
            oembed = requests.get(
                "https://open.spotify.com/oembed",
                params={"url": f"https://open.spotify.com/{kind}/{item_id}"},
                timeout=6,
            )
            if oembed.status_code == 200:
                playlist_title = (oembed.json().get("title") or "").strip()
        except Exception:
            pass

    if not queries:
        pair_matches = re.findall(
            r'"title":"([^"]{2,100})","subtitle":"([^"]{1,100})"',
            html,
        )
        for t_title, t_sub in pair_matches:
            clean_title = t_title.encode("utf-8").decode("unicode_escape", errors="ignore").strip()
            clean_sub = t_sub.encode("utf-8").decode("unicode_escape", errors="ignore").strip()
            if clean_title and clean_title.lower() != playlist_title.lower():
                queries.append(f"{clean_title} {clean_sub}".strip())

    seen = set()
    unique_queries = []
    for q in queries:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            unique_queries.append(q)

    return playlist_title or f"Spotify {kind.title()}", unique_queries


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
        return jsonify({"error": "Music search service is not configured"}), 500

    parsed = urlparse(raw_url)
    host = parsed.netloc.lower()

    if "youtube.com" in host or "youtu.be" in host:
        qs = parse_qs(parsed.query)
        pl_id = (qs.get("list") or [None])[0]
        if not pl_id:
            return jsonify({"error": "Invalid YouTube playlist URL (missing list= ID)"}), 400

        yt_title, tracks = _fetch_full_youtube_playlist(pl_id, api_key, max_tracks=150)
        if not tracks:
            return jsonify({"error": "Could not fetch YouTube playlist (make sure it is Public)"}), 400

        return jsonify({
            "name": custom_name or yt_title,
            "tracks": tracks,
        }), 200

    if "spotify.com" in host:
        try:
            sp_title, track_queries = _extract_spotify_tracks(raw_url)
            if not track_queries:
                return jsonify({"error": "Could not read songs from that Spotify link (ensure playlist is Public)"}), 400

            tracks = []
            for t_query in track_queries[:80]:
                matches = _yt_search_videos(f"{t_query} audio song", api_key, max_results=1)
                if matches:
                    tracks.append(matches[0])

            return jsonify({
                "name": custom_name or sp_title,
                "tracks": tracks,
            }), 200
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception:
            return jsonify({"error": "Failed to import Spotify playlist"}), 400

    return jsonify({"error": "Unsupported link. Paste a YouTube or Spotify playlist URL."}), 400
