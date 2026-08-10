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

GOOGLE_CHAT_URL = "https://chat.google.com/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

class PhiloChatApp:
    def __init__(self, ipc_write_fd=None, profile_id="default", username=None):
        set_process_name(SUBAPP_CHAT_NAME)
        self.ipc_write_fd = ipc_write_fd
        self.profile_id = profile_id
        self.username = username
        self.unread_count = 0
        self.selected_title = None

        print(f"philo-chat: initializing (profile={profile_id}, user={username})", flush=True)

        self.network_session = SessionManager.get_instance().get_network_session(
            provider="google",
            profile_id=profile_id,
        )

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
            print("philo-chat: ----------------------------------------", flush=True)
            print(f"philo-chat: failed to set background color: {e}", flush=True)
            print("philo-chat: ----------------------------------------", flush=True)

        self.web_view.connect("create", self._on_create_window)
        self.web_view.connect("notify::title", self._on_title_changed)
        self.web_view.connect("web-process-terminated", self._on_web_process_terminated)

        self.load_google_chat()

    def _on_web_process_terminated(self, web_view, reason):
        print("philo-chat: ----------------------------------------", flush=True)
        print(f"philo-chat: web process crashed (reason={reason}), reloading", flush=True)
        print("philo-chat: ----------------------------------------", flush=True)
        web_view.reload()

    def load_google_chat(self):
        if self.username:
            target_url = f"https://accounts.google.com/ServiceLogin?service=mail&continue=https://chat.google.com/&Email={urllib.parse.quote(self.username)}"
        else:
            target_url = "https://accounts.google.com/ServiceLogin?service=mail&continue=https://chat.google.com/"
        print(f"philo-chat: loading {target_url}", flush=True)
        self.web_view.load_uri(target_url)

    def _on_create_window(self, web_view, navigation_action):
        request = navigation_action.get_request()
        uri = request.get_uri() if request else None
        if uri:
            print(f"philo-chat: redirecting popup to main view ({uri})", flush=True)
            web_view.load_uri(uri)
        return None

    def _parse_selected_title(self, raw_title):
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
            print(f"philo-chat: status updated (unread={self.unread_count}, title='{self.selected_title}')", flush=True)
            self._send_ipc_msg({
                "type": "status_update",
                "app": "chat",
                "count": self.unread_count,
                "title": self.selected_title,
            })

    def _send_ipc_msg(self, msg_dict):
        if self.ipc_write_fd is not None:
            try:
                line = json.dumps(msg_dict) + "\n"
                os.write(self.ipc_write_fd, line.encode("utf-8"))
            except Exception as e:
                print("philo-chat: ----------------------------------------", flush=True)
                print(f"philo-chat: IPC write error: {e}", flush=True)
                print("philo-chat: ----------------------------------------", flush=True)

    def get_widget(self):
        return self.web_view


def run_philo_chat_subprocess(ipc_write_fd):
    set_process_name(SUBAPP_CHAT_NAME)
    app = Gtk.Application(application_id="com.philotes.philo_chat")
    
    def on_activate(gtk_app):
        philo_chat = PhiloChatApp(ipc_write_fd=ipc_write_fd)
        window = Gtk.ApplicationWindow(application=gtk_app, title="philo-chat")
        window.set_child(philo_chat.get_widget())
        window.set_default_size(900, 700)
        window.present()

    app.connect("activate", on_activate)
    app.run(None)

if __name__ == "__main__":
    run_philo_chat_subprocess(None)
