"""A-201 · Cielos reflejados e iluminación (plano de cielo reflejado, 1:50 en A2).

Plug-in de lámina extra: sheets(ex, lay, val) -> [{id, file, title, order, svg}].

Todo sale de data/existing.json + data/layout.json (+ validation.json):
  * tipos de cielo por zona (CT-1 estructura expuesta negro mate en salón/barra; CT-2 / CT-3 cielos lisos lavables en
    cocina, BBQ, lavado y cold prep), nivel = existing.ceiling.height_assumed (3.00 supuesto, VERIFY ON SITE);
  * luminarias: decor (colgantes, apliques, listones, rótulo, relieve de leños) + propuesta calculada (rieles sobre las filas de
    mesas, downlights en circulaciones, herméticas IP65 en cocina por método de lúmenes, luces integradas en campanas);
  * emergencia, rótulos de salida y detectores de layout.life_safety;
  * campanas HD-1 / HD-2 (equipment overhead), ductos y montantes de layout.mep.exhaust, difusores de aire de reposición
    (mep.makeup_air) y chimenea del smoker.

`ceiling_layout(ex, lay, val)` también la usa la lámina A-301 (cortes) para dibujar los mismos elementos en alzado.
ANTEPROYECTO: posiciones, niveles lumínicos y especificaciones a validar por el profesional responsable (CFIA) y los
ingenieros electricista / mecánico.
"""
import math
import os
import sys

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lavageo import R, premises, standing_existing_walls  # noqa: E402
from plan_svg import FONT, MONO, S, Sheet, f, mtext, rect_el, sx, sy, text, tw  # noqa: E402

# ---------------------------------------------------------------------------------------------- criteria
LUX_KITCHEN = 500      # lx de diseño en áreas de preparación/cocción/lavado (referencia EN 12464-1; Salud no fija lux: a validar)
LM_L8 = 4000           # lm por luminaria hermética IP65 1.20 m (referencia de catálogo, a validar)
UF, MF = 0.55, 0.80    # factor de utilización / mantenimiento (estimación)
L8_LEN, L8_W = 1.20, 0.12
DUCT_W = {'EXT-1': 0.35, 'EXT-2': 0.35, 'EXT-3': 0.25}   # anchos esquemáticos en planta (m) — TO BE ENGINEERED
CT_OF_ZONE = {'D': 'CT-1', 'C': 'CT-1', 'B': 'CT-2', 'E': 'CT-2', 'W': 'CT-3', 'A': 'CT-3'}

C_GREASE = '#b35900'   # ducto de grasa (gas)
C_SOLID = '#c2410c'    # combustible sólido
C_FLUE = '#6e2508'     # chimenea smoker
C_MUA = '#1f63c6'      # aire de reposición
C_EM = '#3a3000'
C_FIRE = '#c1121f'
C_EGR = '#0a7d3b'
C_LIGHT = '#ffb347'
C_RED = '#b00020'


def ct_defs(ceil):
    """Ceiling types (text in Spanish; level from existing.ceiling)."""
    lv = f"+{ceil:.2f}"
    return [
        {'id': 'CT-1', 'zones': ['D', 'C'], 'short': 'SALÓN / BARRA', 'pattern': 'url(#ct1)', 'stroke': '#2a2522',
         'name': 'Estructura expuesta pintada negro mate',
         'finish': 'Sin cielo suspendido: losa, vigas e instalaciones vistas (ductos, bandejas, rieles) pintadas negro mate '
                   '(como el render). Pintura de baja emisión; instalaciones ordenadas y soportadas a la estructura.',
         'level': f'{lv} fondo de estructura (supuesto)'},
        {'id': 'CT-2', 'zones': ['B', 'E'], 'short': 'COCINA CALIENTE / BBQ', 'pattern': 'url(#ct2)', 'stroke': '#c2410c',
         'name': 'Cielo liso lavable INCOMBUSTIBLE',
         'finish': 'Fibrocemento o lámina metálica con pintura epóxica/sanitaria, juntas selladas, color claro. Sello incombustible '
                   'alrededor de campanas, ductos y chimenea (NFPA 96: 0 mm a incombustibles — verificar).',
         'level': f'{lv} (supuesto) · nunca < 2.40'},
        {'id': 'CT-3', 'zones': ['W', 'A'], 'short': 'LAVADO / COLD PREP', 'pattern': 'url(#ct3)', 'stroke': '#2f6fd0',
         'name': 'Cielo liso lavable resistente a humedad',
         'finish': 'Panel sanitario PVC / fibra de vidrio o gypsum RH con pintura epóxica, color claro, sin juntas abiertas ni '
                   'superficies que acumulen polvo o condensación (Salud DE 37308-S — artículo a confirmar).',
         'level': f'{lv} (supuesto) · nunca < 2.40'},
    ]


LUM_TYPES = {
    'L-1': {'name': 'Proyector LED orientable sobre riel negro', 'spec': '≈10 W · 2700 K · IRC ≥90 · dimerizable', 'mount': 'Riel adosado a estructura'},
    'L-2': {'name': 'Downlight cilíndrico de superficie negro Ø≈0.10', 'spec': '≈12 W · 2700 K · UGR < 19 · dimerizable', 'mount': 'Adosado a estructura'},
    'L-3': {'name': 'Colgante domo negro Ø0.24 (decor)', 'spec': 'LED ≈8 W · 2700 K · dimerizable', 'mount': 'Suspendido · borde inf. h {h}'},
    'L-4': {'name': 'Aplique de pared cono negro (decor)', 'spec': 'LED ≈6 W · 2700 K', 'mount': 'Muro norte · h {h}'},
    'L-5': {'name': 'Tira LED lineal (listones / relieve de leños)', 'spec': '≈10 W/m · 2700 K · perfil con difusor', 'mount': 'Oculta en mobiliario'},
    'L-6': {'name': 'Rótulo LAVA con halo retroiluminado', 'spec': 'LED ámbar · fuente remota', 'mount': 'Faja sobre vidrio · eje h {h}'},
    'L-7': {'name': 'Lámparas de calor del pase C2 (equipo)', 'spec': 'Según proveedor del pase', 'mount': 'Sobre repisa de pase'},
    'L-8': {'name': 'Hermética LED IP65 lineal 1.20 m', 'spec': f'≈{LM_L8} lm · 4000 K · difusor PC inastillable', 'mount': 'Adosada a cielo CT-2 / CT-3'},
    'L-9': {'name': 'Luminaria integrada en campana (listada)', 'spec': 'Suministro del fabricante de HD-1 / HD-2', 'mount': 'Dentro de la campana'},
    'EM': {'name': 'Luz de emergencia autónoma (ver A-104)', 'spec': '≥1.5 h · ≥10.8 lx prom. / ≥1.1 lx mín.', 'mount': 'Muro o cielo · h ≈2.40'},
    'RS': {'name': 'Rótulo SALIDA iluminado (ver A-104)', 'spec': 'Autónomo ≥1.5 h · direccional', 'mount': 'Sobre puerta / colgante'},
}


# ---------------------------------------------------------------------------------------------- helpers
def _rect(r):
    x0, y0, x1, y1 = r
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _c(r):
    x0, y0, x1, y1 = _rect(r)
    return (x0 + x1) / 2, (y0 + y1) / 2


def filter_min(lay, default=1.22):
    """Minimum height of the HD-2 (solid fuel) grease filters above the cooking surface, read from the hood note in
    layout.json ('filtros ≥1.22 m ...'); NFPA 96 cap. 14 — TBV."""
    import re
    for e in lay.get('equipment', []):
        if e.get('key') == 'hood' and 'solid' in (e.get('system') or ''):
            m = re.search(r'filtros\s*≥\s*([0-9]+(?:\.[0-9]+)?)\s*m', e.get('note', ''))
            if m:
                return float(m.group(1))
    return default


def hood_items(lay):
    return [e for e in lay.get('equipment', []) if e.get('key') == 'hood' or (e.get('overhead') and e.get('cat') == 'hood')]


def hood_low(lay):
    """Hood lower edge: the floor-to-hood side panel (new partition touching a hood) gives it; default 2.05 (TBV)."""
    hoods = hood_items(lay)
    for w in lay.get('new_walls', []):
        if w.get('type') == 'partition' and w.get('h') and any(R(w['rect']).buffer(0.02).intersects(R(h['rect'])) for h in hoods):
            return float(w['h'])
    return 2.05


def section_cuts(lay):
    """A-A through the charcoal grill (Y of its centre); B-B through the X band shared by every hot-line item; 5 cm grid."""
    eq = lay.get('equipment', [])
    p = next((e for e in eq if e.get('key') == 'parrilla'), None)
    line = [e for e in eq if e.get('cat') == 'fire' and e.get('key') in ('parrilla', 'cocina_4q', 'plancha', 'freidora_1', 'freidora_2')]
    ya = math.floor(_c(p['rect'])[1] * 20) / 20 if p else 3.15
    if line:
        a = max(_rect(e['rect'])[0] for e in line)
        b = min(_rect(e['rect'])[2] for e in line)
        xb = math.floor((a + b) / 2 * 20) / 20 if b > a else math.floor(_c(line[0]['rect'])[0] * 20) / 20
    else:
        xb = 3.9
    return {'A': {'axis': 'y', 'at': ya, 'look': (0, -1)}, 'B': {'axis': 'x', 'at': xb, 'look': (1, 0)}}


def _largest_rect(mask):
    """Largest all-True axis-aligned rectangle in a boolean grid -> (area, (c0, r0, c1, r1)) inclusive."""
    nr, nc = mask.shape
    h = np.zeros(nc, dtype=int)
    best = (0, None)
    for i in range(nr):
        h = np.where(mask[i], h + 1, 0)
        stack = []
        for j in range(nc + 1):
            cur = h[j] if j < nc else 0
            start = j
            while stack and stack[-1][1] >= cur:
                s0, hh = stack.pop()
                area = hh * (j - s0)
                if area > best[0]:
                    best = (area, (s0, i - hh + 1, j - 1, i))
                start = s0
            stack.append((start, cur))
    return best


def _fixture_box(cx, cy, along):
    hl, hw = L8_LEN / 2, L8_W / 2
    return box(cx - hl, cy - hw, cx + hl, cy + hw) if along == 'x' else box(cx - hw, cy - hl, cx + hw, cy + hl)


