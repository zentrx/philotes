import sys
import os
import json
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib, GObject

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
    ICON_HICOLOR_TASKS,
    ICON_GREYSCALE_TASKS,
    ICON_HICOLOR_PHILOTES,
    ICON_GREYSCALE_PHILOTES,
    THEME_CSS_PATH,
)
from philotes.subapps.philo_chat import PhiloChatApp
from philotes.subapps.philo_msgs import PhiloMsgsApp
from philotes.subapps.philo_wordle import PhiloWordleApp
from philotes.subapps.philo_keep import PhiloKeepApp
from philotes.subapps.philo_tasks import PhiloTasksApp
from philotes.account_manager import AccountManager
from philotes.settings_manager import SettingsManager
from philotes.views.settings_view import SettingsView
from philotes.components.splash_view import SplashView


class PhilotesWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Philotes")
        set_process_name(APP_NAME)
        self.set_default_size(1150, 750)

        settings_mgr = SettingsManager.get_instance()
        self.tab_order = settings_mgr.get_tab_order()
        self.double_click_time_ms = settings_mgr.get_system_double_click_time()
        self.ipc_handles = {}

        self.chat_app = None
        self.msgs_app = None
        self.wordle_app = None
        self.keep_app = None
        self.tasks_app = None

        total_cards = settings_mgr.accounts.get_total_card_count()
        enabled_tabs = [t for t in self.tab_order if settings_mgr.is_tab_enabled(t)]

        # Rule: If no Auth Cards present or no enabled tabs, bring user to Settings tab on launch
        if total_cards == 0 or not enabled_tabs:
            self.current_tab = "settings"
        else:
            self.current_tab = enabled_tabs[0]

        self.unread_chat_count = 0
        self.unread_msgs_count = 0
        self.unread_keep_count = 0
        self.unread_tasks_count = 0
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

        # Tasks Tab Button
        self.tasks_tab_button = Gtk.Button()
        self.tasks_tab_button.connect("clicked", self._on_tasks_tab_clicked)

        self.tasks_tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.tasks_tab_box.set_halign(Gtk.Align.CENTER)
        self.tasks_tab_box.set_valign(Gtk.Align.CENTER)
        self.tasks_overlay = Gtk.Overlay()
        self.tasks_icon_img = Gtk.Image()
        self.tasks_icon_img.add_css_class("tab-icon-img")
        self.tasks_overlay.set_child(self.tasks_icon_img)

        self.tasks_overlay_badge = Gtk.Label(label="")
        self.tasks_overlay_badge.add_css_class("badge")
        self.tasks_overlay_badge.add_css_class("badge-overlay")
        self.tasks_overlay_badge.set_halign(Gtk.Align.END)
        self.tasks_overlay_badge.set_valign(Gtk.Align.START)
        self.tasks_overlay.add_overlay(self.tasks_overlay_badge)

        self.tasks_label = Gtk.Label(label="Tasks")
        self.tasks_label.add_css_class("tab-label")

        self.tasks_badge = Gtk.Label(label="")
        self.tasks_badge.add_css_class("badge")
        self.tasks_badge.add_css_class("badge-hidden")

        self.tasks_tab_box.append(self.tasks_overlay)
        self.tasks_tab_box.append(self.tasks_label)
        self.tasks_tab_box.append(self.tasks_badge)
        self.tasks_tab_button.set_child(self.tasks_tab_box)

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

        # Tab Mapping & Dynamic Ordering
        self.tab_buttons = {
            "chat": self.chat_tab_button,
            "msgs": self.msgs_tab_button,
            "tasks": self.tasks_tab_button,
            "keep": self.keep_tab_button,
            "wordle": self.wordle_tab_button,
        }

        for tab_id in self.tab_order:
            if tab_id in self.tab_buttons:
                btn = self.tab_buttons[tab_id]
                btn.set_visible(settings_mgr.is_tab_enabled(tab_id))
                self.tabs_box.append(btn)

        for tab_id, btn in self.tab_buttons.items():
            self._setup_tab_drag_and_drop(tab_id, btn)

        box_drop_target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        box_drop_target.connect("drop", self._on_tabs_box_drop)
        self.tabs_box.add_controller(box_drop_target)

        self.top_bar.append(self.tabs_box)

        # Right Settings Button
        self.settings_button = Gtk.Button()
        self.settings_button.set_name("settings-button")
        self.settings_button.add_css_class("tab-button")
        self.settings_button.add_css_class("tab-button-inactive")
        self.settings_button.connect("clicked", self._on_settings_tab_clicked)
        self.settings_button.set_halign(Gtk.Align.END)
        self.settings_button.set_valign(Gtk.Align.CENTER)
        
        settings_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        settings_box.set_halign(Gtk.Align.CENTER)
        settings_box.set_valign(Gtk.Align.CENTER)
        settings_label = Gtk.Label(label="⚙")
        settings_label.set_halign(Gtk.Align.CENTER)
        settings_label.set_valign(Gtk.Align.CENTER)
        settings_box.append(settings_label)
        self.settings_button.set_child(settings_box)

        # Settings double-click to refresh
        settings_click = Gtk.GestureClick()
        settings_click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        settings_click.connect("pressed", lambda g, n, x, y: self.refresh_tab("settings") if n == 2 else None)
        self.settings_button.add_controller(settings_click)

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

        if settings_mgr.is_tab_enabled("chat"):
            self._init_chat_view()
        if settings_mgr.is_tab_enabled("msgs"):
            self._init_msgs_view()
        if settings_mgr.is_tab_enabled("wordle"):
            self._init_wordle_view()
        if settings_mgr.is_tab_enabled("keep"):
            self._init_keep_view()
        if settings_mgr.is_tab_enabled("tasks"):
            self._init_tasks_view()

        self.settings_view = SettingsView(
            on_accounts_changed_cb=self._on_accounts_changed,
            on_reset_tab_order_cb=self._on_reset_tab_order,
            on_tab_toggled_cb=self._on_tab_toggled,
        )
        self.stack.add_named(self.settings_view, "settings")
        
        self.stack.set_visible_child_name(self.current_tab)
        self._update_tab_ui()
        self._update_header_title()

    def _cleanup_ipc_handle(self, tab_id: str):
        if tab_id in self.ipc_handles:
            read_fd, watch_id = self.ipc_handles.pop(tab_id)
            try:
                GLib.source_remove(watch_id)
            except Exception:
                pass
            try:
                os.close(read_fd)
            except Exception:
                pass

    def _init_chat_view(self):
        self._cleanup_ipc_handle("chat")
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
            watch_id = GLib.io_add_watch(read_fd, GLib.IO_IN, self._on_ipc_data_received)
            self.ipc_handles["chat"] = (read_fd, watch_id)

    def _init_msgs_view(self):
        self._cleanup_ipc_handle("msgs")
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
            watch_id = GLib.io_add_watch(read_fd, GLib.IO_IN, self._on_ipc_data_received)
            self.ipc_handles["msgs"] = (read_fd, watch_id)

    def _init_wordle_view(self):
        self._cleanup_ipc_handle("wordle")
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
            watch_id = GLib.io_add_watch(read_fd, GLib.IO_IN, self._on_ipc_data_received)
            self.ipc_handles["wordle"] = (read_fd, watch_id)
            return True

    def _init_keep_view(self):
        self._cleanup_ipc_handle("keep")
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
            watch_id = GLib.io_add_watch(read_fd, GLib.IO_IN, self._on_ipc_data_received)
            self.ipc_handles["keep"] = (read_fd, watch_id)

    def _init_tasks_view(self):
        self._cleanup_ipc_handle("tasks")
        active_card = AccountManager.get_instance().get_active_card("google")
        
        if existing := self.stack.get_child_by_name("tasks"):
            self.stack.remove(existing)

        if active_card is None:
            self.tasks_app = None
            self.unread_tasks_count = 0
            splash = SplashView("Google", on_goto_settings_cb=self._on_settings_tab_clicked)
            self.stack.add_named(splash, "tasks")
        else:
            profile_id = active_card.get("profile_dir")
            username = active_card.get("username")
            self.unread_tasks_count = active_card.get("unread_count", 0)
            read_fd, write_fd = os.pipe()
            self.tasks_app = PhiloTasksApp(ipc_write_fd=write_fd, profile_id=profile_id, username=username)
            tasks_widget = self.tasks_app.get_widget()
            self.stack.add_named(tasks_widget, "tasks")
            watch_id = GLib.io_add_watch(read_fd, GLib.IO_IN, self._on_ipc_data_received)
            self.ipc_handles["tasks"] = (read_fd, watch_id)

    def _on_accounts_changed(self):
        settings_mgr = SettingsManager.get_instance()
        if settings_mgr.is_tab_enabled("chat"):
            self._init_chat_view()
        if settings_mgr.is_tab_enabled("msgs"):
            self._init_msgs_view()
        if settings_mgr.is_tab_enabled("wordle"):
            self._init_wordle_view()
        if settings_mgr.is_tab_enabled("keep"):
            self._init_keep_view()
        if settings_mgr.is_tab_enabled("tasks"):
            self._init_tasks_view()

        if self.current_tab in ("chat", "msgs", "wordle", "keep", "tasks"):
            if settings_mgr.is_tab_enabled(self.current_tab):
                self.stack.set_visible_child_name(self.current_tab)
            else:
                enabled = [t for t in self.tab_order if settings_mgr.is_tab_enabled(t)]
                self.current_tab = enabled[0] if enabled else "settings"
                self.stack.set_visible_child_name(self.current_tab)
        self._update_tab_ui()

    def _load_tab(self, tab_id: str):
        if tab_id == "chat":
            self._init_chat_view()
        elif tab_id == "msgs":
            self._init_msgs_view()
        elif tab_id == "wordle":
            self._init_wordle_view()
        elif tab_id == "keep":
            self._init_keep_view()
        elif tab_id == "tasks":
            self._init_tasks_view()

    def _unload_tab(self, tab_id: str):
        self._cleanup_ipc_handle(tab_id)
        app = getattr(self, f"{tab_id}_app", None)
        if app:
            try:
                app.cleanup()
            except Exception as e:
                sys.stderr.write(f"[Philotes] Error cleaning up {tab_id} app: {e}\n")
            setattr(self, f"{tab_id}_app", None)

        if existing := self.stack.get_child_by_name(tab_id):
            self.stack.remove(existing)

        if tab_id == "chat":
            self.unread_chat_count = 0
        elif tab_id == "msgs":
            self.unread_msgs_count = 0
        elif tab_id == "tasks":
            self.unread_tasks_count = 0
        elif tab_id == "keep":
            self.unread_keep_count = 0
        elif tab_id == "wordle":
            self.wordle_completed = None

        import gc
        gc.collect()

    def _on_tab_toggled(self, tab_id: str, is_enabled: bool):
        if is_enabled:
            # 1. Load for the first time in the background
            self._load_tab(tab_id)
            # 2. Make tab button available in the tabs bar
            if tab_id in self.tab_buttons:
                self.tab_buttons[tab_id].set_visible(True)
            # 3. Position the tab button in the top bar in the same place that it used to be
            self._reorder_tabs_ui()
        else:
            # 1. Tab should no longer be available in the tabs bar
            if tab_id in self.tab_buttons:
                self.tab_buttons[tab_id].set_visible(False)
            # 2. Memory should be released
            self._unload_tab(tab_id)
            # 3. If currently selected tab was disabled, redirect away
            if self.current_tab == tab_id:
                settings_mgr = SettingsManager.get_instance()
                enabled = [t for t in self.tab_order if settings_mgr.is_tab_enabled(t)]
                if enabled:
                    self.current_tab = enabled[0]
                    self.stack.set_visible_child_name(self.current_tab)
                else:
                    self._on_settings_tab_clicked()
        self._update_tab_ui()
        self._update_header_title()

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
                            elif app_name == "tasks":
                                self.unread_tasks_count = count

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

    def _on_tasks_tab_clicked(self, widget=None):
        self.current_tab = "tasks"
        self.stack.set_visible_child_name("tasks")
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
        if self.wordle_app is None:
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
        elif self.current_tab == "tasks":
            tab_name = "Tasks"
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

        # Tasks tab styling
        if self.current_tab == "tasks":
            self.tasks_tab_button.remove_css_class("tab-button-inactive")
            self.tasks_tab_button.add_css_class("tab-button")
            self.tasks_tab_button.add_css_class("tab-button-active")
            self._set_image_from_svg(self.tasks_icon_img, ICON_HICOLOR_TASKS)
            self.tasks_label.set_visible(True)
            self.tasks_overlay_badge.set_visible(False)
            if self.unread_tasks_count > 0:
                self.tasks_badge.set_text(str(self.unread_tasks_count))
                self.tasks_badge.remove_css_class("badge-hidden")
                self.tasks_badge.set_visible(True)
            else:
                self.tasks_badge.set_text("")
                self.tasks_badge.add_css_class("badge-hidden")
                self.tasks_badge.set_visible(False)
        else:
            self.tasks_tab_button.remove_css_class("tab-button-active")
            self.tasks_tab_button.add_css_class("tab-button")
            self.tasks_tab_button.add_css_class("tab-button-inactive")
            self._set_image_from_svg(self.tasks_icon_img, ICON_GREYSCALE_TASKS)
            self.tasks_label.set_visible(False)
            self.tasks_badge.set_visible(False)
            if self.unread_tasks_count > 0:
                self.tasks_overlay_badge.set_text(str(self.unread_tasks_count))
                self.tasks_overlay_badge.remove_css_class("badge-hidden")
                self.tasks_overlay_badge.set_visible(True)
            else:
                self.tasks_overlay_badge.set_text("")
                self.tasks_overlay_badge.add_css_class("badge-hidden")
                self.tasks_overlay_badge.set_visible(False)

        # Settings button styling
        if self.current_tab == "settings":
            self.settings_button.remove_css_class("tab-button-inactive")
            self.settings_button.add_css_class("tab-button-active")
        else:
            self.settings_button.remove_css_class("tab-button-active")
            self.settings_button.add_css_class("tab-button-inactive")

    def _setup_tab_drag_and_drop(self, tab_id, btn):
        drag_source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self._on_tab_drag_prepare, tab_id)
        drag_source.connect("drag-begin", self._on_tab_drag_begin, tab_id)
        drag_source.connect("drag-end", self._on_tab_drag_end, tab_id)
        drag_source.connect("drag-cancel", self._on_tab_drag_cancel, tab_id)
        btn.add_controller(drag_source)

        drop_target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        drop_target.connect("enter", self._on_tab_drop_enter, tab_id)
        drop_target.connect("motion", self._on_tab_drop_motion, tab_id)
        drop_target.connect("leave", self._on_tab_drop_leave, tab_id)
        drop_target.connect("drop", self._on_tab_drop, tab_id)
        btn.add_controller(drop_target)

        # Double-click gesture to refresh tab
        click_gesture = Gtk.GestureClick()
        click_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click_gesture.connect("pressed", self._on_tab_pressed, tab_id)
        btn.add_controller(click_gesture)

    def _on_tab_pressed(self, gesture, n_press, x, y, tab_id):
        if n_press == 2:
            self.refresh_tab(tab_id)

    def refresh_tab(self, tab_id: str):
        print(f"[Philotes] Refreshing tab: {tab_id}", flush=True)
        if tab_id != "settings" and not SettingsManager.get_instance().is_tab_enabled(tab_id):
            return
        if tab_id == "chat":
            if self.chat_app:
                self.chat_app.reload()
            else:
                self._init_chat_view()
        elif tab_id == "msgs":
            if self.msgs_app:
                self.msgs_app.reload()
            else:
                self._init_msgs_view()
        elif tab_id == "tasks":
            if self.tasks_app:
                self.tasks_app.reload()
            else:
                self._init_tasks_view()
        elif tab_id == "keep":
            if self.keep_app:
                self.keep_app.reload()
            else:
                self._init_keep_view()
        elif tab_id == "wordle":
            if self.wordle_app:
                self.wordle_app.reload()
            else:
                self._init_wordle_view()
        elif tab_id == "settings":
            self.settings_view.refresh_cards()

    def _on_tab_drag_prepare(self, source, x, y, tab_id):
        # Only allow dragging when the tab is currently selected/active
        if tab_id != self.current_tab:
            return None
        return Gdk.ContentProvider.new_for_value(tab_id)

    def _on_tab_drag_begin(self, source, drag, tab_id):
        btn = self.tab_buttons[tab_id]
        paintable = Gtk.WidgetPaintable.new(btn)
        source.set_icon(paintable, int(btn.get_width() / 2), int(btn.get_height() / 2))
        btn.add_css_class("tab-dragging")

    def _on_tab_drag_end(self, source, drag, delete_data, tab_id):
        btn = self.tab_buttons[tab_id]
        btn.remove_css_class("tab-dragging")
        self._clear_tab_drop_indicators()

    def _on_tab_drag_cancel(self, source, drag, reason, tab_id):
        btn = self.tab_buttons[tab_id]
        btn.remove_css_class("tab-dragging")
        self._clear_tab_drop_indicators()
        return False

    def _clear_tab_drop_indicators(self):
        for btn in self.tab_buttons.values():
            btn.remove_css_class("tab-drop-before")
            btn.remove_css_class("tab-drop-after")

    def _on_tab_drop_enter(self, target, x, y, tab_id):
        return Gdk.DragAction.MOVE

    def _on_tab_drop_motion(self, target, x, y, tab_id):
        btn = self.tab_buttons[tab_id]
        w = btn.get_width()
        if (w > 0 and x < w / 2) or (w <= 0 and x <= 0):
            btn.add_css_class("tab-drop-before")
            btn.remove_css_class("tab-drop-after")
        else:
            btn.add_css_class("tab-drop-after")
            btn.remove_css_class("tab-drop-before")
        return Gdk.DragAction.MOVE

    def _on_tab_drop_leave(self, target, tab_id):
        btn = self.tab_buttons[tab_id]
        btn.remove_css_class("tab-drop-before")
        btn.remove_css_class("tab-drop-after")

    def _on_tab_drop(self, target, value, x, y, target_tab_id):
        self._clear_tab_drop_indicators()
        if value == target_tab_id or value not in self.tab_order or target_tab_id not in self.tab_order:
            return False

        btn = self.tab_buttons[target_tab_id]
        width = btn.get_width()
        drop_after = (x >= (width / 2)) if width > 0 else (x > 0)

        self.tab_order.remove(value)
        target_idx = self.tab_order.index(target_tab_id)
        if drop_after:
            self.tab_order.insert(target_idx + 1, value)
        else:
            self.tab_order.insert(target_idx, value)

        self._reorder_tabs_ui()
        SettingsManager.get_instance().set_tab_order(self.tab_order)
        return True

    def _on_tabs_box_drop(self, target, value, x, y):
        self._clear_tab_drop_indicators()
        if value not in self.tab_order:
            return False
        self.tab_order.remove(value)
        self.tab_order.append(value)
        self._reorder_tabs_ui()
        SettingsManager.get_instance().set_tab_order(self.tab_order)
        return True

    def _reorder_tabs_ui(self):
        prev = None
        for tab_id in self.tab_order:
            btn = self.tab_buttons.get(tab_id)
            if btn and btn.get_parent() == self.tabs_box:
                self.tabs_box.reorder_child_after(btn, prev)
                prev = btn

    def _on_reset_tab_order(self):
        self.tab_order = SettingsManager.get_instance().reset_tab_order()
        self._reorder_tabs_ui()
        self._update_tab_ui()

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
