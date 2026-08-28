# Sport plugin protocol

Every family under `dcm/sports/<family>/` exposes:

- SportPluginManifest
- LeagueRuleRegistry
- PrimitiveStatRegistry
- AppearanceModel / OpportunityModel / EfficiencyModel
- EventWorldBuilder / PrimitiveLedgerBuilder
- ConservationRuleSet
- MarketDeriver
- EvidenceRequirementRegistry
- PlatformParticipationBinding
- CapabilityRows

Unknown HAR sport:

```
SPORT_DISCOVERED → MARKETS_INVENTORIED → PLUGIN_MISSING → UNSUPPORTED_FAIL_CLOSED
```

Never:

```
UNKNOWN SPORT → GENERIC NORMAL → PLAYABLE
```

A family may share physics (NFL/CFB/CFL) and **must not** share platform reboot/DNP rows.

Appearance is physical. PrizePicks administration consumes facts; it does not define snaps, PA, fight-seconds, or minutes.

No new common-schema fields without a mutation dossier.
