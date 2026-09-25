# 04 · Cálculos preliminares de instalaciones

**LAVA – Contemporary Fire & BBQ** — local ex-Marna's, Terrazas Lindora (centro comercial abierto en régimen de condominio), Lindora, Santa Ana, San José, Costa Rica  
Anteproyecto v3.0 · 2026-09-25 · documento generado desde los datos del proyecto (`tools/permit_docs.py`)

> **ANTEPROYECTO / PRELIMINAR** — no es un documento constructivo ni una declaración de cumplimiento: todo lo aquí indicado es **a validar por el profesional responsable** (CFIA) y por las ingenierías. Las citas normativas provienen mayormente de fuentes secundarias y se marcan "verificar".

**PRELIMINAR — a validar por ingeniero** (mecánico / electricista). Valores de referencia para dimensionar espacios y coordinar; no sustituyen las memorias de cálculo firmadas. Fuentes: `data/mech_calcs.json` (M-101/M-102) y `data/elec_loads.json` (E-101).

## Resumen de cifras (PRELIMINAR)

| Concepto | Valor preliminar | Ver |
|---|---|---|
| Extracción EXT-1 (HD-1) | 1068 L/s · ducto 450×350 mm | §1 |
| Extracción EXT-2 (HD-2) | 1320 L/s · ducto 450×400 mm | §1 |
| Aire de reposición AR-1 | 2030 L/s (85 %) · ducto 700×500 mm | §2 |
| Gas (4 equipos) | ≈102.7 kW · principal 1" GLP / 1-1/4" GN | §3 |
| Agua caliente | 205 L/h pico → CA-1 150 L / 6.0 kW + CA-2 15 L | §4 |
| Trampa de grasa GT-1 | 15–35 gpm (PDI, referencia) | §5 |
| Electricidad | demanda 33.8 kVA · diseño 36.7 kVA · principal 125 A (120/208 V 3F 4H + T) | §7 |

## 1. Extracción de campanas

PRELIMINAR — a validar por ingeniero. Caudal por metro lineal de campana según el servicio (ASHRAE 154 / IMC 507, campana mural no listada = referencia conservadora); campanas listadas UL 710 suelen operar en el rango indicado (guías CKV / fabricante). La selección final la hace el ingeniero con el listado del equipo.

| Sistema | Campana | L × F (m) | Equipos | Servicio | cfm/ft / L/s·m | Q (L/s / m³/h / cfm) | Ducto (mm) | Rango campana listada (L/s) |
|---|---|---|---|---|---|---|---|---|
| EXT-1 | HD-1 · grasa (gas) | 2.30 × 1.15 | H2, H3, H4, H5 | medio | 300 / 464 | 1068 / 3846 / 2264 | 450×350 (6.8 m/s) · Ø450 | 712–1068 |
| EXT-2 | HD-2 · combustible sólido | 1.55 × 1.10 | H1 | extra-pesado (combustible sólido) | 550 / 852 | 1320 / 4752 / 2797 | 450×400 (7.3 m/s) · Ø475 | 840–1320 |

Velocidad de diseño 7.5 m/s; mínima NFPA 96 2.54 m/s; máxima práctica 12.7 m/s. Sección = Q / v_diseño; rectangular en pasos de 50 mm (relación ≤1.5) y circular en pasos de 25 mm.

Riser existente de Marna's para EXT-1: sección 0.40 × 0.40 m → 6.68 m/s con el caudal de EXT-1. Compatible por velocidad si el ducto aguas arriba mantiene la sección y cumple NFPA 96 (material, soldadura, cerramiento) — VERIFY ON SITE. El collarín existente queda sobre la nueva división NW-1: requiere transición sobre el cielo.

EXT-3 (smoker S1): Chimenea propia de tiro natural, listada según el fabricante del smoker y NFPA 211; diámetro del collarín del equipo (típ. 150–200 mm) — VERIFY ficha. Si se exige campana: Si el smoker deja escapar efluentes al abrir la puerta (NFPA 96 cap. 14): campana listada y sistema de extracción independiente → ≈1192 L/s (4292 m³/h), ducto 400×400 mm.

**EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED.** **SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED.**

## 2. Aire de reposición

PRELIMINAR — a validar por ingeniero. Aire de reposición 80–90 % del caudal extraído (cocina levemente negativa respecto del salón; ΔP ≤ 4.98 Pa NFPA 96 §8.3; con combustible sólido, suministro positivo durante toda la cocción)

Extracción total 2388 L/s (8598 m³/h, 5061 cfm).

| % reposición | Q (L/s) | m³/h | cfm | Transferencia desde salón (L/s) |
|---|---:|---:|---:|---:|
| 80 % | 1911 | 6879 | 4049 | 478 |
| 85 % (diseño) | 2030 | 7309 | 4302 | 358 |
| 90 % | 2150 | 7738 | 4555 | 239 |

- Ducto de reposición 700×500 mm (5.8 m/s) o Ø675 mm.
- Difusores: 2 × 1015 L/s → área de cara ≥2.03 m² c/u a 0.5 m/s. Descarga a baja velocidad (≈0.5 m/s o menos cerca de las campanas; guías CKV / ASHRAE) para no perturbar la captura: difusores perforados o pleno perimetral — TO BE ENGINEERED. Con 2 difusores el área resulta grande: evaluar pleno perimetral o más difusores.
- Si el smoker necesita campana: +1192 L/s de extracción → reposición ≈3044 L/s.

## 3. Gas

PRELIMINAR — a validar por ingeniero. Fuente: Red de gas del centro comercial (tipo de gas y presión: VERIFY). Potencias típicas de catálogo — reemplazar por las fichas técnicas de los equipos (DIMENSION TO VERIFY).

| Equipo | Descripción | kW típ. | BTU/h típ. | Base | Ramal GLP | Ramal GN |
|---|---|---:|---:|---|---|---|
| H2 | Cocina 4Q gas | 35.2 | 120 000 | 4 quemadores × 8.8 kW (30 000 BTU/h) | 1/2" | 1/2" |
| H3 | Plancha | 14.7 | 50 000 | plancha 70 cm, 2 quemadores × 25 000 BTU/h | 1/2" | 1/2" |
| H4 | Freidora 1 | 26.4 | 90 000 | freidora 40 cm ≈ 18 kg de aceite, 90 000 BTU/h | 1/2" | 1/2" |
| H5 | Freidora 2 | 26.4 | 90 000 | freidora 40 cm ≈ 18 kg de aceite, 90 000 BTU/h | 1/2" | 1/2" |

Total ≈102.7 kW (350 000 BTU/h) → GLP ≈7.39 kg/h (3.97 m³/h) · gas natural ≈9.91 m³/h. Largo en planta 3.54 m, desarrollado ≈8.31 m.

| Tramo | Largo de tabla (ft) | GLP | GN |
|---|---:|---|---|
| en el local | 30 | 1" | 1" |
| hasta 15 m desde el regulador | 50 | 1" | 1-1/4" |

Recomendado: 1" (25 mm) hierro negro cédula 40 si es GLP; 1-1/4" (32 mm) si es gas natural — PRELIMINAR — TO BE ENGINEERED. NFPA 54 tablas de capacidad (tubería metálica céd. 40, ΔP 0.5" c.a.; GLP 11" c.a. / GN <2 psi) — valores de referencia, verificar edición; para GLP rigen además NFPA 58 y las disposiciones de Bomberos.

## 4. Agua caliente

PRELIMINAR — a validar por ingeniero. ASHRAE Handbook HVAC Applications (Service Water Heating), restaurante de servicio completo: 5.7 L (1.5 gal) a 60 °C por comida en la hora máxima — referencia, verificar. 36 asientos → 36 comidas en la hora pico → **205 L a 60 °C**. Capacidad 1.ª hora = 0.7 × volumen + recuperación (kW × 3600 / (4.186 × 40 K)).

