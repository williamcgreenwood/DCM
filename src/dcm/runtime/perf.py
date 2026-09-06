"""Stage instrumentation. Collects metrics. Does NOT write PeakRSS PASS / SLO PASS."""

from __future__ import annotations

import resource
import time
from typing import Any


class StageTimer:
    def __init__(self, stage: str):
        self.stage = stage
        self.t0 = time.perf_counter()
        self.cpu0 = time.process_time()

    def finish(self, **extra: Any) -> dict[str, Any]:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rec = {
            "Stage": self.stage,
            "WallSeconds": time.perf_counter() - self.t0,
            "CPUSeconds": time.process_time() - self.cpu0,
            "PeakRSSBytesObserved": int(rss) * 1024,
            "QualityGateState": "INSTRUMENTED_NOT_CERTIFIED",
            "hostPerformanceCertified": False,
            **extra,
        }
        return rec
