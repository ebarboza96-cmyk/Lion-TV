"""Build the test-fit report (Markdown for the repo + JSON for the walkthrough app's "Datos" tab).

Usage: python3 tools/report.py [data/layout.json] [data/validation.json]
Writes docs/INFORME_TEST_FIT.md and data/report.json. Qualitative content lives in data/report_content.json.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lavageo import R, ROOT, load_existing, load_json, seat_count


def eq_dims(e):
    x0, y0, x1, y1 = e['rect']
    wd, dp = abs(x1 - x0), abs(y1 - y0)
    if e.get('front') in ('N', 'S'):
        a, b = wd, dp
    elif e.get('front') in ('E', 'W'):
        a, b = dp, wd
    else:
        a, b = max(wd, dp), min(wd, dp)
    return a, b


def main():
    lay_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data', 'layout.json')
    val_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'data', 'validation.json')
    ex = load_existing()
    lay = load_json(lay_path)
    val = load_json(val_path)
    content = load_json(os.path.join(ROOT, 'data', 'report_content.json'))
    m = val['metrics']
    zones = {z['id']: z for z in m.get('zones', [])}
    routes = m.get('routes', [])

    seats = seat_count(lay)
    tables = lay.get('tables', [])
    n2 = sum(1 for t in tables if int(t.get('seats', 0)) <= 2)
    n4 = sum(1 for t in tables if int(t.get('seats', 0)) >= 4)
    banq = sum(int(b.get('seats', 0)) for b in lay.get('banquettes', []))
    chairs = len(lay.get('chairs', []))

    z = lambda k: zones.get(k, {}).get('area_m2')
    prod = round(sum(z(k) or 0 for k in ('B', 'E', 'W', 'A')), 2)
    main_aisle = min((r['min_width'] for r in routes if r.get('kind') in ('guest', 'server') and r.get('required', 0) >= 1.1), default=None)
    metrics = {
        'seats': seats,
        'seats_detail': f"{chairs} sillas + {banq} puestos en banca · {n2} mesas de 2 (unibles) y {n4} mesas de 4",
        'partition_shift_m': m.get('partition_shift_m'),
        'new_partition_x': m.get('new_partition_x'),
        'dining_m2': z('D'),
        'bar_m2': z('C'),
        'kitchen_hot_m2': z('B'),
        'bbq_m2': z('E'),
        'washing_m2': z('W'),
        'cold_prep_m2': z('A'),
        'production_m2': prod,
        'premises_m2': m.get('premises_area_m2'),
        'main_aisle_m': main_aisle,
        'hot_line_length': m.get('hot_line_length'),
        'hood_length': m.get('hood_length'),
        'parrilla_view_pct': m.get('seats_with_parrilla_view_pct'),
        'parrilla_visible_from_entrance': m.get('parrilla_visible_from_entrance'),
        'zones': m.get('zones', []),
        'routes': routes,
        'warnings': val.get('warnings', []),
        'issues': val.get('issues', []),
    }
    equipment = []
    for e in lay.get('equipment', []):
        a, b = eq_dims(e)
        equipment.append({'tag': e.get('tag', e['id']), 'name': e.get('label'), 'cat': e.get('cat'), 'w': round(a, 2), 'd': round(b, 2),
                          'h': e.get('h'), 'tbv': bool(e.get('tbv')), 'overhead': bool(e.get('overhead')), 'note': e.get('note', '')})

    report = {'metrics': metrics, 'equipment': equipment, **content}
    with open(os.path.join(ROOT, 'data', 'report.json'), 'w') as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)

    # ---------------- Markdown
    L = []
    L.append('# LAVA · Contemporary Fire & BBQ — Informe de test-fit')
    L.append('')
    L.append(content.get('intro', ''))
    L.append('')
    L.append('Láminas: [`plan/LAVA_test-fit_planos_A2.pdf`](../plan/LAVA_test-fit_planos_A2.pdf) '
             '(A-101 planta propuesta · A-102 demolición/construcción · A-103 flujos). '
             'Recorrido 3D: [`app/index.html`](../app/index.html).')
    L.append('')
    L.append('## 1. Resumen en cifras')
    L.append('')
    L.append('| Indicador | Valor |')
    L.append('|---|---|')
    L.append(f"| Asientos en salón | **{seats}** ({metrics['seats_detail']}) |")
    if metrics['partition_shift_m'] is not None:
        L.append(f"| Corrimiento de la división cocina/salón | {metrics['partition_shift_m']:.2f} m hacia atrás (de X = 6.30 a X = {metrics['new_partition_x']:.2f}) |")
    for zid, label in (('B', 'B · Hot line / show kitchen (incluye mesa + horno)'), ('E', 'E · BBQ production (smoker + holding + leña)'),
                       ('W', 'W · Washing (antiguas PILAS)'), ('A', 'A · Cold prep + frío + almacén (antigua PASTELERÍA)'),
                       ('C', 'C · Bar / POS + pase'), ('D', 'D · Dining (salón)')):
        if zid in zones:
            L.append(f"| Área {label} | ≈ {zones[zid]['area_m2']:.1f} m² |")
    L.append(f"| Área total de producción (B + E + W + A) | ≈ {prod:.1f} m² |")
    L.append(f"| Área de salón + barra (D + C) | ≈ {(z('D') or 0) + (z('C') or 0):.1f} m² |")
    L.append(f"| Área interior del local (medida sobre el PDF) | ≈ {metrics['premises_m2']:.1f} m² |")
    if main_aisle:
        L.append(f"| Pasillo principal del salón (ancho libre medido) | {main_aisle:.2f} m |")
    if metrics['hot_line_length']:
        L.append(f"| Hot line / campana propuesta | {metrics['hot_line_length']:.2f} m / {metrics['hood_length']:.2f} m |")
    if metrics['parrilla_view_pct'] is not None:
        L.append(f"| Asientos con línea de vista directa a la parrilla | {metrics['parrilla_view_pct']:.0f} % · visible desde la entrada: {'sí' if metrics['parrilla_visible_from_entrance'] else 'no'} |")
    L.append('')
    L.append('## 2. Anchos de pasillo (medidos automáticamente sobre la planta)')
    L.append('')
    L.append('Ancho libre mínimo a lo largo de cada recorrido, entre equipos, mobiliario (sillas ocupadas) y muros.')
    L.append('')
    L.append('| Recorrido | Tipo | Ancho mínimo | Requerido | Longitud |')
    L.append('|---|---|---|---|---|')
    kind_es = {'guest': 'clientes', 'server': 'meseros', 'clean': 'limpio', 'dirty': 'sucio', 'delivery': 'delivery', 'fuel': 'combustible'}
    for r in routes:
        L.append(f"| {r.get('label') or r['id']} | {kind_es.get(r.get('kind'), r.get('kind'))} | **{r['min_width']:.2f} m** | {r['required']:.2f} m | {r['length']:.1f} m |")
    L.append('')
    for sec in content.get('sections', []):
        L.append(f"## {sec['title']}")
        L.append('')
        for p in sec.get('paragraphs', []):
            L.append(p)
            L.append('')
        for it in sec.get('bullets', []):
            L.append(f"- {it}")
        if sec.get('bullets'):
            L.append('')
        if sec.get('table'):
            hdr = sec['table']['header']
            L.append('| ' + ' | '.join(hdr) + ' |')
            L.append('|' + '---|' * len(hdr))
            for row in sec['table']['rows']:
                L.append('| ' + ' | '.join(str(c) for c in row) + ' |')
            L.append('')
    for title, key in (('Dimensiones y condiciones a verificar en sitio', 'verify'), ('Riesgos de circulación y operación', 'risks'),
                       ('Banderas de ingeniería', 'flags')):
        items = content.get(key) or []
        if items:
            L.append(f'## {title}')
            L.append('')
            for i, it in enumerate(items, 1):
                L.append(f"{i}. {it}" if key != 'flags' else f"- **{it}**")
            L.append('')
    L.append('## Cuadro de equipos')
    L.append('')
    L.append('Frente × fondo × alto en metros. **\\*** = DIMENSION TO VERIFY.')
    L.append('')
    L.append('| Tag | Equipo | Dimensiones | Nota |')
    L.append('|---|---|---|---|')
    for e in equipment:
        dims = f"{e['w']:.2f} × {e['d']:.2f}" + (f" × {float(e['h']):.2f}" if e['h'] and not e['overhead'] else '')
        star = ' \\*' if e['tbv'] else ''
        L.append(f"| {e['tag']} | {e['name']} | {dims}{star} | {e['note']} |")
    L.append('')
    if metrics['warnings']:
        L.append('## Alertas del validador geométrico')
        L.append('')
        for w in metrics['warnings']:
            L.append(f"- {w}")
        L.append('')
    L.append('---')
    L.append(content.get('footer', ''))
    with open(os.path.join(ROOT, 'docs', 'INFORME_TEST_FIT.md'), 'w') as fh:
        fh.write('\n'.join(L) + '\n')
    print('wrote docs/INFORME_TEST_FIT.md and data/report.json')


if __name__ == '__main__':
    main()
