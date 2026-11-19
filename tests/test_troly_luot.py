"""Đêm #2 (ADR-0016): sửa lag khi lướt xem trước để đặt In/Out. Kiểm: hàng đợi một lệnh nhảy, nhảy keyframe khi kéo + chính xác khi dừng tay/thả,
tải trước clip kế, nút "Đo lướt" chỉ có khi --debug và chỉ đọc, API debug_save an toàn. Dữ liệu giả, tên ví dụ LV_Ten."""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import test_troly as T                # noqa: E402
import troly_api as ta                # noqa: E402

WEB = os.path.join(HERE, "..", "app", "troly_web")


def rd(n):
    with open(os.path.join(WEB, n), encoding="utf-8") as f:
        return f.read()


class Web(unittest.TestCase):
    def setUp(self):
        self.pl, self.html, self.app = rd("player.js"), rd("index.html"), rd("app.js")

    def test_chi_mot_lenh_nhay_dang_chay_va_lenh_moi_thay_lenh_cu(self):
        pump = self.pl[self.pl.index("function plPump"):self.pl.index("function plSeek")]
        self.assertIn("SK.busy", pump)
        self.assertIn("SK.want = null", pump)                                                  # lấy vị trí mới nhất, bỏ lệnh dồn ở giữa
        self.assertIn("if (!v || SK.want == null || SK.busy) return;", pump.replace("const v = PL.vid; ", ""))
        self.assertIn('v.addEventListener("seeked", () => { SK.busy = false;', self.pl)         # chờ seeked mới gửi lệnh kế
        self.assertIn("plPump()", self.pl[self.pl.index('v.addEventListener("seeked"'):][:200])

    def test_dang_keo_nhay_theo_keyframe_dung_tay_hoac_tha_thi_chinh_xac(self):
        seek = self.pl[self.pl.index("function plSeek"):self.pl.index("function plNudge")]
        self.assertIn("SK.fast", seek)
        self.assertIn("SK.dwell = setTimeout", seek)                                           # dừng tay chưa thả chuột: nhảy chính xác sau ~0,22 s
        self.assertIn("SK.fast = false", seek)
        self.assertIn("clearTimeout(SK.dwell)", seek)                                          # có lệnh mới thì hủy hẹn giờ cũ
        self.assertIn("kfBefore(t)", self.pl)
        self.assertIn("{ fast: true }", self.pl)                                               # kéo mép In/Out
        self.assertIn("plSeekRelease", self.pl)                                                # thả thanh lướt: chính xác
        self.assertIn("clearTimeout(SK.dwell)", self.pl[self.pl.index("function plStop"):self.pl.index("function plEl")])    # đổi clip: hủy hẹn giờ

    def test_chi_mot_the_video_khong_tai_truoc_bang_bo_giai_ma_thu_hai(self):
        self.assertEqual(self.pl.count('document.createElement("video")'), 1)                  # đo trong pywebview thật: bộ giải mã thứ hai không giúp gì, bỏ
        self.assertNotIn("plPreloadNext", self.pl)
        self.assertIn("function plEl()", self.pl)

    def test_nut_do_luot_an_mac_dinh_va_chi_doc(self):
        self.assertRegex(self.html, r'<button class="btn hidden" id="plMeasure"')
        self.assertIn("api().debug_on()", self.pl)
        meas = self.pl[self.pl.index("async function plSweep"):]
        for bad in ("set_inout", "inout_write", "api().move", "api().apply", "append_starred", "SetMarkInOut", "label("):
            self.assertNotIn(bad, meas, bad)
        self.assertIn("api().debug_save(", meas)                                               # số đo lưu ra file nhỏ
        for mode in ('"cu"', '"keyframe"', '"chinhxac"'):
            self.assertIn(mode, meas)
        self.assertIn("getVideoPlaybackQuality", meas)                                         # khung rớt
        self.assertIn("mediaCapabilities", meas)                                               # E5: có giải mã phần cứng không (chỉ ghi lại)

    def test_phim_va_khong_co_event_key(self):
        self.assertNotRegex(self.pl, r"\be\.key\b")


class Api(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        name = "2026.10.17.LV_Ten"
        root = T.FFolder("Master")
        self.api = ta.TrolyApi(name, self.tmp, resolve_factory=lambda: T.FResolve(T.FProject(name, T.FPool(root))), start_worker=False)

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mac_dinh_khong_debug_va_khong_ghi_file(self):
        self.assertFalse(self.api.debug_on())
        self.assertIn("error", self.api.debug_save("do_luot_1", {"a": 1}))
        self.assertFalse(os.path.isdir(os.path.join(self.tmp, "troly", "debug")))

    def test_debug_ghi_file_nho_trong_thu_muc_du_lieu_va_chan_ten_xau(self):
        self.api.debug = True
        self.assertTrue(self.api.debug_on())
        r = self.api.debug_save("do_luot_20261118", {"tieng_viet": "đo", "n": 3})
        self.assertTrue(r["ok"])
        self.assertTrue(r["path"].startswith(os.path.join(self.tmp, "troly", "debug")))
        with open(r["path"], encoding="utf-8") as f:
            self.assertEqual(json.load(f)["tieng_viet"], "đo")
        for bad in ("..\\x", "../x", "a/b", "", "a.json", "x" * 80, None):
            self.assertIn("error", self.api.debug_save(bad, {}), repr(bad))

    def test_panel_bat_debug_thi_dat_co_cho_api(self):
        with open(os.path.join(HERE, "..", "app", "panel_troly_web.py"), encoding="utf-8") as f:
            self.assertIn("api.debug = a.debug", f.read())


if __name__ == "__main__":
    unittest.main()
