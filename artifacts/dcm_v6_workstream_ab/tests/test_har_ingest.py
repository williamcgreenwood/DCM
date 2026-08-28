"""HAR → board.json accounting. Additive; does not retire WSAB_BASELINE_46."""

from __future__ import annotations

import json
from pathlib import Path

from dcm.ingest.board import freeze_board
from dcm.ingest.har import ingest_har, sha256_text
from dcm.ingest.prizepicks import parse_prizepicks_payload
from dcm.runtime.har_run import run_har
from dcm.runtime.mount_v541 import EXPECTED_SOURCE, attempt_mount

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "synthetic_har.json"


def test_sha256_abc():
    assert sha256_text("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_synthetic_har_accounts_every_row_and_goblins():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ing = ingest_har(raw, raw_bytes=FIXTURE.read_bytes())
    assert ing["adapter"] == "SYNTHETIC"
    assert ing["v5Decoder"] == "NOT_MOUNTED"
    ids = {r["projectionId"] for r in ing["rows"]}
    assert ids == {"n1", "n6", "f1", "c1", "m3", "s1"}
    goblins = [r for r in ing["rows"] if r["modifier"] == "GOBLIN"]
    assert len(goblins) == 1
    assert goblins[0]["projectionId"] == "n6"


def test_denied_account_endpoint_is_not_replayed():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ing = ingest_har(raw)
    assert ing["indexStats"]["denied_endpoints"] >= 1
    for row in ing["rows"]:
        assert "account" not in json.dumps(row).lower()


def test_board_json_accounting_and_wsab_bind():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ing = ingest_har(raw, raw_bytes=FIXTURE.read_bytes())
    board = freeze_board(ing, mount={"state": "ABSENT_IN_THIS_WORKSPACE", "har_decoder": "NOT_MOUNTED"})
    acc = board["accounting"]
    assert acc["raw_projection_rows"] == 6
    assert acc["goblin_rows"] == 1
    assert acc["standard_rows"] == 5
    assert acc["unique_offer_rows"] == 6
    assert board["learningRevision"] == "LR000000"
    assert board["predictiveClaim"] == "NONE"
    football = [r for r in board["rows"] if r["league"] in {"NFL", "CFB"}]
    assert football
    assert all(r["wsabMarketBound"] for r in football)
    sayin = next(r for r in board["rows"] if r["playerName"] == "Julian Sayin")
    assert sayin["cfbOfficialNameListed"] is True
    assert sayin["cfbOfficialPlayerId"] is None
    assert sayin["playerId"] == "SAYIN_SRC"


def test_prizepicks_jsonapi_payload():
    payload = {
        "data": [
            {
                "id": "9001",
                "type": "projection",
                "attributes": {
                    "line_score": 24.5,
                    "stat_type": "Points",
                    "description": "Jayson Tatum",
                    "odds_type": "standard",
                },
                "relationships": {
                    "new_player": {"data": {"id": "p1", "type": "new_player"}},
                    "league": {"data": {"id": "7", "type": "league"}},
                    "new_game": {"data": {"id": "g1", "type": "new_game"}},
                },
            },
            {
                "id": "9002",
                "type": "projection",
                "attributes": {
                    "line_score": 12.5,
                    "stat_type": "Points",
                    "odds_type": "goblin",
                },
                "relationships": {
                    "new_player": {"data": {"id": "p2", "type": "new_player"}},
                    "league": {"data": {"id": "7", "type": "league"}},
                    "new_game": {"data": {"id": "g1", "type": "new_game"}},
                },
            },
        ],
        "included": [
            {"id": "p1", "type": "new_player", "attributes": {"display_name": "Jayson Tatum", "team": "BOS", "position": "F"}},
            {"id": "p2", "type": "new_player", "attributes": {"display_name": "Jrue Holiday", "team": "BOS", "position": "G"}},
            {"id": "7", "type": "league", "attributes": {"name": "NBA", "sport": "Basketball"}},
            {"id": "g1", "type": "new_game", "attributes": {"home_name": "NYK", "away_name": "BOS"}},
        ],
    }
    parsed = parse_prizepicks_payload(payload)
    assert parsed is not None
    name, rows = parsed
    assert name == "PRIZEPICKS_JSONAPI"
    assert len(rows) == 2
    assert rows[0]["market"] == "pts"
    assert rows[0]["league"] == "NBA"
    assert rows[1]["modifier"] == "GOBLIN"
    assert rows[0]["side"] == "UNKNOWN"
    assert rows[0]["offeredHigher"] is True


def test_unknown_shape_fail_closed():
    ing = ingest_har({"foo": [1, 2, 3]})
    assert ing["adapter"] == "UNKNOWN"
    assert ing["rows"] == []
    assert "UNKNOWN_HAR_SHAPE" in ing["warnings"]


def test_mount_refuses_wrong_hash(tmp_path: Path):
    src = tmp_path / "Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.txt"
    src.write_text("not-the-canonical-bytes\n", encoding="utf-8")
    dest = tmp_path / "copy"
    state = attempt_mount(dest=dest, source=src, ledger=None, expected_source=EXPECTED_SOURCE)
    assert state["state"] == "HASH_MISMATCH"
    assert state["copied"] is False
    assert list(dest.glob("*")) == []


def test_mount_copies_only_on_match(tmp_path: Path):
    src = tmp_path / "toy.txt"
    src.write_bytes(b"toy-source")
    digest = __import__("hashlib").sha256(b"toy-source").hexdigest()
    dest = tmp_path / "copy"
    state = attempt_mount(dest=dest, source=src, ledger=None, expected_source=digest, expected_ledger="x")
    assert state["state"] == "HASH_VERIFIED"
    assert (dest / "toy.txt").read_bytes() == b"toy-source"


def test_har_run_synthetic_does_not_promote_lr(tmp_path: Path):
    result = run_har(
        inbox=None,
        out_root=tmp_path / "RUNS",
        synthetic=True,
        cutoff="2026-08-28T00:00:00Z",
        workspace=Path("/workspace"),
    )
    integ = result["integrity"]
    assert integ["learningRevision"] == "LR000000"
    assert integ["predictiveClaim"] == "NONE"
    assert integ["optimizedDcm60Claim"] is False
    assert integ["v5MountState"] in {"ABSENT_IN_THIS_WORKSPACE", "HASH_MISMATCH"}
    assert (Path(result["dest"]) / "board.json").is_file()
    assert integ["rawRows"] >= 6
