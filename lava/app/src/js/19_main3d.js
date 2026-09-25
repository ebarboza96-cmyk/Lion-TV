/* ===================================================================================
   19 main3d: lazy three.js import, renderer, scene assembly, animation loop,
   resize + adaptive resolution, WebGL failure handling.
   =================================================================================== */

function webglOK() {
  try { const c = document.createElement('canvas'); return !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl'))); } catch (e) { return false; }
}
function fail3D(msg) {
  $('#loader').hidden = true;
  $('#fail-msg').textContent = msg;
  $('#fail3d').hidden = false;
  for (const s of ['.rail', '.hud-top', '#minimap', '#joy', '#caption']) { const n = $(s); if (n) n.hidden = true; }
}
function loaderStep(p, msg) { const f = $('#loader-fill'); if (f) f.style.width = Math.round(p * 100) + '%'; if (msg) $('#loader-msg').textContent = msg; return nextFrame(); }

function setFov() {
  const cam = W3.camera; if (!cam || W3.aerial) return;
  const a = cam.aspect || 1;
  // keep >= ~52 deg horizontal on portrait phones
  cam.fov = clamp(Math.max(65, 2 * Math.atan(Math.tan(26 * Math.PI / 180) / a) * 180 / Math.PI), 50, 86);
  cam.updateProjectionMatrix();
}

let STARTED3D = false;
async function start3D() {
  if (STARTED3D) return; STARTED3D = true;
  await loaderStep(0.05, 'Encendiendo la parrilla…');
  if (!webglOK()) { fail3D('Este navegador o dispositivo no puede mostrar gráficos 3D (WebGL desactivado o no disponible). El plano y los datos siguen disponibles.'); return; }
  try {
    THREE = await import('three');
    ({ OrbitControls } = await import('three/addons/controls/OrbitControls.js'));
    ({ mergeGeometries } = await import('three/addons/utils/BufferGeometryUtils.js'));
  } catch (e) {
    console.warn('LAVA: three.js no disponible', e);
    fail3D('No se pudo cargar el motor 3D (three.js desde cdn.jsdelivr.net). Revisa la conexión y recarga; el plano y los datos siguen disponibles sin conexión.');
    return;
  }
  const stage = $('#stage');
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: (window.devicePixelRatio || 1) < 2, powerPreference: 'high-performance', alpha: false });
  } catch (e) { fail3D('No se pudo iniciar WebGL en este dispositivo. El plano y los datos siguen disponibles.'); return; }
  W3.renderer = renderer;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.setClearColor(0x0b0908, 1);
  W3.maxDpr = Math.min(2, window.devicePixelRatio || 1);
  W3.dpr = W3.maxDpr;
  renderer.setPixelRatio(W3.dpr);
  stage.append(renderer.domElement);
  renderer.domElement.setAttribute('aria-hidden', 'true');
  renderer.domElement.addEventListener('webglcontextlost', e => { e.preventDefault(); $('#loader').hidden = false; $('#loader').style.opacity = 1; $('#loader-msg').textContent = 'Se perdió el contexto gráfico; recuperando…'; });
  renderer.domElement.addEventListener('webglcontextrestored', () => { $('#loader').hidden = true; });

  try {
    await loaderStep(0.15, 'Tallando texturas…');
    try { await Promise.race([document.fonts ? document.fonts.load('800 60px "Big Shoulders Display"') : null, sleep(1500)]); } catch (e) { /* fonts optional */ }
    makeTextures(renderer);
    makeMaterials();
    await loaderStep(0.35, 'Levantando muros…');
    const scene = new THREE.Scene(); W3.scene = scene;
    scene.background = new THREE.Color(0x0b0908);
    scene.environment = makeEnvironment(renderer);
    W3.root = new THREE.Group(); scene.add(W3.root);
    W3.ceiling = new THREE.Group(); scene.add(W3.ceiling);
    const B = new Batch(), CB = new Batch(), SB = new Batch();
    buildArchitecture(B, CB);
    buildPartition(B);
    await loaderStep(0.5, 'Montando la cocina…');
    buildEquipment(B, CB, SB);
    buildFurniture(B, SB);
    await loaderStep(0.65, 'Colgando lámparas…');
    buildDecor(B, CB);
    buildCeiling(CB);
    buildLogs();
    B.flush(W3.root); CB.flush(W3.ceiling); SB.flush(W3.root, { renderOrder: 1 });
    buildFlames(scene);
    buildGlowPoints(scene);
    buildLights(scene);
    buildAerialLayers(scene);
    await loaderStep(0.8, 'Encendiendo el fuego…');
    const cam = new THREE.PerspectiveCamera(65, 1, 0.05, 90); W3.camera = cam;
    const controls = new OrbitControls(cam, renderer.domElement);
    controls.enabled = false; controls.enableDamping = true; controls.dampingFactor = 0.08; controls.maxPolarAngle = Math.PI * 0.47; controls.minDistance = 3; controls.maxDistance = 45; controls.screenSpacePanning = true;
    W3.controls = controls;
    initWalkInput(stage);
    initMinimap();
    renderStops();
    // initial view: entrance, looking at the show kitchen
    const s0 = MODEL.stops[0];
    if (s0) { const v = lookAtPlan(s0.pos[0], s0.pos[1], s0.look[0], s0.look[1], s0.lookH); setView(s0.pos[0], s0.pos[1], v.yaw, v.pitch); markStop(0); }
    else { const p = MODEL.snap(MODEL.entrance[0], MODEL.entrance[1]) || MODEL.entrance; setView(p[0], p[1], Math.PI, -0.03); }
    resize3D();
    if (window.ResizeObserver) new ResizeObserver(() => resize3D()).observe(stage); else window.addEventListener('resize', resize3D);
    // warm up (compile) before revealing
    renderer.compile(scene, cam);
    applyWalkCamera(cam); renderer.render(scene, cam);
    await loaderStep(1, 'Listo');
    const ld = $('#loader'); ld.style.opacity = 0; setTimeout(() => { ld.hidden = true; }, REDUCED ? 0 : 700);
    if (s0) showCaption(0);
    showHint();
    W3.ready = true;
    W3.clock = performance.now();
    requestAnimationFrame(loop);
    emit('ready3d');
  } catch (e) {
    console.error('LAVA: error construyendo la escena', e);
    fail3D('Ocurrió un problema al construir la escena 3D con estos datos. El plano y los datos siguen disponibles.');
  }
}

