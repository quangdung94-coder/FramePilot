"""Giao diện Bước 5 bản 3 TIMELINE KÉO THẢ (ADR-0013, theo design/5_timeline_keo_tha): phần tử có mặt, nhãn theo demo, chức năng nêu trên trang có thật,
kéo thả bằng pointer events, phím đọc bằng event.code, tạo timeline chỉ sau hộp xác nhận."""
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
        for i in ("durTarget", "d5Res", "d5Tl", "d5Ruler", "d5V2", "d5V1", "d5A1", "d5A2", "d5Order", "d5Warn", "d5RTitle", "d5Why", "d5SugA", "d5SugB", "d5SugC",
                  "d5SugD", "d5SugE", "d5Create", "d5Reset", "d5FootL"):
            self.assertEqual(self.html.count('id="%s"' % i), 1, i)
        ids = re.findall(r'\bid="([^"]+)"', self.html)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn('<script src="step5.js"></script>', self.html)
        self.assertNotIn("right5", self.html + self.app)

    def test_nhan_theo_demo(self):
        for t in ("Xếp cụm sự kiện lên timeline", "VIDEO MỤC TIÊU", "Xếp lại theo giờ quay", "V2", "V1", "A1", "A2", "Kéo thân khối = dời chỗ", "Kéo mép phải = đổi thời lượng",
                  "Kéo khối con lên V2", "vạch chéo = đang tắt tiếng", "giờ quay thật là thứ tự mặc định", "Gợi ý cách xử lý", "Đưa lên Timeline mới", "Chưa ghi gì vào DaVinci"):
            self.assertIn(t, self.p5, t)
        for t in ("Hiện Tại", "Thứ tự trong cụm", "BIN CON", "LẤY (gốc → ra)", "TRACK", "TỐC ĐỘ", "TIẾNG", "GHI CHÚ", "xếp tay", "V2 · chồng", "Slow mượt tự tính",
                  "nhiều mức", "thả vào đây", "thiếu", "mục tiêu", "không cộng"):
            self.assertIn(t, self.js, t)

    def test_chuc_nang_nhu_chu_tren_trang_co_that(self):
        for fn in ("dur_state", "dur_set_target", "dur_set_stage", "dur_set_bin_take", "dur_toggle_lock", "dur_rebalance", "dur_lower_target", "dur_tl_unslow", "dur_fit_over",
                   "dur_tl_move_cluster", "dur_tl_move_block", "dur_tl_set_track", "dur_tl_set_speed", "dur_tl_set_mute", "dur_tl_reset", "dur_create_timeline"):
            self.assertIn("api()." + fn, self.js, fn)
        self.assertIn("renderPage5()", self.app)
        self.assertIn("goPage(3)", self.js)
        self.assertIn("p3View(", self.js)

    def test_keo_tha_bang_pointer_events_va_phim_event_code(self):
        for ev in ("pointerdown", "pointermove", "pointerup", "pointercancel"):
            self.assertIn(ev, self.js, ev)
        self.assertIn("touch-action: none", self.css)
        self.assertIn("ew-resize", self.css)
        self.assertIn("e.code", self.js)
        self.assertNotIn("e.key", self.js)
        self.assertIn("Math.min(avail", self.js)                                              # kéo mép phải không vượt Có (theo RA TIMELINE)
        for cls in ("tl-drop", "tl-re", "tl-grip", "tl-fh", "tl-cb"):                         # vạch cam "thả vào đây", mép phải, chấm kéo dòng, thân khối mẹ/con
            self.assertIn(cls, self.js + self.css, cls)
        self.assertIn("e.shiftKey", self.js)                                                  # giữ Shift: tinh chỉnh

    def test_khong_con_thanh_keo_cu_va_ten_lop_khong_dung_do_voi_app(self):
        for bad in ('id="d5Cut"', "d5-grip", "dur_cut", "dur_set_share", "cut_ready", "Cắt gọt cho vừa"):
            self.assertNotIn(bad, self.html + self.js, bad)
        self.assertNotRegex(self.js, r'" sel"|\bclass="sel\b')                                # .sel của app là ô chọn cao 40 px: từng làm méo khung cụm

    def test_tao_timeline_chi_sau_hop_xac_nhan_va_ghi_du_thieu_slow_tat_tieng(self):
        seg = self.js[self.js.index('$("d5Create").addEventListener'):]
        self.assertLess(seg.index("await ask("), seg.index("api().dur_create_timeline"))
        for t in ("Không sửa hay xóa timeline đang có", "Đang thiếu", "Đang dư", "Khối Slow", "Khối tắt tiếng", "Độ dài V1", "mục tiêu", "Số clip", "2 track hình V1, V2"):
            self.assertIn(t, seg, t)
        for bad in ("api().inout_write", "api().apply", "api().append_starred", "SetMarkInOut"):
            self.assertNotIn(bad, self.js, bad)

    def test_xac_nhan_khi_xep_lai_neu_da_xep_tay(self):
        seg = self.js[self.js.index('$("d5Reset").addEventListener'):self.js.index('$("d5SugA")')]
        self.assertIn("tl_manual", seg)
        self.assertLess(seg.index("await ask("), seg.index("dur_tl_reset"))


if __name__ == "__main__":
    unittest.main()
