"""Bước 6 AI trong panel (ADR-0022): gợi ý hạng 1-3 theo giai đoạn, học từ nhãn tay khi đủ nhãn, Nhận chỉ gán nhãn trong kế hoạch,
Bỏ qua, AI không bao giờ gọi DaVinci. Dữ liệu giả (vector 2 chiều), tên ví dụ LV_Ten."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
import test_troly as T                # noqa: E402
import troly_ai as ai                 # noqa: E402
import troly_api as ta                # noqa: E402
import troly_core as tc               # noqa: E402


def unit(x, y):
    v = np.array([x, y], dtype=np.float32)
    return v / np.linalg.norm(v)


class Rank(unittest.TestCase):
    def setUp(self):
        self.vec = {("f", "a"): unit(1, 0), ("f", "b"): unit(0.9, 0.1), ("f", "c"): unit(0, 1), ("f", "q"): unit(0.95, 0.05)}
        self.desc = (["Decor", "Khác"], {("f", "q"): [0.2, 0.8], ("f", "z"): [0.7, 0.3]})

    def test_chua_du_nhan_dung_mo_ta_va_chi_trong_bin_cua_giai_doan(self):
        src, top = ai.rank_for_clip(("f", "q"), ["Decor", "Khác"], self.vec, {("f", "a"): "Decor"}, self.desc)
        self.assertEqual(src, "mo_ta")
        self.assertEqual(top[0]["bin"], "Khác")
        self.assertAlmostEqual(sum(t["score"] for t in top), 1.0, places=2)
        src, top = ai.rank_for_clip(("f", "q"), ["Decor"], self.vec, {}, self.desc)               # giai đoạn chỉ có Decor
        self.assertEqual([t["bin"] for t in top], ["Decor"])

    def test_du_nhan_hoc_tu_nhan_tay(self):
        vec, lab = dict(self.vec), {}
        for i in range(10):
            vec[("x", str(i))] = unit(1, 0.02 * i)
            lab[("x", str(i))] = "Decor"
            vec[("y", str(i))] = unit(0.02 * i, 1)
            lab[("y", str(i))] = "Khác"
        src, top = ai.rank_for_clip(("f", "q"), ["Decor", "Khác"], vec, lab, self.desc)
        self.assertEqual(src, "nhan")                                                              # đủ ≥ 20 nhãn
        self.assertEqual(top[0]["bin"], "Decor")                                                   # hình gần Decor dù mô tả nói Khác

    def test_khong_du_du_lieu_thi_khong_goi_y(self):
        self.assertEqual(ai.rank_for_clip(("f", "none"), ["Decor"], self.vec, {}, self.desc), (None, []))

    def test_khoa_khong_phan_biet_hoa_thuong_va_duoi_file(self):
        self.assertEqual(ai.ck("01_Footage/DG4939.MP4"), ai.ck("01_footage/dg4939.mov"))


class Panel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.name = "2026.10.17.LV_Ten"
        sel = T.FFolder("01_SELECTED", [T.FItem("a", T.props("DGa.MP4", "Sat Oct 17 2026 08:10:00", "Sat Oct 17 08:10:20 2026", 1000, Type="Video + Audio")),
                                        T.FItem("b", T.props("DGb.MP4", "Sat Oct 17 2026 08:20:00", "Sat Oct 17 08:20:20 2026", 1000, Type="Video + Audio"))])
        foot = T.FFolder("01_footage")
        foot.subs.append(sel)
        root = T.FFolder("Master")
        root.subs.append(foot)
        self.pool = T.FPool(root)
        self.api = ta.TrolyApi(self.name, self.tmp, resolve_factory=lambda: T.FResolve(T.FProject(self.name, self.pool)), start_worker=False)
        self.api._worker.connect()
        self.api.init()
        self._jobs()
        self.api.load("Master/01_footage/01_SELECTED")
        self._jobs()
        self.api._plan["stages"] = [{"name": "Chuẩn bị", "start": 0.0, "end": 100000.0, "color": "#fff", "bins": ["Decor", "Khác"]}]
        self.api._plan["offsets"] = {}
        self.api.state()
        d = os.path.join(self.tmp, "troly", "ai_suggest")
        os.makedirs(d)
        self.sfile = os.path.join(d, tc._safe(self.name) + ".json")
        items = [{"clip": "01_footage/DGa.mov", "scores": [0.9, 0.1]}, {"clip": "01_footage/DGb.mov", "scores": [0.3, 0.7]}]
        with open(self.sfile, "w", encoding="utf-8") as f:
            json.dump({"bins": ["Decor", "Khác"], "items": items}, f)

    def _jobs(self):
        w = self.api._worker
        while not w.jobs.empty():
            j, a = w.jobs.get()
            getattr(w, "do_" + j)(a)
        self.api._drain()

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def uid(self, n):
        return next(c["uid"] for c in self.api.state()["clips"] if c["name"] == n)

    def test_chua_chay_ai_thi_bao_chua_co(self):
        os.remove(self.sfile)
        self.assertFalse(self.api.ai_info()["has_data"])
        self.assertEqual(self.api.ai_for([self.uid("DGa.MP4")]), {})

    def test_goi_y_hang_theo_mo_ta_va_thong_tin(self):
        info = self.api.ai_info()
        self.assertTrue(info["has_data"])
        self.assertEqual(info["mode"], "mo_ta")
        a, b = self.uid("DGa.MP4"), self.uid("DGb.MP4")
        r = self.api.ai_for([a, b])
        self.assertEqual(r[a]["top"][0]["bin"], "Decor")
        self.assertEqual(r[b]["top"][0]["bin"], "Khác")
        self.assertEqual(r[a]["src"], "mo_ta")

    def test_nhan_chi_gan_nhan_khong_goi_davinci(self):
        u = self.uid("DGa.MP4")
        before = len(self.api._plan.get("moves", []))
        st = self.api.ai_accept([[u, "Decor"]])
        self.assertEqual(st["ai_accepted"], 1)
        lab = list(self.api._plan["labels"].values())[0]
        self.assertEqual((lab["bin"], lab["by"]), ("Decor", "ai_duyet"))
        self.assertEqual(len(self.api._plan.get("moves", [])), before)                 # chưa chuyển gì trong DaVinci
        self.assertTrue(self.api._worker.jobs.empty())                                 # không việc nào gửi cho luồng DaVinci
        self.api.label([u], 0, None)                                                   # bỏ nhãn như thường
        self.assertEqual(self.api._plan["labels"], {})

    def test_nhan_bin_ngoai_giai_doan_bi_tu_choi(self):
        st = self.api.ai_accept([[self.uid("DGa.MP4"), "Không có bin này"]])
        self.assertEqual((st["ai_accepted"], st["ai_bad"]), (0, 1))
        self.assertEqual(self.api._plan["labels"], {})

    def test_bo_qua_roi_hien_lai(self):
        u = self.uid("DGa.MP4")
        self.api.ai_skip([u])
        self.assertEqual(self.api.ai_for([u]), {u: {"skipped": True}})
        self.api.ai_skip([u], undo=True)
        self.assertIn("top", self.api.ai_for([u])[u])

    def test_clip_da_xep_khong_goi_y_tru_khi_xin(self):
        u = self.uid("DGa.MP4")
        self.api.label([u], 0, "Khác")
        self.assertEqual(self.api.ai_for([u]), {})
        self.assertIn(u, self.api.ai_for([u], include_labeled=True))

    def test_khong_co_venv_thi_bao_loi_khong_chay(self):
        self.api._ai_job = ai.AiJob(self.name, self.tmp, python=os.path.join(self.tmp, "khong_co", "python.exe"))
        self.assertFalse(self.api.ai_info()["can_run"])
        self.assertIn("error", self.api.ai_run())


class Safe(unittest.TestCase):
    def test_ai_trong_panel_khong_ghi_davinci(self):
        src = open(os.path.join(HERE, "..", "app", "troly_ai.py"), encoding="utf-8").read()
        for bad in ("troly_resolve", "MoveClips", "SetMarkInOut", "AddSubFolder"):
            self.assertNotIn(bad, src)
        api = open(os.path.join(HERE, "..", "app", "troly_api.py"), encoding="utf-8").read()
        seg = api[api.index("def ai_info"):api.index("# ------------------------------------------------------------------ thumbnail")]
        for bad in ("jobs.put", "_worker", "inout_write"):
            self.assertNotIn(bad, seg, bad)


if __name__ == "__main__":
    unittest.main()
