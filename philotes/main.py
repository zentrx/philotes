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
from philotes.settings_manager import SettingsManager, TAB_METADATA
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

        self.tab_buttons = {}
        self._tab_ui_descriptors = {}

        self._build_tab_button(
            tab_id="chat",
            label_text="Chat",
            icon_active=ICON_HICOLOR_CHAT,
            icon_inactive=ICON_GREYSCALE_CHAT,
            on_clicked_cb=self._on_chat_tab_clicked,
            unread_count_fn=lambda: self.unread_chat_count,
        )
        self._build_tab_button(
            tab_id="msgs",
            label_text="Messages",
            icon_active=ICON_HICOLOR_MSGS,
            icon_inactive=ICON_GREYSCALE_MSGS,
            on_clicked_cb=self._on_msgs_tab_clicked,
            unread_count_fn=lambda: self.unread_msgs_count,
        )
        self._build_tab_button(
            tab_id="tasks",
            label_text="Tasks",
            icon_active=ICON_HICOLOR_TASKS,
            icon_inactive=ICON_GREYSCALE_TASKS,
            on_clicked_cb=self._on_tasks_tab_clicked,
        )
        self._build_tab_button(
            tab_id="keep",
            label_text="Keep",
            icon_active=ICON_HICOLOR_KEEP,
            icon_inactive=ICON_GREYSCALE_KEEP,
            on_clicked_cb=self._on_keep_tab_clicked,
        )
        self._build_tab_button(
            tab_id="wordle",
            label_text="Wordle",
            icon_active=ICON_HICOLOR_WORDLE,
            icon_inactive=ICON_GREYSCALE_WORDLE,
            on_clicked_cb=self._on_wordle_tab_clicked,
            badge_style="dot",
            fallback_icon="wayland",
            custom_overlay_fn=lambda: not self.wordle_completed,
        )

        self._subapp_classes = {
            "chat": PhiloChatApp,
            "msgs": PhiloMsgsApp,
            "tasks": PhiloTasksApp,
            "keep": PhiloKeepApp,
            "wordle": PhiloWordleApp,
        }

        self.tab_loaders = {
            "chat": self._init_chat_view,
            "msgs": self._init_msgs_view,
            "tasks": self._init_tasks_view,
            "keep": self._init_keep_view,
            "wordle": self._init_wordle_view,
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

        for tab_id, loader in self.tab_loaders.items():
            if settings_mgr.is_tab_enabled(tab_id):
                loader()

        self.settings_view = SettingsView(
            on_accounts_changed_cb=self._on_accounts_changed,
            on_reset_tab_order_cb=self._on_reset_tab_order,
            on_tab_toggled_cb=self._on_tab_toggled,
        )
        self.stack.add_named(self.settings_view, "settings")
        
        self.stack.set_visible_child_name(self.current_tab)
        self._update_tab_ui()
        self._update_header_title()

    def _build_tab_button(
        self,
        tab_id: str,
        label_text: str,
        icon_active,
        icon_inactive,
        on_clicked_cb,
        unread_count_fn=None,
        badge_style: str = "count",
        fallback_icon: str = None,
        custom_overlay_fn=None,
    ) -> Gtk.Button:
        tab_button = Gtk.Button()
        tab_button.connect("clicked", on_clicked_cb)

        tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tab_box.set_halign(Gtk.Align.CENTER)
        tab_box.set_valign(Gtk.Align.CENTER)

        overlay = Gtk.Overlay()
        icon_img = Gtk.Image()
        icon_img.add_css_class("tab-icon-img")
        overlay.set_child(icon_img)

        if badge_style == "dot":
            overlay_badge = Gtk.Box()
            overlay_badge.add_css_class("badge-blue-dot")
            overlay_badge.set_visible(False)
            badge = None
        else:
            overlay_badge = Gtk.Label(label="")
            overlay_badge.add_css_class("badge")
            overlay_badge.add_css_class("badge-overlay")
            badge = Gtk.Label(label="")
            badge.add_css_class("badge")
            badge.add_css_class("badge-hidden")
            badge.set_halign(Gtk.Align.CENTER)
            badge.set_valign(Gtk.Align.CENTER)

        overlay_badge.set_halign(Gtk.Align.END)
        overlay_badge.set_valign(Gtk.Align.START)
        overlay.add_overlay(overlay_badge)

        label = Gtk.Label(label=label_text)
        label.add_css_class("tab-label")

        tab_box.append(overlay)
        tab_box.append(label)
        if badge is not None:
            tab_box.append(badge)
        tab_button.set_child(tab_box)

        # Preserve instance attributes for backward compatibility
        setattr(self, f"{tab_id}_tab_button", tab_button)
        setattr(self, f"{tab_id}_tab_box", tab_box)
        setattr(self, f"{tab_id}_overlay", overlay)
        setattr(self, f"{tab_id}_icon_img", icon_img)
        setattr(self, f"{tab_id}_overlay_badge", overlay_badge)
        setattr(self, f"{tab_id}_label", label)
        if badge is not None:
            setattr(self, f"{tab_id}_badge", badge)

        self.tab_buttons[tab_id] = tab_button

        descriptor = {
            "button": tab_button,
            "icon_img": icon_img,
            "label": label,
            "badge": badge,
            "overlay_badge": overlay_badge,
            "icon_active": icon_active,
            "icon_inactive": icon_inactive,
        }
        if unread_count_fn is not None:
            descriptor["unread_count"] = unread_count_fn
        if fallback_icon is not None:
            descriptor["fallback_icon"] = fallback_icon
        if custom_overlay_fn is not None:
            descriptor["custom_overlay"] = custom_overlay_fn

        self._tab_ui_descriptors[tab_id] = descriptor
        return tab_button

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

    def _init_tab_view(self, tab_id: str) -> bool:
        """
        Unified view initializer for any sub-application tab.
        Tears down any previously mounted instance (stopping DOM timers and closing
        IPC pipes) before mounting either a SplashView or a fresh sub-app WebView.
        """
        self._unload_tab(tab_id, collect_gc=False)

        meta = TAB_METADATA.get(tab_id, {})
        provider = meta.get("provider", "google")
        splash_title = "NYTimes" if provider == "nytimes" else "Google"
        active_card = AccountManager.get_instance().get_active_card(provider)

        is_unavailable = (
            active_card is None
            or (provider == "nytimes" and not active_card.get("subscribed", True))
        )

        if is_unavailable:
            splash = SplashView(splash_title, on_goto_settings_cb=self._on_settings_tab_clicked)
            self.stack.add_named(splash, tab_id)
            return False

        profile_id = active_card.get("profile_dir")
        username = active_card.get("username")
        if hasattr(self, f"unread_{tab_id}_count"):
            setattr(self, f"unread_{tab_id}_count", active_card.get("unread_count", 0))

        read_fd, write_fd = os.pipe()
        app_cls = self._subapp_classes[tab_id]
        app_instance = app_cls(ipc_write_fd=write_fd, profile_id=profile_id, username=username)
        setattr(self, f"{tab_id}_app", app_instance)

        self.stack.add_named(app_instance.get_widget(), tab_id)
        watch_id = GLib.io_add_watch(read_fd, GLib.IO_IN, self._on_ipc_data_received)
        self.ipc_handles[tab_id] = (read_fd, watch_id)
        return True

    def _init_chat_view(self):
        return self._init_tab_view("chat")

    def _init_msgs_view(self):
        return self._init_tab_view("msgs")

    def _init_wordle_view(self):
        return self._init_tab_view("wordle")

    def _init_keep_view(self):
        return self._init_tab_view("keep")

    def _init_tasks_view(self):
        return self._init_tab_view("tasks")

    def get_tab_app(self, tab_id: str):
        if tab_id == "settings":
            return getattr(self, "settings_view", None)
        return getattr(self, f"{tab_id}_app", None)

    def _on_accounts_changed(self):
        settings_mgr = SettingsManager.get_instance()
        for tab_id, loader in self.tab_loaders.items():
            if settings_mgr.is_tab_enabled(tab_id):
                loader()

        if self.current_tab in self.tab_loaders:
            if settings_mgr.is_tab_enabled(self.current_tab):
                self.stack.set_visible_child_name(self.current_tab)
            else:
                enabled = [t for t in self.tab_order if settings_mgr.is_tab_enabled(t)]
                self.current_tab = enabled[0] if enabled else "settings"
                self.stack.set_visible_child_name(self.current_tab)
        self._update_tab_ui()
        self._update_header_title()

    def _load_tab(self, tab_id: str):
        if loader := self.tab_loaders.get(tab_id):
            loader()

    def _unload_tab(self, tab_id: str, collect_gc: bool = True):
        self._cleanup_ipc_handle(tab_id)
        app = self.get_tab_app(tab_id)
        if app:
            try:
                app.cleanup()
            except Exception as e:
                sys.stderr.write(f"[Philotes] Error cleaning up {tab_id} app: {e}\n")
            setattr(self, f"{tab_id}_app", None)

        if existing := self.stack.get_child_by_name(tab_id):
            self.stack.remove(existing)

        if hasattr(self, f"unread_{tab_id}_count"):
            setattr(self, f"unread_{tab_id}_count", 0)
        if hasattr(self, f"{tab_id}_selected_title"):
            setattr(self, f"{tab_id}_selected_title", None)
        if tab_id == "wordle":
            self.wordle_completed = True

        if collect_gc:
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
        SettingsManager.get_instance().sync_system_theme_to_gtk()

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
                            setattr(self, f"unread_{app_name}_count", msg.get("count", 0))

                        if "completed" in msg and app_name == "wordle":
                            self.wordle_completed = msg.get("completed", False)

                        if "title" in msg:
                            setattr(self, f"{app_name}_selected_title", msg.get("title"))

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

    def _switch_to_tab(self, tab_id: str):
        self.current_tab = tab_id
        self.stack.set_visible_child_name(tab_id)
        self._update_tab_ui()
        self._update_header_title()

    def _on_chat_tab_clicked(self, widget=None):
        self._switch_to_tab("chat")

    def _on_msgs_tab_clicked(self, widget=None):
        self._switch_to_tab("msgs")

    def _on_keep_tab_clicked(self, widget=None):
        self._switch_to_tab("keep")

    def _on_tasks_tab_clicked(self, widget=None):
        self._switch_to_tab("tasks")

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
        self._switch_to_tab("wordle")

    def _on_settings_tab_clicked(self, widget=None):
        self._switch_to_tab("settings")

    def _update_header_title(self):
        meta = TAB_METADATA.get(self.current_tab, {})
        tab_name = meta.get("short_name", self.current_tab.capitalize())
        selected_title = getattr(self, f"{self.current_tab}_selected_title", None)

        if selected_title:
            full_title = f"Philotes | {tab_name} | {selected_title}"
        else:
            full_title = f"Philotes | {tab_name}"

        self.set_title(full_title)

    def _update_tab_ui(self):
        for tab_id, ui in self._tab_ui_descriptors.items():
            is_active = (self.current_tab == tab_id)
            btn = ui["button"]
            icon_img = ui["icon_img"]
            label = ui["label"]
            badge = ui.get("badge")
            overlay_badge = ui.get("overlay_badge")

            if is_active:
                btn.remove_css_class("tab-button-inactive")
                btn.add_css_class("tab-button")
                btn.add_css_class("tab-button-active")
                self._set_image_from_svg(icon_img, ui["icon_active"], fallback_icon_name=ui.get("fallback_icon"))
                label.set_visible(True)
                if overlay_badge and not ui.get("custom_overlay"):
                    overlay_badge.set_visible(False)
                if badge:
                    count = ui["unread_count"]() if "unread_count" in ui else 0
                    if count > 0:
                        badge.set_text(str(count))
                        badge.remove_css_class("badge-hidden")
                        badge.set_visible(True)
                    else:
                        badge.set_text("")
                        badge.add_css_class("badge-hidden")
                        badge.set_visible(False)
            else:
                btn.remove_css_class("tab-button-active")
                btn.add_css_class("tab-button")
                btn.add_css_class("tab-button-inactive")
                self._set_image_from_svg(icon_img, ui["icon_inactive"], fallback_icon_name=ui.get("fallback_icon"))
                label.set_visible(False)
                if badge:
                    badge.set_visible(False)
                if overlay_badge and not ui.get("custom_overlay"):
                    count = ui["unread_count"]() if "unread_count" in ui else 0
                    if count > 0:
                        overlay_badge.set_text(str(count))
                        overlay_badge.remove_css_class("badge-hidden")
                        overlay_badge.set_visible(True)
                    else:
                        overlay_badge.set_text("")
                        overlay_badge.add_css_class("badge-hidden")
                        overlay_badge.set_visible(False)

            if "custom_overlay" in ui and overlay_badge:
                overlay_badge.set_visible(ui["custom_overlay"]())

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
        app = self.get_tab_app(tab_id)
        if app and hasattr(app, "reload"):
            app.reload()
        else:
            self._load_tab(tab_id)

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
