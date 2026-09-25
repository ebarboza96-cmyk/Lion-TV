# 00 · Índice del paquete

**LAVA – Contemporary Fire & BBQ** — local ex-Marna's, Terrazas Lindora (centro comercial abierto en régimen de condominio), Lindora, Santa Ana, San José, Costa Rica  
Anteproyecto v3.0 · 2026-09-25 · documento generado desde los datos del proyecto (`tools/permit_docs.py`)

> **ANTEPROYECTO / PRELIMINAR** — no es un documento constructivo ni una declaración de cumplimiento: todo lo aquí indicado es **a validar por el profesional responsable** (CFIA) y por las ingenierías. Las citas normativas provienen mayormente de fuentes secundarias y se marcan "verificar".

Contenido del paquete de anteproyecto para permisos ("anteproyecto listo para revisión y firma"): láminas, documentos, datos de origen, lo que falta y quién lo hace.

## 1. Proyecto

| Concepto | Dato |
|---|---|
| Proyecto | LAVA – Contemporary Fire & BBQ |
| Ubicación | local ex-Marna's, Terrazas Lindora (centro comercial abierto en régimen de condominio), Lindora, Santa Ana, San José, Costa Rica |
| Obra | Remodelación interior (acondicionamiento) de local comercial existente — obra mayor |
| Uso propuesto | Restaurante de parrilla y ahumados, con venta de bebidas alcohólicas (licencia clase C) |
| Área interior del local | 107.65 m² (sobre el PDF de Marna's; VERIFY ON SITE) |
| Capacidad máxima declarada | 49 personas (clientes + personal) |
| Asientos | 36 en 14 mesas (10 de 2 y 4 de 4): 18 sillas + 18 puestos en banca |
| Versión de datos | layout v3.0 · 2026-09-25 |
| Estado | ANTEPROYECTO / PRELIMINAR — a validar por el profesional responsable (CFIA) |

## 2. Láminas

Juego de láminas A2 a 1:50 generado desde los mismos datos (`tools/plan_svg.py` + módulos de `tools/sheets/`). Estado según `plan/sheets.json`:

| Lámina | Título | Disciplina · firma | Archivo | Estado |
|---|---|---|---|---|
| A-101 | Planta arquitectónica propuesta | Arquitectura · Arquitecto responsable | `lava_A101_planta.svg` | generada |
| A-102 | Existente / demolición / nuevo | Arquitectura · Arquitecto responsable | `lava_A102_demolicion.svg` | generada |
| A-103 | Flujos y circulaciones | Arquitectura · Arquitecto responsable | `lava_A103_flujos.svg` | generada |
| A-104 | Seguridad humana y protección contra incendios | Arquitectura · Arquitecto / ing. protección contra incendios | `lava_A104_seguridad.svg` | generada |
| A-105 | Accesibilidad (Ley 7600) | Arquitectura · Arquitecto responsable | `lava_A105_accesibilidad.svg` | generada |
| A-106 | Acabados y puertas | Arquitectura · Arquitecto responsable | `lava_A106_acabados.svg` | generada |
| A-201 | Cielos reflejados e iluminación | Arquitectura · Arquitecto responsable | `lava_A201_cielos.svg` | generada |
| A-301 | Cortes y elevaciones | Arquitectura · Arquitecto responsable | `lava_A301_cortes.svg` | generada |
| M-101 | Hidrosanitario (esquema) | Mecánica · Ingeniero mecánico | `lava_M101_hidrosanitario.svg` | generada |
| M-102 | Gas, extracción, aire de reposición y supresión (esquema) | Mecánica · Ingeniero mecánico | `lava_M102_gas_extraccion.svg` | generada |
| E-101 | Eléctrico (esquema) y cuadro de cargas preliminar | Electricidad · Ingeniero electricista | `lava_E101_electrico.svg` | generada |

- PDF del juego completo: `plan/LAVA_test-fit_planos_A2.pdf` (generado).
- Base editable para AutoCAD: `plan/LAVA_base_v3.dxf` (propuesta) y `plan/LAVA_base_v3_existente.dxf` (existente), `tools/export_dxf.py`.
- Cada lámina lleva en el cajetín la casilla PROFESIONAL RESPONSABLE (CFIA) en blanco para nombre, carné y firma.

## 3. Documentos de este paquete (`docs/permisos/`)

| Archivo | Documento | Contenido | Para |
|---|---|---|---|
| `00_indice.md` | Índice del paquete | Este índice: láminas, documentos, datos, pendientes. | Todos |
| `01_memoria_descriptiva.md` | Memoria descriptiva | Proyecto, ubicación, áreas, programa, zonificación, capacidad, sistemas y cambios respecto de Marna's. | Arquitecto, APC |
| `02_especificaciones_tecnicas.md` | Especificaciones técnicas | Especificaciones por desempeño: demolición, particiones, acabados, puertas, equipos, campanas, supresión, gas, hidrosanitario, electricidad, señalización, accesibilidad. | Arquitecto, ingenierías, contratista |
| `03_seguridad_humana_y_egreso.md` | Seguridad humana y egreso | Carga de ocupantes, clasificación, salidas, recorridos medidos vs límites, señalización, emergencia, extintores, supresión, detección. | Arquitecto, Bomberos |
| `04_calculos_preliminares_instalaciones.md` | Cálculos preliminares de instalaciones | Caudales de campanas, ductos, aire de reposición, gas, agua caliente, trampa de grasa, aparatos y cuadro de cargas eléctricas (PRELIMINAR). | Ing. mecánico, ing. electricista |
| `05_checklist_normativo.md` | Checklist normativo | Requisito / fuente / estado en el anteproyecto / qué debe verificar el profesional. | Profesional responsable |
| `06_tramites.md` | Trámites y permisos | Paso a paso de trámites: condominio, uso de suelo, CFIA/APC, licencia, bitácora, patente, licores, rótulo, PSF, gas, póliza. | Cliente, arquitecto |
| `07_levantamiento_en_sitio.md` | Levantamiento en sitio | Formulario de levantamiento en sitio con cada VERIFY ON SITE / DIMENSION TO VERIFY de los datos. | Arquitecto (visita) |
| `08_carta_administracion.md` | Carta a la administración del condominio | Carta modelo a la administración del condominio con todas las solicitudes. | Cliente |
| `LAVA_documentos_permiso.pdf` | Todos los documentos en un PDF (A4) | Portada + documentos 00–08 | Revisión e impresión |

## 4. Datos de origen

| Archivo | Contenido | Generado por |
|---|---|---|
| `data/existing.json` | Condiciones existentes leídas del PDF de Marna's (muros, columnas, puertas, ductos, puntos húmedos, cielo) | levantamiento del PDF |
| `data/layout.json` | Propuesta v3.0: zonas, equipos, mobiliario, muros y vanos nuevos, seguridad humana, MEP | `tools/make_layout.py` |
| `data/validation.json` | Áreas por zona, anchos libres por ruta, verificaciones automáticas | `tools/validate.py` |
| `data/life_safety_calcs.json` | Carga de ocupantes, recorridos de egreso, extintores (A-104) | `tools/sheets/s104_seguridad.py` |
| `data/mech_calcs.json` | Caudales, ductos, gas, agua caliente, trampa de grasa (M-101/M-102) | `tools/sheets/s401_mecanica.py` |
| `data/elec_loads.json` | Circuitos, demanda, tablero, enclavamientos (E-101) | `tools/sheets/s501_electrica.py` |
| `docs/permisos/_normativa_cache.json` | Investigación normativa y auditoría preliminar (copia recortada) | investigación de cumplimiento |

## 5. Qué falta y quién lo hace

| # | Pendiente | Responsable | Referencia |
|---:|---|---|---|
| 1 | Visita y levantamiento en sitio (formulario 07); ajustar planos a lo medido | Arquitecto responsable | 07, VERIFY ON SITE |
| 2 | Contrato de consultoría CFIA y registro en el APC; firma digital de cada lámina | Arquitecto + ingenieros | 06 paso 4 |
| 3 | Diseño de extracción, aire de reposición y supresión (selección de campanas listadas, ventiladores, ducto, remates) | Ingeniero mecánico + proveedor certificado del sistema de supresión | EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED |
| 4 | Validar ubicación, chimenea y requisitos del smoker (o cambiar a smoker eléctrico / pellet listado) | Ingeniero mecánico + Bomberos | SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED |
| 5 | Diseño de gas desde la red del centro comercial (tipo, presión, capacidad, ruta, válvulas, detector) | Ingeniero mecánico + administración | M-102, 04 |
| 6 | Diseño hidrosanitario: agua fría/caliente, desagües, ventilación, trampa de grasa, sifones de piso | Ingeniero mecánico (CIHSE) | M-101, 04 |
| 7 | Diseño eléctrico: acometida, TE-1, circuitos, emergencia, enclavamientos, puesta a tierra | Ingeniero electricista (NEC 2020) | E-101, 04 |
| 8 | Revisión estructural: penetraciones de losa (EXT-2, EXT-3, AR-1), ventiladores en cubierta, dintel de PS-1, anclaje sísmico | Ingeniero estructural | 02 §17 |
| 9 | Planta de cubierta con ventiladores, chimenea y distancias de remate (no incluida en este paquete) | Ingeniero mecánico + arquitecto | NFPA 96 §7.8 |
| 10 | Fichas técnicas y listados de todos los equipos marcados * (DIMENSION TO VERIFY) | Cliente / proveedor de cocina | 12 equipos, 07 §M |
| 11 | Carta de la administración (obras, baños comunes, basura, gas, cubierta, PS-1, puerta, rótulos, horario) | Cliente | 08 |
| 12 | Autorización del propietario registral / arrendador | Cliente | 06 paso 1 |
| 13 | Uso de suelo conforme (restaurante con venta de licor) | Cliente | 06 paso 2 |
| 14 | Confirmar con el Área Rectora de Salud que se aceptan los baños comunes del centro comercial | Cliente + arquitecto | 03, 05 PER-13 |
| 15 | Plan de emergencias, capacitación, contratos de limpieza de ductos y mantenimiento de supresión | Operador (LAVA) | 03 §14 |

## 6. Cómo regenerar

```bash
tools/build_all.sh                      # validación + láminas + informe + app
python3 tools/permit_docs.py           # estos documentos + PDF (lee plan/sheets.json)
python3 tools/permit_docs.py --research <research.json> --audit <audit.json>   # actualiza la copia normativa
```

Banderas del anteproyecto (se mantienen literalmente en inglés en láminas y documentos):

- **EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED**
- **SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED**
- **DIMENSION TO VERIFY**
- **VERIFY ON SITE**
