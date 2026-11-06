import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from SALTbot import SPARQLQuerys


def test_get_entities_by_name_splits_candidate_detail_queries(monkeypatch):
	calls = []

	def fake_execute_select(query, endpoint=SPARQLQuerys.GENERAL_ENDPOINT, timeout=SPARQLQuerys.DEFAULT_TIMEOUT):
		calls.append(query)

		if len(calls) == 1:
			return [
				{
					"item": {"value": "http://www.wikidata.org/entity/Q1"},
					"itemLabel": {"value": "First article"},
				},
				{
					"item": {"value": "http://www.wikidata.org/entity/Q2"},
					"itemLabel": {"value": "Second article"},
				},
			]

		item_id = "Q1" if "VALUES ?item { wd:Q1 }" in query else "Q2"
		return [
			{
				"item": {"value": f"http://www.wikidata.org/entity/{item_id}"},
				"prop": {"value": "P31"},
				"value": {"value": "http://www.wikidata.org/entity/Q13442814"},
			}
		]

	monkeypatch.setattr(SPARQLQuerys, "executeSelect", fake_execute_select)

	entities = SPARQLQuerys.sparql_getEntitiesByName(
		"Chowlk",
		"Q13442814",
		{"instance of": "P31", "main subject": "P921", "described by source": "P1343"},
		{"DOI": "P356", "code repository": "P1324"},
		None,
	)

	assert list(entities) == ["Q1", "Q2"]
	assert len(calls) == 3
	assert "VALUES ?item { wd:Q1 }" in calls[1]
	assert "VALUES ?item { wd:Q2 }" in calls[2]
	assert "wd:Q1 wd:Q2" not in calls[1]
	assert "wd:Q1 wd:Q2" not in calls[2]


def test_get_entities_by_repository_url_uses_direct_url_lookup_then_candidate_details(monkeypatch):
	calls = []

	def fake_execute_select(query, endpoint=SPARQLQuerys.GENERAL_ENDPOINT, timeout=SPARQLQuerys.DEFAULT_TIMEOUT):
		calls.append(query)

		if len(calls) == 1:
			return [
				{
					"item": {"value": "http://www.wikidata.org/entity/Q10"},
					"itemLabel": {"value": "First software"},
				},
				{
					"item": {"value": "http://www.wikidata.org/entity/Q20"},
					"itemLabel": {"value": "Second software"},
				},
			]

		item_id = "Q10" if "VALUES ?item { wd:Q10 }" in query else "Q20"
		return [
			{
				"item": {"value": f"http://www.wikidata.org/entity/{item_id}"},
				"prop": {"value": "P1324"},
				"value": {"value": "https://github.com/oeg-upm/Chowlk"},
			}
		]

	monkeypatch.setattr(SPARQLQuerys, "executeSelect", fake_execute_select)

	entities = SPARQLQuerys.sparql_getEntitiesByRepositoryUrl(
		"https://github.com/oeg-upm/Chowlk",
		"Q17155032",
		{"instance of": "P31", "main subject": "P921", "described by source": "P1343", "software": "Q7397", "software category": "Q17155032"},
		{"DOI": "P356", "code repository": "P1324"},
		None,
	)

	assert list(entities) == ["Q10", "Q20"]
	assert len(calls) == 3
	assert "VALUES ?repositoryUrl {" in calls[0]
	assert "<https://github.com/oeg-upm/Chowlk>" in calls[0]
	assert "<https://github.com/oeg-upm/Chowlk/>" in calls[0]
	assert "<https://github.com/oeg-upm/Chowlk.git>" in calls[0]
	assert "?item wdt:P1324 ?repositoryUrl ." in calls[0]
	assert "FILTER(STR(?repositoryUrl)" not in calls[0]
	assert "VALUES ?item { wd:Q10 }" in calls[1]
	assert "VALUES ?item { wd:Q20 }" in calls[2]


