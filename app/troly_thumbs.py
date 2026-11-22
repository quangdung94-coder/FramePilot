"""
troly_thumbs.py - Ảnh thumbnail cho Trợ lý File Quay (ADR-0009). KHÔNG gọi DaVinci.

- Ưu tiên PROXY (nhẹ, 1080p) nếu clip đã có proxy và file proxy còn trên ổ; không có mới đọc file gốc.
- Áp LUT mà người dựng đã gắn cho clip trong Media Pool (thuộc tính "Input LUT", ví dụ
  'Sony\\SLog3SGamut3.CineToLC-709TypeA'), để thumbnail có màu giống lúc xem trong DaVinci thay vì màu Log xám.
  Proxy của DaVinci không "nướng" LUT vào hình nên phải áp LUT cả khi đọc proxy (đo 15/11/2026).
- Cắt một khung hình bằng ffmpeg (đã cài sẵn trên máy dựng), thu nhỏ trước rồi mới áp LUT (nhanh hơn).
- Kết quả lưu ở <data_root>/cache/troly_thumbs/<project>/<mã>.jpg; mã gồm đường dẫn, cỡ, giờ sửa file, LUT, vị trí,
  nên đổi LUT trong DaVinci là thumbnail tự làm lại, không đổi thì lần sau mở ngay.

Đường dẫn LUT trong bộ lọc ffmpeg rất khó viết đúng trên Windows (dấu ':' và '\\'), nên file LUT được CHÉP vào thư mục
cache với tên ngắn và ffmpeg chạy ngay trong thư mục đó, chỉ cần ghi tên file.
"""
import concurrent.futures as cf
import hashlib
import os
import shutil
import subprocess
import sys
import troly_proc

FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LUT_EXTS = ("", ".cube", ".3dl", ".dat", ".csp", ".m3d")
DEFAULT_WIDTH = 320
DEFAULT_POS = 0.4          # lấy khung ở 40% độ dài clip (đầu clip hay rung, cuối clip hay hạ máy)


def lut_dirs(extra=None):
    """Các thư mục LUT của DaVinci trên Windows & macOS (hệ thống + người dùng), cộng thư mục ghi thêm trong config."""
    out = list(extra or [])
    if sys.platform == "darwin":
        out.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT")
        out.append(os.path.expanduser("~/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT"))
        return out
    pd = os.environ.get("PROGRAMDATA") or r"C:\ProgramData"
    out.append(os.path.join(pd, "Blackmagic Design", "DaVinci Resolve", "Support", "LUT"))
    ad = os.environ.get("APPDATA")
    if ad:
        out.append(os.path.join(ad, "Blackmagic Design", "DaVinci Resolve", "Support", "LUT"))
    return out


def find_lut(name, dirs):
    """'Sony\\SLog3SGamut3.CineToLC-709TypeA' -> đường dẫn file .cube thật, không thấy thì None.
    Nhận cả tên đã là đường dẫn đầy đủ."""
    if not name:
        return None
    rel = name.replace("/", os.sep).replace("\\", os.sep)
    cands = [rel] if os.path.isabs(rel) else [os.path.join(d, rel) for d in dirs]
    for base in cands:
        for ext in LUT_EXTS:
            p = base + ext
            if os.path.isfile(p):
                return p
    return None


def pick_source(path, proxy):
    """(file sẽ đọc, 'proxy'|'goc'|None). Proxy chỉ dùng khi file còn trên ổ."""
    if proxy and os.path.isfile(proxy):
        return proxy, "proxy"
    if path and os.path.isfile(path):
        return path, "goc"
    return None, None


def cache_key(src, lut_path, pos, width):
    try:
        st = os.stat(src)
        sig = "%s|%d|%d" % (src, st.st_size, int(st.st_mtime))
    except OSError:
        sig = src
    if lut_path:
        try:
            sig += "|%s|%d" % (lut_path, int(os.stat(lut_path).st_mtime))
        except OSError:
            sig += "|" + lut_path
    sig += "|%.3f|%d" % (pos, width)
    return hashlib.sha1(sig.encode("utf-8")).hexdigest()[:20]


