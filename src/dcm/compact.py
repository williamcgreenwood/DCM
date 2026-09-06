"""Compact compute representation: int IDs, NumPy SoA columns, feature/parameter matrices.

Audit representation stays in dataclasses/dicts/JSON (BoardStore.row / public APIs).
This module is the intentional boundary for hot numerical fields only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

SCHEMA_VERSION = "dcm.compact.v1-20260906"

# Fixed dtypes for hot paths (compute representation).
DTYPE_ID = np.int32
DTYPE_F = np.float64
MISSING_ID = np.int32(-1)
NAN = np.nan


@dataclass(slots=True)
class IdMap:
    """Bidirectional string ↔ int32 registry. Stable insertion order."""

    _to_i: dict[str, int] = field(default_factory=dict)
    _to_s: list[str] = field(default_factory=list)

    def intern(self, key: str | None) -> int:
        s = str(key or "")
        if not s:
            return int(MISSING_ID)
        existing = self._to_i.get(s)
        if existing is not None:
            return existing
        idx = len(self._to_s)
        if idx > np.iinfo(DTYPE_ID).max:
            raise OverflowError("IdMap exceeded int32 capacity")
        self._to_i[s] = idx
        self._to_s.append(s)
        return idx

    def get(self, key: str | None) -> int:
        s = str(key or "")
        if not s:
            return int(MISSING_ID)
        return int(self._to_i.get(s, MISSING_ID))

    def resolve(self, idx: int) -> str:
        if idx < 0 or idx >= len(self._to_s):
            return ""
        return self._to_s[idx]

    def __len__(self) -> int:
        return len(self._to_s)

    @property
    def strings(self) -> tuple[str, ...]:
        return tuple(self._to_s)

    def to_audit(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "kind": "IdMap",
            "size": len(self._to_s),
            "ids": list(self._to_s),
        }


@dataclass(slots=True)
class CompactNumericBoard:
    """Structure-of-arrays hot columns aligned by row_id (int32 index)."""

    n: int
    offer_i: np.ndarray  # int32 row→offer map index (usually == row_id)
    subject_i: np.ndarray
    event_i: np.ndarray
    market_i: np.ndarray
    affiliation_i: np.ndarray
    line: np.ndarray
    mean: np.ndarray
    variance: np.ndarray
    reliability: np.ndarray
    fragility: np.ndarray
    ood: np.ndarray
    offer_ids: IdMap = field(default_factory=IdMap)
    subject_ids: IdMap = field(default_factory=IdMap)
    event_ids: IdMap = field(default_factory=IdMap)
    market_ids: IdMap = field(default_factory=IdMap)
    affiliation_ids: IdMap = field(default_factory=IdMap)

    @classmethod
    def empty(cls, n: int = 0) -> "CompactNumericBoard":
        z = max(0, int(n))
        return cls(
            n=z,
            offer_i=np.full(z, MISSING_ID, dtype=DTYPE_ID),
            subject_i=np.full(z, MISSING_ID, dtype=DTYPE_ID),
            event_i=np.full(z, MISSING_ID, dtype=DTYPE_ID),
            market_i=np.full(z, MISSING_ID, dtype=DTYPE_ID),
            affiliation_i=np.full(z, MISSING_ID, dtype=DTYPE_ID),
            line=np.full(z, NAN, dtype=DTYPE_F),
            mean=np.full(z, NAN, dtype=DTYPE_F),
            variance=np.full(z, NAN, dtype=DTYPE_F),
            reliability=np.full(z, NAN, dtype=DTYPE_F),
            fragility=np.full(z, NAN, dtype=DTYPE_F),
            ood=np.full(z, NAN, dtype=DTYPE_F),
        )

    @classmethod
    def from_board_rows(cls, rows: Sequence[Mapping[str, Any]]) -> "CompactNumericBoard":
        """Build SoA columns from auditable board row dicts (one pass)."""
        material = [r for r in rows if str(r.get("projectionId") or "")]
        out = cls.empty(len(material))
        for i, row in enumerate(material):
            oid = str(row.get("projectionId") or "")
            out.offer_i[i] = out.offer_ids.intern(oid)
            out.subject_i[i] = out.subject_ids.intern(
                str(row.get("playerId") or row.get("subjectId") or "")
            )
            out.event_i[i] = out.event_ids.intern(str(row.get("eventId") or ""))
            out.market_i[i] = out.market_ids.intern(str(row.get("market") or "").lower())
            out.affiliation_i[i] = out.affiliation_ids.intern(
                str(row.get("teamId") or row.get("team") or "")
            )
            out.line[i] = _as_float(row.get("line"))
            # Optional hot fields when already present on the row / prior grade.
            out.mean[i] = _as_float(row.get("mean") if "mean" in row else row.get("projectedMean"))
            out.variance[i] = _as_float(row.get("variance") if "variance" in row else row.get("projectedVariance"))
            out.reliability[i] = _as_float(row.get("reliability"))
            out.fragility[i] = _as_float(row.get("fragility"))
            out.ood[i] = _as_float(row.get("oodRisk") if "oodRisk" in row else row.get("ood"))
        return out

    def fill_from_grade_rows(self, grades: Sequence[Mapping[str, Any]], *, offer_key: str = "offerId") -> int:
        """Overlay mean/reliability/fragility/ood from graded rows. Returns fills."""
        by_offer = {str(g.get(offer_key) or g.get("projectionId") or ""): g for g in grades}
        filled = 0
        for i in range(self.n):
            oid = self.offer_ids.resolve(int(self.offer_i[i]))
            g = by_offer.get(oid)
            if not g:
                continue
            if "mean" in g or "projectedMean" in g:
                self.mean[i] = _as_float(g.get("mean", g.get("projectedMean")))
            if "variance" in g or "projectedVariance" in g:
                self.variance[i] = _as_float(g.get("variance", g.get("projectedVariance")))
            if "reliability" in g:
                self.reliability[i] = _as_float(g.get("reliability"))
            if "fragility" in g:
                self.fragility[i] = _as_float(g.get("fragility"))
            if "oodRisk" in g or "ood" in g:
                self.ood[i] = _as_float(g.get("oodRisk", g.get("ood")))
            filled += 1
        return filled

    def line_sum(self) -> float:
        """Microbench-friendly SoA reduction (ignores NaN)."""
        mask = np.isfinite(self.line)
        if not mask.any():
            return 0.0
        return float(np.sum(self.line[mask]))

    def to_audit_row(self, row_id: int) -> dict[str, Any]:
        """Boundary conversion: compact row → auditable dict."""
        if row_id < 0 or row_id >= self.n:
            raise IndexError("row_id out of range")
        return {
            "schema": SCHEMA_VERSION,
            "rowId": int(row_id),
            "offerId": self.offer_ids.resolve(int(self.offer_i[row_id])),
            "subjectId": self.subject_ids.resolve(int(self.subject_i[row_id])),
            "eventId": self.event_ids.resolve(int(self.event_i[row_id])),
            "marketId": self.market_ids.resolve(int(self.market_i[row_id])),
            "affiliationId": self.affiliation_ids.resolve(int(self.affiliation_i[row_id])),
            "line": _finite_or_none(self.line[row_id]),
            "mean": _finite_or_none(self.mean[row_id]),
            "variance": _finite_or_none(self.variance[row_id]),
            "reliability": _finite_or_none(self.reliability[row_id]),
            "fragility": _finite_or_none(self.fragility[row_id]),
            "oodRisk": _finite_or_none(self.ood[row_id]),
        }


@dataclass(slots=True)
class FeatureMatrix:
    """Dense feature matrix (entities × named numerical features)."""

    entity_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    values: np.ndarray  # float64 shape (n_entities, n_features)
    as_of: str = ""
    schema: str = SCHEMA_VERSION

    @property
    def shape(self) -> tuple[int, int]:
        return (len(self.entity_ids), len(self.feature_names))

    def to_audit_records(self) -> list[dict[str, Any]]:
        """Public/audit boundary: expand matrix back to typed feature dicts."""
        out: list[dict[str, Any]] = []
        for ei, entity in enumerate(self.entity_ids):
            for fi, name in enumerate(self.feature_names):
                val = self.values[ei, fi]
                out.append(
                    {
                        "entity": entity,
                        "featureName": name,
                        "value": None if not np.isfinite(val) else float(val),
                        "asOf": self.as_of,
                        "schema": self.schema,
                        "representation": "COMPACT_MATRIX",
                    }
                )
        return out


@dataclass(slots=True)
class ParameterMatrix:
    """Dense parameter fields aligned to offer (or subject) IDs."""

    offer_ids: tuple[str, ...]
    field_names: tuple[str, ...]
    values: np.ndarray  # float64 (n_offers, n_fields)
    schema: str = SCHEMA_VERSION

    @property
    def shape(self) -> tuple[int, int]:
        return (len(self.offer_ids), len(self.field_names))

    def to_audit_snapshots(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for oi, oid in enumerate(self.offer_ids):
            params: dict[str, Any] = {}
            for fi, name in enumerate(self.field_names):
                val = self.values[oi, fi]
                if np.isfinite(val):
                    params[name] = float(val)
            out.append({"offerId": oid, "parameters": params, "schema": self.schema, "representation": "COMPACT_MATRIX"})
        return out


# Common numerical parameter keys already produced by build_parameter_snapshot.
DEFAULT_PARAM_FIELDS: tuple[str, ...] = (
    "minutes_mean",
    "minutes_sd",
    "pass_att_mean",
    "pass_att_sd",
    "rush_att_mean",
    "rush_att_sd",
    "routes_mean",
    "routes_sd",
    "pa_mean",
    "pa_sd",
    "pass_yds_mean",
    "rush_yds_mean",
    "rec_yds_mean",
)


def feature_matrix_from_records(
    records: Iterable[Mapping[str, Any]],
    *,
    as_of: str = "",
) -> FeatureMatrix:
    """Pack already-numerical FeatureStore records into a dense matrix."""
    entities: list[str] = []
    entity_index: dict[str, int] = {}
    names: list[str] = []
    name_index: dict[str, int] = {}
    cells: list[tuple[int, int, float]] = []
    for rec in records:
        try:
            value = float(rec.get("value"))
        except (TypeError, ValueError):
            continue
        if not np.isfinite(value):
            continue
        entity = str(rec.get("entity") or rec.get("playerId") or "")
        fname = str(rec.get("featureName") or rec.get("name") or "")
        if not entity or not fname:
            continue
        if entity not in entity_index:
            entity_index[entity] = len(entities)
            entities.append(entity)
        if fname not in name_index:
            name_index[fname] = len(names)
            names.append(fname)
        cells.append((entity_index[entity], name_index[fname], value))
    values = np.full((len(entities), len(names)), NAN, dtype=DTYPE_F)
    for ei, fi, val in cells:
        values[ei, fi] = val
    return FeatureMatrix(
        entity_ids=tuple(entities),
        feature_names=tuple(names),
        values=values,
        as_of=as_of,
    )


def parameter_matrix_from_snapshots(
    snapshots: Iterable[Mapping[str, Any]],
    *,
    field_names: Sequence[str] | None = None,
) -> ParameterMatrix:
    """Pack numerical fields from parameter snapshots into a dense matrix."""
    fields = tuple(field_names) if field_names is not None else DEFAULT_PARAM_FIELDS
    offer_ids: list[str] = []
    rows_vals: list[np.ndarray] = []
    for snap in snapshots:
        oid = str(
            snap.get("offerId")
            or snap.get("projectionId")
            or (snap.get("row") or {}).get("projectionId")
            or ""
        )
        if not oid:
            continue
        params = snap.get("parameters") if isinstance(snap.get("parameters"), Mapping) else snap
        row = np.full(len(fields), NAN, dtype=DTYPE_F)
        for i, name in enumerate(fields):
            if name in params:
                row[i] = _as_float(params.get(name))
        offer_ids.append(oid)
        rows_vals.append(row)
    if not rows_vals:
        return ParameterMatrix(offer_ids=(), field_names=fields, values=np.zeros((0, len(fields)), dtype=DTYPE_F))
    return ParameterMatrix(
        offer_ids=tuple(offer_ids),
        field_names=fields,
        values=np.vstack(rows_vals),
    )


def round_trip_id_maps(board: CompactNumericBoard) -> dict[str, bool]:
    """Verify string↔int32 maps round-trip for every populated row."""
    ok_offer = True
    ok_subject = True
    ok_event = True
    ok_market = True
    ok_aff = True
    for i in range(board.n):
        oi = int(board.offer_i[i])
        if oi >= 0 and board.offer_ids.get(board.offer_ids.resolve(oi)) != oi:
            ok_offer = False
        si = int(board.subject_i[i])
        if si >= 0 and board.subject_ids.get(board.subject_ids.resolve(si)) != si:
            ok_subject = False
        ei = int(board.event_i[i])
        if ei >= 0 and board.event_ids.get(board.event_ids.resolve(ei)) != ei:
            ok_event = False
        mi = int(board.market_i[i])
        if mi >= 0 and board.market_ids.get(board.market_ids.resolve(mi)) != mi:
            ok_market = False
        ai = int(board.affiliation_i[i])
        if ai >= 0 and board.affiliation_ids.get(board.affiliation_ids.resolve(ai)) != ai:
            ok_aff = False
    return {
        "offer": ok_offer,
        "subject": ok_subject,
        "event": ok_event,
        "market": ok_market,
        "affiliation": ok_aff,
    }


def _as_float(value: Any) -> float:
    try:
        x = float(value)
        return x if np.isfinite(x) else NAN
    except (TypeError, ValueError):
        return NAN


def _finite_or_none(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return float(x) if np.isfinite(x) else None
