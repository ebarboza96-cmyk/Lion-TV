"""Generate the LAVA conceptual plan sheets (SVG, A2 landscape, 1:50) from existing.json + layout.json.

Usage:
    python3 tools/plan_svg.py [data/layout.json] [--validation data/validation.json]

Writes plan/lava_A101_planta.svg, plan/lava_A102_demolicion.svg, plan/lava_A103_flujos.svg and
plan/lava_plan.svg (copy of A-101, embedded by the walkthrough app).
"""
import datetime
import json
import math
import os
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(__file__))
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from lavageo import (R, ROOT, blocking_obstacles, door_swing_poly, front_zone, load_existing, load_json,
                     seat_count, standing_existing_walls)

SHEET_W, SHEET_H = 594.0, 420.0  # mm, A2 landscape
S = 20.0                         # 1:50 -> 1 m = 20 mm
VIEW = (-1.55, -1.45, 16.95, 12.35)  # model window (m)
DRAW = (14.0, 16.0)              # sheet mm of model VIEW top-left
FONT = "Figtree, 'Liberation Sans', Arial, sans-serif"
MONO = "'JetBrains Mono', 'DejaVu Sans Mono', monospace"

COL = {
    'existing_fill': '#9b9b98', 'existing_stroke': '#5c5c58',
    'column': '#4a4a47', 'demolish': '#d62828', 'new': '#111111', 'glass': '#35b6e8',
    'fire': ('#f6a04d', '#a24f00'), 'cold': ('#86b3ee', '#1a55b0'), 'prep': ('#bcd5f6', '#1a55b0'),
    'wash': ('#bde6ea', '#17737a'), 'storage': ('#e7d8b5', '#75602e'), 'smoker': ('#e46a2e', '#6e2508'),
    'bar': ('#d7c6ec', '#553688'), 'delivery': ('#f5e27f', '#7d6d0c'), 'misc': ('#dcdcdc', '#555555'),
    'hood': ('none', '#b35900'),
    'table': ('#b7dfb0', '#2b7a31'), 'chair': ('#dff1da', '#2b7a31'), 'banquette': ('#8fcb86', '#1f5f25'),
}
ZONE_FILL = {'A': '#2f6fd0', 'B': '#f07c14', 'C': '#7a4fb8', 'D': '#2e9a3a', 'E': '#c2410c'}
ROUTE = {'clean': ('#1f63c6', None), 'dirty': ('#d62828', '5 3'), 'guest': ('#2e9a3a', None),
         'server': ('#7a4fb8', '1.5 2'), 'delivery': ('#b39b00', '6 2 1.5 2'), 'fuel': ('#8c4a1e', '2 2')}
ROUTE_NAME = {'clean': 'Flujo limpio (almacén → prep → cocción → pase)', 'dirty': 'Flujo sucio (salón → lavado)',
              'guest': 'Clientes', 'server': 'Meseros (pase → mesas)', 'delivery': 'Delivery / repartidores',
              'fuel': 'Combustible sólido / cenizas'}


def sx(x):
    return DRAW[0] + (x - VIEW[0]) * S


def sy(y):
    return DRAW[1] + (y - VIEW[1]) * S


def f(v):
    return f"{v:.2f}"


def pts_attr(pts):
    return ' '.join(f"{f(sx(x))},{f(sy(y))}" for x, y in pts)


def rect_el(r, fill, stroke, sw=0.25, dash=None, extra=''):
    x0, y0, x1, y1 = r
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return (f'<rect x="{f(sx(x0))}" y="{f(sy(y0))}" width="{f((x1-x0)*S)}" height="{f((y1-y0)*S)}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d} {extra}/>')


def poly_el(geom, fill, stroke, sw=0.25, extra=''):
    out = []
    for g in (getattr(geom, 'geoms', None) or [geom]):
        if g.is_empty or g.geom_type != 'Polygon':
            continue
        out.append(f'<polygon points="{pts_attr(list(g.exterior.coords))}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')
    return ''.join(out)


def text(x, y, s, size=2.2, anchor='middle', weight='400', fill='#1b1b1b', family=FONT, rot=0, extra=''):
    t = f' transform="rotate({rot} {f(x)} {f(y)})"' if rot else ''
    return (f'<text x="{f(x)}" y="{f(y)}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}" fill="{fill}"{t} {extra}>{escape(s)}</text>')


def mtext(x, y, lines, size=2.2, anchor='middle', weight='400', fill='#1b1b1b', lh=1.22, family=FONT, rot=0):
    n = len(lines)
    y0 = y - (n - 1) * size * lh / 2 + size * 0.35
    return ''.join(text(x, y0 + i * size * lh, ln, size, anchor, weight, fill, family, rot) for i, ln in enumerate(lines))


