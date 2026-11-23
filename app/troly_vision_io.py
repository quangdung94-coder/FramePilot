# -*- coding: utf-8 -*-
"""
Phân tích hình ảnh (độ nét Laplacian + độ rung Optical Flow) và âm thanh (Silero VAD)
trên file proxy để gợi ý mốc In/Out (chỉ đọc proxy, không ghi vào DaVinci hay ổ đĩa).
"""
import atexit
import json
import os
import subprocess
import sys
import threading

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


_TLS = threading.local()
_FACE_LOCK = threading.Lock()
_FACE_WORKER = None  # {"proc": Popen, "key": (py, worker, model)}


def _resolve_face_paths(ai_python=None, model_path=None):
    try:
        import troly_env
        cfg = troly_env.config() or {}
        py = ai_python or troly_env.ai_python(cfg.get("ai_python"), cfg)
        droot = troly_env.default_data_root(cfg)
    except Exception:                                     # noqa: BLE001
        if sys.platform == "darwin":
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            py = ai_python or os.path.join(base, "ai_env", "bin", "python3")
            droot = os.path.join(base, "data")
        else:
            py = ai_python or r"C:\VideoAI_ai_venv\Scripts\python.exe"
            droot = r"D:\VideoAI\data"
    mp_model = model_path or os.path.join(droot, "models", "mediapipe", "face_landmarker.task")
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "troly_face_worker.py")
    if not (py and os.path.isfile(py) and os.path.isfile(mp_model) and os.path.isfile(worker)):
        return None, None, None
    return py, worker, mp_model


def _kill_proc(p):
    if p is None:
        return
    try:
        if p.stdin:
            p.stdin.close()
    except OSError:
        pass
    try:
        if p.stdout:
            p.stdout.close()
    except OSError:
        pass
    if p.poll() is None:
        try:
            p.wait(timeout=1.5)
        except Exception:                                 # noqa: BLE001
            troly_proc.kill_tree(p.pid)
            try:
                p.kill()
            except OSError:
                pass


def close_face_worker():
    """Tắt gọn tiến trình troly_face_worker.py đang giữ sống (giải phóng RAM sau khi xong lô Bước 3)."""
    global _FACE_WORKER
    with _FACE_LOCK:
        w = _FACE_WORKER
        _FACE_WORKER = None
    if not w:
        return
    p = w.get("proc")
    if p is not None and p.poll() is None:
        try:
            p.stdin.write(b'{"cmd":"quit"}\n')
            p.stdin.flush()
        except OSError:
            pass
    _kill_proc(p)


def close_workers():
    """Tắt gọn toàn bộ worker giữ sống của Bước 3 (MediaPipe khuôn mặt + Silero VAD)."""
    close_face_worker()
    try:
        import troly_speech as _sp
        if hasattr(_sp, "close_vad_worker"):
            _sp.close_vad_worker()
    except Exception:                                     # noqa: BLE001
        pass


atexit.register(close_workers)