| Volumen (L) | kW | Recuperación (L/h) | 1.ª hora (L) | ≥ demanda |
|---:|---:|---:|---:|---|
| 80 | 3.0 | 65 | 121 | no |
| 100 | 4.5 | 97 | 167 | no |
| 150 | 6.0 | 129 | 234 | sí |
| 200 | 6.0 | 129 | 269 | sí |
| 300 | 9.0 | 194 | 404 | sí |

- CA-1: termotanque eléctrico vertical 150 L / 6.0 kW, mural sobre W3 (1.ª hora 234 L).
- CA-2: calentador eléctrico bajo barra (punto de uso) 15 L / 1.5 kW — sirve PB-1 (C1).
- Almacenamiento ≥60 °C; lavamanos con válvula mezcladora termostática (≈43 °C) — criterio usual, verificar CIHSE / Salud. Circuitos eléctricos de CA-1 y CA-2 en las láminas eléctricas. PRELIMINAR — TO BE ENGINEERED

## 5. Trampa de grasa GT-1

PRELIMINAR — a validar por ingeniero. PDI G-101 (referencia): caudal = volumen de tanques × 0.75 / periodo de vaciado; capacidad de grasa ≈ 2 × caudal (lb) — el CIHSE 2017 rige el dimensionamiento final.

| Periodo de vaciado | Caudal (gpm / L/s) | Tamaño PDI (gpm / L/s) | Capacidad de grasa (lb / kg) |
|---|---:|---:|---:|
| 1 min | 29.7 / 1.88 | 35 / 2.21 | 70 / 31.8 |
| 2 min | 14.9 / 0.94 | 15 / 0.95 | 30 / 13.6 |

Supuestos: fregadero W1 de 2 tanques de 0.5 × 0.5 × 0.3 m (150 L). Recomendación: Interceptor hidromecánico bajo W1 de 15–35 gpm (0.95–2.21 L/s), accesible para limpieza; recibe W1, FD-1 y FD-2 — PRELIMINAR — TO BE ENGINEERED.

## 6. Aparatos sanitarios y desagües

PRELIMINAR — TO BE ENGINEERED (CIHSE 2017).

