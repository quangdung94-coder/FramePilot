"""Đêm #3: đổi tên hiển thị thành FramePilot + icon. Đổi tên hiển thị thôi; KHÔNG đổi khóa lưu/dữ liệu/tên timeline (đổi sẽ mất dữ liệu cũ)."""
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, ROOT)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


class Ten(unittest.TestCase):
    def test_tieu_de_trang_va_thanh_tren_la_framepilot(self):
        h = rd("app", "troly_web", "index.html")
        self.assertIn("<title>FramePilot</title>", h)
        self.assertIn('<span class="brand-title">FramePilot</span>', h)
        self.assertNotIn("<title>Trợ lý File Quay", h)

    def test_cua_so_pywebview_va_taskbar(self):
        p = rd("app", "panel_troly_web.py")
        self.assertIn("troly_env.window_title(a.project)", p)                                  # tiêu đề cửa sổ (S3 19/11: dùng chung với đoạn tìm cửa sổ cũ)
        import troly_env
        self.assertEqual(troly_env.window_title("X"), "FramePilot - X")
        self.assertIn('APP_ID = "FramePilot"', p)                                              # nhóm riêng trên taskbar (không gộp với python.exe)
        self.assertIn("SetCurrentProcessExplicitAppUserModelID(APP_ID)", p)
        self.assertIn("win.events.shown += lambda: set_window_icon(win)", p)
        self.assertIn("WM_SETICON = 0x80", p)                                                  # icon cho titlebar và taskbar
        self.assertIn('os.path.join(HERE, "assets", "framepilot.ico")', p)

    def test_menu_davinci_tro_ten_moi_va_khong_tu_xoa_muc_cu(self):
        import install
        self.assertEqual(install.NAME, "FramePilot.py")
        self.assertEqual(install.OLD_NAME, "VideoAI Trợ lý File Quay.py")
        src = rd("install.py")
        self.assertIn("--remove-old", src)
        self.assertIn("MARKER in f.read()", src)                                               # chỉ xóa file do install.py tạo
        self.assertIn("if remove and mine and not check:", src)                               # không bao giờ xóa khi chỉ kiểm tra / không có cờ

    def test_install_khong_xoa_muc_cu_neu_khong_co_co(self):
        import contextlib
        import io
        import tempfile
        import install
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            old = os.path.join(d, install.OLD_NAME)
            with open(old, "w", encoding="utf-8") as f:
                f.write("# x\n" + install.MARKER + "\n")
            install.old_entry(d, False, False)
            self.assertTrue(os.path.isfile(old))                                               # chỉ nhắc
            install.old_entry(d, True, True)
            self.assertTrue(os.path.isfile(old))                                               # --check: không xóa
            install.old_entry(d, True, False)
            self.assertFalse(os.path.isfile(old))                                              # có cờ + file của mình: xóa
            with open(old, "w", encoding="utf-8") as f:
                f.write("# file của người khác\n")
            install.old_entry(d, True, False)
            self.assertTrue(os.path.isfile(old))                                               # không phải file của mình: giữ

    def test_khong_doi_khoa_luu_va_ten_timeline(self):
        core = rd("app", "troly_core.py") + rd("app", "troly_api.py") + rd("app", "troly_tl.py") + rd("app", "troly_resolve.py")
        self.assertNotIn("FramePilot", core)                                                   # khóa plan / dữ liệu / tên timeline giữ nguyên
        self.assertIn("Rough Cut sao", rd("app", "troly_api.py") + rd("app", "troly_resolve.py") + rd("app", "troly_core.py"))

    def test_hop_thoai_loi_va_tat_may_goi_framepilot(self):
        self.assertIn('"FramePilot", 0x10', rd("app", "troly_env.py"))
        self.assertIn("FramePilot: phân tích xong", rd("app", "troly_batch.py"))


