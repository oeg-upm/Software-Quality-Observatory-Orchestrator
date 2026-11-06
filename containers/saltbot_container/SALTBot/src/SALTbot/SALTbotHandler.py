import bibtexparser
import yaml
from yaml.loader import SafeLoader
from urllib.parse import urlparse, urlunparse

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator import wbi_login
#from wikiintegrator import wbi_core
from wikibaseintegrator import wbi_helpers
from wikibaseintegrator.datatypes import ExternalID, Item, String, URL, Quantity, Property, CommonsMedia, GlobeCoordinate
from wikibaseintegrator.models import Qualifiers
from wikibaseintegrator.wbi_enums import ActionIfExists

import time
import json
import re
import unicodedata


import click
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup

from . import SALTbotUpdater
from . import SALTbotSearcher
from . import SPARQLQuerys
from . import SALTbotStatementDefiner


WIKIDATA_REQUEST_INTERVAL = 0.5  # seconds
_last_wikidata_request = 0.0
DEFAULT_WIKIDATA_MANDATORY_NODES = {
    'instance of': 'P31',
    'main subject': 'P921',
    'described by source': 'P1343',
    'scholarly article': 'Q13442814',
    'software category': 'Q17155032',
    'software': 'Q7397'
}
DEFAULT_WIKIDATA_OPTIONAL_NODES = {
    'licenses': {},
    'code repository': 'P1324',
    'programming language': 'P277',
    'download url': 'P4945',
    'license': 'P275',
    'version control system': 'P8423',
    'web interface software': 'P10627',
    'Git': 'Q186055',
    'GitHub': 'Q82066181',
    'DOI': 'P356',
    'full work available at URL': 'P953',
    'OpenAlex ID': 'P10283',
    'free software': 'Q341'
}

def waitForWikidataRateLimit():
    global _last_wikidata_request

    elapsed = time.monotonic() - _last_wikidata_request
    remaining = WIKIDATA_REQUEST_INTERVAL - elapsed

    if remaining > 0:
        time.sleep(remaining)

    _last_wikidata_request = time.monotonic()
    
    
def getCorrectQnode(name, Qnodes):
    result = None
    for i in Qnodes:
        if i['label'] == name:
            result = i['id']
        #print(result)
    if result == None and name in ['instance of', 'main subject', 'described by source', 'scholarly article', 'software category', 'software']:
        raise TypeError(str(name)+" was not found on target Wikibase")
    return result

#TODO: change excepts  
def getOptionalNodes(wbi, configData):
    if SPARQLQuerys.isDefaultWikidataConfig(configData):
        return DEFAULT_WIKIDATA_OPTIONAL_NODES.copy()

    return SPARQLQuerys.sparql_getOptionalNodes(configData)
       
def getMandatoryNodes(wbi, configData):
    if SPARQLQuerys.isDefaultWikidataConfig(configData):
        return DEFAULT_WIKIDATA_MANDATORY_NODES.copy()

    try:
        return SPARQLQuerys.sparql_getMandatoryNodes(configData)
    except Exception as e:
        print('SALTbot Error: one or more of the required entities and properties has not been found in the target wikibase')
        print(e)
        raise(e)
#gets possible pnodes of target wikibase to create software pages and returns a list with all the possible statements for that software




#Returns all entities related to entityQnode of class targetClass in the given wikibase
def getRelatedEntities(entityJSON, candidates, property=None): 
    entities = []
    if property==None:
        for prop in entityJSON['claims']:
            for statement in entityJSON['claims'][prop]:
                if statement['mainsnak']['datatype']=='wikibase-item' and statement['mainsnak']['datavalue']['value']['id'] in candidates.keys():
                    entities.append([statement['mainsnak']['datavalue']['value']['id'],candidates[statement['mainsnak']['datavalue']['value']['id']]['labels']['en']['value'], statement['mainsnak']['property']])
            
    return entities


