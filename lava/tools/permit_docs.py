#!/usr/bin/env python3
"""Generate the permit document package docs/permisos/ (Markdown + one PDF) from the project data files.

ANTEPROYECTO / PRELIMINAR. Every figure is read from data/*.json, so the documents always match the sheets:
  data/existing.json, data/layout.json, data/validation.json            (base + proposal, owned by the lead)
  data/life_safety_calcs.json (A-104), data/mech_calcs.json (M-101/M-102), data/elec_loads.json (E-101)  — optional
  plan/sheets.json + tools/sheets/*.py                                     (sheet list for the index)
  compliance research.json / audit.json                                    (optional; see --research / --audit)

Usage:
  python3 tools/permit_docs.py [--research research.json] [--audit audit.json] [--out docs/permisos] [--no-pdf]
                               [--png DIR [--png-pages 1,2,5]]
Writes 00_indice.md … 08_carta_administracion.md and LAVA_documentos_permiso.pdf (Markdown → HTML with python
'markdown' → PDF with Playwright/Chromium like tools/export_sheets.js; fonts inlined from tools/fonts/fonts.css).
When research/audit files are given, a trimmed copy is cached in <out>/_normativa_cache.json so later runs without
them reproduce the regulatory checklist (05).
"""
import argparse
import base64
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapely.geometry import Point, Polygon  # noqa: E402

from lavageo import R, ROOT, load_existing, load_json, seat_count  # noqa: E402

OUT_DIR = os.path.join(ROOT, 'docs', 'permisos')
CACHE_NAME = '_normativa_cache.json'
PDF_NAME = 'LAVA_documentos_permiso.pdf'

FLAG_EXT = 'EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED'
FLAG_SMOKER = 'SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED'
FLAG_DIM = 'DIMENSION TO VERIFY'
FLAG_SITE = 'VERIFY ON SITE'
FLAGS = [FLAG_EXT, FLAG_SMOKER, FLAG_DIM, FLAG_SITE]

PROJECT = 'LAVA – Contemporary Fire & BBQ'
SITE = ("local ex-Marna's, Terrazas Lindora (centro comercial abierto en régimen de condominio), "
        'Lindora, Santa Ana, San José, Costa Rica')
VALIDAR = 'a validar por el profesional responsable'

DOCS = [
    ('00', '00_indice.md', 'Índice del paquete'),
    ('01', '01_memoria_descriptiva.md', 'Memoria descriptiva'),
    ('02', '02_especificaciones_tecnicas.md', 'Especificaciones técnicas'),
    ('03', '03_seguridad_humana_y_egreso.md', 'Seguridad humana y egreso'),
    ('04', '04_calculos_preliminares_instalaciones.md', 'Cálculos preliminares de instalaciones'),
    ('05', '05_checklist_normativo.md', 'Checklist normativo'),
    ('06', '06_tramites.md', 'Trámites y permisos'),
    ('07', '07_levantamiento_en_sitio.md', 'Levantamiento en sitio'),
    ('08', '08_carta_administracion.md', 'Carta a la administración del condominio'),
]

CLIENT_FACTS = [
    'El centro comercial tiene **servicios sanitarios comunes**; LAVA los usará para clientes **y** personal (no se '
    'proyectan baños dentro del local).',
    'Se **venderán bebidas alcohólicas** (licencia municipal clase C, Ley 9047, restaurante).',
    'El centro comercial tiene **red de gas**: los equipos a gas se conectan a ella (sin cilindros en el local).',
    'No se dispone del plano general del centro comercial. Es un **centro comercial abierto** con **reglamento de '
    'condominio** vigente: ubicación de baños comunes, cuarto de basura, acometidas y cubierta se confirman en sitio y '
    'con la administración.',
]

# ------------------------------------------------------------------------------------------------ small helpers

# existing.json notes were typed without accents (copied from the PDF survey): restore them in the documents
ACC_FIX = {'salon': 'salón', 'comun': 'común', 'extraccion': 'extracción', 'division': 'división', 'collarin': 'collarín',
           'maquina': 'máquina', 'cafe': 'café', 'Geometria': 'Geometría', 'extraida': 'extraída', 'ahi': 'ahí', 'area': 'área',
           'Area': 'Área', 'administracion': 'administración', 'demolicion': 'demolición', 'ubicacion': 'ubicación', 'detras': 'detrás'}
_ACC_RE = re.compile(r'\b(' + '|'.join(ACC_FIX) + r')\b')


def acc(s):
    return _ACC_RE.sub(lambda m: ACC_FIX[m.group(1)], str(s))


def acc_md(md):
    """Accent repair on the final Markdown, leaving code spans / fenced blocks and URLs untouched."""
    parts = re.split(r'(```.*?```|`[^`\n]*`|https?://\S+)', md, flags=re.S)
    return ''.join(x if (x.startswith('`') or x.startswith('http')) else acc(x) for x in parts)


# the research notes were written in the first person and mention the research tooling: impersonal wording for a
# permit document (the facts are kept; sentences that only describe the tooling are dropped)
_NEUTRAL = [
    (r'según lo que pude leer', 'según fuentes secundarias'),
    (r'NO LO PUDE VERIFICAR', 'NO VERIFICADO'),
    (r'\b([Nn])o verifiqué en esta sesión', r'\1o se verificó'),
    (r'\b([Nn])o verifiqué', r'\1o se verificó'),
    (r'\b([Nn])o pude (confirmar|ver|revisar|verificar|leer)', r'\1o se pudo \2'),
    (r'\b([Ss])olo pude ver', r'\1olo se vieron'),
    (r'\b([Nn])o confirmé', r'\1o se confirmó'),
    (r'\bNO encontré', 'no se encontró'),
    (r'\b([Nn])o encontré', r'\1o se encontró'),
    (r'\bencontré', 'se encontró'),
    (r'lo recuerdo como', 'se cita como'),
]
_NEUTRAL_DROP = re.compile(r'WebFetch|WebSearch|proxy|verified_from_primary|en este entorno|presupuesto (compartido )?de|[Nn]o abrí', re.I)


def neutral(s):
    if not isinstance(s, str) or not s:
        return s
    for a, b in _NEUTRAL:
        s = re.sub(a, b, s)
    out = []
    for chunk in re.split(r'(?<=[.;])\s+|\n+', s):
        if chunk.strip() and not _NEUTRAL_DROP.search(chunk):
            out.append(chunk.strip())
    return ' '.join(out)


def scrub(o, key=None):
    if isinstance(o, dict):
        return {k: scrub(v, k) for k, v in o.items()}
    if isinstance(o, list):
        return [scrub(v, key) for v in o]
    if isinstance(o, str) and key not in ('url', 'id', 'req_id', 'key'):
        return neutral(o)
    return o


def cut_sent(s, k):
    """Cut at the last sentence end before k characters (no mid-sentence ellipsis)."""
    s = ' '.join(str(s or '').split())
    if len(s) <= k:
        return s
    t = s[:k]
    i = max(t.rfind('. '), t.rfind('; '))
    return (t[:i + 1] if i > k * 0.5 else cut(s, k)) + ' (texto completo en ' + CACHE_NAME + ')'


def n(v, d=2, dash='—'):
    if v is None:
        return dash
    try:
        return f'{float(v):.{d}f}'
    except (TypeError, ValueError):
        return str(v)


def esc(s):
    s = '' if s is None else str(s)
    return s.replace('|', '\\|').replace('\n', '<br>')


def table(headers, rows, align=None):
    """Markdown pipe table. align: string of l/r/c per column."""
    al = align or 'l' * len(headers)
    sep = {'l': '---', 'r': '---:', 'c': ':---:'}
    out = ['| ' + ' | '.join(esc(h) for h in headers) + ' |',
           '|' + '|'.join(sep.get(a, '---') for a in al) + '|']
    for r in rows:
        out.append('| ' + ' | '.join(esc(c) for c in r) + ' |')
    return '\n'.join(out) + '\n'


def bullets(items):
    return '\n'.join(f'- {i}' for i in items if i) + '\n'


def cut(s, k):
    s = ' '.join(str(s or '').split())
    if len(s) <= k:
        return s
    t = s[:k - 1].rsplit(' ', 1)[0]
    return t.rstrip(',;:') + ' …'


def first_sentence(s, k=170):
    s = ' '.join(str(s or '').split())
    m = re.match(r'(.+?[.;:])(\s|$)', s)
    return cut(m.group(1) if m else s, k)


def nint(v):
    try:
        return f'{int(round(float(v))):,}'.replace(',', '\u202f')
    except (TypeError, ValueError):
        return '—'


def sent(*parts):
    """Join sentences, adding a period where a part does not end with punctuation."""
    out = ''
    for p in parts:
        p = ' '.join(str(p or '').split())
        if not p:
            continue
        if out and not out.rstrip().endswith(('.', ':', ';', '!', '?', ')')):
            out = out.rstrip() + '.'
        out = (out + ' ' + p).strip()
    return out


OPEN_ES = {'double_acting_door': 'puerta de vaivén', 'door': 'puerta abatible', 'service_door': 'puerta de servicio',
           'sliding_door': 'puerta corrediza', 'opening': 'vano', 'pass_window': 'ventana de pase'}
KIND_ES = {'storefront': 'vitrina', 'window': 'ventana', 'pass': 'ventana de pase', 'opening': 'vano', 'double': 'puerta doble',
           'context': 'contexto'}


def join_notes(notes):
    """Notes split over several lines (a line without final punctuation continues on the next one)."""
    out = []
    for x in notes:
        x = str(x).lstrip('!').strip()
        if out and not out[-1].rstrip().endswith(('.', ':', ';', ')')):
            out[-1] = out[-1].rstrip() + ' ' + x
        else:
            out.append(x)
    return out


BLANK = r'\_\_\_\_\_\_\_\_\_\_'
BOX = '☐'

ST = {'OK': ('ok', 'PREVISTO'), 'PAR': ('par', 'PARCIAL'), 'ING': ('ing', 'INGENIERÍA'), 'DOC': ('doc', 'TRÁMITE'),
      'SIT': ('sit', 'VERIFICAR EN SITIO'), 'AJ': ('aj', 'AJUSTAR'), 'NA': ('na', 'NO APLICA'), 'INF': ('inf', 'INFORMATIVO')}
ST_HELP = {
    'OK': 'Resuelto en el anteproyecto v3 (dibujado o especificado); falta la validación y firma del profesional.',
    'PAR': 'Resuelto en parte o condicionado a una aprobación, un documento o un dato de sitio.',
    'ING': 'Queda para el diseño de ingeniería (cálculo, selección de equipo, listado del fabricante).',
    'DOC': 'Trámite o documento administrativo; no se resuelve en el plano.',
    'SIT': 'No determinable sin levantamiento en sitio o información de la administración.',
    'AJ': 'El anteproyecto no alcanza el criterio o el margen es insuficiente: hay que ajustar o justificar.',
    'NA': 'No aplica con la solución adoptada (se indica por qué).',
    'INF': 'Criterio informativo o de clasificación; no exige un elemento en el plano.',
}


def nw(s):
    return f'<span class="nw">{s}</span>'


def badge(code):
    c, t = ST.get(code, ST['INF'])
    return f'<span class="st st-{c}">{t}</span>'


def load_opt(path):
    try:
        return load_json(path) if path and os.path.exists(path) else None
    except (OSError, ValueError):
        return None


def rect_len(r):
    x0, y0, x1, y1 = r
    return max(abs(x1 - x0), abs(y1 - y0))


def eq_dims(e):
    """(front width, depth) of an equipment item, as in tools/report.py."""
    x0, y0, x1, y1 = e['rect']
    wd, dp = abs(x1 - x0), abs(y1 - y0)
    if e.get('front') in ('N', 'S'):
        return wd, dp
    if e.get('front') in ('E', 'W'):
        return dp, wd
    return max(wd, dp), min(wd, dp)


def dims_str(e, star=True):
    a, b = eq_dims(e)
    s = f'{a:.2f} × {b:.2f}'
    if e.get('h') is not None and not e.get('overhead'):
        s += f' × {float(e["h"]):.2f}'
    return s + (' \\*' if (star and e.get('tbv')) else '')


def mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return None


# ------------------------------------------------------------------------------------------------ data model


class Facts:
    """Everything the documents need, computed once from the data files."""

    def __init__(self, research_path=None, audit_path=None, out_dir=OUT_DIR):
        d = lambda *p: os.path.join(ROOT, 'data', *p)  # noqa: E731
        self.ex = load_existing()
        self.lay = load_json(d('layout.json'))
        self.val = load_opt(d('validation.json')) or {}
        self.m = self.val.get('metrics', {})
        self.lsc = load_opt(d('life_safety_calcs.json'))
        self.mech = load_opt(d('mech_calcs.json'))
        self.elec = load_opt(d('elec_loads.json'))
        self.content = load_opt(d('report_content.json')) or {}
        _fix_layout_wording(self.lay)
        self.meta = self.lay.get('meta', {})
        self.ver = self.meta.get('version', '?')
        self.date = self.meta.get('date', '')
        self.ls = self.lay.get('life_safety', {})
        self.mep = self.lay.get('mep', {})
        self.out_dir = out_dir

        # zones
        self.zones = self.lay.get('zones', [])
        self.zpoly = {z['id']: Polygon(z['poly']) for z in self.zones}
        self.zname = {z['id']: z.get('short') or z.get('name') for z in self.zones}
        self.zfull = {z['id']: z.get('name') or z.get('short') for z in self.zones}
        self.zarea = {z['id']: z['area_m2'] for z in self.m.get('zones', [])}
        if not self.zarea:
            from lavageo import premises
            prem = premises(self.ex)
            self.zarea = {k: round(p.intersection(prem).area, 2) for k, p in self.zpoly.items()}
        self.area = self.m.get('premises_area_m2')
        if self.area is None:
            self.area = round(Polygon(self.ex['premises_polygon']).area, 2)

        # equipment / furniture
        self.eq = {e['id']: e for e in self.lay.get('equipment', [])}
        self.bykey = {}
        for e in self.lay.get('equipment', []):
            self.bykey.setdefault(e.get('key'), []).append(e)
        self.seats = seat_count(self.lay)
        self.tables = self.lay.get('tables', [])
        self.n2 = sum(1 for t in self.tables if int(t.get('seats', 0)) <= 2)
        self.n4 = sum(1 for t in self.tables if int(t.get('seats', 0)) >= 4)
        self.chairs = len(self.lay.get('chairs', []))
        self.banq = self.lay.get('banquettes', [])
        self.banq_seats = sum(int(b.get('seats', 0)) for b in self.banq)
        self.acc_tables = [t['id'] for t in self.tables if t.get('accessible')]
        self.tbv = [e for e in self.lay.get('equipment', []) if e.get('tbv')]

        # walls / openings
        self.exwall = {w['id']: w for w in self.ex.get('walls', [])}
        self.exdoor = {x['id']: x for x in self.ex.get('doors', [])}
        self.nw = {w['id']: w for w in self.lay.get('new_walls', [])}
        self.op = {o.get('label') or o['id']: o for o in self.lay.get('new_openings', [])}
        self.dent = self.exdoor.get('D-ENT', {})
        self.ceiling = float((self.ex.get('ceiling') or {}).get('height_assumed', 3.0))
        self.part_x = self.m.get('new_partition_x')
        self.shift = self.m.get('partition_shift_m')
        pp = Polygon(self.ex['premises_polygon'])
        self.bounds = pp.bounds

        # life safety
        self.declared = self.ls.get('capacity_declared')
        occ = (self.lsc or {}).get('occupant_load', {})
        self.occ_rows = occ.get('rows', [])
        self.occ_zone = occ.get('total_rounded_per_zone')
        self.occ_use = occ.get('total_rounded_per_use')
        self.occ_raw = occ.get('total_unrounded')
        self.threshold = occ.get('nfpa101_assembly_threshold', 50)
        self.paths = [p for p in (self.lsc or {}).get('egress_paths', [])]
        uniq, seen = [], set()
        for p in self.paths:
            key = (round(p['length'], 2), tuple(map(tuple, p.get('polyline', [])))[:2])
            if p['id'] == 'E0' and key in seen:
                continue
            seen.add(key)
            uniq.append(p)
        self.paths_u = uniq
        summ = (self.lsc or {}).get('summary', {})
        self.longest = summ.get('longest_path') or (max(self.paths, key=lambda p: p['length']) if self.paths else None)
        self.longest30 = summ.get('longest_path_at_0.30m_clearance')
        self.ls_issues = summ.get('issues', [])
        self.limits = self.ls.get('limits', {})
        self.lim_common = float(self.limits.get('common_path_m', 22.86))
        self.lim_travel = float(self.limits.get('travel_m', 45.72))
        self.checks = {c['id']: c for c in (self.lsc or {}).get('device_checks', [])}
        self.exits_c = (self.lsc or {}).get('exits', [])
        self.margin = (self.longest['limit'] - self.longest['length']) if self.longest else None
        # restroom budget (36 m, INVU — verificar): the most conservative internal distance among A-104 (E1, and E1 at
        # 0.30 m from corners) and A-105 (grid walk to the D-ENT plane)
        cand = [(self.longest['length'], 'A-104 ' + self.longest['id'])] if self.longest else []
        if self.longest30:
            cand.append((self.longest30['length'], f"A-104 {self.longest30['path']} a 0.30 m de esquinas"))
        self.d_far_a105 = _a105_far(self.ex, self.lay)
        if self.d_far_a105:
            cand.append((self.d_far_a105, 'A-105'))
        self.far_cand = cand
        self.far_int = max(cand) if cand else None
        self.restroom_budget = (36.0 - self.far_int[0]) if self.far_int else None

        # routes / widths
        self.routes = self.m.get('routes', [])
        self.conns = self.m.get('connections', [])
        self.main_aisle = min((r['min_width'] for r in self.routes
                               if r.get('kind') in ('guest', 'server') and r.get('required', 0) >= 1.1), default=None)
        # the plans (A-101 / DXF) dimension the main aisle from layout.dims: use the same figure in the documents
        dm_ = next((d for d in self.lay.get('dims', []) if 'pasillo principal' in str(d.get('label') or '')), None)
        if dm_:
            self.main_aisle = abs(dm_['b'][1] - dm_['a'][1]) if abs(dm_['b'][0] - dm_['a'][0]) < 1e-6 else abs(dm_['b'][0] - dm_['a'][0])
        self.min_route = min(self.routes, key=lambda r: r['min_width']) if self.routes else None

        # geometry checks used by the checklist
        self.fryer_flame = None
        fr = [e for e in self.lay.get('equipment', []) if str(e.get('key', '')).startswith('freidora')]
        fl = [e for e in self.lay.get('equipment', []) if e.get('key') in ('cocina_4q', 'parrilla')]
        if fr and fl:
            self.fryer_flame = min((R(a['rect']).distance(R(b['rect'])), a['id'], b['id']) for a in fr for b in fl)
        self.fuel = (self.bykey.get('fuel_storage') or [None])[0]
        self.smoker = (self.bykey.get('smoker') or [None])[0]
        self.parrilla = (self.bykey.get('parrilla') or [None])[0]
        self.fuel_d = {}
        if self.fuel:
            for o in [self.smoker, self.parrilla]:
                if o:
                    self.fuel_d[o['id']] = R(self.fuel['rect']).distance(R(o['rect']))
        self.hoods = [e for e in self.lay.get('equipment', []) if e.get('key') == 'hood']
        self.hood_serves = {}
        fire = [e for e in self.lay.get('equipment', []) if e.get('cat') == 'fire' and not e.get('stack_with')]
        for h in self.hoods:
            hb = R(h['rect'])
            self.hood_serves[h['id']] = [e['id'] for e in fire if hb.intersection(R(e['rect'])).area > 0.05]
        self.hood_lower = float(self.nw.get('NW-2', {}).get('h', 2.05)) if 'NW-2' in self.nw else None
        self.handwash = [e for e in self.lay.get('equipment', []) if str(e.get('key', '')).startswith('handwash')]
        self.niche = next((dc for dc in self.lay.get('decor', []) if dc.get('type') == 'firewood_niche'), None)

        # MEP
        self.gas = self.mep.get('gas', {})
        self.gas_network = 'red' in str(self.gas.get('source', '')).lower()
        self.devices = (self.elec or {}).get('devices', {})
        self.circuits = (self.elec or {}).get('circuits', [])
        self.eq_circ = {}
        for c in self.circuits:
            if c.get('group') == 'X':
                continue
            for tok in re.findall(r'[A-Z]{1,3}-?\d+', str(c.get('ref', ''))):
                self.eq_circ.setdefault(tok, []).append(c)
        self.gas_kw = {c['id']: c for c in ((self.mech or {}).get('gas', {}) or {}).get('consumers', [])}

        # sheets
        self.sheets = sheet_index()
        self.sheet_ids = {s['id'] for s in self.sheets}
        lay_t = mtime(os.path.join(ROOT, 'data', 'layout.json'))
        pdf_t = mtime(os.path.join(ROOT, 'plan', 'LAVA_test-fit_planos_A2.pdf'))
        self.plan_pdf_stale = bool(lay_t and pdf_t and pdf_t < lay_t)
        self.plan_pdf_exists = pdf_t is not None

        # regulatory research / audit (optional, cached)
        self.research, self.audit, self.norm_source = load_normativa(research_path, audit_path, out_dir)
        self.research, self.audit = scrub(self.research), scrub(self.audit)

    # ---------------------------------------------------------------- convenience
    def zone_at(self, pt):
        p = Point(pt)
        for zid, poly in self.zpoly.items():
            if poly.buffer(1e-6).contains(p):
                return zid
        return min(self.zpoly, key=lambda k: self.zpoly[k].distance(p)) if self.zpoly else None

    def zlabel(self, pt):
        z = self.zone_at(pt)
        return f'{z} · {self.zname.get(z, "")}' if z else '—'

    def eqz(self, zid):
        poly = self.zpoly.get(zid)
        out = []
        for e in self.lay.get('equipment', []):
            c = R(e['rect']).centroid
            if poly is not None and poly.buffer(0.02).contains(c):
                out.append(e)
        return out

    def exh(self, sid):
        for s in ((self.mech or {}).get('exhaust', {}) or {}).get('systems', []):
            if s['id'] == sid:
                return s
        return None


def _fix_layout_wording(lay):
    """Document-only wording fixes on the in-memory layout (layout.json is owned by make_layout.py and is not modified)."""
    for e in lay.get('equipment', []):
        # K3: DE 37308-S makes a hand-wash sink in the kitchen mandatory (research S-07) — same wording as M-101
        if str(e.get('key', '')).startswith('handwash') and '(recomendado)' in str(e.get('label', '')):
            e['label'] = e['label'].replace('(recomendado)', '(obligatorio)')
            if str(e.get('note', '')).startswith('Recomendado'):
                e['note'] = 'Obligatorio (DE 37308-S, verificar)' + e['note'][len('Recomendado'):]
    ps = (lay.get('life_safety') or {}).get('pull_station') or {}
    if ps.get('note'):
        # the '≈3 m de la parrilla' of the note contradicts the distances measured on A-104: they are quoted instead
        ps['note'] = re.sub(r',?\s*≈\s*[\d.]+\s*m de la parrilla', '', ps['note'])
    return lay


def _a105_far(ex, lay):
    """Walking distance from the farthest point of the premises to D-ENT as measured on A-105 (None if unavailable)."""
    try:
        from sheets.s105_accesibilidad import analyse
        return round(float(analyse(ex, lay)['d_far'][0]), 2)
    except Exception:  # noqa: BLE001 — optional cross-check
        return None


def sheet_index():
    """plan/sheets.json (built) merged with the sheet modules present in tools/sheets (not yet built)."""
    plan = os.path.join(ROOT, 'plan')
    idx = {}
    built = load_opt(os.path.join(plan, 'sheets.json')) or []
    lay_t = mtime(os.path.join(ROOT, 'data', 'layout.json'))
    for d in built:
        idx[d['id']] = dict(d, built=True, module=None)
    pat = re.compile(r"'id':\s*'([A-Z]\d{3})',\s*'file':\s*'([^']+)',\s*'title':\s*'([^']+)',\s*'order':\s*(\d+)")
    for f in sorted(glob.glob(os.path.join(ROOT, 'tools', 'sheets', '*.py'))):
        name = os.path.basename(f)[:-3]
        if name.startswith('_'):
            continue
        try:
            src = open(f, encoding='utf-8').read()
        except OSError:
            continue
        for m in pat.finditer(src):
            sid, file, title, order = m.group(1), m.group(2), m.group(3), int(m.group(4))
            if sid in idx:
                idx[sid]['module'] = name
            else:
                idx[sid] = {'id': sid, 'file': file, 'title': title, 'order': order, 'built': False, 'module': name}
    for s in idx.values():
        p = os.path.join(plan, s['file'])
        t = mtime(p)
        s['exists'] = t is not None
        s['stale'] = bool(t and lay_t and t < lay_t)
    return sorted(idx.values(), key=lambda s: s['order'])


def sheet_tag(sid):
    return f'{sid[0]}-{sid[1:]}' if re.match(r'^[A-Z]\d{3}$', sid) else sid


SHEET_SIGN = {'A': 'Arquitecto responsable', 'M': 'Ingeniero mecánico', 'E': 'Ingeniero electricista'}
SHEET_DISC = {'A': 'Arquitectura', 'M': 'Mecánica', 'E': 'Electricidad'}


def load_normativa(research_path, audit_path, out_dir):
    """research.json + audit.json when given (a trimmed copy is cached), else the cache in out_dir."""
    cache_p = os.path.join(out_dir, CACHE_NAME)
    research = load_opt(research_path) if research_path else None
    audit = load_opt(audit_path) if audit_path else None
    if research or audit:
        cache = load_opt(cache_p) or {}
        if research:
            cache['research'] = {
                dom: {'adopted_editions': dd.get('adopted_editions', ''), 'notes': dd.get('notes', ''),
                      'sources': [{k: s.get(k) for k in ('title', 'url', 'date_or_edition', 'fetched')} for s in dd.get('sources', [])],
                      'requirements': [{k: r.get(k) for k in ('id', 'authority', 'source_ref', 'requirement', 'criterion', 'applies_when',
                                                              'checkable_on_plan', 'confidence', 'verified_from_primary', 'url')}
                                       for r in dd.get('requirements', [])]}
                for dom, dd in research.items()}
            cache['research_file'] = os.path.basename(research_path)
        if audit:
            cache['audit'] = {
                'domains': [{'domain': dd.get('domain'), 'findings': [
                    {k: f.get(k) for k in ('req_id', 'topic', 'status', 'severity', 'citation', 'fix')} for f in dd.get('findings', [])]}
                    for dd in audit.get('domains', [])],
                'verification': {'verdicts': [{k: v.get(k) for k in ('key', 'verdict', 'reason')}
                                              for v in (audit.get('verification') or {}).get('verdicts', [])],
                                 'missing': (audit.get('verification') or {}).get('missing', [])}}
            cache['audit_file'] = os.path.basename(audit_path)
        os.makedirs(out_dir, exist_ok=True)
        with open(cache_p, 'w', encoding='utf-8') as fh:
            json.dump(cache, fh, indent=1, ensure_ascii=False)
        src = 'archivos de investigación y auditoría entregados (copia en ' + CACHE_NAME + ')'
        return cache.get('research'), cache.get('audit'), src
    cache = load_opt(cache_p)
    if cache:
        return cache.get('research'), cache.get('audit'), f'copia guardada {CACHE_NAME}'
    return None, None, 'no disponible'


