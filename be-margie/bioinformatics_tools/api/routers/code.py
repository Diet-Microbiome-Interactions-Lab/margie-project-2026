"""The Python scripts behind MARGIE's own steps, under /v1/code (auth required), for the Code and FAQ pages.

The files are read from this server's installed copy of workflow_tools, the code a run executes,
so the pages show each script as it stands. Routes: GET / (the steps and their files),
GET /file?path=<path under workflow_tools> (one file's text), GET /snippet?path=&symbol= (one
function, class, constant or Snakemake rule of a file, with its line numbers, for the FAQ).
"""
import ast
import hashlib
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from bioinformatics_tools.api.auth import get_current_user

router = APIRouter(prefix="/v1/code", tags=["code"])

WORKFLOW_TOOLS = Path(__file__).resolve().parents[2] / "workflow_tools"

# The steps in run order (margie_sb.smk), each with its scripts in the order they run.
STEPS = [
    {
        "key": "workflow",
        "title": "The workflow",
        "what": "The Snakemake workflow, rule by rule, with each step's inputs, outputs and container; the tools and "
                "phases MARGIE knows; and the helpers that set each genome's paths and gene caller (RASTtk, or "
                "Prodigal for a genome new to MARGIE).",
        "files": ["margie_sb.smk", "workflow_registry.py", "workflow_helpers.py"],
    },
    {
        "key": "hashes",
        "title": "Genome, protein and gene hashes",
        "what": "Recognises each genome, protein and gene by a hash of its sequence, restores what was annotated "
                "before and records each protein's results once, linked to the genomes it occurs in.",
        "files": ["genome_identity.py", "output_cache.py", "protein_cache.py"],
    },
    {
        "key": "loading",
        "title": "Loading into the MARGIE database",
        "what": "Loads each step's table with each row's genome hash. A reload replaces the genome's rows; "
                "RASTtk-based results replace Prodigal-based ones, and Prodigal-based results leave RASTtk-based ones.",
        "files": ["load_to_db.py"],
    },
    {
        "key": "localisation",
        "title": "Envelope and localisation",
        "what": "Adds the genome's envelope call (phase 7) to the localisation tools' tables, and turns SignalP 6.0's "
                "output into a results table.",
        "files": ["enrich_with_envelope.py", "process_signalp6.py"],
    },
    {
        "key": "consolidation",
        "title": "Consolidation",
        "what": "Merges each tool's table into one row per gene, on the genes of the genome's gene caller.",
        "files": ["consolidation/detect-columns.py", "consolidation/merge-all-columns.py",
                  "consolidation/filter-no-stat.py", "consolidation/_shared.py"],
    },
    {
        "key": "labeling",
        "title": "Labeling",
        "what": "Gives each gene one label, with its EC consensus, operon context and tool agreement.",
        "files": ["labeling/assign-canonical-label.py", "labeling/add-ec-consensus.py",
                  "labeling/add-operon-info.py", "labeling/add-cluster-agreement.py"],
    },
    {
        "key": "operon-database",
        "title": "Operon database",
        "what": "Adds each genome to the OCC reference, the operon contexts C3 scores against.",
        "files": ["scoring/update-occ-reference-depot.py", "scoring/c3_occ.py", "scoring/c3_lib.py"],
    },
    {
        "key": "scoring",
        "title": "Scoring",
        "what": "Scores each label: hierarchy and confidence tiers, C1 to C4, and the final 0-1 confidence.",
        "files": ["scoring/score-hierarchy-tier.py", "scoring/score-confidence-tier.py",
                  "scoring/score-c1-tool-coverage.py", "scoring/score-c2-operon-probability.py",
                  "scoring/c3_score_organism.py", "scoring/score-c4-ec-agreement.py",
                  "scoring/score-confidence-final.py", "scoring/make-final-annotation-with-confidence.py"],
    },
    {
        "key": "fingerprinting",
        "title": "Fingerprinting",
        "what": "Fingerprints each gene and operon and writes the final annotated tables, GFF and workbook.",
        "files": ["fingerprint/add-gene-fingerprint.py", "fingerprint/add-operon-fingerprint.py",
                  "fingerprint/add-fingerprint-to-final.py", "fingerprint/make-final-annotated.py",
                  "fingerprint/make-final-excel.py", "scoring/make-gff.py"],
    },
    {
        "key": "fingerprint-databases",
        "title": "Fingerprint databases",
        "what": "Merges each genome's gene and operon fingerprints into the shared databases.",
        "files": ["fingerprint/update-fingerprint-database.py",
                  "fingerprint/update-operon-fingerprint-database.py"],
    },
    {
        "key": "genome-map",
        "title": "Genome map and diagrams",
        "what": "Draws each genome's interactive map (gene, operon or review mode; circular or linear; one or two strands), "
                "its circular figure and its operon diagrams.",
        "files": ["viz/gen_genome_viewer.py", "viz/make_circular_genome.py",
                  "scoring/analysis/report_figures/make_complete_operon_diagrams.py"],
    },
    {
        "key": "reports",
        "title": "Reports",
        "what": "Builds each genome's report figures and tables and the report across genomes, and checks their numbers "
                "against the scoring outputs.",
        "files": ["scoring/analysis/report_figures/make_organism_report.py",
                  "scoring/analysis/report_figures/make_global_report.py",
                  "scoring/analysis/report_figures/reportfig_lib.py",
                  "scoring/analysis/report_figures/verify_report.py"],
    },
    {
        "key": "run-records",
        "title": "A run's folders and records",
        "what": "Says where each step's results came from (the cache report), leaves each genome's folder with its final "
                "files on top and the step folders under per-tool-phased-output/, and writes a job's PDF report.",
        "files": ["cache_report.py", "reorganize_outputs.py", "report/job_report.py"],
    },
]

