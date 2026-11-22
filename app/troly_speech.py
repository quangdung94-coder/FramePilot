"""
troly_speech.py - Chép lời cho Trợ lý File Quay, tab "4 · Lời nói" (giai đoạn A). KHÔNG gọi DaVinci, KHÔNG đụng file gốc.

Mỗi clip: trích âm thanh ra WAV tạm (16 kHz mono) -> KÉO LÊN mức chuẩn (không loại file vì tiếng nhỏ) -> lọc khoảng lặng
bằng silero-vad -> ghép các đoạn có tiếng -> Const-me Whisper (ggml medium) + gợi ý từ ngữ lễ cưới (CHỈ tiếng Việt)
-> đổi mốc thời gian về file gốc. WAV tạm luôn bị xóa. Chữ chép lời không in ra màn hình hay nhật ký, chỉ có số.

Chép từ kho VideoAI cũ (learn_night.py, learn_speech.py, analyze_audio.py), không import ngược.
"""
import json
import os
import re
import subprocess
import troly_proc
import tempfile
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
RATE = 16000
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
EXTRACT_TIMEOUT_S = 900        # trích âm một file (clip dài hàng chục phút vẫn chỉ vài chục giây); quá thì coi file hỏng
WHISPER_TIMEOUT_S = 1800       # Whisper một WAV (lô nhiều file: nhân số file)

VAD_PAD_S = 0.3           # chừa quanh mỗi đoạn có tiếng người
VAD_JOIN_S = 0.6          # hai đoạn tiếng cách nhau dưới 0,6 giây thì gộp
VAD_GAP_S = 0.4           # khoảng lặng chèn giữa các đoạn khi ghép lại

TARGET_DB = -20.0         # mức chuẩn: ô 0,1 giây to nhất (phân vị 95) kéo về khoảng này (dBFS RMS)
MAX_GAIN_DB = 30.0        # kéo lên tối đa (đề xuất ban đầu; số đo thật sẽ chỉnh)
PEAK_CEIL = 0.97          # kéo xong đỉnh sóng không vượt mức này (tránh vỡ tiếng)
WARN_GAIN_DB = 18.0       # kéo hơn mức này thì đánh dấu "kết quả có thể sai"


