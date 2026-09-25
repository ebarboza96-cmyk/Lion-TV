"""Validate a LAVA layout proposal against the existing conditions.

Usage:
    python3 tools/validate.py data/layout.json [--json out.json]

Checks (all objective, geometry-based):
  * every item inside the premises, not intersecting walls/columns/new walls
  * no overlaps between items (chairs may tuck <=12 cm under their table)
  * required clear floor in front of each item's working face ("front"/"clear")
  * door swing areas free
  * minimum clear width along each declared route (sampled every 5 cm)
  * dirty-dish route must not cross clean route / prep zones
  * hood covers the hot line (with overhang) ; parrilla visibility from seats/entrance
  * required equipment present ; zone areas ; seat count
"""
import json
import math
import sys

import numpy as np
from scipy import ndimage
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, __import__('os').path.dirname(__file__))
from lavageo import (R, blocking_obstacles, door_swing_poly, find_equipment, front_zone, item_lists,
                     load_existing, load_json, opaque_obstacles, premises, seat_count, seat_points,
                     standing_existing_walls)

RES = 0.02
TOL = 0.011  # 1 cm tolerance for touching

REQUIRED = {
    'fridge_2d': 'Refrigerador comercial 2 puertas 145x70',
    'freezer_1d': 'Congelador vertical 1 puerta 75x70',
    'mesa_fria': 'Mesa fria refrigerada 180x70',
    'mesa_1': 'Mesa de trabajo inox #1 180x70',
    'mesa_2': 'Mesa de trabajo inox #2 180x70',
    'shelf_4': 'Estanteria 4 niveles 170x35',
    'sink_2t': 'Fregadero 2 tanques 200x80',
    'mop_sink': 'Pileta / mop sink 60x50',
    'handwash': 'Lavamanos 33x38',
    'parrilla': 'Parrilla argentina 150',
    'cocina_4q': 'Cocina LPG 4 quemadores',
    'plancha': 'Plancha 70',
    'freidora_1': 'Freidora #1',
    'freidora_2': 'Freidora #2',
    'hood': 'Campana 360x90',
    'smoker': 'Smoker cabinet',
    'fuel_storage': 'Almacen lena/carbon',
    'barra': 'Barra / caja',
    'pos': 'POS',
    'pass': 'Pase de platos',
    'delivery_staging': 'Staging delivery',
}
OPTIONAL = {'holding': 'Holding cabinet', 'mesa_opt': 'Mesa 187x60'}
HOT_LINE = ['parrilla', 'cocina_4q', 'plancha', 'freidora_1', 'freidora_2']


def rasterize(prem, obstacles, bounds):
    x0, y0, x1, y1 = bounds
    nx = int(math.ceil((x1 - x0) / RES))
    ny = int(math.ceil((y1 - y0) / RES))
    xs = x0 + (np.arange(nx) + 0.5) * RES
    ys = y0 + (np.arange(ny) + 0.5) * RES
    free = np.zeros((ny, nx), dtype=bool)
    try:
        from shapely import contains_xy
        XX, YY = np.meshgrid(xs, ys)
        inside = contains_xy(prem, XX, YY)
        blocked = contains_xy(obstacles, XX, YY) if not obstacles.is_empty else np.zeros_like(inside)
        free = inside & ~blocked
    except ImportError:  # pragma: no cover
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                p = Point(x, y)
                free[j, i] = prem.contains(p) and not obstacles.contains(p)
    dt = ndimage.distance_transform_edt(free) * RES
    return free, dt, (x0, y0)


def dt_at(dt, origin, x, y):
    i = int((x - origin[0]) / RES)
    j = int((y - origin[1]) / RES)
    if j < 0 or i < 0 or j >= dt.shape[0] or i >= dt.shape[1]:
        return 0.0
    return float(dt[j, i])


def route_width(dt, origin, pts, skip_ends=0.35):
    line = LineString(pts)
    L = line.length
    worst = (1e9, None)
    n = max(2, int(L / 0.05))
    for k in range(n + 1):
        s = L * k / n
        if s < skip_ends or s > L - skip_ends:
            continue
        p = line.interpolate(s)
        w = 2 * dt_at(dt, origin, p.x, p.y)
        if w < worst[0]:
            worst = (w, (round(p.x, 2), round(p.y, 2)))
    return worst, L


