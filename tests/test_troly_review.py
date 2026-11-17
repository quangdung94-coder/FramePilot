"""Xuất danh sách clip "có thể sai" (mục D): chỉ ĐỌC kho, ghi CSV + SRT ra thư mục dữ liệu, không ghi đè, tối đa 50 clip, không vào thư mục mã.
Dùng dữ liệu giả (chữ mẫu chung)."""
import csv
import hashlib
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import troly_speech_review as rv      # noqa: E402
import troly_speech_srt as sx         # noqa: E402
import troly_speech_store as ss       # noqa: E402


def line(t0, t1, text, why=()):
    return {"t0": t0, "t1": t1, "text": text, "keys": [], "why": list(why)}


def res(lines, gain=0.0, dur=30.0, speech=((1.0, 5.0),)):
    return {"dur": dur, "gain_db": gain, "speech": [list(s) for s in speech], "lines": lines}


class Review(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmp, "kho", "p.loinoi.sqlite")
        st = ss.Store(self.store_path)
        s = (1, 1.0)
        st.put_result("01_footage/DG1.MP4", "u1", "DG1.MP4", s, "01:00:00:00", res([line(1, 3, "câu mẫu một"), line(4, 6, "đăng ký kênh", ["hallu"])]), "vi")
        st.put_result("01_footage/DG2.MP4", "u2", "DG2.MP4", s, "01:10:00:00", res([line(1, 3, "câu mẫu hai")], gain=25.0), "vi")
        st.put_result("01_footage/DG3.MP4", "u3", "DG3.MP4", s, "01:20:00:00", res([]), "vi")                  # có tiếng, Whisper không ra chữ
        st.put_result("01_footage/DG4.MP4", "u4", "DG4.MP4", s, "01:30:00:00", res([line(1, 3, "bình thường")]), "vi")   # không có sai
        st.put_error("01_footage/DG5.MP4", "u5", "DG5.MP4", s, "01:40:00:00", "pre", "lỗi")                   # lỗi: không thuộc danh sách có thể sai
        st.close()
        self.out = os.path.join(self.tmp, "review")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sha(self):
        with open(self.store_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def test_xuat_dung_clip_co_the_sai_va_khong_ghi_vao_kho(self):
        before = self.sha()
        r = rv.export(self.store_path, self.out, "LV_Ten")
        self.assertEqual(self.sha(), before)                                              # kho không đổi một byte (chỉ đọc)
        self.assertEqual(r["clips"], 3)
        with open(r["csv"], encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([x["khoa_clip"] for x in rows], ["01_footage/DG1.MP4", "01_footage/DG2.MP4", "01_footage/DG3.MP4"])   # dòng nghi trước, rồi kéo nhiều
        self.assertEqual(rows[0]["ly_do"], "hallu")
        self.assertEqual(rows[1]["ly_do"], "keo")
        self.assertEqual(rows[2]["ly_do"], "khong_chu")
        self.assertEqual((rows[0]["so_dong"], rows[0]["so_dong_nghi"]), ("2", "1"))

    def test_srt_co_ma_clip_so_dong_nhan_nghi_va_doc_lai_duoc(self):
        r = rv.export(self.store_path, self.out, "LV_Ten")
        with open(r["srt"], encoding="utf-8") as f:
            text = f.read()
        blocks = sx.parse_srt(text)
        self.assertEqual(len(blocks), 3)                                                  # DG1 (2 dòng, cả dòng nghi) + DG2 (1 dòng)
        self.assertIn("[DG1#01] câu mẫu một", blocks[0][2])
        self.assertIn("[DG1#02] [NGHI:hallu] đăng ký kênh", blocks[1][2])
        self.assertIn("[DG2#01]", blocks[2][2])
        self.assertGreater(blocks[2][0], blocks[1][1])                                    # giờ nối tiếp, không chồng
        self.assertEqual(r["lines"], 3)

    def test_gioi_han_50_va_tham_so_limit(self):
        st = ss.Store(self.store_path)
        for i in range(60):
            st.put_result("01_footage/X%02d.MP4" % i, "u", "X%02d.MP4" % i, (1, 1.0), "00:00:00:00", res([line(1, 2, "mẫu", ["thua"])]), "vi")
        st.close()
        self.assertEqual(rv.export(self.store_path, self.out, "p")["clips"], 50)
        self.assertEqual(rv.export(self.store_path, os.path.join(self.tmp, "r2"), "p", limit=5)["clips"], 5)

    def test_khong_ghi_de_file_cu_va_khong_co_clip_sai(self):
        import datetime
        t = datetime.datetime(2026, 11, 18, 9, 0, 0)
        a = rv.export(self.store_path, self.out, "p", now=t)
        b = rv.export(self.store_path, self.out, "p", now=t + datetime.timedelta(seconds=5))
        self.assertNotEqual(a["csv"], b["csv"])
        self.assertTrue(os.path.isfile(a["csv"]) and os.path.isfile(b["csv"]))
        ok = os.path.join(self.tmp, "kho2", "q.loinoi.sqlite")
        st = ss.Store(ok)
        st.put_result("a/Z.MP4", "u", "Z.MP4", (1, 1.0), None, res([line(1, 2, "tốt")]), "vi")
        st.close()
        self.assertEqual(rv.export(ok, os.path.join(self.tmp, "r3"), "q"), {"clips": 0, "lines": 0})
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "r3")))                    # không có gì để xuất thì không tạo thư mục

    def test_cong_cu_khong_nam_trong_thu_muc_ma_va_khong_chua_chu_that(self):
        code = os.path.dirname(os.path.dirname(os.path.abspath(rv.__file__)))
        self.assertFalse(os.path.abspath(self.out).lower().startswith(code.lower() + os.sep))
        src = open(rv.__file__, encoding="utf-8").read()
        self.assertIn("mode=ro", src)                                                      # mở kho ở chế độ chỉ đọc


if __name__ == "__main__":
    unittest.main()
