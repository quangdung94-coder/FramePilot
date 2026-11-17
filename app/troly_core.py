"""
troly_core.py - Lõi của "Trợ lý File Quay" (ADR-0009, hướng mới chốt 15/11/2026). KHÔNG gọi DaVinci, không vẽ giao diện.

Việc của file này:
  1. Đọc GIỜ QUAY thật của từng clip từ thông tin DaVinci đưa ra (Date Created / Date Modified / độ dài).
     Đo 15/11/2026 trên Sony A7S III: "Date Created" = lúc bấm quay, "Date Modified" = lúc dừng quay.
     Start TC của máy KHÔNG phải giờ thật (lệch nhiều giờ) nên không dùng.
  2. Chia ngày quay thành GIAI ĐOẠN (Rước dâu, Gia tiên, ...) theo khoảng giờ người dựng tự kéo; gợi ý ban đầu bằng
     các khoảng nghỉ quay dài nhất.
  3. Mẫu sự kiện (bộ giai đoạn + bin con), lưu kế hoạch của từng project và NHÃN phân loại (dữ liệu để AI học sau).

Giờ trong file này tính bằng PHÚT kể từ 0:00 của ngày quay ĐẦU TIÊN (ngày thứ hai = 1440 + ...), để một project quay
nhiều ngày vẫn nằm trên một thanh thời gian.
"""
import datetime
import hashlib
import json
import os
import re
import shutil

SCHEMA = 1

# ---------------------------------------------------------------------------
# GIỜ QUAY
# ---------------------------------------------------------------------------
_MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                        "dec"])}
_TIME = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})$")


def parse_resolve_date(s):
    """Đọc chuỗi ngày giờ của DaVinci, không phụ thuộc ngôn ngữ Windows (strptime %b hỏng khi Tk đổi locale).
    Nhận cả hai kiểu đã thấy: 'Sat Oct 17 2026 06:25:28' (Date Created) và 'Sat Oct 17 06:25:33 2026' (Date Modified),
    ngày một chữ số 'Thu Nov 5 2026 11:52:05'. Trả về datetime hoặc None."""
    if not s:
        return None
    parts = str(s).replace(",", " ").split()
    mon = day = year = None
    hms = None
    for p in parts:
        low = p.lower()[:3]
        if low in _MON and mon is None:
            mon = _MON[low]
        elif _TIME.match(p):
            hms = tuple(int(x) for x in _TIME.match(p).groups())
        elif p.isdigit():
            v = int(p)
            if len(p) == 4:
                year = v
            elif day is None and 1 <= v <= 31:
                day = v
    if not (mon and day and year and hms):
        # dạng ISO 2026-10-17T06:25:28 (ffprobe) hoặc 2026-10-17 06:25:28
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})", str(s))
        if not m:
            return None
        y, mo, d, h, mi, se = (int(x) for x in m.groups())
        return datetime.datetime(y, mo, d, h, mi, se)
    try:
        return datetime.datetime(year, mon, day, *hms)
    except ValueError:
        return None


def clip_duration_s(props):
    """Độ dài clip (giây) từ Frames / FPS; dự phòng Duration dạng HH:MM:SS:FF."""
    try:
        fps = float(props.get("FPS") or 0)
        frames = float(props.get("Frames") or 0)
        if fps > 0 and frames > 0:
            return frames / fps
    except (TypeError, ValueError):
        pass
    d = str(props.get("Duration") or "")
    m = re.match(r"(\d+):(\d+):(\d+)[:;](\d+)", d)
    if m:
        h, mi, s, f = (int(x) for x in m.groups())
        fps = float(props.get("FPS") or 25) or 25
        return h * 3600 + mi * 60 + s + f / fps
    return 0.0


