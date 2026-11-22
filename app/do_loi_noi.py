"""
do_loi_noi.py - ĐO chép lời trên vài clip người dựng chỉ (đề bài lời nói A, bước 1). Chỉ in SỐ, không in chữ chép lời.

  & $py app\do_loi_noi.py "J:\...\DG1234.MP4" "J:\...\DG1235.MP4" [--lang vi] [--max-gain 30]

Mỗi clip in: độ dài, mức tiếng gốc (p95, trung vị, đỉnh), dB kéo lên, số đoạn nói, giây tiếng đưa vào Whisper, giây chạy,
tốc độ (giây chạy / giây tiếng), số câu, số câu nghi bịa theo mã lý do. File gốc chỉ được ffmpeg ĐỌC.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import troly_speech as sp   # noqa: E402


def whisper_cfg():
    """Cấu hình whisper: config.json của dự án (khóa "whisper"); chưa có thì dùng mặc định chuẩn hóa."""
    import troly_env
    p = os.path.join(os.path.dirname(HERE), "config.json")
    cfg = {}
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            cfg = (json.load(f).get("whisper") or {})
    except (OSError, ValueError):
        pass
    cfg.setdefault("exe", troly_env.constme_exe())
    cfg.setdefault("model", troly_env.constme_model())
    return cfg


def main():
    a_ = argparse.ArgumentParser()
    a_.add_argument("files", nargs="+")
    a_.add_argument("--lang", default="vi")
    a_.add_argument("--max-gain", type=float, default=sp.MAX_GAIN_DB)
    a_.add_argument("--no-gain", action="store_true", help="đo đối chứng: KHÔNG kéo âm lượng")
    a = a_.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                       # noqa: BLE001
        pass
    cfg = whisper_cfg()
    for k in ("exe", "model"):
        if not os.path.isfile(cfg[k]):
            sys.exit("Không thấy %s: %s" % (k, cfg[k]))
    name, vad = sp.load_vad()
    if vad is None:
        sys.exit("Thiếu thư viện silero-vad (không tải gì về; hỏi người dựng).")
    phr = sp.load_phrases()
    index = sp.build_index(phr)
    for i, f in enumerate(a.files, 1):
        if not os.path.isfile(f):
            print("[%d] KHÔNG THẤY FILE" % i)
            continue
        r = sp.transcribe_clip(f, cfg, vad, lang=a.lang, prompt=phr.get("prompt"), index=index,
                               max_gain=0.0 if a.no_gain else a.max_gain)
        n = len(r["lines"])
        bad = [l for l in r["lines"] if l["why"]]
        why = {}
        for l in bad:
            for w in l["why"]:
                why[w] = why.get(w, 0) + 1
        speech_s = round(sum(b - a_ for a_, b in r["speech"]), 1)
        rtf = round(r["took_s"] / r["audio_s"], 2) if r["audio_s"] else None
        keys = sum(1 for l in r["lines"] if l["keys"])
        print("[%d] %s | dài %.0fs | mức gốc p95 %.1f dB, trung vị %.1f dB, đỉnh %.3f | kéo +%.1f dB | VAD %d đoạn, %.1fs nói | "
              "Whisper %.1fs tiếng, chạy %.1fs (x%s) | %d câu, nghi bịa %d %s, câu có cụm key %d"
              % (i, os.path.basename(f)[:3] + "***", r["dur"], r["p95_db"], r["med_db"], r["peak"], r["gain_db"],
                 len(r["speech"]), speech_s, r["audio_s"], r["took_s"], rtf, n, len(bad), json.dumps(why), keys),
              flush=True)


if __name__ == "__main__":
    main()
