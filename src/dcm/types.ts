export const DCM_VERSION = "6.0.0+WSAB.UNIVERSAL.LR000000";
export const LEARNING_REVISION = "LR000000";
export const PREDICTIVE_CLAIM = "NONE";
export const SCHEMA_ID = "PHASE_BC_SCHEMA_V1_2026-08-25";
export const EXPECTED_V5_SOURCE =
  "bd1fb433d5f82d3812e453c30edcbb67db11b20f60e43cf50424c45a7c2ff474";
export const EXPECTED_V5_LEDGER =
  "a9956ef1d231eb37ea5898b5145d660b986b68ee4dc6cfbd5c43fed59064c29a";
export const EXPECTED_SCHEMA =
  "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22";
export const RULE_SNAPSHOT = "PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1";

export type Side = "MORE" | "LESS";
export type Modifier = "STANDARD" | "DEMON" | "GOBLIN" | "OTHER";
export type Grade = "PLAYABLE" | "LEAN" | "PASS" | "TRAP";
export type ProductType = "PLAYER_PICKS" | "TEAM_PICKS" | "CULTURE_PICKS";
export type ProductionState =
  | "PRODUCTION_SUPPORTED"
  | "SHADOW_SUPPORTED"
  | "RESEARCH_ONLY"
  | "UNSUPPORTED_FAIL_CLOSED";

export type RowState =
  | "MODELED"
  | "UNSUPPORTED_FAIL_CLOSED"
  | "MISSING_DEFINITION"
  | "MISSING_EVIDENCE"
  | "OFFERED_SIDE_UNKNOWN"
  | "MODIFIER_UNKNOWN"
  | "GOBLIN_EXCLUDED"
  | "HALF_LINE_POLICY_EXCLUDED"
  | "STALE_EVIDENCE"
  | "DUPLICATE"
  | "OTHER_EXPLICIT_BLOCKER";

export type AdminState =
  | "ACTIVE"
  | "DNP"
  | "REBOOT"
  | "CANCELLED"
  | "INVALID_MARKET"
  | "UNRESOLVED";

export interface BoardRow {
  projectionId: string;
  sportFamily: string;
  league: string;
  eventId: string;
  eventLabel: string;
  playerId: string;
  playerName: string;
  teamId: string;
  team: string;
  opponent: string;
  market: string;
  marketLabel: string;
  line: number;
  side: Side | "UNKNOWN";
  offeredHigher: boolean;
  offeredLower: boolean;
  modifier: Modifier;
  boardId: string;
  productType: ProductType;
  role: string;
}

export interface EvidencePacket {
  scope: "EVENT" | "TEAM" | "PLAYER";
  entityId: string;
  seasonN: number;
  recentN: number;
  roleEpochN: number;
  sameOppN: number;
  opportunityMean: number;
  efficiencyMean: number;
  injury: string;
  role: string;
  notes: string;
  quality: number;
}

export interface ModeledProp {
  row: BoardRow;
  state: RowState;
  blocker?: string;
  grade: Grade | null;
  pHigher: number | null;
  pLower: number | null;
  pPush: number | null;
  selectedSide: Side | null;
  selectedP: number | null;
  lowerBound: number | null;
  mean: number | null;
  median: number | null;
  opportunityMean: number | null;
  reliability: number | null;
  dataQuality: number | null;
  volatility: number | null;
  fragility: number | null;
  ood: number | null;
  falseSign: number | null;
  selectionScore: number | null;
  rank: number | null;
  primaryReason: string;
  primaryRisk: string;
  evidenceIds: string[];
}

export interface RunIntegrity {
  runId: string;
  dcmVersion: string;
  learningRevision: string;
  predictiveClaim: string;
  schemaId: string;
  schemaState: string;
  v5SourceState: string;
  v5LedgerState: string;
  harHash: string;
  sourceAdapter: string;
  forecastCutoff: string;
  rawRows: number;
  goblinExcluded: number;
  halfLineExcluded: number;
  modeledRows: number;
  blockedRows: number;
  unresolvedRows: number;
  uniqueEvents: number;
  uniqueTeams: number;
  uniquePlayers: number;
  researchComplete: boolean;
  modelComplete: boolean;
  rankComplete: boolean;
  freezeComplete: boolean;
  boardComplete: boolean;
  top25QualifiedCount: number;
  playableCount: number;
  cardSize: number;
  freezeHash: string;
  lr: string;
}

export interface DcmRun {
  integrity: RunIntegrity;
  board: BoardRow[];
  population: ModeledProp[];
  excluded: ModeledProp[];
  top25Ranked: ModeledProp[];
  top25Qualified: ModeledProp[];
  top100: ModeledProp[];
  card: ModeledProp[];
  blockers: { code: string; count: number; detail: string }[];
  gates: {
    BOARD_COMPLETE: boolean;
    RESEARCH_COMPLETE: boolean;
    MODEL_COMPLETE: boolean;
    RANK_COMPLETE: boolean;
    FREEZE_COMPLETE: boolean;
  };
  accounting: Record<string, number>;
}
