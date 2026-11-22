r"""
troly_env.py - Cấu hình và kết nối DaVinci cho Trợ lý File Quay (thay cho các module dùng chung của repo VideoAI cũ).

- config.json nằm ở thư mục gốc TroLyFileQuay (cạnh CLAUDE.md).
- data_root: nơi lưu nhãn, kế hoạch project, cache thumbnail (mặc định D:\VideoAI\data, dùng chung với bản cũ
  để không mất công xếp tay).
"""
import atexit
import json
import os
import sys


def is_mac():
    """True khi đang chạy trên macOS."""
    return sys.platform == "darwin"


def _mac_bundle_parent(exe_dir):
    """Nếu chạy từ FramePilot.app/Contents/MacOS, trả về thư mục chứa FramePilot.app (ghi được, không nằm trong .app)."""
    norm = os.path.abspath(exe_dir)
    if norm.endswith(os.path.join(".app", "Contents", "MacOS")):
        return os.path.abspath(os.path.join(norm, "..", "..", ".."))
    p1 = os.path.dirname(norm)
    p2 = os.path.dirname(p1)
    if os.path.basename(norm) == "MacOS" and os.path.basename(p1) == "Contents" and p2.endswith(".app"):
        return os.path.dirname(p2)
    return norm


def mac_app_support_dir():
    return os.path.expanduser("~/Library/Application Support/FramePilot")


if getattr(sys, "frozen", False):
    _EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    APP = getattr(sys, "_MEIPASS", _EXE_DIR)
    _BASE_DIR = _mac_bundle_parent(_EXE_DIR) if is_mac() else _EXE_DIR
    # Ưu tiên config.json ở cạnh gói (hoặc Application Support trên macOS), không có mới lùi lên repo
    _cfg_here = os.path.join(_BASE_DIR, "config.json")
    _mac_sup = mac_app_support_dir()
    _repo_guess = os.path.abspath(os.path.join(_BASE_DIR, "..", ".."))
    if os.path.isfile(_cfg_here):
        ROOT = _BASE_DIR
    elif is_mac() and os.path.isfile(os.path.join(_mac_sup, "config.json")):
        ROOT = _mac_sup
    elif os.path.isfile(os.path.join(_repo_guess, "config.json")):
        ROOT = _repo_guess
    else:
        ROOT = _BASE_DIR
else:
    APP = os.path.dirname(os.path.abspath(__file__))
    ROOT = os.path.dirname(APP)
CONFIG = os.path.join(ROOT, "config.json")


def ensure_tools_path():
    """Đưa các thư mục công cụ đi kèm (tools/ffmpeg, ...) vào PATH để ffmpeg/ffprobe chạy được trên máy mới chưa cài sẵn PATH."""
    cands = [
        os.path.join(ROOT, "tools", "ffmpeg"),
        os.path.join(APP, "tools", "ffmpeg"),
        os.path.join(ROOT, "tools"),
    ]
    if is_mac():
        cands += [
            os.path.join(mac_app_support_dir(), "tools", "ffmpeg"),
            "/opt/homebrew/bin",
            "/usr/local/bin",
        ]
    else:
        cands += [
            r"D:\VideoAI\tools\ffmpeg",
            r"C:\VideoAI\tools\ffmpeg",
        ]
    cur = os.environ.get("PATH") or ""
    parts = [p for p in cur.split(os.pathsep) if p]
    low = {os.path.normcase(os.path.abspath(p)) for p in parts}
    added = []
    for d in cands:
        if os.path.isdir(d):
            nd = os.path.normcase(os.path.abspath(d))
            if nd not in low:
                added.append(d)
                low.add(nd)
    if added:
        os.environ["PATH"] = os.pathsep.join(added + parts)


ensure_tools_path()


def default_data_root(cfg=None):
    """Đường dẫn data_root từ config hoặc thư mục data mặc định trên máy hiện tại."""
    c = cfg if isinstance(cfg, dict) else config()
    v = c.get("data_root")
    if v:
        return v
    if not is_mac() and os.path.isdir(r"D:\VideoAI\data"):
        return r"D:\VideoAI\data"
    return os.path.join(ROOT, "data")


