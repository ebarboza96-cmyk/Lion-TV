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
DOOR = (4.03, 4.93)   # kitchen door P-1 (0.90 clear) at the south end of the partition
LINE_D = 0.80         # depth of range / plancha / fryers (TBV)
PARR_D = 0.90         # depth of parrilla (TBV)

L = {
    'meta': {
        'name': 'LAVA test-fit v2 · zonificación operativa del cliente',
        'strategy': 'Hot line sobre la división con el salón; BBQ (smoker + holding) al fondo; lavado en PILAS; cold prep en PASTELERÍA',
        'version': '2.0',
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
             'Especificación térmica/cortafuego del vidrio y del muro detrás de la parrilla TO BE ENGINEERED.'},
    {'id': 'NW-2', 'rect': [P0 - PARR_D, 3.916, P0, 3.966], 'type': 'partition', 'h': 2.05,
     'short': 'Panel térmico', 'note': 'Panel lateral incombustible piso-campana entre parrilla y puerta (protección térmica y cierre lateral de campana).'},
]
L['new_openings'] += [
    {'id': 'P-1', 'type': 'double_acting_door', 'rect': [P0, DOOR[0], P1, DOOR[1]], 'width': 0.90, 'label': 'P-1',
     'note': 'Puerta de cocina de vaivén 0.90 con visor. Entrada de loza sucia y salida de platos al pase.'},
    {'id': 'PS-1', 'type': 'service_door', 'rect': [2.56, 11.486, 3.46, 11.616], 'width': 0.90, 'label': 'PS-1',
     'hinge': [3.46, 11.616], 'closed_to': [2.56, 11.616], 'swing_to': [3.46, 12.516], 'conditional': True,
     'note': 'PUERTA DE SERVICIO CONDICIONAL: sustituye parte de la ventana sur existente (hacia pasillo del edificio). '
             'Requiere aprobación de la administración y revisión estructural — VERIFY ON SITE.'},
]
L['demolish'].append({'id': 'IP-P2', 'rect': [1.46, 8.536, 1.56, 8.886], 'note': 'Recorte del remate liviano de IP-P2 bajo IP-P3 (35 cm) para liberar la boca del pasillo limpio.'})
L['demolish'].append({'id': 'EW-S2', 'rect': [3.365, 11.486, 3.46, 11.616], 'conditional': True,
                      'note': 'Solo si se aprueba PS-1: ampliar vano 9.5 cm en muro sur.'})

# ---------------------------------------------------------------- B · HOT LINE / SHOW KITCHEN
FL = P0 - LINE_D
eq('H1', 'parrilla', 'Parrilla argentina', 'fire', [P0 - PARR_D, 2.416, P0, 3.916], 'W', 1.20, 0.90, True,
   note='Carbón/leña. 150 cm; fondo y brasero TBV. Pieza visual principal: de frente al salón tras el vidrio.')
eq('H2', 'cocina_4q', 'Cocina LPG 4 quemadores', 'fire', [FL, 1.616, P0, 2.416], 'W', 1.10, 0.90, True, plan_label='Cocina 4Q LPG',
   note='4 quemadores extragrandes; frente 80 cm TBV.')
eq('H3', 'plancha', 'Plancha', 'fire', [FL, 0.916, P0, 1.616], 'W', 1.10, 0.90, True, note='Módulo 70 cm; fondo TBV.')
eq('H4', 'freidora_1', 'Freidora 1', 'fire', [FL, 0.516, P0, 0.916], 'W', 1.10, 0.90, True,
   note='Freidora independiente; huella comercial 40×80 — DIMENSION TO VERIFY.')
eq('H5', 'freidora_2', 'Freidora 2', 'fire', [FL, YN, P0, 0.516], 'W', 1.10, 0.90, True,
   note='Freidora independiente; huella comercial 40×80 — DIMENSION TO VERIFY.')
