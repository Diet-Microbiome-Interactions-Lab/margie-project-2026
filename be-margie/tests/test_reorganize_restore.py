"""A reorganized genome folder put back as the run made it, for a run that resumes it
(reorganize_outputs.restore_layout, the reverse of reorganize_one)."""
from pathlib import Path

from bioinformatics_tools.workflow_tools import reorganize_outputs as ro


def _tree(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob('*')) if p.is_file()}


def test_a_reorganized_folder_is_put_back_as_the_run_made_it(tmp_path):
    org = tmp_path / 'run' / 'gA--fa1:aaaaaaaa'
    for rel, text in {
        'cog/cog_results.tsv': 'cog', 'cog/cog_db.tkn': '', 'rasttk/rast.faa': '>a\nM\n',
        'scoring/FINAL_ANNOTATION_WITH_CONFIDENCE.tsv': 'final', 'scoring/figures/fig1.png': 'png',
        'labeling/labeled-genes.tsv': 'labels', 'FINAL_GENOME_VIEWER.html': 'viewer',
    }.items():
        (org / rel).parent.mkdir(parents=True, exist_ok=True)
        (org / rel).write_text(text)
    made = _tree(org)
    assert ro.reorganize_one(org)['error'] is None
    assert (org / ro.PTP / 'cog' / 'cog_results.tsv').is_file() and (org / 'diagrams' / 'fig1.png').is_file()

    result = ro.restore_layout(org)
    assert result['error'] is None
    assert _tree(org) == made
    assert not (org / ro.PTP).exists() and not (org / 'diagrams').exists()
    # Put back once: a second call moves nothing.
    assert ro.restore_layout(org)['actions'] == []
