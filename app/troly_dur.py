"""
troly_dur.py - Bước 5 Thời lượng (ADR-0013): chia thời lượng video mục tiêu cho giai đoạn và bin con, cắt gọt các clip có sao cho vừa.
LOGIC THUẦN: không gọi DaVinci, không ghi file. Chỉ cho ra KẾ HOẠCH (danh sách clip + In/Out + tổng) để hiển thị; tạo timeline do
TrolyWorker.do_create_cut_timeline làm sau khi người dựng bấm xác nhận.

CÁC SỐ MẶC ĐỊNH LÀ ĐỀ XUẤT, CHƯA ĐƯỢC NGƯỜI DỰNG XÁC NHẬN (giao diện ghi rõ "đề xuất, anh sửa được"):
  - Mục tiêu 12 phút (khoảng gợi ý 10-15).
  - Tổng bin: Decor 10-20 giây, Beauty cô dâu 20-30 giây.
  - Bin khác, tự suy ra: tự nhiên = tổng độ dài gợi ý (bảng quy tắc Bước 3) của các clip có sao trong bin;
    Max = min(90, tự nhiên), Min = min(Max, 0,6 × tự nhiên). Bin không có clip sao: 0-0.
Min-Max là TỔNG của cả bin (khác độ dài từng clip ở Bước 3, vẫn lấy từ bin_rules / In/Out đặt tay / kiểu quay).
BẢN THANH KÉO (18/11/2026): mỗi giai đoạn/bin có "Có" = tổng clip sao (thanh đầy), "Lấy" = số giây lấy (kéo chấm hoặc gõ), không vượt Có.
Mặc định KHÔNG giới hạn Max/Min cho bin (chỉ có tác dụng khi anh tự đặt trong "Giới hạn nâng cao"). Thêm plan["durations"]["bin_s"] = {giai đoạn: {bin: giây}}.
Người dựng sửa thì lưu trong kế hoạch: plan["durations"] = {"target_min", "stage_s": {tên giai đoạn: giây anh chốt}, "locked": [tên giai đoạn khóa],
"bins": {tên giai đoạn: {tên bin: [min, max]}}}; khóa chỉ xuất hiện khi anh sửa.
Làm lại 18/11/2026 (đề bài Bước 5 làm lại): mỗi giai đoạn MỘT số giây. Giai đoạn anh gõ số hoặc khóa là "chốt"; các giai đoạn còn lại co giãn
theo tỉ lệ clip sao có, không vượt quá số clip sao có (thiếu thì báo thiếu, không bịa clip). Mọi thứ tính lại ngay, không còn nút cắt gọt.
(Khóa cũ "stage_share" của bản trước không còn dùng; còn trong file cũng vô hại.)
"""
import copy
import math

import troly_core as tc

TARGET_DEFAULT_MIN = 12.0
TARGET_LIMITS_MIN = (1.0, 120.0)          # giới hạn nhập (phút)
SUGGEST_RANGE_MIN = (10.0, 15.0)          # khoảng gợi ý (chỉ để nhắc)
BIN_SCALE_S = 90.0                        # thang của thanh trong demo, cũng là Max tối đa của bin tự suy ra
DERIVE_MIN_RATIO = 0.6
UNSORTED = "(chưa xếp bin)"
MIN_STAGE_SHARE = 0.02
STAGE_MAX_S = 7200.0                      # giai đoạn anh chốt tối đa 2 giờ
TOL_S = 10.0                              # chênh <= 10 giây so với mục tiêu vẫn coi là "đạt" (Truyền thống chỉ bỏ nguyên clip nên lệch vài giây)


def _floor1(x):
    return math.floor(x * 10 + 1e-9) / 10.0


def star_level(plan, clip):
    """Mức sao của clip: 0 = không sao. Hiện chỉ có sao/không sao (True = 1); khi có mức 1/2/3 thì giá trị số được dùng làm độ ưu tiên."""
    v = (plan.get("stars") or {}).get(clip.rel)
    if not v:
        return 0
    return 1 if v is True else (int(v) if isinstance(v, (int, float)) and v > 0 else 1)


def check_target(minutes):
    try:
        v = float(minutes)
    except (TypeError, ValueError):
        return False, "Thời lượng phải là số phút."
    if v != v or v in (float("inf"), float("-inf")):
        return False, "Thời lượng phải là số phút."
    lo, hi = TARGET_LIMITS_MIN
    if v < lo or v > hi:
        return False, "Thời lượng mục tiêu từ %g đến %g phút." % (lo, hi)
    return True, round(v, 4)


def check_bin_minmax(mn, mx):
    try:
        mn, mx = float(mn), float(mx)
    except (TypeError, ValueError):
        return False, "Số giây phải là số."
    for v in (mn, mx):
        if v != v or v in (float("inf"), float("-inf")):
            return False, "Số giây phải là số."
        if v < 0:
            return False, "Số giây không được âm."
        if v > 3600:
            return False, "Số giây tối đa là 3600."
    if mn > mx:
        return False, "Min không được lớn hơn Max."
    return True, (round(mn, 1), round(mx, 1))


