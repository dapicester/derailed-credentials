import os
import sys
from dataclasses import dataclass
from functools import cached_property, reduce

import click

from .core import Credentials, MasterKeyAlreadyExists
from .diffing import Diffing


def open_external_editor(file_name: str) -> None:
    import shlex
    import subprocess

    editor = os.environ.get("EDITOR", "nano")
    cmd = shlex.split(editor) + [file_name]
    subprocess.run(cmd, check=True)


@dataclass
class Derailed:
    credentials_path: str | None = None
    master_key_path: str | None = None

    @cached_property
    def credentials(self) -> Credentials:
        return Credentials(self.credentials_path, self.master_key_path)


@click.group(help="Manage encrypted credentials")
@click.option("--credentials-path", help="Path to credentials file")
@click.option("--master-key-path", help="Path to master key file")
@click.version_option(package_name="derailed-credentials")
@click.pass_context
def derailed(ctx, credentials_path: str, master_key_path: str) -> None:
    ctx.ensure_object(Derailed)

    ctx.obj.credentials_path = credentials_path
    ctx.obj.master_key_path = master_key_path


@derailed.command(
    short_help="Open the credentials for editing",
    help="Open the decrypted credentials in `$VISUAL` or `$EDITOR` for editing.",
)
@click.pass_context
def edit(ctx) -> None:
    Diffing().ensure_diffing_driver_is_configured()

    click.echo(f"Editing {ctx.obj.credentials.credentials_path} ...")
    with ctx.obj.credentials.change() as file_name:
        open_external_editor(file_name)
    click.echo("Credentials updated.")


@derailed.command(help="Fetch a value in the decrypted credentials")
@click.argument("path")
@click.pass_context
def fetch(ctx, path: str):
    data = ctx.obj.credentials.config
    try:
        value = reduce(lambda doc, key: doc[key], path.split("."), data)
        click.echo(str(value))
        return
    except (KeyError, TypeError):
        click.echo(f"Invalid or missing credentials path: {path}")
        sys.exit(1)


@derailed.command(help="Show decrypted credentials")
@click.pass_context
def show(ctx) -> None:
    click.echo(ctx.obj.credentials.show())


@derailed.command(help="Enroll/disenroll in decrypted diffs of credentials using git")
@click.option(
    "--enroll",
    help="Enroll project in credentials file diffing with `git diff`",
    is_flag=True,
)
@click.option(
    "--disenroll",
    help="Disenroll project in credentials file diffing",
    is_flag=True,
)
@click.argument("content_path", required=False)
@click.pass_context
def diff(ctx, enroll: bool, disenroll: bool, content_path: str) -> None:
    if content_path:
        click.echo(ctx.obj.credentials.show())
    elif enroll:
        Diffing().enroll_project_in_credentials_diffing()
    elif disenroll:
        Diffing().disenroll_project_from_credentials_diffing()


@derailed.command(help="Generate master key")
@click.option("--force", is_flag=True)
@click.pass_context
def generate_key(ctx, force: bool) -> None:
    credentials = ctx.obj.credentials

    try:
        master_key = credentials.create_master_key_file(force)
    except MasterKeyAlreadyExists:
        response = input(
            f"Master key file {credentials.master_key_path} already exists. Overwrite? [y/N]: "
        )
        if response.lower() == "y":
            master_key = credentials.create_master_key_file(force=True)
        else:
            click.secho("Aborted.", fg="red")
            sys.exit(1)
    else:
        click.echo(f"Master key {master_key} created at {credentials.master_key_path}")
        click.secho(
            f"Keep this key secure! You can also set it as {credentials.MASTER_KEY_ENV} environment variable.",
            fg="red",
        )
