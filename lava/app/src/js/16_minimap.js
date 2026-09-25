/* ===================================================================================
   16 minimap (plan outline, zones, walls, equipment, stops, you + heading; tap = go)
   and 17 picking (tap/hover equipment -> info card; tap floor -> walk there).
   =================================================================================== */

const MM = { canvas: null, ctx: null, base: null, scale: 1, ox: 0, oy: 0, w: 0, h: 0, last: 0 };

function initMinimap() {
  const c = $('#mm'); MM.canvas = c; MM.ctx = c.getContext('2d');
  const resize = () => {
    const r = c.getBoundingClientRect(); if (!r.width) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.round(r.width * dpr); c.height = Math.round(r.height * dpr);
    MM.w = c.width; MM.h = c.height;
    const bb = rgrow(MODEL.pbb, 0.35);
    MM.scale = Math.min(MM.w / rw(bb), MM.h / rh(bb));
    MM.ox = (MM.w - rw(bb) * MM.scale) / 2 - bb[0] * MM.scale; MM.oy = (MM.h - rh(bb) * MM.scale) / 2 - bb[1] * MM.scale;
    drawMinimapBase();
  };
  MM.resize = resize;
  if (window.ResizeObserver) new ResizeObserver(resize).observe(c);
  resize();
  const toPlan = e => { const r = c.getBoundingClientRect(), dpr = MM.w / r.width; return [((e.clientX - r.left) * dpr - MM.ox) / MM.scale, ((e.clientY - r.top) * dpr - MM.oy) / MM.scale]; };
  c.addEventListener('pointerdown', e => {
    e.preventDefault(); e.stopPropagation();
    const [x, y] = toPlan(e);
    if (W3.aerial) { W3.controls.target.copy(V3(x, y, 0)); return; }
    const s = MODEL.snap(x, y, RADIUS + 0.02, 2.5); if (!s) return;
    stopAuto(); TOUR.motion = null; setView(s[0], s[1]); $('#caption').hidden = true;
  });
  const btn = $('#btn-map'), mm = $('#minimap');
  if (matchMedia('(max-width:760px)').matches) mm.classList.add('collapsed');
  btn.addEventListener('click', () => { const col = mm.classList.toggle('collapsed'); btn.setAttribute('aria-expanded', String(!col)); if (!col) resize(); });
}
function mmP(x, y) { return [MM.ox + x * MM.scale, MM.oy + y * MM.scale]; }
function mmRect(ctx, r) { const a = mmP(r[0], r[1]); ctx.rect(a[0], a[1], rw(r) * MM.scale, rh(r) * MM.scale); }
function drawMinimapBase() {
  const M = MODEL, base = mkCanvas(MM.w, MM.h), x = base.getContext('2d');
  x.fillStyle = '#26211d'; x.beginPath(); M.prem.forEach((p, i) => { const q = mmP(p[0], p[1]); i ? x.lineTo(q[0], q[1]) : x.moveTo(q[0], q[1]); }); x.closePath(); x.fill();
  for (const z of M.zones) { x.fillStyle = z.color; x.globalAlpha = 0.22; x.beginPath(); z.poly.forEach((p, i) => { const q = mmP(p[0], p[1]); i ? x.lineTo(q[0], q[1]) : x.moveTo(q[0], q[1]); }); x.closePath(); x.fill(); }
  x.globalAlpha = 1;
  x.fillStyle = '#5b544c'; for (const e of M.equip) if (!e.overhead) { x.beginPath(); mmRect(x, e.rect); x.fill(); }
  x.fillStyle = '#4f5a45'; for (const t of [...M.tables, ...M.banquettes]) { x.beginPath(); mmRect(x, t.rect); x.fill(); }
  x.fillStyle = '#d8d0c2'; for (const w of M.walls) { x.beginPath(); mmRect(x, w.rect); x.fill(); }
  for (const c of M.columns) { x.beginPath(); mmRect(x, c.rect); x.fill(); }
  x.fillStyle = '#6fd3ff'; for (const g of M.glazing) { x.beginPath(); mmRect(x, rgrow(g.rect, 0.03)); x.fill(); }
  x.strokeStyle = '#8c8377'; x.lineWidth = 1; x.beginPath(); M.prem.forEach((p, i) => { const q = mmP(p[0], p[1]); i ? x.lineTo(q[0], q[1]) : x.moveTo(q[0], q[1]); }); x.closePath(); x.stroke();
  const dpr = MM.w / (MM.canvas.getBoundingClientRect().width || MM.w);
  x.font = `${Math.round(9 * dpr)}px "JetBrains Mono",monospace`; x.textAlign = 'center'; x.textBaseline = 'middle';
  M.stops.forEach((s, i) => { const q = mmP(s.pos[0], s.pos[1]); x.fillStyle = 'rgba(201,160,99,.9)'; x.beginPath(); x.arc(q[0], q[1], 6.5 * dpr, 0, 7); x.fill(); x.fillStyle = '#141210'; x.fillText(String(i + 1), q[0], q[1] + 0.5); });
  MM.base = base;
}
function drawMinimap(now) {
  if (!MM.base || now - MM.last < 66) return; MM.last = now;
  const x = MM.ctx; x.clearRect(0, 0, MM.w, MM.h); x.drawImage(MM.base, 0, 0);
  const dpr = MM.w / (MM.canvas.getBoundingClientRect().width || MM.w);
  let px, py, yaw;
  if (W3.aerial && W3.camera) { const t = W3.controls.target; px = t.x; py = t.z; const c = W3.camera.position; yaw = Math.atan2(t.z - c.z, t.x - c.x); }
  else { px = WALK.x; py = WALK.y; yaw = WALK.yaw; }
  const q = mmP(px, py), fov = W3.camera ? W3.camera.fov * (W3.camera.aspect || 1) * Math.PI / 180 / 2 : 0.8, R = 34 * dpr;
  const g = x.createRadialGradient(q[0], q[1], 2, q[0], q[1], R); g.addColorStop(0, 'rgba(255,106,26,.55)'); g.addColorStop(1, 'rgba(255,106,26,0)');
  x.fillStyle = g; x.beginPath(); x.moveTo(q[0], q[1]); x.arc(q[0], q[1], R, yaw - Math.min(fov, 1.1), yaw + Math.min(fov, 1.1)); x.closePath(); x.fill();
  x.fillStyle = '#ff6a1a'; x.strokeStyle = '#141210'; x.lineWidth = 2 * dpr; x.beginPath(); x.arc(q[0], q[1], 4.5 * dpr, 0, 7); x.fill(); x.stroke();
}