class Sheet:
    def __init__(self, ex, lay, val, kind):
        self.ex, self.lay, self.val, self.kind = ex, lay, val or {}, kind
        self.m = (self.val.get('metrics') or {})
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    # ------------------------------------------------------------------ primitives
    def dim(self, a, b, off, label=None, size=2.3, color='#222', side=1):
        """Aligned dimension between model points a,b, offset `off` metres to the left of a->b."""
        (x1, y1), (x2, y2) = a, b
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-6:
            return
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        nx, ny = -uy, ux
        p1 = (x1 + nx * off, y1 + ny * off)
        p2 = (x2 + nx * off, y2 + ny * off)
        g = [f'<g class="dim" stroke="{color}" fill="none" stroke-width="0.18">']
        ext = 0.12 if off > 0 else -0.12
        g.append(f'<line x1="{f(sx(x1 + nx * 0.06 * (1 if off > 0 else -1)))}" y1="{f(sy(y1 + ny * 0.06 * (1 if off > 0 else -1)))}" '
                 f'x2="{f(sx(p1[0] + nx * ext))}" y2="{f(sy(p1[1] + ny * ext))}"/>')
        g.append(f'<line x1="{f(sx(x2 + nx * 0.06 * (1 if off > 0 else -1)))}" y1="{f(sy(y2 + ny * 0.06 * (1 if off > 0 else -1)))}" '
                 f'x2="{f(sx(p2[0] + nx * ext))}" y2="{f(sy(p2[1] + ny * ext))}"/>')
        g.append(f'<line x1="{f(sx(p1[0]))}" y1="{f(sy(p1[1]))}" x2="{f(sx(p2[0]))}" y2="{f(sy(p2[1]))}"/>')
        for p in (p1, p2):  # architectural slash ticks
            t = 0.09
            g.append(f'<line stroke-width="0.35" x1="{f(sx(p[0] - (ux + nx) * t))}" y1="{f(sy(p[1] - (uy + ny) * t))}" '
                     f'x2="{f(sx(p[0] + (ux + nx) * t))}" y2="{f(sy(p[1] + (uy + ny) * t))}"/>')
        g.append('</g>')
        lbl = label if label is not None else f"{L:.2f}"
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ang = math.degrees(math.atan2(uy, ux))
        if ang > 90 or ang <= -90:
            ang += 180
        tx, ty = sx(mx) + (-math.sin(math.radians(ang))) * 0.9 * side, sy(my) - math.cos(math.radians(ang)) * 0.9 * side
        g.append(text(tx, ty, lbl, size, family=MONO, fill=color, rot=ang, extra='paint-order="stroke" stroke="#fff" stroke-width="0.8"'))
        self.add(''.join(g))

    def callout(self, anchor, at, lines, color='#1b1b1b', size=2.1, box_fill='#ffffff', weight='600', width=None):
        ax, ay = sx(anchor[0]), sy(anchor[1])
        bx, by = sx(at[0]), sy(at[1])
        w = width or max(len(s) for s in lines) * size * 0.56 + 3
        h = len(lines) * size * 1.25 + 2.2
        # leader to nearest box edge midpoint
        ex_ = bx if abs(ax - bx) < w / 2 else (bx - w / 2 if ax < bx else bx + w / 2)
        ey_ = by if abs(ax - bx) >= w / 2 else (by - h / 2 if ay < by else by + h / 2)
        self.add(f'<g class="callout"><polyline points="{f(ax)},{f(ay)} {f(ex_)},{f(ey_)}" fill="none" stroke="{color}" stroke-width="0.25"/>'
                 f'<circle cx="{f(ax)}" cy="{f(ay)}" r="0.6" fill="{color}"/>'
                 f'<rect x="{f(bx - w/2)}" y="{f(by - h/2)}" width="{f(w)}" height="{f(h)}" rx="0.6" fill="{box_fill}" stroke="{color}" stroke-width="0.3"/>'
                 + mtext(bx, by, lines, size, weight=weight, fill=color) + '</g>')

    # ------------------------------------------------------------------ layers
    def defs(self):
        return ('<defs>'
                '<pattern id="hatch-ex" patternUnits="userSpaceOnUse" width="1.2" height="1.2" patternTransform="rotate(45)">'
                '<rect width="1.2" height="1.2" fill="#a8a8a5"/><line x1="0" y1="0" x2="0" y2="1.2" stroke="#6e6e6a" stroke-width="0.25"/></pattern>'
                '<pattern id="hatch-smoker" patternUnits="userSpaceOnUse" width="1.4" height="1.4" patternTransform="rotate(45)">'
                '<rect width="1.4" height="1.4" fill="#f09461"/><line x1="0" y1="0" x2="0" y2="1.4" stroke="#6e2508" stroke-width="0.3"/></pattern>'
                '<pattern id="hatch-demo" patternUnits="userSpaceOnUse" width="1.6" height="1.6" patternTransform="rotate(-45)">'
                '<rect width="1.6" height="1.6" fill="#fff4f4"/><line x1="0" y1="0" x2="0" y2="1.6" stroke="#f1a3a3" stroke-width="0.35"/></pattern>'
                '<marker id="arr" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="4.5" markerHeight="4.5" orient="auto-start-reverse">'
                '<path d="M0,0 L6,3 L0,6 z" fill="context-stroke"/></marker>'
                + ''.join(f'<marker id="arr-{k}" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="4" markerHeight="4" orient="auto">'
                          f'<path d="M0,0 L6,3 L0,6 z" fill="{c}"/></marker>' for k, (c, _) in ROUTE.items())
                + '</defs>')

    def layer_zones(self, opacity=0.10):
        g = ['<g id="zones">']
        for z in self.lay.get('zones', []):
            zid = z['id'][0]
            c = ZONE_FILL.get(zid, '#999')
            g.append(f'<polygon points="{pts_attr(z["poly"])}" fill="{c}" fill-opacity="{opacity}" stroke="{c}" stroke-opacity="0.45" stroke-width="0.3" stroke-dasharray="1.2 1"/>')
        g.append('</g>')
        self.add(''.join(g))

    def zone_labels(self):
        prem = Polygon(self.ex['premises_polygon'])
        g = ['<g id="zone-labels">']
        for z in self.lay.get('zones', []):
            zid = z['id'][0]
            c = ZONE_FILL.get(zid, '#999')
            poly = Polygon(z['poly']).intersection(prem)
            if poly.is_empty:
                continue
            lp = z.get('label_at')
            if lp:
                px, py = lp
            else:
                # largest free spot in zone for the label
                items = unary_union([R(e['rect']) for e in self.lay.get('equipment', []) if not e.get('overhead')] +
                                    [R(t['rect']) for t in self.lay.get('tables', [])] + [R(c_['rect']) for c_ in self.lay.get('chairs', [])])
                free = poly.difference(items)
                p = free.representative_point() if not free.is_empty else poly.representative_point()
                px, py = p.x, p.y
            area = poly.area
            g.append(f'<circle cx="{f(sx(px))}" cy="{f(sy(py) - 1.2)}" r="3.1" fill="{c}"/>')
            g.append(text(sx(px), sy(py) - 0.1, zid, 3.6, weight='800', fill='#ffffff'))
            g.append(text(sx(px), sy(py) + 4.3, z.get('short', z.get('name', '')).upper(), 1.9, weight='700', fill=c))
            g.append(text(sx(px), sy(py) + 6.6, f"≈ {area:.1f} m²", 1.8, family=MONO, fill=c))
        g.append('</g>')
        self.add(''.join(g))

    def layer_existing(self, show_demo=True, faint=False):
        ex, lay = self.ex, self.lay
        g = ['<g id="existing">']
        st = ex['stair']
        g.append(rect_el(st['outline'], '#f3f3f1', '#b5b5b0', 0.2))
        for fl in st['flights']:
            x0, y0, x1, y1 = fl
            n = int(round((y1 - y0) / st['tread']))
            for i in range(n + 1):
                yy = y0 + i * st['tread']
                g.append(f'<line x1="{f(sx(x0))}" y1="{f(sy(yy))}" x2="{f(sx(x1))}" y2="{f(sy(yy))}" stroke="#c4c4bf" stroke-width="0.15"/>')
        ox = st['outline']
        g.append(text(sx((ox[0] + ox[2]) / 2), sy(10.6), 'ESCALERA EXISTENTE', 2.2, weight='700', fill='#8b8b86'))
        g.append(text(sx((ox[0] + ox[2]) / 2), sy(10.6) + 2.8, '(edificio · fuera del local · no se modifica)', 1.7, fill='#8b8b86'))
        for s in ex['shafts']:
            x0, y0, x1, y1 = s['rect']
            g.append(rect_el(s['rect'], '#ffffff', '#6e6e6a', 0.2))
            g.append(f'<path d="M{f(sx(x0))},{f(sy(y0))} L{f(sx(x1))},{f(sy(y1))} M{f(sx(x0))},{f(sy(y1))} L{f(sx(x1))},{f(sy(y0))}" stroke="#8a8a85" stroke-width="0.15"/>')
        for w, geom in standing_existing_walls(ex, lay):
            g.append(poly_el(geom, 'url(#hatch-ex)' if not faint else '#c8c8c5', COL['existing_stroke'], 0.25))
        for c in ex['columns']:
            g.append(rect_el(c['rect'], COL['column'], '#222', 0.25))
        for gl in ex['glazing']:
            x0, y0, x1, y1 = gl['rect']
            g.append(rect_el(gl['rect'], '#e3f6ff', COL['glass'], 0.3))
            if (x1 - x0) < (y1 - y0):
                g.append(f'<line x1="{f(sx((x0+x1)/2))}" y1="{f(sy(y0))}" x2="{f(sx((x0+x1)/2))}" y2="{f(sy(y1))}" stroke="{COL["glass"]}" stroke-width="0.35"/>')
            else:
                g.append(f'<line x1="{f(sx(x0))}" y1="{f(sy((y0+y1)/2))}" x2="{f(sx(x1))}" y2="{f(sy((y0+y1)/2))}" stroke="{COL["glass"]}" stroke-width="0.35"/>')
        # main entrance double door (swing inward)
        for hy, sign in ((1.643, 1), (3.643, -1)):
            hx = 16.3
            r = 0.97
            g.append(f'<line x1="{f(sx(hx))}" y1="{f(sy(hy))}" x2="{f(sx(hx - r))}" y2="{f(sy(hy))}" stroke="#333" stroke-width="0.3"/>')
            g.append(f'<path d="M{f(sx(hx - r))},{f(sy(hy))} A{f(r*S)},{f(r*S)} 0 0 {0 if sign > 0 else 1} {f(sx(hx))},{f(sy(hy + sign * r))}" '
                     f'fill="none" stroke="#555" stroke-width="0.18" stroke-dasharray="0.8 0.6"/>')
        g.append('</g>')
        self.add(''.join(g))

    def layer_demolish(self):
        ex, lay = self.ex, self.lay
        ids = {d['id']: d for d in lay.get('demolish', []) if 'rect' not in d}
        g = ['<g id="demolish">']
        for w in ex['walls']:
            if w['id'] in ids:
                g.append(rect_el(w['rect'], 'url(#hatch-demo)', COL['demolish'], 0.4, dash='1.2 0.8'))
        for d in lay.get('demolish', []):
            if 'rect' in d:
                g.append(rect_el(d['rect'], 'url(#hatch-demo)', COL['demolish'], 0.4, dash='1.2 0.8'))
        g.append('</g>')
        self.add(''.join(g))

    def layer_new(self):
        lay = self.lay
        g = ['<g id="new-walls">']
        openings = [o for o in lay.get('new_openings', []) if o.get('rect')]
        for w in lay.get('new_walls', []):
            geom = R(w['rect'])
            for o in openings:
                if o.get('type') in ('door', 'double_acting_door', 'sliding_door', 'service_door', 'opening'):
                    geom = geom.difference(R(o['rect']))
            g.append(poly_el(geom, COL['new'], '#000', 0.2))
            if w.get('type') == 'glass_partition':
                x0, y0, x1, y1 = w['rect']
                vert = (x1 - x0) < (y1 - y0)
                for part in (getattr(geom, 'geoms', None) or [geom]):
                    bx0, by0, bx1, by1 = part.bounds
                    if vert:
                        g.append(f'<line x1="{f(sx((x0+x1)/2))}" y1="{f(sy(by0 + 0.03))}" x2="{f(sx((x0+x1)/2))}" y2="{f(sy(by1 - 0.03))}" stroke="{COL["glass"]}" stroke-width="0.55"/>')
                    else:
                        g.append(f'<line x1="{f(sx(bx0 + 0.03))}" y1="{f(sy((y0+y1)/2))}" x2="{f(sx(bx1 - 0.03))}" y2="{f(sy((y0+y1)/2))}" stroke="{COL["glass"]}" stroke-width="0.55"/>')
        for o in lay.get('new_openings', []):
            t = o.get('type')
            if not o.get('rect'):
                continue
            x0, y0, x1, y1 = o['rect']
            cond = o.get('conditional')
            stroke = '#b00020' if cond else '#111'
            if t == 'pass_window':
                g.append(rect_el(o['rect'], '#ffffff', '#111', 0.2))
                g.append(rect_el(o['rect'], 'none', COL['glass'], 0.2, dash='0.6 0.4'))
                continue
            if t in ('door', 'service_door') and 'hinge' in o:
                hx, hy = o['hinge']
                bx, by = o['swing_to']
                cx, cy = o['closed_to']
                r = math.hypot(cx - hx, cy - hy)
                sw = door_swing_poly(o)
                a0 = math.atan2(cy - hy, cx - hx)
                a1 = math.atan2(by - hy, bx - hx)
                d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
                sweep = 1 if d > 0 else 0
                g.append(f'<line x1="{f(sx(hx))}" y1="{f(sy(hy))}" x2="{f(sx(bx))}" y2="{f(sy(by))}" stroke="{stroke}" stroke-width="0.35"/>')
                g.append(f'<path d="M{f(sx(cx))},{f(sy(cy))} A{f(r*S)},{f(r*S)} 0 0 {sweep} {f(sx(bx))},{f(sy(by))}" fill="none" stroke="{stroke}" stroke-width="0.18" stroke-dasharray="0.8 0.6"/>')
                if cond:
                    g.append(rect_el(o['rect'], 'none', stroke, 0.35, dash='1 0.6'))
            elif t == 'double_acting_door':
                vert = (x1 - x0) < (y1 - y0)
                if vert:
                    cx_ = (x0 + x1) / 2
                    g.append(f'<line x1="{f(sx(cx_ - 0.35))}" y1="{f(sy(y0 + 0.05))}" x2="{f(sx(cx_ + 0.35))}" y2="{f(sy(y1 - 0.05))}" stroke="#111" stroke-width="0.3"/>')
                    g.append(f'<line x1="{f(sx(cx_ + 0.35))}" y1="{f(sy(y0 + 0.05))}" x2="{f(sx(cx_ - 0.35))}" y2="{f(sy(y1 - 0.05))}" stroke="#111" stroke-width="0.3"/>')
                else:
                    cy_ = (y0 + y1) / 2
                    g.append(f'<line x1="{f(sx(x0 + 0.05))}" y1="{f(sy(cy_ - 0.35))}" x2="{f(sx(x1 - 0.05))}" y2="{f(sy(cy_ + 0.35))}" stroke="#111" stroke-width="0.3"/>')
                    g.append(f'<line x1="{f(sx(x0 + 0.05))}" y1="{f(sy(cy_ + 0.35))}" x2="{f(sx(x1 - 0.05))}" y2="{f(sy(cy_ - 0.35))}" stroke="#111" stroke-width="0.3"/>')
            elif t == 'sliding_door':
                g.append(rect_el(o['rect'], 'none', stroke, 0.3, dash='1 0.5'))
            if o.get('label'):
                g.append(text(sx((x0 + x1) / 2) + 2.4, sy((y0 + y1) / 2), o['label'], 1.8, weight='700', fill=stroke, anchor='start'))
        g.append('</g>')
        self.add(''.join(g))

    def layer_equipment(self, faint=False, tags=True):
        lay = self.lay
        g = ['<g id="equipment">']
        hoods = []
        for e in lay.get('equipment', []):
            cat = e.get('cat', 'misc')
            if e.get('overhead'):
                hoods.append(e)
                continue
            fill, stroke = COL.get(cat, COL['misc']) if cat in COL else COL['misc']
            if faint:
                fill, stroke = '#efefed', '#b6b6b1'
            if cat == 'smoker' and e.get('key') == 'smoker' and not faint:
                fill = 'url(#hatch-smoker)'
            g.append(rect_el(e['rect'], fill, stroke, 0.3))
            x0, y0, x1, y1 = e['rect']
            x0, x1 = min(x0, x1), max(x0, x1)
            y0, y1 = min(y0, y1), max(y0, y1)
            # front edge marker (working face)
            fr = e.get('front')
            if fr in ('N', 'S', 'E', 'W') and not faint:
                if fr == 'N':
                    seg = (x0 + 0.05, y0 + 0.04, x1 - 0.05, y0 + 0.04)
                elif fr == 'S':
                    seg = (x0 + 0.05, y1 - 0.04, x1 - 0.05, y1 - 0.04)
                elif fr == 'W':
                    seg = (x0 + 0.04, y0 + 0.05, x0 + 0.04, y1 - 0.05)
                else:
                    seg = (x1 - 0.04, y0 + 0.05, x1 - 0.04, y1 - 0.05)
                g.append(f'<line x1="{f(sx(seg[0]))}" y1="{f(sy(seg[1]))}" x2="{f(sx(seg[2]))}" y2="{f(sy(seg[3]))}" stroke="{stroke}" stroke-width="0.5"/>')
            if tags and not faint:
                w, h = (x1 - x0) * S, (y1 - y0) * S
                tag = e.get('tag') or e.get('id')
                lbl = e.get('short') or e.get('label', '')
                rot = -90 if h > w * 1.25 else 0
                long_side = max(w, h)
                if min(w, h) >= 5.5:
                    if lbl and long_side >= len(lbl) * 1.05 + 4:
                        if rot:
                            g.append(text(sx((x0 + x1) / 2) - 0.2, sy((y0 + y1) / 2), tag, 2.1, weight='800', fill=stroke, rot=rot))
                            g.append(text(sx((x0 + x1) / 2) + 2.3, sy((y0 + y1) / 2), lbl, 1.8, fill='#2b2b2b', rot=rot))
                        else:
                            g.append(text(sx((x0 + x1) / 2), sy((y0 + y1) / 2) - 0.2, tag, 2.1, weight='800', fill=stroke))
                            g.append(text(sx((x0 + x1) / 2), sy((y0 + y1) / 2) + 2.3, lbl, 1.8, fill='#2b2b2b'))
                    else:
                        g.append(text(sx((x0 + x1) / 2), sy((y0 + y1) / 2) + 0.75, tag, 2.1, weight='800', fill=stroke, rot=rot))
                else:
                    g.append(text(sx((x0 + x1) / 2), sy((y0 + y1) / 2) + 0.6, tag, 1.7, weight='800', fill=stroke, rot=rot))
                if e.get('tbv'):
                    g.append(f'<circle cx="{f(sx(x1) - 0.9)}" cy="{f(sy(y0) + 0.9)}" r="0.55" fill="#b00020"/>')
        for hd in hoods:
            fill, stroke = COL['hood']
            if faint:
                stroke = '#d9a36f'
            g.append(rect_el(hd['rect'], 'none', stroke, 0.45, dash='2 0.8'))
            x0, y0, x1, y1 = hd['rect']
            g.append(f'<path d="M{f(sx(x0))},{f(sy(y0))} L{f(sx(x1))},{f(sy(y1))} M{f(sx(x0))},{f(sy(y1))} L{f(sx(x1))},{f(sy(y0))}" stroke="{stroke}" stroke-width="0.15" stroke-dasharray="1 0.8" fill="none"/>')
        g.append('</g>')
        self.add(''.join(g))

    def layer_furniture(self, faint=False):
        lay = self.lay
        g = ['<g id="furniture">']
        tf, ts = COL['table'] if not faint else ('#eeeeec', '#bdbdb8')
        cf, cs = COL['chair'] if not faint else ('#f4f4f2', '#c6c6c1')
        bf, bs = COL['banquette'] if not faint else ('#e8e8e5', '#bdbdb8')
        for b in lay.get('banquettes', []):
            x0, y0, x1, y1 = b['rect']
            g.append(rect_el(b['rect'], bf, bs, 0.3, extra='rx="0.8"'))
            back = b.get('back')
            if back in ('N', 'S', 'E', 'W'):
                t = 0.13
                r = {'N': (x0, y0, x1, y0 + t), 'S': (x0, y1 - t, x1, y1), 'W': (x0, y0, x0 + t, y1), 'E': (x1 - t, y0, x1, y1)}[back]
                g.append(rect_el(r, bs, bs, 0.1))
            if not faint:
                n = int(b.get('seats', 0))
                horiz = (x1 - x0) >= (y1 - y0)
                for i in range(1, n):
                    fr_ = i / n
                    if horiz:
                        xx = x0 + fr_ * (x1 - x0)
                        g.append(f'<line x1="{f(sx(xx))}" y1="{f(sy(y0) + 0.8)}" x2="{f(sx(xx))}" y2="{f(sy(y1) - 0.8)}" stroke="{bs}" stroke-width="0.12" stroke-dasharray="0.5 0.5"/>')
                    else:
                        yy = y0 + fr_ * (y1 - y0)
                        g.append(f'<line x1="{f(sx(x0) + 0.8)}" y1="{f(sy(yy))}" x2="{f(sx(x1) - 0.8)}" y2="{f(sy(yy))}" stroke="{bs}" stroke-width="0.12" stroke-dasharray="0.5 0.5"/>')
        for t in lay.get('tables', []):
            g.append(rect_el(t['rect'], tf, ts, 0.3, extra='rx="0.4"'))
        for c in lay.get('chairs', []):
            x0, y0, x1, y1 = c['rect']
            g.append(rect_el(c['rect'], cf, cs, 0.25, extra='rx="1.1"'))
            fc = c.get('facing')
            if not fc:
                # infer: back is on the side away from its table
                tbl = next((t for t in lay.get('tables', []) if t['id'] == c.get('table')), None)
                if tbl:
                    tc = R(tbl['rect']).centroid
                    cc = R(c['rect']).centroid
                    dx, dy = tc.x - cc.x, tc.y - cc.y
                    fc = ('E' if dx > 0 else 'W') if abs(dx) > abs(dy) else ('S' if dy > 0 else 'N')
            if fc:
                t_ = 0.07
                r = {'S': (x0 + 0.04, y0, x1 - 0.04, y0 + t_), 'N': (x0 + 0.04, y1 - t_, x1 - 0.04, y1),
                     'E': (x0, y0 + 0.04, x0 + t_, y1 - 0.04), 'W': (x1 - t_, y0 + 0.04, x1, y1 - 0.04)}[fc]
                g.append(rect_el(r, cs, cs, 0.1))
        if not faint:
            for t in lay.get('tables', []):
                x0, y0, x1, y1 = t['rect']
                g.append(text(sx((x0 + x1) / 2), sy((y0 + y1) / 2) + 0.6, t.get('tag', t['id']), 1.5, weight='700', fill='#1f5f25'))
        g.append('</g>')
        self.add(''.join(g))

    def layer_routes(self, width=0.9, opacity=0.85, tags=True):
        lay = self.lay
        g = ['<g id="routes">']
        rinfo = {r['id']: r for r in (self.m.get('routes') or [])}
        for r in lay.get('routes', []):
            c, dash = ROUTE.get(r.get('kind'), ('#333', None))
            d = f' stroke-dasharray="{dash}"' if dash else ''
            g.append(f'<polyline points="{pts_attr(r["pts"])}" fill="none" stroke="{c}" stroke-width="{width}" stroke-opacity="{opacity}" '
                     f'stroke-linecap="round" stroke-linejoin="round"{d} marker-end="url(#arr-{r.get("kind")})"/>')
            if tags and r['id'] in rinfo and rinfo[r['id']].get('at'):
                at = rinfo[r['id']]['at']
                w = rinfo[r['id']]['min_width']
                x, y = sx(at[0]), sy(at[1])
                g.append(f'<g><rect x="{f(x - 5.2)}" y="{f(y - 2.1)}" width="10.4" height="4.2" rx="2.1" fill="#fff" stroke="{c}" stroke-width="0.35"/>'
                         + text(x, y + 0.75, f"↔ {w:.2f}", 2.0, family=MONO, weight='700', fill=c) + '</g>')
        g.append('</g>')
        self.add(''.join(g))

    def grid_axes(self):
        g = ['<g id="axes" font-family="' + FONT + '">']
        for name, x in (('A', 0.0), ('B', 7.8), ('C', 16.3)):
            g.append(f'<line x1="{f(sx(x))}" y1="{f(sy(-1.05))}" x2="{f(sx(x))}" y2="{f(sy(-0.62))}" stroke="#777" stroke-width="0.15" stroke-dasharray="1.5 0.6 0.3 0.6"/>')
            g.append(f'<circle cx="{f(sx(x))}" cy="{f(sy(-1.2))}" r="2.6" fill="#fff" stroke="#555" stroke-width="0.3"/>')
            g.append(text(sx(x), sy(-1.2) + 1.1, name, 3.0, weight='700', fill='#444'))
        for name, y in (('1', 0.0), ('2', 8.5)):
            g.append(f'<line x1="{f(sx(-1.3))}" y1="{f(sy(y))}" x2="{f(sx(-0.95))}" y2="{f(sy(y))}" stroke="#777" stroke-width="0.15"/>')
            g.append(f'<circle cx="{f(sx(-1.35) - 1.3)}" cy="{f(sy(y))}" r="2.6" fill="#fff" stroke="#555" stroke-width="0.3"/>')
            g.append(text(sx(-1.35) - 1.3, sy(y) + 1.1, name, 3.0, weight='700', fill='#444'))
        g.append('</g>')
        self.add(''.join(g))

    # ------------------------------------------------------------------ sheet furniture
    def frame_and_titleblock(self, title, subtitle, number):
        W, H = SHEET_W, SHEET_H
        g = [f'<rect x="5" y="5" width="{W-10}" height="{H-10}" fill="none" stroke="#111" stroke-width="0.6"/>',
             f'<line x1="436" y1="5" x2="436" y2="{H-5}" stroke="#111" stroke-width="0.35"/>']
        # title block bottom-right
        tb_y = H - 62
        g.append(f'<rect x="436" y="{tb_y}" width="{W-441}" height="57" fill="#141210"/>')
        g.append(text(442, tb_y + 11, 'LΛVΛ', 9.5, anchor='start', weight='800', fill='#ece5d8', family="'Big Shoulders Display', 'Liberation Sans', Arial, sans-serif", extra='letter-spacing="1.5"'))
        g.append(text(442, tb_y + 16.5, 'CONTEMPORARY FIRE & BBQ', 2.3, anchor='start', weight='600', fill='#ff7a1a', extra='letter-spacing="0.6"'))
        g.append(text(442, tb_y + 23.5, 'Local ex-Marna\'s · Terrazas Lindora, Santa Ana', 2.2, anchor='start', fill='#ece5d8'))
        g.append(text(442, tb_y + 30.5, title, 3.1, anchor='start', weight='700', fill='#ffffff'))
        g.append(text(442, tb_y + 35.5, subtitle, 2.0, anchor='start', fill='#cfc6b8'))
        g.append(text(442, tb_y + 42, 'TEST-FIT CONCEPTUAL · NO ES PLANO CONSTRUCTIVO', 2.1, anchor='start', weight='700', fill='#ff7a1a'))
        g.append(text(442, tb_y + 47, 'Base geométrica: PDF Marna\'s Rev8 Opción 1 (1:50). Todo a validar por arquitecto/ingeniería.', 1.6, anchor='start', fill='#b9b0a2'))
        g.append(text(442, tb_y + 51.5, f"Escala 1:50 en A2 · cotas en metros · {datetime.date(2026, 9, 25).isoformat()}", 1.7, anchor='start', fill='#b9b0a2', family=MONO))
        g.append(f'<rect x="{W-40}" y="{tb_y + 22}" width="30" height="30" fill="none" stroke="#ece5d8" stroke-width="0.35"/>')
        g.append(text(W - 25, tb_y + 30, 'LÁMINA', 1.8, fill='#b9b0a2'))
        g.append(text(W - 25, tb_y + 42, number, 7.0, weight='800', fill='#ffffff'))
        # scale bar under drawing
        x0, y0 = sx(-1.2), sy(12.05)
        seg = ['<g id="scalebar">']
        for i in range(5):
            seg.append(f'<rect x="{f(x0 + i*S)}" y="{f(y0)}" width="{S}" height="1.3" fill="{"#111" if i % 2 == 0 else "#fff"}" stroke="#111" stroke-width="0.2"/>')
            seg.append(text(x0 + i * S, y0 + 4.2, str(i), 1.8, family=MONO))
        seg.append(text(x0 + 5 * S, y0 + 4.2, '5 m', 1.8, family=MONO))
        seg.append(text(x0 + 5 * S + 4, y0 + 1.4, '1:50', 2.0, anchor='start', weight='700'))
        seg.append('</g>')
        g.extend(seg)
        # orientation note
        nx, ny = sx(15.9), sy(11.3)
        g.append(f'<g id="north"><circle cx="{f(nx)}" cy="{f(ny)}" r="5" fill="none" stroke="#333" stroke-width="0.3"/>'
                 f'<path d="M{f(nx)},{f(ny-4.2)} L{f(nx+2)},{f(ny+2.5)} L{f(nx)},{f(ny+1.2)} L{f(nx-2)},{f(ny+2.5)} z" fill="#333"/>'
                 + text(nx, ny + 8.5, 'Orientación del PDF original', 1.6, fill='#555')
                 + text(nx, ny + 10.6, '(no es norte geográfico)', 1.6, fill='#555') + '</g>')
        self.add(''.join(g))

    def side_panel(self, blocks):
        x, y = 441.0, 13.0
        g = ['<g id="side-panel">']
        for kind, payload in blocks:
            if kind == 'h':
                g.append(text(x, y + 3, payload.upper(), 2.6, anchor='start', weight='800', fill='#141210', extra='letter-spacing="0.35"'))
                g.append(f'<line x1="{x}" y1="{y + 4.6}" x2="{SHEET_W - 10}" y2="{y + 4.6}" stroke="#141210" stroke-width="0.3"/>')
                y += 8.4
            elif kind == 'legend':
                for sw, label in payload:
                    g.append(sw(x, y))
                    g.append(text(x + 12, y + 2.6, label, 2.05, anchor='start'))
                    y += 4.6
                y += 1.6
            elif kind == 'rows':
                for a, b in payload:
                    g.append(text(x, y + 2.6, a, 2.05, anchor='start', fill='#333'))
                    g.append(text(SHEET_W - 11, y + 2.6, b, 2.05, anchor='end', weight='700', family=MONO))
                    g.append(f'<line x1="{x}" y1="{y + 3.8}" x2="{SHEET_W - 10}" y2="{y + 3.8}" stroke="#e1ddd6" stroke-width="0.2"/>')
                    y += 4.4
                y += 1.6
            elif kind == 'para':
                for ln in payload:
                    style = ln.startswith('!')
                    s = ln[1:] if style else ln
                    g.append(text(x, y + 2.4, s, 1.95, anchor='start', weight='700' if style else '400',
                                  fill='#b00020' if style else '#2a2a2a'))
                    y += 3.3
                y += 1.8
            elif kind == 'gap':
                y += payload
        g.append('</g>')
        self.add(''.join(g))
        return y

    def schedule(self, x, y, w, rows_max=15):
        eq = [e for e in self.lay.get('equipment', [])]
        order = {'fire': 0, 'hood': 1, 'smoker': 2, 'cold': 3, 'prep': 4, 'wash': 5, 'storage': 6, 'bar': 7, 'delivery': 8, 'misc': 9}
        eq.sort(key=lambda e: (order.get(e.get('cat'), 9), e.get('tag', e['id'])))
        g = ['<g id="schedule">']
        g.append(text(x, y + 3, 'CUADRO DE EQUIPOS', 2.6, anchor='start', weight='800', extra='letter-spacing="0.35"'))
        g.append(text(x + 55, y + 3, '(* = DIMENSION TO VERIFY · a × p × h en m)', 1.9, anchor='start', fill='#b00020'))
        y += 6
        cols = math.ceil(len(eq) / rows_max) if eq else 1
        cw = w / max(cols, 1)
        for i, e in enumerate(eq):
            c, r = divmod(i, rows_max)
            xx, yy = x + c * cw, y + r * 4.3
            x0, y0, x1, y1 = e['rect']
            wd, dp = abs(x1 - x0), abs(y1 - y0)
            a, b = (wd, dp) if e.get('front') in ('N', 'S') else (dp, wd)
            if e.get('front') not in ('N', 'S', 'E', 'W'):
                a, b = max(wd, dp), min(wd, dp)
            fill, stroke = COL.get(e.get('cat', 'misc'), COL['misc']) if e.get('cat') in COL else COL['misc']
            g.append(f'<rect x="{f(xx)}" y="{f(yy)}" width="3" height="3" fill="{fill if fill != "none" else "#fff"}" stroke="{stroke}" stroke-width="0.3"/>')
            g.append(text(xx + 4.2, yy + 2.5, e.get('tag', e['id']), 2.0, anchor='start', weight='800', fill=stroke))
            name = e.get('label', '')
            g.append(text(xx + 12, yy + 2.5, name[:38], 1.95, anchor='start'))
            dims = f"{a:.2f}×{b:.2f}" + (f"×{float(e['h']):.2f}" if e.get('h') and not e.get('overhead') else '')
            g.append(text(xx + cw - 3, yy + 2.5, dims + ('*' if e.get('tbv') else ''), 1.85, anchor='end', family=MONO,
                          fill='#b00020' if e.get('tbv') else '#222'))
        g.append('</g>')
        self.add(''.join(g))

    def wall_table(self, x, y, w):
        ex, lay = self.ex, self.lay
        gone = {d['id'] for d in lay.get('demolish', [])}
        g = ['<g id="wall-table">', text(x, y + 3, 'EVALUACIÓN DE MUROS EXISTENTES (lectura del PDF + criterio, VERIFY ON SITE)', 2.6, anchor='start', weight='800', extra='letter-spacing="0.3"')]
        y += 6.5
        cols = [(0, 'ID'), (20, 'Descripción'), (150, 'Espesor'), (172, 'Trama PDF'), (196, 'Lectura estructural'), (330, 'Acción')]
        for dx, h in cols:
            g.append(text(x + dx, y + 2.4, h, 1.9, anchor='start', weight='700', fill='#555'))
        y += 4.2
        walls = [w_ for w_ in ex['walls'] if w_['kind'] in ('perimeter', 'partition_light', 'pilaster_shafts')]
        rows_max = 14
        for i, w_ in enumerate(walls[:2 * rows_max]):
            c, r = divmod(i, rows_max)
            if c:
                continue
            yy = y + r * 3.6
            x0, y0, x1, y1 = w_['rect']
            t = min(abs(x1 - x0), abs(y1 - y0))
            act = 'DEMOLER' if w_['id'] in gone else 'MANTENER'
            colr = COL['demolish'] if act == 'DEMOLER' else '#333'
            vals = [w_['id'], w_['note'][:70], f"{t*100:.0f} cm", 'sí' if w_.get('hatched') else 'no', w_.get('structural_guess', '')[:58], act]
            for (dx, _), v in zip(cols, vals):
                g.append(text(x + dx, yy + 2.4, v, 1.75, anchor='start', fill=colr if dx in (0, 330) else '#222',
                              weight='700' if dx in (0, 330) else '400', family=MONO if dx in (150,) else FONT))
        g.append('</g>')
        self.add(''.join(g))

    def flow_diagram(self, x, y, w):
        g = ['<g id="flow-diagram">', text(x, y + 3, 'LÓGICA DE FLUJOS', 2.6, anchor='start', weight='800', extra='letter-spacing="0.3"')]
        steps = [('A', 'Recepción + almacenamiento', ZONE_FILL['A']), ('A', 'Preparación fría', ZONE_FILL['A']),
                 ('B', 'Cocción (línea caliente)', ZONE_FILL['B']), ('C', 'Pase + barra / caja', ZONE_FILL['C']), ('D', 'Salón', ZONE_FILL['D'])]
        bw, bh, gap = 62, 11, 17
        yy = y + 9
        for i, (z, name, c) in enumerate(steps):
            xx = x + i * (bw + gap)
            g.append(f'<rect x="{f(xx)}" y="{f(yy)}" width="{bw}" height="{bh}" rx="1.5" fill="{c}" fill-opacity="0.12" stroke="{c}" stroke-width="0.5"/>')
            g.append(f'<circle cx="{f(xx + 6)}" cy="{f(yy + bh/2)}" r="3.2" fill="{c}"/>')
            g.append(text(xx + 6, yy + bh / 2 + 1.2, z, 3.2, weight='800', fill='#fff'))
            g.append(text(xx + 11, yy + bh / 2 + 0.9, name, 2.3, anchor='start', weight='600'))
            if i < len(steps) - 1:
                g.append(f'<line x1="{f(xx + bw + 1)}" y1="{f(yy + bh/2)}" x2="{f(xx + bw + gap - 1.5)}" y2="{f(yy + bh/2)}" stroke="{ROUTE["clean"][0]}" stroke-width="0.8" marker-end="url(#arr-clean)"/>')
        yy2 = yy + bh + 12
        back = [('D', 'Salón (mesas)', ZONE_FILL['D']), ('C', 'Puerta cocina / retorno', ZONE_FILL['C']), ('A', 'Lavado (fregadero 2T)', ZONE_FILL['A'])]
        for i, (z, name, c) in enumerate(back):
            xx = x + (4 - i) * (bw + gap)
            g.append(f'<rect x="{f(xx)}" y="{f(yy2)}" width="{bw}" height="{bh}" rx="1.5" fill="#fff" stroke="{ROUTE["dirty"][0]}" stroke-width="0.5" stroke-dasharray="1.5 1"/>')
            g.append(f'<circle cx="{f(xx + 6)}" cy="{f(yy2 + bh/2)}" r="3.2" fill="{c}"/>')
            g.append(text(xx + 6, yy2 + bh / 2 + 1.2, z, 3.2, weight='800', fill='#fff'))
            g.append(text(xx + 11, yy2 + bh / 2 + 0.9, name, 2.3, anchor='start', weight='600'))
            if i < len(back) - 1:
                g.append(f'<line x1="{f(xx - 1)}" y1="{f(yy2 + bh/2)}" x2="{f(xx - gap + 1.5)}" y2="{f(yy2 + bh/2)}" stroke="{ROUTE["dirty"][0]}" stroke-width="0.8" stroke-dasharray="2 1" marker-end="url(#arr-dirty)"/>')
        g.append(text(x, yy2 + bh + 7, 'El retorno de platos sucios entra por la puerta de cocina directo al lavado, sin atravesar la preparación ni la línea caliente.', 2.1, anchor='start', fill='#b00020', weight='600'))
        g.append('</g>')
        self.add(''.join(g))

    def render(self):
        body = ''.join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SHEET_W} {SHEET_H}" width="{SHEET_W}mm" height="{SHEET_H}mm" '
                f'font-family="{FONT}" role="img" aria-label="LAVA plano conceptual">'
                f'<rect width="{SHEET_W}" height="{SHEET_H}" fill="#ffffff"/>' + self.defs() + body + '</svg>')


