# -*- coding: utf-8 -*-
"""troly_audio_events.py - Nhận diện sự kiện âm thanh đám cưới (vỗ tay, cười lớn, cụng ly, múa lân, pháo hoa, xúc động)
bằng LAION-CLAP (chạy offline trên GPU/CPU trong C:\\VideoAI_ai_venv). CHỈ ĐỌC WAV tạm, không sửa file gốc.
"""
import argparse
import json
import os
import sys
import wave

EVENTS = (
    ("vỗ tay", "crowd clapping and loud applause at a wedding celebration"),
    ("cười lớn", "people laughing loudly and cheering happily at a party"),
    ("cụng ly", "glasses clinking and toasting champagne at a banquet dinner"),
    ("múa lân", "loud traditional lion dance drums and cymbals"),
    ("pháo hoa", "fireworks exploding and crowd cheering"),
    ("xúc động", "emotional crying and sobbing during a wedding speech"),
)


def _read_wav_48k(path):
    import numpy as np
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return x, sr


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--thr", type=float, default=0.35)
    ap.add_argument("--win", type=float, default=3.0)
    ap.add_argument("--step", type=float, default=2.0)
    a = ap.parse_args()

    if not os.path.isdir(a.model) or not os.path.isfile(a.wav):
        print("[]")
        return

    import numpy as np
    import torch
    from transformers import ClapModel, ClapProcessor

    x, sr = _read_wav_48k(a.wav)
    if len(x) < int(sr * 0.5):
        print("[]")
        return

    if torch.cuda.is_available():
        dev = "cuda"
    elif getattr(getattr(torch, "backends", None), "mps", None) and torch.backends.mps.is_available():
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        dev = "mps"
    else:
        dev = "cpu"
    proc = ClapProcessor.from_pretrained(a.model, local_files_only=True)
    model = ClapModel.from_pretrained(a.model, local_files_only=True).to(dev).eval()

    labels = [e[0] for e in EVENTS]
    prompts = [e[1] for e in EVENTS]
    win_n = max(1, int(a.win * sr))
    step_n = max(1, int(a.step * sr))
    chunks, spans = [], []
    pos = 0
    dur = len(x) / float(sr)
    while pos < len(x):
        seg = x[pos:pos + win_n]
        if len(seg) < int(0.8 * sr) and chunks:
            break
        chunks.append(seg)
        spans.append((round(pos / float(sr), 2), round(min(dur, (pos + win_n) / float(sr)), 2)))
        pos += step_n
        if len(chunks) >= 90:  # tối đa ~3 phút quét nhanh
            break

    if not chunks:
        print("[]")
        return

    out = []
    with torch.no_grad():
        t_inp = proc(text=prompts, return_tensors="pt", padding=True).to(dev)
        t_feat = model.get_text_features(**t_inp)
        if not isinstance(t_feat, torch.Tensor):
            t_feat = getattr(t_feat, "pooler_output", t_feat[0])
        t_feat = t_feat / t_feat.norm(dim=-1, keepdim=True)

        bs = 16
        for i in range(0, len(chunks), bs):
            batch = chunks[i:i + bs]
            a_inp = proc(audio=batch, sampling_rate=sr, return_tensors="pt", padding=True).to(dev)
            a_feat = model.get_audio_features(**a_inp)
            if not isinstance(a_feat, torch.Tensor):
                a_feat = getattr(a_feat, "pooler_output", a_feat[0])
            a_feat = a_feat / a_feat.norm(dim=-1, keepdim=True)
            sims = (a_feat @ t_feat.T).float().cpu().numpy()
            # Chuyển sang xác suất softmax nhẹ + lọc theo ngưỡng cosine thô
            for j, row in enumerate(sims):
                best_k = int(np.argmax(row))
                raw_sim = float(row[best_k])
                if raw_sim >= a.thr:
                    t0, t1 = spans[i + j]
                    if out and out[-1]["tag"] == labels[best_k] and t0 <= out[-1]["t1"] + 0.5:
                        out[-1]["t1"] = max(out[-1]["t1"], t1)
                        out[-1]["score"] = max(out[-1]["score"], round(raw_sim, 3))
                    else:
                        out.append({"t0": t0, "t1": t1, "tag": labels[best_k], "score": round(raw_sim, 3)})

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
