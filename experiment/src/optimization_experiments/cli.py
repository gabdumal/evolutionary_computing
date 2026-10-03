from __future__ import annotations

import argparse
from pathlib import Path

from .campaigns import run_campaign
from .experiments.cso import create_cso_smoke_experiment
from .experiments.zoadamm import create_zoadamm_smoke_experiment


def main() -> None:
    parser = argparse.ArgumentParser(prog="opt-experiments")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("cso-smoke", "zoadamm-smoke"):
        smoke = subparsers.add_parser(command)
        smoke.add_argument("--artifact-root", type=Path, default=Path("_artifacts"))
        smoke.add_argument("--workers", type=int, default=None)

    args = parser.parse_args()

    if args.command == "cso-smoke":
        experiment = create_cso_smoke_experiment()
    elif args.command == "zoadamm-smoke":
        experiment = create_zoadamm_smoke_experiment()
    else:
        raise AssertionError(f"Unhandled command: {args.command!r}")

    report = run_campaign(
        experiment,
        artifact_root=args.artifact_root,
        max_workers=args.workers,
    )
    print(report, flush=True)


if __name__ == "__main__":
    main()
