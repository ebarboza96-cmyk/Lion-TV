"""E-101 · Eléctrico (esquema) y cuadro de cargas preliminar.

Plug-in de lámina extra: sheets(ex, lay, val) -> [{id, file, title, order, svg}]
  E-101 · Eléctrico (esquema) y cuadro de cargas preliminar      order 501   lava_E101_electrico.svg
También escribe data/elec_loads.json (cargas por circuito, asignación de fases en TE-1, demanda NEC 2020 art. 220,
acometida sugerida, enclavamientos y verificaciones).

Todo se ubica desde data/existing.json + data/layout.json (+ data/mech_calcs.json si existe):
  * puntos de fuerza en la cara posterior de cada equipo (lado opuesto a `front`), llevados al muro si está a ≤0.35 m;
  * TE-1 = layout.mep.panel; CC-1 (control de campanas) se deriva al lado de TE-1 y comparte su espacio de trabajo;
  * ventiladores EXT-1 / EXT-2 (layout.mep.exhaust, en el collarín) y AR-1 (mep.makeup_air; símbolo en el riser propuesto
    de M-102, mech_calcs.makeup_air.riser): caudales de mech_calcs.json → potencia;
  * gas: solenoide VS (mep.gas.solenoid); detector DG-1 y gabinetes SUP-1/SUP-2 con la misma regla que M-102;
  * calentadores CA-1 / CA-2 de mech_calcs.json (water_heaters);
  * alumbrado: luminarias de A-201 (sheets.s201_cielos.ceiling_layout) agrupadas en circuitos por zona;
    emergencia / rótulos de salida de layout.life_safety.
Los valores de kW / A son TÍPICOS de catálogo (TBV = to be verified con la ficha técnica de cada equipo).

ANTEPROYECTO / PRELIMINAR — a validar por ingeniero electricista (Código Eléctrico CR / NEC 2020).
"""
import json
import math
import os
import sys

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lavageo import R, ROOT, blocking_obstacles, load_json, premises, standing_existing_walls  # noqa: E402
from plan_svg import FONT, MONO, S, Sheet, f, sw_line, sw_rect, sx, sy, text, tw  # noqa: E402

# ============================================================================ flags / status
PRELIM = 'PRELIMINAR — a validar por ingeniero electricista (Código Eléctrico CR / NEC 2020)'
FLAG_ENG = 'EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED'
FLAG_SMOKER = 'SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED'
FLAG_DIM = 'DIMENSION TO VERIFY'
FLAG_SITE = 'VERIFY ON SITE'

# ============================================================================ reference values (NEC 2020, a verificar)
SQ3 = math.sqrt(3.0)
V_LN, V_LL = 120.0, 208.0               # sistema supuesto 120/208 V 3F 4H (VERIFY con el C.C.)
V_1PH_ALT = 240.0                        # alternativa 120/240 V 1F 3H
T220_56 = {1: 1.00, 2: 1.00, 3: 0.90, 4: 0.80, 5: 0.70}      # ≥6 unidades → 0.65
VA_M2_REST = 16.0                         # NEC 2020 Tabla 220.12: restaurantes 16 VA/m² (1.5 VA/pie²) — verificar
VA_REC = 180.0                            # NEC 220.14(I)
VA_SIGN = 1200.0                          # NEC 220.14(F) / 600.5(A)
STD_A = [15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200, 225, 250, 300, 350, 400]
BUS_A = [100, 125, 150, 200, 225, 400]
WIRE = [(20, '#12'), (30, '#10'), (40, '#8'), (55, '#6'), (70, '#4'), (85, '#3'), (100, '#2')]   # THHN Cu 75 °C (ref.)
HP_STD = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5]
FLC_3F_208 = {0.5: 2.4, 0.75: 3.5, 1.0: 4.6, 1.5: 6.6, 2.0: 7.5, 3.0: 10.6, 5.0: 16.7, 7.5: 24.2}   # NEC T430.250
FLC_1F_230 = {0.5: 4.9, 0.75: 6.9, 1.0: 8.0, 1.5: 10.0, 2.0: 12.0, 3.0: 17.0, 5.0: 28.0, 7.5: 40.0}  # NEC T430.248
DP_EXH, DP_MUA, ETA_FAN = 500.0, 375.0, 0.50    # Pa (≈2" y 1.5" c.a.) y eficiencia total ventilador+motor (supuestos)
GROWTH = 0.20                                    # reserva de crecimiento recomendada
PANEL_SPACES = [24, 30, 42, 54, 66, 84]            # tamaños usuales de tablero (espacios); ≥20 % libres
# luminarias (W por unidad; L-5 W/m) — mismas referencias que el cuadro de luminarias de A-201
W_LUM = {'L-1': 10, 'L-2': 12, 'L-3': 8, 'L-4': 6, 'L-5': 10, 'L-6': 60, 'L-8': 36, 'L-9': 20, 'EM': 5, 'RS': 3}

# equipo (layout key) → dato eléctrico típico (TBV)
EQ_ELEC = {
    'fridge_2d': dict(desc='Refrigerador 2 puertas', V=120, poles=1, va=840, conn='Toma dedicada 20 A', basis='reach-in 2P ≈1/2 HP · 7 A'),
    'freezer_1d': dict(desc='Congelador vertical', V=120, poles=1, va=720, conn='Toma dedicada 20 A', basis='1 puerta ≈1/2 HP · 6 A'),
    'mesa_fria': dict(desc='Mesa fría refrigerada', V=120, poles=1, va=480, conn='Toma dedicada 20 A', basis='180 cm ≈1/5 HP · 4 A'),
    'oven': dict(desc='Horno convección de mesa + recirc. UL 710B', V=208, poles=2, va=6000, conn='Toma 6-50R o conexión fija',
                 basis='≈6 kW (ficha)', sym='spec', note='Enclavamiento propio del equipo UL 710B (filtros / supresión integrada)'),
    'freidora_1': dict(desc='Freidoras H4 + H5 · encendido / control', V=120, poles=1, va=120, conn='Toma por freidora (vía KS-1)',
                       basis='≈1 A c/u si encendido electrónico', note='KS-1 abre con SUP-1 (NFPA 96 · corte de energía de equipos protegidos)'),
    'holding': dict(desc='Holding caliente', V=120, poles=1, va=1500, conn='Toma dedicada 20 A', basis='gabinete ½ altura ≈1.5 kW'),
    'smoker': dict(desc='Smoker · controles / ventilador de tiro (si aplica)', V=120, poles=1, va=720, conn='Toma dedicada 20 A',
                   basis='según ficha · 6 A', note='Solo si el smoker lo requiere · posición según fabricante (lejos del hogar)'),
    'pass': dict(desc='Pase C2 · lámparas de calor (L-7)', V=120, poles=1, va=500, conn='Conexión fija sobre la repisa',
                 basis='tira ≈60 cm · 500 W', sym='j', at='center', gfci=False),
    'barra': dict(desc='Enfriador bajo barra (cerveza / bebidas)', V=120, poles=1, va=600, conn='Toma dedicada 20 A', basis='≈5 A',
                  t=0.45, note='Venta de alcohol (licencia clase C): chopera / enfriador — ficha TBV'),
    'pos': dict(desc='POS + impresora de comandas', V=120, poles=1, va=500, conn='Toma dedicada · tierra aislada', basis='con UPS',
                group='IT', note='UPS ≥15 min · red de datos hasta RK-1'),
}
NO_ELEC = ('parrilla', 'cocina_4q', 'plancha')

# ============================================================================ colours
C_K = '#c2410c'        # equipos de cocina (NEC 220.56)
C_REC = '#1f4fa3'      # tomas generales
C_MOT = '#6d28d9'      # motores / ventilación
C_HVAC = '#4b5563'     # A/C (reserva)
C_CTRL = '#c1121f'     # control / seguridad / enclavamientos
C_IT = '#0f766e'       # POS / TI
C_SIGN = '#9a3412'
C_RED = '#b00020'
C_WS = '#0a7d3b'       # espacio de trabajo
C_TXT = '#262626'
LUM_COL = {'LUM-1': '#2e7d32', 'LUM-2': '#9a6700', 'LUM-3': '#be185d', 'LUM-4': '#0369a1'}
GROUP = {
    'K': ('Equipos de cocina', 'NEC 220.56', C_K),
    'M': ('Motores / ventilación', '220.50 · 430.24', C_MOT),
    'H': ('A/C (reserva)', '220.50 · 100 %', C_HVAC),
    'L': ('Alumbrado', '220.12 · 220.42', '#2e7d32'),
    'S': ('Rótulo exterior', '220.14(F) · 600.5', C_SIGN),
    'R': ('Tomas generales', '220.14(I) · 220.44', C_REC),
    'C': ('Control / seguridad', '100 % · continuo', C_CTRL),
    'IT': ('POS / TI', '100 % · continuo', C_IT),
    'X': ('Reserva (no sumada)', '—', '#8a8a85'),
}
GROUP_ORDER = ['K', 'M', 'H', 'L', 'S', 'R', 'C', 'IT', 'X']
GROUP_SHORT = {'K': 'Cocina · 220.56', 'M': 'Motor · 430.24', 'H': 'A/C · 100 %', 'L': 'Alumbrado · 220.12', 'S': 'Rótulo · 600.5',
               'R': 'Tomas · 220.44', 'C': 'Control · continuo', 'IT': 'POS/TI · continuo', 'X': 'Reserva · no suma'}
DIRV = {'N': (0.0, -1.0), 'S': (0.0, 1.0), 'E': (1.0, 0.0), 'W': (-1.0, 0.0)}
OPP = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}


# ============================================================================ helpers
def nrect(r):
    x0, y0, x1, y1 = r
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def ctr(r):
    x0, y0, x1, y1 = nrect(r)
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def edge_pt(r, side, t=0.5):
    x0, y0, x1, y1 = nrect(r)
    return {'N': (x0 + (x1 - x0) * t, y0), 'S': (x0 + (x1 - x0) * t, y1),
            'W': (x0, y0 + (y1 - y0) * t), 'E': (x1, y0 + (y1 - y0) * t)}[side]


def next_std(a, table=STD_A):
    for v in table:
        if v >= a - 1e-6:
            return v
    return table[-1]


def wire_for(a):
    for lim, w in WIRE:
        if a <= lim:
            return w
    return '#1/0'


def wrap(s, n):
    out, cur = [], ''
    for w in str(s or '').split():
        if cur and len(cur) + 1 + len(w) > n:
            out.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur:
        out.append(cur)
    return out


def fmt_kva(va):
    return f"{va / 1000:.2f}"


def halo(w=0.9):
    return f'paint-order="stroke" stroke="#ffffff" stroke-width="{w}" stroke-linejoin="round"'


def mline(x1, y1, x2, y2, c, w=0.25, dash=None, extra=''):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" stroke="{c}" stroke-width="{w}"{d} {extra}/>'


def mrect(x, y, w, h, fill, stroke, sw=0.3, dash=None, rx=0, extra=''):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    r = f' rx="{rx}"' if rx else ''
    return f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{r} {extra}/>'


# ============================================================================ symbols (sheet mm)
def sym_rec(x, y, col, n=(0, 1), gfci=False, r=1.15):
    """Duplex receptacle: circle + two parallel stubs along the wall normal; GFCI = room-side half filled."""
    nx, ny = n
    px, py = -ny, nx
    g = [f'<circle cx="{f(x)}" cy="{f(y)}" r="{r}" fill="#ffffff" stroke="{col}" stroke-width="0.32"/>']
    if gfci:
        a = math.atan2(ny, nx)
        a0, a1 = a - math.pi / 2, a + math.pi / 2
        x0, y0 = x + r * math.cos(a0), y + r * math.sin(a0)
        x1, y1 = x + r * math.cos(a1), y + r * math.sin(a1)
        g.append(f'<path d="M{f(x0)},{f(y0)} A{r},{r} 0 0 1 {f(x1)},{f(y1)} Z" fill="{col}"/>')
    for s_ in (-0.42, 0.42):
        g.append(mline(x + px * s_ - nx * 1.7, y + py * s_ - ny * 1.7, x + px * s_ + nx * 1.7, y + py * s_ + ny * 1.7,
                       col if not gfci else '#1b1b1b', 0.26))
    return ''.join(g)


def sym_spec(x, y, col, r=1.25):
    return (f'<circle cx="{f(x)}" cy="{f(y)}" r="{r}" fill="#ffffff" stroke="{col}" stroke-width="0.35"/>'
            f'<path d="M{f(x)},{f(y - 0.8)} L{f(x + 0.75)},{f(y + 0.55)} L{f(x - 0.75)},{f(y + 0.55)} Z" fill="{col}"/>')


def sym_j(x, y, col, r=1.2, t='J'):
    return (f'<circle cx="{f(x)}" cy="{f(y)}" r="{r}" fill="#ffffff" stroke="{col}" stroke-width="0.35"/>'
            + text(x, y + 0.5, t, 1.35, weight='800', fill=col))