def shoot_time(props, tolerance_s=15):
    """Giờ BẮT ĐẦU quay của clip + nguồn của giờ đó.

    - created = Date Created; end_based = Date Modified - độ dài.
    - Hai giờ khớp nhau (lệch <= tolerance_s): tin "Date Created" (nguồn 'created').
    - Không khớp: thường do file đã được chép lại (Windows đổi giờ tạo, giữ giờ sửa) -> dùng giờ sửa trừ độ dài
      (nguồn 'modified').
    - Chỉ có một trong hai: dùng cái có. Không có gì: (None, 'none').
    """
    created = parse_resolve_date(props.get("Date Created"))
    modified = parse_resolve_date(props.get("Date Modified"))
    dur = clip_duration_s(props)
    end_based = modified - datetime.timedelta(seconds=dur) if modified else None
    if created and end_based:
        if abs((created - end_based).total_seconds()) <= tolerance_s:
            return created, "created"
        return end_based, "modified"
    if created:
        return created, "created"
    if end_based:
        return end_based, "modified"
    return None, "none"


def camera_key(props):
    """Nhận biết MÁY QUAY của clip để chỉnh lệch giờ theo từng máy.
    Ưu tiên số serial / tên máy DaVinci đọc được; không có thì dùng tiền tố tên file (DG4939 -> DG) + độ phân giải."""
    for k in ("Camera Serial #", "Camera ID", "Camera Type", "Camera #"):
        v = (props.get(k) or "").strip()
        if v:
            return v
    name = os.path.splitext(props.get("File Name") or "")[0]
    m = re.match(r"^([A-Za-z_\-]*[A-Za-z])", name)
    prefix = m.group(1).upper().rstrip("_-") if m else "?"
    return "%s %s" % (prefix, props.get("Resolution") or "")


def minutes_of(dt, day0):
    """Phút kể từ 0:00 của ngày day0 (date)."""
    base = datetime.datetime.combine(day0, datetime.time())
    return (dt - base).total_seconds() / 60.0


def fmt_min(m, with_day=True):
    """Phút -> 'HH:MM' ('+1' khi sang ngày sau)."""
    m = int(round(m))
    d, r = divmod(m, 1440)
    s = "%02d:%02d" % divmod(r, 60)
    return s + (" (+%d)" % d if with_day and d else "")


def parse_hhmm(s, ref_day=0):
    """'7:30' / '07:30' / '0730' -> phút (cộng ref_day*1440). Hỏng thì ValueError."""
    t = str(s).strip().split("(")[0].strip()
    m = re.match(r"^(\d{1,2})[:hH\.]?(\d{2})$", t)
    if not m:
        raise ValueError("Giờ không hợp lệ: %r (viết kiểu 07:30)" % s)
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise ValueError("Giờ không hợp lệ: %r" % s)
    return ref_day * 1440 + h * 60 + mi


class Clip(object):
    """Một clip trong media pool, chỉ giữ những gì Trợ lý cần."""

    __slots__ = ("uid", "name", "path", "proxy", "lut", "dur", "fps", "frames", "t_start", "t_src", "camera",
                 "bin_path", "clip_color", "rel", "mark_in", "mark_out", "tc")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def to_dict(self):
        d = {k: getattr(self, k) for k in self.__slots__}
        d["t_start"] = self.t_start.isoformat() if self.t_start else None
        return d

    @classmethod
    def from_props(cls, uid, props, bin_path="", mark_in=None, mark_out=None):
        t, src = shoot_time(props)
        path = props.get("File Path") or ""
        return cls(uid=uid, name=props.get("File Name") or props.get("Clip Name") or "", path=path,
                   proxy=props.get("Proxy Media Path") or "", lut=props.get("Input LUT") or "",
                   dur=clip_duration_s(props), fps=float(props.get("FPS") or 0) or None,
                   frames=int(float(props.get("Frames") or 0)), t_start=t, t_src=src, camera=camera_key(props),
                   bin_path=bin_path, clip_color=props.get("Clip Color") or "", rel=rel_path(path),
                   mark_in=mark_in, mark_out=mark_out, tc=props.get("Start TC") or "")


