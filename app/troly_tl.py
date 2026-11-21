"""
troly_tl.py - Bước 5 bản 3 (ADR-0013): TIMELINE KÉO THẢ. LOGIC THUẦN: không gọi DaVinci, không ghi file.
Khối = bin con; cụm mẹ = giai đoạn. Thứ tự mặc định theo GIỜ QUAY THẬT, anh dời được cả cụm mẹ lẫn từng bin con (kể cả sang cụm khác).
Mỗi khối có track (V1 | V2 chồng), tốc độ (100% | Slow mượt tự tính | số), tiếng (bật/tắt). Mọi số giây là RA TIMELINE (= In/Out gốc / tốc độ);
Hiện Tại chỉ tính V1, khối ở V2 chạy chồng lên và KHÔNG cộng vào độ dài.

Lưu trong kế hoạch: plan["durations"]["tl"] = {
    "order": [tên giai đoạn],                      thứ tự cụm mẹ (chỉ có khi anh dời)
    "kids":  {tên cụm: ["Giai đoạn|Bin", ...]},    thứ tự khối con trong cụm (kể cả khối kéo từ cụm khác sang)
    "blk":   {giai đoạn: {bin: {"track": "V2", "at": giây, "speed": 50 | "auto", "mute": true, "manual": true}}},
    "stg":   {giai đoạn: {"speed": ..., "mute": ...}},   đặt ở cụm mẹ thì áp mọi khối con; khối con đặt riêng THẮNG
    "manual": true }                                dấu "xếp tay"
Khóa chỉ xuất hiện khi anh sửa. Số liệu thời lượng (Lấy, Có, thiếu/dư) do troly_dur.build tính; ở đây chỉ XẾP và đặt vị trí.
"""
import copy

import troly_dur as td

SPEED_LIMITS = (5.0, 400.0)


# ------------------------------------------------------------------ bố cục
def _members(r, tl):
    """(thứ tự cụm, {cụm: [khóa khối]}, {khóa: thông tin gốc}) theo cấu hình; chưa cấu hình thì theo giờ quay thật."""
    names = [s["name"] for s in r["stages"]]
    order = [n for n in (tl.get("order") or []) if n in names]
    order += [n for n in names if n not in order]
    info, origin = {}, {}
    for s in r["stages"]:
        for b in s["bins"]:
            if b["n_starred"] > 0:
                info[b["key"]] = (s["name"], b)
                origin[b["key"]] = s["name"]

    def t0(k):
        v = info[k][1].get("t0")
        return (v is None, v if v is not None else 0.0)

    kids_cfg = tl.get("kids") if isinstance(tl.get("kids"), dict) else {}
    members, placed = {n: [] for n in order}, set()
    for cl in order:
        for k in kids_cfg.get(cl, []) if isinstance(kids_cfg.get(cl, []), list) else []:
            if k in info and k not in placed:
                members[cl].append(k)
                placed.add(k)
    rest = {n: [] for n in order}
    for k in sorted(info, key=t0):
        if k not in placed:
            rest[origin[k]].append(k)
    for cl in order:
        members[cl] += rest[cl]
    return order, members, info


def speed_view(tl, stage, b, items):
    """Tốc độ hiển thị của một khối: {mode: '100'|'auto'|'custom'|'mixed', pct: số hoặc None, own: đặt riêng?}."""
    spec = td.speed_spec(tl, stage, b["name"])
    ps = sorted({round(i["p"], 3) for i in items})
    own = td._blk(tl, stage, b["name"]).get("speed") is not None
    if len(ps) > 1:
        mode, pct = "mixed", None
    else:
        pct = round(ps[0] * 100, 1) if ps else (100.0 if spec is None else (spec if spec != "auto" else None))
        mode = "auto" if spec == "auto" else ("100" if abs((pct or 100.0) - 100.0) < 0.05 else "custom")
    return {"mode": mode, "pct": pct, "own": own, "spec": spec}


