"""Kiểm thử nhiều camera, trang 1 (ADR-0031): nhận máy, tên máy, máy chuẩn, đổi máy chuẩn, độ lệch đồng hồ, kiểm tra lệch (cảnh báo > 3 giờ,
chặn > 12 giờ), lưu theo project; project 1 máy chạy y như cũ. Dùng Media Pool giả, không cần DaVinci."""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import test_troly as T                # noqa: E402
import troly_api as ta                # noqa: E402
import troly_cams as cm               # noqa: E402
import troly_core as tc               # noqa: E402

WEB = os.path.join(HERE, "..", "app", "troly_web")
PATH = "Master/01_footage/01_SELECTED"
NAME = "2026.10.17.LV_Mau"


class PureCams(unittest.TestCase):
    def test_meta_doc_model_serial_hang(self):
        self.assertEqual(cm.meta({"Camera Type": "Sony ILCE-7M4", "Camera Serial #": "2205", "Camera Manufacturer": "Sony"}),
                         ("Sony", "Sony ILCE-7M4", "2205"))
        self.assertEqual(cm.meta({}), ("", "", ""))
        self.assertEqual(cm.meta({"Camera Type": "  ", "Camera ID": "X1"}), ("", "", "X1"))

    def test_ensure_groups_theo_so_file_toi_da_4_may(self):
        cfg = cm.new_cfg()
        gs = [{"key": k, "n": n} for k, n in (("a", 10), ("b", 50), ("c", 30), ("d", 5), ("e", 1))]
        self.assertTrue(cm.ensure_groups(cfg, gs))
        self.assertEqual([cfg["map"][k] for k in "bcad"], ["A", "B", "C", "D"])
        self.assertEqual(cfg["map"]["e"], "")                  # nhóm thứ 5: để người dựng gán tay, không im lặng gán bừa
        self.assertFalse(cm.ensure_groups(cfg, gs))            # chạy lại không đổi gì

    def test_check_name(self):
        cfg = cm.new_cfg()
        self.assertEqual(cm.check_name(cfg, "A", "  Máy   chính ")[1], "Máy chính")
        self.assertFalse(cm.check_name(cfg, "A", "")[0])
        self.assertFalse(cm.check_name(cfg, "A", "   ")[0])
        self.assertFalse(cm.check_name(cfg, "A", "máy b")[0])  # trùng "Máy B", không phân biệt hoa thường
        self.assertTrue(cm.check_name(cfg, "A", "máy a")[0])   # đặt lại đúng tên của chính nó thì được
        self.assertFalse(cm.check_name(cfg, "A", "x" * 21)[0])
        self.assertFalse(cm.check_name(cfg, "Z", "ok")[0])

    def test_parse_offset_canh_bao_va_chan(self):
        self.assertEqual(cm.parse_offset("+01:12:14"), (True, 4334.0, ""))
        ok, v, w = cm.parse_offset("-00:02:14")
        self.assertEqual((ok, v, w), (True, -134.0, ""))
        ok, v, w = cm.parse_offset("03:00:01")                 # vừa quá 3 giờ: cảnh báo, vẫn cho áp
        self.assertTrue(ok)
        self.assertIn("3 giờ", w)
        ok, v, w = cm.parse_offset("03:00:00")                 # đúng 3 giờ: chưa cảnh báo
        self.assertEqual((ok, w), (True, ""))
        ok, msg, _ = cm.parse_offset("+12:00:01")              # quá 12 giờ: chặn
        self.assertFalse(ok)
        self.assertIn("12 giờ", msg)
        self.assertTrue(cm.parse_offset("+12:00:00")[0])
        for bad in ("", "abc", "1:2", "+01:61:00", "+01:00:75"):
            self.assertFalse(cm.parse_offset(bad)[0], bad)

    def test_fmt_offset_va_vong_tron(self):
        for v in (0.0, 4334.0, -134.0, 43200.0):
            self.assertEqual(cm.parse_offset(cm.fmt_offset(v))[1], v)

    def test_doi_may_chuan_tinh_lai_do_lech(self):
        # giờ chung = giờ A. B đã chỉnh +134, C đã chỉnh -4334, D chưa chỉnh.
        cfg = cm.new_cfg()
        cfg["shift"] = {"B": 134.0, "C": -4334.0}
        cm.set_ref(cfg, "C")
        # giờ chung mới = giờ C: A lệch +4334 so với C, B lệch 134 + 4334 = 4468; C là máy chuẩn không có mục; D vẫn chưa chỉnh.
        self.assertEqual(cfg["shift"], {"A": 4334.0, "B": 4468.0})
        self.assertEqual(cfg["ref"], "C")
        cm.set_ref(cfg, "A")                                   # đổi ngược lại về như cũ
        self.assertEqual(cfg["shift"], {"B": 134.0, "C": -4334.0})

    def test_doi_may_chuan_sang_may_chua_chinh_giu_nguyen_may_khac(self):
        cfg = cm.new_cfg()
        cfg["shift"] = {"B": 100.0}
        cm.set_ref(cfg, "D")                                   # D chưa chỉnh: coi như giờ D đã là giờ chung
        self.assertEqual(cfg["shift"], {"B": 100.0})
        self.assertEqual(cfg["ref"], "D")

    def test_offset_from_moment_va_chong_nhau(self):
        # cùng một khoảnh khắc: máy chuẩn đọc 09:48:20, máy kia đọc 08:36:06 -> cộng 01:12:14 vào máy kia
        v = cm.offset_from_moment(9 * 3600 + 48 * 60 + 20 - 30, 30, 8 * 3600 + 36 * 60 + 6 - 25, 25)
        self.assertEqual(cm.fmt_offset(v), "+01:12:14")
        self.assertGreater(cm.overlap_after(100, 60, 50, 60, 20), 0)
        self.assertLessEqual(cm.overlap_after(100, 60, 20, 60, 0), 0)

    def test_has_overlap(self):
        self.assertFalse(cm.has_overlap([(0, 10), (10, 20), (30, 40)]))
        self.assertFalse(cm.has_overlap([(0, 10), (9, 20)]))   # chồng 1 giây: trong dung sai
        self.assertTrue(cm.has_overlap([(0, 10), (5, 20)]))

    def test_clean_cfg_hong_khong_nem_loi(self):
        for bad in (None, 5, "x", {"map": 3, "names": [], "shift": {"B": "x", "Z": 1, "C": 99999999}, "ref": "Q"}):
            c = cm.clean_cfg(bad)
            self.assertEqual(c["ref"], "A")
            self.assertEqual(c["shift"], {})
            self.assertEqual(c["names"]["B"], "Máy B")


