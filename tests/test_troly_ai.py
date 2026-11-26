"""Bước 6 AI (ADR-0020): phần không cần torch - mô tả bin, ghép thumbnail với proxy, đo độ khớp, trang báo cáo, an toàn (chỉ gợi ý)."""
import json
import os
import sys
import tempfile
import unittest

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APP)
import troly_ai as ai          # noqa: E402
import troly_thumbs as tt      # noqa: E402


class AiPure(unittest.TestCase):
    def test_mo_ta_moi_bin_co_it_nhat_2_cau_tieng_anh(self):
        for b in ("Decor", "Beauty cô dâu", "Gia đình cô dâu", "Phỏng vấn", "Khác", "Cô dâu chú rể", "Sân khấu", "Khách"):
            p = ai.prompts_for(b)
            self.assertGreaterEqual(len(p), 2, b)
            self.assertTrue(all(isinstance(x, str) and x.isascii() for x in p), b)
        lạ = ai.prompts_for("Lạ hoắc")                           # bin lạ: câu chung có tên bin
        self.assertEqual(len(lạ), 2)
        self.assertIn("Lạ hoắc", lạ[0])

    def test_bin_ghep_dung_quy_tac(self):
        self.assertIn("groom", ai.prompts_for("Chú rể")[0])
        self.assertIn("bride and groom", ai.prompts_for("Cô dâu chú rể")[0])      # cặp đôi không rơi vào "chú rể"
        self.assertIn("family", ai.prompts_for("Gia đình cô dâu")[0])

    def test_ghep_thumbnail_voi_proxy_va_dem_thumbnail_thua(self):
        with tempfile.TemporaryDirectory() as t:
            proxy_root, dr, proj = os.path.join(t, "px"), os.path.join(t, "data"), "P1"
            pdir = os.path.join(proxy_root, proj, "ProxyMedia", "x", proj, "01_footage")
            os.makedirs(pdir)
            os.makedirs(os.path.join(dr, "cache", "troly_thumbs", proj))
            for n in ("A1", "A2"):
                open(os.path.join(pdir, n + ".mov"), "wb").write(b"x" * 10)
            f1 = os.path.join(pdir, "A1.mov")
            k = tt.cache_key(f1, None, tt.DEFAULT_POS, ai.THUMB_WIDTH)
            open(os.path.join(dr, "cache", "troly_thumbs", proj, k + ".jpg"), "wb").write(b"j")
            open(os.path.join(dr, "cache", "troly_thumbs", proj, "deadbeef.jpg"), "wb").write(b"j")   # thumbnail thừa
            clips, orphan = ai.match_thumbs(proj, dr, proxy_root)
            self.assertEqual(len(clips), 2)                      # còn proxy: thumbnail thừa không thành clip
            self.assertEqual(orphan, 1)
            got = {c["name"]: c["thumb"] for c in clips}
            self.assertTrue(got["A1"].endswith(k + ".jpg"))
            self.assertIsNone(got["A2"])                         # chưa có thumbnail: bỏ qua và đếm
            self.assertEqual(clips[0]["rel"], "01_footage/A1.mov")

    def test_nhan_doc_theo_ten_khong_phan_biet_duoi_file(self):
        plan = {"labels": {"01_footage/DG1.MP4": {"bin": "Decor"}, "x/y.MP4": "Khác", "z.MP4": {"bin": None}}}
        m = ai.labels_by_stem(plan)
        self.assertEqual(m[("01_footage", "dg1")], "Decor")
        self.assertEqual(m[("x", "y")], "Khác")
        self.assertEqual(len(m), 2)

    def test_do_do_khop_can_du_20_nhan(self):
        bins = ["A", "B"]
        mk = lambda lab, top: {"label": lab, "top": [{"bin": b, "score": .5} for b in top]}      # noqa: E731
        few = [mk("A", ["A", "B"])] * 19
        self.assertIn("chưa đủ nhãn", ai.evaluate(few, bins)["note"])
        enough = [mk("A", ["A", "B"])] * 15 + [mk("B", ["A", "B"])] * 5
        ev = ai.evaluate(enough, bins)
        self.assertEqual(ev["labeled"], 20)
        self.assertEqual(ev["top1"], 0.75)
        self.assertEqual(ev["top3"], 1.0)
        self.assertEqual(ev["per_bin"]["B"]["top1_recall"], 0.0)

    def test_trang_bao_cao_tinh_khong_chen_chu_la(self):
        with tempfile.TemporaryDirectory() as t:
            d = os.path.join(t, "troly", "ai_suggest")
            os.makedirs(d)
            thumb = os.path.join(t, "cache", "troly_thumbs", "P", "a b.jpg")
            s = {"project_tag": "P", "model": "m", "bins": ["Decor", "<b>"], "prompts": {"Decor": ["x"]}, "count": 1,
                 "items": [{"clip": "c/A", "name": "A<1>", "thumb": thumb, "label": "Decor",
                            "top": [{"bin": "<b>", "score": .9}, {"bin": "Decor", "score": .1}]}],
                 "eval": {"labeled": 0, "note": "chưa đủ nhãn để đo"}}
            json.dump(s, open(os.path.join(d, "P.json"), "w", encoding="utf-8"))
            out = ai.build_review("P", t)
            h = open(out, encoding="utf-8").read()
            self.assertIn("THAM KHẢO", h)
            self.assertNotIn("<b></b>", h)
            self.assertIn("&lt;b&gt;", h)                         # tên bin bị thoát ký tự
            self.assertIn("a%20b.jpg", h)                         # đường dẫn ảnh mã hóa
            self.assertTrue(out.endswith(os.path.join("ai_review", "P", "index.html")))