def layout(r, plan):
    """Bố cục timeline từ kết quả troly_dur.build: cụm mẹ, khối con, vị trí bắt đầu / độ dài RA TIMELINE trên V1 và V2.
    Trả {order, clusters[{stage,i,color?,start,dur,kids,speed,mute}], blocks{khóa: {...}}, v1_end, v2_end, items_by_key}."""
    tl = td.tl_cfg(plan)
    order, members, info = _members(r, tl)
    by_key = {}
    for it in r["items"]:
        by_key.setdefault(it["key"], []).append(it)
    blocks = {}
    for cl in order:
        for k in members[cl]:
            stage, b = info[k]
            its = by_key.get(k, [])
            bl = td._blk(tl, stage, b["name"])
            blocks[k] = {"key": k, "stage": stage, "bin": b["name"], "cluster": cl, "track": b["track"], "dur": round(b["total_s"], 2),
                         "have": b["natural_s"], "avail": b["avail_s"], "pin": b["pin"], "n_clips": len(its), "n_starred": b["n_starred"],
                         "take_src": round(sum(i["src_dur"] for i in its), 2), "speed": speed_view(tl, stage, b, its),
                         "mute": td.mute_of(tl, stage, b["name"]), "mute_own": isinstance(bl.get("mute"), bool),
                         "manual": bool(bl.get("manual")), "at": bl.get("at"), "start": 0.0}
    t = 0.0
    clusters = []
    for i, cl in enumerate(order):
        c0 = t
        v1, v2 = [], []
        for k in members[cl]:
            bk = blocks[k]
            if bk["track"] == "V1":
                bk["start"] = round(t, 3)
                t += bk["dur"]
                v1.append(k)
            else:
                v2.append(k)
                bk["_default_at"] = c0
        spec = (tl.get("stg") or {}).get(cl) or {}
        sps = {(blocks[k]["speed"]["mode"], blocks[k]["speed"]["pct"]) for k in members[cl]}
        sp = {"mode": "mixed", "pct": None} if len(sps) > 1 else (
            {"mode": next(iter(sps))[0], "pct": next(iter(sps))[1]} if sps else {"mode": "100", "pct": 100.0})
        mutes = {blocks[k]["mute"] for k in members[cl]}
        clusters.append({"stage": cl, "i": next(j for j, s in enumerate(r["stages"]) if s["name"] == cl), "start": round(c0, 3), "dur": round(t - c0, 3),
                         "kids": members[cl], "v1": v1, "v2": v2, "speed": sp, "speed_own": spec.get("speed") is not None,
                         "mute": ("mixed" if len(mutes) > 1 else (True in mutes)), "mute_own": isinstance(spec.get("mute"), bool)})
    v1_end = t
    t2 = 0.0
    for k in sorted([k for k, b in blocks.items() if b["track"] == "V2"], key=lambda k: (blocks[k]["at"] if td._num(blocks[k]["at"]) else blocks[k]["_default_at"])):
        bk = blocks[k]
        at = bk["at"] if td._num(bk["at"]) else bk["_default_at"]
        bk["start"] = round(max(float(at), t2), 3)
        t2 = bk["start"] + bk["dur"]
        bk.pop("_default_at", None)
    for bk in blocks.values():
        bk.pop("_default_at", None)
    return {"order": order, "clusters": clusters, "blocks": blocks, "v1_end": round(v1_end, 3), "v2_end": round(t2, 3), "manual": bool(tl.get("manual")),
            "by_key": by_key}


def placements(r, plan):
    """Danh sách đoạn để đưa lên DaVinci, theo bố cục: [{uid, in_s, out_s (GỐC), p, track 'V1'|'V2', start_s, dur_s (RA), key, stage, bin, mute}].
    V1 theo thứ tự cụm rồi khối; V2 theo vị trí. Trong khối: theo giờ quay."""
    lay = layout(r, plan)
    out = []
    for k, bk in sorted(lay["blocks"].items(), key=lambda kv: (kv[1]["track"] != "V1", kv[1]["start"])):
        t = bk["start"]
        for it in lay["by_key"].get(k, []):
            out.append({"uid": it["uid"], "in_s": it["in_s"], "out_s": it["out_s"], "p": it["p"], "track": bk["track"], "start_s": round(t, 3),
                        "dur_s": it["dur"], "key": k, "stage": bk["stage"], "bin": bk["bin"], "mute": bk["mute"], "pct": round(it["p"] * 100, 1)})
            t += it["dur"]
    out.sort(key=lambda x: (x["track"] != "V1", x["start_s"]))
    return out


