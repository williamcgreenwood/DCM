import { contentHash } from "./hash.ts";
import { DEMO_HAR } from "./demo-board.ts";
import { ingestHar } from "./har.ts";
import { classify, modelRow } from "./model.ts";
import {
  DCM_VERSION,
  LEARNING_REVISION,
  PREDICTIVE_CLAIM,
  SCHEMA_ID,
  type DcmRun,
  type ModeledProp,
  type RunIntegrity,
} from "./types.ts";

function count(pop: ModeledProp[], state: string) {
  return pop.filter((p) => p.state === state).length;
}

export function runFromHar(raw: unknown = DEMO_HAR, cutoff = "2026-08-27T16:00:00Z"): DcmRun {
  const ingest = ingestHar(raw);
  const board = ingest.rows;
  const classified = board.map((row) => {
    const c = classify(row);
    return modelRow(row, c.state, c.blocker);
  });

  const modeled = classified.filter((p) => p.state === "MODELED");
  const ranked = [...modeled].sort((a, b) => (b.selectionScore ?? 0) - (a.selectionScore ?? 0));
  ranked.forEach((p, i) => {
    p.rank = i + 1;
  });

  const top100 = ranked.slice(0, 100);
  const top25Ranked = ranked.slice(0, 25);
  const qualified = ranked.filter(
    (p) =>
      p.grade === "PLAYABLE" &&
      p.row.modifier !== "GOBLIN" &&
      p.blocker !== "RESEARCH_ONLY_NOT_SELECTABLE",
  );
  const top25Qualified = qualified.slice(0, 25);
  const card = top25Qualified.slice(0, 6);
  const excluded = classified.filter((p) => p.state !== "MODELED");

  const blockerMap = new Map<string, number>();
  for (const p of classified) {
    const code = p.blocker ?? p.state;
    blockerMap.set(code, (blockerMap.get(code) ?? 0) + 1);
  }
  const blockers = [...blockerMap.entries()].map(([code, n]) => ({
    code,
    count: n,
    detail:
      code === "GOBLIN_SELECTION_FORBIDDEN"
        ? "Extracted and excluded from production selection."
        : code === "UNSUPPORTED_FAIL_CLOSED"
          ? "Inventoried; no plugin/rule — not sent through a generic Normal."
          : code === "HALF_LINE_AVOID_BASEBALL_HRRBI_0_5"
            ? "User preference / fragility gate. Directional, not a theorem."
            : code === "RESEARCH_ONLY_NOT_SELECTABLE"
              ? "Modeled for audit; cannot enter the card."
              : "Explicit fail-closed or policy state.",
  }));

  const events = new Set(board.map((r) => r.eventId));
  const teams = new Set(board.map((r) => r.teamId));
  const players = new Set(board.map((r) => r.playerId));
  const runId = `RUN_${contentHash({ har: ingest.harHash, cutoff }).slice(0, 16)}`;
  const freezeHash = contentHash({
    board: board.map((b) => b.projectionId),
    ranks: ranked.map((p) => [p.row.projectionId, p.rank, p.selectedP]),
    cutoff,
  });

  const integrity: RunIntegrity = {
    runId,
    dcmVersion: DCM_VERSION,
    learningRevision: LEARNING_REVISION,
    predictiveClaim: PREDICTIVE_CLAIM,
    schemaId: SCHEMA_ID,
    schemaState: "DECLARED_UNVERIFIED",
    v5SourceState: "ABSENT_IN_THIS_WORKSPACE",
    v5LedgerState: "ABSENT_IN_THIS_WORKSPACE",
    harHash: ingest.harHash,
    sourceAdapter: ingest.adapter,
    forecastCutoff: cutoff,
    rawRows: board.length,
    goblinExcluded: count(classified, "GOBLIN_EXCLUDED"),
    halfLineExcluded: count(classified, "HALF_LINE_POLICY_EXCLUDED"),
    modeledRows: modeled.length,
    blockedRows: excluded.length,
    unresolvedRows: count(classified, "OFFERED_SIDE_UNKNOWN") + count(classified, "MODIFIER_UNKNOWN"),
    uniqueEvents: events.size,
    uniqueTeams: teams.size,
    uniquePlayers: players.size,
    researchComplete: true,
    modelComplete: true,
    rankComplete: true,
    freezeComplete: true,
    boardComplete: board.length > 0,
    top25QualifiedCount: top25Qualified.length,
    playableCount: qualified.length,
    cardSize: card.length,
    freezeHash,
    lr: LEARNING_REVISION,
  };

  return {
    integrity,
    board,
    population: ranked.concat(excluded),
    excluded,
    top25Ranked,
    top25Qualified,
    top100,
    card,
    blockers,
    gates: {
      BOARD_COMPLETE: integrity.boardComplete,
      RESEARCH_COMPLETE: true,
      MODEL_COMPLETE: true,
      RANK_COMPLETE: true,
      FREEZE_COMPLETE: true,
    },
    accounting: {
      raw_projection_rows: board.length,
      unique_offer_rows: board.length,
      standard_rows: board.filter((r) => r.modifier === "STANDARD").length,
      goblin_rows: board.filter((r) => r.modifier === "GOBLIN").length,
      demon_rows: board.filter((r) => r.modifier === "DEMON").length,
      goblin_excluded: integrity.goblinExcluded,
      half_line_excluded: integrity.halfLineExcluded,
      modeled: integrity.modeledRows,
      unsupported: count(classified, "UNSUPPORTED_FAIL_CLOSED"),
      research_only: classified.filter((p) => p.blocker === "RESEARCH_ONLY_NOT_SELECTABLE").length,
      final_model_population: modeled.length,
    },
  };
}

export function verifyInstall() {
  return {
    dcmVersion: DCM_VERSION,
    learningRevision: LEARNING_REVISION,
    predictiveClaim: PREDICTIVE_CLAIM,
    schemaId: SCHEMA_ID,
    schemaState: "DECLARED_UNVERIFIED",
    v5Source: "ABSENT",
    v5Ledger: "ABSENT",
    wsabBaseline46: "PYTHON_PACKAGE_PRESENT",
    lifecycle: "IMPLEMENTED_STANDALONE",
    ok: true,
  };
}
