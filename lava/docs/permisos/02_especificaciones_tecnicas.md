# 02 · Especificaciones técnicas

**LAVA – Contemporary Fire & BBQ** — local ex-Marna's, Terrazas Lindora (centro comercial abierto en régimen de condominio), Lindora, Santa Ana, San José, Costa Rica  
Anteproyecto v3.0 · 2026-09-25 · documento generado desde los datos del proyecto (`tools/permit_docs.py`)

> **ANTEPROYECTO / PRELIMINAR** — no es un documento constructivo ni una declaración de cumplimiento: todo lo aquí indicado es **a validar por el profesional responsable** (CFIA) y por las ingenierías. Las citas normativas provienen mayormente de fuentes secundarias y se marcan "verificar".

Especificación por desempeño para el anteproyecto. Los proveedores entregan fichas técnicas, listados (UL/ETL/NSF), planos de taller y memorias para aprobación del profesional responsable **antes** de fabricar o instalar. Todo lo marcado * o "DIMENSION TO VERIFY" / "VERIFY ON SITE" se confirma antes de comprar.

## 1. Generalidades

- Normativa de referencia (ediciones vigentes a confirmar por el profesional): Reglamento de Construcciones INVU 2018 y reformas; Reglamento Nacional de Protección contra Incendios (RNPCI 2023) con el paquete NFPA (101, 96, 10, 17A, 72, 54/58, 211); Código Eléctrico de Costa Rica (NEC 2020); CIHSE 2017 (CFIA); DE 37308-S (servicios de alimentación); Ley 7600 y DE 26831-MP; Código Sísmico de Costa Rica; reglamento interno del condominio.
- Coordinación con la administración: horario de obras, protección de áreas comunes, acarreos, cortes de servicios (ver 08).
- Materiales en cocina, lavado y cold prep: lisos, impermeables, lavables e incombustibles donde se indique.
- Cualquier sustitución de equipo exige volver a verificar holguras, campanas, cargas y recorridos (los datos del anteproyecto se regeneran desde `data/layout.json`).

## 2. Demoliciones y retiros

| Elemento | Alcance | Largo (m) | Descripción |
|---|---|---:|---|
| IP-KB | total | 4.14 | División liviana actual cocina/barra (10 cm, sin trama ni columnas). |
| IP-P0b | total | 1.06 | Tramo liviano cocina/pilas: abre el paso directo puerta de cocina → lavado. |
| IP-P1 | parcial | 0.10 | Recorte de 7.6 cm del extremo de IP-P1 para que P-2 tenga vano 0.99 (paso libre ≥0.90, Ley 7600). |
| IP-P2 | parcial | 0.35 | Recorte del remate liviano de IP-P2 bajo IP-P3 (35 cm) para liberar la boca del pasillo limpio. |
| EW-S2 | condicional (solo si se aprueba PS-1) | 0.13 | Solo si se aprueba PS-1: ampliar vano 9.5 cm en muro sur. |
| HOOD-EX | retiro de equipo | 3.80 | Campana existente Marna’s 3.80 × 1.10 — A RETIRAR. Sellar collarines y ductos no reutilizados con lámina de acero soldada y cierre incombustible. |
| D-DISH-old | retiro de antepecho si existe | 0.80 | Ventana platos sucios existente — dejar el paso libre hacia lavado (VERIFY ON SITE). |

- Sondeo previo de cada muro a demoler: confirmar que es liviano y que no aloja instalaciones (VERIFY ON SITE).
- No se tocan columnas, perímetro, escalera ni ductos del edificio.
- Retiro de escombros por la ruta y en el horario autorizados por la administración; protección de pisos y del pasillo común.

## 3. Particiones nuevas

**NW-1 · Muro bajo h 1.00 + vidrio** — largo 4.87 m, h 3.00 m, base maciza h 1.00 m. NEW PARTITION WALL → PROPOSED. Base sólida incombustible h≈1.00 m + vidrio hacia el salón. Base maciza (concreto o bloque) en todo el tramo de la línea. Tramo de la parrilla, de h 1.00 hasta el borde de la campana 2: vidrio vitrocerámico (≥680 °C) o pantalla inox con cámara ventilada de 25 mm; resto vidrio templado/laminado de seguridad. Especificación térmica/cortafuego TO BE ENGINEERED.

**NW-2 · Panel térmico** — largo 0.90 m, h 2.05 m. Panel lateral incombustible piso-campana entre parrilla y puerta (protección térmica y cierre lateral de campana).

- Base de NW-1: bloque de concreto relleno o concreto, incombustible, anclada a la losa (anclaje por ingeniero estructural).
- Tramo detrás de la parrilla H1 (Y 2.42…3.92) desde h 1.00 hasta la campana HD-2: vidrio vitrocerámico (≥680 °C) o pantalla inox con cámara ventilada de 25 mm; resto: vidrio templado o laminado de seguridad (zona de tránsito junto a P-1). Especificación térmica / cortafuego TO BE ENGINEERED.
- Perfilería metálica; sellos incombustibles en encuentros con losa, muros y campana.
- Nicho decorativo: Relieve decorativo de leños cerámicos / acero (incombustible), sin hueco: la base detrás de la parrilla queda maciza. Sin leña real ni jardinera. Material: incombustible.
- NW-2: acero inoxidable sobre placa cementicia con cámara de aire, de piso a campana; cierra lateralmente HD-2 y protege la ruta hacia P-1.

