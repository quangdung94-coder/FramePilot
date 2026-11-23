"""Unit tests for 50-step small-action Ctrl+Z / Ctrl+Y undo-redo stack & Page 2 Shift multi-select (Hướng A)."""
import datetime
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

import troly_api as ta  # noqa: E402
import troly_core as tc  # noqa: E402


def _mk_clip(uid, name, hh, mm, dur=10.0):
    dt = datetime.datetime(2026, 11, 22, hh, mm, 0)
    return tc.Clip(
        uid=uid, name=name, path="J:/test/" + name, rel="01/" + name,
        dur=dur, fps=25.0, frames=int(dur * 25), t_start=dt, t_src="created",
        camera="A", bin_path="Master", clip_color="", mark_in=None, mark_out=None, tc="00:00:00:00",
    )


class TestPlanUndoRedoAndPage2Shift(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.api = ta.TrolyApi("FP_TEST_UNDO", self.tmp.name, start_worker=False)
        clips = [
            _mk_clip("u1", "C01.MP4", 9, 0),
            _mk_clip("u2", "C02.MP4", 9, 5),
            _mk_clip("u3", "C03.MP4", 9, 10),
        ]
        self.api._clips = clips
        self.api._by_uid = {c.uid: c for c in clips}
        self.api._day0 = datetime.datetime(2026, 11, 22, 0, 0, 0)
        self.api._plan["stages"] = [
            tc.make_stage("Đón khách", 540, 600, ["Decor", "Khách"], 0),
            tc.make_stage("Nghi lễ", 600, 660, ["Phát biểu"], 1),
        ]
        self.api._plan["moves"] = [{"at": "20:00", "n": 99, "log": []}]
        self.api._recount()

    def tearDown(self):
        self.tmp.cleanup()

    def test_undo_redo_small_actions_across_pages_and_preserves_moves(self):
        # 1) Label clip on Page 2
        self.api.label(["u1"], 0, "Decor")
        self.assertEqual(tc.label_of(self.api._plan, self.api._by_uid["u1"])["bin"], "Decor")
        # 2) Toggle star on Page 2/3
        self.api.toggle_star(["u1"])
        self.assertTrue(tc.is_starred(self.api._plan, self.api._by_uid["u1"]))
        # 3) Set In/Out on Page 3
        self.api.set_inout("u1", 1.0, 5.0)
        self.assertEqual(tc.manual_inout(self.api._plan, self.api._by_uid["u1"]), (1.0, 5.0))
        # 4) Toggle mute A1 on Page 4
        self.api.toggle_mute(["u1"])
        self.assertTrue(tc.is_muted(self.api._plan, self.api._by_uid["u1"]))
        # 5) Change Page 5 target
        self.api.dur_set_target(15)
        self.assertEqual(self.api._plan["durations"]["target_min"], 15.0)

        # Undo 5 times step-by-step
        r = self.api.plan_undo()
        self.assertEqual(r["undo_info"]["action"], "Đổi mục tiêu thời lượng")
        self.assertNotIn("target_min", self.api._plan.get("durations") or {})

        r = self.api.plan_undo()
        self.assertFalse(tc.is_muted(self.api._plan, self.api._by_uid["u1"]))

        r = self.api.plan_undo()
        self.assertIsNone(tc.manual_inout(self.api._plan, self.api._by_uid["u1"]))

        r = self.api.plan_undo()
        self.assertFalse(tc.is_starred(self.api._plan, self.api._by_uid["u1"]))

        r = self.api.plan_undo()
        self.assertIsNone(tc.label_of(self.api._plan, self.api._by_uid["u1"]))

        # Stack now empty -> returns empty: True
        self.assertTrue(self.api.plan_undo()["empty"])
        # Big DaVinci move history MUST remain intact!
        self.assertEqual(len(self.api._plan["moves"]), 1)
        self.assertEqual(self.api._plan["moves"][0]["n"], 99)

        # Redo restores step-by-step
        r = self.api.plan_redo()
        self.assertEqual(tc.label_of(self.api._plan, self.api._by_uid["u1"])["bin"], "Decor")
        r = self.api.plan_redo()
        self.assertTrue(tc.is_starred(self.api._plan, self.api._by_uid["u1"]))

    def test_undo_stack_capped_at_50(self):
        for i in range(60):
            self.api.toggle_star(["u1"])
        self.assertEqual(len(self.api._undo_stack), 50)

    def test_frontend_ctrlz_ctrly_and_page2_shift_huong_a(self):
        with open(os.path.join(APP, "troly_web", "app.js"), encoding="utf-8") as f:
            app_js = f.read()
        with open(os.path.join(APP, "troly_web", "player.js"), encoding="utf-8") as f:
            pl_js = f.read()
        self.assertIn("api().plan_undo()", app_js)
        self.assertIn("api().plan_redo()", app_js)
        self.assertIn('e.code === "KeyY"', app_js)
        self.assertIn("if (e.shiftKey || e.ctrlKey || e.metaKey) { e.preventDefault(); return; }", app_js)
        # Hướng A: Hover scrub on #grid must NOT auto-call moveCur()
        idx_hs = pl_js.find("function initGridHoverScrub")
        hs_block = pl_js[idx_hs:idx_hs + 1500]
        self.assertNotIn("moveCur(idx)", hs_block)

    def test_hover_scrub_plopen_khong_bi_chan_boi_curclip(self):
        """Hồi quy 23/11: Hover Scrub gọi plOpen(c) mà không đổi curClip(); plOpen phải kiểm PL.uid/PL.seq chứ không kiểm curClip().uid."""
        with open(os.path.join(APP, "troly_web", "player.js"), encoding="utf-8") as f:
            pl_js = f.read()
        opn = pl_js[pl_js.index("async function plOpen(c)"):pl_js.index('$("plPlay").onclick')]
        self.assertNotIn("curClip().uid !== uid", opn)
        self.assertIn("PL.uid !== uid", opn)
        self.assertIn("PL.seq !== seq", opn)
        # loadedmetadata phải chỉ gọi plRenderIo(curC) khi clip đang mở đúng là curClip()
        lm = pl_js[pl_js.index('v.addEventListener("loadedmetadata"'):pl_js.index('v.addEventListener("timeupdate"')]
        self.assertIn("curC && curC.uid === PL.uid", lm)


if __name__ == "__main__":
    unittest.main()
