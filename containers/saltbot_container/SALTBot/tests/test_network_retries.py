import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from SALTbot import SALTbotHandler, SALTbotSearcher as searcher, SPARQLQuerys as sparql


def response(status=200, payload=None, headers=None):
    result = requests.Response()
    result.status_code = status
    result.url = 'https://api.openalex.org/works'
    result.headers.update(headers or {})
    result._content = json.dumps(payload if payload is not None else {'results': []}).encode()
    return result


def stub_requests(monkeypatch, outcomes):
    outcomes = iter(outcomes)
    calls, sleeps = [], []

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(requests, 'get', get)
    monkeypatch.setattr(searcher.time, 'sleep', sleeps.append)
    return calls, sleeps


@pytest.mark.parametrize('lookup,value', [(searcher.queryOpenAlex, 'Test article'), (searcher.queryOpenAlexByDoi, '10.1234/test')])
def test_openalex_key_is_sent_in_header_on_every_retry_and_corpus(monkeypatch, lookup, value):
    work = {'id': 'https://openalex.org/W1', 'type': 'article'}
    calls, _ = stub_requests(monkeypatch, [response(503), response(), response(payload={'results': [work]})])
    assert lookup(value, openalex_api_key='example-openalex-key') == work
    assert [call[1]['params']['corpus'] for call in calls] == ['core', 'core', 'all']
    for args, kwargs in calls:
        assert kwargs['headers'] == {'Authorization': 'Bearer example-openalex-key'}
        assert 'api_key' not in kwargs['params']
        assert 'example-openalex-key' not in args[0]


def test_openalex_remains_anonymous_without_key(monkeypatch):
    calls, _ = stub_requests(monkeypatch, [response(), response()])
    assert searcher.queryOpenAlex('Test article') is None
    assert all('Authorization' not in kwargs.get('headers', {}) for _, kwargs in calls)


@pytest.mark.parametrize('error_type', [requests.exceptions.SSLError, requests.ConnectionError, requests.Timeout])
def test_sparql_retries_transport_errors_with_rate_limit(monkeypatch, capsys, error_type):
    calls, sleeps = stub_requests(monkeypatch, [error_type('unexpected EOF')] * 3 + [response(payload={'results': {'bindings': []}})])
    assert sparql.executeSelect('SELECT * WHERE {}') == []
    assert len(calls) == 4 and all(call == calls[0] for call in calls)
    assert sleeps == [5, 5, 5, 10, 5, 20, 5]
    assert error_type.__name__ in capsys.readouterr().err


def test_sparql_raises_original_ssl_error_after_three_retries(monkeypatch):
    error = requests.exceptions.SSLError('unexpected EOF')
    calls, sleeps = stub_requests(monkeypatch, [error] * 4)
    with pytest.raises(requests.exceptions.SSLError) as caught:
        sparql.executeSelect('SELECT * WHERE {}')
    assert caught.value is error
    assert len(calls) == 4
    assert sleeps == [5, 5, 5, 10, 5, 20, 5]


def test_sparql_transport_and_http_errors_share_retry_budget(monkeypatch):
    calls, sleeps = stub_requests(monkeypatch, [requests.exceptions.SSLError('EOF'), response(503), requests.Timeout('slow'), response(504)])
    with pytest.raises(requests.HTTPError):
        sparql.executeSelect('SELECT * WHERE {}')
    assert len(calls) == 4 and sleeps == [5, 5, 5, 10, 5, 20, 5]


@pytest.mark.parametrize('lookup,value', [(searcher.queryOpenAlex, 'Test article'), (searcher.queryOpenAlexByDoi, '10.1234/test')])
def test_openalex_recovers_after_three_503_errors(monkeypatch, lookup, value):
    work = {'id': 'https://openalex.org/W1', 'type': 'article', 'doi': 'https://doi.org/10.1234/test'}
    calls, sleeps = stub_requests(monkeypatch, [response(503, {'error': 'Search temporarily unavailable'}) for _ in range(3)] + [response(payload={'results': [work]})])
    assert lookup(value) == work
    assert len(calls) == 4 and all(call == calls[0] for call in calls)
    assert sleeps == [5, 10, 20]


