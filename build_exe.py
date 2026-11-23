"""build_exe.py - Đóng gói FramePilot thành bản chạy độc lập (dist/FramePilot/FramePilot.exe) song song bản Python.

Cách chạy:
  & C:\\VideoAI_venv\\Scripts\\python.exe build_exe.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "app")
ENTRY = os.path.join(APP, "panel_troly_web.py")
ICO = os.path.join(APP, "assets", "framepilot.ico")
SEP = ";" if os.name == "nt" else ":"


def main():
    try:
        import PyInstaller.__main__ as pyi
    except ImportError:
        sys.exit("Chưa có PyInstaller. Cài bằng: pip install pyinstaller")

    args = [
        ENTRY,
        "--name=FramePilot",
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--paths=" + APP,
        "--add-data=" + os.path.join(APP, "troly_web") + SEP + "troly_web",
        "--add-data=" + os.path.join(APP, "assets") + SEP + "assets",
        "--add-data=" + os.path.join(APP, "troly_asr_worker.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "troly_face_worker.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "troly_audio_events.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "troly_diarize_worker.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "troly_vad_worker.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "troly_ai.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "troly_thumbs.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "troly_core.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "troly_env.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "troly_proc.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "troly_src.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "troly_setup.py") + SEP + ".",
        "--add-data=" + os.path.join(APP, "wedding_phrases.json") + SEP + ".",
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=troly_sync",
        "--hidden-import=troly_setup",
        "--exclude-module=torch",
        "--exclude-module=torchvision",
        "--exclude-module=torchaudio",
        "--exclude-module=open_clip",
        "--exclude-module=faster_whisper",
        "--exclude-module=scipy",
        "--exclude-module=matplotlib",
        "--distpath=" + os.path.join(ROOT, "dist"),
        "--workpath=" + os.path.join(ROOT, "build"),
        "--specpath=" + ROOT,
    ]
    if os.path.isfile(ICO) and os.name == "nt":
        args.append("--icon=" + ICO)
    pyi.run(args)
    dist_dir = os.path.join(ROOT, "dist", "FramePilot")
    stage_portable_bundle(dist_dir)
    out = os.path.join(dist_dir, "FramePilot.exe" if os.name == "nt" else "FramePilot")
    print("Đóng gói xong (v0.4.0 - 22h01, bản sạch + kèm plugin/model + bộ cài thông minh):", out)


def _ensure_junction(link_path, target_path):
    """Tạo junction (liên kết thư mục Windows) cho models / ai_env để gói đóng gói có đủ tài nguyên mà không tốn gấp đôi ổ cứng."""
    if not os.path.isdir(target_path):
        return False
    if os.path.exists(link_path):
        return True
    if os.name == "nt":
        import subprocess
        os.makedirs(os.path.dirname(link_path), exist_ok=True)
        r = subprocess.run(["cmd", "/c", "mklink", "/J", link_path, target_path], capture_output=True, text=True)
        return r.returncode == 0
    return False


def stage_portable_bundle(dist_dir):
    """Chuẩn bị gói cài đặt SẠCH 100% (không chứa dữ liệu project khách cũ), kèm plugin (ffmpeg, ffprobe, constme),
    models AI, môi trường AI và file CaiDat_MayMoi.bat (tự hỏi trước và bỏ qua mục đã có trên máy đích)."""
    import json
    import shutil
    sys.path.insert(0, APP)
    import troly_setup as tset

    if not os.path.isdir(dist_dir):
        return

    # 1. Tuyệt đối không để config.json cá nhân hoặc dữ liệu khách cũ trong bản đóng gói
    cfg_in_dist = os.path.join(dist_dir, "config.json")
    if os.path.isfile(cfg_in_dist):
        os.remove(cfg_in_dist)

    # Ghi config.example.json sạch 100%
    clean_cfg = tset.build_clean_config(dist_dir)
    with open(os.path.join(dist_dir, "config.example.json"), "w", encoding="utf-8") as f:
        json.dump(clean_cfg, f, ensure_ascii=False, indent=2)

    # Chép file hướng dẫn cài đặt & bật plugin DaVinci vào bản đóng gói
    guide_src = os.path.join(ROOT, "HUONG_DAN_CAI_DAT.txt")
    if os.path.isfile(guide_src):
        shutil.copy2(guide_src, os.path.join(dist_dir, "HUONG_DAN_CAI_DAT.txt"))

    # 2. Đóng gói kèm plugin ffmpeg.exe & ffprobe.exe
    ff_dir = os.path.join(dist_dir, "tools", "ffmpeg")
    os.makedirs(ff_dir, exist_ok=True)
    for bname in ("ffmpeg", "ffprobe"):
        src_bin = shutil.which(bname)
        dst_bin = os.path.join(ff_dir, bname + ".exe")
        if src_bin and os.path.isfile(src_bin) and not os.path.isfile(dst_bin):
            shutil.copy2(src_bin, dst_bin)

    # 3. Đóng gói kèm plugin Const-me Whisper CLI
    cm_src = r"D:\VideoAI\tools\whisper\constme"
    cm_dst = os.path.join(dist_dir, "tools", "whisper", "constme")
    if os.path.isdir(cm_src):
        for sub in ("cli", "lib"):
            s_sub = os.path.join(cm_src, sub)
            d_sub = os.path.join(cm_dst, sub)
            if os.path.isdir(s_sub) and not os.path.isdir(d_sub):
                shutil.copytree(s_sub, d_sub, dirs_exist_ok=True)

    # 4. Nối thư mục 9 bộ Model AI (D:\VideoAI\data\models -> dist\FramePilot\models)
    models_src = r"D:\VideoAI\data\models"
    models_dst = os.path.join(dist_dir, "models")
    if os.path.isdir(models_src) and not os.path.exists(models_dst):
        os.makedirs(models_dst, exist_ok=True)
        for m_key, _m_lbl in tset.REQUIRED_MODELS:
            s_m = os.path.join(models_src, m_key)
            d_m = os.path.join(models_dst, m_key)
            if os.path.isdir(s_m):
                _ensure_junction(d_m, s_m)

    # 5. Nối môi trường chạy AI (C:\VideoAI_ai_venv -> dist\FramePilot\ai_env)
    ai_src = r"C:\VideoAI_ai_venv"
    ai_dst = os.path.join(dist_dir, "ai_env")
    if os.path.isdir(ai_src):
        _ensure_junction(ai_dst, ai_src)

    # 5b. Đóng gói kèm Python 3.10 portable base (python_base/) để ai_env chạy được trên máy mới chưa cài Python
    py_base_src = ""
    ai_cfg = os.path.join(ai_src, "pyvenv.cfg")
    if os.path.isfile(ai_cfg):
        try:
            with open(ai_cfg, "r", encoding="utf-8-sig", errors="replace") as f:
                for line in f:
                    s = line.strip()
                    if s.lower().startswith("home") and "=" in s:
                        cand = s.split("=", 1)[1].strip().strip('"')
                        if os.path.isfile(os.path.join(cand, "python.exe")):
                            py_base_src = cand
                        break
        except OSError:
            pass
    if not py_base_src and os.path.isfile(os.path.join(sys.base_prefix, "python.exe")):
        py_base_src = sys.base_prefix
    py_base_dst = os.path.join(dist_dir, "python_base")
    if py_base_src and not os.path.isfile(os.path.join(py_base_dst, "python.exe")):
        os.makedirs(py_base_dst, exist_ok=True)
        for fname in ("python.exe", "pythonw.exe", "python3.dll", "python310.dll", "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"):
            fp = os.path.join(py_base_src, fname)
            if os.path.isfile(fp):
                shutil.copy2(fp, os.path.join(py_base_dst, fname))
        for dname in ("DLLs", "include", "libs"):
            dp = os.path.join(py_base_src, dname)
            if os.path.isdir(dp):
                shutil.copytree(dp, os.path.join(py_base_dst, dname), dirs_exist_ok=True)
        lib_src = os.path.join(py_base_src, "Lib")
        if os.path.isdir(lib_src):
            shutil.copytree(
                lib_src,
                os.path.join(py_base_dst, "Lib"),
                ignore=shutil.ignore_patterns("site-packages", "test", "__pycache__"),
                dirs_exist_ok=True,
            )
            os.makedirs(os.path.join(py_base_dst, "Lib", "site-packages"), exist_ok=True)

    # 6. Tạo file bấm đúp CaiDat_MayMoi.bat (tự sửa pyvenv.cfg portable -> quét mục trùng -> hỏi xác nhận -> bỏ qua mục đã có)
    bat_path = os.path.join(dist_dir, "CaiDat_MayMoi.bat")
    bat_content = """@echo off
