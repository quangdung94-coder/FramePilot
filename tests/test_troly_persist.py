"""Kiểm thử lưu/nạp lại kế hoạch của Trợ lý File Quay (ADR-0009, bổ sung 15/11/2026: panel nhớ project sau khi mở lại).
Không cần DaVinci: dùng Media Pool giả của test_troly.py."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_troly as T                # noqa: E402
import troly_api as ta                # noqa: E402
import troly_core as tc               # noqa: E402

PATH = "Master/01_footage/01_SELECTED"
NAMES = ["2026.10.25.LV_X&Y", "2026.11.01.LV_Nguyễn Văn Ánh & Đặng Thị Hồng", "2026.12.31.AB_Tên (có) [ngoặc]",
         "2026.10.17.LV_Ten"]


def make_pool(n=5):
    def mk(uid, hh, mm):
        return T.FItem(uid, T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:%02d:00" % (hh, mm),
                                    "Sat Oct 17 %02d:%02d:06 2026" % (hh, mm), 300, Type="Video + Audio"))
    clips = [mk("a", 6, 30), mk("b", 6, 40), mk("c", 8, 10), mk("d", 8, 20), mk("e", 18, 0)][:n]
    sel = T.FFolder("01_SELECTED", clips)
    foot = T.FFolder("01_footage")
    foot.subs.append(sel)
    root = T.FFolder("Master")
    root.subs.append(foot)
    return T.FPool(root), sel, mk


class UidProject(T.FProject):
    def __init__(self, name, pool, uid):
        super().__init__(name, pool)
        self.uid = uid

    def GetUniqueId(self):
        return self.uid


class Names(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_names_with_ampersand_and_vietnamese_roundtrip(self):
        for name in NAMES:
            plan = tc.new_plan(name)
            plan["source_bin"] = PATH
            plan["labels"]["01_footage/DG1.MP4"] = {"stage": "Rước dâu", "bin": "Nhà trai đến", "by": "nguoi"}
            plan["ui"] = {"page": 2, "view": [360.0, 1320.0], "gStage": 1, "gSub": "Nhà trai đến", "onlyNew": False}
            tc.save_plan(self.tmp, plan)
            p = tc.plan_path(self.tmp, name)
            self.assertTrue(os.path.isfile(p), name)
            self.assertEqual(os.path.dirname(p), os.path.join(self.tmp, "troly", "projects"))
            back = tc.load_plan(self.tmp, name)
            self.assertEqual(back["labels"], plan["labels"], name)
            self.assertEqual(back["ui"], plan["ui"], name)
            self.assertEqual(back["project"], name)

    def test_illegal_characters_and_trailing_dot(self):
        self.assertEqual(tc._safe('a<b>c:d"e/f\\g|h?i*j'), "a_b_c_d_e_f_g_h_i_j")
        self.assertEqual(tc._safe("2026.10.25.X."), "2026.10.25.X")
        self.assertEqual(tc._safe("..."), "project")
        self.assertEqual(tc._safe("Ánh & Đặng"), "Ánh & Đặng")

    def test_two_names_with_same_safe_name_do_not_overwrite_each_other(self):
        a, b = "2026.10.01.X_a:b", "2026.10.01.X_a|b"
        self.assertEqual(tc._safe(a), tc._safe(b))
        pa = tc.new_plan(a)
        pa["labels"]["k"] = {"stage": "S", "bin": "A"}
        tc.save_plan(self.tmp, pa)
        pb = tc.new_plan(b)
        pb["labels"]["k"] = {"stage": "S", "bin": "B"}
        tc.save_plan(self.tmp, pb)
        self.assertNotEqual(tc.plan_path(self.tmp, a), tc.plan_path(self.tmp, b))
        self.assertEqual(tc.load_plan(self.tmp, a)["labels"]["k"]["bin"], "A")
        self.assertEqual(tc.load_plan(self.tmp, b)["labels"]["k"]["bin"], "B")

    def test_atomic_save_keeps_backup_and_corrupt_file_is_never_overwritten_by_empty_plan(self):
        name = NAMES[0]
        plan = tc.new_plan(name)
        plan["labels"]["k1"] = {"stage": "S", "bin": "A"}
        tc.save_plan(self.tmp, plan)
        plan["labels"]["k2"] = {"stage": "S", "bin": "B"}
        tc.save_plan(self.tmp, plan)                                   # lần 2: bản lần 1 thành .bak
        p = tc.plan_path(self.tmp, name)
        self.assertEqual(len(json.load(open(p + ".bak", encoding="utf-8"))["labels"]), 1)
        self.assertFalse(os.path.exists(p + ".tmp"))                   # không để file tạm
        with open(p, "w", encoding="utf-8") as f:                      # mô phỏng file chính bị cắt cụt giữa chừng
            f.write('{"schema": 1, "project": %s, "labels": {"k1": {"sta' % json.dumps(name, ensure_ascii=False))
        back = tc.load_plan(self.tmp, name)
        self.assertEqual(len(back["labels"]), 1)                       # nạp lại từ .bak
        self.assertIn("_note", back)
        corrupt = [f for f in os.listdir(os.path.dirname(p)) if ".corrupt-" in f]
        self.assertEqual(len(corrupt), 1)                              # file hỏng được GIỮ để cứu, không bị ghi đè
        tc.save_plan(self.tmp, {k: v for k, v in back.items() if not k.startswith("_")})
        self.assertEqual(len(tc.load_plan(self.tmp, name)["labels"]), 1)
        self.assertEqual(len([f for f in os.listdir(os.path.dirname(p)) if ".corrupt-" in f]), 1)

    def test_both_files_corrupt_gives_empty_plan_but_keeps_corrupt_copy(self):
        name = NAMES[1]
        p = tc.plan_path(self.tmp, name)
        os.makedirs(os.path.dirname(p))
        open(p, "w", encoding="utf-8").write("{rác")
        back = tc.load_plan(self.tmp, name)
        self.assertEqual((back["stages"], back["labels"]), ([], {}))
        self.assertTrue(any(".corrupt-" in f for f in os.listdir(os.path.dirname(p))))


class Reopen(unittest.TestCase):
    """Ghi, thoát, mở lại (Api mới trên cùng thư mục dữ liệu), so khớp."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pool, self.sel, self.mk = make_pool()
        self.name = NAMES[0]
        self.uid = "uid-111"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def api(self, name=None, uid=None):
        name, uid = name or self.name, uid or self.uid
        a = ta.TrolyApi(name, self.tmp, start_worker=False,
                        resolve_factory=lambda: T.FResolve(UidProject(name, self.pool, uid)))
        a._worker.connect()
        a.events = []
        a._emit_fn = lambda k, d: a.events.append((k, d))
        return a

    @staticmethod
    def pump(a):
        for _ in range(10):
            while not a._worker.jobs.empty():
                job, arg = a._worker.jobs.get()
                getattr(a._worker, "do_" + job)(arg)
            a._drain()
            if a._worker.jobs.empty() and a._q.empty():
                return

    def first_session(self):
        a = self.api()
        a.init()
        self.pump(a)
        a.load(PATH)
        self.pump(a)
        a.suggest("Tiệc nhà hàng")
        a.label(["a"], 0, "Decor")
        a.label(["b"], 0, "Khách")
        a.move(["c"], 2, "Khách")                                    # chọn tay + nhãn
        a.set_offset(a.state()["cameras"][0]["cam"], "-30")
        a.set_stage(1, {"start_txt": "08:00", "end_txt": "08:30"})
        a.save_ui({"page": 2, "view": [400.5, 1300.0], "gStage": 2, "gSub": "Khách", "onlyNew": True})
        return a

    def test_everything_is_saved_immediately_without_timer(self):
        a = self.first_session()
        on_disk = json.load(open(tc.plan_path(self.tmp, self.name), encoding="utf-8"))     # chưa gọi close()/chờ gì
        self.assertEqual(on_disk["labels"]["01_footage/DGa.MP4"]["bin"], "Decor")
        self.assertEqual(on_disk["manual"]["01_footage/DGc.MP4"]["stage"], a._stages[2]["name"])
        self.assertEqual(on_disk["ui"]["page"], 2)
        self.assertEqual(on_disk["source_bin"], PATH)
        self.assertEqual(on_disk["project_uid"], self.uid)

    def test_reopen_restores_state_and_autoloads_clips(self):
        a = self.first_session()
        before = a.state()
        a.close()
        b = self.api()                                                 # mở lại panel, KHÔNG gọi load()
        info = b.init()
        self.pump(b)
        self.assertEqual(info["ui"], {"page": 2, "view": [400.5, 1300.0], "gStage": 2, "gSub": "Khách", "onlyNew": True})
        after = b.state()
        self.assertEqual(after["n"], before["n"])                       # clip tự nạp
        self.assertEqual([s["range"] for s in after["stages"]], [s["range"] for s in before["stages"]])
        self.assertEqual([s["count"] for s in after["stages"]], [s["count"] for s in before["stages"]])
        self.assertEqual([c["label"] for c in after["clips"]], [c["label"] for c in before["clips"]])
        self.assertEqual([c["manual"] for c in after["clips"]], [c["manual"] for c in before["clips"]])
        self.assertEqual([c["stage"] for c in after["clips"]], [c["stage"] for c in before["clips"]])
        self.assertEqual(after["cameras"], before["cameras"])           # lệch giờ theo máy
        self.assertEqual((after["bin"], after["template"], after["n_manual"]),
                         (before["bin"], before["template"], before["n_manual"]))
        self.assertEqual((after["new_n"], after["gone_n"]), (0, 0))
        self.assertTrue(any(k == "state" for k, _ in b.events))

    def test_autoload_only_once_not_after_apply(self):
        a = self.first_session()
        a.close()
        b = self.api()
        b.init()
        self.pump(b)
        b.events.clear()
        b._worker.jobs.put(("bins", None))                              # như sau Áp dụng/Hoàn tác
        self.pump(b)
        self.assertEqual([k for k, _ in b.events if k == "state"], [])  # không nạp lại lần nữa

    def test_new_and_missing_clips_after_reopen(self):
        a = self.first_session()
        a.close()
        self.sel.clips.append(self.mk("f", 19, 0))                      # clip MỚI trong Media Pool
        self.sel.clips = [c for c in self.sel.clips if c.uid != "b"]    # clip đã xếp nhãn KHÔNG còn nữa
        b = self.api()
        b.init()
        self.pump(b)
        st = b.state()
        self.assertEqual((st["n"], st["new_n"], st["gone_n"]), (5, 1, 1))
        lab = {c["name"]: c["label"] for c in st["clips"]}
        self.assertEqual(lab["DGa.MP4"], "Decor")                       # nhãn clip còn lại giữ nguyên
        self.assertIsNone(lab["DGf.MP4"])                               # clip mới chưa phân loại
        self.assertIn("1 clip MỚI", [d["text"] for k, d in b.events if k == "status"][-1])
        self.assertIn("labels", json.load(open(tc.plan_path(self.tmp, self.name), encoding="utf-8")))
        self.assertIn("01_footage/DGb.MP4", tc.load_plan(self.tmp, self.name)["labels"])   # nhãn clip mất vẫn nằm trong file

    def test_project_renamed_in_resolve_keeps_plan_by_unique_id(self):
        a = self.first_session()
        a.close()
        new_name = "2026.10.25.LV_X&Y-doiTen"
        b = self.api(name=new_name)                                     # cùng GetUniqueId, tên khác
        b.init()
        self.pump(b)
        st = b.state()
        self.assertEqual(st["n"], 5)
        self.assertEqual({c["name"]: c["label"] for c in st["clips"]}["DGa.MP4"], "Decor")
        self.assertEqual(b._plan["project"], new_name)
        self.assertTrue(os.path.isfile(tc.plan_path(self.tmp, new_name)))
        self.assertTrue(os.path.isfile(tc.plan_path(self.tmp, self.name)))       # file cũ giữ nguyên, không xóa
        self.assertTrue(any("đổi tên" in d["text"] for k, d in b.events if k == "status"))

    def test_other_project_with_different_uid_does_not_adopt(self):
        a = self.first_session()
        a.close()
        c = self.api(name="2026.11.02.XX_KhacHan", uid="uid-999")
        c.init()
        self.pump(c)
        self.assertEqual((c.state()["n"], c._plan["labels"]), (0, {}))

    def test_corrupt_plan_on_open_recovers_from_backup_and_tells_user(self):
        a = self.first_session()
        a.label(["d"], 1, None)                                         # thêm một lần lưu để có .bak
        a.close()
        p = tc.plan_path(self.tmp, self.name)
        open(p, "w", encoding="utf-8").write("{hỏng")
        b = self.api()
        b.init()
        self.pump(b)
        self.assertGreaterEqual(len(b._plan["labels"]), 2)
        self.assertTrue(any("hỏng" in d["text"] for k, d in b.events if k == "status"))

    def test_save_ui_validates_and_ignores_garbage(self):
        a = self.api()
        self.assertFalse(a.save_ui({"page": "abc"}))
        self.assertTrue(a.save_ui({"page": 1, "view": [1, 2], "gStage": None, "gSub": None, "onlyNew": False}))
        self.assertEqual(a._plan["ui"]["view"], [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
