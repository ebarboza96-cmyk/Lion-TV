/* ===================================================================================
   15 aerial: dollhouse orbit view (ceiling hidden, walls cut), zone tints A–E and
   route ribbons (clean blue, dirty red dashed, guest green, delivery yellow, fuel brown).
   =================================================================================== */

const CUT_H = 2.25;

function textSprite(text, sub, color) {
  const c = mkCanvas(512, 160), x = c.getContext('2d');
  x.fillStyle = 'rgba(20,18,16,.82)'; const r = 26;
  x.beginPath(); x.moveTo(r, 8); x.arcTo(504, 8, 504, 152, r); x.arcTo(504, 152, 8, 152, r); x.arcTo(8, 152, 8, 8, r); x.arcTo(8, 8, 504, 8, r); x.fill();
  x.fillStyle = color || '#ece5d8'; x.font = '800 64px "Big Shoulders Display","Arial Narrow",sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle';
  x.fillText(text, 256, sub ? 60 : 80);
  if (sub) { x.fillStyle = '#ece5d8'; x.font = '500 34px Figtree,sans-serif'; x.fillText(sub.length > 26 ? sub.slice(0, 25) + '…' : sub, 256, 116); }
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex(c, { repeat: false, aniso: false }), depthTest: false, transparent: true }));
  sp.scale.set(1.5, 0.47, 1); sp.renderOrder = 20;
  return sp;
}

function buildAerialLayers(scene) {
  const M = MODEL;
  const zones = new THREE.Group(), routes = new THREE.Group(), labels = new THREE.Group(), caps = new THREE.Group();
  for (const z of M.zones) {
    const g = new THREE.ShapeGeometry(new THREE.Shape(z.poly.map(p => new THREE.Vector2(p[0], p[1])))); g.rotateX(Math.PI / 2);
    const m = new THREE.Mesh(g, basic({ color: new THREE.Color(z.color), transparent: true, opacity: 0.26, depthWrite: false, side: THREE.DoubleSide }));
    m.position.y = 0.012; m.renderOrder = 2; zones.add(m);
    const s = textSprite(z.id, z.name, z.color); s.position.copy(V3(z.c[0], z.c[1], 1.2)); labels.add(s);
  }
  for (const r of M.routes) {
    const col = new THREE.Color(ROUTE_COLOR[r.kind] || '#cccccc');
    const B = new Batch(); const w = 0.09, dashed = r.kind === 'dirty';
    for (let i = 1; i < r.pts.length; i++) {
      const a = r.pts[i - 1], b = r.pts[i], L = Math.hypot(b[0] - a[0], b[1] - a[1]); if (L < 1e-3) continue;
      const pieces = dashed ? Math.max(1, Math.floor(L / 0.34)) : 1;
      for (let k = 0; k < pieces; k++) {
        const t0 = k / pieces, t1 = dashed ? (k + 0.6) / pieces : 1;
        const p0 = [lerp(a[0], b[0], t0), lerp(a[1], b[1], t0)], p1 = [lerp(a[0], b[0], t1), lerp(a[1], b[1], t1)];
        const len = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]);
        const g = new THREE.PlaneGeometry(len + (dashed ? 0 : w), w); g.rotateX(-Math.PI / 2); g.rotateY(-Math.atan2(p1[1] - p0[1], p1[0] - p0[0]));
        g.translate((p0[0] + p1[0]) / 2, 0.06, (p0[1] + p1[1]) / 2); B.add(null, g, 'own');
      }
    }
    // arrow head
    const a = r.pts[r.pts.length - 2], b = r.pts[r.pts.length - 1], ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
    const tri = new THREE.BufferGeometry(); const s = 0.26;
    const P = (dx, dy) => [b[0] + Math.cos(ang) * dx - Math.sin(ang) * dy, b[1] + Math.sin(ang) * dx + Math.cos(ang) * dy];
    const q = [P(0.05, 0), P(-s, s * 0.6), P(-s, -s * 0.6)];
    tri.setAttribute('position', new THREE.Float32BufferAttribute([q[0][0], 0.06, q[0][1], q[2][0], 0.06, q[2][1], q[1][0], 0.06, q[1][1]], 3)); tri.computeVertexNormals();
    B.add(null, tri, 'own');
    const list = B.m.get(null) || [];
    const geo = mergeGeometries(list, false);
    const mesh = new THREE.Mesh(geo, basic({ color: col, transparent: true, opacity: 0.95, depthTest: false, side: THREE.DoubleSide }));
    mesh.renderOrder = 10; routes.add(mesh);
  }
  const CBt = new Batch();
  for (const r of W3.caps) CBt.add(MAT.cap, hquad(r, CUT_H + 0.002), 'own');
  CBt.flush(caps);
  // entrance marker
  const ent = textSprite('ENTRADA', null, '#ff6a1a'); ent.scale.set(1.2, 0.38, 1); ent.position.copy(V3(M.entrance[0] + 0.6, M.entrance[1], 0.8)); labels.add(ent);
  // "you are here"
  const you = new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.5, 16), basic({ color: 0xff6a1a })); you.rotation.x = Math.PI; you.renderOrder = 11;
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.22, 0.3, 24), basic({ color: 0xff6a1a, side: THREE.DoubleSide, transparent: true, opacity: 0.8, depthTest: false })); ring.rotation.x = -Math.PI / 2; ring.renderOrder = 11;
  const youG = new THREE.Group(); youG.add(you, ring); you.position.y = 0.6; ring.position.y = 0.05;
  for (const g of [zones, routes, labels, caps, youG]) { g.visible = false; scene.add(g); }
  W3.aer = { zones, routes, labels, caps, you: youG };
  // legend
  const leg = $('#route-legend'); leg.replaceChildren();
  for (const k of [...new Set(M.routes.map(r => r.kind))]) {
    const svg = document.createElementNS(SVGNS, 'svg'); svg.setAttribute('viewBox', '0 0 30 8');
    svg.append(sv('line', { x1: 1, y1: 4, x2: 29, y2: 4, stroke: ROUTE_COLOR[k] || '#ccc', 'stroke-width': 3, 'stroke-dasharray': k === 'dirty' ? '5 3' : null }));
    leg.append(svg, el('span', null, ROUTE_ES[k] || k));
  }
  if (!M.routes.length) leg.append(el('span', { style: 'grid-column:1/-1' }, 'El layout no define rutas.'));
}

