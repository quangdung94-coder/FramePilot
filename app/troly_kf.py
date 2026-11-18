"""
troly_kf.py - Danh sách keyframe (khung chính) của proxy để lướt mượt (Việc 2, ADR-0023). Chỉ ĐỌC proxy bằng ffprobe (đọc chỉ mục gói tin,
không giải mã, không tạo proxy mới); kết quả nhỏ lưu cache <data_root>\\cache\\troly_kf\\<project>\\ (xóa được, tự tạo lại).
Kéo thanh lướt thì nhảy theo keyframe gần nhất phía trước (giải mã 1 khung, nhanh); thả ra thì nhảy chính xác.
"""
import hashlib
import json
import os
import shutil
import subprocess

TIMEOUT_S = 40
VERSION = 1
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def ffprobe_path(ffmpeg=None):
    p = shutil.which("ffprobe")
    if p:
        return p
    if ffmpeg:
        cand = os.path.join(os.path.dirname(ffmpeg), "ffprobe.exe")
        if os.path.isfile(cand):
            return cand
    return "ffprobe"


def parse_packets(text):
    """Dòng 'pts_time,flags' (flags bắt đầu bằng K là keyframe) -> danh sách giây tăng dần, không trùng."""
    out = []
    for line in (text or "").splitlines():
        parts = line.strip().split(",")
        if len(parts) < 2 or not parts[1].startswith("K"):
            continue
        try:
            out.append(round(float(parts[0]), 4))
        except ValueError:
            continue
    return sorted(set(out))


def probe(src, ffprobe="ffprobe", timeout=TIMEOUT_S, runner=subprocess.run):
    """Keyframe của luồng hình đầu tiên, hoặc None nếu ffprobe lỗi / quá giờ. Chỉ đọc."""
    cmd = [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time,flags", "-of", "csv=p=0", src]
    try:
        r = runner(cmd, capture_output=True, text=True, timeout=timeout, creationflags=FLAGS)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    kf = parse_packets(r.stdout)
    return kf or None


def cache_file(cache_dir, src):
    return os.path.join(cache_dir, hashlib.sha1(src.encode("utf-8")).hexdigest()[:20] + ".json")


def get(src, cache_dir, ffprobe="ffprobe", runner=subprocess.run):
    """Keyframe (có cache theo cỡ + giờ sửa của proxy). Trả list hoặc None."""
    try:
        st = os.stat(src)
    except OSError:
        return None
    p = cache_file(cache_dir, src)
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        if d.get("v") == VERSION and d.get("size") == st.st_size and d.get("mtime") == int(st.st_mtime) and isinstance(d.get("kf"), list):
            return d["kf"]
    except (OSError, ValueError):
        pass
    kf = probe(src, ffprobe, runner=runner)
    if kf is None:
        return None
    try:
        os.makedirs(cache_dir, exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"v": VERSION, "size": st.st_size, "mtime": int(st.st_mtime), "kf": kf}, f)
        os.replace(tmp, p)
    except OSError:
        pass
    return kf