def suggest_inout(dur, label=None):
    """Gợi ý in/out (giây) theo quy tắc ADR-0004 kết hợp nhãn phân loại bin con:
    - Decor / Chi tiết: cần đoạn 2.5 - 3.5s ổn định, bỏ 1s đầu bấm máy.
    - Cô dâu chú rể / Beauty: cần đoạn 3.5 - 4.5s khoảnh khắc đẹp.
    - Nghi lễ / Gia tiên: giữ đoạn dài 5 - 8s (hoặc gần hết clip nếu ngắn).
    - Phỏng vấn: giữ trọn câu nói.
    - Mặc định (ADR-0004 v4): vào 1.2s, ra = vào + 3.0s, cách cuối >= 1.0s.
    """
    dur = float(dur or 0)
    if dur < 1.0:
        return None
    lb = (label or "").lower()
    if any(k in lb for k in ("decor", "chi tiết", "trang trí")):
        trim = 3.0
        rule = "Decor: 3.0s ổn định"
    elif any(k in lb for k in ("cô dâu", "chú rể", "beauty", "nhẫn")):
        trim = 4.0
        rule = "CD-CR: 4.0s cảm xúc"
    elif any(k in lb for k in ("nghi lễ", "gia tiên", "lễ", "chào bàn", "đón khách")):
        trim = min(7.0, max(3.0, dur - 1.0))
        rule = "Nghi lễ: giữ 5–7s"
    elif "phỏng vấn" in lb:
        trim = max(3.0, dur - 1.0)
        rule = "Phỏng vấn: giữ trọn câu"
    else:
        trim = 3.0
        rule = "Quy tắc v4: vào +1.2s, giữ 3s"

    t_in = min(1.2, max(0.0, (dur - trim) / 2.0)) if dur < 5.0 else 1.2
    t_out = min(dur - 0.5, t_in + trim)
    if t_out <= t_in + 0.5:
        t_in = 0.0
        t_out = dur
    return {"in_s": round(t_in, 2), "out_s": round(t_out, 2), "dur": round(t_out - t_in, 2), "rule": rule}


PROJECT_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.")


def rel_path(path):
    """Đường dẫn TƯƠNG ĐỐI từ thư mục project (CLAUDE.md): J:\\..\\2026.10.17.LV_X\\01_footage\\DG1.MP4 -> 01_footage/DG1.MP4."""
    parts = (path or "").replace("\\", "/").split("/")
    for i, p in enumerate(parts):
        if PROJECT_RE.match(p):
            return "/".join(parts[i + 1:])
    return "/".join(parts[-2:])


def day0_of(clips):
    ts = [c.t_start for c in clips if c.t_start]
    return min(ts).date() if ts else datetime.date.today()


def clip_minutes(clip, day0, offsets=None):
    """(phút bắt đầu, phút kết thúc) của clip trên thanh thời gian, đã cộng lệch giờ của máy (giây)."""
    if not clip.t_start:
        return None
    off = (offsets or {}).get(clip.camera, 0) or 0
    a = minutes_of(clip.t_start, day0) + off / 60.0
    return a, a + (clip.dur or 0) / 60.0


# ---------------------------------------------------------------------------
# MẪU SỰ KIỆN
# ---------------------------------------------------------------------------
PALETTE = ["#F2A33A", "#5B9BF5", "#4FC1A6", "#C98BE0", "#EF7D65", "#A9CF62", "#E88AB0", "#E0B860", "#7FB7E8",
           "#B89A7A"]
OTHER_BIN = "Khác"

BUILTIN_TEMPLATES = {
    "Cưới đầy đủ (sáng lễ, tối tiệc)": [
        ("Chuẩn bị nhà gái", ["Decor", "Beauty cô dâu", "Gia đình cô dâu", "Phỏng vấn"]),
        ("Rước dâu", ["Nhà trai đến", "Trao lễ vật", "Cô dâu chú rể", "Gia đình"]),
        ("Gia tiên", ["Decor", "Nghi lễ", "Cô dâu chú rể", "Gia đình", "Phỏng vấn"]),
        ("Đón dâu về nhà trai", ["Decor", "Nghi lễ", "Cô dâu chú rể", "Gia đình"]),
        ("Đón khách", ["Decor", "Cô dâu chú rể", "Khách", "Gia đình"]),
        ("Lễ nhà hàng", ["Sân khấu", "Nghi lễ", "Phát biểu", "Cô dâu chú rể", "Khách"]),
        ("Chào bàn", ["Cô dâu chú rể", "Khách"]),
    ],
    "Lễ gia tiên (một buổi)": [
        ("Chuẩn bị", ["Decor", "Beauty cô dâu", "Chú rể", "Gia đình", "Phỏng vấn"]),
        ("Rước dâu", ["Nhà trai đến", "Trao lễ vật", "Cô dâu chú rể", "Gia đình"]),
        ("Gia tiên", ["Decor", "Nghi lễ", "Cô dâu chú rể", "Gia đình", "Phỏng vấn"]),
        ("Kết thúc", ["Cô dâu chú rể", "Gia đình"]),
    ],
    "Tiệc nhà hàng": [
        ("Đón khách", ["Decor", "Cô dâu chú rể", "Khách", "Gia đình"]),
        ("Lễ nhà hàng", ["Sân khấu", "Nghi lễ", "Phát biểu", "Cô dâu chú rể", "Khách"]),
        ("Chào bàn", ["Cô dâu chú rể", "Khách"]),
    ],
}
DEFAULT_TEMPLATE = "Cưới đầy đủ (sáng lễ, tối tiệc)"


