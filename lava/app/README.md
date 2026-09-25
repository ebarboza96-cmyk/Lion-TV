# LAVA – recorrido 3D, plano y datos

Build (from `lava/`):

```bash
python3 tools/build_app.py                 # uses data/existing.json + data/layout.json (+ data/report.json, plan/lava_plan.svg if present)
python3 tools/build_app.py --layout otra.json --out /tmp/prueba   # try another layout without touching data/
```

Outputs (single self-contained files, all CSS/JS/data inline):

- `app/index.html` – full document. Open it directly from disk or serve the folder (`python3 -m http.server -d app`).
- `app/artifact.html` – the same page as a fragment for Claude Artifacts (no doctype/html/head/body).

Only external resources: three.js r160 from `cdn.jsdelivr.net/npm` (importmap) and Google Fonts. Without them the
Plano and Datos tabs still work and the 3D tab shows a clear message.

Source lives in `app/src/`: `template.html` (markup + CSS) and `js/*.js` (concatenated in filename order into one
ES module). Deep links: `#recorrido`, `#plano`, `#datos`.

Optional layout fields read by the 3D view: `decor[]` (`slat_wall`, `sign`, `poster`, `sconce`, `pendant`, `planter`,
`firewood_niche` with `rect` or `pos`, `face`, `text`, `h`, `z`, `size`, `style`, `text_at`), `decor_defaults: false`
to disable automatic decor, and `tour[]` (`{id, title, text, pos:[x,y], look:[x,y], look_h, flags:[]}`).
