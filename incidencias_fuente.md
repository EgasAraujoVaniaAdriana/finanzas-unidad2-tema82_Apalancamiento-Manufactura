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

---

## Observación técnica · Unidad del título que no corresponde a sus cifras (Alicorp, 2025T4)

| Campo | Detalle |
|---|---|
| Archivo | `datos_crudos/smv/datos_crudos_2024200498D_smv_73_2025T4_I_exp2026007262.html` |
| Descarga | 2026-11-26 00:58:03 -0500 · SHA-256 `620ac295035fbfa845864c3aa03fe1f3bf5e27bbbcb5a3d9160fa494bfe7ae97` (`log_ejecucion.txt`) |
| Qué dice el título | «ESTADOS FINANCIEROS, INDIVIDUAL, TRIMESTRE IV AL 31 DE DICIEMBRE DEL 2025 ( EN MILES DE DOLARES )», en todas las secciones del estado |
| Qué se esperaba | «EN MILES DE NUEVOS SOLES», como en los otros 299 crudos del lote 1 |

**Evidencia.** El total de activos al 31-dic-2024 es el mismo en tres crudos:

| Crudo | Unidad del título | Total de activos al 31-dic-2024 |
|---|---|---|
| 2024T4 (`..._73_2024T4_I_exp2025007047.html`), columna actual | Miles de nuevos soles | 8 981 886 |
| 2025T3 (`..._73_2025T3_I_exp2025047511.html`), columna comparativa | Miles de nuevos soles | 8 981 886 |
| 2025T4 (`..._73_2025T4_I_exp2026007262.html`), columna comparativa | Miles de **dólares** | 8 981 886 |

**Interpretación.** Si la emisora hubiera cambiado su moneda de presentación, la NIC 21 exige expresar también las cifras comparativas en la nueva moneda, y el saldo de 2024 no coincidiría con el publicado en soles. Como coincide, las cifras de 2025T4 están en miles de soles y la unidad del título es una inconsistencia de rótulo. Es el único caso entre los 300 crudos del lote 1. La magnitud lo confirma: el total de activos pasa de 10 018 191 (30-set-2025) a 8 823 663 (31-dic-2025); leído en dólares, se habría triplicado en un trimestre.

| Cómo verificarlo | (1) Abrir el crudo de 2025T4 y leer el título y la columna comparativa del estado de situación financiera. (2) Abrir los crudos de 2024T4 y 2025T3 y comparar el total de activos al 31-dic-2024. (3) En el portal de la SMV, las notas de los estados de Alicorp del IV trimestre de 2025 indican la moneda de presentación |

**Decisión.** El crudo se conserva sin editar. El script 03 aplica una regla general: si el título de un estado indica una moneda distinta de soles y su columna comparativa coincide con el saldo del crudo del cierre anterior, se trata con la unidad de ese crudo y se registra en el log como `UNIDAD_CORREGIDA`, con la evidencia; si no coincide, el 03 se detiene (sería un cambio real de moneda).

---

## Observación técnica · Presentaciones incompletas del mismo expediente (Backus 2025T4 y San Juan 2025T2)

| Campo | Detalle |
|---|---|
| Qué se observó | En la grilla de la SMV, un mismo expediente aparece con dos presentaciones de «Estados Financieros» y distinta fecha. Ejemplo: Backus (47), 2025T4, expediente 2026007423, presentado el 16/02/2026 09:53:22 p.m. y el 20/03/2026 08:18:52 p.m. La primera trae el estado de resultados, pero no el estado de situación financiera («No se encontraron registro coincidentes…»); la segunda trae los dos |
| Efecto en la descarga del lote 1 | El nombre del crudo distinguía solo por expediente, así que las dos presentaciones daban el mismo nombre: el script guardó la primera (incompleta) y omitió la segunda. Por eso el log del lote 1 registra «ya existían: 1» en Cervecería San Juan (49) y Backus (47) |
| Archivos afectados (guardados en Colab, nunca subidos al repositorio) | `datos_crudos_2024200498D_smv_49_2025T2_I_exp2025034256.html` (2026-11-26 01:14:14, 181 764 bytes, SHA-256 `af159b62872ddfdece67882a569fbf10458bd658e466d51e2c62c6836427006b`) y `datos_crudos_2024200498D_smv_47_2025T4_I_exp2026007423.html` (2026-11-26 01:22:44, 183 400 bytes, SHA-256 `8b63598efa9ed3b6f244a4585681e588339467eeec8678078d9f5a13fa05975a`). Pesan unos 70 KB menos que los demás crudos, porque les falta el balance |
| Cómo se detectó | Revisión de partidas del lote 1 (sin conexión): esos dos archivos eran los únicos sin total de activos, propiedades, planta y equipo ni otros pasivos financieros. Se confirmó en el portal: la primera presentación no muestra el estado de situación financiera y la segunda sí |

**Decisión.**
1. Se borraron los dos archivos incompletos antes del primer commit de la etapa de descarga. Sus líneas `CRUDO` se conservan en el log como registro de lo ocurrido.
2. Se agregó al script 02 una regla declarada en su docstring: si un expediente tiene varias presentaciones, se revisan de la más reciente a la más antigua y se guarda solo la primera que trae el estado de situación financiera y el estado de resultados con contenido; las incompletas no se guardan y quedan registradas en el log (líneas `PRESENTACIONES`, con todas las fechas y la elegida). Si todas fueran incompletas, se guarda la más reciente y se marca como dato faltante en el 03.
3. Se volvió a ejecutar el lote 1: el script omitió los 298 crudos existentes y descargó esos dos trimestres aplicando la regla.

| Cómo verificarlo | (1) En `log_ejecucion.txt`, las líneas `CRUDO` del 2026-11-26 01:14:14 y 01:22:44 (archivos borrados) y las líneas `PRESENTACIONES` y `CRUDO` de la nueva ejecución del lote 1. (2) En el portal de la SMV, buscar Backus, individual, 2025, IV trimestre: aparecen dos filas de «Estados Financieros» con el expediente 2026007423; la del 16/02/2026 no muestra el estado de situación financiera |