def ai_python(cfg_value=None, cfg=None):
    """Tìm Python của môi trường AI theo hệ điều hành (Windows: Scripts/python.exe; macOS: bin/python3)."""
    if cfg_value and os.path.isfile(cfg_value):
        return cfg_value
    c = cfg if isinstance(cfg, dict) else config()
    if is_mac():
        sup = mac_app_support_dir()
        cands = [
            cfg_value,
            c.get("ai_python"),
            os.path.join(ROOT, "ai_env", "bin", "python3"),
            os.path.join(ROOT, "ai_env", "bin", "python"),
            os.path.join(sup, "ai_env", "bin", "python3"),
            os.path.join(sup, "ai_env", "bin", "python"),
        ]
        fallback = cfg_value or c.get("ai_python") or os.path.join(ROOT, "ai_env", "bin", "python3")
    else:
        cands = [
            cfg_value,
            c.get("ai_python"),
            os.path.join(ROOT, "ai_env", "Scripts", "python.exe"),
            os.path.join(ROOT, "ai_env", "python.exe"),
            r"C:\VideoAI_ai_venv\Scripts\python.exe",
            r"C:\VideoAI_ai_venv\python.exe",
            r"C:\VideoAI_venv\Scripts\python.exe",
        ]
        fallback = cfg_value or c.get("ai_python") or r"C:\VideoAI_ai_venv\Scripts\python.exe"
    for p in cands:
        if p and os.path.isfile(p):
            return p
    return fallback


def vad_python(cfg=None):
    """Tìm Python có silero-vad cho troly_vad_worker.py."""
    c = cfg if isinstance(cfg, dict) else config()
    if is_mac():
        sup = mac_app_support_dir()
        cands = [
            c.get("python"),
            c.get("ai_python"),
            os.path.join(ROOT, "ai_env", "bin", "python3"),
            os.path.join(ROOT, "ai_env", "bin", "python"),
            os.path.join(sup, "ai_env", "bin", "python3"),
        ]
    else:
        cands = [
            c.get("python"),
            os.path.join(ROOT, "ai_env", "Scripts", "python.exe"),
            os.path.join(ROOT, "ai_env", "python.exe"),
            r"C:\VideoAI_venv\Scripts\python.exe",
            c.get("ai_python"),
            r"C:\VideoAI_ai_venv\Scripts\python.exe",
            r"C:\VideoAI_ai_venv\python.exe",
        ]
    for p in cands:
        if p and os.path.isfile(p):
            return p
    return None


def constme_exe():
    """Đường dẫn Const-me Whisper CLI dự phòng (chỉ Windows; trên macOS dùng MLX/faster-whisper nên trả chuỗi rỗng)."""
    if is_mac():
        return ""
    for p in (
        os.path.join(ROOT, "tools", "whisper", "constme", "cli", "main.exe"),
        r"D:\VideoAI\tools\whisper\constme\cli\main.exe",
        r"C:\VideoAI\tools\whisper\constme\cli\main.exe",
    ):
        if os.path.isfile(p):
            return p
    return os.path.join(ROOT, "tools", "whisper", "constme", "cli", "main.exe")


def constme_model(droot=None):
    """Đường dẫn model ggml-medium.bin cho Const-me Whisper (chỉ Windows; macOS trả chuỗi rỗng)."""
    if is_mac():
        return ""
    base = droot or default_data_root()
    for p in (
        os.path.join(base, "models", "ggml-medium.bin"),
        os.path.join(ROOT, "models", "ggml-medium.bin"),
        r"D:\VideoAI\data\models\ggml-medium.bin",
    ):
        if os.path.isfile(p):
            return p
    return os.path.join(base, "models", "ggml-medium.bin")


def torch_device(torch_mod=None):
    """Chọn thiết bị PyTorch tối ưu: cuda (Windows NVIDIA) -> mps (Apple Silicon chip M) -> cpu."""
    t = torch_mod
    if t is None:
        import torch as t
    if t.cuda.is_available():
        return "cuda"
    mps = getattr(getattr(t, "backends", None), "mps", None)
    if mps is not None and mps.is_available():
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        return "mps"
    return "cpu"


def torch_empty_cache(torch_mod=None):
    """Giải phóng bộ nhớ GPU sau khi nhúng (CUDA hoặc Apple Silicon MPS)."""
    t = torch_mod
    if t is None:
        import torch as t
    if t.cuda.is_available():
        t.cuda.empty_cache()
        return
    mps = getattr(getattr(t, "backends", None), "mps", None)
    if mps is not None and mps.is_available():
        mps_mod = getattr(t, "mps", None)
        if mps_mod is not None and hasattr(mps_mod, "empty_cache"):
            try:
                mps_mod.empty_cache()
            except Exception:  # noqa: BLE001
                pass


def config_path():
    """config.json mặc định ở thư mục gốc; biến môi trường TROLY_CONFIG trỏ sang file khác (dùng để thử panel trên BẢN SAO dữ liệu)."""
    return os.environ.get("TROLY_CONFIG") or CONFIG


