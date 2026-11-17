"""Kiểm tra tĩnh giao diện tab "4 · Lời nói" (app/troly_web). Đánh số bước đã đổi 17/11/2026:
1 Giai đoạn, 2 Phân loại bin, 3 In/Out, 4 Lời nói (mới), 5 Thời lượng."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web")


def read(name):
    with open(os.path.join(WEB, name), "r", encoding="utf-8") as f:
        return f.read()


class TabsLoiNoi(unittest.TestCase):
    def setUp(self):
        self.html, self.js, self.sp, self.css = read("index.html"), read("app.js"), read("speech.js"), read("style.css")

    def test_nhan_tab_va_so_buoc(self):
        tabs = re.findall(r'<a href="#" data-page="(\d)" class="step">([^<]+)</a>', self.html)
        self.assertEqual(tabs, [("1", "1 · Giai đoạn"), ("2", "2 · Phân loại bin"), ("3", "3 · In / Out"),
                                ("4", "4 · Lời nói"), ("5", "5 · Thời lượng")])
        self.assertNotIn("4 · Thời lượng", self.html)
        self.assertNotIn("Bước 4 · Thời lượng", self.html)
        self.assertIn("Bước 5 · Thời lượng", self.html)

    def test_trang_va_dau_vao_theo_so_moi(self):
        for pid in ("page1", "page2", "page4", "page5"):
            self.assertIn('id="%s"' % pid, self.html)
        self.assertIn('$("page5").classList.toggle("hidden", page !== 5)', self.js)
        self.assertIn('$("right5").classList.toggle("hidden", page !== 5)', self.js)
        self.assertIn("[1, 2, 3, 4, 5].includes(ui.page)", self.js)

    def test_script_loi_noi_nap_sau_app(self):
        self.assertLess(self.html.index('src="app.js"'), self.html.index('src="speech.js"'))

    def test_phim_tat_loi_noi_dung_event_code_va_bo_qua_o_nhap(self):
        key = self.sp[self.sp.index("function lnKey"):][:600]
        self.assertIn('e.code === "KeyJ"', key)
        self.assertNotRegex(key, r"e\.key\s*===?\s*[\"']j[\"']")
        self.assertIn("INPUT|SELECT|TEXTAREA", key)
        self.assertIn("if (page === 4) { lnKey(e); return; }", self.js)

    def test_phan_sau_hien_mo_ghi_sap_co(self):
        self.assertRegex(self.html, r'id="lnExport" disabled[^>]*>[^<]*sắp có')
        self.assertRegex(self.html, r'class="btn ln-deep" disabled[^>]*>[^<]*sắp có')
        self.assertRegex(self.html, r'class="seg-off" disabled[^>]*>Tầng 2')

    def test_dat_in_out_chi_luu_vao_ke_hoach_khong_ghi_davinci(self):
        self.assertIn("speech_set_inout", self.sp)
        for bad in ("SetMarkInOut", "set_mark", "reveal("):
            self.assertNotIn(bad, self.sp)

    def test_mau_thanh_va_chu_thich_theo_demo(self):
        for col in ("#A9CF62", "#5B9BF5", "#E0B860"):                      # key xanh lá, người nói xanh dương, méo vàng
            self.assertIn(col, self.css)
        for text in ("Có cụm key lễ cưới", "Có người nói", "Tiếng méo, kết quả có thể sai", "Im lặng", "Đoạn gợi ý In / Out",
                     "Chỉ clip có cụm key", "Tiếng nói từ 20 giây", "Tìm chữ", "Gắn sao (J)", "Đặt In / Out"):
            self.assertIn(text, self.html)


if __name__ == "__main__":
    unittest.main()
