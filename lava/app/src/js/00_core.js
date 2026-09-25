/* ===================================================================================
   LAVA walkthrough – 00 core: data, DOM + geometry helpers (no three.js dependency)
   All src/js/*.js files are concatenated (in filename order) into ONE ES module by
   tools/build_app.py, so they share this top-level scope.
   =================================================================================== */
'use strict';

// three.js is loaded lazily (dynamic import) so Plano/Datos keep working without it.
let THREE = null, OrbitControls = null, mergeGeometries = null;

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat(3)) if (k != null && k !== false) e.append(k.nodeType ? k : String(k));
  return e;
}
const SVGNS = 'http://www.w3.org/2000/svg';
function sv(tag, attrs, ...kids) {
  const e = document.createElementNS(SVGNS, tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) if (v != null && v !== false) e.setAttribute(k, v);
  for (const k of kids.flat(3)) if (k != null && k !== false) e.append(k.nodeType ? k : String(k));
  return e;
}

/* ---------- data ---------- */
const DATA = (() => {
  try { const n = document.getElementById('lava-data'); return n ? JSON.parse(n.textContent) : {}; }
  catch (e) { console.warn('LAVA: datos embebidos ilegibles', e); return {}; }
})();
const EX = (DATA.existing && typeof DATA.existing === 'object') ? DATA.existing : {};
const LAY = (DATA.layout && typeof DATA.layout === 'object') ? DATA.layout : {};
const REPORT = (DATA.report && typeof DATA.report === 'object') ? DATA.report : null;
const PLAN_SVG = typeof DATA.planSvg === 'string' && DATA.planSvg.includes('<svg') ? DATA.planSvg : null;
const BUILD = DATA.build || {};

const mq = q => { try { return matchMedia(q).matches; } catch (e) { return false; } };
const REDUCED = mq('(prefers-reduced-motion: reduce)');
const COARSE = mq('(pointer: coarse)');

const FLAGS = {
  EXTRACTION: 'EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED',
  SMOKER: 'SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED',
  DIM: 'DIMENSION TO VERIFY',
  SITE: 'VERIFY ON SITE',
};

const KEY_ES = {
  fridge_2d: 'Refrigerador 2 puertas', freezer_1d: 'Congelador 1 puerta', mesa_fria: 'Mesa fría refrigerada',
  mesa_1: 'Mesa de trabajo inox 1', mesa_2: 'Mesa de trabajo inox 2', mesa_opt: 'Mesa de trabajo opcional',
  shelf_4: 'Estantería 4 niveles', sink_2t: 'Fregadero 2 tanques', mop_sink: 'Pileta de aseo', handwash: 'Lavamanos',
  parrilla: 'Parrilla argentina', cocina_4q: 'Cocina 4 quemadores', plancha: 'Plancha', freidora_1: 'Freidora 1',
  freidora_2: 'Freidora 2', hood: 'Campana de extracción', smoker: 'Smoker (ahumador)', fuel_storage: 'Leña y carbón',
  barra: 'Barra / caja', pos: 'Punto de venta (POS)', pass: 'Pase de platos', delivery_staging: 'Estación de delivery',
  holding: 'Gabinete caliente (holding)', trash: 'Basurero', ice: 'Máquina de hielo', back_bar: 'Contrabarra', host: 'Recepción',
};
const CAT_ES = { fire: 'Fuego', cold: 'Frío', prep: 'Preparación', wash: 'Lavado', storage: 'Almacenaje', smoker: 'Smoker',
  bar: 'Barra / pase', delivery: 'Delivery', hood: 'Extracción', misc: 'Varios', dining: 'Salón' };
const CAT_COLOR = { fire: '#f28c28', cold: '#4f8fe0', prep: '#93bdf0', wash: '#3fb8b8', storage: '#c8a86a', smoker: '#d9622b',
  bar: '#a98bd6', delivery: '#e8cf4a', hood: '#b35900', misc: '#9b9185', dining: '#5f9e5f' };
const ROUTE_COLOR = { clean: '#3b8fe0', dirty: '#e0403a', guest: '#3fbf5f', server: '#a37be0', delivery: '#f0c93a', fuel: '#9a6a3f' };
const ROUTE_ES = { clean: 'Flujo limpio', dirty: 'Flujo sucio', guest: 'Clientes', server: 'Servicio', delivery: 'Delivery', fuel: 'Combustible' };
const ZONE_FALLBACK_COLORS = ['#1f5fbf', '#f28c28', '#3fb8b8', '#2e7d32', '#d9622b', '#a98bd6'];

/* ---------- small utils ---------- */
const arr = v => (Array.isArray(v) ? v : []);
const num = (v, d) => (typeof v === 'number' && isFinite(v)) ? v
  : (typeof v === 'string' && v.trim() !== '' && isFinite(+v)) ? +v : d;
