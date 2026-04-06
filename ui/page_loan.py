"""
Module 2 UI: 住宅ローン比較・シミュレーションページ
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import LOAN_DEFAULTS, RATE_SCENARIOS
from modules.loan_simulator import (
    amortization_schedule,
    breakeven_variable_rate,
    compare_banks,
    scenario_schedule,
)


def render():
    st.header("📊 住宅ローン比較・シミュレーション")

    banks = st.session_state.get("bank_data", [])
    if not banks:
        st.info("先に「🏦 銀行金利取得」タブで銀行データを読み込んでください。")
        return

    # ---------- 入力パラメータ（サイドバー） ----------
    with st.sidebar:
        st.subheader("🔧 ローン条件")
        amount_man = st.slider("借入金額（万円）", 500, 10000, LOAN_DEFAULTS["amount_man"], step=100)
        period_years = st.selectbox("借入期間（年）", list(range(10, 36)), index=25)
        down_man = st.number_input("頭金（万円）", min_value=0, value=LOAN_DEFAULTS["down_payment_man"], step=100)
        bonus_ratio = st.slider("ボーナス返済割合 (%)", 0, 40, 0) / 100

        st.subheader("📈 金利上昇シナリオ")
        selected_scenarios = st.multiselect(
            "表示するシナリオ",
            options=list(RATE_SCENARIOS.keys()),
            default=list(RATE_SCENARIOS.keys()),
        )
        hike_start_year = st.slider("金利上昇開始（年後）", 1, 15, 5)

        st.subheader("🏦 対象銀行")
        bank_names = [b["bank_name"] for b in banks]
        selected_banks_names = st.multiselect("比較する銀行", bank_names, default=bank_names)

    principal = (amount_man - down_man) * 10000
    selected_banks = [b for b in banks if b["bank_name"] in selected_banks_names]

    if not selected_banks:
        st.warning("銀行を1行以上選択してください。")
        return

    # ---------- 比較テーブル ----------
    st.subheader("📋 銀行横断比較テーブル")
    summary_df = compare_banks(selected_banks, principal, period_years, bonus_ratio)
    if summary_df.empty:
        st.warning("表示できるデータがありません。")
        return

    def highlight_min(s):
        is_min = s == s.min()
        return ["background-color: #d4edda" if v else "" for v in is_min]

    styled = (
        summary_df.drop(columns=["最安値"])
        .style.apply(highlight_min, subset=["月額返済(円)"])
        .format({"金利(%)": "{:.2f}", "実効金利(%)": "{:.3f}",
                 "月額返済(円)": "{:,.0f}", "総返済額(円)": "{:,.0f}", "総利息(円)": "{:,.0f}"})
    )
    st.dataframe(styled, use_container_width=True)

    # ---------- ブレークイーブン分析 ----------
    st.subheader("⚖️ 変動 vs 固定 ブレークイーブン分析")
    _render_breakeven(selected_banks, principal, period_years, bonus_ratio)

    # ---------- シナリオグラフ ----------
    st.subheader("📈 金利上昇シナリオグラフ（累計返済額）")
    _render_scenario_graph(selected_banks, principal, period_years, bonus_ratio,
                           selected_scenarios, hike_start_year)


def _render_breakeven(banks, principal, years, bonus_ratio):
    rows = []
    for bank in banks:
        var_rate = bank.get("variable_35")
        fix_rate = bank.get("fixed_35")
        if var_rate is None or fix_rate is None:
            continue
        try:
            var_rate = float(var_rate)
            fix_rate = float(fix_rate)
        except (TypeError, ValueError):
            continue

        be = breakeven_variable_rate(principal, years, fix_rate, var_rate, bonus_ratio)
        rows.append({
            "銀行名": bank["bank_name"],
            "変動金利(%)": var_rate,
            "固定金利(%)": fix_rate,
            "損益分岐金利(%)": round(be, 3) if be else "計算不能",
            "判定": (
                f"変動が平均 {be:.2f}% を超えると固定が有利" if be else "—"
            ),
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("変動・固定の両金利が揃っている銀行がありません。")


def _render_scenario_graph(banks, principal, years, bonus_ratio, selected_scenarios, hike_start_year):
    fig = go.Figure()

    for bank in banks[:3]:  # 見やすさのため最大3行
        var_rate = bank.get("variable_35")
        if var_rate is None:
            continue
        try:
            var_rate = float(var_rate)
        except (TypeError, ValueError):
            continue

        for scenario_name in selected_scenarios:
            hike = RATE_SCENARIOS[scenario_name]
            df = scenario_schedule(principal, var_rate, years, hike, hike_start_year)
            df["cumulative_payment"] = df["payment"].cumsum() / 10000  # 万円

            fig.add_trace(go.Scatter(
                x=df["month"] / 12,
                y=df["cumulative_payment"],
                mode="lines",
                name=f"{bank['bank_name']} {scenario_name}",
            ))

        # 固定金利の水平線（総返済額）
        fix_rate = bank.get("fixed_35")
        if fix_rate is not None:
            try:
                fix_df = amortization_schedule(principal, float(fix_rate), years, bonus_ratio)
                fix_total = fix_df["payment"].sum() / 10000
                fig.add_hline(
                    y=fix_total,
                    line_dash="dash",
                    annotation_text=f"{bank['bank_name']} 固定総返済 {fix_total:,.0f}万円",
                    annotation_position="bottom right",
                )
            except (TypeError, ValueError):
                pass

    fig.update_layout(
        xaxis_title="経過年数",
        yaxis_title="累計返済額（万円）",
        legend_title="銀行 × シナリオ",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)

    # 残高推移グラフ
    st.subheader("💰 残高推移グラフ")
    fig2 = go.Figure()
    for bank in banks[:3]:
        var_rate = bank.get("variable_35")
        if var_rate is None:
            continue
        try:
            df = amortization_schedule(principal, float(var_rate), years, bonus_ratio)
            fig2.add_trace(go.Scatter(
                x=df["month"] / 12,
                y=df["balance"] / 10000,
                mode="lines",
                name=bank["bank_name"],
            ))
        except (TypeError, ValueError):
            pass

    fig2.update_layout(
        xaxis_title="経過年数",
        yaxis_title="残高（万円）",
        height=400,
    )
    st.plotly_chart(fig2, use_container_width=True)
