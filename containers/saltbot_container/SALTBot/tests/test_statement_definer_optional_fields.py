import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from SALTbot import SALTbotStatementDefiner


def test_create_software_operations_accepts_missing_license():
    info = {
        "name": [{"result": {"value": "Example software"}}],
        "description": [{"result": {"value": "Example description"}}],
        "code_repository": [
            {"result": {"value": "https://github.com/example/software"}}
        ],
    }
    man_nodes = {
        "instance of": "P31",
        "software": "Q7397",
    }
    opt_nodes = {
        "licenses": {"MIT": "Q334661"},
        "license": "P275",
        "free software": None,
    }

    operations = SALTbotStatementDefiner.createSoftwareOperations(
        info,
        man_nodes,
        opt_nodes,
        None,
        None,
    )

    assert not any(
        operation[0] == "statement" and operation[1]["p"] == "P275"
        for operation in operations
    )


def test_create_software_operations_uses_only_one_license():
    info = {
        "name": [{"result": {"value": "Example software"}}],
        "description": [{"result": {"value": "Example description"}}],
        "code_repository": [
            {"result": {"value": "https://github.com/example/software"}}
        ],
        "license": [
            {"result": {"spdx_id": "Apache-2.0"}},
            {"result": {"spdx_id": "Apache-2.0"}},
            {"result": {"spdx_id": "Apache-2.0"}},
        ],
    }
    man_nodes = {
        "instance of": "P31",
        "software": "Q7397",
    }
    opt_nodes = {
        "licenses": {"Apache-2.0": "Q13785927"},
        "license": "P275",
        "free software": None,
    }

    operations = SALTbotStatementDefiner.createSoftwareOperations(
        info,
        man_nodes,
        opt_nodes,
        None,
        None,
    )

    license_operations = [
        operation
        for operation in operations
        if operation[0] == "statement" and operation[1]["p"] == "P275"
    ]
    assert len(license_operations) == 1


def test_create_software_operations_uses_article_title_when_description_is_missing():
    operations = SALTbotStatementDefiner.createSoftwareOperations(
        {"name": [{"result": {"value": "Example software"}}]},
        {"instance of": "P31", "software": "Q7397"},
        {},
        None,
        None,
        {"title": "Example article"},
    )

    assert operations[:2] == [
        [
            "create",
            {
                "LABEL": "Example software",
                "DESCRIPTION": "scientific software associated with the article Example article",
            },
        ],
        [
            "statement",
            {
                "datatype": "Item",
                "s": "Example software",
                "p": "P31",
                "o": "Q7397",
                "qualifiers": None,
            },
        ],
    ]


def test_define_operations_records_automatically_selected_entities():
    repo_url = "https://github.com/oeg-upm/fair_ontologies"
    info = {
        "code_repository": [{"result": {"value": repo_url}}],
    }
    article_qid = "Q125468286"
    software_qid = "Q124653416"
    results = {
        repo_url: {
            "repo-article": ["FOOPS!"],
            "article": None,
            "software": None,
            "article-software-link": False,
            "software-article-link": False,
        }
    }

    SALTbotStatementDefiner.defineOperations(
        info,
        {article_qid: []},
        {software_qid: []},
        [True, [True, "DOI match"], [True, "URL match"]],
        {"main subject": "P921", "described by source": "P1343"},
        {},
        results,
        None,
        None,
        None,
    )

    assert results == {
        repo_url: {
            "repo-article": ["FOOPS!"],
            "article": article_qid,
            "software": software_qid,
            "article-software-link": False,
            "software-article-link": False,
        }
    }


def test_create_article_operations_uses_valid_openalex_external_id_and_skips_null_doi():
    operations = SALTbotStatementDefiner.createArticleOperations(
        {
            "name": [{"result": {"value": "Example software"}}],
            "description": [{"result": {"value": "Example description"}}],
        },
        {"instance of": "P31", "scholarly article": "Q13442814"},
        {"DOI": "P356", "OpenAlex ID": "P10283"},
        {
            "id": "https://openalex.org/W6965061615",
            "display_name": "Example article",
            "doi": None,
        },
        None,
    )

    assert not any(
        operation[0] == "statement" and operation[1]["p"] == "P356"
        for operation in operations
    )
    assert [
        operation
        for operation in operations
        if operation[0] == "statement" and operation[1]["p"] == "P10283"
    ] == [
        [
            "statement",
            {
                "datatype": "ExternalID",
                "s": "Example article",
                "p": "P10283",
                "o": "W6965061615",
                "qualifiers": None,
            },
        ]
    ]


def test_create_article_operations_uses_software_name_when_description_is_missing():
    operations = SALTbotStatementDefiner.createArticleOperations(
        {"name": [{"result": {"value": "Example software"}}]},
        {"instance of": "P31", "scholarly article": "Q13442814"},
        {},
        {"title": "Example article"},
        None,
    )

    assert operations[:2] == [
        [
            "create",
            {
                "LABEL": "Example article",
                "DESCRIPTION": "scientific article associated with the software Example software",
            },
        ],
        [
            "statement",
            {
                "datatype": "Item",
                "s": "Example article",
                "p": "P31",
                "o": "Q13442814",
                "qualifiers": None,
            },
        ],
    ]


def test_create_article_operations_uses_url_without_missing_identifiers():
    article_url = "https://ceur-ws.org/Vol-3846/paper12.pdf"
    operations = SALTbotStatementDefiner.createArticleOperations(
        {"name": [{"result": {"value": "Example software"}}]},
        {"instance of": "P31", "scholarly article": "Q13442814"},
        {
            "DOI": "P356",
            "OpenAlex ID": "P10283",
            "full work available at URL": "P953",
        },
        {
            "title": "Example CEUR article",
            "url": article_url,
            "type": "inproceedings",
        },
        None,
    )

    assert [
        operation
        for operation in operations
        if operation[0] == "statement" and operation[1]["p"] == "P953"
    ] == [
        [
            "statement",
            {
                "datatype": "URL",
                "s": "Example CEUR article",
                "p": "P953",
                "o": article_url,
                "qualifiers": None,
            },
        ]
    ]
    assert not any(
        operation[0] == "statement"
        and operation[1]["p"] in {"P356", "P10283"}
        for operation in operations
    )


def test_define_operations_reuses_article_without_creating_it_again():
    repo_url = "https://github.com/example/second-software"
    article_title = "Shared CEUR article"
    operations = SALTbotStatementDefiner.defineOperations(
        {
            "name": [{"result": {"value": "Second software"}}],
            "code_repository": [{"result": {"value": repo_url}}],
        },
        {},
        {},
        [True, [False, ""], [False, ""]],
        {
            "instance of": "P31",
            "software": "Q7397",
            "main subject": "P921",
            "described by source": "P1343",
        },
        {},
        {
            repo_url: {
                "repo-article": [article_title],
                "article": None,
                "software": None,
                "article-software-link": False,
                "software-article-link": False,
            }
        },
        None,
        None,
        None,
        {
            "title": article_title,
            "url": "https://ceur-ws.org/Vol-1234/paper1.pdf",
            "type": "inproceedings",
            "create": False,
        },
    )

    assert not any(
        operation[0] == "create" and operation[1]["LABEL"] == article_title
        for operation in operations
    )
    assert any(
        operation[0] == "create" and operation[1]["LABEL"] == "Second software"
        for operation in operations
    )
    assert any(
        operation[0] == "statement"
        and operation[1]["s"] == article_title
        and operation[1]["p"] == "P921"
        and operation[1]["o"] == "Second software"
        for operation in operations
    )