def config():
    try:
        with open(config_path(), "r", encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def data_root():
    return config().get("data_root")


def cache_root():
    """Nơi chứa cache (thumbnail, sóng âm, keyframe, khung RAM). Mặc định trùng data_root nếu chưa cấu hình riêng."""
    return config().get("cache_root") or data_root()


def srt_root():
    """Thư mục mặc định xuất / chứa file SRT của toàn bộ panel (rỗng = mỗi lần xuất sẽ hỏi)."""
    return config().get("srt_root") or ""


def templates_path():
    """Đường dẫn file/thư mục lưu mẫu sự kiện (rỗng = mặc định <data_root>/troly/templates.json)."""
    return config().get("templates_path") or ""


def camera_luts():
    """Ánh xạ tiền tố tên file máy quay -> đường dẫn file LUT (.cube/.3dl) để xem trước khi clip chưa gắn LUT trong DaVinci."""
    v = config().get("camera_luts")
    return dict(v) if isinstance(v, dict) else {}


def asr_engine():
    """Động cơ chép lời Page 4: 'auto' (ưu tiên Whisper large-v3-turbo), 'whisper_turbo', 'phowhisper', 'constme'."""
    v = str(config().get("asr_engine") or "auto").strip().lower()
    return v if v in ("auto", "whisper_turbo", "phowhisper", "constme") else "auto"


def save_config(patch):
    """Cập nhật một phần config.json qua file tạm (giữ nguyên các mục khác)."""
    p = config_path()
    cur = config()
    cur.update(patch or {})
    parent = os.path.dirname(os.path.abspath(p))
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return cur


def window_title(project):
    """Tiêu đề cửa sổ FramePilot của một project (dùng để tạo cửa sổ và để cửa sổ thứ hai tìm lại cửa sổ cũ)."""
    return "FramePilot - " + project


def bring_to_front(title, user32=None):
    """Đưa cửa sổ có tiêu đề `title` lên trước, khôi phục nếu đang thu nhỏ. Trả True nếu tìm thấy;
    False nếu không thấy / lỗi (khi đó gọi lại giữ thông báo cũ). Chỉ thao tác cửa sổ, không đụng gì khác."""
    if is_mac() and user32 is None:
        try:
            import troly_proc
            script = (
                'on run argv\n'
                '  set t to item 1 of argv\n'
                '  tell application "System Events"\n'
                '    repeat with p in (every application process whose visible is true)\n'
                '      repeat with w in (every window of p)\n'
                '        if name of w is t then\n'
                '          set frontmost of p to true\n'
                '          return "OK"\n'
                '        end if\n'
                '      end repeat\n'
                '    end repeat\n'
                '  end tell\n'
                '  return "NO"\n'
                'end run'
            )
            r = troly_proc.chay_an(["osascript", "-e", script, title], capture_output=True, text=True, timeout=3)
            return r.returncode == 0 and "OK" in (r.stdout or "")
        except Exception:                                 # noqa: BLE001
            return False
    try:
        if user32 is None:
            import ctypes
            user32 = ctypes.windll.user32
            user32.FindWindowW.restype = ctypes.c_void_p
            user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
            for fn in ("IsIconic", "ShowWindow", "SetForegroundWindow", "BringWindowToTop"):
                getattr(user32, fn).argtypes = [ctypes.c_void_p] + ([ctypes.c_int] if fn == "ShowWindow" else [])
        h = user32.FindWindowW(None, title)
        if not h:
            return False
        if user32.IsIconic(h):
            user32.ShowWindow(h, 9)                       # SW_RESTORE
        user32.keybd_event(0x12, 0, 0, 0)                 # bấm-nhả Alt: Windows mới cho tiến trình mới giành foreground
        user32.keybd_event(0x12, 0, 2, 0)
        user32.BringWindowToTop(h)
        user32.SetForegroundWindow(h)
        return not user32.IsIconic(h)
    except Exception:                                     # noqa: BLE001
        return False


def fail(msg):
    """Báo lỗi bằng hộp thoại hệ điều hành (Windows MessageBoxW / macOS osascript dialog), rồi thoát."""
    print("[LỖI] " + msg)
    if is_mac():
        try:
            import troly_proc
            script = 'on run argv\ndisplay dialog (item 1 of argv) with title "FramePilot" buttons {"OK"} default button 1 with icon stop\nend run'
            troly_proc.chay_an(["osascript", "-e", script, str(msg)], capture_output=True, text=True, timeout=15)
        except Exception:                                 # noqa: BLE001
            pass
    else:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, msg, "FramePilot", 0x10)
        except Exception:                                 # noqa: BLE001  không phải Windows
            pass
    sys.exit(1)


