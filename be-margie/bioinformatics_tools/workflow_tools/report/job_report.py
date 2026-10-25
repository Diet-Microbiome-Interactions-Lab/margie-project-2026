#!/usr/bin/env python3
"""job_report.py -- a MARGIE job's report, zipped into its run folder.

The website sends what the Jobs page shows (model.json: the job, its summary and each step's
details, as the step popups give them), the job's log and the licence acceptances. This writes a
PDF of tables from them and zips it with:
  * the job's log and Snakemake's own logs (.snakemake/log, .snakemake/slurm_logs)
  * each tool's provenance record (original_container_outputs/**/*pipeline*log*.txt)
  * the run's cache report (cache-report.tsv)
  * the licence acceptances (licence.json)

Usage: job_report.py --run-dir <run> --work <folder with model.json, job-log.txt, licence.json> --out <zip>
"""
import argparse
import json
import textwrap
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

PAGE = (11.69, 8.27)  # A4 landscape, inches
INK = "#222222"
MUTED = "#666666"
HEAD = "#e9ecef"
STRIPE = "#f6f7f8"
# Lines of table text a page holds; rows split across pages by their wrapped height.
LINES_PER_PAGE = 30
# Logs larger than this in total are listed in the report and left out of the zip.
LOG_LIMIT = 400 * 1024 * 1024

STATE_WORD = {"done": "done", "run": "running", "wait": "waiting", "failed": "failed",
              "partial": "partly done", "none": "not started", "na": "not chosen"}


def when(value) -> str:
    """Formats an ISO time or epoch milliseconds as 'YYYY-MM-DD HH:MM:SS UTC'; '' when empty."""
    if value in (None, "", 0):
        return ""
    try:
        if isinstance(value, (int, float)):
            t = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        else:
            t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, OSError, OverflowError):
        return str(value)


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


