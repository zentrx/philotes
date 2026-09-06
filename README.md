# Philotes (v5.0.0)

**Philotes** is a lightweight, Linux-first (Arch Linux optimized) communication application container designed to run continuously with minimal system resource footprint. Built on **GTK 4** and **WebKitGTK 6.0**, it hosts modular sub-applications: **Google Chat** (`philo-chat`), **Google Messages** (`philo-msgs`), **Google Keep** (`philo-keep`), **Google Tasks** (`philo-tasks`), and **NYT Wordle** (`philo-wordle`).

---

## Features

- **Process Isolation & OS Identification (`btop`/`htop`)**:
  - Main process (`philotes`) and child sub-application tasks registered via native Linux `prctl(PR_SET_NAME)` to `philotes`, `philo-chat`, `philo-msgs`, `philo-keep`, `philo-tasks`, and `philo-wordle`.
- **Top Bar & Dynamic Tabs**:
  - Modern header bar featuring active expanded tabs (color icon + label + unread/reminder/task badge) and collapsed inactive tabs (greyscale icon + overlayed badge).
  - Background webviews remain mounted in memory for instant tab switching.
- **Single Sign-On & Profile Session Pools**:
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
