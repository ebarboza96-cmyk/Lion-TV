"""A-106 · Acabados y puertas — ANTEPROYECTO, a validar por el profesional responsable.

Finishes plan derived from data/existing.json + data/layout.json:
  * floor finish (PI-xx) per zone polygon, with tile-grid patterns; incombustible floor/wall protection around the
    solid-fuel equipment (keys parrilla / smoker);
  * wall finish (MU-xx) computed per wall face: each room boundary (zone ∩ premises − walls) is sampled every 5 cm, the
    point just outside the face is tested against the solid walls; the face gets MU-02 near fire equipment, MU-03 where
    the slat-wall decor is, MU-04 on the north face of the dining room, MU-05 on the kitchen/dining partition, etc.;
  * skirting (ZO-xx) and ceiling (CI-xx) per zone, proposed floor drains (FD-x, same as M-101);
  * door / window schedule (D-ENT, P-1, PS-1, existing opening, NW-1 glazing, NW-2 panel, storefront and south window).
Codes: PI floors, MU walls, ZO skirting / media caña, CI ceilings ("P-1" is a DOOR, never a finish code).
"""
import math
import re

from shapely.geometry import Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from lavageo import R, door_swing_poly, item_lists, new_openings_geom, premises, standing_existing_walls
from plan_svg import COL, LEGEND_WALLS, MONO, S, VIEW, Sheet, f, poly_el, sx, sy, text, tw

KITCHEN = ('A', 'B', 'E', 'W')
PUBLIC = ('C', 'D')
ZONE_FIN = {   # design decision per zone (zone ids from layout.json)
    'B': {'PI': 'PI-01', 'ZO': 'ZO-01', 'CI': 'CI-01'},
    'E': {'PI': 'PI-01', 'ZO': 'ZO-01', 'CI': 'CI-01'},
    'A': {'PI': 'PI-01', 'ZO': 'ZO-01', 'CI': 'CI-01'},
    'W': {'PI': 'PI-02', 'ZO': 'ZO-02', 'CI': 'CI-01'},
    'C': {'PI': 'PI-03', 'ZO': 'ZO-03', 'CI': 'CI-02'},
    'D': {'PI': 'PI-03', 'ZO': 'ZO-03', 'CI': 'CI-02'},
}
FLOOR = {'PI-01': ('#e7eef6', '#b9cadd', (0.30, 0.60)), 'PI-02': ('#d3eeec', '#9fd0cc', None), 'PI-03': ('#efeae2', '#cfc6b6', (1.20, 0.60))}
WALLC = {'MU-01': '#1f8fb8', 'MU-02': '#e0520b', 'MU-03': '#8a5a2b', 'MU-04': '#4d6273', 'MU-05': '#2b2b2b', 'MU-06': '#c6b08a'}
BAND = 0.075          # wall-finish band width (m)
FIRE_MARGIN = 0.45    # incombustible protection beyond the equipment (preliminary)
ACC, WARN, BAD = '#0b4f8a', '#a35c00', '#b00020'
LEAF_LOSS = 0.06


def _specs(ex):
    h = float((ex.get('ceiling') or {}).get('height_assumed', 3.0))
    return [
        ('PI-01', 'PISO', 'Porcelanato técnico antideslizante 30×60 color claro, junta epóxica ≤ 3 mm; clase de resbalamiento para zona '
                          'húmeda (R11 o superior — verificar ficha); pendiente 1–2 % a sifones. Bajo parrilla y smoker: sobre losa, incombustible.'),
        ('PI-02', 'PISO', 'Uretano-cemento antideslizante continuo (e ≥ 6 mm), sin juntas, resistente a choque térmico y a químicos de '
                          'limpieza; pendiente 1–2 % a sifones.'),
        ('PI-03', 'PISO', 'Porcelanato rectificado gran formato 60×120 aspecto "concreto pulido", gris claro cálido, mate antideslizante '
                          '(verificar ficha), junta 2 mm a tono; sin cambios de nivel (Ley 7600).'),
        ('ZO-01', 'ZÓCALO', 'Media caña sanitaria continua piso–muro y piso–base de equipo fijo (pieza curva de porcelanato o mortero '
                            'epóxico; radio ≥ 3 cm — verificar).'),
        ('ZO-02', 'ZÓCALO', 'Media caña integral de uretano-cemento h 0.15, monolítica con PI-02.'),
        ('ZO-03', 'ZÓCALO', 'Rodapié de porcelanato PI-03 h 0.08, canto pulido, junta a tono.'),
        ('MU-01', 'MURO', 'Revestimiento sanitario liso color claro (porcelanato / cerámica esmaltada o panel FRP-PVC sanitario) de piso a '
                          'h ≥ 2.10, recomendado hasta cielo; encima pintura epóxica lavable clara; juntas selladas, esquineros sanitarios.'),
        ('MU-02', 'MURO', f'Protección incombustible tras equipos de fuego: acero inoxidable sobre placa cementicia con cámara de aire, piso a '
                          f'campana, equipo + {FIRE_MARGIN:.2f} a cada lado (preliminar); según listado / NFPA 96 — TO BE ENGINEERED.'),
        ('MU-03', 'MURO', 'Muro de listones de madera retroiluminado (LED lineal oculto), muro sur del salón; madera con retardante de '
                          'llama; clase de acabado interior según NFPA 101 cap. 10 / RNPCI (verificar).'),
        ('MU-04', 'MURO', 'Aspecto concreto visto con textura de encofrado de tabla (micro-cemento o panel cementicio texturizado), '
                          'sellador mate: muro norte de salón y barra.'),
        ('MU-05', 'MURO', 'Base de NW-1 cara salón (h 1.00): placa cementicia incombustible con micro-cemento gris oscuro; rótulo LAVA '
                          'y relieve decorativo de leños incombustible (sin hueco) según decoración.'),
        ('MU-06', 'MURO', 'Pintura acrílica lavable mate gris cálido claro: resto de paramentos de salón y barra (columnas, muro de '
                          'escalera, remates).'),
        ('CI-01', 'CIELO', 'Cielo liso lavable sin juntas abiertas: gypsum RH con pintura epóxica blanca o panel sanitario; sin cielo '
                           'modular poroso; incombustible junto a campanas y ductos (holguras NFPA 96 — verificar). Altura VERIFY ON SITE.'),
        ('CI-02', 'CIELO', f'Cielo expuesto: losa, vigas, ductos, bandejas y tuberías pintados negro mate (near-black); luminarias '
                           f'colgantes. Altura libre supuesta {h:.2f} — VERIFY ON SITE.'),
        ('FD', 'SIFÓN', 'Coladera / sifón de piso FD-n con rejilla inox y trampa (propuesto, mismo trazado que M-101): ubicación, diámetro '
                        'y pendientes por ingeniería sanitaria (CIHSE) — VERIFY. Existentes WP: reutilizar si el levantamiento lo confirma.'),
        ('TR', 'TRANSICIÓN', 'Cambio PI-01 / PI-03 en P-1 a nivel: perfil inox biselado ≤ 0.02 (art. 142 DE 26831-MP — verificar).'),
    ]


# ----------------------------------------------------------------------------------------------- helpers
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


