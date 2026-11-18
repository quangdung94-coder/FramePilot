"""Bước 5 bản 3 (ADR-0013): timeline kéo thả. RA TIMELINE khi Slow, Slow mượt tự tính (fps), mẹ áp con / con thắng mẹ, thứ tự cụm/khối, V1/V2,
đọc lại kiểm V1 liền nhau, tắt tiếng. Dữ liệu giả, tên ví dụ LV_Ten."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import troly_core as tc               # noqa: E402
import troly_dur as td                # noqa: E402
import troly_tl as ttl                # noqa: E402

T0 = datetime.datetime(2026, 10, 17, 8, 0, 0)
STAGES = [{"name": "Chuẩn bị", "bins": ["Decor", "Beauty cô dâu", "Chú rể"], "start": 0, "end": 99999},
          {"name": "Đón khách", "bins": ["Đón khách"], "start": 0, "end": 99999}]


def clip(uid, minute, fps=50.0, dur=30.0):
    return tc.Clip(uid=uid, name=uid, dur=dur, fps=fps, frames=int(dur * fps), t_start=T0 + datetime.timedelta(minutes=minute),
                   rel="01_footage/%s.MP4" % uid)


def scene(spec, tl=None, durations=None, **extra):
    """spec = [(uid, giai đoạn, bin, phút, fps)] -> (plan, clips, assign, stages); mỗi clip dài 30 s, 1 sao."""
    plan = tc.new_plan("2026.10.17.LV_Ten")
    plan["stages"] = STAGES
    d = {"target_min": 12}
    d.update(durations or {})
    if tl:
        d["tl"] = tl
    plan["durations"] = d
    plan.update(extra)
    clips, assign = [], {}
    for uid, si, b, minute, fps in spec:
        c = clip(uid, minute, fps)
        clips.append(c)
        assign[uid] = si
        plan["stars"][c.rel] = True
        plan["labels"][c.rel] = {"uid": uid, "stage": STAGES[si]["name"], "bin": b, "by": "nguoi"}
    return plan, clips, assign, STAGES


BASE = [("d1", 0, "Decor", 10, 50.0), ("d2", 0, "Decor", 11, 50.0), ("b1", 0, "Beauty cô dâu", 5, 50.0), ("b2", 0, "Beauty cô dâu", 6, 50.0),
        ("c1", 0, "Chú rể", 20, 50.0), ("k1", 1, "Đón khách", 30, 50.0), ("k2", 1, "Đón khách", 31, 50.0)]


def bin_of(r, stage, name):
    return next(b for s in r["stages"] if s["name"] == stage for b in s["bins"] if b["name"] == name)


class RaTimeline(unittest.TestCase):
    def test_slow_50_ra_gap_doi_va_co_thanh_day_gap_doi(self):
        r0 = td.build(*scene(BASE), tl_fps=25.0)
        r1 = td.build(*scene(BASE, tl={"blk": {"Chuẩn bị": {"Beauty cô dâu": {"speed": 50}}}}), tl_fps=25.0)
        b0, b1 = bin_of(r0, "Chuẩn bị", "Beauty cô dâu"), bin_of(r1, "Chuẩn bị", "Beauty cô dâu")
        self.assertAlmostEqual(b1["natural_s"], b0["natural_s"] * 2, places=1)             # Có (thanh đầy) = Có gốc / tốc độ
        self.assertAlmostEqual(b1["total_s"], b0["total_s"] * 2, places=1)                 # RA TIMELINE = lấy / tốc độ
        it0 = [i for i in r0["items"] if i["bin"] == "Beauty cô dâu"]
        it1 = [i for i in r1["items"] if i["bin"] == "Beauty cô dâu"]
        self.assertEqual([(i["in_s"], i["out_s"]) for i in it0], [(i["in_s"], i["out_s"]) for i in it1])   # Slow GIỮ NGUYÊN In/Out gốc
        self.assertTrue(all(abs(i["dur"] - i["src_dur"] * 2) < 0.05 for i in it1))
        self.assertTrue(all(i["p"] == 0.5 for i in it1))

    def test_hien_tai_thieu_du_theo_ra_timeline(self):
        base = td.build(*scene(BASE, durations={"target_min": 30}), tl_fps=25.0)             # đủ clip: lấy hết
        slow = td.build(*scene(BASE, durations={"target_min": 30}, tl={"stg": {"Chuẩn bị": {"speed": 50}}}), tl_fps=25.0)
        s0 = next(s for s in base["stages"] if s["name"] == "Chuẩn bị")
        s1 = next(s for s in slow["stages"] if s["name"] == "Chuẩn bị")
        self.assertAlmostEqual(s1["total_s"], s0["total_s"] * 2, places=0)
        self.assertGreater(slow["total_s"], base["total_s"])                                 # Hiện Tại dài hơn vì Slow
        self.assertAlmostEqual(slow["delta_s"], slow["total_s"] - slow["target_s"], places=1)
        short = td.build(*scene(BASE, durations={"target_min": 30}), tl_fps=25.0)
        self.assertEqual(short["state"], "short")
        over = td.build(*scene(BASE, durations={"target_min": 1.0}, tl={"stg": {"Chuẩn bị": {"speed": 50}}, "blk": {}}), tl_fps=25.0)
        self.assertLessEqual(over["total_s"], 62.0)                                          # mục tiêu không phải giới hạn cứng nhưng tổng co theo mục tiêu

    def test_keo_mep_phai_khong_vuot_co_theo_ra_timeline(self):
        plan, clips, assign, st = scene(BASE, tl={"blk": {"Chuẩn bị": {"Beauty cô dâu": {"speed": 50}}}},
                                        durations={"bin_s": {"Chuẩn bị": {"Beauty cô dâu": 9999}}, "stage_s": {"Chuẩn bị": 7000}})
        r = td.build(plan, clips, assign, st, 25.0)
        b = bin_of(r, "Chuẩn bị", "Beauty cô dâu")
        self.assertEqual(b["pin"], b["avail_s"])
        self.assertAlmostEqual(b["total_s"], b["natural_s"], places=0)
        base = bin_of(td.build(*scene(BASE), tl_fps=25.0), "Chuẩn bị", "Beauty cô dâu")
        self.assertAlmostEqual(b["natural_s"], base["natural_s"] * 2, places=1)             # Có của khối Slow = Có gốc / 0,5

    def test_v2_khong_cong_vao_do_dai(self):
        r0 = td.build(*scene(BASE), tl_fps=25.0)
        r1 = td.build(*scene(BASE, tl={"blk": {"Chuẩn bị": {"Decor": {"track": "V2", "at": 5.0}}}}), tl_fps=25.0)
        d0 = bin_of(r0, "Chuẩn bị", "Decor")
        d1 = bin_of(r1, "Chuẩn bị", "Decor")
        self.assertEqual(d1["track"], "V2")
        self.assertAlmostEqual(r1["total_s"], r0["total_s"] - d0["total_s"], places=1)       # Hiện Tại KHÔNG có khối V2
        self.assertAlmostEqual(r1["v2_s"], d0["total_s"], places=1)
        self.assertTrue(any(i["track"] == "V2" for i in r1["items"]))                        # nhưng clip vẫn lên timeline (V2)


class TocDo(unittest.TestCase):
    def test_slow_muot_tu_tinh_50p_60p(self):
        c50, c60 = clip("a", 1, 50.0), clip("b", 1, 60.0)
        self.assertAlmostEqual(td.speed_p("auto", c50, 25.0), 0.5)
        self.assertAlmostEqual(td.speed_p("auto", c60, 30.0), 0.5)
        self.assertAlmostEqual(td.speed_p("auto", c60, 25.0), 25 / 60.0, places=4)           # 41,7%
        self.assertAlmostEqual(td.speed_p("auto", c50, 30.0), 0.6)
        self.assertEqual(td.speed_p("auto", clip("c", 1, 25.0), 25.0), 1.0)                  # source chậm bằng timeline: giữ 100%
        self.assertEqual(td.speed_p("auto", clip("d", 1, 24.0), 30.0), 1.0)                  # không bao giờ nhanh hơn 100%
        self.assertEqual(td.speed_p(None, c50, 25.0), 1.0)
        self.assertEqual(td.speed_p(50.0, c60, 25.0), 0.5)

    def test_slow_muot_tu_tinh_theo_tung_clip_trong_khoi(self):
        spec = [("a", 0, "Decor", 1, 50.0), ("b", 0, "Decor", 2, 60.0)]
        r = td.build(*scene(spec, tl={"blk": {"Chuẩn bị": {"Decor": {"speed": "auto"}}}}), tl_fps=25.0)
        ps = {i["uid"]: i["p"] for i in r["items"]}
        self.assertAlmostEqual(ps["a"], 0.5)
        self.assertAlmostEqual(ps["b"], 0.4167, places=3)
        lay = ttl.layout(r, scene(spec, tl={"blk": {"Chuẩn bị": {"Decor": {"speed": "auto"}}}})[0])
        self.assertEqual(lay["blocks"]["Chuẩn bị|Decor"]["speed"]["mode"], "mixed")          # hai mức trong cùng khối

    def test_me_ap_con_con_thang_me(self):
        tl = {"stg": {"Chuẩn bị": {"speed": 50}}, "blk": {"Chuẩn bị": {"Chú rể": {"speed": 100}}}}
        plan = scene(BASE, tl=tl)
        r = td.build(*plan, tl_fps=25.0)
        self.assertEqual({i["p"] for i in r["items"] if i["bin"] == "Decor"}, {0.5})         # con không đặt riêng: theo mẹ
        self.assertEqual({i["p"] for i in r["items"] if i["bin"] == "Chú rể"}, {1.0})        # con đặt riêng 100% thắng mẹ 50%
        lay = ttl.layout(r, plan[0])
        self.assertEqual(lay["clusters"][0]["speed"]["mode"], "mixed")                       # mẹ có con khác mức: "nhiều mức"
        self.assertEqual(lay["clusters"][1]["speed"]["mode"], "100")
        self.assertTrue(lay["blocks"]["Chuẩn bị|Chú rể"]["speed"]["own"])
        self.assertFalse(lay["blocks"]["Chuẩn bị|Decor"]["speed"]["own"])

    def test_mute_me_ap_con_con_thang_me(self):
        tl = {"stg": {"Chuẩn bị": {"mute": True}}, "blk": {"Chuẩn bị": {"Chú rể": {"mute": False}}}}
        self.assertTrue(td.mute_of(tl, "Chuẩn bị", "Decor"))
        self.assertFalse(td.mute_of(tl, "Chuẩn bị", "Chú rể"))
        self.assertFalse(td.mute_of(tl, "Đón khách", "Đón khách"))                           # mặc định bật

    def test_gia_tri_hong_bi_bo_qua(self):
        for bad in ("abc", 0, 1, 9999, float("nan"), -5):
            self.assertIsNone(td.speed_spec({"blk": {"Chuẩn bị": {"Decor": {"speed": bad}}}}, "Chuẩn bị", "Decor"), bad)
        self.assertEqual(td.speed_spec({"blk": {"Chuẩn bị": {"Decor": {"speed": 100}}}}, "Chuẩn bị", "Decor"), None)


class BoCuc(unittest.TestCase):
    def lay(self, tl=None, spec=BASE):
        plan = scene(spec, tl=tl)
        r = td.build(*plan, tl_fps=25.0)
        return plan[0], r, ttl.layout(r, plan[0])

    def test_mac_dinh_theo_gio_quay_that(self):
        _p, _r, lay = self.lay()
        self.assertEqual(lay["order"], ["Chuẩn bị", "Đón khách"])
        # Beauty quay lúc phút 5, Decor phút 10, Chú rể phút 20 => Beauty đứng trước Decor dù Decor đứng trước trong danh sách bin
        self.assertEqual(lay["clusters"][0]["kids"], ["Chuẩn bị|Beauty cô dâu", "Chuẩn bị|Decor", "Chuẩn bị|Chú rể"])
        starts = [lay["blocks"][k]["start"] for k in lay["clusters"][0]["kids"]]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(lay["clusters"][1]["start"], lay["clusters"][0]["start"] + lay["clusters"][0]["dur"])

    def test_v1_lien_nhau_va_v1_end_bang_hien_tai(self):
        _p, r, lay = self.lay()
        t = 0.0
        for c in lay["clusters"]:
            for k in c["v1"]:
                self.assertAlmostEqual(lay["blocks"][k]["start"], t, places=2)
                t += lay["blocks"][k]["dur"]
        self.assertAlmostEqual(lay["v1_end"], r["total_s"], places=1)

    def test_doi_thu_tu_cum_me_con_di_theo(self):
        plan, r, lay = self.lay()
        self.assertIsNone(ttl.move_cluster(plan, r, "Đón khách", 0))
        lay2 = ttl.layout(r, plan)
        self.assertEqual(lay2["order"], ["Đón khách", "Chuẩn bị"])
        self.assertEqual(lay2["clusters"][1]["kids"], lay["clusters"][0]["kids"])            # con đi theo mẹ, giữ thứ tự
        self.assertAlmostEqual(lay2["blocks"]["Đón khách|Đón khách"]["start"], 0.0)
        self.assertTrue(ttl.is_manual(plan))

    def test_doi_thu_tu_con_trong_cum(self):
        plan, r, lay = self.lay()
        self.assertIsNone(ttl.move_block(plan, r, "Chuẩn bị|Chú rể", "Chuẩn bị", 0))
        lay2 = ttl.layout(r, plan)
        self.assertEqual(lay2["clusters"][0]["kids"], ["Chuẩn bị|Chú rể", "Chuẩn bị|Beauty cô dâu", "Chuẩn bị|Decor"])
        self.assertTrue(lay2["blocks"]["Chuẩn bị|Chú rể"]["manual"])
        self.assertFalse(lay2["blocks"]["Chuẩn bị|Decor"]["manual"])

    def test_keo_con_sang_cum_khac(self):
        plan, r, lay = self.lay()
        self.assertIsNone(ttl.move_block(plan, r, "Chuẩn bị|Decor", "Đón khách", 1))
        lay2 = ttl.layout(r, plan)
        self.assertEqual(lay2["clusters"][1]["kids"], ["Đón khách|Đón khách", "Chuẩn bị|Decor"])
        self.assertNotIn("Chuẩn bị|Decor", lay2["clusters"][0]["kids"])
        self.assertEqual(lay2["blocks"]["Chuẩn bị|Decor"]["cluster"], "Đón khách")
        self.assertEqual(lay2["blocks"]["Chuẩn bị|Decor"]["stage"], "Chuẩn bị")             # vẫn là bin của giai đoạn gốc
        self.assertGreater(lay2["blocks"]["Chuẩn bị|Decor"]["start"], lay2["blocks"]["Đón khách|Đón khách"]["start"])

    def test_keo_con_len_v2_chong_len_v1_tai_cho_tha(self):
        plan, r, lay = self.lay()
        total = r["total_s"]
        self.assertIsNone(ttl.set_track(plan, r, "Chuẩn bị|Decor", "V2", 12.5))
        r2 = td.build(plan, *self._rest(plan), tl_fps=25.0)
        lay2 = ttl.layout(r2, plan)
        b = lay2["blocks"]["Chuẩn bị|Decor"]
        self.assertEqual((b["track"], b["start"]), ("V2", 12.5))
        self.assertLess(r2["total_s"], total)                                                # V2 không cộng vào Hiện Tại
        self.assertNotIn("Chuẩn bị|Decor", lay2["clusters"][0]["v1"])
        self.assertIsNone(ttl.set_track(plan, r2, "Chuẩn bị|Decor", "V1"))
        self.assertEqual(ttl.layout(td.build(plan, *self._rest(plan), tl_fps=25.0), plan)["blocks"]["Chuẩn bị|Decor"]["track"], "V1")

    def _rest(self, plan):
        p2, clips, assign, st = scene(BASE)
        return clips, assign, st

    def test_hai_khoi_v2_khong_chong_nhau_tren_v2(self):
        plan, r, _lay = self.lay()
        ttl.set_track(plan, r, "Chuẩn bị|Decor", "V2", 5.0)
        ttl.set_track(plan, r, "Chuẩn bị|Chú rể", "V2", 6.0)
        r2 = td.build(plan, *self._rest(plan), tl_fps=25.0)
        lay = ttl.layout(r2, plan)
        a, b = lay["blocks"]["Chuẩn bị|Decor"], lay["blocks"]["Chuẩn bị|Chú rể"]
        first, second = sorted((a, b), key=lambda x: x["start"])
        self.assertGreaterEqual(second["start"], first["start"] + first["dur"] - 1e-6)

    def test_nut_xep_lai_theo_gio_quay_giu_toc_do_va_tieng(self):
        plan, r, _lay = self.lay(tl={"blk": {"Chuẩn bị": {"Beauty cô dâu": {"speed": 50, "mute": True}}}})
        ttl.move_cluster(plan, r, "Đón khách", 0)
        ttl.set_track(plan, r, "Chuẩn bị|Decor", "V2", 5.0)
        self.assertTrue(ttl.is_manual(plan))
        ttl.reset_order(plan)
        self.assertFalse(ttl.is_manual(plan))
        t = td.tl_cfg(plan)
        for k in ("order", "kids", "manual"):
            self.assertNotIn(k, t)
        self.assertEqual(t["blk"]["Chuẩn bị"]["Beauty cô dâu"], {"speed": 50, "mute": True})   # tốc độ và tiếng giữ
        self.assertNotIn("Decor", t["blk"]["Chuẩn bị"])
        r2 = td.build(plan, *self._rest(plan), tl_fps=25.0)
        self.assertEqual(ttl.layout(r2, plan)["order"], ["Chuẩn bị", "Đón khách"])

    def test_nho_thu_tu_theo_project_va_doi_ten(self):
        plan, r, _ = self.lay()
        ttl.move_cluster(plan, r, "Đón khách", 0)
        ttl.set_speed(plan, "block", "Chuẩn bị|Decor", 50)
        ttl.set_mute(plan, "stage", "Đón khách", True)
        import json
        plan2 = json.loads(json.dumps(plan))                                                # ghi/đọc lại kế hoạch
        self.assertEqual(td.tl_cfg(plan2)["order"], ["Đón khách", "Chuẩn bị"])
        tc._rename_tl(td.tl_cfg(plan2), "stage", "Chuẩn bị", "Nhà gái", None)
        t = td.tl_cfg(plan2)
        self.assertEqual(t["order"], ["Đón khách", "Nhà gái"])
        self.assertIn("Nhà gái|Decor", t["kids"].get("Nhà gái", t["kids"].get("Đón khách", [])) + t["kids"].get("Nhà gái", []) + sum(t["kids"].values(), []))
        self.assertEqual(t["blk"]["Nhà gái"]["Decor"]["speed"], 50.0)
        tc._rename_tl(t, "bin", "Decor", "Chi tiết", "Nhà gái")
        self.assertEqual(t["blk"]["Nhà gái"]["Chi tiết"]["speed"], 50.0)
        self.assertIn("Nhà gái|Chi tiết", sum(t["kids"].values(), []))

    def test_dat_tocdo_sai_bi_chan(self):
        plan = scene(BASE)[0]
        self.assertIsNotNone(ttl.set_speed(plan, "block", "Chuẩn bị|Decor", 1))
        self.assertIsNotNone(ttl.set_speed(plan, "stage", "Chuẩn bị", "abc"))
        self.assertIsNone(ttl.set_speed(plan, "stage", "Chuẩn bị", "auto"))
        self.assertIsNone(ttl.set_speed(plan, "stage", "Chuẩn bị", None))


class Dat(unittest.TestCase):
    def test_placements_v1_lien_nhau_v2_theo_vi_tri_tiep_theo_khoi(self):
        tl = {"blk": {"Chuẩn bị": {"Decor": {"track": "V2", "at": 4.0, "speed": 50, "mute": True}}}}
        plan = scene(BASE, tl=tl)
        r = td.build(*plan, tl_fps=25.0)
        pl = ttl.placements(r, plan[0])
        v1 = [x for x in pl if x["track"] == "V1"]
        v2 = [x for x in pl if x["track"] == "V2"]
        t = 0.0
        for x in v1:
            self.assertAlmostEqual(x["start_s"], t, places=2)
            t += x["dur_s"]
        self.assertAlmostEqual(t, r["total_s"], places=1)
        self.assertEqual(len(v2), 2)
        self.assertAlmostEqual(v2[0]["start_s"], 4.0)
        self.assertAlmostEqual(v2[1]["start_s"], 4.0 + v2[0]["dur_s"], places=2)             # clip trong khối V2 nối tiếp nhau
        self.assertTrue(all(x["mute"] and x["pct"] == 50.0 for x in v2))
        self.assertEqual([x["track"] for x in pl], ["V1"] * len(v1) + ["V2"] * 2)           # V1 trước, V2 sau

    def test_summary_cho_hop_xac_nhan(self):
        tl = {"blk": {"Chuẩn bị": {"Beauty cô dâu": {"speed": 50}, "Decor": {"mute": True, "track": "V2", "at": 3}}}}
        plan = scene(BASE, tl=tl)
        r = td.build(*plan, tl_fps=25.0)
        sm = ttl.summary(r, plan[0])
        self.assertEqual(sm["slow"], ["Beauty cô dâu (50%)"])
        self.assertEqual(sm["muted"], ["Decor"])
        self.assertEqual(sm["v2"], ["Decor"])
        self.assertEqual(sm["n_v2"], 2)

    def test_doc_lai_v1_lien_nhau_khong_chong_khong_ho(self):
        pl = [{"track": "V1"}] * 3 + [{"track": "V2"}]
        ok, msgs = ttl.verify_readback(pl, [("V1", 0, 50), ("V1", 50, 150), ("V1", 150, 200), ("V2", 60, 160)])
        self.assertTrue(ok, msgs)
        ok, msgs = ttl.verify_readback(pl, [("V1", 0, 50), ("V1", 60, 160), ("V1", 160, 210), ("V2", 60, 160)])
        self.assertFalse(ok)
        self.assertIn("hở", msgs[0])
        ok, msgs = ttl.verify_readback(pl, [("V1", 0, 50), ("V1", 40, 140), ("V1", 140, 190), ("V2", 60, 160)])
        self.assertFalse(ok)
        self.assertIn("chồng", msgs[0])
        ok, msgs = ttl.verify_readback(pl, [("V1", 0, 50), ("V1", 50, 100), ("V1", 100, 150)])
        self.assertFalse(ok)                                                                 # thiếu clip V2

    def test_module_thuan(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_tl.py"), encoding="utf-8") as f:
            src = f.read()
        for bad in ("troly_resolve", "CreateTimeline", "SetMarkInOut", "os.remove", "subprocess", "SetSpeed"):
            self.assertNotIn(bad, src, bad)


if __name__ == "__main__":
    unittest.main()
