from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="opt-experiments")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version")
    args = parser.parse_args()

    if args.command == "version":
        print("optimization-experiments 0.1.0")
