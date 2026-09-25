/* ===================================================================================
   14 tour: guided stops (layout.tour or generated), smooth path-following camera
   (A* on the walk grid), caption cards, automatic tour.
   =================================================================================== */

const TOUR = { idx: -1, motion: null, auto: false, autoTimer: null };

function renderStops() {
  const box = $('#stops'); box.replaceChildren();
  MODEL.stops.forEach((s, i) => {
    box.append(el('button', { class: 'stop', type: 'button', 'data-i': i, 'aria-current': 'false', title: s.title, onclick: () => { stopAuto(); goStop(i); } },
      el('b', null, String(i + 1).padStart(2, '0')), s.title));
  });
  $('#btn-auto').addEventListener('click', () => (TOUR.auto ? stopAuto() : startAuto()));
  $('#cap-x').addEventListener('click', () => { $('#caption').hidden = true; });
  $('#cap-prev').addEventListener('click', () => { stopAuto(); goStop((TOUR.idx - 1 + MODEL.stops.length) % MODEL.stops.length); });
  $('#cap-next').addEventListener('click', () => { stopAuto(); goStop((TOUR.idx + 1) % MODEL.stops.length); });
}
function markStop(i) {
  TOUR.idx = i;
  $$('#stops .stop').forEach((b, k) => b.setAttribute('aria-current', String(k === i)));
  const b = $(`#stops .stop[data-i="${i}"]`);
  if (b && b.scrollIntoView) { const box = $('#stops'); const L = b.offsetLeft - box.clientWidth / 2 + b.clientWidth / 2; box.scrollTo({ left: L, behavior: REDUCED ? 'auto' : 'smooth' }); }
}
function showCaption(i) {
  const s = MODEL.stops[i]; if (!s) return;
  $('#cap-idx').textContent = `${String(i + 1).padStart(2, '0')} / ${String(MODEL.stops.length).padStart(2, '0')}`;
  $('#cap-title').textContent = s.title;
  $('#cap-text').textContent = s.text || '';
  $('#cap-flags').replaceChildren(...(s.flags || []).map(f => el('span', { class: 'flag' + (f === FLAGS.DIM || f === FLAGS.SITE ? ' tbv' : '') }, f)));
  $('#info').hidden = true;
  $('#caption').hidden = false;
}

function goStop(i, opts = {}) {
  const s = MODEL.stops[i]; if (!s) return;
  if (W3.aerial) toggleAerial(false);
  markStop(i); showCaption(i);
  const v = lookAtPlan(s.pos[0], s.pos[1], s.look[0], s.look[1], s.lookH);
  moveTo(s.pos, v.yaw, v.pitch, opts);
  emit('stop', i);
}

/* animate the walker along a path to (pos, yaw, pitch) */
function moveTo(pos, yaw, pitch, { instant = false, onDone = null } = {}) {
  cancelTourMotion(true);
  if (instant || REDUCED) { setView(pos[0], pos[1], yaw, pitch); onDone && onDone(); return; }
  const start = [WALK.x, WALK.y];
  let path = MODEL.findPath(start, pos) || [start, pos];
  if (path.length < 2) path = [start, pos];
  // arc length table
  const L = [0]; for (let i = 1; i < path.length; i++) L.push(L[i - 1] + Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]));
  const total = L[L.length - 1];
  const speed = total > 14 ? total / 7.5 : 2.0;
  const dur = clamp(total / speed, 1.1, 8.5) + 0.6;
  TOUR.motion = { path, L, total, t: 0, dur, yaw0: WALK.yaw, pitch0: WALK.pitch, yaw1: yaw, pitch1: pitch, onDone };
}
function samplePath(m, s) {
  s = clamp(s, 0, m.total);
  let i = 1; while (i < m.L.length - 1 && m.L[i] < s) i++;
  const a = m.path[i - 1], b = m.path[i], seg = (m.L[i] - m.L[i - 1]) || 1, t = (s - m.L[i - 1]) / seg;
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t)];
}
function updateTour(dt) {
  const m = TOUR.motion; if (!m) return;
  m.t += dt;
  const u = clamp(m.t / m.dur, 0, 1), e = easeInOut(u);
  const s = e * m.total;
  // gentle corner rounding: average of a few samples around s
  let px = 0, py = 0; const k = [-0.35, 0, 0.35];
  for (const o of k) { const p = samplePath(m, s + o * Math.min(1, m.total * 0.1)); px += p[0]; py += p[1]; }
  WALK.x = px / k.length; WALK.y = py / k.length;
  if (u >= 1) { WALK.x = m.path[m.path.length - 1][0]; WALK.y = m.path[m.path.length - 1][1]; }
  // heading: look ahead along the path, blend to final view near the end
  const ahead = samplePath(m, s + 1.4);
  const travelYaw = m.total > 0.3 && Math.hypot(ahead[0] - WALK.x, ahead[1] - WALK.y) > 0.05 ? Math.atan2(ahead[1] - WALK.y, ahead[0] - WALK.x) : m.yaw1;
  const w = smooth(clamp((u - 0.55) / 0.45, 0, 1)), wStart = smooth(clamp(u / 0.2, 0, 1));
  const yawTravel = m.yaw0 + angDiff(m.yaw0, travelYaw) * wStart;
  WALK.yaw = yawTravel + angDiff(yawTravel, m.yaw1) * w;
  WALK.pitch = lerp(lerp(m.pitch0, -0.02, wStart), m.pitch1, w);
  if (u >= 1) { WALK.yaw = m.yaw1; WALK.pitch = m.pitch1; const cb = m.onDone; TOUR.motion = null; cb && cb(); }
}
function cancelTourMotion(internal) {
  if (TOUR.motion && !internal) TOUR.motion = null;
  if (!internal && TOUR.auto) stopAuto();
}
function startAuto() {
  TOUR.auto = true;
  const b = $('#btn-auto'); b.setAttribute('aria-pressed', 'true'); b.innerHTML = '❚❚ <span class="long">Pausar </span>recorrido';
  const step = i => {
    if (!TOUR.auto) return;
    goStop(i, {});
    const wait = () => {
      if (!TOUR.auto) return;
      if (TOUR.motion) { TOUR.autoTimer = setTimeout(wait, 250); return; }
      TOUR.autoTimer = setTimeout(() => { if (TOUR.auto) step((i + 1) % MODEL.stops.length); }, 6500);
    };
    TOUR.autoTimer = setTimeout(wait, 400);
  };
  step(TOUR.idx >= 0 && TOUR.idx < MODEL.stops.length - 1 ? TOUR.idx + 1 : 0);
}
function stopAuto() {
  TOUR.auto = false; clearTimeout(TOUR.autoTimer);
  const b = $('#btn-auto'); if (b) { b.setAttribute('aria-pressed', 'false'); b.innerHTML = '▶ <span class="long">Recorrido </span>automático'; }
}
