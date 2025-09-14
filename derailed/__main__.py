"""
The main entrypoint, invoke with `derailed` or `python -m derailed`.
"""

from derailed.cli import Cli


def main():
    Cli().main()


if __name__ == "__main__":
    main()
