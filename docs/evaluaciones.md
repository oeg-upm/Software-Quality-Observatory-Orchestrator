## 6. Evaluación del paralelismo en los workers
### 6.1 Hardware usado en las pruebas

| Componente        | Especificación                  |
| ----------------- | ------------------------------- |
| Equipo            | Lenovo 20WNS30L13               |
| CPU               | Intel Core i7-1185G7 (11th Gen) |
| Núcleos           | 4 cores / 8 threads             |
| Frecuencia        | ~3.0 GHz                        |
| RAM               | 16 GB                           |
| Sistema Operativo | Windows 11 Pro 64 bits          |
| DirectX           | DirectX 12                      |

### 6.2 Rendimientos
Se comparó el rendimiento del sistema utilizando la configuración de workers considerada óptima para el hardware disponible durante el desarrollo frente al tiempo total secuencial estimado.

Estas mediciones corresponden a ejecuciones completas anteriores al filtrado incremental actual; las ejecuciones posteriores pueden procesar solo los repositorios modificados.

No incluyen RESQUI, SALTBot ni la generación de descripciones con Ollama. Para comparar nuevas ejecuciones se deben indicar las versiones, el lote procesado y el modelo utilizado.

Este tiempo secuencial se calculó como el sumatorio de los tiempos individuales de procesamiento de cada repositorio, tanto en la fase de extracción de metadatos (SOCA) como en la fase de evaluación de calidad (RSFC). De este modo, se obtiene una aproximación del tiempo total que habría requerido la ejecución en un escenario completamente secuencial.

La comparación entre ambos enfoques permite evaluar el grado de paralelización alcanzado por el sistema, así como cuantificar la mejora en términos de reducción del tiempo total de ejecución.

##### Organización FAIR2ADAPT
**Datos**
- 27 repositorios

**Tabla**

| Métrica                          | Tiempo   |
|----------------------------------|----------|
| SOCA (10 workers)                | 1m 20s   |
| RSFC (4 workers)                 | 3m 30s   |
|                                  |          |
| SOCA secuencial (total)          | 11m 50s  |
| RSFC secuencial (total)          | 13m 20s  |


##### Organización oeg-upm
**Datos**
- 376 repositorios

**Tabla**

| Métrica                          | Tiempo     |
|----------------------------------|------------|
| SOCA (10 workers)                | 36m 57s    |
| RSFC (4 workers)                 | 50m 02s    |
|                                  |            |
| SOCA secuencial (total)          | 5h 47m 22s |
| RSFC secuencial (total)          | 3h 19m 20s |


### Conclusiones

| Organización | Tiempo paralelo | Tiempo secuencial | Speedup |
|-------------|-----------------|-------------------|---------|
| FAIR2ADAPT  | 4m 50s          | 25m 10s           | 5.21x   |
| OEG-UPM     | 1h 26m 59s      | 9h 06m 42s        | 6.28x   |

Los resultados obtenidos muestran un speedup significativo en ambos escenarios evaluados.

Se observa que:
- El sistema escala mejor en cargas grandes (oeg-upm), donde el paralelismo se aprovecha más eficientemente.
- El speedup no es lineal debido a:
  - Overhead de coordinación entre workers
  - Limitaciones de la GitHub API (rate limiting)
  - Latencias de red y operaciones de I/O

A pesar de ello, se consigue una reducción sustancial del tiempo total de ejecución, validando la arquitectura distribuida propuesta.
