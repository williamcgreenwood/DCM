"""Champion / challenger registry. Shadow-only in this PR. Never auto-promote.

Champion = current production probability path (software + LR000000).
Challengers persist as status=SHADOW. promote() hard-refuses LR / predictiveClaim changes.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE

REGISTRY_SCHEMA = "dcm.model_registry.v1-20260830"
CHAMPION_ID = "dcm.production.software+LR000000"
MIN_PROMOTE_N = 200
STATUS_SHADOW = "SHADOW"

HARD_REFUSE_LR = "LR_AND_PREDICTIVE_CLAIM_PROMOTION_HARD_REFUSED_THIS_PR"

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def champion_record() -> dict[str, Any]:
    return {
        "modelId": CHAMPION_ID,
        "role": "CHAMPION",
        "software": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "status": "PRODUCTION_PROBABILITY_PATH",
        "path": "frozen selectedP/calibratedP (apply_calibration inactive at LR000000)",
        "trainedWeights": False,
        "pkl": False,
        "neuralNet": False,
    }

def empty_registry() -> dict[str, Any]:
    return {
        "schema": REGISTRY_SCHEMA,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "software": SOFTWARE,
        "champion": champion_record(),
        "challengers": [],
        "autoPromote": False,
        "updatedAtUtc": _now(),
    }

def load_registry(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return empty_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_registry()
    if not isinstance(data, dict):
        return empty_registry()
    data.setdefault("champion", champion_record())
    data.setdefault("challengers", [])
    data["learningRevision"] = LEARNING_REVISION
    data["predictiveClaim"] = PREDICTIVE_CLAIM
    return data

def save_registry(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(data)
    data["updatedAtUtc"] = _now()
    data["learningRevision"] = LEARNING_REVISION
    data["predictiveClaim"] = PREDICTIVE_CLAIM
    data["autoPromote"] = False
    payload = {k: v for k, v in data.items() if k != "contentHash"}
    data["contentHash"] = content_hash(payload)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data

def register_challenger(
    path: Path,
    *,
    model_id: str,
    feature_schema_hash: str = "",
    training_cutoff: str = "",
    hyperparams: dict[str, Any] | None = None,
    train_metrics: dict[str, Any] | None = None,
    walkforward_metrics: dict[str, Any] | None = None,
    status: str = STATUS_SHADOW,
) -> dict[str, Any]:
    if status and status != STATUS_SHADOW:
        raise RuntimeError("CHALLENGER_MUST_REGISTER_AS_SHADOW")
    if not model_id or model_id == CHAMPION_ID:
        raise RuntimeError("CHALLENGER_ID_INVALID")
    reg = load_registry(path)
    rec = {
        "modelId": model_id,
        "featureSchemaHash": feature_schema_hash,
        "trainingCutoff": training_cutoff,
        "hyperparams": hyperparams or {},
        "trainMetrics": train_metrics or {},
        "walkforwardMetrics": walkforward_metrics or {},
        "status": STATUS_SHADOW,
        "role": "CHALLENGER",
        "trainedNeuralNet": False,
        "pkl": False,
        "production": False,
        "registeredAtUtc": _now(),
        "note": "SHADOW only. Does not replace the production probability path.",
    }
    others = [c for c in (reg.get("challengers") or []) if isinstance(c, dict) and c.get("modelId") != model_id]
    others.append(rec)
    reg["challengers"] = others
    save_registry(path, reg)
    return rec

def _metric(block: dict[str, Any] | None, key: str) -> float | None:
    if not isinstance(block, dict):
        return None
    nested = block.get("metrics") if isinstance(block.get("metrics"), dict) else block
    val = nested.get(key) if isinstance(nested, dict) else None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None

def propose_promotion(path: Path, challenger_id: str) -> dict[str, Any]:
    """Return BLOCKED with reasons unless N / Brier / logloss / subgroup placeholders pass.

    Passing the numeric gates still does not change champion, LR, or predictiveClaim.
    """
    reg = load_registry(path)
    chal = next((c for c in (reg.get("challengers") or []) if isinstance(c, dict) and c.get("modelId") == challenger_id), None)
    reasons: list[str] = []
    if chal is None:
        reasons.append("CHALLENGER_NOT_FOUND")
        return {"status": "BLOCKED", "challengerId": challenger_id, "reasons": reasons, "lrUnchanged": LEARNING_REVISION, "predictiveClaimUnchanged": PREDICTIVE_CLAIM}
    wf = chal.get("walkforwardMetrics") if isinstance(chal.get("walkforwardMetrics"), dict) else {}
    champ_wf = (reg.get("champion") or {}).get("walkforwardMetrics") if isinstance(reg.get("champion"), dict) else {}
    n = _metric(wf, "n") or 0.0
    if n < MIN_PROMOTE_N:
        reasons.append(f"INSUFFICIENT_WALKFORWARD_N:{int(n)}<{MIN_PROMOTE_N}")
    brier_c = _metric(wf, "brier")
    brier_h = _metric(champ_wf, "brier") if isinstance(champ_wf, dict) else None
    if brier_c is None or brier_h is None or not (brier_c < brier_h):
        reasons.append("WALKFORWARD_BRIER_DOES_NOT_BEAT_CHAMPION")
    ll_c = _metric(wf, "logLoss") or _metric(wf, "log_loss")
    ll_h = _metric(champ_wf, "logLoss") or _metric(champ_wf, "log_loss") if isinstance(champ_wf, dict) else None
    if ll_c is None or ll_h is None or not (ll_c < ll_h):
        reasons.append("WALKFORWARD_LOGLOSS_DOES_NOT_BEAT_CHAMPION")
    subgroup = chal.get("subgroupSafety") if isinstance(chal.get("subgroupSafety"), dict) else None
    if not subgroup:
        reasons.append("SUBGROUP_SAFETY_PLACEHOLDER_MISSING")
    elif not subgroup.get("pass"):
        reasons.append("SUBGROUP_SAFETY_PLACEHOLDER_FAILED")
    reasons.append(HARD_REFUSE_LR)
    if str(chal.get("status") or "") != STATUS_SHADOW:
        reasons.append("CHALLENGER_NOT_SHADOW")
    eligible = (
        n >= MIN_PROMOTE_N
        and brier_c is not None
        and brier_h is not None
        and brier_c < brier_h
        and ll_c is not None
        and ll_h is not None
        and ll_c < ll_h
        and isinstance(subgroup, dict)
        and bool(subgroup.get("pass"))
    )
    return {
        "status": "BLOCKED" if (reasons and not eligible) or True else "SHADOW_ONLY_NOT_PRODUCTION",
        "blocked": True,
        "numericGatesPass": eligible,
        "challengerId": challenger_id,
        "reasons": reasons,
        "championId": CHAMPION_ID,
        "lrUnchanged": LEARNING_REVISION,
        "predictiveClaimUnchanged": PREDICTIVE_CLAIM,
        "autoPromote": False,
        "note": "Even if numeric gates pass, this PR will not promote a challenger onto LR/predictiveClaim.",
    }

def promote(path: Path, challenger_id: str) -> dict[str, Any]:
    """Hard-refuse any promotion that would change LEARNING_REVISION or PREDICTIVE_CLAIM."""
    _ = load_registry(path)
    _ = os.environ.get("DCM_ALLOW_LR_PROMOTE")  # documented; still hard-refused in this PR
    return {
        "ok": False,
        "status": "REFUSED",
        "challengerId": challenger_id,
        "reasons": [
            HARD_REFUSE_LR,
            "champion remains software+LR000000",
            "predictiveClaim remains NONE",
            "DCM_ALLOW_LR_PROMOTE does not override this PR",
        ],
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "challengerStatus": STATUS_SHADOW,
        "pkl": False,
    }

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Shadow-only model registry. Cannot advance LR000000.")
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--register-shadow", dest="register_id", default=None)
    p.add_argument("--feature-schema-hash", default="")
    p.add_argument("--training-cutoff", default="")
    p.add_argument("--propose", dest="propose_id", default=None)
    p.add_argument("--promote", dest="promote_id", default=None)
    args = p.parse_args(argv)
    if args.register_id:
        rec = register_challenger(
            args.registry,
            model_id=args.register_id,
            feature_schema_hash=args.feature_schema_hash,
            training_cutoff=args.training_cutoff,
        )
        print(json.dumps(rec, indent=2, sort_keys=True))
        return 0
    if args.propose_id:
        print(json.dumps(propose_promotion(args.registry, args.propose_id), indent=2, sort_keys=True))
        return 0
    if args.promote_id:
        print(json.dumps(promote(args.registry, args.promote_id), indent=2, sort_keys=True))
        return 0
    print(json.dumps(load_registry(args.registry), indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
