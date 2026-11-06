# General
- Actualizada la documentación en español e inglés para RSFC 0.2.0 y rsmetacheck-bot 0.6.1.
- Update del workflow `SQOO_modular_workflow` para incluir SALTBot
- Update de scripts de build docker images con ultima version de saltbot y rsmetacheck-bot
- Configurado RabbitMQ para que su generación de logs no ocupen mas de 60MB 
# RSMETACHECK-BOT
- Actualizado a su versión 0.6.1
- Renombrada la integración desde sw-metadata-bot a rsmetacheck-bot y documentadas las nuevas CLI `run-analysis`, `publish`, `simulate-publish` y `convert-legacy`.

# SOCA

# RSFC
- Actualizado a su versión 0.2.0
- Documentada la reutilización de metadatos SOCA mediante `rsfc --metadata`.

# RESQUI
- Migrada la integracion de QualityPipelines desde submodulo a codigo raw en `containers/resqui_container/QualityPipelines`, fijando la referencia al commit upstream `98eb8efb83bd17e8e020bf11e8195b204c9453fd`


# DashVERSE


# SALTBOT
- Intregrado SALTBot en SQOO
- Creado saltbot_workflow para integración en el workflow de SALTBot