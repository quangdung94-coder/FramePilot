"""
troly_batch.py - "Phân tích cả project": chép lời cả bin, rồi làm sẵn thumbnail, rồi (nếu người dựng tick) lưu project DaVinci và TẮT MÁY
sau 2 phút đếm ngược có nút Huỷ (ADR-0017). Logic điều phối thuần, KHÔNG gọi DaVinci hay tắt máy trực tiếp: mọi việc ngoài (chép lời,
chờ thumbnail, SaveProject, lệnh tắt máy, đồng hồ) được TRUYỀN VÀO, nên kiểm thử dùng bản giả và không bao giờ tắt máy thật.

QUY TẮC AN TOÀN (đã chốt với người dựng 18/11/2026):
  - Ô "Tắt máy khi xong" mặc định TẮT.
  - KHÔNG BAO GIỜ tắt máy nếu: bị dừng giữa chừng, chép lời lỗi hoặc đối chiếu lệch, thumbnail chưa xong, có ngoại lệ bất kỳ,
    lưu project lỗi (kiểm lúc bắt đầu đếm ngược VÀ ngay trước khi tắt), hoặc người dựng bấm Huỷ lúc đếm ngược.
  - Lệnh tắt máy mặc định từ chối chạy khi biến môi trường TROLY_NO_SHUTDOWN có giá trị (bộ kiểm thử đặt biến này).
"""
import os
import subprocess
import time

COUNTDOWN_S = 120


def system_shutdown():
    """Lệnh tắt máy thật (Windows). Từ chối nếu TROLY_NO_SHUTDOWN được đặt (kiểm thử, chạy thử)."""
    if os.environ.get("TROLY_NO_SHUTDOWN"):
        raise RuntimeError("TROLY_NO_SHUTDOWN được đặt: từ chối tắt máy thật.")
    subprocess.run(["shutdown", "/s", "/t", "10", "/c", "Trợ lý File Quay: phân tích xong, tắt máy theo yêu cầu."], check=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


class AnalyzeAll(object):
    """speech_fn(stop_check) -> dict số liệu của lượt chép lời (có 'ok', 'stopped').
    thumbs_fn(stop_check, on_progress) -> (xong?, số xong, tổng): chờ thumbnail của mọi clip, xong? = False nếu bị dừng hoặc kẹt.
    save_fn() -> bool: lưu project DaVinci (SaveProject). shutdown_fn(): tắt máy. sleep(giây): đồng hồ (kiểm thử truyền bản không chờ).
    emit(loại, dữ liệu): báo giao diện. Kết quả run(): dict, 'shutdown' = off | sent | cancelled | skipped."""

    def __init__(self, speech_fn, thumbs_fn, save_fn, shutdown_fn=None, emit=None, countdown_s=COUNTDOWN_S, sleep=time.sleep):
        self.speech_fn, self.thumbs_fn, self.save_fn = speech_fn, thumbs_fn, save_fn
        self.shutdown_fn = shutdown_fn or system_shutdown
        self.emit = emit or (lambda kind, data=None: None)
        self.countdown_s, self.sleep = countdown_s, sleep
        self.stop = False                 # người dựng bấm Dừng phân tích
        self.cancel_shutdown = False      # người dựng bấm Huỷ tắt máy (hoặc Dừng)
        self.phase = "idle"

    def _phase(self, name, text):
        self.phase = name
        self.emit("analyze_phase", {"phase": name, "text": text})

    def _halted(self):
        return self.stop

    def run(self, shutdown_when_done=False):
        res = {"speech": None, "thumbs": None, "stopped": False, "ok": False, "shutdown": "off", "reason": "", "error": None}
        try:
            self._phase("speech", "Đang chép lời cả bin...")
            sp = self.speech_fn(self._halted)
            res["speech"] = sp
            if self.stop or (sp or {}).get("stopped"):
                res["stopped"], res["reason"] = True, "bị dừng giữa chừng"
            else:
                self._phase("thumbs", "Đang làm sẵn thumbnail...")
                done, n, total = self.thumbs_fn(self._halted, lambda a, b: self.emit("analyze_thumbs", {"n": a, "total": b}))
                res["thumbs"] = {"done": bool(done), "n": n, "total": total}
                if self.stop:
                    res["stopped"], res["reason"] = True, "bị dừng giữa chừng"
            res["ok"] = (not res["stopped"] and bool((sp or {}).get("ok")) and bool((res["thumbs"] or {}).get("done")))
            if not res["ok"] and not res["reason"]:
                res["reason"] = ("chép lời lỗi hoặc đối chiếu lệch" if not (sp or {}).get("ok") else "thumbnail chưa xong")
        except Exception as e:                                     # noqa: BLE001  ngoại lệ bất kỳ -> không tắt máy
            res["error"], res["reason"] = str(e), "có lỗi: %s" % e
        if shutdown_when_done:
            res["shutdown"] = self._maybe_shutdown(res)
        self._phase("done", "Phân tích xong." if res["ok"] else "Phân tích dừng: %s." % res["reason"])
        self.emit("analyze_done", res)
        return res

    # ------------------------------------------------------------------
    def _maybe_shutdown(self, res):
        if not res["ok"]:
            res["reason"] = res["reason"] or "chưa xong"
            self.emit("analyze_shutdown", {"state": "skipped", "reason": "Không tắt máy vì " + res["reason"]})
            return "skipped"
        try:
            self._phase("save", "Đang lưu project DaVinci trước khi tắt máy...")
            if self.save_fn() is not True:
                return self._skip(res, "lưu project DaVinci lỗi")
            for left in range(self.countdown_s, 0, -1):            # đếm ngược, mỗi giây kiểm Huỷ/Dừng
                if self.cancel_shutdown or self.stop:
                    return self._cancel()
                self.emit("analyze_countdown", {"remaining": left})
                self.sleep(1)
            if self.cancel_shutdown or self.stop:
                return self._cancel()
            if self.save_fn() is not True:                         # lưu lại lần cuối, lỗi thì thôi
                return self._skip(res, "lưu project DaVinci lỗi (lần cuối)")
            if self.cancel_shutdown or self.stop:                  # Huỷ/Dừng bấm trong lúc lưu lần cuối: kiểm lại ngay trước khi tắt
                return self._cancel()
            self._phase("shutdown", "Đang tắt máy...")
            self.shutdown_fn()
            self.emit("analyze_shutdown", {"state": "sent"})
            return "sent"
        except Exception as e:                                     # noqa: BLE001
            return self._skip(res, "có lỗi khi tắt máy: %s" % e)

    def _cancel(self):
        self.emit("analyze_shutdown", {"state": "cancelled"})
        return "cancelled"

    def _skip(self, res, why):
        res["reason"] = why
        self.emit("analyze_shutdown", {"state": "skipped", "reason": "Không tắt máy vì " + why})
        return "skipped"