def widest_path_bottleneck(free, dt, origin, a, b):
    """Max-min clearance between two points (binary search on eroded connectivity)."""
    def seed(pt, rad=0.5):
        cj, ci = int((pt[1] - origin[1]) / RES), int((pt[0] - origin[0]) / RES)
        k = int(rad / RES)
        j0, j1 = max(0, cj - k), min(dt.shape[0], cj + k + 1)
        i0, i1 = max(0, ci - k), min(dt.shape[1], ci + k + 1)
        sub = dt[j0:j1, i0:i1].copy()
        jj, ii = np.mgrid[j0:j1, i0:i1]
        sub[(jj - cj) ** 2 + (ii - ci) ** 2 > k * k] = -1
        m = np.unravel_index(np.argmax(sub), sub.shape)
        return (j0 + m[0], i0 + m[1])
    ia, ib = seed(a), seed(b)
    lo, hi = 0.0, 3.0
    for _ in range(18):
        mid = (lo + hi) / 2
        mask = dt >= mid / 2
        lab, _n = ndimage.label(mask)
        la = lab[ia] if 0 <= ia[0] < lab.shape[0] and 0 <= ia[1] < lab.shape[1] else 0
        lb = lab[ib] if 0 <= ib[0] < lab.shape[0] and 0 <= ib[1] < lab.shape[1] else 0
        if la and la == lb:
            lo = mid
        else:
            hi = mid
    return lo


