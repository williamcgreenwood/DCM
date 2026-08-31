"""Versioned source catalog / adapter capability registry."""
from __future__ import annotations

from dcm.research.source_catalog import catalog_summary, load_source_catalog, sources_for


def test_catalog_loads_and_is_hashed():
    cat = load_source_catalog()
    assert cat["schema"] == "pillars_dcm.source_catalog.v1"
    assert cat["sourceCount"] >= 5
    assert cat["contentHash"]
    summary = catalog_summary(cat)
    assert summary["secretsInRepo"] is False
    assert summary["authenticatedRequired"] is False
    assert "prizepicks_offer" in summary["sourceIds"]
    assert "generic_web_search" in summary["sourceIds"]


def test_catalog_priority_official_before_search():
    ranked = sources_for(sport="basketball", competition="WNBA", entity_kind="SUBJECT")
    assert ranked
    ids = [s["sourceId"] for s in ranked]
    if "official_wnba" in ids and "generic_web_search" in ids:
        assert ids.index("official_wnba") < ids.index("generic_web_search")
    assert all(s.get("liveFetch") != "always" for s in ranked)


def test_catalog_counterparty_basketball():
    ranked = sources_for(sport="basketball", entity_kind="COUNTERPARTY")
    assert any(s["sourceId"] == "basketball_reference" for s in ranked)
