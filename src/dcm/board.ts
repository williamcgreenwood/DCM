import type { BoardRow } from "./types.ts";
import { contentHash } from "./hash.ts";
import type { HarIngestResult } from "./har.ts";
import { EXPECTED_V5_LEDGER, EXPECTED_V5_SOURCE, LEARNING_REVISION, PREDICTIVE_CLAIM } from "./types.ts";

export interface BoardAccounting {
  raw_projection_rows: number;
  unique_offer_rows: number;
  standard_rows: number;
  goblin_rows: number;
  demon_rows: number;
  unknown_modifier_rows: number;
  unknown_side_rows: number;
  duplicate_rows: number;
  removed_rows: number;
  unresolved_rows: number;
  wsab_bound_rows: number;
  goblin_excluded: number;
  half_line_excluded: number;
  modeled: number;
  unsupported: number;
  research_only: number;
  final_model_population: number;
}

export interface FrozenBoard {
  schemaId: string;
  parserVersion: string;
  learningRevision: string;
  predictiveClaim: string;
  v5Mount: {
    state: string;
    har_decoder: string;
    expected_source_sha256: string;
    expected_ledger_sha256: string;
  };
  sourceAdapter: string;
  harSha256: string;
  captureStart: string;
  captureEnd: string;
  forecastCutoff: string;
  redactedSecrets: number;
  indexStats: Record<string, number>;
  warnings: string[];
  rows: BoardRow[];
  unresolvedRows: string[];
  eventIds: string[];
  accounting: BoardAccounting;
  contentHash: string;
}

export function accountRows(rows: BoardRow[], extras: Partial<BoardAccounting> = {}): BoardAccounting {
  const unique = new Set(rows.map((r) => r.projectionId));
  return {
    raw_projection_rows: rows.length,
    unique_offer_rows: unique.size,
    standard_rows: rows.filter((r) => r.modifier === "STANDARD").length,
    goblin_rows: rows.filter((r) => r.modifier === "GOBLIN").length,
    demon_rows: rows.filter((r) => r.modifier === "DEMON").length,
    unknown_modifier_rows: rows.filter((r) => r.modifier === "OTHER").length,
    unknown_side_rows: rows.filter((r) => r.side === "UNKNOWN").length,
    duplicate_rows: Math.max(0, rows.length - unique.size),
    removed_rows: 0,
    unresolved_rows: rows.filter((r) => r.market === "unknown" || r.league === "UNKNOWN").length,
    wsab_bound_rows: rows.filter((r) => r.wsabMarketBound).length,
    goblin_excluded: extras.goblin_excluded ?? 0,
    half_line_excluded: extras.half_line_excluded ?? 0,
    modeled: extras.modeled ?? 0,
    unsupported: extras.unsupported ?? 0,
    research_only: extras.research_only ?? 0,
    final_model_population: extras.final_model_population ?? rows.filter((r) => r.modifier !== "GOBLIN").length,
  };
}

export function freezeBoard(ingest: HarIngestResult, cutoff: string): FrozenBoard {
  const rows = ingest.rows;
  const accounting = accountRows(rows);
  const payload: Omit<FrozenBoard, "contentHash"> = {
    schemaId: "BOARD_JSON_V1_2026-08-28",
    parserVersion: ingest.parserVersion,
    learningRevision: LEARNING_REVISION,
    predictiveClaim: PREDICTIVE_CLAIM,
    v5Mount: {
      state: "ABSENT_IN_THIS_WORKSPACE",
      har_decoder: ingest.v5Decoder,
      expected_source_sha256: EXPECTED_V5_SOURCE,
      expected_ledger_sha256: EXPECTED_V5_LEDGER,
    },
    sourceAdapter: ingest.adapter,
    harSha256: ingest.harSha256,
    captureStart: ingest.captureStart,
    captureEnd: ingest.captureEnd,
    forecastCutoff: cutoff,
    redactedSecrets: ingest.redactedSecrets,
    indexStats: ingest.indexStats,
    warnings: ingest.warnings,
    rows,
    unresolvedRows: rows.filter((r) => r.market === "unknown" || r.league === "UNKNOWN").map((r) => r.projectionId),
    eventIds: [...new Set(rows.map((r) => r.eventId))],
    accounting,
  };
  return { ...payload, contentHash: contentHash(payload) };
}
