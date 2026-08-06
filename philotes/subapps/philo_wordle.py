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

WORDLE_URL = "https://www.nytimes.com/games/wordle/index.html"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

CHECK_WORDLE_STATUS_JS = """
(function() {
    try {
        const todayStr = new Date().toISOString().slice(0, 10);

        const rawState = localStorage.getItem("nyt-wordle-state");
        if (rawState) {
            const state = JSON.parse(rawState);
            const status = state.gameStatus || (state.stats && state.stats.gameStatus);
            if (status === "WIN" || status === "FAIL" || status === "IN_PROGRESS_WON" || status === "IN_PROGRESS_LOST") {
                return JSON.stringify({completed: true});
            }
        }

        const rawMoat = localStorage.getItem("nyt-wordle-moat");
        if (rawMoat) {
            const moat = JSON.parse(rawMoat);
            const status = moat.gameStatus || moat.status;
            if (status === "WIN" || status === "FAIL") {
                return JSON.stringify({completed: true});
            }
        }

        if (document.querySelector('button[data-testid="share-button"]') ||
            document.querySelector('[data-testid="stats-dialog"]') ||
            document.querySelector('game-stats') ||
            document.querySelector('[class*="Stats-module"]') ||
            document.querySelector('div[class*="countdown"]')) {
            return JSON.stringify({completed: true});
        }
    } catch(e) {}
    return JSON.stringify({completed: false});
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
        self.wordle_completed = False

        print(f"philo-wordle: initializing (profile={profile_id}, user={username})", flush=True)

        self.network_session = SessionManager.get_instance().get_network_session(
            provider="nytimes",
            profile_id=profile_id,
        )

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
        GLib.timeout_add(2000, self._periodic_completion_check)

    def _periodic_completion_check(self):
        self._check_wordle_completion()
        return True

    def _on_web_process_terminated(self, web_view, reason):
        print(f"philo-wordle: web process crashed (reason={reason}), reloading", flush=True)
        web_view.reload()

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

    def get_widget(self):
        return self.web_view


def run_philo_wordle_subprocess(ipc_write_fd):
    set_process_name(SUBAPP_WORDLE_NAME)
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