def summary(r, plan):
    """Cho hộp xác nhận: khối nào Slow, khối nào tắt tiếng, bao nhiêu clip ở V2."""
    lay = layout(r, plan)
    slow, muted, v2 = [], [], []
    for k in [k for c in lay["clusters"] for k in c["kids"]]:
        b = lay["blocks"][k]
        if b["speed"]["mode"] != "100":
            slow.append("%s (%s)" % (b["bin"], "nhiều mức" if b["speed"]["mode"] == "mixed" else "%g%%" % b["speed"]["pct"]))
        if b["mute"]:
            muted.append(b["bin"])
        if b["track"] == "V2":
            v2.append(b["bin"])
    return {"slow": slow, "muted": muted, "v2": v2, "n_v1": sum(1 for x in placements(r, plan) if x["track"] == "V1"),
            "n_v2": sum(1 for x in placements(r, plan) if x["track"] == "V2")}


def verify_readback(pl, got):
    """Kiểm kết quả ĐỌC LẠI từ DaVinci. pl = placements (đã sắp V1 trước); got = [(track, start_frame, end_frame)] cùng thứ tự V1 theo vị trí, V2..V4 theo vị trí.
    V1 phải liền nhau (trừ khi ở chế độ nhiều track máy có đánh dấu gapped); V2..V4 phải đủ số clip. Trả (ok, [lời])."""
    msgs = []
    v1 = [g for g in got if g[0] == "V1"]
    gapped = any(x.get("gapped") for x in pl)
    if not gapped:
        for a, b in zip(v1, v1[1:]):
            if b[1] != a[2]:
                msgs.append("V1: clip kết thúc ở %d nhưng clip kế bắt đầu ở %d (%s)." % (a[2], b[1], "chồng" if b[1] < a[2] else "hở"))
    for tr in ("V1", "V2", "V3", "V4"):
        if tr == "V1" and not gapped:
            continue
        gtr = [g for g in got if g[0] == tr]
        ptr = [x for x in pl if x["track"] == tr]
        if len(gtr) != len(ptr):
            msgs.append("%s: có %d clip, cần %d." % (tr, len(gtr), len(ptr)))
    return (not msgs), msgs


# ------------------------------------------------------------------ thao tác (sửa plan["durations"]["tl"])
def _tl(plan):
    return plan.setdefault("durations", {}).setdefault("tl", {})


def _clean(plan):
    d = plan.get("durations") or {}
    t = d.get("tl")
    if isinstance(t, dict):
        for k in ("blk", "stg", "kids"):
            if k in t and not t[k]:
                t.pop(k)
        if not t:
            d.pop("tl", None)


def _split(key):
    stage, _sep, b = key.partition("|")
    return stage, b


def _freeze(r, plan):
    """Ghi thứ tự đang hiện thành cấu hình tường minh (để dời một khối không làm các khối khác nhảy chỗ)."""
    lay = layout(r, plan)
    t = _tl(plan)
    t["order"] = list(lay["order"])
    t["kids"] = {c["stage"]: list(c["kids"]) for c in lay["clusters"]}
    return lay


def move_cluster(plan, r, stage, to_index):
    lay = layout(r, plan)
    if stage not in lay["order"]:
        return "Không có cụm “%s”." % stage
    order = [x for x in lay["order"] if x != stage]
    to_index = max(0, min(len(order), int(to_index)))
    order.insert(to_index, stage)
    _freeze(r, plan)
    t = _tl(plan)
    t["order"] = order
    t["manual"] = True
    return None


