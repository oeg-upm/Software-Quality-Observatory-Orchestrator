import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from SALTbot import llm_requests
from SALTbot import SALTbotStatementDefiner as definer
from SALTbot import SALTbotBibliography as bibliography
from SALTbot import SALTbotHandler as handler


@pytest.fixture(autouse=True)
def ollama(monkeypatch):
    monkeypatch.setenv('LLM_MODEL', 'test-model')
    monkeypatch.setenv('OLLAMA_HOST', 'http://ollama:11434/')
    post = Mock(return_value=SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {'response': ' Short\n summary. '}))
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(requests.sessions.Session, 'request',
                        Mock(side_effect=AssertionError('NETWORK FORBIDDEN')))
    return post


def test_long_description_uses_nonstreaming_ollama_summary(ollama):
    description = 'Long description. ' * 30
    assert definer.getDescription({'description': [{'result': {'value': description}}]}, 'Fallback') == 'Short summary.'
    ollama.assert_called_once()
    args, kwargs = ollama.call_args
    assert args == ('http://ollama:11434/api/generate',)
    assert kwargs['json']['model'] == 'test-model'
    assert kwargs['json']['prompt'] == description.strip()
    assert kwargs['json']['stream'] is False
    assert kwargs['json']['think'] is False
    assert kwargs['timeout'] == (5, 180)


@pytest.mark.parametrize('value', ['Short description', 'x' * 250])
def test_short_or_exactly_250_character_description_does_not_call_ollama(value, ollama):
    assert definer.getDescription({'description': {'result': {'value': value}}}, 'Fallback') == value
    ollama.assert_not_called()


def test_missing_description_does_not_call_ollama(ollama):
    assert definer.getDescription({}, 'Fallback') == 'Fallback'
    ollama.assert_not_called()


@pytest.mark.parametrize('length', [249, 250])
def test_software_summary_within_250_characters_is_accepted(length, ollama):
    ollama.return_value.json = lambda: {'response': 'x' * length}
    assert llm_requests.fallback_desc_llm('Long description', 'Fallback') == 'x' * length


@pytest.mark.parametrize('payload', [
    {'response': ''}, {'response': '   '},
    {'response': 'x' * 251}, {'response': None}, {'response': ['invalid']}, {}, [],
])
def test_invalid_summaries_keep_fallback_and_log_reason(payload, ollama, capsys):
    ollama.return_value.json = lambda: payload
    assert llm_requests.fallback_desc_llm('Long description', 'Fallback') == 'Fallback'
    assert 'SALTbot Ollama' in capsys.readouterr().err


@pytest.mark.parametrize('error', [requests.Timeout('timeout'),
                                       requests.ConnectionError('connection refused'),
                                       requests.HTTPError('503 Service Unavailable'),
                                       ValueError('Invalid JSON')])
def test_ollama_errors_keep_fallback(error, ollama, capsys):
    ollama.side_effect = error
    assert llm_requests.fallback_desc_llm('Long description', 'x' * 300) == 'x' * 250
    assert type(error).__name__ in capsys.readouterr().err


def test_missing_model_keeps_fallback_without_request(monkeypatch, ollama):
    monkeypatch.delenv('LLM_MODEL')
    assert llm_requests.fallback_desc_llm('Long description', 'Fallback') == 'Fallback'
    ollama.assert_not_called()


def test_http_error_is_checked_before_json(ollama):
    ollama.return_value.raise_for_status = Mock(side_effect=requests.HTTPError('500'))
    ollama.return_value.json = Mock(side_effect=AssertionError('Must check HTTP status first'))
    assert llm_requests.fallback_desc_llm('Long description', 'Fallback') == 'Fallback'


def test_default_ollama_host(monkeypatch, ollama):
    monkeypatch.delenv('OLLAMA_HOST')
    assert llm_requests.fallback_desc_llm('Long description', 'Fallback') == 'Short summary.'
    assert ollama.call_args.args[0] == 'http://ollama:11434/api/generate'


@pytest.mark.parametrize('index,expected', [
    ({'Research': [2, 0], 'supports': [1]}, 'Research supports Research'),
    (None, ''), ({}, ''), ([], ''), ({'word': None}, ''),
    ({'word': [-1]}, ''), ({'word': ['0']}, ''), ({'word': [True]}, ''),
    ({'word': [1]}, ''), ({'a': [0], 'b': [0]}, ''),
])
def test_article_abstract_reconstruction(index, expected):
    assert bibliography.getAbstract({'abstract_inverted_index': index}) == expected


