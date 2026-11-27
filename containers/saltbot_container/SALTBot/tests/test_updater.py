import copy
import io
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from wikibaseintegrator.datatypes import Item
from wikibaseintegrator.models import Claims
from wikibaseintegrator.wbi_exceptions import MWApiError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from SALTbot import SALTbotUpdater as updater
from SALTbot import SALTbotStatementDefiner as definer
import SALTbot.SALTbot as cli


GUID = "Q123$D70A4206-C983-4905-90C1-7C49766FAB79"


def statement(subject="Q123", value="Q7397", datatype="Item", prop="P31", qualifiers=None):
    return ["statement", {"s": subject, "p": prop, "o": value,
                          "datatype": datatype, "qualifiers": qualifiers}]


def create(label="Example", description="scientific software"):
    return ["create", {"LABEL": label, "DESCRIPTION": description}]


def parse(operations):
    return updater.parseOperations([repr(op) + "\n" for op in operations])


def entity(qid="Q123", claims=None):
    item = SimpleNamespace(id=qid, labels=Mock(), descriptions=Mock(), claims=claims or Claims())
    item.write = Mock(return_value=item)
    return item


def wikibase(item=None):
    item = item or entity()
    return SimpleNamespace(item=SimpleNamespace(new=Mock(return_value=item), get=Mock(return_value=item)))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network access forbidden in updater tests")
    monkeypatch.setattr("requests.sessions.Session.request", blocked)
    monkeypatch.setattr(updater, "WIKIDATA_WRITE_INTERVAL", 0, raising=False)
    monkeypatch.setattr(updater, "_last_wikidata_write", None, raising=False)


@pytest.mark.parametrize("datatype,value,prop", [
    ("URL", "https://github.com/example/repo", "P1324"),
    ("Item", "Q7397", "P31"),
    ("ExternalID", "10.1234/EXAMPLE", "P356"),
])
def test_converts_qualifiers_and_preserves_operations(datatype, value, prop):
    operations = [create(), statement("Example", value, datatype, prop,
                  [["Q186055", "P8423"], ["Q82066181", "P10627"]])]
    original = copy.deepcopy(operations)
    item = entity()
    assert updater.updateChanges(parse(operations), wikibase(item)) == []
    claim = item.claims.get(prop)[0].get_json()
    assert claim["qualifiers"]["P8423"][0]["datavalue"]["value"]["id"] == "Q186055"
    assert claim["qualifiers"]["P10627"][0]["datavalue"]["value"]["id"] == "Q82066181"
    assert operations == original


@pytest.mark.parametrize("length", [250, 251])
def test_description_limit(length):
    info = {"description": [{"result": {"value": "x" * length}}]}
    assert definer.getDescription(info, "fallback") == ("x" * length if length == 250 else "fallback")


def test_description_fallback_is_bounded_and_does_not_choose_later_entries():
    info = {"description": [{"result": {"value": "x" * 251}}, {"result": {"value": "later"}}]}
    assert definer.getDescription(info, "fallback") == "fallback"
    assert len(definer.getDescription({}, "x" * 300)) == 250


def test_long_somef_description_generates_entity_specific_fallbacks():
    info = {"name": [{"result": {"value": "ya2ro"}}],
            "description": [{"result": {"value": "x" * 293}}]}
    software = definer.createSoftwareOperations(info, {"instance of": "P31", "software": "Q7397"}, {}, None, None, {"title": "Example article"})
    article = definer.createArticleOperations(info, {"instance of": "P31", "scholarly article": "Q13442814"}, {}, {"title": "Example article"}, None)
    assert software[0][1]["DESCRIPTION"] == "scientific software associated with the article Example article"
    assert article[0][1]["DESCRIPTION"] == "scientific article associated with the software ya2ro"


@pytest.mark.parametrize("length", [250, 251])
@pytest.mark.parametrize("descriptions", [[], [{"result": {"value": "x" * 293}}]])
def test_software_fallback_uses_title_only_when_complete_phrase_fits(length, descriptions):
    prefix = "scientific software associated with the article "
    title = "x" * (length - len(prefix))
    info = {"name": [{"result": {"value": "software"}}], "description": descriptions}
    operations = definer.createSoftwareOperations(info, {"instance of": "P31", "software": "Q7397"}, {}, None, None, {"title": title})
    expected = prefix + title if length == 250 else "scientific software associated with a research article"
    assert operations[0][1]["DESCRIPTION"] == expected


def test_software_fallback_is_generic_without_article_title():
    info = {"name": [{"result": {"value": "software"}}]}
    operations = definer.createSoftwareOperations(info, {"instance of": "P31", "software": "Q7397"}, {}, None, None)
    assert operations[0][1]["DESCRIPTION"] == "scientific software associated with a research article"