def _place_rect(rect, n, region, avoid, gap=0.25):
    """n fixtures in lines along the rectangle's long axis; each line shifted as a whole to dodge `avoid`."""
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    along = 'y' if h >= w else 'x'
    La, Lc = (h, w) if along == 'y' else (w, h)
    best = None
    for m in range(1, 5):
        for k in range(1, 8):
            if m * k < n or m * k > n + 1:
                continue
            sa, sc = La / k, Lc / m
            if sa < L8_LEN + gap:
                continue
            score = max(sa, sc) + 0.2 * (m * k - n) + (0.3 if m > 1 and sc < 0.9 else 0)
            if best is None or score < best[0]:
                best = (score, m, k, sa, sc)
    if best is None:     # too short: one fixture per line across
        along = 'x' if along == 'y' else 'y'
        La, Lc = Lc, La
        best = (0, 1, max(1, min(n, int(La // (L8_LEN + gap)))), La / max(1, min(n, int(La // (L8_LEN + gap)))), Lc)
    _, m, k, sa, sc = best
    a0 = y0 if along == 'y' else x0
    c0 = x0 if along == 'y' else y0
    out = []
    offs_c = sorted({round(sg * d * 0.05, 3) for d in range(0, 13) for sg in (1, -1)}, key=lambda v: (abs(v), -v))
    offs_a = sorted({round(sg * d * 0.05, 3) for d in range(0, 13) for sg in (1, -1)}, key=lambda v: (abs(v), -v))
    for j in range(m):
        cc = c0 + (j + 0.5) * sc
        best_line = []
        for doff in offs_c:
            line = []
            for i in range(k):
                ca = a0 + (i + 0.5) * sa
                for aoff in offs_a:
                    px, py = (cc + doff, ca + aoff) if along == 'y' else (ca + aoff, cc + doff)
                    b = _fixture_box(px, py, along)
                    if region.contains(b) and not avoid.intersects(b) and all(b.distance(q) >= gap for q in line_boxes(out + line)):
                        line.append(((px, py), along))
                        break
            if len(line) > len(best_line):
                best_line = line
            if len(line) == k:
                break
        out.extend(best_line)
    return out


def line_boxes(line):
    return [_fixture_box(p[0], p[1], a) for p, a in line]


# ---------------------------------------------------------------------------------------------- layout
def ceiling_layout(ex, lay, val=None):
    ceil = float((ex.get('ceiling') or {}).get('height_assumed') or 3.0)
    hl = hood_low(lay)
    prem = premises(ex)
    ls = lay.get('life_safety', {}) or {}
    mep = lay.get('mep', {}) or {}
    eq = lay.get('equipment', [])
    zpoly = {z['id']: Polygon(z['poly']).intersection(prem) for z in lay.get('zones', [])}
    walls = unary_union([g for _, g in standing_existing_walls(ex, lay)] + [R(c['rect']) for c in ex.get('columns', [])]
                        + [R(w['rect']) for w in lay.get('new_walls', [])])

    # ---- hoods
    hoods = []
    for h in hood_items(lay):
        x0, y0, x1, y1 = _rect(h['rect'])
        hoods.append({'id': h['id'], 'rect': (x0, y0, x1, y1), 'z0': hl, 'z1': hl + float(h.get('h') or 0.6),
                      'system': h.get('system', ''), 'label': h.get('plan_label') or h.get('label', ''), 'item': h})
    hood_geom = unary_union([R(h['rect']) for h in hoods]) if hoods else Polygon()

    # ---- ceiling devices from life_safety / mep
    em = [tuple(p) for p in ls.get('emergency_lights', [])]
    hot = unary_union([zpoly[z] for z in ('B', 'E') if z in zpoly]) if any(z in zpoly for z in ('B', 'E')) else Polygon()
    det = [{'at': tuple(p), 'kind': 'T' if hot.buffer(0.01).contains(Point(p)) else 'H'} for p in ls.get('smoke_detectors', [])]
    exits = [dict(e) for e in ls.get('exit_signs', [])]
    mua = mep.get('makeup_air', {}) or {}
    diff = [{'at': tuple(p), 'size': 0.60, 'id': mua.get('id', 'AR')} for p in mua.get('diffusers', [])]

    # ---- ducts / risers
    ducts = []
    collar_rect = (ex.get('existing_hood') or {}).get('collar')
    for xh in mep.get('exhaust', []):
        pts = [tuple(p) for p in (xh.get('route') or [])] or ([tuple(xh['collar'])] if xh.get('collar') else [])
        kind = xh.get('kind', '')
        color = C_FLUE if 'chimenea' in kind else (C_SOLID if 'sólido' in kind or 'solido' in kind else C_GREASE)
        d = {'id': xh['id'], 'serves': xh.get('serves'), 'kind': kind, 'pts': pts, 'w': DUCT_W.get(xh['id'], 0.3), 'color': color,
             'riser_note': xh.get('riser', ''), 'fan': xh.get('fan', ''), 'note': xh.get('note', ''), 'collar': tuple(xh.get('collar') or pts[0])}
        d['riser_at'] = pts[-1]
        if collar_rect and R(collar_rect).buffer(0.05).contains(Point(pts[-1])):   # transition to the existing (Marna's) riser
            d['riser_rect'] = tuple(collar_rect)
            d['existing_riser'] = True
        ducts.append(d)
    duct_geom = unary_union([LineString(d['pts']).buffer(d['w'] / 2, cap_style=2) if len(d['pts']) > 1 else Point(d['collar']).buffer(d['w'] / 2)
                             for d in ducts]) if ducts else Polygon()

    dev_pts = [p for p in em] + [d['at'] for d in det] + [tuple(e['at']) for e in exits]
    dev_geom = unary_union([Point(p).buffer(0.26) for p in dev_pts] + [box(p['at'][0] - p['size'] / 2, p['at'][1] - p['size'] / 2,
                                                                       p['at'][0] + p['size'] / 2, p['at'][1] + p['size'] / 2) for p in diff])

    lights = []   # {type, at, zone, src, ...}
    # ---- decor-driven
    for dc in lay.get('decor', []):
        t = dc.get('type')
        r = _rect(dc['rect'])
        if t == 'pendant':
            lights.append({'type': 'L-3', 'at': _c(r), 'h': dc.get('h'), 'src': 'decor', 'r': (r[2] - r[0]) / 2})
        elif t == 'sconce':
            lights.append({'type': 'L-4', 'at': _c(r), 'rect': r, 'face': dc.get('face'), 'h': dc.get('h'), 'src': 'decor'})
        elif t in ('slat_wall', 'firewood_niche', 'planter'):
            lights.append({'type': 'L-5', 'rect': r, 'face': dc.get('face'), 'h': dc.get('h'), 'z': dc.get('z'), 'src': 'decor', 'what': t,
                           'len': max(r[2] - r[0], r[3] - r[1])})
        elif t == 'sign':
            lights.append({'type': 'L-6', 'rect': r, 'face': dc.get('face'), 'h': dc.get('h'), 'size': dc.get('size'), 'text': dc.get('text', 'LAVA'), 'src': 'decor'})
    for e in eq:
        if e.get('key') == 'pass':
            lights.append({'type': 'L-7', 'rect': _rect(e['rect']), 'src': 'equipo', 'of': e['id']})

    # ---- dining: tracks over table rows (spots over each table)
    tables = lay.get('tables', [])
    rows = []
    for t in sorted(tables, key=lambda t: _c(t['rect'])[1]):
        cy = _c(t['rect'])[1]
        if rows and abs(rows[-1]['y'] - cy) < 0.4:
            rows[-1]['t'].append(t)
        else:
            rows.append({'y': cy, 't': [t]})
    tracks = []
    for rw in rows:
        xs0 = min(_rect(t['rect'])[0] for t in rw['t'])
        xs1 = max(_rect(t['rect'])[2] for t in rw['t'])
        spots = []
        for t in sorted(rw['t'], key=lambda t: _rect(t['rect'])[0]):
            x0, y0, x1, y1 = _rect(t['rect'])
            cx = (x0 + x1) / 2
            spots += [(cx, rw['y'])] if (x1 - x0) < 1.0 else [(cx - (x1 - x0) / 4, rw['y']), (cx + (x1 - x0) / 4, rw['y'])]
        tracks.append({'p0': (xs0 - 0.15, rw['y']), 'p1': (xs1 + 0.15, rw['y']), 'spots': spots, 'tables': [t['id'] for t in rw['t']]})
    for tr in tracks:
        for p in tr['spots']:
            lights.append({'type': 'L-1', 'at': p, 'src': 'propuesta'})

    # ---- dining: downlights on circulation lines (aligned with the life-safety devices, dodging them)
    down = []
    busy = dev_pts + [l['at'] for l in lights if l.get('at')]

    def free(p, rad=0.55):
        return all(math.dist(p, q) >= rad for q in busy + down)

    if len(rows) >= 2:
        n_ids = {t['id'] for t in rows[0]['t']}
        s_ids = {t['id'] for t in rows[-1]['t']}
        cn = [_rect(c['rect']) for c in lay.get('chairs', []) if c.get('table') in n_ids]
        cs = [_rect(c['rect']) for c in lay.get('chairs', []) if c.get('table') in s_ids]
        ya = ((max(r[3] for r in cn) if cn else max(_rect(t['rect'])[3] for t in rows[0]['t'])) +
              (min(r[1] for r in cs) if cs else min(_rect(t['rect'])[1] for t in rows[-1]['t']))) / 2
        xa0 = min(_rect(t['rect'])[0] for t in tables) + 0.5
        ko = [_rect(k['rect']) for k in ex.get('keepouts', [])]
        xa1 = min([k[0] for k in ko] + [max(_rect(t['rect'])[2] for t in tables) + 0.5]) - 0.3
        on = sorted(p[0] for p in dev_pts if abs(p[1] - ya) < 0.3 and xa0 - 0.6 <= p[0] <= xa1 + 0.6)
        anch = []
        for x in on:
            if anch and x - anch[-1][-1] < 0.3:
                anch[-1].append(x)
            else:
                anch.append([x])
        nodes = [xa0 - 0.6] + [sum(a) / len(a) for a in anch] + [xa1 + 0.6]
        for a, b in zip(nodes, nodes[1:]):
            k = max(0, round((b - a) / 1.2) - 1)
            for j in range(1, k + 1):
                p = (a + (b - a) * j / (k + 1), ya)
                if free(p, 0.4):
                    down.append(p)
        aisle = {'y': ya, 'x0': xa0, 'x1': xa1}
    else:
        aisle = None
    # bar service aisle (between the new partition and the bar counters)
    part = next((w for w in lay.get('new_walls', []) if w.get('role') == 'kitchen_dining_partition'), None)
    bar = [_rect(e['rect']) for e in eq if e.get('cat') == 'bar' and not e.get('stack_with')]
    if part and bar:
        px1 = _rect(part['rect'])[2]
        bx0 = min(r[0] for r in bar)
        by0, by1 = min(r[1] for r in bar), max(r[3] for r in bar)
        xb = (px1 + bx0) / 2
        nb = max(1, math.ceil((by1 - by0 - 0.4) / 1.2))
        for i in range(nb):
            p = (xb, by0 + 0.2 + (i + 0.5) * (by1 - by0 - 0.4) / nb)
            if free(p, 0.4):
                down.append(p)
        # lobby in front of the kitchen door (between partition, bar and the first south-row table)
        s_row = rows[-1]['t'] if rows else []
        lx1 = min(_rect(t['rect'])[0] for t in s_row) - 0.1 if s_row else px1 + 2.0
        ly0, ly1 = by1 + 0.1, _rect(part['rect'])[3]
        lx = (px1 + lx1) / 2
        for fy in (0.28, 0.75):
            p = (lx, ly0 + fy * (ly1 - ly0))
            if not free(p, 0.5):
                p = (lx + 0.45, p[1])
            if free(p, 0.45):
                down.append(p)
    # reception / delivery desk at the entrance
    for e in eq:
        if e.get('key') == 'delivery_staging':
            p = _c(e['rect'])
            if free(p, 0.45):
                down.append(p)
    for p in down:
        lights.append({'type': 'L-2', 'at': p, 'src': 'propuesta'})

    # ---- kitchen: IP65 fixtures by lumen method, fitted into the largest free rectangles of each zone
    tall = unary_union([R(e['rect']) for e in eq if not e.get('overhead') and (float(e.get('h') or 0) >= 1.8 or e.get('cat') == 'smoker')])
    avoid = unary_union([hood_geom.buffer(0.12), duct_geom.buffer(0.08), dev_geom.buffer(0.04), tall])
    calc = []
    for zid in ('B', 'E', 'W', 'A'):
        if zid not in zpoly:
            continue
        z = zpoly[zid]
        region = z.difference(walls.buffer(0.02)).difference(hood_geom.buffer(0.05))
        area_zone = next((zz['area_m2'] for zz in ((val or {}).get('metrics', {}) or {}).get('zones', []) if zz['id'] == zid), z.area)
        a_eff = region.area
        need = max(1, math.ceil(LUX_KITCHEN * a_eff / (LM_L8 * UF * MF)))
        reg_in = region.buffer(-0.12)
        # rectangles
        x0, y0, x1, y1 = reg_in.bounds
        st = 0.05
        xs = np.arange(x0 + st / 2, x1, st)
        ys = np.arange(y0 + st / 2, y1, st)
        XX, YY = np.meshgrid(xs, ys)
        mask = shapely.contains_xy(reg_in, XX, YY)
        rects = []
        for _ in range(4):
            area, rr = _largest_rect(mask)
            if not rr:
                break
            c0, r0, c1, r1 = rr
            rect = (xs[c0] - st / 2, ys[r0] - st / 2, xs[c1] + st / 2, ys[r1] + st / 2)
            wr, hr = rect[2] - rect[0], rect[3] - rect[1]
            if wr * hr < 1.0 or min(wr, hr) < 0.35 or max(wr, hr) < L8_LEN + 0.1:
                break
            rects.append(rect)
            mask[r0:r1 + 1, c0:c1 + 1] = False
        tot = sum((r[2] - r[0]) * (r[3] - r[1]) for r in rects) or 1
        alloc = [max(1, round(need * (r[2] - r[0]) * (r[3] - r[1]) / tot)) if (r[2] - r[0]) * (r[3] - r[1]) > 2.0 else 0 for r in rects]
        if rects and sum(alloc) < need:
            alloc[0] += need - sum(alloc)
        placed = []
        for rect, n in zip(rects, alloc):
            if n <= 0:
                continue
            for (p, along) in _place_rect(rect, n, reg_in.buffer(0.001), unary_union([avoid] + [_fixture_box(q[0], q[1], a) for q, a in placed])):
                placed.append((p, along))
        for p, along in placed:
            lights.append({'type': 'L-8', 'at': p, 'along': along, 'zone': zid, 'src': 'propuesta'})
        calc.append({'zone': zid, 'area': area_zone, 'area_eff': round(a_eff, 2), 'lux': LUX_KITCHEN, 'need': need, 'drawn': len(placed),
                     'lux_est': round(len(placed) * LM_L8 * UF * MF / a_eff) if a_eff else 0})
    # ---- hood lights (integrated, listed)
    for h in hoods:
        x0, y0, x1, y1 = h['rect']
        L = max(x1 - x0, y1 - y0)
        n = max(1, round(L / 1.0))
        vert = (y1 - y0) >= (x1 - x0)
        for i in range(n):
            a = (i + 0.5) / n
            p = ((x0 + x1) / 2 - (x1 - x0) * 0.12, y0 + a * (y1 - y0)) if vert else (x0 + a * (x1 - x0), (y0 + y1) / 2)
            lights.append({'type': 'L-9', 'at': p, 'of': h['id'], 'src': 'campana'})

    cts = ct_defs(ceil)
    ct_regions = []
    for ct in cts:
        g = unary_union([zpoly[z] for z in ct['zones'] if z in zpoly]) if any(z in zpoly for z in ct['zones']) else Polygon()
        ct_regions.append({'ct': ct, 'geom': g})
    return {'ceil': ceil, 'hood_low': hl, 'hoods': hoods, 'em': em, 'det': det, 'exits': exits, 'diff': diff, 'mua': mua,
            'ducts': ducts, 'lights': lights, 'tracks': tracks, 'aisle': aisle, 'calc': calc, 'cts': cts, 'ct_regions': ct_regions,
            'zpoly': zpoly, 'cuts': section_cuts(lay)}




# ============================================================================================== drawing helpers (sheet mm)
DEFS = ('<defs>'
        '<pattern id="ct1" patternUnits="userSpaceOnUse" width="2.4" height="2.4" patternTransform="rotate(45)">'
        '<rect width="2.4" height="2.4" fill="#2a2522" fill-opacity="0.11"/>'
        '<line x1="0" y1="0" x2="0" y2="2.4" stroke="#2a2522" stroke-opacity="0.30" stroke-width="0.2"/></pattern>'
        '<pattern id="ct2" patternUnits="userSpaceOnUse" width="2.2" height="2.2">'
        '<rect width="2.2" height="2.2" fill="#fdecd9" fill-opacity="0.85"/>'
        '<path d="M0.7,1.1 H1.5 M1.1,0.7 V1.5" stroke="#c2410c" stroke-opacity="0.42" stroke-width="0.16"/></pattern>'
        '<pattern id="ct3" patternUnits="userSpaceOnUse" width="2.2" height="2.2">'
        '<rect width="2.2" height="2.2" fill="#e3eefb" fill-opacity="0.9"/>'
        '<circle cx="1.1" cy="1.1" r="0.22" fill="#2f6fd0" fill-opacity="0.42"/></pattern>'
        '</defs>')


def _wrap(s, n):
    import textwrap
    return textwrap.wrap(s, n) or ['']


def _wrapw(s_, width_mm, size, family=FONT, max_lines=None):
    """Wrap to a width in mm (Figtree ≈0.52·size per char, mono ≈0.62·size)."""
    k = 0.62 if family == MONO else 0.52
    lines = _wrap(s_, max(8, int(width_mm / (size * k))))
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:max(1, len(lines[-1]) - 1)].rstrip() + '…'
    return lines


def s_spot(x, y):
    return (f'<circle cx="{f(x)}" cy="{f(y)}" r="0.95" fill="{C_LIGHT}" stroke="#111" stroke-width="0.25"/>'
            f'<circle cx="{f(x)}" cy="{f(y)}" r="0.3" fill="#111"/>')


def s_track(x0, y0, x1, y1):
    return (f'<line x1="{f(x0)}" y1="{f(y0)}" x2="{f(x1)}" y2="{f(y1)}" stroke="#111" stroke-width="0.6"/>'
            + ''.join(f'<line x1="{f(x)}" y1="{f(y - 0.9)}" x2="{f(x)}" y2="{f(y + 0.9)}" stroke="#111" stroke-width="0.35"/>' for x, y in ((x0, y0), (x1, y1))))


def s_down(x, y):
    return (f'<circle cx="{f(x)}" cy="{f(y)}" r="1.3" fill="#ffffff" stroke="#111" stroke-width="0.32"/>'
            f'<circle cx="{f(x)}" cy="{f(y)}" r="0.62" fill="{C_LIGHT}"/>')


def s_pend(x, y, r=2.4):
    return (f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="#ffe2b3" stroke="#111" stroke-width="0.3"/>'
            f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r * 0.45)}" fill="none" stroke="#111" stroke-width="0.2"/>'
            f'<circle cx="{f(x)}" cy="{f(y)}" r="0.35" fill="#111"/>')


def s_sconce(cx, cy, face, r=1.5):
    if face in ('S', 'N'):
        sweep = 0 if face == 'S' else 1
        d = f'M{f(cx - r)},{f(cy)} A{f(r)},{f(r)} 0 0 {sweep} {f(cx + r)},{f(cy)} Z'
    else:
        sweep = 1 if face == 'E' else 0
        d = f'M{f(cx)},{f(cy - r)} A{f(r)},{f(r)} 0 0 {sweep} {f(cx)},{f(cy + r)} Z'
    return f'<path d="{d}" fill="#ffe2b3" stroke="#111" stroke-width="0.3"/>'


def s_led(x0, y0, x1, y1):
    return (f'<line x1="{f(x0)}" y1="{f(y0)}" x2="{f(x1)}" y2="{f(y1)}" stroke="#e07b00" stroke-width="0.75" '
            f'stroke-dasharray="1.3 0.6" stroke-linecap="butt"/>')


def s_l8(x, y, along, label=True):
    w, h = (L8_LEN * S, L8_W * S) if along == 'x' else (L8_W * S, L8_LEN * S)
    g = [f'<rect x="{f(x - w/2)}" y="{f(y - h/2)}" width="{f(w)}" height="{f(h)}" fill="#ffffff" stroke="#1a55b0" stroke-width="0.32"/>']
    if along == 'x':
        g.append(f'<line x1="{f(x - w/2 + 0.6)}" y1="{f(y)}" x2="{f(x - 3.2)}" y2="{f(y)}" stroke="#1a55b0" stroke-width="0.2"/>'
                 f'<line x1="{f(x + 3.2)}" y1="{f(y)}" x2="{f(x + w/2 - 0.6)}" y2="{f(y)}" stroke="#1a55b0" stroke-width="0.2"/>')
        if label:
            g.append(text(x, y + 0.55, 'L-8', 1.45, weight='800', fill='#1a55b0', family=MONO))
    else:
        g.append(f'<line x1="{f(x)}" y1="{f(y - h/2 + 0.6)}" x2="{f(x)}" y2="{f(y - 3.2)}" stroke="#1a55b0" stroke-width="0.2"/>'
                 f'<line x1="{f(x)}" y1="{f(y + 3.2)}" x2="{f(x)}" y2="{f(y + h/2 - 0.6)}" stroke="#1a55b0" stroke-width="0.2"/>')
        if label:
            g.append(text(x + 0.55, y, 'L-8', 1.45, weight='800', fill='#1a55b0', family=MONO, rot=-90))
    return ''.join(g)


def s_l9(x, y):
    return (f'<circle cx="{f(x)}" cy="{f(y)}" r="0.9" fill="#fff3d6" stroke="{C_GREASE}" stroke-width="0.28"/>'
            f'<path d="M{f(x-0.6)},{f(y-0.6)} L{f(x+0.6)},{f(y+0.6)} M{f(x-0.6)},{f(y+0.6)} L{f(x+0.6)},{f(y-0.6)}" stroke="{C_GREASE}" stroke-width="0.2"/>')


def s_em(x, y):
    return (f'<rect x="{f(x - 2.1)}" y="{f(y - 1.1)}" width="4.2" height="2.2" rx="0.3" fill="#fff3b0" stroke="{C_EM}" stroke-width="0.3"/>'
            f'<circle cx="{f(x - 1.0)}" cy="{f(y)}" r="0.6" fill="{C_EM}"/><circle cx="{f(x + 1.0)}" cy="{f(y)}" r="0.6" fill="{C_EM}"/>')


def s_exit(x, y, d='E'):
    w, h = 7.0, 3.0
    g = [f'<rect x="{f(x - w/2)}" y="{f(y - h/2)}" width="{w}" height="{h}" rx="0.4" fill="{C_EGR}" stroke="#063d1d" stroke-width="0.25"/>',
         text(x - 0.9, y + 0.5, 'SALIDA', 1.3, weight='800', fill='#ffffff')]
    ax, ay = x + w / 2 - 1.1, y
    tri = {'E': [(ax - 0.6, ay - 0.8), (ax + 0.7, ay), (ax - 0.6, ay + 0.8)], 'W': [(ax + 0.6, ay - 0.8), (ax - 0.7, ay), (ax + 0.6, ay + 0.8)],
           'N': [(ax - 0.8, ay + 0.6), (ax, ay - 0.8), (ax + 0.8, ay + 0.6)], 'S': [(ax - 0.8, ay - 0.6), (ax, ay + 0.8), (ax + 0.8, ay - 0.6)]}.get(d)
    if tri:
        g.append(f'<polygon points="{" ".join(f"{f(a)},{f(b)}" for a, b in tri)}" fill="#ffffff"/>')
    return ''.join(g)


def s_det(x, y, k):
    return (f'<circle cx="{f(x)}" cy="{f(y)}" r="1.7" fill="#ffffff" stroke="#1b1b1b" stroke-width="0.35"/>'
            + text(x, y + 0.62, k, 1.7, weight='800', fill='#1b1b1b'))


def s_diff(x, y, size=12.0):
    h = size / 2
    return (f'<rect x="{f(x - h)}" y="{f(y - h)}" width="{f(size)}" height="{f(size)}" fill="#eaf2fd" stroke="{C_MUA}" stroke-width="0.4"/>'
            f'<rect x="{f(x - h * 0.55)}" y="{f(y - h * 0.55)}" width="{f(size * 0.55)}" height="{f(size * 0.55)}" fill="none" stroke="{C_MUA}" stroke-width="0.2"/>'
            f'<path d="M{f(x-h)},{f(y-h)} L{f(x+h)},{f(y+h)} M{f(x-h)},{f(y+h)} L{f(x+h)},{f(y-h)}" stroke="{C_MUA}" stroke-width="0.22"/>')


def s_riser(x, y, w, color, dash=None):
    h = w / 2
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return (f'<rect x="{f(x - h)}" y="{f(y - h)}" width="{f(w)}" height="{f(w)}" fill="#ffffff" stroke="{color}" stroke-width="0.5"{d}/>'
            f'<path d="M{f(x-h)},{f(y-h)} L{f(x+h)},{f(y+h)} M{f(x-h)},{f(y+h)} L{f(x+h)},{f(y-h)}" stroke="{color}" stroke-width="0.3"/>'
            f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(min(h * 0.45, 1.3))}" fill="{color}"/>')


def s_secmark(x, y, letter, sheet, ang):
    """Section bubble with a direction arrow; ang = screen angle (deg) of the viewing direction."""
    a = math.radians(ang)
    tx, ty = x + math.cos(a) * 4.6, y + math.sin(a) * 4.6
    px, py = -math.sin(a), math.cos(a)
    tri = [(tx, ty), (x + math.cos(a) * 2.6 + px * 2.3, y + math.sin(a) * 2.6 + py * 2.3), (x + math.cos(a) * 2.6 - px * 2.3, y + math.sin(a) * 2.6 - py * 2.3)]
    return (f'<polygon points="{" ".join(f"{f(u)},{f(v)}" for u, v in tri)}" fill="#141210"/>'
            f'<circle cx="{f(x)}" cy="{f(y)}" r="3.3" fill="#ffffff" stroke="#141210" stroke-width="0.4"/>'
            f'<line x1="{f(x - 3.3)}" y1="{f(y)}" x2="{f(x + 3.3)}" y2="{f(y)}" stroke="#141210" stroke-width="0.25"/>'
            + text(x, y - 0.6, letter, 2.4, weight='800') + text(x, y + 2.25, sheet, 1.35, weight='700', family=MONO))


class Placer:
    """Tiny collision-aware placer for tags (sheet mm)."""

    def __init__(self, area=(12.5, 13.5, 429.5, 309.0)):
        self.occ = []
        self.area = box(*area)

    def add(self, g, w=1.0):
        if g is not None and not g.is_empty:
            self.occ.append((g, w))

    def addbox(self, x0, y0, x1, y1, w=1.0):
        self.add(box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), w)

    def cost(self, b):
        c = 0.0
        for g, w in self.occ:
            if g.intersects(b):
                ig = g.intersection(b)
                c += w * (ig.area if ig.geom_type in ('Polygon', 'MultiPolygon') else ig.length * 0.8 + 0.5)
        if not self.area.contains(b):
            c += 1000
        return c

    def place(self, cands, w, h, weight=3.0, pref=None, dist_w=0.02):
        best = None
        for i, (cx, cy) in enumerate(cands):
            b = box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            c = self.cost(b) + (math.dist((cx, cy), pref) * dist_w if pref else i * 0.02)
            if best is None or c < best[0]:
                best = (c, cx, cy, b)
        self.add(best[3], weight)
        return best[1], best[2], best[0]