def clip_cut(plan, clip, label, span=None):
    """Cách cắt một clip có sao: dict(in_s, out_s, len, lmin, fixed). In/Out anh đặt tay THẮNG (cố định, không rút thêm);
    không thì gợi ý theo bảng quy tắc Bước 3 (rules, kiểu quay, số giây Truyền thống). lmin = độ dài tối thiểu được rút tới:
    min của quy tắc bin; Truyền thống thì không rút (chỉ bỏ clip)."""
    dur = float(clip.dur or 0)
    m = span if span is not None else tc.manual_inout(plan, clip)
    if m:
        a = max(0.0, min(float(m[0]), dur)) if dur else float(m[0])
        b = max(a, min(float(m[1]), dur)) if dur else float(m[1])
        return {"in_s": a, "out_s": b, "len": b - a, "lmin": b - a, "fixed": True}
    style = plan.get("shoot_style") or ""
    rules = plan.get("bin_rules") or None
    s = tc.suggest_plan(plan, dur, label)
    if s is None:                                           # clip < 1 giây: lấy nguyên clip
        return {"in_s": 0.0, "out_s": dur, "len": dur, "lmin": dur, "fixed": True}
    ln = s["out_s"] - s["in_s"]
    if style == "traditional":
        lmin = ln
    else:
        _t, mn, _mx, _whole, _ed = tc.rule_for(label, rules)
        lmin = min(ln, mn)
    return {"in_s": s["in_s"], "out_s": s["out_s"], "len": ln, "lmin": lmin, "fixed": False}


def default_bin_minmax(name, natural):
    """Mặc định KHÔNG giới hạn: (0, tự nhiên, 'khong_gioi_han'). Min-Max chỉ có tác dụng khi anh tự đặt trong "Giới hạn nâng cao"
    (bản đầu chặn Decor 10-20 s... làm tụt tổng video xuống còn 10 phút dù clip sao dư; bỏ ngày 18/11/2026)."""
    return 0.0, round(natural, 1), "khong_gioi_han"


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float("inf"), float("-inf"))


# ---- Bản 3 (timeline kéo thả): khối = bin con trong cụm mẹ (giai đoạn); mỗi khối có track V1/V2, tốc độ, tiếng. Lưu ở plan["durations"]["tl"].
def block_key(stage, bin_name):
    return "%s|%s" % (stage, bin_name)


def tl_cfg(plan):
    d = (plan.get("durations") or {}) if isinstance(plan, dict) else {}
    t = d.get("tl")
    return t if isinstance(t, dict) else {}


def _blk(tl, stage, bin_name):
    b = (tl.get("blk") or {}).get(stage)
    b = b.get(bin_name) if isinstance(b, dict) else None
    return b if isinstance(b, dict) else {}


def block_track(tl, stage, bin_name):
    return "V2" if _blk(tl, stage, bin_name).get("track") == "V2" else "V1"


def speed_spec(tl, stage, bin_name):
    """Tốc độ của khối: khối con đặt riêng THẮNG khối mẹ. Trả None (100%), 'auto' (Slow mượt tự tính) hoặc số phần trăm."""
    for src in (_blk(tl, stage, bin_name), (tl.get("stg") or {}).get(stage) or {}):
        if isinstance(src, dict) and src.get("speed") is not None:
            v = src["speed"]
            if v == "auto":
                return "auto"
            if _num(v) and 5 <= v <= 400:
                return None if abs(v - 100) < 1e-9 else float(v)
            return None
    return None


def mute_of(tl, stage, bin_name):
    """Tiếng của khối: True = TẮT. Khối con đặt riêng thắng khối mẹ; mặc định bật."""
    for src in (_blk(tl, stage, bin_name), (tl.get("stg") or {}).get(stage) or {}):
        if isinstance(src, dict) and isinstance(src.get("mute"), bool):
            return src["mute"]
    return False


def speed_p(spec, clip, tl_fps):
    """Hệ số tốc độ (1.0 = giữ nguyên, 0.5 = Slow 50%) của MỘT clip. 'auto' = fps timeline / fps source (50p->25p = 0.5; 60p->25p = 0.4167;
    50p->30p = 0.6), không bao giờ nhanh hơn 100%. Độ dài trên timeline (RA) = độ dài In/Out gốc / hệ số."""
    if spec == "auto":
        f = getattr(clip, "fps", None)
        return max(0.05, min(1.0, float(tl_fps) / float(f))) if f and tl_fps else 1.0
    if _num(spec) and spec > 0:
        return float(spec) / 100.0
    return 1.0


