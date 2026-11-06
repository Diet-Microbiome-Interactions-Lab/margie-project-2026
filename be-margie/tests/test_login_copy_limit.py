"""The login node takes copies under 500 MB (user_stores.LOGIN_COPY_LIMIT); larger ones run on SLURM."""
import pytest

from bioinformatics_tools.api.services import user_stores as us


def test_a_plan_counts_its_copy_and_files_steps():
    plan = [['copy', 'a', '/s', '/d', 600], ['files', 'b', '/s', '/d', 10, 'x'], ['mkdir', '/x'], ['new', 'c', '/y']]
    assert us._plan_bytes(plan) == 610


def test_with_no_slurm_account_a_large_copy_is_refused_before_anything_is_written():
    plan = [['copy', 'MARGIE database', '/base.db', '/work.db', 600 * 1024 * 1024]]
    with pytest.raises(us.StoreError) as e:
        us._start(None, '/root', 'setup', plan, {}, cfg={})
    assert e.value.status == 409 and '500.0 MB' in str(e.value) and 'SLURM account' in str(e.value)
