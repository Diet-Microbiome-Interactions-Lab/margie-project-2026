// @ts-nocheck
/**
 * The DNA film on Home: atoms form bases, sugars and phosphates, which join into nucleotides, two
 * strands, a double helix and a circular genome that closes into the MARGIE logo (about 15 s).
 * Ported from the stand-alone page in the animations folder: its drawing as it was, on a canvas
 * the page passes in, with the page's background and text colours. mount() plays it once and
 * holds the last frame; still shows the last frame at once (reduced motion).
 */
// ---------- Random numbers: a fixed seed, so each run is the same film
function mulberry32(a) {
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(29102026);
const rr = (a, b) => a + (b - a) * rand();
const TAU = Math.PI * 2;

// ---------- Easing
const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);
const prog = (t, t0, d) => clamp01((t - t0) / d);
const smooth = (x) => x * x * (3 - 2 * x);
const inOut = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const outC = (x) => 1 - Math.pow(1 - x, 3);

// ---------- Timeline, in seconds at 1x
const T = { sugar: 1.4, base: 2.1, nuc: 3.6, line: 5.0, pair: 7.2, hb: 7.7, twist: 8.8, fade: 9.4, bend: 10.9, spin: 12.95, word: 13.4, end: 15.4 };
const DUR = { in: 0.8, form: 0.32, nuc: 0.55, line: 0.85, pair: 0.8, twist: 2.0, fade: 0.7, bend: 1.9, spin: 2.2, word: 1.0 };
T.close = T.bend + DUR.bend;
const STAGES = [
  { t: 0, name: 'Elements', note: 'Carbon, hydrogen, nitrogen, oxygen and phosphorus atoms come in.' },
  { t: T.sugar, name: 'Covalent bonds', note: 'Atoms share electrons and bond into deoxyribose sugars and phosphate groups.' },
  { t: 2.4, name: 'Purines and pyrimidines', note: 'Rings close into bases: adenine and guanine are purines | cytosine and thymine are pyrimidines.' },
  { t: T.nuc, name: 'Nucleotides', note: 'Each base bonds to a sugar and each sugar to a phosphate; water leaves as the base joins.' },
  { t: T.line, name: 'Phosphodiester bonds', note: 'Each 3′ oxygen bonds to the next phosphate, and two single strands grow 5′ to 3′.' },
  { t: T.pair, name: 'Hydrogen bonds', note: 'The antiparallel strands pair: A with T by two hydrogen bonds | G with C by three.' },
  { t: T.twist, name: 'Double helix', note: 'The double strand coils, ten base pairs to a turn.' },
  { t: T.bend, name: 'Circular genome', note: 'The helix bends round, its two ends join, and the circular genome closes.' }
];

// ---------- Colours: the logo's strands, and the puzzle's bases
const STRAND = ['#1F6BFF', '#FF8A1F'];
const BASE_COL = { A: '#8CDC28', T: '#14C8F0', G: '#FFC83C', C: '#F2589B' };
const BASE_INK = { A: '#3F7A0A', T: '#06799A', G: '#9A7000', C: '#B0285F' };
const BASE_NAME = { A: 'Adenine', G: 'Guanine', C: 'Cytosine', T: 'Thymine' };
const PAIR = { A: 'T', T: 'A', G: 'C', C: 'G' };
const ELS = ['C', 'H', 'N', 'O', 'P'];
const EL_NAME = { C: 'Carbon', H: 'Hydrogen', N: 'Nitrogen', O: 'Oxygen', P: 'Phosphorus' };
const EL_R = { C: 0.3, H: 0.19, N: 0.3, O: 0.3, P: 0.4 };
const EL_FIXED = { light: { N: '#4256D6', O: '#E5484D', P: '#F29D0C' }, dark: { N: '#7083FF', O: '#FF6B6B', P: '#FFB020' } };

// ---------- 2D geometry, one unit = one bond
const D2R = Math.PI / 180;
const dir = (a) => [Math.cos(a * D2R), Math.sin(a * D2R)];
const add = (p, q, s = 1) => [p[0] + q[0] * s, p[1] + q[1] * s];
const sub = (p, q) => [p[0] - q[0], p[1] - q[1]];
const rotp = (p, a) => { const c = Math.cos(a * D2R), s = Math.sin(a * D2R); return [p[0] * c - p[1] * s, p[0] * s + p[1] * c]; };
const angOf = (v) => Math.atan2(v[1], v[0]) / D2R;
const HL = 0.7;
const R5 = 0.8507;

/** A small molecule builder: named atoms at 2D points, and bonds with their order. */
function mol() {
  const atoms = {}, bonds = [];
  const m = {
    atoms, bonds,
    at(n, p, el = n[0]) { atoms[n] = { el, p }; return m; },
    on(n, from, a, len = 1, order = 1, el = n[0]) { atoms[n] = { el, p: add(atoms[from].p, dir(a), len) }; bonds.push([from, n, order]); return m; },
    bond(a, b, order = 1) { bonds.push([a, b, order]); return m; },
    ring(names, dbl) {
      names.forEach((a, i) => { const b = names[(i + 1) % names.length]; m.bond(a, b, dbl.includes(a + b) || dbl.includes(b + a) ? 2 : 1); });
      return m;
    }
  };
  return m;
}

/** Cytosine or thymine, ring centre at the origin; N3 points at the partner (+y). */
function pyrimidine(t) {
  const m = mol();
  const A = { N1: 210, C2: 150, N3: 90, C4: 30, C5: 330, C6: 270 };
  for (const n in A) m.at(n, dir(A[n]));
  const six = ['N1', 'C2', 'N3', 'C4', 'C5', 'C6'];
  m.ring(six, t === 'C' ? ['N3C4', 'C5C6'] : ['C5C6']);
  m.on('O2', 'C2', 150, 1, 2);
  if (t === 'C') m.on('N4', 'C4', 30).on('H41', 'N4', 90, HL).on('H42', 'N4', -30, HL).on('H5', 'C5', 330, HL);
  else m.on('O4', 'C4', 30, 1, 2).on('H3', 'N3', 90, HL).on('C7', 'C5', 330);
  m.on('H6', 'C6', 270, HL).on('HX', 'N1', 210, HL);
  return { ...m, rings: [six], attach: 'N1', face: 'N3', out: 210, purine: false };
}

/** Adenine or guanine, six-membered ring centre at the origin; N1 points at the partner (+y). */
function purine(t) {
  const m = mol();
  const A = { N1: 90, C2: 150, N3: 210, C4: 270, C5: 330, C6: 30 };
  for (const n in A) m.at(n, dir(A[n]));
  const c4 = m.atoms.C4.p, c5 = m.atoms.C5.p, mid = [(c4[0] + c5[0]) / 2, (c4[1] + c5[1]) / 2];
  const ml = Math.hypot(mid[0], mid[1]);
  const pc = add(mid, [mid[0] / ml, mid[1] / ml], 0.688);
  const a4 = angOf(sub(c4, pc));
  m.at('N9', add(pc, dir(a4 + 72), R5)).at('C8', add(pc, dir(a4 + 144), R5)).at('N7', add(pc, dir(a4 + 216), R5));
  const six = ['N1', 'C2', 'N3', 'C4', 'C5', 'C6'], five = ['C4', 'C5', 'N7', 'C8', 'N9'];
  m.ring(six, t === 'G' ? ['C2N3', 'C4C5'] : ['N1C6', 'C2N3', 'C4C5']);
  m.bond('C5', 'N7').bond('N7', 'C8', 2).bond('C8', 'N9').bond('N9', 'C4');
  if (t === 'G') m.on('O6', 'C6', 30, 1, 2).on('H1', 'N1', 90, HL).on('N2', 'C2', 150).on('H21', 'N2', 90, HL).on('H22', 'N2', 210, HL);
  else m.on('N6', 'C6', 30).on('H61', 'N6', 90, HL).on('H62', 'N6', -30, HL).on('H2', 'C2', 150, HL);
  const out = angOf(sub(m.atoms.N9.p, pc));
  m.on('H8', 'C8', angOf(sub(m.atoms.C8.p, pc)), HL).on('HX', 'N9', out, HL);
  return { ...m, rings: [six, five], attach: 'N9', face: 'N1', out, purine: true };
}

