#!/usr/bin/env python3
"""Export the LAVA v3 anteproyecto to editable AutoCAD DXF files (AutoCAD 2018 DXF, units = metres).

Usage:
    python3 tools/export_dxf.py [--out plan] [--check OUT_DIR]

Writes
    plan/LAVA_base_v3.dxf            proposal: existing walls to keep, demolition, new walls/openings, equipment,
                                     furniture, zones, dimensions (DIMENSION entities), life safety, MEP anchors,
                                     schedules and a project-data title block
    plan/LAVA_base_v3_existente.dxf  existing conditions only (Marna's survey, data/existing.json)

--check OUT_DIR re-reads both files with ezdxf (audit + entity count per layer) and renders PNGs of the model space
(full view + zoomed crops) with ezdxf.addons.drawing / matplotlib into OUT_DIR.

Coordinates: 1 drawing unit = 1 m, origin = column axis A / axis row 1, exactly like data/*.json.  The JSON Y axis
grows SOUTH (down the PDF) while AutoCAD's Y grows up, so the DXF stores (X, -Y) and the plan reads like the PDF
sheets.  The named UCS "LAVA-DATOS" (Y axis pointing down) makes AutoCAD report the JSON coordinates (ID / LIST).
Everything is ANTEPROYECTO / PRELIMINAR: a validar por el profesional responsable.
"""
import argparse
import json
import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ezdxf  # noqa: E402
from ezdxf import colors as ezcolors  # noqa: E402
from ezdxf import units, zoom  # noqa: E402
from ezdxf.enums import MTextEntityAlignment, TextEntityAlignment  # noqa: E402
from shapely.geometry import LineString, Point, Polygon, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from lavageo import R, ROOT, front_zone, load_existing, load_json, premises, seat_count, standing_existing_walls  # noqa: E402
from plan_svg import ROUTE, eq_dims_cm  # noqa: E402

FLAG_EXT = 'EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED'
FLAG_SMOKER = 'SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED'
FLAG_DIM = 'DIMENSION TO VERIFY'
FLAG_SITE = 'VERIFY ON SITE'
STATUS = 'ANTEPROYECTO / PRELIMINAR — a validar por el profesional responsable (CFIA)'

# ------------------------------------------------------------------------------------------------ layer standard
# name, ACI colour, linetype, lineweight (1/100 mm), description, on by default
LAYERS = [
    ('A-EJE', 8, 'LAVA_EJE', 13, 'Ejes de columnas A-B-C / 1-2', True),
    ('A-MURO-EXIST', 8, 'Continuous', 35, 'EXISTING WALL: muro existente que se mantiene (contorno)', True),
    ('A-MURO-EXIST-TRAMA', 253, 'Continuous', 5, 'Trama de muro existente', True),
    ('A-MURO-DEMOL', 1, 'LAVA_DEMOL', 35, 'WALL TO DEMOLISH: muro / vidrio / tramo a demoler', True),
    ('A-MURO-DEMOL-TRAMA', 11, 'Continuous', 5, 'Trama de demolición', True),
    ('A-MURO-NUEVO', 7, 'Continuous', 70, 'NEW PROPOSED WALL: muro / división nueva', True),
    ('A-MURO-NUEVO-TRAMA', 7, 'Continuous', 5, 'Relleno sólido de muro nuevo', True),
    ('A-VIDRIO', 4, 'Continuous', 25, 'Vidrio: vitrinas, ventana, vidrio de la división NW-1', True),
    ('A-PUERTA', 150, 'Continuous', 25, 'Puertas y vanos con giro de hoja', True),
    ('A-PUERTA-COND', 1, 'LAVA_COND', 25, 'Puerta / vano CONDICIONAL (requiere aprobación)', True),
    ('A-COLUMNA', 7, 'Continuous', 50, 'Columnas (contorno)', True),
    ('A-COLUMNA-TRAMA', 8, 'Continuous', 5, 'Relleno de columnas', True),
    ('A-ESCALERA', 8, 'Continuous', 18, 'Escalera del edificio (fuera del local)', True),
    ('A-DUCTO', 8, 'Continuous', 18, 'Ductos existentes (shafts)', True),
    ('A-CONTEXTO', 9, 'LAVA_FINO', 13, 'Contexto fuera del local (puertas vecinas, terraza)', True),
    ('A-EQUIPO', 30, 'Continuous', 25, 'Equipos de cocina / barra en piso (trazo grueso = frente de trabajo)', True),
    ('A-EQUIPO-ALTO', 30, 'LAVA_OCULTO', 35, 'Equipos en altura: campanas (proyección)', True),
    ('A-EQUIPO-TEXTO', 7, 'Continuous', 13, 'Rótulos de equipos: tag · nombre · medida (* = DIMENSION TO VERIFY)', True),
    ('A-EQUIPO-DESPEJE', 8, 'LAVA_FINO', 9, 'Despeje libre exigido frente a cada equipo', False),
    ('A-RETIRO', 1, 'LAVA_DEMOL', 25, 'Equipo existente a retirar', True),
    ('A-MOBILIARIO', 94, 'Continuous', 18, 'Mesas, sillas y bancas corridas', True),
    ('A-DECOR', 32, 'Continuous', 13, 'Decoración: celosía, letrero, afiches, luminarias decorativas', True),
    ('A-ZONA', 8, 'LAVA_FINO', 18, 'Zonas operativas: límite, nombre y área', True),
    ('A-ZONA-TRAMA', 8, 'Continuous', 5, 'Relleno transparente de zonas', True),
    ('A-FLUJO', 5, 'Continuous', 25, 'Flujos operativos (limpio / sucio / platos / clientes / delivery)', False),
    ('A-COTA', 7, 'Continuous', 13, 'Cotas (entidades DIMENSION, estilo LAVA-50)', True),
    ('A-COTA-DEMO', 1, 'Continuous', 13, 'Cotas del estado Marna’s y corrimiento (lámina A-102)', False),
    ('A-NOTA-CLAVE', 7, 'Continuous', 18, 'Notas clave numeradas (mismas que la lámina A-101)', True),
    ('A-TEXTO', 7, 'Continuous', 18, 'Textos, rótulo, notas y cuadros', True),
    ('S-SEGURIDAD', 1, 'Continuous', 25, 'Salidas, rótulos SALIDA, luces de emergencia, extintores, detectores, pulsadores', True),
    ('S-EGRESO', 230, 'LAVA_OCULTO', 18, 'Recorridos de egreso medidos (data/life_safety_calcs.json)', False),
    ('M-GAS', 40, 'LAVA_GAS', 35, 'Gas de la red del centro comercial: acometida, llaves, solenoide, manifold (esquemático)', True),
    ('M-EXTRACCION', 6, 'Continuous', 35, 'Extracción EXT-1 / EXT-2 y chimenea EXT-3: collarines y ductos verticales', True),
    ('M-AIRE', 140, 'Continuous', 25, 'Aire de reposición AR-1 (difusores y riser propuesto de M-102)', True),
    ('P-SANITARIO', 5, 'Continuous', 25, 'Artefactos sanitarios, trampa de grasa, puntos húmedos existentes WP, desagües', True),
    ('E-TABLERO', 200, 'Continuous', 35, 'Tablero eléctrico y espacio de trabajo', True),
]
LAYER_SPEC = {row[0]: row for row in LAYERS}

# linetypes in metres (1:50 print -> 0.10 m = 2 mm)
LINETYPES = [
    ('LAVA_EJE', [0.9, 0.6, -0.1, 0.1, -0.1], 'Eje  ____ _ ____ _'),
    ('LAVA_DEMOL', [0.18, 0.12, -0.06], 'Demolición __ __ __'),
    ('LAVA_OCULTO', [0.21, 0.15, -0.06], 'Proyección / en altura ___ ___'),
    ('LAVA_FINO', [0.09, 0.06, -0.03], 'Fino _ _ _ _'),
    ('LAVA_GAS', [0.40, 0.28, -0.05, 0.02, -0.05], 'Gas ____ . ____ .'),
    ('LAVA_COND', [0.24, 0.14, -0.04, 0.02, -0.04], 'Condicional ___ . ___ .'),
]

LH = 1.6            # line pitch / text height
OVERALL_Y = -1.72   # existing-file overall width dimension line (between A-102 chains and the axis dimensions)
H_TAG = 0.065       # in-plan tags
H_EQ = (0.075, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045)
DIM_H = 0.075
ROTULO_W, ROTULO_H = 10.0, 3.6
PLUMB_KEYS = ('sink', 'handwash', 'grease')


# ------------------------------------------------------------------------------------------------ small helpers
def P(x, y):
    """data (Y down) -> DXF (Y up)."""
    return (float(x), -float(y))


