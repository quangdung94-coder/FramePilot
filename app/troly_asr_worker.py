# -*- coding: utf-8 -*-
"""troly_asr_worker.py - Chạy Whisper AI cục bộ bằng venv AI riêng:
- macOS Apple Silicon (chip M): ưu tiên mlx-whisper (GPU Metal / Unified Memory) nếu thư mục model là định dạng MLX.
- Windows / dự phòng CT2: chạy faster-whisper (CUDA float16 trên NVIDIA, hoặc CPU int8).
KHÔNG ghi chữ chép lời ra log hay file; chỉ trả JSON kết quả qua stdout. CHỈ ĐỌC WAV tạm.
"""
import argparse
import json
import os
import sys


def _add_cuda12_dlls():
    if os.name != "nt":
        return
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


def is_mlx_model_dir(model_dir):
    """True nếu thư mục là model Whisper định dạng MLX (weights.npz / weights.safetensors / model.safetensors, không phải CT2 model.bin)."""
    if not model_dir or not os.path.isdir(model_dir):
        return False
    if os.path.isfile(os.path.join(model_dir, "model.bin")):
        return False
    for fname in ("weights.npz", "weights.safetensors", "model.safetensors"):
        if os.path.isfile(os.path.join(model_dir, fname)):
            return True
    return False


def _run_mlx(model_dir, wavs, lang, prompt):
    """Chạy mlx-whisper tận dụng GPU Apple Silicon (100% offline từ thư mục model cục bộ)."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import mlx_whisper
    out = {}
    kw = {"path_or_hf_repo": model_dir, "language": lang or "vi"}
    if prompt and (lang or "vi") == "vi":
        kw["initial_prompt"] = prompt
    for w in wavs:
        if not os.path.isfile(w):
            out[w] = []
            continue
        res = mlx_whisper.transcribe(w, **kw) or {}
        rows = []
        for s in (res.get("segments") or []):
            txt = str(s.get("text") or "").strip()
            if txt:
                rows.append([round(float(s.get("start") or 0.0), 2), round(float(s.get("end") or 0.0), 2), txt])
        out[w] = rows
    return out


def _run_faster_whisper(model_dir, wavs, lang, prompt, beam):
    _add_cuda12_dlls()
    from faster_whisper import WhisperModel

    try:
        model = WhisperModel(model_dir, device="cuda", compute_type="float16")
    except Exception:
        model = WhisperModel(model_dir, device="cpu", compute_type="int8")

    out = {}
    kw = {"language": lang or "vi", "vad_filter": True, "beam_size": max(1, int(beam))}
    if prompt and (lang or "vi") == "vi":
        kw["initial_prompt"] = prompt

    for w in wavs:
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
    return out


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
    ap.add_argument("--backend", default="auto", choices=("auto", "mlx", "ct2"))
    ap.add_argument("wavs", nargs="+")
    a = ap.parse_args()

    use_mlx = (a.backend == "mlx") or (a.backend == "auto" and sys.platform == "darwin" and is_mlx_model_dir(a.model))
    if use_mlx:
        out = _run_mlx(a.model, a.wavs, a.lang, a.prompt)
    else:
        out = _run_faster_whisper(a.model, a.wavs, a.lang, a.prompt, a.beam)

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
