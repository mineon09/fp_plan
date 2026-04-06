"""
Module 4: 人生設計キャッシュフロー計算エンジン
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from config import LIFE_DEFAULTS, SCENARIOS


def calc_life_cashflow(
    profile: dict,
    loan_schedule: pd.DataFrame | None,
    life_events: list[dict],
) -> pd.DataFrame:
    """
    生涯キャッシュフロー年次計算。

    profile keys (万円/年 / 割合): 全て LIFE_DEFAULTS 参照。
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

        # 収入
        if age < p["retire_age"]:
            income = (
                p["income_man"] * 10000 * (1 + p["income_growth_rate"]) ** years_elapsed
                + p["income_spouse_man"] * 10000
            )
        elif age == p["retire_age"]:
            income = p["severance_pay_man"] * 10000
        else:
            income = 0.0

        # 年金
        if age >= p["pension_start_age"]:
            income += p["pension_monthly_man"] * 10000 * 12

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