## 4. Acabados

Asignación por zona (lámina A-106 (Acabados y puertas); los muros MU-xx se asignan por cara de muro en la lámina):

| Zona | Piso | Zócalo | Cielo |
|---|---|---|---|
| B · HOT LINE / SHOW KITCHEN | PI-01 | ZO-01 | CI-01 |
| E · BBQ PRODUCTION | PI-01 | ZO-01 | CI-01 |
| W · WASHING | PI-02 | ZO-02 | CI-01 |
| A · COLD PREP | PI-01 | ZO-01 | CI-01 |
| C · BAR / POS | PI-03 | ZO-03 | CI-02 |
| D · DINING | PI-03 | ZO-03 | CI-02 |

| Código | Tipo | Especificación |
|---|---|---|
| PI-01 | PISO | Porcelanato técnico antideslizante 30×60 color claro, junta epóxica ≤ 3 mm; clase de resbalamiento para zona húmeda (R11 o superior — verificar ficha); pendiente 1–2 % a sifones. Bajo parrilla y smoker: sobre losa, incombustible. |
| PI-02 | PISO | Uretano-cemento antideslizante continuo (e ≥ 6 mm), sin juntas, resistente a choque térmico y a químicos de limpieza; pendiente 1–2 % a sifones. |
| PI-03 | PISO | Porcelanato rectificado gran formato 60×120 aspecto "concreto pulido", gris claro cálido, mate antideslizante (verificar ficha), junta 2 mm a tono; sin cambios de nivel (Ley 7600). |
| ZO-01 | ZÓCALO | Media caña sanitaria continua piso–muro y piso–base de equipo fijo (pieza curva de porcelanato o mortero epóxico; radio ≥ 3 cm — verificar). |
| ZO-02 | ZÓCALO | Media caña integral de uretano-cemento h 0.15, monolítica con PI-02. |
| ZO-03 | ZÓCALO | Rodapié de porcelanato PI-03 h 0.08, canto pulido, junta a tono. |
| MU-01 | MURO | Revestimiento sanitario liso color claro (porcelanato / cerámica esmaltada o panel FRP-PVC sanitario) de piso a h ≥ 2.10, recomendado hasta cielo; encima pintura epóxica lavable clara; juntas selladas, esquineros sanitarios. |
| MU-02 | MURO | Protección incombustible tras equipos de fuego: acero inoxidable sobre placa cementicia con cámara de aire, piso a campana, equipo + 0.45 a cada lado (preliminar); según listado / NFPA 96 — TO BE ENGINEERED. |
| MU-03 | MURO | Muro de listones de madera retroiluminado (LED lineal oculto), muro sur del salón; madera con retardante de llama; clase de acabado interior según NFPA 101 cap. 10 / RNPCI (verificar). |
| MU-04 | MURO | Aspecto concreto visto con textura de encofrado de tabla (micro-cemento o panel cementicio texturizado), sellador mate: muro norte de salón y barra. |
| MU-05 | MURO | Base de NW-1 cara salón (h 1.00): placa cementicia incombustible con micro-cemento gris oscuro; rótulo LAVA y relieve decorativo de leños incombustible (sin hueco) según decoración. |
| MU-06 | MURO | Pintura acrílica lavable mate gris cálido claro: resto de paramentos de salón y barra (columnas, muro de escalera, remates). |
| CI-01 | CIELO | Cielo liso lavable sin juntas abiertas: gypsum RH con pintura epóxica blanca o panel sanitario; sin cielo modular poroso; incombustible junto a campanas y ductos (holguras NFPA 96 — verificar). Altura VERIFY ON SITE. |
| CI-02 | CIELO | Cielo expuesto: losa, vigas, ductos, bandejas y tuberías pintados negro mate (near-black); luminarias colgantes. Altura libre supuesta 3.00 — VERIFY ON SITE. |
| FD | SIFÓN | Coladera / sifón de piso FD-n con rejilla inox y trampa (propuesto, mismo trazado que M-101): ubicación, diámetro y pendientes por ingeniería sanitaria (CIHSE) — VERIFY. Existentes WP: reutilizar si el levantamiento lo confirma. |
| TR | TRANSICIÓN | Cambio PI-01 / PI-03 en P-1 a nivel: perfil inox biselado ≤ 0.02 (art. 142 DE 26831-MP — verificar). |

- Acabados interiores del salón (listones de madera MU-03, tapicería de bancas): clase A o B según NFPA 101 cap. 10 / RNPCI (ASTM E84 / UL 723: propagación de llama ≤75, humo ≤450) o tratamiento ignífugo certificado — ficha obligatoria.
- Cocina, lavado y cold prep: sin madera ni materiales porosos; uniones piso–muro sanitarias; colores claros.

## 5. Cielos

| Tipo | Zonas | Descripción | Nivel |
|---|---|---|---|
| CT-1 | D, C | Estructura expuesta pintada negro mate. Sin cielo suspendido: losa, vigas e instalaciones vistas (ductos, bandejas, rieles) pintadas negro mate (como el render). Pintura de baja emisión; instalaciones ordenadas y soportadas a la estructura. | +3.00 fondo de estructura (supuesto) |
| CT-2 | B, E | Cielo liso lavable INCOMBUSTIBLE. Fibrocemento o lámina metálica con pintura epóxica/sanitaria, juntas selladas, color claro. Sello incombustible alrededor de campanas, ductos y chimenea (NFPA 96: 0 mm a incombustibles — verificar). | +3.00 (supuesto) · nunca < 2.40 |
| CT-3 | W, A | Cielo liso lavable resistente a humedad. Panel sanitario PVC / fibra de vidrio o gypsum RH con pintura epóxica, color claro, sin juntas abiertas ni superficies que acumulen polvo o condensación (Salud DE 37308-S — artículo a confirmar). | +3.00 (supuesto) · nunca < 2.40 |

