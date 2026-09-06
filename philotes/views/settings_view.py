import sys
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from philotes.account_manager import AccountManager
from philotes.auth import GCPAuthManager, parse_id_token
from philotes.auth_nytimes import NYTimesLoginWindow
from philotes.session_manager import SessionManager
from philotes.components.account_card import AccountCardWidget

class SettingsView(Gtk.Box):
    def __init__(self, on_accounts_changed_cb=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.on_accounts_changed_cb = on_accounts_changed_cb

        self.set_name("settings-view")
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.set_margin_top(24)
        self.set_margin_bottom(24)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        main_vbox.set_halign(Gtk.Align.START)
        main_vbox.set_hexpand(True)

        header_title = Gtk.Label()
        header_title.set_markup("<span size='xx-large' weight='bold'>Settings &amp; Service Pools</span>")
        header_title.set_halign(Gtk.Align.START)
        main_vbox.append(header_title)

        # Alert Banner Container
        self.alert_banner = Gtk.Label()
        self.alert_banner.add_css_class("settings-alert-banner")
        self.alert_banner.set_halign(Gtk.Align.START)
        self.alert_banner.set_visible(False)
        main_vbox.append(self.alert_banner)

        # -------------------------------------------------------------
        # Google Service Pool
        # -------------------------------------------------------------
        google_sec_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        google_sec_vbox.set_halign(Gtk.Align.START)

        sec_title = Gtk.Label()
        sec_title.set_markup("<span size='x-large' weight='bold'>Google Service Logins</span>")
        sec_title.set_halign(Gtk.Align.START)
        google_sec_vbox.append(sec_title)

        sec_desc = Gtk.Label(label="GCP OAuth 2.0 PKCE authentication for Google Chat, Google Messages, Google Keep, Google Tasks, and Workspace services.")
        sec_desc.add_css_class("section-desc")
        sec_desc.set_halign(Gtk.Align.START)
        google_sec_vbox.append(sec_desc)

        # Cards Container Box (Oldest at Top, Newest at Bottom)
        self.cards_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.cards_vbox.set_halign(Gtk.Align.START)
        google_sec_vbox.append(self.cards_vbox)

        # Add Google Auth Card Button (Below all Auth Cards)
        add_user_btn = Gtk.Button(label="+ Add Google Auth Card")
        add_user_btn.add_css_class("add-account-btn")
        add_user_btn.set_halign(Gtk.Align.START)
        add_user_btn.connect("clicked", self._on_add_google_card_clicked)
        google_sec_vbox.append(add_user_btn)

        main_vbox.append(google_sec_vbox)

        # -------------------------------------------------------------
        # New York Times Service Pool
        # -------------------------------------------------------------
        nyt_sec_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        nyt_sec_vbox.set_halign(Gtk.Align.START)

        nyt_title = Gtk.Label()
        nyt_title.set_markup("<span size='x-large' weight='bold'>New York Times Service Logins</span>")
        nyt_title.set_halign(Gtk.Align.START)
        nyt_sec_vbox.append(nyt_title)

        nyt_desc = Gtk.Label(label="Authentication & Subscription for NYTimes Wordle and Games services.")
        nyt_desc.add_css_class("section-desc")
        nyt_desc.set_halign(Gtk.Align.START)
        nyt_sec_vbox.append(nyt_desc)

        self.nytimes_cards_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.nytimes_cards_vbox.set_halign(Gtk.Align.START)
        nyt_sec_vbox.append(self.nytimes_cards_vbox)

        add_nyt_user_btn = Gtk.Button(label="+ Add NYTimes Auth Card")
        add_nyt_user_btn.add_css_class("add-account-btn")
        add_nyt_user_btn.set_halign(Gtk.Align.START)
        add_nyt_user_btn.connect("clicked", self._on_add_nytimes_card_clicked)
        nyt_sec_vbox.append(add_nyt_user_btn)

        main_vbox.append(nyt_sec_vbox)

        scrolled.set_child(main_vbox)
        self.append(scrolled)

        self.refresh_cards()

    def show_alert_message(self, message: str):
        if message:
            self.alert_banner.set_text(f"⚠️ {message}")
            self.alert_banner.set_visible(True)
        else:
            self.alert_banner.set_visible(False)

    def refresh_cards(self):
        # Refresh Google Cards
        while child := self.cards_vbox.get_first_child():
            self.cards_vbox.remove(child)

        google_cards = AccountManager.get_instance().get_cards(provider="google")
        if not google_cards:
            empty_label = Gtk.Label(label="No Auth Cards present in Google Service Pool. Click '+ Add Google Auth Card' below.")
            empty_label.add_css_class("section-desc")
            empty_label.set_halign(Gtk.Align.START)
            self.cards_vbox.append(empty_label)
        else:
            for card_data in google_cards:
                card_widget = AccountCardWidget(card_data, on_state_changed_cb=self._on_card_state_changed)
                self.cards_vbox.append(card_widget)

        # Refresh NYTimes Cards
        while child := self.nytimes_cards_vbox.get_first_child():
            self.nytimes_cards_vbox.remove(child)

        nyt_cards = AccountManager.get_instance().get_cards(provider="nytimes")
        if not nyt_cards:
            empty_nyt_label = Gtk.Label(label="No Auth Cards present in NYTimes Service Pool. Click '+ Add NYTimes Auth Card' below.")
            empty_nyt_label.add_css_class("section-desc")
            empty_nyt_label.set_halign(Gtk.Align.START)
            self.nytimes_cards_vbox.append(empty_nyt_label)
        else:
            for card_data in nyt_cards:
                card_widget = AccountCardWidget(card_data, on_state_changed_cb=self._on_card_state_changed)
                self.nytimes_cards_vbox.append(card_widget)

    def _on_card_state_changed(self):
        self.refresh_cards()
        if self.on_accounts_changed_cb:
            self.on_accounts_changed_cb()

    def _on_add_google_card_clicked(self, widget):
        auth_mgr = GCPAuthManager()
        acc_count = len(AccountManager.get_instance().get_cards("google")) + 1

        if not auth_mgr.is_configured():
            # Create sample Auth Card if client_secret.json not configured
            AccountManager.get_instance().add_auth_card(
                provider="google",
                display_name=f"Google User {acc_count}",
                username=f"user{acc_count}@gmail.com",
            )
            self._on_card_state_changed()
        else:
            widget.set_sensitive(False)

            def on_auth_finished(tokens, error):
                widget.set_sensitive(True)
                if error or not tokens:
                    if error:
                        sys.stderr.write(f"[Philotes Settings] Add Auth Card error or cancelled: {error}\n")
                    return

                display_name = f"Authenticated User {acc_count}"
                username = f"auth.user{acc_count}@gmail.com"

                if "id_token" in tokens:
                    payload = parse_id_token(tokens["id_token"])
                    if payload.get("email"):
                        username = payload["email"]
                    if payload.get("name"):
                        display_name = payload["name"]

                email_prefix = username.split("@")[0]
                profile_dir_name = f"google-{email_prefix}"

                AccountManager.get_instance().add_auth_card(
                    provider="google",
                    display_name=display_name,
                    username=username,
                    profile_dir=profile_dir_name,
                )

                self._on_card_state_changed()

            auth_mgr.start_pkce_login_async(callback=on_auth_finished)

    def _on_add_nytimes_card_clicked(self, widget):
        parent_win = self.get_root()
        
        def on_login_success(user_data):
            AccountManager.get_instance().add_auth_card(
                provider="nytimes",
                display_name=user_data.get("display_name", "NYTimes User"),
                username=user_data.get("username", "user@nytimes.com"),
                profile_dir=user_data.get("profile_dir"),
                subscribed=user_data.get("subscribed", True),
            )
            self.show_alert_message(None)
            self._on_card_state_changed()

        login_win = NYTimesLoginWindow(parent_window=parent_win, on_success_cb=on_login_success)
        login_win.present()


