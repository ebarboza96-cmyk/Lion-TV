/* ===================================================================================
   01 model: everything derived from existing.json + layout.json (no three.js).
   Walls/openings/regions/walk-grid/pathfinding, decor placement, tour stops, metrics.
   =================================================================================== */

const DOOR_TYPES = new Set(['door', 'double_acting_door', 'sliding_door', 'service_door', 'opening']);
const HOT_KEYS = ['parrilla', 'cocina_4q', 'plancha', 'freidora_1', 'freidora_2'];
const FOH_NAME = /sal[oó]n|comedor|dining|barra|\bbar\b|caja|entrada|recep|clientes|foh/i;

const MODEL = buildModel();

function buildModel() {
  const M = { warnings: [] };
  M.ceilH = clamp(num(EX.ceiling && EX.ceiling.height_assumed, 3.0), 2.4, 6);
  M.meta = (LAY.meta && typeof LAY.meta === 'object') ? LAY.meta : {};

  /* ---------- premises ---------- */
  let prem = arr(EX.premises_polygon).map(pt).filter(Boolean);
  if (prem.length < 3) {
    const rs = arr(EX.walls).map(w => nrect(w && w.rect)).filter(Boolean);
    const bb = rs.length ? [Math.min(...rs.map(r => r[0])), Math.min(...rs.map(r => r[1])), Math.max(...rs.map(r => r[2])), Math.max(...rs.map(r => r[3]))] : [0, 0, 10, 5];
    prem = [[bb[0], bb[1]], [bb[2], bb[1]], [bb[2], bb[3]], [bb[0], bb[3]]];
    M.warnings.push('Sin premises_polygon: se usa el rectángulo envolvente de los muros.');
  }
  M.prem = prem;
  M.pbb = polyBBox(prem);
  M.premArea = polyArea(prem);
  M.segs = prem.map((p, i) => { const q = prem[(i + 1) % prem.length]; return [p[0], p[1], q[0], q[1]]; });

  /* ---------- existing context ---------- */
  M.columns = arr(EX.columns).map(c => ({ id: str(c && c.id), rect: nrect(c && c.rect), note: str(c && c.note) })).filter(c => c.rect);
  M.shafts = arr(EX.shafts).map(s => ({ id: str(s && s.id), rect: nrect(s && s.rect), note: str(s && s.note) })).filter(s => s.rect);
  M.glazing = arr(EX.glazing).map(g => ({ id: str(g && g.id), kind: str(g && g.kind, 'window'), rect: nrect(g && g.rect), note: str(g && g.note) })).filter(g => g.rect);
  M.stair = EX.stair && nrect(EX.stair.outline) ? { rect: nrect(EX.stair.outline), flights: arr(EX.stair.flights).map(nrect).filter(Boolean) } : null;
  M.doors = arr(EX.doors).filter(d => d && d.kind !== 'context' && Array.isArray(d.opening) && d.opening.length >= 4).map(d => {
    const o = d.opening.map(Number);
    return { id: str(d.id), kind: str(d.kind), a: [o[0], o[1]], b: [o[2], o[3]], width: num(d.width, Math.hypot(o[2] - o[0], o[3] - o[1])), note: str(d.note) };
  }).filter(d => d.a.every(isFinite) && d.b.every(isFinite));
  M.keepouts = arr(EX.keepouts).map(k => ({ id: str(k && k.id), rect: nrect(k && k.rect), note: str(k && k.note) })).filter(k => k.rect);

  /* ---------- demolitions / openings / walls ---------- */
  const dem = arr(LAY.demolish).filter(d => d && typeof d === 'object');
  const gone = new Set(dem.filter(d => typeof d.id === 'string' && !nrect(d.rect)).map(d => d.id));
  const partial = dem.map(d => nrect(d.rect)).filter(Boolean);
  M.openings = arr(LAY.new_openings).filter(o => o && typeof o === 'object').map((o, i) => ({
    id: str(o.id, 'OP' + (i + 1)), type: str(o.type, 'opening'), rect: nrect(o.rect), label: str(o.label), width: num(o.width, null),
    hinge: pt(o.hinge), closed_to: pt(o.closed_to), swing_to: pt(o.swing_to), conditional: !!o.conditional, note: str(o.note),
  })).filter(o => o.rect);
  const doorOps = M.openings.filter(o => DOOR_TYPES.has(o.type));
  const passOps = M.openings.filter(o => o.type === 'pass_window');

  M.demolished = [];
  M.walls = [];        // standing wall pieces (door openings cut) {id, rect, src, kind, type, h, role}
  M.wallsSolid = [];   // same but with door openings closed (for region classification)
  for (const w of arr(EX.walls)) {
    const r = nrect(w && w.rect); if (!r) continue;
    if (gone.has(w.id)) { M.demolished.push({ id: str(w.id), rect: r }); continue; }
    let pieces = [r];
    for (const p of partial) {
      const i = rInter(r, p); if (i) M.demolished.push({ id: str(w.id), rect: i });
      pieces = pieces.flatMap(q => rSub(q, p));
    }
    for (const q of pieces) M.wallsSolid.push(q);
    for (const o of doorOps) pieces = pieces.flatMap(q => rSub(q, o.rect));
    for (const q of pieces) M.walls.push({ id: str(w.id), rect: q, src: 'existing', kind: str(w.kind, 'wall'), type: 'existing', h: M.ceilH });
  }
  M.newWalls = arr(LAY.new_walls).filter(w => w && typeof w === 'object').map((w, i) => ({
    id: str(w.id, 'NW' + (i + 1)), rect: nrect(w.rect), type: str(w.type, 'partition'), role: str(w.role),
    h: clamp(num(w.h, M.ceilH), 0.3, M.ceilH), base_h: clamp(num(w.base_h, 1.0), 0.2, 1.4), note: str(w.note),
  })).filter(w => w.rect);
  for (const w of M.newWalls) {
    M.wallsSolid.push(w.rect);
    let pieces = [w.rect];
    for (const o of doorOps) pieces = pieces.flatMap(q => rSub(q, o.rect));
    for (const q of pieces) M.walls.push({ id: w.id, rect: q, src: 'new', kind: 'new', type: w.type, h: w.h, base_h: w.base_h, role: w.role, parent: w });
  }
  for (const o of doorOps) M.wallsSolid.push(o.rect);

  /* ---------- program ---------- */
  M.equip = arr(LAY.equipment).filter(e => e && typeof e === 'object').map((e, i) => {
    const r = nrect(e.rect); if (!r) return null;
    const key = str(e.key);
    return { id: str(e.id, 'EQ' + (i + 1)), key, label: str(e.label) || KEY_ES[key] || key || 'Equipo', cat: str(e.cat, 'misc'),
      rect: r, h: clamp(num(e.h, 0.9), 0.02, M.ceilH), front: normDir(e.front), clear: Math.max(0, num(e.clear, 0)), tbv: !!e.tbv,
      overhead: !!e.overhead || key === 'hood', stack: str(e.stack_with), note: str(e.note), baffle: !!e.baffle };
  }).filter(Boolean);
  M.byKey = k => M.equip.filter(e => e.key === k);
  M.one = k => M.equip.find(e => e.key === k) || null;
  M.tables = arr(LAY.tables).filter(t => t && typeof t === 'object').map((t, i) => ({ id: str(t.id, 'T' + (i + 1)), rect: nrect(t.rect),
    seats: Math.max(0, Math.round(num(t.seats, 2))), type: str(t.type), join: arr(t.joinable_with).map(String) })).filter(t => t.rect);
  M.chairs = arr(LAY.chairs).filter(c => c && typeof c === 'object').map((c, i) => ({ id: str(c.id, 'CH' + (i + 1)), rect: nrect(c.rect),
    table: str(c.table), facing: normDir(c.facing) })).filter(c => c.rect);
  M.banquettes = arr(LAY.banquettes).filter(b => b && typeof b === 'object').map((b, i) => ({ id: str(b.id, 'BQ' + (i + 1)), rect: nrect(b.rect),
    seats: Math.max(0, Math.round(num(b.seats, 0))), back: normDir(b.back) })).filter(b => b.rect);
  M.zones = arr(LAY.zones).filter(z => z && typeof z === 'object').map((z, i) => {
    const poly = arr(z.poly).map(pt).filter(Boolean); if (poly.length < 3) return null;
    const color = /^#[0-9a-f]{3,8}$/i.test(str(z.color)) ? z.color : ZONE_FALLBACK_COLORS[i % ZONE_FALLBACK_COLORS.length];
    return { id: str(z.id, String.fromCharCode(65 + i)), name: str(z.name), poly, color, prep: !!z.prep, area: polyArea(poly), c: polyCentroid(poly) };
  }).filter(Boolean);
  M.routes = arr(LAY.routes).filter(r => r && typeof r === 'object').map((r, i) => {
    const pts = arr(r.pts).map(pt).filter(Boolean); if (pts.length < 2) return null;
    let len = 0; for (let k = 1; k < pts.length; k++) len += Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]);
    return { id: str(r.id, 'R' + (i + 1)), kind: str(r.kind, 'guest'), label: str(r.label), pts, min_width: num(r.min_width, null), len };
  }).filter(Boolean);
  M.points = {};
  if (LAY.points && typeof LAY.points === 'object') for (const [k, v] of Object.entries(LAY.points)) { const p = pt(v); if (p) M.points[k] = p; }
  M.seats = M.chairs.length + M.banquettes.reduce((s, b) => s + b.seats, 0);

  M.partition = M.newWalls.find(w => w.role === 'kitchen_dining_partition') || M.newWalls.find(w => w.type === 'glass_partition') || null;

  /* ---------- colliders (continuous 2D collision) ---------- */
  const furn = [...M.tables.map(t => t.rect), ...M.banquettes.map(b => b.rect)];
  const eqBlock = M.equip.filter(e => !e.overhead).map(e => e.rect);
  M.colliders = [...M.walls.map(w => w.rect), ...M.columns.map(c => c.rect), ...M.glazing.map(g => g.rect), ...M.shafts.map(s => s.rect),
    ...(M.stair ? [M.stair.rect] : []), ...eqBlock, ...furn];
  M.barriers = [...M.wallsSolid.map(r => ({ r, k: 'wall' })), ...M.columns.map(c => ({ r: c.rect, k: 'column' })), ...M.glazing.map(g => ({ r: g.rect, k: 'glass' }))];

  /* ---------- entrance ---------- */
  const dEnt = M.doors.find(d => d.id === 'D-ENT') || M.doors.find(d => d.kind === 'double') || null;
  M.entranceDoor = dEnt;
  let ent = M.points.entrance || null;
  if (!ent && dEnt) {
    const cx = (dEnt.a[0] + dEnt.b[0]) / 2, cy = (dEnt.a[1] + dEnt.b[1]) / 2;
    const nx = -(dEnt.b[1] - dEnt.a[1]), ny = dEnt.b[0] - dEnt.a[0], L = Math.hypot(nx, ny) || 1;
    for (const s of [0.6, -0.6]) { const x = cx + nx / L * s, y = cy + ny / L * s; if (inPoly(x, y, prem)) { ent = [x, y]; break; } }
  }
  if (!ent) ent = [M.pbb[2] - 0.6, (M.pbb[1] + M.pbb[3]) / 2];
  M.entrance = ent;

  buildGrid(M);
  classifyRegions(M);
  M.partInfo = partitionInfo(M);
  M.decor = resolveDecor(M);
  for (const d of M.decor) if (d.collide) M.colliders.push(d.collide);
  M.stops = buildStops(M);
  M.metrics = computeMetrics(M);
  return M;
}

