"""Regression guards for the rights-aware five-repository donor audit."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs/donor/EXTERNAL_DONOR_FIVE_REPO_MATRIX.json"


def _matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def test_five_donor_matrix_is_complete_and_content_hashed():
    matrix = _matrix()
    donors = {item["repository"].rstrip("/").split("/")[-1]: item for item in matrix["donors"]}
    assert set(donors) == {
        "sports-betting", "scikit-ai", "imbalanced-learn-extra",
        "scikit-complexity", "copier-modern-python",
    }
    for donor in donors.values():
        assert len(donor["observed_main_commit"]) == 40
        assert donor["components"]
        for component in donor["components"]:
            assert component["disposition"] in matrix["disposition_enum"]
            assert component["source_sha256"]
            assert all(len(digest) == 64 for digest in component["source_sha256"].values())
            assert component["imported_code_and_attribution"].startswith("NONE")
    assert matrix["runtime_change_summary"]["code_imported"] is False
    assert matrix["runtime_change_summary"]["new_runtime_dependencies"] == []


def test_unresolved_oversampling_license_is_a_hard_exclusion():
    donor = next(d for d in _matrix()["donors"] if d["repository"].endswith("/imbalanced-learn-extra"))
    assert donor["rights_state"].startswith("BLOCKED_RIGHTS")
    assert "Conflicting evidence" in donor["license_evidence"]
    assert {c["disposition"] for c in donor["components"]} == {"BLOCKED_RIGHTS"}
    assert "Apache-2.0" in donor["license_evidence"]
    assert "MIT" in donor["license_evidence"]
    assert "BSD-3-Clause" in donor["license_evidence"]


def test_remote_llm_and_physics_donors_remain_outside_runtime():
    donors = {d["repository"].split("/")[-1]: d for d in _matrix()["donors"]}
    assert {c["disposition"] for c in donors["scikit-ai"]["components"]} == {
        "REJECT_DUPLICATE", "REJECT_POOR_FIT"
    }
    assert {c["disposition"] for c in donors["scikit-complexity"]["components"]} == {
        "REJECT_POOR_FIT"
    }
    assert "SageMath" in donors["scikit-complexity"]["python_and_dependency_health"]
    assert "LAMMPS" in donors["scikit-complexity"]["python_and_dependency_health"]


def test_canonical_package_does_not_import_donor_engines_or_template():
    forbidden_roots = {"sportsbet", "skai", "imblearn_extra", "skcomplex", "copier"}
    for path in (ROOT / "src/dcm").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".", 1)[0]]
            else:
                continue
            assert not forbidden_roots.intersection(names), f"donor runtime import in {path}"


def test_template_donor_did_not_replace_canonical_packaging_or_runtime():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "DCM_BOOTSTRAP_MANIFEST.json").read_text(encoding="utf-8"))
    assert 'name = "pillars-dcm"' in pyproject
    assert manifest["engine"]["canonical"] == "Python"
    assert manifest["requiredArtifacts"]["algorithmRegistry"] == "configs/algorithm_registry.json"
    assert (ROOT / ".github/workflows/dcm-v6-ci.yml").is_file()
    assert (ROOT / "scripts/build_code_inventory.py").is_file()


def test_event_grouped_walkforward_is_registered_to_its_runtime_consumer():
    registry = json.loads((ROOT / "configs/algorithm_registry.json").read_text(encoding="utf-8"))
    row = next(item for item in registry["algorithms"] if item["algorithm_id"] == "ALG-ML-TIME-009")
    assert row["implementation_module"] == "dcm.learning.walkforward"
    assert row["implementation_symbol"] == "chronological_folds"
    assert row["runtime_consumer"] == "dcm.learning.walkforward.run_walkforward"
    assert row["lifecycle"] == "REQUIRED_CONDITIONAL"
