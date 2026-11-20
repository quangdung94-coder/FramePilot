"""
hoc_tu_cu_phan_tich.py - Phần PHÂN TÍCH thuần (không gọi DaVinci, không đọc video) của tool học từ project cũ.
Vào: dump (từ DaVinci) + mẫu thưa (âm thanh/khung nhỏ). Ra: dict số liệu. Không có tên khách/clip trong kết quả.
"""
import datetime
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import troly_core as tc               # noqa: E402

SAFE_TL = ("full", "intro", "sameday", "highlight", "teaser")


def q(v, p):
    s = sorted(v)
    if not s:
        return None
    k = (len(s) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 2)


def dist(v):
    return {"n": len(v), "p10": q(v, .1), "p25": q(v, .25), "med": q(v, .5), "p75": q(v, .75), "p90": q(v, .9)}


def clip_dur(c):
    try:
        return float(c["props"]["Frames"]) / float(c["props"]["FPS"])
    except (TypeError, ValueError, ZeroDivisionError, KeyError):
        return None


def tl_label(i, name):
    n = (name or "").strip().lower()
    return n if n in SAFE_TL else "T%d" % (i + 1)


def pick_main(dump, forced=None):
    """Timeline chính: tên chỉ định trong cấu hình local, không thì timeline có nhiều clip khác nhau nhất."""
    tls = dump["timelines"]
    if forced:
        for i, t in enumerate(tls):
            if t["name"] == forced:
                return i
    best, bi = -1, 0
    for i, t in enumerate(tls):
        n = len({it["uid"] for it in t["items"]})
        if n > best:
            best, bi = n, i
    return bi


def segments(dump, ti):
    """Đoạn nguồn thật của timeline ti: [{uid, dur, a, b, tl_s, cam}] (bỏ đổi tốc độ), a/b tính giây từ đầu file."""
    by = {c["uid"]: c for c in dump["clips"]}
    t = dump["timelines"][ti]
    tlfps = float(t.get("fps") or 25)
    t0 = t.get("start_frame") or 0
    out = []
    for it in t["items"]:
        c = by.get(it["uid"])
        d = clip_dur(c) if c else None
        if not d:
            continue
        fps = float(c["props"]["FPS"])
        span = (it["src_end_f"] - it["src_start_f"]) / fps
        tls = it["dur"] / tlfps
        if tls <= 0 or not 0.9 <= span / tls <= 1.1:
            continue
        out.append({"uid": c["uid"], "dur": d, "a": it["src_start_f"] / fps, "b": min(it["src_end_f"] / fps, d),
                    "tl_s": (it["start"] - t0) / tlfps, "track": it["track"], "cam": tc.camera_key(c["props"])})
    return out


def shoot(c):
    dt, _ = tc.shoot_time(c["props"])
    return dt


# ---------------------------------------------------------------- (a) In/Out
def inout_stats(dump, samples, ti):
    segs = segments(dump, ti)
    seen, rows = set(), []
    for s in segs:
        k = (s["uid"], round(s["a"], 1), round(s["b"], 1))
        if k not in seen:
            seen.add(k)
            rows.append(s)
    if not rows:
        return {"n": 0}
    keep = [r["b"] - r["a"] for r in rows]
    head = [r["a"] for r in rows]
    tail = [r["dur"] - r["b"] for r in rows]
    ratio = [(r["b"] - r["a"]) / r["dur"] for r in rows]
    edges = [0, 10, 30, 120, 1e9]
    buckets = {}
    for lo, hi in zip(edges, edges[1:]):
        sub = [r for r in rows if lo <= r["dur"] < hi]
        if sub:
            buckets["%d-%s s" % (lo, "∞" if hi > 1e8 else hi)] = {
                "n": len(sub), "keep_med": q([r["b"] - r["a"] for r in sub], .5),
                "head_med": q([r["a"] for r in sub], .5), "tail_med": q([r["dur"] - r["b"] for r in sub], .5),
                "ty_le_giu_med": q([(r["b"] - r["a"]) / r["dur"] for r in sub], .5)}
    per_clip = {}
    for r in rows:
        per_clip[r["uid"]] = per_clip.get(r["uid"], 0) + 1
    res = {"n": len(rows), "keep": dist(keep), "head": dist(head), "tail": dist(tail), "ty_le_giu": dist(ratio),
           "gan_tron_clip_pct": round(100.0 * sum(1 for x in ratio if x >= 0.9) / len(ratio)),
           "bo_dau_pct": round(100.0 * sum(1 for x in head if x > 0.5) / len(head)),
           "theo_do_dai": buckets,
           "clip_dung_nhieu_doan_pct": round(100.0 * sum(1 for v in per_clip.values() if v > 1) / len(per_clip))}
    res["am_thanh"] = audio_in_out(rows, samples)
    return res