/* ============================ grid ============================ */
function buildGrid(M) {
  const cell = 0.05, bb = rgrow(M.pbb, 0.15);
  const nx = Math.max(4, Math.ceil((bb[2] - bb[0]) / cell)), ny = Math.max(4, Math.ceil((bb[3] - bb[1]) / cell));
  const G = { x0: bb[0], y0: bb[1], cell, nx, ny, n: nx * ny };
  G.ix = x => Math.floor((x - G.x0) / cell);
  G.iy = y => Math.floor((y - G.y0) / cell);
  G.cx = i => G.x0 + (i + 0.5) * cell;
  G.cy = j => G.y0 + (j + 0.5) * cell;
  G.ok = (i, j) => i >= 0 && j >= 0 && i < nx && j < ny;
  const inside = new Uint8Array(G.n);
  for (let j = 0; j < ny; j++) {           // scanline fill of the premises polygon
    const y = G.cy(j), xs = [];
    for (const s of M.segs) { const [ax, ay, bx, by] = s; if ((ay > y) !== (by > y)) xs.push(ax + (y - ay) * (bx - ax) / (by - ay)); }
    xs.sort((a, b) => a - b);
    for (let k = 0; k + 1 < xs.length; k += 2) {
      const i0 = Math.max(0, Math.ceil((xs[k] - G.x0) / cell - 0.5)), i1 = Math.min(nx - 1, Math.floor((xs[k + 1] - G.x0) / cell - 0.5));
      for (let i = i0; i <= i1; i++) inside[j * nx + i] = 1;
    }
  }
  const paint = (mask, r) => {   // cells overlapping rect
    const i0 = Math.max(0, Math.floor((r[0] - G.x0) / cell)), i1 = Math.min(nx - 1, Math.ceil((r[2] - G.x0) / cell) - 1);
    const j0 = Math.max(0, Math.floor((r[1] - G.y0) / cell)), j1 = Math.min(ny - 1, Math.ceil((r[3] - G.y0) / cell) - 1);
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) mask[j * nx + i] = 1;
  };
  const solid = new Uint8Array(G.n), block = new Uint8Array(G.n);
  for (const r of M.wallsSolid) paint(solid, r);
  for (const c of M.columns) paint(solid, c.rect);
  for (const g of M.glazing) paint(solid, g.rect);
  for (const r of M.colliders) paint(block, r);
  G.inside = inside; G.solid = solid; G.block = block; G.paint = paint;
  // clearance field: distance (m) from each free cell to nearest blocked/outside cell
  const free = new Uint8Array(G.n);
  for (let k = 0; k < G.n; k++) free[k] = inside[k] && !block[k] ? 1 : 0;
  const d2 = edt2(free, nx, ny);
  const clr = new Float32Array(G.n);
  for (let k = 0; k < G.n; k++) clr[k] = free[k] ? Math.max(0, Math.sqrt(d2[k]) * cell - cell / 2) : 0;
  G.free = free; G.clr = clr;
  M.grid = G;
  M.walkR = 0.24;
  M.clearanceAt = (x, y) => { const i = G.ix(x), j = G.iy(y); return G.ok(i, j) ? clr[j * nx + i] : 0; };
  M.isWalk = (x, y, r = M.walkR) => M.clearanceAt(x, y) >= r;
  M.isInside = (x, y) => inPoly(x, y, M.prem);
  M.snap = (x, y, r = M.walkR, maxD = 4) => {
    const i0 = G.ix(x), j0 = G.iy(y); let best = null, bd = Infinity;
    const R = Math.ceil(maxD / cell);
    for (let rad = 0; rad <= R; rad++) {
      for (let dj = -rad; dj <= rad; dj++) for (let di = -rad; di <= rad; di++) {
        if (Math.max(Math.abs(di), Math.abs(dj)) !== rad) continue;
        const i = i0 + di, j = j0 + dj; if (!G.ok(i, j)) continue;
        if (clr[j * nx + i] >= r) { const d = Math.hypot(G.cx(i) - x, G.cy(j) - y); if (d < bd) { bd = d; best = [G.cx(i), G.cy(j)]; } }
      }
      if (best && bd <= rad * cell) break;
    }
    return best;
  };
  M.los = (a, b, r = M.walkR) => {
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]), n = Math.max(1, Math.ceil(L / (cell * 0.7)));
    for (let k = 0; k <= n; k++) { const t = k / n; if (!M.isWalk(lerp(a[0], b[0], t), lerp(a[1], b[1], t), r)) return false; }
    return true;
  };
  M.seeLine = (a, b, ignore) => { // wall line of sight (walls/columns only)
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]), n = Math.max(1, Math.ceil(L / (cell * 0.7)));
    for (let k = 1; k < n; k++) {
      const t = k / n, x = lerp(a[0], b[0], t), y = lerp(a[1], b[1], t);
      if (ignore && x >= ignore[0] && x <= ignore[2] && y >= ignore[1] && y <= ignore[3]) continue;
      const i = G.ix(x), j = G.iy(y); if (!G.ok(i, j) || solid[j * nx + i]) return false;
    }
    return true;
  };
  M.findPath = (a, b, r = M.walkR) => findPath(M, a, b, r);
}

