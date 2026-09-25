/* ===================================================================================
   12 equipment + furniture: every item is sized from layout.json (rect + h),
   detailed by `key` (falls back to `cat`, then to a plain box).
   =================================================================================== */

function legs(B, f, z1, inset = 0.04, r = 0.02, mat = MAT.stainlessDark) {
  for (const [u, v] of [[inset, inset], [f.w - inset, inset], [inset, f.d - inset], [f.w - inset, f.d - inset]]) { const p = f.P(u, v); B.cylV(mat, p[0], p[1], 0, z1, r, 8); }
}
function knobRow(B, f, z, n, u0 = 0.1, u1 = null, mat = MAT.matteBlack) {
  u1 = u1 == null ? f.w - 0.1 : u1;
  for (let i = 0; i < n; i++) { const u = n === 1 ? (u0 + u1) / 2 : lerp(u0, u1, i / (n - 1)); const a = f.P(u, f.d), b = f.P(u, f.d + 0.035); B.cylAB(mat, [a[0], a[1], z], [b[0], b[1], z], 0.02, 10); }
}
function doorSeams(B, f, z0, z1, n) {
  for (let i = 1; i < n; i++) { const u = f.w * i / n; B.box(MAT.matteBlack, f.R(u - 0.004, f.d - 0.004, u + 0.004, f.d + 0.002), z0, z1); }
  for (let i = 0; i < n; i++) { const u0 = f.w * i / n + 0.06, u1 = f.w * (i + 1) / n - 0.06; const a = f.P(u0, f.d + 0.02), b = f.P(u1, f.d + 0.02); B.cylAB(MAT.stainless, [a[0], a[1], z1 - 0.07], [b[0], b[1], z1 - 0.07], 0.009, 6); }
}
function counterUnit(B, f, z0, h, { doors = 0, top = MAT.stainless, body = MAT.stainless, open = false } = {}) {
  B.box(top, f.R(0, 0, f.w, f.d), h - 0.035, h);
  if (open) {
    B.box(MAT.stainlessDark, f.R(0.03, 0.03, f.w - 0.03, f.d - 0.03), z0 + 0.2, z0 + 0.225);
    legs(B, f, h - 0.035);
  } else {
    B.box(body, f.R(0.012, 0.01, f.w - 0.012, f.d - 0.012), z0 + 0.12, h - 0.035);
    B.box(MAT.matteBlack, f.R(0.03, 0.03, f.w - 0.03, f.d - 0.05), z0, z0 + 0.12);
    if (doors) doorSeams(B, f, z0 + 0.14, h - 0.05, doors);
  }
}
function backsplash(B, M, e, f, zTop) {
  const n = f.n, back = f.P(f.w / 2, -0.005);
  const t = castRay(M, back[0], back[1], -n[0], -n[1], 1).t;
  if (t > 0.15) return;
  const r = f.R(0, -t - 0.012, f.w, -t);
  B.box(e.cat === 'fire' ? MAT.stainless : MAT.stainlessDark, r, e.h - 0.03, zTop);
}

