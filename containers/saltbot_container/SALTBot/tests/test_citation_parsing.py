import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import SALTbot.SALTbotSearcher as searcher


@pytest.mark.parametrize("bibtex_first", [False, True])
def test_preferred_citation_takes_priority_over_bibtex(bibtex_first):
    title = "Preferred scientific article"
    url = "https://ceur-ws.org/Vol-3846/paper12.pdf"
    preferred = {
        "technique": "file_exploration",
        "result": {
            "type": "SoftwareApplication",
            "value": (
                "title: Software title\n"
                "preferred-citation:\n"
                "  type: conference-paper\n"
                f"  title: {title}\n"
                "  doi: 10.1234/preferred\n"
                f"  url: {url}\n"
            ),
        },
    }
    bibtex = {
        "technique": "regular_expression",
        "result": {
            "type": "Text_excerpt",
            "value": (
                "@inproceedings{old, title={Old article title}, "
                "doi={10.1234/old}, url={https://ceur-ws.org/Vol-3846/}}"
            ),
        },
    }
    info = {"citation": [bibtex, preferred] if bibtex_first else [preferred, bibtex]}

    assert searcher.parseTitles(info) == ([title], {"10.1234/preferred": title}, {url: title})
    assert searcher.parseCitationCandidates(info) == [
        {"title": title, "url": url, "type": "conference-paper"}
    ]


@pytest.mark.parametrize("preferred_type", ["software", "conference-paper"])
def test_unusable_preferred_citation_falls_back_to_bibtex(preferred_type):
    info = {
        "citation": [
            {
                "technique": "file_exploration",
                "result": {
                    "type": "SoftwareApplication",
                    "value": (
                        "preferred-citation:\n"
                        f"  type: {preferred_type}\n"
                        "  url: https://example.org/software\n"
                    ),
                },
            },
            {
                "technique": "regular_expression",
                "result": {
                    "type": "Text_excerpt",
                    "value": (
                        "@inproceedings{paper, title={Valid article}, "
                        "url={https://ceur-ws.org/Vol-1234/paper1.pdf}}"
                    ),
                },
            },
        ]
    }

    assert searcher.parseTitles(info) == (
        ["Valid article"], {}, {"https://ceur-ws.org/Vol-1234/paper1.pdf": "Valid article"}
    )
    assert searcher.parseCitationCandidates(info) == [
        {
            "title": "Valid article",
            "url": "https://ceur-ws.org/Vol-1234/paper1.pdf",
            "type": "inproceedings",
        }
    ]


def test_parse_titles_reads_bibtex_embedded_in_a_text_excerpt():
    info = {
        "citation": [
            {
                "technique": ["regular_expression", "header_analysis"],
                "result": {
                    "type": "Text_excerpt",
                    "title": "FAIROs: Towards FAIR Assessment in Research Objects",
                    "doi": "https://doi.org/10.1007/978-3-031-16802-4_6",
                    "value": (
                        "If you use FAIROs, please cite:\n"
                        "@inproceedings{fairos,\n"
                        "  title={FAIROs: Towards FAIR Assessment in Research Objects},\n"
                        "  doi={https://doi.org/10.1007/978-3-031-16802-4_6}\n"
                        "}"
                    ),
                },
            }
        ]
    }

    titles, dois, article_urls = searcher.parseTitles(info)

    assert titles == ["FAIROs: Towards FAIR Assessment in Research Objects"]
    assert dois == {
        "https://doi.org/10.1007/978-3-031-16802-4_6": (
            "FAIROs: Towards FAIR Assessment in Research Objects"
        )
    }
    assert article_urls == {}


def test_parse_titles_extracts_article_url_without_using_software_doi():
    article_title = (
        "Towards Assessing FAIR Research Software Best Practices "
        "in an Organization Using RDF-star"
    )
    article_url = "https://ceur-ws.org/Vol-3526/paper-09.pdf"
    info = {
        "citation": [
            {
                "technique": "file_exploration",
                "result": {
                    "title": "OEG Software Graph",
                    "doi": "10.5281/zenodo.8114677",
                    "type": "SoftwareApplication",
                    "value": (
                        "title: OEG Software Graph\n"
                        "doi: 10.5281/zenodo.8114677\n"
                    ),
                },
            },
            {
                "technique": "file_exploration",
                "result": {
                    "title": article_title,
                    "url": article_url,
                    "type": "ScholarlyArticle",
                    "value": (
                        "preferred-citation:\n"
                        "  title: Towards Assessing FAIR Research Software "
                        "Best Practices in an Organization Using RDF-star\n"
                        "  type: article\n"
                        f"  url: {article_url}\n"
                    ),
                },
            },
        ]
    }

    titles, dois, article_urls = searcher.parseTitles(info)

    assert titles == [article_title]
    assert dois == {}
    assert article_urls == {article_url: article_title}


