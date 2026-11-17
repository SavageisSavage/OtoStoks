# OtoStoksBot Pro v4.0 - Autonomous Quantitative Trading Engine

OtoStoksBot Pro v4.0 is a high-frequency, multi-regime autonomous algorithmic trading system and desktop terminal engineered for the Steam game Screen Stocks.

---

## What is New in v4.0

- **Institutional 16-Dimensional Quantitative Pipeline**: Real-time extraction of EMA spread (9/21), Wilder's RSI-14, Bollinger Band %B and Bandwidth, Normalized Volatility (20), multi-horizon return velocity (ret1, ret3, ret8), Momentum Acceleration, Z-Score (30), Normalized MACD Histogram, Kaufman Efficiency Ratio (KAMA), Normalized ATR Ratio (14), Fast Stochastic Oscillator %K, Donchian Channel Breakout Index, and Composite Market Regime Index.
- **Trained 16-Feature Huber LightGBM ONNX Model v4**: Pre-trained on real market tick data with Huber robust loss (70.32% directional accuracy, 74.9 microsecond evaluation latency).
- **5-State Market Regime Classifier**: Dynamically tags and trades market cycles (Trending Bull, Trending Bear, Volatile Breakout, Mean-Reverting Range, and Choppy Noise).
- **Volatility-Adjusted Fractional Kelly Position Sizing**: Mathematically derives optimal capital deployment using win-probability confidence, reward-to-risk ratio, and volatility compression factors.
- **Dynamic ATR Trailing Stops & Stagnation Capital Recycler**: Replaces rigid flat stops with adaptive ATR-based trailing barriers and recycles capital out of stalled sideways tickers.
- **Concurrent Independent Order Execution**: Dispatches multi-stock order recommendations concurrently in parallel via asynchronous order gather.
- **Native Desktop Application**: Runs in a native desktop window (no black terminal console, no localhost URL bar).

---

## Operating Modes & Strategy Presets

1. **Turbo Snowball (< $50k)**: High-velocity compound growth mode with aggressive Kelly fraction for early capital expansion.
2. **Growth Core ($50k - $1B)**: Balanced trend continuation and mean-reversion with dynamic ATR trailing stops.
3. **Capital Shield**: Conservative capital preservation with tight stop-losses, restricted allocation fractions, and strict chop filtering.
4. **Billionaire Dividend Vault (>= $1B)**: Automatic DRIP compounder locking net worth into highest-yield dividend stocks ($STEP, $STEAM, $WAVE) for steady passive revenue per minute.

---

## Quick Start Installation Guide

### Windows Users

#### Method A: Guided Windows Installer (Recommended)
1. Navigate to the GitHub Releases section.
2. Download `OtoStoksBot-Setup.exe`.
3. Run the installer and follow the setup wizard.
4. Launch `OtoStoksBot Pro v4.0` from your Desktop shortcut or Start Menu.
5. Start Screen Stocks on Steam; the bot will link to the game bridge automatically.

#### Method B: Standalone Portable Executable
1. Download `OtoStoksBot-WINDOWS.exe` from Releases.
2. Run the executable directly. No terminal window will appear.

---

### macOS Users

1. Download `OtoStoksBot-MAC.dmg` from Releases.
2. Double-click the `.dmg` file to mount it.
3. Drag `OtoStoksBot.app` into your `Applications` directory.
4. Double-click `OtoStoksBot.app` to launch. The app will automatically initialize a virtual environment and launch the native GUI.

---

### Linux Users

1. Download `OtoStoksBot-LINUX.tar.gz` from Releases.
2. Extract the archive:
   ```bash
   tar -xzf OtoStoksBot-LINUX.tar.gz
   cd OtoStoksBot
   ```
3. Run the launcher script:
   ```bash
   chmod +x run_linux.sh
   ./run_linux.sh
   ```

---

### Running from Clean Source Code

1. Download `OtoStoks_source.zip` or `OtoStoks_source.tar.gz`.
2. Extract the archive into a folder.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the engine:
   ```bash
   python main.py
   ```

