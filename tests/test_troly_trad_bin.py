"""Quay Truyền thống: cắt ĐẦU và ĐUÔI riêng, THEO TỪNG BIN (ADR-0025). Mặc định 1,5 / 1,5; kế hoạch cũ (khóa trad_trim_s là số) đọc được;
nhập sai bị chặn; đổi số thì gợi ý đã lưu thành "cũ" và tính lại khi chạy lại. Dữ liệu giả, tên ví dụ LV_Ten."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import test_troly_inout_sug as B      # noqa: E402
import troly_core as tc               # noqa: E402


class Core(unittest.TestCase):
    def test_chua_sua_gi_giong_het_cu_1_5_dau_1_5_duoi(self):
        r = tc.suggest_inout(30.0, "Đón khách", "traditional")
        self.assertEqual((r["in_s"], r["out_s"]), (1.5, 28.5))
        self.assertEqual(r["rule"], "Truyền thống: giữ dài, cắt 1.5s đầu và 1.5s đuôi")
        for dur in (0.9, 1.0, 1.5, 2.0, 2.9, 3.0, 4.0, 30.0):                                # kể cả clip ngắn: y hệt cách tính cũ (co đều hai đầu)
            old_cut = min(1.5, max(0.0, (dur - 1.0) / 2.0)) if dur >= 1.0 else None
            got = tc.suggest_inout(dur, None, "traditional", None, None)
            if old_cut is None:
                self.assertIsNone(got)
            else:
                self.assertEqual((got["in_s"], got["out_s"]), (round(old_cut, 2), round(dur - old_cut, 2)), dur)

    def test_cat_dau_duoi_rieng_cho_tung_bin_clip_dai(self):
        plan = tc.new_plan("2026.10.17.LV_Ten")
        plan["shoot_style"] = "traditional"
        plan["trad_trim"] = {"Đón khách": [1.0, 0.5], "Tiễn khách": [1.0, 0.5]}
        for lb in ("Đón khách", "Tiễn khách"):                                                # ví dụ của anh: giữ gần trọn clip, cắt 1 s đầu, 0,5 s đuôi
            r = tc.suggest_plan(plan, 40.0, lb)
            self.assertEqual((r["in_s"], r["out_s"], r["dur"]), (1.0, 39.5, 38.5), lb)
            self.assertEqual(r["rule"], "Truyền thống: giữ dài, cắt 1.0s đầu và 0.5s đuôi")
        other = tc.suggest_plan(plan, 40.0, "Nghi lễ")                                        # bin chưa sửa: dùng mặc định chung
        self.assertEqual((other["in_s"], other["out_s"]), (1.5, 38.5))
        self.assertEqual(tc.suggest_plan(plan, 40.0, None)["in_s"], 1.5)                      # clip chưa xếp bin

    def test_mac_dinh_chung_tach_dau_duoi_la_mac_dinh_cua_bin_chua_sua(self):
        plan = tc.new_plan("2026.10.17.LV_Ten")
        plan["shoot_style"] = "traditional"
        plan["trad_trim_s"] = [2.0, 0.5]
        plan["trad_trim"] = {"Decor": [0.0, 0.0]}
        self.assertEqual(tc.trad_default(plan), (2.0, 0.5))
        r = tc.suggest_plan(plan, 20.0, "Nghi lễ")
        self.assertEqual((r["in_s"], r["out_s"]), (2.0, 19.5))
        r = tc.suggest_plan(plan, 20.0, "Decor")                                              # riêng bin thắng mặc định chung; 0 hợp lệ
        self.assertEqual((r["in_s"], r["out_s"]), (0.0, 20.0))

    def test_clip_ngan_van_chua_it_nhat_1_giay_va_giu_ti_le(self):
        plan = tc.new_plan("2026.10.17.LV_Ten")
        plan["shoot_style"] = "traditional"
        plan["trad_trim"] = {"Đón khách": [1.0, 0.5]}
        r = tc.suggest_plan(plan, 2.0, "Đón khách")                                           # cần cắt 1,5 nhưng chỉ có 1,0 dư: co theo tỉ lệ 2:1
        self.assertAlmostEqual(r["dur"], 1.0, places=1)
        self.assertAlmostEqual(r["in_s"] / (2.0 - r["out_s"]), 2.0, places=1)
        r = tc.suggest_plan(plan, 1.0, "Đón khách")                                           # đúng 1 giây: giữ nguyên cả clip
        self.assertEqual((r["in_s"], r["out_s"]), (0.0, 1.0))
        self.assertIsNone(tc.suggest_plan(plan, 0.9, "Đón khách"))
        for dur in (1.0, 1.2, 2.0, 3.0, 5.0, 60.0):
            for h, t in ((0, 0), (1, 0.5), (1.5, 1.5), (30, 30)):
                rr = tc.suggest_inout(dur, "x", "traditional", None, None, (h, t))
                self.assertGreaterEqual(rr["dur"], min(dur, 1.0) - 0.011, (dur, h, t))        # luôn còn >= 1 giây (clip ≥ 1 s)

    def test_khoa_cu_la_so_van_doc_duoc_va_gia_tri_hong_bi_bo_qua(self):
        plan = tc.new_plan("2026.10.17.LV_Ten")
        plan["shoot_style"] = "traditional"
        plan["trad_trim_s"] = 2.0                                                              # kế hoạch cũ: một số chung
        self.assertEqual(tc.trad_default(plan), (2.0, 2.0))
        self.assertEqual(tc.suggest_plan(plan, 30.0, "Decor")["in_s"], 2.0)
        for bad in ("x", -1, [1], [1, 2, 3], [-1, 0], [1, "a"], True, float("nan"), 9999, {"a": 1}):
            plan["trad_trim_s"] = bad
            self.assertEqual(tc.trad_default(plan), (1.5, 1.5), bad)                           # hỏng thì dùng mặc định, không lỗi
            plan["trad_trim"] = {"Decor": bad}
            self.assertIsNone(tc.trad_for(plan, "Decor"), bad)
        plan["trad_trim"] = "khong-phai-dict"
        self.assertIsNone(tc.trad_for(plan, "Decor"))

    def test_nhap_sai_bi_chan_voi_loi_ro(self):
        for bad in ((-1, 1), (1, -0.1), ("a", 1), (1, None), (float("nan"), 1), (1, float("inf")), (601, 1), (1, 601)):
            ok, msg = tc.check_trad(*bad)
            self.assertFalse(ok, bad)
            self.assertIsInstance(msg, str)
        self.assertEqual(tc.check_trad(0, 0), (True, (0.0, 0.0)))
        self.assertEqual(tc.check_trad("1,5".replace(",", "."), 0.5), (True, (1.5, 0.5)))

    def test_kieu_khac_khong_dung_cat_dau_duoi(self):
        plan = tc.new_plan("2026.10.17.LV_Ten")
        plan["trad_trim"] = {"Decor": [0.0, 0.0]}
        plan["trad_trim_s"] = [5.0, 5.0]
        base = tc.suggest_inout(20.0, "Decor", "")
        self.assertEqual(tc.suggest_plan(plan, 20.0, "Decor"), base)                          # chưa chọn kiểu: bảng min/max như cũ
        plan["shoot_style"] = "psc"
        self.assertEqual(tc.suggest_plan(plan, 20.0, "Decor"), tc.suggest_inout(20.0, "Decor", "psc"))   # PSC giữ nguyên bảng min/max

    def test_chu_ky_cache_doi_khi_doi_cat_dau_duoi(self):
        plan = tc.new_plan("2026.10.17.LV_Ten")
        plan["shoot_style"] = "traditional"
        s0 = tc.sug_signature(plan, "Đón khách")
        plan["trad_trim"] = {"Đón khách": [1.0, 0.5]}
        s1 = tc.sug_signature(plan, "Đón khách")
        self.assertNotEqual(s0, s1)
        self.assertEqual(tc.sug_signature(plan, "Tiễn khách"), s0)                            # bin khác (cùng quy tắc) không bị ảnh hưởng
        plan["trad_trim"]["Đón khách"] = [1.0, 0.6]
        self.assertNotEqual(tc.sug_signature(plan, "Đón khách"), s1)
        plan["trad_trim_s"] = [2.0, 0.5]                                                       # mặc định chung đổi -> mọi bin chưa sửa
        self.assertNotEqual(tc.sug_signature(plan, "Tiễn khách"), s0)


class Api(unittest.TestCase):
    setUp = B.Api.setUp
    tearDown = B.Api.tearDown
    _jobs = B.Api._jobs
    run_sug = B.Api.run_sug
    clip = B.Api.clip

    def test_chua_sua_goi_y_y_het_hien_tai(self):
        self.api.set_shoot_style("traditional")
        b = self.clip("DGb.MP4")["sug"]
        self.assertEqual((b["in_s"], b["out_s"]), (1.5, 58.5))                                 # clip 60 s: 1,5 đầu, 1,5 đuôi
        self.assertFalse({"trad_trim", "trad_trim_s"} & set(self.api._plan))                   # chưa sửa: không có khóa

    def test_dat_cat_dau_duoi_theo_bin_luu_trong_ke_hoach_va_ap_vao_goi_y(self):
        self.api.set_shoot_style("traditional")
        r = self.api.set_trad_bin("Decor", 1.0, 0.5)
        self.assertNotIn("error", r)
        self.assertEqual(self.api._plan["trad_trim"], {"Decor": [1.0, 0.5]})
        b = self.clip("DGb.MP4")["sug"]                                                       # DGb là Decor
        self.assertEqual((b["in_s"], b["out_s"]), (1.0, 59.5))
        d = self.clip("DGd.MP4")["sug"]                                                       # DGd cũng Decor; DGa là Phỏng vấn: chưa sửa -> mặc định
        self.assertEqual((d["in_s"], d["out_s"]), (1.0, 59.5))
        self.assertEqual(self.clip("DGa.MP4")["sug"]["in_s"], 1.5)
        rs = self.api._rules_state()
        self.assertEqual(rs["trad_bins"]["Decor"], {"head": 1.0, "tail": 0.5, "edited": True})
        self.assertEqual(rs["trad_bins"]["Phỏng vấn"], {"head": 1.5, "tail": 1.5, "edited": False})

    def test_mac_dinh_chung_tach_dau_duoi_va_khoa_cu_tuong_thich(self):
        self.api.set_shoot_style("traditional")
        self.api.set_trad_default(2.0, 0.5)
        self.assertEqual(self.api._plan["trad_trim_s"], [2.0, 0.5])
        self.assertEqual(self.api._rules_state()["trad_head"], 2.0)
        self.assertEqual(self.api._rules_state()["trad_tail"], 0.5)
        self.api.set_trad_default(1.0, 1.0)
        self.assertEqual(self.api._plan["trad_trim_s"], 1.0)                                   # đầu = đuôi: vẫn là SỐ như khóa cũ
        self.api.set_trad_default(1.5, 1.5)
        self.assertNotIn("trad_trim_s", self.api._plan)                                        # về mặc định: xóa khóa
        self.assertNotIn("error", self.api.set_trad_trim(2.0))                                 # hàm cũ vẫn chạy
        self.assertEqual(self.api._plan["trad_trim_s"], 2.0)

    def test_nhap_sai_bi_chan_va_khong_ghi_gi(self):
        for args in ((-1, 1), (1, -1), ("a", 1), (1, None), (float("nan"), 1), (700, 1)):
            self.assertIn("error", self.api.set_trad_default(*args), args)
            self.assertIn("error", self.api.set_trad_bin("Decor", *args), args)
        self.assertIn("error", self.api.set_trad_bin("", 1, 1))
        self.assertIn("error", self.api.set_trad_bin(None, 1, 1))
        self.assertFalse({"trad_trim", "trad_trim_s"} & set(self.api._plan))

    def test_ve_mac_dinh_tung_bin_va_ca_bang(self):
        self.api.set_trad_bin("Decor", 1, 0.5)
        self.api.set_trad_bin("Phỏng vấn", 0, 0)
        self.api.set_trad_default(2, 0.5)
        self.api.reset_trad_bin("Decor")
        self.assertEqual(list(self.api._plan["trad_trim"]), ["Phỏng vấn"])
        self.api.reset_trad_bin("Phỏng vấn")
        self.assertNotIn("trad_trim", self.api._plan)                                          # hết bin sửa thì bỏ khóa
        self.api.set_trad_bin("Decor", 1, 0.5)
        self.api.reset_bin_rule(None)                                                          # "Về mặc định" cả bảng: xóa cả cắt đầu/đuôi
        self.assertFalse({"trad_trim", "trad_trim_s", "bin_rules"} & set(self.api._plan))

    def test_doi_cat_dau_duoi_thi_goi_y_da_luu_thanh_cu_va_chay_lai_tinh_lai(self):
        self.api.set_shoot_style("traditional")
        self.run_sug()
        b = self.clip("DGb.MP4")["sug"]
        self.assertEqual((b["src"], b["in_s"], b["stale"]), ("rule", 1.5, False))
        self.api.set_trad_bin("Decor", 1.0, 0.5)
        b = self.clip("DGb.MP4")["sug"]
        self.assertTrue(b["stale"])                                                            # cache cũ: báo cần "Chạy lại", chưa tự đổi
        self.assertEqual(b["in_s"], 1.5)
        self.assertFalse(self.clip("DGa.MP4")["sug"]["stale"] and False)
        self.run_sug()
        b = self.clip("DGb.MP4")["sug"]
        self.assertEqual((b["in_s"], b["out_s"], b["stale"]), (1.0, 59.5, False))              # chạy lại -> theo số mới

    def test_ke_hoach_cu_chi_co_khoa_trad_trim_s_so_doc_va_ghi_vong_khong_loi(self):
        import tempfile
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "troly", "projects"))
        old = {"schema": 1, "project": "2026.10.17.LV_Ten", "source_bin": "M", "template": "x", "stages": [], "offsets": {}, "labels": {},
               "moves": [], "updated": None, "day0": None, "shoot_style": "traditional", "trad_trim_s": 2.0}
        p = os.path.join(d, "troly", "projects", "2026.10.17.LV_Ten.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(old, f)
        plan = tc.load_plan(d, "2026.10.17.LV_Ten")
        self.assertEqual(tc.trad_default(plan), (2.0, 2.0))
        self.assertEqual(tc.suggest_plan(plan, 30.0, "Decor")["in_s"], 2.0)
        tc.save_plan(d, plan)
        with open(p, encoding="utf-8") as f:
            back = json.load(f)
        self.assertEqual(back["trad_trim_s"], 2.0)
        self.assertNotIn("trad_trim", back)                                                    # khóa mới chỉ có khi anh sửa theo bin


class Web(unittest.TestCase):
    def setUp(self):
        web = os.path.join(HERE, "..", "app", "troly_web")
        self.js = open(os.path.join(web, "step3.js"), encoding="utf-8").read()
        self.html = open(os.path.join(web, "index.html"), encoding="utf-8").read()

    def test_bang_truyen_thong_hai_cot_cat_dau_cat_duoi_va_hai_o_chung(self):
        self.assertIn("Cắt đầu (s)", self.js)
        self.assertIn("Cắt đuôi (s)", self.js)
        self.assertIn("api().set_trad_bin(", self.js)
        self.assertIn("api().set_trad_default(", self.js)
        self.assertEqual(self.html.count('id="tradHead"'), 1)
        self.assertEqual(self.html.count('id="tradTail"'), 1)
        self.assertNotIn('id="tradTrim"', self.html)
        self.assertIn("Về mặc định", self.html)


if __name__ == "__main__":
    unittest.main()