def _sheet_geom(g):
    return shapely.affinity.affine_transform(g, [S, 0, 0, S, sx(0), sy(0)])


# ============================================================================================== sheet
def build_sheet(ex, lay, val, L):
    ceil = L['ceil']
    s = Sheet(ex, lay, val, 'A201')
    s.add(DEFS)
    s.frame_and_titleblock('A-201 · Cielos reflejados e iluminación',
                           'Tipos de cielo · luminarias · emergencia y detección · campanas, ductos y aire de reposición', 'A-201',
                           scale_note='Escala 1:50 en A2 · plano de cielo reflejado · cotas en metros')
    s.grid_axes()
    # ceiling types
    g = ['<g id="ceiling-types">']
    for cr in L['ct_regions']:
        ct = cr['ct']
        g.append(_poly_pattern(cr['geom'], ct['pattern'], ct['stroke']))
    g.append('</g>')
    s.add(''.join(g))
    s.layer_existing()
    s.layer_new()
    s.layer_furniture(faint=True)
    s.layer_equipment(faint=True, labels=False)

    P = Placer()
    for w, gm in standing_existing_walls(ex, lay):
        P.add(_sheet_geom(gm), 0.5)
    for c in ex['columns']:
        P.add(_sheet_geom(R(c['rect'])), 0.8)
    for w in lay.get('new_walls', []):
        P.add(_sheet_geom(R(w['rect'])), 0.8)
    for sh in ex.get('shafts', []):
        P.add(_sheet_geom(R(sh['rect'])), 0.4)

    # ---------------------------------------------------------------- hoods + integrated lights
    g = ['<g id="hoods">']
    for h in L['hoods']:
        x0, y0, x1, y1 = h['rect']
        col = C_SOLID if 'solid' in h['system'] else C_GREASE
        g.append(rect_el(h['rect'], '#fffaf4', col, 0.55, dash='2.2 0.9', extra='fill-opacity="0.92"'))
        g.append(f'<path d="M{f(sx(x0))},{f(sy(y0))} L{f(sx(x1))},{f(sy(y1))} M{f(sx(x0))},{f(sy(y1))} L{f(sx(x1))},{f(sy(y0))}" '
                 f'stroke="{col}" stroke-width="0.14" stroke-dasharray="1 0.8" fill="none" stroke-opacity="0.6"/>')
        P.add(_sheet_geom(R(h['rect'])), 0.6)
    for lt in L['lights']:
        if lt['type'] == 'L-9':
            x, y = sx(lt['at'][0]), sy(lt['at'][1])
            g.append(s_l9(x, y))
            P.addbox(x - 1.1, y - 1.1, x + 1.1, y + 1.1, 3)
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- ducts / risers
    g = ['<g id="ducts">']
    for d in L['ducts']:
        col = d['color']
        pts = d['pts']
        if len(pts) > 1:
            band = LineString(pts).buffer(d['w'] / 2, cap_style=2, join_style=2)
            g.append(_poly_pattern(band, col, col, opacity=0.16, dash='1.4 0.7', sw=0.4))
            P.add(_sheet_geom(band), 2)
        if d.get('riser_rect'):
            rr = d['riser_rect']
            g.append(rect_el(rr, 'none', col, 0.45, dash='0.9 0.6'))
            x, y = sx(_c(rr)[0]), sy(_c(rr)[1])
            g.append(f'<path d="M{f(sx(rr[0]))},{f(sy(rr[1]))} L{f(sx(rr[2]))},{f(sy(rr[3]))} M{f(sx(rr[0]))},{f(sy(rr[3]))} L{f(sx(rr[2]))},{f(sy(rr[1]))}" stroke="{col}" stroke-width="0.25" stroke-dasharray="0.9 0.6"/>')
            P.add(_sheet_geom(R(rr)), 2)
        cx, cy = d['collar']
        rx, ry = d['riser_at']
        if not d.get('riser_rect'):
            g.append(s_riser(sx(rx), sy(ry), d['w'] * S, col))
            P.addbox(sx(rx) - d['w'] * S / 2, sy(ry) - d['w'] * S / 2, sx(rx) + d['w'] * S / 2, sy(ry) + d['w'] * S / 2, 4)
        if len(pts) > 1:
            g.append(f'<circle cx="{f(sx(cx))}" cy="{f(sy(cy))}" r="1.0" fill="{col}"/>')
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- make-up air diffusers
    g = ['<g id="makeup-air">']
    for df in L['diff']:
        x, y = sx(df['at'][0]), sy(df['at'][1])
        g.append(s_diff(x, y, df['size'] * S))
        P.addbox(x - df['size'] * S / 2, y - df['size'] * S / 2, x + df['size'] * S / 2, y + df['size'] * S / 2, 4)
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- luminaires
    g = ['<g id="luminaires">']
    for tr in L['tracks']:
        x0, y0, x1, y1 = sx(tr['p0'][0]), sy(tr['p0'][1]), sx(tr['p1'][0]), sy(tr['p1'][1])
        g.append(s_track(x0, y0, x1, y1))
        P.addbox(x0, y0 - 1.0, x1, y1 + 1.0, 2)
    for lt in L['lights']:
        t = lt['type']
        if t == 'L-1':
            x, y = sx(lt['at'][0]), sy(lt['at'][1])
            g.append(s_spot(x, y))
        elif t == 'L-2':
            x, y = sx(lt['at'][0]), sy(lt['at'][1])
            g.append(s_down(x, y))
            P.addbox(x - 1.4, y - 1.4, x + 1.4, y + 1.4, 4)
        elif t == 'L-3':
            x, y = sx(lt['at'][0]), sy(lt['at'][1])
            r = max(1.6, lt.get('r', 0.12) * S)
            g.append(s_pend(x, y, r))
            P.addbox(x - r, y - r, x + r, y + r, 4)
        elif t == 'L-4':
            x0, y0, x1, y1 = lt['rect']
            face = lt.get('face') or 'S'
            wx = {'S': ((x0 + x1) / 2, y0), 'N': ((x0 + x1) / 2, y1), 'E': (x0, (y0 + y1) / 2), 'W': (x1, (y0 + y1) / 2)}[face]
            x, y = sx(wx[0]), sy(wx[1])
            g.append(s_sconce(x, y, face, 1.7))
            P.addbox(x - 1.8, y - 1.8, x + 1.8, y + 1.8, 4)
        elif t == 'L-5':
            x0, y0, x1, y1 = lt['rect']
            face = lt.get('face') or 'S'
            if face in ('N', 'S'):
                yy = y0 if face == 'N' else y1
                seg = (sx(x0), sy(yy) + (-0.5 if face == 'N' else 0.5), sx(x1), sy(yy) + (-0.5 if face == 'N' else 0.5))
            else:
                xx = x1 if face == 'E' else x0
                seg = (sx(xx) + (0.5 if face == 'E' else -0.5), sy(y0), sx(xx) + (0.5 if face == 'E' else -0.5), sy(y1))
            g.append(s_led(*seg))
            P.addbox(seg[0] - 0.6, seg[1] - 0.6, seg[2] + 0.6, seg[3] + 0.6, 2)
        elif t == 'L-6':
            x0, y0, x1, y1 = lt['rect']
            g.append(rect_el(lt['rect'], '#ffd9b0', '#8f4500', 0.3))
            vert = (y1 - y0) > (x1 - x0)
            cx, cy = sx((x0 + x1) / 2), sy((y0 + y1) / 2)
            lx = sx(x1) + 1.6 if vert else cx
            g.append(text(lx, cy + (0 if vert else -1.2), f"L-6 · {lt.get('text', 'LAVA')}", 1.5, weight='800', fill='#8f4500', family=MONO, rot=-90 if vert else 0))
            P.add(_sheet_geom(R(lt['rect'])), 3)
            P.addbox(lx - 1.1, cy - 8, lx + 1.1, cy + 8, 3)
        elif t == 'L-7':
            g.append(rect_el(lt['rect'], 'none', '#8f4500', 0.3, dash='0.8 0.5'))
        elif t == 'L-8':
            x, y = sx(lt['at'][0]), sy(lt['at'][1])
            g.append(s_l8(x, y, lt['along']))
            w_, h_ = (L8_LEN * S, L8_W * S) if lt['along'] == 'x' else (L8_W * S, L8_LEN * S)
            P.addbox(x - w_ / 2 - 0.3, y - h_ / 2 - 0.3, x + w_ / 2 + 0.3, y + h_ / 2 + 0.3, 8)
    for tr in L['tracks']:
        for p in tr['spots']:
            x, y = sx(p[0]), sy(p[1])
            P.addbox(x - 1.1, y - 1.1, x + 1.1, y + 1.1, 4)
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- life-safety devices (decluttered)
    g = ['<g id="devices">']
    dev = []
    for p in L['em']:
        dev.append(('EM', p, 4.4, 2.4, lambda x, y, p=p: s_em(x, y)))
    for d in L['det']:
        dev.append(('DET', d['at'], 3.6, 3.6, lambda x, y, d=d: s_det(x, y, d['kind'])))
    for e in L['exits']:
        dev.append(('RS', tuple(e['at']), 7.2, 3.2, lambda x, y, e=e: s_exit(x, y, e.get('dir', 'E'))))
    placed = []
    offs = [(0, 0), (0, -3.6), (0, 3.6), (3.8, 0), (-3.8, 0), (0, -5.2), (0, 5.2), (4.6, -3.2), (-4.6, -3.2), (4.6, 3.2), (-4.6, 3.2)]
    for kind, p, w, h, fn in dev:
        x, y = sx(p[0]), sy(p[1])
        best = None
        for dx, dy in offs:
            b = box(x + dx - w / 2, y + dy - h / 2, x + dx + w / 2, y + dy + h / 2)
            c = sum(b.intersection(q).area for q in placed) * 10 + P.cost(b) * 0.3 + math.hypot(dx, dy) * 0.05
            if best is None or c < best[0]:
                best = (c, dx, dy, b)
        _, dx, dy, b = best
        placed.append(b)
        P.add(b, 5)
        if dx or dy:
            g.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x + dx)}" y2="{f(y + dy)}" stroke="#555" stroke-width="0.2"/>'
                     f'<circle cx="{f(x)}" cy="{f(y)}" r="0.45" fill="#555"/>')
        g.append(fn(x + dx, y + dy))
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- callouts (top band) + section marks, registered first
    for b in callouts(s, L, lay):
        P.add(b, 8)
    section_marks(s, L, ex, P)

    # ---------------------------------------------------------------- tags: hoods, ducts, diffusers, lights
    g = ['<g id="tags">']

    def tag(lines, anchor_xy, cands, color, size=1.65, weights=None, bg=True, leader=True, dist_w=0.03):
        w = max(tw(s_, size) for s_ in lines) + 1.6
        h = len(lines) * size * 1.22 + 0.9
        best_ = None
        for cx_, cy_ in cands:
            b_ = box(cx_ - w / 2, cy_ - h / 2, cx_ + w / 2, cy_ + h / 2)
            c_ = P.cost(b_) + (math.dist((cx_, cy_), anchor_xy) * dist_w if anchor_xy else 0)
            if leader and anchor_xy and math.dist((cx_, cy_), anchor_xy) > max(w, h) / 2 + 0.6:
                lx_ = min(max(anchor_xy[0], cx_ - w / 2), cx_ + w / 2)
                ly_ = min(max(anchor_xy[1], cy_ - h / 2), cy_ + h / 2)
                ld = LineString([(lx_, ly_), anchor_xy])
                c_ += sum(150 for q in placed if q.intersects(ld) and not q.contains(Point(anchor_xy)))
            if best_ is None or c_ < best_[0]:
                best_ = (c_, cx_, cy_, b_)
        cx, cy = best_[1], best_[2]
        P.add(best_[3], 6)
        out = []
        if leader and anchor_xy and math.dist((cx, cy), anchor_xy) > max(w, h) / 2 + 0.6:
            bx = min(max(anchor_xy[0], cx - w / 2), cx + w / 2)
            by = min(max(anchor_xy[1], cy - h / 2), cy + h / 2)
            out.append(f'<line x1="{f(bx)}" y1="{f(by)}" x2="{f(anchor_xy[0])}" y2="{f(anchor_xy[1])}" stroke="{color}" stroke-width="0.22"/>'
                       f'<circle cx="{f(anchor_xy[0])}" cy="{f(anchor_xy[1])}" r="0.45" fill="{color}"/>')
        if bg:
            out.append(f'<rect x="{f(cx - w/2)}" y="{f(cy - h/2)}" width="{f(w)}" height="{f(h)}" rx="0.6" fill="#ffffff" fill-opacity="0.93" stroke="{color}" stroke-width="0.25"/>')
        out.append(mtext(cx, cy, lines, size, weight='700', fill=color, lh=1.22, weights=weights or (['800'] + ['600'] * (len(lines) - 1))))
        g.append(''.join(out))
        return cx, cy

    def ring(x, y, r_list=(5, 8, 11, 14, 18, 23), n=16):
        out = [(x, y)]
        for r in r_list:
            for k in range(n):
                a = 2 * math.pi * k / n
                out.append((x + r * math.cos(a), y + r * math.sin(a) * 0.8))
        return out

    hl = L['hood_low']
    for h in L['hoods']:
        x0, y0, x1, y1 = h['rect']
        col = C_SOLID if 'solid' in h['system'] else C_GREASE
        solid = 'solid' in h['system']
        lines = [f"{h['id']} · {'COMBUSTIBLE SÓLIDO' if solid else 'LÍNEA A GAS'}", f"borde inf. +{hl:.2f} TBV",
                 'arrestachispas · sistema propio' if solid else 'UL 300 + corte de gas']
        size = 1.55
        tl = max(tw(q, size) for q in lines) + 1.6          # along the hood (rotated text)
        tt = len(lines) * size * 1.22 + 0.8
        vert = (y1 - y0) >= (x1 - x0)
        hx0, hy0, hx1, hy1 = sx(x0), sy(y0), sx(x1), sy(y1)
        cands = []
        for fx in np.linspace(0.2, 0.8, 13):
            for fy in np.linspace(0.2, 0.8, 13):
                cands.append((hx0 + fx * (hx1 - hx0), hy0 + fy * (hy1 - hy0)))
        # candidates are tested with the rotated box size
        bw, bh = (tt, tl) if vert else (tl, tt)
        hood_box = _sheet_geom(R(h['rect']))
        P.occ = [(gg, ww) for gg, ww in P.occ if not gg.equals(hood_box)]
        cx, cy, _ = P.place(cands, bw, bh, 3, pref=((hx0 + hx1) / 2, (hy0 + hy1) / 2), dist_w=0.02)
        P.add(hood_box, 0.6)
        g.append(f'<rect x="{f(cx - bw/2)}" y="{f(cy - bh/2)}" width="{f(bw)}" height="{f(bh)}" rx="0.6" fill="#ffffff" fill-opacity="0.95" stroke="{col}" stroke-width="0.25"/>')
        g.append(mtext(cx, cy, lines, size, weight='700', fill=col, lh=1.22, rot=-90 if vert else 0, weights=['800', '600', '600']))
    for d in L['ducts']:
        rx, ry = d['riser_at']
        x, y = sx(rx), sy(ry)
        if d.get('existing_riser'):
            lines = [f"{d['id']} ↑ a riser existente", 'solo si la inspección lo aprueba', 'VERIFY ON SITE']
        elif 'chimenea' in d['kind']:
            lines = [f"{d['id']} ↑ chimenea smoker", 'propia · listada NFPA 211 · TBV']
        else:
            lines = [f"{d['id']} ↑ ducto propio a cubierta", 'cerramiento RF 1 h · TBV']
        tag(lines, (x, y), ring(x, y), d['color'], size=1.55)
    for df in L['diff']:          # compact tag per diffuser (flow / route: EXTRACTION callout + legend)
        x, y = sx(df['at'][0]), sy(df['at'][1])
        hs = df['size'] * S / 2
        tag([f"{L['mua'].get('id', 'AR-1')} · TBE"], (x, y), [(x, y - hs - 2.2), (x, y + hs + 2.2), (x - hs - 7.5, y), (x + hs + 7.5, y)]
            + ring(x, y, (10, 13), 16), C_MUA, size=1.5, leader=False)
    # luminaire type tags (one per group)
    groups = {}
    for lt in L['lights']:
        if lt['type'] in ('L-2', 'L-3', 'L-4'):
            groups.setdefault(lt['type'], []).append(lt)
    labels = {'L-2': 'L-2', 'L-3': 'L-3 colgante h {h}', 'L-4': 'L-4 aplique h {h}'}
    for t, items in groups.items():
        for i, lt in enumerate(items):
            if t == 'L-2' and i % 3:
                continue
            if t == 'L-3' and i:
                continue
            x, y = sx(lt['at'][0]), sy(lt['at'][1])
            s_ = labels[t].format(h=f"{float(lt.get('h') or 0):.2f}")
            tag([s_], (x, y), ring(x, y, (3.5, 5, 7), 12), '#2a2a2a', size=1.5, bg=True, leader=False)
    for tr in L['tracks']:
        x, y = sx(tr['p0'][0]), sy(tr['p0'][1])
        tag(['L-1 riel + proyectores'], (x, y), [(x - 12, y), (x - 12, y - 3), (x - 12, y + 3), (x + 12, y - 3.5), (x + 12, y + 3.5)], '#2a2a2a', size=1.5, leader=False)
    # ceiling tags per zone (keep the light axes readable)
    if L['aisle']:
        P.addbox(sx(L['aisle']['x0'] - 0.6), sy(L['aisle']['y']) - 1.6, sx(L['aisle']['x1'] + 0.6), sy(L['aisle']['y']) + 1.6, 2)
    for tr in L['tracks']:
        P.addbox(sx(tr['p0'][0]), sy(tr['p0'][1]) - 1.8, sx(tr['p1'][0]), sy(tr['p1'][1]) + 1.8, 2)
    zones = {z['id']: z for z in lay.get('zones', [])}
    ctz = {z: cr['ct'] for cr in L['ct_regions'] for z in cr['ct']['zones']}
    for zid, zp in L['zpoly'].items():
        if zp.is_empty or zid not in ctz:
            continue
        ct = ctz[zid]
        z = zones.get(zid, {})
        inner = zp.buffer(-0.35)
        if inner.is_empty:
            inner = zp
        x0, y0, x1, y1 = inner.bounds
        cands = [(sx(xx), sy(yy)) for xx in np.arange(x0, x1 + 0.01, 0.2) for yy in np.arange(y0, y1 + 0.01, 0.2) if inner.contains(Point(xx, yy))]
        pref = z.get('label_at') or (zp.representative_point().x, zp.representative_point().y)
        size = 1.75
        head = [f"{ct['id']} · {z.get('short', zid)}"]
        lvl = f"+{ceil:.2f}* VERIFY ON SITE"
        w_lvl = len(lvl) * 1.5 * 0.62
        if tw(head[0], size) > w_lvl + 1.0 and ' / ' in head[0]:      # long zone names: two lines, narrower tag
            a_, b_ = head[0].split(' / ', 1)
            head = [a_ + ' /', b_]
        w = max(max(tw(q, size) for q in head), w_lvl) + 2.6
        hh = (len(head) + 1) * size * 1.25 + 1.2
        cx, cy, _ = P.place(cands, w, hh, 4, pref=(sx(pref[0]), sy(pref[1])), dist_w=0.01)
        y_top = cy - hh / 2 + 0.6 + size
        g.append(f'<rect x="{f(cx - w/2)}" y="{f(cy - hh/2)}" width="{f(w)}" height="{f(hh)}" rx="1.0" fill="#ffffff" stroke="{ct["stroke"]}" stroke-width="0.45"/>'
                 + ''.join(text(cx, y_top + i * size * 1.25, q, size, weight='800', fill=ct['stroke'] if ct['id'] != 'CT-1' else '#1b1b1b')
                           for i, q in enumerate(head))
                 + text(cx, y_top + len(head) * size * 1.25 + 0.1, lvl, 1.5, weight='700', fill=C_RED, family=MONO))
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- dimensions of the light rows (dining)
    if L['tracks'] and L['aisle']:
        prem = premises(ex)
        xe = prem.bounds[2]
        ys = sorted({round(tr['p0'][1], 3) for tr in L['tracks']} | {round(L['aisle']['y'], 3)})
        wall_n = min(y for x, y in ex['premises_polygon'] if x > xe - 1.0)
        wall_s = max(y for x, y in ex['premises_polygon'] if x > xe - 1.0)
        chain = [wall_n] + ys + [wall_s]
        for a, b in zip(chain, chain[1:]):
            s.dim((xe, a), (xe, b), 0.75)
        s.add(text(sx(xe + 1.05), sy(chain[1]) + 0.6, 'eje L-1', 1.5, anchor='start', weight='700', fill='#2a2a2a'))
        s.add(text(sx(xe + 1.05), sy(L['aisle']['y']) + 0.6, 'eje L-2 / EM', 1.5, anchor='start', weight='700', fill='#2a2a2a'))
        s.add(text(sx(xe + 1.05), sy(chain[-2]) + 0.6, 'eje L-1', 1.5, anchor='start', weight='700', fill='#2a2a2a'))

    # ---------------------------------------------------------------- tables inside the plan (free area east of the stair)
    ceiling_tables(s, L, 222.5, 177.0, 142.0)
    luminaire_schedule(s, L, lay, 12.0, 322.0)
    coordination_table(s, L, lay, 292.0, 322.0, 138.0)

    # ---------------------------------------------------------------- side panel
    def sw_sym(fn):
        return lambda x, y: fn(x + 5, y + 1.7)

    def sw_ct(pat, stroke):
        return lambda x, y: f'<rect x="{x}" y="{y}" width="10" height="3.4" fill="{pat}" stroke="{stroke}" stroke-width="0.35"/>'

    legend = [
        (sw_ct('url(#ct1)', '#2a2522'), 'CT-1 estructura expuesta negro mate'),
        (sw_ct('url(#ct2)', '#c2410c'), 'CT-2 liso lavable incombustible'),
        (sw_ct('url(#ct3)', '#2f6fd0'), 'CT-3 liso lavable resistente a humedad'),
        (lambda x, y: rect_el_mm(x, y, 10, 3.4, '#fffaf4', C_GREASE, dash='2.2 0.9') + s_l9(x + 5, y + 1.7), 'Campana HD-1 / HD-2 + L-9 integrada'),
        (lambda x, y: s_riser(x + 5, y + 1.7, 3.4, C_SOLID), 'Ducto / chimenea vertical a cubierta'),
        (lambda x, y: s_diff(x + 5, y + 1.7, 3.4), 'Difusor de aire de reposición AR-1'),
        (lambda x, y: s_track(x + 0.5, y + 1.7, x + 9.5, y + 1.7) + s_spot(x + 3, y + 1.7) + s_spot(x + 7, y + 1.7), 'L-1 riel + proyectores sobre mesas'),
        (sw_sym(s_down), 'L-2 downlight de superficie'),
        (lambda x, y: s_pend(x + 3, y + 1.7, 1.6) + s_sconce(x + 8, y + 0.2, 'S', 1.5), 'L-3 colgante · L-4 aplique (decor)'),
        (lambda x, y: s_led(x + 0.5, y + 1.7, x + 9.5, y + 1.7), 'L-5 tira LED · L-6 rótulo · L-7 pase'),
        (lambda x, y: s_l8(x + 5, y + 1.7, 'x', label=False)[:0] + rect_el_mm(x + 0.5, y + 1.0, 9, 1.4, '#ffffff', '#1a55b0'), 'L-8 hermética IP65 1.20 m (cocina)'),
        (sw_sym(s_em), 'EM luz de emergencia (A-104)'),
        (lambda x, y: s_exit(x + 5, y + 1.7, 'E'), 'RS rótulo SALIDA iluminado'),
        (lambda x, y: s_det(x + 2.5, y + 1.7, 'H') + s_det(x + 7.5, y + 1.7, 'T'), 'Detector humo (H) / térmico (T)'),
        (lambda x, y: s_secmark(x + 5, y + 1.7, '', '', -90)[:0] + _mini_sec(x, y), 'Corte → lámina A-301'),
    ]
    notes = [
        '!ANTEPROYECTO: niveles, luminarias y rutas a validar por el',
        '!profesional responsable (CFIA) e ingenierías.',
        'Cielo reflejado: misma orientación que A-101 (vista como espejo).',
        f'Nivel de cielo / fondo de estructura +{ceil:.2f} SUPUESTO: VERIFY ON SITE.',
        'Altura libre mínima 2.40 m (INVU 2018 — artículo por confirmar).',
        'CT-2: cielo incombustible; campanas y ductos a 0 mm solo de',
        'materiales incombustibles (NFPA 96 §4.2 — verificar edición).',
        'Zonas de alimentos: luminarias con difusor inastillable y',
        'superficies lavables (Salud DE 37308-S — artículo a confirmar).',
        f'Campanas: borde inferior +{L["hood_low"]:.2f} (= panel NW-2); filtros de',
        f'HD-2 ≥{filter_min(lay):.2f} m sobre la superficie de cocción (NFPA 96',
        'cap. 14, TBV; tabla general 1.07 m carbón) — ver A-301.',
        '!TBV = DIMENSION TO VERIFY · * = nivel supuesto (VERIFY ON SITE).',
        '!EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED',
        '!SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED',
        'Emergencia, rótulos y detectores: los mismos de A-104.',
        'Rociadores del edificio: VERIFY ON SITE; no dibujados.',
        'Circuitos, tablero TE-1, cargas y control (dimmer / escenas):',
        'TO BE ENGINEERED por el ingeniero electricista (NEC 2020).',
    ]
    from collections import Counter
    cnt = Counter(l['type'] for l in L['lights'])
    rows = [('Nivel de cielo / estructura (supuesto)', f"+{ceil:.2f} VERIFY"),
            ('Borde inferior de campanas (TBV)', f"+{L['hood_low']:.2f}"),
            ('L-1 proyectores / rieles', f"{cnt.get('L-1', 0)} / {len(L['tracks'])}"),
            ('L-2 downlights · L-3 colgantes · L-4 apliques', f"{cnt.get('L-2', 0)} · {cnt.get('L-3', 0)} · {cnt.get('L-4', 0)}"),
            ('L-8 herméticas IP65 (dibujadas / requeridas)', f"{cnt.get('L-8', 0)} / {sum(c['need'] for c in L['calc'])}"),
            ('Luces de emergencia · rótulos SALIDA', f"{len(L['em'])} · {len(L['exits'])}"),
            ('Detectores humo / térmicos', f"{sum(1 for d in L['det'] if d['kind'] == 'H')} / {sum(1 for d in L['det'] if d['kind'] == 'T')}"),
            ('Campanas · ductos/chimeneas · difusores AR', f"{len(L['hoods'])} · {len(L['ducts'])} · {len(L['diff'])}")]
    verify = ['Altura real a losa / vigas y espesor de losa (cortes A-301).',
              'Penetraciones de losa y rutas hasta cubierta de EXT-1/2/3 (condominio',
              'y revisión estructural); estado del riser existente de Marna’s.',
              'Red de rociadores y alarma del edificio (tipo, cabezas, integración).',
              'Acometida eléctrica y ubicación final del tablero TE-1.']
    y_end = s.side_panel([('h', 'Leyenda de cielo'), ('legend', legend), ('h', 'Cifras (contadas en la lámina)'), ('rows', rows),
                          ('h', 'Notas'), ('para', notes), ('h', 'VERIFY ON SITE'), ('para', verify)])
    return s.render(), y_end