| Tag | Aparato | AF | AC | Desagüe | UD | Sifón / ventilación | Descarga a | Nota |
|---|---|---|---|---|---:|---|---|---|
| W1 | Fregadero 2 tanques + ducha de prelavado | 1/2" (12) | 1/2" (12) | 2" (50) | 3 | sifón 2" · vent. 1-1/2" | GT-1 → WP1 | Agua caliente al tanque de lavado; tanques ≈2 × 75 L supuestos (VERIFY ficha). |
| W2 | Lavamanos del lavado | 1/2" (12) | 1/2" (VMT) | 1-1/2" (38) | 1 | sifón 1-1/2" · vent. 1-1/4" | WP2 | Grifo de pedal o sensor recomendado; jabón líquido y toallas desechables. |
| K3 | Lavamanos de cocina (exclusivo manos) | 1/2" (12) | 1/2" (VMT) | 1-1/2" → 2" bajo piso | 1 | sifón 1-1/2" · vent. 1-1/4" | WP4 | Salud DE 37308-S: lavamanos en el área de cocina (obligatorio). |
| A8 | Lavamanos de la zona fría | 1/2" (12) | 1/2" (VMT) | 1-1/2" → 2" bajo piso | 1 | sifón 1-1/2" · vent. 1-1/4" | WP4 | Exclusivo de cold prep; jabón y toallas desechables. |
| W3 | Pileta de aseo (mop sink) | 1/2" (12) | 1/2" (12) | 3" (75) | 3 | sifón 3" · vent. 1-1/2" | WP3 | Llave con rosca de manguera y rompevacío. Recibe la descarga T&P de CA-1 (indirecta). |
| PB-1 | Pileta de barra (en la barra C1) | 1/2" (desde WP5) | 1/2" (CA-2) | 1-1/2" (38) | 1 | sifón 1-1/2" · vent. 1-1/4" | WP5 | Reutiliza el punto de agua y desagüe de WP5; extensión ≈1 m — VERIFY ON SITE. |
| C5 | Lavamanos del personal de barra | 1/2" (12) | 1/2" (CA-2) | 1-1/2" (38) | 1 | sifón 1-1/2" · vent. 1-1/4" | WP5 | Al fondo del pasillo de barra; desagüe al colector de barra → WP5. |
| CA-1 | Termotanque eléctrico ≈150 L / 6 kW | 3/4" entrada | 3/4" salida | T&P 3/4" | — | válv. T&P + expansión | pileta de aseo (indir.) | Mural sobre la pileta de aseo, anclado a EW-E2 (≈200 kg lleno — VERIFY). Hora pico ≈205 L/h a 60 °C. |
| CA-2 | Calentador bajo barra ≈15 L / 1.5 kW | 1/2" (12) | 1/2" (12) | T&P 1/2" | — | válv. T&P | PB-1 (indirecta) | Punto de uso para la barra (evita un ramal de agua caliente de ≈10 m desde CA-1). |
| LL-1 | Llave de manguera con rompevacío + carrete | 3/4" (18) | — | — | — | — | FD-1 (lavado de pisos) | Manguera fija NFPA 96 cap. 14 si el hogar de H1 > 0.14 m³ (VERIFY ficha); si no, solo lavado. |
| FD-1 | Coladera de piso con canastilla · cocina (zonas B + E) | — | — | 2" (50) | 2 | sifón + sello (cebado) | GT-1 → WP1 | Pendiente de piso hacia la coladera (1–2 %, verificar). Con grasa: pasa por la trampa. |
| FD-2 | Coladera de piso con canastilla · lavado (zona W) | — | — | 2" (50) | 2 | sifón + sello (cebado) | GT-1 → WP1 | Pendiente de piso hacia la coladera (1–2 %, verificar). Con grasa: pasa por la trampa. |
| FD-3 | Coladera de piso con canastilla · cold prep (zona A) | — | — | 2" (50) | 2 | sifón + sello (cebado) | WP3 | Pendiente de piso hacia la coladera (1–2 %, verificar). Recibe condensados indirectos si aplica. |
| GT-1 | Trampa / interceptor de grasa bajo el fregadero | — | — | entrada 2" · salida 3" (75) | 7 | ventilación propia 1-1/2" | WP1 | 15–35 gpm (0.95–2.21 L/s), ref. PDI G-101; CIHSE rige; accesible. |
| WP6 | Punto húmedo existente sin uso | tapón | tapón | tapón registrable | — | — | — | Anular agua y desagüe con tapones accesibles — VERIFY ON SITE. |

| Punto existente | Uso propuesto | UD ref. | Colector | En mep.drain_existing |
|---|---|---:|---|---|
| WP1 | W1 vía GT-1, FD-1, FD-2 | 7 | 3" (75) | sí |
| WP2 | W2 | 1 | 2" (50) | sí |
| WP3 | W3, FD-3 | 5 | 3" (75) | sí |
| WP4 | K3, A8 | 2 | 2" (50) | sí |
| WP5 | PB-1, C5 | 2 | 2" (50) | sí |
| WP6 | sin uso: anular (tapón registrable) | — | — | no |

## 7. Cargas eléctricas

PRELIMINAR — a validar por ingeniero electricista (Código Eléctrico CR / NEC 2020). Sistema supuesto: 120/208 V 3F 4H + T (VERIFY) · alternativa 120/240 V 1F.

