#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==> Building and Installing Philotes via Pacman (Arch Linux)..."

cd "$SCRIPT_DIR"

if command -v makepkg &> /dev/null; then
    makepkg -ef -si --noconfirm
    echo "==> Philotes successfully installed via pacman!"
else
    echo "==> Warning: makepkg not found, installing locally via pip --editable..."
    cd "$PROJECT_DIR"
    pip install -e . --break-system-packages
    echo "==> Philotes installed locally via pip!"
fi
