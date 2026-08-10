"""
Philotes Universal Clipboard Bridge

Provides image paste support for WebKitGTK 6.0 WebViews by intercepting paste key shortcuts
and bridging binary image data from Gdk.Clipboard into web DOM ClipboardEvents.
"""

import base64
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, Gdk, WebKit, GLib


class WebKitImagePasteBridge:
    """
    Universal bridge enabling image paste functionality in WebKitGTK WebViews.

    WebKitGTK native clipboard platform adapter omits binary image streams when dispatching
    native paste events. This bridge intercepts paste shortcuts (Ctrl+V, Shift+Insert),
    reads Gdk.Clipboard for Gdk.Texture image data, and dispatches a synthetic ClipboardEvent
    with a DataTransfer File payload to the active DOM element.
    """

    def __init__(self, web_view: WebKit.WebView):
        self.web_view = web_view

        # Ensure clipboard access is enabled in WebKit settings
        settings = self.web_view.get_settings()
        if settings:
            settings.set_javascript_can_access_clipboard(True)

        # Attach key controller to intercept paste shortcuts
        self.key_controller = Gtk.EventControllerKey()
        self.key_controller.connect("key-pressed", self._on_key_pressed)
        self.web_view.add_controller(self.key_controller)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        # Match Ctrl+V, Ctrl+v, or Shift+Insert
        is_ctrl_v = bool(state & Gdk.ModifierType.CONTROL_MASK) and (
            keyval in (Gdk.KEY_v, Gdk.KEY_V)
        )
        is_shift_ins = bool(state & Gdk.ModifierType.SHIFT_MASK) and (
            keyval in (Gdk.KEY_Insert, Gdk.KEY_KP_Insert)
        )

        if is_ctrl_v or is_shift_ins:
            display = Gdk.Display.get_default()
            if display:
                clipboard = display.get_clipboard()
                if clipboard:
                    formats = clipboard.get_formats()
                    if formats and (
                        formats.contain_gtype(Gdk.Texture.__gtype__)
                        or formats.contain_mime_type("image/png")
                        or formats.contain_mime_type("image/jpeg")
                        or formats.contain_mime_type("image/tiff")
                        or formats.contain_mime_type("image/bmp")
                    ):
                        clipboard.read_texture_async(None, self._on_texture_read, None)

        return False

    def _on_texture_read(self, clipboard, result, user_data):
        try:
            texture = clipboard.read_texture_finish(result)
            if not texture:
                return

            bytes_obj = texture.save_to_png_bytes()
            if not bytes_obj:
                return

            png_data = bytes_obj.get_data()
            if not png_data:
                return

            b64_str = base64.b64encode(png_data).decode("utf-8")

            js_code = f"""
            (function() {{
                try {{
                    const b64 = "{b64_str}";
                    const byteChars = atob(b64);
                    const byteNumbers = new Array(byteChars.length);
                    for (let i = 0; i < byteChars.length; i++) {{
                        byteNumbers[i] = byteChars.charCodeAt(i);
                    }}
                    const byteArray = new Uint8Array(byteNumbers);
                    const blob = new Blob([byteArray], {{ type: 'image/png' }});
                    const file = new File([blob], 'pasted_image.png', {{ type: 'image/png' }});

                    const dt = new DataTransfer();
                    dt.items.add(file);

                    let target = document.activeElement;
                    if (!target || target === document.body || target.nodeName === 'BODY') {{
                        target = document.querySelector(
                            '[contenteditable="true"], [role="textbox"], textarea, input:not([type="hidden"])'
                        );
                    }}

                    if (target) {{
                        const pasteEvent = new ClipboardEvent('paste', {{
                            clipboardData: dt,
                            bubbles: true,
                            cancelable: true
                        }});
                        target.dispatchEvent(pasteEvent);
                        console.log('[Philotes ClipboardBridge] Dispatched synthetic image paste to target', target);
                    }} else {{
                        console.warn('[Philotes ClipboardBridge] No suitable input target found for image paste.');
                    }}
                }} catch (err) {{
                    console.error('[Philotes ClipboardBridge] Failed synthetic image paste dispatch:', err);
                }}
            }})();
            """
            self.web_view.evaluate_javascript(
                js_code, -1, None, None, None, None, None
            )
        except Exception as e:
            print(
                f"[Philotes ClipboardBridge] Warning: failed to read clipboard texture: {e}",
                flush=True,
            )


def enable_image_paste(web_view: WebKit.WebView) -> WebKitImagePasteBridge:
    """
    Helper function to attach WebKitImagePasteBridge to a WebKit.WebView.
    """
    return WebKitImagePasteBridge(web_view)
