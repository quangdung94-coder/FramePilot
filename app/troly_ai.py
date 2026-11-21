r"""
troly_ai.py - Bước 6 AI (ADR-0020): nhúng thumbnail bằng OpenCLIP ViT-B/32 và GỢI Ý bin theo mô tả. CHỈ ĐỌC + GỢI Ý.

- Không ghi gì vào DaVinci, không đổi kế hoạch panel, không chuyển clip. Chỉ đọc thumbnail trong cache và proxy_root (chỉ để
  đối chiếu tên file), chỉ ghi vào: <data_root>\cache\troly_embed\<project>\ (vector, xóa được), <data_root>\troly\ai_suggest\<project>.json,
  <data_root>\troly\ai_review\<project>\index.html.
- Model chạy cục bộ (D:\VideoAI\data\models\openclip_vitb32_laion2b), ảnh không gửi đi đâu.
- Phần ghép thumbnail <-> clip và phần mô tả không cần torch (kiểm thử được bằng venv của panel). Phần nhúng cần venv AI (C:\VideoAI_ai_venv).

Chạy (venv AI):  python troly_ai.py embed|suggest|review|all --project "<tên project>"   (thêm --stop để dừng, chạy lại để làm tiếp)
"""
import argparse
import hashlib
import html
import json
import os
import sys
import time
import unicodedata
import urllib.parse

APP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP)
import troly_thumbs as tt           # noqa: E402  (chỉ thư viện chuẩn)
import troly_core as tc             # noqa: E402

MODEL_DIR_NAME = "openclip_vitb32_laion2b"
MODEL_FILE = "open_clip_model.safetensors"
MODEL_ARCH = "ViT-B-32"
SIGLIP_DIR_NAME = "siglip_vitb16"
SIGLIP_ARCH = "ViT-B-16-SigLIP"
TEMPERATURE = 100.0                 # CLIP: logit_scale ~100
BATCH = 32
THUMB_WIDTH = 320


def _root():
    import troly_env
    return troly_env.data_root() or r"D:\VideoAI\data", (troly_env.config().get("proxy_root") or r"F:\02_Proxy Media")


def _norm(s):
    return unicodedata.normalize("NFC", (s or "")).casefold()


# ---------------------------------------------------------------------------
# Mô tả tiếng Anh từng bin (2-4 câu). Bin lạ: tạo câu chung từ tên bin.
# ---------------------------------------------------------------------------
PROMPT_RULES = (
    (("phỏng vấn",), ["a person being interviewed, looking at the camera and talking",
                      "a person speaking into a microphone",
                      "an interview shot of one person sitting and talking at a wedding"]),
    (("cô dâu chú rể", "cô dâu và chú rể", "cặp đôi", "cô dâu & chú rể"), ["a bride and groom together, a wedding couple",
                                                                          "the newlyweds holding hands and smiling at each other",
                                                                          "a couple in wedding clothes during the ceremony"]),
    (("sân khấu",), ["a wedding stage with lights, screen and flower arch",
                     "the bride and groom standing on a stage in a banquet hall",
                     "a wedding stage with a master of ceremonies"]),
    (("phát biểu", "diễn văn"), ["a person giving a speech with a microphone at a wedding",
                                 "a speaker standing at a podium in front of guests"]),
    (("lễ vật", "trao lễ"), ["relatives carrying red gift trays with offerings for a Vietnamese wedding",
                             "people in ao dai holding trays covered with red cloth",
                             "exchanging wedding gifts between two families"]),
    (("nhà trai", "nhà gái", "rước"), ["a group of people in formal clothes arriving in a procession at a house",
                                       "the groom's family walking in a line carrying gifts",
                                       "a wedding procession arriving with cars and people"]),
    (("khách", "đón khách"), ["wedding guests sitting and standing in a hall",
                              "guests arriving, greeting and signing the guest book at a wedding",
                              "a crowd of wedding guests at tables"]),
    (("gia đình", "họ hàng", "người thân"), ["family members standing together at a wedding",
                                              "a group of relatives posing for a photo",
                                              "parents and relatives with the bride and groom"]),
    (("chú rể",), ["a groom in a black suit posing for a portrait",
                   "a groom wearing a suit and boutonniere getting ready",
                   "a man in a suit at a wedding, groom close-up"]),
    (("cô dâu", "beauty"), ["a bride in a white wedding dress posing for a portrait",
                            "a bride getting her makeup done by a makeup artist",
                            "a beautiful bride close-up, bridal portrait",
                            "a bride putting on her dress and veil"]),
    (("decor", "chi tiết", "trang trí"), ["wedding decoration with flowers and candles",
                                          "a close-up of wedding details such as table setting, backdrop and rings",
                                          "an empty wedding venue with decorations and no people"]),
    (("nghi lễ", "gia tiên", "lễ"), ["a traditional Vietnamese wedding ceremony with an altar, incense and offerings",
                                     "a couple bowing at an ancestral altar",
                                     "a formal wedding ceremony with relatives"]),
    (("chào bàn", "tiệc", "nhà hàng"), ["a wedding reception in a restaurant with guests at round tables",
                                        "the bride and groom toasting with champagne at a banquet",
                                        "a wedding banquet hall with a stage and lights"]),
    (("khác",), ["a blurry or dark frame of the floor, ceiling or camera equipment",
                 "people walking around, a random behind-the-scenes moment",
                 "an out-of-focus or unclear photo"]),
)