def section_marks(s, L, ex, P):
    cuts = L['cuts']
    prem = premises(ex)
    bx0, by0, bx1, by1 = prem.bounds
    g = ['<g id="section-marks">']
    dd = 'stroke="#141210" stroke-width="0.45" stroke-dasharray="3 0.8 0.6 0.8"'
    ca = cuts['A']['at']
    for xm in (bx0 - 1.15, bx1 + 1.2):
        g.append(s_secmark(sx(xm), sy(ca), 'A', 'A-301', -90))
        P.addbox(sx(xm) - 4, sy(ca) - 5.5, sx(xm) + 4, sy(ca) + 4, 6)
    g.append(f'<line x1="{f(sx(bx0 - 0.8))}" y1="{f(sy(ca))}" x2="{f(sx(bx0 - 0.1))}" y2="{f(sy(ca))}" {dd}/>')
    g.append(f'<line x1="{f(sx(bx1 + 0.1))}" y1="{f(sy(ca))}" x2="{f(sx(bx1 + 0.85))}" y2="{f(sy(ca))}" {dd}/>')
    cb = cuts['B']['at']
    top = min(y for x, y in ex['premises_polygon']) - 0.116 - 0.62
    for ym in (top, by1 + 0.55):
        g.append(s_secmark(sx(cb), sy(ym), 'B', 'A-301', 0))
        P.addbox(sx(cb) - 4, sy(ym) - 4, sx(cb) + 5.5, sy(ym) + 4, 6)
    g.append(f'<line x1="{f(sx(cb))}" y1="{f(sy(top) + 3.3)}" x2="{f(sx(cb))}" y2="{f(sy(0.0))}" {dd}/>')
    g.append(f'<line x1="{f(sx(cb))}" y1="{f(sy(by1 + 0.13))}" x2="{f(sx(cb))}" y2="{f(sy(by1 + 0.55) - 3.3)}" {dd}/>')
    g.append('</g>')
    s.add(''.join(g))


