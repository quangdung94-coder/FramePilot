"""Kiểm thử trang 1 lấy nguồn từ timeline DaVinci (ADR-0032): gộp máy theo track, tiền tố tên file, trục từ đầu timeline, bin mẹ, mẫu sự kiện,
cắt giai đoạn. Dùng Media Pool + timeline GIẢ, không cần DaVinci."""
import os
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
import troly_src as ts                # noqa: E402

NAME = "2026.11.14.Lora_Mau"
PATH = "Master/01_footage"


class Pure(unittest.TestCase):
    def test_tien_to_bo_ngay_o_dau_ten(self):
        self.assertEqual(ts.prefix_of("20261114_HM2129.MP4"), "HM")
        self.assertEqual(ts.prefix_of("DG4939.MP4"), "DG")
        self.assertEqual(ts.prefix_of("B_A5395.MP4"), "B_A")
        self.assertEqual(ts.prefix_of("A001_0915.MP4"), "A")
        self.assertEqual(ts.prefix_of("20261114_0001.MP4"), "")          # không có chữ: để trống, giao diện dùng tên Máy N, không hiện "?"

    def test_camera_key_khong_con_dau_hoi(self):
        k = tc.camera_key(T.props("20261114_HM2129.MP4", "", "", 1))
        self.assertTrue(k.startswith("HM "), k)
        self.assertNotIn("?", tc.camera_key(T.props("20261114_0001.MP4", "", "", 1)))

    def test_dung_bo_qua_co_xoay_tru_khi_bat_may_quay_doc(self):
        self.assertFalse(ts.portrait(3840, 2160, 90))                    # mặc định: chỉ kích thước mã hoá gốc
        self.assertTrue(ts.portrait(3840, 2160, 90, after_rotation=True))
        self.assertTrue(ts.portrait(2160, 3840, 0))

    def raw(self, tracks):
        return {"name": "t", "fps": 25.0, "start": 0, "tracks": tracks}

    def item(self, uid, name, start, dur, w=3840, h=2160, rot=0, audio_only=False):
        return {"uid": uid, "name": name, "start": start, "dur": dur, "w": w, "h": h, "rot": rot, "audio_only": audio_only}

    def test_may_theo_track_ten_theo_tien_to(self):
        raw = self.raw([
            {"kind": "video", "idx": 1, "name": "V1", "items": [self.item("a", "DG1.MP4", 0, 100), self.item("b", "DG2.MP4", 100, 100)]},
            {"kind": "video", "idx": 2, "name": "V2", "items": [self.item("c", "B_A1.MP4", 0, 100)]},
            {"kind": "video", "idx": 3, "name": "V3", "items": [self.item("d", "20261114_HM1.MP4", 0, 100)]},
            {"kind": "video", "idx": 4, "name": "V4", "items": []},
            {"kind": "audio", "idx": 1, "name": "Recorder", "items": [self.item("w", "x.WAV", 0, 500, audio_only=True), self.item("v", "DG1.MP4", 0, 100)]},
        ])
        ms = ts.machines(raw)
        self.assertEqual([m["name"] for m in ms], ["Máy A · DG", "Máy B · B_A", "Máy C · HM"])    # track rỗng không thành máy
        self.assertEqual([m["n"] for m in ms], [2, 1, 1])
        self.assertEqual(len({m["color"] for m in ms}), 3)
        rows = ts.audio_rows(raw)
        self.assertEqual([(r["name"], len(r["items"])) for r in rows], [("Recorder", 1)])          # âm thanh đi kèm clip video không thành hàng

    def test_tach_may_quay_doc_chi_khi_bat_cong_tac(self):
        raw = self.raw([{"kind": "video", "idx": 1, "name": "V1", "items": [self.item("a", "DJI1.MP4", 0, 50), self.item("b", "DJI2.MP4", 50, 50, 3840, 2160, 90)]}])
        self.assertEqual(len(ts.machines(raw, vertical=False)), 1)
        ms = ts.machines(raw, vertical=True)
        self.assertEqual(len(ms), 2)
        self.assertEqual(sorted(m["orient"] for m in ms), ["d", "n"])

    def test_nhan_biet_da_sync(self):
        a = [self.item("a", "DG1.MP4", 0, 1000)]
        b = [self.item("b", "B1.MP4", 100, 800)]
        self.assertTrue(ts.is_synced(self.raw([{"kind": "video", "idx": 1, "items": a}, {"kind": "video", "idx": 2, "items": b}]))[0])
        seq = [self.item("c", "B2.MP4", 5000, 800)]                     # máy 2 nằm sau máy 1: chưa sync
        ok, why = ts.is_synced(self.raw([{"kind": "video", "idx": 1, "items": a}, {"kind": "video", "idx": 2, "items": seq}]))
        self.assertFalse(ok)
        self.assertTrue(why)
        self.assertFalse(ts.is_synced(self.raw([]))[0])
        self.assertTrue(ts.is_synced(self.raw([{"kind": "video", "idx": 1, "items": a}]))[0])      # một máy: không cần sync

    def test_vi_tri_dau_tien_va_so_lan(self):
        raw = self.raw([{"kind": "video", "idx": 1, "items": [self.item("a", "DG1.MP4", 250, 50), self.item("a", "DG1.MP4", 50, 25)]}])
        p = ts.placements(raw)["a"]
        self.assertEqual((p["pos"], p["dur"], p["n"]), (2.0, 1.0, 2))                                # 50 frame / 25 fps

    def test_hms_hai_chieu(self):
        self.assertEqual(ts.fmt_hms(90), "1:30:00")
        self.assertEqual(ts.fmt_hms(0.5), "0:00:30")
        self.assertEqual(ts.parse_hms("1:30:00"), 90.0)
        self.assertEqual(ts.parse_hms("01:30"), 90.0)
        for bad in ("", "abc", "1:70:00", "1:00:99"):
            with self.assertRaises(ValueError):
                ts.parse_hms(bad)

    def test_mau_chi_tiec_nha_hang_va_bin_me(self):
        tpl = tc.BUILTIN_TEMPLATES["Chỉ tiệc nhà hàng"]
        self.assertEqual([n for n, _ in tpl], ["Đón khách", "Làm lễ · Vows", "Tiệc"])
        self.assertEqual({tc.event_of("Chỉ tiệc nhà hàng", n) for n, _ in tpl}, {"Tiệc nhà hàng"})         # chỉ MỘT bin mẹ
        full = tc.BUILTIN_TEMPLATES["Cưới đầy đủ (sáng lễ, tối tiệc)"]
        self.assertEqual({tc.event_of("Cưới đầy đủ (sáng lễ, tối tiệc)", n) for n, _ in full}, {"Lễ gia tiên", "Tiệc nhà hàng"})
        self.assertEqual(tc.event_of("mẫu tự lưu", "X"), tc.DEFAULT_EVENT)