#TODO: uncomment if
# queries the graph for entities with name, which are instance of targetClass. The instance_of pnode has to be passed for integration with other wikibases
def getEntitiesByName(name, targetClass, man_nodes, opt_nodes, configData):
    return SPARQLQuerys.sparql_getEntitiesByName(
        name,
        targetClass,
        man_nodes,
        opt_nodes,
        configData
    )


def getEntitiesByRepositoryUrl(repositoryUrl, targetClass, man_nodes, opt_nodes, configData):
    return SPARQLQuerys.sparql_getEntitiesByRepositoryUrl(
        repositoryUrl,
        targetClass,
        man_nodes,
        opt_nodes,
        configData
    )


def getEntitiesByDoi(doi, targetClass, man_nodes, opt_nodes, configData):
    return SPARQLQuerys.sparql_getEntitiesByDoi(
        doi,
        targetClass,
        man_nodes,
        opt_nodes,
        configData
    )


def getEntitiesByOpenAlexId(openAlexId, targetClass, man_nodes, opt_nodes, configData):
    return SPARQLQuerys.sparql_getEntitiesByOpenAlexId(
        openAlexId,
        targetClass,
        man_nodes,
        opt_nodes,
        configData
    )


def getEntitiesByArticleUrl(articleUrl, targetClass, man_nodes, opt_nodes, configData):
    return SPARQLQuerys.sparql_getEntitiesByArticleUrl(
        articleUrl,
        targetClass,
        man_nodes,
        opt_nodes,
        configData
    )
    



#info: json extracted with somef
#wbi: wbi object with all the graph related info
#articleQnode: the article Qnode in the target wikibase
#softwareQnode: the software Qnode in target wikibase
#instanceofPnode: the instance_of property pnode in target wikibase
#TODO: change operation printing format
def printArticleMatches(articles, openAlex, openAlexMatchMethod):
    for article_id, article in articles.items():
        title = article['labels']['en']['value']
        print(
            f'ARTICLE FOUND IN WIKIDATA: {article_id} | {title} | '
            f'https://www.wikidata.org/wiki/{article_id}'
        )

    if openAlex is not None:
        openalex_url = openAlex['id']
        openalex_id = openalex_url.rstrip('/').rsplit('/', 1)[-1]
        title = openAlex.get('display_name') or openAlex.get('title', '')
        print(
            f'ARTICLE FOUND IN OPENALEX BY {openAlexMatchMethod}: '
            f'{openalex_id} | {title} | {openalex_url}'
        )


def normalizeArticleTitle(title):
    normalized = unicodedata.normalize('NFKC', str(title)).casefold()
    normalized = ''.join(
        character if character.isalnum() else ' '
        for character in normalized
    )
    return ' '.join(normalized.split())


def filterArticleCandidatesByTitle(articles, titles):
    normalized_titles = {
        normalizeArticleTitle(title)
        for title in titles
        if title
    }
    return {
        article_id: article
        for article_id, article in articles.items()
        if normalizeArticleTitle(article['labels']['en']['value'])
        in normalized_titles
    }


def openAlexTitleMatches(openAlex, titles):
    openalex_title = openAlex.get('display_name') or openAlex.get('title')
    if not openalex_title:
        return False

    normalized_openalex_title = normalizeArticleTitle(openalex_title)
    return any(
        normalized_openalex_title == normalizeArticleTitle(title)
        for title in titles
    )


def normalizeArticleUrl(article_url):
    parsed = urlparse(str(article_url).strip())
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip('/'),
        parsed.params,
        parsed.query,
        '',
    ))


def selectCitationArticle(candidates, registry):
    candidates_by_url = {}
    for candidate in candidates:
        normalized_url = normalizeArticleUrl(candidate.get('url', ''))
        if normalized_url:
            candidates_by_url.setdefault(normalized_url, candidate)

    if len(candidates_by_url) != 1:
        if len(candidates_by_url) > 1:
            print(
                'MULTIPLE EXPLICIT SCIENTIFIC CITATIONS FOUND. '
                'NO ARTICLE WILL BE SELECTED AUTOMATICALLY.'
            )
        return None

    normalized_url, candidate = next(iter(candidates_by_url.items()))
    selected = candidate.copy()
    if normalized_url in registry:
        selected['title'] = registry[normalized_url]
        selected['create'] = False
    else:
        registry[normalized_url] = selected['title']
        selected['create'] = True

    return selected


