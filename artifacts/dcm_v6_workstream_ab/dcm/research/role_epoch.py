"""RoleEpochBuilder: production constructor for role-comparable game samples.

Basketball: GS/starter flags, minutes change-points, teammate-out flags.
Gridiron: starter/depth, QB identity, snap/route/target/carry share change-points.
Never invents logs. Thin support raises priorWeight.
"""
from __future__ import annotations

from statistics import mean
from typing import Any

from dcm.research.gamelog import parse_gs, parse_numeric
from dcm.research.gridiron_gamelog import looks_like_gridiron_log, parse_numeric as _grid_num, normalize_gridiron_log

BUILDER_ID = "RoleEpochBuilder.v2-20260830"
PRIOR_N = 8.0
SEASON_DISCOUNT = 0.35
CHANGEPOINT_THRESHOLD = 8.0
MIN_SEGMENT = 3
STARTER_MINUTES = {"NBA": 24.0, "WNBA": 20.0, "NCAAB": 22.0, "NCAAW": 22.0}
GRIDIRON_LEAGUES = frozenset({"NFL", "CFB", "NFLP", "CFL", "UFL"})
STARTER_SNAPS = {"NFL": 40.0, "CFB": 35.0, "NFLP": 30.0}
STARTER_PASS_ATT = 18.0
GRIDIRON_CHANGEPOINT = 10.0
QB_ROLES = frozenset({"qb", "quarterback", "starter_qb", "backup_qb"})
DEPTH_ROLES = frozenset({"depth", "backup", "reserve", "second_unit", "second-unit", "bench"})

STARTER_ROLES = frozenset({"starter", "starting", "start", "started", "gs"})
BENCH_ROLES = frozenset({"bench", "reserve", "second_unit", "second-unit", "secondunit"})
POSITION_TOKENS = frozenset({
    "g", "guard", "f", "forward", "c", "center",
    "pg", "sg", "sf", "pf", "unknown", "unk",
})
TRUTHY = frozenset({"1", "true", "yes", "y", "out"})


