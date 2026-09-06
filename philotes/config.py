import os
from pathlib import Path

APP_NAME = "philotes"
SUBAPP_CHAT_NAME = "philo-chat"
SUBAPP_MSGS_NAME = "philo-msgs"
SUBAPP_WORDLE_NAME = "philo-wordle"
SUBAPP_KEEP_NAME = "philo-keep"
SUBAPP_TASKS_NAME = "philo-tasks"

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = Path(os.path.expanduser("~/.config/philotes"))
CACHE_DIR = Path(os.path.expanduser("~/.cache/philotes"))

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _resolve_asset_path(rel_path: str) -> Path:
    # 1. Workspace / relative to BASE_DIR
    local_path = BASE_DIR / rel_path
    if local_path.exists():
        return local_path
    # 2. Installed system paths (/opt/philotes, /usr/share/philotes)
    for prefix in [Path("/opt/philotes"), Path("/usr/share/philotes")]:
        sys_path = prefix / rel_path
        if sys_path.exists():
            return sys_path
    return local_path

ICON_HICOLOR_CHAT = _resolve_asset_path("icons/hicolor/chat.svg")
ICON_GREYSCALE_CHAT = _resolve_asset_path("icons/greyscale/chat.svg")
ICON_HICOLOR_MSGS = _resolve_asset_path("icons/hicolor/messages.svg")
ICON_GREYSCALE_MSGS = _resolve_asset_path("icons/greyscale/messages.svg")
ICON_HICOLOR_WORDLE = _resolve_asset_path("icons/hicolor/wordle.svg")
ICON_GREYSCALE_WORDLE = _resolve_asset_path("icons/greyscale/wordle.svg")
ICON_HICOLOR_KEEP = _resolve_asset_path("icons/hicolor/keep.svg")
ICON_GREYSCALE_KEEP = _resolve_asset_path("icons/greyscale/keep.svg")
ICON_HICOLOR_TASKS = _resolve_asset_path("icons/hicolor/tasks.svg")
ICON_GREYSCALE_TASKS = _resolve_asset_path("icons/greyscale/tasks.svg")
ICON_HICOLOR_PHILOTES = _resolve_asset_path("icons/hicolor/philotes.svg")
ICON_GREYSCALE_PHILOTES = _resolve_asset_path("icons/greyscale/philotes.svg")

THEME_CSS_PATH = _resolve_asset_path("styles/dark-sharp.css")