@pytest.mark.parametrize("operations", [
    [create(description="x" * 251)],
    [create(label="x" * 251)],
    [create(), create()],
    [["unknown", {}]],
    [statement(datatype="Unknown")],
    [statement(subject="missing")],
    [statement(value="future"), create("future")],
    [statement(prop="invalid")],
    [statement(qualifiers=[["not-a-qid", "P8423"]])],
    [statement(qualifiers={})],
    [["remove_statement", {"s": "Q456", "id": GUID}]],
])
def test_invalid_input_is_rejected(operations):
    with pytest.raises(cli.click.ClickException, match="line"):
        parse(operations)


def test_blank_lines_are_ignored():
    assert updater.parseOperations(["\n", repr(statement()), "  \n"]) == [statement()]


def test_failed_creation_leaves_dependents_pending_but_saves_independent_case(capsys):
    bad, good = entity("Q100"), entity("Q200")
    bad.write.side_effect = AssertionError()
    wbi = wikibase()
    wbi.item.new.side_effect = [bad, good]
    operations = parse([create("Bad"), statement("Bad"), create("Good"), statement("Good")])
    errors = updater.updateChanges(operations, wbi)
    assert len(errors) == 2
    assert "AssertionError" in errors[0]
    assert "PENDING" in errors[1]
    assert good.write.call_count == 2
    assert "AssertionError" in capsys.readouterr().err
    wbi.item.get.assert_not_called()


def test_failed_save_reports_every_pending_operation_and_exits_nonzero(capsys):
    item = entity()
    item.write.side_effect = RuntimeError("write rejected")
    operations = parse([statement(), statement(value="Q341")])
    with pytest.raises(cli.click.ClickException, match="2"):
        updater.executeOperations(operations, True, wikibase(item))
    output = capsys.readouterr()
    assert "PENDING" in output.err
    assert "RuntimeError" in output.err
    assert "Statement prepared" in output.out
    assert "Entity saved" not in output.out


def test_failed_qualifier_creation_marks_dependent_statement_pending():
    item = entity()
    item.write.side_effect = RuntimeError("creation failed")
    operations = parse([create("Qualifier"), statement(qualifiers=[["Qualifier", "P8423"]])])
    errors = updater.updateChanges(operations, wikibase(item))
    assert len(errors) == 2
    assert errors[1].startswith("PENDING")


def test_remove_statement_only_removes_matching_guid_and_groups_save():
    keep = Item(value="Q341", prop_nr="P31")
    keep.id = "Q123$F2C64DC9-1FCD-4D85-ABBF-1F59E385894D"
    remove = Item(value="Q7397", prop_nr="P31")
    remove.id = GUID
    item = entity(claims=Claims().add([keep, remove]))
    operation = ["remove_statement", {"s": "Q123", "id": GUID}]
    assert updater.updateChanges(parse([operation, operation]), wikibase(item)) == []
    assert remove.removed
    assert not keep.removed
    assert item.write.call_count == 1
    payload = item.claims.get_json()["P31"]
    assert "remove" in next(c for c in payload if c["id"] == GUID)
    assert "remove" not in next(c for c in payload if c["id"] == keep.id)


def test_already_absent_statement_does_not_write(capsys):
    item = entity()
    assert updater.updateChanges(parse([["remove_statement", {"s": "Q123", "id": GUID}]]), wikibase(item)) == []
    item.write.assert_not_called()
    assert "Already absent" in capsys.readouterr().out


def test_failed_removal_save_is_reported_as_pending():
    claim = Item(value="Q7397", prop_nr="P31")
    claim.id = GUID
    item = entity(claims=Claims().add(claim))
    item.write.side_effect = RuntimeError("remove failed")
    errors = updater.updateChanges(parse([["remove_statement", {"s": "Q123", "id": GUID}]]), wikibase(item))
    assert len(errors) == 1
    assert "PENDING" in errors[0] and GUID in errors[0]


def test_successful_save_is_reported_only_after_request_returns(capsys):
    item = entity()
    def write(**kwargs):
        assert "Entity saved" not in capsys.readouterr().out
        return item
    item.write.side_effect = write
    assert updater.updateChanges(parse([statement()]), wikibase(item)) == []
    assert "Entity saved: Q123" in capsys.readouterr().out


def test_wait_messages_have_context_and_filter_is_restored(monkeypatch, caplog):
    logger = logging.getLogger("wikibaseintegrator.wbi_helpers")
    filters = list(logger.filters)
    ticks = iter([10.0, 15.0])
    monkeypatch.setattr(updater.time, "monotonic", lambda: next(ticks))
    def request():
        logger.error("maxlag. sleeping for %d seconds", 60)
        raise RuntimeError("failed")
    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError):
        updater.runRequest("SAVE", "Q123", request)
    assert "SAVE Q123" in caplog.text
    assert "retry=1" in caplog.text and "elapsed=5.0s" in caplog.text
    assert "sleeping for 60 seconds" in caplog.text
    assert logger.filters == filters


