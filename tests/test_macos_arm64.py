# -*- coding: utf-8 -*-
"""test_macos_arm64.py - Bộ kiểm thử cho bản macOS Apple Silicon (chip M1/M2/M3/M4),
chạy được cả trên Windows (mock darwin) lẫn macOS thật (GitHub Actions macos-14)."""
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.join(ROOT, "app")
if APP not in sys.path:
    sys.path.insert(0, APP)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import troly_asr_worker as asr_w
import troly_batch as tb
import troly_env as te
import troly_proc as tp
import troly_setup as ts
import troly_speech as sp
import troly_thumbs as tt
import build_mac


class TestMacOSEnvAndPaths(unittest.TestCase):
    def test_mac_bundle_parent(self):
        p = os.path.join("/Users", "demo", "FramePilot_Mac", "FramePilot.app", "Contents", "MacOS")
        got = te._mac_bundle_parent(p)
        self.assertTrue(got.endswith("FramePilot_Mac"), got)

    def test_resolve_paths_darwin(self):
        with mock.patch.object(sys, "platform", "darwin"):
            api_dir, modules, lib, rdir = te.resolve_paths({})
            self.assertIn("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting", api_dir)
            self.assertTrue(modules.endswith("Modules"))
            self.assertTrue(lib.endswith("fusionscript.so"))
            self.assertIn("DaVinci Resolve.app", rdir)

    def test_ai_python_and_constme_darwin(self):
        with mock.patch.object(sys, "platform", "darwin"):
            py = te.ai_python(cfg={})
            self.assertNotIn("Scripts\\python.exe", py)
            self.assertNotIn("C:\\VideoAI", py)
            self.assertTrue(py.endswith("python3") or py.endswith("python"))
            self.assertEqual(te.constme_exe(), "")
            self.assertEqual(te.constme_model(), "")

    def test_lut_dirs_darwin(self):
        with mock.patch.object(sys, "platform", "darwin"):
            dirs = tt.lut_dirs(["/custom/lut"])
            self.assertEqual(dirs[0], "/custom/lut")
            self.assertTrue(any("/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT" in d for d in dirs))
            self.assertFalse(any("ProgramData" in d for d in dirs))

    def test_torch_device_mps_priority(self):
        fake_torch = types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=lambda: False, empty_cache=mock.Mock()),
            backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: True)),
            mps=types.SimpleNamespace(empty_cache=mock.Mock()),
        )
        self.assertEqual(te.torch_device(fake_torch), "mps")
        self.assertEqual(os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK"), "1")
        te.torch_empty_cache(fake_torch)
        fake_torch.mps.empty_cache.assert_called_once()

    def test_torch_device_cpu_fallback(self):
        fake_torch = types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=lambda: False),
            backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False)),
        )
        self.assertEqual(te.torch_device(fake_torch), "cpu")

    def test_proc_giau_strips_windows_flags_on_posix(self):
        with mock.patch.object(os, "name", "posix"):
            kw = tp._giau({"creationflags": 0x08000000, "startupinfo": object(), "timeout": 5}, new_session=True)
            self.assertNotIn("creationflags", kw)
            self.assertNotIn("startupinfo", kw)
            self.assertTrue(kw.get("start_new_session"))
            self.assertEqual(kw["timeout"], 5)

    def test_shutdown_darwin_uses_osascript(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TROLY_NO_SHUTDOWN", None)
            with mock.patch.object(sys, "platform", "darwin"), mock.patch.object(tp, "chay_an") as m_run:
                tb.system_shutdown()
                m_run.assert_called_once()
                cmd = m_run.call_args[0][0]
                self.assertEqual(cmd[0], "osascript")


class TestMacOSWhisperMLX(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fp_mac_asr_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_is_mlx_model_dir(self):
        mlx_d = os.path.join(self.tmp, "whisper_large_v3_turbo_mlx")
        ct2_d = os.path.join(self.tmp, "whisper_large_v3_turbo")
        os.makedirs(mlx_d)
        os.makedirs(ct2_d)
        with open(os.path.join(mlx_d, "weights.safetensors"), "wb") as f:
            f.write(b"123")
        with open(os.path.join(ct2_d, "model.bin"), "wb") as f:
            f.write(b"123")
        self.assertTrue(asr_w.is_mlx_model_dir(mlx_d))
        self.assertFalse(asr_w.is_mlx_model_dir(ct2_d))

    def test_faster_whisper_model_dir_prefers_mlx_on_darwin(self):
        mlx_d = os.path.join(self.tmp, "models", "whisper_large_v3_turbo_mlx")
        ct2_d = os.path.join(self.tmp, "models", "whisper_large_v3_turbo")
        os.makedirs(mlx_d)
        os.makedirs(ct2_d)
        with mock.patch.object(sys, "platform", "darwin"):
            got = sp.faster_whisper_model_dir("whisper_turbo", self.tmp)
            self.assertEqual(got, mlx_d)
        # Nếu chưa có MLX thì lùi về CT2
        shutil.rmtree(mlx_d)
        with mock.patch.object(sys, "platform", "darwin"):
            got2 = sp.faster_whisper_model_dir("whisper_turbo", self.tmp)
            self.assertEqual(got2, ct2_d)


class TestMacOSCleanBundleAndSetup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fp_mac_pkg_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_clean_config_mac_has_zero_windows_paths(self):
        cfg = ts.build_clean_config("/Users/test/FramePilot_Mac_ARM64", is_mac_os=True)
        self.assertTrue(ts.is_clean_config_dict(cfg, is_mac_os=True))
        self.assertTrue(cfg["ai_python"].endswith("bin/python3") or cfg["ai_python"].endswith("bin\\python3"))
        self.assertEqual(cfg["resolve"]["install_path"], "/Applications/DaVinci Resolve/DaVinci Resolve.app")
        self.assertEqual(cfg["whisper"]["exe"], "")

    def test_scan_system_mac_offline_uv_and_no_constme(self):
        pkg = os.path.join(self.tmp, "pkg")
        os.makedirs(os.path.join(pkg, "offline_env", "wheels"))
        with open(os.path.join(pkg, "offline_env", "wheels", "torch-2.4.0-arm64.whl"), "wb") as f:
            f.write(b"whl")
        os.makedirs(os.path.join(pkg, "models", "whisper_large_v3_turbo_mlx"))
        with open(os.path.join(pkg, "models", "whisper_large_v3_turbo_mlx", "weights.safetensors"), "wb") as f:
            f.write(b"w")

        target = os.path.join(self.tmp, "target")
        plan = ts.scan_system(pkg, target_root=target, is_mac_os=True)
        ids = [it["id"] for it in plan["items"]]
        self.assertNotIn("tool_constme", ids)
        self.assertIn("model_whisper_large_v3_turbo_mlx", ids)
        self.assertIn("model_phowhisper_medium_mlx", ids)
        ai_it = [it for it in plan["items"] if it["id"] == "ai_runtime"][0]
        self.assertEqual(ai_it["install_mode"], "offline_uv")
        self.assertTrue(ai_it["has_source"])
        menu_it = [it for it in plan["items"] if it["id"] == "davinci_menu"][0]
        self.assertIn("FramePilot.app", menu_it["src"])

    def test_scan_system_mac_accepts_ct2_whisper_fallback_from_windows_models(self):
        pkg = os.path.join(self.tmp, "pkg_win_models")
        os.makedirs(os.path.join(pkg, "models", "whisper_large_v3_turbo"))
        with open(os.path.join(pkg, "models", "whisper_large_v3_turbo", "model.bin"), "wb") as f:
            f.write(b"ct2")
        target = os.path.join(self.tmp, "target_mac")
        plan = ts.scan_system(pkg, target_root=target, is_mac_os=True)
        by_id = {it["id"]: it for it in plan["items"]}
        it = by_id["model_whisper_large_v3_turbo_mlx"]
        self.assertTrue(it["has_source"])
        self.assertTrue(it["src"].endswith("whisper_large_v3_turbo"))
        self.assertTrue(it["dst"].endswith("whisper_large_v3_turbo"))

    def test_mo_an_tracked_by_huy_tat_ca(self):
        p = tp.mo_an([sys.executable, "-c", "import time; time.sleep(30)"])
        self.assertIsNone(p.poll())
        tp.huy_tat_ca()
        try:
            p.wait(timeout=3)
        except Exception:
            pass
        self.assertIsNotNone(p.poll())

    def test_stage_clean_mac_bundle_and_audit(self):
        out = os.path.join(self.tmp, "FramePilot_Mac_ARM64")
        # Giả lập có file rác cũ cần được dọn sạch
        os.makedirs(os.path.join(out, "data", "troly"))
        with open(os.path.join(out, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"cache_root": "E:/Kho dữ liệu/QuangKhoi"}, f)

        build_mac.stage_clean_mac_bundle(out, include_ffmpeg=False)

        self.assertFalse(os.path.exists(os.path.join(out, "config.json")))
        self.assertFalse(os.path.exists(os.path.join(out, "data")))
        self.assertTrue(os.path.isfile(os.path.join(out, "config.example.json")))
        self.assertTrue(os.path.isfile(os.path.join(out, "CaiDat_MayMoi.command")))
        self.assertTrue(os.path.isfile(os.path.join(out, "HUONG_DAN_CAI_DAT_MAC.txt")))
        self.assertTrue(os.path.isfile(os.path.join(out, "CHECKLIST_TEST_MAC.txt")))
        issues = ts.audit_clean_bundle(out, is_mac_os=True)
        self.assertEqual(issues, [])

        # Kiểm tra audit bắt được nếu ai đó bỏ nhầm config.json cá nhân vào gói
        with open(os.path.join(out, "config.json"), "w", encoding="utf-8") as f:
            f.write("{}")
        self.assertTrue(len(ts.audit_clean_bundle(out, is_mac_os=True)) >= 1)

    def test_js_cmd_shortcuts_present(self):
        web = os.path.join(APP, "troly_web")
        with open(os.path.join(web, "app.js"), encoding="utf-8") as f:
            app_js = f.read()
        with open(os.path.join(web, "speech.js"), encoding="utf-8") as f:
            sp_js = f.read()
        with open(os.path.join(web, "player.js"), encoding="utf-8") as f:
            pl_js = f.read()
        with open(os.path.join(web, "step5.js"), encoding="utf-8") as f:
            s5_js = f.read()
        self.assertIn('(e.ctrlKey || e.metaKey) && !e.altKey && (e.code === "KeyZ" || e.code === "KeyY")', app_js)
        self.assertIn('(e.ctrlKey || e.metaKey) && e.code === "KeyA"', app_js)
        self.assertIn('(e.ctrlKey || e.metaKey) && e.code === "KeyA"', sp_js)
        self.assertIn('if (!e.ctrlKey && !e.metaKey) return;', pl_js)
        self.assertIn('if (e.ctrlKey || e.metaKey)', s5_js)


if __name__ == "__main__":
    unittest.main()
