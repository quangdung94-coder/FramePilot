"""
troly_proc.py - MỘT chỗ duy nhất để chạy tiến trình con (ffmpeg, ffprobe, Whisper, tiến trình AI, lệnh tắt máy) mà KHÔNG hiện cửa sổ console đen.

Trên Windows, panel chạy bằng pythonw nên tiến trình con nào không giấu console sẽ chớp một cửa sổ cmd đen. Mọi lời gọi subprocess trong app\ phải đi qua
chay_an (chạy xong mới trả, như subprocess.run) hoặc mo_an (chạy nền, như subprocess.Popen). Có test quét: không còn lời gọi subprocess nào ngoài file này.
"""
import os
import signal
import subprocess
import threading

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_ACT_LOCK = threading.Lock()
_ACTIVE = {}      # tag -> set[Popen]
_ALL_PROCS = set()  # mọi Popen đang sống do mo_an tạo ra (để huy_tat_ca dọn sạch trên macOS/POSIX)


def _giau(kw, new_session=False):
    """Thêm cờ CREATE_NO_WINDOW và STARTUPINFO(SW_HIDE) trên Windows; trên macOS/POSIX bỏ cờ Windows-only."""
    kw = dict(kw)
    if os.name == "nt":
        kw["creationflags"] = int(kw.get("creationflags") or 0) | CREATE_NO_WINDOW
        if kw.get("startupinfo") is None:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0                          # SW_HIDE
            kw["startupinfo"] = si
    else:
        kw.pop("creationflags", None)
        kw.pop("startupinfo", None)
        if new_session and "start_new_session" not in kw:
            kw["start_new_session"] = True
    return kw


def kill_tree(pid):
    """Diệt trọn cây tiến trình con (Windows: taskkill /T /F; macOS/POSIX: killpg nhóm tiến trình con)."""
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
    else:
        try:
            pgid = os.getpgid(int(pid))
            if pgid and pgid != os.getpgid(0):
                os.killpg(pgid, signal.SIGKILL)
                return
        except OSError:
            pass
    try:
        os.kill(int(pid), getattr(signal, "SIGKILL", 9))
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


def huy_tat_ca():
    """Ngắt toàn bộ tiến trình con đang theo dõi (dùng cho atexit trên macOS/POSIX thay Windows Job Object)."""
    with _ACT_LOCK:
        tags = list(_ACTIVE.keys())
        all_p = list(_ALL_PROCS)
    for t in tags:
        huy_nhom(t)
    for p in all_p:
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
            _ALL_PROCS.discard(p)


def mo_an(cmd, **kw):
    """subprocess.Popen không hiện cửa sổ console (trên POSIX tách session riêng để kill_tree & huy_tat_ca diệt sạch tiến trình con)."""
    p = subprocess.Popen(cmd, **_giau(kw, new_session=True))
    with _ACT_LOCK:
        dead = [x for x in _ALL_PROCS if x.poll() is not None]
        for x in dead:
            _ALL_PROCS.discard(x)
        _ALL_PROCS.add(p)
    return p
