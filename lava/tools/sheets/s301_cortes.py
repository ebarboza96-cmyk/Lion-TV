"""A-301 · Cortes y elevaciones (A2; cortes 1:50, elevaciones 1:25; coordenadas propias de dibujo, no la VIEW de planta).

Plug-in de lámina extra: sheets(ex, lay, val) -> [{id, file, title, order, svg}].

Dibuja, desde data/existing.json + data/layout.json (y la misma distribución de cielo que A-201):
  * Corte A-A longitudinal por la parrilla (Y del centro de la parrilla): acceso → salón → división NW-1 → parrilla /
    campana HD-2 → BBQ → muro oeste, mirando al norte;
  * Corte B-B transversal por la línea caliente (X común a todos los equipos de la línea): muro norte → freidoras →
    plancha → cocina → parrilla → NW-2 → P-1 → ala de servicio, mirando al este;
  * Elevación E-1 de la división cocina/salón vista desde el salón (muro bajo + vidrio + rótulo + relieve de leños + P-1);
  * Elevación E-2 de barra + caja accesible (1.05 / 0.80) vista desde el salón;
  * planta clave 1:200 con las líneas de corte y las elevaciones.
Alturas: equipment.h, new_walls.h/base_h, decor.h/z, existing.ceiling.height_assumed (3.00 VERIFY ON SITE), borde de
campana = panel NW-2 (piso-campana). Mobiliario (mesas 0.75, sillas 0.45) y puertas 2.10 son referenciales (TBV).
ANTEPROYECTO: a validar por el profesional responsable (CFIA) y los ingenieros mecánico / electricista.
"""
import math
import os
import sys

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lavageo import R, premises, standing_existing_walls  # noqa: E402
from plan_svg import COL, DISPLAY, FONT, MONO, Sheet, f, mtext, text, tw  # noqa: E402

try:
    from sheets.s201_cielos import C_EGR, C_FLUE, C_GREASE, C_MUA, C_RED, C_SOLID, _rect, ceiling_layout, filter_min  # noqa: E402
except ImportError:  # pragma: no cover
    from s201_cielos import C_EGR, C_FLUE, C_GREASE, C_MUA, C_RED, C_SOLID, _rect, ceiling_layout, filter_min  # noqa: E402

DOOR_H = 2.10          # altura de puertas (referencial, TBV)
TABLE_H = 0.75         # mesas (referencial)
SEAT_H = 0.45
CHAIR_BACK = 0.85
BANQ_BACK = 0.95
SLAB_T = 0.25          # espesor de losa dibujado (desconocido: VERIFY ON SITE)
Z_TOP = 4.35           # tope del dibujo (flechas "a cubierta")
FILTER_UP = 0.10       # borde inferior de filtros sobre el borde de campana (TBV)
STK_BEY = '#5f5f5a'
STK_GHOST = '#b3b3ae'
CORTEN = '#b87a55'
BASE_FILL = '#dcc6b2'
GLASS = '#35b6e8'
DEFS = ('<defs>'
        '<pattern id="s-hatch-ex" patternUnits="userSpaceOnUse" width="1.2" height="1.2" patternTransform="rotate(45)">'
        '<rect width="1.2" height="1.2" fill="#a8a8a5"/><line x1="0" y1="0" x2="0" y2="1.2" stroke="#6e6e6a" stroke-width="0.25"/></pattern>'
        '<pattern id="s-conc" patternUnits="userSpaceOnUse" width="3" height="3">'
        '<rect width="3" height="3" fill="#e4e2dd"/><circle cx="0.8" cy="0.9" r="0.28" fill="#9d9a93"/><circle cx="2.2" cy="2.1" r="0.2" fill="#9d9a93"/>'
        '<path d="M1.6,0.4 l0.5,0.5 M0.3,2.3 l0.4,-0.4" stroke="#9d9a93" stroke-width="0.15"/></pattern>'
        '<pattern id="s-base" patternUnits="userSpaceOnUse" width="1.6" height="1.6" patternTransform="rotate(-45)">'
        f'<rect width="1.6" height="1.6" fill="{BASE_FILL}"/><line x1="0" y1="0" x2="0" y2="1.6" stroke="#9c7a5e" stroke-width="0.18"/></pattern>'
        '<pattern id="s-ct2" patternUnits="userSpaceOnUse" width="1.6" height="1.6">'
        '<rect width="1.6" height="1.6" fill="#fdecd9"/><path d="M0.5,0.8 H1.1 M0.8,0.5 V1.1" stroke="#c2410c" stroke-width="0.14"/></pattern>'
        '<pattern id="s-ct3" patternUnits="userSpaceOnUse" width="1.6" height="1.6">'
        '<rect width="1.6" height="1.6" fill="#e3eefb"/><circle cx="0.8" cy="0.8" r="0.2" fill="#2f6fd0"/></pattern>'
        '<marker id="s-arr" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.2" markerHeight="3.2" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#333"/></marker>'
        '<marker id="s-arr-g" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.2" markerHeight="3.2" orient="auto">'
        f'<path d="M0,0 L6,3 L0,6 z" fill="{C_GREASE}"/></marker>'
        '<marker id="s-arr-s" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.2" markerHeight="3.2" orient="auto">'
        f'<path d="M0,0 L6,3 L0,6 z" fill="{C_SOLID}"/></marker>'
        '<marker id="s-arr-f" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.2" markerHeight="3.2" orient="auto">'
        f'<path d="M0,0 L6,3 L0,6 z" fill="{C_FLUE}"/></marker>'
        '<marker id="s-arr-m" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.2" markerHeight="3.2" orient="auto">'
        f'<path d="M0,0 L6,3 L0,6 z" fill="{C_MUA}"/></marker>'
        '</defs>')
ARR = {C_GREASE: 's-arr-g', C_SOLID: 's-arr-s', C_FLUE: 's-arr-f', C_MUA: 's-arr-m'}


# ============================================================================================== view engine
class View:
    """Orthographic section / elevation. Plane = {axis}=at; look = unit plan vector; u = right-hand coordinate."""

    def __init__(self, name, axis, at, look, u_lim, k, ox, oz, max_depth=99.0, ghost_depth=None, z_lim=(-0.3, Z_TOP)):
        self.name, self.axis, self.at, self.look = name, axis, at, look
        self.rx, self.ry = -look[1], look[0]
        self.u_lim, self.k, self.ox, self.oz = u_lim, k, ox, oz
        self.max_depth, self.ghost_depth, self.z_lim = max_depth, ghost_depth, z_lim
        self.parts = []          # (layer, key, svg)
        self.occ = []            # label obstacles (sheet boxes)
        self.solids = []         # opaque (u0, u1, z0, z1, depth) for occlusion tests
        self.lbox = None         # allowed label area (sheet mm)

    # ---- mapping
    def U(self, x, y):
        return x * self.rx + y * self.ry

    def X(self, u):
        return self.ox + (u - self.u_lim[0]) * self.k

    def Z(self, z):
        return self.oz - z * self.k

    def span(self, rect):
        x0, y0, x1, y1 = _rect(rect)
        us = [self.U(x, y) for x, y in ((x0, y0), (x1, y1))]
        a, b = min(us), max(us)
        if b < self.u_lim[0] or a > self.u_lim[1]:
            return None
        return max(a, self.u_lim[0]), min(b, self.u_lim[1])

    def classify(self, rect):
        """-> ('cut'|'beyond'|'ghost'|None, depth)."""
        x0, y0, x1, y1 = _rect(rect)
        p0, p1 = (y0, y1) if self.axis == 'y' else (x0, x1)
        sg = self.look[1] if self.axis == 'y' else self.look[0]
        tol = 2e-3
        if p0 + tol < self.at < p1 - tol:
            return 'cut', 0.0
        if sg > 0 and p0 >= self.at - tol:
            d = max(0.0, p0 - self.at)
        elif sg < 0 and p1 <= self.at + tol:
            d = max(0.0, self.at - p1)
        else:
            return None, None
        if d > self.max_depth:
            return None, None
        if self.ghost_depth is not None and d > self.ghost_depth:
            return 'ghost', d
        return 'beyond', d

    # ---- primitives (sheet mm)
    def rect(self, u0, u1, z0, z1, fill, stroke, sw=0.25, dash=None, extra=''):
        a, b = sorted((self.X(u0), self.X(u1)))
        c, d = sorted((self.Z(z0), self.Z(z1)))
        ds = f' stroke-dasharray="{dash}"' if dash else ''
        return f'<rect x="{f(a)}" y="{f(c)}" width="{f(b - a)}" height="{f(d - c)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{ds} {extra}/>'

    def line(self, u0, z0, u1, z1, stroke, sw=0.25, dash=None, extra=''):
        ds = f' stroke-dasharray="{dash}"' if dash else ''
        return f'<line x1="{f(self.X(u0))}" y1="{f(self.Z(z0))}" x2="{f(self.X(u1))}" y2="{f(self.Z(z1))}" stroke="{stroke}" stroke-width="{sw}"{ds} {extra}/>'

    def poly(self, pts, fill, stroke, sw=0.25, dash=None, closed=True, extra=''):
        ds = f' stroke-dasharray="{dash}"' if dash else ''
        tag = 'polygon' if closed else 'polyline'
        return f'<{tag} points="{" ".join(f"{f(self.X(u))},{f(self.Z(z))}" for u, z in pts)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{ds} {extra}/>'

    def txt(self, u, z, s, size=1.7, anchor='middle', weight='600', fill='#1b1b1b', family=FONT, rot=0, halo=False):
        ex = 'paint-order="stroke" stroke="#ffffff" stroke-width="0.8"' if halo else ''
        return text(self.X(u), self.Z(z), s, size, anchor, weight, fill, family, rot, extra=ex)

    def put(self, layer, key, svg):
        self.parts.append((layer, key, svg))

    def block(self, u0, u1, z0, z1, w=1.0):
        a, b = sorted((self.X(u0), self.X(u1)))
        c, d = sorted((self.Z(z0), self.Z(z1)))
        self.occ.append((box(a, c, b, d), w))

    def solid(self, u0, u1, z0, z1, d):
        self.solids.append((min(u0, u1), max(u0, u1), min(z0, z1), max(z0, z1), d or 0.0))

    def hidden(self, u0, u1, z0, z1, d):
        occ = [box(a, c, b, e) for a, b, c, e, dd in self.solids if dd < (d or 0.0) - 1e-3]
        if not occ:
            return False
        b = box(u0, z0, u1, z1)
        return b.area > 0 and unary_union(occ).intersection(b).area >= 0.8 * b.area

    def render(self, clip_id=None):
        parts = sorted(self.parts, key=lambda t: (t[0], t[1]))
        body = ''.join(s for ly, _, s in parts if ly < 5)
        notes = ''.join(s for ly, _, s in parts if ly >= 5)
        if not clip_id:
            return body + notes
        x0, x1 = self.X(self.u_lim[0]), self.X(self.u_lim[1])
        y0, y1 = self.Z(self.z_lim[1]), self.Z(self.z_lim[0])
        return (f'<clipPath id="{clip_id}"><rect x="{f(x0)}" y="{f(y0)}" width="{f(x1 - x0)}" height="{f(y1 - y0)}"/></clipPath>'
                f'<g clip-path="url(#{clip_id})">{body}</g>' + notes)

    # ---- label placement (sheet mm)
    def label(self, lines, target, cands, color='#1b1b1b', size=1.6, weights=None, leader=True, bg=True):
        """target/cands in (u, z); returns svg and registers the box."""
        w = max(tw(s, size) for s in lines) + 1.4
        h = len(lines) * size * 1.22 + 0.8
        lboxes = getattr(self, '_lboxes', [])
        tpt = (self.X(target[0]), self.Z(target[1])) if (leader and target) else None

        def _leader(cx, cy, b):
            if tpt is None or b.buffer(0.3).contains(Point(*tpt)):
                return None
            bx = min(max(tpt[0], cx - w / 2), cx + w / 2)
            by = cy + h / 2 if tpt[1] > cy + h / 2 else (cy - h / 2 if tpt[1] < cy - h / 2 else tpt[1])
            return LineString([(bx, by), tpt])
        best = None
        lleads = getattr(self, '_leaders', [])
        for i, cand in enumerate(cands):
            cu, cz = cand[0], cand[1]
            pen = cand[2] if len(cand) > 2 else 0.0      # optional per-candidate penalty
            cx, cy = self.X(cu), self.Z(cz)
            b = box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            c = sum(wt * (g.intersection(b).area if g.geom_type in ('Polygon', 'MultiPolygon') else g.intersection(b).length)
                    for g, wt in self.occ if g.intersects(b)) + i * 0.05 + pen
            if self.lbox and not box(*self.lbox).contains(b):
                c += 1000
            ld = _leader(cx, cy, b)
            if ld is not None:   # a leader must not run across another label, nor cross another leader
                c += 20 * sum(ld.intersection(q).length for q in lboxes if q.intersects(ld))
                c += 20 * sum(1 for q in lleads if q.crosses(ld))
            c += 20 * sum(b.intersection(q).length for q in lleads if q.intersects(b))
            c += 60 * sum(b.intersection(q).area for q in lboxes if q.intersects(b))     # never stack labels
            if best is None or c < best[0]:
                best = (c, cx, cy, b)
        _, cx, cy, b = best
        self.occ.append((b, 4))
        ld = _leader(cx, cy, b)
        if ld is not None:       # later labels keep off this leader
            self.occ.append((ld.buffer(0.35), 3))
            self._leaders = lleads + [ld]
        self._lboxes = lboxes + [b]
        out = []
        if leader and target:
            tx, ty = self.X(target[0]), self.Z(target[1])
            if not b.buffer(0.3).contains(Point(tx, ty)):
                bx = min(max(tx, cx - w / 2), cx + w / 2)
                by = cy + h / 2 if ty > cy + h / 2 else (cy - h / 2 if ty < cy - h / 2 else ty)
                out.append(f'<line x1="{f(bx)}" y1="{f(by)}" x2="{f(tx)}" y2="{f(ty)}" stroke="{color}" stroke-width="0.2"/>'
                           f'<circle cx="{f(tx)}" cy="{f(ty)}" r="0.4" fill="{color}"/>')
        if bg:
            out.append(f'<rect x="{f(cx - w/2)}" y="{f(cy - h/2)}" width="{f(w)}" height="{f(h)}" rx="0.5" fill="#ffffff" fill-opacity="0.93" stroke="none"/>')
        out.append(mtext(cx, cy, lines, size, weight='700', fill=color, lh=1.22, weights=weights or (['800'] + ['500'] * (len(lines) - 1))))
        return ''.join(out)