def _get_face_worker(py, worker, mp_model):
    """Khởi động (hoặc dùng lại) 1 tiến trình troly_face_worker.py --serve duy nhất."""
    global _FACE_WORKER
    key = (os.path.abspath(py), os.path.abspath(worker), os.path.abspath(mp_model))
    if _FACE_WORKER is not None:
        p = _FACE_WORKER["proc"]
        if _FACE_WORKER["key"] == key and p.poll() is None:
            return p
        old = _FACE_WORKER["proc"]
        _FACE_WORKER = None
        _kill_proc(old)
    p = troly_proc.mo_an(
        [py, "-X", "utf8", worker, "--model", mp_model, "--serve"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        line = p.stdout.readline()
        if not line:
            _kill_proc(p)
            return None
        hdr = json.loads(line.decode("utf-8", errors="replace"))
        if not hdr.get("ready"):
            _kill_proc(p)
            return None
    except Exception:                                     # noqa: BLE001
        _kill_proc(p)
        return None
    _FACE_WORKER = {"proc": p, "key": key}
    return p


def _query_face_worker(py, worker, mp_model, req_header, raw_blob=None):
    """Gửi 1 yêu cầu tới worker MediaPipe giữ sống; tự khởi động lại 1 lần nếu pipe đứt."""
    global _FACE_WORKER
    with _FACE_LOCK:
        for _attempt in range(2):
            p = _get_face_worker(py, worker, mp_model)
            if p is None:
                return None
            try:
                p.stdin.write((json.dumps(req_header) + "\n").encode("utf-8"))
                if raw_blob is not None:
                    p.stdin.write(raw_blob)
                p.stdin.flush()
                line = p.stdout.readline()
                if not line:
                    raise OSError("face worker EOF")
                return json.loads(line.decode("utf-8", errors="replace"))
            except Exception:                             # noqa: BLE001
                _FACE_WORKER = None
                _kill_proc(p)
    return None


def analyze_proxy_faces(proxy_path, timestamps, ai_python=None, model_path=None):
    """Quét biểu cảm khuôn mặt (nụ cười, nhắm mắt) bằng MediaPipe Face Landmarker qua venv AI riêng (giữ worker sống).
    Trả danh sách [(has_face, smile, blink)] khớp timestamps, hoặc None nếu chưa có model/venv AI."""
    if not proxy_path or not os.path.isfile(proxy_path) or not timestamps:
        return None
    py, worker, mp_model = _resolve_face_paths(ai_python=ai_python, model_path=model_path)
    if not py:
        return None

    # Nếu analyze_proxy_vision vừa giải mã sẵn khung RGB <= 480px trong cùng luồng: gửi thẳng khung qua pipe (0 lần giải mã lại!)
    cached = getattr(_TLS, "frames", None)
    data = None
    if cached and cached[0] == proxy_path and len(cached[1]) == len(timestamps) and cached[1]:
        frames_rgb = cached[1]
        h, w = frames_rgb[0].shape[:2]
        blob = b"".join(np.ascontiguousarray(fr, dtype=np.uint8).tobytes() for fr in frames_rgb)
        data = _query_face_worker(py, worker, mp_model, {"cmd": "frames", "n": len(frames_rgb), "w": int(w), "h": int(h)}, raw_blob=blob)
    else:
        data = _query_face_worker(py, worker, mp_model, {"cmd": "video", "video": proxy_path, "times": [round(float(t), 3) for t in timestamps]})

    if isinstance(data, list) and len(data) == len(timestamps):
        return [(float(x[0]), float(x[1]), float(x[2])) for x in data]
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

    collect_rgb = bool(use_faces and _resolve_face_paths()[0])
    rgb_frames = []
    rgb_size = None
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
        cur_pos = 0
        for f in range(0, total_frames, step):
            diff = f - cur_pos
            if diff == 0:
                ret, frame = cap.read()
            elif 0 < diff <= 12:
                ok_g = True
                for _ in range(diff):
                    if not cap.grab():
                        ok_g = False
                        break
                ret, frame = cap.read() if ok_g else (False, None)
            else:
                cap.set(cv2.CAP_PROP_POS_FRAMES, f)
                ret, frame = cap.read()
            cur_pos = f + 1
            if not ret or frame is None:
                break
            h, w = frame.shape[:2]
            if collect_rgb:
                fr480 = cv2.resize(frame, (480, max(1, int(h * 480.0 / w)))) if w > 480 else frame
                if rgb_size is None:
                    rgb_size = (fr480.shape[1], fr480.shape[0])
                elif (fr480.shape[1], fr480.shape[0]) != rgb_size:
                    fr480 = cv2.resize(fr480, rgb_size)
                rgb_frames.append(cv2.cvtColor(fr480, cv2.COLOR_BGR2RGB))
            fr360 = cv2.resize(frame, (360, max(1, int(h * 360.0 / w)))) if w > 360 else frame
            gray = cv2.cvtColor(fr360, cv2.COLOR_BGR2GRAY)
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
    faces = None
    if use_faces:
        _TLS.frames = (proxy_path, rgb_frames) if collect_rgb and len(rgb_frames) == len(samples) else None
        try:
            faces = analyze_proxy_faces(proxy_path, [s[0] for s in samples])
        finally:
            _TLS.frames = None
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

    try:
        cmd = [
            "ffmpeg", "-nostdin", "-i", proxy_path,
            "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1",
        ]
        p = troly_proc.chay_an(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
        raw = p.stdout or b""
        if p.returncode != 0 or len(raw) < 3200:
            return []
        if len(raw) % 2:
            raw = raw[:-1]
        audio_i16 = np.frombuffer(raw, dtype="<i2")
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
