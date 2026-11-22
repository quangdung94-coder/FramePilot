"""
troly_resolve.py - Cầu nối DaVinci cho Trợ lý File Quay (ADR-0009). Mọi lệnh gọi DaVinci chạy trong MỘT luồng nền
(giống panel_common.ResolveWorker), giao diện chỉ gửi việc và nhận kết quả qua hàng đợi.

Việc ĐỌC: danh sách bin, clip của một bin (gồm mọi bin con), thuộc tính từng clip.
Việc GHI (chỉ khi người dựng bấm "Áp dụng vào Media Pool", ADR-0009):
  - tạo bin con bên trong bin nguồn (01_Rước dâu, 01_Rước dâu/Decor, ...): AddSubFolder;
  - CHUYỂN clip vào bin đó: MoveClips. Không xóa clip, không đổi tên, không đụng file trên ổ, màu.
  - GHI In/Out của clip nguồn (SetMarkInOut) CHỈ khi người dựng bấm nút, luôn sao lưu In/Out cũ trước và có Hoàn tác (ADR-0016).
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


def is_audio_only(props):
    t = props.get("Type") or ""
    return "Audio" in t and "Video" not in t and "Timeline" not in t and "Compound" not in t


def walk_bins(folder, path, out):
    n = 0
    for c in folder.GetClipList() or []:
        if is_video({"Type": c.GetClipProperty("Type") or ""}):
            n += 1
    out.append({"path": path, "name": folder.GetName(), "n": n})
    for sf in folder.GetSubFolderList() or []:
        walk_bins(sf, path + "/" + sf.GetName(), out)
    return out


def segs_all(v1, v2):
    return list(v1) + list(v2)


def tc_size(res):
    import re
    m = re.match(r"^\s*(\d+)\s*[xX]\s*(\d+)\s*$", str(res or ""))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


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
        self.pm = None
        self.project_uid = ""
        self.items = {}                   # uid -> (đường bin, MediaPoolItem) của lần đọc gần nhất
        self.audio_items = {}             # uid -> (đường bin, MediaPoolItem) các file audio rời (Tascam/Zoom/Mixer) trong Media Pool
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
        pm = resolve.GetProjectManager()
        p = pm.GetCurrentProject()
        if not p or p.GetName() != self.project_name:
            raise RuntimeError("DaVinci đang mở project khác. Hãy mở project %s." % self.project_name)
        self.pm = pm
        self.project = p
        try:                                          # id bền của project (không đổi khi đổi tên project)
            self.project_uid = str(p.GetUniqueId() or "")
        except Exception:                             # noqa: BLE001  bản DaVinci/giả lập không có hàm này
            self.project_uid = ""

    def _require_current(self):
        """Việc GHI chỉ chạy khi DaVinci vẫn đang mở đúng project của panel (người dựng có thể đã đổi project sau khi mở panel;
        khi đó các đối tượng đã đọc thuộc project cũ, ghi vào là sai chỗ)."""
        cur = self.pm.GetCurrentProject() if self.pm is not None else None
        if not cur or cur.GetName() != self.project_name:
            self.project = None                           # lần sau kết nối lại và kiểm lại
            raise RuntimeError("DaVinci đang mở project khác. Hãy mở project %s." % self.project_name)

    @property
    def pool(self):
        return self.project.GetMediaPool()

    @staticmethod
    def _same_tl(a, b):
        if a is None or b is None:
            return False
        if a is b:
            return True
        try:
            ua, ub = a.GetUniqueId(), b.GetUniqueId()
            if ua and ub:
                return ua == ub
        except Exception:                                     # noqa: BLE001  bản giả lập không có GetUniqueId
            pass
        try:
            return a.GetName() == b.GetName()
        except Exception:                                     # noqa: BLE001
            return False

    def _make_current(self, tl):
        """AppendToTimeline của DaVinci thêm clip vào timeline HIỆN TẠI. Trước khi gọi nó phải chắc timeline hiện tại là timeline MỚI vừa tạo,
        không thì clip bị chèn vào timeline đang dựng của người dùng. True chỉ khi đọc lại thấy đúng."""
        try:
            self.project.SetCurrentTimeline(tl)
        except Exception:                                     # noqa: BLE001
            pass
        try:
            return self._same_tl(self.project.GetCurrentTimeline(), tl)
        except Exception:                                     # noqa: BLE001
            return False

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
        self.post("tl_fps", self._read_tl_fps())
        # Quét toàn bộ Media Pool lấy các file audio rời (Tascam / Zoom / Mixer WAV/MP3) để Bước 4 tự chọn & sync
        audio_list, self.audio_items = [], {}
        try:
            all_rows = walk_clips(root, root.GetName(), [])
            seen_a = set()
            for bp_a, mpi_a in all_rows:
                pr_a = mpi_a.GetClipProperty() or {}
                if not is_audio_only(pr_a):
                    continue
                uid_a = mpi_a.GetUniqueId()
                if uid_a in seen_a:
                    continue
                seen_a.add(uid_a)
                self.audio_items[uid_a] = (bp_a, mpi_a)
                path_a = pr_a.get("File Path") or ""
                audio_list.append({
                    "uid": uid_a,
                    "name": pr_a.get("File Name") or pr_a.get("Clip Name") or "",
                    "path": path_a,
                    "rel": tc.rel_path(path_a),
                    "dur": tc.clip_duration_s(pr_a),
                    "fps": float(pr_a.get("FPS") or 0) or None,
                    "frames": int(float(pr_a.get("Frames") or 0)),
                    "bin_path": bp_a,
                })
        except Exception:                                     # noqa: BLE001
            pass
        self.post("audio_clips", audio_list)
        self.post("clips", (bin_path, clips))

    def _read_tl_fps(self):
        """fps timeline của project (cho "Slow mượt tự tính"); không đọc được thì None (panel dùng 25)."""
        try:
            v = float(self.project.GetSetting("timelineFrameRate"))
            return v if v > 0 else None
        except Exception:                                     # noqa: BLE001
            return None

    # --- ĐỌC TIMELINE (ADR-0032, chỉ ĐỌC) ---------------------------------------
    def do_tl_list(self, _):
        """Tên các timeline của project + timeline đang mở. Chỉ đọc."""
        names, cur = [], None
        try:
            n = int(self.project.GetTimelineCount() or 0)
            for i in range(1, n + 1):
                t = self.project.GetTimelineByIndex(i)
                if t is not None:
                    names.append(t.GetName())
            c = self.project.GetCurrentTimeline()
            cur = c.GetName() if c else None
        except Exception:                                      # noqa: BLE001  bản giả lập / DaVinci không cho đọc danh sách timeline
            pass
        self.post("timelines", (names, cur))

    def do_tl_read(self, name):
        """Đọc vị trí, độ dài, track của từng clip trên timeline `name` (khung hình của timeline). KHÔNG ghi gì.
        DaVinci chỉ cho đọc item của timeline đang mở, nên nếu timeline khác đang mở thì mở timeline cần đọc rồi TRẢ LẠI timeline cũ."""
        prev = self.project.GetCurrentTimeline()
        tl = None
        for i in range(1, int(self.project.GetTimelineCount() or 0) + 1):
            t = self.project.GetTimelineByIndex(i)
            if t is not None and t.GetName() == name:
                tl = t
                break
        if tl is None:
            raise RuntimeError("Không thấy timeline %s trong project." % name)
        switched = not self._same_tl(prev, tl)
        try:
            if switched:
                self.project.SetCurrentTimeline(tl)
            raw = self._read_timeline(tl, name)
        finally:
            if switched and prev is not None:
                try:
                    self.project.SetCurrentTimeline(prev)
                except Exception:                              # noqa: BLE001
                    pass
        self.post("tl_data", raw)

    def _read_timeline(self, tl, name):
        try:
            fps = float(tl.GetSetting("timelineFrameRate"))
        except Exception:                                      # noqa: BLE001
            fps = 25.0
        start0 = int(tl.GetStartFrame() or 0)
        cache = {}

        def info(mp):
            uid = mp.GetUniqueId()
            if uid not in cache:
                pr = mp.GetClipProperty() or {}
                typ = str(pr.get("Type") or "")
                res = str(pr.get("Resolution") or "")
                try:
                    rot = int(float(pr.get("Rotation") or pr.get("Video Rotation") or 0))
                except (TypeError, ValueError):
                    rot = 0
                m = tc_size(res)
                cache[uid] = {"uid": uid, "name": str(pr.get("File Name") or pr.get("Clip Name") or ""), "w": m[0], "h": m[1], "rot": rot,
                              "audio_only": typ.lower().startswith("audio") and "video" not in typ.lower()}
            return cache[uid]

        tracks, n_items = [], 0
        for kind in ("video", "audio"):
            for idx in range(1, int(tl.GetTrackCount(kind) or 0) + 1):
                items = []
                for it in tl.GetItemListInTrack(kind, idx) or []:
                    mp = it.GetMediaPoolItem()
                    if mp is None:                              # chuyển cảnh, tiêu đề, generator: không phải clip nguồn
                        continue
                    d = dict(info(mp))
                    d["start"] = int(it.GetStart()) - start0
                    d["dur"] = int(it.GetDuration())
                    items.append(d)
                    n_items += 1
                    if n_items % 200 == 0:
                        self.post("progress", ("Đang đọc timeline", n_items, n_items + 200))
                tracks.append({"kind": kind, "idx": idx, "name": str(tl.GetTrackName(kind, idx) or ""), "items": items})
        return {"name": name, "fps": fps, "start": 0, "tracks": tracks}

    # --- GHI (ADR-0009) -----------------------------------------------------
    def do_apply(self, arg):
        """arg = (bin nguồn, {uid: [tên bin cấp 1, tên bin cấp 2] }). Clip có [] thì để nguyên chỗ cũ.
        Trả nhật ký [(uid, bin cũ, bin mới)] chỉ gồm các clip ĐÃ chuyển thật."""
        src_path, targets = arg
        self._require_current()
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
            try:
                for name in parts:
                    folder = ensure_sub(self.pool, folder, name)
                    if folder is None:
                        break
            except Exception:                                  # noqa: BLE001
                folder = None
            if folder is None:                                 # không tạo được bin: tính lỗi nhóm này, KHÔNG bỏ nhật ký các nhóm đã chuyển
                failed += len(uids)
                continue
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
        self._require_current()
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

    def do_save_project(self, box):
        """Lưu project DaVinci đang mở (ProjectManager.SaveProject). CHỈ gọi từ "Phân tích cả project" khi người dựng tick tắt máy
        (quy tắc ADR-0017). box = {'event': threading.Event, 'ok': bool}; luôn đặt event để bên gọi không treo."""
        try:
            self.connect()
            p = self.pm.GetCurrentProject()
            if not p or p.GetName() != self.project_name:
                raise RuntimeError("DaVinci đang mở project khác, không lưu.")
            box["ok"] = bool(self.pm.SaveProject())
            if not box["ok"]:
                self.post("error", ("save_project", "DaVinci trả False khi lưu project."))
        except Exception as e:                                # noqa: BLE001
            box["ok"] = False
            self.post("error", ("save_project", str(e)))
        finally:
            box["event"].set()

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
        self._require_current()
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
                if tl and not self._make_current(tl):
                    why.append("đã tạo timeline rỗng \"%s b\" nhưng không chuyển được sang nó, KHÔNG thêm clip để khỏi chèn nhầm vào timeline "
                               "đang mở (bạn xóa tay timeline rỗng đó nếu thấy)" % name)
                    tl = None
                elif tl:
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

    def do_create_cut_timeline(self, arg):
        """Bước 5 (ADR-0013 bản 3): tạo MỘT timeline MỚI. arg = (tên, [đoạn]); đoạn = dict(uid, a, b (frame GỐC, từ đầu file), pct (tốc độ %),
        track 'V1'|'V2', start_f (frame trên timeline, tính từ đầu timeline), mute). Mỗi đoạn là clip con, KHÔNG ghi In/Out lên clip gốc.
        Cách làm (ĐÃ THỬ trên project thử 18/11/2026, xem ADR-0013):
          1) V1: CreateTimelineFromClips ở 100% (trả rỗng thì CreateEmptyTimeline + AppendToTimeline), rồi từng clip Slow: SetSpeed(Percentage,
             RippleTimeline=True) theo thứ tự -> clip sau tự bị đẩy ra sau, liền nhau không chồng không hở. (RippleTimeline=False KHÔNG dùng được:
             clip giữ nguyên độ dài, DaVinci cắt bớt phần source.)
          2) V2: AppendToTimeline với trackIndex=2 + recordFrame (tiếng vào A2); clip Slow ở V2 thì KHÓA V1/A1 rồi SetSpeed ripple True
             (không khóa thì ripple cắt đôi và đẩy V1).
          3) Tắt tiếng: SetCurrentTimeline rồi SetClipEnabled(False) trên clip TIẾNG của khối (A1 cho V1, A2 cho V2). Không đụng A3 trở lên.
        Cuối cùng ĐỌC LẠI vị trí đầu/cuối từng clip để kiểm V1 liền nhau, V2 đúng chỗ. Không xóa/sửa timeline có sẵn, không render.
        Sau khi tạo kiểm lại: số timeline tăng đúng 1 và các timeline cũ còn nguyên tên."""
        name, segs = arg
        self._require_current()
        if not self.items:
            raise RuntimeError("Hãy bấm 'Đọc clip' trước.")
        segs = [dict(x) if isinstance(x, dict) else {"uid": x[0], "a": x[1], "b": x[2], "pct": 100.0, "track": "V1", "start_f": 0, "mute": False}
                for x in segs]
        segs = [x for x in segs if x["uid"] in self.items]
        if not segs:
            raise RuntimeError("Không có đoạn nào để đưa lên timeline.")
        def _t_idx(x):
            tr = str(x.get("track") or "V1").upper()
            if tr.startswith("V") and tr[1:].isdigit():
                return max(1, int(tr[1:]))
            return 1

        v1 = [x for x in segs if _t_idx(x) == 1]
        v_more = sorted([x for x in segs if _t_idx(x) >= 2], key=lambda x: (_t_idx(x), x.get("start_f", 0)))

        # Nếu là chế độ xếp theo track máy (multi_track: A->V1, B->V2, C->V3, D->V4) hoặc không có clip V1,
        # đặt tất cả clip bằng recordFrame đúng mốc start_f thay vì CreateTimelineFromClips (vốn ép V1 dính liền từ 0).
        v1_gapped = (not v1) or any(x.get("multi_track") for x in segs)

        def info(x):
            return {"mediaPoolItem": self.items[x["uid"]][1], "startFrame": int(x["a"]), "endFrame": int(x["b"])}

        infos = [] if v1_gapped else [info(x) for x in v1]
        # Chia danh sách V1 thành các lô KHÔNG lặp mediaPoolItem trong cùng một lời gọi:
        # DaVinci Resolve 21 có lỗi C++ trong CreateTimelineFromClips khi cùng một mediaPoolItem xuất hiện 2 lần
        # (ví dụ clip cắt 2 khúc Shift+I/O): nó làm lệch toàn bộ các clip phía sau sang phải 1 vị trí với LeftOffset âm
        # khiến cả cụm cuối bị đứng 1 tấm hình! Tách lô theo uid duy nhất + AppendToTimeline tránh triệt để lỗi này.
        v1_chunks = []
        if infos:
            cur_ch, seen_u = [], set()
            for x_seg, ci_seg in zip(v1, infos):
                u_seg = x_seg["uid"]
                if u_seg in seen_u and cur_ch:
                    v1_chunks.append(cur_ch)
                    cur_ch, seen_u = [], set()
                cur_ch.append(ci_seg)
                seen_u.add(u_seg)
            if cur_ch:
                v1_chunks.append(cur_ch)
        first_chunk = v1_chunks[0] if v1_chunks else []
        rest_chunks = v1_chunks[1:] if len(v1_chunks) > 1 else []
        before = self._timeline_names()
        pool = self.pool
        tl, why, created_empty = None, [], False
        if first_chunk:
            try:
                tl = pool.CreateTimelineFromClips(name, first_chunk)
            except Exception as e:                            # noqa: BLE001
                why.append("CreateTimelineFromClips lỗi: %s" % e)
            if not tl:
                why.append("CreateTimelineFromClips trả rỗng")
        if not tl:
            try:
                tl = pool.CreateEmptyTimeline(name)
                created_empty = bool(tl)
                if tl and (first_chunk or rest_chunks or v_more or v1_gapped) and not self._make_current(tl):
                    why.append("không chuyển được sang timeline mới, KHÔNG thêm đoạn để khỏi chèn nhầm vào timeline đang mở")
                    tl = None
                elif tl and first_chunk and not pool.AppendToTimeline(first_chunk):
                    why.append("AppendToTimeline không thêm được đoạn nào")
                    tl = None
                elif not tl:
                    why.append("CreateEmptyTimeline trả rỗng")
            except Exception as e:                            # noqa: BLE001
                why.append("cách 2 lỗi: %s" % e)
                tl = None
        if not tl:
            extra = " Một timeline rỗng có thể đã được tạo, bạn xóa tay nếu thấy (Trợ lý không xóa timeline)." if created_empty else ""
            raise RuntimeError("DaVinci không tạo được timeline mới (%d đoạn). Chi tiết: %s.%s" % (len(segs), "; ".join(why), extra))
        # Chèn nối tiếp các lô còn lại (khi có clip cắt nhiều khúc Shift+I/O) và chèn bù nếu DaVinci rớt đoạn nào
        rescue_msgs = []
        if infos and not v1_gapped:
            def _append_one(ci_item, pos_1based):
                ci = dict(ci_item)
                ok_one = False
                try:
                    ok_one = bool(pool.AppendToTimeline([ci]))
                except Exception:                             # noqa: BLE001
                    ok_one = False
                if not ok_one and ci["endFrame"] > ci["startFrame"] + 2:
                    ci2 = dict(ci)
                    ci2["endFrame"] = ci["endFrame"] - 2
                    try:
                        ok_one = bool(pool.AppendToTimeline([ci2]))
                    except Exception:                         # noqa: BLE001
                        ok_one = False
                if not ok_one:
                    rescue_msgs.append("Không chèn được đoạn V1 số %d (frame %d–%d)." % (pos_1based, ci["startFrame"], ci["endFrame"]))
                return ok_one

            if rest_chunks:
                if self._make_current(tl):
                    offset = len(first_chunk)
                    for ch in rest_chunks:
                        # Đoạn đầu mỗi lô sau chính là khúc lặp Shift+I/O -> chèn riêng 1 đoạn rồi mới chèn phần còn lại (tất cả uid duy nhất)
                        _append_one(ch[0], offset + 1)
                        tail = ch[1:]
                        if tail:
                            try:
                                before_n = len(tl.GetItemListInTrack("video", 1) or [])
                            except Exception:                 # noqa: BLE001
                                before_n = None
                            ok_tail = False
                            try:
                                ok_tail = bool(pool.AppendToTimeline(tail))
                            except Exception:                 # noqa: BLE001
                                ok_tail = False
                            added_n = len(tail) if ok_tail else 0
                            if before_n is not None:
                                try:
                                    after_n = len(tl.GetItemListInTrack("video", 1) or [])
                                    added_n = max(0, after_n - before_n)
                                except Exception:             # noqa: BLE001
                                    pass
                            for k_rem in range(added_n, len(tail)):
                                _append_one(tail[k_rem], offset + 1 + k_rem + 1)
                        offset += len(ch)
                else:
                    rescue_msgs.append("Không chuyển được sang timeline mới để chèn %d đoạn V1 còn lại." % (len(infos) - len(first_chunk)))
            try:
                got_v1 = len(tl.GetItemListInTrack("video", 1) or [])
            except Exception:                                 # noqa: BLE001
                got_v1 = len(infos)
            if got_v1 < len(infos):
                if self._make_current(tl):
                    for idx_rem in range(got_v1, len(infos)):
                        _append_one(infos[idx_rem], idx_rem + 1)
                else:
                    rescue_msgs.append("DaVinci chỉ thêm %d/%d đoạn V1 và không chuyển được sang timeline mới để chèn bù." % (got_v1, len(infos)))
        if v1_gapped:
            v1_arg, v_more_arg = [], sorted(segs, key=lambda x: (_t_idx(x), x.get("start_f", 0)))
        else:
            v1_arg, v_more_arg = v1, v_more
        notes = self._finish_layout(tl, v1_arg, v_more_arg, info, _t_idx, _v1_gapped=v1_gapped)
        if rescue_msgs:
            notes["msgs"] = rescue_msgs + notes["msgs"]
            notes["layout_ok"] = False
        after = self._timeline_names()
        res = {"name": name, "n": len(segs), "before": None if before is None else len(before), "after": None if after is None else len(after),
               "old_intact": None, "verified": False, "layout_ok": notes["layout_ok"], "layout_msgs": notes["msgs"], "n_slow": notes["n_slow"],
               "n_muted": notes["n_muted"], "n_v2": len(v_more), "n_rec_a2": notes.get("n_rec_a2", 0)}
        if before is not None and after is not None:
            res["old_intact"] = all(after.count(n) >= before.count(n) for n in set(before))
            res["verified"] = len(after) == len(before) + 1 and bool(res["old_intact"]) and name in after
        self.post("cut_timeline_created", res)

    def _finish_layout(self, tl, v1, v2, info, _t_idx=None, _v1_gapped=False):
        """Slow ở V1, khối V2..V4, tắt tiếng, đọc lại kiểm (xem do_create_cut_timeline). Mọi lỗi nhỏ được ghi lại, không làm hỏng timeline đã tạo."""
        if _t_idx is None:
            _t_idx = lambda x: 2 if str(x.get("track") or "").upper() == "V2" else 1
        notes = {"layout_ok": None, "msgs": [], "n_slow": 0, "n_muted": 0, "n_rec_a2": 0}
        has_rec = any(x.get("rec_uid") for x in v1)
        need = any(float(x.get("pct", 100)) < 99.95 for x in segs_all(v1, v2)) or v2 or any(x.get("mute") for x in segs_all(v1, v2)) or has_rec
        if not need:
            return notes
        pool = self.pool
        is_cur = self._make_current(tl)
        if not is_cur:
            notes["msgs"].append("Không đặt được timeline mới làm timeline hiện tại: bỏ qua V2 và tắt tiếng (để khỏi ghi nhầm vào timeline đang mở).")
            notes["layout_ok"] = False
            v2 = []
        # 1) V1: Slow lần lượt, ripple
        for i, x in enumerate(v1):
            pct = float(x.get("pct", 100))
            if pct >= 99.95:
                continue
            try:
                its = tl.GetItemListInTrack("video", 1) or []
                ok = its[i].SetSpeed({"Percentage": pct, "RippleTimeline": True})
                notes["n_slow"] += 1 if ok else 0
                if not ok:
                    notes["msgs"].append("SetSpeed %g%% không được ở clip V1 số %d." % (pct, i + 1))
            except Exception as e:                            # noqa: BLE001
                notes["msgs"].append("SetSpeed lỗi ở clip V1 số %d: %s" % (i + 1, e))
        # 2) V2..V4
        v2_start = {}
        if v2:
            max_t = max(_t_idx(x) for x in v2)
            try:
                while int(tl.GetTrackCount("video")) < max_t:
                    tl.AddTrack("video")
                while int(tl.GetTrackCount("audio")) < max_t:
                    tl.AddTrack("audio", "stereo")
            except Exception as e:                            # noqa: BLE001
                notes["msgs"].append("Không thêm được track: %s" % e)
            s0 = tl.GetStartFrame()
            for j, x in enumerate(v2):
                ti = _t_idx(x)
                rec = int(s0) + int(x.get("start_f", 0))
                ci = info(x)
                ci.update({"trackIndex": ti, "recordFrame": rec})
                try:
                    pool.AppendToTimeline([ci])
                except Exception as e:                        # noqa: BLE001
                    notes["msgs"].append("Không đặt được clip V%d số %d: %s" % (ti, j + 1, e))
                    continue
                pct = float(x.get("pct", 100))
                its2 = [it for it in (tl.GetItemListInTrack("video", ti) or []) if int(it.GetStart()) == rec]
                if not its2:
                    notes["msgs"].append("Không thấy clip V%d số %d sau khi đặt." % (ti, j + 1))
                    continue
                if pct < 99.95:
                    locked = []
                    try:
                        for t in range(1, max_t + 1):
                            if t == ti:
                                continue
                            for kind in ("video", "audio"):
                                if tl.SetTrackLock(kind, t, True):
                                    locked.append((kind, t))
                        ok = its2[0].SetSpeed({"Percentage": pct, "RippleTimeline": True})
                        notes["n_slow"] += 1 if ok else 0
                        if not ok:
                            notes["msgs"].append("SetSpeed %g%% không được ở clip V%d số %d." % (pct, ti, j + 1))
                    except Exception as e:                    # noqa: BLE001
                        notes["msgs"].append("SetSpeed lỗi ở clip V%d số %d: %s" % (ti, j + 1, e))
                    finally:
                        for kind, t in locked:
                            try:
                                tl.SetTrackLock(kind, t, False)
                            except Exception:                 # noqa: BLE001
                                notes["msgs"].append("CẢNH BÁO: chưa mở khóa lại track %s%d, bạn mở tay." % ("V" if kind == "video" else "A", t))
                v2_start[j] = (ti, rec)
        # 2b) Chèn âm thanh Recorder rời đã sync xuống track A2 khớp vị trí từng clip V1 (mặc định A1 tắt, A2 bật để so sánh)
        rec_placed = {}
        if is_cur and has_rec and self.audio_items:
            try:
                while int(tl.GetTrackCount("audio") or 0) < 2:
                    tl.AddTrack("audio", "stereo")
                v1_now = tl.GetItemListInTrack("video", 1) or []
                for i, x in enumerate(v1):
                    ru = x.get("rec_uid")
                    if not ru or ru not in self.audio_items or i >= len(v1_now):
                        continue
                    pos_f = int(v1_now[i].GetStart())
                    ci_a = {
                        "mediaPoolItem": self.audio_items[ru][1],
                        "mediaType": 2,
                        "trackIndex": 2,
                        "recordFrame": pos_f,
                        "startFrame": int(x.get("rec_a", 0)),
                        "endFrame": int(x.get("rec_b", 1)),
                    }
                    try:
                        if pool.AppendToTimeline([ci_a]):
                            rec_placed[i] = pos_f
                            notes["n_rec_a2"] += 1
                    except Exception as e:                    # noqa: BLE001
                        notes["msgs"].append("Không đặt được tiếng Recorder A2 ở clip V1 số %d: %s" % (i + 1, e))
            except Exception as e:                            # noqa: BLE001
                notes["msgs"].append("Chèn tiếng Recorder A2 lỗi: %s" % e)
        # 3) tắt tiếng đúng khối (clip tiếng cùng vị trí với clip hình) + với clip có Recorder A2: mặc định A1 tắt, A2 bật (trừ khi anh tắt tiếng ở Bước 4/5)
        try:
            v1_items = tl.GetItemListInTrack("video", 1) or []
            a_by_track = {1: {int(it.GetStart()): it for it in (tl.GetItemListInTrack("audio", 1) or [])}}
            if rec_placed or v2:
                a_by_track[2] = {int(it.GetStart()): it for it in (tl.GetItemListInTrack("audio", 2) or [])}
            if v2:
                for ti in {_t_idx(x) for x in v2}:
                    a_by_track[ti] = {int(it.GetStart()): it for it in (tl.GetItemListInTrack("audio", ti) or [])}
            for i, x in enumerate(v1):
                if i >= len(v1_items):
                    continue
                st_f = int(v1_items[i].GetStart())
                if i in rec_placed:
                    # Có Recorder A2: mặc định A1 TẮT, A2 BẬT (nếu clip bị tắt tiếng bởi nút M / khối tắt tiếng -> tắt cả A1 lẫn A2)
                    a1_it = a_by_track[1].get(st_f)
                    if a1_it is not None:
                        a1_it.SetClipEnabled(False)
                    a2_it = a_by_track.get(2, {}).get(rec_placed[i])
                    if a2_it is not None:
                        a2_it.SetClipEnabled(not bool(x.get("mute")))
                    if x.get("mute"):
                        notes["n_muted"] += 1
                elif x.get("mute"):
                    ai = a_by_track[1].get(st_f)
                    if ai is not None and ai.SetClipEnabled(False):
                        notes["n_muted"] += 1
            for j, x in enumerate(v2):
                if x.get("mute") and j in v2_start:
                    ti, rec = v2_start[j]
                    ai = a_by_track.get(ti, {}).get(rec)
                    if ai is not None and ai.SetClipEnabled(False):
                        notes["n_muted"] += 1
        except Exception as e:                                # noqa: BLE001
            notes["msgs"].append("Tắt tiếng lỗi: %s" % e)
        # 4) đọc lại vị trí
        try:
            import troly_tl
            v1_rb = tl.GetItemListInTrack("video", 1) or []
            got = [("V1", int(it.GetStart()), int(it.GetEnd())) for it in v1_rb]
            if v2:
                for ti in sorted({_t_idx(x) for x in v2 if _t_idx(x) >= 2}):
                    got += [("V%d" % ti, int(it.GetStart()), int(it.GetEnd())) for it in (tl.GetItemListInTrack("video", ti) or [])]
            pl = [{"track": "V1"} for _ in v1] + [{"track": "V%d" % _t_idx(x)} for x in v2]
            if _v1_gapped:
                pl = [{"track": "V%d" % _t_idx(x), "gapped": True} for x in v2]
            notes["layout_ok"], more = troly_tl.verify_readback(pl, got)
            notes["msgs"] += more
            neg = []
            for idx_it, it in enumerate(v1_rb):
                if hasattr(it, "GetLeftOffset"):
                    try:
                        lo = int(it.GetLeftOffset())
                        if lo < 0:
                            neg.append("#%d %s (offset=%d)" % (idx_it + 1, it.GetName() if hasattr(it, "GetName") else "", lo))
                    except Exception:                         # noqa: BLE001
                        pass
            if neg:
                notes["layout_ok"] = False
                notes["msgs"].append("CẢNH BÁO: %d clip V1 có LeftOffset âm (có thể đứng hình): %s." % (len(neg), ", ".join(neg[:5])))
        except Exception as e:                                # noqa: BLE001
            notes["msgs"].append("Không đọc lại được vị trí: %s" % e)
        return notes

    def _timeline_names(self):
        """Tên các timeline hiện có (để kiểm trước/sau), hoặc None nếu bản DaVinci/giả lập không hỏi được."""
        try:
            n = int(self.project.GetTimelineCount())
            return [self.project.GetTimelineByIndex(i).GetName() for i in range(1, n + 1)]
        except Exception:                                     # noqa: BLE001
            return None

    # --- GHI In/Out (ADR-0016) ----------------------------------------------------------------------------------
    @staticmethod
    def _read_vio(mpi):
        """(in, out) frame video đang đặt trong clip, hoặc (None, None)."""
        try:
            m = mpi.GetMarkInOut() or {}
        except Exception:                                     # noqa: BLE001
            return None, None
        v = m.get("video") if isinstance(m, dict) else None
        if not isinstance(v, dict) or v.get("in") is None or v.get("out") is None:
            return None, None
        return int(v["in"]), int(v["out"])

    def do_inout_write(self, arg):
        """arg = (data_root, tên project, [(uid, rel, in_frame, out_frame)]). Thứ tự an toàn:
        1) đọc In/Out CŨ của từng clip, 2) GHI FILE SAO LƯU (lỗi thì dừng, chưa đụng DaVinci), 3) SetMarkInOut từng clip,
        4) đọc lại đối chiếu. Chỉ gọi SetMarkInOut; không xóa clip, không đụng timeline/file/render."""
        root, pname, rows = arg
        self._require_current()
        if not self.items:
            raise RuntimeError("Hãy bấm 'Đọc clip' trước.")
        todo, old = [], []
        for uid, rel, a, b in rows:
            if uid not in self.items:
                continue
            oa, ob = self._read_vio(self.items[uid][1])
            old.append({"uid": uid, "rel": rel, "in": oa, "out": ob, "new_in": a, "new_out": b})
            todo.append((uid, a, b))
        if not todo:
            raise RuntimeError("Không có clip nào để ghi In/Out.")
        backup = tc.write_inout_backup(root, pname, old)
        if not tc.read_inout_backup(backup):
            raise RuntimeError("Không ghi được file sao lưu In/Out, chưa đụng DaVinci.")
        ok, bad, mismatch = [], [], []
        for n, (uid, a, b) in enumerate(todo):
            mpi = self.items[uid][1]
            try:
                r = mpi.SetMarkInOut(int(a), int(b), "all")
            except Exception as e:                            # noqa: BLE001
                r = False
                bad.append((uid, "lỗi: %s" % e))
                continue
            if not r:
                bad.append((uid, "DaVinci từ chối"))
                continue
            if self._read_vio(mpi) == (int(a), int(b)):
                ok.append(uid)
            else:
                mismatch.append((uid, self._read_vio(mpi)))
            if n % 20 == 0:
                self.post("progress", ("Đang ghi In/Out", n + 1, len(todo)))
        self.post("inout_written", {"backup": backup, "ok": ok, "bad": bad, "mismatch": mismatch, "total": len(todo)})

    def do_inout_restore(self, arg):
        """arg = đường dẫn file sao lưu. Khôi phục đúng In/Out cũ (cũ trống thì xóa In/Out) rồi đọc lại đối chiếu."""
        self._require_current()
        data = tc.read_inout_backup(arg)
        if not data or not isinstance(data.get("entries"), list):
            raise RuntimeError("Không đọc được file sao lưu In/Out.")
        if not self.items:
            raise RuntimeError("Hãy bấm 'Đọc clip' trước.")
        ok, bad, skipped = [], [], 0
        for e in data["entries"]:
            uid = e.get("uid")
            if uid not in self.items:
                skipped += 1
                continue
            mpi = self.items[uid][1]
            try:
                if e.get("in") is None or e.get("out") is None:
                    r = mpi.ClearMarkInOut("all")
                    good = self._read_vio(mpi) == (None, None)
                else:
                    r = mpi.SetMarkInOut(int(e["in"]), int(e["out"]), "all")
                    good = self._read_vio(mpi) == (int(e["in"]), int(e["out"]))
            except Exception as ex:                           # noqa: BLE001
                bad.append((uid, "lỗi: %s" % ex))
                continue
            if r and good:
                ok.append(uid)
            else:
                bad.append((uid, "không khôi phục khớp"))
        self.post("inout_restored", {"backup": arg, "ok": ok, "bad": bad, "skipped": skipped})

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
