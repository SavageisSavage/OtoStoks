"""
tools/bench_feed.py - Measures the cost of the market feed path.

Compares the upstream strategy (read + parse market.json on a fixed 120 ms loop)
with the change-driven watcher used by this fork. Runs against the real export
file on this machine, so it needs no game process and no third-party packages.

    python tools/bench_feed.py [--file PATH] [--seconds 10]
"""
import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_mod import MarketFileWatcher, normalise_market_data  # noqa: E402


def default_export_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(
        home, "AppData", "LocalLow", "Conradical Games", "Screen Stocks",
        "mods", "export", "market.json",
    )


def time_call(fn, repeat=200):
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=default_export_path())
    ap.add_argument("--seconds", type=float, default=10.0)
    args = ap.parse_args()

    path = args.file
    if not os.path.exists(path):
        print(f"market.json not found at {path}")
        print("Run Screen Stocks once with mod support enabled, or pass --file.")
        return 1

    raw = open(path, "rb").read()
    payload = json.loads(raw)
    size_kb = len(raw) / 1024.0
    print(f"export: {path}")
    print(f"size  : {size_kb:.1f} KB, {len(payload.get('stocks', []))} tickers\n")

    # --- Stage costs -----------------------------------------------------------
    def full_read_parse():
        with open(path, "rb") as f:
            buf = f.read()
        normalise_market_data(json.loads(buf))

    def parse_only():
        normalise_market_data(json.loads(raw))

    def stat_and_compare():
        st = os.stat(path)
        with open(path, "rb") as f:
            buf = f.read()
        return buf == raw and st.st_size >= 0

    full = time_call(full_read_parse)
    parse = time_call(parse_only)
    cheap = time_call(stat_and_compare)

    def show(label, samples):
        print(f"{label:<34} p50 {statistics.median(samples):7.3f} ms   "
              f"mean {statistics.mean(samples):7.3f} ms   max {max(samples):7.3f} ms")

    show("read + parse + normalise (upstream)", full)
    show("json + normalise only", parse)
    show("stat + byte compare (this fork)", cheap)

    # --- End-to-end loop simulation -------------------------------------------
    # The feed publishes ~1 frame/sec (measured from history.json: median 1002 ms).
    frames_per_sec = 1.0
    iterations_upstream = int(args.seconds / 0.120)
    iterations_new = int(args.seconds / 0.010)

    upstream_cost = iterations_upstream * statistics.median(full)
    new_cost = iterations_upstream * statistics.median(cheap)  # same loop rate, gated
    print(f"\nSimulated {args.seconds:.0f} s at {frames_per_sec:.0f} frame/s")
    print(f"  upstream 120 ms loop : {iterations_upstream:5d} parses of unchanged data, "
          f"{upstream_cost:8.1f} ms CPU")
    print(f"  this fork, 120 ms    : {iterations_upstream:5d} polls, "
          f"{int(iterations_upstream * frames_per_sec * 0.120)} parses, "
          f"{upstream_cost - new_cost:8.1f} ms saved")
    print(f"  this fork, 10 ms     : {iterations_new:5d} polls, "
          f"{int(args.seconds * frames_per_sec)} parses, "
          f"reaction <= 10 ms instead of <= 120 ms")

    # --- Watcher correctness on the live file ---------------------------------
    watcher = MarketFileWatcher()
    changed, snap, age = watcher.poll(force=True)
    print(f"\nwatcher: first poll changed={changed}, "
          f"tickers={len((snap or {}).get('stocks', {}))}, file age={age:.0f} ms")
    changed, _, _ = watcher.poll()
    print(f"watcher: unchanged poll changed={changed} (must be False)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
