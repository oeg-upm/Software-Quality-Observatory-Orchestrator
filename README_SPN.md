[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18879858.svg)](https://doi.org/10.5281/zenodo.18879858)[![Project Status: Active ](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)[![GitHub release](https://img.shields.io/github/v/release/SergioZSZ/Software-Quality-Observatory-Orchestrator-TFG?include_prereleases)](https://github.com/SergioZSZ/Software-Quality-Observatory-Orchestrator-TFG/releases)![RSFC_Coverage](https://img.shields.io/badge/rsfc-coverage_83%25-green)


Documentación detallada en : https://software-quality-observatory-orchestrator-tfg.readthedocs.io/es/latest/

# TFG – Orquestación automatizada de evaluación de software y generación de catálogo



## 1. Objetivo del proyecto

El objetivo del proyecto es diseñar e implementar un sistema reproducible que:

1. Extraiga automáticamente repositorios de GitHub
2. Genere metadatos estructurados del software
3. Evalúe la calidad del software mediante indicadores automáticos
4. Evalúe la calidad de los metadatos del software y, si se habilita, suba Issues automáticas a GitHub
5. Prepare la información para su integración en dashboards (DashVERSE) y catálogos (SOCA)
6. Permita orquestar todo el proceso mediante workflows automatizados

El sistema se basa en la integración y orquestación de herramientas existentes dentro de una arquitectura desacoplada y reproducible.

---



## 2. Arquitectura del sistema

| Componente       | Rol                                    |
| ---------------- | -------------------------------------- |
| n8n              | Orquestación del workflow modular y sus subworkflows |
| SOCA              | Descubrimiento incremental, metadatos y portal software |
| RSFC              | Evaluación de indicadores FAIR de software |
| RESQUI            | Evaluación configurable mediante QualityPipelines |
| RabbitMQ          | Distribución de trabajos entre workers |
| workers           | Procesamiento paralelo de SOCA, RSFC y RESQUI |
| rate limiters     | Control de peticiones a GitHub para RSFC y RESQUI |
| Nginx             | Publicación del portal SOCA |
| sw-metadata-bot   | Evaluación incremental de metadatos e issues opcionales |
| DashVERSE         | Persistencia y visualización de assessments |





Cada herramienta se ejecuta en su propio entorno aislado, garantizando:

- Reproducibilidad
- Portabilidad
- Independencia del sistema operativo
- Aislamiento de dependencias
- Escalabilidad

---


## Desarrollo e integraciones

### SOCA

La imagen `soca-heavy` incorpora SOCA 0.0.4 y SOMEF 0.11.2. `soca_runner.main` recibe un proyecto, organizaciones o usuarios de GitHub y repositorios adicionales.

El runner mantiene `repository-state.json` y separa el inventario en repositorios actualizados y eliminados. Solo publica trabajos para los actualizados; los workers extraen los metadatos en staging y promueven el resultado de forma atómica. Un fallo conserva el resultado anterior y queda reflejado en `status.json`.

Los workers se escalan con:

```bash
docker compose up -d --scale worker_soca=N
```

Al final, `soca_runner.genportal` combina los metadatos con los resultados de calidad. Nginx publica los portales en `http://localhost:8030/portals/<project>/`.

### RSFC

La imagen `rsfc-heavy` utiliza RSFC 0.1.8 y reutiliza los metadatos SOCA cuando están disponibles. El worker busca el JSON de `outputs/soca/<project>/metadata/<owner>_<repo>_*.json`, lo pasa a RSFC con `--metadata` y, si no existe, ejecuta RSFC con el análisis normal del repositorio. El launcher publica los repositorios actualizados en `rsfc_jobs` y elimina las salidas de los repositorios retirados.

Cada worker:

1. Espera un token del rate limiter cuando está activado.
2. Ejecuta RSFC en staging.
3. Valida `rsfc_output/rsfc_assessment.json`.
4. Promueve el resultado o genera `failed_assessment.json` sin borrar el anterior.
5. Actualiza `status.json` bajo bloqueo.

Los resultados se guardan en `outputs/rsfc/<project>/<owner>_<repo>/`.

### RESQUI

`resqui-heavy` incorpora QualityPipelines como submódulo y forma parte del workflow modular. Sus workers consumen `resqui_jobs`, ejecutan la configuración seleccionada y guardan `resqui_summary.json` en `outputs/resqui/<project>/<owner>_<repo>/`.

El volumen `sqoo_resqui_work` permite que el worker y los contenedores de plugins compartan el workspace. `RESQUI_SHARED_WORKDIR` y `RESQUI_DOCKER_WORK_VOLUME` configuran este comportamiento.

RESQUI utiliza el mismo patrón de staging, estado y eliminación de resultados retirados que RSFC. Las configuraciones disponibles se encuentran en `containers/resqui_container/resqui_runner/configurations/` y se seleccionan desde `containers/.env` con `RESQUI_CONF`, usando el nombre del fichero sin la extension `.json`.

### sw-metadata-bot

Las imágenes `sw-metadata-bot:latest` y `sw-metadata-bot-conf:latest` contienen sw-metadata-bot 0.5.3 y los recursos NLTK/SOMEF necesarios.

n8n genera un `config.json` con el inventario completo. El bot localiza la snapshot anterior, compara commits y copia los artefactos de repositorios sin cambios. Los informes se guardan en `outputs/sw-metadata-bot/<project>/runs/<snapshot>/`.

`launch_issue` separa el análisis de la publicación: si es `false`, no se llama a `sw-metadata-bot publish`.

### DashVERSE y portal

`dashverse_workflow.json` lee los assessments de RSFC y RESQUI, completa `@id` y `author`, y publica en la API de DashVERSE usando `DASHVERSE_JWT`.

El portal incorpora:

- metadatos SOCA;
- informes de RSFC y RESQUI;
- informes e issues de sw-metadata-bot;
- accesos a los dashboards de dashverse.

Los identificadores de dashboards y el dominio de Superset se configuran con `DASHBOARD_ORG_EMBED_ID`, `DASHBOARD_REPO_EMBED_ID` y `SUPERSET_PUBLIC_DOMAIN`.



## 4. Workflow modular de n8n

`SQOO_modular_workflow.json` es el único workflow principal. Orquesta, en este orden, `soca_workflow.json`, `rsfc_workflow.json`, `resqui_workflow.json`, `sw-metadata-bot_workfow.json` y `dashverse_workflow.json`.

El nodo `Conf` define:

- `project`: nombre estable de la ejecución.
- `organizations`: organizaciones o usuarios de GitHub, indicando `org` y `type`.
- `extra_repositories`: repositorios adicionales.
- `launch_issue`: activa o desactiva la publicación de issues.

### Etapas

1. SOCA consulta GitHub y compara el inventario con `repository-state.json`. Genera `repos.txt`, `repos-updated.txt` y `repos-removed.txt`.
2. `If has changes` continúa el pipeline cuando hay repositorios actualizados o eliminados; si no hay cambios, consolida directamente el estado.
3. Solo los repositorios nuevos o modificados pasan por los workers de SOCA, RSFC y RESQUI. Los retirados se eliminan de sus salidas persistidas.
4. RSFC y RESQUI guardan resultados por `owner_repo` y notifican el estado del lote mediante `status.json`; los fallos por repositorio quedan registrados en `failed_repos` sin detener el pipeline.
5. sw-metadata-bot recibe el inventario completo, reutiliza la snapshot anterior para repositorios sin cambios y publica issues solo si `launch_issue` está activado.
6. SOCA genera el portal enriquecido, que Nginx publica en `http://localhost:8030/portals/<project>/`.
7. `If repo updated` llama a DashVERSE solo si existen assessments nuevos; una ejecución con solo eliminaciones pasa directamente a la consolidación.
8. El estado pendiente se consolida como `repository-state.json` únicamente cuando finaliza el pipeline.

---





## 5. Requisitos

### Orquestador

- Docker Engine o Docker Desktop con Compose v2.
- Python 3.11 o 3.12 para desarrollo local.
- Git con soporte de submódulos.
- Token de GitHub recomendado para evitar el rate limit y publicar issues.

En Windows, Docker Desktop debe tener activada la integración con WSL si se despliega DashVERSE.

### DashVERSE

DashVERSE 0.3.0 se despliega desde Linux sobre Kubernetes local con Minikube. Todos los comandos de `kubectl`, `minikube`, `tofu`, `ansible-playbook` y `just` deben ejecutarse desde el mismo entorno para compartir el contexto de Kubernetes.

Requisitos principales:

- Docker Engine con Compose v2 o Podman para las imágenes de DashVERSE.
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
- zip y unzip.
- netcat (`nc`).

Instalación de utilidades habituales en Debian/Ubuntu:

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

Además, deben estar instalados Docker o Podman, Minikube, kubectl, Helm, OpenTofu y Just.

Comprobación desde la raíz de DashVERSE:

```bash
cd integrations/DashVERSE
just check-deps
```



         

#### Herramientas usadas en el proyecto:
- SOCA 0.0.4:
https://github.com/oeg-upm/soca/releases

- RSFC 0.1.8:
https://github.com/oeg-upm/rsfc/releases/tag/v0.1.8

- SOMEF 0.11.1:
https://github.com/KnowledgeCaptureAndDiscovery/somef/releases/tag/0.11.1

- DASHVERSE 0.3.0: 
https://github.com/EVERSE-ResearchSoftware/DashVERSE/releases/tag/v0.3.0

- sw-metadata-bot 0.5.3:
https://github.com/SoftwareUnderstanding/sw-metadata-bot/releases/tag/v0.5.3

- RsMetaCheck >=0.3.3:
https://github.com/SoftwareUnderstanding/RsMetaCheck/releases
      
      
---


## 6. Instalación/Despliegue

#### 6.1 Previa
 Se debe crear un archivo `.env` en el directorio `/containers` que tenga las variables entorno: 
   - `GITHUB_API_TOKEN`: token personal de GitHub; para publicar issues debe permitir acceso a repositorios públicos

   - `RABBITMQ_USER` usuario de RabbitMQ puesto en el servicio `rabbitmq` del `/containers/docker-compose.yml`
   - `RABBITMQ_PASSWORD` contraseña de RabbitMQ puesto en el servicio `rabbitmq` del `/containers/docker-compose.yml`

   - `RATE_LIMIT_RSFC_ENABLED` poner true/false dependiendo de si se quiere activar el limiter para los workers para peticiones a GitHubAPI
   - `RATE_LIMIT_RESQUI_ENABLED` poner true/false dependiendo de si se quiere activar el limiter para los workers RESQUI para peticiones a GitHubAPI
   - `RESQUI_CONF` nombre de la configuracion RESQUI a usar desde `containers/resqui_container/resqui_runner/configurations/`, sin extension `.json`. Por ejemplo, `RESQUI_CONF=complete_no_rsfc_superlinter` cargara `complete_no_rsfc_superlinter.json`.

   - `OUTPUTS` la ruta de acceso al directorio a usar como volumen compartido (se debe llamar ``outputs`` y estar dentro del directorio `/containers`)
   - `PORTAL_PORT` puerto del host desde el que Nginx publica los portales SOCA (por defecto `8030`)

   - `DASHBOARD_ORG_EMBED_ID` id o slug del dashboard global importado en DashVERSE/Superset (por defecto `global`)
   - `DASHBOARD_REPO_EMBED_ID` id o slug del dashboard SQO-repo importado en DashVERSE/Superset (por defecto `assessments`)
      ambos valores corresponden a dashboards por defecto de dashverse

   - `DASHVERSE_JWT` token generado por la API de DashVERSE para publicar assessments desde n8n

   - `SUPERSET_PUBLIC_DOMAIN` dominio público usado por el navegador para cargar los dashboards. En local se utiliza `http://localhost:8088`.

      El archivo `/containers/.env.example` contiene todos los nombres necesarios; hay que sustituir los tokens, rutas e identificadores de dashboard.


**A tener en cuenta**:  
-  El token (classic) se debe obtener desde GitHub y seleccionando el scope 'public_repo'. si no saltará error el uso de ese token. Se puede dejar vacía pero sólo se podrán realizar 50 peticiones por hora a GitHubAPI (no recomendable, muchos repos = error) y no se podrán subir las Issues automáticamente.

-  El nº o slug de dashboard es el que aparezca tras importar en DashVERSE la plantilla contenida en `/integrations/dashboard`. Los dashboards deben estar publicados y permitir embebido desde el portal.


#### 6.2 Instalación/Despliegue del orquestador
Siguiendo los pasos en orden secuencial:

Las imágenes pueden construirse con `scripts/build-docker-images.sh` en WSL/Linux o `scripts/build-docker-images.ps1` en PowerShell. Los mandatos equivalentes son:

0. Importar los submodulos del repositorio:
   - SQOO usa `containers/resqui_container/QualityPipelines-2.0` como submodulo para incluir el codigo fuente de RESQUI/QualityPipelines.
   - Si se clona el repositorio desde cero, usar:
      - Mandato: `git clone --recurse-submodules https://github.com/SergioZSZ/Software-Quality-Observatory-Orchestrator-TFG.git`
   - Si el repositorio ya estaba clonado o se acaba de hacer `git pull`, ejecutar desde la raiz de SQOO:
      - Mandato: `git submodule update --init --recursive`
   - Para comprobar que el submodulo esta descargado:
      - Mandato: `git submodule status`

1. Generar imágenes  docker:
   - `soca-heavy`:
      - Directorio desde el que crearla: `/containers/soca_container` 
      - Mandato: `docker build -t soca-heavy .`
   - `rsfc-heavy`:
      - Directorio desde el que crearla: `/containers/rsfc_container` 
      - Mandato: `docker build -t rsfc-heavy .`
   - `sw-metadata-bot`:
      - Directorio desde el que crearla: `/integrations/sw-metadata-bot-0.5.3`
      - Mandato: `docker build -t sw-metadata-bot .`
   - `sw-metadata-bot-conf`:
      - Directorio desde el que crearla: `/containers/sw-metadata-bot_container` 
      - Mandato: `docker build -t sw-metadata-bot-conf .`
   - `resqui-heavy`:
      - Directorio desde el que crearla: `/containers/resqui_container`
      - Mandato: `docker build -t resqui-heavy .`

   Estas son las imágenes del orquestador SQOO. Las imágenes propias de DashVERSE (`dashverse/backend` y `dashverse/frontend`) no se construyen con estos scripts: las construye `just deploy` desde `integrations/DashVERSE` usando `minikube image build`.

2. Desde el directorio `/containers` ejecutar el mandato en la terminal `docker compose up -d --scale worker_rsfc=N --scale worker_soca=N --scale worker_resqui=N`, siendo N el nº de workers a lanzar (si es la primera vez desplegándolo usar la etiqueta `--build` )

   El servicio RESQUI usa el volumen Docker nombrado `sqoo_resqui_work` montado como `/resqui-work`. Este volumen permite que el worker `resqui-heavy` y los contenedores Docker lanzados por los plugins de RESQUI compartan el mismo workspace de trabajo. No debe sustituirse por un bind mount local si se quiere ejecutar RESQUI dentro de Docker con plugins.

3. Acceder a n8n mediante el navegador en http://localhost:5678
4. En el primer acceso:
    1. Crear cuenta de usuario en n8n
    2. Importar los workflows desde `/containers/n8n_container/workflows/`
5. Importar y usar el workflow modular:
   - Importar `SQOO_modular_workflow.json` y los subworkflows `soca_workflow.json`, `rsfc_workflow.json`, `resqui_workflow.json`, `sw-metadata-bot_workfow.json` y `dashverse_workflow.json`.
   - Despues revisar los nodos `Call '<subworkflow>'` del workflow principal para que apunten a los subworkflows importados en la instancia de n8n.
6. Editar el nodo inicial de configuración con la organización/usuario deseado:
   - `project`: nombre estable para las salidas y el estado incremental.
   - `organizations`: lista de objetos con `org` y `type` (`org` o `user`).
   - `extra_repositories`: lista opcional de URLs adicionales.
   - `launch_issue`: `true` para publicar issues con `sw-metadata-bot publish`, `false` para ejecutar solo el análisis de metadatos.
7. Ejecutar manualmente

Tras ello se obtienen en `outputs` los metadatos SOCA, assessments RSFC y RESQUI, snapshots de sw-metadata-bot y el portal final. Nginx sirve el portal en `http://localhost:8030/portals/<project>/`.



## Instalación/Despliegue DashVERSE 0.3.0

### 1. Entrar en DashVERSE

Desde la raíz del repositorio SQOO:

```bash
cd integrations/DashVERSE
```

Comprobar los mandatos disponibles:

```bash
just --list
```

Comprobar dependencias:

```bash
just check-deps
```

### 2. Arrancar Minikube

```bash
minikube config set driver docker
minikube start --cpus=4 --memory=4096 --driver=docker
```

Comprobar el estado:

```bash
minikube status
kubectl get ns
```

### 3. Desplegar DashVERSE

```bash
just forward_address=0.0.0.0 deploy
```

Este mandato realiza el despliegue completo:

- comprueba las dependencias;
- comprueba o arranca Minikube;
- construye las imágenes de backend y frontend dentro del runtime de Minikube;
- aplica la infraestructura con OpenTofu;
- configura los port-forwards;
- sincroniza el catálogo de indicadores y dimensiones de EVERSE;
- importa dashboards, charts y datasets en Superset.

Si el despliegue falla en la importación de dashboards con `zip: not found`:

```bash
sudo apt update
sudo apt install -y zip unzip
just setup-dashboards
```

### 4. Comprobar servicios

```bash
just status
```

Consultar credenciales generadas:

```bash
just show-access
```

Consultar logs generales:

```bash
just logs
```

Logs concretos:

```bash
just logs-postgres
just logs-postgrest
just logs-superset
just logs-backend
just logs-frontend
```

### 5. URLs expuestas

Con los port-forwards activos se exponen los siguientes servicios:

- Frontend DashVERSE: `http://localhost:8080`
- Superset: `http://localhost:8088`
- API de assessments: `http://localhost:3000`
- API de autenticación/backend: `http://localhost:8000`
- Documentación de PostgREST: `http://localhost:3001`
- Documentación del backend: `http://localhost:8001`

Comprobaciones rápidas:

```bash
curl -I http://localhost:8088/health
curl http://localhost:3000/
```

### 6. Crear usuario

Acceder al backend:

```text
http://localhost:8000
```

Crear un usuario para SQOO, por ejemplo:

```text
username: sqoo
email: sqoo@example.org
password: <password>
```

### 7. Generar el token JWT

DashVERSE 0.3.0 incluye un mandato rápido para generar el JWT:

```bash
just jwt <usuario> '<password>'
```

Ejemplo:

```bash
just jwt sqoo '<password>'
```



### 8. Configurar SQOO

En `containers/.env` configurar:

```env
DASHVERSE_JWT=<token_generado_con_just_jwt>
SUPERSET_PUBLIC_DOMAIN=http://localhost:8088
```

### 9. Reimportar dashboards o resincronizar catálogo

Reimportar dashboards de Superset:

```bash
just setup-dashboards
```

Resincronizar indicadores y dimensiones EVERSE:

```bash
just trigger-sync
```

### 10. Parada y arranque posterior

Parar Minikube:

```bash
minikube stop
```

Volver a arrancar:

```bash
minikube start --driver=docker
```

Comprobar el servicio de port-forward:

```bash
just port-forward-status
```

Si los port-forwards no están activos:

```bash
just forward_address=0.0.0.0 port-forward
```




## 7. Estudios sobre el proyecto



**Evaluación de paralelismo de workers:** 
https://software-quality-observatory-orchestrator-tfg.readthedocs.io/es/latest/estudios/#estudio-sobre-el-paralelismo-de-workers

**Estudio sobre RAM y espacio del dispositivo:**
*In progress*

---


## 8. Soporte
Para cualquier problema escribir una issue en:
https://github.com/SergioZSZ/Software-Quality-Observatory-Orchestrator-TFG/issues


