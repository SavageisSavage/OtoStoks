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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine.bridge as bridge  # noqa: E402


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
