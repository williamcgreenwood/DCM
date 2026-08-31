"""GitHub-verifiable DCM run audit archive.

Copies a SAFE subset of a finished run into audit/runs/<runId>/ so a reviewer
can prove: the run finished, research ran WITH evidence (URLs, timestamps,
claim hashes) BEFORE ranking, and every selection cites that evidence.

Never copies HARs, sqlite indexes, full populations, worlds, or anything
that looks like cookies/tokens/authorization. Never prints secrets.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.coverage import coverage_report, evaluate_request
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE

BOARD_MAX_BYTES = 2 * 1024 * 1024
COMPLETE_STATES = frozenset(
    {"COMPLETE_FROZEN", "COMPLETE_WITH_UNSUPPORTED_ROWS", "EMPTY_CARD_COMPLETE"}
)
# Three-layer Python freeze states: modeled card/top25 exist while v5/V1 production root stays closed.
PYTHON_FREEZE_STATES = COMPLETE_STATES | {
    "RESEARCHED_MODELED_CARD",
    "RESEARCHED_MODELED_TOP25",
}
REQUIRED_PICK_SCOPES = frozenset({"PLAYER", "EVENT", "MARKET_DEFINITION", "MARKET", "OFFER"})
SKIP_EVIDENCE_JSON = frozenset({"coverage.json", "conflicts.json"})
SECRET_SUBSTR = ("cookie", "token", "authorization", "password", "passwd", "secret", "apikey", "api_key")
SECRET_CONTENT_RE = re.compile(
    r"(?i)(set-cookie|\bcookie\b|\bauthorization\b|\bbearer\b|\bcsrf\b|session[-_]?token)"
)
DEFAULT_GIT_NAME = "dcm-archive"
DEFAULT_GIT_EMAIL = "dcm-archive@users.noreply.github.com"
MANUAL_STATES = frozenset({"MANUAL_RESEARCH_CARD"})
MANUAL_EVIDENCE_MODES = frozenset({"manual_research", "manual"})
REQUIRED_MODEL_STAGES = frozenset({"RESEARCH", "MODEL", "RANK", "FREEZE"})
# Canonical certification flags. The former locksCertified field is retired
# from runtime/audit state; compatibility callers may use locks_certified().
CERT_FLAG_KEYS = (
    "archiveIntegrityCertified",
    "evidenceCoverageCertified",
    "evidenceTemporalCertified",
    "modelRunCertified",
    "selectionCertified",
    "productionRootCertified",
    "predictiveValidationEarned",
    "hashCertifiedPythonFreeze",
)
FORBIDDEN_NAMES = frozenset(
    {
        "index.sqlite",
        "population_full.jsonl",
        "full_population.jsonl",
    }
)
FORBIDDEN_DIR_PARTS = frozenset({"worlds", "raw_har", "raw_capture"})
PACK_FILES = (
    "hashes.json",
    "hashes",
    "accounting.json",
    "input_manifest.json",
    "frozen_forecast.json",
    "freeze.json",
    "frozen_forecast.sha256",
    "top25_ranked.json",
    "top25_qualified.json",
    "strict_card.json",
    "production_certified_card.json",
    "blockers.json",
    "run_integrity.json",
    "production_readiness.json",
    "checkpoint.json",
    "VERSION.json",
    "SCHEMA_STATE.json",
    "MODEL_CONFIG.json",
    "CALIBRATION_STATE.json",
    "research_plan.json",
    "host_research_plan.json",
    "research_requests.json",
    "evidence_bundle.jsonl",
    "evidence_manifest.json",
    "bundle_manifest.json",
    "subject_offer_sets.json",
    "research_population_manifest.json",
    "research_dependency_graph.json",
    "universal_host_research_plan.json",
    "sport_plugin_contract_registry.json",
    "research_population_manifest_legacy.json",
    "player_offer_sets.json",
    "player_research_packets.json",
    "team_research_packets.json",
    "event_research_packets.json",
    "opponent_research_packets.json",
    "entity_research_packets.json",
    "entity_graph.json",
    "staged_research.json",
    "identities/player_index.json",
    "identities/map.json",
    "evidence_graph.json",
    "feature_store.jsonl",
    "feature_store_manifest.json",
    "event_worlds_meta.json",
    "prop_explanations.jsonl",
    "MOUNT_STATE.json",
    "RUN_AUDIT.md",
    "pick_evidence.json",
    "archive_manifest.json",
)


def scan_for_secrets(path: Path) -> list[str]:
    """Return secret-like tokens found in file text. Empty list means clean.

    Matches Cookie, Set-Cookie, Authorization, Bearer, CSRF, and session
    token-like keys. Binary files are skipped.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return []
    if b"\x00" in raw[:8192]:
        return []
    try:
        text_body = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_body = raw.decode("latin-1")
        except UnicodeDecodeError:
            return []
    hits: list[str] = []
    seen: set[str] = set()
    for match in SECRET_CONTENT_RE.finditer(text_body):
        token = match.group(0)
        key = token.lower()
        if key not in seen:
            seen.add(key)
            hits.append(token)
    return hits