setlocal EnableExtensions
chcp 65001 >nul
title FramePilot v0.4.0 (22h01) - Cai Dat ^& Kiem Tra Phu Thuoc
cd /d "%~dp0"

set "PKG_ROOT=%~dp0"
if "%PKG_ROOT:~-1%"=="\\" set "PKG_ROOT=%PKG_ROOT:~0,-1%"

echo ====================================================================
echo   FRAMEPILOT v0.4.0 (22h01) - BO CAI DAT THONG MINH CHO MAY MOI
echo   (Tu dong phat hien plugin/model da co san tren may de BO QUA)
echo ====================================================================
echo.

REM Tu dong va pyvenv.cfg neu ai_env dang tro ve duong dan Python may cu
if exist "%PKG_ROOT%\\ai_env\\Scripts\\python.exe" (
    "%PKG_ROOT%\\ai_env\\Scripts\\python.exe" -c "import sys" >nul 2>&1
    if errorlevel 1 (
        if exist "%PKG_ROOT%\\python_base\\python.exe" (
            echo [Sua tu dong] Dang cap nhat duong dan Python portable cho ai_env...
            "%PKG_ROOT%\\python_base\\python.exe" -X utf8 -c "import os, sys; p=sys.argv[1]; cfg=os.path.join(p,'ai_env','pyvenv.cfg'); open(cfg,'w',encoding='utf-8').write('home = '+os.path.join(p,'python_base')+'\\ninclude-system-site-packages = false\\nversion = 3.10.11\\n')" "%PKG_ROOT%"
        )
    )
)

