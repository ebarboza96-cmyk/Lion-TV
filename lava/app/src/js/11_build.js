/* ===================================================================================
   11 build: materials, geometry batching, architecture (floor, walls, glazing,
   kitchen partition, ceiling), decor and lights.  Plan (x,y) -> world (X=x, Z=y), Y up.
   =================================================================================== */

const W3 = { flames: [], doors: [], picks: [], occluders: [], anim: [], glowPts: [], lights: [], logs: [], caps: [] };
const MAT = {};

function V3(x, y, h) { return new THREE.Vector3(x, h, y); }

/* ---------- geometry helpers ---------- */
function worldUV(g) {
  const p = g.attributes.position, n = g.attributes.normal;
  let uv = g.attributes.uv;
  if (!uv) { uv = new THREE.BufferAttribute(new Float32Array(p.count * 2), 2); g.setAttribute('uv', uv); }
  for (let i = 0; i < p.count; i++) {
    const nx = n.getX(i), ny = n.getY(i), nz = n.getZ(i), ax = Math.abs(nx), ay = Math.abs(ny), az = Math.abs(nz);
    const X = p.getX(i), Y = p.getY(i), Z = p.getZ(i);
    if (ay >= ax && ay >= az) uv.setXY(i, X, Z);
    else if (ax >= az) uv.setXY(i, nx > 0 ? -Z : Z, Y);
    else uv.setXY(i, nz > 0 ? X : -X, Y);
  }
  uv.needsUpdate = true;
  return g;
}
class Batch {
  constructor() { this.m = new Map(); }
  add(mat, g, uv = 'world') {
    if (!g) return;
    if (g.index) g = g.toNonIndexed();
    if (!g.attributes.normal) g.computeVertexNormals();
    if (uv === 'world') worldUV(g);
    else if (!g.attributes.uv) g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
    for (const k of Object.keys(g.attributes)) if (k !== 'position' && k !== 'normal' && k !== 'uv') g.deleteAttribute(k);
    g.clearGroups();
    if (!this.m.has(mat)) this.m.set(mat, []);
    this.m.get(mat).push(g);
  }
  box(mat, r, z0, z1, uv) { if (!r || z1 - z0 < 1e-4 || rw(r) < 1e-4 || rh(r) < 1e-4) return; const g = new THREE.BoxGeometry(rw(r), z1 - z0, rh(r)); g.translate(rcx(r), (z0 + z1) / 2, rcy(r)); this.add(mat, g, uv); }
  boxR(mat, cx, cy, cz, sx, sy, sz, rot = 0, uv) { const g = new THREE.BoxGeometry(sx, sz, sy); if (rot) g.rotateY(rot); g.translate(cx, cz, cy); this.add(mat, g, uv); }
  cylV(mat, x, y, z0, z1, r, seg = 12, uv = 'own', r2) { const g = new THREE.CylinderGeometry(r2 != null ? r2 : r, r, z1 - z0, seg); g.translate(x, (z0 + z1) / 2, y); this.add(mat, g, uv); }
  cylAB(mat, a, b, r, seg = 10, uv = 'own') { // a,b = [x,y,z] plan+height
    const A = V3(a[0], a[1], a[2]), Bv = V3(b[0], b[1], b[2]), d = Bv.clone().sub(A), L = d.length(); if (L < 1e-4) return;
    const g = new THREE.CylinderGeometry(r, r, L, seg, 1, false);
    g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize()));
    g.translate((A.x + Bv.x) / 2, (A.y + Bv.y) / 2, (A.z + Bv.z) / 2); this.add(mat, g, uv);
  }
  geo(mat, g, m4, uv = 'own') { if (m4) g.applyMatrix4(m4); this.add(mat, g, uv); }
  flush(parent, opts = {}) {
    for (const [mat, list] of this.m) {
      let geo = null;
      try { geo = list.length === 1 ? list[0] : mergeGeometries(list, false); } catch (e) { console.warn('LAVA: merge', e); }
      if (!geo) continue;
      geo.computeBoundingSphere();
      const mesh = new THREE.Mesh(geo, mat);
      mesh.matrixAutoUpdate = false; mesh.updateMatrix();
      if (opts.renderOrder != null) mesh.renderOrder = opts.renderOrder;
      if (mat.userData && mat.userData.order != null) mesh.renderOrder = mat.userData.order;
      parent.add(mesh);
      for (const g of list) if (g !== geo) g.dispose();
    }
    this.m.clear();
  }
}
/* vertical quad from plan point a to b (normal = left of a->b in plan coordinates, i.e. (-dy, dx)) */
function vquad(a, b, z0, z1) {
  const g = new THREE.BufferGeometry();
  const p = [a[0], z0, a[1], b[0], z0, b[1], b[0], z1, b[1], a[0], z0, a[1], b[0], z1, b[1], a[0], z1, a[1]];
  g.setAttribute('position', new THREE.Float32BufferAttribute(p, 3));
  g.computeVertexNormals();
  return g;
}
function hquad(r, z, down = false) {
  const g = new THREE.PlaneGeometry(rw(r), rh(r)); g.rotateX(down ? Math.PI / 2 : -Math.PI / 2); g.translate(rcx(r), z, rcy(r)); return g;
}
/* frame for items with a working face: u along face, v from back (0) to front (d) */
function frameOf(rect, front) {
  const n = DIRV[front] || DIRV.S, u = [-n[1], n[0]];
  const w = Math.abs(u[0]) * rw(rect) + Math.abs(u[1]) * rh(rect), d = Math.abs(n[0]) * rw(rect) + Math.abs(n[1]) * rh(rect);
  const cx = rcx(rect), cy = rcy(rect), ox = cx - n[0] * d / 2 - u[0] * w / 2, oy = cy - n[1] * d / 2 - u[1] * w / 2;
  const P = (uu, vv) => [ox + u[0] * uu + n[0] * vv, oy + u[1] * uu + n[1] * vv];
  const R = (u0, v0, u1, v1) => { const a = P(u0, v0), b = P(u1, v1); return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1])]; };
  return { w, d, n, u, P, R, rot: Math.atan2(n[0], n[1]), rect };
}
/* basis for wall-mounted flat things facing `face` (text reads left->right for the viewer) */
function faceBasis(face) {
  const out = { E: [1, 0, 0], W: [-1, 0, 0], N: [0, 0, -1], S: [0, 0, 1] }[face] || [0, 0, 1];
  const right = { E: [0, 0, -1], W: [0, 0, 1], N: [-1, 0, 0], S: [1, 0, 0] }[face] || [1, 0, 0];
  return { out: new THREE.Vector3(...out), right: new THREE.Vector3(...right), up: new THREE.Vector3(0, 1, 0) };
}
function faceMatrix(face, pos) { const b = faceBasis(face); return new THREE.Matrix4().makeBasis(b.right, b.up, b.out).setPosition(pos); }

function glow(x, y, z, size, color) { W3.glowPts.push({ x, y, z, size, color: new THREE.Color(color) }); }

