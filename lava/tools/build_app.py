#!/usr/bin/env python3
"""Bundle the LAVA walkthrough app into single self-contained HTML files.

Inputs (paths relative to the lava/ project root):
  app/src/template.html      markup + CSS (a fragment: <title>, <style>, <link>s, markup, placeholders)
  app/src/js/*.js            ES-module source, concatenated in filename order into ONE <script type="module">
  data/existing.json         existing conditions (required)
  data/layout.json           layout proposal (required; override with --layout)
  data/report.json           validation report (optional: metrics{}, verify[], risks[], flags[])
  plan/lava_plan.svg         project plan drawing (optional; inlined into the Plano tab)

Outputs:
  app/index.html             complete standalone document (open from disk or any static host)
  app/artifact.html          same page as a fragment for Claude Artifacts (no doctype/html/head/body)

The only external resources are three.js r160 (cdn.jsdelivr.net/npm, via importmap) and Google Fonts.

Usage:
  python3 tools/build_app.py [--layout data/layout.json] [--out app] [--no-report] [--no-plan]
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THREE_VER = '0.160.0'
IMPORTMAP = {
    'imports': {
        'three': f'https://cdn.jsdelivr.net/npm/three@{THREE_VER}/build/three.module.js',
        'three/addons/': f'https://cdn.jsdelivr.net/npm/three@{THREE_VER}/examples/jsm/',
    }
}
ALLOWED_HOSTS = ('cdn.jsdelivr.net', 'fonts.googleapis.com', 'fonts.gstatic.com', 'www.w3.org')


def rel(p):
    return os.path.join(ROOT, p)


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def load_json(p, required=True):
    if not os.path.exists(p):
        if required:
            sys.exit(f'ERROR: falta {os.path.relpath(p, ROOT)}')
        return None
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        if required:
            sys.exit(f'ERROR: {os.path.relpath(p, ROOT)} no es JSON válido: {e}')
        print(f'AVISO: {os.path.relpath(p, ROOT)} ignorado (JSON inválido: {e})')
        return None


def json_for_script(obj):
    # safe inside <script type="application/json">: no '<' at all (escaped as \u003c inside strings)
    s = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    return s.replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def clean_svg(text):
    text = re.sub(r'<\?xml[^>]*\?>', '', text)
    text = re.sub(r'<!DOCTYPE[^>]*>', '', text, flags=re.I)
    text = re.sub(r'<script\b.*?</script>', '', text, flags=re.I | re.S)
    return text.strip()


def bundle_js(src_dir):
    files = sorted(f for f in os.listdir(src_dir) if f.endswith('.js'))
    if not files:
        sys.exit('ERROR: no hay archivos en app/src/js/')
    parts = []
    for f in files:
        code = read(os.path.join(src_dir, f))
        if re.search(r'^\s*(import|export)\s', code, flags=re.M):
            sys.exit(f'ERROR: {f} usa import/export estático; los módulos se concatenan (usa import() dinámico).')
        parts.append(f'/* ---- {f} ---- */\n{code}')
    js = '\n'.join(parts)
    js = re.sub(r'</(script)', r'<\\/\1', js, flags=re.I)
    return js, files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--layout', default='data/layout.json')
    ap.add_argument('--existing', default='data/existing.json')
    ap.add_argument('--report', default='data/report.json')
    ap.add_argument('--plan', default='plan/lava_plan.svg')
    ap.add_argument('--out', default='app')
    ap.add_argument('--no-report', action='store_true')
    ap.add_argument('--no-plan', action='store_true')
    a = ap.parse_args()

    def P(p):
        return p if os.path.isabs(p) else rel(p)

    template = read(rel('app/src/template.html'))
    js, files = bundle_js(rel('app/src/js'))
    existing = load_json(P(a.existing))
    layout = load_json(P(a.layout))
    report = None if a.no_report else load_json(P(a.report), required=False)
    plan_svg = None
    if not a.no_plan and os.path.exists(P(a.plan)):
        plan_svg = clean_svg(read(P(a.plan)))
        if '<svg' not in plan_svg:
            print('AVISO: plan SVG sin <svg>, se ignora')
            plan_svg = None

    data = {
        'existing': existing, 'layout': layout, 'report': report, 'planSvg': plan_svg,
        'build': {'date': datetime.date.today().isoformat(), 'layout': os.path.relpath(P(a.layout), ROOT), 'three': THREE_VER},
    }
    importmap = '<script type="importmap">' + json.dumps(IMPORTMAP, separators=(',', ':')) + '</script>'
    data_tag = '<script type="application/json" id="lava-data">' + json_for_script(data) + '</script>'
    script_tag = '<script type="module">\n' + js + '\n</script>'

    for ph in ('<!--@IMPORTMAP-->', '<!--@DATA-->', '<!--@SCRIPT-->'):
        if ph not in template:
            sys.exit(f'ERROR: template.html no contiene {ph}')
    frag = (template.replace('<!--@IMPORTMAP-->', importmap)
                    .replace('<!--@DATA-->', data_tag)
                    .replace('<!--@SCRIPT-->', script_tag))

    # ---- artifact fragment: <title>, <style>, links, markup, scripts (no doctype/html/head/body)
    artifact = frag.strip() + '\n'
    if re.search(r'<!doctype|<html[\s>]|<head[\s>]|<body[\s>]', artifact, flags=re.I):
        sys.exit('ERROR: el fragmento contiene doctype/html/head/body')
    if not artifact.startswith('<title>'):
        sys.exit('ERROR: el fragmento debe empezar con <title>')

    # ---- full document: move title/style/links into <head>
    m_title = re.search(r'<title>.*?</title>', frag, flags=re.S)
    m_style = re.search(r'<style>.*?</style>', frag, flags=re.S)
    head_end = m_style.end()
    rest = frag[head_end:]
    links = re.findall(r'<link\b[^>]*>', rest.split('<div', 1)[0])
    body = rest
    for l in links:
        body = body.replace(l, '', 1)
    desc = 'Recorrido 3D, plano y datos del test-fit de LAVA – Contemporary Fire & BBQ (Terrazas Lindora).'
    index = ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
             '<meta name="theme-color" content="#141210">\n'
             f'<meta name="description" content="{desc}">\n'
             + m_title.group(0) + '\n' + '\n'.join(links) + '\n' + m_style.group(0) + '\n</head>\n<body>\n'
             + body.strip() + '\n</body>\n</html>\n')

    out = P(a.out)
    os.makedirs(out, exist_ok=True)
    for name, content in (('index.html', index), ('artifact.html', artifact)):
        path = os.path.join(out, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        urls = set(re.findall(r'https?://([a-zA-Z0-9.-]+)', content))
        bad = sorted(u for u in urls if u not in ALLOWED_HOSTS)
        size = len(content.encode('utf-8'))
        print(f'{os.path.relpath(path, ROOT)}: {size / 1024:.0f} KB' + (f'  AVISO hosts externos: {bad}' if bad else ''))
    print(f'fuentes JS: {", ".join(files)}')
    print(f'datos: existing.json + {os.path.relpath(P(a.layout), ROOT)}'
          + (' + report.json' if report else ' (sin report.json)') + (' + lava_plan.svg' if plan_svg else ' (sin plano SVG)'))


if __name__ == '__main__':
    main()
