import bibtexparser
import yaml
from yaml.loader import SafeLoader
from urllib.parse import urlparse
from email.utils import parsedate_to_datetime

from wikibaseintegrator import wbi_login
#from wikiintegrator import wbi_core
from wikibaseintegrator import wbi_helpers
from wikibaseintegrator.datatypes import ExternalID, Item, String, URL, Quantity, Property, CommonsMedia, GlobeCoordinate
from wikibaseintegrator.models import Qualifiers
from wikibaseintegrator.wbi_enums import ActionIfExists

import time
import json
import re
import requests
import sys
import click
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup


OPENALEX_ARTICLE_TYPES = {
    "article",
    "book-chapter",
    "conference-paper",
    "data-paper",
    "preprint",
    "review",
    "software-paper",
}

OPENALEX_MAX_RETRIES = 3
OPENALEX_RETRY_DELAY = 5

SCIENTIFIC_CITATION_TYPES = {
    "article",
    "journal-article",
    "journal article",
    "conference-paper",
    "conference paper",
    "paper",
    "proceedings-article",
    "proceedings article",
    "scholarlyarticle",
    "scholarly article",
}

BIBTEX_ARTICLE_TYPES = {
    "article",
    "inproceedings",
}


def _bibtexValue(value):
    return value.value if hasattr(value, "value") else value


def _parseBibEntry(info):
    bibtex_value = info["result"]["value"]
    bibtex_start = re.search(r"@\w+\s*\{", bibtex_value)
    if bibtex_start is None:
        return None

    bibtex_value = bibtex_value[bibtex_start.start():]
    if hasattr(bibtexparser, "loads"):
        parsed_bib = bibtexparser.loads(bibtex_value)
    else:
        parsed_bib = bibtexparser.parse_string(bibtex_value)

    if not parsed_bib.entries:
        return None

    entry = parsed_bib.entries[0]
    return {
        "type": str(
            _bibtexValue(
                entry.get("ENTRYTYPE")
                or entry.get("entry_type")
                or getattr(entry, "entry_type", "")
            )
        ).lower(),
        "title": _bibtexValue(entry.get("title")),
        "doi": _bibtexValue(entry.get("doi")),
        "url": _bibtexValue(entry.get("url")),
        "author": _bibtexValue(entry.get("author")),
        "language": _bibtexValue(entry.get("langid") or entry.get("language")),
    }


def parseBib(info):
    try:
        entry = _parseBibEntry(info)
        if entry is None:
            return None, None

        return entry["title"], entry["doi"]

    except Exception:
        return None, None


def _queryOpenAlexArticle(query_filter, error_message, openalex_api_key='', work_id=None):
    request_options = {'timeout': 60}
    api_key = (openalex_api_key or '').strip()
    if api_key:
        request_options['headers'] = {'Authorization': f'Bearer {api_key}'}
    for corpus in ("core", "all"):
        for attempt in range(OPENALEX_MAX_RETRIES + 1):
            try:
                response = requests.get(
                    'https://api.openalex.org/works' + (f'/{work_id}' if work_id else ''),
                    params={'corpus': corpus} if work_id else {'filter': query_filter, 'corpus': corpus},
                    **request_options
                )
                if work_id and response.status_code == 404 and corpus == 'core':
                    result = {}
                    break
                response.raise_for_status()
                result = response.json()
            except (requests.RequestException, ValueError) as error:
                error_response = getattr(error, 'response', None)
                status = error_response.status_code if error_response is not None else None
                retryable = (
                    isinstance(error, (requests.ConnectionError, requests.Timeout))
                    or status in (429, 502, 503, 504)
                )
                reason = f'{type(error).__name__}: {error}'
                if error_response is not None:
                    reason += f' | {error_response.text[:500]}'
                if not retryable or attempt == OPENALEX_MAX_RETRIES:
                    print(error_message, reason, f'(corpus={corpus})',
                          file=sys.stderr, flush=True)
                    raise

                delay = OPENALEX_RETRY_DELAY * (2 ** attempt)
                if error_response is not None:
                    header = error_response.headers.get('Retry-After')
                    try:
                        try:
                            server_delay = float(header)
                        except ValueError:
                            server_delay = parsedate_to_datetime(header).timestamp() - time.time()
                        if 0 < server_delay < float('inf'):
                            delay = server_delay
                    except (TypeError, ValueError, OverflowError):
                        pass
                print(
                    f'SALTbot OpenAlex {reason}: retry {attempt + 1}/'
                    f'{OPENALEX_MAX_RETRIES} in {delay}s (corpus={corpus})',
                    file=sys.stderr, flush=True,
                )
                time.sleep(delay)
                continue
            break

        for work in [result] if work_id else result.get('results', []):
            if work.get('type') in OPENALEX_ARTICLE_TYPES:
                if not work_id and work.get('is_authors_truncated') and work.get('id'):
                    return queryOpenAlexById(work['id'], openalex_api_key=openalex_api_key)
                return work

    return None


