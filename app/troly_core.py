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
    name = re.sub(r"^\d{6,8}[_\-\s]?", "", name)                  # bỏ ngày ở đầu tên: 20261114_HM1947 -> HM1947
    m = re.match(r"^([A-Za-z_\-]*[A-Za-z])", name)
    prefix = m.group(1).upper().rstrip("_-") if m else "Máy"
    return ("%s %s" % (prefix, props.get("Resolution") or "")).strip()


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
                 "bin_path", "clip_color", "rel", "mark_in", "mark_out", "tc", "size", "rot",
                 "tl_mode", "tl_pos", "tl_dur", "tl_track", "tl_n")

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
        import troly_src
        try:
            rot = int(float(props.get("Rotation") or props.get("Video Rotation") or 0))
        except (TypeError, ValueError):
            rot = 0
        return cls(size=troly_src.parse_size(props.get("Resolution")), rot=rot, uid=uid, name=props.get("File Name") or props.get("Clip Name") or "", path=path,
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
    (("chúc thọ", "phát biểu"), "Phát biểu/Chúc thọ: trích 4–8.5s", 4.0, 8.5, False),
    (("gia đình", "họ hàng"), "Gia đình: giữ 3–4s", 3.0, 4.0, False),
    (("beauty", "nhẫn"), "Beauty: 4.0s cảm xúc", 4.0, 4.0, False),                  # chưa có mẫu thật, giữ số cũ
    (("cô dâu", "chú rể"), "CD-CR: giữ 2–3s", 2.0, 3.0, False),
    (("cụ ông", "cụ bà", "ông bà"), "Cụ ông bà: giữ 2.5–4s", 2.5, 4.0, False),
    (("trao quà", "mừng thọ"), "Trao quà/Mừng thọ: giữ 3–5s", 3.0, 5.0, False),
    (("văn nghệ",), "Văn nghệ: giữ 3–4.5s", 3.0, 4.5, False),
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
                txt = "Quy tắc của bạn: trọn câu, từ %gs" % v["min"]
            else:
                txt = "Quy tắc của bạn: giữ %g–%gs" % (v["min"], v["max"]) if v["min"] != v["max"] else "Quy tắc của bạn: giữ %gs" % v["min"]
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


TRAD_MAX_S = 600.0


def check_trad(head, tail):
    """Kiểm số giây cắt ĐẦU và ĐUÔI (kiểu Truyền thống) anh nhập: số, không âm, tối đa 600. Trả (True, (đầu, đuôi)) hoặc (False, lời báo)."""
    try:
        h, t = float(head), float(tail)
    except (TypeError, ValueError):
        return False, "Số giây cắt phải là số."
    for v in (h, t):
        if v != v or v in (float("inf"), float("-inf")):
            return False, "Số giây cắt phải là số."
        if v < 0:
            return False, "Số giây cắt không được âm."
        if v > TRAD_MAX_S:
            return False, "Số giây cắt tối đa là %d." % TRAD_MAX_S
    return True, (round(h, 2), round(t, 2))


def trad_pair(v):
    """Giá trị lưu trong kế hoạch -> (đầu, đuôi) hoặc None. Nhận số (khóa cũ trad_trim_s: đầu = đuôi) hoặc cặp [đầu, đuôi]; hỏng thì None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        ok, r = check_trad(v, v)
        return r if ok else None
    if isinstance(v, (list, tuple)) and len(v) == 2:
        ok, r = check_trad(v[0], v[1])
        return r if ok else None
    return None


def trad_default(plan):
    """Cắt đầu / đuôi dùng chung cho bin chưa sửa (khóa trad_trim_s: số hoặc cặp; chưa có -> 1,5 / 1,5)."""
    return trad_pair(plan.get("trad_trim_s")) or (TRAD_HEAD_S, TRAD_TAIL_S)


def trad_for(plan, label):
    """Cắt đầu / đuôi RIÊNG của một bin (plan["trad_trim"][tên bin]) hoặc None nếu bin chưa sửa."""
    d = plan.get("trad_trim")
    return trad_pair(d.get(label)) if isinstance(d, dict) and label else None


def suggest_plan(plan, dur, label):
    """Gợi ý mức 1 theo MỌI thông số của kế hoạch (kiểu quay, bảng min/max, cắt đầu/đuôi chung và theo bin)."""
    return suggest_inout(dur, label, plan.get("shoot_style") or "", plan.get("bin_rules") or None, trad_default(plan), trad_for(plan, label))


def suggest_inout(dur, label=None, style="", rules=None, trad_trim=None, trad_bin=None):
    """Gợi ý in/out (giây) theo quy tắc ADR-0004 kết hợp nhãn phân loại bin con:
    - Decor / Chi tiết: cần đoạn 2.5 - 3.5s ổn định, bỏ 1s đầu bấm máy.
    - Cô dâu chú rể / Beauty: cần đoạn 3.5 - 4.5s khoảnh khắc đẹp.
    - Nghi lễ / Gia tiên: giữ đoạn dài 5 - 8s (hoặc gần hết clip nếu ngắn).
    - Phỏng vấn: giữ trọn câu nói.
    - Mặc định (ADR-0004 v4): vào 1.2s, ra = vào + 3.0s, cách cuối >= 1.0s.
    Truyền thống: trad_trim = số (đầu = đuôi, khóa cũ) hoặc cặp (đầu, đuôi) dùng chung; trad_bin = cặp riêng của bin (thắng trad_trim).
    """
    dur = float(dur or 0)
    if dur < 1.0:
        return None
    if style == "traditional":
        # Truyền thống (ADR-0018): giữ source dài nhất có thể, chỉ cắt đầu và đuôi. Cắt đầu / đuôi chỉnh được riêng từng bin (ADR-0025),
        # mặc định 1.5 / 1.5. Clip ngắn thì cắt ít hơn (co đều cả hai đầu) để vẫn còn ít nhất 1 giây. Chỉ là bộ tham số gợi ý (màu xanh).
        h, t = trad_pair(trad_bin) or trad_pair(trad_trim) or (TRAD_HEAD_S, TRAD_TAIL_S)
        room = max(0.0, dur - 1.0)
        if h + t > room and h + t > 0:
            k = room / (h + t)
            h, t = h * k, t * k
        head, tail = h, t
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


def manual_inouts(plan, clip):
    """Danh sách các khúc In/Out đặt tay [(in_s, out_s), ...] của một clip (hỗ trợ cắt nhiều khúc trong 1 source)."""
    arr = (plan.get("inouts") or {}).get(clip.rel)
    if isinstance(arr, list) and arr:
        out = [(float(x[0]), float(x[1])) for x in arr if isinstance(x, (list, tuple)) and len(x) == 2 and float(x[1]) > float(x[0])]
        if out:
            return out
    m = manual_inout(plan, clip)
    return [m] if m else []


def set_manual_inout(plan, clip, in_s, out_s):
    """Lưu In/Out đặt tay (giây). None -> xóa. Trả (in, out) đã kẹp, hoặc None."""
    d = plan.setdefault("inout", {})
    ds = plan.get("inouts")
    if isinstance(ds, dict):
        ds.pop(clip.rel, None)
    if in_s is None or out_s is None:
        d.pop(clip.rel, None)
        return None
    a, b = clamp_inout(in_s, out_s, clip.dur, clip.fps)
    d[clip.rel] = [a, b]
    return a, b


def set_manual_inouts(plan, clip, spans):
    """Lưu danh sách nhiều khúc In/Out [(in_s, out_s), ...]. Rỗng/None -> xóa hết. Trả list [(a, b), ...]."""
    d = plan.setdefault("inout", {})
    ds = plan.setdefault("inouts", {})
    clean = []
    for sp in (spans or []):
        if not isinstance(sp, (list, tuple)) or len(sp) != 2 or sp[0] is None or sp[1] is None:
            continue
        a, b = clamp_inout(float(sp[0]), float(sp[1]), clip.dur, clip.fps)
        if b > a:
            clean.append((a, b))
    if not clean:
        d.pop(clip.rel, None)
        ds.pop(clip.rel, None)
        return []
    d[clip.rel] = [clean[0][0], clean[0][1]]
    if len(clean) > 1:
        ds[clip.rel] = [[a, b] for a, b in clean]
    else:
        ds.pop(clip.rel, None)
    return clean


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
        if data and data.get("project") == project and not data.get("restored"):   # tên 'X' và 'X_B' cùng tiền tố 'X_': xét đúng project trong file
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
    if clip.tl_mode:                                     # nguồn = timeline DaVinci (ADR-0032): vị trí trên timeline, KHÔNG dùng giờ trong file
        if clip.tl_pos is None:
            return None                                  # clip không nằm trên timeline: ngoài mọi giai đoạn
        a = clip.tl_pos / 60.0
        return a, a + (clip.tl_dur if clip.tl_dur is not None else (clip.dur or 0)) / 60.0
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
    "Chỉ tiệc nhà hàng": [
        ("Đón khách", ["Decor", "Cô dâu chú rể", "Khách", "Gia đình"]),
        ("Làm lễ · Vows", ["Sân khấu", "Nghi lễ", "Phát biểu", "Cô dâu chú rể", "Khách"]),
        ("Tiệc", ["Cô dâu chú rể", "Khách", "Gia đình"]),
    ],
    "Lễ mừng thọ (đầy đủ)": [
        ("Chuẩn bị", ["Decor", "Cụ ông", "Cụ bà", "Cụ ông cụ bà", "Gia đình", "Phỏng vấn"]),
        ("Đón khách", ["Decor", "Cụ ông cụ bà", "Khách", "Gia đình", "Chụp hình"]),
        ("Nghi lễ mừng thọ", ["Sân khấu", "Nghi lễ", "Chúc thọ · Phát biểu", "Trao quà · Mừng thọ", "Cụ ông cụ bà", "Gia đình"]),
        ("Văn nghệ · Tiệc", ["Cụ ông cụ bà", "Văn nghệ", "Chào bàn", "Khách", "Gia đình"]),
    ],
    "Lễ mừng thọ (chỉ tiệc)": [
        ("Đón khách", ["Decor", "Cụ ông cụ bà", "Khách", "Gia đình", "Chụp hình"]),
        ("Nghi lễ mừng thọ", ["Sân khấu", "Nghi lễ", "Chúc thọ · Phát biểu", "Trao quà · Mừng thọ", "Cụ ông cụ bà", "Khách"]),
        ("Tiệc · Chào bàn", ["Cụ ông cụ bà", "Văn nghệ", "Khách", "Gia đình"]),
    ],
}
# Bin mẹ (sự kiện) của từng giai đoạn trong mẫu: {mẫu: {tên giai đoạn: tên bin mẹ}}. Mẫu không có ở đây (mẫu người dựng tự lưu) thì mọi giai đoạn
# vào một bin mẹ mặc định. Bin mẹ chỉ là NHÓM trong panel (ADR-0032): bin giai đoạn vẫn tạo trong bin nguồn.
DEFAULT_EVENT = "Sự kiện"
TEMPLATE_EVENTS = {
    "Cưới đầy đủ (sáng lễ, tối tiệc)": {"Chuẩn bị nhà gái": "Lễ gia tiên", "Rước dâu": "Lễ gia tiên", "Gia tiên": "Lễ gia tiên",
                                        "Đón dâu về nhà trai": "Lễ gia tiên", "Đón khách": "Tiệc nhà hàng", "Lễ nhà hàng": "Tiệc nhà hàng",
                                        "Chào bàn": "Tiệc nhà hàng"},
    "Lễ gia tiên (một buổi)": {"Chuẩn bị": "Lễ gia tiên", "Rước dâu": "Lễ gia tiên", "Gia tiên": "Lễ gia tiên", "Kết thúc": "Lễ gia tiên"},
    "Tiệc nhà hàng": {"Đón khách": "Tiệc nhà hàng", "Lễ nhà hàng": "Tiệc nhà hàng", "Chào bàn": "Tiệc nhà hàng"},
    "Chỉ tiệc nhà hàng": {"Đón khách": "Tiệc nhà hàng", "Làm lễ · Vows": "Tiệc nhà hàng", "Tiệc": "Tiệc nhà hàng"},
    "Lễ mừng thọ (đầy đủ)": {"Chuẩn bị": "Lễ mừng thọ", "Đón khách": "Lễ mừng thọ",
                             "Nghi lễ mừng thọ": "Tiệc mừng thọ", "Văn nghệ · Tiệc": "Tiệc mừng thọ"},
    "Lễ mừng thọ (chỉ tiệc)": {"Đón khách": "Tiệc mừng thọ", "Nghi lễ mừng thọ": "Tiệc mừng thọ", "Tiệc · Chào bàn": "Tiệc mừng thọ"},
}


def event_of(template, stage_name):
    """Tên bin mẹ của một giai đoạn theo mẫu."""
    return (TEMPLATE_EVENTS.get(template) or {}).get(stage_name) or DEFAULT_EVENT
DEFAULT_TEMPLATE = "Cưới đầy đủ (sáng lễ, tối tiệc)"


def make_stage(name, start, end, bins, idx, event=None):
    bins = [b for b in bins if b and b != OTHER_BIN] + [OTHER_BIN]
    st = {"name": name, "start": float(start), "end": float(end), "color": PALETTE[idx % len(PALETTE)],
          "bins": bins}
    if event:
        st["event"] = event
    return st


def _tpl_file(data_root, custom_path=None):
    if custom_path:
        cp = str(custom_path).strip()
        if cp.lower().endswith(".json"):
            return cp
        return os.path.join(cp, "templates.json")
    return os.path.join(data_root, "troly", "templates.json") if data_root else None


def templates(data_root, custom_path=None):
    """Mẫu có sẵn + mẫu người dựng đã lưu (data_root/troly/templates.json hoặc custom_path, ghi đè mẫu cùng tên)."""
    out = {k: [(n, list(b)) for n, b in v] for k, v in BUILTIN_TEMPLATES.items()}
    p = _tpl_file(data_root, custom_path)
    if p and os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                for k, v in (json.load(f) or {}).items():
                    out[k] = [(s["name"], list(s.get("bins") or [])) for s in v]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return out


def save_template(data_root, name, stages, custom_path=None):
    p = _tpl_file(data_root, custom_path)
    d = {}
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f) or {}
        except (OSError, ValueError):
            d = {}
    d[name] = [{"name": s["name"], "bins": [b for b in s["bins"] if b != OTHER_BIN]} for s in stages]
    _write_json(p, d)
    return p


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
    """Người dựng CHỌN TAY giai đoạn cho clip (phím F1–F12, kéo thả). stage_name None = bỏ chọn tay (tính lại theo giờ)."""
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


def is_rejected(plan, clip):
    return bool((plan.get("rejected") or {}).get(clip.rel))


def set_rejected(plan, clip, val=None):
    """Đặt hoặc đảo cờ Bỏ (rejected) trong kế hoạch JSON. Không bao giờ đụng file thật hay Media Pool."""
    rej = plan.setdefault("rejected", {})
    cur = bool(rej.get(clip.rel))
    nxt = (not cur) if val is None else bool(val)
    if nxt:
        rej[clip.rel] = True
    else:
        rej.pop(clip.rel, None)
    return nxt


def load_plan(data_root, project):
    """Nạp kế hoạch của project. File chính hỏng thì GIỮ NGUYÊN file hỏng (đổi tên .corrupt-<giờ>) rồi nạp .bak; cả hai hỏng
    mới trả kế hoạch rỗng. Không bao giờ để lần lưu sau ghi đè mất file hỏng. plan['_note'] ghi chú việc đã làm (không lưu)."""
    p = plan_path(data_root, project)
    note = None
    d = _read_json(p) if os.path.isfile(p) else None
    if d is None and os.path.isfile(p):
        keep = "%s.corrupt-%s" % (p, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        n_dup = 1
        while os.path.exists(keep + ("" if n_dup == 1 else "-%d" % n_dup)):       # hai lần hỏng cùng một giây: thêm hậu tố, không ghi đè bản trước
            n_dup += 1
        keep += "" if n_dup == 1 else "-%d" % n_dup
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
NAME_FORBIDDEN = ':/\*?"<>|'           # ký tự Windows cấm trong tên file/thư mục; KHÔNG gồm & (19/11/2026: người dùng có dùng & trong tên bin, ADR-0029)
NAME_MAX = 60
WS_OK = chr(9) + chr(10) + chr(13)       # tab, xuống dòng: gọn thành khoảng trắng thường, không coi là lỗi


def check_new_name(new, siblings, current=None):
    """Kiểm tên mới. Trả (tên đã gọn khoảng trắng, lỗi hoặc None). siblings = tên các bin cùng cấp; current = tên đang đổi
    (không tính là trùng với chính nó). HÀM DUY NHẤT kiểm tên bin/giai đoạn: "+ Bin mới" (add_bin) và Đổi tên (rename_check) cùng gọi.
    Không để trống, không ký tự cấm (: / \ * ? " < > | và ký tự điều khiển; KHÔNG chặn &), không kết thúc bằng dấu chấm (dấu cách cuối đã bị gọn), không trùng tên khác trong cùng cấp (không phân biệt hoa thường)."""
    raw = new or ""
    n = " ".join(raw.split())
    if any((ord(c) < 32 and c not in WS_OK) or ord(c) == 127 for c in raw):      # kiểm trên bản gốc: split() sẽ nuốt 0x1c-0x1f như khoảng trắng
        return n, "Tên không được chứa ký tự điều khiển."
    if not n:
        return n, "Tên không được để trống."
    bad = [c for c in NAME_FORBIDDEN if c in n]
    if bad:
        return n, "Tên không được chứa các ký tự: %s" % " ".join(bad)
    if n.endswith("."):
        return n, "Tên không được kết thúc bằng dấu chấm."
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
        btags = st.get("bin_tags")
        if isinstance(btags, dict) and old in btags:
            if new not in btags:
                btags[new] = btags[old]
            btags.pop(old, None)
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
            for key in ("stage_share", "stage_s"):                # tỉ lệ cũ và số giây anh chốt (Bước 5 làm lại)
                sh = dur.get(key)
                if isinstance(sh, dict) and old in sh:
                    sh[new] = sh.pop(old)
            lk = dur.get("locked")
            if isinstance(lk, list) and old in lk:
                lk[lk.index(old)] = new
            for key in ("bins", "bin_s"):                         # Min-Max nâng cao và số giây bin anh kéo
                bb = dur.get(key)
                if isinstance(bb, dict) and old in bb:
                    bb[new] = bb.pop(old)
            _rename_tl(dur.get("tl"), "stage", old, new, None)
        else:
            for key in ("bins", "bin_s"):
                sub = (dur.get(key) or {}).get(stage_old)
                if isinstance(sub, dict) and old in sub:
                    sub[new] = sub.pop(old)
            _rename_tl(dur.get("tl"), "bin", old, new, stage_old)
    return p_old, p_new


def _rename_tl(tl, kind, old, new, stage):
    """Bước 5 bản 3: đổi tên giai đoạn/bin trong thứ tự cụm, thứ tự khối ("Giai đoạn|Bin"), cấu hình khối (track, tốc độ, tiếng)."""
    if not isinstance(tl, dict):
        return
    def key(st, b):
        return "%s|%s" % (st, b)
    if kind == "stage":
        if isinstance(tl.get("order"), list):
            tl["order"] = [new if x == old else x for x in tl["order"]]
        if isinstance(tl.get("kids"), dict):
            kids = {}
            for cl, lst in tl["kids"].items():
                kids[new if cl == old else cl] = [(new + "|" + x.split("|", 1)[1]) if x.split("|", 1)[0] == old else x for x in lst]
            tl["kids"] = kids
        for k in ("blk", "stg"):
            if isinstance(tl.get(k), dict) and old in tl[k]:
                tl[k][new] = tl[k].pop(old)
    else:
        if isinstance(tl.get("kids"), dict):
            for cl, lst in tl["kids"].items():
                tl["kids"][cl] = [key(stage, new) if x == key(stage, old) else x for x in lst]
        sub = (tl.get("blk") or {}).get(stage)
        if isinstance(sub, dict) and old in sub:
            sub[new] = sub.pop(old)


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


# --- Gợi ý In/Out cho clip sao: mức 1 theo quy tắc bin, mức 2 theo lời nói (Bước 3 làm lại, ADR-0024) ---------------------
SUG_PAD_DEFAULT = 0.3                 # đệm hai đầu khi gợi ý theo lời nói (giây), ô chỉnh trong panel
SUG_PAD_MAX = 3.0
SUG_MIN_SPAN = 0.5                    # đoạn theo lời nói ngắn hơn ngần này thì coi như không có (rơi về mức 1)


def sug_pad(plan):
    v = (plan.get("inout_sug_cfg") or {}).get("pad")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return SUG_PAD_DEFAULT
    return v if 0.0 <= v <= SUG_PAD_MAX else SUG_PAD_DEFAULT


def speech_span(lines, dur, pad=SUG_PAD_DEFAULT):
    """Mức 2: In = đầu câu có tiếng nói đầu tiên, Out = cuối câu cuối cùng, cộng đệm pad hai đầu, kẹp trong [0, dur].
    lines = [{'t0','t1'}] từ kho lời nói. Không có câu hợp lệ / đoạn ngắn hơn SUG_MIN_SPAN -> None."""
    ls = []
    for l in lines or []:
        try:
            a, b = float(l["t0"]), float(l["t1"])
        except (KeyError, TypeError, ValueError):
            continue
        if b > a:
            ls.append((a, b))
    if not ls:
        return None
    a = max(0.0, min(x for x, _ in ls) - pad)
    b = max(y for _, y in ls) + pad
    if dur:
        b = min(b, float(dur))
        a = min(a, b)
    if b - a < SUG_MIN_SPAN:
        return None
    return round(a, 2), round(b, 2)


def sug_signature(plan, label):
    """Chữ ký các thông số làm nên gợi ý (kiểu quay, quy tắc của bin, số giây Truyền thống, đệm) để biết gợi ý đã lưu có cũ không."""
    t = rule_for(label, plan.get("bin_rules") or None)
    return "|".join(str(x) for x in (plan.get("shoot_style") or "", t[1], t[2], t[3], trad_default(plan), trad_for(plan, label), sug_pad(plan)))


def compute_sug(plan, clip, label, lines, vision=None):
    """Gợi ý cho một clip: ưu tiên chữ Whisper / VAD (nếu có), rồi đến phân tích Hình ảnh (nét + êm), cuối cùng là quy tắc bin.
    Trả dict {in, out, src: 'speech'|'vision'|'rule', rule, sig, pad} hoặc None."""
    dur = float(clip.dur or 0)
    pad = sug_pad(plan)
    sp = speech_span(lines, dur, pad) if lines else None
    if sp:
        return {"in": sp[0], "out": sp[1], "src": "speech", "rule": "Theo lời nói (đệm %g s)" % pad, "sig": sug_signature(plan, label), "pad": pad}
    if vision and vision.get("in") is not None and vision.get("out") is not None:
        return {"in": vision["in"], "out": vision["out"], "src": "vision", "rule": vision.get("rule") or "Hình ảnh (Nét + Êm)", "sig": sug_signature(plan, label), "pad": pad}
    r = suggest_plan(plan, dur, label)
    if r is None:
        return None
    return {"in": r["in_s"], "out": r["out_s"], "src": "rule", "rule": r["rule"], "sig": sug_signature(plan, label), "pad": pad}


def sug_note(plan, clip, label, sug, new_in, new_out, via):
    """Ghi lại để có số đo thật: anh NHẬN NGUYÊN gợi ý (via='accept') hay CHỈNH (via='edit' mà khác gợi ý). sug = (vào, ra, nguồn)."""
    if not sug:
        return
    a, b, src = sug
    same = abs(new_in - a) <= 0.02 and abs(new_out - b) <= 0.02
    if via == "edit" and same:
        state = "accepted"
    else:
        state = "accepted" if via == "accept" else "adjusted"
    plan.setdefault("inout_stats", {}).setdefault("clips", {})[clip.rel] = {
        "src": src, "state": state, "bin": label or "", "sug": [round(a, 2), round(b, 2)], "final": [round(new_in, 2), round(new_out, 2)]}


def sug_forget(plan, clip):
    """Anh xóa In/Out đặt tay: bỏ ghi nhận của clip đó."""
    ((plan.get("inout_stats") or {}).get("clips") or {}).pop(clip.rel, None)


def sug_counts(plan):
    c = (plan.get("inout_stats") or {}).get("clips") or {}
    out = {"accepted": 0, "adjusted": 0, "by_src": {}}
    for v in c.values():
        out[v["state"]] = out.get(v["state"], 0) + 1
        d = out["by_src"].setdefault(v["src"], {"accepted": 0, "adjusted": 0})
        d[v["state"]] += 1
    return out
