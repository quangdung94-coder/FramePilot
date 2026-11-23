# -*- coding: utf-8 -*-
r"""
troly_setup.py - Bộ cài đặt thông minh & kiểm tra phụ thuộc khi mang bản đóng gói FramePilot.exe sang máy Windows khác.

Đảm bảo 3 tiêu chí:
1. SẠCH 100%: Không mang theo bất kỳ dữ liệu khách hàng, kế hoạch project cũ, cache cũ hay đường dẫn cá nhân nào.
2. ĐÓNG GÓI KÈM PLUGIN & MODEL: Kiểm tra từng công cụ (ffmpeg, ffprobe, Const-me Whisper), môi trường AI (PyTorch/Whisper/VAD/MediaPipe)
   và từng bộ Model AI (9 bộ model).
3. HỎI TRƯỚC & BỎ QUA CÁI ĐÃ CÓ: Quét máy đích trước khi cài, hiển thị rõ mục nào [ĐÃ CÓ -> BỎ QUA], mục nào [CHƯA CÓ -> SẼ CÀI],
   hỏi người dùng xác nhận rồi mới cài những mục chưa có (tuyệt đối không chép đè model/plugin đã có sẵn trên máy đích).
"""
import argparse
import json
import os
import re
import shutil
import sys

REQUIRED_MODELS = (
    ("whisper_large_v3_turbo", "Whisper large-v3-turbo (Chép lời đa ngữ / tiếng Việt nhanh)"),
    ("phowhisper_medium_ct2", "PhoWhisper-medium CT2 (Chép lời chuyên tiếng Việt)"),
    ("siglip2_vitb16", "SigLIP 2 ViT-B/16 (Phân loại cảnh AI Bước 2 - chính)"),
    ("siglip_vitb16", "SigLIP ViT-B/16 (Phân loại cảnh AI Bước 2 - dự phòng)"),
    ("openclip_vitb32_laion2b", "OpenCLIP ViT-B/32 (Phân loại cảnh AI Bước 2 - cơ bản)"),
    ("dinov2_small", "DINOv2-small (Tìm góc máy / cảnh tương tự Bước 2)"),
    ("clap_htsat_unfused", "LAION-CLAP (Nhận diện 6 tiếng động đám cưới Bước 3)"),
    ("mediapipe", "MediaPipe Face Landmarker (Nụ cười / tránh nhắm mắt Bước 3)"),
    ("wavlm_sv", "WavLM-SV (Tách người nói MC / Gia đình Bước 4)"),
)

REQUIRED_MODELS_MAC = (
    ("whisper_large_v3_turbo_mlx", "Whisper large-v3-turbo MLX (Chép lời GPU chip M)"),
    ("phowhisper_medium_mlx", "PhoWhisper-medium MLX (Chép lời tiếng Việt GPU chip M)"),
    ("siglip2_vitb16", "SigLIP 2 ViT-B/16 (Phân loại cảnh AI Bước 2 - chính)"),
    ("siglip_vitb16", "SigLIP ViT-B/16 (Phân loại cảnh AI Bước 2 - dự phòng)"),
    ("openclip_vitb32_laion2b", "OpenCLIP ViT-B/32 (Phân loại cảnh AI Bước 2 - cơ bản)"),
    ("dinov2_small", "DINOv2-small (Tìm góc máy / cảnh tương tự Bước 2)"),
    ("clap_htsat_unfused", "LAION-CLAP (Nhận diện 6 tiếng động đám cưới Bước 3)"),
    ("mediapipe", "MediaPipe Face Landmarker (Nụ cười / tránh nhắm mắt Bước 3)"),
    ("wavlm_sv", "WavLM-SV (Tách người nói MC / Gia đình Bước 4)"),
)

# Các mẫu đường dẫn/tên project cá nhân tuyệt đối không được xuất hiện trong config.json bản đóng gói
FORBIDDEN_PATTERNS = (
    r"QuangKhoi",
    r"ThuyTrang",
    r"Baoluan",
    r"KimNga",
    r"01_Project video",
    r"Kho dữ liệu",
    r"2026\.10\.",
    r"2026\.11\.",
)


def _is_mac_flag(is_mac_os=None):
    return (sys.platform == "darwin") if is_mac_os is None else bool(is_mac_os)