class Icon(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(ROOT, "app", "assets", "framepilot.ico")

    def test_ico_co_trong_repo_du_cac_co(self):
        with open(self.path, "rb") as f:
            d = f.read()
        self.assertEqual(struct.unpack("<HHH", d[:6])[:2], (0, 1))                             # đúng định dạng .ico
        n = struct.unpack("<H", d[4:6])[0]
        sizes = {(d[6 + 16 * i] or 256) for i in range(n)}
        self.assertEqual(sizes, {16, 24, 32, 48, 64, 128, 256})

    def test_dat_icon_khong_co_file_hoac_khong_co_cua_so_thi_bo_qua_khong_loi(self):
        import panel_troly_web as pw

        class Fake:                                                                           # cửa sổ không có .native (không phải Windows / chưa hiện)
            pass
        self.assertFalse(pw.set_window_icon(Fake(), os.path.join(ROOT, "khong_co.ico")))
        self.assertFalse(pw.set_window_icon(Fake(), self.path))


class XungHo(unittest.TestCase):
    """Đêm #4: chữ hiển thị trong panel gọi người dùng là "bạn". Quét mọi chuỗi hiển thị (chuỗi Python không phải docstring, chữ trong html/js không phải chú thích):
    "anh" đứng một mình phải ra 0 chỗ. Chỗ cố ý giữ: "tiếng Anh" (English), không phải đại từ."""

    @staticmethod
    def _py_strings(path):
        import ast
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        doc = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body and isinstance(n.body[0], ast.Expr) \
                    and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str):
                doc.add(n.body[0].value.lineno)               # docstring không hiển thị
        return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.lineno not in doc]

    @staticmethod
    def _web_lines(path):
        import re
        with open(path, encoding="utf-8") as f:
            s = f.read()
        s = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", "", m.group(0)), s, flags=re.S)
        s = re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", "", m.group(0)), s, flags=re.S)
        s = re.sub(r"(?m)(^|\s)//[^\n]*", lambda m: m.group(1), s)
        return s.split("\n")

    @staticmethod
    def _hits(text):
        import re
        out = []
        for m in re.finditer(r"(?<!\w)[Aa]nh(?!\w)", text):
            if text[max(0, m.start() - 6):m.start()].lower().endswith("tiếng "):
                continue                                      # "tiếng Anh" = English
            out.append(text[max(0, m.start() - 30):m.end() + 30])
        return out

    def test_khong_con_chu_anh_dung_mot_minh_trong_chuoi_hien_thi(self):
        import glob
        bad = []
        for f in sorted(glob.glob(os.path.join(ROOT, "app", "**", "*"), recursive=True)):
            rel = os.path.relpath(f, os.path.join(ROOT, "app")).replace("\\", "/")
            if f.endswith(".py"):
                texts = self._py_strings(f)
            elif f.endswith((".js", ".html")):
                texts = self._web_lines(f)
            else:
                continue
            for t in texts:
                for h in self._hits(t):
                    bad.append((rel, h))
        self.assertEqual(bad, [])

    def test_bo_quet_bat_dai_tu_that_va_bo_qua_tieng_anh_anh_hinh_nhanh(self):
        s = "tiếng Anh và ảnh, nhanh, thanh; Anh xếp, của anh."
        self.assertEqual(len(self._hits(s)), 2)               # chỉ "Anh xếp" và "của anh"
        self.assertEqual(self._hits("tiếng Anh"), [])
        self.assertIn('"tiếng Anh"', rd("app", "troly_web", "step3.js"))   # chỗ giữ lại vẫn còn nguyên

    def test_chu_moi_dung_ban(self):
        h = rd("app", "troly_web", "index.html") + rd("app", "troly_web", "step3.js")
        for t in ("chờ bạn duyệt", "Ô viền cam = bạn đã sửa", "In/Out chỉ vào DaVinci khi bạn bấm nút Ghi", "Giữ nguyên clip bạn đã đặt tay"):
            self.assertIn(t, h, t)


if __name__ == "__main__":
    unittest.main()
