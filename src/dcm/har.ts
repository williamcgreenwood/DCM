import { CFB_OFFICIAL_NAMES } from "./cfb-names.ts";
import { BASKETBALL_MARKETS, FOOTBALL_MARKETS, mapLeague, mapStat, marketLabel } from "./markets.ts";
import { sha256Hex } from "./sha256.ts";
import type { BoardRow, Modifier, Side } from "./types.ts";

export const PARSER_VERSION = "HAR_ADAPTER_V6_DEV_2026-08-28";
export const V5_DECODER = "NOT_MOUNTED";

export interface HarIngestResult {
  adapter: "SYNTHETIC" | "PRIZEPICKS_JSONAPI" | "PRIZEPICKS_NORMALIZED" | "PRIZEPICKS_FLAT" | "OUTLIER_BET" | "UNKNOWN";
  rows: BoardRow[];
  harHash: string;
  harSha256: string;
  parserVersion: string;
  redactedSecrets: number;
  warnings: string[];
  captureStart: string;
  captureEnd: string;
  indexStats: Record<string, number>;
  v5Decoder: string;
  synthetic: boolean;
}

const SECRET_KEYS = ["cookie", "authorization", "set-cookie", "csrf", "access_token", "refresh_token", "session"];
const DENY = ["/auth", "/login", "/session", "/oauth", "/users/me", "/wallet", "/stripe", "/checkout", "/entries", "/account"];
const ALLOW = ["prizepicks.com", "outlier.bet", "outlier.com", "api.outlier"];

function countSecrets(text: string): number {
  const lower = text.toLowerCase();
  let n = 0;
  for (const k of SECRET_KEYS) if (lower.includes(k)) n += 1;
  return n;
}

function allowlisted(url: string): boolean {
  const u = url.toLowerCase();
  if (DENY.some((d) => u.includes(d))) return false;
  return ALLOW.some((h) => u.includes(h));
}

function denied(url: string): boolean {
  const u = url.toLowerCase();
  return DENY.some((d) => u.includes(d));
}

function asModifier(s: string): Modifier {
  const u = s.toLowerCase();
  if (u.includes("goblin")) return "GOBLIN";
  if (u.includes("demon")) return "DEMON";
  if (u.includes("standard") || u === "" || u === "none") return "STANDARD";
  return "OTHER";
}

export function asSide(s: string): Side | "UNKNOWN" {
  if (s === "MORE" || s === "LESS") return s;
  const u = s.toUpperCase();
  if (u === "OVER" || u === "HIGHER") return "MORE";
  if (u === "UNDER" || u === "LOWER") return "LESS";
  return "UNKNOWN";
}

function rel(item: Record<string, unknown>, included: Map<string, Record<string, unknown>>, ...names: string[]) {
  const rels = (item.relationships as Record<string, { data?: { type?: string; id?: string } | Array<{ type?: string; id?: string }> }>) || {};
  for (const name of names) {
    let ref = rels[name]?.data;
    if (Array.isArray(ref)) ref = ref[0];
    if (!ref?.id) continue;
    const found = included.get(`${ref.type}:${ref.id}`);
    if (found) return found;
  }
  return undefined;
}

function attrs(node: Record<string, unknown> | undefined): Record<string, unknown> {
  const a = node?.attributes;
  return a && typeof a === "object" ? (a as Record<string, unknown>) : {};
}

function annotate(row: BoardRow): BoardRow {
  const football = row.league === "NFL" || row.league === "CFB" || row.league === "NFLP";
  const bound = football
    ? FOOTBALL_MARKETS.has(row.market)
    : (row.league === "NBA" || row.league === "WNBA") && BASKETBALL_MARKETS.has(row.market);
  return {
    ...row,
    wsabPlugin: bound ? (football ? "football" : "basketball") : null,
    wsabMarketBound: bound,
    cfbOfficialNameListed: CFB_OFFICIAL_NAMES.has(row.playerName.toLowerCase()),
    cfbOfficialPlayerId: null,
  };
}

function fromNormalized(item: Record<string, unknown>): BoardRow | null {
  if (!item.projectionId) return null;
  const line = Number(item.line);
  if (!Number.isFinite(line)) return null;
  const market = String(item.market || "");
  const side = asSide(String(item.side || "UNKNOWN"));
  return annotate({
    projectionId: String(item.projectionId),
    sportFamily: String(item.sportFamily || "unknown"),
    league: String(item.league || "UNKNOWN"),
    eventId: String(item.eventId || ""),
    eventLabel: String(item.eventLabel || ""),
    playerId: String(item.playerId || ""),
    playerName: String(item.playerName || ""),
    teamId: String(item.teamId || item.team || ""),
    team: String(item.team || ""),
    opponent: String(item.opponent || ""),
    market,
    marketLabel: String(item.marketLabel || marketLabel(market)),
    line,
    side,
    offeredHigher: Boolean(item.offeredHigher ?? side === "MORE"),
    offeredLower: Boolean(item.offeredLower ?? side === "LESS"),
    modifier: asModifier(String(item.modifier || "OTHER")),
    boardId: String(item.boardId || "FULL_GAME"),
    productType: "PLAYER_PICKS",
    role: String(item.role || ""),
  });
}