const EQ = {
  parrilla(B, e, f) {
    const h = e.h, zt = h - 0.16;
    B.box(MAT.blackSteel, f.R(0.03, 0.05, f.w - 0.03, f.d - 0.05), 0.1, zt);
    B.box(MAT.matteBlack, f.R(0.05, 0.08, f.w - 0.05, f.d - 0.08), 0, 0.1);
    doorSeams(B, f, 0.14, zt - 0.04, Math.max(1, Math.round(f.w / 0.6)));
    B.box(MAT.blackSteel, f.R(0, 0, f.w, f.d), zt, zt + 0.05);                     // tray
    B.box(MAT.blackSteel, f.R(0, 0, 0.03, f.d), zt, h + 0.35);                     // side walls
    B.box(MAT.blackSteel, f.R(f.w - 0.03, 0, f.w, f.d), zt, h + 0.35);
    B.box(MAT.blackSteel, f.R(0, 0, f.w, 0.03), zt, h + 0.62);                     // back wall
    B.box(MAT.blackSteel, f.R(0, f.d - 0.03, f.w, f.d), zt, h - 0.02);             // front lip
    B.box(MAT.stainless, f.R(0, f.d - 0.035, f.w, f.d + 0.01), h - 0.02, h);
    // embers
    const eb = f.R(0.03, 0.2, f.w - 0.03, f.d - 0.03);
    B.add(MAT.ember, hquad(eb, zt + 0.055), 'own');
    // v-grates
    const zg = h + 0.03;
    for (let u = 0.07; u < f.w - 0.05; u += 0.032) B.box(MAT.grate, f.R(u, 0.28, u + 0.008, f.d - 0.06), zg, zg + 0.012);
    for (const v of [0.28, f.d - 0.08]) B.box(MAT.grate, f.R(0.04, v, f.w - 0.04, v + 0.02), zg - 0.01, zg + 0.015);
    // brasero (fire basket) at the back
    const bz0 = zt + 0.05, bz1 = h + 0.42;
    for (let u = 0.1; u < f.w - 0.08; u += 0.06) { const p = f.P(u, 0.22); B.cylV(MAT.grate, p[0], p[1], bz0, bz1, 0.006, 6); }
    B.box(MAT.grate, f.R(0.08, 0.2, f.w - 0.08, 0.24), bz1, bz1 + 0.012);
    // logs inside basket
    for (let i = 0; i < Math.max(3, Math.round(f.w / 0.22)); i++) {
      const u = lerp(0.18, f.w - 0.18, (i + 0.5) / Math.max(3, Math.round(f.w / 0.22)));
      const p = f.P(u, 0.12);
      W3.logs.push({ x: p[0], y: p[1], z: bz0 + 0.06 + (i % 2) * 0.07, r: 0.045, len: 0.17, alongX: Math.abs(f.n[0]) > 0.5, rot: i });
    }
    // crank wheels
    for (const u of [0.12, f.w - 0.12]) {
      const p = f.P(u, f.d + 0.05);
      const g = new THREE.TorusGeometry(0.075, 0.01, 6, 18); g.rotateY(f.rot); g.translate(p[0], h - 0.06, p[1]); B.add(MAT.stainless, g, 'own');
      const q = f.P(u, f.d); B.cylAB(MAT.stainless, [q[0], q[1], h - 0.06], [p[0], p[1], h - 0.06], 0.01, 6);
    }
    // flames
    const nF = Math.max(4, Math.round(f.w / 0.17));
    for (let i = 0; i < nF; i++) {
      const u = lerp(0.14, f.w - 0.14, (i + 0.5) / nF), p = f.P(u, 0.14 + (i % 2) * 0.05);
      W3.flames.push({ x: p[0], y: p[1], z: bz0 + 0.1, w: 0.2 + (i % 3) * 0.04, h: 0.42 + (i % 2) * 0.12, ph: i * 1.7 });
    }
    for (let i = 0; i < 3; i++) { const p = f.P(lerp(0.25, f.w - 0.25, i / 2), f.d * 0.6); W3.flames.push({ x: p[0], y: p[1], z: zt + 0.1, w: 0.13, h: 0.16, ph: 5 + i * 2.3, small: true }); }
    const c = f.P(f.w / 2, f.d * 0.55); glow(c[0], c[1], zt + 0.2, 1.2, 0x9a3a0c);
    const c2 = f.P(f.w / 2, 0.15); glow(c2[0], c2[1], bz0 + 0.25, 1.4, 0xb4440c);
    W3.fire = { x: c[0], y: c[1], z: zt + 0.1 };
  },
  cocina_4q(B, e, f) {
    counterUnit(B, f, 0, e.h - 0.03, { body: MAT.stainless });
    B.box(MAT.matteBlack, f.R(0.08, f.d - 0.012, f.w - 0.08, f.d + 0.004), 0.25, e.h - 0.2);    // oven door
    const hp = [f.P(0.12, f.d + 0.03), f.P(f.w - 0.12, f.d + 0.03)]; B.cylAB(MAT.stainless, [hp[0][0], hp[0][1], e.h - 0.24], [hp[1][0], hp[1][1], e.h - 0.24], 0.01, 6);
    B.box(MAT.matteBlack, f.R(0.01, 0.01, f.w - 0.01, f.d - 0.01), e.h - 0.03, e.h);
    const nu = f.w > 0.7 ? 2 : 1, nv = 2;
    for (let i = 0; i < nu; i++) for (let j = 0; j < nv; j++) {
      const p = f.P(f.w * (i + 0.5) / nu, f.d * (j + 0.5) / nv);
      const g = new THREE.TorusGeometry(0.085, 0.012, 6, 18); g.rotateX(Math.PI / 2); g.translate(p[0], e.h + 0.02, p[1]); B.add(MAT.grate, g, 'own');
      B.boxR(MAT.grate, p[0], p[1], e.h + 0.02, 0.24, 0.018, 0.014, 0); B.boxR(MAT.grate, p[0], p[1], e.h + 0.02, 0.018, 0.24, 0.014, 0);
      glow(p[0], p[1], e.h + 0.02, 0.12, 0x1e3a8a);
    }
    knobRow(B, f, e.h - 0.12, nu * 2 + 1);
  },
  plancha(B, e, f) {
    counterUnit(B, f, 0, e.h - 0.04, { doors: 1 });
    B.box(MAT.grate, f.R(0.02, 0.06, f.w - 0.02, f.d - 0.04), e.h - 0.04, e.h);
    B.box(MAT.stainless, f.R(0, 0, f.w, 0.05), e.h - 0.04, e.h + 0.12); B.box(MAT.stainless, f.R(0, 0, 0.02, f.d), e.h - 0.04, e.h + 0.08); B.box(MAT.stainless, f.R(f.w - 0.02, 0, f.w, f.d), e.h - 0.04, e.h + 0.08);
    knobRow(B, f, e.h - 0.12, 2);
  },
  freidora(B, e, f) {
    counterUnit(B, f, 0, e.h, { doors: 1 });
    B.box(MAT.oil, f.R(0.05, 0.12, f.w - 0.05, f.d - 0.15), e.h - 0.02, e.h + 0.002);
    const nb = f.w > 0.45 ? 2 : 1;
    for (let i = 0; i < nb; i++) {
      const u0 = 0.05 + i * (f.w - 0.1) / nb + 0.01, u1 = u0 + (f.w - 0.1) / nb - 0.02;
      const r = f.R(u0, 0.14, u1, f.d - 0.2);
      for (const rr of [[r[0], r[1], r[2], r[1] + 0.008], [r[0], r[3] - 0.008, r[2], r[3]], [r[0], r[1], r[0] + 0.008, r[3]], [r[2] - 0.008, r[1], r[2], r[3]]]) B.box(MAT.grate, rr, e.h + 0.02, e.h + 0.14);
      const a = f.P((u0 + u1) / 2, f.d - 0.2), b = f.P((u0 + u1) / 2, f.d + 0.02); B.cylAB(MAT.matteBlack, [a[0], a[1], e.h + 0.12], [b[0], b[1], e.h + 0.2], 0.012, 6);
    }
    knobRow(B, f, e.h - 0.1, 1);
  },
  hood(B, e, f) {
    const M = MODEL, zb = clamp(2.05, 1.8, M.ceilH - 0.6), hh = Math.min(0.58, M.ceilH - zb - 0.12);
    const sh = new THREE.Shape([new THREE.Vector2(0, 0), new THREE.Vector2(f.d, 0), new THREE.Vector2(f.d, hh * 0.45), new THREE.Vector2(f.d * 0.62, hh), new THREE.Vector2(0, hh)]);
    const g = new THREE.ExtrudeGeometry(sh, { depth: f.w, bevelEnabled: false });
    const nx = new THREE.Vector3(f.n[0], 0, f.n[1]), uz = new THREE.Vector3(f.u[0], 0, f.u[1]);
    const o = f.P(0, 0);
    B.geo(MAT.stainless, g, new THREE.Matrix4().makeBasis(nx, new THREE.Vector3(0, 1, 0), uz).setPosition(V3(o[0], o[1], zb)), 'world');
    B.box(MAT.grate, f.R(0.05, 0.05, f.w - 0.05, f.d * 0.55), zb - 0.012, zb);
    for (let u = 0.1; u < f.w - 0.05; u += 0.5) B.box(MAT.stainlessDark, f.R(u, 0.05, u + 0.01, f.d * 0.55), zb - 0.016, zb);
    B.box(MAT.lightCool, f.R(0.08, f.d - 0.16, f.w - 0.08, f.d - 0.08), zb - 0.008, zb - 0.002, 'own');
    const dp = f.P(f.w / 2, f.d * 0.32);
    B.cylV(MAT.stainless, dp[0], dp[1], zb + hh - 0.01, M.ceilH, 0.19, 20);
    for (let u = 0.4; u < f.w - 0.2; u += 0.9) { const p = f.P(u, f.d - 0.12); glow(p[0], p[1], zb - 0.05, 0.5, 0x8a8478); }
    W3.occluders.push({ box: new THREE.Box3(V3(e.rect[0], e.rect[1], zb), V3(e.rect[2], e.rect[3], zb + hh)) });
    e._z0 = zb; e._z1 = zb + hh;
  },
  pass(B, e, f) {
    const z0 = e.overhead ? 1.45 : 0;
    if (!e.overhead) counterUnit(B, f, 0, e.h, { open: true });
    const zs = e.overhead ? 1.45 : e.h + 0.5;
    for (const u of [0.03, f.w - 0.03]) { const p = f.P(u, f.d * 0.3); B.cylV(MAT.stainless, p[0], p[1], e.overhead ? zs : e.h, zs + 0.05, 0.015, 8); }
    B.box(MAT.stainless, f.R(0, f.d * 0.05, f.w, f.d * 0.6), zs, zs + 0.035);
    B.box(MAT.lightWarm, f.R(0.04, f.d * 0.12, f.w - 0.04, f.d * 0.16), zs - 0.006, zs, 'own');
    B.box(MAT.lightWarm, f.R(0.04, f.d * 0.42, f.w - 0.04, f.d * 0.46), zs - 0.006, zs, 'own');
    B.box(MAT.stainlessDark, f.R(0, f.d * 0.58, f.w, f.d * 0.6), zs - 0.05, zs + 0.035);
    for (let u = 0.3; u < f.w - 0.2; u += 0.55) { const p = f.P(u, f.d * 0.3); glow(p[0], p[1], zs - 0.04, 0.45, 0xff7a3a); }
    if (!e.overhead) {
      const n = Math.max(1, Math.floor(f.w / 0.55));
      for (let i = 0; i < n; i++) { const p = f.P(lerp(0.3, f.w - 0.3, n === 1 ? 0.5 : i / (n - 1)), f.d * 0.45); B.cylV(MAT.white, p[0], p[1], e.h, e.h + 0.015, 0.13, 20); B.cylV(MAT.food[i % 4], p[0], p[1], e.h + 0.015, e.h + 0.045, 0.06, 10); }
    }
    void z0;
  },
  holding(B, e, f) {
    B.box(MAT.stainless, f.R(0.01, 0.01, f.w - 0.01, f.d - 0.01), 0.15, e.h); legs(B, f, 0.15, 0.05, 0.02);
    B.box(MAT.lightSoft, f.R(0.07, f.d - 0.02, f.w - 0.07, f.d - 0.012), 0.25, e.h - 0.08, 'own');
    B.box(MAT.glass, f.R(0.06, f.d - 0.01, f.w - 0.06, f.d + 0.002), 0.24, e.h - 0.07, 'own');
  },
  handwash(B, e, f) {
    const z1 = Math.min(e.h, 0.92);
    B.box(MAT.stainless, f.R(0, 0, f.w, f.d), z1 - 0.2, z1);
    B.box(MAT.stainlessDark, f.R(0.04, 0.06, f.w - 0.04, f.d - 0.04), z1 - 0.004, z1 + 0.001);
    const p = f.P(f.w / 2, 0.04); B.cylV(MAT.stainless, p[0], p[1], z1, z1 + 0.22, 0.012, 8);
    B.box(MAT.white, f.R(f.w * 0.25, -0.01, f.w * 0.75, 0.07), z1 + 0.35, z1 + 0.55);
  },
  sink_2t(B, e, f) {
    counterUnit(B, f, 0, e.h, { open: true });
    const nB = 2, bw = (f.w - 0.12) / nB;
    for (let i = 0; i < nB; i++) B.box(MAT.stainlessDark, f.R(0.06 + i * bw + 0.02, 0.1, 0.06 + (i + 1) * bw - 0.02, f.d - 0.08), e.h - 0.004, e.h + 0.001);
    B.box(MAT.stainless, f.R(0, 0, f.w, 0.03), e.h, e.h + 0.25);
    const p = f.P(0.06 + bw, 0.05); B.cylV(MAT.stainless, p[0], p[1], e.h, e.h + 0.75, 0.014, 8);
    const q = f.P(0.06 + bw, 0.35); B.cylAB(MAT.stainless, [p[0], p[1], e.h + 0.75], [q[0], q[1], e.h + 0.72], 0.012, 6);
    B.cylV(MAT.matteBlack, q[0], q[1], e.h + 0.45, e.h + 0.72, 0.02, 8);
    // stacked plates
    const s = f.P(0.06 + bw * 1.5, f.d * 0.55); B.cylV(MAT.white, s[0], s[1], e.h, e.h + 0.1, 0.12, 18);
  },
  mop_sink(B, e, f) {
    B.box(MAT.stainlessDark, f.R(0, 0, f.w, f.d), 0, 0.3); B.box(MAT.matteBlack, f.R(0.05, 0.05, f.w - 0.05, f.d - 0.05), 0.297, 0.301);
    const p = f.P(f.w / 2, 0.03); B.cylV(MAT.stainless, p[0], p[1], 0.3, 0.95, 0.012, 8);
  },
  fridge(B, e, f, doors) {
    B.box(MAT.white, f.R(0, 0.01, f.w, f.d - 0.02), 0.12, e.h - 0.02);
    B.box(MAT.matteBlack, f.R(0.02, 0.03, f.w - 0.02, f.d - 0.05), 0, 0.12);
    B.box(MAT.stainless, f.R(0, f.d - 0.02, f.w, f.d), e.h - 0.2, e.h - 0.02);
    const dp = f.R(f.w * 0.4, f.d - 0.001, f.w * 0.6, f.d + 0.001); B.box(MAT.display, dp, e.h - 0.15, e.h - 0.08, 'own');
    for (let i = 1; i < doors; i++) { const u = f.w * i / doors; B.box(MAT.matteBlack, f.R(u - 0.004, f.d - 0.025, u + 0.004, f.d - 0.018), 0.12, e.h - 0.2); }
    for (let i = 0; i < doors; i++) { const u = doors === 1 ? f.w - 0.08 : (i === 0 ? f.w / 2 - 0.06 : f.w / 2 + 0.06); const a = f.P(u, f.d - 0.02), b = f.P(u, f.d + 0.02); B.box(MAT.stainless, [Math.min(a[0], b[0]) - 0.01, Math.min(a[1], b[1]) - 0.01, Math.max(a[0], b[0]) + 0.01, Math.max(a[1], b[1]) + 0.01], 0.9, 1.5); }
  },
  fridge_2d(B, e, f) { EQ.fridge(B, e, f, 2); },
  freezer_1d(B, e, f) { EQ.fridge(B, e, f, 1); },
  mesa_fria(B, e, f) {
    counterUnit(B, f, 0, e.h, { doors: Math.max(1, Math.round(f.w / 0.6)) });
    const n = Math.max(2, Math.floor((f.w - 0.1) / 0.17));
    for (let i = 0; i < n; i++) { const u = 0.05 + (f.w - 0.1) * (i + 0.5) / n; B.box(MAT.food[i % MAT.food.length], f.R(u - 0.075, 0.05, u + 0.075, 0.3), e.h - 0.01, e.h + 0.012); }
    B.box(MAT.white, f.R(0.05, 0.36, f.w - 0.05, f.d - 0.03), e.h, e.h + 0.015);
  },
  mesa(B, e, f) {
    counterUnit(B, f, 0, e.h, { open: true });
    B.box(MAT.white, f.R(f.w * 0.15, 0.15, f.w * 0.45, f.d - 0.12), e.h, e.h + 0.02);
    const p = f.P(f.w * 0.75, f.d * 0.45); B.cylV(MAT.stainlessDark, p[0], p[1], e.h, e.h + 0.14, 0.11, 16);
  },
  mesa_1(B, e, f) { EQ.mesa(B, e, f); }, mesa_2(B, e, f) { EQ.mesa(B, e, f); }, mesa_opt(B, e, f) { EQ.mesa(B, e, f); },
  shelf_4(B, e, f) {
    const lv = [0.18, 0.62, 1.06, 1.5, e.h - 0.02].filter(z => z <= e.h);
    for (const u of [0.02, f.w - 0.02]) for (const v of [0.02, f.d - 0.02]) { const p = f.P(u, v); B.cylV(MAT.stainless, p[0], p[1], 0, e.h, 0.014, 6); }
    const rnd = mulberry32(Math.round(e.rect[0] * 999));
    for (const z of lv) {
      B.box(MAT.stainlessDark, f.R(0, 0, f.w, f.d), z, z + 0.02);
      if (z > e.h - 0.1) continue;
      let u = 0.05;
      while (u < f.w - 0.15) { const w = 0.12 + rnd() * 0.2, hh = 0.1 + rnd() * 0.22; const m = [MAT.white, MAT.kraft, MAT.stainlessDark, MAT.white][(rnd() * 4) | 0]; B.box(m, f.R(u, 0.04, Math.min(f.w - 0.04, u + w), f.d - 0.04), z + 0.02, z + 0.02 + hh); u += w + 0.03 + rnd() * 0.08; }
    }
  },
  smoker(B, e, f) {
    const h = e.h;
    B.box(MAT.blackSteel, f.R(0.02, 0.02, f.w - 0.02, f.d - 0.04), 0.15, h);
    legs(B, f, 0.15, 0.06, 0.03, MAT.matteBlack);
    const split = 0.15 + (h - 0.15) * 0.33;
    B.box(MAT.matteBlack, f.R(0.02, f.d - 0.045, f.w - 0.02, f.d - 0.035), split - 0.01, split + 0.01);
    // firebox door with glowing vent
    const vent = f.R(f.w * 0.25, f.d - 0.042, f.w * 0.75, f.d - 0.03);
    B.box(MAT.ember, vent, 0.28, 0.34, 'own');
    const gp = f.P(f.w / 2, f.d); glow(gp[0], gp[1], 0.31, 0.7, 0xc2410c);
    W3.smokerGlow = { x: gp[0], y: gp[1] };
    // handles, thermometer
    for (const z of [split - 0.12, h - 0.25]) { const a = f.P(f.w * 0.3, f.d - 0.03), b = f.P(f.w * 0.7, f.d - 0.03); const a2 = f.P(f.w * 0.3, f.d + 0.03), b2 = f.P(f.w * 0.7, f.d + 0.03); B.cylAB(MAT.brass, [a2[0], a2[1], z], [b2[0], b2[1], z], 0.012, 6); B.cylAB(MAT.brass, [a[0], a[1], z], [a2[0], a2[1], z], 0.01, 6); B.cylAB(MAT.brass, [b[0], b[1], z], [b2[0], b2[1], z], 0.01, 6); }
    const t = f.P(f.w / 2, f.d - 0.03), t2 = f.P(f.w / 2, f.d); B.cylAB(MAT.white, [t[0], t[1], h - 0.4], [t2[0], t2[1], h - 0.4], 0.05, 16);
    const fl = f.P(f.w * 0.75, f.d * 0.4); B.cylV(MAT.matteBlack, fl[0], fl[1], h, MODEL.ceilH, 0.09, 14);
  },
  fuel_storage(B, e, f) {
    const lv = [0.05, e.h * 0.5, e.h - 0.03];
    for (const u of [0.02, f.w - 0.02]) for (const v of [0.02, f.d - 0.02]) { const p = f.P(u, v); B.cylV(MAT.matteBlack, p[0], p[1], 0, e.h, 0.016, 6); }
    for (const z of lv) B.box(MAT.matteBlack, f.R(0, 0, f.w, f.d), z, z + 0.025);
    const alongX = Math.abs(f.u[0]) < 0.5; // logs run front-to-back
    const rnd = mulberry32(Math.round(e.rect[1] * 997));
    for (let k = 0; k < lv.length - 1; k++) {
      const z0 = lv[k] + 0.025, z1 = lv[k + 1] - 0.02, rows = Math.max(1, Math.floor((z1 - z0) / 0.09));
      for (let j = 0; j < rows; j++) for (let u = 0.07; u < f.w - 0.05; u += 0.1) {
        if (k === 0 && u > f.w * 0.55) continue;
        const p = f.P(u + (j % 2) * 0.05, f.d / 2);
        W3.logs.push({ x: p[0], y: p[1], z: z0 + 0.045 + j * 0.085, r: 0.04 + rnd() * 0.012, len: Math.min(0.42, f.d - 0.06), alongX, rot: rnd() * 6 });
      }
      if (k === 0) B.box(MAT.matteBlack, f.R(f.w * 0.58, 0.05, f.w - 0.04, f.d - 0.05), z0, z0 + Math.min(0.4, z1 - z0));
    }
  },
  delivery_staging(B, e, f) {
    const lv = [0.3, e.h * 0.62, e.h - 0.03];
    for (const u of [0.02, f.w - 0.02]) for (const v of [0.02, f.d - 0.02]) { const p = f.P(u, v); B.cylV(MAT.matteBlack, p[0], p[1], 0, e.h, 0.014, 6); }
    const rnd = mulberry32(Math.round(e.rect[1] * 313));
    for (const z of lv) {
      B.box(MAT.matteBlack, f.R(0, 0, f.w, f.d), z, z + 0.02);
      if (z > e.h - 0.1) continue;
      let u = 0.04; while (u < f.w - 0.2) { const w = 0.2 + rnd() * 0.06; B.box(MAT.kraft, f.R(u, 0.06, u + w, f.d - 0.08), z + 0.02, z + 0.26 + rnd() * 0.06, 'own'); u += w + 0.04; }
    }
    const p = f.P(f.w * 0.5, f.d * 0.5); B.boxR(MAT.screen, p[0], p[1], e.h + 0.1, 0.2, 0.02, 0.14, f.rot);
  },
  barra(B, e, f) {
    const h = e.h, back = 0.05;
    B.box(MAT.matteBlack, f.R(back, 0.04, f.w - 0.02, f.d - 0.16), 0, h - 0.05);
    // customer face: vertical walnut fluting
    for (let u = 0.02; u < f.w - 0.02; u += 0.045) B.box(MAT.walnut, f.R(u, f.d - 0.165, Math.min(f.w - 0.02, u + 0.035), f.d - 0.13), 0.1, h - 0.06);
    B.box(MAT.ledStrip, f.R(0.03, f.d - 0.15, f.w - 0.03, f.d - 0.14), 0.06, 0.075, 'own');
    B.box(MAT.oak, f.R(0, 0, f.w, f.d), h - 0.055, h);
    const a = f.P(0.05, f.d - 0.08), b = f.P(f.w - 0.05, f.d - 0.08);
    B.cylAB(MAT.brass, [a[0], a[1], 0.22], [b[0], b[1], 0.22], 0.022, 10);
    for (let u = 0.3; u < f.w - 0.1; u += 1.0) { const p = f.P(u, f.d - 0.08), q = f.P(u, f.d - 0.15); B.cylAB(MAT.brass, [p[0], p[1], 0.22], [q[0], q[1], 0.15], 0.012, 6); }
    // bartender side: under-counter shelf with glasses
    B.box(MAT.stainlessDark, f.R(0.02, 0.0, f.w - 0.02, 0.05), 0.6, 0.62);
    for (let u = 0.25; u < f.w - 0.2; u += 0.7) { const p = f.P(u, f.d * 0.3); for (let k = 0; k < 3; k++) { const q = f.P(u + k * 0.09, f.d * 0.3); B.cylV(MAT.bottle, q[0], q[1], h, h + 0.24, 0.035, 10); B.cylV(MAT.bottle, q[0], q[1], h + 0.24, h + 0.32, 0.012, 8); } void p; }
    const L = f.P(f.w * 0.5, f.d - 0.2); glow(L[0], L[1], 0.1, 0.7, 0x5a2a0c);
  },
  pos(B, e, f, z0) {
    const zb = z0 || 0;
    const p = f.P(f.w / 2, f.d / 2);
    B.boxR(MAT.matteBlack, p[0], p[1], zb + 0.02, 0.18, 0.14, 0.04, f.rot);
    B.cylV(MAT.matteBlack, p[0], p[1], zb + 0.04, zb + 0.16, 0.015, 8);
    const g = new THREE.BoxGeometry(0.3, 0.2, 0.02); g.rotateX(-0.35); g.rotateY(f.rot); g.translate(p[0], zb + 0.24, p[1]); B.add(MAT.matteBlack, g, 'own');
    const s = new THREE.PlaneGeometry(0.27, 0.17); s.translate(0, 0, 0.011); s.rotateX(-0.35); s.rotateY(f.rot); s.translate(p[0], zb + 0.24, p[1]); B.add(MAT.screen, s, 'own');
  },
  back_bar(B, e, f) {
    B.box(MAT.walnut, f.R(0, 0, f.w, f.d), 0, 0.9);
    B.box(MAT.lightSoft, f.R(0.02, 0.0, f.w - 0.02, 0.02), 0.95, e.h, 'own');
    for (const z of [1.25, 1.65]) { B.box(MAT.oak, f.R(0, 0, f.w, f.d * 0.8), z, z + 0.03); for (let u = 0.08; u < f.w - 0.05; u += 0.09) { const p = f.P(u, f.d * 0.4); B.cylV(MAT.bottle, p[0], p[1], z + 0.03, z + 0.26, 0.032, 8); } }
  },
  host(B, e, f) { B.box(MAT.walnut, f.R(0.02, 0.02, f.w - 0.02, f.d - 0.02), 0, e.h - 0.04); B.box(MAT.oak, f.R(0, 0, f.w, f.d), e.h - 0.04, e.h); const p = f.P(f.w * 0.7, f.d * 0.5); B.cylV(MAT.brass, p[0], p[1], e.h, e.h + 0.3, 0.008, 6); B.cylV(MAT.lightWarm, p[0], p[1], e.h + 0.3, e.h + 0.36, 0.04, 10); glow(p[0], p[1], e.h + 0.34, 0.4, 0xffa050); },
  trash(B, e, f) { const p = f.P(f.w / 2, f.d / 2); B.cylV(MAT.matteBlack, p[0], p[1], 0, e.h, Math.min(f.w, f.d) / 2 - 0.01, 16); },
  ice(B, e, f) { counterUnit(B, f, 0, e.h, { doors: 1 }); },
};

