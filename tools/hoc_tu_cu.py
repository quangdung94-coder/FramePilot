r"""
hoc_tu_cu.py - Học thói quen dựng từ các project cũ. CHẠY BẰNG MỘT LỆNH:
    & C:\VideoAI_venv\Scripts\python.exe tools\hoc_tu_cu.py
Hỏi xác nhận (gõ Y) rồi mới chạy. Bị ngắt thì chạy lại đúng lệnh đó: tool nhớ tiến độ và làm tiếp.

CHỈ ĐỌC: không ghi Media Pool/In-Out, không sửa project gốc, không đụng file video.
Cách đọc an toàn: ExportProject bản gốc ra .drp (chỉ đọc), nhập thành project TẠM "_hoc_tu_cu_<mã>", đọc project tạm, rồi xóa project tạm
(chỉ xóa project tên bắt đầu "_hoc_tu_cu_" do chính tool tạo). Project đang mở được lưu rồi mở lại đúng như cũ.
Video: chỉ lấy mẫu thưa bằng ffmpeg (cửa sổ 1,5 giây, vài chục chỗ mỗi clip), không chạy model AI.
Tên khách thật chỉ nằm trong hoc_tu_cu.local.json (không lên Git). Kết quả: <data_root>\hoc_tu_cu\.

Tuỳ chọn: --thu MÃ (chỉ một project, ví dụ LV_B)  --mau-toi-da N (thử: chỉ lấy mẫu N clip)  --gio-toi-da H (dừng lấy mẫu sau H giờ)
          --chi-phan-tich (không đụng DaVinci/ổ đĩa, chỉ phân tích lại dữ liệu đã thu)  --giu-tam (không xóa project tạm)
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, HERE)
import troly_env                                   # noqa: E402
import hoc_tu_cu_phan_tich as pt                   # noqa: E402

TMP_PREFIX = "_hoc_tu_cu_"
WIN = 1.5


def log(msg):
    print(datetime.datetime.now().strftime("%H:%M:%S"), msg, flush=True)


def load_local():
    p = os.path.join(ROOT, "hoc_tu_cu.local.json")
    if not os.path.exists(p):
        sys.exit("Thiếu hoc_tu_cu.local.json (xem hoc_tu_cu.local.example.json).")
    with open(p, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def jload(p, default=None):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def jsave(p, d):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


# ----------------------------------------------------------------------------- DaVinci (chỉ đọc)
KEEP = ("File Name", "File Path", "FPS", "Frames", "Duration", "Date Created", "Date Modified", "Resolution", "Type",
        "Camera Serial #", "Camera ID", "Camera Type", "Camera #", "Start TC")


def walk(folder, path, out):
    for c in folder.GetClipList() or []:
        out.append((path, c))
    for sf in folder.GetSubFolderList() or []:
        walk(sf, path + "/" + sf.GetName(), out)
    return out


def dump_project(proj):
    root = proj.GetMediaPool().GetRootFolder()
    clips = []
    for bp, c in walk(root, root.GetName(), []):
        p = c.GetClipProperty() or {}
        t = p.get("Type") or ""
        if "Video" not in t or "Timeline" in t or "Compound" in t:
            continue
        try:
            m = c.GetMarkInOut() or {}
            v = m.get("video") if isinstance(m, dict) else None
            mark = [int(v["in"]), int(v["out"])] if isinstance(v, dict) and "in" in v and "out" in v else None
        except Exception:                                   # noqa: BLE001
            mark = None
        path = p.get("File Path") or ""
        clips.append({"uid": c.GetUniqueId(), "bin": bp, "props": {k: p.get(k) for k in KEEP if p.get(k) is not None},
                      "mark": mark, "online": bool(path) and os.path.exists(path), "path": path})
    tls = []
    for i in range(1, (proj.GetTimelineCount() or 0) + 1):
        tl = proj.GetTimelineByIndex(i)
        items, others = [], []
        for tr in range(1, (tl.GetTrackCount("video") or 0) + 1):
            for it in tl.GetItemListInTrack("video", tr) or []:
                mp = it.GetMediaPoolItem()
                if mp is None:
                    others.append({"track": tr, "start": it.GetStart(), "end": it.GetEnd(), "name": it.GetName()})
                    continue
                items.append({"uid": mp.GetUniqueId(), "track": tr, "start": it.GetStart(), "end": it.GetEnd(),
                              "dur": it.GetDuration(), "src_start_f": it.GetSourceStartFrame(),
                              "src_end_f": it.GetSourceEndFrame()})
        try:
            markers = [{"frame": int(k), "name": (v or {}).get("name", ""), "color": (v or {}).get("color", "")}
                       for k, v in (tl.GetMarkers() or {}).items()]
        except Exception:                                   # noqa: BLE001
            markers = []
        tls.append({"name": tl.GetName(), "fps": tl.GetSetting("timelineFrameRate"), "start_frame": tl.GetStartFrame(),
                    "items": items, "others": others, "markers": markers})
    return {"clips": clips, "timelines": tls}


def stage_resolve(todo, local, ddir, state, keep_tmp):
    """todo: [mã] cần export+dump. Một phiên DaVinci cho tất cả."""
    r = troly_env.connect_resolve()
    pm = r.GetProjectManager()
    cur = pm.GetCurrentProject()
    orig = cur.GetName() if cur else None
    log("Project đang mở: %s" % ("(có)" if orig else "(không)"))
    if cur and not pm.SaveProject():
        sys.exit("SaveProject project đang mở lỗi, dừng (không đụng gì).")
    made = []
    try:
        for code in todo:
            real = local["projects"][code]
            st = state.setdefault(code, {})
            drp = os.path.join(ddir, code + ".drp")
            if not os.path.exists(drp):
                log("%s: xuất bản sao .drp (chỉ đọc project gốc)" % code)
                if not pm.ExportProject(real, drp, False) or not os.path.exists(drp):
                    log("%s: ExportProject lỗi (tên project có đúng không, có đang ở thư mục khác trong Project Manager?)" % code)
                    st["loi"] = "export"
                    continue
            tmp = TMP_PREFIX + code
            if tmp not in (pm.GetProjectListInCurrentFolder() or []):
                if not pm.ImportProject(drp, tmp):
                    log("%s: ImportProject lỗi" % code)
                    st["loi"] = "import"
                    continue
                made.append(tmp)
            p = pm.LoadProject(tmp)
            now = pm.GetCurrentProject()
            if not p or not now or now.GetName() != tmp:
                log("%s: không mở được project tạm" % code)
                st["loi"] = "load"
                continue
            t0 = time.time()
            d = dump_project(now)
            jsave(os.path.join(ddir, code + "_dump.json"), d)
            st["dump"] = True
            st.pop("loi", None)
            jsave(os.path.join(ddir, "tien_do.json"), state)
            log("%s: đọc xong %d clip, %d timeline, %.0fs" % (code, len(d["clips"]), len(d["timelines"]), time.time() - t0))
    finally:
        if orig:
            pm.LoadProject(orig)
            now = pm.GetCurrentProject()
            log("Mở lại project cũ: %s" % ("đã mở lại" if now and now.GetName() == orig else "KHÔNG mở lại được, hãy mở tay"))
            if not keep_tmp and now and now.GetName() == orig:
                for tmp in made + [t for t in (pm.GetProjectListInCurrentFolder() or []) if t.startswith(TMP_PREFIX) and t not in made]:
                    if tmp.startswith(TMP_PREFIX):
                        log("xóa project tạm %s: %s" % (tmp[len(TMP_PREFIX):], pm.DeleteProject(tmp)))
        else:
            log("Không có project nào đang mở lúc đầu nên giữ project tạm _hoc_tu_cu_* (xóa tay trong Project Manager được).")


# ----------------------------------------------------------------------------- lấy mẫu thưa bằng ffmpeg
def audio_feats(pcm):
    import numpy as np
    x = np.frombuffer(pcm, dtype="<i2").astype("float32") / 32768.0
    if x.size < 800:
        return {}
    rms = float(np.sqrt(np.mean(x * x)) + 1e-9)
    sp = np.abs(np.fft.rfft(x * np.hanning(x.size))) ** 2
    fr = np.fft.rfftfreq(x.size, 1 / 8000.0)
    tot = float(sp.sum()) + 1e-9
    voice = float(sp[(fr >= 300) & (fr <= 3400)].sum() / tot)
    n = x.size // 800
    fl = x[:n * 800].reshape(n, 800)
    fdb = 20 * np.log10(np.sqrt((fl * fl).mean(axis=1)) + 1e-6)
    return {"rms": round(20 * float(np.log10(rms)), 1), "voice": round(voice, 3), "dyn": round(float(fdb.std()), 2),
            "zcr": round(float((np.diff(np.sign(x)) != 0).mean()), 3)}


def frame_feats(raw):
    import numpy as np
    if len(raw) != 32 * 18 * 3:
        return {}
    a = np.frombuffer(raw, dtype="uint8").reshape(18, 32, 3).astype("float32") / 255.0
    mx, mn = a.max(axis=2), a.min(axis=2)
    top = a[:6]
    grid = a.reshape(3, 6, 4, 8, 3).mean(axis=(1, 3))                  # lưới 3x4 màu trung bình
    return {"bright": round(float(a.mean()), 3), "sat": round(float((mx - mn).mean()), 3),
            "sky": round(float((top[..., 2] - top[..., 0]).mean()), 3), "rgb": [round(float(v), 2) for v in grid.ravel()]}


def sample_clip(path, dur, n, tmpdir):
    out = []
    for i in range(n):
        t = max(0.0, min(dur - WIN, (i + 0.5) / n * dur - WIN / 2))
        af = os.path.join(tmpdir, "a%d_%d.raw" % (os.getpid(), id(out)))
        base = ["ffmpeg", "-v", "error", "-nostdin", "-ss", "%.2f" % t, "-t", "%.2f" % WIN, "-i", path]
        vid = ["-map", "0:v:0", "-frames:v", "1", "-vf", "scale=32:18", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
        aud = ["-map", "0:a:0", "-ac", "1", "-ar", "8000", "-f", "s16le", "-y", af]
        row = {"t": round(t + WIN / 2, 2)}
        try:
            r = subprocess.run(base + vid + aud, capture_output=True, timeout=120)
            if r.returncode != 0:                                     # có thể không có tiếng: thử riêng hình
                r = subprocess.run(base + vid, capture_output=True, timeout=120)
            row.update(frame_feats(r.stdout))
            if os.path.exists(af):
                with open(af, "rb") as f:
                    row.update(audio_feats(f.read()))
        except (subprocess.TimeoutExpired, OSError):
            pass
        finally:
            try:
                os.remove(af)
            except OSError:
                pass
        out.append(row)
    return out


def stage_sample(code, ddir, max_clips, deadline):
    dump = jload(os.path.join(ddir, code + "_dump.json"))
    mp = os.path.join(ddir, code + "_mau.jsonl")
    done = set()
    if os.path.exists(mp):
        with open(mp, "r", encoding="utf-8") as f:
            for ln in f:
                try:
                    done.add(json.loads(ln)["uid"])
                except (ValueError, KeyError):
                    pass
    used = {s["uid"] for s in pt.segments(dump, pt.pick_main(dump))}
    clips = [c for c in dump["clips"] if c.get("online") and pt.clip_dur(c) and c["uid"] not in done]
    clips.sort(key=lambda c: (c["uid"] not in used, c["path"]))       # clip có trên timeline trước, cùng ổ đứng gần nhau
    if max_clips:
        clips = clips[:max_clips]
    off = sum(1 for c in dump["clips"] if not c.get("online"))
    log("%s: lấy mẫu %d clip (đã có %d, offline %d)" % (code, len(clips), len(done), off))
    tmpdir = tempfile.mkdtemp(prefix="hoc_tu_cu_")

    def job(c):
        d = pt.clip_dur(c)
        n = min(24, max(4, int(d / 8))) if c["uid"] in used else (3 if d >= 10 else 2)
        return c["uid"], sample_clip(c["path"], d, n, tmpdir)
    k = 0
    with cf.ThreadPoolExecutor(2) as ex, open(mp, "a", encoding="utf-8") as out:
        it = iter(clips)
        pend = set()
        while True:
            while len(pend) < 4 and time.time() < deadline:
                c = next(it, None)
                if c is None:
                    break
                pend.add(ex.submit(job, c))
            if not pend:
                break
            fin, pend = cf.wait(pend, return_when=cf.FIRST_COMPLETED)
            for fu in fin:
                uid, w = fu.result()
                out.write(json.dumps({"uid": uid, "w": w}) + "\n")
                out.flush()
                k += 1
                if k % 25 == 0:
                    log("%s: %d/%d clip" % (code, k, len(clips)))
    return k < len(clips)


def read_samples(ddir, code):
    s = {}
    p = os.path.join(ddir, code + "_mau.jsonl")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                    s[r["uid"]] = r["w"]
                except (ValueError, KeyError):
                    pass
    return s


def stage_analyse(code, ddir, local):
    dump = jload(os.path.join(ddir, code + "_dump.json"))
    res = pt.analyse(dump, read_samples(ddir, code), (local.get("main_timeline") or {}).get(code))
    jsave(os.path.join(ddir, code + "_phan_tich.json"), res)
    return res


def main():
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except Exception:                                   # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--thu")
    ap.add_argument("--mau-toi-da", type=int, default=0)
    ap.add_argument("--gio-toi-da", type=float, default=0)
    ap.add_argument("--chi-phan-tich", action="store_true")
    ap.add_argument("--giu-tam", action="store_true")
    a = ap.parse_args()
    local = load_local()
    dr = troly_env.data_root()
    if not dr:
        sys.exit("config.json chưa có data_root.")
    ddir = os.path.join(dr, "hoc_tu_cu")
    os.makedirs(ddir, exist_ok=True)
    state = jload(os.path.join(ddir, "tien_do.json"), {})
    codes = [a.thu] if a.thu else list(local["projects"])
    for c in codes:
        if c not in local["projects"]:
            sys.exit("Không có mã %s trong hoc_tu_cu.local.json" % c)
    need_dump = [c for c in codes if not os.path.exists(os.path.join(ddir, c + "_dump.json"))]
    if not a.chi_phan_tich:
        print("\n=== Học từ project cũ: sẽ làm gì ===")
        print("Project:", ", ".join(codes), "(%d)" % len(codes))
        print("1. DaVinci: LƯU project đang mở, chuyển sang bản sao tạm _hoc_tu_cu_* của từng project (nhập từ .drp xuất ra), ĐỌC timeline + clip,")
        print("   rồi mở lại project đang mở và xóa các project tạm. Project gốc không bị mở hay sửa. Cần việc này cho:",
              ", ".join(need_dump) or "(không, đã đọc xong)")
        print("2. ffmpeg: lấy mẫu THƯA từng clip (cửa sổ 1,5 giây, vài chục chỗ/clip) để đo âm thanh và màu khung nhỏ. Không chạy model AI,")
        print("   không ghi gì vào video. Cần cắm đủ ổ HDD/SSD chứa video; clip ổ vắng sẽ bị bỏ qua và báo lại.")
        print("3. Phân tích ra số liệu, lưu ở:", ddir)
        print("Không ghi Media Pool/In-Out, không xóa/sửa clip hay timeline. Bị ngắt thì chạy lại lệnh này để làm tiếp.")
        if input("\nGõ Y rồi Enter để chạy, phím khác để thoát: ").strip().lower() != "y":
            print("Đã hủy, chưa làm gì.")
            return 0
        if need_dump:
            stage_resolve(need_dump, local, ddir, state, a.giu_tam)
        deadline = time.time() + a.gio_toi_da * 3600 if a.gio_toi_da else float("inf")
        for c in codes:
            if os.path.exists(os.path.join(ddir, c + "_dump.json")) and time.time() < deadline:
                partial = stage_sample(c, ddir, a.mau_toi_da, deadline)
                state.setdefault(c, {})["mau_chua_xong"] = partial
                jsave(os.path.join(ddir, "tien_do.json"), state)
    tong = {}
    for c in codes:
        if os.path.exists(os.path.join(ddir, c + "_dump.json")):
            tong[c] = stage_analyse(c, ddir, local)
            log("%s: đã phân tích" % c)
    jsave(os.path.join(ddir, "tong_hop.json"), tong)
    print("\nXong. Số liệu tổng hợp (không tên khách):", os.path.join(ddir, "tong_hop.json"))
    miss = [c for c in codes if not os.path.exists(os.path.join(ddir, c + "_dump.json"))]
    if miss:
        print("Chưa đọc được:", ", ".join(miss), "(xem dòng lỗi phía trên)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
