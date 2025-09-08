import argparse
import sys

from .core import Credentials, CredentialsError, MasterKeyAlreadyExists


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="derailed", description="Manage encrypted credentials"
    )
    parser.add_argument("--credentials-path", help="Path to credentials file")
    parser.add_argument("--master-key-path", help="Path to master key file")
    parser.add_argument("--master-key-env", help="Environment variable for master key")

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
    generate_parser = subparsers.add_parser("generate-key", help="Generate master key")
    generate_parser.add_argument(
        "--force", help="Overwrite existing file", action="store_true"
    )

    # Get command
    get_parser = subparsers.add_parser("get", help="Get a credential value")
    get_parser.add_argument("key", help="Key to retrieve")
    get_parser.add_argument("--default", help="Default value if key not found")

    # Set command
    set_parser = subparsers.add_parser("set", help="Set a credential value")
    set_parser.add_argument("key", help="Key to set")
    set_parser.add_argument("value", help="Value to set")

    # Delete command
    del_parser = subparsers.add_parser("delete", help="Delete a credential")
    del_parser.add_argument("key", help="Key to delete")

    return parser


def main():
    """Command line interface."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        credentials = Credentials(
            credentials_path=args.credentials_path,
            master_key_path=args.master_key_path,
            master_key_env=args.master_key_env,
        )

        if args.command == "generate-key":
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
                print(
                    f"Master key {master_key} created at {credentials.master_key_path}"
                )
                print(
                    f"Keep this key secure! You can also set it as {credentials.MASTER_KEY_ENV} environment variable."
                )

        elif args.command == "edit":
            if credentials.edit(args.editor, args.pretend) is True:
                print("Credentials updated successfully.")
            else:
                print("No changes made.")

        elif args.command == "show":
            print(credentials.show())

        elif args.command == "get":
            value = credentials.get(args.key, args.default)
            if value is not args.default:
                print(value)
            else:
                print(f"Key '{args.key}' not found")
                sys.exit(1)

        elif args.command == "set":
            credentials.set(args.key, args.value)
            print(f"Set {args.key}")

        elif args.command == "delete":
            if credentials.delete(args.key):
                print(f"Deleted {args.key}")
            else:
                print(f"Key '{args.key}' not found")
                sys.exit(1)

    except CredentialsError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
