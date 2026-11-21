# -*- coding: utf-8 -*-
"""Kiểm tra chéo Giai đoạn 2 (SigLIP trong troly_ai) và Giai đoạn 3 (Nhiều camera Trang 2 & Trang 3)."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
WEB = os.path.join(APP, "troly_web")
sys.path.insert(0, APP)

import troly_ai as ai


class TestGiaiDoan2Va3(unittest.TestCase):
    def test_siglip_fallback_va_tach_cache(self):
        with tempfile.TemporaryDirectory() as td:
            # Chưa có SigLIP -> dùng thư mục embed cũ
            self.assertFalse(ai.has_siglip(td))
            self.assertIn("troly_embed", ai.embed_dir(td, "P1"))
            self.assertNotIn("siglip", ai.embed_dir(td, "P1"))

            # Có thư mục SigLIP -> tự động tách sang troly_embed_siglip
            os.makedirs(os.path.join(td, "models", ai.SIGLIP_DIR_NAME, "models--timm--ViT-B-16-SigLIP"))
            self.assertTrue(ai.has_siglip(td))
            self.assertIn("troly_embed_siglip", ai.embed_dir(td, "P1"))

    def test_multicam_trang_2_va_3_trong_web(self):
        with open(os.path.join(WEB, "index.html"), encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(WEB, "multicam.js"), encoding="utf-8") as f:
            mc = f.read()

        self.assertIn('id="mcBar2"', html)
        self.assertIn('id="mcLanes2"', html)
        self.assertIn('id="mcLanes3"', html)
        self.assertIn('src="multicam.js"', html)

        self.assertIn("mcModeLane", mc)
        self.assertIn("mcSyncTg", mc)
        self.assertIn("let mcSyncSug = false;", mc)  # công tắc mặc định TẮT theo quy tắc


if __name__ == "__main__":
    unittest.main()