REM Chon Python hoat dong duoc de chay trinh cai dat
set "SETUP_PY="
if exist "%PKG_ROOT%\\ai_env\\Scripts\\python.exe" (
    "%PKG_ROOT%\\ai_env\\Scripts\\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "SETUP_PY=%PKG_ROOT%\\ai_env\\Scripts\\python.exe"
)
if not defined SETUP_PY if exist "%PKG_ROOT%\\python_base\\python.exe" (
    "%PKG_ROOT%\\python_base\\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "SETUP_PY=%PKG_ROOT%\\python_base\\python.exe"
)
if not defined SETUP_PY if exist "C:\\VideoAI_ai_venv\\Scripts\\python.exe" (
    "C:\\VideoAI_ai_venv\\Scripts\\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "SETUP_PY=C:\\VideoAI_ai_venv\\Scripts\\python.exe"
)
if not defined SETUP_PY if exist "C:\\VideoAI_venv\\Scripts\\python.exe" (
    "C:\\VideoAI_venv\\Scripts\\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "SETUP_PY=C:\\VideoAI_venv\\Scripts\\python.exe"
)

if defined SETUP_PY (
    "%SETUP_PY%" -X utf8 "%PKG_ROOT%\\_internal\\troly_setup.py" --pkg-root "%PKG_ROOT%"
) else (
    "%PKG_ROOT%\\FramePilot.exe" --setup --pkg-root "%PKG_ROOT%"
)

echo.
pause
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)


if __name__ == "__main__":
    main()