Altura mínima de piso a cielo 2.40 m (INVU, artículo por confirmar). Altura existente VERIFY ON SITE.

## 6. Puertas, ventanas y herrajes

| Elemento | Tipo | Especificación |
|---|---|---|
| D-ENT (existente) | doble 2.00 m, hojas 0.97 | Salida principal al pasillo abierto del centro comercial. Hojas hoy hacia adentro (permitido con <50 personas). Recomendado invertir el giro hacia afuera sin invadir el pasillo común — VERIFY con la administración. Herraje de palanca o barra, sin llave desde adentro durante la operación; umbral ≤0.02 m; rótulo SALIDA iluminado encima y rótulo CAPACIDAD MÁXIMA 49. |
| P-1 | puerta de vaivén, vano 1.02 m | Puerta de cocina de vaivén: vano 1.02, hoja ≈0.96 con visor, paso libre ≥0.90 (Ley 7600 art. 140). Única conexión cocina/salón: entrada de loza sucia y salida de platos; circulación por la derecha. Siempre libre (ruta de evacuación del personal). Visor de vidrio de seguridad, placa de patada inox, bisagras de doble acción; marco metálico delgado para conservar el paso libre. |
| P-2 | puerta abatible, vano 0.99 m | Puerta de cierre automático en el vano existente pasillo limpio → lavado (separa limpio/sucio y conserva la ruta de evacuación del ala). Cierrapuertas; sin cerradura con llave; placa de patada inox. |
| PS-1 | puerta de servicio, vano 0.90 m (CONDICIONAL) | PUERTA DE SERVICIO CONDICIONAL: sustituye parte de la ventana sur existente (hacia pasillo del edificio). Requiere aprobación de la administración y revisión estructural. Si el pasillo sur es parte de la salida de la escalera del edificio, puede exigirse puerta cortafuego autocerrante — VERIFY ON SITE. Si se aprueba: giro hacia afuera, barra antipánico, cierre automático; resistencia al fuego si el pasillo sur es parte de la salida de la escalera; dintel estructural; burlete y cedazo. |
| GL-F1 (existente) | vitrina | Vitrina fachada (1.34) |
| GL-F2 (existente) | vitrina | Vitrina fachada (1.34) |
| GL-W1 (existente) | ventana | Ventana 2.00 m en muro sur del ala. Da hacia área/pasillo sur (puerta de escalera abre ahí). VERIFY que hay detrás. Se sustituye en parte por PS-1 si se aprueba. |

## 7. Equipos de cocina y mobiliario técnico

Dimensiones frente × fondo × alto (m). * = DIMENSION TO VERIFY. Energía y potencias típicas (*) de `mech_calcs.json` / `elec_loads.json`: reemplazar por las fichas técnicas.

