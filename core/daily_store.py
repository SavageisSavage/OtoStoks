"""
core/daily_store.py - Persistent 7-Day Performance & Investment Analytics.
Tracks daily net worth equity milestones, top investment harvests, and loss fumbles.
Generates comprehensive institutional CSV audits.
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from core.config import get_base_dir
import otostoks_proto as pb


class DailyStatsStore:
    def __init__(self, data_file: Optional[str] = None):
        if not data_file:
            base_dir = get_base_dir()
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            data_file = os.path.join(data_dir, "daily_stats.json")
        self.file_path = data_file
        self.daily_records: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.daily_records = data
            except Exception:
                self.daily_records = {}

    def save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.daily_records, f, indent=2)
        except Exception:
            pass

    def today_key(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def update_daily(self, net_worth: float, cash: float):
        """Updates today's starting, high, low, and current valuation milestones."""
        if net_worth <= 0:
            return
        dk = self.today_key()
        rec = self.daily_records.setdefault(dk, {
            "date": dk,
            "start": net_worth,
            "high": net_worth,
            "low": net_worth,
            "current": net_worth,
            "cash": cash,
            "last_updated": time.strftime("%H:%M:%S")
        })

        rec["high"] = max(rec.get("high", net_worth), net_worth)
        rec["low"] = min(rec.get("low", net_worth), net_worth)
        rec["current"] = net_worth
        rec["cash"] = cash
        rec["last_updated"] = time.strftime("%H:%M:%S")

        # Keep last 14 days
        if len(self.daily_records) > 14:
            sorted_keys = sorted(self.daily_records.keys())
            for old_k in sorted_keys[:-14]:
                del self.daily_records[old_k]

        self.save()

    def get_past_7_days(self) -> List[Dict[str, Any]]:
        """Returns sorted past 7 days records with net change and percentage gain."""
        sorted_keys = sorted(self.daily_records.keys())[-7:]
        out = []
        for k in sorted_keys:
            r = self.daily_records[k]
            st = float(r.get("start", 0.0))
            cur = float(r.get("current", st))
            diff = cur - st
            pct = ((cur - st) / st * 100.0) if st > 0 else 0.0
            out.append({
                "date": r.get("date", k),
                "start": st,
                "high": r.get("high", cur),
                "low": r.get("low", cur),
                "current": cur,
                "profit": diff,
                "pct": pct
            })
        return out

    def get_performance_analysis(self, trades_pb_path: str) -> Dict[str, Any]:
        """
        Parses all historical trades and identifies:
        - Good Investments (Top Winning Trades)
        - Fumbles (Biggest Losses / Missed Exits)
        - Overall Win/Loss ratios and Profit Factor
        """
        trades = pb.read_all_trades(trades_pb_path) if os.path.exists(trades_pb_path) else []
        wins = []
        fumbles = []
        total_won = 0.0
        total_lost = 0.0

        for r in trades:
            p_pct = float(r.profit_pct)
            # Only evaluate exit trades where pnl is finalized
            if r.action in ("SELL", "CLOSE", "COVER") and p_pct != 0.0:
                t_val = {
                    "trade_id": r.trade_id,
                    "timestamp": r.timestamp,
                    "time_str": datetime.fromtimestamp(r.timestamp / 1000.0 if r.timestamp > 1e11 else r.timestamp).strftime("%H:%M:%S") if r.timestamp else "-",
                    "ticker": r.ticker,
                    "action": r.action,
                    "price": float(r.price),
                    "amount": int(r.amount),
                    "profit_pct": p_pct,
                    "dollar_gain": round((p_pct / 100.0) * float(r.price) * int(r.amount), 2),
                    "reason": r.reason
                }
                if p_pct > 0:
                    wins.append(t_val)
                    total_won += t_val["dollar_gain"]
                else:
                    fumbles.append(t_val)
                    total_lost += abs(t_val["dollar_gain"])

        # Top 10 Best Investments
        wins.sort(key=lambda x: x["dollar_gain"], reverse=True)
        # Top 10 Worst Fumbles
        fumbles.sort(key=lambda x: x["dollar_gain"])

        profit_factor = (total_won / total_lost) if total_lost > 0 else (99.0 if total_won > 0 else 1.0)
        tot_closed = len(wins) + len(fumbles)
        win_rate = (len(wins) / tot_closed * 100.0) if tot_closed > 0 else 0.0

        return {
            "top_investments": wins[:10],
            "fumbles": fumbles[:10],
            "total_trades_count": len(trades),
            "closed_trades_count": tot_closed,
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "total_won_dollars": round(total_won, 2),
            "total_lost_dollars": round(total_lost, 2),
            "past_7_days": self.get_past_7_days()
        }
