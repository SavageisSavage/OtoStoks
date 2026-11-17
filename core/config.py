import os
import sys
import socket
import subprocess
from typing import Tuple, Dict, Any, Optional

STEAM_APP_ID = "4356780"

# ------------------------------------------------------------------------------
# Latency tunables
#
# The game republishes mods/export/market.json roughly once per second (median
# 1002 ms, p95 1058 ms, measured from history.json). Polling faster than that
# only re-parses an unchanged 34 KB JSON document, so the loop is driven by the
# file's mtime instead of a fixed sleep.
# ------------------------------------------------------------------------------
POLL_IDLE_S = 0.01                 # idle poll when the game has not written a new frame
SNAPSHOT_STALE_S = 5.0             # treat the feed as lost after this long without a write
BROADCAST_IDLE_S = 0.5             # refresh the dashboard at least this often while idle
PROCESS_CHECK_INTERVAL_S = 2.0     # how often to ask tasklist whether the game runs
HTTP_BRIDGE_BACKOFF_S = 15.0       # initial probe backoff; escalates to 60 s
COMMAND_CONFIRM_TIMEOUT_MS = 2000  # max wait for the game to consume a command file
COMMAND_CONFIRM_POLL_MS = 5        # polling granularity while confirming an order

# Quantitative Signal Constants
SIGNAL_STRONG_BUY = 2
SIGNAL_BUY = 1
SIGNAL_NEUTRAL = 0
SIGNAL_SHORT = -1
SIGNAL_STRONG_SHORT = -2

# Preset Configuration Profiles
PRESET_PROFILES: Dict[str, Dict[str, Any]] = {
    "TURBO": {
        "max_alloc_pct": 85.0,
        "stop_loss_pct": 15.0,
        "min_profit_pct": 6.0,
        "tech_target_x": 16.0,
        "max_positions": 5,
        "kelly_mult": 0.40,
        "description": "High-velocity compound snowball for accelerating early capital"
    },
    "GROWTH": {
        "max_alloc_pct": 40.0,
        "stop_loss_pct": 12.0,
        "min_profit_pct": 8.0,
        "tech_target_x": 18.0,
        "max_positions": 6,
        "kelly_mult": 0.25,
        "description": "Balanced trend continuation and alpha harvesting"
    },
    "DEFENSIVE": {
        "max_alloc_pct": 15.0,
        "stop_loss_pct": 4.0,
        "min_profit_pct": 4.0,
        "tech_target_x": 15.0,
        "max_positions": 3,
        "kelly_mult": 0.12,
        "description": "Strict capital shield with low drawdown tolerance"
    },
    "BILLIONAIRE": {
        "max_alloc_pct": 100.0,
        "stop_loss_enabled": False,
        "take_profit_enabled": False,
        "max_positions": 10,
        "kelly_mult": 0.50,
        "description": "Permanent dividend holding vault collecting compound interest per minute"
    }
}


def get_base_dir() -> str:
    """Returns application base directory, supporting PyInstaller bundles."""
    return getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_protobuf_paths() -> Tuple[str, str]:
    """Returns absolute paths to ticks and trades protobuf files."""
    base_dir = get_base_dir()
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    ticks_pb = os.path.join(data_dir, "otostoks_ticks.pb")
    trades_pb = os.path.join(data_dir, "otostoks_trades.pb")
    return ticks_pb, trades_pb


def get_settings_path() -> str:
    """Returns absolute path to persistent settings JSON file."""
    base_dir = get_base_dir()
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "settings.json")


def get_model_path() -> str:
    """Finds the active ONNX model.

    Order: OTOSTOKS_MODEL override, then the app directory, then the repository
    root (source checkout). The path is resolved at runtime rather than patched
    to a developer's machine, so a checkout works from any location.
    """
    override = os.environ.get("OTOSTOKS_MODEL")
    if override and os.path.exists(override):
        return os.path.abspath(override)

    base_dir = get_base_dir()
    candidates = [
        os.path.join(base_dir, "model.onnx"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model.onnx"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return os.path.join(base_dir, "model.onnx")


def find_available_port(preferred_port: int = 8080) -> int:
    """Finds an available local port starting from preferred_port without terminating other apps."""
    for p in range(preferred_port, preferred_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', p))
                return p
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


_GAME_EXE_CANDIDATES = ("Screen Stocks.exe", "ScreenStocks.exe", "screen_stocks.exe")
# Remember which name matched so the common case is a single lookup instead of
# three. Guarded implicitly: the value is only ever a name from the tuple above.
_matched_exe: Optional[str] = None


def check_game_process() -> Tuple[bool, Optional[int]]:
    """
    Checks if the Screen Stocks game executable is running.

    Uses a filtered, shell-free tasklist call. The upstream version ran
    `tasklist /FO CSV /NH` through cmd.exe and parsed every process on the
    machine: measured 158 ms per call versus 45 ms here. The answer feeds a UI
    badge, so it is also called from a worker thread rather than the event loop.
    """
    global _matched_exe
    if sys.platform != "win32":
        return False, None

    order = list(_GAME_EXE_CANDIDATES)
    if _matched_exe in order:
        order.remove(_matched_exe)
        order.insert(0, _matched_exe)

    for exe in order:
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"IMAGENAME eq {exe}", "/FO", "CSV", "/NH"],
                text=True, stderr=subprocess.DEVNULL,
            )
        except Exception:
            continue
        for line in out.splitlines():
            if not line.strip().startswith('"'):
                continue  # "INFO: No tasks are running..." when nothing matched
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) >= 2 and parts[1].strip().isdigit():
                _matched_exe = exe
                return True, int(parts[1].strip())
    return False, None


def launch_screen_stocks() -> Tuple[bool, str]:
    """Launches Screen Stocks via Steam protocol URL."""
    try:
        import webbrowser
        webbrowser.open(f"steam://rungameid/{STEAM_APP_ID}")
        return True, "Launched Screen Stocks via Steam"
    except Exception as e:
        return False, str(e)
