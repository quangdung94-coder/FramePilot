r"""
panel_troly_web.py - FramePilot (trước 18/11/2026 tên là "Trợ lý File Quay") v0.2.0, giao diện HTML (ADR-0010, người dựng duyệt 15/11/2026).

Mở cửa sổ pywebview (WebView2 của Windows) hiển thị src\troly_web\index.html; chức năng ở troly_api.TrolyApi
(JavaScript gọi qua window.pywebview.api). Menu DaVinci "FramePilot" mở file này (cài bằng install.py ở thư mục gốc).

Chạy tay: & $py app\panel_troly_web.py --project "<tên project đang mở trong DaVinci>"
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import troly_api as ta       # noqa: E402

APP_ID = "FramePilot"                         # nhóm riêng trên taskbar (không gộp với python.exe)
ICON = os.path.join(HERE, "assets", "framepilot.ico")
INDEX = os.path.join(HERE, "troly_web", "index.html")


def set_window_icon(win, ico=None):
    """Gắn icon FramePilot lên cửa sổ pywebview (Windows cần .ico, đặt bằng WM_SETICON) để titlebar và taskbar hiện đúng icon thay vì icon Python.
    Lỗi gì cũng bỏ qua (chỉ mất icon, không ảnh hưởng chức năng)."""
    ico = ico or ICON
    if not os.path.isfile(ico):
        return False
    try:
        import ctypes
        hwnd = int(win.native.Handle.ToInt64())
        u = ctypes.windll.user32
        u.LoadImageW.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        # WM_SETICON = 0x80; ICON_SMALL = 0, ICON_BIG = 1; LoadImage: IMAGE_ICON = 1, LR_LOADFROMFILE = 0x10
        for which, size in ((0, u.GetSystemMetrics(49)), (1, u.GetSystemMetrics(11))):       # SM_CXSMICON, SM_CXICON (theo DPI hiện tại)
            h = u.LoadImageW(None, ico, 1, size, size, 0x10)
            if h:
                u.SendMessageW(hwnd, 0x80, which, h)
        return True
    except Exception:                         # noqa: BLE001
        return False


def fail(msg):
    import troly_env
    troly_env.fail(msg)


def main():
    import argparse
    a_ = argparse.ArgumentParser(description="FramePilot (giao diện HTML)")
    a_.add_argument("--project", help="tên project đang mở trong DaVinci")
    a_.add_argument("--debug", action="store_true", help="bật công cụ kiểm tra của WebView2 (F12)")
    a = a_.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                         # noqa: BLE001
        pass
    try:                                      # icon/nhóm riêng trên taskbar
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:                         # noqa: BLE001
        pass
    try:
        import webview
    except ImportError:
        fail("Thiếu pywebview. Chạy: & $py -m pip install pywebview")
    import troly_env
    troly_env.kill_children_on_exit()          # đóng cửa sổ thì ffmpeg/Whisper/AI do panel chạy ra cũng tắt theo
    data_root = troly_env.data_root()
    if not data_root:
        fail("Không đọc được config.json (data_root).")
    if not a.project:
        fail("Hãy mở Trợ lý từ menu Workspace > Scripts của DaVinci (hoặc chạy với --project).")
    lock = troly_env.instance_lock(data_root, a.project)        # giữ đến khi đóng cửa sổ (biến cục bộ sống tới hết main)
    if lock is None:
        fail("FramePilot đang mở cho project \"%s\" ở một cửa sổ khác. Hãy dùng cửa sổ đó (hai cửa sổ cùng project sẽ ghi đè nhãn của nhau)."
             % a.project)

    holder = {}

    def emit(kind, data):
        w = holder.get("win")
        if w is not None:
            w.evaluate_js("window.onEvent && window.onEvent(%s, %s)" % (json.dumps(kind), json.dumps(data)))

    api = ta.TrolyApi(a.project, data_root, emit=emit, proxy_root=troly_env.config().get("proxy_root"))
    # maximized: luôn vừa màn hình ở mọi tỉ lệ DPI (không lẹm mép); min_size đủ cho bố cục 3 cột
    win = webview.create_window("FramePilot - " + a.project, url=INDEX, js_api=api,
                                width=1440, height=880, min_size=(1100, 680), background_color="#18181B",
                                maximized=True, text_select=False)
    holder["win"] = win
    api.debug = a.debug                           # --debug: bật nút "Đo lướt" ở trình phát
    api.pick_dir_fn = lambda: (lambda r: r[0] if r else None)(win.create_file_dialog(webview.FOLDER_DIALOG))
    win.events.closed += lambda: api.close()
    win.events.shown += lambda: set_window_icon(win)
    webview.start(debug=a.debug, gui="edgechromium")


if __name__ == "__main__":
    main()
