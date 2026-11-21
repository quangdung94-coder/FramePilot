"""B7 (19/11): Space ở Bước 2 phát/dừng clip đang chọn; chưa có proxy thì BÁO RÕ lý do chứ không im lặng. Đọc event.code, chặn Space làm nút đang focus bị bấm lại."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web")


def read(n):
    with open(os.path.join(WEB, n), encoding="utf-8") as f:
        return f.read()


class SpaceBuoc2(unittest.TestCase):
    def setUp(self):
        self.js = read("player.js")

    def test_phim_doc_bang_event_code_o_buoc_2_va_3(self):
        m = re.search(r'document\.addEventListener\("keydown".*?\n\}, true\);', self.js[self.js.index("phím: Space"):], re.S)
        self.assertIn('e.code === "Space"', m.group(0))
        self.assertIn("page !== 2 && page !== 3", m.group(0))
        self.assertNotIn("e.key", m.group(0))

    def test_khong_proxy_thi_space_bao_ly_do_khong_im_lang(self):
        body = self.js[self.js.index("function plToggle()"):self.js.index("function plStop()")]
        self.assertIn("status(", body)
        self.assertIn("Chưa có proxy", body)
        self.assertIn("Space không phát được", body)

    def test_nha_phim_space_khong_bam_lai_nut_dang_focus(self):
        self.assertRegex(self.js, re.compile(r'addEventListener\("keyup".*?e\.code !== "Space".*?preventDefault', re.S))


if __name__ == "__main__":
    unittest.main()