def fit_bin(entries, budget):
    """Cắt gọt một bin cho tổng <= budget. entries = [{'level','pos','cut'}]. Trả (giữ lại với 'use' = độ dài, danh sách bị bỏ).
    Trước hết bỏ clip ít ưu tiên nhất (mức sao thấp nhất; bằng nhau thì clip quay muộn hơn) cho tới khi tổng độ dài TỐI THIỂU vừa;
    rồi rút dần độ dài các clip (không bao giờ dưới lmin, In/Out đặt tay không rút) cho tổng đúng bằng budget."""
    kept = list(entries)
    dropped = []
    while kept and sum(e["cut"]["lmin"] for e in kept) > budget + 1e-9:
        victim = min(kept, key=lambda e: (e["level"], -e["pos"]))
        kept.remove(victim)
        dropped.append(victim)
    tot_full = sum(e["cut"]["len"] for e in kept)
    tot_min = sum(e["cut"]["lmin"] for e in kept)
    r = 1.0 if tot_full <= budget + 1e-9 or tot_full <= tot_min else max(0.0, (budget - tot_min) / (tot_full - tot_min))
    carry = 0.0                                              # phần lẻ 0,1 giây dồn sang clip sau: tổng đúng budget, không hụt vài giây khi có hàng trăm clip
    for e in kept:
        c = e["cut"]
        ln = c["len"] if r >= 1.0 else c["lmin"] + (c["len"] - c["lmin"]) * r
        if not c["fixed"] and ln < c["len"]:
            want = ln + carry
            ln = max(c["lmin"], _floor1(want))
            carry = max(-1.0, min(1.0, want - ln))
        e["use"] = min(ln, c["len"])
    return kept, dropped