def _table(x, y, cols, rows, size=1.6, lh=2.0, pad=0.9, head=1.7, title=None, title_note=None):
    g = []
    W = sum(c[1] for c in cols)
    if title:
        g.append(text(x, y + 3.0, title, 2.5, anchor='start', weight='800', extra='letter-spacing="0.3"'))
        if title_note:
            g.append(text(x + tw(title, 2.5) + len(title) * 0.5 + 4, y + 3.0, title_note, 1.7, anchor='start', fill=BAD, weight='600'))
        y += 5.2
    g.append(f'<rect x="{f(x)}" y="{f(y)}" width="{f(W)}" height="{f(head + 2.6)}" fill="#141210"/>')
    cx = x
    for h, w in cols:
        g.append(text(cx + 1.2, y + head + 0.75, h, head, anchor='start', weight='700', fill='#ffffff'))
        cx += w
    y += head + 2.6
    for i, r in enumerate(rows):
        cells, nl = [], 1
        for (h, w), c in zip(cols, r):
            if isinstance(c, str):
                s_, colr, wt, sw_ = c, '#222222', '400', None
            else:
                c = tuple(c) + ('#222', '400', None)[len(c) - 1:]
                s_, colr, wt, sw_ = c[:4]
            ls = _wrap(s_, w - 2.4 - (4.2 if sw_ else 0), size)
            nl = max(nl, len(ls))
            cells.append((ls, colr, wt, w, sw_))
        rh = nl * lh + 2 * pad
        if i % 2 == 1:
            g.append(f'<rect x="{f(x)}" y="{f(y)}" width="{f(W)}" height="{f(rh)}" fill="#f4f2ee"/>')
        cx = x
        for ls, colr, wt, w, sw_ in cells:
            dx = 1.2
            if sw_:
                g.append(sw_(cx + 1.2, y + pad + 0.1))
                dx = 5.4
            for j, ln in enumerate(ls):
                g.append(text(cx + dx, y + pad + size * 0.85 + j * lh, ln, size, anchor='start', weight=wt, fill=colr))
            cx += w
        y += rh
        g.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x + W)}" y2="{f(y)}" stroke="#d9d4cb" stroke-width="0.2"/>')
    return ''.join(g), y


def _floor_swatch(code, w=3.4, h=3.0):
    fill, stroke, _ = FLOOR[code]

    def fn(x, y):
        return f'<rect x="{f(x)}" y="{f(y)}" width="{w}" height="{h}" fill="url(#fin-{code})" stroke="{stroke}" stroke-width="0.3"/>'
    return fn


def _wall_swatch(code, w=3.4, h=3.0):
    def fn(x, y):
        return (f'<rect x="{f(x)}" y="{f(y)}" width="{w}" height="{h}" fill="#ffffff" stroke="#bbb" stroke-width="0.2"/>'
                f'<rect x="{f(x)}" y="{f(y + h - 1.1)}" width="{w}" height="1.1" fill="{WALLC[code]}"/>')
    return fn


def _shift(fn, dx=3.3):
    def g(x, y):
        return fn(x + dx, y)
    return g


def _generic_swatch(color):
    def fn(x, y):
        return f'<rect x="{f(x)}" y="{f(y)}" width="3.4" height="3.0" fill="{color}" stroke="#999" stroke-width="0.2"/>'
    return fn


# ----------------------------------------------------------------------------------------------- analysis
def _solids(ex, lay):
    ops = new_openings_geom(lay)
    nwg = []
    for w in lay.get('new_walls', []):
        g = R(w['rect'])
        for o in ops:
            g = g.difference(o.buffer(0.001))
        nwg.append((w, g))
    solid = unary_union([g for _, g in standing_existing_walls(ex, lay)] + [R(c['rect']) for c in ex['columns']] + [g for _, g in nwg])
    return solid, nwg


def _rooms(ex, lay, solid):
    prem = premises(ex)
    out = []
    for z in lay.get('zones', []):
        poly = Polygon(z['poly']).intersection(prem).difference(solid)
        for pg in getattr(poly, 'geoms', [poly]):
            if pg.geom_type == 'Polygon' and pg.area > 0.05:
                out.append((z, orient(pg, 1.0)))
    return out


def _wall_runs(ex, lay, rooms, solid, nwg):
    fire = [R(e['rect']) for e in lay.get('equipment', []) if e.get('cat') in ('fire', 'smoker') and not e.get('overhead')]
    slats = unary_union([R(d['rect']).buffer(0.08) for d in lay.get('decor', []) if d.get('type') == 'slat_wall'])
    part = unary_union([g for w, g in nwg if w.get('role') == 'kitchen_dining_partition'])
    panels = unary_union([g for w, g in nwg if w.get('role') != 'kitchen_dining_partition'])
    runs = []
    for z, pg in rooms:
        rings = [pg.exterior] + list(pg.interiors)
        for ring in rings:
            cs = list(ring.coords)
            for a, b in zip(cs[:-1], cs[1:]):
                L = math.dist(a, b)
                if L < 0.02:
                    continue
                dx, dy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
                nx, ny = dy, -dx          # outward normal (CCW exterior / CW holes)
                n = max(1, int(round(L / 0.05)))
                seq = []
                for i in range(n):
                    t = (i + 0.5) / n
                    p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
                    po = Point(p[0] + nx * 0.03, p[1] + ny * 0.03)
                    code = None
                    if solid.contains(po):
                        P = Point(p)
                        if z['id'] in KITCHEN:
                            if (not panels.is_empty and panels.buffer(0.01).contains(po)) or any(fr.distance(P) <= FIRE_MARGIN for fr in fire):
                                code = 'MU-02'
                            else:
                                code = 'MU-01'
                        else:
                            if not part.is_empty and part.buffer(0.01).contains(po):
                                code = 'MU-05'
                            elif ny < -0.5:
                                code = 'MU-04'
                            elif ny > 0.5 and not slats.is_empty and slats.contains(P):
                                code = 'MU-03'
                            else:
                                code = 'MU-06'
                    seq.append((t, code))
                # absorb short runs (< 0.35 m) sandwiched between two runs of the same code
                grp = []
                for t, code in seq:
                    if grp and grp[-1][0] == code:
                        grp[-1][1] += 1
                    else:
                        grp.append([code, 1])
                for k in range(1, len(grp) - 1):
                    if grp[k][1] * L / n < 0.35 and grp[k - 1][0] == grp[k + 1][0] and grp[k - 1][0]:
                        grp[k][0] = grp[k - 1][0]
                seq = [(0, c) for c, cnt in grp for _ in range(cnt)]
                i = 0
                while i < len(seq):
                    j = i
                    while j + 1 < len(seq) and seq[j + 1][1] == seq[i][1]:
                        j += 1
                    if seq[i][1]:
                        t0, t1 = i / n, (j + 1) / n
                        p0 = (a[0] + t0 * (b[0] - a[0]), a[1] + t0 * (b[1] - a[1]))
                        p1 = (a[0] + t1 * (b[0] - a[0]), a[1] + t1 * (b[1] - a[1]))
                        runs.append({'zone': z['id'], 'code': seq[i][1], 'p0': p0, 'p1': p1, 'n': (nx, ny), 'len': L * (t1 - t0)})
                    i = j + 1
    return runs


def _drains(ex, lay):
    """Proposed floor drains: the same FD-n as the plumbing scheme M-101 (sheets.s401_mecanica.plumbing_model) so both
    sheets agree; if that module is unavailable, fall back to drains derived here from the wet / hot equipment."""
    try:
        import importlib
        pm = importlib.import_module('sheets.s401_mecanica').plumbing_model(ex, lay)
        out = [{'p': tuple(pt), 'why': zone, 'id': fid, 'to': to} for fid, pt, zone, to, _g in pm.get('FD', [])]
        if out:
            return out
    except Exception as err:   # noqa: BLE001
        print('A-106: M-101 floor drains unavailable, deriving locally:', err)
    return _drains_local(ex, lay)


def _drains_local(ex, lay):
    """Fallback: floor drains derived from the wet / hot equipment (positions to be engineered)."""
    eq = lay.get('equipment', [])
    free_obs = unary_union([R(e['rect']) for e in eq if not e.get('overhead')])
    out = []

    def front_pt(rect, fr, d):
        x0, y0, x1, y1 = rect
        x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        return {'W': (x0 - d, (y0 + y1) / 2), 'E': (x1 + d, (y0 + y1) / 2), 'N': ((x0 + x1) / 2, y0 - d), 'S': ((x0 + x1) / 2, y1 + d)}.get(fr)

    def add(p, why):
        if p is None:
            return
        P = Point(p)
        if free_obs.buffer(0.12).contains(P):
            return
        if any(P.distance(Point(q['p'])) < 0.8 for q in out):
            return
        out.append({'p': p, 'why': why})
    for key, why in (('sink_2t', 'lavado'),):
        for e in eq:
            if e.get('key') == key:
                add(front_pt(e['rect'], e.get('front'), 0.40), why)
    hoods = [e for e in eq if e.get('key') == 'hood' and e.get('system') == 'grease']
    for hd in hoods:
        under = [e for e in eq if e.get('cat') == 'fire' and not e.get('overhead') and R(e['rect']).intersects(R(hd['rect']))]
        if under:
            u = unary_union([R(e['rect']) for e in under])
            fr = under[0].get('front', 'W')
            hx0, hy0, hx1, hy1 = R(hd['rect']).bounds
            rb = u.bounds
            p = {'W': (rb[0] - 0.45, (hy0 + hy1) / 2), 'E': (rb[2] + 0.45, (hy0 + hy1) / 2),
                 'N': ((hx0 + hx1) / 2, rb[1] - 0.45), 'S': ((hx0 + hx1) / 2, rb[3] + 0.45)}.get(fr)
            add(p, 'línea caliente')
    for key, why in (('smoker', 'BBQ / smoker'), ('fridge_2d', 'cold prep')):
        for e in eq:
            if e.get('key') == key:
                add(front_pt(e['rect'], e.get('front'), 0.45), why)
    for i, d in enumerate(out, 1):
        d['id'] = f'FD-{i}'
    return out