def sym_motor(x, y, col, r=1.55):
    return (f'<circle cx="{f(x)}" cy="{f(y)}" r="{r}" fill="#ffffff" stroke="{col}" stroke-width="0.4"/>'
            + text(x, y + 0.6, 'M', 1.7, weight='800', fill=col))


def sym_box(x, y, w, h, t, col, fill='#ffffff', tcol=None, size=1.2):
    return (mrect(x - w / 2, y - h / 2, w, h, fill, col, 0.32)
            + text(x, y + size * 0.36, t, size, weight='800', fill=tcol or col))


def sym_em(x, y, col):
    return (mrect(x - 1.5, y - 0.8, 3.0, 1.6, '#ffffff', col, 0.3)
            + f'<circle cx="{f(x - 0.7)}" cy="{f(y)}" r="0.45" fill="{col}"/><circle cx="{f(x + 0.7)}" cy="{f(y)}" r="0.45" fill="{col}"/>')


def sym_rs(x, y, col):
    return (mrect(x - 1.6, y - 0.85, 3.2, 1.7, '#0a7d3b', col, 0.3)
            + text(x, y + 0.45, 'S', 1.2, weight='800', fill='#ffffff'))


def sym_panel(x0, y0, x1, y1, col='#111111'):
    """Panelboard: outline, half filled (sheet mm rect)."""
    w, h = x1 - x0, y1 - y0
    if w >= h:
        half = mrect(x0, y0 + h / 2, w, h / 2, col, 'none', 0)
    else:
        half = mrect(x0 + w / 2, y0, w / 2, h, col, 'none', 0)
    return mrect(x0, y0, w, h, '#ffffff', col, 0.4) + half


def sym_breaker(x, y, col, w=0.3):
    """Single-line breaker: small arc between two dots (vertical)."""
    return (f'<circle cx="{f(x)}" cy="{f(y - 1.2)}" r="0.3" fill="{col}"/><circle cx="{f(x)}" cy="{f(y + 1.2)}" r="0.3" fill="{col}"/>'
            f'<path d="M{f(x)},{f(y - 1.2)} A1.3,1.3 0 0 1 {f(x)},{f(y + 1.2)}" fill="none" stroke="{col}" stroke-width="{w}"/>')


# ============================================================================ geometry from data
def wall_union(ex, lay):
    g = [gg for _, gg in standing_existing_walls(ex, lay)] + [R(c['rect']) for c in ex.get('columns', [])]
    ops = [R(o['rect']) for o in lay.get('new_openings', []) if o.get('rect')]
    for w in lay.get('new_walls', []):
        gw = R(w['rect'])
        for o in ops:
            gw = gw.difference(o)
        g.append(gw)
    return unary_union(g)


def snap_to_wall(p, side, walls, max_d=0.35):
    """Move p outward (toward `side`) until it meets a wall face (≤ max_d); else keep p."""
    dx, dy = DIRV[side]
    for i in range(0, int(max_d * 100) + 1):
        q = (p[0] + dx * i / 100, p[1] + dy * i / 100)
        if walls.intersects(Point(q).buffer(0.006)):
            return q, True
    return p, False


def back_side(e, host=None):
    fr = e.get('front') or (host or {}).get('front')
    return OPP.get(fr)


def wall_point(e, side, walls, ts=None):
    """Point on the `side` edge of e, preferring positions that land on a wall (not on glazing)."""
    order = ts or [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8, 0.1, 0.9]
    first = None
    for t in order:
        p = edge_pt(e['rect'], side, t)
        q, hit = snap_to_wall(p, side, walls)
        if first is None:
            first = q
        if hit:
            return q
    return first


def zone_of(lay, p):
    pt = Point(p)
    best = None
    for z in lay.get('zones', []):
        poly = Polygon(z['poly'])
        if poly.buffer(0.02).contains(pt):
            best = z['id']
            if poly.contains(pt):
                return z['id']
    if best:
        return best
    d = sorted((Polygon(z['poly']).distance(pt), z['id']) for z in lay.get('zones', []))
    return d[0][1] if d and d[0][0] < 0.6 else '—'


def load_mech():
    p = os.path.join(ROOT, 'data', 'mech_calcs.json')
    try:
        return load_json(p) if os.path.exists(p) else {}
    except Exception:  # noqa: BLE001 — sibling file may be mid-write
        return {}


def fan_motor(q_ls, dp):
    """Required shaft power → next standard HP → FLC (208 V 3F, T430.250)."""
    kw_req = (q_ls / 1000.0) * dp / ETA_FAN / 1000.0
    hp = next((h for h in HP_STD if h * 0.746 >= kw_req), HP_STD[-1])
    return kw_req, hp, FLC_3F_208[hp], FLC_1F_230[hp]


