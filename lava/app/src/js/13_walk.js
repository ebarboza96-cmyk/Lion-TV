/* ===================================================================================
   13 walk: first-person camera, keyboard / drag / wheel / joystick, 2D collision
   (circle vs rects + premises edges, slides along obstacles).
   =================================================================================== */

const EYE = 1.6, RADIUS = 0.24;
const WALK = { x: 0, y: 0, yaw: Math.PI, pitch: -0.03, keys: new Set(), joy: { x: 0, y: 0, active: false }, drag: null, speed: 1.55,
  lastInput: 0, moving: false };

function collide(x, y, r = RADIUS) {
  const M = MODEL;
  for (let it = 0; it < 4; it++) {
    let moved = false;
    for (const c of M.colliders) {
      if (x < c[0] - r || x > c[2] + r || y < c[1] - r || y > c[3] + r) continue;
      const qx = clamp(x, c[0], c[2]), qy = clamp(y, c[1], c[3]);
      const dx = x - qx, dy = y - qy, d = Math.hypot(dx, dy);
      if (d >= r) continue;
      if (d > 1e-7) { x = qx + dx / d * r; y = qy + dy / d * r; }
      else { const L = x - c[0], R = c[2] - x, T = y - c[1], Bm = c[3] - y, m = Math.min(L, R, T, Bm); if (m === L) x = c[0] - r; else if (m === R) x = c[2] + r; else if (m === T) y = c[1] - r; else y = c[3] + r; }
      moved = true;
    }
    for (const s of M.segs) {
      const ex = s[2] - s[0], ey = s[3] - s[1], L2 = ex * ex + ey * ey || 1;
      const t = clamp(((x - s[0]) * ex + (y - s[1]) * ey) / L2, 0, 1), qx = s[0] + ex * t, qy = s[1] + ey * t;
      const dx = x - qx, dy = y - qy, d = Math.hypot(dx, dy);
      if (d < r && d > 1e-7) { x = qx + dx / d * r; y = qy + dy / d * r; moved = true; }
    }
    if (!moved) break;
  }
  return [x, y];
}
function tryMove(dx, dy) {
  const M = MODEL;
  const steps = Math.max(1, Math.ceil(Math.hypot(dx, dy) / 0.08));
  let x = WALK.x, y = WALK.y;
  for (let i = 0; i < steps; i++) {
    const [nx, ny] = collide(x + dx / steps, y + dy / steps);
    if (!M.isInside(nx, ny)) break;
    x = nx; y = ny;
  }
  WALK.x = x; WALK.y = y;
}
function setView(x, y, yaw, pitch) { WALK.x = x; WALK.y = y; if (yaw != null) WALK.yaw = yaw; if (pitch != null) WALK.pitch = pitch; }
function lookAtPlan(px, py, lx, ly, lh = 1.35) {
  const yaw = Math.atan2(ly - py, lx - px), d = Math.hypot(lx - px, ly - py) || 1;
  return { yaw, pitch: clamp(Math.atan2(lh - EYE, d), -0.9, 0.7) };
}
function applyWalkCamera(cam) {
  const cp = Math.cos(WALK.pitch);
  cam.position.set(WALK.x, EYE, WALK.y);
  cam.lookAt(WALK.x + Math.cos(WALK.yaw) * cp, EYE + Math.sin(WALK.pitch), WALK.y + Math.sin(WALK.yaw) * cp);
}
function userInput() { WALK.lastInput = performance.now(); if (typeof cancelTourMotion === 'function') cancelTourMotion(); }

function updateWalk(dt) {
  let f = 0, s = 0, turn = 0;
  const k = WALK.keys;
  if (k.has('KeyW') || k.has('ArrowUp')) f += 1;
  if (k.has('KeyS') || k.has('ArrowDown')) f -= 1;
  if (k.has('KeyA')) s -= 1;
  if (k.has('KeyD')) s += 1;
  if (k.has('ArrowLeft') || k.has('KeyQ')) turn -= 1;
  if (k.has('ArrowRight') || k.has('KeyE')) turn += 1;
  if (WALK.joy.active) { f += -WALK.joy.y; s += WALK.joy.x; }
  const run = k.has('ShiftLeft') || k.has('ShiftRight') ? 1.9 : 1;
  WALK.yaw += turn * 1.7 * dt;
  const mag = Math.hypot(f, s);
  WALK.moving = mag > 0.01;
  if (!WALK.moving) return;
  if (mag > 1) { f /= mag; s /= mag; }
  const sp = WALK.speed * run * dt, cy = Math.cos(WALK.yaw), sy = Math.sin(WALK.yaw);
  // right vector in plan = (-sin, cos) rotated: forward (cos, sin); right = (-sin, cos)
  tryMove((cy * f - sy * s) * sp, (sy * f + cy * s) * sp);
}