eq('HD', 'hood', 'Campana línea caliente', 'hood', [P0 - 1.10, YN, P0, 3.966], None, 0, 0.6, True, overhead=True, closed_ends=True, label_side='outside',
   note='Cubre parrilla + cocina + plancha + 2 freidoras (3.80 m) con voladizo frontal 20 cm: ≈3.85 × 1.10 m. '
        'La propuesta Aceros VB 3.60 × 0.90 NO cubre esta línea. EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED.')
eq('K1', 'mesa_1', 'Mesa de trabajo inox', 'prep', [0.875, YN, 2.425, 0.816], 'S', 1.00, 0.90, False, plan_label='Mesa inox + K2 horno',
   note='Apoyo / mise en place / bandejeo / terminación junto a la línea. 155 × 70 (ajustada para dejar 1.10 m frente a freidoras).')
eq('K2', 'oven', 'Horno (sobre mesa)', 'fire', [1.675, YN, 2.425, 0.816], None, 0, 1.55, True, stack_with='K1', no_label=True,
   note='Horno de convección/combi de mesa ≈75 × 70 TBV. Extracción del horno según tipo — TO BE ENGINEERED.')
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
eq('W4', 'mesa_opt', 'Mesa de apoyo / escurrido', 'wash', [1.56, 5.20, 2.16, 7.07], 'E', 1.00, 0.90, False,
   note='187 × 60 (mesa opcional del programa) contra la división existente P1: racks limpios / apoyo.')
eq('W5', 'shelf_wash', 'Estante loza limpia', 'storage', [2.10, 8.086, 3.30, 8.436], 'N', 0.80, 1.80, False,
   note='120 × 35, 4 niveles.')

# ---------------------------------------------------------------- A · COLD PREP (former PASTELERIA + clean corridor)
eq('A1', 'fridge_2d', 'Refrigerador 2 puertas', 'cold', [3.81, 8.95, 4.51, 10.40], 'W', 0.90, 2.00, False, note='145 × 70 × 200.')
eq('A2', 'freezer_1d', 'Congelador vertical', 'cold', [3.81, 10.40, 4.51, 11.15], 'W', 0.90, 2.00, False, plan_label='Congelador', note='75 × 70 × 200.')
eq('A3', 'mesa_fria', 'Mesa fría refrigerada', 'cold', [0.72, 10.786, 2.52, 11.486], 'N', 1.00, 0.90, False, note='180 × 70.')
eq('A4', 'mesa_2', 'Mesa de trabajo inox (prep fría)', 'prep', [0.0, 9.55, 0.70, 10.75], 'E', 1.00, 0.90, False, plan_label='Mesa inox prep',
   note='120 × 70 (reducida de 180 para dejar libre la boca del pasillo limpio; ajuste permitido por el cliente).')
eq('A5', 'shelf_4', 'Estantería 4 niveles', 'storage', [2.10, 8.536, 3.80, 8.886], 'S', 0.80, 1.80, False, note='170 × 35.')
eq('A6', 'shelf_dry', 'Almacén seco (estantería)', 'storage', [-0.085, 5.10, 0.365, 7.90], 'E', 0.85, 2.00, False,
   note='280 × 45 a lo largo del pasillo limpio (muro oeste).')
# ---------------------------------------------------------------- C · BAR / POS
eq('C1', 'barra', 'Barra / caja + bebidas', 'bar', [5.40, YN, 6.05, 1.70], 'E', 0.90, 1.05, False, plan_label='Barra / caja + C3 POS',
   note='Barra compacta: caja, POS y apoyo de bebidas (enfriador bajo barra). Pileta de barra: extender drenaje existente WP5 ≈1 m — VERIFY.')
eq('C2', 'pass', 'Pase / pickup caliente', 'bar', [5.40, 1.70, 6.05, 2.35], 'E', 0.90, 1.05, False, plan_label='Pase',
   note='Repisa de pase con lámparas de calor: se carga desde el pasillo de barra (lado cocina) y se retira desde el salón.')
eq('C3', 'pos', 'POS', 'bar', [5.50, 0.95, 5.95, 1.40], None, 0, 1.10, False, stack_with='C1', no_label=True)
eq('D2', 'delivery_staging', 'Recepción + staging / retiro delivery', 'delivery', [15.45, 0.40, 16.20, 1.00], 'S', 0.60, 1.05, False, plan_label='Recep. + delivery',
   note='Atril de recepción con repisa para pedidos listos: el repartidor retira en la entrada sin cruzar el salón. Los pedidos se empacan en el pase.')

