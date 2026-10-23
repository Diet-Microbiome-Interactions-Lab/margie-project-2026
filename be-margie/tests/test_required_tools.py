"""The tools every MARGIE(SB) run needs (workflow_registry.MARGIE_SB_REQUIRED_TOOLS) come with any choice:
the seven C1 sources, InterPro (labeling's NCBIfam, HAMAP, PIRSF and CDD), dbCAN (a C4 EC source) and
the operons C2 and C3 read. MEROPS, TCDB and GenProp stay optional."""

from unittest.mock import patch

from bioinformatics_tools.workflow_tools.workflow_registry import MARGIE_SB_REQUIRED_TOOLS, WORKFLOWS
from tests.test_api import authed_client, client  # noqa: F401 (fixtures)

SSH = "bioinformatics_tools.api.routers.ssh"


def test_the_required_set_and_what_stays_optional():
    assert MARGIE_SB_REQUIRED_TOOLS == {'cog', 'kegg', 'eggnog', 'uniprot', 'pfam', 'tigrfam', 'pgap', 'interpro', 'dbcan', 'operon'}
    assert not {'merops', 'tcdb', 'geneprop'} & MARGIE_SB_REQUIRED_TOOLS


def test_the_workflow_listing_marks_them():
    wf = WORKFLOWS['margie_sb'] if isinstance(WORKFLOWS, dict) else next(w for w in WORKFLOWS if getattr(w, 'id', None) == 'margie_sb')
    tools = wf['tools'] if isinstance(wf, dict) else wf.tools
    marked = {t['key'] for t in tools if t.get('required')}
    assert marked == set(MARGIE_SB_REQUIRED_TOOLS)


def _run(authed_client, tools, usage="academic"):  # noqa: F811
    with patch("bioinformatics_tools.api.licensing.has_accepted_current_terms", return_value=True), \
            patch("bioinformatics_tools.api.licensing.get_entitlement", return_value={"usage_type": usage, "licensed_tools": []}), \
            patch(f"{SSH}.tool_assets") as assets, patch(f"{SSH}.user_stores") as stores, \
            patch(f"{SSH}._build_connection"), patch(f"{SSH}.job_runner") as runner, patch(f"{SSH}.ssh_sftp") as sftp:
        sftp.read_remote_yaml.return_value = {"main_database": "~/my-db.db", "compute": {"cluster_default": {"account": "lab", "partition": "cpu"}}}
        stores.apply_finished.return_value = False
        stores.status.return_value = {"ready": True, "op": {}}
        stores.point_config.return_value = False
        assets.missing_for_run.return_value = []
        resp = authed_client.post("/v1/ssh/run_workflow", json={"genome_path": "/g/ecoli.fasta", "workflow": "margie_sb", "selected_tools": tools})
        return resp, runner


def test_a_run_choosing_only_genome_properties_still_runs_the_required_tools(authed_client):  # noqa: F811
    resp, runner = _run(authed_client, ["geneprop"])
    assert resp.status_code == 200, resp.json()
    command = runner.submit_job.call_args.kwargs.get("command") or runner.submit_job.call_args.args[1]
    chosen = command.split("margie_sb.selected_tools:", 1)[1].split()[0].split(",")
    assert set(chosen) >= MARGIE_SB_REQUIRED_TOOLS | {"geneprop"}


def test_a_commercial_user_without_a_kegg_licence_is_told_so(authed_client):  # noqa: F811
    resp, runner = _run(authed_client, ["geneprop"], usage="commercial")
    assert resp.status_code == 403 and "kegg" in resp.json()["detail"]
    runner.submit_job.assert_not_called()
