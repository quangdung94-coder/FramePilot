"""Đổi tên giai đoạn / bin con qua TrolyApi (ADR-0015): CHỈ đổi trong kế hoạch của panel; bin thật trong Media Pool chỉ tạo khi
Áp dụng, bin cũ đã Áp dụng thì còn lại rỗng và được nhắc, không tự xóa. Media Pool giả, không cần DaVinci. Tên ví dụ LV_Ten."""
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
NAME = "2026.10.17.LV_Ten"


class RenameApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

        def mk(uid, hh, mm):
            return T.FItem(uid, T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:%02d:00" % (hh, mm),
                                        "Sat Oct 17 %02d:%02d:06 2026" % (hh, mm), 300, Type="Video + Audio"))
        self.sel = T.FFolder("01_SELECTED", [mk("a", 8, 10), mk("b", 8, 20), mk("c", 8, 30)])
        foot = T.FFolder("01_footage")
        foot.subs.append(self.sel)
        root = T.FFolder("Master")
        root.subs.append(foot)
        self.pool = T.FPool(root)
        self.events = []
        self.api = self._api()
        self.w = self.api._worker
        self.w.connect()
        self.api.init()
        self.run_jobs()
        self.api.load(SRC)
        self.run_jobs()
        self.api._plan["stages"] = []
        self.api.add_stage()
        self.api.set_stage(0, {"name": "Gia tiên", "start_txt": "08:00", "end_txt": "09:00", "bins": ["Decor", "Nghi lễ", "Phỏng vấn"]})
        self.api._recount()

    def _api(self):
        return ta.TrolyApi(NAME, self.tmp, emit=lambda k, d: self.events.append((k, d)),
                           resolve_factory=lambda: T.FResolve(T.FProject(NAME, self.pool)), start_worker=False)

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_jobs(self):
        while not self.w.jobs.empty():
            job, arg = self.w.jobs.get()
            getattr(self.w, "do_" + job)(arg)
        self.api._drain()

    def uid(self, n):
        return next(c.uid for c in self.api._clips if c.name == "DG%s.MP4" % n)

    def label(self):
        self.api.label([self.uid("a"), self.uid("c")], 0, "Decor")
        self.api.label([self.uid("b")], 0, "Nghi lễ")

    def apply(self):
        self.assertTrue(self.api.apply())
        self.run_jobs()

    def sub_names(self, *path):
        f = self.sel
        for n in path:
            f = next(x for x in f.subs if x.GetName() == n)
        return sorted(x.GetName() for x in f.subs)

    def clip_label(self, n):
        return next(c for c in self.api.state()["clips"] if c["uid"] == self.uid(n))["label"]

    # ------------------------------------------------------------------
    def test_kiem_ten(self):
        c = self.api.rename_check
        self.assertIn("trống", c("stage", 0, "", "  ")["error"])
        for ch in ':/\\*?"<>|':
            self.assertIn(ch, c("bin", 0, "Decor", "A%sB" % ch)["error"])
        self.assertTrue(c("bin", 0, "Decor", "Duyên&Phát").get("ok"))                     # S2 19/11/2026: & KHÔNG bị chặn ở cả đổi tên lẫn + Bin mới
        self.assertIn("Đã có", c("bin", 0, "Decor", "nghi lễ")["error"])                   # trùng bin cùng cấp
        self.api.add_stage()
        self.api.set_stage(1, {"name": "Đón khách", "start_txt": "09:00", "end_txt": "10:00", "bins": ["Decor"]})
        self.assertIn("Đã có", c("stage", 1, "", "gia TIÊN")["error"])                     # trùng tên giai đoạn khác
        self.assertTrue(c("bin", 1, "Decor", "Nghi lễ")["ok"])                              # bin cùng tên ở GIAI ĐOẠN KHÁC thì được
        self.assertIn("không đổi tên được", c("bin", 0, "Khác", "X")["error"])
        self.assertIn("error", c("stage", 7, "", "X"))
        self.assertTrue(c("bin", 0, "Decor", "Trang trí")["ok"])
        self.assertTrue(c("bin", 0, "Decor", "Decor")["same"])
        before = list(self.api._stages[0]["bins"])
        for bad in ("", "a:b", "Nghi lễ"):
            self.assertIn("error", self.api.rename("bin", 0, "Decor", bad))
        self.assertEqual(self.api._stages[0]["bins"], before)                              # tên sai không đổi gì

    def test_doi_ten_bin_con_nhan_va_phim_so_khong_mat(self):
        self.label()
        r = self.api.rename("bin", 0, "Decor", "Trang trí")
        self.assertTrue(r["ok"])
        st = self.api.state()
        self.assertEqual([(b["name"], b["key"]) for b in st["stages"][0]["bins"][:3]], [("Trang trí", "1"), ("Nghi lễ", "2"), ("Phỏng vấn", "3")])
        self.assertEqual((self.clip_label("a"), self.clip_label("c"), self.clip_label("b")), ("Trang trí", "Trang trí", "Nghi lễ"))
        self.assertTrue(self.w.jobs.empty())                                               # không có việc nào gửi sang DaVinci
        # phím 1 vẫn gắn clip vào bin đầu (sau khi đổi tên là "Trang trí")
        self.api.label([self.uid("b")], 0, st["stages"][0]["bins"][0]["name"])
        self.assertEqual(self.clip_label("b"), "Trang trí")

    def test_doi_ten_giai_doan_nhan_va_chon_tay_khong_mat(self):
        self.label()
        self.api.move([self.uid("c")], 0, "Decor")
        self.assertTrue(self.api.rename("stage", 0, "Gia tiên", "Lễ nhập gia")["ok"])
        st = self.api.state()
        self.assertEqual(st["stages"][0]["name"], "Lễ nhập gia")
        self.assertEqual(st["stages"][0]["bin"], "01_Lễ nhập gia")
        self.assertEqual((self.clip_label("a"), self.clip_label("b")), ("Decor", "Nghi lễ"))
        self.assertTrue(all(m["stage"] == "Lễ nhập gia" for m in self.api._plan["manual"].values()))
        pv = self.api.apply_preview()
        self.assertEqual([r["bin"] for r in pv["rows"]], ["01_Lễ nhập gia"])

    def test_nhat_ky_chuyen_giu_nguyen_va_hoan_tac_van_chay(self):
        self.label()
        self.apply()
        moves0 = [dict(m) for m in self.api._plan["moves"]]
        logs0 = [list(x) for x in self.api._plan["moves"][-1]["log"]]
        self.assertTrue(self.api.rename("bin", 0, "Decor", "Trang trí")["ok"])
        self.assertEqual(self.api._plan["moves"][-1]["log"], logs0)                        # nhật ký ghi bin thật, không bị sửa
        self.assertEqual(len(self.api._plan["moves"]), len(moves0))
        self.assertTrue(self.api.undo())                                                   # Hoàn tác lần Áp dụng cũ vẫn tìm đúng bin
        self.run_jobs()
        self.assertEqual(sorted(c.GetClipProperty("File Name") for c in self.sel.clips), ["DGa.MP4", "DGb.MP4", "DGc.MP4"])

    def test_ap_dung_sau_khi_doi_ten_nhac_bin_cu_con_lai_rong(self):
        self.label()
        self.assertEqual(self.api.apply_preview()["emptied"], [])                          # chưa Áp dụng: không có bin cũ
        self.apply()
        self.assertEqual(self.api.apply_preview()["emptied"], [])                          # Áp dụng rồi nhưng chưa đổi tên
        self.api.rename("bin", 0, "Decor", "Trang trí")
        pv = self.api.apply_preview()
        self.assertEqual(pv["emptied"], ["01_Gia tiên/Decor"])                             # a, c đều chuyển đi: bin cũ sẽ rỗng
        self.assertEqual(pv["rows"][0]["sub"], [{"name": "Nghi lễ", "n": 1}, {"name": "Trang trí", "n": 2}])
        self.apply()                                                                       # bin mới tạo, clip chuyển sang
        self.assertEqual(self.sub_names("01_Gia tiên"), ["Decor", "Nghi lễ", "Trang trí"])
        self.assertEqual(self.sub_names("01_Gia tiên", "Decor"), [])                       # bin cũ còn lại RỖNG, KHÔNG bị xóa
        self.assertFalse(hasattr(self.pool, "deleted"))
        self.assertEqual(self.api._by_uid[self.uid("a")].bin_path, SRC + "/01_Gia tiên/Trang trí")

    def test_bin_cu_con_clip_khac_thi_khong_bao_rong(self):
        self.label()
        self.apply()
        self.api.label([self.uid("c")], 0, "Phỏng vấn")                                    # c đổi bin, a vẫn ở Decor
        self.assertEqual(self.api.apply_preview()["emptied"], [])

    def test_mo_lai_panel_ten_moi_con(self):
        self.label()
        self.api.rename("bin", 0, "Nghi lễ", "Lễ chính")
        self.api.rename("stage", 0, "Gia tiên", "Lễ nhập gia")
        api2 = self._api()
        try:
            self.assertEqual(api2._plan["stages"][0]["name"], "Lễ nhập gia")
            self.assertIn("Lễ chính", api2._plan["stages"][0]["bins"])
            self.assertEqual(sorted(v["stage"] for v in api2._plan["labels"].values()), ["Lễ nhập gia"] * 3)
            self.assertTrue(os.path.isfile(os.path.join(self.tmp, "troly", "projects", NAME + ".json.bak")))      # bản .bak trước lần lưu
        finally:
            api2._thumbs.shutdown()


if __name__ == "__main__":
    unittest.main()
