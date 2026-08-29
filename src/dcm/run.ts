/** Dual-engine guard. Canonical probabilities live in Python only. */

export function runFromHar(): never {
  throw new Error("CANONICAL_ENGINE_IS_PYTHON");
}

export function verifyInstall() {
  return {
    dcmVersion: "6.0.0+WSAB.E2E.PRODUCTION_PIPELINE.LR000000",
    learningRevision: "LR000000",
    predictiveClaim: "NONE",
    schemaId: "PHASE_BC_SCHEMA_V1_2026-08-25",
    schemaState: "DECLARED_UNVERIFIED",
    v5Source: "ABSENT",
    v5Ledger: "ABSENT",
    v5Decoder: "NOT_MOUNTED",
    wsabBaseline46: "PYTHON_PACKAGE_PRESENT",
    harSpine: "PYTHON_CANONICAL",
    e2eRunner: "PYTHON_CANONICAL",
    lifecycle: "PYTHON_CANONICAL",
    chatgptOperable: true,
    hostPerformanceCertified: false,
    optimizedDcm60Claim: false,
    ok: true,
  };
}
