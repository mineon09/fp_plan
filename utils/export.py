"""
データ永続化ユーティリティ (JSON 保存・読込)
"""

import json
import os

from config import DATA_DIR, BANK_RATES_FILE, USER_PROFILE_FILE


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def save_bank_rates(banks: list[dict], fetch_date: str = "") -> None:
    _ensure_data_dir()
    with open(BANK_RATES_FILE, "w", encoding="utf-8") as f:
        json.dump({"fetch_date": fetch_date, "banks": banks}, f, ensure_ascii=False, indent=2)


def load_bank_rates() -> dict | None:
    if not os.path.exists(BANK_RATES_FILE):
        return None
    with open(BANK_RATES_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_user_profile(profile: dict) -> None:
    _ensure_data_dir()
    with open(USER_PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def load_user_profile() -> dict | None:
    if not os.path.exists(USER_PROFILE_FILE):
        return None
    with open(USER_PROFILE_FILE, encoding="utf-8") as f:
        return json.load(f)