def test_parse_titles_deduplicates_the_same_article():
    title = "FOOPS!: An Ontology Pitfall Scanner for the FAIR Principles"
    info = {
        "citation": [
            {
                "technique": "file_exploration",
                "result": {
                    "type": "ScholarlyArticle",
                    "title": title,
                    "value": (
                        "preferred-citation:\n"
                        "  type: article\n"
                        f"  title: '{title}'\n"
                    ),
                },
            },
            {
                "technique": "regular_expression",
                "result": {
                    "type": "Text_excerpt",
                    "title": title,
                    "value": f"@article{{foops, title={{{title}}}}}",
                },
            },
        ]
    }

    titles, _, _ = searcher.parseTitles(info)

    assert titles == [title]


def test_parse_citation_candidates_accepts_doi_less_inproceedings():
    title = "Benchmark for Automatic Keyword Extraction in Spanish"
    article_url = "https://ceur-ws.org/Vol-3846/paper12.pdf"
    info = {
        "citation": [
            {
                "technique": "regular_expression",
                "result": {
                    "type": "Text_excerpt",
                    "value": (
                        "@inproceedings{benchmark,\n"
                        f"  title={{{title}}},\n"
                        f"  url={{{article_url}}}\n"
                        "}"
                    ),
                },
            }
        ]
    }

    assert searcher.parseCitationCandidates(info) == [
        {
            "title": title,
            "url": article_url,
            "type": "inproceedings",
        }
    ]


def test_parse_citation_candidates_rejects_misc_entries():
    info = {
        "citation": [
            {
                "technique": "file_exploration",
                "result": {
                    "type": "Text_excerpt",
                    "value": (
                        "@misc{ontology,\n"
                        "  title={Example ontology},\n"
                        "  url={https://example.org/ontology}\n"
                        "}"
                    ),
                },
            }
        ]
    }

    assert searcher.parseCitationCandidates(info) == []


def test_parse_citation_candidates_reads_preferred_citation_from_cff():
    title = "A CEUR conference paper"
    article_url = "https://ceur-ws.org/Vol-1234/paper1.pdf"
    info = {
        "citation": [
            {
                "technique": "file_exploration",
                "result": {
                    "type": "SoftwareApplication",
                    "value": (
                        "title: Example software\n"
                        "type: software\n"
                        "preferred-citation:\n"
                        "  type: conference-paper\n"
                        f"  title: '{title}'\n"
                        f"  url: {article_url}\n"
                    ),
                },
            }
        ]
    }

    assert searcher.parseCitationCandidates(info) == [
        {
            "title": title,
            "url": article_url,
            "type": "conference-paper",
        }
    ]


def test_query_openalex_by_doi_uses_the_doi_filter(monkeypatch):
    expected_work = {
        "id": "https://openalex.org/W1",
        "type": "conference-paper",
    }
    request = {}

    class Response:
        def json(self):
            return {"meta": {"count": 1}, "results": [expected_work]}

    def fake_get(url, params, timeout):
        request.update(url=url, params=params, timeout=timeout)
        return Response()

    monkeypatch.setattr(searcher.requests, "get", fake_get)

    result = searcher.queryOpenAlexByDoi("10.1007/978-3-031-16802-4_6")

    assert result == expected_work
    assert request == {
        "url": "https://api.openalex.org/works",
        "params": {
            "filter": "doi:https://doi.org/10.1007/978-3-031-16802-4_6",
            "corpus": "core",
        },
        "timeout": 60,
    }


def test_query_openalex_falls_back_to_all_corpora(monkeypatch):
    expected_work = {
        "id": "https://openalex.org/W2",
        "type": "article",
    }
    requests = []
    responses = [
        {"meta": {"count": 0}, "results": []},
        {"meta": {"count": 1}, "results": [expected_work]},
    ]

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    def fake_get(url, params, timeout):
        requests.append({"url": url, "params": params, "timeout": timeout})
        return Response(responses[len(requests) - 1])

    monkeypatch.setattr(searcher.requests, "get", fake_get)

    result = searcher.queryOpenAlex("Expansion corpus article")

    assert result == expected_work
    assert [request["params"]["corpus"] for request in requests] == [
        "core",
        "all",
    ]


def test_query_openalex_rejects_non_article_work_types(monkeypatch):
    software_work = {
        "id": "https://openalex.org/W3",
        "type": "software",
    }
    requests = []

    class Response:
        def json(self):
            return {"meta": {"count": 1}, "results": [software_work]}

    def fake_get(url, params, timeout):
        requests.append(params)
        return Response()

    monkeypatch.setattr(searcher.requests, "get", fake_get)

    result = searcher.queryOpenAlexByDoi("10.5281/zenodo.20080309")

    assert result is None
    assert [params["corpus"] for params in requests] == ["core", "all"]
