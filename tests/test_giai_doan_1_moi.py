# -*- coding: utf-8 -*-
"""Kiểm tra chéo Giai đoạn 1:
- troly_vision_io: tính độ nét (Laplacian) & độ rung (Optical Flow) trên video giả lập.
- troly_core.compute_sug hỗ trợ vision & giữ nguyên tương thích speech/rule.
- Giao diện: Zoom Page 1/2, Hover Scrub không giữ chuột, J/K/L, I/O ở Bước 2 & 3, P gắn sao.
"""
import os
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np
import cv2

import sys
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
WEB = os.path.join(APP, "troly_web")
sys.path.insert(0, APP)

import troly_core as tc
import troly_vision_io as tvio


class TestGiaiDoan1(unittest.TestCase):
    def test_vision_io_chons_doan_net_va_em(self):
        """Tạo video 6 giây: 0-2s mờ+rung, 2-6s nét+êm. Thuật toán phải chọn đoạn sau 1.3s (nét & êm)."""
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "test_proxy.avi")
            fps = 10.0
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            vw = cv2.VideoWriter(p, fourcc, fps, (320, 180))
            for i in range(60):  # 6 giây
                img = np.zeros((180, 320, 3), dtype=np.uint8)
                if i < 20:
                    # Đoạn đầu: di chuyển mạnh và mờ
                    cv2.circle(img, (40 + (i * 12) % 240, 90), 30, (120, 120, 120), -1)
                    img = cv2.GaussianBlur(img, (15, 15), 5)
                else:
                    # Đoạn sau: đứng yên và cực nét (ô bàn cờ nhỏ)
                    for y in range(20, 160, 20):
                        for x in range(40, 280, 20):
                            if ((x + y) // 20) % 2 == 0:
                                cv2.rectangle(img, (x, y), (x + 15, y + 15), (255, 255, 255), -1)
                vw.write(img)
            vw.release()

            res = tvio.analyze_proxy_vision(p, dur=6.0, target_len=3.0, head_skip=1.3, max_samples=30)
            self.assertIsNotNone(res)
            self.assertGreaterEqual(res["in"], 1.3)
            self.assertGreater(res["out"] - res["in"], 2.0)
            self.assertIn("Hình ảnh", res["rule"])

    def test_compute_sug_uu_tien_speech_roi_vision_roi_rule(self):
        plan = tc.new_plan("2026.11.21.LV_Test")
        clip = SimpleNamespace(rel="01_footage/A001.MP4", dur=12.0)
        vis = {"in": 1.5, "out": 5.0, "rule": "Hình ảnh (Nét 500 · Êm 0.2)"}

        # 1. Có speech -> dùng speech
        s1 = tc.compute_sug(plan, clip, "Decor", [{"t0": 2.0, "t1": 6.0}], vision=vis)
        self.assertEqual(s1["src"], "speech")

        # 2. Không speech, có vision -> dùng vision
        s2 = tc.compute_sug(plan, clip, "Decor", [], vision=vis)
        self.assertEqual(s2["src"], "vision")
        self.assertEqual(s2["in"], 1.5)
        self.assertEqual(s2["out"], 5.0)

        # 3. Không speech, không vision -> rơi về rule
        s3 = tc.compute_sug(plan, clip, "Decor", [], vision=None)
        self.assertEqual(s3["src"], "rule")

    def test_web_co_zoom_hover_jkl_va_phim_p(self):
        html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
        app_js = open(os.path.join(WEB, "app.js"), encoding="utf-8").read()
        pl_js = open(os.path.join(WEB, "player.js"), encoding="utf-8").read()

        self.assertIn('id="g1Zoom"', html)
        self.assertIn('id="g2Zoom"', html)
        self.assertIn("marquee-box", app_js)
        self.assertIn("plAttachHoverScrub", pl_js)
        self.assertIn("plJkl", pl_js)
        self.assertIn('e.code === "KeyP"', app_js)


if __name__ == "__main__":
    unittest.main()
