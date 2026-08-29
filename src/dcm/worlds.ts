/** Event-once primitive worlds. PRA = PTS+REB+AST in the same draw. */
import { mulberry32, seedFrom } from "./hash.ts";
import type { BoardRow } from "./types.ts";

export type StatWorld = Record<string, number>;

function clip(x: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, x));
}

function gauss(rng: () => number, mu: number, sd: number) {
  const u = Math.max(1e-12, rng());
  const v = rng();
  const z = Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  return mu + sd * z;
}

export function sampleBasketball(rng: () => number, minutes: number): StatWorld {
  const fga = Math.max(0, gauss(rng, minutes * 0.55, 3.2));
  const tpa = clip(gauss(rng, fga * 0.42, 1.8), 0, fga);
  const twopa = fga - tpa;
  const tpm = clip(gauss(rng, tpa * 0.36, 1.1), 0, tpa);
  const twopm = clip(gauss(rng, twopa * 0.52, 1.4), 0, twopa);
  const fgm = twopm + tpm;
  const fta = Math.max(0, gauss(rng, minutes * 0.18, 1.4));
  const ftm = clip(gauss(rng, fta * 0.78, 0.9), 0, fta);
  const oreb = Math.max(0, gauss(rng, minutes * 0.05, 0.7));
  const dreb = Math.max(0, gauss(rng, minutes * 0.18, 1.2));
  const reb = oreb + dreb;
  const ast = Math.max(0, gauss(rng, minutes * 0.14, 1.3));
  const stl = Math.max(0, gauss(rng, minutes * 0.03, 0.5));
  const blk = Math.max(0, gauss(rng, minutes * 0.025, 0.5));
  const tov = Math.max(0, gauss(rng, minutes * 0.08, 0.8));
  const pts = 2 * twopm + 3 * tpm + ftm;
  return {
    minutes,
    fga,
    tpa,
    twopa,
    fgm,
    tpm,
    twopm,
    fta,
    ftm,
    oreb,
    dreb,
    reb,
    ast,
    stl,
    blk,
    tov,
    pts,
    pra: pts + reb + ast,
    pr: pts + reb,
    pa: pts + ast,
    ra: reb + ast,
  };
}

export function sampleFootball(rng: () => number, role: string): StatWorld {
  if (role === "QB" || role === "") {
    const pass_att = Math.max(0, gauss(rng, 34, 6));
    const sacks = Math.max(0, gauss(rng, 2.2, 1.1));
    const scramble = Math.max(0, gauss(rng, 3.0, 1.5));
    const designed = Math.max(0, gauss(rng, 2.0, 1.2));
    const rush_att = designed + scramble;
    const pass_cmp = clip(gauss(rng, pass_att * 0.65, 3), 0, pass_att);
    const pass_yds = Math.max(0, gauss(rng, pass_att * 7.1, 45));
    const rush_yds = Math.max(0, gauss(rng, rush_att * 4.4, 18));
    return {
      pass_att,
      pass_cmp,
      sacks_taken: sacks,
      scramble_att: scramble,
      designed_rush_att: designed,
      rush_att,
      dropbacks: pass_att + sacks + scramble,
      pass_yds,
      rush_yds,
      rec_yds: 0,
      receptions: 0,
      targets: 0,
      routes: 0,
      pass_rush_yds: pass_yds + rush_yds,
      rush_rec_yds: rush_yds,
    };
  }
  const rush_att = Math.max(0, gauss(rng, role === "RB" ? 12 : 1.5, 4));
  const rush_yds = Math.max(0, gauss(rng, rush_att * 4.3, 18));
  const routes = Math.max(0, gauss(rng, role === "WR" || role === "TE" ? 22 : 8, 5));
  const targets = clip(gauss(rng, routes * 0.28, 2), 0, routes);
  const receptions = clip(gauss(rng, targets * 0.68, 1.4), 0, targets);
  const rec_yds = Math.max(0, gauss(rng, receptions * 11.5, 18));
  return {
    pass_att: 0,
    pass_cmp: 0,
    sacks_taken: 0,
    scramble_att: 0,
    designed_rush_att: 0,
    rush_att,
    dropbacks: 0,
    pass_yds: 0,
    rush_yds,
    rec_yds,
    receptions,
    targets,
    routes,
    pass_rush_yds: rush_yds,
    rush_rec_yds: rush_yds + rec_yds,
  };
}

