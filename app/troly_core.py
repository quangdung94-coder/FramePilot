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


SHOOT_STYLES = ("", "traditional", "psc")          # "" = chưa chọn (không đổi gì)
TRAD_HEAD_S, TRAD_TAIL_S = 1.5, 1.5               # Truyền thống: chỉ gợi ý cắt khoảng 1-2 giây đầu và đuôi mỗi clip


# --- Quy tắc gợi ý từng bin (ADR-0019) ---
# Bộ mặc định theo số đo thật (ADR-0021, anh duyệt 18/11/2026): p25–p75 độ dài anh giữ trên timeline thành phẩm, làm tròn 0,5s. Cột: từ khóa nhãn bin, chữ giải thích,
# giữ tối thiểu (giây), tối đa (giây; None = không giới hạn), trọn câu (giữ đến gần hết clip, không chặn tối đa).
BUILTIN_RULES = (
    (("decor", "chi tiết", "trang trí"), "Decor: 3.0s ổn định", 3.0, 3.0, False),
    (("phỏng vấn",), "Phỏng vấn: trích 4–8.5s", 4.0, 8.5, False),                 # ADR-0021: anh chỉ trích ~7s từ clip dài, không giữ trọn câu
    (("gia đình", "họ hàng"), "Gia đình: giữ 3–4s", 3.0, 4.0, False),
    (("beauty", "nhẫn"), "Beauty: 4.0s cảm xúc", 4.0, 4.0, False),                  # chưa có mẫu thật, giữ số cũ
    (("cô dâu", "chú rể"), "CD-CR: giữ 2–3s", 2.0, 3.0, False),
    (("chào bàn",), "Chào bàn: giữ 3–4s", 3.0, 4.0, False),
    (("nhà trai đến",), "Nhà trai đến: giữ 3–4.5s", 3.0, 4.5, False),
    (("khách",), "Khách: giữ 2.5–4s", 2.5, 4.0, False),
    (("nghi lễ", "gia tiên", "lễ"), "Nghi lễ: giữ 2.5–5s", 2.5, 5.0, False),
)
DEFAULT_RULE = ("Quy tắc v4: vào +1.2s, giữ 3s", 3.0, 3.0, False)
RULE_MAX_S = 600.0
OTHER_KEY = "*"                                   # dòng "Bin khác" của bảng: áp cho bin không khớp quy tắc có sẵn nào


def builtin_rule(label):
    """(chữ giải thích, min, max, trọn câu) mặc định của một nhãn bin."""
    lb = (label or "").lower()
    for keys, text, mn, mx, whole in BUILTIN_RULES:
        if any(k in lb for k in keys):
            return text, mn, mx, whole
    return DEFAULT_RULE


def _is_builtin(label):
    lb = (label or "").lower()
    return any(any(k in lb for k in keys) for keys, _t, _a, _b, _w in BUILTIN_RULES)


def check_bin_rule(mn, mx, whole=False):
    """Kiểm quy tắc người dùng nhập: số dương, min <= max. Trả (True, {'min','max','whole'}) hoặc (False, lời báo lỗi)."""
    try:
        mn = float(mn)
        mx = None if whole else float(mx)
    except (TypeError, ValueError):
        return False, "Số giây phải là số."
    for v in (mn,) if whole else (mn, mx):
        if v != v or v in (float("inf"), float("-inf")):
            return False, "Số giây phải là số."
        if v <= 0:
            return False, "Số giây phải lớn hơn 0."
        if v > RULE_MAX_S:
            return False, "Số giây tối đa là %d." % RULE_MAX_S
    if not whole and mn > mx:
        return False, "Tối thiểu không được lớn hơn tối đa."
    return True, {"min": round(mn, 2), "max": None if whole else round(mx, 2), "whole": bool(whole)}


def rule_for(label, rules=None):
    """Quy tắc áp cho nhãn bin: bin người dùng đã sửa > quy tắc có sẵn khớp từ khóa > dòng 'Bin khác' đã sửa > mặc định.
    Trả (chữ giải thích, min, max, trọn câu, đã_sửa)."""
    rules = rules or {}
    r = rules.get(label) if label else None
    if r is None and not _is_builtin(label):
        r = rules.get(OTHER_KEY)
    if r:
        ok, v = check_bin_rule(r.get("min"), r.get("max"), r.get("whole"))
        if ok:
            if v["whole"]:
                txt = "Quy tắc của anh: trọn câu, từ %gs" % v["min"]
            else:
                txt = "Quy tắc của anh: giữ %g–%gs" % (v["min"], v["max"]) if v["min"] != v["max"] else "Quy tắc của anh: giữ %gs" % v["min"]
            return txt, v["min"], v["max"], v["whole"], True
    t, mn, mx, whole = builtin_rule(label)
    return t, mn, mx, whole, False


