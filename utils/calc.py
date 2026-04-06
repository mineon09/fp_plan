"""
共通計算ユーティリティ (NPV, IRR 等)
"""

import numpy as np


def npv(rate: float, cashflows: list[float]) -> float:
    """正味現在価値 (rate: 期間利率)"""
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows))


def irr(cashflows: list[float], guess: float = 0.1, tol: float = 1e-6, max_iter: int = 1000) -> float | None:
    """内部収益率（ニュートン法）。解なしの場合は None"""
    rate = guess
    for _ in range(max_iter):
        f = npv(rate, cashflows)
        df = sum(-t * cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cashflows))
        if abs(df) < 1e-12:
            return None
        rate_new = rate - f / df
        if abs(rate_new - rate) < tol:
            return rate_new
        rate = rate_new
    return None


def compound(principal: float, annual_rate: float, years: int) -> float:
    """複利終価"""
    return principal * (1 + annual_rate) ** years
