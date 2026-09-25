"""Quick-look PNG render of a layout proposal (for design iteration, not the final drawing).

Usage: python3 tools/render_png.py data/layout.json out.png
"""
import math
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Rectangle, FancyArrowPatch

sys.path.insert(0, __import__('os').path.dirname(__file__))
from lavageo import R, door_swing_poly, front_zone, load_existing, load_json, standing_existing_walls

CAT = {
    'fire': ('#f28c28', '#b35900'),
    'cold': ('#7fb3ff', '#1f5fbf'),
    'prep': ('#b9d7ff', '#1f5fbf'),
    'wash': ('#9be3e3', '#177a7a'),
    'storage': ('#e2cfa5', '#7a6231'),
    'smoker': ('#d9622b', '#7a2a0a'),
    'bar': ('#c9b3e6', '#5b3d8a'),
    'delivery': ('#f6e27a', '#8a7a12'),
    'hood': ('none', '#b35900'),
    'dining': ('#9fd49f', '#2e7d32'),
    'misc': ('#dddddd', '#555555'),
}
ROUTE = {'clean': '#1f77b4', 'dirty': '#d62728', 'guest': '#2ca02c', 'server': '#9467bd', 'delivery': '#bcbd22', 'fuel': '#8c564b'}


def rect_patch(ax, r, fc, ec, lw=0.8, ls='-', alpha=1.0, z=2, hatch=None):
    x0, y0, x1, y1 = r
    ax.add_patch(Rectangle((min(x0, x1), min(y0, y1)), abs(x1 - x0), abs(y1 - y0), facecolor=fc, edgecolor=ec,
                           lw=lw, ls=ls, alpha=alpha, zorder=z, hatch=hatch))


