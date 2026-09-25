# LAVA · Contemporary Fire & BBQ — Informe del anteproyecto (test-fit v3)

Anteproyecto v3 de **LAVA · Contemporary Fire & BBQ** en el local ex-Marna’s (Terrazas Lindora, centro comercial abierto, Santa Ana). La geometría base son los vectores del PDF de Marna’s (1:50, calibrado con los 16.30 m entre ejes A y C); no se modificaron columnas, escalera, perímetro ni zonas húmedas. Se mantiene la zonificación fijada por el cliente (hot line sobre la división con el salón; BBQ production en el muro del fondo; lavado en PILAS; cold prep en la antigua PASTELERÍA) y se incorporan los ajustes de una revisión normativa preliminar (CFIA/APC, Municipalidad de Santa Ana, Bomberos/NFPA, Ministerio de Salud y Ley 7600). Es un anteproyecto para que un profesional responsable del CFIA lo verifique en sitio, lo ajuste y lo firme: no es todavía un plano constructivo.

Láminas A2: [`plan/LAVA_test-fit_planos_A2.pdf`](../plan/LAVA_test-fit_planos_A2.pdf) (A-101 planta arquitectónica propuesta · A-102 existente / demolición / nuevo · A-103 flujos y circulaciones · A-104 seguridad humana y protección contra incendios · A-105 accesibilidad (ley 7600) · A-106 acabados y puertas). Documentos para permisos: [`docs/permisos/`](permisos/). Archivos DXF para AutoCAD: `plan/*.dxf`. Recorrido 3D: [`app/index.html`](../app/index.html).

## 1. Resumen en cifras

| Indicador | Valor |
|---|---|
| Asientos en salón | **36** (18 sillas + 18 puestos en banca · 10 mesas de 2 (unibles) y 4 mesas de 4) |
| Corrimiento de la división cocina/salón | 1.97 m hacia atrás (de X = 6.30 a X = 4.33) |
| Área B · Hot line / show kitchen (incluye mesa + horno) | ≈ 12.6 m² |
| Área E · BBQ production (smoker + holding + leña) | ≈ 8.2 m² |
| Área W · Washing (antiguas PILAS) | ≈ 9.6 m² |
| Área A · Cold prep + frío + almacén (antigua PASTELERÍA) | ≈ 18.9 m² |
| Área C · Bar / POS + pase | ≈ 5.8 m² |
| Área D · Dining (salón) | ≈ 51.6 m² |
| Área total de producción (B + E + W + A) | ≈ 49.2 m² |
| Área de salón + barra (D + C) | ≈ 57.4 m² |
| Área interior del local (medida sobre el PDF) | ≈ 107.7 m² |
| Pasillo principal del salón (ancho libre medido) | 1.28 m |
| Hot line / campana propuesta | 3.80 m / 3.85 m |
| Asientos con línea de vista directa a la parrilla | 100 % · visible desde la entrada: sí |

## 2. Anchos de pasillo (medidos automáticamente sobre la planta)

Ancho libre mínimo a lo largo de cada recorrido, entre equipos, mobiliario (sillas ocupadas) y muros.

| Recorrido | Tipo | Ancho mínimo | Requerido | Longitud |
|---|---|---|---|---|
| Entrada → barra / caja | clientes | **1.28 m** | 1.10 m | 9.9 m |
| Pase → mesas (pasillo central) | meseros | **1.28 m** | 1.10 m | 8.6 m |
| Línea → puerta P-1 → pase | meseros | **0.98 m** | 0.90 m | 5.6 m |
| Salón → puerta P-1 → lavado | sucio | **0.95 m** | 0.90 m | 14.1 m |
| Frío → prep → pasillo limpio → línea | limpio | **1.04 m** | 1.00 m | 11.5 m |
| Smoker → holding → línea / pase | limpio | **1.00 m** | 1.00 m | 3.6 m |
| Pase → staging en recepción (retiro sin cruzar salón) | delivery | **0.97 m** | 0.90 m | 11.5 m |
| Leña / cenizas ↔ PS-1 (condicional, fuera de horario) | combustible | **1.04 m** | 0.90 m | 8.5 m |

## 3. Zonificación operativa (fijada por el cliente)

Secuencia desde el salón hacia el fondo: **muro al restaurante → HOT LINE → apoyo (mesa + horno) → muro del fondo (smoker + holding) → PILAS (lavado) → PASTELERÍA (cold prep)**. Lo optimizado dentro de esa lógica: espaciamientos, tamaños de mesa, sentido de puertas, pasillos, posición del pase y la conexión barra–cocina, y el layout del salón.