# ============================================================================================== geometry from data
def partition_info(ex, lay, ceil):
    P = next((w for w in lay.get('new_walls', []) if w.get('role') == 'kitchen_dining_partition'), None)
    if not P:
        return None
    r = _rect(P['rect'])
    base_h = float(P.get('base_h') or 1.0)
    glass_top = min(max(float(P.get('h') or ceil) - 0.5, base_h + 0.9), ceil - 0.35)   # same rule as the 3D walkthrough
    doors = []
    for o in lay.get('new_openings', []):
        if o.get('rect') and R(o['rect']).buffer(0.02).intersects(R(P['rect'])) and o.get('type') in ('door', 'double_acting_door', 'sliding_door', 'service_door', 'opening'):
            doors.append(o)
    decor = [d for d in lay.get('decor', []) if R(d['rect']).buffer(0.03).intersects(R(P['rect']))]
    return {'wall': P, 'rect': r, 'base_h': base_h, 'glass_top': glass_top, 'doors': doors, 'decor': decor}


def walls_union(ex, lay):
    return unary_union([g for _, g in standing_existing_walls(ex, lay)] + [R(c['rect']) for c in ex.get('columns', [])]
                       + [R(w['rect']) for w in lay.get('new_walls', [])])


# ============================================================================================== drawing of items
def draw_slabs(v, prem, ceil, cts_along, label_side='left'):
    """Floor + ceiling slabs over the premises extent along u, ceiling finishes per zone interval."""
    u0, u1 = v.u_lim
    a, b = cts_along['extent']
    a, b = max(u0, a - 0.35), min(u1, b + 0.35)
    g = [v.rect(a, b, -SLAB_T, 0, 'url(#s-conc)', '#555', 0.3),
         v.line(u0, 0, u1, 0, '#1b1b1b', 0.45),
         v.rect(a, b, ceil, ceil + SLAB_T, 'url(#s-conc)', '#555', 0.3)]
    for (p, q, ct) in cts_along['ivals']:
        if ct == 'CT-1':
            g.append(v.rect(p, q, ceil - 0.03, ceil, '#1b1917', '#1b1917', 0.1))
        else:
            g.append(v.rect(p, q, ceil - 0.04, ceil, 'url(#s-ct2)' if ct == 'CT-2' else 'url(#s-ct3)', '#c2410c' if ct == 'CT-2' else '#2f6fd0', 0.25))
    v.put(0, 0, ''.join(g))
    v.block(a, b, ceil - 0.04, ceil + SLAB_T, 1)
    v.block(a, b, -SLAB_T, 0, 1)


def ct_intervals(v, L, zones_poly, line_geom):
    ivals = []
    for cr in L['ct_regions']:
        inter = cr['geom'].intersection(line_geom)
        for gg in (getattr(inter, 'geoms', None) or [inter]):
            if gg.is_empty or gg.geom_type != 'LineString':
                continue
            us = [v.U(x, y) for x, y in gg.coords]
            ivals.append((min(us), max(us), cr['ct']['id']))
    return sorted(ivals)


def draw_walls(v, ex, lay, ceil, P):
    for w, geom in standing_existing_walls(ex, lay):
        for gg in (getattr(geom, 'geoms', None) or [geom]):
            _wall_piece(v, gg.bounds, ceil, existing=True)
    for c in ex.get('columns', []):
        _wall_piece(v, c['rect'], ceil, existing=True, column=True)
    for w in lay.get('new_walls', []):
        if P and w is P['wall']:
            continue
        _wall_piece(v, w['rect'], float(w.get('h') or ceil), existing=False)


def _wall_piece(v, rect, h, existing=True, column=False):
    cls, d = v.classify(rect)
    sp = v.span(rect)
    if not cls or not sp:
        return
    u0, u1 = sp
    if cls != 'ghost':
        v.solid(u0, u1, 0, h, d)
    if cls == 'cut':
        fill = 'url(#s-hatch-ex)' if existing else '#111111'
        v.put(3, 0, v.rect(u0, u1, 0, h, fill, '#222', 0.45))
        v.block(u0, u1, 0, h, 3)
    elif cls == 'beyond':
        v.put(1, -d, v.rect(u0, u1, 0, h, '#f3f2ef' if not column else '#e9e8e4', STK_BEY, 0.22))
    else:
        v.put(1, -d, v.rect(u0, u1, 0, h, 'none', STK_GHOST, 0.2, dash='1 0.6'))


def eq_shape(v, e, u0, u1, z0, z1, mode):
    """Equipment in section/elevation with light detail by key."""
    key = e.get('key', '')
    cat = e.get('cat', 'misc')
    if mode == 'cut':
        fill, stk, sw = COL.get(cat, COL['misc'])[0], COL.get(cat, COL['misc'])[1], 0.45
        if fill == 'none':
            fill = '#ffffff'
    elif mode == 'beyond':
        fill, stk, sw = ('#f3ece2' if cat == 'bar' else '#ffffff'), STK_BEY, 0.22
    else:
        fill, stk, sw = 'none', STK_GHOST, 0.18
    dash = '1 0.6' if mode == 'ghost' else None
    g = []
    w = u1 - u0
    top = z1
    if key in ('mesa_1', 'mesa_2', 'mesa_opt', 'mesa_fria', 'mesa_esquina', 'holding', 'delivery_staging') and key not in ('mesa_fria', 'holding'):
        g.append(v.rect(u0, u1, top - 0.04, top, fill, stk, sw, dash))
        g.append(v.rect(u0 + 0.03, u1 - 0.03, 0.18, 0.21, fill, stk, sw * 0.8, dash))
        for uu in (u0 + 0.04, u1 - 0.07):
            g.append(v.rect(uu, uu + 0.03, 0, top - 0.04, fill, stk, sw * 0.8, dash))
    elif key in ('sink_2t', 'mop_sink', 'handwash', 'handwash_k', 'handwash_cold', 'handwash_bar'):
        bz = max(z0, top - 0.28)
        g.append(v.rect(u0, u1, bz, top, fill, stk, sw, dash))
        g.append(v.line(u0 + 0.05, top - 0.03, u1 - 0.05, top - 0.03, stk, sw * 0.7, dash))
        g.append(v.poly([(u0 + 0.06, top - 0.03), (u0 + 0.1, bz + 0.05), (u1 - 0.1, bz + 0.05), (u1 - 0.06, top - 0.03)], 'none', stk, sw * 0.7, dash, closed=False))
        if bz > z0 + 0.05:
            for uu in (u0 + 0.04, u1 - 0.07):
                g.append(v.rect(uu, uu + 0.03, z0, bz, fill, stk, sw * 0.8, dash))
    elif key in ('fridge_2d', 'freezer_1d'):
        g.append(v.rect(u0, u1, z0 + 0.1, top, fill, stk, sw, dash))
        g.append(v.rect(u0 + 0.02, u1 - 0.02, z0, z0 + 0.1, fill, stk, sw * 0.7, dash))
        g.append(v.line(u0 + 0.06, top - 0.12, u1 - 0.06, top - 0.12, stk, sw * 0.7, dash))
    elif key.startswith('shelf') or key in ('lockers', 'chem_cabinet', 'fuel_storage'):
        g.append(v.rect(u0, u1, z0, top, fill, stk, sw, dash))
        n = 4 if key != 'lockers' else 2
        for i in range(1, n):
            zz = z0 + 0.15 + (top - z0 - 0.15) * i / n
            g.append(v.line(u0, zz, u1, zz, stk, sw * 0.7, dash))
        if key == 'fuel_storage':
            for i in range(int(w / 0.12)):
                g.append(f'<circle cx="{f(v.X(u0 + 0.08 + i * 0.12))}" cy="{f(v.Z(z0 + 0.25))}" r="{f(0.05 * v.k)}" fill="none" stroke="{stk}" stroke-width="0.15"/>')
    elif key == 'parrilla':
        fz = top - 0.32
        g.append(v.rect(u0, u1, fz, top, '#f6a04d' if mode == 'cut' else fill, stk, sw, dash))
        g.append(v.rect(u0 + 0.03, u1 - 0.03, 0.12, fz, fill, stk, sw * 0.8, dash))
        g.append(v.line(u0 + 0.03, top, u1 - 0.03, top, '#6e2508' if mode != 'ghost' else stk, 0.5, dash))
        if mode != 'ghost':
            n = max(3, int(w / 0.12))
            for i in range(n):
                uu = u0 + 0.06 + (w - 0.12) * i / max(1, n - 1)
                g.append(f'<circle cx="{f(v.X(uu))}" cy="{f(v.Z(fz + 0.07))}" r="{f(0.028 * v.k)}" fill="#c2410c"/>')
    elif key in ('cocina_4q', 'plancha', 'freidora_1', 'freidora_2'):
        g.append(v.rect(u0, u1, 0.1, top, fill, stk, sw, dash))
        g.append(v.line(u0, top - 0.08, u1, top - 0.08, stk, sw * 0.7, dash))
        for uu in (u0 + 0.04, u1 - 0.07):
            g.append(v.rect(uu, uu + 0.03, 0, 0.1, fill, stk, sw * 0.8, dash))
        if key == 'cocina_4q':
            for i in range(2):
                uu = u0 + w * (0.28 + 0.44 * i)
                g.append(v.rect(uu - 0.1, uu + 0.1, top, top + 0.04, 'none', stk, sw * 0.8, dash))
        if key.startswith('freidora'):
            g.append(v.line(u0 + w * 0.3, top, u0 + w * 0.3, top + 0.12, stk, sw * 0.8, dash))
            g.append(v.line(u0 + w * 0.3, top + 0.12, u0 + w * 0.6, top + 0.12, stk, sw * 0.8, dash))
    elif key == 'smoker':
        g.append(v.rect(u0, u1, 0.15, top, '#e46a2e' if mode == 'cut' else fill, stk, sw, dash))
        g.append(v.rect(u0 + 0.08, u1 - 0.08, 0.3, 0.62, 'none', stk, sw * 0.8, dash))
        g.append(v.rect(u0 + 0.08, u1 - 0.08, 0.75, top - 0.12, 'none', stk, sw * 0.8, dash))
        for uu in (u0 + 0.04, u1 - 0.07):
            g.append(v.rect(uu, uu + 0.03, 0, 0.15, fill, stk, sw * 0.8, dash))
    elif key == 'oven':
        g.append(v.rect(u0, u1, z0, top, fill, stk, sw, dash))
        g.append(v.rect(u0 + 0.08, u1 - 0.14, z0 + 0.1, top - 0.12, 'none', stk, sw * 0.7, dash))
    elif key in ('barra', 'pass', 'caja'):
        g.append(v.rect(u0, u1, top - 0.05, top, fill, stk, sw, dash))
        if key == 'caja':
            g.append(v.rect(u0 + 0.03, u1 - 0.03, 0.72, top - 0.05, fill, stk, sw * 0.8, dash))
            g.append(v.rect(u0 + 0.05, u1 - 0.05, 0, 0.72, 'none', stk, sw * 0.6, '0.8 0.6'))
            for uu in (u0, u1 - 0.04):
                g.append(v.rect(uu, uu + 0.04, 0, top - 0.05, fill, stk, sw, dash))
        else:
            g.append(v.rect(u0 + 0.02, u1 - 0.02, 0, top - 0.05, fill, stk, sw, dash))
            g.append(v.line(u0 + 0.02, 0.1, u1 - 0.02, 0.1, stk, sw * 0.6, dash))
    elif key == 'pos':
        g.append(v.rect(u0 + w * 0.2, u1 - w * 0.2, z0, z0 + 0.03, fill, stk, sw, dash))
        g.append(v.poly([(u0 + w * 0.35, z0 + 0.03), (u0 + w * 0.3, z0 + 0.3), (u1 - w * 0.3, z0 + 0.3), (u1 - w * 0.35, z0 + 0.03)], fill, stk, sw, dash))
    elif key == 'waste_bins':
        n = max(1, int(w / 0.35))
        for i in range(n):
            a = u0 + i * w / n
            g.append(v.rect(a + 0.03, a + w / n - 0.03, z0, top, fill, stk, sw, dash))
    elif key == 'grease_trap':
        g.append(v.rect(u0, u1, z0, top, '#fff3c2' if mode == 'cut' else fill, stk, sw, dash))
        g.append(v.line(u0, top - 0.05, u1, top - 0.05, stk, sw * 0.7, dash))
    else:
        g.append(v.rect(u0, u1, z0, top, fill, stk, sw, dash))
    return ''.join(g)


