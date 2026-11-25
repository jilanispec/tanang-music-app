import json
import os
import sys
from unittest.mock import MagicMock, patch

# Ensure project root is importable when running inside Pydroid
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.auth import hash_password, sign_session_token, verify_password
from api.youtube_search import SEARCH_CACHE, handler as yt_handler


def test_password_and_hash_security():
    print("1. Testing scrypt password/hash security...")
    secret_a = "TanangSecret#2026"
    secret_b = "WrongSecret#2026"

    hash_1 = hash_password(secret_a)
    hash_2 = hash_password(secret_a)

    assert hash_1.startswith("scrypt$"), "Hash should use scrypt format"
    assert hash_1 != hash_2, "Random salt must generate unique hashes for the same secret"
    assert verify_password(secret_a, hash_1) is True, "Valid secret must pass verification"
    assert verify_password(secret_b, hash_1) is False, "Wrong secret must fail verification"
    assert verify_password("", hash_1) is False, "Empty secret must fail verification"
    assert verify_password(secret_a, "corrupted$hash$value") is False, "Malformed hash must fail safely"

    try:
        hash_password("short")
        assert False, "Secrets shorter than 8 chars should raise ValueError"
    except ValueError:
        pass

    token = sign_session_token("jilan", "super-secret-key")
    parts = token.split(":")
    assert len(parts) == 3 and parts[0] == "jilan", "Session token must be user:nonce:signature"
    print("   PASS: Password hashing, verification, and session signing work.")


def test_youtube_search_cache_without_real_quota():
    print("2. Testing YouTube search caching & response formatting (mocked)...")
    SEARCH_CACHE.clear()

    fake_yt_response = MagicMock()
    fake_yt_response.status_code = 200
    fake_yt_response.json.return_value = {
        "items": [
            {
                "id": {"videoId": "dQw4w9WgXcQ"},
                "snippet": {
                    "title": "Sample Track - Official Audio",
                    "channelTitle": "Sample Artist",
                    "thumbnails": {
                        "high": {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"}
                    },
                },
            }
        ]
    }

    written_chunks = []

    class FakeRequest:
        def makefile(self, *args, **kwargs):
            return None

    def invoke_search(query_str):
        written_chunks.clear()
        inst = yt_handler.__new__(yt_handler)
        inst.path = f"/api/youtube_search?q={query_str}"
        inst.headers = {}
        inst.send_response = lambda code: None
        inst.send_header = lambda k, v: None
        inst.end_headers = lambda: None

        class DummyWfile:
            def write(self, data):
                written_chunks.append(data)

        inst.wfile = DummyWfile()
        inst.do_GET()
        return json.loads(b"".join(written_chunks).decode("utf-8"))

    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-key-only"}), patch(
        "api.youtube_search.requests.get", return_value=fake_yt_response
    ) as mock_get:
        first_call = invoke_search("sample%20song")
        second_call = invoke_search("sample%20song")

        assert first_call["cached"] is False
        assert second_call["cached"] is True, "Second identical search should hit cache"
        assert mock_get.call_count == 1, "Cached search should not make a second external call"
        assert first_call["tracks"][0]["videoId"] == "dQw4w9WgXcQ"
        assert "thumbnail" in first_call["tracks"][0]

    SEARCH_CACHE.clear()
    print("   PASS: YouTube search payload & quota-saving cache work.")


def test_live_vercel_endpoints_optional():
    """
    Optional live test: set LIVE_BASE_URL environment variable in Pydroid
    e.g. LIVE_BASE_URL=https://your-app.vercel.app
    to test /api/health and /api/youtube_search on your deployed app.
    """
    base_url = os.environ.get("LIVE_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        print("3. Skipping live endpoint test (set LIVE_BASE_URL to test deployed Vercel URL).")
        return

    import requests

    print(f"3. Testing live deployment at {base_url}...")
    r_health = requests.get(f"{base_url}/api/health", timeout=15)
    print("   /api/health status:", r_health.status_code, r_health.text)

    r_auth = requests.post(
        f"{base_url}/api/auth",
        json={"action": "register", "username": "testuser", "password": "TestPassword#123"},
        timeout=15,
    )
    print("   /api/auth register status:", r_auth.status_code, r_auth.text)


if __name__ == "__main__":
    test_password_and_hash_security()
    test_youtube_search_cache_without_real_quota()
    test_live_vercel_endpoints_optional()
    print("\nALL LOCAL TESTS COMPLETED SUCCESSFULLY.")
