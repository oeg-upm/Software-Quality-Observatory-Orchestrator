"""Publication and CFF software metadata; never creates author entities."""
import re
import sys
import unicodedata
from urllib.parse import urldefrag

import bibtexparser
import yaml
from bibtexparser.middlewares import SeparateCoAuthors, SplitNameParts
from pylatexenc.latex2text import LatexNodes2Text

from . import SALTbotSearcher as searcher
from . import SPARQLQuerys


def getAbstract(work):
    """Reconstruct an OpenAlex abstract, or return empty text for missing/invalid data."""
    index = work.get('abstract_inverted_index')
    if not isinstance(index, dict):
        return ''
    words = {}
    for word, positions in index.items():
        if not isinstance(word, str) or not word.strip() or not isinstance(positions, list):
            return ''
        for position in positions:
            if type(position) is not int or position < 0 or position in words:
                return ''
            words[position] = word
    if sorted(words) != list(range(len(words))):
        return ''
    return ' '.join(words[position] for position in range(len(words)))


def _title(value):
    return re.sub(r'[\W_]+', '', unicodedata.normalize('NFKD', str(value or '')).casefold())


def _authors(value):
    if isinstance(value, str):
        if value.count(' y ') >= 2 and not re.search(r'\s+and\s+', value):
            print('Ambiguous BibTeX author list: use "and" between authors; trying another source.', file=sys.stderr)
            return []
        parsed = bibtexparser.parse_string('@misc{citation,author={' + value + '}}',
                                          append_middleware=[SeparateCoAuthors(), SplitNameParts()])
        if not parsed.entries or parsed.failed_blocks:
            return []
        decoder = LatexNodes2Text()
        return [decoder.latex_to_text(' '.join(name.first + name.von + name.last + name.jr)).strip()
                for name in parsed.entries[0]['author']]
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    names = []
    for author in value or []:
        if isinstance(author, str):
            name = author
        elif isinstance(author, dict):
            name = author.get('name') or ' '.join(str(author.get(k) or '') for k in ('given-names', 'family-names'))
        else:
            continue
        names.append(' '.join(str(name).split()))
    return names


def _matches(candidate, work):
    if candidate.get('doi') and work.get('doi'):
        return SPARQLQuerys.normalizeDoi(candidate['doi']).casefold() == SPARQLQuerys.normalizeDoi(work['doi']).casefold()
    if candidate.get('url') and work.get('url'):
        if urldefrag(candidate['url'])[0].rstrip('/') == urldefrag(work['url'])[0].rstrip('/'):
            return True
    return bool(_title(candidate.get('title'))) and _title(candidate['title']) == _title(work.get('title') or work.get('display_name'))


def getMetadata(info, work):
    work = work or {}
    citations = []
    sources = []
    for key in ('citation', 'bibtex'):
        entries = info.get(key) or []
        sources.extend(entries if isinstance(entries, list) else [entries])
    for citation in sources:
        if not isinstance(citation, dict):
            continue
        value = str(citation.get('result', {}).get('value') or '')
        if re.search(r'@\w+\s*\{', value):
            data = searcher._parseBibEntry(citation)
            if data and data['type'] in searcher.BIBTEX_ARTICLE_TYPES:
                citations.append((2, data))
        else:
            try:
                parsed = yaml.safe_load(value)
            except yaml.YAMLError:
                continue
            if isinstance(parsed, dict):
                preferred = parsed.get('preferred-citation')
                data = preferred if isinstance(preferred, dict) else parsed
                if str(data.get('type', '')).lower() in searcher.SCIENTIFIC_CITATION_TYPES | searcher.BIBTEX_ARTICLE_TYPES:
                    citations.append((0 if isinstance(preferred, dict) else 1, data))
    matched = []
    for priority, data in sorted(citations, key=lambda x: x[0]):
        if data not in matched and _matches(data, work):
            matched.append(data)
    citation = matched[0] if matched else {}
    authors = [a.get('raw_author_name') or (a.get('author') or {}).get('display_name')
               for a in work.get('authorships') or []
               if 'author_position' not in a or a['author_position'] is not None]
    authors = [' '.join(str(name or '').split()) for name in authors]
    language = str(work.get('language') or citation.get('language') or 'und').strip().lower()
    language = {'english': 'en', 'spanish': 'es', 'french': 'fr', 'german': 'de',
                'italian': 'it', 'portuguese': 'pt'}.get(language, language)
    if not re.fullmatch(r'[a-z]{2,3}(?:-[a-z0-9]+)*', language):
        language = 'und'
    citation_authors = next((names for c in matched if any(names := _authors(c.get('authors') or c.get('author')))), [])
    return {'title': work.get('title') or citation.get('title') or work.get('display_name'),
            'language': language, 'authors': citation_authors or (authors if any(authors) else [])}


def _authorOperations(subject, names, nodes, claims):
    operations = []
    if nodes.get('author name string') and not claims.get(nodes['author name string']) and not claims.get(nodes.get('author')):
        for position, name in enumerate(names, 1):
            if not name:
                continue
            qualifiers = [{'datatype': 'String', 'p': nodes['series ordinal'], 'o': str(position)}] if nodes.get('series ordinal') else None
            operations.append(['statement', {'s': subject, 'p': nodes['author name string'], 'o': name,
                                            'datatype': 'String', 'qualifiers': qualifiers}])
    return operations


def articleOperations(subject, info, work, nodes, claims=None):
    claims = claims or {}
    data = getMetadata(info, work)
    operations = []
    if nodes.get('title') and data['title'] and not claims.get(nodes['title']):
        operations.append(['statement', {'s': subject, 'p': nodes['title'], 'o': ' '.join(str(data['title']).split()),
                                        'datatype': 'MonolingualText', 'language': data['language'], 'qualifiers': None}])
    return operations + _authorOperations(subject, data['authors'], nodes, claims)


def getSoftwareAuthors(info):
    entries = info.get('citation') or []
    for citation in entries if isinstance(entries, list) else [entries]:
        if not isinstance(citation, dict):
            continue
        result = citation.get('result') or {}
        if str(result.get('is_preferred_citation', '')).casefold() == 'true':
            continue
        try:
            data = yaml.safe_load(str(result.get('value') or ''))
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict) or str(data.get('type', 'software')).casefold() != 'software':
            continue
        sources = citation.get('source') or []
        sources = sources if isinstance(sources, list) else [sources]
        is_cff = data.get('cff-version') or result.get('format') == 'cff' or any(
            re.search(r'\.cff(?:[?#].*)?$', str(source), re.IGNORECASE) for source in sources)
        if is_cff:
            names = _authors(data.get('authors'))
            if any(names):
                return names
    return []


def softwareOperations(subject, info, nodes, claims=None):
    return _authorOperations(subject, getSoftwareAuthors(info), nodes, claims or {})
