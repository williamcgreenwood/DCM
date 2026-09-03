"""Every registry row has producer, consumer, tests, benchmarks, and traces."""
from __future__ import annotations

from dcm.algorithms.registry import load_algorithm_registry, resolve_implementation


REQUIRED = {"REQUIRED_CORE", "REQUIRED_CONDITIONAL", "PERMANENT_CHALLENGER"}


def test_algorithm_trace_complete():
    records = load_algorithm_registry()
    assert records
    missing = []
    for rec in records:
        if rec.lifecycle not in REQUIRED:
            missing.append(f"LIFECYCLE:{rec.algorithm_id}")
        if not rec.runtime_producer:
            missing.append(f"PRODUCER:{rec.algorithm_id}")
        if not rec.runtime_consumer:
            missing.append(f"CONSUMER:{rec.algorithm_id}")
        if not rec.test_ids:
            missing.append(f"TESTS:{rec.algorithm_id}")
        if not rec.benchmark_ids:
            missing.append(f"BENCHMARKS:{rec.algorithm_id}")
        if not rec.requirement_trace_ids:
            missing.append(f"TRACE:{rec.algorithm_id}")
        if not rec.implementation_module or not rec.implementation_symbol:
            missing.append(f"IMPL:{rec.algorithm_id}")
        else:
            resolve_implementation(rec)
        if rec.lifecycle in {"REQUIRED_CORE", "REQUIRED_CONDITIONAL"} and rec.retired_version:
            missing.append(f"ACTIVE_RETIRED:{rec.algorithm_id}")
    assert missing == []
