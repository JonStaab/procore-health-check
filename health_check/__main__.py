"""Command line entry point.

  python -m health_check demo                      Run on bundled sample data (no account needed)
  python -m health_check auth                      Print the sandbox login URL, then paste the code
  python -m health_check projects                  List companies and projects you can see
  python -m health_check dump --company-id C --project-id P    Save raw RFI and submittal JSON
  python -m health_check run --company-id C --project-id P     Build the Value Review from live sandbox data
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

from . import metrics, report

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

SANDBOX_NOTE = ("Built on the Procore Developer Sandbox with sample project data. Independent portfolio "
                "project by Jonathan Staab; not affiliated with or endorsed by Procore.")
DEMO_NOTE = ("Demo run on synthetic sample data bundled with this project. Independent portfolio "
             "project by Jonathan Staab; not affiliated with or endorsed by Procore.")


def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def build(rfis_raw, subs_raw, customer, project, note, today, outfile: Path) -> Path:
    rfis = metrics.summarize(rfis_raw, "RFIs", today)
    subs = metrics.summarize(subs_raw, "Submittals", today)
    health = metrics.health_score(rfis, subs)
    html = report.render(customer, project, rfis, subs, health,
                         metrics.recommendations(rfis, subs), metrics.adoption_plan(rfis, subs), note, today)
    outfile.parent.mkdir(exist_ok=True)
    outfile.write_text(html, encoding="utf-8")
    print(f"Score {health.score} ({health.grade}). Report written to {outfile}")
    return outfile


def main() -> None:
    _load_env()
    parser = argparse.ArgumentParser(prog="health_check")
    sub = parser.add_subparsers(dest="cmd", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--today", help="Pin the date (YYYY-MM-DD) for repeatable output", default="2026-11-16")
    sub.add_parser("auth")
    sub.add_parser("projects")
    for name in ("dump", "run"):
        p = sub.add_parser(name)
        p.add_argument("--company-id", type=int, required=True)
        p.add_argument("--project-id", type=int, required=True)
        p.add_argument("--customer", default="Sandbox Company")
    args = parser.parse_args()

    if args.cmd == "demo":
        data = ROOT / "sample_data"
        build(json.loads((data / "rfis.json").read_text()), json.loads((data / "submittals.json").read_text()),
              "Coastal Builders (sample customer)", "Riverfront Medical Office Building", DEMO_NOTE,
              date.fromisoformat(args.today), OUT / "value_review_demo.html")
        return

    from . import procore  # imported late so demo mode needs no credentials

    if args.cmd == "auth":
        print("1. Open this URL, sign in to your sandbox, click Allow, and copy the code:\n")
        print(procore.authorize_url(), "\n")
        procore.exchange_code(input("2. Paste the code here: "))
        print("Saved tokens to .tokens.json")
    elif args.cmd == "projects":
        client = procore.Procore()
        for company in client.companies():
            print(f"Company {company['id']}: {company.get('name')}")
            for proj in procore.Procore(company["id"]).projects():
                print(f"   Project {proj['id']}: {proj.get('name')}")
    else:
        client = procore.Procore(args.company_id)
        rfis_raw, subs_raw = client.rfis(args.project_id), client.submittals(args.project_id)
        if args.cmd == "dump":
            OUT.mkdir(exist_ok=True)
            (OUT / "raw_rfis.json").write_text(json.dumps(rfis_raw, indent=2))
            (OUT / "raw_submittals.json").write_text(json.dumps(subs_raw, indent=2))
            print(f"Saved {len(rfis_raw)} RFIs and {len(subs_raw)} submittals to {OUT}")
        else:
            name = next((p.get("name") for p in client.projects() if p["id"] == args.project_id), str(args.project_id))
            build(rfis_raw, subs_raw, args.customer, name, SANDBOX_NOTE, date.today(), OUT / "value_review.html")


if __name__ == "__main__":
    main()
