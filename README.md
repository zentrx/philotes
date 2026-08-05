# Philotes

**Philotes** is a lightweight, Linux-first (Arch Linux optimized) communication application container designed to run continuously with minimal system resource footprint. Built on **GTK 4** and **WebKitGTK 6.0**, it hosts modular sub-applications starting with **Google Chat** (`philo-chat`).

---

## Features

- **Process Isolation & OS Identification (`btop`/`htop`)**:
  - Task name registered via native Linux `prctl(PR_SET_NAME)` to `philotes` and `philo-chat`.
- **Top Bar & Dynamic Tabs**:
  - Modern header bar featuring active expanded tabs (icon + label + unread badge) and collapsed inactive tabs (greyscale icon + overlayed badge).
  - Background webviews remain mounted in memory for instant tab switching.
- **Single Sign-On & Profile Session Pools**:
  - Shared WebKit 6.0 `NetworkSession` with SQLite persistent cookie database (`cookies.sqlite`).
  - Symlink-based default profile manager (`profiles/google-default` -> `google-user1`).
- **GCP OAuth 2.0 PKCE Authorization**:
  - Permanent refresh token rotation for background Google service integrations.
- **Arch Linux Native Packaging**:
  - Complete `PKGBUILD` and `pkg/install.sh` for pacman installation.

---

## Installation

### On Arch Linux (via Pacman)
```bash
git clone https://github.com/zentrx/philotes.git
cd philotes
./pkg/install.sh
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

2. **GCP OAuth Setup (Settings ⚙)**:
   - Download your Desktop Application OAuth client key from Google Cloud Console.
   - Copy to `~/.config/philotes/client_secret.json`.
   - Open Settings in Philotes and click **Sign in with Google (GCP OAuth)**.

---

## License

MIT License.
