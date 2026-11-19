"""
troly_frames.py - "Kho khung nhỏ trong RAM" để RÊ CHUỘT xem trước mượt (ADR-0016 bản 2, mục G2-G5).

Vì sao: thẻ <video> chỉ nhảy rẻ khi đáp xuống keyframe; trong WebView2 thật mỗi lần nhảy mất cả trăm mili giây đến hơn một giây, nên rê chuột hình
chỉ đổi vài lần mỗi giây (đo trong pywebview thật, ADR-0016 bản 2). Cách chuẩn của các trình dựng: giải mã sẵn khung vào bộ nhớ rồi vẽ từ đó khi rê.

Cách làm:
- Khi mở clip, MỘT tiến trình ffmpeg (ưu tiên thấp) đọc proxy (chỉ ĐỌC) ra khung nhỏ (cạnh dài 640 px, mỗi 2 hình một khung với proxy 50p = 25 khung/giây;
  clip dài hơn 120 giây thì thưa gấp đôi), nén JPEG, GIỮ TRONG RAM. KHÔNG ghi file ra đĩa, KHÔNG tạo proxy hay bản nhẹ mới. Áp LUT của clip ngay lúc
  giải mã (cùng cách làm thumbnail) để màu khớp khung video. Giải mã tiến dần từ đầu; hủy được; bị hủy giữa chừng thì lần sau làm tiếp từ chỗ đã có.
- Giữ tối đa MAX_CLIPS clip gần nhất (LRU), tổng không quá MAX_BYTES. Chỉ MỘT việc giải mã chạy một lúc: mở clip đang xem thì hủy việc nạp trước.
- Khung được phát qua máy chủ phát cục bộ (troly_play.PlayServer) ở /f/<vé>/<chỉ số>, vé ngẫu nhiên; không mở thêm thư mục.
"""
import collections
import hashlib
import os
import re
import shutil
import subprocess
import troly_proc
import threading
import time

MAX_CLIPS = 8                       # số clip giữ trong RAM (chỉnh được)
MAX_BYTES = 300 * 1024 * 1024       # tổng RAM tối đa cho khung (chỉnh được)
WIDTH = 640
LONG_CLIP_S = 120.0                 # clip dài hơn thì thưa khung gấp đôi để khỏi vượt RAM
TARGET_FPS = 25.0
JPEG_Q = 6                          # mjpeg -q:v (2 = đẹp nhất, 31 = tệ nhất)
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) | 0x00004000     # + BELOW_NORMAL_PRIORITY_CLASS: không tranh CPU với trình phát
SOI = b"\xff\xd8\xff"


def plan_step(fps, dur):
    """Lấy một khung trong mỗi `step` hình gốc: ~25 khung/giây, thưa gấp đôi với clip dài."""
    fps = float(fps or 25.0)
    step = max(1, int(round(fps / TARGET_FPS)))
    if dur and dur > LONG_CLIP_S:
        step *= 2
    return step


def build_cmd(ffmpeg, src, step, start_t=0.0, lut_name=None, width=WIDTH):
    vf = "select=not(mod(n\\,%d)),scale=%d:%d:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=fast_bilinear" % (step, width, width)
    if lut_name:
        vf += ",format=rgb48le,lut3d=file=%s,format=yuvj420p" % lut_name
    else:
        vf += ",format=yuvj420p"
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin"]
    if start_t > 0:
        cmd += ["-ss", "%.3f" % start_t]
    return cmd + ["-i", src, "-an", "-vf", vf, "-fps_mode", "passthrough", "-f", "image2pipe", "-c:v", "mjpeg", "-q:v", str(JPEG_Q), "-"]