# ------------------------------------------------------------------------------------------------ common blocks


def header(F, num, title, purpose):
    return (f'# {num} · {title}\n\n'
            f'**{PROJECT}** — {SITE}  \n'
            f'Anteproyecto v{F.ver} · {F.date} · documento generado desde los datos del proyecto (`tools/permit_docs.py`)\n\n'
            f'> **ANTEPROYECTO / PRELIMINAR** — no es un documento constructivo ni una declaración de cumplimiento: '
            f'todo lo aquí indicado es **{VALIDAR}** (CFIA) y por las ingenierías. Las citas normativas provienen '
            f'mayormente de fuentes secundarias y se marcan "verificar".\n\n'
            f'{purpose}\n\n')


def flags_block():
    return ('Banderas del anteproyecto (se mantienen literalmente en inglés en láminas y documentos):\n\n'
            + bullets([f'**{x}**' for x in FLAGS]) + '\n')


def sheet_ref(F, *ids):
    out = []
    for i in ids:
        s = next((s for s in F.sheets if s['id'] == i), None)
        out.append(f'{sheet_tag(i)} ({s["title"]})' if s else sheet_tag(i))
    return ', '.join(out)


def energy_of(F, e):
    parts = []
    if e.get('key') in ('parrilla', 'smoker'):
        parts.append('carbón / leña')
    if e['id'] in (F.gas.get('consumers') or []):
        g = F.gas_kw.get(e['id'])
        parts.append(f'gas de red ≈{n(g["kW_typ"], 1)} kW\\*' if g else 'gas de red')
    for c in F.eq_circ.get(e['id'], []):
        parts.append(f'{c["V"]} V · {c["VA"] / 1000:.2f} kVA\\* (circ. {c["circuit"]})')
    return '; '.join(dict.fromkeys(parts)) or '—'


PERF = {
    'parrilla': 'Parrilla de carbón/leña de acero, listada (UL/ETL) o con memoria de materiales aceptada por Bomberos; hogar ≤0.14 m³ '
                'o manguera fija (NFPA 96 cap. 14, verificar); base y respaldo incombustibles; bandeja de cenizas metálica; holguras según listado.',
    'cocina_4q': 'Cocina comercial de 4 quemadores a gas, listada para el tipo de gas de la red (GN o GLP — VERIFY), válvulas de seguridad '
                 'con termopar, conexión con conector listado ≤1.5 m y cable de restricción.',
    'plancha': 'Plancha a gas listada, termostática, sin llama expuesta (condición de la separación freidoras–llama abierta).',
    'freidora_1': 'Freidora a gas listada (UL 197 / NSF 4 o equivalente), termostato + límite de alta temperatura independiente; '
                  '≤36 kg de aceite; encendido 120 V vía contactor KS-1 (corte al disparar la supresión).',
    'hood': 'Campana listada UL 710 o fabricada en acero ≥1.09 mm (18 MSG) / inox ≥0.94 mm (20 MSG) con uniones soldadas estancas '
            '(NFPA 96 cap. 5); filtros listados UL 1046; luminaria listada. ' + FLAG_EXT + '.',
    'mesa_1': 'Mesa de acero inoxidable AISI 304, NSF 2, entrepaño inferior, patas regulables, uniones selladas.',
    'oven': 'Horno eléctrico de convección de mesa con campana de recirculación integrada listada UL 710B (ventless) y enclavamiento '
            'propio; 208 V (VERIFY tensión disponible).',
    'handwash': 'Lavamanos exclusivo para manos, inox, con agua fría y caliente mezclada (≈43 °C), grifo de accionamiento no manual '
                'recomendado, jabón líquido, toallas desechables y basurero de pedal (DE 37308-S, verificar).',
    'smoker': 'Smoker vertical listado para uso comercial en interior (UL/ETL) con chimenea propia (NFPA 211) o campana independiente; '
              'piso incombustible; holguras según listado. ' + FLAG_SMOKER + '. Alternativa: smoker eléctrico o de pellet listado.',
    'holding': 'Gabinete de mantenimiento en caliente eléctrico, NSF 4, 120 V.',
    'fuel_storage': 'Gabinete metálico cerrado para la provisión de un día, nada encima, ≥0.915 m de los aparatos de combustible sólido '
                    '(NFPA 96 cap. 14, verificar).',
    'sink_2t': 'Fregadero de 2 tanques inox AISI 304 NSF 2 con escurridores y ducha de prelavado; agua fría y caliente; descarga a GT-1.',
    'mop_sink': 'Pileta de aseo de piso con llave de manguera y rompevacío; recibe la descarga T&P del termotanque (indirecta).',
    'mesa_opt': 'Mesa inox AISI 304 NSF 2 para racks limpios.',
    'waste_bins': '3 contenedores con tapa y pedal (orgánicos / valorizables / ordinarios) — separación en la fuente (Ley 8839, verificar).',
    'chem_cabinet': 'Gabinete cerrado y rotulado para químicos, con bandeja antiderrame, separado de alimentos y loza limpia.',
    'grease_trap': 'Interceptor de grasa hidromecánico accesible, tapa hermética; caudal según 04 (PDI G-101 referencia; CIHSE rige).',
    'shelf_wash': 'Estantería inox o epóxica NSF, 4 niveles.',
    'fridge_2d': 'Refrigerador comercial NSF 7 con termómetro visible; 120 V.',
    'freezer_1d': 'Congelador comercial NSF 7 con termómetro visible; 120 V.',
    'mesa_fria': 'Mesa refrigerada NSF 7; 120 V.',
    'mesa_esquina': 'Esquinero inox AISI 304 que cierra la mesada en L sin rendijas.',
    'mesa_2': 'Mesa de trabajo inox AISI 304 NSF 2.',
    'shelf_4': 'Estantería inox o epóxica NSF, primer nivel ≥0.15 m del piso.',
    'shelf_dry': 'Estantería de almacén seco NSF, primer nivel ≥0.15 m del piso, separada de químicos.',
    'barra': 'Barra de bebidas con enfriador bajo barra (NSF 7) y pileta de barra PB-1 con agua fría y caliente (CA-2).',
    'lockers': 'Casilleros metálicos ventilados, fuera de áreas de alimentos.',
    'caja': 'Tramo de mostrador accesible h 0.80 × 0.90 m con espacio libre inferior (Ley 7600, DE 26831-MP art. 148, verificar).',
    'pass': 'Repisa de pase con lámparas de calor (L-7), 120 V.',
    'pos': 'POS e impresora de comandas en circuito dedicado.',
    'delivery_staging': 'Atril de recepción con repisa para pedidos listos.',
}
PERF['freidora_2'] = PERF['freidora_1']
PERF['handwash_k'] = PERF['handwash_cold'] = PERF['handwash_bar'] = PERF['handwash']


# ------------------------------------------------------------------------------------------------ 00 índice


def _pm_dist(F):
    pm = F.checks.get('PM-1') or {}
    dh = pm.get('dist_to_hoods') or {}
    if not dh:
        return ''
    return ('Distancia medida en A-104 a las campanas: ' + ', '.join(f'{k} {n(v)} m' for k, v in dh.items())
            + ' — la referencia de 3–6 m (IFC; NFPA 17A / 96 según edición) no se alcanza: validar la ubicación con el listado del '
            'sistema y Bomberos (VERIFICAR).' if not pm.get('ifc_ref_3_6m_ok', True) else '.')


def doc_00(F):
    L = [header(F, '00', 'Índice del paquete',
                'Contenido del paquete de anteproyecto para permisos ("anteproyecto listo para revisión y firma"): láminas, '
                'documentos, datos de origen, lo que falta y quién lo hace.')]
    L.append('## 1. Proyecto\n\n')
    L.append(table(['Concepto', 'Dato'], [
        ('Proyecto', PROJECT),
        ('Ubicación', SITE),
        ('Obra', 'Remodelación interior (acondicionamiento) de local comercial existente — obra mayor'),
        ('Uso propuesto', 'Restaurante de parrilla y ahumados, con venta de bebidas alcohólicas (licencia clase C)'),
        ('Área interior del local', f'{n(F.area)} m² (sobre el PDF de Marna\'s; {FLAG_SITE})'),
        ('Capacidad máxima declarada', f'{F.declared} personas (clientes + personal)'),
        ('Asientos', f'{F.seats} en {len(F.tables)} mesas ({F.n2} de 2 y {F.n4} de 4): {F.chairs} sillas + {F.banq_seats} puestos en banca'),
        ('Versión de datos', f'layout v{F.ver} · {F.date}'),
        ('Estado', 'ANTEPROYECTO / PRELIMINAR — ' + VALIDAR + ' (CFIA)'),
    ]))
    L.append('\n## 2. Láminas\n\n')
    L.append('Juego de láminas A2 a 1:50 generado desde los mismos datos (`tools/plan_svg.py` + módulos de `tools/sheets/`). '
             'Estado según `plan/sheets.json`:\n\n')
    rows = []
    for s in F.sheets:
        if s['built'] and s['exists'] and not s['stale']:
            st = 'generada'
        elif s['built'] and s['stale']:
            st = 'regenerar (datos más recientes)'
        elif s['built']:
            st = 'en índice, archivo faltante'
        else:
            st = 'módulo listo · falta ejecutar `tools/build_all.sh`'
        k = s['id'][0]
        sign = SHEET_SIGN.get(k, 'Profesional responsable')
        if s['id'] == 'A104':
            sign = 'Arquitecto / ing. protección contra incendios'
        rows.append((sheet_tag(s['id']), s['title'], f'{SHEET_DISC.get(k, "")} · {sign}', f'`{s["file"]}`', st))
    L.append(table(['Lámina', 'Título', 'Disciplina · firma', 'Archivo', 'Estado'], rows))
    pdfst = ('desactualizado respecto de layout.json: regenerar' if F.plan_pdf_stale else
             ('generado' if F.plan_pdf_exists else 'no generado'))
    L.append('\n' + bullets([
        f'PDF del juego completo: `plan/LAVA_test-fit_planos_A2.pdf` ({pdfst}).',
        'Base editable para AutoCAD: `plan/LAVA_base_v3.dxf` (propuesta) y `plan/LAVA_base_v3_existente.dxf` (existente), '
        '`tools/export_dxf.py`.' if os.path.exists(os.path.join(ROOT, 'plan', 'LAVA_base_v3.dxf')) else None,
        'Cada lámina lleva en el cajetín la casilla PROFESIONAL RESPONSABLE (CFIA) en blanco para nombre, carné y firma.',
    ]))
    L.append('\n## 3. Documentos de este paquete (`docs/permisos/`)\n\n')
    what = {
        '00': ('Este índice: láminas, documentos, datos, pendientes.', 'Todos'),
        '01': ('Proyecto, ubicación, áreas, programa, zonificación, capacidad, sistemas y cambios respecto de Marna\'s.', 'Arquitecto, APC'),
        '02': ('Especificaciones por desempeño: demolición, particiones, acabados, puertas, equipos, campanas, supresión, gas, '
               'hidrosanitario, electricidad, señalización, accesibilidad.', 'Arquitecto, ingenierías, contratista'),
        '03': ('Carga de ocupantes, clasificación, salidas, recorridos medidos vs límites, señalización, emergencia, '
               'extintores, supresión, detección.', 'Arquitecto, Bomberos'),
        '04': ('Caudales de campanas, ductos, aire de reposición, gas, agua caliente, trampa de grasa, aparatos y cuadro de cargas '
               'eléctricas (PRELIMINAR).', 'Ing. mecánico, ing. electricista'),
        '05': ('Requisito / fuente / estado en el anteproyecto / qué debe verificar el profesional.', 'Profesional responsable'),
        '06': ('Paso a paso de trámites: condominio, uso de suelo, CFIA/APC, licencia, bitácora, patente, licores, rótulo, PSF, '
               'gas, póliza.', 'Cliente, arquitecto'),
        '07': ('Formulario de levantamiento en sitio con cada VERIFY ON SITE / DIMENSION TO VERIFY de los datos.', 'Arquitecto (visita)'),
        '08': ('Carta modelo a la administración del condominio con todas las solicitudes.', 'Cliente'),
    }
    rows = [(f'`{fn}`', t, *what[num]) for num, fn, t in DOCS]
    rows.append((f'`{PDF_NAME}`', 'Todos los documentos en un PDF (A4)', 'Portada + documentos 00–08', 'Revisión e impresión'))
    L.append(table(['Archivo', 'Documento', 'Contenido', 'Para'], rows))
    L.append('\n## 4. Datos de origen\n\n')
    src = [
        ('`data/existing.json`', 'Condiciones existentes leídas del PDF de Marna\'s (muros, columnas, puertas, ductos, puntos húmedos, cielo)', 'levantamiento del PDF'),
        ('`data/layout.json`', 'Propuesta v' + F.ver + ': zonas, equipos, mobiliario, muros y vanos nuevos, seguridad humana, MEP', '`tools/make_layout.py`'),
        ('`data/validation.json`', 'Áreas por zona, anchos libres por ruta, verificaciones automáticas', '`tools/validate.py`'),
        ('`data/life_safety_calcs.json`', 'Carga de ocupantes, recorridos de egreso, extintores (A-104)' if F.lsc else 'no disponible', '`tools/sheets/s104_seguridad.py`'),
        ('`data/mech_calcs.json`', 'Caudales, ductos, gas, agua caliente, trampa de grasa (M-101/M-102)' if F.mech else 'no disponible', '`tools/sheets/s401_mecanica.py`'),
        ('`data/elec_loads.json`', 'Circuitos, demanda, tablero, enclavamientos (E-101)' if F.elec else 'no disponible', '`tools/sheets/s501_electrica.py`'),
        (f'`docs/permisos/{CACHE_NAME}`', 'Investigación normativa y auditoría preliminar (copia recortada)' if F.research else 'no disponible', 'investigación de cumplimiento'),
    ]
    L.append(table(['Archivo', 'Contenido', 'Generado por'], src))
    L.append('\n## 5. Qué falta y quién lo hace\n\n')
    todo = [
        ('Visita y levantamiento en sitio (formulario 07); ajustar planos a lo medido', 'Arquitecto responsable', '07, VERIFY ON SITE'),
        ('Contrato de consultoría CFIA y registro en el APC; firma digital de cada lámina', 'Arquitecto + ingenieros', '06 paso 4'),
        ('Diseño de extracción, aire de reposición y supresión (selección de campanas listadas, ventiladores, ducto, remates)',
         'Ingeniero mecánico + proveedor certificado del sistema de supresión', FLAG_EXT),
        ('Validar ubicación, chimenea y requisitos del smoker (o cambiar a smoker eléctrico / pellet listado)', 'Ingeniero mecánico + Bomberos', FLAG_SMOKER),
        ('Diseño de gas desde la red del centro comercial (tipo, presión, capacidad, ruta, válvulas, detector)', 'Ingeniero mecánico + administración', 'M-102, 04'),
        ('Diseño hidrosanitario: agua fría/caliente, desagües, ventilación, trampa de grasa, sifones de piso', 'Ingeniero mecánico (CIHSE)', 'M-101, 04'),
        ('Diseño eléctrico: acometida, TE-1, circuitos, emergencia, enclavamientos, puesta a tierra', 'Ingeniero electricista (NEC 2020)', 'E-101, 04'),
        ('Revisión estructural: penetraciones de losa (EXT-2, EXT-3, AR-1), ventiladores en cubierta, dintel de PS-1, anclaje sísmico',
         'Ingeniero estructural', '02 §17'),
        ('Planta de cubierta con ventiladores, chimenea y distancias de remate (no incluida en este paquete)', 'Ingeniero mecánico + arquitecto', 'NFPA 96 §7.8'),
        ('Fichas técnicas y listados de todos los equipos marcados * (DIMENSION TO VERIFY)', 'Cliente / proveedor de cocina', f'{len(F.tbv)} equipos, 07 §M'),
        ('Carta de la administración (obras, baños comunes, basura, gas, cubierta, PS-1, puerta, rótulos, horario)', 'Cliente', '08'),
        ('Autorización del propietario registral / arrendador', 'Cliente', '06 paso 1'),
        ('Uso de suelo conforme (restaurante con venta de licor)', 'Cliente', '06 paso 2'),
        ('Confirmar con el Área Rectora de Salud que se aceptan los baños comunes del centro comercial', 'Cliente + arquitecto', '03, 05 PER-13'),
        ('Plan de emergencias, capacitación, contratos de limpieza de ductos y mantenimiento de supresión', 'Operador (LAVA)', '03 §14'),
    ]
    pend = [sheet_tag(s['id']) for s in F.sheets if not s['built']]
    if pend or F.plan_pdf_stale:
        txt = 'Ejecutar `tools/build_all.sh` antes de cualquier revisión'
        if pend:
            txt += ': incluye en plan/ las láminas ' + ', '.join(pend)
        if F.plan_pdf_stale:
            txt += ('; ' if pend else ': ') + 'regenera PNG y PDF desde layout v' + F.ver + ' (hoy desactualizados)'
        todo.insert(0, (txt + '; luego volver a correr `tools/permit_docs.py`', 'Equipo del anteproyecto', 'plan/sheets.json'))
    L.append(table(['#', 'Pendiente', 'Responsable', 'Referencia'], [(i + 1, *r) for i, r in enumerate(todo)], 'rlll'))
    L.append('\n## 6. Cómo regenerar\n\n')
    L.append('```bash\ntools/build_all.sh                      # validación + láminas + informe + app\n'
             'python3 tools/permit_docs.py           # estos documentos + PDF (lee plan/sheets.json)\n'
             'python3 tools/permit_docs.py --research <research.json> --audit <audit.json>   # actualiza la copia normativa\n```\n\n')
    L.append(flags_block())
    return ''.join(L)


# ------------------------------------------------------------------------------------------------ 01 memoria


