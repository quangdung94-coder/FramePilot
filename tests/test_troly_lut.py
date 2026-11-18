"""Việc 1 (ADR-0023): khung xem đúng màu LUT. Đọc .cube, API lut_cube (chỉ đọc), máy chủ phát cho phép WebGL đọc khung hình, giao diện có nút LUT,
không tạo file mới."""
import array
import base64
import os
import shutil
import sys
import tempfile
import unittest
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import test_troly as T                # noqa: E402
import troly_api as ta                # noqa: E402
import troly_lut as tl                # noqa: E402
import troly_play as tp               # noqa: E402


def write_cube(path, size=2, body=None, extra=""):
    lines = ["# thử", 'TITLE "LUT thử"', "LUT_3D_SIZE %d" % size, extra]
    n = size ** 3
    for i in range(n):
        r, g, b = i % size, (i // size) % size, i // (size * size)
        lines.append("%f %f %f" % (r / (size - 1.0), g / (size - 1.0), b / (size - 1.0)))
    if body is not None:
        lines = lines[:4] + body
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


class Cube(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def test_doc_lut_3d_dung_thu_tu_r_nhanh_nhat(self):
        p = os.path.join(self.t, "a.cube")
        write_cube(p, 2)
        d = tl.parse_cube(p)
        self.assertEqual((d["size"], d["title"]), (2, "LUT thử"))
        self.assertEqual(list(d["data"][:6]), [0.0, 0.0, 0.0, 1.0, 0.0, 0.0])             # phần tử thứ hai: R = 1 (R chạy nhanh nhất)
        self.assertEqual(list(d["data"][6:9]), [0.0, 1.0, 0.0])                            # rồi G
        self.assertEqual(list(d["data"][12:15]), [0.0, 0.0, 1.0])                          # rồi B
        self.assertEqual((d["dmin"], d["dmax"]), ([0.0] * 3, [1.0] * 3))

    def test_domain_va_payload_base64_float32(self):
        p = os.path.join(self.t, "d.cube")
        write_cube(p, 2, extra="DOMAIN_MIN 0.1 0.1 0.1\nDOMAIN_MAX 0.9 0.9 0.9")
        pl = tl.payload(p)
        self.assertEqual((pl["size"], pl["dmin"], pl["dmax"]), (2, [0.1, 0.1, 0.1], [0.9, 0.9, 0.9]))
        raw = base64.b64decode(pl["b64"])
        self.assertEqual(len(raw), 2 ** 3 * 3 * 4)
        a = array.array("f")
        a.frombytes(raw)
        self.assertEqual(a[3], 1.0)

    def test_file_hong_bi_tu_choi_gon(self):
        bad = {"1d": "LUT_1D_SIZE 4\n0 0 0\n", "thieu_dong": "LUT_3D_SIZE 2\n0 0 0\n1 1 1\n", "khong_phai_so": "LUT_3D_SIZE 2\n" + "a b c\n" * 8,
               "co_qua_lon": "LUT_3D_SIZE 999\n", "khong_size": "0 0 0\n", "domain_sai": "LUT_3D_SIZE 2\nDOMAIN_MIN 1 1 1\nDOMAIN_MAX 0 0 0\n" + "0 0 0\n" * 8}
        for name, text in bad.items():
            p = os.path.join(self.t, name + ".cube")
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            with self.assertRaises(tl.LutError, msg=name):
                tl.parse_cube(p)
        with self.assertRaises(tl.LutError):
            tl.parse_cube(os.path.join(self.t, "khong_co.cube"))

    def test_chi_doc_khong_tao_file_moi(self):
        p = os.path.join(self.t, "a.cube")
        write_cube(p, 2)
        before = sorted(os.listdir(self.t))
        tl.payload(p)
        self.assertEqual(sorted(os.listdir(self.t)), before)


class Api(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.lutdir = os.path.join(self.tmp, "luts")
        os.makedirs(os.path.join(self.lutdir, "Sony"))
        write_cube(os.path.join(self.lutdir, "Sony", "Thu.cube"), 3)
        a = T.FItem("a", T.props("DGa.MP4", "Sat Oct 17 2026 08:00:00", "Sat Oct 17 08:00:20 2026", 1000, Type="Video + Audio", **{"Input LUT": "Sony\\Thu"}))
        b = T.FItem("b", T.props("DGb.MP4", "Sat Oct 17 2026 09:00:00", "Sat Oct 17 09:00:20 2026", 1000, Type="Video + Audio"))
        c = T.FItem("c", T.props("DGc.MP4", "Sat Oct 17 2026 10:00:00", "Sat Oct 17 10:00:20 2026", 1000, Type="Video + Audio", **{"Input LUT": "Khong\\Co"}))
        sel = T.FFolder("01_SELECTED", [a, b, c])
        foot = T.FFolder("01_footage")
        foot.subs.append(sel)
        root = T.FFolder("Master")
        root.subs.append(foot)
        pool = T.FPool(root)
        name = "2026.10.17.LV_Ten"
        self.api = ta.TrolyApi(name, self.tmp, resolve_factory=lambda: T.FResolve(T.FProject(name, pool)), start_worker=False)
        self.api._thumbs.dirs.insert(0, self.lutdir)
        self.api._worker.connect()
        self.api.init()
        w = self.api._worker
        while not w.jobs.empty():
            j, arg = w.jobs.get()
            getattr(w, "do_" + j)(arg)
        self.api._drain()
        self.api.load("Master/01_footage/01_SELECTED")
        while not w.jobs.empty():
            j, arg = w.jobs.get()
            getattr(w, "do_" + j)(arg)
        self.api._drain()

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def uid(self, n):
        return next(c["uid"] for c in self.api.state()["clips"] if c["name"] == n)

    def test_lut_cube_ba_truong_hop(self):
        r = self.api.lut_cube(self.uid("DGa.MP4"))
        self.assertEqual((r["size"], r["title"]), (3, "LUT thử"))
        self.assertTrue(r["b64"])
        self.assertEqual(self.api.lut_cube(self.uid("DGb.MP4")), {"none": True})              # không gắn LUT: hình gốc
        self.assertIn("Không thấy file LUT", self.api.lut_cube(self.uid("DGc.MP4"))["error"])
        self.assertIn("error", self.api.lut_cube("khong-co"))

    def test_lut_cube_doc_lai_tu_bo_nho_va_khong_ghi_gi(self):
        before = sorted(os.listdir(self.lutdir + "/Sony"))
        a = self.api.lut_cube(self.uid("DGa.MP4"))
        self.assertIs(self.api.lut_cube(self.uid("DGa.MP4")), a)
        self.assertEqual(sorted(os.listdir(self.lutdir + "/Sony")), before)


class Play(unittest.TestCase):
    def test_may_chu_phat_cho_phep_webgl_doc_khung_hinh(self):
        t = tempfile.mkdtemp()
        try:
            root = os.path.join(t, "px")
            os.makedirs(root)
            with open(os.path.join(root, "a.mov"), "wb") as f:
                f.write(b"0123456789")
            s = tp.PlayServer([root])
            try:
                u = s.url_for(os.path.join(root, "a.mov"))
                rq = urllib.request.Request(u)
                rq.add_header("Range", "bytes=0-3")
                with urllib.request.urlopen(rq, timeout=5) as r:
                    self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")
                    self.assertEqual(r.status, 206)
            finally:
                s.close()
        finally:
            shutil.rmtree(t, ignore_errors=True)


class Web(unittest.TestCase):
    def setUp(self):
        web = os.path.join(HERE, "..", "app", "troly_web")
        self.pl = open(os.path.join(web, "player.js"), encoding="utf-8").read()
        self.html = open(os.path.join(web, "index.html"), encoding="utf-8").read()
        self.app = open(os.path.join(web, "app.js"), encoding="utf-8").read()

    def test_player_ap_lut_bang_webgl_va_co_nut_bat_tat(self):
        self.assertIn('getContext("webgl2"', self.pl)
        self.assertIn("api().lut_cube(", self.pl)
        self.assertIn('v.crossOrigin = "anonymous"', self.pl)                                   # để WebGL đọc được khung hình
        self.assertEqual(self.html.count('id="plLut"'), 1)
        self.assertIn("RGB16F", self.pl)
        self.assertIn("lutDetach()", self.pl[self.pl.index("function plStop"):self.pl.index("function plStop") + 400])

    def test_doi_hinh_tinh_khong_xoa_canvas_lut(self):
        self.assertIn("canvas.pv-lut", self.app[self.app.index("const showImg"):self.app.index("const showImg") + 400])

    def test_khong_gui_gi_vao_davinci_tu_phan_lut(self):
        seg = self.pl[self.pl.index("Việc 1 (ADR-0023)"):self.pl.index("/* ---- trình phát ---- */")]
        for bad in ("inout_write", "api().apply", "set_inout", "SetMarkInOut"):
            self.assertNotIn(bad, seg, bad)


if __name__ == "__main__":
    unittest.main()