| Tag | Equipo | Medidas | Energía | Requisito de desempeño |
|---|---|---|---|---|
| H1 | Parrilla argentina | 1.50 × 0.90 × 0.90 \* | carbón / leña | Parrilla de carbón/leña de acero, listada (UL/ETL) o con memoria de materiales aceptada por Bomberos; hogar ≤0.14 m³ o manguera fija (NFPA 96 cap. 14, verificar); base y respaldo incombustibles; bandeja de cenizas metálica; holguras según listado. |
| H2 | Cocina 4 quemadores (gas de red) | 0.80 × 0.80 × 0.90 \* | gas de red ≈35.2 kW\* | Cocina comercial de 4 quemadores a gas, listada para el tipo de gas de la red (GN o GLP — VERIFY), válvulas de seguridad con termopar, conexión con conector listado ≤1.5 m y cable de restricción. |
| H3 | Plancha | 0.70 × 0.80 × 0.90 \* | gas de red ≈14.7 kW\* | Plancha a gas listada, termostática, sin llama expuesta (condición de la separación freidoras–llama abierta). |
| H4 | Freidora 1 | 0.40 × 0.80 × 0.90 \* | gas de red ≈26.4 kW\*; 120 V · 0.24 kVA\* (circ. 1) | Freidora a gas listada (UL 197 / NSF 4 o equivalente), termostato + límite de alta temperatura independiente; ≤36 kg de aceite; encendido 120 V vía contactor KS-1 (corte al disparar la supresión). |
| H5 | Freidora 2 | 0.40 × 0.80 × 0.90 \* | gas de red ≈26.4 kW\*; 120 V · 0.24 kVA\* (circ. 1) | Freidora a gas listada (UL 197 / NSF 4 o equivalente), termostato + límite de alta temperatura independiente; ≤36 kg de aceite; encendido 120 V vía contactor KS-1 (corte al disparar la supresión). |
| HD-1 | Campana 1 · línea a gas | 2.30 × 1.15 \* | — | Campana listada UL 710 o fabricada en acero ≥1.09 mm (18 MSG) / inox ≥0.94 mm (20 MSG) con uniones soldadas estancas (NFPA 96 cap. 5); filtros listados UL 1046; luminaria listada. EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED. |
| HD-2 | Campana 2 · parrilla (combustible sólido) | 1.55 × 1.10 \* | — | Campana listada UL 710 o fabricada en acero ≥1.09 mm (18 MSG) / inox ≥0.94 mm (20 MSG) con uniones soldadas estancas (NFPA 96 cap. 5); filtros listados UL 1046; luminaria listada. EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED. |
| K1 | Mesa de trabajo inox | 1.40 × 0.70 × 0.90 | 120 V · 0.36 kVA\* (circ. 33) | Mesa de acero inoxidable AISI 304, NSF 2, entrepaño inferior, patas regulables, uniones selladas. |
| K2 | Horno (sobre mesa) | 0.75 × 0.70 × 1.55 \* | 208 V · 6.00 kVA\* (circ. 3-5) | Horno eléctrico de convección de mesa con campana de recirculación integrada listada UL 710B (ventless) y enclavamiento propio; 208 V (VERIFY tensión disponible). |
| K3 | Lavamanos cocina | 0.33 × 0.38 × 0.90 | — | Lavamanos exclusivo para manos, inox, con agua fría y caliente mezclada (≈43 °C), grifo de accionamiento no manual recomendado, jabón líquido, toallas desechables y basurero de pedal (DE 37308-S, verificar). |
| S1 | Smoker vertical (ahumador) | 1.40 × 0.75 × 1.90 \* | carbón / leña; 120 V · 0.72 kVA\* (circ. 2) | Smoker vertical listado para uso comercial en interior (UL/ETL) con chimenea propia (NFPA 211) o campana independiente; piso incombustible; holguras según listado. SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED. Alternativa: smoker eléctrico o de pellet listado. |
| S2 | Holding caliente | 0.60 × 0.75 × 1.00 \* | 120 V · 1.50 kVA\* (circ. 7) | Gabinete de mantenimiento en caliente eléctrico, NSF 4, 120 V. |
| S3 | Leña / carbón (rack metálico) | 1.00 × 0.50 × 1.20 \* | — | Gabinete metálico cerrado para la provisión de un día, nada encima, ≥0.915 m de los aparatos de combustible sólido (NFPA 96 cap. 14, verificar). |
| W1 | Fregadero 2 tanques | 2.00 × 0.80 × 0.90 | — | Fregadero de 2 tanques inox AISI 304 NSF 2 con escurridores y ducha de prelavado; agua fría y caliente; descarga a GT-1. |
| W2 | Lavamanos | 0.33 × 0.38 × 0.90 | — | Lavamanos exclusivo para manos, inox, con agua fría y caliente mezclada (≈43 °C), grifo de accionamiento no manual recomendado, jabón líquido, toallas desechables y basurero de pedal (DE 37308-S, verificar). |
| W3 | Pileta / mop sink | 0.50 × 0.60 × 0.45 | — | Pileta de aseo de piso con llave de manguera y rompevacío; recibe la descarga T&P del termotanque (indirecta). |
| W4 | Mesa de apoyo / escurrido | 1.87 × 0.60 × 0.90 | 120 V · 0.36 kVA\* (circ. 33) | Mesa inox AISI 304 NSF 2 para racks limpios. |
| W6 | Basureros con tapa (bajo escurridor sucio) | 0.80 × 0.70 × 0.70 | — | 3 contenedores con tapa y pedal (orgánicos / valorizables / ordinarios) — separación en la fuente (Ley 8839, verificar). |
| W7 | Gabinete de químicos | 0.33 × 0.30 × 1.80 | — | Gabinete cerrado y rotulado para químicos, con bandeja antiderrame, separado de alimentos y loza limpia. |
| GT-1 | Trampa de grasa (bajo fregadero) | 0.70 × 0.70 × 0.40 \* | — | Interceptor de grasa hidromecánico accesible, tapa hermética; caudal según 04 (PDI G-101 referencia; CIHSE rige). |
| W5 | Estante loza limpia | 1.20 × 0.35 × 1.80 | — | Estantería inox o epóxica NSF, 4 niveles. |
| A1 | Refrigerador 2 puertas | 1.45 × 0.70 × 2.00 | 120 V · 0.84 kVA\* (circ. 8) | Refrigerador comercial NSF 7 con termómetro visible; 120 V. |
| A2 | Congelador vertical | 0.75 × 0.70 × 2.00 | 120 V · 0.72 kVA\* (circ. 4) | Congelador comercial NSF 7 con termómetro visible; 120 V. |
| A3 | Mesa fría refrigerada | 1.80 × 0.70 × 0.90 | 120 V · 0.48 kVA\* (circ. 6) | Mesa refrigerada NSF 7; 120 V. |
| A7 | Esquinero inox (mesada en L) | 0.70 × 0.70 × 0.90 | — | Esquinero inox AISI 304 que cierra la mesada en L sin rendijas. |
| A8 | Lavamanos prep fría | 0.33 × 0.38 × 0.90 | — | Lavamanos exclusivo para manos, inox, con agua fría y caliente mezclada (≈43 °C), grifo de accionamiento no manual recomendado, jabón líquido, toallas desechables y basurero de pedal (DE 37308-S, verificar). |
| A4 | Mesa de trabajo inox (prep fría) | 1.20 × 0.70 × 0.90 | 120 V · 0.18 kVA\* (circ. 34) | Mesa de trabajo inox AISI 304 NSF 2. |
| A5 | Estantería 4 niveles | 1.70 × 0.35 × 1.80 | — | Estantería inox o epóxica NSF, primer nivel ≥0.15 m del piso. |
| A6 | Almacén seco (estantería) | 2.80 × 0.45 × 2.00 | — | Estantería de almacén seco NSF, primer nivel ≥0.15 m del piso, separada de químicos. |
| C1 | Barra de bebidas | 0.68 × 0.65 × 1.05 | 120 V · 0.60 kVA\* (circ. 11); 120 V · 1.50 kVA\* (circ. 9) | Barra de bebidas con enfriador bajo barra (NSF 7) y pileta de barra PB-1 con agua fría y caliente (CA-2). |
| C5 | Lavamanos de barra | 0.33 × 0.38 × 0.90 | — | Lavamanos exclusivo para manos, inox, con agua fría y caliente mezclada (≈43 °C), grifo de accionamiento no manual recomendado, jabón líquido, toallas desechables y basurero de pedal (DE 37308-S, verificar). |
| L1 | Casilleros del personal | 1.00 × 0.45 × 1.80 | — | Casilleros metálicos ventilados, fuera de áreas de alimentos. |
| C4 | Caja accesible (h 0.80) | 0.90 × 0.65 × 0.80 | — | Tramo de mostrador accesible h 0.80 × 0.90 m con espacio libre inferior (Ley 7600, DE 26831-MP art. 148, verificar). |
| C2 | Pase / pickup caliente | 0.65 × 0.65 × 1.05 | 120 V · 0.50 kVA\* (circ. 13) | Repisa de pase con lámparas de calor (L-7), 120 V. |
| C3 | POS | 0.45 × 0.45 × 0.90 | 120 V · 0.50 kVA\* (circ. 40) | POS e impresora de comandas en circuito dedicado. |
| D2 | Recepción + staging / retiro delivery | 0.75 × 0.60 × 1.05 | 120 V · 0.54 kVA\* (circ. 37) | Atril de recepción con repisa para pedidos listos. |