/* ---------- materials ---------- */
function std(o) { return new THREE.MeshStandardMaterial(o); }
function basic(o) { return new THREE.MeshBasicMaterial(o); }
function makeMaterials() {
  MAT.floor = std({ map: TEX.concrete, roughnessMap: TEX.concreteRough, roughness: 0.62, metalness: 0.0, envMapIntensity: 0.55 });
  MAT.tileFloor = std({ map: TEX.tile, roughness: 0.78, envMapIntensity: 0.4 });
  MAT.exterior = std({ map: TEX.tile, color: 0x6a655f, roughness: 0.6, envMapIntensity: 0.3 });
  MAT.wallFOH = std({ map: TEX.boardConcrete, color: 0xc2beb8, roughness: 0.96, envMapIntensity: 0.2 });
  MAT.wallTile = std({ map: TEX.subway, roughness: 0.28, envMapIntensity: 0.55 });
  MAT.wallPaint = std({ map: TEX.paint, roughness: 0.9, envMapIntensity: 0.35 });
  MAT.wallOuter = std({ color: 0x3b3834, roughness: 1, envMapIntensity: 0.2 });
  MAT.cap = basic({ color: 0x2b2622 });
  MAT.ceiling = std({ color: 0x0b0a0a, roughness: 1, envMapIntensity: 0.05, side: THREE.DoubleSide });
  MAT.blackSteel = std({ map: TEX.blacksteel, roughness: 0.5, metalness: 0.65, envMapIntensity: 0.7 });
  MAT.matteBlack = std({ color: 0x141312, roughness: 0.75, metalness: 0.2, envMapIntensity: 0.4 });
  MAT.stainless = std({ map: TEX.brushed, roughness: 0.3, metalness: 1.0, envMapIntensity: 1.0 });
  MAT.stainlessDark = std({ color: 0x8a8e92, roughness: 0.42, metalness: 1.0, envMapIntensity: 0.8 });
  MAT.grate = std({ color: 0x1a1918, roughness: 0.55, metalness: 0.8 });
  MAT.oak = std({ map: TEX.oak, roughness: 0.5, envMapIntensity: 0.6 });
  MAT.walnut = std({ map: TEX.walnut, roughness: 0.62, envMapIntensity: 0.4 });
  MAT.fabric = std({ map: TEX.fabric, roughness: 0.95, envMapIntensity: 0.35 });
  MAT.fabricBack = std({ map: TEX.fabric, color: 0xb9c2ae, roughness: 0.97, envMapIntensity: 0.3 });
  MAT.brass = std({ color: 0xc9a063, metalness: 1.0, roughness: 0.3, envMapIntensity: 1.2 });
  MAT.bronze = std({ color: 0x3a2618, metalness: 0.85, roughness: 0.42, envMapIntensity: 0.8 });
  MAT.corten = std({ map: TEX.corten, roughness: 0.82, metalness: 0.35, envMapIntensity: 0.5 });
  MAT.glass = std({ color: 0xa8bcc0, transparent: true, opacity: 0.1, roughness: 0.04, metalness: 0.1, envMapIntensity: 1.6, depthWrite: false });
  MAT.glass.userData.order = 5;
  MAT.white = std({ color: 0xe6e4df, roughness: 0.35, envMapIntensity: 0.6 });
  MAT.rubber = std({ color: 0x121212, roughness: 0.9 });
  MAT.plate = std({ color: 0x1d1c1b, roughness: 0.25, envMapIntensity: 0.8 });
  MAT.bottle = std({ color: 0x0b120e, roughness: 0.12, metalness: 0.3, envMapIntensity: 1.4 });
  MAT.amberGlass = basic({ color: new THREE.Color(1.7, 0.85, 0.32) });
  MAT.lightWarm = basic({ color: new THREE.Color(5, 3.3, 1.8) });
  MAT.lightSoft = basic({ color: new THREE.Color(2.4, 1.5, 0.75) });
  MAT.lightCool = basic({ color: new THREE.Color(3.2, 3.1, 2.9) });
  MAT.ledStrip = basic({ color: new THREE.Color(3.5, 1.9, 0.8) });
  MAT.ember = basic({ map: TEX.ember, color: new THREE.Color(3.2, 2.2, 1.6) });
  MAT.soil = std({ color: 0x241810, roughness: 1 });
  MAT.leaves = std({ map: TEX.leaves, alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.8, envMapIntensity: 0.3 });
  MAT.kraft = std({ map: TEX.kraft, roughness: 0.9 });
  MAT.duct = std({ map: TEX.duct, metalness: 0.75, roughness: 0.42, envMapIntensity: 0.8 });
  MAT.red = std({ color: 0x5e140d, roughness: 0.6, envMapIntensity: 0.3 });
  MAT.bark = std({ map: TEX.bark, roughness: 0.95 });
  MAT.endgrain = std({ map: TEX.endgrain, roughness: 0.85 });
  MAT.oil = std({ color: 0x5a3a0c, roughness: 0.08, metalness: 0.2, envMapIntensity: 1.2 });
  MAT.blob = basic({ map: TEX.blob, transparent: true, depthWrite: false, color: 0x000000, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
  MAT.blob.userData.order = 1;
  MAT.food = [0xb8321f, 0x5e8a2e, 0xe8dfc8, 0xd9a13b, 0x7a2f1c].map(c => std({ color: c, roughness: 0.7 }));
  MAT.screen = basic({ map: screenTexture('pos') });
  MAT.display = basic({ map: screenTexture('3°C') });
}

/* ---------- region-aware wall box ---------- */
function wallMatFor(cls, z0, z1) {
  if (cls === 1) return [[MAT.wallFOH, z0, z1]];
  if (cls === 2) return z1 > 2.05 && z0 < 2.05 ? [[MAT.wallTile, z0, 2.05], [MAT.wallPaint, 2.05, z1]] : [[z1 <= 2.05 ? MAT.wallTile : MAT.wallPaint, z0, z1]];
  return [[MAT.wallOuter, z0, z1]];
}
function wallBox(B, r, z0, z1, opts = {}) {
  const M = MODEL;
  const sides = [
    { a: [r[2], r[1]], b: [r[0], r[1]], n: [0, -1] }, // N face (normal -y): order so (-dy,dx) = n
    { a: [r[0], r[3]], b: [r[2], r[3]], n: [0, 1] },
    { a: [r[2], r[3]], b: [r[2], r[1]], n: [1, 0] },
    { a: [r[0], r[1]], b: [r[0], r[3]], n: [-1, 0] },
  ];
  for (const s of sides) {
    const L = Math.hypot(s.b[0] - s.a[0], s.b[1] - s.a[1]); if (L < 0.005) continue;
    const steps = Math.max(1, Math.round(L / 0.1)); let runStart = 0, cls = null;
    const clsAt = t => { const x = lerp(s.a[0], s.b[0], t) + s.n[0] * 0.08, y = lerp(s.a[1], s.b[1], t) + s.n[1] * 0.08; return opts.force != null ? opts.force : M.regionAt(x, y); };
    const emit = (t0, t1, c) => {
      const A = [lerp(s.a[0], s.b[0], t0), lerp(s.a[1], s.b[1], t0)], Bp = [lerp(s.a[0], s.b[0], t1), lerp(s.a[1], s.b[1], t1)];
      for (const [mat, za, zb] of wallMatFor(c, z0, z1)) if (zb - za > 1e-3) B.add(mat, vquad(A, Bp, za, zb));
    };
    for (let k = 0; k < steps; k++) {
      const c = clsAt((k + 0.5) / steps);
      if (cls === null) cls = c;
      else if (c !== cls) { emit(runStart / steps, k / steps, cls); runStart = k; cls = c; }
    }
    emit(runStart / steps, 1, cls);
  }
  B.add(MAT.wallOuter, hquad(r, z1));
  W3.occluders.push({ box: new THREE.Box3(V3(r[0], r[1], z0), V3(r[2], r[3], z1)) });
  W3.caps.push(r);
}

/* ============================ scene ============================ */
function buildArchitecture(B, CB) {
  const M = MODEL, H = M.ceilH;
  W3.caps = [];
  /* floor */
  const shape = new THREE.Shape(M.prem.map(p => new THREE.Vector2(p[0], -p[1])));
  const fg = new THREE.ShapeGeometry(shape); fg.rotateX(-Math.PI / 2);
  B.add(MAT.floor, fg);
  for (const r of M.bohRects) B.add(MAT.tileFloor, hquad(rgrow(r, 0.012), 0.002));
  /* exterior corridor beyond the storefront (dim) */
  const ex = [M.pbb[2] + 0.02, M.pbb[1] - 2, M.pbb[2] + 9, M.pbb[3] + 1];
  B.add(MAT.exterior, hquad(ex, -0.01));
  /* ceiling */
  const cg = new THREE.ShapeGeometry(new THREE.Shape(M.prem.map(p => new THREE.Vector2(p[0], p[1])))); cg.rotateX(Math.PI / 2); cg.translate(0, H, 0);
  CB.add(MAT.ceiling, cg);
  /* walls */
  for (const w of M.walls) {
    if (w.src === 'new' && w.type === 'glass_partition') continue;
    if (w.src === 'new') {
      const top = w.type === 'low_wall' ? w.h : Math.min(H, w.h);
      wallBox(B, w.rect, 0, top);
      if (w.type === 'low_wall') B.box(MAT.oak, rgrow(w.rect, 0.015), top, top + 0.035);
    } else wallBox(B, w.rect, 0, H);
  }
  for (const c of M.columns) wallBox(B, c.rect, 0, H);
  for (const s of M.shafts) if (M.isInside(rcx(s.rect), rcy(s.rect))) wallBox(B, s.rect, 0, H);
  if (M.stair) wallBox(B, M.stair.rect, 0, H, { force: 0 });
  /* perimeter safety skin: premises edges not covered by walls/glazing/doors */
  const covered = (x, y) => M.walls.some(w => pRectDist(x, y, w.rect) < 0.03) || M.columns.some(c => pRectDist(x, y, c.rect) < 0.03) ||
    M.glazing.some(g => pRectDist(x, y, g.rect) < 0.05) || M.doors.some(d => { const L = Math.hypot(d.b[0] - d.a[0], d.b[1] - d.a[1]) || 1; const t = clamp(((x - d.a[0]) * (d.b[0] - d.a[0]) + (y - d.a[1]) * (d.b[1] - d.a[1])) / (L * L), 0, 1); return Math.hypot(x - lerp(d.a[0], d.b[0], t), y - lerp(d.a[1], d.b[1], t)) < 0.06; });
  const ccw = polySignedArea(M.prem) > 0;
  for (const s of M.segs) {
    const L = Math.hypot(s[2] - s[0], s[3] - s[1]); if (L < 0.02) continue;
    const steps = Math.max(1, Math.round(L / 0.1)); let start = -1;
    const flush = (k0, k1) => {
      const a = [lerp(s[0], s[2], k0 / steps), lerp(s[1], s[3], k0 / steps)], b = [lerp(s[0], s[2], k1 / steps), lerp(s[1], s[3], k1 / steps)];
      // inward normal: for CCW (in y-down plan) polygon interior is to the right
      const g = ccw ? vquad(a, b, 0, H) : vquad(b, a, 0, H);
      B.add(MAT.wallFOH, g);
    };
    for (let k = 0; k < steps; k++) {
      const t = (k + 0.5) / steps, x = lerp(s[0], s[2], t), y = lerp(s[1], s[3], t);
      const unc = !covered(x, y);
      if (unc && start < 0) start = k; if (!unc && start >= 0) { flush(start, k); start = -1; }
    }
    if (start >= 0) flush(start, steps);
  }
  buildGlazing(B);
}
function polySignedArea(p) { let a = 0; for (let i = 0; i < p.length; i++) { const q = p[i], s = p[(i + 1) % p.length]; a += q[0] * s[1] - s[0] * q[1]; } return a / 2; }

function buildGlazing(B) {
  const M = MODEL, H = M.ceilH, headZ = Math.min(2.7, H - 0.2);
  for (const g of M.glazing) {
    const r = g.rect, alongY = rh(r) >= rw(r), L = alongY ? rh(r) : rw(r);
    const isWin = g.kind === 'window';
    const z0 = isWin ? 0.95 : 0.0, z1 = isWin ? 2.15 : headZ;
    if (isWin) { wallBox(B, r, 0, z0); wallBox(B, r, z1, H); }
    else wallBox(B, r, z1, H);
    const mid = alongY ? [rcx(r) - 0.006, r[1], rcx(r) + 0.006, r[3]] : [r[0], rcy(r) - 0.006, r[2], rcy(r) + 0.006];
    B.box(MAT.glass, mid, z0 + 0.04, z1 - 0.04, 'own');
    const fr = (a0, a1) => alongY ? [rcx(r) - 0.025, a0, rcx(r) + 0.025, a1] : [a0, rcy(r) - 0.025, a1, rcy(r) + 0.025];
    const a0 = alongY ? r[1] : r[0], a1 = alongY ? r[3] : r[2];
    const n = Math.max(1, Math.round(L / 1.1));
    for (let i = 0; i <= n; i++) { const a = lerp(a0, a1, i / n); B.box(MAT.matteBlack, fr(Math.max(a0, a - 0.025), Math.min(a1, a + 0.025)), z0, z1); }
    B.box(MAT.matteBlack, fr(a0, a1), z0, z0 + 0.06); B.box(MAT.matteBlack, fr(a0, a1), z1 - 0.06, z1);
  }
  // entrance doors (existing double door): frame + two glass leaves (closed)
  for (const d of M.doors) {
    if (d.kind !== 'double' && d.kind !== 'door') continue;
    const alongY = Math.abs(d.b[1] - d.a[1]) > Math.abs(d.b[0] - d.a[0]);
    const a0 = alongY ? Math.min(d.a[1], d.b[1]) : Math.min(d.a[0], d.b[0]), a1 = alongY ? Math.max(d.a[1], d.b[1]) : Math.max(d.a[0], d.b[0]);
    const c = alongY ? d.a[0] : d.a[1];
    const R = (p0, p1, t = 0.025) => alongY ? [c - t, p0, c + t, p1] : [p0, c - t, p1, c + t];
    wallBox(B, R(a0, a1, 0.06), headZ, H);
    B.box(MAT.matteBlack, R(a0, a1, 0.04), headZ - 0.07, headZ);
    const leaves = d.kind === 'double' ? 2 : 1, lw = (a1 - a0) / leaves;
    for (let i = 0; i < leaves; i++) {
      const p0 = a0 + i * lw, p1 = p0 + lw;
      B.box(MAT.glass, R(p0 + 0.05, p1 - 0.05, 0.006), 0.1, headZ - 0.12, 'own');
      for (const [q0, q1] of [[p0, p0 + 0.05], [p1 - 0.05, p1]]) B.box(MAT.matteBlack, R(q0, q1, 0.022), 0, headZ - 0.07);
      B.box(MAT.matteBlack, R(p0, p1, 0.022), 0, 0.1); B.box(MAT.matteBlack, R(p0, p1, 0.022), headZ - 0.13, headZ - 0.07);
      const hx = i === 0 ? p1 - 0.12 : p0 + 0.12;
      const inward = MODEL.isInside(alongY ? c - 0.3 : hx, alongY ? hx : c - 0.3) ? -1 : 1;
      const P = alongY ? [c + inward * 0.07, hx] : [hx, c + inward * 0.07];
      B.cylV(MAT.brass, P[0], P[1], 0.75, 1.55, 0.014, 10);
    }
  }
}

/* ---------- kitchen / dining partition ---------- */
function buildPartition(B, walls) {
  const M = MODEL, PI = M.partInfo, H = M.ceilH;
  const glassWalls = M.walls.filter(w => w.src === 'new' && w.type === 'glass_partition');
  for (const w of glassWalls) {
    const isMain = PI && w.parent === PI.wall;
    const r = w.rect, alongY = rh(r) >= rw(r);
    const a0 = alongY ? r[1] : r[0], a1 = alongY ? r[3] : r[2];
    const t0 = alongY ? r[0] : r[1], t1 = alongY ? r[2] : r[3], tm = (t0 + t1) / 2;
    const R = (p0, p1, q0 = t0, q1 = t1) => { const a = Math.min(q0, q1), b = Math.max(q0, q1); return alongY ? [a, p0, b, p1] : [p0, a, p1, b]; };
    const baseH = w.base_h || 1.0;
    const glassTop = isMain ? PI.glassTop : Math.min(w.h, H);
    const face = isMain ? PI.face : openFace(M, r);
    const fsgn = (face === 'E' || face === 'S') ? 1 : -1;   // + means dining at t1
    const tD = fsgn > 0 ? t1 : t0, tK = fsgn > 0 ? t0 : t1;
    const passes = isMain ? PI.passes.map(p => [Math.max(p[0], a0), Math.min(p[1], a1)]).filter(p => p[1] - p[0] > 0.1) : [];
    const niches = M.decor.filter(d => (d.type === 'firewood_niche' || d.type === 'planter') && rInter(rgrow(r, 0.02), d.rect)).map(d => {
      const i = rInter(rgrow(r, 0.02), d.rect); return { d, p0: Math.max(a0, alongY ? i[1] : i[0]), p1: Math.min(a1, alongY ? i[3] : i[2]) };
    }).sort((p, q) => p.p0 - q.p0);
    /* base: solid pieces between niches */
    let cur = a0;
    const baseMat = MAT.corten;
    for (const n of niches) {
      if (n.p0 > cur + 0.005) B.box(baseMat, R(cur, n.p0), 0, baseH);
      const zb = n.d.z != null ? n.d.z : 0.12, zt = Math.min(baseH - 0.08, n.d.h != null ? n.d.h : baseH - 0.12);
      const planter = n.d.type === 'planter';
      const back = [tK, tK + (fsgn > 0 ? 0.035 : -0.035)].sort((p, q) => p - q);
      B.box(baseMat, R(n.p0, n.p1), 0, planter ? 0.1 : zb);
      B.box(baseMat, R(n.p0, n.p1), planter ? baseH - 0.06 : zt, baseH);
      B.box(MAT.matteBlack, R(n.p0, n.p1, back[0], back[1]), zb, zt);
      if (planter) buildPlanter(B, alongY, n.p0, n.p1, Math.min(tD, tK + (fsgn > 0 ? 0.035 : -0.035)), Math.max(tD, tK + (fsgn > 0 ? 0.035 : -0.035)), 0.1, baseH - 0.06, face);
      else buildLogStack(alongY, n.p0 + 0.02, n.p1 - 0.02, back, tD, zb, zt, face);
      // warm LED at niche top
      B.box(MAT.ledStrip, R(n.p0 + 0.03, n.p1 - 0.03, tD - fsgn * 0.03, tD - fsgn * 0.015), (planter ? baseH - 0.075 : zt - 0.012), planter ? baseH - 0.06 : zt, 'own');
      cur = n.p1;
    }
    if (a1 > cur + 0.005) B.box(baseMat, R(cur, a1), 0, baseH);
    // steel cap on the base
    B.box(MAT.blackSteel, R(a0, a1, t0 - 0.01, t1 + 0.01), baseH, baseH + 0.02);
    /* glass + mullions */
    let spans = [[a0, a1]];
    const passTop = baseH + 0.62;
    for (const p of passes) spans = spans.flatMap(s => (p[1] <= s[0] || p[0] >= s[1]) ? [s] : [[s[0], p[0]], [p[1], s[1]]].filter(q => q[1] - q[0] > 0.02));
    for (const s of spans) B.box(MAT.glass, R(s[0], s[1], tm - 0.006, tm + 0.006), baseH + 0.02, glassTop, 'own');
    for (const p of passes) {
      B.box(MAT.glass, R(p[0], p[1], tm - 0.006, tm + 0.006), passTop, glassTop, 'own');
      B.box(MAT.matteBlack, R(p[0], p[1], t0 - 0.005, t1 + 0.005), passTop, passTop + 0.05);
      // stainless pass shelf through the opening
      B.box(MAT.stainless, R(p[0] - 0.02, p[1] + 0.02, Math.min(tD, tK) - 0.22, Math.max(tD, tK) + 0.22), baseH + 0.02, baseH + 0.05);
    }
    const L = a1 - a0, nM = Math.max(1, Math.round(L / 1.15));
    const mull = [];
    for (let i = 0; i <= nM; i++) mull.push(lerp(a0, a1, i / nM));
    for (const p of passes) { mull.push(p[0], p[1]); }
    for (const a of mull) {
      const inPass = passes.some(p => a > p[0] + 0.01 && a < p[1] - 0.01);
      B.box(MAT.matteBlack, R(Math.max(a0, a - 0.022), Math.min(a1, a + 0.022), tm - 0.03, tm + 0.03), inPass ? passTop : baseH, glassTop);
    }
    B.box(MAT.matteBlack, R(a0, a1, tm - 0.035, tm + 0.035), glassTop - 0.05, glassTop);
    /* fascia to ceiling (sign board) */
    if (glassTop < H - 0.01) {
      B.box(MAT.corten, R(a0, a1, t0 - 0.02, t1 + 0.02), glassTop, H);
      const nP = Math.max(1, Math.round(L / 1.2));
      for (let i = 1; i < nP; i++) { const a = lerp(a0, a1, i / nP); B.box(MAT.matteBlack, R(a - 0.005, a + 0.005, tD + fsgn * 0.018, tD + fsgn * 0.026), glassTop, H); }
    }
    W3.occluders.push({ box: new THREE.Box3(V3(r[0], r[1], 0), V3(r[2], r[3], baseH)) });
    W3.occluders.push({ box: new THREE.Box3(V3(r[0], r[1], glassTop), V3(r[2], r[3], H)) });
    W3.caps.push(r);
  }
  /* door openings in any wall: header above 2.1 m + animated leaves */
  for (const o of M.openings) {
    if (!DOOR_TYPES.has(o.type)) continue;
    const r = o.rect, alongY = rh(r) >= rw(r);
    const hosts = M.walls.filter(w => rDist(w.rect, r) < 0.03);
    const host = hosts.find(w => w.src === 'new') || hosts[0] || null;
    const hostTop = host ? (host.type === 'glass_partition' ? H : Math.min(H, host.h || H)) : H;
    const headZ = 2.1;
    if (host && host.type === 'glass_partition') {
      const P = PI && host.parent === PI.wall ? PI : null; const gt = P ? P.glassTop : 2.4;
      B.box(MAT.glass, alongY ? [rcx(r) - 0.006, r[1], rcx(r) + 0.006, r[3]] : [r[0], rcy(r) - 0.006, r[2], rcy(r) + 0.006], headZ + 0.05, gt, 'own');
      B.box(MAT.matteBlack, rgrow(r, 0.005), headZ, headZ + 0.05);
      if (gt < H) B.box(MAT.corten, alongY ? [r[0] - 0.02, r[1], r[2] + 0.02, r[3]] : [r[0], r[1] - 0.02, r[2], r[3] + 0.02], gt, H);
    } else wallBox(B, r, headZ, hostTop);
    const a0 = alongY ? r[1] : r[0], a1 = alongY ? r[3] : r[2], c = alongY ? rcx(r) : rcy(r);
    const jamb = (p0, p1) => alongY ? [r[0] - 0.01, p0, r[2] + 0.01, p1] : [p0, r[1] - 0.01, p1, r[3] + 0.01];
    B.box(MAT.matteBlack, jamb(a0, a0 + 0.03), 0, headZ); B.box(MAT.matteBlack, jamb(a1 - 0.03, a1), 0, headZ);
    if (o.type === 'opening') continue;
    const width = a1 - a0 - 0.06;
    const two = o.type === 'double_acting_door' ? width > 1.05 : false;
    const leaves = o.type === 'double_acting_door' && !two ? 1 : two ? 2 : 1;
    const lw = width / leaves;
    for (let i = 0; i < leaves; i++) {
      const hingeA = i === 0 ? a0 + 0.03 : a1 - 0.03, dir = i === 0 ? 1 : -1;
      const pivot = new THREE.Group();
      const hp = alongY ? V3(c, hingeA, 0) : V3(hingeA, c, 0);
      pivot.position.copy(hp);
      const leaf = new THREE.Group();
      const matLeaf = o.type === 'double_acting_door' || o.type === 'service_door' ? MAT.stainless : MAT.walnut;
      const gl = new THREE.Mesh(new THREE.BoxGeometry(lw - 0.01, headZ - 0.04, 0.04), matLeaf);
      worldUV(gl.geometry);
      gl.position.set(dir * (lw / 2), (headZ - 0.04) / 2 + 0.02, 0);
      leaf.add(gl);
      if (o.type === 'double_acting_door') {
        const port = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 0.046, 20), MAT.glass); port.rotation.x = Math.PI / 2; port.position.set(dir * (lw / 2), 1.5, 0); leaf.add(port);
        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.145, 0.012, 6, 24), MAT.matteBlack); ring.position.set(dir * (lw / 2), 1.5, 0.024); leaf.add(ring);
        const ring2 = ring.clone(); ring2.position.z = -0.024; leaf.add(ring2);
        const kick = new THREE.Mesh(new THREE.BoxGeometry(lw - 0.02, 0.3, 0.046), MAT.stainlessDark); kick.position.set(dir * (lw / 2), 0.17, 0); leaf.add(kick);
      } else {
        const h1 = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.3, 8), MAT.brass); h1.position.set(dir * (lw - 0.1), 1.0, 0.05); leaf.add(h1);
      }
      leaf.rotation.y = alongY ? -Math.PI / 2 : 0;
      pivot.add(leaf);
      W3.root.add(pivot);
      const swingMax = o.type === 'sliding_door' ? 0 : 1.35;
      W3.doors.push({ pivot, dir, base: 0, open: 0, max: swingMax, center: [rcx(r), rcy(r)], alongY, double: o.type === 'double_acting_door' });
    }
  }
}
function buildLogStack(alongY, p0, p1, back, tD, zb, zt, face) {
  const len = Math.abs(tD - (back[0] + back[1]) / 2) - 0.02;
  const logLen = clamp(len, 0.08, 0.45);
  const rad = 0.052, rows = Math.max(1, Math.floor((zt - zb) / (rad * 1.75))), cols = Math.max(1, Math.floor((p1 - p0) / (rad * 2.05)));
  const tc = (Math.min(tD, back[0]) + Math.max(tD, back[1])) / 2;
  const rnd = mulberry32(Math.round(p0 * 1000));
  for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
    const a = p0 + rad + i * (p1 - p0 - 2 * rad) / Math.max(1, cols - 1) + (j % 2 ? rad * 0.5 : 0);
    if (a > p1 - rad * 0.9) continue;
    const z = zb + rad + j * rad * 1.72;
    const r = rad * (0.78 + rnd() * 0.3);
    W3.logs.push({ x: alongY ? tc : a, y: alongY ? a : tc, z, r, len: logLen, alongX: alongY, rot: rnd() * 6 });
  }
}
function buildPlanter(B, alongY, p0, p1, q0, q1, z0, z1, face) {
  const R = (a, b, c, d) => alongY ? [c, a, d, b] : [a, c, b, d];
  B.box(MAT.soil, R(p0, p1, q0, q1), z0, z0 + 0.1);
  const rnd = mulberry32(Math.round(p0 * 777));
  const n = Math.max(2, Math.round((p1 - p0) / 0.16));
  for (let i = 0; i < n; i++) {
    const a = lerp(p0 + 0.06, p1 - 0.06, (i + 0.5) / n) + (rnd() - 0.5) * 0.05, t = (q0 + q1) / 2;
    const h = (z1 - z0) * (0.75 + rnd() * 0.35) + 0.12, w = 0.26 + rnd() * 0.12;
    for (const rot of [0, Math.PI / 2, Math.PI / 4]) {
      const g = new THREE.PlaneGeometry(w, h); g.translate(0, h / 2, 0); g.rotateY(rot + rnd());
      g.translate(alongY ? t : a, z0 + 0.08, alongY ? a : t);
      B.add(MAT.leaves, g, 'own');
    }
  }
  glow(alongY ? (q0 + q1) / 2 : (p0 + p1) / 2, alongY ? (p0 + p1) / 2 : (q0 + q1) / 2, z1 - 0.1, Math.min(0.9, (p1 - p0) * 0.6), 0x6a3a14);
}

