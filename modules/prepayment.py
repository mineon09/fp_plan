"""
Module 3: 繰り上げ返済・借り換えシミュレーター
"""

from __future__ import annotations

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# 繰り上げ返済
# ---------------------------------------------------------------------------

def prepayment_schedule(
    principal: float,
    annual_rate_pct: float,
    years: int,
    prepayments: list[dict],
    mode: str = "short",
) -> pd.DataFrame:
    """
    繰り上げ返済スケジュール計算。
    prepayments: [{"month": int, "amount": float}, ...]
    mode: "short" = 返済期間短縮型, "reduce" = 月額減額型
    Returns DataFrame: month, payment, interest, principal_repaid, balance, prepayment
    """
    prepay_map = {p["month"]: p["amount"] for p in prepayments}
    r = annual_rate_pct / 100 / 12
    balance = principal
    remaining = years * 12
    rows = []

    for month in range(1, years * 12 + 1):
        if balance <= 0:
            break

        # 通常返済
        if r > 0:
            payment = balance * r * (1 + r) ** remaining / ((1 + r) ** remaining - 1)
        else:
            payment = balance / remaining

        interest = balance * r
        principal_repaid = payment - interest
        balance = max(balance - principal_repaid, 0)
        remaining -= 1

        # 繰り上げ返済
        prepay = prepay_map.get(month, 0.0)
        if prepay > 0 and balance > 0:
            prepay = min(prepay, balance)
            balance -= prepay
            if mode == "short":
                # 月額固定・期間短縮（remainingを再計算）
                if balance > 0 and r > 0:
                    remaining = int(np.ceil(
                        -np.log(1 - balance * r / payment) / np.log(1 + r)
                    ))
                elif balance > 0:
                    remaining = int(np.ceil(balance / payment))
                else:
                    remaining = 0
            # reduce モードは次月から payment が自動再計算される（remaining は変えない）

        rows.append({
            "month": month,
            "payment": payment,
            "interest": interest,
            "principal_repaid": principal_repaid,
            "balance": max(balance, 0),
            "prepayment": prepay,
        })

        if balance <= 0:
            break

    return pd.DataFrame(rows)


def prepayment_effect(
    principal: float,
    annual_rate_pct: float,
    years: int,
    prepayments: list[dict],
    mode: str = "short",
) -> dict:
    """
    繰り上げあり vs なし の比較サマリー。
    """
    from modules.loan_simulator import amortization_schedule

    base_df = amortization_schedule(principal, annual_rate_pct, years)
    prep_df = prepayment_schedule(principal, annual_rate_pct, years, prepayments, mode)

    base_total = base_df["payment"].sum()
    prep_total = prep_df["payment"].sum() + prep_df["prepayment"].sum()
    base_interest = base_df["interest"].sum()
    prep_interest = prep_df["interest"].sum()

    base_months = len(base_df[base_df["balance"] > 0]) + 1
    prep_months = len(prep_df)

    return {
        "base_total": base_total,
        "prep_total": prep_total,
        "savings": base_total - prep_total,
        "interest_savings": base_interest - prep_interest,
        "base_months": base_months,
        "prep_months": prep_months,
        "months_saved": base_months - prep_months,
        "base_df": base_df,
        "prep_df": prep_df,
    }


# ---------------------------------------------------------------------------
# 繰り上げ返済 vs 投資 比較
# ---------------------------------------------------------------------------

def prepay_vs_invest(
    prepay_amount: float,
    prepay_month: int,
    loan_rate_pct: float,
    invest_return_annual: float,
    tax_rate: float,
    horizon_months: int,
) -> dict:
    """
    繰り上げ返済に充てた場合 vs 投資に回した場合の資産差比較。
    """
    # 繰り上げ返済の効果 = 節約できる利息（= 確定利回り）
    monthly_loan_rate = loan_rate_pct / 100 / 12
    interest_saved = prepay_amount * monthly_loan_rate * horizon_months  # 簡易近似

    # 投資の効果
    monthly_invest_rate = invest_return_annual / 12
    invest_value = prepay_amount * (1 + monthly_invest_rate) ** horizon_months
    invest_gain = invest_value - prepay_amount
    invest_gain_after_tax = invest_gain * (1 - tax_rate)
    invest_net = prepay_amount + invest_gain_after_tax

    return {
        "prepay_amount": prepay_amount,
        "interest_saved": interest_saved,
        "invest_final_value": invest_net,
        "invest_gain_after_tax": invest_gain_after_tax,
        "diff": invest_net - (prepay_amount + interest_saved),
        "invest_wins": invest_net > prepay_amount + interest_saved,
    }


# ---------------------------------------------------------------------------
# 借り換えシミュレーター
# ---------------------------------------------------------------------------

def refinance_simulation(
    current_balance: float,
    current_rate_pct: float,
    remaining_months: int,
    new_rate_pct: float,
    refinance_cost: float,
) -> dict:
    """
    借り換え効果計算。
    Returns:
        breakeven_months: 元が取れるまでの月数
        total_savings: 総節約額
        recommend: 推奨判定文字列
    """
    r_old = current_rate_pct / 100 / 12
    r_new = new_rate_pct / 100 / 12

    if r_old > 0:
        old_payment = (
            current_balance * r_old * (1 + r_old) ** remaining_months
            / ((1 + r_old) ** remaining_months - 1)
        )
    else:
        old_payment = current_balance / remaining_months

    if r_new > 0:
        new_payment = (
            current_balance * r_new * (1 + r_new) ** remaining_months
            / ((1 + r_new) ** remaining_months - 1)
        )
    else:
        new_payment = current_balance / remaining_months

    monthly_saving = old_payment - new_payment
    if monthly_saving <= 0:
        return {
            "monthly_saving": monthly_saving,
            "breakeven_months": None,
            "total_savings": (old_payment - new_payment) * remaining_months,
            "recommend": "❌ 借り換えメリットなし（月額が増加します）",
        }

    breakeven_months = int(np.ceil(refinance_cost / monthly_saving))
    total_savings = monthly_saving * remaining_months - refinance_cost

    if breakeven_months > remaining_months:
        recommend = f"⚠️ 残存期間内（{remaining_months}ヶ月）に元が取れません（{breakeven_months}ヶ月必要）"
    elif breakeven_months <= 24:
        recommend = f"✅ 強く推奨（{breakeven_months}ヶ月で元が取れます）"
    else:
        recommend = f"🔶 検討余地あり（{breakeven_months}ヶ月で元が取れます）"

    return {
        "monthly_saving": monthly_saving,
        "breakeven_months": breakeven_months,
        "total_savings": total_savings,
        "recommend": recommend,
    }
