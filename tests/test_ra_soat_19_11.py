"""Tổng duyệt 19/11/2026 (nhánh ra-soat-19-11): mỗi bài chứng minh một lỗi đã tìm thấy (đỏ trước khi sửa, xanh sau khi sửa).
Dữ liệu giả trong thư mục tạm, DaVinci giả, tên ví dụ LV_Ten. Không đụng footage/proxy/project thật."""
import json
import os
import queue
import shutil
import subprocess
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

NAME = "2026.10.17.LV_Ten"
A = "Master/01_footage/A_cam"
B = "Master/01_footage/B_cam"


def mk(uid, hh, path=None):
    p = T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:00:00" % hh, "Sat Oct 17 %02d:00:06 2026" % hh, 300, Type="Video + Audio")
    if path:
        p["File Path"] = path
    return T.FItem(uid, p)


def two_bin_pool():
    fa = T.FFolder("A_cam", [mk("a1", 6), mk("a2", 9), mk("a3", 18)])
    fb = T.FFolder("B_cam", [mk("b1", 7), mk("b2", 19)])
    foot = T.FFolder("01_footage")
    foot.subs += [fa, fb]
    root = T.FFolder("Master")
    root.subs.append(foot)
    return T.FPool(root)


class Base(unittest.TestCase):
    pool_fn = staticmethod(two_bin_pool)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pool = self.pool_fn()
        self.events = []
        self.api = self.make_api()

    def make_api(self):
        api = ta.TrolyApi(NAME, self.tmp, emit=lambda k, d: self.events.append((k, d)),
                          resolve_factory=lambda: T.FResolve(T.FProject(NAME, self.pool)), start_worker=False)
        api._worker.connect()
        return api

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_jobs(self, api=None):
        api = api or self.api
        w = api._worker
        while not w.jobs.empty():
            j, a = w.jobs.get()
            try:
                getattr(w, "do_" + j)(a)
            except Exception as e:                    # noqa: BLE001
                w.post("error", (j, str(e)))
        api._drain()

    def statuses(self):
        return [d["text"] for k, d in self.events if k == "status"]


class StagesKeptPerBin(Base):
    def test_doc_bin_khac_roi_quay_lai_khong_mat_giai_doan_da_keo(self):
        """Lỗi (Nghiêm trọng): chọn bin nguồn khác rồi bấm Đọc clip thì giai đoạn người dựng đã kéo/đổi tên bị ghi đè bằng giai đoạn
        gợi ý và lưu ngay; quay lại bin cũ cũng không lấy lại được."""
        self.api.init()
        self.run_jobs()
        self.api.load(A)
        self.run_jobs()
        st = self.api.set_stage(0, {"name": "Nhà gái của tôi"})
        self.assertNotIn("error", st)
        mine = json.loads(json.dumps(self.api._plan["stages"]))
        self.api.load(B)                              # bấm nhầm bin khác
        self.run_jobs()
        self.api.load(A)                              # quay lại
        self.run_jobs()
        self.assertEqual(self.api._plan["stages"], mine)
        reopened = tc.load_plan(self.tmp, NAME)       # và đã lưu xuống đĩa
        self.assertEqual(reopened["stages"], mine)


class UndoOtherBin(Base):
    def test_hoan_tac_khi_dang_xem_bin_khac_bao_ro_ly_do(self):
        """Lỗi (Trung bình): lần chuyển gần nhất thuộc bin A nhưng đang đọc bin B: bấm Hoàn tác thì không có gì xảy ra, không báo gì."""
        self.api.init()
        self.run_jobs()
        self.api.load(A)
        self.run_jobs()
        st = self.api.state()
        self.api.label([st["clips"][0]["uid"]], 0, st["stages"][0]["bins"][0]["name"])
        self.assertTrue(self.api.apply())
        self.run_jobs()
        self.assertEqual(len(self.api._plan["moves"]), 1)
        self.api.load(B)
        self.run_jobs()
        self.events.clear()
        self.assertFalse(self.api.undo())
        self.assertTrue(any("A_cam" in s and "Hoàn tác" in s for s in self.statuses()), self.statuses())
        self.assertEqual(len(self.api._plan["moves"]), 1)     # nhật ký vẫn giữ


