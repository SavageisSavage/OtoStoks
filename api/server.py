import os
import sys
import io
import csv
import time
import base64
import asyncio
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from core.models import ManualTradePayload, SettingsPayload, PresetPayload
from core.state import AppState
from core.config import (
    get_base_dir,
    get_model_path,
    launch_screen_stocks,
    check_game_process,
    BROADCAST_IDLE_S,
    POLL_IDLE_S,
    PROCESS_CHECK_INTERVAL_S,
)
from core.steam_news import fetch_steam_news, start_steam_news_poller
from core.game_mod import (
    read_in_game_settings,
    save_in_game_settings,
    list_skins,
    install_skin,
    delete_skin,
    equip_skin
)
from ui.dashboard import DASHBOARD_HTML
from engine.features import FastFeatureTracker
from engine.ml_engine import LocalModelEngine, run_retrain_pipeline, start_auto_retrain_worker
from engine.latency import PIPELINE, timed
from engine.bridge import (
    fetch_snapshot,
    fetch_snapshot_http,
    fetch_snapshot_change,
    dispatch_order,
    dispatch_order_http,
    run_auto_installer,
    check_bridge_health,
    FILE_WATCHER,
)
from engine.strategy import evaluate_portfolio, execute_orders_batch, record_trade_in_proto, start_tick_storage_worker
import otostoks_proto as pb


