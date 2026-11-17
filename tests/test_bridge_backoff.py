"""
Tests for the HTTP-bridge probe backoff in engine.bridge.

The bridge only exists when the BepInEx DLL is loaded. When it is not, probing a
filtered port costs the full socket timeout on every attempt, so the probe has to
back off - and back off harder each time it fails, otherwise it stalls the loop on
a fixed schedule forever.

    python -m unittest discover -s tests -v
"""
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine.bridge as bridge  # noqa: E402
from core.config import SNAPSHOT_STALE_S  # noqa: E402


class FakeFeed:
    """Stands in for MarketFileWatcher in transport-selection tests."""

    def __init__(self, changed, age_ms, frames=None):
        self._changed = changed
        self._age_ms = age_ms
        self.frames = (1 if changed else 0) if frames is None else frames

    def poll(self, force=False):
        if self._changed:
            return True, {"marketReady": True, "source": "native_mod", "stocks": {}}, self._age_ms
        return False, None, self._age_ms

    def is_stale(self, age_ms):
        if age_ms is None:
            return True
        return age_ms > SNAPSHOT_STALE_S * 1000.0


class TransportSelectionTests(unittest.TestCase):
    def test_healthy_file_feed_never_probes_the_socket_bridge(self):
        feed = FakeFeed(changed=True, age_ms=40.0)
        with mock.patch.object(bridge, "FILE_WATCHER", feed), \
                mock.patch.object(bridge, "fetch_snapshot_http",
                                  side_effect=AssertionError("probe must not run")):
            changed, snap, age = bridge.fetch_snapshot_change()
        self.assertTrue(changed)
        self.assertEqual(snap["source"], "native_mod")
        self.assertEqual(bridge.CURRENT_TRANSPORT, "native_mod")

    def test_socket_bridge_is_used_once_the_file_feed_goes_quiet(self):
        feed = FakeFeed(changed=False, age_ms=60_000.0, frames=1)
        http_snap = {"marketReady": True, "source": "http_bridge", "stocks": {}}
        with mock.patch.object(bridge, "FILE_WATCHER", feed), \
                mock.patch.object(bridge, "fetch_snapshot_http", return_value=http_snap) as probe:
            changed, snap, age = bridge.fetch_snapshot_change()
        self.assertTrue(changed)
        self.assertEqual(snap["source"], "http_bridge")
        self.assertEqual(bridge.CURRENT_TRANSPORT, "http")
        probe.assert_called_once()

    def test_quiet_feed_without_a_bridge_reports_no_frame(self):
        feed = FakeFeed(changed=False, age_ms=60_000.0, frames=1)
        with mock.patch.object(bridge, "FILE_WATCHER", feed), \
                mock.patch.object(bridge, "fetch_snapshot_http", return_value=None):
            changed, snap, age = bridge.fetch_snapshot_change()
        self.assertFalse(changed)
        self.assertIsNone(snap)
        self.assertEqual(age, 60_000.0)

    def test_no_probe_before_the_first_frame_inside_the_grace_window(self):
        """Frame one must not pay a socket timeout while the file feed is starting."""
        feed = FakeFeed(changed=False, age_ms=None, frames=0)
        with mock.patch.object(bridge, "FILE_WATCHER", feed), \
                mock.patch.object(bridge, "_STARTED_AT", time.time()), \
                mock.patch.object(bridge, "fetch_snapshot_http",
                                  side_effect=AssertionError("probe must not run")):
            changed, snap, _ = bridge.fetch_snapshot_change()
        self.assertFalse(changed)
        self.assertIsNone(snap)


class ProbeBackoffTests(unittest.TestCase):
    def setUp(self):
        bridge._http_fails = 0
        bridge._http_backoff_until = 0.0
        bridge._http_backoff_s = bridge.HTTP_BRIDGE_BACKOFF_S

    def test_slow_failure_backs_off_immediately(self):
        before = time.time()
        bridge._note_http_failure()
        self.assertGreater(bridge._http_backoff_until, before)
        self.assertEqual(bridge._http_fails, 1)

    def test_backoff_escalates(self):
        bridge._note_http_failure()
        first = bridge._http_backoff_s
        bridge._note_http_failure()
        second = bridge._http_backoff_s
        self.assertGreater(second, first)

    def test_backoff_is_capped(self):
        for _ in range(20):
            bridge._note_http_failure()
        self.assertLessEqual(bridge._http_backoff_s, bridge._HTTP_BACKOFF_MAX_S)

    def test_probe_is_skipped_while_backed_off(self):
        bridge._http_backoff_until = time.time() + 60
        started = time.perf_counter()
        self.assertIsNone(bridge.fetch_snapshot_http(timeout=5))
        elapsed_ms = (time.perf_counter() - started) * 1000
        # A skipped probe must not pay the socket timeout.
        self.assertLess(elapsed_ms, 50)

    def test_failed_probe_arms_backoff(self):
        """
        A closed port on this machine takes ~1 s to refuse, which is why the
        backoff matters: one failed probe must make the next one free.
        """
        self.assertIsNone(bridge.fetch_snapshot_http(port=1, timeout=2))
        self.assertGreater(bridge._http_backoff_until, time.time())

        started = time.perf_counter()
        self.assertIsNone(bridge.fetch_snapshot_http(port=1, timeout=2))
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.assertLess(elapsed_ms, 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