def rect_el_mm(x, y, w, h, fill, stroke, dash=None, sw=0.35):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>'


def _mini_sec(x, y):
    return (f'<line x1="{f(x)}" y1="{f(y + 1.7)}" x2="{f(x + 6)}" y2="{f(y + 1.7)}" stroke="#141210" stroke-width="0.45" stroke-dasharray="2 0.6 0.5 0.6"/>'
            f'<circle cx="{f(x + 8)}" cy="{f(y + 1.7)}" r="1.8" fill="#fff" stroke="#141210" stroke-width="0.35"/>'
            f'<polygon points="{f(x + 6.8)},{f(y - 0.2)} {f(x + 9.2)},{f(y - 0.2)} {f(x + 8)},{f(y - 1.6)}" fill="#141210"/>')


def _poly_pattern(geom, fill, stroke, opacity=1.0, dash='1.4 1', sw=0.35):
    out = []
    for gg in (getattr(geom, 'geoms', None) or [geom]):
        if gg.is_empty or gg.geom_type != 'Polygon':
            continue
        d = 'M' + ' L'.join(f'{f(sx(x))},{f(sy(y))}' for x, y in gg.exterior.coords) + ' Z'
        for ring_ in gg.interiors:
            d += ' M' + ' L'.join(f'{f(sx(x))},{f(sy(y))}' for x, y in ring_.coords) + ' Z'
        out.append(f'<path d="{d}" fill="{fill}" fill-opacity="{opacity}" fill-rule="evenodd" stroke="{stroke}" stroke-opacity="0.6" '
                   f'stroke-width="{sw}" stroke-dasharray="{dash}"/>')
    return ''.join(out)


