"""Bước 3 (ADR-0019): bảng quy tắc gợi ý từng bin (chưa sửa = y hệt bản cũ, đặt tay luôn thắng, kiểm hợp lệ) và sóng âm từ proxy
(chỉ đọc, cache, giới hạn thời gian, không có proxy thì báo). Dùng dữ liệu giả, tên ví dụ LV_Ten."""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_troly as T                # noqa: E402
import test_troly_style as TS         # noqa: E402
import troly_api as ta                # noqa: E402
import troly_core as tc               # noqa: E402
import troly_wave as tw               # noqa: E402


def pack(r):
    return None if r is None else [r["in_s"], r["out_s"], r["dur"], r["rule"]]


class Rules(unittest.TestCase):
    def test_chua_sua_bang_quy_tac_giong_het_ban_cu(self):
        for dur, label, want in TS.BASELINE:
            for rules in (None, {}):
                self.assertEqual(pack(tc.suggest_inout(dur, label, "", rules)), want, (dur, label))
                self.assertEqual(pack(tc.suggest_inout(dur, label, "", rules, None)), want, (dur, label))
            got = pack(tc.suggest_inout(dur, label, "psc", {}))                                       # PSC + bảng chưa sửa = như ADR-0018
            if want is None:
                self.assertIsNone(got)
            else:
                self.assertEqual(got[:3], want[:3])
        for dur in (0.9, 1.0, 2.0, 30.0):
            self.assertEqual(pack(tc.suggest_inout(dur, "Bin lạ", "traditional")), pack(tc.suggest_inout(dur, "Bin lạ", "traditional", {}, None)))

    def test_bang_hien_ra_dung_so_mac_dinh_va_khong_danh_dau_da_sua(self):
        v = {r["name"]: r for r in tc.rules_view({}, ["Decor", "Beauty cô dâu", "Nghi lễ", "Phỏng vấn"])}
        self.assertEqual((v["Decor"]["min"], v["Decor"]["max"], v["Decor"]["whole"]), (3.0, 3.0, False))
        self.assertEqual((v["Beauty cô dâu"]["min"], v["Beauty cô dâu"]["max"]), (4.0, 4.0))
        self.assertEqual((v["Nghi lễ"]["min"], v["Nghi lễ"]["max"]), (2.5, 5.0))                       # ADR-0021: số đo thật
        self.assertEqual((v["Phỏng vấn"]["min"], v["Phỏng vấn"]["max"], v["Phỏng vấn"]["whole"]), (4.0, 8.5, False))
        self.assertEqual((v["*"]["min"], v["*"]["max"]), (3.0, 3.0))
        self.assertFalse(any(r["edited"] for r in v.values()))

    def test_bang_moi_theo_so_do_that_adr_0021(self):
        want = {"Nghi lễ": (2.5, 5.0), "Chào bàn": (3.0, 4.0), "Khách": (2.5, 4.0), "Gia đình cô dâu": (3.0, 4.0), "Nhà trai đến": (3.0, 4.5),
                "Cô dâu chú rể": (2.0, 3.0), "Phỏng vấn": (4.0, 8.5), "Decor": (3.0, 3.0), "Beauty cô dâu": (4.0, 4.0), "Đón khách": (2.5, 4.0)}
        v = {r["name"]: r for r in tc.rules_view({}, list(want))}
        for b, mm in want.items():
            self.assertEqual((v[b]["min"], v[b]["max"]), mm, b)
            self.assertFalse(v[b]["whole"], b)
        self.assertEqual(tc.suggest_inout(30.0, "Phỏng vấn")["dur"], 8.5)                           # không còn giữ trọn câu
        self.assertEqual(tc.suggest_inout(30.0, "Nghi lễ")["dur"], 5.0)
        self.assertEqual(tc.suggest_inout(30.0, "Gia đình cô dâu")["rule"], "Gia đình: giữ 3–4s")   # "gia đình" xét trước "cô dâu"
        self.assertEqual(tc.suggest_inout(30.0, "Bin lạ")["rule"], "Quy tắc v4: vào +1.2s, giữ 3s")

    def test_kiem_hop_le(self):
        self.assertTrue(tc.check_bin_rule(3, 5)[0])
        self.assertTrue(tc.check_bin_rule(3, 3)[0])                                                  # min = max được
        self.assertEqual(tc.check_bin_rule(5, 3), (False, "Tối thiểu không được lớn hơn tối đa."))
        for bad in ((0, 3), (-1, 3), (3, 0), ("a", 3), (3, None), (3, "x"), (float("nan"), 3), (3, float("inf")), (1, 601)):
            self.assertFalse(tc.check_bin_rule(*bad)[0], bad)
        ok, v = tc.check_bin_rule(2, None, True)                                                     # trọn câu: không cần tối đa
        self.assertTrue(ok)
        self.assertEqual(v, {"min": 2.0, "max": None, "whole": True})
        self.assertFalse(tc.check_bin_rule(0, None, True)[0])

    def test_quy_tac_nguoi_dung_doi_goi_y(self):
        rules = {"Decor": {"min": 2, "max": 5, "whole": False}}
        r = tc.suggest_inout(30.0, "Decor", "", rules)
        self.assertEqual(r["dur"], 5.0)                                                              # clip dài: chặn ở tối đa 5s
        self.assertIn("Quy tắc của anh", r["rule"])
        self.assertEqual(tc.suggest_inout(3.0, "Decor", "", rules)["dur"], 2.0)                      # clip 3s: dur-1 = 2s, bằng tối thiểu
        self.assertEqual(pack(tc.suggest_inout(30.0, "Chú rể", "", rules)), pack(tc.suggest_inout(30.0, "Chú rể")))   # bin khác không đổi
        w = tc.suggest_inout(30.0, "Phỏng vấn", "", {"Phỏng vấn": {"min": 5, "max": None, "whole": True}})
        self.assertEqual(w["dur"], 28.3)                                                             # trọn câu: giữ gần hết clip
        r = tc.suggest_inout(30.0, "Decor", "", {"Decor": {"min": 4, "max": 4, "whole": False}})
        self.assertEqual(r["dur"], 4.0)

    def test_dong_bin_khac_chi_ap_cho_bin_khong_khop_quy_tac_co_san(self):
        rules = {tc.OTHER_KEY: {"min": 6, "max": 6, "whole": False}}
        self.assertEqual(tc.suggest_inout(30.0, "Bin lạ", "", rules)["dur"], 6.0)
        self.assertEqual(tc.suggest_inout(30.0, None, "", rules)["dur"], 6.0)
        self.assertEqual(pack(tc.suggest_inout(30.0, "Decor", "", rules)), pack(tc.suggest_inout(30.0, "Decor")))

    def test_quy_tac_hong_trong_file_bi_bo_qua(self):
        bad = {"Decor": {"min": 9, "max": 2, "whole": False}}                                        # file kế hoạch bị sửa tay sai
        self.assertEqual(pack(tc.suggest_inout(30.0, "Decor", "", bad)), pack(tc.suggest_inout(30.0, "Decor")))

    def test_truyen_thong_cat_dau_duoi_chinh_duoc(self):
        r = tc.suggest_inout(30.0, None, "traditional", None, 2.5)
        self.assertEqual((r["in_s"], r["out_s"]), (2.5, 27.5))
        r = tc.suggest_inout(30.0, None, "traditional", None, 0)
        self.assertEqual((r["in_s"], r["out_s"]), (0.0, 30.0))
        self.assertGreaterEqual(tc.suggest_inout(3.0, None, "traditional", None, 10)["dur"], 1.0)    # clip ngắn vẫn còn ít nhất 1 giây


class RulesApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proxy = os.path.join(self.tmp, "proxy")
        os.makedirs(self.proxy)
        self.pf = os.path.join(self.proxy, "DGa.mov")
        with open(self.pf, "wb") as f:
            f.write(b"x" * 100)
        sel = T.FFolder("01_SELECTED", [T.FItem("a", T.props("DGa.MP4", "Sat Oct 17 2026 08:10:00", "Sat Oct 17 08:10:20 2026", 1000, Type="Video + Audio",
                                                              **{"Proxy Media Path": self.pf})),
                                        T.FItem("b", T.props("DGb.MP4", "Sat Oct 17 2026 08:20:00", "Sat Oct 17 08:20:20 2026", 1000, Type="Video + Audio"))])
        foot = T.FFolder("01_footage")
        foot.subs.append(sel)
        root = T.FFolder("Master")
        root.subs.append(foot)
        self.pool = T.FPool(root)
        self.name = "2026.10.17.LV_Ten"
        self.api = self._api()
        self.api._worker.connect()
        self.api.init()
        self.run_jobs()
        self.api.load("Master/01_footage/01_SELECTED")
        self.run_jobs()

    def _api(self):
        return ta.TrolyApi(self.name, self.tmp, resolve_factory=lambda: T.FResolve(T.FProject(self.name, self.pool)), start_worker=False, proxy_root=self.proxy)

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

    def test_chua_sua_khong_co_khoa_trong_ke_hoach_va_goi_y_nhu_cu(self):
        self.api.state()
        self.assertNotIn("bin_rules", self.api._plan)
        self.assertNotIn("trad_trim_s", self.api._plan)
        self.assertEqual(self.sug()["rule"], "Quy tắc v4: vào +1.2s, giữ 3s")
        self.assertEqual((self.sug()["in_s"], self.sug()["out_s"]), (1.2, 4.2))

    def test_sua_quy_tac_luu_trong_ke_hoach_mo_lai_van_con_va_ve_mac_dinh(self):
        r = self.api.set_bin_rule(tc.OTHER_KEY, 8, 10)
        self.assertNotIn("error", r)
        s = self.sug()
        self.assertEqual((s["in_s"], s["out_s"], s["dur"]), (1.2, 11.2, 10.0))                       # clip 20 giây, quy tắc 8-10s
        self.assertIn("Quy tắc của anh", s["rule"])
        self.assertTrue(next(b for b in r["rules"]["bins"] if b["name"] == tc.OTHER_KEY)["edited"])
        api2 = self._api()
        try:
            self.assertEqual(api2._plan["bin_rules"][tc.OTHER_KEY], {"min": 8.0, "max": 10.0, "whole": False})
        finally:
            api2._thumbs.shutdown()
        self.api.reset_bin_rule(tc.OTHER_KEY)
        self.assertEqual(self.sug()["rule"], "Quy tắc v4: vào +1.2s, giữ 3s")
        self.assertNotIn("bin_rules", self.api._plan)

    def test_gia_tri_sai_bi_chan_va_khong_ghi_vao_ke_hoach(self):
        for args in ((tc.OTHER_KEY, 5, 3), (tc.OTHER_KEY, 0, 3), (tc.OTHER_KEY, "a", 3), ("", 3, 3)):
            self.assertIn("error", self.api.set_bin_rule(*args), args)
        self.assertNotIn("bin_rules", self.api._plan)
        self.assertIn("error", self.api.set_trad_trim(-1))
        self.assertIn("error", self.api.set_trad_trim("x"))
        self.assertNotIn("trad_trim_s", self.api._plan)

    def test_truyen_thong_cat_chinh_duoc_va_ve_mac_dinh_xoa_khoa(self):
        self.api.set_shoot_style("traditional")
        self.api.set_trad_trim(2)
        s = self.sug()
        self.assertEqual((s["in_s"], s["out_s"]), (2.0, 18.0))                                       # clip 20 giây
        self.assertEqual(self.api.state()["rules"]["trad_trim"], 2.0)
        self.api.set_trad_trim(1.5)
        self.assertNotIn("trad_trim_s", self.api._plan)                                              # bằng mặc định thì không lưu khóa
        self.api.set_trad_trim(3)
        self.api.reset_bin_rule()
        self.assertNotIn("trad_trim_s", self.api._plan)

    def test_dat_tay_luon_thang_va_goi_y_khong_duoc_ghi(self):
        uid = next(c.uid for c in self.api._clips if c.name == "DGa.MP4")
        self.api.set_inout(uid, 2.0, 6.0)
        before = tc.inout_frames(self.api._plan, self.api._by_uid[uid])
        self.api.set_bin_rule(tc.OTHER_KEY, 8, 10)
        self.api.set_shoot_style("traditional")
        self.api.set_trad_trim(4)
        self.assertEqual(tc.inout_frames(self.api._plan, self.api._by_uid[uid]), before)
        c = next(c for c in self.api.state()["clips"] if c["name"] == "DGa.MP4")
        self.assertEqual((c["in_s"], c["out_s"], c["io_src"]), (2.0, 6.0, "manual"))                 # giao diện lấy đặt tay, không lấy gợi ý
        pv = self.api.inout_write_preview("selected", [x.uid for x in self.api._clips])
        self.assertEqual((pv["n"], pv["skip"]), (1, 1))                                              # clip chưa đặt tay: gợi ý không được ghi

    def test_bang_quy_tac_trong_state_gom_bin_cua_cac_giai_doan(self):
        self.api._plan["stages"] = [{"name": "A", "bins": ["Decor", "Phỏng vấn"]}, {"name": "B", "bins": ["Decor", "Chú rể"]}]
        names = [b["name"] for b in self.api._rules_state()["bins"]]
        self.assertEqual(names, ["Decor", "Phỏng vấn", "Chú rể", tc.OTHER_KEY])


