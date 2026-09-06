"""Versioned source catalog / adapter capability registry."""
from __future__ import annotations

from dcm.research.source_catalog import catalog_summary, load_source_catalog, source_health_seeds, sources_for
from dcm.research.source_health import default_cfb_source_health


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


def test_cfb_health_router_is_derived_from_cfb_catalog_capabilities():
    seeds = source_health_seeds(sport="gridiron", competition="CFB")
    ids = {row["sourceId"] for row in seeds}
    assert {"cfb_official_athletics", "college_football_reference", "open_meteo_weather", "espn_status"} <= ids
    health = default_cfb_source_health()
    catalog_ids = {row["catalogSourceId"] for row in health.snapshot()["sources"]}
    assert {"cfb_official_athletics", "college_football_reference", "open_meteo_weather", "espn_status"} <= catalog_ids
    event_route = health.route(claim_type="EVENT", sport="CFB")
    environment_route = health.route(claim_type="ENVIRONMENT", sport="CFB")
    assert event_route[0] == "CFB_OFFICIAL_GAMEBOOK"
    assert environment_route[0] == "CFB_WEATHER"
