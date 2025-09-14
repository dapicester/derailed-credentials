from pathlib import Path

import pytest

from derailed import Credentials


class TestCredentialsIntegration:
    """Integration tests simulating real usage scenarios."""

    @pytest.fixture
    def app_setup(self, temp_dir):
        config_dir = Path(temp_dir) / "config"
        config_dir.mkdir()

        creds = Credentials(
            credentials_path=str(config_dir / "credentials.yml.enc"),
            master_key_path=str(config_dir / "master.key"),
        )

        # Create master key
        master_key = creds.create_master_key_file()

        yield creds, config_dir, master_key

    def test_multiple_environments(self, app_setup):
        """Test handling multiple environment files."""
        creds, config_dir, master_key = app_setup

        # Create separate credentials for different environments
        prod_creds = Credentials(
            credentials_path=str(config_dir / "credentials.production.yml.enc"),
            master_key_path=str(config_dir / "master.key"),
        )

        staging_creds = Credentials(
            credentials_path=str(config_dir / "credentials.staging.yml.enc"),
            master_key_path=str(config_dir / "master.key"),
        )

        # Set different values
        prod_creds.config = {"database.password": "prod-password"}
        staging_creds.config = {"database.password": "staging-password"}

        assert prod_creds.get("database.password") == "prod-password"
        assert staging_creds.get("database.password") == "staging-password"
