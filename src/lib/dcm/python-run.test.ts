import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

test("python-run does not hardcode stale cutoff or production fixture/worlds", () => {
  const src = readFileSync(new URL("./python-run.ts", import.meta.url), "utf8");
  assert.equal(src.includes("2026-08-28T00:00:00Z"), false);
  assert.equal(src.includes("2026-08-28T23:59:59Z"), false);
  assert.match(src, /cutoffFromCapture/);
  assert.match(src, /data.research/);
  assert.equal(src.includes('DCM_FAST_WORLDS: "48"'), false);
});