| Grupo | kVA | Criterio |
|---|---:|---|
| Alumbrado general | 1.72 | NEC 2020 Tabla 220.12 (restaurantes 16 VA/m²) vs. conectado A-201 → el mayor; 220.42 al 100 % |
| Rótulo exterior | 1.20 | NEC 220.14(F) / 600.5(A): ≥1200 VA |
| Tomas generales | 1.08 | NEC 220.14(I) 180 VA c/u · 220.44 (10 kVA al 100 %, resto 50 %) |
| Equipos de cocina | 13.39 | NEC 2020 220.56 / Tabla 220.56 (≥6 unidades 65 %; nunca menor que la suma de las 2 mayores) |
| Motores (ventiladores) | 9.85 | NEC 220.50 / 430.24: 100 % + 25 % del motor mayor |
| Reserva A/C | 5.31 | Reserva A/C 100 % (220.50 / 440) — a definir por ingeniero mecánico |
| Control / TI | 1.25 | 100 % |
| **Demanda total** | **33.81** |  |
| +25 % cargas continuas | 2.92 | 25 % adicional sobre cargas continuas (alumbrado, rótulo, control/TI, calentadores 422.13) — NEC 215.3 / 230.42 |
| **Carga de diseño** | **36.72** | conectada total 39.58 kVA |

- Corriente: 101.9 A a 208 V 3F (122.3 A con 20 % de crecimiento); 153.0 A a 240 V 1F (183.6 A).
- Sugerido: 120/208 V · 3F · 4H + T (VERIFY con la administración / empresa distribuidora) · principal 125 A · barra 150 A · 54 espacios (43 usados). Alternativa: 120/240 V · 1F · 3H + T: principal 200 A (menos recomendable: motores y equipos de 208 V).
- Balance de fases conectado: A 13.21 kVA, B 13.35 kVA, C 13.02 kVA (desbalance 2.5 %).

### 7.1 Cuadro de circuitos (preliminar)