def required_models_for_os(is_mac_os=None):
    return REQUIRED_MODELS_MAC if _is_mac_flag(is_mac_os) else REQUIRED_MODELS


def app_executable_path(target_root, is_mac_os=None):
    if _is_mac_flag(is_mac_os):
        return os.path.join(target_root, "FramePilot.app", "Contents", "MacOS", "FramePilot")
    return os.path.join(target_root, "FramePilot.exe")


def _dir_has_files(path):
    if not path or not os.path.exists(path):
        return False
    if os.path.isfile(path):
        return os.path.getsize(path) > 0
    for _r, _d, files in os.walk(path):
        for f in files:
            if not f.endswith(".tmp"):
                return True
    return False


def is_clean_config_dict(cfg, is_mac_os=None):
    """True nếu dict config không chứa bất kỳ tên khách hay đường dẫn project cá nhân nào (và không có đường dẫn Windows nếu là bản macOS)."""
    raw = json.dumps(cfg or {}, ensure_ascii=False)
    if any(re.search(p, raw, re.IGNORECASE) for p in FORBIDDEN_PATTERNS):
        return False
    if is_mac_os is True:
        if re.search(r"[A-Za-z]:\\\\|\.exe\b", raw, re.IGNORECASE):
            return False
    return True


def audit_clean_bundle(bundle_dir, is_mac_os=None):
    """Kiểm tra thư mục gói đóng gói có SẠCH 100% không. Trả về danh sách lỗi (rỗng = sạch tuyệt đối)."""
    issues = []
    if not os.path.isdir(bundle_dir):
        return ["Không thấy thư mục gói: %s" % bundle_dir]
    if os.path.isfile(os.path.join(bundle_dir, "config.json")):
        issues.append("Tồn tại config.json cá nhân trong gói đóng gói")
    for forbidden_dir in ("data", "saas_video"):
        if os.path.isdir(os.path.join(bundle_dir, forbidden_dir)):
            issues.append("Không được đóng gói kèm thư mục: %s" % forbidden_dir)
    cfg_ex = os.path.join(bundle_dir, "config.example.json")
    if os.path.isfile(cfg_ex):
        try:
            with open(cfg_ex, "r", encoding="utf-8-sig") as f:
                cfg_obj = json.load(f)
            if not is_clean_config_dict(cfg_obj, is_mac_os=_is_mac_flag(is_mac_os)):
                issues.append("config.example.json còn chứa dữ liệu cá nhân hoặc đường dẫn sai hệ điều hành")
        except (OSError, ValueError) as e:
            issues.append("config.example.json lỗi đọc JSON: %s" % e)
    else:
        issues.append("Thiếu config.example.json trong gói đóng gói")
    # Quét tên file/thư mục cấp trên xem có lọt dữ liệu project cũ không
    for root, dirs, files in os.walk(bundle_dir):
        # Không đi sâu vào thư mục nhị phân lớn / wheels / models
        dirs[:] = [d for d in dirs if d not in ("models", "wheels", "ai_env", "python", "python_base", "_internal", "FramePilot.app")]
        for name in dirs + files:
            if any(re.search(p, name, re.IGNORECASE) for p in FORBIDDEN_PATTERNS):
                issues.append("Phát hiện tên nhạy cảm trong gói: %s" % os.path.join(root, name))
    return issues


def build_clean_config(target_root, data_root=None, ai_python=None, proxy_root="", is_mac_os=None):
    """Tạo dict config.json sạch 100% (không chứa dữ liệu khách hay đường dẫn project cũ)."""
    mac = _is_mac_flag(is_mac_os)
    droot = data_root or os.path.join(target_root, "data")
    if mac:
        aipy = ai_python or os.path.join(target_root, "ai_env", "bin", "python3")
        return {
            "data_root": droot,
            "proxy_root": proxy_root or "",
            "ai_python": aipy,
            "asr_engine": "auto",
            "resolve": {
                "install_path": "/Applications/DaVinci Resolve/DaVinci Resolve.app",
            },
            "whisper": {
                "exe": "",
                "model": "",
            },
            "cache_root": "",
            "srt_root": "",
            "templates_path": "",
            "camera_luts": {},
        }
    aipy = ai_python or os.path.join(target_root, "ai_env", "Scripts", "python.exe")
    if not os.path.isfile(aipy) and os.path.isfile(r"C:\VideoAI_ai_venv\Scripts\python.exe"):
        aipy = r"C:\VideoAI_ai_venv\Scripts\python.exe"
    constme = os.path.join(target_root, "tools", "whisper", "constme", "cli", "main.exe")
    if not os.path.isfile(constme) and os.path.isfile(r"D:\VideoAI\tools\whisper\constme\cli\main.exe"):
        constme = r"D:\VideoAI\tools\whisper\constme\cli\main.exe"
    return {
        "data_root": droot,
        "proxy_root": proxy_root or "",
        "ai_python": aipy,
        "asr_engine": "auto",
        "resolve": {
            "install_path": r"C:\Program Files\Blackmagic Design\DaVinci Resolve",
        },
        "whisper": {
            "exe": constme,
            "model": os.path.join(droot, "models", "ggml-medium.bin"),
        },
        "cache_root": "",
        "srt_root": "",
        "templates_path": "",
        "camera_luts": {},
    }


