"""Nhiều camera, trang 1 (ADR-0031): nhận máy từ metadata và tên file, tên máy A-D, máy chuẩn, độ lệch đồng hồ.

Logic thuần, không gọi DaVinci, không đụng file gốc. Mọi thứ lưu trong kế hoạch project (plan["cams"]):
  map    {khóa nhóm máy (Clip.camera): chữ cái A-D}   nhóm chưa có chữ thì ""
  names  {chữ cái: tên người dựng đặt}
  ref    chữ cái máy chuẩn giờ (mặc định A)
  shift  {chữ cái: giây CỘNG vào giờ máy đó để ra giờ chung}; máy chuẩn không có mục. Máy chưa chỉnh: không có mục.
  moment {chữ cái: {"ref": [khóa clip, giây], "cam": [khóa clip, giây]}} khoảnh khắc đã dùng để tính (ghi lại cho dễ kiểm).
Giờ chung = giờ của máy chuẩn. Tối đa 4 máy. Độ lệch: cảnh báo trên 3 giờ, chặn trên 12 giờ.
"""
import re

LETTERS = "ABCD"
MAX_CAMS = 4
WARN_S = 3 * 3600
BLOCK_S = 12 * 3600
NAME_MAX = 20
OVERLAP_TOL_S = 2.0

_MODEL_KEYS = ("Camera Type", "Camera Model", "Camera Model Name", "Model", "Camera Manufacturer Model")
_SERIAL_KEYS = ("Camera Serial #", "Camera Serial Number", "Camera ID", "Camera #")
_MAKER_KEYS = ("Camera Manufacturer", "Camera Make", "Make")


def _first(props, keys):
    for k in keys:
        v = (props.get(k) or "")
        v = str(v).strip()
        if v:
            return v
    return ""


def meta(props):
    """(hãng, model, serial) đọc từ thuộc tính clip của DaVinci; thiếu thì chuỗi rỗng."""
    return _first(props, _MAKER_KEYS), _first(props, _MODEL_KEYS), _first(props, _SERIAL_KEYS)


def default_names():
    return {L: "Máy " + L for L in LETTERS}


def new_cfg():
    return {"map": {}, "names": default_names(), "ref": "A", "shift": {}, "moment": {}}


def clean_cfg(cfg):
    """Kế hoạch cũ/hỏng -> cấu hình hợp lệ (không bao giờ ném lỗi)."""
    out = new_cfg()
    if not isinstance(cfg, dict):
        return out
    m = cfg.get("map")
    if isinstance(m, dict):
        out["map"] = {str(k): v for k, v in m.items() if v in LETTERS or v == ""}
    n = cfg.get("names")
    if isinstance(n, dict):
        for L in LETTERS:
            v = n.get(L)
            if isinstance(v, str) and v.strip():
                out["names"][L] = v.strip()[:NAME_MAX]
    if cfg.get("ref") in tuple(LETTERS):
        out["ref"] = cfg["ref"]
    s = cfg.get("shift")
    if isinstance(s, dict):
        for L, v in s.items():
            if L in LETTERS and isinstance(v, (int, float)) and abs(v) <= BLOCK_S:
                out["shift"][L] = float(v)
    if cfg.get("managed"):
        out["managed"] = True
    mo = cfg.get("moment")
    if isinstance(mo, dict):
        out["moment"] = {L: v for L, v in mo.items() if L in LETTERS and isinstance(v, dict)}
    return out


def ensure_groups(cfg, groups):
    """Gán chữ cái cho nhóm máy mới: nhóm nhiều file nhất lấy chữ trống đầu tiên (A, B, C, D). Nhóm thứ 5 trở đi để "" (người dựng gán tay
    hoặc gộp). Trả True nếu cfg có đổi. groups = [{"key","n"}...]."""
    changed = False
    m = cfg["map"]
    used = {v for v in m.values() if v}
    for g in sorted(groups, key=lambda g: (-g["n"], g["key"])):
        if g["key"] in m:
            continue
        free = [L for L in LETTERS if L not in used]
        m[g["key"]] = free[0] if free else ""
        if free:
            used.add(free[0])
        changed = True
    return changed


