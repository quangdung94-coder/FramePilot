"""S3 (19/11/2026): mở FramePilot lần hai cho cùng project thì ĐƯA CỬA SỔ CŨ LÊN TRƯỚC (khôi phục nếu đang thu nhỏ); không đưa lên được thì giữ thông báo cũ.
Dùng cửa sổ Windows THẬT tạo bằng user32 (không cần DaVinci). Việc mở qua menu DaVinci thật: CHƯA CHẠY THẬT."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import troly_env  # noqa: E402


@unittest.skipUnless(os.name == "nt", "chỉ Windows")
class BringToFront(unittest.TestCase):
    def _make(self, title):
        import ctypes
        u = ctypes.windll.user32
        u.CreateWindowExW.restype = ctypes.c_void_p
        u.CreateWindowExW.argtypes = [ctypes.c_ulong, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        h = u.CreateWindowExW(0, "Static", title, 0x10CF0000, 100, 100, 300, 200, None, None, None, None)   # WS_VISIBLE|WS_OVERLAPPEDWINDOW
        if not h:
            self.skipTest("không tạo được cửa sổ thử (không có desktop)")
        self.addCleanup(lambda: u.DestroyWindow(ctypes.c_void_p(h)))
        return u, ctypes.c_void_p(h)

    def test_khoi_phuc_cua_so_dang_thu_nho(self):
        title = troly_env.window_title("2026.11.06.Lora_Duyên&Phát (thử S3)")
        self.assertEqual(title, "FramePilot - 2026.11.06.Lora_Duyên&Phát (thử S3)")
        u, h = self._make(title)
        u.ShowWindow(h, 6)                                        # SW_MINIMIZE
        self.assertTrue(u.IsIconic(h))
        self.assertTrue(troly_env.bring_to_front(title))
        self.assertFalse(u.IsIconic(h))
        self.assertTrue(u.IsWindowVisible(h))

    def test_khong_thay_cua_so_thi_tra_false(self):
        self.assertFalse(troly_env.bring_to_front("FramePilot - khong-co-project-nay-%d" % os.getpid()))

    def test_loi_user32_thi_tra_false_khong_ne_ngoai_le(self):
        class Boom(object):
            def __getattr__(self, name):
                raise OSError("hỏng")
        self.assertFalse(troly_env.bring_to_front("x", user32=Boom()))


class PanelDungHam(unittest.TestCase):
    def test_panel_dung_chung_tieu_de_va_dua_len_truoc_roi_moi_bao_loi(self):
        src = open(os.path.join(HERE, "..", "app", "panel_troly_web.py"), encoding="utf-8").read()
        self.assertIn("troly_env.window_title(a.project)", src)
        self.assertEqual(src.count("window_title("), 2)               # tạo cửa sổ và tìm cửa sổ cũ cùng một tiêu đề
        i = src.index("if lock is None:")
        body = src[i:i + 700]
        self.assertLess(body.index("bring_to_front"), body.index("fail("))     # đưa lên được thì thoát êm, không thì mới hiện thông báo cũ
        self.assertIn("đang mở cho project", body)


if __name__ == "__main__":
    unittest.main()