def git_identity() -> tuple[str, str]:
    """Author/committer identity for archive commits. Never requires git config."""
    name = (os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("GIT_COMMITTER_NAME") or DEFAULT_GIT_NAME).strip()
    email = (os.environ.get("GIT_AUTHOR_EMAIL") or os.environ.get("GIT_COMMITTER_EMAIL") or DEFAULT_GIT_EMAIL).strip()
    return name or DEFAULT_GIT_NAME, email or DEFAULT_GIT_EMAIL


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    name, email = git_identity()
    env["GIT_AUTHOR_NAME"] = (os.environ.get("GIT_AUTHOR_NAME") or name).strip() or DEFAULT_GIT_NAME
    env["GIT_AUTHOR_EMAIL"] = (os.environ.get("GIT_AUTHOR_EMAIL") or email).strip() or DEFAULT_GIT_EMAIL
    env["GIT_COMMITTER_NAME"] = (os.environ.get("GIT_COMMITTER_NAME") or name).strip() or DEFAULT_GIT_NAME
    env["GIT_COMMITTER_EMAIL"] = (os.environ.get("GIT_COMMITTER_EMAIL") or email).strip() or DEFAULT_GIT_EMAIL
    return env


def certification_fields(audit: dict[str, Any]) -> dict[str, Any]:
    """Subset of audit flags for runner stdout, INDEX.jsonl, and manifests."""
    out: dict[str, Any] = {}
    for key in CERT_FLAG_KEYS:
        if key in audit:
            out[key] = audit[key]
    for extra in ("evidenceCoverageScope", "evidenceTemporalNote", "emptyCardReason"):
        if extra in audit and audit[extra] is not None:
            out[extra] = audit[extra]
    return out


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _s(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    rows.append(rec)
    except OSError:
        return []
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _looks_like_claim(rec: Any) -> bool:
    if not isinstance(rec, dict):
        return False
    return any(k in rec for k in ("semantic_scope", "claim_hash", "claim_value", "claimHash"))


def _read_claims(dest: Path) -> list[dict[str, Any]]:
    bundle = dest / "evidence_bundle.jsonl"
    if bundle.is_file():
        return _load_jsonl(bundle)
    evidence = dest / "evidence"
    if not evidence.is_dir():
        return []
    claims_path = evidence / "claims.json"
    if claims_path.is_file():
        data = _load_json(claims_path)
        if isinstance(data, list):
            return [x for x in data if _looks_like_claim(x)]
        if _looks_like_claim(data):
            return [data]
    out: list[dict[str, Any]] = []
    for path in sorted(evidence.glob("*.json")):
        if path.name in SKIP_EVIDENCE_JSON or path.name == "claims.json":
            continue
        data = _load_json(path)
        if isinstance(data, list):
            out.extend(x for x in data if _looks_like_claim(x))
        elif _looks_like_claim(data):
            out.append(data)
    return out


def _read_requests(dest: Path) -> list[dict[str, Any]]:
    data = _load_json(dest / "research_requests.json")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict) and isinstance(data.get("requests"), list):
        return [x for x in data["requests"] if isinstance(x, dict)]
    checkpoint = _load_json(dest / "checkpoint.json") or {}
    if isinstance(checkpoint, dict):
        for key in ("researchRequests", "research_requests", "requests"):
            rows = checkpoint.get(key)
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]
    for name in ("research_plan.json", "host_research_plan.json"):
        plan = _load_json(dest / name)
        if isinstance(plan, list):
            return [x for x in plan if isinstance(x, dict)]
        if isinstance(plan, dict) and isinstance(plan.get("requests"), list):
            return [x for x in plan["requests"] if isinstance(x, dict)]
    return []


def _read_card(dest: Path) -> list[dict[str, Any]]:
    data = _load_json(dest / "strict_card.json")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("picks", "card", "locks", "rows"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]
    return []


