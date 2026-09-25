"""Generate the LAVA conceptual plan sheets (SVG, A2 landscape, 1:50) from existing.json + layout.json.

Usage:
    python3 tools/plan_svg.py [data/layout.json] [--validation data/validation.json] [--out plan]

Writes plan/lava_A101_planta.svg, plan/lava_A102_demolicion.svg, plan/lava_A103_flujos.svg and
plan/lava_plan.svg (copy of A-101, embedded by the walkthrough app).

Layout extras read here (all optional):
  dims:      [{a:[x,y], b:[x,y], off:m, label, sheets:[A101|A102|A103], color}]   axis-aligned; `off` is the
             signed distance of the dimension line from point a along the perpendicular axis (model metres).
  keynotes:  [{anchor:[x,y], text, sheets, color}]  -> numbered markers + list box
  keynote_box: {A101:[x0,y0,x1,y1], ...}             model-coordinate box for the keynote list
  zones[].short / label_at / label_lines             big zone labels
  equipment[].label_at [x,y]                         put the label outside with a leader
"""
import datetime
import math
import os
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(__file__))
from shapely.geometry import Polygon
from shapely.ops import unary_union

from lavageo import R, ROOT, door_swing_poly, load_existing, load_json, seat_count, standing_existing_walls

SHEET_W, SHEET_H = 594.0, 420.0          # mm, A2 landscape
S = 20.0                                 # 1:50 -> 1 m = 20 mm
VIEW = (-1.75, -2.30, 17.55, 12.45)      # model window (m)
DRAW = (12.0, 13.0)                      # sheet mm of model VIEW top-left
FONT = "Figtree, 'Liberation Sans', Arial, sans-serif"
MONO = "'JetBrains Mono', 'DejaVu Sans Mono', monospace"
DISPLAY = "'Big Shoulders Display', 'Liberation Sans', Arial, sans-serif"

COL = {
    'existing_stroke': '#5c5c58', 'column': '#4a4a47', 'demolish': '#d62828', 'new': '#111111', 'glass': '#35b6e8',
    'fire': ('#f6a04d', '#8f4500'), 'cold': ('#86b3ee', '#1a55b0'), 'prep': ('#bcd5f6', '#1a55b0'),
    'wash': ('#bde6ea', '#17737a'), 'storage': ('#e7d8b5', '#75602e'), 'smoker': ('#e46a2e', '#6e2508'),
    'bar': ('#d7c6ec', '#553688'), 'delivery': ('#f5e27f', '#6d5f08'), 'misc': ('#dcdcdc', '#555555'),
    'hood': ('none', '#b35900'),
    'table': ('#b7dfb0', '#2b7a31'), 'chair': ('#dff1da', '#2b7a31'), 'banquette': ('#8fcb86', '#1f5f25'),
}
ZONE_FILL = {'A': '#2f6fd0', 'B': '#f07c14', 'C': '#7a4fb8', 'D': '#2e9a3a', 'E': '#c2410c', 'W': '#17737a'}
ROUTE = {'clean': ('#1f63c6', None), 'dirty': ('#d62828', '5 3'), 'guest': ('#2e9a3a', None),
         'server': ('#7a4fb8', '1.5 2'), 'delivery': ('#b39b00', '6 2 1.5 2'), 'fuel': ('#8c4a1e', '2 2')}
ROUTE_NAME = {'clean': 'Flujo limpio (frío → prep → línea / BBQ)', 'dirty': 'Flujo sucio (salón → lavado)',
              'guest': 'Clientes', 'server': 'Platos: línea → P-1 → pase → mesas', 'delivery': 'Delivery (pedido → recepción)',
              'fuel': 'Leña / cenizas (PS-1 condicional)'}


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
    t = f' transform="rotate({f(rot)} {f(x)} {f(y)})"' if rot else ''
    return (f'<text x="{f(x)}" y="{f(y)}" font-family="{family}" font-size="{f(size)}" font-weight="{weight}" '
            f'text-anchor="{anchor}" fill="{fill}"{t} {extra}>{escape(str(s))}</text>')


def mtext(x, y, lines, size=2.2, anchor='middle', weight='400', fill='#1b1b1b', lh=1.2, family=FONT, rot=0, weights=None):
    """Multi-line text centred on (x, y); with rotation the block rotates around (x, y)."""
    n = len(lines)
    out = []
    for i, ln in enumerate(lines):
        off = (i - (n - 1) / 2) * size * lh + size * 0.35
        w = weights[i] if weights else weight
        if rot:
            a = math.radians(rot)
            tx, ty = x - math.sin(a) * off, y + math.cos(a) * off
            out.append(text(tx, ty, ln, size, anchor, w, fill, family, rot))
        else:
            out.append(text(x, y + off, ln, size, anchor, w, fill, family))
    return ''.join(out)


def tw(s, size):
    """Approximate text width in mm."""
    return len(str(s)) * size * 0.55


def eq_dims_cm(e):
    x0, y0, x1, y1 = e['rect']
    wd, dp = abs(x1 - x0), abs(y1 - y0)
    fr = e.get('front')
    if fr in ('N', 'S'):
        a, b = wd, dp
    elif fr in ('E', 'W'):
        a, b = dp, wd
    else:
        a, b = max(wd, dp), min(wd, dp)
    return f"{a*100:.0f}×{b*100:.0f}" + ('*' if e.get('tbv') else '')


