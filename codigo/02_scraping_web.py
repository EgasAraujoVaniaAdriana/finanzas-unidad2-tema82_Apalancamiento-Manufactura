# Nombres y apellidos: Vania Adriana Egas Araujo
# Código de matrícula: 2024200498D
# Tema N.º 82 del temario: Apalancamiento operativo y financiero en la industria manufacturera peruana
# Fecha de extracción: 2026-11-26
"""
Script 02 — Descarga programática (SMV, Superintendencia del Mercado de Valores).

Qué hace, por etapas (se elige con --etapa al ejecutar):
  lista         Revisa el robots.txt y lee del formulario «Información Financiera»
                la lista de emisoras vigentes y retiradas, con su código SMV.
                Las registra en log_ejecucion.txt. No guarda archivos.
  verificacion  Para cada emisora de EMISORAS, busca sus estados financieros
                intermedios (trimestrales) Individuales y Consolidados y cuenta
                cuántos trimestres distintos (año y periodo del estado) tiene
                entre 2011 y 2025. Sirve para decidir el tipo de estado.
                Lo registra en el log. No guarda archivos.
  descarga      Selecciona y descarga, en una sola pasada por emisora:
                1) busca sus estados intermedios INDIVIDUALES (año y trimestre
                   en TODOS) y cuenta sus trimestres distintos de 2011T1 a
                   2025T4;
                2) la emisora queda INCLUIDA solo si tiene MIN_TRIMESTRES (60,
                   panel completo); si no, EXCLUIDA. La decisión, con su
                   conteo, se registra en el log;
                3) de las incluidas, abre el detalle de cada trimestre (lupa
                   de la fila «Estados Financieros») y lo guarda TAL COMO
                   LLEGA, en HTML, en datos_crudos/smv/, con su SHA-256 y la
                   unidad monetaria del título.
                Si un archivo ya existe, no se vuelve a pedir (permite reanudar).

Almacenamiento y subida por lotes (etapa «descarga»):
    Los detalles se guardan sin editar en datos_crudos/smv/, un archivo HTML
    por emisora, trimestre y N.º de expediente. La etapa se ejecuta por lotes
    de LOTE_TAMANO emisoras (--lote k) y, al terminar cada lote con
    descargas, sus crudos y el log se suben al repositorio en un commit
    propio («lote k»); los lotes que solo cuentan emisoras sin descargar
    ninguna (las retiradas) se suben juntos en un solo commit. Por eso el
    historial tiene varios commits de esta etapa. Se hace así por tres razones:
      1) carga moderada al portal: a las pausas entre solicitudes y entre
         emisoras se suma la pausa entre lotes;
      2) control de calidad: cada lote se revisa (partidas y unidades) antes
         de subirlo y de seguir con el siguiente;
      3) conservación: lo descargado queda respaldado en el repositorio lote
         por lote; si la sesión o el portal se cortan, solo se repite el lote
         en curso y lo ya guardado no se vuelve a pedir.
    Si un mismo trimestre aparece con varias presentaciones (del mismo
    expediente o de expedientes distintos), por ejemplo, una primera sin el
    estado de situación financiera y otra posterior completa, se guarda un
    solo crudo: la más reciente que traiga el balance y el estado de
    resultados con contenido; las incompletas no se guardan y quedan
    registradas en el log («PRESENTACIONES»).
    El log registra cada lote («DESCARGA | lote k de 9»), cada decisión de
    selección («SELECCION») y cada archivo guardado («CRUDO») con su SHA-256
    y la unidad del título. Las observaciones sobre el contenido de los
    crudos (por ejemplo, un título con una unidad que no corresponde a sus
    cifras) se documentan en incidencias_fuente.md; el crudo no se edita.

En todas las etapas:
  - Se revisa el robots.txt antes de cualquier otra solicitud.
  - Se declara un User-Agent identificable y se deja una pausa de 2 s entre
    solicitudes (y una pausa mayor entre emisoras).
  - Si el portal responde 403, 429, otro código distinto de 200 o una página
    inesperada, el script se DETIENE: no reintenta ni intenta evadir el bloqueo.

Ejecución (desde la raíz del proyecto):
    python codigo/02_scraping_web.py --etapa lista
    python codigo/02_scraping_web.py --etapa verificacion
    python codigo/02_scraping_web.py --etapa verificacion --demo   (solo 1 emisora)
    python codigo/02_scraping_web.py --etapa descarga --lote 1     (emisoras 1 a 5)
    python codigo/02_scraping_web.py --etapa descarga --demo       (2 detalles, carpeta temporal)

    Orden: primero «lista»; con esa lista se completa EMISORAS; luego
    «verificacion» y, por último, «descarga», lote por lote (LOTE_TAMANO
    emisoras por lote). El modo --demo es la versión corta para la
    demostración en vivo: cuenta y selecciona la primera emisora y guarda 2
    detalles en una carpeta temporal, fuera de datos_crudos/.

Fuente (citar en APA 7.ª edición, numeral 2.4.8 de la consigna):
    Superintendencia del Mercado de Valores [SMV]. (2026). Información
    financiera de emisores [Base de datos del Portal del Mercado de Valores,
    SIMV]. Consultado en la fecha de extracción del encabezado, de
    https://www.smv.gob.pe/simv/Frm_InformacionFinanciera
    El portal no requiere clave ni registro.

Librerías externas: requests y beautifulsoup4 (versiones en requirements.txt).

Uso de inteligencia artificial: este script se escribió con la asistencia de
Claude (Anthropic), un asistente de IA, en noviembre de 2026. La estudiante
definió el diseño y las decisiones, revisó el código, lo ejecutó y verificó
sus resultados. La declaración completa está en el README y en el artículo.

"""

# ---------------------------------------------------------------------------
# LIBRERÍAS
# ---------------------------------------------------------------------------
# argparse: lee la etapa pedida (--etapa) · hashlib: SHA-256 de cada respuesta
# urllib.robotparser: lee el robots.txt · requests: solicitudes HTTP
# BeautifulSoup: lee el HTML del formulario y de la grilla de resultados
# html: decodifica el enlace del detalle · tempfile: carpeta temporal del --demo
import argparse
import hashlib
import html
import platform
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import bs4
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# RUTAS (siempre relativas a la raíz del proyecto; nunca rutas de Colab/Drive)
# ---------------------------------------------------------------------------
CODIGO_MATRICULA = "2024200498D"
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_CRUDOS = RAIZ / "datos_crudos" / "smv"
RUTA_LOG = RAIZ / "log_ejecucion.txt"