def make_stage(name, start, end, bins, idx):
    bins = [b for b in bins if b and b != OTHER_BIN] + [OTHER_BIN]
    return {"name": name, "start": float(start), "end": float(end), "color": PALETTE[idx % len(PALETTE)],
            "bins": bins}


def templates(data_root):
    """Mẫu có sẵn + mẫu người dựng đã lưu (data_root/troly/templates.json, ghi đè mẫu cùng tên)."""
    out = {k: [(n, list(b)) for n, b in v] for k, v in BUILTIN_TEMPLATES.items()}
    p = os.path.join(data_root, "troly", "templates.json") if data_root else None
    if p and os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                for k, v in (json.load(f) or {}).items():
                    out[k] = [(s["name"], list(s.get("bins") or [])) for s in v]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return out


def save_template(data_root, name, stages):
    p = os.path.join(data_root, "troly", "templates.json")
    d = {}
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f) or {}
        except (OSError, ValueError):
            d = {}
    d[name] = [{"name": s["name"], "bins": [b for b in s["bins"] if b != OTHER_BIN]} for s in stages]
    _write_json(p, d)


# ---------------------------------------------------------------------------
# CHIA GIAI ĐOẠN
# ---------------------------------------------------------------------------
def spans(clips, day0, offsets=None):
    """[(phút đầu, phút cuối, clip)] xếp theo giờ, bỏ clip không có giờ."""
    out = []
    for c in clips:
        m = clip_minutes(c, day0, offsets)
        if m:
            out.append((m[0], m[1], c))
    out.sort(key=lambda x: x[0])
    return out


def gaps(clips, day0, offsets=None):
    """Các khoảng NGHỈ QUAY giữa hai clip liên tiếp: [(độ dài phút, phút kết thúc clip trước, phút bắt đầu clip sau)]."""
    sp = spans(clips, day0, offsets)
    out = []
    end = None
    for a, b, _ in sp:
        if end is not None and a > end:
            out.append((a - end, end, a))
        end = b if end is None else max(end, b)
    return out


def suggest_stages(clips, day0, template, offsets=None, min_gap=3.0, pad=1.0):
    """Gợi ý giai đoạn ban đầu: cắt ở (số giai đoạn - 1) khoảng nghỉ DÀI NHẤT (>= min_gap phút), giai đoạn thứ i lấy
    tên thứ i của mẫu. Ít khoảng nghỉ hơn số giai đoạn thì các giai đoạn còn lại để trống (độ dài 0, người dựng tự kéo).
    Người dựng luôn chỉnh lại bằng tay trên thanh thời gian; đây chỉ là điểm xuất phát."""
    sp = spans(clips, day0, offsets)
    n = len(template)
    if not sp or not n:
        return [make_stage(name, 0, 0, bins, i) for i, (name, bins) in enumerate(template)]
    gs = [g for g in gaps(clips, day0, offsets) if g[0] >= min_gap]
    cuts = sorted(gs, key=lambda g: -g[0])[:max(0, n - 1)]
    cuts = sorted(cuts, key=lambda g: g[1])
    bounds = []
    lo = sp[0][0]
    for g in cuts:
        bounds.append((lo, g[1]))
        lo = g[2]
    bounds.append((lo, max(b for _, b, _ in sp)))
    out = []
    for i, (name, bins) in enumerate(template):
        if i < len(bounds):
            a, b = bounds[i]
            out.append(make_stage(name, max(0.0, a - pad), b + pad, bins, i))
        else:
            last = out[-1]["end"] if out else sp[-1][1]
            out.append(make_stage(name, last, last, bins, i))
    return out


