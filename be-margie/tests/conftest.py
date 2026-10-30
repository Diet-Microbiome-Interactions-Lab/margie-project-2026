"""
Pytest configuration and shared fixtures.
"""
import os
import sys
from pathlib import Path

# --- BSP required env vars ---------------------------------------------------
# auth.py reads BSP_SECRET_KEY and BSP_ENCRYPTION_KEY at *import time* and
# raises RuntimeError if either is missing.  Set them here (module level,
# before any test module imports the app) so pytest always starts cleanly.
# setdefault() leaves real env vars (e.g. from CI secrets) untouched.
from cryptography.fernet import Fernet

os.environ.setdefault("BSP_SECRET_KEY", "pytest-only-secret-do-not-use-in-production")
os.environ.setdefault("BSP_ENCRYPTION_KEY", Fernet.generate_key().decode())
# -----------------------------------------------------------------------------

import pytest

# Add the project root to Python path so imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Ensure we're using the local virtual environment
venv_path = project_root / ".venv"
if venv_path.exists():
    # Add the venv site-packages to path if needed
    import site
    site_packages = venv_path / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if site_packages.exists():
        site.addsitedir(str(site_packages))


@pytest.fixture(scope="session")
def project_root_path():
    """Provide the project root path."""
    return project_root


@pytest.fixture(scope="session")
def test_files_dir():
    """Provide the test-files directory path."""
    test_dir = project_root / "test-files"
    if not test_dir.exists():
        pytest.skip("test-files directory not found")
    return test_dir


@pytest.fixture
def example_fasta_file(test_files_dir):
    """Provide path to the example FASTA file."""
    fasta_file = test_files_dir / "example.fasta"
    if not fasta_file.exists():
        pytest.skip("example.fasta not found in test-files")
    return str(fasta_file)


@pytest.fixture
def example_fastq_file(test_files_dir):
    """Provide path to the example FASTQ file."""
    fastq_file = test_files_dir / "example.fastq"
    if not fastq_file.exists():
        pytest.skip("example.fastq not found in test-files")
    return str(fastq_file)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up the test environment."""
    # Ensure we're in the project root directory
    original_cwd = os.getcwd()
    os.chdir(project_root)
    
    yield
    
    # Restore original directory
    os.chdir(original_cwd)


# Pytest markers for different test categories
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may be slower)"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (should be fast)"
    )
    config.addinivalue_line(
        "markers", "cli: marks tests that test CLI functionality"
    )
    config.addinivalue_line(
        "markers", "api: marks tests that test API endpoints"
    )
    config.addinivalue_line(
        "markers", "workflow: marks tests that test workflow execution"
    )


# Pytest collection configuration
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Mark CLI tests
        if "test_cli" in item.nodeid or "cli" in item.name.lower():
            item.add_marker(pytest.mark.cli)

        # Mark API tests
        if "test_api" in item.nodeid:
            item.add_marker(pytest.mark.api)

        # Mark workflow tests
        if "test_workflow" in item.nodeid:
            item.add_marker(pytest.mark.workflow)
        
        # Mark integration tests (tests that use subprocess or external files)
        if any(keyword in item.nodeid for keyword in ["subprocess", "real_test", "example_"]):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)

@pytest.fixture(autouse=True)
def _fresh_reads():
    """Every test starts without the API's short-lived reads (services/read_cache.py)."""
    from bioinformatics_tools.api.services import read_cache

    read_cache._answers.clear()
    yield
    read_cache._answers.clear()


@pytest.fixture(autouse=True)
def _fresh_access(monkeypatch):
    """Every test starts with no sign-in lockouts and any cluster accepted (api/access.py)."""
    from bioinformatics_tools.api import access

    monkeypatch.delenv(access.ENV, raising=False)
    for guard in (access.SIGNIN_BY_NAME, access.SIGNIN_BY_ADDRESS, access.SIGNUP_BY_ADDRESS):
        guard.reset()
    yield


@pytest.fixture(autouse=True)
def _no_scratch_copies(monkeypatch):
    """Tests run without the working folder's copies (scratch_cache): their connections are fakes."""
    from bioinformatics_tools.api.services import scratch_cache
    monkeypatch.setattr(scratch_cache, "backup", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _launches_recorded(monkeypatch):
    """A launched run reads back from the job history (ssh._in_history): the connections are fakes.
    test_relaunch_guards tests the check itself."""
    from bioinformatics_tools.api.routers import ssh

    def recorded(*args, **kwargs):
        return True
    recorded.real = ssh._in_history
    monkeypatch.setattr(ssh, "_in_history", recorded)
