"""
troly_resolve.py - Cầu nối DaVinci cho Trợ lý File Quay (ADR-0009). Mọi lệnh gọi DaVinci chạy trong MỘT luồng nền
(giống panel_common.ResolveWorker), giao diện chỉ gửi việc và nhận kết quả qua hàng đợi.

Việc ĐỌC: danh sách bin, clip của một bin (gồm mọi bin con), thuộc tính từng clip.
Việc GHI (chỉ khi người dựng bấm "Áp dụng vào Media Pool", ADR-0009):
  - tạo bin con bên trong bin nguồn (01_Rước dâu, 01_Rước dâu/Decor, ...): AddSubFolder;
  - CHUYỂN clip vào bin đó: MoveClips. Không xóa clip, không đổi tên, không đụng file trên ổ, không đụng in/out, màu.
  - Mỗi lần chuyển ghi nhật ký (clip nào từ bin nào sang bin nào) vào kế hoạch của project để HOÀN TÁC được.
"""
import os
import queue
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import troly_core as tc    # noqa: E402


def is_video(props):
    t = props.get("Type") or ""
    return "Video" in t and "Timeline" not in t and "Compound" not in t


def walk_bins(folder, path, out):
    n = 0
    for c in folder.GetClipList() or []:
        if is_video({"Type": c.GetClipProperty("Type") or ""}):
            n += 1
    out.append({"path": path, "name": folder.GetName(), "n": n})
    for sf in folder.GetSubFolderList() or []:
        walk_bins(sf, path + "/" + sf.GetName(), out)
    return out


def find_folder(root, path):
    """'Master/01_footage/01_SELECTED' -> Folder (đi theo tên từng cấp). Không thấy -> None."""
    parts = [p for p in (path or "").split("/") if p]
    if not parts or parts[0] != root.GetName():
        return None
    cur = root
    for name in parts[1:]:
        nxt = None
        for sf in cur.GetSubFolderList() or []:
            if sf.GetName() == name:
                nxt = sf
                break
        if nxt is None:
            return None
        cur = nxt
    return cur


def walk_clips(folder, path, out):
    """[(đường bin, MediaPoolItem)] của bin và mọi bin con."""
    for c in folder.GetClipList() or []:
        out.append((path, c))
    for sf in folder.GetSubFolderList() or []:
        walk_clips(sf, path + "/" + sf.GetName(), out)
    return out


def ensure_sub(pool, parent, name):
    for sf in parent.GetSubFolderList() or []:
        if sf.GetName() == name:
            return sf
    return pool.AddSubFolder(parent, name)