// Turn each base about its sugar carbon so the paired faces sit parallel and in line.
function faceVec(b) { return sub(b.atoms[b.face].p, add(b.atoms[b.attach].p, dir(b.out))); }
const vPy = faceVec(pyrimidine('C')), vPu = faceVec(purine('G'));
const rotFor = (v, f) => Math.acos(f / Math.hypot(v[0], v[1])) / D2R - angOf(v);
let lo = 0.2, hi = Math.min(Math.hypot(...vPy), Math.hypot(...vPu)) - 0.01;
for (let i = 0; i < 60; i++) { const f = (lo + hi) / 2; if (rotFor(vPy, f) + rotFor(vPu, f) > 0) lo = f; else hi = f; }
const ROT_PY = rotFor(vPy, lo), ROT_PU = rotFor(vPu, lo);
/** The glycosidic bond leans 20 degrees nearer the strand's normal, clear of the sugar ring. */
const GLY_BEND = 20;
function placeBase(b, r) {
  for (const n in b.atoms) b.atoms[n].p = rotp(b.atoms[n].p, r);
  const out = b.out + r + GLY_BEND;
  const c1 = add(b.atoms[b.attach].p, dir(out));
  for (const n in b.atoms) b.atoms[n].p = sub(b.atoms[n].p, c1);
  b.gly = out + 180;
  return b;
}
const BASE = { A: placeBase(purine('A'), ROT_PU), G: placeBase(purine('G'), ROT_PU), C: placeBase(pyrimidine('C'), ROT_PY), T: placeBase(pyrimidine('T'), ROT_PY) };

// Deoxyribose, C1' at the origin and its ring away from the base; then the phosphate on C5'.
const pcS = [0, -R5];
const SUG = mol().at("C1'", [0, 0]).at("C2'", add(pcS, dir(18), R5)).at("C3'", add(pcS, dir(-54), R5)).at("C4'", add(pcS, dir(234), R5)).at("O4'", add(pcS, dir(162), R5));
SUG.ring(["C1'", "C2'", "C3'", "C4'", "O4'"], []);
SUG.on("C5'", "C4'", 200).on("O3'", "C3'", angOf([0.6, -0.8]));
const PHO = mol().at("O5'", add(SUG.atoms["C5'"].p, dir(240)));
PHO.on('P', "O5'", 200).on('OP1', 'P', 240, 1, 2).on('OP2', 'P', 300);
const O3p = SUG.atoms["O3'"].p, Pp = PHO.atoms.P.p;
/** Rise per base pair: the O3' of one nucleotide sits one bond from the next phosphate. */
const S = O3p[0] + Math.sqrt(1 - (Pp[1] - O3p[1]) ** 2) - Pp[0];
PHO.at('OP3', [O3p[0] - S, O3p[1]]).bond('P', 'OP3');

// ---------- The genome: 70 base pairs, seven turns of ten
const N = 70, TURN = 10, HB_GAP = 2.0, GFAR = 15;
const A_R = 6.3, W_R = 0.85 * A_R, RUNG_W = 1.75;
const R_END = 7.68 * A_R;
const SIG_F = (TAU * R_END) / (N * S);
const W_C = (BASE.C.atoms.N3.p[1] + BASE.G.atoms.N1.p[1] + HB_GAP) / 2;
const xOf = (i) => (i - (N - 1) / 2) * S;
const seq = Array.from({ length: N }, () => 'ACGT'[Math.floor(rand() * 4)]);

const nucs = [], atoms = [], bonds = [], hbonds = [], rings = [], flashes = [], waters = [], callouts = [];
const bond = (a, b, order, tOn, extra = {}) => bonds.push({ a, b, order, tOn, tOff: Infinity, glow: Infinity, st: -1, ...extra });

for (let st = 0; st < 2; st++) {
  for (let i = 0; i < N; i++) {
    const b = st ? PAIR[seq[i]] : seq[i], tb = BASE[b];
    const cx = -tb.atoms[tb.face].p[0];
    /** Strand 0 above the axis, strand 1 below; bases mirror across it, sugars turn half round (antiparallel). */
    const place = (p, isBase) => (st === 0 ? [cx + p[0], -W_C + p[1]] : isBase ? [cx + p[0], W_C - p[1]] : [cx - p[0], W_C - p[1]]);
    const k = nucs.length;
    const n = { k, st, i, b, idx: {}, parts: [[], [], []] };
    const put = (name, el, p, part) => { n.idx[name] = atoms.length; n.parts[part].push(atoms.length); atoms.push({ k, part, el, name, lx: p[0], ly: p[1], leave: Infinity }); };
    for (const nm in tb.atoms) put(nm, tb.atoms[nm].el, place(tb.atoms[nm].p, true), 0);
    for (const nm in SUG.atoms) put(nm, SUG.atoms[nm].el, place(SUG.atoms[nm].p, false), 1);
    put("O1'", 'O', place(dir(tb.gly), true), 1);
    for (const nm in PHO.atoms) put(nm, PHO.atoms[nm].el, place(PHO.atoms[nm].p, false), 2);
    n.base = tb;
    nucs.push(n);
  }
}
const nucAt = (st, i) => nucs[st * N + i];

// Where each nucleotide floats before the strands form: a loose grid, strand 0 above, strand 1 below.
const COLS = 18, ROWS = 4, cellW = (N * S) / COLS, cellH = 17;
for (let st = 0; st < 2; st++) {
  const cells = [];
  for (let c = 0; c < COLS; c++) for (let r = 0; r < ROWS; r++) cells.push({ c, r, o: rand() });
  cells.sort((p, q) => p.c - q.c || p.o - q.o);
  while (cells.length > N) cells.splice(Math.floor(rand() * cells.length), 1);
  for (let i = 0; i < N; i++) {
    const cell = cells[i], n = nucAt(st, i);
    const row = st ? cell.r : ROWS - 1 - cell.r;
    n.Fx = -(N * S) / 2 + (cell.c + 0.5) * cellW + rr(-3, 3);
    n.Fy = (st ? 1 : -1) * ((row + 0.5) * cellH + 1.5) + rr(-2.5, 2.5);
  }
}

