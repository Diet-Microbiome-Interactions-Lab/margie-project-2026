"""Databases a user put in the working folder themselves are used where they are (user_stores.own_copy,
adopt), and the folders a config leaves empty default to <scratch>/margie/margie-{input,output,databases}."""

import subprocess
from unittest.mock import patch

from bioinformatics_tools.api.services import user_stores as us

JOB_DB = us.STORE_BY_ID["job_db"]
OCC = us.STORE_BY_ID["occ"]
FP = us.STORE_BY_ID["fingerprint"]
POOL = us.STORE_BY_ID["genome_pool"]
ROOT = "/scratch/c/u/margie/margie-databases"


def test_the_base_database_dropped_at_the_top_is_found():
    f = us.own_copy(JOB_DB, "u", ROOT, ["margie-thesis-22-prokaryotes-base.db", "notes.txt"], [])
    assert f == {"path": f"{ROOT}/margie-thesis-22-prokaryotes-base.db", "how": "base", "version": 1}


def test_the_base_database_in_its_subfolder_is_found():
    f = us.own_copy(JOB_DB, "u", ROOT, ["sqlite/"], ["margie-thesis-22-prokaryotes-base.db"])
    assert f["path"] == f"{ROOT}/sqlite/margie-thesis-22-prokaryotes-base.db"


def test_margies_own_names_win_and_the_newest_is_taken():
    inside = ["u-margie-thesis-22-prokaryotes-base-v1.db", "u-margie-thesis-22-prokaryotes-base-v3.db",
              "u-margie-thesis-22-prokaryotes-base-v4.db.partial", "margie-thesis-22-prokaryotes-base.db"]
    f = us.own_copy(JOB_DB, "u", ROOT, [], inside)
    assert f == {"path": f"{ROOT}/sqlite/u-margie-thesis-22-prokaryotes-base-v3.db", "how": "named", "version": 3}


def test_someone_elses_copy_is_not_taken():
    assert us.own_copy(JOB_DB, "u", ROOT, [], ["other-margie-thesis-22-prokaryotes-base-v2.db"]) is None


def test_a_base_folder_copied_in_as_is_is_found_only_when_complete():
    assert us.own_copy(POOL, "u", ROOT, ["genome-pool/"], ["fna/", "faa/"])["how"] == "flat"
    assert us.own_copy(POOL, "u", ROOT, ["genome-pool/"], ["fna/"]) is None
    assert us.own_copy(FP, "u", ROOT, [], FP["base_files"][:-1]) is None
    assert us.own_copy(FP, "u", ROOT, [], FP["base_files"] + ["fingerprint-database.tsv.bak"])["path"] == f"{ROOT}/fingerprint-database"


def _check(found, out):
    with patch.object(us, "_run", return_value=(0, out)):
        us._check_own(None, found, {"job_db": "/depot/base.db"})
    return found


def test_a_finished_copy_of_the_same_size_is_ready():
    f = _check({"job_db": {"path": "/x.db", "how": "base", "version": 1}}, "10000\njob_db 500 1000\njob_db.base 500\n")
    assert f["job_db"]["ready"] and f["job_db"]["bytes"] == 500


def test_a_copy_still_changing_or_of_another_size_waits():
    f = _check({"job_db": {"path": "/x.db", "how": "base", "version": 1}}, "10000\njob_db 500 9990\njob_db.base 500\n")
    assert not f["job_db"]["ready"] and "still changing" in f["job_db"]["note"]
    f = _check({"job_db": {"path": "/x.db", "how": "base", "version": 1}}, "10000\njob_db 300 1000\njob_db.base 500\n")
    assert not f["job_db"]["ready"] and "size" in f["job_db"]["note"]


def test_folders_need_no_size_check():
    f = _check({"genome_pool": {"path": f"{ROOT}/genome-pool", "how": "flat", "version": 1}}, "")
    assert f["genome_pool"]["ready"]


def _adopt(tmp_path, store, found):
    """Runs adopt()'s commands in a real folder."""
    with patch.object(us, "_run", side_effect=lambda conn, cmd, timeout=60: (lambda r: (r.returncode, r.stdout + r.stderr))(
            subprocess.run(["bash", "-c", cmd], capture_output=True, text=True))):
        return us.adopt(None, store, found, str(tmp_path), "u")


