"""M-101 / M-102 · Instalaciones mecánicas (esquema) para revisión del profesional responsable.

Plug-in de lámina extra: sheets(ex, lay, val) -> [{id, file, title, order, svg}]
  M-101 · Hidrosanitario (esquema)                                  order 401  lava_M101_hidrosanitario.svg
  M-102 · Gas, extracción, aire de reposición y supresión (esquema) order 402  lava_M102_gas_extraccion.svg
También escribe data/mech_calcs.json (caudales de campana, ductos, aire de reposición, gas, agua caliente, trampa de grasa,
cuadro de aparatos).

Todo se ubica desde data/existing.json + data/layout.json: equipos (W1, W2, W3, K3, C1, GT-1, H1..H5, HD-1, HD-2, S1, K1...),
puntos húmedos existentes WP1..WP6, muros, ductos S1/S3/S-PIL, puerta P-1, zonas y layout.mep (gas, exhaust, makeup_air).
Los elementos nuevos que no existen en los datos (coladeras, calentadores, llave de manguera, gabinete de supresión, detector
de gas) se derivan de esa geometría (centro del piso libre de cada zona, muros, frentes de equipos).

ANTEPROYECTO / PRELIMINAR: diámetros, caudales y citas normativas a validar por el profesional responsable (CFIA).
Las tasas de extracción son valores de referencia de diseño (ASHRAE 154 / IMC 507 para campanas no listadas; rangos típicos de
campanas listadas UL 710 según guías CKV / fabricantes), no una selección de equipo.

Standalone:  python3 tools/sheets/s401_mecanica.py   (solo recalcula y escribe el JSON)
"""
import json
import math
import os
import sys

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polylabel, unary_union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lavageo import R, ROOT, load_existing, load_json, premises, seat_count, standing_existing_walls  # noqa: E402
from plan_svg import COL, FONT, LEGEND_WALLS, MONO, S, Sheet, f, rect_el, sw_line, sw_rect, sx, sy, text, tw  # noqa: E402

# ============================================================================ reference values (PRELIMINAR)
FT = 0.3048
CFM_LS = 0.47194745                       # 1 cfm = 0.4719 L/s
LSM_PER_CFMFT = CFM_LS / FT               # 1 cfm/ft = 1.548 L/s por metro de campana
BTU_KW = 3412.14                          # BTU/h por kW
# Servicio de la campana (ASHRAE 154): nombre, tasa mínima campana mural NO listada (cfm/pie; ASHRAE 154 / IMC 507),
# rango típico de campanas murales LISTADAS UL 710 (cfm/pie; guías CKV / fabricantes).
DUTY = {
    'light': ('liviano', 200, (150, 200)),
    'medium': ('medio', 300, (200, 300)),
    'heavy': ('pesado', 400, (200, 400)),
    'extra_heavy': ('extra-pesado (combustible sólido)', 550, (350, 550)),
}
DUTY_ORDER = ['light', 'medium', 'heavy', 'extra_heavy']
KEY_DUTY = {'parrilla': 'extra_heavy', 'smoker': 'extra_heavy', 'cocina_4q': 'medium', 'plancha': 'medium',
            'freidora_1': 'medium', 'freidora_2': 'medium', 'oven': 'light', 'holding': 'light'}
V_DESIGN = 7.5          # m/s velocidad de diseño en ducto de grasa (práctica usual 7.6–9.1 m/s ≈ 1500–1800 fpm)
V_MIN = 2.54            # m/s mínimo NFPA 96 §8.2.1.1 (500 fpm) — verificar edición
V_MAX = 12.7            # m/s límite práctico (ruido / pérdida de carga)
MUA_PCTS = (0.80, 0.85, 0.90)
MUA_DESIGN = 0.85
V_MUA = 6.0             # m/s velocidad de diseño del ducto principal de reposición
# Gas: potencias típicas de catálogo (reemplazar por fichas técnicas)
GAS_TYP = {
    'cocina_4q': (35.2, '4 quemadores × 8.8 kW (30 000 BTU/h)'),
    'plancha': (14.7, 'plancha 70 cm, 2 quemadores × 25 000 BTU/h'),
    'freidora_1': (26.4, 'freidora 40 cm ≈ 18 kg de aceite, 90 000 BTU/h'),
    'freidora_2': (26.4, 'freidora 40 cm ≈ 18 kg de aceite, 90 000 BTU/h'),
}
HHV_LPG_KG = 50.0       # MJ/kg (GLP / propano, poder calorífico superior, referencia)
HHV_LPG_M3 = 93.2       # MJ/m³ (propano gaseoso)
HHV_NG_M3 = 37.3        # MJ/m³ (gas natural)
# NFPA 54 (tablas de referencia) · tubería metálica cédula 40 · ΔP 0.5" c.a.
#   GLP: propano sin diluir, 11" c.a. de entrada — capacidad en kBTU/h ; GN: 0.60 g.e., < 2 psi — capacidad en pie³/h (≈ kBTU/h)
PIPE_LPG = {10: {'1/2"': 291, '3/4"': 608, '1"': 1150, '1-1/4"': 2350}, 20: {'1/2"': 200, '3/4"': 418, '1"': 787, '1-1/4"': 1620},
            30: {'1/2"': 160, '3/4"': 336, '1"': 632, '1-1/4"': 1300}, 40: {'1/2"': 137, '3/4"': 287, '1"': 541, '1-1/4"': 1110},
            50: {'1/2"': 122, '3/4"': 255, '1"': 480, '1-1/4"': 985}}
PIPE_NG = {10: {'1/2"': 172, '3/4"': 360, '1"': 678, '1-1/4"': 1390}, 20: {'1/2"': 118, '3/4"': 247, '1"': 466, '1-1/4"': 957},
           30: {'1/2"': 95, '3/4"': 199, '1"': 374, '1-1/4"': 768}, 40: {'1/2"': 81, '3/4"': 170, '1"': 320, '1-1/4"': 657},
           50: {'1/2"': 72, '3/4"': 151, '1"': 284, '1-1/4"': 583}}
PIPE_ORDER = ['1/2"', '3/4"', '1"', '1-1/4"']
# Agua caliente: ASHRAE Handbook HVAC Applications (Service Water Heating), restaurante de servicio completo:
# 1.5 gal (5.7 L) a 60 °C por comida en la hora máxima.
HW_L_PER_MEAL = 5.7
MEALS_PER_SEAT_PEAK = 1.0
HW_DT = 40.0             # K (20 → 60 °C)
HEATERS = [(80, 3.0), (100, 4.5), (150, 6.0), (200, 6.0), (300, 9.0)]
# Trampa de grasa (PDI G-101, referencia): tanque supuesto 0.50 × 0.50 × 0.30 m, llenado 75 %, vaciado en 1 o 2 min
SINK_TANK = (0.50, 0.50, 0.30)
PDI_SIZES = [4, 7, 10, 15, 20, 25, 35, 50, 75, 100]    # gpm
GPM_LS = 0.0630902

FLAG_ENG = 'EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED'
FLAG_SMOKER = 'SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED'
PRELIM = 'PRELIMINAR — TO BE ENGINEERED'

# ============================================================================ colours
C_AF = '#1f63c6'
C_AC = '#d0312d'
C_DR = '#6d4c1d'
C_GR = '#c2560c'
C_WP = '#17737a'
C_GAS = '#b8860b'
C_GAS_D = '#5a4300'
C_EXT1 = '#b35900'
C_EXT2 = '#8a2a07'
C_EXT3 = '#5b4636'
C_MUA = '#0f7f9c'
C_SUP = '#c1121f'
C_RED = '#b00020'
C_TXT = '#262626'
C_FIX_F, C_FIX_S = COL['wash']


# ============================================================================ small geometry helpers
def ctr(r):
    return ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)


def eqd(lay):
    return {e['id']: e for e in lay.get('equipment', [])}


def _offset(pts, d):
    return list(LineString(pts).offset_curve(d, join_style=2).coords)


def wrap(s, n):
    """Greedy word wrap to lines of at most n characters."""
    out, cur = [], ''
    for w in str(s or '').split():
        if cur and len(cur) + 1 + len(w) > n:
            out.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur:
        out.append(cur)
    return out


def _free_pole(ex, lay, zone_ids, snap=None):
    """Centre of the largest free floor area (pole of inaccessibility) of the given zones."""
    prem = premises(ex)
    zp = unary_union([Polygon(z['poly']) for z in lay.get('zones', []) if z['id'] in zone_ids]).intersection(prem)
    obs = [R(e['rect']) for e in lay.get('equipment', []) if not e.get('overhead')]
    obs += [g for _, g in standing_existing_walls(ex, lay)] + [R(w['rect']) for w in lay.get('new_walls', [])]
    obs += [R(c['rect']) for c in ex['columns']]
    free = zp.difference(unary_union(obs).buffer(0.05))
    if free.geom_type == 'MultiPolygon':
        free = max(free.geoms, key=lambda g: g.area)
    p = polylabel(free, 0.01)
    return (round(p.x, 3), round(p.y, 3))


# ============================================================================ calculations
def _pick_rect(a_req, max_ratio=1.5):
    best = None
    for a in range(200, 1201, 50):
        for b in range(200, a + 1, 50):
            if a / b > max_ratio:
                continue
            A = a * b / 1e6
            if A + 1e-9 < a_req:
                continue
            key = (round(A, 4), a - b)
            if best is None or key < best[0]:
                best = (key, a, b)
    return best[1], best[2]


def _pick_round(a_req):
    d = math.sqrt(4 * a_req / math.pi)
    return int(math.ceil(d / 0.025 - 1e-9) * 25)


def _duct(q_ls, v):
    a_req = q_ls / 1000 / v
    a, b = _pick_rect(a_req)
    d = _pick_round(a_req)
    area = a * b / 1e6
    return {'area_required_m2': round(a_req, 4), 'rect_mm': [a, b], 'rect_area_m2': round(area, 4),
            'velocity_rect_ms': round(q_ls / 1000 / area, 2), 'round_mm': d,
            'velocity_round_ms': round(q_ls / 1000 / (math.pi * (d / 1000) ** 2 / 4), 2)}


def _hood_appliances(lay, hood):
    hg = R(hood['rect'])
    out = []
    for e in lay.get('equipment', []):
        if e.get('overhead') or e.get('key') not in KEY_DUTY:
            continue
        if R(e['rect']).intersection(hg).area > 0.02:
            out.append(e)
    return out


def exhaust_calcs(ex, lay):
    eq = eqd(lay)
    mep = lay.get('mep', {})
    rows = []
    for x in mep.get('exhaust', []):
        tgt = eq.get(x.get('serves'))
        row = {'id': x['id'], 'serves': x.get('serves'), 'kind': x.get('kind'), 'collar': x.get('collar'),
               'route': x.get('route'), 'riser': x.get('riser'), 'fan': x.get('fan'), 'note': x.get('note')}
        if tgt and tgt.get('key') == 'hood':
            apps = _hood_appliances(lay, tgt)
            duty = max((KEY_DUTY[a['key']] for a in apps), key=DUTY_ORDER.index) if apps else 'medium'
            x0, y0, x1, y1 = tgt['rect']
            length, depth = max(abs(x1 - x0), abs(y1 - y0)), min(abs(x1 - x0), abs(y1 - y0))
            name, cfm_ft, listed = DUTY[duty]
            rate = cfm_ft * LSM_PER_CFMFT
            q = length * rate
            row.update({
                'hood': tgt['id'], 'hood_length_m': round(length, 3), 'hood_depth_m': round(depth, 3),
                'hood_style': 'mural (canopy contra la división NW-1), extremos cerrados' if tgt.get('closed_ends') else 'mural',
                'appliances': [{'id': a['id'], 'label': a.get('label'), 'duty': KEY_DUTY[a['key']]} for a in apps],
                'duty': duty, 'duty_name': name,
                'rate_cfm_per_ft': cfm_ft, 'rate_Ls_per_m': round(rate, 1),
                'rate_basis': 'ASHRAE 154 / IMC 507: caudal mínimo para campana mural NO listada (referencia de diseño)',
                'listed_range_cfm_per_ft': list(listed),
                'listed_range_Ls': [round(length * listed[0] * LSM_PER_CFMFT), round(length * listed[1] * LSM_PER_CFMFT)],
                'Q_Ls': round(q, 1), 'Q_m3h': round(q * 3.6), 'Q_cfm': round(q / CFM_LS),
                'duct': _duct(q, V_DESIGN), 'v_design_ms': V_DESIGN, 'v_min_ms': V_MIN,
            })
            row['v_ok'] = row['duct']['velocity_rect_ms'] >= V_MIN and row['duct']['velocity_rect_ms'] <= V_MAX
            rows.append(row)
        elif tgt:   # solid-fuel appliance with its own flue (smoker)
            x0, y0, x1, y1 = tgt['rect']
            fr = tgt.get('front')
            front_len = abs(y1 - y0) if fr in ('E', 'W') else abs(x1 - x0)
            deep = abs(x1 - x0) if fr in ('E', 'W') else abs(y1 - y0)
            name, cfm_ft, listed = DUTY['extra_heavy']
            rate = cfm_ft * LSM_PER_CFMFT
            q_alt = front_len * rate
            row.update({
                'appliance': tgt['id'], 'duty': 'extra_heavy', 'duty_name': name,
                'primary': 'Chimenea propia de tiro natural, listada según el fabricante del smoker y NFPA 211; '
                           'diámetro del collarín del equipo (típ. 150–200 mm) — VERIFY ficha',
                'flue_diameter_mm_typical': [150, 200], 'Q_Ls': None,
                'alternative_hood': {
                    'when': 'Si el smoker deja escapar efluentes al abrir la puerta (NFPA 96 cap. 14): campana listada y '
                            'sistema de extracción independiente',
                    'hood_length_m': round(front_len, 3), 'hood_depth_m': round(deep, 3), 'rate_cfm_per_ft': cfm_ft,
                    'rate_Ls_per_m': round(rate, 1), 'Q_Ls': round(q_alt, 1), 'Q_m3h': round(q_alt * 3.6),
                    'Q_cfm': round(q_alt / CFM_LS), 'duct': _duct(q_alt, V_DESIGN)},
            })
            rows.append(row)
    hoods = [r for r in rows if r.get('Q_Ls')]
    tot = sum(r['Q_Ls'] for r in hoods)
    mua = {'basis': 'Aire de reposición 80–90 % del caudal extraído (cocina levemente negativa respecto del salón; '
                    'ΔP ≤ 4.98 Pa NFPA 96 §8.3; con combustible sólido, suministro positivo durante toda la cocción)',
           'exhaust_total_Ls': round(tot, 1), 'exhaust_total_m3h': round(tot * 3.6), 'exhaust_total_cfm': round(tot / CFM_LS),
           'cases': [{'pct': int(round(p * 100)), 'Q_Ls': round(tot * p, 1), 'Q_m3h': round(tot * p * 3.6),
                      'Q_cfm': round(tot * p / CFM_LS), 'transfer_from_dining_Ls': round(tot * (1 - p), 1)} for p in MUA_PCTS],
           'design_pct': int(MUA_DESIGN * 100)}
    q_mua = tot * MUA_DESIGN
    mua['design_Q_Ls'] = round(q_mua, 1)
    mua['duct'] = _duct(q_mua, V_MUA)
    mua['v_design_ms'] = V_MUA
    diffs = lay.get('mep', {}).get('makeup_air', {}).get('diffusers', [])
    if diffs:
        per = q_mua / len(diffs)
        mua['diffusers'] = {'count': len(diffs), 'Q_each_Ls': round(per, 1),
                            'min_face_area_each_m2_at_0.5ms': round(per / 1000 / 0.5, 2),
                            'note': 'Descarga a baja velocidad (≈0.5 m/s o menos cerca de las campanas; guías CKV / ASHRAE) '
                                    'para no perturbar la captura: difusores perforados o pleno perimetral — TO BE ENGINEERED'}
    alt = next((r['alternative_hood'] for r in rows if r.get('alternative_hood')), None)
    if alt:
        mua['if_smoker_hood_required'] = {'extra_exhaust_Ls': alt['Q_Ls'],
                                          'mua_design_Ls': round((tot + alt['Q_Ls']) * MUA_DESIGN, 1)}
    # existing Marna's collar vs EXT-1
    col = (ex.get('existing_hood') or {}).get('collar')
    e1 = next((r for r in hoods if r['id'] == 'EXT-1'), None)
    if col and e1:
        a = abs(col[2] - col[0]) * abs(col[3] - col[1])
        e1['existing_collar'] = {'rect': col, 'section_m': [round(abs(col[2] - col[0]), 3), round(abs(col[3] - col[1]), 3)],
                                 'area_m2': round(a, 3), 'velocity_ms': round(e1['Q_Ls'] / 1000 / a, 2),
                                 'note': 'Compatible por velocidad si el ducto aguas arriba mantiene la sección y cumple NFPA 96 '
                                         '(material, soldadura, cerramiento) — VERIFY ON SITE. El collarín existente queda '
                                         'sobre la nueva división NW-1: requiere transición sobre el cielo.'}
    return rows, mua


def _pipe_for(load_k, table, length_ft):
    col = next((L for L in sorted(table) if L >= length_ft), max(table))
    for d in PIPE_ORDER:
        if table[col][d] >= load_k:
            return d, col
    return PIPE_ORDER[-1] + '+', col


def gas_calcs(ex, lay):
    eq = eqd(lay)
    g = lay.get('mep', {}).get('gas', {})
    cons = []
    for cid in g.get('consumers', []):
        e = eq.get(cid)
        if not e:
            continue
        kw, basis = GAS_TYP.get(e.get('key'), (20.0, 'valor genérico'))
        btu = kw * BTU_KW
        cons.append({'id': cid, 'label': e.get('plan_label') or e.get('label'), 'kW_typ': kw, 'BTUh_typ': round(btu, -3), 'basis': basis,
                     'branch_LPG': _pipe_for(btu / 1000, PIPE_LPG, 10)[0], 'branch_NG': _pipe_for(btu / 1000, PIPE_NG, 10)[0]})
    kw = sum(c['kW_typ'] for c in cons)
    btu_k = kw * BTU_KW / 1000
    path = gas_path(lay, ex)
    plan_len = LineString(path).length if len(path) > 1 else 0.0
    dev = (plan_len + 2.0) * 1.5         # + 2 m de subidas / bajadas, +50 % por accesorios
    dev_ft = dev / FT
    main = {}
    for lbl, L in (('en el local', dev_ft), ('hasta 15 m desde el regulador', 15 / FT)):
        dl, cl = _pipe_for(btu_k, PIPE_LPG, L)
        dn, cn = _pipe_for(btu_k, PIPE_NG, L)
        main[lbl] = {'length_ft_table': cl, 'LPG': dl, 'NG': dn}
    return {
        'source': g.get('source'), 'entry': g.get('entry'), 'entry_note': g.get('entry_note'),
        'main_valve': g.get('main_valve'), 'solenoid': g.get('solenoid'), 'note': g.get('note'),
        'consumers': cons, 'total_kW_typ': round(kw, 1), 'total_BTUh_typ': round(kw * BTU_KW, -3),
        'flow_LPG_kg_h': round(kw * 3.6 / HHV_LPG_KG, 2), 'flow_LPG_m3_h': round(kw * 3.6 / HHV_LPG_M3, 2),
        'flow_NG_m3_h': round(kw * 3.6 / HHV_NG_M3, 2),
        'plan_length_m': round(plan_len, 2), 'developed_length_m': round(dev, 2),
        'main_pipe': main,
        'recommended_main': '1" (25 mm) hierro negro cédula 40 si es GLP; 1-1/4" (32 mm) si es gas natural — ' + PRELIM,
        'table_basis': 'NFPA 54 tablas de capacidad (tubería metálica céd. 40, ΔP 0.5" c.a.; GLP 11" c.a. / GN <2 psi) — '
                       'valores de referencia, verificar edición; para GLP rigen además NFPA 58 y las disposiciones de Bomberos',
        'basis_kW': 'Potencias típicas de catálogo — reemplazar por las fichas técnicas de los equipos (DIMENSION TO VERIFY)',
    }