// Per-nucleotide motion, and each atom's place relative to its part.
const PART_D = [2.4, 0.5, 2.1];
const ORDER_ROOT = [null, "C1'", 'P'];
for (const n of nucs) {
  const ids = n.parts.flat();
  let cx = 0, cy = 0;
  for (const j of ids) { cx += atoms[j].lx; cy += atoms[j].ly; }
  cx /= ids.length; cy /= ids.length;
  const x0 = xOf(n.i);
  n.Lx = x0 + cx; n.Ly = cy; n.sgn = n.st ? 1 : -1;
  n.th0 = rr(-Math.PI, Math.PI); n.spin = rr(-0.25, 0.25);
  n.dr = rr(0.5, 1.4); n.dw = rr(0.6, 1.4); n.dp = rr(0, TAU); n.bump = rr(-9, 9);
  n.part = n.parts.map((ps, p) => {
    let px = 0, py = 0;
    for (const j of ps) { px += atoms[j].lx - cx; py += atoms[j].ly - cy; }
    px /= ps.length; py /= ps.length;
    for (const j of ps) { atoms[j].rx = atoms[j].lx - cx - px; atoms[j].ry = atoms[j].ly - cy - py; }
    const l = Math.hypot(px, py) || 1, a = rr(-0.5, 0.5);
    const ax = (px / l) * Math.cos(a) - (py / l) * Math.sin(a), ay = (px / l) * Math.sin(a) + (py / l) * Math.cos(a);
    return { cx: px, cy: py, ax: ax * PART_D[p], ay: ay * PART_D[p], th: rr(-0.9, 0.9) };
  });
}

// Bonds inside each part, and the order its atoms take their places (out from a root atom).
const tmplBonds = (n, p) => (p === 0 ? n.base.bonds : p === 1 ? [...SUG.bonds, ["C1'", "O1'", 1]] : PHO.bonds);
for (const n of nucs) {
  n.done = [0, 0, 0];
  for (let p = 0; p < 3; p++) {
    const tb = tmplBonds(n, p);
    const root = p === 0 ? n.base.attach : ORDER_ROOT[p];
    const adj = {};
    for (const [a, b] of tb) { (adj[a] ||= []).push(b); (adj[b] ||= []).push(a); }
    const seen = [root], q = [root];
    while (q.length) { const a = q.shift(); for (const b of adj[a] || []) if (!seen.includes(b)) { seen.push(b); q.push(b); } }
    const t0 = p === 0 ? T.base + rr(0, 0.9) : T.sugar + (p === 2 ? 0.1 : 0) + rr(0, 0.8);
    seen.forEach((nm, o) => {
      const at = atoms[n.idx[nm]];
      at.tForm = t0 + o * 0.03;
      at.tIn = rand() * Math.max(0, Math.min(1.0, at.tForm - 0.75));
      const sa = rr(0, TAU), sd = rr(30, 60), ca = rr(0, TAU), cd = rr(1.4, 4.2);
      at.sx = Math.cos(sa) * sd; at.sy = Math.sin(sa) * sd;
      at.cx = Math.cos(ca) * cd; at.cy = Math.sin(ca) * cd;
      at.ow = rr(1.2, 3.0) * (rand() < 0.5 ? -1 : 1);
      at.w1 = rr(16, 30); at.w2 = rr(16, 30); at.p1 = rr(0, TAU); at.p2 = rr(0, TAU);
    });
    n.done[p] = Math.max(...seen.map((nm) => atoms[n.idx[nm]].tForm)) + DUR.form;
    for (const [a, b, o] of tb) {
      const ja = n.idx[a], jb = n.idx[b];
      bond(ja, jb, o, Math.max(atoms[ja].tForm, atoms[jb].tForm) + DUR.form * 0.8);
    }
  }
  for (const ring of n.base.rings) {
    const ids = ring.map((nm) => n.idx[nm]);
    rings.push({ ids, k: n.k, col: BASE_COL[n.b], tOn: Math.max(...ids.map((j) => atoms[j].tForm)) + DUR.form });
  }
  n.ringDone = Math.max(...rings.filter((r) => r.k === n.k).map((r) => r.tOn));
  flashes.push({ j: n.idx[n.base.attach], t0: n.ringDone, col: BASE_COL[n.b] });
}

// Nucleotides: each base joins its sugar, each sugar its phosphate; the base's H and the sugar's OH leave as water.
for (const n of nucs) {
  n.tNuc = Math.max(T.nuc + rr(0, 0.55), n.done[0] + 0.05, n.done[1] + 0.05, n.done[2] + 0.05);
  const tj = n.tNuc + DUR.nuc * 0.8;
  bond(n.idx["C1'"], n.idx[n.base.attach], 1, tj, { kind: 'gly' });
  bond(n.idx["C5'"], n.idx["O5'"], 1, tj, { glowOf: n.k });
  const tl = n.tNuc + DUR.nuc * 0.55;
  atoms[n.idx.HX].leave = tl;
  atoms[n.idx["O1'"]].leave = tl;
  waters.push({ j: n.idx["O1'"], t0: tl, k: n.k });
  flashes.push({ j: n.idx["C1'"], t0: tj, col: BASE_COL[n.b] });
}

// Strands: nucleotides line up 5' to 3', and each phosphodiester bond forms as its neighbour arrives.
const prevOf = (n) => (n.st === 0 ? (n.i > 0 ? nucAt(0, n.i - 1) : null) : n.i < N - 1 ? nucAt(1, n.i + 1) : null);
const nextOf = (n) => (n.st === 0 ? (n.i < N - 1 ? nucAt(0, n.i + 1) : null) : n.i > 0 ? nucAt(1, n.i - 1) : null);
const ringPrev = (n) => (n.st === 0 ? nucAt(0, N - 1) : nucAt(1, 0));
for (const n of nucs) {
  const rank = n.st === 0 ? n.i : N - 1 - n.i;
  n.tLine = T.line + (1.15 * rank) / (N - 1) + rr(0, 0.15);
}
for (const n of nucs) {
  const p = prevOf(n);
  n.tPd = p ? Math.max(n.tLine, p.tLine) + DUR.line + 0.02 : T.close;
  const o3 = (p || ringPrev(n)).idx["O3'"];
  bond(o3, n.idx.P, 1, n.tPd, { kind: 'pd', glowOf: (p || ringPrev(n)).k });
  atoms[n.idx.OP3].leave = n.tPd - 0.08;
  if (p) { waters.push({ j: n.idx.OP3, t0: n.tPd - 0.08, k: n.k, out: n.sgn }); flashes.push({ j: n.idx.P, t0: n.tPd, col: STRAND[n.st] }); }
}
for (const n of nucs) {
  const nx = nextOf(n);
  n.glow = Math.min(n.tPd, nx ? nx.tPd : T.close);
}
/** The backbone inside a nucleotide: P, O5', C5', C4', C3', O3'. */
const CHAIN = new Set(["P|O5'", "C4'|C5'", "C3'|C4'", "C3'|O3'"]);
for (const bd of bonds) {
  const a = atoms[bd.a], b = atoms[bd.b];
  bd.tOff = Math.min(a.leave, b.leave);
  if (bd.glowOf === undefined && a.k === b.k && CHAIN.has([a.name, b.name].sort().join('|'))) bd.glowOf = a.k;
  if (bd.glowOf !== undefined) { bd.glow = nucs[bd.glowOf].glow; bd.st = nucs[bd.glowOf].st; }
}

