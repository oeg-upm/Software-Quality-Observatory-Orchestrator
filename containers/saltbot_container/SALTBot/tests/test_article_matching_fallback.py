import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from SALTbot import SALTbotHandler


ARTICLE_CLASS = "Q13442814"
SOFTWARE_CLASS = "Q17155032"
REPOSITORY_PROPERTY = "P1324"
DOI_PROPERTY = "P356"


def entity(label):
    return {
        "labels": {"en": {"value": label}},
        "claims": {},
    }


def saltbot_nodes():
    return (
        {
            "scholarly article": ARTICLE_CLASS,
            "software category": SOFTWARE_CLASS,
        },
        {
            "code repository": REPOSITORY_PROPERTY,
            "DOI": DOI_PROPERTY,
        },
    )


def test_filter_article_candidates_keeps_normalized_exact_titles():
    candidates = {
        "QWIDOCO": entity("WIDOCO: A Wizard for Documenting Ontologies"),
        "QTINTO": entity(
            "TINTO: Converting Tidy Data into image for classification "
            "with 2-Dimensional Convolutional Neural Networks"
        ),
        "QFOOPS": entity(
            "FOOPS!: An Ontology Pitfall Scanner for the FAIR principles"
        ),
        "QWRONG": entity(
            "FAIR Research Objects for realizing Open Science with "
            "RELIANCE EOSC project"
        ),
    }
    titles = [
        "WIDOCO: A wizard for documenting ontologies",
        (
            "TINTO: Converting Tidy Data into Image for Classification "
            "with 2-Dimensional Convolutional Neural Networks"
        ),
        "FOOPS!: An Ontology Pitfall Scanner for the FAIR Principles",
        "FAIROs: Towards FAIR Assessment in Research Objects",
    ]

    filtered = SALTbotHandler.filterArticleCandidatesByTitle(candidates, titles)

    assert list(filtered) == ["QWIDOCO", "QTINTO", "QFOOPS"]


def test_select_citation_article_reuses_normalized_article_url():
    registry = {}
    first = SALTbotHandler.selectCitationArticle(
        [
            {
                "title": "Shared CEUR paper",
                "url": "HTTPS://CEUR-WS.ORG/Vol-3846/paper12.pdf/",
                "type": "inproceedings",
            }
        ],
        registry,
    )
    second = SALTbotHandler.selectCitationArticle(
        [
            {
                "title": "Shared CEUR paper",
                "url": "https://ceur-ws.org/Vol-3846/paper12.pdf#page=1",
                "type": "conference-paper",
            }
        ],
        registry,
    )

    assert first["create"] is True
    assert second == {
        "title": "Shared CEUR paper",
        "url": "https://ceur-ws.org/Vol-3846/paper12.pdf#page=1",
        "type": "conference-paper",
        "create": False,
    }
    assert len(registry) == 1


def test_select_citation_article_rejects_multiple_distinct_candidates():
    candidates = [
        {"title": "Paper one", "url": "https://example.org/one"},
        {"title": "Paper two", "url": "https://example.org/two"},
    ]

    assert SALTbotHandler.selectCitationArticle(candidates, {}) is None


@pytest.mark.parametrize(
    "second_work",
    [
        {"doi": "10.1016/J.SOFTX.2025.102444", "id": "https://openalex.org/W999"},
        {"doi": None, "id": "W4416706803"},
    ],
)
def test_openalex_articles_reuse_doi_or_openalex_id(second_work):
    registry = {}
    info = {"name": [{"result": {"value": "Example software"}}]}
    first_work = {
        "title": "Canonical article title",
        "doi": "https://doi.org/10.1016/j.softx.2025.102444",
        "id": "https://openalex.org/W4416706803",
    }
    first = SALTbotHandler.selectOpenAlexArticle(info, first_work, registry)
    second = SALTbotHandler.selectOpenAlexArticle(
        info, {"title": "A different title spelling", **second_work}, registry
    )

    assert first["create"] is True
    assert second["create"] is False
    assert SALTbotHandler.SALTbotStatementDefiner.getArticleLabel(info, second) == "Canonical article title"
    assert "create" not in first_work


