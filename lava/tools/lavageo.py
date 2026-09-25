"""Shared geometry helpers for the LAVA test-fit (existing conditions + layout proposals).

Coordinates are metres. Origin: column axis A (X) / axis row 1 (Y). X grows toward the
storefront (east), Y grows toward the service wing (south). Rects are [x0, y0, x1, y1].
"""
import json
import math
import os

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(path):
    with open(path) as f:
        return json.load(f)


def load_existing():
    return load_json(os.path.join(ROOT, 'data', 'existing.json'))


def R(r):
    x0, y0, x1, y1 = r
    return box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def premises(ex):
    return Polygon(ex['premises_polygon'])


def demolished_ids(lay):
    return {d['id'] for d in lay.get('demolish', []) if 'rect' not in d}


def standing_existing_walls(ex, lay):
    """Existing walls that remain (whole-wall demolitions removed, partial ones subtracted)."""
    gone = demolished_ids(lay)
    partial = [R(d['rect']) for d in lay.get('demolish', []) if 'rect' in d]
    out = []
    for w in ex['walls']:
        if w['id'] in gone:
            continue
        g = R(w['rect'])
        for p in partial:
            g = g.difference(p)
        if not g.is_empty:
            out.append((w, g))
    return out


def new_openings_geom(lay):
    return [R(o['rect']) for o in lay.get('new_openings', []) if o.get('rect') and o.get('type') in (
        'door', 'double_acting_door', 'sliding_door', 'service_door', 'opening')]


def item_lists(lay):
    """All physical items that occupy floor area, as (kind, item, geom)."""
    items = []
    for e in lay.get('equipment', []):
        if e.get('overhead'):
            continue
        items.append(('equipment', e, R(e['rect'])))
    for t in lay.get('tables', []):
        items.append(('table', t, R(t['rect'])))
    for c in lay.get('chairs', []):
        items.append(('chair', c, R(c['rect'])))
    for b in lay.get('banquettes', []):
        items.append(('banquette', b, R(b['rect'])))
    return items


def seat_points(lay):
    pts = []
    for c in lay.get('chairs', []):
        g = R(c['rect'])
        pts.append((c.get('id'), g.centroid))
    for b in lay.get('banquettes', []):
        g = R(b['rect'])
        n = int(b.get('seats', 0))
        x0, y0, x1, y1 = g.bounds
        horiz = (x1 - x0) >= (y1 - y0)
        for i in range(n):
            f = (i + 0.5) / n
            if horiz:
                pts.append((f"{b.get('id')}#{i+1}", Point(x0 + f * (x1 - x0), (y0 + y1) / 2)))
            else:
                pts.append((f"{b.get('id')}#{i+1}", Point((x0 + x1) / 2, y0 + f * (y1 - y0))))
    return pts


def seat_count(lay):
    return len(lay.get('chairs', [])) + sum(int(b.get('seats', 0)) for b in lay.get('banquettes', []))


def front_zone(e):
    """Rectangle of required clear floor in front of an item's working face."""
    f = e.get('front')
    c = float(e.get('clear', 0) or 0)
    if not f or f == 'none' or c <= 0:
        return None
    x0, y0, x1, y1 = e['rect']
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    if f == 'N':
        return box(x0, y0 - c, x1, y0)
    if f == 'S':
        return box(x0, y1, x1, y1 + c)
    if f == 'W':
        return box(x0 - c, y0, x0, y1)
    if f == 'E':
        return box(x1, y0, x1 + c, y1)
    return None


def door_swing_poly(o, steps=16):
    """Quarter-circle swing polygon from hinge, leaf length, closed/open tip points."""
    if 'hinge' not in o or 'swing_to' not in o or 'closed_to' not in o:
        return None
    hx, hy = o['hinge']
    ax, ay = o['closed_to']
    bx, by = o['swing_to']
    r = math.hypot(ax - hx, ay - hy)
    a0 = math.atan2(ay - hy, ax - hx)
    a1 = math.atan2(by - hy, bx - hx)
    d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    pts = [(hx, hy)]
    for i in range(steps + 1):
        a = a0 + d * i / steps
        pts.append((hx + r * math.cos(a), hy + r * math.sin(a)))
    return Polygon(pts)


def blocking_obstacles(ex, lay, include_items=True):
    """Union of everything that blocks walking inside the premises."""
    prem = premises(ex)
    obs = []
    for w, g in standing_existing_walls(ex, lay):
        obs.append(g)
    for c in ex['columns']:
        obs.append(R(c['rect']))
    openings = new_openings_geom(lay)
    for w in lay.get('new_walls', []):
        g = R(w['rect'])
        for o in openings:
            g = g.difference(o.buffer(0.001))
        obs.append(g)
    if include_items:
        for kind, it, g in item_lists(lay):
            obs.append(g)
    return prem, unary_union(obs)


def opaque_obstacles(ex, lay, min_h=1.4):
    """Obstacles that block line of sight at seated eye height (~1.2 m)."""
    obs = []
    for w, g in standing_existing_walls(ex, lay):
        obs.append(g)
    for c in ex['columns']:
        obs.append(R(c['rect']))
    for w in lay.get('new_walls', []):
        if w.get('type') in ('glass_partition', 'low_wall', 'glass'):
            continue
        obs.append(R(w['rect']))
    for e in lay.get('equipment', []):
        if e.get('overhead'):
            continue
        if float(e.get('h', 0) or 0) >= min_h:
            obs.append(R(e['rect']))
    return unary_union(obs) if obs else None


def find_equipment(lay, key):
    return [e for e in lay.get('equipment', []) if e.get('key') == key]
