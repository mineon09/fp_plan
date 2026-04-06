"""
Module 1 UI: 銀行金利データ取得ページ
"""

import json
import streamlit as st

from config import DEFAULT_BANKS
from modules.bank_data import generate_prompt, parse_and_validate, get_default_banks


def render():
    st.header("🏦 銀行金利データ取得")
    st.markdown(
        "AIに最新の住宅ローン金利を照会するプロンプトを生成します。"
        "生成されたプロンプトをClaudeやChatGPTに貼り付け、返ってきたJSONをここに貼り付けてください。"
    )

    # ---------- 銀行選択 ----------
    all_names = [b["bank_name"] for b in DEFAULT_BANKS]
    selected = st.multiselect(
        "対象銀行を選択",
        options=all_names,
        default=all_names,
        key="bank_select",
    )

    # ---------- プロンプト生成 ----------
    if st.button("📋 プロンプトを生成", type="primary"):
        if not selected:
            st.warning("銀行を1行以上選択してください。")
        else:
            st.session_state["generated_prompt"] = generate_prompt(selected)

    if "generated_prompt" in st.session_state:
        st.subheader("生成されたプロンプト")
        st.text_area(
            "以下をコピーしてAIに貼り付けてください",
            value=st.session_state["generated_prompt"],
            height=320,
            key="prompt_display",
        )

    st.divider()

    # ---------- JSON 貼り付け ----------
    st.subheader("AI出力（JSON）を貼り付け")
    raw_json = st.text_area(
        "AIが返したJSONをここに貼り付け",
        height=200,
        key="raw_json_input",
        placeholder='{"fetch_date": "2026-04", "banks": [...]}',
    )

    col1, col2 = st.columns([1, 3])
    use_default = col2.button("デフォルト値を使用（サンプル）")

    if col1.button("✅ パース・検証", type="primary"):
        if not raw_json.strip():
            st.error("JSONを貼り付けてください。")
        else:
            _apply_parsed(parse_and_validate(raw_json))

    if use_default:
        banks = get_default_banks()
        st.session_state["bank_data"] = banks
        st.session_state["bank_fetch_date"] = "default"
        st.success(f"{len(banks)} 行のデフォルトデータを読み込みました。")

    # ---------- 確認テーブル ----------
    if "bank_data" in st.session_state and st.session_state["bank_data"]:
        banks = st.session_state["bank_data"]
        st.subheader("📊 銀行金利テーブル（確認・編集）")
        st.caption(f"取得日: {st.session_state.get('bank_fetch_date', '-')}")

        edited = st.data_editor(
            _to_display_df(banks),
            use_container_width=True,
            num_rows="dynamic",
            key="bank_editor",
        )

        if st.button("💾 このデータで計算する", type="primary"):
            st.session_state["bank_data"] = edited.to_dict("records")
            st.success("銀行データを確定しました。ローン比較タブへ進んでください。")


def _apply_parsed(result: dict):
    if result["errors"]:
        for e in result["errors"]:
            st.error(e)
    for w in result["warnings"]:
        st.warning(w)
    if result["ok"]:
        st.session_state["bank_data"] = result["banks"]
        st.session_state["bank_fetch_date"] = result["fetch_date"]
        st.success(f"{len(result['banks'])} 行の銀行データを読み込みました。")
    else:
        st.error("データの読み込みに失敗しました。エラーを確認してください。")


def _to_display_df(banks: list[dict]):
    import pandas as pd
    rows = []
    for b in banks:
        rows.append({
            "銀行名": b.get("bank_name", ""),
            "変動35年(%)": b.get("variable_35"),
            "固定35年(%)": b.get("fixed_35"),
            "固定10年(%)": b.get("fixed_10"),
            "団信": b.get("has_team_dan", True),
            "備考": b.get("notes", ""),
        })
    return pd.DataFrame(rows)
