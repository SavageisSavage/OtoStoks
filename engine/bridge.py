import os
import sys
import time
import json
import shutil
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple

from core.config import (
    get_base_dir,
    check_game_process,
    COMMAND_CONFIRM_TIMEOUT_MS,
    HTTP_BRIDGE_BACKOFF_S,
    SNAPSHOT_STALE_S,
)
from core.game_mod import (
    find_game_dir,
    get_game_paths,
    ensure_native_mod_support,
    read_native_market_file,
    dispatch_native_order,
    wait_command_consumed,
    MarketFileWatcher,
)

# Active bridge transport mode: 'http', 'native_mod', or None
CURRENT_TRANSPORT = "http"

# The HTTP bridge only exists when the BepInEx DLL is loaded into the game. Probing
# a closed port on every loop iteration costs a connection attempt, and if the port
# is filtered rather than refused it costs the full timeout. Back off instead, and
# escalate so a filtered port cannot cost 600 ms on a fixed schedule forever.
_http_fails: int = 0
_http_backoff_until: float = 0.0
_http_backoff_s: float = HTTP_BRIDGE_BACKOFF_S
_HTTP_BACKOFF_MAX_S: float = 60.0

# Shared change-driven reader for the native export file.
FILE_WATCHER = MarketFileWatcher()