export function sampleBaseball(rng: () => number, pa: number): StatWorld {
  const bb = clip(gauss(rng, pa * 0.09, 0.4), 0, pa);
  const hbp = clip(gauss(rng, pa * 0.01, 0.15), 0, pa - bb);
  const sf = clip(gauss(rng, pa * 0.02, 0.15), 0, pa - bb - hbp);
  const sh = clip(gauss(rng, pa * 0.005, 0.08), 0, pa - bb - hbp - sf);
  const ab = pa - bb - hbp - sf - sh;
  const so = clip(gauss(rng, ab * 0.24, 0.7), 0, ab);
  const hr = clip(gauss(rng, ab * 0.04, 0.35), 0, ab);
  const triple = clip(gauss(rng, ab * 0.005, 0.08), 0, Math.max(0, ab - hr));
  const dbl = clip(gauss(rng, ab * 0.05, 0.35), 0, Math.max(0, ab - hr - triple));
  const single = clip(gauss(rng, ab * 0.15, 0.55), 0, Math.max(0, ab - hr - triple - dbl));
  const h = single + dbl + triple + hr;
  const tb = single + 2 * dbl + 3 * triple + 4 * hr;
  return {
    PA: pa,
    AB: ab,
    BB: bb,
    HBP: hbp,
    SF: sf,
    SH: sh,
    SO: so,
    H: h,
    "1B": single,
    "2B": dbl,
    "3B": triple,
    HR: hr,
    TB: tb,
    hits_runs_rbi: h + gauss(rng, 0.6, 0.5) + gauss(rng, 0.5, 0.5),
    k: so,
    h,
    tb,
  };
}

const MARKET_KEY: Record<string, string> = {
  pts: "pts",
  reb: "reb",
  ast: "ast",
  pra: "pra",
  pr: "pr",
  pa: "pa",
  ra: "ra",
  "3pm": "tpm",
  stl: "stl",
  blk: "blk",
  pass_yds: "pass_yds",
  rush_yds: "rush_yds",
  rec_yds: "rec_yds",
  receptions: "receptions",
  pass_rush_yds: "pass_rush_yds",
  rush_rec_yds: "rush_rec_yds",
  h: "H",
  tb: "TB",
  k: "SO",
  hits_runs_rbi: "hits_runs_rbi",
};

export function valueFromStats(market: string, stats: StatWorld): number {
  if (market === "pra") return stats.pts + stats.reb + stats.ast;
  const key = MARKET_KEY[market] ?? market;
  if (!(key in stats)) throw new Error(`UNSUPPORTED_MARKET:${market}`);
  return stats[key];
}

export const N_WORLDS = 64;

export function simulatePlayerWorlds(row: BoardRow, seed: string, n = N_WORLDS): StatWorld[] {
  const rng = mulberry32(seedFrom(`${seed}:${row.playerId}:${row.eventId}`));
  const worlds: StatWorld[] = [];
  for (let i = 0; i < n; i++) {
    if (row.sportFamily === "basketball") {
      worlds.push(sampleBasketball(rng, row.league === "NBA" ? 34 : 31));
    } else if (row.sportFamily === "gridiron") {
      worlds.push(sampleFootball(rng, row.role || "QB"));
    } else if (row.sportFamily === "baseball") {
      worlds.push(sampleBaseball(rng, 4.2));
    } else {
      throw new Error(`UNSUPPORTED_FAMILY:${row.sportFamily}`);
    }
  }
  return worlds;
}

export function fromWorlds(values: number[], line: number) {
  if (!values.length) return { pHigher: 0, pLower: 0, pPush: 1, mean: 0 };
  const n = values.length;
  let higher = 0;
  let lower = 0;
  let sum = 0;
  for (const v of values) {
    sum += v;
    if (v > line + 1e-9) higher += 1;
    else if (v < line - 1e-9) lower += 1;
  }
  const push = n - higher - lower;
  return { pHigher: higher / n, pLower: lower / n, pPush: push / n, mean: sum / n };
}
