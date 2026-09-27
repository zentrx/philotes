# Philotes Implementation Document (v5.3.0)

This document provides a comprehensive overview of the currently implemented architecture, design choices, component structures, and lessons learned during the development of **Philotes**.

---

## 1. Overview & System Goals

**Philotes** is a lightweight, Linux-first (Arch Linux optimized) communication application container designed to run continuously with a minimal system resource footprint. It hosts modular sub-applications built on **GTK 4** and **WebKitGTK 6.0**. 

Supported sub-applications:
1. **Google Chat (`philo-chat`)**: Isolated webview container hosting Google Chat with real-time unread badge monitoring and universal image paste.
2. **Google Messages (`philo-msgs`)**: Integrated webview container hosting Google Messages (`messages.google.com/web`) with persistent device pairing, unread SMS/MMS notifications, and universal image paste.
3. **Google Tasks (`philo-tasks`)**: Integrated Google Tasks container with live task monitoring and universal image paste.
4. **Google Keep (`philo-keep`)**: Integrated Google Keep note and task container with upcoming Reminders tracking and universal image paste.
5. **NYT Wordle (`philo-wordle`)**: Interactive NYT Wordle puzzle integration.

---

## 2. Currently Implemented Structures & Architecture

```
                               ┌────────────────────────────────────────┐
                               │            philotes (Main)             │
                               │  - GTK4 Window & Draggable Top Bar     │
                               │  - SettingsManager (settings.json)     │
                               │    └─ AccountManager (accounts.json)   │
                               │  - SessionManager (Profile Symlinks)   │
                               └──────────────────┬─────────────────────┘
                                                  │
        ┌──────────────────────┬───────────────────┼───────────────────┬───────────────────┐
        ▼                      ▼                   ▼                   ▼                   ▼
 ┌───────────────┐     ┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
 │  philo-chat   │     │  philo-msgs   │   │  philo-tasks  │   │  philo-keep   │   │  philo-wordle │
 │ - Google Chat │     │ - Messages    │   │ - Google Tasks│   │ - Google Keep │   │ - NYT Wordle  │
 │ - WebKit 6.0  │     │ - WebKit 6.0  │   │ - WebKit 6.0  │   │ - WebKit 6.0  │   │ - WebKit 6.0  │
 └───────────────┘     └───────────────┘   └───────────────┘   └───────────────┘   └───────────────┘
```

### 2.1 Multi-Process Sub-Application Architecture
- **Master Container (`philotes.main:main`)**: Initializes the main GTK 4 window, top navigation bar, account manager, and view stack.
- **Sub-Application Binaries (`philo-chat`, `philo-msgs`, `philo-wordle`, `philo-keep`, `philo-tasks`)**: Executable Python sub-processes registered via native Linux `prctl(PR_SET_NAME)` so `btop`, `htop`, and `ps aux` accurately display individual task names (`philotes`, `philo-chat`, `philo-msgs`, `philo-wordle`, `philo-keep`, `philo-tasks`) with independent CPU and memory tracking.
- **Background Persistence**: Webviews remain mounted in memory when switching tabs, allowing instant, zero-latency tab switching without web page re-renders.

### 2.2 Auth Card & Service Pool Manager (`philotes.account_manager`)
- **Data Persistence**: Account profiles and card metadata are persisted in `~/.config/philotes/accounts.json`.
- **Card Schema**:
  ```json
  {
    "card_id": "google_1722870000",
    "provider": "google",
    "display_name": "User Name",
    "username": "user@gmail.com",
    "created_at": "2026-08-05 12:30:00",
    "unread_count": 0,
    "active": true,
    "default": true,
    "profile_dir": "google-user1"
  }
  ```
- **Single Active Card Enforcement**: Only one card in a provider service pool can be active (`active: true`). Toggling a card active deactivates all other cards in that pool.
- **Single Default Card Enforcement**: Only one card in a pool is marked default (`default: true`). A symlink at `~/.config/philotes/profiles/google-default` points directly to the default profile folder (`google-user1`).
- **Deletion & Promotion**: Deleting an Auth Card removes its stored profile folder. If the deleted card was default, the oldest remaining card in the pool is automatically promoted to default.
- **Splash Screen Redirection (`philotes.components.splash_view`)**: If 0 cards are active in a pool, tabs redirect to a dark splash screen instructing the user to activate or add an account in Settings.

### 2.3 WebKitGTK 6.0 Session Pools (`philotes.session_manager`)
- **Profile Storage**: Profile directories stored under `~/.config/philotes/profiles/<profile_dir>`.
- **Session Data**: Each profile maintains an isolated or shared `WebKit.NetworkSession` using a persistent SQLite cookie database (`cookies.sqlite`).
- **Unified Session Pool**: `philo-chat` and `philo-msgs` share the active Google profile session pool, allowing single sign-on across Google services and persistent Web QR pairing for Google Messages.

