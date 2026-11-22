"""Unit tests for Event templates/AI/phrases/5m preset & DaVinci Media Pool Recorder 2-stage auto-sync + A1(OFF)/A2(ON) export."""
import json
import os
import sys
import tempfile
import unittest
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

import troly_ai as ai  # noqa: E402
import troly_core as tc  # noqa: E402
import troly_resolve as tr  # noqa: E402
import troly_sync as tsy  # noqa: E402


def _write_wav_f32(path, samples, sr=16000):
    s = np.clip(samples, -1.0, 1.0)
    pcm = (s * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


class TestEventAndRecorderSync(unittest.TestCase):
    def test_two_event_templates_compact_subbins_and_rules(self):
        t1 = "Event · Hội nghị / Khai trương / Khai trường"
        t2 = "Event · Gala Dinner / Year End Party"
        self.assertIn(t1, tc.BUILTIN_TEMPLATES)
        self.assertIn(t2, tc.BUILTIN_TEMPLATES)
        for tn in (t1, t2):
            self.assertIn(tn, tc.TEMPLATE_EVENTS)
            for st_name, bins in tc.BUILTIN_TEMPLATES[tn]:
                self.assertLessEqual(len(bins), 6, f"{tn}/{st_name} has >6 sub-bins")
                self.assertIn(st_name, tc.TEMPLATE_EVENTS[tn])
        # Event In/Out rules
        _, mn, mx, _ = tc.builtin_rule("Logo · Sản phẩm")
        self.assertEqual((mn, mx), (2.5, 4.0))
        _, mn2, mx2, _ = tc.builtin_rule("Vinh danh · Trao giải")
        self.assertEqual((mn2, mx2), (3.0, 5.0))

    def test_event_ai_concepts_and_synonyms(self):
        ev_ids = {c["id"] for c in ai.CONCEPTS if c["group"] == "Event"}
        self.assertGreaterEqual(len(ev_ids), 8)
        self.assertEqual(ai.infer_concept("Logo · Sản phẩm"), "ev_thuong_hieu")
        self.assertEqual(ai.infer_concept("Đánh trống khai trường"), "ev_nghi_thuc")
        self.assertEqual(ai.infer_concept("Múa lân"), "mua_lan")
        self.assertEqual(ai.infer_concept("Opening show"), "ev_van_nghe")
        self.assertEqual(ai.infer_concept("Lucky draw"), "ev_van_nghe")
        self.assertEqual(ai.infer_concept("Keynote"), "ev_phat_bieu")
        self.assertEqual(ai.infer_concept("Trao học bổng"), "ev_vinh_danh")
        self.assertEqual(ai.infer_concept("Khán giả vỗ tay"), "ev_khan_gia")
        self.assertEqual(ai.infer_concept("Check-in · Photobooth"), "ev_checkin")

    def test_event_speech_phrases_and_ui_preset(self):
        with open(os.path.join(APP, "wedding_phrases.json"), encoding="utf-8") as f:
            phr = json.load(f)
        self.assertIn("event", phr["groups"])
        self.assertIn("khai mạc", phr["groups"]["event"])
        self.assertIn("khai trương", phr["groups"]["event"])
        with open(os.path.join(APP, "troly_web", "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn('data-min="5" data-style="event">Event 5:00</button>', html)
        for st_val in ("teaser", "highlight", "event", "psc", "traditional"):
            self.assertIn(st_val, tc.SHOOT_STYLES)
            self.assertIn(f'value="{st_val}"', html)
        self.assertIn('id="lnRecBtn"', html)
        self.assertIn('id="lnRecBox"', html)

    def test_two_stage_audio_sync_locks_exact_offset_with_noise(self):
        rng = np.random.default_rng(42)
        sr = 16000
        rec_dur = 45.0
        rec = rng.normal(0.0, 0.02, int(rec_dur * sr)).astype(np.float32)
        # Put distinct speech-like modulated bursts around 23.40s .. 33.40s
        true_off = 23.40
        t_seg = np.arange(int(10.0 * sr), dtype=np.float32) / sr
        env = (np.sin(2 * np.pi * 1.3 * t_seg) > 0).astype(np.float32) * (0.5 + 0.5 * np.sin(2 * np.pi * 3.7 * t_seg))
        sig = env * (0.4 * np.sin(2 * np.pi * 420 * t_seg) + 0.3 * np.sin(2 * np.pi * 890 * t_seg) + 0.25 * rng.normal(0, 1, len(t_seg)))
        i0 = int(true_off * sr)
        rec[i0:i0 + len(sig)] += sig.astype(np.float32)
        # Camera clip: same 10s segment + camera hall noise
        cam = sig.astype(np.float32) + rng.normal(0.0, 0.08, len(sig)).astype(np.float32)
        # Unrelated silent/random clip
        unrelated = rng.normal(0.0, 0.03, int(6.0 * sr)).astype(np.float32)

        with tempfile.TemporaryDirectory() as td:
            p_rec = os.path.join(td, "ZOOM0001.WAV")
            p_cam = os.path.join(td, "C001.WAV")
            p_bad = os.path.join(td, "FLYCAM.WAV")
            _write_wav_f32(p_rec, rec, sr=sr)
            _write_wav_f32(p_cam, cam, sr=sr)
            _write_wav_f32(p_bad, unrelated, sr=sr)

            rec_env, rdur = tsy.extract_envelope(p_rec)
            self.assertIsNotNone(rec_env)
            off, conf = tsy.sync_clip_to_recorder(p_cam, p_rec, rec_env=rec_env, rec_dur=rdur, clip_dur=10.0)
            self.assertIsNotNone(off, f"Expected sync match, got conf={conf}")
            self.assertAlmostEqual(off, true_off, delta=0.05)
            self.assertGreaterEqual(conf, 0.35)

            off_bad, _ = tsy.sync_clip_to_recorder(p_bad, p_rec, rec_env=rec_env, rec_dur=rdur, clip_dur=6.0)
            self.assertIsNone(off_bad)

    def test_davinci_export_places_recorder_a2_on_and_disables_a1_by_default(self):
        self.assertTrue(tr.is_audio_only({"Type": "Audio"}))
        self.assertFalse(tr.is_audio_only({"Type": "Video + Audio"}))

        class _FakeItem:
            def __init__(self, name, start, dur):
                self._name, self._s, self._d = name, start, dur
                self.enabled = True
            def GetName(self): return self._name
            def GetStart(self): return self._s
            def GetEnd(self): return self._s + self._d
            def GetLeftOffset(self): return 0
            def SetClipEnabled(self, v):
                self.enabled = bool(v)
                return True

        class _FakeTL:
            def __init__(self, name):
                self._name = name
                self.v1, self.a1, self.a2 = [], [], []
                self.a_tracks = 1
                self._cur = 0
            def GetName(self): return self._name
            def GetStartFrame(self): return 0
            def GetTrackCount(self, kind): return self.a_tracks if kind == "audio" else 1
            def AddTrack(self, kind, sub=None):
                if kind == "audio":
                    self.a_tracks += 1
                return True
            def GetItemListInTrack(self, kind, idx):
                if kind == "video" and idx == 1:
                    return list(self.v1)
                if kind == "audio" and idx == 1:
                    return list(self.a1)
                if kind == "audio" and idx == 2:
                    return list(self.a2)
                return []
            def add_v1(self, infos):
                for ci in infos:
                    dur = ci["endFrame"] - ci["startFrame"]
                    self.v1.append(_FakeItem(ci["mediaPoolItem"], self._cur, dur))
                    self.a1.append(_FakeItem(ci["mediaPoolItem"], self._cur, dur))
                    self._cur += dur

        class _FakePool:
            def __init__(self):
                self.cur_tl = None
                self.a2_calls = []
            def CreateTimelineFromClips(self, name, infos):
                tl = _FakeTL(name)
                tl.add_v1(infos)
                self.cur_tl = tl
                return tl
            def AppendToTimeline(self, infos):
                for ci in infos:
                    if ci.get("mediaType") == 2 and ci.get("trackIndex") == 2:
                        self.a2_calls.append(ci)
                        dur = ci["endFrame"] - ci["startFrame"]
                        self.cur_tl.a2.append(_FakeItem(ci["mediaPoolItem"], ci["recordFrame"], dur))
                return True

        class _FakeProj:
            def __init__(self, pool):
                self._pool = pool
                self._cur = None
            def GetName(self): return "FP_TEST_REC"
            def GetTimelineCount(self): return 1 if self._pool.cur_tl else 0
            def GetTimelineByIndex(self, i): return self._pool.cur_tl
            def SetCurrentTimeline(self, tl):
                self._cur = tl
                return True
            def GetCurrentTimeline(self): return self._cur
            def GetMediaPool(self): return self._pool

        events = []
        pool = _FakePool()
        w = tr.TrolyWorker.__new__(tr.TrolyWorker)
        w.project = _FakeProj(pool)
        w.project_name = "FP_TEST_REC"
        w.pm = type("PM", (), {"GetCurrentProject": lambda self_: w.project})()
        w.items = {"u1": ("Master", "C01.MP4"), "u2": ("Master", "C02.MP4"), "u3": ("Master", "C03.MP4")}
        w.audio_items = {"rec1": ("Master/Audio", "ZOOM0001.WAV")}
        w.post = lambda ev, data: events.append((ev, data))
        w._require_current = lambda: None
        w._make_current = lambda tl: w.project.SetCurrentTimeline(tl)

        segs = [
            # Clip 1: synced to Recorder, NOT muted -> A1 OFF, A2 ON!
            {"uid": "u1", "a": 25, "b": 125, "pct": 100.0, "track": "V1", "start_f": 0, "mute": False, "rec_uid": "rec1", "rec_a": 500, "rec_b": 600},
            # Clip 2: synced to Recorder, explicitly muted (M) -> BOTH A1 OFF and A2 OFF!
            {"uid": "u2", "a": 25, "b": 125, "pct": 100.0, "track": "V1", "start_f": 100, "mute": True, "rec_uid": "rec1", "rec_a": 900, "rec_b": 1000},
            # Clip 3: no Recorder sync, NOT muted -> A1 stays ON, no A2!
            {"uid": "u3", "a": 25, "b": 125, "pct": 100.0, "track": "V1", "start_f": 200, "mute": False},
        ]
        w.do_create_cut_timeline(("EventTest", segs))
        tl = pool.cur_tl
        self.assertEqual(len(pool.a2_calls), 2)
        self.assertEqual(tl.a_tracks, 2)
        # Clip 1: A1 OFF, A2 ON
        self.assertFalse(tl.a1[0].enabled)
        self.assertTrue(tl.a2[0].enabled)
        # Clip 2: both OFF
        self.assertFalse(tl.a1[1].enabled)
        self.assertFalse(tl.a2[1].enabled)
        # Clip 3: A1 ON
        self.assertTrue(tl.a1[2].enabled)
        self.assertEqual(events[-1][1]["n_rec_a2"], 2)


if __name__ == "__main__":
    unittest.main()
