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
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import troly_core as tc           # noqa: E402
import troly_resolve as tr        # noqa: E402
import troly_thumbs as tt         # noqa: E402
import troly_ai as ai             # noqa: E402
import troly_dur as td            # noqa: E402
import troly_lut as tl            # noqa: E402
import troly_kf as tkf            # noqa: E402

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
    def __init__(self, project, data_root, emit=None, resolve_factory=None, start_worker=True, thumb_workers=4,
                 proxy_root=None):
        self._project, self._root = project, data_root
        self._proxy_root = proxy_root          # thư mục proxy (config.json: proxy_root); None = chưa cấu hình
        self._play = None
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
        self._analyze = None
        self._ai_cache, self._ai_job = {}, None            # Bước 6 AI (ADR-0022)
        self._dur_cut = None                               # Bước 5: bản cắt gọt đã bấm "Cắt gọt cho vừa" (đúng bản này mới được đưa lên timeline)
        import troly_batch as _tb
        self._shutdown_fn = _tb.system_shutdown     # kiểm thử thay bằng bản giả
        self._analyze_countdown, self._analyze_sleep = _tb.COUNTDOWN_S, time.sleep      # kiểm thử rút ngắn
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
            elif kind == "inout_written":
                self._on_inout_written(data)
            elif kind == "inout_restored":
                self._on_inout_restored(data)
            elif kind == "cut_timeline_created":
                self._busy = False
                self._dur_cut = None
                ok = data.get("verified")
                if ok:
                    chk = "Kiểm lại: số timeline %s → %s, timeline cũ còn nguyên." % (data["before"], data["after"])
                elif data.get("before") is not None:
                    chk = "CHƯA kiểm lại khớp (số timeline hoặc timeline cũ không khớp), hãy xem trong DaVinci."
                else:
                    chk = "CHƯA kiểm lại được số timeline (DaVinci không cho đọc danh sách)."
                self._emit("status", {"text": "Đã tạo timeline mới “%s” gồm %d đoạn. %s" % (data["name"], data["n"], chk), "kind": "ok" if ok else "warn"})
                self._emit("dur_timeline_done", data)
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
                eff = tc.effective_inout(self._plan, c)          # đặt tay trong panel > đang có trong DaVinci
                in_s, out_s, io_src = (round(eff[0], 2), round(eff[1], 2), eff[2]) if eff else (None, None, None)
                dv = (round(c.mark_in / fps, 2), round(c.mark_out / fps, 2)) if c.mark_in is not None and c.mark_out is not None else None
                sug = tc.suggest_inout(c.dur, lb, self._plan.get("shoot_style") or "", self._plan.get("bin_rules"), self._plan.get("trad_trim_s"))
                clips.append({"uid": c.uid, "name": c.name, "m0": m[0] if m else None, "m1": m[1] if m else None,
                              "time": c.t_start.strftime("%H:%M:%S") if c.t_start else "--:--:--",
                              "dur": c.dur or 0, "stage": si, "label": lb,
                              "manual": bool(tc.manual_of(self._plan, c)), "camera": c.camera, "src": c.t_src, "lut": c.lut or "", "bin_path": c.bin_path,
                              "thumb": c.uid in self._thumb_done and bool(self._thumb_done[c.uid][0]),
                              "in_s": in_s, "out_s": out_s, "io_src": io_src, "dv": dv, "fps": fps, "tc": c.tc or "", "sug": sug,
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
                    "shoot_style": self._plan.get("shoot_style") or "",
                    "rules": self._rules_state(),
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

    def set_shoot_style(self, style):
        """Kiểu quay của project: '' (chưa chọn, không đổi gì), 'traditional' (Truyền thống) hoặc 'psc'. Lưu trong kế hoạch project.
        CHỈ đổi gợi ý màu xanh; In/Out người dựng đặt tay luôn thắng và gợi ý không bao giờ được ghi vào DaVinci (ADR-0018)."""
        style = style or ""
        if style not in tc.SHOOT_STYLES:
            return {"error": "Kiểu quay không hợp lệ."}
        with self._lock:
            if style:
                self._plan["shoot_style"] = style
            else:
                self._plan.pop("shoot_style", None)
            self._save_now()
        return self.state()

    # ------------------------------------------------------------------ bảng quy tắc từng bin + sóng âm (ADR-0019)
    def _rules_state(self):
        names = []
        for st in self._plan.get("stages") or []:
            for b in st.get("bins") or []:
                if b not in names:
                    names.append(b)
        tt_ = self._plan.get("trad_trim_s")
        return {"bins": tc.rules_view(self._plan, names), "trad_trim": tc.TRAD_HEAD_S if tt_ is None else tt_,
                "trad_default": tc.TRAD_HEAD_S, "style": self._plan.get("shoot_style") or ""}

    def set_bin_rule(self, name, mn, mx, whole=False):
        """Sửa quy tắc gợi ý của một bin (name = tên bin, hoặc '*' cho dòng 'Bin khác'). Lưu trong kế hoạch project.
        CHỈ đổi gợi ý màu xanh; In/Out đặt tay luôn thắng và gợi ý không bao giờ được ghi vào DaVinci."""
        if not name or not isinstance(name, str):
            return {"error": "Thiếu tên bin."}
        ok, v = tc.check_bin_rule(mn, mx, bool(whole))
        if not ok:
            return {"error": v}
        with self._lock:
            self._plan.setdefault("bin_rules", {})[name] = v
            self._save_now()
        return self.state()

    def reset_bin_rule(self, name=None):
        """Về mặc định: một bin (name) hoặc cả bảng (name rỗng) và số giây cắt của Truyền thống."""
        with self._lock:
            br = self._plan.get("bin_rules") or {}
            if name:
                br.pop(name, None)
            else:
                br = {}
                self._plan.pop("trad_trim_s", None)
            if br:
                self._plan["bin_rules"] = br
            else:
                self._plan.pop("bin_rules", None)
            self._save_now()
        return self.state()

    def set_trad_trim(self, seconds):
        """Số giây cắt đầu và đuôi của kiểu Truyền thống (mặc định 1.5)."""
        try:
            v = float(seconds)
        except (TypeError, ValueError):
            return {"error": "Số giây phải là số."}
        if v != v or v < 0 or v > 30:
            return {"error": "Số giây cắt phải từ 0 đến 30."}
        with self._lock:
            if abs(v - tc.TRAD_HEAD_S) < 1e-9:
                self._plan.pop("trad_trim_s", None)
            else:
                self._plan["trad_trim_s"] = round(v, 2)
            self._save_now()
        return self.state()

    def _wave_maker(self):
        if getattr(self, "_wave", None) is None:
            import troly_wave as tw
            self._wave = tw.WaveMaker(os.path.join(self._root, "cache", "troly_wave", tc._safe(self._project)))
        return self._wave

    def wave(self, uid):
        """Sóng âm của clip, làm nền từ proxy (chỉ đọc): {'peaks': [0..100...]} | {'pending': True} | {'error': ...}."""
        c = self._by_uid.get(uid)
        if c is None:
            return {"error": "Không thấy clip."}
        if not self._proxy_root:
            return {"error": "Chưa cấu hình proxy_root trong config.json."}
        src = c.proxy
        if not src or not os.path.isfile(src):
            return {"error": "Chưa có proxy"}
        import troly_play as tp
        if not tp.inside(src, [self._proxy_root]):
            return {"error": "Proxy nằm ngoài thư mục proxy đã cấu hình."}
        return self._wave_maker().get(c.rel or c.name, src)

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
            src = self._plan.get("source_bin") or ""
            leaving, in_bin = collections.Counter(), collections.Counter()
            for c in self._clips:                       # bin cũ (đã tạo lần Áp dụng trước) mà mọi clip trong đó sắp chuyển đi thì sẽ RỖNG
                bp = c.bin_path or ""
                if bp.startswith(src + "/"):
                    in_bin[bp] += 1
                    p = tg.get(c.uid)
                    if p and src + "/" + "/".join(p) != bp:
                        leaving[bp] += 1
            emptied = sorted(b[len(src) + 1:] for b in in_bin if in_bin[b] == leaving[b])
            return {"src": src, "rows": rows, "emptied": emptied,
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

    # ------------------------------------------------------------------ Bước 6 AI: gợi ý bin (ADR-0022) - CHỈ GỢI Ý
    # Gợi ý lấy từ file riêng + vector (chỉ đọc). "Nhận" chỉ gán NHÃN trong kế hoạch panel (như anh xếp tay); chuyển clip trong DaVinci vẫn do
    # nút "Áp dụng vào Media Pool" (có nhật ký + Hoàn tác). AI không bao giờ gọi DaVinci.
    def _ai_files(self):
        d = ai.embed_dir(self._root, self._project)
        return os.path.join(d, "vectors.npz"), os.path.join(self._root, "troly", "ai_suggest", tc._safe(self._project) + ".json")

    def _ai_data(self):
        """(vectors, desc) nạp lại khi file đổi."""
        vf, sf = self._ai_files()
        sig = tuple((os.path.getmtime(f) if os.path.isfile(f) else 0) for f in (vf, sf))
        if self._ai_cache.get("sig") != sig:
            try:
                self._ai_cache = {"sig": sig, "vec": ai.load_vectors(self._root, self._project), "desc": ai.load_suggest(self._root, self._project)}
            except Exception:                                 # noqa: BLE001  numpy thiếu / file hỏng: coi như chưa có
                self._ai_cache = {"sig": sig, "vec": {}, "desc": None}
        return self._ai_cache["vec"], self._ai_cache["desc"]

    def _ai_labeled(self):
        out = {}
        for rel, v in (self._plan.get("labels") or {}).items():
            if isinstance(v, dict) and v.get("bin"):
                out[ai.ck(rel)] = v["bin"]
        return out

    def _ai_jobobj(self):
        if self._ai_job is None:
            import troly_env
            self._ai_job = ai.AiJob(self._project, self._root, (troly_env.config() or {}).get("ai_python"))
        return self._ai_job

    def ai_info(self):
        with self._lock:
            vec, desc = self._ai_data()
            job = self._ai_jobobj()
            lab = self._ai_labeled()
            n_lab = sum(1 for k in lab if k in vec)
            return {"has_data": bool(desc and desc[1]), "running": job.running(), "can_run": job.available(), "log": job.last_log(),
                    "n_vectors": len(vec), "n_labeled": n_lab, "mode": "nhan" if n_lab >= ai.MIN_FEWSHOT_LABELS else "mo_ta",
                    "min_labels": ai.MIN_FEWSHOT_LABELS}

    def ai_run(self):
        """Chạy nhúng + gợi ý bằng venv AI trong nền (dừng được bằng ai_stop, chạy lại thì làm tiếp)."""
        with self._lock:
            job = self._ai_jobobj()
            if not job.available():
                return {"error": "Chưa có venv AI hoặc model (xem docs/adr/0020)."}
            job.start()
            return self.ai_info()

    def ai_stop(self):
        with self._lock:
            self._ai_jobobj().stop()
            return self.ai_info()

    def ai_for(self, uids, include_labeled=False):
        """{uid: {'src': 'nhan'|'mo_ta', 'top': [{'bin','score'}...]}} cho các clip; clip đã bị bỏ qua -> {'skipped': True};
        chưa có dữ liệu -> {}. Chỉ xét các bin của giai đoạn clip đang ở. Clip đã xếp bị bỏ qua trừ khi include_labeled."""
        with self._lock:
            vec, desc = self._ai_data()
            if not vec and not desc:
                return {}
            lab = self._ai_labeled()
            skip = self._plan.get("ai_skip") or {}
            out = {}
            for u in uids:
                c = self._by_uid.get(u)
                si = self._assign.get(u)
                if not c or si is None or si < 0 or si >= len(self._stages):
                    continue
                if not include_labeled and self._label_in_stage(c, si):
                    continue
                if skip.get(c.rel or c.name):
                    out[u] = {"skipped": True}
                    continue
                cand = self._stages[si]["bins"]
                key = ai.ck(c.rel or c.name)
                train = {k: b for k, b in lab.items() if k != key}
                src, top = ai.rank_for_clip(key, cand, vec, train, desc)
                if top:
                    out[u] = {"src": src, "top": top}
            return out

    def ai_accept(self, pairs):
        """Nhận gợi ý: pairs = [[uid, tên bin]]. Chỉ gán NHÃN trong kế hoạch (by='ai_duyet'); không đụng DaVinci."""
        with self._lock:
            n, bad = 0, 0
            for u, b in pairs:
                c = self._by_uid.get(u)
                si = self._assign.get(u)
                if not c or si is None or si < 0 or si >= len(self._stages) or b not in self._stages[si]["bins"]:
                    bad += 1
                    continue
                tc.set_label(self._plan, c, self._stages[si]["name"], b, by="ai_duyet")
                (self._plan.get("ai_skip") or {}).pop(c.rel or c.name, None)
                n += 1
            self._save_soon()
            st = self.state()
            st["ai_accepted"], st["ai_bad"] = n, bad
            return st

    def ai_skip(self, uids, undo=False):
        """Bỏ qua gợi ý của clip (lưu trong kế hoạch panel; undo=True để hiện lại)."""
        with self._lock:
            sk = self._plan.setdefault("ai_skip", {})
            for u in uids:
                c = self._by_uid.get(u)
                if c:
                    if undo:
                        sk.pop(c.rel or c.name, None)
                    else:
                        sk[c.rel or c.name] = True
            self._save_soon()
            return {"ok": True}

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

    # ------------------------------------------------------------------ In/Out (ADR-0016)
    def set_inout(self, uid, in_s, out_s):
        """Lưu In/Out đặt tay (giây từ đầu file) vào KẾ HOẠCH panel; in_s/out_s None thì xóa. Không đụng DaVinci."""
        with self._lock:
            c = self._by_uid.get(uid)
            if c is None:
                return {"error": "Không thấy clip."}
            try:
                r = tc.set_manual_inout(self._plan, c, in_s, out_s)
            except (TypeError, ValueError):
                return {"error": "In/Out không hợp lệ."}
            self._save_now()
            return {"ok": True, "in_s": r[0] if r else None, "out_s": r[1] if r else None}

    def _inout_rows(self, uids):
        rows = []
        for u in uids:
            c = self._by_uid.get(u)
            fr = tc.inout_frames(self._plan, c) if c is not None else None
            if fr:
                rows.append((u, c.rel, fr[0], fr[1]))
        return rows

    def inout_write_preview(self, scope="starred", uids=None):
        """Đếm clip sẽ được ghi (để hộp xác nhận nói rõ số clip). scope: 'starred' = clip có sao, 'selected' = uids.
        Chỉ clip có In/Out ĐẶT TAY mới được ghi; còn lại bị bỏ qua (không ghi gợi ý tự động)."""
        with self._lock:
            pool = uids or [] if scope == "selected" else [c.uid for c in self._clips if tc.is_starred(self._plan, c)]
            rows = self._inout_rows(pool)
            return {"pool": len(pool), "n": len(rows), "skip": len(pool) - len(rows),
                    "has_undo": bool(tc.latest_inout_backup(self._root, self._project))}

    def inout_write(self, scope="starred", uids=None):
        """Ghi In/Out đặt tay vào Media Pool DaVinci (sau khi người dựng đã xác nhận ở giao diện). Sao lưu cũ trước."""
        with self._lock:
            if self._busy or not self._clips:
                return {"error": "Đang bận hoặc chưa đọc clip."}
            pool = uids or [] if scope == "selected" else [c.uid for c in self._clips if tc.is_starred(self._plan, c)]
            rows = self._inout_rows(pool)
            if not rows:
                return {"error": "Không có clip nào có In/Out đặt tay để ghi."}
            self._busy = True
            self._worker.jobs.put(("inout_write", (self._root, self._project, rows)))
        self._emit("status", {"text": "Đang sao lưu In/Out cũ rồi ghi %d clip..." % len(rows), "kind": "info"})
        return {"ok": True, "n": len(rows)}

    def _on_inout_written(self, r):
        self._busy = False
        self._plan["last_inout_backup"] = r["backup"]
        for u in r["ok"]:                                   # DaVinci nay đã có đúng giá trị này
            c = self._by_uid.get(u)
            fr = tc.inout_frames(self._plan, c) if c is not None else None
            if fr:
                c.mark_in, c.mark_out = fr
        self._save_now()
        n_bad = len(r["bad"]) + len(r["mismatch"])
        names = ", ".join(self._by_uid[u].name for u, _ in (r["bad"] + r["mismatch"])[:5] if u in self._by_uid)
        if n_bad:
            msg = "Ghi In/Out: khớp %d/%d clip; %d clip LỖI/LỆCH (%s). Bấm Hoàn tác In/Out để khôi phục nếu cần." % (
                len(r["ok"]), r["total"], n_bad, names)
        else:
            msg = "Đã ghi In/Out cho %d clip, đọc lại khớp 100%%. Sao lưu: %s" % (len(r["ok"]), r["backup"])
        self._emit("state", self.state())
        self._emit("status", {"text": msg, "kind": "warn" if n_bad else "ok"})

    def inout_undo(self):
        with self._lock:
            p = tc.latest_inout_backup(self._root, self._project)
            if self._busy or not p or not self._clips:
                return {"error": "Chưa có bản sao lưu In/Out để hoàn tác."}
            self._busy = True
            self._worker.jobs.put(("inout_restore", p))
        self._emit("status", {"text": "Đang khôi phục In/Out cũ...", "kind": "info"})
        return {"ok": True}

    def _on_inout_restored(self, r):
        self._busy = False
        data = tc.read_inout_backup(r["backup"]) or {}
        if not r["bad"]:
            data["restored"] = True                          # đánh dấu để lần Hoàn tác sau lấy bản trước nữa
            try:
                tc._write_json(r["backup"], data)
            except OSError:
                pass
        by = {e["uid"]: e for e in data.get("entries", [])}
        for u in r["ok"]:
            c, e = self._by_uid.get(u), by.get(u)
            if c is not None and e is not None:
                c.mark_in, c.mark_out = e.get("in"), e.get("out")
        msg = "Đã khôi phục In/Out cũ cho %d clip, đọc lại khớp." % len(r["ok"])
        if r["bad"]:
            msg = "Khôi phục %d clip; %d clip KHÔNG khớp, file sao lưu vẫn giữ: %s" % (len(r["ok"]), len(r["bad"]), r["backup"])
        self._emit("state", self.state())
        self._emit("status", {"text": msg, "kind": "warn" if r["bad"] else "ok"})

    # ------------------------------------------------------------------ trình phát proxy (ADR-0016)
    def _play_dir(self):
        return os.path.join(self._root, "cache", "troly_play", tc._safe(self._project))

    def _play_server(self):
        import troly_play as tp
        if self._play is None:
            self._play = tp.PlayServer([self._proxy_root, self._play_dir()])
        return self._play

    def play_info(self, uid, transcode=False):
        """URL phát file proxy của clip (chỉ đọc). transcode=True: phương án dự phòng, ffmpeg tạo mp4 H.264 nhẹ trong cache
        (xóa được). Clip không có proxy: {"error": "Chưa có proxy"} để giao diện hiện thumbnail."""
        import troly_play as tp
        c = self._by_uid.get(uid)
        if c is None:
            return {"error": "Không thấy clip."}
        if not self._proxy_root:
            return {"error": "Chưa cấu hình proxy_root trong config.json."}
        src = c.proxy
        if not src or not os.path.isfile(src):
            return {"error": "Chưa có proxy"}
        if not tp.inside(src, [self._proxy_root]):
            return {"error": "Proxy nằm ngoài thư mục proxy đã cấu hình."}
        if transcode:
            dst = tp.ensure_play_mp4(src, self._play_dir(), c.rel or c.name)
            if not dst:
                return {"error": "ffmpeg không tạo được bản xem nhẹ."}
            src = dst
        url = self._play_server().url_for(src)
        if not url:
            return {"error": "Không phát được file này."}
        return {"url": url, "fps": c.fps or 25.0, "dur": c.dur or 0, "transcoded": bool(transcode)}

    def keyframes(self, uid):
        """Keyframe của proxy (giây) để lướt mượt; chỉ đọc proxy trong proxy_root. {'kf': [...]} hoặc {'error': ...}."""
        import troly_play as tp
        c = self._by_uid.get(uid)
        if c is None or not self._proxy_root:
            return {"error": "Không thấy clip hoặc chưa cấu hình proxy_root."}
        src = c.proxy
        if not src or not os.path.isfile(src) or not tp.inside(src, [self._proxy_root]):
            return {"error": "Chưa có proxy"}
        kf = tkf.get(src, os.path.join(self._root, "cache", "troly_kf", tc._safe(self._project)), tkf.ffprobe_path(self._thumbs.ffmpeg))
        return {"kf": kf} if kf else {"error": "Không đọc được keyframe"}

    def lut_cube(self, uid):
        """Dữ liệu LUT .cube của clip để giao diện áp bằng WebGL lên khung xem (Việc 1, ADR-0023). Chỉ ĐỌC file LUT; không có LUT thì {'none': True}."""
        c = self._by_uid.get(uid)
        if c is None:
            return {"error": "Không thấy clip."}
        if not c.lut:
            return {"none": True}
        path = self._thumbs.lut_for(c.lut)
        if not path:
            return {"error": "Không thấy file LUT %s" % c.lut}
        cache = self.__dict__.setdefault("_lut_payloads", {})
        if path not in cache:
            try:
                cache[path] = tl.payload(path)
            except (tl.LutError, OSError) as e:
                cache[path] = {"error": str(e)}
        return cache[path]

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
                fut.add_done_callback(lambda f, u=c.uid: self._thumb_ready(f, u))
                n += 1
                if n >= THUMB_INFLIGHT:
                    break

    def _thumb_ready(self, fut, uid_hint=None):
        try:
            uid, p, note = fut.result()
        except Exception as e:            # noqa: BLE001  làm thumbnail ném ngoại lệ: giải phóng chỗ, tính là lỗi (không kẹt hàng đợi)
            if uid_hint is not None:
                with self._lock:
                    self._inflight.discard(uid_hint)
                    self._thumb_done[uid_hint] = (None, "lỗi: %s" % e)
            self._emit("status", {"text": "Lỗi thumbnail: %s" % e, "kind": "warn"})
            return self._pump_thumbs()
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

    # ------------------------------------------------------------------ BƯỚC 5: THỜI LƯỢNG (ADR-0013)
    # Số liệu mặc định là ĐỀ XUẤT (chưa được người dựng xác nhận). Khóa plan["durations"] chỉ có khi anh sửa.
    def _dur_build(self):
        self._recount()
        return td.build(self._plan, self._clips, self._assign, self._stages)

    def _dur_view(self, r=None):
        r = r or self._dur_build()
        for i, s in enumerate(r["stages"]):
            s["color"] = self._stages[i].get("color")
            for j, b in enumerate(s["bins"]):
                b["color"] = SUB_COLORS[j % len(SUB_COLORS)]
        r["cut_ready"] = self._dur_cut is not None and self._dur_cut["items"] == r["items"]
        r["proposed"] = True
        r["limits"] = {"target": list(td.TARGET_LIMITS_MIN), "suggest": list(td.SUGGEST_RANGE_MIN), "scale_s": td.BIN_SCALE_S}
        d = self._plan.get("durations") or {}
        r["edited"] = {"target": "target_min" in d, "share": bool(d.get("stage_share")), "bins": bool(d.get("bins"))}
        r["style"] = self._plan.get("shoot_style") or ""
        return r

    def dur_state(self):
        with self._lock:
            return self._dur_view()

    def dur_set_target(self, minutes):
        with self._lock:
            ok, v = td.check_target(minutes)
            if not ok:
                return {"error": v}
            self._plan.setdefault("durations", {})["target_min"] = v
            self._save_soon()
            return self._dur_view()

    def dur_set_share(self, index, fraction):
        """Kéo thanh tỉ lệ: giai đoạn index chiếm fraction (0..1), các giai đoạn khác co giãn để TỔNG luôn bằng 1."""
        with self._lock:
            r = self._dur_build()
            if not isinstance(index, int) or not 0 <= index < len(r["shares"]):
                return {"error": "Không có giai đoạn số %s." % index}
            try:
                f = float(fraction)
            except (TypeError, ValueError):
                return {"error": "Tỉ lệ phải là số."}
            if f != f:
                return {"error": "Tỉ lệ phải là số."}
            v = td.normalize_shares(r["shares"], index, f)
            self._plan.setdefault("durations", {})["stage_share"] = {s["name"]: round(x, 4) for s, x in zip(r["stages"], v)}
            self._save_soon()
            return self._dur_view()

    def dur_set_bin(self, stage_i, bin_name, mn, mx):
        """Sửa Min-Max TỔNG của một bin con (giây). Sai (âm, không phải số, Min > Max) thì báo lỗi và KHÔNG ghi gì."""
        with self._lock:
            if not isinstance(stage_i, int) or not 0 <= stage_i < len(self._stages):
                return {"error": "Không có giai đoạn số %s." % stage_i}
            ok, v = td.check_bin_minmax(mn, mx)
            if not ok:
                return {"error": v}
            name = self._stages[stage_i]["name"]
            self._plan.setdefault("durations", {}).setdefault("bins", {}).setdefault(name, {})[bin_name] = list(v)
            self._save_soon()
            return self._dur_view()

    def dur_reset(self):
        """Về số đề xuất: xóa mọi chỉnh sửa Bước 5 khỏi kế hoạch (mục tiêu, tỉ lệ, Min-Max)."""
        with self._lock:
            self._plan.pop("durations", None)
            self._dur_cut = None
            self._save_soon()
            return self._dur_view()

    def dur_cut(self):
        """Nút "Cắt gọt cho vừa": tính kế hoạch cắt gọt (chỉ trong panel) và nhớ lại đúng bản này. Chưa chạm DaVinci."""
        with self._lock:
            r = self._dur_build()
            self._dur_cut = {"items": r["items"], "total_s": r["total_s"], "target_min": r["target_min"]}
            return self._dur_view(r)

    def dur_create_timeline(self):
        """Nút "Đưa lên Timeline mới" (giao diện đã hỏi xác nhận). Chỉ đưa ĐÚNG bản đã cắt gọt; số liệu đã đổi thì bắt cắt gọt lại.
        Ghi nhật ký (số clip, tổng giây) TRƯỚC khi tạo; chỉ tạo timeline mới, không SetMarkInOut lên clip gốc."""
        import re
        with self._lock:
            if self._busy or not self._clips:
                return {"error": "Trợ lý đang bận hoặc chưa có clip."}
            r = self._dur_build()
            if not r["items"]:
                return {"error": "Không có clip nào để đưa lên (chưa gắn sao ★ hoặc đã bị cắt hết)."}
            if self._dur_cut is None or self._dur_cut["items"] != r["items"]:
                return {"error": "Số liệu đã đổi từ lần cắt gọt trước. Hãy bấm \"Cắt gọt cho vừa\" rồi xem lại trước khi đưa lên."}
            segs, rows = [], []
            for it in r["items"]:
                c = self._by_uid.get(it["uid"])
                if c is None or not c.fps:
                    continue
                a, b = tc.cut_frames(it["in_s"], it["out_s"], c.fps, c.frames)
                segs.append((c.uid, a, b))
                rows.append({"rel": c.rel, "stage": self._stages[it["stage"]]["name"], "bin": it["bin"], "in_s": it["in_s"], "out_s": it["out_s"],
                             "in_frame": a, "out_frame": b})
            if not segs:
                return {"error": "Không có đoạn nào hợp lệ (clip thiếu fps)."}
            stamp = datetime.datetime.now()
            raw = "Rough Cut thoi luong %s %s" % (self._project, stamp.strftime("%d.%m %Hh%Mm%S"))
            name = " ".join(re.sub(r'[\\/:*?"<>|&]', " ", raw).split())
            try:
                log = tc.write_timeline_log(self._root, self._project, {
                    "created": stamp.isoformat(timespec="seconds"), "timeline_name": name, "count": len(segs), "total_s": r["total_s"],
                    "target_min": r["target_min"], "delta_s": r["delta_s"], "style": self._plan.get("shoot_style") or "", "items": rows})
            except OSError as e:
                return {"error": "Không ghi được nhật ký, chưa đụng DaVinci: %s" % e}
            self._busy = True
            self._worker.jobs.put(("create_cut_timeline", (name, segs)))
        self._emit("status", {"text": "Đang tạo timeline mới (%d đoạn, %s)..." % (len(segs), td.mmss(r["total_s"])), "kind": "info"})
        return {"ok": True, "count": len(segs), "total_s": r["total_s"], "name": name, "log": log}

    # ------------------------------------------------------------------ ĐỔI TÊN GIAI ĐOẠN / BIN CON (ADR-0015)
    def _rename_siblings(self, kind, i):
        if kind == "stage":
            return [s["name"] for s in self._stages], self._stages[i]["name"]
        return list(self._stages[i]["bins"]), None

    def rename_check(self, kind, i, old, new):
        """Kiểm tên mới trước khi đổi (chưa ghi gì). Trả {'error'} hoặc {'ok', 'name', 'same', 'n_clips'}: n_clips = số clip đang
        nằm trong bin cũ ở Media Pool (nếu đã Áp dụng; bin đó sẽ còn lại rỗng, Trợ lý không tự xóa)."""
        with self._lock:
            if kind not in ("stage", "bin") or not (0 <= i < len(self._stages)):
                return {"error": "Không thấy giai đoạn."}
            if kind == "bin" and (old not in self._stages[i]["bins"] or old == tc.OTHER_BIN):
                return {"error": "Bin “%s” không đổi tên được." % old}
            sibs, cur = self._rename_siblings(kind, i)
            cur = cur if kind == "stage" else old
            n, err = tc.check_new_name(new, sibs, cur)
            if err:
                return {"error": err}
            s = self._stages[i]
            src = self._plan.get("source_bin") or ""
            pre = tc.bin_prefix(src, i, s["name"], old if kind == "bin" else None)
            n_clips = sum(1 for c in self._clips if (c.bin_path or "") == pre or (c.bin_path or "").startswith(pre + "/"))
            return {"ok": True, "name": n, "same": n == cur, "n_clips": n_clips}

    def rename(self, kind, i, old, new):
        """Đổi tên giai đoạn (kind='stage') hoặc bin con (kind='bin') CHỈ trong kế hoạch của panel: nhãn clip đi theo tên mới,
        phím 1-9 giữ nguyên theo vị trí. Bin thật trong Media Pool chỉ được tạo khi bấm Áp dụng (ADR-0015)."""
        with self._lock:
            chk = self.rename_check(kind, i, old, new)
            if chk.get("error"):
                return chk
            if chk["same"]:
                return {"ok": True, "same": True}
            self._recount()
            cur = self._stages[i]["name"] if kind == "stage" else old
            keys = {c.rel or c.name for c in self._clips if self._assign.get(c.uid) == i}
            tc.rename_in_plan(self._plan, kind, i, cur, chk["name"], keys)
            self._save_now()
            self._recount()
        self._emit("state", self.state())
        return {"ok": True, "name": chk["name"], "old_bin_left": chk["n_clips"] > 0}

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
            items = self._speech_items()
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

    def speech_pick_dir(self):
        """Hộp chọn thư mục kho lời nói (cửa sổ do panel_troly_web gắn vào pick_dir_fn)."""
        fn = getattr(self, "pick_dir_fn", None)
        if fn is None:
            return {"error": "Không mở được hộp chọn thư mục ở chế độ này."}
        p = fn()
        if not p:
            return {"cancel": True}
        return self.speech_set_dir(p)

    def _seg_colors(self, speech, flags, suspect_gain):
        """Màu từng đoạn nói trên thanh: key (có cụm key lễ cưới), dist (câu nghi sai hoặc kéo âm lượng nhiều), sp (có người nói)."""
        out = []
        for a, b in speech:
            col = "sp"
            for t0, t1, nk, why in flags:
                if min(b, t1) - max(a, t0) > 0:
                    if why:
                        col = "dist"
                        break
                    if nk:
                        col = "key"
            if col == "sp" and suspect_gain:
                col = "dist"
            out.append([a, b, col])
        return out

    def _span(self, key, row, flags, clip):
        """Khung gợi ý In/Out (giây tính từ đầu file). Thứ tự ưu tiên: người dựng đặt tay trong panel > In/Out đặt trong
        DaVinci > gợi ý theo chữ (từ câu có cụm key đầu tiên tới câu có cụm key cuối cùng, đệm 1 giây hai đầu).
        None nếu không có gì để gợi ý. Chỉ ĐỌC, không ghi gì vào DaVinci."""
        import troly_speech_store as ss
        dur = row.get("dur") or 0
        man = (self._plan.get("inout") or {}).get(key)
        if man:
            a, b, src = man[0], man[1], "manual"
        elif clip is not None and clip.mark_in is not None and clip.mark_out is not None and clip.fps:
            a, b, src = clip.mark_in / clip.fps, clip.mark_out / clip.fps, "davinci"
        else:
            ln = [f for f in flags if f[2] and not f[3]]
            if not ln:
                return None
            a, b, src = max(0.0, ln[0][0] - 1.0), min(dur, ln[-1][1] + 1.0), "text"
        fps = (clip.fps if clip is not None else None) or 25.0
        return {"in_s": round(a, 2), "out_s": round(b, 2), "src": src,
                "tc_in": ss.add_timecode(row.get("tc"), a, fps), "tc_out": ss.add_timecode(row.get("tc"), b, fps)}

    def speech_clips(self, only_keys=False, min_speech=0.0, text=""):
        """Bản đồ lời nói: mỗi clip một dòng (không có chữ từng câu) + bộ lọc. 'all' = mọi clip đã có dòng (cho đếm X / Y),
        'summary' = số liệu cả project."""
        with self._lock:
            st = self._speech_store()
            if st is None:
                return {"rows": [], "all": [], "summary": None}
            by_rel = {c.rel: c for c in self._clips}
            flags = st.line_flags()
            hits = st.search(text) if (text or "").strip() else None
            rows, all_ = [], []
            for r in st.clip_rows():
                c = by_rel.get(r["key"])
                if c is None or r["status"] not in ("done", "silent"):
                    continue
                all_.append({"uid": c.uid, "stage": self._assign.get(c.uid), "spoken_s": 0.0})
                spoken = round(sum(b - a for a, b in r["speech"]), 1)
                all_[-1]["spoken_s"] = spoken
                if (only_keys and not r["n_keys"]) or spoken < float(min_speech or 0) or (hits is not None and r["key"] not in hits):
                    continue
                fl = flags.get(r["key"], [])
                rows.append({"uid": c.uid, "key": r["key"], "name": c.name, "stage": self._assign.get(c.uid),
                             "time": c.t_start.strftime("%H:%M:%S") if c.t_start else None,
                             "t_sort": c.t_start.isoformat() if c.t_start else "",
                             "dur": r["dur"] or c.dur or 0, "fps": c.fps or 25.0, "tc": r["tc"], "spoken_s": spoken, "lang": r["lang"], "n_keys": r["n_keys"],
                             "headline": r["headline"] or "", "suspect": bool(r["suspect"]), "silent": r["status"] == "silent",
                             "segs": self._seg_colors(r["speech"], fl, (r["gain_db"] or 0) > 18.0),
                             "span": self._span(r["key"], r, fl, c), "star": tc.is_starred(self._plan, c)})
            rows.sort(key=lambda x: (x["t_sort"], x["key"]))
            return {"rows": rows, "all": all_, "summary": st.counts([c.rel for c in self._clips])}

    def speech_detail(self, uid):
        """Cột phải: chữ của một clip + khung In/Out. Chữ chỉ đi từ kho ra giao diện, không đi đâu khác."""
        with self._lock:
            st = self._speech_store()
            c = self._by_uid.get(uid)
            if st is None or c is None:
                return {"lines": [], "span": None}
            row = next((r for r in st.clip_rows() if r["key"] == c.rel), None)
            if row is None:
                return {"lines": [], "span": None}
            lines = st.lines_of(c.rel)
            fl = [(l["t0"], l["t1"], len(l["keys"]), ",".join(l["why"])) for l in lines]
            return {"lines": lines, "span": self._span(c.rel, row, fl, c), "lang": row["lang"], "dur": row["dur"], "fps": c.fps or 25.0,
                    "tc": row["tc"], "suspect": bool(row["suspect"]), "star": tc.is_starred(self._plan, c)}

    def speech_set_inout(self, uid, in_s, out_s):
        """Lưu In/Out người dựng đặt tay VÀO KẾ HOẠCH CỦA PANEL (không ghi vào DaVinci). in_s/out_s = None thì xóa."""
        with self._lock:
            c = self._by_uid.get(uid)
            if c is None:
                return {"error": "Không thấy clip."}
            d = self._plan.setdefault("inout", {})
            if in_s is None or out_s is None:
                d.pop(c.rel, None)
            else:
                a, b = sorted((float(in_s), float(out_s)))
                d[c.rel] = [round(a, 2), round(b, 2)]
            self._save_now()
        return {"ok": True}

    def speech_export(self, scope, uids=None, dest=None):
        """Xuất SRT (mục A4). scope: 'stages' = mỗi giai đoạn một file (giờ nối tiếp liên tục qua các clip); 'selection' = một
        file cho các clip uids; 'clip' = SRT riêng một clip (giờ gốc của clip). dest = thư mục người dựng chọn (None: mở hộp chọn).
        File đã có thì KHÔNG ghi đè: thêm giờ vào tên. Chữ chỉ đi từ kho ra thư mục này."""
        import datetime as _dt
        import troly_speech_srt as sx
        with self._lock:
            st = self._speech_store()
        if st is None:
            return {"error": "Chưa chọn thư mục kho lời nói, hoặc chưa chép lời."}
        if scope not in ("stages", "selection", "clip"):
            return {"error": "Kiểu xuất không hợp lệ."}
        if not dest:
            fn = getattr(self, "pick_dir_fn", None)
            if fn is None:
                return {"error": "Không mở được hộp chọn thư mục ở chế độ này."}
            dest = fn()
            if not dest:
                return {"cancel": True}
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).lower()
        dest = os.path.abspath(dest)
        if dest.lower() == root or dest.lower().startswith(root + os.sep):
            return {"error": "Thư mục xuất SRT không được nằm trong thư mục mã của Trợ lý (chữ chép lời không vào git). Chọn thư mục khác."}
        with self._lock:
            rows = {r["key"]: r for r in st.clip_rows() if r["status"] == "done" and r["n_lines"]}
            codes = sx.clip_codes([r["key"] for r in st.clip_rows()])
            order = sorted([c for c in self._clips if c.rel in rows], key=lambda c: (c.t_start or _dt.datetime.min, c.rel))
            want = set(uids or [])

            def pack(c):
                return {"key": c.rel, "code": codes[c.rel], "dur": rows[c.rel]["dur"], "lines": st.lines_of(c.rel)}
            jobs = []
            if scope == "stages":
                groups = {}
                for c in order:
                    groups.setdefault(self._assign.get(c.uid), []).append(c)
                for i, s in enumerate(self._stages):
                    if i in groups:
                        jobs.append(("%02d %s.srt" % (i + 1, sx.safe_name(s["name"])), groups[i], True))
                if None in groups:
                    jobs.append(("99 Ngoài giai đoạn.srt", groups[None], True))
            elif scope == "selection":
                cs = [c for c in order if c.uid in want]
                if cs:
                    jobs.append(("Phần đã chọn (%d clip).srt" % len(cs), cs, True))
            else:
                cs = [c for c in order if c.uid in want][:1]
                if cs:
                    jobs.append(("%s.srt" % sx.safe_name(codes[cs[0].rel]), cs, False))
            if not jobs:
                return {"error": "Không có clip nào đã chép lời để xuất (chọn clip có chữ)."}
            os.makedirs(dest, exist_ok=True)
            files, skipped = [], 0
            stamp = _dt.datetime.now().strftime("%Y-%m-%d %H%M%S")
            for name, cs, cont in jobs:
                text, n, sk, _ = sx.build_srt([pack(c) for c in cs], continuous=cont)
                skipped += sk
                if not n:
                    continue
                path = os.path.join(dest, name)
                if os.path.exists(path):
                    path = os.path.join(dest, "%s (%s).srt" % (name[:-4], stamp))
                with open(path + ".tmp", "w", encoding="utf-8", newline="\r\n") as f:
                    f.write(text + "\n")
                os.replace(path + ".tmp", path)
                files.append({"name": os.path.basename(path), "clips": len(cs), "lines": n})
            if not files:
                return {"error": "Các clip này chỉ có dòng nghi bịa, không có gì để xuất."}
            return {"ok": True, "dir": dest, "files": files, "skipped_lines": skipped}

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

    # ------------------------------------------------------------------ PHÂN TÍCH CẢ PROJECT + TẮT MÁY (ADR-0017)
    def _speech_items(self):
        return [{"key": c.rel, "uid": c.uid, "name": c.name, "path": c.path, "tc": c.tc} for c in self._clips if c.rel]

    def _analyze_speech(self, stop_check):
        """Chép lời cả bin cho lượt "Phân tích cả project" (chạy ở luồng riêng, trả số liệu của SpeechRun)."""
        import troly_speech as sp
        import troly_speech_run as sr
        with self._lock:
            st = self._speech_store()
            cfg = self._speech_cfg()
            items = self._speech_items()
        if stop_check():
            return {"ok": False, "stopped": True, "message": "Đã dừng trước khi chép lời."}
        name, vad = sp.load_vad()
        if vad is None:
            return {"ok": False, "message": "Thiếu thư viện silero-vad."}
        phr = sp.load_phrases()
        run = sr.SpeechRun(st, vad_run=vad, index=sp.build_index(phr), prompt=phr.get("prompt"),
                           log_path=os.path.join(cfg["dir"], "loinoi.log"),
                           on_progress=lambda n, t: self._emit("speech_progress", {"n": n, "total": t}))
        with self._lock:
            self._speech_run = run
        try:
            return run.run(items, cfg.get("lang", "vi"))
        finally:
            with self._lock:
                self._speech_run = None

    def _wait_thumbs(self, stop_check, on_progress, stall_s=300):
        """Chờ thumbnail của MỌI clip xong (thumbnail tự chạy nền sau khi đọc clip). Trả (xong?, số đã xử lý, tổng).
        Dừng thì xong? = False; không có tiến triển quá stall_s giây cũng False."""
        last, t_last = -1, time.time()
        while True:
            self._pump_thumbs()
            with self._lock:
                total, done = len(self._clips), len(self._thumb_done)
            on_progress(done, total)
            if done >= total:
                return True, done, total
            if stop_check():
                return False, done, total
            if done != last:
                last, t_last = done, time.time()
            elif time.time() - t_last > stall_s:
                return False, done, total
            time.sleep(1.0)

    def _save_project(self):
        """SaveProject qua luồng DaVinci duy nhất; True chỉ khi DaVinci báo đã lưu."""
        box = {"event": threading.Event(), "ok": False}
        self._worker.jobs.put(("save_project", box))
        return bool(box["event"].wait(90) and box["ok"])

    def analyze_start(self, shutdown=False):
        """Nút "Phân tích cả project": chép lời cả bin -> làm sẵn thumbnail -> (nếu tick) lưu project DaVinci và tắt máy sau 2 phút
        đếm ngược có nút Huỷ. shutdown mặc định False. Báo qua sự kiện analyze_phase / analyze_countdown / analyze_done."""
        import troly_batch as tb
        with self._lock:
            if self._analyze is not None:
                return {"error": "Đang phân tích rồi."}
            if self._speech_run is not None:
                return {"error": "Đang chép lời rồi, hãy chờ hoặc dừng trước."}
            if not self._clips:
                return {"error": "Chưa có clip. Hãy bấm 'Đọc clip' trước."}
            if self._speech_store() is None:
                return {"error": "Chưa chọn thư mục kho lời nói."}
            an = tb.AnalyzeAll(self._analyze_speech, self._wait_thumbs, self._save_project, self._shutdown_fn, emit=self._emit,
                              countdown_s=self._analyze_countdown, sleep=self._analyze_sleep)
            self._analyze = an
            flag = bool(shutdown)
            n = len(self._speech_items())

        def go():
            try:
                an.run(flag)
            except Exception as e:                      # noqa: BLE001
                self._emit("analyze_done", {"ok": False, "error": str(e), "shutdown": "skipped", "reason": str(e)})
            finally:
                with self._lock:
                    self._analyze = None
        threading.Thread(target=go, daemon=True).start()
        return {"ok": True, "count": n, "shutdown": flag}

    def analyze_stop(self):
        """Dừng phân tích (và huỷ tắt máy): KHÔNG bao giờ tắt máy sau khi dừng."""
        with self._lock:
            if self._analyze is not None:
                self._analyze.stop = True
                self._analyze.cancel_shutdown = True
            if self._speech_run is not None:
                self._speech_run.stop = True
        return {"ok": True}

    def analyze_cancel_shutdown(self):
        """Nút Huỷ trong lúc đếm ngược: phân tích đã xong, chỉ huỷ việc tắt máy."""
        with self._lock:
            if self._analyze is not None:
                self._analyze.cancel_shutdown = True
        return {"ok": True}

    def analyze_state(self):
        with self._lock:
            return {"running": self._analyze is not None, "phase": self._analyze.phase if self._analyze else "idle"}

    def close(self):
        if self._play is not None:
            self._play.close()
        self._closed = True
        if self._analyze is not None:                    # đóng cửa sổ giữa chừng: dừng và KHÔNG tắt máy
            self._analyze.stop = True
            self._analyze.cancel_shutdown = True
        if self._speech_run is not None:
            self._speech_run.stop = True
        if self._ai_job is not None and self._ai_job.running():       # AI nền: gửi cờ dừng (dừng sau lô ảnh hiện tại, chạy lại thì làm tiếp)
            self._ai_job.stop()
        if self._save_timer:
            self._save_timer.cancel()
        self._save_now()
        self._thumbs.shutdown()
        self._worker.jobs.put(("quit", None))
        return True
