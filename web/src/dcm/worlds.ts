/** Dual-engine guard. World sampling is Python-only. */

export function sampleBasketball(): never {
  throw new Error("CANONICAL_ENGINE_IS_PYTHON");
}

export function fromWorlds(): never {
  throw new Error("CANONICAL_ENGINE_IS_PYTHON");
}

export function valueFromStats(): never {
  throw new Error("CANONICAL_ENGINE_IS_PYTHON");
}

export function simulatePlayerWorlds(): never {
  throw new Error("CANONICAL_ENGINE_IS_PYTHON");
}