# ---------------------------------------------------------------------------
# PARÁMETROS DEL ESTUDIO (constantes fijas; nunca «hoy»)
# ---------------------------------------------------------------------------
# Mismo panel que el script 01: 2012T1 a 2025T4, con descarga desde 2011T1
# por los rezagos t-1 y t-4.
FECHA_INICIO = "2012T1"
FECHA_CORTE = "2025T4"
# Años del periodo de los estados que se cuentan (columna «Año» de la SMV).
ANIO_PERIODO_MIN, ANIO_PERIODO_MAX = 2011, 2025

# Emisoras evaluadas (manufactura no primaria, vigentes y retiradas): códigos
# SMV, la llave que une cada trimestre en el 03. Se eligieron después de la
# etapa «lista». La etapa «descarga» decide cuáles entran al panel con la
# regla MIN_TRIMESTRES. Ejemplo: Alicorp = "73".
EMISORAS = ["73", "74470", "49", "47", "43173", "75981", "198", "101", "102", "108", "119", "330", "123", "112860", "117", "84522", "30011", "45", "33862", "57255", "250", "162", "191", "165", "4", "46", "51219", "148", "150808", "154463", "117471", "162521", "83510", "122783", "120088", "152418", "98", "95", "114979", "107", "87", "306", "201", "80"]

# Tipos de estado que compara la etapa «verificacion».
# I = Individual, C = Consolidado. El tipo del panel se decide con ese conteo.
TIPOS_VERIFICACION = ("I", "C")

# Tipo que descarga la etapa «descarga»: solo Individual (decidido el
# 25-nov con la verificación; la limitación se declara en el artículo).
TIPO_DESCARGA = "I"
# Regla de selección del panel (fijada antes de la descarga): una emisora
# entra solo si tiene sus estados individuales en los 60 trimestres de
# 2011T1 a 2025T4. Así el panel queda balanceado: todas las emisoras se
# observan en los mismos 56 trimestres de 2012T1-2025T4, más los 4 de 2011
# que se usan para los rezagos (t-1 y t-4). Un trimestre presentado más de
# una vez (reexpresión) cuenta una sola vez.
MIN_TRIMESTRES = (ANIO_PERIODO_MAX - ANIO_PERIODO_MIN + 1) * 4        # = 60
# Emisoras por lote (ver «Almacenamiento y subida por lotes» en el docstring):
# carga moderada al portal, revisión de cada lote y respaldo en el repositorio.
LOTE_TAMANO = 5
# Detalles que descarga el modo --demo.
DEMO_DETALLES = 2
# Trimestre del estado según el mes de cierre que muestra el título del detalle.
MES_A_TRIMESTRE = {"MARZO": 1, "JUNIO": 2, "SETIEMBRE": 3, "SEPTIEMBRE": 3, "DICIEMBRE": 4}
# La columna «Período» de la grilla viene en números romanos (I a IV).
PERIODO_A_TRIMESTRE = {"I": 1, "II": 2, "III": 3, "IV": 4}

# ---------------------------------------------------------------------------
# PARÁMETROS DEL PORTAL DE LA SMV (formulario ASP.NET)
# ---------------------------------------------------------------------------
URL_ROBOTS = "https://www.smv.gob.pe/robots.txt"
# El parámetro data= es el que usa el propio menú de la SMV: sin él, el portal
# responde con su página de error (ver incidencias_fuente.md).
URL_FORM = ("https://www.smv.gob.pe/simv/Frm_InformacionFinanciera"
            "?data=A70181B60967D74090DCD93C4920AA1D769614EC12")
CAMPO_EMPRESA = "ctl00$MainContent$cboDenominacionSocial"
CAMPO_RETIRADAS = "ctl00$MainContent$cbxRetiradas"
CAMPO_TIPO = "ctl00$MainContent$cboTipo"            # I = Individual, C = Consolidada
CAMPO_PERIODO = "ctl00$MainContent$cboPeriodo"      # T = Intermedio (trimestral), A = Anual
CAMPO_ANIO = "ctl00$MainContent$cboAnio"            # -1 = TODOS
CAMPO_TRIMESTRE = "ctl00$MainContent$cboTrimestre"  # -1 = TODOS
BOTON_BUSCAR = "ctl00$MainContent$cbBuscar"
ID_GRILLA = "MainContent_grdInfoFinanciera"
NOMBRE_GRILLA = "ctl00$MainContent$grdInfoFinanciera"
MAX_PAGINAS = 20     # tope de páginas de resultados por búsqueda

# Identificación del proyecto ante el servidor y pausas.
# REEMPLAZAR por tu correo antes de ejecutar (el script se detiene si no).
CORREO_CONTACTO = "e_2024200498D@uncp.edu.pe"
USER_AGENT = (
    "ProyectoAcademico-FinanzasI-UNCP-Tema82/1.0 "
    f"(uso academico; contacto: {CORREO_CONTACTO})"
)
PAUSA_SEG = 2                 # pausa mínima entre solicitudes (consigna: ≥ 1 s)
PAUSA_ENTRE_EMISORAS = 10     # pausa adicional al pasar de una emisora a otra
TIMEOUT_SEG = 60

ZONA_HORARIA = ZoneInfo("America/Lima")

# ---------------------------------------------------------------------------
# FUNCIONES · 1. REGISTRO EN EL LOG Y ENCABEZADO
# ---------------------------------------------------------------------------
class Detener(Exception):
    """Respuesta inesperada o posible bloqueo: el script se detiene sin reintentar."""


def ahora():
    """Fecha y hora actual de Lima, con zona horaria (para el log)."""
    return datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d %H:%M:%S %z")


def registrar(mensaje):
    """Muestra el mensaje en consola y lo agrega al log_ejecucion.txt."""
    linea = f"{ahora()} | 02_scraping_web | {mensaje}"
    print(linea)
    with open(RUTA_LOG, "a", encoding="utf-8", newline="\n") as log:
        log.write(linea + "\n")


def sha256_bytes(contenido):
    """SHA-256 de una respuesta (evidencia de lo que devolvió el portal)."""
    return hashlib.sha256(contenido).hexdigest()


def verificar_encabezado():
    """
    Revisa el encabezado obligatorio (numeral 2.4.2): las 4 primeras líneas
    deben ser comentarios con (1) nombres y apellidos, (2) código de
    matrícula, (3) tema y número del temario y (4) fecha de extracción exacta
    (AAAA-MM-DD). Si falta algo, se detiene antes de cualquier solicitud.
    Un encabezado incompleto o una fecha aproximada es una mala práctica.
    """
    lineas = Path(__file__).read_text(encoding="utf-8").splitlines()[:4]
    reglas = [r"^# Nombres y apellidos: \S.+$",
              r"^# Código de matrícula: \S+$",
              r"^# Tema N\.º \d+ del temario: \S.+$",
              r"^# Fecha de extracción: (\d{4}-\d{2}-\d{2})\s*$"]
    for numero, regla in enumerate(reglas, start=1):
        linea = lineas[numero - 1] if len(lineas) >= numero else ""
        if not re.match(regla, linea):
            sys.exit(f"ERROR en la línea {numero} del encabezado: «{linea}». "
                     "Debe ser un comentario que empiece con «#» y siga el formato obligatorio.")
    fecha = re.match(reglas[3], lineas[3]).group(1)
    hoy = datetime.now(ZONA_HORARIA).date().isoformat()
    registrar(f"Encabezado de 4 líneas verificado (fecha de extracción {fecha})")
    if fecha != hoy:
        registrar(f"ADVERTENCIA: el encabezado dice {fecha} y hoy es {hoy}")


