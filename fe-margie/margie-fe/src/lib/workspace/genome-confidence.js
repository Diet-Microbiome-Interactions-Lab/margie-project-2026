// @ts-nocheck
/**
 * A film for Home's opening, about what MARGIE does (about 9 s): a stretch of genome with its genes
 * on both strands; evidence from the annotation databases lands on each gene, which takes the colour
 * of its confidence tier as the evidence gathers; operons join their genes and lift a weak member;
 * the stretch closes into a circular genome map, coloured by confidence as on Results, with the MARGIE
 * wordmark in the middle. The tier colours are the site's (--mg-tier-*), so palettes apply.
 * The same code runs in animations/genome-confidence.html.
 */

const TAU = Math.PI * 2;

// ---------- Random numbers: a fixed seed, so each run is the same film
function mulberry32(a) {
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(30102026);
const rr = (a, b) => a + (b - a) * rand();

// ---------- Easing
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const prog = (t, t0, d) => clamp01((t - t0) / d);
const smooth = (x) => x * x * (3 - 2 * x);
const easeOut = (x) => 1 - Math.pow(1 - x, 3);
const easeIO = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

// ---------- Timeline, in seconds at 1x
const T = { line: 0, genes: 0.25, chips: 0.6, ev: 1.15, chipsOut: 3.95, operon: 4.35, lift: 5.05, bend: 6.0, word: 7.6, end: 8.8 };
const DUR = { line: 0.8, gene: 0.35, chips: 0.45, fly: 0.55, chipsOut: 0.45, operon: 0.7, lift: 0.7, bend: 1.8, word: 1.0 };
export const STAGES = [
  { t: 0, name: 'Genes', note: 'A stretch of genome: its protein-coding genes on both strands.' },
  { t: T.ev, name: 'Evidence', note: 'Each annotation database reports what it finds for each gene.' },
  { t: T.ev + 1.2, name: 'Confidence', note: 'A gene takes the colour of its confidence tier as the evidence gathers: blue highest, then green, yellow, orange and red.' },
  { t: T.operon, name: 'Operons', note: 'Genes in one operon are joined, and a conserved operon lifts its weaker members.' },
  { t: T.bend, name: 'Genome map', note: 'The genome closes into its map, coloured by confidence, as on Results.' }
];

// ---------- The genome, in units of the box's height: the ring's middle radius, a gene's
// thickness and its gap from the backbone
const RR = 0.36, TH = 0.056, GAP = 0.013;
const L = TAU * RR;
const SOURCES = ['COG', 'KEGG', 'eggNOG', 'UniProt', 'Pfam', 'TIGRFAM', 'PGAP'];
/** Tiers by the number of sources with evidence (0 highest ... 4 low; 5 no tier). */
const tierOf = (h) => (h >= 7 ? 0 : h >= 5 ? 1 : h === 4 ? 2 : h >= 2 ? 3 : h >= 1 ? 4 : 5);

// Genes in runs on one strand; a run of two or more is an operon.
const genes = [];
const operons = [];
{
  const runs = [];
  let left = 30;
  while (left > 0) {
    const n = Math.min(left, [1, 1, 2, 2, 3, 3, 4][Math.floor(rand() * 7)]);
    runs.push(n);
    left -= n;
  }
  const lens = [];
  for (const n of runs) for (let i = 0; i < n; i++) lens.push(rr(0.7, 1.35));
  const gapU = 0.14, total = lens.reduce((a, b) => a + b, 0) + gapU * lens.length;
  const unit = L / total;
  let s = -L / 2 + (gapU * unit) / 2, g = 0;
  const hitsPool = [7, 7, 7, 6, 6, 5, 5, 5, 4, 4, 3, 3, 2, 2, 1, 6, 7, 5, 3, 0, 7, 6, 7, 5, 4, 6, 7, 6, 2, 5];
  for (let i = hitsPool.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [hitsPool[i], hitsPool[j]] = [hitsPool[j], hitsPool[i]]; }
  runs.forEach((n, r) => {
    const strand = rand() < 0.55 ? 1 : -1;
    const op = n >= 2 ? operons.length : -1;
    if (op >= 0) operons.push({ genes: [], strand });
    for (let i = 0; i < n; i++, g++) {
      const len = lens[g] * unit;
      const gene = { s0: s, s1: s + len, strand, op, hits: hitsPool[g % hitsPool.length], lift: 0, tLift: Infinity, dots: [] };
      genes.push(gene);
      if (op >= 0) operons[op].genes.push(gene);
      s += len + gapU * unit;
    }
  });
  // A conserved operon lifts its weaker members: an operon with a well-supported gene lifts one
  // member in the fair or medium tier by one tier.
  let lifted = 0;
  for (const o of operons) {
    if (lifted >= 3) break;
    if (!o.genes.some((x) => x.hits >= 5)) continue;
    const weak = o.genes.find((x) => x.hits >= 2 && x.hits <= 4);
    if (weak) { weak.lift = 1; weak.tLift = T.lift + lifted * 0.28; lifted++; }
  }
  // Evidence: one dot from each source with a hit, launched gene by gene along the stretch.
  genes.forEach((gene, i) => {
    const from = SOURCES.map((_, k) => k);
    for (let k = from.length - 1; k > 0; k--) { const j = Math.floor(rand() * (k + 1)); [from[k], from[j]] = [from[j], from[k]]; }
    for (let j = 0; j < gene.hits; j++) {
      const t0 = T.ev + (i / genes.length) * 2.15 + j * 0.085 + rr(0, 0.05);
      gene.dots.push({ src: from[j], t0, t1: t0 + DUR.fly, bow: rr(0.25, 0.5) * (rand() < 0.5 ? -1 : 1) });
    }
  });
}

// ---------- Canvas, theme, view
/** @type {HTMLCanvasElement} */
let canvas;
/** @type {CanvasRenderingContext2D} */
let ctx;
/** @type {HTMLElement} */
let stageEl;
let VW = 0, VH = 0, dpr = 1;
const PAL = {};
const LOOK = {
  light: { fg: '#1f2937', muted: '#6b7280', line: '#cbd2dc', none: '#C3CFCB', glow: 'rgba(31,119,255,0.10)' },
  dark: { fg: '#e6eaf2', muted: '#94a3b8', line: '#3a465c', none: '#4A5654', glow: 'rgba(91,141,255,0.14)' }
};
const TIERS = ['#1F77FF', '#00B84D', '#FFCC00', '#FF8C00', '#EE2233'];
let isDark = () => false;
function toHex(c) {
  const m = c.match(/rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)(?:[,\s/]+([\d.]+%?))?/);
  if (!m || (m[4] !== undefined && parseFloat(m[4]) === 0)) return '';
  return '#' + [m[1], m[2], m[3]].map((v) => (+v).toString(16).padStart(2, '0')).join('');
}
function readTheme() {
  const dark = isDark();
  const base = LOOK[dark ? 'dark' : 'light'];
  const cs = getComputedStyle(canvas);
  const site = (name, fallback) => {
    const v = cs.getPropertyValue(name).trim();
    return (v && (v.startsWith('#') ? v : toHex(v))) || fallback;
  };
  PAL.fg = site('--mg-text', base.fg);
  PAL.muted = site('--mg-text-2', base.muted);
  PAL.line = base.line;
  PAL.glow = base.glow;
  PAL.tier = TIERS.map((c, i) => site(`--mg-tier-${i}`, c)).concat([site('--mg-tier-5', base.none)]);
}
function resize() {
  const r = stageEl.getBoundingClientRect();
  dpr = Math.min(2, window.devicePixelRatio || 1);
  VW = Math.max(1, r.width);
  VH = Math.max(1, r.height);
  canvas.width = Math.round(VW * dpr);
  canvas.height = Math.round(VH * dpr);
}