def build(plan, clips, assign, stages, tl_fps=None):
    """Kế hoạch cắt gọt toàn project (xem docstring đầu file). MỌI số giây ở đây là RA TIMELINE (= In/Out gốc / tốc độ); khối ở V2 không cộng vào
    tổng/Hiện Tại. tl_fps = fps timeline của project (cho Slow mượt tự tính). Trả dict:
      target_s, total_s, delta_s, state (ok | short | over | no_star), stages[{name, share, budget_s, total_s, natural_s (CÓ = thanh đầy), avail_s, maxed,
      pinned, locked, n_starred, n_bins, n_used, dropped_n, dropped_s, dropped_clips, bins[{name, min, max, edited, natural_s, avail_s, pin,
      total_s, shots, dropped}]}], items[{uid, stage, bin, in_s, out_s, dur}] theo thứ tự giai đoạn rồi giờ quay, warnings[], n_starred, n_used."""
    d = plan.get("durations") or {}
    ok, tmin = check_target(d.get("target_min", TARGET_DEFAULT_MIN))
    tmin = tmin if ok else TARGET_DEFAULT_MIN
    target = tmin * 60.0
    warnings = []
    groups = {}                                            # (si, bin) -> [entry]
    excluded = 0
    starred = [c for c in clips if tc.is_starred(plan, c)]
    for c in starred:
        si = assign.get(c.uid)
        man = tc.manual_of(plan, c)
        if man:
            si = next((i for i, s in enumerate(stages) if s["name"] == man.get("stage")), si)
        if si is None or si < 0 or si >= len(stages):
            excluded += 1
            continue
        s = stages[si]
        lab = tc.label_of(plan, c)
        b = lab["bin"] if lab and lab.get("stage") == s["name"] and lab.get("bin") in s["bins"] else None
        spans = tc.manual_inouts(plan, c)
        if spans:
            for sp in spans:
                groups.setdefault((si, b or UNSORTED), []).append({"clip": c, "label": b, "span": sp})
        else:
            groups.setdefault((si, b or UNSORTED), []).append({"clip": c, "label": b})
    for lst in groups.values():
        lst.sort(key=lambda e: (e["clip"].t_start is None, e["clip"].t_start, (e.get("span") or (0.0,))[0]))
        for pos, e in enumerate(lst):
            e["pos"] = pos
            e["level"] = star_level(plan, e["clip"])
            e["cut"] = clip_cut(plan, e["clip"], e["label"], span=e.get("span"))
    ranges = d.get("bins") or {}
    bin_pins = d.get("bin_s") if isinstance(d.get("bin_s"), dict) else {}
    tl = tl_cfg(plan)
    tl_fps = float(tl_fps) if _num(tl_fps) and tl_fps > 0 else 25.0
    for (si, bname), lst in groups.items():                          # tốc độ từng clip: độ dài RA TIMELINE = In/Out gốc / hệ số; mọi số sau đây tính theo RA
        spec = speed_spec(tl, stages[si]["name"], bname)
        for e in lst:
            pp = speed_p(spec, e["clip"], tl_fps)
            c = e["cut"]
            e["p"] = pp
            c["len_src"] = c["len"]
            c["len"] = c["len"] / pp
            c["lmin"] = c["lmin"] / pp

    def bin_info(si, name, lst):
        sname = stages[si]["name"]
        nat = sum(e["cut"]["len"] for e in lst)
        user = (ranges.get(sname) or {}).get(name)
        ok2, v = check_bin_minmax(*user) if isinstance(user, (list, tuple)) and len(user) == 2 else (False, None)
        dmn, dmx, kind = default_bin_minmax(name, nat)
        mn, mx = v if ok2 else (dmn, dmx)
        hard_max = mx if ok2 else float("inf")                       # chưa đặt thì KHÔNG giới hạn
        kept_all, _gone = fit_bin(lst, min(nat, hard_max))           # tối đa bin này cho được (Truyền thống: nguyên clip)
        avail = sum(e["use"] for e in kept_all)
        pin = (bin_pins.get(sname) or {}).get(name) if isinstance(bin_pins.get(sname), dict) else None
        pin = min(float(pin), avail) if _num(pin) and pin >= 0 else None
        return {"name": name, "min": mn, "max": mx, "default_min": dmn, "default_max": dmx, "default_kind": kind, "edited": bool(ok2),
                "natural_s": round(nat, 1), "n_starred": len(lst), "avail_s": round(avail, 1), "pin": pin, "hard_max": hard_max,
                "track": block_track(tl, sname, name), "key": block_key(sname, name),
                "t0": min((e["clip"].t_start.timestamp() for e in lst if e["clip"].t_start), default=None)}

    stage_rows = []
    for si, s in enumerate(stages):
        names = list(s["bins"]) + ([UNSORTED] if (si, UNSORTED) in groups else [])
        bins = [bin_info(si, n, groups.get((si, n), [])) for n in names]
        stage_rows.append({"i": si, "name": s["name"], "bins": bins, "nat_cap": sum(b["avail_s"] for b in bins if b["track"] != "V2")})
    # mỗi giai đoạn MỘT số giây: giai đoạn anh gõ/kéo/khóa (stage_s) giữ nguyên (không quá số clip có), còn lại chia theo clip sao có
    stage_s = d.get("stage_s") if isinstance(d.get("stage_s"), dict) else {}
    locked_names = set(x for x in d.get("locked", []) if isinstance(x, str)) if isinstance(d.get("locked"), list) else set()
    pinned = {}
    for r in stage_rows:
        v = stage_s.get(r["name"])
        if _num(v) and 0 <= v <= STAGE_MAX_S:
            pinned[r["i"]] = min(float(v), r["nat_cap"])
    budgets = allocate_stages(target, [r["nat_cap"] for r in stage_rows], pinned)

    # ---- vòng A: mỗi bin trong mỗi giai đoạn được bao nhiêu giây, clip nào giữ / bỏ
    sparts = []
    for r, budget in zip(stage_rows, budgets):
        si = r["i"]
        bins = [b for b in r["bins"] if b["track"] != "V2"]          # khối chồng ở V2 KHÔNG cộng vào độ dài và không chia ngân sách
        v2bins = [b for b in r["bins"] if b["track"] == "V2"]
        pin_sum = sum(b["pin"] for b in bins if b["pin"] is not None)
        budget = max(budget, pin_sum)                               # anh kéo bin con: tổng giai đoạn không thấp hơn tổng các bin đã kéo
        free = [b for b in bins if b["pin"] is None]
        rem = budget - pin_sum
        caps = [b["avail_s"] for b in free]
        mins = [min(b["min"], c) for b, c in zip(free, caps)]       # chỉ Min anh tự đặt mới > 0
        room = sum(c - m for c, m in zip(caps, mins))
        if sum(caps) <= rem + 1e-9 or room <= 1e-9:
            ratio = 1.0 if sum(caps) <= rem + 1e-9 else 0.0
        else:
            ratio = max(0.0, min(1.0, (rem - sum(mins)) / room))
        if sum(mins) > rem + 1e-9 and sum(caps) > rem:
            warnings.append({"kind": "stage_over", "stage": r["name"],
                             "text": "Giai đoạn “%s”: tổng Min các bin (%d giây) vượt phần lấy (%d giây). Hãy tăng thời lượng giai đoạn hoặc giảm Min." % (
                                 r["name"], round(sum(mins)), round(rem))})
        parts = []
        for b in bins:
            lst = groups.get((si, b["name"]), [])
            if b["pin"] is not None:
                B = b["pin"]
            else:
                k = free.index(b)
                B = mins[k] + (caps[k] - mins[k]) * ratio
            kept, dropped = fit_bin(lst, B)
            parts.append({"b": b, "B": B, "kept": kept, "dropped": dropped})
        left = budget - sum(e["use"] for p_ in parts for e in p_["kept"])      # bù số dư do chỉ bỏ NGUYÊN clip (Truyền thống)
        for p_ in sorted(parts, key=lambda q: -len(q["dropped"])):
            if p_["b"]["pin"] is not None:
                continue
            for e in reversed(list(p_["dropped"])):
                btot = sum(x["use"] for x in p_["kept"])
                ln = e["cut"]["len"]
                if ln <= left + 1e-9 and btot + ln <= p_["b"]["hard_max"] + 1e-9:
                    e["use"] = ln
                    p_["kept"].append(e)
                    p_["dropped"].remove(e)
                    left -= ln
        for b in v2bins:                                            # V2: lấy theo số anh kéo, không thì lấy hết clip sao của khối
            lst = groups.get((si, b["name"]), [])
            B = b["pin"] if b["pin"] is not None else b["avail_s"]
            kept, dropped = fit_bin(lst, B)
            parts.append({"b": b, "B": B, "kept": kept, "dropped": dropped, "v2": True})
        sparts.append({"r": r, "budget": budget, "parts": parts, "fixed": si in pinned or pin_sum > 0})
    # bù toàn cục: tổng còn thiếu mà vẫn có clip đã bỏ ở giai đoạn chưa chốt thì đặt lại clip quan trọng nhất nếu làm tổng gần mục tiêu hơn
    total0 = sum(e["use"] for sp in sparts for p_ in sp["parts"] if not p_.get("v2") for e in p_["kept"])
    while starred and total0 < target - 0.5:
        best = None
        for sp in sparts:
            if sp["fixed"]:
                continue
            for p_ in sp["parts"]:
                if p_.get("v2"):
                    continue
                btot = sum(x["use"] for x in p_["kept"])
                for e in p_["dropped"]:
                    ln = e["cut"]["len"]
                    gap = target - total0                           # đặt lại clip nếu làm tổng GẦN mục tiêu hơn và không vượt quá TOL_S
                    if 0 < ln <= 2 * gap + 1e-9 and ln - gap <= TOL_S and btot + ln <= p_["b"]["hard_max"] + 1e-9:
                        key = (e["level"], -e["pos"])
                        if best is None or key > best[0]:
                            best = (key, p_, e)
        if best is None:
            break
        _k, p_, e = best
        e["use"] = e["cut"]["len"]
        p_["kept"].append(e)
        p_["dropped"].remove(e)
        total0 += e["use"]

    # ---- vòng B: ghi số liệu từng bin / giai đoạn, danh sách đoạn cho timeline
    items, total = [], 0.0
    for sp in sparts:
        r, budget = sp["r"], sp["budget"]
        si = r["i"]
        stage_total, v2_total, dropped_clips = 0.0, 0.0, []
        for p_ in sp["parts"]:
            b, kept, dropped = p_["b"], p_["kept"], p_["dropped"]
            for e in dropped:
                dropped_clips.append({"name": e["clip"].rel.rsplit("/", 1)[-1], "len": round(e["cut"]["len"], 1), "bin": b["name"],
                                      "_k": (e["level"], -e["pos"])})
            btotal = sum(e["use"] for e in kept)
            b.update({"budget_s": round(p_["B"], 1), "total_s": round(btotal, 1), "shots": len(kept), "dropped": len(dropped)})
            if p_.get("v2"):
                v2_total += btotal
            else:
                stage_total += btotal
            for e in kept:
                c, cut = e["clip"], e["cut"]
                pp = e.get("p", 1.0)
                out = cut["in_s"] + e["use"] * pp                       # In/Out GỐC: Slow giữ nguyên điểm vào, độ dài gốc = RA x hệ số
                if c.dur:
                    out = min(out, float(c.dur))
                items.append({"uid": c.uid, "stage": si, "bin": b["name"], "key": b["key"], "track": b["track"], "in_s": round(cut["in_s"], 2),
                              "out_s": round(out, 2), "p": round(pp, 4), "src_dur": round(out - cut["in_s"], 2),
                              "dur": round((out - cut["in_s"]) / pp, 2), "t": c.t_start, "fixed": cut["fixed"]})
            if b["edited"] and b["n_starred"] and b["natural_s"] > b["max"] + 1e-9:
                warnings.append({"kind": "bin_over", "stage": r["name"], "bin": b["name"],
                                 "text": "Bin “%s” (%s): clip sao dài %d giây, vượt Max %d giây bạn đặt; đã cắt gọt%s." % (
                                     b["name"], r["name"], round(b["natural_s"]), round(b["max"]),
                                     (", bỏ %d clip ít ưu tiên" % len(dropped)) if dropped else "")})
            if b["edited"] and b["min"] > 0 and btotal + 1e-9 < b["min"] and b["n_starred"]:
                warnings.append({"kind": "bin_short", "stage": r["name"], "bin": b["name"],
                                 "text": "Bin “%s” (%s) lấy %d giây, ít hơn Min %d giây bạn đặt (có %d clip sao). Không tự thêm clip chưa sao." % (
                                     b["name"], r["name"], round(btotal), round(b["min"]), b["n_starred"])})
        dropped_clips.sort(key=lambda c: c["_k"])                    # ít ưu tiên nhất đứng đầu
        for c in dropped_clips:
            c.pop("_k", None)
        have = sum(b["natural_s"] for b in r["bins"] if b["track"] != "V2")
        r["share"] = round(budget / target, 4) if target else 0.0
        r["budget_s"] = round(budget, 1)
        r["total_s"] = round(stage_total, 1)
        r["natural_s"] = round(have, 1)
        r["avail_s"] = round(r["nat_cap"], 1)
        r["v2_s"] = round(v2_total, 1)
        r["n_starred"] = sum(b["n_starred"] for b in r["bins"])
        r["n_bins"] = sum(1 for b in r["bins"] if b["n_starred"])
        r["n_used"] = sum(b["shots"] for b in r["bins"])
        r["dropped_n"] = len(dropped_clips)
        r["dropped_s"] = round(max(0.0, have - stage_total), 1)
        r["dropped_clips"] = dropped_clips
        r["maxed"] = bool(r["n_starred"]) and stage_total >= have - 0.5
        r["pinned"] = si in pinned
        r["locked"] = si in pinned and r["name"] in locked_names
        total += stage_total
    items.sort(key=lambda it: (it["stage"], it["t"] is None, it["t"]))
    for it in items:
        it.pop("t", None)
    if not starred:
        warnings.append({"kind": "no_star", "text": "Chưa có clip nào gắn sao ★. Gắn sao (phím J) ở Bước 2 trước."})
    if excluded:
        warnings.append({"kind": "excluded", "text": "%d clip có sao nằm ngoài mọi giai đoạn nên không đưa lên timeline." % excluded})
    lo, hi = SUGGEST_RANGE_MIN
    if not (lo <= tmin <= hi):
        warnings.append({"kind": "target_range", "text": "Mục tiêu %g phút nằm ngoài khoảng gợi ý %g–%g phút." % (tmin, lo, hi)})
    if starred and total + 1e-9 < target * 0.95:
        warnings.append({"kind": "target_short", "text": "Tổng sau cắt gọt (%s) ngắn hơn mục tiêu %s: chưa đủ clip có sao. Không tự thêm clip." % (mmss(total), mmss(target))})
    delta = total - target
    state = "no_star" if not starred else ("short" if delta < -TOL_S else ("over" if delta > TOL_S else "ok"))
    keys = ("name", "share", "budget_s", "total_s", "bins", "natural_s", "avail_s", "n_starred", "n_bins", "n_used", "dropped_n", "dropped_s",
            "dropped_clips", "maxed", "pinned", "locked", "v2_s")
    for r in stage_rows:
        for b in r["bins"]:
            b.pop("hard_max", None)
    return {"target_min": tmin, "target_s": target, "total_s": round(total, 1), "delta_s": round(delta, 1),
            "short_s": round(max(0.0, target - total), 1) if state == "short" else 0.0,
            "v2_s": round(sum(r["v2_s"] for r in stage_rows), 1), "tl_fps": tl_fps,
            "shares": [round(sp["budget"] / target, 4) if target else 0.0 for sp in sparts],
            "stages": [{k: r[k] for k in keys} for r in stage_rows], "state": state, "tol_s": TOL_S,
            "items": items, "warnings": warnings, "n_starred": len(starred), "n_used": len(items), "n_excluded": excluded,
            "n_clips": len(clips)}