# ---------------------------------------------------------------------------
# FUNCIONES · 2. SOLICITUDES AL PORTAL Y ROBOTS.TXT
# ---------------------------------------------------------------------------
def solicitar(sesion, url, datos=None, detalle=""):
    """
    Hace una solicitud (GET, o POST si hay datos) después de la pausa, la
    registra en el log (URL, filtros enviados, HTTP, bytes y SHA-256) y se
    detiene si la respuesta no es la esperada. Nunca reintenta un 403 o 429.
    """
    # Pausa ANTES de cada solicitud: así nunca hay dos seguidas sin espera.
    time.sleep(PAUSA_SEG)
    metodo = "POST" if datos is not None else "GET"
    try:
        if datos is None:
            resp = sesion.get(url, timeout=TIMEOUT_SEG)
        else:
            resp = sesion.post(url, data=datos, timeout=TIMEOUT_SEG)
    except requests.RequestException as error:
        raise Detener(f"{metodo} {url} sin respuesta: {error}")
    # Todo queda en el log, también las respuestas con error.
    registrar(f"{metodo} {url}{' | ' + detalle if detalle else ''} | HTTP {resp.status_code} | "
              f"{len(resp.content)} bytes | SHA-256 {sha256_bytes(resp.content)}")
    # 403 = acceso denegado y 429 = demasiadas solicitudes: posible bloqueo.
    # No se reintenta ni se cambia nada para evadirlo.
    if resp.status_code in (403, 429):
        raise Detener(f"HTTP {resp.status_code}: posible bloqueo del portal")
    if resp.status_code != 200:
        raise Detener(f"HTTP {resp.status_code} inesperado")
    return resp


def revisar_robots(sesion):
    """
    Descarga el robots.txt y lo consulta con RobotFileParser ANTES de tocar el
    formulario. Si la dirección redirige a una página que no es un robots.txt
    (caso documentado en incidencias_fuente.md), no hay reglas que leer: se
    registra y se continúa con User-Agent identificable y pausa de 2 s.
    Si el robots.txt prohíbe el formulario, se registra BLOQUEADO_POR_ROBOTS
    y el script se detiene.
    """
    resp = solicitar(sesion, URL_ROBOTS)
    redirecciones = " → ".join(r.url for r in resp.history) or "ninguna"
    tipo = resp.headers.get("Content-Type", "")
    registrar(f"robots.txt | URL final {resp.url} | redirecciones: {redirecciones} | Content-Type {tipo}")
    es_robots = urlparse(resp.url).path.endswith("robots.txt") and "text/plain" in tipo.lower()
    if not es_robots:
        registrar("robots.txt | la dirección no devuelve un robots.txt, sino otra página: "
                  "no hay reglas que restrinjan el acceso (ver incidencias_fuente.md)")
        return
    lector = RobotFileParser()
    lector.parse(resp.text.splitlines())
    if not lector.can_fetch(USER_AGENT, URL_FORM):
        registrar(f"BLOQUEADO_POR_ROBOTS | {URL_FORM}")
        raise Detener("el robots.txt no permite el formulario de Información Financiera")
    registrar("robots.txt | el formulario está permitido para este User-Agent")


# ---------------------------------------------------------------------------
# FUNCIONES · 3. FORMULARIO DE LA SMV (ASP.NET)
# El formulario guarda su estado en campos ocultos (__VIEWSTATE,
# __EVENTVALIDATION…). Cada envío debe devolverlos tal como llegaron, igual
# que lo hace el navegador al pulsar un botón.
# ---------------------------------------------------------------------------
def armar_datos(sopa):
    """Copia los campos del formulario tal como los enviaría el navegador."""
    formulario, datos = sopa.find("form"), {}
    for campo in formulario.find_all("input"):
        tipo, nombre = (campo.get("type") or "text").lower(), campo.get("name")
        if not nombre or tipo in ("submit", "image", "button"):
            continue
        if tipo in ("radio", "checkbox") and not campo.has_attr("checked"):
            continue
        datos[nombre] = campo.get("value", "on" if tipo == "checkbox" else "")
    for lista in formulario.find_all("select"):
        elegida = lista.find("option", selected=True) or lista.find("option")
        if lista.get("name") and elegida is not None:
            datos[lista["name"]] = elegida.get("value", "")
    return datos


def leer_empresas(sopa):
    """Devuelve {código SMV: denominación}. Si no hay lista, no es la página esperada."""
    lista = sopa.find("select", {"name": CAMPO_EMPRESA})
    if lista is None:
        raise Detener("la respuesta no contiene el formulario de Información Financiera")
    return {o["value"].strip(): o.get_text(strip=True)
            for o in lista.find_all("option")
            if o.get("value", "").strip().isdigit() and int(o["value"]) > 0}


def obtener_listas(sesion):
    """
    Abre el formulario (emisoras vigentes) y luego marca la casilla «Retiradas».
    Devuelve las dos páginas, la dirección del formulario y los diccionarios
    de vigentes y retiradas. Las retiradas evitan el sesgo de supervivencia.
    """
    # 1) Formulario tal como abre: lista de emisoras vigentes.
    resp = solicitar(sesion, URL_FORM, detalle="formulario (vigentes)")
    pagina_vigentes = BeautifulSoup(resp.text, "html.parser")
    url_accion = urljoin(resp.url, pagina_vigentes.find("form").get("action"))
    vigentes = leer_empresas(pagina_vigentes)

    # 2) Se marca la casilla «Retiradas», como al hacer clic en el navegador.
    datos = armar_datos(pagina_vigentes)
    datos.update({"__EVENTTARGET": CAMPO_RETIRADAS, "__EVENTARGUMENT": "", CAMPO_RETIRADAS: "on"})
    resp = solicitar(sesion, url_accion, datos, detalle="casilla Retiradas = marcada")
    pagina_retiradas = BeautifulSoup(resp.text, "html.parser")
    con_casilla = leer_empresas(pagina_retiradas)
    # 3) Retiradas = las que aparecen con la casilla y no estaban entre las vigentes.
    retiradas = {c: n for c, n in con_casilla.items() if c not in vigentes}
    if not retiradas:
        registrar("ADVERTENCIA: al marcar «Retiradas» la lista no agregó emisoras nuevas")
    registrar(f"Emisoras: {len(vigentes)} vigentes | {len(retiradas)} retiradas")
    return pagina_vigentes, pagina_retiradas, url_accion, vigentes, retiradas


