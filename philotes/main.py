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
    ICON_HICOLOR_MSGS,
    ICON_GREYSCALE_MSGS,
    ICON_HICOLOR_WORDLE,
    ICON_GREYSCALE_WORDLE,
    ICON_HICOLOR_KEEP,
    ICON_GREYSCALE_KEEP,
    ICON_HICOLOR_PHILOTES,
    ICON_GREYSCALE_PHILOTES,
    THEME_CSS_PATH,
)
from philotes.subapps.philo_chat import PhiloChatApp
from philotes.subapps.philo_msgs import PhiloMsgsApp
from philotes.subapps.philo_wordle import PhiloWordleApp
from philotes.subapps.philo_keep import PhiloKeepApp
from philotes.account_manager import AccountManager
from philotes.views.settings_view import SettingsView
from philotes.components.splash_view import SplashView


class PhilotesWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Philotes")
        set_process_name(APP_NAME)
        self.set_default_size(1150, 750)

        total_cards = AccountManager.get_instance().get_total_card_count()
        # Rule: If no Auth Cards present, bring user to Settings tab on launch
        if total_cards == 0:
            self.current_tab = "settings"
        else:
            self.current_tab = "chat"

        self.unread_chat_count = 0
        self.unread_msgs_count = 0
        self.unread_keep_count = 0
        self.chat_selected_title = None
        self.msgs_selected_title = None
        self.wordle_completed = True
        self.wordle_selected_title = None

        self._load_theme()

        root_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root_vbox)

        # Top Bar Container
        self.top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.top_bar.set_name("top-bar")

        # Left Tab Bar
        self.tabs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.tabs_box.set_hexpand(True)

        # Chat Tab Button
        self.chat_tab_button = Gtk.Button()
        self.chat_tab_button.connect("clicked", self._on_chat_tab_clicked)
        
        self.chat_tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.chat_tab_box.set_halign(Gtk.Align.CENTER)
        self.chat_tab_box.set_valign(Gtk.Align.CENTER)
        self.chat_overlay = Gtk.Overlay()
        self.chat_icon_img = Gtk.Image()
        self.chat_icon_img.add_css_class("tab-icon-img")
        self.chat_overlay.set_child(self.chat_icon_img)

        self.chat_overlay_badge = Gtk.Label(label="")
        self.chat_overlay_badge.add_css_class("badge")
        self.chat_overlay_badge.add_css_class("badge-overlay")
        self.chat_overlay_badge.set_halign(Gtk.Align.END)
        self.chat_overlay_badge.set_valign(Gtk.Align.START)
        self.chat_overlay.add_overlay(self.chat_overlay_badge)

        self.chat_label = Gtk.Label(label="Chat")
        self.chat_label.add_css_class("tab-label")

        self.chat_badge = Gtk.Label(label="")
        self.chat_badge.add_css_class("badge")
        self.chat_badge.add_css_class("badge-hidden")

        self.chat_tab_box.append(self.chat_overlay)
        self.chat_tab_box.append(self.chat_label)
        self.chat_tab_box.append(self.chat_badge)
        self.chat_tab_button.set_child(self.chat_tab_box)
        self.tabs_box.append(self.chat_tab_button)

        # Messages Tab Button
        self.msgs_tab_button = Gtk.Button()
        self.msgs_tab_button.connect("clicked", self._on_msgs_tab_clicked)

        self.msgs_tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.msgs_tab_box.set_halign(Gtk.Align.CENTER)
        self.msgs_tab_box.set_valign(Gtk.Align.CENTER)
        self.msgs_overlay = Gtk.Overlay()
        self.msgs_icon_img = Gtk.Image()
        self.msgs_icon_img.add_css_class("tab-icon-img")
        self.msgs_overlay.set_child(self.msgs_icon_img)

        self.msgs_overlay_badge = Gtk.Label(label="")
        self.msgs_overlay_badge.add_css_class("badge")
        self.msgs_overlay_badge.add_css_class("badge-overlay")
        self.msgs_overlay_badge.set_halign(Gtk.Align.END)
        self.msgs_overlay_badge.set_valign(Gtk.Align.START)
        self.msgs_overlay.add_overlay(self.msgs_overlay_badge)

        self.msgs_label = Gtk.Label(label="Messages")
        self.msgs_label.add_css_class("tab-label")

        self.msgs_badge = Gtk.Label(label="")
        self.msgs_badge.add_css_class("badge")
        self.msgs_badge.add_css_class("badge-hidden")

        self.msgs_tab_box.append(self.msgs_overlay)
        self.msgs_tab_box.append(self.msgs_label)
        self.msgs_tab_box.append(self.msgs_badge)
        self.msgs_tab_button.set_child(self.msgs_tab_box)
        self.tabs_box.append(self.msgs_tab_button)

        # Keep Tab Button
        self.keep_tab_button = Gtk.Button()
        self.keep_tab_button.connect("clicked", self._on_keep_tab_clicked)

        self.keep_tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.keep_tab_box.set_halign(Gtk.Align.CENTER)
        self.keep_tab_box.set_valign(Gtk.Align.CENTER)
        self.keep_overlay = Gtk.Overlay()
        self.keep_icon_img = Gtk.Image()
        self.keep_icon_img.add_css_class("tab-icon-img")
        self.keep_overlay.set_child(self.keep_icon_img)

        self.keep_overlay_badge = Gtk.Label(label="")
        self.keep_overlay_badge.add_css_class("badge")
        self.keep_overlay_badge.add_css_class("badge-overlay")
        self.keep_overlay_badge.set_halign(Gtk.Align.END)
        self.keep_overlay_badge.set_valign(Gtk.Align.START)
        self.keep_overlay.add_overlay(self.keep_overlay_badge)

        self.keep_label = Gtk.Label(label="Keep")
        self.keep_label.add_css_class("tab-label")

        self.keep_badge = Gtk.Label(label="")
        self.keep_badge.add_css_class("badge")
        self.keep_badge.add_css_class("badge-hidden")

        self.keep_tab_box.append(self.keep_overlay)
        self.keep_tab_box.append(self.keep_label)
        self.keep_tab_box.append(self.keep_badge)
        self.keep_tab_button.set_child(self.keep_tab_box)
        self.tabs_box.append(self.keep_tab_button)

        # Wordle Tab Button
        self.wordle_tab_button = Gtk.Button()
        self.wordle_tab_button.connect("clicked", self._on_wordle_tab_clicked)

        self.wordle_tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.wordle_tab_box.set_halign(Gtk.Align.CENTER)
        self.wordle_tab_box.set_valign(Gtk.Align.CENTER)
        self.wordle_overlay = Gtk.Overlay()
        self.wordle_icon_img = Gtk.Image()
        self.wordle_icon_img.add_css_class("tab-icon-img")
        self.wordle_overlay.set_child(self.wordle_icon_img)

        self.wordle_overlay_badge = Gtk.Box()
        self.wordle_overlay_badge.add_css_class("badge-blue-dot")
        self.wordle_overlay_badge.set_halign(Gtk.Align.END)
        self.wordle_overlay_badge.set_valign(Gtk.Align.START)
        self.wordle_overlay_badge.set_visible(False)
        self.wordle_overlay.add_overlay(self.wordle_overlay_badge)

        self.wordle_label = Gtk.Label(label="Wordle")
        self.wordle_label.add_css_class("tab-label")

        self.wordle_tab_box.append(self.wordle_overlay)
        self.wordle_tab_box.append(self.wordle_label)
        self.wordle_tab_button.set_child(self.wordle_tab_box)
        self.tabs_box.append(self.wordle_tab_button)

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
        self.set_child(root_vbox)

        self._init_chat_view()
        self._init_msgs_view()
        self._init_wordle_view()
        self._init_keep_view()

        self.settings_view = SettingsView(on_accounts_changed_cb=self._on_accounts_changed)
        self.stack.add_named(self.settings_view, "settings")
        
        self.stack.set_visible_child_name(self.current_tab)
        self._update_tab_ui()
        self._update_header_title()

    def _init_chat_view(self):
        active_card = AccountManager.get_instance().get_active_card("google")
        
        if existing := self.stack.get_child_by_name("chat"):
            self.stack.remove(existing)

        if active_card is None:
            self.chat_app = None
            self.unread_chat_count = 0
            splash = SplashView("Google", on_goto_settings_cb=self._on_settings_tab_clicked)
            self.stack.add_named(splash, "chat")
        else:
            profile_id = active_card.get("profile_dir")
            username = active_card.get("username")
            self.unread_chat_count = active_card.get("unread_count", 0)
            read_fd, write_fd = os.pipe()
            self.chat_app = PhiloChatApp(ipc_write_fd=write_fd, profile_id=profile_id, username=username)
            chat_widget = self.chat_app.get_widget()
            self.stack.add_named(chat_widget, "chat")
            GLib.io_add_watch(read_fd, GLib.IO_IN, self._on_ipc_data_received)

    def _init_msgs_view(self):
        active_card = AccountManager.get_instance().get_active_card("google")
        
        if existing := self.stack.get_child_by_name("msgs"):
            self.stack.remove(existing)

        if active_card is None:
            self.msgs_app = None
            self.unread_msgs_count = 0
            splash = SplashView("Google", on_goto_settings_cb=self._on_settings_tab_clicked)
            self.stack.add_named(splash, "msgs")
        else:
            profile_id = active_card.get("profile_dir")
            username = active_card.get("username")
            self.unread_msgs_count = active_card.get("unread_count", 0)
            read_fd, write_fd = os.pipe()
            self.msgs_app = PhiloMsgsApp(ipc_write_fd=write_fd, profile_id=profile_id, username=username)
            msgs_widget = self.msgs_app.get_widget()
            self.stack.add_named(msgs_widget, "msgs")
            GLib.io_add_watch(read_fd, GLib.IO_IN, self._on_ipc_data_received)

    def _init_wordle_view(self):
        active_card = AccountManager.get_instance().get_active_card("nytimes")
        
        if existing := self.stack.get_child_by_name("wordle"):
            self.stack.remove(existing)

        if active_card is None or not active_card.get("subscribed", True):
            self.wordle_app = None
            splash = SplashView("NYTimes", on_goto_settings_cb=self._on_settings_tab_clicked)
            self.stack.add_named(splash, "wordle")
            return False
        else:
            profile_id = active_card.get("profile_dir")
            username = active_card.get("username")
            read_fd, write_fd = os.pipe()
            self.wordle_app = PhiloWordleApp(ipc_write_fd=write_fd, profile_id=profile_id, username=username)
            wordle_widget = self.wordle_app.get_widget()
            self.stack.add_named(wordle_widget, "wordle")
            GLib.io_add_watch(read_fd, GLib.IO_IN, self._on_ipc_data_received)
            return True

    def _init_keep_view(self):
        active_card = AccountManager.get_instance().get_active_card("google")
        
        if existing := self.stack.get_child_by_name("keep"):
            self.stack.remove(existing)

        if active_card is None:
            self.keep_app = None
            self.unread_keep_count = 0
            splash = SplashView("Google", on_goto_settings_cb=self._on_settings_tab_clicked)
            self.stack.add_named(splash, "keep")
        else:
            profile_id = active_card.get("profile_dir")
            username = active_card.get("username")
            self.unread_keep_count = active_card.get("unread_count", 0)
            read_fd, write_fd = os.pipe()
            self.keep_app = PhiloKeepApp(ipc_write_fd=write_fd, profile_id=profile_id, username=username)
            keep_widget = self.keep_app.get_widget()
            self.stack.add_named(keep_widget, "keep")
            GLib.io_add_watch(read_fd, GLib.IO_IN, self._on_ipc_data_received)

    def _on_accounts_changed(self):
        self._init_chat_view()
        self._init_msgs_view()
        self._init_wordle_view()
        self._init_keep_view()
        if self.current_tab in ("chat", "msgs", "wordle", "keep"):
            self.stack.set_visible_child_name(self.current_tab)
        self._update_tab_ui()

    def _load_theme(self):
        display = Gdk.Display.get_default()
        if display:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            if ICON_HICOLOR_PHILOTES.parent.exists():
                icon_theme.add_search_path(str(ICON_HICOLOR_PHILOTES.parent))

        css_provider = Gtk.CssProvider()
        if THEME_CSS_PATH.exists():
            css_provider.load_from_path(str(THEME_CSS_PATH))
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
        else:
            sys.stderr.write(f"[Philotes] Warning: CSS theme not found at {THEME_CSS_PATH}\n")

    def _on_ipc_data_received(self, source, condition):
        if condition & GLib.IO_IN:
            try:
                data = os.read(source, 1024).decode("utf-8")
                if not data:
                    return False
                for line in data.strip().split("\n"):
                    if not line:
                        continue
                    msg = json.loads(line)
                    msg_type = msg.get("type")
                    app_name = msg.get("app")

                    if msg_type in ("unread_count", "status_update", "title_update"):
                        if "count" in msg:
                            count = msg.get("count", 0)
                            if app_name == "msgs":
                                self.unread_msgs_count = count
                            elif app_name == "chat":
                                self.unread_chat_count = count
                            elif app_name == "keep":
                                self.unread_keep_count = count

                        if "completed" in msg and app_name == "wordle":
                            self.wordle_completed = msg.get("completed", False)

                        if "title" in msg:
                            title = msg.get("title")
                            if app_name == "msgs":
                                self.msgs_selected_title = title
                            elif app_name == "chat":
                                self.chat_selected_title = title
                            elif app_name == "wordle":
                                self.wordle_selected_title = title

                        GLib.idle_add(self._update_tab_ui)
                        GLib.idle_add(self._update_header_title)
                    elif msg_type == "auth_error" and app_name == "wordle":
                        reason = msg.get("reason")
                        err_msg = (
                            "No appropriate NYTimes Auth Card found in Service Pool."
                            if reason == "no_auth_card"
                            else "Your NYTimes Authorization does not include a valid subscription."
                        )
                        GLib.idle_add(lambda: self._redirect_to_settings_with_error(err_msg))
            except Exception as e:
                sys.stderr.write(f"[Philotes] IPC read parse error: {e}\n")
        return True

    def _redirect_to_settings_with_error(self, err_msg):
        self._on_settings_tab_clicked()
        self.settings_view.show_alert_message(err_msg)

    def _on_chat_tab_clicked(self, widget):
        self.current_tab = "chat"
        self.stack.set_visible_child_name("chat")
        self._update_tab_ui()
        self._update_header_title()

    def _on_msgs_tab_clicked(self, widget):
        self.current_tab = "msgs"
        self.stack.set_visible_child_name("msgs")
        self._update_tab_ui()
        self._update_header_title()

    def _on_keep_tab_clicked(self, widget=None):
        self.current_tab = "keep"
        self.stack.set_visible_child_name("keep")
        self._update_tab_ui()
        self._update_header_title()

    def _on_wordle_tab_clicked(self, widget=None):
        active_card = AccountManager.get_instance().get_active_card("nytimes")
        if active_card is None:
            self._on_settings_tab_clicked()
            self.settings_view.show_alert_message("No appropriate NYTimes Auth Card found in Service Pool.")
            return

        if not active_card.get("subscribed", True):
            self._on_settings_tab_clicked()
            self.settings_view.show_alert_message("Your NYTimes Authorization does not include a valid subscription.")
            return

        self.settings_view.show_alert_message(None)
        self._init_wordle_view()
        self.current_tab = "wordle"
        self.stack.set_visible_child_name("wordle")
        self._update_tab_ui()
        self._update_header_title()

    def _on_settings_tab_clicked(self, widget=None):
        self.current_tab = "settings"
        self.stack.set_visible_child_name("settings")
        self._update_tab_ui()
        self._update_header_title()

    def _update_header_title(self):
        if self.current_tab == "chat":
            tab_name = "Chat"
            selected_title = self.chat_selected_title
        elif self.current_tab == "msgs":
            tab_name = "Messages"
            selected_title = self.msgs_selected_title
        elif self.current_tab == "wordle":
            tab_name = "Wordle"
            selected_title = self.wordle_selected_title
        elif self.current_tab == "keep":
            tab_name = "Keep"
            selected_title = None
        elif self.current_tab == "settings":
            tab_name = "Settings"
            selected_title = None
        else:
            tab_name = self.current_tab.capitalize()
            selected_title = None

        if selected_title:
            full_title = f"Philotes | {tab_name} | {selected_title}"
        else:
            full_title = f"Philotes | {tab_name}"

        self.set_title(full_title)

    def _update_tab_ui(self):
        # Chat tab styling
        if self.current_tab == "chat":
            self.chat_tab_button.remove_css_class("tab-button-inactive")
            self.chat_tab_button.add_css_class("tab-button")
            self.chat_tab_button.add_css_class("tab-button-active")
            self._set_image_from_svg(self.chat_icon_img, ICON_HICOLOR_CHAT)
            self.chat_label.set_visible(True)
            self.chat_overlay_badge.set_visible(False)
            if self.unread_chat_count > 0:
                self.chat_badge.set_text(str(self.unread_chat_count))
                self.chat_badge.remove_css_class("badge-hidden")
                self.chat_badge.set_visible(True)
            else:
                self.chat_badge.set_text("")
                self.chat_badge.add_css_class("badge-hidden")
                self.chat_badge.set_visible(False)
        else:
            self.chat_tab_button.remove_css_class("tab-button-active")
            self.chat_tab_button.add_css_class("tab-button")
            self.chat_tab_button.add_css_class("tab-button-inactive")
            self._set_image_from_svg(self.chat_icon_img, ICON_GREYSCALE_CHAT)
            self.chat_label.set_visible(False)
            self.chat_badge.set_visible(False)
            if self.unread_chat_count > 0:
                self.chat_overlay_badge.set_text(str(self.unread_chat_count))
                self.chat_overlay_badge.remove_css_class("badge-hidden")
                self.chat_overlay_badge.set_visible(True)
            else:
                self.chat_overlay_badge.set_text("")
                self.chat_overlay_badge.add_css_class("badge-hidden")
                self.chat_overlay_badge.set_visible(False)

        # Messages tab styling
        if self.current_tab == "msgs":
            self.msgs_tab_button.remove_css_class("tab-button-inactive")
            self.msgs_tab_button.add_css_class("tab-button")
            self.msgs_tab_button.add_css_class("tab-button-active")
            self._set_image_from_svg(self.msgs_icon_img, ICON_HICOLOR_MSGS)
            self.msgs_label.set_visible(True)
            self.msgs_overlay_badge.set_visible(False)
            if self.unread_msgs_count > 0:
                self.msgs_badge.set_text(str(self.unread_msgs_count))
                self.msgs_badge.remove_css_class("badge-hidden")
                self.msgs_badge.set_visible(True)
            else:
                self.msgs_badge.set_text("")
                self.msgs_badge.add_css_class("badge-hidden")
                self.msgs_badge.set_visible(False)
        else:
            self.msgs_tab_button.remove_css_class("tab-button-active")
            self.msgs_tab_button.add_css_class("tab-button")
            self.msgs_tab_button.add_css_class("tab-button-inactive")
            self._set_image_from_svg(self.msgs_icon_img, ICON_GREYSCALE_MSGS)
            self.msgs_label.set_visible(False)
            self.msgs_badge.set_visible(False)
            if self.unread_msgs_count > 0:
                self.msgs_overlay_badge.set_text(str(self.unread_msgs_count))
                self.msgs_overlay_badge.remove_css_class("badge-hidden")
                self.msgs_overlay_badge.set_visible(True)
            else:
                self.msgs_overlay_badge.set_text("")
                self.msgs_overlay_badge.add_css_class("badge-hidden")
                self.msgs_overlay_badge.set_visible(False)

        # Wordle tab styling
        if self.current_tab == "wordle":
            self.wordle_tab_button.remove_css_class("tab-button-inactive")
            self.wordle_tab_button.add_css_class("tab-button")
            self.wordle_tab_button.add_css_class("tab-button-active")
            self._set_image_from_svg(self.wordle_icon_img, ICON_HICOLOR_WORDLE, fallback_icon_name="wayland")
            self.wordle_label.set_visible(True)
        else:
            self.wordle_tab_button.remove_css_class("tab-button-active")
            self.wordle_tab_button.add_css_class("tab-button")
            self.wordle_tab_button.add_css_class("tab-button-inactive")
            self._set_image_from_svg(self.wordle_icon_img, ICON_GREYSCALE_WORDLE, fallback_icon_name="wayland")
            self.wordle_label.set_visible(False)

        # Show small blue dot overlayed on icon top right corner if Wordle is incomplete
        if not self.wordle_completed:
            self.wordle_overlay_badge.set_visible(True)
        else:
            self.wordle_overlay_badge.set_visible(False)

        # Keep tab styling
        if self.current_tab == "keep":
            self.keep_tab_button.remove_css_class("tab-button-inactive")
            self.keep_tab_button.add_css_class("tab-button")
            self.keep_tab_button.add_css_class("tab-button-active")
            self._set_image_from_svg(self.keep_icon_img, ICON_HICOLOR_KEEP)
            self.keep_label.set_visible(True)
            self.keep_overlay_badge.set_visible(False)
            if self.unread_keep_count > 0:
                self.keep_badge.set_text(str(self.unread_keep_count))
                self.keep_badge.remove_css_class("badge-hidden")
                self.keep_badge.set_visible(True)
            else:
                self.keep_badge.set_text("")
                self.keep_badge.add_css_class("badge-hidden")
                self.keep_badge.set_visible(False)
        else:
            self.keep_tab_button.remove_css_class("tab-button-active")
            self.keep_tab_button.add_css_class("tab-button")
            self.keep_tab_button.add_css_class("tab-button-inactive")
            self._set_image_from_svg(self.keep_icon_img, ICON_GREYSCALE_KEEP)
            self.keep_label.set_visible(False)
            self.keep_badge.set_visible(False)
            if self.unread_keep_count > 0:
                self.keep_overlay_badge.set_text(str(self.unread_keep_count))
                self.keep_overlay_badge.remove_css_class("badge-hidden")
                self.keep_overlay_badge.set_visible(True)
            else:
                self.keep_overlay_badge.set_text("")
                self.keep_overlay_badge.add_css_class("badge-hidden")
                self.keep_overlay_badge.set_visible(False)

    def _set_image_from_svg(self, gtk_image, svg_path, pixel_size=28, fallback_icon_name=None):
        if svg_path and svg_path.exists():
            try:
                gtk_image.set_from_file(str(svg_path))
                gtk_image.set_pixel_size(pixel_size)
                return
            except Exception as e:
                sys.stderr.write(f"[Philotes] Error loading SVG {svg_path}: {e}\n")
        if fallback_icon_name:
            gtk_image.set_from_icon_name(fallback_icon_name)
            gtk_image.set_pixel_size(pixel_size)


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
