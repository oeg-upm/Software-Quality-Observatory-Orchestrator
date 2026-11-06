import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import SALTbot.SPARQLQuerys as sparql


class FakeResponse:
    status_code = 502
    headers = {
        "Server": "test-gateway",
        "X-Request-Id": "req-123",
    }
    text = "Bad Gateway from test endpoint"

    def raise_for_status(self):
        raise requests.exceptions.HTTPError("502 Server Error: Bad Gateway")


def test_execute_select_prints_http_error_and_response_stderr(monkeypatch, capsys):
    monkeypatch.setattr(sparql, "waitForSparqlRateLimit", lambda: None)
    monkeypatch.setattr(sparql.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(sparql.requests, "get", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(requests.exceptions.HTTPError):
        sparql.executeSelect("SELECT * WHERE {}", endpoint="https://example.test/sparql")

    captured = capsys.readouterr()

    assert "SALTbot SPARQL HTTPError:" in captured.err
    assert "502 Server Error: Bad Gateway" in captured.err
    assert "SALTbot SPARQL endpoint: https://example.test/sparql" in captured.err
    assert "SALTbot SPARQL response headers:" in captured.err
    assert "X-Request-Id" in captured.err
    assert "req-123" in captured.err
    assert "SALTbot SPARQL response stderr:" in captured.err
    assert "Bad Gateway from test endpoint" in captured.err
