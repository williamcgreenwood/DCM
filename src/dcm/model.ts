import { selectionState } from "./capabilities.ts";
import { lineSurface } from "./line-surface.ts";
import type { BoardRow, Grade, ModeledProp, RowState, Side } from "./types.ts";
import { fromWorlds, simulatePlayerWorlds, type StatWorld, valueFromStats } from "./worlds.ts";

function gradeOf(
  p: number,
  lb: number,
  demon: boolean,
  fragility: number,
  robustnessArea = 0,
  elasticity = 0,
  falseSign = 0,
): Grade {
  if (demon) {
    if (p >= 0.63 && lb >= 0.56 && robustnessArea >= 1.0 && elasticity <= 0.25 && falseSign <= 0.22 && fragility <= 0.4) {
      return "PLAYABLE";
    }
    if (p >= 0.56) return "LEAN";
    if (p < 0.46) return "TRAP";
    return "PASS";
  }
  if (fragility > 0.55) return p > 0.55 ? "LEAN" : "TRAP";
  if (p >= 0.58 && lb >= 0.52) return "PLAYABLE";
  if (p >= 0.54) return "LEAN";
  if (p < 0.46) return "TRAP";
  return "PASS";
}

function reasonOf(row: BoardRow): { reason: string; risk: string; quality: number } {
  if (row.sportFamily === "basketball") {
    return {
      reason: "Event-once ledger; PRA = PTS+REB+AST in the same draw.",
      risk: "Minute cut / foul trouble.",
      quality: 0.82,
    };
  }
  if (row.league === "NFL" || row.league === "CFB") {
    return {
      reason: "Football primitives; composites from one dropback/rush ledger.",
      risk: "Game script / target steal.",
      quality: row.league === "CFB" ? 0.7 : 0.8,
    };
  }
  if (row.sportFamily === "baseball") {
    return { reason: "MLB PA path is SHADOW_SUPPORTED.", risk: "Not a production promotion.", quality: 0.72 };
  }
  return { reason: "League/market prior only.", risk: "Thin evidence.", quality: 0.4 };
}

export function modelRow(row: BoardRow, state: RowState, blocker?: string, worlds?: StatWorld[]): ModeledProp {
  const empty: ModeledProp = {
    row,
    state,
    blocker,
    grade: null,
    pHigher: null,
    pLower: null,
    pPush: null,
    selectedSide: null,
    selectedP: null,
    lowerBound: null,
    mean: null,
    median: null,
    opportunityMean: null,
    reliability: null,
    dataQuality: null,
    volatility: null,
    fragility: null,
    ood: null,
    falseSign: null,
    selectionScore: null,
    rank: null,
    trueLineTolerance: null,
    primaryReason: blocker ?? "not modeled",
    primaryRisk: blocker ?? "fail-closed",
    evidenceIds: [],
  };
  if (state !== "MODELED") return empty;

  let draws = worlds;
  try {
    draws = draws ?? simulatePlayerWorlds(row, row.projectionId);
    const values = draws.map((w) => valueFromStats(row.market, w));
    const dist = fromWorlds(values, row.line);
    const sum = dist.pHigher + dist.pLower + dist.pPush || 1;
    const pHigher = dist.pHigher / sum;
    const pLower = dist.pLower / sum;
    const pPush = dist.pPush / sum;
    let side: Side;
    if (row.side === "MORE" || row.side === "LESS") side = row.side;
    else if (row.offeredHigher && !row.offeredLower) side = "MORE";
    else if (row.offeredLower && !row.offeredHigher) side = "LESS";
    else if (pHigher >= pLower) side = row.offeredHigher ? "MORE" : "LESS";
    else side = row.offeredLower ? "LESS" : "MORE";
    const selectedP = side === "MORE" ? pHigher : pLower;
    const meta = reasonOf(row);
    const reliability = 0.55 + 0.4 * meta.quality;
    const fragility = row.modifier === "DEMON" ? 0.42 : Math.abs((row.line % 1) - 0.5) < 0.05 ? 0.38 : 0.18;
    const ood = row.league === "CFB" && row.eventId.includes("REG") ? 0.35 : 0.08;
    const falseSign = Math.max(0.04, 0.5 - Math.abs(selectedP - 0.5));
    const lb = Math.max(0.01, selectedP - (0.05 + 0.08 * (1 - meta.quality) + 0.04 * fragility));
    const serious = selectedP >= 0.52 || row.modifier === "DEMON";
    const surf = serious
      ? lineSurface(values, row.line)
      : {
          offered_line: row.line,
          offered_probability: pHigher,
          break_even_line: row.line,
          true_unclamped_line_tolerance: 0,
          edge_elasticity: 0,
          robustness_area: 0,
        };
    const grade = gradeOf(selectedP, lb, row.modifier === "DEMON", fragility, surf.robustness_area, surf.edge_elasticity, falseSign);
    const selectionScore =
      selectedP * 0.45 +
      lb * 0.25 +
      reliability * 0.12 +
      meta.quality * 0.08 -
      fragility * 0.1 -
      ood * 0.08 -
      (row.modifier === "DEMON" ? 0.04 : 0);
    const sd = Math.sqrt(values.reduce((a, v) => a + (v - dist.mean) ** 2, 0) / Math.max(1, values.length));
    return {
      row,
      state,
      blocker,
      grade,
      pHigher,
      pLower,
      pPush,
      selectedSide: side,
      selectedP,
      lowerBound: lb,
      mean: dist.mean,
      median: dist.mean,
      opportunityMean: row.sportFamily === "basketball" ? (row.league === "NBA" ? 34 : 31) : dist.mean,
      reliability,
      dataQuality: meta.quality,
      volatility: Math.min(1, sd / (Math.abs(dist.mean) + 1)),
      fragility,
      ood,
      falseSign,
      selectionScore,
      rank: null,
      trueLineTolerance: surf.true_unclamped_line_tolerance,
      primaryReason: meta.reason,
      primaryRisk: meta.risk,
      evidenceIds: [`E_${row.eventId}`, `T_${row.teamId}`, `P_${row.playerId}`],
    };
  } catch {
    return { ...empty, state: "UNSUPPORTED_FAIL_CLOSED", blocker: "UNSUPPORTED_FAIL_CLOSED" };
  }
}

