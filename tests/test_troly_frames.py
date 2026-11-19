"""ADR-0016 bản 2 (G2-G5): kho khung nhỏ trong RAM để rê chuột mượt. Dùng ffmpeg GIẢ (một script Python in ra các "JPEG" giả) nên không cần video thật.
Kiểm: tách khung, kế hoạch lấy khung, KHÔNG ghi file ra đĩa, nạp tiến dần, hủy khi đổi clip + làm tiếp, LRU theo số clip và RAM, nạp trước chỉ khi rảnh,
phục vụ qua máy chủ cục bộ chỉ bằng vé, API, và giao diện (rê = vẽ từ RAM, không gọi Python trong lúc rê)."""
import json
import os
import shutil
import sys
import tempfile
import textwrap
import time
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import test_troly as T                # noqa: E402
import troly_api as ta                # noqa: E402
import troly_frames as tf             # noqa: E402
import troly_play as tp               # noqa: E402

WEB = os.path.join(HERE, "..", "app", "troly_web")

FAKE = textwrap.dedent('''
    import sys, time
    n, size, delay, start = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
    out = sys.stdout.buffer
    for i in range(n):
        out.write(b"\\xff\\xd8\\xff\\xe0" + bytes([65 + (i % 26)]) * size)
        out.flush()
        time.sleep(delay)
''')


def rd(n):
    with open(os.path.join(WEB, n), encoding="utf-8") as f:
        return f.read()


