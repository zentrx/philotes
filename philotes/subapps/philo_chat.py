import sys
import os
import re
import json
import urllib.parse
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit, GLib

from philotes.process_utils import set_process_name
from philotes.config import SUBAPP_CHAT_NAME
from philotes.session_manager import SessionManager
from philotes.clipboard_bridge import enable_image_paste

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


# =============================================================================
# PhiloChatApp - Standardized Sub-Application
# =============================================================================
class PhiloChatApp:
    # -------------------------------------------------------------------------
    # Section 1: Subapp Metadata & Configuration Hooks
    # -------------------------------------------------------------------------
    APP_ID = "chat"
    SUBAPP_NAME = SUBAPP_CHAT_NAME
    PROVIDER = "google"
    DEFAULT_URL = "https://chat.google.com/"
    DOM_POLL_INTERVAL_SEC = 0  # Google Chat uses title notifications (no timer needed)

    # -------------------------------------------------------------------------
    # Section 2: Standardized Lifecycle & WebKit Initialization (Boilerplate)
    # -------------------------------------------------------------------------
    def __init__(self, ipc_write_fd=None, profile_id="default", username=None):
        self._init_state(ipc_write_fd, profile_id, username)
        self._init_network_session()
        self._init_webkit_settings()
        self._init_webview()
        self._init_signals()
        self._init_dom_polling()
        self.load_initial_url()

    def _init_state(self, ipc_write_fd, profile_id, username):
        set_process_name(self.SUBAPP_NAME)
        self.ipc_write_fd = ipc_write_fd
        self.profile_id = profile_id
        self.username = username
        self.unread_count = 0
        self.selected_title = None
        print(f"{self.SUBAPP_NAME}: initializing (profile={profile_id}, user={username})", flush=True)

    def _init_network_session(self):
        self.network_session = SessionManager.get_instance().get_network_session(
            provider=self.PROVIDER,
            profile_id=self.profile_id,
        )

    def _init_webkit_settings(self):
        self.settings = WebKit.Settings()
        self.settings.set_user_agent(USER_AGENT)
        self.settings.set_enable_javascript(True)
        self.settings.set_enable_developer_extras(True)
        self.settings.set_enable_page_cache(True)
        self.settings.set_enable_html5_local_storage(True)
        self.settings.set_enable_smooth_scrolling(True)
        self.settings.set_enable_webrtc(True)
        self.settings.set_enable_media_stream(True)
        self.settings.set_enable_encrypted_media(True)
        self.settings.set_hardware_acceleration_policy(WebKit.HardwareAccelerationPolicy.ALWAYS)

    def _init_webview(self):
        self.web_view = WebKit.WebView(network_session=self.network_session)
        self.web_view.set_settings(self.settings)
        enable_image_paste(self.web_view)

        try:
            gi.require_version("Gdk", "4.0")
            from gi.repository import Gdk
            rgba = Gdk.RGBA()
            rgba.parse("#1a1b26")
            self.web_view.set_background_color(rgba)
        except Exception as e:
            print(f"{self.SUBAPP_NAME}: failed to set background color: {e}", flush=True)

    def _init_signals(self):
        self.web_view.connect("create", self._on_create_window)
        self.web_view.connect("notify::title", self._on_title_changed)
        self.web_view.connect("web-process-terminated", self._on_web_process_terminated)

    def _init_dom_polling(self):
        self.poll_timer_id = None
        if self.DOM_POLL_INTERVAL_SEC > 0:
            self.poll_timer_id = GLib.timeout_add_seconds(self.DOM_POLL_INTERVAL_SEC, self._on_poll_timer)

    def _on_poll_timer(self):
        return self._poll_dom()

    def load_initial_url(self):
        target_url = self._get_target_url()
        print(f"{self.SUBAPP_NAME}: loading {target_url}", flush=True)
        self.web_view.load_uri(target_url)

    def load_google_chat(self):
        """Backward-compatibility alias for load_initial_url."""
        self.load_initial_url()

    def reload(self):
        if hasattr(self, "web_view") and self.web_view:
            self.load_initial_url()

    def cleanup(self):
        if getattr(self, "poll_timer_id", None):
            try:
                GLib.source_remove(self.poll_timer_id)
            except Exception:
                pass
            self.poll_timer_id = None

        if hasattr(self, "web_view") and self.web_view:
            try:
                self.web_view.stop_loading()
                self.web_view.load_uri("about:blank")
            except Exception:
                pass
            self.web_view = None

        if self.ipc_write_fd is not None:
            try:
                os.close(self.ipc_write_fd)
            except Exception:
                pass
            self.ipc_write_fd = None

    def get_widget(self):
        return self.web_view

    # -------------------------------------------------------------------------
    # Section 3: Standardized Event Handlers & IPC (Boilerplate)
    # -------------------------------------------------------------------------
    def _on_web_process_terminated(self, web_view, reason):
        print(f"{self.SUBAPP_NAME}: web process crashed (reason={reason}), reloading", flush=True)
        web_view.reload()

    def _on_create_window(self, web_view, navigation_action):
        request = navigation_action.get_request()
        uri = request.get_uri() if request else None
        if uri:
            print(f"{self.SUBAPP_NAME}: redirecting popup to main view ({uri})", flush=True)
            web_view.load_uri(uri)
        return None

    def _send_ipc_msg(self, msg_dict):
        if self.ipc_write_fd is not None:
            try:
                line = json.dumps(msg_dict) + "\n"
                os.write(self.ipc_write_fd, line.encode("utf-8"))
            except Exception as e:
                print(f"{self.SUBAPP_NAME}: IPC write error: {e}", flush=True)

    def _broadcast_status(self):
        self._send_ipc_msg({
            "type": "status_update",
            "app": self.APP_ID,
            "count": self.unread_count,
            "title": self.selected_title,
        })

    # -------------------------------------------------------------------------
    # Section 4: Application-Specific Logic & Custom Hooks
    # -------------------------------------------------------------------------
    def _get_target_url(self) -> str:
        if self.username:
            return f"https://accounts.google.com/ServiceLogin?service=mail&continue=https://chat.google.com/&Email={urllib.parse.quote(self.username)}"
        return "https://accounts.google.com/ServiceLogin?service=mail&continue=https://chat.google.com/"

    def _parse_selected_title(self, raw_title: str) -> str | None:
        if not raw_title:
            return None
        clean = re.sub(r"^\(\d+\)\s*", "", raw_title).strip()
        if clean.endswith(" - Google Chat"):
            clean = clean[:-14].strip()
        elif clean.startswith("Google Chat - "):
            clean = clean[14:].strip()
        elif clean.endswith(" - Chat"):
            clean = clean[:-7].strip()
        elif clean.startswith("Chat - "):
            clean = clean[7:].strip()

        if clean in ("Google Chat", "Google", "Chat", "Sign in - Google Accounts", "Accounts"):
            return None
        return clean if clean else None

    def _on_title_changed(self, web_view, param):
        title = web_view.get_title()
        if not title:
            return

        match = re.search(r"^\((\d+)\)", title)
        new_count = int(match.group(1)) if match else 0
        new_title = self._parse_selected_title(title)

        if new_count != self.unread_count or new_title != self.selected_title:
            self.unread_count = new_count
            self.selected_title = new_title
            print(f"{self.SUBAPP_NAME}: status updated (unread={self.unread_count}, title='{self.selected_title}')", flush=True)
            self._broadcast_status()

    def _poll_dom(self) -> bool:
        """Hook for timer-based DOM polling. Chat relies purely on title notifications."""
        return True


# -----------------------------------------------------------------------------
# Section 5: Standalone Subprocess Runner (Boilerplate)
# -----------------------------------------------------------------------------
def run_philo_chat_subprocess(ipc_write_fd):
    set_process_name(SUBAPP_CHAT_NAME)
    app = Gtk.Application(application_id="com.philotes.philo_chat")

    def on_activate(gtk_app):
        philo_chat = PhiloChatApp(ipc_write_fd=ipc_write_fd)
        window = Gtk.ApplicationWindow(application=gtk_app, title=SUBAPP_CHAT_NAME)
        window.set_child(philo_chat.get_widget())
        window.set_default_size(900, 700)
        window.present()

    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    run_philo_chat_subprocess(None)
