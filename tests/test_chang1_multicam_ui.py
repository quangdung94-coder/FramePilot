"""Kiểm thử Chặng 1: Nhiều camera trọn bộ 5 trang + Reject (X) + AI Search/Similar + Cache Manager + Hardware + V1..V3."""
import os
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.abspath(os.path.join(HERE, "..", "app"))
WEB = os.path.join(APP, "troly_web")
sys.path.insert(0, APP)

import troly_api as ta
import troly_core as tc
import troly_hw as hw
import troly_resolve as tr


class TestChang1Backend(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.api = ta.TrolyApi("P_MC_TEST", self.tmp.name, emit=lambda *a: None, start_worker=False)
        self.c1 = tc.Clip(uid="u1", rel="A001.mp4", name="A001.mp4", t_start=tc.datetime.datetime(2026, 11, 20, 9, 0, 0),
                          dur=30.0, fps=25.0, frames=750, bin_path="Master/01")
        self.c2 = tc.Clip(uid="u2", rel="B001.mp4", name="B001.mp4", t_start=tc.datetime.datetime(2026, 11, 20, 9, 0, 5),
                          dur=30.0, fps=25.0, frames=750, bin_path="Master/01")
        self.api._clips = [self.c1, self.c2]
        self.api._by_uid = {c.uid: c for c in self.api._clips}
        self.api._day0 = tc.datetime.datetime(2026, 11, 20, 0, 0, 0)
        self.api._machines = [
            {"key": "t1", "letter": "A", "name": "Máy A · A001", "color": "#4FC1A6", "prefix": "A", "n": 1},
            {"key": "t2", "letter": "B", "name": "Máy B · B001", "color": "#C98BE0", "prefix": "B", "n": 1},
        ]
        self.api._mk_letter = {"u1": "A", "u2": "B"}
        self.api._plan["stages"] = [{"name": "Gia tiên", "start": 530.0, "end": 560.0, "color": "#F2A33A", "bins": ["Nghi lễ", "Decor"]}]
        self.api._assign = {"u1": 0, "u2": 0}

    def tearDown(self):
        self.tmp.cleanup()

    def test_hw_detect_returns_valid_fields(self):
        info = hw.detect(refresh=True)
        for k in ("os", "accel", "gpu_name", "cpu_cores", "tier", "thumb_workers", "wave_workers"):
            self.assertIn(k, info)
        self.assertGreaterEqual(info["thumb_workers"], 1)

    def test_toggle_reject_and_rename_machine(self):
        st = self.api.toggle_reject(["u1"], True)
        self.assertEqual(st["n_rejected"], 1)
        u1 = next(c for c in st["clips"] if c["uid"] == "u1")
        self.assertTrue(u1["rejected"])
        st2 = self.api.rename_machine("t1", "Máy A · Cô dâu")
        m1 = next(m for m in st2["machines"] if m["key"] == "t1")
        self.assertEqual(m1["name"], "Máy A · Cô dâu")

    def test_ai_similar_vector_and_text_search(self):
        self.api._ai_cache = {
            "sig": (0, 0),
            "vec": {"A001.mp4": np.array([1.0, 0.0], dtype=np.float32), "B001.mp4": np.array([0.9, 0.1], dtype=np.float32)},
            "desc": {"bins": {"B001.mp4": {"bin": "Decor", "score": 0.9}}},
        }
        sim = self.api.ai_similar("u1")
        self.assertEqual(sim["mode"], "vector")
        self.assertEqual(sim["uids"], ["u2"])
        sr = self.api.ai_search("decor")
        self.assertIn("u2", sr["uids"])

    def test_cache_clear_preserves_plan_json(self):
        self.api._save_now()
        pfile = tc.plan_path(self.tmp.name, "P_MC_TEST")
        tdir = os.path.join(self.tmp.name, "cache", "troly_thumbs", tc._safe("P_MC_TEST"))
        os.makedirs(tdir, exist_ok=True)
        with open(os.path.join(tdir, "x.jpg"), "wb") as f:
            f.write(b"123")
        self.assertTrue(os.path.isfile(pfile))
        res = self.api.cache_clear(tc._safe("P_MC_TEST"))
        self.assertTrue(res["ok"])
        self.assertFalse(os.path.isdir(tdir))
        self.assertTrue(os.path.isfile(pfile))

    def test_dur_view_marks_multicam_overlap(self):
        tc.toggle_star(self.api._plan, self.c1)
        tc.toggle_star(self.api._plan, self.c2)
        tc.set_label(self.api._plan, self.c1, "Gia tiên", "Nghi lễ")
        tc.set_label(self.api._plan, self.c2, "Gia tiên", "Nghi lễ")
        self.api._plan.setdefault("inout", {})["A001.mp4"] = [2.0, 12.0]
        self.api._plan.setdefault("inout", {})["B001.mp4"] = [2.0, 12.0]
        dv = self.api.dur_state()
        self.assertEqual(dv["n_machines"], 2)
        self.assertTrue(all(it["overlap"] for it in dv["items"]))
        self.assertEqual({it["mk"] for it in dv["items"]}, {"A", "B"})


class TestFrontendWiring(unittest.TestCase):
    def test_new_ui_controls_present(self):
        def rd(fn):
            with open(os.path.join(WEB, fn), encoding="utf-8") as f:
                return f.read()
        html, app_js, sp_js, s5_js = rd("index.html"), rd("app.js"), rd("speech.js"), rd("step5.js")
        for eid in ("p2Find", "p2SimBtn", "hideRej", "waveZIn", "waveSnap", "lnPickBox", "lnGolden", "lnDedup", "d5Presets", "d5CamTrack", "setCacheList", "helpModal"):
            self.assertIn(eid, html)
        self.assertIn("toggle_reject", app_js)
        self.assertIn("speech_start(bins, cams)", sp_js)
        self.assertIn("dur_create_timeline(multiTrack, chosenName)", s5_js)
        self.assertIn("d5TlName", s5_js)

    def test_dur_create_timeline_custom_name(self):
        api = ta.TrolyApi("P_TL_NAME", tempfile.mkdtemp(), emit=lambda *a: None, start_worker=False)
        c1 = tc.Clip(uid="u1", rel="A001.mp4", name="A001.mp4", t_start=tc.datetime.datetime(2026, 11, 20, 9, 0, 0),
                     dur=20.0, fps=25.0, frames=500, bin_path="Master/01")
        api._clips = [c1]
        api._by_uid = {"u1": c1}
        api._day0 = tc.datetime.datetime(2026, 11, 20, 0, 0, 0)
        api._plan["stages"] = [{"name": "Gia tiên", "start": 530.0, "end": 560.0, "color": "#F2A33A", "bins": ["Nghi lễ"]}]
        api._assign = {"u1": 0}
        tc.toggle_star(api._plan, c1)
        tc.set_label(api._plan, c1, "Gia tiên", "Nghi lễ")
        api._plan.setdefault("inout", {})["A001.mp4"] = [2.0, 10.0]
        r = api.dur_create_timeline(False, "Highlight Cuoi 2026")
        self.assertTrue(r.get("ok"))
        self.assertEqual(r.get("name"), "Highlight Cuoi 2026")


if __name__ == "__main__":
    unittest.main()
