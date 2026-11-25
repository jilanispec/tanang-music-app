from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import parse_qs, urlparse
import requests

SEARCH_CACHE: dict[str, list[dict]] = {}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        query = (params.get("q") or [""])[0].strip().lower()

        if not query:
            self._send_json(400, {"error": "Missing query parameter 'q'"})
            return

        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            self._send_json(500, {"error": "YOUTUBE_API_KEY is not configured"})
            return

        if query in SEARCH_CACHE:
            self._send_json(200, {"cached": True, "tracks": SEARCH_CACHE[query]})
            return

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
            self._send_json(resp.status_code, {"error": "YouTube API request failed"})
            return

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
        self._send_json(200, {"cached": False, "tracks": tracks})

    def _send_json(self, status: int, payload: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))