// Base pairs: hydrogen bonds zip from the middle outward.
for (let i = 0; i < N; i++) {
  const n0 = nucAt(0, i), n1 = nucAt(1, i);
  const pu = BASE[n0.b].purine ? n0 : n1, py = pu === n0 ? n1 : n0;
  const t0 = T.hb + (0.7 * Math.abs(xOf(i))) / ((N * S) / 2) + rr(0, 0.08);
  const gc = pu.b === 'G';
  const list = gc ? [[pu, 'H1', py, 'N3'], [pu, 'H21', py, 'O2'], [py, 'H41', pu, 'O6']] : [[py, 'H3', pu, 'N1'], [pu, 'H61', py, 'O4']];
  for (const [d, dn, a, an] of list) hbonds.push({ a: d.idx[dn], b: a.idx[an], tOn: t0 });
  flashes.push({ j: n0.idx[n0.base.face], t0, col: null });
  n0.tHb = t0; n0.gc = gc;
}

// Callouts near the middle of the first close view.
{
  const near = [...nucs].sort((p, q) => Math.hypot(p.Fx, p.Fy * 1.4) - Math.hypot(q.Fx, q.Fy * 1.4));
  const used = new Set();
  const pick = (f) => { const n = near.find((m) => !used.has(m.k) && f(m)); used.add(n.k); return n; };
  const sg = pick(() => true), ph = pick(() => true);
  callouts.push({ j: sg.idx["O4'"], t0: sg.done[1], t1: sg.done[1] + 1.25, text: 'Deoxyribose sugar' });
  callouts.push({ j: ph.idx.P, t0: ph.done[2], t1: ph.done[2] + 1.25, text: 'Phosphate group' });
  const pu = pick((m) => m.base.purine), py = pick((m) => !m.base.purine);
  callouts.push({ j: pu.idx.C4, t0: pu.ringDone, t1: pu.ringDone + 1.3, text: `${BASE_NAME[pu.b]} | purine` });
  callouts.push({ j: py.idx.C5, t0: py.ringDone, t1: py.ringDone + 1.3, text: `${BASE_NAME[py.b]} | pyrimidine` });
  const nu = near[0];
  callouts.push({ j: nu.idx["C1'"], t0: nu.tNuc + DUR.nuc, t1: Math.min(T.line + 0.3, nu.tNuc + DUR.nuc + 1.3), text: 'Nucleotide' });
  const mids = [...Array(N).keys()].sort((p, q) => Math.abs(xOf(p)) - Math.abs(xOf(q)));
  const at = nucAt(0, mids.find((i) => !nucAt(0, i).gc)), gcn = nucAt(0, mids.find((i) => nucAt(0, i).gc));
  callouts.push({ j: at.idx[at.base.face], t0: at.tHb + 0.15, t1: T.twist + 0.5, text: 'A–T | 2 hydrogen bonds' });
  const gcp = nucAt(1, gcn.i);
  callouts.push({ j: gcp.idx[gcp.base.face], t0: gcn.tHb + 0.15, t1: T.twist + 0.5, text: 'G–C | 3 hydrogen bonds', below: true });
}

// ---------- Flat arrays for the per-frame loop
const NA = atoms.length;
const F = (key) => Float32Array.from(atoms, (a) => a[key]);
const A_k = Int32Array.from(atoms, (a) => a.k), A_p = Int8Array.from(atoms, (a) => a.part), A_el = Int8Array.from(atoms, (a) => ELS.indexOf(a.el));
const A_rx = F('rx'), A_ry = F('ry'), A_tForm = F('tForm'), A_tIn = F('tIn'), A_leave = Float64Array.from(atoms, (a) => a.leave);
const A_sx = F('sx'), A_sy = F('sy'), A_cx = F('cx'), A_cy = F('cy'), A_ow = F('ow');
const A_w1 = F('w1'), A_w2 = F('w2'), A_p1 = F('p1'), A_p2 = F('p2');
const SX = new Float32Array(NA), SY = new Float32Array(NA), VIS = new Uint8Array(NA);
const NK = nucs.length;
const P_x = new Float32Array(NK), P_y = new Float32Array(NK), P_c = new Float32Array(NK), P_s = new Float32Array(NK);
const Q_x = new Float32Array(NK * 3), Q_y = new Float32Array(NK * 3), Q_c = new Float32Array(NK * 3), Q_s = new Float32Array(NK * 3);
const K_phi = new Float32Array(NK);

/** Where nucleotide n sits at time t: its centre, turn, and each part's offset and turn. */
function nucPose(n, t, k) {
  const eN = smooth(prog(t, n.tNuc, DUR.nuc));
  const eL = inOut(prog(t, n.tLine, DUR.line));
  const gap = GFAR * (1 - inOut(prog(t, T.pair, DUR.pair)));
  const tx = n.Lx, ty = n.Ly + n.sgn * gap;
  const dx = tx - n.Fx, dy = ty - n.Fy, dl = Math.hypot(dx, dy) || 1;
  const bump = Math.sin(Math.PI * eL) * n.bump, free = 1 - eL;
  P_x[k] = n.Fx + dx * eL - (dy / dl) * bump + free * n.dr * Math.sin(t * n.dw + n.dp);
  P_y[k] = n.Fy + dy * eL + (dx / dl) * bump + free * n.dr * Math.cos(t * n.dw * 0.8 + n.dp);
  const th = (n.th0 + n.spin * t) * free;
  P_c[k] = Math.cos(th); P_s[k] = Math.sin(th);
  const f = 1 - eN;
  for (let p = 0; p < 3; p++) {
    const q = n.part[p], i = k * 3 + p;
    Q_x[i] = q.cx + q.ax * f; Q_y[i] = q.cy + q.ay * f;
    Q_c[i] = Math.cos(q.th * f); Q_s[i] = Math.sin(q.th * f);
  }
}
/** Atom j in ladder space at time t (the nucleotide pose already set for t). */
const JIT = 0.55, VIB = 0.045;
function atomAt(j, t, out) {
  const k = A_k[j], i = k * 3 + A_p[j];
  const x = A_rx[j], y = A_ry[j];
  const px = x * Q_c[i] - y * Q_s[i] + Q_x[i], py = x * Q_s[i] + y * Q_c[i] + Q_y[i];
  let wx = P_x[k] + px * P_c[k] - py * P_s[k], wy = P_y[k] + px * P_s[k] + py * P_c[k];
  const eM = smooth(prog(t, A_tForm[j], DUR.form));
  if (eM < 1) {
    const eI = outC(prog(t, A_tIn[j], DUR.in)), a = A_ow[j] * t, ca = Math.cos(a), sa = Math.sin(a);
    const ox = (1 - eI) * A_sx[j] + eI * (A_cx[j] * ca - A_cy[j] * sa + JIT * Math.sin(A_w1[j] * t + A_p1[j]));
    const oy = (1 - eI) * A_sy[j] + eI * (A_cx[j] * sa + A_cy[j] * ca + JIT * Math.cos(A_w2[j] * t + A_p2[j]));
    wx += (1 - eM) * ox; wy += (1 - eM) * oy;
  }
  wx += VIB * Math.sin(A_w1[j] * t + A_p1[j]); wy += VIB * Math.cos(A_w2[j] * t + A_p2[j]);
  out[0] = wx; out[1] = wy;
}
// Where each leaving atom starts its drift, worked out once.
{
  const tmp = [0, 0];
  for (const w of waters) {
    nucPose(nucs[w.k], w.t0, w.k);
    atomAt(w.j, w.t0, tmp);
    w.x = tmp[0]; w.y = tmp[1];
    let dx, dy;
    if (w.out) { dx = rr(-0.6, 0.6); dy = w.out * -1; }
    else { dx = tmp[0] - P_x[w.k]; dy = tmp[1] - P_y[w.k]; }
    const l = Math.hypot(dx, dy) || 1, a = rr(-0.5, 0.5);
    w.dx = (dx / l) * Math.cos(a) - (dy / l) * Math.sin(a); w.dy = (dx / l) * Math.sin(a) + (dy / l) * Math.cos(a);
    w.rot = rr(0, TAU); w.spin = rr(-4, 4);
  }
}