def resolve_scripts_utility_dir(is_mac_os=None):
    if _is_mac_flag(is_mac_os):
        return os.path.expanduser(
            "~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
        )
    appdata = os.environ.get("APPDATA") or ""
    if appdata:
        return os.path.join(appdata, "Blackmagic Design", "DaVinci Resolve", "Support", "Fusion", "Scripts", "Utility")
    return ""


def scan_system(pkg_root, target_root=None, target_data_root=None, target_ai_dir=None, is_mac_os=None):
    """Quét toàn bộ plugin, công cụ, môi trường AI và từng model trên máy đích so với gói cài đặt `pkg_root`.
    Trả về dict kế hoạch cài đặt chi tiết (mục nào đã có -> skip, mục nào chưa có -> install)."""
    mac = _is_mac_flag(is_mac_os)
    pkg_root = os.path.abspath(pkg_root)
    target_root = os.path.abspath(target_root or pkg_root)
    if not target_data_root:
        if not mac and os.path.isdir(r"D:\VideoAI\data"):
            target_data_root = r"D:\VideoAI\data"
        else:
            target_data_root = os.path.join(target_root, "data")
    target_data_root = os.path.abspath(target_data_root)
    if not target_ai_dir:
        if not mac and os.path.isdir(r"C:\VideoAI_ai_venv"):
            target_ai_dir = r"C:\VideoAI_ai_venv"
        else:
            target_ai_dir = os.path.join(target_root, "ai_env")
    target_ai_dir = os.path.abspath(target_ai_dir)

    items = []

    # 1. Công cụ ffmpeg & ffprobe
    ff_sys = shutil.which("ffmpeg") and shutil.which("ffprobe")
    ff_bin_name = "ffmpeg" if mac else "ffmpeg.exe"
    ff_dst = os.path.join(target_root, "tools", "ffmpeg", ff_bin_name)
    ff_src = os.path.join(pkg_root, "tools", "ffmpeg")
    has_ff = bool(ff_sys or os.path.isfile(ff_dst))
    items.append({
        "id": "tool_ffmpeg",
        "kind": "plugin",
        "name": "Plugin xử lý hình/tiếng (ffmpeg + ffprobe)",
        "exists": has_ff,
        "has_source": _dir_has_files(ff_src),
        "src": ff_src,
        "dst": os.path.join(target_root, "tools", "ffmpeg"),
        "detail": "Đã có trong máy" if has_ff else "Chưa có trên máy đích",
    })

    # 2. Công cụ Const-me Whisper CLI (chỉ Windows; macOS dùng MLX-Whisper tận dụng GPU chip M)
    if not mac:
        cm_dst = os.path.join(target_root, "tools", "whisper", "constme", "cli", "main.exe")
        cm_alt = r"D:\VideoAI\tools\whisper\constme\cli\main.exe"
        cm_src = os.path.join(pkg_root, "tools", "whisper", "constme")
        has_cm = os.path.isfile(cm_dst) or os.path.isfile(cm_alt)
        items.append({
            "id": "tool_constme",
            "kind": "plugin",
            "name": "Plugin Const-me Whisper CLI (C++ dự phòng)",
            "exists": has_cm,
            "has_source": _dir_has_files(cm_src),
            "src": cm_src,
            "dst": os.path.join(target_root, "tools", "whisper", "constme"),
            "detail": "Đã có sẵn" if has_cm else "Chưa có trên máy đích",
        })

    # 3. Môi trường Python AI
    if mac:
        ai_py_dst = os.path.join(target_ai_dir, "bin", "python3")
        if not os.path.isfile(ai_py_dst):
            ai_py_dst = os.path.join(target_ai_dir, "bin", "python")
        offline_src = os.path.join(pkg_root, "offline_env")
        ai_src = offline_src if _dir_has_files(os.path.join(offline_src, "wheels")) else os.path.join(pkg_root, "ai_env")
        install_mode = "offline_uv" if ai_src == offline_src else "copy"
        ai_label = "Môi trường chạy AI chip M (PyTorch MPS + MLX-Whisper + Silero-VAD + MediaPipe)"
    else:
        ai_py_dst = os.path.join(target_ai_dir, "Scripts", "python.exe")
        if not os.path.isfile(ai_py_dst):
            ai_py_dst = os.path.join(target_ai_dir, "python.exe")
        ai_src = os.path.join(pkg_root, "ai_env")
        install_mode = "copy"
        ai_label = "Môi trường chạy AI (PyTorch + Whisper + Silero-VAD + MediaPipe)"
    has_ai_env = os.path.isfile(ai_py_dst)
    items.append({
        "id": "ai_runtime",
        "kind": "runtime",
        "install_mode": install_mode,
        "name": ai_label,
        "exists": has_ai_env,
        "has_source": _dir_has_files(ai_src),
        "src": ai_src,
        "dst": target_ai_dir,
        "detail": ("Đã có tại %s" % target_ai_dir) if has_ai_env else ("Sẽ cài vào %s" % target_ai_dir),
    })

    # 4. Từng bộ Model AI trong thư mục models/ (trên macOS ưu tiên bản MLX, tự nhận diện bản CT2 dự phòng nếu chép từ Windows sang)
    mac_ct2_fallbacks = {
        "whisper_large_v3_turbo_mlx": "whisper_large_v3_turbo",
        "phowhisper_medium_mlx": "phowhisper_medium_ct2",
    }
    pkg_models_dir = os.path.join(pkg_root, "models")
    dst_models_dir = os.path.join(target_data_root, "models")
    for m_key, m_label in required_models_for_os(mac):
        m_dst = os.path.join(dst_models_dir, m_key)
        m_src = os.path.join(pkg_models_dir, m_key)
        exists = _dir_has_files(m_dst)
        has_src = _dir_has_files(m_src)
        if mac and m_key in mac_ct2_fallbacks:
            alt_key = mac_ct2_fallbacks[m_key]
            alt_dst = os.path.join(dst_models_dir, alt_key)
            alt_src = os.path.join(pkg_models_dir, alt_key)
            if not exists and _dir_has_files(alt_dst):
                exists = True
                m_dst = alt_dst
            if not has_src and _dir_has_files(alt_src):
                has_src = True
                m_src = alt_src
                if not exists:
                    m_dst = alt_dst
        items.append({
            "id": "model_" + m_key,
            "kind": "model",
            "model_key": m_key,
            "name": "Model AI: " + m_label,
            "exists": exists,
            "has_source": has_src,
            "src": m_src,
            "dst": m_dst,
            "detail": "Đã có trên máy -> BỎ QUA" if exists else ("Đóng gói kèm -> SẼ CÀI" if has_src else "Chưa có trong gói"),
        })

    # 5. Menu DaVinci Resolve Studio (Workspace > Scripts > Utility > FramePilot.py)
    scripts_dir = resolve_scripts_utility_dir(mac)
    menu_file = os.path.join(scripts_dir, "FramePilot.py") if scripts_dir else ""
    exe_path = app_executable_path(target_root, mac)
    menu_exists = False
    if menu_file and os.path.isfile(menu_file):
        try:
            with open(menu_file, "r", encoding="utf-8") as f:
                txt = f.read()
            menu_exists = (os.path.normcase(exe_path) in os.path.normcase(txt))
        except OSError:
            menu_exists = False
    items.append({
        "id": "davinci_menu",
        "kind": "menu",
        "name": "Plugin Menu DaVinci Resolve (Workspace > Scripts > FramePilot)",
        "exists": menu_exists,
        "has_source": True,
        "src": exe_path,
        "dst": menu_file,
        "detail": "Đã trỏ đúng bản ứng dụng này" if menu_exists else "Sẽ gắn menu vào DaVinci Resolve",
    })

    return {
        "is_mac": mac,
        "pkg_root": pkg_root,
        "target_root": target_root,
        "target_data_root": target_data_root,
        "target_ai_dir": target_ai_dir,
        "items": items,
    }


