"""Run one CI check suite using the selected interpreter."""

from __future__ import annotations

import argparse
import subprocess
import sys


def run_module(*arguments: str) -> None:
    """Run a Python module and propagate failures to the CI job."""
    subprocess.run([sys.executable, "-m", *arguments], check=True)


def main() -> None:
    """Dispatch a named suite without duplicating commands in workflow YAML."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("unit", "lint"))
    args = parser.parse_args()
    if args.suite == "unit":
        run_module(
            "coverage", "run", "-m", "unittest", "discover",
            "-s", "tests", "-p", "test_*.py",
        )
        run_module("coverage", "report", "-m")
    else:
        run_module("pylint", "--jobs=1", "jacl4py", "tests")


if __name__ == "__main__":
    main()