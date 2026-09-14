[![DOI]\(https\://zenodo.org/badge/DOI/10.5281/zenodo.18879858.svg)]\(https\://doi.org/10.5281/zenodo.18879858)[![Project Status: Active ]\(https\://www\.repostatus.org/badges/latest/active.svg)]\(https\://www\.repostatus.org/#active)[![License]\(https\://img.shields.io/badge/license-Apache%202.0-blue.svg)]\(https\://www\.apache.org/licenses/LICENSE-2.0)[![GitHub release]\(https\://img.shields.io/github/v/release/SergioZSZ/Software-Quality-Observatory-Orchestrator-TFG?include\_prereleases)]\(https\://github.com/SergioZSZ/Software-Quality-Observatory-Orchestrator-TFG/releases)![RSFC\_Coverage]\(https\://img.shields.io/badge/rsfc-coverage\_83%25-green)



Detailed documentation at : https\://software-quality-observatory-orchestrator-tfg.readthedocs.io/es/latest/

**# TFG – Automated software assessment orchestration and catalog generation**





**## 1. Project objective**

The objective of the project is to design and implement a reproducible system that:

1\. Automatically extracts GitHub repositories

2\. Generates structured software metadata

3\. Assesses software quality using automated indicators

4\. Assesses the quality of software metadata and, if enabled, creates automatic Issues on GitHub

5\. Prepares the information for integration into dashboards (DashVERSE) and catalogs (SOCA)

6\. Allows the entire process to be orchestrated through automated workflows

The system is based on the integration and orchestration of existing tools within a decoupled and reproducible architecture.

\---





**## 2. System architecture**

\| Component       | Role                                    |

\| ---------------- | -------------------------------------- |

\| n8n              | Orchestration of the modular workflow and its subworkflows |

\| SOCA              | Incremental discovery, metadata and software portal |

\| RSFC              | Assessment of software FAIR indicators |

\| RESQUI            | Configurable assessment using QualityPipelines |

\| RabbitMQ          | Distribution of jobs among workers |

\| workers           | Parallel processing of SOCA, RSFC and RESQUI |

\| rate limiters     | Control of GitHub requests for RSFC and RESQUI |

\| Nginx             | Publication of the SOCA portal |

\| sw-metadata-bot   | Incremental metadata assessment and optional issues |

\| DashVERSE         | Persistence and visualization of assessments |









Each tool runs in its own isolated environment, ensuring:

\- Reproducibility

\- Portability

\- Operating system independence

\- Dependency isolation

\- Scalability

\---



**## Development and integrations**

**### SOCA**

The \`soca-heavy\` image includes SOCA 0.0.4 and SOMEF 0.11.2. \`soca\_runner.main\` receives a project, GitHub organizations or users and additional repositories.

The runner maintains \`repository-state.json\` and separates the inventory into updated and removed repositories. It only publishes jobs for updated repositories; workers extract the metadata in staging and promote the result atomically. A failure preserves the previous result and is reflected in \`status.json\`.

Workers are scaled with:

\`\`\`bash

docker compose up -d --scale worker\_soca=N

\`\`\`

At the end, \`soca\_runner.genportal\` combines the metadata with the quality results. Nginx publishes the portals at \`http\://localhost:8030/portals/\<project>/\`.

**### RSFC**

The \`rsfc-heavy\` image uses RSFC 0.1.8 and reuses SOCA metadata when available. The worker looks for the JSON at \`outputs/soca/\<project>/metadata/\<owner>\_\<repo>\_\*.json\`, passes it to RSFC with \`--metadata\` and, if it does not exist, runs RSFC with the normal repository analysis. The launcher publishes updated repositories to \`rsfc\_jobs\` and removes outputs from removed repositories.

Each worker:

1\. Waits for a token from the rate limiter when it is enabled.

2\. Runs RSFC in staging.

3\. Validates \`rsfc\_output/rsfc\_assessment.json\`.

4\. Promotes the result or generates \`failed\_assessment.json\` without deleting the previous one.

5\. Updates \`status.json\` under lock.

Results are stored in \`outputs/rsfc/\<project>/\<owner>\_\<repo>/\`.

**### RESQUI**

\`resqui-heavy\` includes QualityPipelines as a submodule and is part of the modular workflow. Its workers consume \`resqui\_jobs\`, run the selected configuration and store \`resqui\_summary.json\` in \`outputs/resqui/\<project>/\<owner>\_\<repo>/\`.

The \`sqoo\_resqui\_work\` volume allows the worker and plugin containers to share the workspace. \`RESQUI\_SHARED\_WORKDIR\` and \`RESQUI\_DOCKER\_WORK\_VOLUME\` configure this behavior.

RESQUI uses the same staging, state and removed-result deletion pattern as RSFC. The available configurations are located in \`containers/resqui\_container/resqui\_runner/configurations/\` and are selected from \`containers/.env\` with \`RESQUI\_CONF\`, using the filename without the \`.json\` extension.

**### sw-metadata-bot**

The \`sw-metadata-bot\:latest\` and \`sw-metadata-bot-conf\:latest\` images contain sw-metadata-bot 0.5.3 and the required NLTK/SOMEF resources.

n8n generates a \`config.json\` with the complete inventory. The bot locates the previous snapshot, compares commits and copies the artifacts from unchanged repositories. Reports are stored in \`outputs/sw-metadata-bot/\<project>/runs/\<snapshot>/\`.

\`launch\_issue\` separates analysis from publication: if it is \`false\`, \`sw-metadata-bot publish\` is not called.

**### DashVERSE and portal**

\`dashverse\_workflow\.json\` reads RSFC and RESQUI assessments, fills in \`@id\` and \`author\`, and publishes them to the DashVERSE API using \`DASHVERSE\_JWT\`.

The portal includes:

\- SOCA metadata;

\- RSFC and RESQUI reports;

\- sw-metadata-bot reports and issues;

\- links to the DashVERSE dashboards.

Dashboard identifiers and the Superset domain are configured with \`DASHBOARD\_ORG\_EMBED\_ID\`, \`DASHBOARD\_REPO\_EMBED\_ID\` and \`SUPERSET\_PUBLIC\_DOMAIN\`.





**## 4. n8n modular workflow**

\`SQOO\_modular\_workflow\.json\` is the only main workflow. It orchestrates, in this order, \`soca\_workflow\.json\`, \`rsfc\_workflow\.json\`, \`resqui\_workflow\.json\`, \`sw-metadata-bot\_workfow\.json\` and \`dashverse\_workflow\.json\`.

The \`Conf\` node defines:

\- \`project\`: stable name for the execution.

\- \`organizations\`: GitHub organizations or users, indicating \`org\` and \`type\`.

\- \`extra\_repositories\`: additional repositories.

\- \`launch\_issue\`: enables or disables issue publication.

**### Stages**

1\. SOCA queries GitHub and compares the inventory with \`repository-state.json\`. It generates \`repos.txt\`, \`repos-updated.txt\` and \`repos-removed.txt\`.

2\. \`If has changes\` continues the pipeline when there are updated or removed repositories; if there are no changes, it consolidates the state directly.

3\. Only new or modified repositories go through the SOCA, RSFC and RESQUI workers. Removed repositories are deleted from their persisted outputs.

4\. RSFC and RESQUI store results by \`owner\_repo\` and report batch status through \`status.json\`; per-repository failures are recorded in \`failed\_repos\` without stopping the pipeline.

5\. sw-metadata-bot receives the complete inventory, reuses the previous snapshot for unchanged repositories and publishes issues only if \`launch\_issue\` is enabled.

6\. SOCA generates the enriched portal, which Nginx publishes at \`http\://localhost:8030/portals/\<project>/\`.

7\. \`If repo updated\` calls DashVERSE only if new assessments exist; an execution containing only removals goes directly to consolidation.

8\. The pending state is consolidated as \`repository-state.json\` only when the pipeline finishes.

\---









**## 5. Requirements**

**### Orchestrator**

\- Docker Engine or Docker Desktop with Compose v2.

\- Python 3.11 or 3.12 for local development.

\- Git with submodule support.

\- GitHub token recommended to avoid the rate limit and publish issues.

On Windows, Docker Desktop must have WSL integration enabled if DashVERSE is deployed.

**### DashVERSE**

DashVERSE 0.3.0 is deployed from Linux on local Kubernetes with Minikube. All \`kubectl\`, \`minikube\`, \`tofu\`, \`ansible-playbook\` and \`just\` commands must be run from the same environment to share the Kubernetes context.

Requirements principales:

\- Docker Engine with Compose v2 or Podman for the DashVERSE images.

\- Git.

\- Minikube.

\- kubectl.

\- Helm.

\- OpenTofu (\`tofu\`).

\- Ansible (\`ansible-playbook\`).

\- Just.

\- Python.

\- curl.

\- jq.

\- base64.

\- zip and unzip.

\- netcat (\`nc\`).

Installation of common utilities on Debian/Ubuntu:

\`\`\`bash

sudo apt update

sudo apt install -y \\

  git \\

  curl \\

  jq \\

  unzip \\

  zip \\

  ansible \\

  netcat-openbsd \\

  python3 \\

  python3-venv

\`\`\`

In addition, Docker or Podman, Minikube, kubectl, Helm, OpenTofu and Just must be installed.

Check from the DashVERSE root:

\`\`\`bash

cd integrations/DashVERSE

just check-deps

\`\`\`









**#### Tools used in the project:**

\- SOCA 0.0.4:

https\://github.com/oeg-upm/soca/releases

\- RSFC 0.1.8:

https\://github.com/oeg-upm/rsfc/releases/tag/v0.1.8

\- SOMEF 0.11.1:

https\://github.com/KnowledgeCaptureAndDiscovery/somef/releases/tag/0.11.1

\- DASHVERSE 0.3.0: 

https\://github.com/EVERSE-ResearchSoftware/DashVERSE/releases/tag/v0.3.0

\- sw-metadata-bot 0.5.3:

https\://github.com/SoftwareUnderstanding/sw-metadata-bot/releases/tag/v0.5.3

\- RsMetaCheck >=0.3.3:

https\://github.com/SoftwareUnderstanding/RsMetaCheck/releases



\---



**## 6. Installation/Deployment**

**#### 6.1 Prerequisites**

 A \`.env\` file must be created in the \`/containers\` directory containing the environment variables: 

   - \`GITHUB\_API\_TOKEN\`: personal GitHub token; to publish issues it must allow access to public repositories

   - \`RABBITMQ\_USER\` RabbitMQ user set in the \`rabbitmq\` service of \`/containers/docker-compose.yml\`

   - \`RABBITMQ\_PASSWORD\` RabbitMQ password set in the \`rabbitmq\` service of \`/containers/docker-compose.yml\`

   - \`RATE\_LIMIT\_RSFC\_ENABLED\` set true/false depending on whether the limiter for workers making GitHub API requests should be enabled

   - \`RATE\_LIMIT\_RESQUI\_ENABLED\` set true/false depending on whether the limiter for RESQUI workers making GitHub API requests should be enabled

   - \`RESQUI\_CONF\` name of the RESQUI configuration to use from \`containers/resqui\_container/resqui\_runner/configurations/\`, without the \`.json\` extension. For example, \`RESQUI\_CONF=complete\_no\_rsfc\_superlinter\` will load \`complete\_no\_rsfc\_superlinter.json\`.

   - \`OUTPUTS\` path to the directory to use as a shared volume (it must be called \`\`outputs\`\` and be inside the \`/containers\` directory)

   - \`PORTAL\_PORT\` host port from which Nginx publishes the SOCA portals (default \`8030\`)

   - \`DASHBOARD\_ORG\_EMBED\_ID\` id or slug of the global dashboard imported into DashVERSE/Superset (default \`global\`)

   - \`DASHBOARD\_REPO\_EMBED\_ID\` id or slug of the SQO-repo dashboard imported into DashVERSE/Superset (default \`assessments\`)

      both values correspond to DashVERSE default dashboards

   - \`DASHVERSE\_JWT\` token generated by the DashVERSE API to publish assessments from n8n

   - \`SUPERSET\_PUBLIC\_DOMAIN\` public domain used by the browser to load the dashboards. Locally, \`http\://localhost:8088\` is used.

      The \`/containers/.env.example\` file contains all required names; tokens, paths and dashboard identifiers must be replaced.



**\*\*Keep in mind\*\***:  

\-  The token (classic) must be obtained from GitHub with the 'public\_repo' scope selected. otherwise, using that token will produce an error. It can be left empty but only 50 requests per hour can be made to the GitHub API (not recommended, many repos = error) and Issues cannot be created automatically.

\-  The dashboard number or slug is the one shown after importing into DashVERSE the template contained in \`/integrations/dashboard\`. Dashboards must be published and allow embedding from the portal.



**#### 6.2 Installation/Deployment del orquestador**

Following the steps in sequential order:

The images can be built with \`scripts/build-docker-images.sh\` on WSL/Linux or \`scripts/build-docker-images.ps1\` in PowerShell. The equivalent commands are:

0\. Import the repository submodules:

   - SQOO uses \`containers/resqui\_container/QualityPipelines-2.0\` as a submodule to include the RESQUI/QualityPipelines source code.

   - If cloning the repository from scratch, use:

      - Command: \`git clone --recurse-submodules https\://github.com/SergioZSZ/Software-Quality-Observatory-Orchestrator-TFG.git\`

   - If the repository was already cloned or \`git pull\` was just run, execute from the SQOO root:

      - Command: \`git submodule update --init --recursive\`

   - To check that the submodule has been downloaded:

      - Command: \`git submodule status\`

1\. Build Docker images:

   - \`soca-heavy\`:

      - Directory from which to build it: \`/containers/soca\_container\` 

      - Command: \`docker build -t soca-heavy .\`

   - \`rsfc-heavy\`:

      - Directory from which to build it: \`/containers/rsfc\_container\` 

      - Command: \`docker build -t rsfc-heavy .\`

   - \`sw-metadata-bot\`:

      - Directory from which to build it: \`/integrations/sw-metadata-bot-0.5.3\`

      - Command: \`docker build -t sw-metadata-bot .\`

   - \`sw-metadata-bot-conf\`:

      - Directory from which to build it: \`/containers/sw-metadata-bot\_container\` 

      - Command: \`docker build -t sw-metadata-bot-conf .\`

   - \`resqui-heavy\`:

      - Directory from which to build it: \`/containers/resqui\_container\`

      - Command: \`docker build -t resqui-heavy .\`

   These are the SQOO orchestrator images. DashVERSE's own images (\`dashverse/backend\` and \`dashverse/frontend\`) are not built with these scripts: \`just deploy\` builds them from \`integrations/DashVERSE\` using \`minikube image build\`.

2\. From the \`/containers\` directory, run the command in the terminal \`docker compose up -d --scale worker\_rsfc=N --scale worker\_soca=N --scale worker\_resqui=N\`, where N is the number of workers to launch (if it is the first deployment, use the \`--build\` flag )

   The RESQUI service uses the named Docker volume \`sqoo\_resqui\_work\` mounted as \`/resqui-work\`. This volume allows the \`resqui-heavy\` worker and Docker containers launched by RESQUI plugins to share the same workspace. It should not be replaced with a local bind mount if RESQUI is to be run inside Docker with plugins.

3\. Access n8n through the browser at http\://localhost:5678

4\. On first access:

    1. Create a user account in n8n

    2. Import the workflows from \`/containers/n8n\_container/workflows/\`

5\. Import and use the modular workflow:

   - Import \`SQOO\_modular\_workflow\.json\` and the subworkflows \`soca\_workflow\.json\`, \`rsfc\_workflow\.json\`, \`resqui\_workflow\.json\`, \`sw-metadata-bot\_workfow\.json\` and \`dashverse\_workflow\.json\`.

   - Then review the \`Call '\<subworkflow>'\` nodes in the main workflow so they point to the subworkflows imported into the n8n instance.

6\. Edit the initial configuration node with the desired organization/user:

   - \`project\`: stable name for outputs and incremental state.

   - \`organizations\`: list of objects with \`org\` and \`type\` (\`org\` or \`user\`).

   - \`extra\_repositories\`: optional list of additional URLs.

   - \`launch\_issue\`: \`true\` to publish issues with \`sw-metadata-bot publish\`, \`false\` to run metadata analysis only.

7\. Run manually

After that, \`outputs\` contains SOCA metadata, RSFC and RESQUI assessments, sw-metadata-bot snapshots and the final portal. Nginx serves the portal at \`http\://localhost:8030/portals/\<project>/\`.





**## Installation/Deployment DashVERSE 0.3.0**

**### 1. Enter DashVERSE**

From the SQOO repository root:

\`\`\`bash

cd integrations/DashVERSE

\`\`\`

Check the available commands:

\`\`\`bash

just --list

\`\`\`

Check dependencies:

\`\`\`bash

just check-deps

\`\`\`

**### 2. Start Minikube**

\`\`\`bash

minikube config set driver docker

minikube start --cpus=4 --memory=4096 --driver=docker

\`\`\`

Check the status:

\`\`\`bash

minikube status

kubectl get ns

\`\`\`

**### 3. Deploy DashVERSE**

\`\`\`bash

just forward\_address=0.0.0.0 deploy

\`\`\`

This command performs the complete deployment:

\- checks dependencies;

\- checks or starts Minikube;

\- builds the backend and frontend images inside the Minikube runtime;

\- applies the infrastructure with OpenTofu;

\- configures the port-forwards;

\- synchronizes the EVERSE indicator and dimension catalog;

\- imports dashboards, charts and datasets into Superset.

If deployment fails during dashboard import with \`zip: not found\`:

\`\`\`bash

sudo apt update

sudo apt install -y zip unzip

just setup-dashboards

\`\`\`

**### 4. Check services**

\`\`\`bash

just status

\`\`\`

View generated credentials:

\`\`\`bash

just show-access

\`\`\`

View general logs:

\`\`\`bash

just logs

\`\`\`

Specific logs:

\`\`\`bash

just logs-postgres

just logs-postgrest

just logs-superset

just logs-backend

just logs-frontend

\`\`\`

**### 5. Exposed URLs**

With active port-forwards, the following services are exposed:

\- DashVERSE frontend: \`http\://localhost:8080\`

\- Superset: \`http\://localhost:8088\`

\- Assessments API: \`http\://localhost:3000\`

\- Authentication/backend API: \`http\://localhost:8000\`

\- PostgREST documentation: \`http\://localhost:3001\`

\- Backend documentation: \`http\://localhost:8001\`

Quick checks:

\`\`\`bash

curl -I http\://localhost:8088/health

curl http\://localhost:3000/

\`\`\`

**### 6. Create user**

Access the backend:

\`\`\`text

http\://localhost:8000

\`\`\`

Create a user for SQOO, for example:

\`\`\`text

username: sqoo

email: sqoo\@example.org

password: \<password>

\`\`\`

**### 7. Generate the JWT token**

DashVERSE 0.3.0 includes a quick command to generate the JWT:

\`\`\`bash

just jwt \<user> '\<password>'

\`\`\`

Example:

\`\`\`bash

just jwt sqoo '\<password>'

\`\`\`





**### 8. Configure SQOO**

In \`containers/.env\`, configure:

\`\`\`env

DASHVERSE\_JWT=\<token\_generated\_with\_just\_jwt>

SUPERSET\_PUBLIC\_DOMAIN=http\://localhost:8088

\`\`\`

**### 9. Reimport dashboards or resynchronize catalog**

Reimport Superset dashboards:

\`\`\`bash

just setup-dashboards

\`\`\`

Resynchronize EVERSE indicators and dimensions:

\`\`\`bash

just trigger-sync

\`\`\`

**### 10. Stop and subsequent startup**

Stop Minikube:

\`\`\`bash

minikube stop

\`\`\`

Start again:

\`\`\`bash

minikube start --driver=docker

\`\`\`

Check the port-forward service:

\`\`\`bash

just port-forward-status

\`\`\`

If the port-forwards are not active:

\`\`\`bash

just forward\_address=0.0.0.0 port-forward

\`\`\`







**## 7. Studies on the project**





**\*\*Worker parallelism assessment:\*\*** 

https\://software-quality-observatory-orchestrator-tfg.readthedocs.io/es/latest/estudios/#estudio-sobre-el-paralelismo-de-workers

**\*\*Study on RAM and device storage:\*\***

*\*In progress\**

\---



**## 8. Support**

For any problem, open an issue at:

https\://github.com/oeg-upm/Software-Quality-Observatory-Orchestrator-TFG/issues