# ---------------------------------------------------------------------------
# KHO CỤM KEY (chép từ learn_speech.py)
# ---------------------------------------------------------------------------
def load_phrases(path=None):
    with open(path or os.path.join(HERE, "wedding_phrases.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def normalize(text):
    """Chữ thường, bỏ dấu câu (giữ dấu thanh tiếng Việt), gộp khoảng trắng."""
    t = (text or "").lower()
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return " ".join(t.replace("_", " ").split())


def expand(phrase, variants):
    forms = {normalize(phrase)}
    for k, alts in (variants or {}).items():
        nk = normalize(k)
        for f in list(forms):
            if nk in f:
                for alt in alts:
                    forms.add(f.replace(nk, normalize(alt)))
    return forms


def build_index(phr):
    out = []
    for g, items in (phr.get("groups") or {}).items():
        for p in items:
            out.append((g, p, expand(p, phr.get("variants"))))
    return out


def find_keys(text, index):
    """Các cụm key có trong câu: [(nhóm, cụm gốc)], mỗi cụm một lần mỗi câu, khớp trọn từ."""
    t = " %s " % normalize(text)
    return [(g, p) for g, p, forms in index if any(" %s " % f in t for f in forms)]


# ---------------------------------------------------------------------------
# ÂM THANH: trích, đo, kéo lên mức chuẩn
# ---------------------------------------------------------------------------
def extract_wav(src, out_wav, ffmpeg="ffmpeg"):
    """Trích âm thanh từ file gốc (chỉ đọc) ra WAV 16 kHz mono. Lỗi thì ném RuntimeError."""
    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-vn", "-ac", "1",
           "-ar", str(RATE), "-c:a", "pcm_s16le", out_wav]
    try:
        r = troly_proc.chay_an(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
                               timeout=EXTRACT_TIMEOUT_S, tag="speech")
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg trích âm quá %d giây (file hỏng?), bỏ qua clip này." % EXTRACT_TIMEOUT_S)
    if r.returncode != 0 or not os.path.isfile(out_wav):
        raise RuntimeError("ffmpeg lỗi: " + (r.stderr or "")[-200:])
    return out_wav


def read_wav(path):
    import numpy as np
    with wave.open(path) as w:
        raw = w.readframes(w.getnframes())
        return np.frombuffer(raw, dtype=np.int16), w.getframerate()


def write_wav(path, x, rate=RATE):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(x.tobytes())


def level_stats(x, rate=RATE, win=0.1):
    """Mức tiếng (dBFS): phân vị 95 và trung vị của RMS mỗi ô 0,1 giây, và đỉnh sóng."""
    import numpy as np
    n = int(rate * win)
    k = len(x) // n
    if k == 0:
        return {"p95_db": -120.0, "med_db": -120.0, "peak": 0.0}
    f = x[:k * n].astype(np.float64).reshape(k, n) / 32768.0
    r = 20 * np.log10(np.maximum(np.sqrt(np.mean(f * f, axis=1)), 1e-6))
    return {"p95_db": float(np.percentile(r, 95)), "med_db": float(np.median(r)),
            "peak": float(np.abs(x.astype(np.int32)).max()) / 32768.0}


def compute_gain(stats, target=TARGET_DB, max_gain=MAX_GAIN_DB, peak_ceil=PEAK_CEIL):
    """Số dB kéo lên (>= 0): đưa p95 về mức chuẩn, không quá max_gain, không làm đỉnh vượt peak_ceil."""
    g = max(0.0, target - stats["p95_db"])
    if stats["peak"] > 0:
        import math
        g = min(g, 20 * math.log10(peak_ceil / stats["peak"]) if peak_ceil > stats["peak"] else 0.0)
    import math
    return math.floor(max(0.0, min(g, max_gain)) * 10) / 10.0       # làm tròn XUỐNG để không vượt trần đỉnh sóng


def apply_gain(x, gain_db):
    import numpy as np
    if gain_db <= 0:
        return x
    y = x.astype(np.float64) * (10 ** (gain_db / 20.0))
    return np.clip(y, -32768, 32767).astype(np.int16)


# ---------------------------------------------------------------------------
# LỌC KHOẢNG LẶNG (silero-vad) và ghép đoạn
# ---------------------------------------------------------------------------
def _load_vad_worker():
    """Dự phòng cho bản đóng gói FramePilot.exe (loại torch): gọi troly_vad_worker.py bằng Python venv có silero-vad."""
    import tempfile
    import troly_env as te
    import troly_proc

    here = os.path.dirname(os.path.abspath(__file__))
    worker = os.path.join(here, "troly_vad_worker.py")
    if not os.path.isfile(worker):
        return None, None
    cfg = te.config() or {}
    candidates = [cfg.get("python"), r"C:\VideoAI_venv\Scripts\python.exe", cfg.get("ai_python")]
    py = next((p for p in candidates if p and os.path.isfile(p)), None)
    if not py:
        return None, None

    def run(x):
        fd, pcm = tempfile.mkstemp(suffix=".pcm", prefix="fp_vad_")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(x.astype("<i2", copy=False).tobytes())
            r = troly_proc.chay_an(
                [py, "-X", "utf8", worker, "--pcm", pcm, "--rate", str(RATE)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, tag="speech",
            )
            if r.returncode != 0:
                raise RuntimeError("Lỗi silero-vad worker: %s" % (r.stderr or "")[-200:])
            lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
            return json.loads(lines[-1]) if lines else []
        finally:
            try:
                os.remove(pcm)
            except OSError:
                pass

    return "silero-vad(worker)", run


def load_vad():
    """(tên, hàm(mono16k int16) -> [[giây đầu, giây cuối]]) hoặc (None, None) nếu thiếu thư viện."""
    try:
        import numpy as np
        import torch
        from silero_vad import load_silero_vad, get_speech_timestamps
        torch.set_num_threads(1)
        model = load_silero_vad()

        def run(x):
            ts = get_speech_timestamps(torch.from_numpy(x.astype(np.float32) / 32768.0), model,
                                       sampling_rate=RATE, return_seconds=True)
            return [[round(t["start"], 2), round(t["end"], 2)] for t in ts]
        return "silero-vad(CPU)", run
    except ImportError:
        return _load_vad_worker()


def join_chunks(chunks, pad=VAD_PAD_S, join=VAD_JOIN_S, total=None):
    out = []
    for a, b in sorted(chunks):
        a, b = max(0.0, a - pad), (min(total, b + pad) if total else b + pad)
        if out and a - out[-1][1] < join:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def concat_map(chunks, gap=VAD_GAP_S):
    """[(đầu trong file ghép, cuối trong file ghép, đầu trong file gốc)]."""
    out, pos = [], 0.0
    for a, b in chunks:
        out.append((round(pos, 3), round(pos + (b - a), 3), a))
        pos += (b - a) + gap
    return out


def map_time(t, mapping):
    if not mapping:
        return t
    for c0, c1, o0 in mapping:
        if t <= c1:
            return o0 + max(0.0, t - c0)
    c0, c1, o0 = mapping[-1]
    return o0 + (c1 - c0)


def concat_audio(x, chunks, gap=VAD_GAP_S, rate=RATE):
    import numpy as np
    sil = np.zeros(int(gap * rate), dtype=np.int16)
    parts = []
    for i, (a, b) in enumerate(chunks):
        parts.append(x[int(a * rate):int(b * rate)])
        if i < len(chunks) - 1:
            parts.append(sil)
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.int16)


# ---------------------------------------------------------------------------
# WHISPER (Const-me main.exe + ggml medium) và câu nghi bịa
# ---------------------------------------------------------------------------
HALLU = re.compile(
    r"subscrib\w*|subrisb\w*|subcrib\w*|đăng k[ýí](?: cho)? kênh|ghiền mì gõ|bỏ lỡ(?: những)? video|lalaschool|ủng hộ kênh"
    r"|cảm ơn(?: các bạn)? đã xem video|hẹn gặp lại(?: các bạn)? (?:ở|trong)(?: những)? video|(?:nhớ |hãy )?(?:bấm|nhấn) chuông|like(?:,| và)? (?:share|chia sẻ)",
    re.I,
)
SRT_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def parse_srt(text):
    out = []
    for block in re.split(r"\r?\n\s*\r?\n", (text or "").strip()):
        lines = [x for x in block.splitlines() if x.strip()]
        for i, ln in enumerate(lines):
            m = SRT_TIME.search(ln)
            if m:
                g = [int(x) for x in m.groups()]
                out.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0,
                            g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0, " ".join(lines[i + 1:]).strip()))
                break
    return out