def mb(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    return f"{n / 1e6:.1f} MB" if n >= 1e5 else f"{n / 1e3:.1f} KB"


def wrap(text, width: int) -> str:
    return "\n".join(textwrap.wrap(str(text or ""), width=width, break_long_words=True)) or ""


def page_title(fig, title: str, sub: str = ""):
    fig.text(0.04, 0.95, title, fontsize=15, fontweight="bold", color=INK, va="top")
    if sub:
        fig.text(0.04, 0.91, sub, fontsize=9.5, color=MUTED, va="top")


def table_pages(pdf, title: str, sub: str, headers: list[str], rows: list[list], widths: list[int], note: str = ""):
    """Writes rows as a ruled table over as many pages as they need; widths are wrap widths in characters."""
    if not rows:
        rows = [["(none)"] + [""] * (len(headers) - 1)]
    total = sum(widths)
    col_w = [w / total for w in widths]
    # Wrapped a little inside each column, as characters vary in width.
    wrapped = [[wrap(v, max(4, int(w * 0.85))) for v, w in zip(r, widths)] for r in rows]
    # Pages by wrapped height: each takes rows until its lines are used up.
    chunks, chunk, used = [], [], 0
    for row in wrapped:
        h = max(1, max(str(c).count("\n") + 1 for c in row))
        if chunk and used + h > LINES_PER_PAGE:
            chunks.append(chunk)
            chunk, used = [], 0
        chunk.append(row)
        used += h
    chunks.append(chunk)
    for k, cells in enumerate(chunks):
        fig = plt.figure(figsize=PAGE)
        page_title(fig, title, sub + (f"  |  page {k + 1} of {len(chunks)}" if len(chunks) > 1 else ""))
        ax = fig.add_axes([0.04, 0.06, 0.92, 0.82])
        ax.axis("off")
        t = ax.table(cellText=cells, colLabels=headers, colWidths=col_w, loc="upper left", cellLoc="left", colLoc="left")
        t.auto_set_font_size(False)
        t.set_fontsize(7.4)
        line_h = 0.026
        heights = [max(1, max(str(c).count("\n") + 1 for c in row)) for row in cells]
        for (r, c), cell in t.get_celld().items():
            cell.set_edgecolor("#cfd4d9")
            cell.set_linewidth(0.5)
            if r == 0:
                cell.set_facecolor(HEAD)
                cell.set_text_props(fontweight="bold", color=INK)
                cell.set_height(line_h * 1.3)
            else:
                cell.set_height(line_h * heights[r - 1] + 0.006)
                cell.set_facecolor(STRIPE if r % 2 == 0 else "white")
                cell.set_text_props(color=INK)
        if note and k == len(chunks) - 1:
            fig.text(0.04, 0.03, wrap(note, 210), fontsize=7.6, color=MUTED, va="bottom")
        pdf.savefig(fig)
        plt.close(fig)


def text_page(pdf, title: str, paragraphs: list[str]):
    fig = plt.figure(figsize=PAGE)
    page_title(fig, title)
    y = 0.86
    for p in paragraphs:
        block = wrap(p, 150)
        fig.text(0.04, y, block, fontsize=9.2, color=INK, va="top", linespacing=1.45)
        y -= 0.034 * (block.count("\n") + 1) + 0.022
    pdf.savefig(fig)
    plt.close(fig)


def build_pdf(path: Path, model: dict, licence: list[dict], included: dict):
    run = model.get("run") or {}
    summary = model.get("summary") or {}
    steps = model.get("steps") or []
    genomes = model.get("genomes") or []
    columns = model.get("columns") or []
    clock = model.get("clock") or []
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    started, finished = run.get("started"), run.get("finished")
    took = None
    try:
        a = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(finished).replace("Z", "+00:00")) if finished else datetime.now(timezone.utc)
        if a.tzinfo is None:
            a = a.replace(tzinfo=timezone.utc)
        if b.tzinfo is None:
            b = b.replace(tzinfo=timezone.utc)
        took = (b - a).total_seconds()
    except (TypeError, ValueError):
        pass
    label = run.get("label") or run.get("id") or "MARGIE job"
    with PdfPages(path) as pdf:
        # Summary: the job as the Jobs page's panel shows it.
        rows = [
            ["Job", label],
            ["Job id", run.get("id", "")],
            ["Status", run.get("status", "")],
            ["Command", run.get("command") or " ".join(run.get("args") or [])],
            ["Started", when(started)],
            ["Finished", when(finished) if finished else "still running when the report was made"],
            ["Running time" if finished else "Running for", span(took)],
            ["Output folder", run.get("outputDir", "")],
            ["Genomes", str(summary.get("genomes", len(genomes)))],
            ["Steps done", f"{summary.get('done', '')} of {summary.get('all', '')} ({summary.get('overall', '')}%)"],
        ]
        if not finished and summary.get("left") is not None:
            rows.append(["Time left (estimate)", span(summary.get("left")) + (f"; first runs here: {', '.join(summary.get('untimed') or [])}" if summary.get("untimed") else "")])
        if run.get("reason"):
            rows.append(["Reason it stopped", run.get("reason")])
        if run.get("progressText"):
            rows.append(["Progress as the run reports it", run.get("progressText")])
        rows.append(["Report made", made])
        table_pages(pdf, "MARGIE job report", label, ["Item", "Value"], rows, [28, 150],
                    note="The tables that follow give each genome's progress, each step across the genomes, the time each step took, "
                         "each step's details as its popup on the Jobs page gives them, and the licence acceptances. The zip beside this "
                         "report holds the logs, the tools' provenance records and the cache report.")
        # Genomes.
        table_pages(pdf, "Genomes", "Each genome's progress over the steps it runs",
                    ["Genome", "State", "Progress", "Steps done", "Running now"],
                    [[g.get("genome"), g.get("state"), f"{g.get('pct', '')}%", f"{g.get('done', '')} of {g.get('of', '')}",
                      " | ".join(g.get("running") or [])] for g in genomes],
                    [60, 14, 10, 12, 50])
        # Steps across genomes.
        table_pages(pdf, "Steps", "Each step across the genomes",
                    ["Step", "Done", "Failed", "Genomes", "Progress"],
                    [[c.get("step"), c.get("done"), c.get("failed"), c.get("of"),
                      "" if c.get("pct") is None else f"{c.get('pct')}%"] for c in columns],
                    [40, 12, 12, 12, 12])
        # Time each step took, from the job's tool clock.
        timed = sorted(clock, key=lambda e: (str(e.get("genome")), e.get("start") or 0))
        table_pages(pdf, "Time taken", "When each step started and ended for each genome, from the job's tool clock",
                    ["Genome", "Step", "Started", "Ended (last seen)", "Took", "Outcome"],
                    [[e.get("genome") or "(the whole run)", e.get("tool"), when(e.get("start")), when(e.get("last")),
                      span(((e.get("last") or 0) - (e.get("start") or 0)) / 1000) if e.get("start") else "",
                      "failed" if e.get("failed") else "finished" if e.get("ok") else "running or stopped"] for e in timed],
                    [52, 18, 24, 24, 14, 18])
        # Totals by step.
        by_step: dict[str, list[float]] = {}
        for e in clock:
            if e.get("start") and e.get("last") and e.get("ok"):
                by_step.setdefault(str(e.get("tool")), []).append((e["last"] - e["start"]) / 1000)
        table_pages(pdf, "Time taken by step", "Finished runs of each step: how many, and their typical and total time",
                    ["Step", "Finished", "Shortest", "Median", "Longest", "Total"],
                    [[k, len(v), span(min(v)), span(sorted(v)[len(v) // 2]), span(max(v)), span(sum(v))]
                     for k, v in sorted(by_step.items())],
                    [30, 12, 16, 16, 16, 16])
        # Each step's details, as its popup gives them.
        detail_rows = []
        for s in steps:
            jobs = " | ".join(f"{j.get('id')} {j.get('status', '')}".strip() for j in (s.get("jobs") or []))
            store = s.get("file") or ""
            if store and s.get("fileSize"):
                store += f" ({mb(s.get('fileSize'))})"
            detail_rows.append([
                s.get("genome"), s.get("step"), STATE_WORD.get(s.get("state"), s.get("state")), s.get("say", ""),
                " ".join(x for x in [s.get("source", ""), f"({s.get('level')} level)" if s.get("level") else "", s.get("detail", "")] if x),
                store, "yes" if s.get("loaded") else "", jobs,
                span(s.get("seconds")) if s.get("seconds") is not None else "",
            ])
        table_pages(pdf, "Step details", "Each step for each genome, as its popup on the Jobs page gives it",
                    ["Genome", "Step", "State", "Detail", "Results came from", "Results file", "In database", "SLURM jobs", "Time"],
                    detail_rows, [30, 14, 10, 32, 30, 22, 11, 20, 10])
        # Licence acceptances.
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
            lic_rows.append([when(r.get("accepted_at")), r.get("terms_version", ""), (r.get("terms_sha256") or "")[:16],
                             r.get("usage_type") or "", " | ".join(map(str, tools or [])), " | ".join(map(str, items or []))])
        table_pages(pdf, "Licence acceptances", "The licence terms this account accepted for MARGIE and its tools",
                    ["Accepted", "Terms version", "Terms SHA-256 (start)", "Use", "Tools licensed", "Items accepted"],
                    lic_rows, [22, 12, 18, 12, 30, 60])
        # What is in the zip, and how to read the tables.
        text_page(pdf, "About this report", [
            "States: done | running | waiting | failed | partly done | not started | not chosen (a step this run left out).",
            "Results came from: fresh (run in this job) | restored (from the MARGIE database, at genome level for a whole genome "
            "run before, or protein level for proteins annotated before) | partly restored | kept (already in the run folder from an earlier attempt).",
            "Time taken comes from the job's tool clock: the start of a step and the last time it was seen running.",
            "In the zip: " + "; ".join(f"{k}: {v}" for k, v in included.items()) + ".",
        ])


def add_tree(zf: zipfile.ZipFile, base: Path, files, prefix: str) -> int:
    n = 0
    for f in files:
        try:
            zf.write(f, f"{prefix}/{f.relative_to(base)}")
            n += 1
        except (OSError, ValueError):
            continue
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run_dir, work, out = Path(a.run_dir), Path(a.work), Path(a.out)
    model = json.loads((work / "model.json").read_text())
    licence = json.loads((work / "licence.json").read_text()) if (work / "licence.json").exists() else []

    snake_logs = sorted((run_dir / ".snakemake" / "log").glob("*.log"))
    slurm_logs = sorted(p for p in (run_dir / ".snakemake" / "slurm_logs").rglob("*") if p.is_file())
    provenance = sorted(p for p in (run_dir / "original_container_outputs").rglob("*")
                        if p.is_file() and ("pipeline" in p.name.lower() and "log" in p.name.lower() or "provenance" in p.name.lower()))
    log_bytes = sum(p.stat().st_size for p in snake_logs + slurm_logs)
    included = {
        "MARGIE-job-report.pdf": "these tables",
        "job.json": "the data behind them",
        "logs/job-log.txt": "the job's log as the Jobs page shows it",
        "logs/snakemake": f"{len(snake_logs)} Snakemake log(s)",
        "logs/slurm": f"{len(slurm_logs)} SLURM job log(s)" if log_bytes <= LOG_LIMIT else "left out: the logs pass 400 MB; they stay in the run folder",
        "provenance": f"{len(provenance)} provenance record(s) from the tools' containers",
        "cache-report.tsv": "where each step's results came from",
        "licence/acceptances.json": "the licence acceptances",
    }

    pdf_path = work / "MARGIE-job-report.pdf"
    build_pdf(pdf_path, model, licence, included)

    tmp = out.with_suffix(".zip.partial")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(pdf_path, "MARGIE-job-report.pdf")
        zf.writestr("job.json", json.dumps(model, indent=2))
        if (work / "job-log.txt").exists():
            zf.write(work / "job-log.txt", "logs/job-log.txt")
        add_tree(zf, run_dir / ".snakemake" / "log", snake_logs, "logs/snakemake")
        if log_bytes <= LOG_LIMIT:
            add_tree(zf, run_dir / ".snakemake" / "slurm_logs", slurm_logs, "logs/slurm")
        add_tree(zf, run_dir / "original_container_outputs", provenance, "provenance")
        if (run_dir / "cache-report.tsv").exists():
            zf.write(run_dir / "cache-report.tsv", "cache-report.tsv")
        zf.writestr("licence/acceptances.json", json.dumps(licence, indent=2))
        zf.writestr("README.txt", "MARGIE job report\n\n" + "\n".join(f"{k}: {v}" for k, v in included.items()) + "\n")
    tmp.replace(out)
    print(out)


if __name__ == "__main__":
    main()
