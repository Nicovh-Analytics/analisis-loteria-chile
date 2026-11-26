"""Herramientas estadísticas para sorteos de K números distintos entre N.

En un sorteo de lotería los K números de cada extracción son distintos
(sin reemplazo). El chi-cuadrado de Pearson y la simulación multinomial
suponen extracción con reemplazo, y con eso subestiman el χ² y sobreestiman
el p-value: bajo H0, E[χ²] es N−K y no N−1 (Loto 6/41: 35 vs 40; Kino 14/25:
11 vs 24). Este módulo corrige ambas cosas.
"""

import numpy as np
from scipy import stats


def chi2_sorteo(freq, n, K, N):
    """χ² de uniformidad para n sorteos de K números distintos entre N.

    Reescala el χ² de Pearson por (N−1)/(N−K) para que bajo H0 siga una
    χ²(N−1). Devuelve (chi2_ajustado, p_value).
    """
    freq = np.asarray(freq, dtype=float)
    esperada = n * K / N
    chi2 = ((freq - esperada) ** 2 / esperada).sum() * (N - 1) / (N - K)
    return chi2, stats.chi2.sf(chi2, N - 1)


def desv_estandar(n, K, N):
    """Desviación estándar de la frecuencia de un número en n sorteos."""
    p = K / N
    return np.sqrt(n * p * (1 - p))


def simular_frecuencias(n, K, N, rng, pesos=None):
    """Frecuencia de cada número (1..N) en n sorteos simulados de K distintos.

    Sin pesos, cada sorteo es un subconjunto uniforme. Con pesos, la
    extracción es sucesiva y proporcional a los pesos (lo mismo que
    np.random.choice(N, K, replace=False, p=pesos)), vectorizada con claves
    de Gumbel: los K números con mayor log(peso) + Gumbel.
    """
    if pesos is None:
        claves = rng.random((n, N))
    else:
        claves = np.log(pesos) + rng.gumbel(size=(n, N))
    elegidos = np.argpartition(-claves, K - 1, axis=1)[:, :K]
    return np.bincount(elegidos.ravel(), minlength=N)
