# -*- coding: utf-8 -*-
"""troly_face_worker.py - Quét biểu cảm khuôn mặt (nụ cười, nhắm mắt) bằng MediaPipe Face Landmarker (CPU) trong venv AI riêng.
CHỈ ĐỌC file proxy/video; chỉ trả JSON số liệu [[has_face, smile, blink], ...] qua stdout.
"""
import argparse
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--times", required=True, help="Danh sách mốc giây cách nhau bởi dấu phẩy")
    a = ap.parse_args()

    if not os.path.isfile(a.model) or not os.path.isfile(a.video):
        print("[]")
        return

    times = [float(x) for x in a.times.split(",") if x.strip()]
    if not times:
        print("[]")
        return

    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_py
    from mediapipe.tasks.python import vision as mp_vis

    cap = cv2.VideoCapture(a.video)
    if not cap.isOpened():
        print("[]")
        return

    opts = mp_vis.FaceLandmarkerOptions(
        base_options=mp_py.BaseOptions(model_asset_path=a.model),
        output_face_blendshapes=True,
        num_faces=3,
    )
    landmarker = mp_vis.FaceLandmarker.create_from_options(opts)
    out = []
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        for t in times:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(round(t * fps))))
            ok, frame = cap.read()
            if not ok or frame is None:
                out.append([0.0, 0.0, 0.0])
                continue
            h, w = frame.shape[:2]
            if w > 480:
                frame = cv2.resize(frame, (480, max(1, int(h * 480.0 / w))))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            if not res.face_blendshapes:
                out.append([0.0, 0.0, 0.0])
                continue
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
            out.append([1.0, round(best_smile, 3), round(max_blink, 3)])
    finally:
        landmarker.close()
        cap.release()

    print(json.dumps(out))


if __name__ == "__main__":
    main()