def split_jpegs(buf, final=False):
    """Tách các JPEG liền nhau trong buf (bắt đầu bằng FFD8FF; dữ liệu nén không bao giờ chứa FFD8FF vì FF luôn được độn 00).
    Trả (danh sách khung hoàn chỉnh, phần dư). final=True: phần dư cuối cùng cũng là một khung."""
    out = []
    start = buf.find(SOI)
    if start < 0:
        return out, b""
    while True:
        nxt = buf.find(SOI, start + 3)
        if nxt < 0:
            break
        out.append(bytes(buf[start:nxt]))
        start = nxt
    rest = bytes(buf[start:])
    if final and rest:
        out.append(rest)
        rest = b""
    return out, rest


class _Clip(object):
    def __init__(self, key, src, fps, dur, step, lut_name):
        self.key, self.src, self.fps, self.dur, self.step, self.lut_name = key, src, fps, dur, step, lut_name
        self.frames = []
        self.bytes = 0
        self.done = False
        self.failed = ""
        self.token = None
        self.t_load = 0.0           # giây đã mất để nạp (đo)

    @property
    def out_fps(self):
        return (self.fps or 25.0) / self.step

    @property
    def total(self):
        return max(1, int(round((self.dur or 0) * self.out_fps))) if self.dur else 0