# ---------------------------------------------------------------------- legend swatches
def sw_rect(fill, stroke, dash=None, pattern=None):
    def fn(x, y):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        return f'<rect x="{x}" y="{y}" width="10" height="3.4" fill="{pattern or fill}" stroke="{stroke}" stroke-width="0.35"{d}/>'
    return fn


def sw_line(color, dash=None, w=0.9):
    def fn(x, y):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        return f'<line x1="{x}" y1="{y+1.7}" x2="{x+10}" y2="{y+1.7}" stroke="{color}" stroke-width="{w}"{d}/>'
    return fn


def sw_glass():
    def fn(x, y):
        return (f'<rect x="{x}" y="{y+0.6}" width="10" height="2.2" fill="#111"/>'
                f'<line x1="{x+0.3}" y1="{y+1.7}" x2="{x+9.7}" y2="{y+1.7}" stroke="{COL["glass"]}" stroke-width="0.55"/>')
    return fn


LEGEND_WALLS = [
    (sw_rect(None, COL['existing_stroke'], pattern='url(#hatch-ex)'), 'Existente (muros, columnas, ductos) – se mantiene'),
    (sw_rect(None, COL['demolish'], dash='1.2 0.8', pattern='url(#hatch-demo)'), 'EXISTING WALL → DEMOLISH / REMOVE'),
    (sw_rect('#111', '#000'), 'NEW PARTITION WALL → PROPOSED'),
    (sw_glass(), 'Muro bajo sólido + vidrio (spec. térmica pendiente)'),
]
LEGEND_EQ = [
    (sw_rect(*COL['fire']), 'Equipos de fuego / línea caliente'),
    (sw_rect('none', COL['hood'][1], dash='2 0.8'), 'Campana (proyección en altura)'),
    (sw_rect(None, COL['smoker'][1], pattern='url(#hatch-smoker)'), 'Smoker de combustible sólido'),
    (sw_rect(*COL['cold']), 'Refrigeración / preparación fría'),
    (sw_rect(*COL['wash']), 'Lavado (fregadero, mop sink, lavamanos)'),
    (sw_rect(*COL['storage']), 'Almacenamiento seco / leña'),
    (sw_rect(*COL['bar']), 'Barra / caja / pase'),
    (sw_rect(*COL['delivery']), 'Staging delivery'),
    (sw_rect(*COL['table']), 'Salón: mesas, sillas, bancas'),
]


