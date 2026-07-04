from __future__ import annotations

import re
from collections import OrderedDict

import pandas as pd

from data import (
    COMMERCIAL_KEYWORD_WEIGHTS,
    EXAMPLE_QUERY_GROUPS,
    GENERIC_SUG_TEMPLATES,
    INTENT_LABELS,
    INTENT_RULES,
    INTENT_TRANSACTION_BASE,
    SCENARIO_CONFIG,
    SCENARIO_SUG_TEMPLATES,
    SPECIFICITY_MODIFIERS,
)


def normalize_query(query: str) -> str:
    return " ".join(query.strip().split())


def get_example_options() -> list[tuple[str, str]]:
    return [
        (category, query)
        for category, queries in EXAMPLE_QUERY_GROUPS.items()
        for query in queries
    ]


def find_scenario(query: str) -> dict:
    query_lower = query.lower()
    best_scenario = None
    best_score = 0

    for scenario in SCENARIO_CONFIG:
        score = sum(1 for keyword in scenario["match"] if keyword.lower() in query_lower)
        if score > best_score:
            best_scenario = scenario
            best_score = score

    if best_scenario:
        return best_scenario

    return {
        "category": "通用搜索场景",
        "match": (),
        "default_intents": ("信息查询", "购买决策", "攻略需求"),
        "intent_boosts": {"信息查询": 2},
    }


def detect_intents(query: str) -> dict:
    scenario = find_scenario(query)
    query_lower = query.lower()
    raw_scores = {intent: 0 for intent in INTENT_LABELS}
    matched_keywords = {intent: [] for intent in INTENT_LABELS}

    for rule in INTENT_RULES:
        for keyword in rule.keywords:
            if keyword.lower() in query_lower:
                raw_scores[rule.intent] += rule.weight
                matched_keywords[rule.intent].append(keyword)

    for intent, boost in scenario.get("intent_boosts", {}).items():
        if raw_scores.get(intent, 0) > 0 or scenario["category"] != "通用搜索场景":
            raw_scores[intent] += boost

    if not any(raw_scores.values()):
        raw_scores["信息查询"] = 5
        matched_keywords["信息查询"].append("fallback")

    confidences = {
        intent: min(100, int(round(28 + score * 6.5))) if score > 0 else 0
        for intent, score in raw_scores.items()
    }

    ranked_intents = sorted(
        INTENT_LABELS,
        key=lambda intent: (confidences[intent], raw_scores[intent], -INTENT_LABELS.index(intent)),
        reverse=True,
    )
    primary_intent = ranked_intents[0]
    secondary_intents = [
        intent
        for intent in ranked_intents[1:]
        if confidences[intent] >= 45
    ][:3]

    return {
        "query": query,
        "scenario": scenario,
        "primary_intent": primary_intent,
        "secondary_intents": secondary_intents,
        "confidence": confidences[primary_intent],
        "confidences": confidences,
        "raw_scores": raw_scores,
        "matched_keywords": matched_keywords,
    }


def build_intent_distribution(intent_result: dict) -> pd.DataFrame:
    rows = []
    primary = intent_result["primary_intent"]
    secondary = set(intent_result["secondary_intents"])

    for intent in INTENT_LABELS:
        if intent == primary:
            role = "主意图"
        elif intent in secondary:
            role = "辅助意图"
        else:
            role = "弱信号"

        rows.append(
            {
                "意图类型": intent,
                "Confidence": intent_result["confidences"][intent],
                "匹配关键词": "、".join(intent_result["matched_keywords"][intent]) or "-",
                "识别角色": role,
            }
        )

    return pd.DataFrame(rows)


def _render_template(template: str, topic: str) -> str:
    return normalize_query(template.format(topic=topic))


def _dedupe(items: list[str]) -> list[str]:
    return list(OrderedDict.fromkeys(item for item in items if item))


def _get_templates_for_intent(intent: str, scenario_category: str) -> list[str]:
    scenario_templates = SCENARIO_SUG_TEMPLATES.get(scenario_category, {}).get(intent, [])
    generic_templates = GENERIC_SUG_TEMPLATES.get(intent, [])
    return [*scenario_templates, *generic_templates]


