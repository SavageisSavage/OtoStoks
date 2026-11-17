"""
engine/latency.py - Rolling latency telemetry for the decision pipeline.

The bot's control loop has several distinct stages between "the game published a
price" and "an order file exists on disk". Without numbers you cannot tell which
one is eating the budget, so every stage records into a shared meter here and the
percentiles are exposed to the dashboard through AppState.get_snapshot().

Stages instrumented by the engine:
    snapshot_wait   - idle wait until the game rewrites mods/export/market.json
    snapshot_parse  - stat + json.load + normalisation of that file
    features        - 16-factor vector construction
    inference       - ONNX batch evaluation
    decision        - evaluate_portfolio() order generation
    dispatch        - writing the command file and confirming consumption
    cycle           - whole loop iteration, end to end

All values are milliseconds.
"""
import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Dict, Iterator, Optional


class LatencyMeter:
    """Thread-safe rolling percentile meter for named pipeline stages."""

    def __init__(self, window: int = 240):
        self._lock = threading.Lock()
        self._window = window
        self._samples: Dict[str, deque] = {}

    def record(self, stage: str, ms: float) -> None:
        with self._lock:
            dq = self._samples.get(stage)
            if dq is None:
                dq = deque(maxlen=self._window)
                self._samples[stage] = dq
            dq.append(float(ms))

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        with self._lock:
            out: Dict[str, Dict[str, float]] = {}
            for stage, dq in self._samples.items():
                if not dq:
                    continue
                vals = sorted(dq)
                n = len(vals)
                out[stage] = {
                    "n": n,
                    "last": round(dq[-1], 3),
                    "avg": round(sum(vals) / n, 3),
                    "p50": round(vals[n // 2], 3),
                    "p95": round(vals[min(n - 1, int(n * 0.95))], 3),
                    "max": round(vals[-1], 3),
                }
            return out


# Process-wide meter shared by the loop, the bridge and the feature pipeline.
PIPELINE = LatencyMeter()


@contextmanager
def timed(stage: str, meter: Optional[LatencyMeter] = None) -> Iterator[None]:
    """Record wall-clock duration of a block, in milliseconds, into the meter."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        (meter or PIPELINE).record(stage, (time.perf_counter() - t0) * 1000.0)
