"""Đổi tên bin qua TrolyApi + việc nền Media Pool giả (ADR-0015, phương án (b)): tạo bin mới, chuyển clip và bin con, chỉ xóa bin
cũ khi đã rỗng, nhãn không mất, phím 1-9 theo vị trí, Hoàn tác. Không cần DaVinci. Tên ví dụ LV_Ten."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_troly as T                # noqa: E402
import troly_api as ta                # noqa: E402

SRC = "Master/01_footage/01_SELECTED"


class RenamePool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

        def mk(uid, hh, mm):
            return T.FItem(uid, T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:%02d:00" % (hh, mm),
                                        "Sat Oct 17 %02d:%02d:06 2026" % (hh, mm), 300, Type="Video + Audio"))
        self.sel = T.FFolder("01_SELECTED", [mk("a", 8, 10), mk("b", 8, 20)])
        foot = T.FFolder("01_footage")
        foot.subs.append(self.sel)
        root = T.FFolder("Master")
        root.subs.append(foot)
        self.pool = T.FPool(root)
        self.name = "2026.10.17.LV_Ten"
        self.events = []
        self.api = ta.TrolyApi(self.name, self.tmp, emit=lambda k, d: self.events.append((k, d)),
                               resolve_factory=lambda: T.FResolve(T.FProject(self.name, self.pool)), start_worker=False)
        self.w = self.api._worker
        self.w.connect()
        self.api.init()
        self.run_jobs()
        self.api.load(SRC)
        self.run_jobs()
        self.api._plan["stages"] = []
        self.api.add_stage()
        self.api.set_stage(0, {"name": "Gia tiên", "start_txt": "08:00", "end_txt": "09:00", "bins": ["Decor", "Nghi lễ"]})
        self.api._recount()

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_jobs(self):
        while not self.w.jobs.empty():
            job, arg = self.w.jobs.get()
            try:
                getattr(self.w, "do_" + job)(arg)
            except Exception as e:                      # noqa: BLE001  giống TrolyWorker.run
                self.w.post("error", (job, str(e)))
        self.api._drain()

    def uid(self, n):
        return next(c.uid for c in self.api._clips if c.name == "DG%s.MP4" % n)

    def applied(self):
        """Xếp a vào Decor, b ở giai đoạn (không bin con) rồi áp dụng vào Media Pool."""
        self.api.label([self.uid("a")], 0, "Decor")
        self.assertTrue(self.api.apply())
        self.run_jobs()

    def folder(self, *parts):
        f = self.sel
        for n in parts:
            f = next((x for x in f.subs if x.GetName() == n), None)
            if f is None:
                return None
        return f

    def names(self, f=None):
        return sorted(x.GetName() for x in (f or self.sel).subs)

    def clip_names(self, f):
        return sorted(c.GetClipProperty("File Name") for c in f.clips)

    # ------------------------------------------------------------------
    def test_kiem_ten_truoc_khi_doi(self):
        self.assertIn("trống", self.api.rename_check("stage", 0, "", "  ")["error"])
        self.assertIn(":", self.api.rename_check("bin", 0, "Decor", "Lễ: a")["error"])
        self.assertIn("Đã có", self.api.rename_check("bin", 0, "Decor", "nghi lễ")["error"])
        self.assertIn("không đổi tên được", self.api.rename_check("bin", 0, "Khác", "X")["error"])
        self.assertIn("error", self.api.rename_check("stage", 9, "", "X"))
        self.assertTrue(self.api.rename_check("bin", 0, "Decor", "Trang trí")["ok"])
        self.assertTrue(self.api.rename_check("bin", 0, "Decor", "Decor")["same"])
        self.assertIn("error", self.api.rename("bin", 0, "Decor", "Nghi lễ"))                   # chặn cả lúc đổi thật
        self.assertEqual(self.api._stages[0]["bins"][:2], ["Decor", "Nghi lễ"])                 # không đổi gì

    def test_doi_ten_bin_con_trong_media_pool_nhan_va_phim_so(self):
        self.applied()
        self.assertEqual(self.names(self.folder("01_Gia tiên")), ["Decor"])
        r = self.api.rename("bin", 0, "Decor", "Trang trí")
        self.assertTrue(r["ok"])
        self.run_jobs()
        gt = self.folder("01_Gia tiên")
        self.assertEqual(self.names(gt), ["Trang trí"])                                         # bin cũ biến mất, bin mới còn
        self.assertEqual(self.clip_names(self.folder("01_Gia tiên", "Trang trí")), ["DGa.MP4"])  # clip được chuyển sang, không mất
        self.assertEqual(self.pool.deleted, ["Decor"])                                          # chỉ xóa đúng bin cũ đã rỗng
        st = self.api.state()
        self.assertEqual([b["name"] for b in st["stages"][0]["bins"][:2]], ["Trang trí", "Nghi lễ"])
        self.assertEqual(st["stages"][0]["bins"][0]["key"], "1")                                 # phím 1 vẫn là bin đầu
        self.assertEqual(next(c for c in st["clips"] if c["uid"] == self.uid("a"))["label"], "Trang trí")
        self.assertEqual(self.api._by_uid[self.uid("a")].bin_path, SRC + "/01_Gia tiên/Trang trí")
        self.assertEqual(self.last_status()[1], "ok")

    def test_doi_ten_giai_doan_chuyen_ca_clip_va_bin_con(self):
        self.applied()
        self.assertTrue(self.api.rename("stage", 0, "Gia tiên", "Lễ nhập gia")["ok"])
        self.run_jobs()
        self.assertEqual(self.names(), ["01_Lễ nhập gia"])
        new = self.folder("01_Lễ nhập gia")
        self.assertEqual(self.names(new), ["Decor"])                                            # bin con đi theo
        self.assertEqual(self.clip_names(self.folder("01_Lễ nhập gia", "Decor")), ["DGa.MP4"])
        self.assertEqual(self.clip_names(new), ["DGb.MP4"])                                     # clip ở bin giai đoạn
        self.assertEqual(self.pool.deleted, ["01_Gia tiên"])
        a = self.api._by_uid[self.uid("a")]
        self.assertEqual(a.bin_path, SRC + "/01_Lễ nhập gia/Decor")
        self.assertEqual(self.api.state()["stages"][0]["name"], "Lễ nhập gia")
        # áp dụng lại sau khi đổi tên không tạo bin trùng, không chuyển gì
        self.assertTrue(self.api.apply())
        self.run_jobs()
        self.assertEqual(self.names(), ["01_Lễ nhập gia"])

    def test_hoan_tac_doi_ten(self):
        self.applied()
        self.api.rename("bin", 0, "Decor", "Trang trí")
        self.run_jobs()
        self.assertEqual(self.api.state()["moves"][-1]["rename"], "Decor → Trang trí")
        self.assertTrue(self.api.undo())
        self.run_jobs()
        self.assertEqual(self.names(self.folder("01_Gia tiên")), ["Decor"])
        self.assertEqual(self.clip_names(self.folder("01_Gia tiên", "Decor")), ["DGa.MP4"])
        self.assertEqual(self.api._stages[0]["bins"][:2], ["Decor", "Nghi lễ"])
        self.assertEqual(self.api._plan["labels"][self.api._clips[0].rel]["bin"], "Decor")
        self.assertEqual(len(self.api._plan["moves"]), 1)                                       # còn lại lần áp dụng
        # hoàn tác lần áp dụng cũ vẫn chạy đúng (nhật ký đã đi theo tên)
        self.api.rename("bin", 0, "Decor", "Trang trí")
        self.run_jobs()
        self.assertTrue(self.api.undo())
        self.run_jobs()
        self.assertTrue(self.api.undo())
        self.run_jobs()
        self.assertEqual(self.sel.clips and sorted(c.GetClipProperty("File Name") for c in self.sel.clips), ["DGa.MP4", "DGb.MP4"])

    def test_chua_co_bin_trong_media_pool_thi_chi_doi_trong_panel(self):
        r = self.api.rename("bin", 0, "Decor", "Trang trí")
        self.assertTrue(r["ok"])
        self.run_jobs()
        self.assertEqual(self.names(), [])                                                       # không tạo bin gì trong Media Pool
        self.assertFalse(hasattr(self.pool, "deleted"))
        self.assertEqual(self.api._stages[0]["bins"][0], "Trang trí")
        self.assertIn("chưa có trong Media Pool", self.last_status()[0])

    def test_loi_chuyen_clip_khong_xoa_gi_va_bao_cach_xu_ly(self):
        self.applied()
        self.pool.fail_move = True
        self.api.rename("bin", 0, "Decor", "Trang trí")
        self.run_jobs()
        old = self.folder("01_Gia tiên", "Decor")
        self.assertIsNotNone(old)                                                                # bin cũ còn nguyên
        self.assertEqual(self.clip_names(old), ["DGa.MP4"])                                      # clip không mất
        self.assertFalse(hasattr(self.pool, "deleted"))
        text, kind = self.last_status()
        self.assertEqual(kind, "error")
        self.assertIn("Áp dụng vào Media Pool", text)
        self.assertFalse(self.api._busy)
        self.assertEqual(self.api._stages[0]["bins"][0], "Trang trí")                            # nhãn đi theo tên mới, không mồ côi

    def test_bin_cu_con_do_thi_giu_nguyen(self):
        """Bin cũ còn clip sau khi chuyển (DaVinci không chuyển hết) thì KHÔNG xóa."""
        self.applied()
        old = self.folder("01_Gia tiên", "Decor")
        orig = self.pool.MoveClips

        def partial(items, dst):                      # chỉ chuyển được một nửa: giả lập một clip kẹt lại
            return orig([], dst) if False else (old.clips.append(self.sel.clips[0]) or orig(items, dst))
        self.pool.MoveClips = partial
        self.api.rename("bin", 0, "Decor", "Trang trí")
        self.run_jobs()
        self.assertIsNotNone(self.folder("01_Gia tiên", "Decor"))
        self.assertFalse(hasattr(self.pool, "deleted"))

    def last_status(self):
        d = [d for k, d in self.events if k == "status"][-1]
        return d["text"], d["kind"]


if __name__ == "__main__":
    unittest.main()
