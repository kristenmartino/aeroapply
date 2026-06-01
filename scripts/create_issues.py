#!/usr/bin/env python3
"""Create GitHub milestones, epic + child issues from backlog/issues.json.

Usage:
    python3 scripts/create_issues.py --owner kristenmartino --repo aeroapply [--dry-run]

Writes backlog/created_issues.json (number/url/labels/sprint) for setup_github_project.py.
Requires the `gh` CLI (authenticated). No jq needed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "backlog" / "issues.json"
OUT = ROOT / "backlog" / "created_issues.json"

DEFAULT_LABEL_COLOR = "ededed"


def gh(args: list[str], dry: bool = False, capture: bool = False) -> str:
    if dry:
        print("DRY:", "gh", *args)
        return ""
    res = subprocess.run(["gh", *args], capture_output=capture, text=True)
    if res.returncode != 0:
        msg = (res.stderr or "").strip()
        if capture:
            print(f"  ! gh {' '.join(args)} -> {msg}", file=sys.stderr)
        return ""
    return (res.stdout or "").strip()


def short_epic(key: str) -> str:
    return "epic:" + key.removeprefix("EPIC-").removeprefix("epic-").lower()


def ensure_label(name: str, repo: str, dry: bool) -> None:
    gh(["label", "create", name, "--color", DEFAULT_LABEL_COLOR, "--repo", repo, "--force"],
       dry=dry, capture=True)


def ensure_milestones(repo: str, sprints: set[int], dry: bool) -> dict[int, str]:
    existing = {}
    out = gh(["api", f"repos/{repo}/milestones", "--paginate"], capture=True)
    if out:
        try:
            for m in json.loads(out):
                existing[m["title"]] = m["number"]
        except json.JSONDecodeError:
            pass
    mapping: dict[int, str] = {}
    for s in sorted(sprints):
        title = f"Sprint {s}"
        if title in existing:
            mapping[s] = title
        else:
            gh(["api", f"repos/{repo}/milestones", "-f", f"title={title}"], dry=dry, capture=True)
            mapping[s] = title
    return mapping


def issue_body(issue: dict) -> str:
    lines = [issue.get("body", "").strip(), ""]
    lines.append(f"**Epic:** {issue.get('epic', '—')}  ·  **Estimate:** {issue.get('estimate', '—')}")
    acs = issue.get("acceptance_criteria") or []
    if acs:
        lines += ["", "### Acceptance criteria", *[f"- [ ] {a}" for a in acs]]
    deps = issue.get("dependencies") or []
    if deps:
        lines += ["", "**Dependencies:** " + "; ".join(deps)]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default="kristenmartino")
    ap.add_argument("--repo", default="aeroapply")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    repo = f"{args.owner}/{args.repo}"
    dry = args.dry_run

    data = json.loads(BACKLOG.read_text())
    epics = data.get("epics", [])
    issues = data.get("issues", [])
    print(f"Loaded {len(epics)} epics, {len(issues)} issues from {BACKLOG.name}")

    # 1. Ensure every label that any issue references exists.
    all_labels = {lbl for i in issues for lbl in (i.get("labels") or [])}
    all_labels |= {short_epic(e["key"]) for e in epics}
    all_labels |= {short_epic(i["epic"]) for i in issues if i.get("epic")}
    all_labels |= {"type:epic"}
    for lbl in sorted(all_labels):
        ensure_label(lbl, repo, dry)

    # 2. Milestones (sprints).
    sprints = {int(i["sprint"]) for i in issues if i.get("sprint")}
    ms = ensure_milestones(repo, sprints, dry)

    created: list[dict] = []

    # 3. Epic tracking issues.
    for e in epics:
        title = f"[Epic] {e['title']}"
        body = f"{e.get('goal', '').strip()}\n\nEpic key: `{e['key']}`"
        url = gh(["issue", "create", "--repo", repo, "--title", title, "--body", body,
                  "--label", "type:epic", "--label", short_epic(e["key"])], dry=dry, capture=True)
        print(f"  epic: {title} -> {url or '(dry)'}")
        if url:
            created.append({"url": url, "title": title, "epic": e["key"], "labels": ["type:epic"]})
        time.sleep(0.8)

    # 4. Child issues.
    for i in issues:
        cmd = ["issue", "create", "--repo", repo, "--title", i["title"], "--body", issue_body(i)]
        for lbl in (i.get("labels") or []):
            cmd += ["--label", lbl]
        if i.get("epic"):
            cmd += ["--label", short_epic(i["epic"])]
        if i.get("sprint") and int(i["sprint"]) in ms:
            cmd += ["--milestone", ms[int(i["sprint"])]]
        url = gh(cmd, dry=dry, capture=True)
        print(f"  issue: {i['title'][:60]} -> {url or '(dry)'}")
        if url:
            created.append({
                "url": url, "title": i["title"], "epic": i.get("epic"),
                "labels": i.get("labels") or [], "sprint": i.get("sprint"),
                "estimate": i.get("estimate"),
            })
        time.sleep(0.8)

    if not dry:
        OUT.write_text(json.dumps(created, indent=2))
        print(f"\nWrote {len(created)} created issues to {OUT}")


if __name__ == "__main__":
    main()
