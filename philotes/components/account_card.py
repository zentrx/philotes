import sys
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from philotes.account_manager import AccountManager

class AccountCardWidget(Gtk.Box):
    def __init__(self, account_data: dict, on_state_changed_cb=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.account_data = account_data
        self.on_state_changed_cb = on_state_changed_cb
        self.is_confirming_delete = False

        self.set_name("account-card")
        self._apply_border_style()

        # Left Delete Button Box
        self.left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.left_box.set_valign(Gtk.Align.START)
        self._render_left_delete_buttons()
        self.append(self.left_box)

        # Center Info VBox
        info_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_vbox.set_hexpand(True)

        display_name = account_data.get("display_name", "Google User")
        username = account_data.get("username", "user@gmail.com")
        created_at = account_data.get("created_at", "Unknown")
        unread_count = account_data.get("unread_count", 0)

        # Name Label
        name_label = Gtk.Label()
        name_label.set_markup(f"<span weight='bold' size='large'>{display_name}</span>")
        name_label.set_halign(Gtk.Align.START)

        # Username / Email Label
        user_label = Gtk.Label(label=username)
        user_label.add_css_class("card-username")
        user_label.set_halign(Gtk.Align.START)

        # Created At Label
        time_label = Gtk.Label(label=f"Created: {created_at}")
        time_label.add_css_class("card-time")
        time_label.set_halign(Gtk.Align.START)

        info_vbox.append(name_label)
        info_vbox.append(user_label)
        info_vbox.append(time_label)
        self.append(info_vbox)

        # Right Status & Default Toggle Box
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        right_box.set_valign(Gtk.Align.START)

        if unread_count > 0:
            badge = Gtk.Label(label=f"{unread_count} unread")
            badge.add_css_class("badge")
            right_box.append(badge)

        provider = account_data.get("provider")
        if provider == "nytimes":
            is_sub = account_data.get("subscribed", True)
            sub_btn = Gtk.Button(label="✓ Subscribed" if is_sub else "✗ No Sub")
            if is_sub:
                sub_btn.add_css_class("card-default-btn-active")
            else:
                sub_btn.add_css_class("card-default-btn-inactive")
            sub_btn.connect("clicked", self._on_sub_toggle_clicked)
            right_box.append(sub_btn)

        # Default Toggle Button
        is_default = account_data.get("default", False)
        default_btn = Gtk.Button(label="★ Default" if is_default else "Make Default")
        if is_default:
            default_btn.add_css_class("card-default-btn-active")
        else:
            default_btn.add_css_class("card-default-btn-inactive")
        
        default_btn.connect("clicked", self._on_default_toggle_clicked)
        right_box.append(default_btn)

        self.append(right_box)

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