def stage_of(minute, stages):
    """Chỉ số giai đoạn chứa phút này (giai đoạn sau thắng khi hai khoảng chạm nhau), không có thì None."""
    hit = None
    for i, s in enumerate(stages):
        if s["start"] <= minute < s["end"] or (s["start"] == s["end"] == minute):
            hit = i
    return hit


def assign(clips, stages, day0, offsets=None, manual=None):
    """{uid: chỉ số giai đoạn hoặc None}. Giai đoạn CHỌN TAY (manual: {khóa clip: {'stage': tên}}) thắng giai đoạn tính
    theo giờ BẮT ĐẦU của clip, nên kéo lại mốc giờ ở thẻ 1 không làm mất. Tên giai đoạn chọn tay không còn (đã xóa)
    thì quay về tính theo giờ."""
    idx = {s["name"]: i for i, s in enumerate(stages)}
    out = {}
    for c in clips:
        man = (manual or {}).get(clip_key(c))
        if man and man.get("stage") in idx:
            out[c.uid] = idx[man["stage"]]
            continue
        m = clip_minutes(c, day0, offsets)
        out[c.uid] = stage_of(m[0], stages) if m else None
    return out


def clip_key(clip):
    """Khóa của clip trong kế hoạch (nhãn, chọn tay): đường dẫn tương đối, bền khi project chuyển ổ."""
    return clip.rel or clip.name


def set_manual(plan, clip, stage_name, by="nguoi"):
    """Người dựng CHỌN TAY giai đoạn cho clip (Shift+số, kéo thả). stage_name None = bỏ chọn tay (tính lại theo giờ)."""
    man = plan.setdefault("manual", {})
    if stage_name is None:
        man.pop(clip_key(clip), None)
        return
    man[clip_key(clip)] = {"uid": clip.uid, "stage": stage_name, "by": by,
                           "at": datetime.datetime.now().isoformat(timespec="seconds")}


def manual_of(plan, clip):
    return (plan.get("manual") or {}).get(clip_key(clip))


def counts(assignment, n_stages):
    cnt = [0] * n_stages
    outside = 0
    for v in assignment.values():
        if v is None:
            outside += 1
        else:
            cnt[v] += 1
    return cnt, outside


# ---------------------------------------------------------------------------
# LƯU KẾ HOẠCH + NHÃN PHÂN LOẠI
# ---------------------------------------------------------------------------
def _safe(name):
    """Tên project -> tên file an toàn trên Windows. Chỉ đổi ký tự cấm (<>:"/\\|?*) và dấu chấm/khoảng trắng cuối tên.
    '&', dấu tiếng Việt, khoảng trắng giữa tên đều hợp lệ nên giữ nguyên."""
    out = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).rstrip(" .")
    return out or "project"


_HEAD_PROJECT = re.compile(r'"project"\s*:\s*("(?:[^"\\]|\\.)*")')
_HEAD_UID = re.compile(r'"project_uid"\s*:\s*("(?:[^"\\]|\\.)*")')