## 8. Campanas, ductos y extracción (NFPA 96)

**EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED.** Valores de caudal y ducto: ver 04 (PRELIMINAR).

| Campana | Descripción | Largo × fondo (m) | Equipos bajo campana | Sistema | Caudal / ducto | Nota |
|---|---|---|---|---|---|---|
| HD-1 | Campana 1 · línea a gas | 2.30 × 1.15 | H2, H3, H4, H5 | EXT-1 | 1068 L/s · ducto 450×350 mm | Freidoras + plancha + cocina 4Q (2.30 m): ≈2.30 × 1.15 m (voladizo frontal 0.20), supresión de químico húmedo UL 300 / NFPA 17A y corte de gas enclavado. Collarín nuevo dentro de la campana con transición al ducto existente de Marna’s si la inspección lo aprueba (VERIFY ON SITE). Panel divisorio con la campana 2 en Y 2.42. EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED. |
| HD-2 | Campana 2 · parrilla (combustible sólido) | 1.55 × 1.10 | H1 | EXT-2 | 1320 L/s · ducto 450×400 mm | Solo la parrilla (NFPA 96 cap. 14): campana, ducto, ventilador y descarga INDEPENDIENTES de la campana 1, arrestachispas antes de los filtros, filtros ≥1.22 m sobre la superficie de cocción en su posición más alta (NFPA 96 cap. 14, TBV), supresión listada para combustible sólido. ≈1.55 × 1.10 m. Ducto vertical propio a cubierta en cerramiento RF 1 h. EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED. |

- Dos sistemas **independientes**: HD-1 (gas) y HD-2 (parrilla de combustible sólido): campana, ducto, ventilador y descarga propios; no se unen en ningún punto (NFPA 96 cap. 14, verificar numeración de la edición adoptada).
- Borde inferior de campanas ≈2.05 m (altura del panel NW-2) — TBV con la altura libre real; HD-2: filtros ≥1.22 m sobre la superficie de cocción (NFPA 96 cap. 14, TBV) y arrestachispas antes de los filtros.
- Ducto de grasa: acero al carbono ≥1.37 mm (16 MSG) o inox ≥1.09 mm (18 MSG), soldadura continua estanca, sin sifones, registros de limpieza en cada cambio de dirección; cerramiento resistente al fuego 1 h (<4 pisos) o envolvente listada; holguras 457 / 76 / 0 mm a combustibles / combustibilidad limitada / incombustibles.
- Velocidad en ducto ≥2.54 m/s (NFPA 96 §8.2, verificar); ventiladores de descarga vertical en cubierta con bisagra de limpieza y drenaje de grasa.
- Descarga en cubierta: ≥3 m horizontales a tomas de aire, linderos y edificios vecinos; ≥1.5 m a estructuras combustibles (NFPA 96 §7.8, cifras por confirmar); remate de la chimenea del smoker según INVU (≥5 m sobre edificios en 25 m, por verificar) — aprobación del condominio.
- EXT-1: Collarín nuevo en HD-1 con transición al riser existente de Marna’s (X 4.10–4.50, Y 0.47–0.87) solo si la inspección lo aprueba; si no, ducto nuevo acero 16 MSG soldado en cerramiento RF — VERIFY ON SITE
- EXT-2: Ducto vertical propio sobre la parrilla hasta cubierta, en cerramiento RF 1 h nuevo (penetración de losa: revisión estructural + aprobación del condominio)
- EXT-3 (smoker): Chimenea listada vertical (NFPA 211) sobre el smoker hasta cubierta, con arrestachispas — VERIFY. Alternativa: smoker eléctrico o de pellet listado. SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED.
- Horno K2 fuera de campanas: solo con recirculación integrada listada UL 710B.
- Limpieza: extracción de combustible sólido mensual; demás según uso (NFPA 96, tabla de frecuencias; verificar).

