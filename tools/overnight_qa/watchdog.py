r"""
watchdog.py - Process, Memory, GPU VRAM, Handle, Popup Dialog & Zombie Watchdog.

Runs a lightweight background sampling thread while FramePilot.exe executes:
- Tracks FramePilot.exe RSS MB, threads, handles (Windows), CPU time.
- Tracks associated msedgewebview2.exe processes (total RSS MB & count).
- Tracks worker subprocesses (ffmpeg, ffprobe, AI python workers).
- Samples NVIDIA GPU VRAM (MB) & utilization (%) via nvidia-smi (offline).
- Detects Windows crash/error dialogs (#32770) belonging to FramePilot.exe and
  extracts the full dialog message text.
- Detects memory/VRAM leaks (sustained upward drift) and zombie processes left
  behind after FramePilot.exe closes.
"""
import ctypes
from ctypes import wintypes
import os
import subprocess
import threading
import time
import psutil

WORKER_KEYWORDS = (
    "troly_asr_worker",
    "troly_face_worker",
    "troly_diarize_worker",
    "troly_audio_events",
    "troly_ai.py",
)


def query_nvidia_gpu():
    """Return (vram_used_mb, vram_total_mb, gpu_util_pct) or (None, None, None)."""
    try:
        si = None
        if os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            timeout=2.5,
            startupinfo=si,
        ).decode("utf-8", errors="replace").strip()
        if not out:
            return None, None, None
        first_line = out.splitlines()[0]
        parts = [p.strip() for p in first_line.split(",")]
        if len(parts) >= 3:
            return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        pass
    return None, None, None


def detect_error_dialogs(target_pid: int):
    """Inspect visible #32770 MessageBox dialogs owned by target_pid on Windows."""
    if os.name != "nt" or not target_pid:
        return []
    dialogs = []
    try:
        user32 = ctypes.windll.user32
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def read_child_texts(parent_hwnd):
            texts = []

            def child_cb(chwnd, _lp):
                buf = ctypes.create_unicode_buffer(1024)
                user32.GetWindowTextW(chwnd, buf, 1024)
                t = buf.value.strip()
                if t and t not in ("OK", "Cancel", "Yes", "No", "&OK", "&Cancel"):
                    texts.append(t)
                return True

            user32.EnumChildWindows(parent_hwnd, EnumWindowsProc(child_cb), 0)
            return " | ".join(texts)

        def win_cb(hwnd, _lp):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == target_pid and user32.IsWindowVisible(hwnd):
                cls = ctypes.create_unicode_buffer(128)
                title = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls, 128)
                user32.GetWindowTextW(hwnd, title, 256)
                if cls.value == "#32770":
                    body = read_child_texts(hwnd)
                    dialogs.append({"hwnd": int(hwnd), "title": title.value, "body": body})
            return True

        user32.EnumWindows(EnumWindowsProc(win_cb), 0)
    except Exception:
        pass
    return dialogs


def snapshot_fp_workers(parent_pid: int = 0):
    """Find active FramePilot AI/media worker processes (ffmpeg, ffprobe, troly_*_worker)."""
    found = []
    child_pids = set()
    if parent_pid:
        try:
            for c in psutil.Process(parent_pid).children(recursive=True):
                child_pids.add(c.pid)
        except Exception:
            pass

    for p in psutil.process_iter(["pid", "ppid", "name", "cmdline", "memory_info"]):
        try:
            name = (p.info["name"] or "").lower()
            cmd = " ".join(p.info["cmdline"] or [])
            is_worker = False
            if p.info["pid"] in child_pids and name in ("ffmpeg.exe", "ffprobe.exe", "python.exe", "pythonw.exe"):
                is_worker = True
            elif name in ("python.exe", "pythonw.exe") and any(k in cmd for k in WORKER_KEYWORDS):
                is_worker = True
            if is_worker:
                rss = (p.info["memory_info"].rss / (1024 * 1024)) if p.info["memory_info"] else 0.0
                found.append({
                    "pid": p.info["pid"],
                    "ppid": p.info["ppid"],
                    "name": name,
                    "rss_mb": round(rss, 1),
                    "cmd": cmd[:200],
                })
        except Exception:
            pass
    return found


def snapshot_webview2_for_exe(exe_name: str = "FramePilot.exe"):
    """Return (count, total_rss_mb) for msedgewebview2.exe processes belonging to FramePilot."""
    count = 0
    total_mb = 0.0
    marker = f"--webview-exe-name={exe_name}".lower()
    for p in psutil.process_iter(["name", "cmdline", "memory_info"]):
        try:
            if (p.info["name"] or "").lower() != "msedgewebview2.exe":
                continue
            cmd = " ".join(p.info["cmdline"] or []).lower()
            if marker in cmd:
                count += 1
                if p.info["memory_info"]:
                    total_mb += p.info["memory_info"].rss / (1024 * 1024)
        except Exception:
            pass
    return count, round(total_mb, 1)


