from __future__ import annotations

import argparse
from pathlib import Path

from .campaigns import run_campaign
from .experiments.cso import create_cso_smoke_experiment


def main() -> None:
    parser = argparse.ArgumentParser(prog="opt-experiments")
    subparsers = parser.add_subparsers(dest="command", required=True)

    smoke = subparsers.add_parser("cso-smoke")
    smoke.add_argument("--artifact-root", type=Path, default=Path("_artifacts"))
    smoke.add_argument("--workers", type=int, default=None)

    args = parser.parse_args()

    if args.command == "cso-smoke":
        report = run_campaign(
            create_cso_smoke_experiment(),
            artifact_root=args.artifact_root,
            max_workers=args.workers,
        )
        print(report, flush=True)


if __name__ == "__main__":
    main()
