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
from philotes.config import SUBAPP_TASKS_NAME
from philotes.session_manager import SessionManager
from philotes.clipboard_bridge import enable_image_paste

GOOGLE_TASKS_URL = "https://tasks.google.com/u/0/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

class PhiloTasksApp:
    def __init__(self, ipc_write_fd=None, profile_id="default", username=None):
        set_process_name(SUBAPP_TASKS_NAME)
        self.ipc_write_fd = ipc_write_fd
        self.profile_id = profile_id
        self.username = username
        self.tasks_count = 0

        print(f"philo-tasks: initializing (profile={profile_id}, user={username})", flush=True)

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
            print("philo-tasks: ----------------------------------------", flush=True)
            print(f"philo-tasks: failed to set background color: {e}", flush=True)
            print("philo-tasks: ----------------------------------------", flush=True)

        self.web_view.connect("create", self._on_create_window)
        self.web_view.connect("notify::title", self._on_title_changed)
        self.web_view.connect("web-process-terminated", self._on_web_process_terminated)

        GLib.timeout_add_seconds(3, self._poll_dom_timer)

        self.load_google_tasks()

    def load_google_tasks(self):
        if self.username:
            target_url = f"https://accounts.google.com/ServiceLogin?continue=https://tasks.google.com/u/0/&Email={urllib.parse.quote(self.username)}"
        else:
            target_url = GOOGLE_TASKS_URL
        print(f"philo-tasks: loading {target_url}", flush=True)
        self.web_view.load_uri(target_url)

    def _poll_dom_timer(self):
        self._evaluate_dom_tasks()
        return True

    def _evaluate_dom_tasks(self):
        js_code = """
        (function() {
            // 1. Check title badge e.g. (3) Google Tasks
            let titleMatch = document.title.match(/^\\((\\d+)\\)/);
            if (titleMatch) {
                return parseInt(titleMatch[1], 10);
            }

            // 2. Count active task items in Google Tasks DOM
            let taskElements = document.querySelectorAll(
                'div[role="checkbox"][aria-checked="false"], ' +
                'div[data-task-id], ' +
                '.task-item, ' +
                'div[aria-label*="Task"]'
            );
            
            let activeTasks = 0;
            let seenText = new Set();
            for (let el of taskElements) {
                let txt = (el.getAttribute('aria-label') || el.innerText || '').trim();
                if (txt && !seenText.has(txt)) {
                    seenText.add(txt);
                    activeTasks++;
                }
            }
            return activeTasks;
        })();
        """
        try:
            self.web_view.evaluate_javascript(js_code, -1, None, None, None, self._on_dom_tasks_evaluated, None)
        except Exception:
            pass

    def _on_dom_tasks_evaluated(self, web_view, result, user_data):
        try:
            js_val = web_view.evaluate_javascript_finish(result)
            if js_val:
                count = int(js_val.to_double()) if js_val.is_number() else 0
                if count != self.tasks_count:
                    self.tasks_count = count
                    print(f"philo-tasks: tasks count updated -> {self.tasks_count}", flush=True)
                    self._send_ipc_msg({
                        "type": "status_update",
                        "app": "tasks",
                        "count": self.tasks_count,
                    })
        except Exception:
            pass

    def _on_web_process_terminated(self, web_view, reason):
        print("philo-tasks: ----------------------------------------", flush=True)
        print(f"philo-tasks: web process crashed (reason={reason}), reloading", flush=True)
        print("philo-tasks: ----------------------------------------", flush=True)
        web_view.reload()

    def _on_create_window(self, web_view, navigation_action):
        request = navigation_action.get_request()
        uri = request.get_uri() if request else None
        if uri:
            print(f"philo-tasks: redirecting popup to main view ({uri})", flush=True)
            web_view.load_uri(uri)
        return None

    def _on_title_changed(self, web_view, param):
        title = web_view.get_title()
        if not title:
            return
        match = re.search(r"^\((\d+)\)", title)
        new_count = int(match.group(1)) if match else self.tasks_count
        if new_count != self.tasks_count:
            self.tasks_count = new_count
            print(f"philo-tasks: status updated via title notification (count={self.tasks_count})", flush=True)
            self._send_ipc_msg({
                "type": "status_update",
                "app": "tasks",
                "count": self.tasks_count,
            })

    def _send_ipc_msg(self, msg_dict):
        if self.ipc_write_fd is not None:
            try:
                line = json.dumps(msg_dict) + "\n"
                os.write(self.ipc_write_fd, line.encode("utf-8"))
            except Exception as e:
                print("philo-tasks: ----------------------------------------", flush=True)
                print(f"philo-tasks: IPC write error: {e}", flush=True)
                print("philo-tasks: ----------------------------------------", flush=True)

    def get_widget(self):
        return self.web_view


def run_philo_tasks_subprocess(ipc_write_fd):
    set_process_name(SUBAPP_TASKS_NAME)
    app = Gtk.Application(application_id="com.philotes.philo_tasks")

    def on_activate(gtk_app):
        philo_tasks = PhiloTasksApp(ipc_write_fd=ipc_write_fd)
        window = Gtk.ApplicationWindow(application=gtk_app, title="philo-tasks")
        window.set_child(philo_tasks.get_widget())
        window.set_default_size(900, 700)
        window.present()

    app.connect("activate", on_activate)
    app.run(None)

if __name__ == "__main__":
    run_philo_tasks_subprocess(None)
