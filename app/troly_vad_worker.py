r"""
troly_vad_worker.py - Worker tách riêng chạy silero-vad qua Python venv (C:\VideoAI_venv / ai_env).

Dùng khi FramePilot.exe / FramePilot.app đóng gói PyInstaller (loại torch để giữ bản chạy gọn nhẹ).
- Một lần: --pcm <path> --rate 16000 -> in dòng JSON [[start_s, end_s], ...].
- Chế độ giữ sống (--serve): nạp model silero-vad đúng 1 lần, nhận nhiều clip PCM qua stdin/stdout.
"""
import argparse
import json
import os
import sys


def _read_exact(stream, nbytes):
    buf = bytearray()
    while len(buf) < nbytes:
        chunk = stream.read(nbytes - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def _run_pcm(np, torch, get_speech_timestamps, model, raw, rate):
    x = np.frombuffer(raw, dtype=np.int16)
    if x.size == 0:
        return []
    ts = get_speech_timestamps(
        torch.from_numpy(x.astype(np.float32) / 32768.0),
        model,
        sampling_rate=int(rate),
        return_seconds=True,
    )
    return [[round(float(t["start"]), 2), round(float(t["end"]), 2)] for t in ts]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcm", default="", help="File raw PCM int16 mono 16kHz")
    ap.add_argument("--rate", type=int, default=16000)
    ap.add_argument("--serve", action="store_true", help="Giữ tiến trình sống nhận nhiều clip PCM qua stdin/stdout")
    a = ap.parse_args()

    if not a.serve and not os.path.isfile(a.pcm):
        sys.exit("Khong thay file PCM: " + a.pcm)

    import numpy as np
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    torch.set_num_threads(1)
    model = load_silero_vad()

    if a.serve:
        sys.stdout.write(json.dumps({"ready": True}) + "\n")
        sys.stdout.flush()
        stdin_buf = sys.stdin.buffer
        while True:
            raw_line = stdin_buf.readline()
            if not raw_line:
                break
            try:
                req = json.loads(raw_line.decode("utf-8"))
            except Exception:
                continue
            cmd = req.get("cmd")
            if cmd == "quit":
                break
            if cmd == "pcm":
                nbytes = int(req.get("nbytes") or 0)
                rate = int(req.get("rate") or a.rate)
                if nbytes <= 0:
                    out = []
                else:
                    raw = _read_exact(stdin_buf, nbytes)
                    if raw is None:
                        break
                    out = _run_pcm(np, torch, get_speech_timestamps, model, raw, rate)
                sys.stdout.write(json.dumps(out) + "\n")
                sys.stdout.flush()
        return

    with open(a.pcm, "rb") as f:
        raw = f.read()
    print(json.dumps(_run_pcm(np, torch, get_speech_timestamps, model, raw, a.rate)))


if __name__ == "__main__":
    main()