def queryOpenAlexById(work_id, openalex_api_key=''):
    work_id = str(work_id).rstrip('/').rsplit('/', 1)[-1]
    if not re.fullmatch(r'W[0-9]+', work_id):
        raise ValueError('Invalid OpenAlex work ID')
    return _queryOpenAlexArticle(None, 'OpenAlex work lookup failed:', openalex_api_key, work_id=work_id)


def queryOpenAlex(article, openalex_api_key=''):
    article = article.replace(",", "")
    return _queryOpenAlexArticle(
        'title.search:' + article,
        'OpenAlex query failed:',
        openalex_api_key=openalex_api_key,
    )


def queryOpenAlexByDoi(doi, openalex_api_key=''):
    doi = doi.strip()
    if doi.lower().startswith('doi:'):
        doi = doi[4:]
    if not doi.startswith(('http://', 'https://')):
        doi = 'https://doi.org/' + doi

    return _queryOpenAlexArticle(
        'doi:' + doi,
        'OpenAlex DOI query failed:',
        openalex_api_key=openalex_api_key,
    )


def _citationSources(info, require_url=False):
    citations = info.get("citation", [])
    preferred = []
    for citation in citations:
        techniques = citation.get("technique", [])
        if not isinstance(techniques, list):
            techniques = [techniques]
        if not any(t in {"file_exploration", "regular_expression"} for t in techniques):
            continue

        result = citation.get("result", {})
        value = str(result.get("value", ""))
        if re.search(r"@\w+\s*\{", value):
            continue
        try:
            parsed = yaml.load(value, Loader=SafeLoader)
        except yaml.YAMLError:
            continue
        data = parsed.get("preferred-citation") if isinstance(parsed, dict) else None
        if not isinstance(data, dict):
            continue
        citation_type = str(data.get("type") or result.get("type", "")).strip().lower()
        if citation_type not in SCIENTIFIC_CITATION_TYPES or not str(data.get("title") or "").strip():
            continue
        if require_url and not str(data.get("url") or "").strip():
            continue
        preferred.append(citation)

    return preferred or citations


