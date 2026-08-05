import sys
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

class SplashView(Gtk.Box):
    def __init__(self, service_name: str = "Google", on_goto_settings_cb=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.on_goto_settings_cb = on_goto_settings_cb

        self.set_name("splash-view")
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)

        # Icon / Header
        icon_label = Gtk.Label()
        icon_label.set_markup("<span size='32000' color='#f7768e'>⚠️</span>")

        title_label = Gtk.Label()
        title_label.set_markup(f"<span size='x-large' weight='bold'>No Active {service_name} User</span>")

        message_label = Gtk.Label(
            label=f"No users are currently active for the {service_name} service pool.\nPlease enable a user in the Settings tab."
        )
        message_label.set_justify(Gtk.Justification.CENTER)
        message_label.add_css_class("splash-message")

        # Action Button
        settings_btn = Gtk.Button(label="Go to Settings ⚙")
        settings_btn.add_css_class("splash-settings-btn")
        settings_btn.connect("clicked", self._on_button_clicked)

        self.append(icon_label)
        self.append(title_label)
        self.append(message_label)
        self.append(settings_btn)

    def _on_button_clicked(self, widget):
        if self.on_goto_settings_cb:
            self.on_goto_settings_cb()