function edt2(free, nx, ny) {
  const INF = 1e20, n = Math.max(nx, ny);
  const f = new Float64Array(n), d = new Float64Array(n), v = new Int32Array(n), z = new Float64Array(n + 1);
  const out = new Float32Array(nx * ny);
  const pass = len => {
    let k = 0; v[0] = 0; z[0] = -INF; z[1] = INF;
    for (let q = 1; q < len; q++) {
      let s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]);
      while (s <= z[k]) { k--; s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]); }
      k++; v[k] = q; z[k] = s; z[k + 1] = INF;
    }
    k = 0;
    for (let q = 0; q < len; q++) { while (z[k + 1] < q) k++; d[q] = (q - v[k]) * (q - v[k]) + f[v[k]]; }
  };
  for (let i = 0; i < nx; i++) { for (let j = 0; j < ny; j++) f[j] = free[j * nx + i] ? INF : 0; pass(ny); for (let j = 0; j < ny; j++) out[j * nx + i] = d[j]; }
  for (let j = 0; j < ny; j++) { for (let i = 0; i < nx; i++) f[i] = out[j * nx + i]; pass(nx); for (let i = 0; i < nx; i++) out[j * nx + i] = d[i]; }
  return out;
}

function findPath(M, a, b, r) {
  const G = M.grid, nx = G.nx;
  const sa = M.snap(a[0], a[1], r, 1.5), sb = M.snap(b[0], b[1], r, 2.5);
  if (!sa || !sb) return null;
  const s = G.iy(sa[1]) * nx + G.ix(sa[0]), t = G.iy(sb[1]) * nx + G.ix(sb[0]);
  const walk = k => G.clr[k] >= r;
  const g = new Float32Array(G.n).fill(Infinity), came = new Int32Array(G.n).fill(-1), closed = new Uint8Array(G.n);
  const heap = [], hf = [];
  const push = (k, f) => { heap.push(k); hf.push(f); let i = heap.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (hf[p] <= hf[i]) break; [heap[p], heap[i]] = [heap[i], heap[p]]; [hf[p], hf[i]] = [hf[i], hf[p]]; i = p; } };
  const pop = () => { const top = heap[0]; const lk = heap.pop(), lf = hf.pop(); if (heap.length) { heap[0] = lk; hf[0] = lf; let i = 0; for (;;) { const l = 2 * i + 1, rr = l + 1; let m = i; if (l < heap.length && hf[l] < hf[m]) m = l; if (rr < heap.length && hf[rr] < hf[m]) m = rr; if (m === i) break; [heap[m], heap[i]] = [heap[i], heap[m]]; [hf[m], hf[i]] = [hf[i], hf[m]]; i = m; } } return top; };
  const tx = t % nx, ty = (t / nx) | 0;
  const hfun = k => { const dx = Math.abs(k % nx - tx), dy = Math.abs(((k / nx) | 0) - ty); return (dx + dy) + (Math.SQRT2 - 2) * Math.min(dx, dy); };
  g[s] = 0; push(s, hfun(s));
  const N8 = [[1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1], [1, 1, Math.SQRT2], [1, -1, Math.SQRT2], [-1, 1, Math.SQRT2], [-1, -1, Math.SQRT2]];
  let found = false, iter = 0;
  while (heap.length && iter++ < 400000) {
    const k = pop(); if (closed[k]) continue; closed[k] = 1;
    if (k === t) { found = true; break; }
    const i = k % nx, j = (k / nx) | 0;
    for (const [di, dj, c] of N8) {
      const ii = i + di, jj = j + dj; if (ii < 0 || jj < 0 || ii >= nx || jj >= G.ny) continue;
      const kk = jj * nx + ii; if (closed[kk] || !walk(kk)) continue;
      if (di && dj && (!walk(j * nx + ii) || !walk(jj * nx + i))) continue;
      // prefer the middle of aisles a little (cost grows near obstacles)
      const ng = g[k] + c * (1 + 0.6 / (1 + 12 * G.clr[kk]));
      if (ng < g[kk]) { g[kk] = ng; came[kk] = k; push(kk, ng + hfun(kk)); }
    }
  }
  if (!found) return null;
  const raw = []; for (let k = t; k !== -1; k = came[k]) raw.push([G.cx(k % nx), G.cy((k / nx) | 0)]);
  raw.reverse();
  raw[0] = [a[0], a[1]]; raw[raw.length - 1] = [b[0], b[1]];
  // string pulling
  const out = [raw[0]]; let i = 0;
  while (i < raw.length - 1) {
    let j = raw.length - 1;
    while (j > i + 1 && !M.los(raw[i], raw[j], r * 0.92)) j--;
    out.push(raw[j]); i = j;
  }
  return out;
}

