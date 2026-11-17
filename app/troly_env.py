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


def fail(msg):
    """Báo lỗi bằng hộp thoại Windows (panel chạy bằng pythonw nên không có cửa sổ chữ), rồi thoát."""
    print("[LỖI] " + msg)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "Trợ lý File Quay", 0x10)
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