# ---------------------------------------------------------------- D · DINING
T, CH, BQ = L['tables'], L['chairs'], L['banquettes']
ROW_N = dict(bq=(YN, YN + 0.55), tb=(0.716, 1.416), ch=(1.466, 1.916), facing='N')
ROW_S = dict(bq=(YS - 0.55, YS), tb=(3.686, 4.386), ch=(3.186, 3.636), facing='S')


def row(prefix, x0, x1, R, pattern):
    """pattern: list of table widths (0.70 = 2-top, 1.20 = 4-top); gaps between joinable 2-tops 0.20, else 0.35."""
    x = x0
    seats_bq = 0
    n = 0
    prev = None
    ids = []
    for w in pattern:
        gap = 0.20 if (prev == 0.70 and w == 0.70) else (0.35 if prev is not None else 0.0)
        x += gap
        if x + w > x1 + 1e-6:
            break
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
        if a['seats'] == 2 and b['seats'] == 2 and round(b['rect'][0] - a['rect'][2], 2) <= 0.21:
            a.setdefault('joinable_with', []).append(b['id'])
    return x, seats_bq


# north row: from east of column B1 to before the entrance swing
N_PATTERN = [0.70, 0.70, 1.20, 0.70, 0.70, 1.20, 0.70, 0.70]
xn_end, sn = row('TN', 8.20, 15.30, ROW_N, N_PATTERN)
BQ.append({'id': 'BQ-N', 'rect': [8.15, YN, round(xn_end + 0.05, 3), YN + 0.55], 'seats': sn, 'back': 'N'})
# south row: from the service zone to before the entrance swing
S_PATTERN = [0.70, 0.70, 1.20, 0.70, 0.70, 1.20, 0.70, 0.70, 1.20]
xs_end, ss = row('TS', 6.60, 15.30, ROW_S, S_PATTERN)
BQ.append({'id': 'BQ-S', 'rect': [6.55, YS - 0.55, round(xs_end + 0.05, 3), YS], 'seats': ss, 'back': 'S'})

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
     'poly': [[P1, YN], [6.95, YN], [6.95, 2.45], [P1, 2.45]], 'label_at': [6.52, 1.25], 'label_size': 3.6, 'label_at_flows': [6.5, 0.6]},
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
    {'id': 'R-dirty', 'kind': 'dirty', 'label': 'Salón → puerta P-1 → lavado', 'pts': [[15.0, 2.62], [7.0, 2.6], [6.36, 2.8], [5.5, 4.0], [5.1, 4.48], [3.9, 4.48], [2.9, 4.8], [2.73, 5.3], [2.73, 5.9]], 'min_width': 0.90},
    {'id': 'R-clean', 'kind': 'clean', 'label': 'Frío → prep → pasillo limpio → línea', 'pts': [[3.3, 9.7], [1.9, 9.7], [0.95, 8.95], [0.89, 8.3], [0.89, 5.3], [0.9, 4.75], [1.3, 4.3], [2.7, 3.8], [2.9, 1.3]], 'min_width': 1.00},
    {'id': 'R-bbq', 'kind': 'clean', 'label': 'Smoker → holding → línea / pase', 'pts': [[1.15, 1.7], [1.15, 2.85], [2.6, 3.7], [2.8, 4.4]], 'min_width': 1.00},
    {'id': 'R-deliv', 'kind': 'delivery', 'label': 'Pase → staging en recepción (retiro sin cruzar salón)', 'pts': [[4.95, 3.0], [6.36, 2.8], [7.0, 2.5], [15.0, 2.45], [15.75, 1.55]], 'min_width': 0.90},
    {'id': 'R-fuel', 'kind': 'fuel', 'label': 'Leña / cenizas ↔ PS-1 (condicional, fuera de horario)', 'pts': [[3.05, 11.3], [3.1, 10.5], [2.2, 9.6], [0.95, 8.95], [0.89, 8.3], [0.89, 5.3], [0.95, 3.9]], 'min_width': 0.90},
]
L['checks'] = [
    ['entrance', 'barra_front', 1.10], ['pass_dining', 'dining_far', 1.10], ['kitchen_door', 'dish_drop', 0.90],
    ['cold_storage', 'line', 1.00], ['line', 'kitchen_door', 0.90], ['smoker_front', 'kitchen_door', 0.90],
    ['expo_pass', 'kitchen_door', 0.90], ['delivery_staging', 'expo_pass', 0.90], ['service_door', 'fuel', 0.90],
]

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
    {'type': 'firewood_niche', 'rect': [P0, 2.52, P1, 3.22], 'face': 'E', 'z': 0.12, 'h': 0.86},
    {'type': 'planter', 'rect': [P0, 3.30, P1, 3.90], 'face': 'E', 'h': 1.0},
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
     'text': 'Entrando por la puerta P-1, la línea queda a la derecha bajo una sola campana. Mesa de trabajo con horno en el muro norte, junto a las freidoras. Pasillo de trabajo ≥1.10 m.',
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
                  (2.416, 3.916, '1.50'), (DOOR[0], DOOR[1], '0.90')]:
    dim([FL if b_ <= 2.416 else P0 - PARR_D, a_], [FL if b_ <= 2.416 else P0 - PARR_D, b_], 2.85, t)
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
dim([2.425, 0.40], [FL, 0.40], 0.40, '1.10')
dim([0.665, 1.25], [FL, 1.25], 1.25, f'{FL - 0.665:.2f} libre')
dim([2.16, 6.20], [3.31, 6.20], 6.20, '1.15')
dim([0.365, 6.70], [1.46, 6.70], 6.70, '1.10')
dim([0.70, 10.05], [3.81, 10.05], 10.05, None)
dim([3.10, 8.886], [3.10, 10.786], 3.10, None)
# dining / bar
dim([12.2, 1.916], [12.2, 3.186], 12.2, '1.27 pasillo principal')
dim([P1, 0.95], [5.40, 0.95], 0.95, '0.93')
dim([9.8, 0.716], [10.15, 0.716], 0.716, None)

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
              'Campana ≈3.85 × 1.10 sobre toda la hot line (3.80 m).',
              'La campana 3.60 × 0.90 propuesta no cubre la línea.']},
    {'anchor': [0.95, 1.65], 'sheets': ['A101'], 'color': '#6e2508',
     'text': ['SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED',
              'Chimenea propia; leña, cenizas y drenaje de grasa por el frente.']},
    {'anchor': [P1 + 0.28, 3.55], 'sheets': ['A101'], 'color': '#111111',
     'text': ['NEW PROPOSED WALL · división cocina/salón en X = 4.33',
              'Muro bajo sólido h 1.00 + vidrio (spec. térmica TO BE ENGINEERED).',
              'Corrimiento 1.97 m respecto de la división de Marna’s.']},
    {'anchor': [5.05, 2.75], 'sheets': ['A101'], 'color': '#553688',
     'text': ['PASE: línea → P-1 (0.90) → pase caliente al sur de la barra (≈2 m)',
              'P-1 es la única conexión cocina/salón: vaivén con visor.']},
    {'anchor': [1.65, 0.98], 'sheets': ['A101'], 'color': '#8f4500',
     'text': ['Mesa inox 155 × 70 + horno de mesa (muro norte, junto a freidoras)',
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
     'text': ['P-1 · puerta de vaivén 0.90 con visor (nuevo vano)']},
    {'anchor': [1.51, 6.3], 'sheets': ['A102'], 'color': '#5c5c58',
     'text': ['EXISTING WALL · se mantienen perímetro, columnas, escalera y ductos',
              'y las divisiones IP-P0a, IP-P1, IP-P2, IP-P3 (separan limpio / sucio).',
              'Confirmar en sitio que no alojan instalaciones — VERIFY ON SITE.']},
]