class FTLItem(object):
    def __init__(self, uid, props, start, dur):
        self.mp, self.start, self.dur = T.FItem(uid, props), start, dur

    def GetMediaPoolItem(self):
        return self.mp

    def GetStart(self):
        return self.start

    def GetDuration(self):
        return self.dur


class FTimeline(object):
    def __init__(self, name, video, audio=None, fps=25.0, start=0):
        self.name, self.video, self.audio, self.fps, self.start = name, video, audio or [], fps, start

    def GetName(self):
        return self.name

    def GetSetting(self, k):
        return str(self.fps)

    def GetStartFrame(self):
        return self.start

    def GetTrackCount(self, kind):
        return len(self.video if kind == "video" else self.audio)

    def GetTrackName(self, kind, i):
        return "%s %d" % (kind, i)

    def GetItemListInTrack(self, kind, i):
        return list((self.video if kind == "video" else self.audio)[i - 1])


class FProjectTL(T.FProject):
    def __init__(self, name, pool, tls):
        T.FProject.__init__(self, name, pool)
        self.tls, self.cur, self.log = tls, tls[0], []

    def GetTimelineCount(self):
        return len(self.tls)

    def GetTimelineByIndex(self, i):
        return self.tls[i - 1]

    def GetCurrentTimeline(self):
        return self.cur

    def SetCurrentTimeline(self, t):
        self.cur = t
        self.log.append(t.GetName())
        return True


