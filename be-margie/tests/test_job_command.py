"""The command a job ran: kept beside its results as a script to run again, and served to the Jobs page."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from bioinformatics_tools.api.routers.ssh import _command_script, _dane_wf_command
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

ENV = [("MARGIE_LICENSE_ACCEPTED", "2026.1"), ("MARGIE_USAGE_TYPE", "academic"), ("MARGIE_LICENSED_TOOLS", "pfam")]


def test_the_command_line_is_unchanged():
    """What dane_wf receives is the same one line as before the script was kept."""
    assert _dane_wf_command("margie_sb", "/in", "/out/1", "rasttk,pfam", resume=True, license_env="A='1' ") == (
        "A='1' ~/bioinformatics-tools/.venv/bin/dane_wf margie sb input: /in output_dir: /out/1"
        " margie_sb.selected_tools: rasttk,pfam margie_sb.resume: true"
    )


def test_the_script_runs_from_the_code_folder_one_argument_to_a_line():
    text = _command_script("job-1", "margie_sb", "/in", "/out/1", "rasttk,pfam", resume=True, env=ENV)
    lines = text.splitlines()
    assert lines[0] == "#!/usr/bin/env bash"
    assert "cd ~/bioinformatics-tools" in lines
    assert ".venv/bin/dane_wf margie sb \\" in lines
    assert "  input: /in \\" in lines
    assert lines[-1] == "  margie_sb.resume: true"
    # Every line of the command but the last continues it.
    start = lines.index("MARGIE_LICENSE_ACCEPTED='2026.1' \\")
    assert all(ln.endswith(" \\") for ln in lines[start:-1])


def test_the_script_is_valid_bash():
    text = _command_script("job-1", "margie_sb", "/in", "/out/1", None, env=ENV)
    assert subprocess.run(["bash", "-n"], input=text, text=True).returncode == 0


JOB = {"user_id": 1, "work_dir": "/out/1", "genome_path": "/in", "workflow": "margie_sb", "selected_tools": "pfam"}


@patch("bioinformatics_tools.api.routers.ssh._build_connection", return_value=MagicMock())
@patch("bioinformatics_tools.api.routers.ssh._load_job_for_action", return_value=JOB)
@patch("bioinformatics_tools.api.routers.ssh._read_small_remote", return_value="#!/usr/bin/env bash\ncd ~/bioinformatics-tools\n")
def test_the_kept_script_is_served(_read, _load, _conn, authed_client):  # noqa: F811
    d = authed_client.get("/v1/ssh/job_command/job-1").json()
    assert d["exact"] is True
    assert d["file"] == "/out/1/run-command.sh"
    assert "cd ~/bioinformatics-tools" in d["script"]


@patch("bioinformatics_tools.api.routers.ssh._build_connection", return_value=MagicMock())
@patch("bioinformatics_tools.api.routers.ssh._load_job_for_action", return_value=JOB)
@patch("bioinformatics_tools.api.routers.ssh._read_small_remote", side_effect=FileNotFoundError)
def test_an_older_job_gets_its_command_rebuilt(_read, _load, _conn, authed_client):  # noqa: F811
    d = authed_client.get("/v1/ssh/job_command/job-1").json()
    assert d["exact"] is False
    assert "  input: /in \\" in d["script"]
    assert "licence settings it ran with were not kept" in d["script"]