def validate(lay_path):
    ex = load_existing()
    lay = load_json(lay_path)
    prem, walls_only = blocking_obstacles(ex, lay, include_items=False)
    _, all_obs = blocking_obstacles(ex, lay, include_items=True)
    issues, warnings, metrics = [], [], {}

    items = item_lists(lay)
    # 1. containment + wall collisions
    for kind, it, g in items:
        if not prem.buffer(TOL).contains(g):
            out = g.difference(prem).area
            if out > 0.002:
                issues.append(f"{kind} {it.get('id')} ({it.get('label','')}) sale del local ({out:.3f} m2 fuera)")
        hit = g.intersection(walls_only).area
        if hit > 0.002:
            issues.append(f"{kind} {it.get('id')} ({it.get('label','')}) choca con muro/columna ({hit:.3f} m2)")

    for ko in ex.get('keepouts', []):
        kg = R(ko['rect'])
        for kind, it, g in items:
            a = g.intersection(kg).area
            if a > 0.002:
                issues.append(f"{kind} {it.get('id')} invade zona libre {ko['id']} ({ko['note'][:40]}...) {a:.2f} m2")

    # 2. item overlaps
    table_geoms = {t['id']: R(t['rect']) for t in lay.get('tables', [])}
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            k1, a, g1 = items[i]
            k2, b, g2 = items[j]
            inter = g1.intersection(g2).area
            if inter <= 0.002:
                continue
            if {k1, k2} == {'chair', 'table'}:
                ch = g1 if k1 == 'chair' else g2
                minside = min(ch.bounds[2] - ch.bounds[0], ch.bounds[3] - ch.bounds[1])
                if inter <= 0.13 * minside + 0.002:
                    continue
            if a.get('stack_with') == b.get('id') or b.get('stack_with') == a.get('id'):
                continue
            issues.append(f"Solape {k1} {a.get('id')} / {k2} {b.get('id')} ({inter:.3f} m2)")

    # 3. front clearances
    for kind, it, g in items:
        fz = front_zone(it)
        if fz is None:
            continue
        others = unary_union([walls_only] + [g2 for k2, it2, g2 in items if it2 is not it])
        bad = fz.intersection(others).area
        if bad > 0.01:
            depth = float(it.get('clear'))
            issues.append(f"Frente de {it.get('id')} ({it.get('label','')}) sin despeje de {depth:.2f} m ({bad:.2f} m2 obstruidos)")
        outside = fz.difference(prem).area
        if outside > 0.01:
            issues.append(f"Frente de {it.get('id')} ({it.get('label','')}) cae fuera del local ({outside:.2f} m2)")

    # 4. door swings
    for o in lay.get('new_openings', []):
        sw = door_swing_poly(o)
        if sw is None:
            continue
        others = unary_union([g for k, it, g in items])
        bad = sw.intersection(others).area
        if bad > 0.01:
            issues.append(f"Barrido de puerta {o.get('id')} obstruido ({bad:.2f} m2)")

    # 5. rasterize + routes
    b = prem.bounds
    free, dt, origin = rasterize(prem, all_obs, (b[0] - 0.1, b[1] - 0.1, b[2] + 0.1, b[3] + 0.1))
    routes = []
    for r in lay.get('routes', []):
        (w, where), L = route_width(dt, origin, r['pts'], float(r.get('skip_ends', 0.35)))
        need = float(r.get('min_width', 0.9))
        ok = w + 0.005 >= need
        routes.append({'id': r['id'], 'kind': r.get('kind'), 'label': r.get('label'), 'min_width': round(w, 2),
                       'at': where, 'required': need, 'length': round(L, 2), 'ok': ok})
        if not ok:
            issues.append(f"Ruta {r['id']} ({r.get('label','')}): ancho minimo {w:.2f} m en {where} < {need:.2f} m")
    metrics['routes'] = routes

    pts = lay.get('points', {})
    pairs = lay.get('checks', [])
    bn = []
    for a_name, b_name, need in pairs:
        if a_name in pts and b_name in pts:
            w = widest_path_bottleneck(free, dt, origin, pts[a_name], pts[b_name])
            bn.append({'from': a_name, 'to': b_name, 'bottleneck': round(w, 2), 'required': need, 'ok': w + 0.005 >= need})
            if w + 0.005 < need:
                issues.append(f"Conexion {a_name}->{b_name}: cuello de botella {w:.2f} m < {need:.2f} m")
    metrics['connections'] = bn

    # 6. dirty/clean separation
    rmap = {r['id']: r for r in lay.get('routes', [])}
    dirty = [r for r in lay.get('routes', []) if r.get('kind') == 'dirty']
    clean = [r for r in lay.get('routes', []) if r.get('kind') == 'clean']
    prep_zones = [Polygon(z['poly']) for z in lay.get('zones', []) if z.get('prep')]
    prep_items = unary_union([R(e['rect']).buffer(0.05) for e in lay.get('equipment', [])
                              if e.get('key') in ('mesa_fria', 'mesa_1', 'mesa_2', 'mesa_opt')])
    sep = []
    for d in dirty:
        dl = LineString(d['pts'])
        for c in clean:
            x = dl.intersection(LineString(c['pts']))
            if not x.is_empty:
                sep.append(f"Ruta sucia {d['id']} cruza ruta limpia {c['id']}")
        for z in prep_zones:
            if dl.intersects(z):
                sep.append(f"Ruta sucia {d['id']} atraviesa zona de preparacion")
        if not prep_items.is_empty and dl.distance(prep_items) < 0.3:
            sep.append(f"Ruta sucia {d['id']} pasa a {dl.distance(prep_items):.2f} m de una mesa de preparacion")
    metrics['dirty_clean_conflicts'] = sep
    for s in sep:
        warnings.append(s)

    # 7. required equipment
    missing = [f"{k}: {v}" for k, v in REQUIRED.items() if not find_equipment(lay, k)]
    for m in missing:
        issues.append(f"Falta equipo requerido -> {m}")
    metrics['optional_present'] = [k for k in OPTIONAL if find_equipment(lay, k)]

    # 8. hood coverage
    hoods = find_equipment(lay, 'hood')
    line = [e for k in HOT_LINE for e in find_equipment(lay, k)]
    if hoods and line:
        hg = unary_union([R(h['rect']) for h in hoods])
        lg = unary_union([R(e['rect']) for e in line])
        uncovered = lg.difference(hg).area
        lb = lg.bounds
        hb = hg.bounds
        horiz = (lb[2] - lb[0]) >= (lb[3] - lb[1])
        run = (lb[2] - lb[0]) if horiz else (lb[3] - lb[1])
        overhang = min(lb[0] - hb[0], hb[2] - lb[2]) if horiz else min(lb[1] - hb[1], hb[3] - lb[3])
        metrics['hot_line_length'] = round(run, 2)
        metrics['hood_length'] = round((hb[2] - hb[0]) if horiz else (hb[3] - hb[1]), 2)
        metrics['hood_min_end_overhang'] = round(overhang, 2)
        metrics['hot_line_uncovered_m2'] = round(uncovered, 3)
        if uncovered > 0.01:
            warnings.append(f"Campana no cubre {uncovered:.2f} m2 de la linea caliente (linea {run:.2f} m vs campana {metrics['hood_length']:.2f} m)")
        elif overhang < 0.15 and not any(h.get('closed_ends') for h in hoods):
            warnings.append(f"Voladizo lateral de campana {overhang:.2f} m < 0.15 m tipico")

    # fryer separation from open flame (typ. NFPA 96: 406 mm or baffle)
    flames = [e for k in ('parrilla', 'cocina_4q') for e in find_equipment(lay, k)]
    for fk in ('freidora_1', 'freidora_2'):
        for f in find_equipment(lay, fk):
            for fl in flames:
                dist = R(f['rect']).distance(R(fl['rect']))
                if dist < 0.40 and not f.get('baffle'):
                    warnings.append(f"{fk} a {dist:.2f} m de {fl['key']} (llama abierta): requiere 40 cm o deflector")

    # 9. parrilla visibility
    parr = find_equipment(lay, 'parrilla')
    if parr:
        opq = opaque_obstacles(ex, lay)
        pg = R(parr[0]['rect'])
        tgt = pg.centroid
        seats = seat_points(lay)
        seen = 0
        for sid, sp in seats:
            ray = LineString([sp, tgt])
            blk = opq.difference(pg.buffer(0.01)) if opq is not None else None
            if blk is None or not ray.intersects(blk):
                seen += 1
        metrics['seats_with_parrilla_view'] = seen
        metrics['seats_with_parrilla_view_pct'] = round(100 * seen / max(1, len(seats)), 1)
        ent = pts.get('entrance')
        if ent:
            ray = LineString([ent, (tgt.x, tgt.y)])
            blk = opq.difference(pg.buffer(0.01)) if opq is not None else None
            metrics['parrilla_visible_from_entrance'] = bool(blk is None or not ray.intersects(blk))
            metrics['entrance_to_parrilla_m'] = round(Point(ent).distance(tgt), 2)
        glass = [w for w in lay.get('new_walls', []) if w.get('type') == 'glass_partition']
        if glass:
            gd = min(R(w['rect']).distance(pg) for w in glass)
            metrics['parrilla_to_glass_m'] = round(gd, 2)

    # 10. areas + seats
    zones = []
    for z in lay.get('zones', []):
        zp = Polygon(z['poly']).intersection(prem)
        zones.append({'id': z['id'], 'name': z.get('name'), 'area_m2': round(zp.area, 2)})
    metrics['zones'] = zones
    metrics['seats'] = seat_count(lay)
    metrics['premises_area_m2'] = round(prem.area, 2)
    nw = lay.get('new_walls', [])
    part = [w for w in nw if w.get('role') == 'kitchen_dining_partition']
    if part:
        metrics['new_partition_x'] = round(min(R(w['rect']).bounds[0] for w in part), 3)
        metrics['partition_shift_m'] = round(6.298 - metrics['new_partition_x'], 2)
    return {'issues': issues, 'warnings': warnings, 'metrics': metrics}