| Zona | Ubicación | Contenido (frente × fondo, cm) | Área |
|---|---|---|---|
| B · HOT LINE / SHOW KITCHEN | Contra la nueva división; a la derecha al entrar a la cocina desde el salón | Parrilla 150×90* (combustible sólido, campana 2 propia ≈155×110) → cocina 4Q 80×80* → plancha 70×80* → freidora 1 40×80* → freidora 2 40×80* (campana 1 ≈230×115 con supresión UL 300). Espacio técnico de 15 cm detrás de la línea a gas. Mesa inox 140×70 + horno eléctrico de mesa (ventless) en el muro norte. Lavamanos 33×38. | ≈ 12.6 m² |
| E · BBQ PRODUCTION | Muro oeste (fondo de la cocina) | Smoker vertical ≈140×75* con chimenea propia → holding caliente ≈60×75* → gabinete metálico de leña/carbón 100×50* (provisión de un día). Frente libre 1.00 m. | ≈ 8.2 m² |
| W · WASHING | Ubicación existente de PILAS (drenajes WP1–WP3) | Fregadero 2 tanques 200×80 con trampa de grasa y basureros con tapa bajo el escurridor sucio, lavamanos 33×38, mop sink 60×50, mesa de escurrido limpio 187×60, estante loza limpia 120×35, gabinete de químicos. P-2 de cierre automático hacia el pasillo limpio. | ≈ 9.6 m² |
| A · COLD PREP | Antigua PASTELERÍA + pasillo limpio del muro oeste | Refrigerador 2P 145×70×200 y congelador 75×70×200 contra el muro este, mesa fría 180×70 + esquinero + mesa inox 120×70 en L, lavamanos, estantería 170×35, almacén seco 280×45. | ≈ 18.9 m² |
| C · BAR / POS | Salón, junto a la división (lado norte) | Barra de bebidas 68×65 (h 1.05), caja accesible h 0.80 con POS (90×65), pase caliente 65×65, lavamanos de barra. Solo servicio: sin taburetes. | ≈ 5.8 m² |
| D · DINING | Salón | 36 asientos: 2 bancas con asientos individuales fijos (8 + 10), 10 mesas de 2 (70×70, unibles) y 4 mesas de 4 (120×70), 18 sillas; 2 mesas accesibles (TN6, TS8); casilleros del personal junto a P-1. | ≈ 51.6 m² |

## 4. Corrimiento de la división cocina / salón

La nueva división (NEW PROPOSED WALL, NW-1) queda con su cara de cocina en X = 4.33 m desde el eje A: **1.97 m más atrás** que la división de Marna’s (X = 6.30). El salón gana ≈ 9.6 m² (1.97 × 4.87 m).

Por qué no más atrás: la hot line mide 3.80 m y, con la puerta P-1 (vano 1.02 m), ocupa los 4.87 m de la división. Detrás de la línea hay que dejar 1.10 m libres frente a las freidoras hasta la mesa del muro norte (140 × 70) y 1.00 m frente al smoker, además del espacio técnico de 15 cm para el gas. Con un horno de piso (en vez de horno de mesa) la división tendría que quedar en X ≈ 5.1.

La división es un muro bajo macizo e incombustible h ≈ 1.00 m con vidrio encima, para ver la parrilla desde el salón (visible desde la entrada, a ≈ 12 m, y desde el 100 % de los asientos). Detrás de la parrilla el vidrio debe ser vitrocerámico (≥680 °C) o llevar pantalla inox con cámara ventilada; en el resto, vidrio de seguridad. Sin leña real ni jardinera en la base: el relieve decorativo es incombustible. Un panel térmico (NW-2) cierra el costado de la parrilla hacia la puerta P-1. Especificación TO BE ENGINEERED.

## 5. Muros: existentes, a demoler y nuevos

Lectura hecha sobre el PDF (espesor, trama de mampostería, relación con columnas). Confirmar en sitio con sondeo antes de demoler (instalaciones embebidas, anclajes, rigidizadores).

