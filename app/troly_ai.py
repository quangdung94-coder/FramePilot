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
import re
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
SIGLIP2_DIR_NAME = "siglip2_vitb16"
SIGLIP2_ARCH = "ViT-B-16-SigLIP2"
DINOV2_DIR_NAME = "dinov2_small"
TEMPERATURE = 100.0                 # CLIP: logit_scale ~100
SIGLIP2_TEMP = 35.0                 # SigLIP2: nhiệt độ softmax theo từng giai đoạn trên điểm cosine thô
KHAC_COSINE_PENALTY = 0.055         # giảm thiên lệch khiến mục 'Khác' hút nhầm clip quay thật
BATCH = 32
THUMB_WIDTH = 320


def _root():
    import troly_env
    return troly_env.default_data_root(), (troly_env.config().get("proxy_root") or "")


def _norm(s):
    return unicodedata.normalize("NFC", (s or "")).casefold()


def strip_accents(s):
    """Chuẩn hóa tiếng Việt không dấu, bỏ số thứ tự đầu, đổi _/- thành khoảng trắng, viết thường.
    Ví dụ: '02_Làm lễ tại gia' -> 'lam le tai gia', 'CDCR' -> 'cdcr'."""
    t = str(s or "").replace("đ", "d").replace("Đ", "D")
    t = unicodedata.normalize("NFD", t)
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = t.casefold()
    t = re.sub(r"^\s*\d+\s*[._\-)\s]+", "", t)
    t = re.sub(r"[^a-z0-9&]+", " ", t)
    return " ".join(t.split())