# ============================================================================ calculation
def calc(ex, lay, val=None):
    E = {e['id']: e for e in lay.get('equipment', [])}
    mep = lay.get('mep', {}) or {}
    ls = lay.get('life_safety', {}) or {}
    mech = load_mech()
    walls = wall_union(ex, lay)
    prem = premises(ex)
    circuits = []

    def add(**c):
        c.setdefault('qty', 1)
        c.setdefault('pts', [])
        c.setdefault('sum', True)
        c.setdefault('tbv', True)
        c.setdefault('note', '')
        c.setdefault('cont', False)
        c.setdefault('motor', None)
        c['va'] = c.get('va_unit', 0) * c['qty'] if 'va' not in c else c['va']
        if 'zone' not in c:
            c['zone'] = ' · '.join(sorted({zone_of(lay, (p['at'])) for p in c['pts']})) if c['pts'] else '—'
        circuits.append(c)
        return c

    def pt(at, sym, n=(0, 1), tag=True, **kw):
        d = {'at': (round(at[0], 3), round(at[1], 3)), 'sym': sym, 'n': n, 'tag': tag}
        d.update(kw)
        return d

    def eq_point(e, spec):
        host = E.get(e.get('stack_with')) if e.get('stack_with') else None
        if spec.get('at') == 'center':
            return ctr(e['rect']), (0, 1)
        side = back_side(e, host)
        if side is None:
            return ctr(e['rect']), (0, 1)
        if host and side in ('N', 'S'):
            # stacked item: host edge, own centre along the edge
            hx0, hy0, hx1, hy1 = nrect(host['rect'])
            cx, _ = ctr(e['rect'])
            p0 = (cx, hy0 if side == 'N' else hy1)
            q, _ = snap_to_wall(p0, side, walls)
        elif host:
            hx0, hy0, hx1, hy1 = nrect(host['rect'])
            _, cy = ctr(e['rect'])
            q = (hx0 if side == 'W' else hx1, cy)
            q, _ = snap_to_wall(q, side, walls)
        elif spec.get('t') is not None:
            q, _ = snap_to_wall(edge_pt(e['rect'], side, spec['t']), side, walls)
        else:
            q = wall_point(e, side, walls)
        dx, dy = DIRV[side]
        return q, (-dx, -dy)

    # ---------------------------------------------------------------- kitchen equipment (NEC 220.56)
    wet = {'A', 'B', 'E', 'W', 'C'}
    done = set()
    for e in lay.get('equipment', []):
        k = e.get('key')
        if k not in EQ_ELEC or k in done:
            continue
        spec = EQ_ELEC[k]
        grp = spec.get('group', 'K')
        if k == 'freidora_1':
            fr = [x for x in lay['equipment'] if x.get('key') in ('freidora_1', 'freidora_2')]
            done.add('freidora_2')
            pts = []
            for x in fr:
                q, n = eq_point(x, spec)
                pts.append(pt(q, 'gfci', n, ref=x['id']))
            add(key='FRY', ref=' + '.join(x['id'] for x in fr), desc=spec['desc'], V=spec['V'], poles=spec['poles'],
                va_unit=spec['va'], qty=len(fr), group=grp, conn=spec['conn'], gfci=True, basis=spec['basis'],
                note=spec.get('note', ''), pts=pts, interlock='KS-1')
            continue
        q, n = eq_point(e, spec)
        z = zone_of(lay, q if spec.get('at') != 'center' else ctr(e['rect']))
        gf = spec.get('gfci', z in wet)
        sym = spec.get('sym') or ('gfci' if gf else 'rec')
        add(key=e['id'], ref=e['id'], desc=spec['desc'], V=spec['V'], poles=spec['poles'], va_unit=spec['va'], group=grp,
            conn=spec['conn'] + (' GFCI' if gf and 'GFCI' not in spec['conn'] and sym != 'j' else ''), gfci=gf and sym != 'j',
            basis=spec['basis'], note=spec.get('note', ''), pts=[pt(q, sym, n, ref=e['id'])], zone=z)
    # bar counter receptacles (blender / small drinks equipment) on the bar staff side
    barra = next((e for e in lay['equipment'] if e.get('key') == 'barra'), None)
    if barra:
        side = back_side(barra)
        q, _ = snap_to_wall(edge_pt(barra['rect'], side, 0.85), side, walls)
        dx, dy = DIRV[side]
        add(key='BAR-TC', ref=barra['id'], desc='Tomas de mostrador de barra (licuadora / batidora)', V=120, poles=1, va_unit=1500,
            group='K', conn='2 tomas dobles GFCI sobre mesada', gfci=True, basis='licuadora comercial ≈1.5 kVA',
            pts=[pt(q, 'gfci', (-dx, -dy), ref=barra['id'])], note='Cócteles / bebidas (venta de alcohol)')
    # water heaters (mech_calcs → M-101)
    wh = (mech.get('water_heaters') or {})
    ca1 = wh.get('CA-1') or {'kW': 6.0, 'volume_L': 150}
    ca2 = wh.get('CA-2') or {'kW': 1.5, 'volume_L': 15}
    w3 = next((e for e in lay['equipment'] if e.get('key') == 'mop_sink'), None)
    ca1_at = ca1.get('at') or (ctr(w3['rect']) if w3 else None)
    ca2_at = ca2.get('at') or (edge_pt(barra['rect'], back_side(barra), 0.25) if barra else None)
    add(key='CA-1', ref='CA-1', desc=f"Termotanque CA-1 {ca1.get('volume_L', 150):.0f} L (M-101)", V=208, poles=2,
        va_unit=ca1.get('kW', 6.0) * 1000, group='K', conn='Conexión fija + seccionador', gfci=False, cont=True,
        basis=f"{ca1.get('kW', 6.0):.1f} kW a 208 V", note='NEC 422.13: carga continua (125 %). Resistencias para 208 V (a 240 V nominal rinde 75 %)',
        pts=[pt(ca1_at, 'j', (0, 1), ref='CA-1', t='CA')] if ca1_at else [])
    add(key='CA-2', ref='CA-2', desc=f"Calentador bajo barra CA-2 {ca2.get('volume_L', 15):.0f} L", V=120, poles=1,
        va_unit=ca2.get('kW', 1.5) * 1000, group='K', conn='Conexión fija bajo barra', gfci=False, cont=True,
        basis=f"{ca2.get('kW', 1.5):.1f} kW", note='NEC 422.13: carga continua', pts=[pt(ca2_at, 'j', (0, 1), ref='CA-2', t='CA')] if ca2_at else [])

    # ---------------------------------------------------------------- motors (exhaust / make-up air)
    ext_mech = {x['id']: x for x in ((mech.get('exhaust') or {}).get('systems') or [])}
    q_def = {'EXT-1': 1068.0, 'EXT-2': 1320.0}
    motors = []
    for x in mep.get('exhaust', []):
        if not x.get('fan') or 'chimenea' in (x.get('kind') or ''):
            continue
        q = (ext_mech.get(x['id']) or {}).get('Q_Ls') or q_def.get(x['id'], 1200.0)
        kw_req, hp, flc3, flc1 = fan_motor(q, DP_EXH)
        solid = 'sólido' in (x.get('kind') or '') or 'solido' in (x.get('kind') or '')
        note = ('No se apaga con brasas en H1: selector con llave + rótulo; sigue con SUP-2' if solid else
                'Sigue operando con SUP-1 salvo que el listado indique otra cosa; prueba de flujo → permiso de VS')
        m = add(key=x['id'], ref=x['id'], desc=f"Ventilador {x['id']} · {x.get('serves')} · {x.get('kind')} · en cubierta", V=208, poles=3,
                va=SQ3 * V_LL * flc3, group='M', conn='Arrancador CC-1 + seccionador local', gfci=False,
                basis=f"{q:.0f} L/s · {hp:g} HP · FLC {flc3} A", note=note, motor={'hp': hp, 'flc': flc3, 'flc1': flc1, 'q': q,
                                                                                     'kw_req': kw_req, 'dp': DP_EXH},
                pts=[pt(tuple(x['collar']), 'motor', (0, 1), ref=x['id'], tag=False)] if x.get('collar') else [])
        m['zone'] = 'cubierta'
        motors.append(m)
    mua = mep.get('makeup_air') or {}
    if mua:
        q = ((mech.get('makeup_air') or {}).get('design_Q_Ls')) or 0.85 * sum(m['motor']['q'] for m in motors)
        kw_req, hp, flc3, flc1 = fan_motor(q, DP_MUA)
        dif = [tuple(p) for p in mua.get('diffusers', [])]
        at = tuple((mech.get('makeup_air') or {}).get('riser') or ()) or None      # same point as the M-102 riser
        if at is None and dif:
            # symbol on the diffuser line, dodging emergency lights / detectors drawn at the same place
            busy = [tuple(p) for p in ls.get('emergency_lights', [])] + [tuple(p) for p in ls.get('smoke_detectors', [])]
            a_, b_ = dif[0], dif[-1]
            for t in (0.5, 0.35, 0.65, 0.2, 0.8):
                qq = (a_[0] + (b_[0] - a_[0]) * t, a_[1] + (b_[1] - a_[1]) * t)
                if all(math.dist(qq, p) >= 0.3 for p in busy):
                    at = qq
                    break
            at = at or ((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2)
        m = add(key=mua.get('id', 'AR-1'), ref=mua.get('id', 'AR-1'), desc=f"Ventilador de reposición {mua.get('id', 'AR-1')} · en cubierta (sin templar)",
                V=208, poles=3, va=SQ3 * V_LL * flc3, group='M', conn='Arrancador CC-1 + seccionador local', gfci=False,
                basis=f"{q:.0f} L/s · {hp:g} HP · FLC {flc3} A",
                note='Arranca con EXT-1 / EXT-2 (IMC 508.1.1); con SUP-1/2 según listado — TO BE ENGINEERED',
                motor={'hp': hp, 'flc': flc3, 'flc1': flc1, 'q': q, 'kw_req': kw_req, 'dp': DP_MUA},
                pts=[pt(at, 'motor', (0, 1), ref=mua.get('id', 'AR-1'), tag=False)] if at else [])
        m['zone'] = 'cubierta'
        motors.append(m)
    # A/C reserve (dining + bar) — cooling ≈250 W/m² (restaurant, reference), COP ≈3.0
    zc = {z['id']: Polygon(z['poly']).intersection(prem).area for z in lay.get('zones', [])}
    a_cool = zc.get('D', 0) + zc.get('C', 0)
    kw_cool = a_cool * 0.25
    tr = kw_cool / 3.517
    va_ac = kw_cool / 3.0 / 0.9 * 1000
    add(key='AC-R', ref='A/C', desc=f"A/C salón + barra (reserva ≈{math.ceil(tr * 2) / 2:.1f} TR)", V=208, poles=3, va=va_ac, group='H',
        conn='Según placa (MCA / MOP)', gfci=False, zone='D · C',
        basis=f"{a_cool:.0f} m² × 250 W/m² · COP 3", note='Tipo y capacidad: ingeniero mecánico — la cocina no se climatiza (reposición AR-1)')

    # ---------------------------------------------------------------- lighting (A-201 luminaires) + emergency
    L = None
    try:
        from sheets.s201_cielos import ceiling_layout
        L = ceiling_layout(ex, lay, val)
    except Exception as err:  # noqa: BLE001
        print('WARNING: s201 ceiling_layout unavailable:', err)
    lum_def = {'LUM-1': ('Alumbrado salón (L-1 rieles · L-2 · L-4 apliques) + EM/RS', 'Atenuador en barra'),
               'LUM-2': ('Alumbrado barra + decor (L-2 · L-3 · L-5 · rótulo L-6) + EM', 'Atenuador / reloj en barra'),
               'LUM-3': ('Alumbrado cocina caliente + BBQ (L-8 IP65 · L-9 campanas) + EM', 'Interruptor en cocina'),
               'LUM-4': ('Alumbrado lavado + cold prep (L-8 IP65) + EM/RS', 'Interruptor en el ala')}
    zone_circ = {'D': 'LUM-1', 'C': 'LUM-2', 'B': 'LUM-3', 'E': 'LUM-3', 'W': 'LUM-4', 'A': 'LUM-4'}
    lum = {k: {'va': 0.0, 'n': 0, 'items': []} for k in lum_def}
    lights_out = []
    if L:
        for lt in L['lights']:
            t = lt['type']
            if t == 'L-7':            # pass heat lamps: counted with the pass (C2)
                continue
            p = lt.get('at') or ctr(lt['rect'])
            z = zone_of(lay, p)
            circ = 'LUM-2' if t in ('L-3', 'L-5', 'L-6') else ('LUM-3' if t == 'L-9' else zone_circ.get(z, 'LUM-1'))
            w = W_LUM.get(t, 10) * (lt.get('len', 1.0) if t == 'L-5' else 1.0)
            lum[circ]['va'] += w
            lum[circ]['n'] += 1
            lights_out.append({'type': t, 'at': (round(p[0], 3), round(p[1], 3)), 'rect': lt.get('rect'), 'along': lt.get('along'),
                               'circuit': circ, 'W': round(w, 1)})
    else:  # fallback: area × W/m²
        for zid, circ in zone_circ.items():
            lum[circ]['va'] += zc.get(zid, 0) * (8.0 if zid in ('D', 'C') else 11.0)
    em_out = []
    for p in ls.get('emergency_lights', []):
        circ = zone_circ.get(zone_of(lay, p), 'LUM-1')
        lum[circ]['va'] += W_LUM['EM']
        lum[circ]['n'] += 1
        em_out.append({'kind': 'EM', 'at': tuple(p), 'circuit': circ})
    for rs in ls.get('exit_signs', []):
        circ = zone_circ.get(zone_of(lay, rs['at']), 'LUM-1')
        lum[circ]['va'] += W_LUM['RS']
        lum[circ]['n'] += 1
        em_out.append({'kind': 'RS', 'at': tuple(rs['at']), 'circuit': circ, 'id': rs.get('id')})
    for k, (desc, ctl) in lum_def.items():
        add(key=k, ref=k, desc=desc, V=120, poles=1, va=lum[k]['va'], qty=lum[k]['n'] or 1, group='L', conn=ctl, gfci=False,
            cont=True, basis='A-201 · W de referencia', note='EM / RS en el mismo circuito, antes del interruptor (NEC 700.12, equipos unitarios — verificar inciso)',
            zone={'LUM-1': 'D', 'LUM-2': 'C · D', 'LUM-3': 'B · E', 'LUM-4': 'W · A'}[k], lum=True)
    # exterior sign (storefront, beside the entrance)
    dent = next((d for d in ex.get('doors', []) if d['id'] == 'D-ENT'), None)
    sign_at = None
    if dent:
        (ox0, oy0, ox1, oy1) = dent['opening']
        fac = max(ox0, ox1)
        # on the storefront, just north of the door leaves (clear of the entrance label / exit sign)
        sign_at = (fac + 0.30, min(oy0, oy1) - 0.40)
    add(key='ROT-EXT', ref='RÓT.', desc='Rótulo exterior de fachada (reglamento del condominio)', V=120, poles=1, va=VA_SIGN, group='S',
        conn='Salida de rótulo + reloj / fotocelda', gfci=False, cont=True, zone='fachada', basis='NEC 220.14(F): 1200 VA mín.',
        note='NEC 600.5(A): circuito de 20 A exclusivo · diseño y permiso según reglamento del C.C. (VERIFY)',
        pts=[pt(sign_at, 'j', (-1, 0), ref='RÓT', t='R')] if sign_at else [])

    # ---------------------------------------------------------------- general receptacles (180 VA c/u)
    k1 = E.get('K1')
    w4 = next((e for e in lay['equipment'] if e.get('key') == 'mesa_opt'), None)
    a4 = next((e for e in lay['equipment'] if e.get('key') == 'mesa_2'), None)
    rec_k = []
    if k1:
        # side of K1 away from the oven K2 (the oven occupies the other end)
        k2 = E.get('K2')
        kx0, _, kx1, _ = nrect(k1['rect'])
        side = 'W' if (k2 and ctr(k2['rect'])[0] > (kx0 + kx1) / 2) else 'E'
        q, _ = snap_to_wall(edge_pt(k1['rect'], side, 0.5), side, walls)
        rec_k.append(pt(q, 'gfci', (-DIRV[side][0], -DIRV[side][1]), ref='K1'))
    if w4:
        sd = back_side(w4)
        q = wall_point(w4, sd, walls)
        rec_k.append(pt(q, 'gfci', (-DIRV[sd][0], -DIRV[sd][1]), ref='W4'))
    add(key='TG-1', ref='K1 · W4', desc='Tomas generales cocina (mesada K1) + lavado (W4)', V=120, poles=1, va_unit=VA_REC, qty=len(rec_k),
        group='R', conn='Tomas dobles GFCI h 1.10 sobre mesada', gfci=True, basis='180 VA c/u', pts=rec_k, tbv=False,
        note='A ≥0.30 m de piletas; tapa a prueba de salpicaduras')
    rec_a = []
    if a4:
        sd = back_side(a4)
        q = wall_point(a4, sd, walls)
        rec_a.append(pt(q, 'gfci', (-DIRV[sd][0], -DIRV[sd][1]), ref='A4'))
    add(key='TG-2', ref='A4', desc='Tomas generales cold prep (mesada A4: procesador / selladora)', V=120, poles=1, va_unit=VA_REC,
        qty=max(1, len(rec_a)), group='R', conn='Tomas dobles GFCI h 1.10 sobre mesada', gfci=True, basis='180 VA c/u', pts=rec_a, tbv=False)
    rec_d = []
    te = (mep.get('panel') or {})
    te_r = nrect(te['rect']) if te.get('rect') else None
    cc_r = (te_r[2] + 0.02, te_r[1], te_r[2] + 0.42, te_r[3]) if te_r else None
    bqn = next((b for b in lay.get('banquettes', []) if b.get('back') == 'N'), None)
    bqs = next((b for b in lay.get('banquettes', []) if b.get('back') == 'S'), None)
    if cc_r and bqn:
        xm = (cc_r[2] + nrect(bqn['rect'])[0]) / 2
        q, _ = snap_to_wall((xm, nrect(bqn['rect'])[3]), 'N', walls, max_d=0.8)
        rec_d.append(pt(q, 'rec', (0, 1), ref='D'))
    if bqs:
        bx1 = nrect(bqs['rect'])[2]
        xm = (bx1 + prem.bounds[2]) / 2
        q, _ = snap_to_wall((xm, nrect(bqs['rect'])[1]), 'S', walls, max_d=0.8)
        rec_d.append(pt(q, 'rec', (0, -1), ref='D'))
    d2 = next((e for e in lay['equipment'] if e.get('key') == 'delivery_staging'), None)
    if d2:
        sd = back_side(d2)
        q, _ = snap_to_wall(edge_pt(d2['rect'], sd, 0.5), sd, walls)
        rec_d.append(pt(q, 'rec', (-DIRV[sd][0], -DIRV[sd][1]), ref=d2['id']))
    add(key='TG-3', ref='D · D2', desc='Tomas generales salón (limpieza) + recepción / delivery D2', V=120, poles=1, va_unit=VA_REC,
        qty=len(rec_d), group='R', conn='Tomas dobles h 0.40 · D2 sobre mueble', gfci=False, basis='180 VA c/u', pts=rec_d, tbv=False)

    # ---------------------------------------------------------------- control / safety devices
    gm = mep.get('gas', {}) or {}
    wn = next((w for w in ex.get('walls', []) if w['id'] == 'EW-N1'), None)
    north_y = (max(wn['rect'][1], wn['rect'][3]) if wn else 0.116) + 0.10
    k2 = E.get('K2')
    xs_valves = [p[0] for p in (gm.get('solenoid'), gm.get('main_valve'), gm.get('entry')) if p]
    dg = ((nrect(k1['rect'])[2] + min(xs_valves)) / 2, north_y) if (k1 and xs_valves) else None
    pull = ls.get('pull_station') or {}
    pm_ids = pull.get('ids') or (['PM-1'] if pull else [])
    hd2 = E.get('HD-2')
    n_s = 2 if (hd2 and len(pm_ids) > 1) else 1
    sups = []
    if k1:
        kx0 = nrect(k1['rect'])[0]
        kx1 = nrect(k2['rect'])[0] if k2 else nrect(k1['rect'])[2]
        for i in range(n_s):
            sups.append((f'SUP-{i + 1}', (kx0 + (kx1 - kx0) * (i + 0.5) / n_s, north_y)))
    s2 = next((e for e in lay['equipment'] if e.get('key') == 'holding'), None)
    s3 = next((e for e in lay['equipment'] if e.get('key') == 'fuel_storage'), None)
    dco = None
    if s2 and s3:
        sd = back_side(s2)
        y_ = (nrect(s2['rect'])[3] + nrect(s3['rect'])[1]) / 2
        dco, _ = snap_to_wall((nrect(s2['rect'])[0], y_), sd, walls)
    ctrl_pts = [pt(p, 'sup', (0, 1), ref=sid, tag=False, t=sid) for sid, p in sups]
    if dg:
        ctrl_pts.append(pt(dg, 'dev', (0, 1), ref='DG-1', t='DG', tag=False))
    if dco:
        ctrl_pts.append(pt(dco, 'dev', (1, 0), ref='DCO-1', t='CO', tag=False))
    add(key='CT-SEG', ref='SUP·DG·CO', desc='SUP-1/SUP-2 (liberación / alarma) + DG-1 gas + DCO-1 CO',
        V=120, poles=1, va=150, group='C', conn='Exclusivo · interruptor con traba (rojo)', gfci=False, cont=True,
        basis='≈150 VA', note='NFPA 72 / listado del sistema; con respaldo de batería', pts=ctrl_pts)
    vs = gm.get('solenoid')
    add(key='CT-CC1', ref='CC-1 · VS', desc='CC-1 control de campanas + VS solenoide N.C. (rearme manual) + KS-1',
        V=120, poles=1, va=200, group='C', conn='Circuito exclusivo', gfci=False, cont=True, basis='≈200 VA',
        note='Lógica en la matriz causa–efecto', pts=[pt(tuple(vs), 'dev', (0, 1), ref='VS', t='VS', tag=False)] if vs else [])
    add(key='IT-RK', ref='RK-1', desc='RK-1 comunicaciones · Wi-Fi · audio · CCTV (mural junto a TE-1)', V=120, poles=1, va=400, group='IT',
        conn='Toma dedicada h ≥2.10 · tierra aislada', gfci=False, cont=True, basis='≈400 VA', zone='C')

    # ---------------------------------------------------------------- spares (not added to the demand)
    add(key='R-EXT3', ref='EXT-3', desc='Reserva: campana + ventilador del smoker (si Bomberos lo exige)', V=208, poles=3,
        va=SQ3 * V_LL * FLC_3F_208[1.5], group='X', conn='Espacio de reserva', gfci=False, sum=False,
        basis='≈1192 L/s · 1.5 HP', note=FLAG_SMOKER, zone='—')
    add(key='R-SMK', ref='S1 alt.', desc='Reserva: smoker eléctrico / pellet listado (alternativa EXT-3)', V=208, poles=2,
        va=6000, group='X', conn='Espacio de reserva', gfci=False, sum=False, basis='≈6 kW TBV', note='Si reemplaza al smoker de leña', zone='E')

    # ---------------------------------------------------------------- per-circuit protection
    for c in circuits:
        if c['poles'] == 3:
            i_ = c['va'] / (SQ3 * c['V'])
        else:
            i_ = c['va'] / c['V']
        c['I'] = i_
        if c.get('motor'):
            flc = c['motor']['flc']
            brk = max(15, next_std(flc * 1.75))          # arranque: ≈175 % FLC (tope 250 %, NEC 430.52 T430.52)
            brk = min(brk, max(15, next_std(flc * 2.5)))
        else:
            lo = 20 if (c['group'] in ('K', 'R', 'L', 'S', 'IT') and c['V'] == 120) else 15
            brk = max(lo, next_std(i_ * 1.25))
        c['brk'] = brk
        c['wire'] = wire_for(brk)

    # ---------------------------------------------------------------- panel TE-1 (42 spaces, 120/208 V 3F) — phase balance
    poles_needed = sum(c['poles'] for c in circuits)
    spaces = next((n_ for n_ in PANEL_SPACES if n_ >= poles_needed * 1.2), PANEL_SPACES[-1])
    rows = spaces // 2
    occ = {}
    phase = [0.0, 0.0, 0.0]
    # table order (group, then as listed); each circuit takes one of the first free positions, choosing the one that
    # keeps the phases most balanced → readable, mostly sequential numbering
    order = sorted(circuits, key=lambda c: (GROUP_ORDER.index(c['group']), circuits.index(c)))
    for c in order:
        feas = []
        for side in (0, 1):
            for r0 in range(rows - c['poles'] + 1):
                rs = list(range(r0, r0 + c['poles']))
                if not any((side, r) in occ for r in rs):
                    feas.append((2 * r0 + 1 + side, side, rs))
        feas.sort()
        best = None
        for slot0, side, rs in feas[:6]:
            ph = [r % 3 for r in rs]
            trial = phase[:]
            if c['sum']:
                for p_ in ph:
                    trial[p_] += c['va'] / c['poles']
            cand = (round(max(trial) / 250.0), slot0)
            if best is None or cand < best[0]:
                best = (cand, side, rs, ph, trial)
        _, side, rs, ph, trial = best
        for r in rs:
            occ[(side, r)] = c['key']
        phase = trial
        c['slots'] = [2 * r + 1 + side for r in rs]
        c['phases'] = ['ABC'[p_] for p_ in ph]
        c['circ'] = '-'.join(str(s_) for s_ in c['slots'])
    used = len(occ)

    # ---------------------------------------------------------------- demand (NEC 2020 art. 220)
    area = prem.area
    sm = [c for c in circuits if c['sum']]
    light_conn = sum(c['va'] for c in sm if c['group'] == 'L')
    light_nec = VA_M2_REST * area
    light_dem = max(light_conn, light_nec)
    sign = sum(max(VA_SIGN, c['va']) for c in sm if c['group'] == 'S')
    n_rec = sum(c['qty'] for c in sm if c['group'] == 'R')
    rec = VA_REC * n_rec
    rec_dem = min(rec, 10000) + 0.5 * max(0.0, rec - 10000)
    kit_units = []
    for c in sm:
        if c['group'] == 'K':
            kit_units += [c['va'] / c['qty']] * c['qty']
    n_k = len(kit_units)
    fk = T220_56.get(n_k, 0.65) if n_k else 1.0
    kit_sum = sum(kit_units)
    two = sum(sorted(kit_units)[-2:])
    kit_dem = max(kit_sum * fk, two)
    mot = [c['va'] for c in sm if c['group'] == 'M']
    mot_dem = sum(mot) + 0.25 * (max(mot) if mot else 0)
    hvac = sum(c['va'] for c in sm if c['group'] == 'H')
    ctrl = sum(c['va'] for c in sm if c['group'] in ('C', 'IT'))
    total = light_dem + sign + rec_dem + kit_dem + mot_dem + hvac + ctrl
    wh_va = sum(c['va'] for c in sm if c['key'] in ('CA-1', 'CA-2'))
    cont_adder = 0.25 * (light_dem + sign + ctrl + wh_va)
    design = total + cont_adder
    i3 = design / (SQ3 * V_LL)
    i1 = design / V_1PH_ALT
    i3g, i1g = i3 * (1 + GROWTH), i1 * (1 + GROWTH)
    main3 = next_std(i3g)
    main1 = next_std(i1g)
    bus3 = next_std(max(main3, 150), BUS_A)
    connected = sum(c['va'] for c in sm)
    demand = {
        'area_m2': round(area, 1),
        'lighting': {'connected_VA': round(light_conn), 'nec_unit_VA_m2': VA_M2_REST, 'nec_min_VA': round(light_nec), 'demand_VA': round(light_dem),
                     'basis': 'NEC 2020 Tabla 220.12 (restaurantes 16 VA/m²) vs. conectado A-201 → el mayor; 220.42 al 100 %'},
        'sign': {'demand_VA': round(sign), 'basis': 'NEC 220.14(F) / 600.5(A): ≥1200 VA'},
        'receptacles': {'count': n_rec, 'VA': round(rec), 'demand_VA': round(rec_dem), 'basis': 'NEC 220.14(I) 180 VA c/u · 220.44 (10 kVA al 100 %, resto 50 %)'},
        'kitchen': {'units': n_k, 'connected_VA': round(kit_sum), 'factor': fk, 'two_largest_VA': round(two), 'demand_VA': round(kit_dem),
                    'basis': 'NEC 2020 220.56 / Tabla 220.56 (≥6 unidades 65 %; nunca menor que la suma de las 2 mayores)'},
        'motors': {'connected_VA': round(sum(mot)), 'largest_VA': round(max(mot) if mot else 0), 'demand_VA': round(mot_dem),
                   'basis': 'NEC 220.50 / 430.24: 100 % + 25 % del motor mayor'},
        'hvac_reserve': {'demand_VA': round(hvac), 'basis': 'Reserva A/C 100 % (220.50 / 440) — a definir por ingeniero mecánico'},
        'control_it': {'demand_VA': round(ctrl), 'basis': '100 %'},
        'total_demand_VA': round(total),
        'continuous_adder_VA': round(cont_adder),
        'continuous_basis': '25 % adicional sobre cargas continuas (alumbrado, rótulo, control/TI, calentadores 422.13) — NEC 215.3 / 230.42',
        'design_VA': round(design),
        'connected_total_VA': round(connected),
        'I_3F_208': round(i3, 1), 'I_1F_240': round(i1, 1),
        'growth_pct': GROWTH * 100,
        'I_3F_208_growth': round(i3g, 1), 'I_1F_240_growth': round(i1g, 1),
        'suggested': {
            'system': '120/208 V · 3F · 4H + T (VERIFY con la administración / empresa distribuidora)',
            'main_A': main3, 'bus_A': bus3, 'spaces': spaces, 'spaces_used': used,
            'alt_1F': f'120/240 V · 1F · 3H + T: principal {main1} A (menos recomendable: motores y equipos de 208 V)',
            'alt_1F_main_A': main1,
        },
        'phase_connected_VA': {'A': round(phase[0]), 'B': round(phase[1]), 'C': round(phase[2])},
        'phase_imbalance_pct': round((max(phase) - min(phase)) / (sum(phase) / 3) * 100, 1) if sum(phase) else 0,
    }
    # ---------------------------------------------------------------- TE-1 working space (NEC 110.26)
    ws = None
    ws_check = {}
    if te_r:
        x0 = min(te_r[0], cc_r[0])
        x1 = max(te_r[2], cc_r[2])
        if x1 - x0 < 0.762:
            xm = (x0 + x1) / 2
            x0, x1 = xm - 0.381, xm + 0.381
        ws = (round(x0, 3), round(te_r[3], 3), round(x1, 3), round(te_r[3] + 0.90, 3))
        _, obs = blocking_obstacles(ex, lay, include_items=True)
        hit = R(ws).intersection(obs).area
        prem_ok = prem.buffer(0.005).contains(R(ws))
        ws_check = {'rect': ws, 'depth_m': 0.90, 'width_m': round(x1 - x0, 3), 'height_m': 2.0, 'obstruction_m2': round(hit, 4),
                    'inside_premises': bool(prem_ok), 'clear': bool(hit < 1e-4 and prem_ok),
                    'basis': 'NEC 2020 110.26(A): fondo 0.90 m (0–150 V a tierra, condición 1) · ancho ≥0.762 m o el del equipo · alto 2.0 m; 110.26(E) espacio dedicado'}

    return {
        'circuits': circuits, 'demand': demand, 'lights': lights_out, 'em': em_out, 'L': L, 'panel': te, 'te_rect': te_r, 'cc_rect': cc_r,
        'ws': ws, 'ws_check': ws_check, 'sups': sups, 'dg': dg, 'dco': dco, 'vs': vs, 'motors': motors, 'mep': mep, 'mech': bool(mech),
        'sign_at': sign_at, 'no_elec': [e['id'] for e in lay['equipment'] if e.get('key') in NO_ELEC],
    }


# ============================================================================ drawing
class Occ:
    """Very small collision book-keeping for tags (sheet mm boxes)."""

    def __init__(self):
        self.boxes = []

    def add(self, b):
        self.boxes.append(b)

    def hits(self, b, pad=0.25):
        x0, y0, x1, y1 = b
        n = 0
        for (a0, b0, a1, b1) in self.boxes:
            if x0 < a1 + pad and x1 > a0 - pad and y0 < b1 + pad and y1 > b0 - pad:
                n += 1
        return n


def gcol(c):
    return GROUP[c['group']][2] if not c.get('lum') else LUM_COL.get(c['key'], '#2e7d32')


def draw_plan(s, res, lay, ex):
    g = []
    # ---- GFCI areas (kitchen, BBQ, washing, cold prep, bar with sink): light tint
    prem = premises(ex)
    wet = unary_union([Polygon(z['poly']) for z in lay.get('zones', []) if z['id'] in ('A', 'B', 'E', 'W', 'C')]).intersection(prem)
    g.append('<defs><pattern id="e-gfci" patternUnits="userSpaceOnUse" width="2.0" height="2.0" patternTransform="rotate(45)">'
             '<rect width="2.0" height="2.0" fill="#e8f1fc"/><line x1="0" y1="0" x2="0" y2="2.0" stroke="#b9d0ee" stroke-width="0.25"/></pattern>'
             '<pattern id="e-ws" patternUnits="userSpaceOnUse" width="1.6" height="1.6" patternTransform="rotate(-45)">'
             '<rect width="1.6" height="1.6" fill="#eaf7ee"/><line x1="0" y1="0" x2="0" y2="1.6" stroke="#8fcca2" stroke-width="0.3"/></pattern></defs>')
    for gg in (getattr(wet, 'geoms', None) or [wet]):
        if gg.is_empty or gg.geom_type != 'Polygon':
            continue
        pts = ' '.join(f"{f(sx(x))},{f(sy(y))}" for x, y in gg.exterior.coords)
        g.append(f'<polygon points="{pts}" fill="url(#e-gfci)" fill-opacity="0.85" stroke="#6f9bd6" stroke-width="0.3" stroke-dasharray="1.2 0.8"/>')
    s.add('<g id="gfci-areas">' + ''.join(g) + '</g>')


def _sym_box(p):
    """Sheet-mm bounding box of a plan symbol."""
    x, y = sx(p['at'][0]), sy(p['at'][1])
    r = {'motor': 1.8, 'sup': 1.4, 'dev': 1.55}.get(p['sym'], 1.45)
    return (x - r, y - r, x + r, y + r)


def door_label_boxes(lay):
    """Boxes of the door labels drawn by Sheet.layer_new (same placement rule)."""
    out = []
    for o in lay.get('new_openings', []):
        if not o.get('rect') or not o.get('label'):
            continue
        x0, y0, x1, y1 = o['rect']
        lx, ly = sx((x0 + x1) / 2), sy((y0 + y1) / 2)
        t_ = f"{o['label']} · {o.get('width', 0.9):.2f}"
        wv = tw(t_, 2.0)
        if o.get('type') == 'double_acting_door':
            cx, cy = lx + 7.5, ly + 0.8
        else:
            cx, cy = lx, ly + 5.2
        out.append((cx - wv / 2, cy - 2.0, cx + wv / 2, cy + 0.6))
    return out


def draw_overlay(s, res, lay, ex):
    """Everything electrical on top of the (faint) architecture."""
    occ = Occ()       # hard obstacles (symbols, labels)
    soft = Occ()      # luminaires (tags may sit on them but prefer not)
    for b in door_label_boxes(lay):
        occ.add(b)
    # 'ACCESO' label drawn by Sheet.layer_existing next to the main door (rotated text)
    ax_, ay_ = sx(16.62), sy(2.64)
    occ.add((ax_ - 1.8, ay_ - tw('ACCESO', 2.2) / 2, ax_ + 1.0, ay_ + tw('ACCESO', 2.2) / 2))
    all_pts = [p for c in res['circuits'] for p in c['pts']]
    for p in all_pts:
        occ.add(_sym_box(p))
    for d in res['em']:
        x, y = sx(d['at'][0]), sy(d['at'][1])
        occ.add((x - 1.7, y - 1.0, x + 1.7, y + 1.0))
    te_r, cc_r, ws = res['te_rect'], res['cc_rect'], res['ws']
    for r_ in (te_r, cc_r):
        if r_:
            occ.add((sx(r_[0]), sy(r_[1]) - 0.5, sx(r_[2]), sy(r_[3]) + 3.2))
    if ws:
        x0, y0, x1, y1 = ws
        wl = tw('ESPACIO DE TRABAJO 0.90 × 1.02 · h 2.00', 1.35) * 1.08
        occ.add((sx(x0), sy(y1) + 0.6, sx(x0) + wl, sy(y1) + 4.9))
    for lt in res['lights']:
        x, y = sx(lt['at'][0]), sy(lt['at'][1])
        if lt['type'] == 'L-8':
            along = lt.get('along') or 'x'
            hw, hh = (12.0, 1.2) if along in ('x', 'h', 'X') else (1.2, 12.0)
            soft.add((x - hw, y - hh, x + hw, y + hh))
        else:
            soft.add((x - 1.0, y - 1.0, x + 1.0, y + 1.0))

    def cost(b, pad=0.25):
        return occ.hits(b, pad) * 10 + soft.hits(b, 0.1) * 2

    # ---- equipment id tags (grey) — placed inside each rect, dodging the electrical symbols
    g = []
    for e in lay.get('equipment', []):
        if e.get('overhead'):
            continue
        if e.get('stack_with') and e.get('key') not in EQ_ELEC:
            continue
        x0, y0, x1, y1 = nrect(e['rect'])
        tag = e.get('tag', e['id'])
        size = 1.5 if not e.get('stack_with') else 1.35
        wv, hv = tw(tag, size) + 0.4, size + 0.2
        best = None
        for fx, fy in ((0.5, 0.5), (0.5, 0.3), (0.5, 0.7), (0.3, 0.5), (0.7, 0.5), (0.3, 0.3), (0.7, 0.7), (0.3, 0.7), (0.7, 0.3)):
            cx, cy = sx(x0 + (x1 - x0) * fx), sy(y0 + (y1 - y0) * fy)
            b = (cx - wv / 2, cy - hv / 2, cx + wv / 2, cy + hv / 2)
            sc = occ.hits(b, 0.7) * 10 + soft.hits(b, 0.1) * 0.6 + abs(fx - 0.5) + abs(fy - 0.5)
            if best is None or sc < best[0]:
                best = (sc, cx, cy, b)
        _, cx, cy, b = best
        occ.add(b)
        g.append(text(cx, cy + size * 0.36, tag, size, weight='700', fill='#a3a39e'))
    s.add('<g id="eq-tags">' + ''.join(g) + '</g>')

    # ---- lighting (A-201 positions) coloured by circuit
    g = []
    for lt in res['lights']:
        c = LUM_COL[lt['circuit']]
        x, y = sx(lt['at'][0]), sy(lt['at'][1])
        t = lt['type']
        if t == 'L-8':
            along = lt.get('along') or 'x'
            L8, W8 = 1.2 * S, 0.12 * S
            if along in ('x', 'h', 'X'):
                g.append(mrect(x - L8 / 2, y - W8 / 2, L8, W8, '#ffffff', c, 0.3, extra='fill-opacity="0.6"'))
            else:
                g.append(mrect(x - W8 / 2, y - L8 / 2, W8, L8, '#ffffff', c, 0.3, extra='fill-opacity="0.6"'))
        elif t in ('L-5', 'L-6') and lt.get('rect'):
            x0, y0, x1, y1 = nrect(lt['rect'])
            if (x1 - x0) >= (y1 - y0):
                g.append(mline(sx(x0), sy((y0 + y1) / 2), sx(x1), sy((y0 + y1) / 2), c, 0.55, dash='1.4 0.7'))
            else:
                g.append(mline(sx((x0 + x1) / 2), sy(y0), sx((x0 + x1) / 2), sy(y1), c, 0.55, dash='1.4 0.7'))
        else:
            r = 0.75 if t in ('L-1', 'L-9') else 0.95
            g.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{r}" fill="#ffffff" stroke="{c}" stroke-width="0.35"/>'
                     f'<circle cx="{f(x)}" cy="{f(y)}" r="{r * 0.4:.2f}" fill="{c}"/>')
    for d in res['em']:
        c = LUM_COL[d['circuit']]
        x, y = sx(d['at'][0]), sy(d['at'][1])
        g.append(sym_em(x, y, c) if d['kind'] == 'EM' else sym_rs(x, y, c))
    s.add('<g id="lighting">' + ''.join(g) + '</g>')

    # ---- TE-1 + CC-1 + working space
    g = []
    if ws:
        x0, y0, x1, y1 = ws
        ok = res['ws_check'].get('clear')
        cw = C_WS if ok else C_RED
        g.append(mrect(sx(x0), sy(y0), (x1 - x0) * S, (y1 - y0) * S, 'url(#e-ws)', cw, 0.4, dash='1.2 0.7'))
        g.append(text(sx(x0), sy(y1) + 2.3, f"ESPACIO DE TRABAJO {y1 - y0:.2f} × {x1 - x0:.2f} · h 2.00", 1.35, anchor='start', weight='800',
                      fill=cw, extra=halo(0.7)))
        g.append(text(sx(x0), sy(y1) + 4.2, 'NEC 110.26 · mantener libre' if ok else 'NEC 110.26 · CONFLICTO', 1.3, anchor='start', weight='700',
                      fill=cw, extra=halo(0.7)))
    if te_r:
        g.append(sym_panel(sx(te_r[0]), sy(te_r[1]), sx(te_r[2]), sy(te_r[3])))
        g.append(text(sx((te_r[0] + te_r[2]) / 2), sy(te_r[3]) + 2.5, 'TE-1', 1.9, weight='800', fill='#111', extra=halo()))
    if cc_r:
        g.append(mrect(sx(cc_r[0]), sy(cc_r[1]), (cc_r[2] - cc_r[0]) * S, (cc_r[3] - cc_r[1]) * S, '#ffffff', C_CTRL, 0.4))
        g.append(text(sx((cc_r[0] + cc_r[2]) / 2), sy(cc_r[3]) + 2.5, 'CC-1', 1.9, weight='800', fill=C_CTRL, extra=halo()))
    s.add('<g id="panel">' + ''.join(g) + '</g>')

    # ---- interlock bus (control cable, schematic): drops from SUP-1/2, DG-1, VS to a run inside the north wall → CC-1
    g = []
    ctrl_pts = [p for _, p in res['sups']] + ([res['dg']] if res['dg'] else []) + ([tuple(res['vs'])] if res['vs'] else [])
    if cc_r and ctrl_pts:
        yb = 0.045
        xa = min(p[0] for p in ctrl_pts)
        xb = cc_r[0] + 0.06
        g.append(mline(sx(xa), sy(yb), sx(xb), sy(yb), C_CTRL, 0.35, dash='1.6 0.8'))
        g.append(f'<circle cx="{f(sx(xb))}" cy="{f(sy(yb))}" r="0.55" fill="{C_CTRL}"/>')
        for p in ctrl_pts:
            g.append(mline(sx(p[0]), sy(yb), sx(p[0]), sy(p[1]), C_CTRL, 0.3, dash='0.8 0.5'))
    s.add('<g id="interlock-bus">' + ''.join(g) + '</g>')

    # ---- power points
    g = []
    lab = []
    items = []
    for c in res['circuits']:
        col = gcol(c)
        for p in c['pts']:
            x, y = sx(p['at'][0]), sy(p['at'][1])
            n = p.get('n', (0, 1))
            sym = p['sym']
            if sym in ('rec', 'gfci'):
                g.append(sym_rec(x, y, col, n, gfci=(sym == 'gfci'), r=1.2))
            elif sym == 'spec':
                g.append(sym_spec(x, y, col, r=1.3))
            elif sym == 'j':
                g.append(sym_j(x, y, col, t=p.get('t', 'J'), r=1.25))
            elif sym == 'motor':
                g.append(sym_motor(x, y, col))
            elif sym == 'sup':
                g.append(sym_box(x, y, 2.6, 2.2, p.get('t', 'SUP')[-1], C_CTRL, fill=C_CTRL, tcol='#ffffff', size=1.2))
            elif sym == 'dev':
                g.append(sym_box(x, y, 2.9, 2.0, p.get('t', ''), C_CTRL, size=1.05))
            if p.get('tag', True):
                items.append((c['circ'], p, x, y, col, 'mono'))
            elif sym == 'motor':
                items.append((p.get('ref', ''), p, x, y, col, 'name'))
    # circuit tags next to each point (inward), avoiding other symbols / tags
    for t_, p, x, y, col, kind in items:
        size = 1.55 if kind == 'mono' else 1.5
        wv = tw(t_, size) + 1.0
        hv = size + 0.8
        nx, ny = p.get('n', (0, 1))
        px, py = -ny, nx
        cands = []
        for dist in (3.1, 4.5):
            for sh in (0.0, 2.3, -2.3):
                cands.append((x + nx * (dist + (wv / 2 - 1.2 if abs(nx) > 0.5 else 0)) + px * sh, y + ny * dist + py * sh))
        cands += [(x + px * (3.3 + wv / 2), y + py * 3.3), (x - px * (3.3 + wv / 2), y - py * 3.3)]
        if kind == 'name':
            cands = [(x + 2.2 + wv / 2, y - 2.0), (x - 2.2 - wv / 2, y - 2.0), (x + 2.2 + wv / 2, y + 2.2), (x - 2.2 - wv / 2, y + 2.2)]
        best = None
        for i, (cx, cy) in enumerate(cands):
            b = (cx - wv / 2, cy - hv / 2, cx + wv / 2, cy + hv / 2)
            sc = cost(b) + i * 0.1
            if best is None or sc < best[0]:
                best = (sc, cx, cy, b)
        _, cx, cy, b = best
        occ.add(b)
        if math.dist((x, y), (cx, cy)) > 3.8:
            lab.append(mline(x, y, cx, cy, col, 0.18))
        if kind == 'mono':
            lab.append(mrect(b[0], b[1], b[2] - b[0], b[3] - b[1], '#ffffff', col, 0.25, rx=0.5))
            lab.append(text(cx, cy + size * 0.36, t_, size, weight='800', fill=col, family=MONO))
        else:
            lab.append(text(cx, cy + size * 0.36, t_, size, weight='800', fill=col, extra=halo(0.8)))
    s.add('<g id="power-points">' + ''.join(g) + ''.join(lab) + '</g>')

    # ---- lighting circuit tags (one per circuit, near the centroid of its luminaires, in free space)
    g = []
    circ_by = {c['key']: c for c in res['circuits']}
    for k, col in LUM_COL.items():
        pts_ = [lt['at'] for lt in res['lights'] if lt['circuit'] == k] + [d['at'] for d in res['em'] if d['circuit'] == k]
        if not pts_ or k not in circ_by:
            continue
        c = circ_by[k]
        cxm = sum(p[0] for p in pts_) / len(pts_)
        cym = sum(p[1] for p in pts_) / len(pts_)
        t1 = f"{k} · circ. {c['circ']}"
        t2 = f"{c['va'] / 1000:.2f} kVA · {c['qty']} puntos"
        size = 1.65
        wv = max(tw(t1, size), tw(t2, 1.4)) + 2.2
        hv = 5.4
        best = None
        for dy in (0, -0.4, 0.4, -0.8, 0.8, -1.2, 1.2, -1.7, 1.7):
            for dx in (0, 0.5, -0.5, 1.0, -1.0, 1.6, -1.6):
                cx, cy = sx(cxm + dx), sy(cym + dy)
                b = (cx - wv / 2, cy - hv / 2, cx + wv / 2, cy + hv / 2)
                sc = cost(b, 0.4) * 5 + abs(dx) + abs(dy)
                if best is None or sc < best[0]:
                    best = (sc, cx, cy, b)
        _, cx, cy, b = best
        occ.add(b)
        g.append(mrect(b[0], b[1], wv, hv, '#ffffff', col, 0.35, rx=0.8, extra='fill-opacity="0.95"'))
        g.append(text(cx, cy - 0.3, t1, size, weight='800', fill=col))
        g.append(text(cx, cy + 1.95, t2, 1.4, weight='600', fill=col, family=MONO))
    s.add('<g id="lighting-tags">' + ''.join(g) + '</g>')
    return occ


