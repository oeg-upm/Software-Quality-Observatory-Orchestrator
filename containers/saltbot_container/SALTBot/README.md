# SALTbot: Software and Article Linker Toolbot
[![Project Status: Active – The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active) [![DOI](https://zenodo.org/badge/490763453.svg)](https://zenodo.org/badge/latestdoi/490763453)


## DESCRIPTION

  This repository contains the implementation of a tool designed to link Scientific Articles and their Software pages on Wikibase graphs.
  
  SALTBot is proposed as a Wikidata bot, with its own page [here](https://www.wikidata.org/wiki/User:SALTbot). It is maintained and run by the Ontology Engineering Group and Universidad Politécnica de Madrid.


## REQUIRENMENTS
- Python >=3.11,<3.13
- poetry: `pip install poetry`
- Docker in case you want to use it by Docker image

## INSTALLATION
    
  1. Clone repository: `git clone https://github.com/SoftwareUnderstanding/SALTbot`
  
  **Recomendation:** config poetry to have the environments inside the repository `poetry config virtualenvs.in-project true --local`
  2. inside the repository, install the poetry environment: `poetry install`
3. Enable the environment: `. .venv/bin/activate` 
4. Configure Saltbot:
  - Manually: execute `saltbot configure` & fill the features
  - By Script:create the `.env` file (use .env.example as template)  & fill the features:
      ```
      MEDIAWIKI_API_URL= 
      WIKIBASE_USER= # Mandatory, your wikibase user bot
      WIKIBASE_PASSWORD=  # Mandatory, your wikibase user pwd
      GITHUB_API_TOKEN=   # Recommended, due to GithubApiLimits
      OPENALEX_API_KEY=   # Optional, authenticates OpenAlex article searches
      SPARQL_ENDPOINT_URL=
      WIKIBASE_URL=
      ``` 
  after that, run the script `configure_from_env.sh`

`saltbot configure` accepts an optional OpenAlex API key, defaulting to `OPENALEX_API_KEY` from the environment. The configuration script reads the same variable; article searches send it as a Bearer header on every request and retry. Existing configurations without this key continue using anonymous OpenAlex access.

If you want to use the docker implementation create the docker image: `docker build -t saltbot .` 

  
 
  


*MODIFICAR USAGE*

## USAGE
### Configure
Before running SALTbot, you must first configure your login credentials and wikibase using the configure command
```console
python SALTbot.py configure
```
You can invoke this command using -a as argument to skip the Wikibase configuration and target Wikidata automatically 
SALTbot will then prompt you for you login information and the required wikibase URLs. If left blank, the URLs will default to Wikidata's respective values
An example of the Wikibase configuration using Wikidatas values would be the following

```console
MEDIAWIKI_API_URL = https://www.wikidata.org/w/api.php
SPARQL_ENDPOINT_URL = https://query.wikidata.org/
WIKIBASE_URL = https://www.wikidata.org
```
### Running
Once configured, execute SALTbot using

```console
python SALTbot.py run  [ARGS]
```

 For more info, run:
 ```console
 python SALTbot.py [COMMAND] --help
 ```
 
### Description summaries with Ollama

For new software, when the first nonempty SOMEF description exceeds 250 characters, `describe` calls `llm_requests.fallback_desc_llm()` to request a neutral English summary from Ollama's `/api/generate` endpoint. Set `LLM_MODEL` inside the SALTBot process; `OLLAMA_HOST` defaults to `http://ollama:11434` and can point to `http://localhost:11434` for local execution. The model must already be available in Ollama. Docker containers must share a network, and n8n's environment variables must be explicitly forwarded to each `docker run`.

Software descriptions of up to 250 characters and missing descriptions keep their existing behavior. Generated software summaries must contain 1 to 250 characters after whitespace normalization. A missing model setting, HTTP/connection error, timeout, invalid JSON or invalid summary logs the reason and retains the existing default description. Requests have a 5-second connection timeout and a 180-second read timeout, without retries.

New articles use a separate prompt: SALTBot reconstructs `abstract_inverted_index` from the OpenAlex work already returned by the search and asks Ollama to summarize that abstract in English. Both software and article prompts request at most 20 words and fewer than 200 characters to leave a margin; validation only requires 1 to 250 characters after whitespace normalization, accepting longer word counts within that character limit. Missing or malformed abstracts skip Ollama; request failures and invalid summaries use `scientific article associated with the software <name>`, bounded to the same character limit. Article descriptions never reuse SOMEF software descriptions. Citation-only papers, including CEUR papers without an OpenAlex abstract, use this fallback; PDFs are not downloaded.

The shared-article registry generates one article creation and description per DOI, OpenAlex ID or publication URL within a `describe` run. Existing articles and software retain their descriptions, and SALTBot only proposes missing links. There is no persistent description cache: repeating `describe` before publishing a new article may call Ollama again.

When creating an article found in OpenAlex, a missing `url` is filled from an explicit scientific SOMEF citation whose title matches after normalization, allowing `P953` to retain CEUR publication URLs. Existing result URLs are preserved; software citations and citations with different titles are not used. This fallback adds no API calls and does not enrich existing Wikidata entities.

### Updating Wikidata

Run `saltbot update --file operation_list.txt`; review the operations and confirm with `y`. Add `--auto` to skip confirmation. Alternatively, `--operations-dir operations` combines `*_operations.txt` files into `final_operation_list.txt`. Source files are always preserved, including after success or cancellation; retaining them does not make it safe to execute them twice.

The UTF-8 TXT contains one Python literal per nonempty line: `['create', {'LABEL': ..., 'DESCRIPTION': ...}]` or `['statement', {'s': ..., 'p': ..., 'o': ..., 'datatype': 'Item'|'URL'|'ExternalID'|'String'|'MonolingualText', 'qualifiers': None|[[item_id, property_id], ...]}]`. Labels used as temporary references must be created before their statements. The whole file is validated before login; labels and descriptions must contain 1–250 characters. Regenerate older files with `describe` if their descriptions are too long. New software descriptions come from SOMEF and new article descriptions from OpenAlex abstracts, following the Ollama rules above. Software fallbacks include the article title when the complete phrase fits within 250 characters; otherwise, or when no title is available, they use a generic research-software description.

New article creation generates `P1476` titles (`MonolingualText`, with an explicit `language`) and `P2093` author names (`String`), ordered with `P1545` string qualifiers. Authors come first from the matching scientific `preferred-citation`, then other scientific citations, then BibTeX; OpenAlex authorships are the final fallback. Software contributors are not used as publication authors. BibTeX author lists must use `and`; ambiguous nonstandard lists are skipped with a diagnostic instead of publishing several people as one author. The title uses the source language or `und` when unknown. Author entities are never created or matched by name.

Existing articles and software retain SALTBot's linking behavior: reuse existing entities, create only missing ones and propose only missing links between them. If both entities are already linked in both directions, no operations are generated. `describe` does not load existing entities through the Action API to inspect or fill titles or authors. Normal discovery and link checks remain in place. Truncated OpenAlex search authorships are retrieved through the single-work endpoint for new article creation; API failures remain visible as repository failures.

New software authors use only the root `authors` list in the CFF extracted into SOMEF `citation`, as `P2093` names with `P1545` order qualifiers. `preferred-citation.authors` belongs to the article and is never used for software authorship; generic SOMEF `author` detections are also ignored. These statements are generated only during software creation. Missing CFF authors produce no author statements.

Typed qualifiers such as `{"datatype": "String", "p": "P1545", "o": "1"}` are supported alongside legacy `[item_id, property_id]` pairs. `MonolingualText` statements require `language`; other statement values remain in `o`. Regenerate operations after upgrading and review them before running `update`; title and author proposals apply only to newly created entities.

To remove one existing statement, use `['remove_statement', {'s': 'Q123', 'id': 'Q123$D70A4206-C983-4905-90C1-7C49766FAB79'}]`, replacing the example with the real entity and statement GUID. Only that GUID is removed; the entity, labels, descriptions and other statements remain. An already absent statement is a no-op. Removals are grouped by entity and require the same confirmation as additions.

Prepared statements are saved together per entity. The updater logs confirmed saves and prints failed or dependent pending operations to stderr, including their input operation number, entity and exception type. Any failures produce a nonzero exit status so callers such as n8n can detect an incomplete update; independent operations may already have been saved. Preserve the logs, for example with `2>&1 | tee update.log`, and reconcile existing QIDs before retrying a partial run. The `status.json` produced by `describe` does not track `update`.

Wait messages include the action (`LOGIN`, `LOAD`, `CREATE` or `SAVE`), target, observed retry count and elapsed seconds, followed by WikibaseIntegrator's original reason and pause. Existing retry limits and `maxlag` remain unchanged. The updater does not provide automatic resumption or general duplicate prevention. Use offline tests first and run real writes separately, since Wikidata can impose long waits.

 ## Citation
 If you use SALTbot, please use the following citation:
 ```
 @article{bolinches2023saltbot,
  title		   = {SALTBot: Linking Software and Articles in Wikidata},
  author	   = {Bolinches, Jorge and Garijo, Daniel},
  year         = {2023},
  booktitle    = {Proceedings of the Wikidata Workshop 2023 co-located with 22nd International Semantic Web Conference (ISWC 2023)},
  publisher    = {CEUR-WS.org},
  series       = {{CEUR} Workshop Proceedings},
  volume       = {3640},
  url          = {https://ceur-ws.org/Vol-3640/paper12.pdf}
}

 ```

  