class TrolyWorker(threading.Thread):
    """Nhận việc qua self.jobs = (tên, tham số), gọi do_<tên>, trả (loại, dữ liệu) qua out_q."""

    def __init__(self, project_name, out_q, resolve_factory=None):
        super().__init__(daemon=True)
        self.project_name, self.out_q = project_name, out_q
        self.jobs = queue.Queue()
        self.project = None
        self.project_uid = ""
        self.items = {}                   # uid -> (đường bin, MediaPoolItem) của lần đọc gần nhất
        self._factory = resolve_factory

    def post(self, kind, data=None):
        self.out_q.put((kind, data))

    def connect(self):
        if self.project is not None:
            return
        if self._factory:
            resolve = self._factory()
        else:
            import troly_env
            resolve = troly_env.connect_resolve()
        p = resolve.GetProjectManager().GetCurrentProject()
        if not p or p.GetName() != self.project_name:
            raise RuntimeError("DaVinci đang mở project khác. Hãy mở project %s." % self.project_name)
        self.project = p
        try:                                          # id bền của project (không đổi khi đổi tên project)
            self.project_uid = str(p.GetUniqueId() or "")
        except Exception:                             # noqa: BLE001  bản DaVinci/giả lập không có hàm này
            self.project_uid = ""

    @property
    def pool(self):
        return self.project.GetMediaPool()

    # --- ĐỌC --------------------------------------------------------------
    def do_bins(self, _):
        root = self.pool.GetRootFolder()
        cur = self.pool.GetCurrentFolder()
        self.post("bins", (walk_bins(root, root.GetName(), []), cur.GetName() if cur else None))

    def do_load(self, bin_path):
        root = self.pool.GetRootFolder()
        f = find_folder(root, bin_path)
        if f is None:
            raise RuntimeError("Không thấy bin %s trong media pool." % bin_path)
        rows = walk_clips(f, bin_path, [])
        clips, self.items = [], {}
        for i, (bp, mpi) in enumerate(rows):
            props = mpi.GetClipProperty() or {}
            if not is_video(props):
                continue
            uid = mpi.GetUniqueId()
            self.items[uid] = (bp, mpi)
            marks = {}
            try:
                marks = mpi.GetMarkInOut() or {}
            except Exception:
                pass
            v_mark = marks.get("video") if isinstance(marks, dict) else {}
            if not isinstance(v_mark, dict):
                v_mark = {}
            m_in = v_mark.get("in")
            m_out = v_mark.get("out")
            clips.append(tc.Clip.from_props(uid, props, bp, mark_in=m_in, mark_out=m_out))
            if i % 50 == 0:
                self.post("progress", ("Đang đọc clip", i + 1, len(rows)))
        self.post("clips", (bin_path, clips))

    # --- GHI (ADR-0009) -----------------------------------------------------
    def do_apply(self, arg):
        """arg = (bin nguồn, {uid: [tên bin cấp 1, tên bin cấp 2] }). Clip có [] thì để nguyên chỗ cũ.
        Trả nhật ký [(uid, bin cũ, bin mới)] chỉ gồm các clip ĐÃ chuyển thật."""
        src_path, targets = arg
        root = self.pool.GetRootFolder()
        src = find_folder(root, src_path)
        if src is None:
            raise RuntimeError("Không thấy bin nguồn %s." % src_path)
        if not self.items:
            self.do_load(src_path)
        groups = {}
        for uid, parts in targets.items():
            if not parts or uid not in self.items:
                continue
            dst_path = src_path + "/" + "/".join(parts)
            if self.items[uid][0] == dst_path:
                continue                                       # đã đúng chỗ
            groups.setdefault(tuple(parts), []).append(uid)
        log, failed = [], 0
        done = 0
        total = sum(len(v) for v in groups.values())
        for parts, uids in sorted(groups.items()):
            folder = src
            for name in parts:
                folder = ensure_sub(self.pool, folder, name)
                if folder is None:
                    raise RuntimeError("Không tạo được bin %s." % name)
            dst_path = src_path + "/" + "/".join(parts)
            items = [self.items[u][1] for u in uids]
            ok = self.pool.MoveClips(items, folder)
            if not ok:
                failed += len(uids)
                continue
            for u in uids:
                log.append((u, self.items[u][0], dst_path))
                self.items[u] = (dst_path, self.items[u][1])
            done += len(uids)
            self.post("progress", ("Đang chuyển clip", done, total))
        self.post("applied", (log, failed))

    def do_undo(self, log):
        """Chuyển clip về lại bin cũ theo nhật ký của lần áp dụng (bin trống đã tạo để lại, không xóa)."""
        root = self.pool.GetRootFolder()
        back, failed = [], 0
        by_dst = {}
        for uid, old, new in log:
            by_dst.setdefault(old, []).append(uid)
        if not self.items:
            raise RuntimeError("Hãy bấm 'Đọc clip' trước khi hoàn tác.")
        for old, uids in by_dst.items():
            f = find_folder(root, old)
            items = [self.items[u][1] for u in uids if u in self.items]
            if f is None or not items or not self.pool.MoveClips(items, f):
                failed += len(uids)
                continue
            for u in uids:
                if u in self.items:
                    self.items[u] = (old, self.items[u][1])
                    back.append(u)
        self.post("undone", (back, failed))

    def do_reveal(self, uid):
        """Mở bin chứa clip và chọn clip đó trong media pool (để anh xem ngay trong DaVinci)."""
        if uid not in self.items:
            return
        bp, mpi = self.items[uid]
        f = find_folder(self.pool.GetRootFolder(), bp)
        if f is not None:
            self.pool.SetCurrentFolder(f)
        try:
            self.pool.SetSelectedClip(mpi)
        except Exception:                                     # noqa: BLE001  bản DaVinci cũ không có lệnh này
            pass

    def do_append_timeline(self, uids):
        """Tạo timeline MỚI từ danh sách clip có sao (đã sắp theo giai đoạn và giờ quay). KHÔNG sửa timeline đang có.
        Thử 2 cách: CreateTimelineFromClips, nếu DaVinci trả rỗng thì CreateEmptyTimeline + AppendToTimeline.
        Lỗi thì báo rõ bước nào hỏng."""
        import datetime
        import re
        if not self.items:
            raise RuntimeError("Hãy bấm 'Đọc clip' trước.")
        items = [self.items[u][1] for u in uids if u in self.items]
        if not items:
            raise RuntimeError("Không tìm thấy clip nào để đưa vào timeline (đã bấm 'Đọc clip' chưa?).")
        try:
            pname = self.project.GetName() or "project"
        except Exception:                                     # noqa: BLE001
            pname = "project"
        stamp = datetime.datetime.now().strftime("%d.%m %Hh%M")
        name = re.sub(r'[\\/:*?"<>|&]', " ", "Rough Cut sao %s %s" % (pname, stamp))   # bỏ ký tự hay làm DaVinci từ chối tên
        pool = self.pool
        tl, why = None, []
        try:
            tl = pool.CreateTimelineFromClips(name, items)
        except Exception as e:                                # noqa: BLE001
            why.append("CreateTimelineFromClips lỗi: %s" % e)
        if not tl:
            why.append("CreateTimelineFromClips trả rỗng")
            try:
                tl = pool.CreateEmptyTimeline(name + " b")
                if tl:
                    ok = pool.AppendToTimeline(items)
                    if not ok:
                        why.append("AppendToTimeline không thêm được clip nào")
                        ok = pool.AppendToTimeline([{"mediaPoolItem": x} for x in items])
                        if not ok:
                            why.append("AppendToTimeline (dạng dict) cũng không thêm được")
                            tl = None
                else:
                    why.append("CreateEmptyTimeline trả rỗng")
            except Exception as e:                            # noqa: BLE001
                why.append("cách 2 lỗi: %s" % e)
                tl = None
        if not tl:
            raise RuntimeError("DaVinci không tạo được timeline mới (%d clip). Chi tiết: %s. "
                               "Hãy thử chuyển sang trang Edit hoặc Media của DaVinci rồi bấm lại." % (len(items), "; ".join(why)))
        self.post("timeline_appended", (len(items), True))

    def run(self):
        while True:
            job, arg = self.jobs.get()
            if job == "quit":
                return
            try:
                self.connect()
                getattr(self, "do_" + job)(arg)
            except Exception as e:                            # noqa: BLE001
                if "kết nối" in str(e) or "project khác" in str(e):
                    self.project = None
                self.post("error", (job, str(e)))