function hexRgb(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function mix(a, b, f) { const A = hexRgb(a), B = hexRgb(b); return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * f)).join(',')})`; }
function withAlpha(h, a) { const [r, g, b] = hexRgb(h); return `rgba(${r},${g},${b},${a})`; }

// ---------- The bend: the straight stretch closes into a ring of radius RR
let K = 0, SC = 1, CX = 0, CY = 0, SHIFT = 0;
/** Screen position of a point s along the stretch, y toward the ring's centre (both in box heights). */
function place(s, y, out) {
  let x, yy;
  if (K < 1e-4) { x = s; yy = y; }
  else {
    const k = K / RR, a = k * s, sn = Math.sin(a), cs = Math.cos(a);
    x = sn / k - y * sn;
    yy = (1 - cs) / k + y * cs - SHIFT;
  }
  out[0] = CX + x * VH * SC;
  out[1] = CY + yy * VH * SC;
  return out;
}
function setView(t) {
  K = easeIO(prog(t, T.bend, DUR.bend));
  // The bent stretch is an arc of angle K x 360 degrees: its extent, in box heights, is kept centred
  // and inside the box as it closes.
  const band = GAP + TH + 0.04;
  let w = L, h = 0;
  if (K > 1e-4) {
    const rho = RR / K, half = Math.min(Math.PI, (K * TAU) / 2);
    w = 2 * rho * Math.sin(Math.min(half, Math.PI / 2));
    h = rho * (1 - Math.cos(half));
  }
  SHIFT = h / 2;
  SC = Math.min(1, (0.92 * VW) / ((w + 2 * band) * VH), 0.96 / (h + 2 * band));
  CX = VW / 2;
  // The stretch sits a little low, under the sources; the ring is centred.
  CY = VH / 2 + (1 - K) * VH * 0.06;
}

// ---------- Drawing
const P = [0, 0], Q = [0, 0];
function chipAt(k, out) {
  const span = Math.min(VW * 0.88, L * VH * SC * 1.02), x0 = VW / 2 - span / 2;
  out[0] = x0 + (span * (k + 0.5)) / SOURCES.length;
  out[1] = VH * 0.11;
  return out;
}
function drawChips(t) {
  const a = Math.min(easeOut(prog(t, T.chips, DUR.chips)), 1 - smooth(prog(t, T.chipsOut, DUR.chipsOut)));
  if (a <= 0) return;
  const span = Math.min(VW * 0.88, L * VH * SC * 1.02);
  let size = Math.max(8, Math.min(12.5, VH * 0.042));
  ctx.font = `600 ${size}px Lato, Helvetica, Arial, sans-serif`;
  const widest = Math.max(...SOURCES.map((s) => ctx.measureText(s).width));
  if (widest * SOURCES.length * 1.15 > span) { size *= span / (widest * SOURCES.length * 1.15); ctx.font = `600 ${size}px Lato, Helvetica, Arial, sans-serif`; }
  ctx.save();
  ctx.globalAlpha = a;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  SOURCES.forEach((s, k) => {
    chipAt(k, P);
    ctx.fillStyle = PAL.muted;
    ctx.fillText(s, P[0], P[1] - VH * 0.006);
    ctx.fillStyle = withAlpha(PAL.fg, 0.55);
    ctx.beginPath(); ctx.arc(P[0], P[1] + size * 0.95, Math.max(1.6, VH * 0.009), 0, TAU); ctx.fill();
  });
  ctx.restore();
}
function drawBackbone(t) {
  const grow = easeOut(prog(t, T.line, DUR.line));
  if (grow <= 0) return;
  ctx.save();
  ctx.strokeStyle = PAL.line;
  ctx.lineWidth = Math.max(1, VH * 0.006 * SC);
  ctx.lineCap = 'round';
  ctx.beginPath();
  const half = (L / 2) * grow, n = 160;
  for (let i = 0; i <= n; i++) {
    place(-half + (2 * half * i) / n, 0, P);
    if (i) ctx.lineTo(P[0], P[1]); else ctx.moveTo(P[0], P[1]);
  }
  if (K > 0.999) ctx.closePath();
  ctx.stroke();
  ctx.restore();
}
/** The gene's colour now: its tier after the evidence that has landed, and its lift. */
function geneColour(g, t) {
  let c = 0, last = -Infinity;
  for (const d of g.dots) if (t >= d.t1) { c++; last = Math.max(last, d.t1); }
  let tier = tierOf(c), before = tierOf(Math.max(0, c - 1)), f = c ? smooth(prog(t, last, 0.22)) : 1;
  if (t >= g.tLift) {
    const lifted = Math.max(0, tier - g.lift);
    const lf = smooth(prog(t, g.tLift, 0.35));
    return mix(PAL.tier[tier], PAL.tier[lifted], lf);
  }
  return c ? mix(PAL.tier[before], PAL.tier[tier], f) : PAL.tier[5];
}
function genePath(g, grow) {
  const y0 = g.strand > 0 ? -(GAP + TH) : GAP, y1 = y0 + TH, ym = (y0 + y1) / 2;
  const len = (g.s1 - g.s0) * grow, mid = (g.s0 + g.s1) / 2;
  const s0 = mid - len / 2, s1 = mid + len / 2;
  const tip = Math.min(len * 0.3, TH * 0.6);
  const n = 8;
  ctx.beginPath();
  if (g.strand > 0) {
    for (let i = 0; i <= n; i++) { place(s0 + ((s1 - tip - s0) * i) / n, y0, P); i ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]); }
    place(s1, ym, P); ctx.lineTo(P[0], P[1]);
    for (let i = n; i >= 0; i--) { place(s0 + ((s1 - tip - s0) * i) / n, y1, P); ctx.lineTo(P[0], P[1]); }
  } else {
    for (let i = 0; i <= n; i++) { place(s0 + tip + ((s1 - s0 - tip) * i) / n, y0, P); i ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]); }
    for (let i = n; i >= 0; i--) { place(s0 + tip + ((s1 - s0 - tip) * i) / n, y1, P); ctx.lineTo(P[0], P[1]); }
    place(s0, ym, P); ctx.lineTo(P[0], P[1]);
  }
  ctx.closePath();
}
function drawGenes(t) {
  ctx.save();
  ctx.lineJoin = 'round';
  genes.forEach((g, i) => {
    const grow = easeOut(prog(t, T.genes + i * 0.022, DUR.gene));
    if (grow <= 0) return;
    genePath(g, grow);
    ctx.fillStyle = geneColour(g, t);
    ctx.fill();
    ctx.strokeStyle = withAlpha(PAL.fg, 0.18);
    ctx.lineWidth = 0.8;
    ctx.stroke();
  });
  ctx.restore();
}
function geneCentre(g, out) {
  return place((g.s0 + g.s1) / 2, g.strand > 0 ? -(GAP + TH / 2) : GAP + TH / 2, out);
}
function drawEvidence(t) {
  ctx.save();
  const r = Math.max(1.5, VH * 0.0105);
  for (const g of genes) {
    for (const d of g.dots) {
      if (t < d.t0 || t > d.t1 + 0.2) continue;
      chipAt(d.src, P);
      P[1] += VH * 0.045;
      geneCentre(g, Q);
      const f = easeIO(prog(t, d.t0, DUR.fly));
      const mx = (P[0] + Q[0]) / 2 + (Q[1] - P[1]) * d.bow * 0.35, my = (P[1] + Q[1]) / 2;
      const x = (1 - f) * (1 - f) * P[0] + 2 * (1 - f) * f * mx + f * f * Q[0];
      const y = (1 - f) * (1 - f) * P[1] + 2 * (1 - f) * f * my + f * f * Q[1];
      if (t <= d.t1) {
        ctx.fillStyle = withAlpha(PAL.fg, 0.62);
        ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
      } else {
        // On landing, a small ring in the gene's new colour.
        const k = prog(t, d.t1, 0.2);
        ctx.strokeStyle = withAlpha(PAL.fg, 0.35 * (1 - k));
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(Q[0], Q[1], r * (1.2 + 2.2 * k), 0, TAU); ctx.stroke();
      }
    }
  }
  ctx.restore();
}
function drawOperons(t) {
  const a = Math.min(easeOut(prog(t, T.operon, DUR.operon)), 1 - smooth(prog(t, T.bend, 0.45)));
  if (a <= 0) return;
  ctx.save();
  ctx.strokeStyle = withAlpha(PAL.fg, 0.45 * a);
  ctx.lineWidth = Math.max(1, VH * 0.005);
  ctx.lineCap = 'round';
  operons.forEach((o, i) => {
    const grow = easeOut(prog(t, T.operon + i * 0.07, DUR.operon));
    if (grow <= 0) return;
    const s0 = o.genes[0].s0, s1 = s0 + (o.genes[o.genes.length - 1].s1 - s0) * grow;
    const y = o.strand > 0 ? -(GAP + TH + 0.03) : GAP + TH + 0.03, tick = 0.018 * (o.strand > 0 ? 1 : -1);
    ctx.beginPath();
    place(s0, y + tick, P); ctx.moveTo(P[0], P[1]);
    for (let k = 0; k <= 12; k++) { place(s0 + ((s1 - s0) * k) / 12, y, P); ctx.lineTo(P[0], P[1]); }
    if (grow >= 1) { place(s1, y + tick, P); ctx.lineTo(P[0], P[1]); }
    ctx.stroke();
  });
  // The lift: a pulse round each gene its operon lifts.
  for (const g of genes) {
    if (!(t >= g.tLift && t < g.tLift + DUR.lift)) continue;
    const k = prog(t, g.tLift, DUR.lift);
    geneCentre(g, P);
    ctx.strokeStyle = withAlpha(PAL.tier[Math.max(0, tierOf(g.hits) - g.lift)], 0.7 * (1 - k));
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(P[0], P[1], VH * (0.035 + 0.07 * easeOut(k)), 0, TAU); ctx.stroke();
  }
  ctx.restore();
}
// The logo's wordmark in the middle of the closed map.
const logo = typeof Image === 'undefined' ? null : new Image();
function drawWordmark(t) {
  const a = smooth(prog(t, T.word, DUR.word));
  if (a <= 0) return;
  const inner = (RR - GAP - TH) * VH * SC;
  const clip = inner - VH * 0.012, half = clip / 0.555;
  ctx.save();
  // A soft glow inside the ring.
  const gr = ctx.createRadialGradient(CX, CY, 0, CX, CY, inner);
  gr.addColorStop(0, PAL.glow);
  gr.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.globalAlpha = a;
  ctx.fillStyle = gr;
  ctx.beginPath(); ctx.arc(CX, CY, inner, 0, TAU); ctx.fill();
  if (logo && logo.complete && logo.naturalWidth) {
    ctx.beginPath(); ctx.arc(CX, CY, clip, 0, TAU); ctx.clip();
    const sc = 1 + 0.04 * (1 - a);
    ctx.drawImage(logo, CX - half * sc, CY - half * sc, 2 * half * sc, 2 * half * sc);
  } else {
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = '#FF8A1F'; ctx.font = `900 ${Math.round(half * 0.11)}px Lato, sans-serif`;
    ctx.fillText('B S P', CX, CY - half * 0.13);
    ctx.fillStyle = '#1F6BFF'; ctx.font = `900 ${Math.round(half * 0.22)}px Lato, sans-serif`;
    ctx.fillText('MARGIE', CX, CY + half * 0.08);
  }
  ctx.restore();
}
function render(t) {
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  // Transparent: the film sits on the page's own background.
  ctx.clearRect(0, 0, VW, VH);
  setView(t);
  drawChips(t);
  drawBackbone(t);
  drawOperons(t);
  drawGenes(t);
  drawEvidence(t);
  drawWordmark(t);
}

/**
 * Plays the film on `el` (its parent sets the size), at rate() times its own speed, read on each
 * frame (the site's motion and speed settings; 0 shows the last frame). Returns replay(), seek(t),
 * retheme() (after a theme change) and destroy().
 * @param {HTMLCanvasElement} el
 * @param {{ logoSrc: string, dark?: () => boolean, rate?: () => number, onEnd?: () => void }} options
 * @returns {{ replay(): void, seek(t: number): void, retheme(): void, destroy(): void, end: number }}
 */
export function mount(el, { logoSrc, dark = () => false, rate = () => 1, onEnd = () => {} }) {
  canvas = el;
  ctx = el.getContext('2d');
  stageEl = el.parentElement;
  isDark = dark;
  if (logoSrc) logo.src = logoSrc;
  readTheme();
  resize();
  let time = 0, raf = 0, last = 0;
  const frame = () => render(time);
  function tick(now) {
    const r = rate();
    time = r > 0 ? Math.min(T.end, time + Math.min(0.05, (now - last) / 1000) * r) : T.end;
    last = now;
    frame();
    if (time < T.end) raf = requestAnimationFrame(tick);
    else onEnd();
  }
  function play() {
    cancelAnimationFrame(raf);
    last = performance.now();
    raf = requestAnimationFrame(tick);
  }
  const ro = new ResizeObserver(() => { resize(); frame(); });
  ro.observe(stageEl);
  logo.addEventListener('load', frame);
  play();
  return {
    end: T.end,
    replay() { time = 0; play(); },
    seek(t) { cancelAnimationFrame(raf); time = Math.max(0, Math.min(T.end, t)); frame(); },
    retheme() { readTheme(); frame(); },
    destroy() { cancelAnimationFrame(raf); ro.disconnect(); logo.removeEventListener('load', frame); }
  };
}
