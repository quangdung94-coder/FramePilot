"""Bước 3 làm lại (ADR-0024): gợi ý In/Out cho clip sao (mức 1 quy tắc bin, mức 2 theo lời nói), nhận gợi ý (A), đặt tay thắng,
ghi nhận nhận nguyên / chỉnh. Dữ liệu giả, tên ví dụ LV_Ten. Không DaVinci, không Whisper."""
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import test_troly as T                # noqa: E402
import test_troly_loinoi_api as LA    # noqa: E402
import troly_api as ta                # noqa: E402
import troly_core as tc               # noqa: E402


def L(a, b):
    return {"t0": a, "t1": b}


class Core(unittest.TestCase):
    def test_muc_2_dau_cau_dau_cuoi_cau_cuoi_cong_dem(self):
        self.assertEqual(tc.speech_span([L(10, 14), L(20, 24), L(40, 44)], 60.0, 0.3), (9.7, 44.3))
        self.assertEqual(tc.speech_span([L(0.1, 3)], 60.0, 0.3), (0.0, 3.3))                    # đệm không âm
        self.assertEqual(tc.speech_span([L(55, 59.9)], 60.0, 0.3), (54.7, 60.0))                # đệm không vượt độ dài clip
        self.assertEqual(tc.speech_span([L(5, 8), L(30, 31)], 60.0, 0.0), (5.0, 31.0))          # đệm 0 chỉnh được
        self.assertEqual(tc.speech_span([L(20, 24), L(10, 14)], 60.0, 0.3), (9.7, 24.3))        # không cần xếp sẵn

    def test_muc_2_khong_co_chu_hoac_cau_hong_thi_none(self):
        self.assertIsNone(tc.speech_span([], 60.0))
        self.assertIsNone(tc.speech_span(None, 60.0))
        self.assertIsNone(tc.speech_span([L(5, 5), {"t0": "x", "t1": 3}, {}], 60.0))
        self.assertIsNone(tc.speech_span([L(5, 5.1)], 60.0, 0.0))                              # ngắn hơn 0,5 s: coi như không có

    def test_dem_chinh_duoc_va_gioi_han(self):
        plan = tc.new_plan("2026.10.17.LV_Ten")
        self.assertEqual(tc.sug_pad(plan), 0.3)
        plan["inout_sug_cfg"] = {"pad": 1.0}
        self.assertEqual(tc.sug_pad(plan), 1.0)
        for bad in (-1, 99, "x", None):
            plan["inout_sug_cfg"] = {"pad": bad}
            self.assertEqual(tc.sug_pad(plan), 0.3)

    def test_ghi_nhan_nhan_nguyen_hay_chinh(self):
        plan = tc.new_plan("2026.10.17.LV_Ten")
        c = tc.Clip(uid="u", name="u", dur=60.0, fps=50.0, frames=3000, rel="01_footage/u.MP4")
        tc.sug_note(plan, c, "Decor", (1.0, 4.0, "rule"), 1.0, 4.0, "accept")
        self.assertEqual(tc.sug_counts(plan)["accepted"], 1)
        tc.sug_note(plan, c, "Decor", (1.0, 4.0, "rule"), 1.5, 4.0, "edit")                     # kéo sau khi nhận -> đã chỉnh
        cnt = tc.sug_counts(plan)
        self.assertEqual((cnt["accepted"], cnt["adjusted"]), (0, 1))                           # mỗi clip một trạng thái, không đếm đôi
        tc.sug_note(plan, c, "Decor", (1.0, 4.0, "rule"), 1.0, 4.0, "edit")                     # kéo về đúng gợi ý = nhận nguyên
        self.assertEqual(tc.sug_counts(plan)["accepted"], 1)
        tc.sug_forget(plan, c)
        self.assertEqual(tc.sug_counts(plan), {"accepted": 0, "adjusted": 0, "by_src": {}})
        tc.sug_note(plan, c, "Decor", None, 1, 2, "edit")                                       # không có gợi ý: không ghi gì
        self.assertNotIn("inout_stats", {k: v for k, v in plan.items() if k == "inout_stats" and v.get("clips")})


