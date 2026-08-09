from app.tools import parse_extract, parse_search_title


def test_parse_search_title_returns_first_result_title():
    response_json = {"query": {"search": [{"title": "Ada Lovelace"}, {"title": "Ada"}]}}

    assert parse_search_title(response_json) == "Ada Lovelace"


def test_parse_search_title_returns_none_when_no_results():
    response_json = {"query": {"search": []}}

    assert parse_search_title(response_json) is None


def test_parse_extract_returns_first_nonempty_extract():
    response_json = {
        "query": {"pages": {"12345": {"extract": "Ada Lovelace was a mathematician."}}}
    }

    assert parse_extract(response_json) == "Ada Lovelace was a mathematician."


def test_parse_extract_returns_none_when_extract_is_blank():
    response_json = {"query": {"pages": {"-1": {"extract": ""}}}}

    assert parse_extract(response_json) is None