def doc_01(F):
    L = [header(F, '01', 'Memoria descriptiva',
                'Descripción del proyecto para la revisión del profesional responsable y el ingreso al APC. Cifras tomadas de '
                '`data/*.json` (las mismas de las láminas).')]
    x0, y0, x1, y1 = F.bounds
    L.append('## 1. Datos generales\n\n')
    L.append(table(['Concepto', 'Dato'], [
        ('Proyecto', f'{PROJECT} — restaurante de parrilla (carbón/leña) y ahumados'),
        ('Ubicación', SITE),
        ('Local', "Ex-Marna's (cafetería). Finca filial N.° [completar] · plano catastrado [completar]"),
        ('Propietario / arrendatario', '[completar] / [completar]'),
        ('Tipo de obra', 'Remodelación interior de local comercial existente (obra mayor: demoliciones livianas, muros nuevos, '
                         'campanas y ductos, gas, electricidad, hidrosanitario)'),
        ('Uso propuesto', 'Restaurante con servicio a la mesa y venta de bebidas alcohólicas (licencia clase C, Ley 9047 — a tramitar)'),
        ('Área interior', f'{n(F.area)} m² (medida sobre el PDF de Marna\'s, tolerancia ±2 cm — {FLAG_SITE})'),
        ('Capacidad máxima declarada', f'{F.declared} personas, clientes + personal (ver 03)'),
        ('Asientos', f'{F.seats}: {F.chairs} sillas + {F.banq_seats} puestos en banca · {F.n2} mesas de 2 y {F.n4} de 4 · '
                     f'mesas accesibles {", ".join(F.acc_tables) or "—"}'),
        ('Base geométrica', (F.ex.get('meta') or {}).get('source', '')),
        ('Versión', f'Anteproyecto v{F.ver} · {F.date}'),
    ]))
    L.append('\n## 2. Condiciones informadas por el cliente\n\n' + bullets(CLIENT_FACTS))
    L.append('\n## 3. Local existente\n\n')
    dp = (F.ex.get('dimensions_from_pdf') or {})
    ax = (F.ex.get('meta') or {}).get('axes', {})
    hood = F.ex.get('existing_hood') or {}
    rows = [
        ('Franja principal (cocina + salón)', dp.get('interior_top_strip', '')),
        ('Ala de servicio', f"{dp.get('wing_north', '')}; {dp.get('wing_south', '')}; largo {dp.get('wing_length', '')}"),
        ('Ejes de columnas', f"A–B {n(ax.get('B', 0) - ax.get('A', 0))} m · B–C {n(ax.get('C', 0) - ax.get('B', 0))} m · 1–2 {n(ax.get('row2', 0) - ax.get('row1', 0))} m"),
        ('Columnas', '; '.join(f"{c['id']}: {c.get('note', '')}" for c in F.ex.get('columns', []))),
        ('Puerta principal D-ENT', f"{n(F.dent.get('width'))} m, doble, {F.dent.get('swing', '')} — {F.dent.get('note', '')}"),
        ('Vitrinas / ventanas', '; '.join(f"{g['id']} {g.get('note', '')}" for g in F.ex.get('glazing', []))),
        ('Ductos', '; '.join(f"{s['id']}: {s.get('note', '')}" for s in F.ex.get('shafts', []))),
        ('Escalera del edificio', (F.ex.get('stair') or {}).get('note', '')),
        ('Campana existente', hood.get('note', '')),
        ('Puntos húmedos', '; '.join(f"{w['id']} {w.get('desc', '')}" for w in F.ex.get('wet_points_existing', []))),
        ('Altura libre', f"{n(F.ceiling)} m supuesta — {(F.ex.get('ceiling') or {}).get('note', '')}"),
        ('Terraza en pasillo común', (F.ex.get('terrace_existing') or {}).get('note', '') + ' (no forma parte de esta propuesta)'),
    ]
    L.append(table(['Elemento', 'Condición (según el PDF de Marna\'s)'], rows))
    L.append('\nCoordenadas del proyecto: X desde el eje A hacia la fachada (este), Y desde el eje 1 hacia el ala de servicio (sur); '
             '"norte" es la parte superior del PDF original, no el norte geográfico.\n')

    L.append('\n## 4. Programa y zonificación\n\n')
    rows = []
    occ = {r['zone']: r for r in F.occ_rows}
    for z in F.zones:
        zid = z['id']
        items = [e for e in F.eqz(zid)]
        txt = ', '.join(f"{e['id']} {e.get('label') or e.get('plan_label')}" for e in items)
        if zid == 'D':
            txt = (f'{len(F.tables)} mesas ({F.n2} de 2, {F.n4} de 4), {F.chairs} sillas, bancas '
                   + ' y '.join(f"{b['id']} ({b['seats']})" for b in F.banq) + (', ' + txt if txt else ''))
        rows.append((f'{zid} · {z.get("short") or z.get("name")}', z.get('name'), n(F.zarea.get(zid)),
                     f"{100 * (F.zarea.get(zid) or 0) / F.area:.0f} %", occ.get(zid, {}).get('occupants', '—'), txt))
    prod = sum(F.zarea.get(k, 0) for k in ('B', 'E', 'W', 'A'))
    pub = sum(F.zarea.get(k, 0) for k in ('C', 'D'))
    rows.append(('Total zonas', 'Producción B+E+W+A · público C+D', n(prod + pub), '', F.occ_zone or '—',
                 f'producción {n(prod)} m² · salón + barra {n(pub)} m²'))
    L.append(table(['Zona', 'Uso', 'm²', '% local', 'Ocup.', 'Equipos y mobiliario'], rows, 'llrrrl'))
    L.append('\nOcup. = carga de ocupantes de cálculo por zona (NFPA 101, ver 03). La diferencia entre la suma de zonas y el área del '
             'local corresponde a muros interiores y remates.\n\n')
    L.append('Secuencia fijada por el cliente, desde el salón hacia el fondo: muro al salón → **HOT LINE / SHOW KITCHEN** (parrilla → '
             'cocina 4Q → plancha → freidora 1 → freidora 2) → mesa de apoyo + horno (muro norte) → **BBQ PRODUCTION** (smoker + '
             'holding, muro del fondo) → **WASHING** (antiguas PILAS) → **COLD PREP** (antigua PASTELERÍA). **BAR / POS** con pase '
             'caliente junto a la división; **DINING** con vista a la parrilla desde '
             f"{n(F.m.get('seats_with_parrilla_view_pct'), 0)} % de los asientos.\n")

    L.append('\n## 5. Capacidad y clasificación\n\n')
    L.append(f'- **{F.declared} personas** (clientes + personal). ' + re.sub(r'^Capacidad máxima declarada y rotulada: \d+ personas \(clientes \+ personal\)\.\s*', '', F.ls.get('capacity_note', '')) + '\n')
    if F.occ_zone is not None:
        L.append(f'- Carga de ocupantes de cálculo (áreas ÷ factores NFPA 101): **{F.occ_zone}** redondeando por zona; {F.occ_use} por uso; '
                 f'{n(F.occ_raw)} sin redondear. Umbral de reunión pública: {F.threshold}.\n')
    L.append('- Barra solo de servicio (sin taburetes ni clientes de pie). ' + F.ls.get('waiting_area', '') + '\n')
    L.append('- Con 50 personas o más cambia la clasificación (reunión pública) y la salida única deja de ser aceptable: ver 03 §15.\n')

    L.append('\n## 6. Intervención: qué cambia respecto de Marna\'s\n\n')
    L.append(f'La división cocina/salón pasa de X = {n(F.exwall.get("IP-KB", {}).get("rect", [0])[0])} (Marna\'s) a X = {n(F.part_x)} '
             f'(cara cocina): **{n(F.shift)} m** hacia el fondo. El salón gana ≈{n((F.shift or 0) * 4.87, 1)} m² '
             '(franja × 4.87 m de fondo).\n\n')
    L.append('### 6.1 Se conserva\n\n' + bullets(F.lay.get('structure_notes', [])[:4] + [
        'Puntos húmedos existentes reutilizados: ' + ', '.join(f"{w['id']} → {w['use']}" for w in (F.mech or {}).get('wet_points_existing', []))
        if F.mech else None]))
    rows = []
    for d in F.lay.get('demolish', []):
        w = F.exwall.get(d['id'], {})
        r = d.get('rect') or w.get('rect')
        tag = 'condicional' if d.get('conditional') else ('parcial' if 'rect' in d else 'total')
        rows.append((d['id'], tag, n(rect_len(r)) if r else '—', d.get('note', '')))
    for it in F.lay.get('remove_items', []):
        rows.append((it['id'], 'retiro', n(rect_len(it['rect'])), it.get('label', '')))
    L.append('\n### 6.2 Se demuele o retira\n\n' + table(['Elemento', 'Tipo', 'Largo (m)', 'Descripción'], rows, 'llrl'))
    rows = []
    for w in F.lay.get('new_walls', []):
        rows.append((w['id'], w.get('short') or w.get('type'), n(rect_len(w['rect'])), n(w.get('h')), w.get('note', '')))
    for o in F.lay.get('new_openings', []):
        rows.append((o.get('label') or o['id'], OPEN_ES.get(o['type'], o['type']) + (' (condicional)' if o.get('conditional') else ''),
                     n(o.get('width')), '—', o.get('note', '')))
    L.append('\n### 6.3 Se construye\n\n' + table(['Elemento', 'Tipo', 'Largo / vano (m)', 'h (m)', 'Descripción'], rows, 'llrrl'))
    L.append('\n### 6.4 Uso de los espacios\n\n')
    L.append(table(['Espacio de Marna\'s', 'Uso en LAVA'], [
        (f'Cocina (X {n(x0)}…{n(F.exwall.get("IP-KB", {}).get("rect", [0])[0])})',
         f'Hot line + BBQ production hasta X {n(F.part_x)}; la franja restante pasa a barra/salón'),
        ('Barra / salón', 'Barra de bebidas, caja accesible, pase y salón de ' + str(F.seats) + ' asientos'),
        ('PILAS', F.zfull.get('W', 'Lavado')),
        ('PASTELERÍA', F.zfull.get('A', 'Cold prep')),
        ('Campana 3.80 × 1.10', 'Se retira; dos campanas nuevas independientes (HD-1 gas, HD-2 parrilla)'),
        ('Uso: cafetería', 'Restaurante con cocción a gas y con combustible sólido, venta de licor — confirmar si Bomberos lo trata como cambio de uso (05 EG-23)'),
    ]))

    L.append('\n## 7. Flujos operativos\n\n' + bullets(join_notes(F.lay.get('flow_notes', []))))
    if F.routes:
        L.append('\nAnchos libres mínimos medidos (sillas ocupadas, entre equipos y muros):\n\n')
        L.append(table(['Recorrido', 'Tipo', 'Ancho mín. (m)', 'Objetivo (m)', 'Largo (m)'],
                       [(r.get('label'), r.get('kind'), n(r['min_width']), n(r.get('required')), n(r.get('length'), 1)) for r in F.routes], 'llrrr'))

    L.append('\n## 8. Sistemas e instalaciones (resumen)\n\n')
    rows = []
    e1, e2 = F.exh('EXT-1'), F.exh('EXT-2')
    if e1 and e2:
        rows.append(('Extracción', f"EXT-1 → HD-1 (línea a gas) ≈{n(e1['Q_Ls'], 0)} L/s; EXT-2 → HD-2 (parrilla, combustible sólido, "
                                   f"sistema independiente) ≈{n(e2['Q_Ls'], 0)} L/s; EXT-3 chimenea propia del smoker. {FLAG_EXT}", 'M-102 · 04'))
    mua = (F.mech or {}).get('makeup_air')
    if mua:
        rows.append(('Aire de reposición', f"AR-1 ≈{n(mua['design_Q_Ls'], 0)} L/s ({mua['design_pct']} % de la extracción), 2 difusores — TO BE ENGINEERED", 'M-102 · 04'))
    rows.append(('Supresión', 'HD-1: químico húmedo UL 300 / NFPA 17A con corte de gas y energía; HD-2: sistema listado para combustible sólido; '
                              f"pulsadores {', '.join(F.ls.get('pull_station', {}).get('ids', []))} junto a P-1", 'A-104 · 02 §9'))
    g = (F.mech or {}).get('gas', {})
    rows.append(('Gas', f"{F.gas.get('source', '')}; consumidores {', '.join(F.gas.get('consumers', []))}"
                        + (f"; ≈{n(g.get('total_kW_typ'), 1)} kW típicos" if g else '') + '; sin cilindros en el local', 'M-102 · 04'))
    hw = (F.mech or {}).get('hot_water', {})
    if hw:
        ca1 = hw.get('CA-1', {})
        rows.append(('Agua caliente', f"CA-1 termotanque {ca1.get('volume_L')} L / {n(ca1.get('kW'), 1)} kW (hora pico ≈{hw.get('peak_hour_demand_L_60C')} L a 60 °C); "
                                      f"CA-2 {hw.get('CA-2', {}).get('volume_L')} L bajo barra", 'M-101 · 04'))
    gt = (F.mech or {}).get('grease_trap', {})
    rows.append(('Desagües', 'Reutiliza puntos húmedos existentes; trampa de grasa GT-1 bajo el fregadero'
                             + (f" ({gt.get('recommendation', '')})" if gt else '') + '; coladeras de piso FD-1…3', 'M-101 · 04'))
    dm = (F.elec or {}).get('demand', {})
    if dm:
        sg = dm.get('suggested', {})
        rows.append(('Electricidad', f"{(F.elec or {}).get('system_assumed', '')}; demanda ≈{n(dm['total_demand_VA'] / 1000, 1)} kVA, diseño "
                                     f"{n(dm['design_VA'] / 1000, 1)} kVA → principal {sg.get('main_A')} A; tablero {F.mep.get('panel', {}).get('id', 'TE-1')}", 'E-101 · 04'))
    rows.append(('Seguridad humana', f"Salida única SAL-1 (D-ENT {n(F.dent.get('width'))} m); {len(F.ls.get('exit_signs', []))} rótulos de salida; "
                                     f"{len(F.ls.get('emergency_lights', []))} luces de emergencia; {len(F.ls.get('extinguishers', []))} extintores; "
                                     f"{len(F.ls.get('smoke_detectors', []))} detectores", 'A-104 · 03'))
    rows.append(('Climatización', 'Ventilación / A/C del salón y cocina TO BE ENGINEERED (el local solo tiene fachada al este); reserva en el cuadro de cargas', 'E-101'))
    rows.append(('Iluminación', 'Plano de cielos y luminarias por tipo (L-1…L-9), emergencia y rótulos', 'A-201'))
    L.append(table(['Sistema', 'Propuesta (anteproyecto)', 'Ver'], rows))

    L.append('\n## 9. Servicios sanitarios, personal y residuos\n\n')
    lk = (F.bykey.get('lockers') or [{}])[0]
    L.append(bullets([
        F.ls.get('restrooms', ''),
        f"Recorrido interno desde el punto más remoto ({F.longest['from']}) hasta D-ENT: "
        + ' · '.join(f'{src} {n(v)} m' for v, src in F.far_cand)
        + f". Con el límite de 36 m al servicio sanitario (INVU, artículo por confirmar) y el valor mayor, el baño común tendría que "
        f"estar a ≤{n(F.restroom_budget, 1)} m de D-ENT por el pasillo — {FLAG_SITE}." if F.far_int else None,
        f"Personal: {lk.get('id', 'L1')} {lk.get('label', '')} — {lk.get('note', '')}" if lk else None,
        f"Lavamanos exclusivos: {', '.join(e['id'] + ' ' + (e.get('plan_label') or e.get('label')) for e in F.handwash)}.",
        'Residuos: ' + ' '.join(e.get('note', '') for e in F.bykey.get('waste_bins', [])),
        'Cenizas y leña: ' + F.ls.get('fuel_storage_note', ''),
    ]))
    L.append('\n## 10. Accesibilidad (Ley 7600)\n\n')
    c4 = (F.bykey.get('caja') or [{}])[0]
    L.append(bullets([
        f"Acceso a nivel por D-ENT ({n(F.dent.get('width'))} m, dos hojas de {n(F.ls.get('exits', [{}])[0].get('leaf'))}); umbral ≤0.02 m — {FLAG_SITE}.",
        f"Caja accesible {c4.get('id', 'C4')} a h {n(c4.get('h'))} m ({c4.get('note', '')})" if c4 else None,
        f"Mesas accesibles: {', '.join(F.acc_tables)}." if F.acc_tables else None,
        f"Pasillo principal del salón: {n(F.main_aisle)} m libres (≥1.20 m, DE 26831-MP art. 141, verificar)." if F.main_aisle else None,
        f"Puerta de cocina P-1: vano {n(F.op.get('P-1', {}).get('width'))} m, paso libre ≥0.90 m (art. 140) a confirmar con la hoja.",
        'Servicio sanitario accesible: el del centro comercial (DE 26831-MP art. 143) — ' + FLAG_SITE + '. Detalle en ' + sheet_ref(F, 'A105') + '.',
    ]))
    L.append('\n## 11. Venta de bebidas alcohólicas\n\n')
    L.append(bullets([
        'Licencia municipal clase C (restaurante), Ley 9047: cocina equipada, menú de al menos 10 opciones durante todo el horario, '
        'salón con mesas y servicio a la mesa (fuente secundaria, verificar con la Municipalidad de Santa Ana).',
        f'El anteproyecto tiene {len(F.tables)} mesas y {F.seats} asientos, sin banquetas de barra (mínimos reportados de 8 mesas y 32 '
        'asientos en algunos reglamentos: por confirmar si Santa Ana los aplica).',
        'Barra C1 solo de servicio; enfriador de bebidas bajo barra y pileta de barra PB-1.',
        'Restricciones por distancia a centros educativos y de salud y por zonificación: verificar con la Municipalidad (06 paso 12).',
    ]))
    L.append('\n## 12. Supuestos y riesgos principales\n\n')
    L.append(bullets(F.content.get('risks', [])))
    L.append('\n## 13. Láminas de referencia\n\n' + bullets(f"{sheet_tag(s['id'])} · {s['title']}" for s in F.sheets))
    L.append('\n' + flags_block())
    return ''.join(L)


# ------------------------------------------------------------------------------------------------ 02 especificaciones


def doc_02(F):
    L = [header(F, '02', 'Especificaciones técnicas',
                'Especificación por desempeño para el anteproyecto. Los proveedores entregan fichas técnicas, listados (UL/ETL/NSF), '
                'planos de taller y memorias para aprobación del profesional responsable **antes** de fabricar o instalar. '
                f'Todo lo marcado * o "{FLAG_DIM}" / "{FLAG_SITE}" se confirma antes de comprar.')]
    L.append('## 1. Generalidades\n\n' + bullets([
        'Normativa de referencia (ediciones vigentes a confirmar por el profesional): Reglamento de Construcciones INVU 2018 y reformas; '
        'Reglamento Nacional de Protección contra Incendios (RNPCI 2023) con el paquete NFPA (101, 96, 10, 17A, 72, 54/58, 211); '
        'Código Eléctrico de Costa Rica (NEC 2020); CIHSE 2017 (CFIA); DE 37308-S (servicios de alimentación); Ley 7600 y DE 26831-MP; '
        'Código Sísmico de Costa Rica; reglamento interno del condominio.',
        'Coordinación con la administración: horario de obras, protección de áreas comunes, acarreos, cortes de servicios (ver 08).',
        'Materiales en cocina, lavado y cold prep: lisos, impermeables, lavables e incombustibles donde se indique.',
        'Cualquier sustitución de equipo exige volver a verificar holguras, campanas, cargas y recorridos (los datos del anteproyecto se '
        'regeneran desde `data/layout.json`).',
    ]))
    # 2 demolitions
    rows = []
    for d in F.lay.get('demolish', []):
        w = F.exwall.get(d['id'], {})
        r = d.get('rect') or w.get('rect')
        tag = 'condicional (solo si se aprueba PS-1)' if d.get('conditional') else ('parcial' if 'rect' in d else 'total')
        rows.append((d['id'], tag, n(rect_len(r)) if r else '—', d.get('note', '')))
    for it in F.lay.get('remove_items', []):
        rows.append((it['id'], 'retiro de equipo', n(rect_len(it['rect'])), it.get('label', '') +
                     '. Sellar collarines y ductos no reutilizados con lámina de acero soldada y cierre incombustible.'))
    dd = F.exdoor.get('D-DISH-old', {})
    if dd:
        rows.append(('D-DISH-old', 'retiro de antepecho si existe', n(dd.get('width')),
                     dd.get('note', '') + f' — dejar el paso libre hacia lavado ({FLAG_SITE}).'))
    L.append('\n## 2. Demoliciones y retiros\n\n' + table(['Elemento', 'Alcance', 'Largo (m)', 'Descripción'], rows, 'llrl'))
    L.append('\n' + bullets([
        'Sondeo previo de cada muro a demoler: confirmar que es liviano y que no aloja instalaciones (' + FLAG_SITE + ').',
        'No se tocan columnas, perímetro, escalera ni ductos del edificio.',
        'Retiro de escombros por la ruta y en el horario autorizados por la administración; protección de pisos y del pasillo común.',
    ]))
    # 3 partitions
    L.append('\n## 3. Particiones nuevas\n\n')
    for w in F.lay.get('new_walls', []):
        L.append(f"**{w['id']} · {w.get('short') or w.get('type')}** — largo {n(rect_len(w['rect']))} m, h {n(w.get('h'))} m"
                 + (f", base maciza h {n(w.get('base_h'))} m" if w.get('base_h') else '') + f". {w.get('note', '')}\n\n")
    h1 = F.parrilla
    L.append(bullets([
        'Base de NW-1: bloque de concreto relleno o concreto, incombustible, anclada a la losa (anclaje por ingeniero estructural).',
        f"Tramo detrás de la parrilla {h1['id']} (Y {n(h1['rect'][1])}…{n(h1['rect'][3])}) desde h 1.00 hasta la campana HD-2: vidrio "
        'vitrocerámico (≥680 °C) o pantalla inox con cámara ventilada de 25 mm; resto: vidrio templado o laminado de seguridad '
        '(zona de tránsito junto a P-1). Especificación térmica / cortafuego TO BE ENGINEERED.' if h1 else None,
        'Perfilería metálica; sellos incombustibles en encuentros con losa, muros y campana.',
        sent(f"Nicho decorativo: {F.niche.get('note', '')}", f"Material: {F.niche.get('material', '')}.") if F.niche else None,
        'NW-2: acero inoxidable sobre placa cementicia con cámara de aire, de piso a campana; cierra lateralmente HD-2 y protege la ruta hacia P-1.',
    ]))
    # 4 finishes
    L.append('\n## 4. Acabados\n\n')
    try:
        from sheets.s106_acabados import ZONE_FIN, _specs
        specs = _specs(F.ex)
        rows = [(z['id'] + ' · ' + (z.get('short') or ''), ZONE_FIN.get(z['id'], {}).get('PI', '—'), ZONE_FIN.get(z['id'], {}).get('ZO', '—'),
                 ZONE_FIN.get(z['id'], {}).get('CI', '—')) for z in F.zones]
        L.append('Asignación por zona (lámina ' + sheet_ref(F, 'A106') + '; los muros MU-xx se asignan por cara de muro en la lámina):\n\n')
        L.append(table(['Zona', 'Piso', 'Zócalo', 'Cielo'], rows))
        L.append('\n' + table(['Código', 'Tipo', 'Especificación'], specs))
    except Exception as err:  # noqa: BLE001
        L.append(f'(Especificación de acabados no disponible: {err}. Ver lámina A-106.)\n')
    L.append('\n' + bullets([
        'Acabados interiores del salón (listones de madera MU-03, tapicería de bancas): clase A o B según NFPA 101 cap. 10 / RNPCI '
        '(ASTM E84 / UL 723: propagación de llama ≤75, humo ≤450) o tratamiento ignífugo certificado — ficha obligatoria.',
        'Cocina, lavado y cold prep: sin madera ni materiales porosos; uniones piso–muro sanitarias; colores claros.',
    ]))
    # 5 ceilings
    L.append('\n## 5. Cielos\n\n')
    try:
        from sheets.s201_cielos import ct_defs
        L.append(table(['Tipo', 'Zonas', 'Descripción', 'Nivel'], [(c['id'], ', '.join(c['zones']), f"{c['name']}. {c['finish']}", c['level'])
                                                                    for c in ct_defs(F.ceiling)]))
    except Exception as err:  # noqa: BLE001
        L.append(f'(Tipos de cielo no disponibles: {err}. Ver lámina A-201.)\n')
    L.append(f'\nAltura mínima de piso a cielo 2.40 m (INVU, artículo por confirmar). Altura existente {FLAG_SITE}.\n')
    # 6 doors
    L.append('\n## 6. Puertas, ventanas y herrajes\n\n')
    ex1 = next((e for e in F.ls.get('exits', []) if e['id'] == 'SAL-1'), {})
    rows = [('D-ENT (existente)', f"doble {n(F.dent.get('width'))} m, hojas {n(ex1.get('leaf'))}",
             sent(ex1.get('note', ''), 'Herraje de palanca o barra, sin llave desde adentro durante la operación; umbral ≤0.02 m; rótulo SALIDA '
                  'iluminado encima y rótulo CAPACIDAD MÁXIMA ' + str(F.declared) + '.'))]
    for o in F.lay.get('new_openings', []):
        extra = {
            'P-1': 'Visor de vidrio de seguridad, placa de patada inox, bisagras de doble acción; marco metálico delgado para conservar el paso libre.',
            'P-2': 'Cierrapuertas; sin cerradura con llave; placa de patada inox.',
            'PS-1': 'Si se aprueba: giro hacia afuera, barra antipánico, cierre automático; resistencia al fuego si el pasillo sur es parte '
                    'de la salida de la escalera; dintel estructural; burlete y cedazo.',
        }.get(o.get('label') or o['id'], '')
        rows.append((o.get('label') or o['id'], f"{OPEN_ES.get(o['type'], o['type'])}, vano {n(o.get('width'))} m" + (' (CONDICIONAL)' if o.get('conditional') else ''),
                     sent(o.get('note', ''), extra)))
    for g in F.ex.get('glazing', []):
        rows.append((g['id'] + ' (existente)', KIND_ES.get(g.get('kind', ''), g.get('kind', '')),
                     sent(g.get('note', ''), 'Se sustituye en parte por PS-1 si se aprueba.' if g['id'] == 'GL-W1' else '')))
    L.append(table(['Elemento', 'Tipo', 'Especificación'], rows))
    # 7 equipment
    L.append('\n## 7. Equipos de cocina y mobiliario técnico\n\n')
    L.append(f'Dimensiones frente × fondo × alto (m). * = {FLAG_DIM}. Energía y potencias típicas (*) de `mech_calcs.json` / `elec_loads.json`: '
             'reemplazar por las fichas técnicas.\n\n')
    rows = []
    for e in F.lay.get('equipment', []):
        rows.append((e['id'], e.get('label'), dims_str(e), energy_of(F, e), PERF.get(e.get('key'), cut(e.get('note', ''), 200))))
    L.append(table(['Tag', 'Equipo', 'Medidas', 'Energía', 'Requisito de desempeño'], rows))
    # 8 hoods & ducts
    L.append('\n## 8. Campanas, ductos y extracción (NFPA 96)\n\n')
    L.append(f'**{FLAG_EXT}.** Valores de caudal y ducto: ver 04 (PRELIMINAR).\n\n')
    rows = []
    for h in F.hoods:
        x0, y0, x1, y1 = h['rect']
        sysid = next((s['id'] for s in F.mep.get('exhaust', []) if s.get('serves') == h['id']), '—')
        s = F.exh(sysid) or {}
        rows.append((h['id'], h.get('label'), f"{n(abs(y1 - y0))} × {n(abs(x1 - x0))}", ', '.join(F.hood_serves.get(h['id'], [])),
                     sysid, f"{n(s.get('Q_Ls'), 0)} L/s · ducto {'×'.join(map(str, (s.get('duct') or {}).get('rect_mm', [])))} mm" if s else '—',
                     h.get('note', '')))
    L.append(table(['Campana', 'Descripción', 'Largo × fondo (m)', 'Equipos bajo campana', 'Sistema', 'Caudal / ducto', 'Nota'], rows))
    L.append('\n' + bullets([
        'Dos sistemas **independientes**: HD-1 (gas) y HD-2 (parrilla de combustible sólido): campana, ducto, ventilador y descarga '
        'propios; no se unen en ningún punto (NFPA 96 cap. 14, verificar numeración de la edición adoptada).',
        f'Borde inferior de campanas ≈{n(F.hood_lower)} m (altura del panel NW-2) — TBV con la altura libre real; HD-2: filtros ≥1.22 m sobre '
        'la superficie de cocción (NFPA 96 cap. 14, TBV) y arrestachispas antes de los filtros.' if F.hood_lower else None,
        'Ducto de grasa: acero al carbono ≥1.37 mm (16 MSG) o inox ≥1.09 mm (18 MSG), soldadura continua estanca, sin sifones, registros de '
        'limpieza en cada cambio de dirección; cerramiento resistente al fuego 1 h (<4 pisos) o envolvente listada; holguras 457 / 76 / 0 mm '
        'a combustibles / combustibilidad limitada / incombustibles.',
        'Velocidad en ducto ≥2.54 m/s (NFPA 96 §8.2, verificar); ventiladores de descarga vertical en cubierta con bisagra de limpieza y drenaje de grasa.',
        'Descarga en cubierta: ≥3 m horizontales a tomas de aire, linderos y edificios vecinos; ≥1.5 m a estructuras combustibles (NFPA 96 §7.8, '
        'cifras por confirmar); remate de la chimenea del smoker según INVU (≥5 m sobre edificios en 25 m, por verificar) — aprobación del condominio.',
        'EXT-1: ' + next((s.get('riser', '') for s in F.mep.get('exhaust', []) if s['id'] == 'EXT-1'), ''),
        'EXT-2: ' + next((s.get('riser', '') for s in F.mep.get('exhaust', []) if s['id'] == 'EXT-2'), ''),
        'EXT-3 (smoker): ' + next((s.get('riser', '') for s in F.mep.get('exhaust', []) if s['id'] == 'EXT-3'), '') + f' {FLAG_SMOKER}.',
        'Horno K2 fuera de campanas: solo con recirculación integrada listada UL 710B.',
        'Limpieza: extracción de combustible sólido mensual; demás según uso (NFPA 96, tabla de frecuencias; verificar).',
    ]))
    # 9 suppression and extinguishers
    L.append('\n## 9. Supresión de incendios y extintores\n\n')
    ps = F.ls.get('pull_station', {})
    L.append(bullets([
        'HD-1: sistema fijo de químico húmedo listado **UL 300** (NFPA 17A) que cubre equipos, pleno y ducto; al disparar cierra la válvula de '
        'gas VS (rearme manual) y abre el contactor KS-1 de los equipos eléctricos protegidos.',
        'HD-2: sistema listado para combustible sólido (agente y boquillas según el listado); arrestachispas; manguera fija si el hogar de la '
        'parrilla supera 0.14 m³ (NFPA 96 cap. 14, verificar).',
        sent(f"Pulsadores manuales {', '.join(ps.get('ids', []))}: {ps.get('note', '')}", f"Altura {ps.get('h', '')}.", _pm_dist(F)),
        'Diseño, instalación, prueba de aceptación y certificado por proveedor autorizado; mantenimiento semestral (NFPA 17A); señal a la alarma '
        f'del centro comercial si existe ({FLAG_SITE}).',
    ]))
    L.append('\n' + table(['Extintor', 'Tipo', 'Ubicación (zona)', 'Nota'],
                          [(x['id'], x['type'], F.zlabel(x['at']), x.get('note', '')) for x in F.ls.get('extinguishers', [])]))
    L.append('\nMontaje: parte superior a ≤1.53 m y parte inferior ≥0.10 m sobre el piso; rótulo junto al clase K: "accionar primero el sistema fijo" (NFPA 10, verificar).\n')
    # 10 gas
    L.append('\n## 10. Gas (red del centro comercial)\n\n')
    g = (F.mech or {}).get('gas', {})
    L.append(bullets([
        f"Fuente: {F.gas.get('source', '')}. Sin cilindros en el local.",
        f"Acometida: {F.gas.get('entry_note', '')}",
        F.gas.get('note', ''),
        f"Consumo típico total ≈{n(g.get('total_kW_typ'), 1)} kW ({nint(g.get('total_BTUh_typ'))} BTU/h); tubería principal: {g.get('recommended_main', '')}" if g else None,
        'Tubería rígida de hierro negro cédula 40 roscada/soldada, soportada y protegida, pintada amarillo; no atravesar sectores internos '
        'del edificio sin aprobación de Bomberos (Disposiciones GLP 2023 si la red es de GLP, verificar); prueba de hermeticidad antes de conectar.',
        'Detector de gas DG-1 según tipo de gas (GLP a ≤0.30 m del piso; GN cerca del cielo), con alarma y corte de VS.' if F.devices.get('DG-1') else None,
        'Informe técnico de la instalación de gas por profesional o inspector acreditado para el Permiso Sanitario de Funcionamiento (06 paso 9).',
    ]))
    # 11 plumbing
    L.append('\n## 11. Hidrosanitario y trampa de grasa (CIHSE 2017)\n\n')
    if F.mech:
        L.append(table(['Tag', 'Aparato', 'AF', 'AC', 'Desagüe', 'A'],
                       [(p['tag'], p['name'], p['af'], p['ac'], p['drain'], p['to']) for p in F.mech.get('plumbing_fixtures', [])]))
    L.append('\n' + bullets([
        'Tuberías de agua: PVC SDR/CPVC o PEX para agua caliente según diseño; válvulas de corte por zona; rompevacíos en llaves de manguera.',
        'Desagües: PVC sanitario con pendientes según CIHSE; ventilación de cada sifón; registros accesibles; la grasa pasa por GT-1 antes de WP1.',
        'Coladeras de piso con canastilla y sello hidráulico en cocina, lavado y cold prep (pendiente 1–2 % a coladeras, verificar).',
        (F.mech or {}).get('hot_water', {}).get('note', '') if F.mech else None,
        'Tipo de losa (sobre terreno o entrepiso) y destino de los desagües existentes: ' + FLAG_SITE + '.',
    ]))
    # 12 MUA & HVAC
    L.append('\n## 12. Aire de reposición, ventilación y climatización\n\n' + bullets([
        (F.mep.get('makeup_air') or {}).get('note', ''),
        f"Caudal de diseño AR-1 ≈{n(mua['design_Q_Ls'], 0)} L/s; ducto {'×'.join(map(str, mua['duct']['rect_mm']))} mm. "
        f"Difusores: {mua['diffusers']['note']}" if (mua := (F.mech or {}).get('makeup_air')) else None,
        'Enclavamiento: AR-1 arranca con EXT-1 o EXT-2; con brasas en H1/S1 la extracción de sólido no se apaga (selector con llave).',
        *F.mep.get('engineering_notes', []),
    ]))
    # 13 electrical
    L.append('\n## 13. Electricidad e iluminación (NEC 2020)\n\n')
    if F.elec:
        dm = F.elec.get('demand', {})
        sg = dm.get('suggested', {})
        ws = F.elec.get('panel', {}).get('working_space', {})
        L.append(bullets([
            f"Sistema supuesto: {F.elec.get('system_assumed', '')} — {FLAG_SITE} con la administración / distribuidora.",
            f"Tablero {F.elec.get('panel', {}).get('id', 'TE-1')}: principal {sg.get('main_A')} A, barra ≥{sg.get('bus_A')} A, "
            f"{sg.get('spaces')} espacios ({sg.get('spaces_used')} usados); espacio de trabajo {n(ws.get('depth_m'))} × {n(ws.get('width_m'))} × "
            f"{n(ws.get('height_m'))} m libre ({ws.get('basis', '')}).",
            'GFCI en cocina, lavado, cold prep y barra (NEC 210.8(B)); conductores de cobre THHN/THWN; canalización metálica en cocina.',
            'Circuitos exclusivos para ventiladores, supresión/control (CC-1), rótulo exterior, POS/TI; luminarias de emergencia autónomas en el '
            'circuito de alumbrado de su área.',
            'Enclavamientos (matriz en 04 y E-101): supresión → VS cierra y KS-1 abre; detector de gas → VS cierra; falta de energía → VS cierra (N.C.).',
        ]))
    try:
        from sheets.s201_cielos import LUM_TYPES
        cnt = {}
        for lt in (F.elec or {}).get('lighting', {}).get('luminaires', []):
            cnt[lt['type']] = cnt.get(lt['type'], 0) + 1
        rows = [(k, v['name'].replace(' / jardinera', ''), v['spec'], v['mount'].replace(' · borde inf. h {h}', '').replace(' · h {h}', '').replace(' · eje h {h}', ''), cnt.get(k, ''))
                for k, v in LUM_TYPES.items() if k not in ('EM', 'RS')]
        rows.append(('EM', LUM_TYPES['EM']['name'], LUM_TYPES['EM']['spec'], LUM_TYPES['EM']['mount'], len(F.ls.get('emergency_lights', []))))
        rows.append(('RS', LUM_TYPES['RS']['name'], LUM_TYPES['RS']['spec'], LUM_TYPES['RS']['mount'], len(F.ls.get('exit_signs', []))))
        L.append('\n' + table(['Tipo', 'Luminaria', 'Especificación', 'Montaje', 'Cant.'], rows, 'llllr'))
        L.append('\nCantidades de A-201 (luminarias lineales/tiras contadas por tramo). Niveles lumínicos y marcas: referencia, a validar.\n')
    except Exception as err:  # noqa: BLE001
        L.append(f'(Tipos de luminaria no disponibles: {err}. Ver A-201.)\n')
    # 14 detection
    det = [F.zone_at(p) for p in F.ls.get('smoke_detectors', [])]
    n_heat = sum(1 for z in det if z in ('B', 'E'))
    L.append('\n## 14. Detección, alarma y enclavamientos\n\n' + bullets([
        f"{len(det)} detectores ({n_heat} térmico(s) en cocina caliente / BBQ, {len(det) - n_heat} de humo). {F.ls.get('detector_note', '')}",
        'Monitor de CO DCO-1 en BBQ production (dos aparatos de combustible sólido).' if F.devices.get('DCO-1') else None,
        F.ls.get('sprinklers', ''),
        'Integración con la alarma del centro comercial (NFPA 72) y señal de disparo de supresión: ' + FLAG_SITE + '.',
    ]))
    # 15 signage
    L.append('\n## 15. Señalización\n\n')
    rows = [(s['id'], s.get('text', ''), F.zlabel(s['at']), s.get('note', '')) for s in F.ls.get('exit_signs', [])]
    L.append(table(['Rótulo', 'Texto', 'Zona', 'Ubicación'], rows))
    L.append('\n' + bullets([
        f'Rótulo "CAPACIDAD MÁXIMA {F.declared} PERSONAS" junto a D-ENT.',
        'Rótulos de extintores, del clase K ("accionar primero el sistema fijo"), de pulsadores de supresión y de la llave de gas exterior.',
        'Rótulos "PROHIBIDO FUMAR" en D-ENT y en el salón; "SOLO PERSONAL AUTORIZADO" en P-1; símbolo internacional de accesibilidad en caja y mesas accesibles.',
        'Rótulo exterior y rótulo LAVA retroiluminado: permiso municipal y aprobación del condominio (06 paso 13).',
        'Rótulos de salida iluminados, autonomía ≥1.5 h (NFPA 101 7.10, verificar).',
    ]))
    # 16 accessibility
    L.append('\n## 16. Accesibilidad (Ley 7600 · DE 26831-MP)\n\n' + bullets([
        'Ruta accesible continua D-ENT → caja accesible → mesas accesibles, sin desniveles; umbrales ≤0.02 m (art. 142, verificar).',
        'Puertas con paso libre ≥0.90 m y 0.45 m libres del lado opuesto a las bisagras (art. 140, verificar); herrajes de palanca.',
        f"Pasillos: salón ≥1.20 m (medido {n(F.main_aisle)} m); interiores ≥0.90 m (art. 141, verificar)." if F.main_aisle else None,
        'Mostrador de caja h 0.80 m con espacio libre inferior para rodillas (art. 148, verificar); mesas accesibles con aproximación '
        'frontal 0.80 × 1.20 m (criterio de referencia, sin artículo costarricense confirmado).',
        'Detalles y áreas de giro Ø1.50 en ' + sheet_ref(F, 'A105') + '.',
    ]))
    # 17 seismic
    L.append('\n## 17. Anclaje sísmico, soportes y cubierta\n\n' + bullets([
        'Anclaje sísmico (Código Sísmico de CR) de campanas, ductos, tubería de gas, termotanque y equipos altos (refrigerador, congelador, smoker, estanterías).',
        'Colgado de campanas y ductos desde la losa; bases y soportes de ventiladores en cubierta: diseño por ingeniero estructural.',
        'Penetraciones de losa y cubierta (EXT-2, EXT-3, AR-1 y, si no se reutiliza el riser existente, EXT-1): revisión estructural, sellos '
        'cortafuego y aprobación del condominio.',
    ]))
    # 18 tests
    L.append('\n## 18. Pruebas, puesta en marcha y entrega\n\n' + bullets([
        'Prueba de hermeticidad de la tubería de gas y certificado; informe técnico de la instalación de gas.',
        'Prueba de aceptación de los sistemas de supresión (incluye corte de gas y energía) y certificado del proveedor.',
        'Balance de caudales de extracción y reposición; medición de presión cocina/salón.',
        'Pruebas eléctricas: aislamiento, continuidad de tierra, disparo de GFCI, autonomía de luces de emergencia.',
        'Prueba de estanqueidad de desagües; limpieza y desinfección final.',
        'Planos conforme a obra, manuales, garantías y programa de mantenimiento (limpieza de ductos, supresión, trampa de grasa).',
    ]))
    L.append('\n' + flags_block())
    return ''.join(L)