def letters_in_use(cfg, groups):
    s = {cfg["map"].get(g["key"], "") for g in groups}
    s.discard("")
    return sorted(s)


def check_name(cfg, letter, name):
    """(ok, tên đã làm sạch | lời báo lỗi). Không trống, không trùng (không phân biệt hoa thường) với máy khác, tối đa 20 ký tự."""
    if letter not in LETTERS:
        return False, "Không có máy %s." % letter
    v = re.sub(r"\s+", " ", str(name or "")).strip()
    if not v:
        return False, "Tên máy không được để trống."
    if len(v) > NAME_MAX:
        return False, "Tên máy tối đa %d ký tự." % NAME_MAX
    for L, other in cfg["names"].items():
        if L != letter and other.lower() == v.lower():
            return False, "Trùng tên với %s. Mỗi máy một tên." % other
    return True, v


def parse_offset(text):
    """'+01:12:14' / '-00:02:14' / '1:12:14' -> (ok, giây | lời lỗi, cảnh báo hoặc ""). Chặn trên 12 giờ, cảnh báo trên 3 giờ."""
    t = str(text or "").strip()
    if not t:
        return False, "Chưa nhập độ lệch. Gõ dạng +01:12:14.", ""
    m = re.match(r"^([+-]?)(\d{1,3}):(\d{1,2}):(\d{1,2})$", t)
    if not m:
        return False, "Gõ độ lệch dạng ±giờ:phút:giây, ví dụ +01:12:14.", ""
    if int(m.group(3)) > 59 or int(m.group(4)) > 59:
        return False, "Phút và giây phải nhỏ hơn 60.", ""
    v = (int(m.group(2)) * 3600 + int(m.group(3)) * 60 + int(m.group(4))) * (-1 if m.group(1) == "-" else 1)
    if abs(v) > BLOCK_S:
        return False, "Độ lệch tối đa ±12 giờ. Lệch hơn thế thường là nhầm ngày, hãy kiểm tra lại khoảnh khắc đã chọn.", ""
    warn = "Lệch trên 3 giờ, thường do đặt nhầm múi giờ hoặc ngày. Kiểm tra lại cho chắc." if abs(v) > WARN_S else ""
    return True, float(v), warn


