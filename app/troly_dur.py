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
FIXED_TOTALS = (                          # ĐỀ XUẤT: (từ khóa tên bin, min, max) giây
    (("decor", "chi tiết", "trang trí"), 10.0, 20.0),
    (("beauty",), 20.0, 30.0),
)
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


def clip_cut(plan, clip, label):
    """Cách cắt một clip có sao: dict(in_s, out_s, len, lmin, fixed). In/Out anh đặt tay THẮNG (cố định, không rút thêm);
    không thì gợi ý theo bảng quy tắc Bước 3 (rules, kiểu quay, số giây Truyền thống). lmin = độ dài tối thiểu được rút tới:
    min của quy tắc bin; Truyền thống thì không rút (chỉ bỏ clip)."""
    dur = float(clip.dur or 0)
    m = tc.manual_inout(plan, clip)
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
    """(min, max, 'de_xuat_co_dinh' | 'tu_suy_ra') cho một bin khi anh chưa sửa."""
    lb = (name or "").lower()
    for keys, mn, mx in FIXED_TOTALS:
        if any(k in lb for k in keys):
            return mn, mx, "co_dinh"
    mx = min(BIN_SCALE_S, round(natural, 1))
    mn = min(mx, round(DERIVE_MIN_RATIO * natural, 1))
    return mn, mx, "tu_suy_ra"


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
    for e in kept:
        c = e["cut"]
        ln = c["len"] if r >= 1.0 else c["lmin"] + (c["len"] - c["lmin"]) * r
        if not c["fixed"] and ln < c["len"]:
            ln = max(c["lmin"], _floor1(ln))
        e["use"] = min(ln, c["len"])
    return kept, dropped


