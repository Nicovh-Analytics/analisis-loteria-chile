"""
Scraper de resultados históricos del Kino y juegos complementarios
Fuente: chileresultados.com
URL: https://chileresultados.com/kino/sorteos/{numero}

Extrae todos los juegos de cada sorteo:
  - Sorteo KINO (14 de 25) — principal
  - Premios Especiales (8 de 25)
  - Sorteo ReKino (14 de 25)
  - Sorteo REQUETE KINO (14 de 25)
  - CHAO JEFE 2 Millones (14 de 25)
  - CHAO JEFE 3 Millones (14 de 25)
  - Sorteo SUPER COMBO MARRAQUETA (14 de 25)

Genera un CSV por cada juego.

Uso:
    pip install requests beautifulsoup4
    python kino_completo.py

Estructura HTML (verificada con DevTools):
    - Cada juego está en un <div class="mb-4">
    - Título del juego en <h3> dentro de ese div
    - Números en <span class="badge rounded-pill bg-warning text-dark">
    - Tabla dentro de <div class="table-responsive">
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
import os

# ──────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────
SORTEO_FIN = 3264        # último sorteo conocido (actualizar si es necesario)
SORTEO_INICIO = 1
MAX_ERRORES_CONSECUTIVOS = 30
DELAY = 1

CARPETA = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Mapeo de títulos de h3 a nombres internos y cantidad esperada de bolillas
JUEGOS = {
    "sorteo kino": {"nombre": "kino_principal", "bolillas": 14},
    "kino": {"nombre": "kino_principal", "bolillas": 14},
    "premios especiales": {"nombre": "kino_premios_especiales", "bolillas": 8},
    "sorteo rekino": {"nombre": "kino_rekino", "bolillas": 14},
    "rekino": {"nombre": "kino_rekino", "bolillas": 14},
    "sorteo requete kino": {"nombre": "kino_requetekino", "bolillas": 14},
    "requete kino": {"nombre": "kino_requetekino", "bolillas": 14},
    "chao jefe 2 millones": {"nombre": "kino_chao_jefe_2m", "bolillas": 14},
    "chao jefe 2": {"nombre": "kino_chao_jefe_2m", "bolillas": 14},
    "chao jefe 3 millones": {"nombre": "kino_chao_jefe_3m", "bolillas": 14},
    "chao jefe 3": {"nombre": "kino_chao_jefe_3m", "bolillas": 14},
    "sorteo super combo marraqueta": {"nombre": "kino_super_combo", "bolillas": 14},
    "super combo marraqueta": {"nombre": "kino_super_combo", "bolillas": 14},
}


# ──────────────────────────────────────────────
# FUNCIONES
# ──────────────────────────────────────────────

def extraer_numeros(elemento):
    """Extrae números de los spans bg-warning dentro de un contenedor."""
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


def identificar_juego(titulo_h3):
    """Identifica el juego a partir del texto del h3.
    Retorna (nombre_interno, bolillas_esperadas) o (None, None)."""
    titulo = titulo_h3.lower().strip()

    # Buscar coincidencia directa primero
    for clave, config in JUEGOS.items():
        if clave in titulo:
            return config["nombre"], config["bolillas"]

    return None, None


def scrape_sorteo(numero):
    """Scrapea todos los juegos de un sorteo del Kino.
    Retorna dict {nombre_juego: [lista de números]} o None."""
    url = f"https://chileresultados.com/kino/sorteos/{numero}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.find("title")
    if not title or "404" in title.text.lower():
        return None

    resultado = {"sorteo": numero}
    juegos_encontrados = 0

    # Buscar todos los div.mb-4 que contienen los juegos
    for div in soup.find_all("div", class_="mb-4"):
        h3 = div.find("h3")
        if not h3:
            continue

        titulo_texto = h3.get_text(strip=True)
        nombre, bolillas_esperadas = identificar_juego(titulo_texto)

        if nombre is None:
            continue

        # Si ya capturamos este juego en este sorteo, saltar
        if nombre in resultado:
            continue

        numeros = extraer_numeros(div)

        if len(numeros) == bolillas_esperadas:
            # Validar rango 1-25
            vals = [int(x) for x in numeros]
            if all(1 <= v <= 25 for v in vals) and len(set(vals)) == bolillas_esperadas:
                resultado[nombre] = numeros
                juegos_encontrados += 1
            else:
                print(f"  ⚠ Sorteo {numero}, {nombre}: números fuera de rango o repetidos")
        elif len(numeros) > bolillas_esperadas:
            print(f"  ⚠ Sorteo {numero}, {nombre}: {len(numeros)} números "
                  f"(esperaba {bolillas_esperadas}), tomando primeros {bolillas_esperadas}")
            resultado[nombre] = numeros[:bolillas_esperadas]
            juegos_encontrados += 1

    if juegos_encontrados == 0:
        return None

    return resultado


def guardar_csv(nombre, datos, num_bolillas):
    """Guarda un CSV para un juego específico."""
    archivo = os.path.join(CARPETA, f"{nombre}.csv")
    registros = [(d["sorteo"], d[nombre]) for d in datos if nombre in d]

    if not registros:
        print(f"  {nombre}: sin datos, no se genera CSV")
        return

    with open(archivo, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["sorteo"] + [f"n{i}" for i in range(1, num_bolillas + 1)]
        writer.writerow(header)
        for sorteo, nums in registros:
            writer.writerow([sorteo] + nums)

    print(f"  {nombre}.csv: {len(registros)} sorteos guardados")


# ──────────────────────────────────────────────
# EJECUCIÓN PRINCIPAL
# ──────────────────────────────────────────────

def main():
    resultados = []
    errores_consecutivos = 0
    total_errores = 0

    print(f"Scraping Kino completo desde sorteo {SORTEO_FIN} hacia atrás...")
    print(f"Se detiene tras {MAX_ERRORES_CONSECUTIVOS} errores consecutivos.\n")

    for n in range(SORTEO_FIN, SORTEO_INICIO - 1, -1):
        try:
            dato = scrape_sorteo(n)
            if dato:
                resultados.append(dato)
                errores_consecutivos = 0
                juegos = [k for k in dato if k != "sorteo"]
                print(f"Sorteo {n}: {len(juegos)} juegos — {', '.join(juegos)}")
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

    # Ordenar por número de sorteo
    resultados.sort(key=lambda x: x["sorteo"])

    print(f"\n{'='*60}")
    print(f"Total sorteos descargados: {len(resultados)}")
    print(f"Total errores: {total_errores}")

    if not resultados:
        print("No se obtuvieron datos. Revisá los selectores con DevTools.")
        return

    # Guardar CSVs — uno por juego
    print(f"\nGenerando CSVs...")

    # Juegos de 14 bolillas
    for nombre in ["kino_principal", "kino_rekino", "kino_requetekino",
                    "kino_chao_jefe_2m", "kino_chao_jefe_3m", "kino_super_combo"]:
        guardar_csv(nombre, resultados, 14)

    # Premios Especiales (8 bolillas)
    guardar_csv("kino_premios_especiales", resultados, 8)

    # Resumen
    print(f"\n{'='*60}")
    print("Resumen de juegos encontrados:")
    todos_juegos = set()
    for r in resultados:
        todos_juegos.update(k for k in r if k != "sorteo")
    for j in sorted(todos_juegos):
        count = sum(1 for r in resultados if j in r)
        print(f"  {j}: {count} sorteos")

    print(f"\nCSVs generados en: {CARPETA}")


if __name__ == "__main__":
    main()
