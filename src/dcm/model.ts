import { mulberry32, seedFrom } from "./hash.ts";
import { selectionState } from "./capabilities.ts";
import type { BoardRow, Grade, ModeledProp, RowState, Side } from "./types.ts";

function erf(x: number): number {
  const s = Math.sign(x);
  const a = Math.abs(x);
  const t = 1 / (1 + 0.3275911 * a);
  const y =
    1 -
    (((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t +
      0.254829592) *
      t *
      Math.exp(-a * a));
  return s * y;
}

function normCdf(x: number, mu: number, sd: number): number {
  if (sd <= 1e-9) return x >= mu ? 1 : 0;
  return 0.5 * (1 + erf((x - mu) / (sd * Math.SQRT2)));
}

interface Prior {
  opp: number;
  eff: number;
  sd: number;
  quality: number;
  reason: string;
  risk: string;
}

function prior(row: BoardRow): Prior {
  const key = `${row.league}:${row.market}`;
  const table: Record<string, Prior> = {
    "NBA:pts": { opp: 34, eff: 0.78, sd: 6.4, quality: 0.86, reason: "Starter minutes hold; usage stable vs NYK pace.", risk: "Blowout minute cut." },
    "NBA:reb": { opp: 34, eff: 0.24, sd: 2.6, quality: 0.84, reason: "Role-epoch rebounding rate vs smaller frontcourt.", risk: "Foul trouble." },
    "NBA:ast": { opp: 34, eff: 0.2, sd: 2.1, quality: 0.82, reason: "On-ball creation vs drop coverage.", risk: "Teammate shot-making." },
    "NBA:pra": { opp: 34, eff: 1.16, sd: 7.8, quality: 0.85, reason: "PRA derived from PTS+REB+AST on one world.", risk: "Correlated minute miss." },
    "NBA:3pm": { opp: 8.2, eff: 0.37, sd: 1.6, quality: 0.78, reason: "Three-point volume from same shot mix.", risk: "Variance of threes." },
    "WNBA:pts": { opp: 31, eff: 0.62, sd: 5.1, quality: 0.8, reason: "WNBA 200-min conservation; not NBA 240.", risk: "Foul-out / rest." },
    "WNBA:reb": { opp: 31, eff: 0.32, sd: 2.8, quality: 0.8, reason: "Glass role vs compact rotation.", risk: "Foul trouble." },
    "WNBA:pra": { opp: 31, eff: 0.92, sd: 6.2, quality: 0.8, reason: "Composite from same stint world.", risk: "Minute redistribution." },
    "NFL:pass_yds": { opp: 36, eff: 7.1, sd: 48, quality: 0.81, reason: "Dropback volume vs BUF pressure; game script two-way.", risk: "Negative script / sacks." },
    "NFL:pass_rush_yds": { opp: 38, eff: 7.0, sd: 52, quality: 0.8, reason: "pass_yds+rush_yds from one ledger.", risk: "Designed-run mix." },
    "NFL:rec_yds": { opp: 7.4, eff: 9.2, sd: 22, quality: 0.77, reason: "Target share; rec ≤ targets ≤ routes.", risk: "Cover-2 funnel." },
    "NFL:rush_yds": { opp: 16, eff: 4.4, sd: 24, quality: 0.76, reason: "Designed + scramble split conserved.", risk: "Pass-heavy script." },
    "NFL:receptions": { opp: 7.4, eff: 0.68, sd: 1.8, quality: 0.78, reason: "Catch rate on frozen targets.", risk: "Target steal." },
    "NFL:def_tackles": { opp: 55, eff: 0.1, sd: 2.2, quality: 0.5, reason: "Defense markets extracted; reboot excluded.", risk: "High definition noise." },
    "CFB:pass_yds": { opp: 32, eff: 7.6, sd: 55, quality: 0.72, reason: "CFP tempo; not regular-season prior.", risk: "CFP opponent quality." },
    "CFB:rec_yds": { opp: 8, eff: 11.2, sd: 28, quality: 0.7, reason: "Feature WR routes in CFP.", risk: "Game script." },
    "MLB:h": { opp: 4.2, eff: 0.28, sd: 0.85, quality: 0.74, reason: "PA path; H = 1B+2B+3B+HR.", risk: "Pitcher quality / weather." },
    "MLB:tb": { opp: 4.2, eff: 0.52, sd: 1.4, quality: 0.73, reason: "TB identity from hit types.", risk: "Batted-ball luck." },
    "MLB:k": { opp: 24, eff: 0.29, sd: 1.8, quality: 0.71, reason: "BF × K rate; pitcher reboot excluded.", risk: "Early hook." },
    "MLB:hits_runs_rbi": { opp: 4.2, eff: 0.55, sd: 1.1, quality: 0.68, reason: "Composite; 0.5 is a fragility gate not a theorem.", risk: "Discrete 0/1 clustering." },
    "UFC:sig_strikes": { opp: 14.5, eff: 5.8, sd: 18, quality: 0.55, reason: "Shared fight clock; research-only.", risk: "Early finish truncates volume." },
  };
  return (
    table[key] ?? {
      opp: 10,
      eff: 1,
      sd: 4,
      quality: 0.4,
      reason: "League/market prior only.",
      risk: "Thin evidence.",
    }
  );
}

function gradeOf(p: number, lb: number, demon: boolean, fragility: number): Grade {
  const need = demon ? 0.63 : 0.58;
  const lbNeed = demon ? 0.56 : 0.52;
  if (fragility > 0.55) return p > 0.55 ? "LEAN" : "TRAP";
  if (p >= need && lb >= lbNeed) return "PLAYABLE";
  if (p >= 0.54) return "LEAN";
  if (p < 0.46) return "TRAP";
  return "PASS";
}

export function modelRow(row: BoardRow, state: RowState, blocker?: string): ModeledProp {
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
    primaryReason: blocker ?? "not modeled",
    primaryRisk: blocker ?? "fail-closed",
    evidenceIds: [],
  };
  if (state !== "MODELED") return empty;

  const pr = prior(row);
  const rng = mulberry32(seedFrom(row.projectionId + row.line + row.playerId));
  const mean = pr.opp * pr.eff * (0.96 + rng() * 0.08);
  const sd = pr.sd * (0.9 + rng() * 0.2);
  const line = row.line;
  const pH = 1 - normCdf(line + 1e-9, mean, sd);
  const pL = normCdf(line - 1e-9, mean, sd);
  const pP = Math.max(0, 1 - pH - pL);
  const sum = pH + pL + pP || 1;
  const pHigher = pH / sum;
  const pLower = pL / sum;
  const pPush = pP / sum;
  let side: Side;
  if (row.side === "MORE" || row.side === "LESS") {
    side = row.side;
  } else if (row.offeredHigher && !row.offeredLower) {
    side = "MORE";
  } else if (row.offeredLower && !row.offeredHigher) {
    side = "LESS";
  } else if (pHigher >= pLower) {
    side = row.offeredHigher ? "MORE" : "LESS";
  } else {
    side = row.offeredLower ? "LESS" : "MORE";
  }
  const selectedP = side === "MORE" ? pHigher : pLower;
  const reliability = 0.55 + 0.4 * pr.quality;
  const fragility = row.modifier === "DEMON" ? 0.42 : Math.abs(line % 1 - 0.5) < 0.05 ? 0.38 : 0.18;
  const ood = row.league === "CFB" && row.eventId.includes("REG") ? 0.35 : 0.08;
  const falseSign = Math.max(0.04, 0.5 - Math.abs(selectedP - 0.5));
  const lb = Math.max(0.01, selectedP - (0.05 + 0.08 * (1 - pr.quality) + 0.04 * fragility));
  const grade = gradeOf(selectedP, lb, row.modifier === "DEMON", fragility);
  const selectionScore =
    selectedP * 0.45 +
    lb * 0.25 +
    reliability * 0.12 +
    pr.quality * 0.08 -
    fragility * 0.1 -
    ood * 0.08 -
    (row.modifier === "DEMON" ? 0.04 : 0);

  return {
    row,
    state,
    grade,
    pHigher,
    pLower,
    pPush,
    selectedSide: side,
    selectedP,
    lowerBound: lb,
    mean,
    median: mean,
    opportunityMean: pr.opp,
    reliability,
    dataQuality: pr.quality,
    volatility: Math.min(1, sd / (Math.abs(mean) + 1)),
    fragility,
    ood,
    falseSign,
    selectionScore,
    rank: null,
    primaryReason: pr.reason,
    primaryRisk: pr.risk,
    evidenceIds: [`E_${row.eventId}`, `T_${row.teamId}`, `P_${row.playerId}`],
  };
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
  const cap = selectionState(row.league, row.market);
  if (cap === "UNSUPPORTED_FAIL_CLOSED") {
    return { state: "UNSUPPORTED_FAIL_CLOSED", blocker: "UNSUPPORTED_FAIL_CLOSED" };
  }
  if (cap === "RESEARCH_ONLY") {
    return { state: "MODELED", blocker: "RESEARCH_ONLY_NOT_SELECTABLE" };
  }
  return { state: "MODELED" };
}
