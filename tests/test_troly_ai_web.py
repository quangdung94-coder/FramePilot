"""Giao diện gợi ý AI ở Bước 2 (ADR-0022): phần tử có mặt, chữ hướng dẫn có chức năng thật, phím đọc bằng event.code, không gọi DaVinci."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web")


def rd(n):
    with open(os.path.join(WEB, n), encoding="utf-8") as f:
        return f.read()


class AiWeb(unittest.TestCase):
    def setUp(self):
        self.html, self.js, self.app = rd("index.html"), rd("ai.js"), rd("app.js")

    def test_phan_tu_va_id_khong_trung(self):
        for i in ('id="aiBox"', 'id="aiSrc"', 'id="aiBody"', 'id="aiActs"'):
            self.assertEqual(self.html.count(i), 1, i)
        self.assertIn('<script src="ai.js"></script>', self.html)
        ids = re.findall(r'\bid="([^"]+)"', self.html)
        self.assertEqual(len(ids), len(set(ids)))
        p2 = self.html[self.html.index('id="page2"'):self.html.index('id="page3"')]
        self.assertIn('id="aiBox"', p2)                                                       # hộp nằm ở Bước 2

    def test_chu_huong_dan_co_chuc_nang_that(self):
        self.assertIn('e.code !== "KeyA" && e.code !== "KeyX"', self.js)                      # A nhận, X bỏ qua
        for fn in ("ai_info", "ai_for", "ai_accept", "ai_skip", "ai_run", "ai_stop"):
            self.assertIn("api()." + fn, self.js, fn)
        self.assertIn("AI gợi ý, chờ bạn duyệt</span>", self.html)                            # chú thích lưới không còn "sắp có"
        self.assertIn('class="tag ai"', self.app)                                             # thẻ gợi ý viền đứt trên lưới

    def test_phim_doc_bang_event_code_va_bo_qua_o_go_chu(self):
        self.assertNotRegex(self.js, r"\be\.key\b")
        self.assertIn("INPUT|SELECT|TEXTAREA", self.js)
        self.assertIn("page !== 2", self.js)

    def test_khong_goi_davinci_tu_gio_dien_ai(self):
        for bad in ("api().apply", "api().move(", "api().append", "inout_write", "SetMarkInOut", "MoveClips", "api().label(", "api().undo"):
            self.assertNotIn(bad, self.js, bad)
        self.assertNotIn("aiTakeAll", self.js)                                                  # Đêm #1: gộp vào nút Tự phân loại (chỉ gán nhãn, có Hoàn tác)


if __name__ == "__main__":
    unittest.main()
