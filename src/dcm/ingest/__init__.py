"""HAR → board.json ingest. Development adapter, not a hash-verified v5.4.1 decoder."""

from dcm.ingest.board import freeze_board
from dcm.ingest.har import ingest_har

__all__ = ["ingest_har", "freeze_board"]
