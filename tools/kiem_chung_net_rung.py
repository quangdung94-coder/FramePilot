# -*- coding: utf-8 -*-
"""
Script đối chiếu độ nét (Laplacian) và độ rung (Optical Flow)
trên các clip đã dựng (A..D) để kiểm chứng giả thuyết In/Out.
Chỉ ĐỌC từ proxy file (F:\02_Proxy Media), không ghi hay sửa file nào.
"""
import os
import sys
import json
import numpy as np

try:
    import cv2
except ImportError:
    print("Lỗi: Chưa cài opencv trong venv")
    sys.exit(1)

def do_do_net_va_rung(video_path, max_samples=100):
    """
    Đọc mẫu đều các khung hình của video:
    - Trả về danh sách dict: {f_idx: int, sec: float, sharpness: float, motion: float}
    """
    if not os.path.exists(video_path):
        return None
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 5:
        cap.release()
        return None
    
    # Bước nhảy để lấy tối đa max_samples khung (tiết kiệm thời gian đọc)
    step = max(1, total_frames // max_samples)
    
    results = []
    prev_gray = None
    
    for f in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ret, frame = cap.read()
        if not ret:
            break
        
        # Resize nhỏ xuống 480p để tính optical flow và sharpness siêu nhanh
        h, w = frame.shape[:2]
        if w > 480:
            scale = 480.0 / w
            frame = cv2.resize(frame, (480, int(h * scale)))
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 1. Độ nét bằng Laplacian Variance
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        
        # 2. Độ rung/chuyển động bằng Optical Flow so với frame trước
        motion = 0.0
        if prev_gray is not None:
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray, None, 
                pyr_scale=0.5, levels=2, winsize=11, 
                iterations=2, poly_n=5, poly_sigma=1.1, flags=0
            )
            # Độ lớn vector chuyển động trung bình
            mag = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
            motion = float(np.mean(mag))
        
        prev_gray = gray
        results.append({
            "frame": f,
            "sec": round(f / fps, 2),
            "sharpness": round(sharpness, 2),
            "motion": round(motion, 2)
        })
    
    cap.release()
    return results

def phan_tich_mau_clip(dump_file, limit_clips=15):
    """
    Đọc dump project, tìm các clip có trên timeline (đã chọn In/Out thật),
    đoạn lấy vs đoạn bỏ.
    """
    if not os.path.exists(dump_file):
        print("Không tìm thấy dump:", dump_file)
        return
    
    dump = json.load(open(dump_file, encoding="utf-8"))
    uid_to_clip = {c["uid"]: c for c in dump.get("clips", [])}
    timelines = dump.get("timelines", [])
    if not timelines:
        print("Không có timeline")
        return
    
    tl = timelines[0]
    items = tl.get("items", [])
    print(f"Tổng clip trên timeline {tl.get('name')}: {len(items)}")
    
    da_do = 0
    ket_qua = []
    
    for it in items:
        if da_do >= limit_clips:
            break
        c = uid_to_clip.get(it["uid"])
        if not c:
            continue
        
        props = c.get("props", {})
        fname = props.get("File Name", "")
        fps = float(props.get("FPS", 25.0))
        
        # Tìm file proxy thật
        # Cấu trúc: F:\02_Proxy Media\<tên project>\ProxyMedia\01_Project video\<tên project>\01_footage\<fname.mov>
        base_name, _ = os.path.splitext(fname)
        path_orig = c.get("path", "")
        
        # Thử tìm proxy tương ứng
        proxy_guess = None
        for root, dirs, files in os.walk(r"F:\02_Proxy Media"):
            for f in files:
                if f.lower() == (base_name + ".mov").lower() or f.lower() == fname.lower():
                    proxy_guess = os.path.join(root, f)
                    break
            if proxy_guess:
                break
        
        if not proxy_guess or not os.path.exists(proxy_guess):
            continue
            
        src_start_f = it.get("src_start_f", 0)
        src_end_f = it.get("src_end_f", 0)
        dur_f = it.get("dur", 0)
        
        in_sec = src_start_f / fps
        out_sec = src_end_f / fps
        
        # Bỏ qua nếu clip giữ toàn bộ hoặc quá ngắn
        total_f = int(props.get("Frames", 0) or 0)
        if total_f <= 0 or dur_f >= total_f * 0.95:
            continue
            
        metrics = do_do_net_va_rung(proxy_guess, max_samples=60)
        if not metrics or len(metrics) < 5:
            continue
            
        # Chia mẫu thành 2 nhóm: Nhóm TRONG đoạn giữ vs Nhóm NGOÀI đoạn giữ (bỏ)
        nhom_giu_sharp = []
        nhom_giu_motion = []
        nhom_bo_sharp = []
        nhom_bo_motion = []
        
        for m in metrics:
            sec = m["sec"]
            if in_sec <= sec <= out_sec:
                nhom_giu_sharp.append(m["sharpness"])
                nhom_giu_motion.append(m["motion"])
            else:
                nhom_bo_sharp.append(m["sharpness"])
                nhom_bo_motion.append(m["motion"])
        
        if not nhom_giu_sharp or not nhom_bo_sharp:
            continue
            
        avg_giu_sharp = np.mean(nhom_giu_sharp)
        avg_bo_sharp = np.mean(nhom_bo_sharp)
        avg_giu_motion = np.mean(nhom_giu_motion)
        avg_bo_motion = np.mean(nhom_bo_motion)
        
        da_do += 1
        kq_clip = {
            "file": fname,
            "in_s": round(in_sec, 2),
            "out_s": round(out_sec, 2),
            "dur_s": round(out_sec - in_sec, 2),
            "sharp_giu": round(float(avg_giu_sharp), 2),
            "sharp_bo": round(float(avg_bo_sharp), 2),
            "motion_giu": round(float(avg_giu_motion), 2),
            "motion_bo": round(float(avg_bo_motion), 2),
            "sharp_cao_hon": bool(avg_giu_sharp > avg_bo_sharp),
            "motion_on_dinh_hon": bool(avg_giu_motion < avg_bo_motion)
        }
        ket_qua.append(kq_clip)
        print(f"[{da_do}/{limit_clips}] {fname}: Giữ {kq_clip['dur_s']}s (từ {kq_clip['in_s']}s đến {kq_clip['out_s']}s)")
        print(f"   -> Nét: giữ={kq_clip['sharp_giu']} vs bỏ={kq_clip['sharp_bo']} | Rung: giữ={kq_clip['motion_giu']} vs bỏ={kq_clip['motion_bo']}")

    # Tổng kết
    if ket_qua:
        ty_le_net = sum(1 for k in ket_qua if k["sharp_cao_hon"]) / len(ket_qua) * 100
        ty_le_rung = sum(1 for k in ket_qua if k["motion_on_dinh_hon"]) / len(ket_qua) * 100
        print("\n=== KẾT QUẢ ĐỐI CHIẾU ===")
        print(f"- Số clip mẫu kiểm tra: {len(ket_qua)}")
        print(f"- Tỷ lệ đoạn GIỮ NÉT HƠN đoạn bỏ: {ty_le_net:.1f}%")
        print(f"- Tỷ lệ đoạn GIỮ ÍT RUNG / ÊM HƠN đoạn bỏ: {ty_le_rung:.1f}%")

if __name__ == "__main__":
    dump_p = r"D:\VideoAI\data\hoc_tu_cu\LV_A_dump.json"
    phan_tich_mau_clip(dump_p, limit_clips=10)