def callouts(s, L, lay):
    """Two flag boxes above the plan (the verbatim English flags stay in English). Returns their boxes (sheet mm)."""
    hoods = L['hoods']
    g = ['<g id="callouts">']
    boxes = []
    y = 21.5
    # box 1 (left, above the BBQ wall): smoker flue
    sm = next((d for d in L['ducts'] if 'chimenea' in d['kind']), None)
    if sm:
        x, w = 52.0, 146.0
        lines = ['SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED']
        lines += _wrap(f"{sm['id']} ({sm['serves']}): {sm['riser_note']}", 104)[:2]
        lines += _wrap(sm.get('note', ''), 104)[:1]
        h = len(lines) * 2.45 + 2.2
        g.append(f'<rect x="{x}" y="{y}" width="{w}" height="{f(h)}" rx="0.8" fill="#ffffff" stroke="{C_FLUE}" stroke-width="0.45"/>')
        for i, ln in enumerate(lines):
            g.append(text(x + 1.5, y + 3.3 + i * 2.45, ln, 1.62 if i else 1.8, anchor='start', weight='800' if i == 0 else '400',
                          fill=C_FLUE if i == 0 else '#262626'))
        rx, ry = sx(sm['riser_at'][0]), sy(sm['riser_at'][1])
        bx = min(max(rx, x + 3), x + w - 3)
        g.append(f'<polyline points="{f(bx)},{f(y + h)} {f(rx)},{f(ry - sm["w"] * S / 2)}" fill="none" stroke="{C_FLUE}" stroke-width="0.3"/>')
        boxes.append(box(x, y, x + w, y + h))
        boxes.append(LineString([(bx, y + h), (rx, ry)]).buffer(0.8))
    # box 2 (right of axis B): extraction
    x, w = 208.0, 158.0
    lines = ['EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED']
    for hd in hoods:
        dd = next((d for d in L['ducts'] if d.get('serves') == hd['id']), None)
        txt = (f"{hd['id']} {'(combustible sólido)' if 'solid' in hd['system'] else '(gas)'}: {hd['rect'][2]-hd['rect'][0]:.2f}×{hd['rect'][3]-hd['rect'][1]:.2f} m, "
               f"+{hd['z0']:.2f}→+{hd['z1']:.2f} · " + (f"{dd['id']}: {dd['riser_note']}" if dd else 'ducto TBE'))
        lines += _wrapw(txt, w - 3.5, 1.62, max_lines=2)
    if L['diff']:
        lines += _wrapw(f"{L['mua'].get('id', 'AR-1')}: {len(L['diff'])} difusores en cielo CT-2 frente a la línea · " + L['mua'].get('note', ''),
                        w - 3.5, 1.62, max_lines=2)
    h = len(lines) * 2.45 + 2.2
    g.append(f'<rect x="{x}" y="{y}" width="{w}" height="{f(h)}" rx="0.8" fill="#ffffff" stroke="{C_GREASE}" stroke-width="0.45"/>')
    for i, ln in enumerate(lines):
        g.append(text(x + 1.5, y + 3.3 + i * 2.45, ln, 1.62 if i else 1.8, anchor='start', weight='800' if i == 0 else '400',
                      fill=C_GREASE if i == 0 else '#262626'))
    if hoods:
        hd = min(hoods, key=lambda q: q['rect'][1])
        cx, cy = sx(hd['rect'][2]) - 1.5, sy(hd['rect'][1]) + 1.5
        g.append(f'<line x1="{f(x + 4)}" y1="{f(y + h)}" x2="{f(cx)}" y2="{f(cy)}" stroke="{C_GREASE}" stroke-width="0.28"/>'
                 f'<circle cx="{f(cx)}" cy="{f(cy)}" r="0.55" fill="{C_GREASE}"/>')
        boxes.append(LineString([(x + 4, y + h), (cx, cy)]).buffer(0.8))
    boxes.append(box(x, y, x + w, y + h))
    g.append('</g>')
    s.add(''.join(g))
    return boxes