# ---------------------------------------------------------------------------
# Bộ Thẻ cảnh chuẩn nghề cưới VN (Phương án B): tách tên bin hiển thị khỏi loại cảnh AI hiểu.
# Thứ tự ưu tiên so khớp: cụm dài/cụ thể trước (vd 'co dau chu re' trước 'co dau' / 'chu re').
# ---------------------------------------------------------------------------
CONCEPTS = (
    {"id": "cap_doi", "label": "Cô dâu chú rể", "group": "Chung", "default": "Cô dâu chú rể",
     "keys": ("co dau chu re", "co dau va chu re", "co dau & chu re", "cdcr", "cd cr", "cap doi", "couple", "first look", "chup doi", "portrait doi"),
     "prompts": ["the bride and groom standing together holding hands or hugging",
                 "a romantic portrait of the wedding couple smiling together",
                 "a newlywed bride and groom walking side by side"]},
    {"id": "cu_ong_cu_ba", "label": "Cụ ông cụ bà", "group": "Mừng thọ", "default": "Cụ ông cụ bà",
     "keys": ("cu ong cu ba", "cu ong va cu ba", "cu ong & cu ba", "ong ba", "hai cu", "thuong tho", "dai tho"),
     "prompts": ["an elderly Vietnamese couple in red or gold traditional ao dai smiling together at a longevity celebration",
                 "a happy senior grandfather and grandmother sitting or posing together at a family celebration",
                 "elderly parents wearing formal traditional Vietnamese clothes celebrating longevity"]},
    {"id": "cu_ong", "label": "Cụ ông", "group": "Mừng thọ", "default": "Cụ ông",
     "keys": ("cu ong", "ong cu", "ong noi", "ong ngoai", "chan dung cu ong"),
     "prompts": ["an elderly Vietnamese grandfather smiling in traditional ao dai or formal suit portrait",
                 "a happy old man wearing red or gold traditional silk tunic at a family longevity party",
                 "close-up portrait of a smiling senior grandfather"]},
    {"id": "cu_ba", "label": "Cụ bà", "group": "Mừng thọ", "default": "Cụ bà",
     "keys": ("cu ba", "ba cu", "ba noi", "ba ngoai", "chan dung cu ba"),
     "prompts": ["an elderly Vietnamese grandmother smiling in traditional ao dai portrait",
                 "a happy old woman wearing red or gold traditional Vietnamese ao dai at a longevity celebration",
                 "close-up portrait of a smiling senior grandmother"]},
    {"id": "chuc_tho", "label": "Chúc thọ · Trao quà", "group": "Mừng thọ", "default": "Trao quà · Mừng thọ",
     "keys": ("trao qua mung tho", "chuc tho", "mung tho", "dang hoa", "tang hoa", "bang mung tho", "khanh vang", "cat banh tho"),
     "prompts": ["children and grandchildren presenting flowers, gifts or longevity plaque to elderly grandparents on stage",
                 "a Vietnamese longevity celebration ceremony with red and gold backdrop, cake and family congratulating elders",
                 "relatives bowing and offering longevity gifts to an elderly grandfather and grandmother"]},
    {"id": "ev_khong_gian", "label": "Không gian · Sân khấu Event", "group": "Event", "default": "Không gian · Decor",
     "keys": ("khong gian decor", "sanh tiec", "san khau led", "flycam", "toan canh", "setup", "mat tien", "teabreak"),
     "prompts": ["wide shot of a corporate conference hall or gala banquet room with large LED stage screen and lighting",
                 "aerial or establishing shot of an event venue, stage, decorated tables and spotlights",
                 "event setup and teabreak table in a modern convention center"]},
    {"id": "ev_thuong_hieu", "label": "Logo · Sản phẩm · Booth", "group": "Event", "default": "Logo · Sản phẩm",
     "keys": ("logo san pham", "logo thuong hieu", "logo", "san pham", "thuong hieu", "booth", "gian hang", "standee", "trung bay", "demo san pham", "trai nghiem", "tham quan"),
     "prompts": ["close-up of a company logo backdrop, brand standee or product display booth at an event",
                 "exhibition booth showcasing products and branded gifts at a corporate launch event",
                 "guests visiting and trying products at a branded display counter"]},
    {"id": "ev_checkin", "label": "Check-in · Khách mời VIP", "group": "Event", "default": "Check-in · Backdrop",
     "keys": ("check in", "checkin", "photobooth", "tham do", "khach moi vip", "khach moi", "hoc sinh", "phu huynh", "chup hinh tap the"),
     "prompts": ["guests checking in at a registration desk or walking a red carpet at an event",
                 "people posing and taking group photos in front of an event backdrop or photobooth",
                 "students, parents or VIP guests arriving and smiling at an event entrance"]},
    {"id": "ev_phat_bieu", "label": "MC · Diễn giả · Tọa đàm", "group": "Event", "default": "MC · Phát biểu",
     "keys": ("mc phat bieu", "keynote", "dien gia", "toa dam", "panel", "slide", "hieu truong", "lanh dao", "lop hoc"),
     "prompts": ["a keynote speaker or CEO speaking into a microphone at a podium in front of a presentation LED screen",
                 "a panel discussion with speakers sitting on stage holding microphones at a conference",
                 "an MC hosting a corporate gala or school opening ceremony on stage"]},
    {"id": "ev_nghi_thuc", "label": "Nghi thức · Cắt băng · Chào cờ", "group": "Event", "default": "Nghi thức · Cắt băng · Chào cờ",
     "keys": ("cat bang", "bam nut", "chao co", "danh trong", "khai truong", "khai giang", "khai truong", "nang ly", "khui sam panh", "mam cung", "nghi thuc", "tha bong bay"),
     "prompts": ["ribbon cutting ceremony with red ribbon and scissors at a grand opening event",
                 "VIP leaders pressing an illuminated launch button or raising glasses for a toast on stage",
                 "flag raising ceremony or school principal beating a large opening drum at a school ceremony"]},
    {"id": "ev_vinh_danh", "label": "Vinh danh · Trao giải", "group": "Event", "default": "Vinh danh · Trao giải",
     "keys": ("vinh danh", "trao giai", "trao cup", "bang khen", "ky niem chuong", "trao hoc bong"),
     "prompts": ["award ceremony on stage presenting trophies, certificates, flowers or plaques to winners",
                 "corporate leaders shaking hands and handing out awards on a bright stage",
                 "students or employees smiling while holding awards and certificates on stage"]},
    {"id": "ev_khan_gia", "label": "Khán giả · Phản ứng", "group": "Event", "default": "Khán giả · Phản ứng",
     "keys": ("khan gia", "phan ung", "vo tay", "hoi dap", "ban tiec", "khong khi ban tiec", "cung ly", "giao luu"),
     "prompts": ["audience clapping, smiling and listening attentively in rows of chairs at a conference or event",
                 "gala dinner guests sitting at round banquet tables laughing and clinking glasses",
                 "crowd of attendees cheering and taking photos with smartphones at an event"]},
    {"id": "ev_van_nghe", "label": "Văn nghệ · Múa lân · Minigame", "group": "Event", "default": "Văn nghệ · Biểu diễn",
     "keys": ("mua lan", "lan su rong", "opening", "opening show", "minigame", "boc tham", "lucky draw", "ca si", "dj", "bieu dien", "trong hoi"),
     "prompts": ["lion dance performance with red and gold lions and drums at a grand opening celebration",
                 "singers, dancers or live band performing on an illuminated stage with colorful spotlights",
                 "exciting stage minigame or lucky draw prize giveaway at a corporate year end party"]},
    {"id": "phong_van", "label": "Phỏng vấn", "group": "Chung", "default": "Phỏng vấn",
     "keys": ("phong van", "interview", "chia se", "tam su", "cam nghi", "pv"),
     "prompts": ["a person being interviewed, looking at the camera and talking",
                 "a person speaking into a microphone",
                 "an interview shot of one person sitting and talking at a wedding"]},
    {"id": "nghi_le_san_khau", "label": "Nghi lễ sân khấu", "group": "Nhà hàng", "default": "Nghi lễ sân khấu",
     "keys": ("nghi le san khau", "nghi le nha hang", "lam le san khau", "san khau", "rot ruou", "cat banh", "vows", "loi the", "trao nhan", "le duong", "khai tiec", "tung hoa", "tien vao le duong"),
     "prompts": ["a wedding stage with lights, screen and flower arch during the ceremony",
                 "the bride and groom pouring champagne tower or cutting wedding cake on stage",
                 "a bride and groom walking down the aisle or exchanging rings and vows on stage"]},
    {"id": "nghi_le_tai_gia", "label": "Nghi lễ tại gia", "group": "Gia tiên", "default": "Nghi lễ tại gia",
     "keys": ("nghi le tai gia", "lam le tai gia", "nghi le gia tien", "gia tien", "ban tho", "nhang", "vu quy", "tan hon", "thanh hon", "dang tra", "len den", "trao vang", "trao qua", "lay ong ba", "an hoi", "dam ngo", "tai gia"),
     "prompts": ["a traditional Vietnamese wedding ceremony at home with an ancestral altar, red backdrop, incense and offerings",
                 "a bride and groom in traditional ao dai bowing at an ancestral altar",
                 "a Vietnamese family ceremony inside a house exchanging tea and gold jewelry"]},
    {"id": "le_nha_tho", "label": "Lễ nhà thờ", "group": "Đặc thù", "default": "Lễ nhà thờ",
     "keys": ("nha tho", "thanh le", "cha xu", "church", "hon phoi", "le nha tho"),
     "prompts": ["a wedding ceremony inside a church with pews, altar and priest",
                 "a bride and groom walking down a church aisle",
                 "a Catholic wedding ceremony at a church altar"]},
    {"id": "phat_bieu", "label": "Phát biểu", "group": "Nhà hàng", "default": "Phát biểu",
     "keys": ("phat bieu", "dien van", "loi cam on", "speech", "mc"),
     "prompts": ["a person giving a speech with a microphone at a wedding",
                 "parents or a speaker standing at a podium in front of wedding guests"]},
    {"id": "le_vat", "label": "Lễ vật / Mâm quả", "group": "Gia tiên", "default": "Lễ vật",
     "keys": ("le vat", "mam qua", "be trap", "trao le", "sinh le", "trap"),
     "prompts": ["relatives carrying red gift trays with offerings for a Vietnamese wedding",
                 "people in ao dai holding trays covered with red cloth",
                 "exchanging wedding gift trays between two families"]},
    {"id": "nha_trai_den", "label": "Nhà trai đến", "group": "Gia tiên", "default": "Nhà trai đến",
     "keys": ("nha trai den", "nha gai den", "don doan"),
     "prompts": ["groom and family arriving outside the house gate carrying red gift trays",
                 "wedding procession walking into the bride house entrance"]},
    {"id": "ruoc_dau", "label": "Rước dâu / Xe hoa", "group": "Gia tiên", "default": "Rước dâu",
     "keys": ("ruoc dau", "don dau", "nha trai", "nha gai", "xe hoa", "doan ruoc", "ruoc", "di chuyen"),
     "prompts": ["bride and groom walking out to a decorated wedding car with flowers",
                 "decorated wedding car and family departing after the home ceremony",
                 "a wedding procession with decorated cars and people"]},
    {"id": "chup_hinh", "label": "Chụp hình / Backdrop", "group": "Nhà hàng", "default": "Chụp hình",
     "keys": ("chup hinh", "chup cong"),
     "prompts": ["bride and groom posing with a group of family and friends for a photo at a flower backdrop",
                 "posed group photo of people standing in a row smiling at the camera at a wedding backdrop"]},
    {"id": "don_khach", "label": "Đón khách / Khách", "group": "Nhà hàng", "default": "Đón khách",
     "keys": ("don khach", "ky ten", "tiep tan", "khach"),
     "prompts": ["wedding guests arriving at the hall entrance, greeting or signing the guest book",
                 "crowd of wedding guests standing, chatting, clapping or watching a wedding stage",
                 "guests dancing, singing or celebrating at a wedding party at night"]},
    {"id": "gia_dinh", "label": "Gia đình", "group": "Chung", "default": "Gia đình",
     "keys": ("gia dinh", "ho hang", "nguoi than", "bo me", "ba me", "cha me", "family", "tap the", "phu dau", "phu re", "ban be"),
     "prompts": ["family members and parents sitting and chatting casually at home before a wedding",
                 "relatives smiling and helping prepare at home in formal ao dai or suits",
                 "portrait of parents and relatives at home"]},
    {"id": "get_ready", "label": "Get ready / Sửa soạn", "group": "Chuẩn bị", "default": "get ready",
     "keys": ("get ready", "sua soan", "chuan bi do"),
     "prompts": ["bride getting hair and makeup done in a room before the wedding",
                 "groom putting on suit, tie or getting ready in a bedroom",
                 "bride putting on wedding dress, veil, shoes or jewelry in dressing room",
                 "close-up of wedding dress hanging, bridal shoes, bouquet or groom details while preparing"]},
    {"id": "chu_re", "label": "Chú rể", "group": "Chuẩn bị", "default": "Chú rể",
     "keys": ("chu re", "groom", "vest", "thay do chu re", "cr"),
     "prompts": ["a groom in a black suit posing for a portrait",
                 "a groom wearing a suit and boutonniere getting ready",
                 "a man in a suit at a wedding, groom close-up"]},
    {"id": "co_dau", "label": "Cô dâu / Beauty", "group": "Chuẩn bị", "default": "Beauty cô dâu",
     "keys": ("co dau", "beauty", "makeup", "make up", "trang diem", "bridal", "vay cuoi", "thay vay", "cd"),
     "prompts": ["a bride in a white wedding dress posing for a portrait",
                 "a bride getting her makeup done by a makeup artist",
                 "a beautiful bride close-up, bridal portrait",
                 "a bride putting on her wedding dress and veil"]},
    {"id": "decor", "label": "Decor / Chi tiết", "group": "Chung", "default": "Decor",
     "keys": ("decor", "trang tri", "chi tiet", "detail", "broll", "b roll", "gallery", "cong hoa", "backdrop", "khong gian", "khong gian decor", "venue", "flycam", "drone", "nhan cuoi", "hoa cuoi"),
     "prompts": ["empty decorated wedding room, floral arch, stage or red wedding backdrop with no people",
                 "close-up of wedding rings, bridal bouquet, table flowers, candles or tea set without people",
                 "wide establishing shot of wedding hall decoration and tables before guests arrive"]},
    {"id": "chao_ban", "label": "Chào bàn / Tiệc", "group": "Nhà hàng", "default": "Chào bàn",
     "keys": ("chao ban", "nang ly", "cung ly", "moi ruou", "di ban", "tiec man", "tiec toi", "an tiec", "banquet", "tiec", "nha hang"),
     "prompts": ["bride and groom holding glasses toasting with guests at round dining tables",
                 "people clinking beer or wine glasses at a round wedding banquet table with dishes"]},
    {"id": "choi_game", "label": "Chơi game / Tiệc vui", "group": "Đặc thù", "default": "Chơi game",
     "keys": ("choi game", "game", "tro choi", "after party", "party", "nhay", "ca hat", "van nghe", "quay", "karaoke"),
     "prompts": ["wedding guests playing fun party games on stage and laughing",
                 "people dancing and celebrating at a wedding after party with colorful lights",
                 "guests singing and cheering at a lively wedding reception"]},
    {"id": "mua_lan", "label": "Múa lân / Biểu diễn", "group": "Đặc thù", "default": "Múa lân",
     "keys": ("mua lan", "lan su rong", "bieu dien", "mua hat", "ca si", "ban nhac"),
     "prompts": ["traditional colorful Vietnamese lion dance performance at a wedding",
                 "lion dancers and drummers performing at a wedding entrance or banquet hall",
                 "a live stage performance or dancers at a wedding reception"]},
    {"id": "khac", "label": "Khác", "group": "Chung", "default": "Khác",
     "keys": ("khac", "other", "rac", "loi", "out net", "nhap"),
     "prompts": ["a blurry out-of-focus shot of the floor, ceiling, or lens cap",
                 "completely dark black screen or accidental camera movement"]},
)

