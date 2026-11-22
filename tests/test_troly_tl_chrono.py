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

    def test_verify_readback_catches_truncated_v1(self):
        pl = [{"track": "V1"}, {"track": "V1"}, {"track": "V1"}]
        got = [("V1", 0, 100), ("V1", 100, 200)]  # missing 3rd clip!
        ok, msgs = ttl.verify_readback(pl, got)
        self.assertFalse(ok)
        self.assertTrue(any("V1: có 2 clip, cần 3." in m for m in msgs))

    def test_create_cut_timeline_splits_duplicate_mediapoolitem_across_calls(self):
        import troly_resolve as tr

        class _FakeItem:
            def __init__(self, name, start, dur, left=0):
                self._name, self._s, self._d, self._l = name, start, dur, left
            def GetName(self): return self._name
            def GetStart(self): return self._s
            def GetEnd(self): return self._s + self._d
            def GetLeftOffset(self): return self._l
            def SetClipEnabled(self, v): return True

        class _FakeTL:
            def __init__(self, name):
                self._name = name
                self.v1 = []
                self._cur = 0
            def GetName(self): return self._name
            def GetStartFrame(self): return 0
            def GetItemListInTrack(self, kind, idx):
                return list(self.v1) if (kind == "video" and idx == 1) else []
            def add(self, infos):
                for ci in infos:
                    dur = ci["endFrame"] - ci["startFrame"]
                    self.v1.append(_FakeItem(ci["mediaPoolItem"], self._cur, dur, ci["startFrame"]))
                    self._cur += dur

        class _FakePool:
            def __init__(self):
                self.calls = []
                self.cur_tl = None
            def CreateTimelineFromClips(self, name, infos):
                # Enforce DaVinci 21 constraint: NO duplicate mediaPoolItem in a single call!
                mpis = [ci["mediaPoolItem"] for ci in infos]
                assert len(mpis) == len(set(mpis)), f"Duplicate mediaPoolItem in CreateTimelineFromClips: {mpis}"
                self.calls.append(("create", list(mpis)))
                tl = _FakeTL(name)
                tl.add(infos)
                self.cur_tl = tl
                return tl
            def AppendToTimeline(self, infos):
                mpis = [ci["mediaPoolItem"] for ci in infos]
                assert len(mpis) == len(set(mpis)), f"Duplicate mediaPoolItem in AppendToTimeline: {mpis}"
                self.calls.append(("append", list(mpis)))
                self.cur_tl.add(infos)
                return True

        class _FakeProj:
            def __init__(self, pool):
                self._pool = pool
                self._cur = None
            def GetName(self): return "FP_TEST"
            def GetTimelineCount(self): return 1 if self._pool.cur_tl else 0
            def GetTimelineByIndex(self, i): return self._pool.cur_tl
            def SetCurrentTimeline(self, tl):
                self._cur = tl
                return True
            def GetCurrentTimeline(self): return self._cur
            def GetMediaPool(self): return self._pool

        events = []
        fake_pool = _FakePool()
        w = tr.TrolyWorker.__new__(tr.TrolyWorker)
        w.project = _FakeProj(fake_pool)
        w.project_name = "FP_TEST"
        w.pm = type("PM", (), {"GetCurrentProject": lambda self_: w.project})()
        w.items = {f"u{i}": ("Master", f"C{i}.MP4") for i in range(1, 6)}
        w.post = lambda ev, data: events.append((ev, data))
        w._require_current = lambda: None
        w._make_current = lambda tl: w.project.SetCurrentTimeline(tl)

        # u2 appears TWICE in a row (Shift+I/O multi-segment), followed by u3, u4, u5
        segs = [
            {"uid": "u1", "a": 50, "b": 150, "pct": 100.0, "track": "V1", "start_f": 0, "mute": False},
            {"uid": "u2", "a": 0, "b": 250, "pct": 100.0, "track": "V1", "start_f": 100, "mute": False},
            {"uid": "u2", "a": 300, "b": 450, "pct": 100.0, "track": "V1", "start_f": 350, "mute": False},
            {"uid": "u3", "a": 50, "b": 150, "pct": 100.0, "track": "V1", "start_f": 500, "mute": False},
            {"uid": "u4", "a": 50, "b": 150, "pct": 100.0, "track": "V1", "start_f": 600, "mute": True},
        ]
        w.do_create_cut_timeline(("TestMultiSeg", segs))
        # Chunk 1: [C1, C2] via CreateTimelineFromClips; Chunk 2: [C2] alone + [C3, C4] via AppendToTimeline
        self.assertEqual(w.pool.calls, [
            ("create", ["C1.MP4", "C2.MP4"]),
            ("append", ["C2.MP4"]),
            ("append", ["C3.MP4", "C4.MP4"]),
        ])
        self.assertEqual(len(w.pool.cur_tl.v1), 5)
        self.assertEqual([it.GetName() for it in w.pool.cur_tl.v1], ["C1.MP4", "C2.MP4", "C2.MP4", "C3.MP4", "C4.MP4"])
        self.assertTrue(all(it.GetLeftOffset() >= 0 for it in w.pool.cur_tl.v1))
        self.assertEqual(events[-1][0], "cut_timeline_created")
        self.assertTrue(events[-1][1]["layout_ok"])

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
