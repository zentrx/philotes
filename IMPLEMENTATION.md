# Philotes Implementation Document (v2.0.2)

This document provides a comprehensive overview of the currently implemented architecture, design choices, component structures, and lessons learned during the development of **Philotes**.

---

## 1. Overview & System Goals

**Philotes** is a lightweight, Linux-first (Arch Linux optimized) communication application container designed to run continuously with a minimal system resource footprint. It hosts modular sub-applications built on **GTK 4** and **WebKitGTK 6.0**. 

Version **2.0.0** represents the two primary active communication sub-applications supported by the platform:
1. **Google Chat (`philo-chat`)**: Isolated webview container hosting Google Chat with real-time unread badge monitoring.
2. **Google Messages (`philo-msgs`)**: Integrated webview container hosting Google Messages (`messages.google.com/web`) with persistent device pairing and unread SMS/MMS notifications.

---

## 2. Currently Implemented Structures & Architecture

```
                               ┌────────────────────────────────────────┐
                               │            philotes (Main)             │
                               │  - GTK4 Window & Top Bar Nav           │
                               │  - AccountManager (accounts.json)      │
                               │  - SessionManager (Profile Symlinks)   │
                               └──────────────────┬─────────────────────┘
                                                  │
                       ┌──────────────────────────┴──────────────────────────┐
                       ▼                                                     ▼
           ┌───────────────────────┐                             ┌───────────────────────┐
           │      philo-chat       │                             │      philo-msgs       │
           │  - Google Chat App    │                             │  - Google Messages    │
           │  - WebKitGTK 6.0      │                             │  - WebKitGTK 6.0      │
           │  - Title Observer     │                             │  - Title Observer     │
           └───────────────────────┘                             └───────────────────────┘
```

### 2.1 Multi-Process Sub-Application Architecture
- **Master Container (`philotes.main:main`)**: Initializes the main GTK 4 window, top navigation bar, account manager, and view stack.
- **Sub-Application Binaries (`philo-chat`, `philo-msgs`)**: Executable Python sub-processes registered via native Linux `prctl(PR_SET_NAME)` so `btop`, `htop`, and `ps aux` accurately display individual task names (`philotes`, `philo-chat`, `philo-msgs`) with independent CPU and memory tracking.
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

### 2.5 Dynamic Top Bar Navigation & UI Theme System
- **Theme**: Defined in `styles/dark-sharp.css` with Arch dark slate palette (`#1a1b26`, `#24283b`, `#7aa2f7`), 0–2px sharp borders, and high-contrast styling.
- **Dynamic Tab States**:
  - **Active/Selected Tab**: Displays full-color icon (`icons/hicolor/<app>.svg`), visible text label, and inline unread count badge pill.
  - **Inactive/Unselected Tab**: Displays greyscale icon (`icons/greyscale/<app>.svg`), hides text label, and overlays unread badge directly over the top-right corner of the icon using `Gtk.Overlay`.

### 2.6 Arch Linux Pacman Packaging
- **`PKGBUILD`**: Complete Arch Linux PKGBUILD script specifying runtime dependencies (`python`, `python-gobject`, `webkitgtk-6.0`, `gtk4`, `hicolor-icon-theme`) and build dependencies (`python-setuptools`, `python-build`, `python-installer`, `python-wheel`).
- **`install.sh`**: One-step script executing `makepkg -ef -si --noconfirm` to compile wheel packages and install via pacman.
- **`philotes.desktop`**: Desktop entry launcher integration for Arch desktop environments (Rofi, dmenu, Hyprland, KDE, GNOME).

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
