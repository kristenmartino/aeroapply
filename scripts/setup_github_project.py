#!/usr/bin/env python3
"""Create the AeroApply GitHub Project (v2), add custom fields, and add all issues.

Usage:
    python3 scripts/setup_github_project.py --owner kristenmartino [--title AeroApply] [--set-status]

Reads backlog/created_issues.json (from create_issues.py). Requires `gh` with the
`project` scope. By default it creates the project + fields and adds every issue as
an item. Pass --set-status to also set Status=Todo per item (one extra call each).
Sprint grouping uses the built-in Milestone field; Area/Priority remain visible as labels.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREATED = ROOT / "backlog" / "created_issues.json"

FIELDS = {
    "Status": ["Todo", "In Progress", "In Review", "Blocked", "Done"],
    "Area": ["sourcing", "graph", "ui", "email", "connectors", "security", "models", "infra", "data"],
    "Priority": ["P0", "P1", "P2"],
    "Estimate": ["S", "M", "L"],
}


def gh_json(args: list[str]) -> dict | list | None:
    res = subprocess.run(["gh", *args], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  ! gh {' '.join(args)} -> {res.stderr.strip()}", file=sys.stderr)
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def gh(args: list[str]) -> bool:
    res = subprocess.run(["gh", *args], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  ! gh {' '.join(args)} -> {res.stderr.strip()}", file=sys.stderr)
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default="kristenmartino")
    ap.add_argument("--title", default="AeroApply")
    ap.add_argument("--set-status", action="store_true")
    args = ap.parse_args()

    created = json.loads(CREATED.read_text()) if CREATED.exists() else []
    if not created:
        print("No created_issues.json — run create_issues.py first.")
        return

    proj = gh_json(["project", "create", "--owner", args.owner, "--title", args.title, "--format", "json"])
    if not proj:
        print("Failed to create project.")
        return
    number, pid = proj["number"], proj["id"]
    print(f"Project #{number} created: {proj.get('url')}")

    # Custom single-select fields.
    for name, opts in FIELDS.items():
        gh(["project", "field-create", str(number), "--owner", args.owner,
            "--name", name, "--data-type", "SINGLE_SELECT",
            "--single-select-options", ",".join(opts)])

    # Resolve field + option ids for Status.
    flist = gh_json(["project", "field-list", str(number), "--owner", args.owner, "--format", "json"]) or {}
    fields = flist.get("fields", flist if isinstance(flist, list) else [])
    status_fid, todo_oid = None, None
    for f in fields:
        if f.get("name") == "Status":
            status_fid = f.get("id")
            for o in f.get("options", []):
                if o.get("name") == "Todo":
                    todo_oid = o.get("id")

    added = 0
    for item in created:
        res = gh_json(["project", "item-add", str(number), "--owner", args.owner,
                       "--url", item["url"], "--format", "json"])
        if not res:
            continue
        added += 1
        if args.set_status and status_fid and todo_oid:
            gh(["project", "item-edit", "--id", res["id"], "--project-id", pid,
                "--field-id", status_fid, "--single-select-option-id", todo_oid])

    print(f"Added {added}/{len(created)} issues to project #{number}.")
    print("Tip: in the UI, add a 'By Sprint' view grouped by Milestone, and a Board grouped by Status.")


if __name__ == "__main__":
    main()
