const STAT: Record<string, string> = {
  points: "pts",
  pts: "pts",
  rebounds: "reb",
  reb: "reb",
  assists: "ast",
  ast: "ast",
  pra: "pra",
  "pts rebs asts": "pra",
  "pts reb ast": "pra",
  "points rebounds assists": "pra",
  "3 pt made": "3pm",
  "3pm": "3pm",
  threes: "3pm",
  "three pointers made": "3pm",
  steals: "stl",
  stl: "stl",
  "passing yards": "pass_yds",
  "pass yds": "pass_yds",
  "rushing yards": "rush_yds",
  "rush yds": "rush_yds",
  "receiving yards": "rec_yds",
  "rec yds": "rec_yds",
  receptions: "receptions",
  "passing rushing yards": "pass_rush_yds",
  "pass rush yds": "pass_rush_yds",
  "rush rec yds": "rush_rec_yds",
  "field goals made": "fg_made",
  "fg made": "fg_made",
  tackles: "def_tackles",
  "def tackles": "def_tackles",
  hits: "h",
  h: "h",
  "total bases": "tb",
  tb: "tb",
  "pitcher strikeouts": "k",
  strikeouts: "k",
  ks: "k",
  k: "k",
  "hits runs rbis": "hits_runs_rbi",
  "hits runs rbi": "hits_runs_rbi",
  "significant strikes": "sig_strikes",
  "sig strikes": "sig_strikes",
  shots: "shots",
  "shots on goal": "sog",
  sog: "sog",
  aces: "aces",
};

const LABEL: Record<string, string> = {
  pts: "Points",
  reb: "Rebounds",
  ast: "Assists",
  pra: "Pts+Reb+Ast",
  "3pm": "3-PT Made",
  stl: "Steals",
  pass_yds: "Passing Yards",
  rush_yds: "Rushing Yards",
  rec_yds: "Receiving Yards",
  receptions: "Receptions",
  pass_rush_yds: "Pass+Rush Yds",
  rush_rec_yds: "Rush+Rec Yds",
  fg_made: "FG Made",
  def_tackles: "Tackles",
  h: "Hits",
  tb: "Total Bases",
  k: "Strikeouts",
  hits_runs_rbi: "Hits+Runs+RBIs",
  sig_strikes: "Sig. Strikes",
  shots: "Shots",
  sog: "Shots on Goal",
  aces: "Aces",
};

const LEAGUE: Record<string, [string, string]> = {
  nba: ["NBA", "basketball"],
  wnba: ["WNBA", "basketball"],
  nfl: ["NFL", "gridiron"],
  nflp: ["NFLP", "gridiron"],
  "nfl preseason": ["NFLP", "gridiron"],
  ncaaf: ["CFB", "gridiron"],
  cfb: ["CFB", "gridiron"],
  "ncaa football": ["CFB", "gridiron"],
  "college football": ["CFB", "gridiron"],
  cfl: ["CFL", "gridiron"],
  mlb: ["MLB", "baseball"],
  kbo: ["KBO", "baseball"],
  nhl: ["NHL", "hockey"],
  ufc: ["UFC", "combat"],
  boxing: ["BOXING", "combat"],
  pga: ["PGA", "golf"],
  atp: ["ATP", "racket"],
  epl: ["EPL", "soccer"],
};

function norm(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

export function mapStat(label: string | undefined): [string, string] {
  if (!label) return ["unknown", "UNKNOWN"];
  const key = STAT[norm(label)];
  if (key) return [key, LABEL[key] ?? label];
  const slug = norm(label).replace(/ /g, "_") || "unknown";
  return [slug, label];
}

export function mapLeague(name: string | undefined, sport?: string): [string, string] {
  const raw = norm(name ?? "");
  if (raw && LEAGUE[raw]) return LEAGUE[raw];
  const sportFam = norm(sport ?? "") === "basketball" ? "basketball" : norm(sport ?? "") === "football" ? "gridiron" : "unknown";
  if (raw) return [raw.toUpperCase().slice(0, 12), sportFam];
  return ["UNKNOWN", "unknown"];
}

export function marketLabel(market: string, fallback = "") {
  return LABEL[market] ?? fallback ?? market;
}

export const FOOTBALL_MARKETS = new Set([
  "pass_yds",
  "rush_yds",
  "rec_yds",
  "receptions",
  "pass_rush_yds",
  "rush_rec_yds",
  "pass_att",
  "pass_cmp",
  "pass_td",
  "rush_att",
  "rush_td",
  "rec_td",
  "targets",
  "fg_made",
  "def_tackles",
]);
export const BASKETBALL_MARKETS = new Set(["pts", "reb", "ast", "pra", "3pm", "stl"]);