function initWalkInput(stage) {
  const keyTarget = window;
  const inRecorrido = () => APP.view === 'recorrido' && !W3.aerial;
  keyTarget.addEventListener('keydown', e => {
    if (APP.view !== 'recorrido') return;
    const tag = (e.target && e.target.tagName) || '';
    if (/INPUT|TEXTAREA|SELECT/.test(tag)) return;
    if (e.code === 'KeyV' && !e.metaKey && !e.ctrlKey) { toggleAerial(); return; }
    if (!inRecorrido()) return;
    const movement = ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyQ', 'KeyE', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ShiftLeft', 'ShiftRight'];
    if (!movement.includes(e.code)) return;
    if (e.code.startsWith('Arrow') && e.target !== stage && e.target !== document.body && !stage.contains(e.target) && e.target.closest && e.target.closest('.rail,.card,.hud-top,.layers,.help')) return;
    WALK.keys.add(e.code); if (!e.code.startsWith('Shift')) userInput(); e.preventDefault();
  });
  keyTarget.addEventListener('keyup', e => WALK.keys.delete(e.code));
  window.addEventListener('blur', () => WALK.keys.clear());
  // drag to look / tap to pick or walk
  stage.addEventListener('pointerdown', e => {
    if (W3.aerial || e.button > 0) return;
    stage.setPointerCapture && stage.setPointerCapture(e.pointerId);
    WALK.drag = { id: e.pointerId, x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, t: performance.now(), moved: 0 };
    stage.classList.add('dragging');
  });
  stage.addEventListener('pointermove', e => {
    const d = WALK.drag;
    if (!d || d.id !== e.pointerId) { if (!W3.aerial && e.pointerType === 'mouse') hoverPick(e); return; }
    const dx = e.clientX - d.x, dy = e.clientY - d.y; d.x = e.clientX; d.y = e.clientY;
    d.moved += Math.abs(dx) + Math.abs(dy);
    if (d.moved > 6) {
      const k = (e.pointerType === 'touch' ? 0.0055 : 0.0042) * (W3.camera ? W3.camera.fov / 65 : 1);
      WALK.yaw -= dx * k; WALK.pitch = clamp(WALK.pitch + dy * k, -1.2, 1.1); userInput();
    }
  });
  const end = e => {
    const d = WALK.drag; if (!d || d.id !== e.pointerId) return;
    WALK.drag = null; stage.classList.remove('dragging');
    if (e.type === 'pointerup' && d.moved < 8 && performance.now() - d.t < 600) tapAt(e);
  };
  stage.addEventListener('pointerup', end); stage.addEventListener('pointercancel', end);
  stage.addEventListener('wheel', e => {
    if (W3.aerial) return; e.preventDefault(); userInput();
    const st = clamp(-e.deltaY * 0.004, -0.5, 0.5);
    tryMove(Math.cos(WALK.yaw) * st, Math.sin(WALK.yaw) * st);
  }, { passive: false });
  // joystick (touch devices)
  const joy = $('#joy'), knob = $('#joy-knob');
  if (COARSE) joy.hidden = false;
  let jid = null, jc = null;
  joy.addEventListener('pointerdown', e => { jid = e.pointerId; joy.setPointerCapture && joy.setPointerCapture(jid); const r = joy.getBoundingClientRect(); jc = [r.left + r.width / 2, r.top + r.height / 2, r.width / 2]; WALK.joy.active = true; moveJoy(e); userInput(); e.stopPropagation(); });
  const moveJoy = e => { if (e.pointerId !== jid) return; let dx = (e.clientX - jc[0]) / jc[2], dy = (e.clientY - jc[1]) / jc[2]; const m = Math.hypot(dx, dy); if (m > 1) { dx /= m; dy /= m; } WALK.joy.x = dx; WALK.joy.y = dy; knob.style.transform = `translate(${dx * jc[2] * 0.62}px,${dy * jc[2] * 0.62}px)`; userInput(); };
  joy.addEventListener('pointermove', moveJoy);
  const jend = e => { if (e.pointerId !== jid) return; jid = null; WALK.joy = { x: 0, y: 0, active: false }; knob.style.transform = ''; };
  joy.addEventListener('pointerup', jend); joy.addEventListener('pointercancel', jend);
}
