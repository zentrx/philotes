import os
import gi
from pathlib import Path

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit
from philotes.config import CONFIG_DIR

PROFILES_BASE_DIR = CONFIG_DIR / "profiles"
PROFILES_BASE_DIR.mkdir(parents=True, exist_ok=True)


class SessionManager:
    _instance = None
    _sessions = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_network_session(self, provider: str = "google", profile_id: str = "default") -> WebKit.NetworkSession:
        if profile_id.startswith(f"{provider}-"):
            key = profile_id
        else:
            key = f"{provider}-{profile_id}"

        if key in self._sessions:
            return self._sessions[key]

        profile_dir = PROFILES_BASE_DIR / key
        data_dir = profile_dir / "data"
        cache_dir = profile_dir / "cache"

        data_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

        network_session = WebKit.NetworkSession.new(
            str(data_dir),
            str(cache_dir)
        )

        cookie_manager = network_session.get_cookie_manager()
        cookie_db_path = data_dir / "cookies.sqlite"
        cookie_manager.set_persistent_storage(
            str(cookie_db_path),
            WebKit.CookiePersistentStorage.SQLITE,
        )
        cookie_manager.set_accept_policy(WebKit.CookieAcceptPolicy.ALWAYS)

        self._sessions[key] = network_session
        return network_session
