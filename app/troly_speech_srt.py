"""
troly_speech_srt.py - Xuất lời nói ra SRT (mục A4, ADR-0014) và đọc lại để ghép về đúng clip, đúng giờ gốc. Logic thuần,
không gọi DaVinci. Chữ chép lời chỉ đi từ kho ra file SRT người dựng chọn thư mục (không vào git, không vào Notion).

Định dạng:
  - Mỗi giai đoạn một file; trong file, các clip xếp theo giờ quay, GIỜ NỐI TIẾP LIÊN TỤC: clip sau bắt đầu sau clip trước
    (độ dài cả clip + 1 giây đệm) nên hai clip không bao giờ chồng giờ.
  - Mỗi dòng chữ bắt đầu bằng MÃ nằm ngay trong dòng chữ: [<mã clip>#<số dòng>] <chữ>. ChatGPT dịch xong vẫn giữ mã,
    nhờ đó ghép về đúng clip (mã clip suy ra từ tên file, trùng tên thì thêm @<4 ký tự băm của khóa clip).
  - Giờ gốc = giờ trong SRT - độ lệch của clip (độ lệch thấy được qua mọi dòng cùng clip, phải giống nhau).
  - Dòng nghi bịa (có mã lý do) không được xuất; số dòng bị bỏ được báo lại.
"""
import hashlib
import os
import re

GAP_S = 1.0                                   # đệm giữa hai clip liền nhau trong file SRT
CODE_RE = re.compile(r"^\s*\[([^\]#\s]+)#(\d+)\]\s*(.*)$", re.S)
TIME_RE = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def srt_time(t):
    ms = int(round(max(0.0, t) * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def parse_time(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def stem_of(key):
    name = key.replace("\\", "/").rsplit("/", 1)[-1]
    return os.path.splitext(name)[0].upper()


def clip_codes(keys):
    """{khóa clip: mã}. Mã = tên file không đuôi (in hoa); hai clip trùng tên thì cả hai thêm @<băm 4 ký tự của khóa>.
    Ổn định: chỉ phụ thuộc tập khóa, không phụ thuộc thứ tự."""
    stems = {}
    for k in keys:
        stems.setdefault(stem_of(k), []).append(k)
    out = {}
    for s, ks in stems.items():
        for k in ks:
            out[k] = s if len(ks) == 1 else "%s@%s" % (s, hashlib.sha1(k.encode("utf-8")).hexdigest()[:4])
    return out


def one_line(text):
    return " ".join((text or "").split())


def build_srt(clips, continuous=True):
    """clips: [{key, code, dur, lines:[{idx, t0, t1, text, why}]}] đã xếp theo thứ tự xuất.
    continuous=True: giờ nối tiếp liên tục qua các clip (file giai đoạn / phần đã chọn); False: giờ gốc của clip (SRT một clip).
    Trả về (chữ SRT, số dòng đã xuất, số dòng bị bỏ vì nghi bịa, [{key, offset, n}])."""
    out, n, skipped, layout, offset, seq = [], 0, 0, [], 0.0, 1
    for c in clips:
        used = 0
        for l in c["lines"]:
            if l.get("why"):
                skipped += 1
                continue
            t0, t1 = offset + l["t0"], offset + max(l["t1"], l["t0"] + 0.2)
            out.append("%d\n%s --> %s\n[%s#%02d] %s\n" % (seq, srt_time(t0), srt_time(t1), c["code"], l["idx"] + 1,
                                                       one_line(l["text"])))
            seq += 1
            n += 1
            used += 1
        layout.append({"key": c["key"], "offset": round(offset, 3), "n": used})
        if continuous:
            offset += float(c.get("dur") or 0) + GAP_S
    return "\n".join(out), n, skipped, layout


def parse_srt(text):
    """SRT -> [(giây đầu, giây cuối, chữ)] (chữ có thể nhiều dòng, nối bằng khoảng trắng)."""
    res = []
    for block in re.split(r"\r?\n\s*\r?\n", (text or "").strip()):
        lines = [x for x in block.splitlines() if x.strip()]
        for i, ln in enumerate(lines):
            m = TIME_RE.search(ln)
            if m:
                g = m.groups()
                res.append((parse_time(*g[:4]), parse_time(*g[4:]), " ".join(x.strip() for x in lines[i + 1:])))
                break
    return res


def read_back(text, code_to_key, store_lines):
    """Đọc lại một file SRT (kể cả sau khi dịch) và ghép về clip + giờ gốc.
    code_to_key: {mã: khóa clip}; store_lines(key) -> [{idx, t0, t1, ...}] của kho.
    Trả về dict: matches [{key, idx, srt_t0, srt_t1, orig_t0, orig_t1, offset, text}], unknown [mã không biết],
    bad [dòng không có mã], inconsistent [khóa clip có độ lệch giờ không đều]."""
    matches, unknown, bad = [], [], []
    cache = {}
    for t0, t1, txt in parse_srt(text):
        m = CODE_RE.match(txt)
        if not m:
            bad.append(txt[:30])
            continue
        code, num, body = m.group(1), int(m.group(2)) - 1, m.group(3)
        key = code_to_key.get(code)
        if key is None:
            unknown.append(code)
            continue
        if key not in cache:
            cache[key] = {l["idx"]: l for l in store_lines(key)}
        ln = cache[key].get(num)
        if ln is None:
            unknown.append("%s#%d" % (code, num + 1))
            continue
        off = round(t0 - ln["t0"], 3)
        matches.append({"key": key, "idx": num, "srt_t0": t0, "srt_t1": t1, "orig_t0": ln["t0"], "orig_t1": ln["t1"],
                        "offset": off, "text": body})
    offs = {}
    for m in matches:
        offs.setdefault(m["key"], set()).add(m["offset"])
    inconsistent = sorted(k for k, v in offs.items() if max(v) - min(v) > 0.01)
    return {"matches": matches, "unknown": unknown, "bad": bad, "inconsistent": inconsistent}


def safe_name(s, default="project"):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", s or "")
    s = " ".join(s.split()).strip(" .")
    return s or default
