r"""
troly_vad_worker.py - Worker tách riêng chạy silero-vad qua Python venv (C:\VideoAI_venv).

Dùng khi FramePilot.exe đóng gói PyInstaller (loại torch để giữ file .exe gọn nhẹ).
Đọc file PCM int16 mono 16 kHz (--pcm <path>), in ra dòng JSON [[start_s, end_s], ...].
"""
import argparse
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcm", required=True, help="File raw PCM int16 mono 16kHz")
    ap.add_argument("--rate", type=int, default=16000)
    a = ap.parse_args()
    if not os.path.isfile(a.pcm):
        sys.exit("Khong thay file PCM: " + a.pcm)
    import numpy as np
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    torch.set_num_threads(1)
    with open(a.pcm, "rb") as f:
        raw = f.read()
    x = np.frombuffer(raw, dtype=np.int16)
    if x.size == 0:
        print("[]")
        return
    model = load_silero_vad()
    ts = get_speech_timestamps(
        torch.from_numpy(x.astype(np.float32) / 32768.0),
        model,
        sampling_rate=a.rate,
        return_seconds=True,
    )
    out = [[round(float(t["start"]), 2), round(float(t["end"]), 2)] for t in ts]
    print(json.dumps(out))


if __name__ == "__main__":
    main()