class InoutBackupOtherProject(unittest.TestCase):
    def test_hoan_tac_in_out_khong_lay_nham_sao_luu_cua_project_ten_dai_hon(self):
        """Lỗi (Trung bình): project 'X' lấy nhầm file sao lưu của project 'X_B' (cùng tiền tố 'X_')."""
        tmp = tempfile.mkdtemp()
        try:
            tc.write_inout_backup(tmp, "LV_Ten", [{"uid": "u1", "rel": "a", "in": None, "out": None}], stamp="20261119-080000")
            other = tc.write_inout_backup(tmp, "LV_Ten_B", [{"uid": "z9", "rel": "z", "in": 1, "out": 2}], stamp="20261119-090000")
            got = tc.latest_inout_backup(tmp, "LV_Ten")
            self.assertNotEqual(got, other)
            self.assertEqual(tc.read_inout_backup(got)["project"], "LV_Ten")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class InoutRestoreSkipped(Base):
    def test_khoi_phuc_ma_bo_qua_clip_chua_doc_thi_khong_danh_dau_da_hoan_tac(self):
        """Lỗi (Trung bình): Hoàn tác In/Out khi clip trong sao lưu chưa được đọc (đang xem bin khác) -> bỏ qua hết nhưng vẫn đánh dấu
        'đã khôi phục', lần sau không còn Hoàn tác được nữa."""
        bk = tc.write_inout_backup(self.tmp, NAME, [{"uid": "khong_co", "rel": "x", "in": None, "out": None}])
        self.api.init()
        self.run_jobs()
        self.api.load(A)
        self.run_jobs()
        self.assertTrue(self.api.inout_undo().get("ok"))
        self.run_jobs()
        self.assertFalse(tc.read_inout_backup(bk).get("restored"))
        self.assertEqual(tc.latest_inout_backup(self.tmp, NAME), bk)


def dup_pool():
    """Hai máy Sony: thẻ nhớ chép vào hai thư mục không có tên ngày -> cùng đuôi CLIP/C0001.MP4."""
    fa = T.FFolder("Footage", [mk("s1", 7, r"J:\Cuoi\CAM A\PRIVATE\M4ROOT\CLIP\C0001.MP4"),
                               mk("s2", 8, r"J:\Cuoi\CAM B\PRIVATE\M4ROOT\CLIP\C0001.MP4"),
                               mk("s3", 9, r"J:\Cuoi\CAM B\PRIVATE\M4ROOT\CLIP\C0002.MP4")])
    root = T.FFolder("Master")
    root.subs.append(fa)
    return T.FPool(root)


class DuplicateRel(Base):
    pool_fn = staticmethod(dup_pool)

    def test_hai_clip_trung_khoa_khong_duoc_ghi_in_out_va_co_canh_bao(self):
        """Lỗi (Nghiêm trọng): hai clip khác nhau trùng khóa đường dẫn tương đối dùng chung In/Out đặt tay -> bấm Ghi In/Out thì clip kia
        cũng bị ghi In/Out người dựng không hề đặt cho nó."""
        self.api.init()
        self.run_jobs()
        self.api.load("Master/Footage")
        self.run_jobs()
        self.assertTrue(any("trùng" in s for s in self.statuses()), self.statuses())
        self.api.set_inout("s1", 1.0, 3.0)
        pv = self.api.inout_write_preview("selected", ["s1", "s2", "s3"])
        self.assertEqual(pv["n"], 0)                  # s1, s2 trùng khóa: không ghi; s3 chưa đặt tay
        self.api.set_inout("s3", 1.0, 2.0)
        r = self.api.inout_write("selected", ["s1", "s2", "s3"])
        self.assertEqual(r.get("n"), 1)


# --------------------------------------------------------------------------- timeline: AppendToTimeline đi vào timeline HIỆN TẠI
class Tl(object):
    def __init__(self, name):
        self.name, self.appended = name, []

    def GetName(self):
        return self.name


