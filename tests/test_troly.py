"""Kiểm thử Trợ lý File Quay: troly_core.py (giờ quay, chia giai đoạn, nhãn) và troly_thumbs.py (proxy, LUT, cache).
Không cần DaVinci. Phần thumbnail cần ffmpeg trên PATH (không có thì bỏ qua)."""
import datetime
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import troly_core as tc    # noqa: E402
import troly_thumbs as tt  # noqa: E402

DT = datetime.datetime


def props(name, created, modified, frames, fps=50.0, **kw):
    d = {"File Name": name, "File Path": r"J:\01_Project video\2026.10.17.LV_Mau\01_footage\%s" % name,
         "Date Created": created, "Date Modified": modified, "Frames": str(frames), "FPS": fps,
         "Resolution": "3840x2160", "Input LUT": "", "Proxy Media Path": ""}
    d.update(kw)
    return d


def clip_at(uid, hh, mm, ss=0, dur_s=6, day=17, cam="DG 3840x2160"):
    return tc.Clip(uid=uid, name="DG%s.MP4" % uid, path="", proxy="", lut="", dur=dur_s, fps=50.0,
                   frames=int(dur_s * 50), t_start=DT(2026, 10, day, hh, mm, ss), t_src="created", camera=cam,
                   bin_path="", clip_color="", rel="01_footage/DG%s.MP4" % uid)


class ShootTime(unittest.TestCase):
    def test_parse_both_resolve_formats(self):
        self.assertEqual(tc.parse_resolve_date("Sat Oct 17 2026 06:25:28"), DT(2026, 10, 17, 6, 25, 28))
        self.assertEqual(tc.parse_resolve_date("Sat Oct 17 06:25:33 2026"), DT(2026, 10, 17, 6, 25, 33))
        self.assertEqual(tc.parse_resolve_date("Thu Nov 5 2026 11:52:05"), DT(2026, 11, 5, 11, 52, 5))
        self.assertEqual(tc.parse_resolve_date("2026-10-17T06:25:28.000000Z"), DT(2026, 10, 17, 6, 25, 28))
        self.assertIsNone(tc.parse_resolve_date(""))
        self.assertIsNone(tc.parse_resolve_date("rác"))

    def test_created_trusted_when_matches_modified(self):
        # số đo thật DG4939: tạo 06:25:28, sửa 06:25:33, 216 frame / 50 fps = 4,32 s
        p = props("DG4939.MP4", "Sat Oct 17 2026 06:25:28", "Sat Oct 17 06:25:33 2026", 216)
        t, src = tc.shoot_time(p)
        self.assertEqual((t, src), (DT(2026, 10, 17, 6, 25, 28), "created"))

    def test_copied_file_falls_back_to_modified(self):
        # chép file sang ổ khác hôm sau: giờ tạo đổi, giờ sửa giữ nguyên
        p = props("DG1.MP4", "Sun Oct 18 2026 10:00:00", "Sat Oct 17 06:25:33 2026", 250)
        t, src = tc.shoot_time(p)
        self.assertEqual(src, "modified")
        self.assertEqual(t, DT(2026, 10, 17, 6, 25, 28))

    def test_no_dates(self):
        self.assertEqual(tc.shoot_time(props("x.mp4", "", "", 10)), (None, "none"))

    def test_camera_key_and_rel_path(self):
        self.assertEqual(tc.camera_key(props("DG4939.MP4", "", "", 1)), "DG 3840x2160")
        self.assertEqual(tc.camera_key(props("C0001.MP4", "", "", 1, **{"Camera Serial #": "123"})), "123")
        self.assertEqual(tc.camera_key(props("DJI_0123.MP4", "", "", 1)), "DJI 3840x2160")
        self.assertEqual(tc.rel_path(r"J:\01_Project video\2026.10.17.LV_Mau\01_footage\DG1.MP4"),
                         "01_footage/DG1.MP4")

    def test_clip_from_props(self):
        p = props("DG4939.MP4", "Sat Oct 17 2026 06:25:28", "Sat Oct 17 06:25:33 2026", 216,
                  **{"Input LUT": "Sony\\X", "Proxy Media Path": r"F:\p\DG4939.mov"})
        c = tc.Clip.from_props("u1", p, "Master/01_SELECTED")
        self.assertAlmostEqual(c.dur, 4.32)
        self.assertEqual((c.lut, c.proxy, c.rel), ("Sony\\X", r"F:\p\DG4939.mov", "01_footage/DG4939.MP4"))

    def test_hhmm(self):
        self.assertEqual(tc.fmt_min(6 * 60 + 25.4), "06:25")
        self.assertEqual(tc.fmt_min(1440 + 61), "01:01 (+1)")
        self.assertEqual(tc.parse_hhmm("7:30"), 450)
        self.assertEqual(tc.parse_hhmm("0730"), 450)
        self.assertEqual(tc.parse_hhmm("01:01 (+1)", 1), 1501)
        with self.assertRaises(ValueError):
            tc.parse_hhmm("25:00")