def test_distinct_openalex_identifiers_do_not_merge_equal_titles():
    info = {"name": [{"result": {"value": "Example software"}}]}
    registry = {}
    first = SALTbotHandler.selectOpenAlexArticle(
        info, {"title": "Shared title", "id": "W1", "doi": "10.1234/one"}, registry
    )
    second = SALTbotHandler.selectOpenAlexArticle(
        info, {"title": "Shared title", "id": "W2", "doi": "10.1234/two"}, registry
    )

    assert first["create"] is True
    assert second["create"] is True


def test_openalex_article_reference_survives_software_title_collision():
    registry = {}
    first_info = {"name": [{"result": {"value": "Shared title"}}]}
    second_info = {"name": [{"result": {"value": "Other software"}}]}
    work = {"title": "Shared title", "id": "https://openalex.org/W123"}

    first = SALTbotHandler.selectOpenAlexArticle(first_info, work, registry)
    second = SALTbotHandler.selectOpenAlexArticle(second_info, work, registry)

    get_label = SALTbotHandler.SALTbotStatementDefiner.getArticleLabel
    assert get_label(first_info, first) == "Shared title scholarly article"
    assert get_label(second_info, second) == get_label(first_info, first)
    assert second["create"] is False


def test_three_repositories_create_one_openalex_article_and_keep_all_links(monkeypatch):
    title = "TINTOlib: A Python library for transforming tabular data into synthetic images for deep neural networks"
    work = {
        "title": title,
        "display_name": title,
        "doi": "https://doi.org/10.1016/j.softx.2025.102444",
        "id": "https://openalex.org/W4416706803",
    }
    monkeypatch.setattr(SALTbotHandler.SALTbotSearcher, "parseTitles", lambda info: ([title], {}, {}))
    monkeypatch.setattr(SALTbotHandler.SALTbotSearcher, "queryOpenAlex", lambda value: work)
    for name in ("getEntitiesByName", "getEntitiesByDoi", "getEntitiesByOpenAlexId"):
        monkeypatch.setattr(SALTbotHandler, name, lambda *args: {})

    names = ["TINTOlib-Crash_Course", "TINTOlib-Documentation", "TINTOlib"]
    registry = {}
    operations = []
    for name in names:
        operations.extend(SALTbotHandler.SALTbot(
            None,
            {
                "name": [{"result": {"value": name}}],
                "code_repository": [{"result": {"value": f"https://github.com/oeg-upm/{name}"}}],
            },
            SALTbotHandler.DEFAULT_WIKIDATA_MANDATORY_NODES,
            {"DOI": "P356", "OpenAlex ID": "P10283", "free software": None},
            True, {}, citation_article_registry=registry,
        ))

    assert sum(op[0] == "create" and op[1]["LABEL"] == title for op in operations) == 1
    for property_id in ("P356", "P10283"):
        assert sum(op[0] == "statement" and op[1]["p"] == property_id for op in operations) == 1
    for name in names:
        assert any(op[0] == "create" and op[1]["LABEL"] == name for op in operations)
        assert any(op[0] == "statement" and op[1]["s"] == title and op[1]["p"] == "P921" and op[1]["o"] == name for op in operations)
        assert any(op[0] == "statement" and op[1]["s"] == name and op[1]["p"] == "P1343" and op[1]["o"] == title for op in operations)


