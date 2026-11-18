"""Trang Bước 3 (ADR-0019): các phần tử chính có mặt, chữ hướng dẫn trên trang có chức năng thật đứng sau, phím đọc bằng event.code,
số không xếp bin ở Bước 3, không có chỗ nào ghi In/Out hay gợi ý tự động vào DaVinci."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web")


def rd(n):
    return open(os.path.join(WEB, n), encoding="utf-8").read()


class Step3Web(unittest.TestCase):
    def setUp(self):
        self.html, self.app, self.pl, self.s3 = rd("index.html"), rd("app.js"), rd("player.js"), rd("step3.js")

    def test_phan_tu_chinh_cua_trang(self):
        for i in ('id="page3"', 'id="p3List"', 'id="p3OnlyStar"', 'id="p3Sug"', 'id="p3Accept"', 'id="p3Tx"', 'id="p3TxList"', 'id="waveBox"', 'id="waveCv"', 'id="ioBar"', 'id="rulesTbl"', 'id="tradTrim"',
                  'id="rulesReset"', 'id="ioWriteStar"', 'id="ioWriteSel"', 'id="ioUndo"', 'id="stageHost3"', 'id="stageHost2"', 'id="stageBox"'):
            self.assertEqual(self.html.count(i), 1, i)                                              # mỗi id đúng một lần
        self.assertIn('<script src="step3.js"></script>', self.html)
        ids = re.findall(r'\bid="([^"]+)"', self.html)
        self.assertEqual(len(ids), len(set(ids)), "id trùng")

    def test_buoc_2_khong_con_thanh_in_out(self):
        p2 = self.html[self.html.index('id="page2"'):self.html.index('id="page3"')]
        for gone in ('id="ioBar"', 'id="ioWriteStar"', 'id="ioUndo"', 'id="ioRule"'):
            self.assertNotIn(gone, p2)
        self.assertIn('id="stageHost2"', p2)                                                        # vẫn xem được clip ở Bước 2

    def test_chu_huong_dan_co_chuc_nang_that(self):
        keys = self.html[self.html.index('<span class="keys p3-keys">'):]
        keys = keys[:keys.index("</span>")]
        for k in ("Space", "KeyI", "KeyO", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "KeyJ"):
            self.assertIn('"%s"' % k, self.pl + self.app, k)                                        # mỗi phím nêu trên trang có code xử lý
        self.assertIn('e.code !== "KeyA"', self.s3)                                                 # A nhận gợi ý (Bước 3)
        for t in ("←/→", "↑/↓", "<b>A</b> nhận gợi ý"):
            self.assertIn(t, keys)
        self.assertIn('ioBar").addEventListener("mousedown"', self.pl)                              # kéo hai mép
        self.assertIn('waveBox").addEventListener("mousedown"', self.pl)                            # bấm sóng âm để lướt
        for fn in ("set_bin_rule", "reset_bin_rule", "set_trad_trim", "wave"):
            self.assertIn("api()." + fn, self.s3, fn)

    def test_phim_doc_bang_event_code_khong_dung_event_key(self):
        for src in (self.pl, self.s3):
            self.assertNotRegex(src, r"\be\.key\b")
        p3 = self.app[self.app.index("if (page === 3) {"):]
        p3 = p3[:p3.index("if (page !== 2 ||")]
        self.assertNotIn("e.key", p3)
        self.assertIn("INPUT|SELECT|TEXTAREA", p3)                                                  # bỏ qua khi đang gõ ô chữ
        self.assertNotIn("digitOf", p3)                                                             # phím số không xếp bin ở Bước 3
        self.assertIn('/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) && e.target.type !== "range"', self.pl)

    def test_i_o_chi_chay_o_buoc_3(self):
        self.assertIn('page !== 3 && (e.code === "KeyI" || e.code === "KeyO")', self.pl)

    def test_khong_goi_ghi_davinci_tu_trang_nay(self):
        for src in (self.s3, self.html):
            for bad in ("SetMarkInOut", "inout_write(", "AddSubFolder", "MoveClips"):
                self.assertNotIn(bad, src, bad)
        self.assertIn('api().inout_write(', self.pl)                                                # chỉ nút Ghi (qua hộp xác nhận) mới ghi
        self.assertIn("await ask(", self.pl[self.pl.index("async function plWrite"):self.pl.index("async function plWrite") + 900])


if __name__ == "__main__":
    unittest.main()
