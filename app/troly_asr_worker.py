# -*- coding: utf-8 -*-
"""troly_asr_worker.py - Chạy faster-whisper (Whisper large-v3-turbo / PhoWhisper CT2) bằng venv AI riêng.
KHÔNG ghi chữ chép lời ra log hay file; chỉ trả JSON kết quả qua stdout. CHỈ ĐỌC WAV tạm.
"""
import argparse
import json
import os
import sys


def _add_cuda12_dlls():
    sp = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")
    for sub in ("cublas", "cudnn", "cuda_nvrtc"):
        b = os.path.join(sp, sub, "bin")
        if os.path.isdir(b):
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(b)
                except OSError:
                    pass
            os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--lang", default="vi")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--beam", type=int, default=3)
    ap.add_argument("wavs", nargs="+")
    a = ap.parse_args()

    _add_cuda12_dlls()
    from faster_whisper import WhisperModel

    try:
        model = WhisperModel(a.model, device="cuda", compute_type="float16")
    except Exception:
        model = WhisperModel(a.model, device="cpu", compute_type="int8")

    out = {}
    kw = {"language": a.lang or "vi", "vad_filter": True, "beam_size": max(1, int(a.beam))}
    if a.prompt and (a.lang or "vi") == "vi":
        kw["initial_prompt"] = a.prompt

    for w in a.wavs:
        if not os.path.isfile(w):
            out[w] = []
            continue
        segs, _info = model.transcribe(w, **kw)
        rows = []
        for s in segs:
            txt = (s.text or "").strip()
            if txt:
                rows.append([round(float(s.start), 2), round(float(s.end), 2), txt])
        out[w] = rows

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
