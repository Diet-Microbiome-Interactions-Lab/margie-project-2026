"""Every store and output folder a run uses is pointed into the working folder (user_stores.point_config),
including a key still naming an earlier working folder, which runs would otherwise keep writing to."""

from unittest.mock import patch

from bioinformatics_tools.api.services import user_stores as us

ROOT = "/scratch/c/u/margie/margie-databases"
OLD = "/scratch/c/u/margie-2026"
MANIFEST = {s["id"]: {"version": 1} for s in us.STORES}


def _point(cfg):
    with patch.object(us, "read_manifest", return_value=MANIFEST):
        return us.point_config(None, cfg, "u", ROOT)


def test_keys_left_on_an_earlier_working_folder_are_brought_here():
    cfg = {
        "main_database": f"{OLD}/sqlite/u-margie-thesis-22-prokaryotes-base-v1.db",
        "margie_sb": {
            "final_tables_depot": {"path": f"{OLD}/final-tables"},
            "scoring_results_historical": {"path": f"{OLD}/scoring-archive"},
            "sqlite_pipeline_snapshot": {"path": f"{OLD}/sqlite/snapshots"},
        },
    }
    assert _point(cfg)
    assert cfg["main_database"] == f"{ROOT}/sqlite/u-margie-thesis-22-prokaryotes-base-v1.db"
    assert cfg["margie_sb"]["final_tables_depot"]["path"] == f"{ROOT}/final-tables"
    assert cfg["margie_sb"]["scoring_results_historical"]["path"] == f"{ROOT}/scoring-archive"
    assert cfg["margie_sb"]["sqlite_pipeline_snapshot"]["path"] == f"{ROOT}/sqlite/snapshots"
    assert cfg["margie_sb"]["operon_database"]["occ_reference_pkl"] == f"{ROOT}/operon-database/u-occ_reference-v1.pkl"
    assert cfg["margie_sb"]["fingerprint_database"]["path"] == (
        f"{ROOT}/fingerprint-database/u-fingerprint-database-v1/fingerprint-database.tsv")
    assert cfg["margie_sb"]["stores_root"] == ROOT


def test_nothing_changes_once_everything_is_here():
    cfg = {}
    assert _point(cfg)
    assert not _point(cfg)
