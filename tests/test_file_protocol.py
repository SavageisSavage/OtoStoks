"""
Tests for the Screen Stocks file/mod protocol in core.game_mod.

These run with the standard library only, against a synthetic game directory, so
they validate the protocol layer without the game, network access or any of the
runtime dependencies in requirements.txt.

    python -m unittest discover -s tests -v
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_mod import (  # noqa: E402
    MarketFileWatcher,
    dispatch_native_order,
    wait_command_consumed,
)


def build_market_frame(price=10.5, sequence=1, cash=1000.0, shares=0, shorted=0):
    """A minimal export frame shaped like the real mods/export/market.json."""
    return {
        "formatVersion": 1,
        "gameVersion": "1.0.13",
        "sequence": sequence,
        "writtenAtMs": int(time.time() * 1000),
        "serverTimeMs": int(time.time() * 1000),
        "marketReady": True,
        "stocks": [
            {
                "stockId": "$BANK",
                "name": "$BANK",
                "price": price,
                "basePrice": 10.0,
                "priceCap": 1000.0,
                "dividendRate": 0.005,
                "maxVolume": 30000,
                "availableShares": "8139540",
                "unlocked": True,
            }
        ],
        "player": {
            "cash": cash,
            "netWorth": 0.0,
            "level": 11,
            "ipoCount": 0,
            "positions": (
                [{"stockId": "$BANK", "sharesOwned": shares, "sharesShorted": shorted,
                  "averageBuyPrice": 10.0, "averageShortPrice": 10.0}]
                if (shares or shorted) else []
            ),
        },
        "marketNews": [],
        "scheduledNews": [],
        "commandResults": [],
    }


class FakeGameDir:
    """Creates the directory shape the real game uses under LocalLow."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="otostoks-test-")
        self.mods = os.path.join(self.root, "mods")
        self.export = os.path.join(self.mods, "export")
        self.commands = os.path.join(self.mods, "commands")
        os.makedirs(self.export)
        os.makedirs(os.path.join(self.commands, "$BANK"))

    def write_market(self, frame):
        path = os.path.join(self.export, "market.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(frame, f, indent=2)
        return path

    def command_path(self, ticker, action, is_max=True):
        return os.path.join(self.commands, ticker, f"{action}{'max' if is_max else 'percent'}.json")

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class MarketFileWatcherTests(unittest.TestCase):
    def setUp(self):
        self.game = FakeGameDir()
        self.watcher = MarketFileWatcher(game_dir=self.game.root)

    def tearDown(self):
        self.game.cleanup()

    def test_missing_export_is_not_a_frame(self):
        changed, snap, age = self.watcher.poll()
        self.assertFalse(changed)
        self.assertIsNone(snap)
        self.assertIsNone(age)

    def test_first_frame_is_reported_then_cached(self):
        self.game.write_market(build_market_frame(price=11.0))
        changed, snap, _ = self.watcher.poll()
        self.assertTrue(changed)
        self.assertEqual(snap["stocks"]["$BANK"]["price"], 11.0)

        # Same file, no rewrite: the loop must not re-parse it.
        changed, snap, age = self.watcher.poll()
        self.assertFalse(changed)
        self.assertIsNone(snap)
        self.assertIsNotNone(age)

    def test_rewrite_is_reported(self):
        self.game.write_market(build_market_frame(price=11.0, sequence=1))
        self.watcher.poll()
        # Bump mtime explicitly: NTFS timestamp granularity is fine, but a fast
        # rewrite in a test can land in the same tick.
        self.game.write_market(build_market_frame(price=12.5, sequence=2))
        changed, snap, _ = self.watcher.poll()
        self.assertTrue(changed)
        self.assertEqual(snap["stocks"]["$BANK"]["price"], 12.5)
        self.assertEqual(self.watcher.frames, 2)

    def test_force_rereads_unchanged_file(self):
        self.game.write_market(build_market_frame(price=13.0))
        self.watcher.poll()
        changed, snap, _ = self.watcher.poll(force=True)
        self.assertTrue(changed)
        self.assertEqual(snap["stocks"]["$BANK"]["price"], 13.0)

    def test_snapshot_normalisation(self):
        self.game.write_market(build_market_frame(price=20.0, cash=500.0, shares=10))
        _, snap, _ = self.watcher.poll()
        holding = snap["stocks"]["$BANK"]["holding"]
        self.assertEqual(holding["sharesOwnedDouble"], 10.0)
        self.assertEqual(snap["player"]["cashDouble"], 500.0)
        # 500 cash + 10 shares at 20 = 700 net worth (computed when absent).
        self.assertAlmostEqual(snap["player"]["netWorthDouble"], 700.0, places=4)

    def test_short_net_worth_uses_short_price(self):
        self.game.write_market(build_market_frame(price=8.0, cash=100.0, shorted=10))
        _, snap, _ = self.watcher.poll()
        # short value = shares * (2*avg_short - price) = 10 * (20 - 8) = 120
        self.assertAlmostEqual(snap["player"]["netWorthDouble"], 220.0, places=4)

    def test_staleness_flag(self):
        path = self.game.write_market(build_market_frame())
        old = time.time() - 30
        os.utime(path, (old, old))
        _, _, age = self.watcher.poll()
        self.assertGreater(age, 5000)
        self.assertTrue(self.watcher.is_stale(age))

    def test_fresh_frame_is_not_stale(self):
        self.game.write_market(build_market_frame())
        _, _, age = self.watcher.poll()
        self.assertFalse(self.watcher.is_stale(age))


class NativeOrderTests(unittest.TestCase):
    def setUp(self):
        self.game = FakeGameDir()

    def tearDown(self):
        self.game.cleanup()

    def test_max_order_writes_execute_true(self):
        ok, msg, path = dispatch_native_order("$BANK", "buy", "max", is_max=True, game_dir=self.game.root)
        self.assertTrue(ok, msg)
        self.assertEqual(path, self.game.command_path("$BANK", "buy"))
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"execute": True})

    def test_percent_order_writes_percent(self):
        ok, _, path = dispatch_native_order("$BANK", "sell", "40", is_max=False, game_dir=self.game.root)
        self.assertTrue(ok)
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload, {"execute": True, "percent": 40})

    def test_percent_is_clamped(self):
        dispatch_native_order("$BANK", "buy", "900", is_max=False, game_dir=self.game.root)
        with open(self.game.command_path("$BANK", "buy", is_max=False), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["percent"], 100)

    def test_unknown_action_rejected(self):
        ok, msg, path = dispatch_native_order("$BANK", "yolo", "max", game_dir=self.game.root)
        self.assertFalse(ok)
        self.assertIsNone(path)
        self.assertIn("Unknown trade action", msg)

    def test_pending_order_blocks_duplicate(self):
        path = self.game.command_path("$BANK", "buy")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"execute": True}, f)
        started = time.perf_counter()
        ok, msg, _ = dispatch_native_order("$BANK", "buy", "max", game_dir=self.game.root)
        elapsed = time.perf_counter() - started
        self.assertFalse(ok)
        self.assertIn("still pending", msg)
        # The grace window is brief; it must not stall the loop for seconds.
        self.assertLess(elapsed, 1.0)


class CommandConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.game = FakeGameDir()
        self.path = self.game.command_path("$BANK", "buy")
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"execute": True}, f)

    def tearDown(self):
        self.game.cleanup()

    def test_times_out_when_game_never_consumes(self):
        self.assertIsNone(wait_command_consumed(self.path, timeout_ms=120, poll_ms=5))

    def test_detects_game_acknowledging_order(self):
        def acknowledge():
            time.sleep(0.05)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"execute": False}, f)

        t = threading.Thread(target=acknowledge)
        t.start()
        elapsed = wait_command_consumed(self.path, timeout_ms=2000, poll_ms=2)
        t.join()
        self.assertIsNotNone(elapsed)
        self.assertLess(elapsed, 1000)
        self.assertGreaterEqual(elapsed, 30)

    def test_deleted_file_counts_as_consumed(self):
        def consume():
            time.sleep(0.03)
            # Windows can still hold the file briefly; retry rather than fail.
            for _ in range(50):
                try:
                    os.remove(self.path)
                    return
                except PermissionError:
                    time.sleep(0.01)

        t = threading.Thread(target=consume)
        t.start()
        elapsed = wait_command_consumed(self.path, timeout_ms=2000, poll_ms=2)
        t.join()
        self.assertIsNotNone(elapsed)

    def test_none_path_is_safe(self):
        self.assertIsNone(wait_command_consumed(None, timeout_ms=10))


if __name__ == "__main__":
    unittest.main(verbosity=2)
