"""Basketball-Reference adapters (gamelog + season summary).

Accept pre-fetched HTML/text fixtures. Live HTTP is opt-in via live=True or
DCM_LIVE_FETCH=1. Normalized counting stats go through
dcm.research.gamelog.normalize_basketball_logs — never invent FGA from PTS.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from dcm.research.adapters.base import adapter_record, live_fetch_enabled
from dcm.research.adapters.html_tables import extract_tables, table_rows_as_dicts
from dcm.research.gamelog import normalize_basketball_log, normalize_basketball_logs


ADAPTER_VERSION = "br-html-1"
GAMELOG_ADAPTER_ID = "BasketballReferenceGameLogAdapter"
PLAYER_ADAPTER_ID = "BasketballReferencePlayerAdapter"
TEAM_ADAPTER_ID = "BasketballReferenceTeamAdapter"
TEAM_GAMELOG_ADAPTER_ID = "BasketballReferenceTeamGameLogAdapter"
SPLIT_ADAPTER_ID = "BasketballReferenceSplitAdapter"
LINEUP_ADAPTER_ID = "BasketballReferenceLineupAdapter"
ONOFF_ADAPTER_ID = "BasketballReferenceOnOffAdapter"
SOURCE_CLASS = "BOX_SCORE_VENDOR"

# B-R data-stat / header aliases already handled by gamelog normalizer
# (mp, trb, fg3a, ...). Keep a few document-level keys.
_SKIP_ROW_MARKERS = {"did not play", "did not dress", "not with team", "inactive", "player suspended"}


def _as_text(document: dict[str, Any]) -> str:
    for key in ("html", "text", "body", "content"):
        value = document.get(key)
        if isinstance(value, (str, bytes)):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    return ""


def _pick_table(tables: list[dict[str, Any]], *id_needles: str) -> dict[str, Any] | None:
    needles = tuple(n.lower() for n in id_needles)
    for table in tables:
        tid = str(table.get("id") or "").lower()
        tclass = str(table.get("class") or "").lower()
        if any(n in tid or n in tclass for n in needles):
            return table
    # Fall back to the widest stats-looking table.
    scored = []
    for table in tables:
        rows = table.get("rows") or []
        headers = table.get("headers") or []
        scored.append((len(rows), len(headers), table))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return scored[0][2] if scored else None


def _fetch_http(url: str, timeout: float = 20.0) -> str:
    req = Request(
        url,
        headers={"User-Agent": "pillars-dcm-research/6.0 (+https://github.com/williamcgreenwood/DCM)"},
    )
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — opt-in live fetch only
        return resp.read().decode("utf-8", errors="replace")


class BasketballReferenceGameLogAdapter:
    adapter_id = GAMELOG_ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    source_class = SOURCE_CLASS

    def __init__(self, *, live: bool | None = None, retrieved_at: str | None = None):
        self.live = live
        self.retrieved_at = retrieved_at

    def fetch(self, spec: dict[str, Any]) -> dict[str, Any]:
        html = spec.get("html") or spec.get("text") or spec.get("body")
        url = str(spec.get("url") or spec.get("source_url") or "")
        if html is not None:
            text = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else str(html)
            return {
                "url": url or "fixture://basketball-reference/gamelog",
                "html": text,
                "retrievedAt": spec.get("retrieved_at") or spec.get("retrievedAt") or self.retrieved_at,
                "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
                "fixture": True,
            }
        if not live_fetch_enabled(self.live):
            raise RuntimeError("BR_GAMELOG_LIVE_FETCH_DISABLED")
        if not url:
            raise ValueError("BR_GAMELOG_URL_REQUIRED")
        text = _fetch_http(url)
        return {
            "url": url,
            "html": text,
            "retrievedAt": self.retrieved_at,
            "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
            "fixture": False,
        }

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        url = str(document.get("url") or "")
        html = _as_text(document)
        retrieved = document.get("retrievedAt") or document.get("retrieved_at") or self.retrieved_at
        published = document.get("publishedAt") or document.get("published_at") or retrieved
        league = document.get("league") or (document.get("fields") or {}).get("league")
        tables = extract_tables(html)
        table = _pick_table(tables, "pgl_basic", "pgl_basic_playoffs", "player_game_log", "gamelog")
        raw_rows = table_rows_as_dicts(table) if table else []
        records: list[dict[str, Any]] = []
        for raw in raw_rows:
            joined = " ".join(str(v) for v in raw.values() if v is not None).strip().lower()
            if any(marker in joined for marker in _SKIP_ROW_MARKERS) and not any(
                k in raw for k in ("mp", "MP", "pts", "PTS")
            ):
                continue
            normalized = normalize_basketball_log(raw, league=str(league) if league else None)
            rec = adapter_record(
                url=url,
                raw=raw,
                fields=normalized or {},
                retrieved_at=retrieved,
                published_at=published,
                source_class=self.source_class,
                adapter_id=self.adapter_id,
                adapter_version=self.adapter_version,
                extra={
                    "kind": "GAME_LOG",
                    "normalized": normalized is not None,
                    "rejectReason": None if normalized is not None else "GAMELOG_MINUTES",
                    "league": league,
                    "tableId": (table or {}).get("id"),
                },
            )
            records.append(rec)
        return records

    def fetch_normalize(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Parse HTML/text into canonical logs via normalize_basketball_logs."""
        doc = spec if spec.get("html") or spec.get("text") or spec.get("body") else self.fetch(spec)
        if "html" not in doc and "text" not in doc:
            doc = self.fetch(spec)
        records = self.normalize(doc)
        valid_fields = [r["fields"] for r in records if r.get("normalized") and r.get("fields")]
        batch = normalize_basketball_logs(valid_fields, league=spec.get("league") or doc.get("league"))
        # Re-run batch on raw rows so rejected originals stay available.
        raw_rows = [r.get("raw") or {} for r in records]
        batch = normalize_basketball_logs(raw_rows, league=spec.get("league") or doc.get("league"))
        return {
            "records": records,
            "logs": batch["logs"],
            "rejected": batch["rejected"],
            "reasonCounts": batch["reasonCounts"],
            "url": doc.get("url"),
            "hostname": urlsplit(str(doc.get("url") or "")).hostname or "",
        }


