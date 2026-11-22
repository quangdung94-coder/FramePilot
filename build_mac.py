#!/usr/bin/env python3
"""build_mac.py - Đóng gói FramePilot bản SẠCH 100% cho macOS Apple Silicon (chip M1/M2/M3/M4 - arm64).

Tạo gói tại: dist/FramePilot_Mac_ARM64/ gồm:
  - FramePilot.app (PyInstaller arm64, đóng gói đủ 12 file worker/module + troly_web + assets + wedding_phrases.json)
  - config.example.json sạch 100% (không chứa đường dẫn Windows hay dữ liệu project cũ)
  - tools/ffmpeg/ffmpeg & ffprobe (arm64 nếu có sẵn trên máy build)
  - CaiDat_MayMoi.command (bộ cài thông minh 100% offline: gỡ Gatekeeper, quét máy đích, bỏ qua mục đã có, cài ai_env từ offline_env/)
  - HUONG_DAN_CAI_DAT_MAC.txt & CHECKLIST_TEST_MAC.txt
  - Tự động chạy audit_clean_bundle() đảm bảo SẠCH 100% trước khi kết thúc.

Cách chạy trên macOS Apple Silicon (hoặc GitHub Actions macos-14):
  python3 build_mac.py
  python3 build_mac.py --stage-only   # chỉ test bước đóng gói sạch (không chạy PyInstaller)
"""
import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "app")
ENTRY = os.path.join(APP, "panel_troly_web.py")
ICO = os.path.join(APP, "assets", "framepilot.ico")
ICNS = os.path.join(APP, "assets", "framepilot.icns")

WORKER_DATA_FILES = (
    "troly_asr_worker.py",
    "troly_face_worker.py",
    "troly_audio_events.py",
    "troly_diarize_worker.py",
    "troly_vad_worker.py",
    "troly_ai.py",
    "troly_thumbs.py",
    "troly_core.py",
    "troly_env.py",
    "troly_proc.py",
    "troly_src.py",
    "troly_setup.py",
    "wedding_phrases.json",
)


def build_icns_from_ico(ico_path, out_icns):
    """Chuyển framepilot.ico -> framepilot.icns trên macOS bằng Pillow + iconutil (nếu chưa có .icns)."""
    if os.path.isfile(out_icns):
        return out_icns
    if sys.platform != "darwin" or not os.path.isfile(ico_path) or not shutil.which("iconutil"):
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    tmp = tempfile.mkdtemp(prefix="fp_icon_")
    iconset = os.path.join(tmp, "framepilot.iconset")
    os.makedirs(iconset, exist_ok=True)
    try:
        im = Image.open(ico_path).convert("RGBA")
        sizes = (
            (16, "icon_16x16.png"),
            (32, "icon_16x16@2x.png"),
            (32, "icon_32x32.png"),
            (64, "icon_32x32@2x.png"),
            (128, "icon_128x128.png"),
            (256, "icon_128x128@2x.png"),
            (256, "icon_256x256.png"),
            (512, "icon_256x256@2x.png"),
            (512, "icon_512x512.png"),
            (1024, "icon_512x512@2x.png"),
        )
        for sz, fname in sizes:
            im.resize((sz, sz), Image.LANCZOS).save(os.path.join(iconset, fname), "PNG")
        r = subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out_icns], capture_output=True, text=True)
        return out_icns if r.returncode == 0 and os.path.isfile(out_icns) else None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pyinstaller_args(icns_path=None, dist_dir=None, work_dir=None):
    """Danh sách tham số PyInstaller chuẩn cho macOS Apple Silicon (arm64)."""
    sep = ":"
    args = [
        ENTRY,
        "--name=FramePilot",
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--target-arch=arm64",
        "--osx-bundle-identifier=com.framepilot.app",
        "--paths=" + APP,
        "--add-data=" + os.path.join(APP, "troly_web") + sep + "troly_web",
        "--add-data=" + os.path.join(APP, "assets") + sep + "assets",
    ]
    for fname in WORKER_DATA_FILES:
        args.append("--add-data=" + os.path.join(APP, fname) + sep + ".")
    args += [
        "--hidden-import=troly_sync",
        "--hidden-import=troly_setup",
        "--hidden-import=troly_hw",
        "--hidden-import=webview.platforms.cocoa",
        "--exclude-module=torch",
        "--exclude-module=torchvision",
        "--exclude-module=torchaudio",
        "--exclude-module=open_clip",
        "--exclude-module=faster_whisper",
        "--exclude-module=mlx",
        "--exclude-module=mlx_whisper",
        "--exclude-module=scipy",
        "--exclude-module=matplotlib",
        "--distpath=" + (dist_dir or os.path.join(ROOT, "dist")),
        "--workpath=" + (work_dir or os.path.join(ROOT, "build_mac")),
        "--specpath=" + ROOT,
    ]
    if icns_path and os.path.isfile(icns_path):
        args.append("--icon=" + icns_path)
    return args


