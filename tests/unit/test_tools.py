from app.tools import (
    WIKIPEDIA_USER_AGENT,
    build_wikipedia_client,
    parse_extract,
    parse_search_title,
)


def test_parse_search_title_returns_first_result_title():
    response_json = {"query": {"search": [{"title": "Ada Lovelace"}, {"title": "Ada"}]}}

    assert parse_search_title(response_json) == "Ada Lovelace"


def test_parse_search_title_returns_none_when_no_results():
    response_json = {"query": {"search": []}}

    assert parse_search_title(response_json) is None


def test_parse_search_title_returns_none_when_title_key_missing():
    response_json = {"query": {"search": [{"snippet": "no title field here"}]}}

    assert parse_search_title(response_json) is None


def test_parse_extract_returns_first_nonempty_extract():
    response_json = {
        "query": {"pages": {"12345": {"extract": "Ada Lovelace was a mathematician."}}}
    }

    assert parse_extract(response_json) == "Ada Lovelace was a mathematician."


def test_parse_extract_returns_none_when_extract_is_blank():
    response_json = {"query": {"pages": {"-1": {"extract": ""}}}}

    assert parse_extract(response_json) is None


def test_build_wikipedia_client_sets_user_agent_header():
    client = build_wikipedia_client()
    try:
        assert client.headers["User-Agent"] == WIKIPEDIA_USER_AGENT
    finally:
        client.close()


def test_build_wikipedia_client_defaults_to_30_second_timeout():
    client = build_wikipedia_client()
    try:
        assert client.timeout.read == 30.0
    finally:
        client.close()