### 2.4 GCP OAuth 2.0 PKCE Authorization (`philotes.auth`)
- **Desktop Client Credentials**: Reads `~/.config/philotes/client_secret.json`.
- **PKCE Verification**: Uses PKCE `code_verifier` and SHA256 `code_challenge` for secure authentication without embedded browser secrets.
- **Loopback Server**: Launches a temporary local HTTP server (`http://127.0.0.1:8080`) to capture authorization codes automatically.
- **UserInfo Integration**: Fetches display name and email via Google's OAuth 2.0 UserInfo API to auto-populate Auth Cards.

### 2.5 Dynamic Top Bar Navigation & Draggable Tab Reordering
- **Theme**: Defined in `styles/dark-sharp.css` with Arch dark slate palette (`#1a1b26`, `#24283b`, `#7aa2f7`), 0–2px sharp borders, and high-contrast styling.
- **Native XDG Portal Color Scheme Synchronization (`philotes.settings_manager`)**:
  - Automatically queries the Linux desktop environment's preferred color scheme via D-Bus XDG Desktop Portal (`org.freedesktop.portal.Settings` -> `org.freedesktop.appearance:color-scheme`) and GSettings (`org.gnome.desktop.interface:color-scheme`).
  - Sets `Gtk.Settings:gtk-application-prefer-dark-theme`, which WebKitGTK uses to evaluate `@media (prefers-color-scheme: dark)`. This ensures standalone web applications like Google Tasks render in dark mode matching the application and OS.
  - Dynamically listens to the portal's `SettingChanged` signal so changes in desktop appearance propagate to running WebViews in real time.
- **Draggable Reordering (`Gtk.DragSource` / `Gtk.DropTarget`)**:
  - Dragging is enabled exclusively on the **currently active tab** (`tab_id == self.current_tab`), preventing misclicks when switching tabs.
  - Interactive hover drop indicators highlight the insertion boundary (`.tab-drop-before` / `.tab-drop-after`).
  - Seamless child reordering within `self.tabs_box` via `reorder_child_after` preserves mounted webview states with zero flicker.
- **Double-Click Tab Refresh (`Gtk.GestureClick`)**:
  - Double-clicking any tab header triggers an immediate reload of the corresponding sub-application webview via `refresh_tab(tab_id)`.
  - Configured via `Gtk.GestureClick` with `Gtk.PropagationPhase.CAPTURE` on each tab button and the settings button.
  - Native Linux double-click threshold detection: resolves `gtk-double-click-time` hierarchically via D-Bus XDG Desktop Portal (`org.freedesktop.portal.Settings`), GSettings (`org.gnome.desktop.peripherals.mouse:double-click`), and `Gtk.Settings`, dynamically synchronizing the interval to GTK.
- **Parent Settings Manager (`philotes.settings_manager`)**:
  - `SettingsManager` manages non-account preferences in `~/.config/philotes/settings.json`, completely separate from `accounts.json`.
  - Coordinates identity service pools by exposing `settings.accounts`.
  - Default tab order: `Chat`, `Messages`, `Tasks`, `Keep`, `Wordle`.
  - Settings View provides a dedicated `↺ Reset Tab Order to Default` action.
- **Dynamic Tab States**:
  - **Active/Selected Tab**: Displays full-color icon (`icons/hicolor/<app>.svg`), visible text label, and inline unread count badge pill.
  - **Inactive/Unselected Tab**: Displays greyscale icon (`icons/greyscale/<app>.svg`), hides text label, and overlays unread badge directly over the top-right corner of the icon using `Gtk.Overlay`.

### 2.6 Universal WebKit Image Paste Bridge (`philotes.clipboard_bridge`)
- **WebKitGTK 6.0 Clipboard Fix**: WebKitGTK's native GTK platform clipboard implementation (`PasteboardGtk`) omits binary image streams from `ClipboardEvent.clipboardData` during native paste dispatch. `philotes.clipboard_bridge` intercepts paste key shortcuts (`Ctrl+V` and `Shift+Insert`) via `Gtk.EventControllerKey`.
- **Gdk.Clipboard Extraction**: Asynchronously extracts image data (`Gdk.Texture` / PNG) from `Gdk.Clipboard`.
- **DOM Synthetic Injection**: Base64 encodes PNG bytes and dispatches a synthetic `ClipboardEvent('paste')` populated with a `DataTransfer` holding a web `File` object (`pasted_image.png`) directly into the active editable element.
- **Universal Default Activation**: Enabled by default across all sub-applications via `enable_image_paste(self.web_view)`.

### 2.7 Service Pool Tab Availability & Memory Lifecycle
- **App-Wide Availability via `SettingsManager`**:
  - Controlled tabs for each provider pool (`google`: Chat, Messages, Tasks, Keep; `nytimes`: Wordle) are configured via `get_enabled_tabs()`, `is_tab_enabled()`, and `set_tab_enabled()`.
  - Persisted independently of auth credentials inside `~/.config/philotes/settings.json` under `"enabled_tabs"`.
- **Zero-Latency Background Loading**:
  - Enabled tabs load on application launch or immediately upon toggle in the background, mounting WebKit views into `GtkStack`.
