from app.services.keyword_retriever import build_snippet, parse_terms


def test_parse_terms_deduplicates_and_splits_chinese_punctuation() -> None:
    assert parse_terms("成分、敏感肌 成分，知性温柔") == ["成分", "敏感肌", "知性温柔"]


def test_build_snippet_centers_first_match() -> None:
    text = "前文" * 80 + "敏感肌实测" + "后文" * 80
    snippet = build_snippet(text, ["敏感肌"], radius=20)
    assert "敏感肌" in snippet
    assert snippet.startswith("…")
    assert snippet.endswith("…")