def draw_callouts(s, res, lay):
    """Roof fans + TE-1/CC-1 + service callouts in the strip above the north wall."""
    g = []
    boxes = []
    for m in res['motors']:
        mo = m['motor']
        solid = 'sólido' in m['desc'] or 'solido' in m['desc']
        lines = [f"{m['key']} · VENTILADOR EN CUBIERTA",
                 f"{mo['q']:.0f} L/s (M-102) · {mo['hp']:g} HP · 208 V 3F",
                 f"FLC {mo['flc']} A · circ. TE-1/{m['circ']} · {m['brk']} A",
                 'arrancador + relé térmico en CC-1',
                 'seccionador a la vista del motor (430.102)']
        is_exh = any(x['id'] == m['key'] for x in (res['mep'].get('exhaust') or []))
        if solid:
            lines.append('!NO SE APAGA CON BRASAS (selector con llave)')
        elif is_exh:
            lines.append('sigue con la supresión · prueba de flujo → VS')
        else:
            lines.append('arranca con los extractores (IMC 508.1.1)')
        anchor = m['pts'][0]['at'] if m['pts'] else None
        boxes.append((m['key'], lines, anchor, C_MOT))
    te_r = res['te_rect']
    d = res['demand']['suggested']
    ws = res['ws_check']
    te_lines = ['TE-1 TABLERO DEL LOCAL + CC-1 CONTROL DE CAMPANAS',
                f"120/208 V 3F 4H+T (VERIFY) · principal {d['main_A']} A · barra ≥{d['bus_A']} A · {d['spaces']} esp.",
                f"DPS tipo 2 · barra de tierra aislada (POS) · {d['spaces_used']} espacios usados + reservas",
                f"espacio de trabajo {ws.get('depth_m', 0.9):.2f} × {ws.get('width_m', 0.76):.2f} × h 2.00 (NEC 110.26): "
                + ('LIBRE en la planta' if ws.get('clear') else 'CONFLICTO — revisar'),
                'CC-1: arrancadores EXT-1 / EXT-2 / AR-1, relé de rearme de VS, KS-1',
                '!Acometida existente, medidor y capacidad disponible: VERIFY ON SITE']
    boxes.append(('TE-1', te_lines, ctr(te_r) if te_r else None, '#111111'))
    # layout: EXT/AR boxes between axis A and axis B, TE-1 box right of axis B
    xa, xb = sx(0.0), sx(7.8)
    y0 = 22.5
    fans = [b for b in boxes if b[0] != 'TE-1']
    # order by anchor x so leaders do not cross
    fans.sort(key=lambda b: (b[2] or (0, 0))[0])
    wbox = (xb - xa - 6.0 - 3.0 * (len(fans) - 1)) / max(1, len(fans))
    out = []
    for i, (k, lines, anc, col) in enumerate(fans):
        bx = xa + 3.0 + i * (wbox + 3.0)
        out.append((k, lines, anc, col, bx, wbox))
    tx = xb + 3.0
    tw_ = min(126.0, sx(16.3) - 3.0 - tx)
    tb = next(b for b in boxes if b[0] == 'TE-1')
    out.append((tb[0], tb[1], tb[2], tb[3], tx, tw_))
    for k, lines, anc, col, bx, bw in out:
        size = 1.72
        lh = 2.45
        # wrap to box width
        wl = []
        for j, ln in enumerate(lines):
            red = ln.startswith('!')
            s_ = ln[1:] if red else ln
            nmax = max(12, int((bw - 3.0) / (size * 0.55)))
            for q in wrap(s_, nmax):
                wl.append(('!' if red else '') + q)
        bh = 2.4 + len(wl) * lh
        g.append(mrect(bx, y0, bw, bh, '#ffffff', col, 0.4))
        for j, ln in enumerate(wl):
            red = ln.startswith('!')
            s_ = ln[1:] if red else ln
            g.append(text(bx + 1.6, y0 + 3.2 + j * lh, s_, size, anchor='start', weight='800' if (j == 0 or red) else '400',
                          fill=C_RED if red else (col if j == 0 else C_TXT)))
        if anc:
            axp, ayp = sx(anc[0]), sy(anc[1])
            ex_ = min(max(axp, bx + 2), bx + bw - 2)
            g.append(mline(ex_, y0 + bh, axp, ayp, col, 0.25))
            g.append(f'<circle cx="{f(axp)}" cy="{f(ayp)}" r="0.5" fill="{col}"/>')
    s.add('<g id="callouts">' + ''.join(g) + '</g>')


