import copy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from wikibaseintegrator.datatypes import Item, ExternalID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from SALTbot import SALTbotHandler as handler
from SALTbot import SALTbotSearcher as searcher
from SALTbot import SALTbotStatementDefiner as definer
from SALTbot import SALTbotUpdater as updater


NODES = {**handler.DEFAULT_WIKIDATA_OPTIONAL_NODES, 'title': 'P1476',
         'author': 'P50', 'author name string': 'P2093', 'series ordinal': 'P1545'}
WORK = {'title': 'Example paper', 'language': 'en', 'doi': '10.1234/paper',
        'id': 'https://openalex.org/W123',
        'authorships': [{'raw_author_name': 'Ana Example'},
                       {'author': {'display_name': 'Daniel Example'}}]}


def citation(value):
    return {'technique': 'file_exploration', 'result': {'value': value}}


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request', Mock(side_effect=AssertionError('NETWORK FORBIDDEN')))


def bibliography():
    from SALTbot import SALTbotBibliography
    return SALTbotBibliography


def test_new_article_includes_title_and_ordered_authors():
    operations = definer.createArticleOperations(
        {'name': [{'result': {'value': 'software'}}]},
        {'instance of': 'P31', 'scholarly article': 'Q13442814'},
        NODES, copy.deepcopy(WORK), None)
    title = next((v for k, v in operations if k == 'statement' and v['p'] == 'P1476'), None)
    assert title is not None
    assert title['o'] == 'Example paper' and title['language'] == 'en'
    authors = [v for k, v in operations if k == 'statement' and v['p'] == 'P2093']
    assert [v['o'] for v in authors] == ['Ana Example', 'Daniel Example']
    assert [v['qualifiers'] for v in authors] == [
        [{'datatype': 'String', 'p': 'P1545', 'o': '1'}],
        [{'datatype': 'String', 'p': 'P1545', 'o': '2'}]]
    updater.parseOperations(repr(op) for op in operations)


def test_cff_fallback_uses_publication_authors_and_unknown_language():
    info = {'citation': [citation('''authors:
  - name: Software contributor
preferred-citation:
  type: conference-paper
  title: CEUR paper
  url: https://ceur-ws.org/Vol-123/paper1.pdf
  authors:
    - given-names: Ana
      family-names: Example
    - name: Research Group
''')]}
    data = bibliography().getMetadata(info, {'title': 'CEUR paper', 'url': 'https://ceur-ws.org/Vol-123/paper1.pdf'})
    assert data == {'title': 'CEUR paper', 'language': 'und', 'authors': ['Ana Example', 'Research Group']}


def test_bibtex_authors_are_split_and_decoded():
    info = {'citation': [citation(r'''@inproceedings{paper,
      title={CEUR paper}, url={https://ceur-ws.org/Vol-123/paper1.pdf},
      author={Garc{\'i}a, Ana and Garijo, Daniel}, langid={english}}''')]}
    data = bibliography().getMetadata(info, {'title': 'CEUR paper'})
    assert data['authors'] == ['Ana García', 'Daniel Garijo']
    assert data['language'] == 'en'


def test_unrelated_citation_and_software_authors_are_not_used():
    info = {'authors': [{'name': 'Software author'}], 'citation': [citation('''preferred-citation:
  type: article
  title: Different paper
  authors:
    - name: Wrong author
''')]}
    data = bibliography().getMetadata(info, {'title': 'Selected paper'})
    assert data['title'] == 'Selected paper' and data['authors'] == []


@pytest.mark.parametrize('level,expected', [(0, 'Preferred Author'), (1, 'Citation Author'), (2, 'Bibtex Author')])
def test_author_sources_take_priority_over_openalex(level, expected):
    sources = [citation('''preferred-citation:
  type: article
  title: Example paper
  authors:
    - name: Preferred Author
'''), citation('''type: article
title: Example paper
authors:
  - name: Citation Author
'''), citation('@article{x,title={Example paper},author={Author, Bibtex}}')]
    info = {'citation': list(reversed(sources[level:]))}
    assert bibliography().getMetadata(info, WORK)['authors'] == [expected]


def test_preferred_citation_without_authors_can_use_bibtex_authors():
    info = {'citation': [citation('preferred-citation:\n  type: article\n  title: Example paper\n')],
            'bibtex': [citation('@article{x,title={Example paper},author={Author, Bibtex}}')]}
    assert bibliography().getMetadata(info, WORK)['authors'] == ['Bibtex Author']