function fromJsonApi(item: Record<string, unknown>, included: Map<string, Record<string, unknown>>): BoardRow | null {
  const a = attrs(item);
  const line = Number(a.line_score ?? a.lineScore ?? a.line);
  if (!Number.isFinite(line)) return null;
  const player = rel(item, included, "new_player", "player");
  const leagueN = rel(item, included, "league");
  const game = rel(item, included, "new_game", "game");
  const pa = attrs(player);
  const la = attrs(leagueN);
  const ga = attrs(game);
  const [league, sportFamily] = mapLeague(String(la.name || la.league || ""), String(la.sport || ""));
  const stat = String(a.stat_type || a.statType || "unknown");
  const [market, marketLabelS] = mapStat(stat);
  const playerName = String(pa.display_name || pa.name || a.description || "UNKNOWN");
  const team = String(pa.team || pa.team_name || ga.home_name || "UNK");
  const home = String(ga.home_name || ga.home || "");
  const away = String(ga.away_name || ga.away || "");
  const opponent = team === home ? away : home || away || "UNK";
  const odds = String(a.odds_type || a.oddsType || "standard");
  const modifier = asModifier(odds);
  const sideRaw = asSide(String(a.selected_side || a.side || ""));
  const offeredHigher = modifier === "GOBLIN" ? true : true;
  const offeredLower = modifier === "GOBLIN" ? false : true;
  return annotate({
    projectionId: String(item.id || `${playerName}_${market}_${line}`),
    sportFamily,
    league,
    eventId: String(game?.id || `${league}_${team}_${opponent}`),
    eventLabel: away && home ? `${away} @ ${home}` : `${team} vs ${opponent}`,
    playerId: String(player?.id || playerName),
    playerName,
    teamId: team,
    team,
    opponent,
    market,
    marketLabel: marketLabelS,
    line,
    side: sideRaw,
    offeredHigher,
    offeredLower,
    modifier,
    boardId: "FULL_GAME",
    productType: "PLAYER_PICKS",
    role: String(pa.position || ""),
  });
}

function parsePayload(obj: unknown): { adapter: HarIngestResult["adapter"]; rows: BoardRow[] } | null {
  if (!obj || typeof obj !== "object") return null;
  const rec = obj as Record<string, unknown>;
  const data = rec.data;
  if (Array.isArray(data) && data[0] && typeof data[0] === "object" && (data[0] as BoardRow).projectionId) {
    const rows = data.map((x) => fromNormalized(x as Record<string, unknown>)).filter((r): r is BoardRow => !!r);
    return rows.length ? { adapter: "PRIZEPICKS_NORMALIZED", rows } : null;
  }
  if (Array.isArray(data) && data[0] && typeof data[0] === "object") {
    const first = data[0] as Record<string, unknown>;
    const a = attrs(first);
    const looks = first.type === "projection" || first.type === "new_projection" || "line_score" in a || "lineScore" in a;
    if (looks) {
      const included = new Map<string, Record<string, unknown>>();
      for (const n of (rec.included as Record<string, unknown>[]) || []) {
        if (n && n.id != null) included.set(`${n.type}:${n.id}`, n);
      }
      const rows = data
        .filter((x): x is Record<string, unknown> => !!x && typeof x === "object")
        .map((x) => fromJsonApi(x, included))
        .filter((r): r is BoardRow => !!r);
      return rows.length ? { adapter: "PRIZEPICKS_JSONAPI", rows } : null;
    }
  }
  for (const key of ["markets", "props", "offers", "lines"] as const) {
    const seq = rec[key];
    if (Array.isArray(seq) && seq[0] && typeof seq[0] === "object") {
      const rows: BoardRow[] = [];
      seq.forEach((item, idx) => {
        if (!item || typeof item !== "object") return;
        const it = item as Record<string, unknown>;
        const line = Number(it.line ?? it.value ?? it.points);
        const playerName = String(it.player || it.playerName || it.name || "");
        if (!Number.isFinite(line) || !playerName) return;
        const [market, label] = mapStat(String(it.stat || it.market || it.prop || ""));
        const [league, sportFamily] = mapLeague(String(it.league || it.sport || ""), String(it.sport || ""));
        rows.push(
          annotate({
            projectionId: String(it.id || it.projectionId || `out_${idx}_${playerName}_${market}_${line}`),
            sportFamily,
            league,
            eventId: String(it.eventId || `${league}_${it.team || "UNK"}`),
            eventLabel: String(it.event || ""),
            playerId: String(it.playerId || playerName),
            playerName,
            teamId: String(it.team || "UNK"),
            team: String(it.team || "UNK"),
            opponent: String(it.opponent || "UNK"),
            market,
            marketLabel: label,
            line,
            side: asSide(String(it.side || "")),
            offeredHigher: true,
            offeredLower: true,
            modifier: "STANDARD",
            boardId: "FULL_GAME",
            productType: "PLAYER_PICKS",
            role: String(it.position || ""),
          }),
        );
      });
      if (rows.length) return { adapter: "OUTLIER_BET", rows };
    }
  }
  return null;
}