class FrameStore(object):
    def __init__(self, cache_dir, ffmpeg=None, max_clips=MAX_CLIPS, max_bytes=MAX_BYTES, lut_copy=None):
        self.cache_dir = cache_dir
        self.ffmpeg = ffmpeg or shutil.which("ffmpeg") or "ffmpeg"
        self.max_clips, self.max_bytes = max_clips, max_bytes
        self.lut_copy = lut_copy                      # hàm (đường dẫn LUT, thư mục cache) -> tên file ngắn (troly_thumbs.local_lut)
        self._clips = collections.OrderedDict()       # key -> _Clip (cuối = mới dùng nhất)
        self._tokens = {}
        self._lock = threading.RLock()
        self._run = None                              # (key, Popen, cờ hủy) việc giải mã đang chạy; chỉ một
        self._closed = False

    # ---------------------------------------------------------------- mở / nạp
    def open(self, key, src, fps, dur, lut_path=None, prefetch=False):
        """Mở (hoặc lấy lại) kho khung của một clip và bắt đầu nạp nếu chưa đủ. Trả thông tin để giao diện lấy khung, hoặc {'error': ...}.
        prefetch=True: chỉ nạp khi KHÔNG có việc giải mã nào đang chạy (không tranh với clip đang xem)."""
        if not src or not os.path.isfile(src):
            return {"error": "Chưa có proxy"}
        with self._lock:
            c = self._clips.get(key)
            if c is not None and c.src == src:
                self._clips.move_to_end(key)
            else:
                step = plan_step(fps, dur)
                lut_name = None
                if lut_path and self.lut_copy:
                    try:
                        lut_name = self.lut_copy(lut_path, self.cache_dir)
                    except OSError:
                        lut_name = None
                c = _Clip(key, src, fps, dur, step, lut_name)
                c.token = hashlib.sha1((key + str(time.time())).encode("utf-8")).hexdigest()[:24]
                self._clips[key] = c
                self._tokens[c.token] = key
                self._evict(keep=key)
            if not c.done and not c.failed:
                running = self._run
                if running is None or running[0] != key:
                    if prefetch and running is not None:
                        return self.info(key)                # đang bận clip khác: chưa nạp trước
                    self._cancel_running()
                    self._start(c)
            return self.info(key)

    def _cancel_running(self):
        if self._run is not None:
            _k, p, flag = self._run
            flag.set()
            try:
                p.kill()
            except OSError:
                pass
            self._run = None

    def _start(self, c):
        if not os.path.isdir(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
        start_t = (len(c.frames) * c.step / (c.fps or 25.0)) if c.frames else 0.0
        cmd = build_cmd(self.ffmpeg, c.src, c.step, start_t, c.lut_name)
        try:
            p = troly_proc.mo_an(cmd, cwd=self.cache_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, creationflags=FLAGS)
        except OSError as e:
            c.failed = "ffmpeg không chạy được: %s" % e
            return
        flag = threading.Event()
        self._run = (c.key, p, flag)
        threading.Thread(target=self._pump, args=(c, p, flag), daemon=True).start()

    def _pump(self, c, p, flag):
        t0 = time.time()
        buf = b""
        errbuf = []
        threading.Thread(target=lambda: errbuf.append(p.stderr.read()), daemon=True).start()
        try:
            while not flag.is_set():
                chunk = p.stdout.read1(1 << 18)                  # trả ngay phần đã có, không chờ đầy 256 KB
                if not chunk:
                    break
                buf += chunk
                frames, buf = split_jpegs(buf)
                if frames:
                    with self._lock:
                        if flag.is_set():
                            break
                        for f in frames:
                            c.frames.append(f)
                            c.bytes += len(f)
                        self._evict(keep=c.key)
                        if c.bytes > self.max_bytes // 2:         # một clip không được chiếm quá nửa kho: dừng nạp (còn phần đã có)
                            flag.set()
                            c.done = True
                            break
            if not flag.is_set():
                frames, _rest = split_jpegs(buf, final=True)
                with self._lock:
                    for f in frames:
                        c.frames.append(f)
                        c.bytes += len(f)
                rc = p.wait()
                with self._lock:
                    if rc == 0 and c.frames:
                        c.done = True
                    elif not c.frames:
                        err = (errbuf[0] if errbuf else b"").decode("utf-8", "replace").strip().splitlines()
                        c.failed = "ffmpeg lỗi: " + (err[-1] if err else "không rõ")
        finally:
            try:
                p.kill()
                p.wait(timeout=5)                          # thu dọn tiến trình đã dừng
            except (OSError, subprocess.TimeoutExpired):
                pass
            c.t_load += time.time() - t0
            with self._lock:
                if self._run is not None and self._run[1] is p:
                    self._run = None

    def _evict(self, keep=None):
        """Bỏ clip cũ nhất (không phải keep) khi vượt số clip hoặc tổng RAM."""
        while True:
            total = sum(c.bytes for c in self._clips.values())
            if len(self._clips) <= self.max_clips and total <= self.max_bytes:
                return
            victim = next((k for k in self._clips if k != keep), None)
            if victim is None:
                return
            if self._run is not None and self._run[0] == victim:
                self._cancel_running()
            c = self._clips.pop(victim)
            self._tokens.pop(c.token, None)

    # ---------------------------------------------------------------- hỏi / lấy
    def info(self, key):
        with self._lock:
            c = self._clips.get(key)
            if c is None:
                return {"error": "Chưa mở"}
            return {"token": c.token, "n": len(c.frames), "total": c.total, "fps": round(c.out_fps, 4), "done": c.done, "error": c.failed or None,
                    "bytes": c.bytes, "load_s": round(c.t_load, 2), "step": c.step}

    def info_by_token(self, tok):
        with self._lock:
            k = self._tokens.get(tok)
            return self.info(k) if k else None

    def frame(self, tok, idx):
        with self._lock:
            k = self._tokens.get(tok)
            c = self._clips.get(k) if k else None
            if c is None or idx < 0 or idx >= len(c.frames):
                return None
            return c.frames[idx]

    def stats(self):
        with self._lock:
            return {"clips": len(self._clips), "bytes": sum(c.bytes for c in self._clips.values()), "max_clips": self.max_clips, "max_bytes": self.max_bytes,
                    "running": self._run[0] if self._run else None}

    def close(self):
        with self._lock:
            self._closed = True
            self._cancel_running()
            self._clips.clear()
            self._tokens.clear()


_TOK = re.compile(r"^/f/([0-9a-f]{24})/(info|\d+)$")


def parse_path(path):
    """'/f/<vé>/<n>' hoặc '/f/<vé>/info' -> (vé, 'info' | int) hoặc None."""
    m = _TOK.match(path.split("?")[0])
    if not m:
        return None
    return m.group(1), (m.group(2) if m.group(2) == "info" else int(m.group(2)))
