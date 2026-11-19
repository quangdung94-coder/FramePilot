"""Nguồn thời gian của trang 1 (ADR-0032): đọc timeline đã sync trong DaVinci, gộp máy theo track, nhận máy theo tiền tố tên file.

Logic thuần, không gọi DaVinci (việc đọc nằm ở troly_resolve.do_tl_read). Trục thời gian = giây kể từ ĐẦU TIMELINE (như DaVinci),
không dùng ngày giờ ghi trong file. KHÔNG xoay hay sửa file, bỏ qua cờ xoay khi nhóm máy (chỉ dùng kích thước mã hoá gốc + tiền tố);
công tắt "Có máy quay dọc" (mặc định TẮT) mới tách nhóm theo hướng SAU xoay.

Dữ liệu thô từ worker (raw): {"name", "fps", "start": frame đầu timeline,
  "tracks": [{"kind": "video"|"audio", "idx": 1.., "name", "items": [{"uid", "name", "start", "dur", "w", "h", "rot", "audio_only"}]}]}
start / dur tính bằng frame của timeline. Clip chuyển cảnh, tiêu đề (không có media pool item) đã bị bỏ ở worker.
"""
import re

COLORS = ["#4FC1A6", "#C98BE0", "#E88AB0", "#E5D06A", "#7FB7E8", "#EF7D65", "#A9CF62", "#B89A7A"]
AUDIO_COLOR = "#6E6E78"
SYNC_MIN_OVERLAP = 0.5


def prefix_of(name):
    """Tiền tố máy của tên file: bỏ phần NGÀY ở đầu (20261114_HM2129.MP4 -> HM), lấy phần chữ trước dãy số (DG4939 -> DG, B_A5395 -> B_A).
    Không có chữ thì trả chuỗi rỗng (giao diện dùng tên 'Máy N', KHÔNG hiện '?')."""
    base = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", str(name or ""))
    base = re.sub(r"^\d{6,8}[_\-\s]?", "", base)
    m = re.match(r"^([A-Za-z_\-]*[A-Za-z])", base)
    return m.group(1).upper().strip("_-") if m else ""


def portrait(w, h, rot=0, after_rotation=False):
    """Clip dọc? Mặc định chỉ nhìn kích thước mã hoá gốc (bỏ qua cờ xoay). after_rotation=True: tính cả cờ xoay 90/270."""
    try:
        w, h = int(w), int(h)
    except (TypeError, ValueError):
        return False
    if after_rotation and int(rot or 0) % 180 == 90:
        w, h = h, w
    return h > w


def parse_size(res):
    m = re.match(r"^\s*(\d+)\s*[xX]\s*(\d+)\s*$", str(res or ""))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def video_tracks(raw):
    return [t for t in (raw.get("tracks") or []) if t.get("kind") == "video" and t.get("items")]


def audio_rows(raw):
    """Hàng âm thanh: chỉ lấy clip CHỈ có âm thanh (Tascam/Zoom, nhạc), bỏ âm thanh đi kèm clip video."""
    rows = []
    for t in raw.get("tracks") or []:
        if t.get("kind") != "audio":
            continue
        its = [it for it in t.get("items") or [] if it.get("audio_only")]
        if its:
            rows.append({"track": t["idx"], "name": (t.get("name") or "Âm thanh").strip() or "Âm thanh", "items": its})
    return rows


def is_synced(raw):
    """(đã sync?, lý do). Rỗng: chưa. Một track: coi là đã có trục. Nhiều track: hai track nhiều clip nhất phải chồng nhau về thời gian
    (khoảng chồng >= 50% khoảng ngắn hơn); không thì các máy đang xếp nối nhau, chưa sync."""
    vt = video_tracks(raw)
    if not vt:
        return False, "Timeline chưa có clip video."
    if len(vt) == 1:
        return True, ""
    spans = []
    for t in sorted(vt, key=lambda t: -len(t["items"]))[:2]:
        a = min(it["start"] for it in t["items"])
        b = max(it["start"] + it["dur"] for it in t["items"])
        spans.append((a, b))
    (a0, b0), (a1, b1) = spans
    ov = min(b0, b1) - max(a0, a1)
    short = max(1, min(b0 - a0, b1 - a1))
    if ov / float(short) >= SYNC_MIN_OVERLAP:
        return True, ""
    return False, "Các track không chồng nhau về thời gian."


