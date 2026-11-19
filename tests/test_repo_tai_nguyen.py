"""Kiểm git 19/11/2026: máy mới clone kho về phải có đủ file nhỏ cần thiết; tài liệu không bị chen ký tự điều khiển vào đường dẫn Windows."""
import glob
import json
import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


class TaiNguyen(unittest.TestCase):
    def test_config_mau_hop_le_va_du_khoa(self):
        with open(os.path.join(ROOT, "config.example.json"), encoding="utf-8") as f:
            c = json.load(f)
        for k in ("data_root", "proxy_root", "resolve", "whisper"):
            self.assertIn(k, c)
        self.assertIn("install_path", c["resolve"])
        self.assertEqual(sorted(c["whisper"]), ["exe", "model"])

    def test_file_nho_can_thiet_co_mat(self):
        for p in ("app/assets/framepilot.ico", "app/wedding_phrases.json", "install.py", "requirements.txt", "requirements_ai.txt",
                  "requirements_speech.txt", "config.example.json"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, p)), p)
        with open(os.path.join(ROOT, "requirements_speech.txt"), encoding="utf-8") as f:
            t = f.read()
        self.assertIn("numpy", t)
        self.assertIn("silero-vad", t)

    def test_gitignore_khong_chan_file_can_thiet(self):
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as f:
            pats = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        self.assertIn("config.json", pats)                                   # config thật không lên git
        self.assertNotIn("config.example.json", pats)
        for bad in ("*.json", "*.txt", "*.ico", "*.md", "app/", "*.js"):
            self.assertNotIn(bad, pats, bad)

    def test_tai_lieu_khong_co_ky_tu_dieu_khien(self):
        """Đường dẫn Windows viết trong chuỗi thường bị ăn thành tab / xóa lùi (\t, \b, \a). Tài liệu .md không được có các ký tự đó."""
        bad = []
        for f in glob.glob(os.path.join(ROOT, "*.md")) + glob.glob(os.path.join(ROOT, "docs", "**", "*.md"), recursive=True):
            with open(f, encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\t]", line):
                        bad.append("%s:%d" % (os.path.relpath(f, ROOT), i))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
