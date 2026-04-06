"""
Streamlit メインエントリポイント
"""

import streamlit as st

st.set_page_config(
    page_title="住宅ローン・人生設計ツール",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- ナビゲーション ----------
PAGES = {
    "🏦 銀行金利取得": "page_bank",
    "📊 ローン比較":   "page_loan",
    "⚡ 繰り上げ/借り換え": "page_prepayment",
    "🗺️ 人生設計":    "page_life",
}

with st.sidebar:
    st.title("🏠 FP プランナー")
    st.caption("住宅ローン・人生設計シミュレーター")
    st.divider()
    selected_page = st.radio("メニュー", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    # 設定・保存エリア（Phase 5 で拡充）
    with st.expander("⚙️ データ管理"):
        from utils.export import save_bank_rates, load_bank_rates, save_user_profile, load_user_profile
        if st.button("銀行データを保存"):
            if st.session_state.get("bank_data"):
                save_bank_rates(st.session_state["bank_data"], st.session_state.get("bank_fetch_date",""))
                st.success("保存しました。")
        if st.button("銀行データを読込"):
            saved = load_bank_rates()
            if saved:
                st.session_state["bank_data"] = saved["banks"]
                st.session_state["bank_fetch_date"] = saved.get("fetch_date","")
                st.success(f"{len(saved['banks'])}行 読み込みました。")
            else:
                st.warning("保存データがありません。")
        st.divider()
        if st.button("セッションをリセット"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# ---------- ページルーティング ----------
module_name = PAGES[selected_page]

if module_name == "page_bank":
    from ui.page_bank import render
elif module_name == "page_loan":
    from ui.page_loan import render
elif module_name == "page_prepayment":
    from ui.page_prepayment import render
elif module_name == "page_life":
    from ui.page_life import render

render()