# ---------------------------------------------------------------------------
# FUNCIONES · 4. BÚSQUEDA Y CONTEO DE ESTADOS (etapa «verificacion»)
# ---------------------------------------------------------------------------
def filas_grilla(sopa):
    """
    Lee la grilla de resultados y devuelve (filas, tabla, total_filas).
    Las columnas se ubican por su ENCABEZADO, no por su posición, porque la
    grilla cambia según la búsqueda: con año y trimestre en TODOS agrega las
    columnas «Año» y «Período». Cada fila devuelta es un diccionario con el
    año, el periodo y la fecha de presentación, y solo se conservan las de
    «Estados Financieros» (no las «Notas a los Estados Financieros»).
    """
    tabla = sopa.find("table", id=ID_GRILLA)
    if tabla is None:
        return [], None, 0
    filas_html = tabla.find_all("tr")
    if not filas_html:
        return [], tabla, 0
    encabezado = [c.get_text(" ", strip=True) for c in filas_html[0].find_all(["th", "td"])]
    if "Documento" not in encabezado:
        # Búsqueda sin resultados: la SMV muestra un aviso en lugar de filas.
        if "No se encontraron registros" in tabla.get_text(" ", strip=True):
            return [], tabla, 0
        raise Detener(f"la grilla no tiene la columna «Documento»: {encabezado}")
    col = {nombre: i for i, nombre in enumerate(encabezado)}
    filas, total = [], 0
    for tr in filas_html[1:]:
        celdas = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(celdas) < len(encabezado) - 1:
            continue                                  # fila del paginador
        total += 1
        if celdas[col["Documento"]] != "Estados Financieros":
            continue
        filas.append({"anio": celdas[col["Año"]] if "Año" in col else "",
                      "periodo": celdas[col["Período"]] if "Período" in col else "",
                      "fecha": celdas[col["Fecha de Presentación"]]
                               if "Fecha de Presentación" in col else ""})
    return filas, tabla, total


def contar_estados(sesion, pagina_base, url_accion, codigo, tipo, es_retirada):
    """
    Busca los estados intermedios (trimestrales) de una emisora y un tipo, con
    año y trimestre en TODOS, recorre todas las páginas de resultados y cuenta
    cuántos trimestres distintos hay entre ANIO_PERIODO_MIN y ANIO_PERIODO_MAX.
    Devuelve (trimestres, primer año, último año).
    """
    # 1) Filtros de la búsqueda: emisora, tipo, periodo intermedio y TODOS.
    datos = armar_datos(pagina_base)
    datos.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "", CAMPO_EMPRESA: codigo,
                  CAMPO_TIPO: tipo, CAMPO_PERIODO: "T", CAMPO_ANIO: "-1",
                  CAMPO_TRIMESTRE: "-1", BOTON_BUSCAR: "Buscar"})
    if es_retirada:
        datos[CAMPO_RETIRADAS] = "on"
    else:
        datos.pop(CAMPO_RETIRADAS, None)
    resp = solicitar(sesion, url_accion, datos,
                     detalle=f"empresa {codigo} | tipo {tipo} | periodo T | año TODOS | trimestre TODOS | página 1")

    # 2) Se leen las filas de cada página de resultados; si hay un enlace a la
    #    página siguiente («Page$n»), se pide esa página.
    todas, filas_totales, pagina = [], 0, 1
    while True:
        sopa = BeautifulSoup(resp.text, "html.parser")
        leer_empresas(sopa)                          # comprueba que es la página esperada
        filas, tabla, total = filas_grilla(sopa)
        todas.extend(filas)
        filas_totales += total
        enlaces = set() if tabla is None else {
            int(n) for n in re.findall(r"Page\$(\d+)", str(tabla))}
        if pagina + 1 not in enlaces or pagina >= MAX_PAGINAS:
            if pagina >= MAX_PAGINAS and pagina + 1 in enlaces:
                registrar(f"ADVERTENCIA: empresa {codigo} tipo {tipo} tiene más de {MAX_PAGINAS} páginas")
            break
        pagina += 1
        datos = armar_datos(sopa)
        datos.update({"__EVENTTARGET": NOMBRE_GRILLA, "__EVENTARGUMENT": f"Page${pagina}"})
        resp = solicitar(sesion, url_accion, datos,
                         detalle=f"empresa {codigo} | tipo {tipo} | página {pagina}")

    # 3) Se cuentan los trimestres DISTINTOS (año y periodo del estado) del
    #    rango: si un trimestre se presentó dos veces, cuenta una sola vez.
    #    Si la grilla tiene filas pero ninguna de «Estados Financieros», se avisa.
    if filas_totales and not todas:
        registrar(f"ADVERTENCIA: empresa {codigo} tipo {tipo}: la grilla tiene {filas_totales} "
                  "filas, pero ninguna de «Estados Financieros»")
    trimestres = {(int(f["anio"]), f["periodo"]) for f in todas
                  if f["anio"].isdigit() and ANIO_PERIODO_MIN <= int(f["anio"]) <= ANIO_PERIODO_MAX}
    anios = [a for a, _ in trimestres]
    return len(trimestres), (min(anios) if anios else None), (max(anios) if anios else None)

# ---------------------------------------------------------------------------
# FUNCIONES · 5. SELECCIÓN Y DESCARGA DEL DETALLE DE CADA ESTADO
# (etapa «descarga»)
# Recorrido igual al del navegador, en una sola sesión: búsqueda de la
# emisora → páginas de resultados → lupa de la fila «Estados Financieros» →
# página de detalle (ver incidencias_fuente.md, «el detalle solo abre en la
# misma sesión»).
# ---------------------------------------------------------------------------
def buscar_todos(sesion, pagina_base, url_accion, codigo, es_retirada, pagina):
    """
    Pide los estados intermedios individuales de una emisora con año y
    trimestre en TODOS. Con pagina = 1 hace la búsqueda; con pagina > 1 pide
    esa página de resultados a partir de la página anterior (pagina_base).
    """
    datos = armar_datos(pagina_base)
    if pagina == 1:
        datos.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "", CAMPO_EMPRESA: codigo,
                      CAMPO_TIPO: TIPO_DESCARGA, CAMPO_PERIODO: "T", CAMPO_ANIO: "-1",
                      CAMPO_TRIMESTRE: "-1", BOTON_BUSCAR: "Buscar"})
        if es_retirada:
            datos[CAMPO_RETIRADAS] = "on"
        else:
            datos.pop(CAMPO_RETIRADAS, None)
    else:
        datos.update({"__EVENTTARGET": NOMBRE_GRILLA, "__EVENTARGUMENT": f"Page${pagina}"})
    resp = solicitar(sesion, url_accion, datos,
                     detalle=f"empresa {codigo} | tipo {TIPO_DESCARGA} | periodo T | "
                             f"año TODOS | trimestre TODOS | página {pagina}")
    sopa = BeautifulSoup(resp.text, "html.parser")
    leer_empresas(sopa)                              # comprueba que es la página esperada
    return sopa


