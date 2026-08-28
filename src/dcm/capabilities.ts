import type { ProductionState } from "./types.ts";

export interface CapabilityRow {
  sportFamily: string;
  league: string;
  productType: "PLAYER_PICKS";
  market: string;
  definitionVersion: string;
  physicsPlugin: ProductionState;
  opportunity: ProductionState;
  efficiency: ProductionState;
  conservation: ProductionState;
  marketDefinition: ProductionState;
  participation: ProductionState;
  reboot: ProductionState;
  productionSelection: ProductionState;
  blocker: string | null;
  note: string;
}

const P = "PRODUCTION_SUPPORTED" as const;
const S = "SHADOW_SUPPORTED" as const;
const R = "RESEARCH_ONLY" as const;
const U = "UNSUPPORTED_FAIL_CLOSED" as const;

function row(
  sportFamily: string,
  league: string,
  market: string,
  productionSelection: ProductionState,
  extra: Partial<CapabilityRow> = {},
): CapabilityRow {
  const supported = productionSelection === P || productionSelection === S;
  return {
    sportFamily,
    league,
    productType: "PLAYER_PICKS",
    market,
    definitionVersion: `${league}_${market}_V1_2026-08-27`,
    physicsPlugin: supported ? P : U,
    opportunity: supported ? P : U,
    efficiency: supported ? P : U,
    conservation: supported ? P : U,
    marketDefinition: supported ? P : U,
    participation: extra.participation ?? (supported ? S : U),
    reboot: extra.reboot ?? U,
    productionSelection,
    blocker: productionSelection === U ? "PLUGIN_OR_RULE_UNVERIFIED" : extra.blocker ?? null,
    note: extra.note ?? "",
  };
}

export const CAPABILITIES: CapabilityRow[] = [
  row("basketball", "NBA", "pts", P, { reboot: P, participation: P, note: "Live primitive topology." }),
  row("basketball", "NBA", "reb", P, { reboot: P, participation: P }),
  row("basketball", "NBA", "ast", P, { reboot: P, participation: P }),
  row("basketball", "NBA", "pra", P, { reboot: P, note: "Composite of PTS+REB+AST from same ledger." }),
  row("basketball", "NBA", "3pm", P, { reboot: P }),
  row("basketball", "NBA", "stl", P, { reboot: P }),
  row("basketball", "WNBA", "pts", P, { reboot: P, note: "200-minute team conservation, not NBA 240." }),
  row("basketball", "WNBA", "reb", P, { reboot: P }),
  row("basketball", "WNBA", "pra", P, { reboot: P }),
  row("gridiron", "NFL", "pass_yds", P, { reboot: P, participation: P, note: "Full-game MORE only; defense excluded." }),
  row("gridiron", "NFL", "rush_yds", P, { reboot: P, participation: P }),
  row("gridiron", "NFL", "rec_yds", P, { reboot: P, participation: P }),
  row("gridiron", "NFL", "receptions", P, { reboot: P }),
  row("gridiron", "NFL", "pass_rush_yds", P, { reboot: P, note: "Derived: pass_yds + rush_yds." }),
  row("gridiron", "NFL", "rush_rec_yds", P, { reboot: P }),
  row("gridiron", "NFLP", "pass_yds", R, { reboot: U, blocker: "PRESEASON_RULE_UNVERIFIED", note: "Physics ok; settlement fail-closed." }),
  row("gridiron", "CFB", "pass_yds", P, { reboot: S, note: "CFP Playoff + named list only." }),
  row("gridiron", "CFB", "rec_yds", P, { reboot: S }),
  row("gridiron", "CFL", "pass_yds", U, { note: "Gridiron physics reusable; PrizePicks reboot unverified." }),
  row("baseball", "MLB", "k", S, { reboot: U, note: "Pitchers excluded from batter reboot." }),
  row("baseball", "MLB", "h", S, { reboot: P, participation: P, note: "Batter MORE + ≤2 PA reboot." }),
  row("baseball", "MLB", "tb", S, { reboot: P }),
  row("baseball", "MLB", "hits_runs_rbi", S, { reboot: P, note: "Composite H+R+RBI; 0.5 half-line policy AVOID_BY_DEFAULT." }),
  row("baseball", "KBO", "k", R, { note: "Architecture reuse; MLB params forbidden." }),
  row("combat", "UFC", "sig_strikes", R, { note: "Shared fight clock; landed ≤ attempted." }),
  row("combat", "BOXING", "punches_landed", U, { note: "Never reuse UFC significant-strike semantics." }),
  row("soccer", "EPL", "shots", U, { note: "Start-dependent DNP; no verified reboot row." }),
  row("hockey", "NHL", "sog", U, { note: "TOI/shift plugin DESIGNED, not production." }),
  row("racket", "ATP", "aces", U, { note: "Point→game→set path DESIGNED." }),
  row("cricket", "T20", "runs", U, { note: "Format-mandatory; T20≠ODI≠Test." }),
  row("golf", "PGA", "strokes", U, { note: "Strokes gained is evidence, not a primitive." }),
  row("esports", "CS2", "kills", U, { note: "Title+patch keyed; no generic ESPORTS model." }),
];

export function lookupCapability(league: string, market: string): CapabilityRow | undefined {
  return CAPABILITIES.find((c) => c.league === league && c.market === market);
}

export function selectionState(league: string, market: string): ProductionState {
  return lookupCapability(league, market)?.productionSelection ?? "UNSUPPORTED_FAIL_CLOSED";
}