CONCEPT_BY_ID = {c["id"]: c for c in CONCEPTS}
_STAGE_HALL_HINTS = ("nha hang", "tiec", "toi", "gala", "san khau", "le duong", "reception", "banquet", "mung tho")
_STAGE_CHURCH_HINTS = ("nha tho", "thanh le", "church")
_STAGE_EVENT_HINTS = ("event", "hoi nghi", "khai truong", "khai giang", "gala", "truong", "setup", "hoat dong", "check in", "khai mac")
_EVENT_SHARED_KEYS = ("khong gian decor", "flycam", "toan canh", "setup", "mat tien", "chup hinh", "van nghe", "bieu dien")
_GENERIC_CEREMONY = ("nghi le", "lam le", "le cuoi", "le", "nl")


def concept_list():
    """Danh sách thẻ cảnh chuẩn cho giao diện (Page 1 menu sổ ra & Page 2 menu chuột phải)."""
    return [{"id": c["id"], "label": c["label"], "group": c["group"], "default": c["default"]} for c in CONCEPTS]


def _has_phrase(norm_text, phrase):
    if not norm_text or not phrase:
        return False
    return re.search(r"(?:^|\s)" + re.escape(phrase) + r"(?:$|\s)", norm_text) is not None


def synonyms_path(data_root):
    """File từ nhớ riêng của editor (<data_root>/troly/ai_synonyms.json), KHÔNG nằm trong cache xóa được."""
    return os.path.join(data_root, "troly", "ai_synonyms.json")