def local_lut(lut_path, cache_dir):
    """Chép LUT vào cache với tên không dấu, không khoảng trắng; trả về TÊN file (dùng làm đối số ffmpeg)."""
    if not lut_path:
        return None
    ext = os.path.splitext(lut_path)[1] or ".cube"
    name = "lut_" + hashlib.sha1(lut_path.encode("utf-8")).hexdigest()[:12] + ext
    dst = os.path.join(cache_dir, name)
    try:
        if not os.path.isfile(dst) or os.path.getmtime(dst) < os.path.getmtime(lut_path):
            shutil.copyfile(lut_path, dst + ".tmp")
            os.replace(dst + ".tmp", dst)
    except OSError:
        return None
    return name


def ffmpeg_cmd(ffmpeg, src, t, out_name, lut_name=None, width=DEFAULT_WIDTH):
    vf = "scale=%d:-2:flags=bilinear" % width
    if lut_name:
        vf += ",format=rgb48le,lut3d=file=%s,format=yuvj420p" % lut_name
    else:
        vf += ",format=yuvj420p"
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-ss", "%.3f" % max(0.0, t), "-i", src,
            "-frames:v", "1", "-an", "-vf", vf, "-q:v", "4", out_name]


class ThumbMaker(object):
    """Làm thumbnail song song (mặc định 4 luồng ffmpeg). Mỗi việc trả (uid, đường dẫn jpg | None, ghi chú)."""

    def __init__(self, cache_dir, ffmpeg=None, workers=4, width=DEFAULT_WIDTH, pos=DEFAULT_POS, lut_dirs_extra=None,
                 use_lut=True):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.ffmpeg = ffmpeg or shutil.which("ffmpeg") or "ffmpeg"
        self.width, self.pos, self.use_lut = width, pos, use_lut
        self.dirs = lut_dirs(lut_dirs_extra)
        self.pool = cf.ThreadPoolExecutor(max_workers=max(1, workers))
        self._lut_cache = {}

    @property
    def root(self):
        return self.cache_dir

    @root.setter
    def root(self, v):
        self.cache_dir = v

    def lut_for(self, lut_name):
        if not self.use_lut or not lut_name:
            return None
        if lut_name not in self._lut_cache:
            self._lut_cache[lut_name] = find_lut(lut_name, self.dirs)
        return self._lut_cache[lut_name]

    def make(self, uid, path, proxy, lut_name, dur, width=None):
        """Làm (hoặc lấy từ cache) thumbnail của một clip. Chạy được ở luồng nào cũng được."""
        width = width or self.width
        src, kind = pick_source(path, proxy)
        if not src:
            return uid, None, "không thấy file gốc lẫn proxy"
        lut_path = self.lut_for(lut_name)
        key = cache_key(src, lut_path, self.pos, width)
        out = os.path.join(self.cache_dir, key + ".jpg")
        note = kind + (" + LUT" if lut_path else (" (không thấy file LUT)" if lut_name and self.use_lut else ""))
        if os.path.isfile(out) and os.path.getsize(out) > 0:
            return uid, out, note
        lut_local = local_lut(lut_path, self.cache_dir) if lut_path else None
        t = (dur or 0) * self.pos
        tmp = key + ".tmp.jpg"
        cmd = ffmpeg_cmd(self.ffmpeg, src, t, tmp, lut_local, width)
        try:
            r = troly_proc.chay_an(cmd, cwd=self.cache_dir, capture_output=True, timeout=60, creationflags=FLAGS)
        except (OSError, subprocess.TimeoutExpired) as e:
            return uid, None, "ffmpeg lỗi: %s" % e
        tmp_full = os.path.join(self.cache_dir, tmp)
        if r.returncode != 0 or not os.path.isfile(tmp_full):
            if t > 0:                                 # clip quá ngắn / tua quá đà: thử khung đầu
                cmd = ffmpeg_cmd(self.ffmpeg, src, 0, tmp, lut_local, width)
                r = troly_proc.chay_an(cmd, cwd=self.cache_dir, capture_output=True, timeout=60, creationflags=FLAGS)
            if r.returncode != 0 or not os.path.isfile(tmp_full):
                err = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()
                return uid, None, "ffmpeg lỗi: " + (err[-1] if err else "không rõ")
        os.replace(tmp_full, out)
        return uid, out, note

    def submit(self, uid, path, proxy, lut_name, dur, width=None):
        return self.pool.submit(self.make, uid, path, proxy, lut_name, dur, width)

    def shutdown(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
