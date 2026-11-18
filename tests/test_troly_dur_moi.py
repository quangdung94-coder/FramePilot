"""Bước 5 làm lại (ADR-0013, bản 18/11/2026): mỗi giai đoạn một số giây, khóa/gõ số làm giai đoạn khác co giãn, không vượt clip sao có,
tự tính lại khi sửa, gợi ý (a)(b)(c). Dữ liệu giả, tên ví dụ LV_Ten."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import troly_dur as td                # noqa: E402
from test_troly_dur import mk         # noqa: E402

STAGES = [{"name": "S%d" % i, "bins": ["Nghi lễ"], "start": 0, "end": 99999} for i in (1, 2, 3)]


def scene(n1=18, n2=12, n3=8, **extra):
    """S1 có n1 clip sao (mỗi clip 5 s theo quy tắc Nghi lễ) ..., mục tiêu mặc định 3:00 = 180 s."""
    spec = []
    for si, n in enumerate((n1, n2, n3)):
        spec += [("s%d_%d" % (si, i), si, "Nghi lễ", 1, si * 100 + i, 30) for i in range(n)]
    d = {"target_min": 3}
    d.update(extra.pop("durations", {}))
    return mk(spec, stages=STAGES, durations=d, **extra)


def stg(r, i):
    return r["stages"][i]


class Chia(unittest.TestCase):
    def test_khong_khoa_chia_theo_ti_le_clip_sao_co(self):
        r = td.build(*scene())
        self.assertEqual([stg(r, i)["avail_s"] for i in range(3)], [90.0, 60.0, 40.0])
        self.assertAlmostEqual(stg(r, 0)["budget_s"], 180 * 90 / 190, delta=0.2)
        self.assertAlmostEqual(sum(stg(r, i)["budget_s"] for i in range(3)), 180.0, delta=0.5)
        self.assertEqual(r["state"], "ok")
        self.assertFalse(any(stg(r, i)["pinned"] for i in range(3)))

    def test_khoa_mot_giai_doan_cac_giai_doan_khac_co_gian(self):
        r = td.build(*scene(durations={"stage_s": {"S1": 80}, "locked": ["S1"]}))
        self.assertAlmostEqual(stg(r, 0)["budget_s"], 80.0)
        self.assertTrue(stg(r, 0)["locked"])
        self.assertAlmostEqual(stg(r, 1)["budget_s"] / stg(r, 2)["budget_s"], 60.0 / 40.0, places=1)   # theo tỉ lệ clip sao còn lại
        self.assertAlmostEqual(r["total_s"], 180.0, delta=1.0)

    def test_khoa_hai_giai_doan_giai_doan_con_lai_nhan_phan_du(self):
        r = td.build(*scene(durations={"stage_s": {"S1": 30, "S2": 20}, "locked": ["S1", "S2"]}))
        self.assertAlmostEqual(stg(r, 2)["budget_s"], 40.0)                # chỉ có 40 s clip sao: KHÔNG vượt dù còn 130 s trống
        self.assertEqual(r["state"], "short")
        self.assertAlmostEqual(r["total_s"], 90.0, delta=1.0)
        self.assertAlmostEqual(r["delta_s"], -90.0, delta=1.0)

    def test_go_so_vao_mot_giai_doan_thanh_anh_chot_con_lai_co_gian(self):
        r = td.build(*scene(durations={"stage_s": {"S2": 55}}))
        self.assertTrue(stg(r, 1)["pinned"])
        self.assertFalse(stg(r, 1)["locked"])                              # gõ số = chốt, chưa phải khóa
        self.assertAlmostEqual(stg(r, 1)["budget_s"], 55.0)
        self.assertAlmostEqual(stg(r, 0)["budget_s"] + stg(r, 2)["budget_s"], 125.0, delta=0.5)
        self.assertAlmostEqual(stg(r, 0)["budget_s"] / stg(r, 2)["budget_s"], 90.0 / 40.0, places=1)

    def test_khong_vuot_qua_clip_sao_co_phan_thua_chia_tiep(self):
        # S3 chỉ có 40 s; mục tiêu rất lớn -> mọi giai đoạn giữ hết, không bịa clip, báo thiếu
        r = td.build(*scene(durations={"target_min": 10}))
        for i, av in enumerate((90.0, 60.0, 40.0)):
            self.assertAlmostEqual(stg(r, i)["budget_s"], av)
            self.assertEqual(stg(r, i)["dropped_n"], 0)
        self.assertEqual(r["n_used"], 38)
        self.assertEqual(r["state"], "short")

    def test_allocate_thuan(self):
        self.assertEqual(td.allocate_stages(100, [50, 50], {}), [50.0, 50.0])
        self.assertEqual(td.allocate_stages(40, [50, 50], {0: 10}), [10.0, 30.0])
        b = td.allocate_stages(100, [10, 100, 100], {})                          # chia theo tỉ lệ clip có
        self.assertAlmostEqual(b[0], 100 * 10 / 210)
        self.assertAlmostEqual(sum(b), 100.0)
        self.assertEqual(td.allocate_stages(500, [10, 100, 100], {}), [10.0, 100.0, 100.0])   # mục tiêu quá lớn: mỗi giai đoạn chỉ tới số clip có
        self.assertEqual(td.allocate_stages(100, [0, 0], {}), [0.0, 0.0])
        self.assertEqual(td.allocate_stages(100, [30, 30], {0: 500}), [500.0, 0.0])     # chốt quá mục tiêu: phần còn lại về 0

    def test_sua_min_max_bin_tinh_lai_ngay(self):
        r0 = td.build(*scene(durations={"target_min": 1.0}))                     # 60 s: S1 ~28 s
        b0 = stg(r0, 0)["bins"][0]
        r1 = td.build(*scene(durations={"target_min": 1.0, "bins": {"S1": {"Nghi lễ": [10, 20]}}}))
        b1 = stg(r1, 0)["bins"][0]
        self.assertTrue(b1["edited"])
        self.assertLessEqual(b1["total_s"], 20.0 + 1e-6)
        self.assertLess(b1["total_s"], b0["total_s"] + 1e-6)
        self.assertEqual(stg(r1, 0)["avail_s"], 20.0)                            # Max thấp hơn thì clip sao "có" cho giai đoạn cũng thấp hơn
        self.assertNotEqual(r0["items"], r1["items"])

    def test_truyen_thong_chi_bo_nguyen_clip_giu_lech_vai_giay(self):
        r = td.build(*scene(shoot_style="traditional", durations={"target_min": 1.5}))
        lens = {i["dur"] for i in r["items"]}
        self.assertEqual(lens, {27.0})                                            # clip dài 30 s bớt 1,5 s đầu và đuôi, KHÔNG rút ngắn thêm
        self.assertTrue(all(stg(r, i)["total_s"] % 27.0 < 1e-6 for i in range(3)))
        for i in range(3):
            self.assertLessEqual(stg(r, i)["total_s"], stg(r, i)["budget_s"] + 1e-6)

    def test_bo_clip_it_uu_tien_va_ghi_ten_clip_bo(self):
        r = td.build(*scene(durations={"target_min": 3.0, "stage_s": {"S1": 40}}))
        s1 = stg(r, 0)
        self.assertGreater(s1["dropped_n"], 0)
        self.assertEqual(len(s1["dropped_clips"]), s1["dropped_n"])
        self.assertTrue(all(c["name"].endswith(".MP4") for c in s1["dropped_clips"]))
        self.assertAlmostEqual(s1["natural_s"] - s1["total_s"], s1["dropped_s"], delta=0.11)


class TruyenThong(unittest.TestCase):
    def test_clip_sao_co_the_cho_la_so_nguyen_clip_vua_max(self):
        spec = [("t%d" % i, 0, "Nghi lễ", 1, i, 30) for i in range(4)]
        r = td.build(*mk(spec, shoot_style="traditional", durations={"bins": {"S1": {"Nghi lễ": [10, 70]}}}))
        b = r["stages"][0]["bins"][2]
        self.assertEqual(b["avail_s"], 54.0)                                       # 2 clip x 27 s vừa Max 70 s; không phải 70
        self.assertEqual(r["stages"][0]["avail_s"], 54.0)

    def test_bu_lai_so_du_do_bo_nguyen_clip(self):
        stages = [{"name": "S1", "bins": ["Nghi lễ", "Khác"], "start": 0, "end": 99999}]
        spec = [("a%d" % i, 0, "Nghi lễ", 1, i, 30) for i in range(4)] + [("b%d" % i, 0, "Khác", 1, 50 + i, 30) for i in range(4)]
        r = td.build(*mk(spec, stages=stages, shoot_style="traditional", durations={"target_min": 5, "stage_s": {"S1": 150}}))
        s1 = r["stages"][0]
        self.assertAlmostEqual(s1["total_s"], 135.0)                                # 5 clip x 27 s: bù thêm 1 clip, lệch dưới 1 clip so với 150 s
        self.assertLessEqual(s1["total_s"], s1["budget_s"] + 1e-6)
        self.assertEqual({round(i["dur"], 1) for i in r["items"]}, {27.0})          # vẫn không rút ngắn clip nào
        self.assertEqual(s1["dropped_n"], 3)


class GoiY(unittest.TestCase):
    def test_trang_thai_ok_short_over_no_star(self):
        self.assertEqual(td.build(*scene())["state"], "ok")
        self.assertEqual(td.build(*scene(durations={"target_min": 10}))["state"], "short")
        self.assertEqual(td.build(*mk([("a", 0, "Decor", 0, 1, 20)], stages=STAGES))["state"], "no_star")
        r = td.build(*scene(durations={"target_min": 1.0, "bins": {"S1": {"Nghi lễ": [80, 90]}, "S2": {"Nghi lễ": [50, 60]}, "S3": {"Nghi lễ": [30, 40]}}}))
        self.assertEqual(r["state"], "over")                                       # tổng Min vượt mục tiêu

    def short_scene(self, locked=()):
        # S3 anh gõ 80 s nhưng chỉ có 40 s clip sao; S1, S2 chia 100 s -> giữ 60 + 40 + 40 = 140 s, thiếu 40 s
        return scene(durations={"stage_s": {"S3": 80}, "locked": list(locked)})

    def test_goi_y_a_chia_lai_cho_du_ra_dung_so(self):
        plan, clips, assign, st = self.short_scene()
        r = td.build(plan, clips, assign, st)
        self.assertEqual(r["state"], "short")
        self.assertAlmostEqual(r["delta_s"], -40.0, delta=1.0)
        adv = td.advise(plan, clips, assign, st, r)
        self.assertIsNotNone(adv["rebalance"])
        self.assertIn("S3 −0:40", adv["rebalance"]["text"])
        d, r2 = td.plan_rebalance(plan, clips, assign, st, r)
        self.assertAlmostEqual(r2["total_s"], 180.0, delta=3.0)                    # đủ mục tiêu sau khi chia lại (làm tròn 0,1 s từng clip)
        self.assertEqual(r2["state"], "ok")
        self.assertAlmostEqual(d["stage_s"]["S3"], 40.0)                           # hạ số chốt bằng số clip có
        self.assertGreater(stg(r2, 0)["budget_s"], stg(r, 0)["budget_s"])         # phần thiếu dồn sang giai đoạn còn dư
        self.assertEqual(sum(1 for t in adv["reasons"] if "S3 chỉ có 0:40" in t), 1)

    def test_goi_y_a_giu_nguyen_giai_doan_khoa(self):
        plan, clips, assign, st = scene(durations={"stage_s": {"S1": 60, "S3": 80}, "locked": ["S1"]})
        r = td.build(plan, clips, assign, st)
        d, r2 = td.plan_rebalance(plan, clips, assign, st, r)
        self.assertAlmostEqual(d["stage_s"]["S1"], 60.0)                           # khóa: không đổi
        self.assertAlmostEqual(stg(r2, 0)["budget_s"], 60.0)
        self.assertAlmostEqual(stg(r2, 2)["budget_s"], 40.0)
        self.assertAlmostEqual(stg(r2, 1)["budget_s"], 60.0)                       # chỉ S2 có clip dư: 60 s (hết clip), tổng 160, báo còn thiếu
        self.assertEqual(r2["state"], "short")
        adv = td.advise(plan, clips, assign, st, r)
        self.assertIn("Vẫn còn thiếu", adv["rebalance"]["text"])
        self.assertIn("giữ nguyên", adv["rebalance"]["text"])

    def test_khoa_thi_khong_hat_so_khoa_xuong_bang_a(self):
        plan, clips, assign, st = self.short_scene(locked=["S3"])                  # S3 khóa 80 s dù chỉ có 40 s
        self.assertIsNone(td.plan_rebalance(plan, clips, assign, st))

    def test_goi_y_b_ha_muc_tieu_bang_so_dang_giu(self):
        plan, clips, assign, st = self.short_scene()
        r = td.build(plan, clips, assign, st)
        adv = td.advise(plan, clips, assign, st, r)
        self.assertEqual(adv["lower"]["title"], "Hạ mục tiêu xuống " + td.mmss(r["total_s"]))
        self.assertIn(td.mmss(r["total_s"]), ("2:19", "2:20"))
        d, r2 = td.plan_lower_target(plan, clips, assign, st, r)
        self.assertAlmostEqual(d["target_min"] * 60, r["total_s"], delta=0.6)
        self.assertEqual(r2["state"], "ok")
        self.assertAlmostEqual(r2["total_s"], r["total_s"], delta=1.0)
        self.assertEqual(r2["n_used"], r["n_used"])                                # giữ hết clip, không đổi số clip

    def test_goi_y_c_mo_bin_con_clip_chua_sao(self):
        plan, clips, assign, st = scene(n3=8, durations={"target_min": 5})
        from test_troly_dur import clip
        extra = clip("u1", 30, 900)
        clips.append(extra)
        assign["u1"] = 2
        plan["labels"][extra.rel] = {"uid": "u1", "stage": "S3", "bin": "Nghi lễ", "by": "nguoi"}
        r = td.build(plan, clips, assign, st)
        adv = td.advise(plan, clips, assign, st, r)
        self.assertEqual((adv["step3"]["stage"], adv["step3"]["bin"]), (2, "Nghi lễ"))
        self.assertIn("S3 còn 0:05", adv["step3"]["text"])
        # đạt mục tiêu: không còn gợi ý
        adv = td.advise(*scene(), td.build(*scene()))
        self.assertEqual((adv["state"], adv["rebalance"], adv["lower"], adv["step3"]), ("ok", None, None, None))

    def test_khong_gioi_thieu_gi_thua_khi_khong_the_chia_lai(self):
        plan, clips, assign, st = scene(durations={"target_min": 10})              # tổng clip sao ít hơn mục tiêu: không giai đoạn nào còn dư
        adv = td.advise(plan, clips, assign, st, td.build(plan, clips, assign, st))
        self.assertIsNone(adv["rebalance"])
        self.assertIsNotNone(adv["lower"])


class TinhChat(unittest.TestCase):
    def test_build_khong_ghi_vao_ke_hoach_va_khoa_cu_stage_share_vo_hai(self):
        plan, clips, assign, st = scene(durations={"stage_share": {"S1": 0.9, "S2": 0.05, "S3": 0.05}})
        before = repr(plan)
        r = td.build(plan, clips, assign, st)
        self.assertEqual(repr(plan), before)
        self.assertFalse(any(stg(r, i)["pinned"] for i in range(3)))              # khóa cũ bị bỏ qua

    def test_gia_tri_hong_trong_file_bi_bo_qua(self):
        r = td.build(*scene(durations={"stage_s": {"S1": "x", "S2": -5, "S3": float("nan")}, "locked": "hỏng"}))
        self.assertFalse(any(stg(r, i)["pinned"] for i in range(3)))

    def test_module_van_thuan(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_dur.py"), encoding="utf-8") as f:
            src = f.read()
        for bad in ("troly_resolve", "CreateTimeline", "SetMarkInOut", "os.remove", "subprocess"):
            self.assertNotIn(bad, src, bad)


if __name__ == "__main__":
    unittest.main()
