# Engineering pass — StatePack queryable store + adaptive freshness

- Agent: Grok
- Date: 2026-08-31
- Starting integration branch: `integration/v6-ml-architecture-20260830`
- Exact starting SHA: `88f7c3aec45eba9499cca5c4b679afe491c9d73d`
- Child branch: `grok/p12-statepack-queryable-store-20260831`
- Do not merge this child to `main`. PR targets integration only.

## Objective

Implement DCM6-ROS-EG-001 §7 portable StatePack (SQLite WAL + deterministic
export + integrity manifests) over the existing content-addressed ResearchStore,
and §11 adaptive freshness so completed historical facts do not expire by clock.

## Files added

- `artifacts/dcm_v6_workstream_ab/dcm/research/freshness.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/statepack.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_freshness.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_statepack.py`
- this pass record

## Contracts

- `H_eff = H_base * M_event * M_volatility * M_status`
- `Freshness = 2 ^ (-age_hours / H_eff)`
- Historical completed-game facts do not use H_eff
- StatePack export sorted by content hash; semantic snapshot hash excludes `createdAt`
- Outcomes indexed with `decides_research_reuse=0`
- Git must not commit the changing SQLite file as source of truth

## Validation

CI on this child is the integration proof. New tests cover freshness equations,
entity/source/as-of queries, export round-trip, and tamper fail-closed.

## Workstream status

P12 7 → 8 (queryable pack exists; not a remote object store; not 10/10).
LR000000 / predictive NONE / production root closed / host performance uncertified.

## Next

1. Fresh-wheel ChatGPT HAR acceptance through `dcm-host`
2. Wire `evaluate_freshness` into `classify_requests` from observed_at + event start
3. Retire remaining PLAYER/TEAM adapter aliases
4. Close remaining PARTIAL SportPlugin bindings
5. Chronological unseen settlements before any LR/predictive promotion
