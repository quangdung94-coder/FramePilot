"""Giao diện Bước 5 làm lại (ADR-0013, theo design/5_thoi_luong_moi): phần tử có mặt, nhãn theo demo, chức năng nêu trên trang có thật,
không còn nút cắt gọt / vạch kéo, tạo timeline chỉ sau hộp xác nhận."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web")


def rd(n):
    with open(os.path.join(WEB, n), encoding="utf-8") as f:
        return f.read()


class DurWeb(unittest.TestCase):
    def setUp(self):
        self.html, self.js, self.app, self.css = rd("index.html"), rd("step5.js"), rd("app.js"), rd("style.css")
        self.p5 = self.html[self.html.index('id="page5"'):self.html.index("<!-- Đếm ngược tắt máy")]

    def test_phan_tu_va_id_khong_trung(self):
        for i in ("durTarget", "d5Res", "d5Seg", "d5Stages", "d5Pv", "d5Warn", "d5RTitle", "d5Why", "d5SugA", "d5SugB", "d5SugC", "d5Create", "d5Reset", "d5FootL"):
            self.assertEqual(self.html.count('id="%s"' % i), 1, i)
        ids = re.findall(r'\bid="([^"]+)"', self.html)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn('<script src="step5.js"></script>', self.html)
        self.assertNotIn("right5", self.html + self.app)

    def test_nhan_theo_demo(self):
        for t in ("VIDEO MỤC TIÊU", "phút:giây", "Chia thời lượng cho từng giai đoạn", "XEM TRƯỚC TIMELINE MỚI", "đậm: giữ", "sọc: bỏ", "nét đứt: thiếu",
                  "Gợi ý cách xử lý", "Cách dùng ổ khóa", "Đưa lên Timeline mới", "Chưa ghi gì vào DaVinci"):
            self.assertIn(t, self.p5, t)
        for t in ("BIN CON", "MIN – MAX (tổng bin)", "Có <b>", "được chia", "Phải bỏ", "Thiếu ", "Sẽ bỏ", "tự cắt gọt khi sửa", "chỉ bỏ nguyên clip"):
            self.assertIn(t, self.js + self.p5, t)

    def test_khong_con_nut_cat_got_va_vach_keo(self):
        for bad in ('id="d5Cut"', "d5-grip", "dur_cut", "dur_set_share", "cut_ready"):
            self.assertNotIn(bad, self.html + self.js + self.css, bad)
        self.assertNotIn(">Cắt gọt cho vừa<", self.p5)

    def test_chuc_nang_nhu_chu_tren_trang_co_that(self):
        for fn in ("dur_state", "dur_set_target", "dur_set_bin", "dur_set_stage", "dur_toggle_lock", "dur_rebalance", "dur_lower_target", "dur_reset", "dur_create_timeline"):
            self.assertIn("api()." + fn, self.js, fn)
        self.assertIn("renderPage5()", self.app)
        self.assertIn("goPage(3)", self.js)                                                      # (c) mở Bước 3 ở đúng bin
        self.assertIn("p3View(", self.js)

    def test_go_so_chong_giat_va_phim_khong_lam_hong_o_nhap(self):
        self.assertIn("d5Stable", self.js)                                                       # gõ dở "4:3" chưa tính lại
        self.assertIn("D5.seq", self.js)                                                         # kết quả cũ đến muộn bị bỏ
        self.assertIn("e.code", self.js)                                                         # phím đọc bằng event.code
        self.assertNotIn("e.key", self.js)

    def test_tao_timeline_chi_sau_hop_xac_nhan(self):
        seg = self.js[self.js.index('$("d5Create").addEventListener'):]
        self.assertLess(seg.index("await ask("), seg.index("api().dur_create_timeline"))
        self.assertIn("Không sửa hay xóa timeline đang có", seg)
        self.assertIn("Đang thiếu", seg)                                                         # thiếu thì hộp xác nhận nói rõ số thiếu
        self.assertNotIn("cut_ready", seg)
        for bad in ("api().inout_write", "api().apply", "api().append_starred", "SetMarkInOut"):
            self.assertNotIn(bad, self.js, bad)


if __name__ == "__main__":
    unittest.main()
