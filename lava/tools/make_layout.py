"""Generate data/layout.json for the LAVA test-fit (v2, client-fixed operational zoning).

Fixed by the client (do not reinterpret):
  * HOT LINE along the new kitchen/dining partition (on the right when entering from the salon):
    parrilla -> cocina 4Q -> plancha -> freidora 1 -> freidora 2 (from the door northwards).
  * Mesa de trabajo + horno on the NORTH wall, next to the end of the line (fryers).
  * BBQ PRODUCTION on the WEST (back) wall: smoker + holding (+ fuel).
  * WASHING stays where Marna's had PILAS (existing drains).
  * COLD PREP + refrigeration + storage in the former PASTELERIA.
Coordinates in metres (see docs/LAYOUT_SCHEMA.md).
Usage: python3 tools/make_layout.py  -> writes data/layout.json
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- key geometry
P0 = 4.325            # new partition, kitchen face (old partition kitchen face = 6.298)
P1 = P0 + 0.15        # new partition, dining face
YN = 0.116            # north wall inner face
YS = 4.986            # south edge of the main strip
DOOR = (3.966, 4.986) # kitchen door P-1: full 1.02 m bay between NW-2 and the south wall (leaf ≈0.96, clear ≥0.90)
LINE_D = 0.80         # depth of range / plancha / fryers (TBV)
TECH = 0.15           # technical gap behind the gas line (manifold, connectors, service valves)
PARR_D = 0.90         # depth of parrilla (TBV)

L = {
    'meta': {
        'name': 'LAVA anteproyecto v3 · zonificación del cliente + ajustes normativos',
        'strategy': 'Hot line sobre la división con el salón; BBQ (smoker + holding) al fondo; lavado en PILAS; cold prep en PASTELERÍA; '
                    'extracción independiente para combustible sólido; gas de la red del centro comercial',
        'version': '3.0',
        'date': '2026-09-25',
    },
    'demolish': [
        {'id': 'IP-KB', 'note': 'División liviana actual cocina/barra (10 cm, sin trama ni columnas).'},
        {'id': 'IP-P0b', 'note': 'Tramo liviano cocina/pilas: abre el paso directo puerta de cocina → lavado.'},
    ],
    'new_walls': [], 'new_openings': [], 'zones': [], 'equipment': [], 'tables': [], 'chairs': [],
    'banquettes': [], 'points': {}, 'routes': [], 'checks': [], 'decor': [], 'tour': [], 'notes': [],
    'dims': [], 'dims_demo': [], 'sheet_notes': [], 'structure_notes': [], 'flow_notes': [],
}
E = L['equipment']


def eq(id_, key, label, cat, rect, front=None, clear=0.0, h=0.9, tbv=False, **kw):
    d = {'id': id_, 'tag': id_, 'key': key, 'label': label, 'cat': cat, 'rect': [round(v, 3) for v in rect],
         'front': front, 'clear': clear, 'h': h, 'tbv': tbv}
    d.update(kw)
    E.append(d)
    return d


# ---------------------------------------------------------------- walls / openings
L['new_walls'] += [
    {'id': 'NW-1', 'rect': [P0, YN, P1, YS], 'type': 'glass_partition', 'role': 'kitchen_dining_partition',
     'h': 3.0, 'base_h': 1.0, 'short': 'Muro bajo h 1.00 + vidrio',
     'note': 'NEW PARTITION WALL → PROPOSED. Base sólida incombustible h≈1.00 m + vidrio hacia el salón. '
             'Base maciza (concreto o bloque) en todo el tramo de la línea. Tramo de la parrilla, de h 1.00 hasta el borde de la campana 2: '
             'vidrio vitrocerámico (≥680 °C) o pantalla inox con cámara ventilada de 25 mm; resto vidrio templado/laminado de seguridad. '
             'Especificación térmica/cortafuego TO BE ENGINEERED.'},
    {'id': 'NW-2', 'rect': [P0 - PARR_D, 3.916, P0, 3.966], 'type': 'partition', 'h': 2.05,
     'short': 'Panel térmico', 'note': 'Panel lateral incombustible piso-campana entre parrilla y puerta (protección térmica y cierre lateral de campana).'},
]
L['new_openings'] += [
    {'id': 'P-1', 'type': 'double_acting_door', 'rect': [P0, DOOR[0], P1, DOOR[1]], 'width': round(DOOR[1] - DOOR[0], 2), 'label': 'P-1',
     'note': 'Puerta de cocina de vaivén: vano 1.02, hoja ≈0.96 con visor, paso libre ≥0.90 (Ley 7600 art. 140). Única conexión cocina/salón: '
             'entrada de loza sucia y salida de platos; circulación por la derecha. Siempre libre (ruta de evacuación del personal).'},
    {'id': 'P-2', 'type': 'door', 'rect': [1.46, 7.076, 1.56, 7.986], 'width': 0.91, 'label': 'P-2',
     'hinge': [1.56, 7.986], 'closed_to': [1.56, 7.076], 'swing_to': [2.47, 7.986],
     'note': 'Puerta de cierre automático en el vano existente pasillo limpio → lavado (separa limpio/sucio y conserva la ruta de evacuación del ala).'},
    {'id': 'PS-1', 'type': 'service_door', 'rect': [2.56, 11.486, 3.46, 11.616], 'width': 0.90, 'label': 'PS-1',
     'hinge': [3.46, 11.616], 'closed_to': [2.56, 11.616], 'swing_to': [3.46, 12.516], 'conditional': True,
     'note': 'PUERTA DE SERVICIO CONDICIONAL: sustituye parte de la ventana sur existente (hacia pasillo del edificio). '
             'Requiere aprobación de la administración y revisión estructural. Si el pasillo sur es parte de la salida de la escalera del edificio, '
             'puede exigirse puerta cortafuego autocerrante — VERIFY ON SITE.'},
]
L['remove_items'] = [{'id': 'HOOD-EX', 'rect': [2.397, 0.116, 6.197, 1.219], 'label': 'Campana existente Marna’s 3.80 × 1.10 — A RETIRAR'}]
L['demolish'].append({'id': 'IP-P2', 'rect': [1.46, 8.536, 1.56, 8.886], 'note': 'Recorte del remate liviano de IP-P2 bajo IP-P3 (35 cm) para liberar la boca del pasillo limpio.'})
L['demolish'].append({'id': 'EW-S2', 'rect': [3.365, 11.486, 3.46, 11.616], 'conditional': True,
                      'note': 'Solo si se aprueba PS-1: ampliar vano 9.5 cm en muro sur.'})

# ---------------------------------------------------------------- B · HOT LINE / SHOW KITCHEN
FL = P0 - LINE_D
eq('H1', 'parrilla', 'Parrilla argentina', 'fire', [P0 - PARR_D, 2.416, P0, 3.916], 'W', 1.20, 0.90, True,
   note='Carbón/leña. 150 cm; fondo y brasero TBV. Pieza visual principal: de frente al salón tras el vidrio.')
eq('H2', 'cocina_4q', 'Cocina 4 quemadores (gas de red)', 'fire', [FL - TECH, 1.616, P0 - TECH, 2.416], 'W', 1.10, 0.90, True, plan_label='Cocina 4Q gas',
   note='4 quemadores extragrandes, gas de la red del centro comercial (sin cilindros en el local); frente 80 cm TBV.')
eq('H3', 'plancha', 'Plancha', 'fire', [FL - TECH, 0.916, P0 - TECH, 1.616], 'W', 1.10, 0.90, True, note='Módulo 70 cm; fondo TBV.')
eq('H4', 'freidora_1', 'Freidora 1', 'fire', [FL - TECH, 0.516, P0 - TECH, 0.916], 'W', 1.10, 0.90, True,
   note='Freidora independiente; huella comercial 40×80 — DIMENSION TO VERIFY.')
eq('H5', 'freidora_2', 'Freidora 2', 'fire', [FL - TECH, YN, P0 - TECH, 0.516], 'W', 1.10, 0.90, True,
   note='Freidora independiente; huella comercial 40×80 — DIMENSION TO VERIFY.')
eq('HD-1', 'hood', 'Campana 1 · línea a gas', 'hood', [P0 - 1.15, YN, P0, 2.416], None, 0, 0.6, True, overhead=True, closed_ends=True,
   label_side='outside', system='grease', plan_label='Campana 1 · gas',
   note='Freidoras + plancha + cocina 4Q (2.30 m): ≈2.30 × 1.15 m (voladizo frontal 0.20), supresión de químico húmedo UL 300 / NFPA 17A y corte de gas enclavado. '
        'Collarín nuevo dentro de la campana con transición al ducto existente de Marna’s si la inspección lo aprueba (VERIFY ON SITE). '
        'Panel divisorio con la campana 2 en Y 2.42. EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED.')
eq('HD-2', 'hood', 'Campana 2 · parrilla (combustible sólido)', 'hood', [P0 - 1.10, 2.416, P0, 3.966], None, 0, 0.6, True, overhead=True, closed_ends=True,
   label_side='outside', system='solid_fuel', plan_label='Campana 2 · sólido',
   note='Solo la parrilla (NFPA 96 cap. 14): campana, ducto, ventilador y descarga INDEPENDIENTES de la campana 1, arrestachispas antes de los filtros, '
        'filtros ≥1.22 m sobre la superficie de cocción en su posición más alta (NFPA 96 cap. 14, TBV), supresión listada para combustible sólido. '
        '≈1.55 × 1.10 m. Ducto vertical propio a cubierta en cerramiento RF 1 h. EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED.')
eq('K1', 'mesa_1', 'Mesa de trabajo inox', 'prep', [0.875, YN, 2.275, 0.816], 'S', 1.00, 0.90, False, plan_label='Mesa inox + K2 horno',
   note='Apoyo / mise en place / bandejeo / terminación junto a la línea. 140 × 70 (ajustada para dejar 1.10 m frente a freidoras).')
eq('K2', 'oven', 'Horno (sobre mesa)', 'fire', [1.525, YN, 2.275, 0.816], None, 0, 1.55, True, stack_with='K1', no_label=True,
   note='Horno eléctrico de convección de mesa ≈75 × 70 TBV, con campana de recirculación integrada listada UL 710B (ventless) porque queda fuera de las campanas — TO BE ENGINEERED.')
eq('K3', 'handwash_k', 'Lavamanos cocina (recomendado)', 'wash', [1.85, 4.606, 2.18, 4.986], 'N', 0.60, 0.90, False,
   note='Recomendado por higiene junto a la línea y a la entrada desde frío (verificar requisito Ministerio de Salud).')

# ---------------------------------------------------------------- E · BBQ PRODUCTION (west wall)
eq('S1', 'smoker', 'Smoker vertical (ahumador)', 'smoker', [-0.085, 1.00, 0.665, 2.40], 'E', 1.00, 1.90, True,
   note='Gabinete ≈100 × 70 + firebox/servicio ≈40 → huella ≈140 × 75 TBV. Carga de combustible y cenizas por el frente; drenaje de grasa; '
        'chimenea propia. SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED.')
eq('S2', 'holding', 'Holding caliente', 'fire', [-0.085, 2.55, 0.665, 3.15], 'E', 0.90, 1.00, True,
   note='Gabinete de mantenimiento en caliente ≈60 × 75 TBV. Flujo smoker → holding → línea/pase.')
eq('S3', 'fuel_storage', 'Leña / carbón (rack metálico)', 'storage', [-0.085, 3.40, 0.415, 4.40], 'E', 0.80, 1.20, True, plan_label='Leña / carbón',
   note='Almacén de uso diario para smoker y parrilla, separado del smoker por el holding. Distancias a combustibles TO BE VALIDATED.')

# ---------------------------------------------------------------- W · WASHING (existing PILAS)
eq('W1', 'sink_2t', 'Fregadero 2 tanques', 'wash', [3.31, 5.15, 4.11, 7.15], 'W', 1.00, 0.90, False,
   note='≈200 × 80 con escurridores. Sobre el drenaje existente de la pila de 3 tanques (WP1).')
eq('W2', 'handwash', 'Lavamanos', 'wash', [4.13, 7.25, 4.51, 7.58], 'W', 0.60, 0.90, False,
   note='33 × 38. Reutiliza la zona húmeda WP2.')
eq('W3', 'mop_sink', 'Pileta / mop sink', 'wash', [3.91, 7.936, 4.51, 8.436], 'W', 0.60, 0.45, False,
   note='60 × 50 en la posición exacta de la pila palo de piso existente (WP3).')
eq('W4', 'mesa_opt', 'Mesa de apoyo / escurrido', 'wash', [1.56, 5.20, 2.16, 7.07], 'E', 1.00, 0.90, False, plan_label='Mesa escurrido (limpio)',
   note='187 × 60 (mesa opcional del programa) contra la división existente P1: racks limpios / apoyo.')
eq('W6', 'waste_bins', 'Basureros con tapa (bajo escurridor sucio)', 'wash', [3.36, 5.20, 4.06, 6.00], None, 0, 0.70, False, stack_with='W1', no_label=True,
   note='3 contenedores con tapa y pedal (orgánicos / valorizables / ordinarios) bajo el escurridor norte de W1, donde entra la loza sucia. '
        'Retiro diario al cuarto de basura del centro comercial, fuera de horario (VERIFY con la administración).')
eq('W7', 'chem_cabinet', 'Gabinete de químicos', 'storage', [4.21, 7.60, 4.51, 7.93], 'W', 0.60, 1.80, False, plan_label='Químicos',
   note='Gabinete cerrado y rotulado para productos de limpieza, lejos de alimentos y loza limpia.')
eq('GT-1', 'grease_trap', 'Trampa de grasa (bajo fregadero)', 'wash', [3.36, 6.35, 4.06, 7.05], None, 0, 0.40, True, stack_with='W1', no_label=True,
   note='Interceptor de grasa accesible para limpieza antes de conectar al drenaje existente; tamaño según CIHSE — TO BE ENGINEERED.')
eq('W5', 'shelf_wash', 'Estante loza limpia', 'storage', [2.10, 8.086, 3.30, 8.436], 'N', 0.80, 1.80, False,
   note='120 × 35, 4 niveles.')

# ---------------------------------------------------------------- A · COLD PREP (former PASTELERIA + clean corridor)
eq('A1', 'fridge_2d', 'Refrigerador 2 puertas', 'cold', [3.81, 9.286, 4.51, 10.736], 'W', 0.90, 2.00, False, note='145 × 70 × 200.')
eq('A2', 'freezer_1d', 'Congelador vertical', 'cold', [3.81, 10.736, 4.51, 11.486], 'W', 0.90, 2.00, False, plan_label='Congelador', note='75 × 70 × 200.')
eq('A3', 'mesa_fria', 'Mesa fría refrigerada', 'cold', [0.70, 10.786, 2.50, 11.486], 'N', 1.00, 0.90, False, note='180 × 70.')
eq('A7', 'mesa_esquina', 'Esquinero inox (mesada en L)', 'prep', [0.0, 10.786, 0.70, 11.486], None, 0, 0.90, False, plan_label='Esquinero',
   note='Cierra la esquina entre A4 y A3 con mesada continua en L (sin rendijas difíciles de limpiar).')
eq('A8', 'handwash_cold', 'Lavamanos prep fría', 'wash', [1.65, 8.536, 1.98, 8.916], 'S', 0.60, 0.90, False, plan_label='Lavamanos',
   note='Lavamanos exclusivo de la zona fría, con jabón y toallas desechables.')
eq('A4', 'mesa_2', 'Mesa de trabajo inox (prep fría)', 'prep', [0.0, 9.586, 0.70, 10.786], 'E', 1.00, 0.90, False, plan_label='Mesa inox prep',
   note='120 × 70 (reducida de 180 para dejar libre la boca del pasillo limpio; ajuste permitido por el cliente).')
eq('A5', 'shelf_4', 'Estantería 4 niveles', 'storage', [2.10, 8.536, 3.80, 8.886], 'S', 0.80, 1.80, False, note='170 × 35.')
eq('A6', 'shelf_dry', 'Almacén seco (estantería)', 'storage', [-0.085, 5.10, 0.365, 7.90], 'E', 0.85, 2.00, False,
   note='280 × 45 a lo largo del pasillo limpio (muro oeste). Estantes a ≥15 cm del piso.')
# ---------------------------------------------------------------- C · BAR / POS
eq('C1', 'barra', 'Barra de bebidas', 'bar', [5.43, YN, 6.08, 0.80], 'E', 0.90, 1.05, False, plan_label='Barra bebidas',
   note='Barra compacta de bebidas con enfriador bajo barra y pileta de barra (extender drenaje existente WP5 ≈1 m — VERIFY).')
eq('C5', 'handwash_bar', 'Lavamanos de barra', 'wash', [P1, YN, P1 + 0.38, YN + 0.33], 'E', 0.50, 0.90, False, plan_label='Lavamanos',
   note='Lavamanos exclusivo del personal de barra, al fondo del pasillo de barra (tramo sin salida).')
eq('L1', 'lockers', 'Casilleros del personal', 'misc', [5.50, YS - 0.45, 6.50, YS], 'N', 0.90, 1.80, False, plan_label='Casilleros personal',
   note='Mueble cerrado de 10 casilleros (100 × 45 × 180) fuera de las áreas de alimentos, junto a P-1. '
        'El personal usa los servicios sanitarios comunes del centro comercial (autorización escrita: VERIFY).')
eq('C4', 'caja', 'Caja accesible (h 0.80)', 'bar', [5.43, 0.80, 6.08, 1.70], 'E', 0.90, 0.80, False, plan_label='Caja h 0.80 + C3 POS',
   note='Tramo de mostrador a 0.80 m de altura, 0.90 m de largo, con espacio libre inferior (Ley 7600, Reglamento art. 148).')
eq('C2', 'pass', 'Pase / pickup caliente', 'bar', [5.43, 1.70, 6.08, 2.35], 'E', 0.90, 1.05, False, plan_label='Pase',
   note='Repisa de pase con lámparas de calor: se carga desde el pasillo de barra (lado cocina) y se retira desde el salón.')
eq('C3', 'pos', 'POS', 'bar', [5.53, 1.00, 5.98, 1.45], None, 0, 0.90, False, stack_with='C4', no_label=True)
eq('D2', 'delivery_staging', 'Recepción + staging / retiro delivery', 'delivery', [15.45, 0.40, 16.20, 1.00], 'S', 0.60, 1.05, False, plan_label='Recep. + delivery',
   note='Atril de recepción con repisa para pedidos listos: el repartidor retira en la entrada sin cruzar el salón. Los pedidos se empacan en el pase.')

# ---------------------------------------------------------------- D · DINING
T, CH, BQ = L['tables'], L['chairs'], L['banquettes']
ROW_N = dict(bq=(YN, YN + 0.55), tb=(0.716, 1.416), ch=(1.466, 1.916), facing='N')
ROW_S = dict(bq=(YS - 0.55, YS), tb=(3.686, 4.386), ch=(3.186, 3.636), facing='S')


def row(prefix, x0, x1, R, pattern, gap_join=0.31, gap_other=0.35):
    """pattern: list of table widths (0.70 = 2-top, 1.20 = 4-top). Gaps ≥0.305 m (NFPA 101 aisle accessway between tables)."""
    x = x0
    seats_bq = 0
    n = 0
    prev = None
    ids = []
    for w in pattern:
        gap = gap_join if (prev == 0.70 and w == 0.70) else (gap_other if prev is not None else 0.0)
        if x + gap + w > x1 + 1e-6:
            break
        x += gap
        n += 1
        tid = f'{prefix}{n}'
        seats = 2 if w <= 0.75 else 4
        T.append({'id': tid, 'tag': tid, 'rect': [round(x, 3), R['tb'][0], round(x + w, 3), R['tb'][1]], 'seats': seats,
                  'type': '2top' if seats == 2 else '4top'})
        nch = 1 if seats == 2 else 2
        for k in range(nch):
            cx = x + w * (k + 0.5) / nch
            CH.append({'id': f'{tid}-c{k+1}', 'rect': [round(cx - 0.225, 3), R['ch'][0], round(cx + 0.225, 3), R['ch'][1]],
                       'table': tid, 'facing': R['facing']})
        seats_bq += nch
        ids.append(tid)
        prev = w
        x += w
    # joinable neighbours
    for i in range(len(ids) - 1):
        a, b = T[-len(ids) + i], T[-len(ids) + i + 1]
        if a['seats'] == 2 and b['seats'] == 2 and round(b['rect'][0] - a['rect'][2], 2) <= gap_join + 0.01:
            a.setdefault('joinable_with', []).append(b['id'])
    return x, seats_bq


# north row: from east of column B1 to before the entrance swing
N_PATTERN = [0.70, 0.70, 1.20, 0.70, 0.70, 1.20, 0.70, 0.70]
xn_end, sn = row('TN', 8.20, 15.30, ROW_N, N_PATTERN)
BQ.append({'id': 'BQ-N', 'rect': [8.15, YN, round(xn_end + 0.05, 3), YN + 0.55], 'seats': sn, 'back': 'N', 'individual': True,
           'note': f'{sn} asientos individuales fijos con divisores (≥0.70 m c/u): la carga de ocupantes se cuenta por asiento, no por longitud.'})
# south row: from the service zone to before the entrance swing
S_PATTERN = [0.70, 0.70, 1.20, 0.70, 0.70, 1.20, 0.70, 0.70, 1.20]
xs_end, ss = row('TS', 6.55, 15.45, ROW_S, S_PATTERN, gap_other=0.32)
BQ.append({'id': 'BQ-S', 'rect': [6.50, YS - 0.55, round(xs_end + 0.05, 3), YS], 'seats': ss, 'back': 'S', 'individual': True,
           'note': f'{ss} asientos individuales fijos con divisores (≥0.70 m c/u): la carga de ocupantes se cuenta por asiento, no por longitud.'})

# accessible tables (Ley 7600): wheelchair takes the aisle-side chair position
for t in T:
    if t['id'] in ('TN6', 'TS8'):
        t['accessible'] = True
        t['note'] = 'Mesa accesible: h 0.76–0.80, espacio libre inferior ≥0.70 m, aproximación 0.80 × 1.20 desde el pasillo (se retira la silla del pasillo).'

# ---------------------------------------------------------------- zones
L['zones'] = [
    {'id': 'B', 'name': 'Cocina caliente / show kitchen', 'short': 'HOT LINE / SHOW KITCHEN', 'color': '#f07c14',
     'poly': [[0.865, YN], [P0, YN], [P0, YS], [1.90, YS], [1.90, 0.866], [0.865, 0.866]],
     'label_at': [2.18, 2.55], 'label_lines': ['HOT LINE /', 'SHOW KITCHEN'], 'label_size': 4.4, 'label_at_flows': [2.2, 2.4]},
    {'id': 'E', 'name': 'Producción BBQ: smoker + holding', 'short': 'BBQ PRODUCTION', 'color': '#c2410c',
     'poly': [[-0.085, 0.866], [1.90, 0.866], [1.90, YS], [-0.085, YS]], 'label_at': [1.20, 3.80], 'label_lines': ['BBQ', 'PRODUCTION'], 'label_size': 4.6, 'label_at_flows': [1.0, 3.45]},
    {'id': 'W', 'name': 'Lavado (antiguas PILAS)', 'short': 'WASHING', 'color': '#17737a',
     'poly': [[1.46, YS], [4.11, YS], [4.11, 6.456], [4.51, 6.456], [4.51, 8.436], [1.56, 8.436], [1.56, YS]],
     'label_at': [2.75, 7.55]},
    {'id': 'A', 'name': 'Cold prep + refrigeración + almacén (antigua PASTELERÍA)', 'short': 'COLD PREP', 'color': '#2f6fd0',
     'prep': True,
     'poly': [[-0.085, YS], [1.46, YS], [1.46, 8.436], [4.51, 8.436], [4.51, 11.486], [0.0, 11.486], [0.0, 8.816],
              [0.315, 8.816], [0.315, 8.186], [-0.085, 8.186]], 'label_at': [2.2, 9.35], 'label_at_flows': [1.9, 10.35]},
    {'id': 'C', 'name': 'Barra / caja / POS / pase', 'short': 'BAR / POS', 'color': '#7a4fb8',
     'poly': [[P1, YN], [6.95, YN], [6.95, 2.45], [P1, 2.45]], 'label_at': [6.60, 1.25], 'label_size': 3.4, 'label_at_flows': [6.5, 0.6]},
    {'id': 'D', 'name': 'Salón', 'short': 'DINING', 'color': '#2e9a3a',
     'poly': [[P1, 2.45], [6.95, 2.45], [6.95, YN], [16.285, YN], [16.285, YS], [P1, YS]], 'label_at': [10.35, 2.55], 'label_at_flows': [10.9, 4.0]},
]

# ---------------------------------------------------------------- points, routes, checks
L['points'] = {
    'entrance': [15.9, 2.64], 'barra_front': [6.55, 1.2], 'pass_dining': [6.55, 2.05], 'dining_far': [15.0, 2.55],
    'kitchen_door': [4.40, 4.48], 'dish_drop': [2.75, 5.55], 'cold_storage': [3.35, 9.3], 'prep': [1.2, 9.85],
    'line': [2.95, 2.5], 'expo_pass': [4.95, 2.02], 'delivery_staging': [15.8, 1.35], 'smoker_front': [1.15, 1.7],
    'service_door': [3.01, 11.3], 'fuel': [0.9, 3.9],
}
L['routes'] = [
    {'id': 'R-guest', 'kind': 'guest', 'label': 'Entrada → barra / caja', 'pts': [[15.9, 2.55], [7.3, 2.55], [6.6, 1.45]], 'min_width': 1.10},
    {'id': 'R-server', 'kind': 'server', 'label': 'Pase → mesas (pasillo central)', 'pts': [[6.6, 2.05], [7.3, 2.55], [15.0, 2.55]], 'min_width': 1.10},
    {'id': 'R-expo', 'kind': 'server', 'label': 'Línea → puerta P-1 → pase', 'pts': [[2.8, 3.4], [2.8, 4.45], [3.9, 4.48], [5.0, 4.48], [5.0, 3.0], [4.95, 2.1]], 'min_width': 0.90},
    {'id': 'R-dirty', 'kind': 'dirty', 'label': 'Salón → puerta P-1 → lavado', 'pts': [[15.0, 2.62], [7.0, 2.6], [6.36, 2.8], [5.2, 3.7], [4.95, 4.40], [3.9, 4.45], [2.9, 4.8], [2.73, 5.3], [2.73, 5.9]], 'min_width': 0.90},
    {'id': 'R-clean', 'kind': 'clean', 'label': 'Frío → prep → pasillo limpio → línea', 'pts': [[3.3, 9.7], [1.9, 9.75], [1.17, 9.25], [0.89, 8.6], [0.89, 8.3], [0.89, 5.3], [0.9, 4.75], [1.25, 4.2], [2.7, 3.8], [2.9, 1.3]], 'min_width': 1.00},
    {'id': 'R-bbq', 'kind': 'clean', 'label': 'Smoker → holding → línea / pase', 'pts': [[1.15, 1.7], [1.15, 2.85], [2.6, 3.7], [2.8, 4.4]], 'min_width': 1.00},
    {'id': 'R-deliv', 'kind': 'delivery', 'label': 'Pase → staging en recepción (retiro sin cruzar salón)', 'pts': [[4.95, 3.0], [6.36, 2.8], [7.0, 2.55], [15.0, 2.55], [15.45, 2.35], [15.75, 1.55]], 'min_width': 0.90},
    {'id': 'R-fuel', 'kind': 'fuel', 'label': 'Leña / cenizas ↔ PS-1 (condicional, fuera de horario)', 'pts': [[3.05, 11.3], [3.1, 10.5], [2.2, 9.75], [1.17, 9.25], [0.89, 8.6], [0.89, 8.3], [0.89, 5.3], [0.95, 3.9]], 'min_width': 0.90},
]
L['checks'] = [
    ['entrance', 'barra_front', 1.10], ['pass_dining', 'dining_far', 1.10], ['kitchen_door', 'dish_drop', 0.90],
    ['cold_storage', 'line', 1.00], ['line', 'kitchen_door', 0.90], ['smoker_front', 'kitchen_door', 0.90],
    ['expo_pass', 'kitchen_door', 0.90], ['delivery_staging', 'expo_pass', 0.90], ['service_door', 'fuel', 0.90],
]

# ---------------------------------------------------------------- life safety (Bomberos) + MEP anchors (single source for all sheets)
L['life_safety'] = {
    'capacity_declared': 49,
    'capacity_note': 'Capacidad máxima declarada y rotulada: 49 personas (clientes + personal). Condición de diseño: ocupación de menos de 50 '
                     'personas (NFPA 101 mercantil / <50): una salida, puerta sin exigencia de giro hacia afuera ni antipánico. VERIFY con Bomberos (RNPCI).',
    'load_factors': [
        {'zones': ['D'], 'factor': 1.4, 'basis': 'neto', 'use': 'Salón con mesas y sillas (NFPA 101 Tabla 7.3.1.2)'},
        {'zones': ['C'], 'factor': 9.3, 'basis': 'bruto', 'use': 'Barra/caja/pase: área de trabajo, solo servicio (sin taburetes ni clientes de pie)'},
        {'zones': ['B', 'E', 'W', 'A'], 'factor': 9.3, 'basis': 'bruto', 'use': 'Cocina, lavado, almacén (NFPA 101 Tabla 7.3.1.2)'},
    ],
    'limits': {'common_path_m': 22.86, 'travel_m': 45.72, 'door_clear_min_m': 0.81, 'egress_mm_per_person': 5.0,
               'note': 'Límites NFPA 101 para <50 personas sin rociadores: camino común 22.86 m (75 ft), recorrido 45.72 m (150 ft). Verificar edición.'},
    'exits': [
        {'id': 'SAL-1', 'opening': 'D-ENT', 'at': [16.30, 2.643], 'width': 2.00, 'leaf': 0.97,
         'note': 'Salida principal al pasillo abierto del centro comercial. Hojas hoy hacia adentro (permitido con <50 personas). '
                 'Recomendado invertir el giro hacia afuera sin invadir el pasillo común — VERIFY con la administración.'},
        {'id': 'SAL-2', 'opening': 'PS-1', 'at': [3.01, 11.55], 'width': 0.90, 'conditional': True,
         'note': 'Segunda salida del personal SOLO si se aprueba PS-1 (condicional). No se cuenta para el cálculo.'},
    ],
    'egress_route_note': 'Ruta del ala: cold prep → boca del pasillo → P-2 (cierre automático) → lavado (franja libre ≥0.915 m entre W4 y W1, sin racks ni carritos) '
                         '→ paso de 1.86 m → P-1 → salón → SAL-1.',
    'waiting_area': 'Sin zona de espera interior: el vestíbulo y el barrido de D-ENT son área de egreso libre. Cola y retiro de delivery afuera.',
    'exit_signs': [
        {'id': 'RS-1', 'at': [16.15, 2.643], 'text': 'SALIDA', 'dir': 'E', 'note': 'Sobre la puerta principal, iluminado'},
        {'id': 'RS-2', 'at': [6.20, 2.55], 'text': 'SALIDA →', 'dir': 'E', 'note': 'Direccional colgante en el salón (visible desde P-1 y la barra)'},
        {'id': 'RS-3', 'at': [4.20, 4.48], 'text': 'SALIDA →', 'dir': 'E', 'note': 'Cara de cocina de la puerta P-1'},
        {'id': 'RS-4', 'at': [0.90, 5.15], 'text': 'SALIDA ↑', 'dir': 'N', 'note': 'Pasillo limpio del ala, hacia la cocina'},
        {'id': 'RS-5', 'at': [1.00, 8.95], 'text': 'SALIDA ↑', 'dir': 'N', 'note': 'Boca del pasillo limpio desde cold prep'},
        {'id': 'RS-6', 'at': [2.70, 7.40], 'text': 'SALIDA ↑', 'dir': 'N', 'note': 'Lavado, sobre la franja de evacuación hacia P-1'},
    ],
    'emergency_lights': [[2.40, 2.40], [0.90, 4.40], [0.90, 7.00], [2.70, 6.60], [2.20, 10.00], [5.00, 3.60], [8.60, 2.55], [12.40, 2.55], [15.60, 2.55]],
    'emergency_note': 'Iluminación de emergencia en todo el recorrido: autonomía ≥1.5 h, ≥10.8 lux promedio y ≥1.1 lux mínimo iniciales (NFPA 101 7.9).',
    'extinguishers': [
        {'id': 'EX-K', 'type': 'Clase K 6 L', 'at': [1.60, 4.95], 'note': 'Freidoras a ≤9.15 m; rótulo: accionar primero el sistema fijo'},
        {'id': 'EX-A1', 'type': 'Clase K 6 L (combustible sólido)', 'at': [-0.04, 4.70],
         'note': 'Smoker y parrilla a ≤6 m (NFPA 96 cap. 14: 2-A de agua pulverizada o químico húmedo K 6 L). Si un hogar supera 0.14 m³: manguera fija de agua.'},
        {'id': 'EX-B1', 'type': 'ABC 2-A:10-B:C', 'at': [2.45, 0.13], 'note': 'Cocina caliente: equipos a gas (10-B a ≤9.15 m de las freidoras)'},
        {'id': 'EX-A2', 'type': 'ABC 2-A:10-B:C', 'at': [15.80, 4.95], 'note': 'Salón, junto a la salida'},
        {'id': 'EX-A3', 'type': 'ABC 2-A:10-B:C', 'at': [0.35, 8.50], 'note': 'Ala de servicio (lavado / cold prep)'},
    ],
    'pull_station': {'at': [P1 + 0.05, 3.85], 'h': '1.07–1.22 m', 'ids': ['PM-1', 'PM-2'],
                     'note': 'Pulsadores manuales de supresión de la campana 1 (PM-1) y de la campana 2 (PM-2), con tapa, en la cara salón de NW-1 '
                             'junto al marco norte de P-1: sobre la ruta de salida del personal, ≈3 m de la parrilla (distancia exigida según edición NFPA 96 / 17A: VERIFY).'},
    'smoke_detectors': [[2.40, 1.20], [0.60, 6.20], [2.40, 9.80], [8.50, 2.55], [12.40, 2.55]],
    'detector_note': 'Detección e integración a la alarma del centro comercial si existe (VERIFY). En cocina caliente: detector térmico, no de humo. '
                     'Monitoreo de CO recomendado por los dos aparatos de combustible sólido.',
    'sprinklers': 'NFPA 101 no exige rociadores con <50 personas. Si el centro comercial tiene red o alarma, integrarse según NFPA 13/72 — VERIFY con la administración.',
    'fuel_storage_note': 'Leña/carbón: solo la provisión de un día, en gabinete metálico cerrado (S3), nada encima, ≥0.915 m de aparatos de combustible sólido. '
                         'Cenizas: retiro diario en contenedor metálico con tapa, fuera de horario, a un punto exterior acordado con la administración.',
    'restrooms': 'Servicios sanitarios: comunes del centro comercial (H/M + accesible) para clientes y personal. Capacidad según CIHSE Tabla 5.3, horario, '
                 'distancia de recorrido y autorización escrita de la administración: VERIFY.',
}
L['mep'] = {
    'gas': {'source': 'Red de gas del centro comercial (tipo de gas y presión: VERIFY)', 'entry': [3.00, 0.00],
            'entry_note': 'Punto de acometida tentativo en el muro norte — VERIFY ON SITE con la administración',
            'main_valve': [3.00, -0.15], 'solenoid': [2.90, 0.20], 'consumers': ['H2', 'H3', 'H4', 'H5'],
            'note': 'Llave de corte principal FUERA del local, en la acometida, rotulada. Válvula solenoide/mecánica enclavada con la supresión de la campana 1 '
                    '(rearme manual) en el muro norte, fuera de la proyección de la campana. Manifold en el espacio técnico de 0.15 m detrás de la línea, '
                    'válvula de servicio por equipo, conectores listados ≤1.5 m con cable de restricción. Detector según tipo de gas (GLP a ≤0.30 m del piso).'},
    'exhaust': [
        {'id': 'EXT-1', 'serves': 'HD-1', 'kind': 'grasa (gas)', 'collar': [3.95, 0.67],
         'route': [[3.95, 0.67], [4.30, 0.67]],
         'riser': 'Collarín nuevo en HD-1 con transición al riser existente de Marna’s (X 4.10–4.50, Y 0.47–0.87) solo si la inspección lo aprueba; '
                  'si no, ducto nuevo acero 16 MSG soldado en cerramiento RF — VERIFY ON SITE', 'fan': 'Ventilador en cubierta — VERIFY'},
        {'id': 'EXT-2', 'serves': 'HD-2', 'kind': 'combustible sólido', 'collar': [3.80, 3.20], 'route': [[3.80, 3.20]],
         'riser': 'Ducto vertical propio sobre la parrilla hasta cubierta, en cerramiento RF 1 h nuevo (penetración de losa: revisión estructural + aprobación del condominio)',
         'fan': 'Ventilador propio en cubierta', 'note': 'Arrestachispas antes de filtros; limpieza mensual. S-PIL no sirve (celda ≈0.11 m).'},
        {'id': 'EXT-3', 'serves': 'S1', 'kind': 'chimenea smoker', 'collar': [0.29, 1.70], 'route': [[0.29, 1.70]],
         'riser': 'Chimenea listada vertical (NFPA 211) sobre el smoker hasta cubierta, con arrestachispas — VERIFY. Alternativa: smoker eléctrico o de pellet listado.',
         'note': 'Remate según NFPA 96 7.8 / INVU (altura sobre edificios vecinos y distancia a tomas de aire: VERIFY).'},
    ],
    'makeup_air': {'id': 'AR-1', 'diffusers': [[2.40, 1.60], [2.40, 3.00]],
                   'note': 'Aire de reposición ≈80–90 % del caudal extraído, entregado sin perturbar la captura de las campanas; suministro positivo para combustible sólido — TO BE ENGINEERED.'},
    'panel': {'id': 'TE-1', 'rect': [6.25, 0.116, 6.85, 0.26],
              'note': 'Tablero eléctrico del local (ubicación propuesta, frente libre 0.90 m) — acometida existente: VERIFY ON SITE.'},
    'grease_trap': 'GT-1',
    'drain_existing': ['WP1', 'WP2', 'WP3', 'WP5'],
    'engineering_notes': ['Anclaje sísmico (Código Sísmico de CR) de campanas, ductos, gas y equipos altos (A1, A2, S1).',
                          'Ventilación / aire acondicionado del salón y de la cocina: el local solo tiene fachada al este — TO BE ENGINEERED.',
                          'Aire de combustión y monitoreo de CO para la parrilla y el smoker.'],
}

# ---------------------------------------------------------------- 3D decor + tour (walkthrough app)
L['decor'] = [
    {'type': 'slat_wall', 'rect': [6.55, YS - 0.075, 15.35, YS], 'face': 'N', 'text': 'LAVA', 'z': 1.0, 'h': 2.85, 'text_at': 0.55},
    {'type': 'sign', 'rect': [P1, 1.30, P1 + 0.06, 3.70], 'face': 'E', 'text': 'LAVA', 'h': 2.62, 'size': 0.42},
    {'type': 'poster', 'rect': [11.10, YN, 11.84, YN + 0.03], 'face': 'S', 'text': 'vaca', 'h': 1.72, 'size': 1.0},
    {'type': 'poster', 'rect': [12.00, YN, 12.74, YN + 0.03], 'face': 'S', 'text': 'GOOD MEAT|GOOD PEOPLE', 'h': 1.72, 'size': 1.0},
    {'type': 'poster', 'rect': [12.90, YN, 13.64, YN + 0.03], 'face': 'S', 'text': 'cerdo', 'h': 1.72, 'size': 1.0},
    {'type': 'sconce', 'rect': [9.20, YN, 9.36, YN + 0.3], 'face': 'S', 'h': 2.2},
    {'type': 'sconce', 'rect': [10.55, YN, 10.71, YN + 0.3], 'face': 'S', 'h': 2.2},
    {'type': 'sconce', 'rect': [14.05, YN, 14.21, YN + 0.3], 'face': 'S', 'h': 2.2},
    {'type': 'pendant', 'rect': [5.60, 0.45, 5.84, 0.69], 'h': 1.95, 'style': 'dome'},
    {'type': 'pendant', 'rect': [5.60, 1.20, 5.84, 1.44], 'h': 1.95, 'style': 'dome'},
    {'type': 'pendant', 'rect': [5.60, 1.90, 5.84, 2.14], 'h': 1.95, 'style': 'dome'},
    {'type': 'firewood_niche', 'rect': [P0, 2.52, P1, 3.22], 'face': 'E', 'z': 0.12, 'h': 0.86, 'material': 'incombustible',
     'note': 'Relieve decorativo de leños cerámicos / acero (incombustible), sin hueco: la base detrás de la parrilla queda maciza. Sin leña real ni jardinera.'},
]
L['tour'] = [
    {'id': 'entrada', 'title': 'Entrada', 'pos': [15.55, 2.64], 'look': [4.0, 3.15], 'look_h': 1.25,
     'text': 'Desde la puerta, el pasillo central remata en la parrilla: fuego y manejo de carnes detrás del vidrio, con el letrero LAVA encima. La división se corrió 1.97 m hacia la cocina para ganar salón.',
     'flags': []},
    {'id': 'salon', 'title': 'Salón', 'pos': [11.2, 2.55], 'look': [7.0, 4.2], 'look_h': 1.2,
     'text': 'Bancas corridas contra ambos muros con mesas de 2 que se unen y mesas de 4. Pasillo central ≥1.20 m para meseros. Celosía de madera retroiluminada en el muro sur; concreto, apliques y afiches en el norte.',
     'flags': ['VERIFY ON SITE']},
    {'id': 'barra', 'title': 'Bar / POS y pase', 'pos': [7.15, 1.85], 'look': [5.7, 1.2], 'look_h': 1.05,
     'text': 'Barra compacta: caja, POS y bebidas. En su extremo sur, el pase caliente: la cocina lo carga desde el pasillo de barra y los meseros retiran desde el salón.',
     'flags': []},
    {'id': 'parrilla', 'title': 'Show kitchen · parrilla', 'pos': [7.3, 3.05], 'look': [3.9, 3.1], 'look_h': 1.3,
     'text': 'La hot line está pegada a la división: parrilla → cocina de 4 quemadores → plancha → 2 freidoras. Los cocineros trabajan de frente al salón; la parrilla queda en el eje de la entrada.',
     'flags': ['EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED', 'DIMENSION TO VERIFY']},
    {'id': 'cocina', 'title': 'Hot line por dentro', 'pos': [2.6, 4.1], 'look': [3.6, 1.2], 'look_h': 1.0,
     'text': 'Entrando por la puerta P-1, la línea queda a la derecha. La parrilla tiene su propia campana y ducto (combustible sólido); freidoras, plancha y cocina van bajo la campana 1 con supresión. Mesa de trabajo con horno en el muro norte. Pasillo de trabajo ≥1.10 m.',
     'flags': ['EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED']},
    {'id': 'bbq', 'title': 'BBQ production', 'pos': [2.1, 2.2], 'look': [0.3, 1.8], 'look_h': 1.1,
     'text': 'Pared del fondo: smoker vertical y holding caliente, con la leña del día al lado. Flujo smoker → holding → línea / pase.',
     'flags': ['SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED', 'DIMENSION TO VERIFY']},
    {'id': 'lavado', 'title': 'Washing (antiguas PILAS)', 'pos': [2.7, 6.9], 'look': [3.8, 5.6], 'look_h': 1.0,
     'text': 'El lavado se queda donde Marna’s tenía las pilas: fregadero de 2 tanques, lavamanos y mop sink sobre los drenajes existentes. La loza sucia entra por P-1 y baja directo, sin tocar el frío.',
     'flags': ['VERIFY ON SITE']},
    {'id': 'coldprep', 'title': 'Cold prep (antigua PASTELERÍA)', 'pos': [2.1, 9.7], 'look': [4.1, 9.3], 'look_h': 1.1,
     'text': 'Todo el frío y la preparación fría juntos: refrigerador de 2 puertas, congelador, mesa fría, mesa de trabajo y estanterías. Se conecta con la cocina por el pasillo limpio del muro oeste.',
     'flags': []},
    {'id': 'servicio', 'title': 'Servicio y delivery', 'pos': [2.6, 10.5], 'look': [3.2, 11.4], 'look_h': 1.0,
     'text': 'Puerta de servicio PS-1 (condicional) en la ventana sur para recibir mercadería, leña y retirar pedidos. Si la administración no la aprueba, los repartidores retiran en la recepción de la entrada.',
     'flags': ['VERIFY ON SITE']},
]

# ---------------------------------------------------------------- dimensions on the plan
# Axis-aligned: horizontal dims draw their line at y = a.y + off, vertical dims at x = a.x + off (metres).
D = L['dims']


def dim(a, b, line, label=None, sheets=('A101',), color=None, key='dims'):
    """line = absolute coordinate of the dimension line (y for horizontal dims, x for vertical)."""
    horiz = abs(b[0] - a[0]) >= abs(b[1] - a[1])
    d = {'a': [round(v, 3) for v in a], 'b': [round(v, 3) for v in b], 'off': round(line - (a[1] if horiz else a[0]), 3),
         'label': label, 'sheets': list(sheets)}
    if color:
        d['color'] = color
    L[key].append(d)


BOTH = ('A101', 'A102')
XE = 16.285                      # facade inner face
# top band: kitchen | partition | dining, and overall
dim([-0.085, -0.564], [P0, 0.0], -1.05, f'{P0 + 0.085:.2f} cocina', BOTH)
dim([P0, 0.0], [P1, 0.0], -1.05, None, BOTH)
dim([P1, 0.0], [XE, 0.30], -1.05, f'{XE - P1:.2f} salón + barra', BOTH)
dim([-0.085, -0.564], [XE, 0.30], -1.45, f'{XE + 0.085:.2f} interior')
# facade (east): glazing | entrance door | glazing, and overall depth
dim([XE, YN], [XE, 1.643], 16.95, None, BOTH)
dim([XE, 1.643], [XE, 3.643], 16.95, '2.00 entrada', BOTH)
dim([XE, 3.643], [XE, YS], 16.95, None, BOTH)
dim([XE, YN], [XE, YS], 17.32, f'{YS - YN:.2f} interior', BOTH)
# hot line chain along the partition (drawn in the kitchen aisle)
for a_, b_, t in [(YN, 0.516, '0.40'), (0.516, 0.916, '0.40'), (0.916, 1.616, '0.70'), (1.616, 2.416, '0.80'),
                  (2.416, 3.916, '1.50'), (DOOR[0], DOOR[1], f'{DOOR[1] - DOOR[0]:.2f}')]:
    dim([FL - TECH if b_ <= 2.416 else P0 - PARR_D, a_], [FL - TECH if b_ <= 2.416 else P0 - PARR_D, b_], 2.85, t)
# west (back) wall: BBQ production + dry store + prep table
dim([-0.085, 1.00], [-0.085, 2.40], -0.95, '1.40 smoker')
dim([-0.085, 2.55], [-0.085, 3.15], -0.95, '0.60')
dim([-0.085, 3.40], [-0.085, 4.40], -0.95, '1.00 leña')
dim([-0.085, 5.10], [-0.085, 7.90], -0.75, '2.80 almacén seco')
dim([0.0, 9.55], [0.0, 10.75], -0.75, '1.20 mesa')
dim([-0.085, YS], [0.0, 11.486], -1.20, f'{11.486 - YS:.2f} ala servicio', BOTH)
L['dims'][-1]['lpos'] = 0.3
# south wing: wall | PS-1 | wall, and overall width
dim([0.0, 11.616], [2.56, 11.616], 12.08, None, BOTH)
dim([2.56, 11.616], [3.46, 11.616], 12.08, None, BOTH)
dim([3.46, 11.616], [4.51, 11.616], 12.08, None, BOTH)
dim([0.0, 11.616], [4.51, 11.636], 12.42, '4.51 ancho ala', BOTH)
# working aisles / clearances (measured between equipment fronts)
dim([2.275, 0.40], [FL - TECH, 0.40], 0.40, '1.10')
dim([0.665, 1.25], [FL - TECH, 1.25], 1.25, f'{FL - TECH - 0.665:.2f} libre')
dim([2.16, 6.20], [3.31, 6.20], 6.20, '1.15')
dim([0.365, 6.70], [1.46, 6.70], 6.70, '1.10')
dim([0.70, 10.05], [3.81, 10.05], 10.05, None)
dim([3.10, 8.886], [3.10, 10.786], 3.10, None)
# dining / bar
dim([12.3, 1.916], [12.3, 3.186], 12.3, '1.27 pasillo principal')
dim([P1, 0.95], [5.43, 0.95], 0.95, None)
_tn = {t['id']: t['rect'] for t in T}
dim([_tn['TN1'][2], 0.716], [_tn['TN2'][0], 0.716], 0.716, None)
dim([_tn['TN2'][2], 0.716], [_tn['TN3'][0], 0.716], 0.716, None)

# A-102 only: partition shift and Marna's layout
dim([P0, 0.0], [6.298, 0.0], -0.72, f'{6.298 - P0:.2f} corrimiento', ('A102',), '#d62828', 'dims_demo')
dim([-0.085, -0.564], [6.298, 0.0], -1.45, f'{6.298 + 0.085:.2f} cocina Marna’s', ('A102',), '#6b6b66', 'dims_demo')
dim([6.398, 0.0], [XE, 0.30], -1.45, f'{XE - 6.398:.2f} salón Marna’s', ('A102',), '#6b6b66', 'dims_demo')
dim([2.249, 5.086], [4.11, 5.086], 5.55, f'{4.11 - 2.249:.2f} paso a lavado', ('A102',), None, 'dims_demo')

# ---------------------------------------------------------------- keynotes (numbered markers + list box)
L['keynote_box'] = {'A101': [8.75, 5.75, 17.25, 12.35], 'A102': [8.75, 5.75, 17.25, 12.35]}
L['keynotes'] = [
    {'anchor': [3.07, 3.62], 'sheets': ['A101'], 'color': '#b35900',
     'text': ['EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED',
              'Dos sistemas independientes: campana 1 (gas, supresión UL 300)',
              'y campana 2 solo parrilla (combustible sólido, NFPA 96 cap. 14).']},
    {'anchor': [0.95, 1.65], 'sheets': ['A101'], 'color': '#6e2508',
     'text': ['SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED',
              'Chimenea propia; leña, cenizas y drenaje de grasa por el frente.']},
    {'anchor': [P1 + 0.28, 3.55], 'sheets': ['A101'], 'color': '#111111',
     'text': ['NEW PROPOSED WALL · división cocina/salón en X = 4.33',
              'Muro bajo sólido h 1.00 + vidrio (spec. térmica TO BE ENGINEERED).',
              'Corrimiento 1.97 m respecto de la división de Marna’s.']},
    {'anchor': [5.05, 2.75], 'sheets': ['A101'], 'color': '#553688',
     'text': ['PASE: línea → P-1 (paso libre ≥0.90) → pase caliente al sur de la barra (≈2 m)',
              'P-1 es la única conexión cocina/salón: vaivén con visor.']},
    {'anchor': [1.65, 0.98], 'sheets': ['A101'], 'color': '#8f4500',
     'text': ['Mesa inox 140 × 70 + horno de mesa (muro norte, junto a freidoras)',
              'Horno de piso: exige división en X ≈ 5.1 — DIMENSION TO VERIFY.']},
    {'anchor': [2.75, 5.45], 'sheets': ['A101'], 'color': '#17737a',
     'text': ['WASHING en la ubicación existente de PILAS — VERIFY ON SITE',
              'Fregadero 2T, lavamanos y mop sink sobre drenajes existentes.']},
    {'anchor': [2.3, 10.4], 'sheets': ['A101'], 'color': '#1a55b0',
     'text': ['COLD PREP concentrado en la antigua PASTELERÍA',
              'Refri 2P · congelador · mesa fría · mesa · estanterías · almacén seco.']},
    {'anchor': [3.01, 11.3], 'sheets': ['A101', 'A102'], 'color': '#b00020',
     'text': ['PS-1 PUERTA DE SERVICIO CONDICIONAL — VERIFY ON SITE',
              'Reemplaza parte de la ventana sur: aprobación de la administración.']},
    {'anchor': [15.8, 1.35], 'sheets': ['A101'], 'color': '#6d5f08',
     'text': ['DELIVERY: retiro en la recepción de la entrada',
              'El repartidor no cruza el salón; pedidos empacados en el pase.']},
    {'anchor': [0.45, 0.45], 'sheets': ['A101', 'A102'], 'color': '#555555',
     'text': ['Ductos en envolvente de columna A1 — VERIFY ON SITE',
              'Altura libre de cielo (3.00 supuesta) — VERIFY ON SITE.']},
    # A-102
    {'anchor': [6.348, 2.2], 'sheets': ['A102'], 'color': '#d62828',
     'text': ['WALL TO DEMOLISH · IP-KB división liviana de Marna’s (X = 6.30)',
              '10 cm, sin trama de mampostería ni columnas → liviana.']},
    {'anchor': [3.58, 5.036], 'sheets': ['A102'], 'color': '#d62828',
     'text': ['WALL TO DEMOLISH · IP-P0b, tramo cocina/pilas',
              'Abre el paso directo puerta P-1 → lavado.']},
    {'anchor': [1.51, 8.71], 'sheets': ['A102'], 'color': '#d62828',
     'text': ['WALL TO DEMOLISH (parcial) · remate de IP-P2, 0.35 m',
              'Libera la boca del pasillo limpio hacia cold prep.']},
    {'anchor': [P1 + 0.28, 1.2], 'sheets': ['A102'], 'color': '#111111',
     'text': ['NEW PROPOSED WALL · NW-1 muro bajo h 1.00 + vidrio',
              'Aterriza sobre el muro existente EW-E1; vidrio TO BE ENGINEERED.']},
    {'anchor': [3.6, 3.62], 'sheets': ['A102'], 'color': '#111111',
     'text': ['NEW PROPOSED WALL · NW-2 panel térmico incombustible',
              'Entre parrilla y puerta P-1, de piso a campana.']},
    {'anchor': [5.0, 4.05], 'sheets': ['A102'], 'color': '#111111',
     'text': ['P-1 · puerta de vaivén, vano 1.02, paso libre ≥0.90, con visor (nuevo vano)',
              'P-2 · puerta de cierre automático en el vano existente pasillo limpio → lavado']},
    {'anchor': [3.0, 0.67], 'sheets': ['A102'], 'color': '#d62828',
     'text': ['Campana existente de Marna’s 3.80 × 1.10 A RETIRAR',
              'Sellar collarines y ductos no reutilizados; inspeccionar el riser si se reutiliza (EXT-1).']},
    {'anchor': [2.65, 5.036], 'sheets': ['A102'], 'color': '#d62828',
     'text': ['Ventana de platos existente (D-DISH-old): retirar antepecho o mostrador si existe',
              'para dejar el paso libre de 1.86 m hacia lavado — VERIFY ON SITE.']},
    {'anchor': [1.51, 6.3], 'sheets': ['A102'], 'color': '#5c5c58',
     'text': ['EXISTING WALL · se mantienen perímetro, columnas, escalera y ductos',
              'y las divisiones IP-P0a, IP-P1, IP-P2, IP-P3 (separan limpio / sucio).',
              'Confirmar en sitio que no alojan instalaciones — VERIFY ON SITE.']},
]

# ---------------------------------------------------------------- notes
L['sheet_notes'] = [
    '!Anteproyecto: revisar, verificar en sitio y firmar por profesional CFIA.',
    'Geometría base: vectores del PDF Marna’s (1:50). Cotas ±2 cm.',
    'Hot line fija sobre la división con el salón (cliente).',
    'BBQ production (smoker + holding) en el muro del fondo.',
    'Lavado en PILAS existentes; cold prep en ex-PASTELERÍA.',
    '* / punto rojo = DIMENSION TO VERIFY (equipo sin ficha).',
    'Altura libre de cielo y ductos existentes: VERIFY ON SITE.',
    'Extracción: 2 sistemas + chimenea smoker — TO BE ENGINEERED.',
    'Capacidad máxima 49 personas (ver A-104). Barra: solo servicio.',
    'Baños: comunes del centro comercial (autorización: VERIFY).',
]
L['structure_notes'] = [
    'Se mantienen columnas A1, B1, C1, A2, escalera, ductos y perímetro.',
    'Solo se demuelen divisiones livianas de 10 cm (IP-KB, IP-P0b).',
    'IP-KB no tiene trama de mampostería ni columnas: liviana.',
    'IP-P0a, IP-P1, IP-P2 e IP-P3 se conservan (separan limpio/sucio).',
    'P-2: puerta de cierre automático en el vano pasillo → lavado.',
    'La nueva división aterriza sobre el muro existente EW-E1.',
    'Campana existente de Marna’s: se retira.',
    '!Confirmar en sitio que ninguna división aloja instalaciones.',
    'PS-1 solo con aprobación: abrir vano en ventana sur.',
]
L['flow_notes'] = [
    'Limpio: cold prep → pasillo oeste → línea → P-1 → pase.',
    'Sucio: salón → P-1 → gira al sur → fregadero (≈1.5 m).',
    'P-2 (cierre automático) separa el pasillo limpio del lavado.',
    'Smoker → holding → línea / pase por el frente del muro oeste.',
    '!P-1 es la única conexión cocina/salón: platos y loza comparten',
    '!puerta (vano 1.02, circulación por la derecha).',
]
L['notes'] = [
    'Zonificación fijada por el cliente (corrección 2): hot line sobre la división con el salón; mesa de trabajo + horno en muro norte junto a las freidoras; smoker + holding en el muro del fondo (oeste); lavado en PILAS; cold prep en PASTELERÍA.',
    'Nueva división en X = 4.325 (cara cocina): corrimiento 1.97 m respecto de la división de Marna’s (X = 6.298). Limitante: línea caliente de 3.80 m + puerta 0.90 en 4.87 m de fondo, y 1.10 m libres frente a las freidoras hasta la mesa de trabajo del muro norte.',
    'Si el horno es de piso (≈80–90 cm) en lugar de horno de mesa, no cabe junto a la mesa en el muro norte sin invadir el frente de las freidoras: la división tendría que quedar en X ≈ 5.1 (corrimiento ≈1.2 m) o el horno ir al muro oeste.',
    'Extracción: NFPA 96 cap. 14 exige que la parrilla de carbón/leña tenga campana, ducto, ventilador y descarga independientes. Se dibujan 2 campanas contiguas: campana 1 ≈2.30 × 1.00 sobre freidoras, plancha y cocina (con supresión UL 300 y corte de gas) y campana 2 ≈1.55 × 1.10 solo sobre la parrilla (arrestachispas). El smoker lleva chimenea propia. La campana única 3.60 × 0.90 cotizada ya no aplica. Dimensiones, caudales, aire de reposición y supresión: TO BE ENGINEERED.',
    'Freidoras junto a la plancha (no junto a llama abierta): cumple la separación típica de 40 cm respecto de parrilla y quemadores; confirmar con ingeniería.',
    'Parrilla contra la división: base incombustible con cámara de aire y vidrio con resistencia térmica/cortafuego — especificación TO BE ENGINEERED.',
    'Pase: la puerta P-1 es la única conexión cocina/salón (la línea ocupa el resto de la división). Los platos salen por P-1 al pase caliente del extremo sur de la barra (≈2 m).',
    'Smoker: chimenea independiente (no conectar al ducto existente), carga de leña y retiro de cenizas por el frente; leña y cenizas entran/salen por PS-1 (si se aprueba) o por la entrada principal fuera de horario.',
]

with open(os.path.join(ROOT, 'data', 'layout.json'), 'w') as fh:
    json.dump(L, fh, indent=1, ensure_ascii=False)
seats = len(CH) + sum(b['seats'] for b in BQ)
print(f'wrote data/layout.json · {len(E)} equipos · {len(T)} mesas · {seats} asientos')