def filas_con_lupa(sopa):
    """
    Devuelve las filas de «Estados Financieros» de una página de resultados,
    cada una con su año, trimestre (1 a 4), N.º de expediente, fecha de
    presentación y el nombre del botón de la lupa. Las columnas se ubican por
    su encabezado, como en filas_grilla. Una fila sin lupa o con un periodo
    desconocido se registra como advertencia y no se usa.
    """
    tabla = sopa.find("table", id=ID_GRILLA)
    if tabla is None or not tabla.find_all("tr"):
        return []
    filas_html = tabla.find_all("tr")
    encabezado = [c.get_text(" ", strip=True) for c in filas_html[0].find_all(["th", "td"])]
    if "Documento" not in encabezado:
        return []                                    # aviso «No se encontraron registros»
    col = {nombre: i for i, nombre in enumerate(encabezado)}
    col_exp = next((i for nombre, i in col.items() if "xpediente" in nombre), None)
    if "Año" not in col or "Período" not in col or col_exp is None:
        raise Detener(f"la grilla no tiene las columnas Año, Período y Expediente: {encabezado}")
    filas = []
    for tr in filas_html[1:]:
        celdas = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(celdas) < len(encabezado) - 1 or celdas[col["Documento"]] != "Estados Financieros":
            continue
        anio, periodo = celdas[col["Año"]], celdas[col["Período"]].upper()
        expediente = re.sub(r"[^0-9A-Za-z]", "", celdas[col_exp])
        lupa = tr.find("input", {"type": "image"})
        if not anio.isdigit() or periodo not in PERIODO_A_TRIMESTRE or lupa is None or not expediente:
            registrar(f"ADVERTENCIA: fila no reconocida (año «{anio}», periodo «{periodo}», "
                      f"expediente «{expediente}», lupa {'sí' if lupa else 'no'}): no se usa")
            continue
        fecha = celdas[col["Fecha de Presentación"]] if "Fecha de Presentación" in col else ""
        filas.append({"anio": int(anio), "trim": PERIODO_A_TRIMESTRE[periodo],
                      "expediente": expediente, "fecha": fecha, "sello": sello_fecha(fecha),
                      "lupa": lupa.get("name")})
    return filas


def paginas_emisora(sesion, pagina_base, url_accion, codigo, es_retirada):
    """
    Recorre todas las páginas de resultados de una emisora y devuelve la lista
    de (página, filas). Las páginas se conservan porque la lupa de cada fila
    se pulsa desde la página en la que aparece. Si la primera búsqueda no trae
    ninguna fila, se repite una vez (respuesta intermitente, ver
    incidencias_fuente.md).
    """
    sopa = buscar_todos(sesion, pagina_base, url_accion, codigo, es_retirada, 1)
    if not filas_con_lupa(sopa):
        registrar(f"ADVERTENCIA: empresa {codigo} sin resultados; se repite la búsqueda una vez")
        time.sleep(PAUSA_ENTRE_EMISORAS)
        sopa = buscar_todos(sesion, pagina_base, url_accion, codigo, es_retirada, 1)
    paginas, numero = [], 1
    while True:
        paginas.append((sopa, filas_con_lupa(sopa)))
        tabla = sopa.find("table", id=ID_GRILLA)
        enlaces = set() if tabla is None else {int(n) for n in re.findall(r"Page\$(\d+)", str(tabla))}
        if numero + 1 not in enlaces or numero >= MAX_PAGINAS:
            if numero >= MAX_PAGINAS and numero + 1 in enlaces:
                raise Detener(f"empresa {codigo} tiene más de {MAX_PAGINAS} páginas: el conteo quedaría incompleto")
            return paginas
        numero += 1
        sopa = buscar_todos(sesion, sopa, url_accion, codigo, es_retirada, numero)


def contar_trimestres(paginas):
    """Trimestres distintos (año, trimestre) de ANIO_PERIODO_MIN a ANIO_PERIODO_MAX."""
    return {(f["anio"], f["trim"]) for _, filas in paginas for f in filas
            if ANIO_PERIODO_MIN <= f["anio"] <= ANIO_PERIODO_MAX}


def sello_fecha(fecha):
    """
    Convierte la fecha de presentación de la grilla («20/03/2026 08:18:52 p.m.»)
    en un sello ordenable AAAAMMDDhhmmss (hora de 24 horas). Si el formato no
    se reconoce, devuelve solo sus dígitos.
    """
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})\s*([ap])", fecha.lower())
    if not m:
        return re.sub(r"\D", "", fecha)
    dia, mes, anio, hora, minuto, segundo, ampm = m.groups()
    hora = int(hora) % 12 + (12 if ampm == "p" else 0)
    return f"{anio}{mes}{dia}{hora:02d}{minuto}{segundo}"


def nombre_crudo(codigo, fila):
    """
    Nombre del archivo crudo: matrícula, fuente, código SMV, año, trimestre,
    tipo y N.º de expediente. El expediente distingue los casos en que un
    trimestre se presentó con más de un expediente (reexpresión); el 03 elige
    cuál usa. Si un mismo expediente tiene varias presentaciones, se guarda
    una sola: la que elige la regla de seleccionar_y_descargar.
    """
    return (f"datos_crudos_{CODIGO_MATRICULA}_smv_{codigo}_{fila['anio']}T{fila['trim']}"
            f"_{TIPO_DESCARGA}_exp{fila['expediente']}.html")


def leer_unidad(texto):
    """Unidad monetaria del título del detalle (por ejemplo, «EN MILES DE NUEVOS SOLES»)."""
    hallada = re.search(r"EN\s+(?:MILES\s+DE\s+|MILLONES\s+DE\s+)?(?:NUEVOS\s+)?"
                        r"(?:SOLES|D[ÓO]LARES(?:\s+AMERICANOS|\s+ESTADOUNIDENSES)?)", texto.upper())
    return re.sub(r"\s+", " ", hallada.group(0)) if hallada else "NO_ENCONTRADA"