def test_get_entities_by_doi_uses_an_exact_doi_lookup(monkeypatch):
	calls = []

	def fake_execute_select(query, endpoint=SPARQLQuerys.GENERAL_ENDPOINT, timeout=SPARQLQuerys.DEFAULT_TIMEOUT):
		calls.append(query)
		if len(calls) == 1:
			return [
				{
					"item": {"value": "http://www.wikidata.org/entity/Q1"},
					"itemLabel": {"value": "FAIROs: Towards FAIR Assessment in Research Objects"},
				}
			]

		return [
			{
				"item": {"value": "http://www.wikidata.org/entity/Q1"},
				"prop": {"value": "P356"},
				"value": {"value": "10.1007/978-3-031-16802-4_6"},
			}
		]

	monkeypatch.setattr(SPARQLQuerys, "executeSelect", fake_execute_select)

	entities = SPARQLQuerys.sparql_getEntitiesByDoi(
		"https://doi.org/10.1007/978-3-031-16802-4_6",
		"Q13442814",
		{"instance of": "P31", "main subject": "P921", "described by source": "P1343"},
		{"DOI": "P356", "code repository": "P1324"},
		None,
	)

	assert list(entities) == ["Q1"]
	assert entities["Q1"]["claims"]["P356"][0]["mainsnak"]["datavalue"]["value"] == "10.1007/978-3-031-16802-4_6"
	assert len(calls) == 2
	assert '?item wdt:P356 "10.1007/978-3-031-16802-4_6" .' in calls[0]
	assert "?prop" not in calls[0]
	assert "wdt:P31+" not in calls[0]
	assert "VALUES ?item { wd:Q1 }" in calls[1]
	assert "wdt:P31+" in calls[1]
	assert "wikibase:mwapi" not in calls[0]


def test_get_entities_by_article_url_uses_exact_p953_lookup(monkeypatch):
	calls = []

	def fake_execute_select(query, endpoint=SPARQLQuerys.GENERAL_ENDPOINT, timeout=SPARQLQuerys.DEFAULT_TIMEOUT):
		calls.append((query, endpoint))
		if len(calls) == 1:
			return [
				{
					"item": {"value": "http://www.wikidata.org/entity/Q123197105"},
					"itemLabel": {"value": "Towards Assessing FAIR Research Software Best Practices in an Organization Using RDF-star"},
				}
			]

		return [
			{
				"item": {"value": "http://www.wikidata.org/entity/Q123197105"},
				"prop": {"value": "P953"},
				"value": {"value": "https://ceur-ws.org/Vol-3526/paper-09.pdf"},
			}
		]

	monkeypatch.setattr(SPARQLQuerys, "executeSelect", fake_execute_select)

	entities = SPARQLQuerys.sparql_getEntitiesByArticleUrl(
		"https://ceur-ws.org/Vol-3526/paper-09.pdf",
		"Q13442814",
		{"instance of": "P31", "main subject": "P921", "described by source": "P1343", "scholarly article": "Q13442814"},
		{"DOI": "P356", "code repository": "P1324", "full work available at URL": "P953"},
		None,
	)

	assert list(entities) == ["Q123197105"]
	assert entities["Q123197105"]["claims"]["P953"][0]["mainsnak"]["datavalue"]["value"] == "https://ceur-ws.org/Vol-3526/paper-09.pdf"
	assert len(calls) == 2
	assert "?item wdt:P953 <https://ceur-ws.org/Vol-3526/paper-09.pdf> ." in calls[0][0]
	assert "wdt:P31+ wd:Q13442814" not in calls[0][0]
	assert "VALUES ?item { wd:Q123197105 }" in calls[1][0]
	assert "wdt:P31+ wd:Q13442814" in calls[1][0]
	assert calls[0][1] == SPARQLQuerys.ARTICLES_ENDPOINT


def test_get_entities_by_openalex_id_uses_exact_p10283_lookup(monkeypatch):
	calls = []

	def fake_execute_select(query, endpoint=SPARQLQuerys.GENERAL_ENDPOINT, timeout=SPARQLQuerys.DEFAULT_TIMEOUT):
		calls.append(query)
		if len(calls) == 1:
			return [
				{
					"item": {"value": "http://www.wikidata.org/entity/Q131162650"},
					"itemLabel": {"value": "Widaug"},
				}
			]

		return [
			{
				"item": {"value": "http://www.wikidata.org/entity/Q131162650"},
				"prop": {"value": "P10283"},
				"value": {"value": "W6965061615"},
			}
		]

	monkeypatch.setattr(SPARQLQuerys, "executeSelect", fake_execute_select)

	entities = SPARQLQuerys.sparql_getEntitiesByOpenAlexId(
		"https://openalex.org/W6965061615",
		"Q13442814",
		{"instance of": "P31", "main subject": "P921", "described by source": "P1343"},
		{"DOI": "P356", "OpenAlex ID": "P10283", "code repository": "P1324"},
		None,
	)

	assert list(entities) == ["Q131162650"]
	assert '?item wdt:P10283 "W6965061615" .' in calls[0]
	assert entities["Q131162650"]["claims"]["P10283"][0]["mainsnak"]["datavalue"]["value"] == "W6965061615"
