"""
住宅ローン控除計算モジュール。

- 年末残高 × 0.7%（新築: 13年、中古: 10年）
- 所得税から控除 → 残余分を住民税から控除（上限 9.75 万円/年）
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# 所得税 簡易推計（給与所得者）
# ---------------------------------------------------------------------------
# 累進税率テーブル: (課税所得上限万円, 税率, 控除額万円)
_TAX_BRACKETS = [
    (195,          0.05,   0.00),
    (330,          0.10,   9.75),
    (695,          0.20,  42.75),
    (900,          0.23,  63.60),
    (1800,         0.33, 153.60),
    (4000,         0.40, 279.60),
    (float("inf"), 0.45, 479.60),
]


def _income_tax_estimate(income_gross_man: float) -> float:
    """給与所得者の概算所得税（万円/年）。復興特別所得税 2.1% 含む。"""
    g = income_gross_man

    # 給与所得控除（2023 年度）
    if g <= 162.5:
        deduction = 55.0
    elif g <= 180:
        deduction = g * 0.4 - 10.0
    elif g <= 360:
        deduction = g * 0.3 + 8.0
    elif g <= 660:
        deduction = g * 0.2 + 44.0
    elif g <= 850:
        deduction = g * 0.1 + 110.0
    else:
        deduction = 195.0

    employment_income = max(g - deduction, 0.0)
    social_ins = g * 0.15          # 社会保険料控除（概算）
    taxable = max(employment_income - 48.0 - social_ins, 0.0)

    tax = 0.0
    for threshold, rate, deduct in _TAX_BRACKETS:
        if taxable <= threshold:
            tax = taxable * rate - deduct
            break

    return max(tax, 0.0) * 1.021   # 復興特別所得税


# ---------------------------------------------------------------------------
# 住宅ローン控除計算
# ---------------------------------------------------------------------------

def calc_loan_deduction(
    principal: float,
    annual_rate_pct: float,
    years: int,
    age_at_purchase: int,
    income_man: float,
    deduction_years: int = 13,
    max_balance_man: float = 3000.0,
    residential_tax_cap_man: float = 9.75,
) -> pd.DataFrame:
    """
    住宅ローン控除の年次シミュレーション。

    Parameters
    ----------
    principal               借入元本（円）
    annual_rate_pct         金利（%）
    years                   借入期間（年）
    age_at_purchase         購入時年齢（表示用）
    income_man              年収（万円、控除期間中固定近似）
    deduction_years         控除期間（新築=13、中古=10）
    max_balance_man         控除対象上限残高（万円。2022〜新築省エネ住宅: 3000万）
    residential_tax_cap_man 住民税控除年額上限（万円/年）

    Returns
    -------
    DataFrame columns:
        age, year, year_end_balance_man,
        deduction_amount_man, income_tax_man,
        income_tax_offset_man, resident_tax_offset_man, net_deduction_man
    """
    from .loan_simulator import amortization_schedule

    df_loan = amortization_schedule(principal, annual_rate_pct, years)
    df_loan["year"] = (df_loan["month"] - 1) // 12 + 1
    year_end_bal = df_loan.groupby("year")["balance"].last().reset_index()

    income_tax = _income_tax_estimate(income_man)   # 年間所得税（控除期間中固定近似）

    rows = []
    for _, row in year_end_bal.iterrows():
        yr = int(row["year"])
        if yr > deduction_years:
            break

        eff_balance_man = min(row["balance"] / 10000, max_balance_man)
        deduction_man = eff_balance_man * 0.007             # 0.7%

        it_offset = min(deduction_man, income_tax)
        remaining = deduction_man - it_offset
        rt_offset = min(remaining, residential_tax_cap_man)
        net = it_offset + rt_offset

        rows.append({
            "age":                    age_at_purchase + yr - 1,
            "year":                   yr,
            "year_end_balance_man":   round(row["balance"] / 10000, 1),
            "deduction_amount_man":   round(deduction_man, 2),
            "income_tax_man":         round(income_tax, 2),
            "income_tax_offset_man":  round(it_offset, 2),
            "resident_tax_offset_man": round(rt_offset, 2),
            "net_deduction_man":      round(net, 2),
        })

    return pd.DataFrame(rows)


def total_loan_deduction(
    principal: float,
    annual_rate_pct: float,
    years: int,
    income_man: float,
    deduction_years: int = 13,
    max_balance_man: float = 3000.0,
    residential_tax_cap_man: float = 9.75,
) -> float:
    """控除期間内の実質控除合計額（万円）。比較テーブル用。"""
    df = calc_loan_deduction(
        principal, annual_rate_pct, years,
        age_at_purchase=0,
        income_man=income_man,
        deduction_years=deduction_years,
        max_balance_man=max_balance_man,
        residential_tax_cap_man=residential_tax_cap_man,
    )
    if df.empty:
        return 0.0
    return float(df["net_deduction_man"].sum())