/* ---------- ceiling services (FOH) & BOH lighting panels ---------- */
function buildCeiling(CB) {
  const M = MODEL, H = M.ceilH, F = M.fohBB, D = M.dining;
  const ax = M.diningAxis;
  const A0 = (ax === 'x' ? F[0] : F[1]) + 0.35, A1 = (ax === 'x' ? F[2] : F[3]) - 0.45;
  const pAt = (a, p) => ax === 'x' ? [a, p] : [p, a];
  const P0 = ax === 'x' ? D[1] : D[0], P1 = ax === 'x' ? D[3] : D[2];
  if (A1 - A0 > 1.5) {
    // spiral ducts
    const ducts = [[lerp(P0, P1, 0.78), 0.22], [lerp(P0, P1, 0.2), 0.15]];
    for (const [p, r] of ducts) {
      const z = H - 0.34;
      CB.cylAB(MAT.duct, [...pAt(A0, p), z], [...pAt(A1, p), z], r, 20);
      for (let a = A0 + 1.4; a < A1 - 0.5; a += 2.8) {
        const q = pAt(a, p); CB.cylV(MAT.duct, q[0], q[1], z - r - 0.1, z, r * 0.7, 16);
        CB.cylV(MAT.matteBlack, q[0], q[1], z - r - 0.13, z - r - 0.1, r * 0.8, 16);
      }
      for (let a = A0 + 0.6; a < A1; a += 1.6) { const q = pAt(a, p); CB.cylV(MAT.matteBlack, q[0], q[1], z + r, H, 0.006, 4); }
    }
    // red sprinkler main + branches
    const ps = lerp(P0, P1, 0.36), zs = H - 0.1;
    CB.cylAB(MAT.red, [...pAt(A0 + 0.3, ps), zs], [...pAt(A1 - 0.3, ps), zs], 0.028, 10);
    for (let a = A0 + 1.0; a < A1; a += 3.0) {
      const q0 = pAt(a, lerp(P0, P1, 0.15)), q1 = pAt(a, lerp(P0, P1, 0.85));
      CB.cylAB(MAT.red, [...q0, zs], [...q1, zs], 0.018, 8);
      for (const q of [q0, q1]) CB.cylV(MAT.stainlessDark, q[0], q[1], zs - 0.08, zs, 0.012, 6);
    }
    // black track rails with spots
    for (const p of [lerp(P0, P1, 0.35), lerp(P0, P1, 0.66)]) {
      const zt = H - 0.05;
      const r0 = ax === 'x' ? [A0, p - 0.015, A1, p + 0.015] : [p - 0.015, A0, p + 0.015, A1];
      CB.box(MAT.matteBlack, r0, zt - 0.035, zt);
      for (let a = A0 + 0.7; a < A1 - 0.2; a += 1.35) {
        const q = pAt(a, p);
        CB.cylV(MAT.matteBlack, q[0], q[1], zt - 0.1, zt - 0.035, 0.012, 6);
        CB.cylV(MAT.matteBlack, q[0], q[1], zt - 0.24, zt - 0.1, 0.038, 12);
        CB.cylV(MAT.lightWarm, q[0], q[1], zt - 0.245, zt - 0.238, 0.03, 12);
        glow(q[0], q[1], zt - 0.27, 0.22, 0xffb060);
      }
    }
    // square supply grilles
    for (let a = A0 + 2.2; a < A1 - 1; a += 4.2) { const q = pAt(a, lerp(P0, P1, 0.5)); CB.box(MAT.matteBlack, [q[0] - 0.28, q[1] - 0.28, q[0] + 0.28, q[1] + 0.28], H - 0.02, H - 0.005); for (let k = -3; k <= 3; k++) CB.box(MAT.grate, [q[0] - 0.22, q[1] + k * 0.06 - 0.012, q[0] + 0.22, q[1] + k * 0.06 + 0.012], H - 0.03, H - 0.02); }
  }
  // BOH/kitchen LED panels on a grid (only above BOH floor)
  const G = M.grid;
  const step = 1.8;
  for (let y = M.pbb[1] + 0.9; y < M.pbb[3]; y += step) for (let x = M.pbb[0] + 0.9; x < M.pbb[2]; x += step) {
    if (M.regionAt(x, y) !== 2 || M.regionAt(x - 0.7, y) !== 2 || M.regionAt(x + 0.7, y) !== 2) continue;
    if (M.equip.some(e => e.key === 'hood' && pRectDist(x, y, e.rect) < 0.3)) continue;
    CB.box(MAT.stainlessDark, [x - 0.64, y - 0.19, x + 0.64, y + 0.19], H - 0.05, H - 0.005);
    CB.box(MAT.lightCool, [x - 0.6, y - 0.15, x + 0.6, y + 0.15], H - 0.055, H - 0.05, 'own');
  }
  void G;
}