def audio_in_out(rows, samples):
    """Cửa sổ mẫu nằm trong đoạn giữ vs đoạn bỏ của CÙNG clip. voice = tỉ lệ năng lượng dải giọng nói (300-3400Hz),
    dyn = độ nhấp nhô âm lượng (lời nói nhấp nhô hơn nhạc/ồn đều). Chỉ là chỉ báo, chưa phải nhận diện lời nói."""
    segs = {}
    for r in rows:
        segs.setdefault(r["uid"], []).append((r["a"], r["b"]))
    d_rms, d_voice, d_dyn, n_clip = [], [], [], 0
    thanh = {"giu": 0, "bo": 0}
    for uid, ws in samples.items():
        if uid not in segs:
            continue
        inn, out = [], []
        for w in ws:
            (inn if any(a <= w["t"] <= b for a, b in segs[uid]) else out).append(w)
        thanh["giu"] += len(inn)
        thanh["bo"] += len(out)
        if inn and out:
            n_clip += 1
            for key, dst in (("rms", d_rms), ("voice", d_voice), ("dyn", d_dyn)):
                a = [w[key] for w in inn if w.get(key) is not None]
                b = [w[key] for w in out if w.get(key) is not None]
                if a and b:
                    dst.append(statistics.mean(a) - statistics.mean(b))
    return {"clip_co_ca_giu_va_bo": n_clip, "cua_so": thanh, "giu_hon_bo_rms_db": dist(d_rms),
            "giu_hon_bo_voice": dist(d_voice), "giu_hon_bo_dyn": dist(d_dyn)}


# ---------------------------------------------------------------- (b) sao
def star_stats(dump, samples, ti):
    used = {s["uid"] for s in segments(dump, ti)}
    clips = [c for c in dump["clips"] if clip_dur(c)]
    if not clips:
        return {"n": 0}
    durs = sorted(clip_dur(c) for c in clips)
    cuts = [q(durs, .25), q(durs, .5), q(durs, .75)]

    def bk(d):
        return sum(1 for x in cuts if d > x)
    names = ["ngắn nhất 25%", "25-50%", "50-75%", "dài nhất 25%"]
    by_dur = {}
    for c in clips:
        b = names[bk(clip_dur(c))]
        t = by_dur.setdefault(b, [0, 0])
        t[0] += 1
        t[1] += c["uid"] in used
    by_hour, by_cam = {}, {}
    for c in clips:
        dt = shoot(c)
        if dt:
            t = by_hour.setdefault(dt.hour, [0, 0])
            t[0] += 1
            t[1] += c["uid"] in used
        t = by_cam.setdefault(tc.camera_key(c["props"]), [0, 0])
        t[0] += 1
        t[1] += c["uid"] in used
    feat = {}
    for key in ("rms", "voice", "dyn", "bright"):
        u = [statistics.mean(w[key] for w in ws if w.get(key) is not None) for uid, ws in samples.items()
             if uid in used and any(w.get(key) is not None for w in ws)]
        n = [statistics.mean(w[key] for w in ws if w.get(key) is not None) for uid, ws in samples.items()
             if uid not in used and any(w.get(key) is not None for w in ws)]
        feat[key] = {"duoc_dung_med": q(u, .5), "khong_dung_med": q(n, .5)}
    cams = {}
    for i, (k, v) in enumerate(sorted(by_cam.items())):
        cams["cam%d" % (i + 1)] = {"clip": v[0], "dung_pct": round(100.0 * v[1] / v[0])}
    return {"n_clip": len(clips), "n_dung": len(used), "dung_pct": round(100.0 * len(used) / len(clips)),
            "theo_do_dai": {k: {"clip": v[0], "dung_pct": round(100.0 * v[1] / v[0])} for k, v in by_dur.items()},
            "theo_gio": {str(h): {"clip": v[0], "dung_pct": round(100.0 * v[1] / v[0])} for h, v in sorted(by_hour.items())},
            "theo_may": cams, "dac_trung": feat}


