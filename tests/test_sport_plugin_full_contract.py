from __future__ import annotations

import pytest

from dcm.sports.common.contract import (
    IMPLEMENTED,
    PARTIAL,
    REQUIRED_COMPONENTS,
    contract_registry_document,
    require_contract,
)


def test_registered_sport_plugin_bindings_resolve_but_partial_contracts_do_not_promote():
    document = contract_registry_document(validate_imports=True)
    assert document["requiredComponents"] == list(REQUIRED_COMPONENTS)
    assert document["genericFallbackAllowed"] is False
    assert document["productionCompleteSports"] == []

    reports = {row["sportId"]: row for row in document["sports"]}
    assert set(reports) == {"basketball", "gridiron"}
    for sport in ("basketball", "gridiron"):
        report = reports[sport]
        assert report["requiredComponentCount"] == len(REQUIRED_COMPONENTS)
        assert report["universalProductionComplete"] is False
        assert report["productionPromotionAllowedByContract"] is False
        # Every registered non-missing binding must import. "PARTIAL" means
        # architecture/semantics incomplete, not a fake/unresolvable module.
        for component in report["components"]:
            if component["state"] in {IMPLEMENTED, PARTIAL}:
                assert component["importResolved"] is True, component
                assert component["importError"] is None

    assert any("FeatureSchema:PARTIAL" == b for b in reports["basketball"]["blockers"])
    assert any("FeatureSchema:PARTIAL" == b for b in reports["gridiron"]["blockers"])
    assert not any("ParticipationModel:PARTIAL" == b for b in reports["basketball"]["blockers"])
    assert not any("ParticipationModel:PARTIAL" == b for b in reports["gridiron"]["blockers"])


def test_sport_plugin_contract_requires_every_named_component():
    basketball = require_contract("basketball")
    report = basketball.report(validate_imports=True)
    names = {row["component"] for row in report["components"]}
    assert names == set(REQUIRED_COMPONENTS)
    assert report["implementedCount"] + report["partialCount"] + report["missingCount"] == len(REQUIRED_COMPONENTS)


def test_unknown_sport_plugin_contract_fails_closed():
    with pytest.raises(LookupError, match="SPORT_PLUGIN_CONTRACT_UNSUPPORTED"):
        require_contract("motorsport")
