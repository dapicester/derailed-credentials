import argparse
import sys
from functools import reduce

from .core import Credentials, CredentialsError, MasterKeyAlreadyExists
from .diffing import Diffing


class Cli:
    """Command line interface."""

    def __init__(self):
        self.parser = self.build_parser()
        self.diffing = Diffing()

    def build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="derailed", description="Manage encrypted credentials"
        )
        parser.add_argument("--credentials-path", help="Path to credentials file")
        parser.add_argument("--master-key-path", help="Path to master key file")

        subparsers = parser.add_subparsers(dest="command", help="Commands")

        # Edit command
        subparsers.add_parser(
            "edit",
            help="Open the decrypted credentials in `$VISUAL` or `$EDITOR` for editing.",
        )

        # Show command
        subparsers.add_parser("show", help="Show decrypted credentials")

        # Fetch command
        fetch_parser = subparsers.add_parser(
            "fetch", help="Fetch a value in the decrypted credentials"
        )
        fetch_parser.add_argument("path")

        # Diff command
        diff_parser = subparsers.add_parser(
            "diff", help="Enroll/disenroll in decrypted diffs of credentials using git"
        )
        diff_parser.add_argument(
            "--enroll",
            help="Enroll project in credentials file diffing with `git diff`",
            action="store_true",
        )
        diff_parser.add_argument(
            "--disenroll",
            help="Disenroll project in credentials file diffing",
            action="store_true",
        )
        diff_parser.add_argument("content_path", nargs="?")

        # Generate key command
        generate_parser = subparsers.add_parser(
            "generate-key", help="Generate master key"
        )
        generate_parser.add_argument(
            "--force", help="Overwrite existing file", action="store_true"
        )

        return parser

    def get_credentials(
        self, credentials_path=str | None, master_key_path=str | None
    ) -> Credentials:
        return Credentials(credentials_path, master_key_path)

    def generate_key(self, args: argparse.Namespace) -> None:
        credentials = self.get_credentials(args.credentials_path, args.master_key_path)

        try:
            master_key = credentials.create_master_key_file(args.force)
        except MasterKeyAlreadyExists:
            response = input(
                f"Master key file {credentials.master_key_path} already exists. Overwrite? [y/N]: "
            )
            if response.lower() == "y":
                master_key = credentials.create_master_key_file(force=True)
            else:
                print("Aborted.")
                sys.exit(1)
        else:
            print(f"Master key {master_key} created at {credentials.master_key_path}")
            print(
                f"Keep this key secure! You can also set it as {credentials.MASTER_KEY_ENV} environment variable."
            )

    def edit(self, args: argparse.Namespace) -> None:
        credentials = self.get_credentials(args.credentials_path, args.master_key_path)
        self.diffing.ensure_diffing_driver_is_configured()

        if credentials.edit() is True:
            print("Credentials updated successfully.")
        else:
            print("No changes made.")

    def fetch(self, args: argparse.Namespace) -> None:
        credentials = self.get_credentials(args.credentials_path, args.master_key_path)
        data = credentials.config
        try:
            value = reduce(lambda doc, key: doc[key], args.path.split("."), data)
            print(str(value))
            return
        except (KeyError, TypeError):
            print("Invalid or missing credentials path:", args.path)
            sys.exit(1)

    def diff(self, args: argparse.Namespace) -> None:
        if args.content_path:
            credentials = self.get_credentials(args.content_path, args.master_key_path)
            print(credentials.show())
        elif args.enroll:
            self.diffing.enroll_project_in_credentials_diffing()
        elif args.disenroll:
            self.diffing.disenroll_project_from_credentials_diffing()

    def show(self, args: argparse.Namespace) -> None:
        credentials = self.get_credentials(args.credentials_path, args.master_key_path)
        print(credentials.show())

    def main(self):
        args = self.parser.parse_args()

        if not args.command:
            self.parser.print_help()
            return

        try:
            getattr(self, args.command.replace("-", "_"))(args)
        except CredentialsError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(1)
