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
from philotes.settings_manager import init_system_theme_sync
from philotes.clipboard_bridge import enable_image_paste

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


# =============================================================================
# PhiloMsgsApp - Standardized Sub-Application
# =============================================================================
class PhiloMsgsApp:
    # -------------------------------------------------------------------------
    # Section 1: Subapp Metadata & Configuration Hooks
    # -------------------------------------------------------------------------
    APP_ID = "msgs"
    SUBAPP_NAME = SUBAPP_MSGS_NAME
    PROVIDER = "google-msgs"
    DEFAULT_URL = "https://messages.google.com/web"
    DOM_POLL_INTERVAL_SEC = 2

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
        init_system_theme_sync()
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
        self.web_view.connect("load-failed", self._on_load_failed)
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

    def load_google_msgs(self):
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

    def _on_load_failed(self, web_view, load_event, failing_uri, error):
        print(f"{self.SUBAPP_NAME}: load failed for {failing_uri}: {error.message}", flush=True)
        return False

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
        return self.DEFAULT_URL

    def _parse_selected_title(self, raw_title: str) -> str | None:
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
            print(f"{self.SUBAPP_NAME}: status updated via title notification (unread={self.unread_count}, title='{self.selected_title}')", flush=True)
            self._broadcast_status()

    def _poll_dom(self) -> bool:
        """Evaluate active conversation title directly from Google Messages DOM."""
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
        except Exception:
            pass
        return True

    def _on_dom_title_evaluated(self, web_view, result, user_data):
        try:
            js_val = web_view.evaluate_javascript_finish(result)
            if js_val:
                title_text = js_val.to_string()
                clean = self._parse_selected_title(title_text)
                if clean != self.selected_title:
                    self.selected_title = clean
                    print(f"{self.SUBAPP_NAME}: active conversation title updated -> '{self.selected_title}'", flush=True)
                    self._broadcast_status()
        except Exception as e:
            print(f"{self.SUBAPP_NAME}: DOM title evaluation error: {e}", flush=True)


# -----------------------------------------------------------------------------
# Section 5: Standalone Subprocess Runner (Boilerplate)
# -----------------------------------------------------------------------------
def run_philo_msgs_subprocess(ipc_write_fd):
    set_process_name(SUBAPP_MSGS_NAME)
    init_system_theme_sync()
    app = Gtk.Application(application_id="com.philotes.philo_msgs")

    def on_activate(gtk_app):
        philo_msgs = PhiloMsgsApp(ipc_write_fd=ipc_write_fd)
        window = Gtk.ApplicationWindow(application=gtk_app, title=SUBAPP_MSGS_NAME)
        window.set_child(philo_msgs.get_widget())
        window.set_default_size(900, 700)
        window.present()

    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    run_philo_msgs_subprocess(None)
