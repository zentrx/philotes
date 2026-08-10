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
from philotes.config import SUBAPP_MSGS_NAME
from philotes.session_manager import SessionManager
from philotes.clipboard_bridge import enable_image_paste

GOOGLE_MSGS_URL = "https://messages.google.com/web"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

class PhiloMsgsApp:
    def __init__(self, ipc_write_fd=None, profile_id="default", username=None):
        set_process_name(SUBAPP_MSGS_NAME)
        self.ipc_write_fd = ipc_write_fd
        self.profile_id = profile_id
        self.username = username
        self.unread_count = 0
        self.selected_title = None

        print(f"philo-msgs: initializing (profile={profile_id}, user={username})", flush=True)

        self.network_session = SessionManager.get_instance().get_network_session(
            provider="google-msgs",
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
            print("philo-msgs: ----------------------------------------", flush=True)
            print(f"philo-msgs: failed to set background color: {e}", flush=True)
            print("philo-msgs: ----------------------------------------", flush=True)

        self.web_view.connect("create", self._on_create_window)
        self.web_view.connect("notify::title", self._on_title_changed)
        self.web_view.connect("load-failed", self._on_load_failed)
        self.web_view.connect("web-process-terminated", self._on_web_process_terminated)

        GLib.timeout_add_seconds(2, self._poll_dom_timer)

        self.load_google_msgs()

    def load_google_msgs(self):
        print(f"philo-msgs: loading {GOOGLE_MSGS_URL}", flush=True)
        self.web_view.load_uri(GOOGLE_MSGS_URL)

    def _poll_dom_timer(self):
        self._evaluate_dom_title()
        return True

    def _evaluate_dom_title(self):
        js_code = """
        (function() {
            // 1. Check title inside active conversation header (top of right pane)
            let headerCandidates = document.querySelectorAll(
                'div.title-container, ' +
                'div.title, ' +
                '.title-container, ' +
                'mws-conversation-header .title, ' +
                'mws-conversation-header h1, ' +
                'mws-conversation-header [role="heading"], ' +
                'mws-conversation-header-container [role="heading"], ' +
                '[data-test-id="conversation-title"], ' +
                '.conversation-title, ' +
                'header [role="heading"], ' +
                'mws-conversation-header'
            );
            for (let el of headerCandidates) {
                let txt = (el.innerText || el.textContent || '').trim();
                if (txt) {
                    let firstLine = txt.split('\\n')[0].trim();
                    if (firstLine && firstLine.length < 80) {
                        let lower = firstLine.toLowerCase();
                        if (!lower.includes('google messages') &&
                            !lower.includes('messages for web') &&
                            !lower.includes('conversations') &&
                            !lower.includes('start chat') &&
                            !lower.includes('sign in') &&
                            !lower.includes('search') &&
                            !lower.includes('details')) {
                            return firstLine;
                        }
                    }
                }
            }

            // 2. Check active/selected conversation item in left conversation list
            let selectedItem = document.querySelector(
                'mws-conversation-list-item[selected], ' +
                'mws-conversation-list-item[aria-selected="true"], ' +
                'mws-conversation-list-item.selected, ' +
                '[role="option"][aria-selected="true"], ' +
                '[role="listitem"][aria-selected="true"]'
            );
            if (selectedItem) {
                let nameEl = selectedItem.querySelector('.name, .title, h2, h3, [role="heading"], span');
                let txt = nameEl ? nameEl.innerText : selectedItem.innerText;
                if (txt) {
                    let firstLine = txt.trim().split('\\n')[0].trim();
                    if (firstLine && firstLine.length < 80) {
                        let lower = firstLine.toLowerCase();
                        if (!lower.includes('google messages') && !lower.includes('conversations')) {
                            return firstLine;
                        }
                    }
                }
            }

            // 3. Fallback: inspect any heading in main conversation pane
            let mainPane = document.querySelector('mws-conversation-container, [role="main"]');
            if (mainPane) {
                let headings = mainPane.querySelectorAll('h1, h2, h3, [role="heading"]');
                for (let h of headings) {
                    let txt = (h.innerText || h.textContent || '').trim();
                    if (txt) {
                        let line = txt.split('\\n')[0].trim();
                        let lower = line.toLowerCase();
                        if (line.length < 80 && !lower.includes('google messages') && !lower.includes('conversations')) {
                            return line;
                        }
                    }
                }
            }

            return "";
        })();
        """
        try:
            self.web_view.evaluate_javascript(js_code, -1, None, None, None, self._on_dom_title_evaluated, None)
        except Exception as e:
            pass

    def _on_dom_title_evaluated(self, web_view, result, user_data):
        try:
            js_val = web_view.evaluate_javascript_finish(result)
            if js_val:
                title_text = js_val.to_string()
                clean = self._parse_selected_title(title_text)
                if clean != self.selected_title:
                    self.selected_title = clean
                    print(f"philo-msgs: active conversation title updated -> '{self.selected_title}'", flush=True)
                    self._send_ipc_msg({
                        "type": "status_update",
                        "app": "msgs",
                        "count": self.unread_count,
                        "title": self.selected_title,
                    })
        except Exception as e:
            print(f"philo-msgs: DOM title evaluation error: {e}", flush=True)

    def _on_web_process_terminated(self, web_view, reason):
        print("philo-msgs: ----------------------------------------", flush=True)
        print(f"philo-msgs: web process crashed (reason={reason}), reloading", flush=True)
        print("philo-msgs: ----------------------------------------", flush=True)
        web_view.reload()

    def _on_load_failed(self, web_view, load_event, failing_uri, error):
        print("philo-msgs: ----------------------------------------", flush=True)
        print(f"philo-msgs: load failed for {failing_uri}: {error.message}", flush=True)
        print("philo-msgs: ----------------------------------------", flush=True)
        return False

    def _on_create_window(self, web_view, navigation_action):
        request = navigation_action.get_request()
        uri = request.get_uri() if request else None
        if uri:
            print(f"philo-msgs: redirecting popup to main view ({uri})", flush=True)
            web_view.load_uri(uri)
        return None

    def _parse_selected_title(self, raw_title):
        if not raw_title:
            return None
        clean = re.sub(r"^\(\d+\)\s*", "", raw_title).strip()
        for suffix in [
            " - Google Messages for web: Conversations",
            ": Conversations",
            " - Google Messages for web",
            " - Messages for web",
            " - Messages",
            " - Google Messages",
        ]:
            if clean.endswith(suffix):
                clean = clean[:-len(suffix)].strip()
                break

        generic = {
            "messages",
            "messages for web",
            "google messages",
            "google messages for web",
            "google messages for web: conversations",
            "conversations",
            "start chat",
            "sign in - google accounts",
            "accounts",
        }
        if clean.lower() in generic:
            return None
        return clean if clean else None

    def _on_title_changed(self, web_view, param):
        title = web_view.get_title()
        if not title:
            return

        match = re.search(r"^\((\d+)\)", title)
        new_count = int(match.group(1)) if match else 0
        parsed_title = self._parse_selected_title(title)

        count_changed = (new_count != self.unread_count)
        if count_changed:
            self.unread_count = new_count

        if parsed_title and parsed_title != self.selected_title:
            self.selected_title = parsed_title
            count_changed = True

        if count_changed:
            print(f"philo-msgs: status updated via title notification (unread={self.unread_count}, title='{self.selected_title}')", flush=True)
            self._send_ipc_msg({
                "type": "status_update",
                "app": "msgs",
                "count": self.unread_count,
                "title": self.selected_title,
            })

    def _send_ipc_msg(self, msg_dict):
        if self.ipc_write_fd is not None:
            try:
                line = json.dumps(msg_dict) + "\n"
                os.write(self.ipc_write_fd, line.encode("utf-8"))
            except Exception as e:
                print("philo-msgs: ----------------------------------------", flush=True)
                print(f"philo-msgs: IPC write error: {e}", flush=True)
                print("philo-msgs: ----------------------------------------", flush=True)

    def get_widget(self):
        return self.web_view


def run_philo_msgs_subprocess(ipc_write_fd):
    set_process_name(SUBAPP_MSGS_NAME)
    app = Gtk.Application(application_id="com.philotes.philo_msgs")

    def on_activate(gtk_app):
        philo_msgs = PhiloMsgsApp(ipc_write_fd=ipc_write_fd)
        window = Gtk.ApplicationWindow(application=gtk_app, title="philo-msgs")
        window.set_child(philo_msgs.get_widget())
        window.set_default_size(900, 700)
        window.present()

    app.connect("activate", on_activate)
    app.run(None)

if __name__ == "__main__":
    run_philo_msgs_subprocess(None)