def generate_suggestions(query: str, intent_result: dict, max_count: int = 8) -> list[str]:
    scenario = intent_result["scenario"]
    category = scenario["category"]
    primary_intent = intent_result["primary_intent"]
    priority_intents = _dedupe(
        [
            primary_intent,
            *intent_result["secondary_intents"],
            *scenario.get("default_intents", ()),
            "购买决策",
            "价格比较",
            "攻略需求",
            "信息查询",
        ]
    )

    suggestions: list[str] = []
    primary_quota = 5 if primary_intent in {"价格比较", "购买决策", "攻略需求", "内容消费", "工具使用"} else 4

    for template in _get_templates_for_intent(primary_intent, category)[:primary_quota]:
        suggestions.append(_render_template(template, query))

    for intent in priority_intents[1:]:
        quota = 3 if len(suggestions) < 5 else 2
        for template in _get_templates_for_intent(intent, category)[:quota]:
            suggestions.append(_render_template(template, query))
            if len(_dedupe(suggestions)) >= max_count:
                return _dedupe(suggestions)[:max_count]

    if len(_dedupe(suggestions)) < 5:
        for intent in INTENT_LABELS:
            for template in _get_templates_for_intent(intent, category)[:2]:
                suggestions.append(_render_template(template, query))
                if len(_dedupe(suggestions)) >= 5:
                    return _dedupe(suggestions)[:max_count]

    return _dedupe(suggestions)[:max_count]


def _keyword_score(text: str, keyword_weights: dict[str, int]) -> tuple[int, list[str]]:
    text_lower = text.lower()
    hits = []
    score = 0

    for keyword, weight in keyword_weights.items():
        if keyword.lower() in text_lower:
            hits.append(keyword)
            score += weight

    return score, hits


def _count_query_overlap(query: str, suggestion: str) -> int:
    query_parts = [part for part in re.split(r"\s+", query) if part]
    if not query_parts:
        return 0

    suggestion_lower = suggestion.lower()
    return sum(1 for part in query_parts if part.lower() in suggestion_lower)


def score_intent_match(query_intents: dict, suggestion_intents: dict, query: str, suggestion: str) -> int:
    query_primary = query_intents["primary_intent"]
    query_secondary = set(query_intents["secondary_intents"])
    sug_primary = suggestion_intents["primary_intent"]
    sug_secondary = set(suggestion_intents["secondary_intents"])

    if sug_primary == query_primary:
        score = 78
    elif sug_primary in query_secondary:
        score = 72
    elif query_primary in sug_secondary:
        score = 68
    elif query_secondary.intersection(sug_secondary):
        score = 62
    else:
        score = 52

    score += min(12, int(suggestion_intents["confidence"] * 0.12))
    score += min(8, _count_query_overlap(query, suggestion) * 4)
    return min(100, score)


def score_transaction_potential(intent: str, suggestion: str, scenario: dict) -> int:
    base_score = INTENT_TRANSACTION_BASE.get(intent, 50)
    keyword_score, _ = _keyword_score(suggestion, COMMERCIAL_KEYWORD_WEIGHTS)
    scenario_boost = {
        "旅游消费": 4,
        "AI 工具": 5,
        "教育留学": 3,
        "体育内容": 2,
        "消费电子": 5,
        "本地生活": 5,
        "通用搜索场景": 0,
    }.get(scenario["category"], 0)

    return min(100, base_score + int(keyword_score * 0.35) + scenario_boost)


def score_specificity(query: str, suggestion: str, scenario: dict) -> int:
    compact = suggestion.replace(" ", "")
    length = len(compact)
    score = 35

    if length >= 8:
        score += 12
    if length >= 12:
        score += 12
    if length >= 18:
        score += 10
    if length > 34:
        score -= 8

    if re.search(r"\d{2,4}|AI|NBA|F1|PPT|iPhone", suggestion, flags=re.IGNORECASE):
        score += 8

    modifier_hits = [keyword for keyword in SPECIFICITY_MODIFIERS if keyword.lower() in suggestion.lower()]
    score += min(20, len(modifier_hits) * 5)
    score += min(10, sum(1 for keyword in scenario.get("match", ()) if keyword.lower() in suggestion.lower()) * 3)
    score += min(8, _count_query_overlap(query, suggestion) * 4)

    return max(0, min(100, score))


def score_commercial_keyword_strength(suggestion: str) -> int:
    keyword_score, _ = _keyword_score(suggestion, COMMERCIAL_KEYWORD_WEIGHTS)
    return min(100, 30 + keyword_score)


def generate_score_reason(scores: dict[str, int], suggestion_intents: dict) -> str:
    reasons = []

    if scores["Intent Match"] >= 85:
        reasons.append("与用户主意图高度一致")
    elif scores["Intent Match"] >= 70:
        reasons.append("覆盖主意图或关键辅助意图")
    else:
        reasons.append("适合作为探索型补充词")

    if scores["Transaction Potential"] >= 85:
        reasons.append("具备直接交易或线索承接价值")
    elif scores["Transaction Potential"] >= 70:
        reasons.append("可引导用户进入决策链路")

    if scores["Specificity"] >= 75:
        reasons.append("表达具体，适合承接长尾需求")

    if scores["Commercial Keyword Strength"] >= 75:
        reasons.append("包含强商业关键词")

    if "工具使用" in [suggestion_intents["primary_intent"], *suggestion_intents["secondary_intents"]]:
        reasons.append("适合承接 AI 工具试用或模板需求")

    return "；".join(_dedupe(reasons))


