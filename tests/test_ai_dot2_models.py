"""Kiểm thử tích hợp AI Đợt 2:
- SigLIP 2 ưu tiên cao nhất trong troly_ai.py (tách cache troly_embed_siglip2).
- DINOv2-small ưu tiên cho nút 'Tìm góc tương tự' (ai_similar -> mode='dino').
- CLAP (troly_audio_events.py + api.audio_events + Page 3 nút Tiếng động AI).
- WavLM-SV tách người nói MC/Gia đình (troly_diarize_worker.py + api.speech_diarize + Page 4 nút Tách người nói).
"""
import datetime
import os
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
sys.path.insert(0, APP)

import troly_ai as ai  # noqa: E402
import troly_api as ta  # noqa: E402
import troly_core as tc  # noqa: E402


class TestAiDot2(unittest.TestCase):
    def test_siglip2_and_dinov2_detection_and_cache_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(ai.has_siglip2(tmp))
            self.assertFalse(ai.has_dinov2(tmp))
            os.makedirs(os.path.join(tmp, "models", ai.SIGLIP2_DIR_NAME), exist_ok=True)
            with open(os.path.join(tmp, "models", ai.SIGLIP2_DIR_NAME, ai.MODEL_FILE), "wb") as f:
                f.write(b"0")
            os.makedirs(os.path.join(tmp, "models", ai.DINOV2_DIR_NAME), exist_ok=True)
            with open(os.path.join(tmp, "models", ai.DINOV2_DIR_NAME, "config.json"), "w", encoding="utf-8") as f:
                f.write("{}")
            self.assertTrue(ai.has_siglip2(tmp))
            self.assertTrue(ai.has_dinov2(tmp))
            self.assertIn("troly_embed_siglip2", ai.embed_dir(tmp, "P_S2"))

    def test_ai_similar_prefers_dinov2_vectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            api = ta.TrolyApi("P_DINO", tmp, emit=lambda *a: None, start_worker=False)
            c1 = tc.Clip(uid="u1", rel="01/A1.MP4", name="A1.MP4", t_start=datetime.datetime(2026, 11, 21, 9, 0, 0), dur=10.0)
            c2 = tc.Clip(uid="u2", rel="01/A2.MP4", name="A2.MP4", t_start=datetime.datetime(2026, 11, 21, 9, 1, 0), dur=10.0)
            c3 = tc.Clip(uid="u3", rel="01/A3.MP4", name="A3.MP4", t_start=datetime.datetime(2026, 11, 21, 9, 2, 0), dur=10.0)
            api._clips = [c1, c2, c3]
            api._by_uid = {c.uid: c for c in api._clips}
            k1, k2, k3 = ai.ck(c1.rel), ai.ck(c2.rel), ai.ck(c3.rel)
            api._ai_cache = {
                "sig": (0, 0),
                "vec": {},
                "dino": {
                    k1: np.array([1.0, 0.0], dtype=np.float32),
                    k2: np.array([0.1, 0.99], dtype=np.float32),
                    k3: np.array([0.98, 0.2], dtype=np.float32),
                },
                "desc": None,
                "c_scores": None,
            }
            r = api.ai_similar("u1")
            self.assertEqual(r["mode"], "dino")
            self.assertEqual(r["uids"][0], "u3")

    def test_wiring_clap_diarize_and_build_exe(self):
        with open(os.path.join(APP, "troly_web", "index.html"), encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(APP, "troly_web", "step3.js"), encoding="utf-8") as f:
            s3 = f.read()
        with open(os.path.join(APP, "troly_web", "speech.js"), encoding="utf-8") as f:
            sp = f.read()
        with open(os.path.join(HERE, "..", "build_exe.py"), encoding="utf-8") as f:
            be = f.read()
        self.assertIn('id="p3ClapBtn"', html)
        self.assertIn('id="p3ClapTags"', html)
        self.assertIn('id="lnDiarizeBtn"', html)
        self.assertIn("api().audio_events(", s3)
        self.assertIn("api().speech_diarize(", sp)
        self.assertIn("troly_audio_events.py", be)
        self.assertIn("troly_diarize_worker.py", be)
        self.assertTrue(os.path.isfile(os.path.join(APP, "troly_audio_events.py")))
        self.assertTrue(os.path.isfile(os.path.join(APP, "troly_diarize_worker.py")))


if __name__ == "__main__":
    unittest.main()