function genericEquip(B, e, f) {
  const byCat = { fire: MAT.stainless, cold: MAT.white, prep: MAT.stainless, wash: MAT.stainless, storage: MAT.stainlessDark, smoker: MAT.blackSteel, bar: MAT.walnut, delivery: MAT.matteBlack };
  if (e.overhead) { B.box(MAT.stainless, e.rect, Math.max(1.6, MODEL.ceilH - 0.9), Math.max(1.6, MODEL.ceilH - 0.9) + Math.min(0.4, e.h)); return; }
  if (e.cat === 'prep' || e.cat === 'wash' || e.cat === 'fire') counterUnit(B, f, 0, e.h, { doors: Math.max(1, Math.round(f.w / 0.6)) });
  else B.box(byCat[e.cat] || MAT.stainlessDark, e.rect, 0, e.h);
}

function buildEquipment(B, CB, SB) {
  const M = MODEL;
  for (const e of M.equip) {
    try {
      const front = itemFront(M, e), f = frameOf(e.rect, front);
      const base = e.stack ? (M.equip.find(q => q.id === e.stack) || {}).h || 0 : 0;
      const key = e.key.replace(/^freidora_\d+$/, 'freidora');
      if (e.key === 'pos') EQ.pos(B, e, f, base);
      else if (EQ[key]) (e.key === 'hood' ? EQ.hood(CB, e, f) : EQ[key](B, e, f));
      else genericEquip(B, e, f);
      if (!e.overhead && ['fire', 'prep', 'wash', 'cold'].includes(e.cat) && e.h < 1.4 && e.key !== 'mop_sink') backsplash(B, M, e, f, e.cat === 'fire' ? 1.98 : e.h + 0.3);
      if (!e.overhead && !e.stack) SB.add(MAT.blob, blobQuad(e.rect, 1.18), 'own');
      const z0 = e._z0 != null ? e._z0 : (e.overhead ? 1.8 : base), z1 = e._z1 != null ? e._z1 : (e.overhead ? MODEL.ceilH - 0.3 : Math.max(base + 0.05, e.key === 'pos' ? base + 0.36 : e.h));
      W3.picks.push({ kind: 'equipment', item: e, box: new THREE.Box3(V3(e.rect[0], e.rect[1], z0), V3(e.rect[2], e.rect[3], z1)) });
    } catch (err) { console.warn('LAVA: equipo', e.id, err); }
  }
}
function blobQuad(r, s = 1.2, z = 0.004) { const g = new THREE.PlaneGeometry(rw(r) * s + 0.12, rh(r) * s + 0.12); g.rotateX(-Math.PI / 2); g.translate(rcx(r), z, rcy(r)); return g; }

