"""Kiểm thử troly_api.TrolyApi (phần chức năng của giao diện HTML, ADR-0010) với Media Pool giả. Không cần DaVinci,
không cần pywebview."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_troly as T                # noqa: E402
import troly_api as ta                # noqa: E402
import troly_core as tc               # noqa: E402

PATH = "Master/01_footage/01_SELECTED"


def make_pool():
    def mk(uid, hh, mm):
        return T.FItem(uid, T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:%02d:00" % (hh, mm),
                                    "Sat Oct 17 %02d:%02d:06 2026" % (hh, mm), 300, Type="Video + Audio"))
    sel = T.FFolder("01_SELECTED", [mk("a", 6, 30), mk("b", 6, 40), mk("c", 8, 10), mk("d", 8, 20), mk("e", 18, 0)])
    foot = T.FFolder("01_footage")
    foot.subs.append(sel)
    root = T.FFolder("Master")
    root.subs.append(foot)
    return T.FPool(root), sel


class Api(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pool, self.sel = make_pool()
        self.events = []
        self.api = ta.TrolyApi("2026.10.17.LV_Mau", self.tmp, emit=lambda k, d: self.events.append((k, d)),
                               resolve_factory=lambda: T.FResolve(T.FProject("2026.10.17.LV_Mau", self.pool)),
                               start_worker=False)
        self.w = self.api._worker
        self.w.connect()

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_jobs(self):
        while not self.w.jobs.empty():
            job, arg = self.w.jobs.get()
            getattr(self.w, "do_" + job)(arg)
        self.api._drain()

    def last(self, kind):
        return [d for k, d in self.events if k == kind][-1]

    def load(self):
        info = self.api.init()
        self.assertEqual(info["parsed"], {"date": "17/10/2026", "team": "LV", "name": "Mau"})
        self.run_jobs()
        self.assertEqual(self.last("bins")["pick"], PATH)
        self.api.load(PATH)
        self.run_jobs()
        return self.api.suggest("Tiệc nhà hàng")

    def test_state_after_load(self):
        st = self.load()
        self.assertEqual(st["n"], 5)
        self.assertEqual([s["count"] for s in st["stages"]], [2, 2, 1])
        self.assertEqual(st["stages"][0]["bin"], "01_Đón khách")
        self.assertEqual(st["gap"]["text"], "08:20 – 18:00")
        self.assertEqual(st["stages"][0]["bins"][0], {"name": "Decor", "key": "1", "color": ta.SUB_COLORS[0],
                                                      "uids": [], "count": 0})
        self.assertEqual(st["day0"], "17/10/2026")
        self.assertIn("state", [k for k, _ in self.events])

    def test_set_stage_text_and_rename_keeps_labels(self):
        self.load()
        self.api.label(["c"], 1, "Sân khấu")
        st = self.api.set_stage(0, {"end_txt": "06:35"})
        self.assertEqual((st["stages"][0]["count"], st["outside"]), (1, 1))
        self.assertIn("error", self.api.set_stage(0, {"end_txt": "25:99"}))
        st = self.api.set_stage(1, {"name": "Lễ", "bins": ["Sân khấu", "Khách", "Khác"]})
        self.assertEqual([b["name"] for b in st["stages"][1]["bins"]], ["Sân khấu", "Khách", "Khác"])
        self.assertEqual(st["stages"][1]["done"], 1)
        self.assertEqual(tc.label_of(self.api._plan, self.api._by_uid["c"])["stage"], "Lễ")
        st = self.api.set_stage(2, {"start": 17 * 60.0, "end": 19 * 60.0})
        self.assertEqual(st["stages"][2]["range"], "17:00 – 19:00")

    def test_label_apply_undo(self):
        self.load()
        self.api.label(["a"], 0, "Decor")
        self.assertIn("error", self.api.label(["b"], 0, "Không có"))
        st = self.api.label(["b"], 0, None)
        self.assertEqual(st["stages"][0]["done"], 1)
        pv = self.api.apply_preview()
        self.assertEqual(pv["total"], 5)
        self.assertEqual(pv["rows"][0], {"bin": "01_Đón khách", "n": 2, "color": st["stages"][0]["color"],
                                         "sub": [{"name": "Decor", "n": 1}]})
        self.assertEqual(len(self.sel.clips), 5)           # xem trước không ghi gì
        self.assertTrue(self.api.apply())
        self.run_jobs()
        self.assertEqual(self.sel.clips, [])
        st = self.last("state")
        self.assertEqual(st["moves"][0]["n"], 5)
        self.assertEqual(self.api._by_uid["a"].bin_path, PATH + "/01_Đón khách/Decor")
        self.assertTrue(self.api.undo())
        self.run_jobs()
        self.assertEqual(sorted(c.uid for c in self.sel.clips), ["a", "b", "c", "d", "e"])
        self.assertEqual(self.last("state")["moves"], [])
        self.assertFalse(self.api.undo())                   # hết nhật ký

    def test_view_lists_per_bin_match_counts_and_viewing_changes_nothing(self):
        st = self.load()                                      # Đón khách: a,b · Lễ nhà hàng: c,d · Chào bàn: e
        self.api.label(["a"], 0, "Decor")
        self.api.label(["b"], 0, "Khách")
        self.api.label(["c"], 1, "Sân khấu")
        st = self.api.state()
        s0 = st["stages"][0]
        by = {b["name"]: b for b in s0["bins"]}
        self.assertEqual(s0["uids"], ["a", "b"])
        self.assertEqual((by["Decor"]["uids"], by["Khách"]["uids"], by["Khác"]["uids"]), (["a"], ["b"], []))
        self.assertEqual(s0["none"], [])
        self.assertEqual(st["stages"][1]["none"], ["d"])       # d chưa có nhãn
        self.assertEqual(st["stages"][1]["uids"], ["c", "d"])
        # số cạnh mỗi bin con = số clip trong lưới của bin đó; chưa xếp + đã xếp = cả giai đoạn
        for s in st["stages"]:
            for b in s["bins"]:
                self.assertEqual(b["count"], len(b["uids"]))
            self.assertEqual(sum(b["count"] for b in s["bins"]) + len(s["none"]), s["count"])
            self.assertEqual(s["done"], s["count"] - len(s["none"]))
        # nhãn cũ của giai đoạn khác (đã chọn tay clip sang giai đoạn khác) không lọt vào bin con của giai đoạn mới
        self.api.move(["a"], 2, None)
        st = self.api.state()
        self.assertEqual(st["stages"][0]["uids"], ["b"])
        self.assertEqual([b["uids"] for b in st["stages"][2]["bins"]], [[], [], []])
        self.assertEqual(st["stages"][2]["none"], ["a", "e"])
        # XEM (gọi state nhiều lần, như bấm bin trong cây) không đổi nhãn, chọn tay hay kế hoạch
        before = (dict(self.api._plan["labels"]), dict(self.api._plan["manual"]), len(self.api._plan["moves"]))
        for _ in range(3):
            self.api.state()
        self.assertEqual(before, (dict(self.api._plan["labels"]), dict(self.api._plan["manual"]),
                                  len(self.api._plan["moves"])))

    def test_parse_name_without_team(self):
        self.api._project = "2026.10.25.TenKhongMa"
        self.assertEqual(self.api._parse_name(), {"date": "25/10/2026", "team": "", "name": "TenKhongMa"})

    def test_move_manual_stage_and_bin(self):
        self.load()                                            # Đón khách: a,b · Lễ nhà hàng: c,d · Chào bàn: e
        st = self.api.move(["a"], 2, None)                      # Shift+3: sang Chào bàn
        self.assertEqual(st["moved"], 1)
        self.assertEqual([s["count"] for s in st["stages"]], [1, 2, 2])
        self.assertEqual((st["n_manual"], [c["manual"] for c in st["clips"] if c["uid"] == "a"]), (1, [True]))
        st = self.api.move(["b", "c"], 2, "Khách")              # Shift+3 rồi 2 / thả vào bin con
        self.assertEqual(st["stages"][2]["count"], 4)
        self.assertEqual(st["stages"][2]["done"], 2)
        self.assertIn("error", self.api.move(["d"], 7, None))
        self.assertIn("error", self.api.move(["d"], 0, "Không có"))
        # kéo lại mốc giờ ở thẻ 1: chọn tay vẫn giữ
        st = self.api.set_stage(2, {"start_txt": "20:00", "end_txt": "21:00"})
        self.assertEqual(st["stages"][2]["count"], 3)          # a,b,c chọn tay; e (18:00) ra ngoài
        # đổi tên giai đoạn: chọn tay đi theo
        st = self.api.set_stage(2, {"name": "Chào bàn tối"})
        self.assertEqual(st["stages"][2]["count"], 3)
        pv = self.api.apply_preview()
        row = [r for r in pv["rows"] if r["bin"] == "03_Chào bàn tối"][0]
        self.assertEqual((row["n"], row["sub"]), (3, [{"name": "Khách", "n": 2}]))
        st = self.api.clear_manual()
        self.assertEqual(st["n_manual"], 0)
        self.assertEqual(st["stages"][2]["count"], 0)

    def test_add_bin_dung_chung_ham_kiem_ten_voi_doi_ten(self):
        """S2 (19/11/2026): "+ Bin mới" và đổi tên bin cùng MỘT hàm kiểm tra (tc.check_new_name), cùng bộ ký tự chặn, không chặn &."""
        self.load()
        names = lambda st: [b["name"] for b in st["stages"][0]["bins"]]
        for bad in ("Cô:dâu", "a/b", "a\b", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b", "chấm.", "ctl\x01"):
            r = self.api.add_bin(0, bad)
            self.assertIn("error", r, bad)
            r2 = self.api.rename_check("bin", 0, "Decor", bad) if "Decor" in names(self.api.state()) else None
            if r2 is not None:
                self.assertEqual(r["error"], r2["error"], bad)           # cùng thông báo
        self.assertNotIn("Flycam&Drone", names(self.api.state()))
        st = self.api.add_bin(0, "Flycam&Drone")
        self.assertNotIn("error", st)
        self.assertIn("Flycam&Drone", names(st))
        self.assertIn("error", self.api.add_bin(0, "flycam&DRONE"))      # trùng tên cùng cấp (không phân biệt hoa thường)
        import troly_core
        calls = []
        orig = troly_core.check_new_name
        troly_core.check_new_name = lambda *a, **k: calls.append(a) or orig(*a, **k)
        try:
            self.api.add_bin(0, "Một")
            b = next(x for x in names(self.api.state()) if x not in ("Khác", "Một"))
            self.api.rename_check("bin", 0, b, "Hai")
        finally:
            troly_core.check_new_name = orig
        self.assertEqual(len(calls), 2)
        self.api.close()

    def test_add_bin_offsets_template_persist(self):
        self.load()
        st = self.api.add_bin(0, "Flycam")
        self.assertEqual([b["name"] for b in st["stages"][0]["bins"]][-2:], ["Flycam", "Khác"])
        cam = st["cameras"][0]["cam"]
        st = self.api.set_offset(cam, "-600")                  # máy nhanh 10 phút
        self.assertEqual(next(c["off"] for c in st["cameras"] if c["cam"] == cam), -600.0)
        self.assertIn("error", self.api.set_offset(cam, "abc"))
        st = self.api.save_template("Mẫu của anh")
        self.assertIn("Mẫu của anh", st["templates"])
        self.api.close()
        api2 = ta.TrolyApi("2026.10.17.LV_Mau", self.tmp, start_worker=False,
                           resolve_factory=lambda: T.FResolve(T.FProject("2026.10.17.LV_Mau", self.pool)))
        try:
            self.assertEqual(api2._plan["template"], "Mẫu của anh")
            self.assertIn("Flycam", api2._plan["stages"][0]["bins"])
        finally:
            api2._thumbs.shutdown()


if __name__ == "__main__":
    unittest.main()