function resize3D() {
  const r = W3.renderer, st = $('#stage'); if (!r || !st.clientWidth) return;
  const w = st.clientWidth, h = st.clientHeight;
  r.setSize(w, h, false);
  W3.camera.aspect = w / Math.max(1, h);
  if (W3.aerial) W3.camera.updateProjectionMatrix(); else setFov();
  updatePointScale();
}
function updatePointScale() {
  if (!W3.glowMat || !W3.camera) return;
  const h = W3.renderer.domElement.height;
  W3.glowMat.uniforms.uScale.value = h / (2 * Math.tan(W3.camera.fov * Math.PI / 360));
}

/* ---------- flames (animated sprites) + glow points (one draw call) ---------- */
function buildFlames(scene) {
  W3.flameSprites = [];
  for (const f of W3.flames) {
    const m = new THREE.SpriteMaterial({ map: TEX.flame, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, color: new THREE.Color(1.5, 1.2, 1.0) });
    const s = new THREE.Sprite(m); s.center.set(0.5, 0.06); s.position.copy(V3(f.x, f.y, f.z)); s.scale.set(f.w, f.h, 1); s.renderOrder = 6;
    scene.add(s); W3.flameSprites.push({ s, f });
  }
}
function buildGlowPoints(scene) {
  const P = W3.glowPts; if (!P.length) return;
  const pos = new Float32Array(P.length * 3), col = new Float32Array(P.length * 3), size = new Float32Array(P.length);
  P.forEach((p, i) => { const v = V3(p.x, p.y, p.z); pos.set([v.x, v.y, v.z], i * 3); col.set([p.color.r, p.color.g, p.color.b], i * 3); size[i] = p.size; });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('color', new THREE.BufferAttribute(col, 3)); g.setAttribute('size', new THREE.BufferAttribute(size, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { map: { value: TEX.glow }, uScale: { value: 500 }, uFlick: { value: 1 } },
    vertexShader: 'attribute float size; attribute vec3 color; varying vec3 vC; uniform float uScale; uniform float uFlick; void main(){ vC = color * uFlick; vec4 mv = modelViewMatrix * vec4(position,1.0); gl_PointSize = min(size * uScale / max(0.05, -mv.z), 900.0); gl_Position = projectionMatrix * mv; }',
    fragmentShader: 'uniform sampler2D map; varying vec3 vC; void main(){ float a = texture2D(map, gl_PointCoord).a; gl_FragColor = vec4(vC * a * 1.6, 1.0); }',
    blending: THREE.AdditiveBlending, depthWrite: false, transparent: true,
  });
  const pts = new THREE.Points(g, mat); pts.renderOrder = 7; pts.frustumCulled = false;
  scene.add(pts); W3.glowPoints = pts; W3.glowMat = mat;
}

