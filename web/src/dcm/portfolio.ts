/** Unique player, event cap, composite overlap. Never pad. Goblins never enter. */
import type { ModeledProp } from "./types.ts";

const COMPONENTS: Record<string, Set<string>> = {
  pra: new Set(["pts", "reb", "ast"]),
  pass_rush_yds: new Set(["pass_yds", "rush_yds"]),
  rush_rec_yds: new Set(["rush_yds", "rec_yds"]),
  hits_runs_rbi: new Set(["h"]),
};

export function buildCard(qualified: ModeledProp[], maxSize = 6, maxPerEvent = 2): ModeledProp[] {
  const card: ModeledProp[] = [];
  const players = new Set<string>();
  const events = new Map<string, number>();
  const marketsByPlayer = new Map<string, Set<string>>();
  for (const p of qualified) {
    if (card.length >= maxSize) break;
    const row = p.row;
    if (row.modifier === "GOBLIN") continue;
    if (players.has(row.playerId)) continue;
    if ((events.get(row.eventId) ?? 0) >= maxPerEvent) continue;
    const have = marketsByPlayer.get(row.playerId) ?? new Set<string>();
    const overlap = COMPONENTS[row.market];
    if (overlap) {
      let hit = false;
      for (const m of have) if (overlap.has(m)) hit = true;
      if (hit) continue;
    }
    let blocked = false;
    for (const existing of have) {
      if (COMPONENTS[existing]?.has(row.market)) blocked = true;
    }
    if (blocked) continue;
    card.push(p);
    players.add(row.playerId);
    events.set(row.eventId, (events.get(row.eventId) ?? 0) + 1);
    have.add(row.market);
    marketsByPlayer.set(row.playerId, have);
  }
  return card;
}
