import time
import asyncio
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple, Optional

from core.config import (
    SIGNAL_STRONG_BUY,
    SIGNAL_BUY,
    SIGNAL_NEUTRAL,
    SIGNAL_SHORT,
    SIGNAL_STRONG_SHORT
)
from core.state import AppState
from engine.bridge import dispatch_order, dispatch_order_http
from engine.risk import (
    record_trade_outcome,
    is_entry_allowed,
    update_trailing_peaks,
    check_protective_exits,
    clear_position_peaks
)
import otostoks_proto as pb


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
        is_in_crash = (-300 <= diff_sec <= 1200)

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


def record_trade_in_proto(trades_pb_path: str, ticker: str, action: str, price: float,
                          amount: int, profit_pct: Optional[float], reason: str):
    """Appends a confirmed trade record to persistent Protocol Buffer datastore."""
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
    except Exception:
        pass


def start_tick_storage_worker(state: AppState):
    """
    Background worker that flushes buffered market ticks to protobuf file every 1.2s.
    """
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
                except Exception:
                    pass

    t = threading.Thread(target=worker, daemon=True, name="TickStorageWorker")
    t.start()


def evaluate_portfolio(state: AppState, signals: Dict[str, Dict[str, Any]], tick_frame: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    High-expectancy portfolio risk and quantitative alpha decision engine.
    Produces atomic orders adhering to fractional Kelly sizing and capital constraints.
    """
    stocks = tick_frame.get('stocks', {})
    now = time.time()
    orders = []

    # Update $BASE 12:30 AM IST Crash Tracker
    is_crash, crash_countdown = is_base_crash_window()
    with state.lock:
        state.is_base_crash_active = is_crash
        state.base_crash_countdown_str = crash_countdown

    stop_loss_enabled = state.settings.get("stop_loss_enabled", True)
    stop_loss_pct = state.settings.get("stop_loss_pct", 15.0)
    take_profit_enabled = state.settings.get("take_profit_enabled", True)
    min_profit_pct = state.settings.get("min_profit_pct", 6.0)
    tech_target_x = state.settings.get("tech_target_x", 16.0)
    max_positions = state.settings.get("max_positions", 5)

    cash = state.player.get("cashDouble", 0.0)
    net_worth = max(state.player.get("netWorthDouble", cash), cash)

    # --------------------------------------------------------------------------
    # STRATEGY 2: BILLIONAIRE DIVIDEND VAULT
    # --------------------------------------------------------------------------
    preset = getattr(state, 'active_strategy_preset', 'TURBO')
    is_billionaire_tier = (net_worth >= 1_000_000_000 or cash >= 1_000_000_000) and (preset == "BILLIONAIRE")
    total_div_income = 0.0

    if is_billionaire_tier:
        with state.lock:
            state.dividend_vault_active = True

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

        # 1. Close open short positions (shorts don't earn dividends)
        for ticker, s in stocks.items():
            h = s.get('holding', {})
            shorted = float(h.get('sharesShortedDouble', 0.0))
            if shorted > 0 and (now - state.last_order_time.get(ticker, 0.0)) >= 2.0:
                orders.append({
                    'action': 'close',
                    'ticker': ticker,
                    'reason': 'Dividend Vault: Closing short position to redeploy capital into pure dividend yield'
                })

        # 2. Deploy available cash across top dividend stocks
        for div_rate, ticker, s in dividend_candidates:
            p = float(s.get('price', 0.0))
            if p <= 0: continue
            h = s.get('holding', {})
            owned = float(h.get('sharesOwnedDouble', 0.0))
            total_div_income += (owned * p * div_rate)

        if cash > 10_000 and dividend_candidates:
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

        return orders
    else:
        with state.lock:
            state.dividend_vault_active = False
            state.dividend_income_per_min = 0.0

    # --------------------------------------------------------------------------
    # PASS 0: USER CONDITIONAL AUTO ACTIONS (Trigger Rules)
    # --------------------------------------------------------------------------
    auto_orders = state.automation_engine.evaluate(stocks)
    if auto_orders:
        orders.extend(auto_orders)

    # --------------------------------------------------------------------------
    # PASS 0.5: SCHEDULED RESET ARBITRAGE (Screen Stocks Event Trader)
    # Anticipates scheduled news pumps and crashes published by the game engine
    # --------------------------------------------------------------------------
    scheduled_news = tick_frame.get('scheduledNews', [])
    server_time_ms = float(tick_frame.get('serverTimeMs', now * 1000.0))
    events_view = []

    for ev in scheduled_news:
        occ_id = str(ev.get("occurrenceId", ""))
        sid = str(ev.get("stockId", "")).strip()
        if not sid or sid not in stocks:
            continue
        curr_price = float(stocks[sid].get("price", 0.0))
        if curr_price <= 0:
            continue
        target_price = float(ev.get("targetPrice", 0.0))
        sched_at = float(ev.get("scheduledAtMs", 0.0))
        left_sec = (sched_at - server_time_ms) / 1000.0

        is_drop = (target_price < curr_price * 0.95)
        is_rise = (target_price > curr_price * 1.05)

        events_view.append({
            "id": occ_id,
            "stock": sid,
            "direction": "drop" if is_drop else ("rise" if is_rise else "reset"),
            "target": target_price,
            "left_seconds": max(0, int(left_sec)),
            "current_price": curr_price
        })

        if occ_id:
            occ = state.event_arbitrage_occurrences.setdefault(occ_id, {"pre": False, "post": False, "pos_type": None})

            # Act 35 seconds before event
            if not occ["pre"] and (0 < left_sec <= 35.0):
                h = stocks[sid].get("holding", {})
                owned = float(h.get("sharesOwnedDouble", 0.0))
                shorted = float(h.get("sharesShortedDouble", 0.0))

                if is_drop:
                    if owned > 0:
                        orders.append({
                            'action': 'close',
                            'ticker': sid,
                            'reason': f'[EVENT ARB] Liquidating long before scheduled crash to ${target_price:.2f}'
                        })
                    if shorted <= 0:
                        orders.append({
                            'action': 'short',
                            'ticker': sid,
                            'amount': 'max',
                            'reason': f'[EVENT ARB] Opening Short 35s before scheduled crash to ${target_price:.2f}'
                        })
                        occ["pos_type"] = "short"
                    occ["pre"] = True

                elif is_rise:
                    if owned <= 0:
                        orders.append({
                            'action': 'buy',
                            'ticker': sid,
                            'amount': 'max',
                            'reason': f'[EVENT ARB] Opening Long 35s before scheduled pump to ${target_price:.2f}'
                        })
                        occ["pos_type"] = "long"
                    occ["pre"] = True

            # Exit 12 seconds after event reset to lock in full profit
            if occ.get("pos_type") and not occ["post"] and (left_sec < -12.0):
                if occ["pos_type"] == "short":
                    orders.append({
                        'action': 'cover',
                        'ticker': sid,
                        'amount': 'max',
                        'reason': f'[EVENT ARB] Covering Short after reset to ${target_price:.2f} (Profit Harvested)'
                    })
                elif occ["pos_type"] == "long":
                    orders.append({
                        'action': 'sell',
                        'ticker': sid,
                        'amount': 'max',
                        'reason': f'[EVENT ARB] Selling Long after reset to ${target_price:.2f} (Profit Harvested)'
                    })
                occ["post"] = True

    with state.lock:
        state.scheduled_events = events_view

    # --------------------------------------------------------------------------
    # PASS 1: OPEN HOLDINGS MAINTENANCE & EXITS
    # --------------------------------------------------------------------------
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

        if has_long or has_short:
            if (now - state.last_order_time.get(ticker, 0.0)) < 3.0:
                continue

            current_pnl_pct = ((price - avg_buy) / avg_buy) * 100.0 if has_long else ((avg_short - price) / avg_short) * 100.0
            update_trailing_peaks(state, ticker, price, current_pnl_pct)

            peak_pnl = state.position_peak_pnl.get(ticker, current_pnl_pct)
            peak_price = state.position_peak_price.get(ticker, price)
            trough_price = state.position_trough_price.get(ticker, price)
            pos_age = now - state.entry_times.get(ticker, now)

            # 1. Protective stop-loss and trailing ratchet
            prot_exit = check_protective_exits(state, ticker, price, current_pnl_pct, has_long, has_short)
            if prot_exit:
                orders.append(prot_exit)
                continue

            # 2. Specialized Stock Personality Reversals
            if profile == "TECH":
                if has_long and price >= tech_target_x:
                    orders.append({
                        'action': 'close',
                        'ticker': ticker,
                        'reason': f'TECH Target X (${tech_target_x:.1f}) reached at ${price:.2f}! Selling long position'
                    })
                    orders.append({
                        'action': 'short',
                        'ticker': ticker,
                        'amount': 'max',
                        'reason': f'TECH Target X Reversal: Opening Short from peak ${price:.2f}'
                    })
                    continue
                elif has_short and (price <= 11.50 or (sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY) and price <= 12.50)):
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
                    continue
                continue

            elif profile == "PUMP":
                if has_long:
                    has_peaked = False
                    exit_reason = ""
                    if peak_price >= 50.0 and price <= (peak_price * 0.90):
                        has_peaked = True
                        exit_reason = f'PUMP Parabolic Peak Reached (${peak_price:.2f})! Locking massive profit'
                    elif peak_price >= 22.0 and (price <= (peak_price * 0.86) or price <= 18.0):
                        has_peaked = True
                        exit_reason = f'PUMP Vertical Peak Exhaustion (${peak_price:.2f})! Harvesting pump wave'
                    elif peak_price >= 14.0 and price <= (peak_price * 0.82) and current_pnl_pct >= 25.0:
                        has_peaked = True
                        exit_reason = f'PUMP Top Exhaustion (${peak_price:.2f})! Locking +{current_pnl_pct:.1f}% profit'

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
                            'reason': f'PUMP Crash Exploiter: Opening Short at peak ${peak_price:.2f} -> Riding dump to base'
                        })
                        continue

                elif has_short:
                    at_bottom = False
                    cover_reason = ""
                    if price <= 9.20:
                        at_bottom = True
                        cover_reason = f'PUMP Dump Bottom Reached at ${price:.2f}! Covering Short for maximum profit'
                    elif price <= 10.00 and trough_price <= 9.20 and price >= (trough_price * 1.12):
                        at_bottom = True
                        cover_reason = f'PUMP Rebound from Trough ${trough_price:.2f} to ${price:.2f}! Covering Short'

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
                            'reason': f'PUMP Dip Buy: Re-entering Long at bottom ${price:.2f}'
                        })
                        continue
                continue

            elif profile == "DUMP":
                if has_short:
                    at_bottom = False
                    exit_reason = ""
                    if price <= 5.50:
                        at_bottom = True
                        exit_reason = f'DUMP Bottom Reached at ${price:.2f}! Covering Short'
                    elif price <= 6.80 and trough_price <= 5.50 and price >= (trough_price * 1.15):
                        at_bottom = True
                        exit_reason = f'DUMP Rebound from Trough ${trough_price:.2f} to ${price:.2f}! Covering Short'

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
                            'reason': f'DUMP Rebound Buy: Opening Long at dump bottom ${price:.2f}'
                        })
                        continue

                elif has_long:
                    at_top = False
                    sell_reason = ""
                    if price >= 9.80:
                        at_top = True
                        sell_reason = f'DUMP Recovery Peak Reached at ${price:.2f}! Closing Long'
                    elif peak_price >= 9.80 and price <= (peak_price * 0.96) and current_pnl_pct >= 20.0:
                        at_top = True
                        sell_reason = f'DUMP Recovery Top Reached (${peak_price:.2f})! Locking +{current_pnl_pct:.1f}% profit'

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
                            'reason': f'DUMP Top Short: Reopening Short at peak ${price:.2f}'
                        })
                        continue
                continue

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
                    continue

            elif profile == "QUIK":
                sudden_dump = (current_pnl_pct < peak_pnl - 4.0 and peak_pnl >= 8.0)
                if has_long and sudden_dump:
                    orders.append({
                        'action': 'close',
                        'ticker': ticker,
                        'reason': f'QUIK Sudden Dump Guard: Securing +{current_pnl_pct:.1f}% profit'
                    })
                    continue

            elif profile == "BASE":
                if is_crash:
                    if has_long:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': 'BASE 12:30 AM IST Crash Active: Liquidating Long before crash'
                        })
                        continue
                    elif has_short and price <= 25.0:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': f'BASE Crash Bottom Reached (${price:.2f})! Covering Short'
                        })
                        orders.append({
                            'action': 'buy',
                            'ticker': ticker,
                            'amount': 'max',
                            'reason': f'BASE Post-Crash Rebound: Buying rock bottom (${price:.2f})'
                        })
                        continue
                continue

            # Standard Minimum Profit Harvest (generic stocks)
            if profile not in ("PUMP", "DUMP", "TECH", "BASE") and pos_age >= 10.0:
                if min_profit_pct > 0 and current_pnl_pct >= min_profit_pct:
                    should_exit = False
                    exit_reason = ""
                    if peak_pnl >= (min_profit_pct + 3.0):
                        if current_pnl_pct <= (peak_pnl - 2.5) and current_pnl_pct >= min_profit_pct:
                            should_exit = True
                            exit_reason = f'Trailing Runner Locked (+{current_pnl_pct:.2f}% secured, peak +{peak_pnl:.1f}%)'
                    else:
                        if take_profit_enabled:
                            should_exit = True
                            exit_reason = f'Min Profit Target Met (+{current_pnl_pct:.2f}%)'
                        else:
                            reversal = (sig in (SIGNAL_SHORT, SIGNAL_STRONG_SHORT)) if has_long else (sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY))
                            if reversal:
                                should_exit = True
                                exit_reason = f'Peak Reversal Harvest (+{current_pnl_pct:.2f}%)'

                    if should_exit:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': exit_reason
                        })
                        continue

            continue

        # Achievements Engine Micro-Trades
        if state.achievements_enabled:
            if ticker in state.micro_positions:
                pos_age = now - state.entry_times.get(ticker, now)
                if owned > 0 and pos_age >= 15.0:
                    gain = (price - avg_buy) / avg_buy if avg_buy > 0 else 0
                    if gain >= 0.005 or pos_age >= 35.0:
                        orders.append({
                            'action': 'close',
                            'ticker': ticker,
                            'reason': f'Achievement Micro-Harvest (+{gain*100:.1f}%, 1 share for Seller milestone)'
                        })
                        state.micro_positions.discard(ticker)
                        state.achievements_stats["total_sells"] += 1
                        continue

            micro_capital_used = sum(float(stocks.get(t, {}).get('price', 0.0)) for t in state.micro_positions)
            micro_budget = min(state.achievement_budget_cap, max(5.0, cash * 0.02))
            if owned == 0 and shorted == 0 and ticker not in state.micro_positions:
                if len(state.micro_positions) < 5 and (micro_capital_used + price) <= micro_budget and not circuit_active:
                    allowed, _ = is_entry_allowed(state, ticker)
                    if allowed and sig_data.get('expected_return', 0.0) >= 0.0:
                        orders.append({
                            'action': 'buy',
                            'ticker': ticker,
                            'amount': "1",
                            'reason': f'Achievement Engine: 1-share micro buy (Cost: ${price:.2f})'
                        })
                        state.entry_times[ticker] = now
                        state.micro_positions.add(ticker)
                        state.achievements_stats["total_buys"] += 1
                        continue

    # --------------------------------------------------------------------------
    # PASS 2: OPPORTUNITY SCREENING & CAPITAL SIZING
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
            if profile == "BANK":
                continue

            h = s.get('holding', {})
            owned = float(h.get('sharesOwnedDouble', 0.0))
            shorted = float(h.get('sharesShortedDouble', 0.0))
            if owned > 0 or shorted > 0:
                continue

            if (now - state.last_order_time.get(ticker, 0.0)) < 3.5:
                continue

            allowed, _ = is_entry_allowed(state, ticker)
            if not allowed:
                continue

            sig_data = signals.get(ticker, {})
            sig = sig_data.get('signal', SIGNAL_NEUTRAL)
            conf = sig_data.get('confidence', 0.0)
            exp_ret = sig_data.get('expected_return', 0.0)
            vol = sig_data.get('volatility', 0.015)

            score = 0.0
            action = 'buy'
            reason = ''

            if profile == "TECH":
                if price <= 12.20:
                    score = 98.0 + max(0.0, (12.20 - price) * 2.0)
                    action = 'buy'
                    reason = f'TECH Dip Buy Zone (${price:.2f} <= $12.20): Accumulating for Target X ${tech_target_x:.1f}'
                elif price >= tech_target_x:
                    score = 96.0 + min(3.0, (price - tech_target_x) * 1.5)
                    action = 'short'
                    reason = f'TECH Target X Peak (${price:.2f} >= ${tech_target_x:.1f}): Shorting peak retracement'

            elif profile == "PUMP":
                if price <= 9.80:
                    score = 98.5
                    action = 'buy'
                    reason = f'PUMP Base Accumulation (${price:.2f} <= $9.80): Buying flat baseline to ride upcoming pump'
                elif price >= 35.0 and sig in (SIGNAL_SHORT, SIGNAL_STRONG_SHORT):
                    score = 95.0
                    action = 'short'
                    reason = f'PUMP Parabolic Reversal (${price:.2f}): Shorting exhausted peak back down to base'

            elif profile == "DUMP":
                if price >= 9.80:
                    score = 96.0
                    action = 'short'
                    reason = f'DUMP Top Short (${price:.2f} >= $9.80): Shorting baseline before sharp drop'
                elif price <= 5.50:
                    score = 96.5
                    action = 'buy'
                    reason = f'DUMP Floor Rebound (${price:.2f} <= $5.50): Buying deep discount for recovery'

            elif profile == "BASE":
                if is_crash:
                    if price <= 25.0:
                        score = 99.0
                        action = 'buy'
                        reason = f'BASE 12:30 AM IST Crash Bottom (${price:.2f}): Generational dip buy at crash floor'
                    elif price >= 400.0:
                        score = 97.0
                        action = 'short'
                        reason = f'BASE 12:30 AM IST Crash Short (${price:.2f}): Shorting high price right before crash'
                else:
                    if price <= 440.0 and sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY):
                        score = 88.0
                        action = 'buy'
                        reason = f'BASE Player Dip Buy (${price:.2f} <= $440.0, outside crash window)'

            elif profile == "WAVE":
                if sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY) and conf >= 0.45:
                    score = 93.0
                    action = 'buy'
                    reason = f'WAVE Harmonic Trough (${price:.2f}): Buying lower swing boundary for upward cycle'
                elif sig in (SIGNAL_SHORT, SIGNAL_STRONG_SHORT) and conf >= 0.45:
                    score = 93.0
                    action = 'short'
                    reason = f'WAVE Harmonic Crest (${price:.2f}): Shorting upper swing boundary for downward cycle'

            elif profile == "STEP":
                div_rate = float(s.get('dividendRate', 0.02))
                if vol <= 0.025:
                    score = 91.0
                    action = 'buy'
                    reason = f'STEP Volatility Squeeze (${price:.2f}): Consolidation with {div_rate*100:.1f}% dividend rate'
                elif sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY):
                    score = 86.0
                    action = 'buy'
                    reason = f'STEP Upward Stair Breakout (${price:.2f})'

            elif profile == "QUIK":
                if sig == SIGNAL_STRONG_BUY and exp_ret >= 0.005:
                    score = 85.0
                    action = 'buy'
                    reason = f'QUIK Momentum Burst (${price:.2f}, Exp Ret: +{exp_ret*100:.1f}%)'

            else:
                if sig in (SIGNAL_BUY, SIGNAL_STRONG_BUY) and conf >= 0.55 and exp_ret >= 0.003:
                    score = 75.0 + min(15.0, conf * 20.0)
                    action = 'buy'
                    reason = f'Quant Trend Buy ({profile}, Conf: {conf*100:.0f}%, Exp Ret: +{exp_ret*100:.2f}%)'
                elif sig in (SIGNAL_SHORT, SIGNAL_STRONG_SHORT) and conf >= 0.55 and exp_ret <= -0.003:
                    score = 75.0 + min(15.0, conf * 20.0)
                    action = 'short'
                    reason = f'Quant Trend Short ({profile}, Conf: {conf*100:.0f}%, Exp Ret: {exp_ret*100:.2f}%)'

            # StockPilot-Inspired Rolling 5-Minute Moving Average Dip Buyer
            r_prices = state.rolling_prices.get(ticker)
            if r_prices and len(r_prices) >= 20:
                avg_5m = sum(r_prices) / len(r_prices)
                if avg_5m > 0 and price <= (avg_5m * 0.92):
                    dip_pct = ((avg_5m - price) / avg_5m) * 100.0
                    dip_score = 91.0 + min(7.0, dip_pct * 0.5)
                    if dip_score > score:
                        score = dip_score
                        action = 'buy'
                        reason = f'[DIP BUYER] Oversold Rebound ({dip_pct:.1f}% below 5m MA ${avg_5m:.2f})'

            if score >= 74.0:
                candidates.append({
                    'score': score,
                    'ticker': ticker,
                    'action': action,
                    'price': price,
                    'reason': reason
                })

        candidates.sort(key=lambda x: x['score'], reverse=True)

        for opp in candidates:
            if open_positions >= max_positions:
                break
            if available_cash < opp['price']:
                break

            score = opp['score']
            ticker = opp['ticker']
            action = opp['action']
            price = opp['price']
            opp_reason = opp['reason']

            sig_inf = signals.get(ticker, {})
            c_conf = max(0.40, min(0.96, sig_inf.get('confidence', score / 100.0)))
            b_ratio = max(1.2, min_profit_pct / max(1.0, stop_loss_pct))
            kelly_star = max(0.08, min(0.75, (c_conf * b_ratio - (1.0 - c_conf)) / b_ratio))

            preset_mult = 0.40 if preset == "TURBO" else (0.25 if preset == "GROWTH" else 0.12)
            t_vol = max(0.005, sig_inf.get('volatility', 0.015))
            vol_scale = min(1.35, max(0.65, 0.015 / t_vol))

            alloc_fraction = min(0.45, max(0.08, kelly_star * preset_mult * vol_scale * (score / 90.0)))
            alloc_amt = min(available_cash * alloc_fraction, available_cash * 0.85)

            effective_price = (price * 1.5) if action == "short" else price
            share_count = max(1, int(alloc_amt / effective_price)) if alloc_amt >= effective_price else 0
            share_count = min(share_count, 10_000_000)

            cost = share_count * price
            if share_count <= 0 or cost > available_cash:
                continue

            available_cash -= cost
            open_positions += 1

            orders.append({
                'action': action,
                'ticker': ticker,
                'amount': str(share_count),
                'reason': f'[ALPHA {score:.0f}/100] {opp_reason} (Allocated: {share_count:,} shares, ${cost:,.2f})'
            })

    return orders


async def execute_single_order(state: AppState, ord_item: Dict[str, Any], stocks_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Executes a single trade order via the HTTP bridge with cash reservation and verification.
    """
    t_ticker = ord_item['ticker']
    t_action = ord_item['action'].upper()
    t_reason = ord_item.get('reason', '')
    t_price = float(stocks_data.get(t_ticker, {}).get('price', 0.0))
    est_shares = int(ord_item.get('amount', 1)) if str(ord_item.get('amount', '')).isdigit() else 1
    est_cost = est_shares * t_price

    # Reserve capital atomically
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
        trade_res = await asyncio.to_thread(dispatch_order, payload)

        if trade_res and trade_res.get("success") is True:
            fill_p = float(trade_res.get('filledPrice') or t_price or 0.0)
            fill_shares = int(trade_res.get('shares') or est_shares) if str(trade_res.get('shares') or est_shares).isdigit() else 1

            with state.lock:
                state.last_order_time[t_ticker] = time.time()
                if t_action == "BUY":
                    state.bot_managed_positions.add(t_ticker)
                    state.entry_times[t_ticker] = time.time()
                    state.position_peak_price[t_ticker] = fill_p
                    state.position_trough_price[t_ticker] = fill_p
                    state.achievements_stats["total_buys"] += 1
                elif t_action == "SHORT":
                    state.bot_managed_positions.add(t_ticker)
                    state.entry_times[t_ticker] = time.time()
                    state.position_peak_price[t_ticker] = fill_p
                    state.position_trough_price[t_ticker] = fill_p
                    state.achievements_stats["total_shorts"] += 1
                elif t_action in ("SELL", "CLOSE", "COVER"):
                    state.bot_managed_positions.discard(t_ticker)
                    clear_position_peaks(state, t_ticker)
                    if t_action in ("SELL", "CLOSE"):
                        state.achievements_stats["total_sells"] += 1
                    else:
                        state.achievements_stats["total_covers"] += 1

            # Performance ledger calculations
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

                record_trade_outcome(state, t_ticker, realized_dollar, realized_pnl_val)

            state.add_log(t_ticker, t_action, "AUTO", f"{t_reason} | Executed at ${fill_p:.2f} x{fill_shares:,}", "EXECUTED")
            record_trade_in_proto(state.trades_pb_path, t_ticker, t_action, fill_p, fill_shares, realized_pnl_val, t_reason)
            state.trade_history.append({
                "id": payload["id"],
                "time": datetime.now().strftime('%H:%M:%S'),
                "ticker": t_ticker,
                "action": t_action,
                "price": f"${fill_p:.2f}",
                "amount": f"{fill_shares:,}",
                "pnl": f"{realized_pnl_val:+.1f}%" if realized_pnl_val is not None else "-",
                "reason": t_reason
            })
            return trade_res
        else:
            msg = trade_res.get("message", "Bridge rejected order") if trade_res else "Game bridge timed out"
            state.add_log(t_ticker, t_action, "AUTO", f"{t_reason} (Rejected: {msg})", "REJECTED")
            return None
    finally:
        if t_action in ("BUY", "SHORT"):
            with state.lock:
                state.reserved_cash = max(0.0, state.reserved_cash - est_cost)


async def execute_orders_batch(state: AppState, orders: List[Dict[str, Any]], stocks_data: Dict[str, Any]):
    """
    Dispatches orders across different tickers concurrently in parallel for maximum speed,
    while ensuring sequential execution for reversals on the SAME ticker
    (await close confirmation BEFORE opening the opposite position).
    """
    if not orders:
        return

    # Group orders by ticker
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for ord_item in orders:
        ticker = ord_item['ticker']
        if ticker not in grouped:
            grouped[ticker] = []
        grouped[ticker].append(ord_item)

    async def _execute_ticker_sequence(ticker_orders: List[Dict[str, Any]]):
        for o in ticker_orders:
            res = await execute_single_order(state, o, stocks_data)
            # If closing order of a reversal failed, do NOT open the opposite position!
            if o['action'].lower() in ('close', 'sell', 'cover') and len(ticker_orders) > 1:
                if not res or res.get('success') is not True:
                    break
                await asyncio.sleep(0.05)

    # Dispatch across all unique tickers concurrently in parallel
    await asyncio.gather(*[_execute_ticker_sequence(ticker_orders) for ticker_orders in grouped.values()])
