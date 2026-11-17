r"""
troly_api.py - Phần CHỨC NĂNG của giao diện HTML "Trợ lý File Quay" (ADR-0010). Không vẽ gì, không import pywebview.

Giao diện HTML (src\troly_web\) gọi các hàm công khai của lớp TrolyApi qua pywebview (window.pywebview.api.<tên>).
Mỗi hàm trả về dữ liệu JSON (dict/list/str/số). Việc lâu (đọc DaVinci, áp dụng, thumbnail) chạy nền và báo về giao
diện qua hàm emit(loại, dữ liệu) (bản chạy thật: window.evaluate_js("onEvent(...)")).

Logic chép từ bản CustomTkinter cũ (đã bỏ, xem docs/adr/0011). Mọi lệnh gọi DaVinci vẫn ở troly_resolve.TrolyWorker.
Thuộc tính và hàm bắt đầu bằng "_" KHÔNG lộ ra JavaScript (quy ước của pywebview).
"""
import base64
import collections
import datetime
import os
import queue
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import troly_core as tc           # noqa: E402
import troly_resolve as tr        # noqa: E402
import troly_thumbs as tt         # noqa: E402

SUB_COLORS = ["#4FC1A6", "#E88AB0", "#F2A33A", "#5B9BF5", "#C98BE0", "#EF7D65", "#A9CF62", "#E0B860", "#7FB7E8",
              "#8A8A94"]
THUMB_INFLIGHT = 8


def _data_uri(path):
    try:
        with open(path, "rb") as f:
            return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return None