def build(plan, clips, assign, stages):
    """Kế hoạch cắt gọt toàn project (xem docstring đầu file). Trả dict:
      target_s, total_s, delta_s, shares, stages[{name, share, budget_s, total_s, bins[{name, min, max, default, edited, natural_s, total_s,
      shots, dropped}]}], items[{uid, stage, bin, in_s, out_s, dur}] theo thứ tự giai đoạn rồi giờ quay, warnings[], n_starred, n_used, n_excluded."""
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
        groups.setdefault((si, b or UNSORTED), []).append({"clip": c, "label": b})
    for lst in groups.values():
        lst.sort(key=lambda e: (e["clip"].t_start is None, e["clip"].t_start))
        for pos, e in enumerate(lst):
            e["pos"] = pos
            e["level"] = star_level(plan, e["clip"])
            e["cut"] = clip_cut(plan, e["clip"], e["label"])
    ranges = d.get("bins") or {}

    def bin_info(si, name, lst):
        nat = sum(e["cut"]["len"] for e in lst)
        dmn, dmx, kind = default_bin_minmax(name, nat)
        user = (ranges.get(stages[si]["name"]) or {}).get(name)
        ok2, v = check_bin_minmax(*user) if isinstance(user, (list, tuple)) and len(user) == 2 else (False, None)
        mn, mx = v if ok2 else (dmn, dmx)
        return {"name": name, "min": mn, "max": mx, "default_min": dmn, "default_max": dmx, "default_kind": kind, "edited": bool(ok2),
                "natural_s": round(nat, 1), "n_starred": len(lst)}

    stage_rows = []
    for si, s in enumerate(stages):
        names = list(s["bins"]) + ([UNSORTED] if (si, UNSORTED) in groups else [])
        bins = [bin_info(si, n, groups.get((si, n), [])) for n in names]
        stage_rows.append({"i": si, "name": s["name"], "bins": bins,
                           "nat_cap": sum(min(b["natural_s"], b["max"]) for b in bins)})
    # mỗi giai đoạn MỘT số giây: giai đoạn anh gõ/khóa (stage_s) giữ nguyên, còn lại chia theo clip sao có (allocate_stages)
    stage_s = d.get("stage_s") if isinstance(d.get("stage_s"), dict) else {}
    locked_names = set(x for x in d.get("locked", []) if isinstance(x, str)) if isinstance(d.get("locked"), list) else set()
    pinned = {}
    for r in stage_rows:
        v = stage_s.get(r["name"])
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and 0 <= v <= STAGE_MAX_S:
            pinned[r["i"]] = float(v)
    budgets = allocate_stages(target, [r["nat_cap"] for r in stage_rows], pinned)
    shares = [x / target if target else 0.0 for x in budgets]
    items, total = [], 0.0
    for r, share, budget in zip(stage_rows, shares, budgets):
        si = r["i"]
        dropped_clips = []
        caps = [min(b["natural_s"], b["max"]) for b in r["bins"]]
        mins = [min(b["min"], c) for b, c in zip(r["bins"], caps)]
        # Min mặc định (chưa sửa, chỉ là đề xuất) co lại cho vừa phần được chia, để số anh gõ cho giai đoạn luôn được tôn trọng;
        # Min anh tự sửa là CỨNG: vượt thì giữ Min và báo "stage_over".
        if sum(mins) > budget + 1e-9:
            hard = sum(m for b, m in zip(r["bins"], mins) if b["edited"])
            soft = sum(m for b, m in zip(r["bins"], mins) if not b["edited"])
            f = max(0.0, min(1.0, (budget - hard) / soft)) if soft > 0 else 1.0
            mins = [m if b["edited"] else m * f for b, m in zip(r["bins"], mins)]
        room = sum(c - m for c, m in zip(caps, mins))
        if sum(caps) <= budget + 1e-9 or room <= 1e-9:
            ratio = 1.0 if sum(caps) <= budget + 1e-9 else 0.0
        else:
            ratio = max(0.0, min(1.0, (budget - sum(mins)) / room))
        if sum(mins) > budget + 1e-9 and sum(caps) > budget:
            warnings.append({"kind": "stage_over", "stage": r["name"],
                             "text": "Giai đoạn “%s”: tổng Min các bin (%d giây) vượt phần chia (%d giây). Hãy tăng tỉ lệ giai đoạn hoặc giảm Min." % (
                                 r["name"], round(sum(mins)), round(budget))})
        stage_total = 0.0
        for b, cap, mn_eff in zip(r["bins"], caps, mins):
            lst = groups.get((si, b["name"]), [])
            B = mn_eff + (cap - mn_eff) * ratio
            kept, dropped = fit_bin(lst, B)
            for e in dropped:
                dropped_clips.append({"name": e["clip"].rel.rsplit("/", 1)[-1], "len": round(e["cut"]["len"], 1), "bin": b["name"]})
            btotal = sum(e["use"] for e in kept)
            b.update({"budget_s": round(B, 1), "total_s": round(btotal, 1), "shots": len(kept), "dropped": len(dropped)})
            stage_total += btotal
            for e in kept:
                c, cut = e["clip"], e["cut"]
                out = cut["in_s"] + e["use"]
                if c.dur:
                    out = min(out, float(c.dur))
                items.append({"uid": c.uid, "stage": si, "bin": b["name"], "in_s": round(cut["in_s"], 2), "out_s": round(out, 2),
                              "dur": round(out - cut["in_s"], 2), "t": c.t_start, "fixed": cut["fixed"]})
            if b["n_starred"] and b["natural_s"] > b["max"] + 1e-9:
                warnings.append({"kind": "bin_over", "stage": r["name"], "bin": b["name"],
                                 "text": "Bin “%s” (%s): clip sao dài %d giây, vượt Max %d giây; đã cắt gọt%s." % (
                                     b["name"], r["name"], round(b["natural_s"]), round(b["max"]),
                                     (", bỏ %d clip ít ưu tiên" % len(dropped)) if dropped else "")})
            elif dropped:
                warnings.append({"kind": "bin_drop", "stage": r["name"], "bin": b["name"],
                                 "text": "Bin “%s” (%s): bỏ %d clip ít ưu tiên để vừa phần chia của giai đoạn." % (b["name"], r["name"], len(dropped))})
            if b["min"] > 0 and btotal + 1e-9 < b["min"] and not (b["n_starred"] and b["natural_s"] > b["max"]):
                warnings.append({"kind": "bin_short", "stage": r["name"], "bin": b["name"],
                                 "text": "Bin “%s” (%s) thiếu %d giây để đạt Min %d giây (có %d clip sao, tổng %d giây). Không tự thêm clip chưa sao." % (
                                     b["name"], r["name"], round(b["min"] - btotal), round(b["min"]), b["n_starred"], round(btotal))})
        r["share"] = round(share, 4)
        r["budget_s"] = round(budget, 1)
        r["total_s"] = round(stage_total, 1)
        r["natural_s"] = round(sum(b["natural_s"] for b in r["bins"]), 1)
        r["avail_s"] = round(r["nat_cap"], 1)
        r["n_starred"] = sum(b["n_starred"] for b in r["bins"])
        r["n_bins"] = sum(1 for b in r["bins"] if b["n_starred"])
        r["n_used"] = sum(b["shots"] for b in r["bins"])
        r["dropped_n"] = len(dropped_clips)
        r["dropped_s"] = round(max(0.0, r["natural_s"] - stage_total), 1)
        r["dropped_clips"] = dropped_clips
        r["short_s"] = round(max(0.0, budget - stage_total), 1)
        r["short_kind"] = "" if r["short_s"] <= TOL_S / 2 else ("no_clips" if budget > r["avail_s"] + TOL_S / 2 else "round")
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
            "dropped_clips", "short_s", "short_kind", "pinned", "locked")
    return {"target_min": tmin, "target_s": target, "total_s": round(total, 1), "delta_s": round(delta, 1), "shares": [round(x, 4) for x in shares],
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


def _clamp_overasking(r, d, include_locked):
    """Giai đoạn anh chốt nhiều hơn số clip sao có: hạ số chốt xuống bằng số có. Trả số giai đoạn đã đổi."""
    ss = d.setdefault("stage_s", {})
    locked = set(d.get("locked") or [])
    n = 0
    for s in r["stages"]:
        if s["pinned"] and s["budget_s"] > s["avail_s"] + TOL_S / 2 and (include_locked or s["name"] not in locked):
            ss[s["name"]] = round(s["avail_s"], 1)
            n += 1
    return n


def plan_rebalance(plan, clips, assign, stages, r=None):
    """(a) "Chia lại cho đủ": dồn phần thiếu sang giai đoạn còn dư clip sao. Giai đoạn KHÓA giữ nguyên; giai đoạn anh gõ số mà thiếu clip thì hạ
    xuống bằng số clip có. Trả (durations mới, kết quả build mới) hoặc None nếu không cải thiện được."""
    r = r or build(plan, clips, assign, stages)
    d = copy.deepcopy(plan.get("durations") or {})
    if not _clamp_overasking(r, d, include_locked=False):
        return None
    r2 = build(_with_durations(plan, d), clips, assign, stages)
    if r2["total_s"] - r["total_s"] < 1.0:
        return None
    return d, r2


def plan_lower_target(plan, clips, assign, stages, r=None):
    """(b) "Hạ mục tiêu xuống <số đang giữ>": mục tiêu = tổng đang giữ; giai đoạn chốt nhiều hơn số clip có thì hạ xuống bằng số có (kể cả đã khóa,
    vì khóa số không có clip thì không đạt được). Trả (durations mới, kết quả build mới) hoặc None."""
    r = r or build(plan, clips, assign, stages)
    d = copy.deepcopy(plan.get("durations") or {})
    _clamp_overasking(r, d, include_locked=True)
    if r["total_s"] < TARGET_LIMITS_MIN[0] * 60.0:
        return None
    d["target_min"] = round(round(r["total_s"]) / 60.0, 4)           # tròn giây, đúng con số "Đang giữ" hiện trên màn hình
    return d, build(_with_durations(plan, d), clips, assign, stages)


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
        out[(si, b or UNSORTED)] = (n + 1, t + clip_cut(plan, c, b)["len"])
    return out


def advise(plan, clips, assign, stages, r):
    """Cột phải "Chưa đạt mục tiêu": vì sao thiếu/dư và ba gợi ý một chạm. Trả dict:
    {state, title, reasons[str], rebalance: {title, text} | None, lower: {title, text, target_min} | None, step3: {stage, bin, title, text} | None}."""
    titles = {"ok": "Đạt mục tiêu", "short": "Chưa đạt mục tiêu", "over": "Đang dài hơn mục tiêu", "no_star": "Chưa có clip sao"}
    out = {"state": r["state"], "reasons": [], "rebalance": None, "lower": None, "step3": None, "title": titles[r["state"]]}
    st = r["state"]
    if st == "no_star":
        out["reasons"].append("Chưa có clip sao ★. Gắn sao (phím J) ở Bước 2 hoặc Bước 3 rồi quay lại.")
        return out
    if st == "ok":
        out["reasons"].append("Đang giữ %s trên mục tiêu %s. Có thể đưa lên Timeline mới." % (mmss(r["total_s"]), mmss(r["target_s"])))
        return out
    if st == "over":
        out["reasons"].append("Tổng đang giữ %s, dài hơn mục tiêu %s. Thường do Min của các bin hoặc số giây anh chốt/khóa lớn hơn phần còn lại; "
                              "hạ Min hoặc mở khóa giai đoạn." % (mmss(r["total_s"]), mmss(r["target_s"])))
        return out
    lack = [s for s in r["stages"] if s["short_kind"] == "no_clips"]
    for s in lack:
        out["reasons"].append("%s chỉ có %s clip sao, ít hơn %s được chia." % (s["name"], mmss(s["avail_s"]), mmss(s["budget_s"])))
    for s in r["stages"]:
        if s["dropped_s"] > TOL_S / 2 and s["short_kind"] != "no_clips":
            out["reasons"].append("%s đang dư %s clip sao phải bỏ." % (s["name"], mmss(s["dropped_s"])))
    if not lack:
        out["reasons"].append("Tổng clip sao còn lại ít hơn mục tiêu, hoặc Truyền thống chỉ bỏ nguyên clip nên lệch vài giây.")
    rb = plan_rebalance(plan, clips, assign, stages, r)
    if rb:
        r2 = rb[1]
        moves = ["%s %s%s" % (a["name"], "+" if b["budget_s"] > a["budget_s"] else "−", mmss(abs(b["budget_s"] - a["budget_s"])))
                 for a, b in zip(r["stages"], r2["stages"]) if abs(b["budget_s"] - a["budget_s"]) >= 1.0]
        txt = ", ".join(moves) + "."
        lk = [a["name"] for a in r["stages"] if a["locked"]]
        if lk:
            txt += " Giai đoạn anh khóa (%s) giữ nguyên." % ", ".join(lk)
        extra = [(b["n_used"] - a["n_used"], a["name"]) for a, b in zip(r["stages"], r2["stages"]) if b["n_used"] > a["n_used"]]
        if extra:
            txt += " Giữ thêm " + ", ".join("%d clip %s" % x for x in extra) + "."
        if r2["state"] == "short":
            txt += " Vẫn còn thiếu %s." % mmss(-r2["delta_s"])
        out["rebalance"] = {"title": "Chia lại cho đủ %s" % mmss(r["target_s"]), "text": txt.strip(), "total_s": r2["total_s"]}
    lw = plan_lower_target(plan, clips, assign, stages, r)
    if lw:
        out["lower"] = {"title": "Hạ mục tiêu xuống %s" % mmss(lw[1]["target_s"]), "target_min": lw[0]["target_min"],
                        "text": "Giữ hết clip sao đang có, không phải thêm clip nào."}
    un = unstarred_by_bin(plan, clips, assign, stages)
    short_names = set(s["name"] for s in lack)
    cand = [(t, si, b, n) for (si, b), (n, t) in un.items() if t > 0 and stages[si]["name"] in short_names]
    if not cand:
        cand = [(t, si, b, n) for (si, b), (n, t) in un.items() if t > 0]
    if cand:
        t, si, b, n = max(cand)
        out["step3"] = {"stage": si, "bin": b, "title": "Quay lại Bước 3 chọn thêm clip",
                        "text": "%s còn %s clip chưa gắn sao (%d clip%s). Mở thẳng chỗ đó để gắn thêm." % (
                            stages[si]["name"], mmss(t), n, "" if b == UNSORTED else ", bin " + b)}
    return out