def draw_diagrams(s, res, x0, y0, w, h):
    """Single-line (top) + cause–effect matrix (bottom) in the free area south of the dining room."""
    g = [mrect(x0, y0, w, h, '#ffffff', '#1b1b1b', 0.35)]
    d = res['demand']
    sug = d['suggested']
    g.append(text(x0 + 3, y0 + 5.2, 'DIAGRAMA UNIFILAR ESQUEMÁTICO · TE-1', 2.5, anchor='start', weight='800', extra='letter-spacing="0.3"'))
    g.append(text(x0 + w - 3, y0 + 5.2, 'sin escala · PRELIMINAR', 1.7, anchor='end', weight='700', fill=C_RED))
    # source chain (left)
    cx = x0 + 12.0
    yy = y0 + 9.0
    g.append(mrect(cx - 9.0, yy, 18, 6.6, '#f3f3f1', '#555', 0.3))
    g.append(text(cx, yy + 2.7, 'RED DEL C.C. /', 1.4, weight='800', fill='#333'))
    g.append(text(cx, yy + 5.0, 'DISTRIBUIDORA', 1.4, weight='800', fill='#333'))
    g.append(mline(cx, yy + 6.6, cx, yy + 9.0, '#111', 0.35))
    g.append(f'<circle cx="{f(cx)}" cy="{f(yy + 11.3)}" r="2.3" fill="#ffffff" stroke="#111" stroke-width="0.35"/>')
    g.append(text(cx, yy + 11.8, 'kWh', 1.25, weight='800'))
    g.append(text(cx + 3.4, yy + 10.9, 'medidor', 1.45, anchor='start', fill='#555'))
    g.append(text(cx + 3.4, yy + 13.0, FLAG_SITE, 1.35, anchor='start', weight='700', fill=C_RED))
    g.append(mline(cx, yy + 13.6, cx, yy + 17.2, '#111', 0.35))
    g.append(text(cx + 1.8, yy + 16.3, 'acometida 4H + T (ruta y calibre: ingeniero)', 1.4, anchor='start', fill='#333'))
    g.append(sym_breaker(cx, yy + 19.3, '#111', 0.45))
    g.append(text(cx + 2.6, yy + 19.1, f"principal 3P {sug['main_A']} A", 1.6, anchor='start', weight='800'))
    g.append(text(cx + 2.6, yy + 21.2, '(incluye 20 % de reserva)', 1.35, anchor='start', fill='#555'))
    bus_y = yy + 25.5
    g.append(mline(cx, yy + 20.5, cx, bus_y, '#111', 0.35))
    # SPD
    g.append(mline(cx, bus_y - 2.1, cx - 5.2, bus_y - 2.1, '#111', 0.25))
    g.append(mrect(cx - 10.0, bus_y - 3.6, 4.8, 3.0, '#ffffff', '#111', 0.3))
    g.append(text(cx - 7.6, bus_y - 1.6, 'DPS', 1.2, weight='800'))
    # bus
    bx0, bx1 = x0 + 4.0, x0 + w - 4.0
    g.append(mline(bx0, bus_y, bx1, bus_y, '#111', 0.9))
    g.append(text(bx1, bus_y - 1.4, f"BARRA TE-1 · 120/208 V 3F 4H + T · ≥{sug['bus_A']} A · {sug['spaces']} espacios", 1.55, anchor='end', weight='800'))
    # groups
    dem_of = {'K': d['kitchen']['demand_VA'], 'M': d['motors']['demand_VA'], 'H': d['hvac_reserve']['demand_VA'],
              'L': d['lighting']['demand_VA'], 'S': d['sign']['demand_VA'], 'R': d['receptacles']['demand_VA']}
    grp_list = []
    for gk in GROUP_ORDER:
        cs = [c for c in res['circuits'] if c['group'] == gk]
        if not cs:
            continue
        dem = dem_of.get(gk)
        if gk in ('C', 'IT'):
            dem = sum(c['va'] for c in cs)
        grp_list.append((gk, cs, dem))
    n = len(grp_list)
    gw = (bx1 - bx0) / n
    by_ = bus_y + 7.6
    name_lines = [wrap(GROUP[gk][0], max(8, int((gw - 1.6) / (1.45 * 0.56))))[:2] for gk, _, _ in grp_list]
    nl = max(len(x) for x in name_lines)
    bh_ = 3.0 + nl * 1.9 + 7.6
    for i, (gk, cs, dem) in enumerate(grp_list):
        name, basis, col = GROUP[gk]
        xc = bx0 + gw * (i + 0.5)
        g.append(mline(xc, bus_y, xc, bus_y + 3.0, col, 0.35))
        g.append(sym_breaker(xc, bus_y + 4.4, col))
        g.append(mline(xc, bus_y + 5.6, xc, by_, col, 0.35))
        bw_ = gw - 1.2
        dash = '1 0.6' if gk in ('X', 'H') else None
        g.append(mrect(xc - bw_ / 2, by_, bw_, bh_, '#ffffff', col, 0.35, dash=dash))
        for j, ln in enumerate(name_lines[i]):
            g.append(text(xc, by_ + 2.6 + j * 1.9, ln, 1.45, weight='800', fill=col))
        yb = by_ + 2.6 + nl * 1.9
        g.append(text(xc, yb + 0.5, f"{len(cs)} circ.", 1.35, fill='#333'))
        g.append(text(xc, yb + 2.5, basis.split(' · ')[0], 1.25, fill='#555'))
        g.append(text(xc, yb + 4.9, '—' if gk == 'X' else (f"{dem / 1000:.1f} kVA" if dem >= 1000 else f"{dem / 1000:.2f} kVA"), 1.75,
                      weight='800', family=MONO,
                      fill=C_RED if gk == 'X' else '#111'))
    yy = by_ + bh_ + 3.6
    g.append(text(x0 + 3, yy, f"Demanda NEC 220: {d['total_demand_VA'] / 1000:.1f} kVA + 25 % continuas {d['continuous_adder_VA'] / 1000:.1f} kVA = "
                  f"{d['design_VA'] / 1000:.1f} kVA → {d['I_3F_208']:.0f} A (208 V 3F) · +20 % → {d['I_3F_208_growth']:.0f} A → "
                  f"principal {sug['main_A']} A", 1.6, anchor='start', weight='800'))
    g.append(text(x0 + 3, yy + 2.6, 'Puesta a tierra: electrodo / conductor del C.C. + unión equipotencial de ductos, gas y campanas — VERIFY ON SITE.',
                  1.4, anchor='start', fill='#444'))
    # ---- cause–effect matrix
    my = yy + 5.2
    g.append(mline(x0, my, x0 + w, my, '#1b1b1b', 0.3))
    g.append(text(x0 + 3, my + 4.6, 'MATRIZ CAUSA–EFECTO · ENCLAVAMIENTOS', 2.5, anchor='start', weight='800', extra='letter-spacing="0.3"'))
    g.append(text(x0 + w - 3, my + 4.6, FLAG_ENG, 1.4, anchor='end', weight='800', fill=C_RED))
    cols = [('Evento (causa)', 36), ('VS gas H2–H5', 17), ('KS-1 freidoras', 17), ('EXT-1', 14), ('EXT-2', 14),
            ('AR-1', 16), ('Alarma', 17)]
    tot = sum(wc for _, wc in cols)
    sc_ = (w - 6) / tot
    cols = [(nm, wc * sc_) for nm, wc in cols]
    rows = [
        ('Disparo SUP-1 (HD-1 · fusible o PM-1)', ['CIERRA R', 'ABRE', 'SIGUE ¹', '—', 'LISTADO ²', 'C.C. + local']),
        ('Disparo SUP-2 (HD-2 · parrilla · PM-2)', ['CIERRA ³', 'ABRE ³', '—', 'SIGUE', 'LISTADO ²', 'C.C. + local']),
        ('DG-1 detecta gas', ['CIERRA R', '—', 'SIGUE', '—', '—', 'local']),
        ('DCO-1 detecta CO', ['—', '—', 'SIGUE', 'SIGUE', 'SIGUE', 'local']),
        ('EXT-1 sin prueba de flujo', ['CIERRA', 'ABRE', '—', '—', '—', 'local']),
        ('EXT-1 o EXT-2 en marcha', ['permite', 'permite', '—', '—', 'ARRANCA', '—']),
        ('Brasas en H1 / S1 (selector con llave)', ['—', '—', '—', 'NO PARA', 'MANTIENE', '—']),
        ('Falla de energía', ['CIERRA R (N.C.)', 'ABRE', 'PARA', 'PARA ⁴', 'PARA', '—']),
    ]
    ty = my + 7.4
    fn = ['R = rearme manual (NFPA 96: corte de combustible y energía de los equipos protegidos). ¹ Salvo que el listado indique otra cosa.',
          '² AR-1 se detiene o sigue según el listado de la supresión; con brasas mantener reposición positiva (M-102). ³ Recomendado: campanas contiguas.',
          '⁴ Con brasas: tiro natural por el ducto propio; no reanudar la cocción sin EXT-2. Lógica, cableado y señales finales: TO BE ENGINEERED.']
    avail = (y0 + h - 2.0) - ty - len(fn) * 2.35 - 1.5
    rh = max(3.0, min(4.2, avail / (len(rows) + 1)))
    fs = min(1.5, rh * 0.42)
    g.append(mrect(x0 + 3, ty, w - 6, rh, '#141210', '#141210', 0.2))
    xx = x0 + 3
    for nm, wc in cols:
        first = nm.startswith('Evento')
        g.append(text(xx + (1.0 if first else wc / 2), ty + rh / 2 + fs * 0.36, nm, fs, anchor='start' if first else 'middle',
                      weight='800', fill='#ffffff'))
        xx += wc
    for i, (ev, vals) in enumerate(rows):
        yy_ = ty + rh * (i + 1)
        if i % 2 == 0:
            g.append(mrect(x0 + 3, yy_, w - 6, rh, '#f6f4f0', 'none', 0))
        xx = x0 + 3
        g.append(text(xx + 1.0, yy_ + rh / 2 + fs * 0.36, ev, fs, anchor='start', weight='700'))
        xx += cols[0][1]
        for (nm, wc), v in zip(cols[1:], vals):
            colr = C_RED if v.startswith(('CIERRA', 'ABRE', 'PARA', 'NO PARA')) else ('#0a7d3b' if v.startswith(('SIGUE', 'ARRANCA', 'MANTIENE', 'permite')) else '#555')
            g.append(text(xx + wc / 2, yy_ + rh / 2 + fs * 0.36, v, fs * 0.97, weight='800' if v != '—' else '400', fill=colr, family=MONO))
            xx += wc
    yy_ = ty + rh * (len(rows) + 1)
    g.append(mline(x0 + 3, yy_, x0 + w - 3, yy_, '#1b1b1b', 0.25))
    for j, ln in enumerate(fn):
        g.append(text(x0 + 3, yy_ + 2.7 + j * 2.35, ln, 1.38, anchor='start', fill='#333'))
    s.add('<g id="diagrams">' + ''.join(g) + '</g>')
    return yy_ + 2.7 + len(fn) * 2.35


