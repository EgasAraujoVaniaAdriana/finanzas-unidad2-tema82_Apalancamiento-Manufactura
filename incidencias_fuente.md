# Incidencias de la fuente — Tema 82

**Estudiante:** Vania Adriana Egas Araujo · 2024200498D
**Tema N.º 82:** Apalancamiento operativo y financiero en la industria manufacturera peruana

Este archivo registra las observaciones técnicas sobre las fuentes de datos y la decisión tomada en cada caso (consigna, numerales 2.4.3 y 2.4.8). Las horas son de Lima (UTC-05:00).

---

## Incidencia 1 · La SMV no publica reglas en `robots.txt`

| Campo | Detalle |
|---|---|
| Fuente | Superintendencia del Mercado de Valores (SMV), portal SIMV |
| URL consultada | https://www.smv.gob.pe/robots.txt |
| Fecha y hora (script) | 2026-11-24 22:41:00 -0500 |
| Redirección | **HTTP 301** (redirección permanente) hacia https://www.gob.pe/smv |
| Código HTTP final | 200 (en https://www.gob.pe/smv) |
| Tamaño de la respuesta | 288 021 bytes |
| Contenido recibido | Una página HTML (`<!DOCTYPE html>…`, título «Superintendencia del Mercado de Valores - SMV - Plataforma del Estado Peruano»): la página institucional de la SMV en gob.pe, no un archivo de reglas |
| Verificación | `urllib.robotparser.RobotFileParser` no encontró ninguna regla `User-agent`/`Disallow`. Las rutas del formulario de Información Financiera resultaron permitidas |
| Captura de pantalla | `evidencias/captura_robots_smv_2026-11-24.png`, tomada el 2026-11-24 a las 22:52: al abrir https://www.smv.gob.pe/robots.txt en el navegador, la barra de direcciones muestra `www.gob.pe/smv` |

| Cómo verificarlo | (1) En cada ejecución, `02_scraping_web.py` registra en `log_ejecucion.txt` la URL final, la redirección y el tipo de contenido del `robots.txt`. (2) En cualquier navegador, abrir https://www.smv.gob.pe/robots.txt: la barra de direcciones cambia a `www.gob.pe/smv` |

**Interpretación:** la dirección `robots.txt` del dominio smv.gob.pe no contiene un archivo de reglas: redirige a la página institucional de la SMV. La SMV no declara restricciones de rastreo. No es un bloqueo.

**Decisión:** se continúa con la descarga programática desde la SMV, con estas medidas:
1. El script `02_scraping_web.py` consulta el `robots.txt` con `RobotFileParser` antes de las solicitudes y registra el resultado en `log_ejecucion.txt`.
2. Si la SMV llegara a publicar reglas, toda ruta prohibida se marca como `BLOQUEADO_POR_ROBOTS` y no se solicita.
3. User-Agent identificable con correo de contacto.
4. Pausa de 2 segundos entre solicitudes.

No se requiere sustitución de fuente ni autorización del docente.

---

## Observación técnica · El formulario exige el parámetro `data=`

| Campo | Detalle |
|---|---|
| URL sin parámetro | https://www.smv.gob.pe/simv/Frm_InformacionFinanciera |
| Fecha y hora | 2026-11-24 22:41:05 -0500 |
| Resultado | HTTP 200, pero redirige a la página de error `/SIMV/Error/_500` |
| URL con parámetro | https://www.smv.gob.pe/simv/Frm_InformacionFinanciera?data=A70181B60967D74090DCD93C4920AA1D769614EC12 |
| Resultado | HTTP 200, formulario completo (ASP.NET WebForms, método POST), 123 185 bytes, desde una sesión nueva sin cookies |

| Cómo verificarlo | En un navegador, abrir las dos URL de esta tabla: sin `data=` aparece la página de error; con `data=`, el formulario. El script usa la segunda y registra su HTTP en el log |

**Decisión:** el parámetro `data=` se declara como constante en el script. No es un bloqueo: la página responde con el mismo valor en una sesión nueva.

---

## Observación técnica · El detalle de los estados solo abre en la misma sesión

| Campo | Detalle |
|---|---|
| Página | `Frm_DetalleInfoFinanciera.aspx?data=…` (detalle de cada estado financiero) |
| Fecha | 2026-11-24 (exploración previa al script) |
| Resultado sin sesión | El enlace copiado del navegador y abierto desde una sesión nueva redirige a `Default.aspx` (la página de inicio): el enlace solo vale dentro de la sesión que lo generó |
| Resultado en la misma sesión | Formulario → búsqueda (emisora, tipo, periodo, año y trimestre) → clic en la lupa de la fila «Estados Financieros» → la respuesta contiene el enlace al detalle → el detalle abre con HTTP 200 y trae las tablas del estado de situación financiera y del estado de resultados, con la unidad en el título (por ejemplo, «EN MILES DE NUEVOS SOLES») |
| Identificador | El detalle no muestra RUC ni CIIU: la llave de cada emisora es su **código SMV** de la lista del formulario |

| Cómo verificarlo | En un navegador: buscar una emisora y un trimestre, pulsar la lupa y copiar la dirección del detalle. Pegarla en una ventana de incógnito (otra sesión): abre la página de inicio, no el detalle. El recorrido en la misma sesión queda registrado en el log de la etapa de descarga |

**Decisión:** el script 02 reproduce ese mismo recorrido, dentro de una sola sesión y con las mismas pausas, como lo haría un usuario en el navegador. No es un bloqueo ni requiere autorización.

---

## Observación técnica · Respuesta intermitente del portal (Eternit, código 102)

| Momento (2026-11-25) | Búsqueda | Resultado | Dónde consta |
|---|---|---|---|
| 02:27:11 | Eternit, individual, intermedio, año y trimestre TODOS | HTTP 200, 12 páginas de resultados | `log_ejecucion.txt` |
| 02:52:01 | La misma búsqueda | HTTP 200, 123 609 bytes, aviso «No se encontraron registros» | `log_ejecucion.txt` (VERIFICACION [9/44], 0 trimestres) |
| hacia las 03:20 | La misma búsqueda, como comprobación | HTTP 200, 222 863 bytes, con filas de Eternit | Celda de diagnóstico (no registrada en el log) |

**Decisión:** el 0 de Eternit en la verificación de 02:41-03:18 se considera una respuesta intermitente del portal, no una falta de datos. Eternit se mantiene en la lista de emisoras. En la etapa de descarga, si una búsqueda devuelve «sin registros», el script la repite una vez y, si persiste, lo registra como advertencia.

---

## Observación técnica · Corridas de la verificación con error de lectura

| Corrida (2026-11-25) | Qué pasó | Corrección |
|---|---|---|
| 01:09-01:47 | Todos los conteos en cero: el script buscaba el documento por la posición de la columna, y con año y trimestre en TODOS la grilla agrega las columnas «Año» y «Período» | Las columnas se ubican por su encabezado y se cuentan trimestres distintos (año y periodo) |
| 02:16-02:27 | Se detuvo en Eternit (consolidado): una búsqueda sin resultados muestra un aviso en lugar de una tabla vacía | El aviso «No se encontraron registros» se lee como cero resultados |
| **02:41-03:18** | **Corrida completa y válida** | — |

**Decisión:** las corridas anteriores se conservan en el log (no se borran) y la válida es la última.
