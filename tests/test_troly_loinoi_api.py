"""Bản đồ lời nói qua TrolyApi thật với Media Pool giả: bộ lọc, câu tiêu biểu, khung In/Out, đặt tay lưu vào kế hoạch.
Không cần DaVinci, không cần Whisper (kho được nạp sẵn dữ liệu giả)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_troly as T                # noqa: E402
import troly_api as ta                # noqa: E402


def line(t0, t1, text, keys=(), why=()):
    return {"t0": t0, "t1": t1, "text": text, "keys": list(keys), "why": list(why)}


def res(lines, speech, dur):
    return {"dur": dur, "gain_db": 0.0, "speech": [list(s) for s in speech], "lines": lines}


class TestApiLoiNoi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.kho = tempfile.mkdtemp()

        def mk(uid, hh, mm, marks=None):
            p = T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:%02d:00" % (hh, mm), "Sat Oct 17 %02d:%02d:06 2026" % (hh, mm), 300)
            p.update({"Type": "Video + Audio", "Start TC": "%02d:%02d:00:00" % (hh, mm)})
            return T.FItem(uid, p, marks=marks)
        sel = T.FFolder("01_SELECTED", [mk("a", 8, 10), mk("b", 8, 20), mk("c", 8, 30), mk("d", 8, 40, {"video": {"in": 100, "out": 200}})])
        foot = T.FFolder("01_footage")
        foot.subs.append(sel)
        root = T.FFolder("Master")
        root.subs.append(foot)
        self.pool = T.FPool(root)
        self.name = "2026.10.17.LV_Ten"
        self.api = self._api()
        self.api._worker.connect()
        self.api.init()
        self._jobs()
        self.api.load("Master/01_footage/01_SELECTED")
        self._jobs()
        self.assertTrue(self.api.speech_set_dir(self.kho, "vi").get("ok"))
        self.st = self.api._speech_store()
        self.keys = dict(zip("abcd", [c.rel for c in self.api._clips]))
        # a: câu có cụm key ở giây 10-14 và 20-24; b: có tiếng, không key; c: im lặng; d: có key và đã có In/Out trong DaVinci
        self.st.put_result(self.keys["a"], "ua", "a", (1, 1.0), "08:10:00:00", res(
            [line(2, 4, "dạ vâng"), line(10, 14, "nhà trai xin phép", ["nhà trai", "xin phép"]), line(20, 24, "mời ba mẹ", ["ba mẹ"])],
            ((2, 4), (10, 14), (20, 24)), 60.0), "vi")
        self.st.put_result(self.keys["b"], "ub", "b", (1, 1.0), "08:20:00:00",
                           res([line(5, 30, "mọi người nhìn qua đây giúp em")], ((5, 30),), 40.0), "vi")
        self.st.put_result(self.keys["c"], "uc", "c", (1, 1.0), "08:30:00:00", res([], (), 20.0), "vi")
        self.st.put_result(self.keys["d"], "ud", "d", (1, 1.0), "08:40:00:00",
                           res([line(1, 3, "xin phép", ["xin phép"])], ((1, 3),), 30.0), "vi")

    def _api(self):
        return ta.TrolyApi(self.name, self.tmp, resolve_factory=lambda: T.FResolve(T.FProject(self.name, self.pool)),
                           start_worker=False)

    def _jobs(self):
        w = self.api._worker
        while not w.jobs.empty():
            job, arg = w.jobs.get()
            getattr(w, "do_" + job)(arg)
        self.api._drain()

    def tearDown(self):
        self.api._thumbs.shutdown()
        self.st.close()
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.kho, ignore_errors=True)

    def rows(self, **kw):
        d = self.api.speech_clips(**kw)
        return {r["name"]: r for r in d["rows"]}, d

    def names(self, **kw):
        return {r["name"] for r in self.api.speech_clips(**kw)["rows"]}

    def test_dem_va_bo_loc(self):
        rows, d = self.rows()
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(d["all"]), 4)                                   # "Hiện X / Y": Y = mọi clip đã có dòng trong kho
        self.assertEqual(self.names(only_keys=True), {"DGa.MP4", "DGd.MP4"})
        self.assertEqual(self.names(min_speech=20), {"DGb.MP4"})            # tiếng nói từ 20 giây
        self.assertEqual(self.names(text="XIN PHÉP"), {"DGa.MP4", "DGd.MP4"})
        r = self.api.speech_clips(text="khong co chu nay")
        self.assertEqual((len(r["rows"]), len(r["all"])), (0, 4))            # tổng không đổi theo lọc

    def test_cau_tieu_bieu_cot_key_va_clip_im_lang(self):
        rows, _ = self.rows()
        self.assertEqual((rows["DGa.MP4"]["headline"], rows["DGa.MP4"]["n_keys"]), ("nhà trai xin phép", 3))
        self.assertEqual(rows["DGb.MP4"]["headline"], "mọi người nhìn qua đây giúp em")      # không key: câu dài nhất
        self.assertTrue(rows["DGc.MP4"]["silent"])
        self.assertEqual(rows["DGc.MP4"]["segs"], [])

    def test_mau_doan_noi(self):
        rows, _ = self.rows()
        self.assertEqual([s[2] for s in rows["DGa.MP4"]["segs"]], ["sp", "key", "key"])
        self.assertEqual([s[2] for s in rows["DGb.MP4"]["segs"]], ["sp"])

    def test_khung_goi_y_tu_cau_key_dau_toi_cuoi_dem_1_giay(self):
        rows, _ = self.rows()
        sp = rows["DGa.MP4"]["span"]
        self.assertEqual((sp["in_s"], sp["out_s"], sp["src"]), (9.0, 25.0, "text"))          # 10-1 .. 24+1
        self.assertEqual((sp["tc_in"], sp["tc_out"]), ("08:10:09:00", "08:10:25:00"))        # cộng timecode bắt đầu
        self.assertIsNone(rows["DGb.MP4"]["span"])                                          # không câu key: không gợi ý

    def test_in_out_davinci_thang_goi_y_va_dat_tay_thang_ca_hai(self):
        rows, _ = self.rows()
        sp = rows["DGd.MP4"]["span"]
        self.assertEqual((sp["src"], sp["in_s"], sp["out_s"]), ("davinci", 2.0, 4.0))        # 100/50, 200/50
        uid = rows["DGd.MP4"]["uid"]
        self.assertTrue(self.api.speech_set_inout(uid, 7.5, 3.0).get("ok"))                 # đảo đầu cuối vẫn lưu đúng thứ tự
        sp = self.rows()[0]["DGd.MP4"]["span"]
        self.assertEqual((sp["src"], sp["in_s"], sp["out_s"]), ("manual", 3.0, 7.5))
        api2 = self._api()                                                                  # mở lại panel: kế hoạch còn
        try:
            self.assertEqual(api2._plan["inout"][self.keys["d"]], [3.0, 7.5])
        finally:
            api2._thumbs.shutdown()
        self.api.speech_set_inout(uid, None, None)                                          # xóa tay: quay về In/Out DaVinci
        self.assertEqual(self.rows()[0]["DGd.MP4"]["span"]["src"], "davinci")

    def test_chi_tiet_clip_co_chu_timecode_va_sao(self):
        rows, _ = self.rows()
        uid = rows["DGa.MP4"]["uid"]
        d = self.api.speech_detail(uid)
        self.assertEqual([l["text"] for l in d["lines"]], ["dạ vâng", "nhà trai xin phép", "mời ba mẹ"])
        self.assertEqual(d["tc"], "08:10:00:00")
        self.assertFalse(d["star"])
        self.api.toggle_star([uid])
        self.assertTrue(self.api.speech_detail(uid)["star"])
        self.assertTrue(self.rows()[0]["DGa.MP4"]["star"])

    def test_chon_ngon_ngu_tay_tung_clip(self):
        rows, _ = self.rows()
        self.api.speech_set_lang(self.keys["b"], "en")
        self.assertEqual(self.rows()[0]["DGb.MP4"]["lang"], "en")
        self.assertEqual(self.api.speech_detail(rows["DGb.MP4"]["uid"])["lang"], "en")

    def test_so_lieu_ca_project(self):
        c = self.rows()[1]["summary"]
        self.assertEqual((c["total"], c["done"], c["silent"], c["err"]), (4, 3, 1, 0))

    def test_chua_chon_kho_thi_khong_loi(self):
        api = ta.TrolyApi(self.name + "x", tempfile.mkdtemp(), start_worker=False)
        try:
            self.assertEqual(api.speech_clips()["rows"], [])
            self.assertIn("error", api.speech_start())
        finally:
            api._thumbs.shutdown()


if __name__ == "__main__":
    unittest.main()