def whisper_cmd(cfg, wav, lang="vi", prompt=None):
    cmd = [cfg["exe"], "-m", cfg["model"], "-l", lang, "-osrt", "-nc", "-f", wav]
    if prompt and lang == "vi":                      # gợi ý từ ngữ CHỈ cho tiếng Việt
        cmd += ["--prompt", prompt]
    return cmd


def faster_whisper_model_dir(engine, data_root=None):
    """Thư mục model CTranslate2 cục bộ cho Whisper large-v3-turbo hoặc PhoWhisper-medium."""
    root = data_root or r"D:\VideoAI\data"
    sub = {"whisper_turbo": "whisper_large_v3_turbo", "phowhisper": "phowhisper_medium_ct2"}.get(engine)
    return os.path.join(root, "models", sub) if sub else ""


def _use_faster_whisper(cfg):
    eng = str((cfg or {}).get("engine") or "").strip().lower()
    if eng not in ("whisper_turbo", "phowhisper"):
        return False
    py = (cfg or {}).get("ai_python") or ""
    mdir = (cfg or {}).get("ct2_dir") or ""
    worker = os.path.join(HERE, "troly_asr_worker.py")
    return os.path.isfile(py) and os.path.isdir(mdir) and os.path.isfile(worker)


def _run_faster_whisper_batch(cfg, wavs, lang="vi", prompt=None):
    """Chạy faster-whisper (Whisper large-v3-turbo / PhoWhisper CT2) qua venv AI riêng trong 1 lần nạp model."""
    worker = os.path.join(HERE, "troly_asr_worker.py")
    cmd = [cfg["ai_python"], "-X", "utf8", worker, "--model", cfg["ct2_dir"], "--lang", lang or "vi"]
    if prompt and (lang or "vi") == "vi":
        cmd += ["--prompt", prompt]
    cmd += list(wavs)
    t = time.time()
    lim = WHISPER_TIMEOUT_S * max(1, len(wavs))
    try:
        r = troly_proc.chay_an(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               creationflags=NO_WINDOW, timeout=lim, tag="speech")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Whisper AI chạy quá %d giây, đã dừng." % lim)
    took = time.time() - t
    if r.returncode != 0:
        raise RuntimeError("Whisper AI lỗi (mã %s): %s" % (r.returncode, (r.stderr or r.stdout or "")[-240:]))
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    if not lines:
        return {}, took
    raw = json.loads(lines[-1])
    out = {}
    for w, rows in (raw.items() if isinstance(raw, dict) else []):
        out[w] = [(float(a), float(b), str(txt)) for a, b, txt in rows]
    return out, took


