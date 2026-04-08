"""
Module 4: 人生設計キャッシュフロー計算エンジン
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from config import LIFE_DEFAULTS, SCENARIOS


# ---------------------------------------------------------------------------
# 収入計算ヘルパー（v1 / v2 兼用）
# ---------------------------------------------------------------------------

def _calc_income(p: dict, age: int, age_now: int) -> float:
    """
    年間収入を計算する。v1（フラット）・v2（配偶者個別）の両スキーマに対応。

    v2 判定: p に 'spouse_retire_age' が存在する場合は v2 モード。
    v2 では配偶者の成長率・定年・退職金・年金を個別に管理する。
    """
    years_elapsed = age - age_now

    # ---- 本人収入 ----
    retire_age = p["retire_age"]
    if age < retire_age:
        primary = p["income_man"] * 10000 * (1 + p["income_growth_rate"]) ** years_elapsed
    elif age == retire_age:
        primary = p.get("severance_pay_man", 0) * 10000
    else:
        primary = 0.0

    # 本人年金
    pension_start = p.get("pension_start_age", retire_age)
    if age >= pension_start:
        # v2: primary_pension_monthly_man が個別に存在する場合はそちらを優先
        if "primary_pension_monthly_man" in p:
            primary += p["primary_pension_monthly_man"] * 10000 * 12
        else:
            # v1: pension_monthly_man を 2 人分として使用（配偶者側で重複加算しない）
            primary += p["pension_monthly_man"] * 10000 * 12

    # ---- 配偶者収入 ----
    # v2 モード: spouse_retire_age が存在する
    is_v2 = "spouse_retire_age" in p
    spouse_retire = p.get("spouse_retire_age", retire_age)
    spouse_growth = p.get("spouse_income_growth_rate", 0.0)

    loss_age   = p.get("spouse_income_loss_age")
    resume_age = p.get("spouse_income_resume_age")
    resume_ratio = p.get("spouse_income_after_resume_ratio", 1.0)

    if age < spouse_retire:
        base_spouse = p.get("income_spouse_man", 0) * 10000
        if is_v2 and spouse_growth > 0:
            base_spouse *= (1 + spouse_growth) ** years_elapsed
        # 収入消滅シナリオ
        if loss_age and age >= loss_age:
            if resume_age and age >= resume_age:
                spouse = base_spouse * resume_ratio
            else:
                spouse = 0.0
        else:
            spouse = base_spouse
    elif age == spouse_retire:
        spouse = p.get("spouse_severance_man", 0) * 10000
    else:
        spouse = 0.0

    # 配偶者年金（v2 のみ個別管理）
    if is_v2 and "spouse_pension_monthly_man" in p:
        spouse_pension_start = p.get("spouse_pension_start_age", 65)
        if age >= spouse_pension_start:
            spouse += p["spouse_pension_monthly_man"] * 10000 * 12

    return primary + spouse


def calc_life_cashflow(
    profile: dict,
    loan_schedule: pd.DataFrame | None,
    life_events: list[dict],
) -> pd.DataFrame:
    """
    生涯キャッシュフロー年次計算。

    profile keys (万円/年 / 割合): 全て LIFE_DEFAULTS 参照。v2 キーは LIFE_DEFAULTS_V2 参照。
    loan_schedule: loan_simulator の amortization_schedule (月次) または None。
    life_events: [{"name": str, "age_start": int, "age_end": int, "total_man": float, "recurring": bool}]

    Returns DataFrame per year:
        age, income, expense, loan_annual, life_event_cost,
        net_cashflow, invest_gain, assets
    """
    p = {**LIFE_DEFAULTS, **profile}
    age_now = p["age_now"]
    age_death = p["age_death"]

    # 年次ローン返済額マップ（月次→年次集計）
    loan_by_age: dict[int, float] = {}
    if loan_schedule is not None and not loan_schedule.empty:
        loan_schedule = loan_schedule.copy()
        loan_schedule["age"] = age_now + (loan_schedule["month"] - 1) // 12
        loan_by_age = loan_schedule.groupby("age")["payment"].sum().to_dict()

    # ライフイベント年次コストマップ
    event_by_age: dict[int, float] = {}
    for ev in life_events:
        a_start = ev["age_start"]
        a_end = ev["age_end"]
        total = ev["total_man"] * 10000
        if ev.get("recurring", False) and a_end > a_start:
            annual_cost = total / (a_end - a_start + 1)
            for age in range(a_start, a_end + 1):
                event_by_age[age] = event_by_age.get(age, 0) + annual_cost
        else:
            event_by_age[a_start] = event_by_age.get(a_start, 0) + total

    rows = []
    assets = p["assets_man"] * 10000

    for age in range(age_now, age_death + 1):
        years_elapsed = age - age_now

        # 収入（v1/v2 兼用ヘルパー）
        income = _calc_income(p, age, age_now)

        # 支出（インフレ考慮）
        if age < p["retire_age"]:
            expense = p["living_cost_monthly_man"] * 10000 * 12 * (1 + p["inflation_rate"]) ** years_elapsed
        else:
            expense = p["living_cost_retire_man"] * 10000 * 12 * (1 + p["inflation_rate"]) ** years_elapsed

        # ローン返済
        loan_annual = loan_by_age.get(age, 0.0)

        # ライフイベント
        life_event_cost = event_by_age.get(age, 0.0)

        # 純キャッシュフロー
        net_cf = income - expense - loan_annual - life_event_cost

        # 投資収益（前年末資産 × 投資利回り）
        invest_gain = max(assets, 0) * p["invest_return"]

        assets += net_cf + invest_gain

        rows.append({
            "age": age,
            "income": income,
            "expense": expense,
            "loan_annual": loan_annual,
            "life_event_cost": life_event_cost,
            "net_cashflow": net_cf,
            "invest_gain": invest_gain,
            "assets": assets,
        })

    return pd.DataFrame(rows)


def calc_scenarios(
    profile: dict,
    loan_schedule: pd.DataFrame | None,
    life_events: list[dict],
) -> dict[str, pd.DataFrame]:
    """楽観/ベース/悲観の3シナリオを同時計算"""
    results = {}
    for scenario_name, params in SCENARIOS.items():
        scenario_profile = {
            **profile,
            "invest_return": params["invest_return"],
            "inflation_rate": params["inflation"],
            "income_growth_rate": params["income_growth"],
        }
        results[scenario_name] = calc_life_cashflow(scenario_profile, loan_schedule, life_events)
    return results


def life_summary(df: pd.DataFrame, age_now: int, retire_age: int) -> dict:
    """生涯CFサマリーカード指標を計算"""
    # 完済年齢（ローン返済がなくなる年）
    loan_ages = df[df["loan_annual"] > 0]["age"]
    payoff_age = int(loan_ages.max()) + 1 if not loan_ages.empty else age_now

    # 資産ピーク
    peak_idx = df["assets"].idxmax()
    peak_age = int(df.loc[peak_idx, "age"])
    peak_assets = df.loc[peak_idx, "assets"]

    # 老後資金枯渇判定
    depleted = df[df["assets"] < 0]
    if depleted.empty:
        depletion_age = None
        depletion_label = "✅ 安全（資産はプラスを維持）"
    else:
        depletion_age = int(depleted.iloc[0]["age"])
        depletion_label = f"⚠️ {depletion_age}歳で資産枯渇"

    # 死亡時資産残高
    final_assets = float(df.iloc[-1]["assets"])

    # FIRE 達成年齢（投資収益 ≥ 生活費）
    fire_df = df[df["invest_gain"] >= df["expense"]]
    fire_age = int(fire_df.iloc[0]["age"]) if not fire_df.empty else None

    return {
        "payoff_age": payoff_age,
        "peak_age": peak_age,
        "peak_assets_man": peak_assets / 10000,
        "depletion_age": depletion_age,
        "depletion_label": depletion_label,
        "final_assets_man": final_assets / 10000,
        "fire_age": fire_age,
    }
