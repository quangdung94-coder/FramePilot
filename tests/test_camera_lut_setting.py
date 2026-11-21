import os
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
WEB = os.path.join(APP, "troly_web")
if APP not in sys.path:
    sys.path.insert(0, APP)

import troly_api as ta  # noqa: E402
import troly_core as tc  # noqa: E402
import troly_env as te  # noqa: E402


def _clip(uid, name, lut=""):
    return tc.Clip(
        uid=uid,
        name=name,
        rel=name,
        path=os.path.join("D:\\Media", name),
        t_start=None,
        t_src="mtime",
        dur=10.0,
        fps=25.0,
        camera="",
        lut=lut,
    )


class TestCameraLutSetting(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_cfg = os.environ.get("TROLY_CONFIG")
        self._cfg_path = os.path.join(self._tmp.name, "config.json")
        os.environ["TROLY_CONFIG"] = self._cfg_path
        self._data_root = os.path.join(self._tmp.name, "data")
        os.makedirs(self._data_root, exist_ok=True)
        te.save_config({"data_root": self._data_root})

    def tearDown(self):
        if self._old_cfg is None:
            os.environ.pop("TROLY_CONFIG", None)
        else:
            os.environ["TROLY_CONFIG"] = self._old_cfg
        self._tmp.cleanup()

    def _make_api(self, project="LV_Test"):
        return ta.TrolyApi(project, self._data_root, start_worker=False, thumb_workers=1)

    def test_effective_lut_priority_davinci_then_setting_prefix(self):
        te.save_config({
            "data_root": self._data_root,
            "camera_luts": {
                "C0": r"D:\LUTs\Sony_SLog3.cube",
                "DG": r"D:\LUTs\DJI_DLog.cube",
                "DG1": r"D:\LUTs\DJI_Pocket.cube",
            },
        })
        api = self._make_api()
        c_dv = _clip("u1", "C0001.MP4", lut="DaVinci_Input.cube")
        c_sony = _clip("u2", "C0002.MP4", lut="")
        c_dji = _clip("u3", "dg0001.mp4", lut="")
        c_dji_long = _clip("u4", "DG1002.MP4", lut="")
        c_other = _clip("u5", "DSC_0001.MP4", lut="")

        self.assertEqual(api._effective_lut(c_dv), "DaVinci_Input.cube")
        self.assertEqual(api._effective_lut(c_sony), r"D:\LUTs\Sony_SLog3.cube")
        self.assertEqual(api._effective_lut(c_dji), r"D:\LUTs\DJI_DLog.cube")
        self.assertEqual(api._effective_lut(c_dji_long), r"D:\LUTs\DJI_Pocket.cube")
        self.assertEqual(api._effective_lut(c_other), "")

    def test_settings_get_pick_save_camera_luts(self):
        api = self._make_api()
        api._clips = [
            _clip("u1", "C0001.MP4"),
            _clip("u2", "C0002.MP4"),
            _clip("u3", "DG0001.MP4"),
        ]
        api.pick_file_fn = lambda: r"D:\LUTs\Wedding.cube"
        self.assertEqual(api.settings_pick_lut(), {"path": r"D:\LUTs\Wedding.cube"})

        res = api.settings_save(
            cache_root="",
            srt_root="",
            camera_luts={"C0": r"D:\LUTs\Wedding.cube", "  ": "skip", "DG": ""},
        )
        self.assertTrue(res.get("ok"))
        self.assertEqual(te.camera_luts(), {"C0": r"D:\LUTs\Wedding.cube"})

        got = api.settings_get()
        self.assertEqual(got["camera_luts"], {"C0": r"D:\LUTs\Wedding.cube"})
        prefixes = {d["prefix"]: d["count"] for d in got["detected_prefixes"]}
        self.assertEqual(prefixes.get("C"), 2)
        self.assertEqual(prefixes.get("DG"), 1)

    def test_thumbs_refresh_clears_only_current_project_and_bumps_gen(self):
        api = self._make_api(project="Project_A")
        other_thumb_dir = os.path.join(self._data_root, "cache", "troly_thumbs", "Project_B")
        os.makedirs(other_thumb_dir, exist_ok=True)
        other_marker = os.path.join(other_thumb_dir, "keep.jpg")
        with open(other_marker, "wb") as f:
            f.write(b"keep")

        os.makedirs(api._thumbs.cache_dir, exist_ok=True)
        cur_marker = os.path.join(api._thumbs.cache_dir, "old.jpg")
        with open(cur_marker, "wb") as f:
            f.write(b"old")

        api._thumb_done["u1"] = (cur_marker, "")
        api._inflight.add("u2")
        api._lut_payloads = {"x.cube": {"title": "x"}}
        old_gen = api._thumb_gen

        api.thumbs_refresh()

        self.assertFalse(os.path.exists(cur_marker))
        self.assertTrue(os.path.exists(other_marker))
        self.assertEqual(api._thumb_done, {})
        self.assertEqual(api._inflight, set())
        self.assertEqual(api._lut_payloads, {})
        self.assertEqual(api._thumb_gen, old_gen + 1)

        # Stale callback from old generation must be ignored
        fut = types.SimpleNamespace(result=lambda: ("u1", cur_marker, "stale"))
        api._thumb_ready(fut, "u1", gen=old_gen)
        self.assertNotIn("u1", api._thumb_done)

    def test_web_ui_lut_setting_and_page4_webgl_wiring(self):
        with open(os.path.join(WEB, "index.html"), "r", encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(WEB, "app.js"), "r", encoding="utf-8") as f:
            app_js = f.read()
        with open(os.path.join(WEB, "player.js"), "r", encoding="utf-8") as f:
            player_js = f.read()
        with open(os.path.join(WEB, "speech.js"), "r", encoding="utf-8") as f:
            speech_js = f.read()

        for id_name in ("setLutAdd", "setRefreshThumbs", "setLutList"):
            self.assertIn(f'id="{id_name}"', html)
        self.assertIn("settings_pick_lut", app_js)
        self.assertIn("thumbs_refresh", app_js)
        self.assertIn("function lutAttachEl", player_js)
        self.assertIn("function lutDetachEl", player_js)
        self.assertIn("lutAttachEl(", speech_js)
        self.assertIn("lutDetachEl(", speech_js)


if __name__ == "__main__":
    unittest.main()
