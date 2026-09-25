# 03 · Seguridad humana y egreso

**LAVA – Contemporary Fire & BBQ** — local ex-Marna's, Terrazas Lindora (centro comercial abierto en régimen de condominio), Lindora, Santa Ana, San José, Costa Rica  
Anteproyecto v3.0 · 2026-09-25 · documento generado desde los datos del proyecto (`tools/permit_docs.py`)

> **ANTEPROYECTO / PRELIMINAR** — no es un documento constructivo ni una declaración de cumplimiento: todo lo aquí indicado es **a validar por el profesional responsable** (CFIA) y por las ingenierías. Las citas normativas provienen mayormente de fuentes secundarias y se marcan "verificar".

Memoria de seguridad humana y protección contra incendios, base para la lámina A-104 (Seguridad humana y protección contra incendios) y la revisión de Bomberos (APC). Cifras de `data/life_safety_calcs.json` y `data/layout.json`.

## 1. Normativa aplicada

- Reglamento Nacional de Protección contra Incendios (RNPCI, versión 2023, Bomberos): adopta el paquete NFPA. El Manual de Disposiciones Técnicas 2013 está derogado (fuente secundaria, verificar).
- NFPA 101 (carga de ocupantes, egreso, señalización, iluminación de emergencia), NFPA 10 (extintores), NFPA 96 (cocinas comerciales, cap. 14 combustible sólido — cap. 15 en ediciones 2021/2024), NFPA 17A (químico húmedo), NFPA 72 (detección y alarma).
- Edición: la vigente adoptada por Bomberos a la fecha de presentación — **verificar edición**. La numeración citada corresponde a las ediciones 2018–2024.
- Límites NFPA 101 para <50 personas sin rociadores: camino común 22.86 m (75 ft), recorrido 45.72 m (150 ft). Verificar edición.

## 2. Clasificación y capacidad

| Concepto | Valor |
|---|---|
| Capacidad máxima declarada (clientes + personal) | 49 personas |
| Carga de cálculo (redondeo por zona) | 46 |
| Carga de cálculo (redondeo por uso / sin redondear) | 43 / 42.75 |
| Umbral de reunión pública (NFPA 101 6.1.2.1, verificar) | 50 personas |
| Clasificación adoptada | mercantil <50 — restaurante con menos de 50 personas (NFPA 101 A.6.1.2.1, verificar); validar con Bomberos |
| Rociadores | NFPA 101 no exige rociadores con <50 personas. Si el centro comercial tiene red o alarma, integrarse según NFPA 13/72 — VERIFY con la administración. |

Condición de diseño: ocupación de menos de 50 personas (NFPA 101 mercantil / <50): una salida, puerta sin exigencia de giro hacia afuera ni antipánico. VERIFY con Bomberos (RNPCI).

## 3. Carga de ocupantes por zona

| Zona | Uso | Área (m²) | m²/pers. | Base | Cálculo | Ocupantes |
|---|---|---:|---:|---|---:|---:|
| D · DINING | Salón con mesas y sillas (NFPA 101 Tabla 7.3.1.2) | 51.58 | 1.4 | neto | 36.84 | 37 |
| C · BAR / POS | Barra/caja/pase: área de trabajo, solo servicio (sin taburetes ni clientes de pie) | 5.78 | 9.3 | bruto | 0.62 | 1 |
| B · HOT LINE / SHOW KITCHEN | Cocina, lavado, almacén (NFPA 101 Tabla 7.3.1.2) | 12.59 | 9.3 | bruto | 1.35 | 2 |
| E · BBQ PRODUCTION | Cocina, lavado, almacén (NFPA 101 Tabla 7.3.1.2) | 8.18 | 9.3 | bruto | 0.88 | 1 |
| W · WASHING | Cocina, lavado, almacén (NFPA 101 Tabla 7.3.1.2) | 9.59 | 9.3 | bruto | 1.03 | 2 |
| A · COLD PREP | Cocina, lavado, almacén (NFPA 101 Tabla 7.3.1.2) | 18.87 | 9.3 | bruto | 2.03 | 3 |
| Total |  | 106.59 |  |  | 42.75 | 46 |

Método: Área de zona (validation.json, m²) ÷ factor (layout.life_safety.load_factors); redondeo hacia arriba por zona. Resultado ≤ 49 declaradas (margen 3 personas) — a validar por el profesional responsable.

## 4. Salidas