def manifold_x(lay):
    """X of the gas manifold: middle of the technical space behind the line (back face → partition), else just inside."""
    eq = eqd(lay)
    g = lay.get('mep', {}).get('gas', {})
    cons = [eq[c] for c in g.get('consumers', []) if c in eq]
    if not cons:
        return None
    back = max(max(e['rect'][0], e['rect'][2]) for e in cons)
    walls = [min(w['rect'][0], w['rect'][2]) for w in lay.get('new_walls', []) if min(w['rect'][0], w['rect'][2]) >= back - 1e-6]
    wall = min(walls) if walls else None
    if wall is not None and wall - back >= 0.05:
        return (back + wall) / 2
    return back - 0.08


def gas_path(lay, ex=None):
    """Main valve / wall entry (outside → inside) → solenoid → manifold behind the line → farthest consumer (model m)."""
    eq = eqd(lay)
    g = lay.get('mep', {}).get('gas', {})
    cons = [eq[c] for c in g.get('consumers', []) if c in eq]
    if not cons or not g.get('entry'):
        return []
    xm = manifold_x(lay)
    prem = premises(ex or load_existing())
    head = [tuple(p) for p in (g.get('entry'), g.get('main_valve')) if p]
    head.sort(key=lambda p: (prem.buffer(-0.02).contains(Point(p)), p[1]))      # outside first, then inward
    vs = tuple(g.get('solenoid') or head[-1])
    far = max((ctr(e['rect'])[1] for e in cons), key=lambda y: abs(y - vs[1]))
    pts = head + ([vs] if vs not in head else []) + [(xm, vs[1]), (xm, far)]
    return pts


def hot_water_calcs(lay):
    seats = seat_count(lay)
    meals = seats * MEALS_PER_SEAT_PEAK
    demand = meals * HW_L_PER_MEAL
    opts = []
    pick = None
    for v, kw in HEATERS:
        rec = kw * 3600 / (4.186 * HW_DT)
        fhr = 0.7 * v + rec
        o = {'volume_L': v, 'kW': kw, 'recovery_Lh': round(rec), 'first_hour_L': round(fhr), 'ok': fhr >= demand}
        opts.append(o)
        if pick is None and o['ok']:
            pick = o
    return {'method': 'ASHRAE Handbook HVAC Applications (Service Water Heating), restaurante de servicio completo: '
                      f'{HW_L_PER_MEAL} L (1.5 gal) a 60 °C por comida en la hora máxima — referencia, verificar',
            'seats': seats, 'meals_peak_hour': meals, 'peak_hour_demand_L_60C': round(demand),
            'first_hour_formula': 'Capacidad 1.ª hora = 0.7 × volumen + recuperación (kW × 3600 / (4.186 × 40 K))',
            'options': opts, 'CA-1': dict(pick or opts[-1], type='termotanque eléctrico vertical', location='mural sobre W3'),
            'CA-2': {'volume_L': 15, 'kW': 1.5, 'type': 'calentador eléctrico bajo barra (punto de uso)', 'serves': 'PB-1 (C1)'},
            'storage_C': 60, 'handwash_mixing_C': 43,
            'note': 'Almacenamiento ≥60 °C; lavamanos con válvula mezcladora termostática (≈43 °C) — criterio usual, '
                    'verificar CIHSE / Salud. Circuitos eléctricos de CA-1 y CA-2 en las láminas eléctricas. ' + PRELIM}


def grease_trap_calcs(lay):
    eq = eqd(lay)
    w1 = next((e for e in lay.get('equipment', []) if e.get('key') == 'sink_2t'), None)
    n = 2 if w1 else 0
    vol = n * SINK_TANK[0] * SINK_TANK[1] * SINK_TANK[2] * 1000
    gal = vol * 0.75 / 3.78541
    res = {'method': 'PDI G-101 (referencia): caudal = volumen de tanques × 0.75 / periodo de vaciado; '
                     'capacidad de grasa ≈ 2 × caudal (lb) — el CIHSE 2017 rige el dimensionamiento final',
           'sink': w1['id'] if w1 else None, 'compartments': n, 'tank_assumed_m': list(SINK_TANK),
           'tanks_volume_L': round(vol, 1), 'drain_volume_gal_75pct': round(gal, 1)}
    for mins in (1, 2):
        gpm = gal / mins
        std = next((s for s in PDI_SIZES if s >= gpm - 1e-9), PDI_SIZES[-1])
        res[f'{mins}min'] = {'flow_gpm': round(gpm, 1), 'flow_Ls': round(gpm * GPM_LS, 2), 'pdi_size_gpm': std,
                             'pdi_size_Ls': round(std * GPM_LS, 2), 'grease_capacity_lb': 2 * std,
                             'grease_capacity_kg': round(2 * std * 0.4536, 1)}
    gt = eq.get('GT-1')
    if gt:
        x0, y0, x1, y1 = gt['rect']
        res['layout_footprint_m'] = [round(abs(x1 - x0), 2), round(abs(y1 - y0), 2), gt.get('h')]
    res['recommendation'] = (f"Interceptor hidromecánico bajo W1 de {res['2min']['pdi_size_gpm']}–{res['1min']['pdi_size_gpm']} gpm "
                             f"({res['2min']['pdi_size_Ls']}–{res['1min']['pdi_size_Ls']} L/s), accesible para limpieza; "
                             'recibe W1, FD-1 y FD-2 — ' + PRELIM)
    return res


# ============================================================================ plumbing geometry model (model metres)
# key -> (nombre, AF, AC, desagüe, UD (ref. UPC/IPC), sifón / ventilación, con grasa, observación)
FIX_KEYS = {
    'sink_2t': ('Fregadero 2 tanques + ducha de prelavado', '1/2" (12)', '1/2" (12)', '2" (50)', 3, 'sifón 2" · vent. 1-1/2"', True,
                'Agua caliente al tanque de lavado; tanques ≈2 × 75 L supuestos (VERIFY ficha).'),
    'handwash': ('Lavamanos del lavado', '1/2" (12)', '1/2" (VMT)', '1-1/2" (38)', 1, 'sifón 1-1/2" · vent. 1-1/4"', False,
                 'Grifo de pedal o sensor recomendado; jabón líquido y toallas desechables.'),
    'handwash_k': ('Lavamanos de cocina (exclusivo manos)', '1/2" (12)', '1/2" (VMT)', '1-1/2" → 2" bajo piso', 1,
                   'sifón 1-1/2" · vent. 1-1/4"', False, 'Salud DE 37308-S: lavamanos en el área de cocina (obligatorio).'),
    'handwash_cold': ('Lavamanos de la zona fría', '1/2" (12)', '1/2" (VMT)', '1-1/2" → 2" bajo piso', 1,
                      'sifón 1-1/2" · vent. 1-1/4"', False, 'Exclusivo de cold prep; jabón y toallas desechables.'),
    'handwash_bar': ('Lavamanos del personal de barra', '1/2" (12)', '1/2" (CA-2)', '1-1/2" (38)', 1, 'sifón 1-1/2" · vent. 1-1/4"',
                     False, 'Al fondo del pasillo de barra; desagüe al colector de barra → WP5.'),
    'mop_sink': ('Pileta de aseo (mop sink)', '1/2" (12)', '1/2" (12)', '3" (75)', 3, 'sifón 3" · vent. 1-1/2"', False,
                 'Llave con rosca de manguera y rompevacío. Recibe la descarga T&P de CA-1 (indirecta).'),
    'barra': ('Pileta de barra (en la barra C1)', '1/2" (desde WP5)', '1/2" (CA-2)', '1-1/2" (38)', 1, 'sifón 1-1/2" · vent. 1-1/4"',
              False, 'Reutiliza el punto de agua y desagüe de WP5; extensión ≈1 m — VERIFY ON SITE.'),
}
HANDWASH_KEYS = ('handwash', 'handwash_k', 'handwash_cold', 'handwash_bar')


def _dedupe(pts):
    out = []
    for p in pts:
        p = (round(p[0], 4), round(p[1], 4))
        if not out or math.dist(out[-1], p) > 1e-3:
            out.append(p)
    return out


def _stub(q, p, dx=0.0, dy=0.0):
    """Orthogonal tap from point q (on a main) to fixture point p: along the main's normal first, then to the fixture."""
    return _dedupe([q, (q[0], q[1] + dy), (p[0] + dx, q[1] + dy), (p[0] + dx, p[1])])


def _nearest_on(poly, p):
    ls = LineString(poly)
    q = ls.interpolate(ls.project(Point(p)))
    return (q.x, q.y)


def plumbing_model(ex, lay):
    E = eqd(lay)
    WP = {w['id']: w for w in ex.get('wet_points_existing', [])}
    WL = {w['id']: w for w in ex.get('walls', [])}
    SH = {s['id']: s for s in ex.get('shafts', [])}
    NW = {w['id']: w for w in lay.get('new_walls', [])}
    NO = {o['id']: o for o in lay.get('new_openings', [])}
    wpc = {k: ctr(v['rect']) for k, v in WP.items()}
    used_wp = set((lay.get('mep') or {}).get('drain_existing') or [])
    m = {'E': E, 'WP': WP}
    part = next((w for w in lay.get('new_walls', []) if w.get('role') == 'kitchen_dining_partition'), None)
    x_part = max(part['rect'][0], part['rect'][2]) if part else 4.475
    gt = next((e for e in lay.get('equipment', []) if e.get('key') == 'grease_trap'), None)
    # ---- fixtures from equipment keys
    fx = []
    for e in lay.get('equipment', []):
        k = e.get('key')
        if k not in FIX_KEYS or e.get('overhead'):
            continue
        name, af, ac, dr, dfu, trap, grease, note = FIX_KEYS[k]
        c = ctr(e['rect'])
        fx.append({'eq': e['id'], 'tag': 'PB-1' if k == 'barra' else e.get('tag', e['id']), 'key': k, 'c': c, 'name': name, 'af': af,
                   'ac': ac, 'drain': dr, 'dfu': dfu, 'trap': trap, 'grease': grease and gt is not None, 'note': note,
                   'bar': c[0] > x_part - 1e-6})
    # destination: grease → GT-1 → WP under/near it; others → nearest existing wet point (WP6-like unused points excluded
    # only if a nearer used point exists)
    gt_wp = None
    if gt:        # the grease trap discharges to the wet point under the grease fixture it serves (else the nearest one)
        gsrc = [E[f_['eq']] for f_ in fx if f_['grease']]
        ov = {k: sum(R(v['rect']).intersection(R(e['rect'])).area for e in gsrc) for k, v in WP.items()}
        gt_wp = max(ov, key=ov.get) if ov and max(ov.values()) > 0.01 else min(wpc, key=lambda k: math.dist(wpc[k], ctr(gt['rect'])))
    for f_ in fx:
        if f_['grease']:
            f_['wp'] = gt_wp
            f_['to'] = f"{gt['id']} → {gt_wp}"
        else:
            f_['wp'] = min(wpc, key=lambda k: math.dist(wpc[k], f_['c']))
            f_['to'] = f_['wp']
    m['fixtures'] = fx
    wing = [f_ for f_ in fx if not f_['bar']]
    bar = [f_ for f_ in fx if f_['bar']]
    # ---- service chase along the east walls of the washing wing (overhead / in wall)
    CH = 0.14
    ew1, ew2, p0a = WL['EW-E1']['rect'], WL['EW-E2']['rect'], WL['IP-P0a']['rect']
    x_e1, x_e2 = ew1[0] - CH, ew2[0] - CH
    y_n = p0a[3] + 0.04
    y_j = ew1[3] + CH
    mop = next((f_ for f_ in wing if f_['key'] == 'mop_sink'), None)
    y_end = mop['c'][1] if mop else y_j + 1.2
    kit = [f_ for f_ in wing if f_['c'][1] < ew1[1]]
    start = kit[0]['c'] if kit else ((p0a[0] + p0a[2]) / 2, y_n)
    M = _dedupe([start, (start[0], y_n), (x_e1, y_n), (x_e1, y_j), (x_e2, y_j), (x_e2, y_end)])
    m['chase'] = M
    m['AF'] = _offset(M, -0.045)      # wall side
    m['AC'] = _offset(M, +0.045)
    m['chase_start'] = kit[0]['eq'] if kit else None
    # cold-water entry: existing supply assumed in shaft S3 (VERIFY ON SITE)
    S3c = ctr(SH['S3']['rect'])
    m['af_entry'] = [S3c, (x_e1 + 0.045, S3c[1])]
    m['af_entry_valve'] = ((S3c[0] + x_e1 + 0.045) / 2, S3c[1])
    # taps from the chase to every other wing fixture
    taps = []
    for f_ in wing:
        if kit and f_ is kit[0]:
            continue
        p = f_['c']
        taps.append(('AF', f_['eq'], _stub(_nearest_on(m['AF'], p), p)))
        if f_['ac'] != '—':
            q = _nearest_on(m['AC'], p)
            taps.append(('AC', f_['eq'], _stub(q, p, 0.09 if abs(q[1] - p[1]) < 0.05 else -0.09, 0.09)))
    m['taps'] = taps
    # LL-1 hose bib on the south face of the heat panel NW-2 (next to the grill, outside the P-1 swing)
    nw2 = NW.get('NW-2')
    p1 = NO.get('P-1')
    if nw2:
        r = nw2['rect']
        rx0, rx1 = min(r[0], r[2]), max(r[0], r[2])
        yl = max(r[1], r[3]) + 0.05
        xl = (rx0 + rx1) / 2
        if p1:          # keep the hose bib out of the P-1 swing (pivot at the south end of the leaf) + 0.15 m
            px0, py0, px1, py1 = p1['rect']
            piv = ((px0 + px1) / 2, max(py0, py1))
            reach = max(p1.get('width', 0.9), abs(py1 - py0)) + 0.15
            dy = abs(piv[1] - yl)
            if dy < reach:
                xl = min(xl, piv[0] - math.sqrt(reach ** 2 - dy ** 2))
            xl = max(xl, rx0 + 0.06)
        m['LL'] = (xl, yl)
        corner = m['AF'][2] if len(m['AF']) > 2 else m['AF'][0]
        m['af_ll'] = _dedupe([corner, (corner[0], yl), (xl, yl)])
    # water heaters: CA-1 wall-hung over the mop sink (T&P into it); CA-2 under the bar counter
    m['CA1'] = (ew2[0] - 0.28, mop['c'][1]) if mop else (x_e2 - 0.2, y_end)
    m['CA1_r'] = 0.28
    bsink = next((f_ for f_ in bar if f_['key'] == 'barra'), None)
    if bar:
        c1 = E[bsink['eq']] if bsink else E[bar[0]['eq']]
        bx0, by0, bx1, by1 = c1['rect']
        wpb = bar[0]['wp']
        wb = wpc[wpb]
        y_top = min(f_['c'][1] for f_ in bar) - 0.10
        xs = [f_['c'][0] for f_ in bar]
        x_af = max(bx0, bx1) - 0.10
        m['af_bar'] = _dedupe([wb, (x_af, wb[1]), (x_af, y_top), (min(xs), y_top)])
        m['af_bar_drops'] = [_dedupe([(f_['c'][0], y_top), f_['c']]) for f_ in bar]
        m['CA2'] = (max(bx0, bx1) - 0.17, max(by0, by1) - 0.16)
        x_ac = m['CA2'][0] - 0.03
        m['ac_bar'] = _dedupe([m['CA2'], (x_ac, y_top + 0.09), (min(xs) + 0.09, y_top + 0.09)])
        m['ac_bar'] = _dedupe([m['CA2'], (x_ac, m['CA2'][1]), (x_ac, y_top + 0.09), (min(xs) + 0.09, y_top + 0.09)])
        m['ac_bar_drops'] = [_dedupe([(f_['c'][0] + 0.09, y_top + 0.09), (f_['c'][0] + 0.09, f_['c'][1])]) for f_ in bar]
        m['bar_wp'] = wpb
    # ---- floor drains at the centre of the free floor of each zone
    fd1 = _free_pole(ex, lay, ['B', 'E'])
    fd2 = _free_pole(ex, lay, ['W'])
    fd3 = _free_pole(ex, lay, ['A'])
    fd3_wp = min(wpc, key=lambda k: math.dist(wpc[k], fd3))
    m['FD'] = [('FD-1', fd1, 'cocina (zonas B + E)', f"{gt['id']} → {gt_wp}" if gt else gt_wp, bool(gt)),
               ('FD-2', fd2, 'lavado (zona W)', f"{gt['id']} → {gt_wp}" if gt else gt_wp, bool(gt)),
               ('FD-3', fd3, 'cold prep (zona A)', fd3_wp, False)]
    # ---- drains (under floor): (id, pts, grease?)
    drains = []
    if gt:
        gx0, gy0, gx1, gy1 = gt['rect']
        GTc = ctr(gt['rect'])
        for f_ in fx:
            if f_['grease']:
                e = E[f_['eq']]
                drains.append((f_['tag'], [(f_['c'][0] - 0.12, min(e['rect'][1], e['rect'][3]) + 0.62), (f_['c'][0] - 0.12, gy0 + 0.06)], True))
        drains.append((gt['id'], [(GTc[0] + 0.15, gy0 + 0.06), (GTc[0] + 0.15, wpc[gt_wp][1])], True))
        drains.append(('FD-2', [fd2, (fd2[0], GTc[1]), (gx0, GTc[1])], True))
        drains.append(('FD-1', [fd1, (fd2[0], fd1[1]), (fd2[0], GTc[1])], True))
    for f_ in wing:
        if f_['grease']:
            continue
        w = wpc[f_['wp']]
        p = ((w[0] - 0.05) if abs(f_['c'][0] - w[0]) < 0.35 else (f_['c'][0] - 0.12), f_['c'][1])
        if math.dist(f_['c'], w) < 0.25:
            continue            # fixture sits on its wet point (mop sink over WP3)
        drains.append((f_['tag'], _dedupe([p, (p[0], w[1]), w]), False))
    drains.append(('FD-3', _dedupe([fd3, (fd3[0], wpc[fd3_wp][1]), (WP[fd3_wp]['rect'][0], wpc[fd3_wp][1])]), False))
    if bar:
        wb = wpc[m['bar_wp']]
        x_d = min(bx0, bx1) + 0.10
        for f_ in bar:
            p = (f_['c'][0] - 0.10, f_['c'][1])
            drains.append((f_['tag'], _dedupe([p, (p[0], p[1] + 0.12), (x_d, p[1] + 0.12)]), False))
        yb = min(f_['c'][1] for f_ in bar) + 0.12
        drains.append(('bar', _dedupe([(x_d, yb), (x_d, wb[1]), (wb[0], wb[1])]), False))
    m['drains'] = drains
    # ---- existing wet points: use
    use = {}
    for f_ in fx:
        use.setdefault(f_['wp'], []).append(f_['tag'] + (' vía ' + gt['id'] if f_['grease'] and gt else ''))
    for t, p, w, to, g in m['FD']:
        use.setdefault(to.split(' → ')[-1], []).append(t)
    m['wp_use'] = {k: (', '.join(use[k]) if k in use else 'sin uso: anular (tapón registrable)') for k in WP}
    m['wp_unlisted'] = sorted(k for k in use if used_wp and k not in used_wp)
    # UD per wet point
    dfu = {}
    for f_ in fx:
        dfu[f_['wp']] = dfu.get(f_['wp'], 0) + (f_['dfu'] or 0)
    for t, p, w, to, g in m['FD']:
        k = to.split(' → ')[-1]
        dfu[k] = dfu.get(k, 0) + 2
    m['wp_dfu'] = dfu
    sizes = ['2" (50)', '3" (75)', '4" (100)']
    pipe = {}
    for k, v in dfu.items():         # collector: by UD, never smaller than the largest trap discharging into it
        big = max([sizes.index(_ud_pipe(v))] + [1 for f_ in fx if f_['wp'] == k and f_['drain'].startswith('3"')])
        pipe[k] = sizes[big]
    m['wp_pipe'] = pipe
    m['gt_dfu'] = sum(f_['dfu'] for f_ in fx if f_['grease']) + sum(2 for t, p, w, to, g in m['FD'] if g)
    return m


