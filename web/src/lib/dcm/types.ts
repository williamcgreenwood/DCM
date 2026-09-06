/** Viewer types for Python-produced artifacts. No probabilities are computed here. */

export type Json =
  | string
  | number
  | boolean
  | null
  | Json[]
  | { [key: string]: Json };

export type SlimPick = {
  rank: number | null;
  player: string;
  team: string;
  opponent: string;
  event: string;
  market: string;
  line: number | null;
  direction: string;
  modifier: string;
  selectedP: number | null;
  pHigher: number | null;
  pLower: number | null;
  pPush: number | null;
  lowerBound: number | null;
  evidenceSafeP: number | null;
  trueLineTolerance: number | null;
  grade: string | null;
  state: string;
  blocker: string | null;
  productionSelectable: boolean;
  calibrationState: string;
  sportFamily: string;
  league: string;
  offeredHigher: boolean;
  offeredLower: boolean;
  projectionId: string;
};

export type BoardRow = {
  projectionId: string;
  playerName: string;
  team: string;
  opponent: string;
  eventLabel: string;
  league: string;
  market: string;
  marketLabel: string;
  line: number | null;
  side: string;
  offeredHigher: boolean;
  offeredLower: boolean;
  modifier: string;
  sportFamily: string;
};

export type ReadinessGate = {
  class: string;
  id: string;
  passed: boolean;
  state: string;
  count?: number;
};

export type ResearchTask = {
  requestId: string;
  scope: string;
  scopeId: string;
  need: string;
  complete: boolean;
  priority: number | null;
};

export type CoverageRow = {
  requestId: string;
  scope: string;
  scopeId: string;
  complete: boolean;
  missing: string[];
  claimCount: number;
};

export type DagNode = {
  nodeType: string;
  state: string;
  artifactHash: string;
};

export type SchemaState = {
  expectedSha256: string;
  observedSha256: string;
  state: string;
  productionEligible: boolean;
  schemaId: string;
};

export type MountState = {
  state: string;
  expectedSource: string;
  expectedLedger: string;
  harDecoder: string;
  note: string;
};

export type DcmView = {
  engine: "PYTHON";
  pythonAvailable: boolean;
  blocker?: string;
  dest?: string;
  missingArtifacts: string[];
  integrity: { [key: string]: Json };
  board: BoardRow[];
  ranked: SlimPick[];
  qualified: SlimPick[];
  card: SlimPick[];
  population: SlimPick[];
  blockers: Array<{ code: string; count: number; detail?: string }>;
  readiness: { blocking: ReadinessGate[]; gates: ReadinessGate[] };
  research: {
    requested: number;
    reused: number;
    complete: boolean;
    claims: number;
    mode: string;
    incomplete: number;
    hierarchy: string[];
    tasks: ResearchTask[];
  };
  coverage: CoverageRow[];
  dag: DagNode[];
  freezeHash: string;
  schema: SchemaState | null;
  mount: MountState | null;
};