class Stages(unittest.TestCase):
    def setUp(self):
        # sáng 06:25-09:27 (nghỉ 14 phút lúc 07:43), tối 16:57-21:38 (nghỉ 45 phút lúc 20:20)
        self.clips = [clip_at("a", 6, 25), clip_at("b", 7, 0), clip_at("c", 7, 43), clip_at("d", 7, 57),
                      clip_at("e", 9, 27), clip_at("f", 16, 57), clip_at("g", 19, 0), clip_at("h", 20, 20),
                      clip_at("i", 21, 5), clip_at("j", 21, 38)]
        self.day0 = tc.day0_of(self.clips)

    def test_gaps_and_suggest_uses_longest_gaps(self):
        g = sorted(tc.gaps(self.clips, self.day0), key=lambda x: -x[0])
        self.assertAlmostEqual(g[0][0], 16 * 60 + 57 - (9 * 60 + 27 + 0.1), places=3)
        tpl = [("Sáng", ["Decor"]), ("Tối", ["Khách"])]
        st = tc.suggest_stages(self.clips, self.day0, tpl)
        self.assertEqual([s["name"] for s in st], ["Sáng", "Tối"])
        self.assertLess(st[0]["end"], 16 * 60 + 57)
        self.assertGreater(st[1]["start"], 9 * 60 + 27)
        a = tc.assign(self.clips, st, self.day0)
        self.assertEqual(tc.counts(a, 2), ([5, 5], 0))
        self.assertEqual(st[0]["bins"], ["Decor", "Khác"])

    def test_suggest_more_stages_than_gaps(self):
        few = self.clips[:2]
        st = tc.suggest_stages(few, self.day0, [("A", []), ("B", []), ("C", []), ("D", [])], min_gap=100)
        self.assertEqual(len(st), 4)
        self.assertEqual(st[1]["start"], st[1]["end"])          # giai đoạn trống, người dựng tự kéo

    def test_outside_and_offsets(self):
        st = [tc.make_stage("Gia tiên", 7 * 60, 8 * 60, [], 0)]
        a = tc.assign(self.clips, st, self.day0)
        self.assertEqual([k for k, v in a.items() if v == 0], ["b", "c", "d"])
        # máy B chạy chậm 10 phút: cộng 600 giây thì clip 06:55 rơi vào 07:05
        late = clip_at("x", 6, 55, cam="B")
        a = tc.assign([late], st, self.day0, offsets={"B": 600})
        self.assertEqual(a["x"], 0)

    def test_multi_day_minutes(self):
        c2 = clip_at("z", 8, 0, day=18)
        self.assertAlmostEqual(tc.clip_minutes(c2, self.day0)[0], 1440 + 480)

    def test_target_folder_and_keymap(self):
        st = [tc.make_stage("Rước dâu", 0, 10, ["Decor", "Gia đình"], 0),
              tc.make_stage("Gia tiên", 10, 20, ["Decor"], 1)]
        self.assertEqual(tc.target_folder(None, None, st), [])
        self.assertEqual(tc.target_folder(1, None, st), ["02_Gia tiên"])
        self.assertEqual(tc.target_folder(0, {"stage": "Rước dâu", "bin": "Decor"}, st), ["01_Rước dâu", "Decor"])
        # nhãn của giai đoạn khác (người dựng đã kéo lại giờ): không kéo clip vào bin con sai
        self.assertEqual(tc.target_folder(1, {"stage": "Rước dâu", "bin": "Decor"}, st), ["02_Gia tiên"])
        self.assertEqual(tc.keymap(st[0]), {"1": "Decor", "2": "Gia đình", "3": "Khác"})
        # chọn tay thắng giai đoạn theo giờ: clip theo giờ ở 01 nhưng người dựng chuyển sang Gia tiên > Decor
        man = {"stage": "Gia tiên"}
        self.assertEqual(tc.target_folder(0, {"stage": "Gia tiên", "bin": "Decor"}, st, man), ["02_Gia tiên", "Decor"])
        self.assertEqual(tc.target_folder(None, None, st, man), ["02_Gia tiên"])
        self.assertEqual(tc.target_folder(0, None, st, {"stage": "Đã xóa"}), ["01_Rước dâu"])

    def test_manual_stage_wins_and_survives_redrag(self):
        st = [tc.make_stage("Sáng", 6 * 60, 10 * 60, [], 0), tc.make_stage("Tối", 16 * 60, 22 * 60, [], 1)]
        plan = tc.new_plan("P")
        a_clip = self.clips[0]                                   # 06:25 -> theo giờ là Sáng
        tc.set_manual(plan, a_clip, "Tối")
        a = tc.assign(self.clips, st, self.day0, manual=plan["manual"])
        self.assertEqual((a["a"], a["b"]), (1, 0))
        st[0]["end"] = 6 * 60 + 30                               # kéo lại mốc giờ: chọn tay vẫn giữ
        st[1]["start"] = 20 * 60
        a = tc.assign(self.clips, st, self.day0, manual=plan["manual"])
        self.assertEqual((a["a"], a["b"], a["f"]), (1, None, None))
        self.assertEqual(tc.manual_of(plan, a_clip)["stage"], "Tối")
        del st[1]                                                # giai đoạn chọn tay bị xóa: quay về theo giờ
        self.assertEqual(tc.assign(self.clips, st, self.day0, manual=plan["manual"])["a"], 0)
        tc.set_manual(plan, a_clip, None)
        self.assertIsNone(tc.manual_of(plan, a_clip))


