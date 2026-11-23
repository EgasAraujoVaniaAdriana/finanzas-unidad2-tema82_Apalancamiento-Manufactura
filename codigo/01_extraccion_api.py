# Nombres y apellidos: Vania Adriana Egas Araujo
# Código de matrícula: 2024200498D
# Tema N.º 82 del temario: Apalancamiento operativo y financiero en la industria manufacturera peruana
# Fecha de extracción: 2026-11-23
"""
Script 01 — Extracción por API (BCRPData, Banco Central de Reserva del Perú).

Qué hace:
  1. Descarga, mediante la API oficial de BCRPData, dos series mensuales:
       - PN01764AM: PBI de la manufactura no primaria (índice 2007 = 100).
         En el script 03 se convierte en pbi_manuf_var (variación % interanual
         del promedio trimestral).
       - PN38705PM: Índice de Precios al Consumidor de Lima Metropolitana
         (índice dic. 2021 = 100; fuente primaria: INEI). En el script 03 sirve
         para deflactar el activo total en ln_activos.
  2. Valida cada respuesta (HTTP 200, JSON legible, nombre de la serie
     correcto y meses completos) antes de guardarla.
  3. Guarda cada respuesta TAL COMO LLEGA (bytes sin editar) en
     datos_crudos/bcrp/, con el código de matrícula en el nombre del archivo
     (numeral 2.4.2), y calcula su SHA-256.
  4. Registra cada solicitud en log_ejecucion.txt (fecha y hora, URL, código
     HTTP, bytes y observaciones) y cada archivo guardado (observaciones, cobertura y SHA-256).

Ejecución (desde la raíz del proyecto):
    python codigo/01_extraccion_api.py

BCRPData no requiere clave de API. Documentación oficial de la API:
https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api
"""

import hashlib
import json
import platform
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# ---------------------------------------------------------------------------
# RUTAS (siempre relativas a la raíz del proyecto; nunca rutas de Colab/Drive)
# ---------------------------------------------------------------------------
# Los archivos de datos llevan el código de matrícula (numeral 2.4.2).
CODIGO_MATRICULA = "2024200498D"
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_CRUDOS = RAIZ / "datos_crudos" / "bcrp"
RUTA_LOG = RAIZ / "log_ejecucion.txt"

# ---------------------------------------------------------------------------
# PARÁMETROS DEL ESTUDIO (constantes fijas; nunca «hoy»)
# ---------------------------------------------------------------------------
# Panel de análisis: del primer trimestre de 2012 al cuarto trimestre de 2025.
FECHA_INICIO = "2012T1"
FECHA_CORTE = "2025T4"
# La descarga empieza UN AÑO ANTES de FECHA_INICIO (enero de 2011), porque
# las variaciones interanuales (t-4) y los rezagos (t-1) necesitan el año
# previo. El rango se calcula a partir de estas dos constantes (ver
# rango_descarga), para que no puedan quedar desalineados.

# ---------------------------------------------------------------------------
# PARÁMETROS DE LA API
# Formato oficial:
#   {URL_BASE}/{código de serie}/{formato}/{periodo inicial}/{periodo final}/{idioma}
# Periodos mensuales con el formato AAAA-M (por ejemplo, 2011-1 y 2025-12).
# ---------------------------------------------------------------------------
URL_BASE = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
FORMATO = "json"
IDIOMA = "esp"

# Series a descargar. «texto_esperado» es un fragmento del nombre que la API
# devuelve en config.series[0].name: si no aparece, el código de serie no es
# el que creemos y el archivo NO se guarda.
SERIES = {
    "PN01764AM": {
        "descripcion": "PBI manufactura no primaria (índice 2007 = 100), mensual",
        "uso": "pbi_manuf_var en el script 03",
        "texto_esperado": "manufactura no primaria",
    },
    "PN38705PM": {
        "descripcion": "IPC Lima Metropolitana (índice dic. 2021 = 100), mensual, fuente INEI",
        "uso": "deflactor de ln_activos en el script 03",
        "texto_esperado": "índice de precios al consumidor (ipc)",
    },
}

# Identificación del proyecto ante el servidor y pausa entre solicitudes.
# REEMPLAZAR por tu correo antes de ejecutar (el script se detiene si no).
CORREO_CONTACTO = "e_2024200498D@uncp.edu.pe"
USER_AGENT = (
    "ProyectoAcademico-FinanzasI-UNCP-Tema82/1.0 "
    f"(uso academico; contacto: {CORREO_CONTACTO})"
)
PAUSA_SEG = 1.5      # pausa mínima entre solicitudes (consigna: ≥ 1 s)
TIMEOUT_SEG = 60     # tiempo máximo de espera por solicitud
MAX_INTENTOS = 3     # reintentos si falla la conexión o el HTTP no es 200

ZONA_HORARIA = ZoneInfo("America/Lima")
MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
            "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------
