import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from SALTbot import SPARQLQuerys


class FakeResponse:
	def __init__(self, status_code=200, headers=None):
		self.status_code = status_code
		self.headers = headers or {}
		self.text = "HTTP error response" if status_code >= 400 else ""

	def raise_for_status(self):
		if self.status_code >= 400:
			raise SPARQLQuerys.requests.HTTPError("error")

	def json(self):
		return {"results": {"bindings": []}}


def test_sparql_queries_use_five_minute_timeout():
	assert SPARQLQuerys.DEFAULT_TIMEOUT == 300


def test_sparql_queries_wait_three_seconds_between_requests():
	assert SPARQLQuerys.SPARQL_REQUEST_INTERVAL == 3.0


def test_sparql_rate_limit_waits_with_simple_sleep(monkeypatch):
	sleeps = []
	monkeypatch.setattr(SPARQLQuerys.time, "sleep", sleeps.append)

	SPARQLQuerys.waitForSparqlRateLimit()

	assert sleeps == [SPARQLQuerys.SPARQL_REQUEST_INTERVAL]


def test_sparql_retry_after_waits_when_error_response_has_header(monkeypatch):
	sleeps = []
	monkeypatch.setattr(SPARQLQuerys.time, "sleep", sleeps.append)

	waited = SPARQLQuerys.waitForSparqlRetryAfter(
		FakeResponse(status_code=429, headers={"Retry-After": "7"})
	)

	assert waited is True
	assert sleeps == [7.0]


def test_sparql_retry_after_does_not_wait_without_error(monkeypatch):
	sleeps = []
	monkeypatch.setattr(SPARQLQuerys.time, "sleep", sleeps.append)

	waited = SPARQLQuerys.waitForSparqlRetryAfter(
		FakeResponse(status_code=200, headers={"Retry-After": "7"})
	)

	assert waited is False
	assert sleeps == []


def test_execute_select_retries_retry_after_errors(monkeypatch):
	sleeps = []
	rate_limit_waits = []
	responses = [
		FakeResponse(status_code=429, headers={"Retry-After": "11"}),
		FakeResponse(status_code=429, headers={"Retry-After": "13"}),
		FakeResponse(status_code=200),
	]

	monkeypatch.setattr(SPARQLQuerys, "waitForSparqlRateLimit", lambda: rate_limit_waits.append("wait"))
	monkeypatch.setattr(SPARQLQuerys.time, "sleep", sleeps.append)
	monkeypatch.setattr(
		SPARQLQuerys.requests,
		"get",
		lambda *args, **kwargs: responses.pop(0),
	)

	bindings = SPARQLQuerys.executeSelect("SELECT * WHERE {}")

	assert bindings == []
	assert sleeps == [11.0, 13.0]
	assert rate_limit_waits == ["wait", "wait", "wait"]


def test_execute_select_raises_after_three_retry_after_retries(monkeypatch):
	sleeps = []
	rate_limit_waits = []
	responses = [
		FakeResponse(status_code=429, headers={"Retry-After": "1"}),
		FakeResponse(status_code=429, headers={"Retry-After": "2"}),
		FakeResponse(status_code=429, headers={"Retry-After": "3"}),
		FakeResponse(status_code=429, headers={"Retry-After": "4"}),
	]

	monkeypatch.setattr(SPARQLQuerys, "waitForSparqlRateLimit", lambda: rate_limit_waits.append("wait"))
	monkeypatch.setattr(SPARQLQuerys.time, "sleep", sleeps.append)
	monkeypatch.setattr(
		SPARQLQuerys.requests,
		"get",
		lambda *args, **kwargs: responses.pop(0),
	)

	with pytest.raises(SPARQLQuerys.requests.HTTPError):
		SPARQLQuerys.executeSelect("SELECT * WHERE {}")

	assert sleeps == [1.0, 2.0, 3.0]
	assert rate_limit_waits == ["wait", "wait", "wait", "wait"]


