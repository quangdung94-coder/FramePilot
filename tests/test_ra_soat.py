"""Rà soát lỗi 18/11/2026: mỗi bài chứng minh một lỗi đã tìm thấy (đỏ trước khi sửa, xanh sau khi sửa). Dữ liệu giả, tên ví dụ."""
import concurrent.futures as cf
import os
import queue
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import test_troly as T                # noqa: E402
import troly_api as ta                # noqa: E402
import troly_batch as tb              # noqa: E402
import troly_resolve as tr            # noqa: E402
import troly_speech_run as sr         # noqa: E402


class FailAddPool(T.FPool):
    """AddSubFolder trả None (DaVinci không tạo được bin) cho tên bắt đầu bằng 'B'; đếm số lần MoveClips."""

    def __init__(self, root):
        super().__init__(root)
        self.moves = 0

    def AddSubFolder(self, parent, name):
        if name.startswith("B"):
            return None
        return super().AddSubFolder(parent, name)

    def MoveClips(self, items, dst):
        self.moves += 1
        return super().MoveClips(items, dst)


def make_worker(pool_cls=T.FPool):
    mk = lambda uid, hh: T.FItem(uid, T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:00:00" % hh,        # noqa: E731
                                              "Sat Oct 17 %02d:00:05 2026" % hh, 250, Type="Video + Audio"))
    sel = T.FFolder("01_SELECTED", [mk("a", 6), mk("b", 7), mk("c", 18)])
    foot = T.FFolder("01_footage")
    foot.subs.append(sel)
    root = T.FFolder("Master")
    root.subs.append(foot)
    pool = pool_cls(root)
    q = queue.Queue()
    w = tr.TrolyWorker("P", q, resolve_factory=lambda: T.FResolve(T.FProject("P", pool)))
    w.connect()
    return w, q, pool, sel


class ApplyPartial(unittest.TestCase):
    def test_tao_bin_that_bai_giua_chung_van_bao_clip_da_chuyen_de_hoan_tac(self):
        """Lỗi: bin thứ hai không tạo được -> ném lỗi, nhật ký của clip ĐÃ chuyển bị mất (không Hoàn tác được)."""
        w, q, pool, sel = make_worker(FailAddPool)
        path = "Master/01_footage/01_SELECTED"
        w.do_load(path)
        w.do_apply((path, {"a": ["A_tot"], "b": ["B_hong"]}))
        kinds = {}
        while not q.empty():
            k, d = q.get()
            kinds[k] = d
        log, failed = kinds["applied"]
        self.assertEqual([u for u, _, _ in log], ["a"])                   # clip a đã chuyển thật -> phải có trong nhật ký
        self.assertEqual(failed, 1)                                       # clip b không chuyển được -> tính lỗi


class WrongProject(unittest.TestCase):
    def setUp(self):
        self.w, self.q, self.pool, self.sel = make_worker(FailAddPool)
        self.path = "Master/01_footage/01_SELECTED"
        self.w.do_load(self.path)
        self.w.pm.project = T.FProject("Project khác", self.pool)         # người dựng đổi project trong DaVinci sau khi mở panel

    def test_moi_viec_ghi_tu_choi_khi_davinci_dang_mo_project_khac(self):
        calls = [("do_apply", (self.path, {"a": ["A_tot"]})), ("do_undo", [("a", self.path, self.path + "/x")]),
                 ("do_inout_write", (tempfile.mkdtemp(), "P", [("a", "01_footage/DGa.MP4", 1, 2)])),
                 ("do_inout_restore", "khong_co.json"), ("do_append_timeline", ["a"])]
        for name, arg in calls:
            with self.assertRaises(RuntimeError, msg=name) as cx:
                getattr(self.w, name)(arg)
            self.assertIn("project khác", str(cx.exception), name)
        self.assertEqual(self.pool.moves, 0)                              # không clip nào bị chuyển


