import assert from "node:assert/strict";
import { test } from "node:test";
import { DEMO_HAR } from "./demo-board.ts";
import { ingestHar } from "./har.ts";
import { contentHash } from "./hash.ts";
import { runFromHar, verifyInstall } from "./run.ts";

test("synthetic HAR ingest accounts every row", async () => {
  const ing = await ingestHar(DEMO_HAR);
  assert.equal(ing.adapter, "SYNTHETIC");
  assert.ok(ing.rows.length >= 30);
});

test("full board is processed; Goblins never enter the card", async () => {
  const run = await runFromHar(DEMO_HAR);
  assert.equal(run.integrity.rawRows, run.board.length);
  assert.ok(run.integrity.goblinExcluded >= 1);
  assert.ok(run.card.every((p) => p.row.modifier !== "GOBLIN"));
  assert.ok(run.top25Qualified.every((p) => p.row.modifier !== "GOBLIN"));
  assert.ok(run.top25Qualified.every((p) => p.grade === "PLAYABLE"));
});

test("empty-or-short card is legal — never pad to six", async () => {
  const run = await runFromHar(DEMO_HAR);
  assert.ok(run.card.length <= 6);
  assert.ok(run.card.length <= run.top25Qualified.length);
  const ids = run.card.map((p) => p.row.playerId);
  assert.equal(ids.length, new Set(ids).size);
  assert.ok(run.card.every((p) => p.grade === "PLAYABLE"));
  assert.ok(run.card.every((p) => p.row.modifier !== "GOBLIN"));
});

test("unsupported sports fail closed after inventory", async () => {
  const run = await runFromHar(DEMO_HAR);
  const soccer = run.population.filter((p) => p.row.league === "EPL");
  assert.ok(soccer.length >= 1);
  assert.ok(soccer.every((p) => p.state === "UNSUPPORTED_FAIL_CLOSED"));
  const cfl = run.population.filter((p) => p.row.league === "CFL");
  assert.ok(cfl.every((p) => p.state === "UNSUPPORTED_FAIL_CLOSED"));
});

test("baseball 0.5 H+R+RBI half-line policy excludes without being a theorem", async () => {
  const run = await runFromHar(DEMO_HAR);
  const hrrbi = run.population.filter((p) => p.row.market === "hits_runs_rbi");
  assert.ok(hrrbi.length >= 1);
  assert.ok(hrrbi.every((p) => p.state === "HALF_LINE_POLICY_EXCLUDED" || p.state === "GOBLIN_EXCLUDED"));
});

test("probabilities simplex on modeled rows", async () => {
  const run = await runFromHar(DEMO_HAR);
  for (const p of run.population) {
    if (p.state !== "MODELED" || p.pHigher == null) continue;
    const s = (p.pHigher ?? 0) + (p.pLower ?? 0) + (p.pPush ?? 0);
    assert.ok(Math.abs(s - 1) < 1e-6, `${p.row.projectionId} simplex ${s}`);
  }
});

test("hash excludes timestamps and is stable", () => {
  const a = contentHash({ x: 1, created_at_utc: "A" });
  const b = contentHash({ created_at_utc: "B", x: 1 });
  assert.equal(a, b);
});

test("run is deterministic", async () => {
  const a = await runFromHar(DEMO_HAR);
  const b = await runFromHar(DEMO_HAR);
  assert.equal(a.integrity.freezeHash, b.integrity.freezeHash);
  assert.equal(a.integrity.playableCount, b.integrity.playableCount);
});

test("verify_install does not bump LR or claim optimized 6.0", () => {
  const v = verifyInstall();
  assert.equal(v.learningRevision, "LR000000");
  assert.equal(v.predictiveClaim, "NONE");
  assert.equal(v.optimizedDcm60Claim, false);
  assert.equal(v.hostPerformanceCertified, false);
  assert.equal(v.chatgptOperable, true);
});

test("completion gates are all true on demo", async () => {
  const run = await runFromHar(DEMO_HAR);
  assert.equal(run.gates.BOARD_COMPLETE, true);
  assert.equal(run.gates.RESEARCH_COMPLETE, true);
  assert.equal(run.gates.MODEL_COMPLETE, true);
  assert.equal(run.gates.RANK_COMPLETE, true);
  assert.equal(run.gates.FREEZE_COMPLETE, true);
  assert.equal(run.integrity.chatgptOperable, true);
  assert.equal(run.integrity.hostPerformanceCertified, false);
  assert.equal(run.integrity.optimizedDcm60Claim, false);
  assert.ok(run.integrity.eventWorlds >= 1);
  assert.ok(run.research.requested >= 1);
  assert.equal(run.dag.completed, 7);
});
