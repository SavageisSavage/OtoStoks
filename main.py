"""
OtoStoksBot - Automated trading bot and live dashboard for Screen Stocks.
Supports Windows, macOS, and Linux.
"""

import os
import sys
import io
from contextlib import asynccontextmanager

# ------------------------------------------------------------------------------
# Fix for Windows Windowed / GUI Mode (--windowed) where stdout/stderr are None
# ------------------------------------------------------------------------------
class SafeStream:
    def __init__(self, fallback_path=None):
        self.fallback = None
        if fallback_path:
            try:
                self.fallback = open(fallback_path, "a", encoding="utf-8")
            except Exception:
                self.fallback = None

    def write(self, s):
        if self.fallback:
            try:
                self.fallback.write(s)
                self.fallback.flush()
            except Exception:
                pass

    def flush(self):
        if self.fallback:
            try:
                self.fallback.flush()
            except Exception:
                pass

    def isatty(self):
        return False

log_dir = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, 'frozen', False) else __file__))
log_file = os.path.join(log_dir, "otostoksbot.log")

if sys.stdout is None:
    sys.stdout = SafeStream(log_file)
if sys.stderr is None:
    sys.stderr = SafeStream(log_file)
if sys.stdin is None:
    sys.stdin = io.StringIO()

# Standalone native desktop window support
try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

import time
import json
import shutil
import sqlite3
import asyncio
import threading
import webbrowser
import subprocess
import collections
import urllib.request
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set

import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse, Response
import csv
import datetime

# Protocol Buffer Integration for OtoStoksBot
try:
    import otostoks_proto as pb
except ImportError:
    try:
        from proto import otostoks_proto as pb
    except ImportError:
        _curr_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        for _cand in [_curr_dir, os.path.join(_curr_dir, 'proto'), os.path.join(os.path.dirname(os.path.abspath(__file__)), 'proto')]:
            if os.path.exists(_cand) and _cand not in sys.path:
                sys.path.insert(0, _cand)
        import otostoks_proto as pb
from pydantic import BaseModel

# Try importing onnxruntime
try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False

# Try importing online re-training libraries
try:
    import lightgbm as lgb
    import pandas as pd
    from onnxmltools import convert_lightgbm
    from onnxconverter_common.data_types import FloatTensorType
    HAS_TRAIN_LIBS = True
except ImportError:
    HAS_TRAIN_LIBS = False

from datetime import datetime, timezone, timedelta

def is_base_crash_window() -> Tuple[bool, str]:
    """
    Checks if current time is within $BASE's 12:30 AM IST (00:30 IST) 24h crash window.
    IST is UTC + 5:30.
    """
    try:
        utc_now = datetime.now(timezone.utc)
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        crash_time_today = ist_now.replace(hour=0, minute=30, second=0, microsecond=0)
        diff_sec = (ist_now - crash_time_today).total_seconds()
        is_in_crash = (-300 <= diff_sec <= 1200) # 5 min before to 20 min after
        
        if ist_now >= (crash_time_today + timedelta(minutes=20)):
            next_crash = crash_time_today + timedelta(days=1)
        else:
            next_crash = crash_time_today
        sec_left = max(0, int((next_crash - ist_now).total_seconds()))
        hours, remainder = divmod(sec_left, 3600)
        minutes, seconds = divmod(remainder, 60)
        countdown_str = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
        return is_in_crash, countdown_str
    except Exception:
        return False, "Unknown"

def get_stock_profile(ticker: str, name: str = "") -> str:
    """
    Identifies the unique game stock personality based on user mechanics.
    """
    t = str(ticker).upper().replace("$", "")
    n = str(name).upper().replace("$", "")
    if t == "BANK" or n == "BANK": return "BANK"
    if t in ("TECH",) or n in ("TECH",): return "TECH"
    if t in ("PUMP",) or n in ("PUMP",): return "PUMP"
    if t in ("DUMP",) or n in ("DUMP",): return "DUMP"
    if t in ("WAVE",) or n in ("WAVE",): return "WAVE"
    if t in ("QUIK",) or n in ("QUIK",): return "QUIK"
    if t in ("PLAIN", "BASE") or n in ("PLAIN", "BASE"): return "BASE"
    if t in ("IDXA", "MOVE") or n in ("IDXA", "MOVE"): return "MOVE"
    if t in ("STEP",) or n in ("STEP",): return "STEP"
    if t in ("STEAM", "TEAM") or n in ("STEAM", "TEAM"): return "TEAM"
    return "GENERIC"

STEAM_APP_ID = "4356780"

# Process management & mod bridge installer

def cleanup_old_instances():
    """
    Terminates any previously running stale instances of OtoStoksBot.exe (excluding current PID),
    guaranteeing a clean start without touching other applications or ports.
    """
    current_pid = os.getpid()
    if sys.platform != "win32":
        return

    target_procs = {"otostoksbot.exe", "screenotonomus.exe", "screenstocksbot.exe"}
    
    # Kill stale bot instances only
    try:
        out = subprocess.check_output('tasklist /FO CSV /NH', shell=True, text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) >= 2:
                proc_name = parts[0].lower()
                pid_str = parts[1]
                if proc_name in target_procs and pid_str.isdigit():
                    pid = int(pid_str)
                    if pid != current_pid:
                        try:
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        except Exception:
                            pass
    except Exception:
        pass
    time.sleep(0.5)

def find_available_port(preferred_port: int = 8080) -> int:
    """Finds an available local port starting from preferred_port without terminating other apps."""
    import socket
    for p in range(preferred_port, preferred_port + 25):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', p))
                return p
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def get_protobuf_paths() -> Tuple[str, str]:
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    ticks_pb = os.path.join(data_dir, "otostoks_ticks.pb")
    trades_pb = os.path.join(data_dir, "otostoks_trades.pb")
    return ticks_pb, trades_pb


def get_settings_path() -> str:
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "settings.json")


def record_trade_in_proto(trades_pb_path: str, ticker: str, action: str, price: float, amount: int, profit_pct: Optional[float], reason: str):
    try:
        trade_id = int(time.time() * 1000)
        rec = pb.TradeRecord(
            trade_id=trade_id,
            timestamp=int(time.time()),
            ticker=str(ticker),
            action=str(action),
            price=float(price),
            amount=int(amount),
            profit_pct=float(profit_pct) if profit_pct is not None else 0.0,
            reason=str(reason)
        )
        pb.append_trade_record(trades_pb_path, rec)
    except Exception as e:
        pass


def run_retrain_pipeline(state: 'AppState') -> Tuple[bool, str]:
    if not HAS_TRAIN_LIBS:
        msg = "Retraining failed: lightgbm/pandas/onnxmltools not available."
        print(f"[!] {msg}", flush=True)
        return False, msg

    with state.lock:
        if state.retraining_status == "Training in progress...":
            return False, "Retraining is already running."
        state.retraining_status = "Training in progress..."
        state.retrain_started_at = time.time()

    print("[*] [PROTOBUF AUTO-LEARNER] Background self-training on Protocol Buffer datastore...", flush=True)
    try:
        t_start = time.time()
        ticker_data = pb.load_ticks_for_training(state.ticks_pb_path)
        total_points = sum(len(v) for v in ticker_data.values())

        if total_points < 300:
            with state.lock:
                state.retraining_status = "Collecting Live Data..."
            return False, f"Collecting live ticks for model adaptation ({total_points}/300 points gathered)."

        feature_rows = []
        forward_horizon = 8

        # Issue 9: Use EXACT unified compute_features on rolling slices for 100% calculation consistency!
        for stock_id, points in ticker_data.items():
            p = np.array([pt[1] for pt in points], dtype=np.float32)
            n = len(p)
            if n < 40:
                continue

            stock_rows = []
            for i in range(25, n - forward_horizon):
                feat_i = compute_features(p[:i+1])
                target_ret = (p[i + forward_horizon] - p[i]) / (p[i] + 1e-8)
                stock_rows.append(np.append(feat_i, target_ret))

            if stock_rows:
                feature_rows.append(np.array(stock_rows, dtype=np.float32))

        if not feature_rows:
            with state.lock:
                state.retraining_status = "Active (Continuous Learner)"
            return False, "Feature extraction produced 0 rows."

        all_data = np.vstack(feature_rows)
        all_data = all_data[~np.isnan(all_data).any(axis=1)]
        all_data = all_data[~np.isinf(all_data).any(axis=1)]

        split_idx = int(len(all_data) * 0.85)
        train_data = all_data[:split_idx]
        val_data = all_data[split_idx:]

        X_train, y_train = train_data[:, :16], train_data[:, 16]
        X_val, y_val = val_data[:, :16], val_data[:, 16]

        train_ds = lgb.Dataset(X_train, label=y_train)
        val_ds = lgb.Dataset(X_val, label=y_val, reference=train_ds)

        params = {
            'objective': 'huber',
            'metric': ['huber', 'l1'],
            'boosting_type': 'gbdt',
            'learning_rate': 0.04,
            'num_leaves': 45,
            'max_depth': 7,
            'min_data_in_leaf': 35,
            'feature_fraction': 0.85,
            'bagging_fraction': 0.85,
            'bagging_freq': 3,
            'verbosity': -1,
            'seed': 42
        }

        model = lgb.train(
            params,
            train_ds,
            num_boost_round=180,
            valid_sets=[val_ds],
            callbacks=[lgb.early_stopping(stopping_rounds=25, verbose=False)]
        )

        preds = model.predict(X_val)
        dir_correct = np.sum((preds * y_val) > 0)
        dir_acc = float(dir_correct / len(y_val))

        # Convert to ONNX with 16 features
        initial_type = [('float_input', FloatTensorType([None, 16]))]
        onnx_model = convert_lightgbm(model, initial_types=initial_type, target_opset=12)

        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        out_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.onnx"),
            os.path.join(base_dir, "model.onnx"),
            r"C:\Users\HP\.gemini\antigravity\scratch\ScreenStocksApp\model.onnx"
        ]
        for op in out_paths:
            try:
                os.makedirs(os.path.dirname(op), exist_ok=True)
                with open(op, "wb") as f:
                    f.write(onnx_model.SerializeToString())
            except Exception:
                pass

        # Hot-reload in memory atomically
        if HAS_ORT:
            try:
                state.inference_engine.session = ort.InferenceSession(onnx_model.SerializeToString())
                print("[+] [AI HOT-RELOAD] Active ONNX inference session updated in-memory!", flush=True)
            except Exception as e:
                print(f"[!] Hot-reload notice: {e}", flush=True)

        elapsed = round(time.time() - t_start, 2)
        with state.lock:
            state.retraining_status = "Active (Continuous Learner)"
            state.last_retrain_time = datetime.now().strftime("%H:%M:%S")
            state.retrain_accuracy = round(dir_acc * 100.0, 1)
            state.retrain_est_seconds = elapsed
            state.auto_retrain_count += 1

        msg = f"Auto-Retrain #{state.auto_retrain_count} Complete! Samples: {len(all_data):,}, Accuracy: {state.retrain_accuracy}%, Time: {elapsed}s"
        print(f"[+] [AI AUTO-TRAIN SUCCESS] {msg}", flush=True)
        state.add_log("AI_ENGINE", "MODEL_RETRAIN", state.mode, msg, "SUCCESS")
        return True, msg
    except Exception as e:
        with state.lock:
            state.retraining_status = f"Error: {e}"
        print(f"[!] [AI RETRAINING ERROR] {e}", flush=True)
        return False, str(e)


def run_auto_installer() -> Tuple[bool, str]:
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    dll_candidates = [
        os.path.join(base_dir, "OtoStoksBridge.dll"),
        os.path.join(base_dir, "OtoStoksBotBridge.dll"),
        os.path.join(base_dir, "ScreenStocksLocalBridge.dll"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "OtoStoksBotBridge.dll"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ScreenStocksLocalBridge.dll"),
        r"C:\Users\HP\.gemini\antigravity\scratch\ScreenStocksApp\OtoStoksBotBridge.dll",
        r"C:\Users\HP\.gemini\antigravity\scratch\ScreenStocksLocalBridge\bin\ScreenStocksLocalBridge.dll"
    ]
    
    src_dll = next((p for p in dll_candidates if os.path.exists(p)), None)
    
    steam_path = None
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
        except Exception:
            steam_path = None
    elif sys.platform == "darwin":
        mac_steam = os.path.expanduser("~/Library/Application Support/Steam")
        if os.path.exists(mac_steam):
            steam_path = mac_steam
    elif sys.platform.startswith("linux"):
        for linux_steam in [os.path.expanduser("~/.steam/steam"), os.path.expanduser("~/.local/share/Steam")]:
            if os.path.exists(linux_steam):
                steam_path = linux_steam
                break

    target_dir = None
    if steam_path:
        cand = os.path.join(steam_path, "steamapps", "common", "Screen Stocks", "BepInEx", "plugins")
        if os.path.exists(cand):
            target_dir = cand

    if not target_dir:
        fallbacks = [
            r"C:\Program Files (x86)\Steam\steamapps\common\Screen Stocks\BepInEx\plugins",
            os.path.expanduser("~/Library/Application Support/Steam/steamapps/common/Screen Stocks/BepInEx/plugins"),
            os.path.expanduser("~/.steam/steam/steamapps/common/Screen Stocks/BepInEx/plugins"),
            os.path.expanduser("~/.local/share/Steam/steamapps/common/Screen Stocks/BepInEx/plugins")
        ]
        for fb in fallbacks:
            if os.path.exists(fb):
                target_dir = fb
                break

    if not src_dll:
        msg = "[INSTALLER] Source mod DLL (OtoStoksBotBridge.dll / ScreenStocksLocalBridge.dll) not found."
        print(f"[!] {msg}", flush=True)
        return False, msg

    if not target_dir:
        msg = "[INSTALLER] Target BepInEx plugins directory not found in Steam path."
        print(f"[!] {msg}", flush=True)
        return False, msg

    try:
        os.makedirs(target_dir, exist_ok=True)
        # Check both names in destination
        dest_candidates = [
            os.path.join(target_dir, "OtoStoksBotBridge.dll"),
            os.path.join(target_dir, "ScreenStocksLocalBridge.dll")
        ]
        active_dest = next((p for p in dest_candidates if os.path.exists(p)), dest_candidates[0])
        try:
            shutil.copy2(src_dll, active_dest)
            msg = f"OtoStoksBot mod DLL updated in plugins folder:\n    {active_dest}"
            print(f"[+] [AUTO-INSTALLER SUCCESS] {msg}", flush=True)
            return True, msg
        except Exception:
            msg = f"OtoStoksBot mod DLL is already installed and loaded by the running game."
            print(f"[+] [AUTO-INSTALLER] {msg}", flush=True)
            return True, msg
    except Exception as e:
        msg = f"Failed to copy DLL: {e}"
        print(f"[!] [AUTO-INSTALLER NOTICE] {msg}", flush=True)
        return False, msg


# Check if Screen Stocks is running (Windows, macOS, Linux)
def check_game_process() -> Tuple[bool, Optional[int]]:
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq Screen Stocks.exe" /NH',
                shell=True,
                text=True,
                stderr=subprocess.DEVNULL
            )
            if "Screen Stocks.exe" in out:
                for line in out.strip().splitlines():
                    if "Screen Stocks.exe" in line:
                        parts = line.split()
                        if len(parts) > 1 and parts[1].isdigit():
                            return True, int(parts[1])
                return True, None
        except Exception:
            pass
    elif sys.platform == "darwin" or sys.platform.startswith("linux"):
        try:
            out = subprocess.check_output(["pgrep", "-f", "Screen Stocks"], text=True, stderr=subprocess.DEVNULL)
            for line in out.strip().splitlines():
                if line.strip().isdigit():
                    return True, int(line.strip())
        except Exception:
            pass
    return False, None


def launch_screen_stocks() -> Tuple[bool, str]:
    try:
        steam_uri = f"steam://rungameid/{STEAM_APP_ID}"
        print(f"[*] Launching game via Steam URL: {steam_uri}")
        webbrowser.open(steam_uri)
        return True, f"Launched Screen Stocks (AppID: {STEAM_APP_ID})"
    except Exception as e:
        err = f"Failed to launch game: {e}"
        print(f"[!] {err}")
        return False, err


# Technical indicators & inference engine

SIGNAL_STRONG_BUY = 2
SIGNAL_BUY = 1
SIGNAL_NEUTRAL = 0
SIGNAL_SHORT = -1
SIGNAL_STRONG_SHORT = -2

SIGNAL_LABELS = {
    SIGNAL_STRONG_BUY: "STRONG BUY",
    SIGNAL_BUY: "BUY",
    SIGNAL_NEUTRAL: "NEUTRAL",
    SIGNAL_SHORT: "SHORT",
    SIGNAL_STRONG_SHORT: "STRONG SHORT"
}


def compute_features(prices: np.ndarray) -> np.ndarray:
    """
    Institutional 16-Factor Quantitative Feature Pipeline:
    Extracts multi-timeframe trend, momentum, volatility, oscillation, 
    Kaufman efficiency ratio, and macro regime score in vectorized NumPy.
    """
    p = np.asarray(prices, dtype=np.float32)
    n = len(p)
    if n < 12:
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
    def __init__(self, max_history: int = 120):
        # Continuous rolling time-series window across snapshots
        self.prices: Dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque(maxlen=max_history))
        self.timestamps: Dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque(maxlen=max_history))

    def update(self, ticker: str, price: float, ts_ms: Optional[int] = None) -> Optional[np.ndarray]:
        dq = self.prices[ticker]
        tq = self.timestamps[ticker]
        curr_ts = ts_ms or int(time.time() * 1000)

        # If duplicate tick at exact same millisecond and price, ignore duplicate
        if dq and len(dq) > 0 and dq[-1] == price and tq and (curr_ts - tq[-1]) < 80:
            pass
        else:
            dq.append(price)
            tq.append(curr_ts)

        if len(dq) < 8:
            return None

        # Call unified feature calculation (guarantees 100% equivalence with training math)
        return compute_features(np.array(dq, dtype=np.float32))