async function indexHar(obj: Record<string, unknown>) {
  const log = (obj.log as Record<string, unknown>) || {};
  const entries = Array.isArray(log.entries) ? (log.entries as Record<string, unknown>[]) : [];
  const stats = { raw_entries: entries.length, denied_endpoints: 0, allowlisted_endpoints: 0, decoded_bodies: 0, duplicate_bodies: 0 };
  const latest = new Map<string, { started: string; body: string }>();
  const seen = new Set<string>();
  for (const ent of entries) {
    const req = (ent.request as Record<string, unknown>) || {};
    const res = (ent.response as Record<string, unknown>) || {};
    const url = String(req.url || "");
    const started = String(ent.startedDateTime || "");
    if (denied(url)) {
      stats.denied_endpoints += 1;
      continue;
    }
    if (!allowlisted(url)) continue;
    stats.allowlisted_endpoints += 1;
    const status = Number(res.status || 0);
    if (status < 200 || status >= 300) continue;
    const content = (res.content as Record<string, unknown>) || {};
    const body = typeof content.text === "string" ? content.text : "";
    if (!body) continue;
    stats.decoded_bodies += 1;
    const h = await sha256Hex(body);
    if (seen.has(h)) stats.duplicate_bodies += 1;
    seen.add(h);
    latest.set(`${req.method || "GET"}:${url.split("?")[0]}`, { started, body });
  }
  return { latest: [...latest.values()], stats };
}

export async function ingestHar(raw: unknown): Promise<HarIngestResult> {
  const text = typeof raw === "string" ? raw : JSON.stringify(raw);
  const harSha256 = await sha256Hex(text);
  const warnings: string[] = [];
  const redacted = countSecrets(text);
  if (redacted) warnings.push("Secrets detected in capture; redacted from persistence. Never replay HAR.");

  let obj: Record<string, unknown> | null = null;
  try {
    obj = (typeof raw === "string" ? JSON.parse(raw) : raw) as Record<string, unknown>;
  } catch {
    warnings.push("HAR parse failed closed.");
  }

  const synthetic = obj?._pillars && typeof obj._pillars === "object" && (obj._pillars as { kind?: string }).kind === "SYNTHETIC_HAR";
  let adapter: HarIngestResult["adapter"] = "UNKNOWN";
  let rows: BoardRow[] = [];
  let parserVersion = PARSER_VERSION;
  let captureStart = "";
  let captureEnd = "";
  let indexStats: Record<string, number> = {};

  if (obj && obj.log && typeof obj.log === "object") {
    const { latest, stats } = await indexHar(obj);
    indexStats = stats;
    const times = latest.map((e) => e.started).filter(Boolean).sort();
    captureStart = times[0] || "";
    captureEnd = times[times.length - 1] || "";
    const batches: BoardRow[] = [];
    let lastAdapter: HarIngestResult["adapter"] = "UNKNOWN";
    for (const e of latest) {
      try {
        const parsed = parsePayload(JSON.parse(e.body));
        if (parsed) {
          lastAdapter = parsed.adapter;
          batches.push(...parsed.rows);
        }
      } catch {
        warnings.push("NON_JSON_BODY");
      }
    }
    const byId = new Map<string, BoardRow>();
    for (const r of batches) byId.set(r.projectionId, r);
    rows = [...byId.values()];
    adapter = lastAdapter;
  } else if (obj) {
    const parsed = parsePayload(obj);
    if (parsed) {
      adapter = parsed.adapter;
      rows = parsed.rows;
    }
  }

  if (!rows.length) warnings.push("UNKNOWN_HAR_SHAPE");
  if (synthetic) {
    adapter = "SYNTHETIC";
    parserVersion = "HAR_SYNTHETIC_V1";
  }
  if (adapter === "UNKNOWN") parserVersion = "HAR_UNKNOWN";

  return {
    adapter,
    rows,
    harHash: harSha256,
    harSha256,
    parserVersion,
    redactedSecrets: redacted,
    warnings,
    captureStart,
    captureEnd,
    indexStats,
    v5Decoder: V5_DECODER,
    synthetic: Boolean(synthetic),
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
  if (row.side === "UNKNOWN") return row.offeredHigher || row.offeredLower;
  if (row.side === "MORE" && !row.offeredHigher) return false;
  if (row.side === "LESS" && !row.offeredLower) return false;
  return true;
}