def prompts_for(bin_name):
    n = _norm(bin_name)
    for keys, texts in PROMPT_RULES:
        if any(k in n for k in keys):
            return list(texts)
    return ["a photo of %s at a wedding" % bin_name, "a video frame showing %s" % bin_name]


# ---------------------------------------------------------------------------
# Ghép thumbnail <-> clip (không cần DaVinci): băm tên cache dựng lại từ file proxy trong proxy_root
# ---------------------------------------------------------------------------
def _lut_candidates():
    out = []
    for d in tt.lut_dirs():
        for r, _, fs in os.walk(d):
            for f in fs:
                if f.lower().endswith((".cube", ".3dl")):
                    out.append(os.path.join(r, f))
    return out


def manifest_path(data_root, project):
    return os.path.join(embed_dir(data_root, project), "clips.json")


def write_manifest(data_root, project, pairs):
    """Panel ghi trước khi chạy AI: pairs = [(rel clip, đường dẫn thumbnail jpg)]. Nhờ đó AI ghép ảnh với clip theo danh sách clip của panel,
    KHÔNG cần thư mục proxy (clip không có proxy vẫn có thumbnail làm từ file gốc)."""
    d = embed_dir(data_root, project)
    os.makedirs(d, exist_ok=True)
    tmp = manifest_path(data_root, project) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump([{"rel": r, "thumb": t} for r, t in pairs], f, ensure_ascii=False)
    os.replace(tmp, manifest_path(data_root, project))


def load_manifest(data_root, project):
    """[{key, rel, name, proxy, thumb}] từ danh sách panel ghi, hoặc None nếu chưa có (khi đó ghép theo proxy như cũ)."""
    try:
        with open(manifest_path(data_root, project), "r", encoding="utf-8") as f:
            rows = json.load(f)
    except (OSError, ValueError):
        return None
    out = []
    for r in rows if isinstance(rows, list) else []:
        parts = str(r.get("rel", "")).replace("\\", "/").split("/")
        stem = os.path.splitext(parts[-1])[0]
        parent = parts[-2] if len(parts) > 1 else ""
        t = r.get("thumb")
        out.append({"key": stem + "|" + parent, "rel": "/".join(parts[-2:]), "name": stem, "proxy": None,
                    "thumb": t if t and os.path.isfile(t) else None})
    return out or None


