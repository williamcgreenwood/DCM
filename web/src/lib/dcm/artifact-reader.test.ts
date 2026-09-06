import assert from "node:assert/strict";
import { test } from "node:test";
import { pythonUnavailable, viewFromPythonArtifacts } from "./artifact-reader.ts";

test("missing python does not invent probabilities", () => {
  const v = pythonUnavailable("not mounted");
  assert.equal(v.pythonAvailable, false);
  assert.equal(v.engine, "PYTHON");
  assert.equal(v.ranked.length, 0);
  assert.equal(v.card.length, 0);
  assert.equal(v.population.length, 0);
  assert.equal(v.board.length, 0);
  assert.ok(v.blockers.some((b) => b.code === "PYTHON_ENGINE_NOT_MOUNTED"));
});

test("viewer copies python P and leaves missing P null", () => {
  const v = viewFromPythonArtifacts({
    run_integrity: {
      rawRows: 2,
      modeled: 1,
      playable: 0,
      cardSize: 0,
      productionSelectionReady: false,
      researchComplete: true,
      productionResearchComplete: false,
    },
    board: {
      rows: [{ projectionId: "x", playerName: "A", offeredHigher: true, offeredLower: false, line: 12.5 }],
    },
    top25_ranked: [{ player: "A", selectedP: 0.4, productionSelectable: false, projectionId: "x" }],
    top25_qualified: [],
    strict_card: [],
    full_population: '{"player":"A","selectedP":0.4,"projectionId":"x"}\n{"player":"B","projectionId":"y"}',
    frozen_forecast: { frozenForecastHash: "abc" },
  });
  assert.equal(v.engine, "PYTHON");
  assert.equal(v.pythonAvailable, true);
  assert.equal(v.ranked[0].selectedP, 0.4);
  assert.equal(v.population[1].selectedP, null);
  assert.equal(v.population[1].player, "B");
  assert.equal(v.card.length, 0);
  assert.equal(v.board[0].offeredLower, false);
  assert.equal(v.freezeHash, "abc");
});

test("unknown offered side stays false rather than both", () => {
  const v = viewFromPythonArtifacts({
    run_integrity: {},
    board: { rows: [{ projectionId: "z", playerName: "C" }] },
    top25_ranked: [],
    strict_card: [],
    frozen_forecast: {},
  });
  assert.equal(v.board[0].offeredHigher, false);
  assert.equal(v.board[0].offeredLower, false);
});
