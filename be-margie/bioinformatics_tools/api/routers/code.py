"""The Python scripts behind MARGIE's own steps, under /v1/code (auth required), for the Code page.

The files are read from this server's installed copy of workflow_tools, the code a run executes,
so the page shows each script as it stands. Routes: GET / (the steps and their files),
GET /file?path=<path under workflow_tools> (one file's text).
"""
import ast
import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from bioinformatics_tools.api.auth import get_current_user

router = APIRouter(prefix="/v1/code", tags=["code"])

WORKFLOW_TOOLS = Path(__file__).resolve().parents[2] / "workflow_tools"

# The steps in run order (margie_sb.smk), each with its scripts in the order they run.
STEPS = [
    {
        "key": "consolidation",
        "title": "Consolidation",
        "what": "Merges each tool's table into one row per gene.",
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
]

_LISTED = {f for step in STEPS for f in step["files"]}


def _summary(text: str, path: str) -> str:
    """The first line of the module docstring, without a leading "<name> —" (or "-")."""
    try:
        doc = ast.get_docstring(ast.parse(text)) or ""
    except SyntaxError:
        return ""
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
