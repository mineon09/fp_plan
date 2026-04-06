"""
Module 3 UI: 繰り上げ返済・借り換えシミュレーターページ
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import LOAN_DEFAULTS
from modules.loan_simulator import amortization_schedule
from modules.prepayment import (
    prepayment_effect,
    prepay_vs_invest,
    refinance_simulation,
)


def render():
    st.header("⚡ 繰り上げ返済・借り換えシミュレーター")

    # ローン情報をセッションから取得、なければサイドバー入力
    with st.sidebar:
        st.subheader("🔧 ローン条件（基本）")
        amount_man = st.slider("借入金額（万円）", 500, 10000, LOAN_DEFAULTS["amount_man"], step=100, key="prep_amount")
        period_years = st.selectbox("借入期間（年）", list(range(10, 36)), index=25, key="prep_period")
        annual_rate = st.number_input("現行金利（%）", min_value=0.1, max_value=8.0, value=0.32, step=0.01, format="%.2f", key="prep_rate")

    principal = amount_man * 10000

    tab1, tab2, tab3 = st.tabs(["⚡ 繰り上げ返済", "📊 繰り上げ vs 投資", "🔄 借り換え"])

    # ==================== Tab 1: 繰り上げ返済 ====================
    with tab1:
        st.subheader("繰り上げ返済シミュレーション")

        mode = st.radio("繰り上げ方式", ["返済期間短縮型 (short)", "月額減額型 (reduce)"], horizontal=True)
        mode_key = "short" if "short" in mode else "reduce"

        st.markdown("##### 繰り上げ返済スケジュール設定")
        st.caption("繰り上げ返済を行う月と金額を入力してください（複数行追加可）")

        default_events = pd.DataFrame([
            {"month": 60,  "amount_man": 100},
            {"month": 120, "amount_man": 200},
        ])
        edited_events = st.data_editor(
            default_events,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "month": st.column_config.NumberColumn("実行月", min_value=1),
                "amount_man": st.column_config.NumberColumn("金額（万円）", min_value=1),
            },
        )

        prepayments = [
            {"month": int(row["month"]), "amount": float(row["amount_man"]) * 10000}
            for _, row in edited_events.iterrows()
            if row["month"] > 0 and row["amount_man"] > 0
        ]

        if st.button("計算する", type="primary", key="calc_prepay"):
            effect = prepayment_effect(principal, annual_rate, period_years, prepayments, mode_key)
            _show_prepayment_effect(effect)
            st.session_state["prepay_effect"] = effect

        if "prepay_effect" in st.session_state:
            _show_prepayment_effect(st.session_state["prepay_effect"])

    # ==================== Tab 2: 繰り上げ vs 投資 ====================
    with tab2:
        st.subheader("繰り上げ返済 vs 投資比較")
        st.markdown("余剰資金を繰り上げ返済に充てるか、NISA/インデックス投資に回すかを比較します。")

        col1, col2 = st.columns(2)
        with col1:
            invest_amount_man = st.number_input("余剰資金（万円）", min_value=10, value=100, step=10)
            prepay_month = st.number_input("繰り上げ実行月", min_value=1, value=60)
        with col2:
            invest_return = st.number_input("投資年利回り（%）", min_value=0.1, max_value=20.0, value=5.0, step=0.1, format="%.1f")
            tax_rate = st.number_input("投資利益税率（%）", min_value=0.0, max_value=50.0, value=20.315, step=0.001, format="%.3f")
            nisa = st.checkbox("NISA口座（非課税）", value=False)

        if nisa:
            tax_rate = 0.0

        horizon = period_years * 12 - int(prepay_month)
        if horizon > 0:
            result = prepay_vs_invest(
                invest_amount_man * 10000,
                int(prepay_month),
                annual_rate,
                invest_return / 100,
                tax_rate / 100,
                horizon,
            )

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("繰り上げ効果（節約利息）", f"{result['interest_saved']/10000:,.1f}万円")
            col_b.metric("投資最終価値", f"{result['invest_final_value']/10000:,.1f}万円")
            col_c.metric(
                "差額（投資 − 繰り上げ）",
                f"{result['diff']/10000:+,.1f}万円",
                delta="投資有利" if result["invest_wins"] else "繰り上げ有利",
            )

            st.info(
                f"💡 {'投資の方が有利です' if result['invest_wins'] else '繰り上げ返済の方が有利です'}"
                f"（差額: {abs(result['diff'])/10000:,.1f}万円）"
            )
        else:
            st.warning("繰り上げ実行月がローン期間を超えています。")

    # ==================== Tab 3: 借り換え ====================
    with tab3:
        st.subheader("借り換えシミュレーター")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**現在のローン**")
            current_balance_man = st.number_input("残債（万円）", min_value=100, value=2500, step=100, key="ref_bal")
            current_rate = st.number_input("現行金利（%）", min_value=0.1, max_value=8.0, value=1.0, step=0.01, format="%.2f", key="ref_rate")
            remaining_years = st.number_input("残存期間（年）", min_value=1, max_value=35, value=25, key="ref_years")
        with col2:
            st.markdown("**借り換え先**")
            banks = st.session_state.get("bank_data", [])
            bank_names = [b["bank_name"] for b in banks] if banks else []
            new_rate_input = st.number_input("借り換え後金利（%）", min_value=0.1, max_value=8.0, value=0.32, step=0.01, format="%.2f", key="ref_new_rate")
            cost_pct = st.number_input("諸費用（借入額の %）", min_value=0.0, max_value=5.0, value=1.0, step=0.1, format="%.1f")

        refinance_cost = current_balance_man * 10000 * cost_pct / 100

        if st.button("借り換え効果を計算", type="primary", key="calc_refin"):
            result = refinance_simulation(
                current_balance_man * 10000,
                current_rate,
                remaining_years * 12,
                new_rate_input,
                refinance_cost,
            )
            _show_refinance_result(result, refinance_cost)
            st.session_state["refin_result"] = result

        if "refin_result" in st.session_state:
            _show_refinance_result(st.session_state["refin_result"], refinance_cost)


def _show_prepayment_effect(effect: dict):
    col1, col2, col3 = st.columns(3)
    col1.metric("節約できる利息", f"{effect['interest_savings']/10000:,.1f}万円")
    col2.metric("短縮期間", f"{effect['months_saved']}ヶ月 ({effect['months_saved']//12}年{effect['months_saved']%12}ヶ月)")
    col3.metric("総節約額", f"{effect['savings']/10000:,.1f}万円")

    # 残高推移グラフ
    base_df = effect["base_df"]
    prep_df = effect["prep_df"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=base_df["month"]/12, y=base_df["balance"]/10000,
                             mode="lines", name="繰り上げなし", line=dict(dash="dash")))
    fig.add_trace(go.Scatter(x=prep_df["month"]/12, y=prep_df["balance"]/10000,
                             mode="lines", name="繰り上げあり"))
    fig.update_layout(xaxis_title="経過年数", yaxis_title="残高（万円）", height=350)
    st.plotly_chart(fig, use_container_width=True)


def _show_refinance_result(result: dict, cost: float):
    st.markdown(f"### {result['recommend']}")
    col1, col2, col3 = st.columns(3)
    col1.metric("月額節約額", f"{result['monthly_saving']:,.0f}円")
    col2.metric("諸費用", f"{cost/10000:,.1f}万円")
    if result["breakeven_months"]:
        col2.metric("損益分岐", f"{result['breakeven_months']}ヶ月 ({result['breakeven_months']//12}年{result['breakeven_months']%12}ヶ月後)")
    col3.metric("総節約額", f"{result['total_savings']/10000:,.1f}万円")
