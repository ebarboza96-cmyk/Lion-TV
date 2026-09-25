"""Render the sheets of ONE module from tools/sheets/ into a scratch folder (SVG + PNG + PDF) without touching plan/.

Usage: python3 tools/preview_sheet.py <module_name> <out_dir>
  e.g. python3 tools/preview_sheet.py s104_seguridad /tmp/prev
Needs Node + Playwright (same as tools/export_sheets.js).
"""
import importlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lavageo import ROOT, load_existing, load_json  # noqa: E402


def main():
    mod, out = sys.argv[1], os.path.abspath(sys.argv[2])
    os.makedirs(out, exist_ok=True)
    ex = load_existing()
    lay = load_json(os.path.join(ROOT, 'data', 'layout.json'))
    vp = os.path.join(ROOT, 'data', 'validation.json')
    val = load_json(vp) if os.path.exists(vp) else None
    shs = importlib.import_module(f'sheets.{mod}').sheets(ex, lay, val)
    index = []
    for sh in shs:
        with open(os.path.join(out, sh['file']), 'w') as fh:
            fh.write(sh['svg'])
        index.append({k: sh[k] for k in ('id', 'file', 'title', 'order')})
    with open(os.path.join(out, 'sheets.json'), 'w') as fh:
        json.dump(index, fh, indent=1, ensure_ascii=False)
    npm_root = subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, NODE_PATH=npm_root)
    subprocess.run(['node', os.path.join(os.path.dirname(__file__), 'export_sheets.js'), out], check=True, env=env)
    for sh in shs:
        print('preview', os.path.join(out, sh['file'].replace('.svg', '.png')))


if __name__ == '__main__':
    main()