/* ============================ regions ============================ */
function classifyRegions(M) {
  const G = M.grid, nx = G.nx, region = new Uint8Array(G.n);   // 0 out, 1 FOH, 2 BOH
  let insideCount = 0; for (let k = 0; k < G.n; k++) if (G.inside[k]) { region[k] = 2; insideCount++; }
  const open = k => G.inside[k] && !G.solid[k];
  let seed = -1, bd = Infinity;
  const ei = G.ix(M.entrance[0]), ej = G.iy(M.entrance[1]);
  for (let j = Math.max(0, ej - 30); j < Math.min(G.ny, ej + 30); j++) for (let i = Math.max(0, ei - 30); i < Math.min(nx, ei + 30); i++) {
    const k = j * nx + i; if (!open(k)) continue; const d = (i - ei) ** 2 + (j - ej) ** 2; if (d < bd) { bd = d; seed = k; }
  }
  let fohCount = 0;
  if (seed >= 0) {
    const q = [seed]; const seen = new Uint8Array(G.n); seen[seed] = 1;
    while (q.length) {
      const k = q.pop(); region[k] = 1; fohCount++;
      const i = k % nx, j = (k / nx) | 0;
      for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const ii = i + di, jj = j + dj; if (!G.ok(ii, jj)) continue; const kk = jj * nx + ii;
        if (!seen[kk] && open(kk)) { seen[kk] = 1; q.push(kk); }
      }
    }
  }
  M.regionMode = 'flood';
  if (seed < 0 || fohCount > 0.85 * insideCount || fohCount < 0.05 * insideCount) {
    // leaked (kitchen open to dining) -> use zones: zones holding tables or named like dining are FOH
    M.regionMode = 'zones';
    const fohZones = M.zones.filter(z => FOH_NAME.test(z.name) || M.tables.some(t => inPoly(rcx(t.rect), rcy(t.rect), z.poly)));
    const bohZones = M.zones.filter(z => !fohZones.includes(z));
    for (let k = 0; k < G.n; k++) {
      if (!G.inside[k]) continue;
      const x = G.cx(k % nx), y = G.cy((k / nx) | 0);
      region[k] = bohZones.some(z => inPoly(x, y, z.poly)) ? 2 : 1;
    }
    if (!M.zones.length) M.regionMode = 'none';
  }
  G.region = region;
  M.regionAt = (x, y) => { const i = G.ix(x), j = G.iy(y); return G.ok(i, j) ? region[j * nx + i] : 0; };
  let b = [Infinity, Infinity, -Infinity, -Infinity], cnt = 0;
  for (let k = 0; k < G.n; k++) if (region[k] === 1) { const x = G.cx(k % nx), y = G.cy((k / nx) | 0); b = [Math.min(b[0], x), Math.min(b[1], y), Math.max(b[2], x), Math.max(b[3], y)]; cnt++; }
  M.fohBB = cnt ? rgrow(b, G.cell / 2) : M.pbb;
  M.fohArea = cnt * G.cell * G.cell;
  const din = [...M.tables, ...M.banquettes, ...M.chairs].map(t => t.rect).filter(r => M.regionAt(rcx(r), rcy(r)) === 1);
  M.dining = din.length ? [Math.min(...din.map(r => r[0])), Math.min(...din.map(r => r[1])), Math.max(...din.map(r => r[2])), Math.max(...din.map(r => r[3]))] : M.fohBB;
  M.diningAxis = rw(M.dining) >= rh(M.dining) ? 'x' : 'y';
  // rectangles (greedy meshing) of BOH floor for the tiled floor
  M.bohRects = greedyRects(G, k => region[k] === 2);
}

function greedyRects(G, pred) {
  const nx = G.nx, used = new Uint8Array(G.n), out = [];
  for (let j = 0; j < G.ny; j++) for (let i = 0; i < nx; i++) {
    const k = j * nx + i; if (used[k] || !pred(k)) continue;
    let w = 1; while (i + w < nx && !used[k + w] && pred(k + w)) w++;
    let h = 1;
    outer: while (j + h < G.ny) { for (let d = 0; d < w; d++) { const kk = (j + h) * nx + i + d; if (used[kk] || !pred(kk)) break outer; } h++; }
    for (let dj = 0; dj < h; dj++) for (let d = 0; d < w; d++) used[(j + dj) * nx + i + d] = 1;
    out.push([G.x0 + i * G.cell, G.y0 + j * G.cell, G.x0 + (i + w) * G.cell, G.y0 + (j + h) * G.cell]);
  }
  return out;
}

/* ray against wall barriers (+ premises edges); returns {t, k} */
function castRay(M, x, y, dx, dy, maxT = 40, kinds) {
  let best = maxT, k = null;
  for (const b of M.barriers) { if (kinds && !kinds.includes(b.k)) continue; const t = rayRect(x, y, dx, dy, b.r); if (t >= 0 && t < best) { best = t; k = b.k; } }
  for (const s of M.segs) { const t = raySeg(x, y, dx, dy, s[0], s[1], s[2], s[3]); if (t >= 0 && t < best) { best = t; k = 'edge'; } }
  return { t: best, k };
}

/* side of a rect that faces the open room */
function openFace(M, r) {
  const cands = rw(r) >= rh(r) ? ['N', 'S'] : ['E', 'W'];
  let best = cands[0], bt = -1;
  for (const f of cands) {
    const [dx, dy] = DIRV[f];
    const ox = rcx(r) + dx * (rw(r) / 2 + 0.02), oy = rcy(r) + dy * (rh(r) / 2 + 0.02);
    const t = M.isInside(ox, oy) ? castRay(M, ox, oy, dx, dy, 20).t : -1;
    if (t > bt) { bt = t; best = f; }
  }
  return best;
}

/* front of equipment: data, else the side with most free space */
function itemFront(M, e) {
  if (e.front) return e.front;
  let best = 'S', bt = -1;
  for (const f of ['N', 'S', 'E', 'W']) {
    const [dx, dy] = DIRV[f];
    const ox = rcx(e.rect) + dx * (rw(e.rect) / 2 + 0.02), oy = rcy(e.rect) + dy * (rh(e.rect) / 2 + 0.02);
    if (!M.isInside(ox, oy)) continue;
    const t = castRay(M, ox, oy, dx, dy, 20).t;
    if (t > bt) { bt = t; best = f; }
  }
  return best;
}

/* ============================ partition ============================ */
function partitionInfo(M) {
  const P = M.partition; if (!P) return null;
  const r = P.rect, along = rh(r) >= rw(r) ? 'y' : 'x';
  // which face is the dining side?
  const probe = f => { const [dx, dy] = DIRV[f]; const x = rcx(r) + dx * (Math.min(rw(r), rh(r)) / 2 + 0.3), y = rcy(r) + dy * (Math.min(rw(r), rh(r)) / 2 + 0.3); return M.regionAt(x, y); };
  const faces = along === 'y' ? ['E', 'W'] : ['N', 'S'];
  let face = faces.find(f => probe(f) === 1);
  if (!face) { const d0 = Math.hypot(rcx(r) + DIRV[faces[0]][0] - M.entrance[0], rcy(r) + DIRV[faces[0]][1] - M.entrance[1]), d1 = Math.hypot(rcx(r) + DIRV[faces[1]][0] - M.entrance[0], rcy(r) + DIRV[faces[1]][1] - M.entrance[1]); face = d0 < d1 ? faces[0] : faces[1]; }
  const a0 = along === 'y' ? r[1] : r[0], a1 = along === 'y' ? r[3] : r[2];
  const iv = o => { const i = rInter(rgrow(r, 0.02), o.rect); return i ? (along === 'y' ? [i[1], i[3]] : [i[0], i[2]]) : null; };
  const doors = M.openings.filter(o => DOOR_TYPES.has(o.type)).map(iv).filter(Boolean);
  let passes = M.openings.filter(o => o.type === 'pass_window').map(iv).filter(Boolean);
  // solid spans (no doors)
  let spans = [[a0, a1]];
  for (const d of doors) spans = spans.flatMap(s => (d[1] <= s[0] || d[0] >= s[1]) ? [s] : [[s[0], d[0]], [d[1], s[1]]].filter(q => q[1] - q[0] > 0.05));
  // implicit pass window where a "pass" item touches the partition on the kitchen side
  let implicitPass = false;
  if (!passes.length && P.type === 'glass_partition') {
    const ps = M.byKey('pass').find(e => rDist(e.rect, r) < 0.3);
    if (ps) {
      const pa = along === 'y' ? [ps.rect[1], ps.rect[3]] : [ps.rect[0], ps.rect[2]];
      const sp = spans.map(s => [Math.max(s[0], pa[0]), Math.min(s[1], pa[1])]).filter(s => s[1] - s[0] > 0.6).sort((p, q) => (q[1] - q[0]) - (p[1] - p[0]))[0];
      if (sp) { const c = (sp[0] + sp[1]) / 2, L = Math.min(1.6, sp[1] - sp[0] - 0.2); passes = [[c - L / 2, c + L / 2]]; implicitPass = true; }
    }
  }
  const glassTop = clamp(P.h - 0.5, P.base_h + 0.9, M.ceilH - 0.35);
  return { wall: P, rect: r, along, face, a0, a1, doors, passes, spans, implicitPass, base_h: P.base_h, glassTop, h: P.h,
    t0: along === 'y' ? r[0] : r[1], t1: along === 'y' ? r[2] : r[3] };
}

