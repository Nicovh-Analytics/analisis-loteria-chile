"""
Scraper de resultados históricos del Loto Chile — versión incremental
Fuente: chileresultados.com
URL: https://chileresultados.com/loto/sorteos/{numero}

Extrae: Loto (6 números + comodín), Recargado, Revancha, Desquite
Genera / actualiza: un CSV por cada tipo de sorteo

Modo incremental:
    Al arrancar lee loto_principal.csv, detecta el último sorteo guardado
    y baja solo desde ese punto hacia adelante. Si el CSV no existe, baja
    todo el histórico. Los sorteos nuevos se combinan con los ya guardados
    y el archivo se reescribe entero, siempre con coma (,) como separador.

Formato de los CSV:
    - Lectura: tolera coma (,) o punto y coma (;) y columnas fantasma de
      Excel (p.ej. "Columna1" o celdas vacías al final).
    - Escritura: SIEMPRE coma estándar y solo las columnas útiles. Esto
      deja los archivos limpios y legibles con pd.read_csv() sin argumentos.
      (Si los abres en Excel chileno se verán en una sola columna: usa
      Datos → Desde texto, o léelos desde el notebook.)

Uso:
    python loto.py            # incremental (default): solo lo que falta
    python loto.py --full     # fuerza rebajar todo desde cero

Selectores HTML (verificados con DevTools):
    - Números principales: <span class="badge rounded-pill bg-danger">
    - Comodín:             <span class="badge rounded-pill bg-warning text-danger">
    - Secciones:           <div class="shadow p-3 mb-3"> con <h3> como título
"""

import requests
from bs4 import BeautifulSoup
from comun import pedir, abrir_atomico
import csv
import time
import os
import sys

# ──────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────
SORTEO_FIN = 5493        # último sorteo a intentar (el techo; actualizar si crece)
SORTEO_INICIO = 1        # piso absoluto para la primera corrida (histórico completo)
MAX_ERRORES_CONSECUTIVOS = 30
DELAY = 1

# El script vive en scrapers/, pero los CSV viven en data/ (un nivel arriba).
AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(AQUI, "..", "data")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ──────────────────────────────────────────────
# LECTURA DE CSV EXISTENTES (tolerante a ; y basura de Excel)
# ──────────────────────────────────────────────

def leer_csv_existente(nombre, n_cols):
    """Lee un CSV ya guardado y devuelve {sorteo: [valores]} con los datos
    que ya tenemos. Tolera separador coma o punto y coma, y descarta las
    columnas fantasma de Excel (Columna1, celdas vacías al final).

    n_cols = cuántas columnas de datos esperamos DESPUÉS de 'sorteo'
             (8-1=7 para el principal con comodín; 6 para las variantes).
    Devuelve {} si el archivo no existe o no se pudo leer."""
    archivo = os.path.join(CARPETA, nombre)
    if not os.path.exists(archivo):
        return {}

    datos = {}
    try:
        with open(archivo, "r", encoding="utf-8", newline="") as f:
            # Detectar separador: si la primera línea tiene ';', usamos ';'
            primera = f.readline()
            sep = ";" if primera.count(";") > primera.count(",") else ","
            f.seek(0)  # volver al inicio para leer todo

            reader = csv.reader(f, delimiter=sep)
            next(reader, None)  # saltar header
            for fila in reader:
                if not fila:
                    continue
                # Tomar solo sorteo + las n_cols siguientes; ignorar lo demás
                celdas = [c.strip() for c in fila]
                try:
                    sorteo = int(celdas[0])
                except (IndexError, ValueError):
                    continue
                valores = celdas[1:1 + n_cols]
                # Rellenar si faltan columnas (por si alguna fila viene corta)
                while len(valores) < n_cols:
                    valores.append("")
                datos[sorteo] = valores
    except Exception as e:
        print(f"⚠ No se pudo leer {nombre} ({e}). Se tratará como vacío.")
        return {}

    return datos


def ultimo_sorteo_guardado():
    """Devuelve el número de sorteo más alto ya guardado en loto_principal.csv,
    o None si no hay datos. Se usa el principal como referencia porque siempre
    está presente (las variantes pueden faltar en algunos sorteos)."""
    datos = leer_csv_existente("loto_principal.csv", 7)  # 6 números + comodín
    if not datos:
        return None
    return max(datos.keys())


