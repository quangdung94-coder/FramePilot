"""Kiểm thử đổi phím giai đoạn Bước 2 sang F1-F12 (ADR-0030): đọc event.code, chặn F1/F5/F11/F12, cảnh báo >12 giai đoạn."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web")


def rd(n):
    with open(os.path.join(WEB, n), "r", encoding="utf-8") as f:
        return f.read()


class TestPhimF(unittest.TestCase):
    def setUp(self):
        self.js = rd("app.js")
        self.html = rd("index.html")

    def test_doc_phim_bang_event_code(self):
        m = re.search(r"function fKeyOf\(e\) \{.*?\}", self.js)
        self.assertIsNotNone(m)
        self.assertIn("e.code", m.group(0))
        self.assertNotIn("e.key", m.group(0))

    def test_regex_f_khop_dung_f1_den_f12(self):
        rx = re.compile(r"^F([1-9]|1[0-2])$")
        for k in range(1, 13):
            self.assertTrue(rx.match("F%d" % k))
        for bad in ("F0", "F13", "F", "Digit1", "KeyF", "F01"):
            self.assertFalse(rx.match(bad), bad)
        self.assertIn(r"/^F([1-9]|1[0-2])$/", self.js)

    def test_chan_mac_dinh_f1_f5_f11_f12(self):
        self.assertIn('new Set(["F1", "F5", "F11", "F12"])', self.js)
        self.assertIn("F_BLOCK.has(e.code)", self.js)
        i = self.js.index("F_BLOCK.has(e.code)")
        self.assertIn("preventDefault", self.js[i:i + 150])

    def test_f_chon_giai_doan_roi_cho_bin_con(self):
        self.assertIn("startPending(f - 1)", self.js)
        self.assertIn("const MAX_F = 12;", self.js)

    def test_shift_so_khong_con_chon_giai_doan(self):
        self.assertNotIn("e.shiftKey && !e.ctrlKey && !e.altKey) {       // Shift+số", self.js)
        self.assertNotIn('"Shift+" + (k + 1)', self.js)
        self.assertIsNone(re.search("⇧[0-9]", self.js))              # nhãn cũ ⇧1 hết; ⇧F1 (mốc cuối ở Bước 1) là phím mới

    def test_canh_bao_qua_12_giai_doan(self):
        self.assertIn("S.stages.length > MAX_F", self.js)
        self.assertIn("không có phím", self.js)

    def test_dong_nhac_phim_khop_phim_moi(self):
        self.assertIn("F1–F12 sang giai đoạn đó rồi bấm số bin con", self.html)
        self.assertNotIn("Shift+số sang giai đoạn", self.html)


if __name__ == "__main__":
    unittest.main()