def selectOpenAlexArticle(info, openAlex, registry):
    keys = []
    if openAlex.get('doi'):
        keys.append('doi:' + SPARQLQuerys.normalizeDoi(openAlex['doi']).casefold())
    if openAlex.get('id'):
        keys.append('openalex:' + SPARQLQuerys.normalizeOpenAlexId(openAlex['id']).casefold())

    existing_label = next((registry[key] for key in keys if key in registry), None)
    selected = openAlex.copy()
    selected['create'] = existing_label is None
    selected['_article_label'] = (
        existing_label if existing_label is not None
        else SALTbotStatementDefiner.getArticleLabel(info, openAlex)
    )
    for key in keys:
        registry[key] = selected['_article_label']
    return selected


def getLinkedEntityIds(entity):
    linked_ids = set()
    for claims in entity.get('claims', {}).values():
        for claim in claims:
            mainsnak = claim.get('mainsnak', {})
            if mainsnak.get('datatype') == 'wikibase-item':
                value = mainsnak.get('datavalue', {}).get('value', {})
                if value.get('id'):
                    linked_ids.add(value['id'])
    return linked_ids


def filterSoftwareCandidatesByName(softwares, name, repository_url, repository_property, articles):
    normalized_name = normalizeArticleTitle(name)
    normalized_repository_url = repository_url.rstrip('/').removesuffix('.git').casefold()
    article_ids = set(articles)
    software_ids_linked_from_articles = set().union(
        *(getLinkedEntityIds(article) for article in articles.values())
    ) if articles else set()
    matches = {}

    for software_id, software in softwares.items():
        label = software.get('labels', {}).get('en', {}).get('value', '')
        if normalizeArticleTitle(label) != normalized_name:
            continue

        repository_claims = software.get('claims', {}).get(repository_property, [])
        repository_urls = {
            str(claim['mainsnak']['datavalue']['value'])
            .rstrip('/')
            .removesuffix('.git')
            .casefold()
            for claim in repository_claims
        }
        repository_matches = normalized_repository_url in repository_urls
        article_matches = bool(
            getLinkedEntityIds(software) & article_ids
            or software_id in software_ids_linked_from_articles
        )
        if not repository_matches and not article_matches:
            continue

        matches[software_id] = software

    return matches





def getRepositoryExclusionReason(info):
    for entry in info.get('application_type', []):
        application_type = str(
            entry.get('result', {}).get('value', '')
        ).strip().casefold()

        if application_type == 'ontology':
            return 'Repository classified as ontology by SOMEF'

    return None