/* ---------- furniture ---------- */
function chairGeometries() {
  const seatShape = new THREE.Shape(); const w = 0.46, d = 0.43, rr = 0.07;
  seatShape.moveTo(-w / 2 + rr, -d / 2); seatShape.lineTo(w / 2 - rr, -d / 2); seatShape.quadraticCurveTo(w / 2, -d / 2, w / 2, -d / 2 + rr); seatShape.lineTo(w / 2, d / 2 - rr); seatShape.quadraticCurveTo(w / 2, d / 2, w / 2 - rr, d / 2);
  seatShape.lineTo(-w / 2 + rr, d / 2); seatShape.quadraticCurveTo(-w / 2, d / 2, -w / 2, d / 2 - rr); seatShape.lineTo(-w / 2, -d / 2 + rr); seatShape.quadraticCurveTo(-w / 2, -d / 2, -w / 2 + rr, -d / 2);
  const seat = new THREE.ExtrudeGeometry(seatShape, { depth: 0.05, bevelEnabled: true, bevelThickness: 0.02, bevelSize: 0.02, bevelSegments: 3, curveSegments: 4 });
  seat.rotateX(-Math.PI / 2); seat.translate(0, 0.44, 0.02);
  const arc = new THREE.Shape(); const R1 = 0.265, R0 = 0.228, a0 = 0.2, a1 = Math.PI - 0.2;
  arc.absarc(0, 0, R1, a0, a1, false); arc.absarc(0, 0, R0, a1, a0, true);
  const back = new THREE.ExtrudeGeometry(arc, { depth: 0.27, bevelEnabled: true, bevelThickness: 0.012, bevelSize: 0.012, bevelSegments: 2, curveSegments: 16 });
  back.rotateX(-Math.PI / 2); back.translate(0, 0.52, 0.05);
  const fabric = mergeGeometries([seat.toNonIndexed ? seat : seat, back].map(g => { g = g.index ? g.toNonIndexed() : g; for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k); g.clearGroups(); return g; }));
  const parts = [];
  for (const [x, z] of [[-0.19, -0.16], [0.19, -0.16], [-0.19, 0.19], [0.19, 0.19]]) { const g = new THREE.CylinderGeometry(0.011, 0.009, 0.45, 8); g.translate(x, 0.225, z); parts.push(g); }
  const ring = new THREE.TorusGeometry(0.247, 0.008, 6, 20, Math.PI - 0.4); ring.rotateX(-Math.PI / 2); ring.rotateY(0.2 + Math.PI); ring.rotateY(Math.PI); ring.translate(0, 0.8, 0.05);
  parts.push(ring);
  const fr = new THREE.BoxGeometry(0.4, 0.015, 0.012); fr.translate(0, 0.43, 0.19); parts.push(fr);
  const fr2 = fr.clone(); fr2.translate(0, 0, -0.35); parts.push(fr2);
  const brass = mergeGeometries(parts.map(g => { g = g.index ? g.toNonIndexed() : g; for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k); g.clearGroups(); return g; }));
  return { fabric, brass };
}