## 9. Supresión de incendios y extintores

- HD-1: sistema fijo de químico húmedo listado **UL 300** (NFPA 17A) que cubre equipos, pleno y ducto; al disparar cierra la válvula de gas VS (rearme manual) y abre el contactor KS-1 de los equipos eléctricos protegidos.
- HD-2: sistema listado para combustible sólido (agente y boquillas según el listado); arrestachispas; manguera fija si el hogar de la parrilla supera 0.14 m³ (NFPA 96 cap. 14, verificar).
- Pulsadores manuales PM-1, PM-2: Pulsadores manuales de supresión de la campana 1 (PM-1) y de la campana 2 (PM-2), con tapa e identificados, en la cara salón de NW-1 junto al marco norte de P-1: sobre la ruta de salida del personal (NFPA 96 §10.5.1) y separados del fuego por NW-1/NW-2 incombustibles. La referencia de 3–6 m de la campana (IFC / listado) no se alcanza en este local: validar con el listado del sistema y Bomberos — VERIFY. Altura 1.07–1.22 m. Distancia medida en A-104 a las campanas: HD-1 1.45 m, HD-2 0.20 m — la referencia de 3–6 m (IFC; NFPA 17A / 96 según edición) no se alcanza: validar la ubicación con el listado del sistema y Bomberos (VERIFICAR).
- Diseño, instalación, prueba de aceptación y certificado por proveedor autorizado; mantenimiento semestral (NFPA 17A); señal a la alarma del centro comercial si existe (VERIFY ON SITE).

| Extintor | Tipo | Ubicación (zona) | Nota |
|---|---|---|---|
| EX-K | Clase K 6 L | E · BBQ PRODUCTION | Freidoras a ≤9.15 m; rótulo: accionar primero el sistema fijo |
| EX-K2 | Clase K 6 L (combustible sólido) | E · BBQ PRODUCTION | Smoker y parrilla a ≤6 m (NFPA 96 cap. 14: 2-A de agua pulverizada o químico húmedo K 6 L). Si un hogar supera 0.14 m³: manguera fija de agua. |
| EX-B1 | ABC 2-A:10-B:C | B · HOT LINE / SHOW KITCHEN | Cocina caliente: equipos a gas (10-B a ≤9.15 m de las freidoras) |
| EX-A2 | ABC 2-A:10-B:C | D · DINING | Salón, junto a la salida |
| EX-A3 | ABC 2-A:10-B:C | A · COLD PREP | Ala de servicio (lavado / cold prep) |

Montaje: parte superior a ≤1.53 m y parte inferior ≥0.10 m sobre el piso; rótulo junto al clase K: "accionar primero el sistema fijo" (NFPA 10, verificar).

## 10. Gas (red del centro comercial)

- Fuente: Red de gas del centro comercial (tipo de gas y presión: VERIFY). Sin cilindros en el local.
- Acometida: Punto de acometida tentativo en el muro norte — VERIFY ON SITE con la administración
- Llave de corte principal FUERA del local, en la acometida, rotulada. Válvula solenoide/mecánica enclavada con la supresión de la campana 1 (rearme manual) en el muro norte, fuera de la proyección de la campana. Manifold en el espacio técnico de 0.15 m detrás de la línea, válvula de servicio por equipo, conectores listados ≤1.5 m con cable de restricción. Detector según tipo de gas (GLP a ≤0.30 m del piso).
- Consumo típico total ≈102.7 kW (350 000 BTU/h); tubería principal: 1" (25 mm) hierro negro cédula 40 si es GLP; 1-1/4" (32 mm) si es gas natural — PRELIMINAR — TO BE ENGINEERED
- Tubería rígida de hierro negro cédula 40 roscada/soldada, soportada y protegida, pintada amarillo; no atravesar sectores internos del edificio sin aprobación de Bomberos (Disposiciones GLP 2023 si la red es de GLP, verificar); prueba de hermeticidad antes de conectar.
- Detector de gas DG-1 según tipo de gas (GLP a ≤0.30 m del piso; GN cerca del cielo), con alarma y corte de VS.
- Informe técnico de la instalación de gas por profesional o inspector acreditado para el Permiso Sanitario de Funcionamiento (06 paso 9).

## 11. Hidrosanitario y trampa de grasa (CIHSE 2017)

