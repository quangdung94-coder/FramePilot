"""Kiểm thử In/Out (ADR-0016): đổi frame<->timecode khi Start TC khác 0, đặt tay lưu/nạp, đặt tay thắng gợi ý/DaVinci,
sao lưu rồi Hoàn tác đúng, ghi lỗi một phần báo rõ. Media Pool giả, không cần DaVinci."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_troly as T                # noqa: E402
import test_troly_api as TA           # noqa: E402
import troly_api as ta                # noqa: E402
import troly_core as tc               # noqa: E402


class MItem(T.FItem):
    """FItem có SetMarkInOut/ClearMarkInOut như DaVinci thật: nhận số frame từ đầu file, chuỗi bị từ chối."""
    refuse = False
    drift = 0

    def SetMarkInOut(self, a, b, kind="all"):
        if self.refuse or not isinstance(a, int) or not isinstance(b, int):
            return False
        self.marks = {"video": {"in": a + self.drift, "out": b}, "audio": {"in": a + self.drift, "out": b}}
        return True

    def ClearMarkInOut(self, kind="all"):
        self.marks = {"video": {}, "audio": {}}
        return True


class Frames(unittest.TestCase):
    def test_tc_roundtrip_start_tc_not_zero(self):
        # file bắt đầu 00:42:38:24 @50fps (đo thật), frame 10 từ đầu file
        st = "00:42:38:24"
        self.assertEqual(tc.start_tc_frames(st, 50.0), (42 * 60 + 38) * 50 + 24)
        self.assertEqual(tc.file_frame_to_tc(0, st, 50.0), st)
        self.assertEqual(tc.file_frame_to_tc(10, st, 50.0), "00:42:38:34")
        self.assertEqual(tc.tc_to_file_frame("00:42:38:34", st, 50.0), 10)
        for f in (0, 1, 49, 50, 239):
            self.assertEqual(tc.tc_to_file_frame(tc.file_frame_to_tc(f, st, 50.0), st, 50.0), f)
        self.assertEqual(tc.tc_to_file_frame("01:00:00:00", "01:00:00:00", 25.0), 0)
        self.assertEqual(tc.start_tc_frames("hỏng", 25.0), 0)

    def test_secs_frames(self):
        self.assertEqual(tc.secs_to_frames(1.2, 50.0), 60)
        self.assertAlmostEqual(tc.frames_to_secs(60, 50.0), 1.2)
        self.assertEqual(tc.secs_to_frames(0.5, 29.97), 15)

    def test_clamp(self):
        self.assertEqual(tc.clamp_inout(3.0, 1.0, 10.0, 25.0), (1.0, 3.0))          # đảo thứ tự
        self.assertEqual(tc.clamp_inout(-5, 99, 10.0, 25.0), (0.0, 10.0))
        a, b = tc.clamp_inout(4.0, 4.0, 10.0, 25.0)
        self.assertAlmostEqual(b - a, 0.04)
        self.assertEqual(tc.clamp_inout(10.0, 12.0, 10.0, 25.0)[1], 10.0)


class Plan(unittest.TestCase):
    def mk(self, **kw):
        d = dict(uid="u", rel="01_footage/A.MP4", dur=10.0, fps=25.0, frames=250, mark_in=None, mark_out=None)
        d.update(kw)
        return tc.Clip(**d)

    def test_manual_wins_and_persists(self):
        tmp = tempfile.mkdtemp()
        try:
            c = self.mk(mark_in=25, mark_out=100)                       # DaVinci: 1.0s - 4.0s
            plan = tc.new_plan("2026.10.17.LV_Mau")
            self.assertEqual(tc.effective_inout(plan, c), (1.0, 4.0, "davinci"))
            tc.set_manual_inout(plan, c, 2.0, 6.0)
            self.assertEqual(tc.effective_inout(plan, c), (2.0, 6.0, "manual"))   # đặt tay thắng DaVinci
            tc.save_plan(tmp, plan)
            plan2 = tc.load_plan(tmp, "2026.10.17.LV_Mau")                 # nạp lại đúng
            self.assertEqual(tc.effective_inout(plan2, c), (2.0, 6.0, "manual"))
            self.assertEqual(tc.inout_frames(plan2, c), (50, 150))
            tc.set_manual_inout(plan2, c, None, None)
            self.assertEqual(tc.effective_inout(plan2, c)[2], "davinci")
            self.assertIsNone(tc.inout_frames(plan2, c))                   # gợi ý tự động KHÔNG bao giờ được ghi
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_frames_clamped_to_clip(self):
        c = self.mk(frames=100)
        plan = tc.new_plan("p")
        plan["inout"] = {c.rel: [1.0, 30.0]}
        self.assertEqual(tc.inout_frames(plan, c), (25, 99))


class Api(TA.Api):
    """Dùng lại giả lập của test_troly_api nhưng clip có SetMarkInOut."""

    def setUp(self):
        super().setUp()
        for i, it in enumerate(self.sel.clips):
            self.sel.clips[i] = MItem(it.uid, it.props, it.marks)

    def prep(self):
        self.load()
        # nạp lại để worker thấy MItem
        self.api.load(TA.PATH)
        self.run_jobs()

    def marks(self, uid):
        return next(i for i in self.sel.clips if i.uid == uid).marks

    def test_write_backup_undo(self):
        self.prep()
        old_a = {"video": {"in": 5, "out": 40}, "audio": {"in": 5, "out": 40}}
        next(i for i in self.sel.clips if i.uid == "a").marks = old_a
        self.assertEqual(self.api.set_inout("a", 1.0, 3.0)["in_s"], 1.0)    # giả lập 50fps -> frame 50..150
        self.api.set_inout("b", 2.0, 4.0)
        self.api.toggle_star(["a", "b", "c"])
        pv = self.api.inout_write_preview("starred")
        self.assertEqual((pv["pool"], pv["n"], pv["skip"]), (3, 2, 1))        # c có sao nhưng chưa đặt tay -> bỏ qua
        self.assertTrue(self.api.inout_write("starred")["ok"])
        self.run_jobs()
        self.assertEqual(self.marks("a")["video"], {"in": 50, "out": 150})
        self.assertEqual(self.marks("b")["video"], {"in": 100, "out": 200})
        self.assertEqual(self.marks("c"), {})                                 # clip khác KHÔNG bị chạm
        self.assertIn("khớp 100%", self.last("status")["text"])
        bk = tc.latest_inout_backup(self.tmp, "2026.10.17.LV_Mau")
        data = json.load(open(bk, encoding="utf-8"))
        ent = {e["uid"]: e for e in data["entries"]}
        self.assertEqual((ent["a"]["in"], ent["a"]["out"]), (5, 40))          # sao lưu In/Out cũ
        self.assertEqual((ent["b"]["in"], ent["b"]["out"]), (None, None))
        self.assertTrue(self.api.inout_undo()["ok"])
        self.run_jobs()
        self.assertEqual(self.marks("a")["video"], {"in": 5, "out": 40})      # khôi phục đúng bản cũ
        self.assertEqual(self.marks("b"), {"video": {}, "audio": {}})
        self.assertIsNone(tc.latest_inout_backup(self.tmp, "2026.10.17.LV_Mau"))

    def test_partial_failure_reported(self):
        self.prep()
        self.api.set_inout("a", 1.0, 3.0)
        self.api.set_inout("b", 2.0, 4.0)
        next(i for i in self.sel.clips if i.uid == "b").refuse = True
        self.api.inout_write("selected", ["a", "b"])
        self.run_jobs()
        txt = self.last("status")["text"]
        self.assertIn("khớp 1/2", txt)
        self.assertIn("LỖI", txt)
        self.assertEqual(self.last("status")["kind"], "warn")

    def test_mismatch_detected(self):
        self.prep()
        self.api.set_inout("a", 1.0, 3.0)
        next(i for i in self.sel.clips if i.uid == "a").drift = 1            # DaVinci đọc lại lệch 1 frame
        self.api.inout_write("selected", ["a"])
        self.run_jobs()
        self.assertIn("LỖI/LỆCH", self.last("status")["text"])

    def test_state_fields_and_clear(self):
        st = self.load()
        self.api.set_inout("a", 1.0, 3.0)
        a = next(c for c in self.api.state()["clips"] if c["uid"] == "a")
        self.assertEqual((a["in_s"], a["out_s"], a["io_src"]), (1.0, 3.0, "manual"))
        self.api.set_inout("a", None, None)
        a = next(c for c in self.api.state()["clips"] if c["uid"] == "a")
        self.assertIsNone(a["io_src"])
        self.assertIn("error", self.api.set_inout("zzz", 1, 2))

    def test_speech_inout_goes_to_write(self):
        self.prep()
        self.api.speech_set_inout("a", 1.5, 3.5)                              # tab Lời nói lưu vào kế hoạch panel
        pv = self.api.inout_write_preview("selected", ["a"])
        self.assertEqual(pv["n"], 1)
        self.api.inout_write("selected", ["a"])
        self.run_jobs()
        self.assertEqual(self.marks("a")["video"], {"in": 75, "out": 175})    # 1.5s và 3.5s ở 50fps


del TA.Api   # tránh chạy lại các bài của lớp gốc trong module này


if __name__ == "__main__":
    unittest.main()
