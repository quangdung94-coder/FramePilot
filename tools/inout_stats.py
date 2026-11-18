"""
inout_stats.py - Thống kê In/Out thật (ADR-0021) từ file dump của tools/inout_dump.py. Kết quả CHỈ LÀ SỐ (không tên khách/clip/lời nói).
  python tools/inout_stats.py --dump P1=<json> --dump P2=<json> [--embed P2=<vectors.npz>] --out <thư mục>
Mẫu = đoạn nguồn thật đã dùng trên timeline thành phẩm (full/intro/sameday, tốc độ ~1, bỏ trùng) và In/Out đặt trong Media Pool.
"""
import argparse
import csv
import json
import math
import os
import re
import statistics
import sys

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APP)
import troly_core as tc               # noqa: E402

FINAL_TL = ("full", "intro", "sameday")
TL_FPS_DEFAULT = 25.0

# Bảng ghép tên bin (để người dựng duyệt): bỏ số thứ tự đầu, gom tên giống nhau.
NAME_MAP = (
    (("nghi lễ",), "Nghi lễ"), (("cô dâu chú rể",), "Cô dâu chú rể"), (("beauty",), "Beauty cô dâu"),
    (("gia đình",), "Gia đình"), (("decor",), "Decor"), (("phỏng vấn",), "Phỏng vấn"), (("khách",), "Khách"),
    (("nhà trai đến",), "Nhà trai đến"), (("chào bàn",), "Chào bàn"), (("khác",), "Khác"),
)


def canon(bin_path):
    """'Master/01_footage/04_Đón dâu về nhà trai/Nghi lễ' -> 'Nghi lễ'; bin không thuộc bảng ghép -> None."""
    parts = [re.sub(r"^\d+[_ ]*", "", p).strip() for p in bin_path.split("/")]
    last = parts[-1].casefold()
    for keys, name in NAME_MAP:
        if any(k in last for k in keys):
            return name
    return None


def clip_dur(c):
    try:
        return float(c["frames"]) / float(c["fps"])
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def samples(d):
    by = {c["uid"]: c for c in d["clips"]}
    out, seen = [], set()
    for t in d["timelines"]:
        if t["name"].strip().lower() not in FINAL_TL:
            continue
        tlfps = float(t.get("fps") or TL_FPS_DEFAULT)
        for it in t["items"]:
            c = by.get(it["uid"])
            if not c:
                continue
            dur = clip_dur(c)
            if not dur:
                continue
            fps = float(c["fps"])
            span = (it["src_end_f"] - it["src_start_f"]) / fps
            tls = it["dur"] / tlfps
            if tls <= 0 or not 0.9 <= span / tls <= 1.1:            # đổi tốc độ (slow-mo...) thì bỏ
                continue
            a, b = it["src_start_f"] / fps, it["src_end_f"] / fps
            key = (c["uid"], round(a, 1), round(b, 1))
            if key in seen:
                continue
            seen.add(key)
            out.append({"src": "timeline", "uid": c["uid"], "bin": c["bin"], "dur": dur, "in": a, "out": min(b, dur), "tl": t["name"]})
    marks = []
    for c in d["clips"]:
        if c["mark"]:
            dur = clip_dur(c)
            if dur:
                fps = float(c["fps"])
                marks.append({"src": "mark", "uid": c["uid"], "bin": c["bin"], "dur": dur, "in": c["mark"][0] / fps,
                              "out": min(c["mark"][1] / fps, dur), "tl": ""})
    return out, marks


