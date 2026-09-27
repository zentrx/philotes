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
from philotes.config import SUBAPP_WORDLE_NAME
from philotes.session_manager import SessionManager
from philotes.settings_manager import init_system_theme_sync
from philotes.clipboard_bridge import enable_image_paste

WORDLE_URL = "https://www.nytimes.com/games/wordle/index.html"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

CHECK_WORDLE_STATUS_JS = """
(function() {
    try {
        var now = new Date();
        var y = now.getFullYear();
        var m = now.getMonth() + 1;
        if (m < 10) { m = '0' + m; }
        var d = now.getDate();
        if (d < 10) { d = '0' + d; }
        var localTodayStr = y + '-' + m + '-' + d;

        for (var i = 0; i < localStorage.length; i++) {
            var key = localStorage.key(i);
            if (key && key.indexOf('games-state-wordle') !== -1) {
                var raw = localStorage.getItem(key);
                if (!raw) { continue; }
                var val = JSON.parse(raw);
                var stateData = null;
                var printDate = null;

                if (val && val.states && val.states.length > 0) {
                    stateData = val.states[0].data || val.states[0];
                    printDate = val.states[0].printDate || val.states[0].date;
                } else if (val && (val.status || (val.game && val.game.status))) {
                    stateData = val.game || val;
                    printDate = val.printDate || val.date;
                }

                if (stateData) {
                    var status = (stateData.status || '').toUpperCase();
                    var isFinished = (status === 'WIN' || status === 'FAIL');
                    
                    var rowIndex = stateData.currentRowIndex || 0;
                    var board = stateData.boardState || stateData.guesses || [];
                    var hasGuesses = Array.isArray(board) && board.some(function(b) { return typeof b === 'string' && b.trim().length > 0; });

                    if (rowIndex >= 6) {
                        isFinished = true;
                    }

                    if (!printDate || printDate === localTodayStr) {
                        if (isFinished) {
                            return JSON.stringify({ completed: true, state: 'FINISHED', status: status, printDate: printDate });
                        } else if (status === 'IN_PROGRESS' && (rowIndex > 0 || hasGuesses)) {
                            return JSON.stringify({ completed: false, state: 'STARTED_UNFINISHED', status: status, printDate: printDate });
                        } else {
                            return JSON.stringify({ completed: false, state: 'NOT_STARTED', status: status, printDate: printDate });
                        }
                    } else {
                        return JSON.stringify({ completed: false, state: 'NOT_STARTED', status: 'NOT_STARTED', printDate: localTodayStr });
                    }
                }
            }
        }
    } catch(e) {}

    return JSON.stringify({ completed: false, state: 'NOT_STARTED', status: 'UNKNOWN' });
})();
"""

AD_BLOCK_CSS = """
/* NYTimes Wordle Ad Block & Element Hiding */
[id*="ad-"], [id*="dfp-ad"], [class*="ad-slot"], [class*="Ad-module"],
[class*="ad-container"], [class*="AdContainer"], iframe[src*="doubleclick"],
iframe[src*="googlesyndication"], div[id^="google_ads"], div[class*="ad-wrapper"],
#bottom-ad, #top-ad, .place-ad, #dfp-ad-top, #dfp-ad-bottom, #portal-editorial-ad,
.ad-unit, [data-testid*="ad-"] {
    display: none !important;
    visibility: hidden !important;
    height: 0px !important;
    max-height: 0px !important;
    min-height: 0px !important;
    margin: 0px !important;
    padding: 0px !important;
    overflow: hidden !important;
    pointer-events: none !important;
    opacity: 0 !important;
}
"""

AD_BLOCK_JS = """
(function() {
    function removeAds() {
        const selectors = [
            '[id*="ad-"]', '[id*="dfp-ad"]', '[class*="ad-slot"]', '[class*="Ad-module"]',
            '[class*="ad-container"]', '[class*="AdContainer"]', 'iframe[src*="doubleclick"]',
            'iframe[src*="googlesyndication"]', 'div[id^="google_ads"]', 'div[class*="ad-wrapper"]',
            '#bottom-ad', '#top-ad', '.place-ad', '#dfp-ad-top', '#dfp-ad-bottom', '#portal-editorial-ad',
            '.ad-unit', '[data-testid*="ad-"]'
        ];
        selectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(el => {
                try {
                    el.style.setProperty('display', 'none', 'important');
                    el.remove();
                } catch(e) {}
            });
        });
    }
    removeAds();
    const observer = new MutationObserver(removeAds);
    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            observer.observe(document.body, { childList: true, subtree: true });
        });
    }
})();
"""