@pytest.mark.parametrize("action", ["LOGIN", "LOAD", "CREATE", "SAVE"])
def test_mediawiki_error_details_are_logged_and_original_error_is_preserved(action, capsys):
    logger = logging.getLogger("wikibaseintegrator.wbi_helpers")
    filters = list(logger.filters)
    messages = [{"name": "abusefilter-warning", "parameters": ["Bulk item creation by new editor"],
                 "html": {"*": "Aviso de creación de entidades"}}]
    error = MWApiError({"code": "failed-save", "info": "The save has failed.", "messages": messages})
    with pytest.raises(MWApiError) as raised:
        updater.runRequest(action, "Example", Mock(side_effect=error))
    assert raised.value is error
    output = capsys.readouterr()
    assert f"[ERROR {action} Example] code: \"failed-save\"" in output.err
    assert 'info: "The save has failed."' in output.err
    assert 'messages:' in output.err and 'abusefilter-warning' in output.err
    assert "Aviso de creación de entidades" in output.err
    assert logger.filters == filters


def test_non_mediawiki_errors_keep_existing_handling(capsys):
    error = RuntimeError("write rejected")
    with pytest.raises(RuntimeError) as raised:
        updater.runRequest("SAVE", "Q123", Mock(side_effect=error))
    assert raised.value is error
    assert capsys.readouterr().err == ""


def test_write_requests_are_spaced_but_reads_are_not(monkeypatch, capsys):
    clock = [100.0]
    sleeps, calls = [], []
    monkeypatch.setattr(updater, "WIKIDATA_WRITE_INTERVAL", 15)
    monkeypatch.setattr(updater.time, "monotonic", lambda: clock[0])
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr(updater.time, "sleep", sleep)
    def request():
        calls.append(clock[0])
    updater.runRequest("CREATE", "First", request)
    clock[0] += 2
    updater.runRequest("LOAD", "Q123", request)
    updater.runRequest("LOGIN", "test-user", request)
    assert sleeps == []
    updater.runRequest("SAVE", "Q123", request)
    clock[0] += 20
    updater.runRequest("CREATE", "Second", request)
    assert sleeps == [13]
    assert calls == [100, 102, 102, 115, 135]
    assert "13.0s" in capsys.readouterr().out


def test_failed_write_also_respects_interval_before_next_attempt(monkeypatch):
    clock = [100.0]
    sleeps = []
    monkeypatch.setattr(updater, "WIKIDATA_WRITE_INTERVAL", 15)
    monkeypatch.setattr(updater.time, "monotonic", lambda: clock[0])
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr(updater.time, "sleep", sleep)
    with pytest.raises(RuntimeError):
        updater.runRequest("CREATE", "First", Mock(side_effect=RuntimeError("write rejected")))
    updater.runRequest("SAVE", "Q123", lambda: None)
    assert sleeps == [15]


def patch_cli(monkeypatch, wbi):
    original_open = open
    def fake_open(path, *args, **kwargs):
        if str(path) == "config.yaml":
            return io.StringIO('USER: offline-test\nPASSWORD: fake\nMEDIAWIKI_API_URL: ""\nSPARQL_ENDPOINT_URL: ""\nWIKIBASE_URL: ""\n')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr("builtins.open", fake_open)
    login = Mock()
    monkeypatch.setattr(cli.wbi_login, "Login", login)
    monkeypatch.setattr(cli, "WikibaseIntegrator", lambda login=None: wbi)
    return login


def test_cli_invalid_input_does_not_login(monkeypatch, tmp_path):
    login = patch_cli(monkeypatch, wikibase())
    source = tmp_path / "operations.txt"
    source.write_text(repr(create(description="x" * 251)), encoding="utf-8")
    result = CliRunner().invoke(cli.cli, ["update", "--file", str(source), "-a"])
    assert result.exit_code != 0
    login.assert_not_called()


@pytest.mark.parametrize("outcome", ["success", "cancel", "failure"])
def test_operations_dir_always_preserves_sources(monkeypatch, tmp_path, outcome):
    item = entity()
    if outcome == "failure":
        item.write.side_effect = RuntimeError("save failed")
    patch_cli(monkeypatch, wikibase(item))
    monkeypatch.setattr(cli, "FINAL_OPERATION_LIST", tmp_path / "merged.txt")
    source = tmp_path / "example_operations.txt"
    content = repr(statement()) + "\n"
    source.write_text(content, encoding="utf-8")
    args = ["update", "--operations-dir", str(tmp_path)]
    result = CliRunner().invoke(cli.cli, args, input="N\n" if outcome == "cancel" else "Y\n")
    assert result.exit_code == (1 if outcome == "failure" else 0), result.output
    assert source.read_text(encoding="utf-8") == content
    if outcome == "cancel":
        item.write.assert_not_called()
