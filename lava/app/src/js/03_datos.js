/* ===================================================================================
   03 datos: metrics, dimensions to verify, risks, engineering flags.
   Uses data/report.json when bundled (keys: metrics{}, verify[], risks[], flags[]),
   otherwise computes basic metrics from the layout in the browser.
   =================================================================================== */

const METRIC_ES = {
  seats: ['Asientos', ''], premises_area_m2: ['Área del local', 'm²'], new_partition_x: ['División nueva (X)', 'm'],
  partition_shift_m: ['Corrimiento de la división', 'm'], hot_line_length: ['Línea caliente', 'm'], hood_length: ['Campana', 'm'],
  hood_min_end_overhang: ['Voladizo mínimo de campana', 'm'], hot_line_uncovered_m2: ['Línea sin campana', 'm²'],
  seats_with_parrilla_view: ['Asientos con vista a la parrilla', ''], seats_with_parrilla_view_pct: ['Asientos con vista a la parrilla', '%'],
  parrilla_visible_from_entrance: ['Parrilla visible desde la entrada', ''], entrance_to_parrilla_m: ['Entrada → parrilla', 'm'],
  parrilla_to_glass_m: ['Parrilla → vidrio', 'm'], routes: ['Rutas', ''], connections: ['Conexiones', ''], zones: ['Zonas', ''],
  optional_present: ['Equipos opcionales presentes', ''], dirty_clean_conflicts: ['Conflictos flujo sucio / limpio', ''],
  dining_area_m2: ['Área de salón', 'm²'], kitchen_area_m2: ['Área de cocina', 'm²'], min_aisle_m: ['Pasillo mínimo', 'm'],
};
const COL_ES = { id: 'Id', kind: 'Tipo', label: 'Descripción', min_width: 'Ancho mín. (m)', at: 'En', required: 'Requerido (m)', length: 'Longitud (m)',
  ok: 'Estado', from: 'Desde', to: 'Hasta', bottleneck: 'Cuello (m)', name: 'Nombre', area_m2: 'Área (m²)', area: 'Área (m²)' };
const humanKey = k => (METRIC_ES[k] ? METRIC_ES[k][0] : COL_ES[k] || String(k).replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase()));

function fmtVal(v, k) {
  if (v == null) return '—';
  if (typeof v === 'boolean') return v ? 'Sí' : 'No';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(Math.abs(v) >= 100 ? 1 : 2);
  if (Array.isArray(v)) return v.every(x => typeof x !== 'object') ? v.join(', ') : `${v.length} elementos`;
  if (typeof v === 'object') return Object.entries(v).map(([a, b]) => `${a}: ${fmtVal(b)}`).join(' · ');
  return String(v);
}
function itemText(it) {
  if (it == null) return ['', ''];
  if (typeof it !== 'object') return [String(it), ''];
  const t = it.text || it.title || it.desc || it.description || it.what || it.item || it.label || it.name || it.id || '';
  const rest = [];
  for (const k of ['where', 'id', 'value', 'dim', 'severity', 'owner', 'action', 'mitigation', 'note']) if (it[k] != null && it[k] !== t) rest.push(`${humanKey(k)}: ${fmtVal(it[k])}`);
  return [String(t || fmtVal(it)), rest.join(' · ')];
}
function tableFrom(rows) {
  const keys = [...new Set(rows.flatMap(r => Object.keys(r)))];
  return el('div', { class: 'tbl-wrap' }, el('table', { class: 'tbl' },
    el('thead', null, el('tr', null, keys.map(k => el('th', { scope: 'col' }, humanKey(k))))),
    el('tbody', null, rows.map(r => el('tr', null, keys.map(k => {
      const v = r[k];
      if (k === 'ok') return el('td', { class: v ? 'ok' : 'bad' }, v ? 'OK' : 'No cumple');
      return el('td', { class: typeof v === 'number' ? 'n' : null }, fmtVal(v, k));
    }))))));
}
const kpi = (v, unit, label, extra) => el('div', { class: 'kpi' }, el('div', { class: 'v' }, v, unit ? el('small', null, unit) : null), el('div', { class: 'l' }, label), extra || null);
const flagEl = f => el('span', { class: 'flag' + (f === FLAGS.DIM || f === FLAGS.SITE ? ' tbv' : '') }, f);