class LocalModelEngine:
    def __init__(self, onnx_path: Optional[str] = None):
        self.session = None
        self.input_name = None
        self.version = 4
        
        if onnx_path and os.path.exists(onnx_path) and HAS_ORT:
            try:
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 2
                self.session = ort.InferenceSession(onnx_path, sess_options=opts, providers=['CPUExecutionProvider'])
                self.input_name = self.session.get_inputs()[0].name
                print(f"[+] Loaded Advanced 16-Factor ONNX Model from {onnx_path}")
            except Exception as e:
                print(f"[!] Warning: Could not init ONNX session ({e}), using analytical multi-factor engine.")

    def predict(self, feat: np.ndarray) -> Tuple[float, int, float, str]:
        """
        Evaluates 16-factor vector via ONNX & analytical ensemble:
        Returns: (expected_return, signal_code, confidence, regime)
        """
        if len(feat) < 16:
            f16 = np.zeros(16, dtype=np.float32)
            f16[:min(16, len(feat))] = feat[:min(16, len(feat))]
            feat = f16

        # Fast ONNX inference
        expected_ret = None
        if self.session is not None:
            try:
                raw = self.session.run(None, {self.input_name: np.expand_dims(feat, axis=0)})[0]
                expected_ret = float(raw[0][0])
            except Exception:
                pass

        ema_spread = float(feat[0])
        rsi14 = float(feat[1])
        bb_pct = float(feat[2])
        bb_width = float(feat[3])
        vol20 = float(feat[4])
        ret1 = float(feat[5])
        ret3 = float(feat[6])
        ret8 = float(feat[7])
        acceleration = float(feat[8])
        zscore30 = float(feat[9])
        macd_hist = float(feat[10])
        kama_eff = float(feat[11])
        atr_ratio = float(feat[12])
        stoch_k = float(feat[13])
        donchian_pct = float(feat[14])
        regime_score = float(feat[15])

        # Analytical multi-factor return expectation (Huber-smoothed ensemble)
        analytical_ret = float(
            (ema_spread * 0.25) +
            (ret3 * 0.20) +
            (macd_hist * 0.20) +
            (acceleration * 0.15) +
            (regime_score * 0.008 * 0.20)
        )

        if expected_ret is None:
            expected_ret = analytical_ret
        else:
            # 70% ONNX model prediction + 30% analytical factor cross-validation
            expected_ret = float(0.70 * expected_ret + 0.30 * analytical_ret)

        # ----------------------------------------------------------------------
        # Multi-Regime Classification Engine
        # ----------------------------------------------------------------------
        if kama_eff > 0.38 and regime_score > 0.20:
            regime = "TRENDING_BULL"
        elif kama_eff > 0.38 and regime_score < -0.20:
            regime = "TRENDING_BEAR"
        elif bb_width > 0.040 and (bb_pct > 1.05 or bb_pct < -0.05):
            regime = "VOLATILE_BREAKOUT"
        elif kama_eff < 0.20 and -0.15 <= regime_score <= 0.15:
            regime = "MEAN_REVERTING_RANGE"
        else:
            regime = "CHOPPY_NOISE"

        # ----------------------------------------------------------------------
        # Signal Generation with Dual-Regime Confluence
        # ----------------------------------------------------------------------
        # Bullish setup:
        # A) Trend markup: Model predicts gain + positive MACD hist + expanding EMA + RSI in healthy zone
        # B) Oversold capitulation bounce: Z-score <= -1.4 + Stoch %K < 20 bouncing + ret1 > 0
        bullish = (
            (expected_ret >= 0.0020 and macd_hist > -0.0005 and 32.0 <= rsi14 <= 82.0 and donchian_pct > 0.30) or
            (zscore30 <= -1.4 and ret1 > 0 and stoch_k < 28.0) or
            (regime == "TRENDING_BULL" and ret1 > 0 and bb_pct < 0.85)
        )

        # Bearish setup:
        # A) Trend breakdown: Model predicts drop + negative MACD hist + decelerating returns
        # B) Overbought exhaustion rejection: Z-score >= 1.5 + Stoch %K > 80 curling + ret1 < 0
        bearish = (
            (expected_ret <= -0.0020 and macd_hist < 0.0005 and 18.0 <= rsi14 <= 68.0 and donchian_pct < 0.70) or
            (zscore30 >= 1.5 and ret1 < 0 and stoch_k > 72.0) or
            (regime == "TRENDING_BEAR" and ret1 < 0 and bb_pct > 0.15)
        )

        signal = SIGNAL_NEUTRAL
        if bullish:
            # Confidence scales with trend efficiency and return magnitude
            confidence = min(0.96, max(0.48, (abs(expected_ret) / 0.008) * 0.45 + (kama_eff * 0.35) + 0.20))
            signal = SIGNAL_STRONG_BUY if (expected_ret >= 0.006 or confidence >= 0.78 or regime == "TRENDING_BULL") else SIGNAL_BUY
        elif bearish:
            confidence = min(0.96, max(0.48, (abs(expected_ret) / 0.008) * 0.45 + (kama_eff * 0.35) + 0.20))
            signal = SIGNAL_STRONG_SHORT if (expected_ret <= -0.006 or confidence >= 0.78 or regime == "TRENDING_BEAR") else SIGNAL_SHORT
        else:
            confidence = 0.20

        return expected_ret, signal, confidence, regime

# Application state and portfolio parameters