def draw_equipment(v, lay, labels=True, only_cut_labels=False):
    eq = {e['id']: e for e in lay.get('equipment', [])}
    tagged = []
    for e in lay.get('equipment', []):
        if e.get('overhead'):
            continue
        cls, d = v.classify(e['rect'])
        sp = v.span(e['rect'])
        if not cls or not sp:
            continue
        h = float(e.get('h') or 0.9)
        z0 = 0.0
        host = eq.get(e.get('stack_with')) if e.get('stack_with') else None
        if host and h > float(host.get('h') or 0):
            z0 = float(host.get('h') or 0)
        layer = 3 if cls == 'cut' else 1
        key = 1 if host and z0 > 0 else 0
        v.put(layer, (-d if d else 0) + (0.001 if key else 0), eq_shape(v, e, sp[0], sp[1], z0, h, cls))
        if cls != 'ghost':
            v.block(sp[0], sp[1], z0, h, 1.5 if cls == 'cut' else 0.6)
            v.solid(sp[0], sp[1], z0 if e.get('key') not in ('caja',) else 0.72, h, d)
        if labels and cls != 'ghost' and (cls == 'cut' or not only_cut_labels):
            tagged.append((e, sp, z0, h, cls, d))
    return tagged


def hood_back_side(h, walls):
    x0, y0, x1, y1 = h['rect']
    edges = {'x0': LineString([(x0, y0), (x0, y1)]), 'x1': LineString([(x1, y0), (x1, y1)]),
             'y0': LineString([(x0, y0), (x1, y0)]), 'y1': LineString([(x0, y1), (x1, y1)])}
    dist = {k: walls.distance(g) for k, g in edges.items()}
    # the long wall-side edge (shortest distance among edges parallel to the long axis)
    long_x = (x1 - x0) >= (y1 - y0)
    cand = ('y0', 'y1') if long_x else ('x0', 'x1')
    return min(cand, key=lambda k: dist[k])


def draw_hoods(v, L, walls):
    out_tags = []
    for h in L['hoods']:
        cls, d = v.classify(h['rect'])
        sp = v.span(h['rect'])
        if not cls or not sp:
            continue
        u0, u1 = sp
        z0, z1 = h['z0'], h['z1']
        col = C_SOLID if 'solid' in h['system'] else C_GREASE
        back = hood_back_side(h, walls)
        bx0, by0, bx1, by1 = h['rect']
        bp = {'x0': (bx0, (by0 + by1) / 2), 'x1': (bx1, (by0 + by1) / 2), 'y0': ((bx0 + bx1) / 2, by0), 'y1': ((bx0 + bx1) / 2, by1)}[back]
        ub = v.U(*bp)
        profile = abs(ub - u0) < 1e-3 or abs(ub - u1) < 1e-3     # the view runs across the hood depth
        dash = '1 0.6' if cls == 'ghost' else None
        stk = col if cls != 'ghost' else STK_GHOST
        sw = 0.55 if cls == 'cut' else (0.3 if cls == 'beyond' else 0.2)
        g = []
        if profile:
            uf = u1 if abs(ub - u0) < 1e-3 else u0
            dr = 1 if ub > uf else -1
            shell = [(uf, z0), (uf, z0 + 0.3), (uf + dr * 0.22, z1), (ub, z1), (ub, z0)]
            g.append(v.poly(shell, '#fff1e0' if cls == 'cut' else '#ffffff', 'none', 0))
            g.append(v.poly(shell, 'none', stk, sw, dash, closed=False))
            fb = (ub - dr * 0.42, z0 + FILTER_UP)
            ft = (ub - dr * 0.06, z1 - 0.12)
            g.append(v.line(fb[0], fb[1], ft[0], ft[1], stk, 0.7 if cls == 'cut' else 0.35, dash))
            g.append(v.rect(fb[0] - 0.05, fb[0] + 0.05, fb[1] - 0.05, fb[1], 'none', stk, 0.25, dash))
            h['_filter_u'] = fb[0]
        else:
            g.append(v.rect(u0, u1, z0, z1, '#fff1e0' if cls == 'cut' else ('#ffffff' if cls == 'beyond' else 'none'), stk, sw, dash))
            g.append(v.line(u0, z0 + FILTER_UP, u1, z0 + FILTER_UP, stk, 0.2, '1.2 0.8'))
            if cls != 'ghost':
                n = max(1, int((u1 - u0) / 0.5))
                for i in range(n + 1):
                    uu = u0 + (u1 - u0) * i / n
                    g.append(v.line(uu, z0 + FILTER_UP, uu, z1 - 0.12, stk, 0.15))
                if 'solid' not in h['system']:
                    for i in range(max(1, int((u1 - u0) / 0.6))):
                        uu = u0 + 0.3 + i * 0.6
                        if uu < u1 - 0.1:
                            g.append(v.poly([(uu - 0.04, z1 - 0.05), (uu + 0.04, z1 - 0.05), (uu, z1 - 0.13)], '#c1121f', 'none'))
        layer = 3 if cls == 'cut' else 1
        v.put(layer, -(d or 0) + 0.0005, ''.join(g))
        if cls != 'ghost':
            v.block(u0, u1, z0, z1, 1.5)
            out_tags.append((h, u0, u1, cls, profile))
    return out_tags


def draw_ducts(v, L, eq_by_id, ceil):
    """Vertical risers (and short transitions) from each hood / the smoker up through the slab (dashed above the ceiling)."""
    tags = []
    for dd in L['ducts']:
        col = dd['color']
        w = dd['w']
        served = next((h for h in L['hoods'] if h['id'] == dd.get('serves')), None)
        zb = served['z1'] if served else float((eq_by_id.get(dd.get('serves')) or {}).get('h') or 2.0)
        # horizontal transition(s) at the top of the hood
        pts = dd['pts']
        for a, b in zip(pts, pts[1:]):
            band = LineString([a, b]).buffer(w / 2, cap_style=2)
            r = band.bounds
            cls, dep = v.classify(r)
            sp = v.span(r)
            if cls and sp and cls != 'ghost':
                v.put(3 if cls == 'cut' else 1, -(dep or 0) + 0.0008,
                      v.rect(sp[0], sp[1], zb, zb + min(0.3, ceil - zb - 0.02), '#fff4e6' if cls == 'cut' else '#ffffff', col, 0.45 if cls == 'cut' else 0.25))
        rr = dd.get('riser_rect') or (dd['riser_at'][0] - w / 2, dd['riser_at'][1] - w / 2, dd['riser_at'][0] + w / 2, dd['riser_at'][1] + w / 2)
        cls, dep = v.classify(rr)
        sp = v.span(rr)
        if not cls or not sp or cls == 'ghost':
            continue
        u0, u1 = sp
        g = []
        z_start = zb if len(pts) < 2 else zb + 0.05
        sw = 0.45 if cls == 'cut' else 0.25
        g.append(v.rect(u0, u1, z_start, ceil, '#fff4e6' if cls == 'cut' else '#ffffff', col, sw))
        # through slab and above: dashed, inside a fire-rated enclosure (existing riser: dotted)
        g.append(v.rect(u0 - 0.05, u1 + 0.05, ceil, Z_TOP - 0.25, 'none', col, 0.2, '0.6 0.6' if dd.get('existing_riser') else '2 1'))
        g.append(v.rect(u0, u1, ceil, Z_TOP - 0.25, 'none', col, sw, '1.6 0.8'))
        g.append(f'<line x1="{f(v.X((u0 + u1) / 2))}" y1="{f(v.Z(Z_TOP - 0.25))}" x2="{f(v.X((u0 + u1) / 2))}" y2="{f(v.Z(Z_TOP - 0.02))}" '
                 f'stroke="{col}" stroke-width="0.35" marker-end="url(#{ARR.get(col, "s-arr")})"/>')
        v.put(4, 0, ''.join(g))
        v.block(u0, u1, z_start, Z_TOP, 2)
        tags.append((dd, u0, u1, cls))
    return tags


