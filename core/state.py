import os
import json
import time
import threading
import collections
from datetime import datetime
from typing import Dict, Any, List, Set, Optional

from core.config import (
    get_protobuf_paths,
    get_settings_path,
    PRESET_PROFILES
)
from engine.automation import AutomationEngine
from core.daily_store import DailyStatsStore
import otostoks_proto as pb


class AppState:
    """
    Thread-safe unified state store for OtoStoksBot.
    Guarantees all properties are fully initialized and synchronized across
    the quantitative engine, HTTP bridge, and user dashboard.
    """
    def __init__(self):
        self.lock = threading.RLock()
        self.running: bool = True

        # Mode: AUTO (autonomous execution) vs SUGGESTION (alpha signals only)
        self.mode: str = "SUGGESTION"
        self.auto_mode_started_at: float = 0.0
        self.auto_time_remaining_str: str = "Unlimited"

        # Connection & Bridge State
        self.connected: bool = False
        self.game_bridge_connected: bool = False
        self.game_running: bool = False
        self.game_pid: Optional[int] = None
        self.server_tick: int = 0
        self.last_update_time: float = 0.0
        self.inf_latency_ms: float = 0.0

        # Capital & Portfolio Risk State
        self.reserved_cash: float = 0.0
        self.bot_managed_positions: Set[str] = set()
        self.position_peak_pnl: Dict[str, float] = {}
        self.position_peak_price: Dict[str, float] = {}
        self.position_trough_price: Dict[str, float] = {}
        self.entry_times: Dict[str, float] = {}
        self.last_order_time: Dict[str, float] = {}
        self.post_exit_cooldown: Dict[str, float] = {}

        # Risk Management & Circuit Breakers
        self.penalty_box: Dict[str, float] = {}
        self.circuit_breaker_until: float = 0.0
        self.consecutive_losses: int = 0

        # Player Data from Screen Stocks
        self.player: Dict[str, Any] = {
            "cash": "$0.00",
            "netWorth": "$0.00",
            "cashDouble": 0.0,
            "netWorthDouble": 0.0,
            "totalUnrealizedPnL": 0.0,
            "level": 1,
            "ipoCount": 0,
            "unlockedAchievementCount": 0
        }

        # Market & Universe State
        self.stocks: Dict[str, Dict[str, Any]] = {}
        self.unlocked_stocks: Set[str] = set()
        self.last_unlock_poll_time: float = 0.0
        self.signal_history: Dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque(maxlen=6))

        # Chart.js rolling series
        self.history_timestamps = collections.deque(maxlen=40)
        self.history_series: Dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque(maxlen=40))

        # Logs & Persistent History
        self.log_counter: int = 0
        self.logs: collections.deque = collections.deque(maxlen=100)
        self.trade_history: collections.deque = collections.deque(maxlen=300)

        # Performance Ledger
        self.session_trades_count: int = 0
        self.session_realized_pnl: float = 0.0
        self.session_wins: int = 0
        self.session_losses: int = 0
        self.active_strategy_preset: str = "TURBO"

        # Achievements Hunter
        self.achievements_enabled: bool = False
        self.achievement_budget_cap: float = 25.0
        self.micro_positions: Set[str] = set()
        self.achievements_stats: Dict[str, Any] = {
            "total_buys": 0,
            "total_sells": 0,
            "total_shorts": 0,
            "total_covers": 0,
            "max_single_profit_pct": 0.0,
            "unlocked_stocks_count": 0,
            "unlocked_achievements": 0
        }

        # Protocol Buffer Datastore & Auto-Trainer State
        self.ticks_pb_path, self.trades_pb_path = get_protobuf_paths()
        self.tick_buffer = collections.deque()
        self.total_ticks_stored: int = pb.count_ticks_in_file(self.ticks_pb_path)
        self.session_ticks_collected: int = 0
        self.retraining_status: str = "Ready"
        self.last_retrain_time: str = "Calibrating..."
        self.retrain_accuracy: Optional[float] = None
        self.auto_retrain_seconds_until_next: int = 60
        self.auto_retrain_count: int = 0
        self.retrain_started_at: float = 0.0
        self.retrain_est_seconds: float = 12.0
        self.inference_engine: Any = None

        # Dividend Vault & Special Events
        self.dividend_vault_active: bool = False
        self.dividend_income_per_min: float = 0.0
        self.total_dividends_received: float = 0.0
        self.base_crash_countdown_str: str = "Calculating..."
        self.is_base_crash_active: bool = False

        # Advanced Event Arbitrage & Auto Rules Engine (StockPilot-Inspired)
        self.automation_engine = AutomationEngine()
        self.daily_store = DailyStatsStore()
        self.scheduled_events: List[Dict[str, Any]] = []
        self.steam_news: List[Dict[str, Any]] = []
        self.event_arbitrage_occurrences: Dict[str, Dict[str, Any]] = {}
        self.rolling_prices: Dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque(maxlen=600))
        self.bridge_transport: str = "auto"

        # Configurable User Settings
        self.settings: Dict[str, Any] = {
            "max_positions": 5,
            "stop_loss_enabled": True,
            "stop_loss_pct": 15.0,
            "take_profit_enabled": True,
            "min_profit_pct": 6.0,
            "auto_time_limit_hours": 0.0,
            "tech_target_x": 16.0,
            "max_alloc_pct": 40.0,
            "background_tracking": False,
            "close_to_tray": True,
            "theme": "dark"
        }

        # Restore saved user settings from disk
        self._load_settings_from_disk()

    def next_log_id(self) -> int:
        with self.lock:
            self.log_counter += 1
            return self.log_counter

    def add_log(self, ticker: str, action: str, mode: str, reason: str, status: str):
        with self.lock:
            lid = self.next_log_id()
            self.logs.appendleft({
                "id": lid,
                "time": datetime.now().strftime("%H:%M:%S"),
                "ticker": ticker,
                "action": action.upper(),
                "mode": mode,
                "reason": reason,
                "status": status
            })

    def toggle_mode(self) -> str:
        """Toggles between AUTO and SUGGESTION mode. Never liquidates positions!"""
        with self.lock:
            if self.mode == "SUGGESTION":
                self.mode = "AUTO"
                self.auto_mode_started_at = time.time()
            else:
                self.mode = "SUGGESTION"
            current = self.mode

        self.add_log(
            ticker="SYSTEM",
            action="MODE_SWITCH",
            mode=current,
            reason=f"Operating mode switched to {current}",
            status="ACTIVE"
        )
        return current

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

    def update_settings(self, max_pos: int, stop_loss_enabled: bool, stop_loss: float,
                        take_profit_enabled: bool, min_profit: float, auto_hours: float,
                        tech_target_x: float = 16.0, max_alloc_pct: float = 40.0,
                        background_tracking: bool = False, close_to_tray: bool = True,
                        theme: str = "dark"):
        with self.lock:
            self.settings["max_positions"] = max(1, min(15, max_pos))
            self.settings["stop_loss_enabled"] = bool(stop_loss_enabled)
            self.settings["stop_loss_pct"] = max(0.0, min(100.0, stop_loss))
            self.settings["take_profit_enabled"] = bool(take_profit_enabled)
            self.settings["min_profit_pct"] = max(0.0, min(100.0, min_profit))
            self.settings["auto_time_limit_hours"] = max(0.0, min(48.0, auto_hours))
            self.settings["tech_target_x"] = max(10.0, min(60.0, tech_target_x))
            self.settings["max_alloc_pct"] = max(5.0, min(100.0, max_alloc_pct))
            self.settings["background_tracking"] = bool(background_tracking)
            self.settings["close_to_tray"] = bool(close_to_tray)
            self.settings["theme"] = str(theme)
            if self.mode == "AUTO":
                self.auto_mode_started_at = time.time()
            self._save_settings_to_disk()

    def apply_preset(self, preset_name: str) -> bool:
        p = preset_name.upper()
        if p not in PRESET_PROFILES:
            return False
        prof = PRESET_PROFILES[p]
        with self.lock:
            self.active_strategy_preset = p
            for k, v in prof.items():
                if k in self.settings:
                    self.settings[k] = v
            if p == "BILLIONAIRE":
                self.dividend_vault_active = True
                self.settings["stop_loss_enabled"] = False
                self.settings["take_profit_enabled"] = False
            self._save_settings_to_disk()
        return True

    def _save_settings_to_disk(self):
        try:
            settings_path = get_settings_path()
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def _load_settings_from_disk(self):
        try:
            settings_path = get_settings_path()
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.settings.update(data)
        except Exception:
            pass

    def get_snapshot(self) -> Dict[str, Any]:
        """Produces serialized state snapshot for REST API and WebSocket broadcast."""
        with self.lock:
            stock_list = sorted(self.stocks.values(), key=lambda s: s.get('ticker', ''))
            chart_series = {k: list(v) for k, v in self.history_series.items()}

            # Accurate win rate calculation (strict 0.0 when 0 wins and > 0 losses)
            tot_trades = self.session_wins + self.session_losses
            if tot_trades > 0:
                win_rate = round((self.session_wins / tot_trades) * 100.0, 1)
            else:
                win_rate = 0.0

            # Update achievements counts
            self.achievements_stats["unlocked_stocks_count"] = len(self.unlocked_stocks)
            self.achievements_stats["unlocked_achievements"] = self.player.get("unlockedAchievementCount", 0)

            return {
                "type": "state_update",
                "mode": self.mode,
                "achievements_enabled": self.achievements_enabled,
                "connected": self.connected,
                "game_connected": self.game_bridge_connected,
                "game_running": self.game_running,
                "game_pid": self.game_pid,
                "server_tick": self.server_tick,
                "inf_latency_ms": round(self.inf_latency_ms, 3),
                "auto_time_remaining": self.auto_time_remaining_str,
                "player": self.player,
                "stocks": stock_list,
                "unlocked_stocks": sorted(list(self.unlocked_stocks)),
                "history": {
                    "timestamps": list(self.history_timestamps),
                    "series": chart_series
                },
                "logs": list(self.logs),
                "settings": self.settings,
                "achievements_stats": self.achievements_stats,
                "micro_positions": list(self.micro_positions),
                "retrain_accuracy": self.retrain_accuracy,
                "reserved_cash": self.reserved_cash,
                "bot_managed_positions": list(self.bot_managed_positions),
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
                "scheduled_events": list(self.scheduled_events),
                "steam_news": list(self.steam_news),
                "daily_history": self.daily_store.get_past_7_days(),
                "stats_summary": self.daily_store.get_performance_analysis(self.trades_pb_path),
                "total_dividends": round(self.total_dividends_received, 2),
                "auto_rules": self.automation_engine.get_rules(),
                "bridge_transport": self.bridge_transport,
                "session_stats": {
                    "trades_count": self.session_trades_count,
                    "realized_pnl": round(self.session_realized_pnl, 2),
                    "win_rate": win_rate,
                    "wins": self.session_wins,
                    "losses": self.session_losses,
                    "active_preset": self.active_strategy_preset
                }
            }
