"""A-104 · Seguridad humana y protección contra incendios (lámina para revisión de Bomberos).

Plug-in de lámina extra: sheets(ex, lay, val) -> [{id, file, title, order, svg}].
También escribe data/life_safety_calcs.json (carga de ocupantes + recorridos de egreso medidos).

Todo se calcula desde data/existing.json + data/layout.json (+ validation.json):
  * carga de ocupantes = área de zona (validation) / factor (layout.life_safety.load_factors), redondeo hacia arriba por zona;
  * recorridos de egreso = caminos más cortos sobre una grilla de 5 cm (obstáculos = lavageo.blocking_obstacles con sillas
    en posición ocupada; radio corporal 0.25 m), suavizados por visibilidad (string pulling) y medidos hasta el plano de la
    puerta de salida;
  * recorridos a extintores (clase K, combustible sólido, clase A / B) con la misma métrica.

Standalone:  python3 tools/sheets/s104_seguridad.py   (solo recalcula y escribe el JSON)
ANTEPROYECTO: valores y citas normativas a validar por el profesional responsable (CFIA) y Bomberos.
"""
import json
import math
import os
import sys

import numpy as np
import shapely
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lavageo import (R, ROOT, blocking_obstacles, front_zone, load_existing, load_json, premises,  # noqa: E402
                     seat_points, standing_existing_walls)
from plan_svg import (DISPLAY, FONT, LEGEND_WALLS, MONO, S, SHEET_W, Sheet, f, mtext, rect_el, sw_rect,  # noqa: E402
                      sx, sy, text, tw)

RES = 0.05            # grid step (m)
BODY = 0.25           # body clearance radius (m)
LIM_COMMON = 22.86    # 75 ft; camino común máx. (mercantil / <50 personas, sin rociadores) — NFPA 101 36.2.5.3 / 12.2.5.1 (verificar edición)
LIM_TRAVEL = 45.72    # 150 ft; distancia de recorrido máx. (mercantil, sin rociadores) — NFPA 101 36.2.6 (verificar edición)
LIM_K = 9.15          # extintor clase K: recorrido ≤ 9.15 m (30 ft) — NFPA 10 6.6 / NFPA 96
LIM_SOLID = 6.0       # 2-A agua o K 6 L a ≤ 6 m (20 ft) de equipos de combustible sólido — NFPA 96 cap. comb. sólido
LIM_A = 22.9          # clase A: recorrido ≤ 22.9 m (75 ft) — NFPA 10 Tabla 6.2.1.1
LIM_B = 9.15          # 10-B a ≤ 9.15 m (30 ft) — NFPA 10 6.3.1
MM_PER_P = 5.0        # capacidad de egreso a nivel / puertas: 5 mm por persona — NFPA 101 Tabla 7.3.3.1
THRESHOLD = 50        # NFPA 101 6.1.2.1: reunión pública con 50 o más personas
HOT_KEYS = ('parrilla', 'cocina_4q', 'plancha', 'freidora_1', 'freidora_2')
GAS_KEYS = ('cocina_4q', 'plancha', 'freidora_1', 'freidora_2')

C_EGR = '#0a7d3b'      # egress green
C_EGR2 = '#b00020'     # critical / fail
C_FIRE = '#c1121f'     # fire devices red
C_GAS = '#b8860b'
C_EM = '#e0a800'


# ============================================================================ geometry / computation
def _ceil(v):
    return int(math.ceil(v - 1e-9))


def occupant_load(lay, val):
    ls = lay.get('life_safety', {})
    zarea = {z['id']: z['area_m2'] for z in ((val or {}).get('metrics', {}).get('zones') or [])}
    zinfo = {z['id']: z for z in lay.get('zones', [])}
    if not zarea:   # fallback: polygon ∩ premises
        ex = load_existing()
        prem = premises(ex)
        zarea = {z['id']: round(Polygon(z['poly']).intersection(prem).area, 2) for z in lay.get('zones', [])}
    rows = []
    for lf in ls.get('load_factors', []):
        for zid in lf['zones']:
            if zid not in zarea:
                continue
            a = float(zarea[zid])
            raw = a / float(lf['factor'])
            rows.append({'zone': zid, 'name': zinfo.get(zid, {}).get('short') or zinfo.get(zid, {}).get('name', zid),
                         'use': lf.get('use', ''), 'area_m2': round(a, 2), 'factor_m2_per_person': lf['factor'],
                         'basis': lf.get('basis', ''), 'raw': round(raw, 2), 'occupants': _ceil(raw)})
    order = {z['id']: i for i, z in enumerate(lay.get('zones', []))}
    order_pub = {'D': 0, 'C': 1}
    rows.sort(key=lambda r: (order_pub.get(r['zone'], 5), order.get(r['zone'], 9)))
    total = sum(r['occupants'] for r in rows)
    by_factor = {}
    for r in rows:
        by_factor.setdefault(r['factor_m2_per_person'], 0.0)
        by_factor[r['factor_m2_per_person']] += r['area_m2']
    total_by_use = sum(_ceil(a / fct) for fct, a in by_factor.items())
    total_raw = sum(r['raw'] for r in rows)
    declared = int(ls.get('capacity_declared', 0) or 0)
    # scenario: bar/POS zone (C) counted as staff work area with the kitchen factor (no standing customers)
    scen = None
    fmax = max((float(lf['factor']) for lf in ls.get('load_factors', [])), default=None)
    rc = next((r for r in rows if r['zone'] == 'C'), None)
    if rc and fmax and fmax > rc['factor_m2_per_person']:
        alt_c = _ceil(rc['area_m2'] / fmax)
        scen = {'label': f"Zona C (barra/POS) como área de trabajo del personal a {fmax:g} m²/p (sin clientes de pie)",
                'zone_C_occupants': alt_c, 'total_rounded_per_zone': total - rc['occupants'] + alt_c}
    return {
        'rows': rows, 'total_rounded_per_zone': total, 'total_rounded_per_use': total_by_use,
        'total_unrounded': round(total_raw, 2), 'declared_capacity': declared, 'nfpa101_assembly_threshold': THRESHOLD,
        'classification_by_calc': 'reunión pública (≥50)' if total >= THRESHOLD else 'mercantil <50',
        'declared_ok_vs_calc': declared >= total,
        'below_threshold_calc': total < THRESHOLD,
        'below_threshold_declared': declared < THRESHOLD,
        'rounding': 'hacia arriba por zona (criterio conservador del paquete)',
        'scenario_bar_as_staff_area': scen,
    }