class PhiloWordleApp:
    def __init__(self, ipc_write_fd=None, profile_id="default", username=None):
        set_process_name(SUBAPP_WORDLE_NAME)
        self.ipc_write_fd = ipc_write_fd
        self.profile_id = profile_id
        self.username = username
        self.wordle_completed = None

        print(f"philo-wordle: initializing (profile={profile_id}, user={username})", flush=True)

        self.network_session = SessionManager.get_instance().get_network_session(
            provider="nytimes",
            profile_id=profile_id,
        )

        init_system_theme_sync()
        self.settings = WebKit.Settings()
        self.settings.set_user_agent(USER_AGENT)
        self.settings.set_enable_javascript(True)
        self.settings.set_enable_developer_extras(True)
        self.settings.set_enable_page_cache(True)
        self.settings.set_enable_html5_local_storage(True)
        self.settings.set_enable_smooth_scrolling(True)
        self.settings.set_hardware_acceleration_policy(WebKit.HardwareAccelerationPolicy.ALWAYS)

        self.web_view = WebKit.WebView(network_session=self.network_session)
        self.web_view.set_settings(self.settings)
        enable_image_paste(self.web_view)

        # Native WebKitGTK Ad-Blocking (UserStyleSheet + UserScript MutationObserver)
        self.user_content_manager = self.web_view.get_user_content_manager()
        style_sheet = WebKit.UserStyleSheet.new(
            AD_BLOCK_CSS,
            WebKit.UserContentInjectedFrames.ALL_FRAMES,
            WebKit.UserStyleLevel.USER,
            None,
            None
        )
        self.user_content_manager.add_style_sheet(style_sheet)

        script = WebKit.UserScript.new(
            AD_BLOCK_JS,
            WebKit.UserContentInjectedFrames.ALL_FRAMES,
            WebKit.UserScriptInjectionTime.START,
            None,
            None
        )
        self.user_content_manager.add_script(script)

        try:
            gi.require_version("Gdk", "4.0")
            from gi.repository import Gdk
            rgba = Gdk.RGBA()
            rgba.parse("#1a1b26")
            self.web_view.set_background_color(rgba)
        except Exception as e:
            print(f"philo-wordle: failed to set background color: {e}", flush=True)

        self.web_view.connect("create", self._on_create_window)
        self.web_view.connect("notify::title", self._on_title_changed)
        self.web_view.connect("notify::uri", self._on_uri_changed)
        self.web_view.connect("load-changed", self._on_load_changed)
        self.web_view.connect("web-process-terminated", self._on_web_process_terminated)

        self.load_wordle()
        self.completion_timer_id = GLib.timeout_add(2000, self._periodic_completion_check)

    def _periodic_completion_check(self):
        self._check_wordle_completion()
        return True

    def _on_web_process_terminated(self, web_view, reason):
        print(f"philo-wordle: web process crashed (reason={reason}), reloading", flush=True)
        web_view.reload()

    def load_initial_url(self):
        self.load_wordle()

    def load_wordle(self):
        print(f"philo-wordle: loading {WORDLE_URL}", flush=True)
        self.web_view.load_uri(WORDLE_URL)

    def _on_create_window(self, web_view, navigation_action):
        request = navigation_action.get_request()
        uri = request.get_uri() if request else None
        if uri:
            print(f"philo-wordle: redirecting popup to main view ({uri})", flush=True)
            web_view.load_uri(uri)
        return None

    def _on_load_changed(self, web_view, load_event):
        if load_event == WebKit.LoadEvent.FINISHED:
            self._check_wordle_completion()

    def _check_wordle_completion(self):
        def on_js_finished(web_view, result):
            try:
                val = web_view.evaluate_javascript_finish(result)
                if val:
                    res_str = val.to_string()
                    data = json.loads(res_str)
                    is_completed = data.get("completed", False)
                    if is_completed != self.wordle_completed:
                        self.wordle_completed = is_completed
                        self._send_ipc_msg({
                            "type": "status_update",
                            "app": "wordle",
                            "completed": self.wordle_completed,
                        })
            except Exception as e:
                pass

        self.web_view.evaluate_javascript(CHECK_WORDLE_STATUS_JS, -1, None, None, None, on_js_finished)

    def _on_uri_changed(self, web_view, param):
        uri = web_view.get_uri()
        if not uri:
            return
        if "subscription" in uri or "subscribe" in uri or "paywall" in uri:
            print(f"philo-wordle: paywall/subscription URL detected ({uri})", flush=True)
            self._send_ipc_msg({
                "type": "auth_error",
                "app": "wordle",
                "reason": "subscription_required",
            })
        elif "login" in uri or "accounts.nytimes.com" in uri:
            print(f"philo-wordle: login URL detected ({uri})", flush=True)
            self._send_ipc_msg({
                "type": "auth_error",
                "app": "wordle",
                "reason": "no_auth_card",
            })

    def _on_title_changed(self, web_view, param):
        title = web_view.get_title()
        if title:
            self._send_ipc_msg({
                "type": "title_update",
                "app": "wordle",
                "title": title,
            })

    def _send_ipc_msg(self, msg_dict):
        if self.ipc_write_fd is not None:
            try:
                line = json.dumps(msg_dict) + "\n"
                os.write(self.ipc_write_fd, line.encode("utf-8"))
            except Exception as e:
                print(f"philo-wordle: IPC write error: {e}", flush=True)

    def reload(self):
        if hasattr(self, "web_view") and self.web_view:
            self.load_initial_url()

    def cleanup(self):
        if getattr(self, "completion_timer_id", None):
            try:
                GLib.source_remove(self.completion_timer_id)
            except Exception:
                pass
            self.completion_timer_id = None
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


def run_philo_wordle_subprocess(ipc_write_fd):
    set_process_name(SUBAPP_WORDLE_NAME)
    init_system_theme_sync()
    app = Gtk.Application(application_id="com.philotes.philo_wordle")
    
    def on_activate(gtk_app):
        philo_wordle = PhiloWordleApp(ipc_write_fd=ipc_write_fd)
        window = Gtk.ApplicationWindow(application=gtk_app, title="philo-wordle")
        window.set_child(philo_wordle.get_widget())
        window.set_default_size(900, 700)
        window.present()

    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    run_philo_wordle_subprocess(None)