/* ---------- decor ---------- */
function buildDecor(B, CB) {
  const M = MODEL;
  for (const d of M.decor) {
    try {
      if (d.type === 'slat_wall') buildSlatWall(B, d);
      else if (d.type === 'sign') buildSign(B, d);
      else if (d.type === 'poster') buildPoster(B, d);
      else if (d.type === 'sconce') buildSconce(B, d);
      else if (d.type === 'pendant') buildPendant(CB, d);
      else if ((d.type === 'firewood_niche' || d.type === 'planter') && !(M.partInfo && rInter(rgrow(M.partInfo.rect, 0.02), d.rect))) buildFreeNiche(B, d);
    } catch (e) { console.warn('LAVA: decor', d.type, e); }
  }
}
function wallSpan(d) { // along-axis extents + face coordinate for thin wall-mounted rects
  const r = d.rect, f = d.face, alongX = f === 'N' || f === 'S';
  const a0 = alongX ? r[0] : r[1], a1 = alongX ? r[2] : r[3];
  const back = f === 'N' ? r[3] : f === 'S' ? r[1] : f === 'E' ? r[0] : r[2];   // side touching the wall
  const sgn = (f === 'S' || f === 'E') ? 1 : -1;
  return { alongX, a0, a1, back, sgn, L: a1 - a0, P: (a, t) => alongX ? [a, back + sgn * t] : [back + sgn * t, a] };
}
function buildSlatWall(B, d) {
  const M = MODEL, s = wallSpan(d);
  const z0 = d.z != null ? d.z : 0.95, z1 = Math.min(M.ceilH - 0.05, d.h != null ? d.h : M.ceilH - 0.16);
  const Rr = (a0, a1, t0, t1) => { const p = s.P(a0, t0), q = s.P(a1, t1); return [Math.min(p[0], q[0]), Math.min(p[1], q[1]), Math.max(p[0], q[0]), Math.max(p[1], q[1])]; };
  // glowing back panel
  const textAt = d.text_at != null ? clamp(d.text_at, 0, 1) : 0.7;
  // canvas runs along +right direction of the face basis; map "a" coordinate to texture u
  const b = faceBasis(d.face);
  const rightIsPlusA = s.alongX ? b.right.x > 0 : b.right.z > 0;
  const tex = slatGlowTexture(s.L, z1 - z0, d.text === '' ? '' : (d.text || 'LAVA'), rightIsPlusA ? textAt : 1 - textAt);
  const mat = basic({ map: tex, color: new THREE.Color(1.55, 1.45, 1.35) });
  const pg = new THREE.PlaneGeometry(s.L, z1 - z0);
  const mid = s.P((s.a0 + s.a1) / 2, 0.006);
  B.geo(mat, pg, faceMatrix(d.face, V3(mid[0], mid[1], (z0 + z1) / 2)));
  // battens: horizontals behind, verticals in front
  const gridV = 0.09, gridH = 0.2;
  for (let z = z0; z <= z1 + 1e-6; z += gridH) B.box(MAT.walnut, Rr(s.a0, s.a1, 0.012, 0.03), Math.min(z, z1 - 0.018), Math.min(z, z1 - 0.018) + 0.018);
  const nV = Math.max(2, Math.round(s.L / gridV));
  for (let i = 0; i <= nV; i++) { const a = lerp(s.a0, s.a1, i / nV); const w = (i === 0 || i === nV) ? 0.05 : 0.02; B.box(MAT.walnut, Rr(clamp(a - w / 2, s.a0, s.a1 - w), clamp(a + w / 2, s.a0 + w, s.a1), 0.03, 0.062), z0, z1); }
  // top cap + cove light line
  B.box(MAT.walnut, Rr(s.a0 - 0.02, s.a1 + 0.02, 0.0, 0.1), z1, z1 + 0.035);
  B.box(MAT.ledStrip, Rr(s.a0, s.a1, 0.004, 0.012), z1 - 0.015, z1);
  B.box(MAT.walnut, Rr(s.a0 - 0.02, s.a1 + 0.02, 0.0, 0.09), z0 - 0.03, z0);
  // text centre (for lights)
  W3.slat = { p: s.P(lerp(s.a0, s.a1, rightIsPlusA ? textAt : 1 - textAt), 0.5), mid: s.P((s.a0 + s.a1) / 2, 0.45), L: s.L, z: (z0 + z1) / 2, d };
  W3.slat.p = s.P(lerp(s.a0, s.a1, textAt), 0.5);
}
function buildSign(B, d) {
  const M = MODEL, s = wallSpan(d);
  const text = (d.text || 'LAVA');
  const { polys, width } = wordGlyphs(text);
  const H = d.size != null ? clamp(d.size, 0.08, 1.5) : clamp(s.L / (width * 1.25), 0.15, 0.5);
  const zc = d.h != null ? d.h : (M.partInfo ? (M.partInfo.glassTop + M.ceilH) / 2 : 2.5);
  const c = s.P((s.a0 + s.a1) / 2, 0);
  const m = faceMatrix(d.face, V3(c[0], c[1], zc));
  for (const p of polys) {
    const sh = new THREE.Shape(p.map(([a, b]) => new THREE.Vector2((a - width / 2) * H, (b - 0.5) * H)));
    const g = new THREE.ExtrudeGeometry(sh, { depth: 0.035, bevelEnabled: true, bevelThickness: 0.004, bevelSize: 0.004, bevelSegments: 1 });
    g.translate(0, 0, 0.035);
    B.geo(MAT.bronze, g, m.clone(), 'own');
  }
  // halo on the board behind the letters
  const halo = signHaloTexture(text);
  const hw = H * (halo.wordW + 1.4) * 1.0, hh = hw / halo.aspect;
  const hm = new THREE.Mesh(new THREE.PlaneGeometry(hw, hh), basic({ map: halo.tex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, color: new THREE.Color(5.0, 3.3, 2.2) }));
  hm.applyMatrix4(faceMatrix(d.face, V3(c[0], c[1], zc)));
  const o = faceBasis(d.face).out; hm.position.addScaledVector(o, 0.012); hm.renderOrder = 3;
  W3.root.add(hm);
  const ob = faceBasis(d.face).out;
  glow(c[0] + ob.x * 0.08, c[1] + ob.z * 0.08, zc, H * (width + 1) * 1.1, 0x4a1e06);
  W3.sign = { p: c, z: zc, face: d.face };
}
function buildPoster(B, d) {
  const s = wallSpan(d);
  const hgt = d.size != null ? d.size : 1.0, zc = d.h != null ? d.h : 1.7, wid = s.L;
  const c = s.P((s.a0 + s.a1) / 2, 0);
  const m = faceMatrix(d.face, V3(c[0], c[1], zc));
  const fr = new THREE.BoxGeometry(wid, hgt, 0.03); fr.translate(0, 0, 0.015); B.geo(MAT.matteBlack, fr, m.clone(), 'own');
  const mat = std({ map: posterTexture(d.text || 'GOOD MEAT|GOOD PEOPLE'), roughness: 0.55, envMapIntensity: 0.4 });
  const pg = new THREE.PlaneGeometry(wid - 0.05, hgt - 0.05); pg.translate(0, 0, 0.0305); B.geo(mat, pg, m.clone(), 'own');
}
function buildSconce(B, d) {
  const s = wallSpan(d), z = d.h != null ? d.h : 2.2, a = (s.a0 + s.a1) / 2;
  const w0 = s.P(a, 0), w1 = s.P(a, 0.2), w2 = s.P(a, 0.3);
  const pl = s.P(a, 0.012); B.box(MAT.matteBlack, s.alongX ? [pl[0] - 0.04, pl[1] - 0.012, pl[0] + 0.04, pl[1] + 0.012] : [pl[0] - 0.012, pl[1] - 0.04, pl[0] + 0.012, pl[1] + 0.04], z + 0.08, z + 0.2);
  B.cylAB(MAT.matteBlack, [w0[0], w0[1], z + 0.14], [w1[0], w1[1], z + 0.2], 0.009, 6);
  B.cylAB(MAT.matteBlack, [w1[0], w1[1], z + 0.2], [w2[0], w2[1], z + 0.1], 0.009, 6);
  const cone = new THREE.CylinderGeometry(0.035, 0.11, 0.14, 18, 1, true); cone.translate(w2[0], z + 0.03, w2[1]); B.add(MAT.matteBlack, cone, 'own');
  const cone2 = new THREE.CylinderGeometry(0.034, 0.108, 0.138, 18, 1, true); cone2.scale(-1, 1, 1); cone2.translate(w2[0], z + 0.03, w2[1]);
  B.add(MAT.lightSoft, cone2, 'own');
  B.cylV(MAT.lightWarm, w2[0], w2[1], z - 0.045, z - 0.035, 0.1, 18);
  glow(w2[0], w2[1], z - 0.06, 0.55, 0xffa050);
  const wallGlow = s.P(a, 0.02);
  glow(wallGlow[0], wallGlow[1], z - 0.35, 1.1, 0x5a2a0c);
}
function buildPendant(CB, d) {
  const M = MODEL, x = rcx(d.rect), y = rcy(d.rect), z = d.h != null ? d.h : 1.95;
  CB.cylV(MAT.matteBlack, x, y, z + 0.2, M.ceilH, 0.004, 4);
  if (d.style === 'cylinder') {
    CB.cylV(MAT.matteBlack, x, y, z, z + 0.3, 0.055, 16);
    CB.cylV(MAT.brass, x, y, z - 0.004, z + 0.035, 0.057, 16);
    CB.cylV(MAT.lightWarm, x, y, z - 0.006, z - 0.004, 0.045, 16);
    glow(x, y, z - 0.03, 0.42, 0xffa24a);
  } else {
    const dome = new THREE.SphereGeometry(0.2, 20, 8, 0, Math.PI * 2, 0, Math.PI / 2); dome.scale(1, 0.75, 1); dome.translate(x, z, y); CB.add(MAT.matteBlack, dome, 'own');
    const inner = new THREE.SphereGeometry(0.195, 20, 8, 0, Math.PI * 2, 0, Math.PI / 2); inner.scale(-1, 0.73, 1); inner.translate(x, z, y); CB.add(MAT.lightSoft, inner, 'own');
    CB.cylV(MAT.matteBlack, x, y, z + 0.14, z + 0.22, 0.025, 10);
    CB.cylV(MAT.lightWarm, x, y, z + 0.02, z + 0.07, 0.035, 12);
    glow(x, y, z - 0.02, 0.62, 0xffb060);
  }
}
function buildFreeNiche(B, d) {
  const r = d.rect, z1 = d.h != null ? d.h : 1.0, z0 = d.z != null ? d.z : 0.1;
  const alongY = d.face === 'E' || d.face === 'W';
  const p0 = alongY ? r[1] : r[0], p1 = alongY ? r[3] : r[2], t0 = alongY ? r[0] : r[1], t1 = alongY ? r[2] : r[3];
  const fs = (d.face === 'E' || d.face === 'S') ? 1 : -1;
  const back = fs > 0 ? [t0, t0 + 0.03] : [t1 - 0.03, t1];
  const R = (a, b, c, e) => alongY ? [c, a, e, b] : [a, c, b, e];
  B.box(MAT.corten, R(p0, p1, t0, t1), 0, z0); B.box(MAT.corten, R(p0, p1, t0, t1), z1, z1 + 0.05);
  B.box(MAT.matteBlack, R(p0, p1, back[0], back[1]), z0, z1);
  B.box(MAT.corten, R(p0, p0 + 0.03, t0, t1), z0, z1); B.box(MAT.corten, R(p1 - 0.03, p1, t0, t1), z0, z1);
  if (d.type === 'planter') buildPlanter(B, alongY, p0 + 0.03, p1 - 0.03, t0 + 0.03, t1 - 0.03, z0, z1, d.face);
  else buildLogStack(alongY, p0 + 0.05, p1 - 0.05, back, fs > 0 ? t1 : t0, z0, z1, d.face);
}