def _exit_segment(ex, lay, e):
    """Door opening segment ((x0,y0),(x1,y1)) + outward unit normal for an exit entry of life_safety.exits."""
    prem = premises(ex)
    seg = None
    for d in ex.get('doors', []):
        if d['id'] == e.get('opening') and d.get('opening'):
            x0, y0, x1, y1 = d['opening']
            seg = ((x0, y0), (x1, y1))
    if seg is None:
        for o in lay.get('new_openings', []):
            if (o.get('label') == e.get('opening') or o.get('id') == e.get('opening')) and o.get('rect'):
                x0, y0, x1, y1 = o['rect']
                if abs(x1 - x0) >= abs(y1 - y0):
                    seg = ((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2))
                else:
                    seg = (((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1))
    if seg is None:
        return None
    (x0, y0), (x1, y1) = seg
    vert = abs(x1 - x0) < abs(y1 - y0)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    if vert:
        n = (1.0, 0.0) if not prem.buffer(-0.01).contains(Point(mx + 0.3, my)) else (-1.0, 0.0)
    else:
        n = (0.0, 1.0) if not prem.buffer(-0.01).contains(Point(mx, my + 0.3)) else (0.0, -1.0)
    return seg, n, vert


class EgressGrid:
    """Walkable grid (body-centre positions) + multi-source Dijkstra from a set of exits."""

    def __init__(self, ex, lay, exits, body=None):
        self.ex, self.lay = ex, lay
        body = BODY if body is None else body
        prem, obs = blocking_obstacles(ex, lay, include_items=True)
        self.obs = obs
        self.prem = prem
        ext = [prem]
        self.exits = []
        for e in exits:
            got = _exit_segment(ex, lay, e)
            if not got:
                continue
            seg, n, vert = got
            (x0, y0), (x1, y1) = seg
            if vert:
                xa = x0
                ebox = box(min(xa, xa + n[0] * 0.8) - 0.12, min(y0, y1), max(xa, xa + n[0] * 0.8) + 0.12, max(y0, y1))
            else:
                ya = y0
                ebox = box(min(x0, x1), min(ya, ya + n[1] * 0.8) - 0.12, max(x0, x1), max(ya, ya + n[1] * 0.8) + 0.12)
            ext.append(ebox)
            self.exits.append({'id': e['id'], 'seg': seg, 'n': n, 'vert': vert, 'box': ebox, 'entry': e})
        area = unary_union(ext)
        self.walk = area.difference(obs).buffer(-body)
        self.walk_b = self.walk.buffer(0.02)
        shapely.prepare(self.walk_b)
        bx0, by0, bx1, by1 = area.bounds
        self.x0, self.y0 = bx0 - 0.1, by0 - 0.1
        self.nx = int(math.ceil((bx1 - self.x0 + 0.1) / RES))
        self.ny = int(math.ceil((by1 - self.y0 + 0.1) / RES))
        xs = self.x0 + (np.arange(self.nx) + 0.5) * RES
        ys = self.y0 + (np.arange(self.ny) + 0.5) * RES
        self.XX, self.YY = np.meshgrid(xs, ys)
        self.free = shapely.contains_xy(self.walk, self.XX, self.YY)
        idx = -np.ones(self.free.shape, dtype=np.int64)
        idx[self.free] = np.arange(int(self.free.sum()))
        self.idx = idx
        self.N = int(self.free.sum())
        self._flat_of = np.flatnonzero(self.free.ravel())
        self._graph()

    def _graph(self):
        F, I = self.free, self.idx
        rows, cols, w = [], [], []
        offs = [(0, 1), (1, 0), (1, 1), (1, -1), (1, 2), (2, 1), (2, -1), (1, -2)]
        H, W = F.shape
        for dj, di in offs:
            j0, j1 = max(0, -dj), H - max(0, dj)
            i0, i1 = max(0, -di), W - max(0, di)
            a = F[j0:j1, i0:i1] & F[j0 + dj:j1 + dj, i0 + di:i1 + di]
            if abs(dj) + abs(di) == 3:     # knight move: both intermediate cells free
                if abs(dj) == 2:
                    m1 = F[j0 + np.sign(dj):j1 + np.sign(dj), i0:i1]
                    m2 = F[j0 + np.sign(dj):j1 + np.sign(dj), i0 + di:i1 + di]
                else:
                    m1 = F[j0:j1, i0 + np.sign(di):i1 + np.sign(di)]
                    m2 = F[j0 + dj:j1 + dj, i0 + np.sign(di):i1 + np.sign(di)]
                a = a & m1 & m2
            src = I[j0:j1, i0:i1][a]
            dst = I[j0 + dj:j1 + dj, i0 + di:i1 + di][a]
            d = RES * math.hypot(dj, di)
            rows.append(src)
            cols.append(dst)
            w.append(np.full(src.shape, d))
        r = np.concatenate(rows)
        c = np.concatenate(cols)
        ww = np.concatenate(w)
        self.G = coo_matrix((np.concatenate([ww, ww]), (np.concatenate([r, c]), np.concatenate([c, r]))),
                            shape=(self.N, self.N)).tocsr()

    def cell(self, x, y):
        i = int((x - self.x0) / RES)
        j = int((y - self.y0) / RES)
        if 0 <= j < self.ny and 0 <= i < self.nx:
            return self.idx[j, i]
        return -1

    def xy(self, k):
        j, i = divmod(int(self._flat_of[k]), self.nx)
        return (self.x0 + (i + 0.5) * RES, self.y0 + (j + 0.5) * RES)

    def solve(self, which=None):
        """Distance field to the chosen exits (ids) — sources = free cells beyond each door plane."""
        src = []
        planes = []
        for e in self.exits:
            if which is not None and e['id'] not in which:
                continue
            (x0, y0), (x1, y1) = e['seg']
            if e['vert']:
                beyond = (self.XX - x0) * e['n'][0] > 0.0
            else:
                beyond = (self.YY - y0) * e['n'][1] > 0.0
            m = self.free & beyond & shapely.contains_xy(e['box'], self.XX, self.YY)
            src.extend(self.idx[m].tolist())
            planes.append(e)
        self.planes = planes
        D, pred, sources = dijkstra(self.G, directed=False, indices=src, min_only=True, return_predecessors=True)
        self.D, self.pred, self.srcs = D, pred, sources
        return D

    def field(self):
        out = np.full(self.free.shape, np.inf)
        out[self.free] = self.D
        return out

    def chain(self, k):
        pts = []
        while k >= 0:
            pts.append(self.xy(k))
            k = self.pred[k]
        return pts

    def smooth(self, pts):
        """Greedy string pulling against the walkable polygon."""
        if len(pts) <= 2:
            return pts
        if len(pts) > 180:
            step = int(math.ceil(len(pts) / 180))
            pts = pts[::step] + ([pts[-1]] if (len(pts) - 1) % step else [])
        out = [pts[0]]
        i = 0
        n = len(pts)
        while i < n - 1:
            cand = [LineString([pts[i], pts[j]]) for j in range(i + 1, n)]
            ok = shapely.covers(self.walk_b, np.array(cand, dtype=object))
            vis = np.flatnonzero(ok)
            j = i + 1 + (int(vis.max()) if len(vis) else 0)
            out.append(pts[j])
            i = j
        return out

    def clip_to_plane(self, pts):
        """Cut the polyline where it crosses the plane of the exit it reaches."""
        line = LineString(pts)
        best = None
        for e in self.planes:
            (x0, y0), (x1, y1) = e['seg']
            if e['vert']:
                half = box(-100, -100, x0, 100) if e['n'][0] > 0 else box(x0, -100, 100, 100)
            else:
                half = box(-100, -100, 100, y0) if e['n'][1] > 0 else box(-100, y0, 100, 100)
            end = Point(pts[-1])
            if e['box'].buffer(0.05).contains(end):
                cut = line.intersection(half)
                geoms = getattr(cut, 'geoms', None) or [cut]
                first = None
                for g in geoms:
                    if g.geom_type == 'LineString' and g.distance(Point(pts[0])) < 1e-6:
                        first = g
                if first is not None:
                    best = (list(first.coords), e['id'])
        if best is None:
            return pts, None
        return best

    def route(self, p, allow_lead=None):
        """Exact-ish shortest egress from point p: (length, pts, exit_id, lead)."""
        k = self.cell(*p)
        lead = 0.0
        start = p
        if k < 0 or not np.isfinite(self.D[k]):
            k, lead = self.nearest(p, allow_lead)
            if k < 0:
                return None
        pts = self.chain(k)
        pts = [start] + pts[1:] if lead == 0.0 else [start] + pts
        sm = self.smooth(pts) if lead == 0.0 else [start] + self.smooth(pts[1:])
        cut, eid = self.clip_to_plane(sm)
        return {'length': round(LineString(cut).length, 2), 'pts': [(round(x, 3), round(y, 3)) for x, y in cut],
                'exit': eid, 'lead': round(lead, 2)}

    def nearest(self, p, allow=None, rad=1.8):
        """Nearest reachable cell from an occupied position (seat): straight lead that only crosses `allow`."""
        px, py = p
        m = self.free & ((self.XX - px) ** 2 + (self.YY - py) ** 2 <= rad * rad)
        ks = self.idx[m]
        xs, ys = self.XX[m], self.YY[m]
        dd = np.hypot(xs - px, ys - py)
        tot = dd + self.D[ks]
        order = np.argsort(tot)
        block = self.obs.difference(allow) if allow is not None else self.obs
        shapely.prepare(block)
        for o in order[:400]:
            if not np.isfinite(tot[o]):
                break
            seg = LineString([p, (xs[o], ys[o])])
            if not block.intersects(seg):
                return int(ks[o]), float(dd[o])
        return -1, 0.0


def _front_point(e, depth=0.30):
    x0, y0, x1, y1 = e['rect']
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    fr = e.get('front')
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return {'N': (cx, y0 - depth), 'S': (cx, y1 + depth), 'W': (x0 - depth, cy), 'E': (x1 + depth, cy)}.get(fr, (cx, cy))


def _argmax_in(grid, region, n_cand=10):
    """Most remote reachable cells inside `region` (grid metric), refined with the exact route."""
    inside = grid.free & shapely.contains_xy(region, grid.XX, grid.YY)
    F = grid.field()
    vals = np.where(inside, F, -np.inf)
    vals[~np.isfinite(vals)] = -np.inf
    flat = np.argsort(vals.ravel())[::-1]
    picks = []
    for fl in flat:
        v = vals.ravel()[fl]
        if not np.isfinite(v) or len(picks) >= n_cand:
            break
        j, i = divmod(int(fl), grid.nx)
        x, y = grid.x0 + (i + 0.5) * RES, grid.y0 + (j + 0.5) * RES
        if all(math.hypot(x - a, y - b) > 0.12 for a, b in picks):
            picks.append((x, y))
    best = None
    for p in picks:
        r = grid.route(p)
        if r and (best is None or r['length'] > best['length']):
            best = r
            best['from_pt'] = (round(p[0], 3), round(p[1], 3))
    return best


def compute(ex, lay, val):
    ls = lay.get('life_safety', {})
    exits = ls.get('exits', [])
    main_exits = [e for e in exits if not e.get('conditional')]
    grid = EgressGrid(ex, lay, exits)
    zones = {z['id']: Polygon(z['poly']) for z in lay.get('zones', [])}
    zname = {z['id']: z.get('short') or z.get('name') for z in lay.get('zones', [])}
    eq = {e['id']: e for e in lay.get('equipment', [])}
    bykey = {}
    for e in lay.get('equipment', []):
        bykey.setdefault(e.get('key'), []).append(e)

    def run(which):
        grid.solve(which)
        out = []
        # 1. most remote point per zone (cold prep, washing, hot line, bar) + reception + smoker front + seats
        if 'A' in zones:
            r = _argmax_in(grid, zones['A'])
            if r:
                out.append(dict(r, id='E1', name=f"{zname['A']} · punto más remoto (zona A)", kind='zone', zone='A'))
        if 'W' in zones:
            r = _argmax_in(grid, zones['W'])
            if r:
                out.append(dict(r, id='E2', name=f"{zname['W']} · punto más remoto (zona W)", kind='zone', zone='W'))
        sm = (bykey.get('smoker') or [None])[0]
        if sm:
            p = _front_point(sm, 0.30)
            r = grid.route(p)
            if r:
                out.append(dict(r, id='E3', name=f"Frente del smoker {sm['id']} (operador)", kind='equipment', from_pt=p))
        hot = [e for k in HOT_KEYS for e in bykey.get(k, [])]
        if hot:
            reg = unary_union([front_zone(e) for e in hot if front_zone(e) is not None])
            r = _argmax_in(grid, reg)
            if r:
                out.append(dict(r, id='E4', name='Línea caliente · operador más remoto (H1–H5)', kind='zone', zone='B'))
        # farthest seat
        allow = unary_union([R(c['rect']) for c in lay.get('chairs', [])] + [R(b['rect']) for b in lay.get('banquettes', [])])
        best = None
        for sid, pt in seat_points(lay):
            k, lead = grid.nearest((pt.x, pt.y), allow)
            if k < 0:
                continue
            tot = lead + grid.D[k]
            if best is None or tot > best[0]:
                best = (tot, sid, (pt.x, pt.y))
        if best:
            r = grid.route(best[2], allow)
            if r:
                out.append(dict(r, id='E5', name=f"Salón · asiento más lejano ({best[1]})", kind='seat',
                                from_pt=(round(best[2][0], 3), round(best[2][1], 3))))
        if 'C' in zones:
            r = _argmax_in(grid, zones['C'])
            if r:
                out.append(dict(r, id='E6', name='Barra / caja · puesto más remoto (zona C)', kind='zone', zone='C'))
        rec = (bykey.get('delivery_staging') or bykey.get('host') or [None])[0]
        if rec:
            p = _front_point(rec, 0.30)
            r = grid.route(p)
            if r:
                out.append(dict(r, id='E7', name=f"Recepción {rec['id']} (atril)", kind='equipment', from_pt=p))
        if 'E' in zones:
            r = _argmax_in(grid, zones['E'])
            if r:
                out.append(dict(r, id='E8', name=f"{zname['E']} · punto más remoto (zona E)", kind='zone', zone='E'))
        # overall most remote reachable point
        r = _argmax_in(grid, grid.prem)
        if r:
            out.append(dict(r, id='E0', name='Punto más remoto del local', kind='global'))
        return out

    paths = run([e['id'] for e in main_exits])
    field_main = grid.field()
    for p in paths:
        p['limit_common_path_m'] = LIM_COMMON
        p['limit_travel_m'] = LIM_TRAVEL
        p['ok_common_path'] = p['length'] <= LIM_COMMON
        p['ok_travel'] = p['length'] <= LIM_TRAVEL
        p['ok'] = p['ok_common_path'] and p['ok_travel']
        p['margin_m'] = round(LIM_COMMON - p['length'], 2)
    # conditional variant (PS-1 counted) — informative only
    cond = [e for e in exits if e.get('conditional')]
    alt = {}
    if cond:
        grid.solve([e['id'] for e in exits])
        for p in paths:
            r = grid.route(tuple(p['pts'][0]), unary_union([R(c['rect']) for c in lay.get('chairs', [])] +
                                                           [R(b['rect']) for b in lay.get('banquettes', [])]))
            if r:
                alt[p['id']] = {'length': r['length'], 'exit': r['exit']}
    # restore main field for device checks
    grid.solve([e['id'] for e in main_exits])
    # sensitivity: NFPA 101 7.6 measures 0.30 m (12 in) clear of corners -> longest path again at 0.30 m
    sens = None
    crit = max(paths, key=lambda q: q['length']) if paths else None
    if crit:
        g30 = EgressGrid(ex, lay, main_exits, body=0.30)
        g30.solve([e['id'] for e in main_exits])
        if crit.get('zone') in zones:
            r30 = _argmax_in(g30, zones[crit['zone']])
        elif crit['kind'] == 'global':
            r30 = _argmax_in(g30, g30.prem)
        else:
            r30 = g30.route(tuple(crit['pts'][0]))
        if r30:
            sens = {'path': crit['id'], 'clearance_m': 0.30, 'length': r30['length'], 'limit': LIM_COMMON,
                    'ok': r30['length'] <= LIM_COMMON, 'from_pt': r30.get('from_pt') or r30['pts'][0]}

    # ---------------------------------------------------------------- extinguishers / devices (travel distances)
    exts = ls.get('extinguishers', [])

    def travel(a, b):
        """Walking distance between two points (single-source Dijkstra from a)."""
        ka = grid.cell(*a)
        if ka < 0:
            ka, _ = grid.nearest(a, None)
        kb = grid.cell(*b)
        if kb < 0:
            kb, _ = grid.nearest(b, None)
        if ka < 0 or kb < 0:
            return None, None
        D, pred = dijkstra(grid.G, directed=False, indices=ka, return_predecessors=True)
        if not np.isfinite(D[kb]):
            return None, None
        pts = []
        k = kb
        while k >= 0:
            pts.append(grid.xy(k))
            k = pred[k]
        pts = [b] + pts + [a]
        sm = grid.smooth(pts)
        return round(LineString(sm).length, 2), [(round(x, 3), round(y, 3)) for x, y in sm]

    checks = []
    k_ext = [e for e in exts if 'clase k' in e['type'].lower() or e['type'].strip().upper().startswith('K ')]
    a_ext = [e for e in exts if '2-A' in e['type'] or 'ABC' in e['type']]
    w_ext = [e for e in exts if 'agua' in e['type'].lower() or 'water' in e['type'].lower()]
    fry = [e for k in ('freidora_1', 'freidora_2') for e in bykey.get(k, [])]
    for hz in fry:
        best = None
        for xe in k_ext:
            L, pts = travel(_front_point(hz, 0.3), tuple(xe['at']))
            if L is not None and (best is None or L < best[0]):
                best = (L, pts, xe['id'])
        if best:
            checks.append({'id': f"K-{hz['id']}", 'hazard': f"{hz['id']} {hz.get('label', '')}", 'device': best[2],
                           'criterion': 'Extintor clase K a ≤ 9.15 m de recorrido (NFPA 10 §6.6 / NFPA 96)',
                           'length': best[0], 'limit': LIM_K, 'ok': best[0] <= LIM_K, 'pts': best[1], 'kind': 'K'})
    solid = [e for k in ('parrilla', 'smoker', 'fuel_storage') for e in bykey.get(k, [])]
    for hz in solid:
        best = None
        for xe in w_ext + k_ext:          # NFPA 96: 2-A tipo AGUA o K 6 L (un ABC de polvo no califica)
            L, pts = travel(_front_point(hz, 0.3), tuple(xe['at']))
            if L is not None and (best is None or L < best[0]):
                best = (L, pts, xe['id'])
        if best:
            checks.append({'id': f"SF-{hz['id']}", 'hazard': f"{hz['id']} {hz.get('plan_label') or hz.get('label', '')}",
                           'device': best[2],
                           'criterion': '2-A (agua) o K 6 L a ≤ 6 m de recorrido de equipo/almacén de combustible sólido (NFPA 96, verificar)',
                           'length': best[0], 'limit': LIM_SOLID, 'ok': best[0] <= LIM_SOLID, 'pts': best[1], 'kind': 'SF'})
    for hz in [e for k in GAS_KEYS for e in bykey.get(k, [])][:1] + [e for k in GAS_KEYS for e in bykey.get(k, [])][-1:]:
        best = None
        for xe in a_ext:
            L, pts = travel(_front_point(hz, 0.3), tuple(xe['at']))
            if L is not None and (best is None or L < best[0]):
                best = (L, pts, xe['id'])
        if best:
            checks.append({'id': f"B-{hz['id']}", 'hazard': f"{hz['id']} {hz.get('plan_label') or hz.get('label', '')} (gas)",
                           'device': best[2], 'criterion': 'Clase B: 10-B a ≤ 9.15 m de recorrido (NFPA 10 §6.3.1)',
                           'length': best[0], 'limit': LIM_B, 'ok': best[0] <= LIM_B, 'pts': best[1], 'kind': 'B'})
    # class A: max travel from any reachable point to the nearest 2-A extinguisher
    srcA = []
    for xe in a_ext:
        k = grid.cell(*xe['at'])
        if k < 0:
            k, _ = grid.nearest(tuple(xe['at']), None)
        if k >= 0:
            srcA.append(k)
    if srcA:
        DA = dijkstra(grid.G, directed=False, indices=srcA, min_only=True)
        fin = DA[np.isfinite(DA)]
        mx = float(fin.max()) if len(fin) else float('nan')
        checks.append({'id': 'A-max', 'hazard': 'Local completo (riesgo ordinario)', 'device': ', '.join(e['id'] for e in a_ext),
                       'criterion': 'Clase A: recorrido ≤ 22.9 m al extintor 2-A más cercano (NFPA 10 Tabla 6.2.1.1)',
                       'length': round(mx, 2), 'limit': LIM_A, 'ok': mx <= LIM_A, 'kind': 'A'})
    # pull station (manual release HD-1)
    ps = ls.get('pull_station')
    hood1 = eq.get('HD-1')
    if ps and hood1:
        at = tuple(ps['at'])
        hd = R(hood1['rect'])
        eu = hd.distance(Point(at))
        ln_hood, pts_h = travel(_front_point(eq.get('H3', hood1) if 'H3' in eq else hood1, 0.3), at)
        kitchen = unary_union([zones[z] for z in ('A', 'B', 'E', 'W') if z in zones])
        kp = [p for p in paths if kitchen.buffer(0.05).contains(Point(p['pts'][0]))]
        route_d = min(LineString(p['pts']).distance(Point(at)) for p in kp) if kp else None
        checks.append({'id': 'PM-1', 'hazard': 'Disparo manual supresión HD-1', 'device': 'PM-1',
                       'criterion': 'En ruta de egreso, h 1.07–1.22 m (NFPA 96 §10.5.1); 3–6 m de la campana = criterio IFC de referencia (verificar)',
                       'length': round(eu, 2), 'limit': 6.0, 'ok': 3.0 <= eu <= 6.0 and (route_d is None or route_d <= 1.0),
                       'walk_from_line': ln_hood, 'dist_to_egress_path': round(route_d, 2) if route_d is not None else None,
                       'kind': 'PM', 'pts': pts_h})

    # ---------------------------------------------------------------- exits capacity
    load = occupant_load(lay, val)
    exit_rows = []
    for e in exits:
        w = float(e.get('width', 0))
        leaf = float(e.get('leaf', w) or w)
        cap = int(w * 1000 / MM_PER_P)
        exit_rows.append({'id': e['id'], 'opening': e.get('opening'), 'width_m': w, 'leaf_m': leaf,
                          'capacity_persons_5mm': cap, 'required_width_mm': round(load['declared_capacity'] * MM_PER_P, 1),
                          'required_width_calc_mm': round(load['total_rounded_per_zone'] * MM_PER_P, 1),
                          'counted': not e.get('conditional'), 'ok': cap >= max(load['declared_capacity'], load['total_rounded_per_zone']) and leaf >= 0.81,
                          'note': e.get('note', '')})
    return {'grid': grid, 'paths': paths, 'alt_with_ps1': alt, 'sensitivity_030': sens, 'checks': checks, 'load': load, 'exits': exit_rows,
            'field': field_main}


def calcs_json(res, lay):
    L = res['load']
    paths = [{'id': p['id'], 'from': p['name'], 'from_pt': p.get('from_pt') or p['pts'][0], 'exit': p['exit'],
              'length': p['length'], 'limit': p['limit_common_path_m'], 'ok': p['ok'],
              'length_m': p['length'], 'limit_common_path_m': p['limit_common_path_m'], 'limit_travel_m': p['limit_travel_m'],
              'ok_common_path': p['ok_common_path'], 'ok_travel': p['ok_travel'], 'margin_m': p['margin_m'],
              'length_with_ps1_conditional_m': (res['alt_with_ps1'].get(p['id']) or {}).get('length'),
              'polyline': p['pts']} for p in res['paths']]
    issues = []
    if L['total_rounded_per_zone'] >= THRESHOLD or L['total_rounded_per_zone'] > L['declared_capacity']:
        issues.append(f"Carga calculada (redondeo por zona) {L['total_rounded_per_zone']} ≥ umbral {THRESHOLD} y > capacidad declarada "
                      f"{L['declared_capacity']}: la estrategia mercantil <50 (salida única, puerta hacia adentro, sin rociadores) "
                      f"requiere justificar el método (por uso = {L['total_rounded_per_use']}) o el uso de la barra C.")
    for p in paths:
        if not p['ok']:
            issues.append(f"Recorrido {p['id']} ({p['from']}) {p['length']:.2f} m > límite {p['limit']:.0f} m.")
    for c in res['checks']:
        if not c['ok']:
            issues.append(f"{c['id']}: {c['hazard']} — {c['criterion']} (medido {c['length']:.2f} m"
                          + (f"; {c['dist_to_egress_path']:.2f} m fuera de la ruta de egreso de cocina" if c.get('dist_to_egress_path') is not None else '')
                          + ').')
    longest = max(paths, key=lambda q: q['length']) if paths else None
    return {
        'summary': {'longest_path': {'id': longest['id'], 'from': longest['from'], 'length': longest['length'],
                                     'limit': longest['limit']} if longest else None,
                    'all_egress_paths_ok': all(p['ok'] for p in paths), 'issues': issues,
                    'longest_path_at_0.30m_clearance': res.get('sensitivity_030')},
        'sheet': 'A-104', 'status': 'ANTEPROYECTO / PRELIMINAR — a validar por el profesional responsable (CFIA) y Bomberos',
        'layout_version': lay.get('meta', {}).get('version'),
        'method': {
            'occupant_load': 'Área de zona (validation.json, m²) ÷ factor (layout.life_safety.load_factors); redondeo hacia arriba por zona.',
            'egress': (f'Camino más corto sobre grilla de {RES*100:.0f} cm (16 vecinos) en el espacio libre = premisas − '
                       f'lavageo.blocking_obstacles (muros, columnas, equipos, mesas, sillas en posición ocupada, bancas) '
                       f'erosionado {BODY:.2f} m (radio corporal); suavizado por visibilidad y medido hasta el plano de la '
                       f'puerta de salida. Desde asientos: tramo recto hasta el pasillo cruzando solo sillas/bancas. '
                       f'Contraste: geodésica exacta (grafo de visibilidad) del recorrido más largo ≈ 0.5 % menor (el método '
                       f'queda del lado conservador); con 0.30 m de las esquinas (NFPA 101 7.6) ver summary.'),
            'limits_source': 'NFPA 101 (edición a verificar, adoptada por RNPCI 2023): camino común 23 m y recorrido 46 m '
                             '(mercantil <50 personas, sin rociadores); capacidad 5 mm/persona.',
        },
        'occupant_load': L,
        'egress_paths': paths,
        'exits': res['exits'],
        'device_checks': [{k: v for k, v in c.items() if k != 'pts'} for c in res['checks']],
    }



# ============================================================================ drawing helpers (sheet mm)
def _to_sheet(g):
    return shapely.affinity.affine_transform(g, [S, 0, 0, S, sx(0), sy(0)])


def _pts(pts):
    return ' '.join(f"{f(sx(x))},{f(sy(y))}" for x, y in pts)


def sym_exit_sign(cx, cy, d='E'):
    w, h = 7.0, 3.0
    g = [f'<rect x="{f(cx - w/2)}" y="{f(cy - h/2)}" width="{w}" height="{h}" rx="0.4" fill="{C_EGR}" stroke="#063d1d" stroke-width="0.25"/>',
         text(cx - 0.9, cy + 0.5, 'SALIDA', 1.3, weight='800', fill='#ffffff')]
    ax, ay = cx + w / 2 - 1.1, cy
    tri = {'E': [(ax - 0.6, ay - 0.8), (ax + 0.7, ay), (ax - 0.6, ay + 0.8)],
           'W': [(ax + 0.6, ay - 0.8), (ax - 0.7, ay), (ax + 0.6, ay + 0.8)],
           'N': [(ax - 0.8, ay + 0.6), (ax, ay - 0.8), (ax + 0.8, ay + 0.6)],
           'S': [(ax - 0.8, ay - 0.6), (ax, ay + 0.8), (ax + 0.8, ay - 0.6)]}.get(d)
    if tri:
        g.append(f'<polygon points="{" ".join(f"{f(a)},{f(b)}" for a, b in tri)}" fill="#ffffff"/>')
    return ''.join(g)


def sym_em_light(cx, cy):
    return (f'<rect x="{f(cx - 2.1)}" y="{f(cy - 1.1)}" width="4.2" height="2.2" rx="0.3" fill="#fff3b0" stroke="#3a3000" stroke-width="0.3"/>'
            f'<circle cx="{f(cx - 1.0)}" cy="{f(cy)}" r="0.6" fill="#3a3000"/><circle cx="{f(cx + 1.0)}" cy="{f(cy)}" r="0.6" fill="#3a3000"/>')


def sym_ext(cx, cy, letter):
    size = 1.9 if len(letter) == 1 else 1.15
    return (f'<circle cx="{f(cx)}" cy="{f(cy)}" r="2.1" fill="{C_FIRE}" stroke="#5c0010" stroke-width="0.3"/>'
            + text(cx, cy + size * 0.36, letter, size, weight='800', fill='#ffffff'))


def sym_pull(cx, cy):
    return (f'<rect x="{f(cx - 1.8)}" y="{f(cy - 1.8)}" width="3.6" height="3.6" fill="{C_FIRE}" stroke="#5c0010" stroke-width="0.3"/>'
            + text(cx, cy + 0.5, 'PM', 1.35, weight='800', fill='#ffffff'))


def sym_det(cx, cy, letter):
    return (f'<circle cx="{f(cx)}" cy="{f(cy)}" r="1.7" fill="#ffffff" stroke="#1b1b1b" stroke-width="0.35"/>'
            + text(cx, cy + 0.62, letter, 1.7, weight='800', fill='#1b1b1b'))


def sym_valve(cx, cy, solenoid=False):
    g = [f'<polygon points="{f(cx-1.9)},{f(cy-1.1)} {f(cx)},{f(cy)} {f(cx-1.9)},{f(cy+1.1)}" fill="{C_GAS}" stroke="#5a4300" stroke-width="0.25"/>',
         f'<polygon points="{f(cx+1.9)},{f(cy-1.1)} {f(cx)},{f(cy)} {f(cx+1.9)},{f(cy+1.1)}" fill="{C_GAS}" stroke="#5a4300" stroke-width="0.25"/>']
    if solenoid:
        g.append(f'<line x1="{f(cx)}" y1="{f(cy)}" x2="{f(cx)}" y2="{f(cy-1.6)}" stroke="#5a4300" stroke-width="0.25"/>')
        g.append(f'<rect x="{f(cx-0.95)}" y="{f(cy-3.4)}" width="1.9" height="1.9" fill="#ffffff" stroke="#5a4300" stroke-width="0.25"/>')
        g.append(text(cx, cy - 1.95, 'S', 1.3, weight='800', fill='#5a4300'))
    return ''.join(g)


def sym_gas_entry(cx, cy):
    return (f'<circle cx="{f(cx)}" cy="{f(cy)}" r="1.7" fill="#ffffff" stroke="{C_GAS}" stroke-width="0.45"/>'
            + text(cx, cy + 0.62, 'G', 1.7, weight='800', fill='#5a4300'))


def sym_capacity(cx, cy):
    return (f'<rect x="{f(cx - 3.6)}" y="{f(cy - 2.2)}" width="7.2" height="4.4" fill="#ffffff" stroke="#111" stroke-width="0.4"/>'
            + text(cx, cy - 0.55, 'CAP. MÁX.', 0.95, weight='700', fill='#111')
            + text(cx, cy + 1.75, '49', 2.2, weight='800', fill=C_EGR2))


def sym_badge(cx, cy, letter, color, label):
    w = 5.2 + tw(label, 2.1) + 1.2
    x0 = cx - w / 2
    return (f'<rect x="{f(x0)}" y="{f(cy - 2.5)}" width="{f(w)}" height="5.0" rx="2.5" fill="#ffffff" fill-opacity="0.94" stroke="{color}" stroke-width="0.45"/>'
            f'<circle cx="{f(x0 + 2.5)}" cy="{f(cy)}" r="2.05" fill="{color}"/>'
            + text(x0 + 2.5, cy + 0.8, letter, 2.2, weight='800', fill='#ffffff')
            + text(x0 + 5.2, cy + 0.78, label, 2.1, anchor='start', weight='800', fill=color, family=MONO)), w


class Placer:
    """Very small collision-aware label placer in sheet mm."""

    def __init__(self, area=(12.5, 13.5, 429.5, 309.0)):
        self.occ = []
        self.area = box(*area)

    def add(self, geom, w=1.0):
        if geom is not None and not geom.is_empty:
            self.occ.append((geom, w))

    def cost(self, b):
        c = 0.0
        for g, w in self.occ:
            if g.intersects(b):
                c += w * (g.intersection(b).area if g.geom_type in ('Polygon', 'MultiPolygon') else g.intersection(b).length * 0.8)
        if not self.area.contains(b):
            c += 1000
        return c

    def place(self, cands, w, h, weight=3.0):
        best = None
        for i, (cx, cy) in enumerate(cands):
            b = box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            c = self.cost(b) + i * 0.02
            if best is None or c < best[0]:
                best = (c, cx, cy, b)
        self.add(best[3], weight)
        return best[1], best[2]


def ring_offsets(cx, cy, w, h, gap=2.6):
    dx, dy = w / 2 + gap, h / 2 + gap
    return [(cx + dx, cy), (cx - dx, cy), (cx, cy - dy), (cx, cy + dy), (cx + dx, cy - dy), (cx - dx, cy - dy),
            (cx + dx, cy + dy), (cx - dx, cy + dy), (cx + dx + 3, cy), (cx - dx - 3, cy), (cx, cy - dy - 3), (cx, cy + dy + 3)]


def table(x, y, cols, rows, size=1.85, rh=3.9, head_size=1.7, colors=None, weights=None, families=None):
    """cols: [(dx, header, anchor)] ; rows: list of lists of str."""
    g = []
    for dx, hd, anc in cols:
        g.append(text(x + dx, y + 2.4, hd, head_size, anchor=anc, weight='700', fill='#555'))
    xe = x + max(dx for dx, _, _ in cols)
    g.append(f'<line x1="{f(x)}" y1="{f(y + 3.6)}" x2="{f(xe)}" y2="{f(y + 3.6)}" stroke="#141210" stroke-width="0.3"/>')
    yy = y + 3.6
    for i, r in enumerate(rows):
        for j, ((dx, _, anc), v) in enumerate(zip(cols, r)):
            c = (colors[i][j] if colors and colors[i] and colors[i][j] else '#1f1f1f')
            wgt = (weights[i][j] if weights and weights[i] and weights[i][j] else '400')
            fam = (families[j] if families and families[j] else FONT)
            g.append(text(x + dx, yy + rh * 0.72, v, size, anchor=anc, weight=wgt, fill=c, family=fam))
        g.append(f'<line x1="{f(x)}" y1="{f(yy + rh)}" x2="{f(xe)}" y2="{f(yy + rh)}" stroke="#e1ddd6" stroke-width="0.2"/>')
        yy += rh
    return ''.join(g), yy


def callout(x, y, w, lines, color, target=None, size=1.7, lh=2.3, first_color=None, anchor_side='bottom'):
    h = len(lines) * lh + 2.0
    g = [f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="0.8" fill="#ffffff" stroke="{color}" stroke-width="0.4"/>']
    for i, ln in enumerate(lines):
        red = ln.startswith('!')
        s = ln[1:] if red else ln
        g.append(text(x + 1.4, y + 1.2 + (i + 0.75) * lh, s, size, anchor='start', weight='800' if i == 0 or red else '400',
                      fill=(first_color or color) if i == 0 else (C_EGR2 if red else '#262626')))
    if target:
        tx, ty = target
        bx = min(max(tx, x + 2), x + w - 2)
        by = y + h if anchor_side == 'bottom' else y
        if anchor_side == 'left':
            bx, by = x, min(max(ty, y + 2), y + h - 2)
        g.append(f'<polyline points="{f(bx)},{f(by)} {f(tx)},{f(ty)}" fill="none" stroke="{color}" stroke-width="0.3"/>')
        g.append(f'<circle cx="{f(tx)}" cy="{f(ty)}" r="0.55" fill="{color}"/>')
    return ''.join(g), h


# ============================================================================ sheet
def build_sheet(ex, lay, val, res):
    ls = lay.get('life_safety', {})
    mep = lay.get('mep', {})
    eq = {e['id']: e for e in lay.get('equipment', [])}
    zones = {z['id']: z for z in lay.get('zones', [])}
    zpoly = {z['id']: Polygon(z['poly']) for z in lay.get('zones', [])}
    prem = premises(ex)
    L = res['load']
    paths = res['paths']
    checks = res['checks']
    s = Sheet(ex, lay, val, 'A104')
    s.add('<defs><marker id="arr-egr" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.6" markerHeight="3.6" orient="auto">'
          f'<path d="M0,0 L6,3 L0,6 z" fill="{C_EGR}"/></marker>'
          '<pattern id="hatch-haz" patternUnits="userSpaceOnUse" width="1.3" height="1.3" patternTransform="rotate(45)">'
          '<rect width="1.3" height="1.3" fill="#fde2c8"/><line x1="0" y1="0" x2="0" y2="1.3" stroke="#e8914a" stroke-width="0.25"/></pattern></defs>')
    s.frame_and_titleblock('A-104 · Seguridad humana y protección contra incendios',
                           'Carga de ocupantes · egreso medido · señalización · emergencia · extintores · supresión · gas', 'A-104')
    s.grid_axes()
    s.layer_zones(0.05)
    s.layer_existing()
    s.layer_new()
    s.layer_furniture(faint=True)
    s.layer_equipment(faint=True, labels=False)

    P = Placer()
    # static obstacles for labels: walls, columns, hazard equipment
    for w, gm in standing_existing_walls(ex, lay):
        P.add(_to_sheet(gm), 0.35)
    for c in ex['columns']:
        P.add(_to_sheet(R(c['rect'])), 0.6)
    for w in lay.get('new_walls', []):
        P.add(_to_sheet(R(w['rect'])), 0.6)
    for o in lay.get('new_openings', []):
        if o.get('rect'):
            P.add(_to_sheet(R(o['rect']).buffer(0.25)), 0.8)

    # ---------------------------------------------------------------- hazards: fire equipment, hoods, flue
    g = ['<g id="hazards">']
    haz = [e for e in lay.get('equipment', []) if not e.get('overhead') and (e.get('cat') in ('fire', 'smoker') or e.get('key') == 'fuel_storage')
           and not e.get('stack_with')]
    collars = [tuple(xh['collar']) for xh in mep.get('exhaust', []) if xh.get('collar')]
    for e in haz:
        fill = 'url(#hatch-smoker)' if e.get('key') == 'smoker' else ('url(#hatch-haz)' if e.get('key') == 'fuel_storage' else '#fbd9b6')
        g.append(rect_el(e['rect'], fill, '#c46a1a', 0.3))
        x0, y0, x1, y1 = e['rect']
        x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        rot = -90 if (y1 - y0) > (x1 - x0) * 1.3 else 0
        tx, ty = (x0 + x1) / 2, (y0 + y1) / 2
        for cx_, cy_ in collars:     # keep the tag clear of a duct collar drawn inside the item
            if x0 <= cx_ <= x1 and y0 <= cy_ <= y1 and math.hypot(cx_ - tx, cy_ - ty) < 0.3:
                if rot:
                    far = y0 if abs(cy_ - y0) > abs(cy_ - y1) else y1
                    ty = (cy_ + far) / 2
                else:
                    far = x0 if abs(cx_ - x0) > abs(cx_ - x1) else x1
                    tx = (cx_ + far) / 2
        g.append(text(sx(tx) + (0.55 if rot else 0), sy(ty) + (0 if rot else 0.55), e.get('tag', e['id']), 1.55,
                      weight='800', fill='#7a3500', rot=rot))
    for hd in [e for e in lay.get('equipment', []) if e.get('key') == 'hood']:
        g.append(rect_el(hd['rect'], 'none', '#b35900', 0.55, dash='2.2 0.9'))
    # smoker flue EXT-3 + hood collars
    for xh in mep.get('exhaust', []):
        c = xh.get('collar')
        if not c:
            continue
        col = '#6e2508' if 'smoker' in xh.get('kind', '') or 'chimenea' in xh.get('kind', '') else '#b35900'
        if xh.get('route') and ('chimenea' in xh.get('kind', '')):
            g.append(f'<polyline points="{_pts(xh["route"])}" fill="none" stroke="{col}" stroke-width="0.9" stroke-dasharray="1.6 0.8"/>')
            ex_, ey_ = xh['route'][-1]
            g.append(f'<circle cx="{f(sx(ex_))}" cy="{f(sy(ey_))}" r="1.3" fill="#ffffff" stroke="{col}" stroke-width="0.45"/>')
        cx, cy = sx(c[0]), sy(c[1])
        g.append(f'<rect x="{f(cx-1.4)}" y="{f(cy-1.4)}" width="2.8" height="2.8" fill="#ffffff" stroke="{col}" stroke-width="0.4"/>'
                 f'<path d="M{f(cx-1.4)},{f(cy-1.4)} L{f(cx+1.4)},{f(cy+1.4)} M{f(cx-1.4)},{f(cy+1.4)} L{f(cx+1.4)},{f(cy-1.4)}" stroke="{col}" stroke-width="0.3"/>')
        P.add(box(cx - 1.6, cy - 1.6, cx + 1.6, cy + 1.6), 2)
    g.append('</g>')
    s.add(''.join(g))
    for e in haz:
        P.add(_to_sheet(R(e['rect'])), 0.25)
    # hood labels (rotated, inside the hood projection)
    for hd in [e for e in lay.get('equipment', []) if e.get('key') == 'hood']:
        x0, y0, x1, y1 = hd['rect']
        txt = f"{hd['id']} · {'SUPRESIÓN UL 300' if hd['id'] == 'HD-1' else 'COMB. SÓLIDO'}"
        s.add(text(sx(x0) + 1.9, sy((y0 + y1) / 2), txt, 1.6, weight='800', fill='#b35900', rot=-90,
                   extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.7"'))

    # ---------------------------------------------------------------- extinguisher coverage (reference radii)
    exts = ls.get('extinguishers', [])
    kx = [e for e in exts if 'clase k' in e['type'].lower()]
    g = ['<g id="coverage">']
    cov_labels = []
    for xe in kx:
        for r_, col, lab in ((LIM_K, '#7a1fa2', f'R {LIM_K:.2f} m · clase K (freidoras)'),
                             (LIM_SOLID, '#c2410c', f'R {LIM_SOLID:.1f} m · comb. sólido')):
            arc = Point(*xe['at']).buffer(r_, 128).exterior.intersection(prem.buffer(-0.02))
            parts = [p for p in (getattr(arc, 'geoms', None) or [arc]) if p.geom_type == 'LineString' and p.length > 0.3]
            for p in parts:
                g.append(f'<polyline points="{_pts(list(p.coords))}" fill="none" stroke="{col}" stroke-width="0.4" stroke-dasharray="2.4 1.2"/>')
                P.add(_to_sheet(p).buffer(0.4), 0.4)
            if parts:
                longest = max(parts, key=lambda q: q.length)
                cov_labels.append((longest, col, lab))
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- gas (schematic)
    gas = mep.get('gas', {})
    g = ['<g id="gas">']
    if gas.get('main_valve') and gas.get('solenoid'):
        cons = [eq[c] for c in gas.get('consumers', []) if c in eq]
        vm, vs = gas['main_valve'], gas['solenoid']
        if gas.get('entry'):
            g.append(f'<polyline points="{_pts([gas["entry"], vm])}" fill="none" stroke="{C_GAS}" stroke-width="0.5" stroke-dasharray="2 0.8"/>')
        if cons:
            xr = max(max(e['rect'][0], e['rect'][2]) for e in cons) - 0.12
            ys = [(e['rect'][1] + e['rect'][3]) / 2 for e in cons]
            trunk = [vm, vs, (xr, vs[1]), (xr, max(ys))]
            g.append(f'<polyline points="{_pts(trunk)}" fill="none" stroke="{C_GAS}" stroke-width="0.5" stroke-dasharray="2 0.8"/>')
            for yv in ys:
                g.append(f'<circle cx="{f(sx(xr))}" cy="{f(sy(yv))}" r="0.55" fill="{C_GAS}"/>')
        if gas.get('entry'):
            g.append(sym_gas_entry(sx(gas['entry'][0]), sy(gas['entry'][1])))
            P.add(box(sx(gas['entry'][0]) - 1.9, sy(gas['entry'][1]) - 1.9, sx(gas['entry'][0]) + 1.9, sy(gas['entry'][1]) + 1.9), 3)
        g.append(sym_valve(sx(vm[0]), sy(vm[1])))
        g.append(sym_valve(sx(vs[0]), sy(vs[1]), solenoid=True))
        P.add(box(sx(vm[0]) - 2, sy(vm[1]) - 1.3, sx(vm[0]) + 2, sy(vm[1]) + 1.3), 3)
        P.add(box(sx(vs[0]) - 2, sy(vs[1]) - 3.6, sx(vs[0]) + 2, sy(vs[1]) + 1.3), 3)
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- egress paths
    crit = max(paths, key=lambda p: p['length']) if paths else None
    shown = []
    for p in paths:
        if p['id'] == 'E0' and any(q is not p and math.dist(q['pts'][0], p['pts'][0]) < 0.2 for q in paths):
            continue
        shown.append(p)
    g = ['<g id="egress">']
    if crit:
        g.append(f'<polyline points="{_pts(crit["pts"])}" fill="none" stroke="{C_EGR if crit["ok"] else C_EGR2}" stroke-opacity="0.22" '
                 f'stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>')
    for p in sorted(shown, key=lambda q: q['length']):
        col = C_EGR if p['ok'] else C_EGR2
        g.append(f'<polyline points="{_pts(p["pts"])}" fill="none" stroke="{col}" stroke-width="0.55" stroke-linecap="round" '
                 f'stroke-linejoin="round" marker-end="url(#arr-egr)"/>')
        P.add(_to_sheet(LineString(p['pts'])).buffer(0.7), 1.2)
    for p in shown:
        x, y = sx(p['pts'][0][0]), sy(p['pts'][0][1])
        g.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="1.25" fill="#ffffff" stroke="{C_EGR if p["ok"] else C_EGR2}" stroke-width="0.5"/>'
                 f'<circle cx="{f(x)}" cy="{f(y)}" r="0.5" fill="{C_EGR if p["ok"] else C_EGR2}"/>')
        P.add(box(x - 1.5, y - 1.5, x + 1.5, y + 1.5), 3)
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- exits
    g = ['<g id="exits">']
    for e in ls.get('exits', []):
        got = _exit_segment(ex, lay, e)
        if not got:
            continue
        seg, n, vert = got
        (x0, y0), (x1, y1) = seg
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        cond = e.get('conditional')
        col = C_EGR2 if cond else C_EGR
        # arrow outward
        off = 0.34 if cond else 0.50          # clear of the 'ACCESO' / 'PS-1 · 0.90' labels drawn by plan_svg
        ax0, ay0 = sx(mx + n[0] * off), sy(my + n[1] * off)
        L_ = 7.0 if cond else 9.0
        bx, by = ax0 + n[0] * L_, ay0 + n[1] * L_
        px, py = -n[1], n[0]
        wbody, whead = 1.3 if not cond else 0.9, 3.0 if not cond else 2.2
        poly = [(ax0 + px * wbody, ay0 + py * wbody), (bx - n[0] * 3.2 + px * wbody, by - n[1] * 3.2 + py * wbody),
                (bx - n[0] * 3.2 + px * whead, by - n[1] * 3.2 + py * whead), (bx, by),
                (bx - n[0] * 3.2 - px * whead, by - n[1] * 3.2 - py * whead), (bx - n[0] * 3.2 - px * wbody, by - n[1] * 3.2 - py * wbody),
                (ax0 - px * wbody, ay0 - py * wbody)]
        dash = ' stroke-dasharray="1 0.6"' if cond else ''
        pstr = ' '.join(f'{f(a)},{f(b)}' for a, b in poly)
        g.append(f'<polygon points="{pstr}" fill="{col if not cond else "#ffffff"}" stroke="{col}" stroke-width="0.4"{dash}/>')
        P.add(box(min(ax0, bx) - 3.2, min(ay0, by) - 3.2, max(ax0, bx) + 3.2, max(ay0, by) + 3.2), 3)
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- devices
    dev = ['<g id="devices">']
    labels = []    # (anchor_x, anchor_y, lines, color, size)
    placed = []    # symbol boxes already drawn (sheet mm) -> nudge coincident ceiling devices for legibility

    def put(cx, cy, hw, hh):
        for dx, dy in ((0, 0), (0, -3.6), (0, 3.6), (-5.0, 0), (5.0, 0), (0, -6.5)):
            b_ = box(cx + dx - hw, cy + dy - hh, cx + dx + hw, cy + dy + hh)
            if not any(b_.intersects(q) for q in placed):
                placed.append(b_)
                P.add(b_, 4)
                return cx + dx, cy + dy
        b_ = box(cx - hw, cy - hh, cx + hw, cy + hh)
        placed.append(b_)
        P.add(b_, 4)
        return cx, cy

    for rs in ls.get('exit_signs', []):
        cx, cy = put(sx(rs['at'][0]), sy(rs['at'][1]), 3.6, 1.6)
        dev.append(sym_exit_sign(cx, cy, rs.get('dir', 'E')))
        labels.append((cx, cy, [rs['id']], C_EGR, 1.6, 7.2, 3.0))
    for xe in exts:
        cx, cy = put(sx(xe['at'][0]), sy(xe['at'][1]), 2.2, 2.2)
        k = 'clase k' in xe['type'].lower()
        dev.append(sym_ext(cx, cy, 'K' if k else 'ABC'))
        labels.append((cx, cy, [xe['id'], xe['type'].replace('Clase K 6 L', 'K 6 L')], C_FIRE, 1.6, None, None))
    for pt in ls.get('emergency_lights', []):
        cx, cy = put(sx(pt[0]), sy(pt[1]), 2.2, 1.2)
        dev.append(sym_em_light(cx, cy))
    hot_zone = unary_union([zpoly[z] for z in ('B', 'E') if z in zpoly]) if zpoly else None
    n_heat = n_smoke = 0
    for pt in ls.get('smoke_detectors', []):
        heat = hot_zone is not None and hot_zone.buffer(0.01).contains(Point(pt))
        n_heat += heat
        n_smoke += not heat
        cx, cy = put(sx(pt[0]), sy(pt[1]), 1.8, 1.8)
        dev.append(sym_det(cx, cy, 'T' if heat else 'H'))
    pm = ls.get('pull_station')
    if pm:
        cx, cy = put(sx(pm['at'][0]), sy(pm['at'][1]) + 1.9, 1.9, 1.9)
        dev.append(sym_pull(cx, cy))
        labels.append((cx, cy, ['PM-1', f"h {pm.get('h', '')}"], C_FIRE, 1.6, None, None))
    # capacity sign beside the main exit (storefront, south jamb of the door)
    main = next((e for e in ls.get('exits', []) if not e.get('conditional')), None)
    cap_xy = None
    if main:
        got = _exit_segment(ex, lay, main)
        if got:
            (x0, y0), (x1, y1) = got[0]
            n = got[1]
            if got[2]:
                cap_xy = (sx(x0 - n[0] * 0.22), sy(max(y0, y1) + 0.30))
            else:
                cap_xy = (sx(max(x0, x1) + 0.30), sy(y0 - n[1] * 0.22))
            cap_xy = put(cap_xy[0], cap_xy[1], 3.8, 2.4)
            dev.append(sym_capacity(*cap_xy))
    if gas.get('main_valve'):
        labels.append((sx(gas['main_valve'][0]), sy(gas['main_valve'][1]), ['VM'], '#5a4300', 1.6, None, None))
    dev.append('</g>')
    s.add(''.join(dev))

    # ---------------------------------------------------------------- zone badges (occupant load)
    lrow = {r['zone']: r for r in L['rows']}
    g = ['<g id="zone-load">']
    for zid, z in zones.items():
        if zid not in lrow:
            continue
        poly = zpoly[zid].intersection(prem)
        color = z.get('color') or '#555'
        label = f"{lrow[zid]['occupants']} p"
        w = 5.2 + tw(label, 2.1) + 1.2
        at = z.get('label_at') or (poly.representative_point().x, poly.representative_point().y)
        cands = []
        inner = poly.buffer(-0.18)
        minx, miny, maxx, maxy = inner.bounds
        for xx in np.arange(minx, maxx, 0.2):
            for yy in np.arange(miny, maxy, 0.2):
                if inner.contains(Point(xx, yy)):
                    cands.append((math.dist((xx, yy), at), sx(xx), sy(yy)))
        cands.sort()
        cx, cy = P.place([(a, b) for _, a, b in cands[:400]], w + 1.0, 6.0, weight=4)
        svg, _ = sym_badge(cx, cy, zid, color, label)
        g.append(svg)
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- path tags
    g = ['<g id="egress-tags">']
    for p in sorted(shown, key=lambda q: -q['length']):
        col = C_EGR if p['ok'] else C_EGR2
        lab = f"{p['id']} · {p['length']:.2f} m"
        w = tw(lab, 1.95) * 1.02 + 2.4
        x, y = sx(p['pts'][0][0]), sy(p['pts'][0][1])
        cx, cy = P.place(ring_offsets(x, y, w, 3.8, 1.4), w, 3.8, weight=5)
        g.append(f'<rect x="{f(cx - w/2)}" y="{f(cy - 1.9)}" width="{f(w)}" height="3.8" rx="1.9" fill="#ffffff" stroke="{col}" stroke-width="0.4"/>'
                 + text(cx, cy + 0.7, lab, 1.95, weight='800', fill=col, family=MONO))
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- device labels
    g = ['<g id="device-labels">']
    for (ax, ay, lines_, col, size, w0, h0) in labels:
        w = max(tw(t_, size) for t_ in lines_) + 1.4
        h = len(lines_) * size * 1.2 + 0.8
        cx, cy = P.place(ring_offsets(ax, ay, w, h, 2.2), w, h, weight=5)
        g.append(f'<rect x="{f(cx - w/2)}" y="{f(cy - h/2)}" width="{f(w)}" height="{f(h)}" fill="#ffffff" fill-opacity="0.9"/>')
        g.append(mtext(cx, cy, lines_, size, weight='700', fill=col, weights=['800'] + ['600'] * (len(lines_) - 1)))
    for line, col, lab in cov_labels:
        pts_ = [line.interpolate(t_, normalized=True) for t_ in (0.5, 0.35, 0.65, 0.2, 0.8)]
        w = tw(lab, 1.6) + 1.4
        cands = []
        for pp in pts_:
            X, Y = sx(pp.x), sy(pp.y)
            cands += [(X + w / 2 + 1, Y), (X - w / 2 - 1, Y), (X, Y - 2.4), (X, Y + 2.4)]
        cx, cy = P.place(cands, w, 2.8, weight=5)
        g.append(f'<rect x="{f(cx - w/2)}" y="{f(cy - 1.4)}" width="{f(w)}" height="2.8" fill="#ffffff" fill-opacity="0.9"/>'
                 + text(cx, cy + 0.55, lab, 1.6, weight='700', fill=col))
    g.append('</g>')
    s.add(''.join(g))

    # ---------------------------------------------------------------- callouts above the north wall (kitchen)
    hd1, hd2 = eq.get('HD-1'), eq.get('HD-2')
    sm = next((e for e in lay.get('equipment', []) if e.get('key') == 'smoker'), None)
    x0b, x1b = sx(0.25), sx(7.65)
    s.add(text(x0b, sy(-1.93), 'EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED', 2.0, anchor='start', weight='800', fill='#b35900'))
    wbox = (x1b - x0b - 3 * 1.6) / 4
    boxes = []
    if sm:
        boxes.append(('#6e2508', ['SOLID-FUEL SMOKER - LOCATION /', 'FLUE / FIRE CODE TO BE VALIDATED',
                                  f"{sm['id']} · EXT-3 chimenea propia listada", '(NFPA 211), sin unir a otros ductos.',
                                  'Leña S3: provisión de 1 día, ≥ 0.915 m', 'del fuego, fuera de la ruta de cenizas.'],
                      (sx((sm['rect'][0] + sm['rect'][2]) / 2), sy(sm['rect'][1]))))
    if gas:
        boxes.append(('#5a4300', ['GAS · RED DEL CENTRO COMERCIAL', 'Tipo y presión: VERIFY · sin cilindros.',
                                  'G acometida · VM corte manual accesible', 'VS solenoide enclavada a la supresión',
                                  'HD-1, rearme manual · detector de fugas', 'según tipo de gas · mangueras ≤ 1.5 m.'],
                      (sx(gas['main_valve'][0]), sy(gas['main_valve'][1]) - 1.2) if gas.get('main_valve') else None))
    if hd1:
        boxes.append(('#b35900', ['HD-1 · CAMPANA 1 · GAS (H2–H5)', 'Supresión química húmeda UL 300 /', 'NFPA 17A: campana, pleno, ducto y',
                                  'equipos. Disparo corta gas (VS) y', 'energía, rearme manual (NFPA 96 cap. 10).',
                                  'Disparo manual PM-1 · extintor EX-K.'],
                      (sx((hd1['rect'][0] + hd1['rect'][2]) / 2), sy(hd1['rect'][1]) + 1.0)))
    if hd2:
        boxes.append(('#b35900', ['HD-2 · CAMPANA 2 · SOLO PARRILLA H1', 'Comb. sólido: NFPA 96 cap. 14 (cap. 15', 'en ed. 2021/2024): campana, ducto,',
                                  'ventilador y descarga propios (EXT-2),', 'arrestachispas antes de filtros,', 'limpieza mensual.'],
                      (sx(hd2['rect'][2]) - 1.2, sy(hd2['rect'][1]) + 3.0)))
    for i, (col, lines_, tgt) in enumerate(boxes):
        bx = x0b + i * (wbox + 1.6)
        svg, h = callout(bx, sy(-1.78), wbox, lines_, col, tgt, size=1.7, lh=2.3)
        s.add(svg)

    # ---------------------------------------------------------------- callouts above the dining (PM-1, detection)
    pmc = next((c for c in checks if c['kind'] == 'PM'), None)
    x0c, x1c = sx(9.45), sx(15.95)
    wc = (x1c - x0c - 1.6) / 2
    cboxes = []
    if pm:
        lines_ = ['PM-1 · DISPARO MANUAL DE LA SUPRESIÓN HD-1', 'h 1.07–1.22 m, identificado, en la ruta de egreso',
                  '(NFPA 96 §10.5.1). 3–6 m de la campana: criterio IFC,']
        lines_.append('solo referencia (NFPA 96 no fija distancia).')
        if pmc:
            lines_.append(f"Medido: {pmc['length']:.2f} m a HD-1; {pmc['dist_to_egress_path']:.2f} m fuera de la ruta de")
            lines_.append(f"egreso de cocina; {pmc['walk_from_line']:.1f} m a pie desde la línea.")
            if not pmc['ok']:
                lines_.append('!→ Reubicar sobre la ruta (p. ej. junto a P-1, lado salón)')
                lines_.append('!  — a validar por el profesional / listado del sistema.')
        cboxes.append((C_FIRE, lines_, (sx(pm['at'][0]) + 1.9, sy(pm['at'][1]) + 1.9)))
    cboxes.append(('#1b1b1b', ['DETECCIÓN Y ALARMA (NFPA 72 · VERIFY)', f'H humo en salón y ala ({n_smoke}) · T térmico en',
                               f'cocina caliente / BBQ ({n_heat}): no usar detector de humo', 'junto a la línea. Integrar a la alarma del centro',
                               'comercial si existe; el disparo de la supresión HD-1', 'se señaliza en esa alarma (NFPA 96 / 72).',
                               'Rótulos y luces de emergencia: ver leyenda.'], None))
    for i, (col, lines_, tgt) in enumerate(cboxes):
        bx = x0c + i * (wc + 1.6)
        svg, h = callout(bx, sy(-1.78), wc, lines_, col, tgt, size=1.7, lh=2.3)
        s.add(svg)

    # ---------------------------------------------------------------- exit notes (outside the facade)
    ex1 = next((e for e in res['exits'] if e['counted']), None)
    if ex1 and main:
        got = _exit_segment(ex, lay, main)
        (x0, y0), (x1, y1) = got[0]
        xa = sx(max(x0, x1) + 0.5)
        yy = sy((y0 + y1) / 2)
        s.add(text(xa + 11.0, yy + 1.2, ex1['id'], 3.6, anchor='start', weight='800', fill=C_EGR, family=DISPLAY))
        s.add(mtext(xa, yy + 9.0, [f"{main.get('opening')} {ex1['width_m']:.2f} m · 2 hojas {ex1['leaf_m']:.2f}",
                                   f"{ex1['capacity_persons_5mm']} p (5 mm/p) ≥ {max(L['declared_capacity'], L['total_rounded_per_zone'])} p",
                                   'hojas hacia adentro (< 50 p)'], 1.6, anchor='start', weight='700', fill=C_EGR, weights=['800', '700', '600']))
        s.add(mtext(xa, yy + 16.0, ['→ pasillo peatonal abierto del', 'centro comercial (VERIFY)'], 1.55, anchor='start', fill='#333'))
        if cap_xy:
            lines_ = [f"CAPACIDAD MÁXIMA {ls.get('capacity_declared', 49)} PERSONAS", 'Rótulo junto a SAL-1 (clientes +',
                      'personal). Venta de alcohol (lic. C):', 'sin taburetes, zona de espera ni', 'eventos que suban la carga.']
            svg, h = callout(xa, cap_xy[1] + 6.0, SHEET_W - 165.0 - xa, lines_, C_EGR2, None, size=1.6, lh=2.2)
            s.add(svg)
            s.add(f'<polyline points="{f(xa)},{f(cap_xy[1] + 8.0)} {f(cap_xy[0] + 3.8)},{f(cap_xy[1] + 1.0)}" fill="none" stroke="{C_EGR2}" stroke-width="0.3"/>')
    ps1 = next((e for e in ls.get('exits', []) if e.get('conditional')), None)
    if ps1:
        got = _exit_segment(ex, lay, ps1)
        if got:
            (x0, y0), (x1, y1) = got[0]
            s.add(mtext(sx(-0.05), sy(max(y0, y1)) + 8.0, [f"{ps1['id']} · {ps1['opening']} CONDICIONAL", 'no se cuenta en el cálculo de egreso',
                                                          '(aprobación C.C. + revisión estructural)'],
                        1.7, anchor='start', weight='700', fill=C_EGR2, weights=['800', '600', '400']))

    # ---------------------------------------------------------------- egress table (free area east of the stair)
    tx0, ty0 = sx(8.75), sy(5.95)
    tx1, ty1 = sx(15.9), sy(12.25)
    X = tx0 + 3.0
    g = [f'<rect x="{f(tx0)}" y="{f(ty0)}" width="{f(tx1 - tx0)}" height="{f(ty1 - ty0)}" fill="#ffffff" stroke="#141210" stroke-width="0.35"/>']
    g.append(text(X, ty0 + 5.6, 'RECORRIDOS DE EGRESO MEDIDOS → SAL-1', 2.8, anchor='start', weight='800', extra='letter-spacing="0.3"'))
    g.append(text(X, ty0 + 9.6, f'Salida única: todo el recorrido es camino común. Límites NFPA 101 (mercantil < 50 p, sin rociadores): '
                                f'{LIM_COMMON:.2f} m / {LIM_TRAVEL:.2f} m.', 1.7, anchor='start', fill='#444'))
    cols = [(0, 'ID', 'start'), (8, 'Desde (punto más remoto de cada área)', 'start'), (82, 'Long. m', 'end'),
            (97, f'≤ {LIM_COMMON:.2f} m', 'end'), (111, f'≤ {LIM_TRAVEL:.2f} m', 'end'), (124, 'Margen', 'end'), (137, 'PS-1*', 'end')]
    rows, colors, weights = [], [], []
    for p in sorted(shown, key=lambda q: -q['length']):
        alt = res['alt_with_ps1'].get(p['id']) or {}
        name = p['name'] + (' ◄ más remoto' if crit and p is crit else '')
        rows.append([p['id'], name[:58], f"{p['length']:.2f}", 'CUMPLE' if p['ok_common_path'] else 'NO CUMPLE',
                     'CUMPLE' if p['ok_travel'] else 'NO CUMPLE', f"{p['margin_m']:+.2f}",
                     f"{alt['length']:.2f}" if alt.get('length') is not None else '—'])
        okc = C_EGR if p['ok_common_path'] else C_EGR2
        okt = C_EGR if p['ok_travel'] else C_EGR2
        colors.append([C_EGR if p['ok'] else C_EGR2, None, None, okc, okt, None, '#888'])
        weights.append(['800', '700' if p is crit else None, '800', '700', '700', None, None])
    tsvg, yy = table(X, ty0 + 12.0, cols, rows, size=1.95, rh=4.1, head_size=1.75,
                     families=[MONO, None, MONO, None, None, MONO, MONO], colors=colors, weights=weights)
    g.append(tsvg)
    yy += 3.4
    mth = [f'Método: camino más corto en grilla de {RES*100:.0f} cm sobre el espacio libre (muros, columnas, equipos, mesas, sillas ocupadas,',
           f'bancas), a {BODY:.2f} m de obstáculos (radio corporal), suavizado por visibilidad y medido hasta el plano de la puerta. NFPA 101',
           "7.6 mide por el eje del recorrido natural a 0.30 m de las esquinas: " + (
               f"con 0.30 m, {res['sensitivity_030']['path']} = {res['sensitivity_030']['length']:.2f} m "
               f"({'CUMPLE' if res['sensitivity_030']['ok'] else 'NO CUMPLE'}). " if res.get('sensitivity_030') else '')
           + 'Datos: data/life_safety_calcs.json.',
           '* Con PS-1 (SAL-2 condicional): solo informativo, NO se cuenta como salida.']
    for ln in mth:
        g.append(text(X, yy, ln, 1.6, anchor='start', fill='#444'))
        yy += 2.6
    # clear widths along egress (from the validator) + doors
    yy += 2.4
    g.append(text(X, yy, 'ANCHOS LIBRES EN LA RUTA DE EGRESO', 2.4, anchor='start', weight='800', extra='letter-spacing="0.2"'))
    g.append(text(X + 62, yy, '(cuello de botella medido · validation.json / A-103)', 1.65, anchor='start', fill='#555'))
    yy += 1.6
    pname = {'entrance': 'entrada', 'barra_front': 'frente de barra', 'pass_dining': 'pase (salón)', 'dining_far': 'fondo del salón',
             'kitchen_door': 'P-1', 'dish_drop': 'lavado', 'cold_storage': 'cold prep', 'line': 'línea caliente',
             'smoker_front': 'frente smoker', 'expo_pass': 'pase (cocina)', 'delivery_staging': 'recepción', 'service_door': 'PS-1',
             'fuel': 'leña'}
    MINW = 0.915
    wrows, wcol, wwt = [], [], []
    for c in ((val or {}).get('metrics', {}).get('connections') or []):
        if 'service_door' in (c['from'], c['to']) or 'fuel' in (c['from'], c['to']):
            continue
        w_ = float(c['bottleneck'])
        ok = w_ + 0.005 >= MINW
        tight = ok and w_ - MINW < 0.03
        wrows.append([f"{pname.get(c['from'], c['from'])} ↔ {pname.get(c['to'], c['to'])}", f"{w_:.2f}", f"≥ {MINW:.3f}",
                      'CUMPLE (VERIFY)' if tight else ('CUMPLE' if ok else 'NO CUMPLE')])
        wcol.append([None, None, '#666', C_EGR2 if not ok else ('#b35900' if tight else C_EGR)])
        wwt.append([None, '800', None, '700'])
    for o in lay.get('new_openings', []):
        if o.get('type') in ('double_acting_door', 'door') and not o.get('conditional'):
            wrows.append([f"{o.get('label', o['id'])} puerta de vaivén (hoja libre ≈ vano − 0.05 VERIFY)", f"{o.get('width', 0):.2f}", '≥ 0.810',
                          'CUMPLE (VERIFY)'])
            wcol.append([None, None, '#666', '#b35900'])
            wwt.append([None, '800', None, '700'])
    if ex1:
        wrows.append([f"SAL-1 {ex1['opening']} (2 hojas, libre por hoja VERIFY)", f"{ex1['width_m']:.2f}", '≥ 0.810 c/hoja', 'CUMPLE (VERIFY)'])
        wcol.append([None, None, '#666', '#b35900'])
        wwt.append([None, '800', None, '700'])
    cols = [(0, 'Tramo / componente', 'start'), (86, 'Ancho m', 'end'), (106, 'Mín. NFPA 101', 'end'), (137, 'Estado', 'end')]
    tsvg, yy = table(X, yy, cols, wrows, size=1.85, rh=3.8, head_size=1.7, families=[None, MONO, MONO, None], colors=wcol, weights=wwt)
    g.append(tsvg)
    yy += 3.0
    g.append(text(X, yy, 'Mín. 0.915 m para todo medio de egreso y 0.81 m libres por hoja de puerta (NFPA 101 7.3.4.1 / 7.2.1.2): margen de 5 mm en cocina,',
                  1.6, anchor='start', fill='#444'))
    g.append(text(X, yy + 2.6, 'sin tolerancia para equipos TBV — replantear con fichas técnicas (VERIFY ON SITE).', 1.6, anchor='start', fill='#444'))
    s.add(''.join(g))

    # ---------------------------------------------------------------- bottom band: occupant load + devices
    y0 = 321.0
    g = [text(12, y0 + 3, 'CARGA DE OCUPANTES · NFPA 101 Tabla 7.3.1.2 (verificar edición)', 2.7, anchor='start', weight='800',
              extra='letter-spacing="0.3"')]
    cols = [(0, 'Zona', 'start'), (46, 'Uso (factor según layout.life_safety)', 'start'), (126, 'Área m²', 'end'), (139, 'm²/p', 'end'),
            (143, 'Base', 'start'), (171, 'Cálculo', 'end'), (190, 'Ocup.', 'end')]
    rows, colors, weights = [], [], []
    for r in L['rows']:
        use = r['use'].replace(' (NFPA 101 Tabla 7.3.1.2)', '')
        rows.append([f"{r['zone']} · {r['name']}"[:28], use[:44], f"{r['area_m2']:.2f}", f"{r['factor_m2_per_person']:g}", r['basis'],
                     f"{r['raw']:.2f}", f"{r['occupants']}"])
        colors.append([zones.get(r['zone'], {}).get('color'), None, None, None, None, '#666', None])
        weights.append(['800', None, None, None, None, None, '800'])
    tot = L['total_rounded_per_zone']
    over = tot >= THRESHOLD or tot > L['declared_capacity']
    rows.append(['TOTAL CALCULADO', 'redondeo hacia arriba por zona', f"{sum(r['area_m2'] for r in L['rows']):.2f}", '', '',
                 f"{L['total_unrounded']:.2f}", f"{tot}"])
    colors.append([C_EGR2 if over else C_EGR, None, None, None, None, '#666', C_EGR2 if over else C_EGR])
    weights.append(['800', '700', '700', None, None, None, '800'])
    rows.append(['CAPACIDAD DECLARADA', 'máxima, rotulada en SAL-1 (clientes + personal)', '', '', '', '', f"{L['declared_capacity']}"])
    colors.append([None, None, None, None, None, None, C_EGR2 if over else C_EGR])
    weights.append(['800', None, None, None, None, None, '800'])
    rows.append(['UMBRAL', 'NFPA 101 6.1.2.1: reunión pública con ≥ 50 personas', '', '', '', '', f'≥ {THRESHOLD}'])
    colors.append([None] * 7)
    weights.append(['800', None, None, None, None, None, '800'])
    tsvg, yy = table(12, y0 + 5.5, cols, rows, size=1.95, rh=4.1, head_size=1.75, families=[None, None, MONO, MONO, None, MONO, MONO],
                     colors=colors, weights=weights)
    g.append(tsvg)
    yy += 3.2
    sc = L.get('scenario_bar_as_staff_area') or {}
    notes = []
    if over:
        notes.append(f"!Calculada {tot} (redondeo por zona) ≥ umbral {THRESHOLD} y > declarada {L['declared_capacity']}: la salida única, la puerta")
        notes.append('!hacia adentro y la ausencia de rociadores dependen de < 50 → a validar por el profesional responsable:')
    notes.append(f"· redondeo por uso: {L['total_rounded_per_use']} p · sin redondeo: {L['total_unrounded']:.1f} p"
                 + (f" · barra C como área de trabajo del personal (9.3 m²/p): {sc.get('total_rounded_per_zone')} p" if sc else ''))
    notes.append('· población prevista: asientos del salón + personal de turno ≤ capacidad declarada (sin taburetes ni zona de espera).')
    for ln in notes:
        red = ln.startswith('!')
        g.append(text(12, yy, ln[1:] if red else ln, 1.75, anchor='start', weight='700' if red else '400', fill=C_EGR2 if red else '#333'))
        yy += 2.8
    s.add(''.join(g))

    x2 = 210.0
    g = [text(x2, y0 + 3, 'EXTINTORES Y DISPARO MANUAL · recorridos medidos sobre la planta', 2.7, anchor='start', weight='800',
              extra='letter-spacing="0.3"')]
    crit_short = {'K': f'Clase K ≤ {LIM_K:.2f} m (NFPA 10 §6.6 / NFPA 96)',
                  'SF': f'2-A agua o K 6 L ≤ {LIM_SOLID:.0f} m (NFPA 96 comb. sólido)',
                  'B': f'10-B ≤ {LIM_B:.2f} m (NFPA 10 §6.3.1)',
                  'A': f'2-A ≤ {LIM_A:.1f} m (NFPA 10 Tabla 6.2.1.1)',
                  'PM': 'En ruta de egreso, h 1.07–1.22 (NFPA 96 §10.5.1)'}
    cols = [(0, 'Riesgo protegido', 'start'), (56, 'Equipo', 'start'), (96, 'Medido m', 'end'), (110, 'Límite', 'end'),
            (114, 'Criterio (verificar edición)', 'start'), (220, 'Estado', 'end')]
    rows, colors, weights = [], [], []
    for c in checks:
        if c['kind'] == 'PM':
            med, lim = f"{c['length']:.2f}", '3–6*'
            st = 'VERIFICAR' if not c['ok'] else 'CUMPLE'
        else:
            med, lim = f"{c['length']:.2f}", f"{c['limit']:.2f}"
            st = 'CUMPLE' if c['ok'] else 'NO CUMPLE'
        rows.append([c['hazard'][:34], c['device'][:22], med, lim, crit_short.get(c['kind'], '')[:58], st])
        stc = C_EGR if st == 'CUMPLE' else C_EGR2
        colors.append([None, C_FIRE, None, '#666', '#444', stc])
        weights.append(['700', '800', '800', None, None, '800'])
    tsvg, yy = table(x2, y0 + 5.5, cols, rows, size=1.9, rh=4.0, head_size=1.75, families=[None, None, MONO, MONO, None, None],
                     colors=colors, weights=weights)
    g.append(tsvg)
    yy += 3.2
    foot = ['Solo K 6 L o 2-A tipo AGUA protegen combustible sólido (NFPA 96): un ABC de polvo no califica → EX-K cubre freidoras, parrilla, smoker y',
            'leña; EX-A cubren clase A/B. Montaje: parte superior ≤ 1.53 m y inferior ≥ 0.10 m del piso, visibles y señalizados (NFPA 10).',
            'Rótulo junto a EX-K: "accionar primero el sistema fijo". * 3–6 m de la campana: criterio IFC de referencia (NFPA 96 no fija distancia).']
    for ln in foot:
        g.append(text(x2, yy, ln, 1.65, anchor='start', fill='#444'))
        yy += 2.7
    s.add(''.join(g))

    # ---------------------------------------------------------------- side panel
    def sw_sym(fn):
        return lambda x, y: fn(x + 5, y + 1.7)

    def sw_path(x, y):
        return (f'<line x1="{x}" y1="{y+1.7}" x2="{x+9.2}" y2="{y+1.7}" stroke="{C_EGR}" stroke-width="0.55" marker-end="url(#arr-egr)"/>')

    def sw_crit(x, y):
        return (f'<line x1="{x+0.5}" y1="{y+1.7}" x2="{x+9.5}" y2="{y+1.7}" stroke="{C_EGR}" stroke-opacity="0.22" stroke-width="2.8" stroke-linecap="round"/>'
                f'<line x1="{x+0.5}" y1="{y+1.7}" x2="{x+9.5}" y2="{y+1.7}" stroke="{C_EGR}" stroke-width="0.55"/>')

    def sw_origin(x, y):
        return (f'<circle cx="{x+2}" cy="{y+1.7}" r="1.25" fill="#fff" stroke="{C_EGR}" stroke-width="0.5"/><circle cx="{x+2}" cy="{y+1.7}" r="0.5" fill="{C_EGR}"/>'
                f'<rect x="{x+4.2}" y="{y+0.2}" width="5.8" height="3.0" rx="1.5" fill="#fff" stroke="{C_EGR}" stroke-width="0.35"/>')

    def sw_exit(x, y):
        return (f'<polygon points="{x},{y+1.1} {x+6},{y+1.1} {x+6},{y} {x+9.5},{y+1.7} {x+6},{y+3.4} {x+6},{y+2.3} {x},{y+2.3}" fill="{C_EGR}"/>')

    def sw_cov(x, y):
        return (f'<line x1="{x}" y1="{y+0.9}" x2="{x+10}" y2="{y+0.9}" stroke="#7a1fa2" stroke-width="0.4" stroke-dasharray="2.4 1.2"/>'
                f'<line x1="{x}" y1="{y+2.6}" x2="{x+10}" y2="{y+2.6}" stroke="#c2410c" stroke-width="0.4" stroke-dasharray="2.4 1.2"/>')

    def sw_det2(x, y):
        return sym_det(x + 2.2, y + 1.7, 'H') + sym_det(x + 7.4, y + 1.7, 'T')

    def sw_valves(x, y):
        return sym_gas_entry(x + 1.9, y + 1.7) + sym_valve(x + 6.9, y + 1.9)

    def sw_badge(x, y):
        return (f'<rect x="{x}" y="{y-0.3}" width="10" height="4.0" rx="2" fill="#fff" stroke="#2e9a3a" stroke-width="0.4"/>'
                f'<circle cx="{x+2}" cy="{y+1.7}" r="1.6" fill="#2e9a3a"/>' + text(x + 2, y + 2.35, 'D', 1.7, weight='800', fill='#fff')
                + text(x + 4.3, y + 2.35, '37 p', 1.6, anchor='start', weight='800', fill='#2e9a3a', family=MONO))

    def sw_hood(x, y):
        return (f'<rect x="{x}" y="{y}" width="4.6" height="3.4" fill="none" stroke="#b35900" stroke-width="0.5" stroke-dasharray="1.6 0.7"/>'
                f'<line x1="{x+5.6}" y1="{y+1.7}" x2="{x+10}" y2="{y+1.7}" stroke="#6e2508" stroke-width="0.9" stroke-dasharray="1.6 0.8"/>')

    legend = [LEGEND_WALLS[0], LEGEND_WALLS[2], LEGEND_WALLS[3],
              (sw_rect('#fbd9b6', '#c46a1a'), 'Equipo de riesgo: fuego / combustible sólido'),
              (sw_hood, 'Campana HD (proyección) · chimenea smoker EXT-3'),
              (sw_badge, 'Zona · ocupantes calculados (tabla inferior)'),
              (sw_path, 'Recorrido de egreso medido (hasta SAL-1)'),
              (sw_crit, 'Recorrido más largo (crítico)'),
              (sw_origin, 'Origen + longitud del recorrido (m)'),
              (sw_exit, 'SALIDA SAL-1 · (contorno rojo = condicional)'),
              (sw_sym(lambda cx, cy: sym_exit_sign(cx, cy, 'E')), 'Rótulo SALIDA iluminado / direccional (RS)'),
              (sw_sym(sym_em_light), 'Luz de emergencia (LE) · 1.5 h'),
              (sw_sym(lambda cx, cy: sym_ext(cx, cy, 'K')), 'Extintor clase K 6 L (EX-K)'),
              (sw_sym(lambda cx, cy: sym_ext(cx, cy, 'ABC')), 'Extintor ABC 2-A:10-B:C (EX-A)'),
              (sw_cov, 'Radio 9.15 m (K) / 6 m (comb. sólido) desde EX-K'),
              (sw_sym(sym_pull), 'Disparo manual supresión HD-1 (PM)'),
              (sw_det2, 'Detector de humo (H) / térmico (T)'),
              (sw_valves, 'Acometida gas (G) · válvula de corte manual (VM)'),
              (sw_sym(lambda cx, cy: sym_valve(cx, cy + 0.8, True)), 'Válvula solenoide (VS) enclavada a HD-1'),
              (sw_sym(sym_capacity), 'Rótulo CAPACIDAD MÁXIMA 49 PERSONAS')]
    far = crit['length'] if crit else 0
    tot = L['total_rounded_per_zone']
    load_bad = tot >= THRESHOLD or tot > L['declared_capacity']
    pm_bad = any(c['kind'] == 'PM' and not c['ok'] for c in checks)
    summary = [
        ('Clasificación pretendida', 'Mercantil < 50 p (Clase C)', None),
        ('Capacidad declarada / calculada', f"{L['declared_capacity']} / {tot} p", C_EGR2 if load_bad else C_EGR),
        ('Salidas contadas', f"{sum(1 for e in res['exits'] if e['counted'])} (SAL-1) + SAL-2 cond.", None),
        ('Recorrido más largo medido', f"{far:.2f} m ≤ {LIM_COMMON:.2f} m", C_EGR if crit and crit['ok'] else C_EGR2),
        ('Capacidad SAL-1 (5 mm/p)', f"{ex1['capacity_persons_5mm'] if ex1 else '—'} p", C_EGR),
        ('Rótulos SALIDA / luces de emergencia', f"{len(ls.get('exit_signs', []))} / {len(ls.get('emergency_lights', []))}", None),
        ('Extintores K / ABC', f"{len(kx)} / {len(exts) - len(kx)}", None),
        ('Detectores humo / térmicos', f"{n_smoke} / {n_heat}", None),
        ('Disparo manual PM-1 en ruta de egreso', 'VERIFICAR' if pm_bad else 'CUMPLE', C_EGR2 if pm_bad else C_EGR),
    ]
    y = s.side_panel([('h', 'Leyenda'), ('legend', legend), ('h', 'Resumen (medido en planta)')])
    g = []
    for a_, b_, c_ in summary:
        g.append(text(441, y + 2.6, a_, 2.0, anchor='start', fill='#333'))
        g.append(text(SHEET_W - 11, y + 2.6, b_, 2.0, anchor='end', weight='700', family=MONO, fill=c_ or '#1b1b1b'))
        g.append(f'<line x1="441" y1="{f(y + 3.8)}" x2="{SHEET_W - 10}" y2="{f(y + 3.8)}" stroke="#e1ddd6" stroke-width="0.2"/>')
        y += 4.3
    s.add(''.join(g))
    y += 1.4
    notes = [
        '!ANTEPROYECTO: a validar por el profesional responsable (CFIA) y Bomberos.',
        '!Citas tomadas de resúmenes, no de textos primarios: verificar edición y numeración.',
        'RNPCI 2023 (Bomberos, Sesión 0214 del 24-03-2023) adopta las normas NFPA;',
        'edición exigible a confirmar en SCIJ / Bomberos. Trámite por APC (CFIA).',
        'NFPA 101 6.1.2.1 / A.6.1.2.1: restaurante < 50 p = mercantil (cap. 36);',
        '≥ 50 p = reunión pública (cap. 12). Carga: NFPA 101 7.3.1 / Tabla 7.3.1.2.',
        'NFPA 101 36.2.4 / 36.2.5.3 / 36.2.6: salida única con recorrido ≤ 23 m sin',
        'rociadores; recorrido ≤ 46 m. Medición del recorrido: NFPA 101 7.6.',
        'NFPA 101 7.10 rótulos de salida iluminados; direccionales donde la salida no',
        'es visible. 7.9 iluminación de emergencia: 1.5 h; 10.8 lx prom. y 1.1 lx mín.',
        'iniciales; 40:1 máx./mín. Rótulos alimentados por el sistema de emergencia.',
        'NFPA 10: extintores visibles y señalizados; clase K con rótulo de uso.',
        'NFPA 96 cap. 10 + NFPA 17A: supresión UL 300, corte de gas y energía con',
        'rearme manual; HD-2 y EXT-3 independientes (cap. 14 / 15, comb. sólido).',
        'NFPA 72: detección / alarma integrada al centro comercial si existe.',
        'Gas: red del C.C. (NFPA 54 / 58 y disposiciones de Bomberos) — VERIFY.',
        'SS.HH.: comunes del C.C., fuera del local (≤ 36 m + autorización: VERIFY).',
    ]
    y = s.side_panel([('h', 'Normativa y criterios'), ('para', notes)], y=y)
    big = ['Segunda salida independiente desde el salón (PS-1 no sirve: pasa por cocina).',
           'Puertas con giro hacia afuera; herraje antipánico (≥ 100 p; ≥ 50 p en ed. 2027).',
           'Rociadores automáticos supervisados (NFPA 101 12.3.5, restaurante nuevo).',
           'Pasillos de mesas ≥ 1.12 m y rótulo de capacidad obligatorio (12.7.9.3).']
    verify = ['Altura libre de cielo (3.00 m supuesta) · ruta de ductos y chimenea.',
              'Ancho libre real de hojas D-ENT y P-1 · giro y cerrajería de D-ENT.',
              'Pasillo abierto del C.C. = descarga al exterior · plan de evacuación del C.C.',
              'Rociadores / alarma existentes en el C.C. · tipo y presión del gas.']
    s.side_panel([('h', 'Si la carga llega a 50 o más'), ('para', big), ('h', 'Verificar en sitio (VERIFY ON SITE)'), ('para', verify)], y=y)
    return s.render()


def sheets(ex, lay, val):
    res = compute(ex, lay, val)
    try:
        with open(os.path.join(ROOT, 'data', 'life_safety_calcs.json'), 'w') as fh:
            json.dump(calcs_json(res, lay), fh, indent=1, ensure_ascii=False)
    except OSError as err:  # read-only checkout: the sheet still renders
        print('WARNING: life_safety_calcs.json not written:', err)
    svg = build_sheet(ex, lay, val, res)
    return [{'id': 'A104', 'file': 'lava_A104_seguridad.svg', 'title': 'Seguridad humana y protección contra incendios',
             'order': 104, 'svg': svg}]


if __name__ == '__main__':
    _ex = load_existing()
    _lay = load_json(os.path.join(ROOT, 'data', 'layout.json'))
    _vp = os.path.join(ROOT, 'data', 'validation.json')
    _val = load_json(_vp) if os.path.exists(_vp) else None
    _res = compute(_ex, _lay, _val)
    _out = calcs_json(_res, _lay)
    with open(os.path.join(ROOT, 'data', 'life_safety_calcs.json'), 'w') as _fh:
        json.dump(_out, _fh, indent=1, ensure_ascii=False)
    for _p in _out['egress_paths']:
        print(f"{_p['id']:<3} {_p['length_m']:6.2f} m  ok={_p['ok']}  {_p['from']}")
    print('carga:', _out['occupant_load']['total_rounded_per_zone'], 'declarada:', _out['occupant_load']['declared_capacity'])
