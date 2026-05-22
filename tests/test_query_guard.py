import pytest

from prt_opensearch_mcp.query_guard import QueryRejectedError, validate_search_body


def test_search_body_caps_size():
    body = validate_search_body({"query": {"match_all": {}}}, max_size=10, hard_max=100)
    assert body["size"] == 10


def test_forbidden_script():
    with pytest.raises(QueryRejectedError):
        validate_search_body({"script": {}}, max_size=10, hard_max=100)
