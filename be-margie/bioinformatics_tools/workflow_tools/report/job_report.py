#!/usr/bin/env python3
"""job_report.py -- a MARGIE job's report, as one PDF.

The website sends what the Jobs page shows (model.json: the job, its summary and each step's
details, as the step popups give them) and the account's licence acceptances (licence.json). This
sets them out as numbered tables on A4 landscape pages, with the databases the results came from
(where each lives, its size, its genomes and genes, its dates and its copies in the backup folder)
and where the job's logs and records are kept.

Usage: job_report.py --work <folder with model.json, licence.json> --out <pdf>
"""
import argparse
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
# Fonts embedded as TrueType: sharp at any zoom, and the text can be searched and copied.
matplotlib.rcParams["pdf.fonttype"] = 42
# The font files' creation dates read as old; fontTools says so while embedding them.
logging.getLogger("fontTools").setLevel(logging.ERROR)
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.ft2font import FT2Font  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

# A4 landscape, in points.
PAGE_W, PAGE_H = 841.89, 595.28
M_L = M_R = 28.0
M_T, M_B = 26.0, 30.0
AVAIL_W = PAGE_W - M_L - M_R
# Type sizes (points) and single line spacing.
FS, FS_TITLE, FS_DOC, FS_FOOT = 7.2, 9.0, 15.0, 6.5
PITCH = 1.2
PAD_X, PAD_Y = 3.0, 1.4
HEAD_FILL = "#e6e6e6"
RULE = "#a6a6a6"
# A column is not made narrower than its longest word, up to this width.
WORD_MAX = 110.0

STATE_WORD = {"done": "done", "run": "running", "wait": "waiting", "failed": "failed",
              "partial": "partly done", "none": "not started", "na": "not chosen"}


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def when(value) -> str:
    """Formats an ISO time or epoch milliseconds as 'YYYY-MM-DD HH:MM UTC'; '' when empty."""
    if value in (None, "", 0):
        return ""
    try:
        if isinstance(value, (int, float)):
            t = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        else:
            t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, OSError, OverflowError):
        return str(value)


