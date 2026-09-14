[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18879858.svg)](https://doi.org/10.5281/zenodo.18879858) [![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active) [![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# TFG – Orquestación automatizada de evaluación de software y generación de catálogo

## Objetivo

SQOO descubre repositorios de GitHub, extrae sus metadatos, evalúa la calidad del software y publica los resultados en un portal y en DashVERSE. El proceso es reproducible, incremental y se orquesta con n8n.

## Arquitectura

| Componente | Función |
| --- | --- |
| n8n | Orquesta el workflow modular y sus subworkflows |
| SOCA | Descubre cambios, extrae metadatos y genera el portal |
| RSFC | Evalúa indicadores FAIR de software |
| RESQUI | Ejecuta evaluaciones configurables de QualityPipelines |
| RabbitMQ | Distribuye trabajos entre workers paralelos |
| sw-metadata-bot | Evalúa metadatos e inicia issues opcionales |
| Nginx | Publica los portales SOCA |
| DashVERSE | Almacena y visualiza assessments RSFC y RESQUI |

## Flujo actual

`SQOO_modular_workflow.json` es el workflow principal. Recibe un `project`, organizaciones o usuarios de GitHub, repositorios adicionales y la opción `launch_issue`.

SOCA compara el inventario actual con el estado anterior. Los repositorios nuevos o modificados se procesan mediante SOCA, RSFC y RESQUI, mientras que los eliminados se retiran de las salidas persistidas. sw-metadata-bot conserva una snapshot completa, el portal se regenera y DashVERSE solo recibe assessments nuevos.

Consulta [Instalación](instalacion.md) para desplegar el sistema.
