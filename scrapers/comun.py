"""Utilidades compartidas por los scrapers: reintentos con backoff y escritura atómica."""

import os
import random
import time
from contextlib import contextmanager

import requests

REINTENTOS = 5
BASE = 2.0   # segundos; la espera crece como BASE * 2**intento
TOPE = 60.0  # espera máxima entre reintentos
REINTENTABLES = {429, 500, 502, 503, 504}


def _espera(intento, retry_after=None):
    """Backoff exponencial con jitter (mitad fija + mitad aleatoria).
    Respeta Retry-After si el servidor lo envía en segundos."""
    exp = min(TOPE, BASE * 2 ** intento)
    espera = random.uniform(exp / 2, exp)
    if retry_after and retry_after.isdigit():
        espera = max(espera, min(TOPE, float(retry_after)))
    return espera


def pedir(url, headers, timeout=15):
    """GET con reintentos. Entrega la respuesta tal cual (200, 404, ...) para que
    el scraper decida; reintenta solo errores transitorios (429/5xx, timeout,
    conexión). Si se agotan los reintentos lanza excepción, para no confundir
    'el sitio me limitó' con 'ese sorteo no existe'."""
    ultimo = None
    for intento in range(REINTENTOS):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code not in REINTENTABLES:
                return resp
            ultimo = f"HTTP {resp.status_code}"
            espera = _espera(intento, resp.headers.get("Retry-After"))
        except (requests.Timeout, requests.ConnectionError) as e:
            ultimo = type(e).__name__
            espera = _espera(intento)
        if intento < REINTENTOS - 1:
            time.sleep(espera)
    raise requests.RequestException(
        f"{url}: sin respuesta válida tras {REINTENTOS} intentos ({ultimo})")


@contextmanager
def abrir_atomico(ruta):
    """Abre un CSV para escribir en un .tmp y lo renombra al terminar sin error.
    Si algo falla a mitad de la escritura, el archivo anterior queda intacto."""
    tmp = ruta + ".tmp"
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            yield f
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
