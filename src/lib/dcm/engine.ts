/** Dual-engine guard. Canonical probabilities live in Python only. */

export function runDcm(): never {
  throw new Error("CANONICAL_ENGINE_IS_PYTHON");
}

export function runFromHar(): never {
  throw new Error("CANONICAL_ENGINE_IS_PYTHON");
}