class Pure(unittest.TestCase):
    def test_ke_hoach_lay_khung(self):
        self.assertEqual(tf.plan_step(50.0, 60), 2)                     # proxy 50p: một khung mỗi 2 hình = 25 khung/giây
        self.assertEqual(tf.plan_step(25.0, 60), 1)
        self.assertEqual(tf.plan_step(60.0, 60), 2)
        self.assertEqual(tf.plan_step(50.0, 300), 4)                    # clip dài hơn 120 giây: thưa gấp đôi để khỏi vượt RAM
        self.assertEqual(tf.plan_step(None, 10), 1)

    def test_tach_khung_jpeg(self):
        a, b, c = b"\xff\xd8\xff\xe0AAA", b"\xff\xd8\xff\xe0BB\xff\x00BB", b"\xff\xd8\xff\xe0C"
        fr, rest = tf.split_jpegs(a + b + c)
        self.assertEqual(fr, [a, b])                                    # khung cuối chưa chắc đủ: giữ lại làm phần dư
        self.assertEqual(rest, c)
        fr, rest = tf.split_jpegs(a + b + c, final=True)
        self.assertEqual((fr, rest), ([a, b, c], b""))
        self.assertEqual(tf.split_jpegs(b"rac khong co khung"), ([], b""))

    def test_lenh_ffmpeg_chi_doc_proxy_va_ra_ong_khong_ghi_dia(self):
        cmd = tf.build_cmd("ffmpeg", r"F:\p\a.mov", 2, 0.0, None)
        self.assertEqual(cmd[-1], "-")                                  # ra stdout, không có đường dẫn file đầu ra
        self.assertIn("image2pipe", cmd)
        self.assertIn("mjpeg", cmd)
        self.assertIn("-an", cmd)
        self.assertIn("select=not(mod(n\\,2))", " ".join(cmd))
        self.assertIn("scale=640:640:force_original_aspect_ratio=decrease", " ".join(cmd))
        self.assertNotIn("lut3d", " ".join(cmd))
        c2 = tf.build_cmd("ffmpeg", r"F:\p\a.mov", 2, 12.5, "lut_x.cube")
        self.assertIn("lut3d=file=lut_x.cube", " ".join(c2))             # cùng cách áp LUT như thumbnail
        self.assertEqual(c2[c2.index("-ss") + 1], "12.500")             # làm tiếp từ chỗ đã có
        src = open(os.path.join(HERE, "..", "app", "troly_frames.py"), encoding="utf-8").read()
        for bad in ('"wb"', "os.replace", "imwrite", "shutil.copy", "-y"):
            self.assertNotIn(bad, src, bad)                             # không ghi file khung ra đĩa, không tạo proxy/bản nhẹ

    def test_duong_dan_khung(self):
        self.assertEqual(tf.parse_path("/f/" + "a" * 24 + "/17"), ("a" * 24, 17))
        self.assertEqual(tf.parse_path("/f/" + "a" * 24 + "/info"), ("a" * 24, "info"))
        for bad in ("/f/../17", "/f/abc/1", "/f/" + "a" * 24 + "/-1", "/f/" + "a" * 24 + "/1/../2", "/v/" + "a" * 24):
            self.assertIsNone(tf.parse_path(bad), bad)


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.script = os.path.join(self.tmp, "fake_ffmpeg.py")
        with open(self.script, "w", encoding="utf-8") as f:
            f.write(FAKE)
        self.cfg = {"n": 12, "size": 100, "delay": 0.0}
        self._orig = tf.build_cmd
        tf.build_cmd = lambda ff, src, step, start_t=0.0, lut=None, width=640: [sys.executable, self.script, str(self.cfg["n"]), str(self.cfg["size"]), str(self.cfg["delay"]), "%.3f" % start_t]
        self.src = os.path.join(self.tmp, "a.mov")
        open(self.src, "wb").write(b"x")
        self.st = tf.FrameStore(os.path.join(self.tmp, "cache"))

    def tearDown(self):
        tf.build_cmd = self._orig
        self.st.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def wait(self, key, done=True, n=None, t=15):
        t0 = time.time()
        while time.time() - t0 < t:
            i = self.st.info(key)
            if (done and i["done"]) or i["error"] or (n is not None and i["n"] >= n):
                return i
            time.sleep(0.02)
        self.fail("hết giờ chờ nạp: %s" % self.st.info(key))

    def test_nap_xong_lay_dung_khung_va_khong_co_file_tren_dia(self):
        r = self.st.open("c1", self.src, 50.0, 0.48, None)
        self.assertIn("token", r)
        i = self.wait("c1")
        self.assertEqual((i["n"], i["done"], i["error"]), (12, True, None))
        self.assertEqual(self.st.frame(i["token"], 0)[:5], b"\xff\xd8\xff\xe0A")
        self.assertEqual(self.st.frame(i["token"], 2)[:5], b"\xff\xd8\xff\xe0C")
        self.assertIsNone(self.st.frame(i["token"], 12))                # quá cuối
        self.assertIsNone(self.st.frame(i["token"], -1))
        self.assertIsNone(self.st.frame("khongco", 0))
        self.assertEqual(i["bytes"], sum(len(self.st.frame(i["token"], k)) for k in range(12)))
        self.assertEqual(os.listdir(os.path.join(self.tmp, "cache")), [])   # chỉ trong RAM: thư mục cache không có file nào

    def test_nap_tien_dan_va_hien_so_khung_dang_co(self):
        self.cfg.update(n=40, delay=0.03)
        self.st.open("c1", self.src, 50.0, 1.6, None)
        i = self.wait("c1", done=False, n=5)
        self.assertGreaterEqual(i["n"], 5)
        self.assertFalse(i["done"])                                     # chưa xong mà đã dùng được các khung đầu
        self.assertIsNotNone(self.st.frame(i["token"], 0))
        self.assertEqual(self.wait("c1")["n"], 40)

    def test_file_proxy_khong_co_thi_bao_loi_khong_chay_gi(self):
        r = self.st.open("c1", os.path.join(self.tmp, "khong_co.mov"), 50.0, 5, None)
        self.assertEqual(r, {"error": "Chưa có proxy"})
        self.assertIsNone(self.st._run)

    def test_ffmpeg_loi_thi_ghi_loi_de_giao_dien_ve_cach_cu(self):
        tf.build_cmd = lambda *a, **k: [sys.executable, "-c", "import sys; sys.stderr.write('hỏng\\n'); sys.exit(3)"]
        self.st.open("c1", self.src, 50.0, 5, None)
        i = self.wait("c1")
        self.assertTrue(i["error"] and "ffmpeg lỗi" in i["error"])
        self.assertEqual(i["n"], 0)

    def test_doi_clip_huy_viec_cu_va_lam_tiep_tu_cho_da_co(self):
        self.cfg.update(n=400, delay=0.01)
        self.st.open("c1", self.src, 50.0, 16, None)
        self.wait("c1", done=False, n=10)
        self.st.open("c2", self.src, 50.0, 16, None)                    # đổi clip: hủy việc của c1 ngay
        self.assertEqual(self.st._run[0], "c2")
        time.sleep(0.2)
        got = self.st.info("c1")["n"]
        self.assertTrue(10 <= got < 400)
        self.assertFalse(self.st.info("c1")["done"])
        self.cfg.update(n=5, delay=0.0)
        seen = []
        orig = tf.build_cmd
        tf.build_cmd = lambda ff, src, step, start_t=0.0, lut=None, width=640: (seen.append(start_t), orig(ff, src, step, start_t, lut, width))[1]
        self.st.open("c1", self.src, 50.0, 16, None)                    # quay lại c1: làm tiếp, không nạp lại từ đầu
        self.assertAlmostEqual(seen[-1], got * 2 / 50.0, places=2)      # ss = số khung đã có x bước / fps
        self.assertTrue(self.wait("c1")["n"] >= got + 5)

    def test_nap_truoc_chi_khi_ranh_va_khong_tranh_clip_dang_xem(self):
        self.cfg.update(n=400, delay=0.01)
        self.st.open("cur", self.src, 50.0, 16, None)
        self.wait("cur", done=False, n=3)
        r = self.st.open("next", self.src, 50.0, 16, None, prefetch=True)
        self.assertEqual(self.st._run[0], "cur")                        # đang bận clip xem: chưa nạp trước
        self.assertEqual(r["n"], 0)
        self.st._cancel_running()
        self.cfg.update(n=6, delay=0.0)
        self.st.open("next", self.src, 50.0, 16, None, prefetch=True)   # rảnh: nạp trước
        self.assertTrue(self.wait("next")["done"])

    def test_lru_theo_so_clip_va_theo_ram(self):
        st = tf.FrameStore(os.path.join(self.tmp, "c2"), max_clips=2, max_bytes=100000)
        for k in ("a", "b", "c"):
            st.open(k, self.src, 50.0, 0.5, None)
            t0 = time.time()
            while not st.info(k).get("done") and time.time() - t0 < 10:
                time.sleep(0.02)
        self.assertEqual(st.info("a"), {"error": "Chưa mở"})            # cũ nhất bị bỏ
        self.assertEqual(st.stats()["clips"], 2)
        self.cfg.update(n=50, size=5000)                                # mỗi clip ~250 KB, vượt 100 KB
        st.close()
        st = tf.FrameStore(os.path.join(self.tmp, "c3"), max_clips=8, max_bytes=100000)
        st.open("big", self.src, 50.0, 2, None)
        t0 = time.time()
        while not st.info("big").get("done") and time.time() - t0 < 10:
            time.sleep(0.02)
        i = st.info("big")
        self.assertLessEqual(i["bytes"], 100000 // 2 + 5100)            # một clip không quá nửa kho: dừng nạp, còn phần đã có
        self.assertGreater(i["n"], 0)
        st.close()

    def test_vong_giu_clip_dang_xem_khi_het_cho(self):
        st = tf.FrameStore(os.path.join(self.tmp, "c4"), max_clips=1)
        st.open("a", self.src, 50.0, 0.5, None)
        st.open("b", self.src, 50.0, 0.5, None)
        self.assertEqual(st.stats()["clips"], 1)
        self.assertIn("token", st.info("b"))                            # clip mới mở (đang xem) luôn được giữ
        st.close()


class Server(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.script = os.path.join(self.tmp, "fake.py")
        open(self.script, "w", encoding="utf-8").write(FAKE)
        self._orig = tf.build_cmd
        tf.build_cmd = lambda *a, **k: [sys.executable, self.script, "5", "50", "0", "0"]
        self.src = os.path.join(self.tmp, "a.mov")
        open(self.src, "wb").write(b"x")
        self.srv = tp.PlayServer([self.tmp])
        self.st = tf.FrameStore(os.path.join(self.tmp, "cache"))
        self.srv.frames = self.st
        self.st.open("c", self.src, 50.0, 0.2, None)
        t0 = time.time()
        while not self.st.info("c")["done"] and time.time() - t0 < 10:
            time.sleep(0.02)
        self.tok = self.st.info("c")["token"]

    def tearDown(self):
        tf.build_cmd = self._orig
        self.srv.close()
        self.st.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def get(self, path):
        try:
            r = urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.srv.port, path), timeout=5)
            return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, b"", e.headers

    def test_khung_va_thong_tin_qua_ve_ngau_nhien(self):
        code, body, h = self.get("/f/%s/1" % self.tok)
        self.assertEqual((code, body[:4], h["Content-Type"]), (200, b"\xff\xd8\xff\xe0", "image/jpeg"))
        self.assertEqual(h["Cache-Control"], "no-store")
        code, body, _ = self.get("/f/%s/info" % self.tok)
        d = json.loads(body)
        self.assertEqual((code, d["n"], d["done"]), (200, 5, True))

    def test_ve_sai_khung_ngoai_pham_vi_hoac_duong_dan_la_deu_bi_tu_choi(self):
        for path in ("/f/%s/5" % ("0" * 24), "/f/%s/99" % self.tok, "/f/%s/../x" % self.tok, "/f/%s/1.jpg" % self.tok, "/f/abc/1", "/f/", "/f/%s" % self.tok):
            self.assertEqual(self.get(path)[0], 404, path)

    def test_khong_co_kho_khung_thi_404_va_phat_proxy_van_nhu_cu(self):
        self.srv.frames = None
        self.assertEqual(self.get("/f/%s/1" % self.tok)[0], 404)
        url = self.srv.url_for(self.src)
        self.assertEqual(urllib.request.urlopen(url, timeout=5).read(), b"x")          # /v/ vẫn chạy, vẫn chỉ trong thư mục cho phép
        self.assertIsNone(self.srv.url_for(os.path.join(os.path.dirname(self.tmp), "ngoai.mov")))


