"""Run the full project pipeline.

Usage:
    python src/run_pipeline.py               # use cached raw data
    python src/run_pipeline.py --refresh     # re-fetch from Oracle's Elixir
    python src/run_pipeline.py --skip-viz    # skip chart generation

The cached path is the default so the project can be reproduced without
depending on the upstream API being available.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def run(script: str, extra: list[str] | None = None) -> None:
    cmd = [sys.executable, str(SRC / script)] + (extra or [])
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Re-fetch raw data")
    parser.add_argument("--skip-viz", action="store_true", help="Skip charts")
    args = parser.parse_args()

    if args.refresh:
        run("collect_data.py", ["--force"])
    run("build_dataset.py")
    run("kpis.py")
    run("model.py")
    if not args.skip_viz:
        run("visualizations.py")
    run("export_powerbi.py")
    run("validate_outputs.py")


if __name__ == "__main__":
    main()
