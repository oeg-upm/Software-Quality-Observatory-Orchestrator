import json
import sys
from pathlib import Path

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import SALTbot.SALTbot as saltbot_module


def write_config(path):
	path.write_text(
		"\n".join(
			[
				"USER: test-user",
				"PASSWORD: test-password",
				"GITHUB_API_TOKEN: ''",
				"MEDIAWIKI_API_URL: ''",
				"SPARQL_ENDPOINT_URL: ''",
				"WIKIBASE_URL: ''",
			]
		),
		encoding="utf-8",
	)


def write_somef_json(path, repo_url):
	path.write_text(
		json.dumps(
			{
				"name": [{"result": {"value": Path(repo_url).name}}],
				"code_repository": [{"result": {"value": repo_url}}],
			}
		),
		encoding="utf-8",
	)


def patch_describe_dependencies(monkeypatch, seen_repos=None):
	def fake_saltbot(wbi, info, man_nodes, opt_nodes, auto, results, fallback_search, config_data, citation_article_registry=None):
		repo_url = info["code_repository"][0]["result"]["value"]
		if seen_repos is not None:
			seen_repos.append(repo_url)
		results[repo_url] = {"repo": repo_url}
		return [["statement", {"s": repo_url}]]

	monkeypatch.setattr(saltbot_module, "WikibaseIntegrator", lambda login=None: object())
	monkeypatch.setattr(saltbot_module.wbi_login, "Login", lambda user, password: object())
	monkeypatch.setattr(saltbot_module.SALTbotHandler, "getMandatoryNodes", lambda wbi, config: {})
	monkeypatch.setattr(saltbot_module.SALTbotHandler, "getOptionalNodes", lambda wbi, config: {})
	monkeypatch.setattr(saltbot_module.SALTbotHandler, "SALTbot", fake_saltbot)


def test_jsondir_processes_jsons_in_deterministic_order(monkeypatch):
	runner = CliRunner()
	seen_repos = []

	with runner.isolated_filesystem():
		write_config(Path("config.yaml"))
		input_dir = Path("metadata")
		input_dir.mkdir()
		write_somef_json(input_dir / "b.json", "https://github.com/example/b")
		write_somef_json(input_dir / "a.json", "https://github.com/example/a")
		patch_describe_dependencies(monkeypatch, seen_repos)

		result = runner.invoke(
			saltbot_module.cli,
			["describe", "--jsondir", str(input_dir), "--output-dir", "saltbot-output", "--auto"],
		)

	assert result.exit_code == 0, result.output
	assert seen_repos == ["https://github.com/example/a", "https://github.com/example/b"]


def test_jsondir_writes_results_once_without_accumulated_duplicates(monkeypatch):
	runner = CliRunner()

	with runner.isolated_filesystem():
		write_config(Path("config.yaml"))
		input_dir = Path("metadata")
		input_dir.mkdir()
		write_somef_json(input_dir / "first.json", "https://github.com/example/first")
		write_somef_json(input_dir / "second.json", "https://github.com/example/second")
		patch_describe_dependencies(monkeypatch)

		result = runner.invoke(
			saltbot_module.cli,
			["describe", "--jsondir", str(input_dir), "--output-dir", "saltbot-output", "--auto"],
		)

		results_lines = Path("saltbot-output/results.txt").read_text(encoding="utf-8").splitlines()
		operation_lines = Path("saltbot-output/operation_list.txt").read_text(encoding="utf-8").splitlines()

	assert result.exit_code == 0, result.output
	assert len(results_lines) == 2
	assert len(operation_lines) == 2
	assert results_lines[0].startswith("https://github.com/example/first:")
	assert results_lines[1].startswith("https://github.com/example/second:")


def test_output_dir_is_created_and_receives_describe_outputs(monkeypatch):
	runner = CliRunner()

	with runner.isolated_filesystem():
		write_config(Path("config.yaml"))
		input_file = Path("repo.json")
		write_somef_json(input_file, "https://github.com/example/repo")
		patch_describe_dependencies(monkeypatch)

		result = runner.invoke(
			saltbot_module.cli,
			["describe", "--jsonfile", str(input_file), "--output-dir", "nested/saltbot-output", "--auto"],
		)

		output_dir = Path("nested/saltbot-output")
		results_exists = (output_dir / "results.txt").exists()
		operations_exists = (output_dir / "operation_list.txt").exists()

	assert result.exit_code == 0, result.output
	assert results_exists
	assert operations_exists


def test_output_files_are_overwritten_between_runs(monkeypatch):
	runner = CliRunner()

	with runner.isolated_filesystem():
		write_config(Path("config.yaml"))
		first_dir = Path("first")
		first_dir.mkdir()
		write_somef_json(first_dir / "old.json", "https://github.com/example/old")
		second_dir = Path("second")
		second_dir.mkdir()
		write_somef_json(second_dir / "new.json", "https://github.com/example/new")
		patch_describe_dependencies(monkeypatch)

		first_result = runner.invoke(
			saltbot_module.cli,
			["describe", "--jsondir", str(first_dir), "--output-dir", "saltbot-output", "--auto"],
		)
		second_result = runner.invoke(
			saltbot_module.cli,
			["describe", "--jsondir", str(second_dir), "--output-dir", "saltbot-output", "--auto"],
		)

		results_text = Path("saltbot-output/results.txt").read_text(encoding="utf-8")
		operations_text = Path("saltbot-output/operation_list.txt").read_text(encoding="utf-8")

	assert first_result.exit_code == 0, first_result.output
	assert second_result.exit_code == 0, second_result.output
	assert "https://github.com/example/new" in results_text
	assert "https://github.com/example/new" in operations_text
	assert "https://github.com/example/old" not in results_text
	assert "https://github.com/example/old" not in operations_text


def test_jsonfile_mode_still_writes_outputs(monkeypatch):
	runner = CliRunner()

	with runner.isolated_filesystem():
		write_config(Path("config.yaml"))
		input_file = Path("repo.json")
		write_somef_json(input_file, "https://github.com/example/repo")
		patch_describe_dependencies(monkeypatch)

		result = runner.invoke(
			saltbot_module.cli,
			["describe", "--jsonfile", str(input_file), "--output-dir", "saltbot-output", "--auto"],
		)

		results_text = Path("saltbot-output/results.txt").read_text(encoding="utf-8")
		operations_text = Path("saltbot-output/operation_list.txt").read_text(encoding="utf-8")

	assert result.exit_code == 0, result.output
	assert "https://github.com/example/repo" in results_text
	assert "https://github.com/example/repo" in operations_text