def _make_executable(path):
    try:
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def stage_clean_mac_bundle(bundle_dir, app_bundle_src=None, include_ffmpeg=True):
    """Chuẩn bị thư mục gói cài đặt macOS Apple Silicon SẠCH 100% tại `bundle_dir`."""
    sys.path.insert(0, APP)
    import troly_setup as tset

    os.makedirs(bundle_dir, exist_ok=True)

    # 1. Xóa tuyệt đối config.json cá nhân hoặc dữ liệu cũ nếu có
    for bad_file in ("config.json", "hoc_tu_cu.local.json"):
        p = os.path.join(bundle_dir, bad_file)
        if os.path.isfile(p):
            os.remove(p)
    for bad_dir in ("data", "saas_video"):
        p = os.path.join(bundle_dir, bad_dir)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)

    # 2. Chép FramePilot.app vào gói (nếu được truyền từ dist/)
    if app_bundle_src and os.path.isdir(app_bundle_src):
        dst_app = os.path.join(bundle_dir, "FramePilot.app")
        if os.path.abspath(app_bundle_src) != os.path.abspath(dst_app):
            if os.path.isdir(dst_app):
                shutil.rmtree(dst_app)
            shutil.copytree(app_bundle_src, dst_app, symlinks=True)

    # 3. Ghi config.example.json sạch 100% chuẩn macOS (không chứa đường dẫn máy build hay C:\, D:\ hay tên khách cũ)
    clean_cfg = tset.build_clean_config("", data_root="", ai_python="", is_mac_os=True)
    clean_cfg["data_root"] = ""
    clean_cfg["ai_python"] = ""
    with open(os.path.join(bundle_dir, "config.example.json"), "w", encoding="utf-8") as f:
        json.dump(clean_cfg, f, ensure_ascii=False, indent=2)

    # 4. Chép tài liệu hướng dẫn cài đặt & checklist test macOS
    for doc in ("HUONG_DAN_CAI_DAT_MAC.txt", "CHECKLIST_TEST_MAC.txt", "requirements_ai_mac.txt"):
        src_doc = os.path.join(ROOT, doc)
        if os.path.isfile(src_doc):
            shutil.copy2(src_doc, os.path.join(bundle_dir, doc))

    # 5. Đóng gói kèm ffmpeg & ffprobe arm64 (nếu có sẵn trên máy build macOS)
    if include_ffmpeg and sys.platform == "darwin":
        ff_dir = os.path.join(bundle_dir, "tools", "ffmpeg")
        os.makedirs(ff_dir, exist_ok=True)
        for bname in ("ffmpeg", "ffprobe"):
            src_bin = shutil.which(bname)
            dst_bin = os.path.join(ff_dir, bname)
            if src_bin and os.path.isfile(src_bin) and not os.path.isfile(dst_bin):
                shutil.copy2(src_bin, dst_bin)
                _make_executable(dst_bin)

    # 6. Tạo file bấm đúp CaiDat_MayMoi.command (gỡ Gatekeeper + gọi troly_setup.py --setup)
    cmd_path = os.path.join(bundle_dir, "CaiDat_MayMoi.command")
    cmd_content = """#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "===================================================================="
echo "  FRAMEPILOT v0.4.0 (macOS Apple Silicon) - BO CAI DAT THONG MINH"
echo "  (100% Offline - Tu dong phat hien muc da co de BO QUA)"
echo "===================================================================="
echo ""

# Go co Gatekeeper quarantine (neu co) de FramePilot.app & tools chay muot
xattr -cr "$DIR" 2>/dev/null || true

APP_BIN="$DIR/FramePilot.app/Contents/MacOS/FramePilot"
SETUP_PY="$DIR/FramePilot.app/Contents/Frameworks/troly_setup.py"
[ ! -f "$SETUP_PY" ] && SETUP_PY="$DIR/FramePilot.app/Contents/Resources/troly_setup.py"

if [ -x "$DIR/ai_env/bin/python3" ] && [ -f "$SETUP_PY" ]; then
    "$DIR/ai_env/bin/python3" -X utf8 "$SETUP_PY" --pkg-root "$DIR"
elif [ -x "$APP_BIN" ]; then
    "$APP_BIN" --setup --pkg-root "$DIR"
elif command -v python3 >/dev/null 2>&1 && [ -f "$SETUP_PY" ]; then
    python3 -X utf8 "$SETUP_PY" --pkg-root "$DIR"
else
    echo "[LOI] Khong tim thay FramePilot.app trong $DIR"
    exit 1
fi

echo ""
read -r -p "Bam Enter de dong cua so..." _
"""
    with open(cmd_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(cmd_content)
    _make_executable(cmd_path)

    # 7. Kiểm toán tự động: đảm bảo gói SẠCH 100% (0 dữ liệu cá nhân, 0 đường dẫn Windows)
    issues = tset.audit_clean_bundle(bundle_dir, is_mac_os=True)
    if issues:
        raise RuntimeError("Gói đóng gói macOS KHÔNG SẠCH:\n - " + "\n - ".join(issues))
    return bundle_dir


def main(argv=None):
    ap = argparse.ArgumentParser(description="Đóng gói FramePilot bản sạch cho macOS Apple Silicon (arm64)")
    ap.add_argument("--stage-only", action="store_true", help="Chỉ chạy bước stage + kiểm tra bản sạch (không chạy PyInstaller)")
    ap.add_argument("--out-dir", default="", help="Thư mục đích của gói (mặc định dist/FramePilot_Mac_ARM64)")
    a = ap.parse_args(argv)

    bundle_dir = a.out_dir or os.path.join(ROOT, "dist", "FramePilot_Mac_ARM64")
    app_src = None

    if not a.stage_only:
        if sys.platform != "darwin":
            sys.exit("PyInstaller chỉ build được FramePilot.app trên máy macOS (hoặc GitHub Actions macos-14).")
        try:
            import PyInstaller.__main__ as pyi
        except ImportError:
            sys.exit("Chưa có PyInstaller. Cài bằng: pip install -r requirements_mac.txt")

        icns_path = build_icns_from_ico(ICO, ICNS)
        pyi.run(pyinstaller_args(icns_path=icns_path))
        app_src = os.path.join(ROOT, "dist", "FramePilot.app")
        if not os.path.isdir(app_src):
            sys.exit("Không thấy dist/FramePilot.app sau khi chạy PyInstaller.")

    stage_clean_mac_bundle(bundle_dir, app_bundle_src=app_src)
    print("Đóng gói macOS Apple Silicon SẠCH 100% hoàn tất:", bundle_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
