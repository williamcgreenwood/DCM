/** Dual-engine guard. Classification and grading are Python-only. */

export function classify(): never {
  throw new Error("CANONICAL_ENGINE_IS_PYTHON");
}

export function modelRow(): never {
  throw new Error("CANONICAL_ENGINE_IS_PYTHON");
}
