import time
from typing import Dict, Any, Tuple, Optional
from core.state import AppState


def record_trade_outcome(state: AppState, ticker: str, realized_dollar: float, realized_pnl_pct: float):
    """
    Updates performance ledger, penalty box, and circuit breaker upon confirmed trade closing.
    """
    with state.lock:
        state.session_trades_count += 1
        state.session_realized_pnl += realized_dollar

        if realized_dollar >= 0:
            state.session_wins += 1
            state.consecutive_losses = 0
        else:
            state.session_losses += 1
            state.consecutive_losses += 1

            # 1. Individual Stock Penalty Box: 45s-105s based on severity
            penalty_duration = 45.0 + min(60.0, abs(realized_pnl_pct) * 2.0)
            state.penalty_box[ticker] = time.time() + penalty_duration
            state.add_log(
                ticker=ticker,
                action="PENALTY_BOX",
                mode=state.mode,
                reason=f"Drawdown of {realized_pnl_pct:.1f}%. Cooldown {penalty_duration:.0f}s active.",
                status="ACTIVE"
            )

            # 2. Portfolio-Wide Circuit Breaker: Triggered after 3 consecutive losses
            if state.consecutive_losses >= 3:
                state.circuit_breaker_until = time.time() + 60.0
                state.add_log(
                    ticker="PORTFOLIO",
                    action="CIRCUIT_BREAKER",
                    mode=state.mode,
                    reason=f"3 consecutive losses detected. 60s cooldown engaged to protect capital.",
                    status="ACTIVE"
                )


def is_entry_allowed(state: AppState, ticker: str) -> Tuple[bool, str]:
    """
    Checks if a new position can be opened for ticker under current portfolio risk rules.
    """
    now = time.time()

    # 1. Global Circuit Breaker Check
    if now < state.circuit_breaker_until:
        rem = int(state.circuit_breaker_until - now)
        return False, f"Circuit Breaker active ({rem}s remaining)"

    # 2. Individual Stock Penalty Box Check
    if now < state.penalty_box.get(ticker, 0.0):
        rem = int(state.penalty_box[ticker] - now)
        return False, f"Stock in Penalty Box ({rem}s remaining)"

    # 3. Post-Exit Cooldown (10s spacing between trades on same stock)
    if now < state.post_exit_cooldown.get(ticker, 0.0):
        rem = int(state.post_exit_cooldown[ticker] - now)
        return False, f"Post-exit spacing ({rem}s remaining)"

    return True, "OK"


def update_trailing_peaks(state: AppState, ticker: str, price: float, current_pnl_pct: float):
    """
    Maintains high-water mark peaks and low-water mark troughs.
    Never overwrites or pops peaks during order generation!
    """
    with state.lock:
        # Profit percentage peak
        peak_pnl = max(state.position_peak_pnl.get(ticker, current_pnl_pct), current_pnl_pct)
        state.position_peak_pnl[ticker] = peak_pnl

        # Price peaks and troughs
        peak_p = max(state.position_peak_price.get(ticker, price), price)
        state.position_peak_price[ticker] = peak_p

        trough_p = min(state.position_trough_price.get(ticker, price), price)
        state.position_trough_price[ticker] = trough_p


def check_protective_exits(state: AppState, ticker: str, price: float,
                           current_pnl_pct: float, has_long: bool, has_short: bool) -> Optional[Dict[str, Any]]:
    """
    Evaluates stop-loss, trailing profit protection, and breakeven defense.
    Returns exit order dictionary if trigger conditions are met.
    """
    stop_loss_enabled = state.settings.get("stop_loss_enabled", True)
    stop_loss_pct = state.settings.get("stop_loss_pct", 15.0)
    take_profit_enabled = state.settings.get("take_profit_enabled", True)
    min_profit_pct = state.settings.get("min_profit_pct", 6.0)

    # 1. Hard Stop-Loss Protection
    if stop_loss_enabled and current_pnl_pct <= -stop_loss_pct:
        act = "sell" if has_long else "cover"
        return {
            "action": act,
            "ticker": ticker,
            "amount": "max",
            "isMax": True,
            "reason": f"Protective Stop-Loss: Exit at {current_pnl_pct:.2f}% (Limit: -{stop_loss_pct:.1f}%)"
        }

    # 2. Dynamic Trailing Profit Ratchet
    peak_pnl = state.position_peak_pnl.get(ticker, current_pnl_pct)
    if take_profit_enabled and peak_pnl >= min_profit_pct:
        # If profit retraces 30% from peak above target, lock in gains
        drawdown_from_peak = peak_pnl - current_pnl_pct
        allowed_giveback = max(1.5, peak_pnl * 0.28)
        if drawdown_from_peak >= allowed_giveback and current_pnl_pct >= 2.0:
            act = "sell" if has_long else "cover"
            return {
                "action": act,
                "ticker": ticker,
                "amount": "max",
                "isMax": True,
                "reason": f"Trailing Profit Lock: Harvested +{current_pnl_pct:.1f}% (Peak was +{peak_pnl:.1f}%)"
            }

    return None


def clear_position_peaks(state: AppState, ticker: str):
    """Safely clears position peak tracking ONLY after confirmed execution."""
    with state.lock:
        state.position_peak_pnl.pop(ticker, None)
        state.position_peak_price.pop(ticker, None)
        state.position_trough_price.pop(ticker, None)
        state.post_exit_cooldown[ticker] = time.time() + 10.0
