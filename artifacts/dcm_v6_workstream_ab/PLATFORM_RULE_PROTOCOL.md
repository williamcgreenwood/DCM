# PrizePicks platform protocol

Lookup key (exact, no nearest match):

`Platform + ProductType + EntryType + League + BoardID + Market + Modifier + Side + RuleVersion + Situation`

ProductType: PLAYER_PICKS | TEAM_PICKS | CULTURE_PICKS

Settlement order: Administrative → Comparison → Economic.

Active reboot snapshot V1 (do not copy elsewhere): NFL, NBA, WNBA, MLB batters, CFB CFP named list.

No verified reboot → NO_VERIFIED_REBOOT_RULE / UNKNOWN_REBOOT_RULE.

Displayed payout hash is the contract. Final return = max(LB, MG). LB UNMODELED without GroupScoreContext.

Scoring providers belong on MarketDefinition (SportRadar / Genius / Stats Perform / Grid) as provenance, not as primitives.
