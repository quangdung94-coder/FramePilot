# -*- coding: utf-8 -*-
"""Kiểm tra tính năng Setting (bánh răng) tùy chọn thư mục Cache & SRT."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
WEB = os.path.join(APP, "troly_web")
sys.path.insert(0, APP)

import troly_env as te
import troly_api as ta


class TestSettingsCacheSrt(unittest.TestCase):
    def test_settings_get_save_va_chan_repo(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.json")
            data_dir = os.path.join(td, "data")
            os.makedirs(data_dir, exist_ok=True)
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"data_root": data_dir}, f)

            old_env = os.environ.get("TROLY_CONFIG")
            os.environ["TROLY_CONFIG"] = cfg
            try:
                api = ta.TrolyApi("2026.11.21.LV_Test", data_dir)
                try:
                    g0 = api.settings_get()
                    self.assertEqual(g0["cache_root"], data_dir)
                    self.assertEqual(g0["srt_root"], "")

                    # Chặn lưu vào thư mục mã nguồn git
                    repo_dir = os.path.abspath(os.path.join(HERE, ".."))
                    bad = api.settings_save(repo_dir, "")
                    self.assertIn("error", bad)

                    # Lưu hợp lệ
                    new_cache = os.path.join(td, "custom_cache")
                    new_srt = os.path.join(td, "custom_srt")
                    ok = api.settings_save(new_cache, new_srt)
                    self.assertTrue(ok.get("ok"))
                    self.assertEqual(te.cache_root(), new_cache)
                    self.assertEqual(te.srt_root(), new_srt)
                    self.assertTrue(api._thumbs.root.startswith(new_cache))
                finally:
                    api.close()
            finally:
                if old_env is None:
                    os.environ.pop("TROLY_CONFIG", None)
                else:
                    os.environ["TROLY_CONFIG"] = old_env

    def test_giao_dien_co_nut_banh_rang_va_modal(self):
        with open(os.path.join(WEB, "index.html"), encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(WEB, "app.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn('id="btnSettings"', html)
        self.assertIn('id="settingsModal"', html)
        self.assertIn("initSettingsModal", js)


if __name__ == "__main__":
    unittest.main()