def ahora():
    """Fecha y hora actual de Lima, con zona horaria (para el log)."""
    return datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d %H:%M:%S %z")


def registrar(mensaje):
    """Muestra el mensaje en consola y lo agrega al log_ejecucion.txt."""
    linea = f"{ahora()} | 01_extraccion_api | {mensaje}"
    print(linea)
    with open(RUTA_LOG, "a", encoding="utf-8", newline="\n") as log:
        log.write(linea + "\n")


def rango_descarga():
    """
    Calcula el periodo inicial y final de la API a partir de FECHA_INICIO y
    FECHA_CORTE. Inicio = enero del año anterior a FECHA_INICIO; fin = último
    mes del trimestre de FECHA_CORTE. Devuelve, por ejemplo, ("2011-1", "2025-12").
    """
    patron = re.compile(r"^(\d{4})T([1-4])$")
    m_ini, m_fin = patron.match(FECHA_INICIO), patron.match(FECHA_CORTE)
    if not m_ini or not m_fin:
        sys.exit("ERROR: FECHA_INICIO y FECHA_CORTE deben tener el formato AAAAT#, p. ej. 2012T1.")
    anio_ini = int(m_ini.group(1)) - 1
    anio_fin, trimestre_fin = int(m_fin.group(1)), int(m_fin.group(2))
    return f"{anio_ini}-1", f"{anio_fin}-{3 * trimestre_fin}"


def meses_esperados(desde, hasta):
    """Lista de periodos con el formato que usa la API («Ene.2011» … «Dic.2025»)."""
    anio, mes = map(int, desde.split("-"))
    anio_fin, mes_fin = map(int, hasta.split("-"))
    meses = []
    while (anio, mes) <= (anio_fin, mes_fin):
        meses.append(f"{MESES_ES[mes - 1]}.{anio}")
        mes += 1
        if mes == 13:
            anio, mes = anio + 1, 1
    return meses