def _ensure_posix_exec_bits(dst):
    """Đảm bảo quyền thực thi (+x) trên macOS/POSIX cho ffmpeg/ffprobe và ai_env/bin/* kể cả khi chép từ USB exFAT/FAT32."""
    if os.name == "nt" or not dst or not os.path.exists(dst):
        return
    candidates = []
    if os.path.isfile(dst):
        candidates.append(dst)
    else:
        for sub in ("ffmpeg", "ffprobe"):
            p = os.path.join(dst, sub)
            if os.path.isfile(p):
                candidates.append(p)
        bin_dir = os.path.join(dst, "bin")
        if os.path.isdir(bin_dir):
            for f in os.listdir(bin_dir):
                p = os.path.join(bin_dir, f)
                if os.path.isfile(p):
                    candidates.append(p)
    for p in candidates:
        try:
            os.chmod(p, 0o755)
        except OSError:
            pass


def _copy_tree_safe(src, dst):
    if not src or not dst or not os.path.exists(src):
        return False
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
        _ensure_posix_exec_bits(dst)
        return True
    if os.path.isfile(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        _ensure_posix_exec_bits(dst)
        return True
    os.makedirs(dst, exist_ok=True)
    for entry in os.listdir(src):
        s_item = os.path.join(src, entry)
        d_item = os.path.join(dst, entry)
        if os.path.isdir(s_item):
            shutil.copytree(s_item, d_item, dirs_exist_ok=True)
        else:
            shutil.copy2(s_item, d_item)
    _ensure_posix_exec_bits(dst)
    return True


def write_davinci_exe_launcher(exe_path, dst_script_path):
    """Ghi file launcher FramePilot.py vào thư mục Scripts/Utility của DaVinci trỏ thẳng tới FramePilot.exe."""
    if not dst_script_path:
        return False
    os.makedirs(os.path.dirname(dst_script_path), exist_ok=True)
    code = (
        '# FramePilot - file khởi chạy do bộ cài FramePilot.exe tạo.\n'
        '# TROLY-FILE-QUAY-LAUNCHER\n'
        'import os\n'
        'import subprocess\n\n'
        'EXE = r"%s"\n'
        'args = [EXE]\n'
        'try:\n'
        '    _proj = resolve.GetProjectManager().GetCurrentProject()   # noqa: F821\n'
        '    if _proj:\n'
        '        args += ["--project", _proj.GetName()]\n'
        'except Exception:\n'
        '    pass\n'
        'kw = dict(cwd=os.path.dirname(EXE), close_fds=True)\n'
        'if os.name == "nt":\n'
        '    kw["creationflags"] = 0x00000008 | 0x00000200\n'
        'getattr(subprocess, "Popen")(args, **kw)\n'
    ) % exe_path
    tmp = dst_script_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(code)
    os.replace(tmp, dst_script_path)
    return True


def ensure_clean_config_file(target_root, target_data_root, target_ai_dir, is_mac_os=None):
    """Đảm bảo config.json ở target_root tồn tại và SẠCH 100% (không chứa tên khách/project cũ)."""
    mac = _is_mac_flag(is_mac_os)
    cfg_path = os.path.join(target_root, "config.json")
    if mac:
        ai_py = os.path.join(target_ai_dir, "bin", "python3")
        if not os.path.isfile(ai_py):
            ai_py = os.path.join(target_ai_dir, "bin", "python")
    else:
        ai_py = os.path.join(target_ai_dir, "Scripts", "python.exe")
        if not os.path.isfile(ai_py):
            ai_py = os.path.join(target_ai_dir, "python.exe")
    clean = build_clean_config(target_root, data_root=target_data_root, ai_python=ai_py, is_mac_os=mac)
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8-sig") as f:
                cur = json.load(f) or {}
        except (OSError, ValueError):
            cur = {}
        # Nếu config hiện có chứa đường dẫn project khách cũ thì dọn sạch cache_root / srt_root
        for k in ("cache_root", "srt_root", "templates_path"):
            v = str(cur.get(k) or "")
            if any(re.search(p, v, re.IGNORECASE) for p in FORBIDDEN_PATTERNS):
                cur[k] = ""
        for k, v in clean.items():
            if k not in cur or not cur[k]:
                cur[k] = v
        clean = cur
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    tmp = cfg_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)
    os.replace(tmp, cfg_path)
    return cfg_path