/* ============================ decor ============================ */
const DECOR_TYPES = ['slat_wall', 'sign', 'poster', 'sconce', 'pendant', 'planter', 'firewood_niche'];
function resolveDecor(M) {
  const out = [];
  for (const d of arr(LAY.decor)) {
    if (!d || typeof d !== 'object' || !DECOR_TYPES.includes(d.type)) continue;
    let r = nrect(d.rect);
    const p = pt(d.pos);
    if (!r && p) r = [p[0] - 0.05, p[1] - 0.05, p[0] + 0.05, p[1] + 0.05];
    if (!r) continue;
    out.push({ type: d.type, rect: r, face: normDir(d.face) || normDir(d.facing) || openFace(M, r), text: str(d.text), h: num(d.h, null),
      z: num(d.z, null), size: num(d.size, null), style: str(d.style), text_at: num(d.text_at, null), src: 'layout' });
  }
  if (LAY.decor_defaults === false) return out;
  const has = t => out.some(d => d.type === t);
  try { autoDecor(M, out, has); } catch (e) { console.warn('LAVA: decor automático incompleto', e); }
  return out;
}

function wallRuns(M, side, a0, a1, mid) {
  // axis x only for dining long axis along x; generalised by swapping when axis is y
  const ax = M.diningAxis, runs = []; let cur = null;
  for (let a = a0; a <= a1 + 1e-6; a += 0.1) {
    const x = ax === 'x' ? a : mid, y = ax === 'x' ? mid : a;
    const dx = ax === 'x' ? 0 : side, dy = ax === 'x' ? side : 0;
    const h = castRay(M, x, y, dx, dy, 12);
    const face = (ax === 'x' ? y : x) + side * h.t;
    const ok = h.k === 'wall' || h.k === 'edge';
    if (ok && cur && Math.abs(face - cur.face) < 0.03) { cur.a1 = a; }
    else { if (cur) runs.push(cur); cur = ok ? { a0: a, a1: a, face } : null; }
  }
  if (cur) runs.push(cur);
  return runs.map(r => ({ a0: r.a0 - 0.05, a1: r.a1 + 0.05, face: r.face })).filter(r => r.a1 - r.a0 > 0.8);
}

function autoDecor(M, out, has) {
  const D = M.dining, F = M.fohBB, ax = M.diningAxis;
  const midPerp = ax === 'x' ? rcy(D) : rcx(D);
  const lo = (ax === 'x' ? F[0] : F[1]) + 0.1, hi = (ax === 'x' ? F[2] : F[3]) - 0.1;
  const entA = ax === 'x' ? M.entrance[0] : M.entrance[1];
  const entAtHigh = Math.abs(entA - hi) < Math.abs(entA - lo);
  const mk = (a0, a1, p0, p1) => ax === 'x' ? [a0, Math.min(p0, p1), a1, Math.max(p0, p1)] : [Math.min(p0, p1), a0, Math.max(p0, p1), a1];
  const faceDir = side => ax === 'x' ? (side > 0 ? 'N' : 'S') : (side > 0 ? 'W' : 'E');   // decor on wall at +side faces back (-side)
  const tall = M.equip.filter(e => !e.overhead && e.h > 1.2);
  const runsA = wallRuns(M, +1, lo, hi, midPerp);   // "south" (render left) – slat wall
  const runsB = wallRuns(M, -1, lo, hi, midPerp);   // "north" (render right) – posters & sconces
  const bqAlong = (face, side) => M.banquettes.some(b => { const e = side > 0 ? (ax === 'x' ? b.rect[3] : b.rect[2]) : (ax === 'x' ? b.rect[1] : b.rect[0]); return Math.abs(e - face) < 0.12; });
  const slatRun = runsA.slice().sort((p, q) => (q.a1 - q.a0) - (p.a1 - p.a0))[0];

  if (!has('slat_wall') && slatRun && slatRun.a1 - slatRun.a0 > 1.5) {
    const a0 = slatRun.a0 + 0.25, a1 = slatRun.a1 - 0.25;
    out.push({ type: 'slat_wall', rect: mk(a0, a1, slatRun.face - 0.075, slatRun.face), face: faceDir(+1), text: 'LAVA',
      z: bqAlong(slatRun.face, +1) ? 1.0 : 0.9, h: M.ceilH - 0.16, text_at: entAtHigh ? 0.74 : 0.26, src: 'auto' });
  }
  if (!has('poster') && runsB.length) {
    // posters near the kitchen end, clear of tall equipment
    const freeRuns = [];
    for (const r of runsB) {
      let segs = [[r.a0 + 0.2, r.a1 - 0.2]];
      for (const e of tall) {
        const near = ax === 'x' ? Math.min(Math.abs(e.rect[1] - r.face), Math.abs(e.rect[3] - r.face)) : Math.min(Math.abs(e.rect[0] - r.face), Math.abs(e.rect[2] - r.face));
        if (near > 0.6) continue;
        const ea = ax === 'x' ? [e.rect[0] - 0.2, e.rect[2] + 0.2] : [e.rect[1] - 0.2, e.rect[3] + 0.2];
        segs = segs.flatMap(s => (ea[1] <= s[0] || ea[0] >= s[1]) ? [s] : [[s[0], ea[0]], [ea[1], s[1]]]);
      }
      for (const s of segs) if (s[1] - s[0] > 2.6) freeRuns.push({ a0: s[0], a1: s[1], face: r.face });
    }
    freeRuns.sort((p, q) => entAtHigh ? p.a0 - q.a0 : q.a1 - p.a1);
    const run = freeRuns[0];
    if (run) {
      const W = 0.74, gap = 0.16, total = 3 * W + 2 * gap;
      let start = entAtHigh ? run.a0 + 0.35 : run.a1 - 0.35 - total;
      start = clamp(start, run.a0, run.a1 - total);
      const texts = entAtHigh ? ['vaca', 'GOOD MEAT|GOOD PEOPLE', 'cerdo'] : ['cerdo', 'GOOD MEAT|GOOD PEOPLE', 'vaca'];
      texts.forEach((t, i) => out.push({ type: 'poster', rect: mk(start + i * (W + gap), start + i * (W + gap) + W, run.face, run.face + 0.03), face: faceDir(-1), text: t, h: 1.72, size: 1.0, src: 'auto' }));
    }
  }
  if (!has('sconce')) {
    for (const r of runsB) {
      const L = r.a1 - r.a0; const n = Math.max(1, Math.round(L / 2.3)); const step = L / n;
      for (let i = 0; i < n; i++) { const a = r.a0 + step * (i + 0.5); if (a - r.a0 < 0.4 || r.a1 - a < 0.4) continue; out.push({ type: 'sconce', rect: mk(a - 0.08, a + 0.08, r.face, r.face + 0.3), face: faceDir(-1), h: 2.2, src: 'auto' }); }
    }
  }
  const PI = M.partInfo;
  if (!has('sign') && PI) {
    const span = PI.spans.slice().sort((p, q) => (q[1] - q[0]) - (p[1] - p[0]))[0] || [PI.a0, PI.a1];
    const c = (span[0] + span[1]) / 2, L = Math.min(span[1] - span[0] - 0.3, 3.2);
    const [dx, dy] = DIRV[PI.face];
    const f = (PI.along === 'y' ? (dx > 0 ? PI.t1 : PI.t0) : (dy > 0 ? PI.t1 : PI.t0)) + (dx + dy) * 0.021;   // fascia face (+2 cm cladding)
    const rect = PI.along === 'y' ? [Math.min(f, f + dx * 0.06), c - L / 2, Math.max(f, f + dx * 0.06), c + L / 2] : [c - L / 2, Math.min(f, f + dy * 0.06), c + L / 2, Math.max(f, f + dy * 0.06)];
    out.push({ type: 'sign', rect, face: PI.face, text: 'LAVA', h: (PI.glassTop + M.ceilH) / 2, size: clamp((M.ceilH - PI.glassTop) * 0.62, 0.22, 0.56), src: 'auto' });
  }
  if (!has('pendant')) {
    if (PI) {
      let sp = PI.passes.length ? PI.passes : [PI.spans.slice().sort((p, q) => (q[1] - q[0]) - (p[1] - p[0]))[0] || [PI.a0, PI.a1]];
      const pass = M.byKey('pass').find(e => rDist(e.rect, PI.rect) < 0.5);
      if (pass) { const pa = PI.along === 'y' ? [pass.rect[1], pass.rect[3]] : [pass.rect[0], pass.rect[2]]; sp = [[Math.max(pa[0], PI.a0), Math.min(pa[1], PI.a1)]]; }
      const [dx, dy] = DIRV[PI.face];
      const k = PI.along === 'y' ? (dx > 0 ? PI.t0 - 0.4 : PI.t1 + 0.4) : (dy > 0 ? PI.t0 - 0.4 : PI.t1 + 0.4);
      for (const s of sp) {
        const L = s[1] - s[0], n = clamp(Math.round(L / 0.75), 1, 6), step = L / n;
        for (let i = 0; i < n; i++) { const a = s[0] + step * (i + 0.5); const p = PI.along === 'y' ? [k, a] : [a, k]; out.push({ type: 'pendant', rect: [p[0] - 0.12, p[1] - 0.12, p[0] + 0.12, p[1] + 0.12], face: PI.face, h: 1.95, style: 'dome', src: 'auto' }); }
      }
    }
    if (slatRun) {
      for (const t of M.tables) {
        const c = [rcx(t.rect), rcy(t.rect)];
        const dd = Math.abs((ax === 'x' ? c[1] : c[0]) - slatRun.face);
        if (dd < 1.6 && M.regionAt(c[0], c[1]) === 1) out.push({ type: 'pendant', rect: [c[0] - 0.08, c[1] - 0.08, c[0] + 0.08, c[1] + 0.08], face: 'S', h: 1.85, style: 'cylinder', src: 'auto' });
      }
    }
  }
  if (PI && PI.wall.type === 'glass_partition' && !has('firewood_niche') && !has('planter')) {
    const span = PI.spans.slice().sort((p, q) => (q[1] - q[0]) - (p[1] - p[0]))[0];
    if (span) {
      const L = span[1] - span[0];
      const mkp = (a0, a1) => PI.along === 'y' ? [PI.t0, a0, PI.t1, a1] : [a0, PI.t0, a1, PI.t1];
      const top = PI.base_h - 0.12;
      if (L >= 2.2) {
        const nW = clamp(L * 0.28, 0.6, 1.25), m = 0.14, g = 0.12;
        const pl0 = span[0] + m + nW + g, pl1 = span[1] - m - nW - g;
        out.push({ type: 'firewood_niche', rect: mkp(span[0] + m, span[0] + m + nW), face: PI.face, z: 0.12, h: top, src: 'auto' });
        if (pl1 - pl0 > 0.4) out.push({ type: 'planter', rect: mkp(pl0, pl1), face: PI.face, h: PI.base_h, src: 'auto' });
        out.push({ type: 'firewood_niche', rect: mkp(span[1] - m - nW, span[1] - m), face: PI.face, z: 0.12, h: top, src: 'auto' });
      } else if (L >= 0.8) {
        const c = (span[0] + span[1]) / 2, w = Math.min(0.9, L - 0.2);
        out.push({ type: 'firewood_niche', rect: mkp(c - w / 2, c + w / 2), face: PI.face, z: 0.12, h: top, src: 'auto' });
      }
    }
  }
}