---

## System Requirements

- Windows 10/11 (64-bit), macOS 12+ (Apple Silicon or Intel), or modern Linux distribution (Ubuntu 20.04+, Debian 11+, Arch, Fedora).
- Python 3.10+ (if running directly from source code).
- Screen Stocks (Steam App ID: 4356780).

---

## Fork notes (this repository)

This is a working fork of upstream `SavageisSavage/OtoStoks`. See `UPSTREAM.md` for
where the source came from and why the `v5` tag archive on GitHub cannot be used.

### What changed: decision latency

The game republishes `mods/export/market.json` roughly once per second (median
1002 ms, p95 1058 ms over a 900-sample window). Upstream polled that file every
120 ms and re-parsed it unconditionally, so most iterations did full work on
unchanged data. Measured on a real install:

| Stage | Upstream | This fork |
|---|---|---|
| `tasklist` process check | 158 ms **on the event loop**, every 2 s | 45 ms, in a worker thread, skipped while the feed is live |
| Reaction to a new frame | 0-120 ms (avg 60) | ~0-10 ms |
| Unchanged-frame work | read + parse, 0.26 ms | one byte compare, 0.08 ms |
| ONNX evaluation | 17 calls per frame | 1 batched call (3.0x faster) |
| Order dispatch | blind `sleep(0.12)` + re-read | pickup confirmation via `stat` |
| HTTP bridge probe | every iteration | only when the file feed is quiet |

End-to-end on a live install (game running, native transport, 119 frames):

| Stage | p50 | p95 | max |
|---|---|---|---|
| `snapshot_wait` | 0.30 ms | 0.36 ms | 8.1 ms |
| `features` | 1.87 ms | 2.77 ms | 2.8 ms |
| `inference` | 0.11 ms | 0.13 ms | 0.25 ms |
| `decision` | 0.14 ms | 0.16 ms | 0.23 ms |
| `cycle` | 3.64 ms | 10.76 ms | 11.2 ms |

The game publishes once per second, so the full pipeline is ~0.4% of the budget
between frames. Three separate stalls had to be removed to get there: the
blocking `tasklist` call, an HTTP probe that cost 600 ms whenever it fired, and a
stale-feed check that misread the game's own file write as a dead connection.

Pipeline timings are recorded per stage and published on the dashboard header
(`state.pipeline_metrics`): `snapshot_wait`, `features`, `inference`, `decision`,
`dispatch`, `cycle`. The header shows the median cycle; hover it for the per-stage
breakdown.

### Running from source

Requires **Python 3.12**; the pinned ONNX/LightGBM wheels are not published for
3.13+ yet.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements.txt
python main.py
```

`requirements-dev.txt` adds the packaging tools (`pyinstaller`). The installer
script is `setup_script.iss` (Inno Setup) and now uses paths relative to the
checkout.

### Tests and measurement

```bash
python -m unittest discover -s tests -v      # 31 tests, stdlib only, no game needed
python tools/bench_feed.py --seconds 10      # feed path against the live export
python tools/verify_env.py                   # deps, ONNX model, inference benchmark
```

The test suite builds a synthetic game directory, so it exercises the mod file
protocol (`mods/export/market.json`, `mods/commands/<TICKER>/*.json`) without
Screen Stocks running.

### Known caveats

- `websockets` is a required runtime dependency, not a leftover. Without it
  uvicorn refuses WebSocket upgrades and the dashboard never updates while the
  bot keeps trading, so the failure is silent unless you check the browser
  console.
- The bridge DLL (`OtoStoksBridge.dll`) is a prebuilt BepInEx/Harmony assembly
  with no source in any release. Rebuilding it is a separate C# project.
- Upstream has no `LICENSE`, so all rights are reserved by default. Keep this
  fork private unless the author grants a license.
- `mods/commands/<TICKER>/*.json` is polled with `os.stat` gating: holding a read
  handle on those files every few milliseconds can make the game's own
  write/delete fail on Windows.

