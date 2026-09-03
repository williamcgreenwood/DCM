"""Research source adapters. Model code calls these; it does not parse websites."""
from dcm.research.adapters.base import SourceAdapter, adapter_record, fetch_normalize, live_fetch_enabled
from dcm.research.adapters.basketball_reference import (
    BasketballReferenceGameLogAdapter,
    BasketballReferenceLineupAdapter,
    BasketballReferenceOnOffAdapter,
    BasketballReferencePlayerAdapter,
    BasketballReferenceSplitAdapter,
    BasketballReferenceTeamAdapter,
    BasketballReferenceTeamGameLogAdapter,
)
from dcm.research.adapters.espn_status import ESPNStatusAdapter
from dcm.research.adapters.official_league import OfficialNBAAdapter, OfficialWNBAAdapter
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
    "BasketballReferenceTeamAdapter",
    "BasketballReferenceTeamGameLogAdapter",
    "BasketballReferenceSplitAdapter",
    "BasketballReferenceLineupAdapter",
    "BasketballReferenceOnOffAdapter",
    "ESPNStatusAdapter",
    "OfficialWNBAAdapter",
    "OfficialNBAAdapter",
    "PrizePicksOfferAdapter",
    "FootballReferenceGameLogAdapter",
    "ProFootballReferenceAdapter",
]