def _place_box(poly_pref, cx, cy, w, h, busy, step=0.1, rad=2.5, hard=None):
    """Best centre for a w×h (m) box near (cx, cy): inside poly_pref, least overlap with busy (and much less with `hard`:
    drains, door swings, tags already placed)."""
    best = None
    k = int(rad / step)
    for i in range(-k, k + 1):
        for j in range(-k, k + 1):
            x, y = cx + i * step, cy + j * step
            b = box(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
            out_ = b.difference(poly_pref).area
            sc = b.intersection(busy).area * 3 + out_ * 6 + 0.02 * math.hypot(i * step, j * step)
            if hard is not None:
                sc += b.intersection(hard).area * 40
            if best is None or sc < best[0]:
                best = (sc, x, y)
    return best[1], best[2]


# ----------------------------------------------------------------------------------------------- sheet
def sheets(ex, lay, val):
    s = Sheet(ex, lay, val, 'A106')
    s.frame_and_titleblock('A-106 · Acabados y puertas',
                           'Pisos PI · muros MU · zócalos / media caña ZO · cielos CI · sifones · cuadro de puertas y ventanas',
                           'A-106', scale_note='Escala 1:50 en A2 · cotas en metros')
    prem = premises(ex)
    solid, nwg = _solids(ex, lay)
    rooms = _rooms(ex, lay, solid)
    runs = _wall_runs(ex, lay, rooms, solid, nwg)
    drains = _drains(ex, lay)
    specs = _specs(ex)
    zones = {z['id']: z for z in lay.get('zones', [])}
    m = (val or {}).get('metrics', {})
    zarea = {z['id']: z['area_m2'] for z in m.get('zones', [])}

    # ---- patterns
    d = ['<defs>']
    for code, (fill, stroke, grid) in FLOOR.items():
        if grid:
            gw, gh = grid[0] * S, grid[1] * S
            d.append(f'<pattern id="fin-{code}" patternUnits="userSpaceOnUse" x="{f(sx(0))}" y="{f(sy(0.116))}" width="{f(gw)}" height="{f(gh)}">'
                     f'<rect width="{f(gw)}" height="{f(gh)}" fill="{fill}"/>'
                     f'<path d="M0,0 H{f(gw)} M0,0 V{f(gh)}" stroke="{stroke}" stroke-width="0.14" fill="none"/></pattern>')
        else:
            d.append(f'<pattern id="fin-{code}" patternUnits="userSpaceOnUse" width="2.2" height="2.2">'
                     f'<rect width="2.2" height="2.2" fill="{fill}"/><circle cx="0.6" cy="0.6" r="0.18" fill="{stroke}"/>'
                     f'<circle cx="1.7" cy="1.6" r="0.14" fill="{stroke}"/></pattern>')
    d.append('<pattern id="fin-fire" patternUnits="userSpaceOnUse" width="1.5" height="1.5" patternTransform="rotate(45)">'
             '<line x1="0" y1="0" x2="0" y2="1.5" stroke="#e0520b" stroke-width="0.35"/></pattern>')
    d.append('</defs>')
    s.add(''.join(d))
    s.grid_axes()

    # ---- floors
    g = ['<g id="floors">']
    for z, pg in rooms:
        code = ZONE_FIN.get(z['id'], {}).get('PI')
        if code:
            g.append(poly_el(pg, f'url(#fin-{code})', 'none', 0))
    # incombustible protection zones around solid-fuel equipment (floor + walls)
    firez = []
    for e in lay.get('equipment', []):
        if e.get('key') in ('parrilla', 'smoker') and not e.get('overhead'):
            firez.append(R(e['rect']).buffer(FIRE_MARGIN, join_style=2).intersection(prem))
    kitchen_rooms = unary_union([pg for z, pg in rooms if z['id'] in KITCHEN])
    fz = unary_union(firez).intersection(kitchen_rooms) if firez else None
    if fz is not None and not fz.is_empty:
        g.append(poly_el(fz, 'url(#fin-fire)', '#e0520b', 0.3, extra='stroke-dasharray="1.2 0.7"'))
    g.append('</g>')
    s.add(''.join(g))

    s.layer_existing()
    s.layer_furniture(faint=True)
    s.layer_equipment(faint=True, labels=False)
    s.layer_new()

    # ---- wall finish bands
    g = ['<g id="wall-finishes">']
    for r in runs:
        (x0, y0), (x1, y1), (nx, ny) = r['p0'], r['p1'], r['n']
        pts = [(x0, y0), (x1, y1), (x1 - nx * BAND, y1 - ny * BAND), (x0 - nx * BAND, y0 - ny * BAND)]
        g.append('<polygon points="' + ' '.join(f"{f(sx(px))},{f(sy(py))}" for px, py in pts) + f'" fill="{WALLC[r["code"]]}" stroke="none"/>')
    g.append('</g>')
    s.add(''.join(g))

    # busy geometry for label placement (model coordinates)
    items = unary_union([gg for _, _, gg in item_lists(lay)])
    swings = [door_swing_poly(o) for o in lay.get('new_openings', [])]
    for o in lay.get('new_openings', []):      # double-acting door: both quarter swings
        if o.get('type') == 'double_acting_door' and o.get('rect'):
            x0, y0, x1, y1 = o['rect']
            if (x1 - x0) < (y1 - y0):
                swings += [box((x0 + x1) / 2 - (y1 - y0), y0, (x0 + x1) / 2 + (y1 - y0), y1)]
    hard = unary_union([Point(dr['p']).buffer(0.25) for dr in drains] + [sw_ for sw_ in swings if sw_ is not None])
    busy = unary_union([items, solid, hard])

    # ---- wall code labels: longest run per (zone, code)
    g = ['<g id="wall-labels">']
    best = {}
    for r in runs:
        k = ('PUB' if r['zone'] in PUBLIC else r['zone'], r['code'])
        if r['len'] >= 0.9 and (k not in best or r['len'] > best[k]['len']):
            best[k] = r
    placed = []
    for k, r in sorted(best.items()):
        (x0, y0), (x1, y1), (nx, ny) = r['p0'], r['p1'], r['n']
        vert = abs(x1 - x0) < abs(y1 - y0)
        lab = r['code']
        wl, hl = tw(lab, 1.6) / S + 0.08, 0.13
        bw, bh = (hl, wl) if vert else (wl, hl)
        cands = []
        for tt in (0.5, 0.3, 0.7, 0.15, 0.85):
            mx, my = x0 + (x1 - x0) * tt, y0 + (y1 - y0) * tt
            for off in (0.19, 0.32, 0.5):
                cx, cy = mx - nx * off, my - ny * off
                bb = box(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
                sc = bb.intersection(busy).area + sum(bb.intersection(p).area for p in placed) * 5 + off * 0.01
                cands.append((sc, cx, cy, bb))
        sc, cx, cy, bb = min(cands, key=lambda c: c[0])
        placed.append(bb)
        g.append(f'<rect x="{f(sx(bb.bounds[0]))}" y="{f(sy(bb.bounds[1]))}" width="{f((bb.bounds[2]-bb.bounds[0])*S)}" '
                 f'height="{f((bb.bounds[3]-bb.bounds[1])*S)}" rx="0.5" fill="#ffffff" stroke="{WALLC[r["code"]]}" stroke-width="0.3"/>')
        g.append(text(sx(cx) + (0.6 if vert else 0), sy(cy) + (0 if vert else 0.6), lab, 1.6, weight='800', fill=WALLC[r['code']] if r['code'] != 'MU-06' else '#7a6440',
                      family=MONO, rot=-90 if vert else 0))
    g.append('</g>')
    s.add(''.join(g))
    busy = unary_union([busy] + placed)

    # ---- drains (proposed) + existing wet points
    g = ['<g id="drains">']
    wp_ids = set((lay.get('mep') or {}).get('drain_existing', []))
    for wp in ex.get('wet_points_existing', []):
        if wp['id'] in wp_ids:
            x0, y0, x1, y1 = wp['rect']
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            g.append(f'<rect x="{f(sx(cx) - 1.3)}" y="{f(sy(cy) - 1.3)}" width="2.6" height="2.6" fill="#fff" stroke="#8a8a85" stroke-width="0.25" stroke-dasharray="0.6 0.4"/>')
            g.append(text(sx(cx), sy(cy) + 3.6, wp['id'], 1.35, fill='#7a7a75', weight='700', family=MONO))
    for dr in drains:
        x, y = dr['p']
        X, Y = sx(x), sy(y)
        g.append(f'<circle cx="{f(X)}" cy="{f(Y)}" r="1.9" fill="#ffffff" stroke="#17737a" stroke-width="0.4"/>')
        g.append(f'<path d="M{f(X-1.2)},{f(Y)} H{f(X+1.2)} M{f(X)},{f(Y-1.2)} V{f(Y+1.2)} M{f(X-0.85)},{f(Y-0.85)} L{f(X+0.85)},{f(Y+0.85)} M{f(X-0.85)},{f(Y+0.85)} L{f(X+0.85)},{f(Y-0.85)}" stroke="#17737a" stroke-width="0.2"/>')
        g.append(text(X + 2.5, Y + 0.7, dr['id'], 1.6, anchor='start', weight='800', fill='#17737a', family=MONO,
                      extra='paint-order="stroke" stroke="#ffffff" stroke-width="0.7"'))
    g.append('</g>')
    s.add(''.join(g))

    # ---- door / window tags on plan
    g = ['<g id="opening-tags">']
    dent = next((dd for dd in ex.get('doors', []) if dd['id'] == 'D-ENT'), None)

    tag_boxes = []

    def reg(x, y, w, h=3.8):
        mx, my = VIEW[0] + (x - sx(VIEW[0])) / S, VIEW[1] + (y - sy(VIEW[1])) / S
        tag_boxes.append(box(mx - w / 2 / S, my - h / 2 / S, mx + w / 2 / S, my + h / 2 / S))

    def dtag(x, y, lab, colr='#141210', fill='#141210', tcol='#ffffff'):
        w = tw(lab, 1.6) + 3.2
        reg(x, y, w)
        return (f'<rect x="{f(x - w/2)}" y="{f(y - 1.9)}" width="{f(w)}" height="3.8" rx="1.9" fill="{fill}" stroke="{colr}" stroke-width="0.35"/>'
                + text(x, y + 0.6, lab, 1.6, weight='800', fill=tcol, family=MONO))

    def wtag(x, y, lab):
        w = tw(lab, 1.6) + 3.0
        reg(x, y, w)
        return (f'<path d="M{f(x - w/2)},{f(y)} L{f(x - w/2 + 1.3)},{f(y - 1.9)} H{f(x + w/2 - 1.3)} L{f(x + w/2)},{f(y)} '
                f'L{f(x + w/2 - 1.3)},{f(y + 1.9)} H{f(x - w/2 + 1.3)} z" fill="#ffffff" stroke="{COL["glass"]}" stroke-width="0.4"/>'
                + text(x, y + 0.6, lab, 1.6, weight='800', fill='#0b6f96', family=MONO))
    if dent:
        xo, ya, _, yb = dent['opening']
        g.append(dtag(sx(xo) + 12.5, sy((ya + yb) / 2) + 9.5, 'D-ENT'))
    # P-1 / PS-1 are already tagged by layer_new() ("P-1 · 0.90"): only register their label area
    for o in lay.get('new_openings', []):
        if o.get('rect'):
            x0, y0, x1, y1 = o['rect']
            if o.get('type') == 'double_acting_door':
                reg(sx((x0 + x1) / 2) + 7.5, sy((y0 + y1) / 2), 14.0)
            else:
                reg(sx((x0 + x1) / 2), sy((y0 + y1) / 2) + 5.2, 14.0)
    kept = _kept_openings(ex, lay, solid)
    for i, (dd, code) in enumerate(kept):
        xa, ya, xb, yb = dd['opening']
        g.append(dtag(sx((xa + xb) / 2) + 6.0, sy((ya + yb) / 2), code))
    for gl in ex.get('glazing', []):
        x0, y0, x1, y1 = gl['rect']
        if (x1 - x0) < (y1 - y0):
            g.append(wtag(sx(x1) + 6.5, sy((y0 + y1) / 2), gl['id']))
        else:
            g.append(wtag(sx((x0 + x1) / 2) - 10.0, sy(y1) + 4.2, gl['id']))
    for w, gg in nwg:
        if w.get('type') == 'glass_partition':
            x0, y0, x1, y1 = w['rect']
            g.append(wtag(sx(x1) + 7.0, sy(y0 + (y1 - y0) * 0.18), w['id']))
    # transition TR at the kitchen door
    p1 = next((o for o in lay.get('new_openings', []) if o.get('type') == 'double_acting_door'), None)
    if p1:
        x0, y0, x1, y1 = p1['rect']
        g.append(f'<line x1="{f(sx((x0 + x1) / 2))}" y1="{f(sy(min(y0, y1)))}" x2="{f(sx((x0 + x1) / 2))}" y2="{f(sy(max(y0, y1)))}" stroke="#b39b00" stroke-width="0.9"/>')
        g.append(text(sx(x1) + 2.0, sy(max(y0, y1)) - 0.3, 'TR', 1.6, anchor='start', weight='800', fill='#8a7700', family=MONO))
    g.append('</g>')
    s.add(''.join(g))
    busy = unary_union([busy] + tag_boxes)

    # ---- room finish tags
    g = ['<g id="room-tags">']
    TW, TH = 29.0, 14.6     # mm
    zone_mu = {}
    for r in runs:
        zone_mu.setdefault(r['zone'], set()).add(r['code'])
    for zid in [z['id'] for z in lay.get('zones', [])]:
        z = zones[zid]
        fin = ZONE_FIN.get(zid)
        if not fin:
            continue
        zp = Polygon(z['poly']).intersection(prem)
        at = z.get('label_at') or [zp.representative_point().x, zp.representative_point().y]
        cx, cy = _place_box(zp.buffer(-0.05), at[0], at[1], TW / S, TH / S, busy, hard=unary_union([hard] + tag_boxes))
        busy = busy.union(box(cx - TW / S / 2, cy - TH / S / 2, cx + TW / S / 2, cy + TH / S / 2))
        X0, Y0 = sx(cx) - TW / 2, sy(cy) - TH / 2
        colr = z.get('color', '#333')
        area = zarea.get(zid, zp.area)
        mus = sorted(zone_mu.get(zid, []))
        mu_txt = ('MU-' + '·'.join(c[3:] for c in mus)) if len(mus) > 2 else (' · '.join(mus) if mus else '—')
        rh = 3.55
        g.append(f'<rect x="{f(X0)}" y="{f(Y0)}" width="{TW}" height="{TH}" rx="0.8" fill="#ffffff" stroke="{colr}" stroke-width="0.45"/>')
        g.append(f'<rect x="{f(X0)}" y="{f(Y0)}" width="{TW}" height="3.9" rx="0.8" fill="{colr}"/>')
        g.append(text(X0 + TW / 2, Y0 + 2.8, f"{z.get('short', z.get('name', zid))[:16]} · {area:.1f} m²", 1.6, weight='800', fill='#ffffff'))
        y1 = Y0 + 3.9
        for i, (code, lab) in enumerate(((fin['PI'], 'PISO'), (fin['ZO'], 'ZÓC.'))):
            cxx = X0 + i * TW / 2
            g.append(text(cxx + 0.9, y1 + 2.6, lab, 1.15, anchor='start', fill='#777', weight='700'))
            g.append(text(cxx + TW / 2 - 0.8, y1 + 2.65, code, 1.55, anchor='end', fill='#1b1b1b', weight='800', family=MONO))
        g.append(text(X0 + 0.9, y1 + rh + 2.6, 'MUROS', 1.15, anchor='start', fill='#777', weight='700'))
        g.append(text(X0 + TW - 0.8, y1 + rh + 2.65, mu_txt, 1.45 if len(mu_txt) > 18 else 1.55, anchor='end', fill='#1b1b1b', weight='800', family=MONO))
        g.append(text(X0 + 0.9, y1 + 2 * rh + 2.6, 'CIELO', 1.15, anchor='start', fill='#777', weight='700'))
        g.append(text(X0 + TW / 2 - 0.8, y1 + 2 * rh + 2.65, fin['CI'], 1.55, anchor='end', fill='#1b1b1b', weight='800', family=MONO))
        g.append(text(X0 + TW / 2 + 0.9, y1 + 2 * rh + 2.6, 'REV.' if zid in KITCHEN else 'ALT.', 1.15, anchor='start', fill='#777', weight='700'))
        g.append(text(X0 + TW - 0.8, y1 + 2 * rh + 2.65, '≥ 2.10' if zid in KITCHEN else 'VERIFY', 1.4, anchor='end',
                      fill='#1b1b1b' if zid in KITCHEN else BAD, weight='800'))
        for k in (1, 2):
            g.append(f'<line x1="{f(X0)}" y1="{f(y1 + k * rh)}" x2="{f(X0 + TW)}" y2="{f(y1 + k * rh)}" stroke="#ddd" stroke-width="0.2"/>')
        g.append(f'<line x1="{f(X0 + TW/2)}" y1="{f(y1)}" x2="{f(X0 + TW/2)}" y2="{f(y1 + rh)}" stroke="#ddd" stroke-width="0.2"/>')
        g.append(f'<line x1="{f(X0 + TW/2)}" y1="{f(y1 + 2 * rh)}" x2="{f(X0 + TW/2)}" y2="{f(Y0 + TH)}" stroke="#ddd" stroke-width="0.2"/>')
    g.append('</g>')
    s.add(''.join(g))

    # ---- door / window schedule (free area of the plan)
    rows = _opening_rows(ex, lay, nwg, kept)
    tx0, ty0 = 240.0, 179.0
    svg, yend = _table(tx0, ty0, [('Código', 15), ('Ubicación · tipo', 40), ('Vano · hoja', 26), ('Libre', 15),
                                  ('Material · acabado', 44), ('Herrajes · observaciones', 46)],
                       rows, size=1.55, lh=1.95, pad=0.8, head=1.6, title='CUADRO DE PUERTAS Y VENTANAS', title_note='* estimado: hoja − 0.06')
    s.add(f'<rect x="{f(tx0 - 2)}" y="{f(ty0 - 1.5)}" width="190" height="{f(yend - ty0 + 5.6)}" fill="#ffffff" stroke="#1b1b1b" stroke-width="0.35"/>')
    s.add(svg)
    s.add(text(tx0, yend + 2.6, 'Anchos, alturas y herrajes a confirmar en sitio y con proveedor (VERIFY ON SITE). Puertas de egreso: NFPA 101 / RNPCI (verificar).',
               1.45, anchor='start', fill='#666'))

    # ---- side panel
    leg = [(_floor_swatch(c), f"{c} · {t}") for c, t in (('PI-01', 'porcelanato antideslizante (cocina)'), ('PI-02', 'uretano-cemento (lavado)'),
                                                         ('PI-03', 'porcelanato 60×120 "concreto pulido"'))]
    leg = [(_shift(fn), lab) for fn, lab in leg]
    leg.append((lambda x, y: f'<rect x="{x+3.3}" y="{y}" width="3.4" height="3.0" fill="url(#fin-fire)" stroke="#e0520b" stroke-width="0.3" stroke-dasharray="1 0.6"/>',
                'Protección incombustible (piso + MU-02)'))
    names = {'MU-01': 'revestimiento sanitario claro', 'MU-02': 'protección incombustible', 'MU-03': 'listones de madera retroiluminados',
             'MU-04': 'concreto visto encofrado de tabla', 'MU-05': 'base NW-1 cara salón', 'MU-06': 'pintura lavable gris cálido'}
    for c in WALLC:
        leg.append((_shift(_wall_swatch(c)), f"{c} · {names[c]}"))
    leg.append((lambda x, y: (f'<circle cx="{x+5}" cy="{y+1.6}" r="1.6" fill="#fff" stroke="#17737a" stroke-width="0.35"/>'
                              f'<path d="M{x+4},{y+1.6} H{x+6} M{x+5},{y+0.6} V{y+2.6}" stroke="#17737a" stroke-width="0.2"/>'),
                'FD · coladera / sifón de piso (esquema M-101)'))
    leg.append((lambda x, y: f'<rect x="{x+3.8}" y="{y+0.4}" width="2.4" height="2.4" fill="#fff" stroke="#8a8a85" stroke-width="0.25" stroke-dasharray="0.6 0.4"/>',
                'WP · punto húmedo / desagüe existente'))
    leg.append((lambda x, y: f'<rect x="{x+1}" y="{y}" width="8" height="3.4" rx="1.7" fill="#141210"/>', 'Puerta (ver cuadro)'))
    leg.append((lambda x, y: f'<path d="M{x+1},{y+1.7} L{x+2.2},{y} H{x+7.8} L{x+9},{y+1.7} L{x+7.8},{y+3.4} H{x+2.2} z" fill="#fff" stroke="{COL["glass"]}" stroke-width="0.4"/>',
                'Ventana / vidrio (ver cuadro)'))
    leg.append((lambda x, y: f'<line x1="{x+5}" y1="{y}" x2="{x+5}" y2="{y+3.4}" stroke="#b39b00" stroke-width="0.9"/>', 'TR · transición de piso a nivel'))
    leg += [LEGEND_WALLS[0], LEGEND_WALLS[2], LEGEND_WALLS[3]]
    health = [
        'DE 37308-S, Reglamento de Servicios de Alimentación al Público',
        '(artículos no confirmados — verificar en SCIJ):',
        '· pisos impermeables, antideslizantes, lavables, sin grietas y',
        '  con pendiente hacia sifones de piso;',
        '· paredes lisas, impermeables, lavables y de color claro;',
        '· unión piso–pared sanitaria (media caña);',
        '· cielos lisos y lavables, que no suelten partículas ni',
        '  acumulen grasa o condensación;',
        '· luminarias protegidas contra rotura sobre alimentos;',
        '· aberturas al exterior con cedazo; pasos de tubería sellados.',
    ]
    fire = [
        'Tras parrilla, smoker, línea a gas y horno: MU-02 incombustible;',
        'campanas / ductos a 457 mm de combustibles, 76 mm de',
        'combustibilidad limitada, 0 mm de incombustibles (NFPA 96',
        '§4.2 — verificar). Piso bajo equipos de combustible sólido',
        'según su listado. Madera del salón (MU-03): tratamiento',
        'retardante; clase según NFPA 101 cap. 10 / RNPCI (verificar).',
        '!NW-1: base incombustible + vidrio: spec térmica / cortafuego',
        '!TO BE ENGINEERED.',
    ]
    look = [
        'Salón / barra (render): PI-03 gris claro cálido "concreto',
        'pulido"; muro sur MU-03 listones retroiluminados; muro norte',
        'MU-04 concreto encofrado de tabla; cielo expuesto CI-02 negro',
        'mate con ductos a la vista.',
        '!ANTEPROYECTO / PRELIMINAR: a validar por el profesional',
        '!responsable. Muestras y fichas técnicas antes de comprar.',
    ]
    doors = [
        'Manijas de palanca h 0.90–1.00; apertura sin llave desde el',
        'interior en puertas de egreso (NFPA 101 / RNPCI — verificar).',
        'P-1: visor, placa de protección y retorno a centro; hoja',
        'incombustible (junto a la parrilla).',
        'Puertas y vanos al exterior: burlete y barredor (control de',
        'plagas); vidrios de fachada con bandas de contraste.',
    ]
    site = [
        '!VERIFY ON SITE antes de especificar:',
        f"· altura libre a losa (supuesta {float((ex.get('ceiling') or {}).get('height_assumed', 3.0)):.2f}) y ductos existentes;",
        '· niveles de piso interior / pasillo CC en D-ENT (umbral);',
        '· estado de la losa para pendientes a sifones (espesor de',
        '  relleno) y diámetro / destino de WP1–WP3 y WP5;',
        '· sustrato de muros existentes para revestimiento MU-01;',
        '· material del muro oeste detrás del smoker (MU-02).',
    ]
    s.side_panel([('h', 'Leyenda'), ('legend', leg),
                  ('h', 'Criterios sanitarios (verificar)'), ('para', health),
                  ('h', 'Protección contra fuego'), ('para', fire),
                  ('h', 'Puertas y vidrios'), ('para', doors),
                  ('h', 'Verificaciones en sitio'), ('para', site),
                  ('h', 'Concepto del salón'), ('para', look)])

    # ---- band: finish schedule by room + code specifications
    _band(s, lay, zones, zarea, zone_mu, drains, rooms, specs, ex)
    return [{'id': 'A106', 'file': 'lava_A106_acabados.svg', 'title': 'Acabados y puertas', 'order': 106, 'svg': s.render()}]


def _kept_openings(ex, lay, solid):
    """Existing openings (doors[].kind opening) whose both jambs still stand -> VA-n."""
    out = []
    n = 0
    for dd in ex.get('doors', []):
        if dd.get('kind') != 'opening' or 'opening' not in dd:
            continue
        xa, ya, xb, yb = dd['opening']
        seg = box(min(xa, xb) - 0.01, min(ya, yb) - 0.01, max(xa, xb) + 0.01, max(ya, yb) + 0.01)
        if any(o.get('rect') and R(o['rect']).buffer(0.02).intersection(seg).area > 0.5 * seg.area for o in lay.get('new_openings', [])):
            continue          # a new door now hangs in this existing opening (e.g. P-2 in D-P1-old): scheduled as that door
        if solid.buffer(0.03).contains(Point(xa, ya)) and solid.buffer(0.03).contains(Point(xb, yb)):
            n += 1
            out.append((dd, f'VA-{n}'))
    return out


def _dist_key(lay, o, key):
    eqs = [R(e['rect']) for e in lay.get('equipment', []) if e.get('key') == key]
    return min((R(o['rect']).distance(g) for g in eqs), default=float('nan'))


def _opening_rows(ex, lay, nwg, kept):
    rows = []
    ls = lay.get('life_safety', {})
    cap = ls.get('capacity_declared', 49)
    dent = next((dd for dd in ex.get('doors', []) if dd['id'] == 'D-ENT'), None)
    exd = next((e for e in ls.get('exits', []) if e.get('opening') == 'D-ENT'), {})
    if dent:
        leaf = float(exd.get('leaf', 0.97))
        wd = float(exd.get('width', dent.get('width', 2.0)))
        rows.append([('D-ENT', '#141210', '800'), 'Fachada · acceso principal EXISTENTE; doble abatible, abre hacia adentro',
                     f'{wd:.2f} × h VERIFY · 2 hojas {leaf:.2f}', f'≈{leaf - LEAF_LOSS:.2f}/hoja*',
                     'Existente (marco y hojas: VERIFY ON SITE). Vidrio de seguridad; bandas de contraste h 0.90–1.00 y 1.30–1.40 (recomendado).',
                     (f'Manija de palanca, apertura sin llave desde el interior, rótulo SALIDA iluminado, umbral ≤ 0.02 biselado. Aforo {cap} (< 50): '
                      'giro hacia adentro admitido (NFPA 101 — verificar). RECOMENDADO invertir el giro hacia afuera sin invadir el pasillo '
                      'común — VERIFY con la administración.', BAD, '600')])
    for o in lay.get('new_openings', []):
        wd = float(o.get('width', 0.9))
        if o.get('type') == 'double_acting_door':
            host = next((w['id'] for w, gg in nwg if o.get('rect') and R(w['rect']).buffer(0.01).contains(R(o['rect']))), 'muro nuevo')
            cl = wd - LEAF_LOSS
            ok = cl >= 0.90 - 1e-6
            rows.append([(o.get('label', o['id']), '#141210', '800'), f"{host} · cocina ↔ salón, NUEVA; vaivén (doble acción) 1 hoja, retorno a centro",
                         f'{wd:.2f} nominal × 2.10', (f'≈{cl:.2f}*', '#222' if ok else BAD, '700'),
                         f'Hoja incombustible (acero inox / núcleo mineral) — a ≈{_dist_key(lay, o, "parrilla"):.2f} de la parrilla; visor de vidrio templado '
                         'o laminado a la altura de la vista; placa de protección inox h 0.30 en ambas caras.',
                         ('Bisagra de piso de doble acción, sin umbral (TR a nivel). '
                          + ('≥ 0.90 libres estimados (art. 140 — verificar con la hoja real). ' if ok else
                             '< 0.90 libres (art. 140 — verificar): recomendado vano ≈1.00. ')
                          + 'Separación platos / loza por horario u operación; siempre libre (ruta de evacuación del personal).',
                          '#222' if ok else BAD, '600')])
        elif o.get('type') in ('service_door', 'door'):
            cond = o.get('conditional')
            cl = wd - LEAF_LOSS
            if cond:
                gl_hit = [gl['id'] for gl in ex.get('glazing', []) if o.get('rect') and R(gl['rect']).intersects(R(o['rect']))]
                rows.append([(o.get('label', o['id']), BAD, '800'),
                             ('Muro sur del ala · servicio; abatible 1 hoja hacia afuera — CONDICIONAL', BAD, '600'),
                             f'{wd:.2f} × 2.10', f'≈{cl:.2f}*',
                             'Metálica (acero) con marco, burlete y barredor inferior (control de plagas); acabado esmalte.',
                             'Apertura sin llave desde el interior + cierrapuertas.'
                             + (f" Sustituye parte de la ventana {', '.join(gl_hit)}:" if gl_hit else '')
                             + ' aprobación de la administración y revisión estructural — VERIFY ON SITE. No cuenta como salida.'])
            else:
                host_op = next((dd for dd in ex.get('doors', []) if dd.get('opening') and o.get('rect') and
                                R(o['rect']).buffer(0.05).contains(Point(dd['opening'][0], dd['opening'][1]))), None)
                where = (f"Vano existente {host_op['id']} ({host_op.get('note', '').rstrip('.').lower()})" if host_op
                         else 'Muro interior del ala')
                okd = cl >= 0.90 - 1e-6
                swing = ''
                if o.get('hinge') and o.get('swing_to') and o.get('closed_to'):
                    hx, hy = o['hinge']
                    bx, by = o['swing_to']
                    cx_, cy_ = o['closed_to']
                    mid = Point(hx + 0.5 * (bx - hx) + 0.5 * (cx_ - hx), hy + 0.5 * (by - hy) + 0.5 * (cy_ - hy))
                    zs = [z for z in lay.get('zones', []) if Polygon(z['poly']).contains(mid)]
                    swing = f"; abre hacia {(zs[0].get('name') or zs[0].get('short') or zs[0]['id']).split(' (')[0].split(':')[0].lower()}" if zs else ''
                rows.append([(o.get('label', o['id']), '#141210', '800'),
                             f"{where}: NUEVA abatible 1 hoja con cierre automático{swing}",
                             f'{wd:.2f} × 2.10', (f'≈{cl:.2f}*', '#222' if okd else WARN, '700'),
                             'Hoja lavable (acero inox o laminado HPL sobre núcleo sólido), marco metálico, barredor inferior; visor recomendado.',
                             ('Manija de palanca, sin llave en el sentido de egreso, cierrapuertas (separa limpio / sucio). '
                              + ('' if okd else '< 0.90 libres (art. 140 — verificar; área de personal): ampliar vano a ≈1.00 o justificar. ')
                              + 'Ruta de evacuación del ala: siempre libre.', '#222' if okd else WARN, '600')])
    for dd, code in kept:
        rows.append([(code, '#141210', '800'), f"Vano existente sin hoja ({dd['id']}): {dd.get('note', '')}", f"{float(dd.get('width', 0.9)):.2f} · sin hoja",
                     f"{float(dd.get('width', 0.9)):.2f}", 'Jambas con esquinero sanitario inox; mismo acabado MU-01.', 'Sin umbral; piso continuo.'])
    for w, gg in nwg:
        x0, y0, x1, y1 = w['rect']
        L = max(abs(x1 - x0), abs(y1 - y0))
        net = gg.area / max(min(abs(x1 - x0), abs(y1 - y0)), 1e-6)
        if w.get('type') == 'glass_partition':
            rows.append([(w['id'], '#0b6f96', '800'), 'División cocina / salón NUEVA: base sólida + vidrio (show kitchen)',
                         f"{net:.2f} netos (de {L:.2f}) · base h {float(w.get('base_h', 1.0)):.2f} · h {float(w.get('h', 3.0)):.2f}", '—',
                         'Base incombustible (bloque de concreto o perfilería de acero + placa cementicia). Vidrio: vitrocerámico o '
                         'cortafuego frente a la parrilla; resto templado laminado.',
                         ('Glazing thermal / fire spec TO BE ENGINEERED. Anclaje a losa y cielo; junta perimetral incombustible.', BAD, '700')])
        else:
            rows.append([(w['id'], '#141210', '800'), f"Panel lateral entre parrilla y P-1 ({w.get('short', '')})",
                         f"{L:.2f} × h {float(w.get('h', 2.0)):.2f}", '—', 'Incombustible: acero inox sobre placa cementicia (MU-02).',
                         'Cierre lateral de la campana 2 — TO BE ENGINEERED con la campana.'])
    ps = next((o for o in lay.get('new_openings', []) if o.get('conditional') and o.get('type') in ('service_door', 'door') and o.get('rect')), None)
    fronts = [gl for gl in ex.get('glazing', []) if gl.get('kind') == 'storefront']
    if fronts:
        ws = ' / '.join(f"{max(abs(gl['rect'][2]-gl['rect'][0]), abs(gl['rect'][3]-gl['rect'][1])):.2f}" for gl in fronts)
        rows.append([(' · '.join(gl['id'] for gl in fronts), '#0b6f96', '800'), 'Vitrinas fijas de fachada EXISTENTES', f'{ws} × h VERIFY', '—',
                     'Mantener. Vinil / rótulo LAVA opcional; bandas de contraste visual (recomendado).', 'VERIFY ON SITE tipo de vidrio y estado.'])
    for gl in ex.get('glazing', []):
        if gl.get('kind') == 'storefront':
            continue
        x0, y0, x1, y1 = gl['rect']
        L = max(abs(x1 - x0), abs(y1 - y0))
        rest = ''
        if ps:
            gg = R(gl['rect']).difference(R(ps['rect']).buffer(0.001))
            rem = [max(p.bounds[2] - p.bounds[0], p.bounds[3] - p.bounds[1]) for p in getattr(gg, 'geoms', [gg]) if p.area > 1e-4]
            if rem:
                rest = f" Si se aprueba {ps.get('label', ps['id'])}: queda {max(rem):.2f}."
        rows.append([(gl['id'], '#0b6f96', '800'), 'Ventana EXISTENTE muro sur del ala (cold prep)', f'{L:.2f} × h VERIFY', '—',
                     'Mantener con cedazo / malla contra insectos (37308-S — verificar); vidrio lavable.', 'VERIFY qué hay detrás.' + rest])
    return rows


def _band(s, lay, zones, zarea, zone_mu, drains, rooms, specs, ex):
    top = 318.0
    g = [f'<line x1="12" y1="{top - 2}" x2="430" y2="{top - 2}" stroke="#141210" stroke-width="0.3"/>',
         f'<line x1="191" y1="{top}" x2="191" y2="410" stroke="#d9d4cb" stroke-width="0.25"/>']
    # ---- room schedule
    zp = {zid: unary_union([pg for z, pg in rooms if z['id'] == zid]) for zid in zones}
    rows = []
    for zid, z in zones.items():
        fin = ZONE_FIN.get(zid)
        if not fin:
            continue
        sps = [d['id'] for d in drains if (zp.get(zid) is not None and zp[zid].buffer(0.05).contains(Point(d['p'])))
               or zid in re.findall(r'\b([A-Z])\b', (d.get('why') or '').split('zona')[-1] if 'zona' in (d.get('why') or '') else '')]
        kitchen = zid in KITCHEN
        mus = sorted(zone_mu.get(zid, []))
        rows.append([(zid, z.get('color', '#333'), '800'), z.get('name', z.get('short', '')),
                     f"{zarea.get(zid, zp[zid].area if zp.get(zid) is not None else 0):.1f}",
                     (fin['PI'], '#1b1b1b', '800', _floor_swatch(fin['PI'], 3.4, 2.6)), fin['ZO'], ', '.join(mus) if mus else '—',
                     '≥ 2.10 / a cielo' if kitchen else '—', fin['CI'], ', '.join(sps) if sps else '—'])
    svg, yend = _table(12, top, [('Zona', 9), ('Local', 47), ('m²', 9), ('Piso', 18), ('Zócalo', 13), ('Muros', 30),
                                 ('Revest. h', 19), ('Cielo', 12), ('Sifón', 12)],
                       rows, size=1.65, lh=2.05, pad=0.75, head=1.6, title='CUADRO DE ACABADOS POR LOCAL')
    g.append(svg)
    notes = ['Muros calculados por paramento (bandas de color en planta); MU-02 = equipo de fuego + 0.45 a cada lado.',
             'Media caña continua también en bases de equipos fijos y al pie de NW-1 / NW-2. Coladeras FD: propuestas (ver M-101).']
    for i, ln in enumerate(notes):
        g.append(text(12, yend + 3.0 + i * 2.25, ln, 1.5, anchor='start', fill='#333'))
    # ---- three small details under the room schedule
    dy = yend + 8.5
    g.append(_details(dy, ex, lay))
    # ---- code specifications (two columns)
    x0 = 195.0
    g.append(text(x0, top + 3.0, 'ESPECIFICACIÓN DE CÓDIGOS', 2.5, anchor='start', weight='800', extra='letter-spacing="0.3"'))
    g.append(text(x0 + 62, top + 3.0, 'ANTEPROYECTO · a validar por el profesional responsable', 1.7, anchor='start', fill=BAD, weight='600'))
    colw = 116.0
    half = (len(specs) + 1) // 2
    size, lh = 1.6, 2.0
    for ci, chunk in enumerate((specs[:half], specs[half:])):
        yy = top + 7.0
        xx = x0 + ci * (colw + 2)
        for code, kind, txt in chunk:
            if code in FLOOR:
                sw = _floor_swatch(code, 3.4, 2.6)(xx, yy + 0.2)
            elif code in WALLC:
                sw = _wall_swatch(code, 3.4, 2.6)(xx, yy + 0.2)
            elif code == 'FD':
                sw = (f'<circle cx="{f(xx + 1.7)}" cy="{f(yy + 1.5)}" r="1.3" fill="#fff" stroke="#17737a" stroke-width="0.3"/>')
            elif code == 'TR':
                sw = f'<line x1="{f(xx + 1.7)}" y1="{f(yy + 0.2)}" x2="{f(xx + 1.7)}" y2="{f(yy + 2.8)}" stroke="#b39b00" stroke-width="0.9"/>'
            else:
                sw = f'<rect x="{f(xx)}" y="{f(yy + 0.2)}" width="3.4" height="2.6" fill="{"#e9e9e6" if code.startswith("ZO") else "#2a2a2a" if code == "CI-02" else "#fafafa"}" stroke="#999" stroke-width="0.25"/>'
            g.append(sw)
            g.append(text(xx + 4.6, yy + 2.2, code, 1.75, anchor='start', weight='800', family=MONO,
                          fill=WALLC.get(code, '#1b1b1b') if code != 'MU-06' else '#7a6440'))
            g.append(text(xx + 4.6, yy + 4.4, kind, 1.2, anchor='start', weight='700', fill='#888'))
            ls = _wrap(txt, colw - 17.0, size)
            for j, ln in enumerate(ls):
                g.append(text(xx + 15.5, yy + 1.9 + j * lh, ln, size, anchor='start', fill=BAD if ('TO BE ENGINEERED' in ln or 'VERIFY' in ln) else '#222'))
            yy += max(2, len(ls)) * lh + 1.45
    s.add(''.join(g))


def _details(y, ex, lay):
    """Three small generic details (schematic, to be engineered): media caña, TR at P-1, MU-02 layers behind the grill."""
    g = []
    hatch = 'url(#hatch-ex)'

    def title(x, n, t, sc):
        return (f'<circle cx="{f(x + 2.2)}" cy="{f(y + 1.7)}" r="2.2" fill="#141210"/>' + text(x + 2.2, y + 2.5, str(n), 2.2, weight='800', fill='#fff')
                + text(x + 5.6, y + 2.6, t, 1.9, anchor='start', weight='800') + text(x + 5.6 + tw(t, 1.9) + len(t) * 0.12 + 1.5, y + 2.6, sc, 1.6,
                                                                                         anchor='start', fill='#666', weight='700', family=MONO))
    k5 = 200.0            # 1:5
    # 1 · media caña (ZO-01) at 1:5
    x = 12.0
    g.append(title(x, 1, 'MEDIA CAÑA ZO-01', '1:5'))
    ox, fy = x + 8.0, y + 24.0
    r = 0.03 * k5
    t = 0.01 * k5
    g.append(f'<rect x="{f(ox - 5)}" y="{f(y + 6)}" width="5" height="{f(fy - y - 6 + 4)}" fill="{hatch}" stroke="#5c5c58" stroke-width="0.2"/>')
    g.append(f'<rect x="{f(ox - 5)}" y="{f(fy)}" width="44" height="4" fill="{hatch}" stroke="#5c5c58" stroke-width="0.2"/>')
    g.append(f'<rect x="{f(ox)}" y="{f(y + 6)}" width="{f(t)}" height="{f(fy - t - r - y - 6)}" fill="{WALLC["MU-01"]}" fill-opacity="0.55" stroke="#1b1b1b" stroke-width="0.2"/>')
    g.append(f'<rect x="{f(ox + t + r)}" y="{f(fy - t)}" width="{f(39 - t - r)}" height="{f(t)}" fill="{FLOOR["PI-01"][0]}" stroke="#1b1b1b" stroke-width="0.2"/>')
    g.append(f'<path d="M{f(ox)},{f(fy - t - r)} H{f(ox + t)} A{f(r)},{f(r)} 0 0 0 {f(ox + t + r)},{f(fy - t)} V{f(fy)} H{f(ox)} z" fill="#d7e3ee" stroke="#1b1b1b" stroke-width="0.25"/>')
    g.append(text(ox + 10, y + 9.5, 'MU-01 revestimiento liso', 1.4, anchor='start', fill='#333'))
    g.append(text(ox + 10, fy - 5.4, f'ZO-01 radio ≥ {0.03:.2f} (verificar)', 1.4, anchor='start', fill='#333', weight='700'))
    g.append(text(ox + 10, fy - 2.6, 'PI-01 + pendiente a FD', 1.4, anchor='start', fill='#333'))
    g.append(f'<line x1="{f(ox + 9.5)}" y1="{f(fy - 5.9)}" x2="{f(ox + t + r * 0.4)}" y2="{f(fy - t - r * 0.4)}" stroke="#777" stroke-width="0.15"/>')
    # 2 · floor transition TR at P-1, 1:5
    x = 70.0
    g.append(title(x, 2, 'TRANSICIÓN TR EN P-1', '1:5'))
    ox, fy = x + 4.0, y + 20.0
    g.append(f'<rect x="{f(ox)}" y="{f(fy)}" width="54" height="4" fill="{hatch}" stroke="#5c5c58" stroke-width="0.2"/>')
    g.append(f'<rect x="{f(ox)}" y="{f(fy - 2.2)}" width="25" height="2.2" fill="{FLOOR["PI-01"][0]}" stroke="#1b1b1b" stroke-width="0.2"/>')
    g.append(f'<rect x="{f(ox + 29)}" y="{f(fy - 2.2)}" width="25" height="2.2" fill="{FLOOR["PI-03"][0]}" stroke="#1b1b1b" stroke-width="0.2"/>')
    g.append(f'<path d="M{f(ox + 25)},{f(fy)} V{f(fy - 2.2)} H{f(ox + 29)} V{f(fy)} M{f(ox + 27)},{f(fy - 2.2)} V{f(fy + 1.8)}" fill="none" stroke="#8a7700" stroke-width="0.45"/>')
    g.append(text(ox + 12.5, fy - 3.4, 'PI-01 cocina', 1.4, fill='#333', weight='700'))
    g.append(text(ox + 41.5, fy - 3.4, 'PI-03 salón', 1.4, fill='#333', weight='700'))
    g.append(text(ox + 27, fy + 7.4, 'perfil inox a nivel · ≤ 0.02 biselado', 1.4, fill='#8a7700', weight='700'))
    g.append(text(ox + 27, fy + 9.8, 'sin umbral (art. 142 — verificar)', 1.4, fill='#333'))
    # 3 · MU-02 layers behind the grill (plan section through NW-1), 1:10 — schematic
    x = 128.0
    k10 = 100.0
    g.append(title(x, 3, 'MU-02 TRAS PARRILLA', '1:10'))
    nw = next((w for w in lay.get('new_walls', []) if w.get('role') == 'kitchen_dining_partition'), None)
    tnw = min(abs(nw['rect'][2] - nw['rect'][0]), abs(nw['rect'][3] - nw['rect'][1])) if nw else 0.15
    ox, cy = x + 4.0, y + 13.5
    hh = 9.0
    layers = [('parrilla (listada / aprobada)', 0.08, COL['fire'][0]), ('separación según listado', 0.05, '#ffffff'),
              ('lámina acero inoxidable', 0.006, '#b8c2c8'), ('placa cementicia', 0.015, '#d8d4cc'), ('cámara de aire', 0.025, '#ffffff'),
              (f"NW-1 base incombustible e {tnw:.2f}", tnw, None), ('MU-05 cara salón', 0.01, '#3a3a3a')]
    xx = ox
    for i, (lab, th, fill) in enumerate(layers):
        w = max(th * k10, 0.45)
        g.append(f'<rect x="{f(xx)}" y="{f(cy - hh / 2)}" width="{f(w)}" height="{f(hh)}" fill="{fill or hatch}" stroke="#1b1b1b" stroke-width="0.2"/>')
        mx = xx + w / 2
        ny = cy - hh / 2 - 2.2 - (1.9 if i in (2, 4) else 0)
        g.append(f'<line x1="{f(mx)}" y1="{f(cy - hh / 2)}" x2="{f(mx)}" y2="{f(ny + 0.9)}" stroke="#888" stroke-width="0.12"/>')
        g.append(f'<circle cx="{f(mx)}" cy="{f(ny)}" r="0.95" fill="#ffffff" stroke="#1b1b1b" stroke-width="0.18"/>')
        g.append(text(mx, ny + 0.5, str(i + 1), 1.2, weight='800'))
        xx += w
    # break line on the grill side
    g.append(f'<path d="M{f(ox)},{f(cy - hh / 2 - 0.5)} l0.8,2 l-1.6,1.5 l1.6,1.5 l-0.8,2" fill="none" stroke="#555" stroke-width="0.2"/>')
    g.append(text(xx + 1.2, cy - 0.6, 'SALÓN', 1.35, anchor='start', fill='#555', weight='700'))
    g.append(text(xx + 1.2, cy + 1.6, '(NW-1)', 1.3, anchor='start', fill='#777'))
    g.append(text(ox, cy + hh / 2 + 2.4, '← COCINA', 1.35, anchor='start', fill='#555', weight='700'))
    ky = cy + hh / 2 + 5.6
    for i, (lab, th, fill) in enumerate(layers):
        cx_ = x + (i // 4) * 31.0
        cy_ = ky + (i % 4) * 2.1
        g.append(text(cx_, cy_, f"{i + 1}  {lab}", 1.35, anchor='start', fill='#333'))
    g.append(text(x, ky + 4 * 2.1 + 0.8, 'Esquemático: espesores y separaciones TO BE ENGINEERED', 1.4, anchor='start', fill=BAD, weight='700'))
    return ''.join(g)