def main():
    lay = load_json(sys.argv[1])
    out = sys.argv[2]
    ex = load_existing()
    fig, ax = plt.subplots(figsize=(22, 16), dpi=110)
    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.add_patch(MPoly(ex['premises_polygon'], closed=True, facecolor='#fbfbf7', edgecolor='none', zorder=0))
    for z in lay.get('zones', []):
        ax.add_patch(MPoly(z['poly'], closed=True, facecolor=z.get('color', '#eeeeee'), alpha=0.18, edgecolor='none', zorder=0.5))
        xs = [p[0] for p in z['poly']]; ys = [p[1] for p in z['poly']]
        ax.text(sum(xs) / len(xs), sum(ys) / len(ys), f"{z['id']}", fontsize=26, color='#999999', alpha=0.35,
                ha='center', va='center', zorder=0.6, weight='bold')
    gone = {d['id'] for d in lay.get('demolish', []) if 'rect' not in d}
    for w in ex['walls']:
        if w['id'] in gone:
            rect_patch(ax, w['rect'], 'none', '#e02020', lw=1.4, ls='--', z=3)
    for d in lay.get('demolish', []):
        if 'rect' in d:
            rect_patch(ax, d['rect'], 'none', '#e02020', lw=1.4, ls='--', z=3)
    for w, g in standing_existing_walls(ex, lay):
        for poly in (getattr(g, 'geoms', None) or [g]):
            ax.add_patch(MPoly(list(poly.exterior.coords), closed=True, facecolor='#9a9a9a', edgecolor='#555555', lw=0.5, zorder=3))
    for c in ex['columns']:
        rect_patch(ax, c['rect'], '#555555', '#222222', z=4)
    for s in ex['shafts']:
        x0, y0, x1, y1 = s['rect']
        rect_patch(ax, s['rect'], 'none', '#777777', lw=0.6, z=4)
        ax.plot([x0, x1], [y0, y1], color='#777777', lw=0.5, zorder=4)
        ax.plot([x0, x1], [y1, y0], color='#777777', lw=0.5, zorder=4)
    for g in ex['glazing']:
        rect_patch(ax, g['rect'], '#bfefff', '#2a9fd6', lw=1.0, z=4)
    st = ex['stair']['outline']
    rect_patch(ax, st, '#f0f0f0', '#aaaaaa', lw=0.5, z=1)
    ax.text((st[0] + st[2]) / 2, (st[1] + st[3]) / 2, 'ESCALERA\n(existente)', ha='center', va='center', fontsize=9, color='#888888')
    for w in lay.get('new_walls', []):
        t = w.get('type', 'partition')
        if t == 'glass_partition':
            rect_patch(ax, w['rect'], '#222222', '#000000', lw=1.0, z=5)
            x0, y0, x1, y1 = w['rect']
            ax.plot([(x0 + x1) / 2] * 2 if (x1 - x0) < (y1 - y0) else [x0, x1],
                    [y0, y1] if (x1 - x0) < (y1 - y0) else [(y0 + y1) / 2] * 2, color='#6fd3ff', lw=1.2, zorder=6)
        else:
            rect_patch(ax, w['rect'], '#111111', '#000000', lw=1.0, z=5)
    for o in lay.get('new_openings', []):
        if o.get('rect'):
            rect_patch(ax, o['rect'], '#ffffff', '#000000', lw=0.4, z=6)
        sw = door_swing_poly(o)
        if sw is not None:
            ax.add_patch(MPoly(list(sw.exterior.coords), closed=True, facecolor='none', edgecolor='#333333', lw=0.6, ls=':', zorder=6))
        if o.get('label'):
            x0, y0, x1, y1 = o['rect']
            ax.text((x0 + x1) / 2, (y0 + y1) / 2, o['label'], fontsize=6, ha='center', va='center', zorder=9,
                    color='#000000', bbox=dict(fc='white', ec='none', alpha=0.7, pad=0.3))
    for e in lay.get('equipment', []):
        fc, ec = CAT.get(e.get('cat', 'misc'), CAT['misc'])
        if e.get('overhead'):
            rect_patch(ax, e['rect'], 'none', ec, lw=1.2, ls='--', z=7)
            x0, y0, x1, y1 = e['rect']
            ax.text(x0 + 0.05, y0 + 0.05, e.get('label', ''), fontsize=6, color=ec, va='top', zorder=9)
            continue
        rect_patch(ax, e['rect'], fc, ec, lw=0.9, z=6)
        fz = front_zone(e)
        if fz is not None:
            x0, y0, x1, y1 = fz.bounds
            rect_patch(ax, [x0, y0, x1, y1], 'none', ec, lw=0.4, ls=':', z=5.5, alpha=0.6)
        x0, y0, x1, y1 = e['rect']
        w, h = abs(x1 - x0), abs(y1 - y0)
        rot = 90 if h > w * 1.3 else 0
        lbl = e.get('label', e.get('id'))
        if e.get('tbv'):
            lbl += '*'
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, lbl, fontsize=6.5, ha='center', va='center', rotation=rot, zorder=9)
    for t in lay.get('tables', []):
        rect_patch(ax, t['rect'], '#cfe9cf', '#2e7d32', lw=0.8, z=6)
    for c in lay.get('chairs', []):
        rect_patch(ax, c['rect'], '#9fd49f', '#2e7d32', lw=0.6, z=6)
    for b in lay.get('banquettes', []):
        rect_patch(ax, b['rect'], '#6fbf73', '#1b5e20', lw=0.8, z=6)
        x0, y0, x1, y1 = b['rect']
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, f"banca {b.get('seats')}p", fontsize=6, ha='center', va='center', zorder=9)
    for r in lay.get('routes', []):
        xs = [p[0] for p in r['pts']]; ys = [p[1] for p in r['pts']]
        ax.plot(xs, ys, color=ROUTE.get(r.get('kind'), '#333333'), lw=2.2, alpha=0.75, zorder=8,
                ls='--' if r.get('kind') == 'dirty' else '-')
        ax.annotate('', xy=r['pts'][-1], xytext=r['pts'][-2], zorder=8,
                    arrowprops=dict(arrowstyle='->', color=ROUTE.get(r.get('kind'), '#333'), lw=2))
    for name, p in lay.get('points', {}).items():
        ax.plot(p[0], p[1], 'k.', ms=4, zorder=9)
        ax.text(p[0] + 0.05, p[1] - 0.05, name, fontsize=5.5, color='#444', zorder=9)
    # grid
    for x in range(-1, 18):
        ax.axvline(x, color='#e0e0e0', lw=0.4, zorder=0.1)
        ax.text(x, -1.05, f'{x}', fontsize=7, ha='center', color='#999')
    for y in range(-1, 13):
        ax.axhline(y, color='#e0e0e0', lw=0.4, zorder=0.1)
        ax.text(-1.25, y, f'{y}', fontsize=7, va='center', color='#999')
    ax.set_xlim(-1.4, 17.0)
    ax.set_ylim(12.2, -1.2)
    ax.set_title(lay.get('meta', {}).get('name', sys.argv[1]), fontsize=14)
    ax.axis('off')
    fig.tight_layout()
    fig.savefig(out)
    print('saved', out)


if __name__ == '__main__':
    main()
