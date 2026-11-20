"""Kiểm phần phân tích của tools/hoc_tu_cu (dữ liệu giả, không cần DaVinci)."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import hoc_tu_cu_phan_tich as pt      # noqa: E402


def fake():
    random.seed(1)
    clips, items, samples = [], [], {}
    t_pos = 0
    base = 6 * 3600                                      # 06:00
    for i in range(60):
        cam = "DG" if i % 2 == 0 else "HM"
        sec = base + (i // 2) * 120 + (3600 * 5 if i >= 40 else 0) + (7 if cam == "HM" else 0)   # HM lệch đồng hồ 7s, nhảy 5 giờ ở clip 40
        h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
        d = 40 + (i % 5) * 10
        uid = "u%d" % i
        clips.append({"uid": uid, "bin": "x", "online": True, "path": "", "mark": None, "props": {
            "File Name": "%s%04d.MP4" % (cam, i), "FPS": "25", "Frames": str(d * 25), "Resolution": "1920x1080",
            "Date Created": "Sat Oct 17 2026 %02d:%02d:%02d" % (h, m, s)}})
        if i % 3 != 2:
            items.append({"uid": uid, "track": 1 if cam == "DG" else 2, "start": t_pos * 25, "end": (t_pos + 10) * 25, "dur": 250,
                          "src_start_f": 5 * 25, "src_end_f": 15 * 25})
            t_pos += 10
        samples[uid] = [{"t": 5 + k * 2, "rms": -30 + (10 if 5 <= 5 + k * 2 <= 15 else 0), "voice": .5, "dyn": 5, "bright": .4,
                         "sat": .3, "sky": 0, "rgb": []} for k in range(8)]
    return {"clips": clips, "timelines": [{"name": "full", "fps": "25", "start_frame": 0, "items": items, "others": [], "markers": []}]}, samples


class T(unittest.TestCase):
    def test_analyse(self):
        d, s = fake()
        r = pt.analyse(d, s)
        io = r["in_out"]
        self.assertEqual(io["keep"]["med"], 10.0)
        self.assertEqual(io["head"]["med"], 5.0)
        self.assertAlmostEqual(io["am_thanh"]["giu_hon_bo_rms_db"]["med"], 10.0, places=1)
        self.assertEqual(r["sao"]["n_dung"], 40)
        self.assertEqual(r["tong_quan"]["timeline"][0]["tl"], "full")
        self.assertTrue(r["tren_timeline"]["diem_chuyen"])            # nhảy 5 giờ phải thành điểm chuyển
        self.assertTrue(r["tu_du_lieu_quay"]["khoang_trong"])
        import json
        json.dumps(r)

    def test_khong_ten_clip(self):
        d, s = fake()
        txt = str(pt.analyse(d, s))
        self.assertNotIn("DG0", txt)


if __name__ == "__main__":
    unittest.main()
