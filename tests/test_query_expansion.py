from app.services.query_expansion import expand_terms


def test_food_ingredient_expansion_is_category_aware() -> None:
    assert expand_terms(["成分"], "食品饮料") == {
        "成分": ["成分", "配料表", "原料", "配方", "营养成分"]
    }


def test_beauty_ingredient_expansion_differs_from_food() -> None:
    assert expand_terms(["成分"], "美妆个护") == {"成分": ["成分", "配方", "原料", "成分党"]}


def test_unknown_term_keeps_original() -> None:
    assert expand_terms(["年轻人"], "食品饮料") == {"年轻人": ["年轻人"]}