# ──────────────────────────────────────────────
# FUNCIONES DE PARSING  (sin cambios)
# ──────────────────────────────────────────────

def extraer_numeros_seccion(seccion_div):
    spans = seccion_div.find_all("span", class_=lambda c: c and "bg-danger" in c and "rounded-pill" in c)
    numeros = []
    for span in spans:
        texto = span.get_text(strip=True)
        if texto.isdigit():
            numeros.append(texto)
    return numeros


def extraer_comodin(seccion_div):
    span = seccion_div.find("span", class_=lambda c: c and "bg-warning" in c and "rounded-pill" in c)
    if span:
        texto = span.get_text(strip=True)
        if texto.isdigit():
            return texto
    return None


def encontrar_secciones(soup):
    secciones = {}
    bloques = soup.find_all("div", class_=lambda c: c and "shadow" in c and "p-3" in c)
    for bloque in bloques:
        titulo_tag = bloque.find(["h3", "h2"])
        if titulo_tag:
            titulo = titulo_tag.get_text(strip=True).lower()
            secciones[titulo] = bloque
    return secciones


def scrape_sorteo(numero):
    url = f"https://chileresultados.com/loto/sorteos/{numero}"
    resp = pedir(url, HEADERS)

    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.find("title")
    if not title or "404" in title.text.lower() or "error" in title.text.lower():
        return None

    secciones = encontrar_secciones(soup)
    if not secciones:
        return None

    resultado = {"sorteo": numero}

    for clave in secciones:
        if "ganadores" in clave or "números" in clave:
            sec = secciones[clave]
            nums = extraer_numeros_seccion(sec)
            comodin = extraer_comodin(sec)
            if len(nums) >= 6:
                resultado["loto"] = nums[:6]
                resultado["comodin"] = comodin
            break

    for clave in secciones:
        if "recargado" in clave:
            nums = extraer_numeros_seccion(secciones[clave])
            if len(nums) >= 6:
                resultado["recargado"] = nums[:6]
            break

    for clave in secciones:
        if "revancha" in clave:
            nums = extraer_numeros_seccion(secciones[clave])
            if len(nums) >= 6:
                resultado["revancha"] = nums[:6]
            break

    for clave in secciones:
        if "desquite" in clave:
            nums = extraer_numeros_seccion(secciones[clave])
            if len(nums) >= 6:
                resultado["desquite"] = nums[:6]
            break

    if "loto" not in resultado:
        return None

    return resultado


# ──────────────────────────────────────────────
# GUARDADO (combina existente + nuevo, reescribe en coma limpia)
# ──────────────────────────────────────────────

def guardar(nombre, header, filas_nuevas, combinar_con_existente):
    """Reescribe el CSV entero en coma estándar.

    - filas_nuevas: lista de listas [sorteo, v1, v2, ...] recién scrapeadas.
    - combinar_con_existente: si True, lee lo que ya había en el archivo
      (tolerando ; y basura de Excel) y lo une con lo nuevo. Si un sorteo
      está en ambos, gana el nuevo. Si False (modo --full), ignora lo viejo.

    Siempre escribe con coma y solo las columnas de 'header'. Devuelve
    (total_filas_en_archivo, filas_agregadas)."""
    n_cols = len(header) - 1  # columnas de datos después de 'sorteo'

    # Partir de lo existente (ya limpio) o de cero
    combinado = {}
    if combinar_con_existente:
        combinado = leer_csv_existente(nombre, n_cols)
    antes = len(combinado)

    # Incorporar lo nuevo (sobrescribe si el sorteo ya estaba)
    for fila in filas_nuevas:
        sorteo = fila[0]
        combinado[sorteo] = [str(x) for x in fila[1:]]

    # Reescribir todo ordenado por sorteo, en coma limpia
    archivo = os.path.join(CARPETA, nombre)
    with abrir_atomico(archivo) as f:
        writer = csv.writer(f)  # csv.writer usa coma por defecto
        writer.writerow(header)
        for sorteo in sorted(combinado.keys()):
            writer.writerow([sorteo] + combinado[sorteo])

    agregadas = len(combinado) - antes
    return len(combinado), agregadas


