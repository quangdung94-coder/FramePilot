r"""harness_cam.py - chạy giao diện FramePilot trong TRÌNH DUYỆT với DaVinci GIẢ (dữ liệu tự tạo, thư mục tạm), để xem/chụp trang nhiều camera.

Không đụng DaVinci, không đụng dữ liệu thật. Cách dùng:
  & $py tools\harness_cam.py --cams 4 --port 8765     rồi mở http://127.0.0.1:8765/
  --cams 1|3|4: số máy giả. --real "<tên project>": nối DaVinci thật (chỉ đọc).
"""
import argparse
import json
import os
import random
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, os.path.join(HERE, "..", "tests"))
import test_troly as T       # noqa: E402
import troly_api as ta       # noqa: E402

WEB = os.path.join(HERE, "..", "app", "troly_web")
PATH = "Master/01_footage/01_SELECTED"
MONTH = {10: "Oct", 11: "Nov"}

# (tên file mẫu, model, seri, sai số đồng hồ giây, giờ bắt đầu, giờ kết thúc, số clip, có metadata)
CAMS = [
    ("DG%04d.MP4", "Sony ILME-FX3", "4102", 0, (7, 31), (11, 26), 142, True),
    ("C%04d.MP4", "Sony ILCE-7SM3", "7718", -134, (7, 31), (11, 26), 148, True),
    ("A001_%04d.MP4", "Sony ILCE-7M4", "2205", -(3600 + 12 * 60 + 14), (9, 12), (11, 28), 86, True),
    ("D%04d.MP4", "", "", 45, (9, 31), (11, 5), 40, False),
]


def pool_for(ncams):
    rnd = random.Random(7)
    clips = []
    for ci, (pat, model, sn, err, a, b, n, meta) in enumerate(CAMS[:ncams]):
        t0, t1 = a[0] * 3600 + a[1] * 60, b[0] * 3600 + b[1] * 60
        for i in range(n):
            t = t0 + (t1 - t0) * i / n + rnd.random() * 8 + err
            dur = 10 + rnd.random() * 40
            h, m, s = int(t // 3600), int(t % 3600 // 60), int(t % 60)
            e = int(t + dur)
            p = T.props(pat % (1000 * (ci + 1) + i), "Sat Oct 17 2026 %02d:%02d:%02d" % (h, m, s),
                        "Sat Oct 17 %02d:%02d:%02d 2026" % (e // 3600, e % 3600 // 60, e % 60), int(dur * 25), fps=25.0, Type="Video + Audio")
            if meta:
                p["Camera Type"], p["Camera Serial #"] = model, sn
            clips.append(T.FItem("c%d_%d" % (ci, i), p))
    sel = T.FFolder("01_SELECTED", clips)
    foot = T.FFolder("01_footage")
    foot.subs.append(sel)
    root = T.FFolder("Master")
    root.subs.append(foot)
    return T.FPool(root)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:            # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--cams", type=int, default=4)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--real", default="", help="tên project đang mở trong DaVinci THẬT (chỉ ĐỌC; dữ liệu kế hoạch ghi vào thư mục tạm, không đụng dữ liệu thật)")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    events, lock = [], threading.Lock()

    def emit(kind, data):
        with lock:
            events.append([kind, data])

    if a.real:
        name = a.real
        api = ta.TrolyApi(name, tmp, emit=emit, start_worker=True)
    else:
        pool = pool_for(a.cams)
        name = "2026.10.17.LV_Mau"
        api = ta.TrolyApi(name, tmp, emit=emit, resolve_factory=lambda: T.FResolve(T.FProject(name, pool)), start_worker=True)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *x):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            p = self.path.split("?")[0]
            if p == "/events":
                if a.real:
                    time.sleep(0.15)                  # DaVinci thật đọc chậm: mỗi lần hỏi sự kiện chờ một chút để chụp ảnh bằng giờ ảo không bỏ lỡ
                with lock:
                    out = events[:]
                    del events[:]
                return self._send(200, json.dumps(out).encode("utf-8"), "application/json")
            if p == "/":
                p = "/index.html"
            f = os.path.normpath(os.path.join(WEB, p.lstrip("/")))
            if not f.startswith(os.path.normpath(WEB)) or not os.path.isfile(f):
                return self._send(404, b"", "text/plain")
            body = open(f, "rb").read()
            if p == "/index.html":
                shim = ("<script>window.pywebview={api:new Proxy({}, {get:(_,m)=>(...a)=>fetch('/rpc',{method:'POST',body:JSON.stringify({m,a})}).then(r=>r.json())})};"
                        "window.addEventListener('DOMContentLoaded',()=>{setTimeout(()=>window.dispatchEvent(new Event('pywebviewready')),50);"
                        "const H=location.hash;const D=(id,ms)=>setTimeout(()=>{const e=document.getElementById(id);e&&e.click()},ms);const Q=k=>{const m=decodeURIComponent(H).match(new RegExp(k+'=([^&]*)'));return m?m[1]:null};if(H.includes('load'))setTimeout(()=>{const b=Q('bin'),t=Q('tl');if(b)document.getElementById('binSel').value=b;if(t)document.getElementById('tlSel').value=t;document.getElementById('loadBtn').click()},3000);if(Q('cur')){let d2=0;setInterval(()=>{if(!d2&&typeof S!=='undefined'&&S&&S.n&&S.src&&!S.src.waiting&&S.src.timeline===(Q('tl')||'')&&S.stages.some(x=>x.count>0)){d2=1;cursorM=+Q('cur');fitView();renderPage1()}},500)}if(Q('tpl')){let done=0;setInterval(()=>{if(!done&&typeof S!=='undefined'&&S&&S.n&&S.src&&!S.src.waiting&&S.stages.length===0&&S.src.timeline===(Q('tl')||'')){done=1;document.getElementById('tplSel').value=Q('tpl');document.getElementById('suggestBtn').click()}},500)}if(H.includes('moment')){D('lkR',6000);D('lkX',6200)}if(H.includes('apply'))D('applyBtn',7200);setInterval(()=>fetch('/events').then(r=>r.json()).then(l=>l.forEach(([k,d])=>window.onEvent&&window.onEvent(k,d))),300);});</script>").encode("utf-8")
                body = body.replace(b"</head>", shim + b"</head>")
            ct = {"html": "text/html", "js": "text/javascript", "css": "text/css"}.get(p.rsplit(".", 1)[-1], "application/octet-stream")
            self._send(200, body, ct + "; charset=utf-8")

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
            try:
                r = getattr(api, req["m"])(*req.get("a", []))
            except Exception as e:           # noqa: BLE001
                r = {"error": "%s: %s" % (type(e).__name__, e)}
            self._send(200, json.dumps(r, default=str).encode("utf-8"), "application/json")

    print("Mở http://127.0.0.1:%d/  (%d máy giả, dữ liệu tạm %s)" % (a.port, a.cams, tmp))
    try:
        ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
    finally:
        api.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

