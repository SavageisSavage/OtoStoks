"""
engine/automation.py - User-Configurable Conditional Auto Actions Engine.
Inspired by institutional trigger rules:
Allows traders to set automated execution triggers:
e.g. "BUY $BASE when price is below 400 with 50% size",
     "SELL $PUMP when price is above 1200 with 100% size".
Supports one-shot execution, continuous repeat cycles, and persistent storage.
"""
import os
import json
import time
import threading
from typing import List, Dict, Any, Optional

from core.config import get_base_dir


class AutomationEngine:
    def __init__(self, data_file: Optional[str] = None):
        self.lock = threading.RLock()
        if not data_file:
            base_dir = get_base_dir()
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            data_file = os.path.join(data_dir, "automation.json")
        self.file_path = data_file
        self.rules: List[Dict[str, Any]] = []
        self.armed_state: Dict[str, bool] = {}
        self.last_fired_time: Dict[str, float] = {}
        self.load()

    def _rule_key(self, r: Dict[str, Any]) -> str:
        return f"{str(r.get('stock', '')).upper()}|{str(r.get('action', '')).lower()}|{str(r.get('when', '')).lower()}|{float(r.get('price', 0.0))}|{int(r.get('percent', 100))}"

    def load(self):
        with self.lock:
            if os.path.exists(self.file_path):
                try:
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        self.rules = data
                    elif isinstance(data, dict):
                        self.rules = data.get("rules", [])
                except Exception:
                    self.rules = []
            else:
                self.rules = []

    def save(self):
        with self.lock:
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump({"rules": self.rules}, f, indent=2)
            except Exception:
                pass

    def get_rules(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [dict(r) for r in self.rules]

    def add_rule(self, stock: str, action: str, when: str, price: float, percent: int = 100, repeat: bool = False) -> Dict[str, Any]:
        with self.lock:
            rid = f"rule_{int(time.time()*1000)}"
            rule = {
                "id": rid,
                "stock": stock.strip().upper(),
                "action": action.strip().lower(),
                "when": when.strip().lower(),
                "price": round(float(price), 4),
                "percent": max(1, min(100, int(percent))),
                "repeat": bool(repeat),
                "enabled": True,
                "created_at": time.strftime("%H:%M:%S")
            }
            self.rules.append(rule)
            self.save()
            return rule

    def remove_rule(self, rule_id: str) -> bool:
        with self.lock:
            before_len = len(self.rules)
            self.rules = [r for r in self.rules if r.get("id") != rule_id]
            if len(self.rules) != before_len:
                self.save()
                return True
            return False

    def toggle_rule(self, rule_id: str) -> Optional[bool]:
        with self.lock:
            for r in self.rules:
                if r.get("id") == rule_id:
                    r["enabled"] = not r.get("enabled", True)
                    self.save()
                    return r["enabled"]
            return None

    def evaluate(self, stocks_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluates active rules against live prices and yields executable orders.
        """
        now = time.time()
        triggered_orders = []

        with self.lock:
            for r in self.rules:
                if not r.get("enabled", True):
                    continue

                sid = r.get("stock", "").upper()
                s_info = stocks_data.get(sid) or stocks_data.get(sid.replace("$", ""))
                if not s_info:
                    continue

                curr_price = float(s_info.get("price", 0.0))
                if curr_price <= 0:
                    continue

                target_p = float(r.get("price", 0.0))
                when = r.get("when", "below")
                action = r.get("action", "buy").lower()
                pct = int(r.get("percent", 100))
                repeat = bool(r.get("repeat", False))
                key = r.get("id") or self._rule_key(r)

                condition_met = (curr_price <= target_p) if when == "below" else (curr_price >= target_p)

                if not condition_met:
                    # Arm the trigger for when it crosses the threshold
                    self.armed_state[key] = True
                    continue

                is_armed = self.armed_state.get(key, True)
                if not is_armed and not repeat:
                    continue

                # Zero-cooldown execution: fires immediately whenever condition holds
                # If repeat is True, allow rapid re-execution with no artificial delay
                self.armed_state[key] = False
                self.last_fired_time[key] = now
                is_max = (pct >= 100)

                triggered_orders.append({
                    "action": action,
                    "ticker": sid,
                    "amount": "max" if is_max else str(pct),
                    "isMax": is_max,
                    "reason": f"[AUTO RULE] {action.upper()} {sid} {pct}% when price {when} ${target_p:.2f} (Current: ${curr_price:.2f})"
                })

        return triggered_orders
