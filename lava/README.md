# LAVA · Contemporary Fire & BBQ — test-fit conceptual

Test-fit arquitectónico y operativo (planta 2D) para LAVA en el local ex-Marna’s (Terrazas Lindora), más un recorrido 3D
del resultado. Anteproyecto: **no es un plano constructivo**; validar con arquitecto, ingenierías, bomberos y la
administración.

## Entregables

| Archivo | Contenido |
|---|---|
| [`plan/LAVA_test-fit_planos_A2.pdf`](plan/LAVA_test-fit_planos_A2.pdf) | Juego de 11 láminas A2 (1:50) de anteproyecto, con recuadro para el profesional responsable (CFIA): **A-101** planta propuesta · **A-102** existente / demolición / nuevo · **A-103** flujos · **A-104** seguridad humana y protección contra incendios (Bomberos) · **A-105** accesibilidad (Ley 7600) · **A-106** acabados y puertas · **A-201** cielos e iluminación · **A-301** cortes y elevaciones · **M-101** hidrosanitario · **M-102** gas, extracción, aire de reposición y supresión · **E-101** eléctrico y cuadro de cargas. |
| `plan/lava_*.png` | Las mismas láminas en PNG. |
| `plan/LAVA_base_v3.dxf`, `plan/LAVA_base_v3_existente.dxf` | Bases editables para AutoCAD (metros, capas por disciplina): propuesta y condición existente. |
| [`docs/permisos/LAVA_documentos_permiso.pdf`](docs/permisos/LAVA_documentos_permiso.pdf) | Documentos para el trámite (63 págs.): índice, memoria descriptiva, especificaciones técnicas, seguridad humana y egreso, cálculos preliminares de instalaciones, checklist normativo, trámites paso a paso, formulario de levantamiento en sitio y carta modelo para la administración del condominio. También en Markdown en `docs/permisos/`. |
| [`docs/INFORME_TEST_FIT.md`](docs/INFORME_TEST_FIT.md) | Informe del anteproyecto: cifras, pasillos, zonificación, muros, flujos, ajustes normativos, verificaciones en sitio, riesgos y cuadro de equipos. |
| [`app/index.html`](app/index.html) | Recorrido 3D + plano + datos en un solo archivo HTML (abrir en el navegador). |

**Qué falta para construir:** levantamiento en sitio, ajuste y firma de un arquitecto responsable (CFIA) y de los ingenieros mecánico
(extracción, gas, supresión) y electricista; autorizaciones del condominio; trámites de uso de suelo, APC, licencia de construcción,
patente, licencia de licores clase C y permiso sanitario (ver `docs/permisos/06_tramites.md`). Las citas normativas provienen de
fuentes secundarias y deben verificarse en los textos oficiales.

## Zonificación (fijada por el cliente)

Muro al restaurante → **HOT LINE / SHOW KITCHEN** (parrilla con campana propia de combustible sólido → cocina 4Q → plancha →
freidora 1 → freidora 2 bajo la campana con supresión) → apoyo (mesa inox + horno, muro norte) → **BBQ PRODUCTION** (smoker + holding, muro del fondo) →
**WASHING** (antiguas PILAS) → **COLD PREP** (antigua PASTELERÍA). **BAR / POS** con pase caliente junto a la división y
**DINING** de 36 asientos. Capacidad máxima declarada: 49 personas.

## Cómo regenerar

```bash
tools/build_all.sh
```

`tools/make_layout.py` es la fuente editable del test-fit (escribe `data/layout.json`). `data/existing.json` guarda las
condiciones existentes leídas del PDF de Marna’s. El resto (validación, láminas, informe y app) se genera desde esos
dos archivos. Formato de datos: [`docs/LAYOUT_SCHEMA.md`](docs/LAYOUT_SCHEMA.md). App: [`app/README.md`](app/README.md).

Requisitos: Python 3 con `shapely`, `scipy`, `numpy`; Node con `playwright` (Chromium) para exportar el PDF. Las
fuentes tipográficas (Google Fonts, licencia OFL) están en `tools/fonts/` para que la exportación funcione sin red.
