# ¿Se puede predecir la lotería? Un análisis estadístico honesto

Análisis estadístico de aleatoriedad en loterías chilenas — Loto (4 bombos independientes) y Kino (1 bombo), usando datos históricos obtenidos por web scraping.

## Objetivo

Investigar si existe estructura explotable en los resultados históricos de la lotería chilena que permita predecir sorteos mejor que el azar.

**Conclusión:** No. Toda la estructura observada es consistente con aleatoriedad pura y coincide con la predicción teórica de la combinatoria. El análisis documenta el método, cuantifica los límites de lo que puede afirmarse, y discute explícitamente los riesgos metodológicos.

## Datos

| Sistema | Estructura | Sorteos | Bombo |
|---|---|---|---|
| Loto principal | 6 de 41 | ~1.222 | físicamente independiente |
| Loto Recargado | 6 de 41 | ~1.128 | físicamente independiente |
| Loto Revancha | 6 de 41 | ~1.222 | físicamente independiente |
| Loto Desquite | 6 de 41 | ~1.222 | físicamente independiente |
| Kino | 14 de 25 | ~889 | estructura distinta |

Fuente: [chileresultados.com](https://www.chileresultados.com), extraídos por web scraping (agosto 2026).

## Metodología

El notebook aplica ~40 tests estadísticos independientes sobre los 5 sistemas:

- **Uniformidad** — Chi-cuadrado de bondad de ajuste por bombo
- **Valores extremos** — Simulación Monte Carlo del "número caliente" esperado
- **Paridad, suma y memoria** — Comparación contra valores teóricos
- **Estadísticos de orden** — Distribución posicional vs predicción combinatoria exacta
- **Apilamiento condicional** — Techo teórico de la probabilidad encadenada
- **Replicación** — 4 bombos independientes con corrección de Bonferroni
- **Robustez** — Kino (14 de 25) como test de generalización
- **Poder estadístico** — Cuantificación del sesgo mínimo detectable
- **P-hacking** — Evaluación explícita de riesgo de falso positivo

## Resultados

| Análisis | Resultado |
|---|---|
| Uniformidad (χ², 5 sistemas) | Todos uniformes, p > 0.5 |
| Valores extremos (número caliente) | Fluctuación normal (~2σ), no sesgo |
| Paridad / suma / memoria | Coinciden con la teoría |
| Estadísticos de orden | r > 0.97 vs combinatoria pura |
| Apilamiento condicional | Mejora 1.00x (identidad matemática) |
| 4 bombos independientes | Replicación con Bonferroni |
| Kino (estructura opuesta) | Misma conclusión |
| Límite de detección física | Sin sesgos groseros; los finos son irrelevantes |

## Estructura del proyecto

```
analisis-loteria-chile/
├── data/                             # Datasets (CSV)
│   ├── loto_principal.csv
│   ├── loto_recargado.csv
│   ├── loto_revancha.csv
│   ├── loto_desquite.csv
│   ├── kino_principal.csv
│   ├── kino_chao_jefe_2m.csv
│   ├── kino_chao_jefe_3m.csv
│   └── kino_super_combo.csv
├── scrapers/                         # Scripts de extracción
│   ├── loto.py                       # Loto (formato HTML nuevo)
│   ├── loto1.py                      # Loto (formato HTML antiguo)
│   ├── kino.py                       # Kino principal
│   └── kino_completo.py              # Kino + juegos complementarios
├── analisis_loteria_completo.ipynb   # Análisis principal (Loto + Kino)
├── analisis_kino_complementarios.ipynb # Replicación en bombos del Kino
├── README.md
└── LICENSE
```

## Cómo ejecutar

1. Clonar el repositorio:
```bash
git clone https://github.com/nicovh-analytics/analisis-loteria-chile.git
cd analisis-loteria-chile
```

2. Instalar dependencias:
```bash
pip install pandas numpy scipy
```

3. Abrir el notebook:
```bash
jupyter notebook analisis_loteria_completo.ipynb
```

Los CSVs ya están incluidos en el repositorio. Para actualizar los datos, ejecutar los scrapers.

## Stack técnico

- **Python 3** — pandas, numpy, scipy
- **Jupyter Notebook** — análisis reproducible
- **BeautifulSoup / requests** — web scraping

## Limitaciones declaradas

- **Cobertura parcial de datos:** chileresultados.com no cubre la totalidad de los sorteos históricos. El Loto tiene ~5.400 sorteos totales pero la fuente solo entrega ~1.222. Los sorteos más antiguos no están disponibles en el sitio y requerirían fuentes alternativas (archivo de Polla, prensa histórica, Diario Oficial).
- **Poder estadístico limitado:** con ~1.200 sorteos, solo se detectan sesgos groseros (>50%). Un sesgo del 2% sería indetectable, pero también irrelevante en las odds.
- **Datos vs proceso:** los datos son resultados públicos, no las condiciones físicas del sorteo. El análisis mide la salida, no el proceso.
- No se descarta la existencia de un sesgo minúsculo — se demuestra que, de existir, sería inexplotable.

## Próximos pasos

- [ ] Agregar juegos complementarios del Kino (replicación Bonferroni en segundo formato)
- [ ] Ampliar cobertura de datos: solicitar dataset completo a Polla Chilena de Beneficencia vía transparencia
- [ ] Explorar fuentes alternativas para sorteos antiguos (archivo de prensa, Diario Oficial)
- [ ] Visualizaciones interactivas

## Licencia

MIT — ver [LICENSE](LICENSE).