def test_a_dropped_file_is_renamed_into_place_with_its_companions(tmp_path):
    (tmp_path / "occ_reference.pkl").write_text("ref")
    (tmp_path / "occ_reference.pkl.members.tsv").write_text("members")
    v = _adopt(tmp_path, OCC, {"path": str(tmp_path / "occ_reference.pkl"), "how": "base", "version": 1})
    dst = tmp_path / "operon-database" / "u-occ_reference-v1.pkl"
    assert v == 1 and dst.read_text() == "ref"
    assert (tmp_path / "operon-database" / "u-occ_reference-v1.pkl.members.tsv").read_text() == "members"
    assert not (tmp_path / "occ_reference.pkl").exists()


def test_a_folder_laid_flat_is_moved_into_its_own_folder(tmp_path):
    pool = tmp_path / "genome-pool"
    (pool / "fna").mkdir(parents=True)
    (pool / "faa").mkdir()
    (pool / "fna" / "a.fna").write_text(">a\n")
    (pool / "keep-me.txt").write_text("not the pool's")
    _adopt(tmp_path, POOL, {"path": str(pool), "how": "flat", "version": 1})
    assert (pool / "u-genome-pool-v1" / "fna" / "a.fna").exists() and (pool / "u-genome-pool-v1" / "faa").is_dir()
    assert (pool / "keep-me.txt").exists() and not (pool / "fna").exists()


def test_margies_own_name_is_used_as_is():
    with patch.object(us, "_run", side_effect=AssertionError("nothing to move")):
        assert us.adopt(None, JOB_DB, {"path": "/p", "how": "named", "version": 4}, ROOT, "u") == 4


def test_when_every_database_is_already_there_no_copy_job_runs():
    stores = [{"version": None, "found": {"path": f"/f/{s['id']}", "how": "named", "version": 2, "ready": True}} for s in us.STORES]
    wrote, ran = {}, []
    with patch.object(us, "status", return_value={"root": ROOT, "op": None, "stores": stores}), \
            patch.object(us, "_start", side_effect=AssertionError("no copy job")), \
            patch.object(us, "read_manifest", return_value={}), \
            patch.object(us, "_run", side_effect=lambda conn, cmd, timeout=60: ran.append(cmd) or (0, "")), \
            patch.object(us.ssh_sftp, "write_remote_text_file", side_effect=lambda path, text, connection: wrote.update({path: text})):
        us.start_setup(None, {}, "u")
    assert '"version": 2' in wrote[f"{ROOT}/.margie/stores.json"]
    assert wrote[f"{ROOT}/.margie/op.status"].startswith("state=done")


def test_only_what_is_missing_is_copied():
    stores = [{"version": None, "found": None} for _ in us.STORES]
    stores[0]["found"] = {"path": "/f", "how": "named", "version": 1, "ready": True}
    stores[1]["found"] = {"path": "/g", "how": "base", "version": 1, "ready": False, "note": "still changing"}
    got = {}
    with patch.object(us, "status", return_value={"root": ROOT, "op": None, "stores": stores}), \
            patch.object(us, "_start", side_effect=lambda conn, root, kind, plan, after, cfg: got.update(plan=plan, after=after)), \
            patch.object(us, "read_manifest", return_value={}), \
            patch.object(us, "_backups", return_value=[]), \
            patch.object(us, "resolve_base", side_effect=lambda conn, s, cfg: f"/depot/{s['base_rel']}"), \
            patch.object(us, "_size", return_value=1), \
            patch.object(us, "_run", return_value=(1, "")), \
            patch.object(us, "_write_manifest"):
        us.start_setup(None, {}, "u")
    assert us.STORES[0]["id"] not in got["after"]["versions"]
    assert us.STORES[1]["id"] in got["after"]["versions"]


def test_empty_folders_get_their_defaults_and_set_ones_stay():
    ran = []
    cfg = {"margie_sb": {"input_path": "", "output_path": "/scratch/c/u/my-results"}}
    with patch.object(us, "_run", side_effect=lambda conn, cmd, timeout=60: ran.append(cmd) or (0, "c u" if "hostname" in cmd else "")):
        assert us.fill_default_folders(None, cfg)
    # No group folder here: the containers and reference databases get sif and reference-databases/db in the working folder.
    assert cfg["margie_sb"] == {"input_path": "/scratch/c/u/margie/margie-input", "output_path": "/scratch/c/u/my-results",
                                "working_folder": "/scratch/c/u/margie", "sif_path": "/scratch/c/u/margie/sif",
                                "db_root": "/scratch/c/u/margie/reference-databases/db"}
    assert all(f"/scratch/c/u/margie/{d}" in ran[-1] for d in ("margie-input", "margie-databases", "sif", "reference-databases/db"))
    with patch.object(us, "_run", side_effect=AssertionError("nothing to do")):
        assert not us.fill_default_folders(None, cfg)


