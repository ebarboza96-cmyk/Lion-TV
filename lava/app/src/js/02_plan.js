/* ===================================================================================
   02 plano: inline project SVG (plan/lava_plan.svg) when bundled, else a clean plan
   generated from the same data. Pan (drag), zoom (wheel / pinch / buttons), fit.
   =================================================================================== */

const PLAN_CAT = {
  fire: ['#f7b27a', '#b35900'], cold: ['#9cc2f5', '#1f5fbf'], prep: ['#cfe1fa', '#1f5fbf'], wash: ['#a9e6e6', '#177a7a'],
  storage: ['#e6d5ae', '#7a6231'], smoker: ['#ec9a72', '#7a2a0a'], bar: ['#d6c6ee', '#5b3d8a'], delivery: ['#f6e48c', '#8a7a12'],
  hood: ['none', '#b35900'], misc: ['#e2ddd4', '#6a645c'],
};

function buildPlanSVG(M) {
  const pad = 1.3;
  const ext = [M.pbb[0], M.pbb[1], M.pbb[2], M.pbb[3]];
  for (const c of M.columns) { ext[0] = Math.min(ext[0], c.rect[0]); ext[1] = Math.min(ext[1], c.rect[1]); ext[2] = Math.max(ext[2], c.rect[2]); ext[3] = Math.max(ext[3], c.rect[3]); }
  const vb = [ext[0] - pad, ext[1] - pad - 0.6, rw(ext) + 2 * pad, rh(ext) + 2 * pad + 1.5];
  const svg = sv('svg', { xmlns: SVGNS, viewBox: vb.join(' '), class: 'plan-root', role: 'img', 'aria-label': 'Plano del test-fit generado desde los datos', 'font-family': 'Figtree, sans-serif' });
  const defs = sv('defs');
  for (const [k, c] of Object.entries(ROUTE_COLOR)) {
    defs.append(sv('marker', { id: 'arw-' + k, viewBox: '0 0 10 10', refX: '8', refY: '5', markerWidth: '5', markerHeight: '5', orient: 'auto-start-reverse' }, sv('path', { d: 'M0 0L10 5L0 10z', fill: c })));
  }
  defs.append(sv('pattern', { id: 'hatch', width: '0.12', height: '0.12', patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, sv('line', { x1: 0, y1: 0, x2: 0, y2: 0.12, stroke: '#77716a', 'stroke-width': 0.025 })));
  svg.append(defs);
  const g = (cls) => { const e = sv('g', { class: cls }); svg.append(e); return e; };
  const R = (r, a) => sv('rect', { x: r[0], y: r[1], width: rw(r), height: rh(r), ...a });
  const T = (x, y, s, text, a = {}) => sv('text', { x, y, 'font-size': s, 'text-anchor': 'middle', 'dominant-baseline': 'central', fill: '#2a2622', ...a }, text);

  // sheet
  svg.append(sv('rect', { x: vb[0], y: vb[1], width: vb[2], height: vb[3], fill: '#f3efe6' }));
  // axes
  const ax = EX.meta && EX.meta.axes ? EX.meta.axes : null;
  const gA = g('axes');
  if (ax) {
    for (const [k, v] of Object.entries(ax)) {
      if (!isFinite(+v)) continue;
      if (/^row/.test(k)) {
        const y = +v; gA.append(sv('line', { x1: vb[0] + 0.5, y1: y, x2: vb[0] + vb[2] - 0.2, y2: y, stroke: '#b9b2a6', 'stroke-width': 0.012, 'stroke-dasharray': '0.25 0.08 0.04 0.08' }));
        gA.append(sv('circle', { cx: vb[0] + 0.3, cy: y, r: 0.2, fill: 'none', stroke: '#8d867b', 'stroke-width': 0.02 }), T(vb[0] + 0.3, y, 0.2, k.replace('row', ''), { fill: '#6d665c' }));
      } else {
        const x = +v; gA.append(sv('line', { x1: x, y1: vb[1] + 0.5, x2: x, y2: vb[1] + vb[3] - 0.2, stroke: '#b9b2a6', 'stroke-width': 0.012, 'stroke-dasharray': '0.25 0.08 0.04 0.08' }));
        gA.append(sv('circle', { cx: x, cy: vb[1] + 0.3, r: 0.2, fill: 'none', stroke: '#8d867b', 'stroke-width': 0.02 }), T(x, vb[1] + 0.3, 0.2, k, { fill: '#6d665c' }));
      }
    }
  }
  // premises
  svg.append(sv('polygon', { points: M.prem.map(p => p.join(',')).join(' '), fill: '#fbf9f4', stroke: 'none' }));
  // stair
  if (M.stair) {
    const gs = g('stair'); gs.append(R(M.stair.rect, { fill: '#e7e2d8', stroke: '#b6afa3', 'stroke-width': 0.015 }));
    for (const f of M.stair.flights) { gs.append(R(f, { fill: 'none', stroke: '#c3bcaf', 'stroke-width': 0.01 })); for (let y = f[1]; y < f[3]; y += 0.3) gs.append(sv('line', { x1: f[0], y1: y, x2: f[2], y2: y, stroke: '#c9c2b5', 'stroke-width': 0.008 })); }
    gs.append(T(rcx(M.stair.rect), rcy(M.stair.rect) - 1.6, 0.2, 'ESCALERA (existente)', { fill: '#8a8378', 'letter-spacing': '0.02' }));
  }
  // zones
  const gz = g('zones');
  for (const z of M.zones) {
    gz.append(sv('polygon', { points: z.poly.map(p => p.join(',')).join(' '), fill: z.color, 'fill-opacity': 0.13, stroke: z.color, 'stroke-opacity': 0.5, 'stroke-width': 0.02, 'stroke-dasharray': '0.12 0.06' }));
    gz.append(T(z.c[0], z.c[1], 0.95, z.id, { fill: z.color, 'fill-opacity': 0.28, 'font-weight': 800, 'font-family': 'Big Shoulders Display, sans-serif' }));
  }
  // demolished
  const gd = g('demolish');
  for (const d of M.demolished) gd.append(R(d.rect, { fill: 'none', stroke: '#d4402a', 'stroke-width': 0.03, 'stroke-dasharray': '0.1 0.06' }));
  // walls
  const gw = g('walls');
  for (const w of M.walls.filter(w => w.src === 'existing')) gw.append(R(w.rect, { fill: '#948e86', stroke: '#5f5a54', 'stroke-width': 0.012 }));
  for (const s of M.shafts) { gw.append(R(s.rect, { fill: 'none', stroke: '#7d776f', 'stroke-width': 0.012 })); gw.append(sv('path', { d: `M${s.rect[0]} ${s.rect[1]}L${s.rect[2]} ${s.rect[3]}M${s.rect[2]} ${s.rect[1]}L${s.rect[0]} ${s.rect[3]}`, stroke: '#9b958c', 'stroke-width': 0.01 })); }
  for (const c of M.columns) gw.append(R(c.rect, { fill: '#55504a', stroke: '#2e2a26', 'stroke-width': 0.012 }));
  for (const gl of M.glazing) gw.append(R(gl.rect, { fill: '#bfe6f5', stroke: '#2a9fd6', 'stroke-width': 0.015 }));
  for (const d of M.doors) {
    gw.append(sv('line', { x1: d.a[0], y1: d.a[1], x2: d.b[0], y2: d.b[1], stroke: '#fbf9f4', 'stroke-width': 0.08 }));
    if (d.kind === 'double') { // two inward leaves
      const mx = (d.a[0] + d.b[0]) / 2, my = (d.a[1] + d.b[1]) / 2; const L = d.width / 2;
      const inward = M.isInside(d.a[0] - 0.3, my) ? -1 : 1;
      for (const [hx, hy, s] of [[d.a[0], d.a[1], 1], [d.b[0], d.b[1], -1]]) {
        const ex = hx + inward * L * 0.98;
        gw.append(sv('path', { d: `M${hx} ${hy} L${ex} ${hy} A${L} ${L} 0 0 ${inward * s > 0 ? 1 : 0} ${hx} ${hy + s * L}`, fill: 'none', stroke: '#7d776f', 'stroke-width': 0.01, 'stroke-dasharray': '0.04 0.03' }));
      }
      gw.append(T(mx + inward * 0.55, my, 0.16, 'ENTRADA', { fill: '#3f3a34', 'font-weight': 700, transform: `rotate(-90 ${mx + inward * 0.55} ${my})` }));
    }
  }
  // new walls
  for (const w of M.walls.filter(w => w.src === 'new')) {
    gw.append(R(w.rect, { fill: '#141210', stroke: '#000', 'stroke-width': 0.01 }));
    if (w.type === 'glass_partition') {
      const r = w.rect, v = rh(r) > rw(r);
      gw.append(sv('line', v ? { x1: rcx(r), y1: r[1], x2: rcx(r), y2: r[3] } : { x1: r[0], y1: rcy(r), x2: r[2], y2: rcy(r), }, null));
      gw.lastChild.setAttribute('stroke', '#6fd3ff'); gw.lastChild.setAttribute('stroke-width', 0.03);
    }
  }
  // openings
  const go = g('openings');
  for (const o of M.openings) {
    go.append(R(o.rect, { fill: o.type === 'pass_window' ? '#e6f6fb' : '#ffffff', stroke: '#141210', 'stroke-width': 0.008 }));
    if (o.hinge && o.closed_to && o.swing_to) {
      const [hx, hy] = o.hinge, [ax_, ay] = o.closed_to, [bx, by] = o.swing_to, r = Math.hypot(ax_ - hx, ay - hy);
      const cross = (ax_ - hx) * (by - hy) - (ay - hy) * (bx - hx);
      go.append(sv('path', { d: `M${hx} ${hy}L${bx} ${by}M${ax_} ${ay}A${r} ${r} 0 0 ${cross > 0 ? 1 : 0} ${bx} ${by}`, fill: 'none', stroke: '#3a352f', 'stroke-width': 0.012, 'stroke-dasharray': '0.05 0.03' }));
    }
    if (o.label) go.append(T(rcx(o.rect), rcy(o.rect), 0.13, o.label, { 'font-weight': 700, fill: '#141210', stroke: '#fff', 'stroke-width': 0.03, 'paint-order': 'stroke' }));
  }
  // furniture
  const gf = g('furniture');
  for (const b of M.banquettes) { gf.append(R(b.rect, { fill: '#8fc28f', stroke: '#2e6b31', 'stroke-width': 0.012, rx: 0.04 })); gf.append(T(rcx(b.rect), rcy(b.rect), 0.13, `banca ${b.seats}p`, { fill: '#1d4a20' })); }
  for (const t of M.tables) gf.append(R(t.rect, { fill: '#d8ecd6', stroke: '#2e7d32', 'stroke-width': 0.012 }));
  for (const c of M.chairs) gf.append(R(c.rect, { fill: '#a9d6a6', stroke: '#2e7d32', 'stroke-width': 0.01, rx: 0.06 }));
  // equipment
  const ge = g('equipment');
  const eqs = M.equip.slice().sort((a, b) => (a.overhead ? 1 : 0) - (b.overhead ? 1 : 0));
  for (const e of eqs) {
    const [fc, ec] = PLAN_CAT[e.cat] || PLAN_CAT.misc;
    if (e.overhead) {
      ge.append(R(e.rect, { fill: 'none', stroke: ec, 'stroke-width': 0.025, 'stroke-dasharray': '0.1 0.05' }));
      ge.append(sv('text', { x: e.rect[0] + 0.06, y: e.rect[1] + 0.14, 'font-size': 0.11, fill: ec }, e.label + (e.tbv ? '*' : '')));
      continue;
    }
    ge.append(R(e.rect, { fill: fc, stroke: ec, 'stroke-width': 0.014 }));
    const f = e.front; if (f && e.clear > 0) {
      const r = e.rect, c = e.clear; const z = f === 'N' ? [r[0], r[1] - c, r[2], r[1]] : f === 'S' ? [r[0], r[3], r[2], r[3] + c] : f === 'W' ? [r[0] - c, r[1], r[0], r[3]] : [r[2], r[1], r[2] + c, r[3]];
      ge.append(R(z, { fill: 'none', stroke: ec, 'stroke-opacity': 0.45, 'stroke-width': 0.008, 'stroke-dasharray': '0.04 0.04' }));
    }
    const rot = rh(e.rect) > rw(e.rect) * 1.3;
    const fs = clamp(Math.min(rot ? rw(e.rect) : rh(e.rect), 0.6) * 0.3, 0.07, 0.15);
    const x = rcx(e.rect), y = rcy(e.rect);
    ge.append(T(x, y, fs, e.label + (e.tbv ? '*' : ''), rot ? { transform: `rotate(-90 ${x} ${y})` } : {}));
  }
  // routes
  const gr = g('routes');
  for (const r of M.routes) {
    const c = ROUTE_COLOR[r.kind] || '#555';
    gr.append(sv('polyline', { points: r.pts.map(p => p.join(',')).join(' '), fill: 'none', stroke: c, 'stroke-width': 0.05, 'stroke-opacity': 0.85,
      'stroke-linejoin': 'round', 'stroke-linecap': 'round', 'stroke-dasharray': r.kind === 'dirty' ? '0.16 0.1' : null, 'marker-end': `url(#arw-${ROUTE_COLOR[r.kind] ? r.kind : 'guest'})` }));
  }
  // points
  const gp = g('points');
  for (const [k, p] of Object.entries(M.points)) { gp.append(sv('circle', { cx: p[0], cy: p[1], r: 0.04, fill: '#141210' })); gp.append(sv('text', { x: p[0] + 0.07, y: p[1] - 0.07, 'font-size': 0.1, fill: '#4a453f' }, k)); }
  // title block, scale bar, north
  const tb = g('titleblock');
  const tx = vb[0] + 0.5, ty = vb[1] + vb[3] - 0.95;
  tb.append(sv('text', { x: tx, y: ty, 'font-size': 0.42, 'font-weight': 800, fill: '#141210', 'font-family': 'Big Shoulders Display, sans-serif', 'letter-spacing': '0.08' }, 'LΛVΛ · TEST-FIT'));
  tb.append(sv('text', { x: tx, y: ty + 0.36, 'font-size': 0.16, fill: '#5a544c' }, `${str(M.meta.name, 'Propuesta')} · cotas en metros · * = DIMENSION TO VERIFY`));
  const sx = vb[0] + vb[2] - 5.9, sy = ty + 0.12;
  for (let i = 0; i < 5; i++) tb.append(sv('rect', { x: sx + i, y: sy, width: 1, height: 0.1, fill: i % 2 ? '#f3efe6' : '#141210', stroke: '#141210', 'stroke-width': 0.01 }));
  for (const i of [0, 1, 2, 5]) tb.append(T(sx + i, sy + 0.3, 0.14, `${i}`, { fill: '#3a352f' }));
  tb.append(T(sx + 2.5, sy - 0.22, 0.13, 'metros', { fill: '#5a544c' }));
  const nx_ = vb[0] + vb[2] - 0.55, ny_ = vb[1] + 1.05;
  tb.append(sv('path', { d: `M${nx_} ${ny_ - 0.35}L${nx_ + 0.16} ${ny_ + 0.2}L${nx_} ${ny_ + 0.1}L${nx_ - 0.16} ${ny_ + 0.2}Z`, fill: '#141210' }));
  tb.append(T(nx_, ny_ - 0.55, 0.18, 'N', { 'font-weight': 700 }));
  tb.append(T(nx_, ny_ + 0.42, 0.09, '(plano)', { fill: '#6a645c' }));
  return { svg, bbox: [vb[0], vb[1], vb[0] + vb[2], vb[1] + vb[3]] };
}

function importPlanSVG(text) {
  try {
    const doc = new DOMParser().parseFromString(text, 'image/svg+xml');
    const root = doc.documentElement;
    if (!root || root.nodeName.toLowerCase() !== 'svg' || doc.querySelector('parsererror')) return null;
    root.querySelectorAll('script,foreignObject').forEach(n => n.remove());
    root.querySelectorAll('*').forEach(n => { for (const a of Array.from(n.attributes)) if (/^on/i.test(a.name) || (/href$/i.test(a.name) && /^\s*javascript:/i.test(a.value))) n.removeAttribute(a.name); });
    const svg = document.importNode(root, true);
    let vb = (svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    if (vb.length !== 4 || vb.some(v => !isFinite(v))) {
      const w = parseFloat(svg.getAttribute('width')) || 1000, h = parseFloat(svg.getAttribute('height')) || 700;
      vb = [0, 0, w, h];
    }
    svg.removeAttribute('width'); svg.removeAttribute('height');
    svg.setAttribute('class', 'plan-root'); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', 'Plano del proyecto (plan/lava_plan.svg)');
    return { svg, bbox: [vb[0], vb[1], vb[0] + vb[2], vb[1] + vb[3]] };
  } catch (e) { console.warn('LAVA: plan SVG ilegible', e); return null; }
}

class PanZoom {
  constructor(wrap) {
    this.wrap = wrap; this.svg = null; this.bbox = [0, 0, 1, 1]; this.v = { cx: 0.5, cy: 0.5, s: 0.01 };
    this.ptrs = new Map(); this.fitted = false;
    wrap.addEventListener('pointerdown', e => this.down(e));
    wrap.addEventListener('pointermove', e => this.move(e));
    const up = e => { this.ptrs.delete(e.pointerId); if (!this.ptrs.size) wrap.classList.remove('dragging'); this.pinch = null; };
    wrap.addEventListener('pointerup', up); wrap.addEventListener('pointercancel', up); wrap.addEventListener('pointerleave', up);
    wrap.addEventListener('wheel', e => { e.preventDefault(); const f = Math.exp(clamp(e.deltaY, -120, 120) * 0.0022); this.zoomAt(e.offsetX, e.offsetY, f); }, { passive: false });
    wrap.addEventListener('keydown', e => {
      const k = e.key, st = 40 * this.v.s;
      if (k === '+' || k === '=') this.zoomBy(1 / 1.25); else if (k === '-') this.zoomBy(1.25);
      else if (k === 'ArrowLeft') this.v.cx -= st; else if (k === 'ArrowRight') this.v.cx += st; else if (k === 'ArrowUp') this.v.cy -= st; else if (k === 'ArrowDown') this.v.cy += st;
      else if (k === '0') this.fit(); else return;
      e.preventDefault(); this.apply();
    });
    if (window.ResizeObserver) new ResizeObserver(() => { if (this.fitted) this.fit(); else this.apply(); }).observe(wrap);
  }
  set(content) {
    this.wrap.replaceChildren(content.svg); this.svg = content.svg; this.bbox = content.bbox;
    this.svg.setAttribute('preserveAspectRatio', 'xMidYMid meet'); this.fit();
  }
  size() { return [Math.max(10, this.wrap.clientWidth), Math.max(10, this.wrap.clientHeight)]; }
  fit() {
    const [w, h] = this.size(), b = this.bbox;
    this.v = { cx: (b[0] + b[2]) / 2, cy: (b[1] + b[3]) / 2, s: Math.max(rw(b) / w, rh(b) / h) * 1.02 };
    this.fitted = true; this.apply();
  }
  apply() {
    if (!this.svg) return;
    const [w, h] = this.size(), s = this.v.s;
    this.svg.setAttribute('viewBox', `${this.v.cx - w * s / 2} ${this.v.cy - h * s / 2} ${w * s} ${h * s}`);
  }
  zoomAt(px, py, f) {
    const [w, h] = this.size(), s = this.v.s;
    const mx = this.v.cx + (px - w / 2) * s, my = this.v.cy + (py - h / 2) * s;
    const b = this.bbox, ns = clamp(s * f, Math.max(rw(b), rh(b)) / 8000, Math.max(rw(b) / w, rh(b) / h) * 3);
    this.v.cx = mx - (px - w / 2) * ns; this.v.cy = my - (py - h / 2) * ns; this.v.s = ns; this.fitted = false; this.apply();
  }
  zoomBy(f) { const [w, h] = this.size(); this.zoomAt(w / 2, h / 2, f); }
  down(e) {
    this.wrap.setPointerCapture && this.wrap.setPointerCapture(e.pointerId);
    this.ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY }); this.wrap.classList.add('dragging');
  }
  move(e) {
    const p = this.ptrs.get(e.pointerId); if (!p) return;
    const rect = this.wrap.getBoundingClientRect();
    if (this.ptrs.size >= 2) {
      const pts = Array.from(this.ptrs.values());
      p.x = e.clientX; p.y = e.clientY;
      const a = pts[0], b = pts[1], d = Math.hypot(a.x - b.x, a.y - b.y), mx = (a.x + b.x) / 2 - rect.left, my = (a.y + b.y) / 2 - rect.top;
      if (this.pinch) { this.zoomAt(mx, my, this.pinch.d / Math.max(d, 1)); this.v.cx -= (mx - this.pinch.mx) * this.v.s; this.v.cy -= (my - this.pinch.my) * this.v.s; this.apply(); }
      this.pinch = { d, mx, my };
      return;
    }
    const dx = e.clientX - p.x, dy = e.clientY - p.y; p.x = e.clientX; p.y = e.clientY;
    this.v.cx -= dx * this.v.s; this.v.cy -= dy * this.v.s; this.fitted = false; this.apply();
  }
}

