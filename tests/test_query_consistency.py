from app.services.query_consistency import categories_for_term, check_query_campaign_consistency


def test_ambiguous_term_includes_food_and_beauty() -> None:
    assert categories_for_term("成分") == {"美妆个护", "食品饮料"}


def test_warns_for_beauty_term_in_food_campaign() -> None:
    warnings = check_query_campaign_consistency(
        ["成分", "敏感肌"],
        campaign_category="食品饮料",
        required_topics=["探店", "配料表"],
        tone_tags=["硬核测评"],
    )
    assert len(warnings) == 1
    assert warnings[0].conflicting_terms == ["敏感肌"]
    assert warnings[0].detected_categories == ["美妆个护"]
    assert warnings[0].suggested_query == "食品饮料 探店 配料表 硬核测评"


def test_does_not_warn_for_matching_food_terms() -> None:
    warnings = check_query_campaign_consistency(
        ["配料表", "低糖", "成分"],
        campaign_category="食品饮料",
        required_topics=["探店"],
        tone_tags=["硬核测评"],
    )
    assert warnings == []


def test_does_not_warn_without_known_category_signal() -> None:
    warnings = check_query_campaign_consistency(
        ["高品质", "年轻人"],
        campaign_category="食品饮料",
        required_topics=["探店"],
        tone_tags=["硬核测评"],
    )
    assert warnings == []