def test_the_databases_folder_defaults_under_margie():
    with patch.object(us, "_run", return_value=(0, "c u")):
        assert us.scratch_root(None, {}) == "/scratch/c/u/margie/margie-databases"
    assert us.scratch_root(None, {"margie_sb": {"stores_root": "/mine/"}}) == "/mine"


def test_a_chosen_working_folder_holds_the_empty_folders():
    cfg = {"margie_sb": {"working_folder": "/scratch/c/u/thesis/", "input_path": "", "output_path": ""}}
    with patch.object(us, "_run", return_value=(0, "")):
        assert us.fill_default_folders(None, cfg)
    assert cfg["margie_sb"]["input_path"] == "/scratch/c/u/thesis/margie-input"
    assert cfg["margie_sb"]["output_path"] == "/scratch/c/u/thesis/margie-output"
    assert us.scratch_root(None, cfg) == "/scratch/c/u/thesis/margie-databases"


def test_empty_container_and_reference_folders_take_the_groups_where_the_account_reads_them():
    shared = {"sif_path": "/group/sif", "db_root": "/group/databases/reference-database-for-annotation/db"}
    cfg = {"margie_sb": {"working_folder": "/w", "input_path": "/w/in", "output_path": "/w/out", "sif_path": "", "db_root": "/mine/db"}}
    ran = []
    with patch.object(us, "SHARED_FOLDER_DEFAULTS", shared), \
         patch.object(us, "_run", side_effect=lambda conn, cmd, timeout=60: ran.append(cmd) or (0, "0" if "-r" in cmd else "")):
        assert us.fill_default_folders(None, cfg)
    assert cfg["margie_sb"]["sif_path"] == "/group/sif" and cfg["margie_sb"]["db_root"] == "/mine/db"
    assert "/group/sif" not in ran[-1]  # the group's folder is read, not made


def test_a_group_folder_the_account_cannot_read_leaves_sif_and_db_in_the_working_folder():
    shared = {"sif_path": "/group/sif", "db_root": "/group/db"}
    cfg = {"margie_sb": {"working_folder": "/w", "input_path": "/w/in", "output_path": "/w/out"}}
    with patch.object(us, "SHARED_FOLDER_DEFAULTS", shared), patch.object(us, "_run", return_value=(0, "")):
        assert us.fill_default_folders(None, cfg)
    assert cfg["margie_sb"]["sif_path"] == "/w/sif" and cfg["margie_sb"]["db_root"] == "/w/reference-databases/db"


def test_the_install_list_joins_folders_with_one_slash():
    from bioinformatics_tools.api.services import tool_assets
    rows = tool_assets.inventory({"margie_sb": {"sif_path": "/", "db_root": "/refs/"}}, "/home/u")
    paths = [r["path"] for r in rows] + [r["shared"] for r in rows]
    assert not [x for x in paths if "//" in x]
    assert "/refs/gtdbtk" in paths and "/gtdbtk.sif" in paths


# ---- by extension: any .db or .pkl the user put there, under any name ----

def test_a_database_under_any_name_is_found_by_its_extension_newest_first():
    f = us.own_copy(JOB_DB, "u", ROOT, [], ["lab-genomes.db", "older.db", "notes.txt"])
    assert f == {"path": f"{ROOT}/sqlite/lab-genomes.db", "how": "ext", "version": 1}
    assert us.own_copy(JOB_DB, "u", ROOT, ["sqlite/", "mine.db"], [])["path"] == f"{ROOT}/mine.db"
    assert us.own_copy(OCC, "u", ROOT, [], ["mine.pkl", "mine.pkl.members.tsv"])["path"] == f"{ROOT}/operon-database/mine.pkl"