def test_ambiguous_wikidata_titles_fall_back_to_openalex_doi(monkeypatch):
    title = "FAIROs: Towards FAIR Assessment in Research Objects"
    doi = "https://doi.org/10.1007/978-3-031-16802-4_6"
    openalex_work = {
        "id": "https://openalex.org/W4311953176",
        "display_name": title,
        "doi": doi,
        "type": "book-chapter",
    }
    name_searches = []
    openalex_doi_searches = []
    captured = {}

    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "parseTitles",
        lambda info: ([title], {doi: title}, {}),
    )
    monkeypatch.setattr(SALTbotHandler, "getEntitiesByDoi", lambda *args: {})

    def fake_get_entities_by_name(name, *args):
        name_searches.append(name)
        return {
            "Q125297073": entity(
                "FAIR Research Objects - CREDiT and Attribuion"
            ),
            "Q114728251": entity(
                "FAIR Research Objects for realizing Open Science with "
                "RELIANCE EOSC project"
            ),
        }

    def fake_query_openalex_by_doi(value):
        openalex_doi_searches.append(value)
        return openalex_work

    def fake_define_operations(*args):
        captured["article_links"] = args[1]
        captured["openalex"] = args[7]
        return ["operation"]

    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByName",
        fake_get_entities_by_name,
    )
    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByRepositoryUrl",
        lambda *args: {},
    )
    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "queryOpenAlexByDoi",
        fake_query_openalex_by_doi,
    )
    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "queryOpenAlex",
        lambda title: None,
    )
    monkeypatch.setattr(SALTbotHandler, "getRelatedEntities", lambda *args: [])
    monkeypatch.setattr(
        SALTbotHandler.SALTbotStatementDefiner,
        "defineOperations",
        fake_define_operations,
    )

    man_nodes, opt_nodes = saltbot_nodes()
    operations = SALTbotHandler.SALTbot(
        None,
        {
            "name": [{"result": {"value": "FAIR Research Object"}}],
            "code_repository": [
                {
                    "result": {
                        "value": "https://github.com/oeg-upm/FAIR-Research-Object"
                    }
                }
            ],
        },
        man_nodes,
        opt_nodes,
        True,
        {},
    )

    assert operations == ["operation"]
    assert name_searches == [title, "FAIR Research Object"]
    assert openalex_doi_searches == [doi]
    assert captured == {
        "article_links": {},
        "openalex": openalex_work,
    }


def test_multiple_exact_titles_fall_back_to_openalex_in_auto_mode(monkeypatch):
    title = "Duplicated article title"
    openalex_work = {
        "id": "https://openalex.org/W456",
        "display_name": title,
        "type": "article",
    }
    captured = {}

    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "parseTitles",
        lambda info: ([title], {}, {}),
    )
    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByName",
        lambda *args: {
            "Q1": entity(title),
            "Q2": entity(title.upper()),
        },
    )
    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByRepositoryUrl",
        lambda *args: {},
    )
    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "queryOpenAlex",
        lambda value: openalex_work,
    )
    monkeypatch.setattr(SALTbotHandler, "getRelatedEntities", lambda *args: [])

    def fake_define_operations(*args):
        captured["article_links"] = args[1]
        captured["openalex"] = args[7]
        return ["operation"]

    monkeypatch.setattr(
        SALTbotHandler.SALTbotStatementDefiner,
        "defineOperations",
        fake_define_operations,
    )

    man_nodes, opt_nodes = saltbot_nodes()
    operations = SALTbotHandler.SALTbot(
        None,
        {
            "name": [{"result": {"value": "Example software"}}],
            "code_repository": [
                {"result": {"value": "https://github.com/example/software"}}
            ],
        },
        man_nodes,
        opt_nodes,
        True,
        {},
    )

    assert operations == ["operation"]
    assert captured == {
        "article_links": {},
        "openalex": openalex_work,
    }


def test_openalex_new_doi_is_checked_in_wikidata_before_creation(monkeypatch):
    title = "Article found by title"
    openalex_doi = "https://doi.org/10.1234/example"
    openalex_work = {
        "id": "https://openalex.org/W123",
        "display_name": title,
        "doi": openalex_doi,
        "type": "article",
    }
    wikidata_article = entity(title)
    doi_searches = []
    captured = {}

    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "parseTitles",
        lambda info: ([title], {}, {}),
    )
    monkeypatch.setattr(SALTbotHandler, "getEntitiesByName", lambda *args: {})

    def fake_get_entities_by_doi(doi, *args):
        doi_searches.append(doi)
        return {"QARTICLE": wikidata_article}

    def fake_define_operations(*args):
        captured["article_links"] = args[1]
        return ["operation"]

    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByDoi",
        fake_get_entities_by_doi,
    )
    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByRepositoryUrl",
        lambda *args: {},
    )
    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "queryOpenAlexByDoi",
        lambda doi: None,
    )
    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "queryOpenAlex",
        lambda value: openalex_work,
    )
    monkeypatch.setattr(SALTbotHandler, "getRelatedEntities", lambda *args: [])
    monkeypatch.setattr(
        SALTbotHandler.SALTbotStatementDefiner,
        "defineOperations",
        fake_define_operations,
    )

    man_nodes, opt_nodes = saltbot_nodes()
    operations = SALTbotHandler.SALTbot(
        None,
        {
            "name": [{"result": {"value": "Example software"}}],
            "code_repository": [
                {"result": {"value": "https://github.com/example/software"}}
            ],
        },
        man_nodes,
        opt_nodes,
        True,
        {},
    )

    assert operations == ["operation"]
    assert doi_searches == [openalex_doi]
    assert captured["article_links"] == {"QARTICLE": []}


