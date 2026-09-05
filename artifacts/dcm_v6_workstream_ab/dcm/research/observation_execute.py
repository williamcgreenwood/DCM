"""Execute source-aware host observations into the closed import→coverage→consumer loop.

Host tasks from ``dcm.research.batch`` carry actionId / sourceFamily / source
candidates. This module accepts matching timestamped observations, validates
typed field coverage, imports EvidenceClaims idempotently, recomputes
requirement coverage, and rebuilds ParameterSnapshots for changed descendants
only when contracts close. One AcquisitionAction observation fans out to every
dependent offer at that reusable scope.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dcm.chat.state import read_json, write_json
from dcm.model.parameters import build_parameter_snapshot
from dcm.research.claims import claim_record, conflict_ledger, dedupe
from dcm.research.coverage import coverage_report, evaluate_request
from dcm.research.evidence_graph import build_evidence_graph
from dcm.research.provider import BundleProvider, _validate_source_url
from dcm.research.authority import derive_quality
from dcm.research.research_store import ResearchStore
from dcm.research.scopes import canonical_scope, lookup_scopes
from dcm.runtime.dag import Dag