def validar_detalle(texto, fila):
    """
    Comprueba la página de detalle ANTES de guardarla:
      1) que traiga las tablas del balance (grdBalanceGeneral) y del estado
         de resultados (grdEstadoGP); si faltan, la sesión pudo perderse;
      2) que la fecha de cierre del título («AL 31 DE MARZO DE 2025»)
         corresponda al año y trimestre pedidos.
    Si algo no coincide, se detiene: guardar un estado de otro trimestre con
    el nombre equivocado es una mala práctica que contamina el panel.
    Devuelve True si las dos tablas traen contenido y False si alguna viene
    vacía (la fuente publicó esa presentación sin el estado).
    """
    sopa = BeautifulSoup(texto, "html.parser")
    con_contenido = True
    for tabla in ("grdBalanceGeneral", "grdEstadoGP"):
        encontrada = sopa.find("table", id=re.compile(tabla))
        if encontrada is None:
            raise Detener(f"el detalle de {fila['anio']}T{fila['trim']} no trae la tabla {tabla}")
        # Tabla presente pero vacía (la página dice «No se encontraron registro…»).
        if len(encontrada.find_all("tr")) < 5:
            con_contenido = False
    plano = sopa.get_text(" ", strip=True).upper()
    cierre = re.search(r"AL\s+\d{1,2}\s+DE\s+([A-ZÁÉÍÓÚ]+)\s+(?:DEL?\s+)?(\d{4})", plano)
    if cierre is None:
        registrar(f"ADVERTENCIA: no se encontró la fecha de cierre en el título de "
                  f"{fila['anio']}T{fila['trim']}; se guarda y se revisa en el 03")
        return con_contenido
    mes, anio = cierre.group(1), int(cierre.group(2))
    if anio != fila["anio"] or MES_A_TRIMESTRE.get(mes) != fila["trim"]:
        raise Detener(f"el título del detalle dice «{cierre.group(0)}», pero se pidió "
                      f"{fila['anio']}T{fila['trim']}")
    return con_contenido


def abrir_detalle(sesion, sopa, url_accion, codigo, fila):
    """
    Pulsa la lupa de la fila (el navegador envía el nombre del botón con .x y
    .y, las coordenadas del clic), toma de la respuesta el enlace a
    Frm_DetalleInfoFinanciera.aspx, lo abre en la misma sesión y lo valida.
    Devuelve (respuesta del detalle, True si trae contenido). No guarda nada.
    """
    datos = armar_datos(sopa)
    datos.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "",
                  f"{fila['lupa']}.x": "10", f"{fila['lupa']}.y": "10"})
    resp = solicitar(sesion, url_accion, datos,
                     detalle=f"empresa {codigo} | lupa {fila['anio']}T{fila['trim']} | "
                             f"expediente {fila['expediente']} | presentado {fila['fecha']}")
    if "Frm_DetalleInfoFinanciera" in resp.url:
        detalle = resp                               # el portal ya redirigió al detalle
    else:
        enlace = re.search(r"Frm_DetalleInfoFinanciera\.aspx\?data=[^'\"\s<>]+", resp.text, re.I)
        if enlace is None:
            raise Detener(f"la respuesta de la lupa ({fila['anio']}T{fila['trim']}) "
                          "no trae el enlace al detalle")
        url_detalle = urljoin(resp.url, html.unescape(enlace.group(0)))
        detalle = solicitar(sesion, url_detalle,
                            detalle=f"detalle empresa {codigo} | {fila['anio']}T{fila['trim']}")
    return detalle, validar_detalle(detalle.text, fila)


def guardar_detalle(detalle, codigo, fila, ruta):
    """Guarda los bytes del detalle tal como llegaron y lo registra. Devuelve la unidad."""
    ruta.write_bytes(detalle.content)
    unidad = leer_unidad(detalle.text)
    registrar(f"CRUDO | {codigo} | {fila['anio']}T{fila['trim']} | exp {fila['expediente']} | "
              f"presentado {fila['fecha']} | {ruta.name} | {len(detalle.content)} bytes | "
              f"SHA-256 {sha256_bytes(detalle.content)} | unidad {unidad}")
    if unidad == "NO_ENCONTRADA":
        registrar(f"ADVERTENCIA: {ruta.name} sin unidad reconocible en el título; revisar en el 03")
    return unidad


def seleccionar_y_descargar(sesion, pagina_base, url_accion, codigo, es_retirada, carpeta, tope=None):
    """
    Cuenta los trimestres individuales de la emisora y aplica la regla
    MIN_TRIMESTRES. Devuelve un diccionario con la decisión:
      INCLUIDA       tiene los MIN_TRIMESTRES: se descargan sus detalles de
                     ANIO_PERIODO_MIN a ANIO_PERIODO_MAX (los que ya existen
                     no se vuelven a pedir);
      EXCLUIDA       tiene menos trimestres que la regla;
      SIN_RESPUESTA  la búsqueda salió vacía dos veces: puede ser una emisora
                     sin ningún estado o una respuesta intermitente del
                     portal, así que NO se trata como excluida y se revisa.
    """
    paginas = paginas_emisora(sesion, pagina_base, url_accion, codigo, es_retirada)
    trimestres = contar_trimestres(paginas)
    total_filas = sum(len(filas) for _, filas in paginas)
    cuenta = {"trimestres": len(trimestres), "guardados": 0, "ya_existian": 0,
              "filas_repetidas": 0, "unidades": set()}
    if total_filas == 0:
        cuenta["decision"] = "SIN_RESPUESTA"
        return cuenta
    if len(trimestres) < MIN_TRIMESTRES:
        cuenta["decision"] = "EXCLUIDA"
        return cuenta
    cuenta["decision"] = "INCLUIDA"
    # Filas del rango agrupadas por trimestre (todas sus presentaciones y expedientes).
    grupos = {}
    for sopa, filas in paginas:
        for f in filas:
            if ANIO_PERIODO_MIN <= f["anio"] <= ANIO_PERIODO_MAX:
                grupos.setdefault((f["anio"], f["trim"]), []).append((sopa, f))
    for (anio, trim), grupo in sorted(grupos.items()):
        # Reanudación: si el trimestre ya tiene su crudo, no se vuelve a pedir.
        patron = f"datos_crudos_{CODIGO_MATRICULA}_smv_{codigo}_{anio}T{trim}_{TIPO_DESCARGA}_exp*.html"
        if any(carpeta.glob(patron)):
            cuenta["ya_existian"] += 1
            continue
        # Presentaciones distintas (expediente + fecha), de la más reciente a la más antigua.
        unicas, vistas = [], set()
        for sopa, fila in sorted(grupo, key=lambda x: (x[1]["sello"], x[1]["expediente"]), reverse=True):
            clave = (fila["expediente"], fila["sello"])
            if clave in vistas:
                cuenta["filas_repetidas"] += 1       # misma fila dos veces en la grilla
                continue
            vistas.add(clave)
            unicas.append((sopa, fila))
        # Regla de presentaciones: se guarda UN crudo por trimestre, el de la presentación
        # más reciente que trae el estado de situación financiera y el estado de
        # resultados con contenido, sea del mismo expediente o de otro. Las demás no se
        # guardan y quedan registradas en el log. Si todas vienen incompletas, se guarda
        # la más reciente (dato faltante en el 03).
        elegida, incompletas, primera = None, [], None
        for sopa, fila in unicas:
            detalle, con_contenido = abrir_detalle(sesion, sopa, url_accion, codigo, fila)
            primera = primera or (detalle, fila)
            if con_contenido:
                elegida = (detalle, fila)
                break
            incompletas.append(f"exp {fila['expediente']} ({fila['fecha']})")
        if elegida is None:
            elegida = primera
            incompletas.pop(0)                       # la más reciente sí se guarda
            registrar(f"ADVERTENCIA: {codigo} {anio}T{trim}: ninguna presentación trae el estado "
                      "completo; se guarda la más reciente (dato faltante en el 03)")
        ruta = carpeta / nombre_crudo(codigo, elegida[1])
        cuenta["unidades"].add(guardar_detalle(elegida[0], codigo, elegida[1], ruta))
        cuenta["guardados"] += 1
        if len(unicas) > 1:
            otras = [f"exp {f['expediente']} ({f['fecha']})" for _, f in unicas if f is not elegida[1]]
            registrar(f"PRESENTACIONES | {codigo} | {anio}T{trim} | {len(unicas)} presentaciones | "
                      f"guardada: exp {elegida[1]['expediente']} ({elegida[1]['fecha']}) | "
                      f"no guardadas: {', '.join(otras)} | "
                      f"de ellas incompletas: {', '.join(incompletas) or '-'}")
        if tope is not None and cuenta["guardados"] >= tope:
            return cuenta
    return cuenta

