"""Bước 5 làm lại thành THANH KÉO (ADR-0013, bản 18/11/2026 tối): Có = thanh đầy, Lấy = kéo/gõ, không vượt Có; mặc định không giới hạn Max;
khóa/gõ số làm giai đoạn khác co giãn; thiếu chỉ báo ở tổng; gợi ý Tự kéo thêm / Hạ mục tiêu / Quay lại Bước 3. Dữ liệu giả, tên ví dụ LV_Ten."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import troly_dur as td                # noqa: E402
from test_troly_dur import mk, clip   # noqa: E402

STAGES = [{"name": "S%d" % i, "bins": ["Nghi lễ"], "start": 0, "end": 99999} for i in (1, 2, 3)]


def scene(n1=18, n2=12, n3=8, stages=STAGES, **extra):
    """S1 có n1 clip sao (mỗi clip 5 s theo quy tắc Nghi lễ) ...; mục tiêu mặc định 3:00 = 180 s; clip sao có tổng 190 s (n mặc định)."""
    spec = []
    for si, n in enumerate((n1, n2, n3)):
        spec += [("s%d_%d" % (si, i), si, "Nghi lễ", 1, si * 1000 + i, 30) for i in range(n)]
    d = {"target_min": 3}
    d.update(extra.pop("durations", {}))
    return mk(spec, stages=stages, durations=d, **extra)


def stg(r, i):
    return r["stages"][i]


class CoVaLay(unittest.TestCase):
    def test_co_la_toan_bo_clip_sao_va_mac_dinh_khong_gioi_han_max(self):
        r = td.build(*scene(durations={"target_min": 30}))                          # mục tiêu rất lớn: phải lấy HẾT clip sao, không bị Max chặn
        for i, have in enumerate((90.0, 60.0, 40.0)):
            self.assertEqual(stg(r, i)["natural_s"], have)
            self.assertAlmostEqual(stg(r, i)["total_s"], have)
            self.assertTrue(stg(r, i)["maxed"])
            b = stg(r, i)["bins"][0]
            self.assertFalse(b["edited"])
            self.assertEqual((b["min"], b["max"]), (0.0, have))
        self.assertEqual(r["n_used"], 38)

    def test_decor_va_beauty_khong_con_bi_chan_mac_dinh(self):
        stages = [{"name": "S1", "bins": ["Decor", "Beauty cô dâu"], "start": 0, "end": 99999}]
        spec = [("d%d" % i, 0, "Decor", 1, i, 20) for i in range(30)] + [("b%d" % i, 0, "Beauty cô dâu", 1, 100 + i, 30) for i in range(30)]
        r = td.build(*mk(spec, stages=stages, durations={"target_min": 30}))
        dec, bea = stg(r, 0)["bins"]
        self.assertGreater(dec["total_s"], 20.0)                                      # trước đây kẹt ở Max 20 s
        self.assertGreater(bea["total_s"], 30.0)                                      # trước đây kẹt ở Max 30 s
        self.assertAlmostEqual(dec["total_s"], dec["natural_s"], places=0)

    def test_min_max_nang_cao_van_chan_khi_anh_tu_dat(self):
        stages = [{"name": "S1", "bins": ["Decor"], "start": 0, "end": 99999}]
        spec = [("d%d" % i, 0, "Decor", 1, i, 20) for i in range(30)]
        r = td.build(*mk(spec, stages=stages, durations={"target_min": 30, "bins": {"S1": {"Decor": [10, 20]}}}))
        b = stg(r, 0)["bins"][0]
        self.assertTrue(b["edited"])
        self.assertLessEqual(b["total_s"], 20.0 + 1e-6)
        self.assertGreaterEqual(stg(r, 0)["avail_s"], 17.0)                           # Max anh đặt hạ trần của giai đoạn (6 clip x 3 s = 18 s)
        self.assertLessEqual(stg(r, 0)["avail_s"], 20.0)
        self.assertEqual(stg(r, 0)["natural_s"], 90.0)                                # thanh đầy vẫn là toàn bộ clip sao
        self.assertIn("bin_over", [w["kind"] for w in r["warnings"]])

    def test_go_hoac_keo_khong_vuot_co(self):
        r = td.build(*scene(durations={"stage_s": {"S3": 7000}}))
        self.assertAlmostEqual(stg(r, 2)["budget_s"], 40.0)                           # kẹp ở cuối thanh (Có = 40 s)
        self.assertAlmostEqual(stg(r, 2)["total_s"], 40.0)
        r = td.build(*scene(durations={"bin_s": {"S3": {"Nghi lễ": 9999}}, "stage_s": {"S3": 7000}}))
        self.assertAlmostEqual(stg(r, 2)["bins"][0]["total_s"], 40.0)
        self.assertEqual(stg(r, 2)["bins"][0]["pin"], 40.0)

    def test_keo_bin_con_tong_giai_doan_theo(self):
        stages = [{"name": "S1", "bins": ["A", "B"], "start": 0, "end": 99999}, {"name": "S2", "bins": ["Nghi lễ"], "start": 0, "end": 99999}]
        spec = [("a%d" % i, 0, "A", 1, i, 30) for i in range(10)] + [("b%d" % i, 0, "B", 1, 50 + i, 30) for i in range(10)] + \
               [("c%d" % i, 1, "Nghi lễ", 1, 200 + i, 30) for i in range(10)]
        r0 = td.build(*mk(spec, stages=stages, durations={"target_min": 1.5}))
        a0, b0 = stg(r0, 0)["bins"]
        r1 = td.build(*mk(spec, stages=stages, durations={"target_min": 1.5, "stage_s": {"S1": b0["total_s"] + 10},
                                                          "bin_s": {"S1": {"A": 10}}}))
        a1, b1 = stg(r1, 0)["bins"]
        self.assertAlmostEqual(a1["total_s"], 10.0, delta=1.5)                         # clip nguyên: 3 clip x 3 s = 9 s                         # bin A kéo xuống 10 s
        self.assertAlmostEqual(b1["total_s"], b0["total_s"], delta=0.5)                # bin B giữ nguyên
        self.assertAlmostEqual(stg(r1, 0)["total_s"], b0["total_s"] + 10.0, delta=1.5)  # tổng giai đoạn cập nhật theo
        self.assertEqual(a1["pin"], 10.0)


class Chia(unittest.TestCase):
    def test_khong_khoa_chia_theo_ti_le_clip_sao_co_va_tong_bang_muc_tieu(self):
        r = td.build(*scene())
        self.assertEqual([stg(r, i)["avail_s"] for i in range(3)], [90.0, 60.0, 40.0])
        self.assertAlmostEqual(stg(r, 0)["budget_s"], 180 * 90 / 190, delta=0.2)
        self.assertAlmostEqual(sum(stg(r, i)["budget_s"] for i in range(3)), 180.0, delta=0.5)
        self.assertAlmostEqual(r["total_s"], 180.0, delta=3.0)
        self.assertEqual(r["state"], "ok")

    def test_khoa_mot_giai_doan_cac_giai_doan_khac_co_gian(self):
        r = td.build(*scene(durations={"stage_s": {"S1": 80}, "locked": ["S1"]}))
        self.assertAlmostEqual(stg(r, 0)["budget_s"], 80.0)
        self.assertTrue(stg(r, 0)["locked"])
        self.assertAlmostEqual(stg(r, 1)["budget_s"] / stg(r, 2)["budget_s"], 60.0 / 40.0, places=1)
        self.assertAlmostEqual(r["total_s"], 180.0, delta=3.0)

    def test_khoa_hai_giai_doan_giai_doan_con_lai_nhan_phan_du_nhung_khong_vuot(self):
        r = td.build(*scene(durations={"stage_s": {"S1": 30, "S2": 20}, "locked": ["S1", "S2"]}))
        self.assertAlmostEqual(stg(r, 2)["budget_s"], 40.0)                          # chỉ có 40 s clip sao: KHÔNG vượt dù còn 130 s trống
        self.assertEqual(r["state"], "short")
        self.assertAlmostEqual(r["total_s"], 90.0, delta=1.0)
        self.assertAlmostEqual(r["short_s"], 90.0, delta=1.0)

    def test_go_so_vao_mot_giai_doan_thanh_anh_chot_con_lai_co_gian(self):
        r = td.build(*scene(durations={"stage_s": {"S2": 55}}))
        self.assertTrue(stg(r, 1)["pinned"])
        self.assertFalse(stg(r, 1)["locked"])
        self.assertAlmostEqual(stg(r, 1)["budget_s"], 55.0)
        self.assertAlmostEqual(stg(r, 0)["budget_s"] + stg(r, 2)["budget_s"], 125.0, delta=0.5)
        self.assertAlmostEqual(stg(r, 0)["budget_s"] / stg(r, 2)["budget_s"], 90.0 / 40.0, places=1)

    def test_thieu_that_chi_bao_o_tong_giai_doan_khong_con_bao_thieu_rieng(self):
        r = td.build(*scene(durations={"target_min": 10}))
        self.assertEqual(r["state"], "short")
        self.assertAlmostEqual(r["short_s"], 600 - 190, delta=1.0)
        for s in r["stages"]:
            self.assertTrue(s["maxed"])
            self.assertNotIn("short_s", s)
            self.assertNotIn("short_kind", s)
            self.assertEqual(s["dropped_n"], 0)

    def test_allocate_thuan(self):
        self.assertEqual(td.allocate_stages(100, [50, 50], {}), [50.0, 50.0])
        self.assertEqual(td.allocate_stages(40, [50, 50], {0: 10}), [10.0, 30.0])
        b = td.allocate_stages(100, [10, 100, 100], {})
        self.assertAlmostEqual(b[0], 100 * 10 / 210)
        self.assertAlmostEqual(sum(b), 100.0)
        self.assertEqual(td.allocate_stages(500, [10, 100, 100], {}), [10.0, 100.0, 100.0])
        self.assertEqual(td.allocate_stages(100, [0, 0], {}), [0.0, 0.0])

    def test_sua_min_max_nang_cao_tinh_lai_ngay(self):
        r0 = td.build(*scene(durations={"target_min": 1.0}))
        r1 = td.build(*scene(durations={"target_min": 1.0, "bins": {"S1": {"Nghi lễ": [10, 20]}}}))
        self.assertTrue(stg(r1, 0)["bins"][0]["edited"])
        self.assertLessEqual(stg(r1, 0)["bins"][0]["total_s"], 20.0 + 1e-6)
        self.assertNotEqual(r0["items"], r1["items"])

    def test_bo_clip_it_uu_tien_va_ghi_ten_clip_bo(self):
        r = td.build(*scene(durations={"target_min": 3.0, "stage_s": {"S1": 40}}))
        s1 = stg(r, 0)
        self.assertGreater(s1["dropped_n"], 0)
        self.assertEqual(len(s1["dropped_clips"]), s1["dropped_n"])
        self.assertTrue(all(c["name"].endswith(".MP4") for c in s1["dropped_clips"]))
        self.assertAlmostEqual(s1["natural_s"] - s1["total_s"], s1["dropped_s"], delta=0.11)


class SoThat(unittest.TestCase):
    """Ca anh báo: 4 giai đoạn có 34:42 clip sao, mục tiêu 30:00. Trước đây còn 10:00 (thiếu 20:00) và 4 số cộng ra 29:11."""

    def four(self, style=None, target_min=30):
        stages = [{"name": "G%d" % i, "bins": ["Nghi lễ"], "start": 0, "end": 99999} for i in range(1, 5)]
        spec = []
        for si, n in enumerate((70, 120, 100, 126)):               # x 5 s = 349 + 600 + 500 + 630 = 2080 s = 34:40 (gần 34:42)
            spec += [("n%d_%d" % (si, i), si, "Nghi lễ", 1, si * 1000 + i, 30) for i in range(n)]
        extra = {"shoot_style": style} if style else {}
        return mk(spec, stages=stages, durations={"target_min": target_min}, **extra)

    def test_34_42_clip_sao_muc_tieu_30_00_phai_dat_30_00(self):
        plan, clips, assign, st = self.four()
        r = td.build(plan, clips, assign, st)
        self.assertAlmostEqual(sum(s["natural_s"] for s in r["stages"]), 34 * 60 + 40, delta=3)       # 34:40 ~ 34:42 clip sao
        self.assertEqual(r["state"], "ok")
        self.assertAlmostEqual(r["total_s"], 1800.0, delta=td.TOL_S)
        self.assertEqual(r["short_s"], 0.0)

    def test_tong_cac_giai_doan_bang_muc_tieu_khi_du_clip(self):
        plan, clips, assign, st = self.four()
        r = td.build(plan, clips, assign, st)
        self.assertAlmostEqual(sum(s["budget_s"] for s in r["stages"]), 1800.0, delta=0.5)      # số "lấy" cộng ra đúng mục tiêu (không 29:11)
        self.assertAlmostEqual(sum(s["total_s"] for s in r["stages"]), r["total_s"], delta=0.2)
        for s in r["stages"]:
            self.assertLessEqual(abs(s["total_s"] - s["budget_s"]), 2.0)

    def test_truyen_thong_van_dat_muc_tieu_nho_bu_lai_clip(self):
        plan, clips, assign, st = self.four(style="traditional")
        r = td.build(plan, clips, assign, st)
        self.assertEqual({round(i["dur"], 1) for i in r["items"]}, {27.0})                      # chỉ bỏ nguyên clip
        self.assertAlmostEqual(r["total_s"], 1800.0, delta=td.TOL_S)
        self.assertNotEqual(r["state"], "short")


class TruyenThong(unittest.TestCase):
    def test_chi_bo_nguyen_clip_khong_rut(self):
        r = td.build(*scene(shoot_style="traditional", durations={"target_min": 1.5}))
        self.assertEqual({round(i["dur"], 1) for i in r["items"]}, {27.0})              # 30 s bớt 1,5 s đầu và đuôi, KHÔNG rút ngắn thêm
        self.assertAlmostEqual(r["total_s"], 90.0, delta=td.TOL_S + 0.5)

    def test_clip_sao_co_the_cho_la_so_nguyen_clip_vua_max(self):
        spec = [("t%d" % i, 0, "Nghi lễ", 1, i, 30) for i in range(4)]
        r = td.build(*mk(spec, shoot_style="traditional", durations={"bins": {"S1": {"Nghi lễ": [10, 70]}}}))
        b = r["stages"][0]["bins"][2]
        self.assertEqual(b["avail_s"], 54.0)
        self.assertEqual(r["stages"][0]["avail_s"], 54.0)

    def test_bu_lai_so_du_do_bo_nguyen_clip(self):
        stages = [{"name": "S1", "bins": ["Nghi lễ", "Khác"], "start": 0, "end": 99999}]
        spec = [("a%d" % i, 0, "Nghi lễ", 1, i, 30) for i in range(4)] + [("b%d" % i, 0, "Khác", 1, 50 + i, 30) for i in range(4)]
        r = td.build(*mk(spec, stages=stages, shoot_style="traditional", durations={"target_min": 5, "stage_s": {"S1": 150}}))
        s1 = r["stages"][0]
        self.assertAlmostEqual(s1["total_s"], 135.0, delta=0.5)
        self.assertEqual({round(i["dur"], 1) for i in r["items"]}, {27.0})


class GoiY(unittest.TestCase):
    def test_trang_thai_ok_short_over_no_star(self):
        self.assertEqual(td.build(*scene())["state"], "ok")
        self.assertEqual(td.build(*scene(durations={"target_min": 10}))["state"], "short")
        self.assertEqual(td.build(*mk([("a", 0, "Decor", 0, 1, 20)], stages=STAGES))["state"], "no_star")
        r = td.build(*scene(durations={"target_min": 1.0, "bins": {"S1": {"Nghi lễ": [80, 90]}, "S2": {"Nghi lễ": [50, 60]}, "S3": {"Nghi lễ": [30, 40]}}}))
        self.assertEqual(r["state"], "over")

    def short_scene(self, locked=()):
        # anh chốt S1 chỉ 20 s (còn 70 s clip sao dư); S2, S3 chỉ có 60 + 40 s => tổng 120 s, thiếu 60 s so với 180 s
        return scene(durations={"stage_s": {"S1": 20}, "locked": list(locked)})

    def test_goi_y_a_tu_keo_them_cho_du_ra_dung_so(self):
        plan, clips, assign, st = self.short_scene()
        r = td.build(plan, clips, assign, st)
        self.assertEqual(r["state"], "short")
        self.assertAlmostEqual(r["total_s"], 120.0, delta=1.0)
        adv = td.advise(plan, clips, assign, st, r)
        self.assertIn("S2 đã kéo hết cỡ (chỉ có 1:00 clip sao).", adv["reasons"])
        self.assertTrue(any(t.startswith("S1 còn dư 1:10") for t in adv["reasons"]))
        self.assertIsNotNone(adv["rebalance"])
        self.assertEqual(adv["rebalance"]["title"], "Tự kéo thêm cho đủ 3:00")
        self.assertIn("S1 +", adv["rebalance"]["text"])
        d, r2 = td.plan_rebalance(plan, clips, assign, st, r)
        self.assertEqual(r2["state"], "ok")
        self.assertAlmostEqual(r2["total_s"], 180.0, delta=3.0)
        self.assertNotIn("S1", d.get("stage_s", {}))                                   # bỏ chốt: S1 co giãn lấy phần thiếu
        self.assertGreater(stg(r2, 1)["total_s"], 55.0)                                # S2 gần hết cỡ

    def test_goi_y_a_giu_nguyen_giai_doan_khoa(self):
        plan, clips, assign, st = scene(durations={"stage_s": {"S1": 20, "S2": 10}, "locked": ["S1"]})
        r = td.build(plan, clips, assign, st)
        d, r2 = td.plan_rebalance(plan, clips, assign, st, r)
        self.assertAlmostEqual(d["stage_s"]["S1"], 20.0)                                # khóa: không đổi
        self.assertNotIn("S2", d["stage_s"])                                           # chưa khóa: thả cho co giãn
        self.assertAlmostEqual(stg(r2, 0)["total_s"], 20.0, delta=0.2)
        self.assertAlmostEqual(stg(r2, 1)["total_s"], 60.0, delta=0.2)
        self.assertEqual(r2["state"], "short")                                         # S1 khóa 20 s nên vẫn thiếu
        adv = td.advise(plan, clips, assign, st, r)
        self.assertIn("Vẫn còn thiếu", adv["rebalance"]["text"])
        self.assertIn("giữ nguyên", adv["rebalance"]["text"])

    def test_tat_ca_khoa_thi_khong_co_goi_y_a(self):
        plan, clips, assign, st = self.short_scene(locked=["S1"])
        self.assertIsNone(td.plan_rebalance(plan, clips, assign, st))

    def test_goi_y_b_ha_muc_tieu_bang_so_hien_tai(self):
        plan, clips, assign, st = self.short_scene()
        r = td.build(plan, clips, assign, st)
        adv = td.advise(plan, clips, assign, st, r)
        self.assertEqual(adv["lower"]["title"], "Hạ mục tiêu xuống " + td.mmss(r["total_s"]))
        d, r2 = td.plan_lower_target(plan, clips, assign, st, r)
        self.assertAlmostEqual(d["target_min"] * 60, r["total_s"], delta=0.6)
        self.assertEqual(r2["state"], "ok")
        self.assertEqual(r2["n_used"], r["n_used"])

    def test_goi_y_c_mo_bin_con_clip_chua_sao(self):
        plan, clips, assign, st = scene(durations={"target_min": 5})
        extra = clip("u1", 30, 900)
        clips.append(extra)
        assign["u1"] = 2
        plan["labels"][extra.rel] = {"uid": "u1", "stage": "S3", "bin": "Nghi lễ", "by": "nguoi"}
        r = td.build(plan, clips, assign, st)
        adv = td.advise(plan, clips, assign, st, r)
        self.assertEqual((adv["step3"]["stage"], adv["step3"]["bin"]), (2, "Nghi lễ"))
        self.assertIn("S3 còn 0:05", adv["step3"]["text"])
        adv = td.advise(*scene(), td.build(*scene()))
        self.assertEqual((adv["state"], adv["rebalance"], adv["lower"], adv["step3"]), ("ok", None, None, None))

    def test_tong_clip_sao_it_hon_muc_tieu_chi_con_ha_muc_tieu_va_buoc_3(self):
        plan, clips, assign, st = scene(durations={"target_min": 10})
        adv = td.advise(plan, clips, assign, st, td.build(plan, clips, assign, st))
        self.assertIsNone(adv["rebalance"])
        self.assertIsNotNone(adv["lower"])
        self.assertTrue(adv["reasons"][0].startswith("Mọi giai đoạn đã kéo hết cỡ"))


class TinhChat(unittest.TestCase):
    def test_build_khong_ghi_vao_ke_hoach_va_khoa_cu_bi_bo_qua(self):
        plan, clips, assign, st = scene(durations={"stage_share": {"S1": 0.9, "S2": 0.05, "S3": 0.05}})
        before = repr(plan)
        r = td.build(plan, clips, assign, st)
        self.assertEqual(repr(plan), before)
        self.assertFalse(any(stg(r, i)["pinned"] for i in range(3)))

    def test_gia_tri_hong_trong_file_bi_bo_qua(self):
        r = td.build(*scene(durations={"stage_s": {"S1": "x", "S2": -5, "S3": float("nan")}, "locked": "hỏng", "bin_s": {"S1": {"Nghi lễ": "x"}, "S2": 5}}))
        self.assertFalse(any(stg(r, i)["pinned"] for i in range(3)))
        self.assertIsNone(stg(r, 0)["bins"][0]["pin"])

    def test_module_van_thuan(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_dur.py"), encoding="utf-8") as f:
            src = f.read()
        for bad in ("troly_resolve", "CreateTimeline", "SetMarkInOut", "os.remove", "subprocess"):
            self.assertNotIn(bad, src, bad)


if __name__ == "__main__":
    unittest.main()
