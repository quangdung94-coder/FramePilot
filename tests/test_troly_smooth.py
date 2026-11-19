"""Việc 2 (ADR-0023): lướt mượt. Keyframe đọc từ proxy (chỉ đọc, cache), API chỉ trong proxy_root, giao diện gửi lệnh nhảy khi lệnh trước xong,
kéo theo keyframe, thả chính xác, dùng lại MỘT thẻ video."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import test_troly as T                # noqa: E402
import troly_api as ta                # noqa: E402
import troly_kf as kf                 # noqa: E402


class Fake(object):
    def __init__(self, out, rc=0, exc=None):
        self.out, self.rc, self.exc, self.calls = out, rc, exc, []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if self.exc:
            raise self.exc
        return subprocess.CompletedProcess(cmd, self.rc, self.out, "")


class Kf(unittest.TestCase):
    def test_doc_goi_tin_chi_lay_keyframe_sap_xep_khong_trung(self):
        text = "0.000000,K__\n0.020000,___\n1.000000,K__\n0.500000,K_\n1.000000,K__\n1.040000,__\nrac,K\n"
        self.assertEqual(kf.parse_packets(text), [0.0, 0.5, 1.0])
        self.assertEqual(kf.parse_packets(""), [])

    def test_probe_chi_doc_goi_tin_khong_giai_ma_va_loi_thi_none(self):
        run = Fake("0,K\n2,K\n")
        self.assertEqual(kf.probe("x.mov", "ffprobe", runner=run), [0.0, 2.0])
        cmd = run.calls[0]
        self.assertIn("packet=pts_time,flags", cmd)                      # chỉ đọc chỉ mục gói tin
        self.assertNotIn("-skip_frame", cmd)
        self.assertNotIn("-y", cmd)                                       # không ghi file
        self.assertIsNone(kf.probe("x.mov", runner=Fake("", rc=1)))
        self.assertIsNone(kf.probe("x.mov", runner=Fake("", exc=subprocess.TimeoutExpired("c", 1))))
        self.assertIsNone(kf.probe("x.mov", runner=Fake("", exc=OSError("không có ffprobe"))))

    def test_cache_theo_co_va_gio_sua_proxy(self):
        t = tempfile.mkdtemp()
        try:
            src = os.path.join(t, "a.mov")
            with open(src, "wb") as f:
                f.write(b"x" * 10)
            cache = os.path.join(t, "cache")
            run = Fake("0,K\n3,K\n")
            self.assertEqual(kf.get(src, cache, runner=run), [0.0, 3.0])
            self.assertEqual(kf.get(src, cache, runner=run), [0.0, 3.0])
            self.assertEqual(len(run.calls), 1)                          # lần hai đọc cache
            with open(src, "wb") as f:                                   # proxy đổi cỡ -> đọc lại
                f.write(b"yy" * 10)
            kf.get(src, cache, runner=run)
            self.assertEqual(len(run.calls), 2)
            self.assertIsNone(kf.get(os.path.join(t, "khong_co.mov"), cache, runner=run))
            self.assertEqual(os.listdir(t).count("a.mov"), 1)            # không ghi gì cạnh proxy
        finally:
            shutil.rmtree(t, ignore_errors=True)


class Api(unittest.TestCase):
    def test_keyframes_chi_trong_proxy_root(self):
        t = tempfile.mkdtemp()
        try:
            proxy = os.path.join(t, "px")
            os.makedirs(proxy)
            ok = os.path.join(proxy, "a.mov")
            out = os.path.join(t, "ngoai.mov")
            for f in (ok, out):
                with open(f, "wb") as fh:
                    fh.write(b"x" * 10)
            name = "2026.10.17.LV_Ten"
            sel = T.FFolder("01_SELECTED", [T.FItem("a", T.props("DGa.MP4", "Sat Oct 17 2026 08:00:00", "Sat Oct 17 08:00:20 2026", 1000, Type="Video + Audio", **{"Proxy Media Path": ok})),
                                            T.FItem("b", T.props("DGb.MP4", "Sat Oct 17 2026 09:00:00", "Sat Oct 17 09:00:20 2026", 1000, Type="Video + Audio", **{"Proxy Media Path": out}))])
            foot = T.FFolder("01_footage")
            foot.subs.append(sel)
            root = T.FFolder("Master")
            root.subs.append(foot)
            pool = T.FPool(root)
            api = ta.TrolyApi(name, t, resolve_factory=lambda: T.FResolve(T.FProject(name, pool)), start_worker=False, proxy_root=proxy)
            api._worker.connect()
            api.init()
            w = api._worker
            while not w.jobs.empty():
                j, a = w.jobs.get()
                getattr(w, "do_" + j)(a)
            api._drain()
            api.load("Master/01_footage/01_SELECTED")
            while not w.jobs.empty():
                j, a = w.jobs.get()
                getattr(w, "do_" + j)(a)
            api._drain()
            uid = {c["name"]: c["uid"] for c in api.state()["clips"]}
            orig = kf.probe
            kf.probe = lambda src, *a, **k: [0.0, 1.0, 2.0]
            try:
                self.assertEqual(api.keyframes(uid["DGa.MP4"]), {"kf": [0.0, 1.0, 2.0]})
                self.assertIn("error", api.keyframes(uid["DGb.MP4"]))     # proxy nằm ngoài proxy_root: từ chối
                self.assertIn("error", api.keyframes("khong-co"))
            finally:
                kf.probe = orig
            api._thumbs.shutdown()
        finally:
            shutil.rmtree(t, ignore_errors=True)

    def test_khong_tao_proxy_moi(self):
        src = open(os.path.join(HERE, "..", "app", "troly_kf.py"), encoding="utf-8").read()
        for bad in ("libx264", "-c:v", "ensure_play_mp4", "os.remove", "shutil.rmtree"):
            self.assertNotIn(bad, src, bad)


class Web(unittest.TestCase):
    def setUp(self):
        self.js = open(os.path.join(HERE, "..", "app", "troly_web", "player.js"), encoding="utf-8").read()

    def test_chi_gui_lenh_nhay_khi_lenh_truoc_xong(self):
        pump = self.js[self.js.index("function plPump()"):self.js.index("function plSeek(t, opt)")]
        self.assertIn("SK.busy", pump)
        self.assertIn("SK.want = null", pump)                                  # lệnh cũ chưa gửi bị thay bằng lệnh mới nhất
        self.assertIn('v.addEventListener("seeked", () => { SK.busy = false;', self.js)
        self.assertIn("plPump()", self.js[self.js.index('v.addEventListener("seeked"'):self.js.index('v.addEventListener("seeked"') + 200])
        self.assertIn("setTimeout(() => { SK.busy = false; plPump(); }, 1500)", pump)   # không treo nếu seeked không tới

    def test_keo_thi_theo_keyframe_tha_thi_chinh_xac(self):
        self.assertIn("SK.fast ? kfBefore(t) : t", self.js)
        self.assertIn("plSeek($(\"plSeek\").value / 1000 * PL.dur, { fast: SK.drag })", self.js)
        rel = self.js[self.js.index("const plSeekRelease"):self.js.index("const plSeekRelease") + 260]
        self.assertIn("plSeek($(\"plSeek\").value / 1000 * PL.dur);", rel)                    # thả: không có {fast}
        self.assertIn("{ fast: true }", self.js)                                              # kéo mép In/Out cũng theo keyframe
        self.assertIn("api().keyframes(uid)", self.js)

    def test_dung_lai_mot_the_video(self):
        self.assertEqual(self.js.count('document.createElement("video")'), 1)       # MỘT thẻ video cho mọi clip (không có thẻ thứ hai tranh bộ giải mã: ADR-0016 bản 2)
        opn = self.js[self.js.index("async function plOpen"):self.js.index('$("plPlay").onclick')]
        self.assertNotIn("old.remove()", opn)
        self.assertNotIn("createElement", opn)
        self.assertIn("v.src = r.url", opn)
        self.assertIn("PL.el", self.js)


if __name__ == "__main__":
    unittest.main()