/* ============================ tour ============================ */
function viewpoint(M, rect, front, opt = {}) {
  const cx = rcx(rect), cy = rcy(rect);
  const base = front ? [DIRV[front]] : [[0, 1], [0, -1], [1, 0], [-1, 0]];
  const dists = opt.dists || [1.8, 2.2, 1.5, 2.7, 1.2, 3.2, 0.95];
  const rots = [0, 0.45, -0.45, 0.85, -0.85, 1.2, -1.2];
  for (const strict of [true, false]) {
    for (const dist of dists) for (const rot of rots) for (const b of base) {
      const dx = b[0] * Math.cos(rot) - b[1] * Math.sin(rot), dy = b[0] * Math.sin(rot) + b[1] * Math.cos(rot);
      const tx = Math.abs(dx) > 1e-6 ? (rw(rect) / 2) / Math.abs(dx) : Infinity, ty = Math.abs(dy) > 1e-6 ? (rh(rect) / 2) / Math.abs(dy) : Infinity;
      const te = Math.min(tx, ty);
      const p = [cx + dx * (te + dist), cy + dy * (te + dist)];
      if (!M.isWalk(p[0], p[1], 0.27)) continue;
      if (!M.seeLine(p, [cx, cy], rgrow(rect, 0.06))) continue;
      if (strict) { // nothing tall in between
        const L = Math.hypot(cx - p[0], cy - p[1]); let ok = true;
        for (let s = 0.3; s < L - 0.1 && ok; s += 0.1) {
          const x = lerp(p[0], cx, s / L), y = lerp(p[1], cy, s / L);
          if (x >= rect[0] - 0.05 && x <= rect[2] + 0.05 && y >= rect[1] - 0.05 && y <= rect[3] + 0.05) break;
          if (M.equip.some(e => !e.overhead && e.h > 1.3 && x >= e.rect[0] && x <= e.rect[2] && y >= e.rect[1] && y <= e.rect[3])) ok = false;
        }
        if (!ok) continue;
      }
      return p;
    }
  }
  return M.snap(cx, cy, 0.27, 5) || [cx, cy];
}

function segsCross(a, b) {
  const ccw = (p, q, r) => (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0]);
  for (let i = 1; i < a.length; i++) for (let j = 1; j < b.length; j++) {
    const p1 = a[i - 1], p2 = a[i], q1 = b[j - 1], q2 = b[j];
    const d1 = ccw(q1, q2, p1), d2 = ccw(q1, q2, p2), d3 = ccw(p1, p2, q1), d4 = ccw(p1, p2, q2);
    if (((d1 > 0) !== (d2 > 0)) && ((d3 > 0) !== (d4 > 0))) return true;
  }
  return false;
}