class CurPool(T.FPool):
    """Như DaVinci thật: AppendToTimeline thêm vào timeline HIỆN TẠI của project. CreateTimelineFromClips trả None (để đi đường dự phòng);
    CreateEmptyTimeline tạo timeline nhưng (giả định xấu) KHÔNG tự đặt làm hiện tại."""

    def __init__(self, root, proj):
        super().__init__(root)
        self.proj = proj

    def CreateTimelineFromClips(self, name, items):
        return None

    def CreateEmptyTimeline(self, name):
        tl = Tl(name)
        self.proj.timelines.append(tl)
        return tl

    def AppendToTimeline(self, items):
        cur = self.proj.current
        if cur is None:
            return False
        cur.appended.extend(items)
        return True


class CurProject(T.FProject):
    def __init__(self, name, pool=None, can_switch=True):
        super().__init__(name, pool)
        self.old = Tl("Timeline dựng của bạn")
        self.timelines = [self.old]
        self.current = self.old
        self.can_switch = can_switch

    def GetTimelineCount(self):
        return len(self.timelines)

    def GetTimelineByIndex(self, i):
        return self.timelines[i - 1]

    def SetCurrentTimeline(self, tl):
        if not self.can_switch:
            return False
        self.current = tl
        return True

    def GetCurrentTimeline(self):
        return self.current


class AppendGoesToCurrent(unittest.TestCase):
    def make(self, can_switch):
        proj = CurProject(NAME, can_switch=can_switch)
        sel = T.FFolder("Sel", [mk("a", 6), mk("b", 7)])
        root = T.FFolder("Master")
        root.subs.append(sel)
        proj.pool = CurPool(root, proj)
        q = queue.Queue()
        w = tr.TrolyWorker(NAME, q, resolve_factory=lambda: T.FResolve(proj))
        w.connect()
        w.do_load("Master/Sel")
        return w, proj

    def test_sao_len_timeline_du_phong_khong_them_vao_timeline_dang_co(self):
        """Lỗi (Nghiêm trọng, ghi nhầm vào DaVinci): đường dự phòng CreateEmptyTimeline + AppendToTimeline thêm clip vào timeline
        HIỆN TẠI; nếu DaVinci không tự chuyển sang timeline mới thì clip bị chèn vào timeline đang dựng của người dùng."""
        w, proj = self.make(can_switch=True)
        w.do_append_timeline(["a", "b"])
        self.assertEqual(proj.old.appended, [])
        self.assertEqual(len(proj.timelines[-1].appended), 2)

    def test_khong_chuyen_duoc_timeline_thi_dung_va_bao_loi(self):
        w, proj = self.make(can_switch=False)
        with self.assertRaises(RuntimeError):
            w.do_append_timeline(["a", "b"])
        self.assertEqual(proj.old.appended, [])

    def test_buoc5_du_phong_cung_khong_them_vao_timeline_dang_co(self):
        w, proj = self.make(can_switch=False)
        segs = [{"uid": "a", "a": 0, "b": 100, "pct": 100.0, "track": "V1", "start_f": 0, "mute": False}]
        with self.assertRaises(RuntimeError):
            w.do_create_cut_timeline(("Thu", segs))
        self.assertEqual(proj.old.appended, [])


# --------------------------------------------------------------------------- hai cửa sổ FramePilot cùng một project
class SingleInstance(unittest.TestCase):
    def test_cua_so_thu_hai_cung_project_bi_chan(self):
        """Lỗi (Nghiêm trọng): mở FramePilot hai lần cho cùng project, mỗi cửa sổ giữ kế hoạch riêng trong bộ nhớ và ghi đè cả file
        -> nhãn/sao xếp ở cửa sổ này mất khi cửa sổ kia lưu."""
        import troly_env
        tmp = tempfile.mkdtemp()
        try:
            h = troly_env.instance_lock(tmp, NAME)
            self.assertIsNotNone(h)
            code = ("import sys; sys.path.insert(0, %r); import troly_env; "
                    "print('LOCKED' if troly_env.instance_lock(%r, %r) is None else 'FREE')") % (
                os.path.join(HERE, "..", "app"), tmp, NAME)
            out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60).stdout
            self.assertIn("LOCKED", out)
            other = troly_env.instance_lock(tmp, NAME + "_khac")   # project khác vẫn mở được
            self.assertIsNotNone(other)
            other.close()
            h.close()
            out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60).stdout
            self.assertIn("FREE", out)                             # đóng cửa sổ (hoặc tiến trình chết) thì khóa tự nhả
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
