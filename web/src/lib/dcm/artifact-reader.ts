/** Parse Python DCM freeze artifacts. Never invent probabilities. */

import type {
  BoardRow,
  CoverageRow,
  DagNode,
  DcmView,
  Json,
  MountState,
  ReadinessGate,
  ResearchTask,
  SchemaState,
  SlimPick,
} from "./types";

function asObj(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

function asArr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function str(v: unknown, fallback = ""): string {
  return v == null ? fallback : String(v);
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function bool(v: unknown): boolean {
  return v === true;
}

function slim(raw: unknown): SlimPick {
  const o = asObj(raw);
  return {
    rank: num(o.rank),
    player: str(o.player || o.playerName),
    team: str(o.team),
    opponent: str(o.opponent),
    event: str(o.event || o.eventLabel),
    market: str(o.market),
    line: num(o.line),
    direction: str(o.direction),
    modifier: str(o.modifier),
    selectedP: num(o.selectedP),
    pHigher: num(o.pHigher),
    pLower: num(o.pLower),
    pPush: num(o.pPush),
    lowerBound: num(o.lowerBound),
    evidenceSafeP: num(o.evidenceSafeP),
    trueLineTolerance: num(o.trueLineTolerance),
    grade: o.grade == null ? null : str(o.grade),
    state: str(o.state),
    blocker: o.blocker == null ? null : str(o.blocker),
    productionSelectable: bool(o.productionSelectable),
    calibrationState: str(o.calibrationState),
    sportFamily: str(o.sportFamily),
    league: str(o.league),
    offeredHigher: bool(o.offeredHigher),
    offeredLower: bool(o.offeredLower),
    projectionId: str(o.projectionId),
  };
}

function boardRow(raw: unknown): BoardRow {
  const o = asObj(raw);
  return {
    projectionId: str(o.projectionId),
    playerName: str(o.playerName),
    team: str(o.team),
    opponent: str(o.opponent),
    eventLabel: str(o.eventLabel),
    league: str(o.league),
    market: str(o.market),
    marketLabel: str(o.marketLabel),
    line: num(o.line),
    side: str(o.side),
    offeredHigher: bool(o.offeredHigher),
    offeredLower: bool(o.offeredLower),
    modifier: str(o.modifier),
    sportFamily: str(o.sportFamily),
  };
}

function jsonSafe(v: unknown): Json {
  if (v == null) return null;
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return v;
  if (Array.isArray(v)) return v.map(jsonSafe);
  if (typeof v === "object") {
    const out: { [key: string]: Json } = {};
    for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
      if (k === "dag") continue;
      out[k] = jsonSafe(val);
    }
    return out;
  }
  return String(v);
}

function parsePopulation(raw: unknown): SlimPick[] {
  if (typeof raw !== "string" || !raw.trim()) return [];
  const rows: SlimPick[] = [];
  for (const line of raw.split("\n")) {
    if (!line.trim()) continue;
    try {
      rows.push(slim(JSON.parse(line)));
    } catch {
      /* skip corrupt line; never invent a row */
    }
    if (rows.length >= 500) break;
  }
  return rows;
}

function researchTasks(raw: unknown): ResearchTask[] {
  const doc = asObj(raw);
  return asArr(doc.tasks).map((t) => {
    const o = asObj(t);
    return {
      requestId: str(o.requestId),
      scope: str(o.scope),
      scopeId: str(o.scopeId),
      need: str(o.need),
      complete: bool(o.complete),
      priority: num(o.priority),
    };
  });
}

function coverageRows(raw: unknown): CoverageRow[] {
  const doc = asObj(raw);
  return asArr(doc.requests).map((t) => {
    const o = asObj(t);
    return {
      requestId: str(o.requestId),
      scope: str(o.scope),
      scopeId: str(o.scopeId),
      complete: bool(o.complete),
      missing: asArr(o.missing).map((m) => str(m)),
      claimCount: num(o.claimCount) ?? 0,
    };
  });
}

function dagNodes(integrityRaw: Record<string, unknown>, freeze: Record<string, unknown>): DagNode[] {
  const dagSnap = asObj(integrityRaw.dag ?? freeze.dag);
  return asArr(dagSnap.nodes).map((n) => {
    const o = asObj(n);
    return {
      nodeType: str(o.nodeType, "NODE"),
      state: str(o.state, "?"),
      artifactHash: str(o.artifactHash),
    };
  });
}

function schemaState(raw: unknown): SchemaState | null {
  if (raw == null) return null;
  const o = asObj(raw);
  return {
    expectedSha256: str(o.expectedSha256),
    observedSha256: str(o.observedSha256),
    state: str(o.state),
    productionEligible: bool(o.productionEligible),
    schemaId: str(o.schemaId),
  };
}

function mountState(raw: unknown): MountState | null {
  if (raw == null) return null;
  const o = asObj(raw);
  return {
    state: str(o.state),
    expectedSource: str(o.expected_source_sha256),
    expectedLedger: str(o.expected_ledger_sha256),
    harDecoder: str(o.har_decoder),
    note: str(o.note),
  };
}

const REQUIRED_ARTIFACTS = ["run_integrity", "board", "frozen_forecast"] as const;

export function viewFromPythonArtifacts(files: Record<string, unknown>, dest?: string): DcmView {
  const integrityRaw = asObj(files.run_integrity ?? files.frozen_forecast);
  const boardDoc = asObj(files.board);
  const readinessRaw = asObj(files.production_readiness);
  const plan = asObj(files.host_research_plan);
  const freeze = asObj(files.frozen_forecast);

  const missingArtifacts = REQUIRED_ARTIFACTS.filter((name) => files[name] == null);

  const blockers = asArr(files.blockers).map((b) => {
    const o = asObj(b);
    return { code: str(o.code), count: num(o.count) ?? 0, detail: o.detail == null ? undefined : str(o.detail) };
  });

  const gate = (raw: unknown): ReadinessGate => {
    const o = asObj(raw);
    return {
      class: str(o.class),
      id: str(o.id),
      passed: bool(o.passed),
      state: str(o.state),
      count: num(o.count) ?? undefined,
    };
  };

  const tasks = researchTasks(files.host_research_plan);
  const freezeHash =
    (typeof files.frozen_forecast_sha256 === "string" && files.frozen_forecast_sha256.trim()) ||
    str(integrityRaw.frozenForecastHash || freeze.frozenForecastHash);

  return {
    engine: "PYTHON",
    pythonAvailable: true,
    dest,
    missingArtifacts,
    integrity: jsonSafe(integrityRaw) as { [key: string]: Json },
    board: asArr(boardDoc.rows).map(boardRow),
    ranked: asArr(files.top25_ranked).map(slim),
    qualified: asArr(files.top25_qualified).map(slim),
    card: asArr(files.strict_card).map(slim),
    population: parsePopulation(files.full_population),
    blockers,
    readiness: {
      blocking: asArr(readinessRaw.blocking).map(gate),
      gates: asArr(readinessRaw.gates).map(gate),
    },
    research: {
      requested: num(integrityRaw.researchRequested) ?? num(plan.taskCount) ?? 0,
      reused: num(integrityRaw.researchReused) ?? 0,
      complete: bool(integrityRaw.researchComplete),
      claims: 0,
      mode: str(integrityRaw.evidenceMode ?? integrityRaw.researchMode ?? plan.mode),
      incomplete: num(plan.incompleteTaskCount) ?? 0,
      hierarchy: asArr(plan.researchHierarchy).map((h) => str(h)),
      tasks,
    },
    coverage: coverageRows(files.coverage),
    dag: dagNodes(integrityRaw, freeze),
    freezeHash,
    schema: schemaState(files.schema_state),
    mount: mountState(files.mount_state),
    blocker: missingArtifacts.length
      ? `Python freeze missing artifacts: ${missingArtifacts.join(", ")}. Displaying present files only.`
      : undefined,
  };
}

export function pythonUnavailable(message: string): DcmView {
  return {
    engine: "PYTHON",
    pythonAvailable: false,
    blocker: message,
    missingArtifacts: [...REQUIRED_ARTIFACTS],
    integrity: {},
    board: [],
    ranked: [],
    qualified: [],
    card: [],
    population: [],
    blockers: [{ code: "PYTHON_ENGINE_NOT_MOUNTED", count: 1, detail: message }],
    readiness: { blocking: [], gates: [] },
    research: {
      requested: 0,
      reused: 0,
      complete: false,
      claims: 0,
      mode: "",
      incomplete: 0,
      hierarchy: [],
      tasks: [],
    },
    coverage: [],
    dag: [],
    freezeHash: "",
    schema: null,
    mount: null,
  };
}
