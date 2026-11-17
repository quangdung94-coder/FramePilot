"""
troly_speech_run.py - Chạy chép lời cả bin vào kho lời nói (ADR-0014). KHÔNG gọi DaVinci: nhận danh sách clip đã đọc sẵn.

  - Chép từng file riêng, 2 tiến trình Whisper song song (gom nhiều file một lần gọi làm mất câu: đo 17/11/2026).
  - Chạy tiếp được: clip đã xong và file không đổi thì bỏ qua; file đổi hoặc lần trước lỗi thì chép lại.
  - Chạy ban đêm: gọi on_progress, ghi nhật ký (CHỈ số liệu và tên clip, không có chữ chép), giữ máy không ngủ, xong thì
    kêu một tiếng và trả về số liệu. KHÔNG tắt máy.
  - Cuối lượt: đối chiếu số file có tiếng = đã chép + lỗi (Store.reconcile). Lệch thì summary["ok"] = False và báo đỏ.

Chạy thử không cần DaVinci:
  & $py app\\troly_speech_run.py --store-dir <thư mục kho> --project <tên> --folder <thư mục chứa file> [--lang vi] [--limit N]
"""
import argparse
import glob
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import troly_speech as sp                 # noqa: E402
import troly_speech_store as st           # noqa: E402

BATCH = 6                                  # số file chuẩn bị cùng lúc (rồi chép song song)
WORKERS = 2                                # số tiến trình Whisper chạy song song (GPU 12 GB đủ cho 2 bản medium)
EN_RATIO = 0.30                            # tỉ lệ từ tiếng Anh thông dụng để nghi file là tiếng Anh
EN_MIN_WORDS = 8


