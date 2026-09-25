"""A-105 · Accesibilidad (Ley 7600 / DE 26831-MP) — ANTEPROYECTO, a validar por el profesional responsable.

Everything is derived from data/existing.json + data/layout.json:
  * accessible route  D-ENT -> caja C4 -> accessible tables (tables[].accessible) -> salida;
  * clear widths measured geometrically (shapely) on the free floor (premises - walls - columns - equipment - furniture);
  * Ø1.50 turning circles drawn ONLY where a free disk fits (erosion of the free floor by 0.75 m);
  * 0.80 x 1.20 approach spaces (the chair on the aisle side is removed; a neighbour chair is slid if needed);
  * walking distance (grid Dijkstra) from the farthest seat / farthest work point to D-ENT -> budget left for the
    mall's common restrooms (<= 36 m, INVU — verificar);
  * details at 1:20 in the free band: caja C4 elevation, accessible table plan + section, threshold at D-ENT.
"""
import itertools
import math

import numpy as np
import shapely
from shapely.affinity import translate
from shapely.geometry import LineString, Point, box
from shapely.ops import nearest_points, unary_union

from lavageo import R, door_swing_poly, item_lists, new_openings_geom, premises, seat_points, standing_existing_walls
from plan_svg import COL, LEGEND_WALLS, MONO, S, Sheet, f, mtext, poly_el, rect_el, sw_line, sx, sy, text, tw

ACC = '#0b4f8a'        # accessibility blue (same as the accessible tables on A-101)
ACC_L = '#dce9f7'
OKC, WARN, BAD = '#2b7a31', '#a35c00', '#b00020'
EGR = '#2e7d32'

REQ_GEN, REQ_INT, REQ_DOOR = 1.20, 0.90, 0.90   # DE 26831-MP arts. 141 / 140 (verificar)
APP_W, APP_L = 0.80, 1.20                       # approach space (referencia)
TURN_R = 0.75                                   # Ø1.50
KNEE = 0.45        # part of the approach that may sit under the table top (referencia internacional, no norma CR)
LEAF_LOSS = 0.06   # estimate: leaf thickness + stop, subtracted from nominal leaf width
MAX_WC = 36.0      # INVU — recorrido máximo al servicio sanitario (verificar)
D20 = 50.0         # 1:20 -> 1 m = 50 mm


# ----------------------------------------------------------------------------------------------- geometry
def _obstacles(ex, lay, skip=(), add=()):
    obs = [g for _, g in standing_existing_walls(ex, lay)]
    obs += [R(c['rect']) for c in ex['columns']]
    ops = new_openings_geom(lay)
    for w in lay.get('new_walls', []):
        g = R(w['rect'])
        for o in ops:
            g = g.difference(o.buffer(0.001))
        obs.append(g)
    for _, it, g in item_lists(lay):
        if it.get('id') in skip:
            continue
        obs.append(g)
    obs += list(add)
    return unary_union(obs)


def _free(ex, lay, skip=(), add=()):
    return premises(ex).difference(_obstacles(ex, lay, skip, add))


def _xsec(free, p, axis):
    """Clear width through point p along 'x' or 'y' (segment of the free floor that contains p)."""
    x, y = p
    ln = LineString([(x - 40, y), (x + 40, y)]) if axis == 'x' else LineString([(x, y - 40), (x, y + 40)])
    inter = ln.intersection(free)
    P = Point(p)
    for seg in getattr(inter, 'geoms', [inter]):
        if seg.geom_type == 'LineString' and seg.distance(P) < 1e-6:
            return seg.length, seg
    return 0.0, None


