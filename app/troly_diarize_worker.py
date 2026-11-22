# -*- coding: utf-8 -*-
"""troly_diarize_worker.py - Tách người nói (MC vs Gia đình / Cô dâu Chú rể) bằng microsoft/wavlm-base-plus-sv
(100% offline, giấy phép mở, không cần HF_TOKEN). CHỈ ĐỌC WAV 16kHz tạm; chỉ trả JSON nhãn người nói qua stdout.
"""
import argparse
import json
import os
import sys
import wave

MC_HINTS = ("quý vị", "kính thưa", "trân trọng", "giới thiệu", "pháo tay", "xin mời", "chương trình", "buổi lễ", "sân khấu")


def _read_wav_16k(path):
    import numpy as np
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0, sr


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--segs", required=True, help="Đường dẫn file JSON chứa danh sách [[t0, t1, text], ...]")
    ap.add_argument("--thr", type=float, default=0.68)
    a = ap.parse_args()

    if not os.path.isdir(a.model) or not os.path.isfile(a.wav) or not os.path.isfile(a.segs):
        print("[]")
        return

    with open(a.segs, "r", encoding="utf-8") as f:
        segs = json.load(f) or []
    if not segs:
        print("[]")
        return

    import numpy as np
    import torch
    from transformers import AutoFeatureExtractor, WavLMForXVector

    x, sr = _read_wav_16k(a.wav)
    if torch.cuda.is_available():
        dev = "cuda"
    elif getattr(getattr(torch, "backends", None), "mps", None) and torch.backends.mps.is_available():
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        dev = "mps"
    else:
        dev = "cpu"
    fe = AutoFeatureExtractor.from_pretrained(a.model, local_files_only=True)
    model = WavLMForXVector.from_pretrained(a.model, local_files_only=True).to(dev).eval()

    embs = []
    with torch.no_grad():
        for item in segs:
            t0, t1 = float(item[0]), float(item[1])
            s0 = max(0, int(t0 * sr))
            s1 = min(len(x), int(max(t1, t0 + 0.6) * sr))
            chunk = x[s0:s1]
            if len(chunk) < int(0.35 * sr):
                embs.append(None)
                continue
            if len(chunk) > int(12.0 * sr):
                chunk = chunk[:int(12.0 * sr)]
            inp = fe(chunk, sampling_rate=sr, return_tensors="pt").to(dev)
            v = model(**inp).embeddings[0].float().cpu().numpy()
            n = float(np.linalg.norm(v))
            embs.append(v / n if n > 1e-6 else None)

    # Gom cụm online thuần numpy bằng cosine similarity
    centroids = []
    counts = []
    assign = []
    for v in embs:
        if v is None:
            assign.append(assign[-1] if assign else 0)
            continue
        best_c, best_s = -1, -1.0
        for ci, cent in enumerate(centroids):
            s = float(np.dot(v, cent))
            if s > best_s:
                best_s, best_c = s, ci
        if best_c >= 0 and best_s >= a.thr:
            n_old = counts[best_c]
            nc = centroids[best_c] * n_old + v
            centroids[best_c] = nc / (float(np.linalg.norm(nc)) or 1.0)
            counts[best_c] = n_old + 1
            assign.append(best_c)
        else:
            centroids.append(v.copy())
            counts.append(1)
            assign.append(len(centroids) - 1)

    # Đoán nhãn MC nếu một cụm có nhiều câu chứa từ khóa dẫn chương trình
    mc_hits = {}
    for ci, item in zip(assign, segs):
        txt = str(item[2] if len(item) > 2 else "").lower()
        if any(k in txt for k in MC_HINTS):
            mc_hits[ci] = mc_hits.get(ci, 0) + 1
    mc_cluster = max(mc_hits.items(), key=lambda kv: kv[1])[0] if mc_hits else -1

    label_map = {}
    num = 1
    for ci in sorted(set(assign)):
        if ci == mc_cluster:
            label_map[ci] = "MC"
        else:
            label_map[ci] = "Người %d" % num
            num += 1

    print(json.dumps([label_map.get(ci, "Người 1") for ci in assign], ensure_ascii=False))


if __name__ == "__main__":
    main()
