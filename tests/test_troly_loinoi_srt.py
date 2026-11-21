"""Xuất SRT (mục A4): mã clip + số dòng trong dòng chữ, giờ nối tiếp liên tục, xuất theo giai đoạn / phần đã chọn / một clip,
và KIỂM THỬ VÒNG ĐỦ: xuất -> đọc lại (kể cả sau khi dịch) -> ghép đúng clip và đúng giờ gốc. Không cần DaVinci hay Whisper."""
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import troly_speech_srt as sx           # noqa: E402
import troly_speech_store as ss         # noqa: E402
from test_troly_loinoi_api import ApiFixture, line, res      # noqa: E402


class TestSrtCore(unittest.TestCase):
    def test_ma_clip_duy_nhat_va_on_dinh(self):
        k = ["01_footage/DG1.MP4", "01_footage/DG2.MP4"]
        c = sx.clip_codes(k)
        self.assertEqual(c, {"01_footage/DG1.MP4": "DG1", "01_footage/DG2.MP4": "DG2"})
        dup = ["a/DG1.MP4", "b/DG1.MP4", "c/DG9.MP4"]                       # hai máy trùng tên file
        c1, c2 = sx.clip_codes(dup), sx.clip_codes(list(reversed(dup)))
        self.assertEqual(c1, c2)                                            # không phụ thuộc thứ tự
        self.assertEqual(len(set(c1.values())), 3)
        self.assertTrue(c1["a/DG1.MP4"].startswith("DG1@") and c1["c/DG9.MP4"] == "DG9")

    def test_gio_srt_va_chu_nhieu_dong(self):
        self.assertEqual(sx.srt_time(3661.5), "01:01:01,500")
        self.assertEqual(sx.srt_time(-1), "00:00:00,000")
        self.assertEqual(sx.one_line("a\n  b\tc"), "a b c")

    def test_gio_noi_tiep_ma_trong_chu_va_dong_nghi_bia_bi_bo(self):
        clips = [{"key": "k1", "code": "A1", "dur": 10.0, "lines": [
                    {"idx": 0, "t0": 1.0, "t1": 2.0, "text": "xin chào", "why": []},
                    {"idx": 1, "t0": 3.0, "t1": 4.0, "text": "đăng ký kênh", "why": ["hallu"]}]},
                 {"key": "k2", "code": "B2", "dur": 5.0, "lines": [{"idx": 0, "t0": 0.5, "t1": 1.5, "text": "tạm biệt", "why": []}]}]
        text, n, skipped, layout = sx.build_srt(clips)
        self.assertEqual((n, skipped), (2, 1))
        self.assertEqual([l["offset"] for l in layout], [0.0, 11.0])        # 10 s + 1 s đệm
        blocks = sx.parse_srt(text)
        self.assertEqual(blocks[0], (1.0, 2.0, "[A1#01] xin chào"))
        self.assertEqual(blocks[1], (11.5, 12.5, "[B2#01] tạm biệt"))
        self.assertEqual([m for m in re.findall(r"(?m)^(\d+)$", text)], ["1", "2"])    # số thứ tự SRT liên tục
        single, _, _, lay1 = sx.build_srt(clips[1:], continuous=False)
        self.assertEqual(sx.parse_srt(single)[0][0], 0.5)                    # SRT một clip: giờ gốc
        self.assertEqual(lay1[0]["offset"], 0.0)

    def test_doc_lai_sau_khi_dich_van_ghep_dung(self):
        lines = {"k1": [{"idx": 0, "t0": 1.0, "t1": 2.0}], "k2": [{"idx": 0, "t0": 0.5, "t1": 1.5}]}
        srt = "1\n00:00:01,000 --> 00:00:02,000\n[A1#01] Hello there\n\n2\n00:00:11,500 --> 00:00:12,500\n[B2#01] Goodbye\n\n3\n00:00:13,000 --> 00:00:14,000\n[ZZ#09] ?\n\n4\n00:00:15,000 --> 00:00:16,000\nkhông mã\n"
        r = sx.read_back(srt, {"A1": "k1", "B2": "k2"}, lambda k: lines[k])
        self.assertEqual([(m["key"], m["idx"], m["offset"], m["text"]) for m in r["matches"]],
                         [("k1", 0, 0.0, "Hello there"), ("k2", 0, 11.0, "Goodbye")])
        self.assertEqual(r["unknown"], ["ZZ"])
        self.assertEqual(len(r["bad"]), 1)
        self.assertEqual(r["inconsistent"], [])

    def test_phat_hien_gio_lech_khong_deu_trong_mot_clip(self):
        lines = {"k1": [{"idx": 0, "t0": 1.0, "t1": 2.0}, {"idx": 1, "t0": 3.0, "t1": 4.0}]}
        srt = "1\n00:00:01,000 --> 00:00:02,000\n[A1#01] a\n\n2\n00:00:09,000 --> 00:00:10,000\n[A1#02] b\n"
        r = sx.read_back(srt, {"A1": "k1"}, lambda k: lines[k])
        self.assertEqual(r["inconsistent"], ["k1"])

    def test_ten_file_an_toan(self):
        self.assertEqual(sx.safe_name('Gia tiên: "lễ" / 1?'), "Gia tiên lễ 1")
        self.assertEqual(sx.safe_name("  .. "), "project")