const str = (v, d = '') => (typeof v === 'string' ? v : (typeof v === 'number' ? String(v) : d));
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = t => t * t * (3 - 2 * t);
const easeInOut = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const fmt = (v, d = 2) => (typeof v === 'number' && isFinite(v) ? v.toFixed(d) : '—');
const angDiff = (a, b) => { let d = (b - a) % (Math.PI * 2); if (d > Math.PI) d -= Math.PI * 2; if (d < -Math.PI) d += Math.PI * 2; return d; };
function pt(p) { return (Array.isArray(p) && p.length >= 2 && isFinite(+p[0]) && isFinite(+p[1])) ? [+p[0], +p[1]] : null; }
function nrect(r) {
  if (!Array.isArray(r) || r.length < 4) return null;
  const v = r.slice(0, 4).map(Number);
  if (v.some(x => !isFinite(x))) return null;
  const R = [Math.min(v[0], v[2]), Math.min(v[1], v[3]), Math.max(v[0], v[2]), Math.max(v[1], v[3])];
  return (R[2] - R[0] < 1e-4 && R[3] - R[1] < 1e-4) ? null : R;
}
const rw = r => r[2] - r[0];
const rh = r => r[3] - r[1];
const rcx = r => (r[0] + r[2]) / 2;
const rcy = r => (r[1] + r[3]) / 2;
const rgrow = (r, g) => [r[0] - g, r[1] - g, r[2] + g, r[3] + g];
const rOverlap = (a, b, e = 0) => a[0] < b[2] - e && b[0] < a[2] - e && a[1] < b[3] - e && b[1] < a[3] - e;
const rInter = (a, b) => { const r = [Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.min(a[2], b[2]), Math.min(a[3], b[3])]; return (r[2] > r[0] && r[3] > r[1]) ? r : null; };
function rSub(a, b) { // a minus b -> up to 4 rects
  const i = rInter(a, b);
  if (!i) return [a];
  const out = [];
  if (i[1] > a[1] + 1e-6) out.push([a[0], a[1], a[2], i[1]]);
  if (i[3] < a[3] - 1e-6) out.push([a[0], i[3], a[2], a[3]]);
  if (i[0] > a[0] + 1e-6) out.push([a[0], i[1], i[0], i[3]]);
  if (i[2] < a[2] - 1e-6) out.push([i[2], i[1], a[2], i[3]]);
  return out.filter(r => rw(r) > 0.004 && rh(r) > 0.004);
}
function rDist(a, b) { const dx = Math.max(0, a[0] - b[2], b[0] - a[2]); const dy = Math.max(0, a[1] - b[3], b[1] - a[3]); return Math.hypot(dx, dy); }
function pRectDist(x, y, r) { const dx = Math.max(r[0] - x, 0, x - r[2]); const dy = Math.max(r[1] - y, 0, y - r[3]); return Math.hypot(dx, dy); }
function polyArea(p) { let a = 0; for (let i = 0, n = p.length; i < n; i++) { const q = p[i], s = p[(i + 1) % n]; a += q[0] * s[1] - s[0] * q[1]; } return Math.abs(a) / 2; }
function polyCentroid(p) {
  let a = 0, cx = 0, cy = 0;
  for (let i = 0, n = p.length; i < n; i++) { const q = p[i], s = p[(i + 1) % n]; const f = q[0] * s[1] - s[0] * q[1]; a += f; cx += (q[0] + s[0]) * f; cy += (q[1] + s[1]) * f; }
  if (Math.abs(a) < 1e-9) { const n = p.length || 1; return [p.reduce((s, q) => s + q[0], 0) / n, p.reduce((s, q) => s + q[1], 0) / n]; }
  return [cx / (3 * a), cy / (3 * a)];
}
function polyBBox(p) { const xs = p.map(q => q[0]), ys = p.map(q => q[1]); return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]; }
function inPoly(x, y, p) {
  let c = false;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
    const a = p[i], b = p[j];
    if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) c = !c;
  }
  return c;
}
const DIRV = { N: [0, -1], S: [0, 1], E: [1, 0], W: [-1, 0] };
const normDir = d => (typeof d === 'string' && DIRV[d.trim().toUpperCase()] ? d.trim().toUpperCase() : null);

/* ---------- ray casting (plan) ---------- */
function rayRect(ox, oy, dx, dy, r) {
  let t0 = -Infinity, t1 = Infinity;
  if (Math.abs(dx) < 1e-12) { if (ox < r[0] || ox > r[2]) return -1; }
  else { let a = (r[0] - ox) / dx, b = (r[2] - ox) / dx; if (a > b) [a, b] = [b, a]; t0 = Math.max(t0, a); t1 = Math.min(t1, b); }
  if (Math.abs(dy) < 1e-12) { if (oy < r[1] || oy > r[3]) return -1; }
  else { let a = (r[1] - oy) / dy, b = (r[3] - oy) / dy; if (a > b) [a, b] = [b, a]; t0 = Math.max(t0, a); t1 = Math.min(t1, b); }
  if (t1 < t0 || t1 < 0) return -1;
  return t0 >= 0 ? t0 : 0;
}
function raySeg(ox, oy, dx, dy, ax, ay, bx, by) {
  const ex = bx - ax, ey = by - ay, den = dx * ey - dy * ex;
  if (Math.abs(den) < 1e-12) return -1;
  const t = ((ax - ox) * ey - (ay - oy) * ex) / den, u = ((ax - ox) * dy - (ay - oy) * dx) / den;
  return (t >= 0 && u >= 0 && u <= 1) ? t : -1;
}

/* ---------- event bus ---------- */
const BUS = new EventTarget();
const emit = (n, d) => BUS.dispatchEvent(new CustomEvent(n, { detail: d }));
const on = (n, f) => BUS.addEventListener(n, e => f(e.detail));

const nextFrame = () => new Promise(r => requestAnimationFrame(() => r()));
const sleep = ms => new Promise(r => setTimeout(r, ms));