@pytest.mark.parametrize("status_code", [502, 503, 504])
def test_execute_select_retries_gateway_errors_after_rate_limit(monkeypatch, status_code):
	events = []
	requests = []
	responses = [FakeResponse(status_code=status_code), FakeResponse()]
	query = "SELECT ?item WHERE { ?item wdt:P31 wd:Q7397 }"

	def fake_get(endpoint, **kwargs):
		requests.append((endpoint, kwargs))
		events.append("request")
		return responses.pop(0)

	monkeypatch.setattr(SPARQLQuerys.time, "sleep", lambda delay: events.append(delay))
	monkeypatch.setattr(SPARQLQuerys.requests, "get", fake_get)

	assert SPARQLQuerys.executeSelect(query) == []
	assert events == [3.0, "request", 5, 3.0, "request"]
	assert len(requests) == 2
	assert requests[0] == requests[1]
	assert requests[0][1]["params"]["query"] == query


@pytest.mark.parametrize("status_code", [502, 503, 504])
def test_execute_select_stops_after_three_gateway_retries(monkeypatch, status_code):
	sleeps = []
	requests = []

	def fake_get(*args, **kwargs):
		requests.append(True)
		return FakeResponse(status_code=status_code)

	monkeypatch.setattr(SPARQLQuerys.time, "sleep", sleeps.append)
	monkeypatch.setattr(SPARQLQuerys.requests, "get", fake_get)

	with pytest.raises(SPARQLQuerys.requests.HTTPError):
		SPARQLQuerys.executeSelect("SELECT * WHERE {}")

	assert len(requests) == 4
	assert sleeps == [3.0, 5, 3.0, 10, 3.0, 20, 3.0]


def test_execute_select_gateway_retry_prefers_retry_after(monkeypatch):
	sleeps = []
	responses = [FakeResponse(status_code=502, headers={"Retry-After": "7"}), FakeResponse()]
	monkeypatch.setattr(SPARQLQuerys.time, "sleep", sleeps.append)
	monkeypatch.setattr(SPARQLQuerys.requests, "get", lambda *args, **kwargs: responses.pop(0))

	assert SPARQLQuerys.executeSelect("SELECT * WHERE {}") == []
	assert sleeps == [3.0, 7.0, 3.0]


def test_execute_select_gateway_retry_ignores_invalid_retry_after(monkeypatch):
	sleeps = []
	responses = [FakeResponse(status_code=503, headers={"Retry-After": "invalid"}), FakeResponse()]
	monkeypatch.setattr(SPARQLQuerys.time, "sleep", sleeps.append)
	monkeypatch.setattr(SPARQLQuerys.requests, "get", lambda *args, **kwargs: responses.pop(0))

	assert SPARQLQuerys.executeSelect("SELECT * WHERE {}") == []
	assert sleeps == [3.0, 5, 3.0]


def test_execute_select_gateway_and_retry_after_share_retry_limit(monkeypatch):
	sleeps = []
	responses = [
		FakeResponse(status_code=502),
		FakeResponse(status_code=429, headers={"Retry-After": "7"}),
		FakeResponse(status_code=503),
		FakeResponse(status_code=504),
	]
	monkeypatch.setattr(SPARQLQuerys.time, "sleep", sleeps.append)
	monkeypatch.setattr(SPARQLQuerys.requests, "get", lambda *args, **kwargs: responses.pop(0))

	with pytest.raises(SPARQLQuerys.requests.HTTPError):
		SPARQLQuerys.executeSelect("SELECT * WHERE {}")

	assert responses == []
	assert sleeps == [3.0, 5, 3.0, 7.0, 3.0, 20, 3.0]


def test_execute_select_does_not_retry_bad_request_without_retry_after(monkeypatch):
	sleeps = []
	requests = []

	def fake_get(*args, **kwargs):
		requests.append(True)
		return FakeResponse(status_code=400)

	monkeypatch.setattr(SPARQLQuerys.time, "sleep", sleeps.append)
	monkeypatch.setattr(SPARQLQuerys.requests, "get", fake_get)

	with pytest.raises(SPARQLQuerys.requests.HTTPError):
		SPARQLQuerys.executeSelect("SELECT * WHERE {}")

	assert len(requests) == 1
	assert sleeps == [3.0]