def q(v, p):
    s = sorted(v)
    if not s:
        return None
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def summarize(rows):
    L = [r["out"] - r["in"] for r in rows]
    H = [r["in"] for r in rows]
    T = [r["dur"] - r["out"] for r in rows]
    D = [r["dur"] for r in rows]
    full = sum(1 for r in rows if (r["out"] - r["in"]) >= 0.9 * r["dur"])

    def f(v, p):
        return None if not v else round(q(v, p), 2)
    return {"n": len(rows), "dur_med": f(D, .5), "keep_p25": f(L, .25), "keep_med": f(L, .5), "keep_p75": f(L, .75),
            "head_p25": f(H, .25), "head_med": f(H, .5), "head_p75": f(H, .75),
            "tail_p25": f(T, .25), "tail_med": f(T, .5), "tail_p75": f(T, .75),
            "gan_tron_clip_pct": round(100.0 * full / len(rows)) if rows else None}


def vs_rule(rows, label):
    """So từng mẫu với gợi ý hiện có của bảng quy tắc (số mặc định, chưa sửa)."""
    n = hit_in = hit_out = 0
    iou, lech = [], []
    for r in rows:
        s = tc.suggest_inout(r["dur"], label)
        if not s:
            continue
        n += 1
        hit_in += abs(s["in_s"] - r["in"]) <= 0.5
        hit_out += abs(s["out_s"] - r["out"]) <= 0.5
        inter = max(0.0, min(s["out_s"], r["out"]) - max(s["in_s"], r["in"]))
        uni = (s["out_s"] - s["in_s"]) + (r["out"] - r["in"]) - inter
        iou.append(inter / uni if uni > 0 else 0)
        lech.append((r["out"] - r["in"]) - s["dur"])                 # + : anh giữ dài hơn gợi ý
    d = max(n, 1)
    return {"n": n, "rule": tc.rule_for(label)[0], "in_trung_pct": round(100.0 * hit_in / d), "out_trung_pct": round(100.0 * hit_out / d),
            "iou_med": round(statistics.median(iou), 2) if iou else None,
            "keep_lech_med_s": round(statistics.median(lech), 2) if lech else None}


def propose(sm):
    """Giá trị ĐỀ XUẤT (không tự áp): giữ tối thiểu = phân vị 25, tối đa = phân vị 75, làm tròn 0,5s; trọn câu nếu thường giữ ≥ 80% clip."""
    if not sm["n"] or sm["n"] < 8:
        return None
    r5 = lambda x: max(0.5, math.floor(x * 2 + 0.5) / 2.0)                    # noqa: E731
    return {"min": r5(sm["keep_p25"]), "max": r5(sm["keep_p75"]), "whole": sm["gan_tron_clip_pct"] >= 80,
            "vao_med": sm["head_med"], "ra_cach_duoi_med": sm["tail_med"]}


def knn_check(rows, labs, vec):
    """Clip giống nhau về hình có cách cắt giống nhau không? Sai số tuyệt đối trung bình (giây) khi đoán độ dài giữ / điểm vào, leave-one-out:
    chung = trung vị cả project; cung_bin = trung vị cùng bin; knn5 = trung vị 5 clip giống nhất về hình."""
    import numpy as np
    X, L, H, B = [], [], [], []
    for r, lab in zip(rows, labs):
        v = vec.get(r["uid"])
        if v is not None:
            X.append(v)
            L.append(r["out"] - r["in"])
            H.append(r["in"])
            B.append(lab)
    if len(X) < 30:
        return {"n": len(X), "note": "quá ít mẫu có vector"}
    X = np.array(X)
    S = X @ X.T
    np.fill_diagonal(S, -9)
    res = {"n": len(X)}
    for name, arr in (("keep", np.array(L)), ("head", np.array(H))):
        e = {"chung": [], "cung_bin": [], "knn5": []}
        for i in range(len(X)):
            others = np.arange(len(X)) != i
            e["chung"].append(abs(arr[i] - np.median(arr[others])))
            same = [j for j in range(len(X)) if j != i and B[j] == B[i]]
            e["cung_bin"].append(abs(arr[i] - np.median(arr[same])) if len(same) >= 3 else abs(arr[i] - np.median(arr[others])))
            nn = np.argsort(-S[i])[:5]
            e["knn5"].append(abs(arr[i] - np.median(arr[nn])))
        res[name] = {k: round(float(np.mean(v)), 2) for k, v in e.items()}
    return res


