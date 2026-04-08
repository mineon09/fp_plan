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
    variable_rate_5yr,
)
from modules.tax_calc import calc_loan_deduction, total_loan_deduction


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

        st.subheader("🏠 住宅ローン控除条件")
        age_at_purchase = st.number_input("購入時年齢", 20, 65, 35, key="loan_purchase_age")
        income_man_ded = st.number_input("年収（万円）", 100, 5000, 600, 50, key="loan_income_ded")
        deduction_years = st.radio("控除期間", [13, 10], horizontal=True,
                                   help="新築・長期優良=13年、一般中古=10年")

        st.subheader("📈 金利上昇シナリオ")
        selected_scenarios = st.multiselect(
            "表示するシナリオ",
            options=list(RATE_SCENARIOS.keys()),
            default=list(RATE_SCENARIOS.keys()),
        )
        hike_start_year = st.slider("金利上昇開始（年後）", 1, 15, 5)
        use_5yr_rule = st.checkbox("5年ルール・125%ルール適用", value=False,
                                   help="日本の変動ローン特有の月額更新ルールを適用します")

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

    # 住宅ローン控除列を追加
    deduction_totals = []
    for _, row in summary_df.iterrows():
        rate = float(row["金利(%)"])
        d = total_loan_deduction(
            principal, rate, period_years, income_man_ded,
            deduction_years=deduction_years,
        )
        deduction_totals.append(round(d, 1))
    summary_df[f"{deduction_years}年控除合計(万)"] = deduction_totals
    total_cost_man = (summary_df["総返済額(円)"] / 10000).round(1)
    summary_df["控除後実質コスト(万)"] = (total_cost_man - summary_df[f"{deduction_years}年控除合計(万)"]).round(1)

    def highlight_min(s):
        is_min = s == s.min()
        return ["background-color: #d4edda" if v else "" for v in is_min]

    display_cols = ["銀行名", "金利種別", "金利(%)", "実効金利(%)",
                    "月額返済(円)", "総返済額(円)", "総利息(円)",
                    f"{deduction_years}年控除合計(万)", "控除後実質コスト(万)"]
    styled = (
        summary_df[display_cols]
        .style.apply(highlight_min, subset=["月額返済(円)"])
        .apply(highlight_min, subset=["控除後実質コスト(万)"])
        .format({
            "金利(%)": "{:.2f}", "実効金利(%)": "{:.3f}",
            "月額返済(円)": "{:,.0f}", "総返済額(円)": "{:,.0f}", "総利息(円)": "{:,.0f}",
            f"{deduction_years}年控除合計(万)": "{:.1f}", "控除後実質コスト(万)": "{:.1f}",
        })
    )
    st.dataframe(styled, use_container_width=True)
    st.caption(f"💡 控除計算条件: 年収 {income_man_ded} 万円・購入時年齢 {age_at_purchase} 歳・控除期間 {deduction_years} 年")

    # ---------- 住宅ローン控除詳細 ----------
    with st.expander(f"📄 住宅ローン控除明細（{deduction_years}年間）"):
        if selected_banks:
            ref_bank = selected_banks[0]
            ref_rate = ref_bank.get("variable_35") or ref_bank.get("fixed_35")
            if ref_rate:
                ded_df = calc_loan_deduction(
                    principal, float(ref_rate), period_years,
                    age_at_purchase, income_man_ded,
                    deduction_years=deduction_years,
                )
                st.caption(f"{ref_bank['bank_name']} 変動金利（{ref_rate}%）ベース")
                st.dataframe(
                    ded_df.rename(columns={
                        "age": "年齢", "year": "控除年目",
                        "year_end_balance_man": "年末残高(万)",
                        "deduction_amount_man": "控除可能額(万)",
                        "income_tax_man": "概算所得税(万)",
                        "income_tax_offset_man": "所得税控除(万)",
                        "resident_tax_offset_man": "住民税控除(万)",
                        "net_deduction_man": "実質還付額(万)",
                    }),
                    use_container_width=True,
                )

    # ---------- ブレークイーブン分析 ----------
    st.subheader("⚖️ 変動 vs 固定 ブレークイーブン分析")
    _render_breakeven(selected_banks, principal, period_years, bonus_ratio)

    # ---------- シナリオグラフ ----------
    st.subheader("📈 金利上昇シナリオグラフ（累計返済額）")
    _render_scenario_graph(selected_banks, principal, period_years, bonus_ratio,
                           selected_scenarios, hike_start_year, use_5yr_rule)


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


def _render_scenario_graph(banks, principal, years, bonus_ratio, selected_scenarios, hike_start_year, use_5yr_rule=False):
    if use_5yr_rule:
        st.info("🔔 5年ルール・125%ルール適用中：月額は5年毎にのみ更新され、前回月額の125%が上限になります。")
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
            if use_5yr_rule:
                df = variable_rate_5yr(principal, var_rate, years, hike, hike_start_year)
            else:
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

    # 5年ルール適用時: 未払い利息グラフ
    if use_5yr_rule:
        st.subheader("⚠️ 未払い利息累積グラフ（5年ルール）")
        st.caption("月額が利息を下回ると発生する「逆アモチ」リスクを可視化します。")
        fig_unpaid = go.Figure()
        has_unpaid = False
        for bank in banks[:3]:
            var_rate = bank.get("variable_35")
            if var_rate is None:
                continue
            try:
                var_rate = float(var_rate)
            except (TypeError, ValueError):
                continue
            for scenario_name in selected_scenarios:
                hike = RATE_SCENARIOS[scenario_name]
                df = variable_rate_5yr(principal, var_rate, years, hike, hike_start_year)
                if df["unpaid_interest_cumulative"].max() > 0:
                    has_unpaid = True
                    fig_unpaid.add_trace(go.Scatter(
                        x=df["month"] / 12,
                        y=df["unpaid_interest_cumulative"] / 10000,
                        mode="lines",
                        name=f"{bank['bank_name']} {scenario_name}",
                        fill="tozeroy",
                    ))
        if has_unpaid:
            fig_unpaid.update_layout(
                xaxis_title="経過年数",
                yaxis_title="未払い利息累計（万円）",
                height=350,
            )
            st.plotly_chart(fig_unpaid, use_container_width=True)
        else:
            st.success("✅ 選択中の全シナリオで未払い利息は発生しません。")

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
