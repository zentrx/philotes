import os
from pathlib import Path

APP_NAME = "philotes"
SUBAPP_CHAT_NAME = "philo-chat"
SUBAPP_MSGS_NAME = "philo-msgs"

BASE_DIR = Path(__file__).resolve().parent.parent.parent

CONFIG_DIR = Path(os.path.expanduser("~/.config/philotes"))
CACHE_DIR = Path(os.path.expanduser("~/.cache/philotes"))

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

ICON_HICOLOR_CHAT = BASE_DIR / "icons" / "hicolor" / "chat.svg"
ICON_GREYSCALE_CHAT = BASE_DIR / "icons" / "greyscale" / "chat.svg"
ICON_HICOLOR_MSGS = BASE_DIR / "icons" / "hicolor" / "messages.svg"
ICON_GREYSCALE_MSGS = BASE_DIR / "icons" / "greyscale" / "messages.svg"
ICON_HICOLOR_PHILOTES = BASE_DIR / "icons" / "hicolor" / "philotes.svg"

# Fallback to system paths if installed in /usr/share
if not ICON_HICOLOR_CHAT.exists():
    ICON_HICOLOR_CHAT = Path("/usr/share/philotes/icons/hicolor/chat.svg")
    ICON_GREYSCALE_CHAT = Path("/usr/share/philotes/icons/greyscale/chat.svg")
    ICON_HICOLOR_MSGS = Path("/usr/share/philotes/icons/hicolor/messages.svg")
    ICON_GREYSCALE_MSGS = Path("/usr/share/philotes/icons/greyscale/messages.svg")
    ICON_HICOLOR_PHILOTES = Path("/usr/share/philotes/icons/hicolor/philotes.svg")

THEME_CSS_PATH = BASE_DIR / "styles" / "dark-sharp.css"
if not THEME_CSS_PATH.exists():
    THEME_CSS_PATH = Path("/usr/share/philotes/styles/dark-sharp.css")

