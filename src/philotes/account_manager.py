import os
import sys
import json
import time
import shutil
from pathlib import Path
from philotes.config import CONFIG_DIR

ACCOUNTS_FILE = CONFIG_DIR / "accounts.json"
PROFILES_BASE_DIR = CONFIG_DIR / "profiles"
PROFILES_BASE_DIR.mkdir(parents=True, exist_ok=True)

class AccountManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.accounts = self._load_accounts()
        self.apply_defaults_on_initial_load()

    def _load_accounts(self):
        if ACCOUNTS_FILE.exists():
            try:
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                sys.stderr.write(f"[Philotes AccountManager] Error loading accounts.json: {e}\n")
        return []

    def apply_defaults_on_initial_load(self):
        """
        Rule: On initial load, if an Auth Card is marked as default, use that authentication profile as active.
        """
        providers = set(card.get("provider") for card in self.accounts if card.get("provider"))
        modified = False
        for provider in providers:
            default_card = self.get_default_card(provider)
            if default_card:
                default_id = default_card.get("card_id")
                for card in self.accounts:
                    if card.get("provider") == provider:
                        should_be_active = (card.get("card_id") == default_id)
                        if card.get("active") != should_be_active:
                            card["active"] = should_be_active
                            modified = True
        if modified:
            self._save_accounts()

    def _save_accounts(self):
        try:
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.accounts, f, indent=2)
        except Exception as e:
            sys.stderr.write(f"[Philotes AccountManager] Error saving accounts.json: {e}\n")

    def get_cards(self, provider: str = None):
        """
        Returns cards for a provider, sorted by creation timestamp (oldest first at top, newest at bottom).
        """
        if provider:
            cards = [acc for acc in self.accounts if acc.get("provider") == provider]
        else:
            cards = list(self.accounts)
        
        cards.sort(key=lambda item: item.get("created_at", ""))
        return cards

    def get_total_card_count(self) -> int:
        return len(self.accounts)

    def get_active_card(self, provider: str):
        # 1. Look for explicitly active card
        for card in self.accounts:
            if card.get("provider") == provider and card.get("active", False):
                return card
        # 2. Fallback to default card
        for card in self.accounts:
            if card.get("provider") == provider and card.get("default", False):
                return card
        # 3. Fallback to first available card in provider pool
        cards = self.get_cards(provider)
        if cards:
            return cards[0]
        return None

    def get_default_card(self, provider: str):
        for card in self.accounts:
            if card.get("provider") == provider and card.get("default", False):
                return card
        return None

    def add_auth_card(self, provider: str, display_name: str, username: str, profile_dir: str = None) -> dict:
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
        card_id = f"{provider}_{int(time.time() * 1000)}"
        if not profile_dir:
            profile_dir = f"{provider}-{username.split('@')[0]}"

        existing_cards = self.get_cards(provider)

        # Rule: Creation -> active = True (deactivates all other cards in pool)
        for card in self.accounts:
            if card.get("provider") == provider:
                card["active"] = False

        # Rule: Creation -> default = True if first card in pool, otherwise False
        is_default = len(existing_cards) == 0

        new_card = {
            "card_id": card_id,
            "provider": provider,
            "display_name": display_name,
            "username": username,
            "created_at": timestamp_str,
            "unread_count": 0,
            "active": True,
            "default": is_default,
            "profile_dir": profile_dir,
        }

        self.accounts.append(new_card)
        self._save_accounts()
        self._sync_default_symlink(provider)
        return new_card

    def set_active(self, card_id: str, provider: str):
        target_card = None
        for card in self.accounts:
            if card.get("provider") == provider and card.get("card_id") == card_id:
                target_card = card
                break

        if not target_card:
            return

        is_currently_active = target_card.get("active", False)

        # Deactivate all cards in provider pool
        for card in self.accounts:
            if card.get("provider") == provider:
                card["active"] = False

        # Toggle: if it was inactive, activate it
        if not is_currently_active:
            target_card["active"] = True

        self._save_accounts()

    def set_default(self, card_id: str, provider: str):
        for card in self.accounts:
            if card.get("provider") == provider:
                card["default"] = (card.get("card_id") == card_id)

        self._save_accounts()
        self._sync_default_symlink(provider)

    def delete_auth_card(self, card_id: str, provider: str):
        deleted_card = None
        for card in self.accounts:
            if card.get("provider") == provider and card.get("card_id") == card_id:
                deleted_card = card
                break

        if not deleted_card:
            return

        was_default = deleted_card.get("default", False)
        profile_dir_name = deleted_card.get("profile_dir")

        # Remove card from memory
        self.accounts = [card for card in self.accounts if card.get("card_id") != card_id]

        # Delete profile data directory
        if profile_dir_name:
            target_path = PROFILES_BASE_DIR / profile_dir_name
            if target_path.exists():
                try:
                    shutil.rmtree(target_path)
                except Exception as e:
                    sys.stderr.write(f"[Philotes AccountManager] Error deleting profile dir {target_path}: {e}\n")

        # Rule: If deleted card was default, promote oldest remaining card in pool to default
        remaining_pool_cards = self.get_cards(provider)
        if was_default and remaining_pool_cards:
            oldest_remaining = remaining_pool_cards[0]
            oldest_remaining["default"] = True
            for card in remaining_pool_cards[1:]:
                card["default"] = False

        self._save_accounts()
        self._sync_default_symlink(provider)

    def _sync_default_symlink(self, provider: str):
        symlink_path = PROFILES_BASE_DIR / f"{provider}-default"

        if symlink_path.is_symlink():
            try:
                symlink_path.unlink()
            except Exception:
                pass
        elif symlink_path.exists():
            try:
                shutil.rmtree(symlink_path)
            except Exception:
                pass

        default_card = self.get_default_card(provider)
        if default_card and default_card.get("profile_dir"):
            target_dir = PROFILES_BASE_DIR / default_card["profile_dir"]
            target_dir.mkdir(parents=True, exist_ok=True)
            try:
                symlink_path.symlink_to(default_card["profile_dir"])
            except Exception as e:
                sys.stderr.write(f"[Philotes AccountManager] Error creating default symlink: {e}\n")