def nrect(r):
    x0, y0, x1, y1 = r
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def polys(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == 'Polygon':
        return [g] if g.area > 1e-5 else []
    return [p for gg in getattr(g, 'geoms', []) for p in polys(gg)]


def tw(s, h, bold=False):
    """Conservative text width (m) for a TEXT of cap height h."""
    return len(str(s)) * h * (0.84 if bold else 0.78)


ACC_FIX = {'salon': 'salón', 'comun': 'común', 'extraccion': 'extracción', 'division': 'división', 'collarin': 'collarín',
           'maquina': 'máquina', 'cafe': 'café', 'Geometria': 'Geometría', 'extraida': 'extraída', 'ahi': 'ahí', 'area': 'área',
           'Area': 'Área', 'administracion': 'administración', 'demolicion': 'demolición', 'ubicacion': 'ubicación'}
_ACC_RE = re.compile(r'\b(' + '|'.join(ACC_FIX) + r')\b')


def acc(s):
    """Restore Spanish accents in survey notes copied from existing.json (whole words only)."""
    return _ACC_RE.sub(lambda m: ACC_FIX[m.group(1)], str(s))


def fix_layout_labels(lay):
    """In-memory wording fixes for the drawing only (layout.json is not modified): K3 is mandatory (DE 37308-S)."""
    for e in lay.get('equipment', []):
        if str(e.get('key', '')).startswith('handwash') and '(recomendado)' in str(e.get('label', '')):
            e['label'] = e['label'].replace('(recomendado)', '(obligatorio)')
            if str(e.get('note', '')).startswith('Recomendado'):
                e['note'] = 'Obligatorio (DE 37308-S, verificar)' + e['note'][len('Recomendado'):]
    return lay


def hex_rgb(c):
    c = (c or '#777777').lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def fit(s, width, h, bold=False):
    s = str(s)
    if tw(s, h, bold) <= width:
        return s
    n = max(1, int(width / (h * (0.84 if bold else 0.78))) - 1)
    return s[:n].rstrip() + '…'


def dim_text_box(a, b, off, label, lpos=0.5):
    """Footprint of a linear dimension's text (same geometry as Dwg.dim registers)."""
    (x1, y1), (x2, y2) = a, b
    horiz = abs(x2 - x1) >= abs(y2 - y1)
    shown = label if label is not None else f"{(abs(x2 - x1) if horiz else abs(y2 - y1)):.2f}"
    wt = tw(shown, DIM_H) + 0.06
    k = 0.03 + DIM_H * 1.3            # either side of the dimension line (the DXF is mirrored in Y)
    if horiz:
        ly, cx = y1 + off, x1 + (x2 - x1) * lpos
        return box(cx - wt / 2, ly - k, cx + wt / 2, ly + k)
    lx, cy = x1 + off, y1 + (y2 - y1) * lpos
    return box(lx - k, cy - wt / 2, lx + k, cy + wt / 2)


def first_sentence(s, n=150):
    s = (s or '').strip()
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + '…'


def eq_size_m(e):
    x0, y0, x1, y1 = nrect(e['rect'])
    wd, dp = x1 - x0, y1 - y0
    fr = e.get('front')
    if fr in ('N', 'S'):
        a, b = wd, dp
    elif fr in ('E', 'W'):
        a, b = dp, wd
    else:
        a, b = max(wd, dp), min(wd, dp)
    return f"{a:.2f}×{b:.2f}×{float(e.get('h') or 0):.2f}" + ('*' if e.get('tbv') else '')


def eq_layer(e):
    if e.get('overhead'):
        return 'A-EQUIPO-ALTO'
    if any(k in (e.get('key') or '') for k in PLUMB_KEYS):
        return 'P-SANITARIO'
    return 'A-EQUIPO'


def optional_json(name):
    p = os.path.join(ROOT, 'data', name)
    try:
        return load_json(p) if os.path.exists(p) else None
    except Exception:          # a half-written file from another tool must not break the export
        return None


DIRV = {'E': (1, 0), 'W': (-1, 0), 'S': (0, 1), 'N': (0, -1), 'SE': (1, 1), 'NE': (1, -1), 'SW': (-1, 1), 'NW': (-1, -1)}


class Placer:
    """Greedy label placement: hard obstacles (texts, walls, symbols) and soft ones (equipment, furniture)."""

    def __init__(self):
        self.hard, self.soft = [], []

    def add(self, g, hard=True):
        if g is not None and not g.is_empty:
            (self.hard if hard else self.soft).append(g)

    def cost(self, g):
        c = 0.0
        for b in self.hard:
            if g.intersects(b):
                c += 1000 * (g.intersection(b).area + 0.002)
        for b in self.soft:
            if g.intersects(b):
                c += g.intersection(b).area + 0.001
        return c


# ------------------------------------------------------------------------------------------------ drawing context
class Dwg:
    def __init__(self, descriptions=None):
        self.descriptions = descriptions or {}
        doc = self.doc = ezdxf.new('R2018', setup=False)
        doc.units = units.M
        hdr = doc.header
        for k, v in (('$MEASUREMENT', 1), ('$LUNITS', 2), ('$LUPREC', 3), ('$AUNITS', 0), ('$AUPREC', 1),
                     ('$LTSCALE', 1.0), ('$PSLTSCALE', 0), ('$MSLTSCALE', 0), ('$TEXTSIZE', 0.1), ('$LWDISPLAY', 1),
                     ('$INSUNITS', 6)):
            try:
                hdr[k] = v
            except Exception:
                pass
        for name, pat, desc in LINETYPES:
            doc.linetypes.add(name, pattern=pat, description=desc)
        doc.styles.add('LAVA', font='arial.ttf')
        doc.styles.add('LAVA-B', font='arialbd.ttf')
        hdr['$TEXTSTYLE'] = 'LAVA'
        ds = doc.dimstyles.add('LAVA-50', dxfattribs={
            'dimtxt': DIM_H, 'dimasz': 0.06, 'dimexo': 0.03, 'dimexe': 0.06, 'dimgap': 0.025, 'dimdle': 0.05,
            'dimtad': 1, 'dimjust': 0, 'dimdec': 2, 'dimzin': 0, 'dimlunit': 2, 'dimdsep': ord('.'), 'dimtih': 0,
            'dimtoh': 0, 'dimtofl': 1, 'dimatfit': 3, 'dimtmove': 0, 'dimscale': 1.0, 'dimlfac': 1.0,
            'dimclrd': 256, 'dimclre': 256, 'dimclrt': 256, 'dimtxsty': 'LAVA'})   # no DIMRND (ezdxf rounds 0.0 to integers)
        ds.set_arrows(blk=ezdxf.ARROWS.architectural_tick)
        hdr['$DIMSTYLE'] = 'LAVA-50'
        doc.ucs.add('LAVA-DATOS', dxfattribs={'origin': (0, 0, 0), 'xaxis': (1, 0, 0), 'yaxis': (0, -1, 0)})
        self.msp = doc.modelspace()
        self.pl = Placer()
        self.used_blocks = set()
        self._blocks()

    # --------------------------------------------------------------- layers
    def L(self, name):
        if name not in self.doc.layers:
            _, aci, lt, lw, desc, on = LAYER_SPEC[name]
            lay = self.doc.layers.add(name, color=aci, linetype=lt, lineweight=lw)
            lay.description = self.descriptions.get(name, desc)
            if not on:
                lay.off()
        return name

    def attrs(self, layer, **kw):
        a = {'layer': self.L(layer)}
        rgb = kw.pop('rgb', None)
        if rgb is not None:
            a['true_color'] = ezcolors.rgb2int(rgb)
        a.update({k: v for k, v in kw.items() if v is not None})
        return a

    # --------------------------------------------------------------- primitives (data coordinates in, DXF out)
    def poly(self, pts, layer, close=False, **kw):
        return self.msp.add_lwpolyline([P(*p) for p in pts], close=close, dxfattribs=self.attrs(layer, **kw))

    def rect(self, r, layer, **kw):
        x0, y0, x1, y1 = nrect(r)
        return self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer, close=True, **kw)

    def line(self, a, b, layer, **kw):
        return self.msp.add_line(P(*a), P(*b), dxfattribs=self.attrs(layer, **kw))

    def circle(self, c, r, layer, **kw):
        return self.msp.add_circle(P(*c), r, dxfattribs=self.attrs(layer, **kw))

    def arc(self, c, p_from, p_to, layer, **kw):
        cx, cy = P(*c)
        ax, ay = P(*p_from)
        bx, by = P(*p_to)
        r = math.hypot(ax - cx, ay - cy)
        a0 = math.degrees(math.atan2(ay - cy, ax - cx))
        a1 = math.degrees(math.atan2(by - cy, bx - cx))
        d = (a1 - a0 + 180) % 360 - 180
        s, e = (a0, a1) if d > 0 else (a1, a0)
        return self.msp.add_arc((cx, cy), r, s, e, dxfattribs=self.attrs(layer, **kw))

    def text(self, s, x, y, h, layer, rot=0, align='MIDDLE_CENTER', bold=False, **kw):
        t = self.msp.add_text(acc(s), height=h, rotation=rot,
                              dxfattribs=self.attrs(layer, style='LAVA-B' if bold else 'LAVA', **kw))
        t.set_placement(P(x, y), align=TextEntityAlignment[align])
        return t

    def lines(self, lines, x, y, h, layer, rot=0, bold_first=True, align='MIDDLE_CENTER', **kw):
        """Stack of TEXT lines centred on (x, y); rot 0 or 90 (reading upwards)."""
        n = len(lines)
        for i, s in enumerate(lines):
            off = (i - (n - 1) / 2) * h * LH
            px, py = (x + off, y) if rot else (x, y + off)
            self.text(s, px, py, h, layer, rot=rot, bold=bold_first and i == 0, align=align, **kw)

    @staticmethod
    def lines_box(lines, x, y, h, rot=0, bold_first=True, pad=0.02):
        w = max(tw(s, h, bold_first and i == 0) for i, s in enumerate(lines))
        ht = len(lines) * h * LH
        if rot:
            w, ht = ht, w
        return box(x - w / 2 - pad, y - ht / 2 - pad, x + w / 2 + pad, y + ht / 2 + pad)

    def mtext(self, s, x, y, h, width, layer, bold=False, **kw):
        s = acc(s).replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}').replace('\n', '\\P')
        m = self.msp.add_mtext(s, dxfattribs=self.attrs(layer, style='LAVA-B' if bold else 'LAVA', char_height=h,
                                                       width=width, **kw))
        m.set_location(P(x, y), attachment_point=MTextEntityAlignment.TOP_LEFT)
        nl = sum(max(1, math.ceil(tw(par, h, bold) / width)) for par in str(s).split('\\P'))
        return nl * h * 1.67

    def outline(self, geom, layer, **kw):
        for p in polys(geom):
            self.poly(list(p.exterior.coords)[:-1], layer, close=True, **kw)
            for ring in p.interiors:
                self.poly(list(ring.coords)[:-1], layer, close=True, **kw)

    def hatch(self, geom, layer, pattern=None, scale=0.02, angle=0.0, rgb=None, transparency=None):
        ps = polys(geom)
        if not ps:
            return None
        h = self.msp.add_hatch(dxfattribs=self.attrs(layer, rgb=rgb))
        if pattern:
            h.set_pattern_fill(pattern, color=256, scale=scale, angle=angle)
        else:
            h.set_solid_fill(color=256)
        if rgb is not None:
            h.rgb = rgb
        for p in ps:
            h.paths.add_polyline_path([P(*c) for c in list(p.exterior.coords)[:-1]], is_closed=True, flags=1)
            for ring in p.interiors:
                h.paths.add_polyline_path([P(*c) for c in list(ring.coords)[:-1]], is_closed=True, flags=0)
        if transparency is not None:
            h.transparency = transparency
        return h

    def arrow(self, tip, u, layer, length=0.16, half=0.06, **kw):
        ux, uy = u
        tri = Polygon([tip, (tip[0] - ux * length - uy * half, tip[1] - uy * length + ux * half),
                       (tip[0] - ux * length + uy * half, tip[1] - uy * length - ux * half)])
        self.hatch(tri, layer, **kw)
        self.outline(tri, layer, linetype='Continuous')

    def insert(self, name, at, layer, attribs=None, rot=0.0, scale=1.0):
        self.used_blocks.add(name)
        ref = self.msp.add_blockref(name, P(*at), dxfattribs=self.attrs(layer, rotation=rot, xscale=scale,
                                                                         yscale=scale))
        if attribs:
            ref.add_auto_attribs({k: str(v) for k, v in attribs.items()})
            for a in ref.attribs:
                a.dxf.layer = layer
        return ref

    def dim(self, a, b, off, label, layer, lpos=0.5, register=True):
        (x1, y1), (x2, y2) = a, b
        horiz = abs(x2 - x1) >= abs(y2 - y1)
        L = abs(x2 - x1) if horiz else abs(y2 - y1)
        fmt = f"{L:.2f}"
        if label is None or label == fmt:
            txt = '<>'
        elif label.startswith(fmt):
            txt = '<>' + label[len(fmt):]
        else:
            txt = label
        base = P(x1, y1 + off) if horiz else P(x1 + off, y1)
        loc = None
        ov = None
        if abs(lpos - 0.5) > 1e-6:
            if horiz:
                loc = P(x1 + (x2 - x1) * lpos, y1 + off - DIM_H * 0.9)
            else:
                loc = P(x1 + off - DIM_H * 0.9, y1 + (y2 - y1) * lpos)
            ov = {'dimtmove': 2}
        d = self.msp.add_linear_dim(base=base, p1=P(*a), p2=P(*b), location=loc, text=txt, angle=0 if horiz else 90,
                                    dimstyle='LAVA-50', override=ov, dxfattribs={'layer': self.L(layer)})
        d.render()
        if register:
            shown = (label if label is not None else fmt)
            wt = tw(shown, DIM_H) + 0.06
            if horiz:
                ly = y1 + off
                self.pl.add(box(min(x1, x2), ly - 0.02, max(x1, x2), ly + 0.02))
                cx = x1 + (x2 - x1) * lpos
                self.pl.add(box(cx - wt / 2, ly - 0.03 - DIM_H * 1.3, cx + wt / 2, ly))
            else:
                lx = x1 + off
                self.pl.add(box(lx - 0.02, min(y1, y2), lx + 0.02, max(y1, y2)))
                cy = y1 + (y2 - y1) * lpos
                self.pl.add(box(lx - 0.03 - DIM_H * 1.3, cy - wt / 2, lx, cy + wt / 2))
        return d

    # --------------------------------------------------------------- flexible labels
    def place(self, lines, anchor, h=H_TAG, layer='A-TEXTO', r0=0.08, dirs=None, rings=6, step=0.12, leader=True,
              bold_first=True, rot=0, cands=None, inside=None, sym_r=None, **kw):
        ax, ay = anchor
        w = max(tw(s, h, bold_first and i == 0) for i, s in enumerate(lines))
        ht = len(lines) * h * LH
        bw, bh = (ht, w) if rot else (w, ht)
        if cands is None:
            cands = []
            for ring in range(rings):
                d = r0 + ring * step
                for k, dn in enumerate(dirs or ['E', 'W', 'S', 'N', 'SE', 'NE', 'SW', 'NW']):
                    ux, uy = DIRV[dn]
                    cands.append((ring * 0.05 + k * 0.001, ax + ux * (d + bw / 2), ay + uy * (d + bh / 2)))
        best = None
        for pen, cx, cy in cands:
            g = box(cx - bw / 2 - 0.015, cy - bh / 2 - 0.015, cx + bw / 2 + 0.015, cy + bh / 2 + 0.015)
            c = self.pl.cost(g) + pen
            if inside is not None:
                c += 1000 * g.difference(inside).area
            if best is None or c < best[0]:
                best = (c, cx, cy, g)
        _, cx, cy, g = best
        self.lines(lines, cx, cy, h, layer, rot=rot, bold_first=bold_first, **kw)
        self.pl.add(g)
        sr = r0 * 0.8 if sym_r is None else sym_r          # radius of the symbol at the anchor
        gap = g.distance(Point(ax, ay))
        if leader and gap - sr > 0.1:
            gb = g.exterior
            q = gb.interpolate(gb.project(Point(ax, ay)))
            L = math.hypot(q.x - ax, q.y - ay) or 1
            a0 = (ax + (q.x - ax) / L * sr, ay + (q.y - ay) / L * sr)
            self.line(a0, (q.x, q.y), layer, lineweight=9, **{k: v for k, v in kw.items() if k == 'rgb'})
        return cx, cy

    # --------------------------------------------------------------- blocks (symbols in metres, layer 0 = ByBlock)
    def _blocks(self):
        doc = self.doc

        def blk(name):
            b_ = doc.blocks.new(name=name, base_point=(0, 0))
            b_.block_record.dxf.units = 6          # metres
            return b_

        def attdef(b, tag, x, y, h, bold=False, align='MIDDLE_CENTER', default=''):
            a = b.add_attdef(tag, (x, y), height=h, text=default,
                             dxfattribs={'layer': '0', 'style': 'LAVA-B' if bold else 'LAVA'})
            a.set_placement((x, y), align=TextEntityAlignment[align])
            return a

        def txt(b, s, x, y, h, bold=True, align='MIDDLE_CENTER'):
            t = b.add_text(s, height=h, dxfattribs={'layer': '0', 'style': 'LAVA-B' if bold else 'LAVA'})
            t.set_placement((x, y), align=TextEntityAlignment[align])

        def rect(b, w, h, cx=0.0, cy=0.0):
            b.add_lwpolyline([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2),
                              (cx - w / 2, cy + h / 2)], close=True, dxfattribs={'layer': '0'})

        b = blk('LAVA-SALIDA')                       # illuminated exit sign
        rect(b, 0.38, 0.15)
        txt(b, 'SALIDA', 0, 0, 0.06)
        b = blk('LAVA-LUZ-EMERG')                    # twin-head emergency light
        rect(b, 0.26, 0.09)
        for sx_ in (-0.07, 0.07):
            b.add_circle((sx_, 0), 0.03, dxfattribs={'layer': '0'})
        b = blk('LAVA-EXTINTOR')
        b.add_circle((0, 0), 0.12, dxfattribs={'layer': '0'})
        b.add_lwpolyline([(-0.085, -0.085), (0.085, -0.085)], dxfattribs={'layer': '0'})
        attdef(b, 'CLASE', 0, 0.01, 0.055, bold=True, default='ABC')
        b = blk('LAVA-DETECTOR')
        b.add_circle((0, 0), 0.10, dxfattribs={'layer': '0'})
        attdef(b, 'TIPO', 0, 0, 0.05, bold=True, default='DH')
        b = blk('LAVA-PULSADOR')
        rect(b, 0.18, 0.18)
        txt(b, 'PM', 0, 0, 0.06)
        b = blk('LAVA-VALVULA')                      # gas valve (bow-tie)
        b.add_lwpolyline([(-0.08, -0.05), (0.08, 0.05), (0.08, -0.05), (-0.08, 0.05)], close=True,
                         dxfattribs={'layer': '0'})
        b = blk('LAVA-SOLENOIDE')
        b.add_lwpolyline([(-0.08, -0.05), (0.08, 0.05), (0.08, -0.05), (-0.08, 0.05)], close=True,
                         dxfattribs={'layer': '0'})
        b.add_line((0, 0), (0, 0.10), dxfattribs={'layer': '0'})
        rect(b, 0.09, 0.07, 0, 0.135)
        b = blk('LAVA-DIFUSOR')                      # supply diffuser
        rect(b, 0.40, 0.40)
        rect(b, 0.22, 0.22)
        for sgn in (-1, 1):
            b.add_line((-0.2, sgn * -0.2), (0.2, sgn * 0.2), dxfattribs={'layer': '0'})
        b = blk('LAVA-DUCTO-V')                      # vertical duct / riser
        b.add_circle((0, 0), 0.13, dxfattribs={'layer': '0'})
        for sgn in (-1, 1):
            b.add_line((-0.092, sgn * -0.092), (0.092, sgn * 0.092), dxfattribs={'layer': '0'})
        b = blk('LAVA-DESAGUE')                      # floor drain
        b.add_circle((0, 0), 0.07, dxfattribs={'layer': '0'})
        b.add_line((-0.07, 0), (0.07, 0), dxfattribs={'layer': '0'})
        b.add_line((0, -0.07), (0, 0.07), dxfattribs={'layer': '0'})
        b = blk('LAVA-EJE')
        b.add_circle((0, 0), 0.2, dxfattribs={'layer': '0'})
        attdef(b, 'EJE', 0, 0, 0.17, bold=True, default='A')
        # title block with editable attributes (block units: m; origin = top-left corner)
        b = blk('LAVA-ROTULO')
        W, H, D = ROTULO_W, ROTULO_H, 7.0
        b.add_lwpolyline([(0, 0), (W, 0), (W, -H), (0, -H)], close=True, dxfattribs={'layer': '0', 'lineweight': 50})
        b.add_line((D, 0), (D, -H), dxfattribs={'layer': '0'})
        b.add_line((0, -2.55), (D, -2.55), dxfattribs={'layer': '0'})
        txt(b, 'LAVA', 0.25, -0.62, 0.42, align='LEFT')
        txt(b, 'CONTEMPORARY FIRE & BBQ', 1.95, -0.62, 0.11, align='LEFT')
        attdef(b, 'PROYECTO', 0.25, -0.98, 0.1, bold=True, align='LEFT')
        attdef(b, 'UBICACION', 0.25, -1.24, 0.08, align='LEFT')
        attdef(b, 'DOCUMENTO', 0.25, -1.62, 0.15, bold=True, align='LEFT')
        attdef(b, 'ESTADO', 0.25, -1.95, 0.085, bold=True, align='LEFT')
        attdef(b, 'NOTA', 0.25, -2.2, 0.075, align='LEFT')
        attdef(b, 'ESCALA', 0.25, -2.85, 0.075, align='LEFT')
        attdef(b, 'VERSION', 0.25, -3.1, 0.075, align='LEFT')
        attdef(b, 'ARCHIVO', 0.25, -3.35, 0.075, align='LEFT')
        txt(b, 'PROFESIONAL RESPONSABLE (CFIA)', D + 0.2, -0.35, 0.08, align='LEFT')
        attdef(b, 'PROFESIONAL', D + 0.2, -0.75, 0.075, align='LEFT', default='Nombre: ________________')
        attdef(b, 'CARNE_CFIA', D + 0.2, -1.05, 0.075, align='LEFT', default='Carné CFIA: __________')
        attdef(b, 'DISCIPLINA', D + 0.2, -1.35, 0.075, align='LEFT', default='Disciplina: arquitectura')
        txt(b, 'Firma / sello:', D + 0.2, -1.75, 0.075, bold=False, align='LEFT')
        b.add_lwpolyline([(D + 0.2, -1.9), (W - 0.2, -1.9), (W - 0.2, -3.35), (D + 0.2, -3.35)], close=True,
                         dxfattribs={'layer': '0', 'linetype': 'LAVA_FINO'})

    def sym_box(self, at, w, h):
        x, y = at
        return box(x - w / 2, y - h / 2, x + w / 2, y + h / 2)