def mmss(s):
    s = int(round(s))
    return "%d:%02d" % (s // 60, s % 60)


def normalize_shares(values, index, new_value):
    """Đổi tỉ lệ giai đoạn index thành new_value (0..1), phần còn lại co giãn theo tỉ lệ cũ để TỔNG luôn bằng 1. Mỗi giai đoạn tối thiểu MIN_STAGE_SHARE."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [1.0]
    new_value = max(MIN_STAGE_SHARE, min(1.0 - MIN_STAGE_SHARE * (n - 1), float(new_value)))
    rest_old = sum(v for i, v in enumerate(values) if i != index) or 1.0
    rest_new = 1.0 - new_value
    out = []
    for i, v in enumerate(values):
        out.append(new_value if i == index else max(MIN_STAGE_SHARE, v / rest_old * rest_new))
    s = sum(out)
    return [x / s for x in out]


def allocate_stages(target, avail, pinned):
    """Chia `target` giây cho các giai đoạn. avail[i] = tổng clip sao giai đoạn i có thể cho (đã chặn bởi Max từng bin). pinned = {i: giây anh chốt}
    (giữ nguyên, kể cả khi lớn hơn avail: khi đó giai đoạn thiếu clip và hiện "thiếu"). Giai đoạn còn lại chia phần dư theo TỈ LỆ avail, mỗi giai
    đoạn không vượt quá avail của nó (phần thừa chia tiếp cho giai đoạn còn chỗ). Không bịa clip: tổng có thể < target."""
    n = len(avail)
    budget = [0.0] * n
    for i, v in pinned.items():
        budget[i] = float(v)
    rem = max(0.0, float(target) - sum(pinned.values()))
    act = [i for i in range(n) if i not in pinned]
    while act and rem > 1e-9:
        tot = sum(avail[i] for i in act)
        if tot <= 1e-9:
            break
        full = [i for i in act if rem >= tot - 1e-9 or rem * avail[i] / tot >= avail[i] - 1e-9]
        if not full:
            for i in act:
                budget[i] = rem * avail[i] / tot
            break
        for i in full:
            budget[i] = float(avail[i])
            rem -= avail[i]
            act.remove(i)
    return budget


def _with_durations(plan, d):
    p = dict(plan)
    p["durations"] = d
    return p


def plan_rebalance(plan, clips, assign, stages, r=None, tl_fps=None):
    """(a) "Tự kéo thêm cho đủ": bỏ chốt (số gõ/kéo) của các giai đoạn CHƯA khóa để chúng co giãn, dồn phần thiếu sang giai đoạn còn dư clip sao
    (không vượt số clip có). Giai đoạn KHÓA giữ nguyên. Trả (durations mới, kết quả build mới) hoặc None nếu không làm tăng tổng."""
    r = r or build(plan, clips, assign, stages, tl_fps)
    tl_fps = r["tl_fps"]
    d = copy.deepcopy(plan.get("durations") or {})
    locked = set(d.get("locked") or [])
    changed = False
    for s in r["stages"]:
        if s["pinned"] and s["name"] not in locked and not s["maxed"]:
            (d.get("stage_s") or {}).pop(s["name"], None)
            (d.get("bin_s") or {}).pop(s["name"], None)
            changed = True
    if not changed:
        return None
    r2 = build(_with_durations(plan, d), clips, assign, stages, tl_fps)
    if r2["total_s"] - r["total_s"] < 1.0:
        return None
    return d, r2


def plan_lower_target(plan, clips, assign, stages, r=None, tl_fps=None):
    """(b) "Hạ mục tiêu xuống <số Hiện Tại>": mục tiêu = tổng đang giữ (tròn giây); không hạ dưới 1 phút. Trả (durations mới, build mới) hoặc None."""
    r = r or build(plan, clips, assign, stages, tl_fps)
    if r["total_s"] < TARGET_LIMITS_MIN[0] * 60.0:
        return None
    d = copy.deepcopy(plan.get("durations") or {})
    d["target_min"] = round(round(r["total_s"]) / 60.0, 4)           # tròn giây, đúng con số "Hiện Tại" trên màn hình
    return d, build(_with_durations(plan, d), clips, assign, stages, r["tl_fps"])


def best_unslow(plan, clips, assign, stages, r=None, tl_fps=None):
    """Khối Slow đưa về 100% bớt được nhiều thời gian trên V1 nhất. Trả (khóa khối, giây bớt được) hoặc None. Chỉ tính, không ghi."""
    r = r or build(plan, clips, assign, stages, tl_fps)
    tl = tl_cfg(plan)
    best = None
    for s in r["stages"]:
        for b in s["bins"]:
            if b["n_starred"] and b["track"] != "V2" and speed_spec(tl, s["name"], b["name"]) is not None:
                d = copy.deepcopy(plan.get("durations") or {})
                d.setdefault("tl", {}).setdefault("blk", {}).setdefault(s["name"], {}).setdefault(b["name"], {})["speed"] = 100
                r2 = build(_with_durations(plan, d), clips, assign, stages, r["tl_fps"])
                saving = r["total_s"] - r2["total_s"]
                if saving >= 1.0 and (best is None or saving > best[1]):
                    best = (b["key"], saving)
    return best


def plan_fit_over(plan, clips, assign, stages, r=None, tl_fps=None):
    """"Bỏ clip ít ưu tiên cho vừa": khi Hiện Tại dư so với mục tiêu, thả các số anh đã kéo/gõ ở cụm CHƯA khóa để Trợ lý tự rút/bỏ clip ít ưu tiên
    cho vừa mục tiêu. Chỉ khi anh bấm; panel KHÔNG tự bỏ clip. Trả (durations mới, build mới) hoặc None."""
    r = r or build(plan, clips, assign, stages, tl_fps)
    d = copy.deepcopy(plan.get("durations") or {})
    locked = set(d.get("locked") or [])
    changed = False
    for s in r["stages"]:
        if s["pinned"] and s["name"] not in locked:
            (d.get("stage_s") or {}).pop(s["name"], None)
            (d.get("bin_s") or {}).pop(s["name"], None)
            changed = True
    if not changed:
        return None
    r2 = build(_with_durations(plan, d), clips, assign, stages, r["tl_fps"])
    if r["total_s"] - r2["total_s"] < 1.0:
        return None
    return d, r2


def unstarred_by_bin(plan, clips, assign, stages):
    """Clip CHƯA sao theo (chỉ số giai đoạn, tên bin) -> (số clip, tổng độ dài gợi ý). Để gợi ý "quay lại Bước 3 chọn thêm clip"."""
    out = {}
    for c in clips:
        if tc.is_starred(plan, c):
            continue
        si = assign.get(c.uid)
        man = tc.manual_of(plan, c)
        if man:
            si = next((i for i, s in enumerate(stages) if s["name"] == man.get("stage")), si)
        if si is None or si < 0 or si >= len(stages):
            continue
        lab = tc.label_of(plan, c)
        b = lab["bin"] if lab and lab.get("stage") == stages[si]["name"] and lab.get("bin") in stages[si]["bins"] else None
        n, t = out.get((si, b or UNSORTED), (0, 0.0))
        spans = tc.manual_inouts(plan, c) or [None]
        add_len = sum(clip_cut(plan, c, b, span=sp)["len"] for sp in spans)
        out[(si, b or UNSORTED)] = (n + len(spans), t + add_len)
    return out


def advise(plan, clips, assign, stages, r):
    """Cột phải "Chưa đạt mục tiêu": vì sao thiếu/dư và ba gợi ý một chạm. Trả dict:
    {state, title, reasons[str], rebalance: {title, text} | None, lower: {title, text, target_min} | None, step3: {stage, bin, title, text} | None}."""
    titles = {"ok": "Đạt mục tiêu", "short": "Chưa đạt mục tiêu", "over": "Đang dài hơn mục tiêu", "no_star": "Chưa có clip sao"}
    out = {"state": r["state"], "reasons": [], "rebalance": None, "lower": None, "step3": None, "unslow": None, "fit": None, "title": titles[r["state"]]}
    st = r["state"]
    if st == "no_star":
        out["reasons"].append("Chưa có clip sao ★. Gắn sao (phím J) ở Bước 2 hoặc Bước 3 rồi quay lại.")
        return out
    if st == "ok":
        out["reasons"].append("Hiện Tại %s trên mục tiêu %s. Có thể đưa lên Timeline mới." % (mmss(r["total_s"]), mmss(r["target_s"])))
        return out
    if st in ("over", "short"):
        bu = best_unslow(plan, clips, assign, stages, r, r["tl_fps"])
        if bu:
            name = bu[0].split("|", 1)[1]
            out["unslow"] = {"key": bu[0], "title": "Đưa %s về 100%%" % name, "text": "Bớt %s trên timeline." % mmss(bu[1])}
    if st == "over":
        fit = plan_fit_over(plan, clips, assign, stages, r, r["tl_fps"])
        if fit:
            r2 = fit[1]
            out["fit"] = {"title": "Bỏ clip ít ưu tiên cho vừa %s" % mmss(r["target_s"]),
                          "text": "Thả số đã kéo của cụm chưa khóa, Trợ lý rút/bỏ %d clip ít ưu tiên (bạn xem danh sách bỏ trong dòng cụm). Hiện Tại còn %s." % (
                              max(0, r["n_used"] - r2["n_used"]), mmss(r2["total_s"]))}
        fixed = [x for x in r["stages"] if x["pinned"]]
        if fixed and sum(x["total_s"] for x in fixed) >= r["target_s"] - TOL_S:
            out["reasons"].append("Giai đoạn bạn kéo/gõ/khóa (%s) đã lấy %s, bằng hoặc hơn mục tiêu %s nên các giai đoạn khác chỉ còn lấy ít hoặc không lấy. "
                                  "Kéo bớt số đó, mở khóa hoặc nâng mục tiêu." % (", ".join(x["name"] for x in fixed), mmss(sum(x["total_s"] for x in fixed)), mmss(r["target_s"])))
        else:
            out["reasons"].append("Hiện Tại %s, dài hơn mục tiêu %s. Thường do Min bạn đặt trong “Giới hạn nâng cao” lớn hơn phần còn lại; hạ Min hoặc mở khóa giai đoạn."
                                  % (mmss(r["total_s"]), mmss(r["target_s"])))
        return out
    with_star = [s for s in r["stages"] if s["n_starred"]]
    maxed = [s for s in with_star if s["maxed"]]
    spare = [s for s in with_star if s["natural_s"] - s["total_s"] >= TOL_S / 2 and not s["maxed"]]
    if with_star and len(maxed) == len(with_star):
        out["reasons"].append("Mọi giai đoạn đã kéo hết cỡ: tổng clip sao chỉ có %s, ít hơn mục tiêu %s." % (mmss(r["total_s"]), mmss(r["target_s"])))
    else:
        for s in maxed:
            out["reasons"].append("%s đã kéo hết cỡ (chỉ có %s clip sao)." % (s["name"], mmss(s["natural_s"])))
        for s in spare:
            out["reasons"].append("%s còn dư %s clip sao chưa lấy." % (s["name"], mmss(s["natural_s"] - s["total_s"])))
    rb = plan_rebalance(plan, clips, assign, stages, r, r["tl_fps"])
    if rb:
        r2 = rb[1]
        moves = ["%s +%s (còn dư %s clip sao)" % (a["name"], mmss(b["total_s"] - a["total_s"]), mmss(a["natural_s"] - a["total_s"]))
                 for a, b in zip(r["stages"], r2["stages"]) if b["total_s"] - a["total_s"] >= 1.0]
        txt = ", ".join(moves) + "."
        lk = [a["name"] for a in r["stages"] if a["locked"]]
        if lk:
            txt += " Giai đoạn bạn khóa (%s) giữ nguyên %s." % (", ".join(lk), ", ".join(mmss(a["total_s"]) for a in r["stages"] if a["locked"]))
        if r2["state"] == "short":
            txt += " Vẫn còn thiếu %s." % mmss(r2["short_s"])
        out["rebalance"] = {"title": "Tự kéo thêm cho đủ %s" % mmss(r["target_s"]), "text": txt.strip(), "total_s": r2["total_s"]}
    lw = plan_lower_target(plan, clips, assign, stages, r, r["tl_fps"])
    if lw:
        out["lower"] = {"title": "Hạ mục tiêu xuống %s" % mmss(lw[1]["target_s"]), "target_min": lw[0]["target_min"],
                        "text": "Giữ hết clip sao đang có, không phải thêm clip nào."}
    un = unstarred_by_bin(plan, clips, assign, stages)
    maxed_names = set(s["name"] for s in maxed)
    cand = [(t, si, b, n) for (si, b), (n, t) in un.items() if t > 0 and stages[si]["name"] in maxed_names]
    if not cand:
        cand = [(t, si, b, n) for (si, b), (n, t) in un.items() if t > 0]
    if cand:
        t, si, b, n = max(cand)
        out["step3"] = {"stage": si, "bin": b, "title": "Quay lại Bước 3 chọn thêm clip",
                        "text": "%s còn %s clip chưa gắn sao (%d clip%s). Mở thẳng chỗ đó để gắn thêm." % (
                            stages[si]["name"], mmss(t), n, "" if b == UNSORTED else ", bin " + b)}
    return out
