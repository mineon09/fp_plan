"""
定数・設定値
"""

# ---------------------------------------------------------------------------
# 対応銀行デフォルトリスト（2024年末時点参考値）
# ---------------------------------------------------------------------------
DEFAULT_BANKS = [
    {"bank_name": "住信SBIネット銀行", "variable_35": 0.32, "fixed_35": 1.85, "fixed_10": 1.20, "has_team_dan": True, "notes": "ネット銀行"},
    {"bank_name": "auじぶん銀行",      "variable_35": 0.31, "fixed_35": 1.90, "fixed_10": 1.25, "has_team_dan": True, "notes": "ネット銀行"},
    {"bank_name": "PayPay銀行",        "variable_35": 0.38, "fixed_35": 1.95, "fixed_10": 1.30, "has_team_dan": True, "notes": "ネット銀行"},
    {"bank_name": "楽天銀行",           "variable_35": 0.44, "fixed_35": 2.00, "fixed_10": 1.35, "has_team_dan": True, "notes": "ネット銀行"},
    {"bank_name": "三菱UFJ銀行",       "variable_35": 0.48, "fixed_35": 2.10, "fixed_10": 1.50, "has_team_dan": True, "notes": "メガバンク"},
    {"bank_name": "みずほ銀行",         "variable_35": 0.50, "fixed_35": 2.05, "fixed_10": 1.45, "has_team_dan": True, "notes": "メガバンク"},
    {"bank_name": "三井住友銀行",       "variable_35": 0.47, "fixed_35": 2.08, "fixed_10": 1.48, "has_team_dan": True, "notes": "メガバンク"},
    {"bank_name": "りそな銀行",         "variable_35": 0.49, "fixed_35": 2.12, "fixed_10": 1.52, "has_team_dan": True, "notes": "地銀系"},
    {"bank_name": "フラット35（機構）", "variable_35": None, "fixed_35": 1.82, "fixed_10": None, "has_team_dan": False, "notes": "政府系・固定専用"},
]

# ---------------------------------------------------------------------------
# ローン計算デフォルト
# ---------------------------------------------------------------------------
LOAN_DEFAULTS = {
    "amount_man":        3000,   # 借入金額（万円）
    "period_years":      35,     # 借入期間（年）
    "down_payment_man":  0,      # 頭金（万円）
    "bonus_ratio":       0.0,    # ボーナス返済割合
}

# ---------------------------------------------------------------------------
# 金利バリデーション
# ---------------------------------------------------------------------------
RATE_MIN = 0.1   # %
RATE_MAX = 8.0   # %

# ---------------------------------------------------------------------------
# 金利上昇シナリオ（変動用）
# ---------------------------------------------------------------------------
RATE_SCENARIOS = {
    "現状維持":  0.0,
    "+1%上昇":   1.0,
    "+2%上昇":   2.0,
    "+3%上昇":   3.0,
}

# ---------------------------------------------------------------------------
# 人生設計デフォルト
# ---------------------------------------------------------------------------
LIFE_DEFAULTS = {
    "age_now":            35,
    "age_spouse":         33,
    "age_death":          90,
    "income_man":         600,    # 万円/年（税引き前）
    "income_spouse_man":  400,
    "income_growth_rate": 0.015,  # 1.5%/年
    "retire_age":         65,
    "severance_pay_man":  1000,
    "pension_start_age":  65,
    "pension_monthly_man": 22,    # 万円/月（2人合計）
    "living_cost_monthly_man": 25,
    "living_cost_retire_man":  22,
    "inflation_rate":     0.020,
    "assets_man":         500,
    "invest_return":      0.040,
}

# ---------------------------------------------------------------------------
# シナリオパラメータ（楽観/ベース/悲観）
# ---------------------------------------------------------------------------
SCENARIOS = {
    "楽観": {"rate_delta": 0.5,  "invest_return": 0.060, "inflation": 0.015, "income_growth": 0.020},
    "ベース": {"rate_delta": 1.0, "invest_return": 0.040, "inflation": 0.020, "income_growth": 0.015},
    "悲観": {"rate_delta": 2.5,  "invest_return": 0.020, "inflation": 0.030, "income_growth": 0.005},
}

# ---------------------------------------------------------------------------
# ライフイベント プリセット
# ---------------------------------------------------------------------------
LIFE_EVENT_PRESETS = [
    {"name": "教育費（子①）",   "age_start": 38, "age_end": 58, "total_man": 1200, "recurring": True},
    {"name": "教育費（子②）",   "age_start": 40, "age_end": 60, "total_man": 1200, "recurring": True},
    {"name": "車両購入①",        "age_start": 40, "age_end": 40, "total_man": 350,  "recurring": False},
    {"name": "車両購入②",        "age_start": 50, "age_end": 50, "total_man": 350,  "recurring": False},
    {"name": "車両購入③",        "age_start": 60, "age_end": 60, "total_man": 350,  "recurring": False},
    {"name": "住宅リフォーム",   "age_start": 55, "age_end": 55, "total_man": 300,  "recurring": False},
    {"name": "親の介護費用",      "age_start": 65, "age_end": 75, "total_man": 500,  "recurring": True},
    {"name": "旅行・趣味（老後）", "age_start": 65, "age_end": 80, "total_man": 50,   "recurring": True},
    {"name": "葬儀・終活費用",   "age_start": 80, "age_end": 80, "total_man": 300,  "recurring": False},
]

# ---------------------------------------------------------------------------
# データファイルパス
# ---------------------------------------------------------------------------
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BANK_RATES_FILE   = os.path.join(DATA_DIR, "bank_rates.json")
USER_PROFILE_FILE = os.path.join(DATA_DIR, "user_profile.json")
