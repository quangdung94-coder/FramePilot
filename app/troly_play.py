"""
troly_play.py - Máy chủ phát video proxy cục bộ cho khung xem trước (ADR-0016).

- Chỉ nghe 127.0.0.1, cổng ngẫu nhiên. Hỗ trợ Range (kéo thanh thời gian để lướt).
- Chỉ ĐỌC file. Mỗi clip có một "vé" (token ngẫu nhiên) -> đường dẫn; chỉ phát đường dẫn nằm TRONG các thư mục cho phép
  (proxy_root trong config.json, và thư mục cache troly_play). Đường dẫn ngoài thư mục (kể cả dùng .. hay liên kết) bị từ chối.
- Không ghi, đổi tên hay xóa file nào.
"""
import http.server
import mimetypes
import os
import re
import secrets
import socketserver
import threading
import subprocess

CHUNK = 256 * 1024


def inside(path, roots):
    """True nếu path (đã giải liên kết, chuẩn hóa) nằm trong một trong các thư mục roots."""
    if not path or not roots:
        return False
    try:
        p = os.path.normcase(os.path.realpath(path))
        for r in roots:
            if not r:
                continue
            rr = os.path.normcase(os.path.realpath(r))
            if p == rr or p.startswith(rr.rstrip("\\/") + os.sep):
                return True
    except (OSError, ValueError):
        return False
    return False


def parse_range(header, size):
    """'bytes=a-b' -> (a, b) gồm cả hai đầu; None nếu không có/không hợp lệ; 'bad' nếu ngoài file."""
    if not header:
        return None
    m = re.match(r"^bytes=(\d*)-(\d*)$", header.strip())
    if not m or (m.group(1) == "" and m.group(2) == ""):
        return None
    if m.group(1) == "":                               # bytes=-N : N byte cuối
        n = int(m.group(2))
        a, b = max(0, size - n), size - 1
    else:
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else size - 1
        b = min(b, size - 1)
    if a >= size or a > b:
        return "bad"
    return a, b


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class PlayServer(object):
    def __init__(self, allowed_roots):
        self.roots = [r for r in allowed_roots if r]
        self._tokens = {}
        self._lock = threading.Lock()
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):                  # không in log ra màn hình
                pass

            def do_GET(self):
                outer._serve(self, True)

            def do_HEAD(self):
                outer._serve(self, False)

        self._srv = _Server(("127.0.0.1", 0), H)
        self.port = self._srv.server_address[1]
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    def close(self):
        try:
            self._srv.shutdown()
            self._srv.server_close()
        except Exception:                               # noqa: BLE001
            pass

    def url_for(self, path):
        """Cấp vé cho path. Trả URL hoặc None nếu path không nằm trong thư mục cho phép / không có file."""
        if not path or not os.path.isfile(path) or not inside(path, self.roots):
            return None
        tok = secrets.token_urlsafe(16)
        with self._lock:
            self._tokens[tok] = path
        return "http://127.0.0.1:%d/v/%s" % (self.port, tok)

    def _serve(self, h, body):
        m = re.match(r"^/v/([A-Za-z0-9_\-]+)$", h.path.split("?")[0])
        with self._lock:
            path = self._tokens.get(m.group(1)) if m else None
        if not path or not inside(path, self.roots):     # kiểm lại lúc phát, phòng liên kết bị đổi
            h.send_error(403)
            return
        try:
            size = os.path.getsize(path)
        except OSError:
            h.send_error(404)
            return
        rng = parse_range(h.headers.get("Range"), size)
        if rng == "bad":
            h.send_response(416)
            h.send_header("Content-Range", "bytes */%d" % size)
            h.end_headers()
            return
        a, b = rng if rng else (0, size - 1)
        h.send_response(206 if rng else 200)
        h.send_header("Content-Type", mimetypes.guess_type(path)[0] or "video/mp4")
        h.send_header("Accept-Ranges", "bytes")
        h.send_header("Content-Length", str(b - a + 1 if size else 0))
        if rng:
            h.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, size))
        h.end_headers()
        if not body or not size:
            return
        try:
            with open(path, "rb") as f:                  # chỉ mở để ĐỌC
                f.seek(a)
                left = b - a + 1
                while left > 0:
                    buf = f.read(min(CHUNK, left))
                    if not buf:
                        break
                    h.wfile.write(buf)
                    left -= len(buf)
        except (OSError, ConnectionError):
            pass


def transcode_cmd(src, dst, ffmpeg="ffmpeg"):
    """Phương án dự phòng: mp4 H.264 nhẹ (720p, keyframe dày để lướt mượt, âm thanh AAC), chỉ cho clip đang xem.
    Phải có -f mp4: file tạm đuôi .part khiến ffmpeg không chọn được định dạng (đo 18/11/2026: lệnh cũ lỗi ngay, trả None)."""
    return [ffmpeg, "-y", "-v", "error", "-i", src, "-vf", "scale=-2:720", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "28", "-g", "12", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-f", "mp4", dst]


def ensure_play_mp4(src, cache_dir, key, ffmpeg="ffmpeg", timeout=600):
    """Tạo (nếu chưa có) mp4 nhẹ trong cache_dir cho clip. Trả đường dẫn hoặc None nếu ffmpeg lỗi. Chỉ ĐỌC src."""
    os.makedirs(cache_dir, exist_ok=True)
    dst = os.path.join(cache_dir, re.sub(r"[^\w\-.]", "_", key) + ".mp4")
    if os.path.isfile(dst) and os.path.getsize(dst) > 0:
        return dst
    tmp = dst + ".part"
    try:
        subprocess.run(transcode_cmd(src, tmp, ffmpeg), check=True, timeout=timeout,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.replace(tmp, dst)
        return dst
    except (OSError, subprocess.SubprocessError):
        try:
            os.remove(tmp)
        except OSError:
            pass
        return None
