"""Lỗi 19/11: "Tự phân loại" ở Bước 2 chạy nhưng xếp 0 clip, không báo vì sao.
Nguyên nhân gốc: thư mục proxy của project rỗng -> AI chỉ nhúng được thumbnail "mồ côi" (khóa thumb:<mã>), không có tên clip -> không ghép được với
clip nào trong kế hoạch. Test này giữ cho lỗi không quay lại thầm lặng: phải báo rõ lý do, không ghi nhãn nào, và dữ liệu đủ tên clip vẫn chạy như cũ."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_troly_ai_auto as A        # noqa: E402
import troly_core as tc               # noqa: E402


class KhongGhepDuoc(unittest.TestCase):
    labels = A.Auto.labels
    uid = A.Auto.uid
    tearDown = A.Auto.tearDown

    def setUp(self):
        A.Auto.setUp(self)
        self.proxy = os.path.join(self.tmp, "px")
        os.makedirs(os.path.join(self.proxy, self.name))                 # thư mục proxy của project có nhưng RỖNG
        self.api._proxy_root = self.proxy
        d = os.path.join(self.tmp, "troly", "ai_suggest")
        orphan = [{"clip": "(không ghép được clip)", "scores": [0.9, 0.05, 0.05]}]
        with open(os.path.join(d, tc._safe(self.name) + ".json"), "w", encoding="utf-8") as f:
            json.dump({"bins": ["Decor", "Khác", "Nghi"], "items": orphan}, f)

    def test_ai_info_bao_khong_ghep_duoc_kem_ly_do_va_thu_muc(self):
        info = self.api.ai_info()
        self.assertTrue(info["no_match"])
        self.assertIn("proxy", info["no_match"])
        self.assertIn(self.proxy, info["no_match"])

    def test_tu_phan_loai_bao_loi_ro_va_khong_ghi_nhan(self):
        for r in (self.api.ai_auto_apply(), self.api.ai_auto_run()):
            self.assertIn("error", r)
            self.assertIn("không ghép được", r["error"])
            self.assertIn("proxy", r["error"])
        self.assertEqual(self.labels(), {})
        self.assertFalse(self.api._plan.get("ai_auto", {}).get("batches"))

    def test_du_lieu_dung_ten_clip_thi_khong_bao_loi(self):
        items = [{"clip": "01_footage/DG%s.mov" % n, "scores": s} for n, s in (("a", [0.9, 0.05, 0.05]), ("b", [0.5, 0.3, 0.2]), ("c", [0.2, 0.55, 0.25]))]
        p = os.path.join(self.tmp, "troly", "ai_suggest", tc._safe(self.name) + ".json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"bins": ["Decor", "Khác", "Nghi"], "items": items}, f)
        os.utime(p, (os.path.getmtime(p) + 5, os.path.getmtime(p) + 5))   # để _ai_data nạp lại
        self.assertFalse(self.api.ai_info()["no_match"])
        self.assertEqual(self.api.ai_auto_apply()["ai_auto"]["n"], 3)


class KhongCanProxy(unittest.TestCase):
    """Bỏ ràng buộc proxy: AI ghép ảnh theo danh sách clip + thumbnail panel ghi (clips.json), proxy rỗng vẫn chạy được."""

    def test_manifest_ghep_clip_khong_can_proxy(self):
        import tempfile
        import troly_ai as ai
        with tempfile.TemporaryDirectory() as t:
            jpg = os.path.join(t, "a.jpg")
            open(jpg, "wb").write(b"j")
            ai.write_manifest(t, "P1", [("Folder/CLIP/C1.MP4", jpg), ("Folder/CLIP/C2.MP4", os.path.join(t, "khong_co.jpg"))])
            clips, orphan = ai.match_thumbs("P1", t, os.path.join(t, "px_rong"))
            self.assertEqual(orphan, 0)
            self.assertEqual([c["key"] for c in clips], ["C1|CLIP", "C2|CLIP"])
            self.assertEqual(ai.ck("Folder/CLIP/C1.MP4"), ("clip", "c1"))
            self.assertEqual(clips[0]["thumb"], jpg)
            self.assertIsNone(clips[1]["thumb"])                  # ảnh chưa có: bỏ qua, làm tiếp lần sau

    def test_ai_run_ghi_manifest_tu_thumbnail_panel(self):
        import troly_ai as ai
        t = KhongGhepDuoc("test_ai_info_bao_khong_ghep_duoc_kem_ly_do_va_thu_muc")
        t.setUp()
        try:
            jpg = os.path.join(t.tmp, "x.jpg")
            open(jpg, "wb").write(b"j")
            c = t.api._clips[0]
            t.api._thumb_done[c.uid] = (jpg, "")
            class J:                                              # tiến trình AI giả: chỉ ghi nhận đã được gọi start
                started = False
                def available(self): return True
                def start(self): J.started = True
                def running(self): return False
                def last_log(self): return ""
            t.api._ai_job = J()
            t.api.ai_run()
            self.assertTrue(J.started)
            rows = ai.load_manifest(t.tmp, t.name)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["thumb"], jpg)
        finally:
            t.tearDown()


if __name__ == "__main__":
    unittest.main()