def move_block(plan, r, key, to_cluster, to_index):
    """Kéo khối con: đổi thứ tự trong cụm hoặc sang cụm khác (vẫn là bin của giai đoạn gốc, chỉ đổi chỗ trên timeline). Khối về V1."""
    lay = layout(r, plan)
    if key not in lay["blocks"]:
        return "Không có khối “%s”." % key
    if to_cluster not in lay["order"]:
        return "Không có cụm “%s”." % to_cluster
    _freeze(r, plan)
    t = _tl(plan)
    for cl in t["kids"]:
        if key in t["kids"][cl]:
            t["kids"][cl].remove(key)
    lst = t["kids"].setdefault(to_cluster, [])
    # vị trí chèn tính theo các khối V1 của cụm đích (khối V2 không chiếm chỗ trên V1)
    v1 = [k for k in lst if lay["blocks"].get(k, {}).get("track") == "V1" and k != key]
    to_index = max(0, min(len(v1), int(to_index)))
    pos = lst.index(v1[to_index]) if to_index < len(v1) else len(lst)
    lst.insert(pos, key)
    stage, b = _split(key)
    blk = t.setdefault("blk", {}).setdefault(stage, {}).setdefault(b, {})
    blk.pop("track", None)
    blk.pop("at", None)
    blk["manual"] = True
    t["manual"] = True
    return None


def set_track(plan, r, key, track, at=None):
    lay = layout(r, plan)
    if key not in lay["blocks"]:
        return "Không có khối “%s”." % key
    if track not in ("V1", "V2"):
        return "Track chỉ là V1 hoặc V2."
    t = _tl(plan)
    stage, b = _split(key)
    blk = t.setdefault("blk", {}).setdefault(stage, {}).setdefault(b, {})
    if track == "V2":
        if at is not None and not (td._num(at) and 0 <= at <= 24 * 3600):
            return "Vị trí thả không hợp lệ."
        blk["track"] = "V2"
        if at is not None:
            blk["at"] = round(float(at), 2)
        else:
            blk.pop("at", None)
    else:
        blk.pop("track", None)
        blk.pop("at", None)
    blk["manual"] = True
    t["manual"] = True
    return None


def _speed_ok(spec):
    if spec is None or spec == "auto":
        return True
    return td._num(spec) and SPEED_LIMITS[0] <= spec <= SPEED_LIMITS[1]


def set_speed(plan, kind, name, spec):
    """kind 'stage' (cụm mẹ: áp mọi khối con chưa đặt riêng) hoặc 'block' (khối con: đặt riêng, THẮNG mẹ). spec: 100 | 'auto' | số | None (bỏ đặt riêng)."""
    if not _speed_ok(spec):
        return "Tốc độ từ %g%% đến %g%% (hoặc “Slow mượt tự tính”)." % SPEED_LIMITS
    t = _tl(plan)
    if kind == "stage":
        t.setdefault("stg", {}).setdefault(name, {})
        d = t["stg"][name]
    else:
        stage, b = _split(name)
        d = t.setdefault("blk", {}).setdefault(stage, {}).setdefault(b, {})
    if spec is None:
        d.pop("speed", None)
    else:
        d["speed"] = "auto" if spec == "auto" else float(spec)
    return None


def set_mute(plan, kind, name, mute):
    t = _tl(plan)
    if kind == "stage":
        d = t.setdefault("stg", {}).setdefault(name, {})
    else:
        stage, b = _split(name)
        d = t.setdefault("blk", {}).setdefault(stage, {}).setdefault(b, {})
    if mute is None:
        d.pop("mute", None)
    else:
        d["mute"] = bool(mute)
    return None


def reset_order(plan):
    """"Xếp lại theo giờ quay": bỏ thứ tự cụm/khối, track V2 và vị trí đã xếp tay. Giữ tốc độ và tiếng (đó là lựa chọn khác)."""
    t = _tl(plan)
    for k in ("order", "kids", "manual"):
        t.pop(k, None)
    for stage, bins in list((t.get("blk") or {}).items()):
        for b, d in list(bins.items()):
            for k in ("track", "at", "manual"):
                d.pop(k, None)
            if not d:
                bins.pop(b)
        if not bins:
            t["blk"].pop(stage)
    _clean(plan)
    return None


def is_manual(plan):
    return bool(td.tl_cfg(plan).get("manual"))


def tidy(plan):
    """Dọn khóa rỗng sau khi sửa."""
    t = td.tl_cfg(plan)
    for stage, bins in list((t.get("blk") or {}).items()):
        for b, d in list(bins.items()):
            if not d:
                bins.pop(b)
        if not bins:
            t["blk"].pop(stage)
    for stage, d in list((t.get("stg") or {}).items()):
        if not d:
            t["stg"].pop(stage)
    _clean(plan)
