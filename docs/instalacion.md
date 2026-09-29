# Instalación y despliegue

## Orquestador

### 1. Clonar el repositorio

```bash
git clone https://github.com/oeg-upm/Software-Quality-Observatory-Orchestrator.git
cd Software-Quality-Observatory-Orchestrator
```

RESQUI/QualityPipelines esta incluido como codigo fuente raw en `containers/resqui_container/QualityPipelines`. La copia local usada por la imagen `resqui-heavy` corresponde al commit upstream `98eb8efb83bd17e8e020bf11e8195b204c9453fd` de `main` en `EVERSE-ResearchSoftware/QualityPipelines`.

No hace falta ejecutar ningun paso adicional de descarga de dependencias para RESQUI.

### 2. Configurar el entorno

Copiar `containers/.env.example` como `containers/.env` y completar:

- `GITHUB_API_TOKEN`: token de GitHub para consultas y publicación de issues.
- `RABBITMQ_USER` y `RABBITMQ_PASSWORD`.
- `RATE_LIMIT_RSFC_ENABLED` y `RATE_LIMIT_RESQUI_ENABLED`.
- `RESQUI_CONF`: nombre de la configuracion RESQUI que se cargara desde `containers/resqui_container/resqui_runner/configurations/`, sin extension `.json`. Por ejemplo, `RESQUI_CONF=complete_no_rsfc_superlinter`.
- `OUTPUTS`: ruta absoluta de `containers/outputs`.
- `PORTAL_PORT`: puerto de Nginx, `8030` por defecto.
- `DASHBOARD_ORG_EMBED_ID` id o slug del dashboard global importado en DashVERSE/Superset (por defecto `global`)
- `DASHBOARD_REPO_EMBED_ID` id o slug del dashboard SQO-repo importado en DashVERSE/Superset (por defecto `assessments`)
      ambos valores corresponden a dashboards por defecto de dashverse
- `SUPERSET_PUBLIC_DOMAIN`: `http://localhost:8088` en local.
- `DASHVERSE_JWT`: token generado por la API de DashVERSE.

No se deben guardar tokens reales en Git.

### 3. Construir las imágenes

Se pueden usar `scripts/build-docker-images.sh` en WSL/Linux o `scripts/build-docker-images.ps1` en PowerShell. Los mandatos equivalentes desde la raíz son:

```bash
docker build -t soca-heavy:latest containers/soca_container
docker build -t rsfc-heavy:latest containers/rsfc_container
docker build -t resqui-heavy:latest containers/resqui_container
docker build -t rsmetacheck-bot:latest integrations/rsmetacheck-bot-0.6.0
docker build -t rsmetacheck-bot-conf:latest containers/rsmetacheck-bot_container
```

La imagen `rsmetacheck-bot-conf` debe construirse después de `rsmetacheck-bot`, ya que hereda de ella.

Estas son las imágenes del orquestador SQOO. Las imágenes propias de DashVERSE (`dashverse/backend` y `dashverse/frontend`) no se construyen con estos scripts: las construye `just deploy` desde `integrations/DashVERSE` usando `minikube image build`.

### 4. Levantar los servicios

```bash
cd containers
docker compose up -d --build \
  --scale worker_soca=4 \
  --scale worker_rsfc=4 \
  --scale worker_resqui=4
```

Los workers pueden escalarse según los recursos disponibles. Los logs se consultan con:

```bash
docker compose logs -f worker_soca worker_rsfc worker_resqui
```

### 5. Importar el workflow

Acceder a `http://localhost:5678` e importar:

- `SQOO_modular_workflow.json`
- `soca_workflow.json`
- `rsfc_workflow.json`
- `resqui_workflow.json`
- `rsmetacheck-bot_workfow.json`
- `dashverse_workflow.json`

Revisar los nodos `Call '<subworkflow>'` para que apunten a los workflows importados.

En el nodo `Conf` configurar:

```json
{
  "project": "mi-proyecto",
  "organizations": [
    {"org": "mi-organizacion", "type": "org"}
  ],
  "extra_repositories": [],
  "launch_issue": false
}
```

El portal quedará disponible en `http://localhost:8030/portals/<project>/`.

## DashVERSE 0.3.0

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

se debe hacer por curl:
```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user",
    "email": "user@example.com",
    "password": "yourpassword"
  }' | jq
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
