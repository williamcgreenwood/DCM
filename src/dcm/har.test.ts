import assert from "node:assert/strict";
import { test } from "node:test";
import { DEMO_HAR } from "./demo-board.ts";
import { ingestHar } from "./har.ts";
import { runFromHar } from "./run.ts";
import { sha256Hex } from "./sha256.ts";

test("sha256 abc", async () => {
  assert.equal(await sha256Hex("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
});

test("synthetic HAR walks entries and accounts goblins before exclusion", async () => {
  const ing = await ingestHar(DEMO_HAR);
  assert.equal(ing.adapter, "SYNTHETIC");
  assert.equal(ing.v5Decoder, "NOT_MOUNTED");
  assert.ok(ing.rows.length >= 30);
  assert.ok(ing.rows.some((r) => r.modifier === "GOBLIN"));
  assert.equal(ing.harSha256.length, 64);
});

test("PrizePicks JSON:API payload normalizes line/modifier/league", async () => {
  const payload = {
    data: [
      {
        id: "9001",
        type: "projection",
        attributes: { line_score: 24.5, stat_type: "Points", odds_type: "standard" },
        relationships: {
          new_player: { data: { id: "p1", type: "new_player" } },
          league: { data: { id: "7", type: "league" } },
          new_game: { data: { id: "g1", type: "new_game" } },
        },
      },
      {
        id: "9002",
        type: "projection",
        attributes: { line_score: 12.5, stat_type: "Points", odds_type: "goblin" },
        relationships: {
          new_player: { data: { id: "p2", type: "new_player" } },
          league: { data: { id: "7", type: "league" } },
          new_game: { data: { id: "g1", type: "new_game" } },
        },
      },
    ],
    included: [
      { id: "p1", type: "new_player", attributes: { display_name: "Jayson Tatum", team: "BOS", position: "F" } },
      { id: "p2", type: "new_player", attributes: { display_name: "Jrue Holiday", team: "BOS", position: "G" } },
      { id: "7", type: "league", attributes: { name: "NBA", sport: "Basketball" } },
      { id: "g1", type: "new_game", attributes: { home_name: "NYK", away_name: "BOS" } },
    ],
  };
  const ing = await ingestHar(payload);
  assert.equal(ing.adapter, "PRIZEPICKS_JSONAPI");
  assert.equal(ing.rows.length, 2);
  assert.equal(ing.rows[0].market, "pts");
  assert.equal(ing.rows[0].league, "NBA");
  assert.equal(ing.rows[1].modifier, "GOBLIN");
});

test("unknown shape fail closed", async () => {
  const ing = await ingestHar({ foo: [1, 2, 3] });
  assert.equal(ing.adapter, "UNKNOWN");
  assert.equal(ing.rows.length, 0);
  assert.ok(ing.warnings.includes("UNKNOWN_HAR_SHAPE"));
});

test("board HAR with unknown side still models when both sides offered", async () => {
  const run = await runFromHar({
    data: [
      {
        projectionId: "x1",
        sportFamily: "basketball",
        league: "NBA",
        eventId: "E",
        eventLabel: "BOS @ NYK",
        playerId: "TATUM",
        playerName: "Jayson Tatum",
        teamId: "BOS",
        team: "BOS",
        opponent: "NYK",
        market: "pts",
        marketLabel: "Points",
        line: 27.5,
        side: "UNKNOWN",
        offeredHigher: true,
        offeredLower: true,
        modifier: "STANDARD",
        boardId: "FULL_GAME",
        productType: "PLAYER_PICKS",
        role: "F",
      },
    ],
  });
  assert.equal(run.population[0].state, "MODELED");
  assert.ok(run.population[0].selectedSide === "MORE" || run.population[0].selectedSide === "LESS");
});

test("CFB official name is flagged without inventing a player id", async () => {
  const run = await runFromHar(DEMO_HAR);
  const sayin = run.board.find((r) => r.playerName === "Julian Sayin");
  assert.ok(sayin);
  assert.equal(sayin?.cfbOfficialNameListed, true);
  assert.equal(sayin?.cfbOfficialPlayerId, null);
});

test("run does not claim optimized 6.0 or promote LR", async () => {
  const run = await runFromHar(DEMO_HAR);
  assert.equal(run.integrity.learningRevision, "LR000000");
  assert.equal(run.integrity.predictiveClaim, "NONE");
  assert.equal(run.integrity.optimizedDcm60Claim, false);
  assert.equal(run.integrity.v5Decoder, "NOT_MOUNTED");
  assert.ok(run.accounting.raw_projection_rows >= 30);
  assert.ok(run.accounting.goblin_rows >= 1);
});