def run_auto_installer() -> Tuple[bool, str]:
    """
    Auto-detects Steam installation of Screen Stocks and updates BepInEx plugins DLL,
    and simultaneously configures official native mod support.
    """
    # 1. Official Native Mod Support
    mod_ok, mod_msg = ensure_native_mod_support()

    # 2. BepInEx DLL Auto-Installation
    base_dir = get_base_dir()
    dll_candidates = [
        os.path.join(base_dir, "OtoStoksBridge.dll"),
        os.path.join(base_dir, "OtoStoksBotBridge.dll"),
        os.path.join(base_dir, "ScreenStocksLocalBridge.dll"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "OtoStoksBridge.dll"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ScreenStocksLocalBridge.dll")
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

    dll_msg = ""
    if src_dll and target_dir:
        try:
            os.makedirs(target_dir, exist_ok=True)
            dest_candidates = [
                os.path.join(target_dir, "OtoStoksBridge.dll"),
                os.path.join(target_dir, "ScreenStocksLocalBridge.dll")
            ]
            active_dest = next((p for p in dest_candidates if os.path.exists(p)), dest_candidates[0])
            try:
                shutil.copy2(src_dll, active_dest)
                dll_msg = f"OtoStoksBridge DLL synced."
            except Exception:
                dll_msg = "Bridge DLL already loaded in game."
        except Exception as e:
            dll_msg = f"DLL sync notice: {e}"
    else:
        dll_msg = "Running via Native Mod Interface."

    return True, f"{mod_msg} | {dll_msg}"


def _note_http_failure() -> None:
    """
    Escalating backoff after a failed probe.

    No attempt is made to distinguish a refused connection from a filtered one:
    on Windows a closed local port can take about a second to refuse, so the only
    safe assumption is that a failed probe is expensive. The backoff escalates and
    is capped, so a bridge that appears later is still picked up within a minute.
    """
    global _http_fails, _http_backoff_until, _http_backoff_s
    _http_fails += 1
    _http_backoff_until = time.time() + _http_backoff_s
    _http_backoff_s = min(_http_backoff_s * 2.0, _HTTP_BACKOFF_MAX_S)


def fetch_snapshot_http(host: str = "127.0.0.1", port: int = 8765, timeout: float = 0.8) -> Optional[Dict[str, Any]]:
    """Fetches full market and portfolio snapshot from in-game HTTP server."""
    global _http_fails, _http_backoff_until, _http_backoff_s

    if time.time() < _http_backoff_until:
        return None

    try:
        req = urllib.request.Request(f"http://{host}:{port}/snapshot")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and data.get("marketReady", False):
                data["source"] = "http_bridge"
                _http_fails = 0
                _http_backoff_until = 0.0
                _http_backoff_s = HTTP_BRIDGE_BACKOFF_S
                return data
    except Exception:
        _note_http_failure()
        return None

    _note_http_failure()
    return None


def fetch_snapshot(host: str = "127.0.0.1", port: int = 8765) -> Optional[Dict[str, Any]]:
    """
    Universal snapshot fetcher:
    1. Tries HTTP Bridge (fastest socket/memory bridge when loaded).
    2. Falls back seamlessly to Native Mod File (mods/export/market.json).
    """
    global CURRENT_TRANSPORT
    # 1. Try HTTP Bridge
    snap = fetch_snapshot_http(host=host, port=port, timeout=0.6)
    if snap and snap.get("marketReady", False):
        CURRENT_TRANSPORT = "http"
        return snap

    # 2. Try Native Mod File
    native_snap = read_native_market_file()
    if native_snap and native_snap.get("marketReady", False):
        CURRENT_TRANSPORT = "native_mod"
        return native_snap

    return None


def fetch_snapshot_change(allow_http: bool = True) -> Tuple[bool, Optional[Dict[str, Any]], Optional[float]]:
    """
    Change-driven variant of fetch_snapshot() for the main loop.

    Returns (changed, snapshot, age_ms). On the native transport `changed` is False
    whenever the game has not rewritten market.json, which lets the loop skip
    parsing, feature extraction and inference for a frame it already processed.
    The HTTP bridge exposes no file signature, so when it is live every call is
    treated as a new frame.

    allow_http=False skips the bridge probe for one iteration, so the first native
    frame is not delayed by a probe that usually costs a socket timeout.
    """
    global CURRENT_TRANSPORT

    if allow_http:
        snap = fetch_snapshot_http(timeout=0.6)
        if snap and snap.get("marketReady", False):
            CURRENT_TRANSPORT = "http"
            return True, snap, 0.0

    changed, native_snap, age_ms = FILE_WATCHER.poll()
    if changed and native_snap:
        CURRENT_TRANSPORT = "native_mod"
        return True, native_snap, age_ms

    return False, None, age_ms


def reconcile_order_status(ticker: str, action: str) -> Optional[Dict[str, Any]]:
    """
    Checks snapshot after a timed-out dispatch to verify if the trade was already filled in-game,
    preventing duplicate execution on retry.
    """
    return _reconcile_from_snapshot(fetch_snapshot(), ticker, action)


def _reconcile_from_snapshot(snap: Optional[Dict[str, Any]], ticker: str, action: str) -> Optional[Dict[str, Any]]:
    """Position check against an already-parsed snapshot (no extra fetch)."""
    if not snap or "stocks" not in snap:
        return None

    stock_info = snap["stocks"].get(ticker, {})
    holding = stock_info.get("holding", {})
    owned = float(holding.get("sharesOwnedDouble", 0.0))
    shorted = float(holding.get("sharesShortedDouble", 0.0))
    act = action.lower()

    if act in ("close", "sell") and owned == 0.0:
        return {
            "success": True,
            "message": "Reconciled via snapshot: Position closed",
            "filledPrice": stock_info.get("price", 0.0),
            "shares": 0
        }
    if act in ("close", "cover") and shorted == 0.0:
        return {
            "success": True,
            "message": "Reconciled via snapshot: Short covered",
            "filledPrice": stock_info.get("price", 0.0),
            "shares": 0
        }
    if act == "buy" and owned > 0:
        return {
            "success": True,
            "message": "Reconciled via snapshot: Long position confirmed",
            "filledPrice": stock_info.get("price", 0.0),
            "shares": owned
        }
    if act == "short" and shorted > 0:
        return {
            "success": True,
            "message": "Reconciled via snapshot: Short position confirmed",
            "filledPrice": stock_info.get("price", 0.0),
            "shares": shorted
        }
    return None


def dispatch_order_http(order_payload: Dict[str, Any], host: str = "127.0.0.1", port: int = 8765) -> Optional[Dict[str, Any]]:
    """
    Dispatches order to in-game bridge with timeout reconciliation.
    Never blindly retries an order that may have already executed!
    """
    url = f"http://{host}:{port}/trade"
    data_bytes = json.dumps(order_payload).encode('utf-8')
    ticker = order_payload.get("ticker", "")
    action = order_payload.get("action", "")

    for attempt in range(2):
        try:
            req = urllib.request.Request(url, data=data_bytes, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                return res
        except Exception:
            if attempt == 0:
                # Reconcile with game state before retrying!
                reconciled = reconcile_order_status(ticker, action)
                if reconciled:
                    return reconciled
                time.sleep(0.02)
                continue
            return None
    return None


def dispatch_order(order_payload: Dict[str, Any], host: str = "127.0.0.1", port: int = 8765) -> Optional[Dict[str, Any]]:
    """
    Universal order dispatcher:
    Uses HTTP bridge if current transport is HTTP; otherwise uses Native Mod command files.
    """
    global CURRENT_TRANSPORT
    ticker = order_payload.get("ticker", "")
    action = order_payload.get("action", "")
    amount = order_payload.get("amount", "max")
    is_max = (amount == "max" or order_payload.get("isMax", False))

    if CURRENT_TRANSPORT == "http":
        res = dispatch_order_http(order_payload, host=host, port=port)
        if res:
            return res

    # Native Mod Command dispatch fallback
    t_dispatch = time.perf_counter()
    ok, msg, cmd_path = dispatch_native_order(ticker, action, amount, is_max=is_max)
    if not ok:
        return {"success": False, "message": msg}

    # Wait for the game to actually pick the command up rather than sleeping a
    # fixed 120 ms and hoping. This is the real order-pickup latency.
    pickup_ms = wait_command_consumed(cmd_path)
    if pickup_ms is None:
        return {
            "success": False,
            "message": f"{msg} (game did not consume the command within {COMMAND_CONFIRM_TIMEOUT_MS} ms)",
        }

    # The resulting position only becomes visible in a later export frame. Use a
    # private watcher so this does not steal frames from the main loop.
    deadline = time.perf_counter() + 0.35
    confirm_watcher = MarketFileWatcher()
    reconciled = None
    while time.perf_counter() < deadline:
        changed, snap, _ = confirm_watcher.poll()
        if changed and snap:
            reconciled = _reconcile_from_snapshot(snap, ticker, action)
            if reconciled:
                break
        time.sleep(0.01)

    dispatch_ms = (time.perf_counter() - t_dispatch) * 1000.0
    if reconciled:
        reconciled["pickupMs"] = round(pickup_ms, 3)
        reconciled["dispatchMs"] = round(dispatch_ms, 3)
        return reconciled

    return {
        "success": True,
        "message": msg,
        "filledPrice": 0.0,
        "shares": 0,
        "pickupMs": round(pickup_ms, 3),
        "dispatchMs": round(dispatch_ms, 3),
    }


def check_bridge_health(host: str = "127.0.0.1", port: int = 8765) -> bool:
    """Pre-flight check to verify if either the HTTP bridge or Native Mod interface is responding."""
    snap = fetch_snapshot(host=host, port=port)
    return snap is not None and snap.get("marketReady", False)
