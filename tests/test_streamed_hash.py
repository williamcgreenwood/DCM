from dataclasses import dataclass
from enum import Enum

from dcm.contracts.hashes import content_hash, content_hash_streamed


class State(Enum):
    OPEN = "OPEN"


@dataclass
class Fact:
    value: float
    content_hash: str = "excluded"
    created_at_utc: str = "excluded"


def test_streamed_hash_matches_canonical_contract_across_batches():
    graph = {
        "nodes": [
            {"id": i, "value": Fact(float(i)), "states": [State.OPEN, None, "Ω"]}
            for i in range(1_033)
        ],
        "mixedKeyCollision": {1: "one", "1": "string-key"},
        "nested": {"items": [float("nan"), float("inf"), -0.0]},
    }
    assert content_hash_streamed(graph) == content_hash(graph)
