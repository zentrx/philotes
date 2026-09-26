import sys
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango
from philotes import __version__
from philotes.account_manager import AccountManager
from philotes.auth import GCPAuthManager, parse_id_token
from philotes.auth_nytimes import NYTimesLoginWindow
from philotes.session_manager import SessionManager
from philotes.components.account_card import AccountCardWidget
from philotes.settings_manager import SettingsManager, SERVICE_POOLS, TAB_METADATA

CATEGORIES = [
    {
        "id": "google",
        "title": "Google",
        "icon": "🌐",
        "desc": "Google Workspace & Chat",
    },
    {
        "id": "nytimes",
        "title": "NYTimes",
        "icon": "📰",
        "desc": "Wordle & Games",
    },
    {
        "id": "tabs",
        "title": "Tab Layout",
        "icon": "📑",
        "desc": "Top Bar Arrangement",
    },
    {
        "id": "system",
        "title": "System",
        "icon": "⚙️",
        "desc": "Diagnostics & Desktop",
    },
]

class SettingsView(Gtk.Box):
    def __init__(self, on_accounts_changed_cb=None, on_reset_tab_order_cb=None, on_tab_toggled_cb=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.on_accounts_changed_cb = on_accounts_changed_cb
        self.on_reset_tab_order_cb = on_reset_tab_order_cb
        self.on_tab_toggled_cb = on_tab_toggled_cb

        self.set_name("settings-view")
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.is_sidebar_expanded = False
        self.current_category = "google"
        self.category_buttons = {}
        self.category_labels = {}

        # -------------------------------------------------------------
        # Left Sidebar (Master Rail)
        # -------------------------------------------------------------
        self.sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.sidebar_box.add_css_class("settings-sidebar")
        self.sidebar_box.set_size_request(52, -1)

        # Sidebar Collapse / Expand Toggle Button
        self.sidebar_toggle_btn = Gtk.Button(label="☰")
        self.sidebar_toggle_btn.add_css_class("settings-sidebar-toggle-btn")
        self.sidebar_toggle_btn.set_tooltip_text("Toggle sidebar expand / collapse")
        self.sidebar_toggle_btn.connect("clicked", self._on_sidebar_toggle_clicked)
        self.sidebar_box.append(self.sidebar_toggle_btn)

        # Build Sidebar Navigation Buttons
        for cat in CATEGORIES:
            cat_btn = Gtk.Button()
            cat_btn.add_css_class("sidebar-category-btn")
            cat_btn.set_tooltip_text(f"{cat['title']}: {cat['desc']}")

            btn_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            btn_hbox.set_halign(Gtk.Align.START)

            icon_lbl = Gtk.Label(label=cat["icon"])
            icon_lbl.add_css_class("sidebar-category-icon")
            btn_hbox.append(icon_lbl)

            title_lbl = Gtk.Label(label=cat["title"])
            title_lbl.add_css_class("sidebar-category-label")
            title_lbl.set_visible(self.is_sidebar_expanded)
            btn_hbox.append(title_lbl)

            cat_btn.set_child(btn_hbox)
            cat_btn.connect("clicked", lambda b, cid=cat["id"]: self._select_category(cid))

            self.category_buttons[cat["id"]] = cat_btn
            self.category_labels[cat["id"]] = title_lbl
            self.sidebar_box.append(cat_btn)

        self.append(self.sidebar_box)

        # -------------------------------------------------------------
        # Right Detail Area (Detail Stack)
        # -------------------------------------------------------------
        detail_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        detail_container.set_hexpand(True)
        detail_container.set_vexpand(True)
        detail_container.set_margin_start(16)
        detail_container.set_margin_end(16)
        detail_container.set_margin_top(16)
        detail_container.set_margin_bottom(16)

        # Alert Banner Container (Visible across all categories when message is active)
        self.alert_banner = Gtk.Label()
        self.alert_banner.add_css_class("settings-alert-banner")
        self.alert_banner.set_halign(Gtk.Align.FILL)
        self.alert_banner.set_wrap(True)
        self.alert_banner.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.alert_banner.set_visible(False)
        detail_container.append(self.alert_banner)

        # Detail Stack
        self.detail_stack = Gtk.Stack()
        self.detail_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.detail_stack.set_transition_duration(120)
        self.detail_stack.set_hexpand(True)
        self.detail_stack.set_vexpand(True)

        # Build Detail Pages
        self.detail_stack.add_named(self._build_google_page(), "google")
        self.detail_stack.add_named(self._build_nytimes_page(), "nytimes")
        self.detail_stack.add_named(self._build_tabs_page(), "tabs")
        self.detail_stack.add_named(self._build_system_page(), "system")

        detail_container.append(self.detail_stack)
        self.append(detail_container)

        self._select_category("google")
        self.refresh_cards()

    def _on_sidebar_toggle_clicked(self, widget):
        self.is_sidebar_expanded = not self.is_sidebar_expanded
        for lbl in self.category_labels.values():
            lbl.set_visible(self.is_sidebar_expanded)
        if self.is_sidebar_expanded:
            self.sidebar_toggle_btn.set_label("◀")
            self.sidebar_box.set_size_request(160, -1)
        else:
            self.sidebar_toggle_btn.set_label("☰")
            self.sidebar_box.set_size_request(52, -1)

    def _select_category(self, cat_id: str):
        self.current_category = cat_id
        self.detail_stack.set_visible_child_name(cat_id)
        for cid, btn in self.category_buttons.items():
            if cid == cat_id:
                btn.add_css_class("sidebar-category-btn-active")
            else:
                btn.remove_css_class("sidebar-category-btn-active")

    # -----------------------------------------------------------------
    # Page Builders
    # -----------------------------------------------------------------
    def _build_google_page(self) -> Gtk.ScrolledWindow:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        page_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page_vbox.set_hexpand(True)

        header_title = Gtk.Label()
        header_title.set_markup("<span size='x-large' weight='bold'>Google Service Logins</span>")
        header_title.set_halign(Gtk.Align.START)
        page_vbox.append(header_title)

        sec_desc = Gtk.Label(label="GCP OAuth 2.0 PKCE authentication for Google Chat, Google Messages, Google Keep, Google Tasks, and Workspace services.")
        sec_desc.add_css_class("section-desc")
        sec_desc.set_halign(Gtk.Align.START)
        sec_desc.set_wrap(True)
        page_vbox.append(sec_desc)

        # Group Card 1: Controlled Service Tabs
        tabs_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        tabs_card.add_css_class("settings-group-card")
        tabs_card.set_hexpand(True)

        tabs_header = Gtk.Label()
        tabs_header.set_markup("<span size='medium' weight='bold'>Controlled Service Tabs</span>")
        tabs_header.set_halign(Gtk.Align.START)
        tabs_card.append(tabs_header)

        tabs_desc = Gtk.Label(label="Toggle background memory mounting for individual Google services.")
        tabs_desc.add_css_class("section-desc")
        tabs_desc.set_halign(Gtk.Align.START)
        tabs_desc.set_wrap(True)
        tabs_card.append(tabs_desc)

        self.google_tabs_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.google_tabs_vbox.add_css_class("service-tabs-list")
        self.google_tabs_vbox.set_hexpand(True)
        tabs_card.append(self.google_tabs_vbox)
        page_vbox.append(tabs_card)

        # Group Card 2: Google Auth Cards
        auth_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        auth_card.add_css_class("settings-group-card")
        auth_card.set_hexpand(True)

        auth_header = Gtk.Label()
        auth_header.set_markup("<span size='medium' weight='bold'>Google Auth Cards</span>")
        auth_header.set_halign(Gtk.Align.START)
        auth_card.append(auth_header)

        auth_desc = Gtk.Label(label="Active card is illuminated. Exactly one card is active per provider pool.")
        auth_desc.add_css_class("section-desc")
        auth_desc.set_halign(Gtk.Align.START)
        auth_desc.set_wrap(True)
        auth_card.append(auth_desc)

        self.cards_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.cards_vbox.set_hexpand(True)
        auth_card.append(self.cards_vbox)

        add_user_btn = Gtk.Button(label="+ Add Google Auth Card")
        add_user_btn.add_css_class("add-account-btn")
        add_user_btn.set_hexpand(True)
        add_user_btn.connect("clicked", self._on_add_google_card_clicked)
        auth_card.append(add_user_btn)

        page_vbox.append(auth_card)

        scrolled.set_child(page_vbox)
        return scrolled

    def _build_nytimes_page(self) -> Gtk.ScrolledWindow:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        page_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page_vbox.set_hexpand(True)

        header_title = Gtk.Label()
        header_title.set_markup("<span size='x-large' weight='bold'>New York Times Service Logins</span>")
        header_title.set_halign(Gtk.Align.START)
        page_vbox.append(header_title)

        sec_desc = Gtk.Label(label="Authentication & Subscription management for NYTimes Wordle and Games services.")
        sec_desc.add_css_class("section-desc")
        sec_desc.set_halign(Gtk.Align.START)
        sec_desc.set_wrap(True)
        page_vbox.append(sec_desc)

        # Group Card 1: Controlled Service Tabs
        tabs_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        tabs_card.add_css_class("settings-group-card")
        tabs_card.set_hexpand(True)

        tabs_header = Gtk.Label()
        tabs_header.set_markup("<span size='medium' weight='bold'>Controlled Service Tabs</span>")
        tabs_header.set_halign(Gtk.Align.START)
        tabs_card.append(tabs_header)

        tabs_desc = Gtk.Label(label="Toggle background memory mounting for NYTimes Wordle.")
        tabs_desc.add_css_class("section-desc")
        tabs_desc.set_halign(Gtk.Align.START)
        tabs_desc.set_wrap(True)
        tabs_card.append(tabs_desc)

        self.nytimes_tabs_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nytimes_tabs_vbox.add_css_class("service-tabs-list")
        self.nytimes_tabs_vbox.set_hexpand(True)
        tabs_card.append(self.nytimes_tabs_vbox)
        page_vbox.append(tabs_card)

        # Group Card 2: NYTimes Auth Cards
        auth_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        auth_card.add_css_class("settings-group-card")
        auth_card.set_hexpand(True)

        auth_header = Gtk.Label()
        auth_header.set_markup("<span size='medium' weight='bold'>NYTimes Auth Cards</span>")
        auth_header.set_halign(Gtk.Align.START)
        auth_card.append(auth_header)

        auth_desc = Gtk.Label(label="Manage New York Times authentication and Games subscription status.")
        auth_desc.add_css_class("section-desc")
        auth_desc.set_halign(Gtk.Align.START)
        auth_desc.set_wrap(True)
        auth_card.append(auth_desc)

        self.nytimes_cards_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.nytimes_cards_vbox.set_hexpand(True)
        auth_card.append(self.nytimes_cards_vbox)

        add_nyt_user_btn = Gtk.Button(label="+ Add NYTimes Auth Card")
        add_nyt_user_btn.add_css_class("add-account-btn")
        add_nyt_user_btn.set_hexpand(True)
        add_nyt_user_btn.connect("clicked", self._on_add_nytimes_card_clicked)
        auth_card.append(add_nyt_user_btn)

        page_vbox.append(auth_card)

        scrolled.set_child(page_vbox)
        return scrolled

    def _build_tabs_page(self) -> Gtk.ScrolledWindow:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        page_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page_vbox.set_hexpand(True)

        header_title = Gtk.Label()
        header_title.set_markup("<span size='x-large' weight='bold'>Tab Layout &amp; Interface</span>")
        header_title.set_halign(Gtk.Align.START)
        page_vbox.append(header_title)

        sec_desc = Gtk.Label(
            label="Customize tab positions in the top bar. Tabs can be dragged to rearrange when active. "
                  "Order persists automatically across application sessions."
        )
        sec_desc.add_css_class("section-desc")
        sec_desc.set_halign(Gtk.Align.START)
        sec_desc.set_wrap(True)
        page_vbox.append(sec_desc)

        # Group Card: Tab Reordering & Reset
        order_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        order_card.add_css_class("settings-group-card")
        order_card.set_hexpand(True)

        order_header = Gtk.Label()
        order_header.set_markup("<span size='medium' weight='bold'>Tab Order Customization</span>")
        order_header.set_halign(Gtk.Align.START)
        order_card.append(order_header)

        order_desc = Gtk.Label(
            label="Drag any tab header in the top bar when selected to change position. "
                  "Resetting returns tabs to the factory default sequence."
        )
        order_desc.add_css_class("section-desc")
        order_desc.set_halign(Gtk.Align.START)
        order_desc.set_wrap(True)
        order_card.append(order_desc)

        # Summary box showing default sequence
        seq_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        seq_title = Gtk.Label(label="Default Tab Sequence:")
        seq_title.add_css_class("settings-meta-item")
        seq_title.set_halign(Gtk.Align.START)
        seq_box.append(seq_title)

        seq_list = Gtk.Label(label="1. Chat  •  2. Messages  •  3. Tasks  •  4. Keep  •  5. Wordle")
        seq_list.add_css_class("settings-meta-value")
        seq_list.set_halign(Gtk.Align.START)
        seq_list.set_wrap(True)
        seq_box.append(seq_list)
        order_card.append(seq_box)

        # Reset button
        reset_tabs_btn = Gtk.Button(label="↺ Reset Tab Order to Default")
        reset_tabs_btn.add_css_class("reset-tabs-btn")
        reset_tabs_btn.set_hexpand(True)
        reset_tabs_btn.connect("clicked", self._on_reset_tab_order_clicked)
        order_card.append(reset_tabs_btn)

        # Reset status label
        self.reset_status_label = Gtk.Label(label="")
        self.reset_status_label.add_css_class("reset-status-label")
        self.reset_status_label.set_halign(Gtk.Align.START)
        self.reset_status_label.set_wrap(True)
        self.reset_status_label.set_visible(False)
        order_card.append(self.reset_status_label)

        page_vbox.append(order_card)

        scrolled.set_child(page_vbox)
        return scrolled

    def _build_system_page(self) -> Gtk.ScrolledWindow:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        page_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page_vbox.set_hexpand(True)

        header_title = Gtk.Label()
        header_title.set_markup("<span size='x-large' weight='bold'>System &amp; Diagnostics</span>")
        header_title.set_halign(Gtk.Align.START)
        page_vbox.append(header_title)

        sec_desc = Gtk.Label(label="Application environment, desktop integration, and runtime diagnostic values.")
        sec_desc.add_css_class("section-desc")
        sec_desc.set_halign(Gtk.Align.START)
        sec_desc.set_wrap(True)
        page_vbox.append(sec_desc)

        # Group Card 1: Desktop Settings & Gestures
        desktop_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        desktop_card.add_css_class("settings-group-card")
        desktop_card.set_hexpand(True)

        desktop_header = Gtk.Label()
        desktop_header.set_markup("<span size='medium' weight='bold'>Native Desktop Integration</span>")
        desktop_header.set_halign(Gtk.Align.START)
        desktop_card.append(desktop_header)

        gtk_settings = Gtk.Settings.get_default()
        dc_time = gtk_settings.get_property("gtk-double-click-time") if gtk_settings else 400

        dc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dc_lbl = Gtk.Label(label="Double-Click Refresh Interval:")
        dc_lbl.add_css_class("settings-meta-item")
        dc_lbl.set_halign(Gtk.Align.START)
        dc_val = Gtk.Label(label=f"{dc_time} ms")
        dc_val.add_css_class("settings-meta-value")
        dc_row.append(dc_lbl)
        dc_row.append(dc_val)
        desktop_card.append(dc_row)

        dc_desc = Gtk.Label(label="Double-click any active tab header to reload its web contents.")
        dc_desc.add_css_class("section-desc")
        dc_desc.set_halign(Gtk.Align.START)
        dc_desc.set_wrap(True)
        desktop_card.append(dc_desc)
        page_vbox.append(desktop_card)

        # Group Card 2: Environment Details
        env_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        env_card.add_css_class("settings-group-card")
        env_card.set_hexpand(True)

        env_header = Gtk.Label()
        env_header.set_markup("<span size='medium' weight='bold'>Philotes Environment</span>")
        env_header.set_halign(Gtk.Align.START)
        env_card.append(env_header)

        meta_rows = [
            ("Version:", f"Philotes {__version__}"),
            ("Toolkit:", "GTK 4.22 & WebKitGTK 6.0"),
            ("Architecture:", "Multi-Process Isolated WebViews"),
            ("Process Names:", "philo-chat, philo-msgs"),
            ("Config Directory:", "~/.config/philotes"),
        ]

        for label_text, val_text in meta_rows:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl = Gtk.Label(label=label_text)
            lbl.add_css_class("settings-meta-item")
            lbl.set_halign(Gtk.Align.START)
            val = Gtk.Label(label=val_text)
            val.add_css_class("settings-meta-value")
            val.set_halign(Gtk.Align.START)
            row.append(lbl)
            row.append(val)
            env_card.append(row)

        page_vbox.append(env_card)

        scrolled.set_child(page_vbox)
        return scrolled

    def show_alert_message(self, message: str):
        if message:
            self.alert_banner.set_text(f"⚠️ {message}")
            self.alert_banner.set_visible(True)
        else:
            self.alert_banner.set_visible(False)

    def reload(self):
        self._select_category("google")
        self.refresh_cards()

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

        # Refresh Service Tabs
        self.refresh_service_tabs()

    def refresh_service_tabs(self):
        # Refresh Google service tabs
        while child := self.google_tabs_vbox.get_first_child():
            self.google_tabs_vbox.remove(child)
        for tab_id in SERVICE_POOLS.get("google", {}).get("tabs", []):
            row = self._create_service_tab_row(tab_id)
            self.google_tabs_vbox.append(row)

        # Refresh NYTimes service tabs
        while child := self.nytimes_tabs_vbox.get_first_child():
            self.nytimes_tabs_vbox.remove(child)
        for tab_id in SERVICE_POOLS.get("nytimes", {}).get("tabs", []):
            row = self._create_service_tab_row(tab_id)
            self.nytimes_tabs_vbox.append(row)

    def _create_service_tab_row(self, tab_id: str) -> Gtk.Box:
        meta = TAB_METADATA.get(tab_id, {})
        tab_name = meta.get("name", tab_id.title())

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        row.add_css_class("service-tab-row")
        row.set_hexpand(True)

        label = Gtk.Label(label=tab_name)
        label.add_css_class("service-tab-label")
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        row.append(label)

        # State detection: strictly from SettingsManager, NOT UI text
        is_enabled = SettingsManager.get_instance().is_tab_enabled(tab_id)

        badge = Gtk.Label(label="Enabled" if is_enabled else "Disabled")
        badge.add_css_class("service-tab-badge-enabled" if is_enabled else "service-tab-badge-disabled")
        row.append(badge)

        toggle_btn = Gtk.Button(label="Disable" if is_enabled else "Enable")
        toggle_btn.add_css_class("service-tab-toggle-btn")
        toggle_btn.add_css_class("service-tab-btn-disable" if is_enabled else "service-tab-btn-enable")
        toggle_btn.connect("clicked", lambda b, tid=tab_id: self._on_toggle_tab_clicked(tid))
        row.append(toggle_btn)

        return row

    def _on_toggle_tab_clicked(self, tab_id: str):
        settings_mgr = SettingsManager.get_instance()
        current_state = settings_mgr.is_tab_enabled(tab_id)
        new_state = not current_state
        settings_mgr.set_tab_enabled(tab_id, new_state)
        self.refresh_service_tabs()
        if self.on_tab_toggled_cb:
            self.on_tab_toggled_cb(tab_id, new_state)

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

    def _on_reset_tab_order_clicked(self, widget):
        if self.on_reset_tab_order_cb:
            self.on_reset_tab_order_cb()
        self.reset_status_label.set_text("✓ Tab order reset to default: Chat, Messages, Tasks, Keep, Wordle")
        self.reset_status_label.set_visible(True)


