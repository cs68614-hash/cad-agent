"""Prepare a manual live CATIA acceptance record; never connects or modifies CAD."""
import argparse
import datetime
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--i-understand-live-catia", action="store_true", required=True,
                        help="Acknowledge that real CATIA validation needs separate approval")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "NOT_RUN", "catia_contacted": False,
        "notice": "Template only. Obtain explicit authorization before live modeling.",
        "environment": {"catia_release": "", "service_pack": "", "licenses": [], "python": ""},
        "cases": [{"name": name, "status": "NOT_RUN", "evidence": [], "notes": ""}
                  for name in ["attach_and_binding", "unit_baseline", "surface_chain", "partial_failure",
                               "idempotency_and_restart", "file_boundaries", "remote_auth",
                               "exchange_export", "drawing_assembly", "analysis_material_and_solver"]],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(f"NOT_RUN: manual acceptance template written to {args.output}")


if __name__ == "__main__":
    main()
