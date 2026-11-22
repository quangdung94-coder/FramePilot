"""
troly_sync.py - Tự động đối khớp sóng âm (Cross-Correlation / GCC-PHAT) giữa nhiều máy quay hoặc máy ghi âm rời (Tascam/Zoom).

An toàn: CHỈ ĐỌC file qua ffmpeg -> RAM, tuyệt đối không sửa file gốc hay DaVinci.
Chạy 100% trên CPU bằng numpy + ffmpeg sẵn có (0 GB VRAM, không cần tải thêm model).
"""
import os
import shutil

import numpy as np

import troly_proc


def extract_pcm(path, max_sec=180, sr=8000):
    """Trích âm thanh mono float32 (tối đa `max_sec` giây đầu) từ file video/audio. Trả None nếu thiếu ffmpeg hoặc lỗi."""
    if not path or not os.path.isfile(path):
        return None
    ff = shutil.which("ffmpeg")
    if not ff:
        return None
    cmd = [
        ff, "-v", "error", "-i", path,
        "-t", str(int(max_sec)),
        "-vn", "-ac", "1", "-ar", str(int(sr)),
        "-f", "f32le", "-",
    ]
    try:
        p = troly_proc.chay_an(cmd, capture_output=True, timeout=60, tag="speech")
        if p.returncode != 0 or not p.stdout:
            return None
        arr = np.frombuffer(p.stdout, dtype=np.float32)
        return arr if len(arr) >= sr else None
    except Exception:  # noqa: BLE001
        return None