def stamp(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def span(seconds) -> str:
    """Formats seconds as '1 h 05 min', '4 min 10 s' or '12 s'; '' when unknown."""
    if seconds is None or seconds == "":
        return ""
    s = max(0, int(round(float(seconds))))
    if s >= 3600:
        return f"{s // 3600} h {s % 3600 // 60:02d} min"
    if s >= 60:
        return f"{s // 60} min {s % 60:02d} s"
    return f"{s} s"


def size(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    for unit, k in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= k:
            return f"{n / k:.1f} {unit}"
    return f"{int(n)} B"


# ------------------------------------------------------------------ type: a font and its widths

class Fonts:
    """Carlito (the metrics of Calibri), else Liberation Sans (those of Arial), else DejaVu Sans;
    widths from the font's own advances, so text is wrapped to the column it sits in."""

    def __init__(self):
        self.paths = None
        for family in ("Carlito", "Liberation Sans", "DejaVu Sans"):
            try:
                self.paths = {
                    bold: font_manager.findfont(font_manager.FontProperties(family=family, weight="bold" if bold else "normal"),
                                                fallback_to_default=False)
                    for bold in (False, True)}
                self.family = family
                break
            except Exception:  # noqa: BLE001 -- the next family is tried
                continue
        if self.paths is None:
            default = font_manager.findfont(font_manager.FontProperties())
            self.paths, self.family = {False: default, True: default}, "default"
        self.props = {b: font_manager.FontProperties(fname=p) for b, p in self.paths.items()}
        ft = FT2Font(self.paths[False])
        upm = ft.units_per_EM or 1000
        asc, desc = ft.ascender / upm, -ft.descender / upm
        # Baseline below the top of a line box, as a share of the type size.
        self.base = (PITCH - asc - desc) / 2 + asc
        self._ft: dict = {}
        self._w: dict = {}

    def width(self, s: str, pt: float, bold: bool = False) -> float:
        key = (bold, pt)
        cache = self._w.setdefault(key, {})
        ft = self._ft.get(key)
        if ft is None:
            ft = self._ft[key] = FT2Font(self.paths[bold])
            ft.set_size(pt, 72)
        total = 0.0
        for ch in s:
            w = cache.get(ch)
            if w is None:
                try:
                    w = ft.load_char(ord(ch)).linearHoriAdvance / 65536
                except Exception:  # noqa: BLE001 -- a glyph the font lacks
                    w = pt * 0.5
                cache[ch] = w
            total += w
        return total * 1.01

    def wrap(self, text, width: float, pt: float, bold: bool = False) -> list[str]:
        """Lines of `text` within `width` points: broken at spaces, and after / _ , ; | in paths
        and names; a piece wider than the column is cut by characters."""
        lines: list[str] = []
        space = self.width(" ", pt, bold)
        for para in str("" if text is None else text).split("\n"):
            line, lw = "", 0.0
            for p in re.findall(r"\s+|[^\s/_,;|]+[/_,;|]?|[/_,;|]", para):
                if p.isspace():
                    if line and not line.endswith(" "):
                        line, lw = line + " ", lw + space
                    continue
                pw = self.width(p, pt, bold)
                if lw + pw <= width:
                    line, lw = line + p, lw + pw
                    continue
                if line.strip():
                    lines.append(line.rstrip())
                while pw > width and len(p) > 1:
                    k = len(p) - 1
                    while k > 1 and self.width(p[:k], pt, bold) > width:
                        k -= 1
                    lines.append(p[:k])
                    p = p[k:]
                    pw = self.width(p, pt, bold)
                line, lw = p, pw
            lines.append(line.rstrip())
        return lines or [""]


# ------------------------------------------------------------------ pages: text, numbered tables

class Doc:
    """Pages of text and ruled tables, laid out top to bottom; tables continue on the next page
    with their number and title, and 'page i of n' when they take more than one."""

    def __init__(self, fonts: Fonts, footer: str):
        self.f = fonts
        self.footer = footer
        self.pages: list[list[tuple]] = [[]]
        self.y = M_T
        self.count = 0

    @property
    def bottom(self) -> float:
        return PAGE_H - M_B

    def new_page(self):
        self.pages.append([])
        self.y = M_T

    def _text(self, page: int, x: float, top: float, s: str, pt: float, bold: bool = False):
        self.pages[page].append(("t", x, top + pt * self.f.base, s, pt, bold))

    def heading(self, s: str, pt: float = FS_DOC, after: float = 3.0):
        if self.y + pt * PITCH > self.bottom:
            self.new_page()
        self._text(len(self.pages) - 1, M_L, self.y, s, pt, True)
        self.y += pt * PITCH + after

    def para(self, s: str, pt: float = FS, bold: bool = False, after: float = 4.0):
        for line in self.f.wrap(s, AVAIL_W, pt, bold):
            if self.y + pt * PITCH > self.bottom:
                self.new_page()
            self._text(len(self.pages) - 1, M_L, self.y, line, pt, bold)
            self.y += pt * PITCH
        self.y += after

    def table(self, title: str, about: str, headers: list[str], rows: list) -> int:
        """Adds a numbered table and returns its number. The header row is bold on light gray;
        the other rows are plain. A row given as a string is a group's name, in bold across the table."""
        self.count += 1
        number = self.count
        cells = [r if isinstance(r, str) else ["" if v is None else str(v) for v in r] for r in rows]
        cells = cells or [["(none)"] + [""] * (len(headers) - 1)]
        f, pad2, lh = self.f, 2 * PAD_X, FS * PITCH

        # Widths: each column's longest line when they fit side by side, the widest column taking the
        # room left; otherwise each column's longest word, and the room left shared out evenly, a
        # column taking no more than its longest line.
        natural, least = [], []
        for c, h in enumerate(headers):
            col = [(h, True)] + [(r[c], False) for r in cells if not isinstance(r, str)]
            natural.append(max(max(f.width(x, FS, b) for x in v.split("\n")) for v, b in col) + pad2)
            words = [(w, b) for v, b in col for w in re.split(r"[\s/_,;|]+", v) if w]
            least.append(min(max([f.width(w, FS, b) for w, b in words] or [0]) + pad2, WORD_MAX, natural[-1]))
        if sum(natural) <= AVAIL_W:
            widths = list(natural)
            widths[natural.index(max(natural))] += AVAIL_W - sum(natural)
        elif sum(least) >= AVAIL_W:
            widths = [w * AVAIL_W / sum(least) for w in least]
        else:
            widths, spare = list(least), AVAIL_W - sum(least)
            open_cols = sorted(range(len(headers)), key=lambda c: natural[c] - least[c])
            while open_cols and spare > 0.01:
                share = spare / len(open_cols)
                c = open_cols[0]
                give = min(natural[c] - widths[c], share)
                if give < share:
                    widths[c] += give
                    spare -= give
                    open_cols.pop(0)
                    continue
                for c in open_cols:
                    widths[c] += share
                spare = 0
        xs = [M_L]
        for w in widths:
            xs.append(xs[-1] + w)

        head = [f.wrap(h, widths[c] - pad2, FS, True) for c, h in enumerate(headers)]
        body = [f.wrap(r, AVAIL_W - pad2, FS, True) if isinstance(r, str) else [f.wrap(v, widths[c] - pad2, FS) for c, v in enumerate(r)]
                for r in cells]
        head_h = max(len(x) for x in head) * lh + 2 * PAD_Y
        row_h = [(len(r) if isinstance(cells[k], str) else max(len(x) for x in r)) * lh + 2 * PAD_Y for k, r in enumerate(body)]
        title_h = FS_TITLE * PITCH + 2.0
        about_lines = f.wrap(about, AVAIL_W, FS) if about else []
        about_h = len(about_lines) * lh + (2.0 if about_lines else 0)

        # Pages first, so each part's title can say 'page i of n'.
        parts, page, y, i, first = [], len(self.pages) - 1, self.y, 0, True
        while i < len(body):
            top = title_h + (about_h if first else 0) + head_h
            if y + top + row_h[i] > self.bottom and y > M_T + 0.5:
                page, y = page + 1, M_T
                continue
            y0, y = y, y + top
            take = []
            while i < len(body) and (y + row_h[i] <= self.bottom or not take):
                take.append(i)
                y += row_h[i]
                i += 1
            parts.append((page, y0, take, first))
            first = False
            if i < len(body):
                page, y = page + 1, M_T
        while len(self.pages) <= parts[-1][0]:
            self.pages.append([])

        for k, (page, y, take, first) in enumerate(parts):
            ops = self.pages[page]
            label = f"Table {number}: {title}" + (f" | page {k + 1} of {len(parts)}" if len(parts) > 1 else "")
            self._text(page, M_L, y, label, FS_TITLE, True)
            y += title_h
            if first:
                for line in about_lines:
                    self._text(page, M_L, y, line, FS)
                    y += lh
                y += 2.0 if about_lines else 0
            top = y
            ops.append(("r", M_L, y, AVAIL_W, head_h, HEAD_FILL))
            for c, lines in enumerate(head):
                for j, line in enumerate(lines):
                    self._text(page, xs[c] + PAD_X, y + PAD_Y + j * lh, line, FS, True)
            y += head_h
            ops.append(("l", M_L, y, M_L + AVAIL_W, y))
            # Column rules run down each stretch of ordinary rows; a group's row spans the table.
            run_top = y
            for r in take:
                if isinstance(cells[r], str):
                    for x in xs[1:-1]:
                        if y > run_top:
                            ops.append(("l", x, run_top, x, y))
                    for j, line in enumerate(body[r]):
                        self._text(page, M_L + PAD_X, y + PAD_Y + j * lh, line, FS, True)
                    y += row_h[r]
                    run_top = y
                else:
                    for c, lines in enumerate(body[r]):
                        for j, line in enumerate(lines):
                            if line:
                                self._text(page, xs[c] + PAD_X, y + PAD_Y + j * lh, line, FS)
                    y += row_h[r]
                ops.append(("l", M_L, y, M_L + AVAIL_W, y))
            ops.append(("l", M_L, top, M_L + AVAIL_W, top))
            for x in xs[1:-1]:
                ops.append(("l", x, top, x, top + head_h))
                if y > run_top:
                    ops.append(("l", x, run_top, x, y))
            for x in (xs[0], xs[-1]):
                ops.append(("l", x, top, x, y))
            self.y = y + 9.0
        return number

    def save(self, path: Path, title: str):
        n = len(self.pages)
        with PdfPages(path) as pdf:
            info = pdf.infodict()
            info["Title"] = title
            info["Creator"] = "MARGIE"
            for k, ops in enumerate(self.pages):
                fig = plt.figure(figsize=(PAGE_W / 72, PAGE_H / 72))
                right = f"Page {k + 1} of {n}"
                foot_top = PAGE_H - M_B + 12
                ops = ops + [("t", M_L, foot_top + FS_FOOT * self.f.base, self.footer, FS_FOOT, False),
                             ("t", PAGE_W - M_R - self.f.width(right, FS_FOOT), foot_top + FS_FOOT * self.f.base, right, FS_FOOT, False)]
                for op in ops:
                    if op[0] == "t":
                        _, x, base, s, pt, bold = op
                        fig.text(x / PAGE_W, 1 - base / PAGE_H, s, fontproperties=self.f.props[bold], fontsize=pt,
                                 color="black", ha="left", va="baseline", parse_math=False)
                    elif op[0] == "r":
                        _, x, y, w, h, fill = op
                        fig.add_artist(Rectangle((x / PAGE_W, 1 - (y + h) / PAGE_H), w / PAGE_W, h / PAGE_H,
                                                 transform=fig.transFigure, facecolor=fill, edgecolor="none", zorder=0))
                    else:
                        _, x1, y1, x2, y2 = op
                        fig.add_artist(Line2D([x1 / PAGE_W, x2 / PAGE_W], [1 - y1 / PAGE_H, 1 - y2 / PAGE_H],
                                              transform=fig.transFigure, color=RULE, linewidth=0.4, zorder=1))
                pdf.savefig(fig)
                plt.close(fig)


# ------------------------------------------------------------------ what the cluster holds

def where_it_lives(path: str) -> str:
    if path.startswith("/scratch/"):
        return ("Scratch storage on the cluster: fast working space, from which the cluster's purge policy "
                "removes files left unused for a long time")
    if path.startswith("/depot/"):
        return "The group's depot storage on the cluster"
    if path.startswith("/home/"):
        return "The account's home folder on the cluster"
    return "On the cluster"


def database_facts(path: str) -> dict:
    """Size, dates, genomes and genes of a MARGIE database, read without changing it."""
    facts: dict = {"path": path}
    try:
        st = os.stat(path)
    except OSError:
        facts["missing"] = True
        return facts
    facts["size"], facts["changed"] = st.st_size, st.st_mtime
    for attempt in range(6):
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=120)
            try:
                log(f"Counting the genomes and genes in {path}")
                # A genome loaded more than once has its rows more than once; each gene counts once.
                genes, genomes = db.execute(
                    "SELECT count(DISTINCT organism || '|' || feature_id), count(DISTINCT organism) FROM rasttk").fetchone()
                facts["genes"], facts["genomes"] = genes, genomes
                facts["first"], facts["latest"] = db.execute(
                    "SELECT min(loaded_at), max(loaded_at) FROM run_log WHERE status = 'success'").fetchone()
                facts["kept_first"], facts["kept_latest"] = db.execute(
                    "SELECT min(cached_at), max(cached_at) FROM output_cache_when").fetchone()
            finally:
                db.close()
            break
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc) and attempt < 5:
                log(f"{path} is busy (a run is writing to it); trying again")
                time.sleep(15)
                continue
            facts["error"] = str(exc)
            break
    return facts


