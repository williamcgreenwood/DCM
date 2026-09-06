/** Fixture research graph. Operator fills FileProvider evidence for live HARs. */
import { contentHash } from "./hash.ts";
import type { BoardRow } from "./types.ts";

export interface ResearchRequest {
  request_id: string;
  scope: "SPORT" | "EVENT" | "TEAM" | "PLAYER" | "MARKET";
  scope_id: string;
  need: string;
  forecast_cutoff: string;
}

export interface EvidenceClaim {
  claim_hash: string;
  source_id: string;
  semantic_scope: string;
  scope_id: string;
  claim_type: string;
  observed_at: string;
  forecast_cutoff: string;
}

export function buildRequests(rows: BoardRow[], cutoff: string): ResearchRequest[] {
  const reqs = new Map<string, ResearchRequest>();
  const add = (scope: ResearchRequest["scope"], scope_id: string, need: string) => {
    const rec: ResearchRequest = { request_id: "", scope, scope_id, need, forecast_cutoff: cutoff };
    rec.request_id = `REQ_${contentHash(rec).slice(0, 16)}`;
    reqs.set(rec.request_id, rec);
  };
  for (const r of rows) add("SPORT", `${r.sportFamily}:${r.league}`, "rules_calendar_distribution");
  for (const r of rows) add("EVENT", r.eventId, "start_venue_starters_environment");
  for (const r of rows) add("TEAM", r.teamId, "role_pace_matchup");
  for (const r of rows) add("PLAYER", r.playerId, "status_role_logs_opportunity_efficiency");
  for (const r of rows) {
    if (r.modifier === "GOBLIN") continue;
    add("MARKET", r.projectionId, "definition_line_history");
  }
  return [...reqs.values()];
}

export function fixtureClaims(requests: ResearchRequest[], cutoff: string): EvidenceClaim[] {
  return requests.map((req) => ({
    claim_hash: contentHash({ id: req.request_id, cutoff }),
    source_id: "FIXTURE_SYNTHETIC_V1",
    semantic_scope: req.scope,
    scope_id: req.scope_id,
    claim_type: req.need,
    observed_at: cutoff,
    forecast_cutoff: cutoff,
  }));
}

export function assertNotAfterCutoff(observedAt: string, cutoff: string) {
  if (Date.parse(observedAt) > Date.parse(cutoff)) {
    throw new Error(`TEMPORAL_LEAK: observed_at ${observedAt} > cutoff ${cutoff}`);
  }
}
