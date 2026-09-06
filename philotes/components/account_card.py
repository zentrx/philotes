import sys
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from philotes.account_manager import AccountManager

class AccountCardWidget(Gtk.Box):
    def __init__(self, account_data: dict, on_state_changed_cb=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.account_data = account_data
        self.on_state_changed_cb = on_state_changed_cb
        self.is_confirming_delete = False

        self.set_name("account-card")
        self._apply_border_style()

        display_name = account_data.get("display_name", "Google User")
        username = account_data.get("username", "user@gmail.com")
        created_at = account_data.get("created_at", "Unknown")
        unread_count = account_data.get("unread_count", 0)
        is_active = account_data.get("active", False)
        is_default = account_data.get("default", False)
        provider = account_data.get("provider")

        # 1. Header Row (Name + Active status pill + Unread badge)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_box.set_hexpand(True)

        name_label = Gtk.Label()
        name_label.set_markup(f"<span weight='bold' size='large'>{display_name}</span>")
        name_label.set_halign(Gtk.Align.START)
        name_label.set_hexpand(True)
        header_box.append(name_label)

        if unread_count > 0:
            badge = Gtk.Label(label=f"{unread_count} unread")
            badge.add_css_class("badge")
            header_box.append(badge)

        status_pill = Gtk.Label(label="● Active" if is_active else "Inactive")
        status_pill.add_css_class("card-active-pill" if is_active else "card-inactive-pill")
        header_box.append(status_pill)
        self.append(header_box)

        # 2. Middle Info Row (Username + Created At)
        info_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_vbox.set_halign(Gtk.Align.START)

        user_label = Gtk.Label(label=username)
        user_label.add_css_class("card-username")
        user_label.set_halign(Gtk.Align.START)

        time_label = Gtk.Label(label=f"Created: {created_at}")
        time_label.add_css_class("card-time")
        time_label.set_halign(Gtk.Align.START)

        info_vbox.append(user_label)
        info_vbox.append(time_label)
        self.append(info_vbox)

        # 3. Actions Row (Delete button left, Default & Sub buttons right)
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions_box.set_hexpand(True)

        self.left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.left_box.set_halign(Gtk.Align.START)
        self._render_left_delete_buttons()
        actions_box.append(self.left_box)

        right_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        right_actions.set_halign(Gtk.Align.END)
        right_actions.set_hexpand(True)

        if provider == "nytimes":
            is_sub = account_data.get("subscribed", True)
            sub_btn = Gtk.Button(label="✓ Subscribed" if is_sub else "✗ No Sub")
            sub_btn.add_css_class("card-default-btn-active" if is_sub else "card-default-btn-inactive")
            sub_btn.connect("clicked", self._on_sub_toggle_clicked)
            right_actions.append(sub_btn)

        default_btn = Gtk.Button(label="★ Default" if is_default else "Make Default")
        default_btn.add_css_class("card-default-btn-active" if is_default else "card-default-btn-inactive")
        default_btn.connect("clicked", self._on_default_toggle_clicked)
        right_actions.append(default_btn)

        actions_box.append(right_actions)
        self.append(actions_box)

        # Click Controller on Card Body for Active Toggling
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", self._on_card_pressed)
        self.add_controller(gesture)

    def _apply_border_style(self):
        is_active = self.account_data.get("active", False)
        if is_active:
            self.remove_css_class("account-card-inactive")
            self.add_css_class("account-card")
            self.add_css_class("account-card-active")
        else:
            self.remove_css_class("account-card-active")
            self.add_css_class("account-card")
            self.add_css_class("account-card-inactive")

    def _render_left_delete_buttons(self):
        while child := self.left_box.get_first_child():
            self.left_box.remove(child)

        if self.is_confirming_delete:
            confirm_btn = Gtk.Button(label="Confirm Delete")
            confirm_btn.add_css_class("card-confirm-delete-btn")
            confirm_btn.connect("clicked", self._on_confirm_delete_clicked)

            cancel_btn = Gtk.Button(label="Cancel")
            cancel_btn.add_css_class("card-cancel-delete-btn")
            cancel_btn.connect("clicked", self._on_cancel_delete_clicked)

            self.left_box.append(confirm_btn)
            self.left_box.append(cancel_btn)
        else:
            delete_btn = Gtk.Button(label="🗑")
            delete_btn.add_css_class("card-delete-btn")
            delete_btn.connect("clicked", self._on_delete_trash_clicked)
            self.left_box.append(delete_btn)

    def _on_card_pressed(self, gesture, n_press, x, y):
        if self.is_confirming_delete:
            return

        provider = self.account_data.get("provider")
        card_id = self.account_data.get("card_id")
        
        AccountManager.get_instance().set_active(card_id, provider)
        
        if self.on_state_changed_cb:
            self.on_state_changed_cb()

    def _on_sub_toggle_clicked(self, widget):
        provider = self.account_data.get("provider")
        card_id = self.account_data.get("card_id")
        
        AccountManager.get_instance().toggle_subscription(card_id, provider)
        
        if self.on_state_changed_cb:
            self.on_state_changed_cb()

    def _on_default_toggle_clicked(self, widget):
        provider = self.account_data.get("provider")
        card_id = self.account_data.get("card_id")
        
        AccountManager.get_instance().set_default(card_id, provider)
        
        if self.on_state_changed_cb:
            self.on_state_changed_cb()

    def _on_delete_trash_clicked(self, widget):
        self.is_confirming_delete = True
        self._render_left_delete_buttons()

    def _on_cancel_delete_clicked(self, widget):
        self.is_confirming_delete = False
        self._render_left_delete_buttons()

    def _on_confirm_delete_clicked(self, widget):
        provider = self.account_data.get("provider")
        card_id = self.account_data.get("card_id")
        AccountManager.get_instance().delete_auth_card(card_id, provider)
        if self.on_state_changed_cb:
            self.on_state_changed_cb()