def _short(s_, n):
    s_ = (s_ or '').replace('\n', ' ')
    return s_ if len(s_) <= n else s_[:n - 1].rsplit(' ', 1)[0] + '…'


def ceiling_tables(s, L, x, y, w, y_max=303.0):
    g = []
    xx, yy = x + 3, y + 5.5
    tw_ = w - 6
    g.append(text(xx, yy, 'TIPOS DE CIELO (CT)', 2.5, anchor='start', weight='800', extra='letter-spacing="0.35"'))
    yy += 4.8
    for ct in L['cts']:
        g.append(f'<rect x="{f(xx)}" y="{f(yy - 2.4)}" width="9" height="3.2" fill="{ct["pattern"]}" stroke="{ct["stroke"]}" stroke-width="0.35"/>')
        g.append(text(xx + 11, yy, f"{ct['id']} · {ct['name']}", 1.85, anchor='start', weight='800', fill=ct['stroke'] if ct['id'] != 'CT-1' else '#1b1b1b'))
        yy += 2.8
        g.append(text(xx + 11, yy, f"Zonas {', '.join(ct['zones'])} · nivel {ct['level']} · VERIFY ON SITE", 1.55, anchor='start', weight='700', fill=C_RED, family=MONO))
        yy += 2.6
        for ln in _wrapw(ct['finish'], tw_ - 11, 1.6):
            g.append(text(xx + 11, yy, ln, 1.6, anchor='start', fill='#2a2a2a'))
            yy += 2.45
        yy += 1.7
    yy += 1.8
    g.append(text(xx, yy, 'ILUMINACIÓN DE COCINA · MÉTODO DE LÚMENES (estimación)', 2.3, anchor='start', weight='800', extra='letter-spacing="0.3"'))
    yy += 3.3
    g.append(text(xx, yy, f"N = E·A / (Φ·UF·MF) · Φ = {LM_L8} lm (L-8) · UF {UF:.2f} · MF {MF:.2f} · A = área útil fuera de campanas", 1.55, anchor='start', fill='#444', family=MONO))
    yy += 1.6
    cols = [(0, 'Zona', 'start'), (50, 'Área m²', 'end'), (68, 'Útil m²', 'end'), (86, 'E obj. lx', 'end'), (102, 'N req.', 'end'), (117, 'N dib.', 'end'), (tw_, 'E est. lx', 'end')]
    for dx, hd, anc in cols:
        g.append(text(xx + dx, yy + 2.4, hd, 1.6, anchor=anc, weight='700', fill='#555'))
    yy += 3.4
    g.append(f'<line x1="{f(xx)}" y1="{f(yy)}" x2="{f(xx + tw_)}" y2="{f(yy)}" stroke="#141210" stroke-width="0.3"/>')
    for c in L['calc']:
        ok = c['drawn'] >= c['need']
        vals = [f"{c['zone']} · {_zone_short(L, c['zone'])}", f"{c['area']:.1f}", f"{c['area_eff']:.1f}", f"{c['lux']}", f"{c['need']}", f"{c['drawn']}", f"≈{c['lux_est']}"]
        for (dx, _, anc), v in zip(cols, vals):
            g.append(text(xx + dx, yy + 2.75, v, 1.65, anchor=anc, family=FONT if dx == 0 else MONO, weight='700' if dx in (0, 117) else '400',
                          fill=('#0a7d3b' if ok else C_RED) if dx == 117 else '#1f1f1f'))
        yy += 3.5
        g.append(f'<line x1="{f(xx)}" y1="{f(yy)}" x2="{f(xx + tw_)}" y2="{f(yy)}" stroke="#e1ddd6" stroke-width="0.2"/>')
    yy += 3.0
    for ln in ['E objetivo 500 lx en preparación / cocción / lavado: referencia EN 12464-1; Salud no fija lux (no confirmado).',
               'Salón: luz de ambiente regulable (≈100–200 lx, referencia) con escenas; acento sobre cada mesa con L-1.',
               'Cálculo definitivo (fotometría, UGR, uniformidad) y circuitos: ingeniero electricista — a validar.']:
        for q in _wrapw(ln, tw_, 1.55):
            g.append(text(xx, yy, q, 1.55, anchor='start', fill='#2a2a2a'))
            yy += 2.35
    h = min(yy - y + 1.5, y_max - y)
    s.add('<g id="ceiling-tables">' + f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" fill="#ffffff" stroke="#141210" stroke-width="0.35"/>'
          + ''.join(g) + '</g>')
    return y + h