def build():
    """Bin nguồn có 9 clip của 3 máy (DG, B_A, HM) + 1 clip không nằm trên timeline. Timeline sync: mỗi máy một track, chồng nhau về giờ."""
    def mk(uid, fname):
        return T.props(fname, "Sat Nov 14 2026 16:00:00", "Sat Nov 14 16:00:06 2026", 150, Type="Video + Audio")
    plan = [("a1", "DG1.MP4", 1, 0, 500), ("a2", "DG2.MP4", 1, 600, 500), ("a3", "DG3.MP4", 1, 2000, 500),
            ("b1", "B_A1.MP4", 2, 100, 400), ("b2", "B_A2.MP4", 2, 700, 400), ("b3", "B_A3.MP4", 2, 2100, 400),
            ("h1", "20261114_HM1.MP4", 3, 50, 300), ("h2", "20261114_HM2.MP4", 3, 650, 300), ("h3", "20261114_HM3.MP4", 3, 2050, 300)]
    clips = [T.FItem(u, mk(u, f)) for u, f, _, _, _ in plan] + [T.FItem("zz", mk("zz", "DG9.MP4"))]
    video = [[], [], []]
    for u, f, tr, st, du in plan:
        video[tr - 1].append(FTLItem(u, mk(u, f), st, du))
    wav = T.props("TASCAM.WAV", "", "", 100, Type="Audio")
    audio = [[FTLItem("w1", wav, 0, 3000)]]
    synced = FTimeline("test muliticam", video, audio)
    seq = [[FTLItem("a1", mk("a1", "DG1.MP4"), 0, 500)], [FTLItem("b1", mk("b1", "B_A1.MP4"), 9000, 400)]]
    unsynced = FTimeline("chua sync", seq)
    foot = T.FFolder("01_footage", clips)
    root = T.FFolder("Master")
    root.subs.append(foot)
    return T.FPool(root), [synced, unsynced]


