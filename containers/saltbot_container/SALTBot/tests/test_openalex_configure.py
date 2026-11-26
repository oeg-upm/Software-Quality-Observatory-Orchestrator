import sys
from pathlib import Path

from click.testing import CliRunner
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import SALTbot.SALTbot as app


@pytest.mark.parametrize('environment_key,typed_key,expected', [
    ('', 'typed-example-key', 'typed-example-key'),
    ('environment-example-key', '', 'environment-example-key'),
    ('', '', ''),
])
def test_configure_accepts_optional_openalex_key_without_echoing_it(
        monkeypatch, tmp_path, environment_key, typed_key, expected):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('OPENALEX_API_KEY', environment_key)
    captured = {}
    monkeypatch.setattr(app.yaml, 'dump', lambda data, stream: captured.update(data))
    answers = ['test-user', 'test-password', '', typed_key, '', '', '']
    result = CliRunner().invoke(app.cli, ['configure'], input='\n'.join(answers) + '\n')
    assert result.exit_code == 0, result.output
    assert captured['OPENALEX_API_KEY'] == expected
    if expected:
        assert expected not in result.output
