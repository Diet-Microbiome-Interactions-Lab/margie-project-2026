"""Who may use this MARGIE (api/access.py): accounts only on the clusters it accepts
(MARGIE_ALLOWED_CLUSTERS), and repeated failed sign-ins or sign-ups locked out for a while."""

from unittest.mock import MagicMock, patch

import pytest

from bioinformatics_tools.api import access
from tests.test_api import client, test_rsa_key  # noqa: F401 (fixtures)

AUTH = "bioinformatics_tools.api.routers.auth"
REG = {"username": "u1", "password": "S3cur3P@ss!", "cluster_username": "u1"}


def _ssh(home: str = "/home/u1"):
    """A stand-in cluster that answers every command like a quiet shell printing home."""
    out, err = MagicMock(), MagicMock()
    out.read.return_value = home.encode() + b"\n"
    out.channel.recv_exit_status.return_value = 0
    err.read.return_value = b""
    ssh = MagicMock()
    ssh.exec_command.return_value = (MagicMock(), out, err)
    conn = MagicMock()
    conn.connect.return_value = ssh
    return conn


@pytest.mark.parametrize("host, ok", [
    ("login01.hpc.example.edu", True),
    ("u1@login02.hpc.example.edu", True),
    ("LOGIN03.HPC.EXAMPLE.EDU.", True),
    ("login01.hpc.example.edu:22", True),
    ("hpc.example.edu", False),
    ("login01.hpc.example.edu.evil.org", False),
    ("10.0.0.5", False),
    ("", False),
])
def test_cluster_patterns(monkeypatch, host, ok):
    monkeypatch.setenv(access.ENV, "*.hpc.example.edu")
    assert access.cluster_allowed(host) is ok


def test_with_no_list_any_cluster_is_accepted():
    assert access.allowed_clusters() == [] and access.cluster_allowed("anything.example.org")


def test_the_sign_in_page_learns_which_clusters(client, monkeypatch):  # noqa: F811
    assert client.get("/v1/auth/policy").json() == {"clusters": []}
    monkeypatch.setenv(access.ENV, "*.hpc.example.edu, other.example.org")
    assert client.get("/v1/auth/policy").json() == {"clusters": ["*.hpc.example.edu", "other.example.org"]}


def test_sign_up_on_another_cluster_is_refused_before_any_login(client, monkeypatch, test_rsa_key):  # noqa: F811
    monkeypatch.setenv(access.ENV, "*.hpc.example.edu")
    with patch(f"{AUTH}.make_user_connection") as make:
        r = client.post("/v1/auth/register", json={**REG, "cluster_host": "my.own.server", "private_key": test_rsa_key})
    assert r.status_code == 403 and "*.hpc.example.edu" in r.json()["detail"]
    make.assert_not_called()


def test_sign_up_and_sign_in_on_an_accepted_cluster(client, monkeypatch, test_rsa_key):  # noqa: F811
    monkeypatch.setenv(access.ENV, "*.hpc.example.edu")
    with patch(f"{AUTH}.make_user_connection", return_value=_ssh()), patch(f"{AUTH}.ensure_remote_dane_wf"):
        r = client.post("/v1/auth/register", json={**REG, "cluster_host": "login01.hpc.example.edu", "private_key": test_rsa_key})
    assert r.status_code == 201
    assert client.post("/v1/auth/login", json={"username": "u1", "password": REG["password"]}).status_code == 200


def test_an_account_on_a_cluster_no_longer_accepted_cannot_sign_in(client, monkeypatch, test_rsa_key):  # noqa: F811
    with patch(f"{AUTH}.make_user_connection", return_value=_ssh()), patch(f"{AUTH}.ensure_remote_dane_wf"):
        client.post("/v1/auth/register", json={**REG, "cluster_host": "old.cluster.org", "private_key": test_rsa_key})
    monkeypatch.setenv(access.ENV, "*.hpc.example.edu")
    r = client.post("/v1/auth/login", json={"username": "u1", "password": REG["password"]})
    assert r.status_code == 403


def test_moving_an_account_to_another_cluster_is_refused(client, monkeypatch, test_rsa_key):  # noqa: F811
    monkeypatch.setenv(access.ENV, "*.hpc.example.edu")
    with patch(f"{AUTH}.make_user_connection", return_value=_ssh()), patch(f"{AUTH}.ensure_remote_dane_wf"):
        client.post("/v1/auth/register", json={**REG, "cluster_host": "login01.hpc.example.edu", "private_key": test_rsa_key})
    token = client.post("/v1/auth/login", json={"username": "u1", "password": REG["password"]}).json()["access_token"]
    with patch(f"{AUTH}.make_user_connection") as make:
        r = client.put("/v1/auth/update-credentials", json={"cluster_host": "my.own.server"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    make.assert_not_called()


def test_five_wrong_passwords_lock_the_name_even_for_the_right_one(client, monkeypatch, test_rsa_key):  # noqa: F811
    with patch(f"{AUTH}.make_user_connection", return_value=_ssh()), patch(f"{AUTH}.ensure_remote_dane_wf"):
        client.post("/v1/auth/register", json={**REG, "cluster_host": "login01.hpc.example.edu", "private_key": test_rsa_key})
    for _ in range(5):
        assert client.post("/v1/auth/login", json={"username": "u1", "password": "nope"}).status_code == 401
    r = client.post("/v1/auth/login", json={"username": "U1 ", "password": REG["password"]})
    assert r.status_code == 429 and "Try again in 15 minutes" in r.json()["detail"] and int(r.headers["retry-after"]) > 800


def test_a_good_sign_in_clears_the_count(client, test_rsa_key):  # noqa: F811
    with patch(f"{AUTH}.make_user_connection", return_value=_ssh()), patch(f"{AUTH}.ensure_remote_dane_wf"):
        client.post("/v1/auth/register", json={**REG, "cluster_host": "login01.hpc.example.edu", "private_key": test_rsa_key})
    for _ in range(4):
        client.post("/v1/auth/login", json={"username": "u1", "password": "nope"})
    assert client.post("/v1/auth/login", json={"username": "u1", "password": REG["password"]}).status_code == 200
    for _ in range(4):
        client.post("/v1/auth/login", json={"username": "u1", "password": "nope"})
    assert client.post("/v1/auth/login", json={"username": "u1", "password": REG["password"]}).status_code == 200


def test_many_names_from_one_address_lock_the_address(client):  # noqa: F811
    for k in range(20):
        client.post("/v1/auth/login", json={"username": f"guess{k}", "password": "nope"}, headers={"X-Real-IP": "203.0.113.9"})
    r = client.post("/v1/auth/login", json={"username": "someone", "password": "x"}, headers={"X-Real-IP": "203.0.113.9"})
    assert r.status_code == 429
    # Another address is not affected.
    assert client.post("/v1/auth/login", json={"username": "someone", "password": "x"}, headers={"X-Real-IP": "198.51.100.7"}).status_code == 401


def test_sign_ups_from_one_address_are_limited(client, test_rsa_key):  # noqa: F811
    with patch(f"{AUTH}.make_user_connection") as make:
        make.return_value.connect.side_effect = Exception("refused")
        codes = [client.post("/v1/auth/register", json={**REG, "username": f"n{k}", "cluster_host": "x.example.edu", "private_key": test_rsa_key}).status_code
                 for k in range(11)]
    assert codes[:10] == [400] * 10 and codes[10] == 429