def _zone_short(L, zid):
    return {'B': 'cocina caliente', 'E': 'BBQ', 'W': 'lavado', 'A': 'cold prep', 'C': 'barra', 'D': 'salón'}.get(zid, zid)


def luminaire_schedule(s, L, lay, x, y):
    from collections import Counter, defaultdict
    cnt = Counter(l['type'] for l in L['lights'])
    led_len = sum(l.get('len', 0) for l in L['lights'] if l['type'] == 'L-5')
    heights = defaultdict(set)
    for l in L['lights']:
        if l.get('h') is not None:
            heights[l['type']].add(f"{float(l['h']):.2f}")
    zones_l8 = sorted({l.get('zone') for l in L['lights'] if l['type'] == 'L-8'})
    track_len = sum(math.dist(t['p0'], t['p1']) for t in L['tracks'])
    where = {
        'L-1': f"Salón · {len(L['tracks'])} rieles ≈{track_len:.1f} m sobre filas de mesas",
        'L-2': 'Pasillo del salón (eje EM) · pasillo de barra · frente a P-1 · recepción',
        'L-3': 'Sobre barra / caja / pase (decor)',
        'L-4': 'Muro norte del salón (decor)',
        'L-5': f"Listones muro sur + relieve de leños (≈{led_len:.1f} m)",
        'L-6': 'Faja sobre el vidrio NW-1, cara salón (decor)',
        'L-7': 'Repisa del pase C2 (equipo)',
        'L-8': 'Zonas ' + ' · '.join(f"{z} {_zone_short(L, z)}" for z in zones_l8),
        'L-9': ' · '.join(h['id'] for h in L['hoods']) + ' (según fabricante)',
        'EM': 'Ruta de egreso completa (ver A-104)',
        'RS': ' · '.join(e['id'] for e in L['exits']),
    }
    qty = dict(cnt)
    qty['EM'] = len(L['em'])
    qty['RS'] = len(L['exits'])
    order = ['L-1', 'L-2', 'L-3', 'L-4', 'L-5', 'L-6', 'L-7', 'L-8', 'L-9', 'EM', 'RS']
    rows = [t for t in order if qty.get(t)]
    g = ['<g id="luminaire-schedule">']
    g.append(text(x, y + 3, 'CUADRO DE LUMINARIAS', 2.6, anchor='start', weight='800', extra='letter-spacing="0.35"'))
    g.append(text(x + 62, y + 3, 'especificaciones de referencia (no son marcas) · cantidades contadas en esta lámina · a validar por el ingeniero electricista',
                  1.7, anchor='start', fill=C_RED))
    y += 6.2
    W = 272.0
    cols = [(0, 'Tipo', 'start', 17), (17, 'Descripción', 'start', 60), (79, 'Especificación (referencia)', 'start', 56), (137, 'Montaje / altura', 'start', 43),
            (182, 'Ubicación', 'start', 78), (W, 'Cant.', 'end', 12)]
    for dx, hd, anc, _ in cols:
        g.append(text(x + dx, y + 2.4, hd, 1.7, anchor=anc, weight='700', fill='#555'))
    y += 3.5
    g.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x + W)}" y2="{f(y)}" stroke="#141210" stroke-width="0.3"/>')
    sym = {'L-1': lambda a, b: s_track(a - 3.5, b, a + 3.5, b) + s_spot(a, b), 'L-2': s_down, 'L-3': lambda a, b: s_pend(a, b, 1.5),
           'L-4': lambda a, b: s_sconce(a, b - 0.7, 'S', 1.5), 'L-5': lambda a, b: s_led(a - 3.5, b, a + 3.5, b),
           'L-6': lambda a, b: rect_el_mm(a - 3.5, b - 0.9, 7, 1.8, '#ffd9b0', '#8f4500'), 'L-7': lambda a, b: rect_el_mm(a - 3, b - 1.2, 6, 2.4, 'none', '#8f4500', dash='0.8 0.5', sw=0.3),
           'L-8': lambda a, b: rect_el_mm(a - 4, b - 0.7, 8, 1.4, '#ffffff', '#1a55b0'), 'L-9': s_l9, 'EM': s_em, 'RS': lambda a, b: s_exit(a, b, 'E')}
    size = 1.62
    for t in rows:
        lt = LUM_TYPES[t]
        hs = '/'.join(sorted(heights.get(t, []))) or ''
        mount = lt['mount'].format(h=hs)
        if t in ('L-1', 'L-2', 'L-8'):
            mount += f" +{L['ceil']:.2f}*"
        q = qty.get(t, 0)
        qs = f"{q}" if t != 'L-5' else f"{q} tramos"
        vals = [lt['name'], lt['spec'], mount, where.get(t, ''), qs]
        cells = [_wrapw(v, wd - 2, size, max_lines=2) if dx != W else [v] for (dx, _, _, wd), v in zip(cols[1:], vals)]
        n = max(len(c) for c in cells)
        rh = 2.0 + n * 2.2
        g.append(sym[t](x + 10.5, y + rh / 2))
        g.append(text(x, y + rh / 2 + 0.65, t, 1.8, anchor='start', weight='800', family=MONO))
        for (dx, _, anc, _), c in zip(cols[1:], cells):
            y0 = y + rh / 2 - (len(c) - 1) * 1.1 + 0.6
            for i, ln in enumerate(c):
                g.append(text(x + dx, y0 + i * 2.2, ln, size, anchor=anc, weight='700' if dx == W else '400', family=MONO if dx == W else FONT))
        y += rh
        g.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x + W)}" y2="{f(y)}" stroke="#e1ddd6" stroke-width="0.2"/>')
    for i, ln in enumerate([f"* Nivel de cielo supuesto +{L['ceil']:.2f} — VERIFY ON SITE. Salón en 2700 K (cálido, regulable); cocina en 4000 K para inspección de alimentos.",
                            'Rieles L-1 y downlights L-2 adosados a la estructura negra (CT-1) y pintados negro mate; en cocina solo luminarias IP65 lavables.']):
        g.append(text(x, y + 3.1 + i * 2.5, ln, 1.6, anchor='start', fill='#444'))
    g.append('</g>')
    s.add(''.join(g))


def coordination_table(s, L, lay, x, y, w):
    g = ['<g id="coordination">']
    g.append(text(x, y + 3, 'OTROS ELEMENTOS EN CIELO · COORDINACIÓN', 2.6, anchor='start', weight='800', extra='letter-spacing="0.3"'))
    y += 7.0
    rows = []
    for h in L['hoods']:
        rows.append((h['id'], C_SOLID if 'solid' in h['system'] else C_GREASE,
                     f"{'Comb. sólido (NFPA 96 cap. 14) · arrestachispas' if 'solid' in h['system'] else 'Gas · UL 300 / NFPA 17A + solenoide'} · +{h['z0']:.2f}→+{h['z1']:.2f}"))
    for d in L['ducts']:
        rows.append((d['id'], d['color'], f"{d['kind']} → {d['serves']} · {d['riser_note']}"))
    if L['diff']:
        rows.append((L['mua'].get('id', 'AR-1'), C_MUA, f"{len(L['diff'])} difusores · reposición ≈80–90 % del extraído · TO BE ENGINEERED"))
    nh = sum(1 for d in L['det'] if d['kind'] == 'H')
    nt = sum(1 for d in L['det'] if d['kind'] == 'T')
    rows.append(('DET', '#1b1b1b', f"{nh} humo (H) + {nt} térmico (T, cocina caliente) · integrar a la alarma del C.C. (VERIFY)"))
    rows.append(('EM/RS', C_EGR, f"{len(L['em'])} luces de emergencia + {len(L['exits'])} rótulos · ≥1.5 h (NFPA 101 7.9 / 7.10)"))
    rows.append(('ROC.', C_RED, 'Rociadores existentes del edificio: VERIFY ON SITE (no dibujados)'))
    rows.append(('TE-1', '#333', ((lay.get('mep') or {}).get('panel') or {}).get('note', 'Tablero eléctrico: VERIFY ON SITE')))
    for tag_, col, desc in rows:
        ls_ = _wrapw(desc, w - 15, 1.6, max_lines=2)
        g.append(text(x, y, tag_, 1.7, anchor='start', weight='800', fill=col, family=MONO))
        for i, ln in enumerate(ls_):
            g.append(text(x + 14, y + i * 2.2, ln, 1.6, anchor='start', fill='#222'))
        y += 1.7 + len(ls_) * 2.2
        g.append(f'<line x1="{f(x)}" y1="{f(y - 1.9)}" x2="{f(x + w)}" y2="{f(y - 1.9)}" stroke="#e1ddd6" stroke-width="0.2"/>')
        y += 1.2
    g.append('</g>')
    s.add(''.join(g))


def sheets(ex, lay, val):
    L = ceiling_layout(ex, lay, val)
    svg, _ = build_sheet(ex, lay, val, L)
    return [{'id': 'A201', 'file': 'lava_A201_cielos.svg', 'title': 'Cielos reflejados e iluminación', 'order': 201, 'svg': svg}]


if __name__ == '__main__':
    from collections import Counter
    from lavageo import ROOT, load_existing, load_json
    ex = load_existing()
    lay = load_json(os.path.join(ROOT, 'data', 'layout.json'))
    val = load_json(os.path.join(ROOT, 'data', 'validation.json'))
    L = ceiling_layout(ex, lay, val)
    print('hood_low', L['hood_low'], 'cuts', L['cuts'])
    print(Counter(l['type'] for l in L['lights']))
    for c in L['calc']:
        print(c)
