"""
tools/verify_env.py - Verifies the installed environment and measures the
inference path against recorded market history.

Uses the game's own history.json (900 samples per ticker) to build realistic
feature vectors, then checks that batched inference is numerically identical to
the upstream per-ticker path, and reports the timing difference.

    .venv\\Scripts\\python tools\\verify_env.py
"""
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from core.config import get_model_path  # noqa: E402
from engine.features import compute_features, MIN_FEATURE_TICKS  # noqa: E402
from engine.ml_engine import LocalModelEngine  # noqa: E402


def default_history_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(
        home, "AppData", "LocalLow", "Conradical Games", "Screen Stocks",
        "mods", "export", "history.json",
    )


def check_imports() -> bool:
    ok = True
    for name in ["numpy", "fastapi", "uvicorn", "pydantic", "onnxruntime",
                 "lightgbm", "onnxmltools", "skl2onnx", "proto", "webview"]:
        try:
            mod = __import__(name)
            version = getattr(mod, "__version__", "")
            print(f"  {name:<12} OK   {version}")
        except Exception as exc:
            ok = False
            print(f"  {name:<12} FAIL {type(exc).__name__}: {exc}")
    return ok


def load_features(path: str):
    """Builds one feature vector per ticker from the tail of its recorded history."""
    data = json.load(open(path, encoding="utf-8"))
    vectors, names = [], []
    for stock in data.get("stocks", []):
        samples = stock.get("samples") or stock.get("history") or []
        prices = np.array([s["price"] for s in samples], dtype=np.float32)
        if len(prices) < MIN_FEATURE_TICKS:
            continue
        vectors.append(compute_features(prices[-120:]))
        names.append(stock.get("stockId", "?"))
    return names, np.vstack(vectors) if vectors else np.zeros((0, 16), np.float32)


def main() -> int:
    print("Dependencies:")
    if not check_imports():
        print("\nEnvironment incomplete; install requirements.txt first.")
        return 1

    model_path = get_model_path()
    print(f"\nModel: {model_path} ({os.path.getsize(model_path) / 1024:.0f} KB)")
    engine = LocalModelEngine(model_path)
    print(f"ONNX session: {'loaded' if engine.session is not None else 'UNAVAILABLE (analytical fallback only)'}")

    history = default_history_path()
    if not os.path.exists(history):
        print(f"\nNo history.json at {history}; skipping inference benchmark.")
        return 0

    names, feats = load_features(history)
    if len(feats) == 0:
        print("\nNo usable feature vectors in history.json.")
        return 1
    print(f"Feature vectors: {len(feats)} tickers x {feats.shape[1]} factors from {os.path.basename(history)}")

    # Pre-build the raw price windows once: parsing the 1 MB history inside a
    # timing loop measures JSON decoding, not the feature pipeline.
    raw = json.load(open(history, encoding="utf-8"))
    windows = []
    for stock in raw.get("stocks", []):
        samples = stock.get("samples") or stock.get("history") or []
        prices = np.array([s["price"] for s in samples], dtype=np.float32)
        if len(prices) >= MIN_FEATURE_TICKS:
            windows.append(prices[-120:])

    # --- Numerical equivalence -------------------------------------------------
    per_ticker = [engine.predict(row) for row in feats]
    batched = engine.predict_batch(feats)
    mismatches = 0
    for a, b in zip(per_ticker, batched):
        if a[1] != b[1] or abs(a[0] - b[0]) > 1e-9 or abs(a[2] - b[2]) > 1e-9 or a[3] != b[3]:
            mismatches += 1
    print(f"Batched vs per-ticker: {'identical' if mismatches == 0 else f'{mismatches} MISMATCHES'}")

    # --- Timing ----------------------------------------------------------------
    rounds = 200

    t0 = time.perf_counter()
    for _ in range(rounds):
        for row in feats:
            engine.predict(row)
    per_ticker_ms = (time.perf_counter() - t0) * 1000.0 / rounds

    t0 = time.perf_counter()
    for _ in range(rounds):
        engine.predict_batch(feats)
    batched_ms = (time.perf_counter() - t0) * 1000.0 / rounds

    t0 = time.perf_counter()
    for _ in range(rounds):
        for window in windows:
            compute_features(window)
    features_ms = (time.perf_counter() - t0) * 1000.0 / rounds

    print(f"\nPer frame ({len(feats)} tickers):")
    print(f"  features            {features_ms:7.3f} ms")
    print(f"  inference per-ticker{per_ticker_ms:7.3f} ms   (upstream)")
    print(f"  inference batched   {batched_ms:7.3f} ms   ({per_ticker_ms / max(batched_ms, 1e-9):.1f}x faster)")
    print(f"  total now           {features_ms + batched_ms:7.3f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