def draw_partition(v, P, ceil, mode_override=None):
    """NW-1: cut (A-A) or face (B-B, E-1, E-2) with base, cap, glass + mullions, fascia, door, niche, sign."""
    if not P:
        return
    r = P['rect']
    cls, d = v.classify(r)
    sp = v.span(r)
    if not cls or not sp:
        return
    bh, gt = P['base_h'], P['glass_top']
    g = []
    along_y = (r[3] - r[1]) >= (r[2] - r[0])
    if cls == 'cut':
        # the cut crosses the partition thickness
        u0, u1 = sp
        at = v.at
        in_door = any(_rect(o['rect'])[1] <= at <= _rect(o['rect'])[3] if along_y else _rect(o['rect'])[0] <= at <= _rect(o['rect'])[2] for o in P['doors'])
        tm = (u0 + u1) / 2
        if in_door:
            g.append(v.rect(u0, u1, DOOR_H, ceil, '#111', '#000', 0.3))
        else:
            niche = next((dc for dc in P['decor'] if dc['type'] in ('firewood_niche', 'planter') and
                          (_rect(dc['rect'])[1] <= at <= _rect(dc['rect'])[3] if along_y else _rect(dc['rect'])[0] <= at <= _rect(dc['rect'])[2])), None)
            if niche:
                zb = float(niche.get('z') if niche.get('z') is not None else 0.1)
                zt = float(niche.get('h') or bh - 0.1)
                g.append(v.rect(u0, u1, 0, zb, 'url(#s-base)', '#111', 0.45))
                g.append(v.rect(u0, u1, zt, bh, 'url(#s-base)', '#111', 0.45))
                kside = u0 if v.U(r[0], r[1]) <= v.U(r[2], r[3]) and _kitchen_side_is_low(v, P) else u1
                g.append(v.rect(kside, kside + (0.035 if kside == u0 else -0.035), zb, zt, '#111', '#000', 0.2))
                for i in range(3):
                    g.append(f'<circle cx="{f(v.X(tm))}" cy="{f(v.Z(zb + 0.1 + i * 0.13))}" r="{f(0.05 * v.k)}" fill="#8f5a2e" stroke="#4a2a10" stroke-width="0.15"/>')
            else:
                g.append(v.rect(u0, u1, 0, bh, 'url(#s-base)', '#111', 0.45))
            g.append(v.rect(u0 - 0.01, u1 + 0.01, bh, bh + 0.02, '#111', '#000', 0.2))
            g.append(v.rect(tm - 0.01, tm + 0.01, bh + 0.02, gt, GLASS, GLASS, 0.3))
            g.append(v.rect(u0, u1, gt, ceil, CORTEN, '#111', 0.45))
            sign = next((dc for dc in P['decor'] if dc['type'] == 'sign'), None)
            if sign:
                sr = _rect(sign['rect'])
                if (sr[1] <= at <= sr[3]) if along_y else (sr[0] <= at <= sr[2]):
                    ssp = v.span(sign['rect'])
                    hc, sz = float(sign.get('h') or (gt + ceil) / 2), float(sign.get('size') or 0.4)
                    if ssp:
                        g.append(v.rect(ssp[0], ssp[1], hc - sz / 2, hc + sz / 2, '#8f5a2e', '#3a2410', 0.3))
        v.put(3, 0.5, ''.join(g))
        v.block(u0, u1, 0, ceil, 3)
        v.solid(u0, u1, 0, bh, 0)
        v.solid(u0, u1, gt, ceil, 0)
        return
    # ---------------- face (elevation)
    mode = mode_override or cls
    ghost = mode == 'ghost'
    a0, a1 = sp
    ln = STK_GHOST if ghost else '#1b1b1b'
    dash = '1 0.6' if ghost else None
    doors = []
    for o in P['doors']:
        osp = v.span(o['rect'])
        if osp:
            doors.append((osp, o))
    solid = [(a0, a1)]
    for (p, q), _ in doors:
        solid = [s for seg in solid for s in ((seg[0], min(seg[1], p)), (max(seg[0], q), seg[1])) if s[1] - s[0] > 0.01]
    face_vis = _decor_visible(v)
    niches = []
    for dc in P['decor']:
        if dc['type'] in ('firewood_niche', 'planter') and face_vis(dc):
            nsp = v.span(dc['rect'])
            if nsp:
                niches.append((nsp, dc))
    # base (with niches), cap, glass panes, mullions, fascia
    for s0, s1 in solid:
        g.append(v.rect(s0, s1, 0, bh, 'url(#s-base)' if not ghost else 'none', ln, 0.3 if not ghost else 0.18, dash))
        g.append(v.rect(s0, s1, bh, bh + 0.02, '#111' if not ghost else 'none', ln, 0.2, dash))
        g.append(v.rect(s0, s1, bh + 0.02, gt, '#dff3fb' if not ghost else 'none', GLASS if not ghost else STK_GHOST, 0.3, dash,
                        extra='fill-opacity="0.45"'))
        if not ghost:
            for i in range(1, 3):
                uu = s0 + (s1 - s0) * (0.12 + 0.1 * i)
                g.append(v.line(uu, gt - 0.1 - i * 0.12, uu + 0.25, gt - 0.35 - i * 0.12, GLASS, 0.2))
    L_ = a1 - a0
    nM = max(1, round(L_ / 1.15))
    for i in range(nM + 1):
        uu = a0 + L_ * i / nM
        if any(p - 0.02 < uu < q + 0.02 for (p, q), _ in doors):
            continue
        g.append(v.rect(uu - 0.022, uu + 0.022, bh, gt, '#111' if not ghost else 'none', ln, 0.15, dash))
    for (p, q), o in doors:
        for uu in (p, q):
            g.append(v.rect(uu - 0.025, uu + 0.025, 0, gt, '#111' if not ghost else 'none', ln, 0.15, dash))
    g.append(v.rect(a0, a1, gt, ceil, CORTEN if not ghost else 'none', ln, 0.3, dash, extra='fill-opacity="0.9"'))
    if not ghost:
        nP = max(1, round(L_ / 1.2))
        for i in range(1, nP):
            uu = a0 + L_ * i / nP
            g.append(v.line(uu, gt, uu, ceil, '#6d4128', 0.2))
    # doors
    for (p, q), o in doors:
        g.append(v.rect(p, q, DOOR_H, gt, '#3a2a22' if not ghost else 'none', ln, 0.3, dash))
        lw = q - p - 0.06
        g.append(v.rect(p + 0.03, q - 0.03, 0.01, DOOR_H - 0.01, '#f2efe9' if not ghost else 'none', ln, 0.35, dash))
        if not ghost:
            vc = (p + q) / 2
            if o.get('type') == 'double_acting_door':
                g.append(v.poly([(p + 0.05, 0.05), (q - 0.05, DOOR_H / 2), (p + 0.05, DOOR_H - 0.05)], 'none', '#8a8a85', 0.2, '1.2 0.8', closed=False))
            g.append(v.rect(vc - 0.13, vc + 0.13, 1.30, 1.72, '#dff3fb', GLASS, 0.3))
            g.append(v.rect(p + 0.06, q - 0.06, 0.08, 0.32, 'none', '#8a8a85', 0.2))
            g.append(v.txt(vc, 1.05, f"{o.get('label', o['id'])}", 1.9 if v.k > 25 else 1.5, weight='800'))
            g.append(v.txt(vc, 0.9, 'vaivén · visor' if o.get('type') == 'double_acting_door' else 'puerta', 1.4 if v.k > 25 else 1.2, weight='500', fill='#444'))
        _ = lw
    # niches / planters (only on the visible face)
    for (p, q), dc in niches:
        zb = float(dc.get('z') if dc.get('z') is not None else 0.1)
        zt = float(dc.get('h') or bh - 0.1)
        g.append(v.rect(p, q, zb, zt, '#2a211c' if not ghost else 'none', ln, 0.3, dash))
        if dc['type'] == 'firewood_niche' and not ghost:
            rr = 0.055
            n_u = max(1, int((q - p - 0.06) / (2 * rr)))
            n_z = max(1, int((zt - zb - 0.04) / (2 * rr)))
            for i in range(n_u):
                for j in range(n_z):
                    cu = p + 0.03 + rr + i * (q - p - 0.06 - 2 * rr) / max(1, n_u - 1)
                    cz = zb + 0.02 + rr + j * 2 * rr
                    g.append(f'<circle cx="{f(v.X(cu))}" cy="{f(v.Z(cz))}" r="{f(rr * v.k * 0.95)}" fill="#a0673a" stroke="#4a2a10" stroke-width="0.15"/>')
            g.append(v.rect(p + 0.03, q - 0.03, zt - 0.02, zt, '#ffb347', 'none', 0))
        elif dc['type'] == 'planter' and not ghost:
            for i in range(5):
                cu = p + (q - p) * (0.15 + 0.7 * i / 4)
                g.append(f'<ellipse cx="{f(v.X(cu))}" cy="{f(v.Z(zt - 0.05))}" rx="{f(0.07 * v.k)}" ry="{f(0.16 * v.k)}" fill="#6d9b52" stroke="#2f5a22" stroke-width="0.15"/>')
    # sign
    for dc in P['decor']:
        if dc['type'] == 'sign' and face_vis(dc):
            ssp = v.span(dc['rect'])
            if not ssp:
                continue
            hc, sz = float(dc.get('h') or (gt + ceil) / 2), float(dc.get('size') or 0.4)
            cu = (ssp[0] + ssp[1]) / 2
            fs = sz * v.k / 0.72
            if not ghost:
                g.append(f'<ellipse cx="{f(v.X(cu))}" cy="{f(v.Z(hc))}" rx="{f((ssp[1] - ssp[0]) * v.k * 0.42)}" ry="{f(sz * v.k * 0.75)}" fill="#ff7a1a" fill-opacity="0.22"/>')
                g.append(text(v.X(cu), v.Z(hc) + fs * 0.36, dc.get('text', 'LAVA'), fs, weight='800', fill='#3a2410', family=DISPLAY,
                              extra=f'letter-spacing="{f(fs * 0.35)}" stroke="#1b1b1b" stroke-width="0.15"'))
    v.put(1, -(d or 0), ''.join(g))
    v.block(a0, a1, 0, bh, 1)
    v.block(a0, a1, gt, ceil, 1)
    if not ghost:
        for s0, s1 in solid:
            v.solid(s0, s1, 0, bh, d)
        v.solid(a0, a1, gt, ceil, d)
        for (p, q), _ in doors:
            v.solid(p, q, 0, gt, d)


def _kitchen_side_is_low(v, P):
    """True when the kitchen side of the partition maps to the lower u (niche back plate side)."""
    r = P['rect']
    along_y = (r[3] - r[1]) >= (r[2] - r[0])
    if along_y:
        kx = r[0] - 0.3
        return v.U(kx, 0) < v.U(r[2] + 0.3, 0)
    ky = r[1] - 0.3
    return v.U(0, ky) < v.U(0, r[3] + 0.3)


def _decor_visible(v):
    nrm = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}

    def fn(dc):
        n = nrm.get(dc.get('face'))
        return n is None or (n[0] * v.look[0] + n[1] * v.look[1]) < 0
    return fn


def draw_decor(v, lay, P, ceil):
    """Wall decor seen in elevation (posters, sconces, pendants, slat wall) — partition decor is drawn with NW-1."""
    vis = _decor_visible(v)
    pids = {id(dc) for dc in (P['decor'] if P else [])}
    for dc in lay.get('decor', []):
        if id(dc) in pids:
            continue
        cls, d = v.classify(dc['rect'])
        sp = v.span(dc['rect'])
        if not cls or not sp or cls == 'ghost':
            continue
        t = dc['type']
        u0, u1 = sp
        g = []
        if t == 'poster' and vis(dc):
            hc, sz = float(dc.get('h') or 1.7), float(dc.get('size') or 1.0)
            g.append(v.rect(u0, u1, hc - sz / 2, hc + sz / 2, '#f4efe6', '#1b1b1b', 0.3))
            g.append(v.rect(u0 + 0.04, u1 - 0.04, hc - sz / 2 + 0.04, hc + sz / 2 - 0.04, 'none', '#8a8a85', 0.15))
            lbl = str(dc.get('text', '')).split('|')[0][:10]
            g.append(v.txt((u0 + u1) / 2, hc - 0.03, lbl, 1.2 if v.k < 30 else 1.8, weight='700', fill='#555'))
        elif t == 'sconce' and vis(dc):
            z = float(dc.get('h') or 2.2)
            cu = (u0 + u1) / 2
            g.append(v.rect(cu - 0.04, cu + 0.04, z + 0.08, z + 0.2, '#111', '#111', 0.1))
            g.append(v.poly([(cu - 0.035, z + 0.1), (cu - 0.11, z - 0.04), (cu + 0.11, z - 0.04), (cu + 0.035, z + 0.1)], '#111', '#111', 0.1))
            g.append(v.poly([(cu - 0.1, z - 0.045), (cu + 0.1, z - 0.045), (cu + 0.22, z - 0.5), (cu - 0.22, z - 0.5)], '#ffb347', 'none', 0, extra='fill-opacity="0.25"'))
        elif t == 'pendant':
            z = float(dc.get('h') or 1.95)
            cu = (u0 + u1) / 2
            r_ = (u1 - u0) / 2
            g.append(v.line(cu, z + 0.15, cu, ceil, '#111', 0.2))
            g.append(f'<path d="M{f(v.X(cu - r_))},{f(v.Z(z))} A{f(r_ * v.k)},{f(0.15 * v.k)} 0 0 1 {f(v.X(cu + r_))},{f(v.Z(z))} Z" fill="#111" stroke="#111" stroke-width="0.1"/>')
            g.append(v.poly([(cu - r_ * 0.9, z), (cu + r_ * 0.9, z), (cu + r_ * 1.6, z - 0.45), (cu - r_ * 1.6, z - 0.45)], '#ffb347', 'none', 0, extra='fill-opacity="0.22"'))
        elif t == 'slat_wall' and vis(dc):
            z0, z1 = float(dc.get('z') or 1.0), float(dc.get('h') or 2.85)
            g.append(v.rect(u0, u1, z0, z1, '#ffd9a8', '#5a3a1e', 0.3, extra='fill-opacity="0.6"'))
            n = int((u1 - u0) / 0.09)
            for i in range(0, n, 2):
                uu = u0 + i * 0.09
                g.append(v.line(uu, z0, uu, z1, '#5a3a1e', 0.12))
        if g:
            v.put(1, -(d or 0) + 0.002, ''.join(g))


def draw_furniture(v, lay):
    for t in lay.get('tables', []):
        cls, d = v.classify(t['rect'])
        sp = v.span(t['rect'])
        if cls != 'beyond' or not sp:
            continue
        u0, u1 = sp
        cu = (u0 + u1) / 2
        g = [v.rect(u0, u1, TABLE_H - 0.04, TABLE_H, '#ffffff', STK_BEY, 0.22),
             v.rect(cu - 0.03, cu + 0.03, 0.02, TABLE_H - 0.04, '#ffffff', STK_BEY, 0.2),
             v.rect(cu - 0.22, cu + 0.22, 0, 0.02, '#ffffff', STK_BEY, 0.2)]
        v.put(1, -d, ''.join(g))
    for c in lay.get('chairs', []):
        cls, d = v.classify(c['rect'])
        sp = v.span(c['rect'])
        if cls != 'beyond' or not sp:
            continue
        u0, u1 = sp
        g = [v.rect(u0, u1, SEAT_H - 0.04, SEAT_H, '#ffffff', STK_BEY, 0.22),
             v.rect(u0 + 0.02, u1 - 0.02, SEAT_H, CHAIR_BACK, '#ffffff', STK_BEY, 0.22)]
        for uu in (u0 + 0.03, u1 - 0.05):
            g.append(v.rect(uu, uu + 0.02, 0, SEAT_H - 0.04, '#ffffff', STK_BEY, 0.18))
        v.put(1, -d, ''.join(g))
    for b in lay.get('banquettes', []):
        cls, d = v.classify(b['rect'])
        sp = v.span(b['rect'])
        if cls != 'beyond' or not sp:
            continue
        u0, u1 = sp
        g = [v.rect(u0, u1, 0.05, SEAT_H, '#ffffff', STK_BEY, 0.22), v.rect(u0, u1, SEAT_H, BANQ_BACK, '#f7f7f5', STK_BEY, 0.22),
             v.line(u0, SEAT_H - 0.06, u1, SEAT_H - 0.06, STK_BEY, 0.15)]
        n = int(b.get('seats') or 0)
        for i in range(1, n):
            uu = u0 + (u1 - u0) * i / n
            g.append(v.line(uu, SEAT_H + 0.02, uu, BANQ_BACK - 0.03, STK_BEY, 0.12))
        v.put(1, -d, ''.join(g))