@pytest.mark.parametrize('summary,valid', [
    ('x' * 199, True), ('x' * 200, True), ('x' * 250, True), ('x' * 251, False),
    ('word ' * 20, True), ('word ' * 21, True), ('word ' * 40, True), ('   ', False),
])
def test_article_summary_limits(summary, valid, ollama):
    ollama.return_value.json = lambda: {'response': summary}
    result = llm_requests.article_desc_llm('Research abstract.', 'Article fallback')
    assert result == (' '.join(summary.split()) if valid else 'Article fallback')
    system = ollama.call_args.kwargs['json']['system']
    assert 'abstract' in system and '20 words' in system and '200 characters' in system


@pytest.mark.parametrize('abstract', ['', None])
def test_missing_abstract_skips_ollama(abstract, ollama):
    result = llm_requests.article_desc_llm(abstract, 'scientific article ' + 'long ' * 60)
    assert result.startswith('scientific article')
    assert len(result) == 250
    ollama.assert_not_called()


@pytest.mark.parametrize('error', [requests.Timeout('timeout'), requests.HTTPError('503'),
                                       ValueError('Invalid JSON')])
def test_article_request_failure_uses_fallback(error, ollama):
    ollama.side_effect = error
    assert llm_requests.article_desc_llm('Abstract.', 'Article fallback') == 'Article fallback'


@pytest.mark.parametrize('payload', [{}, {'response': None}, {'response': ['invalid']}, []])
def test_invalid_article_response_uses_fallback(payload, ollama):
    ollama.return_value.json = lambda: payload
    assert llm_requests.article_desc_llm('Abstract.', 'Article fallback') == 'Article fallback'


def test_article_without_model_uses_fallback(monkeypatch, ollama):
    monkeypatch.delenv('LLM_MODEL')
    assert llm_requests.article_desc_llm('Abstract.', 'Article fallback') == 'Article fallback'
    ollama.assert_not_called()


def test_article_uses_abstract_instead_of_somef_description(ollama):
    ops = definer.createArticleOperations(
        {'name': [{'result': {'value': 'software'}}],
         'description': [{'result': {'value': 'Software description.'}}]},
        {'instance of': 'P31', 'scholarly article': 'Q13442814'}, {},
        {'title': 'Paper', 'abstract_inverted_index': {'Research': [0], 'abstract.': [1]}}, None)
    assert ops[0][1]['DESCRIPTION'] == 'Short summary.'
    assert ollama.call_args.kwargs['json']['prompt'] == 'Research abstract.'
    ollama.assert_called_once()


def test_article_without_abstract_ignores_somef_description(ollama):
    ops = definer.createArticleOperations(
        {'name': [{'result': {'value': 'software'}}],
         'description': [{'result': {'value': 'Software description.'}}]},
        {'instance of': 'P31', 'scholarly article': 'Q13442814'}, {},
        {'title': 'CEUR paper', 'url': 'https://ceur-ws.org/Vol-1/paper1.pdf'}, None)
    assert ops[0][1]['DESCRIPTION'] == 'scientific article associated with the software software'
    ollama.assert_not_called()


def test_shared_article_is_summarized_once_and_linked_to_both_repositories(ollama):
    work = {'title': 'Shared paper', 'doi': '10.1234/shared',
            'abstract_inverted_index': {'Shared': [0], 'abstract.': [1]}}
    registry, operations = {}, []
    for name in ('first', 'second'):
        repo = 'https://github.com/example/' + name
        info = {'name': [{'result': {'value': name}}],
                'description': [{'result': {'value': 'Short software description'}}],
                'code_repository': [{'result': {'value': repo}}]}
        selected = handler.selectOpenAlexArticle(info, work, registry)
        results = {repo: {'repo-article': ['Shared paper'], 'article': None, 'software': None,
                          'article-software-link': False, 'software-article-link': False}}
        operations.extend(definer.defineOperations(
            info, {}, {}, [True, [False, ''], [False, '']],
            handler.DEFAULT_WIKIDATA_MANDATORY_NODES, {}, results, selected, {}, None))
    ollama.assert_called_once()
    assert sum(k == 'create' and v['LABEL'] == 'Shared paper' for k, v in operations) == 1
    for name in ('first', 'second'):
        assert any(k == 'statement' and v['s'] == name and v['p'] == 'P1343'
                   and v['o'] == 'Shared paper' for k, v in operations)
        assert any(k == 'statement' and v['s'] == 'Shared paper' and v['p'] == 'P921'
                   and v['o'] == name for k, v in operations)