function initDatos() {
  const root = $('#datos'); if (root.dataset.ready) return; root.dataset.ready = '1';
  const M = MODEL, mt = M.metrics;
  root.append(el('h2', null, 'Datos del test-fit'));
  const meta = [str(M.meta.name), str(M.meta.strategy), M.meta.version != null ? 'v' + M.meta.version : ''].filter(Boolean).join(' · ');
  root.append(el('p', { class: 'lead' }, meta || 'Propuesta LAVA sobre el local ex-Marna’s, Terrazas Lindora.'));
  if (!REPORT) root.append(el('p', { class: 'note' }, 'Informe de validación no incluido (data/report.json): las métricas de abajo se calculan en el navegador a partir de layout.json y existing.json. Ejecuta tools/validate.py para el informe completo.'));

  /* ---- metrics ---- */
  root.append(el('h3', null, 'Resumen'));
  const k = el('div', { class: 'kpis' }); root.append(k);
  const oldPart = arr(EX.walls).find(w => w && w.id === 'IP-KB');
  const shift = M.partition && oldPart && nrect(oldPart.rect) ? nrect(oldPart.rect)[0] - M.partition.rect[0] : null;
  const guest = mt.routes.filter(r => r.w != null).sort((a, b) => a.w - b.w)[0];
  const computed = [
    [String(mt.seats), '', 'Asientos'],
    [fmt(mt.premArea, 1), 'm²', 'Área del local'],
    [fmt(mt.fohArea, 1), 'm²', 'Área de salón y barra (aprox.)'],
    [fmt(mt.premArea - mt.fohArea, 1), 'm²', 'Cocina + back of house (aprox.)'],
    shift != null ? [fmt(shift, 2), 'm', 'Corrimiento de la división cocina/salón'] : null,
    guest ? [fmt(guest.w, 2), 'm', `Ancho libre mínimo en rutas (${ROUTE_ES[guest.kind] || guest.kind})`] : null,
    [String(mt.tables), '', 'Mesas'],
    [String(mt.equipment), '', 'Equipos en layout'],
    [fmt(mt.ceilH, 2), 'm', 'Altura de cielo asumida', el('div', null, flagEl(FLAGS.SITE))],
  ].filter(Boolean);
  const rep = REPORT && REPORT.metrics && typeof REPORT.metrics === 'object' ? REPORT.metrics : null;
  const complex = [];
  if (rep) {
    for (const [key, v] of Object.entries(rep)) {
      if (v == null) continue;
      if (typeof v === 'object') { complex.push([key, v]); continue; }
      const [label, unit] = METRIC_ES[key] || [humanKey(key), ''];
      k.append(kpi(fmtVal(v, key), unit, label));
    }
    if (!Object.keys(rep).some(x => /seat/.test(x))) k.prepend(kpi(String(mt.seats), '', 'Asientos'));
  } else computed.forEach(c => k.append(kpi(...c)));

  /* ---- zones + routes ---- */
  const cols = el('div', { class: 'cols' }); root.append(cols);
  const zc = el('div'); cols.append(zc);
  zc.append(el('h3', null, 'Zonas'));
  const zrows = (rep && Array.isArray(rep.zones) ? rep.zones.map(z => ({ id: z.id, name: z.name, area: num(z.area_m2, num(z.area, null)) })) : mt.zones.map(z => ({ id: z.id, name: z.name, area: z.area })));
  if (zrows.length) {
    zc.append(el('div', { class: 'tbl-wrap' }, el('table', { class: 'tbl' },
      el('thead', null, el('tr', null, el('th', { scope: 'col' }, 'Zona'), el('th', { scope: 'col' }, 'Nombre'), el('th', { scope: 'col' }, 'Área (m²)'))),
      el('tbody', null, zrows.map(z => { const zz = M.zones.find(q => q.id === z.id); return el('tr', null, el('td', null, el('span', { class: 'sw', style: `display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px;background:${zz ? zz.color : '#777'}` }), z.id), el('td', null, z.name || '—'), el('td', { class: 'n' }, fmt(z.area, 2))); })))));
  } else zc.append(el('p', { class: 'lead' }, 'El layout no define zonas.'));
  const rc = el('div'); cols.append(rc);
  rc.append(el('h3', null, 'Rutas y anchos libres'));
  if (rep && Array.isArray(rep.routes)) rc.append(tableFrom(rep.routes));
  else if (mt.routes.length) {
    rc.append(el('div', { class: 'tbl-wrap' }, el('table', { class: 'tbl' },
      el('thead', null, el('tr', null, ['Ruta', 'Long. (m)', 'Ancho mín. (m)', 'Requerido', 'Estado'].map(t => el('th', { scope: 'col' }, t)))),
      el('tbody', null, mt.routes.map(r => {
        const ok = r.req == null || r.w == null ? null : r.w + 0.005 >= r.req;
        return el('tr', null, el('td', null, el('span', { style: `display:inline-block;width:14px;height:3px;margin:0 8px 3px 0;background:${ROUTE_COLOR[r.kind] || '#777'}` }), r.label || r.id, el('div', { style: 'color:var(--muted);font-size:11.5px' }, ROUTE_ES[r.kind] || r.kind)),
          el('td', { class: 'n' }, fmt(r.len, 1)), el('td', { class: 'n' }, fmt(r.w, 2)), el('td', { class: 'n' }, r.req != null ? fmt(r.req, 2) : '—'),
          el('td', { class: ok == null ? '' : ok ? 'ok' : 'bad' }, ok == null ? '—' : ok ? 'OK' : 'No cumple'));
      })))));
    rc.append(el('p', { class: 'lead', style: 'font-size:12px;margin-top:6px' }, 'Ancho medido en el navegador sobre una grilla de 5 cm (muros, equipos, mesas y bancas).'));
  } else rc.append(el('p', { class: 'lead' }, 'El layout no define rutas.'));
  for (const [key, v] of complex) {
    if (key === 'zones' || key === 'routes') continue;
    root.append(el('h3', null, humanKey(key)));
    if (Array.isArray(v) && v.length && v.every(x => x && typeof x === 'object')) root.append(tableFrom(v));
    else if (Array.isArray(v)) root.append(v.length ? el('ul', { class: 'list' }, v.map(x => el('li', null, fmtVal(x)))) : el('p', { class: 'lead' }, 'Ninguno.'));
    else root.append(tableFrom([v]));
  }

  /* ---- verify / risks / flags ---- */
  const lists = el('div', { class: 'cols' }); root.append(lists);
  const vcol = el('div'); lists.append(vcol);
  vcol.append(el('h3', null, 'Dimensiones a verificar en sitio'));
  let verify = REPORT && Array.isArray(REPORT.verify) ? REPORT.verify.map(itemText) : null;
  if (!verify) {
    verify = [];
    for (const e of mt.tbv) verify.push([`${e.label} (${e.id}) · ${fmt(rw(e.rect), 2)} × ${fmt(rh(e.rect), 2)} × ${fmt(e.h, 2)} m`, FLAGS.DIM]);
    verify.push([`Altura libre de cielo: se asume ${fmt(M.ceilH, 2)} m`, FLAGS.SITE]);
    const seen = new Set();
    for (const src of [...arr(EX.shafts), ...arr(EX.walls), ...arr(EX.glazing), EX.existing_hood, ...arr(EX.keepouts), EX.terrace_existing]) {
      if (!src || typeof src.note !== 'string' || !/VERIFY/i.test(src.note) || seen.has(src.note)) continue;
      seen.add(src.note); verify.push([`${src.id ? src.id + ': ' : ''}${src.note.replace(/\s*-?\s*VERIFY( ON SITE)?/gi, '').trim()}`, FLAGS.SITE]);
    }
  }
  vcol.append(el('ul', { class: 'list' }, verify.map(([t, s]) => el('li', null, el('div', { class: 't' }, t), s ? el('div', { class: 's' }, (s === FLAGS.DIM || s === FLAGS.SITE) ? flagEl(s) : s) : null))));
  const rcol = el('div'); lists.append(rcol);
  rcol.append(el('h3', null, 'Riesgos'));
  let risks = REPORT && Array.isArray(REPORT.risks) ? REPORT.risks.map(itemText) : null;
  if (!risks) {
    risks = [];
    if (M.one('smoker')) risks.push(['Smoker de combustible sólido dentro del local: ubicación, chimenea y código de incendio por validar con bomberos y la administración.', '']);
    if (M.one('parrilla') || M.one('hood')) risks.push(['Extracción de la parrilla a leña/carbón: ruta del ducto sobre el cielo, aire de reposición y supresión de incendio no están diseñados.', '']);
    const dirty = M.routes.filter(r => r.kind === 'dirty'), clean = M.routes.filter(r => r.kind === 'clean');
    if (dirty.some(d => clean.some(c => segsCross(d.pts, c.pts)))) risks.push(['La ruta sucia cruza la ruta limpia.', '']);
    for (const r of mt.routes) if (r.req != null && r.w != null && r.w + 0.005 < r.req) risks.push([`Ruta ${r.label || r.id}: ancho libre ${fmt(r.w, 2)} m < ${fmt(r.req, 2)} m requerido.`, '']);
    risks.push([`Altura de cielo asumida (${fmt(M.ceilH, 2)} m): condiciona campana, ductos y smoker.`, '']);
  }
  rcol.append(risks.length ? el('ul', { class: 'list' }, risks.map(([t, s]) => el('li', null, el('div', { class: 't' }, t), s ? el('div', { class: 's' }, s) : null))) : el('p', { class: 'lead' }, 'Sin riesgos registrados.'));
  root.append(el('h3', null, 'Banderas de ingeniería'));
  let flags = REPORT && Array.isArray(REPORT.flags) ? REPORT.flags.map(f => itemText(f)[0]) : null;
  if (!flags) { flags = [FLAGS.EXTRACTION]; if (M.one('smoker')) flags.push(FLAGS.SMOKER); if (mt.tbv.length) flags.push(FLAGS.DIM); flags.push(FLAGS.SITE); }
  root.append(el('div', null, flags.map(flagEl)));
  if (REPORT && (Array.isArray(REPORT.issues) || Array.isArray(REPORT.warnings))) {
    root.append(el('h3', null, 'Validador'));
    const li = [...arr(REPORT.issues).map(t => ['Issue', t]), ...arr(REPORT.warnings).map(t => ['Aviso', t])];
    root.append(li.length ? el('ul', { class: 'list' }, li.map(([a, t]) => el('li', null, el('div', { class: 't' }, String(t)), el('div', { class: 's' }, a)))) : el('p', { class: 'lead' }, 'Sin issues ni avisos.'));
  }
  const notes = arr(LAY.notes).filter(n => typeof n === 'string');
  if (notes.length) { root.append(el('h3', null, 'Notas del layout')); root.append(el('ul', { class: 'list' }, notes.map(n => el('li', null, n)))); }
  if (M.warnings.length) root.append(el('p', { class: 'note' }, M.warnings.join(' ')));
  root.append(el('p', { class: 'lead', style: 'font-size:12px;margin-top:26px' },
    `Generado ${BUILD.date ? 'el ' + BUILD.date : ''} desde data/existing.json${BUILD.layout ? ' + ' + BUILD.layout : ' + data/layout.json'}${REPORT ? ' + data/report.json' : ''}. Coordenadas en metros: X desde el eje A hacia la fachada, Y desde el eje 1 hacia el ala de servicio.`));
}
