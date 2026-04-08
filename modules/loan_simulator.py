"""
Module 2: 住宅ローン計算エンジン
- 元利均等計算
- 月次残高推移
- 金利上昇シナリオ
- ブレークイーブン金利（Phase 2 で使用）
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import brentq


# ---------------------------------------------------------------------------
# コア計算
# ---------------------------------------------------------------------------

def monthly_payment(principal: float, annual_rate_pct: float, years: int) -> float:
    """
    元利均等月額返済額
    M = P × r(1+r)^n / ((1+r)^n - 1)
    principal: 借入元本（円）
    annual_rate_pct: 年利率（%）
    years: 返済期間（年）
    """
    if annual_rate_pct <= 0:
        return principal / (years * 12)
    r = annual_rate_pct / 100 / 12
    n = years * 12
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def amortization_schedule(
    principal: float,
    annual_rate_pct: float,
    years: int,
    bonus_ratio: float = 0.0,
) -> pd.DataFrame:
    """
    月次返済スケジュール生成
    Returns DataFrame with columns:
        month, payment, interest, principal_repaid, balance
    bonus_ratio: ボーナス返済割合（0〜0.4）
    """
    regular_principal = principal * (1 - bonus_ratio)
    bonus_principal = principal * bonus_ratio

    r = annual_rate_pct / 100 / 12
    n = years * 12

    regular_payment = monthly_payment(regular_principal, annual_rate_pct, years)
    # ボーナス返済は年2回（6・12月）に均等分割
    bonus_payment = (
        monthly_payment(bonus_principal, annual_rate_pct, years) * 6
        if bonus_ratio > 0
        else 0.0
    )

    rows = []
    balance = principal
    reg_balance = regular_principal
    bon_balance = bonus_principal

    for month in range(1, n + 1):
        # 通常返済
        int_reg = reg_balance * r
        prin_reg = regular_payment - int_reg
        reg_balance = max(reg_balance - prin_reg, 0)

        # ボーナス返済（6・12月）
        int_bon = 0.0
        prin_bon = 0.0
        if bonus_ratio > 0 and month % 6 == 0:
            int_bon = bon_balance * r
            prin_bon = bonus_payment - int_bon
            bon_balance = max(bon_balance - prin_bon, 0)

        total_payment = regular_payment + (bonus_payment if month % 6 == 0 and bonus_ratio > 0 else 0)
        total_interest = int_reg + int_bon
        total_principal = prin_reg + prin_bon
        balance = reg_balance + bon_balance

        rows.append({
            "month": month,
            "payment": total_payment,
            "interest": total_interest,
            "principal_repaid": total_principal,
            "balance": max(balance, 0),
        })

    return pd.DataFrame(rows)


def scenario_schedule(
    principal: float,
    initial_rate_pct: float,
    years: int,
    rate_hike_pct: float = 0.0,
    hike_start_year: int = 5,
) -> pd.DataFrame:
    """
    金利上昇シナリオの月次スケジュール。
    hike_start_year 年目から rate_hike_pct % 上昇（線形）したと仮定して
    残高ベースで毎年再計算。
    """
    balance = principal
    rows = []
    month_global = 0
    remaining_months = years * 12

    for year in range(1, years + 1):
        elapsed_years = year - 1
        if elapsed_years < hike_start_year:
            current_rate = initial_rate_pct
        else:
            # 線形上昇
            progress = (elapsed_years - hike_start_year) / max(years - hike_start_year, 1)
            current_rate = initial_rate_pct + rate_hike_pct * progress

        r = current_rate / 100 / 12
        months_left = remaining_months

        for m in range(12):
            if remaining_months <= 0 or balance <= 0:
                break
            if r > 0:
                payment = balance * r * (1 + r) ** remaining_months / ((1 + r) ** remaining_months - 1)
            else:
                payment = balance / remaining_months

            interest = balance * r
            principal_repaid = payment - interest
            balance = max(balance - principal_repaid, 0)
            remaining_months -= 1
            month_global += 1

            rows.append({
                "month": month_global,
                "year": year,
                "rate_pct": current_rate,
                "payment": payment,
                "interest": interest,
                "principal_repaid": principal_repaid,
                "balance": balance,
            })

        if balance <= 0:
            break

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 比較サマリー
# ---------------------------------------------------------------------------

def compare_banks(
    banks: list[dict],
    principal: float,
    years: int,
    bonus_ratio: float = 0.0,
    dan_sin_rate_pct: float = 0.25,
) -> pd.DataFrame:
    """
    複数銀行のローン比較サマリー DataFrame を返す。
    dan_sin_rate_pct: 団信保険料の実効金利への加算（%）
    変動35年・固定35年に加え、fixed_3 / fixed_5 がある場合は当初固定型も追加。
    """
    rows = []
    for bank in banks:
        has_dan = bank.get("has_team_dan", True)
        dan_add = dan_sin_rate_pct if has_dan else 0.0

        # --- 変動35年 / 固定35年 ---
        for rate_type, rate_key in [("変動35年", "variable_35"), ("固定35年", "fixed_35")]:
            rate = bank.get(rate_key)
            if rate is None:
                continue
            try:
                rate = float(rate)
            except (TypeError, ValueError):
                continue

            df = amortization_schedule(principal, rate, years, bonus_ratio)
            total_payment = df["payment"].sum()
            total_interest = df["interest"].sum()
            m_payment = df.loc[0, "payment"]

            rows.append({
                "銀行名": bank["bank_name"],
                "金利種別": rate_type,
                "金利(%)": rate,
                "実効金利(%)": round(rate + dan_add, 3),
                "月額返済(円)": round(m_payment),
                "総返済額(円)": round(total_payment),
                "総利息(円)": round(total_interest),
            })

        # --- 当初固定型（fixed_3 / fixed_5）+ 変動35年への切替 ---
        var_rate = bank.get("variable_35")
        for fixed_n, fixed_key in [(3, "fixed_3"), (5, "fixed_5")]:
            fixed_n_rate = bank.get(fixed_key)
            if fixed_n_rate is None or var_rate is None:
                continue
            try:
                fixed_n_rate = float(fixed_n_rate)
                var = float(var_rate)
            except (TypeError, ValueError):
                continue

            df = hybrid_schedule(principal, fixed_n_rate, var, years, fixed_n, bonus_ratio)
            total_payment = df["payment"].sum()
            total_interest = df["interest"].sum()
            m_payment = df.loc[0, "payment"]
            avg_rate = (fixed_n_rate * fixed_n + var * (years - fixed_n)) / years

            rows.append({
                "銀行名": bank["bank_name"],
                "金利種別": f"当初{fixed_n}年固定",
                "金利(%)": fixed_n_rate,
                "実効金利(%)": round(avg_rate + dan_add, 3),
                "月額返済(円)": round(m_payment),
                "総返済額(円)": round(total_payment),
                "総利息(円)": round(total_interest),
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["最安値"] = df["月額返済(円)"] == df["月額返済(円)"].min()
    return df


# ---------------------------------------------------------------------------
# ブレークイーブン金利（Phase 2 で UI から呼ばれる）
# ---------------------------------------------------------------------------

def breakeven_variable_rate(
    principal: float,
    years: int,
    fixed_rate_pct: float,
    initial_variable_pct: float,
    bonus_ratio: float = 0.0,
) -> float | None:
    """
    変動金利の平均が何 % になると固定と同等の総返済額になるかを返す。
    SciPy brentq で数値解。
    """
    fixed_total = amortization_schedule(principal, fixed_rate_pct, years, bonus_ratio)["payment"].sum()

    def diff(avg_rate):
        df = amortization_schedule(principal, avg_rate, years, bonus_ratio)
        return df["payment"].sum() - fixed_total

    try:
        return brentq(diff, 0.01, fixed_rate_pct * 3, xtol=1e-5)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 当初固定型ローン（固定N年 → 変動）
# ---------------------------------------------------------------------------

def hybrid_schedule(
    principal: float,
    fixed_rate_pct: float,
    variable_rate_pct: float,
    years: int,
    fixed_years: int,
    bonus_ratio: float = 0.0,
) -> pd.DataFrame:
    """
    当初固定型ローンのスケジュール計算。
    最初の fixed_years は fixed_rate_pct、以降は variable_rate_pct を適用。
    """
    phase1 = amortization_schedule(principal, fixed_rate_pct, years, bonus_ratio)
    phase1_rows = phase1[phase1["month"] <= fixed_years * 12].copy()

    if phase1_rows.empty:
        return amortization_schedule(principal, variable_rate_pct, years, bonus_ratio)

    balance_after_fixed = float(phase1_rows.iloc[-1]["balance"])
    remaining_years = years - fixed_years

    if remaining_years <= 0 or balance_after_fixed <= 0:
        return phase1_rows

    phase2 = amortization_schedule(balance_after_fixed, variable_rate_pct, remaining_years, bonus_ratio)
    phase2 = phase2.copy()
    phase2["month"] += fixed_years * 12

    return pd.concat([phase1_rows, phase2], ignore_index=True)


# ---------------------------------------------------------------------------
# 5年ルール・125%ルール 変動金利シミュレーション
# ---------------------------------------------------------------------------

def variable_rate_5yr(
    principal: float,
    initial_rate_pct: float,
    years: int,
    rate_hike_total_pct: float = 0.0,
    hike_start_year: int = 5,
) -> pd.DataFrame:
    """
    5年ルール・125%ルールに基づく変動金利返済シミュレーション。

    5年ルール  : 月額は 5 年ごとにのみ見直す（金利変動の影響は即時反映されない）
    125%ルール : 見直し時も前回月額の 125% を上限とする

    Returns DataFrame columns:
        month, year, rate_pct, payment, interest, principal_repaid,
        balance, unpaid_interest, unpaid_interest_cumulative
    """
    r0 = initial_rate_pct / 100 / 12
    n_total = years * 12

    if r0 > 0:
        payment_current = principal * r0 * (1 + r0) ** n_total / ((1 + r0) ** n_total - 1)
    else:
        payment_current = principal / n_total

    balance = principal
    unpaid_cum = 0.0
    rows = []

    for month in range(1, n_total + 1):
        year = (month - 1) // 12 + 1
        elapsed_years = year - 1

        # 現在の金利（線形上昇モデル）
        if elapsed_years < hike_start_year:
            current_rate_pct = initial_rate_pct
        else:
            progress = min(
                (elapsed_years - hike_start_year) / max(years - hike_start_year, 1),
                1.0,
            )
            current_rate_pct = initial_rate_pct + rate_hike_total_pct * progress

        r = current_rate_pct / 100 / 12

        # 5 年ごとに月額見直し（month=1 は除く）
        if month > 1 and (month - 1) % 60 == 0 and balance > 0:
            remaining = n_total - month + 1
            if r > 0:
                new_payment = balance * r * (1 + r) ** remaining / ((1 + r) ** remaining - 1)
            else:
                new_payment = balance / remaining
            payment_current = min(new_payment, payment_current * 1.25)

        interest = balance * r

        if payment_current <= interest:
            # 元本が減らない（逆アモチ）→ 未払い利息が蓄積
            unpaid = interest - payment_current
            unpaid_cum += unpaid
            principal_repaid = 0.0
        else:
            unpaid = 0.0
            principal_repaid = payment_current - interest

        balance = max(balance - principal_repaid, 0.0)

        rows.append({
            "month": month,
            "year": year,
            "rate_pct": round(current_rate_pct, 4),
            "payment": payment_current,
            "interest": interest,
            "principal_repaid": principal_repaid,
            "balance": balance,
            "unpaid_interest": unpaid,
            "unpaid_interest_cumulative": unpaid_cum,
        })

        if balance <= 0 and unpaid_cum <= 0:
            break

    return pd.DataFrame(rows)
