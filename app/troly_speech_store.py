"""
troly_speech_store.py - KHO LỜI NÓI của MỘT project (ADR-0014): một file SQLite duy nhất, KHÔNG phải một SRT mỗi clip.
Nằm trong thư mục người dựng chọn (ngoài kho mã). Chữ chép lời không vào git, không vào Notion; chỉ số liệu ra ngoài.

Khóa clip = đường dẫn TƯƠNG ĐỐI (vd 01_footage/DG4939.MP4, giống kế hoạch project); UniqueId của DaVinci lưu kèm để tra ngược.
Không dùng tên file chép lời làm khóa (lần trước tên lệch tên file âm thanh làm sót 6/17 đoạn).

Bảng clips: 1 dòng / clip (ngôn ngữ, độ dài, số dòng, đoạn nói để vẽ thanh màu, số cụm key, câu tiêu biểu, mức kéo âm lượng,
cờ "có thể sai", kích thước + ngày sửa file, timecode bắt đầu, trạng thái done/silent/error).
Bảng lines: 1 dòng / câu (clip, số thứ tự, giờ bắt đầu + kết thúc TÍNH TỪ ĐẦU FILE, chữ, ngôn ngữ, cụm key, mã nghi bịa).
Chạy tiếp được: clip đã xong mà file không đổi (cùng kích thước + ngày sửa) thì bỏ qua.
"""
import json
import os
import sqlite3
import time

import troly_speech as sp