def sha256(ruta):
    """SHA-256 del archivo guardado (evidencia de que el crudo no se editó)."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def validar_respuesta(contenido, codigo, desde, hasta):
    """
    Revisa la respuesta SIN modificarla. Devuelve (es_valida, resumen, avisos).
      - Bloqueantes (no se guarda): no es JSON, no trae datos, o el nombre de
        la serie no coincide con el esperado.
      - Avisos (se guarda, pero queda registrado): meses faltantes o
        sobrantes, valores «n.d.» o valores no numéricos.
    """
    avisos = []
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1")  # solo para leer; el crudo se guarda en bytes
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        return False, {}, ["la respuesta no es un JSON válido (¿página de error?)"]

    periodos = datos.get("periods") or []
    series_cfg = (datos.get("config") or {}).get("series") or []
    if not periodos or not series_cfg:
        return False, {}, ["la respuesta no contiene periodos o metadatos de la serie"]

    nombre = series_cfg[0].get("name", "")
    if SERIES[codigo]["texto_esperado"] not in nombre.lower():
        return False, {}, [f"el nombre devuelto no coincide con lo esperado: «{nombre}»"]

    nombres_periodo = [p.get("name") for p in periodos]
    esperados = meses_esperados(desde, hasta)
    if nombres_periodo != esperados:
        faltan = sorted(set(esperados) - set(nombres_periodo))
        sobran = sorted(set(nombres_periodo) - set(esperados))
        avisos.append(f"cobertura distinta a la pedida: faltan {len(faltan)} meses "
                      f"{faltan[:6]}, sobran {len(sobran)} {sobran[:6]}")

    no_disponibles, no_numericos = 0, 0
    for p in periodos:
        valor = (p.get("values") or [""])[0]
        if valor == "n.d.":
            no_disponibles += 1
            continue
        try:
            float(valor)
        except (TypeError, ValueError):
            no_numericos += 1
    if no_disponibles:
        avisos.append(f"{no_disponibles} meses con valor «n.d.» (no disponible en la fuente)")
    if no_numericos:
        avisos.append(f"{no_numericos} meses con valores no numéricos")

    resumen = {
        "nombre": nombre,
        "observaciones": len(periodos),
        "primer_periodo": nombres_periodo[0],
        "ultimo_periodo": nombres_periodo[-1],
        "no_disponibles": no_disponibles,
    }
    return True, resumen, avisos


def descargar_serie(sesion, codigo, desde, hasta):
    """
    Solicita una serie a la API, la valida y, solo si es válida, guarda los
    bytes recibidos sin editar. Si falla, NO toca el crudo que ya existiera.
    Devuelve un resumen de la descarga (su «estado» indica si se guardó).
    """
    url = f"{URL_BASE}/{codigo}/{FORMATO}/{desde}/{hasta}/{IDIOMA}"
    ruta = CARPETA_CRUDOS / f"datos_crudos_{CODIGO_MATRICULA}_bcrp_{codigo}.json"
    fila = {"fecha_hora": "", "codigo": codigo, "url": url, "http": "",
            "bytes": "", "observaciones": "", "primer_periodo": "",
            "ultimo_periodo": "", "archivo": "", "sha256": "", "estado": "fallido"}

    for intento in range(1, MAX_INTENTOS + 1):
        fila["fecha_hora"] = ahora()
        try:
            resp = sesion.get(url, timeout=TIMEOUT_SEG)
        except requests.RequestException as error:
            registrar(f"GET {url} | intento {intento}/{MAX_INTENTOS} | sin respuesta: {error}")
            time.sleep(PAUSA_SEG)
            continue

        fila["http"], fila["bytes"] = resp.status_code, len(resp.content)
        registrar(f"GET {url} | intento {intento}/{MAX_INTENTOS} | "
                  f"HTTP {resp.status_code} | {len(resp.content)} bytes")
        if resp.status_code != 200:
            time.sleep(PAUSA_SEG)
            continue

        es_valida, resumen, avisos = validar_respuesta(resp.content, codigo, desde, hasta)
        for aviso in avisos:
            registrar(f"{codigo} | {'ADVERTENCIA' if es_valida else 'RECHAZADA'}: {aviso}")
        if not es_valida:
            # Un error de contenido no se arregla reintentando: se detiene aquí.
            registrar(f"{codigo} | NO se guardó el archivo; el crudo existente (si hay) queda intacto")
            return fila

        # Escritura segura: primero a un temporal y luego se reemplaza, para no
        # dejar nunca un crudo a medio escribir.
        temporal = ruta.with_name(ruta.name + ".tmp")
        temporal.write_bytes(resp.content)
        temporal.replace(ruta)

        fila.update({
            "observaciones": resumen["observaciones"],
            "primer_periodo": resumen["primer_periodo"],
            "ultimo_periodo": resumen["ultimo_periodo"],
            "archivo": ruta.relative_to(RAIZ).as_posix(),
            "sha256": sha256(ruta),
            "estado": "ok" if not avisos else "ok_con_advertencias",
        })
        registrar(f"{codigo} | «{resumen['nombre']}» | {resumen['observaciones']} observaciones "
                  f"({resumen['primer_periodo']} a {resumen['ultimo_periodo']}) | "
                  f"guardado en {fila['archivo']} | SHA-256 {fila['sha256']}")
        return fila

    registrar(f"{codigo} | FALLÓ tras {MAX_INTENTOS} intentos; el crudo existente (si hay) queda intacto")
    return fila


def verificar_encabezado():
    """
    Revisa el encabezado obligatorio (numeral 2.4.2): las 4 primeras líneas
    deben ser comentarios (empezar con «#») con (1) nombres y apellidos,
    (2) código de matrícula, (3) tema y número del temario y (4) fecha de
    extracción exacta (AAAA-MM-DD). Si falta algo, se detiene antes de
    descargar. Si la fecha no es la de hoy, solo avisa en el log.
    El dictamen de la Unidad I penalizó encabezados incompletos y fechas
    aproximadas («septiembre de 2026»).
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
        registrar(f"ADVERTENCIA: el encabezado dice {fecha} y hoy es {hoy}; "
                  "actualiza la línea 4 si esta es la descarga definitiva")

# ---------------------------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# ---------------------------------------------------------------------------
def main():
    if "REEMPLAZAR" in CORREO_CONTACTO or "@" not in CORREO_CONTACTO:
        sys.exit("ERROR: escribe tu correo en CORREO_CONTACTO (parte de parámetros) antes de ejecutar.")

    CARPETA_CRUDOS.mkdir(parents=True, exist_ok=True)
    desde, hasta = rango_descarga()

    registrar("=" * 70)
    registrar("INICIO script 01 — extracción por API (BCRPData)")
    registrar(f"Python {platform.python_version()} | requests {requests.__version__}")
    registrar(f"Panel {FECHA_INICIO} a {FECHA_CORTE} | descarga mensual {desde} a {hasta} "
              f"({len(meses_esperados(desde, hasta))} meses por serie)")
    registrar(f"User-Agent: {USER_AGENT} | pausa {PAUSA_SEG} s")
    verificar_encabezado()

    sesion = requests.Session()
    sesion.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

    filas = []
    for i, codigo in enumerate(SERIES):
        if i > 0:
            time.sleep(PAUSA_SEG)  # pausa entre solicitudes
        registrar(f"Serie {codigo}: {SERIES[codigo]['descripcion']} → {SERIES[codigo]['uso']}")
        filas.append(descargar_serie(sesion, codigo, desde, hasta))

    fallidas = [f["codigo"] for f in filas if f["estado"] == "fallido"]
    if fallidas:
        registrar(f"FIN con errores: no se descargaron {fallidas}")
        registrar("=" * 70)
        sys.exit(1)
    registrar(f"FIN correcto: {len(filas)} series descargadas")
    registrar("=" * 70)


if __name__ == "__main__":
    main()