| Muro | Lectura | Acción |
|---|---|---|
| Columnas de concreto (ejes A/B/C – 1/2), envolvente de la columna A1 con ductos (EW-PIL), escalera del edificio | Estructura / ductos del edificio | EXISTING WALL · se mantiene |
| Perímetro: muros norte, oeste, sur del ala, EW-E1 (40 cm, con ducto S3), EW-E2, muro sur del salón | Perimetral | EXISTING WALL · se mantiene |
| IP-KB · división cocina / barra de Marna’s (X = 6.30) | 10 cm, sin trama de mampostería, sin columnas → liviana | WALL TO DEMOLISH |
| IP-P0b · tramo cocina / pilas (1.06 m) | 10 cm, liviana | WALL TO DEMOLISH (abre el paso P-1 → lavado, 1.86 m) |
| IP-P2 · remate de 0.35 m bajo IP-P3 | 10 cm, liviana | Recorte parcial (boca del pasillo limpio) |
| IP-P0a, IP-P1, IP-P2, IP-P3 | 10 cm, livianas | EXISTING WALL · se conservan: separan el flujo limpio del sucio |
| Campana existente de Marna’s 3.80 × 1.10 | Equipo existente | A RETIRAR (sellar collarines; el riser solo se reutiliza si la inspección lo aprueba) |
| Ventana de platos existente (D-DISH-old) | Antepecho/mostrador: VERIFY ON SITE | Retirar si existe, para el paso libre de 1.86 m hacia lavado |
| Vano existente pasillo limpio → lavado (D-P1-old, 0.91) | Vano en IP-P1 | P-2: puerta nueva de cierre automático (separa limpio/sucio y conserva la ruta de evacuación) |
| NW-1 · muro bajo h 1.00 + vidrio (4.87 m) | Nuevo, incombustible | NEW PROPOSED WALL |
| NW-2 · panel térmico parrilla / puerta (0.90 m) | Nuevo, incombustible, piso a campana | NEW PROPOSED WALL |
| P-1 · puerta de vaivén (vano 1.02, hoja ≈0.96, paso libre ≥0.90) con visor | Nuevo vano en NW-1 | NUEVO |
| PS-1 · puerta de servicio 0.90 en la ventana sur del ala | Sustituye parte de GL-W1 + 9.5 cm de EW-S2 | CONDICIONAL · VERIFY ON SITE (aprobación de la administración) |

## 6. Flujos

- **Limpio:** cold prep → pasillo limpio del muro oeste (1.10 m) → hot line y BBQ production.
- **BBQ:** smoker → holding → línea / pase, por el frente del muro oeste (1.00 m libre).
- **Platos:** línea → puerta P-1 (paso libre ≥0.90) → pase caliente en el extremo sur de la barra (≈ 2 m) → meseros por el pasillo central (1.27–1.28 m).
- **Sucio:** salón → P-1 → gira al sur → basureros y fregadero (≈ 1.5 m desde la puerta). La puerta P-2 de cierre automático separa el lavado del pasillo limpio y de cold prep.
- **Evacuación del ala:** cold prep → P-2 → franja libre de lavado → P-1 → salón → salida (≈ 22 m, límite 22.86 m sin rociadores): la franja de lavado se mantiene siempre libre.
- **Delivery:** pedidos empacados en el pase y entregados en la recepción de la entrada; el repartidor no entra al salón y no hay zona de espera interior.
- **Leña / cenizas / basura:** fuera de horario, por PS-1 si se aprueba o por la entrada principal; cenizas en contenedor metálico con tapa a un punto exterior acordado con la administración.

## 7. Ajustes por la revisión normativa (v3)

Una revisión preliminar (investigación + medición automática sobre el plano + verificación adversarial) contrastó el test-fit con los requisitos que revisarán el CFIA (APC), la Municipalidad de Santa Ana, Bomberos (RNPCI 2023 + NFPA 101/96/10/17A), el Ministerio de Salud (DE 37308-S, DE 43432-S) y la Ley 7600 (DE 26831-MP). Las citas provienen mayormente de fuentes secundarias (los textos oficiales no se pudieron abrir desde este entorno): el profesional responsable debe confirmarlas. Cambios incorporados:

- Extracción separada: campana 2 solo para la parrilla de combustible sólido (NFPA 96 cap. 14) con ducto vertical propio; campana 1 para la línea a gas con supresión UL 300 y corte de gas; chimenea propia del smoker.
- Gas de la red del centro comercial: llave principal fuera del local, solenoide enclavada fuera de la campana, manifold en espacio técnico de 15 cm, detector de fugas.
- Capacidad declarada 49 personas (clasificación <50 de NFPA 101): barra solo de servicio, bancas con asientos individuales, sin zona de espera interior.
- Puerta de cocina P-1 ampliada a vano 1.02 (paso libre ≥0.90, Ley 7600); P-2 de cierre automático entre pasillo limpio y lavado.
- Refrigerador y congelador corridos contra el muro sur (elimina el rincón más lejano de la salida); mesada en L en cold prep (sin rendijas).
- Lavamanos exclusivos en cold prep y en la barra; gabinete de químicos; basureros con tapa en el extremo sucio; trampa de grasa.
- Casilleros del personal fuera de las áreas de alimentos (junto a P-1); baños de clientes y personal: comunes del centro comercial (autorización escrita pendiente).
- Caja accesible a 0.80 m y dos mesas accesibles; pasillo principal 1.27 m (≥1.20).
- Extintores: clase K para freidoras y para combustible sólido, ABC en cocina, ala y salón; pulsadores de supresión junto a P-1; señalización y luces de emergencia (lámina A-104).
- Nicho de leña real y jardinera eliminados de la base detrás de la parrilla; campana existente de Marna’s a retirar.

## 8. Método

- Geometría extraída del PDF vectorial (PyMuPDF), escala verificada: 924.09 pt = 16.30 m → 1:50 exacto en A2. Tolerancia ±2 cm.
- Layout generado desde datos (tools/make_layout.py) y validado con tools/validate.py: contención en el local, colisiones, zonas libres frente a equipos, anchos libres por ruta (transformada de distancia, sillas ocupadas), cruce limpio / sucio, cobertura de campana, separación freidoras / llama y línea de vista a la parrilla. Resultado: 0 incumplimientos, 0 avisos.
- Láminas A2 1:50 (tools/plan_svg.py) y recorrido 3D (tools/build_app.py) salen del mismo archivo de datos.

## Dimensiones y condiciones a verificar en sitio

1. Altura libre bajo losa y pleno sobre cielo (se asumió 3.00 m): con la campana a ≈2.05 m quedan ≈0.35 m; si la losa está a menos de ≈3.4 m hay que reevaluar ductos, campanas y smoker.
2. Ruta real de los ductos: EXT-1 (riser existente de Marna’s, inspección con video), EXT-2 vertical nuevo sobre la parrilla y chimenea del smoker hasta cubierta (penetraciones de losa y remates).
3. Red de gas del centro comercial: tipo de gas, presión, capacidad asignada y punto de entrega (tentativo en el muro norte, X ≈ 3.0).
4. Baños comunes del centro comercial: ubicación, distancia desde el local, capacidad para el aforo (CIHSE Tabla 5.3), baño accesible, horario y autorización escrita para clientes y personal.
5. Pasillo común frente a la entrada: abierto y a nivel de calle (define que D-ENT es salida), ancho disponible si se invierte el giro de las hojas; umbral ≤0.02 m.
6. Existencia de rociadores y alarma en el centro comercial.
7. Ventana de platos existente (D-DISH-old): si tiene antepecho, retirarlo para el paso de 1.86 m.
8. Espesor y composición de la división de Marna’s (X = 6.30) y de IP-P0b: livianas y sin instalaciones embebidas.
9. Drenajes existentes de PILAS (WP1–WP3) y WP5 para la barra: diámetro, pendiente y punto para la trampa de grasa.
10. Fichas técnicas y listado (UL/ETL) de parrilla, smoker, freidoras, cocina, plancha, holding y horno ventless (UL 710B).
11. Muro oeste y envolvente de ductos junto al smoker: incombustibles y distancias según el listado del equipo.
12. Ventana sur del ala y muro EW-S2: viabilidad de PS-1 y si el pasillo sur es parte de la salida de la escalera.
13. Cuarto de basura del centro comercial y punto exterior para cenizas.
14. Tablero y acometida eléctrica existentes (capacidad para el cuadro de cargas preliminar).

## Riesgos de circulación y operación

1. Capacidad al límite: el diseño funciona como ocupación de menos de 50 personas (49 declaradas). Con 50 o más cambia a reunión pública y la salida única deja de cumplir.
2. Recorrido de evacuación máximo ≈ 22 m frente a 22.86 m sin rociadores: la franja de lavado y P-1 deben quedar siempre libres; PS-1 lo bajaría a ≈ 13 m.
3. Ductos y chimeneas: si la altura a losa no alcanza o el condominio no aprueba las penetraciones, cambian la extracción de la parrilla y el smoker (alternativa: smoker eléctrico o de pellet).
4. Parrilla argentina de fabricación local sin listado: requiere aprobación de Bomberos con memoria de materiales, o una parrilla listada.
5. P-1 es la única conexión cocina / salón y la salida del personal: se cruza con la loza sucia; circulación por la derecha y bandejero junto a la entrada al lavado.
6. Baños comunes: si Salud no acepta la batería del centro comercial, habría que construir baños propios, lo que reduce asientos y afecta la licencia de licores (mínimo usual 32 asientos).
7. Leña y carbón: solo la provisión de un día; el grueso fuera del local.
8. Espacio de terminación limitado: mesa de 140 cm con horno de mesa; mesa de prep fría de 120 × 70.
9. Sin PS-1, mercadería, leña, basura y cenizas pasan por el salón (solo fuera de horario, con limpieza posterior).