def build_suggestion_table(query: str, intent_result: dict, suggestions: list[str]) -> pd.DataFrame:
    rows = []

    for suggestion in suggestions:
        suggestion_intents = detect_intents(suggestion)
        main_intent = suggestion_intents["primary_intent"]
        auxiliary_intents = suggestion_intents["secondary_intents"]
        scenario = intent_result["scenario"]

        component_scores = {
            "Intent Match": score_intent_match(intent_result, suggestion_intents, query, suggestion),
            "Transaction Potential": score_transaction_potential(main_intent, suggestion, scenario),
            "Specificity": score_specificity(query, suggestion, scenario),
            "Commercial Keyword Strength": score_commercial_keyword_strength(suggestion),
        }
        overall = round(
            component_scores["Intent Match"] * 0.35
            + component_scores["Transaction Potential"] * 0.30
            + component_scores["Specificity"] * 0.20
            + component_scores["Commercial Keyword Strength"] * 0.15
        )

        rows.append(
            {
                "SUG 推荐词": suggestion,
                "主意图": main_intent,
                "辅助意图": "、".join(auxiliary_intents) if auxiliary_intents else "-",
                **component_scores,
                "Overall Commercial Score": overall,
                "推荐理由": generate_score_reason(component_scores, suggestion_intents),
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values("Overall Commercial Score", ascending=False)
        .reset_index(drop=True)
    )


def build_dimension_chart_data(suggestion_df: pd.DataFrame) -> pd.DataFrame:
    score_columns = [
        "Intent Match",
        "Transaction Potential",
        "Specificity",
        "Commercial Keyword Strength",
    ]
    return suggestion_df.set_index("SUG 推荐词")[score_columns]


def generate_strategy_cards(query: str, intent_result: dict, suggestion_df: pd.DataFrame) -> dict[str, str]:
    primary = intent_result["primary_intent"]
    secondary = "、".join(intent_result["secondary_intents"]) or "无明显辅助意图"
    category = intent_result["scenario"]["category"]
    top_row = suggestion_df.iloc[0]
    average_score = suggestion_df["Overall Commercial Score"].mean()

    traffic_map = {
        "价格比较": "优先分发到价格聚合、优惠活动和官方交易入口，同时保留攻略页承接尚未决策的用户。",
        "购买决策": "优先分发到榜单、测评、商品/服务详情页，用评价和对比模块缩短决策路径。",
        "攻略需求": "先进入内容攻略或流程页，再在关键节点插入价格、平台、预约或购买入口。",
        "内容消费": "优先分发到直播、回放、赛程和会员订阅页，突出时效性内容和观看权益。",
        "本地服务": "优先分发到本地商家列表、地图/附近结果、预约入口和用户评价页。",
        "工具使用": "优先分发到工具试用、模板库、教程页和效率场景页，降低首次使用门槛。",
        "品牌偏好": "优先分发到品牌专区、官方入口和竞品对比页，承接确定性品牌需求。",
        "信息查询": "先满足基础信息查询，再通过相关 SUG 引导到攻略、购买或服务承接页。",
    }

    sug_map = {
        "价格比较": "首屏 SUG 应覆盖优惠、价格、折扣、套餐和对比，形成从低价心智到交易入口的连续路径。",
        "购买决策": "推荐词应突出官方入口、购买渠道、推荐榜单和用户评价，帮助用户完成方案筛选。",
        "攻略需求": "推荐词应扩展流程、指南、避坑和时间安排，避免只给泛信息词。",
        "内容消费": "推荐词应覆盖直播、回放、赛程、集锦和订阅，兼顾即时观看和后续消费。",
        "工具使用": "推荐词应覆盖使用方法、免费工具、模板、对比和效率提升，适合 AI 工具增长漏斗。",
    }

    conversion_note = (
        "当前推荐池商业化潜力较高，可将高分 SUG 进入 A/B 实验，观察 SUG 点击率、搜索后点击率和最终转化率。"
        if average_score >= 78
        else "当前推荐池仍需要补充更强交易词和更具体场景词，再进入商业化实验。"
    )

    return {
        "流量分发建议": (
            f"query「{query}」属于「{category}」，主意图为「{primary}」，辅助意图为「{secondary}」。"
            f"{traffic_map.get(primary, traffic_map['信息查询'])}"
        ),
        "SUG 优化建议": (
            f"建议优先展示「{top_row['SUG 推荐词']}」等高分词。"
            f"{sug_map.get(primary, '推荐词应同时覆盖信息补全、决策比较和商业入口，提升搜索框下拉推荐的业务价值。')}"
        ),
        "商业化转化建议": (
            f"推荐池平均商业化分为 {average_score:.1f}，最高分为 {int(top_row['Overall Commercial Score'])}。"
            f"{conversion_note}"
        ),
    }
