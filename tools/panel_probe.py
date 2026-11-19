r"""panel_probe.py - mở cửa sổ FramePilot THẬT (pywebview/WebView2) trên BẢN SAO dữ liệu, bấm phím thật (F1, Shift+F1...) và chụp màn hình.

Không ghi gì vào DaVinci (chỉ đọc), không đụng dữ liệu thật: dữ liệu kế hoạch ghi vào --data (thư mục tạm), config tạm nối bằng TROLY_CONFIG.
  & $py tools\panel_probe.py --project "<tên project đang mở trong DaVinci>" --bin "Master/…" [--timeline "<tên>"] --out "<thư mục ảnh>"
Phải để Unikey chế độ E, Windows ngôn ngữ ENG (nếu không phím số bị chặn).
"""
import argparse
import ctypes
import ctypes.wintypes
import json
import os
import shutil
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
sys.path.insert(0, APP)

VK_F = {n: 0x6F + n for n in range(1, 10)}      # F1 = 0x70
VK_SHIFT, VK_ESC = 0x10, 0x1B


def fg_title():
    u = ctypes.windll.user32
    h = u.GetForegroundWindow()
    n = u.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, buf, n + 1)
    return buf.value


def press(vk, shift=False, need=""):
    """Bấm phím THẬT (có mã quét, để event.code đúng). Không gửi nếu cửa sổ trước mặt không phải cửa sổ thử."""
    u = ctypes.windll.user32
    if need and need not in fg_title():
        raise RuntimeError("cửa sổ trước mặt không phải panel thử: %r" % fg_title())
    sc = lambda v: u.MapVirtualKeyW(v, 0)           # noqa: E731
    if shift:
        u.keybd_event(VK_SHIFT, sc(VK_SHIFT), 0, 0)
    u.keybd_event(vk, sc(vk), 0, 0)
    time.sleep(0.06)
    u.keybd_event(vk, sc(vk), 2, 0)
    if shift:
        u.keybd_event(VK_SHIFT, sc(VK_SHIFT), 2, 0)
    time.sleep(0.6)


