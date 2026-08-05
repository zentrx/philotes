# Philotes Future Implementation Document

This document outlines features, architectural enhancements, and potential sub-applications considered for future versions of **Philotes**.

---

## 1. Vision & Roadmap Overview

The primary goal of Philotes is to serve as a Linux-first, resource-efficient container for essential web and desktop communication tools. Following the successful release of **v2.0.0** (featuring **Google Chat** and **Google Messages**), future development will focus on expanding provider support, multi-account concurrency, OS integration, security hardening, and flexible UI layouts.

---

## 2. Expansion of Sub-Applications & Service Pools

### 2.1 Additional Service Pools
- **Discord (`philo-discord`)**:
  - Web container for Discord Web with WebRTC audio/video support.
  - Dedicated notification title observer parsing server mention badges (`(1) Discord`).
- **Slack (`philo-slack`)**:
  - Support for single and multi-workspace Slack logins.
  - Custom WebKit session isolation per Slack workspace.
- **WhatsApp Web (`philo-wa`)**:
  - Persistent QR pairing container for WhatsApp Web.
  - Background memory management to prevent WebMedia session timeouts.
- **Telegram Web (`philo-tg`)**:
  - Web container targeting Telegram Web Z / Web K with background session caching.
- **Element / Matrix (`philo-matrix`)**:
  - Encrypted Matrix web client container with local state persistence.

### 2.2 Custom User WebApp Generator
- **User-Defined Tabs**: Enable users to add arbitrary web applications directly from the Settings view.
- **Configurable Attributes**:
  - Target URL (e.g. `https://web.skype.com`, internal team dashboards).
  - Tab Icon (custom SVG file upload or icon picker).
  - Unread Badge Regex / JS Selector (custom regex for extracting unread count from `document.title`).
  - Custom User-Agent string override.

---

## 3. Multi-Account Concurrent Tab Support

Currently, Philotes enforces a single active Auth Card per provider service pool. 

- **Side-by-Side Multi-Account Instances**:
  - Allow users to spawn multiple active tabs for the *same* provider simultaneously (e.g. `Chat (Work)` and `Chat (Personal)`).
  - Each tab instance will bind to a distinct `NetworkSession` profile folder (`google-user1`, `google-user2`), enabling isolated authentication states running concurrently in separate top bar tabs.

---

## 4. Credential Vault & Security Hardening

- **Keyring / SecretService API Integration**:
  - Store OAuth refresh tokens and `accounts.json` metadata in system keyrings (GNOME Keyring, KWallet, KeePassXC via SecretService DBus).
- **At-Rest Encryption**:
  - Encrypt cached session cookies and local profile databases when the application is locked or closed.
- **Biometric & PAM Application Lock**:
  - Optional Master Password or PAM/biometric prompt upon application launch to prevent unauthorized access to open web sessions.

---

## 5. Native OS & Desktop Integration

### 5.1 Native OS Desktop Notifications
- Integrate `libnotify` / `GNotification` for OS-level popups when unread counts increase.
- Support action buttons inside notifications (e.g. **"Reply"**, **"Mark as Read"**, **"Mute"**).

### 5.2 System Tray / Status Indicator
- Implement system tray indicator via `AppIndicator3` / `KStatusNotifierItem`.
- Quick-action menu: Do Not Disturb toggle, unread message summary, tab launcher, and "Minimize to System Tray" behavior.

### 5.3 Custom Audio Notifications
- Configurable audio alerts per sub-application tab with custom sound file support (`.wav`, `.ogg`).

### 5.4 Global Keyboard Shortcuts
- Navigation hotkeys:
  - `Ctrl+1` .. `Ctrl+9`: Switch directly to tab N.
  - `Ctrl+Tab` / `Ctrl+Shift+Tab`: Cycle through open tabs.
  - `Ctrl+,`: Open Settings.
  - `Ctrl+Shift+M`: Toggle global mute / Do Not Disturb.

---

## 6. UI & Layout Enhancements

- **Interactive Tab Drag-and-Drop Reordering**: Allow users to drag top bar tabs to reorder them dynamically.
- **Split Screen / Tiled View Mode**: Option to split the main window horizontally or vertically to view two sub-apps side-by-side (e.g. Google Chat on the left, Google Messages on the right).
- **Theme Creator & Live Reload**: Built-in CSS theme builder in Settings with live hot-reloading of custom stylesheets.

---

## 7. Packaging & Ecosystem Distribution

- **Arch User Repository (AUR)**: Submit official `philotes` and `philotes-git` packages to the AUR.
- **Flathub / Flatpak Manifest**: Create Flatpak sandbox builds with restricted permission portals.
- **AppImage Build Pipeline**: Automated CI pipeline building standalone AppImage executables for universal Linux distribution compatibility.