def _ud_pipe(ud):
    return '2" (50)' if ud <= 6 else ('3" (75)' if ud <= 20 else '4" (100)')


def fixture_schedule(lay, m, hw, gtc):
    ca1 = hw['CA-1']
    gt = next((e for e in lay.get('equipment', []) if e.get('key') == 'grease_trap'), None)
    rows = []
    order = ['sink_2t', 'handwash', 'handwash_k', 'handwash_cold', 'mop_sink', 'barra', 'handwash_bar']
    for f_ in sorted(m['fixtures'], key=lambda q: order.index(q['key']) if q['key'] in order else 99):
        rows.append({'tag': f_['tag'], 'eq': f_['eq'], 'name': f_['name'], 'af': f_['af'], 'ac': f_['ac'], 'drain': f_['drain'],
                     'dfu': f_['dfu'], 'trap': f_['trap'], 'to': f_['to'], 'note': f_['note'], 'at': [round(v, 3) for v in f_['c']]})
    rows.append({'tag': 'CA-1', 'eq': None, 'name': f"Termotanque eléctrico ≈{ca1['volume_L']} L / {ca1['kW']:g} kW", 'af': '3/4" entrada',
                 'ac': '3/4" salida', 'drain': 'T&P 3/4"', 'dfu': None, 'trap': 'válv. T&P + expansión', 'to': 'pileta de aseo (indir.)',
                 'note': f"Mural sobre la pileta de aseo, anclado a EW-E2 (≈200 kg lleno — VERIFY). Hora pico ≈{hw['peak_hour_demand_L_60C']} L/h a 60 °C.",
                 'at': [round(v, 3) for v in m['CA1']]})
    if m.get('CA2'):
        rows.append({'tag': 'CA-2', 'eq': None, 'name': 'Calentador bajo barra ≈15 L / 1.5 kW', 'af': '1/2" (12)', 'ac': '1/2" (12)',
                     'drain': 'T&P 1/2"', 'dfu': None, 'trap': 'válv. T&P', 'to': 'PB-1 (indirecta)',
                     'note': 'Punto de uso para la barra (evita un ramal de agua caliente de ≈10 m desde CA-1).',
                     'at': [round(v, 3) for v in m['CA2']]})
    if m.get('LL'):
        rows.append({'tag': 'LL-1', 'eq': None, 'name': 'Llave de manguera con rompevacío + carrete', 'af': '3/4" (18)', 'ac': '—',
                     'drain': '—', 'dfu': None, 'trap': '—', 'to': 'FD-1 (lavado de pisos)',
                     'note': 'Manguera fija NFPA 96 cap. 14 si el hogar de H1 > 0.14 m³ (VERIFY ficha); si no, solo lavado.',
                     'at': [round(v, 3) for v in m['LL']]})
    for tag, pt, where, to, grease in m['FD']:
        rows.append({'tag': tag, 'eq': None, 'name': f'Coladera de piso con canastilla · {where}', 'af': '—', 'ac': '—',
                     'drain': '2" (50)', 'dfu': 2, 'trap': 'sifón + sello (cebado)', 'to': to,
                     'note': ('Pendiente de piso hacia la coladera (1–2 %, verificar). '
                              + ('Con grasa: pasa por la trampa.' if grease else 'Recibe condensados indirectos si aplica.')),
                     'at': list(pt)})
    if gt:
        rows.append({'tag': gt['id'], 'eq': gt['id'], 'name': 'Trampa / interceptor de grasa bajo el fregadero', 'af': '—', 'ac': '—',
                     'drain': 'entrada 2" · salida ' + _ud_pipe(m['gt_dfu']), 'dfu': m['gt_dfu'], 'trap': 'ventilación propia 1-1/2"',
                     'to': next((f_['wp'] for f_ in m['fixtures'] if f_['grease']), ''),
                     'note': f"{gtc['2min']['pdi_size_gpm']}–{gtc['1min']['pdi_size_gpm']} gpm "
                             f"({gtc['2min']['pdi_size_Ls']}–{gtc['1min']['pdi_size_Ls']} L/s), ref. PDI G-101; CIHSE rige; accesible.",
                     'at': [round(v, 3) for v in ctr(gt['rect'])]})
    for k, v in m['wp_use'].items():
        if v.startswith('sin uso'):
            rows.append({'tag': k, 'eq': None, 'name': 'Punto húmedo existente sin uso', 'af': 'tapón', 'ac': 'tapón',
                         'drain': 'tapón registrable', 'dfu': None, 'trap': '—', 'to': '—',
                         'note': 'Anular agua y desagüe con tapones accesibles — VERIFY ON SITE.',
                         'at': [round(v_, 3) for v_ in ctr(m['WP'][k]['rect'])]})
    return rows


# ============================================================================ compute + json
def ar_riser(lay):
    """Proposed AR-1 riser / roof-fan point (data has none): above the first diffuser, behind the K1 bench (VERIFY)."""
    diffs = ((lay.get('mep') or {}).get('makeup_air') or {}).get('diffusers') or []
    if not diffs:
        return None
    d0 = diffs[0]
    y = max(d0[1] - 0.5, 0.95)
    k1 = next((e for e in lay.get('equipment', []) if e['id'] == 'K1'), None)
    if k1:
        y = max(y, max(k1['rect'][1], k1['rect'][3]) + 0.3)
    return (d0[0], y)


def compute(ex, lay, val):
    ext, mua = exhaust_calcs(ex, lay)
    gas = gas_calcs(ex, lay)
    hw = hot_water_calcs(lay)
    gtc = grease_trap_calcs(lay)
    pm = plumbing_model(ex, lay)
    fx = fixture_schedule(lay, pm, hw, gtc)
    return {'exhaust': ext, 'mua': mua, 'gas': gas, 'hw': hw, 'gt': gtc, 'pm': pm, 'fixtures': fx, '_lay': lay}


def calcs_json(res, lay):
    pm = res['pm']
    return {
        'sheets': ['M-101', 'M-102'],
        'status': 'ANTEPROYECTO / PRELIMINAR — a validar por el profesional responsable (CFIA); ' + PRELIM,
        'layout_version': lay.get('meta', {}).get('version'), 'date': lay.get('meta', {}).get('date'),
        'flags': [FLAG_ENG, FLAG_SMOKER, 'VERIFY ON SITE', 'DIMENSION TO VERIFY'],
        'exhaust': {
            'basis': {'rates': 'Caudal por metro lineal de campana según el servicio (ASHRAE 154 / IMC 507, campana mural no '
                               'listada = referencia conservadora); campanas listadas UL 710 suelen operar en el rango indicado '
                               '(guías CKV / fabricante). La selección final la hace el ingeniero con el listado del equipo.',
                      'duty_table_cfm_per_ft': {k: {'name': v[0], 'unlisted': v[1], 'listed_typical': list(v[2])} for k, v in DUTY.items()},
                      'v_design_ms': V_DESIGN, 'v_min_ms_nfpa96': V_MIN, 'v_max_practical_ms': V_MAX,
                      'duct_rule': 'Sección = Q / v_diseño; rectangular en pasos de 50 mm (relación ≤1.5) y circular en pasos de 25 mm'},
            'systems': res['exhaust'],
        },
        'makeup_air': dict(res['mua'], riser=([round(v, 3) for v in ar_riser(lay)] if ar_riser(lay) else None),
                           riser_note='Riser / ventilador AR-1 propuesto (no está en layout.json) — alternativa ducto S1: VERIFY'),
        'gas': res['gas'],
        'hot_water': res['hw'],
        'grease_trap': res['gt'],
        'plumbing_fixtures': res['fixtures'],
        'wet_points_existing': [{'id': k, 'use': v, 'dfu_ref': pm['wp_dfu'].get(k),
                                 'collector': pm['wp_pipe'].get(k),
                                 'in_mep_drain_existing': k in ((lay.get('mep') or {}).get('drain_existing') or [])}
                                for k, v in pm['wp_use'].items()],
        'wet_points_used_but_not_in_mep_drain_existing': pm['wp_unlisted'],
        'grease_trap_inflow_dfu_ref': pm['gt_dfu'],
        'floor_drains': [{'id': t, 'at': list(p), 'zone': w, 'to': to, 'grease': g} for t, p, w, to, g in pm['FD']],
        'water_heaters': {'CA-1': {'at': [round(v, 3) for v in pm['CA1']], **res['hw']['CA-1']},
                          'CA-2': {'at': [round(v, 3) for v in pm['CA2']], **res['hw']['CA-2']}},
        'sources': [
            'CIHSE 2017 (CFIA): agua potable, desagües, ventilación, interceptores de grasa — edición vigente a confirmar',
            'Salud DE 37308-S (servicios de alimentación): lavamanos en cocina, agua caliente en lavado, pisos a coladeras',
            'NFPA 96 (edición adoptada por el RNPCI 2023 a confirmar): cap. 7 ductos, §7.8 descargas, §8.2.1.1 velocidad '
            '≥2.54 m/s, §8.3 aire de reposición, cap. 10 supresión y corte de combustible, cap. 14 combustible sólido',
            'NFPA 17A / UL 300: supresión de químico húmedo · NFPA 211: chimeneas · NFPA 54 / 58: gas',
            'ASHRAE 154 / IMC 507: caudales de referencia por servicio · PDI G-101: interceptores · ASHRAE HVAC Applications: agua caliente',
            'Citas tomadas de resúmenes de búsqueda, no de textos primarios: verificar edición y numeración',
        ],
    }


# ============================================================================ drawing helpers (sheet mm)
def _pts(pts):
    return ' '.join(f"{f(sx(x))},{f(sy(y))}" for x, y in pts)


def pline(pts, color, w=0.45, dash=None, marker=None, halo=True, opacity=1.0, cap='round'):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    mk = f' marker-end="url(#{marker})"' if marker else ''
    out = ''
    if halo:
        out += (f'<polyline points="{_pts(pts)}" fill="none" stroke="#ffffff" stroke-width="{f(w + 0.7)}" '
                f'stroke-linecap="{cap}" stroke-linejoin="round" stroke-opacity="0.9"/>')
    out += (f'<polyline points="{_pts(pts)}" fill="none" stroke="{color}" stroke-width="{f(w)}" stroke-opacity="{opacity}" '
            f'stroke-linecap="{cap}" stroke-linejoin="round"{d}{mk}/>')
    return out