def metrics_rows(ex, lay, val):
    m = (val or {}).get('metrics', {})
    rows = [('Asientos en salón', f"{seat_count(lay)}")]
    if m.get('new_partition_x') is not None:
        rows.append(('Corrimiento de la división', f"{m.get('partition_shift_m', 0):.2f} m"))
    zones = {z['id']: z for z in m.get('zones', [])}
    for zid, label in (('A', 'Área A · BOH / prep / almacén'), ('B', 'Área B · cocina caliente'), ('C', 'Área C · pase + barra/caja'),
                       ('D', 'Área D · salón'), ('E', 'Área E · smoker')):
        if zid in zones:
            rows.append((label, f"{zones[zid]['area_m2']:.1f} m²"))
    routes = {r['id']: r for r in m.get('routes', [])}
    for r in m.get('routes', []):
        if r.get('kind') in ('guest', 'server', 'clean', 'dirty'):
            rows.append((f"Ancho mín. · {r.get('label') or r['id']}"[:44], f"{r['min_width']:.2f} m"))
    if m.get('hot_line_length'):
        rows.append(('Línea caliente / campana', f"{m['hot_line_length']:.2f} / {m.get('hood_length', 0):.2f} m"))
    if m.get('seats_with_parrilla_view_pct') is not None:
        rows.append(('Asientos con vista a parrilla', f"{m['seats_with_parrilla_view_pct']:.0f} %"))
    return rows


