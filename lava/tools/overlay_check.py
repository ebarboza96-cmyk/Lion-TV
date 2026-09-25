"""Overlay existing.json (and optionally a layout.json) on the source PDF to verify geometry.
Usage: python3 tools/overlay_check.py <pdf> <out.png> [layout.json]
"""
import sys, json
import pymupdf as fitz
K = 56.693; OX = 149.4; OY = 2.501 * K
def P(x, y): return (OX + x * K, OY + y * K)
pdf, out = sys.argv[1], sys.argv[2]
ex = json.load(open('data/existing.json'))
d = fitz.open(pdf); p = d[0]
sh = p.new_shape()
def rect(r, color, w=0.6, fill=None, op=0.35):
    a = P(r[0], r[1]); b = P(r[2], r[3])
    sh.draw_rect(fitz.Rect(a, b)); sh.finish(color=color, width=w, fill=fill, fill_opacity=op, stroke_opacity=0.9)
for c in ex['columns']: rect(c['rect'], (1, 0, 0), fill=(1, 0, 0))
for w in ex['walls']:
    col = {'perimeter': (0, 0, 1), 'partition_light': (1, 0.5, 0), 'shaft': (0.5, 0, 0.5), 'neighbor': (0, 0.5, 0.5), 'pilaster_shafts': (0.5, 0, 0.5)}[w['kind']]
    rect(w['rect'], col, fill=col, op=0.25)
for g in ex['glazing']: rect(g['rect'], (0, 0.7, 0), w=1.2, fill=(0, 1, 0))
for s in ex['shafts']: rect(s['rect'], (0.6, 0, 0.8), w=0.8)
for wp in ex['wet_points_existing']: rect(wp['rect'], (0, 0.6, 1), w=1.0)
poly = [P(*pt) for pt in ex['premises_polygon']] + [P(*ex['premises_polygon'][0])]
sh.draw_polyline(poly); sh.finish(color=(1, 0, 1), width=1.0, dashes='[3 2] 0')
if len(sys.argv) > 3:
    lay = json.load(open(sys.argv[3]))
    for e in lay.get('equipment', []):
        rect(e['rect'], (0.9, 0.4, 0), w=0.8, fill=(1, 0.6, 0), op=0.3)
sh.commit()
clip = fitz.Rect(P(-1.5, -1.2), P(17.2, 12.2))
p.get_pixmap(dpi=170, clip=clip).save(out)
print('saved', out)
