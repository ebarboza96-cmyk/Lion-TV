/* ===================================================================================
   20 boot: tabs + hash routing (#recorrido #plano #datos), help, meta, start.
   =================================================================================== */

const APP = { view: 'recorrido' };
const VIEWS = ['recorrido', 'plano', 'datos'];

function showView(v, focus) {
  if (!VIEWS.includes(v)) v = 'recorrido';
  APP.view = v;
  for (const k of VIEWS) {
    const tab = $('#tab-' + k), panel = $('#view-' + k), on = k === v;
    tab.setAttribute('aria-selected', String(on)); tab.tabIndex = on ? 0 : -1; panel.hidden = !on;
  }
  if (focus) $('#tab-' + v).focus();
  if (v === 'plano') { initPlan(); requestAnimationFrame(() => PLAN && PLAN.pz.fitted && PLAN.pz.fit()); }
  if (v === 'datos') initDatos();
  if (v === 'recorrido') { start3D(); if (W3.renderer) requestAnimationFrame(resize3D); }
  WALK.keys && WALK.keys.clear();
}
function routeFromHash() { const h = (location.hash || '').replace('#', '').toLowerCase(); return VIEWS.includes(h) ? h : null; }

function boot() {
  const meta = $('#meta');
  const name = str(MODEL.meta.name);
  meta.replaceChildren(el('b', null, 'Test-fit'), name ? ' · ' + name : '', ' · ', el('span', { class: 'mono' }, `${MODEL.seats} asientos`));
  meta.title = [str(MODEL.meta.name), str(MODEL.meta.strategy)].filter(Boolean).join(' — ');
  // tabs
  $$('.tab').forEach(t => t.addEventListener('click', () => { const v = t.dataset.view; try { if (location.hash !== '#' + v) location.hash = v; else showView(v); } catch (e) { showView(v); } showView(v); }));
  $('.tabs').addEventListener('keydown', e => {
    const i = VIEWS.indexOf(APP.view);
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); const n = VIEWS[(i + (e.key === 'ArrowRight' ? 1 : VIEWS.length - 1)) % VIEWS.length]; try { location.hash = n; } catch (err) { /* sandbox */ } showView(n, true); }
  });
  window.addEventListener('hashchange', () => { const v = routeFromHash(); if (v && v !== APP.view) showView(v); });
  // help
  const help = $('#help'), hb = $('#btn-help');
  $('#help-list').replaceChildren(...(COARSE ? [
    ['Joystick (abajo a la izquierda)', 'caminar'], ['Arrastrar con un dedo', 'mirar alrededor'], ['Tocar el piso', 'caminar hasta ahí'], ['Tocar un equipo', 'nombre y medidas'], ['Paradas (abajo)', 'recorrido guiado'],
  ] : [
    ['W A S D / ↑ ↓', 'caminar (Shift = rápido)'], ['← → o Q E', 'girar'], ['Arrastrar', 'mirar alrededor'], ['Rueda', 'avanzar / retroceder'], ['Clic en el piso', 'caminar hasta ahí'], ['Clic en un equipo', 'nombre y medidas'], ['V', 'vista aérea'],
  ]).map(([a, b]) => el('li', null, el('kbd', null, a), ' ', b)));
  hb.addEventListener('click', () => { help.hidden = !help.hidden; hb.setAttribute('aria-expanded', String(!help.hidden)); });
  $('#btn-aerial').addEventListener('click', () => toggleAerial());
  $('#tg-zones').addEventListener('change', e => { if (W3.aer) W3.aer.zones.visible = W3.aerial && e.target.checked; });
  $('#tg-routes').addEventListener('change', e => { if (W3.aer) W3.aer.routes.visible = W3.aerial && e.target.checked; });
  $('#info-x').addEventListener('click', () => { $('#info').hidden = true; if (typeof setHighlight === 'function' && W3.renderer) setHighlight(null); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { $('#info').hidden = true; help.hidden = true; hb.setAttribute('aria-expanded', 'false'); } });
  showView(routeFromHash() || 'recorrido');
}

// read-only debug handle (handy for QA from the console)
try { Object.defineProperty(window, '__LAVA', { value: { MODEL, W3, WALK, TOUR, APP, goStop, toggleAerial, updateTour }, configurable: true }); } catch (e) { /* ignore */ }

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