def create_app(state: AppState) -> FastAPI:
    active_websockets: List[WebSocket] = []
    ws_lock = asyncio.Lock()

    async def broadcast_state():
        if not active_websockets:
            return
        snapshot = state.get_snapshot()
        disconnected = []
        async with ws_lock:
            for ws in active_websockets:
                try:
                    await ws.send_json(snapshot)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                if ws in active_websockets:
                    active_websockets.remove(ws)

    async def game_bridge_loop():
        # Pre-flight check & DLL auto-installer
        run_auto_installer()

        # Load ML Engine
        model_path = get_model_path()
        model = LocalModelEngine(model_path)
        state.inference_engine = model
        tracker = FastFeatureTracker(max_history=120)

        # Start background storage and learning workers
        start_tick_storage_worker(state)
        start_auto_retrain_worker(state)
        start_steam_news_poller(state)

        last_process_check = 0.0
        last_broadcast = 0.0
        iteration = 0
        prev_cash: Optional[float] = None
        prev_ipo: Optional[int] = None

        while state.running:
            cycle_start = time.perf_counter()
            now = time.time()

            # Process status check every 2 s. tasklist spawns a process, and this used
            # to run directly on the event loop thread: every 2 s the loop stalled for
            # tens of milliseconds, delaying in-flight orders and websocket traffic.
            # Skipped on the first iteration so a slow probe cannot delay frame one.
            if iteration > 0 and (now - last_process_check) >= PROCESS_CHECK_INTERVAL_S:
                last_process_check = now
                is_running, pid = await asyncio.to_thread(check_game_process)
                state.game_running = is_running
                state.game_pid = pid

            # Auto Mode Time Limit Check (Never liquidates on timeout!)
            if state.mode == "AUTO":
                limit_hours = state.settings.get("auto_time_limit_hours", 0.0)
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
                        state.add_log(
                            ticker="SYSTEM",
                            action="AUTO_TIMEOUT",
                            mode="SUGGESTION",
                            reason=f"Auto mode time limit of {limit_hours}h reached. Reverted to Suggestion Mode safely.",
                            status="EXPIRED"
                        )
                else:
                    state.auto_time_remaining_str = "Unlimited"
            else:
                state.auto_time_remaining_str = "Inactive (Suggestion Mode)"

            # Wait for a NEW market frame. There is no fixed 120 ms sleep: the game
            # republishes market.json about once per second (measured median 1002 ms),
            # so an unchanged file costs one stat() and the loop yields again.
            with timed("snapshot_wait"):
                changed, data, age_ms = await asyncio.to_thread(fetch_snapshot_change, iteration > 0)
            iteration += 1

            if not changed:
                if state.connected and FILE_WATCHER.is_stale(age_ms):
                    state.connected = False
                    state.game_bridge_connected = False
                    state.add_log(
                        ticker="BRIDGE",
                        action="STALE",
                        mode=state.mode,
                        reason="Screen Stocks stopped publishing market data",
                        status="OFFLINE"
                    )
                if (time.time() - last_broadcast) >= BROADCAST_IDLE_S:
                    last_broadcast = time.time()
                    state.pipeline_metrics = PIPELINE.snapshot()
                    await broadcast_state()
                await asyncio.sleep(POLL_IDLE_S)
                continue

            if data is None or not data.get("marketReady", False):
                state.connected = False
                state.game_bridge_connected = False
                await asyncio.sleep(0.05)
                continue

            state.last_update_time = time.time()

            state.bridge_transport = data.get("source", "native_mod")

            if not state.connected:
                state.connected = True
                state.game_bridge_connected = True
                state.game_running = True
                trans_label = "Screen Stocks Native Mod" if state.bridge_transport == "native_mod" else "Screen Stocks Local Bridge"
                state.add_log(
                    ticker="BRIDGE",
                    action="CONNECT",
                    mode=state.mode,
                    reason=f"Synchronized with {trans_label}",
                    status="ONLINE"
                )

            # Sync unlocked universe
            raw_unlocked = set(data.get("unlockedStocks", []))
            if not raw_unlocked and "stocks" in data:
                raw_unlocked = set(data["stocks"].keys())
            if raw_unlocked and raw_unlocked != state.unlocked_stocks:
                newly = raw_unlocked - state.unlocked_stocks
                if newly:
                    state.add_log("STATS", "STOCK_UNLOCKED", state.mode, f"New stocks unlocked: {', '.join(newly)}", "UNLOCKED")
                state.unlocked_stocks = raw_unlocked

            # Sync player state
            state.server_tick = data.get("serverTick", 0)
            player = data.get("player", {})
            curr_cash = float(player.get("cashDouble", 0.0))
            curr_ipo = player.get("ipoCount", 0)

            # Passive Dividend Income Detection
            if prev_cash is not None and curr_cash > (prev_cash + 0.05) and curr_ipo == prev_ipo:
                recent_sales = any((now - state.last_order_time.get(t, 0.0) < 2.5) for t in state.stocks)
                if not recent_sales:
                    div_amount = curr_cash - prev_cash
                    state.total_dividends_received += div_amount
                    state.add_log(
                        ticker="DIVIDEND",
                        action="PAYOUT",
                        mode=state.mode,
                        reason=f"Dividend distribution: +${div_amount:,.2f}",
                        status="CREDITED"
                    )
            prev_cash = curr_cash
            prev_ipo = curr_ipo

            state.player = {
                "cash": f"${curr_cash:,.2f}",
                "netWorth": f"${float(player.get('netWorthDouble', 0)):,.2f}",
                "cashDouble": curr_cash,
                "netWorthDouble": float(player.get('netWorthDouble', 0)),
                "totalUnrealizedPnL": float(player.get('totalUnrealizedPnL', 0.0)),
                "level": player.get("level", 1),
                "ipoCount": curr_ipo,
                "unlockedAchievementCount": player.get("unlockedAchievementCount", 0)
            }
            state.daily_store.update_daily(float(player.get('netWorthDouble', 0)), curr_cash)

            stocks_data = data.get("stocks", {})
            signals = {}
            timestamp_str = datetime.now().strftime("%H:%M:%S")
            state.history_timestamps.append(timestamp_str)

            # Pass 1: roll each ticker forward and build its feature vector.
            pending = []
            feat_rows = []
            feat_slot = {}
            t_feat = time.perf_counter()
            for ticker, s in stocks_data.items():
                if state.unlocked_stocks and ticker not in state.unlocked_stocks:
                    continue

                curr_price = float(s.get("price", 0.0))
                if curr_price <= 0:
                    continue

                # Buffer tick for protobuf storage
                state.tick_buffer.append((ticker, int(time.time() * 1000), curr_price))
                state.history_series[ticker].append(curr_price)
                state.rolling_prices[ticker].append(curr_price)

                # Unified 16-feature calculation (requires >= 30 ticks)
                feat = tracker.update(ticker, curr_price)
                slot = len(pending)
                pending.append((ticker, s, feat, curr_price))
                if feat is not None:
                    feat_slot[slot] = len(feat_rows)
                    feat_rows.append(feat)
            PIPELINE.record("features", (time.perf_counter() - t_feat) * 1000.0)

            # Pass 2: one ONNX call for the whole universe instead of one per ticker.
            t_inf = time.perf_counter()
            predictions = model.predict_batch(feat_rows) if feat_rows else []
            inf_ms = (time.perf_counter() - t_inf) * 1000.0
            PIPELINE.record("inference", inf_ms)
            if feat_rows:
                state.inf_latency_ms = inf_ms / len(feat_rows)

            for slot, (ticker, s, feat, curr_price) in enumerate(pending):
                if feat is not None and slot in feat_slot:
                    exp_ret, sig, conf, regime = predictions[feat_slot[slot]]
                    vol = float(feat[4])
                else:
                    exp_ret, sig, conf, regime, vol = 0.0, 0, 0.0, "INITIALIZING", 0.015

                signals[ticker] = {
                    "signal": sig,
                    "confidence": conf,
                    "expected_return": exp_ret,
                    "regime": regime,
                    "volatility": vol
                }

                # Update in-memory stock view
                holding_info = s.get("holding", {})
                owned_shares = float(holding_info.get("sharesOwnedDouble", 0.0))
                shorted_shares = float(holding_info.get("sharesShortedDouble", 0.0))
                holding_str = "FLAT"
                avg_p = 0.0
                if owned_shares > 0:
                    holding_str = f"LONG ({int(owned_shares):,})"
                    avg_p = float(holding_info.get("averageBuyPrice", 0.0))
                elif shorted_shares > 0:
                    holding_str = f"SHORT ({int(shorted_shares):,})"
                    avg_p = float(holding_info.get("averageShortPrice", 0.0))

                signal_name = "NEUTRAL"
                if sig == 2: signal_name = "STRONG_BUY"
                elif sig == 1: signal_name = "BUY"
                elif sig == -1: signal_name = "SHORT"
                elif sig == -2: signal_name = "STRONG_SHORT"

                state.stocks[ticker] = {
                    "ticker": ticker,
                    "name": s.get("name", ticker),
                    "price": curr_price,
                    "signal": signal_name,
                    "signal_code": sig,
                    "confidence": round(conf * 100.0, 1),
                    "expected_return": round(exp_ret * 100.0, 2),
                    "regime": regime,
                    "holding": holding_str,
                    "avg_price": avg_p,
                    "dividendRate": float(s.get("dividendRate", 0.0)),
                    "sparkline": list(state.history_series[ticker])[-20:]
                }

            # Evaluate Portfolio
            with timed("decision"):
                orders = evaluate_portfolio(state, signals, data)

            if orders:
                if state.mode == "AUTO":
                    # Dispatches independent stocks in parallel, sequential reversals per stock
                    with timed("dispatch"):
                        await execute_orders_batch(state, orders, stocks_data)
                else:
                    for order in orders:
                        state.add_log(
                            ticker=order['ticker'],
                            action=f"REC: {order['action'].upper()}",
                            mode="SUGGESTION",
                            reason=order.get('reason', ''),
                            status="RECOMMENDED"
                        )

            PIPELINE.record("cycle", (time.perf_counter() - cycle_start) * 1000.0)
            state.pipeline_metrics = PIPELINE.snapshot()
            last_broadcast = time.time()
            await broadcast_state()
            # Yield, then block on the next frame instead of a fixed 120 ms sleep.
            await asyncio.sleep(0)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Start game bridge loop
        bridge_task = asyncio.create_task(game_bridge_loop())
        yield
        state.running = False
        bridge_task.cancel()

    app = FastAPI(title="OtoStoksBot", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_class=HTMLResponse)
    async def serve_dashboard():
        return HTMLResponse(DASHBOARD_HTML)

    @app.get("/icon.png")
    async def get_app_icon():
        base_dir = get_base_dir()
        candidates = [
            os.path.join(base_dir, "assets", "icon.png"),
            os.path.join(base_dir, "icon.png"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icon.png")
        ]
        for c in candidates:
            if os.path.exists(c):
                return FileResponse(c, media_type="image/png")
        raise HTTPException(status_code=404, detail="Icon not found")

    @app.get("/api/status")
    async def get_status():
        return state.get_snapshot()

    @app.post("/api/toggle_mode")
    async def api_toggle_mode():
        new_mode = state.toggle_mode()
        await broadcast_state()
        return {"mode": new_mode}

    @app.post("/api/toggle_achievements")
    async def api_toggle_achievements():
        new_achieve = state.toggle_achievements()
        await broadcast_state()
        return {"achievements_enabled": new_achieve}

    @app.post("/api/liquidate_all")
    async def api_liquidate_all():
        """
        Manually liquidates all open positions when user clicks 'Liquidate All'.
        Verifies bridge confirmation before reporting success.
        """
        snap = await asyncio.to_thread(fetch_snapshot)
        stocks = snap.get("stocks", {}) if snap else state.stocks
        closed_count = 0

        for ticker, s in stocks.items():
            h = s.get("holding", {}) if isinstance(s.get("holding"), dict) else {}
            owned = float(h.get("sharesOwnedDouble", 0.0))
            shorted = float(h.get("sharesShortedDouble", 0.0))

            if owned > 0 or shorted > 0:
                payload = {
                    "id": f"liq_manual_{ticker}_{int(time.time()*1000)}",
                    "action": "close",
                    "ticker": ticker,
                    "amount": "max",
                    "isMax": True
                }
                res = await asyncio.to_thread(dispatch_order, payload)
                if res and res.get("success") is True:
                    closed_count += 1
                    state.add_log(ticker, "LIQUIDATE_ALL", "MANUAL", "Closed to 100% Cash via Bridge Confirmation", "EXECUTED")
                else:
                    msg = res.get("message", "Bridge rejected") if res else "Bridge timeout"
                    state.add_log(ticker, "LIQUIDATE_ALL", "MANUAL", f"Liquidation order failed ({msg})", "FAILED")

        await broadcast_state()
        return {"status": "success", "closed_positions": closed_count}

    @app.post("/api/retrain")
    async def api_retrain():
        threading.Thread(target=run_retrain_pipeline, args=(state,), daemon=True).start()
        return {"status": "started", "message": "Background retraining pipeline initiated"}

    @app.post("/api/launch_game")
    async def api_launch_game():
        ok, msg = launch_screen_stocks()
        return {"success": ok, "message": msg}

    @app.post("/api/trade")
    async def api_trade(payload: ManualTradePayload):
        ticker = payload.ticker.strip()
        if not ticker.startswith("$"):
            ticker = f"${ticker}"

        action = payload.action.lower().strip()
        effective_pct = payload.pct if payload.pct is not None else payload.percent

        # Strict percentage trade handling: never default to max if pct < 100!
        if effective_pct is not None and effective_pct < 100:
            is_max = False
        else:
            is_max = (payload.amount_type == "max" or payload.is_max is True or (effective_pct is not None and effective_pct >= 100) or action == "close")

        order_payload = {
            "id": f"manual_{ticker}_{action}_{int(time.time()*1000)}",
            "action": action,
            "ticker": ticker,
            "amount": "max",
            "isMax": is_max,
            "percent": effective_pct if not is_max else 100
        }

        # Calculate exact share count if percentage specified
        try:
            snap = await asyncio.to_thread(fetch_snapshot)
            s_info = (snap.get("stocks", {}).get(ticker) if snap else None) or state.stocks.get(ticker, {})
            curr_price = float(s_info.get("price", 0.0))
            h = s_info.get("holding", {}) if isinstance(s_info.get("holding"), dict) else {}
            owned = float(h.get("sharesOwnedDouble", 0.0))
            shorted = float(h.get("sharesShortedDouble", 0.0))
            player_cash = float(snap.get("player", {}).get("cashDouble", state.player.get("cashDouble", 0.0))) if snap else state.player.get("cashDouble", 0.0)

            if not is_max and effective_pct:
                fraction = max(0.01, min(1.0, effective_pct / 100.0))
                if action == "buy" and curr_price > 0:
                    alloc = player_cash * fraction
                    shares = max(1, int(alloc / curr_price))
                    order_payload["amount"] = str(shares)
                elif action == "short" and curr_price > 0:
                    alloc = player_cash * fraction
                    shares = max(1, int(alloc / (curr_price * 1.5)))
                    order_payload["amount"] = str(shares)
                elif action in ("sell", "close") and owned > 0:
                    shares = max(1, int(owned * fraction))
                    order_payload["amount"] = str(shares)
                elif action in ("cover", "close") and shorted > 0:
                    shares = max(1, int(shorted * fraction))
                    order_payload["amount"] = str(shares)
        except Exception:
            pass

        res = await asyncio.to_thread(dispatch_order, order_payload)
        if res and res.get("success", False):
            msg = res.get("message", f"{action.upper()} executed")
            filled_price = float(res.get("filledPrice") or state.stocks.get(ticker, {}).get("price", 0.0))
            filled_shares = int(res.get("shares") or order_payload.get("amount") or 1) if str(res.get("shares") or order_payload.get("amount")).isdigit() else 1

            record_trade_in_proto(
                state.trades_pb_path,
                ticker,
                action.upper(),
                filled_price,
                filled_shares,
                None,
                f"Manual Trade ({effective_pct or 100}%)"
            )
            state.trade_history.append({
                "id": order_payload["id"],
                "time": datetime.now().strftime('%H:%M:%S'),
                "ticker": ticker,
                "action": action.upper(),
                "price": f"${filled_price:.2f}",
                "amount": f"{filled_shares:,}",
                "pnl": "-",
                "reason": f"Manual Trader ({effective_pct or 100}%)"
            })
            state.add_log(ticker, action.upper(), "MANUAL", f"{msg} (${filled_price:.2f} x{filled_shares:,})", "EXECUTED")
            await broadcast_state()
            return {"status": "success", "message": msg, "filledPrice": filled_price, "shares": filled_shares}
        else:
            err = res.get("message", "Bridge rejected trade") if res else "Bridge connection error"
            state.add_log(ticker, action.upper(), "MANUAL", f"Order rejected ({err})", "REJECTED")
            return {"status": "error", "message": err}

    @app.post("/api/preset")
    async def set_strategy_preset(payload: PresetPayload):
        ok = state.apply_preset(payload.preset)
        if ok:
            await broadcast_state()
            return {"status": "success", "active_preset": state.active_strategy_preset, "settings": state.settings}
        raise HTTPException(status_code=400, detail="Invalid preset profile")

    @app.get("/api/export_trades")
    async def export_trades():
        """
        Exports persistent trade execution history to downloadable CSV.
        Robustly handles millisecond and second timestamps and empty logs.
        """
        try:
            trades = pb.read_all_trades(state.trades_pb_path)
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Trade ID", "Timestamp (UTC)", "Ticker", "Action", "Price ($)", "Shares", "Profit (%)", "Algorithmic Reason"])

            if trades:
                for r in reversed(trades):
                    ts_val = float(r.timestamp)
                    if ts_val > 1e11:  # detect milliseconds
                        ts_val /= 1000.0
                    try:
                        ts_str = datetime.fromtimestamp(ts_val).strftime('%Y-%m-%d %H:%M:%S') if ts_val > 0 else ''
                    except Exception:
                        ts_str = ''
                    p_pct_str = f"{r.profit_pct:.2f}%" if r.profit_pct != 0.0 else "-"
                    writer.writerow([r.trade_id, ts_str, r.ticker, r.action, f"{r.price:.2f}", r.amount, p_pct_str, r.reason])
            elif state.trade_history:
                for th in reversed(state.trade_history):
                    writer.writerow([th.get("id"), th.get("time"), th.get("ticker"), th.get("action"), th.get("price"), th.get("amount"), th.get("pnl"), th.get("reason")])

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
        state.update_settings(
            max_pos=payload.max_positions,
            stop_loss_enabled=payload.stop_loss_enabled,
            stop_loss=payload.stop_loss_pct,
            take_profit_enabled=payload.take_profit_enabled,
            min_profit=payload.min_profit_pct,
            auto_hours=payload.auto_time_limit_hours,
            tech_target_x=payload.tech_target_x,
            max_alloc_pct=payload.max_alloc_pct,
            background_tracking=payload.background_tracking,
            close_to_tray=payload.close_to_tray,
            theme=payload.theme
        )
        await broadcast_state()
        return {"status": "success", "settings": state.settings}

    @app.get("/api/news")
    async def get_news():
        items = state.steam_news or fetch_steam_news(count=15)
        return {
            "news": items,
            "scheduled_events": state.scheduled_events
        }

    @app.get("/api/game_settings")
    async def get_in_game_settings():
        return {"settings": read_in_game_settings()}

    @app.post("/api/game_settings")
    async def post_in_game_settings(payload: Dict[str, Any]):
        ok, msg = save_in_game_settings(payload)
        if ok:
            return {"status": "success", "message": msg, "settings": read_in_game_settings()}
        raise HTTPException(status_code=500, detail=msg)

    @app.get("/api/skins")
    async def get_skins():
        return {"skins": list_skins()}

    @app.post("/api/skins")
    async def post_install_skin(payload: Dict[str, Any]):
        name = payload.get("name", "CustomSkin").strip()
        data_b64 = payload.get("image_base64", "")
        file_ext = payload.get("file_ext", "png").lower().replace(".", "")
        if not data_b64:
            raise HTTPException(status_code=400, detail="Missing image data")
        if "," in data_b64:
            data_b64 = data_b64.split(",", 1)[1]
        try:
            raw_bytes = base64.b64decode(data_b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 encoding: {e}")
        meta = payload.get("meta")
        ok, msg = install_skin(name, raw_bytes, file_ext, meta)
        if ok:
            return {"status": "success", "message": msg, "skins": list_skins()}
        raise HTTPException(status_code=400, detail=msg)

    @app.delete("/api/skins/{skin_id}")
    async def api_delete_skin(skin_id: str):
        ok, msg = delete_skin(skin_id)
        if ok:
            return {"status": "success", "message": msg, "skins": list_skins()}
        raise HTTPException(status_code=404, detail=msg)

    @app.post("/api/skins/equip")
    async def api_equip_skin(payload: Dict[str, Any]):
        skin_id = payload.get("skin_id", "")
        if not skin_id:
            raise HTTPException(status_code=400, detail="Missing skin_id")
        ok, msg = equip_skin(skin_id)
        if ok:
            return {"status": "success", "message": msg, "skins": list_skins()}
        raise HTTPException(status_code=500, detail=msg)

    @app.get("/api/portfolio")
    async def get_portfolio():
        with state.lock:
            player_cash = float(state.player.get("cashDouble", 0.0))
            net_worth = float(state.player.get("netWorthDouble", 0.0))
            positions = []
            long_val = 0.0
            short_val = 0.0
            for ticker, s in state.stocks.items():
                p = s.get("position")
                if not p:
                    continue
                qty = int(p.get("shares", 0))
                if qty == 0:
                    continue
                side = str(p.get("side", "LONG")).upper()
                curr_price = float(s.get("price", 0.0))
                val = float(p.get("totalValue", qty * curr_price))
                pnl_pct = float(p.get("profitPercent", 0.0))
                dollar_pnl = float(p.get("unrealizedProfitDouble", 0.0))
                if side == "SHORT":
                    short_val += val
                else:
                    long_val += val
                positions.append({
                    "ticker": ticker,
                    "shares": qty,
                    "side": side,
                    "price": curr_price,
                    "entry_price": float(p.get("boughtPrice", curr_price)),
                    "total_value": round(val, 2),
                    "profit_pct": round(pnl_pct, 2),
                    "dollar_pnl": round(dollar_pnl, 2)
                })

            total_invested = long_val + short_val
            long_pct = round((long_val / net_worth * 100.0), 1) if net_worth > 0 else 0.0
            short_pct = round((short_val / net_worth * 100.0), 1) if net_worth > 0 else 0.0
            cash_pct = round((player_cash / net_worth * 100.0), 1) if net_worth > 0 else 100.0

            return {
                "net_worth": net_worth,
                "cash": player_cash,
                "long_value": round(long_val, 2),
                "short_value": round(short_val, 2),
                "long_pct": long_pct,
                "short_pct": short_pct,
                "cash_pct": cash_pct,
                "total_invested": round(total_invested, 2),
                "positions": positions
            }

    @app.get("/api/stats")
    async def get_stats():
        return state.daily_store.get_performance_analysis(state.trades_pb_path)

    @app.get("/api/export_all_csv")
    async def export_all_csv():
        try:
            output = io.StringIO()
            writer = csv.writer(output)

            # Section 1: 7-Day Net Worth Summary
            writer.writerow(["=== 7-DAY NET WORTH & PERFORMANCE LEDGER ==="])
            writer.writerow(["Date", "Open ($)", "High ($)", "Low ($)", "Close ($)", "Net Profit ($)", "Change (%)"])
            past_days = state.daily_store.get_past_7_days()
            for d in past_days:
                writer.writerow([
                    d.get("date"),
                    f"{d.get('start', 0.0):.2f}",
                    f"{d.get('high', 0.0):.2f}",
                    f"{d.get('low', 0.0):.2f}",
                    f"{d.get('current', 0.0):.2f}",
                    f"{d.get('profit', 0.0):.2f}",
                    f"{d.get('pct', 0.0):.2f}%"
                ])
            writer.writerow([])

            # Section 2: Complete Trade Audit Log
            writer.writerow(["=== COMPLETE TRADE AUDIT LOG ==="])
            writer.writerow(["Trade ID", "Timestamp (UTC)", "Ticker", "Action", "Price ($)", "Shares", "Profit (%)", "Algorithmic Reason"])
            trades = pb.read_all_trades(state.trades_pb_path)
            if trades:
                for r in reversed(trades):
                    ts_val = float(r.timestamp)
                    if ts_val > 1e11:
                        ts_val /= 1000.0
                    try:
                        ts_str = datetime.fromtimestamp(ts_val).strftime('%Y-%m-%d %H:%M:%S') if ts_val > 0 else ''
                    except Exception:
                        ts_str = ''
                    p_pct_str = f"{r.profit_pct:.2f}%" if r.profit_pct != 0.0 else "-"
                    writer.writerow([r.trade_id, ts_str, r.ticker, r.action, f"{r.price:.2f}", r.amount, p_pct_str, r.reason])

            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=OtoStoksBot_Audit_Export_{int(time.time())}.csv"}
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/api/auto-rules")
    async def get_auto_rules():
        return {"rules": state.automation_engine.get_rules()}

    @app.post("/api/auto-rules")
    async def add_auto_rule(payload: Dict[str, Any]):
        stock = payload.get("stock", "")
        if not stock.startswith("$"):
            stock = f"${stock}"
        action = payload.get("action", "buy")
        when = payload.get("when", "below")
        price = float(payload.get("price", 0.0))
        percent = int(payload.get("percent", 100))
        repeat = bool(payload.get("repeat", False))
        if not stock or price <= 0:
            raise HTTPException(status_code=400, detail="Invalid rule parameters")
        rule = state.automation_engine.add_rule(stock, action, when, price, percent, repeat)
        state.add_log(stock, "RULE_CREATED", state.mode, f"Added auto trigger: {action.upper()} {stock} {percent}% when price {when} ${price:.2f}", "CREATED")
        await broadcast_state()
        return {"status": "success", "rule": rule}

    @app.delete("/api/auto-rules/{rule_id}")
    async def delete_auto_rule(rule_id: str):
        ok = state.automation_engine.remove_rule(rule_id)
        if ok:
            state.add_log("SYSTEM", "RULE_REMOVED", state.mode, f"Removed auto trigger {rule_id}", "REMOVED")
            await broadcast_state()
            return {"status": "success"}
        raise HTTPException(status_code=404, detail="Rule not found")

    @app.post("/api/auto-rules/{rule_id}/toggle")
    async def toggle_auto_rule(rule_id: str):
        enabled = state.automation_engine.toggle_rule(rule_id)
        if enabled is not None:
            await broadcast_state()
            return {"status": "success", "enabled": enabled}
        raise HTTPException(status_code=404, detail="Rule not found")

    @app.get("/api/events")
    async def get_scheduled_events():
        return {"events": state.scheduled_events}

    @app.get("/api/compare")
    async def get_compare_series(tickers: Optional[str] = None):
        """
        Multi-stock normalized % return comparison series from start of window.
        """
        requested = [t.strip().upper() for t in (tickers or "").split(",") if t.strip()]
        if not requested:
            requested = list(state.stocks.keys())[:8]

        series_data = {}
        for t in requested:
            pts = list(state.history_series.get(t, []))
            if pts:
                base = pts[0]
                pct_pts = [round(((p - base) / base) * 100.0, 2) if base > 0 else 0.0 for p in pts]
                series_data[t] = pct_pts
            else:
                series_data[t] = []

        return {
            "timestamps": list(state.history_timestamps),
            "series": series_data
        }

    @app.post("/api/shutdown")
    async def api_shutdown():
        state.running = False
        return {"status": "shutting_down"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        async with ws_lock:
            active_websockets.append(websocket)
        try:
            await websocket.send_json(state.get_snapshot())
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            async with ws_lock:
                if websocket in active_websockets:
                    active_websockets.remove(websocket)

    return app
