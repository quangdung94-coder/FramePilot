r"""
troly_env.py - Cấu hình và kết nối DaVinci cho Trợ lý File Quay (thay cho các module dùng chung của repo VideoAI cũ).

- config.json nằm ở thư mục gốc TroLyFileQuay (cạnh CLAUDE.md).
- data_root: nơi lưu nhãn, kế hoạch project, cache thumbnail (mặc định D:\VideoAI\data, dùng chung với bản cũ
  để không mất công xếp tay).
"""
import json
import os
import sys

APP = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(APP)
CONFIG = os.path.join(ROOT, "config.json")


def config():
    try:
        with open(CONFIG, "r", encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def data_root():
    return config().get("data_root")


def window_title(project):
    """Tiêu đề cửa sổ FramePilot của một project (dùng để tạo cửa sổ và để cửa sổ thứ hai tìm lại cửa sổ cũ)."""
    return "FramePilot - " + project


def bring_to_front(title, user32=None):
    """Đưa cửa sổ có tiêu đề `title` lên trước, khôi phục nếu đang thu nhỏ. Trả True nếu tìm thấy và cửa sổ không còn thu nhỏ;
    False nếu không thấy / không phải Windows / lỗi (khi đó gọi lại giữ thông báo cũ). Chỉ thao tác cửa sổ, không đụng gì khác."""
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
    """Báo lỗi bằng hộp thoại Windows (panel chạy bằng pythonw nên không có cửa sổ chữ), rồi thoát."""
    print("[LỖI] " + msg)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "FramePilot", 0x10)
    except Exception:                         # noqa: BLE001  không phải Windows
        pass
    sys.exit(1)


def connect_resolve():
    """Kết nối DaVinci Resolve Studio đang mở. Lỗi thì ném RuntimeError (luồng nền sẽ báo lên giao diện)."""
    resolve_dir = (config().get("resolve") or {}).get("install_path") or os.path.join(
        os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Blackmagic Design", "DaVinci Resolve")
    api_dir = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Blackmagic Design", "DaVinci Resolve",
                           "Support", "Developer", "Scripting")
    modules = os.path.join(api_dir, "Modules")
    lib = os.path.join(resolve_dir, "fusionscript.dll")
    if not os.path.isfile(lib):
        raise RuntimeError("Không thấy %s. DaVinci cài chỗ khác thì sửa config.json mục resolve.install_path." % lib)
    os.environ["RESOLVE_SCRIPT_API"] = api_dir
    os.environ["RESOLVE_SCRIPT_LIB"] = lib
    if modules not in sys.path:
        sys.path.append(modules)
    if hasattr(os, "add_dll_directory"):
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
    """Mỗi project chỉ MỘT cửa sổ FramePilot: hai cửa sổ cùng project giữ hai bản kế hoạch trong bộ nhớ và ghi đè nhau (mất nhãn/sao).
    Khóa một byte của <data_root>\\troly\\locks\\<project>.lock (msvcrt.locking). Trả file đang giữ khóa (giữ đến hết đời tiến trình,
    tiến trình chết thì Windows tự nhả), hoặc None nếu cửa sổ khác đang giữ. Không khóa được vì lý do khác (ổ chỉ đọc...) thì cho chạy."""
    import troly_core as tc
    d = os.path.join(data_root, "troly", "locks")
    try:
        os.makedirs(d, exist_ok=True)
        f = open(os.path.join(d, tc._safe(project) + ".lock"), "a+b")
    except OSError:
        return _NoLock()
    try:
        import msvcrt
    except ImportError:                                                       # không phải Windows
        return f
    try:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        return f
    except OSError:
        f.close()
        return None


class _NoLock(object):
    def close(self):
        pass


_JOB = None


def kill_children_on_exit():
    """Windows: gom tiến trình này vào một Job Object có cờ KILL_ON_JOB_CLOSE, để ffmpeg / Whisper / AI do panel chạy ra bị tắt theo khi
    cửa sổ đóng (không để tiến trình mồ côi). Lỗi (không phải Windows, đã nằm trong job không cho lồng) thì bỏ qua, trả False."""
    global _JOB
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
