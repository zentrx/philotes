import json
import sys
from pathlib import Path
from philotes.config import CONFIG_DIR
from philotes.account_manager import AccountManager

SETTINGS_FILE = CONFIG_DIR / "settings.json"

DEFAULT_TAB_ORDER = ["chat", "msgs", "tasks", "keep", "wordle"]
ALL_VALID_TABS = ["chat", "msgs", "tasks", "keep", "wordle"]

SERVICE_POOLS = {
    "google": {
        "title": "Google Service Logins",
        "tabs": ["chat", "msgs", "tasks", "keep"],
    },
    "nytimes": {
        "title": "New York Times Service Logins",
        "tabs": ["wordle"],
    },
}

TAB_METADATA = {
    "chat": {
        "id": "chat",
        "name": "Google Chat",
        "short_name": "Chat",
        "provider": "google",
    },
    "msgs": {
        "id": "msgs",
        "name": "Google Messages",
        "short_name": "Messages",
        "provider": "google",
    },
    "tasks": {
        "id": "tasks",
        "name": "Google Tasks",
        "short_name": "Tasks",
        "provider": "google",
    },
    "keep": {
        "id": "keep",
        "name": "Google Keep",
        "short_name": "Keep",
        "provider": "google",
    },
    "wordle": {
        "id": "wordle",
        "name": "Wordle & NYT Games",
        "short_name": "Wordle",
        "provider": "nytimes",
    },
}


class SettingsManager:
    """
    Central configuration and settings hub for Philotes.

    Coordinates:
      1. Application-wide preferences (settings.json), including top bar tab ordering.
      2. Service Pool / Auth Card identity management (accounts.json) via self.accounts.
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._settings = self._load_settings()

    @property
    def accounts(self) -> AccountManager:
        """Access the AccountManager sub-component for service pool & identity operations."""
        return AccountManager.get_instance()

    def _load_settings(self) -> dict:
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                sys.stderr.write(f"[Philotes SettingsManager] Error loading settings.json: {e}\n")
        return {}

    def _save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            sys.stderr.write(f"[Philotes SettingsManager] Error saving settings.json: {e}\n")

    def get_tab_order(self) -> list:
        """
        Returns the sanitized and validated tab order.
        Guarantees all known valid tabs are present, filters unknown tabs,
        and avoids duplicate entries. Falls back to DEFAULT_TAB_ORDER if empty.
        """
        raw_order = self._settings.get("tab_order")
        if not isinstance(raw_order, list):
            return list(DEFAULT_TAB_ORDER)

        validated = []
        for tab_id in raw_order:
            if tab_id in ALL_VALID_TABS and tab_id not in validated:
                validated.append(tab_id)

        # Append any valid tabs that were missing
        for tab_id in DEFAULT_TAB_ORDER:
            if tab_id not in validated:
                validated.append(tab_id)

        return validated

    def set_tab_order(self, order: list):
        """
        Validates and saves the tab order to settings.json.
        """
        validated = []
        for tab_id in order:
            if tab_id in ALL_VALID_TABS and tab_id not in validated:
                validated.append(tab_id)

        for tab_id in DEFAULT_TAB_ORDER:
            if tab_id not in validated:
                validated.append(tab_id)

        self._settings["tab_order"] = validated
        self._save_settings()

    def reset_tab_order(self) -> list:
        """
        Resets tab order to DEFAULT_TAB_ORDER and writes to disk.
        """
        self._settings["tab_order"] = list(DEFAULT_TAB_ORDER)
        self._save_settings()
        return list(DEFAULT_TAB_ORDER)

    def get_enabled_tabs(self) -> list:
        """
        Returns the list of currently enabled tab IDs.
        Defaults to all valid tabs if not explicitly configured in settings.json.
        """
        raw = self._settings.get("enabled_tabs")
        if raw is None:
            return list(ALL_VALID_TABS)
        if isinstance(raw, list):
            return [t for t in raw if t in ALL_VALID_TABS]
        return list(ALL_VALID_TABS)

    def is_tab_enabled(self, tab_id: str) -> bool:
        """Check whether a specific tab is currently enabled."""
        return tab_id in self.get_enabled_tabs()

    def set_tab_enabled(self, tab_id: str, enabled: bool):
        """
        Enables or disables a specific tab and persists to settings.json.
        """
        if tab_id not in ALL_VALID_TABS:
            return
        enabled_tabs = self.get_enabled_tabs()
        if enabled and tab_id not in enabled_tabs:
            enabled_tabs.append(tab_id)
        elif not enabled and tab_id in enabled_tabs:
            enabled_tabs.remove(tab_id)
        self._settings["enabled_tabs"] = enabled_tabs
        self._save_settings()

    def get_system_double_click_time(self) -> int:
        """
        Reads the system mouse double-click interval (in milliseconds).
        Resolves via:
          1. D-Bus XDG Desktop Portal (org.freedesktop.portal.Settings)
          2. GSettings (org.gnome.desktop.peripherals.mouse:double-click)
          3. Gtk.Settings (gtk-double-click-time)
        Synchronizes resolved interval to Gtk.Settings:gtk-double-click-time.
        """
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk, Gio, GLib

        double_click_time = None

        # 1. Query D-Bus XDG Desktop Portal Settings
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            reply = bus.call_sync(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.Settings",
                "Read",
                GLib.Variant("(ss)", ("org.gnome.desktop.peripherals.mouse", "double-click")),
                None,
                Gio.DBusCallFlags.NONE,
                500,
                None,
            )
            if reply:
                val = reply.unpack()[0]
                if isinstance(val, int) and val > 0:
                    double_click_time = val
        except Exception:
            pass

        # 2. Query GSettings
        if double_click_time is None:
            try:
                source = Gio.SettingsSchemaSource.get_default()
                if source and source.lookup("org.gnome.desktop.peripherals.mouse", False):
                    gsettings = Gio.Settings(schema="org.gnome.desktop.peripherals.mouse")
                    val = gsettings.get_int("double-click")
                    if val > 0:
                        double_click_time = val
            except Exception:
                pass

        # 3. Query Gtk.Settings
        if double_click_time is None:
            try:
                gtk_settings = Gtk.Settings.get_default()
                if gtk_settings:
                    val = gtk_settings.get_property("gtk-double-click-time")
                    if val and val > 0:
                        double_click_time = val
            except Exception:
                pass

        if double_click_time is None or double_click_time <= 0:
            double_click_time = 400

        # Synchronize to Gtk.Settings
        try:
            gtk_settings = Gtk.Settings.get_default()
            if gtk_settings:
                gtk_settings.set_property("gtk-double-click-time", double_click_time)
        except Exception:
            pass

        return double_click_time