def test_openalex_title_fallback_rejects_unrelated_title(monkeypatch):
    detected_title = "Ontology Governance Framework"
    unrelated_work = {
        "id": "https://openalex.org/W4395011193",
        "display_name": (
            "The Ontology of Urban Governance: A Framework for Pathways "
            "to Sustainable Urban Transition"
        ),
        "doi": "https://doi.org/10.3390/urbansci8020038",
        "type": "article",
    }
    define_operations_called = []

    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "parseTitles",
        lambda info: ([detected_title], {}, {}),
    )
    monkeypatch.setattr(SALTbotHandler, "getEntitiesByName", lambda *args: {})
    monkeypatch.setattr(SALTbotHandler, "getEntitiesByDoi", lambda *args: {})
    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByRepositoryUrl",
        lambda *args: {},
    )
    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "queryOpenAlex",
        lambda value: unrelated_work,
    )
    monkeypatch.setattr(
        SALTbotHandler.SALTbotStatementDefiner,
        "defineOperations",
        lambda *args: define_operations_called.append(True),
    )

    man_nodes, opt_nodes = saltbot_nodes()
    operations = SALTbotHandler.SALTbot(
        None,
        {
            "name": [{"result": {"value": "Ontology-governance-framework"}}],
            "code_repository": [
                {
                    "result": {
                        "value": (
                            "https://github.com/oeg-upm/"
                            "Ontology-governance-framework"
                        )
                    }
                }
            ],
        },
        man_nodes,
        opt_nodes,
        True,
        {},
    )

    assert operations == []
    assert define_operations_called == []


def test_openalex_match_is_checked_by_openalex_id_before_creation(monkeypatch):
    title = "Widaug. Data augmentation for named entity recognition using Wikidata"
    openalex_work = {
        "id": "https://openalex.org/W6965061615",
        "display_name": title,
        "doi": None,
        "type": "article",
    }
    wikidata_article = entity(title)
    openalex_id_searches = []
    captured = {}

    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "parseTitles",
        lambda info: ([title], {}, {}),
    )
    monkeypatch.setattr(SALTbotHandler, "getEntitiesByName", lambda *args: {})
    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByRepositoryUrl",
        lambda *args: {},
    )
    monkeypatch.setattr(
        SALTbotHandler.SALTbotSearcher,
        "queryOpenAlex",
        lambda value: openalex_work,
    )

    def fake_get_entities_by_openalex_id(openalex_id, *args):
        openalex_id_searches.append(openalex_id)
        return {"QARTICLE": wikidata_article}

    monkeypatch.setattr(
        SALTbotHandler,
        "getEntitiesByOpenAlexId",
        fake_get_entities_by_openalex_id,
        raising=False,
    )
    monkeypatch.setattr(SALTbotHandler, "getRelatedEntities", lambda *args: [])

    def fake_define_operations(*args):
        captured["article_links"] = args[1]
        return ["operation"]

    monkeypatch.setattr(
        SALTbotHandler.SALTbotStatementDefiner,
        "defineOperations",
        fake_define_operations,
    )

    man_nodes, opt_nodes = saltbot_nodes()
    opt_nodes["OpenAlex ID"] = "P10283"
    operations = SALTbotHandler.SALTbot(
        None,
        {
            "name": [{"result": {"value": "widaug"}}],
            "code_repository": [
                {"result": {"value": "https://github.com/oeg-upm/widaug"}}
            ],
        },
        man_nodes,
        opt_nodes,
        True,
        {},
    )

    assert operations == ["operation"]
    assert openalex_id_searches == ["W6965061615"]
    assert captured["article_links"] == {"QARTICLE": []}