# ------------------------------------------------------------------------------------------------ plan content
def draw_axes(dw, ex, geo_bounds):
    ax = ex['meta']['axes']
    minx, miny, maxx, maxy = geo_bounds
    top, left = miny - 1.65, minx - 1.35
    for name in ('A', 'B', 'C'):
        if name not in ax:
            continue
        x = ax[name]
        dw.line((x, top + 0.2), (x, maxy + 0.25), 'A-EJE')
        dw.insert('LAVA-EJE', (x, top), 'A-EJE', {'EJE': name})
        dw.pl.add(box(x - 0.22, top - 0.22, x + 0.22, top + 0.22))
    for name, key in (('1', 'row1'), ('2', 'row2')):
        if key not in ax:
            continue
        y = ax[key]
        dw.line((left + 0.2, y), (maxx + 0.25, y), 'A-EJE')
        dw.insert('LAVA-EJE', (left, y), 'A-EJE', {'EJE': name})
        dw.pl.add(box(left - 0.22, y - 0.22, left + 0.22, y + 0.22))
    # axis-to-axis dimensions (existing structure)
    xs = [ax[k] for k in ('A', 'B', 'C') if k in ax]
    for a_, b_ in zip(xs, xs[1:]):
        dw.dim((a_, top + 0.2), (b_, top + 0.2), 0.3, None, 'A-COTA')


def wall_regions(ex, lay, proposal):
    items = standing_existing_walls(ex, lay) if proposal else [(w, R(w['rect'])) for w in ex['walls']]
    shafts = unary_union([R(s['rect']) for s in ex['shafts']])
    cols = unary_union([R(c['rect']) for c in ex['columns']])
    cut = shafts.union(cols)
    allg = unary_union([g for _, g in items]).difference(cut).simplify(0.0005)
    hatched = unary_union([g for w, g in items if w.get('hatched', True)]).difference(cut).simplify(0.0005)
    return allg, hatched