# ---------------------------------------------------------------- lệch giờ giữa các máy
def cam_offsets(dump):
    """Lệch đồng hồ giữa máy: trong timeline đã sync, hai clip khác máy chồng nhau cùng một khoảnh khắc thật.
    offset(B so với A) = giờ_thật_B(điểm chung) - giờ_thật_A(điểm chung); trung vị + độ phân tán (MAD)."""
    by = {c["uid"]: c for c in dump["clips"]}
    diffs = {}
    for t in dump["timelines"]:
        fps = float(t.get("fps") or 25)
        items = []
        for it in t["items"]:
            c = by.get(it["uid"])
            if not c:
                continue
            st = shoot(c)
            cf = float(c["props"].get("FPS") or 0)
            if not st or cf <= 0:
                continue
            items.append((it["start"] / fps, it["end"] / fps, tc.camera_key(c["props"]),
                          st.timestamp() + it["src_start_f"] / cf, it["start"] / fps))
        items.sort()
        for i, a in enumerate(items):
            for b in items[i + 1:i + 40]:
                if b[0] >= a[1]:
                    break
                if a[2] == b[2]:
                    continue
                mid = max(a[0], b[0])
                real_a = a[3] + (mid - a[4])
                real_b = b[3] + (mid - b[4])
                diffs.setdefault((a[2], b[2]), []).append(real_b - real_a)
    out = {}
    for (ca, cb), v in diffs.items():
        if len(v) < 3:
            continue
        m = statistics.median(v)
        mad = statistics.median(abs(x - m) for x in v)
        out[(ca, cb)] = {"n": len(v), "offset_s": round(m, 1), "mad_s": round(mad, 1),
                         "trong_5s_pct": round(100.0 * sum(1 for x in v if abs(x - m) <= 5) / len(v))}
    return out


def offset_for_cams(offs):
    """Đưa mọi máy về đồng hồ máy đầu tiên (chỉ dùng cặp tin cậy: n>=5, MAD<=3s)."""
    res = {}
    for (ca, cb), o in sorted(offs.items(), key=lambda kv: -kv[1]["n"]):
        if o["n"] >= 5 and o["mad_s"] <= 3:
            if ca in res and cb not in res:
                res[cb] = res[ca] - o["offset_s"]
            elif cb in res and ca not in res:
                res[ca] = res[cb] + o["offset_s"]
            elif ca not in res and cb not in res and not res:
                res[ca] = 0.0
                res[cb] = -o["offset_s"]
    return res


# ---------------------------------------------------------------- (c) điểm chuyển
def timeline_jumps(dump, ti, off):
    """Hai clip liền nhau trên timeline mà giờ quay thật nhảy xa = người dựng chuyển sự kiện."""
    by = {c["uid"]: c for c in dump["clips"]}
    t = dump["timelines"][ti]
    fps = float(t.get("fps") or 25)
    t0 = t.get("start_frame") or 0
    seq = []
    for it in sorted(t["items"], key=lambda x: (x["start"], x["track"])):
        c = by.get(it["uid"])
        st = shoot(c) if c else None
        cf = float((c or {"props": {}})["props"].get("FPS") or 0)
        if not st or cf <= 0:
            continue
        real = st.timestamp() + it["src_start_f"] / cf + off.get(tc.camera_key(c["props"]), 0.0)
        seq.append(((it["start"] - t0) / fps, real, it["uid"]))
    seq2 = []                                                       # bỏ clip chồng nhau (nhiều máy cùng lúc): giữ clip đầu mỗi mốc
    for s in seq:
        if not seq2 or s[0] - seq2[-1][0] > 0.5:
            seq2.append(s)
    jumps = [(seq2[i][0], seq2[i][1] - seq2[i - 1][1]) for i in range(1, len(seq2))]
    if not jumps:
        return {"n": 0}
    back = sum(1 for _, d in jumps if d < -1)
    absd = [abs(d) for _, d in jumps]
    thr = max(q(absd, .9) or 0, 60.0)
    big = [(p, d) for p, d in jumps if abs(d) >= thr]
    return {"n_clip_lien_nhau": len(seq2), "nguoc_thoi_gian_pct": round(100.0 * back / len(jumps)),
            "nhay_thoi_gian": dist([a / 60 for a in absd]), "nguong_nhay_s": round(thr),
            "diem_chuyen": [{"tl_pos": fmt(p), "nhay_phut": round(d / 60, 1)} for p, d in big[:30]]}


def fmt(sec):
    sec = int(sec)
    return "%02d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60)


def desc(ws):
    keys = ("bright", "sat", "sky", "rms", "voice")
    v = []
    for k in keys:
        xs = [w[k] for w in ws if w.get(k) is not None]
        v.append(statistics.mean(xs) if xs else None)
    return v