def test_ambiguous_nonstandard_bibtex_author_list_uses_openalex(capsys):
    info = {'citation': [citation('@article{x,title={Example paper},author={Maria Navas-Loro y Daniel Garijo y Oscar Corcho}}')]}
    assert bibliography().getMetadata(info, WORK)['authors'] == ['Ana Example', 'Daniel Example']
    assert 'Ambiguous BibTeX author list' in capsys.readouterr().err


def test_missing_author_name_does_not_change_following_author_position():
    work = {'title': 'Example paper', 'language': 'en', 'authorships': [
        {'raw_author_name': 'First Author'}, {}, {'raw_author_name': 'Third Author'}]}
    operations = bibliography().articleOperations('Q123', {}, work, NODES, {'P1476': [{}]})
    assert [v['qualifiers'][0]['o'] for k, v in operations] == ['1', '3']


def test_single_citation_author_object_is_not_read_as_dictionary_keys():
    assert bibliography()._authors({'given-names': 'Ana', 'family-names': 'Example'}) == ['Ana Example']


def test_already_linked_article_is_left_unchanged_without_loading_it(monkeypatch):
    info = {'name': [{'result': {'value': 'software'}}],
            'code_repository': [{'result': {'value': 'https://github.com/example/software'}}],
            'citation': [citation('''preferred-citation:
  type: article
  title: Example paper
  doi: 10.1234/paper
  language: en
  authors:
    - name: Preferred Author
''')]}
    article = {'labels': {'en': {'value': 'Example paper'}}, 'claims': {
        'P356': [ExternalID(prop_nr='P356', value='10.1234/paper').get_json()],
        'P921': [Item(prop_nr='P921', value='Q456').get_json()]}}
    software = {'labels': {'en': {'value': 'software'}}, 'claims': {
        'P1343': [Item(prop_nr='P1343', value='Q123').get_json()]}}
    monkeypatch.setattr(handler, 'getEntitiesByDoi', lambda *args: {'Q123': article})
    monkeypatch.setattr(handler, 'getEntitiesByRepositoryUrl', lambda *args: {'Q456': software})
    load = Mock(side_effect=AssertionError('Existing entities must not be loaded for enrichment'))
    wbi = SimpleNamespace(item=SimpleNamespace(get=load))
    operations = handler.SALTbot(wbi, info, handler.DEFAULT_WIKIDATA_MANDATORY_NODES, NODES,
                                True, {}, configData={}, citation_article_registry={})
    assert operations == []
    load.assert_not_called()


@pytest.mark.parametrize('author_property', ['P50', 'P2093'])
def test_existing_authors_are_preserved(author_property):
    claims = {'P1476': [{}], author_property: [{}]}
    assert bibliography().articleOperations('Q123', {}, WORK, NODES, claims) == []


def test_missing_title_only_is_filled_without_duplicating_authors():
    operations = bibliography().articleOperations('Q123', {}, WORK, NODES, {'P50': [{}]})
    assert len(operations) == 1 and operations[0][1]['p'] == 'P1476'


def test_updater_serializes_monolingual_title_and_string_ordinal():
    title = {'datatype': 'MonolingualText', 's': 'Q123', 'p': 'P1476',
             'o': 'Título', 'language': 'es', 'qualifiers': None}
    author = {'datatype': 'String', 's': 'Q123', 'p': 'P2093', 'o': 'Ana Example',
              'qualifiers': [{'datatype': 'String', 'p': 'P1545', 'o': '1'}]}
    updater.parseOperations([repr(['statement', title]), repr(['statement', author])])
    assert updater.makeClaim(title, {}).get_json()['mainsnak']['datavalue']['value'] == {'text': 'Título', 'language': 'es'}
    assert updater.makeClaim(author, {}).get_json()['qualifiers']['P1545'][0]['datavalue']['value'] == '1'


def test_direct_openalex_id_uses_core_then_all_and_authentication(monkeypatch):
    responses = [SimpleNamespace(status_code=404),
                 SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                                 json=lambda: {'type': 'article', **WORK})]
    get = Mock(side_effect=responses)
    monkeypatch.setattr(searcher.requests, 'get', get)
    result = searcher.queryOpenAlexById('W123', openalex_api_key='fake-key')
    assert result['title'] == WORK['title']
    assert get.call_count == 2
    for call, corpus in zip(get.call_args_list, ['core', 'all']):
        assert call.args[0] == 'https://api.openalex.org/works/W123'
        assert call.kwargs['params']['corpus'] == corpus
        assert call.kwargs['headers']['Authorization'] == 'Bearer fake-key'


