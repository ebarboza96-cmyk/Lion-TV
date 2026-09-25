/* ===================================================================================
   10 textures: every texture is procedural (canvas) – no network fetches.
   =================================================================================== */

function mulberry32(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

/* tileable fbm value noise in [0,1] */
function noise2(size, freq, oct, seed) {
  const rnd = mulberry32(seed), out = new Float32Array(size * size);
  let amp = 1, tot = 0;
  for (let o = 0; o < oct; o++) {
    const f = freq << o, lat = new Float32Array(f * f);
    for (let i = 0; i < lat.length; i++) lat[i] = rnd();
    const k = f / size;
    for (let y = 0; y < size; y++) {
      const fy = y * k, y0 = fy | 0, ty = (fy - y0) * (fy - y0) * (3 - 2 * (fy - y0)), y1 = (y0 + 1) % f, r0 = y0 * f, r1 = y1 * f;
      for (let x = 0; x < size; x++) {
        const fx = x * k, x0 = fx | 0, tx = (fx - x0) * (fx - x0) * (3 - 2 * (fx - x0)), x1 = (x0 + 1) % f;
        const a = lat[r0 + x0] + (lat[r0 + x1] - lat[r0 + x0]) * tx, b = lat[r1 + x0] + (lat[r1 + x1] - lat[r1 + x0]) * tx;
        out[y * size + x] += (a + (b - a) * ty) * amp;
      }
    }
    tot += amp; amp *= 0.5;
  }
  for (let i = 0; i < out.length; i++) out[i] /= tot;
  return out;
}
function mkCanvas(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
function hex2rgb(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }

let MAX_ANISO = 4;
function tex(canvas, { meters = null, srgb = true, repeat = true, aniso = true } = {}) {
  const t = new THREE.CanvasTexture(canvas);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; }
  if (meters) { const [mx, my] = Array.isArray(meters) ? meters : [meters, meters]; t.repeat.set(1 / mx, 1 / my); }
  if (aniso) t.anisotropy = MAX_ANISO;
  t.needsUpdate = true;
  return t;
}
/* paint a noise field into a canvas with a colour ramp */
function paintNoise(ctx, size, n, c0, c1, alpha = 1) {
  const img = ctx.getImageData(0, 0, size, size), d = img.data, a = hex2rgb(c0), b = hex2rgb(c1);
  for (let i = 0; i < n.length; i++) {
    const t = n[i], j = i * 4;
    d[j] = d[j] * (1 - alpha) + (a[0] + (b[0] - a[0]) * t) * alpha;
    d[j + 1] = d[j + 1] * (1 - alpha) + (a[1] + (b[1] - a[1]) * t) * alpha;
    d[j + 2] = d[j + 2] * (1 - alpha) + (a[2] + (b[2] - a[2]) * t) * alpha;
    d[j + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
}
function speckle(ctx, w, h, count, rnd, colors, rmax = 1.2) {
  for (let i = 0; i < count; i++) { ctx.fillStyle = colors[(rnd() * colors.length) | 0]; ctx.globalAlpha = 0.25 + rnd() * 0.5; ctx.beginPath(); ctx.arc(rnd() * w, rnd() * h, 0.3 + rnd() * rmax, 0, 7); ctx.fill(); }
  ctx.globalAlpha = 1;
}

const TEX = {};
function makeTextures(renderer) {
  MAX_ANISO = Math.min(8, renderer.capabilities.getMaxAnisotropy ? renderer.capabilities.getMaxAnisotropy() : 4);
  const S = 1024;
  /* polished concrete, large format 1.20 x 0.60 tiles; canvas = 2.4 m */
  {
    const c = mkCanvas(S, S), x = c.getContext('2d'), rnd = mulberry32(11);
    paintNoise(x, S, noise2(S, 4, 5, 3), '#8e867c', '#b3aba0');
    const n2 = noise2(S, 16, 3, 5); paintNoise(x, S, n2, '#958d83', '#aaa296', 0.35);
    // per-tile tone
    for (let ty = 0; ty < 4; ty++) for (let tx = 0; tx < 2; tx++) { x.fillStyle = rnd() > 0.5 ? '#ffffff' : '#3a2f25'; x.globalAlpha = 0.02 + rnd() * 0.045; x.fillRect(tx * S / 2, ty * S / 4, S / 2, S / 4); }
    x.globalAlpha = 1;
    speckle(x, S, S, 5000, rnd, ['#6f675e', '#c9c1b4', '#7d746a']);
    x.fillStyle = '#4c453e'; for (let i = 0; i <= 2; i++) x.fillRect(i * S / 2 - 1.5, 0, 3, S); for (let i = 0; i <= 4; i++) x.fillRect(0, i * S / 4 - 1.5, S, 3);
    x.fillStyle = 'rgba(255,255,255,.12)'; for (let i = 0; i <= 2; i++) x.fillRect(i * S / 2 + 1.5, 0, 1, S); for (let i = 0; i <= 4; i++) x.fillRect(0, i * S / 4 + 1.5, S, 1);
    TEX.concrete = tex(c, { meters: 2.4 });
    const r = mkCanvas(512, 512), rx = r.getContext('2d');
    paintNoise(rx, 512, noise2(512, 6, 4, 9), '#5a5a5a', '#9a9a9a');
    rx.fillStyle = '#f0f0f0'; for (let i = 0; i <= 2; i++) rx.fillRect(i * 256 - 2, 0, 4, 512); for (let i = 0; i <= 4; i++) rx.fillRect(0, i * 128 - 2, 512, 4);
    TEX.concreteRough = tex(r, { meters: 2.4, srgb: false });
  }
  /* kitchen anti-slip tile 0.30 m; canvas = 1.2 m */
  {
    const s = 512, c = mkCanvas(s, s), x = c.getContext('2d'), rnd = mulberry32(21);
    paintNoise(x, s, noise2(s, 8, 3, 22), '#3b3733', '#4d4843');
    for (let ty = 0; ty < 4; ty++) for (let tx = 0; tx < 4; tx++) { x.fillStyle = rnd() > 0.5 ? '#fff' : '#000'; x.globalAlpha = 0.03 + rnd() * 0.04; x.fillRect(tx * 128, ty * 128, 128, 128); }
    x.globalAlpha = 1;
    speckle(x, s, s, 9000, rnd, ['#6a645c', '#2a2724', '#5a544d'], 0.9);
    x.fillStyle = '#6d675f'; for (let i = 0; i <= 4; i++) { x.fillRect(i * 128 - 2, 0, 4, s); x.fillRect(0, i * 128 - 2, s, 4); }
    TEX.tile = tex(c, { meters: 1.2 });
  }
  /* board-formed concrete (walls): boards 0.15 m; canvas = 2.4 m */
  {
    const c = mkCanvas(S, S), x = c.getContext('2d'), rnd = mulberry32(31);
    paintNoise(x, S, noise2(S, 3, 5, 32), '#8a857e', '#aaa59d');
    paintNoise(x, S, noise2(S, 24, 2, 33), '#8d8881', '#a8a39b', 0.25);
    const bh = S / 8;   // 0.30 m boards
    for (let b = 0; b < 8; b++) {
      x.fillStyle = rnd() > 0.5 ? '#ffffff' : '#2a241e'; x.globalAlpha = 0.015 + rnd() * 0.03; x.fillRect(0, b * bh, S, bh);
      x.globalAlpha = 0.035; x.strokeStyle = '#5e574f';
      for (let k = 0; k < 4; k++) { x.lineWidth = 0.6 + rnd(); x.beginPath(); const y = b * bh + rnd() * bh; x.moveTo(0, y); for (let xx = 0; xx <= S; xx += 64) x.lineTo(xx, y + Math.sin(xx * 0.01 + k) * 2 + (rnd() - 0.5) * 2); x.stroke(); }
      x.globalAlpha = 0.22; x.fillStyle = '#6d665d'; x.fillRect(0, b * bh, S, 1.2);
      x.globalAlpha = 0.08; x.fillStyle = '#ffffff'; x.fillRect(0, b * bh + 1.2, S, 1);
    }
    x.globalAlpha = 1;
    x.globalAlpha = 0.5; x.fillStyle = '#5b544c'; for (let yy = bh; yy < S; yy += bh * 2) for (let xx = S / 8; xx < S; xx += S / 4) { x.beginPath(); x.arc(xx, yy, 3.5, 0, 7); x.fill(); } x.globalAlpha = 1;
    speckle(x, S, S, 2500, rnd, ['#6a635a', '#c4bdb2']);
    TEX.boardConcrete = tex(c, { meters: 2.4 });
  }
  /* plain paint / plaster */
  {
    const s = 256, c = mkCanvas(s, s), x = c.getContext('2d');
    paintNoise(x, s, noise2(s, 4, 3, 41), '#c9c5be', '#d8d4cd');
    TEX.paint = tex(c, { meters: 1.5 });
  }
  /* white subway tile 0.15 x 0.075 running bond; canvas = 0.6 m */
  {
    const s = 512, c = mkCanvas(s, s), x = c.getContext('2d'), rnd = mulberry32(51);
    x.fillStyle = '#9b978f'; x.fillRect(0, 0, s, s);
    const tw = s / 4, th = s / 8;
    for (let r = 0; r < 8; r++) for (let k = -1; k < 5; k++) {
      const ox = k * tw + (r % 2 ? tw / 2 : 0);
      const g = x.createLinearGradient(0, r * th, 0, r * th + th); const v = 232 + (rnd() * 14 | 0);
      g.addColorStop(0, `rgb(${v},${v},${v - 4})`); g.addColorStop(1, `rgb(${v - 14},${v - 14},${v - 18})`);
      x.fillStyle = g; x.fillRect(ox + 3, r * th + 3, tw - 6, th - 6);
    }
    TEX.subway = tex(c, { meters: 0.6 });
  }
  /* wood: oak + walnut */
  const wood = (seed, c0, c1, lines, meters) => {
    const s = 512, c = mkCanvas(s, s), x = c.getContext('2d'), rnd = mulberry32(seed);
    x.fillStyle = c0; x.fillRect(0, 0, s, s);
    const n = noise2(s, 2, 3, seed + 1); const img = x.getImageData(0, 0, s, s), d = img.data;
    for (let y = 0; y < s; y++) for (let xx = 0; xx < s; xx++) { const i = y * s + xx, v = Math.sin((y + n[i] * 90) * 0.18 + Math.sin(xx * 0.004) * 3) * 0.5 + 0.5; const k = (0.82 + v * 0.18) * (0.9 + n[i] * 0.2); d[i * 4] *= k; d[i * 4 + 1] *= k; d[i * 4 + 2] *= k; }
    x.putImageData(img, 0, 0);
    x.strokeStyle = c1; for (let k = 0; k < lines; k++) { x.globalAlpha = 0.08 + rnd() * 0.12; x.lineWidth = 0.5 + rnd() * 1.5; const y = rnd() * s; x.beginPath(); x.moveTo(0, y); for (let xx = 0; xx <= s; xx += 32) x.lineTo(xx, y + Math.sin(xx * 0.02 + k) * 3); x.stroke(); }
    x.globalAlpha = 1;
    return tex(c, { meters });
  };
  TEX.oak = wood(61, '#b48656', '#6e4a2a', 70, 1.2);
  TEX.walnut = wood(71, '#5a3c26', '#2a1a10', 60, 1.0);
  /* sage fabric */
  {
    const s = 256, c = mkCanvas(s, s), x = c.getContext('2d');
    paintNoise(x, s, noise2(s, 8, 3, 81), '#5b6750', '#6e7b61');
    x.globalAlpha = 0.09; x.fillStyle = '#000'; for (let i = 0; i < s; i += 3) { x.fillRect(i, 0, 1, s); x.fillRect(0, i + 1, s, 1); }
    x.globalAlpha = 1;
    TEX.fabric = tex(c, { meters: 0.35 });
  }
  /* corten / weathered steel */
  {
    const s = 512, c = mkCanvas(s, s), x = c.getContext('2d'), rnd = mulberry32(91);
    paintNoise(x, s, noise2(s, 4, 5, 92), '#3f2213', '#8a4a22');
    paintNoise(x, s, noise2(s, 16, 3, 93), '#2c170c', '#a0602e', 0.35);
    speckle(x, s, s, 2500, rnd, ['#2a150a', '#b8723a', '#5a2e14'], 1.5);
    TEX.corten = tex(c, { meters: 1.6 });
  }
  /* brushed stainless */
  {
    const s = 512, c = mkCanvas(s, s), x = c.getContext('2d'), rnd = mulberry32(101);
    x.fillStyle = '#b8bcc0'; x.fillRect(0, 0, s, s);
    for (let i = 0; i < 1600; i++) { const v = 150 + (rnd() * 100 | 0); x.strokeStyle = `rgba(${v},${v + 2},${v + 5},${0.05 + rnd() * 0.12})`; x.lineWidth = 0.5 + rnd(); const y = rnd() * s; x.beginPath(); x.moveTo(0, y); x.lineTo(s, y + (rnd() - 0.5) * 2); x.stroke(); }
    TEX.brushed = tex(c, { meters: 0.8 });
  }
  /* black steel */
  {
    const s = 256, c = mkCanvas(s, s), x = c.getContext('2d');
    paintNoise(x, s, noise2(s, 8, 4, 111), '#151413', '#2a2826');
    TEX.blacksteel = tex(c, { meters: 0.8 });
  }
  /* spiral duct (u around, v along) */
  {
    const c = mkCanvas(128, 256), x = c.getContext('2d');
    const g = x.createLinearGradient(0, 0, 128, 0); g.addColorStop(0, '#2a2a2b'); g.addColorStop(0.5, '#3b3b3d'); g.addColorStop(1, '#2a2a2b');
    x.fillStyle = g; x.fillRect(0, 0, 128, 256);
    x.strokeStyle = 'rgba(0,0,0,.55)'; x.lineWidth = 3;
    for (let k = -4; k < 8; k++) { x.beginPath(); x.moveTo(0, k * 40); x.lineTo(128, k * 40 + 40); x.stroke(); }
    x.strokeStyle = 'rgba(255,255,255,.08)'; x.lineWidth = 1.5;
    for (let k = -4; k < 8; k++) { x.beginPath(); x.moveTo(0, k * 40 + 3); x.lineTo(128, k * 40 + 43); x.stroke(); }
    TEX.duct = tex(c, { aniso: false });
    TEX.duct.repeat.set(1, 6);
  }
  /* ember bed */
  {
    const s = 256, c = mkCanvas(s, s), x = c.getContext('2d'), rnd = mulberry32(121);
    const n = noise2(s, 8, 4, 122); const img = x.createImageData(s, s), d = img.data;
    for (let i = 0; i < n.length; i++) { const v = Math.pow(clamp((n[i] - 0.35) * 2.2, 0, 1), 1.6); d[i * 4] = 40 + v * 215; d[i * 4 + 1] = 10 + v * v * 170; d[i * 4 + 2] = 5 + v * v * v * 60; d[i * 4 + 3] = 255; }
    x.putImageData(img, 0, 0);
    for (let i = 0; i < 140; i++) { x.fillStyle = rnd() > 0.5 ? 'rgba(20,10,6,.8)' : 'rgba(60,30,18,.7)'; x.beginPath(); x.ellipse(rnd() * s, rnd() * s, 3 + rnd() * 9, 2 + rnd() * 5, rnd() * 3, 0, 7); x.fill(); }
    TEX.ember = tex(c, { aniso: false });
  }
  /* flame sprite */
  {
    const c = mkCanvas(128, 256), x = c.getContext('2d');
    const g = x.createRadialGradient(64, 190, 4, 64, 170, 120);
    g.addColorStop(0, 'rgba(255,250,220,1)'); g.addColorStop(0.18, 'rgba(255,215,120,.95)'); g.addColorStop(0.45, 'rgba(255,120,30,.75)'); g.addColorStop(0.75, 'rgba(200,50,10,.25)'); g.addColorStop(1, 'rgba(120,20,0,0)');
    x.fillStyle = g; x.beginPath(); x.moveTo(64, 6); x.bezierCurveTo(98, 70, 124, 150, 110, 206); x.bezierCurveTo(100, 244, 28, 244, 18, 206); x.bezierCurveTo(4, 150, 30, 70, 64, 6); x.fill();
    TEX.flame = tex(c, { repeat: false, aniso: false });
  }
  /* soft glow + blob shadow */
  {
    const c = mkCanvas(128, 128), x = c.getContext('2d');
    const g = x.createRadialGradient(64, 64, 0, 64, 64, 64); g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.2, 'rgba(255,255,255,.55)'); g.addColorStop(0.5, 'rgba(255,255,255,.14)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = g; x.fillRect(0, 0, 128, 128);
    TEX.glow = tex(c, { repeat: false, aniso: false });
    const b = mkCanvas(64, 64), y = b.getContext('2d');
    const h = y.createRadialGradient(32, 32, 0, 32, 32, 32); h.addColorStop(0, 'rgba(0,0,0,.75)'); h.addColorStop(0.55, 'rgba(0,0,0,.35)'); h.addColorStop(1, 'rgba(0,0,0,0)');
    y.fillStyle = h; y.fillRect(0, 0, 64, 64);
    TEX.blob = tex(b, { repeat: false, aniso: false, srgb: false });
  }
  /* bark + log end grain */
  {
    const c = mkCanvas(128, 128), x = c.getContext('2d'), rnd = mulberry32(131);
    paintNoise(x, 128, noise2(128, 8, 3, 132), '#2b1c12', '#5b4128');
    x.strokeStyle = 'rgba(15,8,4,.6)'; for (let i = 0; i < 40; i++) { x.lineWidth = 1 + rnd() * 2; const xx = rnd() * 128; x.beginPath(); x.moveTo(xx, 0); x.lineTo(xx + (rnd() - 0.5) * 10, 128); x.stroke(); }
    TEX.bark = tex(c, { aniso: false });
    const e = mkCanvas(128, 128), y = e.getContext('2d');
    y.fillStyle = '#b48a5c'; y.fillRect(0, 0, 128, 128);
    for (let r = 60; r > 2; r -= 5 + rnd() * 3) { y.strokeStyle = `rgba(110,72,38,${0.35 + rnd() * 0.3})`; y.lineWidth = 1 + rnd() * 1.5; y.beginPath(); y.arc(64 + (rnd() - 0.5) * 4, 64 + (rnd() - 0.5) * 4, r, 0, 7); y.stroke(); }
    y.strokeStyle = 'rgba(60,35,15,.6)'; y.lineWidth = 2; for (let i = 0; i < 4; i++) { y.beginPath(); y.moveTo(64, 64); const a = rnd() * 7; y.lineTo(64 + Math.cos(a) * 60, 64 + Math.sin(a) * 60); y.stroke(); }
    y.strokeStyle = '#3a2412'; y.lineWidth = 7; y.beginPath(); y.arc(64, 64, 61, 0, 7); y.stroke();
    TEX.endgrain = tex(e, { repeat: false, aniso: false });
  }
  /* leaves (alpha) */
  {
    const c = mkCanvas(256, 256), x = c.getContext('2d'), rnd = mulberry32(141);
    for (let i = 0; i < 26; i++) {
      const a = -Math.PI / 2 + (rnd() - 0.5) * 2.4, L = 60 + rnd() * 70, bx = 128 + (rnd() - 0.5) * 40, by = 250;
      const tx = bx + Math.cos(a) * L * 1.4, ty = by + Math.sin(a) * L * 1.4;
      const g = rnd(); x.fillStyle = `rgb(${40 + g * 40 | 0},${85 + g * 70 | 0},${35 + g * 30 | 0})`;
      x.beginPath(); x.moveTo(bx, by); x.quadraticCurveTo(bx + Math.cos(a + 0.5) * L, by + Math.sin(a + 0.5) * L, tx, ty); x.quadraticCurveTo(bx + Math.cos(a - 0.5) * L, by + Math.sin(a - 0.5) * L, bx, by); x.fill();
    }
    TEX.leaves = tex(c, { repeat: false, aniso: false });
  }
  /* kraft paper */
  {
    const s = 128, c = mkCanvas(s, s), x = c.getContext('2d');
    paintNoise(x, s, noise2(s, 8, 3, 151), '#9a7248', '#b88c5c');
    x.fillStyle = '#1b1712'; x.font = 'bold 22px sans-serif'; x.textAlign = 'center'; x.fillText('LΛVΛ', 64, 76);
    TEX.kraft = tex(c, { repeat: false, aniso: false });
  }
}

/* ---------- LΛVΛ glyphs (cap height 1, y up) ---------- */
const GLYPHS = {
  L: { w: 0.62, p: [[0, 0], [0.62, 0], [0.62, 0.2], [0.2, 0.2], [0.2, 1], [0, 1]] },
  A: { w: 0.9, p: [[0, 0], [0.21, 0], [0.45, 0.615], [0.69, 0], [0.9, 0], [0.51, 1], [0.39, 1]] },
  V: { w: 0.9, p: [[0.39, 0], [0.51, 0], [0.9, 1], [0.69, 1], [0.45, 0.385], [0.21, 1], [0, 1]] },
};
function wordGlyphs(text, gap = 0.3) {
  const out = []; let x = 0;
  for (const ch of String(text || 'LAVA').toUpperCase()) {
    const key = ch === 'Λ' ? 'A' : ch;
    const g = GLYPHS[key];
    if (!g) { x += 0.5; continue; }
    out.push(g.p.map(([a, b]) => [a + x, b])); x += g.w + gap;
  }
  return { polys: out, width: Math.max(0.01, x - gap) };
}
function drawWord(ctx, text, cx, cy, H, fill) {
  const { polys, width } = wordGlyphs(text);
  ctx.fillStyle = fill;
  for (const p of polys) { ctx.beginPath(); p.forEach(([a, b], i) => { const X = cx + (a - width / 2) * H, Y = cy - (b - 0.5) * H; i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); }); ctx.closePath(); ctx.fill(); }
}

/* ---------- posters ---------- */
function posterTexture(kind) {
  const W = 512, H = 700, c = mkCanvas(W, H), x = c.getContext('2d');
  x.fillStyle = '#12100e'; x.fillRect(0, 0, W, H);
  const n = noise2(128, 4, 3, 7 + kind.length); x.globalAlpha = 0.25;
  for (let i = 0; i < 128; i++) for (let j = 0; j < 128; j++) { const v = n[j * 128 + i] * 30 | 0; x.fillStyle = `rgb(${v},${v},${v})`; x.fillRect(i * 4, j * 5.5, 4, 6); }
  x.globalAlpha = 1;
  const cream = '#e9dcc0';
  x.strokeStyle = cream; x.lineWidth = 2; x.globalAlpha = 0.55; x.strokeRect(22, 22, W - 44, H - 44); x.globalAlpha = 1;
  const disp = '"Big Shoulders Display","Oswald","Arial Narrow",sans-serif';
  const k = kind.toLowerCase();
  if (k === 'vaca' || k === 'cow' || k === 'cerdo' || k === 'pig') {
    const pig = k === 'cerdo' || k === 'pig';
    x.save(); x.translate(56, pig ? 250 : 230); x.scale(400, 400);
    x.strokeStyle = cream; x.lineWidth = 3 / 400; x.lineJoin = 'round'; x.lineCap = 'round';
    const P = pig
      ? [[0.1, 0.42], [0.04, 0.4], [0.03, 0.48], [0.1, 0.5], [0.14, 0.6], [0.2, 0.64], [0.21, 0.82], [0.27, 0.82], [0.28, 0.68], [0.62, 0.68], [0.64, 0.82], [0.7, 0.82], [0.72, 0.64], [0.84, 0.56], [0.9, 0.42], [0.95, 0.38], [0.93, 0.33], [0.88, 0.36], [0.82, 0.26], [0.6, 0.18], [0.35, 0.18], [0.2, 0.24], [0.17, 0.16], [0.12, 0.26], [0.1, 0.42]]
      : [[0.28, 0.24], [0.52, 0.22], [0.82, 0.22], [0.88, 0.27], [0.9, 0.62], [0.87, 0.28], [0.86, 0.55], [0.85, 0.9], [0.79, 0.9], [0.76, 0.62], [0.42, 0.64], [0.38, 0.9], [0.32, 0.9], [0.3, 0.6], [0.24, 0.56], [0.2, 0.46], [0.12, 0.52], [0.05, 0.5], [0.04, 0.42], [0.09, 0.3], [0.13, 0.25], [0.1, 0.18], [0.16, 0.23], [0.22, 0.21], [0.28, 0.24]];
    x.beginPath(); P.forEach(([a, b], i) => (i ? x.lineTo(a, b) : x.moveTo(a, b))); x.stroke();
    x.setLineDash([0.012, 0.01]); x.lineWidth = 1.6 / 400;
    const cuts = pig ? [[0.3, 0.19, 0.3, 0.67], [0.48, 0.18, 0.48, 0.67], [0.66, 0.2, 0.66, 0.66], [0.3, 0.42, 0.66, 0.42]] : [[0.36, 0.23, 0.36, 0.62], [0.5, 0.22, 0.5, 0.63], [0.63, 0.22, 0.63, 0.63], [0.75, 0.22, 0.75, 0.62], [0.36, 0.44, 0.75, 0.44]];
    for (const [a, b, c2, d] of cuts) { x.beginPath(); x.moveTo(a, b); x.lineTo(c2, d); x.stroke(); }
    x.restore();
    x.fillStyle = cream; x.textAlign = 'center';
    x.font = `800 52px ${disp}`; x.fillText(pig ? 'CERDO' : 'RES', W / 2, 120);
    x.font = `500 17px ${disp}`; x.globalAlpha = 0.8;
    x.fillText(pig ? 'PAPADA · LOMO · COSTILLA · PANCETA · PIERNA' : 'ENTRAÑA · VACÍO · PICAÑA · TOMAHAWK · ASADO', W / 2, 580);
    x.globalAlpha = 1; x.font = `700 22px ${disp}`; x.fillText('LΛVΛ', W / 2, 640);
  } else {
    const lines = kind.replace(/\|/g, ' ').split(/\s+/).filter(Boolean).slice(0, 5);
    x.fillStyle = cream; x.textAlign = 'center'; x.textBaseline = 'middle';
    const fs = Math.min(150, 560 / Math.max(1, lines.length));
    x.font = `800 ${fs}px ${disp}`;
    lines.forEach((l, i) => { x.save(); const m = x.measureText(l.toUpperCase()); const sx = Math.min(1, (W - 110) / Math.max(1, m.width)); x.translate(W / 2, H / 2 - (lines.length - 1) * fs * 0.49 + i * fs * 0.98); x.scale(sx, 1); x.fillText(l.toUpperCase(), 0, 0); x.restore(); });
  }
  return tex(c, { repeat: false });
}

/* ---------- glowing panel behind slats (with backlit word) ---------- */
function slatGlowTexture(lenM, hM, text, textAt) {
  const W = 2048, H = Math.round(clamp(W * hM / Math.max(lenM, 0.5), 96, 512));
  const c = mkCanvas(W, H), x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, '#ffcf8a'); g.addColorStop(0.06, '#e98a36'); g.addColorStop(0.45, '#a24e17'); g.addColorStop(1, '#5a2a0c');
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  const n = noise2(128, 4, 3, 5);
  x.globalAlpha = 0.18; for (let i = 0; i < 128; i++) { x.fillStyle = n[i * 7 % n.length] > 0.5 ? '#ffb060' : '#401a06'; x.fillRect(i * W / 128, 0, W / 128 + 1, H); }
  x.globalAlpha = 1;
  if (text) {
    const Hl = H * 0.52, cx = W * clamp(textAt, 0.1, 0.9), cy = H * 0.5;
    const pxPerM = W / lenM, Wl = wordGlyphs(text).width * Hl;
    if (Wl < W * 0.8) {
      x.save(); x.shadowColor = 'rgba(255,190,110,1)'; x.shadowBlur = Hl * 0.25; drawWord(x, text, cx, cy, Hl, '#fff1d6'); x.restore();
      drawWord(x, text, cx, cy, Hl, '#fffaf0');
    }
    void pxPerM;
  }
  return tex(c, { repeat: false });
}

function signHaloTexture(text) {
  const { width } = wordGlyphs(text);
  const H = 128, W = Math.round(H * (width + 1.4)), c = mkCanvas(W, H * 2.4), x = c.getContext('2d');
  // shadow-only drawing (shape drawn far off-canvas, its blurred shadow lands on the canvas) – works in every browser
  const OFF = 10000;
  x.shadowOffsetX = OFF;
  for (const [blur, col, s] of [[40, 'rgba(255,110,30,.95)', 1.12], [16, 'rgba(255,170,80,1)', 1.0], [16, 'rgba(255,190,110,.9)', 1.0]]) {
    x.shadowBlur = blur; x.shadowColor = col;
    drawWord(x, text, W / 2 - OFF, c.height / 2, H * s, '#000');
  }
  x.shadowBlur = 0; x.shadowOffsetX = 0;
  return { tex: tex(c, { repeat: false }), aspect: c.width / c.height, wordW: width };
}

function screenTexture(kind) {
  const c = mkCanvas(256, 160), x = c.getContext('2d');
  x.fillStyle = '#0d1a22'; x.fillRect(0, 0, 256, 160);
  if (kind === 'pos') {
    x.fillStyle = '#ff6a1a'; x.fillRect(0, 0, 256, 24);
    x.fillStyle = '#e8f4ff'; x.font = 'bold 14px sans-serif'; x.fillText('LΛVΛ · CAJA', 10, 17);
    for (let i = 0; i < 6; i++) { x.fillStyle = i % 2 ? '#1d3342' : '#18303d'; x.fillRect(10 + (i % 3) * 80, 34 + (i / 3 | 0) * 58, 72, 50); }
  } else { x.fillStyle = '#7ef0a0'; x.font = 'bold 60px monospace'; x.fillText(kind || '3°C', 30, 105); }
  return tex(c, { repeat: false, aniso: false });
}
