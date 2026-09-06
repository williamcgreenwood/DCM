import assert from "node:assert/strict";
import { test } from "node:test";
import { mulberry32 } from "./hash.ts";
import { fromWorlds, sampleBasketball, valueFromStats } from "./worlds.ts";
import { buildCard } from "./portfolio.ts";
import { assertNotAfterCutoff } from "./research.ts";
import type { ModeledProp } from "./types.ts";
import { DEMO_BOARD } from "./demo-board.ts";
import { classify } from "./model.ts";

test("TypeScript world sampling is disabled", () => {
  assert.throws(() => sampleBasketball(), /CANONICAL_ENGINE_IS_PYTHON/);
  assert.throws(() => fromWorlds(), /CANONICAL_ENGINE_IS_PYTHON/);
  assert.throws(() => valueFromStats(), /CANONICAL_ENGINE_IS_PYTHON/);
});

test("classify does not model in TypeScript", () => {
  assert.throws(() => classify(), /CANONICAL_ENGINE_IS_PYTHON/);
});

test("portfolio unique player and goblin veto still applies to Python-shaped rows", () => {
  const mk = (id: string, player: string, event: string, market: string, goblin = false): ModeledProp =>
    ({
      row: {
        ...DEMO_BOARD[0],
        projectionId: id,
        playerId: player,
        eventId: event,
        market,
        modifier: goblin ? "GOBLIN" : "STANDARD",
      },
      state: "MODELED",
      grade: "PLAYABLE",
      pHigher: 0.6,
      pLower: 0.4,
      pPush: 0,
      selectedSide: "MORE",
      selectedP: 0.6,
      lowerBound: 0.55,
      mean: 20,
      median: 20,
      opportunityMean: 34,
      reliability: 0.8,
      dataQuality: 0.8,
      volatility: 0.2,
      fragility: 0.1,
      ood: 0.05,
      falseSign: 0.1,
      selectionScore: 0.7,
      rank: 1,
      trueLineTolerance: 1,
      primaryReason: "t",
      primaryRisk: "t",
      evidenceIds: [],
    }) as ModeledProp;
  const card = buildCard([
    mk("a", "TATUM", "E1", "pts"),
    mk("b", "TATUM", "E1", "pra"),
    mk("c", "GOB", "E2", "pts", true),
    mk("d", "JOKIC", "E1", "pra"),
    mk("e", "BRUNSON", "E1", "pts"),
  ]);
  assert.ok(card.every((p) => p.row.modifier !== "GOBLIN"));
  const players = card.map((p) => p.row.playerId);
  assert.equal(players.length, new Set(players).size);
  assert.ok(card.filter((p) => p.row.eventId === "E1").length <= 2);
});

test("temporal leak fails closed", () => {
  assert.throws(() => assertNotAfterCutoff("2026-08-29T00:00:01Z", "2026-08-28T00:00:00Z"));
});