def _install_offline_uv_env(offline_dir, target_ai_dir, out_fn=print):
    """Dựng môi trường ai_env 100% offline trên macOS Apple Silicon bằng binary `uv` + Python standalone + `wheels/`."""
    import troly_proc
    uv_bin = os.path.join(offline_dir, "uv")
    wheels_dir = os.path.join(offline_dir, "wheels")
    req_file = os.path.join(offline_dir, "requirements_ai_mac.txt")
    py_src_dir = os.path.join(offline_dir, "python")
    py_standalone = os.path.join(py_src_dir, "bin", "python3")
    if not os.path.isfile(uv_bin) or not os.path.isdir(wheels_dir):
        out_fn("  [LỖI] Thiếu uv hoặc thư mục wheels/ trong offline_env.")
        return False
    try:
        os.chmod(uv_bin, 0o755)
    except OSError:
        pass
    # Chép Python standalone sang cạnh target_ai_dir để khi rút USB hoặc xóa offline_env/ thì symlink trong ai_env vẫn sống vĩnh viễn
    if os.path.isfile(py_standalone):
        local_py_dir = os.path.abspath(target_ai_dir) + "_python"
        if not os.path.isfile(os.path.join(local_py_dir, "bin", "python3")):
            shutil.copytree(py_src_dir, local_py_dir, symlinks=True, dirs_exist_ok=True)
        _ensure_posix_exec_bits(local_py_dir)
        py_arg = os.path.join(local_py_dir, "bin", "python3")
    else:
        py_arg = shutil.which("python3") or sys.executable
    out_fn("  -> Tạo venv AI offline tại %s ..." % target_ai_dir)
    r1 = troly_proc.chay_an([uv_bin, "venv", "--python", py_arg, target_ai_dir], capture_output=True, text=True, timeout=180)
    if r1.returncode != 0:
        out_fn("  [LỖI] Không tạo được ai_env: %s" % (r1.stderr or r1.stdout or "")[-300:])
        return False
    venv_py = os.path.join(target_ai_dir, "bin", "python3")
    cmd = [uv_bin, "pip", "install", "--python", venv_py, "--offline", "--no-index", "--find-links", wheels_dir]
    if os.path.isfile(req_file):
        cmd += ["-r", req_file]
    else:
        whls = sorted(os.path.join(wheels_dir, f) for f in os.listdir(wheels_dir) if f.endswith(".whl"))
        if not whls:
            out_fn("  [LỖI] Không thấy file .whl nào trong %s" % wheels_dir)
            return False
        cmd += whls
    out_fn("  -> Cài đặt thư viện AI offline (PyTorch MPS + MLX-Whisper + MediaPipe + Silero-VAD)...")
    r2 = troly_proc.chay_an(cmd, capture_output=True, text=True, timeout=900)
    if r2.returncode != 0:
        out_fn("  [LỖI] Cài thư viện offline thất bại: %s" % (r2.stderr or r2.stdout or "")[-400:])
        return False
    return True


