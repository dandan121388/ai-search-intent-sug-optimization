from __future__ import annotations

import pandas as pd
import streamlit as st

from data import APP_TITLE, EXAMPLE_QUERY_GROUPS
from utils import (
    build_dimension_chart_data,
    build_intent_distribution,
    build_suggestion_table,
    detect_intents,
    generate_strategy_cards,
    generate_suggestions,
    normalize_query,
)


def apply_page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1240px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        .page-header {
            border-bottom: 1px solid #e5e7eb;
            padding-bottom: 1rem;
            margin-bottom: 1.4rem;
        }
        .page-header h1 {
            margin-bottom: 0.35rem;
        }
        .subtle-text {
            color: #4b5563;
            font-size: 1rem;
            line-height: 1.7;
        }
        .section-title {
            margin-top: 1.25rem;
            margin-bottom: 0.45rem;
            font-size: 1.35rem;
            font-weight: 700;
            color: #111827;
        }
        .strategy-card {
            min-height: 190px;
            border: 1px solid #d8dee9;
            border-radius: 8px;
            padding: 1rem 1.05rem;
            background: #ffffff;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        .strategy-card h4 {
            margin-top: 0;
            margin-bottom: 0.65rem;
            color: #0f172a;
        }
        .strategy-card p {
            color: #374151;
            line-height: 1.68;
            margin-bottom: 0;
        }
        .method-box {
            border-left: 4px solid #2563eb;
            background: #f8fafc;
            padding: 1rem 1.1rem;
            border-radius: 6px;
            color: #111827;
            line-height: 1.75;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        f"""
        <div class="page-header">
            <h1>{APP_TITLE}</h1>
            <p class="subtle-text">
                V2 dashboard 使用规则引擎与可解释评分框架，模拟 AI 搜索平台的 SUG 运营决策流程：
                识别用户搜索意图，生成候选推荐词，评估商业化转化潜力，并输出流量分发与运营优化建议。
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_query_input() -> str:
    st.markdown("<div class='section-title'>Query 输入区</div>", unsafe_allow_html=True)
    category_col, example_col = st.columns([1, 1.5])
    categories = list(EXAMPLE_QUERY_GROUPS.keys())

    with category_col:
        selected_category = st.selectbox("业务场景", categories)
    with example_col:
        selected_example = st.selectbox("示例 Query", EXAMPLE_QUERY_GROUPS[selected_category])

    if "selected_example_query" not in st.session_state:
        st.session_state.selected_example_query = selected_example
    if "query_input" not in st.session_state:
        st.session_state.query_input = selected_example
    if st.session_state.selected_example_query != selected_example:
        st.session_state.selected_example_query = selected_example
        st.session_state.query_input = selected_example

    query = st.text_input(
        "手动输入或微调 Query",
        placeholder="例如：AI 数据分析工具",
        key="query_input",
    )
    return normalize_query(query)


def render_intent_section(intent_result: dict) -> pd.DataFrame:
    st.markdown("<div class='section-title'>意图识别结果</div>", unsafe_allow_html=True)
    intent_df = build_intent_distribution(intent_result)
    secondary_text = "、".join(intent_result["secondary_intents"]) or "-"

    metric_cols = st.columns(4)
    metric_cols[0].metric("业务场景", intent_result["scenario"]["category"])
    metric_cols[1].metric("主意图", intent_result["primary_intent"])
    metric_cols[2].metric("Intent Confidence", f"{intent_result['confidence']}/100")
    metric_cols[3].metric("辅助意图", secondary_text)

    with st.expander("查看多意图识别明细", expanded=True):
        st.dataframe(
            intent_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Confidence": st.column_config.ProgressColumn(
                    "Confidence",
                    min_value=0,
                    max_value=100,
                    format="%d",
                )
            },
        )

    return intent_df


def render_suggestion_table(suggestion_df: pd.DataFrame) -> None:
    st.markdown("<div class='section-title'>SUG 推荐词评分表</div>", unsafe_allow_html=True)
    st.dataframe(
        suggestion_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Intent Match": st.column_config.ProgressColumn("Intent Match", min_value=0, max_value=100, format="%d"),
            "Transaction Potential": st.column_config.ProgressColumn(
                "Transaction Potential",
                min_value=0,
                max_value=100,
                format="%d",
            ),
            "Specificity": st.column_config.ProgressColumn("Specificity", min_value=0, max_value=100, format="%d"),
            "Commercial Keyword Strength": st.column_config.ProgressColumn(
                "Commercial Keyword Strength",
                min_value=0,
                max_value=100,
                format="%d",
            ),
            "Overall Commercial Score": st.column_config.ProgressColumn(
                "Overall Commercial Score",
                min_value=0,
                max_value=100,
                format="%d",
            ),
        },
    )


def render_dashboard(suggestion_df: pd.DataFrame, intent_df: pd.DataFrame) -> None:
    st.markdown("<div class='section-title'>可视化 Dashboard</div>", unsafe_allow_html=True)
    top_score = int(suggestion_df["Overall Commercial Score"].max())
    avg_score = suggestion_df["Overall Commercial Score"].mean()
    top_sug = suggestion_df.iloc[0]["SUG 推荐词"]

    metric_cols = st.columns(3)
    metric_cols[0].metric("Top SUG Score", f"{top_score}/100")
    metric_cols[1].metric("Average Score", f"{avg_score:.1f}")
    metric_cols[2].metric("SUG Count", len(suggestion_df))
    st.caption(f"当前推荐池首选测试词：{top_sug}")

    chart_col, dimension_col = st.columns([1, 1])

    with chart_col:
        st.subheader("SUG Overall Commercial Score")
        overall_chart_df = suggestion_df.set_index("SUG 推荐词")[["Overall Commercial Score"]]
        st.bar_chart(overall_chart_df, use_container_width=True)

    with dimension_col:
        st.subheader("评分维度分组柱状图")
        st.bar_chart(build_dimension_chart_data(suggestion_df), use_container_width=True)

    st.subheader("意图分布")
    intent_chart_df = intent_df.set_index("意图类型")[["Confidence"]]
    st.bar_chart(intent_chart_df, use_container_width=True)


def render_strategy_cards(strategy_cards: dict[str, str]) -> None:
    st.markdown("<div class='section-title'>运营策略建议</div>", unsafe_allow_html=True)
    cols = st.columns(3)

    for col, (title, body) in zip(cols, strategy_cards.items()):
        with col:
            st.markdown(
                f"""
                <div class="strategy-card">
                    <h4>{title}</h4>
                    <p>{body}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_methodology() -> None:
    st.markdown("<div class='section-title'>项目方法论说明</div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="method-box">
            <strong>Product Logic：</strong>
            用户 query 先经过场景识别和多意图识别，系统再基于主意图与辅助意图生成候选 SUG。
            每条 SUG 使用四维评分框架评估商业化潜力：
            Intent Match 占 35%，Transaction Potential 占 30%，Specificity 占 20%，
            Commercial Keyword Strength 占 15%。最终结果可用于搜索框推荐词排序、流量分发策略和运营实验设计。
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    apply_page_style()
    render_header()

    query = render_query_input()
    if not query:
        st.info("请输入一个搜索 query，或从示例库中选择。")
        return

    intent_result = detect_intents(query)
    suggestions = generate_suggestions(query, intent_result)
    suggestion_df = build_suggestion_table(query, intent_result, suggestions)
    intent_df = render_intent_section(intent_result)

    render_suggestion_table(suggestion_df)
    render_dashboard(suggestion_df, intent_df)
    render_strategy_cards(generate_strategy_cards(query, intent_result, suggestion_df))
    render_methodology()

    with st.sidebar:
        st.markdown("### 项目范围")
        st.caption("本地规则引擎版本，不接入真实大模型 API 或外部付费服务。")
        st.caption("示例 query 覆盖旅游消费、AI 工具、教育留学、体育内容、消费电子和本地生活。")


if __name__ == "__main__":
    main()
