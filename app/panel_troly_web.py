r"""
panel_troly_web.py - Trợ lý File Quay v0.2.0, giao diện HTML (ADR-0010, người dựng duyệt 15/11/2026).

Mở cửa sổ pywebview (WebView2 của Windows) hiển thị src\troly_web\index.html; chức năng ở troly_api.TrolyApi
(JavaScript gọi qua window.pywebview.api). Menu DaVinci "VideoAI Trợ lý File Quay" mở file này (cài bằng install.py ở thư mục gốc).

Chạy tay: & $py app\panel_troly_web.py --project "<tên project đang mở trong DaVinci>"
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import troly_api as ta       # noqa: E402

APP_ID = "VideoAI.TroLy"
INDEX = os.path.join(HERE, "troly_web", "index.html")


def fail(msg):
    import troly_env
    troly_env.fail(msg)


def main():
    import argparse
    a_ = argparse.ArgumentParser(description="Trợ lý File Quay (giao diện HTML)")
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
    data_root = troly_env.data_root()
    if not data_root:
        fail("Không đọc được config.json (data_root).")
    if not a.project:
        fail("Hãy mở Trợ lý từ menu Workspace > Scripts của DaVinci (hoặc chạy với --project).")

    holder = {}

    def emit(kind, data):
        w = holder.get("win")
        if w is not None:
            w.evaluate_js("window.onEvent && window.onEvent(%s, %s)" % (json.dumps(kind), json.dumps(data)))

    api = ta.TrolyApi(a.project, data_root, emit=emit, proxy_root=troly_env.config().get("proxy_root"))
    # maximized: luôn vừa màn hình ở mọi tỉ lệ DPI (không lẹm mép); min_size đủ cho bố cục 3 cột
    win = webview.create_window("VideoAI Trợ lý File Quay - " + a.project, url=INDEX, js_api=api,
                                width=1440, height=880, min_size=(1100, 680), background_color="#18181B",
                                maximized=True, text_select=False)
    holder["win"] = win
    api.pick_dir_fn = lambda: (lambda r: r[0] if r else None)(win.create_file_dialog(webview.FOLDER_DIALOG))
    win.events.closed += lambda: api.close()
    webview.start(debug=a.debug, gui="edgechromium")


if __name__ == "__main__":
    main()
