"""Kiểm thử Phương án B + Ý 3 + Menu sổ ra Page 1:
- Bóc dấu tiếng Việt + viết tắt + ngữ cảnh cụm sự kiện mẹ (Nghi lễ tại gia vs Nghi lễ sân khấu vs Lễ nhà thờ).
- Thẻ cảnh chuẩn (ai_tag) + đổi tên bin cập nhật điểm AI tức thì qua c_scores.
- Từ nhớ riêng của editor (ai_synonyms.json) tồn tại bền sau khi xóa cache.
- Học nhanh từ 2-3 clip mẫu ngay trong giai đoạn (Chơi game, Múa lân...) không cần đủ 20 nhãn toàn project.
- Giao diện Page 1 menu sổ ra gõ chữ cái đầu & Page 2 menu chuột phải AI hiểu là.
"""
import datetime
import os
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
sys.path.insert(0, APP)

import troly_ai as ai  # noqa: E402
import troly_api as ta  # noqa: E402
import troly_core as tc  # noqa: E402


class TestAiConceptsAndSynonyms(unittest.TestCase):
    def test_strip_accents_and_abbreviations(self):
        self.assertEqual(ai.strip_accents("02_Làm lễ tại gia"), "lam le tai gia")
        self.assertEqual(ai.infer_concept("cdcr"), "cap_doi")
        self.assertEqual(ai.infer_concept("01_PV_Khach"), "phong_van")
        self.assertEqual(ai.infer_concept("chao ban"), "chao_ban")
        self.assertEqual(ai.infer_concept("Choi Game"), "choi_game")
        self.assertEqual(ai.infer_concept("Mua lan"), "mua_lan")
        self.assertEqual(ai.infer_concept("broll decor"), "decor")

    def test_stage_context_splits_ceremony(self):
        self.assertEqual(ai.infer_concept("Nghi lễ", stage_name="Đón về nhà trai"), "nghi_le_tai_gia")
        self.assertEqual(ai.infer_concept("nghi le", stage_name="Tiệc Nhà hàng tối"), "nghi_le_san_khau")
        self.assertEqual(ai.infer_concept("Làm lễ", stage_name="Lễ nhà thờ"), "le_nha_tho")

    def test_custom_synonym_persists_across_cache_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            api = ta.TrolyApi("P_SYN", tmp, emit=lambda *a: None, start_worker=False)
            api._plan["stages"] = [{"name": "Nhà trai", "start": 0.0, "end": 60.0, "color": "#4FC1A6",
                                    "bins": ["Phan chinh", "Khác"]}]
            st = api.ai_set_bin_concept(0, "Phan chinh", "nghi_le_tai_gia")
            self.assertNotIn("error", st)
            t0 = st["stages"][0]["ai_tags"]["Phan chinh"]
            self.assertEqual(t0["tag"], "nghi_le_tai_gia")
            self.assertTrue(t0["custom"])
            # Xóa cache không được làm mất ai_synonyms.json
            tdir = os.path.join(tmp, "cache", "troly_thumbs", tc._safe("P_SYN"))
            os.makedirs(tdir, exist_ok=True)
            with open(os.path.join(tdir, "a.jpg"), "wb") as f:
                f.write(b"123")
            api.cache_clear(tc._safe("P_SYN"))
            syn = ai.load_synonyms(tmp)
            self.assertEqual(ai.infer_concept("phan chinh", stage_name="Nhà trai", custom_map=syn), "nghi_le_tai_gia")
            self.assertIn("Phan chinh", syn["custom_names"])

    def test_rename_keeps_concept_and_scores_instant(self):
        with tempfile.TemporaryDirectory() as tmp:
            api = ta.TrolyApi("P_REN", tmp, emit=lambda *a: None, start_worker=False)
            c1 = tc.Clip(uid="u1", rel="01/A001.MP4", name="A001.MP4",
                         t_start=datetime.datetime(2026, 11, 21, 9, 0, 0), dur=10.0, fps=25.0, frames=250)
            api._clips = [c1]
            api._by_uid = {"u1": c1}
            api._day0 = datetime.datetime(2026, 11, 21, 0, 0, 0)
            api._plan["stages"] = [{"name": "Đón về nhà trai", "start": 530.0, "end": 560.0, "color": "#4FC1A6",
                                    "bins": ["Nghi lễ", "Decor", "Khác"]}]
            api._assign = {"u1": 0}
            c_ids = [c["id"] for c in ai.CONCEPTS]
            row = [0.01] * len(c_ids)
            row[c_ids.index("nghi_le_tai_gia")] = 0.85
            row[c_ids.index("decor")] = 0.05
            k1 = ai.ck(c1.rel)
            api._ai_cache = {"sig": (0, 0), "vec": {k1: np.array([1.0, 0.0], dtype=np.float32)},
                             "desc": None, "c_scores": (c_ids, {k1: row})}
            # Đổi tên bin 'Nghi lễ' -> 'Lam le nha chu re' (không dấu) -> AI vẫn chấm đúng tức thì 0 giây!
            r = api.rename("bin", 0, "Nghi lễ", "Lam le nha chu re")
            self.assertTrue(r.get("ok"))
            res = api.ai_for(["u1"])
            self.assertIn("u1", res)
            self.assertEqual(res["u1"]["top"][0]["bin"], "Lam le nha chu re")

    def test_fast_stage_seed_learning_with_two_samples(self):
        """Ý 3: Chỉ cần 2 clip mẫu xếp tay trong giai đoạn (Chơi game / Múa lân) là học được ngay."""
        v_game = np.array([1.0, 0.0], dtype=np.float32)
        v_lan = np.array([0.0, 1.0], dtype=np.float32)
        v_test = np.array([0.95, 0.05], dtype=np.float32)
        v_test = v_test / np.linalg.norm(v_test)
        vecs = {("01", "g1"): v_game, ("01", "l1"): v_lan, ("01", "t1"): v_test}
        stage_lab = {("01", "g1"): "Chơi game", ("01", "l1"): "Múa lân"}
        src, top = ai.rank_for_clip(("01", "t1"), ["Chơi game", "Múa lân", "Khác"], vecs, stage_lab, None,
                                    stage_labeled=stage_lab)
        self.assertEqual(src, "nhan")
        self.assertEqual(top[0]["bin"], "Chơi game")

    def test_frontend_page1_dropdown_and_page2_pool_ctx_wiring(self):
        with open(os.path.join(APP, "troly_web", "app.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("function vnNorm(", js)
        self.assertIn("function p1DdOpen(", js)
        self.assertIn("ai_set_bin_concept", js)
        self.assertIn('data-act="bin-dd"', js)


if __name__ == "__main__":
    unittest.main()
