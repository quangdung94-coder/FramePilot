"""Unit tests for tools.overnight_qa (safety guard, sandbox junction, watchdog leak detector, reporter)."""
import json
import os
import shutil
import tempfile
import unittest

from tools.overnight_qa.reporter import BugCollector, guess_source_hint
from tools.overnight_qa.safety import (
    DEFAULT_SANDBOX_PREFIX,
    SafetyError,
    SandboxEnv,
    anonymize_text,
    verify_write_guard,
)
from tools.overnight_qa.watchdog import ResourceWatchdog


class TestOvernightQASafety(unittest.TestCase):
    def test_write_guard_blocks_real_project(self):
        # readonly allows any project name
        verify_write_guard("readonly", "2026.10.25.Real_Client")
        # sandbox_write MUST reject non-FP_TEST_ project
        with self.assertRaises(SafetyError):
            verify_write_guard("sandbox_write", "2026.10.25.Real_Client")
        with self.assertRaises(SafetyError):
            verify_write_guard("sandbox_write", "")
        # sandbox_write allows FP_TEST_*
        verify_write_guard("sandbox_write", DEFAULT_SANDBOX_PREFIX + "01")

    def test_sandbox_setup_and_safe_junction_teardown(self):
        base = tempfile.mkdtemp(prefix="qa_test_")
        try:
            fake_real_data = os.path.join(base, "real_data")
            fake_models = os.path.join(fake_real_data, "models")
            os.makedirs(fake_models, exist_ok=True)
            sentinel = os.path.join(fake_models, "keep_me.bin")
            with open(sentinel, "wb") as f:
                f.write(b"MODEL_DATA_DO_NOT_DELETE")

            run_dir = os.path.join(base, "run1")
            sb = SandboxEnv(run_dir, {"data_root": fake_real_data, "proxy_root": r"F:\02_Proxy Media"})
            cfg_path = sb.setup()

            self.assertTrue(os.path.isfile(cfg_path))
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            self.assertEqual(cfg["data_root"], sb.data_root)
            self.assertEqual(cfg["cache_root"], sb.cache_root)
            self.assertTrue(sb.models_linked)
            self.assertTrue(os.path.isfile(os.path.join(sb.data_root, "models", "keep_me.bin")))

            env = sb.build_process_env(cdp_port=9222)
            self.assertEqual(env["TROLY_CONFIG"], cfg_path)
            self.assertEqual(env["TROLY_NO_SHUTDOWN"], "1")
            self.assertIn("--remote-debugging-port=9222", env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"])

            # Teardown MUST remove sandbox without deleting sentinel inside real models!
            sb.teardown(keep_sandbox=False)
            self.assertFalse(os.path.exists(sb.sandbox_dir))
            self.assertTrue(os.path.isfile(sentinel))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_anonymize_masks_client_project_but_keeps_fp_test(self):
        self.assertEqual(
            anonymize_text("Project 2026.10.25.ClientA failed", "2026.10.25.ClientA", enabled=True),
            "Project PROJECT_TEST_MASKED failed",
        )
        self.assertEqual(
            anonymize_text("Project FP_TEST_01 failed", "FP_TEST_01", enabled=True),
            "Project FP_TEST_01 failed",
        )


class TestOvernightQAReporterAndWatchdog(unittest.TestCase):
    def test_deduplication_and_report_files(self):
        tmp = tempfile.mkdtemp(prefix="qa_rep_")
        try:
            bugs = BugCollector(tmp, project_name="2026.10.25.SecretClient", anonymize=True)
            bugs.record_bug("JS_EXCEPTION", "HIGH", "TypeError at line 120 in player.js for 2026.10.25.SecretClient", "stack 1", suite="smoke_e2e", cycle=1)
            bugs.record_bug("JS_EXCEPTION", "HIGH", "TypeError at line 999 in player.js for 2026.10.25.SecretClient", "stack 2", suite="smoke_e2e", cycle=2)
            bugs.record_suite("smoke_e2e", 1, True, 12.4, "OK")

            self.assertEqual(len(bugs.sorted_bugs()), 1)
            self.assertEqual(bugs.sorted_bugs()[0]["count"], 2)
            self.assertNotIn("SecretClient", bugs.sorted_bugs()[0]["title"])
            self.assertIn("player.js", guess_source_hint("JS_EXCEPTION", "player.js error", ""))

            paths = bugs.write_reports(
                meta={"mode": "readonly", "seed": 42, "cycles_done": 2, "exe": "FramePilot.exe"},
                watchdog_samples=[
                    {"total_app_mb": 300, "vram_used_mb": 1200},
                    {"total_app_mb": 340, "vram_used_mb": 1300},
                ],
                peak_stats={"peak_total_mb": 340, "peak_fp_mb": 120, "peak_wv2_mb": 220, "peak_handles": 400, "peak_vram_mb": 1300},
            )
            for p in paths.values():
                self.assertTrue(os.path.isfile(p))
            with open(paths["md"], encoding="utf-8") as f:
                md = f.read()
            self.assertNotIn("SecretClient", md)
            self.assertIn("BUG-001", md)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_watchdog_leak_detection(self):
        wd = ResourceWatchdog(interval_sec=1.0)
        # Simulate sustained RAM & handle growth across 10 samples
        for i in range(10):
            wd.samples.append({
                "ts": float(i),
                "pid": 123,
                "alive": True,
                "fp_rss_mb": 100.0 + i * 80.0,
                "fp_handles": 300 + i * 150,
                "fp_threads": 20,
                "wv2_count": 5,
                "wv2_rss_mb": 200.0,
                "total_app_mb": 300.0 + i * 80.0,
                "worker_count": 0,
                "worker_rss_mb": 0.0,
                "vram_used_mb": 1000.0 + i * 200.0,
                "vram_total_mb": 12288.0,
                "gpu_util_pct": 10.0,
            })
        findings = wd.analyze_leaks()
        cats = {f["category"] for f in findings}
        self.assertIn("MEMORY_LEAK", cats)
        self.assertIn("HANDLE_LEAK", cats)
        self.assertIn("VRAM_LEAK", cats)


if __name__ == "__main__":
    unittest.main()