def keep_awake(on):
    """Chặn máy tự ngủ khi đang chạy (không tắt máy, không đụng cài đặt hệ thống)."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 if on else 0x80000000)
    except Exception:                       # noqa: BLE001
        pass


def low_priority():
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL
    except Exception:                       # noqa: BLE001
        pass


class SpeechRun(object):
    def __init__(self, store, cfg=None, vad_run=None, index=None, prompt=None, log_path=None, on_progress=None,
                 batch=BATCH, ffmpeg="ffmpeg", max_gain=sp.MAX_GAIN_DB):
        self.store, self.cfg = store, cfg or sp.load_whisper_cfg()
        self.vad, self.index, self.prompt = vad_run, index, prompt
        self.log_path, self.on_progress, self.batch = log_path, on_progress, batch
        self.ffmpeg, self.max_gain = ffmpeg, max_gain
        self.stop = False

    def log(self, msg):
        line = "%s %s" % (time.strftime("%H:%M:%S"), msg)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return line

    def run(self, items, lang="vi"):
        """items: [{key, uid, name, path, tc}]. Trả về dict số liệu (xem cuối hàm)."""
        t_all = time.time()
        keep_awake(True)
        tmp = tempfile.mkdtemp(prefix="troly_run_")
        keys = [it["key"] for it in items]
        sigs = {it["key"]: st.file_sig(it["path"]) for it in items}
        todo = [it for it in items if self.store.needs_run(it["key"], sigs[it["key"]])]
        skipped = len(items) - len(todo)
        self.log("BẮT ĐẦU: %d clip, bỏ qua %d (đã chép, file không đổi), chép %d, ngôn ngữ mặc định %s"
                 % (len(items), skipped, len(todo), lang))
        n_done = 0
        try:
            for b0 in range(0, len(todo), self.batch):
                if self.stop:
                    break
                group = todo[b0:b0 + self.batch]
                preps = {}
                for j, it in enumerate(group):
                    k, sig = it["key"], sigs[it["key"]]
                    try:
                        if sig is None:
                            raise RuntimeError("không thấy file")
                        p = sp.prepare_clip(it["path"], self.vad, tmp, "c%d" % j, self.ffmpeg, self.max_gain)
                        if p["wav"]:
                            preps[k] = p
                        else:                                       # không có tiếng người: im lặng
                            self.store.put_result(k, it.get("uid"), it.get("name"), sig, it.get("tc"),
                                                  sp.finish_clip(p, [], self.index), lang)
                            n_done += 1
                            self._progress(n_done, len(todo))
                    except Exception as e:                          # noqa: BLE001
                        self.store.put_error(k, it.get("uid"), it.get("name"), sig, it.get("tc"), "pre", e)
                        self.log("LỖI (trước khi chép) %s: %s" % (k, str(e)[:120]))
                        n_done += 1
                        self._progress(n_done, len(todo))
                by_key = {it["key"]: it for it in group}
                if preps:
                    n_done = self._whisper_group(preps, by_key, sigs, lang, n_done, len(todo))
                self._cleanup(tmp)
        finally:
            self._cleanup(tmp)
            shutil.rmtree(tmp, ignore_errors=True)
            keep_awake(False)
        ok, msg = self.store.reconcile(keys)
        c = self.store.counts(keys)
        remain = 0
        if self.stop:
            remain = sum(1 for it in items if self.store.needs_run(it["key"], sigs[it["key"]]))
            ok, msg = (remain == 0 and ok), "DỪNG GIỮA CHỪNG (còn %d clip chưa chép). %s" % (remain, msg)
        self.log(msg)
        summary = {"ok": ok, "message": msg, "stopped": self.stop, "remaining": remain, "skipped": skipped,
                   "total": c["total"], "speech": c["speech"], "done": c["done"], "silent": c["silent"],
                   "errors": c["err"], "suspect": c["suspect"], "took_s": round(time.time() - t_all, 1)}
        self.log("XONG: " + ", ".join("%s=%s" % kv for kv in summary.items() if kv[0] != "message"))
        try:
            import ctypes
            ctypes.windll.user32.MessageBeep(0x40)                  # kêu một tiếng báo xong
        except Exception:                                           # noqa: BLE001
            pass
        return summary

    # ------------------------------------------------------------------
    def _whisper_group(self, preps, by_key, sigs, lang, n_done, total):
        """Chép TỪNG file riêng (gom nhiều file một lần gọi làm mất câu ở file sau: đo 17/11/2026), nhưng chạy
        WORKERS tiến trình Whisper song song để bù thời gian nạp mô hình."""
        from concurrent.futures import ThreadPoolExecutor

        def one(k):
            p = preps[k]
            t = time.time()
            sents, _ = sp.whisper_run(self.cfg, p["wav"], lang, self.prompt)
            use_lang = lang
            if lang == "vi" and sents:
                ratio, nw = sp.english_ratio(sents)
                if nw >= EN_MIN_WORDS and ratio >= EN_RATIO:        # nghi tiếng Anh: chép lại bằng -l en (không gợi ý)
                    sents, _ = sp.whisper_run(self.cfg, p["wav"], "en", None)
                    use_lang = "en"
            return sents, use_lang, time.time() - t

        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {k: ex.submit(one, k) for k in preps}
            for k, fut in futs.items():
                it, sig, p = by_key[k], sigs[k], preps[k]
                try:
                    sents, use_lang, took = fut.result()
                    res = sp.finish_clip(p, sents, self.index if use_lang == "vi" else self._en_index(), took)
                    self.store.put_result(k, it.get("uid"), it.get("name"), sig, it.get("tc"), res, use_lang)
                except Exception as e:                              # noqa: BLE001
                    self.store.put_error(k, it.get("uid"), it.get("name"), sig, it.get("tc"), "whisper", e)
                    self.log("LỖI (lúc chép) %s: %s" % (k, str(e)[:120]))
                n_done += 1
                self._progress(n_done, total)
        return n_done

    def _en_index(self):
        return []                                                   # kho cụm key chỉ cho tiếng Việt

    def _progress(self, n, total):
        if self.on_progress:
            try:
                self.on_progress(n, total)
            except Exception:                                       # noqa: BLE001
                pass

    @staticmethod
    def _cleanup(tmp):
        for f in glob.glob(os.path.join(tmp, "*")):
            try:
                os.remove(f)
            except OSError:
                pass


def store_path(store_dir, project):
    """File kho của project: <thư mục kho>\\<tên project an toàn>.loinoi.sqlite"""
    safe = "".join("_" if ch in '<>:"/\\|?*' else ch for ch in project).strip(" .") or "project"
    return os.path.join(store_dir, safe + ".loinoi.sqlite")


def main():
    a_ = argparse.ArgumentParser(description="Chép lời một thư mục file vào kho lời nói (thử không cần DaVinci)")
    a_.add_argument("--store-dir", required=True)
    a_.add_argument("--project", required=True)
    a_.add_argument("--folder", required=True)
    a_.add_argument("--lang", default="vi")
    a_.add_argument("--limit", type=int, default=0)
    a = a_.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                       # noqa: BLE001
        pass
    app_root = os.path.dirname(HERE)
    if os.path.abspath(a.store_dir).lower().startswith(app_root.lower() + os.sep):
        sys.exit("Thư mục kho không được nằm trong kho mã (%s). Chọn thư mục khác." % app_root)
    files = sorted(f for f in glob.glob(os.path.join(a.folder, "*")) if f.lower().endswith((".mp4", ".mov", ".mxf", ".wav")))
    if a.limit:
        files = files[:a.limit]
    items = [{"key": os.path.basename(a.folder.rstrip("\\/")) + "/" + os.path.basename(f), "uid": None,
              "name": os.path.basename(f), "path": f, "tc": None} for f in files]
    name, vad = sp.load_vad()
    if vad is None:
        sys.exit("Thiếu silero-vad (không tải gì về; hỏi người dựng).")
    phr = sp.load_phrases()
    store = st.Store(store_path(a.store_dir, a.project))
    low_priority()
    run = SpeechRun(store, vad_run=vad, index=sp.build_index(phr), prompt=phr.get("prompt"),
                    log_path=os.path.join(a.store_dir, "loinoi.log"),
                    on_progress=lambda n, t: print("  tiến độ %d/%d" % (n, t), flush=True))
    s = run.run(items, a.lang)
    print(s["message"])
    print({k: v for k, v in s.items() if k != "message"})
    sys.exit(0 if s["ok"] else 2)


if __name__ == "__main__":
    main()