/* ---------- lights (budget: 1 hemisphere + <= 9 point lights, no shadows) ---------- */
function buildLights(scene) {
  const M = MODEL, H = M.ceilH;
  const hemi = new THREE.HemisphereLight(0xffd6a8, 0x1c130c, 0.55); scene.add(hemi); W3.hemi = hemi; W3.hemiBase = 0.55;
  const add = (x, y, z, color, intensity, dist = 0, tag) => { const l = new THREE.PointLight(color, intensity, dist, 2); l.position.copy(V3(x, y, z)); scene.add(l); W3.lights.push({ l, base: intensity, tag }); return l; };
  const D = M.dining, ax = M.diningAxis;
  if (M.tables.length || M.banquettes.length) {
    for (const f of [0.18, 0.5, 0.82]) { const p = ax === 'x' ? [lerp(D[0], D[2], f), rcy(D)] : [rcx(D), lerp(D[1], D[3], f)]; add(p[0], p[1], 2.2, 0xffb46e, 9, 9, 'dining'); }
  }
  if (W3.slat) add(W3.slat.mid[0], W3.slat.mid[1], 1.9, 0xff9a4a, 9, 8, 'slat');
  const parr = M.one('parrilla');
  if (parr) { const f = frameOf(parr.rect, itemFront(M, parr)); const p = f.P(f.w / 2, f.d * 0.55); W3.fireLight = add(p[0], p[1], 1.35, 0xff7a2a, 14, 8, 'fire'); }
  const hot = HOT_KEYS.flatMap(k => M.byKey(k)).concat(M.byKey('hood'));
  if (hot.length) {
    const bb = [Math.min(...hot.map(e => e.rect[0])), Math.min(...hot.map(e => e.rect[1])), Math.max(...hot.map(e => e.rect[2])), Math.max(...hot.map(e => e.rect[3]))];
    const f = itemFront(M, hot[0]); const n = DIRV[f];
    add(rcx(bb) + n[0] * 1.3, rcy(bb) + n[1] * 1.3, H - 0.4, 0xffe7c8, 14, 8, 'kitchen');
  }
  // back-of-house: cluster remaining BOH equipment into up to 2 groups
  const boh = M.equip.filter(e => !e.overhead && M.regionAt(rcx(e.rect), rcy(e.rect)) === 2 && !HOT_KEYS.includes(e.key) && e.key !== 'smoker');
  if (boh.length) {
    const pts = boh.map(e => [rcx(e.rect), rcy(e.rect)]);
    let c = [pts[0], pts[pts.length - 1]];
    for (let it = 0; it < 8; it++) {
      const g = [[], []]; for (const p of pts) g[Math.hypot(p[0] - c[0][0], p[1] - c[0][1]) <= Math.hypot(p[0] - c[1][0], p[1] - c[1][1]) ? 0 : 1].push(p);
      c = c.map((q, i) => g[i].length ? [g[i].reduce((s, p) => s + p[0], 0) / g[i].length, g[i].reduce((s, p) => s + p[1], 0) / g[i].length] : q);
    }
    const same = Math.hypot(c[0][0] - c[1][0], c[0][1] - c[1][1]) < 2.2;
    for (const q of same ? [[(c[0][0] + c[1][0]) / 2, (c[0][1] + c[1][1]) / 2]] : c) { const s = M.snap(q[0], q[1], 0.1, 2) || q; add(s[0], s[1], H - 0.35, 0xfff1de, 12, 8, 'boh'); }
  }
  const sm = M.one('smoker');
  if (sm) { const f = frameOf(sm.rect, itemFront(M, sm)); const p = f.P(f.w / 2, f.d + 0.25); W3.smokerLight = add(p[0], p[1], 0.5, 0xff6a20, 1.6, 3, 'smoker'); }
}

