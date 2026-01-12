import os
import subprocess
from functools import cached_property
from pathlib import Path

import click

GITATTRIBUTES_ENTRY = """
config/credentials/*.yml.enc diff=derailed_credentials
config/credentials.yml.enc diff=derailed_credentials
""".lstrip()


class Diffing:
    """
    Handles the diffing driver for the credentials file.

    Inspired by https://github.com/rails/rails/blob/main/railties/lib/rails/commands/credentials/credentials_command/diffing.rb
    """

    @cached_property
    def gitattributes(self):
        return Path(os.getcwd()) / ".gitattributes"

    def enroll_project_in_credentials_diffing(self) -> None:
        if self.enrolled_in_credentials_diffing:
            click.echo("Project is already enrolled in credentials file diffing.")
            return

        with self.gitattributes.open(mode="a") as f:
            f.write(GITATTRIBUTES_ENTRY)

        self.configure_diffing_driver()

        click.echo("Enrolled project in credentials file diffing!")

    def disenroll_project_from_credentials_diffing(self) -> None:
        if not self.enrolled_in_credentials_diffing:
            click.echo("Project is not enrolled in credentials file diffing.")
            return

        self.gitattributes.write_text(
            self.gitattributes.read_text().replace(GITATTRIBUTES_ENTRY, "")
        )
        if self.gitattributes.stat().st_size == 0:
            self.gitattributes.unlink()
        click.echo("Disenrolled project from credentials file diffing!")

    def ensure_diffing_driver_is_configured(self) -> None:
        if self.enrolled_in_credentials_diffing and not self.diffing_driver_configured:
            self.configure_diffing_driver()

    @property
    def enrolled_in_credentials_diffing(self) -> bool:
        return (
            self.gitattributes.is_file()
            and GITATTRIBUTES_ENTRY in self.gitattributes.read_text()
        )

    @property
    def diffing_driver_configured(self) -> bool:
        returncode = subprocess.call(
            ["git", "config", "--get", "diff.derailed_credentials.textconv"]
        )
        return returncode == 0

    def configure_diffing_driver(self) -> None:
        subprocess.check_call(
            ["git", "config", "diff.derailed_credentials.textconv", "derailed diff"]
        )
        click.echo("Configured Git diff driver for credentials.")