## Banderas de ingeniería

- **EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED**
- **SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED**
- **DIMENSION TO VERIFY**
- **VERIFY ON SITE**

## Cuadro de equipos

Frente × fondo × alto en metros. **\*** = DIMENSION TO VERIFY.

| Tag | Equipo | Dimensiones | Nota |
|---|---|---|---|
| H1 | Parrilla argentina | 1.50 × 0.90 × 0.90 \* | Carbón/leña. 150 cm; fondo y brasero TBV. Pieza visual principal: de frente al salón tras el vidrio. |
| H2 | Cocina 4 quemadores (gas de red) | 0.80 × 0.80 × 0.90 \* | 4 quemadores extragrandes, gas de la red del centro comercial (sin cilindros en el local); frente 80 cm TBV. |
| H3 | Plancha | 0.70 × 0.80 × 0.90 \* | Módulo 70 cm; fondo TBV. |
| H4 | Freidora 1 | 0.40 × 0.80 × 0.90 \* | Freidora independiente; huella comercial 40×80 — DIMENSION TO VERIFY. |
| H5 | Freidora 2 | 0.40 × 0.80 × 0.90 \* | Freidora independiente; huella comercial 40×80 — DIMENSION TO VERIFY. |
| HD-1 | Campana 1 · línea a gas | 2.30 × 1.15 \* | Freidoras + plancha + cocina 4Q (2.30 m): ≈2.30 × 1.15 m (voladizo frontal 0.20), supresión de químico húmedo UL 300 / NFPA 17A y corte de gas enclavado. Collarín nuevo dentro de la campana con transición al ducto existente de Marna’s si la inspección lo aprueba (VERIFY ON SITE). Panel divisorio con la campana 2 en Y 2.42. EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED. |
| HD-2 | Campana 2 · parrilla (combustible sólido) | 1.55 × 1.10 \* | Solo la parrilla (NFPA 96 cap. 14): campana, ducto, ventilador y descarga INDEPENDIENTES de la campana 1, arrestachispas antes de los filtros, filtros ≥1.22 m sobre la superficie de cocción en su posición más alta (NFPA 96 cap. 14, TBV), supresión listada para combustible sólido. ≈1.55 × 1.10 m. Ducto vertical propio a cubierta en cerramiento RF 1 h. EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED. |
| K1 | Mesa de trabajo inox | 1.40 × 0.70 × 0.90 | Apoyo / mise en place / bandejeo / terminación junto a la línea. 140 × 70 (ajustada para dejar 1.10 m frente a freidoras). |
| K2 | Horno (sobre mesa) | 0.75 × 0.70 × 1.55 \* | Horno eléctrico de convección de mesa ≈75 × 70 TBV, con campana de recirculación integrada listada UL 710B (ventless) porque queda fuera de las campanas — TO BE ENGINEERED. |
| K3 | Lavamanos cocina (recomendado) | 0.33 × 0.38 × 0.90 | Recomendado por higiene junto a la línea y a la entrada desde frío (verificar requisito Ministerio de Salud). |
| S1 | Smoker vertical (ahumador) | 1.40 × 0.75 × 1.90 \* | Gabinete ≈100 × 70 + firebox/servicio ≈40 → huella ≈140 × 75 TBV. Carga de combustible y cenizas por el frente; drenaje de grasa; chimenea propia. SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED. |
| S2 | Holding caliente | 0.60 × 0.75 × 1.00 \* | Gabinete de mantenimiento en caliente ≈60 × 75 TBV. Flujo smoker → holding → línea/pase. |
| S3 | Leña / carbón (rack metálico) | 1.00 × 0.50 × 1.20 \* | Almacén de uso diario para smoker y parrilla, separado del smoker por el holding. Distancias a combustibles TO BE VALIDATED. |
| W1 | Fregadero 2 tanques | 2.00 × 0.80 × 0.90 | ≈200 × 80 con escurridores. Sobre el drenaje existente de la pila de 3 tanques (WP1). |
| W2 | Lavamanos | 0.33 × 0.38 × 0.90 | 33 × 38. Reutiliza la zona húmeda WP2. |
| W3 | Pileta / mop sink | 0.50 × 0.60 × 0.45 | 60 × 50 en la posición exacta de la pila palo de piso existente (WP3). |
| W4 | Mesa de apoyo / escurrido | 1.87 × 0.60 × 0.90 | 187 × 60 (mesa opcional del programa) contra la división existente P1: racks limpios / apoyo. |
| W6 | Basureros con tapa (bajo escurridor sucio) | 0.80 × 0.70 × 0.70 | 3 contenedores con tapa y pedal (orgánicos / valorizables / ordinarios) bajo el escurridor norte de W1, donde entra la loza sucia. Retiro diario al cuarto de basura del centro comercial, fuera de horario (VERIFY con la administración). |
| W7 | Gabinete de químicos | 0.33 × 0.30 × 1.80 | Gabinete cerrado y rotulado para productos de limpieza, lejos de alimentos y loza limpia. |
| GT-1 | Trampa de grasa (bajo fregadero) | 0.70 × 0.70 × 0.40 \* | Interceptor de grasa accesible para limpieza antes de conectar al drenaje existente; tamaño según CIHSE — TO BE ENGINEERED. |
| W5 | Estante loza limpia | 1.20 × 0.35 × 1.80 | 120 × 35, 4 niveles. |
| A1 | Refrigerador 2 puertas | 1.45 × 0.70 × 2.00 | 145 × 70 × 200. |
| A2 | Congelador vertical | 0.75 × 0.70 × 2.00 | 75 × 70 × 200. |
| A3 | Mesa fría refrigerada | 1.80 × 0.70 × 0.90 | 180 × 70. |
| A7 | Esquinero inox (mesada en L) | 0.70 × 0.70 × 0.90 | Cierra la esquina entre A4 y A3 con mesada continua en L (sin rendijas difíciles de limpiar). |
| A8 | Lavamanos prep fría | 0.33 × 0.38 × 0.90 | Lavamanos exclusivo de la zona fría, con jabón y toallas desechables. |
| A4 | Mesa de trabajo inox (prep fría) | 1.20 × 0.70 × 0.90 | 120 × 70 (reducida de 180 para dejar libre la boca del pasillo limpio; ajuste permitido por el cliente). |
| A5 | Estantería 4 niveles | 1.70 × 0.35 × 1.80 | 170 × 35. |
| A6 | Almacén seco (estantería) | 2.80 × 0.45 × 2.00 | 280 × 45 a lo largo del pasillo limpio (muro oeste). Estantes a ≥15 cm del piso. |
| C1 | Barra de bebidas | 0.68 × 0.65 × 1.05 | Barra compacta de bebidas con enfriador bajo barra y pileta de barra (extender drenaje existente WP5 ≈1 m — VERIFY). |
| C5 | Lavamanos de barra | 0.33 × 0.38 × 0.90 | Lavamanos exclusivo del personal de barra, al fondo del pasillo de barra (tramo sin salida). |
| L1 | Casilleros del personal | 1.00 × 0.45 × 1.80 | Mueble cerrado de 10 casilleros (100 × 45 × 180) fuera de las áreas de alimentos, junto a P-1. El personal usa los servicios sanitarios comunes del centro comercial (autorización escrita: VERIFY). |
| C4 | Caja accesible (h 0.80) | 0.90 × 0.65 × 0.80 | Tramo de mostrador a 0.80 m de altura, 0.90 m de largo, con espacio libre inferior (Ley 7600, Reglamento art. 148). |
| C2 | Pase / pickup caliente | 0.65 × 0.65 × 1.05 | Repisa de pase con lámparas de calor: se carga desde el pasillo de barra (lado cocina) y se retira desde el salón. |
| C3 | POS | 0.45 × 0.45 × 0.90 |  |
| D2 | Recepción + staging / retiro delivery | 0.75 × 0.60 × 1.05 | Atril de recepción con repisa para pedidos listos: el repartidor retira en la entrada sin cruzar el salón. Los pedidos se empacan en el pase. |

---
Anteproyecto generado desde datos (data/existing.json + data/layout.json) y validado con tools/validate.py. Revisión normativa preliminar con fuentes mayormente secundarias. Debe ser verificado en sitio, ajustado y firmado por profesionales responsables del CFIA (arquitectura, mecánica, electricidad) antes de cualquier trámite u obra.