class TrolyApi(object):
    def __init__(self, project, data_root, emit=None, resolve_factory=None, start_worker=True, thumb_workers=4):
        self._project, self._root = project, data_root
        self._emit_fn = emit or (lambda kind, data: None)
        self._plan = tc.load_plan(data_root, project)
        self._note = self._plan.pop("_note", None)      # ghi chú khi phải khôi phục file kế hoạch (hiện lúc kết nối)
        self._autoload = bool(self._plan.get("source_bin"))   # mở lại panel: tự nạp clip của bin nguồn đã dùng
        self._new_n, self._gone_n = 0, 0
        self._clips, self._by_uid, self._day0 = [], {}, None
        self._assign = {}
        self._bins = []
        self._busy = False
        self._lock = threading.RLock()
        self._q = queue.Queue()
        self._worker = tr.TrolyWorker(project, self._q, resolve_factory=resolve_factory)
        self._thumbs = tt.ThumbMaker(os.path.join(data_root, "cache", "troly_thumbs", tc._safe(project)),
                                     workers=thumb_workers)
        self._thumb_done = {}             # uid -> (đường dẫn jpg | None, ghi chú)
        self._inflight = set()
        self._want = []                   # uid ưu tiên làm thumbnail trước (đang thấy trên màn hình)
        self._save_timer = None
        self._speech_st, self._speech_run, self._speech_last = None, None, None
        self._closed = False
        self._started = start_worker
        if start_worker:
            self._worker.start()
            threading.Thread(target=self._pump_loop, daemon=True).start()

    # ------------------------------------------------------------------ nội bộ
    def _emit(self, kind, data=None):
        if self._closed:
            return
        try:
            self._emit_fn(kind, data)
        except Exception:                 # noqa: BLE001  cửa sổ đã đóng
            pass

    def _pump_loop(self):
        while True:
            kind, data = self._q.get()
            self._handle(kind, data)

    def _drain(self):
        """Dùng trong test: xử lý hết kết quả của luồng nền ngay tại chỗ."""
        while not self._q.empty():
            self._handle(*self._q.get())

    def _handle(self, kind, data):
        with self._lock:
            if kind == "bins":
                self._on_bins(*data)
            elif kind == "progress":
                what, i, n = data
                self._emit("progress", {"text": "%s %d/%d..." % (what, i, n), "frac": i / float(max(1, n))})
            elif kind == "clips":
                self._on_clips(*data)
            elif kind == "applied":
                self._on_applied(*data)
            elif kind == "undone":
                self._on_undone(*data)
            elif kind == "timeline_appended":
                self._busy = False
                n, created = data
                msg = "Đã đưa %d clip có sao ★ vào %s của DaVinci." % (n, "timeline mới" if created else "timeline hiện tại")
                self._emit("status", {"text": msg, "kind": "ok"})
            elif kind == "error":
                self._busy = False
                job, msg = data
                self._emit("status", {"text": "Lỗi (%s): %s" % (job, msg), "kind": "error"})

    def _save_soon(self):
        """Giữ tên cũ cho các chỗ gọi: nay LƯU NGAY (ghi nguyên tử, giữ .bak). Kế hoạch chỉ vài trăm KB nên ghi mỗi lần
        đổi nhãn/giờ/chọn tay không đáng kể, đổi lại không bao giờ mất thao tác sát lúc tắt."""
        self._save_now()

    def _save_now(self):
        with self._lock:
            try:
                tc.save_plan(self._root, self._plan)
            except OSError as e:
                self._emit("status", {"text": "Không lưu được kế hoạch: %s" % e, "kind": "error"})

    @property
    def _stages(self):
        return self._plan["stages"]

    def _recount(self):
        self._assign = tc.assign(self._clips, self._stages, self._day0, self._plan["offsets"],
                                 manual=self._plan.get("manual")) if self._day0 else {}

    def _label_in_stage(self, c, si):
        if si is None or si >= len(self._stages):
            return None
        s = self._stages[si]
        lab = tc.label_of(self._plan, c)
        return lab["bin"] if lab and lab.get("stage") == s["name"] and lab.get("bin") in s["bins"] else None

    # ------------------------------------------------------------------ trạng thái cho giao diện
    def state(self):
        """Toàn bộ dữ liệu giao diện cần để vẽ lại (giai đoạn, clip, nhãn, đếm)."""
        with self._lock:
            self._recount()
            cnt, outside = tc.counts(self._assign, len(self._stages))
            stages = []
            for i, s in enumerate(self._stages):
                # MỌI số đếm và lưới xem đều lấy từ cùng các danh sách uid này (đúng thứ tự giờ quay), nên số cạnh
                # mỗi bin con luôn bằng số clip lưới hiện khi bấm vào bin đó.
                in_stage = [c for c in self._clips if self._assign.get(c.uid) == i]
                by_bin = collections.defaultdict(list)
                for c in in_stage:
                    by_bin[self._label_in_stage(c, i)].append(c.uid)
                none = by_bin.get(None, [])
                stages.append({"name": s["name"], "start": s["start"], "end": s["end"], "color": s["color"],
                               "count": cnt[i], "bin": "%02d_%s" % (i + 1, s["name"]),
                               "range": "%s – %s" % (tc.fmt_min(s["start"]), tc.fmt_min(s["end"])),
                               "uids": [c.uid for c in in_stage], "none": none,
                               "done": len(in_stage) - len(none),
                               "bins": [{"name": b, "key": str(j + 1) if j < 9 else "",
                                         "color": SUB_COLORS[j % len(SUB_COLORS)], "uids": by_bin.get(b, []),
                                         "count": len(by_bin.get(b, []))}
                                        for j, b in enumerate(s["bins"])]})
            clips = []
            for c in self._clips:
                m = tc.clip_minutes(c, self._day0, self._plan["offsets"]) if self._day0 else None
                si = self._assign.get(c.uid)
                lb = self._label_in_stage(c, si)
                fps = c.fps or 25.0
                in_s = round(c.mark_in / fps, 2) if c.mark_in is not None else None
                out_s = round(c.mark_out / fps, 2) if c.mark_out is not None else None
                sug = tc.suggest_inout(c.dur, lb)
                clips.append({"uid": c.uid, "name": c.name, "m0": m[0] if m else None, "m1": m[1] if m else None,
                              "time": c.t_start.strftime("%H:%M:%S") if c.t_start else "--:--:--",
                              "dur": c.dur or 0, "stage": si, "label": lb,
                              "manual": bool(tc.manual_of(self._plan, c)), "camera": c.camera, "src": c.t_src, "lut": c.lut or "", "bin_path": c.bin_path,
                              "thumb": c.uid in self._thumb_done and bool(self._thumb_done[c.uid][0]),
                              "in_s": in_s, "out_s": out_s, "sug": sug,
                              "star": tc.is_starred(self._plan, c)})
            gap = None
            if self._day0 and self._clips:
                gs = tc.gaps(self._clips, self._day0, self._plan["offsets"])
                if gs:
                    g = max(gs)
                    gap = {"a": g[1], "b": g[2], "text": "%s – %s" % (tc.fmt_min(g[1]), tc.fmt_min(g[2]))}
            cams = collections.Counter(c.camera for c in self._clips)
            moves = self._plan.get("moves") or []
            return {"project": self._project, "bin": self._plan.get("source_bin"),
                    "day0": self._day0.strftime("%d/%m/%Y") if self._day0 else None,
                    "n": len(self._clips), "new_n": self._new_n, "gone_n": self._gone_n,
                    "n_manual": sum(1 for c in self._clips if tc.manual_of(self._plan, c)),
                    "n_starred": sum(1 for c in self._clips if tc.is_starred(self._plan, c)),
                    "stages": stages, "outside": outside, "clips": clips, "gap": gap,
                    "cameras": [{"cam": k, "n": v, "off": self._plan["offsets"].get(k, 0)} for k, v in
                                cams.most_common()],
                    "template": self._plan.get("template") or tc.DEFAULT_TEMPLATE,
                    "templates": list(tc.templates(self._root)),
                    "moves": [{"at": m.get("at", "")[:16].replace("T", " "), "n": len(m["log"])} for m in moves],
                    "busy": self._busy,
                    "thumbs": {"done": sum(1 for v in self._thumb_done.values() if v[0]),
                               "bad": sum(1 for v in self._thumb_done.values() if not v[0])}}

    # ------------------------------------------------------------------ bin + clip
    def init(self):
        """Giao diện đã sẵn sàng: đọc danh sách bin (chạy nền) và trả thông tin ban đầu."""
        self._worker.jobs.put(("bins", None))
        return {"project": self._project, "version": "v0.2.4", "parsed": self._parse_name(),
                "ui": self._plan.get("ui") or {}}

    def save_ui(self, ui):
        """Lưu trạng thái làm việc: bước đang ở, giai đoạn/bin con đang xem, thu phóng thanh giờ, ô lọc."""
        clean = {}
        try:
            clean["page"] = int(ui.get("page", 1))
            v = ui.get("view")
            if isinstance(v, (list, tuple)) and len(v) == 2:
                clean["view"] = [float(v[0]), float(v[1])]
            gs = ui.get("gStage")
            clean["gStage"] = int(gs) if gs is not None else None
            gb = ui.get("gSub")
            clean["gSub"] = str(gb) if gb is not None else None
            clean["onlyNew"] = bool(ui.get("onlyNew"))
        except (TypeError, ValueError):
            return False
        with self._lock:
            if self._plan.get("ui") == clean:
                return True
            self._plan["ui"] = clean
            self._save_now()
        return True

    def _parse_name(self):
        """'2026.10.17.LV_Ten' -> {'date': '17/10/2026', 'team': 'LV', 'name': 'Ten'} (không có thì trống)."""
        parts = self._project.split(".")
        if len(parts) >= 4 and all(p.isdigit() for p in parts[:3]):
            rest = ".".join(parts[3:])
            team, sep, name = rest.partition("_")
            if not sep:                                   # tên không có mã team (không có dấu _)
                team, name = "", rest
            return {"date": "%s/%s/%s" % (parts[2], parts[1], parts[0]), "team": team, "name": name}
        return {"date": "", "team": "", "name": self._project}

    def _adopt_by_uid(self):
        """Project đã ĐỔI TÊN trong DaVinci: kế hoạch cũ nằm ở file tên cũ. Khớp theo GetUniqueId của project (bền khi đổi
        tên) và chép sang tên mới; file cũ giữ nguyên (không xóa). Chỉ làm khi kế hoạch hiện tại còn trống."""
        uid = getattr(self._worker, "project_uid", "") or ""
        if not uid:
            return
        empty = not (self._plan["stages"] or self._plan["labels"] or self._plan.get("manual"))
        if empty and not self._plan.get("project_uid"):
            p, old = tc.find_plan_by_uid(self._root, uid, exclude_project=self._project)
            if old:
                old["project"] = self._project
                self._plan = tc.load_plan(self._root, self._project)
                self._plan.update({k: v for k, v in old.items() if not k.startswith("_")})
                self._plan["project"] = self._project
                self._autoload = bool(self._plan.get("source_bin"))
                self._note = "Project đã đổi tên: đã nhận lại kế hoạch cũ (file %s giữ nguyên)." % os.path.basename(p)
        if self._plan.get("project_uid") != uid:
            self._plan["project_uid"] = uid
            self._save_now()

    def _on_bins(self, bins, cur_name):
        self._bins = bins
        self._adopt_by_uid()
        want = self._plan.get("source_bin")
        pick = None
        if want and any(b["path"] == want for b in bins):
            pick = want
        if pick is None:
            pick = next((b["path"] for b in bins if b["name"] == cur_name and b["n"]), None)
        if pick is None and bins:
            pick = max(bins, key=lambda b: b["n"])["path"]
        # số clip gồm cả bin con (sau khi Áp dụng, clip nằm trong bin con nên bin nguồn tự nó có 0 clip)
        total = {b["path"]: sum(x["n"] for x in bins if x["path"] == b["path"] or x["path"].startswith(b["path"] + "/"))
                 for b in bins}
        self._emit("bins", {"bins": [{"path": b["path"], "n": total[b["path"]]} for b in bins], "pick": pick})
        if self._note:
            self._emit("status", {"text": self._note, "kind": "warn"})
            self._note = None
        if self._autoload and want and any(b["path"] == want for b in bins):
            self._autoload = False                        # chỉ tự nạp MỘT lần khi mở panel (không nạp lại sau Áp dụng/Hoàn tác)
            self._emit("status", {"text": "Đang nạp lại kế hoạch đã lưu của project (%s)..." % want, "kind": "info"})
            self._worker.jobs.put(("load", want))
            return
        self._autoload = False
        self._emit("status", {"text": "Đã kết nối DaVinci. Chọn bin nguồn rồi bấm \"Đọc clip\" (chỉ đọc).",
                              "kind": "info"})

    def load(self, bin_path):
        if not bin_path:
            return False
        self._emit("status", {"text": "Đang đọc clip của %s..." % bin_path, "kind": "info"})
        self._worker.jobs.put(("load", bin_path))
        return True

    def _on_clips(self, bin_path, clips):
        same = self._plan.get("source_bin") == bin_path
        self._plan["source_bin"] = bin_path
        self._clips = sorted(clips, key=lambda c: (c.t_start or datetime.datetime.max, c.name))
        self._by_uid = {c.uid: c for c in self._clips}
        d0 = self._plan.get("day0")
        if same and d0 and self._stages:
            self._day0 = datetime.date.fromisoformat(d0)
        else:
            self._day0 = tc.day0_of(self._clips)
            self._plan["day0"] = self._day0.isoformat()
            self._suggest(self._plan.get("template"))
        keys = {tc.clip_key(c) for c in self._clips}
        prev = set(self._plan.get("seen") or [])
        self._new_n = len(keys - prev) if (same and prev) else 0       # clip MỚI kể từ lần đọc trước (chưa phân loại)
        known = set(self._plan["labels"]) | set(self._plan.get("manual") or {})
        self._gone_n = len(known - keys) if same else 0                # nhãn của clip không còn trong Media Pool: bỏ qua
        self._plan["seen"] = sorted(keys)
        moved = sum(1 for c in self._clips if c.t_src == "modified")
        no_time = sum(1 for c in self._clips if not c.t_start)
        msg = "Đã đọc %d clip của %s." % (len(self._clips), bin_path)
        if self._new_n:
            msg += " %d clip MỚI chưa phân loại (kể từ lần đọc trước)." % self._new_n
        if self._gone_n:
            msg += " %d clip đã xếp không còn trong Media Pool (nhãn giữ trong file, không hiện)." % self._gone_n
        if moved:
            msg += " %d clip lấy giờ theo Date Modified (file đã chép lại)." % moved
        if no_time:
            msg += " %d clip không có giờ quay." % no_time
        self._save_soon()
        self._emit("state", self.state())
        self._emit("status", {"text": msg, "kind": "ok"})
        self._pump_thumbs()

    # ------------------------------------------------------------------ giai đoạn
    def _suggest(self, name):
        tpls = tc.templates(self._root)
        name = name if name in tpls else tc.DEFAULT_TEMPLATE
        self._plan["template"] = name
        self._plan["stages"] = tc.suggest_stages(self._clips, self._day0, tpls[name], self._plan["offsets"])

    def suggest(self, template_name):
        with self._lock:
            if not self._clips:
                return self.state()
            self._suggest(template_name)
            self._save_soon()
            return self.state()

    def set_stage(self, i, fields):
        """Sửa giai đoạn i. fields có thể gồm name, start/end (phút, số) hoặc start_txt/end_txt ('07:30'),
        bins (danh sách tên). Giờ sai -> trả {'error': ...}."""
        with self._lock:
            s = self._stages[i]
            try:
                ref = int(s["start"] // 1440)
                a = tc.parse_hhmm(fields["start_txt"], ref) if "start_txt" in fields else fields.get("start", s["start"])
                b = tc.parse_hhmm(fields["end_txt"], ref) if "end_txt" in fields else fields.get("end", s["end"])
                if "end_txt" in fields and b < a:
                    b += 1440                                     # qua nửa đêm
            except ValueError as e:
                return {"error": str(e)}
            s["start"], s["end"] = float(a), float(max(a, b))
            new = (fields.get("name") or "").strip()
            if new and new != s["name"]:
                for lab in list(self._plan["labels"].values()) + list((self._plan.get("manual") or {}).values()):
                    if lab.get("stage") == s["name"]:                 # nhãn + chọn tay đi theo tên giai đoạn mới
                        lab["stage"] = new
                s["name"] = new
            if "bins" in fields:
                bins = [str(x).strip().replace("/", "-") for x in fields["bins"]]
                s["bins"] = [x for x in bins if x and x != tc.OTHER_BIN] + [tc.OTHER_BIN]
            self._save_soon()
            return self.state()

    def add_stage(self):
        with self._lock:
            last = max([s["end"] for s in self._stages] or [8 * 60.0])
            self._stages.append(tc.make_stage("Giai đoạn %d" % (len(self._stages) + 1), last, last + 30, [],
                                              len(self._stages)))
            self._save_soon()
            return self.state()

    def del_stage(self, i):
        with self._lock:
            del self._stages[i]
            self._save_soon()
            return self.state()

    def set_offset(self, cam, seconds):
        with self._lock:
            try:
                v = float(str(seconds).replace(",", ".") or 0)
            except ValueError:
                return {"error": "Lệch giờ phải là số giây, ví dụ -30."}
            if v:
                self._plan["offsets"][cam] = v
            else:
                self._plan["offsets"].pop(cam, None)
            self._save_soon()
            return self.state()

    def save_template(self, name):
        name = (name or "").strip()
        if not name or not self._stages:
            return self.state()
        with self._lock:
            tc.save_template(self._root, name, self._stages)
            self._plan["template"] = name
            self._save_soon()
            return self.state()

    # ------------------------------------------------------------------ phân loại
    def label(self, uids, stage_i, bin_name):
        """Xếp các clip vào bin con bin_name của giai đoạn stage_i (None = bỏ nhãn). Ghi nhãn để AI học sau."""
        with self._lock:
            s = self._stages[stage_i]
            if bin_name is not None and bin_name not in s["bins"]:
                return {"error": "Bin %s không thuộc giai đoạn %s." % (bin_name, s["name"])}
            for u in uids:
                c = self._by_uid.get(u)
                if c:
                    tc.set_label(self._plan, c, s["name"], bin_name)
            self._save_soon()
            return self.state()

    def move(self, uids, stage_i, bin_name=None):
        """CHỌN TAY giai đoạn cho các clip (Shift+số, kéo thả, chuột phải): chuyển sang giai đoạn stage_i và, nếu có
        bin_name, gắn luôn nhãn bin con đó. Chọn tay thắng giai đoạn tính theo giờ (ADR-0009, bổ sung 15/11)."""
        with self._lock:
            if stage_i is None or not (0 <= stage_i < len(self._stages)):
                return {"error": "Không có giai đoạn số %s." % (stage_i + 1 if stage_i is not None else "?")}
            s = self._stages[stage_i]
            if bin_name is not None and bin_name not in s["bins"]:
                return {"error": "Bin %s không thuộc giai đoạn %s." % (bin_name, s["name"])}
            n = 0
            for u in uids:
                c = self._by_uid.get(u)
                if not c:
                    continue
                tc.set_manual(self._plan, c, s["name"])
                if bin_name is not None:
                    tc.set_label(self._plan, c, s["name"], bin_name)
                n += 1
            self._save_soon()
            st = self.state()
            st["moved"] = n
            return st

    def clear_manual(self):
        """Bỏ mọi chọn tay: clip quay về giai đoạn tính theo giờ (nhãn bin con vẫn giữ)."""
        with self._lock:
            self._plan["manual"] = {}
            self._save_soon()
            return self.state()

    def add_bin(self, stage_i, name):
        with self._lock:
            name = (name or "").strip().replace("/", "-")
            s = self._stages[stage_i]
            if not name or name in s["bins"]:
                return self.state()
            pos = len(s["bins"]) - 1 if s["bins"][-1:] == [tc.OTHER_BIN] else len(s["bins"])
            s["bins"].insert(pos, name)
            self._save_soon()
            return self.state()

    def reveal(self, uid):
        self._worker.jobs.put(("reveal", uid))
        c = self._by_uid.get(uid)
        return c.name if c else ""

    # ------------------------------------------------------------------ áp dụng / hoàn tác
    def _targets(self):
        self._recount()
        return {c.uid: tc.target_folder(self._assign.get(c.uid), tc.label_of(self._plan, c), self._stages,
                                        tc.manual_of(self._plan, c)) for c in self._clips}

    def apply_preview(self):
        """Nội dung hộp xác nhận: số clip mỗi bin sẽ chuyển (chưa ghi gì)."""
        with self._lock:
            tg = self._targets()
            groups = collections.Counter("/".join(p) for p in tg.values() if p)
            rows = []
            for i, s in enumerate(self._stages):
                top = "%02d_%s" % (i + 1, s["name"])
                n = sum(v for k, v in groups.items() if k == top or k.startswith(top + "/"))
                if n:
                    rows.append({"bin": top, "n": n, "color": s["color"],
                                 "sub": [{"name": k.split("/", 1)[1], "n": v} for k, v in sorted(groups.items())
                                         if k.startswith(top + "/")]})
            return {"src": self._plan.get("source_bin"), "rows": rows,
                    "stay": sum(1 for p in tg.values() if not p), "total": sum(groups.values())}

    def apply(self):
        """CHỈ gọi sau khi người dựng đồng ý ở hộp xác nhận (ADR-0009)."""
        with self._lock:
            if self._busy or not self._clips or not self._stages:
                return False
            self._busy = True
            tg = self._targets()
            self._worker.jobs.put(("apply", (self._plan["source_bin"], tg)))
        self._emit("status", {"text": "Đang chuyển clip trong Media Pool...", "kind": "info"})
        return True

    def _on_applied(self, log, failed):
        self._busy = False
        if log:
            self._plan.setdefault("moves", []).append({"at": datetime.datetime.now().isoformat(timespec="seconds"),
                                                       "bin": self._plan["source_bin"],
                                                       "log": [list(x) for x in log]})
            for uid, _old, new in log:
                if uid in self._by_uid:
                    self._by_uid[uid].bin_path = new
            self._save_now()
        msg = "Đã chuyển %d clip vào bin con." % len(log) if log else "Không có clip nào cần chuyển (đã đúng chỗ)."
        if failed:
            msg += " %d clip KHÔNG chuyển được." % failed
        self._emit("state", self.state())
        self._emit("status", {"text": msg, "kind": "warn" if failed else "ok"})
        self._worker.jobs.put(("bins", None))

    def undo(self):
        with self._lock:
            moves = self._plan.get("moves") or []
            if self._busy or not moves or not self._clips:
                return False
            self._busy = True
            self._worker.jobs.put(("undo", [tuple(x) for x in moves[-1]["log"]]))
        self._emit("status", {"text": "Đang hoàn tác...", "kind": "info"})
        return True

    def _on_undone(self, back, failed):
        self._busy = False
        moves = self._plan.get("moves") or []
        if moves and not failed:
            last = moves.pop()
            for uid, old, _new in last["log"]:
                if uid in self._by_uid:
                    self._by_uid[uid].bin_path = old
        self._save_now()
        msg = "Đã đưa %d clip về bin cũ." % len(back)
        if failed:
            msg += " %d clip KHÔNG đưa về được, nhật ký vẫn giữ để thử lại." % failed
        self._emit("state", self.state())
        self._emit("status", {"text": msg, "kind": "warn" if failed else "ok"})
        self._worker.jobs.put(("bins", None))

    # ------------------------------------------------------------------ thumbnail
    def want_thumbs(self, uids):
        """Giao diện báo các clip đang thấy: làm thumbnail của chúng trước. Ảnh đã có thì gửi lại ngay."""
        ready = {}
        with self._lock:
            self._want = [u for u in uids if u in self._by_uid]
            for u in self._want:
                p = self._thumb_done.get(u, (None, None))[0]
                if p:
                    ready[u] = _data_uri(p)
        self._pump_thumbs()
        return ready

    def big(self, uid):
        """Ảnh lớn (640 px) cho khung xem trước, chạy ngay (pywebview gọi hàm này ở luồng riêng)."""
        c = self._by_uid.get(uid)
        if not c:
            return {}
        _, p, note = self._thumbs.make(uid, c.path, c.proxy, c.lut, c.dur, width=640)
        return {"src": _data_uri(p) if p else None, "note": note}

    def _pump_thumbs(self):
        with self._lock:
            if self._closed:
                return
            n = len(self._inflight)
            if n >= THUMB_INFLIGHT or not self._clips:
                return
            order = [self._by_uid[u] for u in self._want if u in self._by_uid] + self._clips
            for c in order:
                if c.uid in self._thumb_done or c.uid in self._inflight:
                    continue
                self._inflight.add(c.uid)
                fut = self._thumbs.submit(c.uid, c.path, c.proxy, c.lut, c.dur)
                fut.add_done_callback(self._thumb_ready)
                n += 1
                if n >= THUMB_INFLIGHT:
                    break

    def _thumb_ready(self, fut):
        try:
            uid, p, note = fut.result()
        except Exception as e:            # noqa: BLE001
            return self._emit("status", {"text": "Lỗi thumbnail: %s" % e, "kind": "warn"})
        with self._lock:
            self._inflight.discard(uid)
            self._thumb_done[uid] = (p, note)
            done = sum(1 for v in self._thumb_done.values() if v[0])
            bad = len(self._thumb_done) - done
        self._emit("thumb", {"uid": uid, "src": _data_uri(p) if p else None, "note": note,
                             "done": done, "bad": bad, "n": len(self._clips)})
        self._pump_thumbs()

    def thumb_note(self, uid):
        return (self._thumb_done.get(uid) or (None, ""))[1] or ""

    def toggle_star(self, uids):
        """Bật / tắt dấu sao ★ cho danh sách clip uid (phím J hoặc nút bấm)."""
        with self._lock:
            for uid in uids:
                c = self._by_uid.get(uid)
                if c:
                    tc.toggle_star(self._plan, c)
            self._save_soon()
        return self.state()

    def append_starred(self):
        """Đưa toàn bộ clip có sao ★ vào timeline của DaVinci (theo thứ tự giờ quay)."""
        with self._lock:
            if self._busy or not self._clips:
                return {"error": "Trợ lý đang bận hoặc chưa có clip."}
            starred = [c for c in self._clips if tc.is_starred(self._plan, c)]
            if not starred:
                return {"error": "Chưa có clip nào được gắn sao ★. Hãy bấm phím J để gắn sao."}
            # Sắp xếp đúng theo giai đoạn và giờ quay
            starred.sort(key=lambda c: (self._assign.get(c.uid) if self._assign.get(c.uid) is not None else 999,
                                        c.t_start or datetime.datetime.min))
            uids = [c.uid for c in starred]
            self._busy = True
            self._worker.jobs.put(("append_timeline", uids))
        self._emit("status", {"text": "Đang đưa %d clip có sao ★ vào Timeline DaVinci..." % len(uids), "kind": "info"})
        return {"ok": True, "count": len(uids)}

    # ------------------------------------------------------------------ LỜI NÓI (bước 4, ADR-0014)
    def _speech_cfg(self):
        return self._plan.setdefault("speech", {"dir": None, "lang": "vi"})

    def _speech_store(self):
        import troly_speech_run as sr
        import troly_speech_store as ss
        d = self._speech_cfg().get("dir")
        if not d:
            return None
        if self._speech_st is None or self._speech_st.path != sr.store_path(d, self._project):
            self._speech_st = ss.Store(sr.store_path(d, self._project))
        return self._speech_st

    def speech_set_dir(self, path, lang=None):
        """Chọn thư mục kho lời nói (nhớ theo project). KHÔNG cho nằm trong thư mục mã (chữ chép lời không vào git)."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).lower()
        p = os.path.abspath(path or "")
        if not p or p.lower() == root or p.lower().startswith(root + os.sep):
            return {"error": "Thư mục kho lời nói không được nằm trong thư mục mã của Trợ lý. Hãy chọn thư mục khác."}
        with self._lock:
            os.makedirs(p, exist_ok=True)
            cfg = self._speech_cfg()
            cfg["dir"] = p
            if lang in ("vi", "en"):
                cfg["lang"] = lang
            self._speech_st = None
            self._save_now()
        return {"ok": True, "dir": p}

    def speech_info(self):
        """Số liệu cho tab Lời nói: thư mục kho, ngôn ngữ mặc định, đang chạy không, số đối chiếu của cả kho."""
        with self._lock:
            cfg = self._speech_cfg()
            st = self._speech_store()
            keys = [c.rel for c in self._clips]
            return {"dir": cfg.get("dir"), "lang": cfg.get("lang", "vi"), "running": self._speech_run is not None,
                    "counts": st.counts(keys) if st else None, "last": self._speech_last}

    def speech_start(self):
        """Chép lời mọi clip của bin đang đọc. Chạy nền, chạy tiếp được; xong báo qua sự kiện 'speech_done'."""
        import troly_speech as sp
        import troly_speech_run as sr
        with self._lock:
            if self._speech_run is not None:
                return {"error": "Đang chép lời rồi."}
            if not self._clips:
                return {"error": "Chưa có clip. Hãy bấm 'Đọc clip' trước."}
            st = self._speech_store()
            if st is None:
                return {"error": "Chưa chọn thư mục kho lời nói."}
            cfg = self._speech_cfg()
            items = [{"key": c.rel, "uid": c.uid, "name": c.name, "path": c.path, "tc": c.tc} for c in self._clips if c.rel]
            name, vad = sp.load_vad()
            if vad is None:
                return {"error": "Thiếu thư viện silero-vad."}
            phr = sp.load_phrases()
            run = sr.SpeechRun(st, vad_run=vad, index=sp.build_index(phr), prompt=phr.get("prompt"),
                               log_path=os.path.join(cfg["dir"], "loinoi.log"),
                               on_progress=lambda n, t: self._emit("speech_progress", {"n": n, "total": t}))
            self._speech_run = run
            self._speech_last = None
            lang = cfg.get("lang", "vi")

        def go():
            try:
                s = run.run(items, lang)
            except Exception as e:                      # noqa: BLE001
                s = {"ok": False, "message": "Lỗi: %s" % e}
            with self._lock:
                self._speech_run, self._speech_last = None, s
            self._emit("speech_done", s)
        threading.Thread(target=go, daemon=True).start()
        return {"ok": True, "count": len(items)}

    def speech_stop(self):
        with self._lock:
            if self._speech_run is not None:
                self._speech_run.stop = True
        return {"ok": True}

    def speech_clips(self, only_keys=False, min_speech=0.0, text=""):
        """Bản đồ lời nói: mỗi clip một dòng (không có chữ từng câu) + bộ lọc. Trả về cả 'shown' và 'total' cho dòng đếm."""
        with self._lock:
            st = self._speech_store()
            if st is None:
                return {"rows": [], "shown": 0, "total": 0}
            by_rel = {c.rel: c for c in self._clips}
            hits = st.search(text) if (text or "").strip() else None
            rows = []
            for r in st.clip_rows():
                if r["status"] != "done" or r["key"] not in by_rel:
                    continue
                spoken = sum(b - a for a, b in r["speech"])
                r["spoken_s"] = round(spoken, 1)
                if (only_keys and not r["n_keys"]) or spoken < float(min_speech or 0) or (hits is not None and r["key"] not in hits):
                    continue
                c = by_rel[r["key"]]
                r["time"] = c.t_start.strftime("%H:%M:%S") if c.t_start else None
                r["span"] = self._inout_from_text(st, r, c)
                rows.append(r)
            rows.sort(key=lambda r: (by_rel[r["key"]].t_start or datetime.datetime.min, r["key"]))
            total = sum(1 for r in st.clip_rows() if r["status"] == "done" and r["key"] in by_rel)
            return {"rows": rows, "shown": len(rows), "total": total}

    def _inout_from_text(self, st, row, clip):
        """Khung gợi ý In/Out chỉ theo chữ: từ câu có cụm key đầu tiên tới câu có cụm key cuối cùng, đệm 1 giây hai đầu.
        Giây tính từ đầu file; In/Out người dựng đặt tay (mark_in/mark_out) thắng. None nếu không có câu có cụm key."""
        import troly_speech_store as ss
        ln = [l for l in st.lines_of(row["key"]) if l["keys"] and not l["why"]]
        if not ln:
            return None
        dur = row["dur"] or 0
        a, b = max(0.0, ln[0]["t0"] - 1.0), min(dur, ln[-1]["t1"] + 1.0)
        out = {"in_s": round(a, 2), "out_s": round(b, 2), "manual": False}
        if clip.mark_in is not None and clip.mark_out is not None and clip.fps:
            out = {"in_s": round(clip.mark_in / clip.fps, 2), "out_s": round(clip.mark_out / clip.fps, 2), "manual": True}
        out["tc_in"], out["tc_out"] = ss.add_timecode(row.get("tc"), out["in_s"], clip.fps), \
            ss.add_timecode(row.get("tc"), out["out_s"], clip.fps)
        return out

    def speech_lines(self, key):
        with self._lock:
            st = self._speech_store()
            return st.lines_of(key) if st else []

    def speech_set_lang(self, key, lang):
        with self._lock:
            st = self._speech_store()
            if st and lang in ("vi", "en"):
                st.set_lang(key, lang)
        return {"ok": True}

    def close(self):
        self._closed = True
        if self._speech_run is not None:
            self._speech_run.stop = True
        if self._save_timer:
            self._save_timer.cancel()
        self._save_now()
        self._thumbs.shutdown()
        self._worker.jobs.put(("quit", None))
        return True
