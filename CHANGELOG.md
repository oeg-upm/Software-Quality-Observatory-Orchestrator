# General
- Actualizada la documentación en español e inglés para RSFC 0.2.2 y rsmetacheck-bot 0.6.2.
- Update del workflow `SQOO_modular_workflow` para incluir SALTBot
- Update de scripts de build docker images con ultima version de saltbot y rsmetacheck-bot
- Configurado RabbitMQ para que su generación de logs no ocupen mas de 60MB 
- Añadido `scripts/cleanup.sh` para limpiar imágenes y caché Docker antiguas y comprobar el uso de disco.
# RSMETACHECK-BOT
- Actualizado a su versión 0.6.2
- Renombrada la integración desde sw-metadata-bot a rsmetacheck-bot y documentadas las nuevas CLI `run-analysis`, `publish`, `simulate-publish` y `convert-legacy`.

# SOCA

# RSFC
- Actualizado a su versión 0.2.2
- Documentada la reutilización de metadatos SOCA mediante `rsfc --metadata`.

# RESQUI
- Migrada la integracion de QualityPipelines desde submodulo a codigo raw en `containers/resqui_container/QualityPipelines`, fijando la referencia al commit upstream `98eb8efb83bd17e8e020bf11e8195b204c9453fd`


# DashVERSE


# OLLAMA
- Añadidos `ollama` y `ollama-init` en ambos Compose, con healthcheck, descarga de `LLM_MODEL` y volumen persistente para los modelos.
- Integrado con SALTBot para resumir descripciones de software y abstracts de artículos, con fallback y validación de hasta 250 caracteres.

# SALTBOT
- Integrado SALTBot en SQOO mediante `saltbot_workflow`, con filtros y actualización opcional de Wikidata.
- Añadidos `status.json` y `structured_operations.json` para monitorización y operaciones por repositorio.
- Mejoradas la detección de artículos y autores, la deduplicación y los reintentos ante errores de API.
- Añadidas descripciones con Ollama desde SOMEF o abstracts de OpenAlex, con fallback y máximo de 250 caracteres.
