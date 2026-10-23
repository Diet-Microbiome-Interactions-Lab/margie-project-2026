"""The Cluster page's SLURM picture: accounts and their limits, what is in use, the user's jobs
(an interactive session with its node), and each partition's free CPUs and memory."""

from unittest.mock import patch

from bioinformatics_tools.api.routers.ssh import _tres, parse_cluster
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

SSH = "bioinformatics_tools.api.routers.ssh"

OUT = """@@host
login03.cluster.example.edu
@@assoc
mylab||normal,standby|12000|12000
@@accounts
mylab||gres/hp_cpu=64,gres/gpu=2|
@@qos
normal||||
standby||||04:00:00
@@usage
mylab|u1|cpu=4,mem=8000M,node=1,billing=4,gres/hp_cpu=2
mylab|u2|cpu=64,mem=450G,node=1,billing=64,gres/hp_cpu=8,gres/gpu=1
@@waiting
mylab|u3|16
mylab|u1|8
@@jobs
101|margie-run|cpu|RUNNING|8:37|3-00:00:00|1|4|a010|None|mylab|/home/u1/run.sh
102|interactive|cpu|RUNNING|1:02|4:00:00|1|8|a020|None|mylab|(null)
104|snakemake-job|cpu|RUNNING|0:10|1:00:00|1|2|a030|None|mylab|(null)
103|big|highmem|PENDING|0:00|10:00:00|1|64||Resources|mylab|/home/u1/big.sh
@@nodes
cpu*|a000|maint|0/128/0/128|257400|245851|hp_cpu:128
cpu*|a001|idle|0/128/0/128|257400|250000|hp_cpu:128
cpu*|a002|mixed|100/28/0/128|257400|60000|hp_cpu:128
highmem|b000|allocated|128/0/0/128|1031600|10000|(null)
@@partitions
cpu*|up|infinite|3|100/156/128/384|257400|hp_cpu:128
highmem|up|14-00:00:00|1|128/0/0/128|1031600|(null)
@@end
"""


def test_tres_lists_become_numbers_with_memory_in_mb():
    assert _tres("cpu=8,mem=32G,node=1,gres/gpu=1") == {"cpu": 8, "mem": 32768, "node": 1, "gres/gpu": 1}
    assert _tres("mem=8000M") == {"mem": 8000}
    assert _tres("") == {}


def test_accounts_show_their_limits_and_what_is_in_use():
    r = parse_cluster(OUT, "u1")
    (acct,) = r["accounts"]
    assert acct["name"] == "mylab" and acct["qos"] == ["normal", "standby"] and acct["partitions"] == []
    assert acct["limits"] == {"gres/hp_cpu": 64, "gres/gpu": 2}
    assert acct["in_use"]["gres/hp_cpu"] == 10 and acct["in_use"]["gres/gpu"] == 1 and acct["in_use"]["cpu"] == 68
    assert acct["mine"]["cpu"] == 4 and acct["my_running"] == 1 and acct["running"] == 2


def test_jobs_and_an_interactive_session_with_its_node():
    r = parse_cluster(OUT, "u1")
    assert [j["id"] for j in r["jobs"]] == ["101", "102", "104", "103"]
    assert [(j["id"], j["nodelist"]) for j in r["interactive"]] == [("102", "a020")]
    assert r["host"] == "login03.cluster.example.edu" and r["on_login_node"] is True


def test_partitions_with_free_cpus_and_memory():
    r = parse_cluster(OUT, "u1")
    cpu, high = r["partitions"]
    assert cpu["name"] == "cpu" and cpu["default"] is True and cpu["cpus"] == {"allocated": 100, "idle": 156, "other": 128, "total": 384}
    # Free memory and ready CPUs count idle and mixed nodes only; the node in maintenance is left out.
    assert cpu["mem_free_mb"] == 310000 and cpu["cpus_ready"] == 156 and cpu["node_states"] == {"maint": 1, "idle": 1, "mixed": 1}
    assert high["gres"] == "" and high["time_limit"] == "14-00:00:00" and high["mem_free_mb"] == 0
    assert r["qos"][1] == {"name": "standby", "group": "", "per_user": "", "jobs_per_user": "", "max_wall": "04:00:00"}


def test_the_route_answers_and_is_reused(authed_client):  # noqa: F811
    with patch(f"{SSH}._build_connection"), patch(f"{SSH}._run_remote_check", return_value=(0, OUT)) as run:
        first = authed_client.get("/v1/ssh/cluster_resources")
        second = authed_client.get("/v1/ssh/cluster_resources")
    assert first.status_code == 200 and second.json() == first.json()
    assert run.call_count == 1
    assert first.json()["partitions"][0]["name"] == "cpu"


def test_no_slurm_is_reported(authed_client):  # noqa: F811
    with patch(f"{SSH}._build_connection"), patch(f"{SSH}._run_remote_check", return_value=(127, "sinfo: command not found")):
        r = authed_client.get("/v1/ssh/cluster_resources")
    assert r.status_code == 502


def test_each_account_says_who_is_using_it():
    users = parse_cluster(OUT, "u1")["accounts"][0]["users"]
    assert [u["user"] for u in users] == ["u2", "u1", "u3"]
    u2, u1, u3 = users
    assert (u2["running"], u2["cpu"], u2["gpu"], u2["me"]) == (1, 64, 1, False)
    assert (u1["running"], u1["cpu"], u1["waiting"], u1["waiting_cpu"], u1["me"]) == (1, 4, 1, 8, True)
    assert (u3["running"], u3["waiting"], u3["waiting_cpu"]) == (0, 1, 16)