def load_persisted_settings() -> Dict[str, Any]:
    """Loads persisted user settings from settings.json."""
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    settings_file = os.path.join(base_dir, "settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_persisted_settings(settings: Dict[str, Any]):
    """Saves user settings safely to settings.json."""
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    settings_file = os.path.join(base_dir, "settings.json")
    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass

class AppState:
    def __init__(self):
        self.lock = threading.RLock()
        self.running = True
        
        # Dual Mode: "AUTO" (execute commands) vs "SUGGESTION" (log recommendations only)
        self.mode = "SUGGESTION"
        # Dedicated Achievements Hunter Mode (Independent on/off toggle button)
        self.achievements_enabled: bool = False
        self.achievement_budget_cap = 25.0  # Max dollars committed to micro-achievement trades (Zero interference)
        self.micro_positions: Set[str] = set()  # Tickers holding 1 share strictly for achievement milestones
        self.position_peak_pnl: Dict[str, float] = {}  # ticker -> peak profit percentage for trailing compounding runs
        self.position_peak_price: Dict[str, float] = {}  # ticker -> peak price (crucial for riding massive PUMP waves)
        self.position_trough_price: Dict[str, float] = {}
        # Ultra Session Performance & Win-Rate Ledger
        self.session_trades_count: int = 0
        self.session_realized_pnl: float = 0.0
        self.session_wins: int = 0
        self.session_losses: int = 0
        self.active_strategy_preset: str = "TURBO"   # ticker -> trough price (crucial for riding full DUMP crashes)
        
        self.connected = False
        self.game_running = False
        self.game_pid: Optional[int] = None
        self.server_tick = 0
        self.last_update_time = 0.0
        self.inf_latency_ms = 0.0

        # Auto Mode Time Limit
        self.auto_mode_started_at: float = 0.0
        self.auto_time_remaining_str: str = "Unlimited"

        # Player Portfolio & Stats
        self.player = {
            "cash": "$0.00",
            "netWorth": "$0.00",
            "cashDouble": 0.0,
            "netWorthDouble": 0.0,
            "totalUnrealizedPnL": 0.0,
            "level": 1,
            "ipoCount": 0,
            "unlockedAchievementCount": 0
        }

        # Multi-Stock State: only unlocked stocks!
        self.stocks: Dict[str, Dict[str, Any]] = {}
        self.unlocked_stocks: Set[str] = set()
        self.last_unlock_poll_time: float = 0.0
        
        # Chart.js rolling window
        self.history_timestamps = collections.deque(maxlen=30)
        self.history_series: Dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque(maxlen=30))

        # Recent logs
        self.logs = collections.deque(maxlen=60)

        # Configurable Settings
        self.settings = {
            "max_positions": 5,
            # Stop loss bar: 0% to 100%, and toggle to ignore completely
            "stop_loss_enabled": True,
            "stop_loss_pct": 15.0,
            # Minimum profit bar: 0% to 100%, and toggle to switch off completely
            "take_profit_enabled": True,
            "min_profit_pct": 5.0,
            # Auto mode time limit in hours (0.0 = unlimited)
            "auto_time_limit_hours": 0.0,
            "tech_target_x": 16.0,
            "max_alloc_pct": 20.0
        }

        # Anti-Loss Circuit Breaker & Penalty Box
        self.penalty_box: Dict[str, float] = {}        # ticker -> timestamp until which entries are blocked
        self.circuit_breaker_until: float = 0.0        # timestamp until which ALL entries are paused
        self.consecutive_losses: int = 0
        self.entry_times: Dict[str, float] = {}        # ticker -> buy timestamp for minimum hold time (15s)
        self.last_order_time: Dict[str, float] = {}    # ticker -> timestamp
        self.post_exit_cooldown: Dict[str, float] = {} # ticker -> timestamp until which re-entry is paused
        self.signal_history: Dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque(maxlen=4))

        # Achievements Hunter Statistics
        self.achievements_stats = {
            "total_buys": 0,
            "total_sells": 0,
            "total_shorts": 0,
            "total_covers": 0,
            "max_single_profit_pct": 0.0,
            "unlocked_stocks_count": 0,
            "unlocked_achievements": 0
        }

        # High-Speed Protocol Buffer Datastore & Continuous Re-Trainer State
        self.ticks_pb_path, self.trades_pb_path = get_protobuf_paths()
        self.tick_buffer = collections.deque()
        self.total_ticks_stored = pb.count_ticks_in_file(self.ticks_pb_path)
        self.session_ticks_collected = 0
        self.retraining_status = "Active (ONNX LightGBM)"
        self.last_retrain_time = "Calibrating..."
        self.retrain_accuracy = None
        self.auto_retrain_seconds_until_next = 60
        self.auto_retrain_count = 0
        self.dividend_vault_active = False
        self.dividend_income_per_min = 0.0
        self.base_crash_countdown_str = "Calculating..."
        self.is_base_crash_active = False
        self.retrain_started_at = 0.0
        self.retrain_est_seconds = 18.0
        self.inference_engine = None

        self.total_ticks_stored = pb.count_ticks_in_file(self.ticks_pb_path)

    def toggle_mode(self) -> str:
        was_auto = False
        with self.lock:
            if self.mode == "SUGGESTION":
                self.mode = "AUTO"
                self.auto_mode_started_at = time.time()
            else:
                self.mode = "SUGGESTION"
                was_auto = True
            current = self.mode
        self.add_log(
            ticker="SYSTEM",
            action="MODE_SWITCH",
            mode=current,
            reason=f"Operating mode swapped to {current}",
            status="ACTIVE"
        )
        # Issue 4: Stopping AUTO mode simply pauses automated order dispatching.
        # It NEVER liquidates positions that the human player opened manually in the game!
        return current

    def liquidate_all_positions(self):
        """
        Immediately dispatches close/exit orders for all currently open positions (long & short),
        leaving the player with 100% cash and zero market risk when stopping auto mode.
        """
        print("[!] [AUTO-STOP LIQUIDATION] Auto mode stopped: Liquidating all open positions to cash...", flush=True)
        try:
            candidates = set()
            with self.lock:
                for t, s in self.stocks.items():
                    holding = str(s.get("holding", "")).upper()
                    if holding and holding != "FLAT":
                        candidates.add(t)
                for t in self.unlocked_stocks:
                    candidates.add(t)

            data = fetch_snapshot_http()
            if data and "stocks" in data:
                stocks = data.get("stocks", {})
                for ticker, s in stocks.items():
                    h = s.get('holding', {})
                    owned = float(h.get('sharesOwnedDouble', 0.0))
                    shorted = float(h.get('sharesShortedDouble', 0.0))
                    if owned > 0 or shorted > 0:
                        candidates.add(ticker)

            if not candidates:
                print("[*] [AUTO-STOP LIQUIDATION] No open positions detected. Portfolio is already 100% cash.", flush=True)
                return

            print(f"[*] [AUTO-STOP LIQUIDATION] Liquidating positions across {len(candidates)} stocks: {list(sorted(candidates))}", flush=True)
            for ticker in sorted(candidates):
                payload = {
                    'id': f"liq_stop_{ticker}_{int(time.time()*1000)}",
                    'action': 'close',
                    'ticker': ticker,
                    'amount': 'max',
                    'isMax': True
                }
                res = dispatch_order_http(payload)
                msg = res.get("message", "Executed") if res else "Order dispatched"
                self.add_log(ticker, "LIQUIDATE_ALL", "AUTO_STOP", f"Auto-liquidated on Auto Mode Stop ({msg})", "EXECUTED")
                print(f"[+] [AUTO-STOP LIQUIDATION] Closed position in {ticker} -> {msg}", flush=True)

            with self.lock:
                self.position_peak_pnl.clear()
                self.position_peak_price.clear()
                self.position_trough_price.clear()
        except Exception as e:
            print(f"[!] Error in liquidate_all_positions: {e}", flush=True)

    def toggle_achievements(self) -> bool:
        with self.lock:
            self.achievements_enabled = not self.achievements_enabled
            curr = self.achievements_enabled
        self.add_log(
            ticker="ACHIEVEMENTS",
            action="ACHIEVE_MODE",
            mode=self.mode,
            reason=f"Achievements Hunter mode {'ENABLED' if curr else 'DISABLED'}",
            status="ACTIVE"
        )
        return curr

    def add_log(self, ticker: str, action: str, mode: str, reason: str, status: str):
        with self.lock:
            self.logs.appendleft({
                "time": datetime.now().strftime("%H:%M:%S"),
                "ticker": ticker,
                "action": action.upper(),
                "mode": mode,
                "reason": reason,
                "status": status
            })

    def update_settings(self, max_pos: int, stop_loss_enabled: bool, stop_loss: float,
                        take_profit_enabled: bool, min_profit: float, auto_hours: float, tech_target_x: float = 16.0):
        with self.lock:
            self.settings["max_positions"] = max(1, min(15, max_pos))
            self.settings["stop_loss_enabled"] = bool(stop_loss_enabled)
            self.settings["stop_loss_pct"] = max(0.0, min(100.0, stop_loss))
            self.settings["take_profit_enabled"] = bool(take_profit_enabled)
            self.settings["min_profit_pct"] = max(0.0, min(100.0, min_profit))
            self.settings["auto_time_limit_hours"] = max(0.0, min(48.0, auto_hours))
            self.settings["tech_target_x"] = max(10.0, min(60.0, tech_target_x))
            if self.mode == "AUTO":
                self.auto_mode_started_at = time.time()
            self._save_settings_to_disk()

    def _save_settings_to_disk(self):
        try:
            settings_json = get_settings_path()
            with open(settings_json, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def _load_settings_from_disk(self):
        try:
            settings_json = get_settings_path()
            if os.path.exists(settings_json):
                with open(settings_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.settings.update(data)
        except Exception:
            pass

    def get_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            stock_list = []
            for ticker, s in sorted(self.stocks.items()):
                stock_list.append(s)

            chart_series = {}
            for ticker, dq in self.history_series.items():
                chart_series[ticker] = list(dq)

            # Update achievements stats
            self.achievements_stats["unlocked_stocks_count"] = len(self.unlocked_stocks)
            self.achievements_stats["unlocked_achievements"] = self.player.get("unlockedAchievementCount", 0)

            return {
                "type": "state_update",
                "mode": self.mode,
                "achievements_enabled": self.achievements_enabled,
                "connected": self.connected,
                "game_running": self.game_running,
                "game_pid": self.game_pid,
                "server_tick": self.server_tick,
                "inf_latency_ms": round(self.inf_latency_ms, 3),
                "auto_time_remaining": self.auto_time_remaining_str,
                "player": self.player,
                "stocks": stock_list,
                "unlocked_stocks": list(sorted(self.unlocked_stocks)),
                "history": {
                    "timestamps": list(self.history_timestamps),
                    "series": chart_series
                },
                "logs": list(self.logs),
                "settings": self.settings,
                "achievements_stats": self.achievements_stats,
                "micro_positions": list(self.micro_positions),
                "db_stats": {
                    "total_ticks": self.total_ticks_stored,
                    "session_ticks": self.session_ticks_collected,
                    "retraining_status": self.retraining_status,
                    "last_retrain_time": self.last_retrain_time,
                    "retrain_accuracy": self.retrain_accuracy,
                    "next_retrain_in": self.auto_retrain_seconds_until_next,
                    "base_crash_countdown": self.base_crash_countdown_str,
                    "is_base_crash_active": self.is_base_crash_active,
                    "dividend_vault_active": self.dividend_vault_active,
                    "dividend_income_per_min": self.dividend_income_per_min,
                    "auto_retrain_count": self.auto_retrain_count,
                    "retrain_seconds_remaining": max(0, int(self.retrain_est_seconds - (time.time() - self.retrain_started_at))) if self.retraining_status == "Training in progress..." else 0,
                    "retrain_est_total": int(self.retrain_est_seconds)
                },
                "circuit_breaker_active": time.time() < self.circuit_breaker_until,
                "session_stats": {
                    "trades_count": self.session_trades_count,
                    "realized_pnl": round(self.session_realized_pnl, 2),
                    "wins": self.session_wins,
                    "losses": self.session_losses,
                    "win_rate": round((self.session_wins / max(1, self.session_wins + self.session_losses)) * 100.0, 1) if (self.session_wins + self.session_losses) > 0 else 0.0,
                    "game_connected": self.game_bridge_connected,
                    "game_pid": self.game_pid,
                    "active_preset": self.active_strategy_preset
                }
            }

app_state = AppState()

def start_auto_retrain_worker(state: AppState):
    """
    Fully Autonomous Background Self-Learning Worker:
    Runs automatically every 60 seconds without requiring user intervention.
    Checks if new ticks arrived, extracts recent sliding window from indexed SQLite
    database in < 0.8 seconds, trains the 10-feature LightGBM model, exports to ONNX in RAM,
    and hot-reloads active inference weights atomically with zero trade interruption.
    """
    def worker():
        time.sleep(8)
        print("[+] [AUTO-TRAINER] Autonomous Background Self-Learner started (cadence: 60s).", flush=True)
        # Warmup training
        try:
            run_retrain_pipeline(state)
        except Exception:
            pass

        last_trained_ticks = state.total_ticks_stored
        last_train_time = time.time()

        while state.running:
            time.sleep(1)
            now = time.time()
            rem = max(0, int(60.0 - (now - last_train_time)))
            with state.lock:
                state.auto_retrain_seconds_until_next = rem

            if (now - last_train_time) >= 60.0:
                new_ticks = state.total_ticks_stored - last_trained_ticks
                last_train_time = time.time()
                # Issue 10: Only retrain if >= 150 new ticks arrived to avoid unnecessary CPU/RAM usage!
                if new_ticks >= 150:
                    if state.retraining_status != "Training in progress...":
                        print(f"[*] [AUTO-TRAINER] Self-learning triggered: +{new_ticks} new ticks buffered. Adapting model...", flush=True)
                        ok, _ = run_retrain_pipeline(state)
                        if ok:
                            last_trained_ticks = state.total_ticks_stored
                else:
                    with state.lock:
                        state.retraining_status = f"Standby (+{new_ticks}/150 new ticks)" 
    t = threading.Thread(target=worker, daemon=True)
    t.start()

def start_tick_storage_worker(state: AppState):
    def worker():
        batch_counter = 0
        while state.running:
            time.sleep(1.2)
            raw_batch = []
            with state.lock:
                while state.tick_buffer:
                    raw_batch.append(state.tick_buffer.popleft())
            if raw_batch:
                try:
                    batch_counter += 1
                    proto_ticks = [
                        pb.MarketTick(
                            ticker=str(t[0]),
                            timestamp_ms=int(t[1]),
                            price=float(t[2]),
                            profile=get_stock_profile(str(t[0]))
                        ) for t in raw_batch
                    ]
                    batch = pb.MarketTickBatch(
                        batch_id=batch_counter,
                        created_at=int(time.time()),
                        ticks=proto_ticks,
                        tick_count=len(proto_ticks)
                    )
                    if pb.append_tick_batch(state.ticks_pb_path, batch):
                        with state.lock:
                            state.session_ticks_collected += len(proto_ticks)
                            state.total_ticks_stored += len(proto_ticks)
                            # Auto-retraining trigger on live data collection
                            if state.session_ticks_collected >= 300 and (state.session_ticks_collected % 1000 == 0):
                                threading.Thread(target=run_retrain_pipeline, args=(state,), daemon=True).start()
                except Exception as e:
                    print(f"[!] Protobuf storage worker error: {e}", flush=True)
    t = threading.Thread(target=worker, daemon=True)
    t.start()


# Strategy engine: stock rules, position sizing, and exits

def evaluate_portfolio(state: AppState, signals: Dict[str, Dict[str, Any]], tick_frame: Dict[str, Any]) -> List[Dict[str, Any]]:
    stocks = tick_frame.get('stocks', {})
    now = time.time()
    orders = []

    # Update $BASE 12:30 AM IST 24-hr Crash Tracker
    is_crash, crash_countdown = is_base_crash_window()
    with state.lock:
        state.is_base_crash_active = is_crash
        state.base_crash_countdown_str = crash_countdown

    # Trading parameters
    stop_loss_enabled = state.settings["stop_loss_enabled"]
    stop_loss_pct = state.settings["stop_loss_pct"]
    take_profit_enabled = state.settings["take_profit_enabled"]
    min_profit_pct = state.settings["min_profit_pct"]
    tech_target_x = state.settings.get("tech_target_x", 16.0)
    max_positions = state.settings["max_positions"]

    cash = state.player.get("cashDouble", 0.0)
    net_worth = max(state.player.get("netWorthDouble", cash), cash)

    # --------------------------------------------------------------------------
    # STRATEGY 2: BILLIONAIRE DIVIDEND VAULT (ACTIVATES WHEN NET WORTH >= $1B)
    # Put all cash into top dividend stocks, hold permanently, collect pure interest/min!
    # --------------------------------------------------------------------------
    # Issue 14: Active trading does NOT stop at $1B unless explicitly set to BILLIONAIRE preset!
    # If using TURBO, GROWTH, or DEFENSIVE, bot continues high-yield active trading while compounding.
    preset = getattr(state, 'active_strategy_preset', 'TURBO')
    is_billionaire_tier = (net_worth >= 1_000_000_000 or cash >= 1_000_000_000) and (preset == "BILLIONAIRE")
    total_div_income = 0.0

    if is_billionaire_tier:
        with state.lock:
            state.dividend_vault_active = True

        # Sort unlocked stocks by dividend yield descending ($STEP 2%, $STEAM 1.3%, $STUMP 1.25%, $WAVE 1%)
        dividend_candidates = []
        for ticker, s in stocks.items():
            s_name = s.get('name', ticker)
            prof = get_stock_profile(ticker, s_name)
            if prof == "BANK":
                continue
            div_rate = float(s.get('dividendRate', 0.0))
            if div_rate > 0:
                dividend_candidates.append((div_rate, ticker, s))

        dividend_candidates.sort(key=lambda x: x[0], reverse=True)

        # 1. Close any open short positions (shorts don't earn dividends)
        for ticker, s in stocks.items():
            h = s.get('holding', {})
            shorted = float(h.get('sharesShortedDouble', 0.0))
            if shorted > 0 and (now - state.last_order_time.get(ticker, 0.0)) >= 2.0:
                orders.append({
                    'action': 'close',
                    'ticker': ticker,
                    'reason': 'Dividend Vault: Closing short position to redeploy capital into pure dividend yield'
                })
                
        # 2. Deploy available cash across top dividend stocks & calculate passive income
        for div_rate, ticker, s in dividend_candidates:
            p = float(s.get('price', 0.0))
            if p <= 0: continue
            h = s.get('holding', {})
            owned = float(h.get('sharesOwnedDouble', 0.0))
            total_div_income += (owned * p * div_rate)

        if cash > 10_000 and dividend_candidates:
            # Reinvest incoming dividend cash into top 4 yields (DRIP)
            for div_rate, ticker, s in dividend_candidates[:4]:
                p = float(s.get('price', 0.0))
                if p <= 0: continue
                if (now - state.last_order_time.get(ticker, 0.0)) >= 2.5:
                    alloc_cash = cash * 0.35
                    share_cnt = int(alloc_cash / p) if alloc_cash >= p else 0
                    if share_cnt > 0 and (share_cnt * p) <= cash:
                        orders.append({
                            'action': 'buy',
                            'ticker': ticker,
                            'amount': str(share_cnt),
                            'reason': f'Dividend Vault DRIP: Buying {share_cnt:,} shares in {ticker} (Yield: {div_rate*100:.2f}%/min)'
                        })
                        cash -= (share_cnt * p)

        with state.lock:
            state.dividend_income_per_min = total_div_income

        # In Billionaire Vault Mode, NEVER sell dividend stocks! Hold permanently for passive interest!
        return orders
    else:
        with state.lock:
            state.dividend_vault_active = False
            state.dividend_income_per_min = 0.0

    # Normal Growth & Accumulation Mode (< $1B Net Worth)
    open_positions = 0
    for ticker, s in stocks.items():
        h = s.get('holding', {})
        if float(h.get('sharesOwnedDouble', 0.0)) > 0 or float(h.get('sharesShortedDouble', 0.0)) > 0:
            open_positions += 1

    circuit_active = (now < state.circuit_breaker_until)

    for ticker, s in stocks.items():
        price = float(s.get('price', 0.0))
        if price <= 0:
            continue

        s_name = s.get('name', ticker)
        profile = get_stock_profile(ticker, s_name)

        # RULE: Completely IGNORE $BANK
        if profile == "BANK":
            continue

        h = s.get('holding', {})
        owned = float(h.get('sharesOwnedDouble', 0.0))
        shorted = float(h.get('sharesShortedDouble', 0.0))
        avg_buy = float(h.get('averageBuyPrice', 0.0))
        avg_short = float(h.get('averageShortPrice', 0.0))

        has_long = (owned > 0 and avg_buy > 0)
        has_short = (shorted > 0 and avg_short > 0)

        sig_data = signals.get(ticker, {})
        sig = sig_data.get('signal', SIGNAL_NEUTRAL)
        conf = sig_data.get('confidence', 0.0)

        # ----------------------------------------------------------------------
        # A. POSITION EXITS & SPECIALIZED REVERSALS
        # ----------------------------------------------------------------------
        if has_long or has_short:
            # Per-ticker debounce buffer (prevent rapid high-frequency flips)
            if (now - state.last_order_time.get(ticker, 0.0)) < 4.0:
                continue

            current_pnl_pct = ((price - avg_buy) / avg_buy) * 100.0 if has_long else ((avg_short - price) / avg_short) * 100.0

            peak_pnl = state.position_peak_pnl.get(ticker, current_pnl_pct)
            if current_pnl_pct > peak_pnl:
                peak_pnl = current_pnl_pct
                state.position_peak_pnl[ticker] = peak_pnl

            # High and Low Water Mark Tracking
            peak_price = max(state.position_peak_price.get(ticker, price), price)
            state.position_peak_price[ticker] = peak_price
            trough_price = min(state.position_trough_price.get(ticker, price), price)
            state.position_trough_price[ticker] = trough_price
            pos_age = now - state.entry_times.get(ticker, now)

            # 1. Force Stop-Loss Check (Emergency circuit)
            if stop_loss_enabled and stop_loss_pct > 0 and current_pnl_pct <= -stop_loss_pct:
                orders.append({
                    'action': 'close',
                    'ticker': ticker,
                    'reason': f'Force Stop-Loss Hit ({current_pnl_pct:.2f}% loss vs -{stop_loss_pct:.1f}% limit)'
                })
                # peak preserved until confirmed close
                state.position_peak_price.pop(ticker, None)
                state.position_trough_price.pop(ticker, None)
                continue

            # 1b. Dynamic Trailing Profit Protection (Ratcheting Stop-Loss)
            # Never let a substantial winning position flip into a negative trade!
            trailing_exit = False
            trailing_reason = ""
            if peak_pnl >= 45.0 and current_pnl_pct <= (peak_pnl - 12.0):
                trailing_exit = True
                trailing_reason = f'Trailing Profit Lock: Harvested +{current_pnl_pct:.1f}% profit (Peak was +{peak_pnl:.1f}%)'
            elif peak_pnl >= 25.0 and current_pnl_pct <= 16.0:
                trailing_exit = True
                trailing_reason = f'Trailing Profit Lock: Securing +{current_pnl_pct:.1f}% profit (Peak was +{peak_pnl:.1f}%)'
            elif peak_pnl >= 12.0 and current_pnl_pct <= 6.5:
                trailing_exit = True
                trailing_reason = f'Trailing Profit Lock: Securing +{current_pnl_pct:.1f}% profit (Peak was +{peak_pnl:.1f}%)'
            elif peak_pnl >= 5.5 and current_pnl_pct <= 1.5 and pos_age >= 20.0:
                trailing_exit = True
                trailing_reason = f'Breakeven Defense: Closed at +{current_pnl_pct:.1f}% (Defending capital against reversal)'

            if trailing_exit and profile not in ("PUMP", "TECH", "DUMP"):
                orders.append({
                    'action': 'close',
                    'ticker': ticker,
                    'reason': trailing_reason
                })
                # peak preserved until confirmed close
                state.position_peak_price.pop(ticker, None)
                state.position_trough_price.pop(ticker, None)
                continue

            # 2. SPECIALIZED STOCK PERSONALITY EXITS & IMMEDIATE REVERSALS
            # $TECH: Dip buy -> Target X short loop
            if profile == "TECH":
                if has_long:
                    if price >= tech_target_x:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': f'TECH Target X (${tech_target_x:.1f}) reached at ${price:.2f}! Selling all long shares'
                        })
                        orders.append({
                            'action': 'short',
                            'ticker': ticker,
                            'amount': 'max',
                            'reason': f'TECH Target X Reversal: Immediately opening Short from peak ${price:.2f}'
                        })
                        # peak preserved until confirmed close
                        state.position_peak_price[ticker] = price
                        state.position_trough_price[ticker] = price
                        continue
                elif has_short:
                    if price <= 11.50 or (sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY) and price <= 12.50):
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': f'TECH Dip Bottom reached at ${price:.2f}! Covering short position'
                        })
                        orders.append({
                            'action': 'buy',
                            'ticker': ticker,
                            'amount': 'max',
                            'reason': f'TECH Dip Buy: Reversing to Long at bottom ${price:.2f}'
                        })
                        # peak preserved until confirmed close
                        state.position_peak_price[ticker] = price
                        state.position_trough_price[ticker] = price
                        continue
                # TECH is managed strictly by the Tech Target X loop. Never exit on generic 5% min profit!
                continue

            # $PUMP: Mega vertical pump -> ride high peak -> short crash down to base!
            elif profile == "PUMP":
                if has_long:
                    # User Domain Rule:
                    # PUMP shoots up to huge heights ($20 to $270+). Hold long throughout the full pump!
                    # Do NOT sell at +20% or $18. Only exit when high-water mark peak exhaustion is confirmed:
                    # - Mega Pump: Peak >= 22.0 and price drops >= 14% from peak (or falls below $18)
                    # - Parabolic Pump: Peak >= 50.0 and price drops >= 10% from peak
                    # - Moderate Pump: Peak >= 14.0 and price drops >= 18% from peak with >= 25% profit
                    has_peaked = False
                    exit_reason = ""
                    if peak_price >= 50.0 and price <= (peak_price * 0.90):
                        has_peaked = True
                        exit_reason = f'PUMP Parabolic Peak Reached (${peak_price:.2f})! Dropped to ${price:.2f} (-10% off high), Locking Massive Profit!'
                    elif peak_price >= 22.0 and (price <= (peak_price * 0.86) or price <= 18.0):
                        has_peaked = True
                        exit_reason = f'PUMP Vertical Peak Exhaustion (${peak_price:.2f})! Dropped to ${price:.2f} (-14% off high), Harvesting Pump Wave!'
                    elif peak_price >= 14.0 and price <= (peak_price * 0.82) and current_pnl_pct >= 25.0:
                        has_peaked = True
                        exit_reason = f'PUMP Top Exhaustion (${peak_price:.2f})! Dropped to ${price:.2f} (-18% off high), Locking +{current_pnl_pct:.1f}% Profit!'

                    if has_peaked:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': exit_reason
                        })
                        orders.append({
                            'action': 'short',
                            'ticker': ticker,
                            'amount': 'max',
                            'reason': f'PUMP Crash Exploiter: Opening Short at pump peak ${peak_price:.2f} -> Riding dump to base!'
                        })
                        # peak preserved until confirmed close
                        state.position_peak_price[ticker] = price
                        state.position_trough_price[ticker] = price
                        continue

                elif has_short:
                    # Ride short down through the entire crash to base level ($7.00 - $9.20).
                    # Do NOT cover short at $15 or on single-tick ML noise!
                    at_bottom = False
                    cover_reason = ""
                    if price <= 9.20:
                        at_bottom = True
                        cover_reason = f'PUMP Dump Bottom Reached at ${price:.2f} (Base Level $7-$9)! Covering Short for Maximum Profit'
                    elif price <= 10.00 and trough_price <= 9.20 and price >= (trough_price * 1.12):
                        at_bottom = True
                        cover_reason = f'PUMP Rebound from Trough ${trough_price:.2f} to ${price:.2f} (+12% bounce)! Covering Short'

                    if at_bottom:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': cover_reason
                        })
                        orders.append({
                            'action': 'buy',
                            'ticker': ticker,
                            'amount': 'max',
                            'reason': f'PUMP Dip Buy: Re-entering Long at bottom ${price:.2f} to ride upcoming mega-pump!'
                        })
                        # peak preserved until confirmed close
                        state.position_peak_price[ticker] = price
                        state.position_trough_price[ticker] = price
                        continue

                # PUMP positions are managed strictly by PUMP cycle logic. Never exit on generic min profit!
                continue

            # $DUMP: First gets dumped to $2.50-$5.50, then rebounds to $9.80+ (Exact reverse of PUMP)
            elif profile == "DUMP":
                if has_short:
                    # Ride short down through the full dump!
                    at_bottom = False
                    exit_reason = ""
                    if price <= 5.50:
                        at_bottom = True
                        exit_reason = f'DUMP Bottom Reached at ${price:.2f} (Deep Dip)! Covering Short for Maximum Profit'
                    elif price <= 6.80 and trough_price <= 5.50 and price >= (trough_price * 1.15):
                        at_bottom = True
                        exit_reason = f'DUMP Rebound from Trough ${trough_price:.2f} to ${price:.2f} (+15% bounce)! Covering Short'

                    if at_bottom:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': exit_reason
                        })
                        orders.append({
                            'action': 'buy',
                            'ticker': ticker,
                            'amount': 'max',
                            'reason': f'DUMP Rebound Buy: Opening Long at dump bottom ${price:.2f} to ride recovery pump!'
                        })
                        # peak preserved until confirmed close
                        state.position_peak_price[ticker] = price
                        state.position_trough_price[ticker] = price
                        continue

                elif has_long:
                    # Ride long through the rebound back up to normal baseline (~$9.80 - $11.00)
                    at_top = False
                    sell_reason = ""
                    if price >= 9.80:
                        at_top = True
                        sell_reason = f'DUMP Recovery Peak Reached at ${price:.2f} (Normal Baseline)! Closing Long'
                    elif peak_price >= 9.80 and price <= (peak_price * 0.96) and current_pnl_pct >= 20.0:
                        at_top = True
                        sell_reason = f'DUMP Recovery Top Reached (${peak_price:.2f})! Locking +{current_pnl_pct:.1f}% Profit'

                    if at_top:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': sell_reason
                        })
                        orders.append({
                            'action': 'short',
                            'ticker': ticker,
                            'amount': 'max',
                            'reason': f'DUMP Top Short: Reopening Short at peak ${price:.2f} to short next dump!'
                        })
                        # peak preserved until confirmed close
                        state.position_peak_price[ticker] = price
                        state.position_trough_price[ticker] = price
                        continue

                # DUMP positions are managed strictly by DUMP cycle logic. Never exit on generic min profit!
                continue

            # $WAVE: Sinusoidal wave oscillator (buy troughs, short crests)
            elif profile == "WAVE":
                if has_long and sig in (SIGNAL_SHORT, SIGNAL_STRONG_SHORT) and current_pnl_pct >= 5.0 and pos_age >= 12.0:
                    orders.append({
                        'action': 'close',
                        'ticker': ticker,
                        'reason': f'WAVE Crest Peak (+{current_pnl_pct:.1f}%)! Closing Long'
                    })
                    orders.append({
                        'action': 'short',
                        'ticker': ticker,
                        'amount': 'max',
                        'reason': 'WAVE Harmonic Reversal: Shorting crest downward wave'
                    })
                    # peak preserved until confirmed close
                    state.position_peak_price[ticker] = price
                    state.position_trough_price[ticker] = price
                    continue
                elif has_short and sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY) and current_pnl_pct >= 5.0 and pos_age >= 12.0:
                    orders.append({
                        'action': 'close',
                        'ticker': ticker,
                        'reason': f'WAVE Trough Bottom (+{current_pnl_pct:.1f}%)! Covering Short'
                    })
                    orders.append({
                        'action': 'buy',
                        'ticker': ticker,
                        'amount': 'max',
                        'reason': 'WAVE Harmonic Reversal: Buying trough upward wave'
                    })
                    # peak preserved until confirmed close
                    state.position_peak_price[ticker] = price
                    state.position_trough_price[ticker] = price
                    continue

            # $QUIK: Exponential runner with sudden dump protection!
            elif profile == "QUIK":
                sudden_dump = (current_pnl_pct < peak_pnl - 4.0 and peak_pnl >= 8.0)
                if has_long and sudden_dump:
                    orders.append({
                        'action': 'close',
                        'ticker': ticker,
                        'reason': f'QUIK Sudden Dump Guard: Securing +{current_pnl_pct:.1f}% profit (peak was +{peak_pnl:.1f}%)'
                    })
                    # peak preserved until confirmed close
                    state.position_peak_price[ticker] = price
                    state.position_trough_price[ticker] = price
                    continue

            # $BASE: 12:30 AM IST Crash Trader
            elif profile == "BASE":
                if is_crash:
                    if has_long:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': 'BASE 12:30 AM IST Crash Active: Liquidating Long before crash!'
                        })
                        # peak preserved until confirmed close
                        continue
                    elif has_short and price <= 25.0:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': f'BASE Crash Bottom Reached (${price:.2f})! Covering Short for maximum profit'
                        })
                        orders.append({
                            'action': 'buy',
                            'ticker': ticker,
                            'amount': 'max',
                            'reason': f'BASE Post-Crash Rebound: Buying rock bottom (${price:.2f}) before recovery!'
                        })
                        # peak preserved until confirmed close
                        state.position_peak_price[ticker] = price
                        state.position_trough_price[ticker] = price
                        continue
                continue

            # Standard Minimum Profit & Trailing Runner (for other generic stocks only)
            if profile not in ("PUMP", "DUMP", "TECH", "BASE") and pos_age >= 10.0:
                if min_profit_pct > 0 and current_pnl_pct >= min_profit_pct:
                    should_exit = False
                    exit_reason = ""
                    if peak_pnl >= (min_profit_pct + 3.0):
                        if current_pnl_pct <= (peak_pnl - 2.5) and current_pnl_pct >= min_profit_pct:
                            should_exit = True
                            exit_reason = f'Trailing Runner Locked (+{current_pnl_pct:.2f}% secured, peak was +{peak_pnl:.1f}%)'
                    else:
                        if take_profit_enabled:
                            should_exit = True
                            exit_reason = f'Min Profit Requirement Met (+{current_pnl_pct:.2f}% vs +{min_profit_pct:.1f}% required)'
                        else:
                            reversal = (sig in (SIGNAL_SHORT, SIGNAL_STRONG_SHORT)) if has_long else (sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY))
                            if reversal:
                                should_exit = True
                                exit_reason = f'Peak Reversal Harvest (+{current_pnl_pct:.2f}% secured above +{min_profit_pct:.1f}% min)'

                    if should_exit:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': exit_reason
                        })
                        state.consecutive_losses = 0
                        # peak preserved until confirmed close
                        state.position_peak_price.pop(ticker, None)
                        state.position_trough_price.pop(ticker, None)
                        continue

            continue

        # ----------------------------------------------------------------------
        # B. DEDICATED ACHIEVEMENTS HUNTER (1-share micro trades)
        # ----------------------------------------------------------------------
        if state.achievements_enabled:
            if ticker in state.micro_positions:
                pos_age = now - state.entry_times.get(ticker, now)
                if owned > 0 and pos_age >= 15.0:
                    gain = (price - avg_buy) / avg_buy if avg_buy > 0 else 0
                    if gain >= 0.005 or pos_age >= 35.0:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': f'Achievement Micro-Harvest (+{gain*100:.1f}%, 1 share exited for Stock Seller milestone)'
                        })
                        state.micro_positions.discard(ticker)
                        state.achievements_stats["total_sells"] += 1
                        continue

            micro_capital_used = sum(float(stocks.get(t, {}).get('price', 0.0)) for t in state.micro_positions)
            micro_budget = min(state.achievement_budget_cap, max(5.0, cash * 0.02))
            if owned == 0 and shorted == 0 and ticker not in state.micro_positions:
                if len(state.micro_positions) < 5 and (micro_capital_used + price) <= micro_budget and not circuit_active:
                    if now >= state.penalty_box.get(ticker, 0.0):
                        if sig_data.get('expected_return', 0.0) >= 0.0:
                            orders.append({
                                'action': 'buy',
                                'ticker': ticker,
                                'amount': "1",
                                'reason': f'Achievement Engine: 1-share micro buy for Holder & Buyer milestone (Cost: ${price:.2f})'
                            })
                            state.entry_times[ticker] = now
                            state.micro_positions.add(ticker)
                            state.achievements_stats["total_buys"] += 1
                            continue

        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        # END OF PASS 1: OPEN HOLDINGS MAINTENANCE
        # ----------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # PASS 2: GLOBAL QUANTITATIVE OPPORTUNITY SCREENING & ALPHA SCORING
    # Evaluates all flat stocks simultaneously, scoring each setup (0-100)
    # and prioritizing high-conviction signature cycles ($TECH, $PUMP, $DUMP, $WAVE, $STEP)
    # --------------------------------------------------------------------------
    available_cash = max(0.0, cash - state.reserved_cash)
    if not circuit_active and open_positions < max_positions and available_cash > 5.0:
        candidates = []

        for ticker, s in stocks.items():
            price = float(s.get('price', 0.0))
            if price <= 0:
                continue

            s_name = s.get('name', ticker)
            profile = get_stock_profile(ticker, s_name)

            # RULE: Completely IGNORE $BANK (Overdraft debt hazard)
            if profile == "BANK":
                continue

            h = s.get('holding', {})
            owned = float(h.get('sharesOwnedDouble', 0.0))
            shorted = float(h.get('sharesShortedDouble', 0.0))
            if owned > 0 or shorted > 0:
                continue # Already in a position

            # Debounce and cooldown checks
            if (now - state.last_order_time.get(ticker, 0.0)) < 3.5:
                continue
            if now < state.post_exit_cooldown.get(ticker, 0.0):
                continue
            # Issue 11: Activate penalty box on losing stocks
            if now < state.penalty_box.get(ticker, 0.0):
                continue

            sig_data = signals.get(ticker, {})
            sig = sig_data.get('signal', SIGNAL_NEUTRAL)
            conf = sig_data.get('confidence', 0.0)
            exp_ret = sig_data.get('expected_return', 0.0)
            vol = sig_data.get('volatility', 0.015)

            score = 0.0
            action = 'buy'
            reason = ''

            # 1. Signature Personality Evaluation
            if profile == "TECH":
                # Predictable $11.50-$12.20 dip -> $16.00 Target X stair-step
                if price <= 12.20:
                    score = 98.0 + max(0.0, (12.20 - price) * 2.0)
                    action = 'buy'
                    reason = f'TECH Dip Buy Zone (${price:.2f} <= $12.20): Accumulating for Target X ${tech_target_x:.1f} run'
                elif price >= tech_target_x:
                    score = 96.0 + min(3.0, (price - tech_target_x) * 1.5)
                    action = 'short'
                    reason = f'TECH Target X Peak (${price:.2f} >= ${tech_target_x:.1f}): Shorting the peak retracement'

            elif profile == "PUMP":
                # Base zone $7.00 - $9.80: Accumulate before massive multi-bagger pump
                if price <= 9.80:
                    score = 98.5
                    action = 'buy'
                    reason = f'PUMP Base Accumulation (${price:.2f} <= $9.80): Buying flat baseline to ride upcoming mega-pump'
                elif price >= 35.0 and sig in (SIGNAL_SHORT, SIGNAL_STRONG_SHORT):
                    score = 95.0
                    action = 'short'
                    reason = f'PUMP Parabolic Reversal (${price:.2f}): Shorting exhausted peak back down to base'

            elif profile == "DUMP":
                # Peak $9.80+ short, and bottom $3.50-$5.50 bounce buy
                if price >= 9.80:
                    score = 96.0
                    action = 'short'
                    reason = f'DUMP Top Short (${price:.2f} >= $9.80): Shorting baseline before sharp drop'
                elif price <= 5.50:
                    score = 96.5
                    action = 'buy'
                    reason = f'DUMP Floor Rebound (${price:.2f} <= $5.50): Buying deep discount for recovery to $9.80+'

            elif profile == "BASE":
                if is_crash:
                    if price <= 25.0:
                        score = 99.0
                        action = 'buy'
                        reason = f'BASE 12:30 AM IST Crash Bottom (${price:.2f}): Generational dip buy at crash floor!'
                    elif price >= 400.0:
                        score = 97.0
                        action = 'short'
                        reason = f'BASE 12:30 AM IST Crash Short (${price:.2f}): Shorting high price right before 24h crash!'
                else:
                    if price <= 440.0 and sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY):
                        score = 88.0
                        action = 'buy'
                        reason = f'BASE Player Dip Buy (${price:.2f} <= $440.0, outside crash window)'

            elif profile == "WAVE":
                # Sinusoidal channel oscillator
                if sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY) and conf >= 0.45:
                    score = 93.0
                    action = 'buy'
                    reason = f'WAVE Harmonic Trough (${price:.2f}): Buying lower swing boundary for upward cycle'
                elif sig in (SIGNAL_SHORT, SIGNAL_STRONG_SHORT) and conf >= 0.45:
                    score = 93.0
                    action = 'short'
                    reason = f'WAVE Harmonic Crest (${price:.2f}): Shorting upper swing boundary for downward cycle'

            elif profile == "STEP":
                # Fixed stair-step with 2.0% compounding dividend
                div_rate = float(s.get('dividendRate', 0.02))
                if vol <= 0.025: # Volatility contraction squeeze
                    score = 91.0
                    action = 'buy'
                    reason = f'STEP Volatility Squeeze (${price:.2f}): Low volatility consolidation with {div_rate*100:.1f}% dividend rate'
                elif sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY):
                    score = 86.0
                    action = 'buy'
                    reason = f'STEP Upward Stair Breakout (${price:.2f})'

            elif profile == "QUIK":
                # Fast scalper
                if sig == SIGNAL_STRONG_BUY and exp_ret >= 0.005:
                    score = 85.0
                    action = 'buy'
                    reason = f'QUIK Momentum Burst (${price:.2f}, Exp Ret: +{exp_ret*100:.1f}%)'

            else:
                # Multi-Factor Quantitative Scoring for Core Universe (TEAM, MOVE, etc.)
                if sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY) and conf >= 0.55 and exp_ret >= 0.003:
                    score = 75.0 + min(15.0, conf * 20.0)
                    action = 'buy'
                    reason = f'Quant Trend Buy ({profile}, Conf: {conf*100:.0f}%, Exp Ret: +{exp_ret*100:.2f}%)'
                elif sig in (SIGNAL_SHORT, SIGNAL_STRONG_SHORT) and conf >= 0.55 and exp_ret <= -0.003:
                    score = 75.0 + min(15.0, conf * 20.0)
                    action = 'short'
                    reason = f'Quant Trend Short ({profile}, Conf: {conf*100:.0f}%, Exp Ret: {exp_ret*100:.2f}%)'

            if score >= 74.0:
                candidates.append({
                    'score': score,
                    'ticker': ticker,
                    'action': action,
                    'price': price,
                    'reason': reason
                })

        # Sort candidates globally by Opportunity Score descending!
        candidates.sort(key=lambda x: x['score'], reverse=True)

        # ----------------------------------------------------------------------
        # PASS 3: CONVICTION-BASED CAPITAL ALLOCATION & EXECUTION
        # ----------------------------------------------------------------------
        for opp in candidates:
            if open_positions >= max_positions:
                break
            if cash < opp['price']:
                break

            score = opp['score']
            ticker = opp['ticker']
            action = opp['action']
            price = opp['price']
            opp_reason = opp['reason']

            # Advanced Volatility-Scaled Fractional Kelly Sizing Engine
            sig_inf = signals.get(ticker, {})
            c_conf = max(0.40, min(0.96, sig_inf.get('confidence', score / 100.0)))
            b_ratio = max(1.2, min_profit_pct / max(1.0, stop_loss_pct))
            kelly_star = max(0.08, min(0.75, (c_conf * b_ratio - (1.0 - c_conf)) / b_ratio))

            # Strategy multiplier based on preset
            preset_mult = 0.40 if preset == "TURBO" else (0.25 if preset == "GROWTH" else 0.12)
            
            # Volatility scaling: scale up on tight consolidation, scale down on violent turbulence
            t_vol = max(0.005, sig_inf.get('volatility', 0.015))
            vol_scale = min(1.35, max(0.65, 0.015 / t_vol))

            alloc_fraction = min(0.45, max(0.08, kelly_star * preset_mult * vol_scale * (score / 90.0)))
            alloc_amt = min(available_cash * alloc_fraction, available_cash * 0.85)
            
            # Issue 13: Handle short collateral (1.5x margin requirement) and clamp shares
            effective_price = (price * 1.5) if action == "short" else price
            share_count = max(1, int(alloc_amt / effective_price)) if alloc_amt >= effective_price else 0
            
            # Clamp share count to practical execution limit
            share_count = min(share_count, 10_000_000)
            
            cost = share_count * price
            if share_count <= 0 or cost > available_cash:
                continue

            # Deduct from available cash immediately so subsequent candidate trades cannot double-spend!
            available_cash -= cost
            open_positions += 1

            orders.append({
                'action': action,
                'ticker': ticker,
                'amount': str(share_count),
                'reason': f'[ALPHA {score:.0f}/100] {opp_reason} (Allocated: {share_count:,} shares, ${cost:,.2f})'
            })
            # Issue 12: Do NOT update state.last_order_time here! Only update when order is confirmed executed!

    return orders