export function classify(row: BoardRow): { state: RowState; blocker?: string } {
  if (row.modifier === "GOBLIN") return { state: "GOBLIN_EXCLUDED", blocker: "GOBLIN_SELECTION_FORBIDDEN" };
  if (row.modifier === "OTHER") return { state: "MODIFIER_UNKNOWN", blocker: "MODIFIER_UNKNOWN" };
  if (row.side === "UNKNOWN" && !row.offeredHigher && !row.offeredLower) {
    return { state: "OFFERED_SIDE_UNKNOWN", blocker: "OFFERED_SIDE_UNKNOWN" };
  }
  if (row.side === "MORE" && !row.offeredHigher) return { state: "OFFERED_SIDE_UNKNOWN", blocker: "OFFERED_SIDE_UNKNOWN" };
  if (row.side === "LESS" && !row.offeredLower) return { state: "OFFERED_SIDE_UNKNOWN", blocker: "OFFERED_SIDE_UNKNOWN" };
  if (row.sportFamily === "baseball" && row.market === "hits_runs_rbi" && Math.abs(row.line - 0.5) < 1e-9) {
    return { state: "HALF_LINE_POLICY_EXCLUDED", blocker: "HALF_LINE_AVOID_BASEBALL_HRRBI_0_5" };
  }
  const worldFamilies = new Set(["basketball", "gridiron", "baseball"]);
  if (!worldFamilies.has(row.sportFamily)) {
    return { state: "UNSUPPORTED_FAIL_CLOSED", blocker: "UNSUPPORTED_FAIL_CLOSED" };
  }
  const cap = selectionState(row.league, row.market);
  if (cap === "UNSUPPORTED_FAIL_CLOSED") {
    return { state: "UNSUPPORTED_FAIL_CLOSED", blocker: "UNSUPPORTED_FAIL_CLOSED" };
  }
  if (cap === "RESEARCH_ONLY") {
    return { state: "MODELED", blocker: "RESEARCH_ONLY_NOT_SELECTABLE" };
  }
  if (cap === "SHADOW_SUPPORTED") {
    return { state: "MODELED", blocker: "SHADOW_SUPPORTED_NOT_SELECTABLE" };
  }
  return { state: "MODELED" };
}

export { gradeOf };
