# SALTBot

SALTBot procesa los metadatos SOMEF de SOCA para enlazar software con artículos científicos. `describe` genera las operaciones y `update` las aplica a Wikidata. En SQOO se ejecuta mediante `saltbot_workflow.json`.

## Selección y búsqueda

El nodo `Filter repos` permite excluir URLs y `Prepare SALTBot metadata dir` copia el último SOMEF de cada repositorio a `metadata-selected`. La lista enviada al subworkflow determina si se procesa todo el inventario o solo los repositorios modificados.

SALTBot prioriza la cita científica `preferred-citation`, después las demás citas y BibTeX. Busca el artículo en Wikidata por DOI, URL y título; si no lo resuelve, consulta OpenAlex. Como última opción acepta una cita científica explícita con título y URL, incluidos artículos CEUR sin DOI.

El software se busca por URL del repositorio. La búsqueda por nombre requiere un candidato único enlazado al artículo. Las entidades existentes se reutilizan y se añaden los enlaces que falten; si ambos ya están enlazados, no se generan operaciones de enlace.

SALTBot omite los repositorios que SOMEF clasifica como `ontology`. Las demás exclusiones se indican en el workflow. Si no encuentra un artículo científico, no genera operaciones solo para el software.

## Operaciones y descripciones

Los artículos nuevos incluyen título y autores, priorizando los de la cita. Los autores del software se obtienen del bloque raíz `authors` del CFF. No se crean entidades de autores ni statements de URL de descarga; se selecciona una licencia por software.

Los artículos compartidos reutilizan una sola creación por DOI, OpenAlex ID o URL dentro de la misma ejecución.

Ollama resume la primera descripción SOMEF no vacía si supera 250 caracteres. Para un artículo nuevo utiliza su abstract de OpenAlex, cuando existe. El prompt pide menos de 200 caracteres y hasta 20 palabras, pero el código solo exige entre 1 y 250 caracteres. Si falta el texto o falla la generación, se usa una descripción alternativa. No se extraen abstracts de PDFs CEUR.

Las entidades existentes conservan sus descripciones. Repetir `describe` antes de publicar una entidad nueva puede volver a llamar al LLM.

## Salidas y actualización

Las salidas se guardan en `containers/outputs/saltbot/<project>/`:

| Fichero | Contenido |
| --- | --- |
| `status.json` | Estado, repositorios procesados y errores por repositorio |
| `structured_operations.json` | Operaciones agrupadas por repositorio y fichero SOMEF |
| `operation_list.txt` | Operaciones del lote para `update` |
| `results.txt` | Resultado de la búsqueda y enlaces de cada repositorio |

Un repositorio fallido no detiene el resto del lote. n8n comprueba que exista `status.json` tras 30 segundos y consulta el estado hasta finalizar. Revisar los errores del estado además de las operaciones.

Mantener `update_wikidata: false` mientras se revisa el resultado. Con `true`, se ejecuta `update` si `operation_list.txt` tiene contenido. El updater conserva los ficheros de entrada y registra los errores y las esperas de Wikidata, incluido `maxlag`.

Las peticiones de creación y guardado se separan al menos 15 segundos por proceso, también tras un fallo, para mantener unas cuatro escrituras por minuto. Los statements se agrupan por entidad; la pausa se aplica a cada escritura, no a cada tripleta.

Los errores de la API de MediaWiki muestran también `code`, `info` y `messages`, junto con la acción y la entidad, para identificar advertencias de filtros y otros motivos de rechazo.

Para las pruebas se pueden preparar ficheros con los statements que falten y sus QID existentes. Las operaciones `create` generan entidades nuevas; no deben usarse para modificar entidades ya creadas.

## Configuración

Definir `WIKIBASE_USER`, `WIKIBASE_PASSWORD`, `OPENALEX_API_KEY` y `LLM_MODEL` en `containers/.env`. La clave de OpenAlex es opcional. El workflow debe pasar estas variables al contenedor; `OLLAMA_HOST` usa `http://ollama:11434` por defecto.

`ollama-init` descarga el modelo en el volumen persistente `ollama_data`. Comprobarlo con `docker exec ollama ollama list`. Las consultas a Wikidata y OpenAlex tienen reintentos para errores transitorios; si se agotan, el error queda en el repositorio correspondiente.