| Salida | Vano | Ancho (m) | Hoja (m) | Capac. (5 mm/p) | Req. (mm) | Se cuenta | Nota |
|---|---|---:|---:|---:|---:|---|---|
| SAL-1 | D-ENT | 2.00 | 0.97 | 400 | 245 | sí | Salida principal al pasillo abierto del centro comercial. Hojas hoy hacia adentro (permitido con <50 personas). Recomendado invertir el giro hacia afuera sin invadir el pasillo común — VERIFY con la administración. |
| SAL-2 | PS-1 | 0.90 | 0.90 | 180 | 245 | no (condicional) | Segunda salida del personal SOLO si se aprueba PS-1 (condicional). No se cuenta para el cálculo. |

- Salida única SAL-1 (D-ENT) al pasillo abierto del centro comercial. Ruta del ala: cold prep → boca del pasillo → P-2 (cierre automático) → lavado (franja libre ≥0.915 m entre W4 y W1, sin racks ni carritos) → paso de 1.86 m → P-1 → salón → SAL-1.
- Puertas: D-ENT gira hacia adentro (aceptable con <50 ocupantes, NFPA 101 7.2.1.4.2, verificar); se recomienda invertir el giro sin invadir el pasillo común (08). P-1 de vaivén siempre libre; P-2 con cierre automático y sin llave.
- Herrajes: apertura sin llave ni conocimiento especial desde el lado de egreso durante la ocupación (NFPA 101 7.2.1.5, verificar).
- Sin zona de espera interior: el vestíbulo y el barrido de D-ENT son área de egreso libre. Cola y retiro de delivery afuera.
- Recorrido más allá de D-ENT (pasillo común abierto hasta la vía pública): VERIFY ON SITE.

## 5. Recorridos de egreso medidos vs límites

