import sys
import os
import json
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib

from philotes.process_utils import set_process_name
from philotes.config import (
    APP_NAME,
    ICON_HICOLOR_CHAT,
    ICON_GREYSCALE_CHAT,
    THEME_CSS_PATH,
)
from philotes.subapps.philo_chat import PhiloChatApp
from philotes.auth import GCPAuthManager


class PhilotesWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Philotes")
        set_process_name(APP_NAME)
        self.set_default_size(1150, 750)

        self.current_tab = "chat"
        self.unread_chat_count = 0

        self._load_theme()

        root_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root_vbox)

        # Top Bar Container
        self.top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.top_bar.set_name("top-bar")

        # Left Tab Bar
        self.tabs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.tabs_box.set_hexpand(True)

        self.chat_tab_button = Gtk.Button()
        self.chat_tab_button.connect("clicked", self._on_chat_tab_clicked)
        
        self.chat_tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.chat_icon_img = Gtk.Image()
        self.chat_label = Gtk.Label(label="Chat")
        self.chat_label.add_css_class("tab-label")

        self.chat_badge = Gtk.Label(label="")
        self.chat_badge.add_css_class("badge")
        self.chat_badge.add_css_class("badge-hidden")

        self.chat_tab_box.append(self.chat_icon_img)
        self.chat_tab_box.append(self.chat_label)
        self.chat_tab_box.append(self.chat_badge)
        self.chat_tab_button.set_child(self.chat_tab_box)

        self.tabs_box.append(self.chat_tab_button)
        self.top_bar.append(self.tabs_box)

        # Right Settings Button
        self.settings_button = Gtk.Button()
        self.settings_button.set_name("settings-button")
        self.settings_button.connect("clicked", self._on_settings_tab_clicked)
        self.settings_button.set_halign(Gtk.Align.END)
        
        settings_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        settings_label = Gtk.Label(label="⚙")
        settings_box.append(settings_label)
        self.settings_button.set_child(settings_box)

        self.top_bar.append(self.settings_button)
        root_vbox.append(self.top_bar)

        # Main Content View Stack
        self.stack = Gtk.Stack()
        self.stack.set_name("content-stack")
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        root_vbox.append(self.stack)

        self._init_philo_chat()

        # Settings View
        self.settings_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.settings_view.set_name("settings-view")
        self.settings_view.set_valign(Gtk.Align.CENTER)
        self.settings_view.set_halign(Gtk.Align.CENTER)
        
        settings_title = Gtk.Label()
        settings_title.set_markup("<span size='x-large' weight='bold'>Philotes Settings &amp; Authorization</span>")
        
        self.auth_manager = GCPAuthManager()
        self.auth_status_label = Gtk.Label()
        self._update_auth_status_label()

        self.login_btn = Gtk.Button(label="Sign in with Google (GCP OAuth)")
        self.login_btn.connect("clicked", self._on_login_clicked)

        self.settings_view.append(settings_title)
        self.settings_view.append(self.auth_status_label)
        self.settings_view.append(self.login_btn)
        
        self.stack.add_named(self.settings_view, "settings")
        self._update_tab_ui()

    def _update_auth_status_label(self):
        if self.auth_manager.is_authenticated():
            self.auth_status_label.set_markup("<span color='#7aa2f7' weight='bold'>Status: Authenticated (Permanent Token Saved)</span>")
        elif self.auth_manager.is_configured():
            self.auth_status_label.set_markup("<span color='#e0af68'>Status: GCP Credentials Loaded. Ready for Sign-In.</span>")
        else:
            self.auth_status_label.set_markup("<span color='#f7768e'>Status: Missing client_secret.json in ~/.config/philotes/</span>")

    def _on_login_clicked(self, widget):
        if not self.auth_manager.is_configured():
            sys.stderr.write("[Philotes] Please place your GCP client_secret.json in ~/.config/philotes/\n")
            return
        
        try:
            tokens = self.auth_manager.perform_pkce_login()
            self._update_auth_status_label()
        except Exception as e:
            sys.stderr.write(f"[Philotes Auth Error] {e}\n")

    def _load_theme(self):
        css_provider = Gtk.CssProvider()
        if THEME_CSS_PATH.exists():
            css_provider.load_from_path(str(THEME_CSS_PATH))
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
        else:
            sys.stderr.write(f"[Philotes] Warning: CSS theme not found at {THEME_CSS_PATH}\n")

    def _init_philo_chat(self):
        read_fd, write_fd = os.pipe()
        self.chat_app = PhiloChatApp(ipc_write_fd=write_fd)
        chat_widget = self.chat_app.get_widget()
        self.stack.add_named(chat_widget, "chat")

        GLib.io_add_watch(read_fd, GLib.IO_IN, self._on_ipc_data_received)

    def _on_ipc_data_received(self, source, condition):
        if condition & GLib.IO_IN:
            try:
                data = os.read(source, 1024).decode("utf-8")
                for line in data.strip().split("\n"):
                    if not line:
                        continue
                    msg = json.loads(line)
                    if msg.get("type") == "unread_count":
                        self.unread_chat_count = msg.get("count", 0)
                        GLib.idle_add(self._update_tab_ui)
            except Exception as e:
                sys.stderr.write(f"[Philotes] IPC read parse error: {e}\n")
        return True

    def _on_chat_tab_clicked(self, widget):
        self.current_tab = "chat"
        self.stack.set_visible_child_name("chat")
        self._update_tab_ui()

    def _on_settings_tab_clicked(self, widget):
        self.current_tab = "settings"
        self.stack.set_visible_child_name("settings")
        self._update_tab_ui()

    def _update_tab_ui(self):
        if self.current_tab == "chat":
            self.chat_tab_button.remove_css_class("tab-button-inactive")
            self.chat_tab_button.add_css_class("tab-button")
            self.chat_tab_button.add_css_class("tab-button-active")
            self._set_image_from_svg(self.chat_icon_img, ICON_HICOLOR_CHAT)
            self.chat_label.set_visible(True)
        else:
            self.chat_tab_button.remove_css_class("tab-button-active")
            self.chat_tab_button.add_css_class("tab-button")
            self.chat_tab_button.add_css_class("tab-button-inactive")
            self._set_image_from_svg(self.chat_icon_img, ICON_GREYSCALE_CHAT)
            self.chat_label.set_visible(False)

        if self.unread_chat_count > 0:
            self.chat_badge.set_text(str(self.unread_chat_count))
            self.chat_badge.remove_css_class("badge-hidden")
        else:
            self.chat_badge.set_text("")
            self.chat_badge.add_css_class("badge-hidden")

    def _set_image_from_svg(self, gtk_image, svg_path):
        if svg_path.exists():
            try:
                gtk_image.set_from_file(str(svg_path))
                gtk_image.set_pixel_size(20)
            except Exception as e:
                sys.stderr.write(f"[Philotes] Error loading SVG {svg_path}: {e}\n")


def main():
    set_process_name(APP_NAME)
    app = Gtk.Application(application_id="com.philotes.app")
    
    def on_activate(gtk_app):
        win = PhilotesWindow(gtk_app)
        win.present()
        win._update_tab_ui()

    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    main()