def rules_view(plan, labels):
    """Bảng quy tắc để hiện: mỗi bin (theo thứ tự labels) + dòng 'Bin khác'. Chưa sửa thì ra đúng số mặc định."""
    rules = (plan or {}).get("bin_rules") or {}
    out = []
    for name in list(labels) + [None]:
        t, mn, mx, whole, ed = rule_for(name, rules)
        out.append({"name": name if name is not None else OTHER_KEY, "min": mn, "max": mx, "whole": whole, "edited": ed})
    return out


def suggest_inout(dur, label=None, style="", rules=None, trad_trim=None):
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
    if style == "traditional":
        # Truyền thống (ADR-0018): giữ source dài nhất có thể, chỉ cắt đầu và đuôi; không phân biệt bin. Clip ngắn thì cắt ít hơn
        # để vẫn còn ít nhất 1 giây. Số giây cắt chỉnh được (ADR-0019, mặc định 1.5). Chỉ là bộ tham số gợi ý (màu xanh).
        cut = TRAD_HEAD_S if trad_trim is None else max(0.0, float(trad_trim))
        head = tail = min(cut, max(0.0, (dur - 1.0) / 2.0))
        return {"in_s": round(head, 2), "out_s": round(dur - tail, 2), "dur": round(dur - head - tail, 2),
                "rule": "Truyền thống: giữ dài, cắt %.1fs đầu và %.1fs đuôi" % (head, tail)}
    rule, mn, mx, whole, _ed = rule_for(label, rules)
    if whole:
        trim = max(mn, dur - 1.0)
    else:
        trim = min(mx, max(mn, dur - 1.0))
        if mn == mx:
            trim = mn

    t_in = min(1.2, max(0.0, (dur - trim) / 2.0)) if dur < 5.0 else 1.2
    t_out = min(dur - 0.5, t_in + trim)
    if t_out <= t_in + 0.5:
        t_in = 0.0
        t_out = dur
    if style == "psc":                                 # PSC: clip ngắn 3-7 giây theo loại bin (bộ tham số hiện có), chỉ ghi rõ kiểu trong chữ giải thích
        rule = "PSC · " + rule
    return {"in_s": round(t_in, 2), "out_s": round(t_out, 2), "dur": round(t_out - t_in, 2), "rule": rule}


# --- In/Out (ADR-0016) -------------------------------------------------------------------------------------------------
# DaVinci SetMarkInOut/GetMarkInOut nhận SỐ FRAME tính từ ĐẦU FILE (frame 0 = frame đầu clip), KHÔNG cộng Start TC của file
# (đã đo thật, ADR-0016). Chuỗi timecode bị từ chối. Panel lưu giây (kế hoạch: plan["inout"][rel] = [in_s, out_s]).
def secs_to_frames(s, fps):
    return int(round(float(s) * float(fps)))


def frames_to_secs(f, fps):
    return round(int(f) / float(fps), 4)


def start_tc_frames(tc_str, fps):
    """'00:42:38:24' -> số frame (fps làm tròn). Chuỗi hỏng -> 0. Chỉ để HIỂN THỊ timecode của file, không dùng khi ghi."""
    m = re.match(r"^\s*(\d+)[:;](\d+)[:;](\d+)[:;.](\d+)\s*$", tc_str or "")
    if not m or not fps:
        return 0
    h, mi, se, fr = (int(x) for x in m.groups())
    nom = int(round(fps))
    return ((h * 60 + mi) * 60 + se) * nom + fr