def whisper_run(cfg, wav, lang="vi", prompt=None):
    """Chép một WAV, trả về ([(giây đầu, giây cuối, chữ)], giây chạy). Tự dùng faster-whisper (large-v3-turbo / PhoWhisper) nếu đã bật."""
    if _use_faster_whisper(cfg):
        out, took = _run_faster_whisper_batch(cfg, [wav], lang, prompt)
        return out.get(wav, []), took
    t = time.time()
    try:
        r = troly_proc.chay_an(whisper_cmd(cfg, wav, lang, prompt), capture_output=True, text=True, encoding="utf-8",
                               errors="replace", creationflags=NO_WINDOW, timeout=WHISPER_TIMEOUT_S, tag="speech")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Whisper chạy quá %d giây, đã dừng." % WHISPER_TIMEOUT_S)
    took = time.time() - t
    srt = os.path.splitext(wav)[0] + ".srt"
    try:
        if r.returncode != 0 or not os.path.isfile(srt):
            raise RuntimeError("Whisper lỗi (mã %s): %s" % (r.returncode, (r.stderr or r.stdout or "")[-200:]))
        with open(srt, "r", encoding="utf-8-sig", errors="replace") as f:
            return parse_srt(f.read()), took
    finally:
        if os.path.isfile(srt):
            os.remove(srt)


def suspect_reasons(sents, speech):
    """Câu nghi bịa: chỉ trả về MÃ LÝ DO (không chữ). sents = [(t0, t1, text)] mốc file gốc; speech = [[a, b]] VAD.
    hallu = câu bịa quen thuộc; lap = lặp y nguyên câu liền trước; ngoai = nằm hẳn ngoài mọi đoạn có tiếng;
    thua = quá ít chữ so với độ dài (dưới 1 chữ/giây khi dài trên 4 giây)."""
    out, prev = [], None
    for a, b, txt in sents:
        why = []
        if HALLU.search(txt or ""):
            why.append("hallu")
        if prev is not None and normalize(txt) == prev and prev:
            why.append("lap")
        prev = normalize(txt)
        if speech and not any(min(b, s1) - max(a, s0) > 0.1 for s0, s1 in speech):
            why.append("ngoai")
        if (b - a) > 4.0 and len((txt or "").split()) / (b - a) < 1.0:
            why.append("thua")
        out.append(why)
    return out


# ---------------------------------------------------------------------------
# CHÉP MỘT CLIP: chuẩn bị (trích, kéo, VAD, ghép) -> Whisper -> hoàn tất (đổi mốc, cụm key, câu nghi bịa)
# ---------------------------------------------------------------------------
EN_WORDS = set("the and you your to of is are it that this for with we our was have has be on in at all so but they "
               "thank thanks today here there what just very like love married happy wedding".split())


def english_ratio(lines):
    """Tỉ lệ từ tiếng Anh thông dụng trong chữ chép (0..1) và số từ. Dùng để nghi file là tiếng Anh."""
    words = [w for l in lines for w in normalize(l["text"] if isinstance(l, dict) else l[2]).split()]
    if not words:
        return 0.0, 0
    return sum(1 for w in words if w in EN_WORDS) / float(len(words)), len(words)


def prepare_clip(path, vad_run, tmp, tag="a", ffmpeg="ffmpeg", max_gain=MAX_GAIN_DB):
    """Trích + kéo âm lượng + lọc khoảng lặng. Trả về dict 'prep'; prep['wav'] là file ghép các đoạn có tiếng
    (None nếu không có tiếng người). WAV trung gian xóa ngay, chỉ giữ file ghép trong thư mục tmp."""
    raw = os.path.join(tmp, "%s_raw.wav" % tag)
    try:
        extract_wav(path, raw, ffmpeg)
        x, rate = read_wav(raw)
    finally:
        if os.path.isfile(raw):
            os.remove(raw)
    dur = len(x) / float(rate)
    st = level_stats(x, rate)
    gain = compute_gain(st, max_gain=max_gain)
    y = apply_gain(x, gain)
    speech = vad_run(y) if vad_run else []
    prep = {"dur": round(dur, 2), "gain_db": gain, "p95_db": round(st["p95_db"], 1), "med_db": round(st["med_db"], 1),
            "peak": round(st["peak"], 3), "speech": speech, "wav": None, "map": None, "audio_s": 0.0}
    chunks = join_chunks([tuple(c) for c in speech], total=dur)
    if chunks:
        joined = concat_audio(y, chunks)
        prep["audio_s"] = round(len(joined) / float(rate), 2)
        prep["wav"] = os.path.join(tmp, "%s_j.wav" % tag)
        write_wav(prep["wav"], joined, rate)
        prep["map"] = concat_map(chunks)
    return prep


