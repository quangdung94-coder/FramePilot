# -*- coding: utf-8 -*-
"""
Phân tích hình ảnh (độ nét Laplacian + độ rung Optical Flow) và âm thanh (Silero VAD)
trên file proxy để gợi ý mốc In/Out (chỉ đọc proxy, không ghi vào DaVinci hay ổ đĩa).
"""
import json
import os
import subprocess
import tempfile

try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import troly_proc
except ImportError:
    from app import troly_proc


def analyze_proxy_faces(proxy_path, timestamps, ai_python=None, model_path=None):
    """Quét biểu cảm khuôn mặt (nụ cười, nhắm mắt) bằng MediaPipe Face Landmarker qua venv AI riêng.
    Trả danh sách [(has_face, smile, blink)] khớp timestamps, hoặc None nếu chưa có model/venv AI."""
    if not proxy_path or not os.path.isfile(proxy_path) or not timestamps:
        return None
    try:
        import troly_env
        cfg = troly_env.config() or {}
        py = ai_python or troly_env.ai_python(cfg.get("ai_python"), cfg)
        droot = troly_env.default_data_root(cfg)
    except Exception:                                     # noqa: BLE001
        cfg = {}
        py = ai_python or r"C:\VideoAI_ai_venv\Scripts\python.exe"
        droot = r"D:\VideoAI\data"
    mp_model = model_path or os.path.join(droot, "models", "mediapipe", "face_landmarker.task")
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "troly_face_worker.py")
    if not (os.path.isfile(py) and os.path.isfile(mp_model) and os.path.isfile(worker)):
        return None
    ts_str = ",".join("%.2f" % float(t) for t in timestamps)
    try:
        p = troly_proc.chay_an(
            [py, "-X", "utf8", worker, "--model", mp_model, "--video", proxy_path, "--times", ts_str],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        if p.returncode != 0:
            return None
        lines = [ln for ln in (p.stdout or "").splitlines() if ln.strip()]
        if not lines:
            return None
        data = json.loads(lines[-1])
        if isinstance(data, list) and len(data) == len(timestamps):
            return [(float(x[0]), float(x[1]), float(x[2])) for x in data]
    except Exception:                                     # noqa: BLE001
        return None
    return None


def analyze_proxy_vision(proxy_path, dur, target_len=3.5, head_skip=1.3, max_samples=48, use_faces=True):
    """Quét mẫu thưa trên proxy để tìm đoạn dài `target_len` giây có độ nét cao & độ rung thấp nhất.
    Trả dict {'in': float, 'out': float, 'sharp': float, 'motion': float, 'rule': str} hoặc None.
    """
    if cv2 is None or np is None:
        return None
    if not proxy_path or not os.path.exists(proxy_path):
        return None
    dur = float(dur or 0)
    if dur < 1.5:
        return None

    cap = cv2.VideoCapture(proxy_path)
    if not cap.isOpened():
        return None

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total_frames < 5 or fps <= 0:
            return None

        actual_dur = total_frames / fps
        use_dur = dur if dur > 0 else actual_dur
        win_len = min(float(target_len), max(1.0, use_dur * 0.6))

        # Chỉ bỏ đầu khi clip đủ dài (trên 4.5s) theo thói quen thực tế (tránh rung tay mới bấm máy)
        skip_s = float(head_skip) if use_dur > (win_len + head_skip + 0.5) else 0.0
        step = max(1, total_frames // max_samples)

        samples = []
        prev_gray = None
        for f in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ret, frame = cap.read()
            if not ret:
                break
            h, w = frame.shape[:2]
            if w > 360:
                frame = cv2.resize(frame, (360, max(1, int(h * 360.0 / w))))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            motion = 0.0
            if prev_gray is not None:
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray, None,
                    pyr_scale=0.5, levels=2, winsize=9,
                    iterations=2, poly_n=5, poly_sigma=1.1, flags=0,
                )
                mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
                motion = float(np.mean(mag))
            prev_gray = gray
            samples.append((f / fps, sharp, motion))
    finally:
        cap.release()

    if len(samples) < 3:
        return None

    sharps = np.array([s[1] for s in samples], dtype=float)
    motions = np.array([s[2] for s in samples], dtype=float)
    s_max = float(np.max(sharps)) or 1.0
    m_max = float(np.max(motions)) or 1.0

    # Cộng điểm MediaPipe Face Landmarker (nụ cười tươi + tránh nhắm mắt ở đầu/cuối) nếu có sẵn model
    faces = analyze_proxy_faces(proxy_path, [s[0] for s in samples]) if use_faces else None
    f_has = np.array([x[0] for x in faces], dtype=float) if faces else None
    f_smile = np.array([x[1] for x in faces], dtype=float) if faces else None
    f_blink = np.array([x[2] for x in faces], dtype=float) if faces else None

    # Cửa sổ trượt tìm đoạn nét nhất, êm nhất & có biểu cảm đẹp nhất sau head_skip
    best_score = -1e9
    best_pair = None
    for t_start, _, _ in samples:
        if t_start < skip_s:
            continue
        t_end = t_start + win_len
        if t_end > use_dur:
            t_end = use_dur
            t_start = max(skip_s, t_end - win_len)
        idx = [i for i, (ts, _, _) in enumerate(samples) if t_start <= ts <= t_end]
        if not idx:
            continue
        avg_s = float(np.mean(sharps[idx]))
        avg_m = float(np.mean(motions[idx]))
        score = (avg_s / s_max) - 0.85 * (avg_m / m_max)
        avg_smile, has_face = 0.0, False
        if f_has is not None:
            face_ratio = float(np.mean(f_has[idx]))
            avg_smile = float(np.mean(f_smile[idx]))
            edge_blink = max(float(f_blink[idx[0]]), float(f_blink[idx[-1]]))
            has_face = face_ratio >= 0.35
            score += 0.35 * face_ratio + 0.45 * avg_smile - (0.55 if edge_blink >= 0.5 else 0.0)
        if score > best_score:
            best_score = score
            best_pair = (t_start, t_end, avg_s, avg_m, has_face, avg_smile)

    if best_pair is None:
        return None

    in_s, out_s, avg_s, avg_m, has_face, avg_smile = best_pair
    if out_s - in_s < 0.8:
        return None
    skip_note = f", bỏ {skip_s:.1f}s đầu" if skip_s > 0 else ""
    face_note = " · Cười tươi" if avg_smile >= 0.35 else (" · Có mặt rõ" if has_face else "")
    return {
        "in": round(in_s, 2),
        "out": round(out_s, 2),
        "sharp": round(avg_s, 1),
        "motion": round(avg_m, 2),
        "smile": round(avg_smile, 2),
        "rule": f"Hình ảnh (Nét {avg_s:.0f} · Êm {avg_m:.2f}{face_note}{skip_note})",
    }


def analyze_proxy_vad(proxy_path, dur, pad=0.35):
    """Phát hiện nhanh đoạn có tiếng người nói bằng Silero VAD từ audio của proxy.
    Trả danh sách [{'t0': float, 't1': float}] hoặc [] nếu không có tiếng nói / thiếu công cụ.
    """
    if np is None or not proxy_path or not os.path.exists(proxy_path):
        return []
    use_worker = None
    try:
        import torch
        from silero_vad import load_silero_vad, get_speech_timestamps
    except ImportError:
        try:
            import troly_speech as _sp
            _name, use_worker = _sp._load_vad_worker()
        except Exception:  # noqa: BLE001
            use_worker = None
        if use_worker is None:
            return []

    tmp_wav = None
    try:
        fd, tmp_wav = tempfile.mkstemp(suffix=".wav", prefix="fp_vad_")
        os.close(fd)
        cmd = [
            "ffmpeg", "-y", "-i", proxy_path,
            "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", tmp_wav,
        ]
        p = troly_proc.chay_an(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        if p.returncode != 0 or not os.path.exists(tmp_wav) or os.path.getsize(tmp_wav) < 1024:
            return []

        import wave
        with wave.open(tmp_wav, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
        audio_i16 = np.frombuffer(raw, dtype=np.int16)
        if len(audio_i16) < 1600:
            return []

        if use_worker is not None:
            segs = use_worker(audio_i16)
            return [{"t0": round(float(s[0]), 2), "t1": round(float(s[1]), 2)} for s in (segs or []) if float(s[1]) - float(s[0]) >= 0.4]

        audio = audio_i16.astype(np.float32) / 32768.0
        model = getattr(analyze_proxy_vad, "_model", None)
        if model is None:
            model = load_silero_vad()
            analyze_proxy_vad._model = model

        wav_tensor = torch.from_numpy(audio)
        ts = get_speech_timestamps(wav_tensor, model, sampling_rate=16000, return_seconds=True)
        out = []
        for seg in ts or []:
            t0, t1 = float(seg.get("start", 0)), float(seg.get("end", 0))
            if t1 - t0 >= 0.4:
                out.append({"t0": round(t0, 2), "t1": round(t1, 2)})
        return out
    except (subprocess.TimeoutExpired, OSError, ValueError, RuntimeError):
        return []
    finally:
        if tmp_wav and os.path.exists(tmp_wav):
            try:
                os.remove(tmp_wav)
            except OSError:
                pass
