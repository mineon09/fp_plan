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
    # Phase 3 実装前のプレースホルダー
    def render():
        st.header("⚡ 繰り上げ返済・借り換えシミュレーター")
        st.info("Phase 3 で実装予定です。")
elif module_name == "page_life":
    # Phase 4 実装前のプレースホルダー
    def render():
        st.header("🗺️ 人生設計キャッシュフローシミュレーター")
        st.info("Phase 4 で実装予定です。")

render()
