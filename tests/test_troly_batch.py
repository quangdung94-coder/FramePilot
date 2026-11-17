"""Phân tích cả project + tắt máy (ADR-0017). TOÀN BỘ lệnh tắt máy và SaveProject là BẢN GIẢ (mock): bộ kiểm thử TUYỆT ĐỐI không tắt máy
thật. Biến môi trường TROLY_NO_SHUTDOWN được đặt ngay khi nạp tệp này để lệnh tắt máy thật tự từ chối nếu lỡ bị gọi."""
import os
os.environ["TROLY_NO_SHUTDOWN"] = "1"                 # chốt an toàn: system_shutdown() thật sẽ ném lỗi

import shutil
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import troly_batch as tb              # noqa: E402


class Calls(object):
    """Ghi lại thứ tự các lệnh (chép lời, thumbnail, lưu, tắt máy) của một lượt chạy giả."""

    def __init__(self, speech=None, thumbs=(True, 5, 5), saves=(True, True), exc=None, on_countdown=None):
        self.log, self.events = [], []
        self._speech = {"ok": True, "stopped": False} if speech is None else speech
        self._thumbs, self._saves, self._exc, self.on_countdown = thumbs, list(saves), exc, on_countdown
        self.an = None

    def speech(self, stop):
        self.log.append("speech")
        if self._exc:
            raise RuntimeError(self._exc)
        return dict(self._speech)

    def thumbs(self, stop, prog):
        self.log.append("thumbs")
        prog(self._thumbs[1], self._thumbs[2])
        return self._thumbs

    def save(self):
        self.log.append("save")
        return self._saves.pop(0) if self._saves else True

    def shutdown(self):
        self.log.append("shutdown")

    def emit(self, kind, data=None):
        self.events.append((kind, data))
        if kind == "analyze_countdown" and self.on_countdown:
            self.on_countdown(data["remaining"], self.an)

    def make(self, countdown=5):
        self.an = tb.AnalyzeAll(self.speech, self.thumbs, self.save, self.shutdown, emit=self.emit, countdown_s=countdown, sleep=lambda s: None)
        return self.an


