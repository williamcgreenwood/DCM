"""Silent retirement is a build failure."""
from __future__ import annotations

from pathlib import Path

import pytest

from dcm.algorithms.contracts import AlgorithmRecord
from dcm.algorithms.registry import load_algorithm_registry

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs" / "architecture" / "ADR-ALG-CONST-001-r0.md"


def test_no_retired_algorithms_without_adr():
    assert ADR.is_file()
    text = ADR.read_text(encoding="utf-8")
    assert "silent" in text.lower() or "Retirement" in text or "retirement" in text
    retired = [r for r in load_algorithm_registry() if r.retired_version]
    for rec in retired:
        assert rec.superseding_adr, rec.algorithm_id


def test_algorithm_record_rejects_retirement_without_adr():
    with pytest.raises(ValueError, match="ALGORITHM_RETIREMENT_REQUIRES_ADR"):
        AlgorithmRecord(
            algorithm_id="ALG-INDEX-001",
            canonical_name="Python hash tables",
            algorithm_family="INDEX",
            lifecycle="REQUIRED_CORE",
            applicability_contract="x",
            input_contract="x",
            output_contract="x",
            semantic_scope="x",
            implementation_module="dcm.algorithms.indexing",
            implementation_symbol="hash_table",
            runtime_producer="x",
            runtime_consumer="x",
            retired_version="v-next",
        )