| Tag | Aparato | AF | AC | Desagüe | A |
|---|---|---|---|---|---|
| W1 | Fregadero 2 tanques + ducha de prelavado | 1/2" (12) | 1/2" (12) | 2" (50) | GT-1 → WP1 |
| W2 | Lavamanos del lavado | 1/2" (12) | 1/2" (VMT) | 1-1/2" (38) | WP2 |
| K3 | Lavamanos de cocina (exclusivo manos) | 1/2" (12) | 1/2" (VMT) | 1-1/2" → 2" bajo piso | WP4 |
| A8 | Lavamanos de la zona fría | 1/2" (12) | 1/2" (VMT) | 1-1/2" → 2" bajo piso | WP4 |
| W3 | Pileta de aseo (mop sink) | 1/2" (12) | 1/2" (12) | 3" (75) | WP3 |
| PB-1 | Pileta de barra (en la barra C1) | 1/2" (desde WP5) | 1/2" (CA-2) | 1-1/2" (38) | WP5 |
| C5 | Lavamanos del personal de barra | 1/2" (12) | 1/2" (CA-2) | 1-1/2" (38) | WP5 |
| CA-1 | Termotanque eléctrico ≈150 L / 6 kW | 3/4" entrada | 3/4" salida | T&P 3/4" | pileta de aseo (indir.) |
| CA-2 | Calentador bajo barra ≈15 L / 1.5 kW | 1/2" (12) | 1/2" (12) | T&P 1/2" | PB-1 (indirecta) |
| LL-1 | Llave de manguera con rompevacío + carrete | 3/4" (18) | — | — | FD-1 (lavado de pisos) |
| FD-1 | Coladera de piso con canastilla · cocina (zonas B + E) | — | — | 2" (50) | GT-1 → WP1 |
| FD-2 | Coladera de piso con canastilla · lavado (zona W) | — | — | 2" (50) | GT-1 → WP1 |
| FD-3 | Coladera de piso con canastilla · cold prep (zona A) | — | — | 2" (50) | WP3 |
| GT-1 | Trampa / interceptor de grasa bajo el fregadero | — | — | entrada 2" · salida 3" (75) | WP1 |
| WP6 | Punto húmedo existente sin uso | tapón | tapón | tapón registrable | — |

- Tuberías de agua: PVC SDR/CPVC o PEX para agua caliente según diseño; válvulas de corte por zona; rompevacíos en llaves de manguera.
- Desagües: PVC sanitario con pendientes según CIHSE; ventilación de cada sifón; registros accesibles; la grasa pasa por GT-1 antes de WP1.
- Coladeras de piso con canastilla y sello hidráulico en cocina, lavado y cold prep (pendiente 1–2 % a coladeras, verificar).
- Almacenamiento ≥60 °C; lavamanos con válvula mezcladora termostática (≈43 °C) — criterio usual, verificar CIHSE / Salud. Circuitos eléctricos de CA-1 y CA-2 en las láminas eléctricas. PRELIMINAR — TO BE ENGINEERED
- Tipo de losa (sobre terreno o entrepiso) y destino de los desagües existentes: VERIFY ON SITE.

## 12. Aire de reposición, ventilación y climatización

- Aire de reposición ≈80–90 % del caudal extraído, entregado sin perturbar la captura de las campanas; suministro positivo para combustible sólido — TO BE ENGINEERED.
- Caudal de diseño AR-1 ≈2030 L/s; ducto 700×500 mm. Difusores: Descarga a baja velocidad (≈0.5 m/s o menos cerca de las campanas; guías CKV / ASHRAE) para no perturbar la captura: difusores perforados o pleno perimetral — TO BE ENGINEERED
- Enclavamiento: AR-1 arranca con EXT-1 o EXT-2; con brasas en H1/S1 la extracción de sólido no se apaga (selector con llave).
- Anclaje sísmico (Código Sísmico de CR) de campanas, ductos, gas y equipos altos (A1, A2, S1).
- Ventilación / aire acondicionado del salón y de la cocina: el local solo tiene fachada al este — TO BE ENGINEERED.
- Aire de combustión y monitoreo de CO para la parrilla y el smoker.

## 13. Electricidad e iluminación (NEC 2020)

- Sistema supuesto: 120/208 V 3F 4H + T (VERIFY) · alternativa 120/240 V 1F — VERIFY ON SITE con la administración / distribuidora.
- Tablero TE-1: principal 125 A, barra ≥150 A, 54 espacios (43 usados); espacio de trabajo 0.90 × 1.02 × 2.00 m libre (NEC 2020 110.26(A): fondo 0.90 m (0–150 V a tierra, condición 1) · ancho ≥0.762 m o el del equipo · alto 2.0 m; 110.26(E) espacio dedicado).
- GFCI en cocina, lavado, cold prep y barra (NEC 210.8(B)); conductores de cobre THHN/THWN; canalización metálica en cocina.
- Circuitos exclusivos para ventiladores, supresión/control (CC-1), rótulo exterior, POS/TI; luminarias de emergencia autónomas en el circuito de alumbrado de su área.
- Enclavamientos (matriz en 04 y E-101): supresión → VS cierra y KS-1 abre; detector de gas → VS cierra; falta de energía → VS cierra (N.C.).

| Tipo | Luminaria | Especificación | Montaje | Cant. |
|---|---|---|---|---:|
| L-1 | Proyector LED orientable sobre riel negro | ≈10 W · 2700 K · IRC ≥90 · dimerizable | Riel adosado a estructura | 18 |
| L-2 | Downlight cilíndrico de superficie negro Ø≈0.10 | ≈12 W · 2700 K · UGR < 19 · dimerizable | Adosado a estructura | 9 |
| L-3 | Colgante domo negro Ø0.24 (decor) | LED ≈8 W · 2700 K · dimerizable | Suspendido | 3 |
| L-4 | Aplique de pared cono negro (decor) | LED ≈6 W · 2700 K | Muro norte | 3 |
| L-5 | Tira LED lineal (listones / relieve de leños) | ≈10 W/m · 2700 K · perfil con difusor | Oculta en mobiliario | 2 |
| L-6 | Rótulo LAVA con halo retroiluminado | LED ámbar · fuente remota | Faja sobre vidrio | 1 |
| L-7 | Lámparas de calor del pase C2 (equipo) | Según proveedor del pase | Sobre repisa de pase |  |
| L-8 | Hermética LED IP65 lineal 1.20 m | ≈4000 lm · 4000 K · difusor PC inastillable | Adosada a cielo CT-2 / CT-3 | 17 |
| L-9 | Luminaria integrada en campana (listada) | Suministro del fabricante de HD-1 / HD-2 | Dentro de la campana | 4 |
| EM | Luz de emergencia autónoma (ver A-104) | ≥1.5 h · ≥10.8 lx prom. / ≥1.1 lx mín. | Muro o cielo · h ≈2.40 | 9 |
| RS | Rótulo SALIDA iluminado (ver A-104) | Autónomo ≥1.5 h · direccional | Sobre puerta / colgante | 6 |

