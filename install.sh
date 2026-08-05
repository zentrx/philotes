#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Building and Installing Philotes via Pacman (Arch Linux)..."

if command -v makepkg &> /dev/null; then
    cd "$SCRIPT_DIR"
    makepkg -ef -si --noconfirm
    echo "==> Philotes successfully installed via pacman!"
else
    echo "==> Warning: makepkg not found, installing locally via pip --editable..."
    cd "$SCRIPT_DIR"
    pip install -e . --break-system-packages
    echo "==> Philotes installed locally via pip!"
fi

# YAMIS (Yet Another Monochrome Icon Set) Integration
YAMIS_SCALABLE_DIR="${HOME}/.local/share/icons/YAMIS/apps/scalable"
YAMIS_THEME_DIR="${HOME}/.local/share/icons/YAMIS"

if [ -d "$YAMIS_SCALABLE_DIR" ]; then
    echo "==> YAMIS icon theme detected at $YAMIS_SCALABLE_DIR"
    cp "$SCRIPT_DIR/icons/greyscale/philotes.svg" "$YAMIS_SCALABLE_DIR/philotes.svg"
    echo "==> Installed greyscale Philotes icon to YAMIS theme ($YAMIS_SCALABLE_DIR/philotes.svg)."

    if command -v gtk-update-icon-cache &> /dev/null; then
        echo "==> Rebuilding YAMIS icon theme cache..."
        gtk-update-icon-cache -f -t "$YAMIS_THEME_DIR" || true
        echo "==> Icon theme cache updated successfully!"
    fi
fi

echo "==> Cleaning up build artifacts..."
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist" "$SCRIPT_DIR"/*.egg-info "$SCRIPT_DIR"/*.pkg.tar.zst "$SCRIPT_DIR/src" "$SCRIPT_DIR/pkg"
echo "==> Installation and cleanup complete!"