/* ---------------- picking ---------------- */
const PICK = { hover: null, ray: null, ndc: null, box: null };
function pickAt(e) {
  const cv = W3.renderer.domElement, r = cv.getBoundingClientRect();
  PICK.ndc = PICK.ndc || new THREE.Vector2(); PICK.ray = PICK.ray || new THREE.Raycaster();
  PICK.ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  PICK.ray.setFromCamera(PICK.ndc, W3.camera);
  const ray = PICK.ray.ray, hit = new THREE.Vector3();
  let best = null, bd = Infinity;
  for (const p of W3.picks) if (ray.intersectBox(p.box, hit)) { const d = hit.distanceTo(ray.origin); if (d < bd) { bd = d; best = p; } }
  let occ = Infinity;
  for (const o of W3.occluders) if (ray.intersectBox(o.box, hit)) { const d = hit.distanceTo(ray.origin); if (d < occ) occ = d; }
  let floor = null;
  if (ray.direction.y < -0.02) { const t = -ray.origin.y / ray.direction.y; const fp = ray.origin.clone().addScaledVector(ray.direction, t); if (t < occ && t < bd) floor = [fp.x, fp.z, t]; }
  if (best && bd < occ + 0.05) return { item: best, d: bd };
  return { floor };
}
function hoverPick(e) {
  if (!W3.renderer || APP.view !== 'recorrido' || (performance.now() - (PICK.lastHover || 0)) < 60) return;
  PICK.lastHover = performance.now();
  const res = pickAt(e);
  const stage = $('#stage');
  const it = res.item || null;
  stage.classList.toggle('hovering', !!it);
  setHighlight(it);
}
function setHighlight(p) {
  if (PICK.hover === p) return; PICK.hover = p;
  if (!PICK.box) { PICK.box = new THREE.Box3Helper(new THREE.Box3(), 0xff6a1a); PICK.box.material.depthTest = false; PICK.box.material.transparent = true; PICK.box.material.opacity = 0.85; PICK.box.renderOrder = 30; W3.scene.add(PICK.box); }
  PICK.box.visible = !!p;
  if (p) { PICK.box.box.copy(p.box).expandByScalar(0.015); }
}
function tapAt(e) {
  if (!W3.renderer) return;
  const res = pickAt(e);
  if (res.item) { showInfo(res.item); setHighlight(res.item); return; }
  if (res.floor && !W3.aerial) {
    const [x, y, d] = res.floor; if (d > 18 || !MODEL.isInside(x, y)) return;
    const s = MODEL.snap(x, y, RADIUS + 0.02, 1.2); if (!s) return;
    stopAuto(); $('#info').hidden = true; setHighlight(null);
    moveTo(s, WALK.yaw + angDiff(WALK.yaw, Math.atan2(s[1] - WALK.y, s[0] - WALK.x)) * (Math.hypot(s[0] - WALK.x, s[1] - WALK.y) > 1.2 ? 1 : 0), WALK.pitch);
  }
}
function showInfo(p) {
  const it = p.item, card = $('#info');
  let k = '', title = '', dims = '', flags = [], note = '';
  if (p.kind === 'equipment') {
    const f = frameOf(it.rect, itemFront(MODEL, it));
    k = `${KEY_ES[it.key] || CAT_ES[it.cat] || 'Equipo'} · ${CAT_ES[it.cat] || it.cat}`;
    title = it.label;
    dims = `${fmt(f.w, 2)} × ${fmt(f.d, 2)} × ${fmt(it.h, 2)} m`;
    if (it.tbv) flags.push(FLAGS.DIM);
    if (it.key === 'hood' || it.key === 'parrilla') flags.push(FLAGS.EXTRACTION);
    if (it.key === 'smoker') flags.push(FLAGS.SMOKER);
    note = [it.note, it.clear ? `Despeje libre al frente: ${fmt(it.clear, 2)} m` : '', it.overhead ? 'Elemento en altura (no ocupa piso).' : ''].filter(Boolean).join(' · ');
  } else if (p.kind === 'table') {
    k = 'Mesa'; title = `Mesa ${it.id}`; dims = `${fmt(rw(it.rect), 2)} × ${fmt(rh(it.rect), 2)} m · ${it.seats} personas`;
    note = it.join.length ? `Se une con ${it.join.join(', ')}` : '';
  } else if (p.kind === 'banquette') {
    k = 'Banca tapizada'; title = `Banca ${it.id}`; dims = `${fmt(Math.max(rw(it.rect), rh(it.rect)), 2)} × ${fmt(Math.min(rw(it.rect), rh(it.rect)), 2)} m · ${it.seats} asientos`;
  }
  $('#info-k').textContent = k; $('#info-title').textContent = title;
  $('#info-dims').replaceChildren(document.createTextNode(dims), el('small', null, p.kind === 'equipment' ? '  (frente × fondo × alto)' : ''));
  $('#info-flags').replaceChildren(...flags.map(f => el('span', { class: 'flag' + (f === FLAGS.DIM ? ' tbv' : '') }, f)));
  const pn = $('#info-note'); pn.textContent = note; pn.hidden = !note;
  if (COARSE || innerWidth < 760) $('#caption').hidden = true;
  card.hidden = false;
}
