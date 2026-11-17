"""
troly_speech_review.py - Gộp danh sách clip "có thể sai" của lượt chép lời thành file CSV + SRT để người dựng duyệt sau (mục D, 18/11/2026).

CHỈ ĐỌC kho SQLite (mở chế độ read-only, không tạo bảng, không ghi gì vào kho). Kết quả ghi vào thư mục dữ liệu
(<data_root>\\troly\\review\\), KHÔNG vào kho mã: file SRT có chữ chép lời nên không được đưa lên Git hay Notion.

  CSV: mỗi clip một dòng (khóa clip, tên, timecode bắt đầu, độ dài, ngôn ngữ, mức kéo âm lượng, số dòng, số dòng nghi, lý do).
  SRT: mọi dòng của các clip đó, giờ nối tiếp liên tục như SRT theo giai đoạn, mã [clip#số dòng] trong dòng chữ; dòng nghi thêm
       nhãn [NGHI:lý do] để dễ tìm. Lý do: hallu = câu bịa quen thuộc, lap = lặp câu trước, ngoai = ngoài đoạn có tiếng, thua = quá ít chữ,
       keo = kéo âm lượng nhiều, khong_chu = có tiếng nhưng Whisper không ra chữ.

Chạy: & $py app\\troly_speech_review.py --store <file .loinoi.sqlite> --project <tên> [--out <thư mục>] [--limit 50]
"""
import argparse
import csv
import datetime
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import troly_speech as sp            # noqa: E402
import troly_speech_srt as sx        # noqa: E402

LIMIT = 50


def _ro(path):
    uri = "file:" + os.path.abspath(path).replace("\\", "/") + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def suspect_clips(store_path, limit=LIMIT):
    """Danh sách clip có thể sai (tối đa limit), nặng nhất trước. Trả (hàng clip, mọi mã clip của kho, hàm lấy dòng)."""
    con = _ro(store_path)
    try:
        allkeys = [r[0] for r in con.execute("SELECT key FROM clips")]
        flagged = {}
        for key, why in con.execute("SELECT clip, why FROM lines WHERE why != ''"):
            for w in why.split(","):
                if w:
                    flagged.setdefault(key, []).append(w)
        rows = []
        for key, name, tc, dur, lang, gain, n_lines, status in con.execute(
                "SELECT key, name, tc, dur, lang, gain_db, n_lines, status FROM clips WHERE suspect = 1"):
            reasons = sorted(set(flagged.get(key, [])))
            if (gain or 0) > sp.WARN_GAIN_DB:
                reasons.append("keo")
            if status == "done" and not n_lines:
                reasons.append("khong_chu")
            rows.append({"key": key, "name": name, "tc": tc or "", "dur": dur or 0, "lang": lang or "", "gain_db": gain or 0,
                         "n_lines": n_lines or 0, "n_flagged": len(flagged.get(key, [])), "reasons": reasons})
        rows.sort(key=lambda r: (-r["n_flagged"], -r["gain_db"], r["key"]))
        rows = rows[:limit]
        lines = {}
        for r in rows:
            lines[r["key"]] = [{"idx": i, "t0": a, "t1": b, "text": t, "why": [w for w in (y or "").split(",") if w]}
                               for i, a, b, t, y in con.execute("SELECT idx, t0, t1, text, why FROM lines WHERE clip=? ORDER BY idx", (r["key"],))]
        return rows, allkeys, lines
    finally:
        con.close()


def export(store_path, out_dir, project="project", limit=LIMIT, now=None):
    """Ghi CSV + SRT vào out_dir (không ghi đè file cũ: tên có ngày giờ). Trả {'csv','srt','clips','lines'} hoặc {'clips': 0}."""
    rows, allkeys, lines = suspect_clips(store_path, limit)
    if not rows:
        return {"clips": 0, "lines": 0}
    os.makedirs(out_dir, exist_ok=True)
    stamp = (now or datetime.datetime.now()).strftime("%Y%m%d-%H%M%S")
    base = os.path.join(out_dir, "co_the_sai_%s_%s" % (sx.safe_name(project), stamp))
    codes = sx.clip_codes(allkeys)
    with open(base + ".csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ma_clip", "khoa_clip", "ten_file", "timecode_bat_dau", "dai_giay", "ngon_ngu", "keo_am_luong_dB", "so_dong",
                    "so_dong_nghi", "ly_do"])
        for r in rows:
            w.writerow([codes[r["key"]], r["key"], r["name"], r["tc"], round(r["dur"], 1), r["lang"], round(r["gain_db"], 1),
                        r["n_lines"], r["n_flagged"], " ".join(r["reasons"])])
    packs = []
    for r in rows:
        ls = []
        for l in lines[r["key"]]:
            tag = "[NGHI:%s] " % ",".join(l["why"]) if l["why"] else ""
            ls.append({"idx": l["idx"], "t0": l["t0"], "t1": l["t1"], "text": tag + (l["text"] or ""), "why": []})   # đưa dòng nghi vào SRT, có nhãn
        packs.append({"key": r["key"], "code": codes[r["key"]], "dur": r["dur"], "lines": ls})
    text, n, _skipped, _layout = sx.build_srt(packs)
    with open(base + ".srt", "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text + "\n")
    return {"csv": base + ".csv", "srt": base + ".srt", "clips": len(rows), "lines": n}


def main():
    a_ = argparse.ArgumentParser(description="Xuất danh sách clip có thể sai (chỉ đọc kho) ra CSV + SRT trong thư mục dữ liệu")
    a_.add_argument("--store", required=True)
    a_.add_argument("--project", default="project")
    a_.add_argument("--out", default=None)
    a_.add_argument("--limit", type=int, default=LIMIT)
    a = a_.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                       # noqa: BLE001
        pass
    out = a.out
    if not out:
        cfg = os.path.join(os.path.dirname(HERE), "config.json")
        with open(cfg, "r", encoding="utf-8-sig") as f:
            out = os.path.join(json.load(f)["data_root"], "troly", "review")
    root = os.path.dirname(HERE).lower()
    if os.path.abspath(out).lower().startswith(root + os.sep):
        sys.exit("Thư mục xuất không được nằm trong thư mục mã (chữ chép lời không vào git).")
    r = export(a.store, out, a.project, a.limit)
    print("Đã xuất %d clip, %d dòng chữ." % (r["clips"], r["lines"]) if r["clips"] else "Không có clip nào 'có thể sai'.")
    for k in ("csv", "srt"):
        if r.get(k):
            print(k.upper() + ": " + r[k])


if __name__ == "__main__":
    main()