# ---------------------------------------------------------------- notes
L['sheet_notes'] = [
    '!Test-fit conceptual: validar con arquitecto e ingenierías.',
    'Geometría base: vectores del PDF Marna’s (1:50). Cotas ±2 cm.',
    'Hot line fija sobre la división con el salón (cliente).',
    'BBQ production (smoker + holding) en el muro del fondo.',
    'Lavado en PILAS existentes; cold prep en ex-PASTELERÍA.',
    '* / punto rojo = DIMENSION TO VERIFY (equipo sin ficha).',
    'Altura libre de cielo y ductos existentes: VERIFY ON SITE.',
    'Campana, aire de reposición, supresión y gas: TO BE ENGINEERED.',
    'Egreso, sentido de puertas y ocupación: validar Bomberos/NFPA 101.',
]
L['structure_notes'] = [
    'Se mantienen columnas A1, B1, C1, A2, escalera, ductos y perímetro.',
    'Solo se demuelen divisiones livianas de 10 cm (IP-KB, IP-P0b).',
    'IP-KB no tiene trama de mampostería ni columnas: liviana.',
    'IP-P0a, IP-P1, IP-P2 e IP-P3 se conservan (separan limpio/sucio).',
    'La nueva división aterriza sobre el muro existente EW-E1.',
    '!Confirmar en sitio que ninguna división aloja instalaciones.',
    'PS-1 solo con aprobación: abrir vano en ventana sur.',
]
L['flow_notes'] = [
    'Limpio: cold prep → pasillo oeste → línea → P-1 → pase.',
    'Sucio: salón → P-1 → gira al sur → fregadero (≈1.5 m).',
    'La ruta sucia no pasa por el pasillo limpio ni por cold prep.',
    'Smoker → holding → línea / pase por el frente del muro oeste.',
    '!P-1 es la única conexión cocina/salón: platos y loza comparten puerta.',
]
L['notes'] = [
    'Zonificación fijada por el cliente (corrección 2): hot line sobre la división con el salón; mesa de trabajo + horno en muro norte junto a las freidoras; smoker + holding en el muro del fondo (oeste); lavado en PILAS; cold prep en PASTELERÍA.',
    'Nueva división en X = 4.325 (cara cocina): corrimiento 1.97 m respecto de la división de Marna’s (X = 6.298). Limitante: línea caliente de 3.80 m + puerta 0.90 en 4.87 m de fondo, y 1.10 m libres frente a las freidoras hasta la mesa de trabajo del muro norte.',
    'Si el horno es de piso (≈80–90 cm) en lugar de horno de mesa, no cabe junto a la mesa en el muro norte sin invadir el frente de las freidoras: la división tendría que quedar en X ≈ 5.1 (corrimiento ≈1.2 m) o el horno ir al muro oeste.',
    'Campana: la línea completa mide 3.80 m y la parrilla tiene 0.90 m de fondo; la campana 3.60 × 0.90 propuesta no la cubre. Se dibuja ≈3.85 × 1.10 como referencia; dimensiones, CFM, aire de reposición, filtros, separación de combustible sólido y supresión: TO BE ENGINEERED.',
    'Freidoras junto a la plancha (no junto a llama abierta): cumple la separación típica de 40 cm respecto de parrilla y quemadores; confirmar con ingeniería.',
    'Parrilla contra la división: base incombustible con cámara de aire y vidrio con resistencia térmica/cortafuego — especificación TO BE ENGINEERED.',
    'Pase: la puerta P-1 es la única conexión cocina/salón (la línea ocupa el resto de la división). Los platos salen por P-1 al pase caliente del extremo sur de la barra (≈2 m).',
    'Smoker: chimenea independiente (no conectar al ducto existente), carga de leña y retiro de cenizas por el frente; leña y cenizas entran/salen por PS-1 (si se aprueba) o por la entrada principal fuera de horario.',
]

with open(os.path.join(ROOT, 'data', 'layout.json'), 'w') as fh:
    json.dump(L, fh, indent=1, ensure_ascii=False)
seats = len(CH) + sum(b['seats'] for b in BQ)
print(f'wrote data/layout.json · {len(E)} equipos · {len(T)} mesas · {seats} asientos')
