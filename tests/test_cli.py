import re
import subprocess
import sys

import pytest

from derailed.core import Credentials


class TestCLI:
    @pytest.fixture
    def cli_env(self, temp_dir, project_root_dir):
        # TODO: DRY
        creds_path = temp_dir / "credentials.yml.enc"
        key_path = temp_dir / "master.key"
        master_key = Credentials.generate_master_key()
        key_path.write_text(master_key)

        return {
            "creds_path": str(creds_path),
            "key_path": str(key_path),
            "master_key": master_key,
            "cwd": str(project_root_dir),
        }

    def run_cli(self, args, cli_env):
        cmd = [
            sys.executable,
            "-m",
            "derailed",
            "--credentials-path",
            cli_env["creds_path"],
            "--master-key-path",
            cli_env["key_path"],
        ] + args

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cli_env["cwd"])

        return result

    def test_help(self, cli_env):
        result = self.run_cli([], cli_env)

        assert result.returncode == 0
        assert "usage: derailed [-h]" in result.stdout

    def test_cli_generate_key(self, temp_dir, project_root_dir):
        key_path = temp_dir / "test_master.key"

        cmd = [
            sys.executable,
            "-m",
            "derailed",
            "--master-key-path",
            str(key_path),
            "generate-key",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root_dir,
        )

        assert result.returncode == 0
        assert key_path.exists()
        assert re.search("Master key (?:.+) created", result.stdout)

    def test_cli_generate_key_already_exist(
        self, master_key, temp_dir, project_root_dir
    ):
        key_path = temp_dir / "master.key"
        assert key_path.exists()

        cmd = [
            sys.executable,
            "-m",
            "derailed",
            "--master-key-path",
            str(key_path),
            "generate-key",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root_dir,
        )

        assert result.returncode == 1
        assert re.search(f"Master key file {key_path} already exists", result.stdout)

    @pytest.fixture
    def credentials_with_data(self, cli_env):
        credentials = Credentials(
            credentials_path=str(cli_env["creds_path"]),
            master_key_path=str(cli_env["key_path"]),
        )
        credentials._save_config({"test_key": "test_value"})
        return credentials

    def test_cli_edit(self, credentials_with_data, cli_env):
        result = self.run_cli(["edit", "--pretend"], cli_env)
        assert result.returncode == 0
        assert "Credentials" in result.stdout or result.stderr == ""

    def test_cli_show(self, credentials_with_data, cli_env):
        result = self.run_cli(["show"], cli_env)
        assert result.returncode == 0
        assert "test_key: test_value" in result.stdout