def _repair_windows_venv_cfg(target_ai_dir, pkg_root, target_root=None, out_fn=print):
    """Tự động sửa ai_env/pyvenv.cfg trên Windows nếu đường dẫn home cũ (từ máy đóng gói) không tồn tại trên máy đích."""
    if os.name != "nt" or not target_ai_dir:
        return False
    cfg_path = os.path.join(target_ai_dir, "pyvenv.cfg")
    if not os.path.isfile(cfg_path):
        return False
    cur_home = ""
    version_line = "version = 3.10.11"
    include_line = "include-system-site-packages = false"
    try:
        with open(cfg_path, "r", encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                s = line.strip()
                if s.lower().startswith("home") and "=" in s:
                    cur_home = s.split("=", 1)[1].strip().strip('"')
                elif s.lower().startswith("version") and "=" in s:
                    version_line = s
                elif s.lower().startswith("include-system-site-packages") and "=" in s:
                    include_line = s
    except OSError:
        return False

    if cur_home and os.path.isfile(os.path.join(cur_home, "python.exe")):
        return True

    new_home = ""
    t_root = os.path.abspath(target_root or pkg_root or os.path.dirname(target_ai_dir))
    p_root = os.path.abspath(pkg_root) if pkg_root else t_root
    dst_base = os.path.join(t_root, "python_base")
    src_base = os.path.join(p_root, "python_base")
    if os.path.isfile(os.path.join(dst_base, "python.exe")):
        new_home = dst_base
    elif os.path.isfile(os.path.join(src_base, "python.exe")):
        if os.path.normcase(src_base) != os.path.normcase(dst_base):
            if out_fn:
                out_fn("-> Đang chép Python 3.10 portable sang %s ..." % dst_base)
            _copy_tree_safe(src_base, dst_base)
            new_home = dst_base
        else:
            new_home = src_base
    else:
        # Dự phòng: tự tìm Python 3.10 có sẵn trên máy đích
        local_app = os.environ.get("LOCALAPPDATA") or ""
        candidates = [
            os.path.join(local_app, "Programs", "Python", "Python310") if local_app else "",
            r"C:\Python310",
            r"C:\Program Files\Python310",
        ]
        for c in candidates:
            if c and os.path.isfile(os.path.join(c, "python.exe")):
                new_home = c
                break

    if not new_home:
        if out_fn:
            out_fn("  [CẢNH BÁO] Không tìm thấy python_base hoặc Python 3.10 để sửa %s" % cfg_path)
        return False

    try:
        tmp = cfg_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("home = %s\n%s\n%s\n" % (new_home, include_line, version_line))
        os.replace(tmp, cfg_path)
        if out_fn:
            out_fn("-> Đã cập nhật pyvenv.cfg trỏ tới Python portable: %s" % new_home)
        return True
    except OSError as e:
        if out_fn:
            out_fn("  [CẢNH BÁO] Không ghi được %s: %s" % (cfg_path, e))
        return False


def run_setup(plan, ask_fn=None, out_fn=print, dry_run=False):
    """Hiển thị danh sách kiểm tra trùng lặp, hỏi người dùng xác nhận trước khi cài, bỏ qua mọi mục đã có."""
    mac = _is_mac_flag(plan.get("is_mac"))
    out_fn("=" * 68)
    out_fn("  FRAMEPILOT v0.4.0 (%s) - KIỂM TRA & CÀI ĐẶT TRÊN MÁY" % ("macOS Apple Silicon" if mac else "Windows"))
    out_fn("=" * 68)
    out_fn("Thư mục ứng dụng : %s" % plan["target_root"])
    out_fn("Thư mục dữ liệu  : %s" % plan["target_data_root"])
    out_fn("Môi trường AI    : %s" % plan["target_ai_dir"])
    out_fn("-" * 68)

    to_install = []
    skipped = []
    for it in plan["items"]:
        if it["exists"]:
            skipped.append(it)
            out_fn("  [ĐÃ CÓ -> BỎ QUA]  %s" % it["name"])
        elif it["has_source"]:
            to_install.append(it)
            out_fn("  [CHƯA CÓ -> CÀI]   %s" % it["name"])
        else:
            out_fn("  [KHÔNG KÈM GÓI]    %s" % it["name"])

    out_fn("-" * 68)
    out_fn("Tổng kết: %d mục đã có sẵn (sẽ bỏ qua), %d mục mới cần cài." % (len(skipped), len(to_install)))

    if dry_run:
        return {"installed": [], "skipped": [x["id"] for x in skipped], "cancelled": False, "dry_run": True}

    if to_install and ask_fn is not None:
        ans = str(ask_fn("Bạn có đồng ý cài %d mục chưa có (các mục đã có sẽ tự động bỏ qua)? [Y/n]: " % len(to_install)) or "").strip().lower()
        if ans and ans not in ("y", "yes", "c", "co", "có", "ok", "1"):
            out_fn("Đã huỷ cài đặt theo yêu cầu.")
            return {"installed": [], "skipped": [x["id"] for x in skipped], "cancelled": True}

    installed = []
    for it in to_install:
        out_fn("-> Đang cài: %s ..." % it["name"])
        if it["kind"] == "menu":
            exe_p = app_executable_path(plan["target_root"], mac)
            if write_davinci_exe_launcher(exe_p, it["dst"]):
                installed.append(it["id"])
        elif it["kind"] == "runtime" and it.get("install_mode") == "offline_uv":
            if _install_offline_uv_env(it["src"], it["dst"], out_fn=out_fn):
                installed.append(it["id"])
        else:
            if _copy_tree_safe(it["src"], it["dst"]):
                installed.append(it["id"])

    if not mac:
        _repair_windows_venv_cfg(plan["target_ai_dir"], plan["pkg_root"], target_root=plan["target_root"], out_fn=out_fn)

    os.makedirs(plan["target_data_root"], exist_ok=True)
    cfg_p = ensure_clean_config_file(plan["target_root"], plan["target_data_root"], plan["target_ai_dir"], is_mac_os=mac)
    out_fn("-> Đã chuẩn hóa file cấu hình sạch: %s" % cfg_p)
    out_fn("=" * 68)
    out_fn("HOÀN TẤT! Đã bỏ qua %d mục trùng có sẵn, đã cài mới %d mục." % (len(skipped), len(installed)))
    return {"installed": installed, "skipped": [x["id"] for x in skipped], "cancelled": False, "config": cfg_p}


def _attach_console_or_gui_ask():
    """Nếu chạy từ FramePilot.exe (--windowed), thử gắn vào console cha; nếu không có stdin thì hỏi qua MessageBoxW."""
    if os.name == "nt" and getattr(sys, "frozen", False):
        try:
            import ctypes
            if ctypes.windll.kernel32.AttachConsole(-1):
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
                sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
        except Exception:
            pass

    def _ask(prompt_text):
        try:
            if sys.stdin and not sys.stdin.closed:
                return input(prompt_text)
        except Exception:
            pass
        if os.name == "nt":
            try:
                import ctypes
                # MB_YESNO (0x04) | MB_ICONQUESTION (0x20) -> IDYES = 6
                r = ctypes.windll.user32.MessageBoxW(None, prompt_text, "FramePilot - Cài đặt", 0x24)
                return "y" if r == 6 else "n"
            except Exception:
                pass
        elif sys.platform == "darwin":
            try:
                import troly_proc
                script = (
                    'on run argv\n'
                    '  set r to button returned of (display dialog (item 1 of argv) with title "FramePilot - Cài đặt" '
                    'buttons {"Huỷ", "Cài đặt"} default button 2)\n'
                    '  return r\n'
                    'end run'
                )
                p = troly_proc.chay_an(["osascript", "-e", script, str(prompt_text)], capture_output=True, text=True, timeout=120)
                if p.returncode == 0:
                    return "y" if "Cài đặt" in (p.stdout or "") else "n"
            except Exception:
                pass
        return "y"

    return _ask


def main(argv=None):
    ask_fn = _attach_console_or_gui_ask()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Trình cài đặt thông minh FramePilot (tự bỏ qua plugin/model đã có)")
    ap.add_argument("--setup", action="store_true", help="Chạy chế độ kiểm tra & cài đặt")
    ap.add_argument("--pkg-root", default="", help="Thư mục gốc của gói đóng gói")
    ap.add_argument("--target-root", default="", help="Thư mục đích cài FramePilot")
    ap.add_argument("--data-root", default="", help="Thư mục lưu dữ liệu & models trên máy đích")
    ap.add_argument("--ai-dir", default="", help="Thư mục môi trường Python AI trên máy đích")
    ap.add_argument("--check-only", action="store_true", help="Chỉ kiểm tra mục nào trùng/chưa có, không cài")
    ap.add_argument("--yes", action="store_true", help="Tự động đồng ý cài các mục chưa có (bỏ qua mục đã có)")
    a = ap.parse_args(argv)

    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if sys.platform == "darwin":
            try:
                import troly_env
                default_pkg = troly_env._mac_bundle_parent(exe_dir)
            except Exception:
                default_pkg = exe_dir
        else:
            default_pkg = exe_dir
    else:
        default_pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pkg_root = a.pkg_root or default_pkg
    plan = scan_system(
        pkg_root,
        target_root=a.target_root or pkg_root,
        target_data_root=a.data_root or None,
        target_ai_dir=a.ai_dir or None,
    )
    ask = None if a.yes else ask_fn
    run_setup(plan, ask_fn=ask, out_fn=print, dry_run=a.check_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