| Circ. | Ref. | Descripción | V | Polos | kVA | A | Breaker | Cond. | GFCI | Grupo |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 1 | H4 + H5 | Freidoras H4 + H5 · encendido / control | 120 | 1 | 0.24 | 2.0 | 20 | #12 | sí | Equipos de cocina |
| 2 | S1 | Smoker · controles / ventilador de tiro (si aplica) | 120 | 1 | 0.72 | 6.0 | 20 | #12 | sí | Equipos de cocina |
| 3-5 | K2 | Horno convección de mesa + recirc. UL 710B | 208 | 2 | 6.00 | 28.8 | 40 | #8 | sí | Equipos de cocina |
| 4 | A2 | Congelador vertical | 120 | 1 | 0.72 | 6.0 | 20 | #12 | sí | Equipos de cocina |
| 6 | A3 | Mesa fría refrigerada | 120 | 1 | 0.48 | 4.0 | 20 | #12 | sí | Equipos de cocina |
| 7 | S2 | Holding caliente | 120 | 1 | 1.50 | 12.5 | 20 | #12 | sí | Equipos de cocina |
| 8 | A1 | Refrigerador 2 puertas | 120 | 1 | 0.84 | 7.0 | 20 | #12 | sí | Equipos de cocina |
| 9 | C1 | Tomas de mostrador de barra (licuadora / batidora) | 120 | 1 | 1.50 | 12.5 | 20 | #12 | sí | Equipos de cocina |
| 10 | CA-2 | Calentador bajo barra CA-2 15 L | 120 | 1 | 1.50 | 12.5 | 20 | #12 |  | Equipos de cocina |
| 11 | C1 | Enfriador bajo barra (cerveza / bebidas) | 120 | 1 | 0.60 | 5.0 | 20 | #12 | sí | Equipos de cocina |
| 12-14 | CA-1 | Termotanque CA-1 150 L (M-101) | 208 | 2 | 6.00 | 28.8 | 40 | #8 |  | Equipos de cocina |
| 13 | C2 | Pase C2 · lámparas de calor (L-7) | 120 | 1 | 0.50 | 4.2 | 20 | #12 |  | Equipos de cocina |
| 15-17-19 | EXT-1 | Ventilador EXT-1 · HD-1 · grasa (gas) · en cubierta | 208 | 3 | 2.38 | 6.6 | 15 | #12 |  | Motores / ventilación |
| 16-18-20 | EXT-2 | Ventilador EXT-2 · HD-2 · combustible sólido · en cubierta | 208 | 3 | 2.70 | 7.5 | 15 | #12 |  | Motores / ventilación |
| 21-23-25 | AR-1 | Ventilador de reposición AR-1 · en cubierta (sin templar) | 208 | 3 | 3.82 | 10.6 | 20 | #12 |  | Motores / ventilación |
| 22-24-26 | A/C | A/C salón + barra (reserva ≈4.5 TR) | 208 | 3 | 5.31 | 14.7 | 20 | #12 |  | A/C (reserva) |
| 27 | LUM-1 | Alumbrado salón (L-1 rieles · L-2 · L-4 apliques) + EM/RS | 120 | 1 | 0.31 | 2.6 | 20 | #12 |  | Alumbrado |
| 28 | LUM-3 | Alumbrado cocina caliente + BBQ (L-8 IP65 · L-9 campanas) + EM | 120 | 1 | 0.34 | 2.9 | 20 | #12 |  | Alumbrado |
| 29 | RÓT. | Rótulo exterior de fachada (reglamento del condominio) | 120 | 1 | 1.20 | 10.0 | 20 | #12 |  | Rótulo exterior |
| 31 | LUM-2 | Alumbrado barra + decor (L-2 · L-3 · L-5 · rótulo L-6) + EM | 120 | 1 | 0.20 | 1.7 | 20 | #12 |  | Alumbrado |
| 32 | LUM-4 | Alumbrado lavado + cold prep (L-8 IP65) + EM/RS | 120 | 1 | 0.38 | 3.2 | 20 | #12 |  | Alumbrado |
| 33 | K1 · W4 | Tomas generales cocina (mesada K1) + lavado (W4) | 120 | 1 | 0.36 | 3.0 | 20 | #12 | sí | Tomas generales |
| 34 | A4 | Tomas generales cold prep (mesada A4: procesador / selladora) | 120 | 1 | 0.18 | 1.5 | 20 | #12 | sí | Tomas generales |
| 37 | D · D2 | Tomas generales salón (limpieza) + recepción / delivery D2 | 120 | 1 | 0.54 | 4.5 | 20 | #12 |  | Tomas generales |
| 38 | SUP·DG·CO | SUP-1/SUP-2 (liberación / alarma) + DG-1 gas + DCO-1 CO | 120 | 1 | 0.15 | 1.2 | 15 | #12 |  | Control / seguridad |
| 39 | CC-1 · VS | CC-1 control de campanas + VS solenoide N.C. (rearme manual) + KS-1 | 120 | 1 | 0.20 | 1.7 | 15 | #12 |  | Control / seguridad |
| 40 | C3 | POS + impresora de comandas | 120 | 1 | 0.50 | 4.2 | 20 | #12 | sí | POS / TI |
| 42-44-46 | EXT-3 | Reserva: campana + ventilador del smoker (si Bomberos lo exige) | 208 | 3 | 2.38 | 6.6 | 15 | #12 |  | Reserva (no sumada) |
| 43 | RK-1 | RK-1 comunicaciones · Wi-Fi · audio · CCTV (mural junto a TE-1) | 120 | 1 | 0.40 | 3.3 | 20 | #12 |  | POS / TI |
| 45-47 | S1 alt. | Reserva: smoker eléctrico / pellet listado (alternativa EXT-3) | 208 | 2 | 6.00 | 28.8 | 40 | #8 |  | Reserva (no sumada) |

kVA de equipos: valores típicos de catálogo (TBV) — reemplazar por las placas de los equipos.

### 7.2 Matriz de enclavamientos