def main():
    path = sys.argv[1]
    res = validate(path)
    if '--json' in sys.argv:
        with open(sys.argv[sys.argv.index('--json') + 1], 'w') as f:
            json.dump(res, f, indent=1, ensure_ascii=False)
    m = res['metrics']
    print(f"== {path}")
    print(f"Asientos: {m.get('seats')}   Area local: {m.get('premises_area_m2')} m2   Division nueva X={m.get('new_partition_x')} (corrimiento {m.get('partition_shift_m')} m)")
    for z in m.get('zones', []):
        print(f"  Zona {z['id']:>3} {z['name'] or '':40s} {z['area_m2']:6.2f} m2")
    print(f"Linea caliente {m.get('hot_line_length')} m | campana {m.get('hood_length')} m | voladizo min {m.get('hood_min_end_overhang')} m")
    print(f"Parrilla: vista desde {m.get('seats_with_parrilla_view')} asientos ({m.get('seats_with_parrilla_view_pct')}%), desde entrada={m.get('parrilla_visible_from_entrance')}, a vidrio {m.get('parrilla_to_glass_m')} m")
    for r in m.get('routes', []):
        print(f"  Ruta {r['id']:<18} [{r['kind']}] min {r['min_width']:.2f} m (req {r['required']:.2f}) len {r['length']:.1f} m {'OK' if r['ok'] else 'FALLA'} {r['label'] or ''}")
    for c in m.get('connections', []):
        print(f"  Conexion {c['from']}->{c['to']}: {c['bottleneck']:.2f} m (req {c['required']}) {'OK' if c['ok'] else 'FALLA'}")
    print(f"ISSUES ({len(res['issues'])}):")
    for i in res['issues']:
        print('  x', i)
    print(f"WARNINGS ({len(res['warnings'])}):")
    for w in res['warnings']:
        print('  !', w)
    sys.exit(1 if res['issues'] else 0)


if __name__ == '__main__':
    main()