Cantidades de A-201 (luminarias lineales/tiras contadas por tramo). Niveles lumínicos y marcas: referencia, a validar.

## 14. Detección, alarma y enclavamientos

- 5 detectores (1 térmico(s) en cocina caliente / BBQ, 4 de humo). Detección e integración a la alarma del centro comercial si existe (VERIFY). En cocina caliente: detector térmico, no de humo. Monitoreo de CO recomendado por los dos aparatos de combustible sólido.
- Monitor de CO DCO-1 en BBQ production (dos aparatos de combustible sólido).
- NFPA 101 no exige rociadores con <50 personas. Si el centro comercial tiene red o alarma, integrarse según NFPA 13/72 — VERIFY con la administración.
- Integración con la alarma del centro comercial (NFPA 72) y señal de disparo de supresión: VERIFY ON SITE.

## 15. Señalización

| Rótulo | Texto | Zona | Ubicación |
|---|---|---|---|
| RS-1 | SALIDA | D · DINING | Sobre la puerta principal, iluminado |
| RS-2 | SALIDA → | D · DINING | Direccional colgante en el salón (visible desde P-1 y la barra) |
| RS-3 | SALIDA → | B · HOT LINE / SHOW KITCHEN | Cara de cocina de la puerta P-1 |
| RS-4 | SALIDA ↑ | A · COLD PREP | Pasillo limpio del ala, hacia la cocina |
| RS-5 | SALIDA ↑ | A · COLD PREP | Boca del pasillo limpio desde cold prep |
| RS-6 | SALIDA ↑ | W · WASHING | Lavado, sobre la franja de evacuación hacia P-1 |

- Rótulo "CAPACIDAD MÁXIMA 49 PERSONAS" junto a D-ENT.
- Rótulos de extintores, del clase K ("accionar primero el sistema fijo"), de pulsadores de supresión y de la llave de gas exterior.
- Rótulos "PROHIBIDO FUMAR" en D-ENT y en el salón; "SOLO PERSONAL AUTORIZADO" en P-1; símbolo internacional de accesibilidad en caja y mesas accesibles.
- Rótulo exterior y rótulo LAVA retroiluminado: permiso municipal y aprobación del condominio (06 paso 13).
- Rótulos de salida iluminados, autonomía ≥1.5 h (NFPA 101 7.10, verificar).

## 16. Accesibilidad (Ley 7600 · DE 26831-MP)

- Ruta accesible continua D-ENT → caja accesible → mesas accesibles, sin desniveles; umbrales ≤0.02 m (art. 142, verificar).
- Puertas con paso libre ≥0.90 m y 0.45 m libres del lado opuesto a las bisagras (art. 140, verificar); herrajes de palanca.
- Pasillos: salón ≥1.20 m (medido 1.27 m); interiores ≥0.90 m (art. 141, verificar).
- Mostrador de caja h 0.80 m con espacio libre inferior para rodillas (art. 148, verificar); mesas accesibles con aproximación frontal 0.80 × 1.20 m (criterio de referencia, sin artículo costarricense confirmado).
- Detalles y áreas de giro Ø1.50 en A-105 (Accesibilidad (Ley 7600)).

## 17. Anclaje sísmico, soportes y cubierta

- Anclaje sísmico (Código Sísmico de CR) de campanas, ductos, tubería de gas, termotanque y equipos altos (refrigerador, congelador, smoker, estanterías).
- Colgado de campanas y ductos desde la losa; bases y soportes de ventiladores en cubierta: diseño por ingeniero estructural.
- Penetraciones de losa y cubierta (EXT-2, EXT-3, AR-1 y, si no se reutiliza el riser existente, EXT-1): revisión estructural, sellos cortafuego y aprobación del condominio.

## 18. Pruebas, puesta en marcha y entrega

- Prueba de hermeticidad de la tubería de gas y certificado; informe técnico de la instalación de gas.
- Prueba de aceptación de los sistemas de supresión (incluye corte de gas y energía) y certificado del proveedor.
- Balance de caudales de extracción y reposición; medición de presión cocina/salón.
- Pruebas eléctricas: aislamiento, continuidad de tierra, disparo de GFCI, autonomía de luces de emergencia.
- Prueba de estanqueidad de desagües; limpieza y desinfección final.
- Planos conforme a obra, manuales, garantías y programa de mantenimiento (limpieza de ductos, supresión, trampa de grasa).

Banderas del anteproyecto (se mantienen literalmente en inglés en láminas y documentos):

- **EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED**
- **SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED**
- **DIMENSION TO VERIFY**
- **VERIFY ON SITE**