function buildStops(M) {
  const custom = arr(LAY.tour).filter(s => s && typeof s === 'object' && pt(s.pos));
  if (custom.length) {
    return custom.map((s, i) => {
      let pos = pt(s.pos); if (!M.isWalk(pos[0], pos[1], 0.2)) pos = M.snap(pos[0], pos[1], 0.22, 3) || pos;
      const look = pt(s.look) || [pos[0] - 1, pos[1]];
      return { id: str(s.id, 's' + (i + 1)), title: str(s.title, 'Parada ' + (i + 1)), text: str(s.text), flags: arr(s.flags).map(String),
        pos, look, lookH: clamp(num(s.look_h, num(s.h, 1.3)), 0, M.ceilH) };
    });
  }
  const S = [];
  const tb = list => list.some(e => e && e.tbv) ? [FLAGS.DIM] : [];
  const parr = M.one('parrilla'), hood = M.one('hood');
  const hot = HOT_KEYS.flatMap(k => M.byKey(k));
  const kitchenLook = parr ? [rcx(parr.rect), rcy(parr.rect)] : M.partInfo ? [rcx(M.partInfo.rect), rcy(M.partInfo.rect)] : [rcx(M.pbb), rcy(M.pbb)];
  const distTo = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  // 1 Entrada
  {
    const pos = M.isWalk(M.entrance[0], M.entrance[1], 0.2) ? M.entrance.slice() : (M.snap(M.entrance[0], M.entrance[1], 0.22, 3) || M.entrance.slice());
    const d = distTo(pos, kitchenLook);
    S.push({ id: 'entrada', title: 'Entrada', pos, look: kitchenLook, lookH: 1.42,
      text: `Desde la puerta, el eje del salón remata en la cocina a la vista: el fuego${parr ? ' de la parrilla' : ''}, enmarcado por el vidrio y el letrero LΛVΛ, es lo primero que ve el cliente (a ${fmt(d, 1)} m).`,
      flags: [] });
  }
  // 2 Salón
  if (M.tables.length || M.banquettes.length) {
    const D = M.dining, ax = M.diningAxis;
    const entHigh = ax === 'x' ? Math.abs(M.entrance[0] - D[2]) < Math.abs(M.entrance[0] - D[0]) : Math.abs(M.entrance[1] - D[3]) < Math.abs(M.entrance[1] - D[1]);
    const f = entHigh ? 0.62 : 0.38;
    const guess = ax === 'x' ? [lerp(D[0], D[2], f), rcy(D)] : [rcx(D), lerp(D[1], D[3], f)];
    const pos = M.snap(guess[0], guess[1], 0.3, 3) || guess;
    const slat = M.decor.find(d => d.type === 'slat_wall');
    let look;
    if (slat) { const t = slat.text_at != null ? slat.text_at : 0.5; look = rw(slat.rect) >= rh(slat.rect) ? [lerp(slat.rect[0], slat.rect[2], t * 0.6 + 0.2), rcy(slat.rect)] : [rcx(slat.rect), lerp(slat.rect[1], slat.rect[3], t * 0.6 + 0.2)]; look = [lerp(look[0], kitchenLook[0], 0.25), lerp(look[1], kitchenLook[1], 0.08)]; }
    else look = ax === 'x' ? [lerp(D[0], D[2], 1 - f), D[3]] : [D[2], lerp(D[1], D[3], 1 - f)];
    const nT = M.tables.length, sizes = [...new Set(M.tables.map(t => t.seats))].sort((a, b) => a - b);
    S.push({ id: 'salon', title: 'Salón', pos, look, lookH: 1.25,
      text: `${M.seats} asientos: ${M.banquettes.length ? 'bancas corridas tapizadas en verde salvia, ' : ''}${nT} mesa${nT === 1 ? '' : 's'} de ${sizes.join(' y ')} personas${M.tables.some(t => t.join.length) ? ' que se pueden unir' : ''} y sillas verde salvia con patas de latón. Celosía de madera retroiluminada en el muro sur; concreto, apliques y afiches en el muro norte; cielo expuesto negro a ${fmt(M.ceilH, 2)} m.`,
      flags: [FLAGS.SITE] });
  }
  // 3 Barra / Caja / Pase
  {
    const bar = M.one('barra') || M.one('pos') || M.one('pass') || M.one('back_bar');
    if (bar) {
      const f = itemFront(M, bar);
      const pos = viewpoint(M, bar.rect, M.regionAt(rcx(bar.rect) + DIRV[f][0] * 1.2, rcy(bar.rect) + DIRV[f][1] * 1.2) === 1 ? f : null, { dists: [1.7, 2.1, 1.4, 2.6] });
      const pass = M.one('pass'), pos_ = M.one('pos');
      S.push({ id: 'barra', title: 'Barra / Caja / Pase', pos, look: [rcx(bar.rect), rcy(bar.rect)], lookH: 1.05,
        text: `Barra de ${fmt(Math.max(rw(bar.rect), rh(bar.rect)), 2)} m con caja${pos_ ? ' (POS)' : ''} y bebidas${pass ? `; el pase de ${fmt(Math.max(rw(pass.rect), rh(pass.rect)), 2)} m conecta la línea caliente con el salón para que los platos salgan sin que el equipo de cocina cruce las mesas` : ''}.`,
        flags: tb([bar, pass, pos_]) });
    }
  }
  // 4 Show kitchen
  if (parr) {
    const f = itemFront(M, parr);
    const pos = viewpoint(M, parr.rect, f, { dists: [Math.max(1.4, parr.clear + 0.25), 1.9, 1.2, 2.4] });
    const L = Math.max(rw(parr.rect), rh(parr.rect));
    const hoodL = hood ? Math.max(rw(hood.rect), rh(hood.rect)) : null;
    S.push({ id: 'parrilla', title: 'Show kitchen · parrilla', pos, look: [rcx(parr.rect), rcy(parr.rect)], lookH: 0.95,
      text: `Parrilla argentina de ${fmt(L, 2)} m a leña y carbón, con brasero y parrillas regulables, a la vista del salón a través del vidrio.${hoodL ? ` Campana de ${fmt(hoodL, 2)} m sobre toda la línea caliente.` : ''}`,
      flags: [FLAGS.EXTRACTION, ...tb([parr])] });
  }
  // 5 Cocina caliente
  if (hot.length) {
    const bb = [Math.min(...hot.map(e => e.rect[0])), Math.min(...hot.map(e => e.rect[1])), Math.max(...hot.map(e => e.rect[2])), Math.max(...hot.map(e => e.rect[3]))];
    const f = itemFront(M, hot[0]); const [nx, ny] = DIRV[f];
    const alongY = rh(bb) >= rw(bb);
    const run = alongY ? rh(bb) : rw(bb);
    const aisle = Math.max(0.7, Math.min(1.3, hot.reduce((m, e) => Math.max(m, e.clear), 0.9)) * 0.75);
    const frontC = [rcx(bb) + nx * (rw(bb) / 2 + aisle), rcy(bb) + ny * (rh(bb) / 2 + aisle)];
    const endA = alongY ? [frontC[0], bb[3] + 0.3] : [bb[2] + 0.3, frontC[1]];
    const endB = alongY ? [frontC[0], bb[1] + 0.3] : [bb[0] + 0.3, frontC[1]];
    let pos = null, look = null;
    for (const [p, q] of [[endA, endB], [endB, endA]]) { const s = M.snap(p[0], p[1], 0.25, 1.2); if (s) { pos = s; look = [q[0] - nx * aisle * 0.9, q[1] - ny * aisle * 0.9]; break; } }
    if (!pos) { pos = viewpoint(M, bb, f); look = [rcx(bb), rcy(bb)]; }
    // measured aisle in front of the line
    let aisleM = Infinity;
    for (const e of hot) {
      const ox = rcx(e.rect) + nx * (rw(e.rect) / 2 + 0.01), oy = rcy(e.rect) + ny * (rh(e.rect) / 2 + 0.01);
      for (const o of M.equip) if (!o.overhead && o !== e && !hot.includes(o)) { const t = rayRect(ox, oy, nx, ny, o.rect); if (t >= 0) aisleM = Math.min(aisleM, t); }
      aisleM = Math.min(aisleM, castRay(M, ox, oy, nx, ny, 10).t);
    }
    const names = hot.map(e => (KEY_ES[e.key] || e.label).toLowerCase().replace(/ \d$/, '')).filter((v, i, a) => a.indexOf(v) === i);
    S.push({ id: 'cocina', title: 'Cocina caliente', pos, look, lookH: 1.0,
      text: `Línea caliente de ${fmt(run, 2)} m bajo una sola campana: ${names.join(', ')}.${isFinite(aisleM) ? ` Pasillo de trabajo de ${fmt(aisleM, 2)} m frente a la línea.` : ''}`,
      flags: [FLAGS.EXTRACTION, ...tb(hot)] });
  }
  // 6 Back of house (prep + frío)
  {
    const t = M.one('fridge_2d') || M.one('freezer_1d') || M.one('mesa_1') || M.one('mesa_2');
    if (t) {
      const pos = viewpoint(M, t.rect, itemFront(M, t), { dists: [1.6, 2.0, 1.3, 2.5, 1.0] });
      const clean = M.routes.find(r => r.kind === 'clean');
      const cold = ['fridge_2d', 'freezer_1d'].filter(k => M.one(k)).length, prep = ['mesa_1', 'mesa_2', 'mesa_opt'].filter(k => M.one(k)).length;
      S.push({ id: 'boh', title: 'Back of house · prep + frío', pos, look: [rcx(t.rect), rcy(t.rect)], lookH: 1.1,
        text: `${cold ? `${cold === 2 ? 'Refrigerador de 2 puertas y congelador' : 'Refrigeración'} junto a ` : ''}${prep} mesa${prep === 1 ? '' : 's'} de trabajo inox${M.one('shelf_4') ? ' y estantería de 4 niveles' : ''}. Flujo limpio: frío → preparación → línea → pase${clean ? ` (${fmt(clean.len, 1)} m)` : ''}.`,
        flags: tb([M.one('fridge_2d'), M.one('freezer_1d'), M.one('mesa_1'), M.one('mesa_2'), M.one('shelf_4')]) });
    }
  }
  // 7 Lavado
  {
    const s = M.one('sink_2t');
    if (s) {
      const pos = viewpoint(M, s.rect, itemFront(M, s), { dists: [1.5, 1.9, 1.2, 2.4] });
      const dirty = M.routes.filter(r => r.kind === 'dirty'), clean = M.routes.filter(r => r.kind === 'clean');
      const crosses = dirty.some(d => clean.some(c => segsCross(d.pts, c.pts)));
      const door = M.openings.find(o => DOOR_TYPES.has(o.type) && M.partInfo && rDist(o.rect, M.partInfo.rect) < 0.2);
      S.push({ id: 'lavado', title: 'Lavado (flujo sucio)', pos, look: [rcx(s.rect), rcy(s.rect)], lookH: 0.95,
        text: `Fregadero de 2 tanques${M.one('mop_sink') ? ' y pileta de aseo' : ''}. La loza sucia entra${door ? ` por la puerta ${door.label || door.id}` : ' desde el salón'} y llega al lavado${dirty.length ? (crosses ? '; hoy la ruta sucia cruza la ruta limpia: revisar.' : ' sin cruzar la ruta limpia.') : '.'}`,
        flags: tb([s, M.one('mop_sink')]) });
    }
  }
  // 8 Smoker
  {
    const s = M.one('smoker');
    if (s) {
      const pos = viewpoint(M, s.rect, itemFront(M, s), { dists: [1.6, 2.0, 1.3, 2.5, 1.0] });
      const fuel = M.one('fuel_storage');
      S.push({ id: 'smoker', title: 'Smoker', pos, look: [rcx(s.rect), rcy(s.rect)], lookH: 1.0,
        text: `Smoker de combustible sólido (${fmt(rw(s.rect), 2)} × ${fmt(rh(s.rect), 2)} m) con chimenea propia${fuel ? `, a ${fmt(rDist(s.rect, fuel.rect), 2)} m del almacén de leña y carbón` : ''}.`,
        flags: [FLAGS.SMOKER, ...tb([s, fuel])] });
    }
  }
  // 9 Delivery
  {
    const d = M.one('delivery_staging');
    if (d) {
      const pos = viewpoint(M, d.rect, itemFront(M, d), { dists: [1.5, 1.9, 1.2, 2.4, 1.0] });
      const r = M.routes.find(x => x.kind === 'delivery');
      S.push({ id: 'delivery', title: 'Delivery / servicio', pos, look: [rcx(d.rect), rcy(d.rect)], lookH: 0.95,
        text: `Estante de despacho para pedidos de delivery y para llevar: bolsas selladas listas para entregar${r ? `; ruta de salida de ${fmt(r.len, 1)} m` : ''}.`,
        flags: tb([d]) });
    }
  }
  return S;
}

