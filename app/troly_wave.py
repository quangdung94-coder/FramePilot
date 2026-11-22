"""
troly_wave.py - Sóng âm của clip cho Bước 3 (ADR-0019).

ffmpeg trích âm thanh từ file PROXY (chỉ ĐỌC, không ghi gì cạnh proxy), tính đỉnh biên độ theo từng đoạn, lưu JSON nhỏ vào
<data_root>\\cache\\troly_wave\\<project>\\ (xóa được, tự tạo lại). Làm trên luồng nền, mỗi lần một clip, có giới hạn thời gian.
Clip không có proxy: báo "Chưa có proxy" (giao diện hiện thanh trống).
"""
import array
import hashlib
import json
import os
import subprocess
import troly_proc
import threading

BINS = 800                      # số cột đỉnh của một clip (đủ mịn cho thanh rộng ~750 px)
SAMPLE_RATE = 4000              # Hz, đủ để vẽ hình dáng sóng, nhẹ (10 phút = 4.8 MB)
TIMEOUT_S = 90                  # quá giờ này thì bỏ, báo lỗi (không treo giao diện)
VERSION = 1


def cache_file(cache_dir, key):
    return os.path.join(cache_dir, hashlib.sha1(key.encode("utf-8")).hexdigest()[:20] + ".json")


def _stamp(src):
    st = os.stat(src)
    return st.st_size, int(st.st_mtime)


def read_cached(path, src):
    """Đỉnh sóng đã lưu nếu còn đúng với file proxy (cùng cỡ và giờ sửa), không thì None."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        size, mt = _stamp(src)
        if d.get("v") == VERSION and d.get("size") == size and d.get("mtime") == mt and isinstance(d.get("peaks"), list):
            return d
    except (OSError, ValueError):
        pass
    return None


def peaks_from_pcm(raw, bins=BINS):
    """PCM s16le mono -> danh sách `bins` số nguyên 0..100 (đỉnh mỗi đoạn, chuẩn hóa theo đỉnh lớn nhất của clip)."""
    a = array.array("h")
    a.frombytes(raw[: len(raw) - (len(raw) % 2)])
    n = len(a)
    if n == 0:
        return []
    bins = max(1, min(bins, n))
    out = []
    for i in range(bins):
        seg = a[i * n // bins:(i + 1) * n // bins] or a[i * n // bins:i * n // bins + 1]
        out.append(max(max(seg), -min(seg)))
    top = max(out) or 1
    return [int(round(v * 100.0 / top)) for v in out]


def make_peaks(src, out_path, ffmpeg="ffmpeg", timeout=TIMEOUT_S, runner=troly_proc.chay_an, ss=None, dur=None):
    """Làm file đỉnh sóng (hỗ trợ cắt lát [ss, ss+dur] cho file Recorder đã sync). Trả {'peaks': [...]} hoặc {'error': ...}."""
    cmd = [ffmpeg, "-v", "error", "-nostdin"]
    if ss is not None and float(ss) > 0:
        cmd += ["-ss", "%.3f" % float(ss)]
    cmd += ["-i", src]
    if dur is not None and float(dur) > 0:
        cmd += ["-t", "%.3f" % float(dur)]
    cmd += ["-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"]
    try:
        r = runner(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": "Làm sóng âm quá %d giây, đã bỏ." % timeout}
    except OSError:
        return {"error": "Không chạy được ffmpeg."}
    if r.returncode != 0:
        return {"error": "ffmpeg không đọc được âm thanh của proxy."}
    peaks = peaks_from_pcm(r.stdout)
    if not peaks:
        return {"error": "Clip không có âm thanh."}
    size, mt = _stamp(src)
    d = {"v": VERSION, "size": size, "mtime": mt, "peaks": peaks}
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, out_path)
    except OSError:
        pass                                    # không lưu được cache thì vẫn dùng kết quả này
    return d


class WaveMaker(object):
    """Làm sóng âm nền, mỗi lần một clip. get() trả ngay: đỉnh sóng | {'pending': True} | {'error': ...}."""

    def __init__(self, cache_dir, ffmpeg="ffmpeg", timeout=TIMEOUT_S, runner=troly_proc.chay_an):
        self._dir, self._ffmpeg, self._timeout, self._runner = cache_dir, ffmpeg, timeout, runner
        self._lock = threading.Lock()
        self._done = {}                         # key -> kết quả
        self._busy = {}                         # key -> Thread
        self._gate = threading.Semaphore(1)

    def get(self, key, src, ss=None, dur=None):
        if not src or not os.path.isfile(src):
            return {"error": "Chưa có proxy"}
        ckey = "%s|rec:%.2f+%.2f" % (key, float(ss or 0.0), float(dur or 0.0)) if (ss is not None or dur is not None) else key
        path = cache_file(self._dir, ckey)
        d = read_cached(path, src)
        if d:
            return {"peaks": d["peaks"]}
        with self._lock:
            if ckey in self._done:                 # kết quả trong bộ nhớ (lỗi giữ đến khi mở lại panel; đỉnh sóng khi không ghi được cache)
                return self._done[ckey]
            if ckey not in self._busy:
                t = threading.Thread(target=self._work, args=(ckey, src, path, ss, dur), daemon=True)
                self._busy[ckey] = t
                t.start()
        return {"pending": True}

    def _work(self, key, src, path, ss=None, dur=None):
        with self._gate:
            res = make_peaks(src, path, self._ffmpeg, self._timeout, self._runner, ss=ss, dur=dur)
        with self._lock:
            self._done[key] = {"error": res["error"]} if res.get("error") else {"peaks": res["peaks"]}
            self._busy.pop(key, None)

    def wait(self, key, timeout=10):
        t = self._busy.get(key)
        if t:
            t.join(timeout)