# ------------------------------------------------------------------------------------------------ 03 seguridad humana

PT_ES = {'entrance': 'entrada', 'barra_front': 'frente de barra', 'pass_dining': 'pase (lado salón)', 'dining_far': 'fondo del salón',
         'kitchen_door': 'puerta P-1', 'dish_drop': 'entrega de loza', 'cold_storage': 'refrigeración', 'prep': 'prep fría', 'line': 'línea caliente',
         'expo_pass': 'pase (lado cocina)', 'delivery_staging': 'recepción / delivery', 'smoker_front': 'frente del smoker',
         'service_door': 'PS-1', 'fuel': 'leña'}


def doc_03(F):
    L = [header(F, '03', 'Seguridad humana y egreso',
                'Memoria de seguridad humana y protección contra incendios, base para la lámina ' + sheet_ref(F, 'A104') +
                ' y la revisión de Bomberos (APC). Cifras de `data/life_safety_calcs.json` y `data/layout.json`.')]
    if not F.lsc:
        L.append('> `data/life_safety_calcs.json` no está disponible: ejecutar `tools/build_all.sh` (lámina A-104) y regenerar.\n\n')
    L.append('## 1. Normativa aplicada\n\n' + bullets([
        'Reglamento Nacional de Protección contra Incendios (RNPCI, versión 2023, Bomberos): adopta el paquete NFPA. El Manual de '
        'Disposiciones Técnicas 2013 está derogado (fuente secundaria, verificar).',
        'NFPA 101 (carga de ocupantes, egreso, señalización, iluminación de emergencia), NFPA 10 (extintores), NFPA 96 (cocinas comerciales, '
        'cap. 14 combustible sólido — cap. 15 en ediciones 2021/2024), NFPA 17A (químico húmedo), NFPA 72 (detección y alarma).',
        'Edición: la vigente adoptada por Bomberos a la fecha de presentación — **verificar edición**. La numeración citada corresponde a las '
        'ediciones 2018–2024.',
        F.limits.get('note') or (F.lsc or {}).get('method', {}).get('limits_source', ''),
    ]))
    # classification
    L.append('\n## 2. Clasificación y capacidad\n\n')
    L.append(table(['Concepto', 'Valor'], [
        ('Capacidad máxima declarada (clientes + personal)', f'{F.declared} personas'),
        ('Carga de cálculo (redondeo por zona)', F.occ_zone if F.occ_zone is not None else '—'),
        ('Carga de cálculo (redondeo por uso / sin redondear)', f'{F.occ_use} / {n(F.occ_raw)}' if F.occ_use is not None else '—'),
        ('Umbral de reunión pública (NFPA 101 6.1.2.1, verificar)', f'{F.threshold} personas'),
        ('Clasificación adoptada', (F.lsc or {}).get('occupant_load', {}).get('classification_by_calc', 'mercantil <50') +
         ' — restaurante con menos de 50 personas (NFPA 101 A.6.1.2.1, verificar); validar con Bomberos'),
        ('Rociadores', F.ls.get('sprinklers', '')),
    ]))
    L.append('\n' + re.sub(r'^Capacidad máxima declarada y rotulada: \d+ personas \(clientes \+ personal\)\.\s*', '', F.ls.get('capacity_note', '')) + '\n')
    # occupant load
    L.append('\n## 3. Carga de ocupantes por zona\n\n')
    if F.occ_rows:
        rows = [(f"{r['zone']} · {r['name']}", r['use'], n(r['area_m2']), n(r['factor_m2_per_person'], 1), r['basis'], n(r['raw']), r['occupants'])
                for r in F.occ_rows]
        rows.append(('Total', '', n(sum(r['area_m2'] for r in F.occ_rows)), '', '', n(F.occ_raw), F.occ_zone))
        L.append(table(['Zona', 'Uso', 'Área (m²)', 'm²/pers.', 'Base', 'Cálculo', 'Ocupantes'], rows, 'llrrlrr'))
        L.append(f"\nMétodo: {(F.lsc or {}).get('method', {}).get('occupant_load', '')} Resultado ≤ {F.declared} declaradas "
                 f"(margen {F.declared - (F.occ_zone or 0)} personas) — {VALIDAR}.\n")
    # exits
    L.append('\n## 4. Salidas\n\n')
    rows = []
    for e in F.exits_c:
        rows.append((e['id'], e.get('opening'), n(e.get('width_m')), n(e.get('leaf_m')), e.get('capacity_persons_5mm'),
                     n(e.get('required_width_mm'), 0), 'sí' if e.get('counted') else 'no (condicional)', e.get('note', '')))
    if rows:
        L.append(table(['Salida', 'Vano', 'Ancho (m)', 'Hoja (m)', 'Capac. (5 mm/p)', 'Req. (mm)', 'Se cuenta', 'Nota'], rows, 'llrrrrll'))
    L.append('\n' + bullets([
        f"Salida única SAL-1 (D-ENT) al pasillo abierto del centro comercial. {F.ls.get('egress_route_note', '')}",
        'Puertas: D-ENT gira hacia adentro (aceptable con <50 ocupantes, NFPA 101 7.2.1.4.2, verificar); se recomienda invertir el giro sin '
        'invadir el pasillo común (08). P-1 de vaivén siempre libre; P-2 con cierre automático y sin llave.',
        'Herrajes: apertura sin llave ni conocimiento especial desde el lado de egreso durante la ocupación (NFPA 101 7.2.1.5, verificar).',
        F.ls.get('waiting_area', ''),
        'Recorrido más allá de D-ENT (pasillo común abierto hasta la vía pública): ' + FLAG_SITE + '.',
    ]))
    # paths
    L.append('\n## 5. Recorridos de egreso medidos vs límites\n\n')
    if F.paths_u:
        rows = []
        for p in sorted(F.paths_u, key=lambda p: -p['length']):
            rows.append((p['id'], p['from'], p['exit'], n(p['length']), n(p.get('limit_common_path_m', p.get('limit'))),
                         n(p.get('limit_travel_m', F.lim_travel)), n(p.get('margin_m')),
                         'dentro del límite' if p.get('ok') else 'EXCEDE', n(p.get('length_with_ps1_conditional_m'))))
        L.append(table(['Ruta', 'Desde', 'Salida', 'Largo (m)', 'Camino común (m)', 'Recorrido (m)', 'Margen (m)', 'Estado', 'Con PS-1 (m)'],
                       rows, 'lllrrrrlr'))
        L.append(f"\nMétodo: {(F.lsc or {}).get('method', {}).get('egress', '').replace('ver summary', 'ver la sensibilidad abajo')}\n")
        if F.longest30:
            L.append(f"\nSensibilidad: con 0.30 m de separación de esquinas y obstáculos (NFPA 101 7.6) la ruta {F.longest30['path']} mide "
                     f"{n(F.longest30['length'])} m frente a {n(F.longest30['limit'])} m.\n")
        if F.margin is not None:
            L.append(f"\n**Margen ajustado:** la ruta más larga ({F.longest['id']}, {F.longest['from']}) deja {n(F.margin)} m de margen. "
                     'La franja de evacuación por lavado y P-1 debe permanecer libre (sin racks ni carritos); cualquier cambio de equipos en '
                     'cold prep o lavado obliga a volver a medir. Con PS-1 aprobada como segunda salida el recorrido baja a lo indicado en la '
                     'última columna (informativo, PS-1 no se cuenta).\n')
    # widths
    L.append('\n## 6. Anchos libres\n\n')
    rows = [(r.get('label'), n(r['min_width']), '0.915', 'sí' if r['min_width'] >= 0.915 else 'NO') for r in F.routes]
    rows += [(f"{PT_ES.get(c['from'], c['from'])} → {PT_ES.get(c['to'], c['to'])}", n(c['bottleneck']), '0.915',
              'sí' if c['bottleneck'] >= 0.915 else 'NO') for c in F.conns]
    if rows:
        L.append(table(['Tramo', 'Ancho libre mín. (m)', 'Mín. NFPA 101 (m)', '≥ mínimo'], rows, 'lrrl'))
    L.append(f"\nPuertas: ancho libre ≥0.81 m por hoja (NFPA 101 7.2.1.2.3.2, verificar) y ≥0.90 m (Ley 7600 art. 140). D-ENT hojas de "
             f"{n(F.ls.get('exits', [{}])[0].get('leaf'))} m; P-1 vano {n(F.op.get('P-1', {}).get('width'))} m — paso libre real {FLAG_SITE}.\n")
    # signage
    L.append('\n## 7. Señalización de salida\n\n')
    L.append(table(['Rótulo', 'Texto', 'Posición (x, y)', 'Zona', 'Nota'],
                   [(s['id'], s.get('text'), f"{n(s['at'][0])}, {n(s['at'][1])}", F.zlabel(s['at']), s.get('note', '')) for s in F.ls.get('exit_signs', [])]))
    L.append(f'\nRótulos iluminados con autonomía ≥1.5 h. Rótulo de capacidad "CAPACIDAD MÁXIMA {F.declared}" junto a D-ENT.\n')
    # emergency lighting
    L.append('\n## 8. Iluminación de emergencia\n\n')
    em = F.ls.get('emergency_lights', [])
    L.append(f"{len(em)} luminarias autónomas. {F.ls.get('emergency_note', '')}\n\n")
    L.append(table(['#', 'Posición (x, y)', 'Zona'], [(i + 1, f'{n(p[0])}, {n(p[1])}', F.zlabel(p)) for i, p in enumerate(em)], 'rll'))
    # extinguishers
    L.append('\n## 9. Extintores portátiles\n\n')
    L.append(table(['Extintor', 'Tipo', 'Posición (x, y)', 'Zona', 'Nota'],
                   [(x['id'], x['type'], f"{n(x['at'][0])}, {n(x['at'][1])}", F.zlabel(x['at']), x.get('note', '')) for x in F.ls.get('extinguishers', [])]))
    if F.checks:
        L.append('\nDistancias de recorrido medidas (A-104):\n\n')
        rows = [(c['id'], c['hazard'], c['device'], c['criterion'], n(c['length']), n(c['limit']),
                 'dentro del límite' if c.get('ok') else 'VERIFICAR') for c in F.checks.values() if c.get('kind') != 'PM']
        L.append(table(['Chequeo', 'Riesgo', 'Extintor', 'Criterio', 'Medido (m)', 'Límite (m)', 'Estado'], rows, 'llllrrl'))
    # suppression
    L.append('\n## 10. Supresión fija de campanas\n\n')
    ps = F.ls.get('pull_station', {})
    L.append(bullets([
        'HD-1 (línea a gas: ' + ', '.join(F.hood_serves.get('HD-1', [])) + '): químico húmedo UL 300 / NFPA 17A; corte automático de gas '
        '(VS, rearme manual) y de energía de los equipos protegidos (KS-1).',
        'HD-2 (parrilla ' + ', '.join(F.hood_serves.get('HD-2', [])) + ', combustible sólido): sistema independiente listado para combustible '
        'sólido; arrestachispas antes de los filtros.',
        f"Pulsadores {', '.join(ps.get('ids', []))} en ({n(ps.get('at', [0, 0])[0])}, {n(ps.get('at', [0, 0])[1])}), h {ps.get('h', '')}: {ps.get('note', '')}",
        f'{FLAG_EXT}.',
        f'{FLAG_SMOKER}.',
    ]))
    pm = F.checks.get('PM-1')
    if pm:
        dh = pm.get('dist_to_hoods') or {}
        dtxt = ', '.join(f'{k} {n(v)} m' for k, v in dh.items()) if dh else f"{n(pm['length'])} m"
        L.append(f"\nChequeo del pulsador (A-104): {pm['criterion']}. Medido a las campanas: {dtxt}; "
                 f"{n(pm.get('dist_to_egress_path'))} m de la ruta de egreso de cocina, {n(pm.get('walk_from_line'))} m a pie desde la línea → "
                 + ('dentro del criterio.' if pm.get('ok') else '**VERIFICAR**: la distancia exigida depende de la edición NFPA 96 / 17A y del '
                    'listado del sistema (la cifra de 3–6 m es un criterio IFC de referencia).') + '\n')
    # detection
    L.append('\n## 11. Detección y alarma\n\n')
    rows = []
    for i, p in enumerate(F.ls.get('smoke_detectors', [])):
        z = F.zone_at(p)
        rows.append((i + 1, f'{n(p[0])}, {n(p[1])}', F.zlabel(p), 'térmico' if z in ('B', 'E') else 'humo'))
    L.append(table(['#', 'Posición (x, y)', 'Zona', 'Tipo'], rows, 'rlll'))
    L.append('\n' + bullets([F.ls.get('detector_note', ''), F.ls.get('sprinklers', ''),
                             'Detector de gas DG-1 y monitor de CO DCO-1: ver 02 §14 y E-101.' if F.devices else None]))
    # solid fuel
    L.append('\n## 12. Combustible sólido (leña / carbón)\n\n')
    L.append(bullets([
        F.ls.get('fuel_storage_note', ''),
        (f"Separación medida del almacén {F.fuel['id']} a los aparatos: " + ', '.join(f'{k} {n(v)} m' for k, v in F.fuel_d.items())
         + ' (≥0.915 m exigidos, NFPA 96 cap. 14, verificar; depende de la huella real del smoker).') if F.fuel_d else None,
        'Extintor para combustible sólido (2-A de agua pulverizada o clase K 6 L) a ≤6 m de cada aparato y del almacén; manguera fija si un '
        'hogar supera 0.14 m³ (verificar ficha).',
        f"{FLAG_SMOKER}.",
    ]))
    # hazards list
    L.append('\n## 13. Riesgos especiales\n\n' + bullets([
        'Aparatos a gas bajo HD-1 y parrilla de carbón/leña bajo HD-2; smoker con chimenea propia (EXT-3).',
        'Almacén de químicos W7 en gabinete cerrado; almacén seco A6 en el ala; leña S3 provisión de un día.',
        'Horno K2 con recirculación listada UL 710B.',
    ]))
    # operating conditions
    L.append('\n## 14. Condiciones de operación (compromisos del operador)\n\n' + bullets([
        f'No superar {F.declared} personas en el local (clientes + personal); rótulo visible en D-ENT.',
        'Barra solo de servicio: sin taburetes ni clientes de pie; sin espera interior; cola y retiro de delivery afuera.',
        'Mantener libres la franja de lavado, P-2 y P-1 (ruta de evacuación del ala).',
        'Leña: solo la provisión de un día; cenizas en contenedor metálico con tapa, retiro diario fuera de horario.',
        'Plan de emergencias integrado al del condominio, capacitación en extintores y supresión, simulacro anual.',
        'Limpieza de la extracción de combustible sólido mensual; mantenimiento semestral de la supresión; bitácora de inspecciones.',
    ]))
    # >= 50
    L.append(f'\n## 15. Qué cambia con {F.threshold} personas o más\n\n' + bullets([
        'Pasa a ocupación de reunión pública (NFPA 101 cap. 12, verificar edición).',
        'Puerta D-ENT con giro hacia afuera (7.2.1.4.2) y posibles herrajes antipánico (umbral de 100 personas en reunión pública, '
        'verificar edición).',
        'Camino común limitado a 6.1 m cuando el espacio sirve a más de 50: la salida única deja de ser aceptable → segunda salida (PS-1).',
        'Rociadores automáticos supervisados en restaurantes nuevos de reunión pública (12.3.5, ediciones 2021+).',
        'Pasillos que sirven mesas ≥1.12 m; rótulo de carga de ocupantes obligatorio.',
    ]))
    if F.ls_issues:
        L.append('\n## 16. Observaciones abiertas del cálculo (A-104)\n\n' + bullets(F.ls_issues))
    L.append('\n' + flags_block())
    return ''.join(L)


# ------------------------------------------------------------------------------------------------ 04 cálculos


