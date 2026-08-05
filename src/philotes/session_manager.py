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

    def _resolve_provider_profiles(self, provider: str):
        prefix = f"{provider}-"
        default_name = f"{provider}-default"
        
        profiles = []
        for entry in PROFILES_BASE_DIR.iterdir():
            if entry.is_dir() and not entry.is_symlink():
                if entry.name.startswith(prefix) and entry.name != default_name:
                    try:
                        ctime = entry.stat().st_ctime
                    except Exception:
                        ctime = 0
                    profiles.append((ctime, entry))

        profiles.sort(key=lambda item: item[0])
        return [entry for _, entry in profiles]

    def ensure_default_symlink(self, provider: str) -> Path:
        symlink_path = PROFILES_BASE_DIR / f"{provider}-default"
        
        # Migrate plain legacy directory to provider-user1 if needed
        if symlink_path.exists() and not symlink_path.is_symlink():
            migrated_dir = PROFILES_BASE_DIR / f"{provider}-user1"
            if not migrated_dir.exists():
                symlink_path.rename(migrated_dir)

        # Remove broken symlink if target directory was deleted
        if symlink_path.is_symlink():
            try:
                target = symlink_path.resolve()
                if not target.exists():
                    symlink_path.unlink()
            except Exception:
                symlink_path.unlink()

        profiles = self._resolve_provider_profiles(provider)

        if not profiles:
            initial_profile = PROFILES_BASE_DIR / f"{provider}-user1"
            initial_profile.mkdir(parents=True, exist_ok=True)
            profiles = [initial_profile]

        oldest_profile = profiles[0]

        if not symlink_path.exists() and not symlink_path.is_symlink():
            symlink_path.symlink_to(oldest_profile.name)
        elif symlink_path.is_symlink():
            if symlink_path.resolve() != oldest_profile.resolve():
                symlink_path.unlink()
                symlink_path.symlink_to(oldest_profile.name)

        return symlink_path

    def get_network_session(self, provider: str = "google", profile_id: str = "default") -> WebKit.NetworkSession:
        if profile_id == "default":
            target_path = self.ensure_default_symlink(provider)
            key = f"{provider}-default"
        else:
            profile_dir = PROFILES_BASE_DIR / f"{provider}-{profile_id}"
            profile_dir.mkdir(parents=True, exist_ok=True)
            self.ensure_default_symlink(provider)
            target_path = profile_dir
            key = f"{provider}-{profile_id}"

        if key in self._sessions:
            return self._sessions[key]

        data_dir = target_path / "data"
        cache_dir = target_path / "cache"

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