class AnalyzeAllSafety(unittest.TestCase):
    def test_tat_may_off_thi_khong_luu_khong_dem_nguoc_khong_tat(self):
        c = Calls()
        r = c.make().run(False)
        self.assertEqual(c.log, ["speech", "thumbs"])
        self.assertEqual((r["ok"], r["shutdown"]), (True, "off"))
        self.assertFalse([e for e in c.events if e[0] in ("analyze_countdown", "analyze_shutdown")])

    def test_tat_may_on_luu_truoc_dem_nguoc_roi_tat_dung_mot_lan(self):
        c = Calls()
        r = c.make(countdown=5).run(True)
        self.assertEqual(c.log, ["speech", "thumbs", "save", "save", "shutdown"])           # lưu đầu đếm ngược + lưu lần cuối, rồi mới tắt
        self.assertEqual(r["shutdown"], "sent")
        self.assertEqual([d["remaining"] for k, d in c.events if k == "analyze_countdown"], [5, 4, 3, 2, 1])

    def test_mac_dinh_dem_nguoc_la_2_phut(self):
        self.assertEqual(tb.COUNTDOWN_S, 120)
        c = Calls()
        c.an = tb.AnalyzeAll(c.speech, c.thumbs, c.save, c.shutdown, emit=c.emit, sleep=lambda s: None)
        c.an.run(True)
        self.assertEqual(len([1 for k, _ in c.events if k == "analyze_countdown"]), 120)

    def test_huy_trong_luc_dem_nguoc_thi_khong_tat(self):
        c = Calls(on_countdown=lambda left, an: setattr(an, "cancel_shutdown", True) if left == 3 else None)
        r = c.make(countdown=5).run(True)
        self.assertEqual(r["shutdown"], "cancelled")
        self.assertNotIn("shutdown", c.log)
        self.assertEqual(c.log.count("save"), 1)

    def test_dung_giua_chung_thi_khong_luu_khong_tat(self):
        c = Calls(speech={"ok": False, "stopped": True})
        r = c.make().run(True)
        self.assertTrue(r["stopped"])
        self.assertEqual(c.log, ["speech"])                                                 # không làm thumbnail, không lưu, không tắt
        self.assertEqual(r["shutdown"], "skipped")

    def test_dung_luc_dang_lam_thumbnail_thi_khong_tat(self):
        c = Calls()
        an = c.make()
        orig = c.thumbs
        c.thumbs = lambda stop, prog: (setattr(an, "stop", True), orig(stop, prog))[1]
        an.thumbs_fn = c.thumbs
        r = an.run(True)
        self.assertNotIn("shutdown", c.log)
        self.assertNotIn("save", c.log)
        self.assertTrue(r["stopped"])

    def test_chep_loi_loi_hoac_doi_chieu_lech_thi_khong_tat(self):
        c = Calls(speech={"ok": False, "stopped": False})
        r = c.make().run(True)
        self.assertNotIn("shutdown", c.log)
        self.assertNotIn("save", c.log)
        self.assertEqual(r["shutdown"], "skipped")

    def test_thumbnail_chua_xong_thi_khong_tat(self):
        c = Calls(thumbs=(False, 3, 5))
        r = c.make().run(True)
        self.assertNotIn("shutdown", c.log)
        self.assertEqual(r["shutdown"], "skipped")

    def test_luu_loi_luc_dau_thi_khong_dem_nguoc_khong_tat(self):
        c = Calls(saves=(False,))
        r = c.make().run(True)
        self.assertEqual(c.log, ["speech", "thumbs", "save"])
        self.assertEqual(r["shutdown"], "skipped")
        self.assertIn("lưu", r["reason"])
        self.assertFalse([e for e in c.events if e[0] == "analyze_countdown"])

    def test_luu_loi_luc_cuoi_thi_khong_tat(self):
        c = Calls(saves=(True, False))
        r = c.make().run(True)
        self.assertNotIn("shutdown", c.log)
        self.assertEqual(r["shutdown"], "skipped")

    def test_save_tra_ve_khong_phai_true_thi_coi_la_loi(self):
        c = Calls(saves=(None,))
        self.assertEqual(c.make().run(True)["shutdown"], "skipped")
        self.assertNotIn("shutdown", c.log)

    def test_ngoai_le_bat_ky_thi_khong_tat(self):
        c = Calls(exc="Whisper chết")
        r = c.make().run(True)
        self.assertNotIn("shutdown", c.log)
        self.assertEqual(r["shutdown"], "skipped")
        self.assertIn("Whisper chết", r["reason"])

    def test_lenh_tat_may_loi_thi_khong_ngoai_le(self):
        c = Calls()
        an = c.make()
        an.shutdown_fn = lambda: (_ for _ in ()).throw(OSError("khong co quyen"))
        self.assertEqual(an.run(True)["shutdown"], "skipped")

    def test_lenh_tat_may_that_tu_choi_khi_co_bien_moi_truong(self):
        self.assertEqual(os.environ.get("TROLY_NO_SHUTDOWN"), "1")
        with self.assertRaises(RuntimeError):
            tb.system_shutdown()