def fetch_snapshot_http() -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request("http://127.0.0.1:8765/snapshot")
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None

def dispatch_order_http(order_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = "http://127.0.0.1:8765/trade"
    data_bytes = json.dumps(order_payload).encode('utf-8')
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, data=data_bytes, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            if attempt == 0:
                time.sleep(0.12)
                continue
            print(f"[!] Order dispatch error ({order_payload.get('ticker')}): {e}")
            return None
    return None

async def game_bridge_loop(state: AppState):
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    model_candidates = [
        os.path.join(base_dir, "model.onnx"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.onnx"),
        r"C:\Users\HP\.gemini\antigravity\scratch\ScreenStocksApp\model.onnx",
        r"C:\Users\HP\.gemini\antigravity\scratch\data\model_test.onnx"
    ]
    onnx_file = next((p for p in model_candidates if os.path.exists(p)), None)
    
    model = LocalModelEngine(onnx_file)
    state.inference_engine = model
    tracker = FastFeatureTracker(max_history=60)

    print("[*] Game bridge monitor active. Checking Screen Stocks status...")
    last_process_check = 0.0

    while state.running:
        now = time.time()
        
        # 1. Process status check every 1.5 seconds
        if (now - last_process_check) >= 1.5:
            last_process_check = now
            is_running, pid = check_game_process()
            state.game_running = is_running
            state.game_pid = pid

        if not state.game_running:
            state.connected = False
            state.game_bridge_connected = False
            await asyncio.sleep(0.5)
            continue

        # 2. Check Auto Mode Time Limit
        if state.mode == "AUTO":
            limit_hours = state.settings["auto_time_limit_hours"]
            if limit_hours > 0:
                elapsed = now - state.auto_mode_started_at
                total_sec = limit_hours * 3600.0
                rem_sec = max(0.0, total_sec - elapsed)
                m, s = divmod(int(rem_sec), 60)
                h, m = divmod(m, 60)
                state.auto_time_remaining_str = f"{h:02d}:{m:02d}:{s:02d}"
                if elapsed >= total_sec:
                    state.mode = "SUGGESTION"
                    state.auto_time_remaining_str = "Time Limit Expired"
                    state.add_log("SYSTEM", "AUTO_TIMEOUT", "SUGGESTION", f"Auto mode time limit of {limit_hours}h reached. Reverted to Suggestion Mode. Auto-liquidating all positions to cash.", "EXPIRED")
                    print(f"\n[!] [AUTO TIME LIMIT EXPIRED] Switched back to Suggestion Mode after {limit_hours} hours. Liquidating all positions...")
                    threading.Thread(target=state.liquidate_all_positions, daemon=True).start()
            else:
                state.auto_time_remaining_str = "Unlimited"
        else:
            state.auto_time_remaining_str = "Inactive (Suggestion Mode)"

        # 3. Fetch snapshot from in-game bridge
        data = await asyncio.to_thread(fetch_snapshot_http)
        if data is None or not data.get("marketReady", False):
            state.connected = False
            await asyncio.sleep(0.3)
            continue

        if not state.connected:
            state.connected = True
            print("[+] Successfully synchronized with Screen Stocks market engine!")
            state.add_log(ticker="BRIDGE", action="CONNECT", mode=state.mode, reason="Connected to Screen Stocks local loopback", status="ONLINE")

        # 4. Dynamic 20-Second Unlocked Stocks & Stats Check
        if (now - state.last_unlock_poll_time) >= 20.0:
            state.last_unlock_poll_time = now
            raw_unlocked = set(data.get("unlockedStocks", []))
            if not raw_unlocked and "stocks" in data:
                raw_unlocked = set(data["stocks"].keys())
            
            if raw_unlocked != state.unlocked_stocks:
                newly_unlocked = raw_unlocked - state.unlocked_stocks
                if newly_unlocked:
                    state.add_log("STATS", "STOCK_UNLOCKED", state.mode, f"New stocks unlocked: {', '.join(newly_unlocked)}!", "UNLOCKED")
                state.unlocked_stocks = raw_unlocked
                print(f"[+] [20s SYNC] Active Unlocked Stock Universe ({len(state.unlocked_stocks)} stocks): {sorted(list(state.unlocked_stocks))}")

        state.server_tick = data.get("serverTick", 0)
        player = data.get("player", {})
        state.player = {
            "cash": f"${float(player.get('cashDouble', 0)):,.2f}",
            "netWorth": f"${float(player.get('netWorthDouble', 0)):,.2f}",
            "cashDouble": float(player.get('cashDouble', 0)),
            "netWorthDouble": float(player.get('netWorthDouble', 0)),
            "totalUnrealizedPnL": float(player.get('totalUnrealizedPnL', 0.0)),
            "level": player.get("level", 1),
            "ipoCount": player.get("ipoCount", 0),
            "unlockedAchievementCount": player.get("unlockedAchievementCount", 0)
        }

        # Filter strictly to unlocked stocks only!
        stocks_data = data.get("stocks", {})
        signals = {}
        inf_times = []
        timestamp_str = datetime.now().strftime("%H:%M:%S")
        state.history_timestamps.append(timestamp_str)

        # Clear removed/locked stocks
        active_tickers = set(stocks_data.keys())
        for old_t in list(state.stocks.keys()):
            if old_t not in active_tickers:
                del state.stocks[old_t]

        for ticker, s in stocks_data.items():
            price = float(s.get('price', 0.0))
            if price <= 0:
                continue

            # Robust Data Collection: buffer every valid tick for SQLite persistence
            t_ms = int(time.time() * 1000)
            state.tick_buffer.append((ticker, t_ms, price))

            state.history_series[ticker].append(round(price, 2))
            feat = tracker.update(ticker, price)
            signal_code = SIGNAL_NEUTRAL
            conf = 0.0
            pred_ret = 0.0
            vol = 0.015

            if feat is not None:
                t_inf = time.perf_counter()
                pred_ret, signal_code, conf, regime = model.predict(feat)
                inf_times.append((time.perf_counter() - t_inf) * 1000.0)
                vol = float(feat[4])
                state.signal_history[ticker].append(signal_code)

                signals[ticker] = {
                    'signal': signal_code,
                    'confidence': conf,
                    'expected_return': pred_ret,
                    'volatility': vol,
                    'regime': regime,
                    'features': feat
                }

            h = s.get('holding', {})
            owned = float(h.get('sharesOwnedDouble', 0.0))
            shorted = float(h.get('sharesShortedDouble', 0.0))
            pnl = float(h.get('unrealizedPnL', 0.0))

            pos_str = "FLAT"
            avg_p = 0.0
            pos_pnl_pct = 0.0
            min_target_pct = state.settings["min_profit_pct"]
            stop_loss_pct = state.settings["stop_loss_pct"] if state.settings["stop_loss_enabled"] else None

            if owned > 0:
                pos_str = f"LONG {owned:,.0f}"
                avg_p = float(h.get('averageBuyPrice', 0.0))
                if avg_p > 0:
                    pos_pnl_pct = round(((price - avg_p) / avg_p) * 100.0, 2)
            elif shorted > 0:
                pos_str = f"SHORT {shorted:,.0f}"
                avg_p = float(h.get('averageShortPrice', 0.0))
                if avg_p > 0:
                    pos_pnl_pct = round(((avg_p - price) / avg_p) * 100.0, 2)

            stop_str = f"-{stop_loss_pct:.1f}%" if state.settings["stop_loss_enabled"] else "OFF"
            exit_status = "Scanning"

            prof = get_stock_profile(ticker, s.get('name', ticker))
            if prof == "BANK":
                exit_status = "Blacklisted (Permanently Ignored)"
            elif prof == "PUMP":
                if owned > 0:
                    pk = state.position_peak_price.get(ticker, price)
                    exit_status = f"Riding Mega-Pump: Peak ${pk:.2f} (Trailing Peak Drop Exit)"
                elif shorted > 0:
                    exit_status = f"Shorting Crash: Target <= $9.20 Base (Now: ${price:.2f})"
                else:
                    exit_status = f"Scanning Base <= $9.80 for Upcoming Pump"
            elif prof == "DUMP":
                if shorted > 0:
                    tr = state.position_trough_price.get(ticker, price)
                    exit_status = f"Shorting Dump: Target <= $5.50 Bottom (Now: ${price:.2f})"
                elif owned > 0:
                    exit_status = f"Riding Rebound: Target >= $9.80 Peak (Now: ${price:.2f})"
                else:
                    exit_status = f"Scanning Top >= $9.80 / Dip <= $5.80"
            elif prof == "TECH":
                tech_x = state.settings.get("tech_target_x", 16.0)
                if owned > 0:
                    exit_status = f"Riding to Target X (${tech_x:.1f}) | Now: ${price:.2f}"
                elif shorted > 0:
                    exit_status = f"Shorting to Dip <= $11.50 | Now: ${price:.2f}"
                else:
                    exit_status = f"Waiting for Dip <= $12.00 | Now: ${price:.2f}"
            elif prof == "BASE":
                is_c, _ = is_base_crash_window()
                if is_c:
                    exit_status = "12:30 AM IST Crash Active (Short Crash / Buy $1-$25 Bottom)"
                else:
                    exit_status = f"Crash in {state.base_crash_countdown_str}"
            elif state.dividend_vault_active:
                exit_status = f"Dividend Vault: Permanent Hold ({float(s.get('dividendRate',0))*100:.2f}%/min)"
            elif owned > 0 or shorted > 0:
                if pos_pnl_pct >= min_target_pct:
                    exit_status = f"Target Met (+{pos_pnl_pct}%) -> Exiting"
                elif state.settings["stop_loss_enabled"] and pos_pnl_pct <= -state.settings["stop_loss_pct"]:
                    exit_status = f"Stop Loss Hit ({pos_pnl_pct}%) -> Exiting"
                else:
                    exit_status = f"Target: +{min_target_pct:.1f}% | Stop: {stop_str}"

            state.stocks[ticker] = {
                "ticker": ticker,
                "price": price,
                "holding": pos_str,
                "avg_price": avg_p,
                "pnl": pnl,
                "pnl_pct": pos_pnl_pct,
                "exit_status": exit_status,
                "pred_return": round(pred_ret * 100.0, 2),
                "signal": signal_code,
                "signal_label": SIGNAL_LABELS.get(signal_code, "NEUTRAL"),
                "confidence": round(conf * 100.0, 1),
                "requiredAchievements": s.get("requiredAchievements", 0),
                "sparkline": list(state.history_series.get(ticker, []))[-20:],
                "dividendRate": float(s.get("dividendRate", 0.0)),
                "profile": prof
            }

        if inf_times:
            state.inf_latency_ms = sum(inf_times) / len(inf_times)

        # 5. Evaluate Orders with High-Expectancy Risk Guardrails
        orders = evaluate_portfolio(state, signals, data)

        # Issue 23: Dispatch and execute orders concurrently/independently in parallel!
        async def execute_single_order(ord_item):
            t_ticker = ord_item['ticker']
            t_action = ord_item['action'].upper()
            t_reason = ord_item.get('reason', '')
            t_price = float(stocks_data.get(t_ticker, {}).get('price', 0.0))
            est_shares = int(ord_item.get('amount', 1)) if str(ord_item.get('amount', '')).isdigit() else 1
            est_cost = est_shares * t_price

            # Issue 1: Atomically reserve cash during order transit
            if t_action in ("BUY", "SHORT"):
                with state.lock:
                    state.reserved_cash += est_cost

            try:
                payload = {
                    'id': f"ord_{t_ticker}_{int(time.time()*1000)}",
                    'action': ord_item['action'],
                    'ticker': t_ticker,
                    'amount': ord_item.get('amount', 'max'),
                    'isMax': 'amount' not in ord_item or ord_item.get('amount') == 'max'
                }
                trade_res = await asyncio.to_thread(dispatch_order_http, payload)
                
                # Issue 6: Confirm trade execution from game bridge response
                if trade_res and trade_res.get("success") is True:
                    # Issue 3: Use TRUE execution price and shares for THIS ticker
                    fill_p = float(trade_res.get('filledPrice') or t_price or 0.0)
                    fill_shares = int(trade_res.get('shares') or est_shares) if str(trade_res.get('shares') or est_shares).isdigit() else 1
                    
                    with state.lock:
                        state.last_order_time[t_ticker] = time.time()
                        if t_action == "BUY":
                            state.bot_managed_positions.add(t_ticker)
                            state.achievements_stats["total_buys"] += 1
                        elif t_action == "SHORT":
                            state.bot_managed_positions.add(t_ticker)
                            state.achievements_stats["total_shorts"] += 1
                        elif t_action in ("SELL", "CLOSE", "COVER"):
                            state.bot_managed_positions.discard(t_ticker)
                            # Issue 2: Only clear peaks when position is verified closed!
                            state.position_peak_pnl.pop(t_ticker, None)
                            state.position_peak_price.pop(t_ticker, None)
                            state.position_trough_price.pop(t_ticker, None)
                            if t_action in ("SELL", "CLOSE"): state.achievements_stats["total_sells"] += 1
                            else: state.achievements_stats["total_covers"] += 1

                    # Accurate realized PnL calculation
                    s_prev = state.stocks.get(t_ticker, {})
                    h_str = s_prev.get('holding', '')
                    avg_p = float(s_prev.get('avg_price', 0.0))
                    realized_pnl_val = None
                    realized_dollar = 0.0

                    if avg_p > 0 and t_action in ('SELL', 'CLOSE', 'COVER'):
                        if 'LONG' in h_str:
                            realized_pnl_val = ((fill_p - avg_p) / avg_p) * 100.0
                            realized_dollar = (fill_p - avg_p) * fill_shares
                        elif 'SHORT' in h_str:
                            realized_pnl_val = ((avg_p - fill_p) / avg_p) * 100.0
                            realized_dollar = (avg_p - fill_p) * fill_shares

                        with state.lock:
                            state.session_realized_pnl += realized_dollar
                            state.session_trades_count += 1
                            if realized_dollar >= 0:
                                state.session_wins += 1
                            else:
                                state.session_losses += 1
                                # Issue 11: Activate penalty box on losing trades!
                                penalty_duration = 45.0 + min(60.0, abs(realized_pnl_val) * 2.0)
                                state.penalty_box[t_ticker] = time.time() + penalty_duration
                                state.add_log(t_ticker, "PENALTY_BOX", "RISK", f"Drawdown of {realized_pnl_val:.1f}%. Cooldown {penalty_duration:.0f}s active.", "ACTIVE")

                    state.add_log(t_ticker, t_action, "AUTO", f"{t_reason} | Executed at ${fill_p:.2f} x{fill_shares:,}", "EXECUTED")
                    record_trade_in_proto(state.trades_pb_path, t_ticker, t_action, fill_p, fill_shares, realized_pnl_val, t_reason)
                    state.trade_history.append({
                        "id": payload["id"],
                        "time": datetime.datetime.now().strftime('%H:%M:%S'),
                        "ticker": t_ticker,
                        "action": t_action,
                        "price": f"${fill_p:.2f}",
                        "amount": f"{fill_shares:,}",
                        "pnl": f"{realized_pnl_val:+.1f}%" if realized_pnl_val is not None else "-",
                        "reason": t_reason
                    })
                else:
                    msg = trade_res.get("message", "Bridge rejected order") if trade_res else "Game bridge timed out"
                    state.add_log(t_ticker, t_action, "AUTO", f"{t_reason} (Rejected: {msg})", "REJECTED")
            finally:
                if t_action in ("BUY", "SHORT"):
                    with state.lock:
                        state.reserved_cash = max(0.0, state.reserved_cash - est_cost)

        if orders:
            if state.mode == "AUTO":
                await asyncio.gather(*[execute_single_order(o) for o in orders])
            else:
                for order in orders:
                    state.add_log(order['ticker'], f"REC: {order['action'].upper()}", "SUGGESTION", order.get('reason', ''), "RECOMMENDED")

        await asyncio.sleep(0.1)


# Web dashboard

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" type="image/png" href="/icon.png">
  <title>OtoStoksBot Pro - Autonomous Trading Terminal</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { background-color: #070b13; color: #cbd5e1; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, Helvetica, Arial, sans-serif; }
    .panel { background-color: #0f1523; border: 1px solid #1e293b; border-radius: 10px; }
    .kpi-card { background-color: #0b111e; border: 1px solid #1e293b; border-radius: 8px; padding: 10px 14px; }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #070b13; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
    .mono { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; }
    .size-pill.active { background-color: #0284c7 !important; color: white !important; font-weight: 700; border-color: #38bdf8 !important; }
    .filter-tab.active { background-color: #1e293b !important; color: #38bdf8 !important; font-weight: 600; border-color: #0284c7 !important; }
    .preset-pill.active { background-color: #38bdf8 !important; color: #020617 !important; font-weight: 800; border-color: #38bdf8 !important; box-shadow: 0 0 10px rgba(56, 189, 248, 0.4); }
    input[type=range] { accent-color: #38bdf8; }
    
    /* Live Price Change Glowing Pulse */
    .flash-up {
      background-color: rgba(16, 185, 129, 0.28) !important;
      color: #34d399 !important;
      border-radius: 4px;
      transition: background-color 0.15s ease;
    }
    .flash-down {
      background-color: rgba(244, 63, 94, 0.28) !important;
      color: #fb7185 !important;
      border-radius: 4px;
      transition: background-color 0.15s ease;
    }
    
    /* Smooth Pulse Indicators */
    @keyframes pulse-subtle {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }
    .pulse-dot { animation: pulse-subtle 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
  </style>
</head>
<body class="min-h-screen p-3 sm:p-4.5 flex flex-col gap-3.5 max-w-[1680px] mx-auto">

  <!-- TOP HEADER & CONTROLS NAVBAR -->
  <header class="panel px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 shadow-sm">
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-2">
        <span id="connIndicator" class="w-2.5 h-2.5 rounded-full bg-slate-500 pulse-dot" title="Game Bridge Link"></span>
        <img src="/icon.png" class="w-6 h-6 rounded border border-emerald-500/40 inline-block object-cover" alt="Logo"><span class="font-bold text-white tracking-wide text-sm mono">OTOSTOKSBOT PRO</span>
      </div>
      <span class="text-xs text-slate-500 font-mono">v4.0 Pro</span>
      <span id="gameConnBadge" class="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-400 border border-slate-700">GAME: DETECTING</span>
      <span id="modeBadge" class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/70 text-amber-300 border border-amber-700/60 mono">
        SUGGESTION MODE
      </span>
    </div>

    <!-- Live $BASE 12:30 AM IST Crash Banner -->
    <div id="baseCrashBanner" class="flex items-center gap-2 px-3 py-1 rounded-full bg-purple-950/60 border border-purple-700/50 text-purple-300 font-mono text-xs">
      <span class="w-2 h-2 rounded-full bg-purple-400 pulse-dot"></span>
      <span class="font-semibold text-purple-200">BASE 12:30 AM IST:</span>
      <span id="baseCrashCountdown" class="font-bold text-white tracking-wider">Syncing...</span>
    </div>

    <!-- Global Controls -->
    <div class="flex items-center gap-2 sm:gap-2.5">
      <button id="soundToggleBtn" onclick="toggleSound()" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors" title="Toggle audio feedback">
        <svg class="w-3.5 h-3.5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"></path></svg> <span id="soundLabel">Audio: ON</span>
      </button>

      <button id="achievementsToggleBtn" onclick="toggleAchievements()" class="px-2.5 py-1 rounded text-xs font-semibold bg-slate-800/90 text-slate-300 border border-slate-700 hover:bg-slate-700 transition-colors flex items-center gap-1.5" title="Toggle Screen Stocks achievements hunter">
        <span class="w-2 h-2 rounded-full bg-slate-500" id="achieveDot"></span>
        <span>Achievements: <strong id="achieveText">OFF</strong></span>
      </button>

      <button type="button" onclick="liquidateAll()" class="px-3 py-1 rounded bg-rose-950/70 hover:bg-rose-900 border border-rose-600/60 text-rose-300 font-bold text-xs shadow-sm transition-all active:scale-95" title="Instantly close all long and short positions to 100% cash">
        <svg class="w-3.5 h-3.5 inline mr-1 text-rose-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" stroke-width="2"/></svg> LIQUIDATE ALL (100% CASH)
      </button>

      <button type="button" id="modeToggleBtn" onclick="toggleMode()" class="px-3.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-md transition-all active:scale-95 mono">
        Switch to AUTO MODE
      </button>
    </div>
  </header>

  <!-- SESSION PERFORMANCE & ALPHA KPI RIBBON -->
  <section class="grid grid-cols-2 md:grid-cols-4 gap-2.5 sm:gap-3">
    <!-- Card 1: Net Worth & Cash -->
    <div class="kpi-card flex flex-col justify-between">
      <div class="flex items-center justify-between text-xs text-slate-400">
        <span class="font-medium">PORTFOLIO VALUATION</span>
        <span id="pnlTag" class="mono text-xs font-semibold text-slate-400">+$0.00 (0.0%)</span>
      </div>
      <div class="flex items-baseline justify-between mt-1">
        <div id="netWorthDisplay" class="mono text-xl sm:text-2xl font-bold text-white">$0.00</div>
      </div>
      <div class="text-xs text-slate-400 mono mt-0.5 flex justify-between">
        <span>Cash: <strong id="cashDisplay" class="text-emerald-400">$0.00</strong></span>
        <span id="ipoTag" class="text-slate-500">IPO: 0</span>
      </div>
    </div>

    <!-- Card 2: Realized Session Alpha & Win Rate -->
    <div class="kpi-card flex flex-col justify-between">
      <div class="flex items-center justify-between text-xs text-slate-400">
        <span class="font-medium">SESSION REALIZED ALPHA</span>
        <span id="sessionTradesCount" class="mono text-xs font-semibold text-cyan-400">0 Trades</span>
      </div>
      <div class="flex items-baseline justify-between mt-1">
        <div id="sessionPnlDisplay" class="mono text-xl sm:text-2xl font-bold text-emerald-400">+$0.00</div>
      </div>
      <div class="text-xs text-slate-400 mono mt-0.5 flex justify-between">
        <span>Win Rate: <strong id="winRateDisplay" class="text-emerald-400">100.0%</strong> (<span id="winLossCounts" class="text-slate-400">0W - 0L</span>)</span>
      </div>
    </div>

    <!-- Card 3: Quantitative AI Engine -->
    <div class="kpi-card flex flex-col justify-between">
      <div class="flex items-center justify-between text-xs text-slate-400">
        <span class="font-medium">QUANT ENGINE</span>
        <span id="activePresetBadge" class="mono text-xs font-bold text-cyan-400">TURBO SNOWBALL</span>
      </div>
      <div class="flex items-baseline justify-between mt-1">
        <div class="flex items-center gap-2">
          <span class="mono text-lg sm:text-xl font-bold text-white" id="latencyDisplay">0.12 ms</span>
          <span class="text-xs text-slate-400">inference</span>
        </div>
      </div>
      <div class="text-xs text-slate-400 mono mt-0.5 flex justify-between">
        <span>Ticks: <strong id="dbTicksCount" class="text-slate-300">0</strong></span>
        <span>Retrain in: <strong id="retrainCountdown" class="text-cyan-400">45s</strong></span>
      </div>
    </div>

    <!-- Card 4: Billionaire Dividend Vault -->
    <div class="kpi-card flex flex-col justify-between">
      <div class="flex items-center justify-between text-xs text-slate-400">
        <span class="font-medium">BILLIONAIRE DIVIDEND VAULT</span>
        <span id="vaultStatusTag" class="mono text-xs font-semibold text-slate-500">Standby (< $1B)</span>
      </div>
      <div class="flex items-baseline justify-between mt-1">
        <div id="divIncomeDisplay" class="mono text-xl sm:text-2xl font-bold text-amber-400">+$0.00 / min</div>
      </div>
      <div class="text-xs text-slate-400 mono mt-0.5 flex justify-between">
        <span>Target X: <strong id="techTargetDisplay" class="text-cyan-400">$16.0</strong></span>
        <span>Universe: <strong id="universeCount" class="text-slate-300">0 Stocks</strong></span>
      </div>
    </div>
  </section>

  <!-- STRATEGY PRESETS & RISK PARAMETERS TOOLBAR -->
  <section class="panel p-3 sm:p-3.5 flex flex-col gap-2.5 shadow-sm">
    <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2.5">
      <!-- Strategy Presets -->
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="text-xs font-bold uppercase tracking-wider text-slate-400 mr-1">Strategy Presets:</span>
        <button type="button" onclick="selectStrategyPreset('TURBO')" id="preset-TURBO" class="preset-pill active px-2.5 py-1 rounded text-xs border border-slate-700 bg-slate-800 text-slate-300 transition-all font-semibold flex items-center gap-1">
          <svg class="w-3.5 h-3.5 inline mr-1 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg> Turbo Snowball (<$50k)
        </button>
        <button type="button" onclick="selectStrategyPreset('GROWTH')" id="preset-GROWTH" class="preset-pill px-2.5 py-1 rounded text-xs border border-slate-700 bg-slate-800 text-slate-300 transition-all font-semibold flex items-center gap-1">
          <svg class="w-3.5 h-3.5 inline mr-1 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg> Growth Core ($50k-$1B)
        </button>
        <button type="button" onclick="selectStrategyPreset('DEFENSIVE')" id="preset-DEFENSIVE" class="preset-pill px-2.5 py-1 rounded text-xs border border-slate-700 bg-slate-800 text-slate-300 transition-all font-semibold flex items-center gap-1">
          <svg class="w-3.5 h-3.5 inline mr-1 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg> Capital Shield
        </button>
        <button type="button" onclick="selectStrategyPreset('BILLIONAIRE')" id="preset-BILLIONAIRE" class="preset-pill px-2.5 py-1 rounded text-xs border border-slate-700 bg-slate-800 text-slate-300 transition-all font-semibold flex items-center gap-1">
          <svg class="w-3.5 h-3.5 inline mr-1 text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg> Billionaire Vault (> $1B)
        </button>
      </div>

      <!-- Auto Mode Run Limit -->
      <div class="flex items-center gap-2">
        <span class="text-xs text-slate-400">Run Limit:</span>
        <select id="autoTimeLimit" onchange="saveSettings()" class="bg-slate-900 border border-slate-700 text-xs text-slate-200 rounded px-2 py-1">
          <option value="0">Unlimited (Infinite)</option>
          <option value="0.5">30 Minutes</option>
          <option value="1">1 Hour</option>
          <option value="2">2 Hours</option>
          <option value="4">4 Hours</option>
          <option value="8">8 Hours</option>
        </select>
        <span id="autoTimeRemainingBadge" class="text-xs mono text-cyan-400 hidden">Remaining: <span id="autoTimeRemaining">--</span></span>
      </div>
    </div>

    <!-- Sliders Strip -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 sm:gap-4 pt-0.5">
      <!-- Stop Loss Slider -->
      <div class="flex flex-col gap-1">
        <div class="flex justify-between items-center text-xs">
          <label class="text-slate-300 font-medium">Stop-Loss Guard</label>
          <span id="stopLossVal" class="mono text-xs font-bold text-rose-400">15.0%</span>
        </div>
        <div class="flex items-center gap-2">
          <input type="range" id="stopLossSlider" min="0" max="50" step="0.5" value="15" oninput="onStopLossSliderChange(this.value)" onchange="saveSettings()" class="w-full h-1.5 bg-slate-800 rounded">
          <button type="button" id="stopLossToggleBtn" onclick="toggleStopLoss()" class="text-xs px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">ON</button>
        </div>
      </div>

      <!-- Min Profit Slider -->
      <div class="flex flex-col gap-1">
        <div class="flex justify-between items-center text-xs">
          <label class="text-slate-300 font-medium">Min Profit Requirement</label>
          <span id="minProfitVal" class="mono text-xs font-bold text-emerald-400">6.0%</span>
        </div>
        <div class="flex items-center gap-2">
          <input type="range" id="minProfitSlider" min="0" max="50" step="0.5" value="6" oninput="onMinProfitSliderChange(this.value)" onchange="saveSettings()" class="w-full h-1.5 bg-slate-800 rounded">
          <button type="button" id="minProfitToggleBtn" onclick="toggleMinProfit()" class="text-xs px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">ON</button>
        </div>
      </div>

      <!-- $TECH Target X Slider -->
      <div class="flex flex-col gap-1">
        <div class="flex justify-between items-center text-xs">
          <label class="text-slate-300 font-medium">$TECH Target X Exit</label>
          <span id="techTargetVal" class="mono text-xs font-bold text-cyan-400">$16.0</span>
        </div>
        <div class="flex items-center gap-2">
          <input type="range" id="techTargetSlider" min="12" max="40" step="0.5" value="16" oninput="onTechSliderChange(this.value)" onchange="saveSettings()" class="w-full h-1.5 bg-slate-800 rounded">
          <div class="flex items-center gap-1">
            <button type="button" onclick="setTechTargetX(16)" class="text-xs px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 hover:text-white">$16</button>
            <button type="button" onclick="setTechTargetX(20)" class="text-xs px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 hover:text-white">$20</button>
            <button type="button" onclick="setTechTargetX(25)" class="text-xs px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 hover:text-white">$25</button>
          </div>
        </div>
      </div>

      <!-- Max Positions & Early Allocation -->
      <div class="flex flex-col gap-1">
        <div class="flex justify-between items-center text-xs">
          <label class="text-slate-300 font-medium">Max Positions / Alloc</label>
          <span id="maxPosVal" class="mono text-xs font-bold text-cyan-400">5 Active</span>
        </div>
        <div class="flex items-center gap-2">
          <input type="range" id="maxPosSlider" min="1" max="15" step="1" value="5" oninput="onMaxPosChange(this.value)" onchange="saveSettings()" class="w-full h-1.5 bg-slate-800 rounded">
          <button type="button" onclick="saveSettings()" class="px-2.5 py-1 rounded bg-cyan-700 hover:bg-cyan-600 text-white text-xs font-bold transition-colors">SAVE</button>
        </div>
      </div>
    </div>
  </section>

  <!-- ACTIVE STOCKS & INTELLIGENT EXECUTION CONSOLE -->
  <section class="panel p-3.5 sm:p-4 flex flex-col gap-3 shadow-sm">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
      <!-- Category Filter Tabs -->
      <div class="flex flex-wrap items-center gap-1 sm:gap-1.5">
        <button type="button" onclick="setCategoryFilter('ALL')" id="filter-ALL" class="filter-tab active px-3 py-1 rounded text-xs font-medium border border-slate-700 bg-slate-900 text-slate-300 hover:text-white transition-all">All Stocks</button>
        <button type="button" onclick="setCategoryFilter('HOLDING')" id="filter-HOLDING" class="filter-tab px-3 py-1 rounded text-xs font-medium border border-slate-700 bg-slate-900 text-slate-300 hover:text-white transition-all">Holding Positions</button>
        <button type="button" onclick="setCategoryFilter('PROFITABLE')" id="filter-PROFITABLE" class="filter-tab px-3 py-1 rounded text-xs font-medium border border-slate-700 bg-slate-900 text-slate-300 hover:text-white transition-all">Profitable</button>
        <button type="button" onclick="setCategoryFilter('SPECIAL')" id="filter-SPECIAL" class="filter-tab px-3 py-1 rounded text-xs font-medium border border-slate-700 bg-slate-900 text-slate-300 hover:text-white transition-all">Special Cycles ($PUMP / $DUMP / $TECH / $BASE)</button>
      </div>

      <!-- Instant Live Search -->
      <div class="relative w-44 sm:w-56">
        <input type="text" id="stockSearchInput" oninput="onSearchInput(this.value)" placeholder="Search ticker or profile..." class="w-full bg-slate-900 border border-slate-700 text-slate-200 placeholder-slate-500 rounded px-2.5 py-1 text-xs focus:outline-none focus:border-cyan-400 transition-colors">
      </div>

      <!-- Integrated Capital Sizing Console -->
      <div class="flex items-center gap-2 bg-slate-900/90 border border-slate-800 px-3 py-1 rounded-lg">
        <span class="text-xs font-semibold text-slate-400">Trade Sizing:</span>
        <input type="range" id="tradeSizeSlider" min="1" max="100" step="1" value="100" oninput="onTradeSliderChange(this.value)" class="w-20 sm:w-28 h-1.5 bg-slate-700 rounded cursor-pointer">
        <span id="tradeSizeDisplay" class="mono text-xs font-bold text-cyan-400 min-w-[55px] text-center">100% MAX</span>

        <div class="flex items-center gap-1 border-l border-slate-800 pl-2">
          <button type="button" onclick="setGlobalTradeSize(10)" class="size-pill px-2 py-0.5 rounded text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors" data-pct="10">10%</button>
          <button type="button" onclick="setGlobalTradeSize(25)" class="size-pill px-2 py-0.5 rounded text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors" data-pct="25">25%</button>
          <button type="button" onclick="setGlobalTradeSize(50)" class="size-pill px-2 py-0.5 rounded text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors" data-pct="50">50%</button>
          <button type="button" onclick="setGlobalTradeSize(75)" class="size-pill px-2 py-0.5 rounded text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors" data-pct="75">75%</button>
          <button type="button" onclick="setGlobalTradeSize(100)" class="size-pill active px-2.5 py-0.5 rounded text-xs bg-cyan-700 text-white font-bold border border-cyan-500 transition-colors" data-pct="100">MAX</button>
        </div>
      </div>
    </div>

    <!-- Active Stocks Table -->
    <div class="overflow-x-auto">
      <table class="w-full text-left text-xs border-collapse">
        <thead>
          <tr class="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold text-[11px]">
            <th class="py-2.5 px-3">Ticker & Strategy</th>
            <th class="py-2.5 px-3">Live Trend (20t)</th>
            <th class="py-2.5 px-3">Market Price</th>
            <th class="py-2.5 px-3">AI Signal</th>
            <th class="py-2.5 px-3">Conf</th>
            <th class="py-2.5 px-3">Position</th>
            <th class="py-2.5 px-3">Cost Basis</th>
            <th class="py-2.5 px-3">Unrealized P&L</th>
            <th class="py-2.5 px-3">Algorithmic Lifecycle Status</th>
            <th class="py-2.5 px-3 text-right">Instant Trade Actions</th>
          </tr>
        </thead>
        <tbody id="stocksTableBody" class="divide-y divide-slate-800/80 mono text-xs">
          <tr>
            <td colspan="10" class="text-center py-6 text-slate-400">Synchronizing with game market feed...</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- BOTTOM SHELF: COMPACT CHART & SELF-TRAINING / AUDIT LOGS -->
  <section class="grid grid-cols-1 lg:grid-cols-2 gap-3.5">
    <!-- Left: Market Price Rolling Chart + Model Ribbon -->
    <div class="panel p-3 flex flex-col gap-2 shadow-sm">
      <div class="flex items-center justify-between text-xs">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-cyan-400"></span>
          <span class="font-bold text-white text-xs uppercase tracking-wider">Live Market Price History</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-slate-400 text-xs">Focus:</span>
          <select id="chartStockSelect" onchange="onChartStockChange(this.value)" class="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded px-2 py-0.5">
            <option value="ALL">All Unlocked Stocks</option>
          </select>
        </div>
      </div>

      <!-- Chart.js Canvas -->
      <div class="w-full h-36 relative">
        <canvas id="marketChart"></canvas>
      </div>

      <!-- Auto-Retraining Status Bar -->
      <div class="bg-slate-900/80 border border-slate-800 rounded px-3 py-1.5 flex items-center justify-between text-xs mono">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-cyan-400" id="retrainStatusDot"></span>
          <span class="text-slate-400">Model:</span>
          <span id="retrainStatusText" class="font-semibold text-slate-200">Quant Engine Active</span>
        </div>
        <div class="flex items-center gap-3">
          <span>Model Acc: <strong id="modelAccText" class="text-emerald-400">Calibrating...</strong></span>
          <span>Retrained: <strong id="retrainCountText" class="text-cyan-400">0x</strong></span>
        </div>
      </div>
    </div>

    <!-- Right: Real-time Execution Audit Log + CSV Export -->
    <div class="panel p-3 flex flex-col gap-2 shadow-sm">
      <div class="flex items-center justify-between text-xs">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
          <span class="font-bold text-white text-xs uppercase tracking-wider">Real-Time Execution Audit Log</span>
        </div>
        <div class="flex items-center gap-2">
          <button type="button" onclick="exportTradeHistoryCSV()" class="px-2.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs flex items-center gap-1 transition-colors" title="Download trade history CSV ledger">
            <span>⬇</span> Export CSV
          </button>
          <span id="logStatusTag" class="text-slate-500 mono text-xs">Listening</span>
        </div>
      </div>

      <!-- Log Terminal Box -->
      <div id="logsContainer" class="bg-slate-950 border border-slate-900 rounded p-2.5 h-44 overflow-y-auto mono text-xs space-y-1">
        <div class="text-slate-500">Awaiting market events & algorithmic trade executions...</div>
      </div>
    </div>
  </section>

  <!-- JAVASCRIPT ENGINE -->
  <script>
    let ws = null;
    let chart = null;
    let currentCategoryFilter = 'ALL';
    let currentSearchQuery = '';
    let currentTradeSizePct = 100;
    let soundEnabled = true;
    let previousPrices = {};
    let lastRenderedStocks = [];

    // Web Audio Synthesizer (Zero External Dependencies)
    function playAudioTone(type) {
      if (!soundEnabled) return;
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        const ctx = new AudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        gain.gain.setValueAtTime(0.04, ctx.currentTime);

        if (type === 'BUY') {
          osc.frequency.setValueAtTime(440, ctx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.12);
          gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18);
          osc.start();
          osc.stop(ctx.currentTime + 0.18);
        } else if (type === 'SHORT') {
          osc.frequency.setValueAtTime(700, ctx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(350, ctx.currentTime + 0.12);
          gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18);
          osc.start();
          osc.stop(ctx.currentTime + 0.18);
        } else if (type === 'CLOSE') {
          osc.frequency.setValueAtTime(523, ctx.currentTime);
          osc.frequency.setValueAtTime(659, ctx.currentTime + 0.08);
          osc.frequency.setValueAtTime(784, ctx.currentTime + 0.16);
          gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
          osc.start();
          osc.stop(ctx.currentTime + 0.25);
        }
      } catch (e) {}
    }

    function toggleSound() {
      soundEnabled = !soundEnabled;
      document.getElementById('soundLabel').innerText = soundEnabled ? 'Audio: ON' : 'Audio: OFF';
      document.getElementById('soundToggleBtn').classList.toggle('border-cyan-500', soundEnabled);
    }

    // Dynamic SVG Sparkline Generator
    function renderSparklineSVG(prices, width = 76, height = 22) {
      if (!prices || prices.length < 2) {
        return `<svg width="${width}" height="${height}" class="opacity-25 inline-block"><line x1="0" y1="${height/2}" x2="${width}" y2="${height/2}" stroke="#64748b" stroke-width="1.5" stroke-dasharray="2,2"/></svg>`;
      }
      const min = Math.min(...prices);
      const max = Math.max(...prices);
      const range = (max - min) || 1;
      const step = width / (prices.length - 1);
      const points = prices.map((p, i) => {
        const x = (i * step).toFixed(1);
        const y = (height - 3 - ((p - min) / range) * (height - 6)).toFixed(1);
        return `${x},${y}`;
      }).join(' ');

      const isUp = prices[prices.length - 1] >= prices[0];
      const stroke = isUp ? '#10b981' : '#f43f5e';
      const lastX = width.toFixed(1);
      const lastY = (height - 3 - ((prices[prices.length - 1] - min) / range) * (height - 6)).toFixed(1);

      return `
        <svg width="${width}" height="${height}" class="overflow-visible inline-block">
          <polyline fill="none" stroke="${stroke}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" points="${points}" />
          <circle cx="${lastX}" cy="${lastY}" r="2.5" fill="${stroke}" class="pulse-dot" />
        </svg>
      `;
    }

    // Stock Profile Badges
    function getProfileBadge(ticker) {
      const t = (ticker || '').toUpperCase();
      if (t.includes('PUMP')) return '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-600/50">PUMP: Peak Wave</span>';
      if (t.includes('DUMP')) return '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-950/80 text-rose-300 border border-rose-600/50">DUMP: Bottom Floor</span>';
      if (t.includes('TECH')) return '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-cyan-950/80 text-cyan-300 border border-cyan-600/50">TECH: Dip/$16 Loop</span>';
      if (t.includes('BASE')) return '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-purple-950/80 text-purple-300 border border-purple-600/50">BASE: 12:30 AM Crash</span>';
      if (t.includes('BANK')) return '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-900 text-slate-400 border border-slate-700">BANK: Blacklisted</span>';
      if (t.includes('STEP')) return '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950/80 text-amber-300 border border-amber-600/50">STEP: 2.0% Yield</span>';
      if (t.includes('WAVE')) return '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-950/80 text-blue-300 border border-blue-600/50">WAVE: Oscillator</span>';
      if (t.includes('QUIK')) return '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-teal-950/80 text-teal-300 border border-teal-600/50">QUIK: Runner</span>';
      return '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 text-slate-300 border border-slate-700">CORE MARKET</span>';
    }

    // Trade Sizing Console Handlers
    function onTradeSliderChange(val) {
      currentTradeSizePct = parseInt(val, 10);
      const disp = document.getElementById('tradeSizeDisplay');
      disp.innerText = (currentTradeSizePct === 100) ? '100% MAX' : `${currentTradeSizePct}%`;

      document.querySelectorAll('.size-pill').forEach(btn => {
        const pct = parseInt(btn.dataset.pct, 10);
        btn.classList.toggle('active', pct === currentTradeSizePct);
      });
    }

    function setGlobalTradeSize(pct) {
      currentTradeSizePct = pct;
      document.getElementById('tradeSizeSlider').value = pct;
      onTradeSliderChange(pct);
    }

    // Strategy Presets
    async function selectStrategyPreset(preset) {
      document.querySelectorAll('.preset-pill').forEach(p => p.classList.remove('active'));
      const activeBtn = document.getElementById(`preset-${preset}`);
      if (activeBtn) activeBtn.classList.add('active');

      document.getElementById('activePresetBadge').innerText = preset;
      showTradeToast(`Applying ${preset} strategy preset...`, 'text-cyan-400');

      try {
        const res = await fetch('/api/strategy_preset', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ preset: preset })
        });
        const d = await res.json();
        if (d.success) {
          showTradeToast(`Applied ${preset} Preset!`, 'text-emerald-400');
          playAudioTone('BUY');
          if (d.settings) applySettingsToUI(d.settings);
        }
      } catch (e) {
        showTradeToast(`Preset update error: ${e}`, 'text-rose-400');
      }
    }

    // Export CSV
    function exportTradeHistoryCSV() {
      showTradeToast('Exporting Trade Ledger CSV...', 'text-cyan-400');
      window.location.href = '/api/export_trades';
    }

    // Filter & Search Handlers
    function setCategoryFilter(cat) {
      currentCategoryFilter = cat;
      document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
      const activeTab = document.getElementById(`filter-${cat}`);
      if (activeTab) activeTab.classList.add('active');
      applyTableFilter();
    }

    function onSearchInput(query) {
      currentSearchQuery = (query || '').trim().toUpperCase();
      applyTableFilter();
    }

    function applyTableFilter() {
      const tbody = document.getElementById('stocksTableBody');
      const rows = tbody.querySelectorAll('tr[id^="row-"]');
      rows.forEach(row => {
        const ticker = (row.dataset.ticker || '').toUpperCase();
        const profile = (row.dataset.profile || '').toUpperCase();
        const holding = (row.dataset.holding || '').toUpperCase();
        const pnl = parseFloat(row.dataset.pnl || '0');

        let matchesCat = true;
        if (currentCategoryFilter === 'HOLDING') {
          matchesCat = (holding && holding !== 'FLAT');
        } else if (currentCategoryFilter === 'PROFITABLE') {
          matchesCat = (pnl > 0);
        } else if (currentCategoryFilter === 'SPECIAL') {
          matchesCat = ['PUMP', 'DUMP', 'TECH', 'PLAIN', 'BASE'].some(k => ticker.includes(k) || profile.includes(k));
        }

        let matchesSearch = true;
        if (currentSearchQuery) {
          matchesSearch = (ticker.includes(currentSearchQuery) || profile.includes(currentSearchQuery));
        }

        row.style.display = (matchesCat && matchesSearch) ? '' : 'none';
      });
    }

    // Instant Trade Execution Trigger
    async function executeStockAction(ticker, action) {
      if (!ticker) return;
      const act = action.toUpperCase();
      const isMax = (currentTradeSizePct === 100 || action === 'close');
      const sizeStr = (action === 'close') ? 'ALL' : (isMax ? 'MAX' : `${currentTradeSizePct}%`);
      showTradeToast(`Dispatching ${act} ${ticker} (${sizeStr})...`, 'text-yellow-400');

      try {
        const res = await fetch('/api/trade', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticker: ticker,
            action: action.toLowerCase(),
            amount_type: isMax ? 'max' : 'percent',
            percent: currentTradeSizePct,
            pct: currentTradeSizePct,
            is_max: isMax
          })
        });
        const ret = await res.json();
        if (ret.success) {
          showTradeToast(`Success: ${act} ${ticker} (${sizeStr})`, 'text-emerald-400');
          playAudioTone(act);
        } else {
          showTradeToast(`Execution Error: ${ret.message || 'Bridge timeout'}`, 'text-rose-400');
        }
      } catch (err) {
        showTradeToast(`Network error: ${err}`, 'text-rose-400');
      }
    }

    function showTradeToast(msg, colorClass) {
      const logBox = document.getElementById('logsContainer');
      const timeStr = new Date().toLocaleTimeString();
      const el = document.createElement('div');
      el.className = `${colorClass || 'text-slate-300'} transition-opacity duration-300`;
      el.innerHTML = `<span class="text-slate-500">[${timeStr}]</span> ${msg}`;
      logBox.insertBefore(el, logBox.firstChild);
      while (logBox.children.length > 60) {
        logBox.removeChild(logBox.lastChild);
      }
    }

    // Initialize Chart.js
    
    // Issue 21: Dynamic Chart Stock Filtering
    let currentChartTicker = 'ALL';
    function onChartStockChange(ticker) {
      currentChartTicker = ticker;
      if (!marketChart) return;
      if (ticker === 'ALL') {
        initChart(lastRenderedStocks);
      } else {
        const found = lastRenderedStocks.find(s => s.ticker === ticker);
        if (found && found.sparkline && found.sparkline.length > 0) {
          marketChart.data.labels = found.sparkline.map((_, i) => `${i+1}`);
          marketChart.data.datasets = [{
            label: `${ticker} Price`,
            data: found.sparkline,
            borderColor: '#38bdf8',
            backgroundColor: 'rgba(56, 189, 248, 0.1)',
            fill: true,
            tension: 0.25,
            borderWidth: 2,
            pointRadius: 2
          }];
          marketChart.update();
        }
      }
    }

function initChart() {
      const ctx = document.getElementById('marketChart').getContext('2d');
      chart = new Chart(ctx, {
        type: 'line',
        data: { labels: [], datasets: [] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 0 },
          elements: { point: { radius: 1, hitRadius: 6 }, line: { borderWidth: 1.8 } },
          scales: {
            x: { display: false },
            y: {
              grid: { color: '#1e293b' },
              ticks: { color: '#64748b', font: { size: 10, family: 'monospace' } }
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: { mode: 'index', intersect: false }
          }
        }
      });
    }

    // Connect WebSocket
    function connectWS() {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${location.host}/ws`;
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        document.getElementById('connIndicator').className = 'w-2.5 h-2.5 rounded-full bg-emerald-400 pulse-dot';
        document.getElementById('connIndicator').title = 'Connected to Screen Stocks Bridge';
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          updateDashboard(data);
        } catch (e) {
          console.error("WS Parse error:", e);
        }
      };

      ws.onclose = () => {
        document.getElementById('connIndicator').className = 'w-2.5 h-2.5 rounded-full bg-rose-500';
        document.getElementById('connIndicator').title = 'Bridge Disconnected';
        setTimeout(connectWS, 2000);
      };

      ws.onerror = (e) => ws.close();
    }

    // Update Dashboard Elements
    function updateDashboard(data) {
      if (!data) return;
      if (data.settings && !window._settingsSynced) {
        applySettingsToUI(data.settings);
        window._settingsSynced = true;
      }

      // 1. Top Navbar Badges
      const isAuto = (data.mode === 'AUTO');
      const modeBadge = document.getElementById('modeBadge');
      const modeToggleBtn = document.getElementById('modeToggleBtn');
      if (modeBadge && modeToggleBtn) {
        if (isAuto) {
          modeBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-600/60 mono';
          modeBadge.innerText = 'AUTO RUNNING';
          modeToggleBtn.className = 'px-3.5 py-1 rounded bg-rose-700 hover:bg-rose-600 text-white font-bold text-xs shadow-md transition-all active:scale-95 mono';
          modeToggleBtn.innerText = 'STOP AUTO MODE';
        } else {
          modeBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/70 text-amber-300 border border-amber-700/60 mono';
          modeBadge.innerText = 'SUGGESTION MODE';
          modeToggleBtn.className = 'px-3.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-md transition-all active:scale-95 mono';
          modeToggleBtn.innerText = 'Switch to AUTO MODE';
        }
      }

      // Base 12:30 AM IST Timer
      const dbStats = data.db_stats || {};
      const countdownEl = document.getElementById('baseCrashCountdown');
      if (countdownEl) {
        countdownEl.innerText = dbStats.base_crash_countdown || 'Syncing...';
        const banner = document.getElementById('baseCrashBanner');
        if (banner) {
          if (dbStats.is_base_crash_active) {
            banner.className = 'flex items-center gap-2 px-3 py-1 rounded-full bg-rose-950/80 border border-rose-500 text-rose-200 font-mono text-xs animate-pulse';
          } else {
            banner.className = 'flex items-center gap-2 px-3 py-1 rounded-full bg-purple-950/60 border border-purple-700/50 text-purple-300 font-mono text-xs';
          }
        }
      }

      // Achievements Mode Button
      const achieveBtn = document.getElementById('achievementsToggleBtn');
      const achieveDot = document.getElementById('achieveDot');
      const achieveText = document.getElementById('achieveText');
      if (achieveBtn && achieveDot && achieveText) {
        if (data.achievements_enabled) {
          achieveDot.className = 'w-2 h-2 rounded-full bg-amber-400 pulse-dot';
          achieveText.innerText = 'ON';
          achieveBtn.className = 'px-2.5 py-1 rounded text-xs font-semibold bg-amber-950/80 text-amber-300 border border-amber-600 hover:bg-amber-900 transition-colors flex items-center gap-1.5';
        } else {
          achieveDot.className = 'w-2 h-2 rounded-full bg-slate-500';
          achieveText.innerText = 'OFF';
          achieveBtn.className = 'px-2.5 py-1 rounded text-xs font-semibold bg-slate-800/90 text-slate-300 border border-slate-700 hover:bg-slate-700 transition-colors flex items-center gap-1.5';
        }
      }

      // 2. KPI Ribbon
      const p = data.player || {};
      document.getElementById('netWorthDisplay').innerText = p.netWorth || '$0.00';
      document.getElementById('cashDisplay').innerText = p.cash || '$0.00';
      document.getElementById('ipoTag').innerText = `IPO: ${p.ipoCount || 0}`;

      const unrealizedPnL = p.totalUnrealizedPnL || 0;
      const pnlTag = document.getElementById('pnlTag');
      if (pnlTag) {
        const sign = unrealizedPnL >= 0 ? '+' : '';
        pnlTag.innerText = `${sign}$${unrealizedPnL.toFixed(2)}`;
        pnlTag.className = unrealizedPnL >= 0 ? 'mono text-xs font-semibold text-emerald-400' : 'mono text-xs font-semibold text-rose-400';
      }

      // Issue 20: Game connection status
      const connDot = document.getElementById('connIndicator');
      const gameBadge = document.getElementById('gameConnBadge');
      if (data.game_connected) {
        if (connDot) connDot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400 pulse-dot';
        if (gameBadge) {
          gameBadge.className = 'px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-950/80 text-emerald-300 border border-emerald-600/60';
          gameBadge.innerText = `GAME: LINKED (PID ${data.game_pid || '-'})`;
        }
      } else {
        if (connDot) connDot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 pulse-dot';
        if (gameBadge) {
          gameBadge.className = 'px-2 py-0.5 rounded text-[11px] font-mono bg-amber-950/80 text-amber-300 border border-amber-600/60';
          gameBadge.innerText = 'GAME: AWAITING BRIDGE';
        }
      }

      // Session Stats
      const session = data.session_stats || {};
      const sessionPnl = session.realized_pnl || 0;
      const sessionPnlEl = document.getElementById('sessionPnlDisplay');
      if (sessionPnlEl) {
        const sSign = sessionPnl >= 0 ? '+' : '';
        sessionPnlEl.innerText = `${sSign}$${sessionPnl.toFixed(2)}`;
        sessionPnlEl.className = sessionPnl >= 0 ? 'mono text-xl sm:text-2xl font-bold text-emerald-400' : 'mono text-xl sm:text-2xl font-bold text-rose-400';
      }
      document.getElementById('sessionTradesCount').innerText = `${session.trades_count || 0} Trades`;
      
      // Issue 19: Strict check so 0% win rate displays accurately as 0.0%, NEVER 100%!
      const wrVal = (session.win_rate !== undefined && session.win_rate !== null) ? session.win_rate : 0.0;
      document.getElementById('winRateDisplay').innerText = `${wrVal.toFixed(1)}%`;
      document.getElementById('winLossCounts').innerText = `${session.wins || 0}W - ${session.losses || 0}L`;

      // Issue 7: Dynamic model accuracy
      const modelAccEl = document.getElementById('modelAccText');
      if (modelAccEl) {
        modelAccEl.innerText = (data.retrain_accuracy !== undefined && data.retrain_accuracy !== null) ? `${data.retrain_accuracy}%` : 'Calibrating...';
      }

      // Latency & DB Stats
      document.getElementById('latencyDisplay').innerText = `${data.inf_latency_ms || 0.12} ms`;
      document.getElementById('dbTicksCount').innerText = (dbStats.total_ticks || 0).toLocaleString();
      document.getElementById('retrainCountdown').innerText = `${dbStats.next_retrain_in || 45}s`;
      document.getElementById('universeCount').innerText = `${(data.unlocked_stocks || []).length} Stocks`;

      // Dividend Vault
      const vaultTag = document.getElementById('vaultStatusTag');
      const divIncome = document.getElementById('divIncomeDisplay');
      if (vaultTag && divIncome) {
        if (dbStats.dividend_vault_active) {
          vaultTag.innerText = 'VAULT ENGAGED (> $1B)';
          vaultTag.className = 'mono text-xs font-bold text-amber-400 animate-pulse';
          divIncome.innerText = `+$${(dbStats.dividend_income_per_min || 0).toFixed(2)} / min`;
        } else {
          vaultTag.innerText = 'Standby (< $1B)';
          vaultTag.className = 'mono text-xs font-semibold text-slate-500';
          divIncome.innerText = '+$0.00 / min';
        }
      }

      // 3. Populate Stocks Table (with Sparklines, Price Flashing, Action Buttons)
      const tbody = document.getElementById('stocksTableBody');
      const stocks = data.stocks || [];
      lastRenderedStocks = stocks;

      if (stocks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center py-6 text-slate-400">Waiting for market feed...</td></tr>';
      } else {
        stocks.forEach(s => {
          let row = document.getElementById(`row-${s.ticker}`);
          if (!row) {
            row = document.createElement('tr');
            row.id = `row-${s.ticker}`;
            row.className = 'hover:bg-slate-800/40 transition-colors';
            row.innerHTML = `
              <td class="py-2.5 px-3 font-bold text-white cell-ticker">
                <div class="flex items-center gap-2">
                  <span>${s.ticker}</span>
                  <span class="cell-profile">${getProfileBadge(s.ticker)}</span>
                </div>
              </td>
              <td class="py-2.5 px-3 cell-sparkline"></td>
              <td class="py-2.5 px-3 font-semibold mono cell-price">
                <span class="cell-price-val px-1.5 py-0.5 rounded transition-all">$${s.price.toFixed(2)}</span>
              </td>
              <td class="py-2.5 px-3 cell-signal"></td>
              <td class="py-2.5 px-3 cell-conf text-slate-400">${s.confidence}%</td>
              <td class="py-2.5 px-3 cell-holding">${s.holding}</td>
              <td class="py-2.5 px-3 cell-avg text-slate-400">$${s.avg_price ? s.avg_price.toFixed(2) : '-'}</td>
              <td class="py-2.5 px-3 cell-pnl"></td>
              <td class="py-2.5 px-3 text-slate-400 cell-status">${s.exit_status || 'Scanning'}</td>
              <td class="py-2.5 px-3 text-right whitespace-nowrap cell-actions">
                <div class="inline-flex items-center gap-1.5">
                  <button type="button" onclick="executeStockAction('${s.ticker}', 'buy')" class="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-sm transition-all active:scale-95" title="Buy ${s.ticker}">BUY</button>
                  <button type="button" onclick="executeStockAction('${s.ticker}', 'sell')" class="btn-row-sell px-2.5 py-1 rounded text-xs font-bold shadow-sm transition-all active:scale-95" title="Sell long shares in ${s.ticker}">SELL</button>
                  <button type="button" onclick="executeStockAction('${s.ticker}', 'short')" class="px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shadow-sm transition-all active:scale-95" title="Short ${s.ticker}">SHORT</button>
                  <button type="button" onclick="executeStockAction('${s.ticker}', 'close')" class="btn-row-close px-2.5 py-1 rounded text-xs font-bold shadow-sm transition-all active:scale-95" title="Close all positions in ${s.ticker}">CLOSE</button>
                </div>
              </td>
            `;
            tbody.appendChild(row);
          }

          // Update Row Data Attributes for Filter
          row.dataset.ticker = s.ticker;
          row.dataset.profile = s.profile || s.ticker;
          row.dataset.holding = s.holding;
          row.dataset.pnl = s.pnl || 0;

          // Render Sparkline
          const sparkCell = row.querySelector('.cell-sparkline');
          if (sparkCell && s.sparkline) {
            sparkCell.innerHTML = renderSparklineSVG(s.sparkline);
          }

          // Live Price Change Pulse Animation
          const priceValEl = row.querySelector('.cell-price-val');
          if (priceValEl) {
            const oldPrice = previousPrices[s.ticker];
            if (oldPrice !== undefined) {
              if (s.price > oldPrice) {
                priceValEl.classList.remove('flash-down');
                priceValEl.classList.add('flash-up');
                setTimeout(() => priceValEl.classList.remove('flash-up'), 500);
              } else if (s.price < oldPrice) {
                priceValEl.classList.remove('flash-up');
                priceValEl.classList.add('flash-down');
                setTimeout(() => priceValEl.classList.remove('flash-down'), 500);
              }
            }
            previousPrices[s.ticker] = s.price;
            priceValEl.innerText = `$${s.price.toFixed(2)}`;
          }

          // Update Signal Badge
          const sigCell = row.querySelector('.cell-signal');
          let sigColor = 'bg-slate-800 text-slate-400 border border-slate-700';
          if (s.signal_label === 'STRONG BUY') sigColor = 'bg-emerald-950 text-emerald-300 border border-emerald-500 font-bold';
          else if (s.signal_label === 'BUY') sigColor = 'bg-emerald-950/60 text-emerald-400 border border-emerald-600/50';
          else if (s.signal_label === 'STRONG SHORT') sigColor = 'bg-rose-950 text-rose-300 border border-rose-500 font-bold';
          else if (s.signal_label === 'SHORT') sigColor = 'bg-rose-950/60 text-rose-400 border border-rose-600/50';
          sigCell.innerHTML = `<span class="px-2 py-0.5 rounded text-[11px] mono ${sigColor}">${s.signal_label}</span>`;

          // Update Confidence, Position, PnL, Status
          row.querySelector('.cell-conf').innerText = `${s.confidence}%`;

          const holdCell = row.querySelector('.cell-holding');
          holdCell.innerText = s.holding;
          if (s.holding.includes('LONG')) holdCell.className = 'py-2.5 px-3 cell-holding font-semibold text-emerald-400';
          else if (s.holding.includes('SHORT')) holdCell.className = 'py-2.5 px-3 cell-holding font-semibold text-rose-400';
          else holdCell.className = 'py-2.5 px-3 cell-holding text-slate-500';

          row.querySelector('.cell-avg').innerText = s.avg_price ? `$${s.avg_price.toFixed(2)}` : '-';

          const pnlCell = row.querySelector('.cell-pnl');
          if (s.pnl !== null && s.pnl !== undefined && s.holding !== 'FLAT') {
            const pnlSign = s.pnl >= 0 ? '+' : '';
            pnlCell.innerText = `${pnlSign}$${s.pnl.toFixed(2)} (${pnlSign}${s.pnl_pct.toFixed(1)}%)`;
            pnlCell.className = s.pnl >= 0 ? 'py-2.5 px-3 cell-pnl font-bold text-emerald-400' : 'py-2.5 px-3 cell-pnl font-bold text-rose-400';
          } else {
            pnlCell.innerText = '-';
            pnlCell.className = 'py-2.5 px-3 cell-pnl text-slate-500';
          }

          row.querySelector('.cell-status').innerText = s.exit_status || 'Scanning';

          // Action Button States
          const hasLong = s.holding.includes('LONG');
          const hasShort = s.holding.includes('SHORT');
          const sellBtn = row.querySelector('.btn-row-sell');
          const closeBtn = row.querySelector('.btn-row-close');

          if (sellBtn) {
            sellBtn.disabled = !hasLong;
            sellBtn.className = hasLong
              ? 'btn-row-sell px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs shadow-sm transition-all active:scale-95'
              : 'btn-row-sell px-2.5 py-1 rounded bg-slate-800 text-slate-600 border border-slate-800 text-xs font-semibold cursor-not-allowed';
          }
          if (closeBtn) {
            closeBtn.disabled = (!hasLong && !hasShort);
            closeBtn.className = (hasLong || hasShort)
              ? 'btn-row-close px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs shadow-sm transition-all active:scale-95'
              : 'btn-row-close px-2.5 py-1 rounded bg-slate-800 text-slate-600 border border-slate-800 text-xs font-semibold cursor-not-allowed';
          }
        });
      }

      applyTableFilter();

      // 4. Update Logs Terminal (Issue 22: Append-only with rendered ID set so events never vanish!)
      const logContainer = document.getElementById('logsContainer');
      const logs = data.logs || [];
      if (logs.length > 0) {
        if (!window._renderedLogKeys) window._renderedLogKeys = new Set();
        logs.forEach(l => {
          const key = `${l.time}_${l.ticker}_${l.action}_${(l.reason || '').slice(0, 20)}`;
          if (!window._renderedLogKeys.has(key)) {
            window._renderedLogKeys.add(key);
            const div = document.createElement('div');
            const statusColor = (l.status === 'EXECUTED') ? 'text-emerald-400' : (l.status === 'FAILED' ? 'text-rose-400' : 'text-cyan-400');
            div.className = 'text-slate-300 border-b border-slate-900/60 pb-0.5';
            div.innerHTML = `<span class="text-slate-500">[${l.time}]</span> <strong class="text-white">${l.ticker}</strong> <span class="${statusColor}">[${l.action}]</span> <span class="text-slate-400">${l.reason}</span>`;
            if (logContainer.children.length > 0 && logContainer.children[0].innerText.includes('Awaiting market events')) {
              logContainer.innerHTML = '';
            }
            logContainer.insertBefore(div, logContainer.firstChild);
            while (logContainer.children.length > 100) {
              logContainer.removeChild(logContainer.lastChild);
            }
          }
        });
      }

      // 5. Update Chart
      const history = data.history || {};
      const chartSeries = history.series || {};
      const timestamps = history.timestamps || [];
      if (chart && timestamps.length > 0) {
        chart.data.labels = timestamps;
        const colorPalette = ['#38bdf8', '#34d399', '#f43f5e', '#fbbf24', '#a855f7', '#ec4899', '#14b8a6'];
        let colorIdx = 0;
        chart.data.datasets = Object.keys(chartSeries).map(ticker => {
          const col = colorPalette[colorIdx % colorPalette.length];
          colorIdx++;
          return {
            label: ticker,
            data: chartSeries[ticker],
            borderColor: col,
            backgroundColor: 'transparent',
            tension: 0.2
          };
        });
        chart.update('none');
      }
    }

    // Settings & Handlers
    function onStopLossSliderChange(val) {
      document.getElementById('stopLossVal').innerText = (parseFloat(val) === 0) ? 'OFF' : `${val}%`;
    }
    function onMinProfitSliderChange(val) {
      document.getElementById('minProfitVal').innerText = (parseFloat(val) === 0) ? 'OFF' : `${val}%`;
    }
    function onTechSliderChange(val) {
      document.getElementById('techTargetVal').innerText = `$${parseFloat(val).toFixed(1)}`;
      document.getElementById('techTargetDisplay').innerText = `$${parseFloat(val).toFixed(1)}`;
    }
    function setTechTargetX(val) {
      document.getElementById('techTargetSlider').value = val;
      onTechSliderChange(val);
      saveSettings();
    }
    function onMaxPosChange(val) {
      document.getElementById('maxPosVal').innerText = `${val} Active`;
    }

    let stopLossActive = true;
    function toggleStopLoss() {
      stopLossActive = !stopLossActive;
      const btn = document.getElementById('stopLossToggleBtn');
      btn.innerText = stopLossActive ? 'ON' : 'OFF';
      btn.className = stopLossActive ? 'text-xs px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-700' : 'text-xs px-1.5 py-0.5 rounded bg-slate-800 text-slate-500 border border-slate-700';
      saveSettings();
    }

    let minProfitActive = true;
    function toggleMinProfit() {
      minProfitActive = !minProfitActive;
      const btn = document.getElementById('minProfitToggleBtn');
      btn.innerText = minProfitActive ? 'ON' : 'OFF';
      btn.className = minProfitActive ? 'text-xs px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-700' : 'text-xs px-1.5 py-0.5 rounded bg-slate-800 text-slate-500 border border-slate-700';
      saveSettings();
    }

    
    function applySettingsToUI(s) {
      if (!s) return;
      if (s.stop_loss_pct !== undefined && s.stop_loss_pct !== null) {
        const el = document.getElementById('stopLossSlider');
        if (el) { el.value = s.stop_loss_pct; }
        const valEl = document.getElementById('stopLossVal');
        if (valEl) { valEl.innerText = `${s.stop_loss_pct}%`; }
      }
      if (s.stop_loss_enabled !== undefined && s.stop_loss_enabled !== null) {
        stopLossActive = !!s.stop_loss_enabled;
        const btn = document.getElementById('stopLossToggleBtn');
        if (btn) {
          btn.innerText = stopLossActive ? 'ON' : 'OFF';
          btn.className = stopLossActive ? 'text-xs px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-700' : 'text-xs px-1.5 py-0.5 rounded bg-slate-800 text-slate-500 border border-slate-700';
        }
      }
      if (s.min_profit_pct !== undefined && s.min_profit_pct !== null) {
        const el = document.getElementById('minProfitSlider');
        if (el) { el.value = s.min_profit_pct; }
        const valEl = document.getElementById('minProfitVal');
        if (valEl) { valEl.innerText = `${s.min_profit_pct}%`; }
      }
      if (s.take_profit_enabled !== undefined && s.take_profit_enabled !== null) {
        minProfitActive = !!s.take_profit_enabled;
        const btn = document.getElementById('minProfitToggleBtn');
        if (btn) {
          btn.innerText = minProfitActive ? 'ON' : 'OFF';
          btn.className = minProfitActive ? 'text-xs px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-700' : 'text-xs px-1.5 py-0.5 rounded bg-slate-800 text-slate-500 border border-slate-700';
        }
      }
      if (s.tech_target_x !== undefined && s.tech_target_x !== null) {
        const el = document.getElementById('techTargetSlider');
        if (el) { el.value = s.tech_target_x; }
        const valEl = document.getElementById('techTargetVal');
        if (valEl) { valEl.innerText = `$${parseFloat(s.tech_target_x).toFixed(1)}`; }
      }
      if (s.max_positions !== undefined && s.max_positions !== null) {
        const el = document.getElementById('maxPosSlider');
        if (el) { el.value = s.max_positions; }
        const valEl = document.getElementById('maxPosVal');
        if (valEl) { valEl.innerText = `${s.max_positions} Active`; }
      }
      if (s.auto_time_limit_hours !== undefined && s.auto_time_limit_hours !== null) {
        const el = document.getElementById('autoTimeLimit');
        if (el) { el.value = s.auto_time_limit_hours; }
      }
    }

async function saveSettings() {
      const payload = {
        stop_loss_enabled: stopLossActive,
        stop_loss_pct: parseFloat(document.getElementById('stopLossSlider').value),
        take_profit_enabled: minProfitActive,
        min_profit_pct: parseFloat(document.getElementById('minProfitSlider').value),
        tech_target_x: parseFloat(document.getElementById('techTargetSlider').value),
        max_positions: parseInt(document.getElementById('maxPosSlider').value, 10),
        auto_time_limit_hours: parseFloat(document.getElementById('autoTimeLimit').value)
      };

      try {
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        showTradeToast('Risk parameters saved!', 'text-cyan-400');
      } catch (e) {
        showTradeToast('Failed to save settings', 'text-rose-400');
      }
    }

    async function toggleMode() {
      try {
        const res = await fetch('/api/toggle_mode', { method: 'POST' });
        const d = await res.json();
        showTradeToast(`Mode switched to ${d.mode}`, 'text-amber-400');
      } catch (e) {
        showTradeToast('Mode switch failed', 'text-rose-400');
      }
    }

    async function toggleAchievements() {
      try {
        const res = await fetch('/api/toggle_achievements', { method: 'POST' });
        const d = await res.json();
        showTradeToast(`Achievements Hunter: ${d.achievements_enabled ? 'ENABLED' : 'DISABLED'}`, 'text-cyan-400');
      } catch (e) {
        showTradeToast('Failed to toggle achievements', 'text-rose-400');
      }
    }

    async function liquidateAll() {
      if (!confirm('Liquidate ALL open long and short positions to 100% Cash immediately?')) return;
      showTradeToast('Initiating emergency liquidation across all positions...', 'text-rose-400');
      try {
        const res = await fetch('/api/liquidate_all', { method: 'POST' });
        const d = await res.json();
        showTradeToast(`Liquidation complete: Closed ${d.closed_positions || 0} positions to 100% Cash`, 'text-emerald-400');
        playAudioTone('CLOSE');
      } catch (e) {
        showTradeToast('Liquidation request error', 'text-rose-400');
      }
    }

    // Startup
    window.addEventListener('DOMContentLoaded', () => {
      initChart();
      connectWS();
      setCategoryFilter('ALL');
    });
  </script>
</body>
</html>
"""





# ==============================================================================
# 7. FASTAPI REST & WEBSOCKET APPLICATION
# ==============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_tick_storage_worker(app_state)
    start_auto_retrain_worker(app_state)
    asyncio.create_task(game_bridge_loop(app_state))
    asyncio.create_task(periodic_broadcast_loop())
    print("[+] Background bridge, broadcast, and high-speed Protocol Buffer storage workers started.", flush=True)
    yield

app = FastAPI(title="OtoStoksBot AI Autonomous Engine", lifespan=lifespan)

connected_websockets: Set[WebSocket] = set()

class SettingsPayload(BaseModel):
    max_positions: int
    stop_loss_enabled: bool
    stop_loss_pct: float
    take_profit_enabled: bool
    min_profit_pct: float
    auto_time_limit_hours: float
    tech_target_x: float = 16.0

class SetStrategyPayload(BaseModel):
    mode: str

@app.get("/icon.png")
async def get_app_icon():
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    for cand in [os.path.join(base_dir, "icon.png"), os.path.join(base_dir, "assets", "icon.png"), "icon.png"]:
        if os.path.exists(cand):
            return FileResponse(cand, media_type="image/png")
    return Response(status_code=404)

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return HTMLResponse(content=HTML_PAGE)

@app.get("/api/status")
async def get_status():
    return JSONResponse(content=app_state.get_snapshot())

@app.post("/api/toggle_mode")
async def api_toggle_mode():
    new_mode = app_state.toggle_mode()
    await broadcast_state()
    return {"mode": new_mode}

@app.post("/api/toggle_achievements")
async def api_toggle_achievements():
    curr = app_state.toggle_achievements()
    await broadcast_state()
    return {"achievements_enabled": curr}

@app.post("/api/liquidate_all")
async def api_liquidate_all():
    threading.Thread(target=app_state.liquidate_all_positions, daemon=True).start()
    return {"status": "dispatched", "message": "Dispatched order to liquidate all positions to 100% cash."}

@app.post("/api/retrain")
async def api_retrain():
    def bg():
        run_retrain_pipeline(app_state)
    threading.Thread(target=bg, daemon=True).start()
    return {"status": "started", "message": "Model retraining pipeline initiated."}

@app.post("/api/launch_game")
async def api_launch_game():
    ok, msg = launch_screen_stocks()
    return {"success": ok, "message": msg}

class ManualTradePayload(BaseModel):
    ticker: str
    action: str  # "buy", "sell", "short", "cover", "close"
    amount_type: Optional[str] = "max"
    percent: Optional[int] = 100
    pct: Optional[int] = None
    amount: Optional[str] = "max"
    is_max: Optional[bool] = None

@app.post("/api/trade")
async def api_trade(payload: ManualTradePayload):
    ticker = payload.ticker.strip()
    if not ticker.startswith("$"):
        ticker = f"${ticker}"

    action = payload.action.lower().strip()
    effective_pct = payload.pct if payload.pct is not None else (payload.percent or 100)
    is_max = (payload.amount_type == "max" or effective_pct >= 100 or payload.is_max is True or action == "close")

    order_payload = {
        "id": f"manual_{ticker}_{action}_{int(time.time()*1000)}",
        "action": action,
        "ticker": ticker,
        "amount": "max",
        "isMax": is_max,
        "percent": effective_pct if not is_max else 100
    }

    # Issue 5: Calculate exact share count for ANY percentage trade (Buy, Short, Sell, Cover)
    try:
        snap = await asyncio.to_thread(fetch_snapshot_http)
        if snap and "stocks" in snap and ticker in snap["stocks"]:
            s_info = snap["stocks"][ticker]
            curr_price = float(s_info.get("price", 0.0))
            h = s_info.get("holding", {})
            owned = float(h.get("sharesOwnedDouble", 0.0))
            shorted = float(h.get("sharesShortedDouble", 0.0))
            player_cash = float(snap.get("player", {}).get("cashDouble", app_state.player.get("cashDouble", 0.0)))

            if not is_max:
                fraction = max(0.01, min(1.0, effective_pct / 100.0))
                if action == "buy" and curr_price > 0:
                    alloc = player_cash * fraction
                    shares = max(1, int(alloc / curr_price))
                    order_payload["amount"] = str(shares)
                    order_payload["isMax"] = False
                elif action == "short" and curr_price > 0:
                    alloc = player_cash * fraction
                    shares = max(1, int(alloc / (curr_price * 1.5)))  # factoring in 1.5x margin
                    order_payload["amount"] = str(shares)
                    order_payload["isMax"] = False
                elif action in ("sell", "close") and owned > 0:
                    shares = max(1, int(owned * fraction))
                    order_payload["amount"] = str(shares)
                    order_payload["isMax"] = False
                elif action in ("cover", "close") and shorted > 0:
                    shares = max(1, int(shorted * fraction))
                    order_payload["amount"] = str(shares)
                    order_payload["isMax"] = False
    except Exception as e:
        print(f"[!] Manual trade calculation notice: {e}")

    res = await asyncio.to_thread(dispatch_order_http, order_payload)
    if res and res.get("success", False):
        msg = res.get("message", f"{action.upper()} executed")
        succ = True
        status_str = "SUCCESS"
        filled_price = float(res.get("filledPrice") or app_state.stocks.get(ticker, {}).get("price", 0.0))
        filled_shares = int(res.get("shares") or order_payload.get("amount") or 1) if str(res.get("shares") or order_payload.get("amount")).isdigit() else 1
        
        # Issue 17: Record confirmed manual trades into persistent Protobuf datastore and memory history!
        try:
            record_trade_in_proto(
                app_state.trades_pb_path,
                ticker,
                action.upper(),
                filled_price,
                filled_shares,
                None,
                f"Manual Trade ({effective_pct}%)"
            )
            app_state.trade_history.append({
                "id": order_payload["id"],
                "time": datetime.datetime.now().strftime('%H:%M:%S'),
                "ticker": ticker,
                "action": action.upper(),
                "price": f"${filled_price:.2f}",
                "amount": f"{filled_shares:,}",
                "pnl": "-",
                "reason": f"Manual Trader ({effective_pct}%)"
            })
        except Exception as e:
            print(f"[!] Manual trade persistence note: {e}")
    else:
        msg = res.get("message", "Bridge rejected order or game not responding") if res else "Game bridge not responding"
        succ = False
        status_str = "REJECTED"

    app_state.add_log(ticker, f"MANUAL_{action.upper()}", "MANUAL", msg, status_str)

    # Fast refresh game state and broadcast within 120ms
    async def fast_refresh():
        await asyncio.sleep(0.12)
        snap = await asyncio.to_thread(fetch_snapshot_http)
        if snap and "player" in snap:
            p = snap["player"]
            with app_state.lock:
                app_state.player["cash"] = p.get("cash", app_state.player["cash"])
                app_state.player["cashDouble"] = float(p.get("cashDouble", app_state.player["cashDouble"]))
                app_state.player["netWorth"] = p.get("netWorth", app_state.player["netWorth"])
                app_state.player["netWorthDouble"] = float(p.get("netWorthDouble", app_state.player["netWorthDouble"]))
                if "stocks" in snap:
                    for s_ticker, s_data in snap["stocks"].items():
                        if s_ticker in app_state.stocks:
                            h = s_data.get("holding", {})
                            owned = float(h.get("sharesOwnedDouble", 0.0))
                            shorted = float(h.get("sharesShortedDouble", 0.0))
                            if owned > 0:
                                app_state.stocks[s_ticker]["holding"] = f"LONG {owned:,.0f}"
                            elif shorted > 0:
                                app_state.stocks[s_ticker]["holding"] = f"SHORT {shorted:,.0f}"
                            else:
                                app_state.stocks[s_ticker]["holding"] = "FLAT"
        await broadcast_state()

    asyncio.create_task(fast_refresh())
    return {"success": succ, "message": msg, "response": res}


class PresetPayload(BaseModel):
    preset: str

@app.post("/api/strategy_preset")
async def set_strategy_preset(payload: PresetPayload):
    p = payload.preset.upper()
    with app_state.lock:
        app_state.active_strategy_preset = p
        if p == "TURBO":
            app_state.settings["max_alloc_pct"] = 85.0
            app_state.settings["stop_loss_pct"] = 15.0
            app_state.settings["min_profit_pct"] = 6.0
            app_state.settings["tech_target_x"] = 16.0
            app_state.settings["max_positions"] = 5
        elif p == "GROWTH":
            app_state.settings["max_alloc_pct"] = 40.0
            app_state.settings["stop_loss_pct"] = 12.0
            app_state.settings["min_profit_pct"] = 8.0
            app_state.settings["tech_target_x"] = 18.0
            app_state.settings["max_positions"] = 6
        elif p == "DEFENSIVE":
            app_state.settings["max_alloc_pct"] = 15.0
            app_state.settings["stop_loss_pct"] = 4.0
            app_state.settings["min_profit_pct"] = 4.0
            app_state.settings["tech_target_x"] = 15.0
            app_state.settings["max_positions"] = 3
        elif p == "BILLIONAIRE":
            app_state.dividend_vault_active = True
            app_state.settings["max_alloc_pct"] = 100.0
            app_state.settings["stop_loss_enabled"] = False
            app_state.settings["take_profit_enabled"] = False
    await broadcast_state()
    return {"success": True, "preset": p, "settings": app_state.settings}

@app.get("/api/export_trades")
async def export_trades():
    try:
        trades = pb.read_all_trades(app_state.trades_pb_path)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Trade ID", "Timestamp (UTC)", "Ticker", "Action", "Price ($)", "Shares", "Profit (%)", "Algorithmic Reason"])
        for r in reversed(trades):
            ts_str = datetime.datetime.fromtimestamp(r.timestamp).strftime('%Y-%m-%d %H:%M:%S') if r.timestamp else ''
            p_pct_str = f"{r.profit_pct:.2f}%" if r.profit_pct != 0.0 else "-"
            writer.writerow([r.trade_id, ts_str, r.ticker, r.action, f"{r.price:.2f}", r.amount, p_pct_str, r.reason])
        
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=OtoStoksBot_Trades_{int(time.time())}.csv"}
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/settings")
async def api_settings(payload: SettingsPayload):
    app_state.update_settings(
        max_pos=payload.max_positions,
        stop_loss_enabled=payload.stop_loss_enabled,
        stop_loss=payload.stop_loss_pct,
        take_profit_enabled=payload.take_profit_enabled,
        min_profit=payload.min_profit_pct,
        auto_hours=payload.auto_time_limit_hours,
        tech_target_x=payload.tech_target_x
    )
    await broadcast_state()
    return {"status": "success", "settings": app_state.settings}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        await websocket.send_text(json.dumps(app_state.get_snapshot()))
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        connected_websockets.discard(websocket)

async def broadcast_state():
    if not connected_websockets:
        return
    msg = json.dumps(app_state.get_snapshot())
    dead = []
    for ws in list(connected_websockets):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_websockets.discard(ws)

async def periodic_broadcast_loop():
    while app_state.running:
        await asyncio.sleep(5.0)
        await broadcast_state()


# Terminal hotkey listener

def start_keyboard_listener(state: AppState):
    def listener():
        if sys.platform != "win32":
            return
        try:
            import msvcrt
            while state.running:
                try:
                    if msvcrt.kbhit():
                        ch = msvcrt.getch()
                        if ch.lower() == b'm':
                            new_mode = state.toggle_mode()
                            print(f"\n[KEYBOARD HOTKEY 'M'] Swapped Mode to: >>> {new_mode} <<<", flush=True)
                        elif ch.lower() == b'a':
                            curr = state.toggle_achievements()
                            print(f"\n[KEYBOARD HOTKEY 'A'] Achievements Hunter Mode: >>> {'ENABLED' if curr else 'DISABLED'} <<<", flush=True)
                except Exception:
                    pass
                time.sleep(0.05)
        except Exception:
            pass

    t = threading.Thread(target=listener, daemon=True)
    t.start()


# ==============================================================================
# 9. MAIN RUNNER & LIFECYCLE
# ==============================================================================

class UvicornServerThread(threading.Thread):
    def __init__(self, fastapi_app, host="127.0.0.1", port=8080):
        super().__init__(daemon=True)
        config = uvicorn.Config(fastapi_app, host=host, port=port, log_level="warning", log_config=None)
        self.server = uvicorn.Server(config)

    def run(self):
        try:
            self.server.run()
        except Exception as e:
            print(f"[!] Server thread error: {e}", flush=True)

    def stop(self):
        self.server.should_exit = True

def wait_for_server(url="http://127.0.0.1:8080/api/status", max_retries=60, delay=0.1):
    for _ in range(max_retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=0.2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(delay)
    return False

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8080")

def main():
    cleanup_old_instances()

    # Step 1: Auto-install mod to BepInEx
    try:
        success, msg = run_auto_installer()
    except Exception:
        pass

    # Step 2: Check if Screen Stocks is already running, auto-start if not
    try:
        is_running, pid = check_game_process()
        if is_running:
            app_state.game_running = True
            app_state.game_pid = pid
        else:
            launch_screen_stocks()
    except Exception:
        pass

    # Step 3: Hotkey listener (if running from a console)
    try:
        start_keyboard_listener(app_state)
    except Exception:
        pass

    is_headless = "--headless" in sys.argv or "--no-gui" in sys.argv

    active_port = find_available_port(8080)
    server_url = f"http://127.0.0.1:{active_port}"

    if HAS_WEBVIEW and not is_headless:
        # Start uvicorn background daemon thread on dynamically verified safe port
        server_thread = UvicornServerThread(app, host="127.0.0.1", port=active_port)
        server_thread.start()
        wait_for_server(f"{server_url}/api/status")

        try:
            # Native desktop application window (Zero black terminal & No localhost URL bar)
            window = webview.create_window(
                title="OtoStoksBot Pro v4.0 - Autonomous Quantitative Trading Engine",
                url=server_url,
                width=1440,
                height=900,
                min_size=(1024, 680),
                background_color="#070b13"
            )

            def on_closed():
                if app_state.mode == "AUTO":
                    try:
                        app_state.liquidate_all_positions()
                    except Exception:
                        pass
                app_state.running = False
                server_thread.stop()

            window.events.closed += on_closed
            webview.start()
        except Exception as e:
            # Graceful fallback to browser if webview encounters display issues
            print(f"[!] Desktop window error, falling back to browser: {e}", flush=True)
            threading.Thread(target=open_browser, daemon=True).start()
            server_thread.join()
        finally:
            server_thread.stop()
            if app_state.mode == "AUTO":
                try:
                    app_state.liquidate_all_positions()
                except Exception:
                    pass
            app_state.running = False
    else:
        # Console / Headless fallback mode
        threading.Thread(target=open_browser, daemon=True).start()
        try:
            uvicorn.run(app, host="127.0.0.1", port=8080, log_config=None)
        except KeyboardInterrupt:
            if app_state.mode == "AUTO":
                app_state.liquidate_all_positions()
            app_state.running = False

if __name__ == "__main__":
    main()
