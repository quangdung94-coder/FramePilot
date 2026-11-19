"""K3 (19/11): cửa sổ cmd đen chớp khi mở clip. Thủ phạm tìm được: nạp sóng âm (troly_wave.make_peaks gọi ffmpeg KHÔNG có creationflags). (Bản xem nhẹ của trình phát đã bị gỡ ngày 19/11, ADR-0029.)
Mọi lời gọi tiến trình con giờ đi qua troly_proc.chay_an / mo_an."""
import glob
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
sys.path.insert(0, APP)
import troly_proc as tp               # noqa: E402


class Proc(unittest.TestCase):
    def test_khong_con_loi_goi_subprocess_nao_ngoai_troly_proc(self):
        bad = []
        pat = re.compile(r"subprocess\.(Popen|run|check_output|check_call|call)\b|os\.system\(|os\.startfile\(|\brunner=subprocess\.")
        for f in sorted(glob.glob(os.path.join(APP, "*.py"))):
            if os.path.basename(f) == "troly_proc.py":
                continue
            with open(f, encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if pat.search(line.split("#")[0]):
                        bad.append("%s:%d: %s" % (os.path.basename(f), i, line.strip()[:90]))
        self.assertEqual(bad, [])

    def test_cac_cho_chay_ffmpeg_dung_ham_dung_chung(self):
        for f, needle in (("troly_wave.py", "runner=troly_proc.chay_an"), ("troly_kf.py", "runner=troly_proc.chay_an"), ("troly_frames.py", "troly_proc.mo_an("),
                          ("troly_thumbs.py", "troly_proc.chay_an(cmd"),
                          ("troly_speech.py", "troly_proc.chay_an("), ("troly_ai.py", "troly_proc.mo_an("), ("troly_batch.py", "troly_proc.chay_an(")):
            with open(os.path.join(APP, f), encoding="utf-8") as fh:
                self.assertIn(needle, fh.read(), f)

    @unittest.skipUnless(os.name == "nt", "chỉ Windows có cửa sổ console")
    def test_ham_dung_chung_them_co_an_va_giu_co_cua_nguoi_goi(self):
        import subprocess
        seen = {}
        orig = subprocess.run
        subprocess.run = lambda cmd, **kw: seen.update(kw) or "ok"
        try:
            self.assertEqual(tp.chay_an(["x"], creationflags=0x4000, capture_output=True), "ok")
        finally:
            subprocess.run = orig
        self.assertEqual(seen["creationflags"], 0x4000 | 0x08000000)            # giữ độ ưu tiên thấp + thêm CREATE_NO_WINDOW
        si = seen["startupinfo"]
        self.assertTrue(si.dwFlags & subprocess.STARTF_USESHOWWINDOW)
        self.assertEqual(si.wShowWindow, 0)                                      # SW_HIDE
        self.assertTrue(seen["capture_output"])

    @unittest.skipUnless(os.name == "nt", "chỉ Windows có cửa sổ console")
    def test_chay_that_khong_tao_cua_so_console(self):
        r = tp.chay_an([sys.executable, "-c", "print('xin chao')"], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "xin chao"))
        p = tp.mo_an([sys.executable, "-c", "import sys; sys.stdout.write('a')"], stdout=-1)
        self.assertEqual(p.communicate()[0], b"a")


if __name__ == "__main__":
    unittest.main()