def parseCitationCandidates(info):
    candidates = []

    for citation in _citationSources(info, require_url=True):
        techniques = citation.get("technique", [])
        if not isinstance(techniques, list):
            techniques = [techniques]
        if not any(
            technique in {"file_exploration", "regular_expression"}
            for technique in techniques
        ):
            continue

        result = citation.get("result", {})
        value = str(result.get("value", "")).strip()
        candidate = None

        if re.search(r"@\w+\s*\{", value):
            try:
                entry = _parseBibEntry(citation)
            except Exception:
                entry = None

            if entry and entry["type"] in BIBTEX_ARTICLE_TYPES:
                candidate = {
                    "title": entry["title"] or result.get("title"),
                    "url": entry["url"] or result.get("url"),
                    "type": entry["type"],
                }
        else:
            try:
                parsed_yaml = yaml.load(value, Loader=SafeLoader)
            except Exception:
                parsed_yaml = None

            if isinstance(parsed_yaml, dict):
                citation_data = parsed_yaml.get("preferred-citation", parsed_yaml)
                if isinstance(citation_data, dict):
                    citation_type = str(
                        citation_data.get("type") or result.get("type", "")
                    ).lower()
                    if citation_type in SCIENTIFIC_CITATION_TYPES:
                        candidate = {
                            "title": citation_data.get("title") or result.get("title"),
                            "url": citation_data.get("url") or result.get("url"),
                            "type": citation_type,
                        }

        if candidate and candidate["title"] and candidate["url"]:
            candidate["title"] = str(candidate["title"]).strip()
            candidate["url"] = str(candidate["url"]).strip()
            if candidate not in candidates:
                candidates.append(candidate)

    return candidates

#returns all the article titles detected
#info: json extracted with somef
def parseTitles(info):
    parsedinfo = []
    DOIs = {}
    article_urls = {}
    article_types = SCIENTIFIC_CITATION_TYPES

    if "citation" not in info:
        return parsedinfo, DOIs, article_urls

    for citation in _citationSources(info):

        techniques = citation["technique"]
        if not isinstance(techniques, list):
            techniques = [techniques]

        if not any(technique in [
            "file_exploration",
            "regular_expression"
        ] for technique in techniques):
            continue

        result = citation["result"]
        value = result.get("value", "").strip()
        fallback_title = result.get("title")
        fallback_doi = result.get("doi")
        fallback_url = result.get("url")
        fallback_type = str(result.get("type", "")).lower()

        # BibTeX
        if re.search(r"@\w+\s*\{", value):
            try:
                entry = _parseBibEntry(citation)
            except Exception:
                entry = None

            if entry is None or entry["type"] not in BIBTEX_ARTICLE_TYPES:
                continue

            title = entry["title"]
            doi = entry["doi"]

            if title:
                print(
                    "DETECTED TITLE:",
                    title,
                    "     TECHNIQUE:",
                    citation["technique"]
                )

                parsedinfo.append(title)

                if doi:
                    DOIs[doi] = title

                article_url = entry["url"] or fallback_url
                if article_url:
                    article_urls[str(article_url).strip()] = title

            continue

        # YAML / CITATION.cff
        try:
            parsed_yaml = yaml.load(
                value,
                Loader=SafeLoader
            )

            if not isinstance(parsed_yaml, dict):
                if fallback_type in article_types and fallback_title and fallback_doi:
                    parsedinfo.append(fallback_title)
                    DOIs[fallback_doi] = fallback_title
                if fallback_type in article_types and fallback_title and fallback_url:
                    article_urls[fallback_url.strip()] = fallback_title
                continue

            if "preferred-citation" in parsed_yaml:
                citation_data = parsed_yaml["preferred-citation"]
            else:
                citation_data = parsed_yaml

            citation_type = str(
                citation_data.get("type", "")
                or result.get("type", "")
            ).lower()
            if citation_type not in article_types:
                if fallback_type in article_types and fallback_title and fallback_doi:
                    parsedinfo.append(fallback_title)
                    DOIs[fallback_doi] = fallback_title
                continue

            title = citation_data.get("title")

            if title:
                print(
                    "DETECTED TITLE:",
                    title,
                    "     TECHNIQUE:",
                    citation["technique"]
                )

                parsedinfo.append(title)

                article_url = citation_data.get("url") or fallback_url
                if article_url:
                    article_urls[article_url.strip()] = title

            doi = citation_data.get("doi") or citation_data.get("DOI")

            if doi and title:
                DOIs[doi] = title

        except Exception as e:
            print(e)

            if fallback_type in article_types and fallback_title and fallback_doi:
                parsedinfo.append(fallback_title)
                DOIs[fallback_doi] = fallback_title

    return list(dict.fromkeys(parsedinfo)), DOIs, article_urls