def SALTbot(wbi, info, man_nodes, opt_nodes, auto, results, fallback_search=False, configData=None, citation_article_registry=None):

    print("\n")
    click.echo(click.style('SEARCH', fg='red', bold=True))
    print("\n")

    #print(man_nodes)
    #print(opt_nodes)


    articles = {}
    softwares = {}

    parsedTitles, DOIs, articleUrls = SALTbotSearcher.parseTitles(info)
    citationCandidates = SALTbotSearcher.parseCitationCandidates(info)
    for candidate in citationCandidates:
        if candidate['title'] not in parsedTitles:
            parsedTitles.append(candidate['title'])
        articleUrls.setdefault(candidate['url'], candidate['title'])
    openAlex = None
    openAlexMatchMethod = None
    citationArticle = None
    #print('parsedTitles: ', parsedTitles)
    results.update({info['code_repository'][0]['result']['value']:{'repo-article':[], 'article':None, 'software':None, 'article-software-link':False, 'software-article-link':False}})
    
    exclusion_reason = getRepositoryExclusionReason(info)
    if exclusion_reason:
        print(f'SKIPPING REPOSITORY: {exclusion_reason}', flush=True)
        return []

    #print('parsedTitles', parsedTitles)

    if parsedTitles == []:
        print("NO DETECTED SCIENTIFIC ARTICLE TITLES")

        if not fallback_search:
            print("FALLBACK SEARCH DISABLED. SALTbot will not search Wikidata by repository name.")
            return []
    for title in parsedTitles:
        results[info['code_repository'][0]['result']['value']]['repo-article'].append(title)

    article_auto = [False, '']

    for doi in DOIs:
        articles.update(
            getEntitiesByDoi(
                doi,
                man_nodes['scholarly article'],
                man_nodes,
                opt_nodes,
                configData
            )
        )

    if len(articles) == 1:
        article_auto = [True, 'DOI match']

    if articles == {}:
        for article_url in articleUrls:
            articles.update(
                getEntitiesByArticleUrl(
                    article_url,
                    man_nodes['scholarly article'],
                    man_nodes,
                    opt_nodes,
                    configData
                )
            )

        if len(articles) == 1:
            article_auto = [True, 'article URL match']

    if articles == {}:
        title_candidates = {}
        for title in parsedTitles:
            title_candidates.update(
                getEntitiesByName(
                    title,
                    man_nodes['scholarly article'],
                    man_nodes,
                    opt_nodes,
                    configData
                )
            )
        articles = filterArticleCandidatesByTitle(
            title_candidates,
            parsedTitles
        )

        discarded_candidates = len(title_candidates) - len(articles)
        if discarded_candidates > 0:
            print(
                'DISCARDED',
                discarded_candidates,
                'WIKIDATA ARTICLE CANDIDATE(S) WITHOUT AN EXACT TITLE MATCH'
            )

        if auto and len(articles) > 1:
            print(
                'MULTIPLE EXACT WIKIDATA TITLE MATCHES FOUND. '
                'TRYING OPENALEX IN AUTO MODE.'
            )
            articles = {}

    name = info['name'][0]['result']['value']

    if articles == {} and parsedTitles == []:
        articles.update(
            getEntitiesByName(
                name,
                man_nodes['scholarly article'],
                man_nodes,
                opt_nodes,
                configData
            )
        )

    #print('ARTICLES: ', articles)

    repository_url = info['code_repository'][0]['result']['value']
    if opt_nodes.get('code repository') not in [None, [], '']:
        softwares = getEntitiesByRepositoryUrl(
            repository_url,
            man_nodes['software category'],
            man_nodes,
            opt_nodes,
            configData
        )

    if softwares == {}:
        name_candidates = getEntitiesByName(
            name,
            man_nodes['software category'],
            man_nodes,
            opt_nodes,
            configData
        )
        name_candidates = filterSoftwareCandidatesByName(
            name_candidates,
            name,
            repository_url,
            opt_nodes.get('code repository'),
            articles
        )
        if len(name_candidates) == 1:
            softwares = name_candidates
        elif len(name_candidates) > 1:
            print(
                'MULTIPLE EXACT SOFTWARE NAME MATCHES FOUND. '
                'NO SOFTWARE WILL BE SELECTED AUTOMATICALLY.'
            )

    software_auto = [False, '']
    if len(softwares) == 1:
        software_auto = [True, 'URL or unique exact name match']


    if articles == {}:
        for doi in DOIs:
            openAlex = SALTbotSearcher.queryOpenAlexByDoi(doi)
            if openAlex is not None:
                openAlexMatchMethod = 'DOI'
                break

        if openAlex is None:
            for title in parsedTitles:
                candidate = SALTbotSearcher.queryOpenAlex(title)
                if candidate is not None and openAlexTitleMatches(
                    candidate,
                    parsedTitles
                ):
                    openAlex = candidate
                    openAlexMatchMethod = 'TITLE'
                    break
                if candidate is not None:
                    print(
                        'DISCARDED OPENALEX ARTICLE CANDIDATE WITHOUT '
                        'AN EXACT TITLE MATCH'
                    )

        if openAlex is not None and openAlex.get('doi'):
            openalex_doi = openAlex['doi']
            searched_dois = {
                SPARQLQuerys.normalizeDoi(doi).casefold()
                for doi in DOIs
            }
            normalized_openalex_doi = (
                SPARQLQuerys.normalizeDoi(openalex_doi).casefold()
            )

            if normalized_openalex_doi not in searched_dois:
                articles.update(
                    getEntitiesByDoi(
                        openalex_doi,
                        man_nodes['scholarly article'],
                        man_nodes,
                        opt_nodes,
                        configData
                    )
                )

                if len(articles) == 1:
                    article_auto = [True, 'OpenAlex DOI match']

        if openAlex is not None and articles == {} and openAlex.get('id'):
            openalex_id = openAlex['id'].rstrip('/').rsplit('/', 1)[-1]
            articles.update(
                getEntitiesByOpenAlexId(
                    openalex_id,
                    man_nodes['scholarly article'],
                    man_nodes,
                    opt_nodes,
                    configData
                )
            )

            if len(articles) == 1:
                article_auto = [True, 'OpenAlex ID match']

    if articles == {} and openAlex is not None and citation_article_registry is not None:
        openAlex = selectOpenAlexArticle(info, openAlex, citation_article_registry)
        if not openAlex['create']:
            print('REUSING ARTICLE FOUND IN OPENALEX:', openAlex['_article_label'])

    if articles == {} and openAlex is None:
        citationArticle = selectCitationArticle(
            citationCandidates,
            citation_article_registry if citation_article_registry is not None else {},
        )
        if citationArticle is not None:
            action = 'CREATING' if citationArticle['create'] else 'REUSING'
            print(
                f'{action} ARTICLE FROM EXPLICIT SCIENTIFIC CITATION: '
                f'{citationArticle["title"]} | {citationArticle["url"]}'
            )
    
    print("\n")
    click.echo(click.style('RESULTS', bold = True))
    if articles == {}:
        print('NO ARTICLES FOUND ON TARGET WIKIBASE')
    
    printArticleMatches(articles, openAlex, openAlexMatchMethod)

    if softwares == {}:
        print('NO SOFTWARE FOUND ON TARGET WIKIBASE')
    for i in softwares.keys():
        print('SOFTWARE FOUND: ',i, ' : ', softwares[i]['labels']['en']['value'])


    

    
    
    article_links = {}
    software_links = {}

    for article in articles:
        
        #article_links[article] = getRelatedEntities( article, softwareQnode, mainSubjectPnode, instanceOfPnode, wbi)
        article_links[article] = getRelatedEntities(articles[article], softwares)
    
    for software in softwares:
        software_links[software] =  getRelatedEntities(softwares[software], articles)

    if article_links != {} or software_links !={}:
        print("\n")
        click.echo(click.style('CLASIFICATION', fg='red', bold = True))
        print("\n")
        click.echo(click.style('ENTITIES LINKED: ', bold=True))

    for i in article_links:
        for j in article_links[i]:
            print('ARTICLE [', i, ':', articles[i]['labels']['en']['value'], '] IS LINKED WITH SOFTWARE [', j[0], ':', j[1], '] THROUGH PROPERTY [', j[2],']')
    for i in software_links:
        for j in software_links[i]:
            print('SOFTWARE [', i, ':', softwares[i]['labels']['en']['value'], '] IS LINKED WITH ARTICLE [', j[0], ':', j[1], '] THROUGH PROPERTY [', j[2], ']')


    if openAlex is None and articles == {} and citationArticle is None:
        print("NO SCIENTIFIC ARTICLE FOUND IN WIKIBASE OR OPENALEX. SALTBOT WILL NOT INTRODUCE SOFTWARE-ONLY STATEMENTS")
        return []
    operation_list = SALTbotStatementDefiner.defineOperations(info, article_links, software_links,[auto, article_auto, software_auto], man_nodes, opt_nodes, results, openAlex, configData, wbi, citationArticle)
    
        
    return operation_list

        
        
    


    





  