class Sheet:
    def __init__(self, ex, lay, val, kind):
        self.ex, self.lay, self.val, self.kind = ex, lay, val or {}, kind
        self.m = (self.val.get('metrics') or {})
        self.parts = []
        self.keys = []

    def add(self, s):
        self.parts.append(s)

    # ------------------------------------------------------------------ dimensions
    def dim(self, a, b, off, label=None, color='#1f1f1f', size=2.1, lpos=0.5):
        (x1, y1), (x2, y2) = a, b
        horiz = abs(x2 - x1) >= abs(y2 - y1)
        g = [f'<g class="dim" stroke="{color}" stroke-width="0.18" fill="none">']
        tick = 0.075
        if horiz:
            ly = y1 + off
            L = abs(x2 - x1)
            for (px, py) in ((x1, y1), (x2, y2)):
                d = 1 if ly > py else -1
                g.append(f'<line x1="{f(sx(px))}" y1="{f(sy(py + d * 0.04))}" x2="{f(sx(px))}" y2="{f(sy(ly + d * 0.09))}"/>')
                g.append(f'<line stroke-width="0.4" x1="{f(sx(px - tick))}" y1="{f(sy(ly + tick))}" x2="{f(sx(px + tick))}" y2="{f(sy(ly - tick))}"/>')
            g.append(f'<line x1="{f(sx(min(x1, x2) - 0.06))}" y1="{f(sy(ly))}" x2="{f(sx(max(x1, x2) + 0.06))}" y2="{f(sy(ly))}"/>')
            g.append('</g>')
            lbl = label if label is not None else f"{L:.2f}"
            g.append(text(sx(x1) + (sx(x2) - sx(x1)) * lpos, sy(ly) - 0.75, lbl, size, family=MONO, fill=color, weight='600',
                          extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.9"'))
        else:
            lx = x1 + off
            L = abs(y2 - y1)
            for (px, py) in ((x1, y1), (x2, y2)):
                d = 1 if lx > px else -1
                g.append(f'<line x1="{f(sx(px + d * 0.04))}" y1="{f(sy(py))}" x2="{f(sx(lx + d * 0.09))}" y2="{f(sy(py))}"/>')
                g.append(f'<line stroke-width="0.4" x1="{f(sx(lx - tick))}" y1="{f(sy(py + tick))}" x2="{f(sx(lx + tick))}" y2="{f(sy(py - tick))}"/>')
            g.append(f'<line x1="{f(sx(lx))}" y1="{f(sy(min(y1, y2) - 0.06))}" x2="{f(sx(lx))}" y2="{f(sy(max(y1, y2) + 0.06))}"/>')
            g.append('</g>')
            lbl = label if label is not None else f"{L:.2f}"
            g.append(text(sx(lx) - 0.75, sy(y1) + (sy(y2) - sy(y1)) * lpos, lbl, size, family=MONO, fill=color, weight='600', rot=-90,
                          extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.9"'))
        self.add(''.join(g))

    def dims_for(self, key, sheet):
        for d in self.lay.get(key, []):
            if sheet in d.get('sheets', [sheet]):
                self.dim(d['a'], d['b'], d.get('off', 0.4), d.get('label'), color=d.get('color', '#1f1f1f'), lpos=d.get('lpos', 0.5))

    # ------------------------------------------------------------------ keynotes
    def keynotes(self, sheet):
        notes = [k for k in self.lay.get('keynotes', []) if sheet in k.get('sheets', ['A101'])]
        box = (self.lay.get('keynote_box') or {}).get(sheet)
        if not notes or not box:
            return
        g = ['<g id="keynotes">']
        for i, k in enumerate(notes, 1):
            ax, ay = sx(k['anchor'][0]), sy(k['anchor'][1])
            c = k.get('color', '#1b1b1b')
            g.append(f'<circle cx="{f(ax)}" cy="{f(ay)}" r="2.3" fill="#ffffff" stroke="{c}" stroke-width="0.45"/>')
            g.append(text(ax, ay + 0.95, str(i), 2.5, weight='800', fill=c))
        x0, y0, x1, y1 = box
        bx, by, bw = sx(x0), sy(y0), (x1 - x0) * S
        need = 10.5 + sum(len(k['text'] if isinstance(k['text'], list) else [k['text']]) * 3.05 + 1.9 for k in notes) + 1.0
        bh = min((y1 - y0) * S, need)
        g.append(f'<rect x="{f(bx)}" y="{f(by)}" width="{f(bw)}" height="{f(bh)}" fill="#ffffff" stroke="#1b1b1b" stroke-width="0.35"/>')
        g.append(text(bx + 3, by + 5.2, 'NOTAS CLAVE', 2.8, anchor='start', weight='800', extra='letter-spacing="0.4"'))
        yy = by + 10.5
        for i, k in enumerate(notes, 1):
            c = k.get('color', '#1b1b1b')
            g.append(f'<circle cx="{f(bx + 4.3)}" cy="{f(yy - 0.8)}" r="2.1" fill="#ffffff" stroke="{c}" stroke-width="0.4"/>')
            g.append(text(bx + 4.3, yy + 0.05, str(i), 2.3, weight='800', fill=c))
            lines = k['text'] if isinstance(k['text'], list) else [k['text']]
            for j, ln in enumerate(lines):
                g.append(text(bx + 8.5, yy + j * 3.05, ln, 2.05, anchor='start', weight='700' if j == 0 else '400',
                              fill=c if j == 0 else '#2a2a2a'))
            yy += len(lines) * 3.05 + 1.9
        g.append('</g>')
        self.add(''.join(g))

    # ------------------------------------------------------------------ layers
    def defs(self):
        return ('<defs>'
                '<pattern id="hatch-ex" patternUnits="userSpaceOnUse" width="1.2" height="1.2" patternTransform="rotate(45)">'
                '<rect width="1.2" height="1.2" fill="#a8a8a5"/><line x1="0" y1="0" x2="0" y2="1.2" stroke="#6e6e6a" stroke-width="0.25"/></pattern>'
                '<pattern id="hatch-smoker" patternUnits="userSpaceOnUse" width="1.4" height="1.4" patternTransform="rotate(45)">'
                '<rect width="1.4" height="1.4" fill="#f09461"/><line x1="0" y1="0" x2="0" y2="1.4" stroke="#6e2508" stroke-width="0.3"/></pattern>'
                '<pattern id="hatch-demo" patternUnits="userSpaceOnUse" width="1.6" height="1.6" patternTransform="rotate(-45)">'
                '<rect width="1.6" height="1.6" fill="#fff4f4"/><line x1="0" y1="0" x2="0" y2="1.6" stroke="#f1a3a3" stroke-width="0.35"/></pattern>'
                + ''.join(f'<marker id="arr-{k}" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="4" markerHeight="4" orient="auto">'
                          f'<path d="M0,0 L6,3 L0,6 z" fill="{c}"/></marker>' for k, (c, _) in ROUTE.items())
                + '</defs>')

    def layer_zones(self, opacity=0.10):
        g = ['<g id="zones">']
        for z in self.lay.get('zones', []):
            c = z.get('color') or ZONE_FILL.get(z['id'][0], '#999')
            g.append(f'<polygon points="{pts_attr(z["poly"])}" fill="{c}" fill-opacity="{opacity}" stroke="{c}" stroke-opacity="0.55" '
                     f'stroke-width="0.35" stroke-dasharray="1.4 1"/>')
        g.append('</g>')
        self.add(''.join(g))

    def zone_labels(self, big=True):
        prem = Polygon(self.ex['premises_polygon'])
        g = ['<g id="zone-labels">']
        for z in self.lay.get('zones', []):
            c = z.get('color') or ZONE_FILL.get(z['id'][0], '#999')
            poly = Polygon(z['poly']).intersection(prem)
            if poly.is_empty:
                continue
            at = z.get('label_at') if big else (z.get('label_at_flows') or z.get('label_at'))
            px, py = at or (poly.representative_point().x, poly.representative_point().y)
            lines = z.get('label_lines') or [z.get('short', z.get('name', ''))]
            size = z.get('label_size', 5.0) if big else 2.6
            cx, cy = sx(px), sy(py)
            h = len(lines) * size * 1.12
            sub = f"ZONA {z['id']} · ≈ {poly.area:.1f} m²"
            wmax = max([len(s) * size * 0.43 for s in lines] + [len(sub) * 2.0 * 0.6])
            g.append(f'<rect x="{f(cx - wmax/2 - 2)}" y="{f(cy - h/2 - 1.6)}" width="{f(wmax + 4)}" height="{f(h + 6.4)}" rx="1.2" '
                     f'fill="#ffffff" fill-opacity="0.82" stroke="{c}" stroke-width="0.5"/>')
            g.append(mtext(cx, cy - 1.1, lines, size, weight='800', fill=c, lh=1.12, family=DISPLAY))
            g.append(text(cx, cy + h / 2 + 3.3, sub, 2.0, weight='700', fill=c, family=MONO))
        g.append('</g>')
        self.add(''.join(g))

    def layer_existing(self):
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
        g.append(text(sx((ox[0] + ox[2]) / 2), sy(10.9), 'ESCALERA EXISTENTE', 2.4, weight='700', fill='#8b8b86'))
        g.append(text(sx((ox[0] + ox[2]) / 2), sy(10.9) + 3.0, '(edificio · fuera del local)', 1.8, fill='#8b8b86'))
        for s in ex['shafts']:
            x0, y0, x1, y1 = s['rect']
            g.append(rect_el(s['rect'], '#ffffff', '#6e6e6a', 0.2))
            g.append(f'<path d="M{f(sx(x0))},{f(sy(y0))} L{f(sx(x1))},{f(sy(y1))} M{f(sx(x0))},{f(sy(y1))} L{f(sx(x1))},{f(sy(y0))}" stroke="#8a8a85" stroke-width="0.15"/>')
        for w, geom in standing_existing_walls(ex, lay):
            g.append(poly_el(geom, 'url(#hatch-ex)', COL['existing_stroke'], 0.25))
        for c in ex['columns']:
            g.append(rect_el(c['rect'], COL['column'], '#222', 0.25))
        for gl in ex['glazing']:
            x0, y0, x1, y1 = gl['rect']
            g.append(rect_el(gl['rect'], '#e3f6ff', COL['glass'], 0.3))
            if (x1 - x0) < (y1 - y0):
                g.append(f'<line x1="{f(sx((x0+x1)/2))}" y1="{f(sy(y0))}" x2="{f(sx((x0+x1)/2))}" y2="{f(sy(y1))}" stroke="{COL["glass"]}" stroke-width="0.35"/>')
            else:
                g.append(f'<line x1="{f(sx(x0))}" y1="{f(sy((y0+y1)/2))}" x2="{f(sx(x1))}" y2="{f(sy((y0+y1)/2))}" stroke="{COL["glass"]}" stroke-width="0.35"/>')
        for hy, sign in ((1.643, 1), (3.643, -1)):      # main double door, swings inward
            hx, r = 16.3, 0.97
            g.append(f'<line x1="{f(sx(hx))}" y1="{f(sy(hy))}" x2="{f(sx(hx - r))}" y2="{f(sy(hy))}" stroke="#333" stroke-width="0.3"/>')
            g.append(f'<path d="M{f(sx(hx - r))},{f(sy(hy))} A{f(r*S)},{f(r*S)} 0 0 {0 if sign > 0 else 1} {f(sx(hx))},{f(sy(hy + sign * r))}" '
                     f'fill="none" stroke="#555" stroke-width="0.18" stroke-dasharray="0.8 0.6"/>')
        g.append(text(sx(16.62), sy(2.64), 'ACCESO', 2.2, weight='800', fill='#333', rot=-90))
        g.append('</g>')
        self.add(''.join(g))

    def layer_demolish(self):
        ex, lay = self.ex, self.lay
        ids = {d['id'] for d in lay.get('demolish', []) if 'rect' not in d}
        g = ['<g id="demolish">']
        for w in ex['walls']:
            if w['id'] in ids:
                g.append(rect_el(w['rect'], 'url(#hatch-demo)', COL['demolish'], 0.45, dash='1.2 0.8'))
        for d in lay.get('demolish', []):
            if 'rect' in d:
                g.append(rect_el(d['rect'], 'url(#hatch-demo)', COL['demolish'], 0.45, dash='1.2 0.8'))
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
            if t in ('door', 'service_door') and 'hinge' in o:
                hx, hy = o['hinge']
                bx, by = o['swing_to']
                cx, cy = o['closed_to']
                r = math.hypot(cx - hx, cy - hy)
                a0 = math.atan2(cy - hy, cx - hx)
                a1 = math.atan2(by - hy, bx - hx)
                d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
                sweep = 1 if d > 0 else 0
                g.append(rect_el(o['rect'], '#ffffff', 'none', 0))
                g.append(f'<line x1="{f(sx(hx))}" y1="{f(sy(hy))}" x2="{f(sx(bx))}" y2="{f(sy(by))}" stroke="{stroke}" stroke-width="0.35"/>')
                g.append(f'<path d="M{f(sx(cx))},{f(sy(cy))} A{f(r*S)},{f(r*S)} 0 0 {sweep} {f(sx(bx))},{f(sy(by))}" fill="none" stroke="{stroke}" stroke-width="0.18" stroke-dasharray="0.8 0.6"/>')
                if cond:
                    g.append(rect_el(o['rect'], 'none', stroke, 0.35, dash='1 0.6'))
            elif t == 'double_acting_door':
                vert = (x1 - x0) < (y1 - y0)
                g.append(rect_el(o['rect'], '#ffffff', 'none', 0))
                if vert:
                    cx_, L = (x0 + x1) / 2, y1 - y0
                    for sgn in (-1, 1):   # two quarter-swings (double acting)
                        g.append(f'<path d="M{f(sx(cx_))},{f(sy(y1))} L{f(sx(cx_))},{f(sy(y0))} A{f(L*S)},{f(L*S)} 0 0 {1 if sgn < 0 else 0} {f(sx(cx_ + sgn * L))},{f(sy(y1))}" '
                                 f'fill="none" stroke="#111" stroke-width="0.18" stroke-dasharray="0.8 0.6"/>')
                    g.append(f'<line x1="{f(sx(cx_))}" y1="{f(sy(y0))}" x2="{f(sx(cx_))}" y2="{f(sy(y1))}" stroke="#111" stroke-width="0.5"/>')
                else:
                    cy_, L = (y0 + y1) / 2, x1 - x0
                    g.append(f'<line x1="{f(sx(x0))}" y1="{f(sy(cy_))}" x2="{f(sx(x1))}" y2="{f(sy(cy_))}" stroke="#111" stroke-width="0.5"/>')
            if o.get('label'):
                lx = sx((x0 + x1) / 2)
                ly = sy((y0 + y1) / 2)
                if t == 'double_acting_door':
                    g.append(text(lx + 7.5, ly + 0.8, f"{o['label']} · {o.get('width', 0.9):.2f}", 2.0, weight='800', fill=stroke))
                else:
                    g.append(text(lx, ly + 5.2, f"{o['label']} · {o.get('width', 0.9):.2f}", 2.0, weight='800', fill=stroke))
        g.append('</g>')
        self.add(''.join(g))

    def layer_equipment(self, faint=False, labels=True):
        lay = self.lay
        g = ['<g id="equipment">']
        hoods = []
        stacked = []
        for e in lay.get('equipment', []):
            cat = e.get('cat', 'misc')
            if e.get('overhead'):
                hoods.append(e)
                continue
            if e.get('stack_with'):
                stacked.append(e)
                continue
            fill, stroke = COL.get(cat, COL['misc'])
            if faint:
                fill, stroke = '#efefed', '#b6b6b1'
            if e.get('key') == 'smoker' and not faint:
                fill = 'url(#hatch-smoker)'
            g.append(rect_el(e['rect'], fill, stroke, 0.3))
            if not faint:
                self._front_mark(g, e, stroke)
        for e in stacked:
            fill, stroke = COL.get(e.get('cat', 'misc'), COL['misc'])
            if faint:
                fill, stroke = '#e4e4e1', '#b6b6b1'
            g.append(rect_el(e['rect'], fill, stroke, 0.3, dash='1.1 0.5', extra='fill-opacity="0.85"'))
        for hd in hoods:
            stroke = '#d9a36f' if faint else COL['hood'][1]
            g.append(rect_el(hd['rect'], 'none', stroke, 0.5, dash='2.2 0.9'))
            x0, y0, x1, y1 = hd['rect']
            g.append(f'<path d="M{f(sx(x0))},{f(sy(y0))} L{f(sx(x1))},{f(sy(y1))} M{f(sx(x0))},{f(sy(y1))} L{f(sx(x1))},{f(sy(y0))}" stroke="{stroke}" stroke-width="0.14" stroke-dasharray="1 0.8" fill="none"/>')
        if labels and not faint:
            for e in lay.get('equipment', []):
                self._eq_label(g, e)
        g.append('</g>')
        self.add(''.join(g))

    def _front_mark(self, g, e, stroke):
        x0, y0, x1, y1 = e['rect']
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        fr = e.get('front')
        if fr not in ('N', 'S', 'E', 'W'):
            return
        seg = {'N': (x0 + 0.05, y0 + 0.04, x1 - 0.05, y0 + 0.04), 'S': (x0 + 0.05, y1 - 0.04, x1 - 0.05, y1 - 0.04),
               'W': (x0 + 0.04, y0 + 0.05, x0 + 0.04, y1 - 0.05), 'E': (x1 - 0.04, y0 + 0.05, x1 - 0.04, y1 - 0.05)}[fr]
        g.append(f'<line x1="{f(sx(seg[0]))}" y1="{f(sy(seg[1]))}" x2="{f(sx(seg[2]))}" y2="{f(sy(seg[3]))}" stroke="{stroke}" stroke-width="0.6"/>')

    def _eq_label(self, g, e):
        if e.get('no_label'):
            return
        cat = e.get('cat', 'misc')
        stroke = COL.get(cat, COL['misc'])[1]
        x0, y0, x1, y1 = e['rect']
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        name = e.get('plan_label') or e.get('label', '')
        dims = eq_dims_cm(e)
        if e.get('overhead'):
            dims = f"≈{(y1-y0)*100:.0f}×{(x1-x0)*100:.0f}" if (y1 - y0) > (x1 - x0) else f"≈{(x1-x0)*100:.0f}×{(y1-y0)*100:.0f}"
        tag = e.get('tag', e['id'])
        lines = [f"{tag} · {name}", dims]
        cx, cy = sx((x0 + x1) / 2), sy((y0 + y1) / 2)
        w, h = (x1 - x0) * S, (y1 - y0) * S
        if e.get('label_at'):
            lx, ly = sx(e['label_at'][0]), sy(e['label_at'][1])
            size = e.get('label_size', 1.9)
            wmax = max(tw(s, size) for s in lines)
            ex_ = lx if abs(lx - cx) < wmax / 2 else (lx - wmax / 2 if lx > cx else lx + wmax / 2)
            g.append(f'<polyline points="{f(cx)},{f(cy)} {f(ex_)},{f(ly)}" fill="none" stroke="{stroke}" stroke-width="0.22"/>')
            g.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="0.45" fill="{stroke}"/>')
            g.append(f'<rect x="{f(lx - wmax/2 - 0.8)}" y="{f(ly - size*1.35)}" width="{f(wmax + 1.6)}" height="{f(size*2.7)}" fill="#ffffff" fill-opacity="0.92" stroke="none"/>')
            g.append(mtext(lx, ly, lines, size, weight='700', fill=stroke, weights=['700', '600']))
            return
        if e.get('overhead'):
            # hood: label along its outer (dashed) edge
            rot = -90 if h > w else 0
            size = 1.9
            if rot:
                lx = sx(x0) - 2.3 if e.get('label_side') == 'outside' else sx(x0) + 2.4
                g.append(mtext(lx, cy, [f"{tag} · {name}", dims], size, weight='700', fill=stroke, rot=-90, weights=['700', '600']))
            else:
                g.append(mtext(cx, sy(y1) - 2.4, [f"{tag} · {name}", dims], size, weight='700', fill=stroke, weights=['700', '600']))
            return
        best = None
        for rot in (0, -90):
            W, H = (w, h) if rot == 0 else (h, w)
            for size in (2.1, 1.9, 1.7, 1.55, 1.4, 1.25):
                for ls in (lines, [tag, name, dims] if len(name) > 10 else None):
                    if ls is None:
                        continue
                    if max(tw(s, size) for s in ls) <= W - 0.8 and len(ls) * size * 1.2 <= H - 0.6:
                        cand = (size, -len(ls), rot == 0, rot, ls)
                        if best is None or cand[:3] > best[:3]:
                            best = cand
        if best:
            size, _, _, rot, ls = best
            g.append(mtext(cx, cy, ls, size, weight='700', fill='#1d1d1d', rot=rot, weights=['800'] + ['600'] * (len(ls) - 1)))
        else:
            size = 1.3
            g.append(mtext(cx, cy, [tag, dims], size, weight='800', fill='#1d1d1d', rot=-90 if h > w else 0))

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
                ty = y0 + 0.35 if back == 'N' else y1 - 0.35
                g.append(text(sx((x0 + x1) / 2), sy(ty) + 0.7, f"BANCA CORRIDA · {b.get('seats')} puestos · fondo {min(x1-x0, y1-y0):.2f}", 1.8, weight='700', fill='#123d16'))
        for t in lay.get('tables', []):
            g.append(rect_el(t['rect'], tf, ts, 0.3, extra='rx="0.4"'))
        for c in lay.get('chairs', []):
            x0, y0, x1, y1 = c['rect']
            g.append(rect_el(c['rect'], cf, cs, 0.25, extra='rx="1.1"'))
            fc = c.get('facing')
            if fc in ('N', 'S', 'E', 'W'):
                t_ = 0.07
                r = {'S': (x0 + 0.04, y0, x1 - 0.04, y0 + t_), 'N': (x0 + 0.04, y1 - t_, x1 - 0.04, y1),
                     'E': (x0, y0 + 0.04, x0 + t_, y1 - 0.04), 'W': (x1 - t_, y0 + 0.04, x1, y1 - 0.04)}[fc]
                g.append(rect_el(r, cs, cs, 0.1))
        if not faint:
            for t in lay.get('tables', []):
                x0, y0, x1, y1 = t['rect']
                g.append(mtext(sx((x0 + x1) / 2), sy((y0 + y1) / 2), [t.get('tag', t['id']), f"{t['seats']}p · {(x1-x0)*100:.0f}×{(y1-y0)*100:.0f}"],
                               1.45, weight='700', fill='#1f5f25', weights=['800', '600']))
        g.append('</g>')
        self.add(''.join(g))

    def layer_routes(self, width=0.9, opacity=0.85):
        lay = self.lay
        g = ['<g id="routes">']
        rinfo = {r['id']: r for r in (self.m.get('routes') or [])}
        for r in lay.get('routes', []):
            c, dash = ROUTE.get(r.get('kind'), ('#333', None))
            d = f' stroke-dasharray="{dash}"' if dash else ''
            g.append(f'<polyline points="{pts_attr(r["pts"])}" fill="none" stroke="{c}" stroke-width="{width}" stroke-opacity="{opacity}" '
                     f'stroke-linecap="round" stroke-linejoin="round"{d} marker-end="url(#arr-{r.get("kind")})"/>')
            if r['id'] in rinfo and rinfo[r['id']].get('at'):
                at = rinfo[r['id']]['at']
                w = rinfo[r['id']]['min_width']
                x, y = sx(at[0]), sy(at[1])
                g.append(f'<g><rect x="{f(x - 5.4)}" y="{f(y - 2.1)}" width="10.8" height="4.2" rx="2.1" fill="#fff" stroke="{c}" stroke-width="0.35"/>'
                         + text(x, y + 0.75, f"↔ {w:.2f}", 2.0, family=MONO, weight='700', fill=c) + '</g>')
        g.append('</g>')
        self.add(''.join(g))

    def grid_axes(self):
        g = ['<g id="axes">']
        top = -2.05
        for name, x in (('A', 0.0), ('B', 7.8), ('C', 16.3)):
            g.append(f'<line x1="{f(sx(x))}" y1="{f(sy(top + 0.15))}" x2="{f(sx(x))}" y2="{f(sy(-0.62))}" stroke="#8a8a85" stroke-width="0.15" stroke-dasharray="1.5 0.6 0.3 0.6"/>')
            g.append(f'<circle cx="{f(sx(x))}" cy="{f(sy(top))}" r="2.5" fill="#fff" stroke="#555" stroke-width="0.3"/>')
            g.append(text(sx(x), sy(top) + 1.05, name, 2.9, weight='700', fill='#444'))
        for name, y in (('1', 0.0), ('2', 8.5)):
            g.append(f'<line x1="{f(sx(-1.45))}" y1="{f(sy(y))}" x2="{f(sx(-0.9))}" y2="{f(sy(y))}" stroke="#8a8a85" stroke-width="0.15"/>')
            g.append(f'<circle cx="{f(sx(-1.55))}" cy="{f(sy(y))}" r="2.5" fill="#fff" stroke="#555" stroke-width="0.3"/>')
            g.append(text(sx(-1.55), sy(y) + 1.05, name, 2.9, weight='700', fill='#444'))
        g.append('</g>')
        self.add(''.join(g))

    # ------------------------------------------------------------------ sheet furniture
    def frame_and_titleblock(self, title, subtitle, number):
        W, H = SHEET_W, SHEET_H
        g = [f'<rect x="5" y="5" width="{W-10}" height="{H-10}" fill="none" stroke="#111" stroke-width="0.6"/>',
             f'<line x1="436" y1="5" x2="436" y2="{H-5}" stroke="#111" stroke-width="0.35"/>']
        tb_y = H - 62
        g.append(f'<rect x="436" y="{tb_y}" width="{W-441}" height="57" fill="#141210"/>')
        g.append(text(442, tb_y + 11, 'LΛVΛ', 9.5, anchor='start', weight='800', fill='#ece5d8', family=DISPLAY, extra='letter-spacing="1.5"'))
        g.append(text(442, tb_y + 16.5, 'CONTEMPORARY FIRE & BBQ', 2.3, anchor='start', weight='600', fill='#ff7a1a', extra='letter-spacing="0.6"'))
        g.append(text(442, tb_y + 23.5, 'Local ex-Marna\'s · Terrazas Lindora, Santa Ana', 2.2, anchor='start', fill='#ece5d8'))
        g.append(text(442, tb_y + 30.5, title, 3.1, anchor='start', weight='700', fill='#ffffff'))
        g.append(text(442, tb_y + 35.5, subtitle, 1.95, anchor='start', fill='#cfc6b8'))
        g.append(text(442, tb_y + 42, 'TEST-FIT CONCEPTUAL · NO ES PLANO CONSTRUCTIVO', 2.1, anchor='start', weight='700', fill='#ff7a1a'))
        g.append(text(442, tb_y + 47, 'Base: vectores del PDF Marna\'s Rev8 Opción 1 (1:50). Validar con arquitecto e ingenierías.', 1.6, anchor='start', fill='#b9b0a2'))
        ver = self.lay.get('meta', {}).get('version', '')
        g.append(text(442, tb_y + 51.5, f"Escala 1:50 en A2 · cotas en metros · v{ver} · {datetime.date(2026, 9, 25).isoformat()}", 1.7, anchor='start', fill='#b9b0a2', family=MONO))
        g.append(f'<rect x="{W-40}" y="{tb_y + 22}" width="30" height="30" fill="none" stroke="#ece5d8" stroke-width="0.35"/>')
        g.append(text(W - 25, tb_y + 30, 'LÁMINA', 1.8, fill='#b9b0a2'))
        g.append(text(W - 25, tb_y + 42, number, 7.0, weight='800', fill='#ffffff'))
        x0, y0 = sx(8.75), sy(12.55)
        seg = ['<g id="scalebar">']
        for i in range(5):
            seg.append(f'<rect x="{f(x0 + i*S)}" y="{f(y0)}" width="{S}" height="1.3" fill="{"#111" if i % 2 == 0 else "#fff"}" stroke="#111" stroke-width="0.2"/>')
            seg.append(text(x0 + i * S, y0 + 4.2, str(i), 1.8, family=MONO))
        seg.append(text(x0 + 5 * S, y0 + 4.2, '5 m', 1.8, family=MONO))
        seg.append(text(x0 + 5 * S + 4, y0 + 1.4, '1:50', 2.0, anchor='start', weight='700'))
        seg.append('</g>')
        g.extend(seg)
        nx, ny = sx(15.05), sy(12.62)
        g.append(f'<g id="north"><circle cx="{f(nx)}" cy="{f(ny)}" r="4.2" fill="none" stroke="#333" stroke-width="0.3"/>'
                 f'<path d="M{f(nx)},{f(ny-3.5)} L{f(nx+1.7)},{f(ny+2.1)} L{f(nx)},{f(ny+1.0)} L{f(nx-1.7)},{f(ny+2.1)} z" fill="#333"/>'
                 + text(nx + 6, ny - 0.6, 'Orientación del PDF', 1.6, anchor='start', fill='#555')
                 + text(nx + 6, ny + 1.6, 'original (no geográfica)', 1.6, anchor='start', fill='#555') + '</g>')
        self.add(''.join(g))

    def side_panel(self, blocks, x=441.0, y=13.0):
        g = ['<g id="side-panel">']
        for kind, payload in blocks:
            if kind == 'h':
                g.append(text(x, y + 3, payload.upper(), 2.6, anchor='start', weight='800', fill='#141210', extra='letter-spacing="0.35"'))
                g.append(f'<line x1="{x}" y1="{y + 4.6}" x2="{SHEET_W - 10}" y2="{y + 4.6}" stroke="#141210" stroke-width="0.3"/>')
                y += 8.2
            elif kind == 'legend':
                for sw, label in payload:
                    g.append(sw(x, y))
                    g.append(text(x + 12, y + 2.6, label, 2.05, anchor='start', weight='700' if label.isupper() else '400'))
                    y += 4.5
                y += 1.4
            elif kind == 'rows':
                for a, b in payload:
                    g.append(text(x, y + 2.6, a, 2.0, anchor='start', fill='#333'))
                    g.append(text(SHEET_W - 11, y + 2.6, b, 2.0, anchor='end', weight='700', family=MONO))
                    g.append(f'<line x1="{x}" y1="{y + 3.8}" x2="{SHEET_W - 10}" y2="{y + 3.8}" stroke="#e1ddd6" stroke-width="0.2"/>')
                    y += 4.3
                y += 1.4
            elif kind == 'para':
                for ln in payload:
                    style = ln.startswith('!')
                    s = ln[1:] if style else ln
                    g.append(text(x, y + 2.4, s, 1.9, anchor='start', weight='700' if style else '400',
                                  fill='#b00020' if style else '#2a2a2a'))
                    y += 3.2
                y += 1.6
        g.append('</g>')
        self.add(''.join(g))
        return y

    def schedule(self, x, y, w, rows_max=12):
        eq = [e for e in self.lay.get('equipment', [])]
        order = {'fire': 0, 'hood': 1, 'smoker': 2, 'prep': 3, 'cold': 4, 'wash': 5, 'storage': 6, 'bar': 7, 'delivery': 8, 'misc': 9}
        eq.sort(key=lambda e: (order.get(e.get('cat'), 9), e.get('tag', e['id'])))
        g = ['<g id="schedule">']
        g.append(text(x, y + 3, 'CUADRO DE EQUIPOS', 2.6, anchor='start', weight='800', extra='letter-spacing="0.35"'))
        g.append(text(x + 52, y + 3, 'frente × fondo × alto (m) · * = DIMENSION TO VERIFY', 1.9, anchor='start', fill='#b00020'))
        y += 6
        cols = max(1, math.ceil(len(eq) / rows_max))
        cw = w / cols
        for i, e in enumerate(eq):
            c, r = divmod(i, rows_max)
            xx, yy = x + c * cw, y + r * 4.05
            x0, y0, x1, y1 = e['rect']
            wd, dp = abs(x1 - x0), abs(y1 - y0)
            a, b = (wd, dp) if e.get('front') in ('N', 'S') else (dp, wd)
            if e.get('front') not in ('N', 'S', 'E', 'W'):
                a, b = max(wd, dp), min(wd, dp)
            fill, stroke = COL.get(e.get('cat', 'misc'), COL['misc'])
            g.append(f'<rect x="{f(xx)}" y="{f(yy)}" width="3" height="3" fill="{fill if fill != "none" else "#fff"}" stroke="{stroke}" stroke-width="0.3"/>')
            g.append(text(xx + 4.2, yy + 2.5, e.get('tag', e['id']), 1.95, anchor='start', weight='800', fill=stroke))
            g.append(text(xx + 10.5, yy + 2.5, e.get('label', '')[:40], 1.9, anchor='start'))
            dims = f"{a:.2f}×{b:.2f}" + (f"×{float(e['h']):.2f}" if e.get('h') and not e.get('overhead') else '')
            g.append(text(xx + cw - 3, yy + 2.5, dims + ('*' if e.get('tbv') else ''), 1.8, anchor='end', family=MONO,
                          fill='#b00020' if e.get('tbv') else '#222'))
        g.append('</g>')
        self.add(''.join(g))

    def flow_diagram(self, x, y):
        g = ['<g id="flow-diagram">', text(x, y + 3, 'LÓGICA OPERATIVA (fijada por el cliente)', 2.6, anchor='start', weight='800', extra='letter-spacing="0.3"')]
        steps = [('A', 'COLD PREP', ZONE_FILL['A']), ('E', 'BBQ PRODUCTION', ZONE_FILL['E']), ('B', 'HOT LINE', ZONE_FILL['B']),
                 ('C', 'PASE · BAR / POS', ZONE_FILL['C']), ('D', 'DINING', ZONE_FILL['D'])]
        bw, bh, gap = 64, 10, 14.5
        yy = y + 8
        for i, (z, name, c) in enumerate(steps):
            xx = x + i * (bw + gap)
            g.append(f'<rect x="{f(xx)}" y="{f(yy)}" width="{bw}" height="{bh}" rx="1.5" fill="{c}" fill-opacity="0.12" stroke="{c}" stroke-width="0.5"/>')
            g.append(f'<circle cx="{f(xx + 5.5)}" cy="{f(yy + bh/2)}" r="3.0" fill="{c}"/>')
            g.append(text(xx + 5.5, yy + bh / 2 + 1.1, z, 3.0, weight='800', fill='#fff'))
            g.append(text(xx + 10.5, yy + bh / 2 + 0.9, name, 2.5, anchor='start', weight='800', fill=c, family=DISPLAY))
            if i < len(steps) - 1:
                g.append(f'<line x1="{f(xx + bw + 1)}" y1="{f(yy + bh/2)}" x2="{f(xx + bw + gap - 1.5)}" y2="{f(yy + bh/2)}" stroke="{ROUTE["clean"][0]}" stroke-width="0.8" marker-end="url(#arr-clean)"/>')
        yy2 = yy + bh + 10
        back = [('D', 'DINING', ZONE_FILL['D']), ('P', 'PUERTA P-1', '#555555'), ('W', 'WASHING (PILAS)', ZONE_FILL['W'])]
        for i, (z, name, c) in enumerate(back):
            xx = x + (4 - i) * (bw + gap)
            g.append(f'<rect x="{f(xx)}" y="{f(yy2)}" width="{bw}" height="{bh}" rx="1.5" fill="#fff" stroke="{ROUTE["dirty"][0]}" stroke-width="0.5" stroke-dasharray="1.5 1"/>')
            g.append(f'<circle cx="{f(xx + 5.5)}" cy="{f(yy2 + bh/2)}" r="3.0" fill="{c}"/>')
            g.append(text(xx + 5.5, yy2 + bh / 2 + 1.1, z, 3.0, weight='800', fill='#fff'))
            g.append(text(xx + 10.5, yy2 + bh / 2 + 0.9, name, 2.5, anchor='start', weight='800', fill=c, family=DISPLAY))
            if i < len(back) - 1:
                g.append(f'<line x1="{f(xx - 1)}" y1="{f(yy2 + bh/2)}" x2="{f(xx - gap + 1.5)}" y2="{f(yy2 + bh/2)}" stroke="{ROUTE["dirty"][0]}" stroke-width="0.8" stroke-dasharray="2 1" marker-end="url(#arr-dirty)"/>')
        g.append(text(x, yy2 + bh + 6.5, 'La loza sucia entra por P-1 y baja directo al lavado (antiguas PILAS): no pasa por COLD PREP ni por el pasillo limpio del muro oeste.', 2.1, anchor='start', fill='#b00020', weight='600'))
        g.append('</g>')
        self.add(''.join(g))

    def wall_table(self, x, y):
        ex, lay = self.ex, self.lay
        gone = {d['id'] for d in lay.get('demolish', []) if 'rect' not in d}
        partial = {d['id'] for d in lay.get('demolish', []) if 'rect' in d and not d.get('conditional')}
        cond = {d['id'] for d in lay.get('demolish', []) if d.get('conditional')}
        g = ['<g id="wall-table">', text(x, y + 3, 'EVALUACIÓN DE MUROS EXISTENTES (lectura del PDF + criterio · VERIFY ON SITE)', 2.6, anchor='start', weight='800', extra='letter-spacing="0.3"')]
        y += 6.5
        cols = [(0, 'ID'), (19, 'Descripción'), (150, 'Esp.'), (164, 'Trama'), (178, 'Lectura estructural'), (320, 'Acción')]
        for dx, h in cols:
            g.append(text(x + dx, y + 2.4, h, 1.9, anchor='start', weight='700', fill='#555'))
        y += 4.1
        walls = [w_ for w_ in ex['walls'] if w_['kind'] in ('perimeter', 'partition_light', 'pilaster_shafts')]
        rh = min(3.45, (408 - y) / max(1, len(walls)))
        for i, w_ in enumerate(walls):
            yy = y + i * rh
            x0, y0, x1, y1 = w_['rect']
            t = min(abs(x1 - x0), abs(y1 - y0))
            if w_['id'] in gone:
                act = 'WALL TO DEMOLISH'
            elif w_['id'] in partial:
                act = 'RECORTE PARCIAL'
            elif w_['id'] in cond:
                act = 'RECORTE CONDICIONAL (PS-1)'
            else:
                act = 'EXISTING WALL · MANTENER'
            colr = COL['demolish'] if act != 'EXISTING WALL · MANTENER' else '#333'
            vals = [w_['id'], w_['note'][:74], f"{t*100:.0f} cm", 'sí' if w_.get('hatched') else 'no', w_.get('structural_guess', '')[:62], act]
            for (dx, _), v in zip(cols, vals):
                g.append(text(x + dx, yy + 2.4, v, 1.7, anchor='start', fill=colr if dx in (0, 320) else '#222',
                              weight='700' if dx in (0, 320) else '400', family=MONO if dx == 150 else FONT))
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
    (sw_rect(None, COL['existing_stroke'], pattern='url(#hatch-ex)'), 'EXISTING WALL (gris · se mantiene)'),
    (sw_rect(None, COL['demolish'], dash='1.2 0.8', pattern='url(#hatch-demo)'), 'WALL TO DEMOLISH (rojo punteado)'),
    (sw_rect('#111', '#000'), 'NEW PROPOSED WALL (negro)'),
    (sw_glass(), 'Nueva división: base sólida + vidrio'),
]
LEGEND_EQ = [
    (sw_rect(*COL['fire']), 'Fuego / hot line (naranja)'),
    (sw_rect('none', COL['hood'][1], dash='2 0.8'), 'Campana (proyección en altura)'),
    (sw_rect(None, COL['smoker'][1], pattern='url(#hatch-smoker)'), 'Smoker combustible sólido'),
    (sw_rect(*COL['cold']), 'Refrigeración / prep fría (azul)'),
    (sw_rect(*COL['prep']), 'Mesas de trabajo inox'),
    (sw_rect(*COL['wash']), 'Lavado'),
    (sw_rect(*COL['storage']), 'Almacén / leña'),
    (sw_rect(*COL['bar']), 'Barra / POS / pase'),
    (sw_rect(*COL['delivery']), 'Delivery / recepción'),
    (sw_rect(*COL['table']), 'Dining: mesas, sillas, bancas (verde)'),
]


def metrics_rows(ex, lay, val):
    m = (val or {}).get('metrics', {})
    rows = [('Asientos en salón', f"{seat_count(lay)}")]
    if m.get('new_partition_x') is not None:
        rows.append(('Corrimiento división cocina/salón', f"{m.get('partition_shift_m', 0):.2f} m"))
    zones = {z['id']: z for z in m.get('zones', [])}
    for z in lay.get('zones', []):
        if z['id'] in zones:
            rows.append((f"{z['id']} · {z.get('short', z.get('name', ''))}"[:34], f"{zones[z['id']]['area_m2']:.1f} m²"))
    for r in m.get('routes', []):
        if r['id'] in ('R-server', 'R-clean', 'R-dirty', 'R-expo'):
            rows.append((f"Ancho mín. {r.get('label') or r['id']}"[:40], f"{r['min_width']:.2f} m"))
    if m.get('hot_line_length'):
        rows.append(('Línea caliente / campana dibujada', f"{m['hot_line_length']:.2f} / {m.get('hood_length', 0):.2f} m"))
    if m.get('seats_with_parrilla_view_pct') is not None:
        rows.append(('Asientos con vista a la parrilla', f"{m['seats_with_parrilla_view_pct']:.0f} %"))
    return rows


def build(lay_path, val_path, outdir):
    ex = load_existing()
    lay = load_json(lay_path)
    val = load_json(val_path) if val_path and os.path.exists(val_path) else None
    os.makedirs(outdir, exist_ok=True)
    out = {}

    # ---------------- A-101 planta propuesta
    s = Sheet(ex, lay, val, 'A101')
    s.frame_and_titleblock('A-101 · Planta propuesta (test-fit)', 'Zonificación operativa, equipos con nombre y medida, mobiliario y cotas', 'A-101')
    s.grid_axes()
    s.layer_zones(0.09)
    s.layer_existing()
    s.layer_demolish()
    s.layer_furniture()
    s.layer_equipment()
    s.layer_new()
    s.zone_labels()
    s.dims_for('dims', 'A101')
    s.keynotes('A101')
    s.side_panel([
        ('h', 'Leyenda'), ('legend', LEGEND_WALLS + LEGEND_EQ),
        ('h', 'Cifras clave (medidas sobre la planta)'), ('rows', metrics_rows(ex, lay, val)),
        ('h', 'Notas'), ('para', lay.get('sheet_notes', [])),
    ])
    n_eq = len(lay.get('equipment', []))
    s.schedule(12, 322, 420, rows_max=max(1, math.ceil(n_eq / 3)))
    out['A101'] = s.render()

    # ---------------- A-102 demolición / construcción
    s = Sheet(ex, lay, val, 'A102')
    s.frame_and_titleblock('A-102 · Existente / demolición / nuevo', 'EXISTING WALL · WALL TO DEMOLISH · NEW PROPOSED WALL · corrimiento de la división', 'A-102')
    s.grid_axes()
    s.layer_existing()
    s.layer_demolish()
    s.layer_new()
    s.dims_for('dims', 'A102')
    s.dims_for('dims_demo', 'A102')
    s.keynotes('A102')
    demo_rows = []
    for d in lay.get('demolish', []):
        w = next((w for w in ex['walls'] if w['id'] == d['id']), None)
        if not w:
            continue
        r = d.get('rect') or w['rect']
        x0, y0, x1, y1 = r
        tag = ' (condicional)' if d.get('conditional') else (' (parcial)' if 'rect' in d else '')
        demo_rows.append((f"{d['id']}{tag}", f"{max(abs(x1-x0), abs(y1-y0)):.2f} m"))
    new_rows = []
    for w in lay.get('new_walls', []):
        x0, y0, x1, y1 = w['rect']
        new_rows.append((f"{w['id']} · {(w.get('short') or w.get('type'))[:30]}", f"{max(abs(x1-x0), abs(y1-y0)):.2f} m"))
    for o in lay.get('new_openings', []):
        new_rows.append((f"{o['id']} · {o['type'].replace('_', ' ')}{' (condicional)' if o.get('conditional') else ''}"[:40], f"{o.get('width', 0):.2f} m"))
    s.side_panel([
        ('h', 'Leyenda'), ('legend', LEGEND_WALLS),
        ('h', 'Wall to demolish (livianas)'), ('rows', demo_rows),
        ('h', 'New proposed wall / vanos'), ('rows', new_rows),
        ('h', 'Criterio estructural'), ('para', lay.get('structure_notes', [])),
    ])
    s.wall_table(12, 322)
    out['A102'] = s.render()

    # ---------------- A-103 flujos
    s = Sheet(ex, lay, val, 'A103')
    s.frame_and_titleblock('A-103 · Flujos y circulaciones', 'Limpio / sucio / platos / clientes / delivery / combustible · anchos mínimos medidos', 'A-103')
    s.grid_axes()
    s.layer_zones(0.07)
    s.layer_existing()
    s.layer_new()
    s.layer_furniture(faint=True)
    s.layer_equipment(faint=True, labels=False)
    s.zone_labels(big=False)
    s.layer_routes()
    kinds = []
    for r in lay.get('routes', []):
        if r.get('kind') not in kinds:
            kinds.append(r.get('kind'))
    leg = [(sw_line(ROUTE[k][0], ROUTE[k][1]), ROUTE_NAME.get(k, k)) for k in kinds if k in ROUTE]
    m = (val or {}).get('metrics', {})
    rrows = [(f"{r.get('label') or r['id']}"[:44], f"{r['min_width']:.2f} (≥{r['required']:.2f})") for r in m.get('routes', [])]
    s.side_panel([
        ('h', 'Flujos'), ('legend', leg),
        ('h', 'Ancho libre mínimo medido (m)'), ('rows', rrows),
        ('para', ['Medido sobre la planta entre equipos, sillas ocupadas y', 'muros a lo largo de cada recorrido.',
                  '!Principal objetivo 1.10–1.20 m · secundaria ≥ 0.90 m.']),
        ('h', 'Separación limpio / sucio'), ('para', lay.get('flow_notes', [])),
    ])
    s.flow_diagram(12, 322)
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
