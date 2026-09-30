"""
Scraper de resultados históricos del Loto Chile
Fuente: chileresultados.com
URL: https://chileresultados.com/loto/sorteos/{numero}

Extrae: Loto (6 números + comodín), Recargado, Revancha, Desquite
Genera: un CSV por cada tipo de sorteo

Uso:
    pip install requests beautifulsoup4
    python scraper_loto_chileresultados.py

Selectores HTML (verificados con DevTools):
    - Números principales: <span class="badge rounded-pill bg-danger">
    - Comodín:             <span class="badge rounded-pill bg-warning text-danger">
    - Secciones (nuevo):   <div class="shadow p-3 mb-3"> con <h3> adentro
    - Secciones (antiguo): <h3> suelto seguido de <table class="table ...">
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import re

# ──────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────
SORTEO_FIN = 4332        # último sorteo conocido (actualizar si es necesario)
SORTEO_INICIO = 1        # desde dónde intentar (el script para solo si no hay datos)
MAX_ERRORES_CONSECUTIVOS = 30   # detener si no encuentra datos en N sorteos seguidos
DELAY = 1                # segundos entre requests

# Carpeta de salida = misma carpeta del script
CARPETA = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ──────────────────────────────────────────────
# FUNCIONES DE PARSING
# ──────────────────────────────────────────────

def extraer_numeros_seccion(seccion_div):
    """Extrae los números de una sección (div.shadow).
    Los números están en <span class="badge rounded-pill bg-danger">.
    Retorna lista de strings con los números."""
    spans = seccion_div.find_all("span", class_=lambda c: c and "bg-danger" in c and "rounded-pill" in c)
    numeros = []
    for span in spans:
        texto = span.get_text(strip=True)
        if texto.isdigit():
            numeros.append(texto)
    return numeros


def extraer_comodin(seccion_element):
    """Extrae el comodín de la sección Loto principal.
    Está en <span class="badge rounded-pill bg-warning text-danger">.
    En formato antiguo puede estar en un <td> dentro de la misma table,
    o en un elemento hermano si la table no lo contiene."""
    # Buscar primero dentro del elemento
    span = seccion_element.find("span", class_=lambda c: c and "bg-warning" in c and "rounded-pill" in c)
    
    # Si no lo encontró, buscar en el siguiente hermano (formato antiguo:
    # a veces el comodín está en una fila extra o fuera de la table)
    if not span:
        siguiente = seccion_element.find_next_sibling()
        if siguiente:
            span = siguiente.find("span", class_=lambda c: c and "bg-warning" in c and "rounded-pill" in c)
    
    if span:
        texto = span.get_text(strip=True)
        if texto.isdigit():
            return texto
    return None


def encontrar_secciones(soup):
    """Encuentra todas las secciones de sorteo.
    
    Formato nuevo (sorteos ~4333+): div.shadow.p-3.mb-3 con h3 adentro.
    Formato antiguo (sorteos anteriores): h3 sueltos seguidos de table.
    
    En ambos casos busca los h3 y asocia el contenedor que tiene los números.
    Retorna un dict: {'números ganadores': elemento, 'recargado': elemento, ...}
    """
    secciones = {}
    
    # Estrategia: buscar todos los h3 de la página
    for h3 in soup.find_all("h3"):
        titulo = h3.get_text(strip=True).lower()
        
        # Ignorar h3 que no son de sorteos
        if not any(palabra in titulo for palabra in [
            "ganadores", "recargado", "revancha", "desquite",
            "jubilazo", "multiplicar", "ahora si"
        ]):
            continue
        
        # Caso 1: el h3 está dentro de un div.shadow (formato nuevo)
        parent_shadow = h3.find_parent("div", class_=lambda c: c and "shadow" in c)
        if parent_shadow:
            secciones[titulo] = parent_shadow
            continue
        
        # Caso 2: el h3 está suelto, los números están en la <table> siguiente (formato antiguo)
        siguiente = h3.find_next_sibling()
        # Avanzar por <hr> u otros tags vacíos hasta encontrar la table
        while siguiente and siguiente.name in ("hr", "br"):
            siguiente = siguiente.find_next_sibling()
        
        if siguiente and siguiente.name == "table":
            secciones[titulo] = siguiente
        elif siguiente:
            # Fallback: usar lo que sea que siga
            secciones[titulo] = siguiente
    
    return secciones


def scrape_sorteo(numero):
    """Scrapea un sorteo completo. Retorna dict con todos los datos o None."""
    url = f"https://chileresultados.com/loto/sorteos/{numero}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    
    if resp.status_code != 200:
        return None
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Verificar que la página tiene contenido real
    title = soup.find("title")
    if not title or "404" in title.text.lower() or "error" in title.text.lower():
        return None
    
    secciones = encontrar_secciones(soup)
    
    if not secciones:
        return None
    
    resultado = {"sorteo": numero}
    
    # --- LOTO (Números Ganadores) ---
    for clave in secciones:
        if "ganadores" in clave or "números" in clave:
            sec = secciones[clave]
            nums = extraer_numeros_seccion(sec)
            comodin = extraer_comodin(sec)
            if len(nums) >= 6:
                resultado["loto"] = nums[:6]
                resultado["comodin"] = comodin
            break
    
    # --- RECARGADO ---
    for clave in secciones:
        if "recargado" in clave:
            nums = extraer_numeros_seccion(secciones[clave])
            if len(nums) >= 6:
                resultado["recargado"] = nums[:6]
            break
    
    # --- REVANCHA ---
    for clave in secciones:
        if "revancha" in clave:
            nums = extraer_numeros_seccion(secciones[clave])
            if len(nums) >= 6:
                resultado["revancha"] = nums[:6]
            break
    
    # --- DESQUITE ---
    for clave in secciones:
        if "desquite" in clave:
            nums = extraer_numeros_seccion(secciones[clave])
            if len(nums) >= 6:
                resultado["desquite"] = nums[:6]
            break
    
    # Si no encontró ni siquiera los números principales, descartar
    if "loto" not in resultado:
        return None
    
    return resultado


# ──────────────────────────────────────────────
# EJECUCIÓN PRINCIPAL
# ──────────────────────────────────────────────

def main():
    resultados = []
    errores_consecutivos = 0
    total_errores = 0
    
    print(f"Iniciando scraping desde sorteo {SORTEO_FIN} hacia atrás...")
    print(f"Se detendrá tras {MAX_ERRORES_CONSECUTIVOS} errores consecutivos.\n")
    
    for n in range(SORTEO_FIN, SORTEO_INICIO - 1, -1):
        try:
            dato = scrape_sorteo(n)
            if dato:
                resultados.append(dato)
                errores_consecutivos = 0
                
                loto_str = " ".join(dato.get("loto", []))
                com_str = dato.get("comodin", "?")
                print(f"Sorteo {n}: [{loto_str}] Comodín: {com_str}")
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
    
    # Ordenar por número de sorteo
    resultados.sort(key=lambda x: x["sorteo"])
    
    print(f"\n{'='*50}")
    print(f"Total sorteos descargados: {len(resultados)}")
    print(f"Total errores: {total_errores}")
    
    if not resultados:
        print("No se obtuvieron datos. Revisá los selectores HTML.")
        return
    
    # ──────────────────────────────────────────
    # GUARDAR CSVs
    # ──────────────────────────────────────────
    
    # 1. LOTO PRINCIPAL
    archivo_loto = os.path.join(CARPETA, "loto_principal.csv")
    with open(archivo_loto, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sorteo", "n1", "n2", "n3", "n4", "n5", "n6", "comodin"])
        for r in resultados:
            if "loto" in r:
                fila = [r["sorteo"]] + r["loto"] + [r.get("comodin", "")]
                writer.writerow(fila)
    print(f"Guardado: {archivo_loto}")
    
    # 2. RECARGADO
    archivo_rec = os.path.join(CARPETA, "loto_recargado.csv")
    con_recargado = [r for r in resultados if "recargado" in r]
    with open(archivo_rec, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sorteo", "n1", "n2", "n3", "n4", "n5", "n6"])
        for r in con_recargado:
            writer.writerow([r["sorteo"]] + r["recargado"])
    print(f"Guardado: {archivo_rec} ({len(con_recargado)} sorteos)")
    
    # 3. REVANCHA
    archivo_rev = os.path.join(CARPETA, "loto_revancha.csv")
    con_revancha = [r for r in resultados if "revancha" in r]
    with open(archivo_rev, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sorteo", "n1", "n2", "n3", "n4", "n5", "n6"])
        for r in con_revancha:
            writer.writerow([r["sorteo"]] + r["revancha"])
    print(f"Guardado: {archivo_rev} ({len(con_revancha)} sorteos)")
    
    # 4. DESQUITE
    archivo_des = os.path.join(CARPETA, "loto_desquite.csv")
    con_desquite = [r for r in resultados if "desquite" in r]
    with open(archivo_des, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sorteo", "n1", "n2", "n3", "n4", "n5", "n6"])
        for r in con_desquite:
            writer.writerow([r["sorteo"]] + r["desquite"])
    print(f"Guardado: {archivo_des} ({len(con_desquite)} sorteos)")
    
    print(f"\n¡Listo! 4 archivos CSV generados en: {CARPETA}")


if __name__ == "__main__":
    main()