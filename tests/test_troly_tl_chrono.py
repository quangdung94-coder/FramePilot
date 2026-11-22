"""Unit tests for Page 5 chronological sort mode (Truyền thống) vs bin-grouped mode (PSC)."""
import datetime
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

import troly_core as tc  # noqa: E402
import troly_dur as td  # noqa: E402
import troly_tl as ttl  # noqa: E402


def _mk_clip(uid, name, hh, mm, ss=0, dur=8.0):
    dt = datetime.datetime(2026, 11, 22, hh, mm, ss)
    return tc.Clip(
        uid=uid, name=name, path="J:/test/" + name, rel="01/" + name,
        dur=dur, fps=25.0, frames=int(dur * 25), t_start=dt, t_src="created",
        camera="A", bin_path="Master", clip_color="", mark_in=None, mark_out=None, tc="00:00:00:00",
    )


class TestPage5ChronoMode(unittest.TestCase):
    def _sample(self, style="traditional"):
        # Interleaved event sequence inside one stage:
        # 10:02 Cụ ông bà -> 10:05 Phát biểu -> 10:12 Trao quà -> 10:18 Cụ ông bà -> 10:30 Cụ ông bà
        clips = [
            _mk_clip("u1", "C01.MP4", 10, 2, 0),
            _mk_clip("u2", "C02.MP4", 10, 5, 0),
            _mk_clip("u3", "C03.MP4", 10, 12, 0),
            _mk_clip("u4", "C04.MP4", 10, 18, 0),
            _mk_clip("u5", "C05.MP4", 10, 30, 0),
        ]
        stages = [tc.make_stage("Nghi lễ mừng thọ", 600, 660, ["Cụ ông cụ bà", "Phát biểu", "Trao quà"], 0)]
        assign = {c.uid: 0 for c in clips}
        plan = tc.new_plan("FP_TEST_TT")
        plan["shoot_style"] = style
        plan["stars"] = {c.rel: True for c in clips}
        for c, bn in zip(clips, ["Cụ ông cụ bà", "Phát biểu", "Trao quà", "Cụ ông cụ bà", "Cụ ông cụ bà"]):
            tc.set_label(plan, c, "Nghi lễ mừng thọ", bn)
        return plan, clips, assign, stages

    def test_both_styles_default_to_bin_grouping_so_subbins_stay_solid(self):
        for style in ("traditional", "psc"):
            plan, clips, assign, stages = self._sample(style=style)
            self.assertEqual(ttl.sort_mode_of(plan), "bin")
            r = td.build(plan, clips, assign, stages, tl_fps=25.0)
            pl = ttl.placements(r, plan)
            # Grouped by bin (each bin con = 1 solid block; clips inside bin stay in chronological order)
            self.assertEqual([x["uid"] for x in pl], ["u1", "u4", "u5", "u2", "u3"])

    def test_move_block_reorders_subbin_and_switches_from_chrono_to_bin(self):
        plan, clips, assign, stages = self._sample(style="traditional")
        self.assertIsNone(ttl.set_sort_mode(plan, "chrono"))
        self.assertEqual(ttl.sort_mode_of(plan), "chrono")
        r0 = td.build(plan, clips, assign, stages, tl_fps=25.0)
        # Drag "Trao quà" to position 0 -> auto-switches to 'bin' so sub-bin order takes effect immediately
        self.assertIsNone(ttl.move_block(plan, r0, "Nghi lễ mừng thọ|Trao quà", "Nghi lễ mừng thọ", 0))
        self.assertEqual(ttl.sort_mode_of(plan), "bin")
        r = td.build(plan, clips, assign, stages, tl_fps=25.0)
        pl = ttl.placements(r, plan)
        self.assertEqual([x["uid"] for x in pl], ["u3", "u1", "u4", "u5", "u2"])

    def test_explicit_chrono_mode_preserves_exact_time_order_and_v2_overlay(self):
        plan, clips, assign, stages = self._sample(style="psc")
        self.assertIsNone(ttl.set_sort_mode(plan, "chrono"))
        self.assertEqual(ttl.sort_mode_of(plan), "chrono")
        # Move Trao quà to V2 while keeping V1 strictly chronological!
        r0 = td.build(plan, clips, assign, stages, tl_fps=25.0)
        self.assertIsNone(ttl.set_track(plan, r0, "Nghi lễ mừng thọ|Trao quà", "V2", at=5.0))
        r = td.build(plan, clips, assign, stages, tl_fps=25.0)
        pl = ttl.placements(r, plan)
        v1 = [x["uid"] for x in pl if x["track"] == "V1"]
        v2 = [x["uid"] for x in pl if x["track"] == "V2"]
        self.assertEqual(v1, ["u1", "u2", "u4", "u5"])
        self.assertEqual(v2, ["u3"])
        for a, b in zip([x for x in pl if x["track"] == "V1"], [x for x in pl if x["track"] == "V1"][1:]):
            self.assertAlmostEqual(a["start_s"] + a["dur_s"], b["start_s"], places=2)

    def test_chrono_runs_merges_only_adjacent_same_bin_clips(self):
        plan, clips, assign, stages = self._sample(style="traditional")
        ttl.set_sort_mode(plan, "chrono")
        r = td.build(plan, clips, assign, stages, tl_fps=25.0)
        lay = ttl.layout(r, plan)
        runs = lay["chrono_runs"]["Nghi lễ mừng thọ"]
        # u1(Cụ ông bà) -> u2(Phát biểu) -> u3(Trao quà) -> u4+u5(Cụ ông bà merged into 1 run of 2 clips)
        self.assertEqual([(rn["bin"], rn["n_clips"]) for rn in runs], [
            ("Cụ ông cụ bà", 1), ("Phát biểu", 1), ("Trao quà", 1), ("Cụ ông cụ bà", 2)
        ])

    def test_per_clip_mute_a1_propagates_to_placements_and_summary(self):
        plan, clips, assign, stages = self._sample(style="traditional")
        # Mute only clip u1 & u3 (keep u2, u4, u5 unmuted)
        self.assertTrue(tc.toggle_mute(plan, clips[0]))
        self.assertTrue(tc.toggle_mute(plan, clips[2]))
        self.assertTrue(tc.is_muted(plan, clips[0]))
        self.assertFalse(tc.is_muted(plan, clips[1]))

        r = td.build(plan, clips, assign, stages, tl_fps=25.0)
        pl = ttl.placements(r, plan)
        muted_uids = [x["uid"] for x in pl if x["mute"]]
        self.assertEqual(muted_uids, ["u1", "u3"])
        sm = ttl.summary(r, plan)
        self.assertEqual(sm["n_clip_muted"], 2)

        # Also works in bin (PSC) mode!
        ttl.set_sort_mode(plan, "bin")
        pl_bin = ttl.placements(r, plan)
        self.assertEqual(sorted(x["uid"] for x in pl_bin if x["mute"]), ["u1", "u3"])

        # Toggling again unmutes cleanly
        self.assertFalse(tc.toggle_mute(plan, clips[0]))
        self.assertFalse(tc.is_muted(plan, clips[0]))

    def test_page4_mute_ui_and_keym_wiring(self):
        with open(os.path.join(APP, "troly_web", "index.html"), encoding="utf-8") as f:
            html_src = f.read()
        with open(os.path.join(APP, "troly_web", "speech.js"), encoding="utf-8") as f:
            sp_src = f.read()
        self.assertIn('id="lnMute"', html_src)
        self.assertIn('id="d5SortMode"', html_src)
        self.assertIn('e.code === "KeyM"', sp_src)
        self.assertIn("api().toggle_mute", sp_src)


if __name__ == "__main__":
    unittest.main()