def resolve_paths(cfg=None):
    """Trả về (api_dir, modules_dir, lib_path, resolve_dir) của DaVinci Resolve theo hệ điều hành."""
    c = cfg if isinstance(cfg, dict) else config()
    if is_mac():
        resolve_dir = (c.get("resolve") or {}).get("install_path") or "/Applications/DaVinci Resolve/DaVinci Resolve.app"
        api_dir = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
        modules = os.path.join(api_dir, "Modules")
        lib = os.path.join(resolve_dir, "Contents", "Libraries", "Fusion", "fusionscript.so")
        if not os.path.isfile(lib):
            alt_lib = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
            if os.path.isfile(alt_lib):
                lib = alt_lib
        return api_dir, modules, lib, resolve_dir
    resolve_dir = (c.get("resolve") or {}).get("install_path") or os.path.join(
        os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Blackmagic Design", "DaVinci Resolve")
    api_dir = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Blackmagic Design", "DaVinci Resolve",
                           "Support", "Developer", "Scripting")
    modules = os.path.join(api_dir, "Modules")
    lib = os.path.join(resolve_dir, "fusionscript.dll")
    return api_dir, modules, lib, resolve_dir


def connect_resolve():
    """Kết nối DaVinci Resolve Studio đang mở (Windows & macOS). Lỗi thì ném RuntimeError."""
    api_dir, modules, lib, resolve_dir = resolve_paths()
    if not os.path.isfile(lib):
        raise RuntimeError("Không thấy %s. DaVinci cài chỗ khác thì sửa config.json mục resolve.install_path." % lib)
    os.environ["RESOLVE_SCRIPT_API"] = api_dir
    os.environ["RESOLVE_SCRIPT_LIB"] = lib
    if modules not in sys.path:
        sys.path.append(modules)
    if not is_mac() and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(resolve_dir)
    try:
        import DaVinciResolveScript as dvr
    except ImportError as e:
        raise RuntimeError("Python không nạp được thư viện của DaVinci: %s" % e)
    resolve = dvr.scriptapp("Resolve")
    if not resolve:
        raise RuntimeError("Không kết nối được DaVinci. Hãy mở DaVinci và bật Preferences > System > General > "
                           "External scripting using = Local.")
    return resolve


def instance_lock(data_root, project):
    """Mỗi project chỉ MỘT cửa sổ FramePilot: khóa <data_root>/troly/locks/<project>.lock (Windows: msvcrt; macOS/POSIX: fcntl.flock).
    Trả file đang giữ khóa, hoặc None nếu cửa sổ khác đang giữ."""
    import troly_core as tc
    d = os.path.join(data_root, "troly", "locks")
    try:
        os.makedirs(d, exist_ok=True)
        f = open(os.path.join(d, tc._safe(project) + ".lock"), "a+b")
    except OSError:
        return _NoLock()
    try:
        import msvcrt
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f
        except OSError:
            f.close()
            return None
    except ImportError:                                                       # macOS / Linux (POSIX)
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except OSError:
            f.close()
            return None
        except ImportError:
            return f


class _NoLock(object):
    def close(self):
        pass


_JOB = None
_ATEXIT_REGISTERED = False


def kill_children_on_exit():
    """Windows: gắn Job Object KILL_ON_JOB_CLOSE. macOS/POSIX: đăng ký atexit dọn sạch mọi tiến trình con."""
    global _JOB, _ATEXIT_REGISTERED
    if os.name != "nt":
        if not _ATEXIT_REGISTERED:
            def _cleanup_posix():
                try:
                    import troly_proc
                    troly_proc.huy_tat_ca()
                except Exception:                                             # noqa: BLE001
                    pass
            atexit.register(_cleanup_posix)
            _ATEXIT_REGISTERED = True
        return True
    try:
        import ctypes
        from ctypes import wintypes as w

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", w.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]

        class IOC(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ("r", "w", "o", "rb", "wb", "ob")]

        class EXT(ctypes.Structure):
            _fields_ = [("Basic", BASIC), ("Io", IOC), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        k = ctypes.windll.kernel32
        k.CreateJobObjectW.restype = w.HANDLE
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        k.GetCurrentProcess.restype = w.HANDLE
        job = k.CreateJobObjectW(None, None)
        if not job:
            return False
        info = EXT()
        info.Basic.LimitFlags = 0x2000                                       # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            return False
        if not k.AssignProcessToJobObject(job, k.GetCurrentProcess()):
            return False
        _JOB = job                                                            # giữ tay cầm đến hết đời tiến trình
        return True
    except Exception:                                                         # noqa: BLE001
        return False