class Api(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proxy_root = os.path.join(self.tmp, "proxy")
        os.makedirs(self.proxy_root)
        self.src = os.path.join(self.proxy_root, "DGa.mov")
        open(self.src, "wb").write(b"x")
        self.out = os.path.join(self.tmp, "ngoai.mov")
        open(self.out, "wb").write(b"x")
        self.script = os.path.join(self.tmp, "fake.py")
        open(self.script, "w", encoding="utf-8").write(FAKE)
        self._orig = tf.build_cmd
        tf.build_cmd = lambda *a, **k: [sys.executable, self.script, "4", "40", "0", "0"]

        def mk(uid, proxy):
            p = T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 08:00:00", "Sat Oct 17 2026 08:01:00", 3000, Type="Video + Audio")
            p["Proxy Media Path"] = proxy
            return T.FItem(uid, p)
        sel = T.FFolder("01_SELECTED", [mk("a", self.src), mk("b", self.out), mk("c", "")])
        foot = T.FFolder("01_footage")
        foot.subs.append(sel)
        root = T.FFolder("Master")
        root.subs.append(foot)
        self.name = "2026.10.17.LV_Ten"
        pool = T.FPool(root)
        self.api = ta.TrolyApi(self.name, self.tmp, resolve_factory=lambda: T.FResolve(T.FProject(self.name, pool)), start_worker=False, proxy_root=self.proxy_root)
        self.api._worker.connect()
        self.api.init()
        self._jobs()
        self.api.load("Master/01_footage/01_SELECTED")
        self._jobs()
        self.api.state()
        self.uid = {c["name"]: c["uid"] for c in self.api.state()["clips"]}

    def _jobs(self):
        w = self.api._worker
        while not w.jobs.empty():
            j, a = w.jobs.get()
            getattr(w, "do_" + j)(a)
        self.api._drain()

    def tearDown(self):
        tf.build_cmd = self._orig
        self.api.close()
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mo_kho_khung_tra_url_va_nap_xong(self):
        r = self.api.frames_open(self.uid["DGa.MP4"])
        self.assertIsNone(r.get("error"))
        self.assertTrue(r["url"].startswith("http://127.0.0.1:") and "/f/" in r["url"])
        c = self.api._by_uid[self.uid["DGa.MP4"]]
        key = c.rel or c.name
        t0 = time.time()
        while not self.api._frame_store().info(key)["done"] and time.time() - t0 < 10:
            time.sleep(0.02)
        code = urllib.request.urlopen(r["url"] + "/0", timeout=5).status
        self.assertEqual(code, 200)
        self.assertEqual(self.api.frames_stats()["clips"], 1)

    def test_clip_khong_proxy_hoac_proxy_ngoai_thu_muc_thi_bao_loi(self):
        self.assertEqual(self.api.frames_open(self.uid["DGc.MP4"]), {"error": "Chưa có proxy"})
        r = self.api.frames_open(self.uid["DGb.MP4"])
        self.assertIn("ngoài thư mục proxy", r["error"])
        self.assertIn("error", self.api.frames_open("khong-co"))
        self.assertEqual(self.api.frames_stats()["clips"], 0)            # không nạp gì

    def test_chua_cau_hinh_proxy_root_thi_bao_loi(self):
        self.api._proxy_root = None
        self.assertEqual(self.api.frames_open(self.uid["DGa.MP4"]), {"error": "Chưa có proxy"})


class Web(unittest.TestCase):
    def setUp(self):
        self.pl, self.css = rd("player.js"), rd("style.css")

    def test_re_chuot_ve_tu_ram_khong_dung_the_video_va_khong_goi_python(self):
        scrub = self.pl[self.pl.index("function frScrub"):self.pl.index("function frRelease")]
        self.assertNotIn("currentTime =", scrub)                         # không nhảy thẻ video trong lúc rê
        self.assertNotIn("api()", scrub)
        fetch = self.pl[self.pl.index("async function frFetch"):self.pl.index("function frScrub")]
        self.assertNotIn("api()", fetch)                                 # lấy khung bằng fetch cục bộ, không qua cầu Python
        self.assertIn("createImageBitmap", fetch)
        seek = self.pl[self.pl.index("function plSeek"):self.pl.index("function plNudge")]
        self.assertIn("opt.fast && frReady()", seek)
        self.assertIn("frScrub(at)", seek)
        self.assertIn("FR_DWELL_MS", seek)                               # dừng tay -> nhảy chính xác

    def test_tha_chuot_thi_nhay_chinh_xac_roi_an_canvas(self):
        self.assertIn("frRelease()", self.pl[self.pl.index('v.addEventListener("seeked"'):][:260])
        self.assertIn("frRelease(); plHead(); plTime(); return;", self.pl)        # đã đúng chỗ rồi: vẫn ẩn canvas
        rel = self.pl[self.pl.index("function frRelease"):][:200]
        self.assertIn('display = "none"', rel)

    def test_chua_co_khung_thi_ve_cach_cu_va_hien_phan_tram_nap(self):
        self.assertIn("function frReady() { return !!(FR.url && FR.n > 0 && !FR.err); }", self.pl)
        self.assertIn("Đang nạp khung xem nhanh", self.pl)
        self.assertIn("kfBefore(t)", self.pl)                            # đường nhảy keyframe cũ vẫn còn làm dự phòng

    def test_giu_toi_da_so_bitmap_va_doi_clip_thi_xoa(self):
        self.assertIn("const FR_KEEP = 160;", self.pl)
        self.assertIn("FR.bmp.size > FR_KEEP", self.pl)
        self.assertIn("frReset(); lutDetach();", self.pl)                # plStop: bỏ khung của clip cũ

    def test_song_am_va_thanh_in_out_re_giu_chuot_cung_ve_tu_ram(self):
        self.assertIn("function plDragScrub", self.pl)
        self.assertIn("requestAnimationFrame(flush)", self.pl)           # gộp theo khung hình
        self.assertIn('$("waveBox").addEventListener("mousedown", (ev) => plDragScrub(ev, $("waveBox")));', self.pl)
        self.assertIn('plDragScrub(ev, $("ioBar"))', self.pl)

    def test_canvas_khung_nam_tren_video(self):
        self.assertIn("canvas.pv-frame", self.css)
        self.assertRegex(self.css, r"canvas\.pv-frame \{[^}]*z-index: 2")        # trên canvas LUT (z-index 1)
        self.assertNotRegex(self.css[self.css.index("canvas.pv-frame"):][:300], r"backdrop-filter|box-shadow|blur")    # H4: không lớp trong suốt/blur đè lên video

    def test_nap_truoc_khi_ranh_va_khong_nap_khi_dang_re(self):
        pre = self.pl[self.pl.index("function frPrefetch"):self.pl.index("function frKeep")]
        self.assertIn("SK.drag || FR.active", pre)
        self.assertIn("frames_open(u, true)", pre)
        self.assertIn("items[cur + 1]", pre)

    def test_khong_tao_file_hay_ghi_in_out_khi_re(self):
        seg = self.pl[self.pl.index("const FR = {"):self.pl.index("/* ---- trình phát ---- */")]
        for bad in ("set_inout", "inout_write", "api().move", "api().apply", "SetMarkInOut"):
            self.assertNotIn(bad, seg, bad)


if __name__ == "__main__":
    unittest.main()
