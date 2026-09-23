"""Command line helpers.

    python -m app.cli demo                 # load synthetic demo data and analyse it
    python -m app.cli import FILE [--country SA] [--platform instagram] [--community NAME]
    python -m app.cli analyze [--reanalyze]
"""
from __future__ import annotations

import argparse
import json
import os

from .analysis.pipeline import run_analysis
from .connectors.base import FetchRequest
from .connectors.tabular import TabularImport, load_records
from .db import session_scope
from .ingest import run_connector

DEMO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_data", "synthetic_comments.csv")


def _import(path: str, country=None, platform=None, community=None) -> dict:
    with open(path, "rb") as f:
        records = load_records(f.read(), path)
    with session_scope() as s:
        run = run_connector(s, TabularImport(records, platform, community), FetchRequest(country=country),
                            source_name=f"cli:{os.path.basename(path)}")
        return {"status": run.status, "stats": run.stats, "error": run.error}


def main() -> None:
    ap = argparse.ArgumentParser(prog="ghci")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo")
    imp = sub.add_parser("import")
    imp.add_argument("file")
    imp.add_argument("--country")
    imp.add_argument("--platform")
    imp.add_argument("--community")
    an = sub.add_parser("analyze")
    an.add_argument("--reanalyze", action="store_true")
    args = ap.parse_args()

    if args.cmd == "demo":
        print(json.dumps(_import(DEMO), indent=2))
    elif args.cmd == "import":
        print(json.dumps(_import(args.file, args.country, args.platform, args.community), indent=2))
    if args.cmd in ("demo", "import", "analyze"):
        with session_scope() as s:
            print(json.dumps(run_analysis(s, reanalyze=getattr(args, "reanalyze", False)), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