# ──────────────────────────────────────────────
# EJECUCIÓN PRINCIPAL
# ──────────────────────────────────────────────

def main():
    full = "--full" in sys.argv

    # combinar = True → preservamos lo ya guardado y le sumamos lo nuevo.
    # En --full lo ignoramos y reescribimos todo desde cero.
    if full:
        inicio = SORTEO_INICIO
        combinar = False
        print("Modo FULL: se rebaja el histórico completo y se reescriben los CSV.")
    else:
        ultimo = ultimo_sorteo_guardado()
        if ultimo is None:
            inicio = SORTEO_INICIO
            combinar = False
            print("No hay CSV previo. Primera descarga del histórico completo.")
        else:
            inicio = ultimo + 1
            combinar = True   # preservar lo existente y sumar lo nuevo
            print(f"Modo incremental: último sorteo guardado = {ultimo}.")
            if inicio > SORTEO_FIN:
                print(f"Ya estás al día (tope configurado: {SORTEO_FIN}). Nada que bajar.")
                print("Si hay sorteos más nuevos, sube SORTEO_FIN y vuelve a correr.")
                return
            print(f"Se bajarán los sorteos {inicio} a {SORTEO_FIN}.")

    # ── Scraping hacia adelante (de inicio a SORTEO_FIN) ──
    resultados = []
    errores_consecutivos = 0
    total_errores = 0

    for n in range(inicio, SORTEO_FIN + 1):
        try:
            dato = scrape_sorteo(n)
            if dato:
                resultados.append(dato)
                errores_consecutivos = 0
                loto_str = " ".join(dato.get("loto", []))
                print(f"Sorteo {n}: [{loto_str}] Comodín: {dato.get('comodin', '?')}")
            else:
                total_errores += 1
                errores_consecutivos += 1
                print(f"Sorteo {n}: sin datos")
        except Exception as e:
            total_errores += 1
            errores_consecutivos += 1
            print(f"Sorteo {n}: error — {e}")

        if errores_consecutivos >= MAX_ERRORES_CONSECUTIVOS:
            print(f"\n{MAX_ERRORES_CONSECUTIVOS} errores consecutivos. Deteniendo en sorteo {n}.")
            break

        time.sleep(DELAY)

    resultados.sort(key=lambda x: x["sorteo"])

    print(f"\n{'='*50}")
    print(f"Sorteos nuevos descargados: {len(resultados)}")
    print(f"Total errores: {total_errores}")

    if not resultados:
        print("No se obtuvieron datos nuevos.")
        return

    # ── Armar filas y guardar ──
    filas_loto = [[r["sorteo"]] + r["loto"] + [r.get("comodin", "")]
                  for r in resultados if "loto" in r]
    filas_rec = [[r["sorteo"]] + r["recargado"] for r in resultados if "recargado" in r]
    filas_rev = [[r["sorteo"]] + r["revancha"] for r in resultados if "revancha" in r]
    filas_des = [[r["sorteo"]] + r["desquite"] for r in resultados if "desquite" in r]

    h_full = ["sorteo", "n1", "n2", "n3", "n4", "n5", "n6", "comodin"]
    h_base = ["sorteo", "n1", "n2", "n3", "n4", "n5", "n6"]

    t1, a1 = guardar("loto_principal.csv", h_full, filas_loto, combinar)
    t2, a2 = guardar("loto_recargado.csv", h_base, filas_rec, combinar)
    t3, a3 = guardar("loto_revancha.csv",  h_base, filas_rev, combinar)
    t4, a4 = guardar("loto_desquite.csv",  h_base, filas_des, combinar)

    print(f"\nArchivo              Total   Nuevos")
    print(f"  loto_principal    {t1:>6}  {a1:>6}")
    print(f"  loto_recargado    {t2:>6}  {a2:>6}")
    print(f"  loto_revancha     {t3:>6}  {a3:>6}")
    print(f"  loto_desquite     {t4:>6}  {a4:>6}")
    print(f"\n¡Listo! CSVs reescritos en coma limpia en: {os.path.abspath(CARPETA)}")


if __name__ == "__main__":
    main()