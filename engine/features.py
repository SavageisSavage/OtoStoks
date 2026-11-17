import time
import collections
from typing import Dict, Optional
import numpy as np

MIN_FEATURE_TICKS = 30


def compute_features(prices: np.ndarray) -> np.ndarray:
    """
    Institutional 16-Factor Quantitative Feature Pipeline.
    Extracts multi-timeframe trend, momentum, volatility, oscillation, 
    Kaufman efficiency ratio, and macro regime score in vectorized NumPy.

    Guarantees strict identical mathematical calculation for both training and live inference.
    """
    p = np.asarray(prices, dtype=np.float32)
    n = len(p)
    if n < MIN_FEATURE_TICKS:
        return np.zeros(16, dtype=np.float32)

    curr_p = float(p[-1])

    # 1. EMA Spread (9 vs 21)
    k9 = 2.0 / 10.0
    k21 = 2.0 / 22.0
    ema9 = p[0]
    ema21 = p[0]
    for i in range(1, n):
        ema9 = p[i] * k9 + ema9 * (1.0 - k9)
        ema21 = p[i] * k21 + ema21 * (1.0 - k21)
    ema_spread = float((ema9 - ema21) / (ema21 + 1e-8))

    # 2. RSI 14 (Wilder's Smoothing)
    alpha14 = 1.0 / 14.0
    diff = np.diff(p)
    gains = np.maximum(0.0, diff)
    losses = np.maximum(0.0, -diff)
    avg_g = gains[0] if len(gains) > 0 else 0.0
    avg_l = losses[0] if len(losses) > 0 else 0.0
    for i in range(1, len(diff)):
        avg_g = gains[i] * alpha14 + avg_g * (1.0 - alpha14)
        avg_l = losses[i] * alpha14 + avg_l * (1.0 - alpha14)
    rs = avg_g / (avg_l + 1e-8)
    rsi14 = float(100.0 - (100.0 / (1.0 + rs)))

    # 3, 4, 5. Bollinger Bands (20) & Volatility
    win20 = min(n, 20)
    sub20 = p[-win20:]
    sma20 = float(np.mean(sub20))
    std20 = float(np.std(sub20))
    upper20 = sma20 + 2.0 * std20
    lower20 = sma20 - 2.0 * std20
    bb_pct = float((curr_p - lower20) / (upper20 - lower20 + 1e-8))
    bb_width = float((upper20 - lower20) / (sma20 + 1e-8))
    vol20 = float(std20 / (sma20 + 1e-8))

    # 6, 7, 8, 9. Multi-Horizon Returns & Acceleration
    prev_1 = float(p[-2]) if n >= 2 else curr_p
    prev_3 = float(p[-4]) if n >= 4 else prev_1
    prev_8 = float(p[-9]) if n >= 9 else prev_3

    ret1 = float((curr_p - prev_1) / (prev_1 + 1e-8))
    ret3 = float((curr_p - prev_3) / (prev_3 + 1e-8))
    ret8 = float((curr_p - prev_8) / (prev_8 + 1e-8))
    acceleration = float(ret3 - ret8)

    # 10. Z-Score 30
    win30 = min(n, 30)
    sub30 = p[-win30:]
    zscore30 = float((curr_p - float(np.mean(sub30))) / (float(np.std(sub30)) + 1e-8))

    # 11. MACD Normalized Histogram (12, 26, 9)
    k12 = 2.0 / 13.0
    k26 = 2.0 / 27.0
    ema12 = p[0]
    ema26 = p[0]
    for i in range(1, n):
        ema12 = p[i] * k12 + ema12 * (1.0 - k12)
        ema26 = p[i] * k26 + ema26 * (1.0 - k26)
    macd_line = (ema12 - ema26) / (curr_p + 1e-8)
    macd_hist = float(macd_line - (ema_spread * 0.5))

    # 12. Kaufman Efficiency Ratio (Noise vs Signal: 10-period)
    win10 = min(n, 10)
    sub10 = p[-win10:]
    net_change = abs(curr_p - float(sub10[0]))
    total_path = float(np.sum(np.abs(np.diff(sub10)))) + 1e-8
    kama_eff = float(net_change / total_path)

    # 13. Normalized ATR Ratio (Average True Range Proxy: 14-period)
    win14 = min(n, 14)
    sub14 = p[-win14:]
    high_low_spreads = np.abs(np.diff(sub14))
    atr_proxy = float(np.mean(high_low_spreads)) if len(high_low_spreads) > 0 else 0.01
    atr_ratio = float(atr_proxy / (curr_p + 1e-8))

    # 14. Fast Stochastic Oscillator %K (14-period)
    min14 = float(np.min(sub14))
    max14 = float(np.max(sub14))
    stoch_k = float(((curr_p - min14) / (max14 - min14 + 1e-8)) * 100.0)

    # 15. Donchian Channel Position (20-period)
    min20 = float(np.min(sub20))
    max20 = float(np.max(sub20))
    donchian_pct = float((curr_p - min20) / (max20 - min20 + 1e-8))

    # 16. Macro Regime Index (-1.0 Bear Exhaustion, 0.0 Range, +1.0 Bull Markup)
    trend_dir = 1.0 if ema_spread > 0 else -1.0
    regime_score = float(np.clip(
        (trend_dir * kama_eff * 0.4) + (ret8 * 30.0 * 0.3) + ((bb_pct - 0.5) * 0.3),
        -1.0, 1.0
    ))

    return np.array([
        ema_spread, rsi14, bb_pct, bb_width, vol20,
        ret1, ret3, ret8, acceleration, zscore30,
        macd_hist, kama_eff, atr_ratio, stoch_k, donchian_pct, regime_score
    ], dtype=np.float32)


class FastFeatureTracker:
    """
    Rolling time-series cache for tick prices.
    Enforces a strict minimum of 30 historical ticks so all technical indicators
    (Bollinger 20, Z-score 30, ATR 14, RSI 14) have complete empirical sample depth.
    """
    def __init__(self, max_history: int = 120):
        self.prices: Dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque(maxlen=max_history))
        self.timestamps: Dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque(maxlen=max_history))

    def update(self, ticker: str, price: float, ts_ms: Optional[int] = None) -> Optional[np.ndarray]:
        dq = self.prices[ticker]
        tq = self.timestamps[ticker]
        curr_ts = ts_ms or int(time.time() * 1000)

        # Skip immediate duplicate ticks within 80ms at identical price
        if dq and len(dq) > 0 and dq[-1] == price and tq and (curr_ts - tq[-1]) < 80:
            pass
        else:
            dq.append(price)
            tq.append(curr_ts)

        # Require >= 30 ticks to eliminate discrepancies with training math
        if len(dq) < MIN_FEATURE_TICKS:
            return None

        return compute_features(np.array(dq, dtype=np.float32))

    def get_prices(self, ticker: str) -> np.ndarray:
        return np.array(self.prices[ticker], dtype=np.float32)
