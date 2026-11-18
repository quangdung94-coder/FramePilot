"""Giao diện Bước 5 (ADR-0013): phần tử có mặt, chữ ghi rõ "đề xuất", chức năng nêu trên trang có thật, tạo timeline chỉ sau hộp xác nhận."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web")


def rd(n):
    with open(os.path.join(WEB, n), encoding="utf-8") as f:
        return f.read()


class DurWeb(unittest.TestCase):
    def setUp(self):
        self.html, self.js, self.app = rd("index.html"), rd("step5.js"), rd("app.js")

    def test_phan_tu_va_id_khong_trung(self):
        for i in ("durTarget", "d5Total", "d5Shots", "d5Stages", "d5Legend", "d5Strip", "d5Rows", "d5Warn", "d5Cut", "d5Create", "d5Reset", "d5Note"):
            self.assertEqual(self.html.count('id="%s"' % i), 1, i)
        ids = re.findall(r'\bid="([^"]+)"', self.html)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn('<script src="step5.js"></script>', self.html)
        self.assertNotIn("Bước 5 · Thời lượng: sắp có", self.html)

    def test_nhan_theo_demo_va_ghi_ro_de_xuat(self):
        for t in ("Video mục tiêu", "Tổng sau khi cắt gọt", "Shot được dùng", "Chia thời gian cho từng giai đoạn", "Cắt gọt cho vừa", "Đưa lên Timeline mới",
                  "Khoảng cho phép và thực tế (thang 0 – 90 giây)", "Sau cắt", "Số shot"):
            self.assertIn(t, self.html, t)
        self.assertIn("ĐỀ XUẤT, anh sửa được", self.html)
        self.assertIn("<em>đề xuất</em>", self.js)                                              # từng dòng bin chưa sửa
        p5 = self.html[self.html.index('id="page5"'):self.html.index("<!-- Đếm ngược tắt máy")]
        self.assertNotIn("đã duyệt", p5.lower())                                                # không ghi "đã duyệt" cho số đề xuất

    def test_chuc_nang_nhu_chu_tren_trang_co_that(self):
        for fn in ("dur_state", "dur_set_target", "dur_set_bin", "dur_set_share", "dur_reset", "dur_cut", "dur_create_timeline"):
            self.assertIn("api()." + fn, self.js, fn)
        self.assertIn('d5-grip', self.js)                                                       # "kéo vạch giữa hai giai đoạn"
        self.assertIn("renderPage5()", self.app)                                                # mở bước 5 thì vẽ lại

    def test_tao_timeline_chi_sau_hop_xac_nhan_va_khi_da_cat_got(self):
        seg = self.js[self.js.index('$("d5Create").addEventListener'):]
        self.assertLess(seg.index("cut_ready"), seg.index("await ask("))
        self.assertLess(seg.index("await ask("), seg.index("api().dur_create_timeline"))
        self.assertIn("Không sửa hay xóa timeline đang có", seg)
        for bad in ("api().inout_write", "api().apply", "api().append_starred", "SetMarkInOut"):
            self.assertNotIn(bad, self.js, bad)


if __name__ == "__main__":
    unittest.main()
