"""Research source adapters. Model code calls these; it does not parse websites."""
from dcm.research.adapters.base import SourceAdapter, adapter_record, fetch_normalize, live_fetch_enabled
from dcm.research.adapters.basketball_reference import (
    BasketballReferenceGameLogAdapter,
    BasketballReferencePlayerAdapter,
)
from dcm.research.adapters.prizepicks import PrizePicksOfferAdapter
from dcm.research.adapters.pro_football_reference import (
    FootballReferenceGameLogAdapter,
    ProFootballReferenceAdapter,
)

__all__ = [
    "SourceAdapter",
    "adapter_record",
    "fetch_normalize",
    "live_fetch_enabled",
    "BasketballReferenceGameLogAdapter",
    "BasketballReferencePlayerAdapter",
    "PrizePicksOfferAdapter",
    "FootballReferenceGameLogAdapter",
    "ProFootballReferenceAdapter",
]
