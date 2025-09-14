import re
import subprocess
import sys
from pathlib import Path

import pytest

from derailed.core import Credentials
from derailed.diffing import GITATTRIBUTES_ENTRY

from .base import EditorMixin


class TestCLI(EditorMixin):
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
            input="n",
            cwd=project_root_dir,
        )

        assert result.returncode == 1
        assert re.search(f"Master key file {key_path} already exists", result.stdout)
        assert "Aborted" in result.stdout

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input="y",
            cwd=project_root_dir,
        )

        assert result.returncode == 0
        assert re.search(f"Master key file {key_path} already exists", result.stdout)

    @pytest.fixture
    def credentials_with_data(self, cli_env):
        credentials = Credentials(
            credentials_path=str(cli_env["creds_path"]),
            master_key_path=str(cli_env["key_path"]),
        )
        credentials.config = {"test_key": "test_value"}
        return credentials

    def test_cli_edit(self, credentials_with_data, cli_env):
        with self.editor_write("secret: password"):
            result = self.run_cli(["edit"], cli_env)
        assert result.returncode == 0
        assert "Credentials updated successfully" in result.stdout

    def test_cli_edit_no_changes(self, credentials_with_data, cli_env):
        with self.editor_write(credentials_with_data.show()):
            result = self.run_cli(["edit"], cli_env)
        assert result.returncode == 0
        assert "No changes made" in result.stdout

    def test_cli_show(self, credentials_with_data, cli_env):
        result = self.run_cli(["show"], cli_env)
        assert result.returncode == 0
        assert "test_key: test_value" in result.stdout

    def test_cli_diff_nothing(self, credentials_with_data, cli_env):
        result = self.run_cli(["diff"], cli_env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_cli_diff_show(self, credentials_with_data, cli_env):
        result = self.run_cli(["diff", cli_env["creds_path"]], cli_env)
        assert result.returncode == 0
        assert "test_key: test_value" in result.stdout

    @pytest.fixture
    def gitattributes(self, cli_env, request):
        gitattributes = Path(cli_env["cwd"]) / ".gitattributes"
        request.addfinalizer(lambda: gitattributes.unlink(missing_ok=True))
        return gitattributes

    @pytest.fixture
    def gitattributes_with_content(self, gitattributes):
        sample_content = "* text=auto\n"
        gitattributes.write_text(sample_content)
        return gitattributes, sample_content

    def test_cli_diff_enroll(self, gitattributes, cli_env):
        assert not gitattributes.exists()

        result = self.run_cli(["diff", "--enroll"], cli_env)
        assert result.returncode == 0
        assert "Enrolled project in credentials file diffing!" in result.stdout
        assert gitattributes.read_text() == GITATTRIBUTES_ENTRY

    def test_cli_diff_enroll_append(self, gitattributes_with_content, cli_env):
        gitattributes, sample_content = gitattributes_with_content

        result = self.run_cli(["diff", "--enroll"], cli_env)
        assert "Enrolled project in credentials file diffing!" in result.stdout
        assert gitattributes.read_text() == f"{sample_content}{GITATTRIBUTES_ENTRY}"

    @pytest.fixture
    def gitattributes_enrolled(self, gitattributes):
        gitattributes.write_text(GITATTRIBUTES_ENTRY)
        return gitattributes

    def test_cli_diff_enroll_already_enrolled(self, gitattributes_enrolled, cli_env):
        result = self.run_cli(["diff", "--enroll"], cli_env)
        assert result.returncode == 0
        assert (
            "Project is already enrolled in credentials file diffing" in result.stdout
        )

    def test_cli_diff_disenroll(self, gitattributes_enrolled, cli_env):
        result = self.run_cli(["diff", "--disenroll"], cli_env)
        assert result.returncode == 0
        assert "Disenrolled project from credentials file diffing" in result.stdout

    def test_cli_diff_disenroll_not_enrolled(self, gitattributes, cli_env):
        result = self.run_cli(["diff", "--disenroll"], cli_env)
        assert result.returncode == 0
        assert "Project is not enrolled in credentials file diffing" in result.stdout

    @pytest.fixture
    def git_config(self, cli_env, request):
        git_config = Path(cli_env["cwd"]) / ".git" / "config"
        request.addfinalizer(
            lambda: subprocess.check_call(
                ["git", "config", "unset", "diff.derailed_credentials.textconv"]
            )
        )
        return git_config

    def test_cli_edit_configure_diff_driver(
        self, gitattributes_enrolled, git_config, credentials_with_data, cli_env
    ):
        assert '[diff "derailed_credentials"]' not in git_config.read_text()

        with self.editor_write("secret: password"):
            result = self.run_cli(["edit"], cli_env)
        assert result.returncode == 0
        assert '[diff "derailed_credentials"]' in git_config.read_text()
