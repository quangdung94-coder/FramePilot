"""Bước 5: API Thời lượng + tạo timeline MỚI trong DaVinci (giả lập): chỉ tạo mới, clip con theo In/Out, không SetMarkInOut, nhật ký trước khi tạo,
kiểm lại số timeline, lưu Min-Max vào kế hoạch chỉ khi anh sửa. Tên ví dụ LV_Ten."""
import glob
import json
import os
import queue
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import test_troly as T                # noqa: E402
import troly_api as ta                # noqa: E402
import troly_core as tc               # noqa: E402
import troly_resolve as tr            # noqa: E402


class Item(T.FItem):
    """Clip giả: nếu bị gọi SetMarkInOut/ClearMarkInOut thì ghi lại (Bước 5 KHÔNG được gọi)."""
    marks_calls = []

    def SetMarkInOut(self, *a):
        Item.marks_calls.append(("set", self.uid) + a)
        return True

    def ClearMarkInOut(self, *a):
        Item.marks_calls.append(("clear", self.uid))
        return True


class Timeline(object):
    def __init__(self, name):
        self.name = name

    def GetName(self):
        return self.name


class TlPool(T.FPool):
    """Media Pool giả có tạo timeline; chế độ: 'ok', 'empty_first' (CreateTimelineFromClips trả None), 'fail_all'."""

    def __init__(self, root, project, mode="ok"):
        super().__init__(root)
        self.project, self.mode, self.calls = project, mode, []

    def CreateTimelineFromClips(self, name, infos):
        self.calls.append(("from_clips", name, infos))
        if self.mode != "ok":
            return None
        tl = Timeline(name)
        self.project.timelines.append(tl)
        return tl

    def CreateEmptyTimeline(self, name):
        self.calls.append(("empty", name))
        if self.mode == "fail_all":
            return None
        tl = Timeline(name)
        self.project.timelines.append(tl)
        return tl

    def AppendToTimeline(self, infos):
        self.calls.append(("append", infos))
        return self.mode != "fail_append"


class TlProject(T.FProject):
    def __init__(self, name, pool=None):
        super().__init__(name, pool)
        self.timelines = [Timeline("full"), Timeline("intro")]

    def GetTimelineCount(self):
        return len(self.timelines)

    def GetTimelineByIndex(self, i):
        return self.timelines[i - 1]


def make_api(tmp, mode="ok", name="2026.10.17.LV_Ten"):
    mk = lambda uid, hh: Item(uid, T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:00:00" % hh,          # noqa: E731
                                           "Sat Oct 17 %02d:00:20 2026" % hh, 1000, Type="Video + Audio"))
    sel = T.FFolder("01_SELECTED", [mk("a", 8), mk("b", 9), mk("c", 10)])
    foot = T.FFolder("01_footage")
    foot.subs.append(sel)
    root = T.FFolder("Master")
    root.subs.append(foot)
    proj = TlProject(name)
    pool = TlPool(root, proj, mode)
    proj.pool = pool
    api = ta.TrolyApi(name, tmp, resolve_factory=lambda: T.FResolve(proj), start_worker=False)
    api._worker.connect()
    api.init()
    run_jobs(api)
    api.load("Master/01_footage/01_SELECTED")
    run_jobs(api)
    api._plan["stages"] = [{"name": "Chuẩn bị", "start": 0.0, "end": 100000.0, "color": "#fff", "bins": ["Decor", "Nghi lễ", "Khác"]}]
    api._plan["offsets"] = {}
    api.state()
    return api, proj, pool


def run_jobs(api):
    w = api._worker
    while not w.jobs.empty():
        j, a = w.jobs.get()
        try:
            getattr(w, "do_" + j)(a)
        except Exception as e:                       # noqa: BLE001
            w.post("error", (j, str(e)))
    api._drain()