function toggleAerial(force) {
  if (!W3.renderer) return;
  const on = force == null ? !W3.aerial : !!force;
  if (on === !!W3.aerial) return;
  W3.aerial = on;
  const M = MODEL, cam = W3.camera;
  $('#btn-aerial').setAttribute('aria-pressed', String(on));
  $('#layers').hidden = !on;
  $('#joy').hidden = on || !COARSE;
  W3.ceiling.visible = !on;
  W3.glowPoints && (W3.glowPoints.visible = !on);
  for (const k of ['caps', 'labels', 'you']) W3.aer[k].visible = on;
  W3.aer.zones.visible = on && $('#tg-zones').checked;
  W3.aer.routes.visible = on && $('#tg-routes').checked;
  W3.renderer.clippingPlanes = on ? [new THREE.Plane(new THREE.Vector3(0, -1, 0), CUT_H)] : [];
  W3.hemi.intensity = on ? 1.6 : W3.hemiBase;
  if (on) {
    cancelTourMotion(); $('#caption').hidden = true;
    const bb = M.pbb, cx = (bb[0] + bb[2]) / 2, cy = (bb[1] + bb[3]) / 2;
    const target = V3(cx, cy, 0);
    // fit the premises: portrait screens look along X so the long axis runs vertically
    const portrait = cam.aspect < 0.9, radius = Math.hypot(rw(bb), rh(bb)) / 2;
    const vf = 42 * Math.PI / 180, hf = 2 * Math.atan(Math.tan(vf / 2) * cam.aspect);
    const dist = radius / Math.sin(Math.min(vf, hf) / 2) * (portrait ? 0.82 : 0.78);
    const el = 0.95, dir = portrait ? new THREE.Vector3(Math.cos(el), Math.sin(el), 0.18).normalize() : new THREE.Vector3(0.08, Math.sin(el), Math.cos(el)).normalize();
    const end = target.clone().addScaledVector(dir, dist);
    W3.controls.target.copy(target); W3.controls.enabled = true;
    cam.fov = 42; cam.updateProjectionMatrix();
    if (REDUCED) { cam.position.copy(end); cam.lookAt(target); }
    else { W3.fly = { t: 0, dur: 1.3, from: cam.position.clone(), to: end, lookFrom: V3(WALK.x + Math.cos(WALK.yaw) * 3, WALK.y + Math.sin(WALK.yaw) * 3, EYE), lookTo: target }; }
  } else {
    W3.controls.enabled = false; W3.fly = null;
    setFov();
  }
  emit('aerial', on);
}
