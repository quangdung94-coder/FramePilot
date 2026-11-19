"""Kiểm thử sửa lỗi (19/11/2026):
showImg: cập nhật hình xem trước mà không xóa DOM (không tháo thẻ video, không xóa canvas.pv-lut, không xóa canvas.pv-frame)."""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "app", "troly_web")


class TestShowImgDOMPreservation(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(WEB, "app.js"), "r", encoding="utf-8") as f:
            self.app = f.read()

    def test_showimg_khong_xoa_canvas_frame_va_khong_thao_video(self):
        """showImg không được gán preview.innerHTML làm tháo thẻ video và mất canvas.pv-frame."""
        i = self.app.index("const showImg =")
        body = self.app[i:i + 450]
        # Không dùng innerHTML = `<img...>` vì sẽ xóa sạch con trong preview kể cả canvas.pv-frame và video
        self.assertNotIn('innerHTML = `<img', body)
        self.assertIn("canvas.pv-lut", body)  # Giữ tính tương thích với test_troly_lut


if __name__ == "__main__":
    unittest.main()
