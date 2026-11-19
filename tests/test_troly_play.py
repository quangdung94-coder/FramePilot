"""Kiểm thử máy chủ phát proxy (ADR-0016): Range, từ chối đường dẫn ngoài thư mục proxy, chỉ đọc."""
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import troly_play as tp  # noqa: E402


class Play(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proxy = os.path.join(self.tmp, "proxy")
        self.other = os.path.join(self.tmp, "khac")
        os.makedirs(os.path.join(self.proxy, "p1"))
        os.makedirs(self.other)
        self.f = os.path.join(self.proxy, "p1", "a.mp4")
        self.data = bytes(range(256)) * 40
        with open(self.f, "wb") as fh:
            fh.write(self.data)
        self.out = os.path.join(self.other, "bi_mat.mp4")
        with open(self.out, "wb") as fh:
            fh.write(b"secret")
        self.srv = tp.PlayServer([self.proxy])

    def tearDown(self):
        self.srv.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def get(self, url, rng=None):
        req = urllib.request.Request(url, headers={"Range": rng} if rng else {})
        return urllib.request.urlopen(req, timeout=5)

    def test_inside(self):
        self.assertTrue(tp.inside(self.f, [self.proxy]))
        self.assertFalse(tp.inside(self.out, [self.proxy]))
        self.assertFalse(tp.inside(os.path.join(self.proxy, "..", "khac", "bi_mat.mp4"), [self.proxy]))
        self.assertFalse(tp.inside(self.proxy + "_x", [self.proxy]))        # tên thư mục chung tiền tố
        self.assertFalse(tp.inside(self.f, []))

    def test_outside_path_refused(self):
        self.assertIsNone(self.srv.url_for(self.out))
        self.assertIsNone(self.srv.url_for(os.path.join(self.proxy, "..", "khac", "bi_mat.mp4")))
        self.assertIsNone(self.srv.url_for(os.path.join(self.proxy, "khong_co.mp4")))

    def test_unknown_token_and_traversal(self):
        base = "http://127.0.0.1:%d" % self.srv.port
        for u in ("/v/khong_co", "/v/..%2f..%2fetc", "/", "/file?p=" + self.out):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self.get(base + u)
            self.assertIn(cm.exception.code, (403, 404))

    def test_full_and_range(self):
        url = self.srv.url_for(self.f)
        self.assertTrue(url.startswith("http://127.0.0.1:"))
        r = self.get(url)
        self.assertEqual((r.status, r.read()), (200, self.data))
        r = self.get(url, "bytes=10-19")
        self.assertEqual((r.status, r.read()), (206, self.data[10:20]))
        self.assertEqual(r.headers["Content-Range"], "bytes 10-19/%d" % len(self.data))
        r = self.get(url, "bytes=%d-" % (len(self.data) - 5))
        self.assertEqual(r.read(), self.data[-5:])
        r = self.get(url, "bytes=-7")
        self.assertEqual(r.read(), self.data[-7:])
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get(url, "bytes=999999-")
        self.assertEqual(cm.exception.code, 416)

    def test_readonly_file_unchanged(self):
        url = self.srv.url_for(self.f)
        mt = os.path.getmtime(self.f)
        self.get(url, "bytes=0-9").read()
        self.assertEqual(open(self.f, "rb").read(), self.data)
        self.assertEqual(os.path.getmtime(self.f), mt)

    def test_parse_range(self):
        self.assertEqual(tp.parse_range("bytes=0-9", 100), (0, 9))
        self.assertEqual(tp.parse_range("bytes=90-200", 100), (90, 99))
        self.assertEqual(tp.parse_range("bytes=100-", 100), "bad")
        self.assertIsNone(tp.parse_range("junk", 100))
        self.assertIsNone(tp.parse_range(None, 100))

    def test_symlink_escape(self):
        if not hasattr(os, "symlink"):
            self.skipTest("không có symlink")
        link = os.path.join(self.proxy, "lk.mp4")
        try:
            os.symlink(self.out, link)
        except OSError:
            self.skipTest("không tạo được symlink")
        self.assertIsNone(self.srv.url_for(link))


class KhongTaoBanXemNhe(unittest.TestCase):
    """S1 (19/11/2026, ADR-0029): bỏ hẳn "bản xem nhẹ" (mp4 720p trong cache). Proxy không phát được thì chỉ báo rõ, không tạo file nào.
    Thay cho test cũ của bản xem nhẹ (TranscodeCmd.test_lenh_co_dinh_dang_ro_va_giu_tieng, PlayerFallback.test_chuyen_ban_xem_nhe_khi_khong_co_hinh)."""

    APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")

    def _doc(self, *p):
        return open(os.path.join(self.APP, *p), encoding="utf-8").read()

    def test_ma_tao_mp4_da_bi_go(self):
        self.assertFalse(hasattr(tp, "transcode_cmd"))
        self.assertFalse(hasattr(tp, "ensure_play_mp4"))
        for f in ("troly_play.py", "troly_api.py"):
            src = self._doc(f)
            for bad in ("libx264", "ensure_play_mp4", "transcode", "_play_dir", "troly_play\\"):
                self.assertNotIn(bad, src, f + ": " + bad)

    def test_play_info_khong_con_tham_so_transcode(self):
        import inspect
        import troly_api
        self.assertEqual(list(inspect.signature(troly_api.TrolyApi.play_info).parameters), ["self", "uid"])

    def test_giao_dien_bao_ro_va_khong_goi_ban_nhe(self):
        js = self._doc("troly_web", "player.js")
        for bad in ("transcode", "bản xem nhẹ", "Bản xem nhẹ", "fallback"):
            self.assertNotIn(bad, js, bad)
        self.assertIn("if (!v.videoWidth) return noPlay();", js)
        self.assertIn('v.addEventListener("error", () => { if (v.getAttribute("src")) noPlay(); })', js)
        body = js[js.index("const noPlay = () => {"):][:700]
        self.assertIn("Không phát được proxy của clip", body)               # nói clip nào
        self.assertIn("HEVC", body)                                          # vì sao
        self.assertIn("tạo lại proxy", body)                                 # nên làm gì

    def test_may_chu_phat_chi_cho_phep_proxy_root(self):
        import troly_api
        src = self._doc("troly_api.py")
        self.assertIn("tp.PlayServer([self._proxy_root])", src)


if __name__ == "__main__":
    unittest.main()