class BasketballReferencePlayerAdapter:
    adapter_id = PLAYER_ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    source_class = SOURCE_CLASS

    def __init__(self, *, live: bool | None = None, retrieved_at: str | None = None):
        self.live = live
        self.retrieved_at = retrieved_at

    def fetch(self, spec: dict[str, Any]) -> dict[str, Any]:
        html = spec.get("html") or spec.get("text") or spec.get("body")
        url = str(spec.get("url") or spec.get("source_url") or "")
        if html is not None:
            text = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else str(html)
            return {
                "url": url or "fixture://basketball-reference/player",
                "html": text,
                "retrievedAt": spec.get("retrieved_at") or spec.get("retrievedAt") or self.retrieved_at,
                "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
                "fixture": True,
            }
        if not live_fetch_enabled(self.live):
            raise RuntimeError("BR_PLAYER_LIVE_FETCH_DISABLED")
        if not url:
            raise ValueError("BR_PLAYER_URL_REQUIRED")
        return {
            "url": url,
            "html": _fetch_http(url),
            "retrievedAt": self.retrieved_at,
            "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
            "fixture": False,
        }

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        url = str(document.get("url") or "")
        html = _as_text(document)
        retrieved = document.get("retrievedAt") or document.get("retrieved_at") or self.retrieved_at
        published = document.get("publishedAt") or document.get("published_at") or retrieved
        tables = extract_tables(html)
        table = _pick_table(tables, "per_game", "totals", "per_game_stats", "stats")
        rows = table_rows_as_dicts(table) if table else []
        # Prefer a current-season row when present; otherwise last numeric season row.
        chosen = None
        want_season = str(document.get("season") or "").strip()
        for row in rows:
            season = str(row.get("season") or row.get("year_id") or "")
            if want_season and want_season in season:
                chosen = row
                break
        if chosen is None:
            for row in reversed(rows):
                if any(k in row for k in ("pts_per_g", "pts", "mp_per_g", "trb_per_g", "ast_per_g", "g")):
                    chosen = row
                    break
        if chosen is None and rows:
            chosen = rows[-1]
        if chosen is None:
            return []
        fields = {
            "season": chosen.get("season") or chosen.get("year_id"),
            "games": chosen.get("g") or chosen.get("games"),
            "gamesStarted": chosen.get("gs"),
            "minutesPerGame": chosen.get("mp_per_g") or chosen.get("mp"),
            "ptsPerGame": chosen.get("pts_per_g") or chosen.get("pts"),
            "rebPerGame": chosen.get("trb_per_g") or chosen.get("trb") or chosen.get("reb"),
            "astPerGame": chosen.get("ast_per_g") or chosen.get("ast"),
            "fgPct": chosen.get("fg_pct"),
            "fg3Pct": chosen.get("fg3_pct"),
            "ftPct": chosen.get("ft_pct"),
            "fgaPerGame": chosen.get("fga_per_g") or chosen.get("fga"),
            "tpaPerGame": chosen.get("fg3a_per_g") or chosen.get("fg3a"),
            "ftaPerGame": chosen.get("fta_per_g") or chosen.get("fta"),
        }
        rec = adapter_record(
            url=url,
            raw=chosen,
            fields={k: v for k, v in fields.items() if v is not None},
            retrieved_at=retrieved,
            published_at=published,
            source_class=self.source_class,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            extra={"kind": "SEASON_SUMMARY", "tableId": (table or {}).get("id")},
        )
        return [rec]