def draw_ceiling_items(v, L, ceil, ls):
    """Luminaires, emergency lights, detectors, exit signs and make-up air diffusers (from the A-201 layout)."""
    def pt_rect(p, w=0.12):
        return (p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2)
    for tr in L['tracks']:
        r = (min(tr['p0'][0], tr['p1'][0]), tr['p0'][1] - 0.02, max(tr['p0'][0], tr['p1'][0]), tr['p0'][1] + 0.02)
        cls, d = v.classify(r)
        sp = v.span(r)
        if cls in ('beyond', 'cut') and sp:
            g = [v.rect(sp[0], sp[1], ceil - 0.05, ceil, '#111', '#111', 0.1)]
            for p in tr['spots']:
                u = v.U(*p)
                if sp[0] <= u <= sp[1]:
                    g.append(v.rect(u - 0.035, u + 0.035, ceil - 0.24, ceil - 0.05, '#111', '#111', 0.1))
                    g.append(v.poly([(u - 0.03, ceil - 0.24), (u + 0.03, ceil - 0.24), (u + 0.18, ceil - 1.0), (u - 0.18, ceil - 1.0)], '#ffb347', 'none', 0, extra='fill-opacity="0.18"'))
            v.put(1, -(d or 0) + 0.003, ''.join(g))
    for lt in L['lights']:
        t = lt['type']
        if t not in ('L-2', 'L-8'):
            continue
        p = lt['at']
        r = pt_rect(p, 0.1) if t == 'L-2' else ((p[0] - 0.6, p[1] - 0.06, p[0] + 0.6, p[1] + 0.06) if lt['along'] == 'x' else (p[0] - 0.06, p[1] - 0.6, p[0] + 0.06, p[1] + 0.6))
        cls, d = v.classify(r)
        sp = v.span(r)
        if cls not in ('beyond', 'cut') or not sp:
            continue
        if t == 'L-2':
            g = v.rect(sp[0], sp[1], ceil - 0.16, ceil, '#111', '#111', 0.1) + v.poly(
                [(sp[0], ceil - 0.16), (sp[1], ceil - 0.16), (sp[1] + 0.25, ceil - 0.9), (sp[0] - 0.25, ceil - 0.9)], '#ffb347', 'none', 0, extra='fill-opacity="0.15"')
        else:
            g = v.rect(sp[0], sp[1], ceil - 0.09, ceil, '#ffffff', '#1a55b0', 0.3) + v.line(sp[0] + 0.03, ceil - 0.09, sp[1] - 0.03, ceil - 0.09, '#9cc3f5', 0.5)
        v.put(1, -(d or 0) + 0.003, g)
    for p in L['em']:
        cls, d = v.classify(pt_rect(p, 0.3))
        sp = v.span(pt_rect(p, 0.3))
        if cls in ('beyond', 'cut') and sp:
            v.put(1, -(d or 0) + 0.003, v.rect(sp[0], sp[1], ceil - 0.1, ceil, '#fff3b0', '#3a3000', 0.25))
    for dt in L['det']:
        cls, d = v.classify(pt_rect(dt['at'], 0.12))
        sp = v.span(pt_rect(dt['at'], 0.12))
        if cls in ('beyond', 'cut') and sp:
            v.put(1, -(d or 0) + 0.003, v.rect(sp[0], sp[1], ceil - 0.05, ceil, '#ffffff', '#1b1b1b', 0.25))
    for e in L['exits']:
        rr = pt_rect(e['at'], 0.35)
        cls, d = v.classify(rr)
        sp = v.span(rr)
        if cls in ('beyond', 'cut') and sp:
            zc = DOOR_H + 0.25
            g = v.rect(sp[0], sp[1], zc - 0.1, zc + 0.1, C_EGR, '#063d1d', 0.25) + v.line((sp[0] + sp[1]) / 2, zc + 0.1, (sp[0] + sp[1]) / 2, ceil, '#555', 0.15)
            v.put(1, -(d or 0) + 0.003, g)
    for df in L['diff']:
        rr = pt_rect(df['at'], df['size'])
        cls, d = v.classify(rr)
        sp = v.span(rr)
        if cls in ('beyond', 'cut') and sp:
            g = v.rect(sp[0], sp[1], ceil - 0.06, ceil, '#eaf2fd', C_MUA, 0.3)
            cu = (sp[0] + sp[1]) / 2
            g += (f'<line x1="{f(v.X(cu))}" y1="{f(v.Z(ceil - 0.08))}" x2="{f(v.X(cu))}" y2="{f(v.Z(ceil - 0.45))}" stroke="{C_MUA}" stroke-width="0.3" marker-end="url(#s-arr-m)"/>')
            g += v.rect(sp[0] + 0.1, sp[1] - 0.1, ceil, Z_TOP - 0.3, 'none', C_MUA, 0.22, '1.2 0.8')
            v.put(1, -(d or 0) + 0.004, g)


def person(v, u, facing=1, z0=0.0, h=1.75, color='#9a9a95'):
    s = h / 1.75
    pts_body = [(u - 0.19 * s, z0 + 1.46 * s), (u + 0.19 * s, z0 + 1.46 * s), (u + 0.15 * s, z0 + 0.92 * s), (u - 0.15 * s, z0 + 0.92 * s)]
    g = [f'<circle cx="{f(v.X(u + 0.02 * facing))}" cy="{f(v.Z(z0 + 1.63 * s))}" r="{f(0.1 * s * v.k)}" fill="none" stroke="{color}" stroke-width="0.25"/>',
         v.poly(pts_body, 'none', color, 0.25),
         v.line(u - 0.08 * s, z0 + 0.92 * s, u - 0.1 * s, z0, color, 0.25), v.line(u + 0.08 * s, z0 + 0.92 * s, u + 0.1 * s, z0, color, 0.25),
         v.line(u + 0.17 * s * facing, z0 + 1.42 * s, u + 0.36 * s * facing, z0 + 1.08 * s, color, 0.25)]
    v.put(2, 0.9, ''.join(g))
    v.block(u - 0.2 * s, u + 0.2 * s, z0 + 0.9 * s, z0 + 1.75 * s, 2)


# ---- annotations
def level_mark(v, u, z, label, sub=None, color='#1b1b1b', side='left'):
    x, y = v.X(u), v.Z(z)
    dx = -1 if side == 'left' else 1
    g = [f'<polygon points="{f(x)},{f(y)} {f(x - 1.4)},{f(y - 2.2)} {f(x + 1.4)},{f(y - 2.2)}" fill="#ffffff" stroke="{color}" stroke-width="0.3"/>',
         f'<line x1="{f(x - 1.4)}" y1="{f(y - 2.2)}" x2="{f(x + dx * 10)}" y2="{f(y - 2.2)}" stroke="{color}" stroke-width="0.2"/>',
         text(x + dx * 2.0, y - 2.9, label, 1.7, anchor='start' if dx > 0 else 'end', weight='800', fill=color, family=MONO)]
    if sub:
        g.append(text(x + dx * 2.0, y + 0.1, sub, 1.35, anchor='start' if dx > 0 else 'end', weight='600', fill=color))
    return ''.join(g)


