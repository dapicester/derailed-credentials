import tempfile
from pathlib import Path

import pytest

from derailed.core import Credentials


@pytest.fixture
def project_root_dir():
    return Path(__file__).parent.parent


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def master_key(temp_dir):
    master_key = Credentials.generate_master_key()
    key_path = temp_dir / "master.key"
    key_path.write_text(master_key)
    return master_key


@pytest.fixture
def credentials(temp_dir):
    creds_path = temp_dir / "credentials.yml.enc"
    key_path = temp_dir / "master.key"
    return Credentials(
        credentials_path=str(creds_path),
        master_key_path=str(key_path),
    )


@pytest.fixture
def credentials_with_key(master_key, credentials, temp_dir):
    return credentials


@pytest.fixture
def sample_data():
    return {
        "api_key": "secret123",
        "database": {
            "password": "dbpass",
            "host": "localhost",
            "nested": {"deep": "value"},
        },
        "debug": True,
    }