def database_copies(backup_root: str, path: str) -> list[tuple[str, int, float]]:
    """Files in the backup folder (three levels down) that are copies of the database: the same
    name, without the account's prefix and version."""
    if not backup_root or not os.path.isdir(backup_root):
        return []
    core = re.sub(r"-v\d+$", "", Path(path).stem)
    core = re.sub(r"^[a-z0-9]+-(?=margie)", "", core)
    found = []
    for pattern in ("*.db", "*/*.db", "*/*/*.db", "*/*/*/*.db"):
        for p in Path(backup_root).glob(pattern):
            stem = re.sub(r"-v\d+$", "", p.stem)
            if core and (core in stem or stem in core):
                try:
                    st = p.stat()
                except OSError:
                    continue
                found.append((str(p), st.st_size, st.st_mtime))
    return sorted(set(found), key=lambda x: -x[2])


def folder_facts(folder: Path, pattern: str = "*") -> tuple[int, int, float]:
    """Files, bytes and the latest change under `folder`."""
    n = total = 0
    latest = 0.0
    if folder.is_dir():
        for p in folder.rglob(pattern):
            try:
                if p.is_file():
                    st = p.stat()
                    n += 1
                    total += st.st_size
                    latest = max(latest, st.st_mtime)
            except OSError:
                continue
    return n, total, latest


