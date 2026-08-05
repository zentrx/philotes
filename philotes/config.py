import os
from pathlib import Path

APP_NAME = "philotes"
SUBAPP_CHAT_NAME = "philo-chat"
SUBAPP_MSGS_NAME = "philo-msgs"

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = Path(os.path.expanduser("~/.config/philotes"))
CACHE_DIR = Path(os.path.expanduser("~/.cache/philotes"))

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

ICON_HICOLOR_CHAT = BASE_DIR / "icons" / "hicolor" / "chat.svg"
ICON_GREYSCALE_CHAT = BASE_DIR / "icons" / "greyscale" / "chat.svg"
ICON_HICOLOR_MSGS = BASE_DIR / "icons" / "hicolor" / "messages.svg"
ICON_GREYSCALE_MSGS = BASE_DIR / "icons" / "greyscale" / "messages.svg"
ICON_HICOLOR_PHILOTES = BASE_DIR / "icons" / "hicolor" / "philotes.svg"
ICON_GREYSCALE_PHILOTES = BASE_DIR / "icons" / "greyscale" / "philotes.svg"

# Fallback to system paths (/opt/philotes or /usr/share/philotes) if installed
if not ICON_HICOLOR_CHAT.exists():
    for prefix in [Path("/opt/philotes"), Path("/usr/share/philotes")]:
        if (prefix / "icons" / "hicolor" / "chat.svg").exists():
            ICON_HICOLOR_CHAT = prefix / "icons" / "hicolor" / "chat.svg"
            ICON_GREYSCALE_CHAT = prefix / "icons" / "greyscale" / "chat.svg"
            ICON_HICOLOR_MSGS = prefix / "icons" / "hicolor" / "messages.svg"
            ICON_GREYSCALE_MSGS = prefix / "icons" / "greyscale" / "messages.svg"
            ICON_HICOLOR_PHILOTES = prefix / "icons" / "hicolor" / "philotes.svg"
            ICON_GREYSCALE_PHILOTES = prefix / "icons" / "greyscale" / "philotes.svg"
            break

THEME_CSS_PATH = BASE_DIR / "styles" / "dark-sharp.css"
if not THEME_CSS_PATH.exists():
    for prefix in [Path("/opt/philotes"), Path("/usr/share/philotes")]:
        if (prefix / "styles" / "dark-sharp.css").exists():
            THEME_CSS_PATH = prefix / "styles" / "dark-sharp.css"
            break

