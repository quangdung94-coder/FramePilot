"""Bước 5 bản 3: API sắp xếp timeline (lưu theo project, nhớ khi mở lại, đổi tên) và worker tạo timeline MỚI có V1/V2, Slow, tắt tiếng trên DaVinci GIẢ
mô phỏng đúng những gì đã ĐO THẬT 18/11/2026 (ripple True đẩy clip sau; ripple False giữ nguyên độ dài; ripple ở V2 không khóa V1 thì làm hỏng V1;
SetClipEnabled chỉ chạy trên timeline hiện tại). Tên ví dụ LV_Ten."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import test_troly as T                # noqa: E402
import test_troly_dur_api as D        # noqa: E402
import troly_api as ta                # noqa: E402
import troly_core as tc               # noqa: E402

TL_START = 90000                      # timeline bắt đầu ở 01:00:00:00 như DaVinci thật (25p)


class FItemTl(object):
    """Clip trên timeline giả: độ dài frame = frame gốc / fps gốc x fps timeline (100%)."""

    def __init__(self, tl, kind, track, name, start, base_len, mpi):
        self.tl, self.kind, self.track, self.name, self.start, self.base, self.mpi = tl, kind, track, name, start, base_len, mpi
        self.speed, self.enabled, self.len = 100.0, True, base_len

    def GetName(self):
        return self.name

    def GetStart(self, *_a):
        return self.start

    def GetEnd(self, *_a):
        return self.start + self.len

    def GetSpeed(self):
        return {"Percentage": self.speed}

    def GetClipEnabled(self):
        return self.enabled

    def SetClipEnabled(self, v):
        if self.tl.project.current is not self.tl:                   # đo thật: chỉ chạy trên timeline hiện tại
            return False
        self.enabled = bool(v)
        return True

    def SetSpeed(self, opts):
        pct = float(opts["Percentage"])
        ripple = bool(opts.get("RippleTimeline", False))
        old_end = self.GetEnd()
        new_len = int(round(self.base * 100.0 / pct)) if ripple else self.len        # đo thật: ripple False giữ nguyên độ dài (cắt bớt source)
        self.speed = pct
        delta = new_len - self.len
        self.len = new_len
        if ripple and delta:
            self.tl.ripple(self, old_end, delta)
        return True


class FTl(object):
    def __init__(self, project, name):
        self.project, self.name = project, name
        self.items = {("video", 1): [], ("video", 2): [], ("video", 3): [], ("audio", 1): [], ("audio", 2): [], ("audio", 3): []}
        self.locked = set()
        self.corrupt = False
        self.fps = 25.0

    def GetName(self):
        return self.name

    def GetStartFrame(self):
        return TL_START

    def GetTrackCount(self, kind):
        return len([k for k in self.items if k[0] == kind])

    def AddTrack(self, kind, *_a):
        self.items[(kind, self.GetTrackCount(kind) + 1)] = []
        return True

    def SetTrackLock(self, kind, i, v):
        (self.locked.add if v else self.locked.discard)((kind, i))
        return True

    def GetIsTrackLocked(self, kind, i):
        return (kind, i) in self.locked

    def GetItemListInTrack(self, kind, i):
        return sorted(self.items.get((kind, i), []), key=lambda x: x.start)

    def add(self, track, mpi, a, b, rec):
        src_fps = float(mpi.GetClipProperty("FPS"))
        n = int(round((b - a) / src_fps * self.fps))
        self.items[("video", track)].append(FItemTl(self, "video", track, mpi.GetClipProperty("File Name"), rec, n, mpi))
        self.items[("audio", track)].append(FItemTl(self, "audio", track, mpi.GetClipProperty("File Name"), rec, n, mpi))

    def ripple(self, item, old_end, delta):
        """Ripple của DaVinci: đẩy mọi thứ sau điểm cuối cũ trên các track KHÔNG khóa; clip nằm vắt qua điểm đó thì bị cắt đôi (ở đây: đánh dấu hỏng)."""
        for key, lst in self.items.items():
            if key in self.locked or key == (item.kind, item.track):
                continue
            for it in lst:
                if it.start < old_end < it.GetEnd():
                    self.corrupt = True
                elif it.start >= old_end:
                    it.start += delta
        for it in self.items[(item.kind, item.track)]:
            if it is not item and it.start >= old_end:
                it.start += delta
        # tiếng đi cùng hình
        other = ("audio" if item.kind == "video" else "video", item.track)
        for it in self.items[other]:
            if it.mpi is item.mpi and it.start == item.start:
                it.len = item.len


class RichPool(D.TlPool):
    def CreateTimelineFromClips(self, name, infos):
        self.calls.append(("from_clips", name, infos))
        tl = FTl(self.project, name)
        t = TL_START
        for inf in infos:
            tl.add(1, inf["mediaPoolItem"], inf["startFrame"], inf["endFrame"], t)
            t += tl.items[("video", 1)][-1].len
        self.project.timelines.append(tl)
        self.project.current = tl
        return tl

    def AppendToTimeline(self, infos):
        self.calls.append(("append", infos))
        tl = self.project.timelines[-1]
        for inf in infos:
            tl.add(inf.get("trackIndex", 1), inf["mediaPoolItem"], inf["startFrame"], inf["endFrame"], inf.get("recordFrame", TL_START))
        return True


class RichProject(D.TlProject):
    current = None

    def SetCurrentTimeline(self, tl):
        self.current = tl
        return True

    def GetCurrentTimeline(self):
        return self.current


def make_rich(tmp, name="2026.10.17.LV_Ten"):
    mk = lambda uid, hh: D.Item(uid, T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:00:00" % hh, "Sat Oct 17 %02d:00:20 2026" % hh, 1000, Type="Video + Audio"))   # noqa: E731
    sel = T.FFolder("01_SELECTED", [mk("a", 8), mk("b", 9), mk("c", 10), mk("d", 11)])
    foot = T.FFolder("01_footage")
    foot.subs.append(sel)
    root = T.FFolder("Master")
    root.subs.append(foot)
    proj = RichProject(name)
    pool = RichPool(root, proj, "ok")
    proj.pool = pool
    api = ta.TrolyApi(name, tmp, resolve_factory=lambda: T.FResolve(proj), start_worker=False)
    api._worker.connect()
    api.init()
    D.run_jobs(api)
    api.load("Master/01_footage/01_SELECTED")
    D.run_jobs(api)
    api._plan["stages"] = [{"name": "Chuẩn bị", "start": 0.0, "end": 100000.0, "color": "#fff", "bins": ["Decor", "Beauty cô dâu", "Chú rể"]}]
    api._plan["offsets"] = {}
    api._tl_fps = 25.0
    api.state()
    return api, proj, pool


class TlApi(unittest.TestCase):
    def setUp(self):
        D.Item.marks_calls = []
        self.tmp = tempfile.mkdtemp()
        self.api, self.proj, self.pool = make_rich(self.tmp)
        self.uids = [c["uid"] for c in self.api.state()["clips"]]
        self.api.label(self.uids[:1], 0, "Decor")
        self.api.label(self.uids[1:2], 0, "Beauty cô dâu")
        self.api.label(self.uids[2:], 0, "Chú rể")
        self.api.toggle_star(self.uids)
        self.api.dur_set_target(30)                                  # lấy hết clip sao

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_state_co_bo_cuc_va_hien_tai_chi_tinh_v1(self):
        v = self.api.dur_state()
        self.assertIn("tl", v)
        self.assertEqual([c["stage"] for c in v["tl"]["clusters"]], ["Chuẩn bị"])
        self.assertAlmostEqual(v["tl"]["v1_end"], v["total_s"], places=1)
        v2 = self.api.dur_tl_set_track("Chuẩn bị|Decor", "V2", 4.0)
        self.assertEqual(v2["tl"]["blocks"]["Chuẩn bị|Decor"]["track"], "V2")
        self.assertLess(v2["total_s"], v["total_s"])                 # V2 không cộng vào độ dài
        self.assertGreater(v2["v2_s"], 0)

    def test_dat_toc_do_tieng_va_luu_theo_project_doc_lai_duoc(self):
        v = self.api.dur_state()
        have0 = v["tl"]["blocks"]["Chuẩn bị|Beauty cô dâu"]["have"]
        v = self.api.dur_tl_set_speed("block", "Chuẩn bị|Beauty cô dâu", 50)
        self.assertAlmostEqual(v["tl"]["blocks"]["Chuẩn bị|Beauty cô dâu"]["have"], have0 * 2, places=1)
        v = self.api.dur_tl_set_mute("stage", "Chuẩn bị", True)
        self.assertTrue(v["tl"]["blocks"]["Chuẩn bị|Decor"]["mute"])
        v = self.api.dur_tl_move_block("Chuẩn bị|Chú rể", "Chuẩn bị", 0)
        self.assertEqual(v["tl"]["clusters"][0]["kids"][0], "Chuẩn bị|Chú rể")
        self.assertTrue(v["tl_manual"])
        self.api._save_now()
        with open(tc.plan_path(self.tmp, self.api._project), encoding="utf-8") as f:
            d = json.load(f)
        tl = d["durations"]["tl"]
        self.assertEqual(tl["blk"]["Chuẩn bị"]["Beauty cô dâu"]["speed"], 50.0)
        self.assertTrue(tl["stg"]["Chuẩn bị"]["mute"])
        self.assertEqual(tl["kids"]["Chuẩn bị"][0], "Chuẩn bị|Chú rể")
        self.assertTrue(tl["manual"])
        v = self.api.dur_tl_reset()                                  # xếp lại theo giờ quay: giữ Slow, tiếng
        self.assertFalse(v["tl_manual"])
        self.assertEqual(self.api._plan["durations"]["tl"]["blk"]["Chuẩn bị"]["Beauty cô dâu"]["speed"], 50.0)
        self.assertNotIn("kids", self.api._plan["durations"]["tl"])

    def test_gia_tri_sai_bi_chan_va_khong_ghi(self):
        before = json.dumps(self.api._plan.get("durations"), sort_keys=True)
        for call in (lambda: self.api.dur_tl_set_speed("block", "Chuẩn bị|Decor", 1), lambda: self.api.dur_tl_set_speed("khac", "x", 50),
                     lambda: self.api.dur_tl_set_mute("khac", "x", True), lambda: self.api.dur_tl_move_block("khongco|bin", "Chuẩn bị", 0),
                     lambda: self.api.dur_tl_move_cluster("khongco", 0), lambda: self.api.dur_tl_set_track("Chuẩn bị|Decor", "V3", 1)):
            self.assertIn("error", call())
        self.assertEqual(json.dumps(self.api._plan.get("durations"), sort_keys=True), before)

    def test_goi_y_dua_khoi_slow_ve_100(self):
        self.api.dur_tl_set_speed("block", "Chuẩn bị|Beauty cô dâu", 50)
        self.api.dur_set_target(1.0)                                 # mục tiêu nhỏ: Hiện Tại dư/thiếu tuỳ; chỉ cần có gợi ý unslow khi Slow thật sự làm dài
        v = self.api.dur_state()
        if v["advice"]["unslow"]:
            self.assertIn("về 100%", v["advice"]["unslow"]["title"])
            v2 = self.api.dur_tl_unslow()
            self.assertEqual(v2["tl"]["blocks"]["Chuẩn bị|Beauty cô dâu"]["speed"]["mode"], "100")

    def test_tao_timeline_v1_lien_nhau_v2_dung_cho_slow_va_tat_tieng(self):
        self.api.dur_tl_set_speed("block", "Chuẩn bị|Beauty cô dâu", 50)
        self.api.dur_tl_set_mute("block", "Chuẩn bị|Beauty cô dâu", True)
        self.api.dur_tl_set_track("Chuẩn bị|Decor", "V2", 3.0)
        self.api.dur_tl_set_speed("block", "Chuẩn bị|Decor", 50)
        self.api.dur_tl_set_mute("block", "Chuẩn bị|Decor", True)
        v = self.api.dur_state()
        n_v1 = v["tl_summary"]["n_v1"]
        r = self.api.dur_create_timeline()
        self.assertTrue(r["ok"], r)
        events = []
        self.api._emit_fn = lambda k, d: events.append((k, d))
        D.run_jobs(self.api)
        tl = self.proj.timelines[-1]
        s0 = tl.GetStartFrame()
        v1 = tl.GetItemListInTrack("video", 1)
        self.assertEqual(len(v1), n_v1)
        for a, b in zip(v1, v1[1:]):
            self.assertEqual(a.GetEnd(), b.GetStart(), "V1 phải liền nhau")                   # không chồng, không hở sau khi đẩy source sau
        self.assertEqual(v1[0].GetStart(), s0)
        v2 = tl.GetItemListInTrack("video", 2)
        self.assertEqual(len(v2), 1)
        self.assertEqual(v2[0].GetStart(), s0 + round(3.0 * 25))                             # V2 đúng chỗ anh thả
        self.assertEqual(v2[0].speed, 50.0)
        self.assertFalse(tl.corrupt)                                                          # khóa V1/A1 khi Slow ở V2 nên V1 không bị cắt đôi
        self.assertEqual(tl.locked, set())                                                    # đã mở khóa lại hết
        slow = [it for it in v1 if it.speed == 50.0]
        self.assertEqual(len(slow), 1)
        self.assertEqual(slow[0].len, slow[0].base * 2)                                       # Slow 50% giữ In/Out: dài gấp đôi
        a1 = tl.GetItemListInTrack("audio", 1)
        off = [it for it in a1 if not it.enabled]
        self.assertEqual([it.name for it in off], ["DGb.MP4"])                                # chỉ tắt tiếng đúng khối Beauty (chung track A1 với khối khác)
        self.assertTrue(all(it.enabled for it in a1 if it.name != "DGb.MP4"))
        a2 = tl.GetItemListInTrack("audio", 2)
        self.assertEqual([it.enabled for it in a2], [False])                                  # khối V2 tắt tiếng nằm ở A2
        self.assertEqual([it.enabled for it in tl.GetItemListInTrack("audio", 3)], [])        # không đụng A3 trở lên
        done = [d for k, d in events if k == "dur_timeline_done"]
        self.assertTrue(done and done[0]["layout_ok"] is True and done[0]["n_slow"] == 2 and done[0]["n_muted"] == 2 and done[0]["verified"])
        self.assertEqual(D.Item.marks_calls, [])                                              # KHÔNG ghi In/Out lên clip gốc
        self.assertEqual(len(self.proj.timelines), 3)                                         # đúng MỘT timeline mới (đã có 2)

    def test_khong_slow_khong_v2_van_dung_duong_cu_khong_goi_api_phu(self):
        r = self.api.dur_create_timeline()
        self.assertTrue(r["ok"])
        D.run_jobs(self.api)
        tl = self.proj.timelines[-1]
        self.assertEqual([it.speed for it in tl.GetItemListInTrack("video", 1)], [100.0] * 4)
        self.assertEqual(tl.GetItemListInTrack("video", 2), [])
        self.assertEqual(self.pool.calls[0][0], "from_clips")
        self.assertEqual(len(self.pool.calls), 1)                                             # không AppendToTimeline

    def test_nhat_ky_ghi_slow_track_tieng(self):
        self.api.dur_tl_set_speed("block", "Chuẩn bị|Decor", "auto")
        self.api.dur_tl_set_mute("block", "Chuẩn bị|Decor", True)
        self.assertTrue(self.api.dur_create_timeline()["ok"])
        import glob
        with open(glob.glob(os.path.join(self.tmp, "troly", "timeline_log", "*.json"))[0], encoding="utf-8") as f:
            rec = json.load(f)
        self.assertEqual(rec["tl_fps"], 25.0)
        self.assertEqual(rec["summary"]["muted"], ["Decor"])
        row = next(x for x in rec["items"] if x["bin"] == "Decor")
        self.assertEqual((row["track"], row["pct"], row["mute"]), ("V1", 50.0, True))        # 50p -> timeline 25p = 50%

    def test_doi_ten_giai_doan_doi_theo_cau_hinh_timeline(self):
        self.api.dur_tl_set_speed("block", "Chuẩn bị|Decor", 50)
        self.api.dur_tl_move_block("Chuẩn bị|Chú rể", "Chuẩn bị", 0)
        self.api.rename("stage", 0, "Chuẩn bị", "Nhà gái")
        tl = self.api._plan["durations"]["tl"]
        self.assertIn("Nhà gái", tl["blk"])
        self.assertIn("Nhà gái|Chú rể", tl["kids"]["Nhà gái"])
        self.api.rename("bin", 0, "Decor", "Chi tiết")
        self.assertIn("Chi tiết", self.api._plan["durations"]["tl"]["blk"]["Nhà gái"])
        v = self.api.dur_state()
        self.assertEqual(v["tl"]["blocks"]["Nhà gái|Chi tiết"]["speed"]["pct"], 50.0)


class MoPhongDungDo(unittest.TestCase):
    """Giữ cho bản giả bám đúng số đo thật (ADR-0013): ripple ở V2 không khóa V1 thì làm hỏng V1; khóa V1/A1 thì an toàn; ripple False không đổi độ dài."""

    def build(self):
        proj = RichProject("2026.10.17.LV_Ten")
        tl = FTl(proj, "t")
        proj.current = tl
        mk = lambda n: D.Item(n, T.props("DG%s.MP4" % n, "Sat Oct 17 2026 08:00:00", "Sat Oct 17 08:00:20 2026", 1000, Type="Video + Audio"))   # noqa: E731
        for i, n in enumerate("abc"):
            tl.add(1, mk(n), 0, 100, TL_START + i * 50)
        tl.add(2, mk("e"), 0, 100, TL_START + 60)
        return tl

    def test_ripple_v2_khong_khoa_lam_hong_v1(self):
        tl = self.build()
        tl.GetItemListInTrack("video", 2)[0].SetSpeed({"Percentage": 50.0, "RippleTimeline": True})
        self.assertTrue(tl.corrupt)

    def test_ripple_v2_khoa_v1_a1_an_toan(self):
        tl = self.build()
        tl.SetTrackLock("video", 1, True)
        tl.SetTrackLock("audio", 1, True)
        tl.GetItemListInTrack("video", 2)[0].SetSpeed({"Percentage": 50.0, "RippleTimeline": True})
        self.assertFalse(tl.corrupt)
        self.assertEqual(tl.GetItemListInTrack("video", 2)[0].len, 100)

    def test_ripple_false_giu_nguyen_do_dai_nen_khong_dung_duoc(self):
        tl = self.build()
        it = tl.GetItemListInTrack("video", 1)[1]
        it.SetSpeed({"Percentage": 50.0, "RippleTimeline": False})
        self.assertEqual(it.len, 50)

    def test_ripple_true_v1_day_clip_sau(self):
        tl = self.build()
        it = tl.GetItemListInTrack("video", 1)[1]
        it.SetSpeed({"Percentage": 50.0, "RippleTimeline": True})
        v1 = tl.GetItemListInTrack("video", 1)
        self.assertEqual([x.start - TL_START for x in v1], [0, 50, 150])
        self.assertEqual(v1[1].len, 100)

    def test_set_clip_enabled_chi_tren_timeline_hien_tai(self):
        tl = self.build()
        tl.project.current = None
        self.assertFalse(tl.GetItemListInTrack("audio", 1)[0].SetClipEnabled(False))


class WorkerSafe(unittest.TestCase):
    def test_worker_khong_dung_a3_tro_len_khong_xoa_khong_render(self):
        with open(os.path.join(HERE, "..", "app", "troly_resolve.py"), encoding="utf-8") as f:
            src = f.read()
        seg = src[src.index("def do_create_cut_timeline"):src.index("def _timeline_names")]
        for bad in ("SetTrackEnable", "DeleteTimelines", "DeleteClips", "StartRendering", "SetMarkInOut", '"audio", 3', '("audio", 3)'):
            self.assertNotIn(bad, seg, bad)
        self.assertIn("SetTrackLock(kind, t, False)", seg)                                    # luôn mở khóa lại (finally)
        self.assertIn("finally:", seg)


if __name__ == "__main__":
    unittest.main()
