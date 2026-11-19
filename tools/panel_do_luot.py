r"""
panel_do_luot.py - Đo độ mượt khi RÊ CHUỘT xem trước TRONG CỬA SỔ PYWEBVIEW THẬT (WebView2), không đọc/ghi project thật.

Mở đúng giao diện của panel (index.html + TrolyApi thật) nhưng với DaVinci GIẢ (dữ liệu giả LV_Ten, dữ liệu tạm trong thư mục tạm), mỗi clip
trỏ tới một file proxy THẬT trong proxy_root (chỉ ĐỌC, không tạo file proxy/bản nhẹ nào). Sau khi trình phát mở xong, chạy một file JS đo
(mặc định tools/measure_seek.js) rồi lưu kết quả JSON và đóng cửa sổ.

  & $py tools\panel_do_luot.py --out kq.json [--app <thư mục app khác để so A/B>] [--js file.js] [--flags "--ignore-gpu-blocklist"]
        [--proxy-dir "<thư mục chứa proxy .mov>"] [--clips 6]
"""
import argparse
import json
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=os.path.join(ROOT, "app"), help="thư mục app\\ cần đo (mặc định bản hiện tại; trỏ sang worktree commit cũ để A/B)")
    ap.add_argument("--js", default=os.path.join(ROOT, "tools", "measure_seek.js"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--flags", default="", help="cờ thêm cho WebView2 (WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS)")
    ap.add_argument("--proxy-dir", default=None)
    ap.add_argument("--clips", type=int, default=6)
    ap.add_argument("--lut", default="", help="tên LUT gán cho clip giả (ví dụ \"Blackmagic Design\\Blackmagic 4.6K Film to Rec709 v3\"), để đo cả lớp màu Log")
    ap.add_argument("--wait", type=int, default=240)
    ap.add_argument("--mode", default="", help="chuỗi gửi cho JS đo (window.MEASURE_MODE), ví dụ lut_off")
    a = ap.parse_args()
    if a.flags:
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = a.flags
    app = os.path.abspath(a.app)
    sys.path.insert(0, app)
    sys.path.insert(1, os.path.join(ROOT, "tests"))
    import webview
    import test_troly as T
    import troly_api as ta
    import troly_core as tc

    proxy_root = None
    try:
        import json as _j
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8-sig") as f:
            proxy_root = _j.load(f).get("proxy_root")
    except OSError:
        pass
    pdir = a.proxy_dir
    if not pdir:                                      # tự tìm thư mục đầu tiên trong proxy_root có proxy .mov đủ lớn (không ghi tên project nào vào mã)
        for dp, _dn, fn in os.walk(proxy_root or ""):
            if any(f.lower().endswith(".mov") and os.path.getsize(os.path.join(dp, f)) > 60 * 1024 * 1024 for f in fn):
                pdir = dp
                break
    if not pdir:
        sys.exit("Không thấy proxy .mov nào đủ lớn trong proxy_root; dùng --proxy-dir")
    files = sorted(f for f in os.listdir(pdir) if f.lower().endswith(".mov") and os.path.getsize(os.path.join(pdir, f)) > 60 * 1024 * 1024)[:a.clips]
    if not files:
        sys.exit("Không thấy proxy .mov đủ lớn trong " + pdir)

    tmp = tempfile.mkdtemp()
    name = "2026.10.17.LV_Ten"

    def mk(i):
        p = T.props("DG%02d.MP4" % i, "Sat Oct 17 2026 %02d:%02d:00" % (8 + i // 6, (i % 6) * 10), "Sat Oct 17 %02d:%02d:20 2026" % (8 + i // 6, (i % 6) * 10), 4176, Type="Video + Audio")
        p["Proxy Media Path"] = os.path.join(pdir, files[i % len(files)])
        p["Input LUT"] = a.lut
        return T.FItem("u%02d" % i, p)
    sel = T.FFolder("01_SELECTED", [mk(i) for i in range(len(files))])
    foot = T.FFolder("01_footage")
    foot.subs.append(sel)
    rootf = T.FFolder("Master")
    rootf.subs.append(foot)
    pool = T.FPool(rootf)
    holder = {}

    def emit(kind, data):
        w = holder.get("win")
        if w is not None:
            try:
                w.evaluate_js("window.onEvent && window.onEvent(%s, %s)" % (json.dumps(kind), json.dumps(data)))
            except Exception:                    # noqa: BLE001
                pass
    api = ta.TrolyApi(name, tmp, emit=emit, resolve_factory=lambda: T.FResolve(T.FProject(name, pool)), proxy_root=proxy_root)
    api.debug = True
    time.sleep(0.3)
    api._worker.connect()
    api.init()
    time.sleep(0.8)
    api.load("Master/01_footage/01_SELECTED")
    time.sleep(1.2)
    api._plan["stages"] = [{"name": "Đón khách", "start": 0.0, "end": 100000.0, "color": "#F2A33A", "bins": ["Đi bàn", "Khác"]}]
    api._plan["offsets"] = {}
    api.state()
    uids = [c["uid"] for c in api.state()["clips"]]
    api.toggle_star(uids)
    index = os.path.join(app, "troly_web", "index.html")
    win = webview.create_window("Đo lướt (DaVinci giả)", url=index, js_api=api, width=1440, height=900, background_color="#18181B")
    holder["win"] = win
    js = open(a.js, encoding="utf-8").read()
    result = {}

    def poll(expr, timeout):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                v = win.evaluate_js(expr)
                if v:
                    return v
            except Exception:                    # noqa: BLE001
                pass
            time.sleep(0.5)
        return None

    def drive():
        try:
            if not poll("typeof S !== 'undefined' && S && S.n", 60):
                result["error"] = "giao diện không nạp được clip"
                return
            win.evaluate_js("goPage(3)")
            if not poll("typeof PL !== 'undefined' && PL.ok", 60):
                result["error"] = "trình phát không mở được proxy"
                return
            time.sleep(1.5)
            win.evaluate_js("window.MEASURE_MODE = %s; window.__res = null; %s\n;(async () => { try { window.__res = JSON.stringify(await measureAll()); } catch (e) { window.__res = JSON.stringify({error: String(e && e.stack || e)}); } })()" % (json.dumps(a.mode), js))
            r = poll("window.__res", a.wait)
            result.update(json.loads(r) if r else {"error": "hết giờ chờ kết quả"})
            result["_cua_so"] = "pywebview (WebView2)"
            result["_app"] = app
            result["_flags"] = a.flags
            result["_proxy"] = files[0]
        except Exception as e:                   # noqa: BLE001
            result["error"] = "lỗi chạy đo: %s" % e
        finally:
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=1)
            try:
                win.destroy()
            except Exception:                    # noqa: BLE001
                pass
    threading.Thread(target=drive, daemon=True).start()
    webview.start(gui="edgechromium")
    api.close()
    print("xong ->", a.out)


if __name__ == "__main__":
    main()