def match_thumbs(project, data_root, proxy_root):
    """Trả (clips, thumbs_khong_ghep_duoc). clips: [{key, rel, name, proxy, thumb(đường dẫn jpg hoặc None)}] theo proxy.
    Chỉ đọc danh sách file + cỡ/giờ sửa của proxy (không mở nội dung)."""
    tdir = os.path.join(data_root, "cache", "troly_thumbs", tc._safe(project))
    man = load_manifest(data_root, project)
    if man is not None:                                     # panel đã ghi danh sách clip + thumbnail: không cần proxy
        return man, 0
    have = {f[:-4] for f in os.listdir(tdir) if f.endswith(".jpg")} if os.path.isdir(tdir) else set()
    pdir = os.path.join(proxy_root, project)
    files = []
    for r, _, fs in os.walk(pdir):
        for f in sorted(fs):
            if f.lower().endswith((".mov", ".mp4", ".mxf")):
                files.append(os.path.join(r, f))
    luts = [None] + _lut_candidates()
    clips, used = [], set()
    for p in sorted(files):
        pick = None
        for lut in luts[1:] + [None]:                       # ưu tiên bản có LUT (hình gần bản thành phẩm)
            k = tt.cache_key(p, lut, tt.DEFAULT_POS, THUMB_WIDTH)
            if k in have:
                pick = k
                break
        parts = p.replace("\\", "/").split("/")
        stem = os.path.splitext(parts[-1])[0]
        rel = "/".join(parts[-2:])                          # 01_footage/DG4939.mov (đuôi proxy khác đuôi file gốc)
        clips.append({"key": stem + "|" + parts[-2], "rel": rel, "name": stem, "proxy": p,
                      "thumb": os.path.join(tdir, pick + ".jpg") if pick else None})
        if pick:
            used.add(pick)
    orphan = sorted(have - used)
    if orphan and not files:                                             # KHÔNG còn proxy nào của project (đã xóa/chuyển): nhúng thumbnail mồ côi, không có tên clip. Còn proxy thì thumbnail thừa là cache cũ, bỏ qua
        from PIL import Image
        for k in orphan:
            f = os.path.join(tdir, k + ".jpg")
            try:
                with Image.open(f) as im:
                    if im.size[0] > THUMB_WIDTH + 80:       # bỏ ảnh lớn (640 px) của cùng clip
                        continue
            except (OSError, ValueError):
                continue
            clips.append({"key": "thumb:" + k, "rel": "(không ghép được clip)", "name": k[:8], "proxy": None, "thumb": f})
    return clips, len(orphan)


def labels_by_stem(plan):
    """{(thư mục/tên không đuôi, không phân biệt hoa thường): tên bin} từ nhãn người dựng xếp (chỉ ĐỌC kế hoạch)."""
    out = {}
    for rel, v in (plan.get("labels") or {}).items():
        b = v.get("bin") if isinstance(v, dict) else v
        if isinstance(v, dict) and v.get("by") == "ai_auto":
            continue                                        # nhãn AI tự xếp không phải nhãn của anh
        if b:
            parts = rel.replace("\\", "/").split("/")
            out[(parts[-2].casefold() if len(parts) > 1 else "", os.path.splitext(parts[-1])[0].casefold())] = b
    return out


def plan_bins(plan):
    seen = []
    for s in plan.get("stages") or []:
        for b in s.get("bins") or []:
            if b not in seen:
                seen.append(b)
    return seen


# ---------------------------------------------------------------------------
# Phần cần torch
# ---------------------------------------------------------------------------
def model_path(data_root):
    return os.path.join(data_root, "models", MODEL_DIR_NAME, MODEL_FILE)


def siglip_dir(data_root):
    return os.path.join(data_root, "models", SIGLIP_DIR_NAME)


def has_siglip(data_root):
    d = siglip_dir(data_root)
    return os.path.isdir(d) and os.path.isdir(os.path.join(d, "models--timm--ViT-B-16-SigLIP"))


