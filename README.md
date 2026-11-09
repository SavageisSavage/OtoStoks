
# 📈 OtoStoksBot 

> High-speed autonomous algorithmic trading bot and real-time financial terminal for the Steam game **Screen Stocks**.

![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen?style=flat-square)
![Architecture](https://img.shields.io/badge/Data%20Engine-Protocol%20Buffers-orange?style=flat-square)

---

## ⚡ Features at a Glance

* **100% Standalone & Pre-Compiled**: Download and run immediately on **Windows**, **macOS**, or **Linux** — no compilers or dependencies required.
* **Specialized Stock Cycle Algorithms**: Hardcoded quantitative state machines designed specifically for Screen Stocks market behavior ($PUMP, $DUMP, $TECH, $BASE, $WAVE, $STEP, and $QUIK).
* **Billionaire Dividend Vault**: Automatically engages when net worth reaches $1B, permanently compounding passive dividend interest every minute (DRIP) with zero selling.
* **Protocol Buffer Streaming**: High-frequency binary serialization (`.proto`) for tick logging and live background model adaptation with zero game stutter.
* **Modern Web Dashboard (`http://127.0.0.1:8080`)**:
  * 20-tick SVG trend sparklines with glowing apex indicators.
  * Real-time Emerald/Rose flash pulses on every game tick.
  * Live realized session P&L ledger, win-rate counter, and profit factor.
  * One-click Strategy Presets (*Turbo Snowball*, *Growth Core*, *Capital Shield*, *Billionaire Vault*).
  * Synthesized Web Audio feedback (chimes for Buy, Short, and Close).
  * 1-Click CSV Trade History export.
  * Emergency full liquidation to 100% cash upon stopping Auto Mode.

---

## 📥 Installation & Quick Start

### Step 0: Download the Latest Release
1. Go to the **[Releases](https://github.com/SavageisSavage/OtoStoksBot/releases/latest)** page on this repository.
2. Under the **Assets** section, download the package for your operating system:
   * **Windows**: `OtoStoksBot-WINDOWS.exe`
   * **macOS**: `OtoStoksBot-MAC.dmg`
   * **Linux**: `OtoStoksBot-LINUX.tar.gz`

---

### 🪟 Windows Setup

1. **Download**: Grab `OtoStoksBot-WINDOWS.exe` from Releases.
2. **Launch**:
   * Double-click `OtoStoksBot-WINDOWS.exe`.
   * A terminal window will open, and your web browser will automatically load the dashboard at `http://127.0.0.1:8080`.
3. **Start Screen Stocks**:
   * Launch **Screen Stocks** on Steam.
   * The bot will automatically verify the BepInEx mod bridge and show a green **Connected** status.
4. **Engage Trading**:
   * In the browser dashboard, click **Switch to AUTO MODE** to begin trading.

> **Tip**: If Windows SmartScreen displays a warning, click **More info** $\rightarrow$ **Run anyway** (this appears for any freshly compiled indie open-source binary).

---

### 🍎 macOS Setup

1. **Download**: Grab `OtoStoksBot-MAC.dmg` from Releases.
2. **Mount the Image**:
   * Double-click `OtoStoksBot-MAC.dmg` to mount the disk image.
   * Open the mounted volume on your desktop.
3. **Run**:
   * Double-click `OtoStoksBot.app` (or right-click `run_mac.sh` $\rightarrow$ **Open with Terminal**).
   * Your browser will automatically open `http://127.0.0.1:8080`.
4. **Connect to Game**:
   * Launch Screen Stocks on Steam. The dashboard will automatically lock onto the local socket.

> **macOS Security Note**: If macOS blocks the app with *"cannot be opened because it is from an unidentified developer"*:
> 1. Open **System Settings** $\rightarrow$ **Privacy & Security**.
> 2. Scroll down and click **Open Anyway**.
> 3. Alternatively, open Terminal and run:
>    ```bash
>    xattr -cr /path/to/OtoStoksBot.app
>    ```

---

### 🐧 Linux Setup

1. **Download**: Grab `OtoStoksBot-LINUX.tar.gz` from Releases.
2. **Extract**:
   ```bash
   tar -xzf OtoStoksBot-LINUX.tar.gz
   cd OtoStoksBot_Linux
   ```
3. **Run**:
   ```bash
   chmod +x run_linux.sh
   ./run_linux.sh
   ```
   * The launcher checks Python 3, sets up a local isolated virtual environment, installs lightweight dependencies (`fastapi`, `proto-plus`), and starts the engine.
4. **Open Dashboard**:
   * Open `http://127.0.0.1:8080` in your browser.
   * Launch Screen Stocks via Steam (Proton / Native).

---

## 🛠️ Running From Source Code

If you prefer inspecting or running directly from raw source code:

1. Clone or download `OtoStoks_source.zip` from Releases:
   ```bash
   git clone https://github.com/your-username/OtoStoksBot.git
   cd OtoStoksBot
   ```

2. Create and activate a virtual environment:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Launch the bot:
   ```bash
   python main.py
   ```

---

## 📊 Core Algorithmic Strategies

Screen Stocks contains programmed market mechanics. OtoStoksBot replaces generic trading indicators with dedicated state machines:

| Ticker | Market Personality | Algorithmic Execution Strategy |
| :--- | :--- | :--- |
| **$PUMP** | Parabolic vertical surges ($20–$270+) | Tracks high-water mark peak velocity. Dynamically tightens trailing stop as price climbs, holds long throughout the surge, immediately executes a **100% MAX Short** at peak exhaustion down to base ($7.00–$9.20), covers, and re-enters long. |
| **$DUMP** | Deep cratering followed by rebound | Rides short all the way down to $2.50–$5.50 floor. Detects floor inflection, covers short, and enters **100% MAX Long** to ride the recovery wave back to $9.80+. |
| **$TECH** | Exponential growth and collapse loop | Accumulates dips at $8.00–$12.00, holds long strictly to Target X ($16.0 default, or $20/$25 presets), sells all long, immediately shorts the peak, and covers at dip bottom. |
| **$BASE** | Player market stock with daily crash | Synchronized to the game's **12:30 AM IST (00:30 IST / 19:00 UTC)** crash. Auto-hedges before the drop, shorts the plunge down to $1–$25, and accumulates rock-bottom for a 30x–50x recovery surge. |
| **$WAVE** | Sinusoidal harmonic oscillator | Uses curvature checks to buy harmonic wave troughs (oversold) and short crest peaks (overbought). |
| **$STEP** | Consolidates at horizontal steps | Collects **2.0%/min passive dividend yield** ($STEP) while arbitrating step breakouts. |
| **$QUIK** | Exponential runner | Lets winners run with a Sudden Dump Guard that locks in profit if price pulls back by >4% from an 8%+ run. |
| **$BANK** | Low-volatility dead money | **Permanently blacklisted.** Never analyzed, traded, or shorted under any condition. |
| **Vault** | Net worth $\ge$ $1,000,000,000 | **Billionaire Dividend Vault**: 100% capital locked into top dividend payers ($STEP, $STEAM, $WAVE), zero selling, automated DRIP reinvestment every 60s for millions per minute in passive interest. |

---

## 🕹️ Dashboard Controls & Shortcuts

* **Auto Mode Toggle**: Switch between **AUTO** (executes trades) and **SUGGESTION** (logs recommendations only).
* **Terminal Hotkeys**:
  * Press `M` in terminal to swap between AUTO and SUGGESTION mode.
  * Press `A` in terminal to toggle Achievements Hunter mode.
* **Liquidate All (`🚨 LIQUIDATE ALL`)**: Instantly closes all open long and short positions to 100% cash.
* **Auto-Stop Safety Sweep**: Disengaging Auto Mode at any time automatically triggers an immediate full cash liquidation.
* **Capital Sizing Console**: Adjust manual trade sizing using the slider (`1%` to `100%`) or quick pills (`10%`, `25%`, `50%`, `75%`, `MAX`).
* **Audio Feedback**: Click `🔊 Audio: ON` in the top bar to toggle synthesized browser trade chimes.
* **Export Ledger**: Click `⬇ Export CSV` above the execution log to download your complete trade ledger into Excel or Google Sheets.

---

## ❓ Troubleshooting

### 1. Dashboard says "Waiting for market feed..."
* Make sure **Screen Stocks** is running and you have loaded into a game save.
* The bot automatically installs the bridge DLL into `Screen Stocks/BepInEx/plugins/`. If your game uses a custom Steam library folder, manually copy `ScreenStocksLocalBridge.dll` into your `BepInEx/plugins/` directory.

### 2. Port 8080 Conflict
* OtoStoksBot automatically scans and clears orphan processes holding port 8080 on startup. If another application (like a local web server) uses port 8080, close that application before starting the bot.

### 3. Antivirus False Positives
* Single-file PyInstaller executables (`.exe`) may occasionally trigger false positives on generic heuristic scanners. The full source code is provided in this repository under `proto/` and `main.py` for complete transparency and independent review.

---

## 📜 License

Distributed under the **MIT License**. See `LICENSE` for more details.