def frames_to_tc(frames, fps):
    nom = max(1, int(round(fps or 25)))
    frames = max(0, int(frames))
    fr = frames % nom
    t = frames // nom
    return "%02d:%02d:%02d:%02d" % (t // 3600, (t // 60) % 60, t % 60, fr)


def tc_to_file_frame(tc_str, start_tc, fps):
    """Timecode hiển thị (đã gồm Start TC của file) -> frame tính từ đầu file (giá trị đưa cho SetMarkInOut)."""
    return start_tc_frames(tc_str, fps) - start_tc_frames(start_tc, fps)


def file_frame_to_tc(frame, start_tc, fps):
    return frames_to_tc(start_tc_frames(start_tc, fps) + int(frame), fps)


def clamp_inout(in_s, out_s, dur, fps=25.0):
    """Sắp xếp, kẹp trong [0, dur], làm tròn theo frame, giữ cách nhau >= 1 frame. dur không rõ (<=0) thì chỉ kẹp >= 0."""
    a, b = sorted((float(in_s), float(out_s)))
    step = 1.0 / float(fps or 25.0)
    a = max(0.0, a)
    if dur and dur > 0:
        a = min(a, max(0.0, dur - step))
        b = min(b, dur)
    b = max(b, a + step)
    if dur and dur > 0:
        b = min(b, dur)
        a = min(a, max(0.0, b - step))
    return round(round(a / step) * step, 4), round(round(b / step) * step, 4)


def manual_inout(plan, clip):
    v = (plan.get("inout") or {}).get(clip.rel)
    return (v[0], v[1]) if v and len(v) == 2 else None


def set_manual_inout(plan, clip, in_s, out_s):
    """Lưu In/Out đặt tay (giây). None -> xóa. Trả (in, out) đã kẹp, hoặc None."""
    d = plan.setdefault("inout", {})
    if in_s is None or out_s is None:
        d.pop(clip.rel, None)
        return None
    a, b = clamp_inout(in_s, out_s, clip.dur, clip.fps)
    d[clip.rel] = [a, b]
    return a, b


def effective_inout(plan, clip):
    """(in_s, out_s, nguồn): đặt tay trong panel LUÔN thắng, rồi In/Out đang có trong DaVinci; không có -> None.
    Gợi ý tự động (suggest_inout) không nằm ở đây, giao diện chỉ dùng khi chưa có gì."""
    m = manual_inout(plan, clip)
    if m:
        return m[0], m[1], "manual"
    if clip.mark_in is not None and clip.mark_out is not None and clip.fps:
        return frames_to_secs(clip.mark_in, clip.fps), frames_to_secs(clip.mark_out, clip.fps), "davinci"
    return None


def inout_frames(plan, clip):
    """Cặp frame (từ đầu file) sẽ ghi vào DaVinci cho clip: chỉ In/Out đặt tay. Không có -> None."""
    m = manual_inout(plan, clip)
    if not m or not clip.fps:
        return None
    fa, fb = secs_to_frames(m[0], clip.fps), secs_to_frames(m[1], clip.fps)
    if clip.frames:
        fb = min(fb, clip.frames - 1)
    if fb <= fa:
        return None
    return fa, fb


def inout_backup_dir(data_root):
    return os.path.join(data_root, "troly", "inout_backup")


def write_inout_backup(data_root, project, entries, stamp=None):
    """Sao lưu In/Out CŨ của các clip trước khi ghi. entries = [{uid, rel, in, out}] (frame hoặc None).
    File riêng có ngày giờ, không ghi đè file cũ. Trả đường dẫn."""
    import datetime as _dt
    d = inout_backup_dir(data_root)
    os.makedirs(d, exist_ok=True)
    stamp = stamp or _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(d, "%s_%s" % (_safe(project), stamp))
    p, i = base + ".json", 1
    while os.path.exists(p):
        i += 1
        p = "%s_%d.json" % (base, i)
    _write_json(p, {"project": project, "at": _dt.datetime.now().isoformat(timespec="seconds"), "entries": entries,
                    "restored": False})
    return p


def read_inout_backup(path):
    return _read_json(path)


def latest_inout_backup(data_root, project):
    d = inout_backup_dir(data_root)
    try:
        names = sorted(n for n in os.listdir(d) if n.startswith(_safe(project) + "_") and n.endswith(".json"))
    except OSError:
        return None
    for n in reversed(names):
        data = _read_json(os.path.join(d, n))
        if data and not data.get("restored"):
            return os.path.join(d, n)
    return None


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
    dur = plan.get("durations")                          # Bước 5: tỉ lệ giai đoạn và Min-Max bin theo TÊN
    if isinstance(dur, dict) and not dup:
        if kind == "stage":
            sh = dur.get("stage_share")
            if isinstance(sh, dict) and old in sh:
                sh[new] = sh.pop(old)
            bb = dur.get("bins")
            if isinstance(bb, dict) and old in bb:
                bb[new] = bb.pop(old)
        else:
            sub = (dur.get("bins") or {}).get(stage_old)
            if isinstance(sub, dict) and old in sub:
                sub[new] = sub.pop(old)
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


# --- Nhật ký tạo timeline cắt gọt (Bước 5, ADR-0013) ---------------------------------------------------------------------
def timeline_log_dir(data_root):
    return os.path.join(data_root, "troly", "timeline_log")


def write_timeline_log(data_root, project, record, stamp=None):
    """Ghi nhật ký TRƯỚC khi tạo timeline (số clip, tổng giây, từng đoạn In/Out). File riêng có ngày giờ, không ghi đè. Trả đường dẫn."""
    d = timeline_log_dir(data_root)
    os.makedirs(d, exist_ok=True)
    stamp = stamp or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(d, "%s_%s" % (_safe(project), stamp))
    p, i = base + ".json", 1
    while os.path.exists(p):
        i += 1
        p = "%s_%d.json" % (base, i)
    _write_json(p, record)
    return p


def cut_frames(in_s, out_s, fps, frames):
    """Đoạn cắt (giây) -> (startFrame, endFrame) cho clipInfo của DaVinci, tính từ ĐẦU FILE. ĐO THẬT 18/11/2026 (DaVinci Resolve Studio 21.1.1):
    độ dài trên timeline = endFrame - startFrame (endFrame là điểm kết thúc, không tính frame đó), nên endFrame = round(ra × fps).
    Kẹp endFrame <= frames - 1 (an toàn, mất tối đa 1 frame ở cuối clip); ra > vào."""
    a = max(0, secs_to_frames(in_s, fps))
    b = secs_to_frames(out_s, fps)
    if frames:
        b = min(b, int(frames) - 1)
        a = min(a, max(0, int(frames) - 2))
    return a, max(a + 1, b)
