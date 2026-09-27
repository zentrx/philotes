# Philotes (v5.3.0)

**Philotes** is a lightweight, Linux-first (Arch Linux optimized) communication application container designed to run continuously with minimal system resource footprint. Built on **GTK 4** and **WebKitGTK 6.0**, it hosts modular sub-applications: **Google Chat** (`philo-chat`), **Google Messages** (`philo-msgs`), **Google Tasks** (`philo-tasks`), **Google Keep** (`philo-keep`), and **NYT Wordle** (`philo-wordle`).

---

## Features

- **Process Isolation & OS Identification (`btop`/`htop`)**:
  - Main process (`philotes`) and child sub-application tasks registered via native Linux `prctl(PR_SET_NAME)` to `philotes`, `philo-chat`, `philo-msgs`, `philo-keep`, `philo-tasks`, and `philo-wordle`.
- **Native XDG Portal Color Scheme Synchronization**:
  - Automatically queries the Linux desktop environment's preferred color scheme via D-Bus XDG Desktop Portal (`org.freedesktop.appearance:color-scheme`) and GSettings (`org.gnome.desktop.interface:color-scheme`).
  - Synchronizes to GTK's `gtk-application-prefer-dark-theme` so WebKitGTK evaluates `@media (prefers-color-scheme: dark)` accurately across all web applications (ensuring dark mode in Google Tasks and all sub-applications).
  - Dynamically monitors portal `SettingChanged` signals to transition running WebViews between light and dark themes in real time without restart.
- **Top Bar & Dynamic Reorderable Tabs**:
  - Double-click tab header to refresh: double-clicking any tab header triggers an instant page refresh/reload using native Linux `Gtk.GestureClick` and system double-click threshold.
  - Drag-and-drop tab reordering when tabs are active, allowing customized arrangements.
  - Persistent tab order saved in `~/.config/philotes/settings.json` across application restarts.
  - Reset Tab Order button in Settings to return to default (`Chat`, `Messages`, `Tasks`, `Keep`, `Wordle`).
  - Active expanded tabs (color icon + label + unread/reminder/task badge) and collapsed inactive tabs (greyscale icon + overlayed badge).
  - Background webviews remain mounted in memory for instant tab switching.
- **Service Pool Tab Enable/Disable & Memory Teardown**:
  - App-wide tab availability controlled per Service Pool in Settings (`google` and `nytimes` pools).
  - Disabled tabs release all memory (WebKit views, DOM polling timers, and IPC channels torn down) and hide from the top bar.
  - Re-enabled tabs automatically restore into their original position in the top bar and mount in the background.
- **Master-Detail Responsive Settings & Profile Pools**:
  - Master-Detail sidebar architecture with collapsible icon-rail mode (52px rail with `☰` toggle) optimized for mobile and thin-column displays (~380px–500px).
  - Extensible modular category registry (`Google`, `NYTimes`, `Tab Layout`, `System`).
  - Fluid-width vertical block Auth Cards with real-time active status pills, default promotion, deletion confirmation, and subscription controls.
  - Unified configuration hub (`SettingsManager`) coordinating non-account UI preferences and authentication service pools.
  - Shared WebKit 6.0 `NetworkSession` with SQLite persistent cookie database (`cookies.sqlite`) across service pools.
  - Symlink-based default profile manager (`profiles/google-default` -> `google-user1`).
- **GCP OAuth 2.0 PKCE Authorization**:
  - Permanent refresh token rotation for background Google service integrations.
- **Arch Linux Native Packaging**:
  - Complete `PKGBUILD` and `install.sh` for pacman installation.

---

## Installation

### On Arch Linux (via Pacman)
```bash
git clone https://github.com/zentrx/philotes.git
cd philotes
./install.sh
```

### Local Development / PyPI Setup
```bash
pip install -e .
philotes
```

---

## Usage & Configuration

1. **Google Chat (`philo-chat`)**:
   - Opens Google Chat in an isolated WebKit 6.0 webview container.
   - Monitors unread chat counts live via `document.title` observers and updates top bar badges.

2. **Google Messages (`philo-msgs`)**:
   - Connects to Google Messages (`messages.google.com/web`) sharing the Google auth profile.
   - Persists Web QR device pairings and displays real-time SMS/MMS unread badges.

3. **Google Keep (`philo-keep`)**:
   - Opens Google Keep (`keep.google.com`) sharing the active Google Auth Card profile.
   - Tracks upcoming Keep Reminders and displays live reminder count badges.

4. **Google Tasks (`philo-tasks`)**:
   - Opens Google Tasks (`tasks.google.com`) sharing the active Google Auth Card profile.
   - Monitors pending task counts live and displays task count badges in the top bar.

5. **GCP OAuth Setup (Settings ⚙)**:
   - Download your Desktop Application OAuth client key from Google Cloud Console.
   - Copy to `~/.config/philotes/client_secret.json`.
   - Open Settings in Philotes and click **Sign in with Google (GCP OAuth)**.

---

## Documentation

- [Implementation Document](IMPLEMENTATION.md): Implemented structures, architectural decisions, and lessons learned.
- [Future Considerations Document](FUTURE_IMPLEMENTATION.md): Feature roadmap and upcoming architectural considerations.

---

## License

MIT License.