def pick_to_requests(pick: dict[str, Any], all_requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match a slim() pick (or full row) onto planned research requests.

    slim() fields: player, event, projectionId, league, market, line, direction.
    Full rows also have playerId, eventId, teamId, boardId.
    """
    player_id = _s(pick.get("playerId") or pick.get("player_id"))
    player_name = _s(pick.get("playerName") or pick.get("player"))
    event_id = _s(pick.get("eventId") or pick.get("event_id"))
    event_label = _s(pick.get("eventLabel") or pick.get("event"))
    projection_id = _s(pick.get("projectionId") or pick.get("projection_id"))
    market = _s(pick.get("market"))
    league = _s(pick.get("league"))
    offer_id = _s(pick.get("offerId") or pick.get("offer_id") or pick.get("offer"))
    team_id = _s(pick.get("teamId") or pick.get("team_id"))
    definition_id = _s(
        pick.get("definitionId") or pick.get("definition_id") or pick.get("marketDefinitionId")
    )

    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for req in all_requests:
        if not isinstance(req, dict):
            continue
        scope = _s(req.get("scope"))
        sid = _s(req.get("scope_id") or req.get("scopeId"))
        rid = _s(req.get("request_id") or req.get("requestId") or f"{scope}:{sid}")
        hit = False
        if scope == "PLAYER":
            name = _s(req.get("name"))
            if player_id and sid == player_id:
                hit = True
            elif player_name and (sid == player_name or name == player_name or name == player_id):
                hit = True
        elif scope == "EVENT":
            label = _s(req.get("label"))
            if event_id and sid == event_id:
                hit = True
            elif event_label and (sid == event_label or label == event_label):
                hit = True
        elif scope in {"MARKET_DEFINITION", "MARKET"}:
            req_market = _s(req.get("market"))
            req_league = _s(req.get("league"))
            if definition_id and sid == definition_id:
                hit = True
            elif market and (sid == market or req_market == market):
                if not league or not req_league or req_league == league:
                    hit = True
        elif scope == "OFFER":
            if projection_id and sid == projection_id:
                hit = True
            elif offer_id and sid == offer_id:
                hit = True
        elif scope == "TEAM":
            if team_id and sid == team_id:
                hit = True
        if hit and rid not in seen:
            seen.add(rid)
            matched.append(req)
    return matched


def _covering_claims(pick_requests: list[dict[str, Any]], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = {
        (_s(req.get("scope")), _s(req.get("scope_id") or req.get("scopeId")))
        for req in pick_requests
    }
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for claim in claims:
        key = (_s(claim.get("semantic_scope")), _s(claim.get("scope_id")))
        if key not in keys:
            continue
        digest = _s(claim.get("claim_hash") or claim.get("claimHash")) or content_hash(claim)
        if digest in seen:
            continue
        seen.add(digest)
        out.append(claim)
    return out


def _player_logs_or_status_missing(player_rows: list[dict[str, Any]]) -> bool:
    if not player_rows:
        return True
    for row in player_rows:
        missing = row.get("missing") or []
        if not row.get("complete"):
            if any(
                code in missing
                for code in ("PLAYER_STATUS", "ROLE_COMPARABLE_GAME_LOGS_MIN_3", "EVIDENCE_CLAIM")
            ):
                return True
            if not missing:
                return True
        if any(
            code in missing
            for code in ("PLAYER_STATUS", "ROLE_COMPARABLE_GAME_LOGS_MIN_3", "EVIDENCE_CLAIM")
        ):
            return True
    return False


def evaluate_pick_evidence(
    pick: dict[str, Any],
    claims: list[dict[str, Any]],
    requests: list[dict[str, Any]],
) -> dict[str, Any]:
    matched = pick_to_requests(pick, requests)
    report = coverage_report(matched, claims)
    matched_scopes = {_s(r.get("scope")) for r in matched}
    has_player = "PLAYER" in matched_scopes
    has_event = "EVENT" in matched_scopes
    has_market = bool(matched_scopes & {"MARKET_DEFINITION", "MARKET", "OFFER"})
    structural = has_player and has_event and has_market and bool(matched)
    player_rows = [row for row in report.get("requests") or [] if _s(row.get("scope")) == "PLAYER"]
    missing: list[str] = []
    for row in report.get("requests") or []:
        missing.extend(str(m) for m in (row.get("missing") or []))
    if not has_player:
        missing.append("PLAYER_REQUEST")
    if not has_event:
        missing.append("EVENT_REQUEST")
    if not has_market:
        missing.append("MARKET_OR_OFFER_REQUEST")
    # Preserve evaluate_request detail for reviewers while still requiring the lock trio.
    complete = bool(report.get("complete")) and structural and not missing
    covering = _covering_claims(matched, claims)
    hashes = [_s(c.get("claim_hash") or c.get("claimHash")) for c in covering]
    hashes = [h for h in hashes if h]
    urls = [_s(c.get("url")) for c in covering if _s(c.get("url"))]
    hallucination = (not claims) or _player_logs_or_status_missing(player_rows) or not has_player
    return {
        "projectionId": pick.get("projectionId") or pick.get("projection_id"),
        "player": pick.get("player") or pick.get("playerName"),
        "market": pick.get("market"),
        "line": pick.get("line"),
        "direction": pick.get("direction") or pick.get("selectedSide") or pick.get("side"),
        "coveringClaimHashes": hashes,
        "urls": urls,
        "coverage": {
            "complete": complete,
            "missing": missing,
            "requests": report.get("requests") or [],
        },
        "hallucinationRisk": bool(hallucination),
        "matchedRequestCount": len(matched),
        "matchedScopes": sorted(matched_scopes),
    }


def _is_fixture_mode(evidence_mode: Any) -> bool:
    mode = _s(evidence_mode).lower()
    if not mode:
        return False
    if "fixture" in mode:
        return True
    return False


def _is_manual_evidence(evidence_mode: Any) -> bool:
    return _s(evidence_mode).lower() in MANUAL_EVIDENCE_MODES


def _parse_iso(value: Any) -> datetime | None:
    s = _s(value)
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _picks_coverage_complete(audit: dict[str, Any]) -> bool:
    card_size = int(audit.get("cardSize") or 0)
    picks = audit.get("picks") or audit.get("pickEvidence") or []
    if not isinstance(picks, list):
        picks = []
    if card_size <= 0:
        return False
    if int(audit.get("claimCount") or 0) <= 0:
        return False
    if not picks:
        return False
    for pick in picks:
        if not isinstance(pick, dict):
            return False
        coverage = pick.get("coverage") or {}
        if not coverage.get("complete"):
            return False
        if pick.get("hallucinationRisk"):
            return False
    return True


def _hash_certified_python_freeze(audit: dict[str, Any]) -> bool:
    run_state = _s(audit.get("runState"))
    frozen = _s(audit.get("frozenForecastHash"))
    if not frozen:
        return False
    if run_state in MANUAL_STATES:
        return False
    if run_state not in PYTHON_FREEZE_STATES:
        return False
    if audit.get("softwareFreeze") is False:
        return False
    return True


def _model_run_certified(audit: dict[str, Any]) -> bool:
    run_state = _s(audit.get("runState"))
    if run_state in MANUAL_STATES:
        return False
    if audit.get("softwareFreeze") is False:
        return False
    if not _hash_certified_python_freeze(audit):
        return False
    if run_state not in PYTHON_FREEZE_STATES:
        return False
    stages = {str(s) for s in (audit.get("completedStages") or [])}
    software_e2e = bool(audit.get("softwareE2eComplete"))
    frozen = _s(audit.get("frozenForecastHash"))
    stages_ok = REQUIRED_MODEL_STAGES.issubset(stages) or (software_e2e and bool(frozen))
    if not stages_ok:
        return False
    if _is_manual_evidence(audit.get("evidenceMode")):
        return False
    if not bool(audit.get("synthetic")) and _is_fixture_mode(audit.get("evidenceMode")):
        return False
    return True


def _evidence_coverage_certified(audit: dict[str, Any], *, research_ran: bool) -> bool:
    card_size = int(audit.get("cardSize") or 0)
    if card_size == 0:
        return bool(research_ran)
    return _picks_coverage_complete(audit)


def _evidence_temporal(audit: dict[str, Any], claims: list[dict[str, Any]]) -> tuple[bool, str | None]:
    cutoff = _parse_iso(audit.get("forecastDecisionCutoff") or audit.get("forecastCutoff"))
    capture = _parse_iso(audit.get("boardCaptureTime"))
    created = _parse_iso(audit.get("createdAtUtc"))
    if not claims:
        return True, None
    for claim in claims:
        if not isinstance(claim, dict):
            return False, "non-dict claim"
        observed = _parse_iso(claim.get("observed_at") or claim.get("observedAt"))
        published = _parse_iso(claim.get("published_at") or claim.get("publishedAt"))
        if observed is None or published is None:
            return False, "claim missing observed_at or published_at"
        if cutoff is not None:
            if observed > cutoff or published > cutoff:
                return False, "claim observed_at/published_at after forecastDecisionCutoff"
        if capture is not None and observed < capture:
            post_capture = False
            if created is not None and created > capture:
                post_capture = True
            if _is_manual_evidence(audit.get("evidenceMode")):
                post_capture = True
            if bool(audit.get("postCaptureResearch")):
                post_capture = True
            if post_capture:
                return (
                    False,
                    "observed_at backdated before HAR capture while research happened after capture",
                )
    return True, None


def _empty_card_reason(audit: dict[str, Any], *, research_ran: bool) -> str | None:
    if int(audit.get("cardSize") or 0) != 0:
        return None
    if not research_ran:
        return "EMPTY_RESEARCH_INCOMPLETE"
    if not bool(audit.get("productionRootCertified")):
        return "EMPTY_ROOT_NOT_CERTIFIED"
    playable = audit.get("playable")
    try:
        playable_n = int(playable) if playable is not None else 0
    except (TypeError, ValueError):
        playable_n = 0
    if playable_n <= 0:
        return "EMPTY_NO_PLAYABLES"
    return "EMPTY_PORTFOLIO_CONSTRAINT"


def compute_certification(
    audit: dict[str, Any],
    *,
    claims: list[dict[str, Any]] | None = None,
    research_ran: bool | None = None,
    secrets_blocked: bool = False,
    hashes_present: bool | None = None,
) -> dict[str, Any]:
    """Compute split canonical certification flags; no combined lock state."""
    claims = list(claims or [])
    if research_ran is None:
        stages = {str(s) for s in (audit.get("completedStages") or [])}
        research_ran = (
            "RESEARCH" in stages
            or bool(audit.get("researchComplete"))
            or bool(audit.get("softwareE2eComplete"))
            or int(audit.get("claimCount") or 0) > 0
            or int(audit.get("requestCount") or 0) > 0
            or bool(claims)
        )
    if hashes_present is None:
        hashes_present = bool(_s(audit.get("frozenForecastHash")) or audit.get("boardHash") or audit.get("harSha256"))

    hash_certified = _hash_certified_python_freeze(audit)
    model_run = _model_run_certified(audit)
    coverage = _evidence_coverage_certified(audit, research_ran=research_ran)
    temporal_ok, temporal_note = _evidence_temporal(audit, claims)
    production_root = bool(audit.get("productionSelectionReady")) and bool(audit.get("systemCertified"))
    lr = _s(audit.get("learningRevision") or LEARNING_REVISION)
    pc = _s(audit.get("predictiveClaim") or PREDICTIVE_CLAIM)
    predictive = False if lr == "LR000000" or pc == "NONE" else bool(audit.get("predictiveValidationEarned"))
    selection = bool(model_run) and bool(hash_certified) and _s(audit.get("runState")) not in MANUAL_STATES
    archive_integrity = bool(hashes_present) and not secrets_blocked
    flags: dict[str, Any] = {
        "archiveIntegrityCertified": archive_integrity,
        "evidenceCoverageCertified": coverage,
        "evidenceCoverageScope": "card_only_not_population",
        "evidenceTemporalCertified": temporal_ok,
        "modelRunCertified": model_run,
        "selectionCertified": selection,
        "productionRootCertified": production_root,
        "predictiveValidationEarned": predictive,
        "hashCertifiedPythonFreeze": hash_certified,
    }
    if temporal_note:
        flags["evidenceTemporalNote"] = temporal_note
    empty_reason = _empty_card_reason({**audit, **flags}, research_ran=research_ran)
    if empty_reason:
        flags["emptyCardReason"] = empty_reason
    return flags


def locks_certified(audit: dict[str, Any]) -> bool:
    """Compatibility helper only; the combined value is not stored canonically."""
    flags = compute_certification(audit, claims=[], research_ran=True)
    return (
        bool(flags.get("modelRunCertified"))
        and bool(flags.get("selectionCertified"))
        and bool(flags.get("evidenceCoverageCertified"))
    )


def _render_run_audit_md(audit: dict[str, Any], picks: list[dict[str, Any]]) -> str:
    run_id = audit.get("runId") or "UNKNOWN"
    lines = [
        f"# DCM run {run_id}",
    ]
    if not audit.get("modelRunCertified"):
        lines.append("**NOT a Python DCM freeze. Do not treat this card as a DCM pick unless modelRunCertified is true.**")
    lines.extend([
        f"- software: {audit.get('software')}, learningRevision: {audit.get('learningRevision')}, predictiveClaim: {audit.get('predictiveClaim')}",
        f"- forecastCutoff: {audit.get('forecastCutoff')}, harSha256: {audit.get('harSha256')}, boardHash: {audit.get('boardHash')}, frozenForecastHash: {audit.get('frozenForecastHash')}",
        f"- runState: {audit.get('runState')}, researchComplete: {audit.get('researchComplete')}, evidenceMode: {audit.get('evidenceMode')}, productionResearchComplete: {audit.get('productionResearchComplete')}",
        f"- BEFORE: researchRequested: {audit.get('researchRequested')}, request count: {audit.get('requestCount')}",
        f"- AFTER: playable: {audit.get('playable')}, cardSize: {audit.get('cardSize')}, hallucinationRisk: {audit.get('hallucinationRisk')}",
        f"- modelRunCertified: {audit.get('modelRunCertified')}, selectionCertified: {audit.get('selectionCertified')}, evidenceCoverageCertified: {audit.get('evidenceCoverageCertified')}",
        f"- evidenceTemporalCertified: {audit.get('evidenceTemporalCertified')}, archiveIntegrityCertified: {audit.get('archiveIntegrityCertified')}, productionRootCertified: {audit.get('productionRootCertified')}",
        f"- predictiveValidationEarned: {audit.get('predictiveValidationEarned')}, hashCertifiedPythonFreeze: {audit.get('hashCertifiedPythonFreeze')}",
        "",
        "## Card",
    ])
    if not picks:
        lines.append("- (empty card)")
    for pick in picks:
        coverage = pick.get("coverage") or {}
        complete = "yes" if coverage.get("complete") else "no"
        missing = coverage.get("missing") or []
        hashes = pick.get("coveringClaimHashes") or []
        urls = pick.get("urls") or []
        lines.append(
            "- {player} | {market} | {line} | {side} | claims={claims} | urls={urls} | complete={complete} | missing={missing}".format(
                player=pick.get("player") or "?",
                market=pick.get("market") or "?",
                line=pick.get("line"),
                side=pick.get("direction") or "?",
                claims=",".join(str(h) for h in hashes) or "none",
                urls=",".join(str(u) for u in urls) or "none",
                complete=complete,
                missing=",".join(str(m) for m in missing) or "none",
            )
        )
    lines.append("")
    lines.append("## Failures")
    failures = [p for p in picks if not ((p.get("coverage") or {}).get("complete"))]
    if not failures:
        lines.append("- none")
    else:
        for pick in failures:
            coverage = pick.get("coverage") or {}
            missing = coverage.get("missing") or []
            lines.append(
                f"- {pick.get('projectionId')} {pick.get('player')} {pick.get('market')} missing={','.join(str(m) for m in missing) or 'none'}"
            )
    lines.append("")
    return "\n".join(lines)


def build_run_audit(dest: Path) -> dict[str, Any]:
    dest = Path(dest)
    freeze = _load_json(dest / "frozen_forecast.json") or _load_json(dest / "freeze.json") or {}
    if not isinstance(freeze, dict):
        freeze = {}
    checkpoint = _load_json(dest / "checkpoint.json") or {}
    if not isinstance(checkpoint, dict):
        checkpoint = {}
    hashes = _load_json(dest / "hashes.json") or {}
    if not isinstance(hashes, dict):
        hashes = {}
    accounting = _load_json(dest / "accounting.json") or {}
    if not isinstance(accounting, dict):
        accounting = {}
    ingest = _load_json(dest / "input_manifest.json") or {}
    if not isinstance(ingest, dict):
        ingest = {}
    integrity = _load_json(dest / "run_integrity.json") or {}
    if not isinstance(integrity, dict):
        integrity = {}
    readiness = _load_json(dest / "production_readiness.json") or {}
    if not isinstance(readiness, dict):
        readiness = {}
    claims = _read_claims(dest)
    requests = _read_requests(dest)
    card = _read_card(dest)

    run_id = (
        freeze.get("runId")
        or checkpoint.get("runId")
        or integrity.get("runId")
        or dest.name
    )
    stages = list(checkpoint.get("completedStages") or freeze.get("completedStages") or [])
    synthetic = bool(
        ingest.get("synthetic")
        or freeze.get("synthetic")
        or integrity.get("synthetic")
        or dest.name.lower().endswith("_synthetic")
    )
    card_size = freeze.get("cardSize")
    if card_size is None:
        card_size = len(card)
    try:
        card_size = int(card_size)
    except (TypeError, ValueError):
        card_size = len(card)

    pick_rows = [evaluate_pick_evidence(pick, claims, requests) for pick in card]
    research_ran = (
        "RESEARCH" in {str(s) for s in stages}
        or bool(freeze.get("researchComplete"))
        or bool(freeze.get("softwareE2eComplete"))
        or bool(claims)
        or bool(requests)
    )
    if card_size == 0:
        hallucination = False if research_ran else True
    else:
        hallucination = (not claims) or any(bool(p.get("hallucinationRisk")) for p in pick_rows)

    audit: dict[str, Any] = {
        "runId": run_id,
        "software": freeze.get("dcmVersion") or freeze.get("software") or SOFTWARE,
        "learningRevision": freeze.get("learningRevision") or LEARNING_REVISION,
        "predictiveClaim": freeze.get("predictiveClaim") or PREDICTIVE_CLAIM,
        "forecastCutoff": freeze.get("forecastCutoff") or checkpoint.get("forecastCutoff"),
        "harSha256": freeze.get("harSha256") or hashes.get("harSha256") or ingest.get("harSha256"),
        "boardHash": freeze.get("boardHash") or hashes.get("boardHash"),
        "frozenForecastHash": freeze.get("frozenForecastHash") or hashes.get("frozenForecastHash"),
        "runState": freeze.get("runState") or integrity.get("runState") or checkpoint.get("runState"),
        "researchComplete": freeze.get("researchComplete"),
        "evidenceMode": freeze.get("evidenceMode") or freeze.get("evidence_mode"),
        "productionResearchComplete": freeze.get("productionResearchComplete"),
        "researchRequested": freeze.get("researchRequested"),
        "requestCount": len(requests),
        "playable": freeze.get("playable"),
        "cardSize": card_size,
        "claimCount": len(claims),
        "synthetic": synthetic,
        "softwareE2eComplete": bool(freeze.get("softwareE2eComplete")),
        "softwareFreeze": freeze.get("softwareFreeze"),
        "completedStages": stages,
        "picks": pick_rows,
        "pickEvidence": pick_rows,
        "createdAtUtc": _now_utc(),
        "hallucinationRisk": bool(hallucination),
        "forecastDecisionCutoff": freeze.get("forecastDecisionCutoff")
        or freeze.get("forecastCutoff")
        or checkpoint.get("forecastCutoff"),
        "boardCaptureTime": (
            freeze.get("boardCaptureTime")
            or ingest.get("captureStart")
            or ingest.get("startedDateTime")
            or ingest.get("harStartedDateTime")
        ),
        "productionSelectionReady": bool(
            freeze.get("productionSelectionReady")
            if freeze.get("productionSelectionReady") is not None
            else readiness.get("productionSelectionReady")
        ),
        "systemCertified": bool(
            freeze.get("systemCertified")
            if freeze.get("systemCertified") is not None
            else readiness.get("systemCertified")
        ),
        "postCaptureResearch": bool(freeze.get("postCaptureResearch")),
    }
    secrets_blocked = False
    for name in PACK_FILES:
        src = dest / name
        if src.is_file() and scan_for_secrets(src):
            secrets_blocked = True
            break
    hashes_present = bool(
        (dest / "hashes.json").is_file()
        or _s(audit.get("frozenForecastHash"))
        or _s(audit.get("boardHash"))
    )
    audit.update(
        compute_certification(
            audit,
            claims=claims,
            research_ran=research_ran,
            secrets_blocked=secrets_blocked,
            hashes_present=hashes_present,
        )
    )

    audit_dir = dest / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    cert = certification_fields(audit)
    pick_payload = {
        "runId": run_id,
        "hallucinationRisk": audit["hallucinationRisk"],
        "cardSize": card_size,
        "claimCount": len(claims),
        "picks": pick_rows,
        "failures": [p for p in pick_rows if not ((p.get("coverage") or {}).get("complete"))],
        **cert,
    }
    manifest = {
        "schema": "pillars_dcm.run_archive_manifest.v6",
        "runId": run_id,
        "createdAtUtc": audit["createdAtUtc"],
        "hallucinationRisk": audit["hallucinationRisk"],
        "sourceDest": str(dest),
        "claimCount": len(claims),
        "requestCount": len(requests),
        "cardSize": card_size,
        "runState": audit.get("runState"),
        "evidenceMode": audit.get("evidenceMode"),
        "synthetic": synthetic,
        **cert,
    }
    (audit_dir / "RUN_AUDIT.md").write_text(_render_run_audit_md(audit, pick_rows), encoding="utf-8")
    _write_json(audit_dir / "pick_evidence.json", pick_payload)
    _write_json(audit_dir / "archive_manifest.json", manifest)
    return audit


def _is_forbidden(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(".har") or name.endswith(".har.gz") or name.endswith(".har.zip") or name.endswith(".har.json"):
        return True
    if name.endswith(".sqlite") or name.endswith(".sqlite3"):
        return True
    if name in FORBIDDEN_NAMES:
        return True
    if any(part.lower() in FORBIDDEN_DIR_PARTS for part in path.parts):
        return True
    lowered = name.replace("-", "_")
    if any(token in lowered for token in SECRET_SUBSTR):
        return True
    return False


def _copy_file(src: Path, dest: Path) -> bool:
    if not src.is_file() or _is_forbidden(src):
        return False
    if scan_for_secrets(src):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def _file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_github_pack(dest: Path, repo_root: Path) -> Path:
    dest = Path(dest)
    repo_root = Path(repo_root)
    freeze = _load_json(dest / "frozen_forecast.json") or _load_json(dest / "freeze.json") or {}
    checkpoint = _load_json(dest / "checkpoint.json") or {}
    run_id = _s((freeze or {}).get("runId") or (checkpoint or {}).get("runId") or dest.name)
    pack = repo_root / "audit" / "runs" / run_id
    pack.mkdir(parents=True, exist_ok=True)

    copied: list[dict[str, Any]] = []
    skipped: list[str] = []

    audit_dir = dest / "audit"
    for name in ("RUN_AUDIT.md", "pick_evidence.json", "archive_manifest.json"):
        src = audit_dir / name
        if src.is_file() and _copy_file(src, pack / name):
            copied.append({"name": name, "bytes": src.stat().st_size, "sha256": _file_sha256(pack / name)})
        elif (dest / name).is_file() and _copy_file(dest / name, pack / name):
            copied.append({"name": name, "bytes": (dest / name).stat().st_size, "sha256": _file_sha256(pack / name)})

    for name in PACK_FILES:
        if name in {"RUN_AUDIT.md", "pick_evidence.json", "archive_manifest.json"}:
            continue
        src = dest / name
        if not src.exists():
            continue
        if _is_forbidden(src):
            skipped.append(name)
            continue
        if src.is_dir():
            skipped.append(name)
            continue
        if _copy_file(src, pack / name):
            copied.append({"name": name, "bytes": src.stat().st_size, "sha256": _file_sha256(pack / name)})

    board = dest / "board.json"
    if board.is_file() and not _is_forbidden(board):
        size = board.stat().st_size
        if size <= BOARD_MAX_BYTES:
            if _copy_file(board, pack / "board.json"):
                copied.append({"name": "board.json", "bytes": size, "sha256": _file_sha256(pack / "board.json")})
        else:
            payload = _load_json(board) or {}
            rows = payload.get("rows") if isinstance(payload, dict) else None
            summary = {
                "omitted": True,
                "reason": "board.json exceeds 2MB; storing counts + contentHash only",
                "bytes": size,
                "contentHash": (payload.get("contentHash") if isinstance(payload, dict) else None)
                or content_hash(payload),
                "rowCount": len(rows) if isinstance(rows, list) else None,
                "accounting": payload.get("accounting") if isinstance(payload, dict) else None,
                "forecastCutoff": payload.get("forecastCutoff") if isinstance(payload, dict) else None,
            }
            _write_json(pack / "board_summary.json", summary)
            copied.append(
                {
                    "name": "board_summary.json",
                    "bytes": (pack / "board_summary.json").stat().st_size,
                    "sha256": _file_sha256(pack / "board_summary.json"),
                }
            )
            skipped.append("board.json")

    # Belt-and-suspenders: never leave a forbidden artifact even if dest layout changes.
    for leftover in list(pack.rglob("*")):
        if leftover.is_file() and _is_forbidden(leftover):
            skipped.append(str(leftover.relative_to(pack)))
            leftover.unlink()

    pack_manifest = {
        "schema": "pillars_dcm.github_pack_manifest.v6",
        "runId": run_id,
        "createdAtUtc": _now_utc(),
        "sourceDest": str(dest),
        "files": copied,
        "skipped": sorted(set(skipped)),
        "excludes": ["*.har", "index.sqlite", "population_full.jsonl", "full_population.jsonl", "worlds", "cookie/token/authorization"],
    }
    _write_json(pack / "archive_manifest.json", pack_manifest)
    return pack


def append_index(repo_root: Path, entry: dict[str, Any]) -> Path:
    repo_root = Path(repo_root)
    path = repo_root / "audit" / "INDEX.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return path


def _git(repo_root: Path, args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=check,
        env=_git_env(),
    )


def _sanitize_git_error(text: str) -> str:
    lowered = (text or "").strip()
    if not lowered:
        return "git command failed"
    for token in SECRET_SUBSTR:
        if token in lowered.lower():
            return "git command failed (details omitted; possible secret in remote output)"
    # Keep it short and non-secret: first line only.
    first = lowered.splitlines()[0]
    return first[:300]


def push_to_github(repo_root: Path, run_id: str, *, push: bool) -> dict[str, Any]:
    repo_root = Path(repo_root)
    rel_run = f"audit/runs/{run_id}"
    result: dict[str, Any] = {
        "commit": None,
        "remote": None,
        "path": rel_run,
        "pushed": False,
    }
    try:
        remote = _git(repo_root, ["remote", "get-url", "origin"])
        if remote.returncode == 0:
            url = (remote.stdout or "").strip()
            # Never return a URL that might embed a token.
            host = url.split("://", 1)[-1]
            userinfo = host.rsplit("@", 1)[0] if "@" in host else ""
            if any(token in url.lower() for token in SECRET_SUBSTR) or (userinfo and ":" in userinfo):
                result["remote"] = "origin"
            else:
                result["remote"] = url or "origin"
        else:
            result["remote"] = "origin"

        paths = [rel_run, "audit/INDEX.jsonl", "audit/README.md"]
        existing = [p for p in paths if (repo_root / p).exists()]
        if not existing:
            result["error"] = "nothing to add"
            return result
        added = _git(repo_root, ["add", "--", *existing])
        if added.returncode != 0:
            result["error"] = _sanitize_git_error(added.stderr or added.stdout)
            return result
        porcelain = _git(repo_root, ["status", "--porcelain", "--", *existing])
        if porcelain.returncode != 0:
            result["error"] = _sanitize_git_error(porcelain.stderr or porcelain.stdout)
            return result
        if porcelain.stdout.strip():
            name, email = git_identity()
            commit = _git(
                repo_root,
                [
                    "-c",
                    f"user.name={name}",
                    "-c",
                    f"user.email={email}",
                    "commit",
                    "-m",
                    f"Archive DCM run {run_id}",
                ],
            )
            if commit.returncode != 0:
                result["error"] = _sanitize_git_error(commit.stderr or commit.stdout)
                return result
        head = _git(repo_root, ["rev-parse", "HEAD"])
        if head.returncode == 0:
            result["commit"] = (head.stdout or "").strip() or None
        if push:
            pushed = _git(repo_root, ["push", "origin", "HEAD"])
            if pushed.returncode != 0:
                result["error"] = _sanitize_git_error(pushed.stderr or pushed.stdout)
                result["pushed"] = False
                return result
            result["pushed"] = True
        return result
    except OSError as exc:
        result["error"] = "git unavailable"
        result["exceptionType"] = type(exc).__name__
        return result
    except Exception as exc:  # noqa: BLE001 — archive must never crash a DCM run
        result["error"] = "archive git step failed"
        result["exceptionType"] = type(exc).__name__
        return result
