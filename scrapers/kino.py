"""
Scraper de resultados históricos del Kino - Lotería de Chile
Fuente: chileresultados.com
URL: https://chileresultados.com/kino/sorteos/{numero}

Estructura del Kino: se extraen 14 bolillas de 25 (números 1 al 25).
Genera: kino_principal.csv (14 números por sorteo)

Uso:
    pip install requests beautifulsoup4
    python scraper_kino.py

Los selectores HTML son los mismos que el Loto en este sitio:
    - Números: <span class="badge rounded-pill bg-danger">
    - Formato nuevo: dentro de <div class="shadow p-3 mb-3">
    - Formato antiguo: <h3> suelto seguido de <table>
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
import os

# ──────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────
SORTEO_FIN = 3264        # último sorteo conocido (9 de agosto 2026)
SORTEO_INICIO = 1        # el script para solo si no encuentra datos
MAX_ERRORES_CONSECUTIVOS = 30
DELAY = 1                # segundos entre requests
NUM_BOLILLAS = 14        # el Kino extrae 14 números

CARPETA = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def extraer_numeros_seccion(elemento):
    """Extrae los números de un contenedor.
    En el Kino los números están en <span class="badge rounded-pill bg-warning text-dark">.
    (OJO: distinto del Loto, que usa bg-danger)"""
    spans = elemento.find_all(
        "span",
        class_=lambda c: c and "bg-warning" in c and "rounded-pill" in c
    )
    numeros = []
    for span in spans:
        texto = span.get_text(strip=True)
        if texto.isdigit():
            numeros.append(texto)
    return numeros


def encontrar_seccion_principal(soup):
    """Encuentra SOLO la sección 'Sorteo KINO' (el juego principal).

    IMPORTANTE: la página tiene varias secciones con bolillas amarillas
    (Sorteo KINO, Premios Especiales, ReKino, RequeteKino, Chao Jefe...).
    Todas usan bg-warning, así que hay que anclar al h3 correcto y tomar
    solo el bloque que le sigue, no toda la página.

    El h3 principal dice exactamente 'Sorteo KINO' (o 'Kino N Resultados'
    en el encabezado, que ignoramos)."""
    candidatos = []
    for h3 in soup.find_all("h3"):
        titulo = h3.get_text(strip=True).lower()
        # Buscamos el h3 que titula la sección principal.
        # "sorteo kino" es el marcador exacto en el formato observado.
        if "sorteo kino" in titulo or titulo.strip() == "kino":
            candidatos.append(h3)

    # Fallback: si no encontró "sorteo kino", buscar el primer h3 que
    # sea seguido de una tabla con bolillas
    if not candidatos:
        for h3 in soup.find_all("h3"):
            sig = h3.find_next()
            if sig and sig.find("span", class_=lambda c: c and "bg-warning" in c):
                candidatos.append(h3)
                break

    for h3 in candidatos:
        # Buscar el contenedor de la tabla que sigue al h3
        # (puede ser div.table-responsive o la table directamente)
        sig = h3.find_next(["div", "table"])
        # Avanzar hasta encontrar algo con bolillas
        cursor = sig
        saltos = 0
        while cursor is not None and saltos < 5:
            if cursor.find("span", class_=lambda c: c and "bg-warning" in c and "rounded-pill" in c):
                return cursor
            cursor = cursor.find_next(["div", "table"])
            saltos += 1
    return None


def scrape_sorteo(numero):
    """Scrapea un sorteo del Kino. Retorna dict o None."""
    url = f"https://chileresultados.com/kino/sorteos/{numero}"
    resp = requests.get(url, headers=HEADERS, timeout=15)

    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.find("title")
    if not title or "404" in title.text.lower():
        return None

    seccion = encontrar_seccion_principal(soup)
    if not seccion:
        return None

    numeros = extraer_numeros_seccion(seccion)

    # El Kino tiene EXACTAMENTE 14 números.
    # Si hay más, probablemente agarró varias secciones juntas → descartar
    # con aviso para revisar. Si hay menos, la página está incompleta.
    if len(numeros) == NUM_BOLILLAS:
        # validación extra: todos entre 1 y 25
        vals = [int(x) for x in numeros]
        if all(1 <= v <= 25 for v in vals) and len(set(vals)) == 14:
            return {"sorteo": numero, "numeros": numeros}
        else:
            print(f"  ⚠ Sorteo {numero}: números fuera de rango o repetidos: {numeros}")
            return None
    elif len(numeros) > NUM_BOLILLAS:
        print(f"  ⚠ Sorteo {numero}: {len(numeros)} números (esperaba 14). "
              f"Puede haber agarrado otra sección. Tomo los primeros 14.")
        return {"sorteo": numero, "numeros": numeros[:NUM_BOLILLAS]}

    return None


def main():
    resultados = []
    errores_consecutivos = 0
    total_errores = 0

    print(f"Scraping Kino desde sorteo {SORTEO_FIN} hacia atrás...")
    print(f"Se detiene tras {MAX_ERRORES_CONSECUTIVOS} errores consecutivos.\n")

    for n in range(SORTEO_FIN, SORTEO_INICIO - 1, -1):
        try:
            dato = scrape_sorteo(n)
            if dato:
                resultados.append(dato)
                errores_consecutivos = 0
                nums_str = " ".join(dato["numeros"])
                print(f"Sorteo {n}: {nums_str}")
            else:
                total_errores += 1
                errores_consecutivos += 1
                print(f"Sorteo {n}: sin datos")
        except Exception as e:
            total_errores += 1
            errores_consecutivos += 1
            print(f"Sorteo {n}: error — {e}")

        if errores_consecutivos >= MAX_ERRORES_CONSECUTIVOS:
            print(f"\n{MAX_ERRORES_CONSECUTIVOS} errores consecutivos. Deteniendo en {n}.")
            break

        time.sleep(DELAY)

    resultados.sort(key=lambda x: x["sorteo"])

    print(f"\n{'='*50}")
    print(f"Total sorteos descargados: {len(resultados)}")
    print(f"Total errores: {total_errores}")

    if not resultados:
        print("No se obtuvieron datos. Revisá los selectores con DevTools.")
        return

    # Guardar CSV — 14 columnas de números
    archivo = os.path.join(CARPETA, "kino_principal.csv")
    with open(archivo, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["sorteo"] + [f"n{i}" for i in range(1, NUM_BOLILLAS + 1)]
        writer.writerow(header)
        for r in resultados:
            writer.writerow([r["sorteo"]] + r["numeros"])

    print(f"Guardado: {archivo}")


if __name__ == "__main__":
    main()