def draw_structure(dw, ex, lay, proposal):
    """Stair, shafts, existing walls, columns, glazing (common to both files)."""
    st = ex['stair']
    dw.rect(st['outline'], 'A-ESCALERA')
    for fl in st['flights']:
        x0, y0, x1, y1 = nrect(fl)
        n = int(round((y1 - y0) / st['tread']))
        for i in range(n + 1):
            yy = y0 + i * st['tread']
            dw.line((x0, yy), (x1, yy), 'A-ESCALERA', lineweight=9)
    ox = nrect(st['outline'])
    cx = (ox[0] + ox[2]) / 2
    lower = max(fl[3] for fl in st['flights'])
    ty = (lower + ox[3]) / 2
    st_lines = ['ESCALERA EXISTENTE', '(edificio, fuera del local)']
    st_h = min(0.11, (ox[2] - ox[0] - 0.2) / max(tw(t_, 1.0, True) for t_ in st_lines))
    dw.lines(st_lines, cx, ty, st_h, 'A-ESCALERA')
    dw.pl.add(dw.lines_box(st_lines, cx, ty, st_h))
    cols = unary_union([R(c['rect']) for c in ex['columns']])
    for s in ex['shafts']:
        x0, y0, x1, y1 = nrect(s['rect'])
        dw.rect(s['rect'], 'A-DUCTO')
        for a, b in (((x0, y0), (x1, y1)), ((x0, y1), (x1, y0))):
            seg = LineString([a, b]).difference(cols)
            for part in getattr(seg, 'geoms', [seg]):
                if part.length > 0.01:
                    (pa, pb) = list(part.coords)[0], list(part.coords)[-1]
                    dw.line(pa, pb, 'A-DUCTO', lineweight=9)
    allg, hatched = wall_regions(ex, lay, proposal)
    dw.hatch(hatched, 'A-MURO-EXIST-TRAMA', pattern='ANSI31', scale=0.02)
    dw.outline(allg, 'A-MURO-EXIST')
    dw.pl.add(allg)
    for c in ex['columns']:
        dw.hatch(R(c['rect']), 'A-COLUMNA-TRAMA')
        dw.rect(c['rect'], 'A-COLUMNA')
        dw.pl.add(R(c['rect']))
    cuts = []
    if proposal:
        cuts = [(o, R(o['rect'])) for o in lay.get('new_openings', []) if o.get('rect')]
    for gl in ex['glazing']:
        g = R(gl['rect'])
        removed = []
        for o, og in cuts:
            if g.intersects(og) and g.intersection(og).area > 1e-5:
                removed.append((o, g.intersection(og)))
                g = g.difference(og)
        for p in polys(g):
            x0, y0, x1, y1 = p.bounds
            dw.rect((x0, y0, x1, y1), 'A-VIDRIO')
            if (x1 - x0) < (y1 - y0):
                dw.line(((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1), 'A-VIDRIO')
            else:
                dw.line((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2), 'A-VIDRIO')
        for o, rg in removed:        # glass replaced by a new opening -> demolition (conditional if the door is)
            dw.hatch(rg, 'A-MURO-DEMOL-TRAMA', pattern='ANSI31', scale=0.02, angle=90)
            dw.outline(rg, 'A-MURO-DEMOL')


def door_leaf(ex, lay, d):
    for e in (lay or {}).get('life_safety', {}).get('exits', []):
        if e.get('opening') == d['id'] and e.get('leaf'):
            return float(e['leaf'])
    m = re.search(r'(\d+\.\d+)', d.get('swing', ''))
    return float(m.group(1)) if m else d.get('width', 1.8) / 2


def draw_existing_doors(dw, ex, lay, proposal):
    prem = premises(ex)
    for d in ex['doors']:
        kind = d.get('kind')
        if kind == 'context':
            pts = [d['hinge']] if 'hinge' in d else d.get('hinges', [])
            for p in pts:
                dw.circle(p, 0.04, 'A-CONTEXTO')
            if pts:
                dw.place([f"{d['id']} (contexto, fuera del local)"], pts[0], h=0.055, layer='A-CONTEXTO', leader=False,
                         bold_first=False)
            continue
        if 'opening' not in d:
            continue
        x0, y0, x1, y1 = d['opening']
        if kind in ('double', 'door'):
            L = math.hypot(x1 - x0, y1 - y0)
            tx, ty = (x1 - x0) / L, (y1 - y0) / L
            nx, ny = -ty, tx
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            if not prem.contains(Point(mx + nx * 0.3, my + ny * 0.3)):
                nx, ny = -nx, -ny
            leaf = door_leaf(ex, lay, d)
            hinges = [((x0, y0), (tx, ty)), ((x1, y1), (-tx, -ty))] if kind == 'double' else [((x0, y0), (tx, ty))]
            for (hx, hy), (ux, uy) in hinges:
                open_tip = (hx + nx * leaf, hy + ny * leaf)
                closed_tip = (hx + ux * leaf, hy + uy * leaf)
                dw.line((hx, hy), open_tip, 'A-PUERTA', lineweight=35)
                dw.arc((hx, hy), closed_tip, open_tip, 'A-PUERTA', lineweight=13)
                dw.pl.add(LineString([(hx, hy), open_tip]).buffer(0.03))
            dw.line((x0, y0), (x1, y1), 'A-PUERTA', lineweight=9)
            lbl = f"{d['id']} · {d.get('width', L):.2f} ({len(hinges)} × {leaf:.2f})"
            dw.place([lbl], (mx - nx * 0.05, my - ny * 0.05), h=H_TAG, layer='A-PUERTA', rot=90 if abs(tx) < abs(ty) else 0,
                     dirs=['E', 'W'] if abs(nx) > 0 else ['N', 'S'], leader=False)
        elif not proposal:
            dw.line((x0, y0), (x1, y1), 'A-PUERTA', linetype='LAVA_FINO', lineweight=13)
            lbl = f"{d['id']} · {'ventana de paso' if kind == 'pass' else 'vano'} {d.get('width', 0):.2f}"
            dw.place([lbl], ((x0 + x1) / 2, (y0 + y1) / 2), h=0.055, layer='A-PUERTA', bold_first=False)


def draw_demolition(dw, ex, lay):
    gone = {d['id']: d for d in lay.get('demolish', []) if 'rect' not in d}
    items = []
    for w in ex['walls']:
        if w['id'] in gone:
            items.append((gone[w['id']], w['rect'], False))
    for d in lay.get('demolish', []):
        if 'rect' in d:
            items.append((d, d['rect'], True))
    for d, r, partial in items:
        g = R(r)
        dw.hatch(g, 'A-MURO-DEMOL-TRAMA', pattern='ANSI31', scale=0.02, angle=90)
        dw.outline(g, 'A-MURO-DEMOL')
    labels = []
    for d, r, partial in items:
        x0, y0, x1, y1 = nrect(r)
        tag = 'DEMOLER ' + d['id'] + (' (parcial)' if partial and not d.get('conditional') else '') + \
              (' (condicional)' if d.get('conditional') else '')
        labels.append((tag, ((x0 + x1) / 2, (y0 + y1) / 2), (y1 - y0) > max(x1 - x0, 0.3)))
    for o in lay.get('remove_items', []):
        dw.rect(o['rect'], 'A-RETIRO')
    return labels


def draw_new_walls(dw, lay):
    door_types = ('door', 'double_acting_door', 'sliding_door', 'service_door', 'opening')
    ops = unary_union([R(o['rect']) for o in lay.get('new_openings', []) if o.get('rect') and o.get('type') in door_types])
    labels = []
    for w in lay.get('new_walls', []):
        g = R(w['rect']).difference(ops) if not ops.is_empty else R(w['rect'])
        dw.hatch(g, 'A-MURO-NUEVO-TRAMA')
        dw.outline(g, 'A-MURO-NUEVO')
        dw.pl.add(g)
        x0, y0, x1, y1 = nrect(w['rect'])
        vert = (x1 - x0) < (y1 - y0)
        if w.get('type') == 'glass_partition':
            for p in polys(g):
                bx0, by0, bx1, by1 = p.bounds
                if vert:
                    dw.line(((x0 + x1) / 2, by0 + 0.03), ((x0 + x1) / 2, by1 - 0.03), 'A-VIDRIO', lineweight=35)
                else:
                    dw.line((bx0 + 0.03, (y0 + y1) / 2), (bx1 - 0.03, (y0 + y1) / 2), 'A-VIDRIO', lineweight=35)
        h = w.get('h')
        base = w.get('base_h')
        extra = f" · base h {base:.2f}" if base else ''
        labels.append(([f"{w['id']} · {w.get('short') or w.get('type')}", f"h {h:.2f}{extra}" if h else w.get('type')],
                       g.representative_point().coords[0], vert, g))
    return labels


def draw_new_openings(dw, lay):
    labels = []
    for o in lay.get('new_openings', []):
        if not o.get('rect'):
            continue
        t = o.get('type')
        layer = 'A-PUERTA-COND' if o.get('conditional') else 'A-PUERTA'
        x0, y0, x1, y1 = nrect(o['rect'])
        if 'hinge' in o and 'swing_to' in o and 'closed_to' in o:
            h, s, c = o['hinge'], o['swing_to'], o['closed_to']
            dw.line(h, s, layer, lineweight=35)
            dw.arc(h, c, s, layer, lineweight=13)
            dw.pl.add(LineString([h, s]).buffer(0.03))
        elif t == 'double_acting_door':
            vert = (x1 - x0) < (y1 - y0)
            if vert:
                c_ = (x0 + x1) / 2
                L = y1 - y0
                hinge, tip = (c_, y1), (c_, y0)
                ends = [(c_ - L, y1), (c_ + L, y1)]
            else:
                c_ = (y0 + y1) / 2
                L = x1 - x0
                hinge, tip = (x1, c_), (x0, c_)
                ends = [(x1, c_ - L), (x1, c_ + L)]
            dw.line(hinge, tip, layer, lineweight=35)
            for e in ends:
                dw.arc(hinge, tip, e, layer, lineweight=13)
            dw.pl.add(LineString([hinge, tip]).buffer(0.03))
        cond = ' · CONDICIONAL' if o.get('conditional') else ''
        kind = {'double_acting_door': 'vaivén', 'service_door': 'servicio', 'door': 'puerta'}.get(t, t)
        labels.append(([f"{o.get('label', o['id'])} · {kind} {o.get('width', 0.9):.2f}{cond}"], ((x0 + x1) / 2, (y0 + y1) / 2),
                       layer))
    return labels


def draw_zones_fill(dw, ex, lay):
    prem = premises(ex)
    out = []
    for z in lay.get('zones', []):
        rgb = hex_rgb(z.get('color'))
        poly = Polygon(z['poly'])
        clip = poly.intersection(prem)
        dw.hatch(clip, 'A-ZONA-TRAMA', rgb=rgb, transparency=0.88)
        dw.poly(z['poly'], 'A-ZONA', close=True, rgb=rgb)
        out.append((z, clip.area, rgb, clip))
    return out


def draw_zone_labels(dw, zones):
    """Big zone name + area, as close as possible to zone.label_at without covering symbols / equipment."""
    for z, area, rgb, clip in zones:
        at = z.get('label_at') or clip.representative_point().coords[0]
        lines = z.get('label_lines') or [z.get('short', z.get('name', z['id']))]
        sub = f"ZONA {z['id']} · ≈ {area:.1f} m²"
        n = len(lines)
        for k in (1.0, 0.85, 0.72, 0.6, 0.5):
            h = z.get('label_size', 5.0) / 20 * 0.58 * k
            hs = max(0.05, 0.065 * min(1.0, k + 0.15))
            w = max([tw(s, h, True) for s in lines] + [tw(sub, hs, True)])
            ht = n * h * 1.3 + hs * 1.5 + 0.04
            best = None
            for i in range(-10, 11):
                for j in range(-8, 9):
                    cx, cy = at[0] + i * 0.1, at[1] + j * 0.1
                    g = box(cx - w / 2 - 0.04, cy - ht / 2 - 0.04, cx + w / 2 + 0.04, cy + ht / 2 + 0.04)
                    c = dw.pl.cost(g) + 1000 * g.difference(clip).area + 0.02 * math.hypot(i, j)
                    if best is None or c < best[0]:
                        best = (c, cx, cy, g)
            if best[0] < 1.0:
                break
        _, cx, cy, g = best
        top = cy - ht / 2
        for i, s in enumerate(lines):
            dw.text(s, cx, top + h * 0.65 + i * h * 1.3, h, 'A-ZONA', bold=True, rgb=rgb)
        dw.text(sub, cx, top + n * h * 1.3 + hs * 0.9 + 0.02, hs, 'A-ZONA', bold=True, rgb=rgb)
        dw.pl.add(g)


def draw_furniture(dw, lay):
    for b in lay.get('banquettes', []):
        x0, y0, x1, y1 = nrect(b['rect'])
        dw.rect(b['rect'], 'A-MOBILIARIO')
        dw.pl.add(R(b['rect']), hard=False)
        back = b.get('back')
        t = 0.13
        horiz = (x1 - x0) >= (y1 - y0)
        strip = {'N': (x0, y0, x1, y0 + t), 'S': (x0, y1 - t, x1, y1), 'W': (x0, y0, x0 + t, y1), 'E': (x1 - t, y0, x1, y1)}.get(back)
        if strip:
            sx0, sy0, sx1, sy1 = strip
            if back == 'N':
                dw.line((x0, sy1), (x1, sy1), 'A-MOBILIARIO')
            elif back == 'S':
                dw.line((x0, sy0), (x1, sy0), 'A-MOBILIARIO')
            elif back == 'W':
                dw.line((sx1, y0), (sx1, y1), 'A-MOBILIARIO')
            else:
                dw.line((sx0, y0), (sx0, y1), 'A-MOBILIARIO')
        n = int(b.get('seats', 0))
        for i in range(1, n):                                   # individual seat dividers
            f_ = i / n
            if horiz:
                xx = x0 + f_ * (x1 - x0)
                ya, yb = (strip[3], y1) if back == 'N' else (y0, strip[1]) if back == 'S' else (y0, y1)
                dw.line((xx, ya), (xx, yb), 'A-MOBILIARIO', lineweight=9)
            else:
                yy = y0 + f_ * (y1 - y0)
                xa, xb = (strip[2], x1) if back == 'W' else (x0, strip[0]) if back == 'E' else (x0, x1)
                dw.line((xa, yy), (xb, yy), 'A-MOBILIARIO', lineweight=9)
        if strip:
            lbl = f"{b['id']} · banca corrida · {n} asientos individuales · fondo {min(x1 - x0, y1 - y0):.2f}"
            sx0, sy0, sx1, sy1 = strip
            hh = min(0.06, (min(sx1 - sx0, sy1 - sy0) - 0.02) / 1.3)
            dw.text(lbl, (sx0 + sx1) / 2, (sy0 + sy1) / 2, hh, 'A-MOBILIARIO', rot=0 if horiz else 90)
    for t in lay.get('tables', []):
        x0, y0, x1, y1 = nrect(t['rect'])
        dw.rect(t['rect'], 'A-MOBILIARIO')
        dw.pl.add(R(t['rect']))
        tag = t.get('tag', t['id'])
        dims_ = f"{t['seats']}p · {(x1 - x0) * 100:.0f}×{(y1 - y0) * 100:.0f}"
        ls = [tag, 'ACCESIBLE', dims_] if t.get('accessible') else [tag, dims_]
        h = 0.06
        while h > 0.04 and (max(tw(s, h, True) for s in ls) > (x1 - x0) - 0.06 or len(ls) * h * LH > (y1 - y0) - 0.04):
            h -= 0.005
        dw.lines(ls, (x0 + x1) / 2, (y0 + y1) / 2, h, 'A-MOBILIARIO')
        if t.get('accessible'):
            dw.rect((x0 - 0.03, y0 - 0.03, x1 + 0.03, y1 + 0.03), 'A-MOBILIARIO', linetype='LAVA_FINO')
    for c in lay.get('chairs', []):
        x0, y0, x1, y1 = nrect(c['rect'])
        dw.rect(c['rect'], 'A-MOBILIARIO', lineweight=13)
        dw.pl.add(R(c['rect']), hard=False)
        t_ = 0.07
        seg = {'S': ((x0 + 0.04, y0 + t_), (x1 - 0.04, y0 + t_)), 'N': ((x0 + 0.04, y1 - t_), (x1 - 0.04, y1 - t_)),
               'E': ((x0 + t_, y0 + 0.04), (x0 + t_, y1 - 0.04)), 'W': ((x1 - t_, y0 + 0.04), (x1 - t_, y1 - 0.04))}.get(c.get('facing'))
        if seg:
            dw.line(seg[0], seg[1], 'A-MOBILIARIO', lineweight=13)


def draw_decor(dw, lay):
    for d in lay.get('decor', []):
        r = d.get('rect')
        if not r:
            continue
        x0, y0, x1, y1 = nrect(r)
        t = d.get('type')
        if t == 'pendant':
            c = ((x0 + x1) / 2, (y0 + y1) / 2)
            rr = max(x1 - x0, y1 - y0) / 2
            dw.circle(c, rr, 'A-DECOR')
            dw.line((c[0] - rr, c[1]), (c[0] + rr, c[1]), 'A-DECOR', lineweight=9)
            dw.line((c[0], c[1] - rr), (c[0], c[1] + rr), 'A-DECOR', lineweight=9)
        else:
            dw.rect(r, 'A-DECOR')
            if t == 'slat_wall':
                n = max(2, int((x1 - x0) / 0.25)) if (x1 - x0) > (y1 - y0) else max(2, int((y1 - y0) / 0.25))
                for i in range(1, n):
                    if (x1 - x0) > (y1 - y0):
                        xx = x0 + i * (x1 - x0) / n
                        dw.line((xx, y0), (xx, y1), 'A-DECOR', lineweight=5)
                    else:
                        yy = y0 + i * (y1 - y0) / n
                        dw.line((x0, yy), (x1, yy), 'A-DECOR', lineweight=5)


def symbol_footprints(lay):
    """Where plan symbols will sit (MEP anchors, life-safety devices, keynote markers), so that equipment labels
    can slide away from them inside their own rectangle."""
    g = []
    mep = lay.get('mep') or {}
    for x in mep.get('exhaust', []):
        for p in [x.get('collar')] + list(x.get('route') or []):
            if p:
                g.append(Point(p).buffer(0.15))
    for p in (mep.get('makeup_air') or {}).get('diffusers', []):
        g.append(Point(p).buffer(0.22))
    ls = lay.get('life_safety') or {}
    for x in ls.get('extinguishers', []):
        g.append(Point(x['at']).buffer(0.14))
    for k in lay.get('keynotes', []):
        if 'A101' in k.get('sheets', ['A101']):
            g.append(Point(k['anchor']).buffer(0.13))
    return unary_union(g) if g else None


def fit_equipment_label(rect, opts, avoid=None):
    """Largest label that fits inside the rectangle; it may slide inside the rectangle to clear symbols."""
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    cx0, cy0 = (x0 + x1) / 2, (y0 + y1) / 2
    best = None
    for rot in (0, 90):
        W, H = (w, h) if rot == 0 else (h, w)
        for size in H_EQ:
            for ls in opts:
                tw_ = max(tw(s, size, i == 0) for i, s in enumerate(ls))
                th_ = len(ls) * size * LH
                if tw_ > W - 0.05 or th_ > H - 0.03:
                    continue
                bw, bh = (tw_, th_) if rot == 0 else (th_, tw_)
                sx_, sy_ = max(0.0, (w - bw) / 2 - 0.02), max(0.0, (h - bh) / 2 - 0.015)
                for fx in (0, -0.5, 0.5, -1, 1):
                    for fy in (0, -0.5, 0.5, -1, 1):
                        cx, cy = cx0 + fx * sx_, cy0 + fy * sy_
                        hit = 0.0
                        if avoid is not None:
                            hit = box(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2).intersection(avoid).area
                        cand = (hit < 1e-4, size, -len(ls), rot == 0, -abs(fx) - abs(fy), rot, ls, cx, cy)
                        if best is None or cand[:5] > best[:5]:
                            best = cand
    return best


def draw_equipment(dw, lay):
    eqs = lay.get('equipment', [])
    floor = [e for e in eqs if not e.get('overhead')]
    avoid = symbol_footprints(lay)
    for e in eqs:
        layer = eq_layer(e)
        x0, y0, x1, y1 = nrect(e['rect'])
        if e.get('overhead'):
            dw.rect(e['rect'], layer)
            dw.line((x0, y0), (x1, y1), layer, lineweight=9)
            dw.line((x0, y1), (x1, y0), layer, lineweight=9)
            continue
        dw.rect(e['rect'], layer, linetype='LAVA_OCULTO' if e.get('stack_with') else None)
        dw.pl.add(R(e['rect']), hard=False)
        fr = e.get('front')
        if fr in ('N', 'S', 'E', 'W') and not e.get('stack_with'):
            seg = {'N': ((x0 + 0.05, y0 + 0.03), (x1 - 0.05, y0 + 0.03)), 'S': ((x0 + 0.05, y1 - 0.03), (x1 - 0.05, y1 - 0.03)),
                   'W': ((x0 + 0.03, y0 + 0.05), (x0 + 0.03, y1 - 0.05)), 'E': ((x1 - 0.03, y0 + 0.05), (x1 - 0.03, y1 - 0.05))}[fr]
            dw.poly(list(seg), layer, const_width=0.025)
        fz = front_zone(e)
        if fz is not None:
            dw.outline(fz, 'A-EQUIPO-DESPEJE')
    # labels inside the rectangles (same fitting rule as the A-101 sheet)
    for e in floor:
        x0, y0, x1, y1 = nrect(e['rect'])
        tag = e.get('tag', e['id'])
        if e.get('no_label') or e.get('stack_with'):
            parent = next((p for p in eqs if p['id'] == e.get('stack_with')), None)
            pc = R(parent['rect']).centroid if parent else R(e['rect']).centroid
            ty = y0 + 0.06 if abs(y0 - pc.y) > abs(y1 - pc.y) else y1 - 0.06
            txt = f"{tag}"
            dw.text(txt, x0 + 0.04, ty, 0.05, 'A-EQUIPO-TEXTO', align='MIDDLE_LEFT', bold=True)
            dw.pl.add(box(x0 + 0.03, ty - 0.04, x0 + 0.05 + tw(txt, 0.05, True), ty + 0.04))
            continue
        name = e.get('plan_label') or e.get('label', '')
        dims = eq_dims_cm(e)
        opts = [[f"{tag} · {name}", dims]]
        if len(name) > 10:
            opts.append([tag, name, dims])
        best = fit_equipment_label((x0, y0, x1, y1), opts, avoid)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if best:
            size, rot, ls, cx, cy = best[1], best[5], best[6], best[7], best[8]
        else:
            size, rot, ls = 0.045, 90 if (y1 - y0) > (x1 - x0) else 0, [tag, dims]
        dw.lines(ls, cx, cy, size, 'A-EQUIPO-TEXTO', rot=rot)
        dw.pl.add(dw.lines_box(ls, cx, cy, size, rot=rot))
    # hoods: label in the front overhang strip, clear of dimension lines
    for hd in [e for e in eqs if e.get('overhead')]:
        x0, y0, x1, y1 = nrect(hd['rect'])
        under = [R(e['rect']) for e in floor if R(e['rect']).intersects(R(hd['rect']))
                 and R(e['rect']).intersection(R(hd['rect'])).area > 0.01]
        vert = (y1 - y0) >= (x1 - x0)
        name = hd.get('plan_label') or hd.get('label')
        L_, D_ = ((y1 - y0), (x1 - x0)) if vert else ((x1 - x0), (y1 - y0))
        lines = [f"{hd.get('tag', hd['id'])} · {name}", f"≈{L_ * 100:.0f}×{D_ * 100:.0f} (proyección)"]
        h = 0.055
        if vert:
            inner = min([g.bounds[0] for g in under] + [x1])
            sx = (x0 + inner) / 2 if inner - x0 > 2 * h * LH else x0 - 2 * h * LH / 2 - 0.02
            span = max(tw(s, h, True) for s in lines)
            cands = [(abs(k) * 0.01, sx, (y0 + y1) / 2 + k * 0.1) for k in range(-12, 13)
                     if y0 + span / 2 <= (y0 + y1) / 2 + k * 0.1 <= y1 - span / 2]
            dw.place(lines, ((x0 + x1) / 2, (y0 + y1) / 2), h=h, layer='A-EQUIPO-TEXTO', rot=90, cands=cands, leader=False)
        else:
            dw.place(lines, ((x0 + x1) / 2, y1), h=h, layer='A-EQUIPO-TEXTO', dirs=['S', 'N'], leader=False)


def draw_life_safety(dw, ex, lay, zones):
    ls = lay.get('life_safety') or {}
    prem = premises(ex)
    hot = [clip for z, a, rgb, clip in zones if 'caliente' in (z.get('name') or '').lower()]
    placed = []            # (lines, anchor, kw) labelled after all symbols are registered
    doors = {d['id']: d for d in ex['doors']}
    opens = {o['id']: o for o in lay.get('new_openings', [])}
    for e in ls.get('exits', []):
        at = e['at']
        cond = e.get('conditional')
        op = doors.get(e.get('opening')) or opens.get(e.get('opening'))
        nx, ny = 0.0, -1.0
        if op and 'opening' in op:
            x0, y0, x1, y1 = op['opening']
        elif op and 'rect' in op:
            x0, y0, x1, y1 = nrect(op['rect'])
            if (x1 - x0) >= (y1 - y0):
                y0 = y1 = (y0 + y1) / 2
            else:
                x0 = x1 = (x0 + x1) / 2
        else:
            x0, y0, x1, y1 = at[0], at[1], at[0], at[1] + 1
        L = math.hypot(x1 - x0, y1 - y0) or 1
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        if not prem.contains(Point(at[0] + nx * 0.3, at[1] + ny * 0.3)):
            nx, ny = -nx, -ny                                   # (nx, ny) points INTO the premises
        tail = (at[0] + nx * 1.1, at[1] + ny * 1.1)
        tip = (at[0] + nx * 0.45, at[1] + ny * 0.45)
        layer = 'S-SEGURIDAD'
        kw = {'linetype': 'LAVA_COND'} if cond else {}
        dw.line(tail, tip, layer, lineweight=50, **kw)
        dw.arrow(tip, (-nx, -ny), layer, length=0.18, half=0.08)
        dw.pl.add(LineString([tail, tip]).buffer(0.09))
        lines = [f"{e['id']} · SALIDA {e.get('width', 0):.2f} m" + (' · CONDICIONAL' if cond else '')]
        if not cond and ls.get('capacity_declared'):
            lines.append(f"Capacidad máxima {ls['capacity_declared']} personas")
        placed.append((lines, tail, {'layer': layer}))
    for s in ls.get('exit_signs', []):
        x, y = s['at']
        dw.insert('LAVA-SALIDA', (x, y), 'S-SEGURIDAD')
        ux, uy = DIRV.get(s.get('dir', 'E'), (1, 0))
        ex_, ey_ = x + ux * (0.19 if ux else 0), y + uy * (0.075 if uy else 0)
        tip = (ex_ + ux * 0.13, ey_ + uy * 0.13)
        dw.arrow(tip, (ux, uy), 'S-SEGURIDAD', length=0.13, half=0.06)
        dw.pl.add(box(x - 0.2, y - 0.08, x + 0.2, y + 0.08).union(Point(tip).buffer(0.05)))
        placed.append(([s['id']], (x, y), {'layer': 'S-SEGURIDAD', 'r0': 0.22}))
    def ceiling_spot(p, w, h):
        """Ceiling devices: keep the data point unless the symbol would hide a dimension text or another
        symbol; then shift it ≤0.4 m (indicative position, noted in the schedule)."""
        best = None
        for k, (dx, dy) in enumerate([(0, 0), (0.25, 0), (-0.25, 0), (0, 0.2), (0, -0.2), (0.4, 0), (-0.4, 0)]):
            q = (p[0] + dx, p[1] + dy)
            c = dw.pl.cost(dw.sym_box(q, w, h)) + k * 0.01
            if best is None or c < best[0]:
                best = (c, q)
        q = best[1]
        if q != tuple(p):
            dw.line(p, q, 'S-SEGURIDAD', lineweight=9, linetype='LAVA_FINO')
        dw.pl.add(dw.sym_box(q, w, h))
        return q

    for p in ls.get('smoke_detectors', []):
        kind = 'DT' if any(c.contains(Point(p)) for c in hot) else 'DH'
        dw.insert('LAVA-DETECTOR', ceiling_spot(p, 0.21, 0.21), 'S-SEGURIDAD', {'TIPO': kind})
    for p in ls.get('emergency_lights', []):
        dw.insert('LAVA-LUZ-EMERG', ceiling_spot(p, 0.28, 0.11), 'S-SEGURIDAD')
    for x_ in ls.get('extinguishers', []):
        cls = 'K' if 'K' in x_.get('type', '').split()[:2] else 'ABC'
        dw.insert('LAVA-EXTINTOR', x_['at'], 'S-SEGURIDAD', {'CLASE': cls})
        dw.pl.add(dw.sym_box(x_['at'], 0.25, 0.25))
        placed.append(([x_['id']], x_['at'], {'layer': 'S-SEGURIDAD', 'r0': 0.15}))
    ps = ls.get('pull_station')
    if ps:
        dw.insert('LAVA-PULSADOR', ps['at'], 'S-SEGURIDAD')
        dw.pl.add(dw.sym_box(ps['at'], 0.2, 0.2))
        placed.append(([' / '.join(ps.get('ids', ['PM'])), f"h {ps.get('h', '')}"], ps['at'], {'layer': 'S-SEGURIDAD', 'r0': 0.12}))
    for k in ex.get('keepouts', []):
        dw.rect(k['rect'], 'S-SEGURIDAD', linetype='LAVA_FINO', lineweight=9)
    return placed


def draw_egress(dw, calcs):
    placed = []
    if not calcs:
        return placed
    ends = set()
    for p in calcs.get('egress_paths', []):
        pts = p.get('polyline') or []
        if len(pts) < 2:
            continue
        dw.poly(pts, 'S-EGRESO')
        (ax, ay), (bx, by) = pts[-2], pts[-1]
        key = (round(bx, 2), round(by, 2))
        if key not in ends:
            ends.add(key)
            L = math.hypot(bx - ax, by - ay) or 1
            dw.arrow((bx, by), ((bx - ax) / L, (by - ay) / L), 'S-EGRESO')
        dw.circle(pts[0], 0.035, 'S-EGRESO', linetype='Continuous')
        lim = p.get('limit_common_path_m', p.get('limit'))
        placed.append(([f"{p['id']} {p.get('length_m', p.get('length', 0)):.2f} m ≤ {lim:.2f}"], pts[0],
                       {'layer': 'S-EGRESO', 'h': 0.055, 'bold_first': False, 'r0': 0.06}))
    return placed


def draw_mep(dw, ex, lay, mech, elec):
    mep = lay.get('mep') or {}
    placed = []
    eqs = {e['id']: e for e in lay.get('equipment', [])}
    gas = mep.get('gas')
    if gas:
        cons = [eqs[c] for c in gas.get('consumers', []) if c in eqs]
        mv, en, so = gas.get('main_valve'), gas.get('entry'), gas.get('solenoid')
        if cons and mv and en and so:
            backs = []
            for e in cons:                      # manifold runs in the technical gap behind the line
                x0, y0, x1, y1 = nrect(e['rect'])
                backs.append({'W': x1, 'E': x0}.get(e.get('front'), x1))
            back = max(backs)
            walls = [nrect(w['rect'])[0] for w in lay.get('new_walls', []) if nrect(w['rect'])[0] >= back - 1e-6]
            mx = (back + min(walls)) / 2 if walls else back + 0.075
            ys = [(nrect(e['rect'])[1] + nrect(e['rect'])[3]) / 2 for e in cons]
            path = [mv, en, so, (mx, so[1]), (mx, max(ys))]
            dw.poly(path, 'M-GAS')
            for e, yc in zip(cons, ys):
                x0, y0, x1, y1 = nrect(e['rect'])
                bx = {'W': x1, 'E': x0}.get(e.get('front'), x1)
                dw.line((mx, yc), (bx, yc), 'M-GAS', linetype='Continuous')
                dw.circle((bx, yc), 0.025, 'M-GAS', linetype='Continuous')
            dw.insert('LAVA-VALVULA', mv, 'M-GAS')
            dw.insert('LAVA-SOLENOIDE', so, 'M-GAS')
            dw.circle(en, 0.04, 'M-GAS', linetype='Continuous')
            for p in (mv, so):
                dw.pl.add(dw.sym_box(p, 0.18, 0.2))
            placed.append((['GAS · llave de corte principal', 'FUERA del local (red del C.C.)'], mv,
                           {'layer': 'M-GAS', 'dirs': ['N', 'NE', 'NW'], 'r0': 0.1}))
            placed.append((['Solenoide gas', '(enclavada HD-1)'], so, {'layer': 'M-GAS', 'r0': 0.12}))
    for x in mep.get('exhaust', []):
        c = x.get('collar')
        if not c:
            continue
        route = x.get('route') or [c]
        if len(route) > 1:
            dw.poly(route, 'M-EXTRACCION')
            dw.circle(c, 0.05, 'M-EXTRACCION')
        dw.insert('LAVA-DUCTO-V', route[-1], 'M-EXTRACCION')
        dw.pl.add(dw.sym_box(route[-1], 0.28, 0.28))
        placed.append(([f"{x['id']} · {x.get('kind', '')}"], route[-1], {'layer': 'M-EXTRACCION', 'r0': 0.16}))
    eh = ex.get('existing_hood') or {}
    if eh.get('collar'):
        dw.rect(eh['collar'], 'M-EXTRACCION', linetype='LAVA_FINO')
        x0, y0, x1, y1 = nrect(eh['collar'])
        dw.line((x0, y0), (x1, y1), 'M-EXTRACCION', linetype='LAVA_FINO', lineweight=9)
        dw.line((x0, y1), (x1, y0), 'M-EXTRACCION', linetype='LAVA_FINO', lineweight=9)
    ma = mep.get('makeup_air')
    if ma:
        for p in ma.get('diffusers', []):
            dw.insert('LAVA-DIFUSOR', p, 'M-AIRE')
            dw.pl.add(dw.sym_box(p, 0.42, 0.42))
        for p in ma.get('diffusers', []):
            placed.append(([ma.get('id', 'AR')], p, {'layer': 'M-AIRE', 'r0': 0.24}))
        rz = ((mech or {}).get('makeup_air') or {}).get('riser')      # proposed riser, same point as M-102 / E-101
        if rz:
            dw.insert('LAVA-DUCTO-V', rz, 'M-AIRE')
            dw.pl.add(dw.sym_box(rz, 0.3, 0.3))
            dif = ma.get('diffusers', [])
            if dif:
                dw.line(tuple(rz), tuple(dif[0]), 'M-AIRE', linetype='LAVA_FINO', lineweight=9)
                for a_, b_ in zip(dif, dif[1:]):
                    dw.line(tuple(a_), tuple(b_), 'M-AIRE', linetype='LAVA_FINO', lineweight=9)
    pn = mep.get('panel')
    if pn and pn.get('rect'):
        x0, y0, x1, y1 = nrect(pn['rect'])
        dw.rect(pn['rect'], 'E-TABLERO')
        dw.hatch(Polygon([(x0, y0), (x1, y0), (x1, y1)]), 'E-TABLERO')
        ws = ((elec or {}).get('panel') or {}).get('working_space', {}).get('rect')
        if not ws:
            m = re.search(r'frente libre (\d+\.\d+)', pn.get('note', ''))
            depth = float(m.group(1)) if m else 0.9
            ws = (x0, y1, x1, y1 + depth)
        dw.rect(ws, 'E-TABLERO', linetype='LAVA_FINO', lineweight=9)
        cc = ((elec or {}).get('panel') or {}).get('control_panel_CC1_rect')
        if cc:
            dw.rect(cc, 'E-TABLERO')
        dw.pl.add(R(pn['rect']))
        placed.append(([pn.get('id', 'TE')] + (['+ CC-1'] if cc else []), ((x0 + x1) / 2, y1), {'layer': 'E-TABLERO', 'dirs': ['S', 'SE', 'SW'], 'r0': 0.08}))
    drains = set(mep.get('drain_existing', [])) | {w['id'] for w in ((mech or {}).get('wet_points_existing') or []) if w.get('dfu_ref')}
    for wp in ex.get('wet_points_existing', []):
        dw.rect(wp['rect'], 'P-SANITARIO', linetype='LAVA_FINO', lineweight=13)
        tag = wp['id'] + (' drenaje exist.' if wp['id'] in drains else ' exist.')
        x0, y0, x1, y1 = nrect(wp['rect'])
        placed.append(([tag], ((x0 + x1) / 2, (y0 + y1) / 2), {'layer': 'P-SANITARIO', 'h': 0.05, 'bold_first': False,
                                                               'r0': 0.05}))
    for fd in (mech or {}).get('floor_drains', []) or []:
        if fd.get('at'):
            dw.insert('LAVA-DESAGUE', fd['at'], 'P-SANITARIO')
            dw.pl.add(dw.sym_box(fd['at'], 0.15, 0.15))
            placed.append(([fd['id']], fd['at'], {'layer': 'P-SANITARIO', 'h': 0.055, 'r0': 0.1}))
    for cid, ca in ((mech or {}).get('water_heaters') or {}).items():
        if isinstance(ca, dict) and ca.get('at'):
            dw.circle(ca['at'], 0.12, 'P-SANITARIO', linetype='LAVA_FINO')
            dw.pl.add(dw.sym_box(ca['at'], 0.25, 0.25))
            placed.append(([cid], ca['at'], {'layer': 'P-SANITARIO', 'h': 0.055, 'r0': 0.14}))
    return placed


def draw_routes(dw, lay):
    for r in lay.get('routes', []):
        c = ROUTE.get(r.get('kind'), ('#333333', None))[0]
        dw.poly(r['pts'], 'A-FLUJO', rgb=hex_rgb(c))


def draw_keynotes(dw, lay, sheet='A101'):
    notes = [k for k in lay.get('keynotes', []) if sheet in k.get('sheets', ['A101'])]
    for i, k in enumerate(notes, 1):
        rgb = hex_rgb(k.get('color', '#111111'))
        dw.circle(k['anchor'], 0.11, 'A-NOTA-CLAVE', rgb=rgb)
        dw.text(str(i), k['anchor'][0], k['anchor'][1], 0.1, 'A-NOTA-CLAVE', bold=True, rgb=rgb)
        dw.pl.add(Point(k['anchor']).buffer(0.13))
    return notes


# ------------------------------------------------------------------------------------------------ panels / tables
def table(dw, x, y, cols, rows, h=0.07, title=None, layer='A-TEXTO', pitch=None):
    """cols: [(header, width)], rows: [[cell...]] (cell str or (str, bold)). (x, y) = top-left, data coords."""
    pitch = pitch or h * 2.1
    yy = y
    W = sum(w for _, w in cols)
    if title:
        dw.text(title, x, yy + h * 0.9, h * 1.35, layer, align='MIDDLE_LEFT', bold=True)
        yy += h * 2.6
    xx = x
    for head, w in cols:
        dw.text(fit(head, w - 0.1, h, True), xx + 0.05, yy + pitch / 2, h, layer, align='MIDDLE_LEFT', bold=True)
        xx += w
    yy += pitch
    dw.line((x, yy), (x + W, yy), layer, lineweight=25)
    for r in rows:
        xx = x
        for (head, w), cell in zip(cols, r):
            s, b = (cell if isinstance(cell, tuple) else (cell, False))
            dw.text(fit(s, w - 0.1, h, b), xx + 0.05, yy + pitch / 2, h, layer, align='MIDDLE_LEFT', bold=b)
            xx += w
        yy += pitch
        dw.line((x, yy), (x + W, yy), layer, lineweight=5)
    return yy - y


def legend(dw, x, y, width):
    dw.text('CAPAS (nombre · contenido)', x, y + 0.1, 0.1, 'A-TEXTO', align='MIDDLE_LEFT', bold=True)
    yy = y + 0.36
    used = [row for row in LAYERS if row[0] in dw.doc.layers]
    for name, aci, lt, lw, desc, on in used:
        sx0, sx1 = x, x + 0.8
        if name.endswith('-TRAMA'):
            g = box(sx0, yy - 0.06, sx1, yy + 0.06)
            if name in ('A-MURO-EXIST-TRAMA', 'A-MURO-DEMOL-TRAMA'):
                dw.hatch(g, name, pattern='ANSI31', scale=0.02, angle=90 if 'DEMOL' in name else 0)
            elif name == 'A-ZONA-TRAMA':
                dw.hatch(g, name, rgb=(47, 111, 208), transparency=0.8)
            else:
                dw.hatch(g, name)
        elif name in ('A-TEXTO', 'A-EQUIPO-TEXTO', 'A-NOTA-CLAVE'):
            dw.text('Abc 123', (sx0 + sx1) / 2, yy, 0.07, name)
        elif name == 'A-COTA':
            dw.line((sx0, yy), (sx1, yy), name)
        else:
            dw.line((sx0, yy), (sx1, yy), name)
        state = '' if on else '  [apagada por defecto]'
        desc = dw.descriptions.get(name, desc)
        dw.text(fit(f"{name} — {desc}{state}", width - 1.0, 0.07), x + 1.0, yy, 0.07, 'A-TEXTO', align='MIDDLE_LEFT')
        yy += 0.2
    used = set(dw.used_blocks)
    if not used & {'LAVA-SALIDA', 'LAVA-LUZ-EMERG', 'LAVA-EXTINTOR', 'LAVA-DETECTOR', 'LAVA-PULSADOR', 'LAVA-VALVULA',
                   'LAVA-SOLENOIDE', 'LAVA-DUCTO-V', 'LAVA-DIFUSOR', 'LAVA-DESAGUE'}:
        return yy - y
    yy += 0.2
    dw.text('SÍMBOLOS', x, yy, 0.1, 'A-TEXTO', align='MIDDLE_LEFT', bold=True)
    yy += 0.35
    syms = [('LAVA-SALIDA', 'S-SEGURIDAD', None, 'Rótulo SALIDA iluminado (triángulo = sentido de salida)'),
            ('LAVA-LUZ-EMERG', 'S-SEGURIDAD', None, 'Luz de emergencia (autonomía ≥ 1.5 h)'),
            ('LAVA-EXTINTOR', 'S-SEGURIDAD', {'CLASE': 'K'}, 'Extintor portátil (K = clase K · ABC = polvo químico)'),
            ('LAVA-DETECTOR', 'S-SEGURIDAD', {'TIPO': 'DT'}, 'Detector: DH humo · DT térmico (cocina caliente)'),
            ('LAVA-PULSADOR', 'S-SEGURIDAD', None, 'Pulsador manual de supresión de campana'),
            ('LAVA-VALVULA', 'M-GAS', None, 'Llave de gas'),
            ('LAVA-SOLENOIDE', 'M-GAS', None, 'Válvula solenoide de gas enclavada con la supresión'),
            ('LAVA-DUCTO-V', 'M-EXTRACCION', None, 'Ducto vertical / collarín de extracción o chimenea'),
            ('LAVA-DIFUSOR', 'M-AIRE', None, 'Difusor de aire de reposición'),
            ('LAVA-DESAGUE', 'P-SANITARIO', None, 'Desagüe de piso')]
    for name, layer, att, desc in syms:
        if name not in used:
            continue
        dw.insert(name, (x + 0.4, yy + 0.08), layer, att)
        dw.text(desc, x + 1.0, yy + 0.08, 0.07, 'A-TEXTO', align='MIDDLE_LEFT')
        yy += 0.42
    return yy - y


def title_block(dw, x, y, lay, ex, document, filename):
    meta = lay.get('meta') or {}
    proj = ex['meta'].get('project', 'LAVA')
    dw.insert('LAVA-ROTULO', (x, y), 'A-TEXTO', {
        'PROYECTO': proj.split('(')[0].strip() + ' · restaurante (adecuación de local)',
        'UBICACION': "Local ex-Marna's · Terrazas Lindora (C.C. abierto, condominio) · Santa Ana, San José, CR",
        'DOCUMENTO': document,
        'ESTADO': STATUS,
        'NOTA': 'Archivo base editable: verificar en sitio, ajustar y firmar. No es plano constructivo.',
        'ESCALA': 'Unidades: metros (1 unidad = 1 m) · imprimir a 1:50 en A2 · cotas ±2 cm (base: PDF de Marna’s)',
        'VERSION': f"Layout v{meta.get('version', '?')} · {meta.get('date', '')} · AutoCAD 2018 DXF",
        'ARCHIVO': filename,
    })
    return ROTULO_H


def general_notes(ex, lay, proposal):
    ls = lay.get('life_safety') or {}
    gas = (lay.get('mep') or {}).get('gas') or {}
    ceil = ex.get('ceiling') or {}
    n = [
        ('!' + STATUS + '. Nada en este archivo declara cumplimiento normativo final.'),
        ('Coordenadas: 1 unidad = 1 m. Origen = eje A (X = 0) / eje 1 (Y = 0). X crece hacia la fachada (este). '
         'Y del DXF = −Y de data/*.json (en los JSON Y crece hacia el sur); el UCS guardado «LAVA-DATOS» reproduce las '
         'coordenadas de los JSON. «Norte» = parte superior del PDF de Marna’s (no es norte geográfico).'),
        f"Base: {ex['meta'].get('source', '')} Tolerancia: {ex['meta'].get('tolerance', '')}",
        f"Cielo: altura supuesta {ceil.get('height_assumed', 3.0):.2f} m — {FLAG_SITE}. {ceil.get('note', '')}",
    ]
    if proposal:
        n += [
            f"!{FLAG_EXT}",
            f"!{FLAG_SMOKER}",
            f"* junto a una medida = {FLAG_DIM} (equipo sin ficha técnica).",
            f"Gas: {gas.get('source', '')}. Sin cilindros en el local. {gas.get('entry_note', '')}.",
            f"{ls.get('restrooms', '')} Criterio a validar: distancia de recorrido ≤ 36 m.",
            'Venta de bebidas alcohólicas: licencia municipal clase C (Ley 9047, restaurante) — trámite y requisitos '
            'a verificar con la Municipalidad de Santa Ana. La barra es solo de servicio (sin taburetes).',
            'Centro comercial abierto con reglamento de condominio; no se dispone del plano del conjunto: ubicación de '
            f"baños comunes, acometida de gas, cuarto de basura y rutas comunes — {FLAG_SITE} con la administración.",
            f"Capacidad: {ls.get('capacity_note', '')}",
            'Capas apagadas por defecto: A-COTA-DEMO (cotas Marna’s / corrimiento), A-FLUJO (flujos operativos), '
            'A-EQUIPO-DESPEJE (despejes frente a equipos). PS-1 y su vano están en capas propias (condicional).',
        ]
        if (lay.get('meta') or {}).get('strategy'):
            n.append(f"Estrategia (definida con el cliente): {lay['meta']['strategy']}.")
        n += [s for s in lay.get('structure_notes', []) if 'Confirmar' in s]
    else:
        n += [
            'Contenido: solo condiciones existentes (muros, columnas, ductos, escalera, vitrinas, puertas, campana de '
            'Marna’s, puntos húmedos). La propuesta LAVA está en LAVA_base_v3.dxf.',
            f"Uso de ductos, espesores y altura libre: {FLAG_SITE}. Lectura estructural = criterio visual del PDF, no "
            'evaluación estructural.',
        ]
    return n


def draw_notes(dw, x, y, width, notes, title='NOTAS GENERALES'):
    dw.text(title, x, y + 0.1, 0.1, 'A-TEXTO', align='MIDDLE_LEFT', bold=True)
    yy = y + 0.32
    for s in notes:
        red = s.startswith('!')
        s = s.lstrip('!')
        dw.text('•', x + 0.05, yy + 0.05, 0.075, 'A-TEXTO', align='MIDDLE_LEFT')
        hgt = dw.mtext(s, x + 0.25, yy, 0.075, width - 0.3, 'A-TEXTO', bold=red, **({'color': 1} if red else {}))
        yy += hgt + 0.07
    return yy - y


# ------------------------------------------------------------------------------------------------ builders
def plan_bounds(ex):
    gs = [R(w['rect']) for w in ex['walls']] + [R(c['rect']) for c in ex['columns']] + \
         [R(s['rect']) for s in ex['shafts']] + [R(ex['stair']['outline'])] + [premises(ex)]
    return unary_union(gs).bounds


def build_proposal(ex, lay):
    dw = Dwg()
    calcs = optional_json('life_safety_calcs.json')
    mech = optional_json('mech_calcs.json')
    elec = optional_json('elec_loads.json')
    b = plan_bounds(ex)
    zones = draw_zones_fill(dw, ex, lay)
    draw_axes(dw, ex, b)
    draw_structure(dw, ex, lay, proposal=True)
    demo_labels = draw_demolition(dw, ex, lay)
    wall_labels = draw_new_walls(dw, lay)
    door_labels = draw_new_openings(dw, lay)
    draw_existing_doors(dw, ex, lay, proposal=True)
    draw_furniture(dw, lay)
    draw_decor(dw, lay)
    draw_equipment(dw, lay)
    draw_routes(dw, lay)
    dim_txt = []
    for d in lay.get('dims', []):
        lp = d.get('lpos', 0.5)
        for cand in [lp] + [c for c in (0.3, 0.7, 0.22, 0.78) if abs(c - lp) > 1e-6]:
            tb = dim_text_box(d['a'], d['b'], d.get('off', 0.4), d.get('label'), cand)
            if not any(tb.intersects(o) for o in dim_txt):
                lp = cand
                break
        dim_txt.append(dim_text_box(d['a'], d['b'], d.get('off', 0.4), d.get('label'), lp))
        dw.dim(d['a'], d['b'], d.get('off', 0.4), d.get('label'), 'A-COTA', lpos=lp)
    for d in lay.get('dims_demo', []):
        dw.dim(d['a'], d['b'], d.get('off', 0.4), d.get('label'), 'A-COTA-DEMO', lpos=d.get('lpos', 0.5), register=False)
    notes = draw_keynotes(dw, lay)
    placed = draw_life_safety(dw, ex, lay, zones)
    placed += draw_mep(dw, ex, lay, mech, elec)
    egress = draw_egress(dw, calcs)
    draw_zone_labels(dw, zones)          # after the symbols, so the big names dodge them
    # flexible labels (after every fixed obstacle is registered)
    for lines, at, vert, g in wall_labels:
        x0, y0, x1, y1 = g.bounds
        dw.place(lines, ((x0 + x1) / 2, (y0 + y1) / 2), h=H_TAG, layer='A-MURO-NUEVO', rot=90 if vert else 0,
                 dirs=['E', 'W'] if vert else ['S', 'N'], r0=(x1 - x0) / 2 + 0.06 if vert else (y1 - y0) / 2 + 0.06, leader=False)
    for o in lay.get('remove_items', []):
        x0, y0, x1, y1 = nrect(o['rect'])
        lbl = o.get('label', o['id'])
        dw.place([lbl.split('—')[0].strip(), 'A RETIRAR' if 'RETIRAR' in lbl.upper() else ''], ((x0 + x1) / 2, y0),
                 h=0.06, layer='A-RETIRO', dirs=['N', 'NE', 'NW'], r0=0.1, rings=8)
    for tag, at, vert in demo_labels:
        dw.place([tag], at, h=0.06, layer='A-MURO-DEMOL', rot=90 if vert else 0, dirs=['E', 'W'] if vert else ['S', 'N'],
                 r0=0.08)
    for lines, at, layer in door_labels:
        dw.place(lines, at, h=H_TAG, layer=layer, r0=0.12)
    for lines, at, kw in placed + egress:     # egress tags last: their layer is off by default
        dw.place(lines, at, **kw)
    # ---------------- column 2: title block, general notes, keynotes
    W2 = 10.0
    px = b[2] + 1.9
    py = b[1] - 1.5
    yy = py + title_block(dw, px, py, lay, ex, 'Base CAD v3 · planta propuesta (anteproyecto)', 'LAVA_base_v3.dxf') + 0.35
    yy += draw_notes(dw, px, yy, W2, general_notes(ex, lay, True)) + 0.35
    dw.text('NOTAS CLAVE (numeración de la lámina A-101)', px, yy, 0.1, 'A-TEXTO', align='MIDDLE_LEFT', bold=True)
    yy += 0.3
    for i, k in enumerate(notes, 1):
        rgb = hex_rgb(k.get('color', '#111111'))
        txts = k['text'] if isinstance(k['text'], list) else [k['text']]
        dw.circle((px + 0.12, yy + 0.05), 0.1, 'A-NOTA-CLAVE', rgb=rgb)
        dw.text(str(i), px + 0.12, yy + 0.05, 0.09, 'A-NOTA-CLAVE', bold=True, rgb=rgb)
        for j, s_ in enumerate(txts):
            dw.text(fit(s_, W2 - 0.4, 0.07, j == 0), px + 0.35, yy + 0.05 + j * 0.15, 0.07, 'A-TEXTO', align='MIDDLE_LEFT',
                    bold=j == 0)
        yy += 0.15 * len(txts) + 0.12
    # ---------------- column 3: layers + symbols, areas, life safety, MEP
    qx = px + W2 + 0.9
    yy = py
    yy += legend(dw, qx, yy, W2) + 0.35
    prem = premises(ex)
    zrows = [[(z['id'], True), z.get('name', ''), f"{a:.2f}"] for z, a, rgb, clip in zones]
    zrows.append([('Σ', True), 'Local (polígono de premisas, interior)', f"{prem.area:.2f}"])
    zrows.append([('', False), f"Asientos: {seat_count(lay)} · capacidad declarada: "
                  f"{(lay.get('life_safety') or {}).get('capacity_declared', '?')} personas", ''])
    yy += table(dw, qx, yy, [('Zona', 0.7), ('Nombre', 7.8), ('Área m²', 1.5)], zrows,
                title='CUADRO DE ÁREAS (≈, a verificar en sitio)') + 0.45
    ls = lay.get('life_safety') or {}
    srows = []
    for e in ls.get('exits', []):
        srows.append([(e['id'], True), f"Salida {e.get('width', 0):.2f} m ({e.get('opening')})", first_sentence(e.get('note'), 120)])
    for s_ in ls.get('exit_signs', []):
        srows.append([(s_['id'], True), f"Rótulo «{s_.get('text', 'SALIDA')}»", s_.get('note', '')])
    for x_ in ls.get('extinguishers', []):
        srows.append([(x_['id'], True), x_.get('type', ''), first_sentence(x_.get('note'), 120)])
    if ls.get('pull_station'):
        p_ = ls['pull_station']
        srows.append([(' / '.join(p_.get('ids', [])), True), f"Pulsador manual h {p_.get('h', '')}", first_sentence(p_.get('note'), 120)])
    srows.append([(f"{len(ls.get('emergency_lights', []))} ×", True), 'Luces de emergencia', first_sentence(ls.get('emergency_note'), 120)])
    srows.append([(f"{len(ls.get('smoke_detectors', []))} ×", True), 'Detectores', first_sentence(ls.get('detector_note'), 120)])
    srows.append([('Nota', True), 'Dispositivos de cielo', 'Detectores y luces: posición indicativa (símbolo corrido ≤0.4 m '
                  'si tapaba una cota; línea fina al punto de datos). Ubicación final: ingeniería.'])
    lim = ls.get('limits') or {}
    if lim:
        srows.append([('Límites', True), 'NFPA 101 (<50 personas)', first_sentence(lim.get('note'), 120)])
    if calcs and calcs.get('summary', {}).get('longest_path'):
        lp = calcs['summary']['longest_path']
        srows.append([(lp.get('id', ''), True), 'Recorrido más largo', f"{lp.get('from', '')}: {lp.get('length', 0):.2f} m "
                      f"≤ {lp.get('limit', 0):.2f} m (capa S-EGRESO)"])
    yy += table(dw, qx, yy, [('ID', 1.1), ('Elemento', 2.5), ('Nota (a validar con Bomberos / RNPCI)', 6.4)], srows,
                title='SEGURIDAD HUMANA (S-SEGURIDAD)') + 0.45
    mep = lay.get('mep') or {}
    mrows = []
    g = mep.get('gas') or {}
    if g:
        mrows.append([('GAS', True), 'Red del centro comercial', first_sentence(g.get('note'), 130)])
    for x in mep.get('exhaust', []):
        mrows.append([(x['id'], True), f"{x.get('kind', '')} · {x.get('serves', '')}", first_sentence(x.get('riser'), 130)])
    if mep.get('makeup_air'):
        mrows.append([(mep['makeup_air'].get('id', 'AR'), True), 'Aire de reposición', first_sentence(mep['makeup_air'].get('note'), 130)])
    if mep.get('panel'):
        mrows.append([(mep['panel'].get('id', 'TE'), True), 'Tablero eléctrico', first_sentence(mep['panel'].get('note'), 130)])
    if mep.get('grease_trap'):
        gt = next((e for e in lay.get('equipment', []) if e['id'] == mep['grease_trap']), {})
        mrows.append([(mep['grease_trap'], True), 'Trampa de grasa', first_sentence(gt.get('note'), 130)])
    wpe = (mech or {}).get('wet_points_existing') or []
    if wpe:
        used = [w['id'] + ('*' if not w.get('in_mep_drain_existing') else '') for w in wpe if w.get('dfu_ref')]
        off = [w['id'] for w in wpe if not w.get('dfu_ref')]
        mrows.append([('WP', True), 'Drenajes existentes', 'Se reutilizan ' + ', '.join(used) + (f"; se anula {', '.join(off)}" if off else '')
                      + (' (* no figura en mep.drain_existing)' if any('*' in u for u in used) else '') + f" — {FLAG_SITE}"])
    elif mep.get('drain_existing'):
        mrows.append([('WP', True), 'Drenajes existentes', 'Se reutilizan ' + ', '.join(mep['drain_existing']) + f" — {FLAG_SITE}"])
    for fd in (mech or {}).get('floor_drains', []) or []:
        mrows.append([(fd['id'], True), 'Desagüe de piso', f"{fd.get('zone', '')} → {fd.get('to', '')}"])
    for cid, ca in ((mech or {}).get('water_heaters') or {}).items():
        if isinstance(ca, dict):
            mrows.append([(cid, True), f"Agua caliente {ca.get('volume_L', '')} L", f"{ca.get('type', '')} · {ca.get('location', ca.get('serves', ''))}"])
    for s_ in mep.get('engineering_notes', []):
        mrows.append([('Nota', True), 'Ingeniería', s_])
    table(dw, qx, yy, [('ID', 1.1), ('Sistema', 2.5), ('Nota (TO BE ENGINEERED)', 6.4)], mrows,
          title='INSTALACIONES (M- / P- / E-) · esquemático')
    # ---------------- under the plan: equipment schedule
    rows = []
    for e in sorted(lay.get('equipment', []), key=lambda e: natural_key(e.get('tag', e['id']))):
        note = e.get('note') or ''
        flags = [f for f in (FLAG_EXT, FLAG_SMOKER, FLAG_SITE, 'TO BE ENGINEERED') if f in note]
        rows.append([(e.get('tag', e['id']), True), e.get('label', ''), eq_size_m(e), eq_layer(e),
                     (flags[0] if flags else first_sentence(note, 140))])
    table(dw, b[0] - 1.35, b[3] + 1.6, [('TAG', 0.75), ('Equipo', 3.5), ('Frente×fondo×alto (m)', 1.75), ('Capa', 1.45),
                                        ('Observación (* = DIMENSION TO VERIFY)', 12.3)], rows, title='CUADRO DE EQUIPOS')
    return dw


def natural_key(s):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', str(s))]


EXISTING_DESC = {
    'A-VIDRIO': 'Vidrio existente: vitrinas de fachada y ventana sur del ala',
    'A-PUERTA': 'Puerta principal existente (giro de hojas) y vanos existentes',
    'A-EQUIPO-ALTO': 'Equipo existente en altura: campana de Marna’s (a retirar según propuesta)',
    'M-EXTRACCION': 'Collarín / ducto existente de la campana de Marna’s (VERIFY ON SITE)',
    'S-SEGURIDAD': 'Barrido de la puerta principal: área libre de egreso',
    'P-SANITARIO': 'Puntos húmedos existentes WP1–WP6 (drenajes: VERIFY ON SITE)',
    'A-MURO-EXIST': 'EXISTING WALL: muros existentes (IP-KB sin trama = división liviana)',
}


def build_existing(ex, lay):
    dw = Dwg(EXISTING_DESC)
    b = plan_bounds(ex)
    draw_axes(dw, ex, b)
    draw_structure(dw, ex, lay, proposal=False)
    draw_existing_doors(dw, ex, lay, proposal=False)
    eh = ex.get('existing_hood') or {}
    if eh.get('rect'):
        x0, y0, x1, y1 = nrect(eh['rect'])
        dw.rect(eh['rect'], 'A-EQUIPO-ALTO')
        dw.line((x0, y0), (x1, y1), 'A-EQUIPO-ALTO', lineweight=9)
        dw.line((x0, y1), (x1, y0), 'A-EQUIPO-ALTO', lineweight=9)
        if eh.get('collar'):
            dw.rect(eh['collar'], 'M-EXTRACCION')
            cx0, cy0, cx1, cy1 = nrect(eh['collar'])
            dw.line((cx0, cy0), (cx1, cy1), 'M-EXTRACCION', lineweight=9)
            dw.line((cx0, cy1), (cx1, cy0), 'M-EXTRACCION', lineweight=9)
            dw.pl.add(R(eh['collar']))
        dw.place(['Campana existente Marna’s', f"{x1 - x0:.2f} × {y1 - y0:.2f} · collarín al centro"],
                 ((x0 + x1) / 2, y1), h=H_TAG, layer='A-EQUIPO-ALTO', dirs=['S'], r0=0.06, leader=False)
    for wp in ex.get('wet_points_existing', []):
        dw.rect(wp['rect'], 'P-SANITARIO')
        dw.pl.add(R(wp['rect']), hard=False)
    for wp in ex.get('wet_points_existing', []):
        x0, y0, x1, y1 = nrect(wp['rect'])
        dw.place([wp['id'], fit(wp.get('desc', ''), 2.2, 0.05)], ((x0 + x1) / 2, (y0 + y1) / 2), h=0.055,
                 layer='P-SANITARIO', r0=0.05)
    te = ex.get('terrace_existing')
    if te:
        dw.rect(te['rect'], 'A-CONTEXTO')
        x0, y0, x1, y1 = nrect(te['rect'])
        dw.lines(['Terraza existente (Marna’s) en pasillo común', 'Área común: permiso de la administración — VERIFY'],
                 (x0 + x1) / 2, (y0 + y1) / 2, 0.08, 'A-CONTEXTO')
    for k in ex.get('keepouts', []):
        dw.rect(k['rect'], 'S-SEGURIDAD', linetype='LAVA_FINO', lineweight=9)
    # dimensions derived from the survey
    prem = premises(ex)
    pts = list(prem.exterior.coords)
    minx, miny, maxx, maxy = prem.bounds
    fac = [p for p in pts if abs(p[0] - maxx) < 1e-6]
    fy0, fy1 = min(p[1] for p in fac), max(p[1] for p in fac)
    dw.dim((minx, miny), (maxx, miny), OVERALL_Y - miny, f"{maxx - minx:.2f} interior", 'A-COTA')
    for d in lay.get('dims_demo', []):
        if 'Marna' in (d.get('label') or ''):
            dw.dim(d['a'], d['b'], d.get('off', 0.4), d.get('label'), 'A-COTA', lpos=d.get('lpos', 0.5))
    chain = sorted({fy0, fy1} | {y for gl in ex['glazing'] for y in (nrect(gl['rect'])[1], nrect(gl['rect'])[3])
                                 if abs(nrect(gl['rect'])[0] - maxx) < 0.05})
    for a_, b_ in zip(chain, chain[1:]):
        dw.dim((maxx, a_), (maxx, b_), 0.665, None, 'A-COTA')
    dw.dim((maxx, miny), (maxx, fy1), 1.035, f"{fy1 - miny:.2f} interior", 'A-COTA')
    south = [p for p in pts if abs(p[1] - maxy) < 1e-6]
    sx0, sx1 = min(p[0] for p in south), max(p[0] for p in south)
    wchain = sorted({sx0, sx1} | {x for gl in ex['glazing'] for x in (nrect(gl['rect'])[0], nrect(gl['rect'])[2])
                                  if abs(nrect(gl['rect'])[1] - maxy) < 0.05})
    ybot = max(nrect(w['rect'])[3] for w in ex['walls'] if nrect(w['rect'])[1] >= maxy - 1e-6)
    for a_, b_ in zip(wchain, wchain[1:]):
        dw.dim((a_, ybot), (b_, ybot), 0.464, None, 'A-COTA')
    dw.dim((sx0, ybot), (sx1, ybot), 0.804, f"{sx1 - sx0:.2f} ancho ala", 'A-COTA')
    dw.dim((minx, fy1), (minx, maxy), -1.115, f"{maxy - fy1:.2f} ala servicio", 'A-COTA')
    # wall ids
    for w in ex['walls']:
        g = R(w['rect'])
        c = g.representative_point()
        x0, y0, x1, y1 = g.bounds
        dw.place([w['id']], (c.x, c.y), h=0.05, layer='A-MURO-EXIST', r0=0.04, rot=90 if (y1 - y0) > (x1 - x0) else 0,
                 dirs=['E', 'W', 'S', 'N'] if (y1 - y0) > (x1 - x0) else ['S', 'N', 'E', 'W'])
    bb = b if not te else unary_union([box(*b), R(te['rect'])]).bounds
    px = bb[2] + 1.9
    py = b[1] - 1.5
    yy = py + title_block(dw, px, py, lay, ex, 'Condiciones existentes (levantamiento Marna’s)',
                          'LAVA_base_v3_existente.dxf') + 0.35
    yy += draw_notes(dw, px, yy, ROTULO_W, general_notes(ex, lay, False)) + 0.35
    legend(dw, px, yy, ROTULO_W)
    rows = []
    for w in ex['walls']:
        x0, y0, x1, y1 = nrect(w['rect'])
        rows.append([(w['id'], True), first_sentence(w.get('note'), 90), f"{min(x1 - x0, y1 - y0) * 100:.0f} cm",
                     'sí' if w.get('hatched') else 'no', w.get('structural_guess', '')])
    table(dw, b[0] - 1.35, b[3] + 1.6, [('ID', 1.1), ('Descripción', 7.2), ('Espesor', 1.0), ('Trama', 0.8),
                                        ('Lectura estructural (criterio visual del PDF — VERIFY ON SITE)', 5.5)],
          rows, title='MUROS EXISTENTES (lectura del PDF)')
    return dw


def finalize(dw, path):
    x0, y0, x1, y1 = msp_extents(dw.msp)
    for k, v in (('$EXTMIN', (x0, y0, 0)), ('$EXTMAX', (x1, y1, 0)), ('$LIMMIN', (x0, y0)), ('$LIMMAX', (x1, y1))):
        dw.doc.header[k] = v
    zoom.extents(dw.msp, factor=1.02)
    dw.doc.saveas(path)
    return path


# ------------------------------------------------------------------------------------------------ verification
def msp_extents(msp):
    from ezdxf import bbox
    ext = bbox.extents(msp, fast=True)
    return ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y


def check(paths, outdir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    os.makedirs(outdir, exist_ok=True)
    report = {}
    for path in paths:
        doc = ezdxf.readfile(path)
        auditor = doc.audit()
        msp = doc.modelspace()
        per_layer = Counter(e.dxf.layer for e in msp)
        kinds = Counter(e.dxftype() for e in msp)
        stem = os.path.splitext(os.path.basename(path))[0]
        report[stem] = {'errors': len(auditor.errors), 'fixes': len(auditor.fixes), 'entities': len(msp),
                        'dimensions': kinds.get('DIMENSION', 0), 'layers': dict(sorted(per_layer.items())),
                        'types': dict(kinds), 'insunits': doc.header.get('$INSUNITS'),
                        'dxfversion': doc.dxfversion}
        cfg = Configuration(background_policy=BackgroundPolicy.WHITE, lineweight_scaling=0.6)
        fig = plt.figure(figsize=(30, 22))
        ax = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        Frontend(ctx, MatplotlibBackend(ax), config=cfg).draw_layout(msp, finalize=True)
        x0_, y0_, x1_, y1_ = msp_extents(msp)
        crops = {'full': (x0_, x1_, y0_, y1_), 'plan': (-2.8, 17.8, -13.3, 2.9),
                 'kitchen': (-2.3, 7.6, -5.3, 2.4), 'wing': (-2.3, 5.2, -13.2, -4.6), 'dining': (5.5, 17.8, -5.6, 1.8),
                 'col2': (18.0, 29.0, y0_, y1_), 'col3': (29.0, x1_, y0_, y1_), 'bottom': (x0_, 18.0, y0_, -12.6)}
        for name, (x0, x1, y0, y1) in crops.items():
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            w = 24 if name in ('full', 'plan') else 16
            fig.set_size_inches(w, w * (y1 - y0) / (x1 - x0))
            fig.savefig(os.path.join(outdir, f'{stem}_{name}.png'), dpi=150 if name != 'full' else 110)
        plt.close(fig)
    with open(os.path.join(outdir, 'dxf_check.json'), 'w') as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(ROOT, 'plan'))
    ap.add_argument('--check', default=None, help='re-read the DXFs and render PNGs into this folder')
    args = ap.parse_args()
    ex = load_existing()
    lay = fix_layout_labels(load_json(os.path.join(ROOT, 'data', 'layout.json')))
    os.makedirs(args.out, exist_ok=True)
    p1 = finalize(build_proposal(ex, lay), os.path.join(args.out, 'LAVA_base_v3.dxf'))
    p2 = finalize(build_existing(ex, lay), os.path.join(args.out, 'LAVA_base_v3_existente.dxf'))
    for p in (p1, p2):
        print('wrote', p)
    if args.check:
        rep = check([p1, p2], args.check)
        for k, v in rep.items():
            print(k, {kk: v[kk] for kk in ('errors', 'fixes', 'entities', 'dimensions', 'insunits', 'dxfversion')})


if __name__ == '__main__':
    main()