SCHEMA = 1
DDL = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS clips (
  key TEXT PRIMARY KEY, uid TEXT, name TEXT, lang TEXT, lang_manual INTEGER DEFAULT 0, dur REAL, n_lines INTEGER,
  speech TEXT, n_keys INTEGER, headline TEXT, gain_db REAL, suspect INTEGER DEFAULT 0, size INTEGER, mtime REAL,
  tc TEXT, status TEXT, err_stage TEXT, err TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS lines (
  clip TEXT, idx INTEGER, t0 REAL, t1 REAL, text TEXT, lang TEXT, keys TEXT, why TEXT, PRIMARY KEY (clip, idx));
CREATE INDEX IF NOT EXISTS lines_clip ON lines (clip);
"""


def file_sig(path):
    """(kích thước, ngày sửa) của file gốc; None nếu không đọc được."""
    try:
        st = os.stat(path)
        return st.st_size, round(st.st_mtime, 3)
    except OSError:
        return None


def headline(lines):
    """Câu tiêu biểu: câu có NHIỀU cụm key nhất; không có thì câu DÀI nhất (bỏ câu nghi bịa). Rỗng nếu không có câu."""
    ok = [l for l in lines if not l.get("why")]
    if not ok:
        return ""
    best = max(ok, key=lambda l: (len(l.get("keys") or []), len(l.get("text") or "")))
    return best["text"]


class Store(object):
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30, check_same_thread=False)
        self.db.executescript(DDL)
        self.db.execute("INSERT OR IGNORE INTO meta VALUES ('schema', ?)", (str(SCHEMA),))
        self.db.commit()

    def close(self):
        try:
            self.db.close()
        except sqlite3.Error:
            pass

    # --- chạy tiếp ----------------------------------------------------------
    def needs_run(self, key, sig):
        """True nếu clip chưa có, đã lỗi, hoặc file đã đổi (kích thước hay ngày sửa khác). done/silent + file y nguyên: bỏ qua."""
        r = self.db.execute("SELECT status, size, mtime FROM clips WHERE key=?", (key,)).fetchone()
        if r is None or r[0] not in ("done", "silent") or sig is None:
            return True
        return (r[1], r[2]) != (sig[0], sig[1])

    # --- ghi ------------------------------------------------------------------
    def put_result(self, key, uid, name, sig, tc, res, lang, warn_gain=sp.WARN_GAIN_DB):
        """Lưu kết quả một clip. res = dict của troly_speech.finish_clip (hoặc None = không có tiếng người)."""
        lines = (res or {}).get("lines") or []
        n_keys = sum(len(l["keys"]) for l in lines if not l["why"])
        bad = sum(1 for l in lines if l["why"])
        gain = (res or {}).get("gain_db") or 0.0
        suspect = 1 if (gain > warn_gain or bad) else 0
        speech_found = bool((res or {}).get("speech"))
        status = "done" if (lines or speech_found) else "silent"   # có tiếng mà Whisper không ra chữ vẫn là "done" (0 dòng) + cờ sai
        if speech_found and not lines:
            suspect = 1
        speech = (res or {}).get("speech") or []
        keep = self.db.execute("SELECT lang, lang_manual FROM clips WHERE key=?", (key,)).fetchone()
        if keep and keep[1]:
            lang = keep[0]                                   # ngôn ngữ người dựng sửa tay thì giữ
        with self.db:
            self.db.execute("DELETE FROM lines WHERE clip=?", (key,))
            self.db.execute(
                "INSERT OR REPLACE INTO clips (key, uid, name, lang, lang_manual, dur, n_lines, speech, n_keys, headline, "
                "gain_db, suspect, size, mtime, tc, status, err_stage, err, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key, uid, name, lang if status == "done" else None, keep[1] if keep else 0, (res or {}).get("dur"), len(lines),
                 json.dumps(speech), n_keys, headline(lines), gain, suspect, sig[0] if sig else None,
                 sig[1] if sig else None, tc, status, None, None, time.strftime("%Y-%m-%dT%H:%M:%S")))
            self.db.executemany(
                "INSERT INTO lines (clip, idx, t0, t1, text, lang, keys, why) VALUES (?,?,?,?,?,?,?,?)",
                [(key, i, l["t0"], l["t1"], l["text"], lang, json.dumps(l["keys"], ensure_ascii=False),
                  ",".join(l["why"])) for i, l in enumerate(lines)])

    def put_error(self, key, uid, name, sig, tc, stage, err):
        """Ghi lỗi một clip. stage: 'pre' (chưa biết có tiếng hay không: trích âm, VAD) hoặc 'whisper' (đã biết có tiếng)."""
        with self.db:
            self.db.execute("DELETE FROM lines WHERE clip=?", (key,))
            self.db.execute(
                "INSERT OR REPLACE INTO clips (key, uid, name, size, mtime, tc, status, err_stage, err, ts) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (key, uid, name, sig[0] if sig else None, sig[1] if sig else None, tc, "error", stage,
                 str(err)[:200], time.strftime("%Y-%m-%dT%H:%M:%S")))

    def set_lang(self, key, lang):
        """Người dựng sửa ngôn ngữ một clip (vi/en); ghi nhớ để lần chạy sau không tự đổi lại."""
        with self.db:
            self.db.execute("UPDATE clips SET lang=?, lang_manual=1 WHERE key=?", (lang, key))
            self.db.execute("UPDATE lines SET lang=? WHERE clip=?", (lang, key))

    # --- đọc --------------------------------------------------------------------
    def counts(self, keys=None):
        """Số liệu đối chiếu cho các clip trong `keys` (None = cả kho)."""
        rows = self.db.execute("SELECT key, status, err_stage, suspect FROM clips").fetchall()
        if keys is not None:
            ks = set(keys)
            rows = [r for r in rows if r[0] in ks]
        c = {"total": len(rows), "done": 0, "silent": 0, "err_pre": 0, "err_whisper": 0, "suspect": 0}
        for _, st, stage, sus in rows:
            if st == "done":
                c["done"] += 1
                c["suspect"] += 1 if sus else 0
            elif st == "silent":
                c["silent"] += 1
            elif st == "error":
                c["err_whisper" if stage == "whisper" else "err_pre"] += 1
        c["speech"] = c["done"] + c["err_whisper"]            # file có tiếng = đã chép + lỗi lúc chép
        c["err"] = c["err_pre"] + c["err_whisper"]
        return c

    def reconcile(self, keys):
        """Đối chiếu cuối lượt. Trả về (ok, thông báo). Quy tắc:
        (1) mọi clip của lượt đều có dòng trong kho: tổng = im lặng + đã chép + lỗi;
        (2) số file có tiếng = số đã chép + số lỗi lúc chép (không clip nào rơi mất)."""
        c = self.counts(keys)
        missing = len(set(keys)) - c["total"]
        ok = missing == 0 and c["total"] == c["silent"] + c["done"] + c["err"] and c["speech"] == c["done"] + c["err_whisper"]
        done_lines = self.db.execute(
            "SELECT COUNT(*) FROM clips c WHERE status='done' AND n_lines != (SELECT COUNT(*) FROM lines l WHERE l.clip=c.key)"
        ).fetchone()[0]
        if done_lines:
            ok = False
        msg = ("ĐỐI CHIẾU: tổng %d = im lặng %d + đã chép %d + lỗi %d | có tiếng %d = đã chép %d + lỗi lúc chép %d"
               % (c["total"], c["silent"], c["done"], c["err"], c["speech"], c["done"], c["err_whisper"]))
        if missing:
            msg += " | THIẾU %d clip chưa có dòng trong kho" % missing
        if done_lines:
            msg += " | %d clip lệch số dòng" % done_lines
        return ok, ("OK: " if ok else "LỆCH: ") + msg

    def clip_rows(self):
        """Mọi clip cho bản đồ lời nói (không có chữ từng câu)."""
        cur = self.db.execute("SELECT key, uid, name, lang, dur, n_lines, speech, n_keys, headline, gain_db, suspect, tc, "
                              "status, err_stage, lang_manual FROM clips")
        cols = [d[0] for d in cur.description]
        out = []
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            d["speech"] = json.loads(d["speech"] or "[]")
            out.append(d)
        return out

    def lines_of(self, key):
        cur = self.db.execute("SELECT idx, t0, t1, text, lang, keys, why FROM lines WHERE clip=? ORDER BY idx", (key,))
        return [{"idx": i, "t0": a, "t1": b, "text": t, "lang": lg, "keys": json.loads(k or "[]"),
                 "why": [w for w in (y or "").split(",") if w]} for i, a, b, t, lg, k, y in cur.fetchall()]

    def search(self, text, limit=2000):
        """Tìm chữ trong cả project (không phân biệt hoa thường và dấu câu). Trả về tập khóa clip có chữ đó."""
        q = sp.normalize(text)
        if not q:
            return set()
        out = set()
        for key, t in self.db.execute("SELECT clip, text FROM lines"):
            if q in sp.normalize(t):
                out.add(key)
                if len(out) >= limit:
                    break
        return out


def add_timecode(tc_start, seconds, fps):
    """Timecode bắt đầu của file ("HH:MM:SS:FF" hay "HH:MM:SS;FF") + số giây trong file -> "HH:MM:SS:FF". None nếu thiếu."""
    import re
    m = re.match(r"^\s*(\d+):(\d+):(\d+)[:;.](\d+)\s*$", tc_start or "")
    if not m or not fps:
        return None
    h, mi, s, f = (int(x) for x in m.groups())
    fr = int(round(fps))
    total = ((h * 60 + mi) * 60 + s) * fr + f + int(round(seconds * fr))
    ff = total % fr
    total //= fr
    return "%02d:%02d:%02d:%02d" % (total // 3600 % 24, total // 60 % 60, total % 60, ff)

def _line_flags(self):
    """{khóa clip: [(giây đầu, giây cuối, số cụm key, mã nghi bịa)]} cho cả kho, để vẽ thanh màu và khung In/Out (không có chữ)."""
    out = {}
    for key, a, b, k, y in self.db.execute("SELECT clip, t0, t1, keys, why FROM lines ORDER BY clip, idx"):
        out.setdefault(key, []).append((a, b, len(json.loads(k or "[]")), y or ""))
    return out


Store.line_flags = _line_flags

