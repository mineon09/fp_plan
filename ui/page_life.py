"""
Module 4 UI: 人生設計キャッシュフローシミュレーターページ
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import LIFE_DEFAULTS, LIFE_EVENT_PRESETS, SCENARIOS
from modules.life_planner import calc_life_cashflow, calc_scenarios, life_summary
from utils.export import save_user_profile, load_user_profile


def render():
    st.header("🗺️ 人生設計キャッシュフローシミュレーター")

    # ローンスケジュールをセッションから取得
    loan_df = st.session_state.get("loan_schedule_df", None)
    if loan_df is None:
        # ローンが設定されていない場合は手入力
        with st.expander("🏠 住宅ローン設定（ローン比較タブで設定済みなら不要）"):
            use_loan = st.checkbox("ローン返済を含める", value=True, key="life_use_loan")
            if use_loan:
                col1, col2, col3 = st.columns(3)
                loan_man = col1.number_input("借入金額（万円）", 500, 10000, 3000, 100, key="life_loan_man")
                loan_years = col2.selectbox("期間（年）", list(range(10, 36)), index=25, key="life_loan_yrs")
                loan_rate = col3.number_input("金利（%）", 0.1, 8.0, 0.32, 0.01, format="%.2f", key="life_loan_rate")

                from modules.loan_simulator import amortization_schedule
                loan_df = amortization_schedule(loan_man * 10000, loan_rate, loan_years)
            else:
                loan_df = None

    # ==================== プロファイル入力 ====================
    with st.expander("👤 基本プロファイル", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            age_now = st.number_input("現在年齢", 20, 70, LIFE_DEFAULTS["age_now"], key="life_age")
            income_man = st.number_input("年収（税引き前・万円）", 100, 5000, LIFE_DEFAULTS["income_man"], 50, key="life_income")
            retire_age = st.number_input("定年年齢", 55, 70, LIFE_DEFAULTS["retire_age"], key="life_retire")
            severance_man = st.number_input("退職金（万円）", 0, 5000, LIFE_DEFAULTS["severance_pay_man"], 100, key="life_sev")
            assets_man = st.number_input("現在の金融資産（万円）", 0, 10000, LIFE_DEFAULTS["assets_man"], 100, key="life_assets")
        with col2:
            age_death = st.number_input("想定寿命", 70, 120, LIFE_DEFAULTS["age_death"], key="life_death")
            income_spouse_man = st.number_input("配偶者年収（万円）", 0, 5000, LIFE_DEFAULTS["income_spouse_man"], 50, key="life_sp_income")
            pension_monthly_man = st.number_input("年金月額 合計（万円）", 0, 100, LIFE_DEFAULTS["pension_monthly_man"], key="life_pension")
            living_cost_man = st.number_input("現在の生活費（月・万円）", 10, 100, LIFE_DEFAULTS["living_cost_monthly_man"], key="life_cost")
            invest_return_pct = st.number_input("投資利回り（%）", 0.0, 20.0, LIFE_DEFAULTS["invest_return"] * 100, 0.5, format="%.1f", key="life_inv")

    profile = {
        "age_now": age_now,
        "age_death": age_death,
        "income_man": income_man,
        "income_spouse_man": income_spouse_man,
        "retire_age": retire_age,
        "severance_pay_man": severance_man,
        "pension_start_age": retire_age,
        "pension_monthly_man": pension_monthly_man,
        "living_cost_monthly_man": living_cost_man,
        "living_cost_retire_man": LIFE_DEFAULTS["living_cost_retire_man"],
        "assets_man": assets_man,
        "invest_return": invest_return_pct / 100,
        "income_growth_rate": LIFE_DEFAULTS["income_growth_rate"],
        "inflation_rate": LIFE_DEFAULTS["inflation_rate"],
    }

    # ==================== ライフイベント ====================
    with st.expander("📅 ライフイベント設定", expanded=False):
        st.caption("プリセットから選択するか、手動で追加・編集してください。")

        preset_names = [e["name"] for e in LIFE_EVENT_PRESETS]
        selected_presets = st.multiselect("プリセットを追加", preset_names, default=preset_names[:5])
        preset_events = [e for e in LIFE_EVENT_PRESETS if e["name"] in selected_presets]

        events_df = pd.DataFrame([
            {"name": e["name"], "age_start": e["age_start"], "age_end": e["age_end"],
             "total_man": e["total_man"], "recurring": e["recurring"]}
            for e in preset_events
        ])

        edited_events = st.data_editor(
            events_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "name": "イベント名",
                "age_start": st.column_config.NumberColumn("開始年齢", min_value=age_now),
                "age_end": st.column_config.NumberColumn("終了年齢", min_value=age_now),
                "total_man": st.column_config.NumberColumn("合計費用（万円）", min_value=0),
                "recurring": st.column_config.CheckboxColumn("毎年分割"),
            },
        )

        life_events = edited_events.to_dict("records")

    # ==================== シナリオ選択 ====================
    show_scenarios = st.checkbox("📊 3シナリオ比較（楽観/ベース/悲観）を表示", value=True)

    col_calc, col_save = st.columns([2, 1])
    with col_calc:
        calc_btn = st.button("🔢 シミュレーション実行", type="primary")
    with col_save:
        if st.button("💾 プロファイル保存"):
            save_user_profile(profile)
            st.success("保存しました。")

    if calc_btn:
        with st.spinner("計算中..."):
            if show_scenarios:
                scenario_results = calc_scenarios(profile, loan_df, life_events)
                st.session_state["life_scenarios"] = scenario_results
            else:
                base_df = calc_life_cashflow(profile, loan_df, life_events)
                st.session_state["life_base"] = base_df
                st.session_state["life_scenarios"] = {"ベース": base_df}

    # ==================== 結果表示 ====================
    if "life_scenarios" in st.session_state:
        _render_results(st.session_state["life_scenarios"], profile, age_now, retire_age)


def _render_results(scenarios: dict[str, pd.DataFrame], profile: dict, age_now: int, retire_age: int):
    # サマリーカード（ベースシナリオ）
    if "ベース" in scenarios:
        base_df = scenarios["ベース"]
        summary = life_summary(base_df, age_now, retire_age)

        st.subheader("📋 サマリーカード（ベースシナリオ）")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("完済年齢", f"{summary['payoff_age']}歳")
        col2.metric("資産ピーク", f"{summary['peak_age']}歳 / {summary['peak_assets_man']:,.0f}万円")
        col3.metric("老後資金", summary["depletion_label"])
        col4.metric("死亡時資産残高", f"{summary['final_assets_man']:,.0f}万円")

        fire_text = f"{summary['fire_age']}歳でFIRE達成" if summary["fire_age"] else "FIRE達成条件未達"
        st.caption(f"💡 {fire_text}")

    # 生涯CF推移グラフ
    st.subheader("📈 純資産推移グラフ")
    fig = go.Figure()

    colors = {"楽観": "#2ecc71", "ベース": "#3498db", "悲観": "#e74c3c"}
    for scenario_name, df in scenarios.items():
        fig.add_trace(go.Scatter(
            x=df["age"],
            y=df["assets"] / 10000,
            mode="lines",
            name=scenario_name,
            line=dict(color=colors.get(scenario_name, "#888888"),
                      width=3 if scenario_name == "ベース" else 1.5,
                      dash="solid" if scenario_name == "ベース" else "dot"),
        ))

    fig.add_hline(y=0, line_color="black", line_width=1.5, line_dash="dash",
                  annotation_text="資産ゼロライン", annotation_position="bottom right")
    fig.update_layout(
        xaxis_title="年齢",
        yaxis_title="純資産（万円）",
        height=450,
        legend_title="シナリオ",
    )
    st.plotly_chart(fig, use_container_width=True)

    # 年次収支テーブル
    if "ベース" in scenarios:
        with st.expander("📄 年次収支テーブル（ベースシナリオ）"):
            df = scenarios["ベース"].copy()
            for col in ["income", "expense", "loan_annual", "life_event_cost",
                        "net_cashflow", "invest_gain", "assets"]:
                df[col] = (df[col] / 10000).round(1)
            df.columns = ["年齢", "収入(万)", "支出(万)", "ローン(万)", "イベント(万)",
                          "純CF(万)", "投資益(万)", "純資産(万)"]

            st.dataframe(df, use_container_width=True, height=400)

            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 CSV ダウンロード", csv, "life_cashflow.csv", "text/csv")