def mline(x1, y1, x2, y2, color, w=0.3, dash=None, marker=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    mk = f' marker-end="url(#{marker})"' if marker else ''
    return f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" stroke="{color}" stroke-width="{f(w)}"{d}{mk}/>'


def dot(cx, cy, r, color, stroke='#ffffff', sw=0.2):
    return f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{color}" stroke="{stroke}" stroke-width="{f(sw)}"/>'


def sym_valve(cx, cy, color, vertical=False, s=1.35, fill=None):
    fill = fill or color
    if vertical:
        a = f'{f(cx - s*0.8)},{f(cy - s)} {f(cx)},{f(cy)} {f(cx + s*0.8)},{f(cy - s)}'
        b = f'{f(cx - s*0.8)},{f(cy + s)} {f(cx)},{f(cy)} {f(cx + s*0.8)},{f(cy + s)}'
    else:
        a = f'{f(cx - s)},{f(cy - s*0.8)} {f(cx)},{f(cy)} {f(cx - s)},{f(cy + s*0.8)}'
        b = f'{f(cx + s)},{f(cy - s*0.8)} {f(cx)},{f(cy)} {f(cx + s)},{f(cy + s*0.8)}'
    return (f'<polygon points="{a}" fill="{fill}" stroke="#ffffff" stroke-width="0.15"/>'
            f'<polygon points="{b}" fill="{fill}" stroke="#ffffff" stroke-width="0.15"/>')


def sym_solenoid(cx, cy, color):
    return (sym_valve(cx, cy, color) + mline(cx, cy, cx, cy - 1.7, color, 0.25)
            + f'<rect x="{f(cx - 1.05)}" y="{f(cy - 3.7)}" width="2.1" height="2.1" fill="#ffffff" stroke="{color}" stroke-width="0.3"/>'
            + text(cx, cy - 2.12, 'S', 1.45, weight='800', fill=color))


def sym_fd(cx, cy, color=C_DR):
    return (f'<rect x="{f(cx - 1.5)}" y="{f(cy - 1.5)}" width="3" height="3" fill="#ffffff" stroke="{color}" stroke-width="0.35"/>'
            f'<circle cx="{f(cx)}" cy="{f(cy)}" r="1.0" fill="none" stroke="{color}" stroke-width="0.25"/>'
            + mline(cx - 1.5, cy, cx + 1.5, cy, color, 0.18) + mline(cx, cy - 1.5, cx, cy + 1.5, color, 0.18))


def sym_heater(cx, cy, r, color=C_AC, label='CA', dashed=False, size=1.5):
    d = ' stroke-dasharray="0.9 0.5"' if dashed else ''
    return (f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="#fff1ef" stroke="{color}" stroke-width="0.4"{d}/>'
            + text(cx, cy + size * 0.36, label, size, weight='800', fill=color))


def sym_cap(cx, cy, color='#333'):
    return (f'<circle cx="{f(cx)}" cy="{f(cy)}" r="1.25" fill="#ffffff" stroke="{color}" stroke-width="0.35"/>'
            + mline(cx - 0.8, cy - 0.8, cx + 0.8, cy + 0.8, color, 0.35) + mline(cx - 0.8, cy + 0.8, cx + 0.8, cy - 0.8, color, 0.35))


def sym_riser(cx, cy, r, color, fill='#ffffff'):
    k = r * 0.7071
    return (f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{fill}" stroke="{color}" stroke-width="0.4"/>'
            + mline(cx - k, cy - k, cx + k, cy + k, color, 0.3) + mline(cx - k, cy + k, cx + k, cy - k, color, 0.3))


def sym_diffuser(cx, cy, h, color=C_MUA):
    g = [f'<rect x="{f(cx - h)}" y="{f(cy - h)}" width="{f(2*h)}" height="{f(2*h)}" fill="#e6f5f9" stroke="{color}" stroke-width="0.4"/>',
         mline(cx - h, cy - h, cx + h, cy + h, color, 0.2), mline(cx - h, cy + h, cx + h, cy - h, color, 0.2),
         f'<rect x="{f(cx - h*0.45)}" y="{f(cy - h*0.45)}" width="{f(h*0.9)}" height="{f(h*0.9)}" fill="#ffffff" stroke="{color}" stroke-width="0.25"/>']
    return ''.join(g)


def sym_nozzle(cx, cy, color=C_SUP, hollow=False):
    fill = '#ffffff' if hollow else color
    return (f'<polygon points="{f(cx - 0.95)},{f(cy - 0.8)} {f(cx + 0.95)},{f(cy - 0.8)} {f(cx)},{f(cy + 0.9)}" '
            f'fill="{fill}" stroke="{color}" stroke-width="0.25"/>')


def sym_box(cx, cy, w, h, label, color, fill='#ffffff', size=1.3, tcol=None):
    return (f'<rect x="{f(cx - w/2)}" y="{f(cy - h/2)}" width="{f(w)}" height="{f(h)}" rx="0.3" fill="{fill}" stroke="{color}" stroke-width="0.35"/>'
            + text(cx, cy + size * 0.36, label, size, weight='800', fill=tcol or color))


def sym_circle_tag(cx, cy, label, color, r=1.8, size=1.25, fill='#ffffff'):
    return (f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{fill}" stroke="{color}" stroke-width="0.35"/>'
            + text(cx, cy + size * 0.36, label, size, weight='800', fill=color if fill == '#ffffff' else '#ffffff'))


def _tw_est(s, size, bold=False):
    """Text width (mm) for Figtree: per-glyph estimate (upper-case / bold lines are wider than plan_svg.tw assumes)."""
    s = str(s)
    k = sum(0.63 if c.isupper() else 0.56 if c.isdigit() else 0.50 if c.islower() else 0.29 if c == ' '
            else 0.80 if c in '→×≈≥≤' else 0.40 for c in s)
    return max(tw(s, size), k * size * (1.07 if bold else 1.0))


class Labels:
    """Label boxes with a white background; keeps their bounding boxes for an overlap self-check."""

    def __init__(self):
        self.boxes = []

    def tag(self, x, y, lines, color, size=1.7, anchor='start', lh=1.28, first_bold=True, bg=True, name=None, fills=None):
        lines = [ln for ln in lines if ln]
        w = max(_tw_est(ln[1:] if ln.startswith('!') else ln, size, bold=(i == 0 and first_bold) or ln.startswith('!'))
                for i, ln in enumerate(lines)) + 2.2
        h = len(lines) * size * lh + 1.3
        x0 = x if anchor == 'start' else (x - w if anchor == 'end' else x - w / 2)
        g = []
        if bg:
            g.append(f'<rect x="{f(x0)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="0.6" fill="#ffffff" fill-opacity="0.95" '
                     f'stroke="{color}" stroke-width="0.3"/>')
        for i, ln in enumerate(lines):
            red = ln.startswith('!')
            s = ln[1:] if red else ln
            c = C_RED if red else (color if (i == 0 and first_bold) else C_TXT)
            if fills and i < len(fills) and fills[i]:
                c = fills[i]
            g.append(text(x0 + 1.1, y + 0.65 + (i + 0.78) * size * lh, s, size, anchor='start',
                          weight='800' if (i == 0 and first_bold) or red else '400', fill=c))
        self.boxes.append((name or lines[0][:24], box(x0, y, x0 + w, y + h)))
        return ''.join(g), (x0, y, x0 + w, y + h)

    def leader(self, bb, target, color, side=None, w=0.25):
        x0, y0, x1, y1 = bb
        tx, ty = target
        if side is None:
            side = 'left' if tx < x0 else ('right' if tx > x1 else ('bottom' if ty > y1 else 'top'))
        if side == 'left':
            px, py = x0, min(max(ty, y0 + 1), y1 - 1)
        elif side == 'right':
            px, py = x1, min(max(ty, y0 + 1), y1 - 1)
        elif side == 'bottom':
            px, py = min(max(tx, x0 + 1.5), x1 - 1.5), y1
        else:
            px, py = min(max(tx, x0 + 1.5), x1 - 1.5), y0
        return (f'<polyline points="{f(px)},{f(py)} {f(tx)},{f(ty)}" fill="none" stroke="{color}" stroke-width="{f(w)}"/>'
                f'<circle cx="{f(tx)}" cy="{f(ty)}" r="0.5" fill="{color}"/>')

    def register(self, name, bb):
        self.boxes.append((name, box(*bb)))

    def overlaps(self, tol=0.3):
        out = []
        for i in range(len(self.boxes)):
            for j in range(i + 1, len(self.boxes)):
                a, b = self.boxes[i][1], self.boxes[j][1]
                if a.intersects(b) and a.intersection(b).area > tol:
                    out.append((self.boxes[i][0], self.boxes[j][0], round(a.intersection(b).area, 2)))
        return out


def table(x, y, cols, rows, size=1.75, rh=4.1, head=1.65, colors=None, weights=None, families=None, head_lines=1, width=None):
    """cols: [(dx, header, anchor)]; header may contain '\n' for 2 lines. rows: list[list[str]]."""
    g = []
    xe = x + width if width else (x + cols[-1][0] if cols[-1][2] == 'end' else x + cols[-1][0] + 40)
    for dx, hd, anc in cols:
        for k, hl in enumerate(hd.split('\n')):
            g.append(text(x + dx, y + 2.3 + k * head * 1.2, hl, head, anchor=anc, weight='700', fill='#555'))
    hy = y + 2.3 + (head_lines - 1) * head * 1.2 + 1.3
    g.append(f'<line x1="{f(x)}" y1="{f(hy)}" x2="{f(xe)}" y2="{f(hy)}" stroke="#141210" stroke-width="0.3"/>')
    yy = hy
    for i, r in enumerate(rows):
        for j, ((dx, _, anc), v) in enumerate(zip(cols, r)):
            c = (colors[i][j] if colors and colors[i] and colors[i][j] else '#1f1f1f')
            wgt = (weights[i][j] if weights and weights[i] and weights[i][j] else '400')
            fam = (families[j] if families and families[j] else FONT)
            g.append(text(x + dx, yy + rh * 0.72, v, size, anchor=anc, weight=wgt, fill=c, family=fam))
        g.append(f'<line x1="{f(x)}" y1="{f(yy + rh)}" x2="{f(xe)}" y2="{f(yy + rh)}" stroke="#e1ddd6" stroke-width="0.2"/>')
        yy += rh
    return ''.join(g), yy


def defs_markers():
    mk = []
    for k, c in (('dr', C_DR), ('gr', C_GR), ('af', C_AF), ('ac', C_AC), ('mua', C_MUA), ('gas', C_GAS_D), ('sup', C_SUP),
                 ('e1', C_EXT1), ('e2', C_EXT2), ('e3', C_EXT3), ('k', '#333333')):
        mk.append(f'<marker id="m4-{k}" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.6" markerHeight="3.6" orient="auto">'
                  f'<path d="M0,0 L6,3 L0,6 z" fill="{c}"/></marker>')
    pats = ('<pattern id="m4-hatch-gt" patternUnits="userSpaceOnUse" width="1.1" height="1.1" patternTransform="rotate(45)">'
            f'<rect width="1.1" height="1.1" fill="#fde7d6"/><line x1="0" y1="0" x2="0" y2="1.1" stroke="{C_GR}" stroke-width="0.25"/></pattern>'
            '<pattern id="m4-hatch-arr" patternUnits="userSpaceOnUse" width="0.9" height="0.9">'
            f'<rect width="0.9" height="0.9" fill="#ffffff"/><path d="M0,0 L0.9,0.9 M0.9,0 L0,0.9" stroke="{C_EXT2}" stroke-width="0.15"/></pattern>'
            '<pattern id="m4-hatch-encl" patternUnits="userSpaceOnUse" width="1.2" height="1.2" patternTransform="rotate(45)">'
            '<rect width="1.2" height="1.2" fill="#f1efe9"/><line x1="0" y1="0" x2="0" y2="1.2" stroke="#9a948a" stroke-width="0.25"/></pattern>')
    return '<defs>' + ''.join(mk) + pats + '</defs>'


def base_plan(s, zones=0.04):
    s.grid_axes()
    if zones:
        s.layer_zones(zones)
    s.layer_existing()
    s.layer_furniture(faint=True)
    s.layer_equipment(faint=True, labels=False)
    s.layer_new()


def eq_tags(s, lay, skip, size=1.35, color='#8b8b86'):
    """Small grey equipment tags (orientation only)."""
    g = ['<g id="eq-tags">']
    for e in lay.get('equipment', []):
        if e['id'] in skip or e.get('overhead') or e.get('stack_with'):
            continue
        cx, cy = ctr(e['rect'])
        g.append(text(sx(cx), sy(cy) + size * 0.36, e.get('tag', e['id']), size, weight='700', fill=color))
    g.append('</g>')
    s.add(''.join(g))


def sw_sym(fn):
    def w(x, y):
        return fn(x + 5, y + 1.7)
    return w


# ============================================================================ M-101 · hidrosanitario
def _stack(items, x, gap=1.6, ymin=None):
    """items: [(target_y, h, payload)] sorted by target → top y of each box without overlaps."""
    out, prev = [], ymin if ymin is not None else -1e9
    for ty, h, pl in sorted(items, key=lambda q: q[0]):
        top = max(ty - h / 2, prev + gap)
        out.append((top, pl))
        prev = top + h
    return out


def build_m101(ex, lay, val, res):
    pm, hw, gtc, fx = res['pm'], res['hw'], res['gt'], res['fixtures']
    E, WP = pm['E'], pm['WP']
    fixtures = pm['fixtures']
    gt = next((e for e in lay.get('equipment', []) if e.get('key') == 'grease_trap'), None)
    s = Sheet(ex, lay, val, 'M101')
    s.add(defs_markers())
    s.frame_and_titleblock('M-101 · Hidrosanitario (esquema)',
                           'Agua fría / caliente · desagües a puntos húmedos existentes · trampa de grasa · coladeras de piso · CIHSE 2017',
                           'M-101')
    base_plan(s, zones=0.05)
    L = Labels()
    fix_ids = [f_['eq'] for f_ in fixtures] + ([gt['id']] if gt else [])
    stacked = {e['id'] for e in lay.get('equipment', []) if e.get('stack_with')}
    eq_tags(s, lay, set(fix_ids) | stacked)
    P = lambda p: (sx(p[0]), sy(p[1]))  # noqa: E731
    halo = 'paint-order="stroke" stroke="#ffffff" stroke-width="0.8"'
    # ---- existing wet points
    g = ['<g id="wet-points">']
    for w in ex.get('wet_points_existing', []):
        used = not pm['wp_use'][w['id']].startswith('sin uso')
        g.append(rect_el(w['rect'], '#e3f4f5' if used else '#f4f4f2', C_WP if used else '#8a8a85', 0.35, dash='1.1 0.6',
                         extra='fill-opacity="0.55"'))
    g.append('</g>')
    s.add(''.join(g))
    # ---- fixtures highlighted
    g = ['<g id="fixtures">']
    for fid in fix_ids:
        e = E.get(fid)
        if not e:
            continue
        if gt and fid == gt['id']:
            g.append(rect_el(e['rect'], 'url(#m4-hatch-gt)', C_GR, 0.4, dash='1.2 0.5'))
        else:
            g.append(rect_el(e['rect'], C_FIX_F, C_FIX_S, 0.4, extra='fill-opacity="0.75"'))
    g.append('</g>')
    s.add(''.join(g))
    # ---- drains (under floor)
    g = ['<g id="drains">']
    for did, pts, grease in pm['drains']:
        g.append(pline(pts, C_GR if grease else C_DR, 0.55, dash='2.4 0.7 0.6 0.7', marker='m4-gr' if grease else 'm4-dr'))
    for w in ex.get('wet_points_existing', []):
        cx, cy = ctr(w['rect'])
        if pm['wp_use'][w['id']].startswith('sin uso'):
            g.append(sym_cap(sx(cx), sy(cy)))
        else:
            g.append(f'<circle cx="{f(sx(cx))}" cy="{f(sy(cy))}" r="1.05" fill="{C_WP}" stroke="#ffffff" stroke-width="0.3"/>'
                     f'<circle cx="{f(sx(cx))}" cy="{f(sy(cy))}" r="0.35" fill="#ffffff"/>')
    for tag, pt, where, to, grease in pm['FD']:
        g.append(sym_fd(sx(pt[0]), sy(pt[1]), C_GR if grease else C_DR))
    g.append('</g>')
    s.add(''.join(g))
    # ---- water (overhead / in wall)
    g = ['<g id="water">']
    g.append(pline(pm['AC'], C_AC, 0.42, dash='1.8 0.7'))
    g.append(pline(pm['AF'], C_AF, 0.42))
    g.append(pline(pm['af_entry'], C_AF, 0.55))
    if pm.get('af_ll'):
        g.append(pline(pm['af_ll'], C_AF, 0.42))
    for kind, eid, pts in pm['taps']:
        g.append(pline(pts, C_AF if kind == 'AF' else C_AC, 0.38, dash=None if kind == 'AF' else '1.8 0.7', halo=False))
        g.append(dot(sx(pts[0][0]), sy(pts[0][1]), 0.5, C_AF if kind == 'AF' else C_AC, sw=0.12))
        g.append(dot(sx(pts[-1][0]), sy(pts[-1][1]), 0.5, C_AF if kind == 'AF' else C_AC, sw=0.12))
    for kind, pts in (('AF', pm['AF']), ('AC', pm['AC'])):
        g.append(dot(sx(pts[0][0]), sy(pts[0][1]), 0.55, C_AF if kind == 'AF' else C_AC, sw=0.15))
    if pm.get('af_bar'):
        g.append(pline(pm['ac_bar'], C_AC, 0.42, dash='1.8 0.7'))
        g.append(pline(pm['af_bar'], C_AF, 0.42))
        for pts in pm['af_bar_drops']:
            g.append(pline(pts, C_AF, 0.38, halo=False) + dot(sx(pts[-1][0]), sy(pts[-1][1]), 0.5, C_AF, sw=0.12))
        for pts in pm['ac_bar_drops']:
            g.append(pline(pts, C_AC, 0.38, dash='1.8 0.7', halo=False) + dot(sx(pts[-1][0]), sy(pts[-1][1]), 0.5, C_AC, sw=0.12))
    ent = pm['af_entry'][0]
    g.append(sym_circle_tag(sx(ent[0]), sy(ent[1]), 'AF', C_AF, r=1.9, size=1.3))
    vx, vy = pm['af_entry_valve']
    g.append(sym_valve(sx(vx), sy(vy), C_AF, s=1.1))
    ca = pm['CA1']
    g.append(sym_heater(sx(ca[0]), sy(ca[1]), pm['CA1_r'] * S, dashed=True, label='CA-1', size=1.35))
    if pm.get('CA2'):
        c2 = pm['CA2']
        g.append(sym_heater(sx(c2[0]), sy(c2[1]), 2.0, label='CA-2', size=1.0))
    if pm.get('LL'):
        lx, ly = pm['LL']
        g.append(sym_valve(sx(lx), sy(ly), C_AF, s=1.2, fill='#ffffff'))
        g.append(f'<circle cx="{f(sx(lx))}" cy="{f(sy(ly))}" r="0.45" fill="{C_AF}"/>')
    g.append('</g>')
    s.add(''.join(g))
    # ---- labels
    lab = []
    by_key = {}
    for f_ in fixtures:
        by_key.setdefault(f_['key'], []).append(f_)
    wpc = {k: ctr(v['rect']) for k, v in WP.items()}
    fdp = {t: p for t, p, *_ in pm['FD']}
    X_E = sx(4.74) + 3.0            # over the (context) stair, east of the wing
    sz = 1.6
    east = [(sy(ent[1]), ['AF · ACOMETIDA EXISTENTE (¿ducto S3?)', 'llave de paso general + válvula check',
                          '!VERIFY ON SITE punto, medidor y presión'], C_AF, P(ent))]
    for f_ in by_key.get('sink_2t', []):
        east.append((sy(f_['c'][1]) - 5, [f"{f_['tag']} · FREGADERO 2T + PRELAVADO", f"AF/AC {f_['af'][:4]} · desagüe {f_['drain'][:2]} → {f_['to']}"],
                     C_FIX_S, (sx(f_['c'][0]) + 2.0, sy(f_['c'][1]) - 7.5)))
    if gt:
        gc = ctr(gt['rect'])
        east.append((sy(gc[1]), [f"{gt['id']} · TRAMPA DE GRASA BAJO EL FREGADERO",
                                 f"{gtc['2min']['pdi_size_gpm']}–{gtc['1min']['pdi_size_gpm']} gpm (ref. PDI G-101) · {PRELIM}"],
                     C_GR, (sx(gc[0]) + 4.0, sy(gc[1]) + 3.0)))
    for f_ in by_key.get('handwash', []):
        east.append((sy(f_['c'][1]), [f"{f_['tag']} · LAVAMANOS → {f_['to']}", 'AF 1/2" · AC 1/2" (VMT) · desagüe 1-1/2"'],
                     C_FIX_S, (sx(f_['c'][0]) + 2.2, sy(f_['c'][1]))))
    east.append((sy(pm['CA1'][1]) - 3, [f"CA-1 · TERMOTANQUE ELÉCTRICO ≈{hw['CA-1']['volume_L']} L / {hw['CA-1']['kW']:g} kW",
                                         'mural sobre la pileta de aseo, anclado a EW-E2', f"T&P a la pileta · {PRELIM}"],
                 C_AC, (sx(pm['CA1'][0]) + 4.0, sy(pm['CA1'][1]) - 3.5)))
    for f_ in by_key.get('mop_sink', []):
        east.append((sy(f_['c'][1]) + 6, [f"{f_['tag']} · PILETA DE ASEO (MOP SINK) SOBRE {f_['to']}",
                                          'AF/AC 1/2" · desagüe 3" · llave con rompevacío'], C_FIX_S, (sx(f_['c'][0]) + 3.0, sy(f_['c'][1]) + 3.2)))
    heights = [(ty, len(lines) * sz * 1.28 + 1.3, (lines, c, tgt)) for ty, lines, c, tgt in east]
    for top, (lines, c, tgt) in _stack(heights, X_E, gap=1.8, ymin=sy(4.986) + 2.0):
        svg, bb = L.tag(X_E, top, lines, c, size=sz)
        lab += [svg, L.leader(bb, tgt, c, side='left')]
    # kitchen / wing interior
    for f_ in by_key.get('handwash_k', []):
        p = P(f_['c'])
        svg, bb = L.tag(sx(0.75), p[1] - 15.5, [f"{f_['tag']} · LAVAMANOS DE COCINA (obligatorio)", f"AF/AC 1/2\" (VMT) · desagüe → {f_['to']}"],
                        C_FIX_S, size=sz)
        lab += [svg, L.leader(bb, (p[0] - 1.2, p[1] - 1.8), C_FIX_S, side='right')]
    for f_ in by_key.get('handwash_cold', []):
        p = P(f_['c'])
        svg, bb = L.tag(p[0] + 4.5, p[1] + 3.0, [f"{f_['tag']} · LAVAMANOS ZONA FRÍA", f"AF/AC 1/2\" (VMT) · desagüe → {f_['to']}"], C_FIX_S, size=sz)
        lab += [svg, L.leader(bb, (p[0] + 1.6, p[1] + 1.2), C_FIX_S, side='left')]
    f1 = P(fdp['FD-1'])
    svg, bb = L.tag(f1[0] - 3.0, f1[1] + 2.4, ['FD-1 · COLADERA COCINA', f"2\" con canastilla → {pm['FD'][0][3]}"], C_GR, size=sz, anchor='end')
    lab += [svg, L.leader(bb, (f1[0] - 1.2, f1[1] + 1.2), C_GR, side='right')]
    if pm.get('LL'):
        llp = P(pm['LL'])
        svg, bb = L.tag(llp[0] - 4.0, llp[1] - 14.0, ['LL-1 · LLAVE DE MANGUERA 3/4"', 'rompevacío + carrete; manguera NFPA 96',
                                                     'cap. 14 si hogar de H1 > 0.14 m³ (VERIFY)'], C_AF, size=1.55, anchor='end')
        lab += [svg, L.leader(bb, (llp[0] - 0.8, llp[1] - 0.4), C_AF, side='right')]
    f2 = P(fdp['FD-2'])
    svg, bb = L.tag(f2[0] - 14.0, f2[1] + 3.2, [f"FD-2 · COLADERA LAVADO → {pm['FD'][1][3]}"], C_GR, size=1.55)
    lab += [svg, L.leader(bb, (f2[0], f2[1] + 1.5), C_GR, side='top')]
    f3 = P(fdp['FD-3'])
    svg, bb = L.tag(f3[0] - 3.0, f3[1] + 2.0, [f"FD-3 · COLADERA COLD PREP → {pm['FD'][2][3]}", 'recibe condensados indirectos (si aplica)'],
                    C_DR, size=1.55, anchor='end')
    lab += [svg, L.leader(bb, (f3[0] - 1.5, f3[1] + 0.8), C_DR, side='right')]
    # wet-point tags
    for wid in WP:
        use = pm['wp_use'][wid]
        if wid in [f_['wp'] for f_ in fixtures if f_['bar']] or use.startswith('sin uso'):
            continue
        r = WP[wid]['rect']
        srcs = [f_ for f_ in fixtures if f_['wp'] == wid and not f_['grease']]
        if any(f_['key'] in ('handwash_k', 'handwash_cold') for f_ in srcs):     # WP4-like: separate note
            w = P(wpc[wid])
            svg, bb = L.tag(sx(0.42), w[1] + 3.8, [f"{wid} existente: recibe {', '.join(f_['tag'] for f_ in srcs)}", '(2" bajo piso — VERIFY)'],
                            C_WP, size=1.5)
            lab += [svg, L.leader(bb, (w[0] - 1.6, w[1] + 0.8), C_WP, side='right')]
            continue
        if any(f_['key'] == 'mop_sink' for f_ in srcs):
            x, y, anc = sx(r[0]) - 0.6, sy(r[3]) + 2.6, 'end'
        elif any(f_['key'] == 'handwash' for f_ in srcs):
            x, y, anc = sx(r[0]) + 0.5, sy(r[3]) + 2.4, 'start'
        else:
            x, y, anc = sx(r[0]) - 0.6, sy(r[1]) + 2.6, 'end'
        lab.append(text(x, y, wid, 1.5, anchor=anc, weight='800', fill=C_WP, extra=halo))
        L.register(wid, (x - tw(wid, 1.5) if anc == 'end' else x, y - 1.2, x if anc == 'end' else x + tw(wid, 1.5), y + 0.4))
    # bar (above the north wall, leaders to each bar fixture)
    barf = [f_ for f_ in fixtures if f_['bar']]
    if barf:
        names = ' + '.join(f"{f_['tag']} {'pileta' if f_['key'] == 'barra' else 'lavamanos'}" for f_ in barf)
        wpb = pm.get('bar_wp', '')
        svg, bb = L.tag(sx(4.62), 34.5, [f"BARRA · {names}", f"AF 1/2\" desde el punto existente de {wpb} (VERIFY)",
                                         'AC 1/2" de CA-2 (≈15 L bajo la barra C1)', f"desagües 1-1/2\" → colector 2\" → {wpb} (ext. ≈1 m)"],
                        C_FIX_S, size=1.55)
        lab.append(svg)
        for f_ in barf:
            lab.append(L.leader(bb, (sx(f_['c'][0]) + 0.6, sy(f_['c'][1]) - 0.8), C_FIX_S, side='bottom'))
        w5 = P(wpc[wpb])
        svg, bb = L.tag(sx(6.45), sy(1.62), [f"{wpb} existente → colector de barra", '!VERIFY ON SITE diámetro y pendiente'], C_WP, size=1.5)
        lab += [svg, L.leader(bb, (w5[0] + 2.2, w5[1] - 0.8), C_WP, side='left')]
    for wid, use in pm['wp_use'].items():
        if use.startswith('sin uso'):
            w = P(wpc[wid])
            svg, bb = L.tag(w[0] + 8.0, w[1] + 2.0, [f"{wid} existente sin uso: anular", 'agua y desagüe con tapón registrable'], '#555555', size=1.5)
            lab += [svg, L.leader(bb, (w[0] + 1.3, w[1] + 0.3), '#555555', side='left')]
    # pipe-size tag on the chase
    ch = pm['chase']
    if len(ch) > 2:
        tag = 'AF 1" · AC 3/4"'
        x_t = sx(ch[1][0]) + 3.0
        lab.append(text(x_t, sy(ch[1][1]) + 3.6, tag, 1.45, anchor='start', weight='700', fill=C_AF, extra=halo))
        L.register('size-tag', (x_t, sy(ch[1][1]) + 2.4, x_t + tw(tag, 1.45), sy(ch[1][1]) + 4.1))
    s.add('<g id="labels">' + ''.join(lab) + '</g>')
    # ---- schematic diagram (free area east of the stair)
    s.add(m101_diagram(res, 229.0, 181.0, 364.0, 303.0, L))
    # ---- side panel
    legend = [
        LEGEND_WALLS[0], LEGEND_WALLS[2], LEGEND_WALLS[3],
        (sw_line(C_AF, None, 0.5), 'Agua fría AF (por cielo / en muro)'),
        (sw_line(C_AC, '1.8 0.7', 0.5), 'Agua caliente AC'),
        (sw_line(C_DR, '2.4 0.7 0.6 0.7', 0.6), 'Desagüe bajo piso → punto húmedo existente'),
        (sw_line(C_GR, '2.4 0.7 0.6 0.7', 0.6), 'Desagüe con grasa → trampa de grasa'),
        (sw_rect(C_FIX_F, C_FIX_S), 'Aparato sanitario servido'),
        (sw_rect('#e3f4f5', C_WP, dash='1.1 0.6'), 'Punto húmedo existente WP (desagüe existente)'),
        (sw_rect(None, C_GR, dash='1.2 0.5', pattern='url(#m4-hatch-gt)'), 'Trampa / interceptor de grasa'),
        (sw_sym(lambda x, y: sym_fd(x, y, C_DR)), 'Coladera de piso FD (sifón + canastilla)'),
        (sw_sym(lambda x, y: sym_heater(x, y, 1.6, label='CA', size=1.0)), 'Calentador de agua CA'),
        (sw_sym(lambda x, y: sym_valve(x, y, C_AF, s=1.2)), 'Llave de paso · LL = llave de manguera'),
        (sw_sym(lambda x, y: sym_cap(x, y)), 'Tapón (punto anulado)'),
    ]
    n_ac = sum(1 for f_ in fixtures if f_['ac'] != '—')
    rows = [
        ('Aparatos con AF / AC', f"{len(fixtures)} / {n_ac} + CA-1 + CA-2"),
        (f"Agua caliente hora pico ({hw['seats']} asientos)", f"≈{hw['peak_hour_demand_L_60C']} L/h a 60 °C"),
        ('CA-1 capacidad 1.ª hora (0.7 V + recup.)', f"{hw['CA-1']['first_hour_L']} L"),
        ('Trampa de grasa (PDI G-101 ref., 2 / 1 min)', f"{gtc['2min']['pdi_size_gpm']}–{gtc['1min']['pdi_size_gpm']} gpm"),
        ('UD de desagüe a la trampa', f"{pm['gt_dfu']} UD · Ø{_ud_pipe(pm['gt_dfu']).split(' ')[0]}"),
        ('Coladeras de piso', f"{len(pm['FD'])} (cocina · lavado · cold prep)"),
    ]
    def _short(s_, n):
        out = ''
        for w_ in s_.replace('(', '').replace(')', '').split():
            if len(out) + len(w_) + 1 > n:
                break
            out = (out + ' ' + w_).strip()
        return out
    wprows = [(f"{k} · {_short(WP[k].get('desc', ''), 24)}", 'anular (tapón)' if v.startswith('sin uso') else v)
              for k, v in pm['wp_use'].items()]
    notes = [
        '!ANTEPROYECTO / PRELIMINAR — a validar por el profesional',
        '!responsable (CFIA). Diámetros: PRELIMINAR — TO BE ENGINEERED.',
        'CIHSE 2017: agua potable, desagües, ventilación e interceptores',
        '  (edición vigente a confirmar). Citas de resúmenes: verificar.',
        'Salud DE 37308-S: lavamanos exclusivos (cocina, zona fría, barra),',
        '  lavado con agua fría y caliente, pisos con pendiente a coladeras.',
        'Con grasa (fregadero, FD-1, FD-2) → trampa → punto existente;',
        '  lavamanos, barra y cold prep sin grasa → directo.',
        'Ventilación de cada sifón y de la trampa a la red existente',
        '  (o válvula de admisión de aire si el CIHSE la admite).',
        'Registros de limpieza en cambios de dirección y en la trampa.',
        'Condensados de A1–A3: bandeja evaporativa o descarga',
        '  indirecta (brecha de aire) a FD-3.',
        'Agua caliente: almacenar ≥60 °C; lavamanos con VMT ≈43 °C.',
        'Servicios sanitarios: comunes del C.C. (sin piezas en el local)',
        '  — autorización escrita y recorrido ≤36 m: VERIFY.',
    ]
    verify = [
        'Acometida AF, medidor y presión disponible (¿ducto S3?).',
        'Diámetro, cota, pendiente y destino de WP1–WP6.',
        'Nivel del local: losa sobre terreno o entrepiso (drenajes',
        '  nuevos bajo piso de FD-1, FD-3, K3 y A8).',
        'Red de ventilación sanitaria existente.',
        'Muro EW-E2 apto para anclar CA-1 (≈200 kg lleno).',
        'Fichas: tanques del fregadero, trampa, CA-1, CA-2, hogar de H1.',
    ]
    y = s.side_panel([('h', 'Leyenda'), ('legend', legend), ('h', 'Resumen (preliminar)'), ('rows', rows),
                      ('h', 'Puntos húmedos existentes'), ('rows', wprows)])
    y = s.side_panel([('h', 'Criterios y normativa'), ('para', notes), ('h', 'VERIFY ON SITE'), ('para', verify)], y=y)
    res.setdefault('_panel_end', {})['M101'] = y
    # ---- fixture schedule (bottom band)
    s.add(m101_schedule(fx, pm, 12, 320))
    res.setdefault('_overlaps', {})['M101'] = L.overlaps()
    return s.render()


def m101_diagram(res, x0, y0, x1, y1, L):
    """One-line schematic of water supply and drainage (no scale), generated from the plumbing model."""
    pm, hw = res['pm'], res['hw']
    fixtures = pm['fixtures']
    wing = [f_ for f_ in fixtures if not f_['bar']]
    bar = [f_ for f_ in fixtures if f_['bar']]
    fz = 1.6
    SHORT = {'sink_2t': 'fregadero 2 tanques', 'handwash': 'lavamanos lavado', 'handwash_k': 'lavamanos cocina',
             'handwash_cold': 'lavamanos zona fría', 'mop_sink': 'pileta de aseo', 'barra': 'pileta de barra',
             'handwash_bar': 'lavamanos barra'}
    g = [f'<rect x="{f(x0)}" y="{f(y0)}" width="{f(x1 - x0)}" height="{f(y1 - y0)}" fill="#ffffff" stroke="#141210" stroke-width="0.35"/>',
         text(x0 + 3, y0 + 5.2, 'ESQUEMA UNIFILAR (sin escala)', 2.6, anchor='start', weight='800', extra='letter-spacing="0.3"'),
         text(x1 - 3, y0 + 5.2, PRELIM, 1.75, anchor='end', weight='700', fill=C_RED)]
    L.register('diagram', (x0, y0, x1, y1))
    # ------------------------------------------------ water (left)
    xa = x0 + 4
    g.append(text(xa, y0 + 11.5, 'AGUA POTABLE', 2.0, anchor='start', weight='800', fill=C_AF))
    src_y = y0 + 16.5
    g.append(sym_box(xa + 16, src_y, 32, 5.2, 'RED C.C. / MEDIDOR', C_AF, size=1.5))
    g.append(text(xa + 34, src_y + 0.6, '(VERIFY)', 1.45, anchor='start', weight='700', fill=C_RED))
    bus_x = xa + 6
    order = {'handwash_k': 0, 'sink_2t': 1, 'handwash': 2, 'mop_sink': 3, 'handwash_cold': 4}
    rows = [(f_['tag'], SHORT.get(f_['key'], f_['name'][:20].lower()), f_['ac'] != '—')
            for f_ in sorted(wing, key=lambda q: order.get(q['key'], 9))]
    if pm.get('LL'):
        rows.append(('LL-1', 'llave de manguera', False))
    rows.append(('CA-1', f"termotanque {hw['CA-1']['volume_L']} L", False))
    ry0, dy = src_y + 10.5, 6.9
    y_last = ry0 + dy * (len(rows) - 1)
    g.append(mline(bus_x, src_y + 2.6, bus_x, y_last - 0.8, C_AF, 0.5))
    g.append(sym_valve(bus_x, src_y + 5.6, C_AF, vertical=True, s=1.1))
    g.append(text(bus_x - 1.8, src_y + 6.1, 'LLP', 1.35, anchor='end', weight='700', fill=C_AF))
    g.append(text(bus_x + 1.2, src_y + 6.1, 'AF 1"', 1.35, anchor='start', weight='700', fill=C_AF))
    ac_x = bus_x + 5.5
    bx = xa + 21
    bw = 36
    ac_rows = [i for i, r in enumerate(rows) if r[2]]
    for i, (t, d, hot) in enumerate(rows):
        yy = ry0 + i * dy
        g.append(mline(bus_x, yy - 0.8, bx, yy - 0.8, C_AF, 0.4))
        g.append(dot(bus_x, yy - 0.8, 0.5, C_AF, sw=0.1))
        if hot:
            g.append(mline(ac_x, yy + 0.9, bx, yy + 0.9, C_AC, 0.4, dash='1.4 0.6'))
            g.append(dot(ac_x, yy + 0.9, 0.5, C_AC, sw=0.1))
        col = C_AC if t == 'CA-1' else (C_AF if t == 'LL-1' else C_FIX_S)
        fill = '#fff1ef' if t == 'CA-1' else '#eef8f9'
        g.append(f'<rect x="{f(bx)}" y="{f(yy - 2.6)}" width="{bw}" height="5.2" rx="0.5" fill="{fill}" stroke="{col}" stroke-width="0.3"/>')
        g.append(text(bx + 1.2, yy + 0.6, t, fz, anchor='start', weight='800', fill=col))
        g.append(text(bx + 9.4, yy + 0.6, d, 1.5, anchor='start', fill=C_TXT))
    if ac_rows:
        g.append(f'<polyline points="{f(bx + bw)},{f(y_last)} {f(bx + bw + 3)},{f(y_last)} {f(bx + bw + 3)},{f(y_last + 5.2)} {f(ac_x)},{f(y_last + 5.2)} '
                 f'{f(ac_x)},{f(ry0 + ac_rows[0] * dy + 0.9)}" fill="none" stroke="{C_AC}" stroke-width="0.5" stroke-dasharray="1.4 0.6"/>')
        g.append(text(ac_x + 1.2, y_last + 4.4, 'AC 3/4" · 60 °C · VMT ≈43 °C a lavamanos', 1.45, anchor='start', weight='700', fill=C_AC))
    # bar group
    if bar:
        yb = y_last + 13.0
        wpb = pm.get('bar_wp', '')
        g.append(text(xa, yb, 'BARRA (sistema local)', 1.7, anchor='start', weight='800', fill=C_TXT))
        g.append(sym_box(xa + 16, yb + 5.2, 32, 5.0, f"PUNTO EXISTENTE {wpb}", C_AF, size=1.4))
        g.append(sym_box(xa + 16, yb + 12.4, 32, 5.0, 'CA-2 · 15 L bajo barra', C_AC, fill='#fff1ef', size=1.4))
        for i, f_ in enumerate(bar):
            fy = yb + 5.2 + i * 7.2
            g.append(sym_box(xa + 50, fy, 18, 5.0, f_['tag'], C_FIX_S, fill='#eef8f9', size=1.5))
            g.append(mline(xa + 32, yb + 5.2, xa + 40.4, fy - 0.8, C_AF, 0.45, marker='m4-af'))
            g.append(mline(xa + 32, yb + 12.4, xa + 40.4, fy + 0.8, C_AC, 0.45, dash='1.4 0.6', marker='m4-ac'))
    # ------------------------------------------------ drainage (right)
    xd = x0 + 69
    g.append(text(xd, y0 + 11.5, 'DESAGÜES (bajo piso)', 2.0, anchor='start', weight='800', fill=C_DR))
    fxw = 19
    cx_ = xd + 29
    wx_ = xd + 43
    gt = next((e for e in res['_lay'].get('equipment', []) if e.get('key') == 'grease_trap'), None) if res.get('_lay') else None
    groups = {}
    for f_ in fixtures:
        groups.setdefault(f_['wp'], {'g': [], 'd': []})['g' if f_['grease'] else 'd'].append(f_['tag'])
    for t, p, w, to, gr in pm['FD']:
        groups.setdefault(to.split(' → ')[-1], {'g': [], 'd': []})['g' if gr else 'd'].append(t)
    mop = next((f_ for f_ in wing if f_['key'] == 'mop_sink'), None)
    if mop:
        groups[mop['wp']]['d'].append('T&P CA-1')
    yy = y0 + 17.5
    for wp in sorted(groups):
        grp = groups[wp]
        for kind in ('g', 'd'):
            items = grp[kind]
            if not items:
                continue
            grease = kind == 'g'
            c = C_GR if grease else C_DR
            ys = [yy + i * 6.0 for i in range(len(items))]
            ym = (ys[0] + ys[-1]) / 2
            for it, y_ in zip(items, ys):
                ind = it.startswith('T&P')
                g.append(f'<rect x="{f(xd)}" y="{f(y_ - 2.2)}" width="{fxw}" height="4.4" rx="0.5" fill="#ffffff" stroke="{c}" stroke-width="0.3"'
                         + (' stroke-dasharray="0.8 0.5"' if ind else '') + '/>')
                g.append(text(xd + fxw / 2, y_ + 0.55, it + (' (indir.)' if ind else ''), 1.45, weight='700', fill=c))
                g.append(f'<polyline points="{f(xd + fxw)},{f(y_)} {f(xd + fxw + 3)},{f(y_)} {f(xd + fxw + 3)},{f(ym)}" fill="none" '
                         f'stroke="{c}" stroke-width="0.4"/>')
            if grease:
                g.append(mline(xd + fxw + 3, ym, cx_ - 5.6, ym, c, 0.45, marker='m4-gr'))
                g.append(f'<rect x="{f(cx_ - 5)}" y="{f(ym - 2.4)}" width="10" height="4.8" fill="url(#m4-hatch-gt)" stroke="{C_GR}" stroke-width="0.35"/>')
                g.append(text(cx_, ym + 0.55, gt['id'] if gt else 'GT', 1.5, weight='800', fill=C_GR,
                              extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.7"'))
                g.append(mline(cx_ + 5, ym, wx_ - 5.1, ym, C_GR, 0.45, marker='m4-gr'))
            else:
                g.append(mline(xd + fxw + 3, ym, wx_ - 5.1, ym, c, 0.45, marker='m4-dr'))
            g.append(f'<rect x="{f(wx_ - 4.5)}" y="{f(ym - 2.4)}" width="9" height="4.8" fill="#e3f4f5" stroke="{C_WP}" stroke-width="0.35" stroke-dasharray="1.1 0.6"/>')
            g.append(text(wx_, ym + 0.55, wp, 1.5, weight='800', fill=C_WP))
            g.append(mline(wx_ + 4.5, ym, wx_ + 9.6, ym, C_WP, 0.45, marker='m4-dr'))
            ud = pm['wp_dfu'].get(wp)
            if ud and kind == ('g' if grp['g'] else 'd'):
                g.append(text(wx_, ym + 4.2, f"Σ {ud} UD", 1.3, weight='700', fill=C_WP))
            yy = ys[-1] + 9.2
    unused = [k for k, v in pm['wp_use'].items() if v.startswith('sin uso')]
    ytop, ybot = y0 + 15.5, yy - 6.0
    xc = wx_ + 9.4
    g.append(mline(xc, ytop, xc, ybot, C_WP, 0.6))
    for i, (s_, w_, c_) in enumerate((('RED SANITARIA', '800', C_WP), ('EXISTENTE C.C.', '800', C_WP), ('Ø, cota, pendiente', '400', C_TXT),
                                      ('y destino:', '400', C_TXT), ('VERIFY ON SITE', '800', C_RED))):
        g.append(text(xc + 1.2, ytop + 2.2 + i * 2.1, s_, 1.35, anchor='start', weight=w_, fill=c_))
    if unused:
        g.append(text(xd, yy - 1.6, f"{', '.join(unused)}: anular (tapón registrable)", 1.45, anchor='start', weight='700', fill='#555'))
    g.append(text(xd, yy + 0.8, 'Ventilación de sifones y de la trampa a la red existente.', 1.45, anchor='start', fill=C_TXT))
    ny = max(yy + 5.0, (y_last + 13.0 + 7.2 * max(1, len(bar)) + 8.0) if bar else y_last + 12.0)
    for i, ln in enumerate(['Llave de paso en cada aparato (AF y AC) · aislamiento térmico en tuberías de AC.',
                            'Sifón en cada aparato; registros de limpieza en cambios de dirección y en la trampa.',
                            'Nivel / losa del local y red sanitaria existente: VERIFY ON SITE antes de definir cotas.']):
        g.append(text(x0 + 3, ny + i * 2.6, ln, 1.45, anchor='start', fill=C_TXT if i < 2 else C_RED, weight='400' if i < 2 else '700'))
    g.append(text(x0 + 3, y1 - 6.0, 'Ubicación en planta: ver símbolos y rótulos. Diámetros en el cuadro inferior. UD = unidades de descarga de referencia',
                  1.4, anchor='start', fill='#555'))
    g.append(text(x0 + 3, y1 - 3.4, '(UPC / IPC); el CIHSE 2017 rige el dimensionamiento — TO BE ENGINEERED.', 1.4, anchor='start', fill='#555'))
    return '<g id="m101-diagram">' + ''.join(g) + '</g>'


def m101_schedule(fx, pm, x, y):
    g = [text(x, y + 3, 'CUADRO DE APARATOS Y DIÁMETROS', 2.6, anchor='start', weight='800', extra='letter-spacing="0.35"'),
         text(x + 72, y + 3, f'{PRELIM} (CIHSE 2017) · Ø nominal pulg. (mm) · VMT = válvula mezcladora termostática · UD = unidades de descarga (ref.)',
              1.8, anchor='start', weight='700', fill=C_RED)]
    cols = [(0, 'Tag', 'start'), (13, 'Aparato / elemento', 'start'), (82, 'AF', 'start'), (106, 'AC', 'start'),
            (128, 'Desagüe', 'start'), (161, 'UD', 'end'), (165, 'Sifón / ventilación', 'start'), (205, 'Descarga a', 'start'),
            (234, 'Observaciones', 'start')]
    rows, colors, weights = [], [], []
    for r in fx:
        rows.append([r['tag'], r['name'], r['af'], r['ac'], r['drain'], '' if r['dfu'] is None else str(r['dfu']), r['trap'], r['to'],
                     r['note']])
        c = C_GR if ('GT' in r['to'] or r['tag'].startswith('GT')) else (C_AC if r['tag'].startswith('CA') else
                                                                        ('#555555' if r['af'] == 'tapón' else C_WP))
        colors.append([c, None, C_AF, C_AC, C_DR, None, None, c, None])
        weights.append(['800', '700', None, None, None, None, None, '700', None])
    rh = min(4.05, (404 - (y + 6 + 5)) / max(1, len(rows) + 1))
    svg, yy = table(x, y + 6, cols, rows, size=1.66, rh=rh, head=1.6, colors=colors, weights=weights,
                    families=[None, None, MONO, MONO, MONO, MONO, None, None, None], width=336)
    g.append(svg)
    col = [f"{k} Σ {v} UD (Ø{pm['wp_pipe'][k].split(' ')[0]})" for k, v in sorted(pm['wp_dfu'].items())]
    g.append(text(x, yy + 3.4, 'Colectores: ' + ' · '.join(col) + '. Tubería: AF PVC presión; AC CPVC o PEX apto 80 °C; desagüe PVC sanitario '
                  'con pendiente ≥1–2 % (verificar CIHSE).', 1.6, anchor='start', fill='#333'))
    return '<g id="m101-schedule">' + ''.join(g) + '</g>'


# ============================================================================ M-102 · gas / extracción / reposición / supresión
def build_m102(ex, lay, val, res):
    E = eqd(lay)
    mep = lay.get('mep', {})
    gas = res['gas']
    ext = {r['id']: r for r in res['exhaust']}
    mua = res['mua']
    s = Sheet(ex, lay, val, 'M102')
    s.add(defs_markers())
    s.frame_and_titleblock('M-102 · Gas, extracción, reposición y supresión',
                           'Red de gas del C.C. · EXT-1 / EXT-2 / EXT-3 independientes · aire de reposición AR-1 · supresión UL 300 · esquema',
                           'M-102')
    base_plan(s, zones=0)
    L = Labels()
    hot = ['H1', 'H2', 'H3', 'H4', 'H5', 'S1', 'K2']
    eq_tags(s, lay, set(hot) | {'HD-1', 'HD-2'})
    P = lambda p: (sx(p[0]), sy(p[1]))  # noqa: E731
    g = []
    # ---- hood-served appliances highlighted
    for hid in hot:
        e = E.get(hid)
        if not e:
            continue
        fill, stroke = COL['smoker'] if e.get('key') == 'smoker' else COL['fire']
        g.append(rect_el(e['rect'], fill, stroke, 0.3, extra='fill-opacity="0.35"'))
        cx, cy = ctr(e['rect'])
        x0 = min(e['rect'][0], e['rect'][2])
        if hid == 'K2':
            continue
        g.append(text(sx(x0) + 1.0, sy(cy) + 0.55, hid, 1.4, anchor='start', weight='800', fill=stroke))
    # ---- existing Marna's collar (to be adapted)
    col = (ex.get('existing_hood') or {}).get('collar')
    if col:
        g.append(rect_el(col, 'none', '#6e6e6a', 0.3, dash='0.8 0.5'))
    # ---- hoods
    hood_c = {'HD-1': C_EXT1, 'HD-2': C_EXT2}
    for hid, c in hood_c.items():
        hd = E.get(hid)
        if not hd:
            continue
        g.append(rect_el(hd['rect'], 'none', c, 0.55, dash='2.2 0.9'))
        x0, y0, x1, y1 = hd['rect']
        g.append(text(sx(x0) - 1.2, sy((y0 + y1) / 2), f"{hid} · {(y1 - y0):.2f} × {(x1 - x0):.2f}", 1.55, weight='800', fill=c, rot=-90))
    # spark arrester strip in HD-2 (upstream of the filters, along the back)
    hd2 = E.get('HD-2')
    if hd2:
        x0, y0, x1, y1 = hd2['rect']
        ar = [x1 - 0.30, y0 + 0.18, x1 - 0.18, y1 - 0.18]
        g.append(rect_el(ar, 'url(#m4-hatch-arr)', C_EXT2, 0.3))
    s.add('<g id="hoods">' + ''.join(g) + '</g>')
    # ---- make-up air (under the exhaust ducts)
    g = []
    diffs = mep.get('makeup_air', {}).get('diffusers', [])
    if diffs:
        riser_ar = ar_riser(lay)
        path = [riser_ar] + [tuple(d) for d in diffs]
        g.append(pline(path, C_MUA, 5.0, halo=False, opacity=0.25, cap='butt'))
        g.append(pline(path, C_MUA, 0.35, halo=False))
        for d in diffs:
            g.append(sym_diffuser(sx(d[0]), sy(d[1]), 3.6))
        g.append(sym_riser(sx(riser_ar[0]), sy(riser_ar[1]), 2.3, C_MUA, fill='#e6f5f9'))
        res['_ar_riser'] = riser_ar
    s.add('<g id="mua">' + ''.join(g) + '</g>')
    # ---- exhaust ducts (horizontal runs drawn at real width; vertical risers as circles with X)
    g = []
    wmap = {'EXT-1': C_EXT1, 'EXT-2': C_EXT2, 'EXT-3': C_EXT3}
    risers = {}
    for x in mep.get('exhaust', []):
        c = wmap.get(x['id'], '#555')
        r = ext.get(x['id'], {})
        if r.get('duct'):
            wd = r['duct']['rect_mm'][1] / 1000
        else:
            wd = (r.get('flue_diameter_mm_typical') or [200])[-1] / 1000
        route = [tuple(p) for p in (x.get('route') or [])]
        if len(route) > 1 and LineString(route).length > 0.05:
            band = LineString(route).buffer(wd / 2, cap_style=2, join_style=2)
            g.append(f'<polygon points="{_pts(list(band.exterior.coords))}" fill="#ffffff" fill-opacity="0.9" stroke="{c}" stroke-width="0.4"/>')
            g.append(pline(route, c, 0.3, dash='1.6 0.8', halo=False, marker=None))
            end = route[-1]
        else:
            end = tuple(x.get('collar') or route[0])
        risers[x['id']] = end
        if x.get('collar') and tuple(x['collar']) != end:
            cx, cy = P(x['collar'])
            g.append(f'<rect x="{f(cx - 1.7)}" y="{f(cy - 1.7)}" width="3.4" height="3.4" fill="#ffffff" stroke="{c}" stroke-width="0.45"/>')
        rr = max(1.9, wd * S / 2) if not r.get('duct') else 2.4
        g.append(sym_riser(sx(end[0]), sy(end[1]), rr, c))
    s.add('<g id="exhaust">' + ''.join(g) + '</g>')
    # ---- gas
    g = []
    gp = gas_path(lay, ex)
    gm = mep.get('gas', {})
    if gp:
        g.append(pline(gp, C_GAS, 0.6))
        xm = gp[-1][0]
        for cid in gm.get('consumers', []):
            e = E.get(cid)
            if not e:
                continue
            cy = ctr(e['rect'])[1]
            xb = max(e['rect'][0], e['rect'][2])         # back face of the appliance
            g.append(pline([(xm, cy), (xb - 0.10, cy)], C_GAS, 0.45, halo=False))
            g.append(dot(sx(xm), sy(cy), 0.5, C_GAS_D, sw=0.1))
            g.append(sym_valve(sx((xm + xb) / 2), sy(cy), C_GAS_D, s=0.75))
        ex_, ey_ = P(gm['entry'])
        g.append(f'<circle cx="{f(ex_)}" cy="{f(ey_)}" r="1.6" fill="#ffffff" stroke="{C_GAS}" stroke-width="0.45"/>'
                 + text(ex_, ey_ + 0.55, 'G', 1.5, weight='800', fill=C_GAS_D))
        if gm.get('main_valve'):
            vx, vy = P(gm['main_valve'])
            g.append(sym_valve(vx, vy, C_GAS_D, vertical=True, s=1.2))
        if gm.get('solenoid'):
            vx, vy = P(gm['solenoid'])
            g.append(sym_valve(vx, vy, C_GAS_D, s=1.2) + mline(vx, vy, vx, vy + 1.5, C_GAS_D, 0.25)
                     + f'<rect x="{f(vx - 1.0)}" y="{f(vy + 1.5)}" width="2.0" height="2.0" fill="#ffffff" stroke="{C_GAS_D}" stroke-width="0.3"/>'
                     + text(vx, vy + 3.0, 'S', 1.35, weight='800', fill=C_GAS_D))
    # gas detector (derived: north wall between K1 and the gas valves; GLP ≤0.30 m del piso)
    k1, k2 = E.get('K1'), E.get('K2')
    wn = next((w for w in ex.get('walls', []) if w['id'] == 'EW-N1'), None)
    north_y = (max(wn['rect'][1], wn['rect'][3]) if wn else 0.116) + 0.10
    dg = None
    xs_valves = [p[0] for p in (gm.get('solenoid'), gm.get('main_valve'), gm.get('entry')) if p]
    if k1 and xs_valves:
        dg = ((max(k1['rect'][0], k1['rect'][2]) + min(xs_valves)) / 2, north_y)
    if dg:
        g.append(sym_circle_tag(*P(dg), 'DG', C_GAS_D, r=1.6, size=1.15))
    s.add('<g id="gas">' + ''.join(g) + '</g>')
    # ---- suppression
    g = []
    pull = (lay.get('life_safety') or {}).get('pull_station')
    pm_ids = (pull or {}).get('ids') or (['PM-1'] if pull else [])
    hd1 = E.get('HD-1')
    hd2_supp = bool(hd2) and (len(pm_ids) > 1 or 'supresi' in (hd2.get('note') or '').lower())
    n1 = n2 = 0
    ext_by = {x['id']: x for x in mep.get('exhaust', [])}
    if hd1:
        x0, y0, x1, y1 = hd1['rect']
        for a in _hood_appliances(lay, hd1):
            ax0, ay0, ax1, ay1 = a['rect']
            n = 2 if a.get('key') == 'cocina_4q' else 1
            for i in range(n):
                g.append(sym_nozzle(sx((ax0 + ax1) / 2), sy(ay0 + (ay1 - ay0) * (i + 0.5) / n)))
                n1 += 1
        col1 = (ext_by.get('EXT-1') or {}).get('collar')
        npl = max(1, math.ceil((y1 - y0) / 1.8))
        for i in range(npl):
            yy = y0 + (y1 - y0) * (i + 0.5) / npl
            if col1 and abs(yy - col1[1]) < 0.3:
                yy = col1[1] + 0.36
            g.append(sym_nozzle(sx(x1 - 0.30), sy(yy)))
            n1 += 1
        if col1:
            g.append(sym_nozzle(*P(col1)))
            n1 += 1
    if hd2:
        for a in _hood_appliances(lay, hd2):
            ax0, ay0, ax1, ay1 = a['rect']
            for i in range(2):
                g.append(sym_nozzle(sx((ax0 + ax1) / 2), sy(ay0 + (ay1 - ay0) * (i + 0.5) / 2), hollow=not hd2_supp))
                n2 += 1
        n2 += 2          # plenum + duct (not drawn at this scale)
    res['_nozzles'] = {'HD-1': n1, 'HD-2': n2 if hd2_supp else 0}
    # agent cabinets on the north wall above K1 (part without the oven)
    sups = []
    if k1:
        kx0 = min(k1['rect'][0], k1['rect'][2])
        kx1 = min(k2['rect'][0], k2['rect'][2]) if k2 else max(k1['rect'][0], k1['rect'][2])
        n_s = 2 if hd2_supp else 1
        for i in range(n_s):
            sups.append((f'SUP-{i + 1}', (kx0 + (kx1 - kx0) * (i + 0.5) / n_s, north_y)))
    # pull stations (data) + cable / interlock (schematic)
    pms = []
    if pull:
        ax, ay = pull['at']
        for i, pid in enumerate(pm_ids):
            pms.append((pid, (ax, ay + (i - (len(pm_ids) - 1) / 2) * 0.19)))
    part = next((w for w in lay.get('new_walls', []) if w.get('role') == 'kitchen_dining_partition'), None)
    if sups:
        yc = 0.05
        xc = (max(part['rect'][0], part['rect'][2]) + 0.05) if part else (pull['at'][0] if pull else sups[-1][1][0])
        cab = [(sups[0][1][0], yc), (xc, yc)]
        if pms:
            cab.append((xc, max(p[1][1] for p in pms)))
        g.append(pline(cab, C_SUP, 0.3, dash='1.0 0.6', halo=False))
        for _, p in sups:
            g.append(pline([(p[0], yc), p], C_SUP, 0.3, dash='1.0 0.6', halo=False))
        if gm.get('solenoid'):
            vs = gm['solenoid']
            g.append(pline([(vs[0], yc), (vs[0], vs[1] - 0.04)], C_SUP, 0.3, dash='1.0 0.6', halo=False))
        for pid, p in pms:
            g.append(pline([(xc, p[1]), p], C_SUP, 0.3, dash='1.0 0.6', halo=False))
        for sid, p in sups:
            g.append(sym_box(*P(p), 3.0, 2.4, sid[-1], C_SUP, fill=C_SUP, size=1.3, tcol='#ffffff'))
    for pid, p in pms:
        g.append(sym_box(sx(p[0]) + 1.6, sy(p[1]), 3.0, 3.0, pid[-1], C_SUP, fill=C_SUP, size=1.3, tcol='#ffffff'))
    s.add('<g id="suppression">' + ''.join(g) + '</g>')
    # ---- labels
    lab = []
    e1, e2 = ext.get('EXT-1', {}), ext.get('EXT-2', {})
    top = 23.0
    W = 40
    x_next = 13.0
    # a) EXT-3 smoker flue (north band)
    if risers.get('EXT-3'):
        x3 = ext_by.get('EXT-3', {})
        lines = ['EXT-3 · CHIMENEA PROPIA DEL SMOKER S1'] + wrap(x3.get('riser', ''), W) + ['!SOLID-FUEL SMOKER - LOCATION / FLUE /', '!FIRE CODE TO BE VALIDATED']
        svg, bb = L.tag(x_next, top, lines, C_EXT3, size=1.6)
        lab += [svg, L.leader(bb, P(risers['EXT-3']), C_EXT3, side='bottom')]
        x_next = bb[2] + 2.0
    # c) gas (north band)
    mp = gas['main_pipe'].get('hasta 15 m desde el regulador', {})
    lines = (['GAS · RED DEL CENTRO COMERCIAL', 'sin cilindros · tipo y presión: VERIFY']
             + wrap(gm.get('entry_note', ''), W)
             + ['VM llave de corte fuera del local, rotulada', 'VS solenoide enclavada (SUP-1), rearme manual',
                f"principal {mp.get('LPG', '')} GLP / {mp.get('NG', '')} GN (PRELIMINAR)", 'manifold en el espacio técnico tras la línea'])
    svg, bb = L.tag(x_next, top, lines, C_GAS_D, size=1.6)
    lab += [svg, L.leader(bb, P(gm['entry']), C_GAS_D, side='bottom')]
    x_next = bb[2] + 2.0
    # d) EXT-1 (north band)
    if e1:
        x1_ = ext_by.get('EXT-1', {})
        d = e1['duct']
        ec = e1.get('existing_collar') or {}
        lines = (['EXT-1 · HD-1 LÍNEA A GAS (UL 300)',
                  f"{e1['Q_Ls']:.0f} L/s · ducto {d['rect_mm'][0]}×{d['rect_mm'][1]} · {d['velocity_rect_ms']:.1f} m/s"]
                 + wrap(x1_.get('riser', ''), W)
                 + ([f"riser existente {ec['section_m'][0]:.2f}×{ec['section_m'][1]:.2f} → {ec['velocity_ms']:.1f} m/s"] if ec else []))
        svg, bb = L.tag(x_next, top, lines, C_EXT1, size=1.6)
        lab += [svg, L.leader(bb, P(risers['EXT-1']), C_EXT1, side='bottom')]
    # b) EXT-2 (dining side, next to HD-2)
    x_din = sx(max(part['rect'][0], part['rect'][2])) + 4.5 if part else sx(4.6)
    if e2:
        x2 = ext_by.get('EXT-2', {})
        d = e2['duct']
        lines = (['EXT-2 · HD-2 SOLO PARRILLA (COMB. SÓLIDO)',
                  f"{e2['Q_Ls']:.0f} L/s · ducto {d['rect_mm'][0]}×{d['rect_mm'][1]} · {d['velocity_rect_ms']:.1f} m/s"]
                 + wrap(x2.get('riser', ''), W) + wrap(x2.get('note', ''), W))
        h = len(lines) * 1.6 * 1.28 + 1.3
        svg, bb = L.tag(x_din, sy(hd2['rect'][1]) - h - 1.5, lines, C_EXT2, size=1.6)
        lab += [svg, L.leader(bb, (sx(risers['EXT-2'][0]) + 1.7, sy(risers['EXT-2'][1]) - 1.7), C_EXT2, side='bottom')]
    # e) suppression / pull stations (dining side, near P-1)
    if pms:
        lines = [f"SUPRESIÓN · {' / '.join(pm_ids)}",
                 f"HD-1 químico húmedo UL 300: ≈{n1} boquillas",
                 '(aparato + pleno + ducto, según listado)']
        if hd2_supp:
            lines += ['HD-2 sistema listado p/ combustible sólido']
        lines += [f"gabinetes {' / '.join(sid for sid, _ in sups)} sobre K1 (h≈1.60)",
                  f"pulsadores h {pull.get('h', '1.07–1.22 m')}, cara salón de NW-1",
                  '!distancia a la campana: VERIFY (ver A-104)']
        pmx, pmy = P(pms[-1][1])
        h = len(lines) * 1.6 * 1.28 + 1.3
        svg, bb = L.tag(x_din + 10.0, pmy - h + 4.0, lines, C_SUP, size=1.6)
        lab += [svg, L.leader(bb, (pmx + 3.2, pmy), C_SUP, side='left')]
    # f) AR-1 (kitchen floor between the BBQ wall and the diffusers)
    if diffs:
        cm = mua['cases']
        ar = res['_ar_riser']
        lines = ['AR-1 · REPOSICIÓN', f"{mua['design_pct']} % ≈ {mua['design_Q_Ls']:.0f} L/s", f"(80–90 %: {cm[0]['Q_Ls']:.0f}–{cm[-1]['Q_Ls']:.0f})",
                 'difusores ≤0.5 m/s', 'toma ≥3 m de descargas', '!ruta a cubierta: VERIFY', '!(opción: ducto S1)']
        d_last = diffs[-1]
        svg, bb = L.tag(sx(0.72), sy(d_last[1]) + 7.0, lines, C_MUA, size=1.45)
        lab += [svg, L.leader(bb, (sx(d_last[0]) - 3.6, sy(d_last[1]) + 2.0), C_MUA, side='right')]
    # S1 shaft as MUA alternative
    s1 = next((q for q in ex.get('shafts', []) if q['id'] == 'S1'), None)
    if s1:
        r = s1['rect']
        svg, bb = L.tag(sx(r[2]) + 3.0, sy(r[1]) + 1.2, ['S1 · ducto existente', 'alternativa para AR-1 (VERIFY)'], C_MUA, size=1.45)
        lab += [svg, L.leader(bb, (sx(r[2]) - 1.0, sy((r[1] + r[3]) / 2)), C_MUA, side='left')]
    # small tags
    halo = 'paint-order="stroke" stroke="#ffffff" stroke-width="0.8"'
    if dg:
        dx_, dy_ = P(dg)
        lab.append(text(dx_, dy_ + 4.0, 'DG-1', 1.3, weight='800', fill=C_GAS_D, extra=halo))
    if gm.get('main_valve'):
        vx, vy = P(gm['main_valve'])
        lab.append(text(vx - 2.0, vy - 0.6, 'VM', 1.3, anchor='end', weight='800', fill=C_GAS_D, extra=halo))
    if gm.get('solenoid'):
        vx, vy = P(gm['solenoid'])
        lab.append(text(vx - 1.6, vy + 3.3, 'VS', 1.3, anchor='end', weight='800', fill=C_GAS_D, extra=halo))
    for sid, p in sups:
        lab.append(text(sx(p[0]), sy(p[1]) + 3.9, sid, 1.25, weight='800', fill=C_SUP, extra=halo))
    for pid, p in pms:
        lab.append(text(sx(p[0]) + 3.6, sy(p[1]) + 0.5, pid, 1.25, anchor='start', weight='800', fill=C_SUP, extra=halo))
    if hd2:
        x0, y0, x1, y1 = hd2['rect']
        lab.append(text(sx(x1 - 0.24), sy(y0 + 0.5) + 0.5, 'ARR', 1.2, weight='800', fill=C_EXT2, rot=-90, extra=halo))
    s.add('<g id="labels">' + ''.join(lab) + '</g>')
    # ---- vertical schematic
    s.add(m102_section(res, lay, 229.0, 181.0, 364.0, 303.0, L))
    # ---- side panel
    legend = [
        LEGEND_WALLS[0], LEGEND_WALLS[2],
        (sw_line(C_GAS, None, 0.6), 'Gas de la red del C.C. (tubería rígida a la vista)'),
        (sw_sym(lambda x, y: sym_valve(x, y, C_GAS_D, s=1.2)), 'VM válvula de corte manual · VA de equipo'),
        (sw_sym(lambda x, y: sym_valve(x, y, C_GAS_D, s=1.2) + f'<rect x="{f(x + 2)}" y="{f(y - 1.4)}" width="2.1" height="2.1" fill="#fff" stroke="{C_GAS_D}" stroke-width="0.3"/>'),
         'VS válvula solenoide enclavada (rearme manual)'),
        (sw_sym(lambda x, y: sym_circle_tag(x, y, 'DG', C_GAS_D, r=1.6, size=1.1)), 'DG detector de gas (GLP ≤0.30 m del piso)'),
        (sw_rect('none', C_EXT1, dash='2.2 0.9'), 'Campana HD (proyección en altura)'),
        (sw_rect('#ffffff', C_EXT1), 'Ducto horizontal (ancho real) · □ collarín'),
        (sw_sym(lambda x, y: sym_riser(x, y, 1.6, C_EXT1)), 'Collarín / ducto vertical a cubierta'),
        (sw_rect(None, C_EXT2, pattern='url(#m4-hatch-arr)'), 'ARR arrestachispas (antes de filtros)'),
        (sw_sym(lambda x, y: sym_diffuser(x, y, 1.6)), 'AR-1 difusor de aire de reposición'),
        (sw_sym(lambda x, y: sym_nozzle(x, y)), 'Boquilla de supresión (según listado del sistema)'),
        (sw_sym(lambda x, y: sym_box(x, y, 3.0, 2.4, '1', C_SUP, fill=C_SUP, size=1.2, tcol='#fff')), 'SUP-1 / SUP-2 gabinete de agente y control'),
        (sw_sym(lambda x, y: sym_box(x, y, 3.0, 3.0, '1', C_SUP, fill=C_SUP, size=1.2, tcol='#fff')), 'PM-1 / PM-2 disparo manual (h 1.07–1.22)'),
        (sw_line(C_SUP, '1.0 0.6', 0.35), 'Cable de disparo / enclavamiento'),
    ]
    tot = mua['exhaust_total_Ls']
    nz = res.get('_nozzles', {})
    rows = [
        (f"EXT-1 · HD-1 servicio {e1.get('duty_name', '')}", f"{e1.get('Q_Ls', 0):.0f} L/s"),
        ('EXT-2 · HD-2 servicio extra-pesado (sólido)', f"{e2.get('Q_Ls', 0):.0f} L/s"),
        ('Σ extracción (EXT-3 por tiro natural)', f"{tot:.0f} L/s · {mua['exhaust_total_m3h']} m³/h"),
        (f"AR-1 reposición {mua['design_pct']} % (80–90 %)", f"{mua['design_Q_Ls']:.0f} L/s"),
        ('Carga de gas H2–H5 (típica)', f"{gas['total_kW_typ']:.0f} kW · {gas['total_BTUh_typ']/1000:.0f} kBTU/h"),
        ('Consumo GLP / GN', f"{gas['flow_LPG_kg_h']:.1f} kg/h · {gas['flow_NG_m3_h']:.1f} m³/h"),
        ('Boquillas HD-1 / HD-2 (estimado)', f"≈{nz.get('HD-1', 0)} / ≈{nz.get('HD-2', 0)}"),
    ]
    inter = [
        'Disparo de SUP-1 (fusibles o PM-1) en HD-1:',
        '  1 · VS cierra el gas de H2–H5 (rearme manual);',
        '  2 · corte eléctrico de equipos bajo HD-1 (TE-1);',
        '  3 · EXT-1 sigue operando salvo que el listado indique',
        '      otra cosa; 4 · señal a la alarma del C.C. (VERIFY).',
        'SUP-2 (PM-2) protege HD-2 / H1: la brasa no se "corta";',
        '  EXT-2 sigue extrayendo mientras haya combustible.',
        'AR-1 enclavado con EXT-1 / EXT-2; con brasas en H1 o S1',
        '  se mantiene reposición positiva — lógica TO BE ENGINEERED.',
    ]
    eng = [ln for n in mep.get('engineering_notes', []) for ln in (lambda w: [w[0]] + ['  ' + q for q in w[1:]])(wrap(n, 60))]
    notes = [
        '!' + FLAG_ENG,
        '!' + FLAG_SMOKER,
        'Tres sistemas independientes (NFPA 96 cap. 14): EXT-1, EXT-2',
        '  y EXT-3 sin compartir ductos, ventiladores ni descargas.',
        'Ducto de grasa: acero ≥1.37 mm (16 MSG) o inox ≥1.09 mm (18 MSG)',
        '  soldado estanco, sin bolsas, con registros; cerramiento 1 h',
        '  hasta la descarga (NFPA 96 cap. 7, verificar edición).',
        'Velocidad en ducto ≥2.54 m/s (NFPA 96 §8.2.1.1, verificar).',
        'Descargas en cubierta ≥3 m de linderos y de la toma AR-1',
        '  (NFPA 96 §7.8; cifras a confirmar en la edición adoptada).',
        'HD-2: arrestachispas antes de filtros; filtros ≥1.22 m sobre la',
        '  superficie de cocción (cap. 14, TBV); hogar >0.14 m³: manguera',
        '  fija LL-1 (M-101). K2: recirculación listada UL 710B.',
        'Gas: sin cilindros; conectores listados ≤1.5 m con cable de',
        '  restricción; válvula de servicio por equipo.',
    ] + eng + ['Citas de resúmenes, no de textos primarios: verificar.']
    verify = [
        'Estado, sección y ruta del riser existente de Marna’s (EXT-1).',
        'Penetraciones de losa / cubierta para EXT-2 y EXT-3',
        '  (revisión estructural + aprobación del condominio).',
        'Altura a losa y pleno sobre el cielo (3.00 supuesto).',
        'Cubierta: ventiladores y toma AR-1; tipo y presión del gas.',
    ]
    y = s.side_panel([('h', 'Leyenda'), ('legend', legend), ('h', 'Resumen (preliminar)'), ('rows', rows)])
    y = s.side_panel([('h', 'Enclavamientos (a validar)'), ('para', inter), ('h', 'Criterios y normativa'), ('para', notes),
                      ('h', 'VERIFY ON SITE'), ('para', verify)], y=y)
    res.setdefault('_panel_end', {})['M102'] = y
    # ---- calc tables (bottom band)
    s.add(m102_tables(res, 12, 320))
    res.setdefault('_overlaps', {})['M102'] = L.overlaps()
    return s.render()


def _hood_gap_line(lay):
    """Space left above the hoods with the assumed ceiling (same data as A-201 / A-301: NW-2 h = hood lower edge)."""
    ex = load_existing()
    ceil = float((ex.get('ceiling') or {}).get('height_assumed', 3.0))
    nw2 = next((w for w in lay.get('new_walls', []) if w['id'] == 'NW-2'), None)
    low = float(nw2.get('h') or 2.05) if nw2 else 2.05
    top = low + max((float(e.get('h') or 0.6) for e in lay.get('equipment', []) if e.get('key') == 'hood'), default=0.6)
    return (f'Con cielo a {ceil:.2f} m (supuesto) y campanas de {low:.2f} a {top:.2f} m quedan ≈{ceil - top:.2f} m para collarines y '
            'transiciones: VERIFY ON SITE la altura a losa.')


def m102_section(res, lay, x0, y0, x1, y1, L):
    """Vertical schematic (no scale): hoods, ducts, fans, make-up air, gas and suppression interlocks."""
    ext = {r['id']: r for r in res['exhaust']}
    mua = res['mua']
    pull = (lay.get('life_safety') or {}).get('pull_station') or {}
    pm_ids = pull.get('ids') or (['PM-1'] if pull else [])
    two = len(pm_ids) > 1
    fs = 1.55
    g = [f'<rect x="{f(x0)}" y="{f(y0)}" width="{f(x1 - x0)}" height="{f(y1 - y0)}" fill="#ffffff" stroke="#141210" stroke-width="0.35"/>',
         text(x0 + 3, y0 + 5.2, 'ESQUEMA VERTICAL (sin escala)', 2.6, anchor='start', weight='800', extra='letter-spacing="0.3"'),
         text(x1 - 3, y0 + 5.2, 'alturas a verificar', 1.75, anchor='end', weight='700', fill=C_RED)]
    L.register('section', (x0, y0, x1, y1))
    y_roof, y_ceil, y_floor = y0 + 27, y0 + 55, y0 + 106
    mpm = (y_floor - y_ceil) / 3.0          # mm per metre inside the room (ceiling 3.00 assumed)
    H = lambda h: y_floor - h * mpm          # noqa: E731
    xl = x0 + 25
    for yy, lbl, sub, dash in ((y_roof, 'CUBIERTA / LOSA', 'VERIFY ON SITE', '2 1'), (y_ceil, f"CIELO h {float((load_existing().get('ceiling') or {}).get('height_assumed', 3.0)):.2f}", 'supuesto — VERIFY', '2 1'),
                               (y_floor, 'NPT ±0.00', '', None)):
        g.append(mline(xl, yy, x1 - 3, yy, '#555555' if dash else '#141210', 0.35 if dash else 0.55, dash=dash))
        g.append(text(x0 + 3, yy - 0.7, lbl, fs, anchor='start', weight='800', fill='#333'))
        if sub:
            g.append(text(x0 + 3, yy + 2.1, sub, 1.4, anchor='start', fill=C_RED, weight='700'))
    g.append(text(x0 + 3, (y_roof + y_ceil) / 2 + 0.5, 'pleno sobre cielo', 1.4, anchor='start', fill='#666'))
    c_sm, c_h2, c_h1, c_ar = x0 + 35, x0 + 62, x0 + 95, x1 - 13
    # --- EXT-3 smoker
    sm_top = H(1.9)
    g.append(f'<rect x="{f(c_sm - 6.5)}" y="{f(sm_top)}" width="13" height="{f(y_floor - sm_top)}" fill="url(#hatch-smoker)" stroke="{COL["smoker"][1]}" stroke-width="0.35"/>')
    g.append(text(c_sm, sm_top + 5.5, 'S1', 1.8, weight='800', fill='#ffffff', extra=f'paint-order="stroke" stroke="{COL["smoker"][1]}" stroke-width="0.5"'))
    g.append(text(c_sm, y_floor + 3.2, 'smoker', 1.45, fill=C_TXT))
    g.append(f'<rect x="{f(c_sm - 1.7)}" y="{f(y_roof - 10)}" width="3.4" height="{f(sm_top - y_roof + 10)}" fill="#ffffff" stroke="{C_EXT3}" stroke-width="0.45"/>')
    g.append(f'<path d="M{f(c_sm - 3.4)},{f(y_roof - 10)} L{f(c_sm + 3.4)},{f(y_roof - 10)} L{f(c_sm)},{f(y_roof - 13.2)} z" fill="{C_EXT3}"/>')
    g.append(text(c_sm + 2.8, y_roof - 5.4, 'EXT-3', fs, anchor='start', weight='800', fill=C_EXT3))
    g.append(text(c_sm + 2.8, y_roof - 3.2, 'tiro natural', 1.4, anchor='start', fill=C_TXT))
    g.append(text(c_sm + 2.8, y_roof - 1.2, 'arrestachispas', 1.4, anchor='start', fill=C_TXT))
    g.append(text(c_sm + 2.8, (y_ceil + sm_top) / 2, 'chimenea', 1.4, anchor='start', fill=C_TXT))
    g.append(text(c_sm + 2.8, (y_ceil + sm_top) / 2 + 2.0, 'listada NFPA 211', 1.4, anchor='start', fill=C_TXT))

    def hood(cx, wb, wt, c, label, q, appl_w, appl_lbl, solid, marker):
        hb, ht = H(2.0), H(2.6)
        ap_top = H(0.9)
        out = [f'<rect x="{f(cx - appl_w/2)}" y="{f(ap_top)}" width="{f(appl_w)}" height="{f(y_floor - ap_top)}" fill="{COL["fire"][0]}" '
               f'stroke="{COL["fire"][1]}" stroke-width="0.35"/>',
               text(cx, ap_top + 5.0, appl_lbl, fs, weight='800', fill=COL['fire'][1])]
        if solid:
            for k in range(5):
                xx = cx - appl_w / 2 + 2 + k * (appl_w - 4) / 4
                out.append(f'<path d="M{f(xx - 1)},{f(ap_top)} Q{f(xx)},{f(ap_top - 3.2)} {f(xx + 1)},{f(ap_top)}" fill="#f07c14" stroke="#c2410c" stroke-width="0.2"/>')
        out.append(f'<path d="M{f(cx - wb/2)},{f(hb)} L{f(cx - wt/2)},{f(ht)} L{f(cx + wt/2)},{f(ht)} L{f(cx + wb/2)},{f(hb)} z" '
                   f'fill="#fbf1e6" stroke="{c}" stroke-width="0.5"/>')
        out.append(mline(cx + wb / 2 - 2.2, hb - 0.3, cx + wt / 2 - 3.2, ht + 1.3, c, 0.7, dash='0.7 0.35'))
        dw = 5.4
        out.append(f'<rect x="{f(cx - dw/2)}" y="{f(y_roof - 2)}" width="{dw}" height="{f(ht - y_roof + 2)}" fill="#ffffff" stroke="{c}" stroke-width="0.45"/>')
        for sgn in (-1, 1):   # fire-rated enclosure through the plenum
            xe = cx + sgn * (dw / 2 + 0.9)
            out.append(f'<rect x="{f(xe - 0.6)}" y="{f(y_roof)}" width="1.2" height="{f(y_ceil - y_roof)}" fill="url(#m4-hatch-encl)" stroke="none"/>')
        fy = y_roof - 7.0
        out.append(f'<rect x="{f(cx - 5)}" y="{f(fy - 3)}" width="10" height="6" rx="1" fill="#ffffff" stroke="{c}" stroke-width="0.5"/>')
        out.append(f'<circle cx="{f(cx)}" cy="{f(fy)}" r="1.9" fill="none" stroke="{c}" stroke-width="0.35"/>')
        out.append(mline(cx - 1.3, fy - 1.3, cx + 1.3, fy + 1.3, c, 0.25) + mline(cx - 1.3, fy + 1.3, cx + 1.3, fy - 1.3, c, 0.25))
        out.append(mline(cx, fy - 3.0, cx, fy - 7.5, c, 0.5, marker=marker))
        out.append(text(cx + 5.8, fy - 2.6, label, fs, anchor='start', weight='800', fill=c))
        out.append(text(cx + 5.8, fy - 0.5, f"{q:.0f} L/s", 1.45, anchor='start', weight='700', fill=c, family=MONO))
        return ''.join(out), hb, ht
    e1, e2 = ext.get('EXT-1', {}), ext.get('EXT-2', {})
    svg, hb2, ht2 = hood(c_h2, 21, 16, C_EXT2, 'EXT-2', e2.get('Q_Ls', 0), 15, 'H1', True, 'm4-e2')
    g.append(svg)
    svg, hb1, ht1 = hood(c_h1, 30, 25, C_EXT1, 'EXT-1', e1.get('Q_Ls', 0), 26, 'H2–H5', False, 'm4-e1')
    g.append(svg)
    g.append(text(c_h1, H(0.9) + 8.0, 'gas', 1.45, weight='700', fill=COL['fire'][1]))
    # spark arrester + filter-to-fuel dimension on HD-2
    g.append(f'<rect x="{f(c_h2 - 8.2)}" y="{f(hb2 - 3.0)}" width="16.4" height="1.7" fill="url(#m4-hatch-arr)" stroke="{C_EXT2}" stroke-width="0.25"/>')
    g.append(text(c_h2 - 11.6, hb2 - 1.5, 'ARR', 1.45, anchor='end', weight='800', fill=C_EXT2))
    dx_ = c_h2 + 12.0
    g.append(mline(dx_, H(0.9), dx_, hb2 - 1.0, '#333', 0.22))
    g.append(mline(dx_ - 0.9, H(0.9), dx_ + 0.9, H(0.9), '#333', 0.3) + mline(dx_ - 0.9, hb2 - 1.0, dx_ + 0.9, hb2 - 1.0, '#333', 0.3))
    g.append(text(dx_ + 1.9, (H(0.9) + hb2) / 2 - 1.6, 'filtros ≥1.22 m', 1.4, anchor='start', weight='700', fill='#333'))
    g.append(text(dx_ + 1.9, (H(0.9) + hb2) / 2 + 0.6, 'sobre la cocción', 1.4, anchor='start', weight='700', fill='#333'))
    g.append(text(dx_ + 1.9, (H(0.9) + hb2) / 2 + 2.8, '(cap. 14, TBV)', 1.35, anchor='start', fill='#333'))
    # nozzles
    for k in range(4):
        g.append(sym_nozzle(c_h1 - 10 + k * 6.7, hb1 + 1.8))
    g.append(sym_nozzle(c_h1, ht1 + 2.6))
    if two:
        for k in range(2):
            g.append(sym_nozzle(c_h2 - 3.5 + k * 7.0, hb2 + 1.8))
    # --- make-up air
    ar_top = y_roof - 9.5
    g.append(f'<rect x="{f(c_ar - 3.2)}" y="{f(ar_top)}" width="6.4" height="{f(y_ceil - ar_top + 1.5)}" fill="#e6f5f9" stroke="{C_MUA}" stroke-width="0.45"/>')
    g.append(f'<rect x="{f(c_ar - 5.5)}" y="{f(ar_top - 5)}" width="11" height="5" rx="0.8" fill="#ffffff" stroke="{C_MUA}" stroke-width="0.45"/>')
    g.append(text(c_ar, ar_top - 1.7, 'AR-1', fs, weight='800', fill=C_MUA))
    for k in (-1, 1):
        g.append(mline(c_ar + k * 1.3, y_ceil + 1.6, c_ar + k * 4.7, y_ceil + 5.4, C_MUA, 0.5, marker='m4-mua'))
    g.append(text(c_ar, y_ceil + 8.8, f"{mua['design_Q_Ls']:.0f} L/s", 1.45, weight='700', fill=C_MUA, family=MONO))
    g.append(text(c_ar, y_ceil + 11.0, f"({mua['design_pct']} %)", 1.4, fill=C_MUA))
    ys_ = y_roof - 18.0
    g.append(mline(c_h1 + 5, ys_, c_ar - 5.5, ys_, '#333', 0.22))
    g.append(mline(c_h1 + 5, ys_ - 0.9, c_h1 + 5, ys_ + 0.9, '#333', 0.3) + mline(c_ar - 5.5, ys_ - 0.9, c_ar - 5.5, ys_ + 0.9, '#333', 0.3))
    g.append(text((c_h1 + c_ar) / 2, ys_ - 0.9, '≥ 3.0 m (verif.)', 1.4, weight='700', fill='#333'))
    # --- gas + suppression / interlocks
    yg = y_floor - 5.2
    xg0 = x1 - 4
    g.append(f'<polyline points="{f(xg0)},{f(yg)} {f(c_h1 + 13)},{f(yg)}" fill="none" stroke="{C_GAS}" stroke-width="0.65"/>')
    g.append(sym_valve(xg0 - 3.5, yg, C_GAS_D, s=1.25))
    g.append(text(xg0 - 3.5, yg + 3.8, 'VM', 1.4, weight='800', fill=C_GAS_D))
    xvs = c_h1 + 20
    g.append(sym_solenoid(xvs, yg, C_GAS_D))
    g.append(text(xvs, yg + 3.8, 'VS', 1.4, weight='800', fill=C_GAS_D))
    g.append(text(xg0 - 7.0, yg - 1.2, 'GAS C.C.', 1.4, anchor='end', weight='800', fill=C_GAS_D))
    xs_ = c_h1 + 24.5
    s1y = H(1.55)
    g.append(sym_box(xs_, s1y, 7.0, 3.2, 'SUP-1', C_SUP, fill=C_SUP, size=1.35, tcol='#ffffff'))
    dash = 'stroke-dasharray="1 0.6"'
    g.append(f'<polyline points="{f(xs_ - 3.5)},{f(s1y)} {f(c_h1 + 12.5)},{f(s1y)} {f(c_h1 + 12.5)},{f(hb1 + 0.2)}" fill="none" stroke="{C_SUP}" stroke-width="0.3" {dash}/>')
    g.append(f'<polyline points="{f(xs_ - 1.5)},{f(s1y + 1.6)} {f(xs_ - 1.5)},{f(yg - 5.8)} {f(xvs)},{f(yg - 5.8)} {f(xvs)},{f(yg - 3.9)}" '
             f'fill="none" stroke="{C_SUP}" stroke-width="0.3" {dash}/>')
    xpm = xs_ + 8.5
    g.append(sym_box(xpm, s1y, 4.0, 3.2, 'PM-1', C_SUP, fill=C_SUP, size=1.1, tcol='#ffffff'))
    g.append(mline(xs_ + 3.5, s1y, xpm - 2.0, s1y, C_SUP, 0.3, dash='1 0.6'))
    if two:
        s2y = H(2.15)
        g.append(sym_box(xs_, s2y, 7.0, 3.2, 'SUP-2', C_SUP, fill=C_SUP, size=1.35, tcol='#ffffff'))
        g.append(sym_box(xpm, s2y, 4.0, 3.2, 'PM-2', C_SUP, fill=C_SUP, size=1.1, tcol='#ffffff'))
        g.append(mline(xs_ + 3.5, s2y, xpm - 2.0, s2y, C_SUP, 0.3, dash='1 0.6'))
        g.append(f'<polyline points="{f(xs_ - 3.5)},{f(s2y)} {f(xs_ - 5.0)},{f(s2y)} {f(xs_ - 5.0)},{f(ht1 - 2.0)} {f(c_h2 + 8.0)},{f(ht1 - 2.0)} '
                 f'{f(c_h2 + 8.0)},{f(hb2 + 0.2)}" fill="none" stroke="{C_SUP}" stroke-width="0.3" {dash}/>')
    fy = y_floor + 6.6
    for i, ln in enumerate([
        'Tres descargas independientes (EXT-1, EXT-2, EXT-3) + toma AR-1. Ductos de grasa en cerramiento resistente al fuego (1 h,',
        'NFPA 96 cap. 7) con registros; ventiladores upblast listados (UL 762) con acceso de limpieza (EXT-2: limpieza mensual).',
        _hood_gap_line(lay),
    ]):
        g.append(text(x0 + 3, fy + i * 2.35, ln, 1.4, anchor='start', fill='#444' if i < 2 else C_RED, weight='400' if i < 2 else '700'))
    return '<g id="m102-section">' + ''.join(g) + '</g>'


def m102_tables(res, x, y):
    ext = res['exhaust']
    mua = res['mua']
    gas = res['gas']
    g = [text(x, y + 3, 'CÁLCULO PRELIMINAR · EXTRACCIÓN Y AIRE DE REPOSICIÓN', 2.6, anchor='start', weight='800', extra='letter-spacing="0.35"'),
         text(x + 118, y + 3, FLAG_ENG, 1.8, anchor='start', weight='800', fill=C_RED)]
    cols = [(0, 'Sistema', 'start'), (15, 'Sirve a', 'start'), (64, 'Servicio (ASHRAE 154)', 'start'), (104, 'Campana\nL × fondo (m)', 'start'),
            (130, 'Tasa de diseño\ncfm/pie · L/s·m', 'start'), (171, 'Caudal\nL/s', 'end'), (186, '\nm³/h', 'end'), (199, '\ncfm', 'end'),
            (203, 'Sección req.\na 7.5 m/s', 'start'), (223, 'Ducto propuesto\nrect. · circ. (mm)', 'start'), (266, 'v real\nm/s', 'end'),
            (270, '≥2.54 m/s\nNFPA 96', 'start')]
    rows, colors, weights = [], [], []
    for r in ext:
        if r.get('Q_Ls'):
            d = r['duct']
            apps = ', '.join(a['id'] for a in r['appliances'])
            rows.append([r['id'], f"{r['hood']}: {apps}", r['duty_name'], f"{r['hood_length_m']:.2f} × {r['hood_depth_m']:.2f}",
                         f"{r['rate_cfm_per_ft']} · {r['rate_Ls_per_m']:.0f}", f"{r['Q_Ls']:.0f}", f"{r['Q_m3h']}", f"{r['Q_cfm']}",
                         f"{d['area_required_m2']:.3f} m²", f"{d['rect_mm'][0]}×{d['rect_mm'][1]} · Ø{d['round_mm']}",
                         f"{d['velocity_rect_ms']:.1f}", 'sí (prel.)' if r['v_ok'] else 'REVISAR'])
            c = C_EXT1 if r['id'] == 'EXT-1' else C_EXT2
            colors.append([c, None, None, None, None, c, None, None, None, None, None, '#0a7d3b' if r['v_ok'] else C_RED])
            weights.append(['800', None, None, None, None, '800', None, None, None, '700', None, '800'])
        else:
            a = r['alternative_hood']
            rows.append([r['id'], f"{r['appliance']} smoker: chimenea propia", 'tiro natural (fabricante)', '—', 'NFPA 211 / listado', '—', '—', '—',
                         '—', 'Ø150–200 (ficha)', '—', 'n/a'])
            colors.append([C_EXT3] + [None] * 10 + ['#555'])
            weights.append(['800'] + [None] * 11)
            d = a['duct']
            rows.append(['alt.', f"campana sobre {r['appliance']} si se exige", r['duty_name'], f"{a['hood_length_m']:.2f} × {a['hood_depth_m']:.2f}",
                         f"{a['rate_cfm_per_ft']} · {a['rate_Ls_per_m']:.0f}", f"{a['Q_Ls']:.0f}", f"{a['Q_m3h']}", f"{a['Q_cfm']}",
                         f"{d['area_required_m2']:.3f} m²", f"{d['rect_mm'][0]}×{d['rect_mm'][1]} · Ø{d['round_mm']}",
                         f"{d['velocity_rect_ms']:.1f}", 'sí (prel.)'])
            colors.append([C_EXT3, '#555', '#555', '#555', '#555', '#555', '#555', '#555', '#555', '#555', '#555', '#0a7d3b'])
            weights.append([None] * 12)
    rows.append(['Σ EXT', 'EXT-1 + EXT-2 (EXT-3 por tiro natural)', '', '', '', f"{mua['exhaust_total_Ls']:.0f}", f"{mua['exhaust_total_m3h']}",
                 f"{mua['exhaust_total_cfm']}", '', '', '', ''])
    colors.append(['#141210'] * 12)
    weights.append(['800', '700', None, None, None, '800', '700', '700', None, None, None, None])
    for c in mua['cases']:
        design = c['pct'] == mua['design_pct']
        d = mua['duct'] if design else None
        rows.append([f"AR-1 {c['pct']} %", 'aire de reposición' + (' (diseño)' if design else ''), f"transferido del salón {c['transfer_from_dining_Ls']:.0f} L/s",
                     '', '', f"{c['Q_Ls']:.0f}", f"{c['Q_m3h']}", f"{c['Q_cfm']}",
                     f"{d['area_required_m2']:.3f} m² a {V_MUA:g} m/s" if d else '', f"{d['rect_mm'][0]}×{d['rect_mm'][1]} · Ø{d['round_mm']}" if d else '',
                     f"{d['velocity_rect_ms']:.1f}" if d else '', ''])
        colors.append([C_MUA, None, '#555', None, None, C_MUA, None, None, None, None, None, None])
        weights.append(['800' if design else '600', '700' if design else None, None, None, None, '800' if design else None,
                        None, None, None, '700' if design else None, None, None])
    svg, yy = table(x, y + 6, cols, rows, size=1.62, rh=3.72, head=1.5, colors=colors, weights=weights, head_lines=2,
                    families=[None, None, None, MONO, MONO, MONO, MONO, MONO, MONO, MONO, MONO, None], width=284)
    g.append(svg)
    e1 = next((r for r in ext if r['id'] == 'EXT-1'), {})
    ec = e1.get('existing_collar')
    foot = [
        'Tasas: caudal mínimo de campana mural NO listada según el servicio (ASHRAE 154 / IMC 507): medio 300, extra-pesado (combustible sólido) 550 cfm/pie.',
        f"Campanas listadas UL 710 suelen operar con menos (típ. medio 200–300, sólido ≥350 cfm/pie; guías CKV / fabricante): EXT-1 {e1.get('listed_range_Ls', ['', ''])[0]}–{e1.get('listed_range_Ls', ['', ''])[1]} L/s.",
        f"Sección = Q / 7.5 m/s (práctica usual 7.6–9.1 m/s); NFPA 96 §8.2.1.1 exige ≥2.54 m/s (500 fpm). Reposición 80–90 %, ducto a {V_MUA:g} m/s.",
        (f"AR-1: {mua['diffusers']['count']} difusores × ≈{mua['diffusers']['Q_each_Ls']:.0f} L/s → ≈{mua['diffusers']['min_face_area_each_m2_at_0.5ms']:.1f} m² de cara c/u a 0.5 m/s: "
         'pleno perimetral o más difusores — TO BE ENGINEERED.') if mua.get('diffusers') else '',
        (f"Collarín existente de Marna’s {ec['section_m'][0]:.2f} × {ec['section_m'][1]:.2f} m = {ec['area_m2']:.2f} m² → {ec['velocity_ms']:.1f} m/s con el caudal de EXT-1: "
         'compatible por velocidad si el ducto mantiene la sección — VERIFY ON SITE.') if ec else '',
    ]
    for i, ln in enumerate([q for q in foot if q]):
        g.append(text(x, yy + 3.2 + i * 2.55, ln, 1.45, anchor='start', fill='#333'))
    # gas table (right)
    gx = x + 300
    g.append(text(gx, y + 3, 'GAS · CARGA TÉRMICA Y DIÁMETROS', 2.6, anchor='start', weight='800', extra='letter-spacing="0.35"'))
    gcols = [(0, 'Consumidor', 'start'), (46, 'kW típ.', 'end'), (63, 'BTU/h', 'end'), (66, 'Ramal\nGLP · GN', 'start')]
    grows, gcolors, gweights = [], [], []
    for c in gas['consumers']:
        grows.append([f"{c['id']} · {c['label'][:28]}", f"{c['kW_typ']:.1f}", f"{c['BTUh_typ']:,.0f}".replace(',', ' '),
                      f"{c['branch_LPG']} · {c['branch_NG']}"])
        gcolors.append([C_GAS_D, None, None, None])
        gweights.append(['700', None, None, None])
    grows.append(['Total (simultáneo)', f"{gas['total_kW_typ']:.1f}", f"{gas['total_BTUh_typ']:,.0f}".replace(',', ' '), ''])
    gcolors.append(['#141210'] * 4)
    gweights.append(['800', '800', '800', None])
    for lbl, v in gas['main_pipe'].items():
        grows.append([f"Principal ({lbl}, {v['length_ft_table']} pies)", '', '', f"{v['LPG']} · {v['NG']}"])
        gcolors.append([C_GAS_D, None, None, C_GAS_D])
        gweights.append(['700', None, None, '800'])
    svg, gy = table(gx, y + 6, gcols, grows, size=1.6, rh=3.72, head=1.5, colors=gcolors, weights=gweights, head_lines=2,
                    families=[None, MONO, MONO, MONO], width=116)
    g.append(svg)
    gfoot = [f"Consumo ≈{gas['flow_LPG_kg_h']:.1f} kg/h GLP ({gas['flow_LPG_m3_h']:.1f} m³/h) o {gas['flow_NG_m3_h']:.1f} m³/h GN.",
             'Tablas NFPA 54 de referencia (céd. 40, ΔP 0.5" c.a.);',
             'potencias típicas: usar fichas técnicas. Para GLP rigen',
             'además NFPA 58 y disposiciones de Bomberos.',
             f"Recomendado: principal 1\" GLP / 1-1/4\" GN — {PRELIM}."]
    for i, ln in enumerate(gfoot):
        g.append(text(gx, gy + 3.2 + i * 2.5, ln, 1.45, anchor='start', fill='#333' if i < 4 else C_RED, weight='400' if i < 4 else '700'))
    return '<g id="m102-tables">' + ''.join(g) + '</g>'


# ============================================================================ plug-in entry point
def sheets(ex, lay, val):
    res = compute(ex, lay, val)
    try:
        with open(os.path.join(ROOT, 'data', 'mech_calcs.json'), 'w') as fh:
            json.dump(calcs_json(res, lay), fh, indent=1, ensure_ascii=False)
    except OSError as err:   # read-only checkout: the sheets still render
        print('WARNING: mech_calcs.json not written:', err)
    m101 = build_m101(ex, lay, val, res)
    m102 = build_m102(ex, lay, val, res)
    if os.environ.get('LAVA_SHEET_DEBUG'):
        print('overlaps', json.dumps(res.get('_overlaps'), ensure_ascii=False))
        print('panel end', res.get('_panel_end'))
    return [
        {'id': 'M101', 'file': 'lava_M101_hidrosanitario.svg', 'title': 'Hidrosanitario (esquema)', 'order': 401, 'svg': m101},
        {'id': 'M102', 'file': 'lava_M102_gas_extraccion.svg', 'title': 'Gas, extracción, aire de reposición y supresión (esquema)',
         'order': 402, 'svg': m102},
    ]


if __name__ == '__main__':
    _ex = load_existing()
    _lay = load_json(os.path.join(ROOT, 'data', 'layout.json'))
    _vp = os.path.join(ROOT, 'data', 'validation.json')
    _val = load_json(_vp) if os.path.exists(_vp) else None
    _res = compute(_ex, _lay, _val)
    _out = calcs_json(_res, _lay)
    with open(os.path.join(ROOT, 'data', 'mech_calcs.json'), 'w') as _fh:
        json.dump(_out, _fh, indent=1, ensure_ascii=False)
    for _r in _out['exhaust']['systems']:
        print(_r['id'], _r.get('Q_Ls'), (_r.get('duct') or {}).get('rect_mm'), (_r.get('duct') or {}).get('velocity_rect_ms'))
    print('MUA', _out['makeup_air']['design_Q_Ls'], _out['makeup_air']['duct']['rect_mm'])
    print('gas', _out['gas']['total_kW_typ'], _out['gas']['main_pipe'])
    print('HW', _out['hot_water']['CA-1'])
    print('GT', _out['grease_trap']['recommendation'])