/* ============================ metrics ============================ */
function computeMetrics(M) {
  const G = M.grid;
  // clearance field including chairs (the walk grid ignores chairs)
  const blk = G.block.slice(); for (const c of M.chairs) G.paint(blk, c.rect);
  const fr = new Uint8Array(G.n); for (let k = 0; k < G.n; k++) fr[k] = G.inside[k] && !blk[k] ? 1 : 0;
  const d2 = edt2(fr, G.nx, G.ny);
  const clrAt = (x, y) => { const i = G.ix(x), j = G.iy(y); if (!G.ok(i, j)) return 0; const k = j * G.nx + i; return fr[k] ? Math.max(0, Math.sqrt(d2[k]) * G.cell - G.cell / 2) : 0; };
  const routeW = r => {
    let L = 0; const segs = [];
    for (let k = 1; k < r.pts.length; k++) { const a = r.pts[k - 1], b = r.pts[k], l = Math.hypot(b[0] - a[0], b[1] - a[1]); segs.push([a, b, l]); L += l; }
    let w = Infinity, at = null, s = 0;
    for (const [a, b, l] of segs) {
      for (let d = 0; d <= l; d += 0.05) {
        const tot = s + d; if (tot < 0.35 || tot > L - 0.35) continue;
        const x = lerp(a[0], b[0], d / l), y = lerp(a[1], b[1], d / l);
        const c = 2 * clrAt(x, y); if (c < w) { w = c; at = [x, y]; }
      }
      s += l;
    }
    return { w: isFinite(w) ? w : null, at };
  };
  const zones = M.zones.map(z => ({ id: z.id, name: z.name, area: z.area, color: z.color }));
  const routes = M.routes.map(r => { const m = routeW(r); return { id: r.id, kind: r.kind, label: r.label, len: r.len, req: r.min_width, w: m.w, at: m.at }; });
  const part = M.partition ? M.partition.rect : null;
  return {
    seats: M.seats, tables: M.tables.length, chairs: M.chairs.length, banquetteSeats: M.banquettes.reduce((s, b) => s + b.seats, 0),
    premArea: M.premArea, fohArea: M.fohArea, zones, routes,
    partitionX: part ? part[0] : null, partitionShift: part ? 6.298 - part[0] : null,
    equipment: M.equip.length, tbv: M.equip.filter(e => e.tbv), ceilH: M.ceilH,
  };
}
