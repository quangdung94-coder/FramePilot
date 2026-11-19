"""
troly_proc.py - MỘT chỗ duy nhất để chạy tiến trình con (ffmpeg, ffprobe, Whisper, tiến trình AI, lệnh tắt máy) mà KHÔNG hiện cửa sổ console đen.

Trên Windows, panel chạy bằng pythonw nên tiến trình con nào không giấu console sẽ chớp một cửa sổ cmd đen. Mọi lời gọi subprocess trong app\ phải đi qua
chay_an (chạy xong mới trả, như subprocess.run) hoặc mo_an (chạy nền, như subprocess.Popen). Có test quét: không còn lời gọi subprocess nào ngoài file này.
"""
import os
import subprocess

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _giau(kw):
    """Thêm cờ CREATE_NO_WINDOW và STARTUPINFO(SW_HIDE) vào kwargs (giữ cờ người gọi đã đặt, ví dụ độ ưu tiên thấp)."""
    kw = dict(kw)
    if os.name == "nt":
        kw["creationflags"] = int(kw.get("creationflags") or 0) | CREATE_NO_WINDOW
        if kw.get("startupinfo") is None:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0                          # SW_HIDE
            kw["startupinfo"] = si
    return kw


def chay_an(cmd, **kw):
    """subprocess.run không hiện cửa sổ console."""
    return subprocess.run(cmd, **_giau(kw))


def mo_an(cmd, **kw):
    """subprocess.Popen không hiện cửa sổ console."""
    return subprocess.Popen(cmd, **_giau(kw))