class AiSafe(unittest.TestCase):
    def test_chi_goi_y_khong_ghi_davinci_hay_ke_hoach(self):
        src = open(os.path.join(APP, "troly_ai.py"), encoding="utf-8").read()
        for bad in ("troly_resolve", "SetMarkInOut", "MoveClips", "AddSubFolder", "CreateTimeline", "save_plan", "os.remove(p)",
                    "shutil.rmtree", "requests", "urllib.request"):
            self.assertNotIn(bad, src, bad)
        self.assertIn("ai_suggest", src)                          # kết quả vào file riêng, không vào kế hoạch
        self.assertIn("load_plan", src)                           # chỉ ĐỌC kế hoạch


class AiFixesRegression(unittest.TestCase):
    def test_load_dino_vectors_recovers_legacy_object_dtype(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as t:
            d = ai.embed_dir(t, "P_OBJ")
            os.makedirs(d, exist_ok=True)
            npz = os.path.join(d, "dino_vectors.npz")
            np.savez(npz, keys=np.array(["A1|01", "A2|01"], dtype=object),
                     vecs=np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32))
            got = ai.load_dino_vectors(t, "P_OBJ")
            self.assertEqual(len(got), 2)
            self.assertIn(("01", "a1"), got)

    def test_ai_data_isolates_corrupt_dino_file_without_wiping_siglip(self):
        import numpy as np
        import troly_api as ta
        with tempfile.TemporaryDirectory() as t:
            d = ai.embed_dir(t, "P_ISO")
            os.makedirs(d, exist_ok=True)
            np.savez(os.path.join(d, "vectors.npz"), keys=np.array(["A1|01"]),
                     vecs=np.array([[1.0, 0.0]], dtype=np.float32))
            with open(os.path.join(d, "dino_vectors.npz"), "wb") as f:
                f.write(b"not a valid npz")
            sd = os.path.join(t, "troly", "ai_suggest")
            os.makedirs(sd, exist_ok=True)
            with open(os.path.join(sd, "P_ISO.json"), "w", encoding="utf-8") as f:
                json.dump({"bins": ["Decor", "Khác"], "items": [{"clip": "01/A1.MP4", "scores": [0.9, 0.1]}]}, f)
            api = ta.TrolyApi("P_ISO", t, emit=lambda *a: None, start_worker=False)
            vec, desc = api._ai_data()
            self.assertIn(("01", "a1"), vec)
            self.assertIsNotNone(desc)
            self.assertEqual(api._ai_cache["dino"], {})

    def test_wedding_concepts_mapping_and_per_stage_softmax(self):
        self.assertEqual(ai.infer_concept("Không gian · Decor", stage_name="Lễ nhà hàng"), "decor")
        self.assertEqual(ai.infer_concept("Không gian · Decor", stage_name="Không gian · Setup Event"), "ev_khong_gian")
        self.assertEqual(ai.infer_concept("get ready", stage_name="Lễ nhà hàng"), "get_ready")
        self.assertEqual(ai.infer_concept("Chụp hình", stage_name="Lễ nhà hàng"), "chup_hinh")
        self.assertEqual(ai.infer_concept("Nhà trai đến", stage_name="Rước dâu"), "nha_trai_den")
        c_ids = [c["id"] for c in ai.CONCEPTS]
        row = [0.01] * len(c_ids)
        row[c_ids.index("chuc_tho")] = 0.90     # thẻ ngoài giai đoạn không được phép cướp điểm
        row[c_ids.index("decor")] = 0.12
        row[c_ids.index("chu_re")] = 0.04
        row[c_ids.index("khac")] = 0.13         # 'khac' bị trừ KHAC_COSINE_PENALTY nên thua decor (0.12 > 0.13 - 0.045)
        src, top = ai.rank_for_clip(("01", "a1"), ["Decor", "Chú rể", "Khác"], {}, {}, None,
                                    stage_name="Chuẩn bị nhà trai", concept_sims=(c_ids, {("01", "a1"): row}))
        self.assertEqual(src, "mo_ta")
        self.assertEqual(top[0]["bin"], "Decor")

    def test_single_bin_seed_does_not_collapse_to_100_percent(self):
        import numpy as np
        v1 = np.array([1.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 1.0], dtype=np.float32)
        vecs = {("01", "d1"): v1, ("01", "d2"): v1, ("01", "d3"): v1, ("01", "q"): v2}
        desc = (["Decor", "Chú rể"], {("01", "q"): [0.1, 0.9]})
        # 3 clip mẫu đều chỉ nằm trong 1 bin 'Decor' -> chưa đủ 2 bin khác nhau -> không được ép toàn bộ giai đoạn thành Decor
        stage_lab = {("01", "d1"): "Decor", ("01", "d2"): "Decor", ("01", "d3"): "Decor"}
        src, top = ai.rank_for_clip(("01", "q"), ["Decor", "Chú rể"], vecs, stage_lab, desc, stage_labeled=stage_lab)
        self.assertEqual(src, "mo_ta")
        self.assertEqual(top[0]["bin"], "Chú rể")


if __name__ == "__main__":
    unittest.main()