def doc_04(F):
    L = [header(F, '04', 'Cálculos preliminares de instalaciones',
                '**PRELIMINAR — a validar por ingeniero** (mecánico / electricista). Valores de referencia para dimensionar espacios y '
                'coordinar; no sustituyen las memorias de cálculo firmadas. Fuentes: `data/mech_calcs.json` (M-101/M-102) y '
                '`data/elec_loads.json` (E-101).')]
    M = F.mech or {}
    E = F.elec or {}
    ex = M.get('exhaust', {})
    rows = []
    for sid in ('EXT-1', 'EXT-2'):
        s = F.exh(sid)
        if s and s.get('Q_Ls'):
            rows.append((f"Extracción {sid} ({s.get('hood')})", f"{n(s['Q_Ls'], 0)} L/s · ducto {'×'.join(map(str, s['duct']['rect_mm']))} mm", '§1'))
    if M.get('makeup_air'):
        mu = M['makeup_air']
        rows.append(('Aire de reposición AR-1', f"{n(mu['design_Q_Ls'], 0)} L/s ({mu['design_pct']} %) · ducto {'×'.join(map(str, mu['duct']['rect_mm']))} mm", '§2'))
    if M.get('gas'):
        g = M['gas']
        rows.append(('Gas (4 equipos)', f"≈{n(g['total_kW_typ'], 1)} kW · principal {g.get('main_pipe', {}).get('en el local', {}).get('LPG', '—')} GLP / "
                     f"{g.get('main_pipe', {}).get('hasta 15 m desde el regulador', {}).get('NG', '—')} GN", '§3'))
    if M.get('hot_water'):
        hw = M['hot_water']
        rows.append(('Agua caliente', f"{hw.get('peak_hour_demand_L_60C')} L/h pico → CA-1 {hw.get('CA-1', {}).get('volume_L')} L / "
                     f"{n(hw.get('CA-1', {}).get('kW'), 1)} kW + CA-2 {hw.get('CA-2', {}).get('volume_L')} L", '§4'))
    if M.get('grease_trap'):
        gt = M['grease_trap']
        rows.append(('Trampa de grasa GT-1', f"{gt.get('2min', {}).get('pdi_size_gpm')}–{gt.get('1min', {}).get('pdi_size_gpm')} gpm (PDI, referencia)", '§5'))
    if E.get('demand'):
        dm = E['demand']
        rows.append(('Electricidad', f"demanda {n(dm['total_demand_VA'] / 1000, 1)} kVA · diseño {n(dm['design_VA'] / 1000, 1)} kVA · principal "
                     f"{dm.get('suggested', {}).get('main_A')} A ({E.get('system_assumed', '').split(' (')[0]})", '§7'))
    if rows:
        L.append('## Resumen de cifras (PRELIMINAR)\n\n' + table(['Concepto', 'Valor preliminar', 'Ver'], rows) + '\n')
    if ex:
        b = ex.get('basis', {})
        L.append('## 1. Extracción de campanas\n\n')
        L.append(f"PRELIMINAR — a validar por ingeniero. {b.get('rates', '')}\n\n")
        rows = []
        for s in ex.get('systems', []):
            if s.get('Q_Ls') is None:
                continue
            dct = s.get('duct', {})
            rows.append((s['id'], f"{s.get('hood')} · {s.get('kind')}", f"{n(s.get('hood_length_m'))} × {n(s.get('hood_depth_m'))}",
                         ', '.join(a['id'] for a in s.get('appliances', [])), s.get('duty_name'), f"{s.get('rate_cfm_per_ft')} / {n(s.get('rate_Ls_per_m'), 0)}",
                         f"{n(s['Q_Ls'], 0)} / {s.get('Q_m3h')} / {s.get('Q_cfm')}",
                         f"{'×'.join(map(str, dct.get('rect_mm', [])))} ({n(dct.get('velocity_rect_ms'), 1)} m/s) · Ø{dct.get('round_mm')}",
                         f"{s.get('listed_range_Ls', ['', ''])[0]}–{s.get('listed_range_Ls', ['', ''])[1]}"))
        L.append(table(['Sistema', 'Campana', 'L × F (m)', 'Equipos', 'Servicio', 'cfm/ft / L/s·m', 'Q (L/s / m³/h / cfm)', 'Ducto (mm)',
                        'Rango campana listada (L/s)'], rows))
        L.append(f"\nVelocidad de diseño {b.get('v_design_ms')} m/s; mínima NFPA 96 {b.get('v_min_ms_nfpa96')} m/s; máxima práctica "
                 f"{b.get('v_max_practical_ms')} m/s. {b.get('duct_rule', '')}.\n")
        e1 = F.exh('EXT-1') or {}
        if e1.get('existing_collar'):
            c = e1['existing_collar']
            L.append(f"\nRiser existente de Marna's para EXT-1: sección {n(c['section_m'][0])} × {n(c['section_m'][1])} m → "
                     f"{n(c['velocity_ms'], 2)} m/s con el caudal de EXT-1. {c.get('note', '')}\n")
        e3 = F.exh('EXT-3') or {}
        if e3:
            alt = e3.get('alternative_hood', {})
            L.append(f"\nEXT-3 (smoker S1): {e3.get('primary', '')}. " + (
                f"Si se exige campana: {alt.get('when', '')} → ≈{n(alt.get('Q_Ls'), 0)} L/s ({alt.get('Q_m3h')} m³/h), ducto "
                f"{'×'.join(map(str, alt.get('duct', {}).get('rect_mm', [])))} mm.\n" if alt else '\n'))
        L.append(f'\n**{FLAG_EXT}.** **{FLAG_SMOKER}.**\n')
    mua = M.get('makeup_air', {})
    if mua:
        L.append('\n## 2. Aire de reposición\n\n')
        L.append(f"PRELIMINAR — a validar por ingeniero. {mua.get('basis', '')}\n\n")
        L.append(f"Extracción total {n(mua['exhaust_total_Ls'], 0)} L/s ({mua['exhaust_total_m3h']} m³/h, {mua['exhaust_total_cfm']} cfm).\n\n")
        L.append(table(['% reposición', 'Q (L/s)', 'm³/h', 'cfm', 'Transferencia desde salón (L/s)'],
                       [(f"{c['pct']} %" + (' (diseño)' if c['pct'] == mua.get('design_pct') else ''), n(c['Q_Ls'], 0), c['Q_m3h'], c['Q_cfm'],
                         n(c['transfer_from_dining_Ls'], 0)) for c in mua.get('cases', [])], 'lrrrr'))
        d = mua.get('duct', {})
        df = mua.get('diffusers', {})
        L.append('\n' + bullets([
            f"Ducto de reposición {'×'.join(map(str, d.get('rect_mm', [])))} mm ({n(d.get('velocity_rect_ms'), 1)} m/s) o Ø{d.get('round_mm')} mm.",
            f"Difusores: {df.get('count')} × {n(df.get('Q_each_Ls'), 0)} L/s → área de cara ≥{n(df.get('min_face_area_each_m2_at_0.5ms'))} m² c/u a 0.5 m/s. "
            + sent(df.get('note', ''), f"Con {df.get('count')} difusores el área resulta grande: evaluar pleno perimetral o más difusores."),
            f"Si el smoker necesita campana: +{n(mua.get('if_smoker_hood_required', {}).get('extra_exhaust_Ls'), 0)} L/s de extracción → "
            f"reposición ≈{n(mua.get('if_smoker_hood_required', {}).get('mua_design_Ls'), 0)} L/s." if mua.get('if_smoker_hood_required') else None,
        ]))
    g = M.get('gas', {})
    if g:
        L.append('\n## 3. Gas\n\n')
        L.append(f"PRELIMINAR — a validar por ingeniero. Fuente: {g.get('source', '')}. {g.get('basis_kW', '')}.\n\n")
        L.append(table(['Equipo', 'Descripción', 'kW típ.', 'BTU/h típ.', 'Base', 'Ramal GLP', 'Ramal GN'],
                       [(c['id'], c['label'], n(c['kW_typ'], 1), nint(c['BTUh_typ']), c['basis'], c['branch_LPG'], c['branch_NG']) for c in g.get('consumers', [])],
                       'llrrlll'))
        L.append(f"\nTotal ≈{n(g.get('total_kW_typ'), 1)} kW ({nint(g.get('total_BTUh_typ'))} BTU/h) → GLP ≈{n(g.get('flow_LPG_kg_h'))} kg/h "
                 f"({n(g.get('flow_LPG_m3_h'))} m³/h) · gas natural ≈{n(g.get('flow_NG_m3_h'))} m³/h. Largo en planta {n(g.get('plan_length_m'))} m, "
                 f"desarrollado ≈{n(g.get('developed_length_m'))} m.\n\n")
        mp = g.get('main_pipe', {})
        L.append(table(['Tramo', 'Largo de tabla (ft)', 'GLP', 'GN'], [(k, v.get('length_ft_table'), v.get('LPG'), v.get('NG')) for k, v in mp.items()], 'lrll'))
        L.append(f"\nRecomendado: {g.get('recommended_main', '')}. {g.get('table_basis', '')}.\n")
    hw = M.get('hot_water', {})
    if hw:
        L.append('\n## 4. Agua caliente\n\n')
        L.append(f"PRELIMINAR — a validar por ingeniero. {hw.get('method', '')}. {hw.get('seats')} asientos → {n(hw.get('meals_peak_hour'), 0)} comidas "
                 f"en la hora pico → **{hw.get('peak_hour_demand_L_60C')} L a 60 °C**. {hw.get('first_hour_formula', '')}.\n\n")
        L.append(table(['Volumen (L)', 'kW', 'Recuperación (L/h)', '1.ª hora (L)', '≥ demanda'],
                       [(o['volume_L'], n(o['kW'], 1), o['recovery_Lh'], o['first_hour_L'], 'sí' if o['ok'] else 'no') for o in hw.get('options', [])], 'rrrrl'))
        c1, c2 = hw.get('CA-1', {}), hw.get('CA-2', {})
        L.append('\n' + bullets([
            f"CA-1: {c1.get('type', '')} {c1.get('volume_L')} L / {n(c1.get('kW'), 1)} kW, {c1.get('location', '')} (1.ª hora {c1.get('first_hour_L')} L).",
            f"CA-2: {c2.get('type', '')} {c2.get('volume_L')} L / {n(c2.get('kW'), 1)} kW — sirve {c2.get('serves', '')}.",
            hw.get('note', ''),
        ]))
    gt = M.get('grease_trap', {})
    if gt:
        L.append('\n## 5. Trampa de grasa GT-1\n\n')
        L.append(f"PRELIMINAR — a validar por ingeniero. {gt.get('method', '')}.\n\n")
        t = gt.get('tank_assumed_m', [0, 0, 0])
        L.append(table(['Periodo de vaciado', 'Caudal (gpm / L/s)', 'Tamaño PDI (gpm / L/s)', 'Capacidad de grasa (lb / kg)'],
                       [(k, f"{n(gt[k]['flow_gpm'], 1)} / {n(gt[k]['flow_Ls'])}", f"{gt[k]['pdi_size_gpm']} / {n(gt[k]['pdi_size_Ls'])}",
                         f"{gt[k]['grease_capacity_lb']} / {n(gt[k]['grease_capacity_kg'], 1)}") for k in ('1min', '2min') if k in gt], 'lrrr').replace('| 1min |', '| 1 min |').replace('| 2min |', '| 2 min |'))
        L.append(f"\nSupuestos: fregadero {gt.get('sink')} de {gt.get('compartments')} tanques de {t[0]} × {t[1]} × {t[2]} m "
                 f"({n(gt.get('tanks_volume_L'), 0)} L). Recomendación: {gt.get('recommendation', '')}.\n")
    if M.get('plumbing_fixtures'):
        L.append('\n## 6. Aparatos sanitarios y desagües\n\n')
        L.append('PRELIMINAR — TO BE ENGINEERED (CIHSE 2017).\n\n')
        L.append(table(['Tag', 'Aparato', 'AF', 'AC', 'Desagüe', 'UD', 'Sifón / ventilación', 'Descarga a', 'Nota'],
                       [(p['tag'], p['name'], p['af'], p['ac'], p['drain'], p['dfu'] if p['dfu'] is not None else '—', p['trap'], p['to'], p.get('note', ''))
                        for p in M['plumbing_fixtures']], 'lllllrlll'))
        L.append('\n' + table(['Punto existente', 'Uso propuesto', 'UD ref.', 'Colector', 'En mep.drain_existing'],
                              [(w['id'], w['use'], w['dfu_ref'] if w['dfu_ref'] is not None else '—', w['collector'] or '—', 'sí' if w['in_mep_drain_existing'] else 'no')
                               for w in M.get('wet_points_existing', [])], 'llrll'))
        if M.get('wet_points_used_but_not_in_mep_drain_existing'):
            L.append(f"\nPuntos usados que no figuran en `mep.drain_existing`: {', '.join(M['wet_points_used_but_not_in_mep_drain_existing'])} — confirmar en sitio.\n")
    if not M:
        L.append('> `data/mech_calcs.json` no está disponible: ejecutar `tools/build_all.sh` (láminas M-101/M-102) y regenerar.\n\n')
    E = F.elec or {}
    if E:
        L.append('\n## 7. Cargas eléctricas\n\n')
        L.append(f"PRELIMINAR — a validar por ingeniero electricista (Código Eléctrico CR / NEC 2020). Sistema supuesto: {E.get('system_assumed', '')}.\n\n")
        dm = E.get('demand', {})
        lab = [('lighting', 'Alumbrado general'), ('sign', 'Rótulo exterior'), ('receptacles', 'Tomas generales'), ('kitchen', 'Equipos de cocina'),
               ('motors', 'Motores (ventiladores)'), ('hvac_reserve', 'Reserva A/C'), ('control_it', 'Control / TI')]
        rows = [(t, n(dm.get(k, {}).get('demand_VA', 0) / 1000), dm.get(k, {}).get('basis', '')) for k, t in lab if k in dm]
        rows.append(('**Demanda total**', f"**{n(dm.get('total_demand_VA', 0) / 1000)}**", ''))
        rows.append(('+25 % cargas continuas', n(dm.get('continuous_adder_VA', 0) / 1000), dm.get('continuous_basis', '')))
        rows.append(('**Carga de diseño**', f"**{n(dm.get('design_VA', 0) / 1000)}**", f"conectada total {n(dm.get('connected_total_VA', 0) / 1000)} kVA"))
        L.append(table(['Grupo', 'kVA', 'Criterio'], rows, 'lrl'))
        sg = dm.get('suggested', {})
        L.append('\n' + bullets([
            f"Corriente: {n(dm.get('I_3F_208'), 1)} A a 208 V 3F ({n(dm.get('I_3F_208_growth'), 1)} A con {n(dm.get('growth_pct'), 0)} % de crecimiento); "
            f"{n(dm.get('I_1F_240'), 1)} A a 240 V 1F ({n(dm.get('I_1F_240_growth'), 1)} A).",
            f"Sugerido: {sg.get('system', '')} · principal {sg.get('main_A')} A · barra {sg.get('bus_A')} A · {sg.get('spaces')} espacios "
            f"({sg.get('spaces_used')} usados). Alternativa: {sg.get('alt_1F', '')}.",
            'Balance de fases conectado: ' + ', '.join(f'{k} {n(v / 1000)} kVA' for k, v in dm.get('phase_connected_VA', {}).items())
            + f" (desbalance {n(dm.get('phase_imbalance_pct'), 1)} %).",
        ]))
        L.append('\n### 7.1 Cuadro de circuitos (preliminar)\n\n')
        rows = [(c['circuit'], c['ref'], c['desc'], c['V'], c['poles'], n(c['VA'] / 1000), n(c['I_A'], 1), c['breaker_A'], c['conductor'],
                 'sí' if c.get('gfci') else '', c.get('group_name', ''))
                for c in sorted(E.get('circuits', []), key=lambda c: int(re.match(r'\d+', str(c['circuit'])).group()) if re.match(r'\d+', str(c['circuit'])) else 999)]
        L.append(table(['Circ.', 'Ref.', 'Descripción', 'V', 'Polos', 'kVA', 'A', 'Breaker', 'Cond.', 'GFCI', 'Grupo'], rows, 'lllrrrrrlll'))
        L.append('\nkVA de equipos: valores típicos de catálogo (TBV) — reemplazar por las placas de los equipos.\n')
        if E.get('interlocks'):
            L.append('\n### 7.2 Matriz de enclavamientos\n\n')
            L.append(table(['Causa', 'Efectos'], [(i['cause'], '; '.join(f'{k}: {v}' for k, v in i['effects'].items())) for i in E['interlocks']]))
        lt = E.get('lighting', {})
        if lt:
            cnt, w = {}, {}
            for x in lt.get('luminaires', []):
                cnt[x['type']] = cnt.get(x['type'], 0) + 1
                w[x['type']] = w.get(x['type'], 0) + float(x.get('W') or 0)
            L.append('\n### 7.3 Alumbrado (de A-201)\n\n')
            L.append(table(['Tipo', 'Cantidad', 'W totales'], [(k, cnt[k], n(w[k], 0)) for k in sorted(cnt)], 'lrr'))
            L.append(f"\nConectado {n(dm.get('lighting', {}).get('connected_VA'), 0)} VA; mínimo NEC {n(dm.get('lighting', {}).get('nec_min_VA'), 0)} VA "
                     f"({n(dm.get('lighting', {}).get('nec_unit_VA_m2'), 0)} VA/m² × {n(dm.get('area_m2'), 1)} m²).\n")
    else:
        L.append('> `data/elec_loads.json` no está disponible: ejecutar `tools/build_all.sh` (lámina E-101) y regenerar.\n\n')
    L.append('\n## 8. Fuentes y verificaciones en sitio\n\n' + bullets(M.get('sources', []) + E.get('sources', [])))
    if E.get('verify_on_site'):
        L.append('\nVERIFY ON SITE (eléctrico): ' + '; '.join(E['verify_on_site']) + '.\n')
    L.append('\n' + flags_block())
    return ''.join(L)


# ------------------------------------------------------------------------------------------------ 05 checklist


DOMAINS = {
    'permisos': 'Permisos, CFIA, municipalidad y condominio',
    'egreso': 'Seguridad humana y egreso (Bomberos · NFPA 101 / 10)',
    'salud_7600': 'Salud (DE 37308-S / 43432-S) y accesibilidad (Ley 7600)',
    'cocina': 'Cocina, combustión, gas y extracción (NFPA 96 / 17A / 54 / 58)',
}