def _median_min(samples, tol=0.005):
    """(min width, location, segment) with the location in the middle of the run of near-minimum samples."""
    if not samples:
        return None, None, None
    wmin = min(v[0] for v in samples)
    near = [v for v in samples if v[0] <= wmin + tol]
    w, loc, seg = near[len(near) // 2]
    return wmin, loc, seg


def _connected(free, a, b, w):
    er = free.buffer(-w / 2)
    A, B = Point(a), Point(b)
    for g in getattr(er, 'geoms', [er]):
        gb = g.buffer(1e-6)
        if gb.contains(A) and gb.contains(B):
            return True
    return False


def _bottleneck(free, a, b, hi=2.0, it=15):
    lo = 0.0
    for _ in range(it):
        m = (lo + hi) / 2
        if _connected(free, a, b, m):
            lo = m
        else:
            hi = m
    return lo


def _approach_options(lay, t):
    """Candidate 0.80 x 1.20 approach spaces of table t: one per aisle-side chair (that chair is removed)."""
    tg = R(t['rect'])
    x0, y0, x1, y1 = tg.bounds
    own = [c for c in lay.get('chairs', []) if c.get('table') == t['id']]
    opts = []
    for c in own:
        cg = R(c['rect'])
        fc = c.get('facing')
        horiz = fc in ('N', 'S')
        a0, a1 = (x0, x1) if horiz else (y0, y1)
        cc = cg.centroid.x if horiz else cg.centroid.y
        lo, hi = a0 + APP_W / 2, a1 - APP_W / 2
        cc = (a0 + a1) / 2 if lo > hi else min(max(cc, lo), hi)
        if fc == 'N':
            ap, under = box(cc - APP_W / 2, y1, cc + APP_W / 2, y1 + APP_L), 'N'
        elif fc == 'S':
            ap, under = box(cc - APP_W / 2, y0 - APP_L, cc + APP_W / 2, y0), 'S'
        elif fc == 'W':
            ap, under = box(x0 - APP_L, cc - APP_W / 2, x0, cc + APP_W / 2), 'W'
        else:
            ap, under = box(x1, cc - APP_W / 2, x1 + APP_L, cc + APP_W / 2), 'E'
        moves = []
        for c2 in own:
            if c2 is c:
                continue
            g2 = R(c2['rect'])
            if g2.intersection(ap).area <= 1e-6:
                continue
            if horiz:
                d = (ap.bounds[2] - g2.bounds[0]) if g2.centroid.x >= cc else -(g2.bounds[2] - ap.bounds[0])
                moves.append((c2, d, translate(g2, d, 0)))
            else:
                d = (ap.bounds[3] - g2.bounds[1]) if g2.centroid.y >= cc else -(g2.bounds[3] - ap.bounds[1])
                moves.append((c2, d, translate(g2, 0, d)))
        opts.append({'table': t, 'chair': c, 'app': ap, 'moves': moves, 'toward_table': under})
    return opts


def _shrink(app, toward, k):
    """Approach rect with k metres of it slid under the table (toward = side where the table is)."""
    x0, y0, x1, y1 = app.bounds
    if toward == 'N':      # chair faces N -> table is north -> table edge is y0
        return box(x0, y0, x1, y1 - k)
    if toward == 'S':
        return box(x0, y0 + k, x1, y1)
    if toward == 'W':
        return box(x0 + k, y0, x1, y1)
    return box(x0, y0, x1 - k, y1)


def _config_free(ex, lay, combo, knee=None):
    skip = {o['chair']['id'] for o in combo} | {m[0]['id'] for o in combo for m in o['moves']}
    add = [m[2] for o in combo for m in o['moves']]
    if knee is not None:
        add += [_shrink(o['app'], o['toward_table'], knee) for o in combo]
    return _free(ex, lay, skip=skip, add=add)


def _geodesic(free, src, step=0.1, clear=0.25):
    """Grid Dijkstra (8-neighbour, no corner cutting) on the free floor eroded by a 0.50 m wide walker."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    walk = free.buffer(-clear)
    bx0, by0, bx1, by1 = free.bounds
    xs = np.arange(bx0 + step / 2, bx1, step)
    ys = np.arange(by0 + step / 2, by1, step)
    X, Y = np.meshgrid(xs, ys)
    ins = shapely.contains_xy(walk, X, Y)
    idx = -np.ones(X.shape, dtype=int)
    idx[ins] = np.arange(int(ins.sum()))
    H, W = ins.shape
    rows, cols, wts = [], [], []

    def link(a, b, cost):
        m = ins[a] & ins[b]
        rows.append(idx[a][m])
        cols.append(idx[b][m])
        wts.append(np.full(int(m.sum()), cost))
    link((slice(None), slice(0, W - 1)), (slice(None), slice(1, W)), step)
    link((slice(0, H - 1), slice(None)), (slice(1, H), slice(None)), step)
    d = step * math.sqrt(2)
    # diagonals only when both orthogonal neighbours are free (no corner cutting)
    for (a, b, o1, o2) in (((slice(0, H - 1), slice(0, W - 1)), (slice(1, H), slice(1, W)),
                            (slice(0, H - 1), slice(1, W)), (slice(1, H), slice(0, W - 1))),
                           ((slice(0, H - 1), slice(1, W)), (slice(1, H), slice(0, W - 1)),
                            (slice(0, H - 1), slice(0, W - 1)), (slice(1, H), slice(1, W)))):
        m = ins[a] & ins[b] & ins[o1] & ins[o2]
        rows.append(idx[a][m])
        cols.append(idx[b][m])
        wts.append(np.full(int(m.sum()), d))
    n = int(ins.sum())
    G = coo_matrix((np.concatenate(wts), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    px, py = X[ins], Y[ins]

    def node(p):
        return int(np.argmin((px - p[0]) ** 2 + (py - p[1]) ** 2))
    dist = dijkstra(G, directed=False, indices=node(src))
    return dist, px, py, node


def analyse(ex, lay):
    """All measurements used on the sheet (also handy for reports)."""
    A = {}
    prem = premises(ex)
    free = _free(ex, lay)
    A['free'] = free
    zones = {z['id']: z for z in lay.get('zones', [])}
    from shapely.geometry import Polygon
    dining = Polygon(zones['D']['poly']) if 'D' in zones else prem
    public = unary_union([Polygon(zones[k]['poly']) for k in ('C', 'D') if k in zones]) if zones else prem

    # ---- main aisle (between the two rows of chairs of the dining room)
    ch_in = [c for c in lay.get('chairs', []) if dining.contains(R(c['rect']).centroid)]
    north = [R(c['rect']).bounds[3] for c in ch_in if c.get('facing') == 'N']
    south = [R(c['rect']).bounds[1] for c in ch_in if c.get('facing') == 'S']
    y_mid = (max(north) + min(south)) / 2 if north and south else 2.55
    tabs_d = [R(t['rect']) for t in lay.get('tables', []) if dining.contains(R(t['rect']).centroid)]
    ax0 = min(t.bounds[0] for t in tabs_d)
    ax1 = max(t.bounds[2] for t in tabs_d)
    samp = []
    for xx in np.arange(ax0, ax1 + 1e-9, 0.01):
        w, seg = _xsec(free, (float(xx), y_mid), 'y')
        if seg is not None:
            samp.append((w, float(xx), seg))
    A['y_mid'], A['aisle_x'] = y_mid, (ax0, ax1)
    A['w_main'], A['w_main_x'], A['w_main_seg'] = _median_min(samp)

    # ---- caja (accessible counter)
    caja = next((e for e in lay['equipment'] if e.get('key') == 'caja'), None)
    A['caja'] = caja
    cg = R(caja['rect'])
    cx0, cy0, cx1, cy1 = cg.bounds
    fr = caja.get('front', 'E')
    cc = ((cy0 + cy1) / 2) if fr in ('E', 'W') else ((cx0 + cx1) / 2)
    if fr == 'E':
        app_c = box(cx1, cc - APP_W / 2, cx1 + APP_L, cc + APP_W / 2)
        A['w_caja'], A['w_caja_seg'] = _xsec(free, (cx1 + 0.01, cc), 'x')
    elif fr == 'W':
        app_c = box(cx0 - APP_L, cc - APP_W / 2, cx0, cc + APP_W / 2)
        A['w_caja'], A['w_caja_seg'] = _xsec(free, (cx0 - 0.01, cc), 'x')
    elif fr == 'S':
        app_c = box(cc - APP_W / 2, cy1, cc + APP_W / 2, cy1 + APP_L)
        A['w_caja'], A['w_caja_seg'] = _xsec(free, (cc, cy1 + 0.01), 'y')
    else:
        app_c = box(cc - APP_W / 2, cy0 - APP_L, cc + APP_W / 2, cy0)
        A['w_caja'], A['w_caja_seg'] = _xsec(free, (cc, cy0 - 0.01), 'y')
    A['app_caja'] = app_c
    A['app_caja_clash'] = app_c.intersection(_obstacles(ex, lay)).area
    A['caja_h'] = float(caja.get('h', 0.8))
    A['caja_len'] = (cy1 - cy0) if fr in ('E', 'W') else (cx1 - cx0)

    # ---- staff passage between the kitchen/dining partition and the bar
    nw = next((w for w in lay.get('new_walls', []) if w.get('role') == 'kitchen_dining_partition'), None)
    bar = [R(e['rect']) for e in lay['equipment'] if e.get('cat') == 'bar' and not e.get('stack_with') and not e.get('overhead')]
    A['w_bar'] = None
    A['bar_niche'] = None
    if nw and bar:
        bu = unary_union(bar)
        nx1 = max(nw['rect'][0], nw['rect'][2])
        xm = (nx1 + bu.bounds[0]) / 2
        # fixtures standing in the passage at its dead end (e.g. the bar hand-wash C5 against the partition): the
        # through-passage is measured beside them; the niche in front of them is reported apart (single-user spot)
        strip = box(nx1, bu.bounds[1], bu.bounds[0], bu.bounds[3])
        niche = [e for e in lay['equipment'] if e.get('cat') != 'bar' and not e.get('overhead') and not e.get('stack_with')
                 and R(e['rect']).intersection(strip).area > 1e-4
                 and min(R(e['rect']).bounds[1] - bu.bounds[1], bu.bounds[3] - R(e['rect']).bounds[3]) < 0.05]
        y_lo, y_hi = bu.bounds[1] + 0.05, bu.bounds[3] - 0.05
        for e in niche:
            gy0, gy1 = R(e['rect']).bounds[1], R(e['rect']).bounds[3]
            if gy0 - bu.bounds[1] < 0.05:
                y_lo = max(y_lo, gy1 + 0.02)
            else:
                y_hi = min(y_hi, gy0 - 0.02)
        samp = []
        for yy in np.arange(y_lo, y_hi + 1e-9, 0.01):
            w, seg = _xsec(free, (xm, float(yy)), 'x')
            if seg is not None:
                samp.append((w, float(yy), seg))
        A['w_bar'], A['w_bar_y'], A['w_bar_seg'] = _median_min(samp)
        if niche:
            e = niche[0]
            gy = (R(e['rect']).bounds[1] + R(e['rect']).bounds[3]) / 2
            w, seg = _xsec(free, (xm, gy), 'x')
            if seg is not None:
                A['bar_niche'] = {'id': e['id'], 'label': e.get('plan_label') or e.get('label', ''), 'w': w, 'seg': seg, 'y': gy}

    # ---- accessible tables: choose the approach chairs that keep the aisle widest
    acc = [t for t in lay.get('tables', []) if t.get('accessible')]
    entr = lay.get('points', {}).get('entrance', [prem.bounds[2] - 0.4, 2.6])
    A['entrance'] = entr
    # route end points: a deep point in front of the caja (>= 0.75 from obstacles when possible) and a point
    # OUTSIDE the D-ENT opening (the free floor is extended through the door), so the ends never limit the width
    feas0 = free.buffer(-TURN_R - 0.003)
    a_pt = app_c.centroid.coords[0]
    if not feas0.is_empty:
        q = nearest_points(feas0, Point(a_pt))[0]
        if q.distance(Point(a_pt)) < 1.0:
            a_pt = (q.x, q.y)
    dent = next((d for d in ex.get('doors', []) if d['id'] == 'D-ENT'), None)
    if dent:
        xo, ya, _, yb = dent['opening']
        ya, yb = min(ya, yb), max(ya, yb)
    else:
        xo, ya, yb = prem.bounds[2], entr[1] - 1.0, entr[1] + 1.0
    door_ext = box(prem.bounds[2] - 0.02, ya, prem.bounds[2] + 3.0, yb)
    b_pt = (prem.bounds[2] + 1.6, (ya + yb) / 2)
    A['route_ends'] = (a_pt, b_pt)
    A['door_ext'] = door_ext
    opts = [_approach_options(lay, t) for t in acc]
    best_combo, best_w, best_shift = None, -1, 9.0
    for combo in itertools.product(*opts):
        fr_ = _config_free(ex, lay, combo, knee=KNEE).union(door_ext)
        w = _bottleneck(fr_, a_pt, b_pt, hi=1.6, it=12)
        shift = sum(abs(m[1]) for o in combo for m in o['moves'])
        if w > best_w + 1e-3 or (abs(w - best_w) <= 1e-3 and shift < best_shift):
            best_combo, best_w, best_shift = combo, w, shift
    A['acc'] = list(best_combo) if best_combo else []
    fr0 = _config_free(ex, lay, A['acc'])                   # chairs removed / slid, nobody seated
    A['free_cfg'] = fr0
    A['bn_route'] = _bottleneck(free.union(door_ext), a_pt, b_pt)      # as drawn on A-101 (chairs in place)
    res = {}
    for o in A['acc']:
        for k in (0.0, KNEE):
            res[(o['table']['id'], k)] = _bottleneck(_config_free(ex, lay, [o], knee=k).union(door_ext), a_pt, b_pt)
    for k in (0.0, KNEE):
        res[('ALL', k)] = _bottleneck(_config_free(ex, lay, A['acc'], knee=k).union(door_ext), a_pt, b_pt)
    A['residual'] = res
    # alternative designation if two accessible positions used together pinch the aisle below 0.90
    A['alt'] = None
    if len(acc) >= 2 and res[('ALL', KNEE)] < REQ_INT:
        keep = acc[0]
        repl = acc[-1]
        rf = {c.get('facing') for c in lay['chairs'] if c.get('table') == repl['id']}
        cands = []
        for t in lay.get('tables', []):
            if t.get('accessible') or t['id'] == repl['id']:
                continue
            if not ({c.get('facing') for c in lay['chairs'] if c.get('table') == t['id']} & rf):
                continue
            ok = None
            for combo in itertools.product(_approach_options(lay, keep), _approach_options(lay, t)):
                if _connected(_config_free(ex, lay, combo, knee=KNEE).union(door_ext), a_pt, b_pt, REQ_INT):
                    ok = combo
                    break
            if ok:
                cands.append((R(t['rect']).centroid.distance(R(repl['rect']).centroid), t['id']))
        cands.sort()
        A['alt'] = (repl['id'], [c[1] for c in cands[:2]])

    # ---- Ø1.50 turning circles (only where a disk really fits)
    circles = []
    feas = fr0.buffer(-TURN_R - 0.003)
    targets = [('Frente a caja', app_c.centroid)] + [(o['table']['id'], o['app'].centroid) for o in A['acc']]
    for name, p in targets:
        if feas.is_empty:
            break
        q = nearest_points(feas, p)[0]
        if q.distance(p) <= 0.9 and public.buffer(0.05).contains(Point(q.x, q.y)):
            circles.append({'name': name, 'c': (q.x, q.y), 'closed_only': False})
    # entrance: with the D-ENT leaves open (they swing inward) and closed
    ls = lay.get('life_safety', {})
    ex_d = next((e for e in ls.get('exits', []) if e.get('opening') == 'D-ENT'), {})
    A['dent'] = dent
    A['dent_leaf'] = float(ex_d.get('leaf', 0.97))
    A['dent_width'] = float(ex_d.get('width', dent['width'] if dent else 2.0))
    swings = []
    if dent:
        xo, ya, _, yb = dent['opening']
        lf = A['dent_leaf']
        for hy, sgn in ((min(ya, yb), 1), (max(ya, yb), -1)):
            sp = door_swing_poly({'hinge': [xo, hy], 'closed_to': [xo, hy + sgn * lf], 'swing_to': [xo - lf, hy]})
            if sp is not None:
                swings.append(sp)
    A['dent_swings'] = swings
    p_ent = Point(prem.bounds[2] - TURN_R - 0.05, (ya + yb) / 2)
    sw_u = unary_union(swings) if swings else None
    feas_open = fr0.difference(sw_u).buffer(-TURN_R - 0.003) if swings else feas
    near_open = None if feas_open.is_empty else nearest_points(feas_open, p_ent)[0]
    q_closed = nearest_points(feas, p_ent)[0]
    A['entr_open_ok'] = near_open is not None and near_open.distance(p_ent) <= 0.6
    if A['entr_open_ok']:
        circles.append({'name': 'Vestíbulo D-ENT', 'c': (near_open.x, near_open.y), 'closed_only': False})
    elif q_closed.distance(p_ent) <= 0.9:
        hit = sw_u is not None and Point(q_closed).buffer(TURN_R).intersection(sw_u).area > 1e-4
        circles.append({'name': 'Vestíbulo D-ENT', 'c': (q_closed.x, q_closed.y), 'closed_only': hit})
    A['circles'] = circles

    # ---- doors
    A['dent_clear'] = A['dent_leaf'] - LEAF_LOSS
    A['dent_clear_both'] = A['dent_width'] - 2 * 0.045
    A['doors'] = []
    for o in lay.get('new_openings', []):
        if o.get('type') in ('door', 'double_acting_door', 'service_door', 'sliding_door'):
            A['doors'].append((o, float(o.get('width', 0.9)) - LEAF_LOSS))

    # ---- walking distance to D-ENT (restroom budget)
    dist, px, py, node = _geodesic(free, (prem.bounds[2] - 0.3, entr[1]))
    seats = seat_points(lay)
    ds = [(dist[node((p.x, p.y))], sid) for sid, p in seats]
    ds = [d for d in ds if np.isfinite(d[0])]
    A['d_seat'] = max(ds) if ds else (float('nan'), '')
    fin = np.isfinite(dist)
    k = int(np.argmax(np.where(fin, dist, -1)))
    A['d_far'] = (float(dist[k]), (float(px[k]), float(py[k])))
    return A


def _staff_door(lay, o):
    """True when the door opening lies wholly inside the staff zones (kitchen / washing / cold prep)."""
    from shapely.geometry import Polygon
    stf = unary_union([Polygon(z['poly']) for z in lay.get('zones', []) if z['id'] in ('A', 'B', 'E', 'W')])
    pub = unary_union([Polygon(z['poly']) for z in lay.get('zones', []) if z['id'] in ('C', 'D')])
    g = R(o['rect']).buffer(0.3)
    return g.intersection(stf).area > 0 and g.intersection(pub).area < 1e-6


# ----------------------------------------------------------------------------------------------- drawing helpers
def _wrap(s, width, size):
    out = []
    for para in str(s).split('\n'):
        cur = ''
        for w in para.split(' '):
            t = (cur + ' ' + w).strip()
            if not cur or tw(t, size) <= width:
                cur = t
            else:
                out.append(cur)
                cur = w
        out.append(cur)
    return out


def _isa(x, y, s=4.6, fill=ACC):
    """International symbol of access (simplified), top-left (x, y), size s mm."""
    u = s / 10.0
    p = (f'<g><rect x="{f(x)}" y="{f(y)}" width="{f(s)}" height="{f(s)}" rx="{f(u*1.2)}" fill="{fill}"/>'
         f'<circle cx="{f(x+4.6*u)}" cy="{f(y+1.9*u)}" r="{f(0.9*u)}" fill="#fff"/>'
         f'<path d="M{f(x+4.4*u)},{f(y+3.2*u)} L{f(x+4.4*u)},{f(y+6.0*u)} L{f(x+6.7*u)},{f(y+6.0*u)} L{f(x+7.6*u)},{f(y+8.4*u)}" '
         f'fill="none" stroke="#fff" stroke-width="{f(0.75*u)}" stroke-linecap="round" stroke-linejoin="round"/>'
         f'<line x1="{f(x+4.4*u)}" y1="{f(y+4.4*u)}" x2="{f(x+6.3*u)}" y2="{f(y+4.4*u)}" stroke="#fff" stroke-width="{f(0.6*u)}" stroke-linecap="round"/>'
         f'<path d="M{f(x+3.3*u)},{f(y+4.9*u)} A{f(2.3*u)},{f(2.3*u)} 0 1 0 {f(x+6.9*u)},{f(y+7.9*u)}" fill="none" stroke="#fff" '
         f'stroke-width="{f(0.7*u)}" stroke-linecap="round"/></g>')
    return p


def _pill(x, y, label, color, size=1.85, bg='#ffffff'):
    w = tw(label, size) + 3.0
    return (f'<g><rect x="{f(x - w/2)}" y="{f(y - 2.05)}" width="{f(w)}" height="4.1" rx="2.05" fill="{bg}" stroke="{color}" stroke-width="0.35"/>'
            + text(x, y + 0.7, label, size, family=MONO, weight='700', fill=color) + '</g>')


def _table(x, y, cols, rows, size=1.6, lh=2.0, pad=1.1, head=1.7, stripe=True, title=None):
    """cols: [(header, width_mm)], rows: [[cell,...]] where cell = str | (str, color, weight)."""
    g = []
    W = sum(c[1] for c in cols)
    if title:
        g.append(text(x, y + 3.0, title, 2.5, anchor='start', weight='800', extra='letter-spacing="0.3"'))
        y += 5.2
    g.append(f'<rect x="{f(x)}" y="{f(y)}" width="{f(W)}" height="{f(head + 2.6)}" fill="#141210"/>')
    cx = x
    for h, w in cols:
        g.append(text(cx + 1.2, y + head + 0.75, h, head, anchor='start', weight='700', fill='#ffffff'))
        cx += w
    y += head + 2.6
    for i, r in enumerate(rows):
        cells = []
        nl = 1
        for (h, w), c in zip(cols, r):
            s, colr, wt = (c, '#222222', '400') if isinstance(c, str) else (c + ('#222', '400'))[:3]
            ls = _wrap(s, w - 2.2, size)
            nl = max(nl, len(ls))
            cells.append((ls, colr, wt, w))
        rh = nl * lh + 2 * pad
        if stripe and i % 2 == 1:
            g.append(f'<rect x="{f(x)}" y="{f(y)}" width="{f(W)}" height="{f(rh)}" fill="#f4f2ee"/>')
        cx = x
        for ls, colr, wt, w in cells:
            for j, ln in enumerate(ls):
                g.append(text(cx + 1.2, y + pad + size * 0.85 + j * lh, ln, size, anchor='start', weight=wt, fill=colr))
            cx += w
        y += rh
        g.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x + W)}" y2="{f(y)}" stroke="#d9d4cb" stroke-width="0.2"/>')
    return ''.join(g), y


def _dim_mm(x1, y1, x2, y2, label, color='#1f1f1f', size=1.75, side=-1, ext=None):
    """Dimension between two sheet points (axis aligned) drawn in sheet mm (details)."""
    g = [f'<g stroke="{color}" stroke-width="0.18" fill="none">']
    t = 0.9
    if abs(y2 - y1) < 1e-6:     # horizontal
        g.append(f'<line x1="{f(x1-1)}" y1="{f(y1)}" x2="{f(x2+1)}" y2="{f(y2)}"/>')
        for xx in (x1, x2):
            g.append(f'<line stroke-width="0.35" x1="{f(xx-t)}" y1="{f(y1+t)}" x2="{f(xx+t)}" y2="{f(y1-t)}"/>')
            if ext is not None:
                g.append(f'<line x1="{f(xx)}" y1="{f(ext)}" x2="{f(xx)}" y2="{f(y1 + (0.8 if y1 > ext else -0.8))}"/>')
        g.append('</g>')
        g.append(text((x1 + x2) / 2, y1 - 0.7 if side < 0 else y1 + size + 0.4, label, size, family=MONO, weight='600', fill=color,
                      extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.8"'))
    else:
        g.append(f'<line x1="{f(x1)}" y1="{f(y1-1)}" x2="{f(x2)}" y2="{f(y2+1)}"/>')
        for yy in (y1, y2):
            g.append(f'<line stroke-width="0.35" x1="{f(x1-t)}" y1="{f(yy+t)}" x2="{f(x1+t)}" y2="{f(yy-t)}"/>')
            if ext is not None:
                g.append(f'<line x1="{f(ext)}" y1="{f(yy)}" x2="{f(x1 + (0.8 if x1 > ext else -0.8))}" y2="{f(yy)}"/>')
        g.append('</g>')
        g.append(text(x1 - 0.7 if side < 0 else x1 + 0.7 + size * 0.8, (y1 + y2) / 2, label, size, family=MONO, weight='600', fill=color,
                      rot=-90, extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.8"'))
    return ''.join(g)


def _detail_title(x, y, n, title, scale):
    return (f'<circle cx="{f(x + 2.6)}" cy="{f(y + 2.0)}" r="2.6" fill="#141210"/>'
            + text(x + 2.6, y + 2.95, str(n), 2.6, weight='800', fill='#ffffff')
            + text(x + 6.6, y + 3.0, title, 2.35, anchor='start', weight='800', extra='letter-spacing="0.2"')
            + text(x + 6.6 + tw(title, 2.35) * 1.02 + len(title) * 0.2 + 2.0, y + 3.0, scale, 2.0, anchor='start', weight='700', fill='#666', family=MONO))


def _hatch(pid, color, sp=1.1, ang=45, sw_=0.22, bg='none'):
    return (f'<pattern id="{pid}" patternUnits="userSpaceOnUse" width="{sp}" height="{sp}" patternTransform="rotate({ang})">'
            f'<rect width="{sp}" height="{sp}" fill="{bg}"/><line x1="0" y1="0" x2="0" y2="{sp}" stroke="{color}" stroke-width="{sw_}"/></pattern>')


def _wheelchair_side(X, Y, u_table_edge, facing=-1, k=D20):
    """Wheelchair user in profile at a table. du > 0 = under the table top (toes ~0.42, knees ~0.12)."""
    e, sg = u_table_edge, facing

    def P(du, v):
        return (X(e + sg * du), Y(v))

    def pl(pts, extra=''):
        return '<polyline points="' + ' '.join(f"{f(a)},{f(b)}" for a, b in (P(*q) for q in pts)) + f'" {extra}/>'
    g = ['<g fill="none" stroke="#1b1b1b" stroke-width="0.3" stroke-linecap="round" stroke-linejoin="round">']
    wc = P(-0.30, 0.30)
    g.append(f'<circle cx="{f(wc[0])}" cy="{f(wc[1])}" r="{f(0.30 * k)}" stroke="#444" stroke-width="0.35"/>')
    g.append(f'<circle cx="{f(wc[0])}" cy="{f(wc[1])}" r="{f(0.26 * k)}" stroke="#9a9a95" stroke-width="0.18"/>')
    cs = P(0.02, 0.06)
    g.append(f'<circle cx="{f(cs[0])}" cy="{f(cs[1])}" r="{f(0.06 * k)}" stroke="#444"/>')
    g.append(pl([(-0.50, 0.95), (-0.43, 0.95), (-0.40, 0.50), (0.06, 0.50), (0.26, 0.10), (0.44, 0.10)], 'stroke="#444" stroke-width="0.35"'))
    g.append(pl([(0.02, 0.12), (0.06, 0.50)], 'stroke="#444"'))
    hd = P(-0.24, 1.21)
    g.append(f'<circle cx="{f(hd[0])}" cy="{f(hd[1])}" r="{f(0.10 * k)}" fill="#ffffff"/>')
    g.append(pl([(-0.28, 1.08), (-0.33, 0.58), (0.12, 0.60), (0.30, 0.14), (0.44, 0.13)], 'stroke-width="0.45"'))
    g.append(pl([(-0.28, 1.00), (-0.16, 0.83), (0.10, 0.815)], 'stroke-width="0.35"'))
    g.append('</g>')
    return ''.join(g)


# ----------------------------------------------------------------------------------------------- sheet
def sheets(ex, lay, val):
    A = analyse(ex, lay)
    s = Sheet(ex, lay, val, 'A105')
    s.frame_and_titleblock('A-105 · Accesibilidad (Ley 7600)',
                           'Ruta accesible, anchos libres medidos, giros Ø1.50, puertas, caja C4 y mesas accesibles',
                           'A-105', scale_note='Planta 1:50 · detalles 1:20 y 1:5 · cotas en m')
    s.add('<defs>' + _hatch('acc-app', ACC, 1.0, 45, 0.2) + _hatch('acc-staff', '#c9c5bd', 1.6, -45, 0.2)
          + _hatch('acc-knee', '#8a8a85', 0.9, 45, 0.16)
          + f'<marker id="arr-acc" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.6" markerHeight="3.6" orient="auto">'
            f'<path d="M0,0 L6,3 L0,6 z" fill="{ACC}"/></marker>'
          + f'<marker id="arr-egr" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.6" markerHeight="3.6" orient="auto">'
            f'<path d="M0,0 L6,3 L0,6 z" fill="{EGR}"/></marker>'
          + '<marker id="arr-k" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.2" markerHeight="3.2" orient="auto">'
            '<path d="M0,0 L6,3 L0,6 z" fill="#1b1b1b"/></marker></defs>')
    s.grid_axes()

    # staff (kitchen) zones: light hatch, out of the public accessible route
    from shapely.geometry import Polygon
    prem = premises(ex)
    staff = unary_union([Polygon(z['poly']) for z in lay.get('zones', []) if z['id'] in ('A', 'B', 'E', 'W')]).intersection(prem)
    s.add(poly_el(staff, 'url(#acc-staff)', 'none', 0))
    pub = unary_union([Polygon(z['poly']) for z in lay.get('zones', []) if z['id'] in ('C', 'D')]).intersection(prem)
    s.add(poly_el(pub, '#eef4fb', 'none', 0, extra='fill-opacity="0.8"'))

    s.layer_existing()
    s.layer_furniture(faint=True)
    s.layer_equipment(faint=True, labels=False)
    s.layer_new()

    g = ['<g id="accesibilidad">']
    # --- D-ENT swings (keep clear) — dashed blue
    for sp in A['dent_swings']:
        g.append(poly_el(sp, ACC, 'none', 0, extra='fill-opacity="0.07"'))

    # --- accessible configuration: removed chairs, slid chairs, accessible tables
    for o in A['acc']:
        t = o['table']
        c = o['chair']
        g.append(rect_el(c['rect'], 'none', BAD, 0.3, dash='0.8 0.6', extra='rx="1.1"'))
        x0, y0, x1, y1 = c['rect']
        g.append(f'<path d="M{f(sx(x0))},{f(sy(y0))} L{f(sx(x1))},{f(sy(y1))} M{f(sx(x0))},{f(sy(y1))} L{f(sx(x1))},{f(sy(y0))}" stroke="{BAD}" stroke-width="0.22"/>')
        for c2, d, geom in o['moves']:
            g.append(rect_el(c2['rect'], 'none', '#9a9a95', 0.2, dash='0.6 0.6', extra='rx="1.1"'))
            g.append(poly_el(geom, '#dff1da', '#2b7a31', 0.3, extra='rx="1.1"'))
        g.append(rect_el(t['rect'], ACC_L, ACC, 0.45, extra='rx="0.4"'))
        tx0, ty0, tx1, ty1 = t['rect']
        g.append(mtext(sx((tx0 + tx1) / 2), sy((ty0 + ty1) / 2), [t.get('tag', t['id']), 'ACCESIBLE'], 1.5, weight='800',
                       fill=ACC, weights=['800', '700']))
        g.append(poly_el(o['app'], 'url(#acc-app)', ACC, 0.35, extra='stroke-dasharray="1 0.5"'))

    # --- caja approach
    g.append(poly_el(A['app_caja'], 'url(#acc-app)', ACC, 0.35, extra='stroke-dasharray="1 0.5"'))
    cj = A['caja']
    g.append(rect_el(cj['rect'], ACC_L, ACC, 0.45))
    cx0, cy0, cx1, cy1 = cj['rect']
    g.append(mtext(sx((cx0 + cx1) / 2), sy((cy0 + cy1) / 2), [cj.get('tag', cj['id']), f"h {A['caja_h']:.2f}"], 1.5,
                   weight='800', fill=ACC, rot=-90))

    # --- turning circles
    for c in A['circles']:
        x, y = c['c']
        dash = ' stroke-dasharray="1.2 0.8"' if c['closed_only'] else ''
        colr = WARN if c['closed_only'] else ACC
        g.append(f'<circle cx="{f(sx(x))}" cy="{f(sy(y))}" r="{f(TURN_R * S)}" fill="{colr}" fill-opacity="0.07" stroke="{colr}" stroke-width="0.4"{dash}/>')
        g.append(f'<circle cx="{f(sx(x))}" cy="{f(sy(y))}" r="0.35" fill="{colr}"/>')

    # --- accessible route (entrance -> caja -> tables), egress
    ym = A['y_mid']
    ex_, ey_ = A['entrance']
    ac = A['app_caja'].centroid
    route = [(ex_, ey_), (ex_ - 0.45, ym), (A['app_caja'].bounds[2] + 0.35, ym), (ac.x, ac.y)]
    pa = ' '.join(f"{f(sx(x))},{f(sy(y))}" for x, y in route)
    g.append(f'<polyline points="{pa}" fill="none" stroke="{ACC}" stroke-width="1.0" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#arr-acc)"/>')
    for o in A['acc']:
        c = o['app'].centroid
        g.append(f'<polyline points="{f(sx(c.x))},{f(sy(ym))} {f(sx(c.x))},{f(sy(c.y))}" fill="none" stroke="{ACC}" stroke-width="0.8" marker-end="url(#arr-acc)"/>')
    # egress line (slightly offset) to D-ENT
    xs_ = min(o['app'].bounds[0] for o in A['acc']) if A['acc'] else ex_ - 3
    eg = [(xs_, ym + 0.2), (ex_ - 0.3, ym + 0.2), (prem.bounds[2] + 0.05, ey_ + 0.2)]
    g.append('<polyline points="' + ' '.join(f"{f(sx(x))},{f(sy(y))}" for x, y in eg) + f'" fill="none" stroke="{EGR}" stroke-width="0.6" '
             f'stroke-dasharray="2 1" marker-end="url(#arr-egr)"/>')
    g.append(text(sx(xs_) - 1.2, sy(ym + 0.2) + 0.6, 'EGRESO → D-ENT', 1.7, anchor='end', weight='800', fill=EGR,
                  extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.7"'))
    g.append(text(sx((route[2][0] + A['w_main_x']) / 2), sy(ym) - 1.3, 'RUTA ACCESIBLE · entrada → caja C4 → mesas accesibles', 1.9, weight='800', fill=ACC,
                  extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.8"'))

    # --- measured widths
    seg = A['w_main_seg']
    if seg is not None:
        _, y0_, _, y1_ = seg.bounds
        xm = A['w_main_x']
        s.dim((xm, y0_), (xm, y1_), 0.0, f"{A['w_main']:.2f}", color=OKC if A['w_main'] >= REQ_GEN else BAD)
        g.append(_pill(sx(xm) - 9.5, sy(ym) + 5.3, f"↔ {A['w_main']:.2f} ≥ {REQ_GEN:.2f}", OKC if A['w_main'] >= REQ_GEN else BAD))
    fr_c = A['caja'].get('front', 'E')
    if fr_c in ('E', 'W'):
        yy = A['app_caja'].bounds[1] + 0.1
        wv, seg = _xsec(A['free'], ((A['app_caja'].bounds[0] + 0.01) if fr_c == 'E' else (A['app_caja'].bounds[2] - 0.01), yy), 'x')
        if seg is not None:
            x0_, _, x1_, _ = seg.bounds
            s.dim((x0_, yy), (x1_, yy), 0.0, f"{wv:.2f} libre", color=OKC, size=1.8, lpos=0.82 if fr_c == 'E' else 0.18)
    if A.get('w_bar') is not None:
        x0_, _, x1_, _ = A['w_bar_seg'].bounds
        s.dim((x0_, A['w_bar_y']), (x1_, A['w_bar_y']), 0.0, f"{A['w_bar']:.2f}", color=OKC if A['w_bar'] >= REQ_INT else BAD, size=1.8)
        g.append(mtext(sx((x0_ + x1_) / 2), sy(A['w_bar_y']) + 3.4, ['paso de', 'personal', f'≥ {REQ_INT:.2f}'], 1.45, weight='700', fill='#444'))
    nch = A.get('bar_niche')
    if nch:
        x0_, _, x1_, _ = nch['seg'].bounds
        s.dim((x0_, nch['y']), (x1_, nch['y']), 0.0, f"{nch['w']:.2f}", color=WARN, size=1.6)
        g.append(mtext(sx((x0_ + x1_) / 2) + 16.5, sy(nch['y']) + 0.2, [f"nicho {nch['id']} ({nch['label'].lower()})", 'fondo sin paso · 1 persona'],
                       1.35, weight='700', fill=WARN, anchor='start', weights=['800', '600']))

    # --- door tags
    dent = A['dent']
    if dent:
        xo, ya, _, yb = dent['opening']
        tx, ty = sx(prem.bounds[2]) + 11.0, sy(max(ya, yb)) + 9.0
        lines = ['D-ENT (existente)', f"{A['dent_width']:.2f} · 2 hojas {A['dent_leaf']:.2f}",
                 f"libre/hoja ≈{A['dent_clear']:.2f}*", 'umbral ≤ 0.02', 'giro: hacia adentro']
        bw = max(tw(x, 1.6) for x in lines) + 2.4
        g.append(f'<line x1="{f(sx(xo))}" y1="{f(sy(max(ya, yb)))}" x2="{f(tx)}" y2="{f(ty - 2)}" stroke="{WARN}" stroke-width="0.25"/>')
        g.append(f'<rect x="{f(tx - bw/2)}" y="{f(ty - 2)}" width="{f(bw)}" height="{f(len(lines)*2.25 + 1.8)}" fill="#fff" stroke="{WARN}" stroke-width="0.35"/>')
        g.append(''.join(text(tx, ty + 1.0 + i * 2.25, ln, 1.6, weight='800' if i == 0 else '600', fill=WARN if i in (0, 2) else '#222')
                         for i, ln in enumerate(lines)))
        g.append(_isa(sx(prem.bounds[2]) + 4.6, sy((ya + yb) / 2) - 16.5, 4.6))
    for o, clear in A['doors']:
        if not o.get('rect'):
            continue
        x0, y0, x1, y1 = o['rect']
        cond = o.get('conditional')
        ok = clear >= REQ_DOOR
        staff_d = _staff_door(lay, o)
        colr = '#777' if cond else (OKC if ok else (WARN if staff_d else BAD))
        lines = [f"{o.get('label', o['id'])} · {o.get('width', 0.9):.2f} nominal" + (' (condicional)' if cond else ''),
                 f"libre ≈{clear:.2f}* {'≥' if ok else '<'} {REQ_DOOR:.2f}"]
        if not ok and not cond:
            lines.append('VERIFICAR (personal): vano ≈1.00' if staff_d else 'AJUSTAR: vano ≈1.00')
        if o.get('type') == 'double_acting_door':
            tx, ty = sx(x1) + 27.0, sy((y0 + y1) / 2) + 1.0
        else:
            tx, ty = sx((x0 + x1) / 2) + 17.0, sy(y1) + 9.0
        bw = max(tw(x, 1.6) for x in lines) + 2.4
        g.append(f'<rect x="{f(tx - bw/2)}" y="{f(ty - 2.2)}" width="{f(bw)}" height="{f(len(lines)*2.3 + 1.6)}" fill="#fff" stroke="{colr}" stroke-width="0.35"/>')
        g.append(''.join(text(tx, ty + 0.8 + i * 2.3, ln, 1.6, weight='800' if i != 1 else '600', fill=colr) for i, ln in enumerate(lines)))

    # --- ISA at caja and accessible tables; circle labels
    for o in A['acc']:
        x0, y0, x1, y1 = o['table']['rect']
        g.append(_isa(sx(x1) + 0.8, sy(y0) + 0.3 if o['toward_table'] == 'N' else sy(y1) - 4.1, 3.4))
    busy = [LineString(route).buffer(0.10), LineString(eg).buffer(0.10)]
    busy += [LineString([(o['app'].centroid.x, ym), (o['app'].centroid.x, o['app'].centroid.y)]).buffer(0.08) for o in A['acc']]
    busy += [o['app'].exterior.buffer(0.03) for o in A['acc']] + [A['app_caja'].exterior.buffer(0.03)]
    busy += [R(o['chair']['rect']) for o in A['acc']]
    busy += [_obstacles(ex, lay)]
    if A['w_main_seg'] is not None:
        busy.append(box(A['w_main_x'] - 0.9, ym + 0.05, A['w_main_x'] + 0.1, ym + 0.45))   # width pill
    busy += [Point(c['c']).buffer(TURN_R).exterior.buffer(0.05) for c in A['circles']]
    busy = unary_union(busy)
    for c in A['circles']:
        x, y = c['c']
        colr = WARN if c['closed_only'] else ACC
        lab = ['Ø1.50 sólo con', 'hojas cerradas'] if c['closed_only'] else ['Ø1.50']
        wl = max(tw(t_, 1.5) for t_ in lab) / S + 0.06
        hl = len(lab) * 1.5 * 1.2 / S + 0.04
        best = None
        for ang in (225, 135, 315, 45, 180, 0, 270, 90):
            for rr in (0.45, 0.25, 0.95):
                px_, py_ = x + rr * math.cos(math.radians(ang)), y + rr * math.sin(math.radians(ang))
                bb = box(px_ - wl / 2, py_ - hl / 2, px_ + wl / 2, py_ + hl / 2)
                sc = bb.intersection(busy).area + (0.02 if rr > 0.9 else 0)
                if best is None or sc < best[0] - 1e-9:
                    best = (sc, px_, py_, bb)
        _, px_, py_, bb = best
        busy = busy.union(bb)
        for i_, ln_ in enumerate(lab):
            g.append(text(sx(px_), sy(py_) + (i_ - (len(lab) - 1) / 2) * 1.8 + 0.5, ln_, 1.5, weight='800', fill=colr, family=MONO,
                          extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.6"'))

    # staff area label
    zA = next((z for z in lay.get('zones', []) if z['id'] == 'A'), None)
    if zA:
        lx, ly = zA.get('label_at', [2.2, 9.35])
        g.append(f'<rect x="{f(sx(lx) - 23)}" y="{f(sy(ly) - 5.8)}" width="46" height="13.6" rx="1" fill="#ffffff" fill-opacity="0.92" stroke="#8a8a85" stroke-width="0.3"/>')
        g.append(mtext(sx(lx), sy(ly) + 1.0, ['ÁREAS DE PERSONAL (cocina)', 'fuera de la ruta pública', f'pasillos interiores ≥ {REQ_INT:.2f}', '(anchos medidos: ver A-103)'],
                       1.7, weight='600', fill='#555', weights=['800', '600', '600', '600']))

    # restroom arrow (outside, common corridor of the open-air mall)
    if dent:
        xo, ya, _, yb = dent['opening']
        ax_, ay_ = sx(prem.bounds[2]) + 2.0, sy(min(ya, yb)) - 9.0
        g.append(f'<line x1="{f(ax_)}" y1="{f(ay_)}" x2="{f(ax_ + 13)}" y2="{f(ay_)}" stroke="{ACC}" stroke-width="0.6" marker-end="url(#arr-acc)"/>')
        g.append(mtext(ax_ + 6.8, ay_ - 4.2, ['baños comunes CC', '(ubicación VERIFY)'], 1.5, weight='700', fill=ACC, weights=['800', '600']))
    g.append('</g>')
    s.add(''.join(g))

    # ------------------------------------------------------------------ verification table (free area of the plan)
    res = A['residual']
    circ_ok = [c['name'] for c in A['circles'] if not c['closed_only']]
    circ_cl = [c['name'] for c in A['circles'] if c['closed_only']]
    acc_ids = ' y '.join(o['table']['id'] for o in A['acc'])
    dr = [(o, c) for o, c in A['doors'] if not o.get('conditional')]
    d_pub_bad = [o.get('label', o['id']) for o, c in dr if c < REQ_DOOR and not _staff_door(lay, o)]
    d_stf_bad = [o.get('label', o['id']) for o, c in dr if c < REQ_DOOR and _staff_door(lay, o)]
    d_txt = '; '.join(f"{o.get('label', o['id'])} ≈{c:.2f}" + (' (personal)' if _staff_door(lay, o) else '') for o, c in dr)
    st140 = ('AJUSTAR ' + ', '.join(d_pub_bad), BAD, '800') if d_pub_bad else (
        ('VERIFICAR · ' + ', '.join(d_stf_bad) + ' < 0.90', WARN, '800') if d_stf_bad else ('VERIFICAR', WARN, '800'))
    nch = A.get('bar_niche')
    ok141 = A['w_main'] >= REQ_GEN and (A['w_bar'] is None or A['w_bar'] >= REQ_INT)
    rows = [
        [('Ley 7600 · DE 26831-MP arts. 103–104 (verificar)', '#222', '700'),
         'Local privado abierto al público: la revisión de planos (APC) fiscaliza la accesibilidad.',
         f'Ruta continua D-ENT → caja C4 → {acc_ids} → salida (dibujada). Tramo vía pública → D-ENT: condominio.',
         ('VERIFICAR', WARN, '800')],
        [('Art. 140 Puertas (verificar)', '#222', '700'),
         'Ancho libre ≥ 0.90; espacio libre ≥ 0.45 junto al lado opuesto a las bisagras.',
         f"D-ENT ≈{A['dent_clear']:.2f}/hoja" + (f"; {d_txt}" if d_txt else '') + f'. * Libre estimado = hoja − {LEAF_LOSS:.2f} (espesor + tope).',
         st140],
        [('Art. 141 Pasillos (verificar)', '#222', '700'),
         f'Pasillo general ≥ {REQ_GEN:.2f}; pasillo interior ≥ {REQ_INT:.2f}.',
         f"Salón {A['w_main']:.2f}; frente a caja {A['w_caja']:.2f}; paso barra/NW-1 {A['w_bar']:.2f} (personal)"
         + (f"; nicho {nch['id']} {nch['w']:.2f} al fondo sin paso (uso puntual)." if nch else '.'),
         ('PREVISTO EN PLANTA*', OKC, '800') if ok141 else ('AJUSTAR', BAD, '800')],
        [('Art. 142 Umbrales (verificar)', '#222', '700'),
         'Eliminar umbrales; si son indispensables: ≤ 0.02, biselados.',
         'D-ENT: niveles interior / exterior VERIFY ON SITE (detalle 4). Transición de pisos en P-1 a nivel (A-106).',
         ('VERIFICAR', WARN, '800')],
        [('Art. 143 Sanitarios (verificar)', '#222', '700'),
         'Cubículo accesible 2.25 × 1.55 (inodoro lateral) o 2.25 × 2.25; puerta 0.90 hacia afuera; barras h 0.90; lavatorio ≤ 0.80.',
         'Sin baños en el local: servicios comunes del centro comercial (H / M + accesible). Ver recuadro inferior.',
         ('VERIFICAR', WARN, '800')],
        [('Art. 148 Mostradores (verificar)', '#222', '700'),
         'Mostradores y mesas (comedor) h 0.80; ventanillas h 0.90.',
         f"Caja C4 h {A['caja_h']:.2f} × {A['caja_len']:.2f} de frente (detalle 1); barra y pase h 1.05 = servicio.",
         ('PREVISTO EN PLANTA*', OKC, '800') if A['caja_h'] <= 0.80 + 1e-6 else ('AJUSTAR', BAD, '800')],
        [('Referencia (artículo CR no confirmado)', '#666', '700'),
         f'Mesa accesible h 0.76–0.80; libre inferior ≥ 0.70; aproximación {APP_W:.2f} × {APP_L:.2f}.',
         f'{acc_ids}: se retira la silla del pasillo (ver detalles 2 y 3).',
         ('PROPUESTO', ACC, '800')],
        [('Referencia (artículo CR no confirmado)', '#666', '700'),
         'Giro Ø1.50 libre en cambios de dirección y frente a puertas.',
         'Cabe (medido en planta): ' + (', '.join(circ_ok) if circ_ok else '—') + '.'
         + (f" {', '.join(circ_cl)}: sólo con hojas cerradas." if circ_cl else '') + ' En el pasillo entre mesas no cabe.',
         ('PARCIAL', WARN, '800')],
    ]
    if A['acc'] and len(A['acc']) >= 2:
        alt = A.get('alt')
        rows.append([('Uso simultáneo (medido)', '#222', '700'),
                     f'Paso libre con usuarios en silla de ruedas en {acc_ids} a la vez.',
                     f"{res[('ALL', KNEE)]:.2f} m con {KNEE:.2f} bajo la mesa · {res[('ALL', 0.0)]:.2f} m con el rectángulo fuera de la mesa."
                     + (f" Alternativa: designar {' o '.join(alt[1])} en lugar de {alt[0]}." if alt and alt[1] else ''),
                     ('AJUSTAR' if res[('ALL', KNEE)] < REQ_INT else 'PREVISTO*', BAD if res[('ALL', KNEE)] < REQ_INT else OKC, '800')])
    tx0, ty0 = 240.0, 179.0
    svg, yend = _table(tx0, ty0, [('Norma / artículo', 33), ('Requisito', 53), ('Medido / propuesto en planta', 72), ('Estado', 28)],
                       rows, size=1.7, lh=2.1, pad=0.85, head=1.7,
                       title='VERIFICACIÓN PRELIMINAR · LEY 7600 / DE 26831-MP')
    s.add(f'<rect x="{f(tx0 - 2)}" y="{f(ty0 - 1.5)}" width="190" height="{f(yend - ty0 + 3.5)}" fill="#ffffff" stroke="#1b1b1b" stroke-width="0.35"/>')
    s.add(svg)
    s.add(text(tx0, yend + 1.3, '* Preliminar: medido sobre la planta del anteproyecto; a validar por el profesional responsable. Citas de fragmentos, no del texto primario.', 1.45,
               anchor='start', fill='#666'))

    # restroom box
    ry = yend + 4.2
    d_seat, seat_id = A['d_seat']
    d_far, p_far = A['d_far']
    src_txt = 'recorrido a pie medido en planta'
    try:   # same measured egress lengths as A-104 / documento 03 (one computation per build, memoised in s104)
        import importlib
        r104 = importlib.import_module('sheets.s104_seguridad').compute_cached(ex, lay, val)
        pp = {p_['id']: p_ for p_ in r104['paths']}
        if 'E5' in pp:
            d_seat, seat_id = pp['E5']['length'], pp['E5']['name'].split('(')[-1].rstrip(')')
        far_ = max((p_ for p_ in r104['paths'] if p_['id'] != 'E5'), key=lambda q: q['length'], default=None)
        if far_:
            d_far, p_far = far_['length'], far_.get('from_pt') or far_['pts'][0]
        src_txt = 'recorridos E5 / E1 de A-104'
    except Exception as err:   # noqa: BLE001 — fall back to this sheet's own grid measurement
        print('A-105: A-104 egress figures unavailable, using own measurement:', err)
    if '#' in str(seat_id):
        bq, n_ = str(seat_id).split('#', 1)
        seat_id = f'{bq}, puesto {n_}'
    rlines = [
        ('!', 'SERVICIOS SANITARIOS = COMUNES DEL CENTRO COMERCIAL (H / M + ACCESIBLE) · VERIFY ON SITE'),
        ('', f'Recorrido máximo hasta el servicio sanitario {MAX_WC:.0f} m (Reglamento de Construcciones INVU — verificar artículo); {src_txt}.'),
        ('', f'Clientes: asiento más lejano ({seat_id}) → D-ENT ≈ {d_seat:.1f} m  ⇒  baño común a ≤ {MAX_WC - d_seat:.1f} m de D-ENT por el pasillo.'),
        ('', f'Personal: punto más lejano (X {p_far[0]:.1f} · Y {p_far[1]:.1f}) → D-ENT ≈ {d_far:.2f} m  ⇒  baño común a ≤ {MAX_WC - d_far:.1f} m de D-ENT.'),
        ('', 'Requisitos a acreditar: autorización escrita de la administración (uso por clientes y personal en todo el horario),'),
        ('', 'capacidad según CIHSE Tabla 5.3 sumando el aforo de LAVA (49), cubículo accesible art. 143 y ruta accesible hasta él.'),
    ]
    rh = len(rlines) * 2.45 + 3.2
    s.add(f'<rect x="{f(tx0 - 2)}" y="{f(yend + 2.0)}" width="190" height="{f(ry - yend - 2.0)}" fill="#ffffff"/>')
    s.add(f'<rect x="{f(tx0 - 2)}" y="{f(ry)}" width="190" height="{f(rh)}" fill="#f3f7fc" stroke="{ACC}" stroke-width="0.4"/>')
    s.add(_isa(tx0 + 184.0 - 4.8, ry + 1.2, 4.2))
    for i, (k, ln) in enumerate(rlines):
        s.add(text(tx0, ry + 3.4 + i * 2.45, ln, 1.66 if k else 1.6, anchor='start', weight='800' if k else '400',
                   fill=ACC if k else '#1f1f1f'))

    # ------------------------------------------------------------------ side panel
    leg = [
        (sw_line(ACC, None, 1.0), 'RUTA ACCESIBLE (entrada → caja → mesas)'),
        (sw_line(EGR, '2 1', 0.6), 'Egreso hacia D-ENT (salida única)'),
        (lambda x, y: f'<rect x="{x}" y="{y}" width="10" height="3.4" fill="url(#acc-app)" stroke="{ACC}" stroke-width="0.35" stroke-dasharray="1 0.5"/>',
         f'Espacio de aproximación {APP_W:.2f} × {APP_L:.2f}'),
        (lambda x, y: f'<circle cx="{x+5}" cy="{y+1.7}" r="2.2" fill="{ACC}" fill-opacity="0.08" stroke="{ACC}" stroke-width="0.4"/>',
         'Giro Ø1.50 libre (verificado en planta)'),
        (lambda x, y: f'<circle cx="{x+5}" cy="{y+1.7}" r="2.2" fill="{WARN}" fill-opacity="0.08" stroke="{WARN}" stroke-width="0.4" stroke-dasharray="1 0.6"/>',
         'Giro Ø1.50 sólo con hojas de D-ENT cerradas'),
        (lambda x, y: f'<rect x="{x}" y="{y}" width="10" height="3.4" fill="{ACC}" fill-opacity="0.07" stroke="none"/>',
         'Barrido de hojas D-ENT (mantener libre)'),
        (lambda x, y: f'<rect x="{x+1}" y="{y}" width="8" height="3.4" rx="0.5" fill="{ACC_L}" stroke="{ACC}" stroke-width="0.45"/>',
         'Mesa accesible / caja accesible'),
        (lambda x, y: (f'<rect x="{x+3}" y="{y}" width="4" height="3.4" rx="1" fill="none" stroke="{BAD}" stroke-width="0.3" stroke-dasharray="0.8 0.6"/>'
                       f'<path d="M{x+3},{y} L{x+7},{y+3.4} M{x+3},{y+3.4} L{x+7},{y}" stroke="{BAD}" stroke-width="0.22"/>'),
         'Silla retirada (verde = silla corrida)'),
        (lambda x, y: _pill(x + 5, y + 1.7, '↔ 1.27', OKC, 1.5), 'Ancho libre medido (m)'),
        (lambda x, y: _isa(x + 3.2, y - 0.3, 3.8), 'Símbolo internacional de accesibilidad'),
        (lambda x, y: f'<rect x="{x}" y="{y}" width="10" height="3.4" fill="url(#acc-staff)" stroke="#bbb" stroke-width="0.2"/>',
         'Área de personal (fuera de la ruta pública)'),
    ] + [LEGEND_WALLS[0], LEGEND_WALLS[2], LEGEND_WALLS[3]]
    m = (val or {}).get('metrics', {})
    wrows = [('Pasillo general del salón (≥ 1.20)', f"{A['w_main']:.2f}"),
             ('Ruta entrada → caja (cuello medido)', f"{A['bn_route']:.2f}"),
             ('Frente a caja C4 (libre)', f"{A['w_caja']:.2f}"),
             ('Paso barra / NW-1, personal (≥ 0.90)', f"{A['w_bar']:.2f}")]
    if A.get('bar_niche'):
        wrows.append((f"Nicho {A['bar_niche']['id']} al fondo de la barra (sin paso)", f"{A['bar_niche']['w']:.2f}"))
    for o in A['acc']:
        tid = o['table']['id']
        wrows.append((f'Con silla de ruedas en {tid} (0.45 bajo mesa)', f"{res[(tid, KNEE)]:.2f}"))
    for r in m.get('routes', []):
        if r.get('kind') in ('clean', 'dirty'):
            lab = r.get('label', r['id']).replace('puerta ', '').replace('pasillo limpio → ', '')
            lab = lab if len(lab) <= 46 else lab[:45] + '…'
            wrows.append((f"Personal · {lab}", f"{r['min_width']:.2f}"))
    drows = [(f"D-ENT {A['dent_width']:.2f} · hoja {A['dent_leaf']:.2f} (libre est.)", f"≈{A['dent_clear']:.2f}"),
             ('D-ENT ambas hojas abiertas (est.)', f"≈{A['dent_clear_both']:.2f}")]
    for o, clear in A['doors']:
        drows.append((f"{o.get('label', o['id'])} {o.get('width', 0.9):.2f} nominal{' (condicional)' if o.get('conditional') else ''}", f"≈{clear:.2f}"))
    notes = [
        '!ANTEPROYECTO / PRELIMINAR: a validar por el profesional responsable.',
        'Citas (fragmentos, no texto primario — verificar en SCIJ): Ley 7600;',
        'DE 26831-MP arts. 103–104, 140 puertas, 141 pasillos, 142 umbrales,',
        '143 sanitarios, 148 mostradores; INVU 2018 art. 13 accesibilidad.',
        'Anchos: medidos en planta sobre el piso libre (muros, columnas,',
        'equipos, mesas y sillas en su posición). Giros Ø1.50: sólo donde el',
        'disco libre cabe (erosión 0.75 m del piso libre).',
        f'Mesas accesibles {acc_ids}: h 0.76–0.80, libre inferior ≥ 0.70, sin',
        'faldón; patas en esquinas o doble pedestal (espacio para rodillas).',
        'Caja C4: tramo a h 0.80 con frente libre; POS al alcance (≤ 1.20).',
        '!D-ENT abre hacia adentro (aforo 49 < 50, NFPA 101): recomendado',
        '!invertir el giro hacia afuera sin invadir el pasillo común — VERIFY',
        '!con la administración. Umbral ≤ 0.02 biselado: VERIFY ON SITE.',
        'Pisos del salón antideslizantes y sin cambios de nivel (A-106).',
        'Rotular mesas accesibles y caja con el símbolo internacional.',
        'Señalización táctil / contraste en vidrios de fachada: recomendado.',
    ]
    for o, c in A['doors']:
        if c < REQ_DOOR and not o.get('conditional'):
            notes.append(f"!{o.get('label', o['id'])} ({o.get('width', 0.9):.2f} nominal) da ≈{c:.2f} libres < {REQ_DOOR:.2f}: ampliar vano a ≈1.00"
                         + (' o justificar (área de personal).' if _staff_door(lay, o) else '.'))
    if len(A['acc']) >= 2 and res[('ALL', KNEE)] < REQ_INT:
        alt = A.get('alt')
        notes += [f"!{acc_ids} quedan enfrentadas: con ambas ocupadas por silla de",
                  f"!ruedas el paso libre baja a {res[('ALL', KNEE)]:.2f} (< {REQ_INT:.2f})."
                  + (f" Designar {' o '.join(alt[1])}" if alt and alt[1] else ''),
                  (f"!en lugar de {alt[0]} — decisión del profesional responsable." if alt and alt[1] else
                   '!Decisión del profesional responsable.')]
    s.side_panel([('h', 'Leyenda'), ('legend', leg),
                  ('h', 'Anchos libres medidos (m)'), ('rows', wrows),
                  ('h', 'Puertas · ancho libre (m, * est.)'), ('rows', drows),
                  ('h', 'Notas'), ('para', notes)])

    # ------------------------------------------------------------------ details band (y 318–412)
    _details(s, ex, lay, A)
    return [{'id': 'A105', 'file': 'lava_A105_accesibilidad.svg', 'title': 'Accesibilidad (Ley 7600)', 'order': 105, 'svg': s.render()}]


# ----------------------------------------------------------------------------------------------- details
D25 = 40.0         # 1:25 -> 1 m = 40 mm


def _details(s, ex, lay, A):
    g = ['<g id="details">']
    top = 318.0
    g.append(f'<line x1="12" y1="{top - 2}" x2="430" y2="{top - 2}" stroke="#141210" stroke-width="0.3"/>')
    for xx in (153.0, 262.0, 369.0):
        g.append(f'<line x1="{xx}" y1="{top}" x2="{xx}" y2="410" stroke="#d9d4cb" stroke-width="0.25"/>')

    # ---------------- 1 · caja C4 elevation, seen from the dining room (looking west: north on the right)
    bar = [e for e in lay['equipment'] if e.get('cat') == 'bar' and not e.get('stack_with') and not e.get('overhead')]
    stacked = [e for e in lay['equipment'] if e.get('stack_with') in {b['id'] for b in bar}]
    yS = max(max(e['rect'][1], e['rect'][3]) for e in bar) + 0.12
    wall_n = min(min(e['rect'][1], e['rect'][3]) for e in bar)        # interior face of the north wall
    wall_t = 0.116
    vmax = 1.28
    ox = 24.0
    fy = top + 13.5 + vmax * D20
    X = lambda y: ox + (yS - y) * D20
    Y = lambda v: fy - v * D20
    g.append(_detail_title(12, top, 1, 'CAJA C4 · ELEVACIÓN DESDE EL SALÓN', '1:20'))
    g.append(text(12, top + 8.3, 'Mirando al oeste (norte a la derecha). Tramo accesible C4 h 0.80 — art. 148 (verificar).', 1.5,
                  anchor='start', fill='#444'))
    nw = next((w for w in lay.get('new_walls', []) if w.get('role') == 'kitchen_dining_partition'), None)
    if nw:
        bh = float(nw.get('base_h', 1.0))
        g.append(f'<rect x="{f(X(yS))}" y="{f(Y(bh))}" width="{f((yS - wall_n) * D20)}" height="{f(bh * D20)}" fill="#ecebe8" stroke="#bdbdb8" stroke-width="0.2"/>')
        g.append(f'<rect x="{f(X(yS))}" y="{f(Y(vmax))}" width="{f((yS - wall_n) * D20)}" height="{f((vmax - bh) * D20)}" fill="#e9f7fd" stroke="#9fd8ef" stroke-width="0.2"/>')
        g.append(text(X(yS) + 1.5, Y(vmax) + 2.6, f"al fondo: {nw['id']} (base h {bh:.2f} + vidrio)", 1.45, anchor='start', fill='#6b6b66'))
    g.append(f'<rect x="{f(X(wall_n))}" y="{f(Y(vmax))}" width="{f(wall_t * D20)}" height="{f(vmax * D20)}" fill="url(#hatch-ex)" stroke="#5c5c58" stroke-width="0.25"/>')
    g.append(f'<line x1="{f(X(yS) - 3)}" y1="{f(fy)}" x2="{f(X(wall_n) + wall_t * D20 + 2)}" y2="{f(fy)}" stroke="#111" stroke-width="0.5"/>')
    fill, stroke = COL['bar']
    for e in bar:
        y0, y1 = sorted((e['rect'][1], e['rect'][3]))
        h = float(e.get('h', 1.0))
        is_c = e.get('key') == 'caja'
        c_ = ACC if is_c else stroke
        g.append(f'<rect x="{f(X(y1))}" y="{f(Y(h))}" width="{f((y1 - y0) * D20)}" height="{f(h * D20)}" fill="{ACC_L if is_c else fill}" '
                 f'stroke="{c_}" stroke-width="{0.5 if is_c else 0.3}"/>')
        g.append(f'<rect x="{f(X(y1))}" y="{f(Y(h))}" width="{f((y1 - y0) * D20)}" height="1.5" fill="{c_}" fill-opacity="0.85"/>')
        name = e.get('plan_label') or e.get('label', '')
        g.append(mtext(X((y0 + y1) / 2), Y(h) - (7.2 if is_c else 4.6), [f"{e.get('tag', e['id'])} · {name}", f"h {h:.2f}"], 1.55,
                       weight='700', fill=c_, weights=['800', '700']))
        if is_c:
            kx0, kx1 = X(y1) + 2.0, X(y0) - 2.0
            g.append(f'<rect x="{f(kx0)}" y="{f(Y(0.70))}" width="{f(kx1 - kx0)}" height="{f(0.70 * D20)}" fill="url(#acc-knee)" '
                     f'stroke="{ACC}" stroke-width="0.3" stroke-dasharray="1 0.6"/>')
            g.append(f'<rect x="{f((kx0 + kx1) / 2 - 10.5)}" y="{f(Y(0.36) - 4.8)}" width="21" height="8.4" fill="#ffffff" fill-opacity="0.9"/>')
            g.append(mtext((kx0 + kx1) / 2, Y(0.36) - 0.4, ['libre inferior h ≥ 0.70', 'si la aproximación', 'es frontal'], 1.45,
                           weight='700', fill=ACC, weights=['800', '600', '600']))
            g.append(_dim_mm(kx1 - 2.6, Y(h), kx1 - 2.6, fy, f"{h:.2f}", ACC, side=-1))
            g.append(_dim_mm(kx0 + 2.6, Y(0.70), kx0 + 2.6, fy, '≥0.70', ACC, side=1, size=1.5))
            g.append(_isa(X((y0 + y1) / 2) - 2.0, Y(h) + 2.4, 4.0))
    for e in stacked:
        y0, y1 = sorted((e['rect'][1], e['rect'][3]))
        base = next((b for b in bar if b['id'] == e['stack_with']), None)
        hb = float(base.get('h', 0.8)) if base else 0.8
        ht = max(float(e.get('h', hb + 0.1)), hb + 0.08)
        g.append(f'<path d="M{f(X(y1))},{f(Y(hb))} L{f(X(y1) + 1.5)},{f(Y(ht))} L{f(X(y0) - 1.5)},{f(Y(ht))} L{f(X(y0))},{f(Y(hb))} z" fill="#555" stroke="#222" stroke-width="0.2"/>')
    tall = sorted([e for e in bar if e.get('key') != 'caja'], key=lambda e: -max(e['rect'][1], e['rect'][3]))
    if tall:
        e = tall[0]
        y0, y1 = sorted((e['rect'][1], e['rect'][3]))
        g.append(_dim_mm(X(y1) - 2.6, Y(float(e.get('h', 1.05))), X(y1) - 2.6, fy, f"{float(e.get('h', 1.05)):.2f}", '#333'))
    for e in bar:
        y0, y1 = sorted((e['rect'][1], e['rect'][3]))
        g.append(_dim_mm(X(y1), fy + 3.8, X(y0), fy + 3.8, f"{y1 - y0:.2f}", ACC if e.get('key') == 'caja' else '#333', side=1))
    g.append(text(X(yS) - 3, fy + 10.3, '← SUR', 1.45, anchor='start', fill='#777', weight='700'))
    g.append(text(X(wall_n) + wall_t * D20 + 2, fy + 10.3, 'NORTE →', 1.45, anchor='end', fill='#777', weight='700'))

    # ---------------- 2 · accessible table plan (rotated: aisle to the right) and 3 · section, 1:25
    o = A['acc'][0] if A['acc'] else None
    if o:
        t = o['table']
        tx0, ty0, tx1, ty1 = t['rect']
        fc = o['toward_table']
        horiz = fc in ('N', 'S')
        depth = (ty1 - ty0) if horiz else (tx1 - tx0)
        length = (tx1 - tx0) if horiz else (ty1 - ty0)
        ap = o['app']
        a_off = ((ap.bounds[0] - tx0) if horiz else (ap.bounds[1] - ty0))
        others = [a['table']['id'] for a in A['acc']]
        U = lambda u: 166.0 + u * D25
        V = lambda v: top + 17.0 + v * D25
        g.append(_detail_title(156, top, 2, 'MESA ACCESIBLE · PLANTA', '1:25'))
        g.append(text(156, top + 8.3, f"Tipo {' / '.join(others)} (dibujada {t['id']}, girada: pasillo a la derecha).", 1.5, anchor='start', fill='#444'))
        g.append(f'<rect x="{f(U(-0.22))}" y="{f(V(-0.05))}" width="{f(0.18 * D25)}" height="{f((length + 0.1) * D25)}" fill="{COL["banquette"][0]}" stroke="{COL["banquette"][1]}" stroke-width="0.3"/>')
        g.append(text(U(-0.13) + 0.6, V(length / 2), 'banca', 1.4, fill='#1f5f25', rot=-90, weight='700'))
        g.append(f'<rect x="{f(U(depth - KNEE))}" y="{f(V(a_off))}" width="{f(KNEE * D25)}" height="{f(APP_W * D25)}" fill="url(#acc-knee)" stroke="none"/>')
        g.append(f'<rect x="{f(U(0))}" y="{f(V(0))}" width="{f(depth * D25)}" height="{f(length * D25)}" fill="{ACC_L}" fill-opacity="0.5" stroke="{ACC}" stroke-width="0.5" rx="0.6"/>')
        g.append(f'<rect x="{f(U(depth - KNEE))}" y="{f(V(a_off))}" width="{f(KNEE * D25)}" height="{f(APP_W * D25)}" fill="none" stroke="#777" stroke-width="0.25" stroke-dasharray="0.8 0.5"/>')
        g.append(f'<rect x="{f(U(depth))}" y="{f(V(a_off))}" width="{f(APP_L * D25)}" height="{f(APP_W * D25)}" fill="url(#acc-app)" stroke="{ACC}" stroke-width="0.4" stroke-dasharray="1 0.5"/>')
        for c2, d, geom in o['moves']:
            gx0, gy0, gx1, gy1 = geom.bounds
            vv0 = (gx0 - tx0) if horiz else (gy0 - ty0)
            vv1 = (gx1 - tx0) if horiz else (gy1 - ty0)
            g.append(f'<rect x="{f(U(depth + 0.05))}" y="{f(V(vv0))}" width="{f(0.45 * D25)}" height="{f((vv1 - vv0) * D25)}" fill="#dff1da" stroke="#2b7a31" stroke-width="0.3" rx="1.5"/>')
            g.append(mtext(U(depth + 0.275), V((vv0 + vv1) / 2), ['silla', f"+{abs(d):.2f}"], 1.35, fill='#1f5f25', weight='700'))
        vfree = (a_off + APP_W + length) / 2 if (length - a_off - APP_W) > a_off else a_off / 2
        g.append(mtext(U(depth / 2), V(vfree), [t['id'], f"{length:.2f}×{depth:.2f}", 'h 0.76–0.80'], 1.45, weight='800', fill=ACC,
                       weights=['800', '600', '600']))
        g.append(f'<rect x="{f(U(depth + APP_L / 2 + 0.05) - 9)}" y="{f(V(a_off + APP_W / 2) - 3.3)}" width="18" height="6.4" fill="#ffffff" fill-opacity="0.9"/>')
        g.append(mtext(U(depth + APP_L / 2 + 0.05), V(a_off + APP_W / 2) + 0.3, ['aproximación', f'{APP_W:.2f} × {APP_L:.2f}'], 1.45,
                       weight='700', fill=ACC, weights=['800', '700']))
        g.append(_dim_mm(U(0), V(length) + 4.2, U(depth), V(length) + 4.2, f"{depth:.2f}", '#333', side=1, size=1.5))
        g.append(_dim_mm(U(depth), V(length) + 4.2, U(depth + APP_L), V(length) + 4.2, f"{APP_L:.2f}", ACC, side=1, size=1.5))
        g.append(_dim_mm(U(depth + APP_L) + 3.0, V(a_off), U(depth + APP_L) + 3.0, V(a_off + APP_W), f"{APP_W:.2f}", ACC, side=1, size=1.5))
        g.append(_dim_mm(U(-0.22) - 2.4, V(0), U(-0.22) - 2.4, V(length), f"{length:.2f}", '#333', side=-1, size=1.5))
        g.append(text(U(depth + APP_L) + 9.0, V(length / 2), '← pasillo', 1.4, fill='#666', rot=-90, weight='700'))
        pn = ['Se retira la silla del pasillo; la vecina se corre', f'lo necesario. Rayado gris: {KNEE:.2f} bajo el tablero',
              '(pies / rodillas) — criterio a validar.']
        for i, ln in enumerate(pn):
            g.append(text(156, V(length) + 11.0 + i * 2.2, ln, 1.45, anchor='start', fill='#333'))

        # section (u = 0 at the far edge of the table, table edge at u = depth; wheelchair faces -u)
        sfy = top + 13.0 + 1.40 * D25 + 8.0
        Us = lambda u: 280.0 + u * D25
        Vs = lambda v: sfy - v * D25
        g.append(_detail_title(265, top, 3, 'MESA ACCESIBLE · CORTE', '1:25'))
        g.append(text(265, top + 8.3, 'Tablero sin faldón; patas en esquinas o doble pedestal.', 1.5, anchor='start', fill='#444'))
        g.append(f'<line x1="{f(Us(-0.30))}" y1="{f(sfy)}" x2="{f(Us(depth + APP_L + 0.10))}" y2="{f(sfy)}" stroke="#111" stroke-width="0.5"/>')
        g.append(f'<path d="M{f(Us(-0.30))},{f(Vs(0.45))} L{f(Us(-0.06))},{f(Vs(0.45))} L{f(Us(-0.06))},{f(sfy)}" fill="none" stroke="{COL["banquette"][1]}" stroke-width="0.35"/>')
        g.append(text(Us(-0.18), Vs(0.45) - 1.0, 'banca', 1.35, fill='#1f5f25', weight='700'))
        g.append(f'<rect x="{f(Us(depth - KNEE))}" y="{f(Vs(0.70))}" width="{f(KNEE * D25)}" height="{f(0.70 * D25)}" fill="url(#acc-knee)" stroke="none"/>')
        g.append(f'<rect x="{f(Us(0))}" y="{f(Vs(0.78))}" width="{f(depth * D25)}" height="{f(0.035 * D25)}" fill="#555" stroke="#222" stroke-width="0.2"/>')
        for uu in (0.03, depth - 0.07):
            g.append(f'<rect x="{f(Us(uu))}" y="{f(Vs(0.745))}" width="{f(0.04 * D25)}" height="{f(0.745 * D25)}" fill="none" stroke="#777" stroke-width="0.2" stroke-dasharray="0.8 0.5"/>')
        g.append(f'<rect x="{f(Us(depth))}" y="{f(sfy - 0.8)}" width="{f(APP_L * D25)}" height="0.8" fill="{ACC}" fill-opacity="0.45"/>')
        g.append(_wheelchair_side(Us, Vs, depth, facing=-1, k=D25))
        g.append(_dim_mm(Us(-0.30) - 2.0, Vs(0.78), Us(-0.30) - 2.0, sfy, '0.76–0.80', '#333', side=-1, size=1.45))
        g.append(_dim_mm(Us(depth - KNEE) + 1.6, Vs(0.70), Us(depth - KNEE) + 1.6, sfy, '≥0.70', ACC, side=1, size=1.45))
        g.append(_dim_mm(Us(depth - KNEE), sfy + 3.6, Us(depth), sfy + 3.6, f'{KNEE:.2f}', '#555', side=1, size=1.4))
        g.append(_dim_mm(Us(depth), sfy + 3.6, Us(depth + APP_L), sfy + 3.6, f'{APP_L:.2f} aproximación', ACC, side=1, size=1.45))

    # ---------------- 4 · threshold at D-ENT (1:5) and door clear width
    x4 = 372.0
    g.append(_detail_title(x4, top, 4, 'UMBRAL D-ENT', '1:5'))
    k5 = 200.0
    fy4 = top + 26.0
    ox4 = x4 + 3.0
    step = 0.02
    seq = [(0.0, 0.0), (0.06, 0.0), (0.10, step), (0.18, step), (0.22, 0.0), (0.27, 0.0)]
    g.append('<polyline points="' + ' '.join(f"{f(ox4 + u * k5)},{f(fy4 - v * k5)}" for u, v in seq) + '" fill="none" stroke="#111" stroke-width="0.45"/>')
    g.append(f'<rect x="{f(ox4)}" y="{f(fy4)}" width="{f(0.27 * k5)}" height="3.5" fill="url(#hatch-ex)" stroke="#5c5c58" stroke-width="0.2"/>')
    g.append(f'<rect x="{f(ox4 + 0.115 * k5)}" y="{f(fy4 - step * k5 - 11)}" width="{f(0.045 * k5)}" height="{f(11 - 0.6)}" fill="#e3f6ff" stroke="{COL["glass"]}" stroke-width="0.3"/>')
    g.append(text(ox4 + 0.1375 * k5, fy4 - step * k5 - 12.0, 'hoja', 1.4, fill='#555'))
    g.append(_dim_mm(ox4 + 0.245 * k5, fy4 - step * k5, ox4 + 0.245 * k5, fy4, '≤0.02', BAD, side=1, size=1.45, ext=ox4 + 0.18 * k5))
    g.append(text(ox4 + 0.08 * k5, fy4 - 2.2, 'bisel', 1.4, fill='#333', weight='700'))
    g.append(text(ox4, fy4 + 6.2, 'INTERIOR', 1.35, anchor='start', fill='#555', weight='700'))
    g.append(text(ox4 + 0.27 * k5, fy4 + 6.2, 'PASILLO CC', 1.35, anchor='end', fill='#555', weight='700'))
    n4 = [('Art. 142 (verificar): eliminar el umbral', '#333', '400'), ('o ≤ 0.02 biselado. Niveles interior /', '#333', '400'),
          ('exterior: VERIFY ON SITE.', BAD, '700'),
          (f"Libre por hoja ≈{A['dent_clear']:.2f} (est. {A['dent_leaf']:.2f} − 0.06):", BAD, '700'), ('medir con la hoja a 90°.', '#333', '400'),
          ('Manija de palanca; apertura sin llave', '#333', '400'), ('desde el interior. Espacio lateral', '#333', '400'),
          ('≥ 0.45 junto al pestillo (art. 140).', '#333', '400')]
    for i, (ln, c, w) in enumerate(n4):
        g.append(text(x4, fy4 + 11.5 + i * 2.25, ln, 1.45, anchor='start', fill=c, weight=w))
    g.append('</g>')
    s.add(''.join(g))