# ------------------------------------------------------------------ the report

def build(model: dict, licence: list[dict], out: Path) -> int:
    run = model.get("run") or {}
    summary = model.get("summary") or {}
    steps = model.get("steps") or []
    genomes = model.get("genomes") or []
    columns = model.get("columns") or []
    clock = model.get("clock") or []
    files = model.get("files") or {}
    run_dir = Path(run.get("outputDir") or ".")
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    label = run.get("label") or run.get("id") or "MARGIE job"

    started, finished = run.get("started"), run.get("finished")
    took = None
    try:
        a = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(finished).replace("Z", "+00:00")) if finished else datetime.now(timezone.utc)
        a = a if a.tzinfo else a.replace(tzinfo=timezone.utc)
        b = b if b.tzinfo else b.replace(tzinfo=timezone.utc)
        took = (b - a).total_seconds()
    except (TypeError, ValueError):
        pass

    fonts = Fonts()
    log(f"Type: {fonts.family}")
    doc = Doc(fonts, f"MARGIE job report | {label} | job {run.get('id', '')} | made {made}")
    doc.heading("MARGIE job report")
    doc.para(f"{label} | job {run.get('id', '')} | made {made}", pt=8.0, after=3.0)
    doc.para("This report sets out the job, where its results came from and the databases they came from, each genome "
             "and each step, the time the steps took, the licence acceptances, and where the job's logs and records are kept. "
             "A table that runs over more than one page gives its page in its title.", after=8.0)

    # The job, as the panel at the top of the Jobs page gives it.
    rows = [
        ["Job", label],
        ["Job id", run.get("id", "")],
        ["Status", run.get("status", "")],
        ["Command", run.get("command") or " ".join(run.get("args") or [])],
        ["Started", when(started)],
        ["Finished", when(finished) if finished else "running when the report was made"],
        ["Running time" if finished else "Running for", span(took)],
        ["Output folder", run.get("outputDir", "")],
        ["Genomes", str(summary.get("genomes", len(genomes)))],
        ["Steps done", f"{summary.get('done', '')} of {summary.get('all', '')} ({summary.get('overall', '')}%)"],
    ]
    if not finished and summary.get("left") is not None:
        rows.append(["Time left (estimate)", span(summary.get("left"))
                     + (f"; first runs here, timed once they have run: {', '.join(summary.get('untimed') or [])}" if summary.get("untimed") else "")])
    if run.get("reason"):
        rows.append(["Reason it stopped", run.get("reason")])
    if run.get("progressText"):
        rows.append(["Progress as the run reports it", run.get("progressText")])
    if run.get("tools"):
        rows.append(["Tools chosen", " | ".join(run.get("tools"))])
    rows.append(["This report", f"{out} (made {made})"])
    doc.table("The job", "The job as the panel at the top of the Jobs page gives it.", ["Item", "Value"], rows)

    # Where the results came from, counted.
    by_source: dict[str, tuple[int, set]] = {}
    for s in steps:
        key = " ".join(x for x in [s.get("source") or "not recorded", f"({s.get('level')} level)" if s.get("level") else ""] if x)
        n, gs = by_source.get(key, (0, set()))
        gs.add(s.get("genome"))
        by_source[key] = (n + 1, gs)
    doc.table("Where the results came from",
              "fresh: run in this job | restored: from a MARGIE database, at genome level (a whole genome run before) or "
              "protein level (proteins annotated before) | partly restored | kept: in the run folder from an earlier attempt.",
              ["Results came from", "Steps", "Genomes"],
              [[k, n, len(gs)] for k, (n, gs) in sorted(by_source.items(), key=lambda x: -x[1][0])])

    # The databases the restored results came from.
    used: dict[str, dict] = {}
    for s in steps:
        db = s.get("database") or ""
        if db:
            u = used.setdefault(db, {"steps": 0, "genomes": set(), "cached": []})
            u["steps"] += 1
            u["genomes"].add(s.get("genome"))
            if s.get("cachedAt"):
                u["cached"].append(str(s.get("cachedAt")))
    names = {db: f"Database {k + 1}" for k, db in enumerate(used)}
    if used:
        for db, u in used.items():
            facts = database_facts(db)
            copies = database_copies(model.get("backupRoot") or "", db)
            rows = [["Database file", db], ["Where it lives", where_it_lives(db)]]
            if facts.get("missing"):
                rows.append(["On the cluster now", "not found at this path when the report was made"])
            else:
                rows += [["Size", size(facts.get("size"))], ["Last changed", stamp(facts["changed"])]]
                if "error" in facts:
                    rows.append(["Genomes and genes", f"could not be read: {facts['error']}"])
                else:
                    rows += [["Genomes in its tables", f"{facts.get('genomes', 0):,}"],
                             ["Genes in its tables", f"{facts.get('genes', 0):,}"],
                             ["First genome loaded", when(facts.get("first"))],
                             ["Latest genome loaded", when(facts.get("latest"))]]
                    if facts.get("kept_latest"):
                        rows.append(["Results kept for reuse", f"between {when(facts.get('kept_first'))} and {when(facts.get('kept_latest'))}"])
            cached = sorted(u["cached"])
            rows.append(["Restored into this job", f"{u['steps']:,} steps for {len(u['genomes']):,} genomes"
                         + (f"; cached between {when(cached[0])} and {when(cached[-1])}" if cached else "")])
            if copies:
                rows += [["Copy in the backup folder" if len(copies) == 1 else f"Copy {k + 1} in the backup folder",
                          f"{p} | {size(n)} | {stamp(t)}"] for k, (p, n, t) in enumerate(copies)]
            else:
                rows.append(["Copies in the backup folder", f"none with this name in {model.get('backupRoot') or 'the backup folder'}"])
            doc.table(f"{names[db]}: where restored results came from",
                      "The database file, where it lives, what it holds and its copies: the file to recover if it is removed.",
                      ["Item", "Value"], rows)
    else:
        doc.para("Each step of this job ran here: no results were restored from a MARGIE database.", after=8.0)

    doc.table("Genomes", "Each genome's progress over the steps it runs.",
              ["Genome", "State", "Progress", "Steps done", "Running now"],
              [[g.get("genome"), g.get("state"), f"{g.get('pct', '')}%", f"{g.get('done', '')} of {g.get('of', '')}",
                " | ".join(g.get("running") or [])] for g in genomes])
    doc.table("Steps", "Each step across the genomes.",
              ["Step", "Done", "Failed", "Genomes", "Progress"],
              [[c.get("step"), c.get("done"), c.get("failed"), c.get("of"),
                "" if c.get("pct") is None else f"{c.get('pct')}%"] for c in columns])

    by_step: dict[str, list[float]] = {}
    for e in clock:
        if e.get("start") and e.get("last") and e.get("ok"):
            by_step.setdefault(str(e.get("tool")), []).append((e["last"] - e["start"]) / 1000)
    doc.table("Time taken by step", "Finished runs of each step: how many, and their shortest, median, longest and total time.",
              ["Step", "Finished", "Shortest", "Median", "Longest", "Total"],
              [[k, len(v), span(min(v)), span(sorted(v)[len(v) // 2]), span(max(v)), span(sum(v))]
               for k, v in sorted(by_step.items())])
    timed = sorted(clock, key=lambda e: (str(e.get("genome")), e.get("start") or 0))
    doc.table("Time taken by each genome's steps",
              "When each step started and was last seen running for each genome, from the job's tool clock.",
              ["Genome", "Step", "Started", "Ended (last seen)", "Took", "Outcome"],
              [[e.get("genome") or "(the whole run)", e.get("tool"), when(e.get("start")), when(e.get("last")),
                span(((e.get("last") or 0) - (e.get("start") or 0)) / 1000) if e.get("start") else "",
                "failed" if e.get("failed") else "finished" if e.get("ok") else "running or stopped"] for e in timed])

    detail_rows: list = []
    last_genome = None
    for s in sorted(steps, key=lambda s: str(s.get("genome"))):
        if s.get("genome") != last_genome:
            last_genome = s.get("genome")
            detail_rows.append(str(last_genome))
        jobs = " | ".join(f"{j.get('id')} {j.get('rule', '')} {j.get('status', '')}".strip() for j in (s.get("jobs") or []))
        store = s.get("file") or ""
        if store and s.get("fileSize"):
            store += f" ({size(s.get('fileSize'))})"
        came = [s.get("source") or "", f"{s.get('level')} level" if s.get("level") else "",
                names.get(s.get("database") or "", ""), s.get("detail") or ""]
        detail_rows.append([
            s.get("step"), s.get("say") or STATE_WORD.get(s.get("state"), s.get("state")),
            " | ".join(x for x in came if x), store, "yes" if s.get("loaded") else "", jobs,
            span(s.get("seconds")) if s.get("seconds") is not None else "",
        ])
    doc.table("Each step for each genome", "Each step's details as its popup on the Jobs page gives them, under its genome.",
              ["Step", "State", "Results came from", "Results file", "In the database", "SLURM jobs", "Time"],
              detail_rows)

    lic_rows = []
    for r in licence:
        try:
            items = json.loads(r.get("accepted_items") or "[]")
        except ValueError:
            items = [r.get("accepted_items")]
        try:
            tools = json.loads(r.get("licensed_tools") or "[]")
        except ValueError:
            tools = [r.get("licensed_tools")]
        lic_rows.append([when(r.get("accepted_at")), r.get("terms_version", ""), r.get("terms_sha256") or "",
                         r.get("usage_type") or "", " | ".join(map(str, tools or [])), " | ".join(map(str, items or []))])
    doc.table("Licence acceptances", "The licence terms this account accepted for MARGIE and its tools.",
              ["Accepted", "Terms version", "Terms SHA-256", "Use", "Tools licensed", "Items accepted"], lic_rows)

    # Where the job's logs and records are.
    log("Reading the job's folders")
    where_rows = []
    run_log = files.get("runLog") or ""
    if run_log and os.path.exists(run_log):
        st = os.stat(run_log)
        where_rows.append(["The job's log (as the Jobs page shows it)", run_log, 1, size(st.st_size), stamp(st.st_mtime)])
    for what, folder, pattern in (("Snakemake's logs", run_dir / ".snakemake" / "log", "*.log"),
                                  ("Each step's SLURM job logs", run_dir / ".snakemake" / "slurm_logs", "*"),
                                  ("The tools' own outputs, with their provenance records", run_dir / "original_container_outputs", "*")):
        n, total, latest = folder_facts(folder, pattern)
        if n:
            where_rows.append([what, str(folder), f"{n:,}", size(total), stamp(latest)])
    for what, name in (("Where each step's results came from", "cache-report.tsv"), ("The command the job ran", "run-command.sh")):
        p = run_dir / name
        if p.exists():
            st = p.stat()
            where_rows.append([what, str(p), 1, size(st.st_size), stamp(st.st_mtime)])
    doc.table("Where the job's logs and records are", "The files behind this report on the cluster.",
              ["What", "Where", "Files", "Size", "Last changed"], where_rows)

    prov: dict[str, set] = {}
    base = run_dir / "original_container_outputs"
    if base.is_dir():
        for p in base.rglob("*"):
            name = p.name.lower()
            if p.is_file() and ("pipeline" in name and "log" in name or "provenance" in name):
                parts = p.relative_to(base).parts
                if len(parts) >= 2:
                    prov.setdefault(parts[1], set()).add(parts[0])
    if prov:
        doc.table("The tools' provenance records",
                  "Each tool's container writes a record of the command, versions and databases it used, beside its output.",
                  ["Tool", "Genomes with a record", "Where"],
                  [[t, len(gs), f"{base}/<genome>/{t}/"] for t, gs in sorted(prov.items())])

    log(f"Writing {len(doc.pages)} pages")
    tmp = out.with_name(out.name + ".partial")
    doc.save(tmp, f"MARGIE job report | {label}")
    tmp.replace(out)
    return len(doc.pages)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    work, out = Path(a.work), Path(a.out)
    model = json.loads((work / "model.json").read_text())
    licence = json.loads((work / "licence.json").read_text()) if (work / "licence.json").exists() else []
    out.parent.mkdir(parents=True, exist_ok=True)
    pages = build(model, licence, out)
    log(f"Done: {out} ({pages} pages)")


if __name__ == "__main__":
    main()