def rules(F):
    """Status of each requirement in the CURRENT data (v3): code, what the plan does, what is left to verify."""
    R_ = {}

    def r(i, code, estado, verif=None):
        R_[i] = (code, estado, verif)

    lp = F.longest
    lp_txt = (f"ruta más larga {lp['id']} {n(lp['length'])} m vs {n(lp['limit'])} m (margen {n(F.margin)} m)" if lp else 'sin cálculo A-104')
    tight = F.margin is not None and F.margin < 1.5
    c4 = (F.bykey.get('caja') or [None])[0]
    p1w = F.op.get('P-1', {}).get('width')
    pm = F.checks.get('PM-1')
    kch = [c for c in F.checks.values() if c.get('kind') == 'K']
    sfch = [c for c in F.checks.values() if c.get('kind') == 'SF']
    ach = F.checks.get('A-max')
    n_sheets = len(F.sheets)
    lk = (F.bykey.get('lockers') or [None])[0]
    hw_ids = ', '.join(e['id'] for e in F.handwash)
    k3 = F.eq.get('K3', {})
    mua = (F.mech or {}).get('makeup_air', {})
    v_ok = all(s.get('v_ok', True) for s in ((F.mech or {}).get('exhaust', {}) or {}).get('systems', []) if s.get('Q_Ls'))
    ff = F.fryer_flame
    fd = F.fuel_d
    fuel_ok = fd and all(v >= 0.915 for v in fd.values())
    budget = f"≤{n(F.restroom_budget, 1)} m desde D-ENT" if F.restroom_budget is not None else 'medir'

    # ---- permisos
    r('PER-01', 'DOC', 'Anteproyecto sin firma: cada lámina deja en blanco la casilla PROFESIONAL RESPONSABLE (CFIA).',
      'Contratar arquitecto responsable e ingenieros (mecánico, electricista, estructural); registrar contrato en el APC; firma digital por lámina.')
    r('PER-02', 'PAR', f'Juego de anteproyecto de {n_sheets} láminas (A/M/E) + memoria, especificaciones y cálculos preliminares (01–04).',
      'Completar planos constructivos: detalles, planta de cubierta, estructural (penetraciones, soportes), memorias de cálculo firmadas.')
    r('PER-03', 'DOC', 'No aplica al plano; el paquete está ordenado para el ingreso APC (modalidad remodelación).', 'Ingresar en APC con los requisitos previos (06 pasos 1–5).')
    r('PER-04', 'PAR', f'Lámina {sheet_tag("A104")} y memoria 03 elaboradas (anteproyecto).', 'Firma del profesional, formulario de Bomberos y ajuste a la edición NFPA vigente.')
    r('PER-05', 'INF', 'Es obra mayor: demoliciones, muros nuevos, campanas, gas, electricidad e hidrosanitario.', 'Tramitar por APC con profesional; no usar boleta de obra menor.')
    r('PER-06', 'DOC', 'Trámite posterior a la revisión APC (06 paso 6).', 'Uso de suelo, póliza RT de la obra, tributos al día, impuesto 1 %.')
    r('PER-07', 'DOC', 'Pendiente del cliente (06 paso 2). Actividad: restaurante con venta de bebidas alcohólicas.', 'Confirmar plan regulador vigente (1991 o el nuevo) y que el uso sea conforme.')
    r('PER-08', 'DOC', 'Carta modelo 08 con todas las solicitudes (obras, baños, basura, gas, cubierta, PS-1, puerta, rótulos, horario).',
      'Obtener carta/acta firmada por la administración o asamblea antes del APC; revisar el reglamento interno.')
    r('PER-09', 'DOC', 'Pendiente del cliente.', 'Autorización escrita del propietario registral o arrendador (también la pide la patente).')
    r('PER-10', 'OK' if F.area <= 300 else 'INF', f'Área del local {n(F.area)} m² ≤ 300 m²: aplica la declaración jurada de los profesionales en lugar del visado de Salud.',
      'Confirmar área tasada y clasificación "Otras Edificaciones"; la declaración obliga a cumplir el DE 37308-S (ver S-xx).')
    r('PER-11', 'DOC', 'Trámite del operador antes de abrir (06 paso 10).', 'Declaración jurada Anexo 3 del DE 43432-S; grupo de riesgo del CIIU 5610.')
    r('PER-12', 'DOC', 'Trámite del operador después de la obra (06 paso 11).', 'PSF, uso de suelo, póliza RT, CCSS, Hacienda, autorización del dueño.')
    r('PER-13', 'PAR', 'Sin baños propios: se usan los servicios comunes del centro comercial para clientes y personal (dato del cliente).',
      f'Autorización escrita de la administración, capacidad según CIHSE Tabla 5.3 sumando LAVA ({F.declared}), baño accesible, horario completo y distancia {budget}; confirmar con el Área Rectora de Salud.')
    r('PER-14', 'PAR', f"Casilleros {lk['id'] if lk else '—'}, basureros con tapa {', '.join(e['id'] for e in F.bykey.get('waste_bins', []))}, lavamanos {hw_ids}; "
                       'cuarto de basura del centro comercial.', 'Confirmar en el texto del DE 37308-S (vestidor, residuos) y el uso del cuarto de basura (08).')
    r('PER-15', 'PAR', 'El servicio sanitario accesible es el del centro comercial.', 'Verificar cubículo accesible (art. 143: ≥2.25 × 1.55 m, puerta 0.90 hacia afuera, barras) y ruta accesible.')
    r('PER-16', 'OK' if c4 and float(c4.get('h', 9)) <= 0.80 else 'AJ',
      f"Caja accesible {c4['id']} a h {n(c4.get('h'))} m, largo {n(eq_dims(c4)[0])} m, con espacio inferior." if c4 else 'No hay tramo a 0.80 m.',
      'Confirmar altura terminada y espacio libre para rodillas (≥0.70 m, referencia) en el detalle de A-105.')
    r('PER-17', 'OK' if (F.main_aisle or 0) >= 1.2 else 'AJ',
      f"D-ENT {n(F.dent.get('width'))} m; pasillo principal {n(F.main_aisle)} m; interiores ≥{n(F.min_route['min_width']) if F.min_route else '—'} m; P-1 vano {n(p1w)} m.",
      'Medir paso libre real de P-1 con la hoja instalada (≥0.90) y espacio de 0.45 m del lado opuesto a las bisagras.')
    r('PER-18', 'PAR', f'D-ENT abre hacia adentro: aceptable con <50 personas (capacidad declarada {F.declared}). Se solicita invertir el giro (08).',
      'Confirmar con Bomberos; si la carga llega a 50, giro hacia afuera obligatorio.')
    r('PER-19', 'SIT', f'Altura supuesta {n(F.ceiling)} m (no legible en el PDF).', 'Medir piso–losa y piso–cielo; si <≈3.4 m bajo losa, reevaluar campanas, ductos y smoker.')
    r('PER-20', 'SIT', 'Chimenea del smoker (EXT-3) y ductos EXT-1/EXT-2 dibujados hasta cubierta; remate no verificado.',
      'Confirmar el artículo INVU de chimeneas (≥5 m sobre edificios en 25 m, por verificar), distancias NFPA 96 §7.8 y aprobación del condominio.')
    r('PER-21', 'PAR', f'Lámina {sheet_tag("E101")} y cuadro de cargas preliminar (04 §7).' if 'E101' in F.sheet_ids else 'Sin lámina eléctrica.',
      'Diseño y firma del ingeniero electricista (NEC 2020); acometida y capacidad con la administración.')
    r('PER-22', 'PAR', f'Láminas {sheet_tag("M101")}/{sheet_tag("M102")}: hidrosanitario, trampa de grasa GT-1, gas desde la red del centro comercial.'
      if 'M101' in F.sheet_ids else 'Sin láminas mecánicas.', 'Diseño y firma del ingeniero mecánico (CIHSE); tipo de gas y presión de la red.')
    r('PER-23', 'DOC', 'Se abre en el APC al tramitar la licencia (06 paso 7).', 'Designar director técnico / inspector de la obra.')
    r('PER-24', 'PAR', f'Se venderá alcohol: licencia clase C. {len(F.tables)} mesas y {F.seats} asientos, sin banquetas de barra; cocina equipada.',
      'Confirmar requisitos de Santa Ana (mínimos de mesas/asientos, distancias a centros educativos/salud, zonificación); menú ≥10 opciones.')
    r('PER-25', 'DOC', 'Rótulo exterior con circuito propio (E-101); permiso pendiente.', 'Croquis, montaje fotográfico, área del rótulo, aprobación del condominio.')
    # ---- egreso
    r('EG-01', 'OK', 'Los documentos citan el RNPCI 2023 (no el Manual 2013 derogado).', 'Confirmar versión vigente del RNPCI a la fecha de presentación.')
    r('EG-02', 'PAR', 'Citas NFPA marcadas "verificar edición".', 'Declarar en la lámina la edición NFPA adoptada por Bomberos.')
    r('EG-03', 'PAR', f'{sheet_tag("A104")} + memoria 03 como base.', 'Formulario de Bomberos, memoria firmada, láminas PCI/gas/mecánica firmadas.')
    if F.occ_zone is not None:
        ok = F.occ_zone < F.threshold and F.declared < F.threshold
        r('EG-04', 'OK' if ok else 'AJ', f'Carga de cálculo {F.occ_zone} (por zona) y declarada {F.declared} < {F.threshold}: restaurante con menos de 50 personas.',
          'Validar la clasificación con Bomberos; no agregar asientos ni barra de pie sin recalcular.')
        r('EG-05', 'OK', f'Tabla de carga por zona (03 §3): {F.occ_zone} por zona / {F.occ_use} por uso / {n(F.occ_raw)} sin redondear.',
          'Confirmar factores (salón 1.4 m² netos; cocina 9.3 m² brutos; barra tratada como área de trabajo).')
    if lp:
        r('EG-06', 'PAR' if tight else 'OK', f'Salida única: {lp_txt}.', 'Mantener libre la franja de lavado y P-1; volver a medir ante cambios; confirmar el límite para <50 sin rociadores.')
        r('EG-07', 'PAR' if tight else 'OK', f'Todo el recorrido es camino común: {lp_txt}.', 'Idem EG-06; PS-1 aprobada reduciría el recorrido.')
    r('EG-08', 'SIT', 'D-ENT descarga al pasillo abierto del centro comercial.', 'Confirmar que el pasillo común es abierto y lleva a la vía pública sin otros límites.')
    if F.routes:
        mw = min([r_['min_width'] for r_ in F.routes] + [c['bottleneck'] for c in F.conns])
        r('EG-09', 'OK' if mw >= 0.915 else 'AJ', f'Ancho libre mínimo medido {n(mw)} m ≥ 0.915 m; SAL-1 2.00 m (capacidad 400 personas a 5 mm/p).',
          'Medir paso libre de hojas (≥0.81 m) en D-ENT y P-1; márgenes pequeños en cocina: no invadir con equipos.')
        r('EG-10', 'OK' if (F.main_aisle or 0) >= 0.915 else 'AJ', f'Pasillo principal del salón {n(F.main_aisle)} m (≥0.915 m con ≤50 personas).',
          'No unir más mesas ni agregar sillas en el pasillo.')
    r('EG-11', 'PAR', f'Hojas de D-ENT hacia adentro (aceptable con {F.declared} < 50).', 'Recomendado invertir el giro sin invadir el pasillo (08).')
    r('EG-12', 'OK', 'Especificado en 02 §6: apertura sin llave desde adentro, herrajes de palanca/barra.', 'Confirmar herrajes existentes de D-ENT en sitio.')
    r('EG-13', 'OK', 'El egreso del salón va directo a D-ENT sin cruzar la cocina; el personal sale por P-1 y el salón.', None)
    r('EG-14', 'PAR', 'PS-1 dibujada como CONDICIONAL; no se cuenta como salida.', 'Aprobación del condominio, destino del pasillo sur, resistencia al fuego, separación entre salidas.')
    r('EG-15', 'OK', f"{len(F.ls.get('exit_signs', []))} rótulos de salida (RS) dibujados y especificados.", 'Confirmar visibilidad desde todos los puntos en sitio.')
    r('EG-16', 'OK', f"{len(F.ls.get('emergency_lights', []))} luminarias de emergencia en todo el recorrido; criterios 1.5 h / 10.8 lx / 1.1 lx.", 'Cálculo fotométrico del ingeniero electricista.')
    r('EG-17', 'PAR', f"{len(F.ls.get('smoke_detectors', []))} detectores dibujados; integración con la alarma del centro comercial pendiente.", 'Confirmar si hay alarma NFPA 72 y cómo integrarse.')
    r('EG-18', 'OK', 'Con <50 personas NFPA 101 no exige rociadores.', 'Confirmar si el edificio tiene rociadores (entonces readecuar la red).')
    if ach:
        r('EG-19', 'OK' if ach.get('ok') else 'AJ', f"Clase A: punto más lejano a {n(ach['length'])} m de un 2-A (≤{n(ach['limit'])}); extintores ABC en cocina, ala y salón.", 'Ubicar y rotular en sitio; altura de montaje.')
    if kch:
        r('EG-20', 'OK' if all(c.get('ok') for c in kch) else 'AJ', 'Clase K: ' + ', '.join(f"{c['hazard'].split()[0]} {n(c['length'])} m" for c in kch) + ' (≤9.15 m).', 'Rótulo junto al clase K.')
    r('EG-21', 'OK' if fuel_ok else 'PAR', f"Almacén {F.fuel['id'] if F.fuel else '—'} de un día; separación " + ', '.join(f'{k} {n(v)} m' for k, v in fd.items()) + ' (≥0.915).',
      'Confirmar volumen del rack y huella real del smoker (ficha).')
    if pm:
        r('EG-22', 'OK' if pm.get('ok') else 'PAR', f"Pulsadores junto a P-1 (lado salón), h {F.ls.get('pull_station', {}).get('h', '')}; a las campanas: "
          + (', '.join(f'{k} {n(v)} m' for k, v in (pm.get('dist_to_hoods') or {}).items()) or f"{n(pm['length'])} m") + '.',
          'Confirmar la distancia exigida (edición NFPA 96/17A y listado); la cifra 3–6 m es un criterio IFC de referencia.')
    r('EG-23', 'DOC', 'De cafetería a restaurante con combustible sólido.', 'Confirmar con Bomberos si se trata como cambio de uso (requisitos de ocupación nueva).')
    r('EG-24', 'OK', f'Rótulo CAPACIDAD MÁXIMA {F.declared} junto a D-ENT (A-104, 02 §15).', None)
    # ---- salud / 7600
    r('S-01', 'DOC', 'Trámite del operador (06 paso 10).', 'Declaración jurada solo cuando la obra cumpla el DE 37308-S.')
    r('S-02', 'PAR', 'Paquete de anteproyecto listo para completar y firmar.', 'Ver PER-01/02.')
    r('S-03', 'PAR', 'Servicios comunes del centro comercial (sin comunicación con la preparación de alimentos).', 'Separados H/M, ventilación, lavamanos con jabón y toallas: verificar en sitio.')
    r('S-04', 'PAR', f'Batería común del centro comercial; aforo de LAVA {F.declared}.', 'Cantidad de piezas según CIHSE Tabla 5.3 (edición vigente) con el aforo del condominio + LAVA.')
    r('S-05', 'SIT', f"Recorrido interno máximo a D-ENT {n(lp['length']) if lp else '—'} m → el baño común debe quedar a {budget} (36 m, INVU, artículo por confirmar).",
      'Medir en sitio la ruta al baño común para el punto más lejano del personal y de los clientes.')
    r('S-06', 'PAR', f"Casilleros {lk['id']} ({lk.get('note', '')[:60]}…); baños comunes." if lk else 'Sin casilleros.', 'Confirmar requisito de vestidor en el DE 37308-S / salud ocupacional.')
    r('S-07', 'OK', f"Lavamanos exclusivo en cocina {k3.get('id', '—')} (+ {', '.join(e['id'] for e in F.handwash if e['id'] != 'K3')}).",
      'La etiqueta de K3 dice "recomendado": es obligatorio; corregir el texto en layout.' if 'recomendado' in str(k3.get('label', '')).lower() else None)
    r('S-08', 'OK' if not F.m.get('dirty_clean_conflicts') else 'PAR', 'Flujo limpio/sucio sin cruces (validación automática); P-2 de cierre automático; químicos en W7.', 'Confirmar operación (horarios de recepción y retiro).')
    r('S-09', 'PAR', 'Fregadero W1 de 2 tanques con agua caliente y ducha de prelavado.', 'Confirmar si el DE 37308-S exige 3 tanques o lavavajillas.')
    r('S-10', 'OK', 'Trampa de grasa GT-1 bajo el fregadero (dimensionamiento preliminar en 04 §5).', 'Diseño según CIHSE y requisitos del alcantarillado del condominio.')
    r('S-11', 'PAR', 'Basureros con tapa W6 bajo el escurridor sucio; retiro diario al cuarto de basura del centro comercial.', 'Autorización y horario del cuarto de basura (08).')
    r('S-12', 'DOC', 'Programa de control de plagas del operador; cedazo en PS-1 si se aprueba.', 'Contrato con empresa autorizada; sellos en puertas y penetraciones.')
    r('S-13', 'OK', f'Acabados sanitarios por zona ({sheet_tag("A106")}, 02 §4) y coladeras de piso.', 'Fichas de materiales; pendientes a coladeras.')
    r('S-14', 'ING', 'Dos campanas con extracción independiente, aire de reposición e iluminación IP65 en cocina (A-201).', FLAG_EXT)
    r('S-15', 'OK', 'Agua potable del acueducto del edificio; agua caliente CA-1/CA-2.', 'Confirmar acometida y medidor en sitio.')
    r('S-16', 'OK', 'Estanterías con primer nivel ≥0.15 m; refrigeración con termómetro; químicos separados.', None)
    r('A-01', 'SIT', 'Acceso a nivel desde el pasillo común por D-ENT.', 'Medir desnivel y umbral (≤0.02 m) en sitio.')
    r('A-02', 'PAR', f"D-ENT {n(F.dent.get('width'))} m; P-1 vano {n(p1w)} m (paso libre ≥0.90 con hoja ≈0.96).", 'Medir paso libre y espacio lateral de 0.45 m.')
    r('A-03', 'OK' if (F.main_aisle or 0) >= 1.2 else 'AJ', f"Pasillo principal {n(F.main_aisle)} m (≥1.20); interiores ≥0.90.", None)
    r('A-04', 'PAR', 'Baño accesible del centro comercial.', 'Verificar art. 143–144 en la batería común.')
    r('A-05', 'OK' if c4 else 'AJ', f"Caja {c4['id']} h {n(c4.get('h'))} m." if c4 else '—', None)
    r('A-06', 'OK' if F.acc_tables else 'AJ', f"Mesas accesibles {', '.join(F.acc_tables)} con aproximación 0.80 × 1.20 (A-105).", 'No hay artículo confirmado de porcentaje de mesas; criterio de referencia.')
    r('A-07', 'PAR', 'Círculos Ø1.50 dibujados donde caben (A-105).', 'Artículo no confirmado; con las hojas de D-ENT abiertas no cabe en el vestíbulo.')
    r('A-08', 'OK' if 'A105' in F.sheet_ids else 'AJ', f"Lámina {sheet_tag('A105')} de accesibilidad.", None)
    r('A-09', 'DOC', 'Se cita CIHSE 2017.', 'Confirmar si una edición nueva rige desde el 28-07-2026 (fragmento de buscador).')
    # ---- cocina
    r('COC-01', 'PAR', f'Láminas {", ".join(sheet_tag(i) for i in ("A104", "M101", "M102") if i in F.sheet_ids)} de anteproyecto.', 'Firma del profesional; láminas de taller de campanas y supresión.')
    hd2 = F.hood_serves.get('HD-2', [])
    r('COC-02', 'OK' if hd2 and all(F.eq[i].get('key') == 'parrilla' for i in hd2) else 'AJ',
      f"HD-2 cubre solo {', '.join(hd2)}; EXT-2 con ducto, ventilador y descarga propios.", 'Confirmar en el diseño que no se une a EXT-1.')
    r('COC-03', 'PAR', 'Chimenea propia EXT-3 (NFPA 211) sobre el smoker hasta cubierta.', FLAG_SMOKER)
    r('COC-04', 'OK', 'Arrestachispas antes de filtros en HD-2 (especificado).', 'Listado del fabricante.')
    r('COC-05', 'SIT', 'Filtros de HD-2 ≥1.22 m sobre la superficie de cocción (TBV).', f'Depende de la altura libre ({n(F.ceiling)} m supuesta) y de la edición NFPA 96.')
    r('COC-06', 'ING', 'UL 300 en HD-1 y sistema listado para combustible sólido en HD-2 (especificados).', FLAG_EXT)
    r('COC-07', 'OK', 'Válvula VS enclavada (rearme manual) y contactor KS-1; matriz en 04 §7.2.', 'Confirmar según el listado del sistema.')
    if pm:
        r('COC-08', 'OK' if pm.get('ok') else 'PAR', f"Pulsadores en la ruta de salida junto a P-1, h {F.ls.get('pull_station', {}).get('h', '')}.", 'Distancia a la campana según edición y listado.')
    if kch:
        r('COC-09', 'OK' if all(c.get('ok') for c in kch) else 'AJ', 'Extintor clase K a ' + ' / '.join(n(c['length']) for c in kch) + ' m de las freidoras (≤9.15).', None)
    if sfch:
        r('COC-10', 'OK' if all(c.get('ok') for c in sfch) else 'AJ', 'Combustible sólido: ' + ', '.join(f"{c['hazard'].split()[0]} {n(c['length'])} m" for c in sfch) + ' (≤6 m).',
          'Tamaño del hogar de la parrilla (>0.14 m³ exige manguera fija).')
    r('COC-11', 'OK' if fuel_ok else 'PAR', 'Separación del almacén de leña: ' + ', '.join(f'{k} {n(v)} m' for k, v in fd.items()) + '.', 'Huella real del smoker y volumen del rack.')
    r('COC-12', 'OK', 'Retiro diario de cenizas en contenedor metálico con tapa, fuera de horario.', 'Punto exterior acordado con la administración (08).')
    r('COC-13', 'ING', 'Parrilla y smoker "listados o aprobados" en la especificación.', 'Fichas y listados; si la parrilla es de fabricación local, memoria de materiales para Bomberos.')
    r('COC-14', 'PAR', 'Base maciza de NW-1, vidrio vitrocerámico o pantalla ventilada tras la parrilla, panel NW-2 incombustible.', 'Especificación térmica TO BE ENGINEERED; holguras 457/76/0 mm de campanas y ductos.')
    r('COC-15', 'ING', 'Campanas listadas UL 710 o de acero 18 MSG / inox 20 MSG (especificado).', 'Voladizos según listado.')
    r('COC-16', 'ING', 'Ducto 16 MSG soldado en cerramiento RF; EXT-1 reutiliza el riser existente solo si la inspección lo aprueba.', FLAG_SITE + ': inspección con video del riser.')
    r('COC-17', 'SIT', 'Descargas en cubierta dibujadas esquemáticamente.', 'Planta de cubierta con distancias a tomas de aire, linderos y vecinos; aprobación del condominio.')
    r('COC-18', 'OK' if v_ok else 'AJ', f"Velocidades de ducto ≥2.54 m/s (04 §1); reposición de diseño {n(mua.get('design_Q_Ls'), 0)} L/s." if mua else 'Velocidades en 04 §1.',
      'Difusores de reposición: área de cara grande con 2 unidades — rediseñar (04 §2).')
    if ff:
        r('COC-19', 'OK' if ff[0] >= 0.406 else 'AJ', f'Freidora {ff[1]} a {n(ff[0])} m de la llama abierta más cercana ({ff[2]}) ≥0.406 m.', 'Condición: la plancha H3 sin llama expuesta.')
    r('COC-20', 'OK', 'Horno K2 con recirculación listada UL 710B.', 'Ficha del horno.')
    r('COC-21', 'NA' if F.gas_network else 'AJ', 'Sin cilindros: gas desde la red del centro comercial (dato del cliente).' if F.gas_network else 'Ubicación de cilindros no definida.',
      'Tipo de gas y ubicación del tanque/regulador de la red; si es GLP rigen las disposiciones de Bomberos.')
    r('COC-22', 'PAR', 'Llave principal fuera del local, solenoide, manifold, conectores ≤1.5 m; ruta tentativa por el muro norte.', 'Ruta que no atraviese sectores internos; presión y regulación.')
    r('COC-23', 'OK' if F.devices.get('DG-1') else 'AJ', 'Detector de gas DG-1 con corte de VS.', 'Altura según tipo de gas.')
    r('COC-24', 'DOC', 'Informe técnico de gas para el PSF (06 paso 9).', 'Profesional o inspector acreditado.')
    r('COC-25', 'OK', 'Limpieza mensual (sólido) y supresión semestral especificadas (02, 03).', None)
    return R_


def extra_rules(F):
    """Audit findings without a research requirement (mostly written on v2): status in v3."""
    R_ = {}

    def r(i, code, estado):
        R_[i] = (code, estado)

    has = lambda k: bool(F.bykey.get(k))  # noqa: E731
    r('PER-17-P1', 'OK' if (F.op.get('P-1', {}).get('width') or 0) >= 1.0 else 'AJ', f"P-1 con vano {n(F.op.get('P-1', {}).get('width'))} m (paso libre ≥0.90 a verificar).")
    r('NEW-01', 'OK', f'Tabla de carga y rótulo de {F.declared} en A-104 / 03.')
    r('NEW-02', 'PAR', f"Ruta más larga {n(F.longest['length']) if F.longest else '—'} m; margen {n(F.margin)} m.")
    r('NEW-03', 'OK' if len(F.hoods) >= 2 else 'AJ', f'{len(F.hoods)} campanas independientes (HD-1 gas, HD-2 parrilla).')
    r('NEW-04', 'ING', 'Supresión UL 300 + sistema para sólido, corte de gas y pulsadores especificados.')
    r('NEW-05', 'OK', 'Orden freidoras–plancha–cocina–parrilla conservado.')
    r('NEW-06', 'OK' if F.niche and 'incomb' in str(F.niche.get('material', '')) else 'PAR', 'Nicho decorativo incombustible, sin leña real.')
    r('NEW-07', 'OK' if F.fuel_d and all(v >= 0.915 for v in F.fuel_d.values()) else 'PAR', 'Separación del rack de leña ≥0.915 m (medida).')
    r('NEW-08', 'SIT', FLAG_SMOKER)
    r('NEW-09', 'SIT', 'Ductos existentes y shafts: inspección en sitio.')
    r('NEW-11', 'ING', 'Base maciza + vidrio vitrocerámico / pantalla ventilada: TO BE ENGINEERED.')
    r('NEW-12', 'OK', f"{len(F.ls.get('extinguishers', []))} extintores ubicados (A-104).")
    r('NEW-13', 'OK', 'Rótulos de salida y luces de emergencia (A-104).')
    r('NEW-14', 'NA' if F.gas_network else 'AJ', 'Gas de red del centro comercial: sin cilindros.')
    r('NEW-15', 'PAR', 'NW-2 protege la ruta hacia P-1; PS-1 condicional.')
    r('NEW-16', 'OK', f"Pasillo principal {n(F.main_aisle)} m.")
    r('NEW-17', 'ING', 'Clase de acabado de los listones exigida en 02 §4.')
    r('NEW-18', 'PAR', 'Casilleros L1 + baños comunes (autorización pendiente).')
    r('NEW-19', 'SIT', 'Rociadores / alarma del edificio: pedir planos a la administración.')
    r('NEW-20', 'ING', 'Descarga en cubierta; filtrado de humo si el condominio lo exige.')
    r('NEW-21', 'PAR', 'PS-1 condicional (aprobación del condominio).')
    r('EG-25', 'OK', f"Bancas con asientos individuales ({' + '.join(str(b['seats']) for b in F.banq)}).")
    r('EG-26', 'OK', 'Sin espera interior; vestíbulo libre.')
    r('EG-27', 'OK', 'Franja de evacuación por lavado definida (regla de operación).')
    r('EG-28', 'OK' if F.niche and 'incomb' in str(F.niche.get('material', '')) else 'PAR', 'Sin leña real ni jardinera tras la parrilla.')
    r('EG-29', 'ING', 'Clase de acabados interiores en 02 §4.')
    r('EG-30', 'OK' if has('chem_cabinet') else 'PAR', 'Químicos en gabinete W7; leña de un día.')
    r('EG-31', 'OK' if len(F.hoods) >= 2 else 'AJ', 'Extracción separada para combustible sólido.')
    r('EG-32', 'OK', 'Plancha entre freidoras y quemadores.')
    r('EG-33', 'SIT', f"Borde inferior de campanas ≈{n(F.hood_lower)} m (≥2.03 m NFPA 101 7.1.5, verificar) — altura real en sitio.")
    r('EG-34', 'OK', 'Egreso accesible a nivel; umbral ≤0.02 m especificado.')
    r('EG-35', 'NA' if F.gas_network else 'AJ', 'Gas de red del centro comercial.')
    r('EG-36', 'DOC', 'Plan de emergencias del operador (03 §14).')
    r('EG-37', 'OK', 'Sin penetraciones nuevas en los muros de la escalera.')
    r('EG-38', 'OK', 'D-P1-old con P-2 (cierre automático, sin llave) conserva el circuito.')
    r('COC-16b', 'OK', 'EXT-2 vertical propio sobre la parrilla (S-PIL descartado).')
    r('COC-11b', 'OK' if F.niche and 'incomb' in str(F.niche.get('material', '')) else 'PAR', 'Nicho incombustible sin hueco.')
    r('COC-16a', 'SIT', 'Reutilización del riser de Marna\'s solo con inspección aprobada.')
    r('COC-NEW-04', 'PAR', 'NW-2 incombustible, pulsadores y extintor junto a P-1; PS-1 condicional.')
    r('COC-NEW-06', 'AJ' if F.plan_pdf_stale or any(not s['built'] for s in F.sheets) else 'OK',
      'Regenerar el juego de láminas desde v' + F.ver if (F.plan_pdf_stale or any(not s['built'] for s in F.sheets)) else 'Láminas generadas desde v' + F.ver)
    r('COC-11a', 'OK' if F.fuel_d and all(v >= 0.915 for v in F.fuel_d.values()) else 'PAR', 'Distancias del rack medidas; cenizas por la ruta indicada.')
    r('COC-NEW-01', 'OK', 'Panel divisorio entre campanas en Y 2.42 (nota de HD-1).')
    r('COC-NEW-02', 'OK', 'Espacio técnico de 0.15 m detrás de la línea a gas.')
    r('COC-NEW-07', 'OK' if F.lay.get('remove_items') else 'AJ', 'Campana de Marna\'s marcada A RETIRAR (A-102).')
    r('COC-NEW-03', 'SIT', 'Interconexión con la alarma del edificio.')
    r('COC-NEW-05', 'SIT', 'Rociadores del edificio.')
    r('X-01', 'OK' if has('chem_cabinet') else 'AJ', 'Gabinete de químicos W7.')
    r('X-02', 'OK' if has('handwash_cold') and has('handwash_bar') else 'PAR', 'Lavamanos A8 (cold prep) y C5 (barra).')
    r('X-03', 'OK' if 'P-2' in F.op else 'PAR', 'P-2 de cierre automático en D-P1-old.')
    r('X-04', 'PAR', 'Recepción fuera de horario por D-ENT; PS-1 condicional.')
    r('X-05', 'AJ' if F.plan_pdf_stale else 'OK', 'Coherencia láminas / datos: ' + ('regenerar PNG/PDF' if F.plan_pdf_stale else 'láminas regeneradas'))
    r('X-06', 'OK', 'Rótulos "Prohibido fumar" especificados (02 §15).')
    r('X-07', 'OK', 'Espacio por trabajador suficiente (auditoría).')
    return R_


AUD2CODE = {'cumple': 'OK', 'no_cumple': 'AJ', 'riesgo': 'PAR', 'falta_documento': 'DOC', 'no_determinable': 'SIT'}
AUD_ES = {'cumple': 'cumple', 'no_cumple': 'no cumple', 'riesgo': 'riesgo', 'falta_documento': 'falta documento', 'no_determinable': 'no determinable'}


def doc_05(F):
    L = [header(F, '05', 'Checklist normativo',
                'Requisito → fuente → estado en el anteproyecto v' + F.ver + ' → lo que el profesional responsable todavía debe verificar. '
                'El estado se calcula sobre los datos actuales (`data/*.json`), no sobre la auditoría original.')]
    res = F.research or {}
    reqs = [(dom, r) for dom, dd in res.items() for r in dd.get('requirements', [])]
    L.append('## 1. Advertencia sobre las fuentes\n\n')
    if reqs:
        conf = {}
        for _, r in reqs:
            conf[r.get('confidence') or '—'] = conf.get(r.get('confidence') or '—', 0) + 1
        prim = sum(1 for _, r in reqs if r.get('verified_from_primary'))
        L.append(f'- {len(reqs)} requisitos investigados; **{prim} verificados en texto primario**. Confianza: '
                 + ', '.join(f'{k} {v}' for k, v in sorted(conf.items())) + '.\n')
        L.append('- La investigación solo pudo leer resúmenes y fragmentos de buscador: los portales de texto primario (SCIJ/pgrweb, '
                 'bomberos.go.cr, cfia.or.cr, nfpa.org) no fueron accesibles. Numeración de artículos y ediciones: **verificar**.\n')
        L.append('- Antes de firmar, el profesional debe revisar en SCIJ y en Bomberos al menos: DE 37308-S, DE 26831-MP arts. 140–148, '
                 'CIHSE Tabla 5.3 (edición vigente), RNPCI 2023 y la edición NFPA adoptada, Reglamento de Construcciones INVU '
                 '(artículos de egreso, altura, chimeneas y 36 m a servicios sanitarios).\n')
        L.append(f'- Fuente de este checklist: {F.norm_source}.\n')
    else:
        L.append('> La investigación normativa (`research.json`) no está disponible: ejecutar con `--research` / `--audit` para '
                 'completar este documento.\n')
    rr = rules(F)
    aud = {}
    verdict = {}
    for dd in (F.audit or {}).get('domains', []):
        for f in dd.get('findings', []):
            aud.setdefault(f['req_id'], f)
    for v in ((F.audit or {}).get('verification') or {}).get('verdicts', []):
        verdict[v['key'].split(':', 1)[-1]] = v['verdict']
    counts = {}
    blocks = []
    for dom, title in DOMAINS.items():
        dd = res.get(dom)
        if not dd:
            continue
        rows = []
        for r in dd.get('requirements', []):
            rid = r['id']
            f = aud.get(rid, {})
            code, estado, verif = rr.get(rid) or (AUD2CODE.get(f.get('status'), 'INF'),
                                                   'Estado según la auditoría preliminar (v2): ' + AUD_ES.get(f.get('status'), '—') + ' — revisar en v3.', None)
            counts.setdefault(dom, {})
            counts[dom][code] = counts[dom].get(code, 0) + 1
            title_r = (f.get('topic') or first_sentence(r.get('requirement'), 120)).rstrip(':')
            src = f"{cut(r.get('source_ref'), 170)} · {r.get('authority', '')} · conf. {r.get('confidence', '—')}" + (
                '' if r.get('verified_from_primary') else ' · secundaria')
            ver = verif or ('Confirmar en el texto vigente: ' + cut(r.get('criterion'), 170))
            rows.append((nw(rid), title_r, src, f'{badge(code)} {estado}', ver))
        blocks.append((title, rows))
    L.append('\n## 2. Estados\n\n' + table(['Estado', 'Significado'], [(badge(k), v) for k, v in ST_HELP.items()]))
    if counts:
        codes = [k for k in ST if any(k in c for c in counts.values())]
        rows = [(DOMAINS[d].split(' (')[0], *[c.get(k, '') for k in codes], sum(c.values())) for d, c in counts.items()]
        tot = [sum(c.get(k, 0) for c in counts.values()) for k in codes]
        rows.append(('**Total**', *tot, sum(tot)))
        L.append('\nResumen por dominio:\n\n' + table(['Dominio', *[badge(k) for k in codes], 'Total'], rows, 'l' + 'r' * (len(codes) + 1)))
    ed = [(DOMAINS.get(dom, dom).split(' (')[0], cut_sent(dd.get('adopted_editions', ''), 1400)) for dom, dd in res.items() if dd.get('adopted_editions')]
    sec = 3
    if ed:
        L.append(f'\n## {sec}. Ediciones y normas vigentes según la investigación\n\n')
        L.append('Texto de la investigación (fuentes secundarias, a septiembre de 2026): confirmar cada edición antes de firmar.\n\n')
        L.append(table(['Dominio', 'Ediciones adoptadas (según resúmenes de búsqueda)'], ed))
        sec += 1
    for title, rows in blocks:
        L.append(f'\n## {sec}. {title}\n\n')
        L.append(table(['ID', 'Requisito', 'Fuente (verificar)', 'Estado en el anteproyecto', 'Qué debe verificar el profesional'], rows))
        sec += 1
    # audit extras
    rid_set = {r['id'] for _, r in reqs}
    ex = extra_rules(F)
    rows = []
    for dd in (F.audit or {}).get('domains', []):
        for f in dd.get('findings', []):
            if f['req_id'] in rid_set:
                continue
            code, estado = ex.get(f['req_id']) or (AUD2CODE.get(f.get('status'), 'INF'), 'revisar en v3')
            v = verdict.get(f['req_id'])
            rows.append((nw(f['req_id']), cut(re.sub(r'^\(Omitido\)\s*', '', f.get('topic', '')), 110), f"{AUD_ES.get(f.get('status'), f.get('status'))} · {f.get('severity', '')}"
                         + (f' · verif.: {v}' if v else ''), f'{badge(code)} {estado}', cut(f.get('fix', ''), 200)))
    if rows:
        L.append(f'\n## {sec}. Hallazgos adicionales de la auditoría preliminar y su estado en v{F.ver}\n\n')
        L.append('La auditoría (medición automática sobre el plano + verificación adversarial) se hizo sobre la versión anterior; muchas '
                 'correcciones ya están incorporadas en v' + F.ver + '. La última columna es la recomendación original.\n\n')
        L.append(table(['ID', 'Tema', 'Auditoría (v2)', f'Estado en v{F.ver}', 'Recomendación original de la auditoría (v2)'], rows))
        sec += 1
    miss = ((F.audit or {}).get('verification') or {}).get('missing', [])
    if miss:
        L.append(f'\n## {sec}. Temas que la verificación señaló como no cubiertos\n\n')
        L.append('Texto original de la verificación (revisar vigencia en v' + F.ver + '):\n\n' + bullets(cut(m, 420) for m in miss))
        sec += 1
    # sources
    srcs = []
    seen = set()
    for dom, dd in res.items():
        for s in dd.get('sources', []):
            k = s.get('url') or s.get('title')
            if k in seen:
                continue
            seen.add(k)
            srcs.append((DOMAINS.get(dom, dom).split(' (')[0], s.get('title', ''), s.get('date_or_edition', '') or '—', 'no' if not s.get('fetched') else 'sí'))
    if srcs:
        L.append(f'\n## {sec}. Fuentes consultadas (vía buscador)\n\n')
        L.append(table(['Dominio', 'Fuente', 'Edición / fecha', 'Texto leído'], srcs))
        L.append('\nLas URL completas están en `docs/permisos/' + CACHE_NAME + '`.\n')
    return ''.join(L)