def pool(ncams):
    items = []
    specs = [("DG%d.MP4", "Sony ILME-FX3", "4102", 0, 7), ("C%d.MP4", "Sony ILCE-7SM3", "7718", -134, 7),
             ("A00_%d.MP4", "Sony ILCE-7M4", "2205", -4334, 7)]
    for ci, (pat, model, sn, err, h0) in enumerate(specs[:ncams]):
        for i in range(12):
            t = h0 * 3600 + i * 600 + err + 300
            created = "Sat Oct 17 2026 %02d:%02d:%02d" % (t // 3600, t % 3600 // 60, t % 60)
            e = t + 6
            modified = "Sat Oct 17 %02d:%02d:%02d 2026" % (e // 3600, e % 3600 // 60, e % 60)
            p = T.props(pat % (100 * ci + i), created, modified, 300, Type="Video + Audio", **{"Camera Type": model, "Camera Serial #": sn})
            items.append(T.FItem("c%d_%d" % (ci, i), p))
    sel = T.FFolder("01_SELECTED", items)
    foot = T.FFolder("01_footage")
    foot.subs.append(sel)
    root = T.FFolder("Master")
    root.subs.append(foot)
    return T.FPool(root)


class ApiCams(unittest.TestCase):
    def make(self, ncams, tmp=None):
        self.tmp = tmp or self.tmp
        pl = pool(ncams)
        api = ta.TrolyApi(NAME, self.tmp, resolve_factory=lambda: T.FResolve(T.FProject(NAME, pl)), start_worker=False)
        api._worker.connect()
        api.init()
        self.run_jobs(api)
        api.load(PATH)
        self.run_jobs(api)
        return api

    def run_jobs(self, api):
        w = api._worker
        while not w.jobs.empty():
            job, arg = w.jobs.get()
            getattr(w, "do_" + job)(arg)
        api._drain()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.apis = []

    def tearDown(self):
        for a in self.apis:
            a._closed = True                                   # chặn _pump_thumbs nạp lại hàng đợi khi hủy thumbnail
            a._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def api(self, n):
        a = self.make(n)
        self.apis.append(a)
        return a

    def test_nhan_3_may_tu_metadata(self):
        st = self.api(3).state()
        c = st["cams"]
        self.assertTrue(c["multi"])
        self.assertEqual([x["letter"] for x in c["cards"]], ["A", "B", "C"])
        self.assertEqual({x["model"] for x in c["cards"]}, {"Sony ILME-FX3", "Sony ILCE-7SM3", "Sony ILCE-7M4"})
        self.assertEqual(c["ref"], "A")
        self.assertEqual(c["ambiguous"], [])
        self.assertTrue(all(x["cam_l"] in "ABC" and x["raw_s"] is not None for x in st["clips"]))
        self.assertEqual({x["n"] for x in c["cards"]}, {12})

    def test_project_1_may_chay_y_nhu_cu(self):
        a = self.api(1)
        st = a.state()
        self.assertFalse(st["cams"]["multi"])
        self.assertEqual(len(st["cams"]["cards"]), 1)
        self.assertEqual(a._plan["offsets"], {})               # không chạm gì vào độ lệch
        self.assertNotIn("managed", a._plan.get("cams", {}))
        self.assertEqual([c["m0"] for c in st["clips"]], sorted(c["m0"] for c in st["clips"]))
        self.assertEqual(st["cameras"][0]["off"], 0)           # lệch giờ cũ theo khóa vẫn dùng được
        st = a.set_offset(st["cameras"][0]["cam"], "-600")
        self.assertEqual(st["cameras"][0]["off"], -600.0)

    def test_doi_ten_khong_trong_khong_trung(self):
        a = self.api(3)
        self.assertIn("error", a.cams_rename("A", ""))
        self.assertIn("error", a.cams_rename("A", "máy b"))
        st = a.cams_rename("A", "Sony chính")
        self.assertEqual(st["cams"]["names"]["A"], "Sony chính")
        self.assertEqual(next(c for c in st["cams"]["cards"] if c["letter"] == "A")["name"], "Sony chính")

    @staticmethod
    def letter_of(st, model):
        return next(c["letter"] for c in st["cams"]["cards"] if c["model"] == model)

    def _pair(self, a, letter):
        st = a.state()
        ref = st["cams"]["ref"]
        r = next(c for c in st["clips"] if c["cam_l"] == ref and c["uid"].endswith("_6"))
        x = next(c for c in st["clips"] if c["cam_l"] == letter and c["uid"].endswith("_6"))
        return r, x

    def test_apply_moment_dich_clip_va_luu_theo_project(self):
        a = self.api(3)
        st0 = a.cams_set_ref(self.letter_of(a.state(), "Sony ILME-FX3"))        # máy chuẩn = FX3 (xếp chữ theo số file, hòa thì theo khóa)
        L = self.letter_of(st0, "Sony ILCE-7M4")
        r, x = self._pair(a, L)
        before = x["m0"]
        st = a.cams_apply_moment(L, r["uid"], 3, x["uid"], 3)
        self.assertNotIn("error", st)
        self.assertEqual(st["cam_msg"]["kind"], "ok")
        after = next(c for c in st["clips"] if c["uid"] == x["uid"])["m0"]
        self.assertAlmostEqual(after - before, 4334 / 60.0, places=3)
        card = next(c for c in st["cams"]["cards"] if c["letter"] == L)
        self.assertTrue(card["set"])
        self.assertEqual(card["shift_txt"], "+01:12:14")
        self.assertIn(L, st["cams"]["moment"])
        a._save_now()
        a2 = self.make(3)                                      # mở lại panel: độ lệch còn nguyên
        self.apis.append(a2)
        st2 = a2.state()
        self.assertEqual(next(c for c in st2["clips"] if c["uid"] == x["uid"])["m0"], after)
        self.assertEqual(next(c for c in st2["cams"]["cards"] if c["letter"] == L)["shift_txt"], "+01:12:14")

    def test_ap_do_lech_go_tay_canh_bao_tren_3_gio_chan_tren_12_gio(self):
        a = self.api(3)
        st = a.cams_apply("B", "+04:00:00")
        self.assertEqual(st["cam_msg"]["kind"], "warn")
        self.assertIn("3 giờ", st["cam_msg"]["text"])
        self.assertEqual(next(c for c in st["cams"]["cards"] if c["letter"] == "B")["shift"], 14400.0)
        r = a.cams_apply("B", "+13:00:00")
        self.assertIn("error", r)
        self.assertEqual(a.state()["cams"]["cards"][1]["shift"], 14400.0)      # bị chặn thì không đổi gì
        self.assertIn("error", a.cams_apply("A", "+00:01:00"))                  # máy chuẩn không chỉnh

    def test_ve_0_va_dat_lai(self):
        a = self.api(3)
        a.cams_apply("B", "+00:02:00")
        a.cams_apply("C", "-00:05:00")
        st = a.cams_reset("B")
        self.assertFalse(next(c for c in st["cams"]["cards"] if c["letter"] == "B")["set"])
        self.assertTrue(next(c for c in st["cams"]["cards"] if c["letter"] == "C")["set"])
        st = a.cams_reset(None)
        self.assertTrue(all(not c["set"] for c in st["cams"]["cards"] if not c["is_ref"]))
        self.assertEqual(a._plan["offsets"], {})

    def test_doi_may_chuan_tinh_lai_va_clip_khop_gio_moi(self):
        a = self.api(3)
        a.cams_apply("B", "+00:02:14")
        st = a.cams_set_ref("B")
        self.assertEqual(st["cams"]["ref"], "B")
        a_card = next(c for c in st["cams"]["cards"] if c["letter"] == "A")
        self.assertEqual(a_card["shift_txt"], "-00:02:14")                     # A lệch -134 so với giờ B
        self.assertFalse(next(c for c in st["cams"]["cards"] if c["letter"] == "B")["set"])
        self.assertIn("error", a.cams_set_ref("D"))

    def test_gan_tay_nhom_may_va_gop(self):
        a = self.api(3)
        st = a.state()
        key = st["cams"]["groups"][2]["key"]
        st = a.cams_assign(key, "")
        self.assertEqual(st["cams"]["unassigned"], [key])
        self.assertTrue(st["cams"]["multi"])
        st = a.cams_assign(key, "A")                                           # gộp vào máy A
        self.assertEqual(len(st["cams"]["cards"]), 2)
        self.assertEqual(next(c for c in st["cams"]["cards"] if c["letter"] == "A")["n"], 24)
        self.assertIn("error", a.cams_assign("khong-co", "A"))

    def test_khong_ghi_vao_davinci(self):
        a = self.api(3)
        a.cams_apply("B", "+00:02:00")
        a.cams_set_ref("B")
        self.assertFalse(any(k in ("apply", "move", "inout") for k, _ in list(a._worker.jobs.queue)))
        self.assertTrue(a._worker.jobs.empty())


class WebFiles(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(WEB, "index.html"), "r", encoding="utf-8") as f:
            self.html = f.read()
        with open(os.path.join(WEB, "cam.js"), "r", encoding="utf-8") as f:
            self.js = f.read()
        with open(os.path.join(WEB, "app.js"), "r", encoding="utf-8") as f:
            self.app = f.read()

    def test_trang_1_co_cac_khoi_theo_demo(self):
        for ident in ("camCards", "clockCol", "clockMulti", "syncBox", "resetAll", "camSec"):
            self.assertIn('id="%s"' % ident, self.html)
        self.assertIn('href="cam.css"', self.html)
        self.assertIn('src="cam.js"', self.html)
        self.assertTrue(os.path.isfile(os.path.join(WEB, "cam.css")))

    def test_app_goi_ham_nhieu_camera(self):
        self.assertIn("renderCams()", self.app)
        self.assertIn("camRowsHtml()", self.app)
        self.assertIn("camChipsOfStage(", self.app)

    def test_chi_goi_ham_cua_trang_1_khong_ghi_davinci(self):
        for name in ("cams_rename", "cams_set_ref", "cams_apply_moment", "cams_apply", "cams_moment", "cams_reset", "cams_assign"):
            self.assertIn("api()." + name, self.js)
        for bad in ("api().apply(", "api().move(", "api().inout_write"):
            self.assertNotIn(bad, self.js)


if __name__ == "__main__":
    unittest.main()