def machines(raw, vertical=False):
    """Danh sách máy = mỗi track video có clip (vertical=True thì tách thêm theo hướng sau xoay).
    [{key, track, letter, name, prefix, n, color, orient}] theo thứ tự track. Tên máy: 'Máy A · DG'."""
    out = []
    for t in sorted(video_tracks(raw), key=lambda t: t["idx"]):
        groups = {"": t["items"]}
        if vertical:
            groups = {}
            for it in t["items"]:
                groups.setdefault("d" if portrait(it.get("w"), it.get("h"), it.get("rot"), True) else "n", []).append(it)
        for sub in sorted(groups):
            its = groups[sub]
            pref = {}
            for it in its:
                p = prefix_of(it.get("name"))
                pref[p] = pref.get(p, 0) + 1
            p = max(pref.items(), key=lambda kv: (kv[1], kv[0]))[0] if pref else ""
            out.append({"key": "t%d%s" % (t["idx"], sub), "track": t["idx"], "prefix": p, "n": len(its), "orient": sub})
    for i, m in enumerate(out):
        m["letter"] = chr(ord("A") + i) if i < 26 else "?"
        m["color"] = COLORS[i % len(COLORS)]
        base = "Máy %s" % m["letter"]
        tag = (m["prefix"] or "").strip()
        if m["orient"]:
            tag = (tag + " " if tag else "") + ("dọc" if m["orient"] == "d" else "ngang")
        m["name"] = "%s · %s" % (base, tag) if tag else base
    return out


def machine_key_of(item, track_idx, vertical):
    return "t%d%s" % (track_idx, ("d" if portrait(item.get("w"), item.get("h"), item.get("rot"), True) else "n") if vertical else "")


def placements(raw, fps=None, vertical=False):
    """{uid: {"pos", "dur", "track", "mk", "n"}} cho clip video: vị trí ĐẦU TIÊN trên timeline (giây kể từ đầu timeline), độ dài đoạn đó,
    số lần clip nằm trên timeline."""
    fps = float(fps or raw.get("fps") or 25.0)
    t0 = raw.get("start") or 0
    out = {}
    for t in video_tracks(raw):
        for it in t["items"]:
            uid = it.get("uid")
            if not uid:
                continue
            p = {"pos": (it["start"] - t0) / fps, "dur": it["dur"] / fps, "track": t["idx"], "mk": machine_key_of(it, t["idx"], vertical), "n": 1}
            old = out.get(uid)
            if old is None:
                out[uid] = p
            else:
                old["n"] += 1
                if p["pos"] < old["pos"]:
                    p["n"] = old["n"]
                    out[uid] = p
    return out


def fmt_hms(minutes, pad_hour=False):
    """Phút (số thực) -> 'H:MM:SS' (trục từ đầu timeline: 0:30:00, 1:15:00)."""
    s = int(round(float(minutes) * 60))
    sign = "-" if s < 0 else ""
    s = abs(s)
    return "%s%s:%02d:%02d" % (sign, ("%02d" if pad_hour else "%d") % (s // 3600), s % 3600 // 60, s % 60)


def parse_hms(text):
    """'1:30:00' / '01:30:00' / '1:30' (giờ:phút) / '90' (phút) -> phút. Hỏng thì ValueError."""
    t = str(text or "").strip()
    m = re.match(r"^(\d{1,3}):(\d{1,2}):(\d{1,2})$", t)
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if mi > 59 or s > 59:
            raise ValueError("Phút và giây phải nhỏ hơn 60: %r" % text)
        return h * 60 + mi + s / 60.0
    m = re.match(r"^(\d{1,3}):(\d{1,2})$", t)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if mi > 59:
            raise ValueError("Phút phải nhỏ hơn 60: %r" % text)
        return h * 60.0 + mi
    raise ValueError("Mốc giờ không hợp lệ: %r (viết kiểu 1:30:00)" % text)