let PLAN = null;
function initPlan() {
  if (PLAN) return;
  const wrap = $('#plan-wrap'); const pz = new PanZoom(wrap);
  const gen = () => buildPlanSVG(MODEL);
  const ext = PLAN_SVG ? importPlanSVG(PLAN_SVG) : null;
  let src = ext ? 'proyecto' : 'datos';
  const show = () => { pz.set(src === 'proyecto' && ext ? ext : gen()); renderSrc(); };
  const renderSrc = () => {
    const box = $('#plan-src'); box.replaceChildren();
    if (!ext) return;
    for (const [k, t] of [['proyecto', 'Plano del proyecto'], ['datos', 'Generado de datos']]) {
      box.append(el('button', { class: 'btn', type: 'button', 'aria-pressed': String(src === k), onclick: () => { src = k; show(); } }, t));
    }
  };
  $('#pz-in').addEventListener('click', () => pz.zoomBy(1 / 1.3));
  $('#pz-out').addEventListener('click', () => pz.zoomBy(1.3));
  $('#pz-fit').addEventListener('click', () => pz.fit());
  const leg = $('#plan-legend');
  $('#pz-leg').addEventListener('click', e => { leg.hidden = !leg.hidden; e.currentTarget.setAttribute('aria-expanded', String(!leg.hidden)); });
  if (matchMedia('(max-width:760px)').matches) { leg.hidden = true; $('#pz-leg').setAttribute('aria-expanded', 'false'); }
  const cats = [...new Set(MODEL.equip.map(e => e.cat))];
  leg.append(el('h3', null, 'Leyenda'));
  const sw = (css, label) => [el('span', { class: 'sw', style: css }), el('span', null, label)];
  leg.append(...sw('background:#948e86', 'Muro existente'), ...sw('background:#141210;box-shadow:inset 0 -3px #6fd3ff', 'Muro / vidrio nuevo'),
    ...sw('border:2px dashed #d4402a', 'Demolición'));
  for (const c of cats) { const [fc, ec] = PLAN_CAT[c] || PLAN_CAT.misc; leg.append(...sw(`background:${fc === 'none' ? 'transparent' : fc};border:2px ${c === 'hood' ? 'dashed' : 'solid'} ${ec}`, CAT_ES[c] || c)); }
  if (MODEL.tables.length || MODEL.banquettes.length) leg.append(...sw('background:#a9d6a6;border:2px solid #2e7d32', 'Mesas, sillas y bancas'));
  for (const k of [...new Set(MODEL.routes.map(r => r.kind))]) leg.append(...sw(`background:transparent;border-top:3px ${k === 'dirty' ? 'dashed' : 'solid'} ${ROUTE_COLOR[k] || '#555'};height:0;margin-top:6px`, 'Ruta: ' + (ROUTE_ES[k] || k)));
  $('#plan-note').replaceChildren(el('span', { class: 'chip' }, el('i', { style: 'background:var(--brass)' }), ext ? 'Plano del proyecto · plan/lava_plan.svg' : 'Plano generado desde layout.json'));
  show();
  PLAN = { pz, refresh: () => pz.fit() };
}