function buildFurniture(B, SB) {
  const M = MODEL;
  // tables
  const rnd = mulberry32(7);
  for (const t of M.tables) {
    const r = t.rect, top = 0.75;
    B.box(MAT.oak, r, top - 0.035, top);
    const long = Math.max(rw(r), rh(r)) > 1.05, alongX = rw(r) >= rh(r);
    const bases = long ? [0.28, 0.72] : [0.5];
    for (const f of bases) {
      const p = alongX ? [lerp(r[0], r[2], f), rcy(r)] : [rcx(r), lerp(r[1], r[3], f)];
      B.box(MAT.matteBlack, [p[0] - 0.03, p[1] - 0.03, p[0] + 0.03, p[1] + 0.03], 0.02, top - 0.035);
      const L = Math.min(rw(r), rh(r)) * 0.38 + 0.08;
      B.box(MAT.matteBlack, [p[0] - L, p[1] - 0.025, p[0] + L, p[1] + 0.025], 0, 0.025);
      B.box(MAT.matteBlack, [p[0] - 0.025, p[1] - L, p[0] + 0.025, p[1] + L], 0, 0.025);
    }
    // settings
    const cx = rcx(r), cy = rcy(r);
    const ch = M.chairs.find(c => c.table === t.id) || M.chairs.slice().sort((a, b) => Math.hypot(rcx(a.rect) - cx, rcy(a.rect) - cy) - Math.hypot(rcx(b.rect) - cx, rcy(b.rect) - cy))[0];
    let dir = ch ? [rcx(ch.rect) - cx, rcy(ch.rect) - cy] : (alongX ? [0, 1] : [1, 0]);
    const dl = Math.hypot(dir[0], dir[1]) || 1; dir = [dir[0] / dl, dir[1] / dl];
    const perp = [-dir[1], dir[0]];
    const off = Math.min(rw(r), rh(r)) * 0.28;
    const seats = t.seats >= 4 && long ? [[0.25, 1], [-0.25, 1], [0.25, -1], [-0.25, -1]] : [[0, 1], [0, -1]];
    for (const [s, k] of seats) {
      const p = [cx + dir[0] * off * k + perp[0] * s * Math.max(rw(r), rh(r)), cy + dir[1] * off * k + perp[1] * s * Math.max(rw(r), rh(r))];
      B.cylV(MAT.plate, p[0], p[1], top, top + 0.012, 0.115, 20);
      B.cylV(MAT.plate, p[0], p[1], top + 0.012, top + 0.018, 0.08, 16);
    }
    const cp = [cx + perp[0] * 0.08, cy + perp[1] * 0.08];
    B.cylV(MAT.amberGlass, cp[0], cp[1], top, top + 0.065, 0.028, 12);
    glow(cp[0], cp[1], top + 0.07, 0.34, 0xffa040);
    if (rnd() > 0.35) { const bp = [cx - perp[0] * 0.12 + dir[0] * 0.02, cy - perp[1] * 0.12 + dir[1] * 0.02]; B.cylV(MAT.bottle, bp[0], bp[1], top, top + 0.19, 0.034, 12); B.cylV(MAT.bottle, bp[0], bp[1], top + 0.19, top + 0.24, 0.014, 10, 'own', 0.012); }
    SB.add(MAT.blob, blobQuad(r, 1.25), 'own');
    W3.picks.push({ kind: 'table', item: t, box: new THREE.Box3(V3(r[0], r[1], 0), V3(r[2], r[3], top)) });
  }
  // banquettes
  for (const b of M.banquettes) {
    const r = b.rect, alongX = rw(r) >= rh(r);
    let back = b.back;
    if (!back) {
      const cands = alongX ? ['N', 'S'] : ['E', 'W'];
      const tl = M.tables.map(t => [rcx(t.rect), rcy(t.rect)]).sort((p, q) => Math.hypot(p[0] - rcx(r), p[1] - rcy(r)) - Math.hypot(q[0] - rcx(r), q[1] - rcy(r)))[0];
      if (tl) { const dx = tl[0] - rcx(r), dy = tl[1] - rcy(r); back = alongX ? (dy > 0 ? 'N' : 'S') : (dx > 0 ? 'W' : 'E'); }
      else back = cands.map(c => [c, castRay(M, rcx(r), rcy(r), DIRV[c][0], DIRV[c][1], 5).t]).sort((p, q) => p[1] - q[1])[0][0];
    }
    const front = { N: 'S', S: 'N', E: 'W', W: 'E' }[back];
    const f = frameOf(r, front);
    B.box(MAT.matteBlack, f.R(0.01, 0.04, f.w - 0.01, f.d - 0.03), 0, 0.1);
    const sg = new THREE.BoxGeometry(1, 1, 1);
    void sg;
    B.box(MAT.fabric, f.R(0.005, 0.1, f.w - 0.005, f.d - 0.005), 0.1, 0.43);
    B.box(MAT.fabric, f.R(0.005, 0.12, f.w - 0.005, f.d - 0.02), 0.43, 0.46);
    B.box(MAT.fabricBack, f.R(0, 0, f.w, 0.07), 0.1, 1.0);
    const n = Math.max(2, Math.round(f.w / 0.19)), cw = f.w / n;
    for (let i = 0; i < n; i++) {
      const u = (i + 0.5) * cw, p = f.P(u, 0.1);
      const g = new THREE.CylinderGeometry(cw * 0.5, cw * 0.5, 0.5, 10, 1, false, 0, Math.PI * 2);
      g.scale(1, 1, 0.55); g.rotateX(-0.12); g.rotateY(f.rot); g.translate(p[0], 0.725, p[1]);
      B.add(MAT.fabric, g, 'own');
    }
    B.box(MAT.walnut, f.R(0, 0, f.w, 0.12), 1.0, 1.03);
    SB.add(MAT.blob, blobQuad(r, 1.08), 'own');
    W3.picks.push({ kind: 'banquette', item: b, box: new THREE.Box3(V3(r[0], r[1], 0), V3(r[2], r[3], 1.0)) });
  }
  // chairs (instanced)
  if (M.chairs.length) {
    const { fabric, brass } = chairGeometries();
    const fm = new THREE.InstancedMesh(fabric, MAT.fabric, M.chairs.length), bm = new THREE.InstancedMesh(brass, MAT.brass, M.chairs.length);
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s3 = new THREE.Vector3();
    M.chairs.forEach((c, i) => {
      const cx = rcx(c.rect), cy = rcy(c.rect);
      let ang;
      if (c.facing) { const d = DIRV[c.facing]; ang = Math.atan2(d[0], d[1]); }
      else {
        const t = M.tables.find(tt => tt.id === c.table) || M.tables.slice().sort((a, b) => Math.hypot(rcx(a.rect) - cx, rcy(a.rect) - cy) - Math.hypot(rcx(b.rect) - cx, rcy(b.rect) - cy))[0];
        ang = t ? Math.atan2(rcx(t.rect) - cx, rcy(t.rect) - cy) : 0;
      }
      const sc = clamp(Math.min(rw(c.rect), rh(c.rect)) / 0.45, 0.85, 1.15);
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), ang); s3.set(sc, 1, sc);
      m4.compose(V3(cx, cy, 0), q, s3); fm.setMatrixAt(i, m4); bm.setMatrixAt(i, m4);
      SB.add(MAT.blob, blobQuad(c.rect, 1.1), 'own');
    });
    fm.instanceMatrix.needsUpdate = bm.instanceMatrix.needsUpdate = true;
    W3.root.add(fm, bm);
  }
}

function buildLogs() {
  if (!W3.logs.length) return;
  const g = new THREE.CylinderGeometry(1, 1, 1, 9, 1);
  const im = new THREE.InstancedMesh(g, [MAT.bark, MAT.endgrain, MAT.endgrain], W3.logs.length);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), q2 = new THREE.Quaternion(), s = new THREE.Vector3();
  W3.logs.forEach((l, i) => {
    q.setFromAxisAngle(l.alongX ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1, 0, 0), Math.PI / 2);
    q2.setFromAxisAngle(new THREE.Vector3(0, 1, 0), l.rot || 0); q.multiply(q2);
    s.set(l.r, l.len, l.r); m4.compose(V3(l.x, l.y, l.z), q, s); im.setMatrixAt(i, m4);
  });
  im.instanceMatrix.needsUpdate = true;
  W3.root.add(im);
}