// ---------- Stage parameters
const twistAt = (t) => inOut(prog(t, T.twist, DUR.twist));
const sigmaAt = (t) => 1 + (SIG_F - 1) * twistAt(t);
const bendAt = (t) => inOut(prog(t, T.bend, DUR.bend));
const spinAt = (t) => inOut(prog(t, T.spin, DUR.spin)) * 360;

// ---------- Camera: keyframes up close, then it follows the helix as it bends
const CAM_KF = [[0, 15, 15], [1.4, 16.5, 16.5], [3.3, 28, 26], [4.7, 62, 56], [6.0, 172, 70], [7.0, 172, 34], [7.8, 52, 21], [9.0, 52, 21]];
const FIT_T = 9.2, FIT_D = 1.1;
/** A smooth curve through keyframes that keeps moving between them and never overshoots (Fritsch–Carlson). */
function monotone(ts, vs) {
  const n = ts.length, d = [], m = new Array(n).fill(0);
  for (let i = 0; i < n - 1; i++) d.push((vs[i + 1] - vs[i]) / (ts[i + 1] - ts[i]));
  for (let i = 1; i < n - 1; i++) m[i] = d[i - 1] * d[i] <= 0 ? 0 : (3 * (ts[i + 1] - ts[i - 1])) / ((2 * ts[i + 1] - ts[i] - ts[i - 1]) / d[i - 1] + (ts[i + 1] + ts[i] - 2 * ts[i - 1]) / d[i]);
  return (t) => {
    if (t <= ts[0]) return vs[0];
    if (t >= ts[n - 1]) return vs[n - 1];
    let i = 0;
    while (t > ts[i + 1]) i++;
    const h = ts[i + 1] - ts[i], u = (t - ts[i]) / h, u2 = u * u, u3 = u2 * u;
    return (2 * u3 - 3 * u2 + 1) * vs[i] + (u3 - 2 * u2 + u) * h * m[i] + (-2 * u3 + 3 * u2) * vs[i + 1] + (u3 - u2) * h * m[i + 1];
  };
}
const camHX = monotone(CAM_KF.map((k) => k[0]), CAM_KF.map((k) => Math.log(k[1])));
const camHY = monotone(CAM_KF.map((k) => k[0]), CAM_KF.map((k) => Math.log(k[2])));
function camKF(t) { return { cx: 0, cy: 0, hx: Math.exp(camHX(t)), hy: Math.exp(camHY(t)) }; }
function camFit(t) {
  const L = N * S * sigmaAt(t), k = bendAt(t), band = A_R + W_R / 2, R0 = L / TAU;
  const padEnd = (R0 + band) / 0.8 - (R0 + band), pad = 7 + (padEnd - 7) * k;
  if (k < 1e-4) return { cx: 0, cy: 0, hx: L / 2 + pad, hy: band + pad };
  const kap = (k * TAU) / L, Th = k * Math.PI, inv = 1 / kap;
  const xm = Th <= Math.PI / 2 ? inv * Math.sin(Th) : inv;
  const ymax = k * R0, ymin = k * R0 - inv * (1 - Math.cos(Th));
  return { cx: 0, cy: (ymax + ymin) / 2, hx: xm + band + pad, hy: (ymax - ymin) / 2 + band + pad };
}
function camAt(t) {
  if (t < FIT_T) return camKF(t);
  const a = camKF(FIT_T), b = camFit(t), e = inOut(prog(t, FIT_T, FIT_D));
  return { cx: a.cx + (b.cx - a.cx) * e, cy: a.cy + (b.cy - a.cy) * e, hx: a.hx * Math.pow(b.hx / a.hx, e), hy: a.hy * Math.pow(b.hy / a.hy, e) };
}

// ---------- Canvas, theme, view
/** @type {HTMLCanvasElement} */
let canvas;
/** @type {CanvasRenderingContext2D} */
let ctx;
/** @type {HTMLElement} */
let stageEl;
const layer = document.createElement('canvas'), lctx = layer.getContext('2d');
let VW = 0, VH = 0, dpr = 1, portrait = false;
const V = { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0, s: 1 };
const PAL = {};
// The film's own colours; the page's background and text colours are read from the site's theme.
const LOOK = {
  light: { bg: '#ffffff', panel: '#ffffff', fg: '#1f2937', muted: '#6b7280', line: '#e5e7eb', accent: '#1f6bff', bond: '#64748b', hb: '#3b82f6', atomC: '#475569', atomH: '#e8ecf2', hEdge: '#94a3b8' },
  dark: { bg: '#0d1322', panel: '#121a2b', fg: '#e6eaf2', muted: '#94a3b8', line: '#26324a', accent: '#5b8dff', bond: '#8b98ad', hb: '#7aa5ff', atomC: '#a5b1c4', atomH: '#e8ecf2', hEdge: '#64748b' }
};
let isDark = () => false;
/** A computed colour as #rrggbb, or '' when it is transparent. */
function toHex(c) {
  const m = c.match(/rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)(?:[,\s/]+([\d.]+%?))?/);
  if (!m || (m[4] !== undefined && parseFloat(m[4]) === 0)) return '';
  return '#' + [m[1], m[2], m[3]].map((v) => (+v).toString(16).padStart(2, '0')).join('');
}
/** The colour the canvas sits on: the first ancestor with a background of its own. */
function backgroundOf(el) {
  for (let n = el; n; n = n.parentElement) {
    const hex = toHex(getComputedStyle(n).backgroundColor);
    if (hex) return hex;
  }
  return '';
}
function readTheme() {
  const dark = isDark();
  const base = LOOK[dark ? 'dark' : 'light'];
  const cs = getComputedStyle(canvas);
  const site = (name, fallback) => toHex(cs.getPropertyValue(name).trim()) || cs.getPropertyValue(name).trim() || fallback;
  PAL.dark = dark;
  PAL.bg = backgroundOf(canvas) || base.bg;
  PAL.panel = site('--mg-surface', base.panel);
  PAL.fg = site('--mg-text', base.fg);
  PAL.muted = site('--mg-text-2', base.muted);
  PAL.line = site('--mg-border', base.line);
  PAL.accent = base.accent;
  PAL.bond = base.bond;
  PAL.hb = base.hb;
  PAL.el = { C: base.atomC, H: base.atomH, ...EL_FIXED[dark ? 'dark' : 'light'] };
  PAL.hEdge = base.hEdge;
}
function resize() {
  const r = stageEl.getBoundingClientRect();
  dpr = Math.min(2, window.devicePixelRatio || 1);
  VW = Math.max(1, r.width); VH = Math.max(1, r.height);
  canvas.width = Math.round(VW * dpr); canvas.height = Math.round(VH * dpr);
  portrait = VH > VW * 1.05;
}
function setView(t) {
  const cam = camAt(t);
  const rho = (portrait ? -90 : 0) * (1 - bendAt(t)) * D2R;
  const cr = Math.abs(Math.cos(rho)), sr = Math.abs(Math.sin(rho));
  const hx = cr * cam.hx + sr * cam.hy, hy = sr * cam.hx + cr * cam.hy;
  const s = Math.min(VW / (2 * hx), VH / (2 * hy));
  const tot = rho + spinAt(t) * D2R;
  const c = Math.cos(tot), sn = Math.sin(tot), cR = Math.cos(rho), sR = Math.sin(rho);
  V.s = s; V.a = s * c; V.b = -s * sn; V.c = s * sn; V.d = s * c;
  V.e = VW / 2 - s * (cR * cam.cx - sR * cam.cy);
  V.f = VH / 2 - s * (sR * cam.cx + cR * cam.cy);
}
const toX = (x, y) => V.a * x + V.b * y + V.e;
const toY = (x, y) => V.c * x + V.d * y + V.f;