def _fixture_or_live(self, spec: dict[str, Any], *, default_url: str, disabled_code: str, url_code: str) -> dict[str, Any]:
    html = spec.get("html") or spec.get("text") or spec.get("body")
    url = str(spec.get("url") or spec.get("source_url") or "")
    if html is not None:
        text = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else str(html)
        return {
            "url": url or default_url,
            "html": text,
            "retrievedAt": spec.get("retrieved_at") or spec.get("retrievedAt") or self.retrieved_at,
            "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
            "fixture": True,
            "league": spec.get("league"),
        }
    if not live_fetch_enabled(self.live):
        raise RuntimeError(disabled_code)
    if not url:
        raise ValueError(url_code)
    return {
        "url": url,
        "html": _fetch_http(url),
        "retrievedAt": self.retrieved_at,
        "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
        "fixture": False,
        "league": spec.get("league"),
    }


class BasketballReferenceTeamAdapter:
    adapter_id = TEAM_ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    source_class = SOURCE_CLASS

    def __init__(self, *, live: bool | None = None, retrieved_at: str | None = None):
        self.live = live
        self.retrieved_at = retrieved_at

    def fetch(self, spec: dict[str, Any]) -> dict[str, Any]:
        return _fixture_or_live(
            self, spec,
            default_url="fixture://basketball-reference/team",
            disabled_code="BR_TEAM_LIVE_FETCH_DISABLED",
            url_code="BR_TEAM_URL_REQUIRED",
        )

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        url = str(document.get("url") or "")
        html = _as_text(document)
        retrieved = document.get("retrievedAt") or document.get("retrieved_at") or self.retrieved_at
        published = document.get("publishedAt") or document.get("published_at") or retrieved
        tables = extract_tables(html)
        table = _pick_table(tables, "team_and_opponent", "team-stats-per_game", "team_misc", "misc_stats", "team_ratings")
        rows = table_rows_as_dicts(table) if table else []
        chosen = None
        for row in rows:
            label = str(row.get("stat") or row.get("") or row.get("player") or "").lower()
            if "team" in label or "pace" in row or "off_rtg" in row or "ortg" in row or "pts" in row:
                chosen = row
                if "team" in label:
                    break
        if chosen is None and rows:
            chosen = rows[0]
        if chosen is None:
            return []
        fields = {
            "pace": chosen.get("pace") or chosen.get("Pace"),
            "ortg": chosen.get("off_rtg") or chosen.get("ortg") or chosen.get("ORtg"),
            "drtg": chosen.get("def_rtg") or chosen.get("drtg") or chosen.get("DRtg"),
            "net_rtg": chosen.get("net_rtg") or chosen.get("nrtg"),
            "pts": chosen.get("pts") or chosen.get("pts_per_g"),
            "opp_pts": chosen.get("opp_pts") or chosen.get("opp_pts_per_g"),
            "possessions": chosen.get("poss") or chosen.get("pace"),
            "fg_pct": chosen.get("fg_pct"),
            "fg3_pct": chosen.get("fg3_pct"),
            "ft_pct": chosen.get("ft_pct"),
        }
        rec = adapter_record(
            url=url,
            raw=chosen,
            fields={k: v for k, v in fields.items() if v is not None},
            retrieved_at=retrieved,
            published_at=published,
            source_class=self.source_class,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            extra={"kind": "TEAM_CONTEXT", "tableId": (table or {}).get("id")},
        )
        return [rec]


