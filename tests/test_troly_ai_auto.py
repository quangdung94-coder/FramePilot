"""Việc 3 (ADR-0023): AI tự xếp khi hạng 1 >= ngưỡng. Dấu riêng by="ai_auto", không tính vào dữ liệu AI học, Hoàn tác, ngưỡng chỉnh được và chỉ lưu
khi anh chỉnh, không đụng DaVinci. Dữ liệu giả, tên ví dụ LV_Ten."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, HERE)
import test_troly as T                # noqa: E402
import troly_ai as ai                 # noqa: E402
import troly_api as ta                # noqa: E402
import troly_core as tc               # noqa: E402


def jobs(api):
    w = api._worker
    while not w.jobs.empty():
        j, a = w.jobs.get()
        getattr(w, "do_" + j)(a)
    api._drain()


class Auto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.name = "2026.10.17.LV_Ten"
        mk = lambda uid, hh: T.FItem(uid, T.props("DG%s.MP4" % uid, "Sat Oct 17 2026 %02d:00:00" % hh, "Sat Oct 17 %02d:00:20 2026" % hh, 1000, Type="Video + Audio"))  # noqa: E731
        sel = T.FFolder("01_SELECTED", [mk("a", 8), mk("b", 9), mk("c", 10), mk("d", 11)])
        foot = T.FFolder("01_footage")
        foot.subs.append(sel)
        root = T.FFolder("Master")
        root.subs.append(foot)
        self.pool = T.FPool(root)
        self.api = ta.TrolyApi(self.name, self.tmp, resolve_factory=lambda: T.FResolve(T.FProject(self.name, self.pool)), start_worker=False)
        self.api._worker.connect()
        self.api.init()
        jobs(self.api)
        self.api.load("Master/01_footage/01_SELECTED")
        jobs(self.api)
        self.api._plan["stages"] = [{"name": "S1", "start": 0.0, "end": 100000.0, "color": "#fff", "bins": ["Decor", "Khác", "Nghi"]}]
        self.api._plan["offsets"] = {}
        self.api.state()
        d = os.path.join(self.tmp, "troly", "ai_suggest")
        os.makedirs(d)
        # điểm theo mô tả (3 bin): a Decor 0.9; b Decor 0.5 (đúng ngưỡng); c Khác 0.55; d hạng 1 chỉ 0.4 (dưới ngưỡng)
        items = [{"clip": "01_footage/DGa.mov", "scores": [0.9, 0.05, 0.05]}, {"clip": "01_footage/DGb.mov", "scores": [0.5, 0.3, 0.2]},
                 {"clip": "01_footage/DGc.mov", "scores": [0.2, 0.55, 0.25]}, {"clip": "01_footage/DGd.mov", "scores": [0.4, 0.35, 0.25]}]
        with open(os.path.join(d, tc._safe(self.name) + ".json"), "w", encoding="utf-8") as f:
            json.dump({"bins": ["Decor", "Khác", "Nghi"], "items": items}, f)

    def tearDown(self):
        self.api._thumbs.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def uid(self, n):
        return next(c["uid"] for c in self.api.state()["clips"] if c["name"] == n)

    def labels(self):
        return {rel.split("/")[-1]: (v["bin"], v["by"]) for rel, v in self.api._plan["labels"].items()}

    def test_mac_dinh_50_phan_tram_va_khong_co_khoa_trong_ke_hoach(self):
        info = self.api.ai_auto_info()
        self.assertEqual((info["threshold"], info["after_run"], info["batches"]), (0.5, False, 0))
        self.assertNotIn("ai_auto", self.api._plan)

    def test_chi_xep_clip_tu_nguong_tro_len_voi_dau_rieng(self):
        st = self.api.ai_auto_run()
        self.assertEqual((st["ai_auto"]["n"], st["ai_auto"]["below"]), (3, 1))               # a 0.9, b 0.5, c 0.55; d chỉ 0.4 nên chờ anh duyệt
        lb = self.labels()
        self.assertEqual(lb["DGa.MP4"], ("Decor", "ai_auto"))
        self.assertEqual(lb["DGb.MP4"], ("Decor", "ai_auto"))                                # đúng ngưỡng 50% thì xếp
        self.assertEqual(lb["DGc.MP4"], ("Khác", "ai_auto"))

    def test_ngưỡng_cao_hon_xep_it_hon_va_sai_bi_chan(self):
        st = self.api.ai_auto_run(threshold=80)
        self.assertEqual(st["ai_auto"]["n"], 1)
        self.assertEqual(list(self.labels()), ["DGa.MP4"])
        for bad in ("abc", 0, 101, -5, float("nan"), None):
            r = self.api.ai_auto_set(bad) if bad is not None else None
            if bad is not None:
                self.assertIn("error", r, bad)
        self.assertIn("error", self.api.ai_auto_run(threshold=0))

    def test_ngưỡng_chi_luu_khi_anh_chinh(self):
        r = self.api.ai_auto_set(65)
        self.assertEqual(r["threshold"], 0.65)
        self.assertEqual(self.api._plan["ai_auto"]["threshold"], 0.65)
        self.assertEqual(self.api.ai_auto_run()["ai_auto"]["threshold"], 0.65)               # lần chạy sau dùng ngưỡng đã chỉnh
        self.assertTrue(self.api.ai_auto_set(None, True)["after_run"])

    def test_khong_dung_clip_da_xep_tay_hoac_da_bo_qua(self):
        self.api.label([self.uid("DGa.MP4")], 0, "Khác")                                    # anh xếp tay: AI không đè
        self.api.ai_skip([self.uid("DGb.MP4")])
        st = self.api.ai_auto_run()
        self.assertEqual(st["ai_auto"]["skipped"], 1)
        lb = self.labels()
        self.assertEqual(lb["DGa.MP4"], ("Khác", "nguoi"))
        self.assertNotIn("DGb.MP4", lb)

    def test_nhan_ai_xep_khong_tinh_vao_du_lieu_ai_hoc(self):
        self.api.ai_auto_run()
        self.assertEqual(self.api._ai_labeled(), {})                                          # kNN/đếm nhãn không thấy nhãn AI xếp
        self.assertEqual(self.api.ai_info()["n_labeled"], 0)
        self.api.label([self.uid("DGd.MP4")], 0, "Decor")                                    # nhãn của anh thì tính
        self.assertEqual(list(self.api._ai_labeled().values()), ["Decor"])
        self.api.ai_accept([[self.uid("DGa.MP4"), "Decor"]])                                  # Nhận thủ công: anh đã duyệt -> tính (như ADR-0022)
        self.assertEqual(len(self.api._ai_labeled()), 2)

    def test_cong_cu_do_va_danh_gia_cung_bo_nhan_ai_xep(self):
        import ai_cross
        plan = {"stages": [{"name": "S1", "bins": ["Decor"]}], "labels": {
            "01_footage/DGa.MP4": {"bin": "Decor", "stage": "S1", "by": "nguoi"}, "01_footage/DGb.MP4": {"bin": "Decor", "stage": "S1", "by": "ai_auto"}}}
        vec = {ai.ck("01_footage/DGa.MP4"): 1, ai.ck("01_footage/DGb.MP4"): 1}
        self.assertEqual([r["k"] for r in ai_cross.labeled_rows(plan, vec)], [ai.ck("01_footage/DGa.MP4")])
        self.assertEqual(list(ai.labels_by_stem(plan)), [("01_footage", "dga")])

    def test_trang_thai_co_dau_ai_xep_de_giao_dien_hien(self):
        self.api.ai_auto_run()
        by = {c["name"]: c["label_by"] for c in self.api.state()["clips"]}
        self.assertEqual((by["DGa.MP4"], by["DGd.MP4"]), ("ai_auto", None))
        self.api.label([self.uid("DGa.MP4")], 0, "Decor")                                    # anh xếp lại tay -> mất dấu AI xếp
        self.assertEqual({c["name"]: c["label_by"] for c in self.api.state()["clips"]}["DGa.MP4"], "nguoi")

    def test_hoan_tac_bo_dung_nhan_ai_va_giu_nhan_anh_da_doi(self):
        self.api.ai_auto_run()
        self.api.label([self.uid("DGb.MP4")], 0, "Khác")                                    # anh đổi tay một clip sau khi AI xếp
        st = self.api.ai_auto_undo()
        self.assertEqual(st["ai_auto_undo"], {"undone": 2, "kept": 1})
        self.assertEqual(self.labels(), {"DGb.MP4": ("Khác", "nguoi")})
        self.assertEqual(self.api.ai_auto_info()["batches"], 0)
        self.assertIn("error", self.api.ai_auto_undo())                                      # hết lần để hoàn tác

    def test_hoan_tac_tung_lan_va_gioi_han_so_lan_giu(self):
        self.api.ai_auto_run(threshold=80)                                                   # lần 1: a
        self.api.ai_auto_run(threshold=50)                                                   # lần 2: b, c, d
        self.assertEqual(self.api.ai_auto_info()["batches"], 2)
        self.api.ai_auto_undo()
        self.assertEqual(list(self.labels()), ["DGa.MP4"])                                    # chỉ lần 2 bị bỏ
        self.api._plan["ai_auto"]["batches"] = [{"at": "x", "threshold": 0.5, "items": []}] * 30
        self.api.label([self.uid("DGa.MP4")], 0, None)
        self.api.ai_auto_run()
        self.assertLessEqual(len(self.api._plan["ai_auto"]["batches"]), ta.AI_AUTO_KEEP)

    def test_chua_chay_ai_thi_bao_loi_va_khong_dung_davinci(self):
        os.remove(os.path.join(self.tmp, "troly", "ai_suggest", tc._safe(self.name) + ".json"))
        self.assertIn("error", self.api.ai_auto_run())
        self.api.ai_auto_set(70)
        self.assertTrue(self.api._worker.jobs.empty())
        self.assertEqual(self.api._plan.get("moves", []), [])

    def test_het_clip_chua_xep_thi_xep_0_clip_khong_bao_chua_chay_ai(self):
        self.api.label([c.uid for c in self.api._clips], 0, "Decor")                         # đã xếp hết
        st = self.api.ai_auto_run()
        self.assertNotIn("error", st)
        self.assertEqual(st["ai_auto"]["n"], 0)
        self.assertEqual(self.api.ai_auto_info()["batches"], 0)                              # 0 clip thì không ghi lần Hoàn tác rỗng

    # ---- Đêm #1: nút Tự phân loại + kéo ngưỡng áp ngay (ai_auto_apply, ai_group_scores) ----
    def test_diem_nhom_cho_bieu_do_chi_doc_va_chi_clip_chua_xep_hoac_ai_xep(self):
        sc = self.api.ai_group_scores([c.uid for c in self.api._clips])
        self.assertEqual({round(v["score"], 2) for v in sc.values()}, {0.9, 0.5, 0.55, 0.4})
        self.api.label([self.uid("DGa.MP4")], 0, "Khác")                                    # xếp tay: không còn trong biểu đồ
        sc = self.api.ai_group_scores([c.uid for c in self.api._clips])
        self.assertNotIn(self.uid("DGa.MP4"), sc)
        self.assertEqual(len(sc), 3)

    def test_doi_nguong_so_tu_xep_va_cho_duyet_doi_dung_khong_goi_ai_lai(self):
        uids = [c.uid for c in self.api._clips]
        st = self.api.ai_auto_apply(50, uids)
        self.assertEqual((st["ai_auto"]["n"], st["ai_auto"]["below"]), (3, 1))
        st = self.api.ai_auto_apply(80, uids)                                                # kéo lên: b, c trả về chờ duyệt, không chạy lại AI
        self.assertEqual((st["ai_auto"]["n"], st["ai_auto"]["released"], st["ai_auto"]["below"]), (0, 2, 3))
        self.assertEqual(list(self.labels()), ["DGa.MP4"])
        st = self.api.ai_auto_apply(40, uids)                                                # kéo xuống: tự xếp thêm cả d
        self.assertEqual((st["ai_auto"]["n"], st["ai_auto"]["released"], st["ai_auto"]["below"]), (3, 0, 0))
        self.assertEqual(len(self.labels()), 4)
        self.assertEqual(self.api.ai_auto_info()["threshold"], 0.4)                          # ngưỡng được nhớ
        self.assertIsNone(self.api._ai_job)                                                  # chưa hề tạo/chạy tiến trình AI
        self.assertTrue(self.api._worker.jobs.empty())

    def test_tu_phan_loai_chi_gan_nhan_khong_chuyen_clip_trong_davinci(self):
        self.api.ai_auto_apply(50, [c.uid for c in self.api._clips])
        self.assertTrue(self.api._worker.jobs.empty())                                       # không có việc nào gửi sang luồng DaVinci
        self.assertEqual(self.api._plan.get("moves", []), [])
        self.assertTrue(all(v == "ai_auto" for _b, v in self.labels().values()))

    def test_chi_dung_clip_trong_nhom_va_khong_dung_nhan_tay(self):
        a, b = self.uid("DGa.MP4"), self.uid("DGb.MP4")
        self.api.label([self.uid("DGc.MP4")], 0, "Decor")                                    # nhãn tay của người dựng
        self.api.ai_auto_apply(50, [a, b])                                                   # chỉ nhóm a, b
        self.assertEqual(sorted(self.labels()), ["DGa.MP4", "DGb.MP4", "DGc.MP4"])
        self.assertEqual(self.labels()["DGc.MP4"], ("Decor", "nguoi"))
        self.api.ai_auto_apply(99, [a, b, self.uid("DGc.MP4")])                              # ngưỡng cao: chỉ gỡ nhãn AI, nhãn tay còn nguyên
        self.assertEqual(list(self.labels()), ["DGc.MP4"])
        self.assertEqual(self.labels()["DGc.MP4"], ("Decor", "nguoi"))

    def test_ap_dung_sai_ngưỡng_hoac_chua_chay_ai_thi_bao_loi_khong_ghi(self):
        for bad in (0, 101, "abc"):
            self.assertIn("error", self.api.ai_auto_apply(bad, [c.uid for c in self.api._clips]), bad)
        self.assertEqual(self.labels(), {})
        os.remove(os.path.join(self.tmp, "troly", "ai_suggest", tc._safe(self.name) + ".json"))
        self.assertIn("error", self.api.ai_auto_apply(50, [c.uid for c in self.api._clips]))

    def test_ap_dung_tung_lan_hoan_tac_duoc(self):
        uids = [c.uid for c in self.api._clips]
        self.api.ai_auto_apply(80, uids)
        self.api.ai_auto_apply(50, uids)
        self.assertEqual(self.api.ai_auto_info()["batches"], 2)
        self.api.ai_auto_undo()
        self.assertEqual(list(self.labels()), ["DGa.MP4"])

    def test_nhan_ai_xep_vao_duoc_ke_hoach_ap_dung_nhu_nhan_thuong(self):
        self.api.ai_auto_run()
        tgt = {c.uid: tc.target_folder(self.api._assign.get(c.uid), tc.label_of(self.api._plan, c), self.api._stages, None) for c in self.api._clips}
        self.assertEqual(tgt[self.uid("DGa.MP4")], ["01_S1", "Decor"])                      # chỉ khi anh bấm Áp dụng mới chuyển bin trong DaVinci


class Web(unittest.TestCase):
    def setUp(self):
        web = os.path.join(HERE, "..", "app", "troly_web")
        self.js = open(os.path.join(web, "ai.js"), encoding="utf-8").read()
        self.app = open(os.path.join(web, "app.js"), encoding="utf-8").read()
        self.html = open(os.path.join(web, "index.html"), encoding="utf-8").read()

    def test_phan_tu_dau_rieng_va_chu_dung_chuc_nang(self):
        for i in ("aiThr", "aiThrR", "aiRun", "aiAutoUndo", "aiAutoAfter", "aiAuto", "aiHist", "aiCntOk", "aiCntWait"):
            self.assertEqual(self.html.count('id="%s"' % i), 1, i)
        self.assertIn("AI xếp · ", self.app)                                                   # dấu riêng trên thẻ
        self.assertIn('c.label_by === "ai_auto"', self.app)
        for fn in ("ai_auto_run", "ai_auto_undo", "ai_auto_set", "ai_auto_info", "ai_auto_apply", "ai_group_scores"):
            self.assertIn("api()." + fn, self.js, fn)
        self.assertIn('value="50"', self.html)                                                 # ngưỡng mặc định 50
        self.assertIn("Tự xếp luôn sau khi AI chạy xong", self.html)

    def test_giao_dien_khong_con_hai_nut_cu_va_khong_co_nhan_demo(self):
        h, js = self.html, self.js
        for bad in ("Chạy lại AI", "Gợi ý cho cả nhóm", 'id="aiAutoRun"', "MỚI ·"):
            self.assertNotIn(bad, h + js, bad)
        self.assertIn("Tự phân loại · ", js)
        self.assertIn("api().ai_auto_apply(", js)
        thr = js[js.index("function aiThrSet"):js.index('$("aiAutoUndo").addEventListener')]
        self.assertNotIn("ai_run", thr)                                                      # kéo ngưỡng không gọi AI chạy lại
        self.assertIn("aiHistPaint()", thr)

    def test_moi_id_js_goi_bang_dollar_deu_co_trong_html_hoac_duoc_dung_dong(self):
        """Lỗi thật đã gặp khi bỏ cặp nút trên cùng: app.js còn gọi $("segMode") đã bị xóa khỏi HTML -> cả panel đứng. Test này bắt cả họ lỗi đó."""
        import glob
        import re
        web = os.path.join(HERE, "..", "app", "troly_web")
        ids = set(re.findall(r'id="([^"]+)"', self.html))
        dyn = {"aiSkip", "tplName", "ioHead", "lnLang", "lnLangBtn", "lnPick", "evName", "d5TlName"}                 # sinh động trong JS (innerHTML), không nằm sẵn trong HTML
        for f in sorted(glob.glob(os.path.join(web, "*.js"))):
            with open(f, encoding="utf-8") as fh:
                src = fh.read()
            miss = {m for m in re.findall(r'\$\("([A-Za-z0-9_]+)"\)', src) if m not in ids and m not in dyn}
            self.assertEqual(miss, set(), os.path.basename(f))

    def test_khong_goi_davinci_va_hop_ap_dung_nhac_so_clip_ai_xep(self):
        seg = self.js[self.js.index("Việc 3 (ADR-0023)"):]
        for bad in ("api().apply", "api().move(", "inout_write", "SetMarkInOut", "append_starred"):
            self.assertNotIn(bad, seg, bad)
        self.assertIn("do AI tự xếp", self.app)                                                # hộp Áp dụng nói rõ số clip AI xếp


if __name__ == "__main__":
    unittest.main()