def vdim(v, u, z0, z1, off_mm, label=None, color='#1f1f1f', size=1.6, lpos=0.5):
    x = v.X(u) + off_mm
    y0, y1 = v.Z(z0), v.Z(z1)
    g = [f'<line x1="{f(v.X(u))}" y1="{f(y0)}" x2="{f(x + (0.8 if off_mm > 0 else -0.8))}" y2="{f(y0)}" stroke="{color}" stroke-width="0.15"/>',
         f'<line x1="{f(v.X(u))}" y1="{f(y1)}" x2="{f(x + (0.8 if off_mm > 0 else -0.8))}" y2="{f(y1)}" stroke="{color}" stroke-width="0.15"/>',
         f'<line x1="{f(x)}" y1="{f(min(y0, y1) - 0.8)}" x2="{f(x)}" y2="{f(max(y0, y1) + 0.8)}" stroke="{color}" stroke-width="0.18"/>']
    for yy in (y0, y1):
        g.append(f'<line x1="{f(x - 0.7)}" y1="{f(yy + 0.7)}" x2="{f(x + 0.7)}" y2="{f(yy - 0.7)}" stroke="{color}" stroke-width="0.35"/>')
    lbl = label if label is not None else f"{abs(z1 - z0):.2f}"
    ym = y0 + (y1 - y0) * lpos
    g.append(text(x - 0.7, ym, lbl, size, weight='700', fill=color, family=MONO, rot=-90,
                  extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.8"'))
    return ''.join(g)


def hdim(v, u0, u1, z, off_mm, label=None, color='#1f1f1f', size=1.6):
    y = v.Z(z) + off_mm
    x0, x1 = v.X(u0), v.X(u1)
    g = [f'<line x1="{f(x0)}" y1="{f(v.Z(z))}" x2="{f(x0)}" y2="{f(y + (0.8 if off_mm > 0 else -0.8))}" stroke="{color}" stroke-width="0.15"/>',
         f'<line x1="{f(x1)}" y1="{f(v.Z(z))}" x2="{f(x1)}" y2="{f(y + (0.8 if off_mm > 0 else -0.8))}" stroke="{color}" stroke-width="0.15"/>',
         f'<line x1="{f(min(x0, x1) - 0.8)}" y1="{f(y)}" x2="{f(max(x0, x1) + 0.8)}" y2="{f(y)}" stroke="{color}" stroke-width="0.18"/>']
    for xx in (x0, x1):
        g.append(f'<line x1="{f(xx - 0.7)}" y1="{f(y + 0.7)}" x2="{f(xx + 0.7)}" y2="{f(y - 0.7)}" stroke="{color}" stroke-width="0.35"/>')
    lbl = label if label is not None else f"{abs(u1 - u0):.2f}"
    g.append(text((x0 + x1) / 2, y - 0.7, lbl, size, weight='700', fill=color, family=MONO, extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.8"'))
    return ''.join(g)


def title_block(x, y, letter, title, sub, scale, color='#141210'):
    return (f'<circle cx="{f(x + 4)}" cy="{f(y)}" r="4" fill="#141210"/>' + text(x + 4, y + 1.3, letter, 3.6 if len(letter) < 3 else 2.6, weight='800', fill='#ffffff', family=DISPLAY)
            + text(x + 10, y - 0.4, title, 3.0, anchor='start', weight='800', fill=color, family=DISPLAY, extra='letter-spacing="0.3"')
            + text(x + 10, y + 3.2, sub, 1.7, anchor='start', weight='500', fill='#444')
            + f'<line x1="{f(x + 10)}" y1="{f(y + 0.9)}" x2="{f(x + 10 + max(tw(title, 3.0) * 0.92, 40))}" y2="{f(y + 0.9)}" stroke="#141210" stroke-width="0.35"/>'
            + text(x + 12 + max(tw(title, 3.0) * 0.92, 40), y - 0.4, scale, 2.2, anchor='start', weight='700', fill='#141210', family=MONO))


# ============================================================================================== views
def _common(v, ex, lay, L, P, walls, eqb, prem, ceil, ls, furniture=True, ceiling_items=True, slabs=True):
    line = LineString([(-50, v.at), (50, v.at)]) if v.axis == 'y' else LineString([(v.at, -50), (v.at, 50)])
    inter = prem.intersection(line)
    us = [v.U(x, y) for gg in (getattr(inter, 'geoms', None) or [inter]) if not gg.is_empty for x, y in gg.coords]
    ext = (min(us), max(us)) if us else v.u_lim
    if slabs:
        draw_slabs(v, prem, ceil, {'extent': ext, 'ivals': ct_intervals(v, L, None, line)})
    draw_walls(v, ex, lay, ceil, P)
    draw_partition(v, P, ceil)
    tagged = draw_equipment(v, lay)
    htags = draw_hoods(v, L, walls)
    dtags = draw_ducts(v, L, eqb, ceil)
    draw_decor(v, lay, P, ceil)
    if furniture:
        draw_furniture(v, lay)
    if ceiling_items:
        draw_ceiling_items(v, L, ceil, ls)
    return ext, tagged, htags, dtags


def _eq_label_text(e):
    name = e.get('plan_label') or e.get('label', '')
    return f"{e.get('tag', e['id'])} · {name}"


def _labels_equipment(v, tagged, ceil, size=1.55, max_z=None, skip=()):
    out = []
    # items with something standing on top of them (K1 under the oven K2) are labelled after it, so their tag keeps
    # clear of the upper item's leader
    def _under(t):
        return any(o is not t and o[1][0] < t[1][1] and t[1][0] < o[1][1] and o[2] >= t[3] - 0.05 for o in tagged)
    for e, sp, z0, h, cls, d in sorted(tagged, key=lambda t: (_under(t), t[1][0])):
        if e['id'] in skip or e.get('stack_with') and e.get('key') in ('pos', 'waste_bins', 'grease_trap'):
            continue
        if cls != 'cut' and v.hidden(sp[0], sp[1], z0, h, d):
            continue
        cu = (sp[0] + sp[1]) / 2
        zt = max(max_z if max_z else ceil - 0.2, min(ceil - 0.2, h + 0.22 + 0.14 * 4))
        cands = ([(cu, h + 0.22 + i * 0.14) for i in range(int(max(1, (zt - h - 0.22) / 0.14)))]
                 + [(cu + du, h + 0.3, 8.0 + 10 * abs(du)) for du in (-0.6, 0.6, -1.0, 1.0)])
        col = COL.get(e.get('cat', 'misc'), COL['misc'])[1] if cls == 'cut' else '#444'
        lines = [_eq_label_text(e)]
        if cls == 'cut':
            lines.append(f"h {h:.2f}{' TBV' if e.get('tbv') else ''}")
        out.append(v.label(lines, (cu, h), cands, col, size))
    return ''.join(out)


def _grid(cu, cz, du=(-3.0, 3.0), dz=(-0.6, 0.6), su=0.25, sz=0.1, pref=None):
    pts = []
    n_u = int(round((du[1] - du[0]) / su))
    n_z = int(round((dz[1] - dz[0]) / sz))
    for i in range(n_u + 1):
        for j in range(n_z + 1):
            pts.append((cu + du[0] + i * su, cz + dz[0] + j * sz))
    px, pz = pref or (cu, cz)
    return sorted(pts, key=lambda q: math.hypot((q[0] - px), (q[1] - pz) * 2.0))


def _duct_label(v, dd, u0, u1, ceil, lines, size=1.5):
    half = (max(tw(q, size) for q in lines) + 1.4) / 2 / v.k
    cu = (u0 + u1) / 2
    zs = ceil + SLAB_T
    cands = []
    for dz in (0.42, 0.7, 0.98):
        for side in (1, -1):
            cands.append((cu + side * ((u1 - u0) / 2 + 0.12 + half), zs + dz))
    return v.label(lines, (u1 if cands[0][0] > cu else u0, zs + 0.3), cands, dd['color'], size)


def build_AA(ex, lay, L, P, walls, eqb, prem, ceil, ox, z_top_y):
    cut = L['cuts']['A']
    bx0, by0, bx1, by1 = prem.bounds
    k = 20.0
    u_lim = (bx0 - 0.45, bx1 + 1.0)
    oz = z_top_y + Z_TOP * k
    v = View('A', 'y', cut['at'], cut['look'], u_lim, k, ox, oz, max_depth=8.0)
    v.lbox = (v.X(u_lim[0]) + 0.5, z_top_y - 2, 432.0, oz + 8)
    ls = lay.get('life_safety', {}) or {}
    ext, tagged, htags, dtags = _common(v, ex, lay, L, P, walls, eqb, prem, ceil, ls)
    # facade door (cut) + outside
    for dr in ex.get('doors', []):
        if dr.get('opening') and dr.get('kind') in ('double', 'single'):
            x0, y0, x1, y1 = dr['opening']
            r = (min(x0, x1) - 0.02, min(y0, y1), max(x0, x1) + 0.02, max(y0, y1))
            cls, _ = v.classify(r)
            sp = v.span(r)
            if cls == 'cut' and sp:
                cu = (sp[0] + sp[1]) / 2
                g = [v.rect(cu - 0.025, cu + 0.025, 0, DOOR_H, '#dff3fb', '#111', 0.45),
                     v.rect(cu - 0.06, cu + 0.06, DOOR_H, ceil, 'none', '#b00020', 0.3, '1 0.6')]
                v.put(3, 0.6, ''.join(g))
                v.put(5, 0, v.label([f"{dr['id']} · {dr.get('width', 2.0):.2f} (2 hojas)", f'h {DOOR_H:.2f} · dintel VERIFY ON SITE'],
                                    (cu, DOOR_H), [(cu + 0.55, DOOR_H + 0.45), (cu + 0.5, 1.2)], '#b00020', 1.5))
    u_out = bx1 + 0.55
    v.put(5, 0, v.txt(u_out + 0.1, 0.55, 'PASILLO ABIERTO', 1.5, weight='800', fill='#777') + v.txt(u_out + 0.1, 0.3, 'DEL C.C.', 1.5, weight='800', fill='#777'))
    v.put(5, 0, v.txt(bx0 - 0.33, 1.2, 'COLINDANCIA', 1.4, weight='800', fill='#777', rot=-90))
    v.block(bx0 - 0.45, bx0 - 0.2, 0.6, 1.8, 5)
    v.block(u_out - 0.5, u_out + 0.7, 0.2, 0.7, 5)
    # people
    parr = next((e for e in lay.get('equipment', []) if e.get('key') == 'parrilla'), None)
    if parr:
        sp = v.span(parr['rect'])
        if sp:
            person(v, sp[0] - 0.45, facing=1)
    bars = [_rect(e['rect']) for e in lay.get('equipment', []) if e.get('cat') == 'bar' and not e.get('stack_with')]
    if bars:
        person(v, max(b[2] for b in bars) + 0.45, facing=-1)
    # keep the dimension columns (parrilla front / NW-1 dining face) free of labels
    if parr and v.span(parr['rect']):
        uf = v.span(parr['rect'])[0] - 0.08
        v.block(uf - 0.22, uf + 0.02, 0, ceil, 3)
    if P:
        du = v.U(P['rect'][2], 0) + 0.12
        v.block(du, du + 0.22, 0, ceil, 3)
    # labels: hoods, ducts, equipment, partition
    lab = []
    for df in L['diff']:
        rr = (df['at'][0] - df['size'] / 2, df['at'][1] - df['size'] / 2, df['at'][0] + df['size'] / 2, df['at'][1] + df['size'] / 2)
        cls, _ = v.classify(rr)
        sp = v.span(rr)
        if cls in ('beyond', 'cut') and sp:
            cu = (sp[0] + sp[1]) / 2
            lab.append(v.label([f"{L['mua'].get('id', 'AR-1')} · aire de reposición", 'difusor + ducto desde exterior · TBE'], (cu, ceil - 0.1),
                               _grid(cu, ceil - 0.5, (-1.8, 1.8), (-0.4, 0.2)), C_MUA, 1.5))
            break
    for h, u0, u1, cls, profile in htags:
        col = C_SOLID if 'solid' in h['system'] else C_GREASE
        lines = [f"{h['id']} · {'campana combustible sólido' if 'solid' in h['system'] else 'campana línea a gas'}",
                 'arrestachispas + filtros · sistema propio' if 'solid' in h['system'] else 'supresión UL 300 + corte de gas']
        cu = (u0 + u1) / 2
        tgt = (cu, h['z1'] - 0.1)
        if cls != 'cut' and any(c2 == 'cut' and min(u1, b1) - max(u0, b0) > 0.5 * (u1 - u0) for _h2, b0, b1, c2, _p in htags):
            lines[0] += ' (detrás)'                      # hood seen behind the cut one: point at its visible edge
            tgt = (u0 + 0.02, h['z0'] + 0.12)
        lab.append(v.label(lines, tgt, _grid(cu - 1.6, (h['z0'] + ceil) / 2, (-1.4, 0.6), (-0.5, 0.35)), col, 1.55))
    for dd, u0, u1, cls in sorted(dtags, key=lambda t: t[1]):
        lab.append(_duct_label(v, dd, u0, u1, ceil, [f"{dd['id']} ↑ a cubierta · {dd['kind']}", 'ruta / remate TO BE ENGINEERED']))
    lab.append(_labels_equipment(v, tagged, ceil, max_z=1.95))
    if P:
        pr = P['rect']
        cu = (v.U(pr[0], 0) + v.U(pr[2], 0)) / 2 if v.axis == 'y' else 0
        lab.append(v.label(['NW-1 · muro bajo incombustible h 1.00', f"+ vidrio hasta +{P['glass_top']:.2f} + faja rótulo"],
                           (cu + 0.08, 1.6), [(cu + 1.6, 1.62), (cu + 1.8, 1.25), (cu + 1.6, 2.0)], '#111', 1.5))
    v.put(6, 0, ''.join(lab))
    # dims + levels
    g = []
    if parr:
        sp = v.span(parr['rect'])
        hd2 = next((h for h in L['hoods'] if 'solid' in h['system']), None)
        if sp and hd2:
            uf = sp[0] - 0.08
            fz = hd2['z0'] + FILTER_UP
            g.append(vdim(v, uf, 0, float(parr.get('h') or 0.9), -2.2, f"{float(parr.get('h') or 0.9):.2f} TBV"))
            g.append(vdim(v, uf, float(parr.get('h') or 0.9), fz, -2.2, f"{fz - float(parr.get('h') or 0.9):.2f} ≥{filter_min(lay):.2f} TBV", color=C_SOLID))
            g.append(vdim(v, uf, fz, ceil, -2.2, f"{ceil - fz:.2f}"))
    if P:
        du = v.U(P['rect'][2], 0) + 0.12
        g.append(vdim(v, du, 0, P['base_h'], 2.0))
        g.append(vdim(v, du, P['base_h'], P['glass_top'], 2.0))
        g.append(vdim(v, du, P['glass_top'], ceil, 2.0))
    ud = (ext[0] + ext[1]) / 2 + 1.0
    g.append(vdim(v, ud, 0, ceil, 0, f"{ceil:.2f} VERIFY ON SITE", color=C_RED))
    ybot = -SLAB_T
    if P:
        pu0, pu1 = sorted((v.U(P['rect'][0], 0), v.U(P['rect'][2], 0)))
        g.append(hdim(v, ext[0], pu0, ybot, 6.0, f"{pu0 - ext[0]:.2f} cocina"))
        g.append(hdim(v, pu0, pu1, ybot, 6.0, f"{pu1 - pu0:.2f}"))
        g.append(hdim(v, pu1, ext[1], ybot, 6.0, f"{ext[1] - pu1:.2f} salón"))
    g.append(hdim(v, ext[0], ext[1], ybot, 11.0, f"{ext[1] - ext[0]:.2f} interior (Y = {v.at:.2f})"))
    uL = u_lim[0]
    g.append(level_mark(v, uL + 0.15, 0, '±0.00', 'NPT existente'))
    g.append(level_mark(v, uL + 0.15, L['hood_low'], f"+{L['hood_low']:.2f}", 'borde campanas TBV', C_GREASE))
    g.append(level_mark(v, uL + 0.15, ceil, f"+{ceil:.2f}", 'cielo SUPUESTO', C_RED))
    v.put(7, 0, ''.join(g))
    return v


def build_BB(ex, lay, L, P, walls, eqb, prem, ceil, ox, z_top_y):
    cut = L['cuts']['B']
    bx0, by0, bx1, by1 = prem.bounds
    k = 20.0
    u_lim = (by0 - 0.55, by1 + 0.5)
    oz = z_top_y + Z_TOP * k
    v = View('B', 'x', cut['at'], cut['look'], u_lim, k, ox, oz, max_depth=0.85)
    v.lbox = (v.X(u_lim[0]) + 0.5, z_top_y - 2, 300.0, oz + 8)
    ls = lay.get('life_safety', {}) or {}
    ext, tagged, htags, dtags = _common(v, ex, lay, L, P, walls, eqb, prem, ceil, ls)
    v.put(5, 0, v.txt(u_lim[0] + 0.12, 1.2, 'EXTERIOR / VECINO (VERIFY)', 1.3, weight='800', fill='#777', rot=-90))
    v.put(5, 0, v.txt(u_lim[1] - 0.1, 1.2, 'PASILLO DEL EDIFICIO (VERIFY)', 1.3, weight='800', fill='#777', rot=-90))
    lab = []
    for h, u0, u1, cls, profile in htags:
        col = C_SOLID if 'solid' in h['system'] else C_GREASE
        lines = [f"{h['id']} · {'combustible sólido' if 'solid' in h['system'] else 'línea a gas'} · {u1 - u0:.2f} m",
                 'filtros + arrestachispas · sistema propio' if 'solid' in h['system'] else 'filtros + boquillas UL 300 (▼) + corte de gas']
        cu = (u0 + u1) / 2
        lab.append(v.label(lines, (cu, h['z0'] + 0.3), [(cu, h['z1'] + 0.2), (cu, h['z0'] - 0.25), (cu + 0.5, h['z0'] - 0.3)], col, 1.5))
    for dd, u0, u1, cls in sorted(dtags, key=lambda t: t[1]):
        lab.append(_duct_label(v, dd, u0, u1, ceil, [f"{dd['id']} ↑ a cubierta", ('riser existente solo si se aprueba' if dd.get('existing_riser') else 'ducto propio · cerramiento RF 1 h')]))
    lab.append(_labels_equipment(v, tagged, ceil, max_z=1.9))
    # NW-2 + P-1 tags
    for w in lay.get('new_walls', []):
        if P and w is P['wall']:
            continue
        cls, d = v.classify(w['rect'])
        sp = v.span(w['rect'])
        if cls and sp:
            cu = (sp[0] + sp[1]) / 2
            lab.append(v.label([f"{w['id']} · {w.get('short', 'panel')}", f"h {float(w.get('h') or 0):.2f} (piso-campana)"], (cu, 1.2),
                               [(cu + 0.8, 1.35), (cu + 0.9, 1.0), (cu + 0.8, 1.7)], '#111', 1.5))
    if P:
        for o in P['doors']:
            sp = v.span(o['rect'])
            if sp:
                cu = (sp[0] + sp[1]) / 2
                lab.append(v.label([f"{o.get('label', o['id'])} (al fondo, en NW-1)", f"vano {o.get('width', 0.9):.2f} · h {DOOR_H:.2f} TBV"], (cu, 1.9),
                                   [(cu, DOOR_H + 0.3), (cu + 0.5, DOOR_H + 0.35)], '#111', 1.5))
    v.put(6, 0, ''.join(lab))
    g = []
    ybot = -SLAB_T
    hot = [e for e in lay.get('equipment', []) if e.get('cat') == 'fire' and not e.get('overhead') and v.classify(e['rect'])[0] == 'cut']
    if hot:
        a = min(v.span(e['rect'])[0] for e in hot)
        b = max(v.span(e['rect'])[1] for e in hot)
        g.append(hdim(v, a, b, ybot, 6.0, f"{b - a:.2f} línea caliente"))
    wing_y = max(y for x, y in [(p[0], p[1]) for p in lay['zones'][0]['poly']]) if lay.get('zones') else None
    zB = next((z for z in lay.get('zones', []) if z['id'] == 'B'), None)
    if zB:
        yb = max(p[1] for p in zB['poly'])
        g.append(hdim(v, ext[0], v.U(0, yb) if v.axis == 'x' else yb, ybot, 11.0, f"{yb - ext[0]:.2f} franja cocina"))
        g.append(hdim(v, yb, ext[1], ybot, 11.0, f"{ext[1] - yb:.2f} ala de servicio"))
    _ = wing_y
    hd = L['hoods'][0] if L['hoods'] else None
    if hd:
        sp = v.span(hd['rect'])
        if sp:
            g.append(vdim(v, sp[0] - 0.05, 0, hd['z0'], -2.2, f"{hd['z0']:.2f} TBV"))
            g.append(vdim(v, sp[0] - 0.05, hd['z0'], hd['z1'], -2.2))
            g.append(vdim(v, sp[0] - 0.05, hd['z1'], ceil, -2.2))
    g.append(vdim(v, ext[1] - 1.2, 0, ceil, 0, f"{ceil:.2f} VERIFY ON SITE", color=C_RED))
    uL = u_lim[0]
    g.append(level_mark(v, uL + 0.1, 0, '±0.00', 'NPT existente'))
    g.append(level_mark(v, uL + 0.1, L['hood_low'], f"+{L['hood_low']:.2f}", 'borde campanas TBV', C_GREASE))
    g.append(level_mark(v, uL + 0.1, ceil, f"+{ceil:.2f}", 'cielo SUPUESTO', C_RED))
    v.put(7, 0, ''.join(g))
    return v


def build_E1(ex, lay, L, P, walls, eqb, prem, ceil, ox, z_top_y):
    if not P:
        return None
    pr = P['rect']
    bar = [_rect(e['rect']) for e in lay.get('equipment', []) if e.get('cat') == 'bar' and not e.get('stack_with')]
    at = min([b[0] for b in bar] + [pr[2] + 1.0]) - 0.06
    k = 40.0
    u_lim = (-(pr[3] + 0.32), -(pr[1] - 0.3))
    ztop = ceil + SLAB_T + 0.05
    oz = z_top_y + ztop * k
    v = View('E1', 'x', at, (-1, 0), u_lim, k, ox, oz, max_depth=8.0, ghost_depth=(at - pr[2]) + 0.05, z_lim=(-0.08, ztop))
    v.lbox = (v.X(u_lim[0]), v.Z(ztop), v.X(u_lim[1]), v.Z(-0.08))
    ls = lay.get('life_safety', {}) or {}
    g0 = [v.rect(u_lim[0], u_lim[1], -0.08, 0, 'url(#s-conc)', '#555', 0.3), v.line(u_lim[0], 0, u_lim[1], 0, '#111', 0.45),
          v.rect(u_lim[0], u_lim[1], ceil, ztop - 0.02, 'url(#s-conc)', '#555', 0.3), v.rect(u_lim[0], u_lim[1], ceil - 0.03, ceil, '#1b1917', '#1b1917', 0.1)]
    v.put(0, 0, ''.join(g0))
    draw_walls(v, ex, lay, ceil, P)
    draw_partition(v, P, ceil)
    tagged = draw_equipment(v, lay, labels=True, only_cut_labels=False)
    draw_hoods(v, L, walls)
    draw_decor(v, lay, P, ceil)
    draw_ceiling_items(v, L, ceil, ls)
    lab = []
    a0, a1 = v.span(pr)
    face_vis = _decor_visible(v)
    for dc in P['decor']:
        if not face_vis(dc):
            continue
        sp = v.span(dc['rect'])
        if not sp:
            continue
        cu = (sp[0] + sp[1]) / 2
        if dc['type'] == 'sign':
            lab.append(v.label([f"L-6 · rótulo {dc.get('text', 'LAVA')} retroiluminado", f"eje +{float(dc.get('h')):.2f} · letras {float(dc.get('size') or 0):.2f}"],
                               (sp[1] - 0.2, float(dc.get('h'))), [(sp[1] + 0.5, ceil - 0.2), (sp[0] - 0.5, ceil - 0.2)], '#8f4500', 1.6))
        elif dc['type'] == 'firewood_niche':
            lab.append(v.label(['Relieve de leños (decorativo) + LED L-5',
                                f"z {float(dc.get('z') or 0):.2f}–{float(dc.get('h') or 0):.2f} · {dc.get('material', 'incombustible')}, sin hueco"],
                               (cu, float(dc.get('h') or 0.8) - 0.1), [(cu, 1.35), (cu + 0.4, 1.35), (cu - 0.4, 1.35)], '#5a3a1e', 1.6))
        elif dc['type'] == 'planter':
            lab.append(v.label(['Jardinera integrada'], (cu, float(dc.get('h') or 1.0)), [(cu, 1.35)], '#2f5a22', 1.6))
    ub = a1 - 0.35
    lab.append(v.label([f"Base incombustible h {P['base_h']:.2f} · MU-05 (A-106)", 'micro-cemento gris oscuro · spec. térmica TO BE ENGINEERED'], (ub, 0.5),
                       [(a1 - 1.05, 0.55), (a1 - 1.05, 0.35), (a1 - 1.05, 0.75)], '#5a3a1e', 1.6))
    lab.append(v.label(['Vidrio vitrocerámico / cortafuego frente a la', 'parrilla; resto templado laminado · TO BE ENGINEERED'], (a1 - 0.6, 1.8),
                       [(a1 - 0.9, 1.55), (a1 - 0.9, 2.0), (a0 + 1.2, 1.55)], '#1a6d96', 1.6))
    lab.append(v.label(['Campanas HD-1 / HD-2 tras el vidrio', f"borde inferior +{L['hood_low']:.2f} TBV"], ((a0 + a1) / 2 + 0.6, L['hood_low'] + 0.2),
                       [((a0 + a1) / 2 + 0.2, L['hood_low'] - 0.45), ((a0 + a1) / 2 + 0.9, L['hood_low'] - 0.35)], '#8a6a52', 1.5))
    lab.append(_labels_equipment(v, [t for t in tagged if t[4] == 'beyond'], ceil, size=1.5, max_z=1.9))
    v.put(6, 0, ''.join(lab))
    g = []
    ybot = -0.08
    for o in P['doors']:
        sp = v.span(o['rect'])
        if sp:
            g.append(hdim(v, sp[0], sp[1], ybot, 5.0, f"{sp[1] - sp[0]:.2f} vano"))
            g.append(vdim(v, sp[0] + 0.02, 0, DOOR_H, 2.4, f"{DOOR_H:.2f} TBV"))
    for dc in P['decor']:
        if dc['type'] in ('firewood_niche', 'planter') and face_vis(dc):
            sp = v.span(dc['rect'])
            if sp:
                g.append(hdim(v, sp[0], sp[1], ybot, 5.0))
    g.append(hdim(v, a0, a1, ybot, 10.0, f"{a1 - a0:.2f} división NW-1"))
    g.append(vdim(v, a1, 0, P['base_h'], 3.5))
    g.append(vdim(v, a1, P['base_h'], P['glass_top'], 3.5))
    g.append(vdim(v, a1, P['glass_top'], ceil, 3.5))
    g.append(vdim(v, a1, 0, ceil, 8.0, f"{ceil:.2f} VERIFY ON SITE", color=C_RED))
    g.append(level_mark(v, u_lim[0] + 0.05, 0, '±0.00', None))
    g.append(level_mark(v, u_lim[0] + 0.05, ceil, f"+{ceil:.2f}", 'SUPUESTO', C_RED))
    v.put(7, 0, ''.join(g))
    return v


def build_E2(ex, lay, L, P, walls, eqb, prem, ceil, ox, z_top_y):
    bar_items = [e for e in lay.get('equipment', []) if e.get('cat') == 'bar']
    if not bar_items:
        return None
    rects = [_rect(e['rect']) for e in bar_items]
    at = max(r[2] for r in rects) + 0.12
    ys0, ys1 = min(r[1] for r in rects), max(r[3] for r in rects)
    k = 40.0
    u_lim = (-(ys1 + 0.42), -(ys0 - 0.35))
    ztop = ceil + SLAB_T + 0.05
    oz = z_top_y + ztop * k
    ghost = (at - P['rect'][2]) + 0.05 if P else None
    v = View('E2', 'x', at, (-1, 0), u_lim, k, ox, oz, max_depth=8.0, ghost_depth=ghost, z_lim=(-0.08, ztop))
    v.lbox = (v.X(u_lim[0]), v.Z(ztop), v.X(u_lim[1]), v.Z(-0.08))
    ls = lay.get('life_safety', {}) or {}
    g0 = [v.rect(u_lim[0], u_lim[1], -0.08, 0, 'url(#s-conc)', '#555', 0.3), v.line(u_lim[0], 0, u_lim[1], 0, '#111', 0.45),
          v.rect(u_lim[0], u_lim[1], ceil, ztop - 0.02, 'url(#s-conc)', '#555', 0.3), v.rect(u_lim[0], u_lim[1], ceil - 0.03, ceil, '#1b1917', '#1b1917', 0.1)]
    v.put(0, 0, ''.join(g0))
    draw_walls(v, ex, lay, ceil, P)
    draw_partition(v, P, ceil)
    tagged = draw_equipment(v, lay)
    draw_hoods(v, L, walls)
    draw_decor(v, lay, P, ceil)
    draw_ceiling_items(v, L, ceil, ls)
    lab = []
    order = sorted([t for t in tagged if t[0].get('cat') == 'bar' and not t[0].get('stack_with')], key=lambda t: t[1][0])
    for e, sp, z0, h, cls, d in order:
        cu = (sp[0] + sp[1]) / 2
        lines = [f"{e.get('tag', e['id'])} · {e.get('label', '')}", f"h {h:.2f} · tramo {sp[1] - sp[0]:.2f}"]
        col = '#553688'
        if e.get('key') == 'caja':
            lines = [f"{e.get('tag', e['id'])} · caja accesible h {h:.2f}", f"tramo {sp[1] - sp[0]:.2f} (Ley 7600 · art. 148)"]
            col = '#0b4f8a'
            lab.append(v.label(['espacio libre inferior', '(medidas a validar)'], None, [(cu, 0.4)], col, 1.45, leader=False))
        lab.append(v.label(lines, (cu, h), [(cu, h + 0.42), (cu, h + 0.62), (cu, h + 0.82)], col, 1.55))
    for e, sp, z0, h, cls, d in tagged:
        if e.get('key') == 'pos':
            cu = (sp[0] + sp[1]) / 2
            lab.append(v.label([f"{e.get('tag', e['id'])} · POS"], (cu, h + 0.25), [(cu - 0.5, h + 0.3), (cu + 0.55, h + 0.3)], '#553688', 1.5))
    pend = [dc for dc in lay.get('decor', []) if dc['type'] == 'pendant' and v.span(dc['rect']) and v.classify(dc['rect'])[0] == 'beyond']
    if pend:
        sp = v.span(pend[0]['rect'])
        cu = (sp[0] + sp[1]) / 2
        lab.append(v.label([f"L-3 colgantes · borde inf. h {float(pend[0].get('h') or 0):.2f}"], (cu, float(pend[0].get('h') or 1.95) + 0.1),
                           [(cu - 0.2, 2.45), (cu + 0.2, 2.45)], '#333', 1.55))
    pas = next((t for t in tagged if t[0].get('key') == 'pass'), None)
    if pas:
        e, sp, z0, h, cls, d = pas
        cu = (sp[0] + sp[1]) / 2
        v.put(4, 0, v.rect(sp[0] + 0.05, sp[1] - 0.05, h + 0.5, h + 0.56, '#8f4500', '#5a2a00', 0.2)
              + ''.join(v.line(uu, h + 0.5, uu, h + 0.62, '#5a2a00', 0.25) for uu in (sp[0] + 0.1, sp[1] - 0.1)))
        lab.append(v.label(['L-7 lámparas de calor del pase', 'altura según proveedor (TBV)'], (cu, h + 0.53), [(cu, h + 1.0), (cu + 0.3, h + 1.1)], '#8f4500', 1.5))
    if P:
        a0, a1 = v.span(P['rect'])
        lab.append(v.label(['NW-1 al fondo (vidrio + faja con rótulo)'], (a0 + 0.3, 2.3), [(a0 + 0.9, 2.2), (a0 + 0.9, 1.85)], '#555', 1.5))
    v.put(6, 0, ''.join(lab))
    g = []
    ybot = -0.08
    for e, sp, z0, h, cls, d in order:
        g.append(hdim(v, sp[0], sp[1], ybot, 5.0))
    if order:
        a = min(t[1][0] for t in order)
        b = max(t[1][1] for t in order)
        g.append(hdim(v, a, b, ybot, 10.0, f"{b - a:.2f} barra + caja + pase"))
        e_c = next((t for t in order if t[0].get('key') == 'caja'), None)
        e_b = next((t for t in order if t[0].get('key') == 'barra'), None)
        if e_b:
            g.append(vdim(v, e_b[1][1], 0, e_b[3], 2.5, None))
        if e_c:
            g.append(vdim(v, e_c[1][0], 0, e_c[3], -2.5, None, color='#0b4f8a'))
    g.append(vdim(v, u_lim[1] - 0.12, 0, ceil, 0, f"{ceil:.2f} VERIFY ON SITE", color=C_RED))
    g.append(level_mark(v, u_lim[0] + 0.05, 0, '±0.00', None))
    g.append(level_mark(v, u_lim[0] + 0.05, ceil, f"+{ceil:.2f}", 'SUPUESTO', C_RED))
    v.put(7, 0, ''.join(g))
    return v


# ============================================================================================== key plan
def key_plan(ex, lay, L, P, x0, y0, k=20.0 / 3.0):
    prem = premises(ex)
    bx0, by0, bx1, by1 = prem.bounds
    ox, oy = x0 + 0.9 * k - bx0 * k, y0 + 0.9 * k - by0 * k

    def X(x):
        return ox + x * k

    def Y(y):
        return oy + y * k

    def poly(g, fill, stroke, sw=0.2, extra=''):
        out = []
        for gg in (getattr(g, 'geoms', None) or [g]):
            if gg.is_empty or gg.geom_type != 'Polygon':
                continue
            out.append(f'<polygon points="{" ".join(f"{f(X(a))},{f(Y(b))}" for a, b in gg.exterior.coords)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')
        return ''.join(out)

    g = ['<g id="key-plan">', poly(prem, '#fbfaf8', '#999', 0.2)]
    for z in lay.get('zones', []):
        g.append(poly(Polygon(z['poly']).intersection(prem), z.get('color', '#999'), 'none', 0, 'fill-opacity="0.10"'))
    for e in lay.get('equipment', []):
        if e.get('overhead'):
            g.append(poly(R(e['rect']), 'none', C_GREASE, 0.25, 'stroke-dasharray="0.8 0.5"'))
        elif not e.get('stack_with'):
            g.append(poly(R(e['rect']), '#e9e9e6', '#b5b5b0', 0.12))
    for w, geom in standing_existing_walls(ex, lay):
        g.append(poly(geom, '#6e6e6a', 'none', 0))
    for c in ex.get('columns', []):
        g.append(poly(R(c['rect']), '#4a4a47', 'none', 0))
    for w in lay.get('new_walls', []):
        g.append(poly(R(w['rect']), '#111', 'none', 0))
    dd = 'stroke="#b00020" stroke-width="0.4" stroke-dasharray="2.4 0.7 0.5 0.7"'
    ca, cb = L['cuts']['A']['at'], L['cuts']['B']['at']
    g.append(f'<line x1="{f(X(bx0 - 0.6))}" y1="{f(Y(ca))}" x2="{f(X(bx1 + 0.6))}" y2="{f(Y(ca))}" {dd}/>')
    g.append(f'<line x1="{f(X(cb))}" y1="{f(Y(by0 - 0.6))}" x2="{f(X(cb))}" y2="{f(Y(by1 + 0.6))}" {dd}/>')

    def mark(x, y, lab, ang):
        a = math.radians(ang)
        tx, ty = x + math.cos(a) * 3.4, y + math.sin(a) * 3.4
        px, py = -math.sin(a), math.cos(a)
        tri = [(tx, ty), (x + math.cos(a) * 1.6 + px * 1.6, y + math.sin(a) * 1.6 + py * 1.6), (x + math.cos(a) * 1.6 - px * 1.6, y + math.sin(a) * 1.6 - py * 1.6)]
        return (f'<polygon points="{" ".join(f"{f(u)},{f(w)}" for u, w in tri)}" fill="#b00020"/>'
                f'<circle cx="{f(x)}" cy="{f(y)}" r="2.2" fill="#ffffff" stroke="#b00020" stroke-width="0.35"/>'
                + text(x, y + 0.75, lab, 2.0 if len(lab) < 3 else 1.5, weight='800', fill='#b00020'))
    g.append(mark(X(bx0 - 0.6) - 2.2, Y(ca), 'A', -90))
    g.append(mark(X(bx1 + 0.6) + 2.2, Y(ca), 'A', -90))
    g.append(mark(X(cb), Y(by0 - 0.6) - 2.2, 'B', 0))
    g.append(mark(X(cb), Y(by1 + 0.6) + 2.2, 'B', 0))
    if P:
        pr = P['rect']
        g.append(mark(X(pr[2] + 1.6), Y(min(4.2, (pr[1] + pr[3]) / 2 + 1.2)), 'E-1', 180))
        bar = [_rect(e['rect']) for e in lay.get('equipment', []) if e.get('cat') == 'bar' and not e.get('stack_with')]
        if bar:
            g.append(mark(X(max(b[2] for b in bar) + 0.9), Y((min(b[1] for b in bar) + max(b[3] for b in bar)) / 2), 'E-2', 180))
    g.append('</g>')
    return ''.join(g), (X(bx0 - 0.9), Y(by0 - 0.9), X(bx1 + 0.9), Y(by1 + 0.9))


# ============================================================================================== sheet
def build_sheet(ex, lay, val):
    L = ceiling_layout(ex, lay, val)
    ceil = L['ceil']
    prem = premises(ex)
    walls = walls_union(ex, lay)
    P = partition_info(ex, lay, ceil)
    eqb = {e['id']: e for e in lay.get('equipment', [])}
    s = Sheet(ex, lay, val, 'A301')
    s.add(DEFS)
    s.frame_and_titleblock('A-301 · Cortes y elevaciones', 'Corte A-A (parrilla) · Corte B-B (línea caliente) · E-1 división · E-2 barra y caja', 'A-301',
                           scalebar=False, north=False, scale_note='Cortes 1:50 · elevaciones 1:25 en A2 · cotas en metros')
    vA = build_AA(ex, lay, L, P, walls, eqb, prem, ceil, ox=34.0, z_top_y=15.0)
    s.add(f'<g id="corte-AA">{vA.render("clip-aa")}</g>')
    s.add(title_block(34, 124.5, 'A', 'CORTE A-A · LONGITUDINAL', f"Por la parrilla (Y = {L['cuts']['A']['at']:.2f}) mirando al muro norte: acceso → salón → NW-1 → parrilla / HD-2 → BBQ",
                      '1:50'))
    vB = build_BB(ex, lay, L, P, walls, eqb, prem, ceil, ox=34.0, z_top_y=137.0)
    s.add(f'<g id="corte-BB">{vB.render("clip-bb")}</g>')
    s.add(title_block(34, 246.5, 'B', 'CORTE B-B · TRANSVERSAL', f"Por la línea caliente (X = {L['cuts']['B']['at']:.2f}) mirando al salón: muro norte → freidoras → plancha → cocina → parrilla → NW-2 → ala",
                      '1:50'))
    kp, kb = key_plan(ex, lay, L, P, 306.0, 139.0)
    s.add(kp)
    s.add(title_block(306, 246.5, 'KP', 'PLANTA CLAVE', 'Líneas de corte (A, B) y elevaciones (E-1, E-2)', '1:150'))
    vE1 = build_E1(ex, lay, L, P, walls, eqb, prem, ceil, ox=34.0, z_top_y=258.0)
    if vE1:
        s.add(f'<g id="elev-E1">{vE1.render("clip-e1")}</g>')
        s.add(title_block(34, 408.0, 'E1', 'ELEVACIÓN E-1 · DIVISIÓN COCINA / SALÓN', 'Vista desde el salón: muro bajo + vidrio + faja con rótulo + relieve de leños + puerta P-1', '1:25'))
    vE2 = build_E2(ex, lay, L, P, walls, eqb, prem, ceil, ox=300.0, z_top_y=258.0)
    if vE2:
        s.add(f'<g id="elev-E2">{vE2.render("clip-e2")}</g>')
        s.add(title_block(300, 408.0, 'E2', 'ELEVACIÓN E-2 · BARRA + CAJA', 'Vista desde el salón: barra 1.05 · caja accesible 0.80 · pase', '1:25'))
    side_panel(s, L, lay, P, eqb, ceil)
    return s.render()


def side_panel(s, L, lay, P, eqb, ceil):
    def sw(fill, stroke, dash=None, sw_=0.35):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        return lambda x, y: f'<rect x="{x}" y="{y}" width="10" height="3.4" fill="{fill}" stroke="{stroke}" stroke-width="{sw_}"{d}/>'

    def swl(color, dash=None, w=0.5):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        return lambda x, y: f'<line x1="{x}" y1="{y + 1.7}" x2="{x + 10}" y2="{y + 1.7}" stroke="{color}" stroke-width="{w}"{d}/>'
    legend = [
        (sw('url(#s-hatch-ex)', '#222'), 'EXISTING WALL cortado'),
        (sw('url(#s-base)', '#111'), 'NW-1 base incombustible (cortada)'),
        (sw('#dff3fb', GLASS), 'Vidrio (NW-1)'),
        (sw(COL['fire'][0], COL['fire'][1]), 'Equipo cortado (color por categoría)'),
        (sw('#ffffff', STK_BEY, sw_=0.22), 'Equipo / muro en vista (más allá)'),
        (sw('none', STK_GHOST, '1 0.6', 0.3), 'Tras el vidrio / oculto (fantasma)'),
        (sw('#fff1e0', C_GREASE), 'Campana HD (perfil) + filtros'),
        (swl(C_SOLID, '1.6 0.8', 0.5), 'Ducto sobre el cielo (esquemático)'),
        (sw('url(#s-conc)', '#555'), 'Losa / piso existente (espesor VERIFY)'),
        (sw('#1b1917', '#1b1917'), 'CT-1 estructura negro mate'),
        (sw('url(#s-ct2)', '#c2410c'), 'CT-2 / CT-3 cielo liso lavable'),
        (swl('#9a9a95', None, 0.3), 'Figura humana 1.75 m (escala)'),
    ]
    hl = L['hood_low']
    hd2 = next((h for h in L['hoods'] if 'solid' in h['system']), None)
    parr = next((e for e in lay.get('equipment', []) if e.get('key') == 'parrilla'), None)
    rows = [('Cielo / fondo de estructura', f"+{ceil:.2f} SUPUESTO"), ('Borde inferior campanas (= NW-2)', f"+{hl:.2f} TBV")]
    if L['hoods']:
        rows.append(('Parte superior de campanas', f"+{L['hoods'][0]['z1']:.2f}"))
    if parr and hd2:
        ph = float(parr.get('h') or 0.9)
        rows.append((f'Filtros HD-2 sobre la parrilla (≥{filter_min(lay):.2f})', f"{hd2['z0'] + FILTER_UP - ph:.2f} TBV"))
        rows.append(('Parrilla: superficie de cocción', f"{ph:.2f} TBV"))
    if P:
        rows.append(('NW-1 base / vidrio / faja', f"{P['base_h']:.2f} / {P['glass_top']:.2f} / {ceil:.2f}"))
        for o in P['doors']:
            rows.append((f"Puerta {o.get('label', o['id'])} (vano × alto)", f"{o.get('width', 0.9):.2f} × {DOOR_H:.2f} TBV"))
    for key in ('barra', 'caja', 'pass', 'smoker'):
        e = next((q for q in lay.get('equipment', []) if q.get('key') == key), None)
        if e:
            rows.append((f"{e.get('tag', e['id'])} · {e.get('label', '')}"[:40], f"{float(e.get('h') or 0):.2f}{' TBV' if e.get('tbv') else ''}"))
    for t, nm in (('pendant', 'Colgantes L-3 (borde inferior)'), ('sconce', 'Apliques L-4'), ('sign', 'Rótulo LAVA (eje)')):
        dc = next((d for d in lay.get('decor', []) if d['type'] == t), None)
        if dc:
            rows.append((nm, f"{float(dc.get('h') or 0):.2f}"))
    rows.append(('Altura libre mínima (INVU, verificar)', '2.40'))
    notes = ['!ANTEPROYECTO: alturas y rutas a validar por el profesional',
             '!responsable (CFIA) y los ingenieros mecánico / electricista.',
             'Cortes y elevaciones en coordenadas propias de dibujo; posiciones',
             'y alturas del modelo del anteproyecto (v3, mismas que A-101).',
             'Mobiliario (mesa 0.75, asiento 0.45) y puertas 2.10: referenciales.',
             '!TBV = DIMENSION TO VERIFY (equipo sin ficha técnica / sin levantamiento).',
             f'Campanas: borde +{hl:.2f} = panel NW-2 piso-campana; filtros de',
             f'HD-2 ≥{filter_min(lay):.2f} m sobre la superficie de cocción (NFPA 96 cap. 14',
             '— TBV; tabla general 1.07 m carbón: confirmar edición adoptada).',
             'Ductos de grasa: acero 16 MSG soldado, sin bolsas, registros de',
             'limpieza y cerramiento RF 1 h al atravesar losa (NFPA 96 cap. 7).',
             'Remates en cubierta: NFPA 96 §7.8 + INVU (art. chimeneas, por',
             'verificar); requieren aprobación del condominio.',
             '!EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED',
             '!SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED',
             'Caja C4: tramo 0.90 a h 0.80 con espacio libre inferior',
             '(Ley 7600, Reglamento art. 148 — medidas a validar).']
    verify = ['Altura real a fondo de losa / vigas y espesor de losa: la cota',
              f'+{ceil:.2f} es un SUPUESTO del levantamiento — VERIFY ON SITE.',
              'Dintel / vidrio fijo sobre D-ENT y altura de puertas.',
              'Número de pisos y ruta vertical real de EXT-1 / EXT-2 / EXT-3.']
    s.side_panel([('h', 'Leyenda'), ('legend', legend), ('h', 'Alturas clave (a validar)'), ('rows', rows),
                  ('h', 'Notas'), ('para', notes), ('h', 'VERIFY ON SITE'), ('para', verify)])


def sheets(ex, lay, val):
    return [{'id': 'A301', 'file': 'lava_A301_cortes.svg', 'title': 'Cortes y elevaciones', 'order': 301, 'svg': build_sheet(ex, lay, val)}]