class BasketballReferenceTeamGameLogAdapter:
    adapter_id = TEAM_GAMELOG_ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    source_class = SOURCE_CLASS

    def __init__(self, *, live: bool | None = None, retrieved_at: str | None = None):
        self.live = live
        self.retrieved_at = retrieved_at

    def fetch(self, spec: dict[str, Any]) -> dict[str, Any]:
        return _fixture_or_live(
            self, spec,
            default_url="fixture://basketball-reference/team-gamelog",
            disabled_code="BR_TEAM_GAMELOG_LIVE_FETCH_DISABLED",
            url_code="BR_TEAM_GAMELOG_URL_REQUIRED",
        )

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        url = str(document.get("url") or "")
        html = _as_text(document)
        retrieved = document.get("retrievedAt") or document.get("retrieved_at") or self.retrieved_at
        published = document.get("publishedAt") or document.get("published_at") or retrieved
        tables = extract_tables(html)
        table = _pick_table(tables, "tgl_basic", "team_game_log", "gamelog")
        raw_rows = table_rows_as_dicts(table) if table else []
        records: list[dict[str, Any]] = []
        for raw in raw_rows:
            fields = {
                "date": raw.get("date_game") or raw.get("date"),
                "opp": raw.get("opp_id") or raw.get("opp"),
                "home": str(raw.get("game_location") or raw.get("location") or "").lower() not in {"@", "away"},
                "pts": raw.get("pts") or raw.get("Tm"),
                "opp_pts": raw.get("opp_pts") or raw.get("Opp"),
                "fga": raw.get("fga"),
                "fta": raw.get("fta"),
                "tov": raw.get("tov"),
                "oreb": raw.get("orb") or raw.get("oreb"),
                "fg": raw.get("fg"),
                "fg3": raw.get("fg3"),
                "fg3a": raw.get("fg3a"),
            }
            records.append(
                adapter_record(
                    url=url,
                    raw=raw,
                    fields={k: v for k, v in fields.items() if v is not None},
                    retrieved_at=retrieved,
                    published_at=published,
                    source_class=self.source_class,
                    adapter_id=self.adapter_id,
                    adapter_version=self.adapter_version,
                    extra={"kind": "TEAM_GAME_LOG", "tableId": (table or {}).get("id")},
                )
            )
        return records


class BasketballReferenceSplitAdapter:
    adapter_id = SPLIT_ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    source_class = SOURCE_CLASS

    def __init__(self, *, live: bool | None = None, retrieved_at: str | None = None):
        self.live = live
        self.retrieved_at = retrieved_at

    def fetch(self, spec: dict[str, Any]) -> dict[str, Any]:
        return _fixture_or_live(
            self, spec,
            default_url="fixture://basketball-reference/splits",
            disabled_code="BR_SPLIT_LIVE_FETCH_DISABLED",
            url_code="BR_SPLIT_URL_REQUIRED",
        )

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        url = str(document.get("url") or "")
        html = _as_text(document)
        retrieved = document.get("retrievedAt") or document.get("retrieved_at") or self.retrieved_at
        published = document.get("publishedAt") or document.get("published_at") or retrieved
        tables = extract_tables(html)
        table = _pick_table(tables, "splits", "player-splits", "team-splits")
        raw_rows = table_rows_as_dicts(table) if table else []
        records: list[dict[str, Any]] = []
        for raw in raw_rows:
            label = str(raw.get("value") or raw.get("split") or raw.get("desc") or raw.get("") or "")
            fields = {
                "split": label,
                "g": raw.get("g") or raw.get("games"),
                "mp": raw.get("mp") or raw.get("mp_per_g"),
                "pts": raw.get("pts") or raw.get("pts_per_g"),
                "reb": raw.get("trb") or raw.get("reb"),
                "ast": raw.get("ast"),
                "fga": raw.get("fga"),
            }
            records.append(
                adapter_record(
                    url=url,
                    raw=raw,
                    fields={k: v for k, v in fields.items() if v is not None and v != ""},
                    retrieved_at=retrieved,
                    published_at=published,
                    source_class=self.source_class,
                    adapter_id=self.adapter_id,
                    adapter_version=self.adapter_version,
                    extra={"kind": "SPLIT", "tableId": (table or {}).get("id")},
                )
            )
        return records


