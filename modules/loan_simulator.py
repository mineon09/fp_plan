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
    """
    rows = []
    for bank in banks:
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

            has_dan = bank.get("has_team_dan", True)
            effective_rate = rate + (dan_sin_rate_pct if has_dan else 0.0)

            rows.append({
                "銀行名": bank["bank_name"],
                "金利種別": rate_type,
                "金利(%)": rate,
                "実効金利(%)": round(effective_rate, 3),
                "月額返済(円)": round(m_payment),
                "総返済額(円)": round(total_payment),
                "総利息(円)": round(total_interest),
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        # 月額最安値フラグ
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