class AnalyzeApi(unittest.TestCase):
    """Qua TrolyApi thật (Media Pool giả): mọi thứ ngoài đều là bản giả, kể cả lệnh tắt máy và SaveProject."""

    def setUp(self):
        import test_troly as T
        import troly_api as ta
        self.tmp, self.kho = tempfile.mkdtemp(), tempfile.mkdtemp()
        sel = T.FFolder("01_SELECTED", [T.FItem("a", T.props("DGa.MP4", "Sat Oct 17 2026 08:10:00", "Sat Oct 17 08:10:06 2026", 300, Type="Video + Audio")),
                                        T.FItem("b", T.props("DGb.MP4", "Sat Oct 17 2026 08:20:00", "Sat Oct 17 08:20:06 2026", 300, Type="Video + Audio"))])
        foot = T.FFolder("01_footage")
        foot.subs.append(sel)
        root = T.FFolder("Master")
        root.subs.append(foot)
        self.pool = T.FPool(root)
        self.name = "2026.10.17.LV_Ten"
        self.events = []
        self.api = ta.TrolyApi(self.name, self.tmp, emit=lambda k, d: self.events.append((k, d)),
                               resolve_factory=lambda: T.FResolve(T.FProject(self.name, self.pool)), start_worker=False)
        w = self.api._worker
        w.connect()
        self.api.init()
        while not w.jobs.empty():
            j, a = w.jobs.get()
            getattr(w, "do_" + j)(a)
        self.api._drain()
        self.api.load("Master/01_footage/01_SELECTED")
        while not w.jobs.empty():
            j, a = w.jobs.get()
            getattr(w, "do_" + j)(a)
        self.api._drain()
        self.api.speech_set_dir(self.kho, "vi")
        self.log = []
        self.api._analyze_speech = lambda stop: (self.log.append("speech"), {"ok": True, "stopped": False})[1]
        self.api._wait_thumbs = lambda stop, prog: (self.log.append("thumbs"), (True, 2, 2))[1]
        self.api._save_project = lambda: (self.log.append("save"), True)[1]
        self.api._shutdown_fn = lambda: self.log.append("shutdown")
        self.api._analyze_countdown, self.api._analyze_sleep = 3, lambda s: None

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.kho, ignore_errors=True)

    def wait(self):
        for _ in range(200):
            if self.api._analyze is None:
                return
            threading.Event().wait(0.02)
        self.fail("phân tích không kết thúc")

    def test_mac_dinh_khong_tat_may(self):
        r = self.api.analyze_start()                                    # không truyền shutdown
        self.assertEqual((r["ok"], r["shutdown"]), (True, False))
        self.wait()
        self.assertEqual(self.log, ["speech", "thumbs"])
        self.assertEqual([d for k, d in self.events if k == "analyze_done"][-1]["shutdown"], "off")

    def test_tick_tat_may_chay_du_chuoi_va_tat_bang_ban_gia(self):
        self.assertTrue(self.api.analyze_start(True)["ok"])
        self.wait()
        self.assertEqual(self.log, ["speech", "thumbs", "save", "save", "shutdown"])
        self.assertEqual([d for k, d in self.events if k == "analyze_done"][-1]["shutdown"], "sent")

    def test_dung_thi_khong_tat_may(self):
        self.api._analyze_sleep = lambda s: self.api.analyze_stop()     # bấm Dừng ngay lúc đếm ngược
        self.api.analyze_start(True)
        self.wait()
        self.assertNotIn("shutdown", self.log)

    def test_huy_tat_may_thi_khong_tat(self):
        self.api._analyze_sleep = lambda s: self.api.analyze_cancel_shutdown()
        self.api.analyze_start(True)
        self.wait()
        self.assertNotIn("shutdown", self.log)
        self.assertEqual([d for k, d in self.events if k == "analyze_shutdown"][-1]["state"], "cancelled")

    def test_dong_cua_so_giua_chung_thi_khong_tat(self):
        self.api._analyze_sleep = lambda s: self.api.close()
        self.api.analyze_start(True)
        self.wait()
        self.assertNotIn("shutdown", self.log)

    def test_khong_chay_hai_luot_cung_luc_va_can_dieu_kien(self):
        ev = threading.Event()
        self.api._analyze_speech = lambda stop: (ev.wait(2), {"ok": True})[1]
        self.assertTrue(self.api.analyze_start()["ok"])
        self.assertIn("error", self.api.analyze_start())
        self.assertTrue(self.api.analyze_state()["running"])
        ev.set()
        self.wait()
        api2 = type(self.api)(self.name + "x", tempfile.mkdtemp(), start_worker=False)
        try:
            self.assertIn("error", api2.analyze_start())                # chưa đọc clip
        finally:
            api2._thumbs.shutdown()


class WorkerSaveProject(unittest.TestCase):
    """do_save_project: gọi SaveProject đúng project, báo lỗi rõ, luôn nhả event."""

    def make(self, save_ok=True, name="P", current="P"):
        import queue
        import troly_resolve as tr

        class PM(object):
            def __init__(self):
                self.saved = 0

            def GetCurrentProject(self):
                return Proj()

            def SaveProject(self):
                self.saved += 1
                return save_ok

        class Proj(object):
            def GetName(self):
                return current

            def GetUniqueId(self):
                return "u"

        class Res(object):
            def __init__(self, pm):
                self.pm = pm

            def GetProjectManager(self):
                return self.pm
        pm = PM()
        q = queue.Queue()
        w = tr.TrolyWorker(name, q, resolve_factory=lambda: Res(pm))
        return w, pm, q

    def run_save(self, w):
        box = {"event": threading.Event(), "ok": False}
        w.do_save_project(box)
        self.assertTrue(box["event"].is_set())
        return box["ok"]

    def test_luu_thanh_cong(self):
        w, pm, q = self.make()
        self.assertTrue(self.run_save(w))
        self.assertEqual(pm.saved, 1)

    def test_davinci_tra_false_la_loi(self):
        w, pm, q = self.make(save_ok=False)
        self.assertFalse(self.run_save(w))
        self.assertEqual(q.get_nowait()[0], "error")

    def test_dang_mo_project_khac_thi_khong_luu(self):
        w, pm, q = self.make(name="P", current="Q")
        self.assertFalse(self.run_save(w))
        self.assertEqual(pm.saved, 0)


if __name__ == "__main__":
    unittest.main()
