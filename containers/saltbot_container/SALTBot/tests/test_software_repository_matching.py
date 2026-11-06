import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from SALTbot import SALTbotHandler


def test_saltbot_falls_back_to_unique_exact_software_name(monkeypatch):
    article = {
        "labels": {"en": {"value": "Example article"}},
        "claims": {},
    }
    named_software = {
        "labels": {"en": {"value": "Software"}},
        "claims": {
            "P1343": [
                {
                    "mainsnak": {
                        "datatype": "wikibase-item",
                        "property": "P1343",
                        "datavalue": {"value": {"id": "Q1"}},
                    }
                }
            ]
        },
    }
    name_search_targets = []
    repository_searches = []
    captured = {}

    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "parseTitles",
        lambda info: (["Example article"], {}, {}),
    )

    def fake_get_entities_by_name(name, target_class, *args):
        name_search_targets.append(target_class)
        if target_class == "Q13442814":
            return {"Q1": article}
        return {"Q2": named_software}

    def fake_get_entities_by_repository_url(repository_url, *args):
        repository_searches.append(repository_url)
        return {}

    def fake_define_operations(*args):
        captured["software_links"] = args[2]
        return ["operation"]

    monkeypatch.setattr(SALTbotHandler, "getEntitiesByName", fake_get_entities_by_name)
    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByRepositoryUrl",
        fake_get_entities_by_repository_url,
    )
    monkeypatch.setattr(SALTbotHandler, "getRelatedEntities", lambda *args: [])
    monkeypatch.setattr(
        SALTbotHandler.SALTbotStatementDefiner,
        "defineOperations",
        fake_define_operations,
    )

    repository_url = "https://github.com/example/software"
    operations = SALTbotHandler.SALTbot(
        None,
        {
            "name": [{"result": {"value": "software"}}],
            "code_repository": [{"result": {"value": repository_url}}],
        },
        {
            "scholarly article": "Q13442814",
            "software category": "Q17155032",
        },
        {"code repository": "P1324"},
        True,
        {},
    )

    assert operations == ["operation"]
    assert name_search_targets == ["Q13442814", "Q17155032"]
    assert repository_searches == [repository_url]
    assert captured["software_links"] == {"Q2": []}


def test_saltbot_does_not_accept_unique_software_name_without_evidence(monkeypatch):
    article = {
        "labels": {"en": {"value": "Example article"}},
        "claims": {},
    }
    unrelated_software = {
        "labels": {"en": {"value": "Software"}},
        "claims": {},
    }
    captured = {}

    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "parseTitles",
        lambda info: (["Example article"], {}, {}),
    )

    def fake_get_entities_by_name(name, target_class, *args):
        if target_class == "Q13442814":
            return {"Q1": article}
        return {"Q2": unrelated_software}

    monkeypatch.setattr(SALTbotHandler, "getEntitiesByName", fake_get_entities_by_name)
    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByRepositoryUrl",
        lambda *args: {},
    )
    monkeypatch.setattr(SALTbotHandler, "getRelatedEntities", lambda *args: [])

    def fake_define_operations(*args):
        captured["software_links"] = args[2]
        return ["operation"]

    monkeypatch.setattr(
        SALTbotHandler.SALTbotStatementDefiner,
        "defineOperations",
        fake_define_operations,
    )

    operations = SALTbotHandler.SALTbot(
        None,
        {
            "name": [{"result": {"value": "software"}}],
            "code_repository": [
                {"result": {"value": "https://github.com/example/software"}}
            ],
        },
        {
            "scholarly article": "Q13442814",
            "software category": "Q17155032",
        },
        {"code repository": "P1324"},
        True,
        {},
    )

    assert operations == ["operation"]
    assert captured["software_links"] == {}


def test_saltbot_does_not_choose_ambiguous_software_name_fallback(monkeypatch):
    article = {
        "labels": {"en": {"value": "Example article"}},
        "claims": {},
    }
    candidate = {
        "labels": {"en": {"value": "Software"}},
        "claims": {},
    }
    captured = {}

    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "parseTitles",
        lambda info: (["Example article"], {}, {}),
    )

    def fake_get_entities_by_name(name, target_class, *args):
        if target_class == "Q13442814":
            return {"Q1": article}
        return {"Q2": candidate, "Q3": candidate}

    monkeypatch.setattr(SALTbotHandler, "getEntitiesByName", fake_get_entities_by_name)
    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByRepositoryUrl",
        lambda *args: {},
    )
    monkeypatch.setattr(SALTbotHandler, "getRelatedEntities", lambda *args: [])

    def fake_define_operations(*args):
        captured["software_links"] = args[2]
        return ["operation"]

    monkeypatch.setattr(
        SALTbotHandler.SALTbotStatementDefiner,
        "defineOperations",
        fake_define_operations,
    )

    operations = SALTbotHandler.SALTbot(
        None,
        {
            "name": [{"result": {"value": "software"}}],
            "code_repository": [
                {"result": {"value": "https://github.com/example/software"}}
            ],
        },
        {
            "scholarly article": "Q13442814",
            "software category": "Q17155032",
        },
        {"code repository": "P1324"},
        True,
        {},
    )

    assert operations == ["operation"]
    assert captured["software_links"] == {}
