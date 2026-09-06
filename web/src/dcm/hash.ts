/** Deterministic content hash. Timestamps never enter the payload. */

const FNV = 0x811c9dc5;

export function contentHash(value: unknown): string {
  const json = canonicalize(value);
  let h = FNV;
  for (let i = 0; i < json.length; i++) {
    h ^= json.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  const a = (h >>> 0).toString(16).padStart(8, "0");
  let h2 = 0x811c9dc5;
  for (let i = json.length - 1; i >= 0; i--) {
    h2 ^= json.charCodeAt(i);
    h2 = Math.imul(h2, 0x01000193);
  }
  const b = (h2 >>> 0).toString(16).padStart(8, "0");
  return `dcm8_${a}${b}`;
}

function canonicalize(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(",")}]`;
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj)
    .filter((k) => k !== "createdAtUtc" && k !== "created_at_utc")
    .sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalize(obj[k])}`).join(",")}}`;
}

export function mulberry32(seed: number) {
  let t = seed >>> 0;
  return () => {
    t += 0x6d2b79f5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

export function seedFrom(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
