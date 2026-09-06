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

test("runFromHar does not compute probabilities in TypeScript", async () => {
  await assert.rejects(() => runFromHar(DEMO_HAR), /CANONICAL_ENGINE_IS_PYTHON/);
});

test("hash excludes timestamps and is stable", () => {
  const a = contentHash({ x: 1, created_at_utc: "A" });
  const b = contentHash({ created_at_utc: "B", x: 1 });
  assert.equal(a, b);
});

test("verify_install does not bump LR or claim optimized 6.0", () => {
  const v = verifyInstall();
  assert.equal(v.learningRevision, "LR000000");
  assert.equal(v.predictiveClaim, "NONE");
  assert.equal(v.optimizedDcm60Claim, false);
  assert.equal(v.hostPerformanceCertified, false);
  assert.equal(v.chatgptOperable, true);
});
