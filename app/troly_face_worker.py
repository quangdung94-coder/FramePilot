# -*- coding: utf-8 -*-
"""troly_face_worker.py - Quét biểu cảm khuôn mặt (nụ cười, nhắm mắt) bằng MediaPipe Face Landmarker (CPU) trong venv AI riêng.
CHỈ ĐỌC file proxy/video (hoặc nhận khung RGB qua stdin ở chế độ --serve); chỉ trả JSON số liệu [[has_face, smile, blink], ...] qua stdout.
"""
import argparse
import json
import os
import sys


def _read_exact(stream, nbytes):
    buf = bytearray()
    while len(buf) < nbytes:
        chunk = stream.read(nbytes - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def _score_rgb(mp, landmarker, rgb):
    res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not res.face_blendshapes:
        return [0.0, 0.0, 0.0]
    best_smile = 0.0
    max_blink = 0.0
    for face_bs in res.face_blendshapes:
        bs = {b.category_name: float(b.score) for b in face_bs}
        sm = 0.5 * (bs.get("mouthSmileLeft", 0.0) + bs.get("mouthSmileRight", 0.0))
        bl = 0.5 * (bs.get("eyeBlinkLeft", 0.0) + bs.get("eyeBlinkRight", 0.0))
        if sm > best_smile:
            best_smile = sm
        if bl > max_blink:
            max_blink = bl
    return [1.0, round(best_smile, 3), round(max_blink, 3)]


def _run_video(cv2, mp, landmarker, video_path, times):
    if not video_path or not os.path.isfile(video_path) or not times:
        return []
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    out = []
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        for t in times:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(round(float(t) * fps))))
            ok, frame = cap.read()
            if not ok or frame is None:
                out.append([0.0, 0.0, 0.0])
                continue
            h, w = frame.shape[:2]
            if w > 480:
                frame = cv2.resize(frame, (480, max(1, int(h * 480.0 / w))))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            out.append(_score_rgb(mp, landmarker, rgb))
    finally:
        cap.release()
    return out


def _serve_loop(cv2, np, mp, landmarker):
    sys.stdout.write(json.dumps({"ready": True}) + "\n")
    sys.stdout.flush()
    stdin_buf = sys.stdin.buffer
    while True:
        raw_line = stdin_buf.readline()
        if not raw_line:
            break
        try:
            req = json.loads(raw_line.decode("utf-8"))
        except Exception:
            continue
        cmd = req.get("cmd")
        if cmd == "quit":
            break
        if cmd == "frames":
            n = int(req.get("n") or 0)
            w = int(req.get("w") or 0)
            h = int(req.get("h") or 0)
            nbytes = n * w * h * 3
            if n <= 0 or w <= 0 or h <= 0:
                out = []
            else:
                blob = _read_exact(stdin_buf, nbytes)
                if blob is None:
                    break
                arr = np.frombuffer(blob, dtype=np.uint8).reshape((n, h, w, 3))
                out = [_score_rgb(mp, landmarker, np.ascontiguousarray(arr[i])) for i in range(n)]
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()
        elif cmd == "video":
            out = _run_video(cv2, mp, landmarker, req.get("video"), req.get("times") or [])
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--video", default="")
    ap.add_argument("--times", default="", help="Danh sách mốc giây cách nhau bởi dấu phẩy")
    ap.add_argument("--serve", action="store_true", help="Giữ tiến trình sống nhận nhiều clip qua stdin/stdout")
    a = ap.parse_args()

    if not os.path.isfile(a.model):
        if a.serve:
            sys.stdout.write(json.dumps({"error": "missing model"}) + "\n")
            sys.stdout.flush()
        else:
            print("[]")
        return

    import cv2
    import numpy as np
    import mediapipe as mp
    from mediapipe.tasks import python as mp_py
    from mediapipe.tasks.python import vision as mp_vis

    opts = mp_vis.FaceLandmarkerOptions(
        base_options=mp_py.BaseOptions(model_asset_path=a.model),
        output_face_blendshapes=True,
        num_faces=3,
    )
    landmarker = mp_vis.FaceLandmarker.create_from_options(opts)
    try:
        if a.serve:
            _serve_loop(cv2, np, mp, landmarker)
            return
        if not os.path.isfile(a.video):
            print("[]")
            return
        times = [float(x) for x in a.times.split(",") if x.strip()]
        if not times:
            print("[]")
            return
        print(json.dumps(_run_video(cv2, mp, landmarker, a.video, times)))
    finally:
        landmarker.close()


if __name__ == "__main__":
    main()
