r"""
install.py - Cài Trợ lý File Quay vào menu Workspace > Scripts > Utility của DaVinci.

Đặt một file khởi chạy nhỏ "VideoAI Trợ lý File Quay.py" vào thư mục Scripts của DaVinci. File đó mở
app\panel_troly_web.py bằng Python ngoài (có pywebview) và truyền tên project đang mở.
Nếu đã có mục cùng tên do repo VideoAI cũ cài thì ghi đè để menu trỏ sang thư mục mới này.
Sửa code trong app\ thì KHÔNG cần cài lại, chỉ đóng và mở lại cửa sổ Trợ lý.

Cách chạy (PowerShell, trong thư mục TroLyFileQuay):
  & C:\VideoAI_venv\Scripts\python.exe install.py           cài hoặc cập nhật
  & C:\VideoAI_venv\Scripts\python.exe install.py --check   chỉ kiểm tra
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(ROOT, "app", "panel_troly_web.py")
NAME = "VideoAI Trợ lý File Quay.py"
MARKER = "# TROLY-FILE-QUAY-LAUNCHER"
OLD_MARKERS = ("# VIDEOAI-PANEL-LAUNCHER",)      # mục do repo VideoAI cũ cài: được phép ghi đè

LAUNCHER = '''# Trợ lý File Quay - file khởi chạy do install.py tạo. Đừng sửa tay, hãy chạy lại install.py.
{marker}
# DaVinci chạy file này bằng Python riêng của nó, nên chỉ mở panel bằng Python ngoài rồi kết thúc ngay.
import os
import subprocess

PYTHONW = r"{pythonw}"
PANEL = r"{panel}"

args = [PYTHONW, PANEL]
try:
    _proj = resolve.GetProjectManager().GetCurrentProject()   # noqa: F821  (biến có sẵn khi chạy trong DaVinci)
    if _proj:
        args += ["--project", _proj.GetName()]
except Exception:
    pass
env = {{k: v for k, v in os.environ.items() if not k.upper().startswith("PYTHON")}}
subprocess.Popen(args, cwd=os.path.dirname(PANEL), env=env, close_fds=True,
                 creationflags=0x00000008 | 0x00000200)   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
'''


def scripts_dir():
    try:
        with open(os.path.join(ROOT, "config.json"), "r", encoding="utf-8-sig") as f:
            p = (json.load(f).get("resolve") or {}).get("scripts_dir")
        if p:
            return os.path.join(p, "Utility")
    except Exception:                         # noqa: BLE001
        pass
    appdata = os.environ.get("APPDATA")
    if not appdata:
        sys.exit("Không đọc được biến APPDATA của Windows.")
    return os.path.join(appdata, "Blackmagic Design", "DaVinci Resolve", "Support", "Fusion", "Scripts", "Utility")


def main():
    a_ = argparse.ArgumentParser(description="Cài Trợ lý File Quay vào Workspace > Scripts của DaVinci")
    a_.add_argument("--check", action="store_true", help="chỉ kiểm tra, không ghi")
    a = a_.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                         # noqa: BLE001
        pass
    if not os.path.isfile(PANEL):
        sys.exit("Không thấy " + PANEL)
    if subprocess.run([sys.executable, "-c", "import webview, PIL"], capture_output=True).returncode != 0:
        sys.exit("Python %s thiếu pywebview hoặc Pillow. Chạy: & %s -m pip install -r requirements.txt"
                 % (sys.executable, sys.executable))
    w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    pythonw = w if os.path.isfile(w) else sys.executable
    dst = os.path.join(scripts_dir(), NAME)
    want = LAUNCHER.format(marker=MARKER, pythonw=pythonw, panel=PANEL)
    have = None
    if os.path.isfile(dst):
        with open(dst, "r", encoding="utf-8") as f:
            have = f.read()
        if MARKER not in have and not any(m in have for m in OLD_MARKERS):
            sys.exit("Đã có file '%s' không do VideoAI tạo. Dừng lại để không ghi đè." % dst)
    print("Panel:   " + PANEL)
    print("Python:  " + pythonw)
    print("Cài vào: " + dst)
    if have == want:
        print("KẾT QUẢ: đã cài đúng bản này. Không cần làm gì.")
        return
    if a.check:
        print("KẾT QUẢ: %s. Chạy lại không có --check để cài." % ("chưa cài" if have is None else "menu đang trỏ chỗ khác"))
        sys.exit(1)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst + ".tmp", "w", encoding="utf-8") as f:
        f.write(want)
    os.replace(dst + ".tmp", dst)
    print("KẾT QUẢ: %s." % ("đã cài mới, khởi động lại DaVinci nếu chưa thấy mục menu" if have is None
                           else "menu đã trỏ sang thư mục TroLyFileQuay"))


if __name__ == "__main__":
    main()
