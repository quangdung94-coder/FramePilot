"""
inout_dump.py - Đọc In/Out thật người dựng đã đặt (ADR-0021). CHỈ ĐỌC DaVinci: không ghi In/Out, không ghi/xóa/tạo timeline, không render.

Việc duy nhất ngoài đọc: đổi project đang mở để đọc (LoadProject), sau khi SaveProject project đang mở; xong (kể cả lỗi) mở lại ĐÚNG project gốc.
  --list                       in tên project đang mở + danh sách project (thư mục hiện tại)
  --export  P ...              ExportProject từng project ra <backup>\drp_<giờ>\ (không cần mở), kiểm dung lượng
  --dump    P ...  --orig NAME  lưu project gốc, mở từng project, dump In/Out + đoạn nguồn trên timeline ra JSON, rồi mở lại project gốc
"""
import argparse
import json
import os
import sys
import time

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APP)
import troly_env                      # noqa: E402

MAX_DRP = 500 * 1024 * 1024


def walk(folder, path, out):
    for c in folder.GetClipList() or []:
        out.append((path, c))
    for sf in folder.GetSubFolderList() or []:
        walk(sf, path + "/" + sf.GetName(), out)
    return out


def vio(m):
    v = (m or {}).get("video") if isinstance(m, dict) else None
    if isinstance(v, dict) and v.get("in") is not None and v.get("out") is not None:
        return int(v["in"]), int(v["out"])
    return None


def dump_project(proj):
    pool = proj.GetMediaPool()
    root = pool.GetRootFolder()
    clips, by_uid = [], {}
    for bp, c in walk(root, root.GetName(), []):
        p = c.GetClipProperty() or {}
        t = p.get("Type") or ""
        if "Video" not in t or "Timeline" in t or "Compound" in t:
            continue
        try:
            m = vio(c.GetMarkInOut())
        except Exception:                                   # noqa: BLE001
            m = None
        path = p.get("File Path") or ""
        d = {"uid": c.GetUniqueId(), "bin": bp, "name": p.get("File Name") or "", "fps": p.get("FPS"), "frames": p.get("Frames"),
             "dur": p.get("Duration"), "mark": m, "online": bool(path) and os.path.exists(path), "path": path,
             "created": p.get("Date Created"), "modified": p.get("Date Modified"), "res": p.get("Resolution")}
        clips.append(d)
        by_uid[d["uid"]] = d
    tls = []
    for i in range(1, (proj.GetTimelineCount() or 0) + 1):
        tl = proj.GetTimelineByIndex(i)
        items = []
        try:
            nv = tl.GetTrackCount("video")
        except Exception:                                   # noqa: BLE001
            nv = 0
        for tr in range(1, nv + 1):
            for it in tl.GetItemListInTrack("video", tr) or []:
                mp = it.GetMediaPoolItem()
                if mp is None:
                    continue
                uid = mp.GetUniqueId()
                row = {"uid": uid, "track": tr, "start": it.GetStart(), "end": it.GetEnd(), "dur": it.GetDuration(),
                       "left": it.GetLeftOffset(), "right": it.GetRightOffset(),
                       "src_start_f": it.GetSourceStartFrame(), "src_end_f": it.GetSourceEndFrame(),
                       "src_start_t": it.GetSourceStartTime(), "src_end_t": it.GetSourceEndTime()}
                items.append(row)
        tls.append({"name": tl.GetName(), "fps": tl.GetSetting("timelineFrameRate"), "items": items})
    return {"project": proj.GetName(), "clips": clips, "timelines": tls}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--export", nargs="*")
    ap.add_argument("--dump", nargs="*")
    ap.add_argument("--orig")
    ap.add_argument("--out")
    a = ap.parse_args()
    r = troly_env.connect_resolve()
    pm = r.GetProjectManager()
    cur = pm.GetCurrentProject()
    print("Project đang mở:", cur.GetName() if cur else None)
    if a.list:
        print("Thư mục:", pm.GetCurrentFolder() if hasattr(pm, "GetCurrentFolder") else "?")
        print("Danh sách:", pm.GetProjectListInCurrentFolder())
        return 0
    os.makedirs(a.out, exist_ok=True)
    if a.export:
        for name in a.export:
            f = os.path.join(a.out, name.replace("&", "_") + ".drp")
            if os.path.exists(f):
                print("đã có, không ghi đè:", f)
                continue
            ok = pm.ExportProject(name, f, True)
            sz = os.path.getsize(f) if os.path.exists(f) else 0
            print("ExportProject", "P?", ok, "%.1f MB" % (sz / 1048576.0))
            if ok and sz > MAX_DRP:
                print("DRP quá lớn (>500 MB) - KHÔNG mở project này")
        return 0
    if a.dump:
        if not cur or cur.GetName() != a.orig:
            print("DaVinci không đang mở project gốc như dự kiến, dừng.")
            return 2
        if not pm.SaveProject():
            print("SaveProject lỗi, dừng.")
            return 2
        rc = 0
        try:
            for name in a.dump:
                t0 = time.time()
                p = pm.LoadProject(name)
                now = pm.GetCurrentProject()
                if not p or not now or now.GetName() != name:
                    print("LoadProject lỗi/khác project, bỏ qua:", bool(p))
                    rc = 3
                    break
                data = dump_project(now)
                f = os.path.join(a.out, name.replace("&", "_") + "_inout.json")
                with open(f, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False)
                print("dump", len(data["clips"]), "clip,", len(data["timelines"]), "timeline,", "%.1fs" % (time.time() - t0), f)
        finally:
            back = pm.LoadProject(a.orig)
            now = pm.GetCurrentProject()
            print("Mở lại project gốc:", bool(back), "->", now.GetName() if now else None)
    return rc


if __name__ == "__main__":
    sys.exit(main())
