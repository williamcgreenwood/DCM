"""dcm-host / python -m dcm.chat CLI. One implementation with HostSession."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dcm.chat.session import HostSession, doctor
from dcm.runtime.cutoff import CutoffRequired
from dcm.version import ExactVersionMismatch


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _add_run(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", type=Path, required=True, help="Existing run directory")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dcm-host",
        description=(
            "ChatGPT/Grok-native DCM host interface. Python is the only probability engine. "
            "The host performs web research and submits simple observations."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", help="Runtime identity, plugins, catalog, blockers")
    d.add_argument("--release-manifest", type=Path, default=None)
    d.add_argument("--workspace", type=Path, default=None)

    p = sub.add_parser("prepare", help="Ingest HAR, account every offer, emit research population")
    p.add_argument("--har", type=Path, default=None)
    p.add_argument("--input", type=Path, action="append", default=None)
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--cutoff", default=None)
    p.add_argument("--cutoff-from-capture", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--workspace", type=Path, default=None)
    p.add_argument("--research-shadow", action="store_true")

    n = sub.add_parser("next-research", help="Next optimized reusable-entity research batch")
    _add_run(n)
    n.add_argument("--max-entities", type=int, default=25)
    n.add_argument("--max-dependent-offers", type=int, default=500)
    n.add_argument("--workspace", type=Path, default=None)

    e = sub.add_parser("evidence-import", help="Import simple host observations (engine hashes)")
    _add_run(e)
    e.add_argument("--input", type=Path, required=True)
    e.add_argument("--workspace", type=Path, default=None)

    c = sub.add_parser("coverage", help="Semantic coverage vs SportResearchSchema")
    _add_run(c)
    c.add_argument("--workspace", type=Path, default=None)

    f = sub.add_parser("forecast", help="Run FeatureStore → freeze via the canonical Python engine")
    _add_run(f)
    f.add_argument("--workspace", type=Path, default=None)
    f.add_argument("--research", choices=["bundle", "fixture", "file"], default="bundle")

    r = sub.add_parser("report", help="Write chat_result.json")
    _add_run(r)
    r.add_argument("--format", dest="fmt", default="json")
    r.add_argument("--workspace", type=Path, default=None)

    u = sub.add_parser("resume", help="Deterministic resume from checkpoint")
    _add_run(u)
    u.add_argument("--workspace", type=Path, default=None)

    a = sub.add_parser("audit", help="Validate hashes, evidence, freeze")
    _add_run(a)
    a.add_argument("--workspace", type=Path, default=None)

    ar = sub.add_parser("archive", help="Content-addressed archive pack; forecast never needs GitHub write")
    _add_run(ar)
    ar.add_argument("--format", default="github-pack")
    ar.add_argument("--repo", type=Path, default=None)
    ar.add_argument("--workspace", type=Path, default=None)

    s = sub.add_parser("settle", help="Append-only settlement against outcomes.json")
    _add_run(s)
    s.add_argument("--outcomes", type=Path, required=True)
    s.add_argument("--card-only", action="store_true")
    s.add_argument("--workspace", type=Path, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            _print(doctor(release_manifest=args.release_manifest, workspace=args.workspace))
            return 0
        if args.command == "prepare":
            session = HostSession.prepare(
                har=args.har,
                input_paths=args.input,
                run_root=args.run_root,
                cutoff=args.cutoff,
                cutoff_from_capture=args.cutoff_from_capture,
                workspace=args.workspace,
                synthetic=args.synthetic,
                research_shadow=args.research_shadow,
            )
            _print({
                "runDest": str(session.dest),
                "runId": session.dest.name,
                "hostState": str(session.dest / "host_state.json"),
            })
            return 0
        session = HostSession.open(args.run, workspace=getattr(args, "workspace", None))
        if args.command == "next-research":
            _print(session.next_research_batch(
                max_entities=args.max_entities,
                max_dependent_offers=args.max_dependent_offers,
            ))
        elif args.command == "evidence-import":
            _print(session.import_evidence(args.input))
        elif args.command == "coverage":
            _print(session.coverage())
        elif args.command == "forecast":
            result = session.forecast(research=args.research)
            _print({
                "run_id": result.get("run_id"),
                "dest": result.get("dest"),
                "runState": result.get("runState"),
            })
        elif args.command == "report":
            _print(session.report(fmt=args.fmt))
        elif args.command == "resume":
            result = session.resume()
            _print({"run_id": result.get("run_id"), "dest": result.get("dest"), "runState": result.get("runState")})
        elif args.command == "audit":
            _print(session.audit())
        elif args.command == "archive":
            _print(session.archive(format=args.format, repo_root=args.repo))
        elif args.command == "settle":
            result = session.settle(args.outcomes, card_only=bool(args.card_only))
            _print(result.get("summary") or result)
        else:
            parser.error(f"unknown command {args.command}")
            return 2
        return 0
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (CutoffRequired, ExactVersionMismatch, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
