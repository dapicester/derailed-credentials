import argparse
import sys

from .core import Credentials, CredentialsError, MasterKeyAlreadyExists


class Cli:
    """Command line interface."""

    def __init__(self):
        self.parser = self.build_parser()

    def build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="derailed", description="Manage encrypted credentials"
        )
        parser.add_argument("--credentials-path", help="Path to credentials file")
        parser.add_argument("--master-key-path", help="Path to master key file")

        subparsers = parser.add_subparsers(dest="command", help="Commands")

        # Edit command
        edit_parser = subparsers.add_parser("edit", help="Edit credentials")
        edit_parser.add_argument("--editor", help="Editor to use")
        edit_parser.add_argument(
            "--pretend", help="Do not actually edit the file", action="store_true"
        )

        # Show command
        subparsers.add_parser("show", help="Show decrypted credentials")

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

        if credentials.edit(args.editor, args.pretend) is True:
            print("Credentials updated successfully.")
        else:
            print("No changes made.")

    def show(self, args: argparse.Namespace) -> None:
        credentials = self.get_credentials(args.credentials_path, args.master_key_path)
        print(credentials.show())

    def main(self):
        args = self.parser.parse_args()

        if not args.command:
            self.parser.print_help()
            return

        try:
            if args.command == "generate-key":
                self.generate_key(args)
            elif args.command == "edit":
                self.edit(args)
            elif args.command == "show":
                self.show(args)
        except CredentialsError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(1)
