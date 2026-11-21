"""
troly_hw.py - Tự nhận diện phần cứng & hệ điều hành (Windows / macOS / GPU / CPU) để FramePilot tự chỉnh mức tải an toàn.

Nguyên tắc:
  - Không ép buộc RTX 3060 hay card NVIDIA: chạy được từ MacBook (Apple Silicon MPS / CPU),
    laptop Windows (VRAM nhỏ hoặc không có GPU rời) tới PC card rời.
  - Nhanh, không tự ý nạp PyTorch nặng nếu chưa cần; chỉ kiểm tra nhẹ và cache kết quả.
"""
import os
import platform
import shutil
import sys

import troly_proc

_CACHED = None


def _nvidia_vram_gb():
    """Đọc dung lượng VRAM (GB) qua nvidia-smi nếu có, không nạp torch."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return 0.0, ""
    try:
        p = troly_proc.chay_an(
            [smi, "--query-gpu=memory.total,name", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        if p.returncode != 0 or not (p.stdout or "").strip():
            return 0.0, ""
        line = (p.stdout or "").strip().splitlines()[0]
        parts = [x.strip() for x in line.split(",", 1)]
        mb = float(parts[0])
        name = parts[1] if len(parts) > 1 else "NVIDIA GPU"
        return round(mb / 1024.0, 1), name
    except Exception:  # noqa: BLE001
        return 0.0, ""


def detect(refresh=False):
    """Trả dict mô tả máy: {os, arch, accel, gpu_name, vram_gb, cpu_cores, tier, thumb_workers, wave_workers, whisper_hint}."""
    global _CACHED
    if _CACHED is not None and not refresh:
        return dict(_CACHED)

    os_name = "mac" if sys.platform == "darwin" else ("win" if os.name == "nt" else "linux")
    arch = platform.machine().lower()
    cores = max(2, int(os.cpu_count() or 4))

    accel = "cpu"
    gpu_name = ""
    vram_gb = 0.0
    tier = "cpu_lite"

    if os_name == "mac":
        if "arm" in arch or "aarch64" in arch:
            accel = "mps"
            gpu_name = "Apple Silicon (Metal/MPS)"
            tier = "apple_silicon"
        else:
            accel = "cpu"
            gpu_name = "Mac Intel (CPU)"
            tier = "cpu_lite"
    else:
        vram_gb, gpu_name = _nvidia_vram_gb()
        if vram_gb > 0:
            accel = "cuda"
            tier = "gpu_full" if vram_gb >= 8.0 else "gpu_lite"

    if tier in ("gpu_full", "apple_silicon"):
        thumb_w = min(6, max(2, cores // 2))
        wave_w = min(4, max(2, cores // 3))
        whisper_hint = "medium / large-v3-turbo (GPU)" if os_name != "mac" else "medium / large-v3-turbo (Metal/CPU)"
    elif tier == "gpu_lite":
        thumb_w = min(4, max(2, cores // 2))
        wave_w = 2
        whisper_hint = "small / medium (int8 GPU)"
    else:
        thumb_w = min(3, max(1, cores // 3))
        wave_w = 1
        whisper_hint = "base / small (CPU nhẹ)"

    _CACHED = {
        "os": os_name,
        "arch": arch,
        "accel": accel,
        "gpu_name": gpu_name or "CPU",
        "vram_gb": vram_gb,
        "cpu_cores": cores,
        "tier": tier,
        "thumb_workers": thumb_w,
        "wave_workers": wave_w,
        "whisper_hint": whisper_hint,
    }
    return dict(_CACHED)


def resolve_scripts_dir(custom=None):
    """Đường dẫn thư mục Utility Scripts của DaVinci Resolve theo hệ điều hành (Windows & macOS)."""
    if custom:
        return os.path.join(custom, "Utility")
    if sys.platform == "darwin":
        return os.path.expanduser(
            "~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
        )
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or ""
        if appdata:
            return os.path.join(
                appdata, "Blackmagic Design", "DaVinci Resolve", "Support", "Fusion", "Scripts", "Utility"
            )
    return os.path.expanduser("~/.local/share/DaVinciResolve/Fusion/Scripts/Utility")