# ------------------------------------------------------------------------------------------------ 06 trámites


def doc_06(F):
    L = [header(F, '06', 'Trámites y permisos',
                'Paso a paso para pasar del anteproyecto a la apertura: quién hace cada trámite, ante qué institución y con qué '
                'documentos. Requisitos tomados de fuentes secundarias (sitios municipales e institucionales vistos por buscador): '
                '**confirmar los requisitos vigentes con cada institución** antes de iniciar.')]
    L.append('## 1. Resumen\n\n')
    steps = [
        ('1', 'Aprobación del condominio y del propietario / arrendador', 'Administración / asamblea; propietario registral', 'Cliente', 'Antes del APC'),
        ('2', 'Certificado de uso de suelo', 'Municipalidad de Santa Ana', 'Cliente', 'Antes del APC y de la patente'),
        ('3', 'Levantamiento en sitio y ajuste del anteproyecto', '—', 'Arquitecto', 'Antes de firmar'),
        ('4', 'Contratos de consultoría y planos constructivos firmados', 'CFIA (APC)', 'Arquitecto + ingenieros', 'Paralelo a 1–2'),
        ('5', 'Revisión institucional en el APC (remodelación)', 'CFIA, Ministerio de Salud (declaración jurada), Bomberos', 'Arquitecto', 'Con 1, 2 y 4 listos'),
        ('6', 'Licencia municipal de construcción', 'Municipalidad de Santa Ana (APC-M)', 'Arquitecto + cliente', 'Después de 5'),
        ('7', 'Póliza de riesgos del trabajo de la obra, bitácora digital y dirección técnica', 'INS · CFIA', 'Contratista · arquitecto', 'Antes de iniciar obras'),
        ('8', 'Obra, inspecciones y pruebas', 'Bomberos, municipalidad, proveedor de supresión', 'Contratista + director técnico', 'Durante la obra'),
        ('9', 'Informe técnico de la instalación de gas', 'Bomberos o profesional / inspector acreditado', 'Ing. mecánico / instalador', 'Al terminar el gas'),
        ('10', 'Permiso Sanitario de Funcionamiento (PSF)', 'Ministerio de Salud — Área Rectora de Santa Ana', 'Operador', 'Antes de abrir'),
        ('11', 'Patente municipal (licencia de actividad lucrativa)', 'Municipalidad de Santa Ana', 'Operador', 'Después de 10'),
        ('12', 'Licencia de expendio de bebidas alcohólicas clase C', 'Municipalidad de Santa Ana', 'Operador', 'Con / después de 11'),
        ('13', 'Permiso de rótulo', 'Municipalidad + condominio', 'Cliente', 'Antes de instalar el rótulo'),
        ('14', 'Arranque de operación', 'INS, CCSS, Hacienda, Salud', 'Operador', 'Antes de abrir'),
    ]
    L.append(table(['Paso', 'Trámite', 'Ante quién', 'Responsable', 'Cuándo'], steps, 'rllll'))
    doc = {
        '1': dict(
            ref='Ley 7933 Reguladora de la Propiedad en Condominio arts. 16 y 27 (reforma Ley 10229); reglamento interno; Ley 7527 (arrendamiento) — verificar',
            docs=['Carta de solicitud (documento 08) con el anteproyecto (láminas A-101…E-101, memoria 01 y especificaciones 02).',
                  'Autorización escrita del propietario registral o arrendador para remodelar y cambiar el uso (la patente también la pide).',
                  'Copia del reglamento del condominio y del manual de inquilinos (requisitos de campanas, grasas, gas, horarios, rótulos).'],
            notes=['Obras en elementos comunes o que los afectan requieren aprobación: cubierta y losa (ductos, ventiladores, chimenea), '
                   'ventana sur (PS-1), fachada y rótulos, conexión a la red de gas, uso de baños comunes y cuarto de basura.',
                   'Si el reglamento restringe el destino (café → restaurante con fuego sólido), el cambio de destino requiere ≥2/3 del valor (art. 27 reformado, verificar).',
                   'El cliente no tiene el plano del centro comercial: pedir a la administración el plano de conjunto con baños comunes, cuarto de '
                   'basura, acometidas (gas, electricidad, agua), cubierta y sistemas de protección contra incendios.']),
        '2': dict(ref='Municipalidad de Santa Ana — Usos de suelo; Plan Regulador (1991 y reformas / nuevo plan en adopción) — verificar',
                  docs=['Formulario en línea; número de finca filial (folio real) y plano catastrado.',
                        'Actividad: "restaurante con venta de bebidas alcohólicas" (clase C).'],
                  notes=['Lo exigen la licencia de construcción y la patente. Confirmar qué plan regulador rige al presentar.']),
        '3': dict(ref='—', docs=['Formulario 07 completo, fotos y medidas; fichas técnicas de equipos.'],
                  notes=['Actualizar `data/existing.json` / `data/layout.json` con lo medido y regenerar láminas y documentos.']),
        '4': dict(ref='Ley 833 art. 83; Reglamento de Contratación de Servicios de Consultoría del CFIA — verificar',
                  docs=['Contrato de consultoría registrado por cada profesional (arquitectura; mecánica: extracción, gas, hidrosanitario, supresión; '
                        'electricidad; estructural si hay penetraciones y soportes).',
                        'Planos constructivos firmados digitalmente: arquitectura (A-1xx…A-3xx), seguridad humana (A-104), mecánica (M-101/M-102 + '
                        'planta de cubierta), eléctrica (E-101), estructural si aplica; especificaciones y memorias de cálculo.'],
                  notes=['Es obra mayor: no aplica la boleta de obra menor (modifica sistemas eléctricos y mecánicos).']),
        '5': dict(ref='DE 36550-MP-MIVAH-S-MEIC reformado por DE 43318; RNPCI 2023 (Bomberos); DE 43318 declaración jurada Salud ≤300 m² — verificar',
                  docs=['Proyecto en APC modalidad REMODELACIÓN con estado existente (A-102) y propuesto.',
                        f'Declaración jurada de los profesionales ante Salud (área del local {n(F.area)} m² ≤ 300 m²; confirmar área tasada).',
                        'Formulario y memoria de Bomberos: lámina A-104 + memoria 03 + láminas de gas, extracción y supresión.',
                        'Uso de suelo, autorización del condominio y del propietario (pasos 1–2).'],
                  notes=['CFIA, Salud y Bomberos revisan en paralelo; las observaciones se atienden por reingreso.',
                         'La declaración jurada de Salud obliga a cumplir el DE 37308-S: resolver antes baños comunes (autorización), residuos y lavamanos.']),
        '6': dict(ref='Ley 833 art. 74; Municipalidad de Santa Ana — Permisos de construcción (APC-M) — verificar',
                  docs=['Planos aprobados en el APC; uso de suelo conforme; póliza de riesgos del trabajo de la obra (INS).',
                        'Propietario y solicitante al día con tributos municipales y CCSS; pago del impuesto de construcción (≈1 % del valor tasado).'],
                  notes=['Plazo reportado ≈15 días hábiles. No se puede iniciar la obra sin licencia.']),
        '7': dict(ref='Reglamento Especial de la Bitácora (CFIA); Ley 6727 / INS riesgos del trabajo — verificar',
                  docs=['Bitácora digital abierta en el APC (≈₡10 000 con la tasación).', 'Director técnico o inspector designado.',
                        'Póliza RT de los trabajadores de la obra.'],
                  notes=['La bitácora se cierra ≤30 días después de terminar y se custodia 10 años.']),
        '8': dict(ref='RNPCI 2023; NFPA 96 / 17A / 54 — verificar',
                  docs=['Pruebas: hermeticidad del gas, aceptación de la supresión (con corte de gas y energía), balance de extracción y reposición, '
                        'pruebas eléctricas, estanqueidad de desagües.', 'Certificados del proveedor de supresión y del instalador de gas.',
                        'Planos conforme a obra.'],
                  notes=['Horario de obras, acarreos y protección de áreas comunes según el reglamento del condominio (08).']),
        '9': dict(ref='DE 41150-MINAE-S y DE 41151-MINAE-S (RTCR 490:2017); RTCR 482:2015 — verificar',
                  docs=['Informe técnico de inspección de la instalación de gas (tubería, reguladores, conectores, artefactos, detector).'],
                  notes=['Se exige para el PSF a establecimientos con GLP; la red del centro comercial puede ser GLP o gas natural: '
                         f'{F.gas.get("source", "")}. Confirmar qué informe aplica.']),
        '10': dict(ref='DE 43432-S (PSF, Anexo 3 primera vez); DE 37308-S (servicios de alimentación) — verificar',
                   docs=['Declaración jurada (Anexo 3) del cumplimiento del DE 37308-S; clasificación por grupo de riesgo (CIIU 5610).',
                         'Informe técnico de gas (paso 9).', 'Autorización de uso de los baños comunes y del cuarto de basura (carta 08).'],
                   notes=['La inspección de Salud es posterior al permiso: la declaración debe ser veraz desde el primer día.',
                          'Personal manipulador de alimentos con capacitación / carné vigente (verificar requisito actual).']),
        '11': dict(ref='Municipalidad de Santa Ana — Licencia de actividad lucrativa — verificar',
                   docs=['Formulario único; cédulas del solicitante y del propietario; certificación literal de la propiedad; autorización del dueño registral.',
                         'Póliza RT (INS); CCSS al día; PSF; inscripción en Hacienda; uso de suelo conforme; tributos municipales al día.'],
                   notes=[]),
        '12': dict(ref='Ley 9047 art. 4 (clase C) y art. 9; Reglamento a la Ley 9047; Municipalidad de Santa Ana — verificar',
                   docs=['Formulario con firma autenticada; CCSS, póliza RT y FODESAF al día; patente (paso 11).',
                         f'Planta con {len(F.tables)} mesas y {F.seats} asientos, cocina equipada; menú con ≥10 opciones durante todo el horario.'],
                   notes=['Restricciones por zonificación y distancia (100 m de centros educativos, infantiles, de adultos mayores y de salud): '
                          'confirmar cómo se aplican a la clase C en un centro comercial.',
                          'Algunos reglamentos piden ≥8 mesas y ≥32 asientos y limitan banquetas de barra a 1/3 de las sillas (LAVA no tiene banquetas).']),
        '13': dict(ref='Municipalidad de Santa Ana — Instalación de rótulos; reglamento del condominio — verificar',
                   docs=['Formulario; personería jurídica (≤1 mes); croquis a escala con estructura y anclaje; montaje fotográfico en la fachada; '
                         'área del rótulo y frente del local; aprobación del condominio.'],
                   notes=['Circuito eléctrico propio del rótulo exterior (E-101).']),
        '14': dict(ref='INS, CCSS, Ministerio de Hacienda — verificar',
                   docs=['Póliza de riesgos del trabajo del personal; inscripción patronal (CCSS); inscripción tributaria.',
                         'Plan de emergencias integrado al del condominio; contratos de limpieza de ductos (mensual por combustible sólido) y '
                         'mantenimiento de supresión (semestral); control de plagas.'],
                   notes=[]),
    }
    L.append('\n## 2. Detalle por paso\n')
    for num, name, who_inst, who, when in steps:
        d = doc[num]
        L.append(f'\n### Paso {num}. {name}\n\n')
        L.append(f'**Ante quién:** {who_inst} · **Responsable:** {who} · **Cuándo:** {when}  \n**Referencia:** {d["ref"]}\n\n')
        L.append('Documentos:\n\n' + bullets(d['docs']))
        if d['notes']:
            L.append('\nNotas:\n\n' + bullets(d['notes']))
    L.append('\n## 3. Instituciones que revisan el proyecto\n\n')
    L.append(table(['Institución', 'Qué revisa', 'Documentos del paquete'], [
        ('CFIA (APC)', 'Responsabilidad profesional, contratos, juego completo de planos', '00, 01, 02, todas las láminas'),
        ('Ministerio de Salud', 'Declaración jurada (≤300 m²) de cumplimiento del DE 37308-S; luego el PSF', '01 §9, 02 §4/§11, A-106, M-101'),
        ('Bomberos', 'Seguridad humana, egreso, extintores, supresión, gas, extracción (RNPCI + NFPA)', '03, A-104, M-102, 04'),
        ('Municipalidad de Santa Ana', 'Uso de suelo, licencia de construcción, patente, licores, rótulo', '01, 06'),
        ('Condominio Terrazas Lindora', 'Obras en elementos comunes, servicios comunes, horarios, rótulos', '08'),
    ]))
    L.append('\n' + flags_block())
    return ''.join(L)


# ------------------------------------------------------------------------------------------------ 07 levantamiento


SCAN_KEYS = ('VERIFY', 'TBV', 'VERIFICAR', 'verificar en sitio', 'Confirmar en sitio')


GENERIC_KEYS = {'note', 'text', 'riser', 'fan', 'source', 'label', 'desc', 'use'}


def scan_verify(F):
    out = []
    seen = {}

    def walk(o, src, ctx, path):
        if isinstance(o, dict):
            c = o.get('id') or o.get('tag')
            for k, v in o.items():
                walk(v, src, c, path + (str(k),))
        elif isinstance(o, list):
            for v in o:
                walk(v, src, ctx, path)
        elif isinstance(o, str) and any(k in o for k in SCAN_KEYS):
            key = ' '.join(o.split())
            el = ctx or next((p for p in reversed(path) if p not in GENERIC_KEYS and not p.isdigit()), path[0] if path else src)
            if key in seen:
                i = seen[key]
                if el not in out[i][1].split(', '):
                    out[i] = (out[i][0], out[i][1] + ', ' + el, out[i][2])
                return
            seen[key] = len(out)
            out.append((src, el, key))
    walk(F.ex, 'existing.json', None, ())
    for k in ('demolish', 'new_walls', 'new_openings', 'remove_items', 'equipment', 'decor', 'life_safety', 'mep', 'structure_notes', 'notes'):
        walk(F.lay.get(k), 'layout.json', k, (k,))
    if F.mech:
        walk(F.mech.get('plumbing_fixtures'), 'mech_calcs.json', 'plumbing', ('plumbing',))
    if F.elec:
        for v in F.elec.get('verify_on_site', []):
            out.append(('elec_loads.json', 'eléctrico', v + ' — VERIFY ON SITE'))
    return out


def doc_07(F):
    L = [header(F, '07', 'Levantamiento en sitio',
                'Formulario para la visita del arquitecto. Reúne cada "VERIFY ON SITE" y "DIMENSION TO VERIFY" de los datos. '
                'Anotar lo medido, marcar ☐ si coincide con el anteproyecto y numerar las fotos. Con lo medido se actualizan '
                '`data/existing.json` / `data/layout.json` y se regeneran láminas y documentos.')]
    L.append('## A. Datos de la visita\n\n')
    L.append(table(['Campo', 'Dato'], [('Fecha / hora', BLANK), ('Profesional responsable / carné CFIA', BLANK), ('Acompañante de la administración', BLANK),
                                       ('Ingenieros presentes', BLANK), ('Equipo de medición (láser, cinta, cámara, detector de gas)', BLANK)]))

    def form(rows):
        return table(['#', 'Elemento', 'Anteproyecto', 'Medido / observado', 'OK', 'Foto'], [(i + 1, a, b, BLANK * 2, BOX, '') for i, (a, b) in enumerate(rows)], 'rlllcl')
    ax = (F.ex.get('meta') or {}).get('axes', {})
    dp = F.ex.get('dimensions_from_pdf') or {}
    strip = re.findall(r'\(([\d.]+) m\)', dp.get('interior_top_strip', ''))
    wl = re.findall(r'= ([\d.]+) m', dp.get('wing_length', ''))
    ws = re.findall(r'\(([\d.]+) m', dp.get('wing_south', ''))
    col = {c['id']: c.get('note', '') for c in F.ex.get('columns', [])}
    hd_top = (F.hood_lower + max(float(h.get('h') or 0) for h in F.hoods)) if (F.hoods and F.hood_lower) else None
    L.append('\n## B. Geometría, niveles y alturas\n\n')
    L.append(form([
        ('Largo interior de la franja principal (cara muro oeste a vitrina)', f'{strip[0]} m' if strip else '—'),
        ('Fondo interior de la franja principal', f'{strip[1]} m' if len(strip) > 1 else '—'),
        ('Ala de servicio: largo / ancho', f"{wl[0] if wl else '—'} / {ws[0] if ws else '—'} m"),
        ('Distancia entre ejes A–B / B–C', f"{n(ax.get('B', 0) - ax.get('A', 0))} / {n(ax.get('C', 0) - ax.get('B', 0))} m"),
        ('Área interior del local', f'{n(F.area)} m²'),
        ('Altura piso terminado – cielo existente', f'{n(F.ceiling)} m (supuesta)'),
        ('Altura piso terminado – fondo de losa / vigas', '≥3.40 m deseable para campanas y ductos'),
        ('Espesor de losa y tipo (sobre terreno / entrepiso)', 'supuesto en A-301 (no legible en el PDF)'),
        ('Espacio sobre las campanas hasta el cielo (ductos, collarines)',
         f'≈{n(F.ceiling - hd_top)} m (campana de {n(F.hood_lower)} a {n(hd_top)} m, supuesto)' if hd_top else '—'),
        ('Desnivel / umbral en D-ENT respecto del pasillo común', '≤0.02 m'),
        ('Columnas C-B1 y C-A2 (salientes)', f"{col.get('C-B1', '')} · {col.get('C-A2', '')}"),
        ('Nueva división NW-1 (cara cocina)', f'X = {n(F.part_x)} m desde el eje A'),
    ]))
    L.append('\n## C. Muros, vanos y elementos a demoler\n\n')
    rows = []
    for d in F.lay.get('demolish', []):
        w = F.exwall.get(d['id'], {})
        what = ('material, espesor, dintel y revisión estructural (condicional)' if d.get('conditional') or w.get('kind') == 'perimeter'
                else 'confirmar liviano, sin instalaciones embebidas')
        rows.append((f"{d['id']} — {what}", d.get('note', '')))
    for it in F.lay.get('remove_items', []):
        rows.append((f"{it['id']} — campana existente, collarines y ruta del ducto", it.get('label', '')))
    for did in ('D-DISH-old', 'D-P1-old', 'D-KB-old'):
        dd = F.exdoor.get(did)
        if dd:
            rows.append((f'{did} — {KIND_ES.get(dd.get("kind"), dd.get("kind"))}', sent(dd.get('note', ''), '¿Tiene antepecho o mostrador?' if did == 'D-DISH-old' else '')))
    for w in F.ex.get('walls', []):
        if any(k in str(w.get('note', '')) for k in ('VERIFY', 'VERIFICAR')):
            rows.append((f"{w['id']}", w.get('note', '')))
    rows.append(('Divisiones que se conservan (IP-P0a, IP-P1, IP-P2, IP-P3)', 'livianas 10 cm; sin instalaciones'))
    L.append(form(rows))
    L.append('\n## D. Ductos, shafts y cubierta\n\n')
    rows = [(f"{s['id']} — uso, sección, continuidad a cubierta, resistencia al fuego", s.get('note', '')) for s in F.ex.get('shafts', [])]
    for s in F.mep.get('exhaust', []):
        rows.append((f"{s['id']} ({s.get('serves')}) — ruta y remate", s.get('riser', '')))
    rows += [
        ('Riser existente de Marna\'s: material, calibre, soldaduras, cerramiento (inspección con video)', 'reutilizable solo si cumple NFPA 96'),
        ('Ubicación posible de ventiladores EXT-1, EXT-2, AR-1 en cubierta y su soporte', 'aprobación del condominio'),
        ('Distancia de las descargas a tomas de aire, ventanas, linderos y edificios vecinos', '≥3 m (NFPA 96 §7.8, verificar)'),
        ('Altura de edificios en un radio de 25 m (remate de chimenea, INVU por verificar)', '≥5 m sobre el más alto (por verificar)'),
        ('Toma de aire de reposición (AR-1): ubicación y distancia a descargas', '≥3 m de las descargas'),
    ]
    L.append(form(rows))
    L.append('\n## E. Agua potable y desagües\n\n')
    use = {w['id']: w['use'] for w in (F.mech or {}).get('wet_points_existing', [])}
    rows = [(f"{w['id']} {w.get('desc', '')} — diámetro, material, profundidad, pendiente, destino, funciona", use.get(w['id'], '—'))
            for w in F.ex.get('wet_points_existing', [])]
    rows += [('Acometida de agua fría, medidor y presión', 'entrada supuesta en ducto S3'),
             ('Colector sanitario del edificio y punto de conexión de GT-1', 'WP1'),
             ('Ventilación sanitaria existente', '—'),
             ('Posibilidad de sifones de piso nuevos (FD-1…3) según tipo de losa', 'depende de B (losa)')]
    L.append(form(rows))
    L.append('\n## F. Gas (red del centro comercial)\n\n')
    g = (F.mech or {}).get('gas', {})
    L.append(form([
        ('Tipo de gas (GLP / gas natural) y presión de suministro', F.gas.get('source', '')),
        ('Punto de entrega / acometida al local', F.gas.get('entry_note', '')),
        ('Ubicación del tanque / regulador / medidor de la red', '—'),
        ('Capacidad asignable al local', f"≥{n(g.get('total_kW_typ'), 1)} kW ({n(g.get('total_BTUh_typ'), 0)} BTU/h) típicos" if g else '—'),
        ('Ubicación de la llave de corte exterior (rotulada)', f"({n(F.gas.get('main_valve', [0, 0])[0])}, {n(F.gas.get('main_valve', [0, 0])[1])}) tentativa"),
        ('Ruta de la tubería sin atravesar sectores internos del edificio', 'muro norte (tentativa)'),
        ('Responsable del mantenimiento de la red y certificaciones', '—'),
    ]))
    L.append('\n## G. Electricidad\n\n')
    rows = [('Tensión y fases disponibles', (F.elec or {}).get('system_assumed', '120/208 V 3F (supuesto)')),
            ('Capacidad asignada al local / medidor', f"principal {(F.elec or {}).get('demand', {}).get('suggested', {}).get('main_A', '—')} A sugerido"),
            ('Tablero existente de Marna\'s: ubicación, capacidad, estado', '—'),
            ('Ruta de acometida hasta TE-1', f"TE-1 en X {n(F.mep.get('panel', {}).get('rect', [0])[0])}–{n(F.mep.get('panel', {}).get('rect', [0, 0, 0])[2])} (muro norte)"),
            ('Alarma del centro comercial: panel, protocolo, punto de conexión', 'señal de supresión'),
            ('Placas de equipos existentes a reutilizar (si hay)', '—')]
    rows += [(v, 'VERIFY ON SITE') for v in (F.elec or {}).get('verify_on_site', []) if v not in ('Tensión / fases disponibles y medidor', "Tablero existente de Marna's",
                                                                                                  'Alarma del C.C. para señales de supresión', 'Placas de equipos (TBV)',
                                                                                                  'Capacidad asignada al local por el C.C.', 'Ruta de acometida')]
    L.append(form(rows))
    L.append('\n## H. Fachada, puerta principal y pasillo común\n\n')
    L.append(form([
        ('D-ENT: ancho del vano, hojas, paso libre por hoja, herrajes', f"{n(F.dent.get('width'))} m; hojas {n(F.ls.get('exits', [{}])[0].get('leaf'))} hacia adentro"),
        ('Ancho del pasillo común frente a D-ENT y posibilidad de invertir el giro', 'giro hacia afuera sin invadir el pasillo'),
        ('Pasillo común abierto y a nivel hasta la vía pública', 'abierto (dato del cliente)'),
        ('Vitrinas GL-F1 / GL-F2 y ubicación del rótulo exterior', 'rótulo sobre fachada'),
        ('Terraza común (Marna\'s) — no forma parte de la propuesta', (F.ex.get('terrace_existing') or {}).get('note', '')),
    ]))
    L.append('\n## I. Ventana sur y puerta de servicio condicional PS-1\n\n')
    ps1 = F.op.get('PS-1', {})
    L.append(form([
        ('GL-W1: qué hay detrás, altura de antepecho, estructura', next((gg.get('note', '') for gg in F.ex.get('glazing', []) if gg['id'] == 'GL-W1'), '')),
        ('Pasillo sur: ¿es parte de la salida o descarga de la escalera?', 'si lo es, puerta cortafuego autocerrante o no se permite'),
        ('Puerta de escalera D-STAIR-S y su barrido', F.exdoor.get('D-STAIR-S', {}).get('note', '')),
        ('Viabilidad del vano PS-1 (0.90) y recorte de EW-S2 (9.5 cm)', ps1.get('note', '')),
        ('Dintel y revisión estructural', 'ingeniero estructural'),
    ]))
    L.append('\n## J. Servicios sanitarios comunes\n\n')
    L.append(form([
        ('Ubicación de la batería común (H / M / accesible)', 'uso de clientes y personal (dato del cliente)'),
        ('Recorrido medido desde D-ENT hasta la puerta de los baños', f"≤{n(F.restroom_budget, 1)} m" if F.restroom_budget else '—'),
        ('Recorrido desde el punto más lejano del local (incluye el recorrido interno)',
         f"{n(F.far_int[0])} m interno ({F.far_int[1]}) + pasillo ≤36 m (INVU, por confirmar)" if F.far_int else '≤36 m'),
        ('Piezas: inodoros / orinales / lavatorios por sexo', 'CIHSE Tabla 5.3 con el aforo del condominio + 49'),
        ('Cubículo accesible: medidas, puerta 0.90 hacia afuera, barras', '≥2.25 × 1.55 m (art. 143)'),
        ('Horario de apertura y control de acceso', 'todo el horario de LAVA'),
        ('Lavamanos con jabón, toallas desechables, ventilación', 'DE 37308-S'),
    ]))
    L.append('\n## K. Residuos, cenizas y abastecimiento\n\n')
    L.append(form([
        ('Cuarto de basura del centro comercial: ubicación, horario, separación', 'retiro diario fuera de horario'),
        ('Punto exterior para cenizas (contenedor metálico con tapa)', 'acordar con la administración'),
        ('Ruta y horario de recepción de mercadería y leña', 'fuera de horario por D-ENT o PS-1'),
        ('Almacenamiento externo de leña (el local guarda solo un día)', '—'),
    ]))
    L.append('\n## L. Protección contra incendios del edificio\n\n')
    L.append(form([
        ('Rociadores automáticos en el local o el edificio (tipo, cabezas existentes)', F.ls.get('sprinklers', '')),
        ('Sistema de detección y alarma NFPA 72 (panel, dispositivos en el local)', 'integración de supresión'),
        ('Hidrantes / gabinetes de mangueras / extintores comunes', '—'),
        ('Plan de emergencias y punto de reunión del condominio', '—'),
        ('Resistencia al fuego de muros colindantes (escalera, vecinos)', 'sin penetraciones nuevas en la escalera'),
    ]))
    L.append(f'\n## M. Equipos — {FLAG_DIM}\n\n')
    L.append('Completar con la ficha técnica del equipo elegido (frente × fondo × alto, potencia, gas, listado).\n\n')
    L.append(table(['Tag', 'Equipo', 'Anteproyecto (m)', 'Ficha: medidas', 'Potencia / gas', 'Listado (UL/ETL/NSF)', 'OK'],
                   [(e['id'], e.get('label'), dims_str(e, star=False), BLANK, BLANK, BLANK, BOX) for e in F.tbv], 'lllllll'))
    L.append('\n## N. Observaciones, croquis y fotos\n\n')
    L.append(table(['Foto N.°', 'Descripción', 'Observación'], [('', '', '')] * 6))
    L.append('\n\nFirma del profesional: ' + BLANK + BLANK + '    Fecha: ' + BLANK + '\n\n')
    items = scan_verify(F)
    L.append(f'\n## Anexo. Todas las menciones de verificación en los datos ({len(items)})\n\n')
    L.append('Lista generada automáticamente (VERIFY / TBV / verificar) para que nada quede fuera del formulario.\n\n')
    L.append(table(['#', 'Archivo', 'Elemento', 'Texto', 'Revisado'], [(i + 1, s, c, cut(t, 300), BOX) for i, (s, c, t) in enumerate(items)], 'rlllc'))
    return ''.join(L)


