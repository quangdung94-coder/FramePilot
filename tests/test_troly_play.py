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


class TranscodeCmd(unittest.TestCase):
    """Đo 18/11/2026: file tạm đuôi .part làm ffmpeg không chọn được định dạng -> bản xem nhẹ không bao giờ tạo được."""

    def test_lenh_co_dinh_dang_ro_va_giu_tieng(self):
        c = tp.transcode_cmd("a.mov", "b.mp4.part")
        i = c.index("-f")
        self.assertEqual(c[i + 1], "mp4")
        self.assertEqual(c[-1], "b.mp4.part")                                # định dạng nêu rõ nên đuôi .part không còn là vấn đề
        self.assertNotIn("-an", c)
        self.assertEqual(c[c.index("-c:a") + 1], "aac")


class PlayerFallback(unittest.TestCase):
    """Đo 18/11/2026 trong WebView2 thật: proxy HEVC không báo lỗi mà chỉ ra tiếng không có hình (videoWidth = 0)."""

    def test_chuyen_ban_xem_nhe_khi_khong_co_hinh(self):
        js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web", "player.js"), encoding="utf-8").read()
        self.assertIn("if (!v.videoWidth) return fallback();", js)
        self.assertIn('v.addEventListener("error", () => { if (v.getAttribute("src")) fallback(); })', js)
        i = js.index("const fallback = () => {")
        body = js[i:i + 400]
        self.assertIn("plOpen(curClip(), true)", body)                      # tạo bản xem nhẹ ffmpeg
        self.assertIn("transcode", body)                                    # không lặp vô hạn khi bản xem nhẹ cũng lỗi


if __name__ == "__main__":
    unittest.main()