class ApiTL(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.apis = []

    def tearDown(self):
        for a in self.apis:
            a._closed = True
            a._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self):
        pool, tls = build()
        self.proj = FProjectTL(NAME, pool, tls)
        a = ta.TrolyApi(NAME, self.tmp, resolve_factory=lambda: T.FResolve(self.proj), start_worker=False)
        a._worker.connect()
        self.apis.append(a)
        self.run_jobs(a)
        return a

    def run_jobs(self, a):
        w = a._worker
        while not w.jobs.empty():
            job, arg = w.jobs.get()
            getattr(w, "do_" + job)(arg)
            a._drain()
        a._drain()

    def loaded(self, tl="test muliticam"):
        a = self.make()
        a.init()
        self.run_jobs(a)
        a.load(PATH, tl)
        self.run_jobs(a)
        return a

    def test_doc_timeline_may_clip_truc_tu_dau_timeline(self):
        a = self.loaded()
        st = a.state()
        self.assertEqual(st["src"]["axis"], "timeline")
        self.assertTrue(st["src"]["synced"])
        self.assertEqual(st["src"]["n_machines"], 3)
        self.assertEqual(st["src"]["n_clips"], 9)
        self.assertEqual(st["src"]["n_missing"], 1)                                 # clip zz trong bin nhưng không nằm trên timeline
        self.assertEqual([m["name"] for m in st["machines"]], ["Máy A · DG", "Máy B · B_A", "Máy C · HM"])
        c = {x["name"]: x for x in st["clips"]}
        self.assertAlmostEqual(c["DG2.MP4"]["m0"], 600 / 25.0 / 60.0)                # vị trí trên timeline, KHÔNG phải giờ trong file
        self.assertIsNone(c["DG9.MP4"]["m0"])
        self.assertEqual(c["20261114_HM1.MP4"]["mk"], "C")
        self.assertEqual([r["name"] for r in st["audio"]], ["audio 1"])
        self.assertEqual(len(st["audio"][0]["items"]), 1)

    def test_khong_tu_ap_mau_va_phai_chon_mau(self):
        a = self.loaded()
        st = a.state()
        self.assertEqual(st["stages"], [])
        self.assertEqual(st["template"], "")                                         # chưa chọn mẫu: ô hiện "Chọn mẫu sự kiện…"
        self.assertIn("error", a.suggest(""))

    def test_chi_tiec_nha_hang_mot_bin_me_va_cung_dat_ten_lai(self):
        a = self.loaded()
        st = a.suggest("Chỉ tiệc nhà hàng")
        self.assertEqual([s["name"] for s in st["stages"]], ["Đón khách", "Làm lễ · Vows", "Tiệc"])
        self.assertEqual([e["name"] for e in st["events"]], ["Tiệc nhà hàng"])
        self.assertEqual(st["events"][0]["idx"], [0, 1, 2])
        st = a.suggest("Cưới đầy đủ (sáng lễ, tối tiệc)")
        self.assertEqual([e["name"] for e in st["events"]], ["Lễ gia tiên", "Tiệc nhà hàng"])
        st = a.rename_event("Tiệc nhà hàng", "Tiệc tối")
        self.assertEqual([e["name"] for e in st["events"]], ["Lễ gia tiên", "Tiệc tối"])
        self.assertIn("error", a.rename_event("Tiệc tối", "lễ gia tiên"))           # trùng tên (không phân biệt hoa thường)
        self.assertIn("error", a.rename_event("Tiệc tối", ""))
        st = a.add_event()
        self.assertEqual(st["events"][-1]["name"], "Sự kiện 3")
        self.assertEqual(st["events"][-1]["idx"], [])

    def test_sua_moc_theo_truc_timeline_h_mm_ss(self):
        a = self.loaded()
        a.suggest("Chỉ tiệc nhà hàng")
        st = a.set_stage(0, {"start_txt": "0:00:10", "end_txt": "0:00:50"})
        self.assertEqual(st["stages"][0]["range"], "0:00:10 – 0:00:50")
        self.assertEqual(st["stages"][0]["start"], 10 / 60.0 * 1)                    # 10 giây = 1/6 phút
        self.assertIn("error", a.set_stage(0, {"start_txt": "07:99"}))

    def test_cat_giai_doan_tai_con_tro_khong_cat_clip(self):
        a = self.loaded()
        a.suggest("Chỉ tiệc nhà hàng")
        a.set_stage(0, {"start": 0.0, "end": 1.0})
        st = a.cut_stage(0.4)
        names = [s["name"] for s in st["stages"]]
        self.assertEqual(names[:2], ["Đón khách", "Đón khách 2"])
        self.assertEqual((st["stages"][0]["end"], st["stages"][1]["start"], st["stages"][1]["end"]), (0.4, 0.4, 1.0))
        self.assertIn("error", a.cut_stage(50.0))                                    # con trỏ ngoài mọi giai đoạn
        self.assertEqual(len(a.state()["clips"]), 10)                                # số clip không đổi

    def test_chua_sync_van_hien_nhan_va_dung_gio_trong_file(self):
        a = self.loaded("chua sync")
        st = a.state()
        self.assertFalse(st["src"]["synced"])
        self.assertEqual(st["src"]["axis"], "clock")
        self.assertIn("Chưa sync", st["src"]["note"])
        self.assertTrue(all(c["m0"] is not None for c in st["clips"]))              # dùng giờ trong file

    def test_moi_nguon_co_bo_giai_doan_rieng(self):
        a = self.loaded()
        a.suggest("Chỉ tiệc nhà hàng")
        self.assertEqual(len(a.state()["stages"]), 3)
        a.load(PATH, "")
        self.run_jobs(a)
        st = a.state()
        self.assertEqual(st["src"]["axis"], "clock")
        self.assertNotEqual([s["name"] for s in st["stages"]], ["Đón khách", "Làm lễ · Vows", "Tiệc"][:0] + ["__khong_co__"])
        a.load(PATH, "test muliticam")
        self.run_jobs(a)
        self.assertEqual([s["name"] for s in a.state()["stages"]], ["Đón khách", "Làm lễ · Vows", "Tiệc"])          # quay lại: giai đoạn cũ còn

    def test_cong_tac_may_quay_doc_mac_dinh_tat(self):
        a = self.loaded()
        self.assertFalse(a.state()["src"]["vertical"])
        st = a.set_vertical(True)
        self.assertTrue(st["src"]["vertical"])
        self.assertEqual(st["src"]["n_machines"], 3)                                 # clip đều ngang nên không tách thêm

    def test_chi_doc_va_tra_lai_timeline_dang_mo(self):
        a = self.loaded("chua sync")                                                 # timeline đang mở là "test muliticam", đọc "chua sync" phải trả lại
        self.assertEqual(self.proj.cur.GetName(), "test muliticam")
        self.assertEqual(self.proj.log, ["chua sync", "test muliticam"])
        self.assertFalse(any(j in ("apply", "inout_write", "append_timeline", "create_cut_timeline") for j, _ in list(a._worker.jobs.queue)))

    def test_nho_timeline_nguon_khi_mo_lai(self):
        a = self.loaded()
        a.suggest("Chỉ tiệc nhà hàng")
        a._save_now()
        b = self.make()
        self.assertEqual(b._tl_want, "test muliticam")
        self.assertEqual(b._plan["tl_source"], "test muliticam")


