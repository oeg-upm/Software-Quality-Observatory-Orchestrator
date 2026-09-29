# Workflow modular

El sistema utiliza `SQOO_modular_workflow.json` como único workflow principal de n8n. Orquesta los siguientes subworkflows:

- `soca_workflow.json`
- `rsfc_workflow.json`
- `resqui_workflow.json`
- `rsmetacheck-bot_workfow.json`
- `dashverse_workflow.json`

## Configuración de entrada

El nodo `Conf` define:

- `project`: nombre estable usado en directorios y estado incremental.
- `organizations`: lista de objetos `{"org": "nombre", "type": "org|user"}`.
- `extra_repositories`: URLs adicionales a las descubiertas en GitHub.
- `launch_issue`: activa la publicación de issues de rsmetacheck-bot.

## 1. Descubrimiento incremental y SOCA

`soca_workflow.json` ejecuta `soca_runner.main`, consulta GitHub y compara cada `updated_at` con `outputs/soca/<project>/repository-state.json`.

Genera:

- `repos.txt`: inventario completo.
- `repos-updated.txt`: repositorios nuevos o modificados.
- `repos-removed.txt`: repositorios retirados.
- `repository-state.pending.json`: estado pendiente de consolidar.

Los workers procesan solo `repos-updated.txt`. Cada extracción se genera en staging y sustituye de forma atómica el resultado anterior; si falla, se conserva el último resultado válido y se registra el error. `status.json` diferencia repositorios correctos y fallidos.

El workflow principal evalúa `has_changes`. Si es `true`, continúa con RSFC; si es `false`, no repite las evaluaciones y consolida directamente el estado pendiente.

## 2. RSFC y RESQUI

Los subworkflows reciben `repos_url` y `repos_removed`:

- RSFC 0.2.0 evalúa los repositorios actualizados, reutiliza metadatos SOCA con `--metadata` cuando existen en `outputs/soca/<project>/metadata/` y, si no los encuentra, ejecuta RSFC con el análisis normal del repositorio. Escribe en `outputs/rsfc/<project>/<owner>_<repo>/`.
- RESQUI evalúa el mismo lote con QualityPipelines y escribe en `outputs/resqui/<project>/<owner>_<repo>/`.
- Ambos eliminan las salidas persistidas de los repositorios retirados y conservan un resultado anterior si una nueva evaluación falla.
- Los subworkflows esperan a que todos los repositorios se procesen. Cuando termina el lote, `status.json` queda en `completed` aunque haya repositorios fallidos; esos fallos se conservan en `failed_repos` y no detienen el pipeline.

## 3. rsmetacheck-bot

rsmetacheck-bot 0.6.0 recibe el inventario completo, no solo el lote actualizado. Esto permite que cada snapshot mantenga todos los repositorios.

El bot:

1. Genera `config.json`.
2. Ejecuta `rsmetacheck-bot run-analysis` con una snapshot fechada.
3. Localiza automáticamente el `run_report.json` anterior.
4. Reutiliza los artefactos cuyo commit no ha cambiado.
5. Ejecuta `rsmetacheck-bot publish` solo cuando `launch_issue` es `true`.

Las snapshots se guardan en `outputs/sw-metadata-bot/<project>/runs/<snapshot>/`. La ruta conserva el nombre histórico para que el portal SOCA pueda localizar los informes, aunque el ejecutable y la imagen sean `rsmetacheck-bot`.

## 4. Portal

Cuando terminan las evaluaciones, `soca_runner.genportal` combina metadatos SOCA, assessments RSFC e informes de rsmetacheck-bot. El portal se guarda en `outputs/soca/<project>/portal/` y Nginx lo sirve en:

```text
http://localhost:8030/portals/<project>/
```

## 5. DashVERSE

`dashverse_workflow.json` enriquece los assessments con `@id` y `author` antes de publicarlos:

- RSFC: `POST /assessment_raw` con `{ "payload": assessment }`.
- RESQUI: `POST /assessment` con el assessment validado.

Las peticiones utilizan `Authorization: Bearer <DASHVERSE_JWT>`.

Tras generar el portal, `If repo updated` comprueba `repo_count`. DashVERSE solo se ejecuta cuando existen repositorios actualizados; los lotes que contienen únicamente eliminaciones pasan directamente a la consolidación.

## 6. Consolidación del estado

Al terminar DashVERSE, o directamente cuando no hay assessments nuevos, n8n sustituye `repository-state.json` por `repository-state.pending.json`. Así, una ejecución fallida no marca como procesados cambios incompletos y una ejecución con solo eliminaciones actualiza correctamente el inventario.