class BasketballReferenceLineupAdapter:
    adapter_id = LINEUP_ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    source_class = SOURCE_CLASS

    def __init__(self, *, live: bool | None = None, retrieved_at: str | None = None):
        self.live = live
        self.retrieved_at = retrieved_at

    def fetch(self, spec: dict[str, Any]) -> dict[str, Any]:
        return _fixture_or_live(
            self, spec,
            default_url="fixture://basketball-reference/lineup",
            disabled_code="BR_LINEUP_LIVE_FETCH_DISABLED",
            url_code="BR_LINEUP_URL_REQUIRED",
        )

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        url = str(document.get("url") or "")
        html = _as_text(document)
        retrieved = document.get("retrievedAt") or document.get("retrieved_at") or self.retrieved_at
        published = document.get("publishedAt") or document.get("published_at") or retrieved
        tables = extract_tables(html)
        table = _pick_table(tables, "lineup", "lineups", "5man")
        raw_rows = table_rows_as_dicts(table) if table else []
        records: list[dict[str, Any]] = []
        for raw in raw_rows:
            fields = {
                "lineup": raw.get("lineup") or raw.get("players") or raw.get("lineup_id"),
                "minutes": raw.get("mp") or raw.get("minutes"),
                "pts": raw.get("pts"),
                "opp_pts": raw.get("opp_pts"),
                "plus": raw.get("plus_minus") or raw.get("diff"),
            }
            records.append(
                adapter_record(
                    url=url,
                    raw=raw,
                    fields={k: v for k, v in fields.items() if v is not None},
                    retrieved_at=retrieved,
                    published_at=published,
                    source_class=self.source_class,
                    adapter_id=self.adapter_id,
                    adapter_version=self.adapter_version,
                    extra={"kind": "LINEUP", "tableId": (table or {}).get("id")},
                )
            )
        return records


class BasketballReferenceOnOffAdapter:
    adapter_id = ONOFF_ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    source_class = SOURCE_CLASS

    def __init__(self, *, live: bool | None = None, retrieved_at: str | None = None):
        self.live = live
        self.retrieved_at = retrieved_at

    def fetch(self, spec: dict[str, Any]) -> dict[str, Any]:
        return _fixture_or_live(
            self, spec,
            default_url="fixture://basketball-reference/on-off",
            disabled_code="BR_ONOFF_LIVE_FETCH_DISABLED",
            url_code="BR_ONOFF_URL_REQUIRED",
        )

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        url = str(document.get("url") or "")
        html = _as_text(document)
        retrieved = document.get("retrievedAt") or document.get("retrieved_at") or self.retrieved_at
        published = document.get("publishedAt") or document.get("published_at") or retrieved
        tables = extract_tables(html)
        table = _pick_table(tables, "on_off", "on-off", "onoff")
        raw_rows = table_rows_as_dicts(table) if table else []
        records: list[dict[str, Any]] = []
        for raw in raw_rows:
            fields = {
                "player": raw.get("player") or raw.get("player_name"),
                "on_minutes": raw.get("on_mp") or raw.get("mp_on") or raw.get("minutes"),
                "on_ortg": raw.get("on_ortg") or raw.get("off_rtg_on"),
                "off_ortg": raw.get("off_ortg") or raw.get("off_rtg_off"),
                "on_drtg": raw.get("on_drtg"),
                "off_drtg": raw.get("off_drtg"),
                "rawEffect": raw.get("net") or raw.get("diff"),
            }
            records.append(
                adapter_record(
                    url=url,
                    raw=raw,
                    fields={k: v for k, v in fields.items() if v is not None},
                    retrieved_at=retrieved,
                    published_at=published,
                    source_class=self.source_class,
                    adapter_id=self.adapter_id,
                    adapter_version=self.adapter_version,
                    extra={"kind": "ON_OFF", "tableId": (table or {}).get("id")},
                )
            )
        return records