| Causa | Efectos |
|---|---|
| Disparo SUP-1 (HD-1) | VS: cierra, rearme manual; KS-1: abre (freidoras 120 V); EXT-1: sigue salvo listado; AR-1: según listado; alarma: C.C. + local |
| Disparo SUP-2 (HD-2) | VS: cierra (recomendado); KS-1: abre (recomendado); EXT-2: sigue; AR-1: según listado; alarma: C.C. + local |
| DG-1 detecta gas | VS: cierra, rearme manual; alarma: local |
| DCO-1 detecta CO | EXT/AR: siguen; alarma: local |
| EXT-1 sin prueba de flujo | VS: cierra; KS-1: abre |
| EXT-1 o EXT-2 en marcha | AR-1: arranca (IMC 508.1.1); VS/KS-1: permiso |
| Brasas en H1/S1 | EXT-2: no se apaga (selector con llave); AR-1: mantiene reposición |
| Falla de energía | VS: cierra (N.C.), rearme manual; KS-1: abre; EXT/AR: paran |

### 7.3 Alumbrado (de A-201)

| Tipo | Cantidad | W totales |
|---|---:|---:|
| L-1 | 18 | 180 |
| L-2 | 9 | 108 |
| L-3 | 3 | 24 |
| L-4 | 3 | 18 |
| L-5 | 2 | 95 |
| L-6 | 1 | 60 |
| L-8 | 17 | 612 |
| L-9 | 4 | 80 |

Conectado 1240 VA; mínimo NEC 1722 VA (16 VA/m² × 107.6 m²).

## 8. Fuentes y verificaciones en sitio

- CIHSE 2017 (CFIA): agua potable, desagües, ventilación, interceptores de grasa — edición vigente a confirmar
- Salud DE 37308-S (servicios de alimentación): lavamanos en cocina, agua caliente en lavado, pisos a coladeras
- NFPA 96 (edición adoptada por el RNPCI 2023 a confirmar): cap. 7 ductos, §7.8 descargas, §8.2.1.1 velocidad ≥2.54 m/s, §8.3 aire de reposición, cap. 10 supresión y corte de combustible, cap. 14 combustible sólido
- NFPA 17A / UL 300: supresión de químico húmedo · NFPA 211: chimeneas · NFPA 54 / 58: gas
- ASHRAE 154 / IMC 507: caudales de referencia por servicio · PDI G-101: interceptores · ASHRAE HVAC Applications: agua caliente
- Citas tomadas de resúmenes de búsqueda, no de textos primarios: verificar edición y numeración
- NEC 2020 (NFPA 70): 110.26 espacio de trabajo; 210.8(B) GFCI; 220.12 / 220.14(F)(I) / 220.42 / 220.44 / 220.50 / 220.56; 215.3 / 230.42 cargas continuas; 422.13 calentadores; 430.24 / 430.52 / 430.102 motores; 600.5 rótulos; 700.12 equipos autónomos
- Código Eléctrico de Costa Rica (DE 36979-MEIC y reformas; NEC 2020 oficializado el 10-07-2024 según prensa) — verificar
- NFPA 96: corte de combustible y energía al disparar la supresión (rearme manual); ventilador sigue operando; cap. 14 combustible sólido
- NFPA 17A / UL 300 (supresión química húmeda) · UL 710B (recirculación del horno K2) · IMC 508.1.1 (reposición enclavada)
- NFPA 101 7.9 (iluminación de emergencia ≥1.5 h) · NFPA 72 (circuito exclusivo con traba)
- Citas tomadas de resúmenes y conocimiento general, no de textos primarios: verificar edición y numeración

VERIFY ON SITE (eléctrico): Tensión / fases disponibles y medidor; Capacidad asignada al local por el C.C.; Ruta de acometida; Tablero existente de Marna's; Placas de equipos (TBV); Alarma del C.C. para señales de supresión.

Banderas del anteproyecto (se mantienen literalmente en inglés en láminas y documentos):

- **EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED**
- **SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED**
- **DIMENSION TO VERIFY**
- **VERIFY ON SITE**