class FakeRun(object):
    def __init__(self, pcm=b"", rc=0, exc=None):
        self.pcm, self.rc, self.exc, self.calls = pcm, rc, exc, []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        if self.exc:
            raise self.exc
        return subprocess.CompletedProcess(cmd, self.rc, self.pcm, b"")


def pcm(vals):
    return struct.pack("<%dh" % len(vals), *vals)


class Wave(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "proxy", "a.mov")
        os.makedirs(os.path.dirname(self.src))
        with open(self.src, "wb") as f:
            f.write(b"x" * 50)
        self.cache = os.path.join(self.tmp, "cache", "troly_wave", "LV_Ten")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dinh_song_chuan_hoa_0_den_100(self):
        p = tw.peaks_from_pcm(pcm([0, 100, -200, 50, 10, -10, 0, 400]), bins=4)
        self.assertEqual(len(p), 4)
        self.assertEqual(max(p), 100)
        self.assertEqual(p[3], 100)
        self.assertEqual(tw.peaks_from_pcm(b""), [])
        self.assertEqual(len(tw.peaks_from_pcm(pcm([1, 2, 3]), bins=800)), 3)                        # ít mẫu hơn số cột

    def test_tao_nen_roi_dung_cache_khong_goi_ffmpeg_lan_hai(self):
        run = FakeRun(pcm([10, -300, 20, 5] * 50))
        wm = tw.WaveMaker(self.cache, runner=run)
        self.assertEqual(wm.get("k1", self.src), {"pending": True})
        wm.wait("k1")
        r = wm.get("k1", self.src)
        self.assertIn("peaks", r)
        self.assertEqual(len(run.calls), 1)
        wm2 = tw.WaveMaker(self.cache, runner=FakeRun(exc=AssertionError("không được gọi")))       # panel mở lại: đọc cache
        self.assertEqual(wm2.get("k1", self.src)["peaks"], r["peaks"])
        cmd = run.calls[0][0]
        self.assertIn(self.src, cmd)
        self.assertEqual(cmd[-1], "-")                                                               # ra stdout, không ghi file cạnh proxy
        self.assertEqual(sorted(os.listdir(os.path.dirname(self.src))), ["a.mov"])
        self.assertTrue(any(f.endswith(".json") for f in os.listdir(self.cache)))

    def test_cache_het_han_khi_proxy_doi(self):
        wm = tw.WaveMaker(self.cache, runner=FakeRun(pcm([1, 2, 3, 4] * 10)))
        wm.get("k", self.src)
        wm.wait("k")
        with open(self.src, "ab") as f:
            f.write(b"y")                                                                            # proxy đổi cỡ
        self.assertIsNone(tw.read_cached(tw.cache_file(self.cache, "k"), self.src))

    def test_chua_co_proxy_va_loi_ffmpeg_va_qua_gio(self):
        wm = tw.WaveMaker(self.cache, runner=FakeRun(b""))
        self.assertEqual(wm.get("x", ""), {"error": "Chưa có proxy"})
        self.assertEqual(wm.get("x", os.path.join(self.tmp, "khong_co.mov")), {"error": "Chưa có proxy"})
        for key, run, text in (("a", FakeRun(b""), "không có âm thanh"), ("b", FakeRun(b"", rc=1), "không đọc được"),
                               ("c", FakeRun(exc=subprocess.TimeoutExpired("ffmpeg", 90)), "quá"), ("d", FakeRun(exc=OSError()), "ffmpeg")):
            w = tw.WaveMaker(self.cache + "_" + key, runner=run)
            w.get(key, self.src)
            w.wait(key)
            r = w.get(key, self.src)
            self.assertIn(text, r.get("error", ""), key)

    def test_gioi_han_thoi_gian_duoc_truyen_cho_ffmpeg(self):
        run = FakeRun(pcm([1, 2, 3, 4]))
        tw.make_peaks(self.src, os.path.join(self.cache, "z.json"), timeout=7, runner=run)
        self.assertEqual(run.calls[0][1]["timeout"], 7)
        self.assertEqual(tw.TIMEOUT_S, 90)

    def test_api_wave_chua_co_proxy_ngoai_thu_muc_va_thanh_cong(self):
        t = RulesApi("test_chua_sua_khong_co_khoa_trong_ke_hoach_va_goi_y_nhu_cu")
        t.setUp()
        try:
            a = t.api
            ua = next(c.uid for c in a._clips if c.name == "DGa.MP4")
            ub = next(c.uid for c in a._clips if c.name == "DGb.MP4")
            self.assertEqual(a.wave(ub), {"error": "Chưa có proxy"})
            self.assertIn("error", a.wave("khong-co"))
            a._wave = tw.WaveMaker(os.path.join(t.tmp, "cache", "troly_wave", "LV_Ten"), runner=FakeRun(pcm([5, -50, 7, 9] * 30)))
            self.assertEqual(a.wave(ua), {"pending": True})
            a._wave.wait(a._by_uid[ua].rel)
            self.assertIn("peaks", a.wave(ua))
            a._by_uid[ua].proxy = os.path.join(t.tmp, "ngoai.mov")                                   # proxy nằm ngoài proxy_root
            open(a._by_uid[ua].proxy, "wb").write(b"x")
            self.assertIn("ngoài", a.wave(ua)["error"])
        finally:
            t.tearDown()


if __name__ == "__main__":
    unittest.main()