def test_margies_names_and_the_base_name_come_before_the_extension():
    assert us.own_copy(JOB_DB, "u", ROOT, [], ["lab.db", "u-margie-thesis-22-prokaryotes-base-v2.db"])["how"] == "named"
    assert us.own_copy(JOB_DB, "u", ROOT, [], ["lab.db", "margie-thesis-22-prokaryotes-base.db"])["how"] == "base"


def test_journals_hidden_files_folders_and_other_extensions_are_not_taken():
    assert us.own_copy(JOB_DB, "u", ROOT, [], ["x.db-journal", ".hidden.db", "snapshots/", "x.pkl", ".db"]) is None


def test_a_copy_found_by_extension_needs_no_size_match_with_the_groups():
    f = _check({"job_db": {"path": "/x.db", "how": "ext", "version": 1}}, "10000\njob_db 300 1000\njob_db.base 500\n")
    assert f["job_db"]["ready"]


def test_a_copy_found_by_extension_is_renamed_into_place(tmp_path):
    (tmp_path / "lab.db").write_text("db")
    v = _adopt(tmp_path, JOB_DB, {"path": str(tmp_path / "lab.db"), "how": "ext", "version": 1})
    assert v == 1 and (tmp_path / "sqlite" / "u-margie-thesis-22-prokaryotes-base-v1.db").read_text() == "db"
    assert not (tmp_path / "lab.db").exists()


def test_without_a_group_folder_no_path_counts_as_the_labs():
    from bioinformatics_tools.api.services import tool_assets
    with patch.object(us, "DEPOT", ""):
        assert not tool_assets._in_lab("/scratch/c/u/margie/sif")
    with patch.object(us, "DEPOT", "/shared/lab/margie"):
        assert tool_assets._in_lab("/shared/lab/margie/sif") and not tool_assets._in_lab("/shared/lab/margie-old")


# ---- margie-build that comes with the server ----

def test_the_servers_margie_build_goes_in_without_its_history_or_lab_notes(tmp_path, monkeypatch):
    import io
    import tarfile
    from bioinformatics_tools.api.services import tool_assets
    b = tmp_path / "margie-build"
    (b / ".git").mkdir(parents=True)
    (b / ".git" / "config").write_text("x")
    (b / "build.sh").write_text("#!/bin/bash\n")
    (b / "README.md").write_text("lab notes")
    (b / "build-containers").mkdir()
    (b / "build-containers" / "README.md").write_text("lab notes")
    (b / "build-containers" / "build-all.sh").write_text("x")
    monkeypatch.setattr(tool_assets, "BUILD_BUNDLE", str(b))
    assert tool_assets.bundled()
    names = tarfile.open(fileobj=io.BytesIO(tool_assets._bundle_tar())).getnames()
    assert "margie-build/build.sh" in names and "margie-build/build-containers/build-all.sh" in names
    assert not [n for n in names if ".git" in n or n.endswith("README.md")]
    monkeypatch.setattr(tool_assets, "BUILD_BUNDLE", "")
    assert not tool_assets.bundled()


def test_a_folder_of_the_users_own_is_not_replaced(monkeypatch, tmp_path):
    from bioinformatics_tools.api.services import tool_assets
    (tmp_path / "build.sh").write_text("x")
    monkeypatch.setattr(tool_assets, "BUILD_BUNDLE", str(tmp_path))
    with patch.object(tool_assets, "_run", return_value=(1, "")):
        try:
            tool_assets.install_bundle(None, {}, "/home/u")
            assert False, "replaced a folder MARGIE did not make"
        except us.StoreError as e:
            assert "did not make it" in str(e)


def test_builds_outside_the_group_keep_their_records_and_group_their_own():
    from bioinformatics_tools.api.services import tool_assets
    with patch.object(us, "DEPOT", "/shared/lab/margie"), patch.object(us, "_run", return_value=(0, "")):
        env = tool_assets.build_env(None, {"margie_sb": {"working_folder": "/scratch/c/u/margie"}})
    assert env == [["env", "MARGIE_RECORDS_DIR", "/scratch/c/u/margie/licensing-records"], ["env", "MARGIE_OPERATOR", "@user"],
                   ["env", "MARGIE_SHARED_GROUP", "@group"]]
    with patch.object(us, "DEPOT", "/shared/lab/margie"), patch.object(us, "_run", return_value=(0, "0")):
        assert tool_assets.build_env(None, {}) == []