def finish_clip(prep, sents, index=None, took=0.0):
    """Gắn mốc về file gốc, đánh dấu câu nghi bịa, gắn cụm key. Trả về dict kết quả (CHỮ nằm trong 'lines')."""
    res = {k: prep[k] for k in ("dur", "gain_db", "p95_db", "med_db", "peak", "speech", "audio_s")}
    res["took_s"] = round(took, 2)
    m = prep.get("map")
    sents = [(round(map_time(a, m), 2), round(map_time(b, m), 2), t) for a, b, t in sents]
    why = suspect_reasons(sents, prep["speech"])
    res["lines"] = []
    for (a, b, t), w in zip(sents, why):
        keys = [] if w else [p for _, p in find_keys(t, index or [])]
        res["lines"].append({"t0": a, "t1": b, "text": t, "keys": keys, "why": w})
    return res


def whisper_batch(cfg, wavs, lang="vi", prompt=None):
    """Chép NHIỀU WAV trong một lần gọi (nạp mô hình một lần). Trả về ({wav: [(t0, t1, text)]}, giây chạy)."""
    if _use_faster_whisper(cfg):
        return _run_faster_whisper_batch(cfg, wavs, lang, prompt)
    cmd = [cfg["exe"], "-m", cfg["model"], "-l", lang, "-osrt", "-nc"]
    if prompt and lang == "vi":
        cmd += ["--prompt", prompt]
    cmd += list(wavs)
    t = time.time()
    lim = WHISPER_TIMEOUT_S * max(1, len(wavs))
    try:
        r = troly_proc.chay_an(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW, timeout=lim, tag="speech")
    except subprocess.TimeoutExpired:
        r = None                                      # vẫn đọc các SRT đã xong (và xóa hết SRT) ở dưới
    took = time.time() - t
    out = {}
    for w in wavs:
        srt = os.path.splitext(w)[0] + ".srt"
        try:
            if os.path.isfile(srt):
                with open(srt, "r", encoding="utf-8-sig", errors="replace") as f:
                    out[w] = parse_srt(f.read())
        finally:
            if os.path.isfile(srt):
                os.remove(srt)
    if r is None and not out:
        raise RuntimeError("Whisper chạy quá %d giây, đã dừng." % lim)
    if r is not None and r.returncode != 0 and not out:
        raise RuntimeError("Whisper lỗi (mã %s): %s" % (r.returncode, (r.stderr or r.stdout or "")[-200:]))
    return out, took


def transcribe_clip(path, cfg, vad_run, lang="vi", prompt=None, index=None, ffmpeg="ffmpeg", tmp_dir=None,
                    max_gain=MAX_GAIN_DB):
    """Chép lời MỘT file source (dùng cho đo và thử). WAV tạm xóa khi xong, kể cả khi lỗi."""
    tmp = tempfile.mkdtemp(prefix="troly_sp_", dir=tmp_dir)
    try:
        prep = prepare_clip(path, vad_run, tmp, "a", ffmpeg, max_gain)
        sents, took = [], 0.0
        if prep["wav"]:
            sents, took = whisper_run(cfg, prep["wav"], lang, prompt)
        return finish_clip(prep, sents, index, took)
    finally:
        for f in os.listdir(tmp):
            try:
                os.remove(os.path.join(tmp, f))
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


def load_whisper_cfg():
    """Cấu hình Whisper: đọc từ troly_env.config(); ưu tiên Whisper large-v3-turbo / PhoWhisper nếu đã tải cục bộ, dự phòng Const-me."""
    try:
        import troly_env
        full = troly_env.config() or {}
    except Exception:                                     # noqa: BLE001
        full = {}
    cfg = dict(full.get("whisper") or {})
    cfg.setdefault("exe", r"D:\VideoAI\tools\whisper\constme\cli\main.exe")
    cfg.setdefault("model", r"E:\Kho dữ liệu\Tài nguyên\WhisperDesktop_SUB_AUTO\ggml-medium.bin")
    data_root = full.get("data_root") or r"D:\VideoAI\data"
    ai_py = full.get("ai_python") or r"C:\VideoAI_ai_venv\Scripts\python.exe"
    want = str(full.get("asr_engine") or cfg.get("engine") or "auto").strip().lower()
    chosen, ct2_dir = "constme", ""
    if want == "auto":
        for cand in ("whisper_turbo", "phowhisper"):
            d = faster_whisper_model_dir(cand, data_root)
            if os.path.isfile(ai_py) and os.path.isdir(d):
                chosen, ct2_dir = cand, d
                break
    elif want in ("whisper_turbo", "phowhisper"):
        d = faster_whisper_model_dir(want, data_root)
        if os.path.isfile(ai_py) and os.path.isdir(d):
            chosen, ct2_dir = want, d
    cfg["engine"] = chosen
    cfg["ai_python"] = ai_py
    cfg["ct2_dir"] = ct2_dir
    return cfg