class DurApi(unittest.TestCase):
    def setUp(self):
        Item.marks_calls = []
        self.tmp = tempfile.mkdtemp()
        self.api, self.proj, self.pool = make_api(self.tmp)
        self.uids = [c["uid"] for c in self.api.state()["clips"]]

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def star_all(self):
        self.api.label(self.uids[:2], 0, "Decor")
        self.api.label(self.uids[2:], 0, "Nghi lễ")
        self.api.toggle_star(self.uids)

    def test_xem_thoi_luong_khong_ghi_khoa_vao_ke_hoach(self):
        self.star_all()
        v = self.api.dur_state()
        self.assertTrue(v["proposed"])
        self.assertEqual(v["target_min"], 12.0)
        self.assertNotIn("durations", self.api._plan)
        self.api.dur_cut()
        self.assertNotIn("durations", self.api._plan)

    def test_sua_muc_tieu_tile_va_min_max_luu_trong_ke_hoach_co_bak(self):
        self.star_all()
        self.assertEqual(self.api.dur_set_target(11)["target_min"], 11.0)
        v = self.api.dur_set_bin(0, "Decor", 5, 12)
        b = next(x for x in v["stages"][0]["bins"] if x["name"] == "Decor")
        self.assertEqual((b["min"], b["max"], b["edited"]), (5.0, 12.0, True))
        self.api._save_now()
        p = tc.plan_path(self.tmp, self.api._project)
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual(d["durations"]["target_min"], 11.0)
        self.assertEqual(d["durations"]["bins"]["Chuẩn bị"]["Decor"], [5.0, 12.0])
        self.api._save_now()
        self.assertTrue(os.path.isfile(p + ".bak"))                                   # có bản .bak như các phần khác

    def test_nhap_sai_bi_chan_va_khong_ghi(self):
        self.star_all()
        for bad in ("abc", 0, 999):
            self.assertIn("error", self.api.dur_set_target(bad))
        for args in ((0, "Decor", 20, 10), (0, "Decor", -1, 5), (0, "Decor", "x", 5), (7, "Decor", 1, 2)):
            self.assertIn("error", self.api.dur_set_bin(*args), args)
        self.assertNotIn("durations", self.api._plan)
        self.assertIn("error", self.api.dur_set_share(9, 0.5))

    def test_keo_ti_le_tong_luon_bang_1(self):
        plan = self.api._plan
        plan["stages"].append({"name": "Sau", "start": 0.0, "end": 100000.0, "color": "#eee", "bins": ["Khác"]})
        self.star_all()
        v = self.api.dur_set_share(0, 0.7)
        self.assertAlmostEqual(sum(s["share"] for s in v["stages"]), 1.0, places=2)
        self.assertAlmostEqual(v["stages"][0]["share"], 0.7, places=2)

    def test_dat_lai_ve_de_xuat(self):
        self.star_all()
        self.api.dur_set_target(14)
        v = self.api.dur_reset()
        self.assertNotIn("durations", self.api._plan)
        self.assertEqual(v["target_min"], 12.0)

    def test_doi_ten_giai_doan_va_bin_giu_min_max(self):
        self.star_all()
        self.api.dur_set_bin(0, "Decor", 5, 12)
        self.api.dur_set_share(0, 1.0)
        self.api.rename("bin", 0, "Decor", "Chi tiết")
        self.assertEqual(self.api._plan["durations"]["bins"]["Chuẩn bị"]["Chi tiết"], [5.0, 12.0])
        self.assertNotIn("Decor", self.api._plan["durations"]["bins"]["Chuẩn bị"])
        self.api.rename("stage", 0, "Chuẩn bị", "Nhà gái")
        self.assertIn("Nhà gái", self.api._plan["durations"]["bins"])
        self.assertIn("Nhà gái", self.api._plan["durations"]["stage_share"])
        self.assertNotIn("Chuẩn bị", self.api._plan["durations"]["stage_share"])

    # ------------------------------------------------------------------ tạo timeline
    def test_chua_cat_got_thi_khong_cho_tao_timeline(self):
        self.star_all()
        r = self.api.dur_create_timeline()
        self.assertIn("error", r)
        self.assertEqual(self.pool.calls, [])

    def test_doi_so_lieu_sau_khi_cat_got_bat_cat_got_lai(self):
        self.star_all()
        self.api.dur_cut()
        self.api.dur_set_bin(0, "Decor", 1, 3)                                         # đổi Max sau khi đã cắt gọt
        self.assertIn("error", self.api.dur_create_timeline())
        self.assertEqual(self.pool.calls, [])

    def test_khong_co_sao_thi_bao_loi(self):
        self.api.dur_cut()
        self.assertIn("error", self.api.dur_create_timeline())

    def test_tao_timeline_moi_dung_in_out_clip_con_ghi_nhat_ky_va_kiem_lai(self):
        self.star_all()
        cut = self.api.dur_cut()
        self.assertTrue(cut["cut_ready"])
        r = self.api.dur_create_timeline()
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], len(cut["items"]))
        logs = glob.glob(os.path.join(self.tmp, "troly", "timeline_log", "*.json"))       # nhật ký ghi TRƯỚC khi tạo
        self.assertEqual(len(logs), 1)
        with open(logs[0], encoding="utf-8") as f:
            rec = json.load(f)
        self.assertEqual((rec["count"], rec["total_s"]), (r["count"], r["total_s"]))
        self.assertEqual(self.pool.calls, [])                                           # job mới được xếp hàng, chưa chạy
        events = []
        self.api._emit_fn = lambda k, d: events.append((k, d))
        run_jobs(self.api)
        self.assertEqual(self.pool.calls[0][0], "from_clips")
        infos = self.pool.calls[0][2]
        self.assertEqual(len(infos), r["count"])
        for inf in infos:
            self.assertEqual(set(inf), {"mediaPoolItem", "startFrame", "endFrame"})
            self.assertGreater(inf["endFrame"], inf["startFrame"])
            self.assertLessEqual(inf["endFrame"], 999)
        self.assertEqual(Item.marks_calls, [])                                          # KHÔNG ghi In/Out lên clip gốc
        self.assertEqual([t.name for t in self.proj.timelines][:2], ["full", "intro"])  # timeline cũ còn nguyên
        self.assertEqual(len(self.proj.timelines), 3)
        done = [d for k, d in events if k == "dur_timeline_done"]
        self.assertTrue(done and done[0]["verified"] and (done[0]["before"], done[0]["after"]) == (2, 3))
        self.assertFalse(self.api._busy)
        self.assertEqual(self.api._dur_cut, None)                                        # phải cắt gọt lại mới tạo tiếp

    def test_ten_timeline_khong_chua_ky_tu_cam_ke_ca_khi_project_co_and(self):
        api, proj, pool = make_api(tempfile.mkdtemp(), name="2026.10.25.LV_X&Y")
        try:
            uids = [c["uid"] for c in api.state()["clips"]]
            api.label(uids, 0, "Decor")
            api.toggle_star(uids)
            api.dur_cut()
            r = api.dur_create_timeline()
            for ch in ':&/\\*?"<>|':
                self.assertNotIn(ch, r["name"])
            self.assertIn("LV_X Y", r["name"])
            run_jobs(api)
            self.assertEqual(proj.timelines[-1].name, r["name"])
        finally:
            api._thumbs.shutdown()

    def test_du_phong_tao_rong_roi_append_va_loi_ca_hai_cach(self):
        for mode, expect_error in (("empty_first", False), ("fail_all", True)):
            tmp = tempfile.mkdtemp()
            api, proj, pool = make_api(tmp, mode)
            try:
                uids = [c["uid"] for c in api.state()["clips"]]
                api.label(uids, 0, "Decor")
                api.toggle_star(uids)
                api.dur_cut()
                self.assertTrue(api.dur_create_timeline()["ok"])
                events = []
                api._emit_fn = lambda k, d, ev=events: ev.append((k, d))
                run_jobs(api)
                kinds = [c[0] for c in pool.calls]
                if expect_error:
                    self.assertEqual(kinds, ["from_clips", "empty"])
                    self.assertTrue(any(k == "status" and d["kind"] == "error" for k, d in events))
                    self.assertEqual(len(proj.timelines), 2)                                 # không tạo gì
                else:
                    self.assertEqual(kinds, ["from_clips", "empty", "append"])
                    self.assertEqual(len(proj.timelines), 3)
                self.assertFalse(api._busy)                                                  # lỗi cũng nhả cờ bận
            finally:
                api._thumbs.shutdown()
                shutil.rmtree(tmp, ignore_errors=True)

    def test_ghi_dang_khac_project_bi_tu_choi(self):
        self.star_all()
        self.api.dur_cut()
        self.assertTrue(self.api.dur_create_timeline()["ok"])
        self.api._worker.pm.project = TlProject("Project khác", self.pool)
        events = []
        self.api._emit_fn = lambda k, d: events.append((k, d))
        run_jobs(self.api)
        self.assertEqual(self.pool.calls, [])
        self.assertTrue(any(k == "status" and "project khác" in d["text"] for k, d in events))

    def test_dang_ban_thi_khong_tao_va_nhat_ky_loi_thi_chua_cham_davinci(self):
        self.star_all()
        self.api.dur_cut()
        self.api._busy = True
        self.assertIn("error", self.api.dur_create_timeline())
        self.api._busy = False
        orig = tc.write_timeline_log
        tc.write_timeline_log = lambda *a, **k: (_ for _ in ()).throw(OSError("đĩa đầy"))
        try:
            r = self.api.dur_create_timeline()
        finally:
            tc.write_timeline_log = orig
        self.assertIn("error", r)
        self.assertTrue(self.api._worker.jobs.empty())
        self.assertEqual(self.pool.calls, [])


class Pure(unittest.TestCase):
    def test_cut_frames_tu_dau_file_va_ke_kep(self):
        self.assertEqual(tc.cut_frames(1.0, 4.0, 50.0, 1000), (50, 199))
        self.assertEqual(tc.cut_frames(18.0, 40.0, 50.0, 1000), (900, 999))         # vượt độ dài thì kẹp
        a, b = tc.cut_frames(5.0, 5.0, 50.0, 1000)
        self.assertGreater(b, a)

    def test_worker_chi_goi_cac_ham_tao_moi_khong_xoa_khong_render_khong_in_out(self):
        with open(os.path.join(HERE, "..", "app", "troly_resolve.py"), encoding="utf-8") as f:
            src = f.read()
        seg = src[src.index("def do_create_cut_timeline"):src.index("# --- GHI In/Out")]
        for bad in ("SetMarkInOut", "ClearMarkInOut", "DeleteTimelines", "DeleteClips", "StartRendering", "AddRenderJob", "SetCurrentTimeline",
                    "LoadProject", "SaveProject"):
            self.assertNotIn(bad, seg, bad)
        self.assertIn("_require_current()", seg)


if __name__ == "__main__":
    unittest.main()