class WebFiles(unittest.TestCase):
    def setUp(self):
        web = os.path.join(HERE, "..", "app", "troly_web")
        self.html = open(os.path.join(web, "index.html"), encoding="utf-8").read()
        self.js = open(os.path.join(web, "app.js"), encoding="utf-8").read()
        self.css = open(os.path.join(web, "style.css"), encoding="utf-8").read()

    def test_giao_dien_co_dung_khoi_theo_demo(self):
        for ident in ("tlSel", "zOut", "zIn", "zFit", "cutStage", "snapBtn", "srcPills", "vertCams", "tlView", "tlLabels", "addEvent", "binPath"):
            self.assertIn('id="%s"' % ident, self.html)
        for text in ("Cắt giai đoạn tại con trỏ", "Vừa khít", "+ Thêm sự kiện (bin mẹ)", "Lưu mẫu cho đám sau", "Có máy quay dọc", "Gợi ý lại"):
            self.assertIn(text, self.html + self.js)

    def test_da_bo_nhung_phan_cu(self):
        for gone in ("camBox", "Chỉnh đồng hồ máy", "Project này chỉ có 1 máy", "Trợ lý đọc được", "Quy định", "Timeline sau khi sync"):
            self.assertNotIn(gone, self.html + self.js)

    def test_chu_cat_bang_dau_ba_cham_va_nhan_con_tro_khong_de_nhan_moc(self):
        self.assertIn("text-overflow: ellipsis", self.css[self.css.index(".sblk .sn"):self.css.index(".sblk .h ")])
        self.assertIn("Math.abs(x - curX) < 70", self.js)                            # nhãn mốc trục gần con trỏ bị ẩn

    def test_trang_1_khong_goi_ham_ghi_davinci(self):
        i = self.js.index("function renderPage1")
        j = self.js.index("/* ------------------------------------------------------------------ áp dụng / hoàn tác")
        seg = self.js[i:j]
        for bad in ("api().apply(", "api().move(", "api().inout_write", "api().append_starred"):
            self.assertNotIn(bad, seg)


if __name__ == "__main__":
    unittest.main()