class ResourceWatchdog:
    """Background sampler that records RAM/VRAM/handles/workers and detects leaks."""

    def __init__(self, interval_sec: float = 5.0):
        self.interval_sec = interval_sec
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._target_pid = 0
        self.samples = []
        self.popup_dialogs = []

    def set_target_pid(self, pid: int):
        with self._lock:
            self._target_pid = int(pid or 0)

    def start(self, pid: int = 0):
        self.set_target_pid(pid)
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="qa-watchdog")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def sample_once(self):
        with self._lock:
            pid = self._target_pid
        rec = {
            "ts": round(time.time(), 1),
            "pid": pid,
            "alive": False,
            "fp_rss_mb": 0.0,
            "fp_handles": 0,
            "fp_threads": 0,
            "wv2_count": 0,
            "wv2_rss_mb": 0.0,
            "total_app_mb": 0.0,
            "worker_count": 0,
            "worker_rss_mb": 0.0,
            "vram_used_mb": None,
            "vram_total_mb": None,
            "gpu_util_pct": None,
        }
        if pid:
            try:
                p = psutil.Process(pid)
                if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                    rec["alive"] = True
                    rec["fp_rss_mb"] = round(p.memory_info().rss / (1024 * 1024), 1)
                    rec["fp_threads"] = p.num_threads()
                    if hasattr(p, "num_handles"):
                        rec["fp_handles"] = p.num_handles()
            except Exception:
                pass

            dialogs = detect_error_dialogs(pid)
            if dialogs:
                with self._lock:
                    for d in dialogs:
                        self.popup_dialogs.append({"ts": rec["ts"], **d})

        wv_cnt, wv_mb = snapshot_webview2_for_exe("FramePilot.exe")
        workers = snapshot_fp_workers(pid)
        w_mb = round(sum(w["rss_mb"] for w in workers), 1)
        vram_used, vram_total, gpu_pct = query_nvidia_gpu()

        rec["wv2_count"] = wv_cnt
        rec["wv2_rss_mb"] = wv_mb
        rec["worker_count"] = len(workers)
        rec["worker_rss_mb"] = w_mb
        rec["total_app_mb"] = round(rec["fp_rss_mb"] + wv_mb + w_mb, 1)
        rec["vram_used_mb"] = vram_used
        rec["vram_total_mb"] = vram_total
        rec["gpu_util_pct"] = gpu_pct

        with self._lock:
            self.samples.append(rec)
        return rec

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.sample_once()
            except Exception:
                pass
            self._stop.wait(self.interval_sec)

    def analyze_leaks(self, ram_drift_mb: float = 450.0, handle_drift: int = 800, vram_drift_mb: float = 900.0):
        """Compare early baseline window vs late window to detect sustained RAM/handle/VRAM leaks."""
        findings = []
        with self._lock:
            alive_samples = [s for s in self.samples if s.get("alive")]
        if len(alive_samples) < 6:
            return findings

        k = max(2, len(alive_samples) // 5)
        early = alive_samples[:k]
        late = alive_samples[-k:]

        avg = lambda arr, key: sum(x[key] for x in arr) / len(arr)

        early_ram = avg(early, "total_app_mb")
        late_ram = avg(late, "total_app_mb")
        if late_ram - early_ram >= ram_drift_mb:
            findings.append({
                "category": "MEMORY_LEAK",
                "severity": "HIGH",
                "title": f"Nghi rò rỉ RAM: tăng +{late_ram - early_ram:.0f} MB ({early_ram:.0f} -> {late_ram:.0f} MB)",
                "detail": f"Tổng RAM (FramePilot + WebView2 + workers) tăng liên tục qua {len(alive_samples)} mẫu đo.",
            })

        early_h = avg(early, "fp_handles")
        late_h = avg(late, "fp_handles")
        if late_h - early_h >= handle_drift:
            findings.append({
                "category": "HANDLE_LEAK",
                "severity": "HIGH",
                "title": f"Nghi rò rỉ Handle Windows: tăng +{late_h - early_h:.0f} ({early_h:.0f} -> {late_h:.0f})",
                "detail": "File/socket/process handle trong FramePilot.exe tăng bất thường (hay gặp khi cv2/ffmpeg chưa đóng file).",
            })

        early_v = [s["vram_used_mb"] for s in early if s["vram_used_mb"] is not None]
        late_v = [s["vram_used_mb"] for s in late if s["vram_used_mb"] is not None]
        if early_v and late_v:
            ev = sum(early_v) / len(early_v)
            lv = sum(late_v) / len(late_v)
            if lv - ev >= vram_drift_mb:
                findings.append({
                    "category": "VRAM_LEAK",
                    "severity": "HIGH",
                    "title": f"Nghi rò rỉ VRAM GPU: tăng +{lv - ev:.0f} MB ({ev:.0f} -> {lv:.0f} MB)",
                    "detail": "VRAM GPU không giải phóng hết sau các chu kỳ chạy AI.",
                })
        return findings

    def peak_stats(self):
        with self._lock:
            s = list(self.samples)
        if not s:
            return {}
        vrams = [x["vram_used_mb"] for x in s if x["vram_used_mb"] is not None]
        return {
            "samples": len(s),
            "peak_fp_mb": max(x["fp_rss_mb"] for x in s),
            "peak_wv2_mb": max(x["wv2_rss_mb"] for x in s),
            "peak_total_mb": max(x["total_app_mb"] for x in s),
            "peak_handles": max(x["fp_handles"] for x in s),
            "peak_workers": max(x["worker_count"] for x in s),
            "peak_vram_mb": max(vrams) if vrams else None,
        }