# ------------------------------------------------------------------------------------------------ 08 carta


def doc_08(F):
    g = (F.mech or {}).get('gas', {})
    e1, e2 = F.exh('EXT-1') or {}, F.exh('EXT-2') or {}
    mua = (F.mech or {}).get('makeup_air', {})
    dm = (F.elec or {}).get('demand', {})
    ps1 = F.op.get('PS-1', {})
    L = [f'# 08 · Carta a la administración del condominio\n\n'
         f'**{PROJECT}** — {SITE}  \nModelo de carta · anteproyecto v{F.ver} · {F.date}\n\n'
         '> **MODELO** — completar los datos entre corchetes, revisar con el cliente y adjuntar el anteproyecto. Las cifras vienen de los '
         f'datos del proyecto y son **PRELIMINARES** ({VALIDAR}).\n\n'
         '---\n\n'
         'Santa Ana, [día] de [mes] de [año]\n\n'
         'Señores  \n**Administración del Condominio Centro Comercial Terrazas Lindora**  \n[Nombre del administrador]  \nPresente\n\n'
         "**Asunto:** Solicitud de aprobación de obras de remodelación y de condiciones de operación — local [N.°] (ex-Marna's), "
         'finca filial [N.°]\n\n'
         'Estimados señores:\n\n'
         f'Por este medio, [nombre del arrendatario / sociedad], cédula [N.°], en calidad de [propietario / arrendatario] del local [N.°] '
         f"(antes Marna's), les informamos que proyectamos instalar el restaurante **{PROJECT}**: restaurante de parrilla y ahumados con "
         f'servicio a la mesa, {F.seats} asientos, capacidad máxima de **{F.declared} personas** (clientes y personal) y venta de bebidas '
         'alcohólicas con licencia municipal clase C. Adjuntamos el anteproyecto (láminas A-101 a E-101, memoria descriptiva y '
         'especificaciones), que será completado y firmado por profesionales incorporados al CFIA.\n\n'
         'Conforme al reglamento del condominio, solicitamos respetuosamente su aprobación o criterio escrito sobre los siguientes puntos:\n\n']
    items = []
    demo = ', '.join(d['id'] for d in F.lay.get('demolish', []) if not d.get('conditional'))
    items.append(('Obras interiores',
                  f"Demolición de divisiones livianas interiores ({demo}); nueva división cocina/salón ({F.nw.get('NW-1', {}).get('short', '').lower()}, "
                  f"NW-1) y panel térmico NW-2; puertas P-1 y P-2; retiro de la campana existente; acabados, instalaciones eléctricas, "
                  'hidrosanitarias y de gas dentro del local. No se modifican columnas, muros perimetrales, escalera ni ductos del edificio. '
                  'Solicitamos además la información técnica disponible del edificio: planos estructurales, de instalaciones y de protección '
                  'contra incendios, y el plano de conjunto del centro comercial.'))
    items.append(('Uso de los servicios sanitarios comunes',
                  'Autorización escrita para que **clientes y personal** de LAVA usen los servicios sanitarios comunes del centro comercial '
                  '(hombres, mujeres y accesible) durante todo nuestro horario de operación. Les pedimos indicar la ubicación, la cantidad de '
                  'piezas y el horario, porque el Ministerio de Salud y el CFIA requieren demostrarlo documentalmente (capacidad según el CIHSE '
                  f'con nuestro aforo de {F.declared} personas, accesibilidad Ley 7600 y distancia de recorrido).'))
    items.append(('Cuarto de basura y cenizas',
                  'Uso del cuarto de basura del centro comercial con retiro diario fuera de horario y separación de residuos (orgánicos, '
                  'valorizables, ordinarios), y un punto exterior autorizado para depositar cenizas frías en contenedor metálico con tapa.'))
    items.append(('Conexión a la red de gas del centro comercial',
                  'Autorización y condiciones técnicas para conectar el local a la red de gas: tipo de gas (GLP o natural), presión, punto de '
                  f"entrega y medición, capacidad asignable (consumo típico estimado ≈{n(g.get('total_kW_typ'), 1)} kW, "
                  f"{nint(g.get('total_BTUh_typ'))} BTU/h, para cocina de 4 quemadores, plancha y 2 freidoras), ubicación de la llave de corte "
                  'exterior, ruta de la tubería y responsable del mantenimiento y las certificaciones. No usaremos cilindros en el local.' if g else
                  'Autorización y condiciones técnicas para conectar el local a la red de gas del centro comercial (tipo, presión, capacidad, '
                  'punto de entrega, llave de corte exterior). No usaremos cilindros en el local.'))
    items.append(('Penetraciones de losa y cubierta, ventiladores y chimenea',
                  f"Instalación de: extractor EXT-1 de la campana a gas (≈{n(e1.get('Q_Ls'), 0)} L/s; se propone reutilizar el ducto existente "
                  f"de Marna's si la inspección lo aprueba); extractor EXT-2 independiente para la parrilla de carbón/leña (≈{n(e2.get('Q_Ls'), 0)} L/s, "
                  'ducto nuevo con arrestachispas); chimenea propia del ahumador (smoker); ventilador de aire de reposición AR-1 '
                  f"(≈{n(mua.get('design_Q_Ls'), 0)} L/s). Requieren penetraciones de losa y cubierta, soportes en cubierta con revisión "
                  'estructural, y descargas a distancia de tomas de aire y vecinos según NFPA 96. Les pedimos indicar las zonas de cubierta '
                  'disponibles, los ductos existentes que podríamos usar y cualquier requisito sobre humo y olores.'))
    items.append(('Puerta de servicio PS-1 (condicional)',
                  f"Apertura de una puerta de servicio de {n(ps1.get('width'))} m en parte de la ventana sur del local hacia el pasillo del "
                  'edificio, para recepción de mercadería, leña y retiro de basura fuera de horario, y como segunda salida del personal. '
                  'Requiere revisión estructural y confirmar que el pasillo no es parte de la salida de la escalera. Si no es posible, '
                  'operaremos por la entrada principal fuera de horario.'))
    items.append(('Sentido de giro de la puerta principal',
                  f"Autorización para invertir el giro de las hojas de la puerta principal ({n(F.dent.get('width'))} m) para que abran hacia "
                  'afuera sin invadir el paso del pasillo común (recomendación de seguridad humana).'))
    items.append(('Rotulación',
                  'Aprobación del rótulo exterior en fachada y del rótulo interior retroiluminado visible desde el pasillo, según el '
                  'reglamento del condominio (el permiso municipal se tramita por separado).'))
    items.append(('Horario y condiciones de obra',
                  'Horario autorizado para trabajos ruidosos y demoliciones, acarreo de materiales y escombros, protección de áreas comunes, '
                  'cortes programados de servicios, acceso del contratista y depósito de garantía si aplica.'))
    items.append(('Servicios del edificio',
                  'Capacidad eléctrica asignable al local y punto de acometida'
                  + (f" (demanda preliminar ≈{n(dm.get('design_VA', 0) / 1000, 1)} kVA, sistema supuesto {(F.elec or {}).get('system_assumed', '').replace(' (VERIFY)', '')})" if dm else '')
                  + '; acometida y medidor de agua; colector sanitario para la trampa de grasa; existencia de rociadores y alarma contra '
                  'incendios, y la forma de integrar la señal de nuestros sistemas de supresión.'))
    items.append(('Venta de bebidas alcohólicas',
                  'Confirmar que el reglamento del condominio no restringe la venta de bebidas alcohólicas en un restaurante (licencia clase C) '
                  'y si existen horarios u otras condiciones.'))
    for i, (t, s) in enumerate(items):
        L.append(f'{i + 1}. **{t}.** {s}\n')
    L.append('\nQuedamos atentos a sus observaciones y a los requisitos adicionales del reglamento o del manual de inquilinos. Con gusto '
             'coordinamos una visita al local con el arquitecto responsable.\n\n'
             'Atentamente,\n\n\n'
             f'{BLANK}{BLANK}  \n[Nombre] — [cargo / representante legal]  \n[Sociedad], cédula [N.°]  \nTeléfono [ ] · correo [ ]\n\n'
             '**Adjuntos:** anteproyecto (láminas A-101 a E-101), 01 Memoria descriptiva, 02 Especificaciones técnicas.\n\n'
             '---\n\n'
             f'**Recibido por la administración:** {BLANK}{BLANK} · Fecha: {BLANK} · Firma y sello: {BLANK}\n')
    return ''.join(L)


# ------------------------------------------------------------------------------------------------ PDF


CSS = r"""
@page { size: A4; margin: 17mm 15mm 17mm 15mm; }
:root { --ink:#1c1a17; --muted:#6b645a; --line:#dcd6cc; --dark:#141210; --cream:#ece5d8; --accent:#ff7a1a; --accent-d:#a84a00; --zebra:#f7f4ef; }
html { font-family: Figtree, 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif; font-size: 9.1pt; color: var(--ink); line-height: 1.42; }
body { margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
section.doc { break-before: page; }
section.doc:first-of-type { break-before: auto; }
h1 { font-family: 'Big Shoulders Display', 'Liberation Sans', sans-serif; font-weight: 800; font-size: 25pt; line-height: 1.05; margin: 0 0 5pt;
     padding-bottom: 5pt; border-bottom: 3pt solid var(--accent); letter-spacing: .2pt; }
h2 { font-family: 'Big Shoulders Display', 'Liberation Sans', sans-serif; font-weight: 800; font-size: 14pt; margin: 13pt 0 4pt; color: var(--dark);
     break-after: avoid; letter-spacing: .2pt; }
h3 { font-size: 10.2pt; font-weight: 800; margin: 10pt 0 3pt; break-after: avoid; }
p { margin: 0 0 5pt; }
h1 + p { color: var(--muted); font-size: 8.4pt; }
blockquote { margin: 5pt 0 8pt; padding: 5pt 9pt; background: #fff3e8; border-left: 3.5pt solid var(--accent); break-inside: avoid; }
blockquote p { margin: 0; }
ul, ol { margin: 2pt 0 6pt 0; padding-left: 15pt; }
li { margin: 0 0 2.2pt; }
table { width: auto; min-width: 55%; max-width: 100%; border-collapse: collapse; margin: 4pt 0 9pt; font-size: 7.5pt; line-height: 1.3; }
thead { display: table-header-group; }
th { background: var(--dark); color: #fff; text-align: left; font-weight: 700; padding: 3pt 4pt; vertical-align: bottom; }
td { padding: 2.4pt 4pt; border-bottom: .5pt solid var(--line); vertical-align: top; overflow-wrap: break-word; }
td code { white-space: nowrap; }
tbody tr:nth-child(even) td { background: var(--zebra); }
tr { break-inside: avoid; }
code { font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace; font-size: .86em; background: #f1ece4; padding: 0 2pt; border-radius: 2pt; }
pre { background: #f1ece4; padding: 6pt 8pt; border-radius: 3pt; font-size: 7.6pt; white-space: pre-wrap; }
pre code { background: none; padding: 0; }
hr { border: 0; border-top: .6pt solid var(--line); margin: 10pt 0; }
strong { font-weight: 800; }
.st { display: inline-block; font-weight: 800; font-size: 6.3pt; padding: .4pt 3pt; border-radius: 2pt; white-space: nowrap; letter-spacing: .2pt; margin-right: 2pt; }
.st-ok { background: #dcefdc; color: #1d6a2c; } .st-par { background: #fff0cf; color: #8a5a00; } .st-ing { background: #e2e9f8; color: #1d4a9a; }
.st-doc { background: #ece6f5; color: #5a3a8e; } .st-sit { background: #fde2cf; color: #a24300; } .st-aj { background: #f9d6d6; color: #a1101d; }
.nw { white-space: nowrap; }
.st-na { background: #eeeeee; color: #555; } .st-inf { background: #eeeeee; color: #333; }
section.d08 p { font-size: 9.6pt; line-height: 1.5; }
section.d08 ol li { margin-bottom: 4pt; font-size: 9.2pt; }
"""

COVER_CSS = r"""
@page { size: A4; margin: 0; }
html, body { margin: 0; padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.cover { width: 210mm; height: 297mm; box-sizing: border-box; padding: 22mm 20mm 16mm; background: #141210; color: #ece5d8;
         font-family: Figtree, 'DejaVu Sans', Arial, sans-serif; position: relative; overflow: hidden; }
.brand { font-family: 'Big Shoulders Display', sans-serif; font-weight: 800; font-size: 74pt; letter-spacing: 6pt; line-height: .9; color: #ece5d8; }
.tag { color: #ff7a1a; font-weight: 700; letter-spacing: 3pt; font-size: 10.5pt; margin-top: 4pt; }
.loc { color: #cfc6b8; font-size: 10pt; margin-top: 10pt; }
.title { font-family: 'Big Shoulders Display', sans-serif; font-weight: 800; font-size: 36pt; line-height: 1.02; margin-top: 30mm; color: #fff; }
.sub { font-size: 12pt; color: #cfc6b8; margin-top: 6pt; }
.status { margin-top: 12mm; border: 1.2pt solid #ff7a1a; color: #ff7a1a; font-weight: 800; padding: 7pt 10pt; font-size: 9.5pt; letter-spacing: .6pt; }
.status span { display: block; color: #ece5d8; font-weight: 400; letter-spacing: 0; margin-top: 3pt; font-size: 8.6pt; }
table.toc { width: 100%; border-collapse: collapse; margin-top: 10mm; font-size: 10pt; }
table.toc td { padding: 4.2pt 0; border-bottom: .5pt solid #3a352f; color: #ece5d8; }
table.toc td.n { width: 12mm; color: #ff7a1a; font-weight: 800; font-family: 'JetBrains Mono', monospace; }
table.toc td.p { width: 16mm; text-align: right; font-family: 'JetBrains Mono', monospace; color: #b9b0a2; }
.foot { position: absolute; left: 20mm; right: 20mm; bottom: 14mm; font-size: 7.8pt; color: #b9b0a2; line-height: 1.5; }
.foot b { color: #ece5d8; }
.bar { position: absolute; left: 0; top: 0; width: 6mm; height: 297mm; background: #ff7a1a; }
"""

NODE_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const jobs = JSON.parse(process.env.LAVA_PDF_JOBS);
  const browser = await chromium.launch();
  for (const j of jobs) {
    const page = await browser.newPage();
    await page.goto('file://' + j.html, { waitUntil: 'load' });
    await page.evaluate(async () => { await document.fonts.ready; });
    const opt = { path: j.pdf, printBackground: true, preferCSSPageSize: true };
    if (j.footer) { opt.displayHeaderFooter = true; opt.headerTemplate = j.header || '<span></span>'; opt.footerTemplate = j.footer; }
    await page.pdf(opt);
    await page.close();
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
"""


def font_css():
    fd = os.path.join(ROOT, 'tools', 'fonts')
    p = os.path.join(fd, 'fonts.css')
    if not os.path.exists(p):
        return ''
    css = open(p, encoding='utf-8').read()

    def rep(m):
        fn = m.group(1)
        fp = os.path.join(fd, fn)
        if not os.path.exists(fp):
            return m.group(0)
        return 'url(data:font/woff2;base64,' + base64.b64encode(open(fp, 'rb').read()).decode() + ')'
    return re.sub(r'url\(([^)]+\.woff2)\)', rep, css)


def md_to_html(md_text):
    try:
        import markdown
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'markdown'], check=False)
        import markdown
    return markdown.markdown(md_text, extensions=['tables', 'sane_lists', 'attr_list', 'md_in_html', 'fenced_code', 'toc'])


def run_node(jobs):
    npm_root = subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, NODE_PATH=npm_root, LAVA_PDF_JOBS=json.dumps(jobs))
    subprocess.run(['node', '-e', NODE_JS], check=True, env=env)


def _fitz():
    try:
        import pymupdf as fz
    except ImportError:
        import fitz as fz
    return fz


def heading_pages(pdf_path, docs_h2):
    """Find the page of each document title (h1, large font) and its h2 headings in the body PDF."""
    fitz = _fitz()
    doc = fitz.open(pdf_path)
    lines = []
    for pi, page in enumerate(doc):
        for b in page.get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                txt = ''.join(s['text'] for s in ln['spans']).strip()
                size = max((s['size'] for s in ln['spans']), default=0)
                if txt:
                    lines.append((pi, size, txt, ln['bbox'][1]))
    doc.close()
    h1 = {}
    for pi, size, txt, _ in lines:
        m = re.match(r'^(0\d) · ', txt)
        if size > 18 and m and m.group(1) not in h1:
            h1[m.group(1)] = pi
    toc = []
    nums = [d[0] for d in DOCS]
    for k, num in enumerate(nums):
        if num not in h1:
            continue
        start = h1[num]
        end = h1.get(nums[k + 1], 10 ** 6) if k + 1 < len(nums) else 10 ** 6
        title = next(t for nn, _, t in DOCS if nn == num)
        toc.append([1, f'{num} · {title}', start])
        h2l = [(pi, txt, y, size) for pi, size, txt, y in lines if 12.5 < size < 16 and start <= pi <= end]
        merged = []
        for pi, txt, y, size in h2l:
            if merged and merged[-1][0] == pi and 0 < y - merged[-1][2] < size * 1.6:
                merged[-1] = (pi, merged[-1][1] + ' ' + txt, y)
            else:
                merged.append((pi, txt, y))
        want = docs_h2.get(num, [])
        wi = 0
        for pi, txt, _ in merged:
            if wi < len(want) and txt.replace(' ', '')[:18] == want[wi].replace(' ', '')[:18]:
                toc.append([2, want[wi], pi])
                wi += 1
    return h1, toc


def cover_html(F, pages, fcss):
    rows = []
    for num, fn, title in DOCS:
        p = pages.get(num)
        rows.append(f'<tr><td class="n">{num}</td><td>{title}</td><td class="p">{"" if p is None else p + 1}</td></tr>')
    sheets = ' · '.join(sheet_tag(s['id']) for s in F.sheets)
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><style>{fcss}</style><style>{COVER_CSS}</style></head><body>'
            f'<div class="cover"><div class="bar"></div>'
            f'<div class="brand">LΛVΛ</div><div class="tag">CONTEMPORARY FIRE &amp; BBQ</div>'
            f"<div class=\"loc\">Local ex-Marna's · Terrazas Lindora · Santa Ana, Costa Rica</div>"
            f'<div class="title">Documentos para permiso</div>'
            f'<div class="sub">Anteproyecto listo para revisión y firma del profesional responsable (CFIA)</div>'
            f'<div class="status">ANTEPROYECTO / PRELIMINAR<span>Todo lo indicado es a validar por el profesional responsable y las ingenierías. '
            f'Las citas normativas provienen mayormente de fuentes secundarias (verificar).</span></div>'
            f'<table class="toc">{"".join(rows)}</table>'
            f'<div class="foot"><b>Anteproyecto v{F.ver} · {F.date}</b> · generado desde data/*.json con tools/permit_docs.py<br>'
            f'Láminas A2 1:50: {sheets}<br>{FLAG_EXT} · {FLAG_SMOKER} · {FLAG_DIM} · {FLAG_SITE}</div>'
            f'</div></body></html>')


def build_pdf(F, mds, out_dir):
    fitz = _fitz()
    fcss = font_css()
    sections = []
    docs_h2 = {}
    for num, fn, title in DOCS:
        md = mds[fn]
        docs_h2[num] = [re.sub(r'[*`]', '', m.group(1)).strip() for m in re.finditer(r'^## (.+)$', md, re.M)]
        sections.append(f'<section class="doc d{num}">{md_to_html(md)}</section>')
    body = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>LAVA · Documentos para permiso</title>'
            f'<style>{fcss}</style><style>{CSS}</style></head><body>{"".join(sections)}</body></html>')
    footer = ('<div style="width:100%;font-family:Arial,sans-serif;font-size:6.8pt;color:#8a8278;padding:0 15mm;display:flex;'
              'justify-content:space-between;"><span>LAVA · Contemporary Fire &amp; BBQ · Documentos para permiso · v' + F.ver + '</span>'
              '<span style="color:#b35000;font-weight:bold">ANTEPROYECTO / PRELIMINAR</span>'
              '<span>Pág. <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
    header_t = '<span></span>'
    with tempfile.TemporaryDirectory() as td:
        bh, bp = os.path.join(td, 'body.html'), os.path.join(td, 'body.pdf')
        with open(bh, 'w', encoding='utf-8') as fh:
            fh.write(body)
        run_node([{'html': bh, 'pdf': bp, 'footer': footer, 'header': header_t}])
        pages, toc = heading_pages(bp, docs_h2)
        ch, cp = os.path.join(td, 'cover.html'), os.path.join(td, 'cover.pdf')
        with open(ch, 'w', encoding='utf-8') as fh:
            fh.write(cover_html(F, pages, fcss))
        run_node([{'html': ch, 'pdf': cp}])
        out = fitz.open(cp)
        b = fitz.open(bp)
        out.insert_pdf(b)
        ncover = out.page_count - b.page_count
        b.close()
        out.set_toc([[1, 'Portada', 1]] + [[lv, t, p + 1 + ncover] for lv, t, p in toc])
        out.set_metadata({'title': 'LAVA – Documentos para permiso (anteproyecto v' + F.ver + ')', 'author': 'Anteproyecto LAVA',
                          'subject': 'ANTEPROYECTO / PRELIMINAR — a validar por el profesional responsable', 'creator': 'tools/permit_docs.py'})
        path = os.path.join(out_dir, PDF_NAME)
        out.save(path, garbage=3, deflate=True)
        npages = out.page_count
        out.close()
    return path, npages, pages


def render_png(pdf, out, pages=None, dpi=110):
    fitz = _fitz()
    os.makedirs(out, exist_ok=True)
    d = fitz.open(pdf)
    sel = pages or list(range(1, d.page_count + 1))
    paths = []
    for p in sel:
        if 1 <= p <= d.page_count:
            fp = os.path.join(out, f'page_{p:03d}.png')
            d[p - 1].get_pixmap(dpi=dpi).save(fp)
            paths.append(fp)
    d.close()
    return paths


# ------------------------------------------------------------------------------------------------ main


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--research', default=os.environ.get('LAVA_RESEARCH'), help='compliance research.json (optional)')
    ap.add_argument('--audit', default=os.environ.get('LAVA_AUDIT'), help='compliance audit.json (optional)')
    ap.add_argument('--out', default=OUT_DIR, help='output folder (default docs/permisos)')
    ap.add_argument('--no-pdf', action='store_true', help='only write the Markdown files')
    ap.add_argument('--png', help='also render PDF pages to PNG in this folder (visual check)')
    ap.add_argument('--png-pages', help='comma-separated page numbers for --png (default: all)')
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    F = Facts(a.research, a.audit, out)
    builders = {'00': doc_00, '01': doc_01, '02': doc_02, '03': doc_03, '04': doc_04, '05': doc_05, '06': doc_06, '07': doc_07, '08': doc_08}
    mds = {}
    for num, fn, _ in DOCS:
        md = acc_md(builders[num](F))
        mds[fn] = md
        with open(os.path.join(out, fn), 'w', encoding='utf-8') as fh:
            fh.write(md.rstrip() + '\n')
        print('wrote', os.path.relpath(os.path.join(out, fn), ROOT))
    if not a.no_pdf:
        path, npages, pages = build_pdf(F, mds, out)
        print('wrote', os.path.relpath(path, ROOT), f'({npages} páginas; inicio de cada documento: ' +
              ', '.join(f'{k}→{v + 2}' for k, v in sorted(pages.items())) + ')')
        if a.png:
            sel = [int(x) for x in a.png_pages.split(',')] if a.png_pages else None
            for p in render_png(path, a.png, sel):
                print('png', p)


if __name__ == '__main__':
    main()