class Api(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.kho = tempfile.mkdtemp()

        def mk(uid, hh):
            p = T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:00:00" % hh, "Sat Oct 17 %02d:01:00 2026" % hh, 3000)
            p.update({"Type": "Video + Audio", "Start TC": "%02d:00:00:00" % hh})
            return T.FItem(uid, p)
        sel = T.FFolder("01_SELECTED", [mk("a", 8), mk("b", 9), mk("c", 10), mk("d", 11), mk("e", 12)])
        foot = T.FFolder("01_footage")
        foot.subs.append(sel)
        root = T.FFolder("Master")
        root.subs.append(foot)
        self.pool = T.FPool(root)
        self.name = "2026.10.17.LV_Ten"
        self.api = ta.TrolyApi(self.name, self.tmp, resolve_factory=lambda: T.FResolve(T.FProject(self.name, self.pool)), start_worker=False)
        self.api._worker.connect()
        self.api.init()
        self._jobs()
        self.api.load("Master/01_footage/01_SELECTED")
        self._jobs()
        self.api._plan["stages"] = [{"name": "S1", "start": 0.0, "end": 100000.0, "color": "#fff", "bins": ["Decor", "Phỏng vấn"]}]
        self.api._plan["offsets"] = {}
        self.api.state()
        self.api.speech_set_dir(self.kho, "vi")
        st = self.api._speech_store()
        k = {n: c.rel for n, c in zip("abcde", self.api._clips)}
        self.k = k
        # a: có chữ (10-14, 20-24); b: chưa chép lời (không có trong kho); c: đã chép nhưng không có tiếng nói; d: có chữ; e: có chữ nhưng không gắn sao
        st.put_result(k["a"], "ua", "a", (1, 1.0), "08:00:00:00", LA.res([LA.line(10, 14, "xin chào"), LA.line(20, 24, "cảm ơn")], ((10, 14), (20, 24)), 60.0), "vi")
        st.put_result(k["c"], "uc", "c", (1, 1.0), "10:00:00:00", LA.res([], (), 60.0), "vi")
        st.put_result(k["d"], "ud", "d", (1, 1.0), "11:00:00:00", LA.res([LA.line(3, 9, "dạ")], ((3, 9),), 60.0), "vi")
        st.put_result(k["e"], "ue", "e", (1, 1.0), "12:00:00:00", LA.res([LA.line(5, 8, "ok")], ((5, 8),), 60.0), "vi")
        self.uid = {c["name"]: c["uid"] for c in self.api.state()["clips"]}
        self.api.label([self.uid["DGa.MP4"], self.uid["DGc.MP4"]], 0, "Phỏng vấn")
        self.api.label([self.uid["DGb.MP4"], self.uid["DGd.MP4"]], 0, "Decor")
        self.api.toggle_star([self.uid[n] for n in ("DGa.MP4", "DGb.MP4", "DGc.MP4", "DGd.MP4")])

    def _jobs(self):
        w = self.api._worker
        while not w.jobs.empty():
            j, a = w.jobs.get()
            getattr(w, "do_" + j)(a)
        self.api._drain()

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.kho, ignore_errors=True)

    def run_sug(self):
        r = self.api.inout_suggest_start()
        self.assertTrue(r.get("ok"), r)
        for _ in range(200):
            time.sleep(0.02)
            if not self.api._sug_run:
                break
        time.sleep(0.05)

    def clip(self, n):
        return next(c for c in self.api.state()["clips"] if c["name"] == n)

    def test_chua_chay_thi_giu_goi_y_tuc_thoi_theo_quy_tac_nhu_cu(self):
        c = self.clip("DGb.MP4")
        self.assertEqual(c["sug"]["src"], "live")
        self.assertEqual((c["sug"]["in_s"], c["sug"]["out_s"]), (1.2, 4.2))
        s = self.api.state()["inout_sug"]
        self.assertEqual((s["starred"], s["done"]), (4, 0))
        self.assertNotIn("inout_sug", self.api._plan)

    def test_chay_nen_muc_1_va_muc_2_dung_nguon_va_dem(self):
        self.run_sug()
        a, b, c, d = (self.clip(n) for n in ("DGa.MP4", "DGb.MP4", "DGc.MP4", "DGd.MP4"))
        self.assertEqual((a["sug"]["src"], a["sug"]["in_s"], a["sug"]["out_s"]), ("speech", 9.7, 24.3))       # mức 2: đầu câu đầu - đệm, cuối câu cuối + đệm
        self.assertEqual((d["sug"]["src"], d["sug"]["in_s"], d["sug"]["out_s"]), ("speech", 2.7, 9.3))
        self.assertEqual(b["sug"]["src"], "rule")                                                            # chưa chép lời -> mức 1 (Decor 3 s)
        self.assertEqual((b["sug"]["in_s"], b["sug"]["out_s"]), (1.2, 4.2))
        self.assertEqual(c["sug"]["src"], "rule")                                                            # không có tiếng nói -> mức 1
        self.assertEqual(c["sug"]["rule"], tc.suggest_inout(60.0, "Phỏng vấn")["rule"])
        e = self.clip("DGe.MP4")
        self.assertEqual(e["sug"]["src"], "live")                                                            # không gắn sao: không chạy, vẫn gợi ý tức thời
        s = self.api.state()["inout_sug"]
        self.assertEqual((s["starred"], s["done"], s["running"]), (4, 4, False))

    def test_dem_chinh_duoc_va_ap_dung_lan_chay_sau(self):
        self.assertEqual(self.api.inout_sug_pad(1.0)["pad"], 1.0)
        for bad in ("x", -1, 10):
            self.assertIn("error", self.api.inout_sug_pad(bad))
        self.run_sug()
        a = self.clip("DGa.MP4")
        self.assertEqual((a["sug"]["in_s"], a["sug"]["out_s"]), (9.0, 25.0))

    def test_goi_y_cu_bi_danh_dau_khi_doi_quy_tac_hoac_dem(self):
        self.run_sug()
        self.assertFalse(self.clip("DGb.MP4")["sug"]["stale"])
        self.api.set_trad_trim(2.0)
        self.api.set_bin_rule("Decor", 5, 6)
        self.assertTrue(self.clip("DGb.MP4")["sug"]["stale"])                                                # quy tắc đổi sau khi chạy: báo "cũ", chưa tự đổi
        self.assertEqual((self.clip("DGb.MP4")["sug"]["in_s"], self.clip("DGb.MP4")["sug"]["out_s"]), (1.2, 4.2))

    def test_chi_xet_clip_sao_khong_co_sao_thi_bao_loi(self):
        self.api.toggle_star([self.uid[n] for n in ("DGa.MP4", "DGb.MP4", "DGc.MP4", "DGd.MP4")])
        self.assertIn("error", self.api.inout_suggest_start())

    def test_khong_ghi_davinci_va_khong_dat_in_out_tay(self):
        self.run_sug()
        self.assertTrue(self.api._worker.jobs.empty())
        self.assertNotIn("inout", self.api._plan)                                                           # chạy gợi ý không tự đặt tay
        self.assertEqual(self.clip("DGa.MP4")["io_src"], None)

    def test_phim_a_nhan_goi_y_thanh_dat_tay_va_ghi_nhan_nhan_nguyen(self):
        self.run_sug()
        r = self.api.inout_accept(self.uid["DGa.MP4"])
        self.assertEqual((r["ok"], r["in_s"], r["out_s"], r["src"]), (True, 9.7, 24.3, "speech"))
        a = self.clip("DGa.MP4")
        self.assertEqual((a["io_src"], a["in_s"], a["out_s"]), ("manual", 9.7, 24.3))                       # xanh thành cam (đặt tay)
        self.assertEqual(r["stats"]["accepted"], 1)
        self.assertEqual(self.api.inout_stats()["by_src"]["speech"]["accepted"], 1)

    def test_dat_tay_luon_thang_goi_y_ke_ca_khi_chay_lai(self):
        self.api.set_inout(self.uid["DGa.MP4"], 2.0, 6.0)
        self.run_sug()
        a = self.clip("DGa.MP4")
        self.assertEqual((a["in_s"], a["out_s"], a["io_src"]), (2.0, 6.0, "manual"))                       # đặt tay vẫn là In/Out hiệu lực
        self.assertEqual((a["sug"]["src"], a["sug"]["in_s"]), ("speech", 9.7))                              # gợi ý vẫn có, chỉ để so
        r = self.api.inout_accept(self.uid["DGa.MP4"])                                                      # nhận lại thì thay bằng gợi ý do anh chủ động bấm
        self.assertEqual(r["in_s"], 9.7)

    def test_keo_chinh_sau_khi_nhan_tinh_la_da_chinh_va_xoa_thi_bo_ghi_nhan(self):
        self.run_sug()
        self.api.inout_accept(self.uid["DGa.MP4"])
        self.api.inout_accept(self.uid["DGb.MP4"])
        self.api.set_inout(self.uid["DGa.MP4"], 10.5, 24.3)                                                 # kéo mép In
        cnt = self.api.inout_stats()
        self.assertEqual((cnt["accepted"], cnt["adjusted"]), (1, 1))
        self.api.set_inout(self.uid["DGb.MP4"], None, None)                                                 # xóa đặt tay
        self.assertEqual(self.api.inout_stats()["accepted"], 0)

    def test_chua_co_goi_y_hoac_clip_la_thi_bao_loi(self):
        self.assertIn("error", self.api.inout_accept("khong-co"))
        c = self.api._by_uid[self.uid["DGa.MP4"]]
        c.dur = 0.5                                                                                         # clip quá ngắn: mức 1 cũng không có gợi ý
        self.assertIn("error", self.api.inout_accept(self.uid["DGa.MP4"]))

    def test_chua_chon_kho_loi_noi_thi_moi_clip_roi_ve_muc_1(self):
        self.api._speech_st = None
        self.api._plan["speech"] = {}
        self.run_sug()
        self.assertEqual({self.clip(n)["sug"]["src"] for n in ("DGa.MP4", "DGb.MP4", "DGc.MP4", "DGd.MP4")}, {"rule"})

    def test_chi_tiet_loi_noi_phan_biet_chua_chep_va_khong_co_tieng_noi(self):
        d = self.api.speech_detail
        self.assertEqual((d(self.uid["DGb.MP4"])["has_row"], d(self.uid["DGb.MP4"])["lines"]), (False, []))      # chưa chép lời: giao diện hiện "Chưa chép lời" + nút Bước 4
        self.assertEqual((d(self.uid["DGc.MP4"])["has_row"], d(self.uid["DGc.MP4"])["lines"]), (True, []))        # đã chép, không có tiếng nói: giao diện ẩn khung chữ
        a = d(self.uid["DGa.MP4"])
        self.assertTrue(a["has_row"])
        self.assertEqual([(l["t0"], l["t1"]) for l in a["lines"]], [(10, 14), (20, 24)])

    def test_ke_hoach_chi_co_khoa_moi_khi_anh_dung(self):
        self.assertFalse({"inout_sug", "inout_sug_cfg", "inout_stats"} & set(self.api._plan))
        self.run_sug()
        self.assertIn("inout_sug", self.api._plan)
        self.api._save_now()
        self.assertTrue(os.path.isfile(tc.plan_path(self.tmp, self.name)))


if __name__ == "__main__":
    unittest.main()