def decisiones_previas():
    """
    Última decisión de cada emisora según las líneas SELECCION del log
    (la descarga va por lotes y se puede reanudar). {código: decisión}.
    """
    ultima = {}
    if not RUTA_LOG.exists():
        return ultima
    for linea in RUTA_LOG.read_text(encoding="utf-8").splitlines():
        partes = linea.split(" | ")
        if len(partes) > 4 and partes[2] == "SELECCION" and partes[3] in (
                "INCLUIDA", "EXCLUIDA", "SIN_RESPUESTA"):
            ultima[partes[4]] = partes[3]
    return ultima


def resumen_seleccion():
    """
    Resumen acumulado de la selección con la última decisión de cada emisora.
    Indica cuántas emisoras faltan por evaluar y, al completarse las 44, las
    filas que tendrá el panel.
    """
    evaluadas = {c: d for c, d in decisiones_previas().items() if c in EMISORAS}
    conteo = {d: sum(1 for x in evaluadas.values() if x == d)
              for d in ("INCLUIDA", "EXCLUIDA", "SIN_RESPUESTA")}
    faltan = len(EMISORAS) - len(evaluadas)
    registrar(f"RESUMEN SELECCION | evaluadas {len(evaluadas)} de {len(EMISORAS)} | "
              f"incluidas {conteo['INCLUIDA']} | excluidas {conteo['EXCLUIDA']} | "
              f"sin respuesta {conteo['SIN_RESPUESTA']} | faltan por evaluar {faltan}")
    if faltan == 0:
        filas = conteo["INCLUIDA"] * (MIN_TRIMESTRES - 4)
        registrar(f"RESUMEN SELECCION | FINAL: {conteo['INCLUIDA']} emisoras × "
                  f"{MIN_TRIMESTRES - 4} trimestres de 2012T1-2025T4 = {filas} filas esperadas")
        if conteo["SIN_RESPUESTA"]:
            registrar("ADVERTENCIA: hay emisoras SIN_RESPUESTA; repetir su lote antes de cerrar la selección")

# ---------------------------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# ---------------------------------------------------------------------------
def etapa_lista(vigentes, retiradas):
    """Registra cada emisora con su código SMV y su estado."""
    for estado, grupo in (("vigente", vigentes), ("retirada", retiradas)):
        for codigo, nombre in sorted(grupo.items(), key=lambda x: x[1]):
            registrar(f"EMISORA | {codigo} | {nombre} | {estado}")


def etapa_verificacion(sesion, paginas, url_accion, vigentes, retiradas, demo):
    """Cuenta los estados Individuales y Consolidados de cada emisora elegida."""
    if not EMISORAS:
        raise Detener("EMISORAS está vacía: complétala con los códigos SMV tras la etapa «lista»")
    codigos = EMISORAS[:1] if demo else EMISORAS
    desconocidos = [c for c in codigos if c not in vigentes and c not in retiradas]
    if desconocidos:
        raise Detener(f"códigos que no están en la lista de la SMV: {desconocidos}")
    # Una línea VERIFICACION por emisora: es la evidencia de la decisión del tipo.
    con_consolidado = 0
    for k, codigo in enumerate(codigos, start=1):
        if k > 1:
            time.sleep(PAUSA_ENTRE_EMISORAS)
        es_retirada = codigo in retiradas
        nombre = retiradas.get(codigo) or vigentes.get(codigo)
        base = paginas[1] if es_retirada else paginas[0]
        resultado = {}
        for tipo in TIPOS_VERIFICACION:
            resultado[tipo] = contar_estados(sesion, base, url_accion, codigo, tipo, es_retirada)
        texto = " | ".join(f"{t}: {n} trimestres ({a or '-'}-{b or '-'})"
                           for t, (n, a, b) in resultado.items())
        registrar(f"VERIFICACION [{k}/{len(codigos)}] | {codigo} | {nombre} | "
                  f"{'retirada' if es_retirada else 'vigente'} | {texto}")
        if resultado.get("C", (0,))[0] > 0:
            con_consolidado += 1
    registrar(f"VERIFICACION | con estados consolidados: {con_consolidado} de {len(codigos)} emisoras "
              f"(trimestres de {ANIO_PERIODO_MIN} a {ANIO_PERIODO_MAX})")