def _as_logs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _raw(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("raw")
    return value if isinstance(value, dict) else {}


def _alias_minutes(row: dict[str, Any]) -> dict[str, Any]:
    """Expose Basketball-Reference MP as minutes without rejecting other sports."""
    parsed = parse_numeric(row.get("minutes"))
    if parsed is not None:
        out = dict(row)
        out["minutes"] = parsed
        return out
    for key in ("mp", "MP", "MIN", "min"):
        if key in row and row[key] is not None:
            parsed = parse_numeric(row[key])
            if parsed is not None:
                out = dict(row)
                out["minutes"] = parsed
                return out
    raw = _raw(row)
    for key in ("minutes", "mp", "MP", "MIN", "min"):
        if key in raw and raw[key] is not None:
            parsed = parse_numeric(raw[key])
            if parsed is not None:
                out = dict(row)
                out["minutes"] = parsed
                return out
    return row


def _teammate_out(row: dict[str, Any]) -> bool:
    for src in (row, _raw(row)):
        if src.get("teammate_out") is True or src.get("teammateOut") is True:
            return True
        for key in ("teammate_out", "teammateOut"):
            text = str(src.get(key) or "").strip().lower()
            if text in TRUTHY:
                return True
    return False


def _explicit_appearance(row: dict[str, Any]) -> str | None:
    """starter / bench from GS or role/appearance. None if unlabeled."""
    for src in (row, _raw(row)):
        for key in ("gs", "started", "starter"):
            if key in src and src[key] is not None:
                parsed = parse_gs(src[key])
                if parsed is not None:
                    return "starter" if parsed == 1 else "bench"
        role = str(src.get("role") or src.get("appearance") or "").strip().lower()
        if role in STARTER_ROLES:
            return "starter"
        if role in BENCH_ROLES:
            return "bench"
    return None


def _minutes_of(row: dict[str, Any]) -> float | None:
    return parse_numeric(row.get("minutes"))


def _date_key(row: dict[str, Any], index: int) -> tuple:
    raw = _raw(row)
    date = str(
        row.get("date")
        or row.get("gameDate")
        or row.get("date_game")
        or raw.get("date_game")
        or raw.get("date")
        or raw.get("gameDate")
        or ""
    )
    rk = str(raw.get("ranker") or raw.get("Rk") or row.get("rk") or "")
    return (date, rk, index)


def _starter_threshold(league: str | None) -> float:
    key = str(league or "").strip().upper()
    return STARTER_MINUTES.get(key, 22.0)


def _label_from_minutes(minutes: float, threshold: float) -> str:
    if minutes >= threshold:
        return "starter"
    if minutes >= 4.0:
        return "bench"
    return "other"


def detect_change_points(minutes: list[float], *, min_seg: int = MIN_SEGMENT, threshold: float = CHANGEPOINT_THRESHOLD) -> list[int]:
    """Greedy binary segmentation. Returns sorted start indices of segments (always includes 0)."""
    n = len(minutes)
    if n < min_seg * 2:
        return [0]

    def best_split(lo: int, hi: int) -> int | None:
        best_i = None
        best_gain = threshold
        span = hi - lo
        if span < min_seg * 2:
            return None
        for i in range(lo + min_seg, hi - min_seg + 1):
            left = minutes[lo:i]
            right = minutes[i:hi]
            if not left or not right:
                continue
            gain = abs(mean(left) - mean(right))
            if gain > best_gain:
                best_gain = gain
                best_i = i
        return best_i

    cuts = {0}
    queue = [(0, n)]
    max_splits = 6
    while queue and len(cuts) < max_splits + 1:
        lo, hi = queue.pop(0)
        idx = best_split(lo, hi)
        if idx is None:
            continue
        cuts.add(idx)
        queue.append((lo, idx))
        queue.append((idx, hi))
    return sorted(cuts)


def governed_change_points(values: list[float]) -> dict[str, Any]:
    """Execute cataloged RoleEpoch detectors. Does not silently rewrite greedy cuts.

    EWMA / CUSUM / Page-Hinkley are REQUIRED_CORE time-series algorithms.
    PELT remains a challenger (greedy binary segmentation is the portable fallback).
    """
    from dcm.algorithms.ml_families import cusum, ewma, page_hinkley

    series = [float(x) for x in values]
    greedy = detect_change_points(series)
    if not series:
        return {
            "greedy": greedy,
            "ewma": [],
            "cusum": [],
            "pageHinkley": [],
            "executed": ["ALG-ML-TIME-001", "ALG-ML-TIME-002", "ALG-ML-TIME-003"],
        }
    smoothed = ewma(series, alpha=0.3)
    return {
        "greedy": greedy,
        "ewma": [round(v, 6) for v in smoothed],
        "cusum": [int(i) for i in cusum(series)],
        "pageHinkley": [int(i) for i in page_hinkley(series)],
        "executed": ["ALG-ML-TIME-001", "ALG-ML-TIME-002", "ALG-ML-TIME-003"],
        "peltChallengerUnused": True,
    }


def shrinkage_weights(role_n: int, season_n: int) -> dict[str, float]:
    """role_sample → player_season → archetype/league prior. Sums to 1.

    Thin support (n=3) has a much larger priorWeight than n=30. Extra non-role
    season games contribute at SEASON_DISCOUNT so a two-game starter stint is
    not treated like a 30-game sample.
    """
    role_n = max(0, int(role_n))
    season_n = max(0, int(season_n))
    extra = max(0.0, float(season_n - role_n))
    total = float(role_n) + extra * SEASON_DISCOUNT + PRIOR_N
    if total <= 0:
        return {"roleWeight": 0.0, "seasonWeight": 0.0, "priorWeight": 1.0}
    return {
        "roleWeight": float(role_n) / total,
        "seasonWeight": (extra * SEASON_DISCOUNT) / total,
        "priorWeight": PRIOR_N / total,
    }


def partition_logs(
    logs: list[dict[str, Any]],
    *,
    claims: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    starter: list[dict[str, Any]] = []
    bench: list[dict[str, Any]] = []
    teammate_out: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []
    for row in logs:
        if _teammate_out(row):
            teammate_out.append(row)
            continue
        appearance = _explicit_appearance(row)
        if appearance == "starter":
            starter.append(row)
        elif appearance == "bench":
            bench.append(row)
        else:
            other.append(row)
    claim_roles = []
    for claim in claims or []:
        value = claim.get("claim_value")
        if isinstance(value, dict) and value.get("role"):
            claim_roles.append(str(value.get("role")))
    return {
        "starter": starter,
        "bench": bench,
        "teammate_out": teammate_out,
        "other": other,
        "claim_roles": claim_roles,
        "invented": False,
    }


def _projected_label(role: Any, teammate_out: bool) -> str | None:
    text = str(role or "").strip().lower()
    if text in {"starter_teammate_out"}:
        return "starter_teammate_out"
    if text in {"bench_teammate_out"}:
        return "bench"
    base = None
    if text in STARTER_ROLES:
        base = "starter"
    elif text in BENCH_ROLES:
        base = "bench"
    elif text in POSITION_TOKENS or not text:
        base = None
    if teammate_out:
        if base == "bench":
            return "bench"
        return "starter_teammate_out"
    return base


def _epoch_record(label: str, start: int, end: int, logs: list[dict[str, Any]]) -> dict[str, Any]:
    slice_logs = logs[start:end]
    minutes = [_minutes_of(r) for r in slice_logs]
    present = [m for m in minutes if m is not None]
    gs_flags = []
    for row in slice_logs:
        appearance = _explicit_appearance(row)
        if appearance == "starter":
            gs_flags.append(1)
        elif appearance == "bench":
            gs_flags.append(0)
    return {
        "label": label,
        "start": start,
        "end": end,
        "n": end - start,
        "minutes_mean": mean(present) if present else None,
        "gs_share": (mean(gs_flags) if gs_flags else None),
    }


def _strip_internal(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if not str(k).startswith("_")}



def _is_gridiron(ctx: dict[str, Any], value: dict[str, Any], logs: list[dict[str, Any]] | None = None) -> bool:
    family = str(ctx.get("sportFamily") or ctx.get("sport_family") or value.get("sportFamily") or value.get("family") or "").lower()
    if family in {"gridiron", "football"}:
        return True
    league = str(ctx.get("league") or value.get("league") or "").strip().upper()
    if league in GRIDIRON_LEAGUES:
        return True
    sample = logs if logs is not None else _as_logs(value.get("role_epoch_logs") or value.get("game_logs") or value.get("gameLogs"))
    football_hits = sum(1 for row in sample if looks_like_gridiron_log(row))
    return football_hits >= 2 and football_hits >= (len(sample) // 2 if sample else 0)


def _share_value(row: dict[str, Any]) -> float | None:
    """Primary share series: snaps, else routes, else targets, else pass_att, else rush_att."""
    for key in ("snaps", "routes", "targets", "pass_att", "rush_att"):
        parsed = parse_numeric(row.get(key))
        if parsed is not None:
            return float(parsed)
    pct = parse_numeric(row.get("snap_pct"))
    if pct is not None:
        return float(pct) * 100.0 if pct <= 1.0 else float(pct)
    return None


def _qb_id_of(row: dict[str, Any]) -> str | None:
    for src in (row, _raw(row)):
        for key in ("qb_id", "qb", "quarterback_id"):
            val = src.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
    return None


def _gridiron_appearance(row: dict[str, Any], *, is_qb: bool, starter_snap: float) -> str | None:
    explicit = _explicit_appearance(row)
    if is_qb:
        if explicit == "starter":
            return "starter_qb"
        if explicit == "bench":
            return "backup_qb"
        role = str(row.get("role") or _raw(row).get("role") or "").strip().lower()
        if role in {"starter_qb", "starting_qb"}:
            return "starter_qb"
        if role in {"backup_qb", "backup"}:
            return "backup_qb"
        pass_att = parse_numeric(row.get("pass_att"))
        if pass_att is not None:
            return "starter_qb" if pass_att >= STARTER_PASS_ATT else "backup_qb"
        share = _share_value(row)
        if share is not None:
            return "starter_qb" if share >= starter_snap else "backup_qb"
        return None
    if explicit:
        return "starter" if explicit == "starter" else "depth"
    role = str(row.get("role") or _raw(row).get("role") or "").strip().lower()
    if role in STARTER_ROLES:
        return "starter"
    if role in DEPTH_ROLES or role in BENCH_ROLES:
        return "depth"
    return None


def _gridiron_label_from_share(share: float, threshold: float, *, is_qb: bool) -> str:
    if is_qb:
        return "starter_qb" if share >= threshold else "backup_qb"
    if share >= threshold:
        return "starter"
    if share >= 8.0:
        return "depth"
    return "other"


def _projected_gridiron_label(role: Any, *, is_qb: bool) -> str | None:
    text = str(role or "").strip().lower()
    if is_qb:
        if text in {"backup", "backup_qb", "bench", "depth"}:
            return "backup_qb"
        if text in QB_ROLES or text in STARTER_ROLES or not text:
            return "starter_qb"
        return "starter_qb"
    if text in DEPTH_ROLES or text in BENCH_ROLES:
        return "depth"
    if text in STARTER_ROLES:
        return "starter"
    return "starter"


class RoleEpochBuilder:
    """Production role-epoch constructor. Builder id never contains 'stub'."""

    builder = BUILDER_ID

    def build(
        self,
        player_claim_value: dict[str, Any],
        claims: list[dict[str, Any]] | None = None,
        today_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ctx = dict(today_context or {})
        value = player_claim_value if isinstance(player_claim_value, dict) else {}
        if _is_gridiron(ctx, value):
            return self._build_gridiron(value, claims=claims, today_context=ctx)
        league = ctx.get("league") or value.get("league")
        raw_logs = _as_logs(value.get("role_epoch_logs") or value.get("game_logs") or value.get("gameLogs"))
        prepared: list[dict[str, Any]] = []
        for i, row in enumerate(raw_logs):
            aliased = _alias_minutes(row)
            minutes = _minutes_of(aliased)
            if minutes is None:
                continue
            item = dict(aliased)
            item["minutes"] = minutes
            item["_src"] = i
            prepared.append(item)
        prepared.sort(key=lambda r: _date_key(r, int(r.get("_src") or 0)))
        for i, row in enumerate(prepared):
            row["_idx"] = i

        threshold = _starter_threshold(str(league) if league else None)
        minutes_series = [float(row["minutes"]) for row in prepared]
        cuts = detect_change_points(minutes_series)
        governed = governed_change_points(minutes_series)

        per_game: list[str] = []
        for row in prepared:
            appearance = _explicit_appearance(row)
            tout = _teammate_out(row)
            if tout and (appearance == "starter" or appearance is None):
                per_game.append("starter_teammate_out")
            elif appearance:
                per_game.append(appearance)
            else:
                per_game.append("")  # fill from minutes / change-points

        n = len(prepared)
        cut_ends = list(cuts) + [n]
        for c, d in zip(cut_ends, cut_ends[1:]):
            unlabeled = [i for i in range(c, d) if not per_game[i]]
            if not unlabeled:
                continue
            seg_minutes = [minutes_series[i] for i in range(c, d)]
            seg_label = _label_from_minutes(mean(seg_minutes) if seg_minutes else 0.0, threshold)
            for i in unlabeled:
                per_game[i] = seg_label or "other"
        for i, label in enumerate(per_game):
            if not label:
                per_game[i] = _label_from_minutes(minutes_series[i], threshold)

        epochs: list[dict[str, Any]] = []
        if n:
            start = 0
            current = per_game[0]
            for i in range(1, n):
                if per_game[i] != current:
                    epochs.append(_epoch_record(current, start, i, prepared))
                    start = i
                    current = per_game[i]
            epochs.append(_epoch_record(current, start, n, prepared))

        tout_today = bool(ctx.get("teammate_out") or ctx.get("teammateOut") or value.get("teammate_out"))
        projected = _projected_label(
            ctx.get("projected_role") or ctx.get("role") or value.get("projected_role") or value.get("role"),
            tout_today,
        )
        selected = None
        if projected:
            matches = [e for e in epochs if e["label"] == projected]
            if not matches and projected == "starter_teammate_out":
                matches = [e for e in epochs if e["label"] == "starter"]
            if matches:
                selected = matches[-1]
        if selected is None and epochs:
            selected = epochs[-1]

        selected_label = selected["label"] if selected else None
        comparable: list[dict[str, Any]] = []
        if selected_label:
            for epoch in epochs:
                if epoch["label"] == selected_label:
                    comparable.extend(prepared[epoch["start"]:epoch["end"]])
        elif selected:
            comparable = prepared[selected["start"]:selected["end"]]

        support_n = len(comparable)
        weights = shrinkage_weights(support_n, n)
        parts = partition_logs(prepared, claims=claims)
        public_logs = [_strip_internal(r) for r in comparable]
        public_epochs = epochs

        return {
            "builder": BUILDER_ID,
            "log_count": n,
            "epochs": public_epochs,
            "selected_epoch": selected,
            "comparable_logs": public_logs,
            "support_n": support_n,
            "shrinkage": {
                "roleWeight": weights["roleWeight"],
                "seasonWeight": weights["seasonWeight"],
                "priorWeight": weights["priorWeight"],
            },
            "partitions": {k: [_strip_internal(r) for r in parts[k]] for k in ("starter", "bench", "teammate_out", "other")},
            "claim_roles": parts["claim_roles"],
            "invented": False,
            "projectedRole": projected,
            "governedChangePoints": governed,
        }

    def _build_gridiron(
        self,
        value: dict[str, Any],
        claims: list[dict[str, Any]] | None = None,
        today_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ctx = dict(today_context or {})
        league = str(ctx.get("league") or value.get("league") or "").upper() or None
        role_hint = str(ctx.get("projected_role") or ctx.get("role") or value.get("projected_role") or value.get("role") or "")
        is_qb = role_hint.strip().upper() in {"QB", "QUARTERBACK", "STARTER_QB", "BACKUP_QB"} or role_hint.strip().lower() in QB_ROLES
        raw_logs = _as_logs(value.get("role_epoch_logs") or value.get("game_logs") or value.get("gameLogs"))
        prepared: list[dict[str, Any]] = []
        for i, row in enumerate(raw_logs):
            normalized = normalize_gridiron_log(row, league=league) if isinstance(row, dict) else None
            item = dict(normalized or row)
            share = _share_value(item)
            if share is None:
                continue
            if not is_qb:
                # Infer QB identity from the log itself when role is unlabeled.
                pa = parse_numeric(item.get("pass_att"))
                if pa is not None and pa >= STARTER_PASS_ATT and parse_numeric(item.get("targets")) is None:
                    is_qb = True
            item["_share"] = share
            item["_src"] = i
            item["_qb_id"] = _qb_id_of(item)
            prepared.append(item)
        # Second pass: if majority of kept logs are QB-shaped, treat as QB.
        if not is_qb and prepared:
            qb_shaped = sum(1 for r in prepared if parse_numeric(r.get("pass_att")) is not None and (parse_numeric(r.get("pass_att")) or 0) >= 8)
            is_qb = qb_shaped >= max(2, len(prepared) // 2)
        prepared.sort(key=lambda r: _date_key(r, int(r.get("_src") or 0)))
        for i, row in enumerate(prepared):
            row["_idx"] = i

        threshold = STARTER_SNAPS.get(str(league or "").upper(), 35.0)
        share_series = [float(row["_share"]) for row in prepared]
        cuts = detect_change_points(share_series, threshold=GRIDIRON_CHANGEPOINT)
        governed = governed_change_points(share_series)

        # QB-identity cuts: new qb_id starts a segment.
        qb_cut = set(cuts)
        last_qb = None
        for i, row in enumerate(prepared):
            qid = row.get("_qb_id")
            if qid and last_qb is not None and qid != last_qb:
                qb_cut.add(i)
            if qid:
                last_qb = qid
        cuts = sorted(qb_cut) or [0]

        per_game: list[str] = []
        for row in prepared:
            label = _gridiron_appearance(row, is_qb=is_qb, starter_snap=threshold)
            per_game.append(label or "")

        n = len(prepared)
        cut_ends = list(cuts) + [n]
        for c, d in zip(cut_ends, cut_ends[1:]):
            unlabeled = [i for i in range(c, d) if not per_game[i]]
            if not unlabeled:
                continue
            seg = [share_series[i] for i in range(c, d)]
            seg_label = _gridiron_label_from_share(mean(seg) if seg else 0.0, threshold, is_qb=is_qb)
            for i in unlabeled:
                per_game[i] = seg_label
        for i, label in enumerate(per_game):
            if not label:
                per_game[i] = _gridiron_label_from_share(share_series[i], threshold, is_qb=is_qb)

        epochs: list[dict[str, Any]] = []
        if n:
            start = 0
            current = per_game[0]
            for i in range(1, n):
                if per_game[i] != current:
                    rec = _epoch_record(current, start, i, prepared)
                    rec["share_mean"] = mean(share_series[start:i]) if i > start else None
                    rec["qb_id"] = prepared[start].get("_qb_id")
                    epochs.append(rec)
                    start = i
                    current = per_game[i]
            rec = _epoch_record(current, start, n, prepared)
            rec["share_mean"] = mean(share_series[start:n]) if n > start else None
            rec["qb_id"] = prepared[start].get("_qb_id")
            epochs.append(rec)

        projected = _projected_gridiron_label(role_hint, is_qb=is_qb)
        selected = None
        if projected:
            matches = [e for e in epochs if e["label"] == projected]
            if not matches and projected == "starter_qb":
                matches = [e for e in epochs if e["label"] == "starter"]
            if matches:
                selected = matches[-1]
        if selected is None and epochs:
            selected = epochs[-1]

        selected_label = selected["label"] if selected else None
        comparable: list[dict[str, Any]] = []
        if selected_label:
            for epoch in epochs:
                if epoch["label"] == selected_label:
                    comparable.extend(prepared[epoch["start"]:epoch["end"]])
        elif selected:
            comparable = prepared[selected["start"]:selected["end"]]

        support_n = len(comparable)
        weights = shrinkage_weights(support_n, n)
        public_logs = [_strip_internal(r) for r in comparable]
        return {
            "builder": BUILDER_ID,
            "mode": "gridiron",
            "log_count": n,
            "epochs": epochs,
            "selected_epoch": selected,
            "comparable_logs": public_logs,
            "support_n": support_n,
            "shrinkage": {
                "roleWeight": weights["roleWeight"],
                "seasonWeight": weights["seasonWeight"],
                "priorWeight": weights["priorWeight"],
            },
            "partitions": {
                "starter": [_strip_internal(r) for r, lab in zip(prepared, per_game) if lab in {"starter", "starter_qb"}],
                "depth": [_strip_internal(r) for r, lab in zip(prepared, per_game) if lab in {"depth", "backup_qb"}],
                "other": [_strip_internal(r) for r, lab in zip(prepared, per_game) if lab not in {"starter", "starter_qb", "depth", "backup_qb"}],
            },
            "invented": False,
            "projectedRole": projected,
            "qbIdentity": is_qb,
            "qb_id": (selected or {}).get("qb_id") if selected else None,
            "governedChangePoints": governed,
        }


