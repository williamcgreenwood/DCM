import { contentHash } from "./hash.ts";
import { DEMO_BOARD } from "./demo-board.ts";
import type { BoardRow, Modifier, Side } from "./types.ts";

export interface HarIngestResult {
  adapter: "SYNTHETIC" | "PRIZEPICKS_JSON" | "UNKNOWN";
  rows: BoardRow[];
  harHash: string;
  parserVersion: string;
  redactedSecrets: number;
  warnings: string[];
}

const SECRET_KEYS = ["cookie", "authorization", "set-cookie", "csrf", "access_token", "refresh_token"];

export function ingestHar(raw: unknown): HarIngestResult {
  const text = typeof raw === "string" ? raw : JSON.stringify(raw);
  const harHash = contentHash(text);
  const warnings: string[] = [];
  let redacted = 0;
  const lower = text.toLowerCase();
  for (const k of SECRET_KEYS) {
    if (lower.includes(k)) redacted += 1;
  }
  if (redacted) warnings.push("Secrets detected in capture; redacted from persistence. Never replay HAR.");

  try {
    const obj = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (obj && typeof obj === "object" && (obj as { _pillars?: { kind?: string } })._pillars?.kind === "SYNTHETIC_HAR") {
      return {
        adapter: "SYNTHETIC",
        rows: DEMO_BOARD.map((r) => ({ ...r })),
        harHash,
        parserVersion: "HAR_SYNTHETIC_V1",
        redactedSecrets: redacted,
        warnings,
      };
    }
    const data = (obj as { data?: BoardRow[] })?.data;
    if (Array.isArray(data) && data[0]?.projectionId) {
      return {
        adapter: "PRIZEPICKS_JSON",
        rows: data as BoardRow[],
        harHash,
        parserVersion: "HAR_JSON_BOARD_V1",
        redactedSecrets: redacted,
        warnings,
      };
    }
  } catch {
    warnings.push("HAR parse failed closed.");
  }
  return {
    adapter: "UNKNOWN",
    rows: [],
    harHash,
    parserVersion: "HAR_UNKNOWN",
    redactedSecrets: redacted,
    warnings: [...warnings, "UNKNOWN_HAR_SHAPE"],
  };
}

export function isGoblin(row: BoardRow): boolean {
  return row.modifier === "GOBLIN";
}

export function halfLineAvoid(row: BoardRow): boolean {
  if (row.sportFamily !== "baseball") return false;
  if (row.market !== "hits_runs_rbi") return false;
  return Math.abs(row.line - 0.5) < 1e-9;
}

export function offeredSideOk(row: BoardRow): boolean {
  if (row.side === "UNKNOWN") return false;
  if (row.side === "MORE" && !row.offeredHigher) return false;
  if (row.side === "LESS" && !row.offeredLower) return false;
  return true;
}

export function asSide(s: string): Side | "UNKNOWN" {
  if (s === "MORE" || s === "LESS") return s;
  return "UNKNOWN";
}

export function asModifier(s: string): Modifier {
  if (s === "DEMON" || s === "GOBLIN" || s === "STANDARD" || s === "OTHER") return s;
  return "OTHER";
}
