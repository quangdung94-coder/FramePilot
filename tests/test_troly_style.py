"""Kiểu quay PSC / Truyền thống (ADR-0018): chỉ là bộ tham số của gợi ý In/Out màu xanh. Chưa chọn = KHÔNG đổi gì (so với bảng giá trị
của bản trước khi thêm tính năng); In/Out đặt tay luôn thắng; không bao giờ ghi gợi ý vào DaVinci. Tên ví dụ LV_Ten."""
import json
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

# [độ dài, nhãn bin, [in, out, giữ, giải thích]] do hàm suggest_inout CŨ (trước khi thêm kiểu quay) trả về
BASELINE = json.loads(r'''[[0.9, null, null], [0.9, "Decor", null], [0.9, "Beauty cô dâu", null], [0.9, "Nghi lễ", null], [0.9, "Phỏng vấn", null], [0.9, "Khác", null], [0.9, "Chú rể", null], [1.0, null, [0.0, 1.0, 1.0, "Quy tắc v4: vào +1.2s, giữ 3s"]], [1.0, "Decor", [0.0, 1.0, 1.0, "Decor: 3.0s ổn định"]], [1.0, "Beauty cô dâu", [0.0, 1.0, 1.0, "CD-CR: 4.0s cảm xúc"]], [1.0, "Nghi lễ", [0.0, 1.0, 1.0, "Nghi lễ: giữ 5–7s"]], [1.0, "Phỏng vấn", [0.0, 1.0, 1.0, "Phỏng vấn: giữ trọn câu"]], [1.0, "Khác", [0.0, 1.0, 1.0, "Quy tắc v4: vào +1.2s, giữ 3s"]], [1.0, "Chú rể", [0.0, 1.0, 1.0, "CD-CR: 4.0s cảm xúc"]], [2.5, null, [0.0, 2.0, 2.0, "Quy tắc v4: vào +1.2s, giữ 3s"]], [2.5, "Decor", [0.0, 2.0, 2.0, "Decor: 3.0s ổn định"]], [4, null, [0.5, 3.5, 3.0, "Quy tắc v4: vào +1.2s, giữ 3s"]], [4, "Decor", [0.5, 3.5, 3.0, "Decor: 3.0s ổn định"]], [4, "Beauty cô dâu", [0.0, 3.5, 3.5, "CD-CR: 4.0s cảm xúc"]], [4, "Nghi lễ", [0.5, 3.5, 3.0, "Nghi lễ: giữ 5–7s"]], [4, "Phỏng vấn", [0.5, 3.5, 3.0, "Phỏng vấn: giữ trọn câu"]], [5, null, [1.2, 4.2, 3.0, "Quy tắc v4: vào +1.2s, giữ 3s"]], [5, "Beauty cô dâu", [1.2, 4.5, 3.3, "CD-CR: 4.0s cảm xúc"]], [5, "Nghi lễ", [1.2, 4.5, 3.3, "Nghi lễ: giữ 5–7s"]], [8, null, [1.2, 4.2, 3.0, "Quy tắc v4: vào +1.2s, giữ 3s"]], [8, "Decor", [1.2, 4.2, 3.0, "Decor: 3.0s ổn định"]], [8, "Beauty cô dâu", [1.2, 5.2, 4.0, "CD-CR: 4.0s cảm xúc"]], [8, "Nghi lễ", [1.2, 7.5, 6.3, "Nghi lễ: giữ 5–7s"]], [8, "Phỏng vấn", [1.2, 7.5, 6.3, "Phỏng vấn: giữ trọn câu"]], [12, "Nghi lễ", [1.2, 8.2, 7.0, "Nghi lễ: giữ 5–7s"]], [12, "Phỏng vấn", [1.2, 11.5, 10.3, "Phỏng vấn: giữ trọn câu"]], [12, "Chú rể", [1.2, 5.2, 4.0, "CD-CR: 4.0s cảm xúc"]], [30, null, [1.2, 4.2, 3.0, "Quy tắc v4: vào +1.2s, giữ 3s"]], [30, "Nghi lễ", [1.2, 8.2, 7.0, "Nghi lễ: giữ 5–7s"]], [30, "Phỏng vấn", [1.2, 29.5, 28.3, "Phỏng vấn: giữ trọn câu"]]]''')


