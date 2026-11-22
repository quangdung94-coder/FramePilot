"""Kiểm thử Bước 3: Tự động đồng bộ sóng âm (troly_sync.py) + Bộ cài đặt thông minh & Bản sạch (troly_setup.py)."""
import json
import os
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
APP = os.path.join(ROOT, "app")
sys.path.insert(0, APP)

import troly_setup as tset
import troly_sync as tsync


class TestBuoc3SyncAndInstaller(unittest.TestCase):
    def test_match_offset_recovers_shifted_waveform(self):
        sr = 8000
        rng = np.random.default_rng(42)
        ref = rng.standard_normal(sr * 10).astype(np.float32)
        shift_sec = 1.25
        shift = int(shift_sec * sr)
        tgt = np.concatenate([np.zeros(shift, dtype=np.float32), ref[:-shift]])
        off, conf = tsync.match_offset(ref, tgt, sr=sr, max_lag_sec=10.0)
        self.assertAlmostEqual(off, -shift_sec, delta=0.05)
        self.assertGreater(conf, 0.5)

    def test_installer_and_mac_scripts_exist(self):
        iss = os.path.join(ROOT, "installer", "FramePilot.iss")
        mac = os.path.join(ROOT, "build_mac.sh")
        self.assertTrue(os.path.isfile(iss))
        self.assertTrue(os.path.isfile(mac))
        with open(iss, encoding="utf-8") as f:
            txt = f.read()
        self.assertIn("FramePilot.exe", txt)
        self.assertIn("FramePilot_Setup", txt)

    def test_clean_config_has_zero_client_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = tset.build_clean_config(tmp)
            self.assertTrue(tset.is_clean_config_dict(cfg))
            self.assertEqual(cfg["cache_root"], "")
            self.assertEqual(cfg["srt_root"], "")
            self.assertEqual(cfg["camera_luts"], {})

            # Giả lập file config có dính tên project khách cũ -> ensure_clean_config_file phải tự lọc sạch
            dirty_path = os.path.join(tmp, "config.json")
            with open(dirty_path, "w", encoding="utf-8") as f:
                json.dump({
                    "data_root": os.path.join(tmp, "data"),
                    "cache_root": r"J:\01_Project video\2026.10.25.QuangKhoi&ThuyTrang\03_framePilot",
                    "srt_root": r"J:\01_Project video\2026.10.25.QuangKhoi&ThuyTrang\03_framePilot",
                }, f)
            tset.ensure_clean_config_file(tmp, os.path.join(tmp, "data"), os.path.join(tmp, "ai_env"))
            with open(dirty_path, "r", encoding="utf-8") as f:
                cleaned = json.load(f)
            self.assertTrue(tset.is_clean_config_dict(cleaned))
            self.assertEqual(cleaned["cache_root"], "")
            self.assertEqual(cleaned["srt_root"], "")

    def test_setup_asks_before_installing_and_skips_existing_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, "pkg")
            dst = os.path.join(tmp, "dst")
            dst_data = os.path.join(tmp, "dst_data")
            dst_ai = os.path.join(tmp, "dst_ai")

            # Gói đóng gói có sẵn 2 model: whisper_large_v3_turbo và siglip2_vitb16
            for m in ("whisper_large_v3_turbo", "siglip2_vitb16"):
                mdir = os.path.join(pkg, "models", m)
                os.makedirs(mdir, exist_ok=True)
                with open(os.path.join(mdir, "model.bin"), "wb") as f:
                    f.write(b"PKG_VERSION_" + m.encode("ascii"))

            # Máy đích ĐÃ CÓ sẵn whisper_large_v3_turbo (bản riêng trên máy đích)
            existing_m = os.path.join(dst_data, "models", "whisper_large_v3_turbo")
            os.makedirs(existing_m, exist_ok=True)
            with open(os.path.join(existing_m, "model.bin"), "wb") as f:
                f.write(b"EXISTING_ON_PC_DO_NOT_OVERWRITE")

            plan = tset.scan_system(pkg, target_root=dst, target_data_root=dst_data, target_ai_dir=dst_ai, is_mac_os=False)
            by_id = {it["id"]: it for it in plan["items"]}
            self.assertTrue(by_id["model_whisper_large_v3_turbo"]["exists"])
            self.assertFalse(by_id["model_siglip2_vitb16"]["exists"])
            self.assertTrue(by_id["model_siglip2_vitb16"]["has_source"])

            # 1) Khi người dùng trả lời 'n' -> huỷ, chưa cài siglip2_vitb16
            logs = []
            r_no = tset.run_setup(plan, ask_fn=lambda _q: "n", out_fn=logs.append)
            self.assertTrue(r_no["cancelled"])
            self.assertFalse(os.path.exists(os.path.join(dst_data, "models", "siglip2_vitb16", "model.bin")))

            # 2) Khi người dùng trả lời 'y' -> cài siglip2_vitb16, BỎ QUA whisper_large_v3_turbo đã có
            asked = []
            r_yes = tset.run_setup(plan, ask_fn=lambda q: (asked.append(q) or "y"), out_fn=logs.append)
            self.assertTrue(asked, "Phải hỏi xác nhận người dùng trước khi cài")
            self.assertFalse(r_yes["cancelled"])
            self.assertIn("model_whisper_large_v3_turbo", r_yes["skipped"])
            self.assertIn("model_siglip2_vitb16", r_yes["installed"])

            # Kiểm tra file đã có trên máy đích không bị ghi đè
            with open(os.path.join(existing_m, "model.bin"), "rb") as f:
                self.assertEqual(f.read(), b"EXISTING_ON_PC_DO_NOT_OVERWRITE")
            # Kiểm tra model chưa có đã được chép sang
            with open(os.path.join(dst_data, "models", "siglip2_vitb16", "model.bin"), "rb") as f:
                self.assertEqual(f.read(), b"PKG_VERSION_siglip2_vitb16")


if __name__ == "__main__":
    unittest.main()
