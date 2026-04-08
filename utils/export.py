"""
データ永続化ユーティリティ (JSON 保存・読込)
"""

import json
import os

from config import DATA_DIR, BANK_RATES_FILE, USER_PROFILE_FILE, LIFE_DEFAULTS_V2


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


def migrate_profile_v1_to_v2(profile_v1: dict) -> dict:
    """
    v1 フラットプロファイルを v2 拡張フィールドに移行する。
    既存キーはそのまま保持し、v2 固有キーをデフォルト値で補完する。
    """
    v2 = {**LIFE_DEFAULTS_V2, **profile_v1}
    # v1 の pension_monthly_man（2人合計）を v2 個別フィールドに按分（5:3 比率でデフォルト分割）
    if "primary_pension_monthly_man" not in profile_v1:
        total_pension = profile_v1.get("pension_monthly_man", LIFE_DEFAULTS_V2["pension_monthly_man"])
        v2["primary_pension_monthly_man"] = round(total_pension * 0.625, 1)
        v2["spouse_pension_monthly_man"]  = round(total_pension * 0.375, 1)
    return v2


def save_user_profile(profile: dict) -> None:
    _ensure_data_dir()
    with open(USER_PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def load_user_profile() -> dict | None:
    if not os.path.exists(USER_PROFILE_FILE):
        return None
    with open(USER_PROFILE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    # v1 プロファイルを自動マイグレーション
    if "primary_pension_monthly_man" not in data and "spouse_pension_monthly_man" not in data:
        data = migrate_profile_v1_to_v2(data)
    return data