def load_synonyms(data_root):
    p = synonyms_path(data_root)
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            return {
                "by_bin": dict(d.get("by_bin") or {}),
                "by_stage_bin": dict(d.get("by_stage_bin") or {}),
                "custom_names": list(d.get("custom_names") or []),
            }
    except (OSError, ValueError):
        pass
    return {"by_bin": {}, "by_stage_bin": {}, "custom_names": []}


def save_synonym(data_root, bin_name, concept_id, stage_name=""):
    """Lưu từ nhớ riêng của editor (ánh xạ tên bin -> thẻ cảnh chuẩn + nhớ tên bin để gợi ý lại ở Page 1)."""
    if not data_root or not bin_name:
        return None
    nb = strip_accents(bin_name)
    ns = strip_accents(stage_name)
    if not nb:
        return None
    d = load_synonyms(data_root)
    if concept_id and concept_id in CONCEPT_BY_ID:
        d["by_bin"][nb] = concept_id
        if ns:
            d["by_stage_bin"][ns + "|" + nb] = concept_id
    elif concept_id == "":
        d["by_bin"].pop(nb, None)
        if ns:
            d["by_stage_bin"].pop(ns + "|" + nb, None)
    clean_name = " ".join(str(bin_name).split()).strip()
    if clean_name and clean_name not in d["custom_names"]:
        d["custom_names"].append(clean_name)
        d["custom_names"] = d["custom_names"][-60:]
    p = synonyms_path(data_root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(p + ".tmp", p)
    return d


def infer_concept(bin_name, stage_name="", custom_map=None):
    """Đoán Thẻ cảnh chuẩn từ tên bin (có dấu hoặc không dấu/viết tắt) + ngữ cảnh Cụm sự kiện mẹ + từ nhớ riêng."""
    nb = strip_accents(bin_name)
    ns = strip_accents(stage_name)
    if not nb:
        return None
    if isinstance(custom_map, dict):
        by_sb = custom_map.get("by_stage_bin") or {}
        by_b = custom_map.get("by_bin") or {}
        if ns and (ns + "|" + nb) in by_sb and by_sb[ns + "|" + nb] in CONCEPT_BY_ID:
            return by_sb[ns + "|" + nb]
        if nb in by_b and by_b[nb] in CONCEPT_BY_ID:
            return by_b[nb]
    # 1. Các nhóm hành động đặc thù luôn thắng từ chỉ người đi kèm (vd 'PV Khách', 'Phỏng vấn cô dâu' -> phong_van)
    for priority_id in ("phong_van", "phat_bieu", "mua_lan", "choi_game", "le_nha_tho"):
        c = CONCEPT_BY_ID[priority_id]
        if any(_has_phrase(nb, kw) for kw in c["keys"]):
            return priority_id
    # 2. Cụm nghi lễ ('nghi le', 'lam le', 'le cuoi') ưu tiên phân loại theo sân khấu / nhà thờ / tại gia trước 'chu re'/'co dau'
    if any(_has_phrase(nb, g) for g in ("nghi le", "lam le", "le cuoi", "nl")):
        if any(_has_phrase(nb, kw) for kw in CONCEPT_BY_ID["nghi_le_san_khau"]["keys"]) or any(_has_phrase(ns, h) for h in _STAGE_HALL_HINTS):
            return "nghi_le_san_khau"
        if any(_has_phrase(nb, kw) for kw in CONCEPT_BY_ID["le_nha_tho"]["keys"]) or any(_has_phrase(ns, h) for h in _STAGE_CHURCH_HINTS):
            return "le_nha_tho"
        return "nghi_le_tai_gia"
    # 3. Khớp theo cụm từ khóa chuẩn (ưu tiên cụm dài trước, theo ranh giới từ)
    is_event_stage = any(_has_phrase(ns, h) for h in _STAGE_EVENT_HINTS)
    best = None
    best_len = 0
    for c in CONCEPTS:
        if c["id"] == "ev_khong_gian" and not is_event_stage and _has_phrase(nb, "khong gian decor"):
            continue
        for kw in c["keys"]:
            if c["id"].startswith("ev_") and not is_event_stage and kw in _EVENT_SHARED_KEYS:
                continue
            if _has_phrase(nb, kw) and len(kw) > best_len:
                best = c["id"]
                best_len = len(kw)
    if best:
        return best
    # 4. Chữ 'le' đứng riêng -> phân biệt theo ngữ cảnh cụm mẹ (Stage)
    if _has_phrase(nb, "le"):
        if any(_has_phrase(ns, h) for h in _STAGE_CHURCH_HINTS):
            return "le_nha_tho"
        if any(_has_phrase(ns, h) for h in _STAGE_HALL_HINTS):
            return "nghi_le_san_khau"
        return "nghi_le_tai_gia"
    return None


def prompts_for(bin_name, stage_name="", custom_map=None):
    cid = infer_concept(bin_name, stage_name=stage_name, custom_map=custom_map)
    if cid and cid in CONCEPT_BY_ID:
        return list(CONCEPT_BY_ID[cid]["prompts"])
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


def siglip2_dir(data_root):
    return os.path.join(data_root, "models", SIGLIP2_DIR_NAME)


def has_siglip2(data_root):
    d = siglip2_dir(data_root)
    return os.path.isfile(os.path.join(d, MODEL_FILE))


def dinov2_dir(data_root):
    return os.path.join(data_root, "models", DINOV2_DIR_NAME)


def has_dinov2(data_root):
    d = dinov2_dir(data_root)
    return os.path.isdir(d) and os.path.isfile(os.path.join(d, "config.json"))


def load_model(data_root):
    import open_clip
    import torch
    import troly_env
    dev = troly_env.torch_device(torch)
    if has_siglip2(data_root):
        sd2 = siglip2_dir(data_root)
        w2 = os.path.join(sd2, MODEL_FILE)
        model, _, pre = open_clip.create_model_and_transforms(SIGLIP2_ARCH, pretrained=w2, device=dev)
        model.eval()
        return model, pre, open_clip.get_tokenizer(SIGLIP2_ARCH), dev
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
    if has_siglip2(data_root):
        sub = "troly_embed_siglip2"
    elif has_siglip(data_root):
        sub = "troly_embed_siglip"
    else:
        sub = "troly_embed"
    return os.path.join(data_root, "cache", sub, tc._safe(project))


def _load_npz_kv(path):
    """Đọc file .npz (keys, vecs) an toàn; tự cứu đọc file cũ bị lưu nhầm dtype=object."""
    import numpy as np
    try:
        with np.load(path, allow_pickle=False) as z:
            return [str(k) for k in z["keys"]], z["vecs"].copy(), False
    except ValueError:
        with np.load(path, allow_pickle=True) as z:
            return [str(k) for k in z["keys"]], z["vecs"].copy(), True


def run_embed_dino(project, data_root, proxy_root):
    """Nhúng thêm vector DINOv2-small (384 chiều) cho 'Tìm góc tương tự' & học mẫu 2-3 clip. Lưu cạnh vectors.npz."""
    if not has_dinov2(data_root):
        return {"skipped": True}
    import numpy as np
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModel

    d = embed_dir(data_root, project)
    os.makedirs(d, exist_ok=True)
    clips, _ = match_thumbs(project, data_root, proxy_root)
    todo_all = [c for c in clips if c["thumb"]]
    npz = os.path.join(d, "dino_vectors.npz")
    keys, vecs, was_pickled = [], None, False
    if os.path.isfile(npz):
        keys, vecs, was_pickled = _load_npz_kv(npz)
    done = set(keys)
    todo = [c for c in todo_all if c["key"] not in done]
    if not todo:
        if was_pickled and keys and vecs is not None:
            tmp = npz + ".tmp.npz"
            np.savez(tmp, keys=np.array(keys), vecs=vecs)
            os.replace(tmp, npz)
        return {"embedded": len(done), "new": 0}
    import troly_env
    dev = troly_env.torch_device(torch)
    ddir = dinov2_dir(data_root)
    proc = AutoImageProcessor.from_pretrained(ddir, local_files_only=True)
    model = AutoModel.from_pretrained(ddir, local_files_only=True).to(dev).eval()
    new_k, new_v = [], []
    stop = os.path.join(d, "STOP")
    with torch.no_grad():
        for i in range(0, len(todo), BATCH):
            if os.path.isfile(stop):
                break
            batch = todo[i:i + BATCH]
            imgs, ok_k = [], []
            for c in batch:
                try:
                    with Image.open(c["thumb"]) as im:
                        imgs.append(im.convert("RGB").copy())
                        ok_k.append(c["key"])
                except (OSError, ValueError):
                    pass
            if not imgs:
                continue
            inp = proc(images=imgs, return_tensors="pt").to(dev)
            v = model(**inp).last_hidden_state[:, 0]
            v = v / v.norm(dim=-1, keepdim=True)
            for k_it, row in zip(ok_k, v.float().cpu().numpy()):
                new_k.append(k_it)
                new_v.append(row)
    if new_k or was_pickled:
        mat = np.stack(new_v).astype(np.float32) if new_v else None
        all_k = keys + new_k
        if vecs is not None and mat is not None:
            all_v = np.concatenate([vecs, mat], axis=0)
        else:
            all_v = mat if mat is not None else vecs
        if all_k and all_v is not None:
            tmp = npz + ".tmp.npz"
            np.savez(tmp, keys=np.array(all_k), vecs=all_v)
            os.replace(tmp, npz)
    del model
    troly_env.torch_empty_cache(torch)
    return {"embedded": len(done) + len(new_k), "new": len(new_k)}


def load_dino_vectors(data_root, project):
    """{ck: vector DINOv2} từ cache nhúng, hoặc {} nếu chưa có."""
    f = os.path.join(embed_dir(data_root, project), "dino_vectors.npz")
    if not os.path.isfile(f):
        return {}
    keys, vecs, _ = _load_npz_kv(f)
    out = {}
    for k, v in zip(keys, vecs):
        stem, _, parent = str(k).partition("|")
        out[(parent.casefold(), stem.casefold())] = v
    return out


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
    syn = load_synonyms(data_root)
    tvecs = []
    cvecs = []
    with torch.no_grad():
        for b in bins:
            t = model.encode_text(tok(prompts_for(b, custom_map=syn)).to(dev))
            t = t / t.norm(dim=-1, keepdim=True)
            m = t.mean(0)
            tvecs.append((m / m.norm()).float().cpu().numpy())
        for c_def in CONCEPTS:
            tc_v = model.encode_text(tok(c_def["prompts"]).to(dev))
            tc_v = tc_v / tc_v.norm(dim=-1, keepdim=True)
            mc = tc_v.mean(0)
            cvecs.append((mc / mc.norm()).float().cpu().numpy())
    T = np.stack(tvecs)                                     # [bins, 512]
    logits = TEMPERATURE * vecs @ T.T
    e = np.exp(logits - logits.max(1, keepdims=True))
    prob = e / e.sum(1, keepdims=True)
    TC = np.stack(cvecs)                                    # [concepts, 512]
    csims = vecs @ TC.T
    clogits = TEMPERATURE * csims
    ce = np.exp(clogits - clogits.max(1, keepdims=True))
    cprob = ce / ce.sum(1, keepdims=True)
    c_ids = [c["id"] for c in CONCEPTS]
    clips, _ = match_thumbs(project, data_root, proxy_root)
    by_key = {c["key"]: c for c in clips}
    lab = labels_by_stem(plan)
    items = []
    for k, p, cp, cs in zip(keys, prob, cprob, csims):
        c = by_key.get(k)
        if not c:
            continue
        order = list(np.argsort(-p)[:3])
        stem_key = (c["rel"].split("/")[0].casefold(), c["name"].casefold())
        items.append({"clip": c["rel"], "name": c["name"], "thumb": c["thumb"],
                      "top": [{"bin": bins[j], "score": round(float(p[j]), 4)} for j in order],
                      "scores": [round(float(x), 4) for x in p],
                      "c_scores": [round(float(x), 4) for x in cp],
                      "c_sims": [round(float(x), 5) for x in cs],
                      "label": lab.get(stem_key)})
    out = {"project_tag": project[:10], "model": ("SigLIP2 %s" % SIGLIP2_ARCH if has_siglip2(data_root) else ("SigLIP %s" % SIGLIP_ARCH if has_siglip(data_root) else "OpenCLIP %s laion2b_s34b_b79k" % MODEL_ARCH)), "bins": bins,
           "concepts": c_ids,
           "prompts": {b: prompts_for(b, custom_map=syn) for b in bins}, "count": len(items), "items": items,
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
    f = os.path.join(embed_dir(data_root, project), "vectors.npz")
    if not os.path.isfile(f):
        return {}
    keys, vecs, _ = _load_npz_kv(f)
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


def load_concept_scores(data_root, project):
    """(concept_ids, {ck: c_scores}) từ file ai_suggest, hoặc None nếu bản cũ chưa có."""
    p = os.path.join(data_root, "troly", "ai_suggest", tc._safe(project) + ".json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    c_ids = d.get("concepts")
    if not isinstance(c_ids, list) or not c_ids:
        return None
    out = {}
    for it in d.get("items", []):
        if it.get("c_scores"):
            out[ck(it["clip"])] = it["c_scores"]
    return (c_ids, out) if out else None


def load_concept_sims(data_root, project):
    """(concept_ids, {ck: c_sims cosine thô}) từ file ai_suggest, hoặc None nếu bản cũ chưa có."""
    p = os.path.join(data_root, "troly", "ai_suggest", tc._safe(project) + ".json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    c_ids = d.get("concepts")
    if not isinstance(c_ids, list) or not c_ids:
        return None
    out = {}
    for it in d.get("items", []):
        if it.get("c_sims"):
            out[ck(it["clip"])] = it["c_sims"]
    return (c_ids, out) if out else None


def _top3(pairs, skip=()):
    pairs = [(b, s) for b, s in pairs if b not in skip]
    pairs.sort(key=lambda x: -x[1])
    return [{"bin": b, "score": round(float(s), 3)} for b, s in pairs[:3]]


MIN_STAGE_SEED = 2                  # chỉ cần 2 clip mẫu xếp tay (ở >= 2 bin) trong giai đoạn là học nhanh


def _knn_probs(v, pool, vectors, k, temp, dino_v=None, dino_vectors=None):
    import numpy as np
    M = np.stack([vectors[kk] for kk, _ in pool])
    sims = M @ v
    if dino_v is not None and dino_vectors:
        d_sims = np.array([
            float(dino_vectors[kk] @ dino_v) if kk in dino_vectors else float(sims[j])
            for j, (kk, _) in enumerate(pool)
        ], dtype=sims.dtype)
        sims = 0.65 * sims + 0.35 * d_sims
    idx = np.argsort(-sims)[:k]
    w = np.exp(temp * (sims[idx] - sims[idx].max()))
    sc = {}
    for j, wi in zip(idx, w):
        sc[pool[j][1]] = sc.get(pool[j][1], 0.0) + float(wi)
    tot = sum(sc.values()) or 1.0
    return {b: x / tot for b, x in sc.items()}


def _knn_rank(v, pool, vectors, k, temp, dino_v=None, dino_vectors=None):
    return _top3(list(_knn_probs(v, pool, vectors, k, temp, dino_v=dino_v, dino_vectors=dino_vectors).items()))


def _zero_shot_probs(key, cand_bins, desc, stage_name="", bin_tags=None, synonyms=None,
                     concept_scores=None, concept_sims=None, temp=None):
    import math
    if not cand_bins:
        return {}
    # 2a. Softmax CHỈ trên các bin của giai đoạn hiện tại từ cosine thô (không bị Mừng thọ / Event / Khác cướp điểm)
    if concept_sims and key in concept_sims[1]:
        c_ids, c_table = concept_sims
        c_idx = {cid: idx for idx, cid in enumerate(c_ids)}
        row = c_table[key]
        raw = []
        for b in cand_bins:
            cid = (bin_tags or {}).get(b) or infer_concept(b, stage_name=stage_name, custom_map=synonyms)
            if cid and cid in c_idx and c_idx[cid] < len(row):
                s = float(row[c_idx[cid]])
                if cid == "khac":
                    s -= KHAC_COSINE_PENALTY
                raw.append((b, s))
        if raw:
            t_val = SIGLIP2_TEMP if temp is None else float(temp)
            mx = max(s for _, s in raw)
            exps = [(b, math.exp(t_val * (s - mx))) for b, s in raw]
            tot = sum(x for _, x in exps) or 1.0
            return {b: x / tot for b, x in exps}
    # 2b. Fallback c_scores (bản ai_suggest cũ chưa có c_sims)
    if concept_scores and key in concept_scores[1]:
        c_ids, c_table = concept_scores
        c_idx = {cid: idx for idx, cid in enumerate(c_ids)}
        row = c_table[key]
        sc = []
        for b in cand_bins:
            cid = (bin_tags or {}).get(b) or infer_concept(b, stage_name=stage_name, custom_map=synonyms)
            if cid and cid in c_idx and c_idx[cid] < len(row):
                sc.append((b, float(row[c_idx[cid]])))
        tot = sum(x for _, x in sc)
        if sc and tot > 0:
            return {b: x / tot for b, x in sc}
    # 3. Dự phòng file ai_suggest.json bản rất cũ: khớp trực tiếp hoặc khớp đồng nghĩa theo thẻ cảnh
    if desc and key in desc[1]:
        bins, table = desc
        row = table[key]
        by_name = {b: float(x) for b, x in zip(bins, row)}
        by_cid = {}
        for b, x in zip(bins, row):
            cid0 = infer_concept(b, stage_name=stage_name, custom_map=synonyms)
            if cid0 and float(x) > by_cid.get(cid0, -1.0):
                by_cid[cid0] = float(x)
        sc = []
        for b in cand_bins:
            if b in by_name:
                sc.append((b, by_name[b]))
            else:
                cid = (bin_tags or {}).get(b) or infer_concept(b, stage_name=stage_name, custom_map=synonyms)
                if cid and cid in by_cid:
                    sc.append((b, by_cid[cid]))
        tot = sum(x for _, x in sc)
        if sc and tot > 0:
            return {b: x / tot for b, x in sc}
    return {}


def _match_cand_bin(b_label, cand_bins, stage_name="", bin_tags=None, synonyms=None):
    """Khớp nhãn tay sang bin ứng viên (khớp nguyên văn, khớp bỏ dấu tiếng Việt, hoặc khớp Thẻ cảnh chuẩn duy nhất)."""
    if b_label in cand_bins:
        return b_label
    nb = strip_accents(b_label)
    for cb in cand_bins:
        if strip_accents(cb) == nb and nb:
            return cb
    cid = infer_concept(b_label, stage_name=stage_name, custom_map=synonyms)
    if cid:
        hits = [cb for cb in cand_bins if ((bin_tags or {}).get(cb) or infer_concept(cb, stage_name=stage_name, custom_map=synonyms)) == cid]
        if len(hits) == 1:
            return hits[0]
    return None


def rank_for_clip(key, cand_bins, vectors, labeled, desc, k=KNN_K, temp=KNN_TEMP,
                  stage_name="", bin_tags=None, synonyms=None, concept_scores=None, stage_labeled=None,
                  concept_sims=None, dino_vectors=None):
    """Gợi ý hạng 1-3 cho một clip trong các bin cand_bins (bin của giai đoạn clip đang ở).
    1) Học nhanh theo >=2 clip mẫu ở >=2 bin trong giai đoạn (pha trộn với zero-shot nếu chưa phủ hết bin) hoặc >=20 nhãn tay toàn project.
    2) Điểm theo Thẻ cảnh chuẩn per-stage trên cosine thô (c_sims) hoặc c_scores (bản cũ).
    3) Dự phòng: bảng mô tả cũ (desc)."""
    zs_probs = _zero_shot_probs(
        key, cand_bins, desc, stage_name=stage_name, bin_tags=bin_tags, synonyms=synonyms,
        concept_scores=concept_scores, concept_sims=concept_sims,
    )
    v = vectors.get(key)
    dino_v = dino_vectors.get(key) if dino_vectors else None

    def _blend(knn_p, n_seeded, n_samples):
        if not zs_probs:
            return _top3(list(knn_p.items()))
        w_knn = min(0.75, 0.25 + 0.50 * min(1.0, n_samples / max(1, 3 * len(cand_bins))))
        all_bins = set(knn_p) | set(zs_probs)
        merged = {b: w_knn * knn_p.get(b, 0.0) + (1.0 - w_knn) * zs_probs.get(b, 0.0) for b in all_bins}
        tot = sum(merged.values()) or 1.0
        return _top3([(b, x / tot) for b, x in merged.items()])

    if v is not None:
        # 1a. Học nhanh từ mẫu ngay trong giai đoạn (bắt buộc có ít nhất 2 bin đã có mẫu để tránh dồn 100% vào 1 bin)
        if stage_labeled:
            spool = [(kk, b) for kk, b in stage_labeled.items() if b in cand_bins and kk != key and kk in vectors]
            n_bins_seeded = len({b for _, b in spool})
            if len(spool) >= MIN_STAGE_SEED and n_bins_seeded >= 2:
                kp = _knn_probs(v, spool, vectors, k, temp, dino_v=dino_v, dino_vectors=dino_vectors)
                return "nhan", _blend(kp, n_bins_seeded, len(spool))
        # 1b. Học từ nhãn tay toàn project (>= 20 nhãn), khớp chéo giai đoạn không phân biệt dấu / theo concept duy nhất
        if len(labeled) >= MIN_FEWSHOT_LABELS:
            pool = []
            for kk, b in labeled.items():
                if kk == key or kk not in vectors:
                    continue
                mb = _match_cand_bin(b, cand_bins, stage_name=stage_name, bin_tags=bin_tags, synonyms=synonyms)
                if mb:
                    pool.append((kk, mb))
            n_bins_pooled = len({b for _, b in pool})
            if len(pool) >= MIN_FEWSHOT_IN_STAGE and n_bins_pooled >= 2:
                kp = _knn_probs(v, pool, vectors, k, temp, dino_v=dino_v, dino_vectors=dino_vectors)
                return "nhan", _blend(kp, n_bins_pooled, len(pool))
    if zs_probs:
        return "mo_ta", _top3(list(zs_probs.items()))
    return None, []


def ai_python(cfg_value=None):
    import troly_env
    return troly_env.ai_python(cfg_value)


class AiJob(object):
    """Chạy nhúng + gợi ý bằng venv AI trong tiến trình con (nền). Dừng bằng cờ STOP (làm tiếp được: chạy lại). Không tự chạy gì khác."""

    def __init__(self, project, data_root, python=None):
        self.project, self.root = project, data_root
        self.python = ai_python(python)
        self._proc = None

    def available(self):
        return os.path.isfile(self.python) and (has_siglip2(self.root) or has_siglip(self.root) or os.path.isfile(model_path(self.root)))

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
        log_dir = os.path.join(self.root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        err_path = os.path.join(log_dir, "ai_embed_%s.err.log" % hashlib.sha1(self.project.encode("utf-8")).hexdigest()[:8])
        err_f = open(err_path, "wb")
        try:
            self._proc = troly_proc.mo_an([self.python, "-X", "utf8", os.path.join(APP, "troly_ai.py"), "run", "--project", self.project],
                                          stdout=subprocess.DEVNULL, stderr=err_f, creationflags=flags)
        finally:
            err_f.close()
        return True

    def stop(self, force=False):
        d = embed_dir(self.root, self.project)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "STOP"), "w", encoding="utf-8"):
            pass
        if force and self.running():
            import troly_proc
            troly_proc.kill_tree(self._proc.pid)

    def last_log(self):
        h = hashlib.sha1(self.project.encode("utf-8")).hexdigest()[:8]
        log = os.path.join(self.root, "logs", "ai_embed_%s.log" % h)
        try:
            with open(log, "r", encoding="utf-8") as f:
                lines = f.read().strip().splitlines()
            if lines:
                return lines[-1][9:]
        except OSError:
            pass
        err_log = os.path.join(self.root, "logs", "ai_embed_%s.err.log" % h)
        try:
            with open(err_log, "r", encoding="utf-8", errors="replace") as f:
                el = [ln.strip() for ln in f.read().splitlines() if ln.strip()]
            if el:
                return "LỖI AI: " + el[-1][:180]
        except OSError:
            pass
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
    if a.cmd == "run":                                      # panel gọi: nhúng (SigLIP2 + DINOv2) rồi gợi ý; bị dừng giữa chừng thì không gợi ý
        res["embed"] = run_embed(a.project, dr, pr)
        if not os.path.isfile(os.path.join(embed_dir(dr, a.project), "STOP")):
            res["dino"] = run_embed_dino(a.project, dr, pr)
        if not os.path.isfile(os.path.join(embed_dir(dr, a.project), "STOP")):
            res["suggest"] = run_suggest(a.project, dr, pr)
        print(json.dumps(res, ensure_ascii=False))
        return 0
    if a.cmd in ("embed", "all"):
        res["embed"] = run_embed(a.project, dr, pr)
        res["dino"] = run_embed_dino(a.project, dr, pr)
    if a.cmd in ("suggest", "all"):
        res["suggest"] = run_suggest(a.project, dr, pr)
    if a.cmd in ("review", "all"):
        res["review"] = build_review(a.project, dr)
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
