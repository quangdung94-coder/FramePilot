"""
sug_accuracy.py - Đo độ đúng của gợi ý In/Out mức 1 (quy tắc bin) so với In/Out THẬT anh đã chốt trong project cũ (ADR-0024). Chỉ ĐỌC.
Nguồn "thật" = đoạn nguồn đã dùng trên timeline thành phẩm (file dump của tools/inout_dump.py, cùng cách lấy mẫu với tools/inout_stats.py).
Mức 2 (theo lời nói) cần chữ Whisper của chính các clip đó trong kho lời nói: project cũ chưa chép lời nên KHÔNG đo được (chỉ báo, không bịa số).
Kết quả chỉ là số (không tên khách/clip): ghi ra --out.
  python tools/sug_accuracy.py --dump P1=<json> --dump P2=<json> --out <thư mục>
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)
import troly_core as tc               # noqa: E402
import inout_stats as st              # noqa: E402


def level1(rows, label_of):
    """Với mỗi mẫu: gợi ý mức 1 theo bảng quy tắc hiện có (chưa chọn kiểu quay) và độ lệch hai đầu (giây)."""
    out = {}
    for r in rows:
        lb = label_of(r)
        s = tc.suggest_inout(r["dur"], lb)
        if not s:
            continue
        d_in, d_out = abs(s["in_s"] - r["in"]), abs(s["out_s"] - r["out"])
        g = out.setdefault(lb or "(không có bin con)", [])
        g.append((d_in, d_out))
    return out


def summarize(pairs):
    n = len(pairs)
    if not n:
        return {"n": 0}
    both = lambda t: round(100.0 * sum(1 for a, b in pairs if a < t and b < t) / n)           # noqa: E731
    med = lambda v: round(sorted(v)[len(v) // 2], 2)                                         # noqa: E731
    return {"n": n, "lech_duoi_1s_pct": both(1.0), "lech_duoi_2s_pct": both(2.0), "in_duoi_1s_pct": round(100.0 * sum(1 for a, _ in pairs if a < 1.0) / n),
            "out_duoi_1s_pct": round(100.0 * sum(1 for _, b in pairs if b < 1.0) / n), "lech_vao_trung_vi_s": med([a for a, _ in pairs]), "lech_ra_trung_vi_s": med([b for _, b in pairs])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="append", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    report = {"muc_1": {}, "muc_2": "chưa đo được: project cũ chưa có chữ Whisper trong kho lời nói", "dinh_nghia": "lệch dưới T giây = CẢ điểm vào và điểm ra cùng lệch dưới T so với đoạn anh dùng thật"}
    for spec in a.dump:
        tag, path = spec.split("=", 1)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        used, _marks = st.samples(d)
        groups = level1(used, lambda r: st.canon(r["bin"]))
        allp = [p for v in groups.values() for p in v]
        report["muc_1"][tag] = {"tat_ca": summarize(allp), "theo_bin": {k: summarize(v) for k, v in sorted(groups.items())}}
    with open(os.path.join(a.out, "sug_accuracy.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