/* ---------- loop ---------- */
const PERF = { frames: 0, acc: 0, lastCheck: 0 };
function loop(now) {
  requestAnimationFrame(loop);
  if (APP.view !== 'recorrido' || document.hidden || !W3.ready) { W3.clock = now; return; }
  const dt = clamp((now - W3.clock) / 1000, 0, 0.1); W3.clock = now;
  const t = now / 1000;
  const cam = W3.camera;
  if (W3.aerial) {
    if (W3.fly) {
      const f = W3.fly; f.t += dt; const u = easeInOut(clamp(f.t / f.dur, 0, 1));
      cam.position.lerpVectors(f.from, f.to, u); const look = f.lookFrom.clone().lerp(f.lookTo, u); cam.lookAt(look);
      if (u >= 1) { W3.fly = null; W3.controls.update(); }
    } else W3.controls.update();
    W3.aer.you.position.copy(V3(WALK.x, WALK.y, 0));
  } else {
    if (TOUR.motion) updateTour(dt); else updateWalk(dt);
    applyWalkCamera(cam);
  }
  // fire flicker
  const fl = 0.82 + 0.12 * Math.sin(t * 7.3) + 0.08 * Math.sin(t * 13.1 + 1.3) + 0.06 * Math.sin(t * 23.7);
  if (W3.fireLight) W3.fireLight.intensity = W3.lights.find(l => l.l === W3.fireLight).base * fl;
  if (W3.smokerLight) W3.smokerLight.intensity = 1.6 * (0.8 + 0.2 * Math.sin(t * 3.1));
  MAT.ember.color.setRGB(2.0 * fl + 0.2, 1.5 * fl, 1.2 * fl);
  if (TEX.ember) { TEX.ember.offset.x = Math.sin(t * 0.21) * 0.03; TEX.ember.offset.y = t * 0.004; }
  for (const { s, f } of W3.flameSprites) {
    const p = f.ph, k = f.small ? 0.35 : 1;
    const hh = f.h * (0.8 + 0.22 * Math.sin(t * 9 + p) + 0.12 * Math.sin(t * 17.3 + p * 2.1));
    s.scale.set(f.w * (0.88 + 0.1 * Math.sin(t * 6.1 + p)), hh, 1);
    s.position.x = f.x + Math.sin(t * 3.3 + p) * 0.012 * k;
    s.material.opacity = 0.75 + 0.25 * Math.sin(t * 11 + p * 1.3);
  }
  if (W3.glowMat) W3.glowMat.uniforms.uFlick.value = 0.94 + 0.06 * Math.sin(t * 5.3);
  // doors: open when camera is close (swing away from the viewer)
  const cx = W3.aerial ? -999 : WALK.x, cy = W3.aerial ? -999 : WALK.y;
  for (const d of W3.doors) {
    const dist = Math.hypot(cx - d.center[0], cy - d.center[1]);
    const target = d.max && dist < 1.5 ? 1 : 0;
    if (target && d.open < 0.02) d.side = d.alongY ? Math.sign(d.center[0] - cx) || 1 : Math.sign(d.center[1] - cy) || 1;
    d.open += (target - d.open) * Math.min(1, dt * 5);
    const s = d.side || 1;
    d.pivot.rotation.y = (d.alongY ? d.dir * s : -d.dir * s) * d.max * smooth(clamp(d.open, 0, 1));
  }
  W3.renderer.render(W3.scene, cam);
  drawMinimap(now);
  updateWhere(now);
  // adaptive resolution
  PERF.frames++; PERF.acc += dt;
  if (now - PERF.lastCheck > 2500) {
    const fps = PERF.frames / Math.max(0.001, PERF.acc); PERF.frames = 0; PERF.acc = 0; PERF.lastCheck = now;
    if (fps < 28 && W3.dpr > 0.75) { W3.dpr = Math.max(0.75, W3.dpr - 0.25); W3.renderer.setPixelRatio(W3.dpr); resize3D(); }
    else if (fps > 55 && W3.dpr < W3.maxDpr) { W3.dpr = Math.min(W3.maxDpr, W3.dpr + 0.25); W3.renderer.setPixelRatio(W3.dpr); resize3D(); }
    W3.fps = fps;
  }
}

let WHERE_LAST = 0, WHERE_TXT = '';
function updateWhere(now) {
  if (now - WHERE_LAST < 300) return; WHERE_LAST = now;
  const M = MODEL, x = W3.aerial ? W3.controls.target.x : WALK.x, y = W3.aerial ? W3.controls.target.z : WALK.y;
  const z = M.zones.find(zz => inPoly(x, y, zz.poly));
  let txt, col = '#9b9185';
  if (W3.aerial) { txt = 'Vista aérea · corte a ' + fmt(CUT_H, 2) + ' m'; col = '#ff6a1a'; }
  else if (z) { txt = `Zona ${z.id}${z.name ? ' · ' + z.name : ''}`; col = z.color; }
  else { const r = M.regionAt(x, y); txt = r === 1 ? 'Salón / barra' : r === 2 ? 'Cocina / back of house' : 'Local'; col = r === 1 ? '#6d7a60' : '#b35900'; }
  if (txt === WHERE_TXT) return; WHERE_TXT = txt;
  const w = $('#where'); w.querySelector('span').textContent = txt; w.querySelector('i').style.background = col;
}

function showHint() {
  const h = $('#hint');
  h.textContent = COARSE ? 'Joystick para caminar · arrastra para mirar · toca un equipo para ver medidas' : 'Arrastra para mirar · WASD o flechas para caminar · clic en el piso para ir · clic en un equipo para ver medidas';
  h.hidden = false; h.style.opacity = 1;
  const hide = () => { h.style.opacity = 0; setTimeout(() => { h.hidden = true; }, 700); };
  setTimeout(hide, 6500);
  const once = () => { hide(); window.removeEventListener('pointerdown', once); window.removeEventListener('keydown', once); };
  setTimeout(() => { window.addEventListener('pointerdown', once); window.addEventListener('keydown', once); }, 300);
}