def draw_load_table(s, res, x, y, w, y_max=411.0):
    cs = sorted([c for c in res['circuits']], key=lambda c: (GROUP_ORDER.index(c['group']), c['slots'][0]))
    g = ['<g id="load-table">']
    g.append(text(x, y + 3, 'CUADRO DE CARGAS PRELIMINAR · TE-1', 2.6, anchor='start', weight='800', extra='letter-spacing="0.35"'))
    g.append(text(x + 66, y + 3, PRELIM + ' · valores típicos de catálogo: * = TBV (ficha técnica) · conductores THHN Cu 75 °C de referencia', 1.75,
                  anchor='start', weight='700', fill=C_RED))
    y += 5.2
    cols = [(0, 'Circ.', 'start'), (14, 'Fase', 'start'), (24, 'Ref.', 'start'), (40, 'Carga / equipo', 'start'), (128, 'Zona', 'start'),
            (140, 'Conexión', 'start'), (199, 'V · polos', 'start'), (224, 'kVA c/u', 'end'), (232, 'Cant.', 'end'), (247, 'kVA', 'end'),
            (251, 'Grupo NEC 2020', 'start'), (284, 'Prot.', 'end'), (289, 'Cond.', 'start'), (299, 'GFCI', 'start'), (308, 'Enclavamiento / nota', 'start')]
    n = len(cs) + 1
    avail = y_max - y - 4.0 - 2.4
    rh = max(2.35, min(3.0, avail / n))
    size = min(1.55, rh * 0.62)
    g.append(mrect(x, y, w, 3.2, '#141210', '#141210', 0.2))
    for dx, hd, anc in cols:
        g.append(text(x + dx + (0.8 if anc == 'start' else 0), y + 2.25, hd, 1.45, anchor=anc, weight='800', fill='#ffffff'))
    y += 3.2
    note_w = w - 308 - 1
    nmax = int(note_w / (size * 0.53))
    for i, c in enumerate(cs):
        yy = y + i * rh
        col = gcol(c)
        grey = not c['sum']
        if i % 2 == 0:
            g.append(mrect(x, yy, w, rh, '#f6f4f0', 'none', 0))
        va_u = c['va'] / c['qty'] if c['qty'] else c['va']
        kva_u = '—' if c.get('lum') else fmt_kva(va_u)
        vals = [
            (0, c['circ'], 'start', MONO, '800', col),
            (14, '-'.join(c['phases']), 'start', MONO, '600', '#333'),
            (24, c['ref'][:11], 'start', FONT, '800', col),
            (40, c['desc'][:74], 'start', FONT, '400', '#8a8a85' if grey else C_TXT),
            (128, str(c['zone'])[:9], 'start', FONT, '400', '#333'),
            (140, c['conn'][:46], 'start', FONT, '400', '#333'),
            (199, f"{c['V']:.0f} · {c['poles']}P", 'start', MONO, '400', '#333'),
            (224, kva_u + ('*' if c['tbv'] and not c.get('lum') else ''), 'end', MONO, '600', C_RED if c['tbv'] and not c.get('lum') else '#333'),
            (232, str(c['qty']), 'end', MONO, '400', '#333'),
            (247, fmt_kva(c['va']), 'end', MONO, '800', '#8a8a85' if grey else '#111'),
            (251, GROUP_SHORT[c['group']], 'start', FONT, '400', '#333'),
            (284, f"{c['brk']} A", 'end', MONO, '700', '#111'),
            (289, c['wire'], 'start', MONO, '400', '#333'),
            (299, 'sí' if c.get('gfci') else '—', 'start', FONT, '700' if c.get('gfci') else '400', '#1f4fa3' if c.get('gfci') else '#999'),
            (308, (c.get('note') or '')[:nmax], 'start', FONT, '400', C_RED if c['group'] == 'X' else '#333'),
        ]
        for dx, v, anc, fam, wt, fc in vals:
            g.append(text(x + dx + (0.8 if anc == 'start' else 0), yy + rh * 0.5 + size * 0.36, v, size, anchor=anc, weight=wt, fill=fc, family=fam))
    yy = y + len(cs) * rh
    d = res['demand']
    g.append(mline(x, yy, x + w, yy, '#141210', 0.35))
    g.append(text(x + 40.8, yy + rh * 0.5 + size * 0.36, 'TOTAL CONECTADO (sin reservas)', size, anchor='start', weight='800'))
    g.append(text(x + 247, yy + rh * 0.5 + size * 0.36, fmt_kva(d['connected_total_VA']), size, anchor='end', weight='800', family=MONO))
    g.append(text(x + 251.8, yy + rh * 0.5 + size * 0.36,
                  f"demanda NEC {d['total_demand_VA'] / 1000:.1f} kVA · diseño {d['design_VA'] / 1000:.1f} kVA · {d['I_3F_208']:.0f} A 3F 208 V → principal {d['suggested']['main_A']} A",
                  size, anchor='start', weight='800', fill=C_RED))
    yy += rh + 0.8
    ne = ', '.join(res['no_elec'])
    g.append(text(x, yy + 1.8, f"Sin conexión eléctrica: {ne} (gas de red / carbón-leña, encendido manual — si la ficha pide 120 V, conectar vía KS-1). "
                  'Los servicios sanitarios son los comunes del C.C.: sin extractores ni secamanos en el local. Caída de tensión ≤3 % ramal / ≤5 % total.',
                  1.4, anchor='start', fill='#444'))
    g.append('</g>')
    s.add(''.join(g))
    return yy + 3


