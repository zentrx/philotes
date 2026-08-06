import sys
import os
import re
import json
import time
import urllib.parse
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit, GLib
from philotes.session_manager import SessionManager
from philotes.config import CONFIG_DIR

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
NYTIMES_LOGIN_URL = "https://myaccount.nytimes.com/auth/login"

EXTRACT_USER_INFO_JS = """
(function() {
    try {
        let email = null;
        let displayName = null;
        let subscribed = true;
        let loggedIn = false;

        const cookies = document.cookie || "";
        if (cookies.includes("NYT-S=") || cookies.includes("NYT-T=") || cookies.includes("nyt-jk=") || cookies.includes("NYT-HD=")) {
            loggedIn = true;
        }

        if (window.nyt_user) {
            email = window.nyt_user.email || window.nyt_user.username;
            displayName = window.nyt_user.displayName || window.nyt_user.name;
            if (window.nyt_user.sub !== undefined) subscribed = !!window.nyt_user.sub;
            if (window.nyt_user.entitlements && (window.nyt_user.entitlements.includes("games") || window.nyt_user.entitlements.includes("hd"))) {
                subscribed = true;
            }
        }

        if (!email && window.__NYT__) {
            const u = window.__NYT__.user || window.__NYT__.userData;
            if (u) {
                email = u.email || u.username;
                displayName = u.displayName || u.name;
                if (u.sub !== undefined) subscribed = !!u.sub;
                if (u.entitlements && (u.entitlements.includes("games") || u.entitlements.includes("hd"))) {
                    subscribed = true;
                }
            }
        }

        if (!email) {
            const emailElem = document.querySelector('[data-testid="user-email"]') || document.querySelector('.user-email') || document.querySelector('#email');
            if (emailElem) {
                email = emailElem.innerText || emailElem.textContent || emailElem.value;
            }
        }

        const uri = window.location.href;

        // Any authenticated session with NYT-S cookie is treated as subscribed by default
        if (loggedIn) {
            subscribed = true;
        }

        return JSON.stringify({
            loggedIn: loggedIn,
            email: email,
            displayName: displayName,
            subscribed: subscribed,
            currentUrl: uri
        });
    } catch(e) {
        return JSON.stringify({loggedIn: false, email: null, displayName: null, subscribed: true, currentUrl: window.location.href});
    }
})();
"""


class NYTimesLoginWindow(Gtk.Window):
    def __init__(self, parent_window=None, on_success_cb=None):
        super().__init__(title="New York Times Login")
        self.set_default_size(560, 720)
        self.set_transient_for(parent_window)
        self.set_modal(True)
        self.on_success_cb = on_success_cb
        self.auth_completed = False

        self.card_id = f"nytimes_{int(time.time() * 1000)}"
        self.profile_dir_name = f"nytimes-{self.card_id}"
        self.network_session = SessionManager.get_instance().get_network_session(
            provider="nytimes",
            profile_id=self.profile_dir_name,
        )

        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header Info & Action Bar
        info_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        info_bar.set_margin_start(12)
        info_bar.set_margin_end(12)
        info_bar.set_margin_top(8)
        info_bar.set_margin_bottom(8)

        info_label = Gtk.Label(label="Log in to your NYTimes account below:")
        info_label.set_hexpand(True)
        info_label.set_halign(Gtk.Align.START)

        self.complete_btn = Gtk.Button(label="Complete Login ✓")
        self.complete_btn.add_css_class("add-account-btn")
        self.complete_btn.connect("clicked", lambda w: self._check_authentication(force=True))

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda w: self.close())

        info_bar.append(info_label)
        info_bar.append(self.complete_btn)
        info_bar.append(cancel_btn)
        main_vbox.append(info_bar)

        # Status Notification Line
        self.status_label = Gtk.Label(label="Please enter your email and password on the NYTimes page.")
        self.status_label.add_css_class("section-desc")
        self.status_label.set_margin_start(12)
        self.status_label.set_margin_bottom(6)
        self.status_label.set_halign(Gtk.Align.START)
        main_vbox.append(self.status_label)

        # WebKit WebView
        self.settings = WebKit.Settings()
        self.settings.set_user_agent(USER_AGENT)
        self.settings.set_enable_javascript(True)
        self.settings.set_enable_html5_local_storage(True)
        self.settings.set_hardware_acceleration_policy(WebKit.HardwareAccelerationPolicy.ALWAYS)

        self.web_view = WebKit.WebView(network_session=self.network_session)
        self.web_view.set_settings(self.settings)
        self.web_view.set_hexpand(True)
        self.web_view.set_vexpand(True)

        self.web_view.connect("load-changed", self._on_load_changed)
        self.web_view.connect("notify::uri", self._on_uri_changed)

        main_vbox.append(self.web_view)
        self.set_child(main_vbox)

        self.web_view.load_uri(NYTIMES_LOGIN_URL)

    def _on_uri_changed(self, web_view, param):
        uri = web_view.get_uri()
        if not uri or self.auth_completed:
            return
        
        # Only attempt auto-check if user navigated away from /auth/ to main NYTimes or Games site
        if "nytimes.com" in uri and "/auth/" not in uri:
            GLib.timeout_add(1000, self._check_authentication)

    def _on_load_changed(self, web_view, load_event):
        if load_event == WebKit.LoadEvent.FINISHED and not self.auth_completed:
            uri = web_view.get_uri() or ""
            if "nytimes.com" in uri and "/auth/" not in uri:
                self._check_authentication()

    def _check_authentication(self, force=False):
        if self.auth_completed:
            return False

        def on_js_finished(web_view, result):
            try:
                val = web_view.evaluate_javascript_finish(result)
                if not val:
                    if force:
                        self.status_label.set_text("Unable to detect login state yet. Please log in first.")
                    return
                data = json.loads(val.to_string())
                is_logged_in = data.get("loggedIn", False)
                current_url = data.get("currentUrl", "")

                if is_logged_in or (force and "/auth/" not in current_url):
                    self.auth_completed = True
                    email = data.get("email")
                    display_name = data.get("displayName")
                    subscribed = data.get("subscribed", True)

                    if not email or "@" not in email:
                        # Prompt or fallback to account index if email omitted
                        acc_count = len(SessionManager.get_instance()._sessions)
                        email = f"nytimes.user{acc_count}@nytimes.com"
                    if not display_name:
                        display_name = email.split("@")[0].capitalize()

                    if self.on_success_cb:
                        self.on_success_cb({
                            "username": email,
                            "display_name": display_name,
                            "subscribed": subscribed,
                            "profile_dir": self.profile_dir_name,
                        })

                    self.close()
                elif force:
                    self.status_label.set_text("Login not completed yet. Please finish entering your credentials.")
            except Exception as e:
                sys.stderr.write(f"[NYTimes Auth] JS evaluation error: {e}\n")

        self.web_view.evaluate_javascript(EXTRACT_USER_INFO_JS, -1, None, None, None, on_js_finished)
        return False