def _head_value(path, rx):
    """Đọc nhanh một giá trị chuỗi ở đầu file JSON (không nạp cả file)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            m = rx.search(f.read(4096))
        return json.loads(m.group(1)) if m else None
    except (OSError, ValueError):
        return None


def plan_path(data_root, project):
    """Đường dẫn file kế hoạch. Hai project có tên khác nhau nhưng cùng tên file sau khi đổi ký tự cấm (a:b và a|b)
    thì project đến sau dùng thêm đuôi băm, để không ghi đè kế hoạch của project kia."""
    d = os.path.join(data_root, "troly", "projects")
    p = os.path.join(d, _safe(project) + ".json")
    owner = _head_value(p, _HEAD_PROJECT) if os.path.isfile(p) else None
    if owner is not None and owner != project:
        p = os.path.join(d, "%s~%s.json" % (_safe(project), hashlib.sha1(project.encode("utf-8")).hexdigest()[:8]))
    return p


def _write_json(p, d):
    """Ghi NGUYÊN TỬ: ghi file tạm, ép xuống đĩa, giữ bản trước làm .bak, rồi đổi tên. Mất điện/tắt máy giữa chừng thì
    file cũ vẫn nguyên."""
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    if os.path.isfile(p) and _read_json(p) is not None:           # chỉ giữ làm .bak khi file hiện tại còn đọc được
        shutil.copyfile(p, p + ".bak")
    os.replace(tmp, p)


def _read_json(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def new_plan(project):
    return {"schema": SCHEMA, "project": project, "project_uid": None, "source_bin": None, "template": DEFAULT_TEMPLATE,
            "stages": [], "offsets": {}, "labels": {}, "manual": {}, "moves": [], "stars": {}, "ui": {}, "seen": [], "updated": None}


def is_starred(plan, clip):
    return bool((plan.get("stars") or {}).get(clip.rel))


def toggle_star(plan, clip):
    stars = plan.setdefault("stars", {})
    if stars.get(clip.rel):
        stars.pop(clip.rel, None)
        return False
    stars[clip.rel] = True
    return True


def load_plan(data_root, project):
    """Nạp kế hoạch của project. File chính hỏng thì GIỮ NGUYÊN file hỏng (đổi tên .corrupt-<giờ>) rồi nạp .bak; cả hai hỏng
    mới trả kế hoạch rỗng. Không bao giờ để lần lưu sau ghi đè mất file hỏng. plan['_note'] ghi chú việc đã làm (không lưu)."""
    p = plan_path(data_root, project)
    note = None
    d = _read_json(p) if os.path.isfile(p) else None
    if d is None and os.path.isfile(p):
        keep = "%s.corrupt-%s" % (p, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        try:
            os.replace(p, keep)
            note = "File kế hoạch bị hỏng, đã giữ lại bản hỏng: %s" % os.path.basename(keep)
        except OSError:
            note = "File kế hoạch bị hỏng."
    if d is None and os.path.isfile(p + ".bak"):
        d = _read_json(p + ".bak")
        if d is not None:
            note = (note or "File kế hoạch không đọc được") + "; đã nạp lại từ bản sao .bak."
    base = new_plan(project)
    if d:
        base.update(d)
        base["project"] = project
    if note:
        base["_note"] = note
    return base


def save_plan(data_root, plan):
    plan["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    out = {k: v for k, v in plan.items() if not k.startswith("_")}
    _write_json(plan_path(data_root, plan["project"]), out)


def find_plan_by_uid(data_root, uid, exclude_project=None):
    """Kế hoạch của project có cùng GetUniqueId nhưng tên khác (project đã đổi tên trong DaVinci). Trả (đường dẫn, dict)."""
    if not uid:
        return None, None
    d = os.path.join(data_root, "troly", "projects")
    if not os.path.isdir(d):
        return None, None
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(d, fn)
        if _head_value(p, _HEAD_UID) == uid:
            plan = _read_json(p)
            if plan and plan.get("project") != exclude_project:
                return p, plan
    return None, None


def set_label(plan, clip, stage_name, bin_name, by="nguoi"):
    """Ghi NHÃN của một clip (dữ liệu để AI học sau): khóa là đường dẫn tương đối (bền khi project chuyển ổ)."""
    key = clip.rel or clip.name
    if bin_name is None:
        plan["labels"].pop(key, None)
        return
    plan["labels"][key] = {"uid": clip.uid, "stage": stage_name, "bin": bin_name, "by": by,
                           "t": clip.t_start.isoformat() if clip.t_start else None,
                           "at": datetime.datetime.now().isoformat(timespec="seconds")}


def label_of(plan, clip):
    return plan["labels"].get(clip.rel or clip.name)


# ---------------------------------------------------------------------------
# ĐỔI TÊN GIAI ĐOẠN / BIN CON (ADR-0015)
# ---------------------------------------------------------------------------
NAME_FORBIDDEN = ':&/\*?"<>|'          # ký tự cấm của tên timeline/bin (CLAUDE.md)
NAME_MAX = 60


def check_new_name(new, siblings, current=None):
    """Kiểm tên mới. Trả (tên đã gọn khoảng trắng, lỗi hoặc None). siblings = tên các bin cùng cấp; current = tên đang đổi
    (không tính là trùng với chính nó). Không để trống, không ký tự cấm, không trùng tên khác trong cùng cấp (không phân biệt hoa thường)."""
    n = " ".join((new or "").split())
    if not n:
        return n, "Tên không được để trống."
    bad = [c for c in NAME_FORBIDDEN if c in n]
    if bad:
        return n, "Tên không được chứa các ký tự: %s" % " ".join(bad)
    if len(n) > NAME_MAX:
        return n, "Tên dài quá %d ký tự." % NAME_MAX
    for s in siblings:
        if s != current and s.casefold() == n.casefold():
            return n, "Đã có tên “%s” trong cùng cấp." % s
    return n, None


def bin_prefix(src, i, stage_name, bin_name=None):
    """Đường bin trong Media Pool: <bin nguồn>/NN_<giai đoạn>[/<bin con>]."""
    p = "%s/%02d_%s" % (src or "", i + 1, stage_name)
    return p + "/" + bin_name if bin_name else p


def rename_in_plan(plan, kind, i, old, new, in_stage_keys=()):
    """Đổi tên trong MỌI nơi kế hoạch lưu tên: stages, labels, manual và trạng thái giao diện (ui). NHẬT KÝ CHUYỂN (moves) giữ
    nguyên vì nó ghi bin THẬT trong Media Pool, nơi tên cũ vẫn còn cho tới khi anh bấm Áp dụng.
    kind = 'stage' (old là tên giai đoạn i) hoặc 'bin' (old là tên bin con của giai đoạn i). Phím 1-9 theo VỊ TRÍ bin nên giữ nguyên.
    Hai giai đoạn trùng tên: chỉ nhãn của clip đang thuộc giai đoạn i (in_stage_keys) được đổi; không trùng thì đổi hết,
    kể cả clip chưa nạp. Trả (đường bin cũ, đường bin mới) theo kế hoạch."""
    st = plan["stages"][i]
    stage_old = st["name"]
    dup = sum(1 for s in plan["stages"] if s["name"] == stage_old) > 1
    keys = set(in_stage_keys)

    def mine(key):
        return (not dup) or key in keys
    src = plan.get("source_bin") or ""
    labels, manual = plan.get("labels") or {}, plan.get("manual") or {}
    if kind == "stage":
        for key, lab in labels.items():
            if lab.get("stage") == old and mine(key):
                lab["stage"] = new
        for key, lab in manual.items():
            if lab.get("stage") == old and mine(key):
                lab["stage"] = new
        st["name"] = new
        p_old, p_new = bin_prefix(src, i, old), bin_prefix(src, i, new)
    else:
        st["bins"][st["bins"].index(old)] = new          # cùng VỊ TRÍ nên phím số không đổi
        for key, lab in labels.items():
            if lab.get("stage") == stage_old and lab.get("bin") == old and mine(key):
                lab["bin"] = new
        p_old, p_new = bin_prefix(src, i, stage_old, old), bin_prefix(src, i, stage_old, new)
        ui = plan.get("ui") or {}
        if ui.get("gStage") == i and ui.get("gSub") == old:
            ui["gSub"] = new
    return p_old, p_new


def target_folder(clip_stage, clip_label, stages, clip_manual=None):
    """Đường bin đích (tương đối với bin nguồn) cho một clip: ['01_Rước dâu', 'Decor'] / ['01_Rước dâu'] / [] (giữ nguyên).
    clip_manual (giai đoạn chọn tay, nếu có) THẮNG clip_stage tính theo giờ.
    Nhãn chỉ áp khi nó thuộc ĐÚNG giai đoạn hiện tại của clip (người dựng kéo lại giờ thì nhãn cũ không kéo clip sai bin)."""
    if clip_manual:
        clip_stage = next((i for i, s in enumerate(stages) if s["name"] == clip_manual.get("stage")), clip_stage)
    if clip_stage is None:
        return []
    s = stages[clip_stage]
    top = "%02d_%s" % (clip_stage + 1, s["name"])
    if clip_label and clip_label.get("stage") == s["name"] and clip_label.get("bin") in s["bins"]:
        return [top, clip_label["bin"]]
    return [top]


def keymap(stage):
    """Phím số -> bin con của giai đoạn: 1..9 theo thứ tự bin."""
    return {str(i + 1): b for i, b in enumerate(stage["bins"][:9])}