def pack(r):
    return None if r is None else [r["in_s"], r["out_s"], r["dur"], r["rule"]]


class StyleRules(unittest.TestCase):
    def test_chua_chon_khong_doi_gi_so_voi_ban_truoc(self):
        for dur, label, want in BASELINE:
            self.assertEqual(pack(tc.suggest_inout(dur, label)), want, (dur, label))                # không truyền kiểu = như cũ
            self.assertEqual(pack(tc.suggest_inout(dur, label, "")), want, (dur, label))            # kiểu "" (chưa chọn) = như cũ

    def test_psc_ra_cung_so_voi_mac_dinh_chi_them_nhan_psc(self):
        for dur, label, want in BASELINE:
            got = pack(tc.suggest_inout(dur, label, "psc"))
            if want is None:
                self.assertIsNone(got)
            else:
                self.assertEqual(got[:3], want[:3], (dur, label))                                   # 3-7 giây theo loại bin, như bộ tham số hiện có
                self.assertTrue(got[3].startswith("PSC · "))

    def test_truyen_thong_giu_dai_chi_cat_dau_va_duoi(self):
        for label in (None, "Decor", "Nghi lễ", "Phỏng vấn", "Beauty cô dâu"):                       # không phân biệt bin
            r = tc.suggest_inout(30.0, label, "traditional")
            self.assertEqual((r["in_s"], r["out_s"], r["dur"]), (1.5, 28.5, 27.0))
            self.assertIn("Truyền thống", r["rule"])
        r = tc.suggest_inout(8.0, "Decor", "traditional")
        self.assertEqual((r["in_s"], r["out_s"]), (1.5, 6.5))                                       # dài hơn nhiều so với 3 giây của PSC
        self.assertGreater(tc.suggest_inout(8.0, "Decor", "traditional")["dur"], tc.suggest_inout(8.0, "Decor", "psc")["dur"])

    def test_truyen_thong_clip_ngan_van_con_it_nhat_1_giay(self):
        self.assertIsNone(tc.suggest_inout(0.9, None, "traditional"))
        for dur in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
            r = tc.suggest_inout(dur, None, "traditional")
            self.assertGreaterEqual(r["dur"], 1.0 - 1e-9, dur)
            self.assertGreaterEqual(r["in_s"], 0.0)
            self.assertLessEqual(r["out_s"], dur)
            self.assertAlmostEqual(r["in_s"] + r["dur"] + (dur - r["out_s"]), dur, places=1)
        r = tc.suggest_inout(1.0, None, "traditional")
        self.assertEqual((r["in_s"], r["out_s"]), (0.0, 1.0))                                       # clip 1 giây: không cắt


class StyleApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        sel = T.FFolder("01_SELECTED", [T.FItem("a", T.props("DGa.MP4", "Sat Oct 17 2026 08:10:00", "Sat Oct 17 08:10:20 2026", 1000, Type="Video + Audio")),
                                        T.FItem("b", T.props("DGb.MP4", "Sat Oct 17 2026 08:20:00", "Sat Oct 17 08:20:20 2026", 1000, Type="Video + Audio"))])
        foot = T.FFolder("01_footage")
        foot.subs.append(sel)
        root = T.FFolder("Master")
        root.subs.append(foot)
        self.pool = T.FPool(root)
        self.name = "2026.10.17.LV_Ten"
        self.api = self._api()
        w = self.api._worker
        w.connect()
        self.api.init()
        self.run_jobs()
        self.api.load("Master/01_footage/01_SELECTED")
        self.run_jobs()

    def _api(self):
        return ta.TrolyApi(self.name, self.tmp, resolve_factory=lambda: T.FResolve(T.FProject(self.name, self.pool)), start_worker=False)

    def run_jobs(self):
        w = self.api._worker
        while not w.jobs.empty():
            j, a = w.jobs.get()
            getattr(w, "do_" + j)(a)
        self.api._drain()

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sug(self, name="DGa.MP4"):
        return next(c for c in self.api.state()["clips"] if c["name"] == name)["sug"]

    def test_mac_dinh_la_chua_chon_va_khong_doi_gi(self):
        st = self.api.state()
        self.assertEqual(st["shoot_style"], "")
        self.assertNotIn("shoot_style", self.api._plan)                                              # kế hoạch cũ không có khóa: không đổi
        self.assertEqual(self.sug()["rule"], "Quy tắc v4: vào +1.2s, giữ 3s")
        self.assertEqual((self.sug()["in_s"], self.sug()["out_s"]), (1.2, 4.2))

    def test_chon_kieu_doi_goi_y_luu_trong_ke_hoach_va_mo_lai_van_con(self):
        r = self.api.set_shoot_style("traditional")
        self.assertEqual(r["shoot_style"], "traditional")
        s = self.sug()
        self.assertEqual((s["in_s"], s["out_s"]), (1.5, 18.5))                                       # clip 20 giây: giữ dài, cắt 1,5 s hai đầu
        self.assertIn("Truyền thống", s["rule"])
        api2 = self._api()
        try:
            self.assertEqual(api2._plan["shoot_style"], "traditional")                              # nhớ theo project
        finally:
            api2._thumbs.shutdown()
        self.api.set_shoot_style("psc")
        self.assertTrue(self.sug()["rule"].startswith("PSC · "))
        self.api.set_shoot_style("")                                                                 # bỏ chọn: về như mặc định
        self.assertEqual(self.sug()["rule"], "Quy tắc v4: vào +1.2s, giữ 3s")
        self.assertNotIn("shoot_style", self.api._plan)

    def test_kieu_khong_hop_le_bi_chan(self):
        self.assertIn("error", self.api.set_shoot_style("lung tung"))
        self.assertNotIn("shoot_style", self.api._plan)

    def test_in_out_dat_tay_luon_thang_va_goi_y_khong_duoc_ghi(self):
        uid = next(c.uid for c in self.api._clips if c.name == "DGa.MP4")
        self.api.set_inout(uid, 2.0, 6.0)
        before = tc.inout_frames(self.api._plan, self.api._by_uid[uid])
        self.api.set_shoot_style("traditional")
        self.assertEqual(tc.inout_frames(self.api._plan, self.api._by_uid[uid]), before)             # đặt tay không đổi theo kiểu quay
        ek = tc.effective_inout(self.api._plan, self.api._by_uid[uid])
        self.assertIsNotNone(ek)
        # clip chưa đặt tay: nút ghi hàng loạt bỏ qua, gợi ý theo kiểu quay KHÔNG được ghi
        pv = self.api.inout_write_preview("selected", [c.uid for c in self.api._clips])
        self.assertEqual((pv["pool"], pv["n"], pv["skip"]), (2, 1, 1))

    def test_tab_giao_dien_co_o_chon_kieu_quay(self):
        web = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web")
        html = open(os.path.join(web, "index.html"), encoding="utf-8").read()
        js = open(os.path.join(web, "app.js"), encoding="utf-8").read()
        self.assertIn('id="styleSel"', html)
        self.assertIn('<option value="">Kiểu quay: chưa chọn</option>', html)                       # mặc định chưa chọn
        self.assertIn('value="traditional"', html)
        self.assertIn('value="psc"', html)
        self.assertIn("set_shoot_style", js)
        self.assertNotIn("SetMarkInOut", js)


if __name__ == "__main__":
    unittest.main()
