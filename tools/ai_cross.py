"""
ai_cross.py - Đo độ tốt của gợi ý AI trong panel (ADR-0022) và ĐỀ XUẤT bảng ghép tên bin giữa các project. Chỉ ĐỌC kế hoạch + vector; chỉ ghi
<data_root>\troly\ai_suggest\cross_report.json và bin_name_map_proposal.json (số + tên bin, không tên khách). KHÔNG tự áp bảng ghép.

Phép đo trên mỗi project có ≥ 20 nhãn tay:
  loo        : bỏ từng clip ra, học từ các clip còn lại (lạc quan vì clip liền kề giống nhau)
  chia_gio   : học từ 60% clip quay SỚM, đoán 40% clip quay MUỘN (sát thực tế hơn)
  mo_ta      : chỉ theo mô tả (không dùng nhãn)
  Tất cả đều chỉ xét các bin thuộc giai đoạn clip đang ở. Đo chéo project (học project này, đoán project kia) chỉ làm khi ≥ 2 project đủ nhãn.
"""
import argparse
import json
import os
import sys

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APP)
import troly_ai as ai      # noqa: E402
import troly_core as tc    # noqa: E402


def labeled_rows(plan, vectors):
    st = {s["name"]: s["bins"] for s in plan.get("stages", [])}
    rows = []
    for rel, v in (plan.get("labels") or {}).items():
        k = ai.ck(rel)
        if isinstance(v, dict) and v.get("bin") and v.get("by") != "ai_auto" and k in vectors and v.get("stage") in st:
            rows.append({"k": k, "bin": v["bin"], "cand": st[v["stage"]], "t": v.get("t") or ""})
    return rows


def score(rows, vectors, train_of, desc, use_labels=True):
    ok1 = ok3 = n = 0
    for r in rows:
        train = train_of(r) if use_labels else {}
        src, top = ai.rank_for_clip(r["k"], r["cand"], vectors, train, desc)
        if not top:
            continue
        n += 1
        ok1 += top[0]["bin"] == r["bin"]
        ok3 += r["bin"] in [t["bin"] for t in top]
    return {"n": n, "top1": round(ok1 / n, 3) if n else None, "top3": round(ok3 / n, 3) if n else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=r"D:\VideoAI\data")
    a = ap.parse_args()
    pdir = os.path.join(a.data_root, "troly", "projects")
    names = sorted(f[:-5] for f in os.listdir(pdir) if f.endswith(".json"))
    report, all_bins, per_project = {}, {}, {}
    for i, name in enumerate(names):
        plan = tc.load_plan(a.data_root, name)
        tag = "P%d" % (i + 1)
        bins = ai.plan_bins(plan)
        all_bins[tag] = bins
        V = ai.load_vectors(a.data_root, name)
        desc = ai.load_suggest(a.data_root, name)
        rows = labeled_rows(plan, V)
        info = {"labels": len(plan.get("labels") or {}), "labels_with_vector": len(rows), "bins": len(bins)}
        if len(rows) >= ai.MIN_FEWSHOT_LABELS:
            lab = {r["k"]: r["bin"] for r in rows}
            info["loo"] = score(rows, V, lambda r: {k: b for k, b in lab.items() if k != r["k"]}, desc)
            info["mo_ta"] = score(rows, V, None, desc, use_labels=False)
            srt = sorted(rows, key=lambda r: r["t"])
            cut = int(len(srt) * 0.6)
            early = {r["k"]: r["bin"] for r in srt[:cut]}
            info["chia_gio"] = score(srt[cut:], V, lambda r: early, desc)
            info["chia_gio"]["train"] = cut
            per_project[tag] = (V, rows)
        else:
            info["note"] = "chưa đủ nhãn để đo"
        report[tag] = info
    tags = list(per_project)
    if len(tags) >= 2:                                           # học project này, đoán project kia (dùng chung tên bin NẾU trùng chữ)
        cross = {}
        for src in tags:
            for dst in tags:
                if src == dst:
                    continue
                Vs, rs = per_project[src]
                Vd, rd = per_project[dst]
                lab = {r["k"]: r["bin"] for r in rs}
                allv = dict(Vs)
                allv.update(Vd)
                cross["%s->%s" % (src, dst)] = score(rd, allv, lambda r: lab, None)
        report["cheo_project"] = cross
    else:
        report["cheo_project"] = "chưa đo được: chỉ %d project đủ nhãn tay (cần ≥ 2)" % len(tags)
    # Đề xuất bảng ghép tên bin (KHÔNG tự áp): gom tên bin giống nhau (bỏ dấu, thường hóa) giữa các project
    import unicodedata

    def fold(s):
        return "".join(c for c in unicodedata.normalize("NFD", s.casefold()) if unicodedata.category(c) != "Mn").replace("đ", "d").strip()
    groups = {}
    for tag, bins in all_bins.items():
        for b in bins:
            groups.setdefault(fold(b), {}).setdefault(b, []).append(tag)
    proposal = {"ghi_chu": "ĐỀ XUẤT, chưa áp. Tên bin viết khác nhau nhưng cùng nghĩa cần anh duyệt trước khi gộp để học chung giữa project.",
                "nhom_trung_chu": [{"ten": list(v)[0], "cac_ten": sorted(v), "project": sorted({t for ts in v.values() for t in ts})} for v in groups.values()]}
    with open(os.path.join(a.data_root, "troly", "ai_suggest", "cross_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open(os.path.join(a.data_root, "troly", "ai_suggest", "bin_name_map_proposal.json"), "w", encoding="utf-8") as f:
        json.dump(proposal, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