def test_truncated_openalex_search_fetches_complete_work(monkeypatch):
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
        'results': [{'type': 'article', 'is_authors_truncated': True, **WORK}]})
    monkeypatch.setattr(searcher.requests, 'get', Mock(return_value=response))
    lookup = Mock(return_value=WORK)
    monkeypatch.setattr(searcher, 'queryOpenAlexById', lookup)
    assert searcher.queryOpenAlex('Example paper', openalex_api_key='fake-key') == WORK
    lookup.assert_called_once_with(WORK['id'], openalex_api_key='fake-key')


def test_citation_with_conflicting_doi_cannot_supply_authors():
    info = {'citation': [citation('''preferred-citation:
  type: article
  title: Example paper
  doi: 10.1234/different
  authors:
    - name: Wrong author
''')]}
    assert bibliography().getMetadata(info, WORK)['authors'] == ['Ana Example', 'Daniel Example']


@pytest.mark.parametrize('operation', [
    ['statement', {'s': 'Q123', 'p': 'P1476', 'o': 'Paper', 'datatype': 'MonolingualText'}],
    ['statement', {'s': 'Q123', 'p': 'P1476', 'o': 'Paper', 'datatype': 'MonolingualText', 'language': 'not a language'}],
    ['statement', {'s': 'Q123', 'p': 'P2093', 'o': 'Author', 'datatype': 'String',
                   'qualifiers': [{'datatype': 'String', 'p': 'invalid', 'o': '1'}]}],
])
def test_invalid_bibliographic_values_fail_preflight(operation):
    with pytest.raises(updater.click.ClickException):
        updater.parseOperations([repr(operation)])


SOFTWARE_CFF = '''cff-version: 1.2.0
authors:
  - given-names: Ana
    family-names: Example
  - name: Research Group
preferred-citation:
  type: article
  title: Example paper
  doi: 10.1234/paper
  authors:
    - name: Paper Author
'''


def test_new_software_uses_only_root_cff_authors_and_preserves_order():
    info = {'name': [{'result': {'value': 'software'}}],
            'citation': [citation(SOFTWARE_CFF), citation(SOFTWARE_CFF)]}
    operations = definer.createSoftwareOperations(
        info, handler.DEFAULT_WIKIDATA_MANDATORY_NODES,
        {key: NODES[key] for key in ('author name string', 'author', 'series ordinal')}, {}, None)
    authors = [v for k, v in operations if k == 'statement' and v['p'] == 'P2093']
    assert [v['o'] for v in authors] == ['Ana Example', 'Research Group']
    assert [v['s'] for v in authors] == ['software', 'software']
    assert [v['qualifiers'][0]['o'] for v in authors] == ['1', '2']
    assert bibliography().getMetadata(info, WORK)['authors'] == ['Paper Author']
    updater.parseOperations(repr(op) for op in operations)
    assert updater.makeClaim(authors[0], {'software': 'Q456'}).get_json()['mainsnak']['datavalue']['value'] == 'Ana Example'


@pytest.mark.parametrize('value', [
    'authors:\n  - name: Unverified author\n',
    'cff-version: 1.2.0\ntype: dataset\nauthors:\n  - name: Dataset author\n',
    'cff-version: 1.2.0\ntype: article\nauthors:\n  - name: Paper author\n',
    'cff-version: 1.2.0\npreferred-citation:\n  authors:\n    - name: Paper author\n',
    '@article{x,title={Paper},author={Author, Paper}}',
    'authors: [invalid yaml',
])
def test_software_does_not_use_other_sources_as_cff_authors(value):
    info = {'citation': [citation(value)], 'author': [{'result': {'value': 'Code author'}}]}
    assert bibliography().softwareOperations('Q456', info, NODES) == []


def test_cff_file_provenance_accepts_root_authors_without_version():
    entry = citation('authors:\n  - name: CFF Author\n')
    entry['source'] = ['https://example.org/README.md', 'https://example.org/CITATION.cff']
    assert bibliography().softwareOperations('Q456', {'citation': [entry]}, NODES)[0][1]['o'] == 'CFF Author'


@pytest.mark.parametrize('author_property', ['P50', 'P2093'])
def test_existing_software_authors_are_preserved(author_property):
    info = {'citation': [citation(SOFTWARE_CFF)]}
    assert bibliography().softwareOperations('Q456', info, NODES, {author_property: [{}]}) == []