function hexRgb(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function mixHex(a, b, f) { const A = hexRgb(a), B = hexRgb(b); return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * f)).join(',')})`; }

// ---------- Atoms, bonds and the small things around them
const tmp = [0, 0];
function computeAtoms(t) {
  for (let k = 0; k < NK; k++) nucPose(nucs[k], t, k);
  const w = twistAt(t), sig = sigmaAt(t);
  for (let k = 0; k < NK; k++) K_phi[k] = (w * TAU * xOf(nucs[k].i)) / (TURN * S);
  const m = 40;
  for (let j = 0; j < NA; j++) {
    if (t >= A_leave[j]) { VIS[j] = 0; continue; }
    atomAt(j, t, tmp);
    let x = tmp[0], y = tmp[1];
    if (w > 0) { x *= sig; y *= Math.cos(K_phi[A_k[j]]); }
    const sx = toX(x, y), sy = toY(x, y);
    SX[j] = sx; SY[j] = sy;
    VIS[j] = sx > -m && sx < VW + m && sy > -m && sy < VH + m ? 1 : 0;
  }
}

function drawAtoms(t, alpha) {
  const s = V.s;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';

  // Backbone glow in the strand's colour once the strand forms.
  const gw = 2.3 * s;
  for (let st = 0; st < 2; st++) {
    ctx.strokeStyle = STRAND[st];
    ctx.lineWidth = gw;
    ctx.globalAlpha = alpha * 0.22;
    ctx.beginPath();
    for (const bd of bonds) {
      if (bd.st !== st || t < bd.glow || t < bd.tOn || t >= bd.tOff) continue;
      if (!VIS[bd.a] && !VIS[bd.b]) continue;
      ctx.moveTo(SX[bd.a], SY[bd.a]); ctx.lineTo(SX[bd.b], SY[bd.b]);
    }
    ctx.stroke();
  }

  // Base rings fill in their base's colour as they close.
  for (const r of rings) {
    if (t < r.tOn) continue;
    const ids = r.ids;
    if (!ids.some((j) => VIS[j])) continue;
    ctx.globalAlpha = alpha * 0.34 * smooth(prog(t, r.tOn, 0.3));
    ctx.fillStyle = r.col;
    ctx.beginPath();
    ctx.moveTo(SX[ids[0]], SY[ids[0]]);
    for (let q = 1; q < ids.length; q++) ctx.lineTo(SX[ids[q]], SY[ids[q]]);
    ctx.closePath(); ctx.fill();
  }

  // Covalent bonds: full ones in one path, growing ones on their own.
  const bw = Math.max(0.9, 0.11 * s), dOff = Math.max(1.1, 0.085 * s);
  const showDouble = s > 9;
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = PAL.bond;
  ctx.lineWidth = bw;
  ctx.beginPath();
  const growing = [];
  for (const bd of bonds) {
    if (t < bd.tOn || t >= bd.tOff) continue;
    const a = bd.a, b = bd.b;
    if (!VIS[a] && !VIS[b]) continue;
    const g = prog(t, bd.tOn, 0.18);
    if (g < 1) { growing.push(bd, g); continue; }
    if (bd.order === 2 && showDouble) {
      const dx = SX[b] - SX[a], dy = SY[b] - SY[a], l = Math.hypot(dx, dy) || 1, nx = (-dy / l) * dOff, ny = (dx / l) * dOff;
      ctx.moveTo(SX[a] + nx, SY[a] + ny); ctx.lineTo(SX[b] + nx, SY[b] + ny);
      ctx.moveTo(SX[a] - nx, SY[a] - ny); ctx.lineTo(SX[b] - nx, SY[b] - ny);
    } else { ctx.moveTo(SX[a], SY[a]); ctx.lineTo(SX[b], SY[b]); }
  }
  ctx.stroke();
  for (let q = 0; q < growing.length; q += 2) {
    const bd = growing[q], g = growing[q + 1], a = bd.a, b = bd.b;
    const dx = SX[b] - SX[a], dy = SY[b] - SY[a];
    ctx.globalAlpha = alpha * (0.4 + 0.6 * g);
    ctx.beginPath();
    ctx.moveTo(SX[a], SY[a]); ctx.lineTo(SX[a] + (dx * g) / 2, SY[a] + (dy * g) / 2);
    ctx.moveTo(SX[b], SY[b]); ctx.lineTo(SX[b] - (dx * g) / 2, SY[b] - (dy * g) / 2);
    ctx.stroke();
  }

  // Hydrogen bonds, dashed.
  ctx.strokeStyle = PAL.hb;
  ctx.lineWidth = Math.max(0.8, 0.075 * s);
  ctx.setLineDash([Math.max(1.5, 0.2 * s), Math.max(1.5, 0.16 * s)]);
  for (const hb of hbonds) {
    if (t < hb.tOn || (!VIS[hb.a] && !VIS[hb.b])) continue;
    ctx.globalAlpha = alpha * smooth(prog(t, hb.tOn, 0.2));
    ctx.beginPath(); ctx.moveTo(SX[hb.a], SY[hb.a]); ctx.lineTo(SX[hb.b], SY[hb.b]); ctx.stroke();
  }
  ctx.setLineDash([]);

  // Atoms, one path per element.
  ctx.globalAlpha = alpha;
  for (let e = 0; e < ELS.length; e++) {
    const el = ELS[e], r = Math.max(0.9, EL_R[el] * s);
    ctx.fillStyle = PAL.el[el];
    ctx.beginPath();
    for (let j = 0; j < NA; j++) {
      if (!VIS[j] || A_el[j] !== e) continue;
      ctx.moveTo(SX[j] + r, SY[j]); ctx.arc(SX[j], SY[j], r, 0, TAU);
    }
    ctx.fill();
    if (el === 'H' && r > 1.6) { ctx.strokeStyle = PAL.hEdge; ctx.lineWidth = Math.min(1, r * 0.2); ctx.stroke(); }
  }
  // Waters drift off where bonds formed.
  drawWaters(t, alpha);

  // Element letters up close.
  if (EL_R.C * s >= 5.5) {
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (let e = 0; e < ELS.length; e++) {
      const el = ELS[e], r = EL_R[el] * s;
      if (r < 4) continue;
      ctx.font = `700 ${Math.round(r * 1.15)}px Lato, Helvetica, Arial, sans-serif`;
      ctx.fillStyle = el === 'H' ? '#334155' : PAL.dark && el === 'C' ? '#0d1322' : '#ffffff';
      for (let j = 0; j < NA; j++) if (VIS[j] && A_el[j] === e) ctx.fillText(el, SX[j], SY[j] + 0.5);
    }
  }
  // Base letters once the rings close.
  if (s >= 6) {
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = `900 ${Math.round(1.2 * s)}px Lato, Helvetica, Arial, sans-serif`;
    for (const n of nucs) {
      const six = rings.find((r) => r.k === n.k);
      if (t < six.tOn || !six.ids.some((j) => VIS[j])) continue;
      let x = 0, y = 0;
      for (const j of six.ids) { x += SX[j]; y += SY[j]; }
      ctx.globalAlpha = alpha * smooth(prog(t, six.tOn, 0.3));
      ctx.fillStyle = BASE_INK[n.b];
      ctx.fillText(n.b, x / 6, y / 6 + 0.5);
    }
  }
  drawFlashes(t, alpha);
  ctx.restore();
}

function drawWaters(t, alpha) {
  const s = V.s, w = twistAt(t);
  if (w > 0) return;
  const rO = Math.max(0.9, EL_R.O * s), rH = Math.max(0.7, EL_R.H * s);
  for (const wa of waters) {
    const u = (t - wa.t0) / 1.1;
    if (u < 0 || u >= 1) continue;
    const d = 6.5 * outC(u), x = wa.x + wa.dx * d, y = wa.y + wa.dy * d;
    const sx = toX(x, y), sy = toY(x, y);
    if (sx < -20 || sx > VW + 20 || sy < -20 || sy > VH + 20) continue;
    ctx.globalAlpha = alpha * (1 - u * u);
    const a = wa.rot + wa.spin * (t - wa.t0), hd = 0.75 * s;
    ctx.fillStyle = PAL.el.H; ctx.strokeStyle = PAL.hEdge; ctx.lineWidth = 1;
    for (const da of [-52, 52]) {
      const hx = sx + Math.cos(a + da * D2R) * hd, hy = sy + Math.sin(a + da * D2R) * hd;
      ctx.beginPath(); ctx.arc(hx, hy, rH, 0, TAU); ctx.fill(); if (rH > 1.6) ctx.stroke();
    }
    ctx.fillStyle = PAL.el.O;
    ctx.beginPath(); ctx.arc(sx, sy, rO, 0, TAU); ctx.fill();
  }
}

function drawFlashes(t, alpha) {
  const s = V.s;
  ctx.lineWidth = Math.max(1.2, 0.12 * s);
  for (const fl of flashes) {
    const u = (t - fl.t0) / 0.42;
    if (u < 0 || u >= 1 || !VIS[fl.j]) continue;
    const e = outC(u);
    ctx.globalAlpha = alpha * 0.85 * (1 - u);
    ctx.strokeStyle = fl.col || PAL.hb;
    ctx.beginPath(); ctx.arc(SX[fl.j], SY[fl.j], Math.max(2, (0.35 + 1.5 * e) * s), 0, TAU); ctx.stroke();
  }
}

// ---------- The ribbon helix, as in the logo
const M = 720;
const HXs = [new Float32Array(M + 1), new Float32Array(M + 1)], HYs = [new Float32Array(M + 1), new Float32Array(M + 1)], HZs = [new Float32Array(M + 1), new Float32Array(M + 1)];
function bendMap(s, Y, k, kap, off, out) {
  if (k < 1e-5) { out[0] = s; out[1] = Y; return; }
  const a = kap * s, sa = Math.sin(a), ca = Math.cos(a);
  out[0] = sa / kap + Y * sa; out[1] = -(1 - ca) / kap + Y * ca + off;
}
function drawHelix(t, alpha) {
  const w = twistAt(t), sig = sigmaAt(t), k = bendAt(t), L = N * S * sig, R0 = L / TAU, kap = (k * TAU) / L, off = k * R0;
  const s = V.s, dim = 0.3 * (1 - k);
  const phiOf = (x) => (w * TAU * x) / (TURN * S);
  for (let st = 0; st < 2; st++) {
    const y0 = st ? A_R : -A_R, X = HXs[st], Y = HYs[st], Z = HZs[st];
    for (let j = 0; j <= M; j++) {
      const x = -(N * S) / 2 + (j * N * S) / M, ph = phiOf(x);
      bendMap(x * sig, y0 * Math.cos(ph), k, kap, off, tmp);
      X[j] = toX(tmp[0], tmp[1]); Y[j] = toY(tmp[0], tmp[1]); Z[j] = y0 * Math.sin(ph);
    }
  }
  // While it fades in, the helix is drawn whole on its own layer, then laid over the atoms.
  const layered = alpha < 0.999, g = layered ? lctx : ctx;
  if (layered) {
    if (layer.width !== canvas.width || layer.height !== canvas.height) { layer.width = canvas.width; layer.height = canvas.height; }
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, VW, VH);
  }
  const run = (st, back) => {
    const X = HXs[st], Y = HYs[st], Z = HZs[st];
    g.beginPath();
    let pen = false;
    for (let j = 0; j < M; j++) {
      if (Z[j] + Z[j + 1] <= 0 === back) { if (!pen) { g.moveTo(X[j], Y[j]); pen = true; } g.lineTo(X[j + 1], Y[j + 1]); } else pen = false;
    }
  };
  g.save();
  g.lineJoin = 'round';
  const rw = W_R * s;
  // Back halves first, a shade lighter while the helix is straight.
  g.lineCap = 'round'; g.lineWidth = rw;
  for (let st = 0; st < 2; st++) { g.strokeStyle = mixHex(STRAND[st], PAL.bg, dim); run(st, true); g.stroke(); }
  // Rungs: half a rung per base, in its colour, from strand edge to strand edge.
  g.lineCap = 'butt'; g.lineWidth = RUNG_W * s;
  const p0 = [0, 0], p1 = [0, 0], pm = [0, 0];
  for (let i = 0; i < N; i++) {
    const x = xOf(i), ph = phiOf(x), cph = Math.cos(ph), sx = x * sig;
    const reach = A_R * Math.abs(cph) - W_R * 0.42;
    if (reach <= 0) continue;
    const y = Math.sign(cph) * reach;
    bendMap(sx, -y, k, kap, off, p0);
    bendMap(sx, 0, k, kap, off, pm);
    bendMap(sx, y, k, kap, off, p1);
    const b0 = seq[i], b1 = PAIR[b0];
    g.strokeStyle = BASE_COL[b0];
    g.beginPath(); g.moveTo(toX(p0[0], p0[1]), toY(p0[0], p0[1])); g.lineTo(toX(pm[0], pm[1]), toY(pm[0], pm[1])); g.stroke();
    g.strokeStyle = BASE_COL[b1];
    g.beginPath(); g.moveTo(toX(pm[0], pm[1]), toY(pm[0], pm[1])); g.lineTo(toX(p1[0], p1[1]), toY(p1[0], p1[1])); g.stroke();
  }
  // Front halves over a thin edge of background, so each crossing reads.
  g.lineCap = 'butt'; g.lineWidth = rw + 3; g.strokeStyle = PAL.bg;
  for (let st = 0; st < 2; st++) { run(st, false); g.stroke(); }
  g.lineCap = 'round'; g.lineWidth = rw;
  for (let st = 0; st < 2; st++) { g.strokeStyle = STRAND[st]; run(st, false); g.stroke(); }
  g.restore();
  if (layered) {
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = alpha;
    ctx.drawImage(layer, 0, 0);
    ctx.restore();
  }
}

// The two ends meet at the top: a burst where the last phosphodiester bonds form.
function drawJunction(t) {
  const u = (t - T.close) / 0.8;
  if (u < 0 || u >= 1) return;
  const R0 = (N * S * SIG_F) / TAU;
  const x = toX(0, -R0), y = toY(0, -R0), s = V.s, e = outC(u);
  ctx.save();
  const g = ctx.createRadialGradient(x, y, 0, x, y, (3 + 14 * e) * s);
  g.addColorStop(0, `rgba(255,255,255,${0.9 * (1 - u)})`);
  g.addColorStop(0.4, PAL.dark ? `rgba(91,141,255,${0.35 * (1 - u)})` : `rgba(31,107,255,${0.25 * (1 - u)})`);
  g.addColorStop(1, 'rgba(31,107,255,0)');
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(x, y, (3 + 14 * e) * s, 0, TAU); ctx.fill();
  ctx.lineWidth = 2.5;
  for (const [i, col] of STRAND.entries()) {
    ctx.globalAlpha = 1 - u;
    ctx.strokeStyle = col;
    ctx.beginPath(); ctx.arc(x, y, (1.5 + (9 + 4 * i) * e) * s, 0, TAU); ctx.stroke();
  }
  ctx.restore();
}

// A soft glow behind the finished ring, breathing like the logo's.
function drawGlow(t, now) {
  const a = smooth(prog(t, T.close - 0.3, 1.2));
  if (a <= 0) return;
  const R0 = (N * S * SIG_F) / TAU, x = V.e, y = V.f, r = (R0 + A_R) * V.s * 1.05;
  const breathe = 0.78 + 0.22 * Math.sin((now / 5000) * TAU);
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  const rgb = PAL.dark ? '91,141,255' : '31,107,255';
  g.addColorStop(0, `rgba(${rgb},${0.16 * a * breathe})`);
  g.addColorStop(0.7, `rgba(${rgb},${0.05 * a * breathe})`);
  g.addColorStop(1, `rgba(${rgb},0)`);
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
}

// The logo's wordmark in the middle of the closed ring.
const logo = new Image();
let logoReady = false;
logo.onload = () => { logoReady = true; };
// The logo's data sits in the last script on the page.
function drawWordmark(t) {
  const a = smooth(prog(t, T.word, DUR.word));
  if (a <= 0) return;
  const band = A_R + W_R / 2, R0 = (N * S * SIG_F) / TAU;
  /** The logo's ring reaches 0.836 of its half-width; its wordmark sits inside 0.555. */
  const half = ((R0 + band) / 0.836) * V.s, x = V.e, y = V.f;
  ctx.save();
  ctx.globalAlpha = a;
  if (logoReady) {
    ctx.beginPath(); ctx.arc(x, y, half * 0.555, 0, TAU); ctx.clip();
    const sc = 1 + 0.04 * (1 - a);
    ctx.drawImage(logo, x - half * sc, y - half * sc, 2 * half * sc, 2 * half * sc);
  } else {
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = STRAND[1]; ctx.font = `900 ${Math.round(half * 0.11)}px Lato, sans-serif`;
    ctx.fillText('B S P', x, y - half * 0.13);
    ctx.fillStyle = STRAND[0]; ctx.font = `900 ${Math.round(half * 0.22)}px Lato, sans-serif`;
    ctx.fillText('MARGIE', x, y + half * 0.08);
  }
  ctx.restore();
}

function drawCallouts(t, alpha) {
  if (alpha <= 0) return;
  ctx.save();
  ctx.font = '700 12.5px Lato, Helvetica, Arial, sans-serif';
  ctx.textBaseline = 'middle';
  for (const c of callouts) {
    if (t < c.t0 || t > c.t1 || !VIS[c.j]) continue;
    const a = alpha * Math.min(smooth(prog(t, c.t0, 0.25)), 1 - smooth(prog(t, c.t1 - 0.25, 0.25)));
    if (a <= 0) continue;
    const x = SX[c.j], y = SY[c.j], tw = ctx.measureText(c.text).width, pw = tw + 18, ph = 24;
    let lx = x + 30, ly = c.below ? y + 38 : y - 38, right = true;
    if (lx + pw > VW - 8) { lx = x - 30 - pw; right = false; }
    if (ly - ph / 2 < 8) ly = y + 38;
    if (ly + ph / 2 > VH - 8) ly = y - 38;
    ctx.globalAlpha = a;
    ctx.strokeStyle = PAL.muted; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(right ? lx : lx + pw, ly); ctx.stroke();
    ctx.fillStyle = PAL.panel; ctx.strokeStyle = PAL.line;
    ctx.beginPath(); ctx.roundRect(lx, ly - ph / 2, pw, ph, 6); ctx.fill(); ctx.stroke();
    ctx.fillStyle = PAL.fg; ctx.textAlign = 'left';
    ctx.fillText(c.text, lx + 9, ly + 0.5);
    ctx.fillStyle = PAL.accent;
    ctx.beginPath(); ctx.arc(x, y, 2.5, 0, TAU); ctx.fill();
  }
  ctx.restore();
}

function render(t, now) {
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  // Transparent: the film sits on the page's own background.
  ctx.clearRect(0, 0, VW, VH);
  setView(t);
  const aA = 1 - smooth(prog(t, T.fade, DUR.fade));
  const aR = smooth(prog(t, T.fade - 0.1, DUR.fade));
  drawGlow(t, now);
  if (aA > 0.001) { computeAtoms(t); drawAtoms(t, aA); }
  if (aR > 0.001) drawHelix(t, aR);
  drawJunction(t);
  drawWordmark(t);
  if (aA > 0.001) drawCallouts(t, aA);
}

/**
 * Plays the film on `el` (its parent sets the size). Returns replay(), retheme() (after a theme
 * change) and destroy().
 * @param {HTMLCanvasElement} el
 * @param {{ logoSrc: string, dark?: () => boolean, still?: boolean, onEnd?: () => void }} options
 * @returns {{ replay(): void, retheme(): void, destroy(): void }}
 */
export function mount(el, { logoSrc, dark = () => false, still = false, onEnd = () => {} } = {}) {
  canvas = el;
  ctx = el.getContext('2d');
  stageEl = el.parentElement;
  isDark = dark;
  logo.src = logoSrc;
  readTheme();
  resize();
  let time = still ? T.end : 0, raf = 0, last = 0;
  const frame = () => render(time, performance.now());
  function tick(now) {
    time = Math.min(T.end, time + Math.min(0.05, (now - last) / 1000));
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
  // The wordmark appears in the last frame once the logo has loaded.
  logo.addEventListener('load', frame);
  if (still) frame();
  else play();
  return {
    replay() { time = 0; play(); },
    retheme() { readTheme(); frame(); },
    destroy() { cancelAnimationFrame(raf); ro.disconnect(); logo.removeEventListener('load', frame); }
  };
}
