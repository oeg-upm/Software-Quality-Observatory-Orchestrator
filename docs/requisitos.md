# Requisitos

## Orquestador

- Docker Engine o Docker Desktop con Compose v2.
- Python 3.11 o 3.12 para desarrollo local.
- Git.
- Token de GitHub recomendado para evitar el rate limit y publicar issues.

En Windows, Docker Desktop debe tener activada la integración con WSL si se despliega DashVERSE.

## DashVERSE

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

- RSFC 0.2.0:
https://github.com/oeg-upm/rsfc/releases/tag/v0.2.0

- SOMEF 0.11.1:
https://github.com/KnowledgeCaptureAndDiscovery/somef/releases/tag/0.11.1

- DASHVERSE 0.3.0: 
https://github.com/EVERSE-ResearchSoftware/DashVERSE/releases/tag/v0.3.0

- rsmetacheck-bot 0.6.0:
https://github.com/SoftwareUnderstanding/rsmetacheck-bot/releases

- RsMetaCheck >=0.3.6:
https://github.com/SoftwareUnderstanding/rsmetacheck/releases