def match_offset(ref_pcm, tgt_pcm, sr=8000, max_lag_sec=60.0):
    """Tính độ lệch (giây) của `tgt_pcm` so với `ref_pcm` bằng FFT GCC-PHAT.
    Trả (offset_sec, confidence [0..1]). Dương nghĩa là `tgt` bắt đầu TRỄ hơn `ref` `offset_sec` giây."""
    if ref_pcm is None or tgt_pcm is None or len(ref_pcm) < sr or len(tgt_pcm) < sr:
        return 0.0, 0.0
    a = ref_pcm.astype(np.float64) - float(np.mean(ref_pcm))
    b = tgt_pcm.astype(np.float64) - float(np.mean(tgt_pcm))
    n = 1 << int(np.ceil(np.log2(len(a) + len(b) - 1)))
    fa = np.fft.rfft(a, n=n)
    fb = np.fft.rfft(b, n=n)
    cc = fa * np.conj(fb)
    denom = np.abs(cc)
    denom = np.where(denom > 1e-12, denom, 1e-12)
    r = np.fft.irfft(cc / denom, n=n)

    max_lag = min(int(max_lag_sec * sr), n // 2 - 1)
    # Dịch vòng để lag âm ở nửa trái, lag dương ở nửa phải
    pos = r[: max_lag + 1]
    neg = r[-max_lag:] if max_lag > 0 else np.empty(0)
    lags = np.concatenate([neg, pos])
    idx = int(np.argmax(lags))
    peak = float(lags[idx])
    med = float(np.median(np.abs(lags))) + 1e-9
    conf = round(min(1.0, max(0.0, (peak / med - 3.0) / 25.0)), 2)
    lag_samples = idx - len(neg)
    return round(lag_samples / float(sr), 3), conf


# ---------------------------------------------------------------------------
# Sync 2 tầng (Coarse-to-Fine) cho file Recorder dài 1–3 tiếng (Tascam/Zoom/Mixer)
# Tầng 1: đường bao năng lượng 100 Hz (4 MB cho 3 tiếng) -> tìm nhanh Top 3 ứng viên.
# Tầng 2: GCC-PHAT 8000 Hz trong cửa sổ ±6 giây quanh từng ứng viên -> khóa chính xác ±0.005s.
# ---------------------------------------------------------------------------
def extract_slice_pcm(path, start_s=0.0, dur_s=30.0, sr=8000, ffmpeg=None):
    """Trích 1 lát âm thanh mono float32 [start_s, start_s + dur_s] qua ffmpeg -ss nhanh."""
    if not path or not os.path.isfile(path) or dur_s <= 0.2:
        return None
    ff = ffmpeg or shutil.which("ffmpeg")
    if not ff:
        return None
    cmd = [ff, "-v", "error", "-nostdin"]
    if start_s and start_s > 0.0:
        cmd += ["-ss", "%.3f" % float(start_s)]
    cmd += ["-i", path, "-t", "%.3f" % float(dur_s), "-vn", "-ac", "1", "-ar", str(int(sr)), "-f", "f32le", "-"]
    try:
        p = troly_proc.chay_an(cmd, capture_output=True, timeout=60, tag="speech")
        if p.returncode != 0 or not p.stdout:
            return None
        arr = np.frombuffer(p.stdout, dtype=np.float32)
        return arr if len(arr) >= int(sr * 0.5) else None
    except Exception:  # noqa: BLE001
        return None


def extract_envelope(path, hop_sr=100, sr=2000, max_sec=None, ffmpeg=None):
    """Đọc file âm thanh/video -> đường bao RMS ở `hop_sr` Hz (100 Hz = 10ms/mẫu; file 3 tiếng ~4 MB RAM).
    Trả (env_float32, total_dur_s) hoặc (None, 0.0)."""
    if not path or not os.path.isfile(path):
        return None, 0.0
    ff = ffmpeg or shutil.which("ffmpeg")
    if not ff:
        return None, 0.0
    cmd = [ff, "-v", "error", "-nostdin", "-i", path]
    if max_sec and max_sec > 0:
        cmd += ["-t", "%.2f" % float(max_sec)]
    cmd += ["-vn", "-ac", "1", "-ar", str(int(sr)), "-f", "f32le", "-"]
    try:
        p = troly_proc.chay_an(cmd, capture_output=True, timeout=180, tag="speech")
        if p.returncode != 0 or not p.stdout:
            return None, 0.0
        pcm = np.frombuffer(p.stdout, dtype=np.float32)
        hop = max(1, int(sr // hop_sr))
        n_frames = len(pcm) // hop
        if n_frames < hop_sr:
            return None, 0.0
        blocks = pcm[: n_frames * hop].reshape(n_frames, hop)
        env = np.sqrt(np.mean(blocks * blocks, axis=1, dtype=np.float64)).astype(np.float32)
        return env, round(len(pcm) / float(sr), 3)
    except Exception:  # noqa: BLE001
        return None, 0.0


def find_coarse_candidates(rec_env, clip_env, hop_sr=100, top_k=3, min_sep_s=8.0):
    """Tìm top_k vị trí bắt đầu (giây trong file Recorder) mà clip_env khớp nhất với rec_env bằng FFT chuẩn hóa."""
    if rec_env is None or clip_env is None:
        return []
    lr, lc = len(rec_env), len(clip_env)
    if lr < hop_sr or lc < hop_sr or lc > lr + hop_sr:
        return []
    a = rec_env.astype(np.float64) - float(np.mean(rec_env))
    b = clip_env.astype(np.float64) - float(np.mean(clip_env))
    b_norm = float(np.linalg.norm(b))
    if b_norm < 1e-8:
        return []
    n = 1 << int(np.ceil(np.log2(lr + lc)))
    cc = np.fft.irfft(np.fft.rfft(a, n=n) * np.conj(np.fft.rfft(b, n=n)), n=n)
    valid = max(1, lr - lc + 1)
    scores = cc[:valid]
    # Chuẩn hóa theo năng lượng cục bộ của rec_env để đoạn nhỏ tiếng không bị đoạn nhạc to lấn át
    cs = np.concatenate(([0.0], np.cumsum(a * a)))
    win_e = np.sqrt(np.maximum(1e-12, cs[lc:lc + valid] - cs[:valid]))
    norm_s = scores / (win_e * b_norm)
    order = np.argsort(norm_s)[::-1]
    min_sep = int(min_sep_s * hop_sr)
    picked = []
    for idx in order:
        i = int(idx)
        if all(abs(i - p) >= min_sep for p in picked):
            picked.append(i)
            if len(picked) >= top_k:
                break
    return [round(i / float(hop_sr), 3) for i in picked]


def sync_clip_to_recorder(clip_path, rec_path, rec_env=None, rec_dur=None, clip_dur=None,
                          sr=8000, hop_sr=100, min_conf=0.32, ffmpeg=None):
    """Sync 2 tầng 1 clip video vào 1 file Recorder dài (Tascam/Zoom/Mixer).
    Trả (offset_s, conf) với offset_s = giây bắt đầu của clip TRONG file Recorder; không khớp -> (None, best_conf)."""
    if rec_env is None:
        rec_env, rec_dur = extract_envelope(rec_path, hop_sr=hop_sr, ffmpeg=ffmpeg)
    if rec_env is None:
        return None, 0.0
    clip_env, env_dur = extract_envelope(clip_path, hop_sr=hop_sr, max_sec=45.0, ffmpeg=ffmpeg)
    if clip_env is None:
        return None, 0.0
    cands = find_coarse_candidates(rec_env, clip_env, hop_sr=hop_sr, top_k=3)
    if not cands:
        return None, 0.0
    fine_dur = min(25.0, float(clip_dur or env_dur or 25.0))
    clip_pcm = extract_slice_pcm(clip_path, 0.0, fine_dur, sr=sr, ffmpeg=ffmpeg)
    if clip_pcm is None:
        return None, 0.0
    best_off, best_conf = None, 0.0
    pad_s = 6.0
    for tc in cands:
        win_start = max(0.0, tc - pad_s)
        win_dur = fine_dur + 2.0 * pad_s
        rec_pcm = extract_slice_pcm(rec_path, win_start, win_dur, sr=sr, ffmpeg=ffmpeg)
        if rec_pcm is None:
            continue
        lag_s, conf = match_offset(rec_pcm, clip_pcm, sr=sr, max_lag_sec=pad_s + 2.0)
        cand_off = round(win_start + lag_s, 3)
        if cand_off < -0.5:
            continue
        if rec_dur and cand_off > rec_dur - 0.5:
            continue
        # Kiểm chéo tương quan đường bao năng lượng tại đúng cand_off để loại 100% khớp giả (flycam / tiếng ồn ngẫu nhiên)
        i_rec = max(0, int(round(cand_off * hop_sr)))
        seg_r = rec_env[i_rec: i_rec + len(clip_env)]
        if len(seg_r) < max(hop_sr, len(clip_env) // 2):
            continue
        seg_c = clip_env[:len(seg_r)]
        sr_z = seg_r.astype(np.float64) - float(np.mean(seg_r))
        sc_z = seg_c.astype(np.float64) - float(np.mean(seg_c))
        denom_e = float(np.linalg.norm(sr_z) * np.linalg.norm(sc_z))
        env_r = float(np.dot(sr_z, sc_z) / denom_e) if denom_e > 1e-9 else 0.0
        if env_r < 0.30:
            continue
        combined = min(1.0, 0.5 * conf + 0.5 * env_r)
        if combined > best_conf:
            best_conf = combined
            best_off = max(0.0, cand_off)
    if best_off is not None and best_conf >= min_conf:
        return best_off, round(best_conf, 2)
    return None, round(best_conf, 2)