def fmt_offset(sec):
    s = int(round(abs(sec)))
    return "%s%02d:%02d:%02d" % ("-" if sec < 0 else "+", s // 3600, s % 3600 // 60, s % 60)


def set_ref(cfg, new_ref):
    """Đổi máy chuẩn: các máy ĐÃ chỉnh được tính lại theo máy mới (giờ chung đổi sang giờ máy mới); máy chưa chỉnh vẫn chưa chỉnh.
    Với máy x đã chỉnh: off'(x) = off(x) - off(máy mới). Máy chuẩn cũ coi như off = 0 nên thành -off(máy mới) nếu máy mới đã chỉnh."""
    if new_ref not in LETTERS:
        return False
    old = cfg["ref"]
    if new_ref == old:
        return True
    sh = cfg["shift"]
    k = sh.get(new_ref)
    new = {}
    if k is not None:
        for L, v in sh.items():
            if L != new_ref:
                new[L] = v - k
        new[old] = -k                    # máy chuẩn cũ: trước đó off = 0, nay là -off(máy mới)
    else:
        new = dict(sh)                   # máy mới chưa chỉnh: giờ của nó coi như đã là giờ chung, các máy khác giữ nguyên
    new = {L: v for L, v in new.items() if L != new_ref}
    cfg["shift"] = new
    cfg["moment"] = {}                   # khoảnh khắc cũ tính theo máy chuẩn cũ: bỏ để khỏi hiểu nhầm
    cfg["ref"] = new_ref
    return True


def offset_from_moment(t_ref_start, pos_ref, t_cam_start, pos_cam):
    """Độ lệch (giây) để cộng vào giờ máy cần chỉnh. t_*_start: giờ GỐC (giây) lúc clip bắt đầu theo đồng hồ của máy đó;
    pos_*: giây trong clip tại khoảnh khắc chung. Giờ của khoảnh khắc ở máy chuẩn trừ giờ ở máy cần chỉnh."""
    return (t_ref_start + pos_ref) - (t_cam_start + pos_cam)


def overlap_after(ref_start, ref_dur, cam_start, cam_dur, off):
    """Số giây hai clip chồng nhau trên giờ chung sau khi áp độ lệch off (<= 0 là không chồng)."""
    a0, a1 = ref_start, ref_start + ref_dur
    b0, b1 = cam_start + off, cam_start + off + cam_dur
    return min(a1, b1) - max(a0, b0)


def has_overlap(intervals, tol=OVERLAP_TOL_S):
    """intervals = [(bắt đầu, kết thúc)] giây. True nếu có hai khoảng chồng nhau hơn tol giây: một máy không quay hai clip cùng lúc,
    nên nhóm chồng giờ có thể là nhiều máy cùng đời bị gộp một nhóm."""
    end = None
    for a, b in sorted(intervals):
        if end is not None and a < end - tol:
            return True
        end = b if end is None else max(end, b)
    return False


def describe_groups(clips, day_secs):
    """Nhóm máy từ danh sách clip. Mỗi clip cần: camera (khóa), cam_model, cam_serial, cam_maker, t_start (datetime|None), dur.
    day_secs(clip) -> giây gốc (giờ đồng hồ máy) hoặc None. Trả danh sách nhóm theo số file giảm dần:
    {key, n, model, serial, maker, source ('metadata'|'name'), ambiguous (lời giải thích hoặc ""), first, last (giây gốc)}."""
    by = {}
    for c in clips:
        by.setdefault(c.camera, []).append(c)
    out = []
    for key, cs in by.items():
        model = next((c.cam_model for c in cs if c.cam_model), "")
        serial = next((c.cam_serial for c in cs if c.cam_serial), "")
        maker = next((c.cam_maker for c in cs if c.cam_maker), "")
        iv, firsts, lasts = [], [], []
        for c in cs:
            s = day_secs(c)
            if s is None:
                continue
            e = s + (c.dur or 0)
            iv.append((s, e))
            firsts.append(s)
            lasts.append(e)
        source = "metadata" if (model or serial) else "name"
        why = ""
        if source == "name":
            why = "Không đọc được model hay số seri trong metadata, nhận theo tên file. Kiểm tra lại cho chắc."
        elif not serial and has_overlap(iv):
            why = "Có clip chồng giờ nhau trong nhóm này và không có số seri: có thể là hai máy cùng đời bị gộp một. Gán tay nếu cần."
        elif has_overlap(iv):
            why = "Có clip chồng giờ nhau trong nhóm này: kiểm tra lại đồng hồ máy hoặc số seri."
        out.append({"key": key, "n": len(cs), "model": model, "serial": serial, "maker": maker, "source": source,
                    "ambiguous": why, "first": min(firsts) if firsts else None, "last": max(lasts) if lasts else None})
    out.sort(key=lambda g: (-g["n"], g["key"]))
    return out


def effective_offsets(cfg, keys):
    """{khóa nhóm: giây} để đưa vào plan['offsets'] (clip_minutes dùng). Máy chuẩn, máy chưa chỉnh, nhóm chưa gán chữ: không có mục."""
    out = {}
    for k in keys:
        L = cfg["map"].get(k, "")
        v = cfg["shift"].get(L) if L and L != cfg["ref"] else None
        if v:
            out[k] = v
    return out
