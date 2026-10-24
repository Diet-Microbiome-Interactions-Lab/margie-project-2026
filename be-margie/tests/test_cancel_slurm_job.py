"""Resources → Your jobs → Cancel: one of the user's own SLURM jobs is cancelled with scancel; a
MARGIE run's driver job is cancelled as its run, so the run is recorded as cancelled."""

from unittest.mock import patch

from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

SSH = "bioinformatics_tools.api.routers.ssh"


@patch(f"{SSH}._build_connection")
def test_a_job_id_must_look_like_one(_conn, authed_client):  # noqa: F811
    with patch(f"{SSH}._run_remote_check") as run:
        for bad in ("12;rm -rf ~", "abc", "12 13", "-1"):
            assert authed_client.post(f"/v1/ssh/cancel_slurm_job/{bad}").status_code in (400, 404)
    run.assert_not_called()


@patch(f"{SSH}._build_connection")
def test_a_job_outside_the_users_queue_is_left_alone(_conn, authed_client):  # noqa: F811
    with patch(f"{SSH}._run_remote_check", return_value=(0, "")) as run, \
         patch(f"{SSH}.ssh_slurm.cancel_slurm_jobs") as cancel:
        r = authed_client.post("/v1/ssh/cancel_slurm_job/4242")
    assert r.status_code == 404 and "4242" in r.json()["detail"]
    assert "-u testuser" in run.call_args[0][1] and "-j 4242" in run.call_args[0][1]
    cancel.assert_not_called()


@patch(f"{SSH}._build_connection")
def test_the_users_job_is_cancelled(_conn, authed_client):  # noqa: F811
    with patch(f"{SSH}._run_remote_check", return_value=(0, "4242")), \
         patch(f"{SSH}.job_store.going_for", return_value=[]), \
         patch(f"{SSH}.ssh_slurm.cancel_slurm_jobs") as cancel, \
         patch(f"{SSH}.read_cache.drop") as drop:
        r = authed_client.post("/v1/ssh/cancel_slurm_job/4242_3")
    assert r.json() == {"cancelled": "4242_3", "run": None}
    assert cancel.call_args[0][0] == ["4242_3"]
    drop.assert_called_with(FAKE_USER["user_id"], "cluster")


@patch(f"{SSH}._build_connection")
def test_a_runs_driver_job_is_cancelled_as_the_run(_conn, authed_client):  # noqa: F811
    with patch(f"{SSH}._run_remote_check", return_value=(0, "777")), \
         patch(f"{SSH}.job_store.going_for", return_value=["run-a", "run-b"]), \
         patch(f"{SSH}.ssh_slurm.driver_job_id", side_effect=lambda run, connection: {"run-a": "555", "run-b": "777"}[run]), \
         patch(f"{SSH}.cancel_job") as cancel_run, \
         patch(f"{SSH}.ssh_slurm.cancel_slurm_jobs") as cancel:
        r = authed_client.post("/v1/ssh/cancel_slurm_job/777")
    assert r.json() == {"cancelled": "777", "run": "run-b"}
    assert cancel_run.call_args[0][0] == "run-b"
    cancel.assert_not_called()