/* ---------- warm environment for reflections (PMREM) ---------- */
function makeEnvironment(renderer) {
  const s = new THREE.Scene();
  const room = new THREE.Mesh(new THREE.BoxGeometry(24, 6, 10), basic({ color: 0x120d0a, side: THREE.BackSide })); room.position.y = 2; s.add(room);
  const panel = (w, h, d, x, y, z, c) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), basic({ color: c })); m.position.set(x, y, z); s.add(m); };
  panel(18, 1.6, 0.1, 0, 1.9, 4.9, new THREE.Color(1.6, 0.8, 0.3));       // slat-wall glow
  panel(4, 1.2, 0.1, -11.9, 1.6, 0, new THREE.Color(2.4, 2.2, 2.0));       // bright kitchen
  panel(0.12, 0.12, 0.12, -11.8, 1.1, 0, new THREE.Color(6, 2.5, 0.8));
  for (let x = -9; x <= 9; x += 3) { panel(0.3, 0.05, 0.3, x, 4.9, -1.2, new THREE.Color(5, 3.4, 1.8)); panel(0.3, 0.05, 0.3, x, 4.9, 1.2, new THREE.Color(5, 3.4, 1.8)); }
  panel(24, 0.1, 10, 0, -0.95, 0, new THREE.Color(0.09, 0.075, 0.06));
  const pm = new THREE.PMREMGenerator(renderer);
  const rt = pm.fromScene(s, 0.02);
  pm.dispose();
  return rt.texture;
}