_LISTED = {f for step in STEPS for f in step["files"]}

# Further files the FAQ quotes from: the pipeline's own bookkeeping. The API, its cluster access
# and the run driver are left out.
SNIPPET_FILES = _LISTED | {
    "margie_sb.smk", "workflow_registry.py", "workflow_helpers.py", "genome_identity.py",
    "protein_cache.py", "output_cache.py", "cache_report.py", "load_to_db.py", "license_gate.py",
    "reorganize_outputs.py", "enrich_with_envelope.py", "process_signalp6.py",
}
_RULE_START = re.compile(r"^(?:rule|checkpoint) (\w+):")


def _summary(text: str, path: str) -> str:
    """The first line of the module docstring (a Snakefile's first triple-quoted string), without a
    leading "<name> —" (or "-")."""
    try:
        doc = ast.get_docstring(ast.parse(text)) or ""
    except SyntaxError:
        m = re.search(r'"""(.*?)"""', text, re.S)
        doc = m.group(1) if m else ""
    first = doc.strip().splitlines()[0] if doc.strip() else ""
    name = Path(path).name
    for sep in (" — ", " - ", " -- "):
        if first.startswith(name + sep):
            first = first[len(name) + len(sep):]
    return first[:1].upper() + first[1:]


def _read(path: str) -> str:
    if path not in _LISTED:
        raise HTTPException(status_code=404, detail="That file is not one the Code page shows.")
    try:
        return (WORKFLOW_TOOLS / path).read_text(encoding="utf-8")
    except OSError:
        raise HTTPException(status_code=404, detail=f"{path} is not on this server.")


def _with_comments(lines: list[str], start: int) -> int:
    """The first line of the comment block directly above line `start` (1-based), or `start`."""
    while start > 1 and lines[start - 2].lstrip().startswith("#"):
        start -= 1
    return start


def snippet(text: str, path: str, symbol: str) -> tuple[int, int] | None:
    """The 1-based first and last lines of `symbol` in `text`: a top-level function, class or
    assignment, or "rule:<name>" in a .smk file; None when it is not there."""
    lines = text.splitlines()
    if path.endswith(".smk"):
        # A rule, or a top-level def or assignment, runs to the next line at the left margin.
        if symbol.startswith("rule:"):
            name = symbol[len("rule:"):]
            starts = lambda line: (m := _RULE_START.match(line)) is not None and m.group(1) == name  # noqa: E731
        else:
            head = re.compile(rf"^(?:def {re.escape(symbol)}\(|{re.escape(symbol)}\s*=)")
            starts = lambda line: head.match(line) is not None  # noqa: E731
        for i, line in enumerate(lines):
            if starts(line):
                end = i + 1
                while end < len(lines) and (not lines[end].strip() or lines[end][0] in " \t)]}"):
                    end += 1
                while end > i + 1 and not lines[end - 1].strip():
                    end -= 1
                return _with_comments(lines, i + 1), end
        return None
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
            first = min([node.lineno] + [d.lineno for d in node.decorator_list])
            return _with_comments(lines, first), node.end_lineno
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == symbol for t in targets):
            return _with_comments(lines, node.lineno), node.end_lineno
    return None


@router.get("")
def list_code(current_user: dict = Depends(get_current_user)):
    """The steps and their scripts, with each file's size, line count and docstring summary."""
    steps = []
    for step in STEPS:
        files = []
        for path in step["files"]:
            try:
                text = (WORKFLOW_TOOLS / path).read_text(encoding="utf-8")
            except OSError:
                continue
            files.append({"path": path, "name": Path(path).name, "lines": len(text.splitlines()),
                          "bytes": len(text.encode("utf-8")), "summary": _summary(text, path)})
        steps.append({**{k: step[k] for k in ("key", "title", "what")}, "files": files})
    return {"steps": steps}


@router.get("/file")
def read_code(path: str = Query(..., max_length=200), current_user: dict = Depends(get_current_user)):
    """One listed script's text, as installed, with its SHA-256."""
    text = _read(path)
    return {"path": path, "name": Path(path).name, "text": text, "lines": len(text.splitlines()),
            "bytes": len(text.encode("utf-8")), "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


@router.get("/snippet")
def read_snippet(path: str = Query(..., max_length=200), symbol: str = Query(..., max_length=120),
                 current_user: dict = Depends(get_current_user)):
    """One function, class, constant or rule of a quoted file, as installed, with its line numbers."""
    if path not in SNIPPET_FILES:
        raise HTTPException(status_code=404, detail="That file is not one the FAQ quotes.")
    try:
        text = (WORKFLOW_TOOLS / path).read_text(encoding="utf-8")
    except OSError:
        raise HTTPException(status_code=404, detail=f"{path} is not on this server.")
    span = snippet(text, path, symbol)
    if span is None:
        raise HTTPException(status_code=404, detail=f"{symbol} is not in {path}.")
    start, end = span
    return {"path": path, "name": Path(path).name, "symbol": symbol, "start": start, "end": end,
            "text": "\n".join(text.splitlines()[start - 1:end]) + "\n", "file_lines": len(text.splitlines()),
            "listed": path in _LISTED}