def build(lay_path, val_path, outdir):
    ex = load_existing()
    lay = load_json(lay_path)
    val = load_json(val_path) if val_path and os.path.exists(val_path) else None
    os.makedirs(outdir, exist_ok=True)
    out = {}

    # ---------------- A-101 planta propuesta
    s = Sheet(ex, lay, val, 'A101')
    s.frame_and_titleblock('A-101 · Planta propuesta (test-fit)', 'Zonificación, equipos a escala, mobiliario y cotas principales', 'A-101')
    s.grid_axes()
    s.layer_zones(0.09)
    s.layer_existing()
    s.layer_demolish()
    s.layer_furniture()
    s.layer_equipment()
    s.layer_new()
    s.zone_labels()
    for d in lay.get('dims', []):
        s.dim(d['a'], d['b'], d.get('off', 0.5), d.get('label'))
    for c in lay.get('callouts', []):
        if 'A101' in c.get('sheets', ['A101']):
            s.callout(c['anchor'], c['at'], c['lines'], color=c.get('color', '#1b1b1b'), width=c.get('w'))
    y = s.side_panel([
        ('h', 'Leyenda'), ('legend', LEGEND_WALLS + LEGEND_EQ),
        ('h', 'Cifras clave (calculadas)'), ('rows', metrics_rows(ex, lay, val)),
    ])
    s.schedule(14, 336, 418, rows_max=max(1, math.ceil(len(lay.get('equipment', [])) / 3)))
    notes = lay.get('sheet_notes', [])
    if notes:
        s.side_panel([('gap', y - 13), ('h', 'Notas'), ('para', notes)])
    out['A101'] = s.render()

    # ---------------- A-102 demolición / construcción
    s = Sheet(ex, lay, val, 'A102')
    s.frame_and_titleblock('A-102 · Demolición y construcción', 'Muros existentes, a demoler y nuevos · traslado de la división cocina/salón', 'A-102')
    s.grid_axes()
    s.layer_existing()
    s.layer_demolish()
    s.layer_new()
    for d in lay.get('dims_demo', []):
        s.dim(d['a'], d['b'], d.get('off', 0.5), d.get('label'), color=d.get('color', '#222'))
    for c in lay.get('callouts', []):
        if 'A102' in c.get('sheets', []):
            s.callout(c['anchor'], c['at'], c['lines'], color=c.get('color', '#1b1b1b'), width=c.get('w'))
    demo_rows = []
    for d in lay.get('demolish', []):
        w = next((w for w in ex['walls'] if w['id'] == d['id']), None)
        if w:
            x0, y0, x1, y1 = w['rect']
            demo_rows.append((f"{d['id']} · {w['note'][:30]}", f"{max(abs(x1-x0), abs(y1-y0)):.2f} m"))
    new_rows = []
    for w in lay.get('new_walls', []):
        x0, y0, x1, y1 = w['rect']
        new_rows.append((f"{w['id']} · {(w.get('short') or w.get('type'))[:30]}", f"{max(abs(x1-x0), abs(y1-y0)):.2f} m"))
    s.wall_table(14, 336, 418)
    y = s.side_panel([
        ('h', 'Leyenda'), ('legend', LEGEND_WALLS),
        ('h', 'A demoler (divisiones livianas)'), ('rows', demo_rows),
        ('h', 'Construcción nueva'), ('rows', new_rows),
        ('h', 'Criterio estructural'), ('para', lay.get('structure_notes', [])),
    ])
    out['A102'] = s.render()

    # ---------------- A-103 flujos
    s = Sheet(ex, lay, val, 'A103')
    s.frame_and_titleblock('A-103 · Flujos y circulaciones', 'Limpio / sucio / clientes / meseros / delivery / combustible · anchos mínimos medidos', 'A-103')
    s.grid_axes()
    s.layer_zones(0.06)
    s.layer_existing(faint=False)
    s.layer_new()
    s.layer_furniture(faint=True)
    s.layer_equipment(faint=True, tags=False)
    s.layer_routes()
    for c in lay.get('callouts', []):
        if 'A103' in c.get('sheets', []):
            s.callout(c['anchor'], c['at'], c['lines'], color=c.get('color', '#1b1b1b'), width=c.get('w'))
    s.flow_diagram(14, 336, 418)
    kinds = []
    for r in lay.get('routes', []):
        if r.get('kind') not in kinds:
            kinds.append(r.get('kind'))
    leg = [(sw_line(ROUTE[k][0], ROUTE[k][1]), ROUTE_NAME.get(k, k)) for k in kinds if k in ROUTE]
    m = (val or {}).get('metrics', {})
    rrows = [(f"{r.get('label') or r['id']}"[:40], f"{r['min_width']:.2f} m (req {r['required']:.2f})") for r in m.get('routes', [])]
    s.side_panel([
        ('h', 'Flujos'), ('legend', leg),
        ('h', 'Ancho libre mínimo medido por ruta'), ('rows', rrows),
        ('para', ['Medición automática sobre la planta: distancia libre entre', 'equipos/mobiliario/muros a lo largo de cada ruta.',
                  '!Circulación principal objetivo 1.10–1.20 m; secundaria ≥ 0.90 m.']),
        ('h', 'Separación limpio / sucio'), ('para', lay.get('flow_notes', [])),
    ])
    out['A103'] = s.render()

    names = {'A101': 'lava_A101_planta.svg', 'A102': 'lava_A102_demolicion.svg', 'A103': 'lava_A103_flujos.svg'}
    for k, v in out.items():
        with open(os.path.join(outdir, names[k]), 'w') as fh:
            fh.write(v)
    with open(os.path.join(outdir, 'lava_plan.svg'), 'w') as fh:
        fh.write(out['A101'])
    return [os.path.join(outdir, n) for n in names.values()]


if __name__ == '__main__':
    lay_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else os.path.join(ROOT, 'data', 'layout.json')
    val_path = None
    if '--validation' in sys.argv:
        val_path = sys.argv[sys.argv.index('--validation') + 1]
    outdir = os.path.join(ROOT, 'plan')
    if '--out' in sys.argv:
        outdir = sys.argv[sys.argv.index('--out') + 1]
    for p in build(lay_path, val_path, outdir):
        print('wrote', p)
