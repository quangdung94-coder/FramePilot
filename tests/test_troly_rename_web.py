"""Kiểm tra tĩnh giao diện đổi tên tại chỗ (ADR-0015): bấm đúp, Enter đổi, Esc hủy, gõ trong ô sửa không bị coi là phím tắt,
chỉ đổi trong kế hoạch (không gọi gì sang DaVinci), hộp xác nhận Áp dụng nhắc bin cũ còn lại rỗng."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web")


def read(name):
    with open(os.path.join(WEB, name), "r", encoding="utf-8") as f:
        return f.read()


class RenameWeb(unittest.TestCase):
    def setUp(self):
        self.js, self.html, self.css = read("app.js"), read("index.html"), read("style.css")
        self.fn = self.js[self.js.index("function inlineRename("):]
        self.fn = self.fn[:self.fn.index("\n}\n") + 3]

    def test_enter_doi_esc_huy_va_phim_tat_khong_bat_duoc_trong_o_sua(self):
        self.assertIn('e.key === "Enter"', self.fn)
        self.assertIn('e.key === "Escape"', self.fn)
        self.assertIn("e.stopPropagation()", self.fn)                       # gõ số hay chữ J không chạy phím 1–9 / J
        self.assertIn('addEventListener("blur"', self.fn)                    # bấm ra ngoài thì hủy
        self.assertNotRegex(self.fn, r"e\.key\s*===?\s*[\"']\d[\"']")        # không so e.key với chữ số
        self.assertIn("INPUT|SELECT|TEXTAREA", self.js[self.js.index('document.addEventListener("keydown"'):])

    def test_bam_dup_ten_giai_doan_va_bin_con(self):
        self.assertIn('$("pool").addEventListener("dblclick"', self.js)
        self.assertIn('doRename("bin"', self.js)
        self.assertIn('doRename("stage"', self.js)
        self.assertIn("nameClick", self.js)                                  # bước 1: nhận bấm đúp bằng thời gian
        self.assertIn("Bấm đúp để đổi tên.", self.html)
        self.assertIn('title="Bấm đúp để đổi tên giai đoạn"', self.js)

    def test_chi_doi_trong_ke_hoach_khong_goi_davinci(self):
        body = self.js[self.js.index("async function doRename("):self.js.index("function inlineRename(")]
        self.assertIn("api().rename(", body)
        for bad in ("apply(", "undo(", "reveal(", "MoveClips", "DeleteFolders"):
            self.assertNotIn(bad, body)
        self.assertIn("Trợ lý không tự xóa", body)                            # nhắc bin cũ còn lại rỗng

    def test_hop_xac_nhan_ap_dung_nhac_bin_cu_con_lai_rong(self):
        i = self.js.index("async function confirmApply(")
        body = self.js[i:i + 2500]
        self.assertIn("pv.emptied", body)
        self.assertIn("RỖNG", body)
        self.assertIn("Trợ lý không tự xóa bin", body)

    def test_o_sua_ten_co_kieu(self):
        self.assertRegex(self.css, r"\.rename-inp \{[^}]*min-width: 0")


if __name__ == "__main__":
    unittest.main()
