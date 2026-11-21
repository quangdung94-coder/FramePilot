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
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=troly_sync",
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
    out = os.path.join(ROOT, "dist", "FramePilot", "FramePilot.exe" if os.name == "nt" else "FramePilot")
    print("Đóng gói xong:", out)


if __name__ == "__main__":
    main()