| Ruta | Desde | Salida | Largo (m) | Camino común (m) | Recorrido (m) | Margen (m) | Estado | Con PS-1 (m) |
|---|---|---|---:|---:|---:|---:|---|---:|
| E1 | COLD PREP · punto más remoto (zona A) | SAL-1 | 21.69 | 22.86 | 45.72 | 1.17 | dentro del límite | 0.55 |
| E4 | Línea caliente · operador más remoto (H1–H5) | SAL-1 | 17.31 | 22.86 | 45.72 | 5.55 | dentro del límite | 11.94 |
| E8 | BBQ PRODUCTION · punto más remoto (zona E) | SAL-1 | 17.26 | 22.86 | 45.72 | 5.60 | dentro del límite | 11.01 |
| E2 | WASHING · punto más remoto (zona W) | SAL-1 | 17.21 | 22.86 | 45.72 | 5.65 | dentro del límite | 5.18 |
| E3 | Frente del smoker S1 (operador) | SAL-1 | 16.81 | 22.86 | 45.72 | 6.05 | dentro del límite | 10.40 |
| E6 | Barra / caja · puesto más remoto (zona C) | SAL-1 | 13.26 | 22.86 | 45.72 | 9.60 | dentro del límite | 13.26 |
| E5 | Salón · asiento más lejano (BQ-S#1) | SAL-1 | 11.91 | 22.86 | 45.72 | 10.95 | dentro del límite | 11.91 |
| E7 | Recepción D2 (atril) | SAL-1 | 0.83 | 22.86 | 45.72 | 22.03 | dentro del límite | 0.83 |

Método: Camino más corto sobre grilla de 5 cm (16 vecinos) en el espacio libre = premisas − lavageo.blocking_obstacles (muros, columnas, equipos, mesas, sillas en posición ocupada, bancas) erosionado 0.25 m (radio corporal); suavizado por visibilidad y medido hasta el plano de la puerta de salida. Desde asientos: tramo recto hasta el pasillo cruzando solo sillas/bancas. Contraste: geodésica exacta (grafo de visibilidad) del recorrido más largo ≈ 0.5 % menor (el método queda del lado conservador); con 0.30 m de las esquinas (NFPA 101 7.6) ver la sensibilidad abajo.

Sensibilidad: con 0.30 m de separación de esquinas y obstáculos (NFPA 101 7.6) la ruta E1 mide 21.82 m frente a 22.86 m.

**Margen ajustado:** la ruta más larga (E1, COLD PREP · punto más remoto (zona A)) deja 1.17 m de margen. La franja de evacuación por lavado y P-1 debe permanecer libre (sin racks ni carritos); cualquier cambio de equipos en cold prep o lavado obliga a volver a medir. Con PS-1 aprobada como segunda salida el recorrido baja a lo indicado en la última columna (informativo, PS-1 no se cuenta).

## 6. Anchos libres

| Tramo | Ancho libre mín. (m) | Mín. NFPA 101 (m) | ≥ mínimo |
|---|---:|---:|---|
| Entrada → barra / caja | 1.28 | 0.915 | sí |
| Pase → mesas (pasillo central) | 1.28 | 0.915 | sí |
| Línea → puerta P-1 → pase | 0.98 | 0.915 | sí |
| Salón → puerta P-1 → lavado | 0.95 | 0.915 | sí |
| Frío → prep → pasillo limpio → línea | 1.04 | 0.915 | sí |
| Smoker → holding → línea / pase | 1.00 | 0.915 | sí |
| Pase → staging en recepción (retiro sin cruzar salón) | 0.97 | 0.915 | sí |
| Leña / cenizas ↔ PS-1 (condicional, fuera de horario) | 1.04 | 0.915 | sí |
| entrada → frente de barra | 1.28 | 0.915 | sí |
| pase (lado salón) → fondo del salón | 1.28 | 0.915 | sí |
| puerta P-1 → entrega de loza | 1.04 | 0.915 | sí |
| refrigeración → línea caliente | 1.12 | 0.915 | sí |
| línea caliente → puerta P-1 | 1.04 | 0.915 | sí |
| frente del smoker → puerta P-1 | 1.04 | 0.915 | sí |
| pase (lado cocina) → puerta P-1 | 1.00 | 0.915 | sí |
| recepción / delivery → pase (lado cocina) | 1.00 | 0.915 | sí |
| PS-1 → leña | 1.12 | 0.915 | sí |

Puertas: ancho libre ≥0.81 m por hoja (NFPA 101 7.2.1.2.3.2, verificar) y ≥0.90 m (Ley 7600 art. 140). D-ENT hojas de 0.97 m; P-1 vano 1.02 m — paso libre real VERIFY ON SITE.

## 7. Señalización de salida

| Rótulo | Texto | Posición (x, y) | Zona | Nota |
|---|---|---|---|---|
| RS-1 | SALIDA | 16.15, 2.64 | D · DINING | Sobre la puerta principal, iluminado |
| RS-2 | SALIDA → | 6.90, 2.75 | D · DINING | Direccional colgante en el salón (visible desde P-1 y la barra) |
| RS-3 | SALIDA → | 4.20, 4.48 | B · HOT LINE / SHOW KITCHEN | Cara de cocina de la puerta P-1 |
| RS-4 | SALIDA ↑ | 0.90, 5.15 | A · COLD PREP | Pasillo limpio del ala, hacia la cocina |
| RS-5 | SALIDA ↑ | 1.00, 8.95 | A · COLD PREP | Boca del pasillo limpio desde cold prep |
| RS-6 | SALIDA ↑ | 2.70, 7.40 | W · WASHING | Lavado, sobre la franja de evacuación hacia P-1 |

Rótulos iluminados con autonomía ≥1.5 h. Rótulo de capacidad "CAPACIDAD MÁXIMA 49" junto a D-ENT.

## 8. Iluminación de emergencia

9 luminarias autónomas. Iluminación de emergencia en todo el recorrido: autonomía ≥1.5 h, ≥10.8 lux promedio y ≥1.1 lux mínimo iniciales (NFPA 101 7.9).

| # | Posición (x, y) | Zona |
|---:|---|---|
| 1 | 2.40, 2.40 | B · HOT LINE / SHOW KITCHEN |
| 2 | 0.90, 4.40 | E · BBQ PRODUCTION |
| 3 | 0.90, 7.00 | A · COLD PREP |
| 4 | 2.70, 6.60 | W · WASHING |
| 5 | 2.20, 10.00 | A · COLD PREP |
| 6 | 5.00, 3.60 | D · DINING |
| 7 | 8.60, 2.55 | D · DINING |
| 8 | 12.40, 2.55 | D · DINING |
| 9 | 15.60, 2.55 | D · DINING |

## 9. Extintores portátiles

| Extintor | Tipo | Posición (x, y) | Zona | Nota |
|---|---|---|---|---|
| EX-K | Clase K 6 L | 1.60, 4.95 | E · BBQ PRODUCTION | Freidoras a ≤9.15 m; rótulo: accionar primero el sistema fijo |
| EX-K2 | Clase K 6 L (combustible sólido) | -0.04, 4.70 | E · BBQ PRODUCTION | Smoker y parrilla a ≤6 m (NFPA 96 cap. 14: 2-A de agua pulverizada o químico húmedo K 6 L). Si un hogar supera 0.14 m³: manguera fija de agua. |
| EX-B1 | ABC 2-A:10-B:C | 2.45, 0.13 | B · HOT LINE / SHOW KITCHEN | Cocina caliente: equipos a gas (10-B a ≤9.15 m de las freidoras) |
| EX-A2 | ABC 2-A:10-B:C | 15.80, 4.95 | D · DINING | Salón, junto a la salida |
| EX-A3 | ABC 2-A:10-B:C | 0.35, 8.50 | A · COLD PREP | Ala de servicio (lavado / cold prep) |

Distancias de recorrido medidas (A-104):

| Chequeo | Riesgo | Extintor | Criterio | Medido (m) | Límite (m) | Estado |
|---|---|---|---|---:|---:|---|
| K-H4 | H4 Freidora 1 | EX-K | Extintor clase K a ≤ 9.15 m de recorrido (NFPA 10 §6.6 / NFPA 96) | 4.51 | 9.15 | dentro del límite |
| K-H5 | H5 Freidora 2 | EX-K | Extintor clase K a ≤ 9.15 m de recorrido (NFPA 10 §6.6 / NFPA 96) | 4.91 | 9.15 | dentro del límite |
| SF-H1 | H1 Parrilla argentina | EX-K | 2-A (agua) o K 6 L a ≤ 6 m de recorrido de equipo/almacén de combustible sólido (NFPA 96, verificar) | 2.47 | 6.00 | dentro del límite |
| SF-S1 | S1 Smoker vertical (ahumador) | EX-K | 2-A (agua) o K 6 L a ≤ 6 m de recorrido de equipo/almacén de combustible sólido (NFPA 96, verificar) | 3.31 | 6.00 | dentro del límite |
| SF-S3 | S3 Leña / carbón | EX-K2 | 2-A (agua) o K 6 L a ≤ 6 m de recorrido de equipo/almacén de combustible sólido (NFPA 96, verificar) | 1.37 | 6.00 | dentro del límite |
| B-H2 | H2 Cocina 4Q gas (gas) | EX-B1 | Clase B: 10-B a ≤ 9.15 m de recorrido (NFPA 10 §6.3.1) | 1.99 | 9.15 | dentro del límite |
| B-H5 | H5 Freidora 2 (gas) | EX-B1 | Clase B: 10-B a ≤ 9.15 m de recorrido (NFPA 10 §6.3.1) | 0.90 | 9.15 | dentro del límite |
| A-max | Local completo (riesgo ordinario) | EX-B1, EX-A2, EX-A3 | Clase A: recorrido ≤ 22.9 m al extintor 2-A más cercano (NFPA 10 Tabla 6.2.1.1) | 10.27 | 22.90 | dentro del límite |

## 10. Supresión fija de campanas

- HD-1 (línea a gas: H2, H3, H4, H5): químico húmedo UL 300 / NFPA 17A; corte automático de gas (VS, rearme manual) y de energía de los equipos protegidos (KS-1).
- HD-2 (parrilla H1, combustible sólido): sistema independiente listado para combustible sólido; arrestachispas antes de los filtros.
- Pulsadores PM-1, PM-2 en (4.53, 3.85), h 1.07–1.22 m: Pulsadores manuales de supresión de la campana 1 (PM-1) y de la campana 2 (PM-2), con tapa e identificados, en la cara salón de NW-1 junto al marco norte de P-1: sobre la ruta de salida del personal (NFPA 96 §10.5.1) y separados del fuego por NW-1/NW-2 incombustibles. La referencia de 3–6 m de la campana (IFC / listado) no se alcanza en este local: validar con el listado del sistema y Bomberos — VERIFY.
- EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED.
- SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED.

Chequeo del pulsador (A-104): En la ruta de egreso del personal (≤ 0.60 m del recorrido medido), h 1.07–1.22 m, identificado por campana (NFPA 96 §10.5.1 / NFPA 17A — verificar edición); 3–6 m de la campana = criterio IFC, solo referencia (NFPA 96 no fija distancia): validar con el listado del sistema. Medido a las campanas: HD-1 1.45 m, HD-2 0.20 m; 0.31 m de la ruta de egreso de cocina, 4.90 m a pie desde la línea → **VERIFICAR**: la distancia exigida depende de la edición NFPA 96 / 17A y del listado del sistema (la cifra de 3–6 m es un criterio IFC de referencia).

## 11. Detección y alarma

| # | Posición (x, y) | Zona | Tipo |
|---:|---|---|---|
| 1 | 2.60, 1.90 | B · HOT LINE / SHOW KITCHEN | térmico |
| 2 | 0.60, 6.20 | A · COLD PREP | humo |
| 3 | 2.40, 9.80 | A · COLD PREP | humo |
| 4 | 9.80, 2.00 | D · DINING | humo |
| 5 | 13.20, 3.10 | D · DINING | humo |

- Detección e integración a la alarma del centro comercial si existe (VERIFY). En cocina caliente: detector térmico, no de humo. Monitoreo de CO recomendado por los dos aparatos de combustible sólido.
- NFPA 101 no exige rociadores con <50 personas. Si el centro comercial tiene red o alarma, integrarse según NFPA 13/72 — VERIFY con la administración.
- Detector de gas DG-1 y monitor de CO DCO-1: ver 02 §14 y E-101.

## 12. Combustible sólido (leña / carbón)

- Leña/carbón: solo la provisión de un día, en gabinete metálico cerrado (S3), nada encima, ≥0.915 m de aparatos de combustible sólido. Cenizas: retiro diario en contenedor metálico con tapa, fuera de horario, a un punto exterior acordado con la administración.
- Separación medida del almacén S3 a los aparatos: S1 1.00 m, H1 3.01 m (≥0.915 m exigidos, NFPA 96 cap. 14, verificar; depende de la huella real del smoker).
- Extintor para combustible sólido (2-A de agua pulverizada o clase K 6 L) a ≤6 m de cada aparato y del almacén; manguera fija si un hogar supera 0.14 m³ (verificar ficha).
- SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED.

## 13. Riesgos especiales

- Aparatos a gas bajo HD-1 y parrilla de carbón/leña bajo HD-2; smoker con chimenea propia (EXT-3).
- Almacén de químicos W7 en gabinete cerrado; almacén seco A6 en el ala; leña S3 provisión de un día.
- Horno K2 con recirculación listada UL 710B.

## 14. Condiciones de operación (compromisos del operador)

- No superar 49 personas en el local (clientes + personal); rótulo visible en D-ENT.
- Barra solo de servicio: sin taburetes ni clientes de pie; sin espera interior; cola y retiro de delivery afuera.
- Mantener libres la franja de lavado, P-2 y P-1 (ruta de evacuación del ala).
- Leña: solo la provisión de un día; cenizas en contenedor metálico con tapa, retiro diario fuera de horario.
- Plan de emergencias integrado al del condominio, capacitación en extintores y supresión, simulacro anual.
- Limpieza de la extracción de combustible sólido mensual; mantenimiento semestral de la supresión; bitácora de inspecciones.

## 15. Qué cambia con 50 personas o más

- Pasa a ocupación de reunión pública (NFPA 101 cap. 12, verificar edición).
- Puerta D-ENT con giro hacia afuera (7.2.1.4.2) y posibles herrajes antipánico (umbral de 100 personas en reunión pública, verificar edición).
- Camino común limitado a 6.1 m cuando el espacio sirve a más de 50: la salida única deja de ser aceptable → segunda salida (PS-1).
- Rociadores automáticos supervisados en restaurantes nuevos de reunión pública (12.3.5, ediciones 2021+).
- Pasillos que sirven mesas ≥1.12 m; rótulo de carga de ocupantes obligatorio.

## 16. Observaciones abiertas del cálculo (A-104)

- PM-1 / PM-2: en la ruta de egreso (0.31 m), pero en planta a HD-1 1.45 m, HD-2 0.20 m de las campanas (criterio IFC de referencia 3–6 m; NFPA 96 no fija distancia): VERIFICAR con el listado del sistema de supresión y el profesional responsable.

Banderas del anteproyecto (se mantienen literalmente en inglés en láminas y documentos):

- **EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED**
- **SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED**
- **DIMENSION TO VERIFY**
- **VERIFY ON SITE**
