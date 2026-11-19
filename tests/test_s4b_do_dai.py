"""S4b (19/11/2026): trình phát không mượn độ dài clip trước khi clip mới thiếu độ dài."""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


class DoDaiClipMoi(unittest.TestCase):
    """(b) Trình phát mượn độ dài clip trước khi clip mới thiếu độ dài (dur = 0): PL.dur giữ số của clip cũ -> thanh/thời gian sai."""

    def setUp(self):
        with open(os.path.join(HERE, "..", "app", "troly_web", "player.js"), encoding="utf-8") as f:
            self.js = f.read()

    def test_khong_muon_do_dai_clip_truoc(self):
        i = self.js.index("async function plOpen(c)")
        body = self.js[i:i + 1600]
        self.assertNotIn("PL.dur = r.dur || PL.dur", body)                           # dòng cũ: r.dur rỗng thì giữ độ dài clip trước
        self.assertIn("PL.dur = r.dur || 0", body)

    def test_hien_chua_ro_do_dai(self):
        self.assertIn("chưa rõ độ dài", self.js)
        i = self.js.index("function plTime")
        self.assertIn("chưa rõ độ dài", self.js[i:i + 900])


if __name__ == "__main__":
    unittest.main()
