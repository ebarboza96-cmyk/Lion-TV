# LAVA · Contemporary Fire & BBQ — test-fit conceptual

Test-fit arquitectónico y operativo (planta 2D) para LAVA en el local ex-Marna’s (Terrazas Lindora), más un recorrido 3D
del resultado. Anteproyecto: **no es un plano constructivo**; validar con arquitecto, ingenierías, bomberos y la
administración.

## Entregables

| Archivo | Contenido |
|---|---|
| [`plan/LAVA_test-fit_planos_A2.pdf`](plan/LAVA_test-fit_planos_A2.pdf) | 3 láminas A2 a escala 1:50. **A-101**: planta propuesta con zonas, equipos con nombre y medida, cotas y notas clave. **A-102**: EXISTING WALL / WALL TO DEMOLISH / NEW PROPOSED WALL y el corrimiento de la división. **A-103**: flujos y anchos libres medidos. |
| `plan/lava_A10x_*.png` | Las mismas láminas en PNG. |
| [`docs/INFORME_TEST_FIT.md`](docs/INFORME_TEST_FIT.md) | Informe: cifras, pasillos, zonificación, muros, flujos, verificaciones en sitio, riesgos y cuadro de equipos. |
| [`app/index.html`](app/index.html) | Recorrido 3D + plano + datos en un solo archivo HTML (abrir en el navegador). |

## Zonificación (fijada por el cliente)

Muro al restaurante → **HOT LINE / SHOW KITCHEN** (parrilla → cocina 4Q → plancha → freidora 1 → freidora 2, una sola
campana) → apoyo (mesa inox + horno, muro norte) → **BBQ PRODUCTION** (smoker + holding, muro del fondo) →
**WASHING** (antiguas PILAS) → **COLD PREP** (antigua PASTELERÍA). **BAR / POS** con pase caliente junto a la división y
**DINING** de 36 asientos.

## Cómo regenerar

```bash
tools/build_all.sh
```

`tools/make_layout.py` es la fuente editable del test-fit (escribe `data/layout.json`). `data/existing.json` guarda las
condiciones existentes leídas del PDF de Marna’s. El resto (validación, láminas, informe y app) se genera desde esos
dos archivos. Formato de datos: [`docs/LAYOUT_SCHEMA.md`](docs/LAYOUT_SCHEMA.md). App: [`app/README.md`](app/README.md).

Requisitos: Python 3 con `shapely`, `scipy`, `numpy`; Node con `playwright` (Chromium) para exportar el PDF. Las
fuentes tipográficas (Google Fonts, licencia OFL) están en `tools/fonts/` para que la exportación funcione sin red.