def load_model(data_root):
    import open_clip
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if has_siglip(data_root):
        sd = siglip_dir(data_root)
        os.environ.setdefault("HF_HOME", sd)
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        model, _, pre = open_clip.create_model_and_transforms(SIGLIP_ARCH, pretrained="webli", cache_dir=sd, device=dev)
        model.eval()
        return model, pre, open_clip.get_tokenizer(SIGLIP_ARCH), dev
    model, _, pre = open_clip.create_model_and_transforms(MODEL_ARCH, pretrained=model_path(data_root), device=dev)
    model.eval()
    return model, pre, open_clip.get_tokenizer(MODEL_ARCH), dev


def embed_dir(data_root, project):
    sub = "troly_embed_siglip" if has_siglip(data_root) else "troly_embed"
    return os.path.join(data_root, "cache", sub, tc._safe(project))


def _log(path, msg):
    line = "%s %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run_embed(project, data_root, proxy_root):
    """Nhúng thumbnail chưa có vector. Dừng: tạo file STOP trong thư mục embed (hoặc --stop); chạy lại thì làm tiếp."""
    import numpy as np
    import torch
    from PIL import Image
    d = embed_dir(data_root, project)
    os.makedirs(d, exist_ok=True)
    log = os.path.join(data_root, "logs", "ai_embed_%s.log" % hashlib.sha1(project.encode("utf-8")).hexdigest()[:8])
    os.makedirs(os.path.dirname(log), exist_ok=True)
    stop = os.path.join(d, "STOP")
    if os.path.isfile(stop):
        os.remove(stop)
    clips, orphan = match_thumbs(project, data_root, proxy_root)
    todo_all = [c for c in clips if c["thumb"]]
    npz = os.path.join(d, "vectors.npz")
    keys, vecs = [], None
    if os.path.isfile(npz):
        with np.load(npz, allow_pickle=False) as z:          # đóng file ngay (Windows không cho ghi đè file đang mở)
            keys, vecs = list(z["keys"]), z["vecs"].copy()
    done = set(keys)
    todo = [c for c in todo_all if c["key"] not in done]
    _log(log, "[%s] clip %d, có thumbnail %d, chưa có thumbnail %d (bỏ qua), thumbnail không ghép được %d, đã có vector %d, cần làm %d"
         % (project[:10], len(clips), len(todo_all), len(clips) - len(todo_all), orphan, len(done), len(todo)))
    if not todo:
        return {"clips": len(clips), "embedded": len(done), "skipped_no_thumb": len(clips) - len(todo_all), "orphan": orphan}
    t0 = time.time()
    model, pre, _, dev = load_model(data_root)
    _log(log, "model nạp xong trên %s (%.1fs)" % (dev, time.time() - t0))
    new_k, new_v = [], []

    def save():
        k = np.array(keys + new_k)
        v = np.concatenate([vecs, np.array(new_v, dtype=np.float32)]) if vecs is not None and new_v else (
            vecs if vecs is not None else np.array(new_v, dtype=np.float32))
        tmp = npz + ".tmp.npz"
        np.savez(tmp, keys=k, vecs=v)
        os.replace(tmp, npz)

    for i in range(0, len(todo), BATCH):
        if os.path.isfile(stop):
            _log(log, "Đã dừng theo yêu cầu; chạy lại để làm tiếp.")
            break
        chunk = todo[i:i + BATCH]
        imgs, ok = [], []
        for c in chunk:
            try:
                with Image.open(c["thumb"]) as im:
                    imgs.append(pre(im.convert("RGB")))
                ok.append(c)
            except (OSError, ValueError):
                _log(log, "bỏ qua ảnh lỗi: %s" % c["name"])
        if imgs:
            with torch.no_grad():
                f = model.encode_image(torch.stack(imgs).to(dev))
                f = f / f.norm(dim=-1, keepdim=True)
            for c, row in zip(ok, f.float().cpu().numpy()):
                new_k.append(c["key"])
                new_v.append(row)
        if (i // BATCH) % 5 == 4:
            save()
            _log(log, "tiến độ %d/%d" % (min(i + BATCH, len(todo)), len(todo)))
    save()
    _log(log, "xong: %d vector mới trong %.1fs" % (len(new_k), time.time() - t0))
    return {"clips": len(clips), "embedded": len(done) + len(new_k), "new": len(new_k), "seconds": round(time.time() - t0, 1),
            "skipped_no_thumb": len(clips) - len(todo_all), "orphan": orphan}


def run_suggest(project, data_root, proxy_root):
    """Gợi ý bin theo mô tả; ghi <data_root>\\troly\\ai_suggest\\<project>.json. Chỉ ĐỌC kế hoạch."""
    import numpy as np
    import torch
    plan = tc.load_plan(data_root, project)
    bins = plan_bins(plan)
    if not bins:
        return {"error": "Kế hoạch chưa có bin con."}
    npz = os.path.join(embed_dir(data_root, project), "vectors.npz")
    if not os.path.isfile(npz):
        return {"error": "Chưa có vector (chạy embed trước)."}
    with np.load(npz, allow_pickle=False) as z:
        keys, vecs = list(z["keys"]), z["vecs"].copy()
    model, _, tok, dev = load_model(data_root)
    tvecs = []
    with torch.no_grad():
        for b in bins:
            t = model.encode_text(tok(prompts_for(b)).to(dev))
            t = t / t.norm(dim=-1, keepdim=True)
            m = t.mean(0)
            tvecs.append((m / m.norm()).float().cpu().numpy())
    T = np.stack(tvecs)                                     # [bins, 512]
    logits = TEMPERATURE * vecs @ T.T
    e = np.exp(logits - logits.max(1, keepdims=True))
    prob = e / e.sum(1, keepdims=True)
    clips, _ = match_thumbs(project, data_root, proxy_root)
    by_key = {c["key"]: c for c in clips}
    lab = labels_by_stem(plan)
    items = []
    for k, p in zip(keys, prob):
        c = by_key.get(k)
        if not c:
            continue
        order = list(np.argsort(-p)[:3])
        stem_key = (c["rel"].split("/")[0].casefold(), c["name"].casefold())
        items.append({"clip": c["rel"], "name": c["name"], "thumb": c["thumb"],
                      "top": [{"bin": bins[j], "score": round(float(p[j]), 4)} for j in order],
                      "scores": [round(float(x), 4) for x in p],
                      "label": lab.get(stem_key)})
    out = {"project_tag": project[:10], "model": ("SigLIP %s" % SIGLIP_ARCH if has_siglip(data_root) else "OpenCLIP %s laion2b_s34b_b79k" % MODEL_ARCH), "bins": bins,
           "prompts": {b: prompts_for(b) for b in bins}, "count": len(items), "items": items,
           "eval": evaluate(items, bins)}
    d = os.path.join(data_root, "troly", "ai_suggest")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, tc._safe(project) + ".json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)
    return {"file": p, "count": len(items), "eval": out["eval"]}


MIN_LABELS = 20


def evaluate(items, bins):
    """Độ khớp gợi ý với nhãn người dựng (≥20 clip có nhãn mới đo)."""
    lab = [it for it in items if it.get("label") in bins]
    if len(lab) < MIN_LABELS:
        return {"labeled": len(lab), "note": "chưa đủ nhãn để đo (cần từ %d clip)" % MIN_LABELS}
    per = {}
    for b in bins:
        mine = [it for it in lab if it["label"] == b]
        pred = [it for it in lab if it["top"][0]["bin"] == b]
        hit = [it for it in mine if it["top"][0]["bin"] == b]
        per[b] = {"labeled": len(mine), "top1_recall": round(len(hit) / len(mine), 3) if mine else None,
                  "predicted": len(pred), "precision": round(sum(1 for it in pred if it["label"] == b) / len(pred), 3) if pred else None}
    t1 = sum(1 for it in lab if it["top"][0]["bin"] == it["label"])
    t3 = sum(1 for it in lab if it["label"] in [t["bin"] for t in it["top"]])
    return {"labeled": len(lab), "top1": round(t1 / len(lab), 3), "top3": round(t3 / len(lab), 3), "per_bin": per}


# ---------------------------------------------------------------------------
# Trang báo cáo tĩnh
# ---------------------------------------------------------------------------
def build_review(project, data_root):
    sp = os.path.join(data_root, "troly", "ai_suggest", tc._safe(project) + ".json")
    with open(sp, "r", encoding="utf-8") as f:
        s = json.load(f)
    outdir = os.path.join(data_root, "troly", "ai_review", tc._safe(project))
    os.makedirs(outdir, exist_ok=True)

    def src(it):
        if not it.get("thumb"):
            return ""
        rel = os.path.relpath(it["thumb"], outdir).replace("\\", "/")
        return urllib.parse.quote(rel)

    groups = {b: [] for b in s["bins"]}
    for it in s["items"]:
        groups.setdefault(it["top"][0]["bin"], []).append(it)
    ev = s.get("eval") or {}
    rows = []
    if "top1" in ev:
        rows.append("<p>Đã có nhãn của bạn: <b>%d</b> clip. Gợi ý hạng 1 trùng nhãn: <b>%.0f%%</b>; nhãn nằm trong 3 gợi ý đầu: <b>%.0f%%</b>.</p>"
                    % (ev["labeled"], ev["top1"] * 100, ev["top3"] * 100))
        rows.append("<table><tr><th>Bin</th><th>Clip bạn xếp</th><th>Gợi ý trúng (recall)</th><th>Số gợi ý hạng 1</th><th>Đúng trong số đó (precision)</th></tr>")
        for b, v in ev["per_bin"].items():
            pc = lambda x: "—" if x is None else "%.0f%%" % (x * 100)      # noqa: E731
            rows.append("<tr><td>%s</td><td>%d</td><td>%s</td><td>%d</td><td>%s</td></tr>"
                        % (html.escape(b), v["labeled"], pc(v["top1_recall"]), v["predicted"], pc(v["precision"])))
        rows.append("</table>")
    else:
        rows.append("<p>%s (đã có nhãn: %d).</p>" % (html.escape(ev.get("note", "")), ev.get("labeled", 0)))
    parts = ["<!doctype html><html lang='vi'><head><meta charset='utf-8'><title>Gợi ý bin theo mô tả (AI) — chỉ tham khảo</title>"
             "<style>body{font:14px Segoe UI,Arial;background:#14161a;color:#e6e6e6;margin:20px}h1{font-size:20px}h2{font-size:16px;margin-top:28px;"
             "border-bottom:1px solid #333;padding-bottom:4px}.g{display:flex;flex-wrap:wrap;gap:8px}.c{width:164px;font-size:11px;color:#aaa}"
             ".c img{width:164px;height:92px;object-fit:cover;border-radius:3px;display:block;background:#222}.ok{color:#6ecf8a}.bad{color:#f0a060}"
             "table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid #333;padding:3px 8px;text-align:left}.note{color:#9aa;max-width:900px}</style></head><body>",
             "<h1>Gợi ý bin theo mô tả — dự án %s</h1>" % html.escape(s["project_tag"]),
             "<p class='note'>Chỉ để THAM KHẢO. AI so ảnh với mô tả chữ, có thể sai; không có clip nào bị chuyển bin. Mô hình: %s, chạy trên máy này, "
             "ảnh không gửi đi đâu. Tổng %d clip.</p>" % (html.escape(s["model"]), s["count"])] + rows
    for b, its in groups.items():
        its = sorted(its, key=lambda x: -x["top"][0]["score"])
        parts.append("<h2>%s — %d clip gợi ý</h2><p class='note'>Mô tả dùng: %s</p><div class='g'>" % (
            html.escape(b), len(its), html.escape(" | ".join(s["prompts"].get(b, [])))))
        for it in its:
            tops = " · ".join("%s %.0f%%" % (html.escape(t["bin"]), t["score"] * 100) for t in it["top"])
            lab = it.get("label")
            mark = "" if not lab else (" <span class='ok'>(bạn xếp: %s ✓)</span>" if lab == it["top"][0]["bin"] else " <span class='bad'>(bạn xếp: %s)</span>") % html.escape(lab)
            parts.append("<div class='c'><img loading='lazy' src='%s' alt=''><div>%s%s</div><div>%s</div></div>" % (src(it), html.escape(it["name"]), mark, tops))
        parts.append("</div>")
    parts.append("</body></html>")
    p = os.path.join(outdir, "index.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    return p


# ---------------------------------------------------------------------------
# Dùng trong panel (ADR-0022): chỉ ĐỌC file gợi ý + vector; gợi ý hạng 1-3 trong các bin của giai đoạn clip đang ở
# ---------------------------------------------------------------------------
MIN_FEWSHOT_LABELS = 20          # từ ngần này clip có nhãn tay (có vector) trong project thì học từ nhãn thay vì chỉ theo mô tả
MIN_FEWSHOT_IN_STAGE = 3         # ... và ít nhất ngần này clip đã xếp trong các bin của giai đoạn đang xét
KNN_K = 7
KNN_TEMP = 20.0


def ck(rel):
    """Khóa so khớp clip panel <-> vector/gợi ý: (thư mục cha, tên không đuôi) không phân biệt hoa thường. Đuôi proxy (.mov) khác file gốc (.MP4)."""
    parts = (rel or "").replace("\\", "/").split("/")
    return ((parts[-2] if len(parts) > 1 else "").casefold(), os.path.splitext(parts[-1])[0].casefold())


def is_orphan_key(k):
    """Khóa của thumbnail 'mồ côi' (nhúng khi project không còn proxy): không có tên clip nên không thể ghép với clip trong kế hoạch."""
    parent, stem = k
    return parent == "" and (stem.startswith("thumb:") or stem.startswith("(không ghép"))


def load_vectors(data_root, project):
    """{ck: vector} từ cache nhúng, hoặc {} nếu chưa có. Cần numpy."""
    import numpy as np
    f = os.path.join(embed_dir(data_root, project), "vectors.npz")
    if not os.path.isfile(f):
        return {}
    with np.load(f, allow_pickle=False) as z:
        keys, vecs = list(z["keys"]), z["vecs"].copy()
    out = {}
    for k, v in zip(keys, vecs):
        stem, _, parent = str(k).partition("|")
        out[(parent.casefold(), stem.casefold())] = v
    return out


def load_suggest(data_root, project):
    """(bins, {ck: scores theo bins}, mô tả) từ file gợi ý theo mô tả, hoặc None nếu chưa chạy."""
    p = os.path.join(data_root, "troly", "ai_suggest", tc._safe(project) + ".json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    out = {}
    for it in d.get("items", []):
        if it.get("scores"):
            out[ck(it["clip"])] = it["scores"]
    return d.get("bins", []), out


def _top3(pairs, skip=()):
    pairs = [(b, s) for b, s in pairs if b not in skip]
    pairs.sort(key=lambda x: -x[1])
    return [{"bin": b, "score": round(float(s), 3)} for b, s in pairs[:3]]


def rank_for_clip(key, cand_bins, vectors, labeled, desc, k=KNN_K, temp=KNN_TEMP):
    """Gợi ý hạng 1-3 cho một clip trong các bin cand_bins (bin của giai đoạn clip đang ở).
    labeled = {ck: bin} nhãn tay (của anh); desc = (bins, {ck: scores}) theo mô tả.
    Trả (nguồn 'nhan'|'mo_ta'|None, [{'bin','score'}...]). Điểm đã chuẩn hóa trong các bin của giai đoạn (cộng lại = 1)."""
    import numpy as np
    v = vectors.get(key)
    if v is not None and len(labeled) >= MIN_FEWSHOT_LABELS:
        pool = [(kk, b) for kk, b in labeled.items() if b in cand_bins and kk != key and kk in vectors]
        if len(pool) >= MIN_FEWSHOT_IN_STAGE:
            M = np.stack([vectors[kk] for kk, _ in pool])
            sims = M @ v
            idx = np.argsort(-sims)[:k]
            w = np.exp(temp * (sims[idx] - sims[idx].max()))
            sc = {}
            for j, wi in zip(idx, w):
                sc[pool[j][1]] = sc.get(pool[j][1], 0.0) + float(wi)
            tot = sum(sc.values()) or 1.0
            return "nhan", _top3([(b, x / tot) for b, x in sc.items()])
    if desc and key in desc[1]:
        bins, table = desc
        sc = [(b, x) for b, x in zip(bins, table[key]) if b in cand_bins]
        tot = sum(x for _, x in sc)
        if sc and tot > 0:
            return "mo_ta", _top3([(b, x / tot) for b, x in sc])
    return None, []


def ai_python(cfg_value=None):
    return cfg_value or r"C:\VideoAI_ai_venv\Scripts\python.exe"


class AiJob(object):
    """Chạy nhúng + gợi ý bằng venv AI trong tiến trình con (nền). Dừng bằng cờ STOP (làm tiếp được: chạy lại). Không tự chạy gì khác."""

    def __init__(self, project, data_root, python=None):
        self.project, self.root = project, data_root
        self.python = ai_python(python)
        self._proc = None

    def available(self):
        return os.path.isfile(self.python) and (has_siglip(self.root) or os.path.isfile(model_path(self.root)))

    def running(self):
        return self._proc is not None and self._proc.poll() is None

    def start(self):
        if self.running():
            return True
        if not self.available():
            return False
        import subprocess
        import troly_proc
        d = embed_dir(self.root, self.project)
        os.makedirs(d, exist_ok=True)
        stop = os.path.join(d, "STOP")
        if os.path.isfile(stop):
            os.remove(stop)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._proc = troly_proc.mo_an([self.python, "-X", "utf8", os.path.join(APP, "troly_ai.py"), "run", "--project", self.project],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        return True

    def stop(self):
        d = embed_dir(self.root, self.project)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "STOP"), "w").close()

    def last_log(self):
        log = os.path.join(self.root, "logs", "ai_embed_%s.log" % hashlib.sha1(self.project.encode("utf-8")).hexdigest()[:8])
        try:
            with open(log, "r", encoding="utf-8") as f:
                lines = f.read().strip().splitlines()
            return lines[-1][9:] if lines else ""
        except OSError:
            return ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("embed", "suggest", "review", "all", "run"))
    ap.add_argument("--project", required=True)
    ap.add_argument("--stop", action="store_true")
    a = ap.parse_args(argv)
    dr, pr = _root()
    if a.stop:
        d = embed_dir(dr, a.project)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "STOP"), "w").close()
        print("Đã đặt cờ dừng.")
        return 0
    res = {}
    if a.cmd == "run":                                      # panel gọi: nhúng rồi gợi ý; bị dừng giữa chừng thì không gợi ý
        res["embed"] = run_embed(a.project, dr, pr)
        if not os.path.isfile(os.path.join(embed_dir(dr, a.project), "STOP")):
            res["suggest"] = run_suggest(a.project, dr, pr)
        print(json.dumps(res, ensure_ascii=False))
        return 0
    if a.cmd in ("embed", "all"):
        res["embed"] = run_embed(a.project, dr, pr)
    if a.cmd in ("suggest", "all"):
        res["suggest"] = run_suggest(a.project, dr, pr)
    if a.cmd in ("review", "all"):
        res["review"] = build_review(a.project, dr)
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