def side_panel(s, res, lay):
    d = res['demand']
    sug = d['suggested']
    def sw(fn):
        return lambda x, y: fn(x + 5, y + 1.7)

    legend = [
        (sw(lambda x, y: sym_rec(x, y, C_K, (0, 1), gfci=True)), 'Tomacorriente GFCI 120 V (mitad llena)'),
        (sw(lambda x, y: sym_rec(x, y, C_REC, (0, 1))), 'Tomacorriente 120 V (salón)'),
        (sw(lambda x, y: sym_spec(x, y, C_K)), 'Toma especial 208 V (horno K2)'),
        (sw(lambda x, y: sym_j(x, y, C_K)), 'Conexión fija (J) · CA calentador · R rótulo'),
        (sw(lambda x, y: sym_motor(x, y, C_MOT)), 'Motor en cubierta (EXT-1 / EXT-2 / AR-1)'),
        (lambda x, y: sym_panel(x, y + 0.4, x + 10, y + 3.0), 'TE-1 tablero · CC-1 control de campanas'),
        (sw_rect(None, C_WS, dash='1.2 0.7', pattern='url(#e-ws)'), 'Espacio de trabajo NEC 110.26 (libre)'),
        (sw_rect(None, '#6f9bd6', dash='1.2 0.8', pattern='url(#e-gfci)'), 'Zona GFCI: cocina, BBQ, lavado, cold prep, barra'),
        (sw(lambda x, y: sym_box(x, y, 2.6, 2.2, '1', C_CTRL, fill=C_CTRL, tcol='#fff')), 'SUP-1 / SUP-2 supresión (contactos a CC-1)'),
        (sw(lambda x, y: sym_box(x, y, 2.9, 2.0, 'DG', C_CTRL, size=1.05)), 'DG-1 gas · DCO-1 CO · VS solenoide N.C.'),
        (sw_line(C_CTRL, '1.6 0.8', 0.35), 'Cable de control / enclavamiento (esquema)'),
        (lambda x, y: ''.join(f'<circle cx="{f(x + 1.5 + i * 2.4)}" cy="{f(y + 1.7)}" r="0.8" fill="#fff" stroke="{c}" stroke-width="0.35"/>'
                              for i, c in enumerate(LUM_COL.values())), 'Luminarias de A-201 por circuito LUM-1…4'),
        (sw(lambda x, y: sym_em(x - 1.5, y, '#2e7d32') + sym_rs(x + 2.2, y, '#2e7d32')), 'EM emergencia · RS rótulo SALIDA'),
        (lambda x, y: mrect(x + 1.5, y + 0.2, 7, 2.9, '#ffffff', C_K, 0.25, rx=0.5) + text(x + 5, y + 2.2, '1-3', 1.4, weight='800', fill=C_K, family=MONO),
         'N.º de circuito en TE-1 (polos)'),
    ]
    ph = d['phase_connected_VA']
    rows = [
        ('Alumbrado (220.12 vs. A-201)', f"{d['lighting']['demand_VA'] / 1000:.2f} kVA"),
        ('Rótulo exterior (220.14(F))', f"{d['sign']['demand_VA'] / 1000:.2f} kVA"),
        (f"Tomas generales ({d['receptacles']['count']} × 180 VA)", f"{d['receptacles']['demand_VA'] / 1000:.2f} kVA"),
        (f"Cocina 220.56 ({d['kitchen']['units']} u. × {d['kitchen']['factor'] * 100:.0f} %)",
         f"{d['kitchen']['connected_VA'] / 1000:.1f} → {d['kitchen']['demand_VA'] / 1000:.2f} kVA"),
        ('Motores (+25 % del mayor)', f"{d['motors']['demand_VA'] / 1000:.2f} kVA"),
        ('A/C salón (reserva)', f"{d['hvac_reserve']['demand_VA'] / 1000:.2f} kVA"),
        ('Control / seguridad / TI', f"{d['control_it']['demand_VA'] / 1000:.2f} kVA"),
        ('DEMANDA ESTIMADA (NEC 220)', f"{d['total_demand_VA'] / 1000:.1f} kVA"),
        ('+25 % cargas continuas → diseño', f"{d['design_VA'] / 1000:.1f} kVA"),
        ('Corriente 3F 208 V / +20 % reserva', f"{d['I_3F_208']:.0f} A / {d['I_3F_208_growth']:.0f} A"),
        ('Alternativa 1F 240 V / +20 %', f"{d['I_1F_240']:.0f} A / {d['I_1F_240_growth']:.0f} A"),
        ('Carga conectada por fase A / B / C', f"{ph['A'] / 1000:.1f} / {ph['B'] / 1000:.1f} / {ph['C'] / 1000:.1f} kVA"),
    ]
    acom = [
        f"!Acometida sugerida: 120/208 V 3F 4H+T · principal {sug['main_A']} A",
        f"!TE-1 barra ≥{sug['bus_A']} A · {sug['spaces']} espacios ({sug['spaces_used']} usados).",
        f"Alternativa 1F 120/240 V: principal {sug['alt_1F_main_A']} A (motores 1F, menos",
        '  recomendable). Confirmar capacidad disponible con el C.C.',
    ]
    inter = [
        'SUP-1 dispara: VS cierra el gas de H2–H5 (rearme manual),',
        '  KS-1 corta los 120 V de las freidoras, EXT-1 sigue, señal',
        '  a la alarma del C.C. (si existe — VERIFY).',
        'SUP-2 (parrilla): EXT-2 sigue; con brasas no se apaga.',
        'AR-1 arranca con EXT-1 / EXT-2 (IMC 508.1.1).',
        'VS solo abre con EXT-1 en marcha, DG-1 sin alarma y',
        '  SUP-1 armado; normalmente cerrada (falla = cierra).',
        'Supresión: contactos secos del sistema listado (UL 300).',
    ]
    notes = [
        '!' + PRELIM,
        '!' + FLAG_ENG,
        '!' + FLAG_SMOKER,
        'GFCI en todos los tomacorrientes de cocina, BBQ, lavado,',
        '  cold prep y barra, incl. 208 V ≤50 A (NEC 2020 210.8(B)).',
        'Refrigeración con GFCI: alarma de temperatura (o conexión',
        '  fija si el ingeniero lo justifica).',
        'Motores: arrancador con relé térmico (CC-1) + seccionador',
        '  a la vista del motor (430.102); protección ≤250 % FLC.',
        'EM/RS con batería ≥1.5 h en el circuito de alumbrado del',
        '  área, antes del interruptor (NFPA 101 7.9 · NEC 700.12).',
        'Luminarias de cocina IP65 con difusor inastillable (Salud).',
        'Ductos, gas, campanas y tablero: unión equipotencial.',
        'Código Eléctrico CR (DE 36979-MEIC; NEC 2020 oficializado',
        '  2024 según prensa) — citas de resúmenes: verificar.',
    ]
    verify = [
        'Tensión y fases disponibles, medidor y ruta de acometida.',
        'Capacidad asignada al local por el C.C. / distribuidora.',
        'Estado del tablero existente de Marna\'s (se sustituye).',
        'Placas de equipos: kW, V, fases, corriente (* TBV).',
        'Sistema de alarma del C.C. para las señales de supresión.',
    ]
    y = s.side_panel([('h', 'Leyenda eléctrica'), ('legend', legend), ('h', 'Demanda estimada (NEC 2020 art. 220)'), ('rows', rows),
                      ('para', acom)])
    prem_ = [
        'Baños: comunes del C.C. (clientes y personal) → sin cargas',
        '  sanitarias propias (extractores, secamanos, calentador).',
        'Venta de alcohol (licencia clase C): enfriador / chopera y',
        '  tomas GFCI de barra (licuadora) incluidos en TE-1.',
        'Gas de la red del C.C. (sin cilindros): H2–H5 solo con',
        '  encendido 120 V vía KS-1; VS enclavada con SUP-1.',
        'C.C. abierto con reglamento: acometida, medidor, rótulo y',
        '  alarma según la administración — VERIFY.',
    ]
    y = s.side_panel([('h', 'Enclavamientos (a validar)'), ('para', inter), ('h', 'Premisas del cliente'), ('para', prem_),
                      ('h', 'Criterios y normativa'), ('para', notes), ('h', FLAG_SITE), ('para', verify)], y=y)
    return y


