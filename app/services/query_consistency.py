from __future__ import annotations

from collections import defaultdict

from app.schemas.retrieval import QueryWarning

# Terms may belong to multiple categories. Ambiguous terms do not trigger a
# mismatch when one of their categories matches the campaign category.
CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "美妆个护": {"美妆个护"},
    "敏感肌": {"美妆个护"},
    "护肤": {"美妆个护"},
    "美白": {"美妆个护"},
    "防晒": {"美妆个护"},
    "香氛": {"美妆个护"},
    "通勤妆": {"美妆个护"},
    "精华": {"美妆个护"},
    "粉底": {"美妆个护"},
    "成分": {"美妆个护", "食品饮料"},
    "时尚穿搭": {"时尚穿搭"},
    "通勤穿搭": {"时尚穿搭"},
    "轻奢": {"时尚穿搭"},
    "国潮": {"时尚穿搭"},
    "配色": {"时尚穿搭"},
    "面料": {"时尚穿搭"},
    "科技数码": {"科技数码"},
    "续航": {"科技数码"},
    "影像": {"科技数码"},
    "手机": {"科技数码"},
    "电脑": {"科技数码"},
    "游戏性能": {"科技数码"},
    "母婴育儿": {"母婴育儿"},
    "辅食": {"母婴育儿"},
    "早教": {"母婴育儿"},
    "亲子": {"母婴育儿"},
    "食品饮料": {"食品饮料"},
    "探店": {"食品饮料"},
    "配料表": {"食品饮料"},
    "低糖": {"食品饮料"},
    "咖啡": {"食品饮料"},
    "早餐": {"食品饮料"},
    "料理": {"食品饮料"},
    "健身运动": {"健身运动"},
    "跑步": {"健身运动"},
    "力量训练": {"健身运动"},
    "瑜伽": {"健身运动"},
    "运动装备": {"健身运动"},
    "家居生活": {"家居生活"},
    "收纳": {"家居生活"},
    "清洁": {"家居生活"},
    "软装": {"家居生活"},
    "家电": {"家居生活", "科技数码"},
    "旅行摄影": {"旅行摄影"},
    "旅行攻略": {"旅行摄影"},
    "酒店": {"旅行摄影"},
    "摄影": {"旅行摄影"},
    "构图": {"旅行摄影"},
}


def categories_for_term(term: str) -> set[str]:
    detected: set[str] = set()
    normalized = term.strip().lower()
    if not normalized:
        return detected
    for keyword, categories in CATEGORY_KEYWORDS.items():
        keyword_lower = keyword.lower()
        if keyword_lower in normalized or (len(normalized) >= 2 and normalized in keyword_lower):
            detected.update(categories)
    return detected


def check_query_campaign_consistency(
    terms: list[str],
    *,
    campaign_category: str,
    required_topics: list[str],
    tone_tags: list[str],
) -> list[QueryWarning]:
    conflicting: dict[str, set[str]] = defaultdict(set)
    for term in terms:
        detected = categories_for_term(term)
        if detected and campaign_category not in detected:
            for category in detected:
                conflicting[category].add(term)

    if not conflicting:
        return []

    conflicting_terms = sorted({term for terms_for_category in conflicting.values() for term in terms_for_category})
    detected_categories = sorted(conflicting)
    quoted_terms = "、".join(f"“{term}”" for term in conflicting_terms)
    category_text = "、".join(f"“{category}”" for category in detected_categories)
    suggested_parts = list(dict.fromkeys([campaign_category, *required_topics, *tone_tags]))
    return [
        QueryWarning(
            code="query_campaign_category_mismatch",
            message=(
                f"查询词{quoted_terms}主要关联{category_text}，可能与当前Campaign品类"
                f"“{campaign_category}”不一致；请确认是否为跨品类需求。"
            ),
            campaign_category=campaign_category,
            conflicting_terms=conflicting_terms,
            detected_categories=detected_categories,
            suggested_query=" ".join(suggested_parts),
        )
    ]

