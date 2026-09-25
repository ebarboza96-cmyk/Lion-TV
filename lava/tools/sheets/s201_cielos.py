"""A-201 · Cielos reflejados e iluminación (plano de cielo reflejado, 1:50 en A2).

Plug-in de lámina extra: sheets(ex, lay, val) -> [{id, file, title, order, svg}].

Todo sale de data/existing.json + data/layout.json (+ validation.json):
  * tipos de cielo por zona (CT-1 estructura expuesta negro mate en salón/barra; CT-2 / CT-3 cielos lisos lavables en
    cocina, BBQ, lavado y cold prep), nivel = existing.ceiling.height_assumed (3.00 supuesto, VERIFY ON SITE);
  * luminarias: decor (colgantes, apliques, listones, rótulo, nicho) + propuesta calculada (rieles sobre las filas de
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
from plan_svg import (COL, DISPLAY, FONT, MONO, S, SHEET_W, Sheet, f, mtext, rect_el, sw_line, sw_rect,  # noqa: E402
                      sx, sy, text, tw)

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
    'L-5': {'name': 'Tira LED lineal (listones / nicho / jardinera)', 'spec': '≈10 W/m · 2700 K · perfil con difusor', 'mount': 'Oculta en mobiliario'},
    'L-6': {'name': 'Rótulo LAVA con halo retroiluminado', 'spec': 'LED ámbar · fuente remota', 'mount': 'Faja sobre vidrio · eje h {h}'},
    'L-7': {'name': 'Lámparas de calor del pase C2 (equipo)', 'spec': 'Según proveedor del pase', 'mount': 'Sobre repisa de pase'},
    'L-8': {'name': 'Hermética LED IP65 lineal 1.20 m', 'spec': f'≈{LM_L8} lm · 4000 K · difusor PC inastillable', 'mount': 'Adosada a cielo CT-2 / CT-3'},
    'L-9': {'name': 'Luminaria integrada en campana (listada)', 'spec': 'Suministro del fabricante de HD-1 / HD-2', 'mount': 'Dentro de la campana'},
    'EM': {'name': 'Luz de emergencia autónoma (life_safety)', 'spec': '≥1.5 h · ≥10.8 lx prom. / ≥1.1 lx mín.', 'mount': 'Muro o cielo · h ≈2.40'},
    'RS': {'name': 'Rótulo SALIDA iluminado (life_safety)', 'spec': 'Autónomo ≥1.5 h · direccional', 'mount': 'Sobre puerta / colgante'},
}


# ---------------------------------------------------------------------------------------------- helpers
def _rect(r):
    x0, y0, x1, y1 = r
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _c(r):
    x0, y0, x1, y1 = _rect(r)
    return (x0 + x1) / 2, (y0 + y1) / 2


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
    chairs = {c['table']: c for c in lay.get('chairs', [])}
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