# ============================================================================ JSON
def to_json(res, lay):
    out = {
        'sheet': 'E-101',
        'status': 'ANTEPROYECTO / ' + PRELIM,
        'layout_version': (lay.get('meta') or {}).get('version'),
        'date': (lay.get('meta') or {}).get('date'),
        'flags': [PRELIM, FLAG_ENG, FLAG_SMOKER, FLAG_DIM, FLAG_SITE],
        'system_assumed': '120/208 V 3F 4H + T (VERIFY) · alternativa 120/240 V 1F',
        'panel': {'id': (res['panel'] or {}).get('id', 'TE-1'), 'rect': res['te_rect'], 'note': (res['panel'] or {}).get('note'),
                  'control_panel_CC1_rect': [round(v, 3) for v in res['cc_rect']] if res['cc_rect'] else None,
                  'working_space': res['ws_check']},
        'circuits': [],
        'demand': res['demand'],
        'lighting': {'source': 'A-201 (sheets.s201_cielos.ceiling_layout)' if res['L'] else 'estimado por área (A-201 no disponible)',
                     'W_per_type': W_LUM, 'luminaires': res['lights'], 'emergency_and_exit': res['em']},
        'devices': {'SUP': [{'id': k, 'at': [round(v, 3) for v in p]} for k, p in res['sups']],
                    'DG-1': [round(v, 3) for v in res['dg']] if res['dg'] else None,
                    'DCO-1': [round(v, 3) for v in res['dco']] if res['dco'] else None,
                    'VS': res['vs'], 'sign_exterior': [round(v, 3) for v in res['sign_at']] if res['sign_at'] else None},
        'no_electrical_connection': res['no_elec'],
        'interlocks': [
            {'cause': 'Disparo SUP-1 (HD-1)', 'effects': {'VS': 'cierra, rearme manual', 'KS-1': 'abre (freidoras 120 V)', 'EXT-1': 'sigue salvo listado',
                                                          'AR-1': 'según listado', 'alarma': 'C.C. + local'}},
            {'cause': 'Disparo SUP-2 (HD-2)', 'effects': {'VS': 'cierra (recomendado)', 'KS-1': 'abre (recomendado)', 'EXT-2': 'sigue',
                                                          'AR-1': 'según listado', 'alarma': 'C.C. + local'}},
            {'cause': 'DG-1 detecta gas', 'effects': {'VS': 'cierra, rearme manual', 'alarma': 'local'}},
            {'cause': 'DCO-1 detecta CO', 'effects': {'EXT/AR': 'siguen', 'alarma': 'local'}},
            {'cause': 'EXT-1 sin prueba de flujo', 'effects': {'VS': 'cierra', 'KS-1': 'abre'}},
            {'cause': 'EXT-1 o EXT-2 en marcha', 'effects': {'AR-1': 'arranca (IMC 508.1.1)', 'VS/KS-1': 'permiso'}},
            {'cause': 'Brasas en H1/S1', 'effects': {'EXT-2': 'no se apaga (selector con llave)', 'AR-1': 'mantiene reposición'}},
            {'cause': 'Falla de energía', 'effects': {'VS': 'cierra (N.C.), rearme manual', 'KS-1': 'abre', 'EXT/AR': 'paran'}},
        ],
        'sources': [
            'NEC 2020 (NFPA 70): 110.26 espacio de trabajo; 210.8(B) GFCI; 220.12 / 220.14(F)(I) / 220.42 / 220.44 / 220.50 / 220.56; '
            '215.3 / 230.42 cargas continuas; 422.13 calentadores; 430.24 / 430.52 / 430.102 motores; 600.5 rótulos; 700.12 equipos autónomos',
            'Código Eléctrico de Costa Rica (DE 36979-MEIC y reformas; NEC 2020 oficializado el 10-07-2024 según prensa) — verificar',
            'NFPA 96: corte de combustible y energía al disparar la supresión (rearme manual); ventilador sigue operando; cap. 14 combustible sólido',
            'NFPA 17A / UL 300 (supresión química húmeda) · UL 710B (recirculación del horno K2) · IMC 508.1.1 (reposición enclavada)',
            'NFPA 101 7.9 (iluminación de emergencia ≥1.5 h) · NFPA 72 (circuito exclusivo con traba)',
            'Citas tomadas de resúmenes y conocimiento general, no de textos primarios: verificar edición y numeración',
        ],
        'verify_on_site': ['Tensión / fases disponibles y medidor', 'Capacidad asignada al local por el C.C.', 'Ruta de acometida',
                           'Tablero existente de Marna\'s', 'Placas de equipos (TBV)', 'Alarma del C.C. para señales de supresión'],
    }
    for c in res['circuits']:
        out['circuits'].append({
            'key': c['key'], 'circuit': c['circ'], 'slots': c['slots'], 'phases': c['phases'], 'ref': c['ref'], 'desc': c['desc'],
            'zone': c['zone'], 'V': c['V'], 'poles': c['poles'], 'qty': c['qty'], 'VA_unit': round(c['va'] / c['qty']) if c['qty'] else round(c['va']),
            'VA': round(c['va']), 'I_A': round(c['I'], 1), 'group': c['group'], 'group_name': GROUP[c['group']][0], 'nec': GROUP[c['group']][1],
            'breaker_A': c['brk'], 'conductor': c['wire'], 'gfci': bool(c.get('gfci')), 'connection': c['conn'], 'continuous': bool(c['cont']),
            'in_demand': bool(c['sum']), 'tbv': bool(c['tbv']), 'basis': c.get('basis'), 'note': c.get('note'),
            'motor': c.get('motor'), 'points': [{'at': list(p['at']), 'sym': p['sym'], 'ref': p.get('ref')} for p in c['pts']],
        })
    return out


# ============================================================================ sheet
def sheets(ex, lay, val):
    res = calc(ex, lay, val)
    try:
        with open(os.path.join(ROOT, 'data', 'elec_loads.json'), 'w') as fh:
            json.dump(to_json(res, lay), fh, indent=1, ensure_ascii=False)
    except Exception as err:  # noqa: BLE001
        print('WARNING: elec_loads.json not written:', err)
    s = Sheet(ex, lay, val, 'E101')
    s.frame_and_titleblock('E-101 · Eléctrico (esquema) y cargas',
                           'Puntos de fuerza, tablero TE-1, GFCI, enclavamientos, cuadro de cargas y demanda NEC 2020 · PRELIMINAR', 'E-101',
                           scale_note='Escala 1:50 en A2 · esquema eléctrico')
    s.grid_axes()
    draw_plan(s, res, lay, ex)
    s.layer_existing()
    s.layer_new()
    s.layer_furniture(faint=True)
    s.layer_equipment(faint=True, labels=False)
    draw_overlay(s, res, lay, ex)
    draw_callouts(s, res, lay)
    # diagrams in the free area south of the dining room (east of the stair, clear of shafts / columns)
    x0, x1 = sx(8.8), sx(15.8)
    y0, y1 = sy(6.0), sy(12.1)
    draw_diagrams(s, res, x0, y0, x1 - x0, y1 - y0)
    draw_load_table(s, res, 12.0, 320.0, 418.0)
    side_panel(s, res, lay)
    return [{'id': 'E101', 'file': 'lava_E101_electrico.svg', 'title': 'Eléctrico (esquema) y cuadro de cargas preliminar', 'order': 501,
             'svg': s.render()}]


if __name__ == '__main__':
    from lavageo import load_existing
    ex_ = load_existing()
    lay_ = load_json(os.path.join(ROOT, 'data', 'layout.json'))
    vp = os.path.join(ROOT, 'data', 'validation.json')
    val_ = load_json(vp) if os.path.exists(vp) else None
    r = calc(ex_, lay_, val_)
    print(json.dumps(r['demand'], indent=1, ensure_ascii=False))
    for c in r['circuits']:
        print(f"{c['circ']:>10} {'-'.join(c['phases']):6} {c['key']:8} {c['va']:8.0f} VA {c['brk']:>3} A {c['zone']}")
