import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from SALTbot import SALTbotHandler


def test_print_article_matches_identifies_wikidata_source(capsys):
    articles = {
        "Q123": {
            "labels": {
                "en": {"value": "Example article"}
            }
        }
    }

    SALTbotHandler.printArticleMatches(articles, None, None)

    assert (
        "ARTICLE FOUND IN WIKIDATA: Q123 | Example article | "
        "https://www.wikidata.org/wiki/Q123"
    ) in capsys.readouterr().out


def test_print_article_matches_identifies_openalex_source_and_method(capsys):
    openalex_work = {
        "id": "https://openalex.org/W456",
        "display_name": "Example OpenAlex article",
    }

    SALTbotHandler.printArticleMatches({}, openalex_work, "DOI")

    assert (
        "ARTICLE FOUND IN OPENALEX BY DOI: W456 | Example OpenAlex article | "
        "https://openalex.org/W456"
    ) in capsys.readouterr().out