class ShutdownCancelRace(unittest.TestCase):
    def test_bam_huy_trong_luc_luu_lan_cuoi_khong_tat_may(self):
        """Lỗi: Huỷ bấm trong lúc SaveProject lần cuối (sau vòng đếm ngược) không còn được kiểm -> vẫn tắt máy."""
        sent = []
        box = {}
        n = {"save": 0}

        def save():
            n["save"] += 1
            if n["save"] == 2:
                box["an"].cancel_shutdown = True                           # người dựng bấm Huỷ giữa lúc lưu lần cuối
            return True
        an = tb.AnalyzeAll(lambda stop: {"ok": True}, lambda stop, prog: (True, 3, 3), save, lambda: sent.append(1), countdown_s=1, sleep=lambda s: None)
        box["an"] = an
        res = an.run(True)
        self.assertEqual(sent, [])
        self.assertEqual(res["shutdown"], "cancelled")


class ThumbSlotLeak(unittest.TestCase):
    def test_thumbnail_loi_ngoai_le_khong_ket_cho_trong_hang_doi(self):
        """Lỗi: future ném ngoại lệ thì uid kẹt mãi trong _inflight (hết chỗ làm thumbnail, 'Phân tích cả project' kẹt 300 giây)."""
        tmp = tempfile.mkdtemp()
        api = ta.TrolyApi("P", tmp, resolve_factory=lambda: None, start_worker=False)
        try:
            api._inflight.add("u1")
            fut = cf.Future()
            fut.set_exception(RuntimeError("ffmpeg treo"))
            api._thumb_ready(fut, "u1")
            self.assertNotIn("u1", api._inflight)
            self.assertIn("u1", api._thumb_done)
            self.assertIsNone(api._thumb_done["u1"][0])
        finally:
            api._thumbs.shutdown()


class WhisperStop(unittest.TestCase):
    def test_dung_giua_mot_lo_thi_khong_chay_tiep_cac_file_chua_bat_dau(self):
        """Lỗi: _whisper_group nộp cả lô vào hàng đợi, Dừng chỉ có tác dụng sau khi cả lô chạy xong."""
        calls = []

        class Store(object):
            def put_result(self, *a, **k):
                calls.append("result")

            def put_error(self, *a, **k):
                calls.append("error")
        run = sr.SpeechRun(Store(), cfg={"exe": "x", "model": "y"}, vad_run=None, index=[], prompt=None)
        run.stop = True
        orig = sr.sp.whisper_run
        sr.sp.whisper_run = lambda *a, **k: calls.append("whisper") or ([], None)
        try:
            preps = {"k%d" % i: {"wav": "w%d" % i} for i in range(4)}
            by_key = {k: {"key": k, "uid": k, "name": k, "tc": ""} for k in preps}
            run._whisper_group(preps, by_key, {k: "sig" for k in preps}, "vi", 0, 4)
        finally:
            sr.sp.whisper_run = orig
        self.assertEqual(calls, [])                                        # đã Dừng: không chạy Whisper, không ghi kết quả/lỗi giả


class OrphanChildren(unittest.TestCase):
    def test_tien_trinh_con_chet_theo_khi_panel_thoat(self):
        """Lỗi: ffmpeg/Whisper/AI do panel chạy ra vẫn sống tiếp khi cửa sổ đóng (tiến trình mồ côi)."""
        import troly_env
        self.assertTrue(hasattr(troly_env, "kill_children_on_exit"))
        code = ("import sys,subprocess,time;sys.path.insert(0,%r);import troly_env;troly_env.kill_children_on_exit();"
                "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);print(p.pid,flush=True);time.sleep(1)"
                % os.path.join(HERE, "..", "app"))
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30).stdout.strip()
        pid = int(out.splitlines()[0])
        time.sleep(1.0)
        alive = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True).stdout
        self.assertNotIn(str(pid), alive.split("PID")[-1] if "PID" in alive else alive)

    def test_panel_goi_ham_don_tien_trinh_con_khi_khoi_dong(self):
        with open(os.path.join(HERE, "..", "app", "panel_troly_web.py"), encoding="utf-8") as f:
            self.assertIn("troly_env.kill_children_on_exit()", f.read())


if __name__ == "__main__":
    unittest.main()
