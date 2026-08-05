import sys
import os
import re
import json
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit, GLib
from philotes.process_utils import set_process_name
from philotes.config import SUBAPP_CHAT_NAME
from philotes.session_manager import SessionManager

GOOGLE_CHAT_URL = "https://chat.google.com/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

class PhiloChatApp:
    def __init__(self, ipc_write_fd=None):
        set_process_name(SUBAPP_CHAT_NAME)
        self.ipc_write_fd = ipc_write_fd
        self.unread_count = 0

        self.network_session = SessionManager.get_instance().get_network_session(
            provider="google",
            profile_id="default",
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

        self.web_view.connect("create", self._on_create_window)
        self.web_view.connect("notify::title", self._on_title_changed)
        
        self.load_google_chat()

    def load_google_chat(self):
        target_url = "https://accounts.google.com/ServiceLogin?service=mail&continue=https://chat.google.com/"
        self.web_view.load_uri(target_url)

    def _on_create_window(self, web_view, navigation_action):
        request = navigation_action.get_request()
        if request and request.get_uri():
            web_view.load_uri(request.get_uri())
        return None

    def _on_title_changed(self, web_view, param):
        title = web_view.get_title()
        if not title:
            return
        
        match = re.search(r"^\((\d+)\)", title)
        new_count = int(match.group(1)) if match else 0

        if new_count != self.unread_count:
            self.unread_count = new_count
            self._send_ipc_msg({"type": "unread_count", "count": self.unread_count})

    def _send_ipc_msg(self, msg_dict):
        if self.ipc_write_fd is not None:
            try:
                line = json.dumps(msg_dict) + "\n"
                os.write(self.ipc_write_fd, line.encode("utf-8"))
            except Exception as e:
                sys.stderr.write(f"[philo-chat] IPC write error: {e}\n")
        else:
            print(f"[philo-chat IPC] {json.dumps(msg_dict)}", flush=True)

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