- **Full Memory Teardown & Process Cleanup**:
  - When a tab is disabled at runtime, its DOM polling and completion GLib timers are removed (`GLib.source_remove`), WebKit loading is stopped with navigation to `about:blank`, IPC pipes and GLib IO watches are closed, the widget is removed from `GtkStack`, and Python garbage collection is triggered.
  - The tab button is hidden from the top bar. If the active tab was the disabled tab, the application switches automatically to the next available tab or Settings.
- **Position Preservation**:
  - When re-enabling a tab, the tab button is shown and immediately re-ordered according to the persisted `tab_order`, restoring it into the exact position it previously occupied.

### 2.8 Arch Linux Pacman Packaging
- **`PKGBUILD`**: Complete Arch Linux PKGBUILD script specifying runtime dependencies (`python`, `python-gobject`, `webkitgtk-6.0`, `gtk4`, `hicolor-icon-theme`) and build dependencies (`python-setuptools`, `python-build`, `python-installer`, `python-wheel`).
- **`install.sh`**: One-step script executing `makepkg -ef -si --noconfirm` to compile wheel packages and install via pacman.
- **`com.philotes.app.desktop` & `philotes.desktop`**: Desktop entry launcher integration matching `application_id="com.philotes.app"` for Wayland desktop environments (Rofi, dmenu, Hyprland, KDE, GNOME).

### 2.9 Master-Detail Sidebar Settings Architecture & Mobile Responsiveness
- **Master-Detail Navigation Layout (`philotes.views.settings_view`)**:
  - Horizontal root container dividing into a collapsible left navigation rail and right detail stack (`Gtk.Stack`).
  - **Collapsible Icon Rail**: Defaults to 52px width displaying category icons (`🌐`, `📰`, `📑`, `⚙️`) designed for thin-column tiling splits and mobile dock geometries (~380px–500px). Expanding via top `☰` toggle expands width to 160px with category titles.
  - **Dynamic Category Registry**: Fully modular `CATEGORIES` list configuring pages for `google`, `nytimes`, `tabs`, and `system`.
- **Mobile-First Responsive Card Geometry**:
  - Replaced rigid desktop min-widths (`540px` and `480px`) with fluid width sizing (`min-width: 0;` and `hexpand=True`).
  - **Vertical Block Auth Cards (`philotes.components.account_card`)**: Refactored card hierarchy into a 3-tier vertical block layout (Header with active pill and unread count, Info row with email and timestamp, and Actions row with inline deletion confirmation and default/subscription controls) that wraps comfortably without horizontal clipping.
- **Strict Adherence to Project State Conventions (Rule 7.2)**:
  - State detection across all settings components operates strictly on internal models (`SettingsManager`, account metadata dictionaries), never relying on UI label or button string matching.

---

## 3. Design Choices & Decisions

| Decision | Alternative Considered | Rationale for Choice |
| :--- | :--- | :--- |
| **Multi-Process Architecture (`prctl`)** | Single-process with internal threads | Multi-process ensures process manager visibility in `btop`/`htop`, crash isolation (webview panic doesn't kill container), and instant 100% RAM recovery on process exit. |
| **Shared Session Pool Per Provider** | Isolated WebKit session per sub-app tab | Sharing the `WebKit.NetworkSession` across `philo-chat` and `philo-msgs` enables seamless Google SSO and maintains device pairing for Google Messages without re-authenticating. |
| **Symlink Default Profile Pointer** | Storage-only JSON references | Maintaining `google-default` -> `google-user1` symlink allows external scripts and CLI utilities to inspect active credentials without parsing JSON files. |
| **DOM Title Observer IPC** | Scraping DOM elements via JS injections | Observing `document.title` `(N)` updates provides a robust, non-fragile method to calculate unread badge counts across web application redesigns. |

---

## 4. Lessons Learned Along the Way

1. **Google OAuth & WebKitGTK User-Agent Filtering**:
   - *Issue*: Google OAuth endpoints reject standard WebKitGTK user-agent strings with `403 disallowed_useragent`.
   - *Lesson*: Explicitly configuring a modern Chrome Desktop User-Agent string (`Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ... Chrome/...`) on the `WebKit.WebView` solved authentication blocks.

2. **Google Account Navigation & Auto-Login**:
   - *Issue*: Navigating directly to service URLs when changing active accounts sometimes retained previous cookie tokens.
   - *Lesson*: Directing the WebView to `https://accounts.google.com/ServiceLogin?continue=<target_url>&Email=<username>` ensures proper account switching and session binding.

3. **GTK 4 `Gtk.Overlay` Badge Alignment**:
   - *Issue*: Badges on collapsed tabs overlapped adjacent top bar icons when unread counts reached 2 or 3 digits.
   - *Lesson*: Applying custom CSS positioning, negative margins, and relative z-index overlays in `dark-sharp.css` ensured badge pills render cleanly without clipping.

4. **Linux Task Naming Limits (`prctl`)**:
   - *Issue*: Linux `prctl(PR_SET_NAME)` truncates process names longer than 15 bytes.
   - *Lesson*: Using concise sub-application names (`philo-chat`, `philo-msgs`) keeps process names under the 15-character OS threshold for system process monitors.
