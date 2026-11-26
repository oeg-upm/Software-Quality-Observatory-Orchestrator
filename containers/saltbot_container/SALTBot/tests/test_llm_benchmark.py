import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llm_benchmark import llm_desc_requests as benchmark


def response(text=' Short\n summary. '):
    return SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {'response': text, 'load_duration': 1_000_000_000,
                      'eval_duration': 2_000_000_000, 'eval_count': 20},
    )


@pytest.fixture
def setup_benchmark(monkeypatch, tmp_path):
    monkeypatch.setattr(benchmark, 'MODELS', ['qwen3:0.6b', 'gemma3:1b'], raising=False)
    monkeypatch.setattr(benchmark, 'DESCRIPTIONS', {'example/one': 'a' * 300, 'example/two': 'b' * 400}, raising=False)
    monkeypatch.setattr(benchmark, 'RESULTS_DIR', tmp_path, raising=False)
    post = Mock(return_value=response())
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(requests.sessions.Session, 'request',
                        Mock(side_effect=AssertionError('NETWORK FORBIDDEN')))
    return post


def test_writes_a_txt_per_model_and_continues_after_invalid_output_and_http_error(setup_benchmark):
    setup_benchmark.side_effect = [response(), response('x' * 250),
                                  requests.HTTPError('404 model not found'), response('Valid summary')]
    directory = benchmark.main()
    assert sorted(p.name for p in directory.iterdir()) == ['gemma3_1b.txt', 'qwen3_0.6b.txt']
    qwen = (directory / 'qwen3_0.6b.txt').read_text(encoding='utf-8')
    gemma = (directory / 'gemma3_1b.txt').read_text(encoding='utf-8')
    assert 'REPOSITORY: https://github.com/example/one' in qwen
    assert 'REPOSITORY: https://github.com/example/two' in qwen
    assert 'DESCRIPTION:\nShort summary.' in qwen
    assert 'CHARACTERS: 250' in qwen and 'VALID_LENGTH: false' in qwen
    assert 'LOAD_SECONDS: 1.0' in qwen and 'TOKENS_PER_SECOND: 10.0' in qwen
    assert 'HTTPError: 404 model not found' in gemma and 'Valid summary' in gemma
    assert setup_benchmark.call_count == 4


def test_same_generation_settings_and_nonstreaming_request_for_each_pair(setup_benchmark):
    benchmark.main()
    for call, model, description in zip(setup_benchmark.call_args_list,
                                        ['qwen3:0.6b'] * 2 + ['gemma3:1b'] * 2,
                                        ['a' * 300, 'b' * 400] * 2):
        assert call.args[0] == 'http://localhost:11434/api/generate'
        payload = call.kwargs['json']
        assert payload['model'] == model and payload['prompt'] == description
        assert payload['stream'] is False and payload['think'] is False
        assert payload['options'] == {'temperature': 0, 'num_predict': 128}
        assert call.kwargs['timeout'] == (5, 180)


@pytest.mark.parametrize('payload', [[], {}, {'response': None}, {'response': 123}])
def test_invalid_json_shape_is_saved_as_error_without_stopping(payload, setup_benchmark):
    bad = response()
    bad.json = lambda: payload
    setup_benchmark.side_effect = [bad, response(), response(), response()]
    directory = benchmark.main()
    content = (directory / 'qwen3_0.6b.txt').read_text(encoding='utf-8')
    assert 'ValueError:' in content and 'Short summary.' in content
    assert setup_benchmark.call_count == 4


def test_timeouts_are_recorded_and_later_cases_continue(setup_benchmark):
    setup_benchmark.side_effect = [requests.Timeout('read timed out'), response(), response(), response()]
    directory = benchmark.main()
    assert 'Timeout: read timed out' in (directory / 'qwen3_0.6b.txt').read_text(encoding='utf-8')
    assert setup_benchmark.call_count == 4


def test_repeated_runs_do_not_overwrite_previous_results(setup_benchmark):
    first = benchmark.main()
    contents = (first / 'qwen3_0.6b.txt').read_bytes()
    second = benchmark.main()
    assert first != second
    assert (first / 'qwen3_0.6b.txt').read_bytes() == contents
