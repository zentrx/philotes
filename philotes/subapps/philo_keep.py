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
from philotes.config import SUBAPP_KEEP_NAME
from philotes.session_manager import SessionManager
from philotes.clipboard_bridge import enable_image_paste

GOOGLE_KEEP_URL = "https://keep.google.com/u/0/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

class PhiloKeepApp:
    def __init__(self, ipc_write_fd=None, profile_id="default", username=None):
        set_process_name(SUBAPP_KEEP_NAME)
        self.ipc_write_fd = ipc_write_fd
        self.profile_id = profile_id
        self.username = username
        self.reminders_count = 0

        print(f"philo-keep: initializing (profile={profile_id}, user={username})", flush=True)

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
            print("philo-keep: ----------------------------------------", flush=True)
            print(f"philo-keep: failed to set background color: {e}", flush=True)
            print("philo-keep: ----------------------------------------", flush=True)

        self.web_view.connect("create", self._on_create_window)
        self.web_view.connect("notify::title", self._on_title_changed)
        self.web_view.connect("web-process-terminated", self._on_web_process_terminated)

        self.poll_timer_id = GLib.timeout_add_seconds(3, self._poll_dom_timer)

        self.load_google_keep()

    def load_google_keep(self):
        if self.username:
            target_url = f"https://accounts.google.com/ServiceLogin?continue=https://keep.google.com/u/0/&Email={urllib.parse.quote(self.username)}"
        else:
            target_url = GOOGLE_KEEP_URL
        print(f"philo-keep: loading {target_url}", flush=True)
        self.web_view.load_uri(target_url)

    def _poll_dom_timer(self):
        self._evaluate_dom_reminders()
        return True

    def _evaluate_dom_reminders(self):
        js_code = """
        (function() {
            // 1. Check title badge e.g. (3) Google Keep
            let titleMatch = document.title.match(/^\\((\\d+)\\)/);
            if (titleMatch) {
                return parseInt(titleMatch[1], 10);
            }

            // 2. Count active reminder chips/badges in Google Keep DOM
            let reminderElements = document.querySelectorAll(
                'div[aria-label*="Reminder"], ' +
                'div[aria-label*="reminder"], ' +
                '.gkeep-reminder, ' +
                '[data-drawer-option="reminders"] .badge, ' +
                'div[role="button"][aria-label*="Reminder"], ' +
                'div[role="button"][aria-label*="reminder"]'
            );
            
            let activeReminders = 0;
            let seenText = new Set();
            for (let el of reminderElements) {
                let txt = (el.getAttribute('aria-label') || el.innerText || '').trim();
                if (txt && !seenText.has(txt)) {
                    seenText.add(txt);
                    // Filter out navigation button labels like "Reminders"
                    let lower = txt.toLowerCase();
                    if (lower !== 'reminders' && lower !== 'reminder' && !lower.startsWith('edit labels')) {
                        activeReminders++;
                    }
                }
            }
            return activeReminders;
        })();
        """
        try:
            self.web_view.evaluate_javascript(js_code, -1, None, None, None, self._on_dom_reminders_evaluated, None)
        except Exception:
            pass

    def _on_dom_reminders_evaluated(self, web_view, result, user_data):
        try:
            js_val = web_view.evaluate_javascript_finish(result)
            if js_val:
                count = int(js_val.to_double()) if js_val.is_number() else 0
                if count != self.reminders_count:
                    self.reminders_count = count
                    print(f"philo-keep: reminders count updated -> {self.reminders_count}", flush=True)
                    self._send_ipc_msg({
                        "type": "status_update",
                        "app": "keep",
                        "count": self.reminders_count,
                    })
        except Exception as e:
            pass

    def _on_web_process_terminated(self, web_view, reason):
        print("philo-keep: ----------------------------------------", flush=True)
        print(f"philo-keep: web process crashed (reason={reason}), reloading", flush=True)
        print("philo-keep: ----------------------------------------", flush=True)
        web_view.reload()

    def _on_create_window(self, web_view, navigation_action):
        request = navigation_action.get_request()
        uri = request.get_uri() if request else None
        if uri:
            print(f"philo-keep: redirecting popup to main view ({uri})", flush=True)
            web_view.load_uri(uri)
        return None

    def _on_title_changed(self, web_view, param):
        title = web_view.get_title()
        if not title:
            return
        match = re.search(r"^\((\d+)\)", title)
        new_count = int(match.group(1)) if match else self.reminders_count
        if new_count != self.reminders_count:
            self.reminders_count = new_count
            print(f"philo-keep: status updated via title notification (count={self.reminders_count})", flush=True)
            self._send_ipc_msg({
                "type": "status_update",
                "app": "keep",
                "count": self.reminders_count,
            })

    def _send_ipc_msg(self, msg_dict):
        if self.ipc_write_fd is not None:
            try:
                line = json.dumps(msg_dict) + "\n"
                os.write(self.ipc_write_fd, line.encode("utf-8"))
            except Exception as e:
                print("philo-keep: ----------------------------------------", flush=True)
                print(f"philo-keep: IPC write error: {e}", flush=True)
                print("philo-keep: ----------------------------------------", flush=True)

    def reload(self):
        if hasattr(self, "web_view") and self.web_view:
            self.web_view.reload()

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


def run_philo_keep_subprocess(ipc_write_fd):
    set_process_name(SUBAPP_KEEP_NAME)
    app = Gtk.Application(application_id="com.philotes.philo_keep")

    def on_activate(gtk_app):
        philo_keep = PhiloKeepApp(ipc_write_fd=ipc_write_fd)
        window = Gtk.ApplicationWindow(application=gtk_app, title="philo-keep")
        window.set_child(philo_keep.get_widget())
        window.set_default_size(900, 700)
        window.present()

    app.connect("activate", on_activate)
    app.run(None)

if __name__ == "__main__":
    run_philo_keep_subprocess(None)
