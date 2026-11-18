"""Thống kê In/Out thật (ADR-0021): hàm thuần + an toàn (công cụ đọc chỉ ĐỌC DaVinci)."""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
sys.path.insert(0, TOOLS)
import inout_stats as st      # noqa: E402


class Stats(unittest.TestCase):
    def test_ghep_ten_bin(self):
        self.assertEqual(st.canon("Master/01_footage/04_Đón dâu về nhà trai/Nghi lễ"), "Nghi lễ")
        self.assertEqual(st.canon("Master/01_footage/05_Đón khách/Cô dâu chú rể"), "Cô dâu chú rể")
        self.assertEqual(st.canon("Master/01_footage/07_Chào bàn"), "Chào bàn")
        self.assertIsNone(st.canon("Master/01a_footage"))

    def test_mau_bo_slowmo_va_trung(self):
        item = {"uid": "u", "src_start_f": 50, "src_end_f": 200, "dur": 75}          # 3s nguồn / 3s dựng
        slow = {"uid": "u", "src_start_f": 0, "src_end_f": 50, "dur": 50}             # 1s nguồn / 2s dựng = 0,5x
        d = {"clips": [{"uid": "u", "bin": "Master/Decor", "fps": 50.0, "frames": "500", "mark": [100, 150]}],
             "timelines": [{"name": "full", "fps": 25.0, "items": [item, dict(item), slow]}, {"name": "multicam_x", "fps": 25.0, "items": [item]}]}
        used, marks = st.samples(d)
        self.assertEqual(len(used), 1)                                             # trùng + slow-mo + timeline multicam bị bỏ
        self.assertAlmostEqual(used[0]["in"], 1.0)
        self.assertAlmostEqual(used[0]["out"], 4.0)
        self.assertEqual((marks[0]["in"], marks[0]["out"]), (2.0, 3.0))

    def test_tu_phan_vi_va_de_xuat(self):
        rows = [{"in": 0.0, "out": float(k), "dur": 20.0} for k in range(1, 11)]
        sm = st.summarize(rows)
        self.assertEqual(sm["n"], 10)
        self.assertAlmostEqual(sm["keep_med"], 5.5)
        p = st.propose(sm)
        self.assertEqual((p["min"], p["max"]), (3.5, 8.0))
        self.assertIsNone(st.propose(st.summarize(rows[:5])))                       # n < 8: chưa đủ mẫu

    def test_so_voi_quy_tac_hien_co(self):
        rows = [{"in": 1.2, "out": 4.2, "dur": 20.0}]
        r = st.vs_rule(rows, None)
        self.assertEqual((r["in_trung_pct"], r["out_trung_pct"], r["iou_med"]), (100, 100, 1.0))

    def test_cong_cu_doc_khong_ghi_davinci(self):
        src = open(os.path.join(TOOLS, "inout_dump.py"), encoding="utf-8").read()
        for bad in ("SetMarkInOut", "ClearMarkInOut", "CreateTimeline", "MoveClips", "AddSubFolder", "DeleteProject", "RenderWith", "StartRendering", "AddRenderJob"):
            self.assertNotIn(bad, src, bad)
        self.assertIn("finally:", src)                                              # luôn mở lại project gốc


if __name__ == "__main__":
    unittest.main()
