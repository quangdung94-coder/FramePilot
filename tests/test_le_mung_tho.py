"""Unit tests for Lễ mừng thọ templates, In/Out rules, AI concepts (Cụ ông / Cụ bà), and speech phrases."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

import troly_ai as ai  # noqa: E402
import troly_core as tc  # noqa: E402


class TestLeMungTho(unittest.TestCase):
    def test_builtin_templates_have_mung_tho_without_cdcr(self):
        for tpl_name in ("Lễ mừng thọ (đầy đủ)", "Lễ mừng thọ (chỉ tiệc)"):
            self.assertIn(tpl_name, tc.BUILTIN_TEMPLATES)
            stages = tc.BUILTIN_TEMPLATES[tpl_name]
            self.assertGreaterEqual(len(stages), 3)
            all_bins = [b for _st, bins in stages for b in bins]
            self.assertIn("Cụ ông cụ bà", all_bins)
            for b in all_bins:
                self.assertNotIn("cô dâu", b.lower())
                self.assertNotIn("chú rể", b.lower())
            # Every stage has an event mapping
            for st_name, _bins in stages:
                self.assertNotEqual(tc.event_of(tpl_name, st_name), tc.DEFAULT_EVENT)

    def test_builtin_rules_for_mung_tho_bins(self):
        txt, mn, mx, _w = tc.builtin_rule("Cụ ông cụ bà")
        self.assertIn("Cụ ông bà", txt)
        self.assertEqual((mn, mx), (2.5, 4.0))

        txt2, mn2, mx2, _w2 = tc.builtin_rule("Chúc thọ · Phát biểu")
        self.assertEqual((mn2, mx2), (4.0, 8.5))

        txt3, mn3, mx3, _w3 = tc.builtin_rule("Trao quà · Mừng thọ")
        self.assertEqual((mn3, mx3), (3.0, 5.0))

    def test_ai_concepts_infer_cu_ong_cu_ba(self):
        self.assertEqual(ai.infer_concept("Cụ ông cụ bà", "Chuẩn bị"), "cu_ong_cu_ba")
        self.assertEqual(ai.infer_concept("Cụ ông", "Chuẩn bị"), "cu_ong")
        self.assertEqual(ai.infer_concept("Cụ bà", "Chuẩn bị"), "cu_ba")
        self.assertEqual(ai.infer_concept("Trao quà · Mừng thọ", "Nghi lễ mừng thọ"), "chuc_tho")
        self.assertEqual(ai.infer_concept("Chúc thọ · Phát biểu", "Nghi lễ mừng thọ"), "phat_bieu")
        self.assertEqual(ai.infer_concept("Nghi lễ", "Nghi lễ mừng thọ"), "nghi_le_san_khau")
        self.assertEqual(ai.infer_concept("Văn nghệ", "Văn nghệ · Tiệc"), "choi_game")

    def test_wedding_phrases_has_mung_tho_group(self):
        with open(os.path.join(APP, "wedding_phrases.json"), encoding="utf-8") as f:
            data = json.load(f)
        mt = (data.get("groups") or {}).get("mung_tho") or []
        self.assertIn("mừng thọ", mt)
        self.assertIn("cụ ông", mt)
        self.assertIn("cụ bà", mt)

    def test_short_tpl_name_keeps_mung_tho_label(self):
        with open(os.path.join(APP, "troly_web", "app.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("/mừng thọ/i.test(t) ? t", js)


if __name__ == "__main__":
    unittest.main()
