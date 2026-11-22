"""Kiểm thử tích hợp Đợt 1:
- Động cơ chép lời AI (Whisper large-v3-turbo / PhoWhisper-medium / Const-me) + cài đặt asr_engine trong Setting.
- MediaPipe Face Landmarker cộng điểm nụ cười và tránh nhắm mắt ở mép In/Out trong troly_vision_io.
- Đóng gói troly_asr_worker.py và troly_face_worker.py trong build_exe.py.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
sys.path.insert(0, APP)

import troly_api as ta  # noqa: E402
import troly_speech as tsp  # noqa: E402
import troly_vision_io as tvio  # noqa: E402


class TestDot1AsrAndFace(unittest.TestCase):
    def test_load_whisper_cfg_selects_engine_from_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_py = os.path.join(tmp, "python.exe")
            open(fake_py, "w").close()
            os.makedirs(os.path.join(tmp, "models", "whisper_large_v3_turbo"), exist_ok=True)
            os.makedirs(os.path.join(tmp, "models", "phowhisper_medium_ct2"), exist_ok=True)
            cfg_p = os.path.join(tmp, "cfg.json")
            old = os.environ.get("TROLY_CONFIG")
            os.environ["TROLY_CONFIG"] = cfg_p
            try:
                with open(cfg_p, "w", encoding="utf-8") as f:
                    json.dump({"data_root": tmp, "ai_python": fake_py, "asr_engine": "auto"}, f)
                c = tsp.load_whisper_cfg()
                self.assertEqual(c["engine"], "whisper_turbo")
                self.assertTrue(c["ct2_dir"].endswith("whisper_large_v3_turbo"))

                with open(cfg_p, "w", encoding="utf-8") as f:
                    json.dump({"data_root": tmp, "ai_python": fake_py, "asr_engine": "phowhisper"}, f)
                c2 = tsp.load_whisper_cfg()
                self.assertEqual(c2["engine"], "phowhisper")
                self.assertTrue(c2["ct2_dir"].endswith("phowhisper_medium_ct2"))

                with open(cfg_p, "w", encoding="utf-8") as f:
                    json.dump({"data_root": tmp, "ai_python": fake_py, "asr_engine": "constme"}, f)
                c3 = tsp.load_whisper_cfg()
                self.assertEqual(c3["engine"], "whisper_turbo" if sys.platform == "darwin" else "constme")
            finally:
                if old is None:
                    os.environ.pop("TROLY_CONFIG", None)
                else:
                    os.environ["TROLY_CONFIG"] = old

    def test_settings_save_and_get_asr_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_p = os.path.join(tmp, "cfg.json")
            with open(cfg_p, "w", encoding="utf-8") as f:
                json.dump({"data_root": tmp}, f)
            old = os.environ.get("TROLY_CONFIG")
            os.environ["TROLY_CONFIG"] = cfg_p
            try:
                api = ta.TrolyApi("P_ASR", tmp, emit=lambda *a: None, start_worker=False)
                r = api.settings_save(tmp, "", None, None, "phowhisper")
                self.assertTrue(r.get("ok"))
                g = api.settings_get()
                self.assertEqual(g["asr_engine"], "phowhisper")
            finally:
                if old is None:
                    os.environ.pop("TROLY_CONFIG", None)
                else:
                    os.environ["TROLY_CONFIG"] = old

    def test_vision_io_prefers_smile_and_avoids_blink(self):
        import cv2
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            vid = os.path.join(tmp, "sample.avi")
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            vw = cv2.VideoWriter(vid, fourcc, 10.0, (160, 90))
            rng = np.random.default_rng(7)
            frame = rng.integers(80, 180, size=(90, 160, 3), dtype=np.uint8)
            for _ in range(100):  # 10 giây
                vw.write(frame)
            vw.release()

            # Giả lập MediaPipe: đoạn sau (6s..10s) có mặt rõ & cười tươi (0.8), đoạn đầu nhắm mắt (0.9)
            def fake_faces(_p, times):
                return [(1.0, 0.85, 0.05) if t >= 5.5 else (1.0, 0.0, 0.9) for t in times]

            with mock.patch.object(tvio, "analyze_proxy_faces", side_effect=fake_faces):
                res = tvio.analyze_proxy_vision(vid, 10.0, target_len=3.0, head_skip=1.0, max_samples=20)
            self.assertIsNotNone(res)
            self.assertGreaterEqual(res["in"], 5.0)
            self.assertIn("Cười tươi", res["rule"])

    def test_wiring_html_js_and_build_exe(self):
        html = open(os.path.join(APP, "troly_web", "index.html"), encoding="utf-8").read()
        js = open(os.path.join(APP, "troly_web", "app.js"), encoding="utf-8").read()
        be = open(os.path.join(HERE, "..", "build_exe.py"), encoding="utf-8").read()
        self.assertIn('id="setAsrSel"', html)
        self.assertIn('setAsrSel', js)
        self.assertIn("troly_asr_worker.py", be)
        self.assertIn("troly_face_worker.py", be)


if __name__ == "__main__":
    unittest.main()
