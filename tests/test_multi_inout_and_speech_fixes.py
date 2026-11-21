import datetime
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
WEB = os.path.join(APP, "troly_web")
if APP not in sys.path:
    sys.path.insert(0, APP)

import troly_api as ta  # noqa: E402
import troly_core as tc  # noqa: E402
import troly_dur as td  # noqa: E402
import troly_env as te  # noqa: E402
import troly_speech as tsp  # noqa: E402


def _clip(uid, name, dur=30.0):
    return tc.Clip(
        uid=uid,
        name=name,
        rel=name,
        path=os.path.join("D:\\Media", name),
        t_start=datetime.datetime(2026, 10, 25, 9, 0, 0),
        t_src="mtime",
        dur=dur,
        fps=25.0,
        camera="C",
        lut="",
    )


class TestMultiInoutAndSpeechFixes(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_cfg = os.environ.get("TROLY_CONFIG")
        os.environ["TROLY_CONFIG"] = os.path.join(self._tmp.name, "config.json")
        self._data_root = os.path.join(self._tmp.name, "data")
        os.makedirs(self._data_root, exist_ok=True)
        te.save_config({"data_root": self._data_root})

    def tearDown(self):
        if self._old_cfg is None:
            os.environ.pop("TROLY_CONFIG", None)
        else:
            os.environ["TROLY_CONFIG"] = self._old_cfg
        self._tmp.cleanup()

    def test_hallu_regex_catches_youtube_phrases(self):
        samples = [
            "Cảm ơn các bạn đã xem video hấp dẫn.",
            "Hãy subrisb kênh để ủng hộ nhé",
            "Nhớ bấm chuông và like và share nha",
            "Hẹn gặp lại các bạn ở những video tiếp theo",
        ]
        for s in samples:
            self.assertIsNotNone(tsp.HALLU.search(s), f"Missed hallucination: {s}")

    def test_manual_inouts_core_and_api(self):
        plan = tc.new_plan("LV_Multi")
        c = _clip("u1", "C0001.MP4", dur=30.0)
        res = tc.set_manual_inouts(plan, c, [(1.0, 4.0), (10.0, 14.0)])
        self.assertEqual(res, [(1.0, 4.0), (10.0, 14.0)])
        self.assertEqual(tc.manual_inout(plan, c), (1.0, 4.0))
        self.assertEqual(tc.manual_inouts(plan, c), [(1.0, 4.0), (10.0, 14.0)])

        api = ta.TrolyApi("LV_Multi", self._data_root, start_worker=False, thumb_workers=1)
        api._clips = [c]
        api._by_uid = {c.uid: c}
        r = api.set_inouts("u1", [[2.0, 5.0], [12.0, 16.0]])
        self.assertTrue(r.get("ok"))
        self.assertEqual(r.get("inouts"), [[2.0, 5.0], [12.0, 16.0]])
        self.assertEqual(r.get("in_s"), 2.0)
        self.assertEqual(r.get("out_s"), 5.0)

        st = api.state()
        self.assertEqual(st["clips"][0]["inouts"], [[2.0, 5.0], [12.0, 16.0]])

    def test_step5_expands_multiple_spans_onto_timeline(self):
        plan = tc.new_plan("LV_Multi")
        c = _clip("u1", "C0001.MP4", dur=30.0)
        tc.toggle_star(plan, c)
        tc.set_label(plan, c, "01_Sáng", "Decor", by="manual")
        tc.set_manual_inouts(plan, c, [(1.0, 4.0), (10.0, 14.0)])
        stages = [{"name": "01_Sáng", "bins": ["Decor"]}]
        assign = {"u1": 0}
        res = td.build(plan, [c], assign, stages)
        self.assertAlmostEqual(res["total_s"], 7.0, places=2)
        items = res["items"]
        self.assertEqual(len(items), 2)
        self.assertAlmostEqual(items[0]["in_s"], 1.0, places=2)
        self.assertAlmostEqual(items[0]["out_s"], 4.0, places=2)
        self.assertAlmostEqual(items[1]["in_s"], 10.0, places=2)
        self.assertAlmostEqual(items[1]["out_s"], 14.0, places=2)

    def test_web_wiring_page4_cors_hide_bad_and_shift_io(self):
        with open(os.path.join(WEB, "index.html"), "r", encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(WEB, "speech.js"), "r", encoding="utf-8") as f:
            speech_js = f.read()
        with open(os.path.join(WEB, "player.js"), "r", encoding="utf-8") as f:
            player_js = f.read()

        self.assertIn('id="lnHideBad"', html)
        self.assertIn('v.crossOrigin = "anonymous"', speech_js)
        self.assertIn("LN.hideBad", speech_js)
        self.assertIn('plMark("in", e.shiftKey)', player_js)
        self.assertIn('plMark("out", e.shiftKey)', player_js)
        self.assertIn("set_inouts(", player_js)


if __name__ == "__main__":
    unittest.main()
