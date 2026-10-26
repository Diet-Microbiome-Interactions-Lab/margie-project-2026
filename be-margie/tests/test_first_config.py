"""A first visit: a missing config.yaml stays missing, so Settings offers the default config."""

from unittest.mock import patch

from bioinformatics_tools.api.services import read_cache
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

SSH = "bioinformatics_tools.api.routers.ssh"


@patch(f"{SSH}._build_connection")
def test_a_missing_config_is_read_as_empty_and_not_written(_conn, authed_client):  # noqa: F811
    read_cache.drop(FAKE_USER["user_id"])
    with patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={}), \
         patch(f"{SSH}.user_stores.fill_default_folders") as fill, \
         patch(f"{SSH}.ssh_sftp.write_remote_yaml") as write:
        assert authed_client.get("/v1/ssh/config").json() == {}
    fill.assert_not_called()
    write.assert_not_called()


@patch(f"{SSH}._build_connection")
def test_an_existing_config_gets_its_empty_folders_filled(_conn, authed_client):  # noqa: F811
    read_cache.drop(FAKE_USER["user_id"])
    with patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={"margie_sb": {"threads": 4}}), \
         patch(f"{SSH}.user_stores.fill_default_folders", return_value=True), \
         patch(f"{SSH}.user_stores.fill_default_partition", return_value=False), \
         patch(f"{SSH}.ssh_sftp.write_remote_yaml") as write:
        authed_client.get("/v1/ssh/config")
    write.assert_called_once()


# ---- first-time setup: the working folder first, the rest in it ----

def _cluster(conn, cmd, timeout=60):
    """The cluster's answers: its name and user, and no group folder this account reads."""
    return (0, "c u") if "hostname" in cmd else (0, "")


@patch(f"{SSH}._build_connection")
def test_setup_suggests_the_working_folder_and_the_folders_in_it(_conn, authed_client):  # noqa: F811
    read_cache.drop(FAKE_USER["user_id"])
    with patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={}), \
         patch(f"{SSH}.user_stores._run", side_effect=_cluster), \
         patch(f"{SSH}.tool_assets.build_recipes", return_value={"path": None, "source": None, "clone_to": "/home/u/margie-build", "url": ""}):
        d = authed_client.get("/v1/ssh/setup").json()
    assert d["configured"] is False and d["working_folder"] == "" and d["default"] == "/scratch/c/u/margie"
    assert d["folders"] == {"input": "/scratch/c/u/margie/margie-input", "output": "/scratch/c/u/margie/margie-output",
                            "databases": "/scratch/c/u/margie/margie-databases", "containers": "/scratch/c/u/margie/sif",
                            "references": "/scratch/c/u/margie/reference-databases/db"}
    assert d["build"]["path"] == "" and d["build"]["clone_to"] == "/home/u/margie-build"


@patch(f"{SSH}._build_connection")
def test_setting_the_working_folder_writes_the_config_and_makes_the_folders(_conn, authed_client):  # noqa: F811
    read_cache.drop(FAKE_USER["user_id"])
    ran = []
    written = {}
    with patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={}), \
         patch(f"{SSH}.user_stores._run", side_effect=lambda conn, cmd, timeout=60: ran.append(cmd) or _cluster(conn, cmd)), \
         patch(f"{SSH}.user_stores.fill_default_partition", return_value=False), \
         patch(f"{SSH}.tool_assets.build_recipes", return_value={"path": None, "source": None, "clone_to": "/h/margie-build", "url": ""}), \
         patch(f"{SSH}.ssh_sftp.write_remote_yaml", side_effect=lambda path, cfg, connection: written.update(cfg)):
        r = authed_client.post("/v1/ssh/setup/working-folder", json={})
    assert r.status_code == 200, r.text
    sb = written["margie_sb"]
    assert sb["working_folder"] == "/scratch/c/u/margie"
    assert sb["input_path"] == "/scratch/c/u/margie/margie-input" and sb["output_path"] == "/scratch/c/u/margie/margie-output"
    assert sb["sif_path"] == "/scratch/c/u/margie/sif" and sb["db_root"] == "/scratch/c/u/margie/reference-databases/db"
    made = " ".join(c for c in ran if c.startswith("mkdir"))
    assert all(f"/scratch/c/u/margie/{d}" in made for d in ("margie-input", "margie-output", "margie-databases", "sif", "reference-databases/db"))
    assert r.json()["working_folder"] == "/scratch/c/u/margie"


