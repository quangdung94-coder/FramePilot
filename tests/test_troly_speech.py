"""Kiểm thử Lời nói giai đoạn A (bước 2): khóa clip, kho dữ liệu, đối chiếu có tiếng/đã chép/lỗi, chạy tiếp, câu tiêu biểu,
tìm chữ, mức kéo âm lượng. Không cần DaVinci, không cần Whisper (giả lập); phần trích âm thanh cần ffmpeg (không có thì bỏ qua)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import troly_speech as sp            # noqa: E402
import troly_speech_run as sr        # noqa: E402
import troly_speech_store as ss      # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def line(t0, t1, text, keys=(), why=()):
    return {"t0": t0, "t1": t1, "text": text, "keys": list(keys), "why": list(why)}


def res(lines, gain=0.0, speech=((0.5, 3.0),), dur=10.0):
    return {"dur": dur, "gain_db": gain, "speech": [list(s) for s in speech], "lines": lines}


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.st = ss.Store(os.path.join(self.tmp, "p.loinoi.sqlite"))

    def tearDown(self):
        self.st.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_headline_nhieu_key_nhat_roi_cau_dai_nhat(self):
        a = [line(0, 1, "câu ngắn"), line(1, 2, "câu có hai cụm", ["a", "b"]), line(2, 3, "câu có một cụm rất dài dòng", ["a"])]
        self.assertEqual(ss.headline(a), "câu có hai cụm")
        b = [line(0, 1, "ngắn"), line(1, 2, "câu này dài hơn hẳn")]
        self.assertEqual(ss.headline(b), "câu này dài hơn hẳn")
        self.assertEqual(ss.headline([line(0, 1, "bịa", why=["hallu"])]), "")     # câu nghi bịa không làm tiêu biểu
        self.assertEqual(ss.headline([]), "")

    def test_khoa_clip_la_duong_dan_tuong_doi_uid_luu_kem(self):
        self.st.put_result("01_footage/DG1.MP4", "uid-1", "DG1.MP4", (100, 5.0), "01:00:00:00",
                           res([line(0, 1, "nhà trai xin phép", ["nhà trai"])]), "vi")
        r = self.st.clip_rows()[0]
        self.assertEqual((r["key"], r["uid"], r["n_keys"], r["tc"]), ("01_footage/DG1.MP4", "uid-1", 1, "01:00:00:00"))
        self.assertEqual(self.st.lines_of("01_footage/DG1.MP4")[0]["keys"], ["nhà trai"])

    def test_clip_chay_tiep_file_doi_thi_chep_lai(self):
        k, sig = "a/x.MP4", (100, 5.0)
        self.assertTrue(self.st.needs_run(k, sig))
        self.st.put_result(k, "u", "x", sig, None, res([line(0, 1, "xin chào")]), "vi")
        self.assertFalse(self.st.needs_run(k, sig))
        self.assertTrue(self.st.needs_run(k, (101, 5.0)))           # kích thước đổi
        self.assertTrue(self.st.needs_run(k, (100, 6.0)))           # ngày sửa đổi
        self.st.put_error("a/y.MP4", "u2", "y", sig, None, "pre", "lỗi")
        self.assertTrue(self.st.needs_run("a/y.MP4", sig))          # lỗi thì chép lại

    def test_co_tieng_nhung_whisper_khong_ra_chu_la_done_co_co_sai(self):
        self.st.put_result("a/z.MP4", "u", "z", (1, 1.0), None, res([]), "vi")
        c = self.st.clip_rows()[0]
        self.assertEqual((c["status"], c["n_lines"], c["suspect"]), ("done", 0, 1))
        self.st.put_result("a/q.MP4", "u", "q", (1, 1.0), None, res([], speech=()), "vi")
        self.assertEqual([r["status"] for r in self.st.clip_rows() if r["key"] == "a/q.MP4"], ["silent"])

    def test_co_the_sai_khi_keo_nhieu_hoac_co_cau_nghi_bia(self):
        self.st.put_result("a/1", "u", "1", (1, 1.0), None, res([line(0, 1, "ok")], gain=sp.WARN_GAIN_DB + 1), "vi")
        self.st.put_result("a/2", "u", "2", (1, 1.0), None, res([line(0, 1, "ok", why=["thua"])]), "vi")
        self.st.put_result("a/3", "u", "3", (1, 1.0), None, res([line(0, 1, "ok")], gain=3.0), "vi")
        sus = {r["key"]: r["suspect"] for r in self.st.clip_rows()}
        self.assertEqual(sus, {"a/1": 1, "a/2": 1, "a/3": 0})

    def test_doi_chieu_khop_va_lech(self):
        s = (1, 1.0)
        self.st.put_result("a/1", "u", "1", s, None, res([line(0, 1, "x")]), "vi")             # đã chép
        self.st.put_result("a/2", "u", "2", s, None, res([], speech=()), "vi")                 # im lặng
        self.st.put_error("a/3", "u", "3", s, None, "pre", "ffmpeg")                           # lỗi trước khi biết có tiếng
        self.st.put_error("a/4", "u", "4", s, None, "whisper", "whisper")                      # có tiếng, lỗi lúc chép
        ok, msg = self.st.reconcile(["a/1", "a/2", "a/3", "a/4"])
        self.assertTrue(ok, msg)
        c = self.st.counts(["a/1", "a/2", "a/3", "a/4"])
        self.assertEqual((c["total"], c["done"], c["silent"], c["err"], c["speech"]), (4, 1, 1, 2, 2))
        ok, msg = self.st.reconcile(["a/1", "a/2", "a/3", "a/4", "a/5"])                       # a/5 không có dòng nào: báo lệch
        self.assertFalse(ok)
        self.assertIn("THIẾU 1", msg)
        self.assertTrue(msg.startswith("LỆCH"))
        self.st.db.execute("UPDATE clips SET n_lines=9 WHERE key='a/1'")                       # số dòng lệch số dòng thật
        ok, msg = self.st.reconcile(["a/1", "a/2", "a/3", "a/4"])
        self.assertFalse(ok)

    def test_tim_chu_trong_ca_project_khong_phan_biet_hoa_thuong_dau_cau(self):
        self.st.put_result("a/1", "u", "1", (1, 1.0), None, res([line(0, 1, "Con xin mời, ba mẹ nâng ly!")]), "vi")
        self.st.put_result("a/2", "u", "2", (1, 1.0), None, res([line(0, 1, "Hôm nay là ngày vui")]), "vi")
        self.assertEqual(self.st.search("NÂNG LY"), {"a/1"})
        self.assertEqual(self.st.search("ngày vui"), {"a/2"})
        self.assertEqual(self.st.search("khong co"), set())
        self.assertEqual(self.st.search("  "), set())

    def test_sua_ngon_ngu_tay_duoc_giu_o_lan_chay_sau(self):
        self.st.put_result("a/1", "u", "1", (1, 1.0), None, res([line(0, 1, "hello")]), "vi")
        self.st.set_lang("a/1", "en")
        self.st.put_result("a/1", "u", "1", (2, 2.0), None, res([line(0, 1, "hello again")]), "vi")   # chép lại
        self.assertEqual(self.st.clip_rows()[0]["lang"], "en")
        self.assertEqual(self.st.lines_of("a/1")[0]["lang"], "en")


class TestSpeechCore(unittest.TestCase):
    def test_tinh_muc_keo(self):
        self.assertEqual(sp.compute_gain({"p95_db": -20.0, "peak": 0.2}), 0.0)
        self.assertEqual(sp.compute_gain({"p95_db": -30.0, "peak": 0.3}), 10.0)
        self.assertEqual(sp.compute_gain({"p95_db": -60.0, "peak": 0.001}, max_gain=12.0), 12.0)       # chặn ở mức tối đa
        g = sp.compute_gain({"p95_db": -40.0, "peak": 0.9})                                            # không làm vỡ tiếng
        self.assertLessEqual(0.9 * 10 ** (g / 20.0), sp.PEAK_CEIL + 1e-6)

    def test_cau_nghi_bia(self):
        speech = [[0.0, 3.0]]
        why = sp.suspect_reasons([(0, 2, "Hãy subscribe cho kênh"), (2, 3, "xin chào"), (3, 4, "xin chào"),
                                  (10, 11, "xin chào"), (0, 8, "ừ")], speech)
        self.assertEqual(why[0], ["hallu"])
        self.assertEqual(why[1], [])
        self.assertIn("lap", why[2])
        self.assertIn("ngoai", why[3])
        self.assertIn("thua", why[4])

    def test_tim_cum_key_va_ngon_ngu_anh(self):
        idx = sp.build_index({"groups": {"g": ["nhà trai", "thắp hương"]}, "variants": {}})
        self.assertEqual([p for _, p in sp.find_keys("Mời NHÀ TRAI vào, thắp hương!", idx)], ["nhà trai", "thắp hương"])
        r, n = sp.english_ratio([(0, 1, "Thank you all for coming today and we love you")])
        self.assertGreater(r, 0.4)
        r, n = sp.english_ratio([(0, 1, "Xin mời ba mẹ nâng ly chúc mừng hai con")])
        self.assertLess(r, 0.1)

    def test_timecode_cong_gio_trong_kho(self):
        self.assertEqual(ss.add_timecode("08:37:00:00", 15, 25.0), "08:37:15:00")
        self.assertEqual(ss.add_timecode("08:37:00:10", 0.4, 25.0), "08:37:00:20")
        self.assertEqual(ss.add_timecode("08:59:59:24", 0.04, 25.0), "09:00:00:00")
        self.assertIsNone(ss.add_timecode("", 5, 25.0))
        self.assertIsNone(ss.add_timecode("08:00:00:00", 5, None))

    def test_khung_gop_va_doi_mac_thoi_gian(self):
        ch = sp.join_chunks([(1.0, 2.0), (2.2, 3.0), (10.0, 11.0)], total=20.0)
        self.assertEqual(len(ch), 2)                        # hai đoạn đầu gộp
        m = sp.concat_map(ch)
        self.assertAlmostEqual(sp.map_time(m[1][0] + 0.5, m), ch[1][0] + 0.5, places=2)


@unittest.skipUnless(HAVE_FFMPEG, "cần ffmpeg")
class TestRunner(unittest.TestCase):
    """Chạy cả lượt với Whisper và VAD giả (không tải gì, không cần GPU) trên file bản sao do ffmpeg tạo."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.files = {}
        for n in ("c1", "c2", "c3", "c4"):
            p = os.path.join(self.tmp, n + ".mp4")
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=4",
                            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=4", "-shortest", p], check=True)
            self.files[n] = p
        self.st = ss.Store(os.path.join(self.tmp, "kho", "p.loinoi.sqlite"))
        self.items = [{"key": "01_footage/%s.mp4" % n, "uid": "u-" + n, "name": n, "path": p, "tc": "01:00:00:00"}
                      for n, p in self.files.items()]
        self.items.append({"key": "01_footage/mat.mp4", "uid": "u-x", "name": "mat", "path": os.path.join(self.tmp, "mat.mp4"),
                           "tc": None})
        self.calls = []
        self._orig = sp.whisper_run
        sp.whisper_run = self._fake_whisper

    def tearDown(self):
        sp.whisper_run = self._orig
        self.st.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fake_whisper(self, cfg, wav, lang="vi", prompt=None):
        self.calls.append(lang)
        if self.fail_whisper_for and len(self.calls) == 2:               # đúng MỘT lần gọi bị lỗi
            raise RuntimeError("Whisper giả lỗi")
        return [(0.0, 1.5, "nhà trai xin phép"), (1.6, 3.0, "mời ba mẹ")], 0.1

    fail_whisper_for = None

    def _run(self, vad):
        idx = sp.build_index({"groups": {"g": ["nhà trai"]}, "variants": {}})
        r = sr.SpeechRun(self.st, cfg={"exe": "x", "model": "y"}, vad_run=vad, index=idx, prompt="p", batch=2)
        return r.run(self.items, "vi")

    def test_ca_luot_doi_chieu_chay_tiep_va_loi(self):
        # c3 im lặng (VAD không thấy tiếng): dùng VAD giả theo độ dài không phân biệt được file, nên đổi VAD theo lượt gọi
        seq = iter([[[0.5, 3.0]], [[0.5, 3.0]], [], [[0.5, 3.0]]])
        s = self._run(lambda y: next(seq))
        self.assertEqual((s["total"], s["done"], s["silent"], s["errors"]), (5, 3, 1, 1))       # 1 lỗi: file "mat" không tồn tại
        self.assertTrue(s["ok"], s["message"])
        self.assertEqual(s["speech"], s["done"])
        self.assertEqual(self.st.clip_rows()[0]["n_keys"] >= 0, True)
        # chạy lại: file không đổi thì bỏ qua hết, riêng file lỗi bị thử lại
        s2 = self._run(lambda y: [[0.5, 3.0]])
        self.assertEqual(s2["skipped"], 4)
        self.assertEqual(s2["errors"], 1)
        # file đổi (ghi thêm) thì chép lại đúng file đó
        with open(self.files["c1"], "ab") as f:
            f.write(b"\0")
        s3 = self._run(lambda y: [[0.5, 3.0]])
        self.assertEqual(s3["skipped"], 3)

    def test_loi_luc_chep_duoc_tinh_vao_co_tieng(self):
        self.fail_whisper_for = True
        s = self._run(lambda y: [[0.5, 3.0]])
        self.assertEqual((s["done"], s["errors"]), (3, 2))                                      # c2 lỗi + file thiếu
        self.assertEqual(s["speech"], 4)                                                       # có tiếng = 3 chép + 1 lỗi lúc chép
        self.assertTrue(s["ok"], s["message"])
        c = self.st.counts([i["key"] for i in self.items])
        self.assertEqual((c["err_pre"], c["err_whisper"]), (1, 1))

    def test_tep_tam_bi_xoa_va_file_goc_khong_doi(self):
        before = {n: (os.path.getsize(p), os.path.getmtime(p)) for n, p in self.files.items()}
        self._run(lambda y: [[0.5, 3.0]])
        after = {n: (os.path.getsize(p), os.path.getmtime(p)) for n, p in self.files.items()}
        self.assertEqual(before, after)
        left = [f for f in os.listdir(tempfile.gettempdir()) if f.startswith("troly_run_")]
        self.assertEqual(left, [])
        self.assertEqual([f for f in os.listdir(self.tmp) if f.endswith((".wav", ".srt"))], [])

    def test_nghi_tieng_anh_chep_lai_bang_en(self):
        en = [(0.0, 2.0, "Thank you all for coming today and we love you so much")]
        orig = self._fake_whisper

        def fake(cfg, wav, lang="vi", prompt=None):
            self.calls.append(lang)
            return en, 0.1
        sp.whisper_run = fake
        self._run(lambda y: [[0.5, 3.0]])
        self.assertIn("en", self.calls)
        self.assertEqual({r["lang"] for r in self.st.clip_rows() if r["status"] == "done"}, {"en"})
        sp.whisper_run = orig


class TestKhoNgoaiMa(unittest.TestCase):
    def test_kho_khong_duoc_nam_trong_thu_muc_ma(self):
        import troly_api as ta
        root = os.path.dirname(os.path.dirname(os.path.abspath(ta.__file__)))
        api = ta.TrolyApi("2026.10.17.LV_Ten", tempfile.mkdtemp(), start_worker=False)
        try:
            self.assertIn("error", api.speech_set_dir(os.path.join(root, "kho_loi_noi")))
            self.assertIn("error", api.speech_set_dir(root))
            d = tempfile.mkdtemp()
            self.assertTrue(api.speech_set_dir(d).get("ok"))
            self.assertEqual(api.speech_info()["dir"], os.path.abspath(d))
        finally:
            api.close()


if __name__ == "__main__":
    unittest.main()
