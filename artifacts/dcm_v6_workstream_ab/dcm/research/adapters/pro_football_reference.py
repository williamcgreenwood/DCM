"""Pro-Football-Reference / Sports-Reference CFB adapters (gamelog).

Accept pre-fetched HTML/text fixtures. Live HTTP is opt-in via live=True or
DCM_LIVE_FETCH=1. Normalized counting stats go through
dcm.research.gridiron_gamelog.normalize_gridiron_logs — never invent routes
from targets or yards from attempts.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from dcm.research.adapters.base import adapter_record, live_fetch_enabled
from dcm.research.adapters.html_tables import extract_tables, table_rows_as_dicts
from dcm.research.gridiron_gamelog import normalize_gridiron_log, normalize_gridiron_logs


ADAPTER_VERSION = "pfr-html-1"
GAMELOG_ADAPTER_ID = "FootballReferenceGameLogAdapter"
PFR_ADAPTER_ID = "ProFootballReferenceAdapter"
SOURCE_CLASS = "BOX_SCORE_VENDOR"

_SKIP_ROW_MARKERS = {
    "did not play", "did not dress", "inactive", "injured reserve",
    "player suspended", "dnp", "bye week",
}


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
    scored = []
    for table in tables:
        rows = table.get("rows") or []
        headers = table.get("headers") or []
        header_stats = " ".join(str(h.get("stat") or h.get("text") or "") for h in headers).lower()
        footballish = any(tok in header_stats for tok in ("pass", "rush", "rec", "tgt", "snap"))
        scored.append((1 if footballish else 0, len(rows), len(headers), table))
    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return scored[0][3] if scored else None


def _fetch_http(url: str, timeout: float = 20.0) -> str:
    req = Request(
        url,
        headers={"User-Agent": "pillars-dcm-research/6.0 (+https://github.com/williamcgreenwood/DCM)"},
    )
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — opt-in live fetch only
        return resp.read().decode("utf-8", errors="replace")


class FootballReferenceGameLogAdapter:
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
            league = spec.get("league") or "NFL"
            host = "pro-football-reference.com" if str(league).upper() != "CFB" else "sports-reference.com"
            return {
                "url": url or f"fixture://{host}/gamelog",
                "html": text,
                "retrievedAt": spec.get("retrieved_at") or spec.get("retrievedAt") or self.retrieved_at,
                "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
                "league": league,
                "fixture": True,
            }
        if not live_fetch_enabled(self.live):
            raise RuntimeError("PFR_GAMELOG_LIVE_FETCH_DISABLED")
        if not url:
            raise ValueError("PFR_GAMELOG_URL_REQUIRED")
        text = _fetch_http(url)
        return {
            "url": url,
            "html": text,
            "retrievedAt": self.retrieved_at,
            "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
            "league": spec.get("league"),
            "fixture": False,
        }

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        url = str(document.get("url") or "")
        html = _as_text(document)
        retrieved = document.get("retrievedAt") or document.get("retrieved_at") or self.retrieved_at
        published = document.get("publishedAt") or document.get("published_at") or retrieved
        league = document.get("league") or (document.get("fields") or {}).get("league")
        tables = extract_tables(html)
        table = _pick_table(
            tables,
            "stats", "gamelog", "passing", "rushing_and_receiving",
            "receiving_and_rushing", "pgl_basic", "player_game_log",
        )
        raw_rows = table_rows_as_dicts(table) if table else []
        records: list[dict[str, Any]] = []
        for raw in raw_rows:
            joined = " ".join(str(v) for v in raw.values() if v is not None).strip().lower()
            has_stat = any(
                k in raw for k in (
                    "pass_att", "pass_yds", "rush_att", "rush_yds", "targets",
                    "rec", "receptions", "rec_yds", "off_pct", "snaps",
                )
            )
            if any(marker in joined for marker in _SKIP_ROW_MARKERS) and not has_stat:
                continue
            normalized = normalize_gridiron_log(raw, league=str(league) if league else None)
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
                    "rejectReason": None if normalized is not None else "GAMELOG_OPPORTUNITY",
                    "league": league,
                    "tableId": (table or {}).get("id"),
                },
            )
            records.append(rec)
        return records

    def fetch_normalize(self, spec: dict[str, Any]) -> dict[str, Any]:
        doc = spec if spec.get("html") or spec.get("text") or spec.get("body") else self.fetch(spec)
        if "html" not in doc and "text" not in doc:
            doc = self.fetch(spec)
        records = self.normalize(doc)
        raw_rows = [r.get("raw") or {} for r in records]
        batch = normalize_gridiron_logs(raw_rows, league=spec.get("league") or doc.get("league"))
        return {
            "records": records,
            "logs": batch["logs"],
            "rejected": batch["rejected"],
            "reasonCounts": batch["reasonCounts"],
            "url": doc.get("url"),
            "hostname": urlsplit(str(doc.get("url") or "")).hostname or "",
        }


class ProFootballReferenceAdapter(FootballReferenceGameLogAdapter):
    """Alias used by NFL hosts. Same parser as FootballReferenceGameLogAdapter."""

    adapter_id = PFR_ADAPTER_ID
