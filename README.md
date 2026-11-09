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
