# Changelog

## Local changes

### SOMEF integration & use of it
- Describe new articles from OpenAlex abstracts through Ollama, validating 1–250 characters while requesting under 200 characters and 20 words only in the prompt; retain a fallback on failure.
- Summarize each newly created article once per `describe` run through the existing shared-article registry; preserve descriptions of existing Wikidata entities.
- Summarize SOMEF descriptions longer than 250 characters through Ollama, accepting summaries up to 250 characters and retaining the default description on failure.
- Added optional `OPENALEX_API_KEY` configuration and Bearer authentication for OpenAlex searches, including retries and corpus fallbacks.
- Updated somef -> 0.11.4
- Added optional `GITHUB_API_TOKEN` support in `saltbot configure` by `saltbot configure` cli && ``configure_from_env.sh`` script
- `describe` now passes the GitHub token to SOMEF using `--github-token` when configured
- Replaced SOMEF `os.system(...)` calls with `subprocess.run([...], check=True)` while preserving SOMEF console logs
- Added clearer SOMEF execution error messages
- Now if SOMEF classifies repositories as `ontology`, they will not be processed

### Research of articles & software
- Preserve a matching scientific SOMEF citation URL as `P953` for new OpenAlex articles when their result lacks `url`, including CEUR papers.
- Generate ordered software author names (`P2093`/`P1545`) exclusively from root CFF authors when creating new software.
- Generate article titles (`P1476`) and ordered author names (`P2093`/`P1545`) when creating new articles.
- Restore existing-entity behavior: reuse existing articles/software and add missing links only; remove Action API metadata enrichment reads from `describe`.
- Author metadata prioritizes scientific preferred-citation, citation and BibTeX over OpenAlex; unknown title languages use `und` rather than assuming English.
- Prioritize valid scientific `preferred-citation` metadata within SOMEF `citation` over BibTeX for article searches and creation fallbacks.
- Added support for repositories whose `preferred-citation` provides a CEUR article title and URL.
- Added a final title-and-URL fallback for explicit scientific citations and deduplicated article creation by normalized publication URL.
- Deduplicate OpenAlex article creation across repositories by normalized DOI or OpenAlex ID, reusing one article reference for all software links in the same run.
- Software lookup prioritizes an exact repository URL (`P1324`); its exact-name fallback requires a unique candidate linked to the detected article.
- SALTbot now selects only the first recognized SPDX license when SOMEF reports multiple license detections.
- Changed WikidataApi queries -> WikidataSPARQLApi queries in the command `saltbot describe` to avoid API rate limits
- Split `sparql_getEntitiesByName` candidate-detail SPARQL queries per entity and aggregates the results to reduce Wikidata query load
- Split repository URL SPARQL lookup into candidate discovery and per-entity detail queries, using direct URL matching instead of `FILTER(STR(...))`
- Split publication URL (`P953`) lookup into candidate discovery and per-entity class validation to avoid expensive gateway timeouts.
- Increased the SPARQL request interval to 5 seconds to reduce `429 Too Many Requests` responses
- Simplified SPARQL rate limiting to a fixed sleep and retries `Retry-After` HTTP error responses up to 3 times
- Retry SPARQL HTTP 502/503/504 errors up to three times, preferring `Retry-After` or waiting 5/10/20 seconds while preserving rate limiting before every attempt.
- Retry SPARQL SSL/connection errors and timeouts up to three times with 5/10/20-second delays and rate limiting before each attempt.
- Check OpenAlex HTTP responses and retry transient failures up to three times; exhausted API errors fail the repository instead of triggering citation-only article creation.
- Added SPARQL HTTPError logging with endpoint and response body before re-raising the exception
- Extracts article titles and DOIs from embedded BibTeX and SOMEF citation metadata fallbacks.
- Article discovery uses exact DOI, publication URL (`P953`) and title matches before OpenAlex; title fallbacks must match exactly after normalization.
- OpenAlex results are checked again in Wikidata by DOI and OpenAlex ID (`P10283`) before creating a new article.
- Added an OpenAlex `core`-to-`all` corpus fallback with scholarly type validation to find expansion-only articles without accepting software or datasets.
- Added entity-specific descriptions when SOMEF omits `description`, preserving complete article and software creation operations.
- Ignored `type: software` citations when looking for scholarly articles
- Prevented software-only operations when no scientific article is found
- Updated the bibtex parser in order to using a newer version

### Internal Data management
- Added `status.json` output to monitor `saltbot describe` execution progress and per-repository failures.
- Added `structured_operations.json` to inspect generated operations grouped by repository/SOMEF metadata file.
- Now SALTBot generates a diferent operation_list.txt and results.txt for different softwares. with the formats `repoOrg_repoName_operation_list.txt` && `repoOrg_repoName_result.txts` 

### General
- Log MediaWiki error code, info and messages with request context to expose detailed creation and save failures.
- Space Wikidata creation and save requests by at least 15 seconds to respect new-account write limits, including failed attempts.
- Support `MonolingualText`, `String` and typed qualifiers in operation files, keeping legacy item qualifier pairs compatible.
- Validate update files before login, convert typed claims and qualifiers, and use description fallbacks including the article title when they fit Wikidata's 250-character limit.
- Report failed/pending operations with nonzero exit status and contextual WBI wait logs; always preserve source operation files.
- Added `remove_statement` operations to remove exact statement GUIDs, grouped by entity, while preserving the entities and unrelated statements.
- Stopped generating software download URL (`P4945`) statements, preserving repository and article URLs.
- Normalized repository/download URLs before generating URL statements
- Normalized article DOI values and emits DOI as `ExternalID`
- Added `ExternalID` handling in the updater.
- Improved logs when article and software are already linked or when no operations are generated
- Added a wikidata rateLimit (0.5s) between requests to not overwhelm WikidataApi
- Changed SALTBot internal logic: if somef does not detect articles related to the repository, SALTBOT will stop its execution
- Added flag `--fallback-search`: if somef does not detect articles related to the repository, SALTBot searchs in Wikidata if there are articles related to the repository name
- Added batch update support through saltbot update ``--operations-dir operations``. This mode merges all ``operations/*_operations.txt`` files into ``final_operation_list.txt``, overwriting it on each run.
The update is then executed from the merged file, while the existing ``--file`` mode remains available for single-repository updates.
If no operation files are found, SALTBot exits without logging in or writing to Wikidata.
- Fixed minor bugs related to the reading of somef extractions
- Implemented SALTBot dockerization
