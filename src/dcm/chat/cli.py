"""dcm-host / python -m dcm.chat CLI. One implementation with HostSession."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dcm.chat.session import HostSession, doctor
from dcm.runtime.cutoff import CutoffRequired
from dcm.research.run_lock import RunBusyError, RunFenceError
from dcm.research.batch_store import BatchEnvelopeError
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
    d.add_argument("--run", type=Path, default=None)
    d.add_argument("--format", choices=["json"], default="json")

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

    nb = sub.add_parser("research-batch", help="Seal the next immutable, failure-aware research batch")
    _add_run(nb)
    nb.add_argument("--max-entities", type=int, default=25)
    nb.add_argument("--max-dependent-offers", type=int, default=500)
    nb.add_argument("--workspace", type=Path, default=None)

    ds = sub.add_parser("director-status", help="Show the durable one-arrow research director state")
    _add_run(ds)
    ds.add_argument("--workspace", type=Path, default=None)

    dstep = sub.add_parser("director-step", help="Advance exactly one research director transition")
    _add_run(dstep)
    dstep.add_argument("--workspace", type=Path, default=None)

    drun = sub.add_parser("director-run", help="Advance the director until it awaits a response")
    _add_run(drun)
    drun.add_argument("--workspace", type=Path, default=None)
    drun.add_argument("--until", choices=["awaiting"], default="awaiting")

    e = sub.add_parser("evidence-import", help="Import simple host observations (engine hashes)")
    _add_run(e)
    e.add_argument("--input", type=Path, required=True)
    e.add_argument("--workspace", type=Path, default=None)

    rv = sub.add_parser("research-validate", help="Validate observations without importing them")
    _add_run(rv)
    rv.add_argument("--input", type=Path, required=True)
    rv.add_argument("--workspace", type=Path, default=None)

    rf = sub.add_parser("research-failure", help="Append one machine-readable research failure")
    _add_run(rf)
    rf.add_argument("--action-id", required=True)
    rf.add_argument("--request-id", default=None)
    rf.add_argument("--source-id", default=None)
    rf.add_argument("--batch-id", default=None)
    rf.add_argument("--code", required=True)
    rf.add_argument("--retryable", action="store_true")
    rf.add_argument("--exclusion-scope", default="ATTEMPT_ONLY")
    rf.add_argument("--safe-reason", default=None)
    rf.add_argument("--workspace", type=Path, default=None)

    c = sub.add_parser("coverage", help="Semantic coverage vs SportResearchSchema")
    _add_run(c)
    c.add_argument("--workspace", type=Path, default=None)
    c.add_argument("--incremental", action="store_true")
    c.add_argument("--verify-full", action="store_true")

    hb = sub.add_parser("har-breakdown", help="Decompose a HAR into a safe structural receipt")
    _add_run(hb)
    hb.add_argument("--har", type=Path, required=True)
    hb.add_argument("--prior", type=Path, default=None)
    hb.add_argument("--workspace", type=Path, default=None)

    ib = sub.add_parser("index-build", help="Build the local exact/semantic search index receipt")
    _add_run(ib)
    ib.add_argument("--workspace", type=Path, default=None)

    sb = sub.add_parser("search-blueprint", help="Compile the sport-neutral public web-search blueprint")
    _add_run(sb)
    sb.add_argument("--workspace", type=Path, default=None)

    cv = sub.add_parser("checkpoint-verify", help="Verify research and canonical checkpoint hashes")
    _add_run(cv)
    cv.add_argument("--workspace", type=Path, default=None)

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

    cfl = sub.add_parser("cfb-launch", help="Guarded CFB HAR vertical slice (account → graphs → research OS → forecast)")
    cfl.add_argument("--har", type=Path, required=True)
    cfl.add_argument("--run-root", type=Path, required=True)
    cfl.add_argument("--cutoff", default=None)
    cfl.add_argument("--cutoff-from-capture", action="store_true")
    cfl.add_argument("--research", choices=["fixture", "bundle", "file"], default="file")
    cfl.add_argument("--bundle", type=Path, default=None)
    cfl.add_argument("--workspace", type=Path, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            _print(doctor(release_manifest=args.release_manifest, workspace=args.workspace, run=args.run))
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
        if args.command == "cfb-launch":
            from dcm.chat.session import cfb_launch
            _print(cfb_launch(
                har=args.har,
                run_root=args.run_root,
                cutoff=args.cutoff,
                cutoff_from_capture=args.cutoff_from_capture,
                research=args.research,
                bundle_path=args.bundle,
                workspace=args.workspace,
            ))
            return 0
        session = HostSession.open(args.run, workspace=getattr(args, "workspace", None))
        if args.command == "next-research":
            _print(session.next_research_batch(
                max_entities=args.max_entities,
                max_dependent_offers=args.max_dependent_offers,
            ))
        elif args.command == "research-batch":
            _print(session.research_batch(
                max_entities=args.max_entities,
                max_dependent_offers=args.max_dependent_offers,
            ))
        elif args.command in {"director-status", "director-step", "director-run"}:
            from dcm.runtime.run_director import RunDirector
            director = RunDirector(args.run, workspace=args.workspace)
            if args.command == "director-status":
                _print(director.status())
            elif args.command == "director-step":
                _print(director.step())
            else:
                _print(director.run_until_awaiting())
        elif args.command == "research-validate":
            _print(session.research_validate(args.input))
        elif args.command == "research-failure":
            _print(session.record_research_failure(
                action_id=args.action_id,
                request_id=args.request_id,
                source_id=args.source_id,
                batch_id=args.batch_id,
                code=args.code,
                retryable=bool(args.retryable),
                exclusion_scope=args.exclusion_scope,
                safe_reason=args.safe_reason,
            ))
        elif args.command == "evidence-import":
            _print(session.import_evidence(args.input))
        elif args.command == "coverage":
            _print(session.coverage(incremental=bool(args.incremental), verify_full=bool(args.verify_full)))
        elif args.command == "har-breakdown":
            _print(session.har_breakdown(args.har, prior=args.prior))
        elif args.command == "index-build":
            _print(session.index_build())
        elif args.command == "search-blueprint":
            _print(session.search_blueprint())
        elif args.command == "checkpoint-verify":
            _print(session.checkpoint_verify())
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
    except (CutoffRequired, ExactVersionMismatch, RunBusyError, RunFenceError, BatchEnvelopeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
