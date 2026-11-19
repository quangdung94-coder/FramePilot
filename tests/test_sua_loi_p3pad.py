"""Kiểm thử sửa lỗi (19/11/2026):
p3Pad: đồng bộ giá trị đệm đã lưu (plan['inout_sug_cfg']['pad']) vào ô nhập trên giao diện Bước 3."""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "app", "troly_web")


class TestP3PadSync(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(WEB, "step3.js"), "r", encoding="utf-8") as f:
            self.s3 = f.read()

    def test_p3pad_dong_bo_gia_tri_da_luu_tu_state(self):
        """p3SugPaint phải cập nhật $('p3Pad').value = g.pad khi có trạng thái lưu, tránh việc mở lại panel luôn hiện 0.3."""
        i = self.s3.index("function p3SugPaint()")
        body = self.s3[i:i + 800]
        self.assertIn('$("p3Pad")', body, "p3SugPaint chưa đồng bộ giá trị vào $('p3Pad')")
        self.assertIn("g.pad", body, "p3SugPaint chưa đọc g.pad để gán vào ô nhập")


if __name__ == "__main__":
    unittest.main()