def real_transitions(dump, samples, off, ti):
    """Ứng viên điểm chuyển từ dữ liệu quay: (1) khoảng trống giờ quay, (2) đổi cảnh/âm thanh giữa các cụm clip."""
    ev = []
    for c in dump["clips"]:
        st, d = shoot(c), clip_dur(c)
        if st and d:
            s = st.timestamp() + off.get(tc.camera_key(c["props"]), 0.0)
            ev.append((s, s + d, c["uid"]))
    if len(ev) < 10:
        return {"n_clip": len(ev)}
    ev.sort()
    day0 = ev[0][0]
    cov, cur_s, cur_e = [], ev[0][0], ev[0][1]
    for s, e, _ in ev[1:]:
        if s > cur_e:
            cov.append((cur_s, cur_e))
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    cov.append((cur_s, cur_e))
    gaps = [(cov[i][1], cov[i + 1][0] - cov[i][1]) for i in range(len(cov) - 1)]
    thr = max(q([g for _, g in gaps], .9) or 0, 120.0) if gaps else 0
    big = [(t, g) for t, g in gaps if g >= thr]
    # đổi cảnh/âm thanh
    vec = [desc(samples.get(u, [])) for _, _, u in ev]
    cols = list(range(5))
    sd = []
    for k in cols:
        xs = [v[k] for v in vec if v[k] is not None]
        sd.append(statistics.pstdev(xs) if len(xs) > 2 and statistics.pstdev(xs) > 1e-9 else 1.0)
    K = 5
    score = []
    for i in range(K, len(ev) - K + 1):
        dd = 0.0
        for k in cols:
            a = [v[k] for v in vec[i - K:i] if v[k] is not None]
            b = [v[k] for v in vec[i:i + K] if v[k] is not None]
            if a and b:
                dd += ((statistics.mean(a) - statistics.mean(b)) / sd[k]) ** 2
        score.append((i, math.sqrt(dd)))
    sc = [s for _, s in score]
    peaks = []
    if len(sc) > 4:
        thr_s = statistics.mean(sc) + 2 * statistics.pstdev(sc)
        for j in range(1, len(score) - 1):
            if score[j][1] >= thr_s and score[j][1] >= score[j - 1][1] and score[j][1] >= score[j + 1][1]:
                peaks.append((ev[score[j][0]][0], round(score[j][1], 2)))
    # vị trí trên timeline của clip đầu tiên sau mỗi ứng viên
    segs = {s["uid"]: s["tl_s"] for s in segments(dump, ti)}
    nxt = {}
    for s, e, u in ev:
        if u in segs:
            nxt[s] = segs[u]
    keys = sorted(nxt)

    def tl_after(t):
        for k in keys:
            if k >= t:
                return fmt(nxt[k])
        return None
    mk = lambda t: datetime.datetime.fromtimestamp(t).strftime("%H:%M")      # noqa: E731
    return {"n_clip": len(ev), "so_doan_lien_tuc": len(cov), "nguong_trong_s": round(thr),
            "khoang_trong": [{"gio": mk(t), "dai_phut": round(g / 60, 1), "tl_pos_sau": tl_after(t + g)} for t, g in big[:30]],
            "doi_canh_am": [{"gio": mk(t), "diem": sc_, "tl_pos_sau": tl_after(t)} for t, sc_ in peaks[:30]]}


def marker_info(dump):
    out = []
    for i, t in enumerate(dump["timelines"]):
        fps = float(t.get("fps") or 25)
        t0 = t.get("start_frame") or 0
        out.append({"tl": tl_label(i, t["name"]), "n_item": len(t["items"]), "n_clip": len({it["uid"] for it in t["items"]}),
                    "n_marker": len(t.get("markers") or []),
                    "marker_pos": [fmt((m["frame"] - 0) / fps) for m in (t.get("markers") or [])][:40],
                    "n_khong_phai_clip": len(t.get("others") or []),
                    "dai_s": round(max([it["end"] for it in t["items"]] + [t0]) / fps - t0 / fps)})
    return out


def analyse(dump, samples, main_name=None):
    ti = pick_main(dump, main_name)
    offs = cam_offsets(dump)
    off = offset_for_cams(offs)
    return {"tong_quan": {"n_clip": len(dump["clips"]), "n_online": sum(1 for c in dump["clips"] if c.get("online")),
                          "n_clip_co_mau": len(samples), "timeline": marker_info(dump), "timeline_chinh": ti + 1,
                          "may": sorted({tc.camera_key(c["props"]) for c in dump["clips"]}).__len__()},
            "lech_gio_may": [{"cap": "may%d-may%d" % (i + 1, i + 2), **v} for i, v in enumerate(offs.values())],
            "in_out": inout_stats(dump, samples, ti), "sao": star_stats(dump, samples, ti),
            "tren_timeline": timeline_jumps(dump, ti, off), "tu_du_lieu_quay": real_transitions(dump, samples, off, ti)}