class TestExportApi(ApiFixture, unittest.TestCase):
    def setUp(self):
        ApiFixture.setUp(self)
        self.out = tempfile.mkdtemp()
        api = self.api
        with api._lock:
            api._plan["stages"] = []
        api.add_stage()
        api.set_stage(0, {"name": "Gia tiên", "start_txt": "08:00", "end_txt": "08:25", "bins": []})
        api.add_stage()
        api.set_stage(1, {"name": "Lễ: nhà hàng", "start_txt": "08:25", "end_txt": "09:00", "bins": []})
        api._assign = {}
        api._recount()

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)
        ApiFixture.tearDown(self)

    def uid(self, n):
        return next(c.uid for c in self.api._clips if c.name == "DG%s.MP4" % n)

    def read(self, name):
        with open(os.path.join(self.out, name), "r", encoding="utf-8") as f:
            return f.read()

    def back(self, text):
        keys = [r["key"] for r in self.st.clip_rows()]
        inv = {v: k for k, v in sx.clip_codes(keys).items()}
        return sx.read_back(text, inv, self.st.lines_of)

    def test_moi_giai_doan_mot_file(self):
        r = self.api.speech_export("stages", None, self.out)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(sorted(f["name"] for f in r["files"]), ["01 Gia tiên.srt", "02 Lễ nhà hàng.srt"])    # ký tự cấm bị thay
        by = {f["name"]: f for f in r["files"]}
        self.assertEqual((by["01 Gia tiên.srt"]["clips"], by["01 Gia tiên.srt"]["lines"]), (2, 4))          # a (3 dòng) + b (1 dòng)
        self.assertEqual((by["02 Lễ nhà hàng.srt"]["clips"], by["02 Lễ nhà hàng.srt"]["lines"]), (1, 1))    # d; c im lặng không xuất
        self.assertEqual(r["skipped_lines"], 0)
        t = self.read("01 Gia tiên.srt")
        self.assertIn("[DGA#02] nhà trai xin phép", t)                       # mã clip + số dòng nằm ngay trong dòng chữ
        self.assertNotIn("DGC", t)

    def test_vong_du_xuat_doc_lai_ghep_dung_clip_va_gio_goc(self):
        self.api.speech_export("stages", None, self.out)
        t = self.read("01 Gia tiên.srt")
        r = self.back(t)
        self.assertEqual((r["unknown"], r["bad"], r["inconsistent"]), ([], [], []))
        got = {(m["key"], m["idx"]): m for m in r["matches"]}
        ka, kb = self.keys["a"], self.keys["b"]
        self.assertEqual(sorted(got), [(ka, 0), (ka, 1), (ka, 2), (kb, 0)])
        for (k, i), m in got.items():                                       # giờ gốc = giờ SRT trừ độ lệch của clip
            self.assertAlmostEqual(m["srt_t0"] - m["offset"], self.st.lines_of(k)[i]["t0"], places=2)
            self.assertAlmostEqual(m["orig_t0"], self.st.lines_of(k)[i]["t0"], places=2)
        self.assertEqual({m["offset"] for m in r["matches"] if m["key"] == ka}, {0.0})
        self.assertEqual({m["offset"] for m in r["matches"] if m["key"] == kb}, {61.0})      # a dài 60 s + 1 s đệm
        # giờ hiển thị trong panel = timecode bắt đầu của file + giờ gốc
        m = got[(ka, 1)]
        self.assertEqual(ss.add_timecode("08:10:00:00", m["orig_t0"], 50.0), "08:10:10:00")
        # các dòng không chồng giờ và tăng dần qua các clip
        starts = [m["srt_t0"] for m in r["matches"]]
        self.assertEqual(starts, sorted(starts))

    def test_dich_xong_van_ghep_ve_dung_clip(self):
        self.api.speech_export("stages", None, self.out)
        t = self.read("01 Gia tiên.srt")
        translated = re.sub(r"(\[[^\]]+\]) .*", r"\1 Translated line.", t)
        r = self.back(translated)
        self.assertEqual(len(r["matches"]), 4)
        self.assertTrue(all(m["text"] == "Translated line." for m in r["matches"]))
        self.assertEqual(r["inconsistent"], [])

    def test_xuat_phan_da_chon_va_mot_clip(self):
        r = self.api.speech_export("selection", [self.uid("d"), self.uid("a")], self.out)
        self.assertEqual([f["name"] for f in r["files"]], ["Phần đã chọn (2 clip).srt"])
        got = self.back(self.read("Phần đã chọn (2 clip).srt"))
        self.assertEqual({m["key"] for m in got["matches"]}, {self.keys["a"], self.keys["d"]})
        self.assertEqual({m["offset"] for m in got["matches"] if m["key"] == self.keys["d"]}, {61.0})     # a trước d theo giờ quay
        r = self.api.speech_export("clip", [self.uid("a")], self.out)
        self.assertEqual([f["name"] for f in r["files"]], ["DGA.srt"])
        got = self.back(self.read("DGA.srt"))
        self.assertEqual({m["offset"] for m in got["matches"]}, {0.0})                                   # SRT một clip: giờ gốc
        self.assertEqual([m["srt_t0"] for m in got["matches"]], [2.0, 10.0, 20.0])
        self.assertIn("error", self.api.speech_export("selection", [], self.out))                       # chưa chọn gì
        self.assertIn("error", self.api.speech_export("clip", [self.uid("c")], self.out))               # clip im lặng không có chữ

    def test_dong_nghi_bia_bi_bo_va_duoc_bao(self):
        self.st.put_result(self.keys["b"], "ub", "b", (1, 1.0), "08:20:00:00",
                           res([line(5, 8, "ok"), line(10, 12, "đăng ký kênh", why=["hallu"])], ((5, 12),), 40.0), "vi")
        r = self.api.speech_export("stages", None, self.out)
        self.assertEqual(r["skipped_lines"], 1)
        self.assertNotIn("đăng ký kênh", self.read("01 Gia tiên.srt"))

    def test_khong_ghi_de_file_da_co_va_khong_xuat_vao_thu_muc_ma(self):
        self.api.speech_export("stages", None, self.out)
        before = self.read("01 Gia tiên.srt")
        r = self.api.speech_export("stages", None, self.out)
        names = sorted(f["name"] for f in r["files"])
        self.assertTrue(all("(" in n for n in names), names)                # lần hai thêm giờ vào tên
        self.assertEqual(self.read("01 Gia tiên.srt"), before)             # file cũ giữ nguyên
        code = os.path.dirname(os.path.dirname(os.path.abspath(sx.__file__)))
        self.assertIn("error", self.api.speech_export("stages", None, os.path.join(code, "xuat")))
        self.assertEqual([f for f in os.listdir(self.out) if f.endswith(".tmp")], [])

    def test_hop_chon_thu_muc_huy_thi_khong_xuat(self):
        import json
        cfg_p = os.path.join(self.out, "_cfg_srt_test.json")
        with open(cfg_p, "w", encoding="utf-8") as fh:
            json.dump({"data_root": self.out, "srt_root": ""}, fh)
        old_cfg = os.environ.get("TROLY_CONFIG")
        os.environ["TROLY_CONFIG"] = cfg_p
        try:
            self.api.pick_dir_fn = lambda: None
            self.assertEqual(self.api.speech_export("stages"), {"cancel": True})
            self.api.pick_dir_fn = lambda: self.out
            self.assertTrue(self.api.speech_export("stages").get("ok"))
        finally:
            if old_cfg is None:
                os.environ.pop("TROLY_CONFIG", None)
            else:
                os.environ["TROLY_CONFIG"] = old_cfg


if __name__ == "__main__":
    unittest.main()
