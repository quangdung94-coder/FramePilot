"""Bước 5 Thời lượng (ADR-0013): chia thời lượng, cắt gọt, các trường hợp biên. Dữ liệu giả, tên ví dụ LV_Ten."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import troly_core as tc               # noqa: E402
import troly_dur as td                # noqa: E402

T0 = datetime.datetime(2026, 10, 17, 8, 0, 0)


def clip(uid, dur=20.0, minute=0, rel=None):
    return tc.Clip(uid=uid, name=uid, dur=dur, fps=50.0, frames=int(dur * 50), t_start=T0 + datetime.timedelta(minutes=minute),
                   rel=rel or "01_footage/%s.MP4" % uid)


def mk(spec, stages=None, **plan_extra):
    """spec = [(uid, giai đoạn, bin, mức sao, phút, dur)] -> (plan, clips, assign, stages)."""
    stages = stages or [{"name": "S1", "bins": ["Decor", "Beauty cô dâu", "Nghi lễ", "Khác"], "start": 0, "end": 99999},
                        {"name": "S2", "bins": ["Nghi lễ", "Khác"], "start": 0, "end": 99999}]
    plan = tc.new_plan("2026.10.17.LV_Ten")
    plan["stages"] = stages
    plan.update(plan_extra)
    clips, assign = [], {}
    for uid, si, b, lv, minute, dur in spec:
        c = clip(uid, dur, minute)
        clips.append(c)
        assign[uid] = si
        if lv:
            plan["stars"][c.rel] = True if lv is True or lv == 1 else lv
        if b:
            plan["labels"][c.rel] = {"uid": uid, "stage": stages[si]["name"], "bin": b, "by": "nguoi"}
    return plan, clips, assign, stages


def total(r):
    return sum(i["dur"] for i in r["items"])


def binrow(r, stage, name):
    return next(b for s in r["stages"] if s["name"] == stage for b in s["bins"] if b["name"] == name)


def kinds(r):
    return [w["kind"] for w in r["warnings"]]


class Defaults(unittest.TestCase):
    def test_de_xuat_decor_10_20_beauty_20_30_va_bin_khac_tu_suy_ra(self):
        plan, clips, assign, st = mk([("a", 0, "Decor", 1, 1, 20)])
        r = td.build(plan, clips, assign, st)
        self.assertEqual((binrow(r, "S1", "Decor")["min"], binrow(r, "S1", "Decor")["max"]), (10.0, 20.0))
        self.assertEqual((binrow(r, "S1", "Beauty cô dâu")["min"], binrow(r, "S1", "Beauty cô dâu")["max"]), (20.0, 30.0))
        plan, clips, assign, st = mk([("n%d" % i, 0, "Nghi lễ", 1, i, 30) for i in range(6)])
        r = td.build(plan, clips, assign, st)
        nl = binrow(r, "S1", "Nghi lễ")
        self.assertEqual(nl["natural_s"], 30.0)                          # 6 clip × 5 s (bảng quy tắc Bước 3: Nghi lễ 2,5–5)
        self.assertEqual((nl["min"], nl["max"]), (18.0, 30.0))           # Min 0,6 × tự nhiên, Max = tự nhiên (tối đa 90)
        self.assertFalse(nl["edited"])
        self.assertEqual(binrow(r, "S1", "Khác")["max"], 0.0)            # bin không có clip sao: 0-0

    def test_muc_tieu_mac_dinh_12_phut_va_khong_co_khoa_trong_ke_hoach(self):
        plan, clips, assign, st = mk([("a", 0, "Decor", 1, 1, 20)])
        r = td.build(plan, clips, assign, st)
        self.assertEqual(r["target_min"], 12.0)
        self.assertNotIn("durations", plan)                              # build không tự ghi khóa vào kế hoạch


class Short(unittest.TestCase):
    def test_bin_thieu_min_chi_canh_bao_khong_tu_them_clip_chua_sao(self):
        plan, clips, assign, st = mk([("a", 0, "Beauty cô dâu", 1, 1, 20), ("b", 0, "Beauty cô dâu", 0, 2, 20), ("c", 0, "Beauty cô dâu", 0, 3, 20)])
        r = td.build(plan, clips, assign, st)
        self.assertEqual([i["uid"] for i in r["items"]], ["a"])           # chỉ clip có sao
        self.assertIn("bin_short", kinds(r))
        self.assertLess(total(r), 20.0)

    def test_chua_co_sao_nao(self):
        plan, clips, assign, st = mk([("a", 0, "Decor", 0, 1, 20)])
        r = td.build(plan, clips, assign, st)
        self.assertEqual(r["items"], [])
        self.assertIn("no_star", kinds(r))
        self.assertEqual(r["total_s"], 0.0)

    def test_khong_co_clip_nao(self):
        plan, clips, assign, st = mk([])
        r = td.build(plan, clips, assign, st)
        self.assertEqual((r["items"], r["n_used"], r["total_s"]), ([], 0, 0.0))
        self.assertAlmostEqual(sum(r["shares"]), 1.0)


class Over(unittest.TestCase):
    def test_vuot_max_bo_clip_it_uu_tien_nhat_khi_khong_the_rut(self):
        # Decor: quy tắc cố định 3 s (không rút được); 8 clip = 24 s > Max 20 -> bỏ 2 clip (mức sao thấp, rồi quay muộn)
        spec = [("d%d" % i, 0, "Decor", 2 if i in (6, 7) else 1, i, 20) for i in range(8)]
        r = td.build(*mk(spec))
        kept = [i["uid"] for i in r["items"]]
        self.assertEqual(len(kept), 6)
        self.assertLessEqual(binrow(r, "S1", "Decor")["total_s"], 20.0)
        self.assertIn("d6", kept)                                         # sao cao được giữ
        self.assertIn("d7", kept)
        self.assertEqual(binrow(r, "S1", "Decor")["dropped"], 2)
        self.assertIn("bin_over", kinds(r))
        self.assertEqual(kept, sorted(kept, key=lambda u: int(u[1:])))     # vẫn đúng thứ tự giờ quay

    def test_rut_in_out_khong_bao_gio_duoi_do_dai_toi_thieu(self):
        # Nghi lễ 2,5–5: 6 clip dài = 30 s; Max do anh đặt 20 s -> rút còn ~3,3 s mỗi clip, không bỏ clip nào
        spec = [("n%d" % i, 0, "Nghi lễ", 1, i, 30) for i in range(6)]
        plan = mk(spec, durations={"target_min": 12, "bins": {"S1": {"Nghi lễ": [10, 20]}}})
        r = td.build(*plan)
        self.assertEqual(len(r["items"]), 6)
        self.assertLessEqual(total(r), 20.0 + 1e-6)
        self.assertGreater(total(r), 19.0)
        self.assertTrue(all(i["dur"] >= 2.5 for i in r["items"]))
        # Max thấp tới mức không đủ 6 × 2,5 s = 15 s -> phải bỏ clip, phần còn lại vẫn >= 2,5 s
        plan = mk(spec, durations={"target_min": 12, "bins": {"S1": {"Nghi lễ": [5, 10]}}})
        r = td.build(*plan)
        self.assertLessEqual(len(r["items"]), 4)
        self.assertTrue(all(i["dur"] >= 2.5 for i in r["items"]))
        self.assertLessEqual(total(r), 10.0 + 1e-6)

    def test_in_out_dat_tay_thang_va_khong_bi_rut(self):
        spec = [("n%d" % i, 0, "Nghi lễ", 1, i, 30) for i in range(3)]
        plan, clips, assign, st = mk(spec, durations={"bins": {"S1": {"Nghi lễ": [1, 16]}}})
        plan["inout"] = {clips[0].rel: [2.0, 12.0]}                       # anh đặt tay 10 s
        r = td.build(plan, clips, assign, st)
        n0 = next(i for i in r["items"] if i["uid"] == "n0")
        self.assertEqual((n0["in_s"], n0["out_s"]), (2.0, 12.0))
        self.assertTrue(n0["fixed"])

    def test_truyen_thong_chi_bo_clip_khong_rut(self):
        spec = [("t%d" % i, 0, "Nghi lễ", 1, i, 30) for i in range(4)]
        plan, clips, assign, st = mk(spec, shoot_style="traditional", durations={"bins": {"S1": {"Nghi lễ": [10, 70]}}})
        r = td.build(plan, clips, assign, st)
        self.assertEqual({round(i["dur"], 1) for i in r["items"]}, {27.0})   # 30 s bớt 1,5 s đầu và cuối như Bước 3
        self.assertEqual(len(r["items"]), 2)                                  # Max 70 s: chỉ vừa 2 clip 27 s (3 clip = 81 s)


class Target(unittest.TestCase):
    def spec(self):
        return [("a%d" % i, 0, "Nghi lễ", 1, i, 30) for i in range(10)] + [("b%d" % i, 1, "Nghi lễ", 1, 100 + i, 30) for i in range(10)]

    def test_muc_tieu_qua_nho_tong_khong_vuot_va_clip_giu_do_dai_toi_thieu(self):
        plan = mk(self.spec(), durations={"target_min": 1})                # 60 giây cho 100 giây nội dung
        r = td.build(*plan)
        self.assertLessEqual(total(r), 60.0 + 1.0)
        self.assertTrue(all(i["dur"] >= 2.5 for i in r["items"]))
        self.assertAlmostEqual(sum(s["budget_s"] for s in r["stages"]), 60.0, places=0)

    def test_muc_tieu_qua_lon_chi_canh_bao_thieu_khong_them_clip(self):
        plan = mk(self.spec(), durations={"target_min": 120})
        r = td.build(*plan)
        self.assertEqual(len(r["items"]), 20)
        self.assertIn("target_short", kinds(r))
        self.assertLess(r["total_s"], r["target_s"])
        self.assertLess(r["delta_s"], 0)

    def test_muc_tieu_hop_le_khong_canh_bao_thieu(self):
        plan = mk(self.spec(), durations={"target_min": 1.5})
        r = td.build(*plan)
        self.assertNotIn("target_short", kinds(r))
        self.assertAlmostEqual(r["total_s"], 90.0, delta=2.0)

    def test_nhap_muc_tieu_sai_bi_chan_va_ngoai_khoang_goi_y_chi_nhac(self):
        for bad in ("abc", None, 0, -5, 500, float("nan")):
            self.assertFalse(td.check_target(bad)[0], bad)
        self.assertEqual(td.check_target("12")[1], 12.0)
        r = td.build(*mk(self.spec(), durations={"target_min": 20}))
        self.assertIn("target_range", kinds(r))
        plan = mk(self.spec(), durations={"target_min": "hỏng"})            # giá trị hỏng trong file: dùng mặc định 12
        self.assertEqual(td.build(*plan)["target_min"], 12.0)

    def test_ti_le_giai_doan_tong_luon_bang_1_va_theo_anh_keo(self):
        plan = mk(self.spec(), durations={"target_min": 1.5, "stage_share": {"S1": 0.8, "S2": 0.2}})
        r = td.build(*plan)
        self.assertAlmostEqual(sum(r["shares"]), 1.0)
        self.assertAlmostEqual(r["stages"][0]["share"], 0.8)
        self.assertAlmostEqual(r["stages"][0]["budget_s"], 72.0, places=0)
        v = td.normalize_shares([0.5, 0.3, 0.2], 0, 0.7)
        self.assertAlmostEqual(sum(v), 1.0)
        self.assertAlmostEqual(v[0], 0.7)
        self.assertAlmostEqual(v[1] / v[2], 1.5)
        v = td.normalize_shares([0.5, 0.5], 1, 1.0)                          # không cho giai đoạn khác về 0
        self.assertGreaterEqual(min(v), td.MIN_STAGE_SHARE - 1e-9)
        self.assertAlmostEqual(sum(v), 1.0)

    def test_tong_min_vuot_phan_chia_thi_canh_bao(self):
        plan = mk(self.spec(), durations={"target_min": 1.5, "stage_share": {"S1": 0.05, "S2": 0.95},
                                          "bins": {"S1": {"Nghi lễ": [40, 50]}}})
        r = td.build(*plan)
        self.assertIn("stage_over", kinds(r))


class OrderAndEdges(unittest.TestCase):
    def test_thu_tu_giai_doan_roi_gio_quay_thuc_va_loai_clip_ngoai_giai_doan(self):
        spec = [("x", 1, "Nghi lễ", 1, 5, 20), ("y", 0, "Decor", 1, 50, 20), ("z", 0, "Decor", 1, 10, 20), ("o", None, None, 1, 1, 20)]
        plan, clips, assign, st = mk([s for s in spec if s[1] is not None])
        out = clip("o", 20, 1)
        clips.append(out)
        plan["stars"][out.rel] = True
        r = td.build(plan, clips, assign, st)
        self.assertEqual([i["uid"] for i in r["items"]], ["z", "y", "x"])
        self.assertEqual(r["n_excluded"], 1)
        self.assertIn("excluded", kinds(r))

    def test_clip_chua_xep_bin_van_vao_nhom_chua_xep(self):
        r = td.build(*mk([("u", 0, None, 1, 1, 20)]))
        self.assertEqual(len(r["items"]), 1)
        self.assertEqual(r["items"][0]["bin"], td.UNSORTED)

    def test_min_max_cua_anh_hop_le_moi_duoc_dung(self):
        self.assertEqual(td.check_bin_minmax(10, 20), (True, (10.0, 20.0)))
        for bad in ((30, 20), (-1, 5), ("a", 5), (1, "x"), (0, 99999), (float("nan"), 1)):
            self.assertFalse(td.check_bin_minmax(*bad)[0], bad)
        plan = mk([("a", 0, "Decor", 1, 1, 20)], durations={"bins": {"S1": {"Decor": [30, 20]}}})   # file hỏng: bỏ qua, dùng mặc định
        r = td.build(*plan)
        self.assertEqual((binrow(r, "S1", "Decor")["min"], binrow(r, "S1", "Decor")["max"], binrow(r, "S1", "Decor")["edited"]), (10.0, 20.0, False))

    def test_clip_rat_ngan_duoi_1_giay_lay_nguyen_clip_va_out_khong_vuot_do_dai(self):
        r = td.build(*mk([("s", 0, "Decor", 1, 1, 0.6), ("l", 0, "Decor", 1, 2, 2.0)]))
        s = next(i for i in r["items"] if i["uid"] == "s")
        self.assertEqual((s["in_s"], s["out_s"]), (0.0, 0.6))
        for i in r["items"]:
            self.assertLessEqual(i["out_s"], 20.0)
            self.assertGreater(i["out_s"], i["in_s"])

    def test_sao_nhieu_muc_uu_tien_cao_duoc_giu(self):
        spec = [("p%d" % i, 0, "Decor", 3 if i == 0 else 1, i, 20) for i in range(8)]
        r = td.build(*mk(spec))
        self.assertIn("p0", [i["uid"] for i in r["items"]])                   # p0 quay sớm nhất nhưng mức sao cao nhất; bị bỏ là clip quay muộn mức thấp
        self.assertNotIn("p7", [i["uid"] for i in r["items"]])


class PureAndSafe(unittest.TestCase):
    def test_module_thuan_khong_goi_davinci(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_dur.py"), encoding="utf-8") as f:
            src = f.read()
        for bad in ("troly_resolve", "CreateTimeline", "SetMarkInOut", "open(", "os.remove", "subprocess"):
            self.assertNotIn(bad, src, bad)
        self.assertNotIn("đã duyệt", src.lower().replace("chưa được người dựng xác nhận", ""))


if __name__ == "__main__":
    unittest.main()