@patch(f"{SSH}._build_connection")
def test_a_new_working_folder_takes_its_folders_along_and_leaves_those_set_apart(_conn, authed_client):  # noqa: F811
    read_cache.drop(FAKE_USER["user_id"])
    old = {"margie_sb": {"working_folder": "/scratch/c/u/margie", "input_path": "/scratch/c/u/margie/margie-input",
                         "output_path": "/data/my-results", "stores_root": "/scratch/c/u/margie/margie-databases",
                         "sif_path": "/scratch/c/u/margie/sif", "db_root": "/scratch/c/u/margie/db"}}
    written = {}
    with patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value=old), \
         patch(f"{SSH}.user_stores._run", side_effect=lambda conn, cmd, timeout=60: (0, "c u" if "hostname" in cmd else "w")), \
         patch(f"{SSH}.tool_assets._run", return_value=(0, "w")), \
         patch(f"{SSH}.user_stores.fill_default_partition", return_value=False), \
         patch(f"{SSH}.tool_assets.build_recipes", return_value={"path": "/h/margie-build", "source": "yours", "clone_to": "/h/margie-build", "url": ""}), \
         patch(f"{SSH}.ssh_sftp.write_remote_yaml", side_effect=lambda path, cfg, connection: written.update(cfg)):
        r = authed_client.post("/v1/ssh/setup/working-folder", json={"path": "/scratch/c/u/lab-run"})
    assert r.status_code == 200, r.text
    sb = written["margie_sb"]
    assert sb["working_folder"] == "/scratch/c/u/lab-run"
    assert sb["input_path"] == "/scratch/c/u/lab-run/margie-input" and sb["stores_root"] == "/scratch/c/u/lab-run/margie-databases"
    # Set apart from the working folder, and the containers and reference databases (hours to set up), stay.
    assert sb["output_path"] == "/data/my-results"
    assert sb["sif_path"] == "/scratch/c/u/margie/sif" and sb["db_root"] == "/scratch/c/u/margie/db"


# ---- the group's folders: named only to an account that reads them ----

GROUP = "/shared/lab/margie"


@patch(f"{SSH}._build_connection")
def test_an_account_outside_the_group_sees_none_of_its_paths_and_its_own_suggestions(_conn, authed_client, monkeypatch):  # noqa: F811
    from bioinformatics_tools.api.services import user_stores
    read_cache.drop(FAKE_USER["user_id"])
    monkeypatch.setattr(user_stores, "DEPOT", GROUP)
    monkeypatch.setattr(user_stores, "GROUP_PATTERN", "/shared/{account}/margie")
    cfg = {"compute": {"cluster_default": {"account": "otherlab"}}, "margie_sb": {"working_folder": "/scratch/c/u/margie"}}
    params = [{"param": "margie_sb.sif_path", "default": f"{GROUP}/sif", "type": "path"},
              {"param": "margie_sb.shared_root", "default": GROUP, "type": "path"},
              {"param": "margie_sb.threads", "default": 4, "type": "int"}]
    with patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value=cfg), \
         patch(f"{SSH}.user_stores._run", return_value=(0, "")), \
         patch(f"{SSH}._get_available_workflows", return_value=[{"id": "margie_sb", "configurable_params": params}]):
        got = {p["param"]: p for p in authed_client.get("/v1/ssh/workflows").json()[0]["configurable_params"]}
    assert got["margie_sb.sif_path"]["default"] == "" and got["margie_sb.sif_path"]["placeholder"] == "/scratch/c/u/margie/sif"
    assert got["margie_sb.shared_root"]["default"] == "" and got["margie_sb.shared_root"]["placeholder"] == "/shared/otherlab/margie"
    assert got["margie_sb.threads"]["default"] == 4
    assert GROUP not in str(got)


@patch(f"{SSH}._build_connection")
def test_a_member_of_the_group_keeps_its_folders_as_defaults(_conn, authed_client, monkeypatch):  # noqa: F811
    from bioinformatics_tools.api.services import user_stores
    read_cache.drop(FAKE_USER["user_id"])
    monkeypatch.setattr(user_stores, "DEPOT", GROUP)
    params = [{"param": "margie_sb.sif_path", "default": f"{GROUP}/sif", "type": "path"},
              {"param": "margie_sb.fingerprint_database.path", "default": "", "type": "path"}]
    cfg = {"margie_sb": {"working_folder": "/scratch/c/u/margie"}}
    with patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value=cfg), \
         patch(f"{SSH}.user_stores._run", return_value=(0, "0")), \
         patch(f"{SSH}._get_available_workflows", return_value=[{"id": "margie_sb", "configurable_params": params}]):
        got = authed_client.get("/v1/ssh/workflows").json()[0]["configurable_params"]
    assert got[0]["default"] == f"{GROUP}/sif" and "placeholder" not in got[0]
    # The databases folder's settings show where the first setup puts them.
    assert got[1]["placeholder"] == (f"/scratch/c/u/margie/margie-databases/fingerprint-database/"
                                     f"{FAKE_USER['cluster_username']}-fingerprint-database-v1/fingerprint-database.tsv")


def test_a_new_config_outside_the_group_carries_none_of_its_paths(monkeypatch):
    from bioinformatics_tools.api.routers import ssh
    from bioinformatics_tools.api.services import user_stores
    monkeypatch.setattr(user_stores, "DEPOT", GROUP)
    cfg = {"margie_sb": {"shared_root": GROUP, "backup_root": f"{GROUP}/databases/x", "threads": 4}, "main_database": "~/m.db"}
    assert ssh._without_group(cfg) == {"margie_sb": {"shared_root": "", "backup_root": "", "threads": 4}, "main_database": "~/m.db"}
    assert user_stores.suggested_group({"compute": {"cluster_default": {"account": "a; rm -rf"}}}) == ""