def grab(path, title=""):
    """Chụp đúng khung cửa sổ thử (nếu tìm thấy), không thì cả màn hình. Hỗ trợ nhiều màn hình (toạ độ ảo)."""
    from PIL import ImageGrab
    u = ctypes.windll.user32
    h = u.FindWindowW(None, title) if title else 0
    if h:
        r = ctypes.wintypes.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        try:
            ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=True).save(path)
            return "rect=%s,%s,%s,%s" % (r.left, r.top, r.right, r.bottom)
        except Exception as e:                 # noqa: BLE001
            ImageGrab.grab(all_screens=True).save(path)
            return "rect=%s,%s,%s,%s loi cat: %r" % (r.left, r.top, r.right, r.bottom, e)
    ImageGrab.grab(all_screens=True).save(path)
    return "toan man hinh"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="", help="file JSON chứa project/bin/timeline/template/out (tránh lỗi dấu cách và tiếng Việt trên dòng lệnh)")
    ap.add_argument("--project", default="")
    ap.add_argument("--bin", default="")
    ap.add_argument("--timeline", default="")
    ap.add_argument("--template", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--data", default="")
    ap.add_argument("--size", default="", help="vd 1440x900 hoặc 1100x700: cửa sổ cỡ đó (không phóng to) để chụp so với demo")
    a = ap.parse_args()
    if a.json:
        for k, v in json.load(open(a.json, encoding="utf-8-sig")).items():
            setattr(a, k, v)
    if not (a.project and a.bin and a.out):
        ap.error("cần --project, --bin, --out (hoặc --json)")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:           # noqa: BLE001
        pass
    import troly_env
    real = json.load(open(os.path.join(HERE, "..", "config.json"), encoding="utf-8-sig"))
    tmp = a.data or tempfile.mkdtemp(prefix="troly_probe_")
    os.makedirs(os.path.join(tmp, "troly", "projects"), exist_ok=True)
    cfg = dict(real)
    cfg["data_root"] = tmp
    cfgp = os.path.join(tmp, "config_thu.json")
    json.dump(cfg, open(cfgp, "w", encoding="utf-8"), ensure_ascii=False)
    os.environ["TROLY_CONFIG"] = cfgp
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:                    # noqa: BLE001
        pass
    W, H = (int(x) for x in a.size.lower().split("x")) if a.size else (1440, 900)
    import webview
    import troly_api as ta
    os.makedirs(a.out, exist_ok=True)
    holder = {}

    def emit(kind, data):
        w = holder.get("win")
        if w is not None:
            w.evaluate_js("window.onEvent && window.onEvent(%s, %s)" % (json.dumps(kind), json.dumps(data)))

    api = ta.TrolyApi(a.project, tmp, emit=emit, proxy_root=cfg.get("proxy_root"))
    win = webview.create_window("FramePilot - thu " + a.project, url=os.path.join(APP, "troly_web", "index.html"), js_api=api,
                                width=W, height=H, min_size=(1000, 600), background_color="#18181B", maximized=True, text_select=False)
    holder["win"] = win
    log = []

    def js(code):
        return win.evaluate_js(code)

    def driver():
        time.sleep(8)
        try:
            if a.size:                           # cỡ cửa sổ để so với demo (1100 hoặc 1440): thu nhỏ từ cửa sổ phóng to
                win.restore()
                time.sleep(1.0)
                win.resize(W, H)
                win.move(30, 30)
                time.sleep(2.0)
            js("document.getElementById('binSel').value=%s;" % json.dumps(a.bin))
            if a.timeline:
                js("document.getElementById('tlSel').value=%s;" % json.dumps(a.timeline))
            js("document.getElementById('loadBtn').click()")
            for _ in range(120):
                time.sleep(1)
                if js("S && S.n && S.src && !S.src.waiting ? 1 : 0"):
                    break
            time.sleep(4)
            if a.template:
                js("document.getElementById('tplSel').value=%s; document.getElementById('suggestBtn').click()" % json.dumps(a.template))
                time.sleep(1.5)
                js("var y=document.getElementById('mYes'); if (y && !document.getElementById('modal').classList.contains('hidden')) y.click()")   # hộp xác nhận Gợi ý lại
                time.sleep(2)
            log.append("clip=%s may=%s stages=%s" % (js("S.n"), js("S.machines.length"), js("S.stages.length")))
            log.append("chup1 " + grab(os.path.join(a.out, "thuc_1_mac_dinh.png"), "FramePilot - thu " + a.project))
            # bấm clip thật (giữa lưới), rồi phím F thật
            js("(function(){var t=document.querySelectorAll('#g1 .tile');t[Math.min(t.length-1,Math.floor(t.length/2))].click();})()")
            time.sleep(0.6)
            need = "FramePilot - thu " + a.project
            hwnd = ctypes.windll.user32.FindWindowW(None, need)
            if hwnd:
                import troly_env as te
                for _ in range(5):                 # đưa cửa sổ thử lên trước (mẹo bấm Alt của troly_env), thử vài lần
                    te.bring_to_front(need)
                    time.sleep(0.8)
                    if need in fg_title():
                        break
                if need not in fg_title():         # vẫn chưa: bấm chuột THẬT vào vùng lưới trong cửa sổ để lấy tiêu điểm
                    r = ctypes.wintypes.RECT()
                    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
                    ctypes.windll.user32.SetCursorPos(int(r.left + (r.right - r.left) * 0.55), int(r.top + (r.bottom - r.top) * 0.80))
                    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
                    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
                    time.sleep(1.0)
            time.sleep(1.0)
            log.append("cua so truoc mat: " + fg_title())
            before = js("JSON.stringify(S.stages.map(function(s){return [s.head&&s.head.name,s.tail&&s.tail.name]}))")
            press(VK_F[1], need=need)                      # F1 thật = mốc ĐẦU giai đoạn 1
            after_head = js("JSON.stringify(S.stages.map(function(s){return [s.head&&s.head.name,s.tail&&s.tail.name]}))")
            msg1 = js("document.getElementById('statusText').textContent")
            js("(function(){var t=document.querySelectorAll('#g1 .tile');t[Math.min(t.length-1,Math.floor(t.length/2)+3)].click();})()")
            time.sleep(0.4)
            press(VK_F[1], shift=True, need=need)          # Shift+F1 thật = mốc CUỐI giai đoạn 1
            after_tail = js("JSON.stringify(S.stages.map(function(s){return [s.head&&s.head.name,s.tail&&s.tail.name]}))")
            msg2 = js("document.getElementById('statusText').textContent + ' | ' + document.getElementById('status').className")
            js("(function(){var t=document.querySelectorAll('#g1 .tile');t[Math.min(t.length-1,Math.floor(t.length/2)+12)].click();})()")
            time.sleep(0.4)
            press(VK_F[1], need=need)                      # mốc đầu SAU mốc cuối: phải bị chặn, báo đỏ
            msg3 = js("document.getElementById('statusText').textContent + ' | ' + document.getElementById('status').className")
            js("(function(){var t=document.querySelectorAll('#g1 .tile');t[Math.floor(t.length/2)].click();})()")
            press(VK_F[1] + 8, need=need)                  # F9: giai đoạn 9 chưa có: báo vàng
            msg4 = js("document.getElementById('statusText').textContent + ' | ' + document.getElementById('status').className")
            press(VK_ESC, need=need)
            sel_after_esc = js("selUid === null")
            log.append("chup2 " + grab(os.path.join(a.out, "thuc_2_sau_khi_bam.png"), "FramePilot - thu " + a.project))
            log.extend(["truoc=" + before, "sau F1=" + after_head, "msg F1=" + msg1, "sau Shift+F1=" + after_tail, "msg Shift+F1=" + msg2,
                        "dau SAU cuoi=" + msg3, "F9 chua co=" + msg4, "Esc bo chon=" + str(sel_after_esc)])
        except Exception as e:                  # noqa: BLE001
            log.append("LOI: %r" % (e,))
        open(os.path.join(a.out, "thuc_log.txt"), "w", encoding="utf-8").write("\n".join(log))
        time.sleep(1)
        win.destroy()

    win.events.shown += lambda: threading.Thread(target=driver, daemon=True).start()
    win.events.closed += lambda: api.close()
    webview.start(gui="edgechromium")
    shutil.rmtree(tmp, ignore_errors=True) if not a.data else None
    print("\n".join(log))


if __name__ == "__main__":
    main()