@pytest.mark.parametrize('status', [429, 502, 503, 504])
def test_openalex_service_failure_is_not_an_empty_search(monkeypatch, status):
    calls, sleeps = stub_requests(monkeypatch, [response(status, {'error': 'Service unavailable'}) for _ in range(4)])
    with pytest.raises(requests.HTTPError):
        searcher.queryOpenAlex('Test article')
    assert len(calls) == 4 and sleeps == [5, 10, 20]
    assert all(call[1]['params']['corpus'] == 'core' for call in calls)


@pytest.mark.parametrize('header,delay', [('7', 7), ('invalid', 5), ('-1', 5)])
def test_openalex_prefers_valid_retry_after(monkeypatch, header, delay):
    _, sleeps = stub_requests(monkeypatch, [response(503, headers={'Retry-After': header}), response(), response()])
    assert searcher.queryOpenAlex('Test article') is None
    assert sleeps == [delay]


def test_openalex_accepts_retry_after_http_date(monkeypatch):
    monkeypatch.setattr(searcher.time, 'time', lambda: 0)
    _, sleeps = stub_requests(monkeypatch, [
        response(503, headers={'Retry-After': 'Thu, 01 Jan 1970 00:00:09 GMT'}),
        response(), response(),
    ])
    assert searcher.queryOpenAlex('Test article') is None
    assert sleeps == [9]


def test_openalex_retries_all_corpus_only_after_valid_empty_core(monkeypatch):
    work = {'id': 'https://openalex.org/W1', 'type': 'article'}
    calls, sleeps = stub_requests(monkeypatch, [response(), response(503), response(payload={'results': [work]})])
    assert searcher.queryOpenAlex('Test article') == work
    assert [call[1]['params']['corpus'] for call in calls] == ['core', 'all', 'all']
    assert sleeps == [5]


def test_openalex_transport_and_http_errors_share_retry_budget(monkeypatch):
    error = requests.exceptions.SSLError('unexpected EOF')
    calls, sleeps = stub_requests(monkeypatch, [error, response(503), requests.Timeout('slow'), error])
    with pytest.raises(requests.exceptions.SSLError) as caught:
        searcher.queryOpenAlex('Test article')
    assert caught.value is error
    assert len(calls) == 4 and sleeps == [5, 10, 20]


def test_openalex_rejects_non_retryable_http_errors(monkeypatch):
    calls, sleeps = stub_requests(monkeypatch, [response(400)])
    with pytest.raises(requests.HTTPError):
        searcher.queryOpenAlex('Test article')
    assert len(calls) == 1 and sleeps == []


def test_openalex_invalid_json_is_not_an_empty_search(monkeypatch):
    malformed = response()
    malformed._content = b'not JSON'
    calls, _ = stub_requests(monkeypatch, [malformed])
    with pytest.raises(ValueError):
        searcher.queryOpenAlex('Test article')
    assert len(calls) == 1


def test_openalex_outage_does_not_activate_citation_creation(monkeypatch):
    calls, _ = stub_requests(monkeypatch, [response(503) for _ in range(4)])
    monkeypatch.setattr(searcher, 'parseTitles', lambda info: (['Test article'], {}, {}))
    monkeypatch.setattr(searcher, 'parseCitationCandidates', lambda info: [])
    for name in ['getEntitiesByName', 'getEntitiesByRepositoryUrl']:
        monkeypatch.setattr(SALTbotHandler, name, lambda *args: {})
    monkeypatch.setattr(SALTbotHandler, 'selectCitationArticle', lambda *args: pytest.fail('API failure must not activate citation fallback'))
    info = {'name': [{'result': {'value': 'test'}}],
            'code_repository': [{'result': {'value': 'https://github.com/example/test'}}]}
    with pytest.raises(requests.HTTPError):
        SALTbotHandler.SALTbot(None, info,
            {'scholarly article': 'Q13442814', 'software category': 'Q17155032'},
            {'code repository': 'P1324'}, True, {},
            configData={'OPENALEX_API_KEY': 'example-openalex-key'})
    assert all(kwargs['headers']['Authorization'] == 'Bearer example-openalex-key'
               for _, kwargs in calls)
