# Nombres y apellidos: Vania Adriana Egas Araujo
# Código de matrícula: 2024200498D
# Tema N.º 82 del temario: Apalancamiento operativo y financiero en la industria manufacturera peruana
# Fecha de extracción: 2026-11-25
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
  descarga      (se agrega en la parte siguiente) Descarga el detalle de cada
                emisora × año × trimestre y lo guarda TAL COMO LLEGA en
                datos_crudos/smv/, con su SHA-256.

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

    Orden: primero «lista»; con esa lista se completa EMISORAS y luego se
    ejecuta «verificacion». El modo --demo es la versión corta para la
    demostración en vivo.

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
import argparse
import hashlib
import platform
import re
import sys
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

# Emisoras del panel: códigos SMV (la llave que une cada trimestre en el 03).
# Se completan después de ejecutar la etapa «lista». Ejemplo: Alicorp = "73".
EMISORAS = ["73", "74470", "49", "47", "43173", "75981", "198", "101", "102", "108", "119", "330", "123", "112860", "117", "84522", "30011", "45", "33862", "57255", "250", "162", "191", "165", "4", "46", "51219", "148", "150808", "154463", "117471", "162521", "83510", "122783", "120088", "152418", "98", "95", "114979", "107", "87", "306", "201", "80"]

# Tipos de estado que compara la etapa «verificacion».
# I = Individual, C = Consolidado. El tipo del panel se decide con ese conteo.
TIPOS_VERIFICACION = ("I", "C")

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


def main():
    parser = argparse.ArgumentParser(description="Script 02 — descarga programática (SMV)")
    parser.add_argument("--etapa", choices=["lista", "verificacion", "descarga"], required=True)
    parser.add_argument("--demo", action="store_true", help="versión corta para la demostración en vivo")
    args = parser.parse_args()

    # Controles previos: correo de contacto y etapa disponible.

    if "REEMPLAZAR" in CORREO_CONTACTO or "@" not in CORREO_CONTACTO:
        sys.exit("ERROR: escribe tu correo en CORREO_CONTACTO (parte de parámetros) antes de ejecutar.")
    if args.etapa == "descarga":
        sys.exit("La etapa «descarga» se agrega en la siguiente parte del script.")

    # Inicio en el log: versiones, User-Agent y pausas (para reproducir la ejecución).
    registrar("=" * 70)
    registrar(f"INICIO script 02 — descarga programática (SMV) | etapa {args.etapa}"
              f"{' | MODO DEMOSTRACIÓN' if args.demo else ''}")
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
        else:
            etapa_verificacion(sesion, (pag_vig, pag_ret), url_accion, vigentes, retiradas, args.demo)
    # Ante una respuesta inesperada, se registra el motivo y se termina.
    except Detener as motivo:
        registrar(f"DETENIDO: {motivo}. No se reintenta; revisar antes de volver a ejecutar.")
        registrar("=" * 70)
        sys.exit(1)
    registrar(f"FIN correcto | etapa {args.etapa}")
    registrar("=" * 70)


if __name__ == "__main__":
    main()
