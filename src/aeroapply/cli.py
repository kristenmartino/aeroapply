"""AeroApply CLI (skeleton). Subcommands are wired up across Sprints 1–6."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="aeroapply", description="AeroApply daemon CLI")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("source", help="run the 24/7 sourcing daemon (Bouncer -> Icebox)")
    sub.add_parser("schedule", help="run the WIP scheduler once (Icebox -> execution graph)")
    sub.add_parser("ui", help="launch the Streamlit Inbox/Ledger/Kanban UI")
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    raise SystemExit(f"'{args.command}' not implemented yet — see docs/ROADMAP.md")


if __name__ == "__main__":
    main()
