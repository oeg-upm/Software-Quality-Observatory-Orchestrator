[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18879858.svg)](https://doi.org/10.5281/zenodo.18879858)[![Project Status: Active ](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)[![GitHub release](https://img.shields.io/github/v/release/oeg-upm/Software-Quality-Observatory-Orchestrator?include_prereleases)](https://github.com/oeg-upm/Software-Quality-Observatory-Orchestrator/releases)![RSFC_Coverage](https://img.shields.io/badge/rsfc-coverage_83%25-green)

# Software Quality Observatory Orchestrator

Detailed documentation: <https://software-quality-observatory-orchestrator-tfg.readthedocs.io/es/latest/>

## 1. Project Objective

The objective of the project is to design and implement a reproducible system that:

1. Automatically extracts GitHub repositories.
2. Generates structured software metadata.
3. Assesses software quality using automated indicators.
4. Assesses the quality of software metadata and, if enabled, creates automatic issues on GitHub.
5. Prepares the information for integration into dashboards (DashVERSE) and catalogs (SOCA).
6. Allows the entire process to be orchestrated through automated workflows.
7. Links software to scientific articles and optionally updates Wikidata through SALTBot.

The system is based on the integration and orchestration of existing tools within a decoupled and reproducible architecture.

## 2. System Architecture

| Component | Role |
| --- | --- |
| n8n | Orchestration of the modular workflow and its subworkflows |
| SOCA | Incremental discovery, metadata and software portal |
| RSFC | Assessment of software FAIR indicators |
| RESQUI | Configurable assessment using QualityPipelines |
| RabbitMQ | Distribution of jobs among workers |
| Workers | Parallel processing of SOCA, RSFC and RESQUI |
| Rate limiters | Control of GitHub requests for RSFC and RESQUI |
| Nginx | Publication of the SOCA portal |
| rsmetacheck-bot | Incremental metadata assessment and optional issues |
| SALTBot | Software and article linking, with optional Wikidata updates |
| Ollama | Local generation of short descriptions for SALTBot |
| DashVERSE | Persistence and visualization of assessments |

Each tool runs in its own isolated environment, ensuring:

- Reproducibility.
- Portability.
- Operating system independence.
- Dependency isolation.
- Scalability.

## 3. Development and Integrations

### SOCA

The `soca-heavy` image includes SOCA 0.0.4 and SOMEF 0.11.5. `soca_runner.main` receives a project, GitHub organizations or users, and additional repositories.

The runner maintains `repository-state.json` and separates the inventory into updated and removed repositories. It only publishes jobs for updated repositories; workers extract the metadata in staging and promote the result atomically. A failure preserves the previous result and is reflected in `status.json`.

Workers are scaled with:

```bash
docker compose up -d --scale worker_soca=N
```

At the end, `soca_runner.genportal` combines the metadata with the quality results. Nginx publishes the portals at `http://localhost:8030/portals/<project>/`.

### RSFC

The `rsfc-heavy` image uses RSFC 0.2.2 and reuses SOCA metadata when available. The worker looks for the JSON at `outputs/soca/<project>/metadata/<owner>_<repo>_*.json`, passes it to RSFC with `--metadata` and, if it does not exist, runs RSFC with the normal repository analysis. The launcher publishes updated repositories to `rsfc_jobs` and removes outputs from removed repositories.

Each worker:

1. Waits for a token from the rate limiter when it is enabled.
2. Runs RSFC in staging.
3. Validates `rsfc_output/rsfc_assessment.json`.
4. Promotes the result or generates `failed_assessment.json` without deleting the previous one.
5. Updates `status.json` under lock.

Results are stored in `outputs/rsfc/<project>/<owner>_<repo>/`.

### RESQUI

`resqui-heavy` includes QualityPipelines/RESQUI as vendored raw source under `containers/resqui_container/QualityPipelines` and is part of the modular workflow. The local source corresponds to upstream commit `98eb8efb83bd17e8e020bf11e8195b204c9453fd` from `EVERSE-ResearchSoftware/QualityPipelines` `main`. Its workers consume `resqui_jobs`, run the selected configuration and store `resqui_summary.json` in `outputs/resqui/<project>/<owner>_<repo>/`.

The `sqoo_resqui_work` volume allows the worker and plugin containers to share the workspace. `RESQUI_SHARED_WORKDIR` and `RESQUI_DOCKER_WORK_VOLUME` configure this behavior.

RESQUI uses the same staging, state and removed-result deletion pattern as RSFC. The available configurations are located in `containers/resqui_container/resqui_runner/configurations/` and are selected from `containers/.env` with `RESQUI_CONF`, using the filename without the `.json` extension.

### rsmetacheck-bot

The `rsmetacheck-bot:latest` and `rsmetacheck-bot-conf:latest` images contain rsmetacheck-bot 0.6.2 and the required NLTK/SOMEF resources.

n8n generates a `config.json` with the complete inventory. The bot locates the previous snapshot, compares commits and copies the artifacts from unchanged repositories. Reports are stored in `outputs/sw-metadata-bot/<project>/runs/<snapshot>/`; this path is kept for compatibility with the SOCA portal even though the executable is now `rsmetacheck-bot`.

`launch_issue` separates analysis from publication: if it is `false`, `rsmetacheck-bot publish` is not called.

### SALTBot

`saltbot-heavy` processes SOMEF metadata from SOCA, finds scientific articles in Wikidata or OpenAlex and generates operations to link them to the software. `status.json` tracks execution and `structured_operations.json` groups operations by repository. A failed repository does not stop the rest of the batch.

`update_wikidata` controls publication. Ollama summarizes long software descriptions and available OpenAlex abstracts, accepting descriptions of up to 250 characters. See [SALTBot](docs/saltbot.md) for filters, outputs and update behavior.

### DashVERSE and Portal

`dashverse_workflow.json` reads RSFC and RESQUI assessments, fills in `@id` and `author`, and publishes them to the DashVERSE API using `DASHVERSE_JWT`.

The portal includes:

- SOCA metadata.
- RSFC and RESQUI reports.
- rsmetacheck-bot reports and issues.
- Links to the DashVERSE dashboards.

Dashboard identifiers and the Superset domain are configured with `DASHBOARD_ORG_EMBED_ID`, `DASHBOARD_REPO_EMBED_ID` and `SUPERSET_PUBLIC_DOMAIN`.

## 4. n8n Modular Workflow

`SQOO_modular_workflow.json` is the only main workflow. It orchestrates, in this order, `soca_workflow.json`, `rsfc_workflow.json`, `resqui_workflow.json`, `rsmetacheck-bot_workfow.json`, `saltbot_workflow.json` and `dashverse_workflow.json`.

The `Conf` node defines:

- `project`: stable name for the execution.
- `organizations`: GitHub organizations or users, indicating `org` and `type`.
- `extra_repositories`: additional repositories.
- `launch_issue`: enables or disables issue publication.
- `update_wikidata`: enables or disables SALTBot updates to Wikidata.
- `linkeddata_tools`: YAML file with the repository list for the linked-data portal.

### Stages

1. SOCA queries GitHub and compares the inventory with `repository-state.json`. It generates `repos.txt`, `repos-updated.txt` and `repos-removed.txt`.
2. `If has changes` continues the pipeline when there are updated or removed repositories; if there are no changes, it consolidates the state directly.
3. Only new or modified repositories go through the SOCA, RSFC and RESQUI workers. Removed repositories are deleted from their persisted outputs.
4. RSFC and RESQUI store results by `owner_repo` and report batch status through `status.json`; per-repository failures are recorded in `failed_repos` without stopping the pipeline.
5. rsmetacheck-bot receives the complete inventory, reuses the previous snapshot for unchanged repositories and publishes issues only if `launch_issue` is enabled.
6. SALTBot generates linking operations and applies them when `update_wikidata` is enabled and the operation file has content.
7. SOCA generates the enriched portal at `http://localhost:8030/portals/<project>/` and the linked-data portal from `linkeddata_tools`.
8. `If repo updated` calls DashVERSE only if new assessments exist; an execution containing only removals goes directly to consolidation.
9. The pending state is consolidated as `repository-state.json` only when the pipeline finishes.

## 5. Requirements

### Orchestrator

- Docker Engine or Docker Desktop with Compose v2.
- Python 3.11 or 3.12 for local development.
- Git.
- GitHub token recommended to avoid the rate limit and publish issues.

On Windows, Docker Desktop must have WSL integration enabled if DashVERSE is deployed.

### DashVERSE

DashVERSE 0.3.0 is deployed from Linux on local Kubernetes with Minikube. All `kubectl`, `minikube`, `tofu`, `ansible-playbook` and `just` commands must be run from the same environment to share the Kubernetes context.

Main requirements:

- Docker Engine with Compose v2 or Podman for the DashVERSE images.
- Git.
- Minikube.
- kubectl.
- Helm.
- OpenTofu (`tofu`).
- Ansible (`ansible-playbook`).
- Just.
- Python.
- curl.
- jq.
- base64.
- zip and unzip.
- netcat (`nc`).

Installation of common utilities on Debian/Ubuntu:

```bash
sudo apt update
sudo apt install -y \
  git \
  curl \
  jq \
  unzip \
  zip \
  ansible \
  netcat-openbsd \
  python3 \
  python3-venv
```

In addition, Docker or Podman, Minikube, kubectl, Helm, OpenTofu and Just must be installed.

Check from the DashVERSE root:

```bash
cd integrations/DashVERSE
just check-deps
```

### Tools Used in the Project

- SOCA 0.0.4: <https://github.com/oeg-upm/soca/releases>
- RSFC 0.2.2: <https://github.com/oeg-upm/rsfc/releases>
- SOMEF 0.11.5: <https://github.com/KnowledgeCaptureAndDiscovery/somef/releases/tag/0.11.5>
- DashVERSE 0.3.0: <https://github.com/EVERSE-ResearchSoftware/DashVERSE/releases/tag/v0.3.0>
- rsmetacheck-bot 0.6.2: <https://github.com/SoftwareUnderstanding/rsmetacheck-bot/releases>
- RsMetaCheck >= 0.3.8: <https://github.com/SoftwareUnderstanding/rsmetacheck/releases>
- SALTBot and Ollama: software/article linking and local description generation.

## 6. Installation and Deployment

### 6.1 Prerequisites

A `.env` file must be created in the `containers` directory containing the environment variables:

- `GITHUB_API_TOKEN`: personal GitHub token; to publish issues it must allow access to public repositories.
- `RABBITMQ_USER`: RabbitMQ user set in the `rabbitmq` service of `containers/docker-compose.yml`.
- `RABBITMQ_PASSWORD`: RabbitMQ password set in the `rabbitmq` service of `containers/docker-compose.yml`.
- `RATE_LIMIT_RSFC_ENABLED`: set to `true` or `false` depending on whether the limiter for workers making GitHub API requests should be enabled.
- `RATE_LIMIT_RESQUI_ENABLED`: set to `true` or `false` depending on whether the limiter for RESQUI workers making GitHub API requests should be enabled.
- `RESQUI_CONF`: name of the RESQUI configuration to use from `containers/resqui_container/resqui_runner/configurations/`, without the `.json` extension. For example, `RESQUI_CONF=complete_no_rsfc` will load `complete_no_rsfc.json`.
- `OUTPUTS`: path to the directory to use as a shared volume. It must be called `outputs` and be inside the `containers` directory.
- `PORTAL_PORT`: host port from which Nginx publishes the SOCA portals. Default: `8030`.
- `DASHBOARD_ORG_EMBED_ID`: ID or slug of the global dashboard imported into DashVERSE/Superset. Default: `global`.
- `DASHBOARD_REPO_EMBED_ID`: ID or slug of the SQO-repo dashboard imported into DashVERSE/Superset. Default: `assessments`.
- `DASHVERSE_JWT`: token generated by the DashVERSE API to publish assessments from n8n.
- `SUPERSET_PUBLIC_DOMAIN`: public domain used by the browser to load the dashboards. Locally, `http://localhost:8088` is used.
- `WIKIBASE_USER` and `WIKIBASE_PASSWORD`: account and bot password used by SALTBot.
- `OPENALEX_API_KEY`: optional OpenAlex API key to reduce anonymous request limits.
- `LLM_MODEL`: Ollama model name, for example `qwen3.5:4b`.

`containers/.env.example` contains all required names. Tokens, paths and dashboard identifiers must be replaced.

Keep in mind:

- The classic GitHub token must be obtained with the `public_repo` scope selected. Otherwise, using that token will produce an error. It can be left empty, but only 50 requests per hour can be made to the GitHub API, which is not recommended for many repositories, and issues cannot be created automatically.
- The dashboard number or slug is the one shown after importing into DashVERSE the template contained in `integrations/dashboards`. Dashboards must be published and allow embedding from the portal.

### 6.2 Orchestrator Installation and Deployment

Follow these steps in order.

#### 1. Build Docker images

The images can be built with `scripts/build-docker-images.sh` on WSL/Linux or `scripts/build-docker-images.ps1` in PowerShell.

Equivalent commands:

```bash
docker build -t soca-heavy containers/soca_container
docker build -t rsfc-heavy containers/rsfc_container
docker build -t resqui-heavy containers/resqui_container
docker build -t rsmetacheck-bot integrations/rsmetacheck-bot
docker build -t rsmetacheck-bot-conf containers/rsmetacheck-bot_container
docker build -t saltbot-heavy containers/saltbot_container/SALTBot
```

These are the SQOO orchestrator images. DashVERSE's own images (`dashverse/backend` and `dashverse/frontend`) are not built with these scripts: `just deploy` builds them from `integrations/DashVERSE` using `minikube image build`.

#### 2. Start the orchestrator

From the `containers` directory, run:

```bash
docker compose up -d --scale worker_rsfc=N --scale worker_soca=N --scale worker_resqui=N
```

If it is the first deployment, add the `--build` flag.

For OEG, use `docker compose -f docker-compose.oeg.yml up -d`; this keeps n8n on host networking. `ollama-init` downloads `LLM_MODEL` into the persistent `ollama_data` volume. Wait for the download and check it with `docker exec ollama ollama list` before running SALTBot.

The RESQUI service uses the named Docker volume `sqoo_resqui_work` mounted as `/resqui-work`. This volume allows the `resqui-heavy` worker and Docker containers launched by RESQUI plugins to share the same workspace. It should not be replaced with a local bind mount if RESQUI is to be run inside Docker with plugins.

#### 3. Access n8n

Open n8n in the browser:

```text
http://localhost:5678
```

#### 4. First access

1. Create a user account in n8n.
2. Import the workflows from `containers/n8n_container/workflows/`.

#### 5. Import and use the modular workflow

Import `SQOO_modular_workflow.json` and the subworkflows `soca_workflow.json`, `rsfc_workflow.json`, `resqui_workflow.json`, `rsmetacheck-bot_workfow.json`, `saltbot_workflow.json` and `dashverse_workflow.json`.

Then review the `Call '<subworkflow>'` nodes in the main workflow so they point to the subworkflows imported into the n8n instance.

Also check expressions referring to other nodes: their names must match the imported workflows, including any `V2` suffixes.

#### 6. Edit the initial configuration node

Configure the desired organization or user:

- `project`: stable name for outputs and incremental state.
- `organizations`: list of objects with `org` and `type` (`org` or `user`).
- `extra_repositories`: optional list of additional URLs.
- `launch_issue`: `true` to publish issues with `rsmetacheck-bot publish`, `false` to run metadata analysis only.
- `update_wikidata`: keep `false` to review SALTBot operations before publishing them.
- `linkeddata_tools`: container path to the linked-data portal YAML, for example `/app/outputs/linkeddata_tools.yml`.

#### 7. Run manually

After that, `outputs` contains SOCA metadata, RSFC and RESQUI assessments, rsmetacheck-bot snapshots and the final portal. Nginx serves the portal at `http://localhost:8030/portals/<project>/`.

## 7. DashVERSE 0.3.0 Installation and Deployment

### 7.1 Enter DashVERSE

From the SQOO repository root:

```bash
cd integrations/DashVERSE
```

Check the available commands:

```bash
just --list
```

Check dependencies:

```bash
just check-deps
```

### 7.2 Start Minikube

```bash
minikube config set driver docker
minikube start --cpus=4 --memory=4096 --driver=docker
```

Check the status:

```bash
minikube status
kubectl get ns
```

### 7.3 Deploy DashVERSE

```bash
just forward_address=0.0.0.0 deploy
```

This command performs the complete deployment:

- Checks dependencies.
- Checks or starts Minikube.
- Builds the backend and frontend images inside the Minikube runtime.
- Applies the infrastructure with OpenTofu.
- Configures the port-forwards.
- Synchronizes the EVERSE indicator and dimension catalog.
- Imports dashboards, charts and datasets into Superset.

If deployment fails during dashboard import with `zip: not found`:

```bash
sudo apt update
sudo apt install -y zip unzip
just setup-dashboards
```

### 7.4 Check services

```bash
just status
```

View generated credentials:

```bash
just show-access
```

View general logs:

```bash
just logs
```

Specific logs:

```bash
just logs-postgres
just logs-postgrest
just logs-superset
just logs-backend
just logs-frontend
```

### 7.5 Exposed URLs

With active port-forwards, the following services are exposed:

- DashVERSE frontend: `http://localhost:8080`
- Superset: `http://localhost:8088`
- Assessments API: `http://localhost:3000`
- Authentication/backend API: `http://localhost:8000`
- PostgREST documentation: `http://localhost:3001`
- Backend documentation: `http://localhost:8001`

Quick checks:

```bash
curl -I http://localhost:8088/health
curl http://localhost:3000/
```

### 7.6 Create user

Access the backend:

```text
http://localhost:8000
```

Create a user for SQOO, for example:

```text
username: sqoo
email: sqoo@example.org
password: <password>
```

### 7.7 Generate the JWT token

DashVERSE 0.3.0 includes a quick command to generate the JWT:

```bash
just jwt <user> '<password>'
```

Example:

```bash
just jwt sqoo '<password>'
```

### 7.8 Configure SQOO

In `containers/.env`, configure:

```env
DASHVERSE_JWT=<token_generated_with_just_jwt>
SUPERSET_PUBLIC_DOMAIN=http://localhost:8088
```

### 7.9 Reimport dashboards or resynchronize catalog

From `integrations/DashVERSE`, reimport Superset dashboards or retry step 10 of `just deploy`:

```bash
just setup-dashboards
```

Resynchronize EVERSE indicators and dimensions:

```bash
just trigger-sync
```

### 7.10 Stop and subsequent startup

Stop Minikube:

```bash
minikube stop
```

Start again:

```bash
minikube start --driver=docker
```

Check the port-forward service:

```bash
just port-forward-status
```

If the port-forwards are not active:

```bash
just forward_address=0.0.0.0 port-forward
```

## 8. Usage 

Once SQOO is deployed, open n8n at `http://localhost:5678`, select `SQOO_modular_workflow` and edit the raw JSON in the `Conf` node. For example:

```json
{
  "project": "oeg-quality",
  "organizations": [
    {"org": "oeg-upm", "type": "org"}
  ],
  "extra_repositories": [
    "https://github.com/EVERSE-ResearchSoftware/DashVERSE"
  ],
  "launch_issue": false,
  "update_wikidata": false,
  "linkeddata_tools": "/app/outputs/linkeddata_tools.yml"
}
```

| Field | Purpose |
| --- | --- |
| `project` | Stable name used for output directories and incremental state. |
| `organizations` | GitHub organizations or users to discover; `type` must be `org` or `user`. |
| `extra_repositories` | Additional GitHub repository URLs; use `[]` when none are needed. |
| `launch_issue` | When `true`, rsmetacheck-bot publishes GitHub issues. |
| `update_wikidata` | When `true`, SALTBot applies its generated updates to the configured Wikibase instance. |
| `linkeddata_tools` | Container path to the YAML configuration used to generate the linked-data portal. |

Click **Execute workflow** and follow the execution in n8n. Results are written below `containers/outputs/<component>/<project>/`, and the generated portal is available at `http://localhost:8030/portals/<project>/`. Keep `launch_issue` and `update_wikidata` set to `false` unless external writes are intended and the required credentials are configured.

SALTBot can summarize SOMEF descriptions longer than 250 characters through Ollama. Pass `LLM_MODEL` into the SALTBot container and optionally set `OLLAMA_HOST` (default: `http://ollama:11434`); the model must already be available and reachable. Invalid summaries or request failures retain the existing default description. See [deployment configuration](docs/instalacion.md).

Both Compose variants include Ollama, an initializer that downloads `LLM_MODEL` into persistent storage, and the n8n backup mounts. Wait for the model download to finish before running SALTBot; the OEG variant retains host networking for n8n.

## 9. Studies on the Project

### Worker Parallelism Assessment

<https://software-quality-observatory-orchestrator-tfg.readthedocs.io/es/latest/estudios/#estudio-sobre-el-paralelismo-de-workers>

### Study on RAM and Device Storage

**In progress**

## 10. Support

For any problem, open an issue at:

<https://github.com/oeg-upm/Software-Quality-Observatory-Orchestrator/issues>