def etapa_descarga(sesion, paginas, url_accion, vigentes, retiradas, lote, demo):
    """
    Aplica la regla de selección y descarga las emisoras incluidas del lote
    pedido (o de todas, si no se pide lote). Cada emisora deja una línea
    SELECCION (INCLUIDA, EXCLUIDA o SIN_RESPUESTA, con su conteo) y, si se
    descargó, una línea DESCARGA. Al final se registra el resumen acumulado.
    En --demo evalúa la primera emisora y guarda DEMO_DETALLES detalles en
    una carpeta temporal, fuera de datos_crudos/.
    """
    if not EMISORAS:
        raise Detener("EMISORAS está vacía: complétala con los códigos SMV tras la etapa «lista»")
    desconocidos = [c for c in EMISORAS if c not in vigentes and c not in retiradas]
    if desconocidos:
        raise Detener(f"códigos que no están en la lista de la SMV: {desconocidos}")
    total_lotes = -(-len(EMISORAS) // LOTE_TAMANO)          # división redondeada hacia arriba
    if demo:
        codigos, carpeta, tope = EMISORAS[:1], Path(tempfile.mkdtemp(prefix="demo_smv_")), DEMO_DETALLES
        registrar(f"DESCARGA | modo demostración: emisora {codigos[0]}, {tope} detalles "
                  f"en {carpeta} (no se tocan los crudos oficiales)")
    elif lote is not None:
        if not 1 <= lote <= total_lotes:
            raise Detener(f"el lote debe estar entre 1 y {total_lotes}")
        inicio = (lote - 1) * LOTE_TAMANO
        codigos, carpeta, tope = EMISORAS[inicio:inicio + LOTE_TAMANO], CARPETA_CRUDOS, None
        registrar(f"DESCARGA | lote {lote} de {total_lotes} | emisoras {inicio + 1} a "
                  f"{inicio + len(codigos)} de {len(EMISORAS)}")
    else:
        codigos, carpeta, tope = EMISORAS, CARPETA_CRUDOS, None
        registrar(f"DESCARGA | todas las emisoras ({len(EMISORAS)}) en una sola ejecución")
    registrar(f"DESCARGA | regla de selección: al menos {MIN_TRIMESTRES} trimestres individuales "
              f"distintos de {ANIO_PERIODO_MIN}T1 a {ANIO_PERIODO_MAX}T4")
    carpeta.mkdir(parents=True, exist_ok=True)
    previas = decisiones_previas()

    for k, codigo in enumerate(codigos, start=1):
        if k > 1:
            time.sleep(PAUSA_ENTRE_EMISORAS)
        es_retirada = codigo in retiradas
        nombre = retiradas.get(codigo) or vigentes.get(codigo)
        base = paginas[1] if es_retirada else paginas[0]
        estado = "retirada" if es_retirada else "vigente"
        cuenta = seleccionar_y_descargar(sesion, base, url_accion, codigo, es_retirada, carpeta, tope)
        motivo = {"INCLUIDA": "cumple la regla",
                  "EXCLUIDA": f"menos de {MIN_TRIMESTRES} trimestres",
                  "SIN_RESPUESTA": "búsqueda vacía dos veces (posible respuesta intermitente)"}
        # Si ya salió vacía en una ejecución anterior, no es una falla momentánea:
        # la emisora no tiene estados individuales en el portal y queda excluida.
        if cuenta["decision"] == "SIN_RESPUESTA" and previas.get(codigo) == "SIN_RESPUESTA" and not demo:
            cuenta["decision"] = "EXCLUIDA"
            motivo["EXCLUIDA"] = "búsqueda vacía también en una ejecución anterior: sin estados individuales"
        registrar(f"SELECCION | {cuenta['decision']} | {codigo} | {nombre} | {estado} | "
                  f"trimestres {ANIO_PERIODO_MIN}T1-{ANIO_PERIODO_MAX}T4: {cuenta['trimestres']} "
                  f"de {MIN_TRIMESTRES} | {motivo[cuenta['decision']]}")
        if cuenta["decision"] == "SIN_RESPUESTA":
            registrar(f"ADVERTENCIA: {codigo} sin respuesta; volver a ejecutar este lote "
                      "(si vuelve a salir vacía, queda EXCLUIDA)")
        if cuenta["decision"] == "INCLUIDA":
            registrar(f"DESCARGA [{k}/{len(codigos)}] | {codigo} | {nombre} | guardados ahora: "
                      f"{cuenta['guardados']} | ya existían: {cuenta['ya_existian']} | "
                      f"unidades: {', '.join(sorted(cuenta['unidades'])) or '-'}")
    if not demo:
        resumen_seleccion()


def main():
    parser = argparse.ArgumentParser(description="Script 02 — descarga programática (SMV)")
    parser.add_argument("--etapa", choices=["lista", "verificacion", "descarga"], required=True)
    parser.add_argument("--demo", action="store_true", help="versión corta para la demostración en vivo")
    parser.add_argument("--lote", type=int, help="solo para «descarga»: número de lote (LOTE_TAMANO emisoras)")
    args = parser.parse_args()

    # Control previo: correo de contacto en el User-Agent.
    if "REEMPLAZAR" in CORREO_CONTACTO or "@" not in CORREO_CONTACTO:
        sys.exit("ERROR: escribe tu correo en CORREO_CONTACTO (parte de parámetros) antes de ejecutar.")

    # Inicio en el log: versiones, User-Agent y pausas (para reproducir la ejecución).
    registrar("=" * 70)
    registrar(f"INICIO script 02 — descarga programática (SMV) | etapa {args.etapa}"
              f"{' | MODO DEMOSTRACIÓN' if args.demo else ''}"
              f"{f' | lote {args.lote}' if args.lote and not args.demo else ''}")
    registrar(f"Python {platform.python_version()} | requests {requests.__version__} | "
              f"beautifulsoup4 {bs4.__version__}")
    registrar(f"User-Agent: {USER_AGENT} | pausa {PAUSA_SEG} s | entre emisoras {PAUSA_ENTRE_EMISORAS} s")
    verificar_encabezado()

    # Una sola sesión para todas las solicitudes, como en el navegador.
    sesion = requests.Session()
    sesion.headers.update({"User-Agent": USER_AGENT})
    try:
        # Orden fijo: robots.txt → listas de emisoras → etapa pedida.
        revisar_robots(sesion)
        pag_vig, pag_ret, url_accion, vigentes, retiradas = obtener_listas(sesion)
        if args.etapa == "lista":
            etapa_lista(vigentes, retiradas)
        elif args.etapa == "verificacion":
            etapa_verificacion(sesion, (pag_vig, pag_ret), url_accion, vigentes, retiradas, args.demo)
        else:
            etapa_descarga(sesion, (pag_vig, pag_ret), url_accion, vigentes, retiradas,
                           args.lote, args.demo)
    # Ante una respuesta inesperada, se registra el motivo y se termina.
    except Detener as motivo:
        registrar(f"DETENIDO: {motivo}. No se reintenta; revisar antes de volver a ejecutar.")
        registrar("=" * 70)
        sys.exit(1)
    registrar(f"FIN correcto | etapa {args.etapa}")
    registrar("=" * 70)


if __name__ == "__main__":
    main()