class PlanStore(unittest.TestCase):
    def test_plan_labels_templates_roundtrip(self):
        tmp = tempfile.mkdtemp()
        try:
            p = tc.load_plan(tmp, "2026.10.17.LV_Mau")
            self.assertEqual(p["stages"], [])
            c = clip_at("a", 6, 25)
            tc.set_label(p, c, "Rước dâu", "Decor")
            p["stages"] = [tc.make_stage("Rước dâu", 0, 10, ["Decor"], 0)]
            tc.save_plan(tmp, p)
            q = tc.load_plan(tmp, "2026.10.17.LV_Mau")
            self.assertEqual(tc.label_of(q, c)["bin"], "Decor")
            self.assertEqual(q["labels"]["01_footage/DGa.MP4"]["by"], "nguoi")
            tc.set_label(q, c, None, None)
            self.assertIsNone(tc.label_of(q, c))
            tc.save_template(tmp, "Mẫu của anh", q["stages"])
            t = tc.templates(tmp)
            self.assertIn(tc.DEFAULT_TEMPLATE, t)
            self.assertEqual(t["Mẫu của anh"], [("Rước dâu", ["Decor"])])
        finally:
            shutil.rmtree(tmp)


FFMPEG = shutil.which("ffmpeg")


@unittest.skipUnless(FFMPEG, "cần ffmpeg")
class Thumbs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.src = os.path.join(cls.tmp, "goc.mp4")
        cls.proxy = os.path.join(cls.tmp, "proxy dir", "px.mov")
        os.makedirs(os.path.dirname(cls.proxy))
        for out, color in ((cls.src, "red"), (cls.proxy, "blue")):
            subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=%s:s=640x360:d=2" % color,
                            "-pix_fmt", "yuv420p", out], check=True)
        # LUT 3D đảo màu, đặt trong thư mục có khoảng trắng và dấu như thư mục LUT thật của DaVinci
        cls.lut_root = os.path.join(cls.tmp, "LUT dir", "Sony")
        os.makedirs(cls.lut_root)
        n = 2
        lines = ["LUT_3D_SIZE %d" % n]
        for b in range(n):
            for g in range(n):
                for r in range(n):
                    lines.append("%d %d %d" % (1 - r, 1 - g, 1 - b))
        with open(os.path.join(cls.lut_root, "Đảo màu.cube"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def mean_rgb(self, path):
        from PIL import Image
        im = Image.open(path).convert("RGB").resize((8, 8))
        px = list(im.getdata())
        return tuple(sum(p[i] for p in px) / len(px) for i in range(3))

    def test_find_lut(self):
        dirs = [os.path.dirname(self.lut_root)]
        self.assertTrue(tt.find_lut("Sony\\Đảo màu", dirs).endswith("Đảo màu.cube"))
        self.assertTrue(tt.find_lut("Sony/Đảo màu.cube", dirs))
        self.assertIsNone(tt.find_lut("Sony\\Không có", dirs))
        self.assertIsNone(tt.find_lut("", dirs))

    def test_proxy_preferred_and_lut_applied_and_cached(self):
        cache = os.path.join(self.tmp, "cache 1")
        tm = tt.ThumbMaker(cache, ffmpeg=FFMPEG, workers=2, lut_dirs_extra=[os.path.dirname(self.lut_root)])
        try:
            uid, out, note = tm.make("u", self.src, self.proxy, "", 2.0)
            self.assertEqual(note, "proxy")
            r, g, b = self.mean_rgb(out)
            self.assertGreater(b, r + 100)                     # proxy màu xanh, không phải file gốc màu đỏ
            uid, out2, note = tm.make("u", self.src, self.proxy, "Sony\\Đảo màu", 2.0)
            self.assertEqual(note, "proxy + LUT")
            self.assertNotEqual(out, out2)                     # đổi LUT -> thumbnail mới
            r, g, b = self.mean_rgb(out2)
            self.assertGreater(r, b + 100)                     # xanh dương đảo màu thành vàng (đỏ + lục cao)
            mtime = os.path.getmtime(out2)
            _, out3, _ = tm.submit("u", self.src, self.proxy, "Sony\\Đảo màu", 2.0).result()
            self.assertEqual((out3, os.path.getmtime(out3)), (out2, mtime))   # lần hai lấy từ cache
        finally:
            tm.shutdown()

    def test_fallback_to_original_and_missing(self):
        cache = os.path.join(self.tmp, "cache 2")
        tm = tt.ThumbMaker(cache, ffmpeg=FFMPEG, workers=1)
        try:
            _, out, note = tm.make("u", self.src, os.path.join(self.tmp, "mat.mov"), "Sony\\Không có", 2.0)
            self.assertEqual(note, "goc (không thấy file LUT)")
            r, g, b = self.mean_rgb(out)
            self.assertGreater(r, b + 100)
            _, out, note = tm.make("u", "", "", "", 1.0)
            self.assertIsNone(out)
        finally:
            tm.shutdown()


# ---------------------------------------------------------------------------
# Media pool giả để kiểm troly_resolve.py (không cần DaVinci)
# ---------------------------------------------------------------------------
class FItem(object):
    def __init__(self, uid, props, marks=None):
        self.uid, self.props = uid, props
        self.marks = marks or {}

    def GetUniqueId(self):
        return self.uid

    def GetClipProperty(self, key=None):
        return self.props if key is None else self.props.get(key)

    def GetMarkInOut(self):
        return self.marks


class FFolder(object):
    def __init__(self, name, clips=None):
        self.name, self.clips, self.subs = name, list(clips or []), []

    def GetName(self):
        return self.name

    def GetClipList(self):
        return list(self.clips)

    def GetSubFolderList(self):
        return list(self.subs)


class FPool(object):
    def __init__(self, root):
        self.root, self.current, self.selected = root, root, None
        self.fail_move = False

    def GetRootFolder(self):
        return self.root

    def GetCurrentFolder(self):
        return self.current

    def SetCurrentFolder(self, f):
        self.current = f
        return True

    def SetSelectedClip(self, c):
        self.selected = c
        return True

    def AddSubFolder(self, parent, name):
        f = FFolder(name)
        parent.subs.append(f)
        return f

    def _all(self, f):
        yield f
        for s in f.subs:
            yield from self._all(s)

    def MoveClips(self, items, dst):
        if self.fail_move:
            return False
        for f in self._all(self.root):
            f.clips = [c for c in f.clips if c not in items]
        dst.clips.extend(items)
        return True


class FProject(object):
    def __init__(self, name, pool):
        self.name, self.pool = name, pool

    def GetName(self):
        return self.name

    def GetMediaPool(self):
        return self.pool


class FResolve(object):
    def __init__(self, project):
        self.project = project

    def GetProjectManager(self):
        return self

    def GetCurrentProject(self):
        return self.project


class Worker(unittest.TestCase):
    def setUp(self):
        import queue
        import troly_resolve as tr
        self.tr = tr
        mk = lambda uid, hh: FItem(uid, props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:00:00" % hh,     # noqa: E731
                                              "Sat Oct 17 %02d:00:05 2026" % hh, 250, Type="Video + Audio"))
        self.sel = FFolder("01_SELECTED", [mk("a", 6), mk("b", 7), mk("c", 18),
                                           FItem("t", {"Type": "Timeline", "File Name": "full"})])
        foot = FFolder("01_footage")
        foot.subs.append(self.sel)
        self.root = FFolder("Master")
        self.root.subs.append(foot)
        self.pool = FPool(self.root)
        self.q = queue.Queue()
        self.w = tr.TrolyWorker("P", self.q, resolve_factory=lambda: FResolve(FProject("P", self.pool)))
        self.w.connect()

    def drain(self, kind):
        while True:
            k, d = self.q.get_nowait()
            if k == kind:
                return d

    def test_load_apply_undo(self):
        path = "Master/01_footage/01_SELECTED"
        self.w.do_bins(None)
        bins, cur = self.drain("bins")
        self.assertEqual([(b["path"], b["n"]) for b in bins][-1], (path, 3))
        self.w.do_load(path)
        bp, clips = self.drain("clips")
        self.assertEqual(sorted(c.uid for c in clips), ["a", "b", "c"])            # bỏ timeline
        self.w.do_apply((path, {"a": ["01_Sáng", "Decor"], "b": ["01_Sáng"], "c": []}))
        log, failed = self.drain("applied")
        self.assertEqual(failed, 0)
        self.assertEqual(sorted(log), [("a", path, path + "/01_Sáng/Decor"), ("b", path, path + "/01_Sáng")])
        sang = self.tr.find_folder(self.root, path + "/01_Sáng")
        self.assertEqual([c.uid for c in sang.clips], ["b"])
        self.assertEqual([c.uid for c in self.tr.find_folder(self.root, path + "/01_Sáng/Decor").clips], ["a"])
        self.assertEqual(sorted(c.uid for c in self.sel.clips), ["c", "t"])
        # áp dụng lại y hệt: không chuyển gì nữa, không tạo bin trùng
        self.w.do_apply((path, {"a": ["01_Sáng", "Decor"], "b": ["01_Sáng"]}))
        self.assertEqual(self.drain("applied"), ([], 0))
        self.assertEqual(len(self.sel.subs), 1)
        # đọc lại từ bin nguồn vẫn thấy cả clip nằm trong bin con
        self.w.do_load(path)
        self.assertEqual(len(self.drain("clips")[1]), 3)
        self.w.do_undo(log)
        back, failed = self.drain("undone")
        self.assertEqual((sorted(back), failed), (["a", "b"], 0))
        self.assertEqual(sorted(c.uid for c in self.sel.clips), ["a", "b", "c", "t"])

    def test_move_failure_reported_and_reveal(self):
        path = "Master/01_footage/01_SELECTED"
        self.w.do_load(path)
        self.drain("clips")
        self.pool.fail_move = True
        self.w.do_apply((path, {"a": ["01_Sáng"]}))
        self.assertEqual(self.drain("applied"), ([], 1))
        self.w.do_reveal("b")
        self.assertEqual(self.pool.selected.uid, "b")
        self.assertIs(self.pool.current, self.sel)

    def test_wrong_project(self):
        import queue
        w = self.tr.TrolyWorker("Khác", queue.Queue(), resolve_factory=lambda: FResolve(FProject("P", self.pool)))
        with self.assertRaises(RuntimeError):
            w.connect()

    def test_suggest_inout(self):
        # Decor: 3s
        d = tc.suggest_inout(6.0, "Decor")
        self.assertIsNotNone(d)
        self.assertEqual(d["dur"], 3.0)
        self.assertEqual(d["in_s"], 1.2)
        self.assertEqual(d["out_s"], 4.2)
        # CD-CR: 2-3s (ADR-0021); Beauty vẫn 4s
        cr = tc.suggest_inout(8.0, "Cô dâu chú rể")
        self.assertEqual(cr["dur"], 3.0)
        self.assertEqual(tc.suggest_inout(8.0, "Beauty cô dâu")["dur"], 4.0)
        # Nghi lễ: dài hơn
        nl = tc.suggest_inout(10.0, "Nghi lễ gia tiên")
        self.assertEqual(nl["dur"], 5.0)
        # Clip quá ngắn
        self.assertIsNone(tc.suggest_inout(0.8, "Decor"))


if __name__ == "__main__":
    unittest.main()