@pytest.mark.parametrize('auto', [True, False])
@pytest.mark.parametrize('article_link,software_link', [(True, True), (False, False), (True, False), (False, True)])
def test_existing_entities_only_receive_missing_links_without_metadata_reads(monkeypatch, auto, article_link, software_link):
    summarize = Mock(side_effect=AssertionError('Existing entities must not receive new descriptions'))
    monkeypatch.setattr(definer.llm_requests, 'article_desc_llm', summarize)
    monkeypatch.setattr(definer.llm_requests, 'fallback_desc_llm', summarize)
    info = {'name': [{'result': {'value': 'software'}}],
            'code_repository': [{'result': {'value': 'https://github.com/example/software'}}],
            'citation': [citation(SOFTWARE_CFF)]}
    article = {'labels': {'en': {'value': 'Example paper'}}, 'claims': {
        'P356': [ExternalID(prop_nr='P356', value='10.1234/paper').get_json()]}}
    software = {'labels': {'en': {'value': 'software'}}, 'claims': {
        'P31': [Item(prop_nr='P31', value='Q7397').get_json()]}}
    if article_link:
        article['claims']['P921'] = [Item(prop_nr='P921', value='Q456').get_json()]
    if software_link:
        software['claims']['P1343'] = [Item(prop_nr='P1343', value='Q123').get_json()]
    monkeypatch.setattr(handler, 'getEntitiesByDoi', lambda *args: {'Q123': article})
    monkeypatch.setattr(handler, 'getEntitiesByRepositoryUrl', lambda *args: {'Q456': software})
    monkeypatch.setattr('builtins.input', lambda *args: '1')
    load = Mock(side_effect=AssertionError('Existing entities must not be loaded for enrichment'))
    wbi = SimpleNamespace(item=SimpleNamespace(get=load))
    registry = {}
    first = handler.SALTbot(wbi, info, handler.DEFAULT_WIKIDATA_MANDATORY_NODES, NODES,
                           auto, {}, configData={}, citation_article_registry=registry)
    expected = []
    if not article_link:
        expected.append(('Q123', 'P921', 'Q456'))
    if not software_link:
        expected.append(('Q456', 'P1343', 'Q123'))
    assert [(v['s'], v['p'], v['o']) for k, v in first] == expected
    load.assert_not_called()
    summarize.assert_not_called()


@pytest.mark.parametrize('existing_article,existing_software', [(True, False), (False, True), (False, False)])
def test_titles_and_authors_are_only_generated_for_new_entities(monkeypatch, existing_article, existing_software):
    info = {'name': [{'result': {'value': 'software'}}],
            'code_repository': [{'result': {'value': 'https://github.com/example/software'}}],
            'citation': [citation(SOFTWARE_CFF)]}
    article = {'labels': {'en': {'value': 'Example paper'}}, 'claims': {}}
    software = {'labels': {'en': {'value': 'software'}}, 'claims': {}}
    monkeypatch.setattr(handler, 'getEntitiesByDoi', lambda *args: {'Q123': article} if existing_article else {})
    monkeypatch.setattr(handler, 'getEntitiesByOpenAlexId', lambda *args: {})
    monkeypatch.setattr(handler, 'getEntitiesByName', lambda *args: {})
    monkeypatch.setattr(handler, 'getEntitiesByRepositoryUrl', lambda *args: {'Q456': software} if existing_software else {})
    monkeypatch.setattr(searcher, 'queryOpenAlexByDoi', lambda *args, **kwargs: copy.deepcopy(WORK))
    load = Mock(side_effect=AssertionError('Existing entities must not be loaded for enrichment'))
    nodes = {**NODES, 'licenses': {'MIT': 'Q334661'}}
    operations = handler.SALTbot(SimpleNamespace(item=SimpleNamespace(get=load)), info,
                                handler.DEFAULT_WIKIDATA_MANDATORY_NODES, nodes, True, {},
                                configData={}, citation_article_registry={})
    created = [v['LABEL'] for k, v in operations if k == 'create']
    assert ('Example paper' in created) == (not existing_article)
    assert ('software' in created) == (not existing_software)
    metadata = [v for k, v in operations if k == 'statement' and v['p'] in ('P1476', 'P2093')]
    assert all(v['s'] not in ('Q123', 'Q456') for v in metadata)
    if not existing_article:
        assert any(v['p'] == 'P1476' and v['s'] == 'Example paper' for v in metadata)
        assert any(v['p'] == 'P2093' and v['o'] == 'Paper Author' for v in metadata)
    if not existing_software:
        assert [v['o'] for v in metadata if v['s'] == 'software'] == ['Ana Example', 'Research Group']
    load.assert_not_called()
