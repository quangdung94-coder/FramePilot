"""
troly_proc.py - MỘT chỗ duy nhất để chạy tiến trình con (ffmpeg, ffprobe, Whisper, tiến trình AI, lệnh tắt máy) mà KHÔNG hiện cửa sổ console đen.

Trên Windows, panel chạy bằng pythonw nên tiến trình con nào không giấu console sẽ chớp một cửa sổ cmd đen. Mọi lời gọi subprocess trong app\ phải đi qua
chay_an (chạy xong mới trả, như subprocess.run) hoặc mo_an (chạy nền, như subprocess.Popen). Có test quét: không còn lời gọi subprocess nào ngoài file này.
"""
import os
import subprocess
import threading

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_ACT_LOCK = threading.Lock()
_ACTIVE = {}  # tag -> set[Popen]


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


def kill_tree(pid):
    """Diệt trọn cây tiến trình con (cả venv launcher lẫn python.exe thật trên Windows) mà không hiện cửa sổ đen."""
    if not pid:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                **_giau({"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "timeout": 5}),
            )
            return
        except Exception:  # noqa: BLE001
            pass
    try:
        os.kill(int(pid), 9)
    except OSError:
        pass


def huy_nhom(tag):
    """Ngắt ngay lập tức mọi tiến trình con đang chạy thuộc nhóm `tag` (vd 'speech' khi bấm Dừng)."""
    with _ACT_LOCK:
        procs = list(_ACTIVE.get(tag) or ())
    for p in procs:
        if p.poll() is None:
            kill_tree(p.pid)
            try:
                p.kill()
            except OSError:
                pass


def chay_an(cmd, **kw):
    """subprocess.run không hiện cửa sổ console. Truyền tag='speech' để hỗ trợ hủy ngang bằng huy_nhom(tag)."""
    tag = kw.pop("tag", None)
    if not tag:
        return subprocess.run(cmd, **_giau(kw))
    timeout = kw.pop("timeout", None)
    cap = kw.pop("capture_output", False)
    if cap:
        kw.setdefault("stdout", subprocess.PIPE)
        kw.setdefault("stderr", subprocess.PIPE)
    p = mo_an(cmd, **kw)
    with _ACT_LOCK:
        _ACTIVE.setdefault(tag, set()).add(p)
    try:
        out, err = p.communicate(timeout=timeout)
        return subprocess.CompletedProcess(cmd, p.returncode, out, err)
    except subprocess.TimeoutExpired:
        kill_tree(p.pid)
        try:
            p.communicate(timeout=2)
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        with _ACT_LOCK:
            s = _ACTIVE.get(tag)
            if s is not None:
                s.discard(p)


def mo_an(cmd, **kw):
    """subprocess.Popen không hiện cửa sổ console."""
    return subprocess.Popen(cmd, **_giau(kw))