def write_html(report, out):
    """Trang HTML tĩnh chỉ có SỐ (không tên khách/clip)."""
    import html as H
    parts = ["<!doctype html><html lang='vi'><head><meta charset='utf-8'><title>Thống kê In/Out thật (chỉ số)</title>"
             "<style>body{font:14px Segoe UI,Arial;background:#14161a;color:#e6e6e6;margin:20px}table{border-collapse:collapse;margin:8px 0 22px}"
             "td,th{border:1px solid #333;padding:3px 8px;text-align:right}td:first-child,th:first-child{text-align:left}h2{font-size:16px}.n{color:#9aa;max-width:900px}</style></head><body>",
             "<h1>Thống kê In/Out thật từ project đã dựng</h1><p class='n'>Đơn vị: giây. 'Giữ' = độ dài đoạn anh dùng; 'Vào' = điểm vào cách đầu clip; 'Đuôi' = điểm ra cách đuôi clip. "
             "p25/trung vị/p75 = một phần tư dưới / giữa / một phần tư trên. Mẫu = đoạn nguồn thật trên timeline thành phẩm (tốc độ thường). Chỉ ĐỀ XUẤT, chưa áp vào panel.</p>"]
    for tag, i in report["projects"].items():
        parts.append("<h2>%s — %d clip, %d đoạn đã dùng trên timeline, %d clip có In/Out trong Media Pool</h2>" % (H.escape(tag), i["clips"], i["used_segments"], i["marks"]))
        parts.append("<table><tr><th>Bin</th><th>n</th><th>Dài clip (tv)</th><th>Giữ p25</th><th>Giữ tv</th><th>Giữ p75</th><th>Vào tv</th><th>Đuôi tv</th><th>Giữ gần trọn clip %</th></tr>")
        for g, s in i["by_bin"].items():
            parts.append("<tr><td>%s</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                H.escape(g), s["n"], s["dur_med"], s["keep_p25"], s["keep_med"], s["keep_p75"], s["head_med"], s["tail_med"], s["gan_tron_clip_pct"]))
        parts.append("</table>")
        if i["vs_rule"]:
            parts.append("<table><tr><th>Bin</th><th>n</th><th>Quy tắc hiện có</th><th>Vào trúng ±0,5s %</th><th>Ra trúng ±0,5s %</th><th>IoU tv</th><th>Giữ lệch tv (+ = anh giữ dài hơn)</th><th>Đề xuất giữ min–max</th></tr>")
            for g, v in i["vs_rule"].items():
                dx = v["de_xuat"]
                parts.append("<tr><td>%s</td><td>%d</td><td style='text-align:left'>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                    H.escape(g), v["n"], H.escape(v["rule"]), v["in_trung_pct"], v["out_trung_pct"], v["iou_med"], v["keep_lech_med_s"],
                    ("%g–%g%s" % (dx["min"], dx["max"], " (trọn câu)" if dx["whole"] else "")) if dx else "chưa đủ mẫu (n<8)"))
            parts.append("</table>")
    parts.append("<h2>Bảng ghép tên bin (để anh duyệt)</h2><table><tr><th>Tên gộp</th><th>Gồm các bin</th></tr>")
    for tag, m in report["bin_map"].items():
        for g, v in m.items():
            parts.append("<tr><td>%s: %s</td><td style='text-align:left'>%s</td></tr>" % (H.escape(tag), H.escape(g), H.escape("; ".join(v))))
    parts.append("</table><h2>Clip giống nhau về hình có cắt giống nhau không? (OpenCLIP, sai số tuyệt đối trung bình, giây)</h2><pre>%s</pre></body></html>" % H.escape(json.dumps(report["knn"], ensure_ascii=False, indent=1)))
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write("".join(parts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="append", required=True)
    ap.add_argument("--embed", action="append", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    report = {"projects": {}, "bin_map": {}, "knn": {}}
    vecs = dict(e.split("=", 1) for e in a.embed)
    rows_csv, rule_csv = [], []
    for spec in a.dump:
        tag, path = spec.split("=", 1)
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        used, marks = samples(d)
        info = {"clips": len(d["clips"]), "online": sum(1 for c in d["clips"] if c["online"]), "marks": len(marks),
                "used_segments": len(used), "timelines_used": sorted({r["tl"] for r in used}), "by_bin": {}, "by_bin_marks": {}, "vs_rule": {}}
        for nm, rows in (("by_bin", used), ("by_bin_marks", marks)):
            groups = {}
            for r in rows:
                g = canon(r["bin"]) or "(không có bin con)"
                if g != "(không có bin con)":
                    tail = "/".join(re.sub(r"^\d+[_ ]*", "", p) for p in r["bin"].split("/")[-2:])
                    report["bin_map"].setdefault(tag, {}).setdefault(g, set()).add(tail)
                groups.setdefault(g, []).append(r)
            groups["(tất cả)"] = rows
            for g, rs in sorted(groups.items()):
                sm = summarize(rs)
                info[nm][g] = sm
                rows_csv.append([tag, "timeline" if nm == "by_bin" else "mark", g] + [sm[k] for k in (
                    "n", "dur_med", "keep_p25", "keep_med", "keep_p75", "head_p25", "head_med", "head_p75", "tail_p25", "tail_med", "tail_p75",
                    "gan_tron_clip_pct")])
                if nm == "by_bin" and g not in ("(tất cả)", "(không có bin con)"):
                    vr = vs_rule(rs, g)
                    vr["de_xuat"] = propose(sm)
                    info["vs_rule"][g] = vr
                    rule_csv.append([tag, g, vr["n"], vr["rule"], vr["in_trung_pct"], vr["out_trung_pct"], vr["iou_med"], vr["keep_lech_med_s"]])
        info["vs_rule_default_all"] = vs_rule(used, None) if used else None
        report["projects"][tag] = info
        if tag in vecs:                                              # khóa vector = tên file không đuôi | thư mục cha
            import numpy as np
            by = {c["uid"]: c for c in d["clips"]}
            with np.load(vecs[tag], allow_pickle=False) as z:
                vv = {str(k): v for k, v in zip(z["keys"], z["vecs"])}
            m = {}
            for r in used:
                p = by[r["uid"]]["path"].replace("\\", "/").split("/")
                k = os.path.splitext(p[-1])[0] + "|" + p[-2]
                if k in vv:
                    m[r["uid"]] = vv[k]
            labs = [canon(r["bin"]) or "(không có bin con)" for r in used]
            report["knn"][tag] = knn_check(used, labs, m)
    report["bin_map"] = {t: {g: sorted(v) for g, v in mm.items()} for t, mm in report["bin_map"].items()}
    with open(os.path.join(a.out, "inout_stats.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    write_html(report, a.out)
    with open(os.path.join(a.out, "by_bin.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["project", "nguon", "bin", "n", "dai_clip_trung_vi_s", "giu_p25", "giu_trung_vi", "giu_p75", "vao_p25", "vao_trung_vi", "vao_p75",
                    "ra_cach_duoi_p25", "ra_cach_duoi_trung_vi", "ra_cach_duoi_p75", "giu_gan_tron_clip_pct"])
        w.writerows(rows_csv)
    with open(os.path.join(a.out, "vs_rules.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["project", "bin", "n", "quy_tac_hien_co", "vao_trung_0.5s_pct", "ra_trung_0.5s_pct", "iou_trung_vi",
                    "giu_lech_trung_vi_s (+ = anh giu dai hon)"])
        w.writerows(rule_csv)
    print(json.dumps({t: {k: v for k, v in i.items() if k in ("clips", "online", "marks", "used_segments", "timelines_used")}
                      for t, i in report["projects"].items()}, ensure_ascii=False))
    print(json.dumps(report["knn"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
