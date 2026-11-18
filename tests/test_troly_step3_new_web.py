"""Bước 3 làm lại (ADR-0024), phần giao diện: cột trái dạng cây có đếm sao/tổng, công tắc mặc định BẬT, nút gợi ý, phím A chỉ ở Bước 3,
khung chữ Whisper (bấm câu, Shift nối dài, chưa chép, không tiếng nói), chữ hướng dẫn có chức năng thật, không gọi ghi DaVinci."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web")


def rd(n):
    with open(os.path.join(WEB, n), encoding="utf-8") as f:
        return f.read()


class Step3New(unittest.TestCase):
    def setUp(self):
        self.html, self.s3, self.app, self.ai, self.pl, self.css = rd("index.html"), rd("step3.js"), rd("app.js"), rd("ai.js"), rd("player.js"), rd("style.css")

    def test_cot_trai_la_cay_dem_sao_tren_tong_va_cong_tac_mac_dinh_bat(self):
        self.assertRegex(self.html, r'<input type="checkbox" id="p3OnlyStar" checked>')
        self.assertIn("Chỉ hiện clip có sao", self.html)
        self.assertNotIn('id="p3Stage"', self.html)                                           # không còn ô chọn bin
        self.assertIn('<span class="n"><b>${uids.filter((u) => star.has(u)).length}</b> / ${uids.length}</span>', self.s3)   # "số clip sao / tổng"
        for cls in ("pool-row", "sub-none", "pool-subs", 'class="sub'):                       # cùng kiểu vẽ với cây Bước 2
            self.assertIn(cls, self.s3)
        self.assertIn("P3.onlyStar", self.s3)
        self.assertIn("onlyStar: true", self.s3)                                              # mặc định BẬT
        self.assertIn(" off", self.s3[self.s3.index("p3-clip${i === cur"):self.s3.index("p3-clip${i === cur") + 120])   # clip chưa sao hiện mờ

    def test_dong_clip_co_ten_gio_cham_trang_thai_va_giu_lai(self):
        seg = self.s3[self.s3.index("const clipsHtml"):self.s3.index("let h = S.stages.map")]
        for part in ("c.name", "c.time", "p3Dot(c)", "p3Keep(c)", "c.star"):
            self.assertIn(part, seg, part)

    def test_nut_goi_y_chay_nen_co_tien_do_va_da_chay_n_tren_m(self):
        self.assertIn('id="p3Sug"', self.html)
        self.assertIn("Chạy gợi ý cho", self.html)                                            # chữ trên nút chính (không còn là khung thông tin)
        self.assertIn("api().inout_suggest_start()", self.s3)
        self.assertIn("đã chạy ${g.done}/${n}", self.s3)
        self.assertIn("inout_sug_progress", self.s3)
        self.assertIn('kind.indexOf("inout_sug_") === 0', self.app)                           # sự kiện nền được nối
        self.assertIn("đã nhận hoặc chỉnh", self.s3)                                          # chân trang đếm số thật

    def test_cay_thu_gon_mo_bang_mui_ten_va_bam_lai_dong_dang_chon(self):
        seg = self.s3
        self.assertIn("P3.fold", seg)
        self.assertIn("fold: {}", seg)                                                         # nhớ trạng thái thu gọn khi đổi clip / đổi bước
        self.assertIn('folded("s:" + i, true)', seg)                                           # cả giai đoạn: mặc định THU GỌN
        self.assertIn('folded("b:" + i + ":" + bn.name, false)', seg)                          # bin: mặc định mở
        self.assertIn("▾", seg)
        self.assertIn("▸", seg)
        self.assertIn("p3-ar", seg)
        fn = seg[seg.index("function p3RowClick"):seg.index('$("p3List").addEventListener("click"')]
        self.assertIn("selected", fn)                                                          # bấm lại dòng đang chọn: đảo trạng thái thu gọn
        self.assertIn("P3.fold[key] = !", fn)
        for bad in ("api().label", "api().move(", "assign("):                                  # bấm bin chỉ XEM, không đổi nhãn
            self.assertNotIn(bad, seg[seg.index("function p3FoldKey"):seg.index('$("p3OnlyStar")')], bad)
        self.assertIn('e.code === "ArrowUp" || e.code === "ArrowDown"', self.app)              # mũi tên lên/xuống đổi clip vẫn chạy

    def test_nut_goi_y_la_nut_chinh_va_khong_im_lang_khi_loi(self):
        self.assertIn("Chạy gợi ý cho", self.s3)
        self.assertIn("Chạy lại gợi ý", self.s3)                                               # xong thì đổi thành "Chạy lại"
        self.assertIn("Đang gợi ý… ${g.n}/${g.total}", self.s3)                                # tiến độ ngay trên nút
        seg = self.s3[self.s3.index("async function p3SugStart"):self.s3.index("async function p3SugFinish")]
        self.assertIn("catch (e)", seg)                                                        # gọi API lỗi cũng bắt
        self.assertIn('p3SugMsg("Không chạy: "', seg)                                          # hiện lỗi rõ
        self.assertIn("status(m, \"warn\")", seg)
        self.assertNotIn("b.disabled = run || !g.starred", self.s3)                            # không khoá im lặng khi chưa có sao
        self.assertIn("p3SugSummary()", self.s3)                                               # dòng trạng thái báo kết quả
        self.assertIn(".p3-gy { background: var(--accent)", self.css)                          # nền nổi

    def test_phim_a_chi_o_buoc_3_va_buoc_2_giu_a_cho_ai_xep_bin(self):
        self.assertIn('page !== 3 || e.code !== "KeyA"', self.s3)
        self.assertIn("/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)", self.s3[self.s3.index('page !== 3 || e.code !== "KeyA"'):][:400])
        self.assertIn("if (page !== 2 ||", self.ai)                                           # ai.js: A ở Bước 2 vẫn là nhận gợi ý AI xếp bin
        self.assertNotRegex(self.s3, r"\be\.key\b")
        self.assertIn("p3SeqNext()", self.s3[self.s3.index("async function p3Accept"):])        # nhận xong tự sang clip kế
        self.assertIn("Nhận gợi ý (A)", self.html)

    def test_khung_chu_whisper_cac_trang_thai_va_thao_tac(self):
        self.assertIn("Bấm một câu để đặt In/Out theo câu đó · Shift + bấm câu khác để nối dài", self.html)
        self.assertIn("Chưa chép lời cho clip này", self.s3)
        self.assertIn("Mở Bước 4 · Lời nói", self.s3)
        self.assertIn("goPage(4)", self.s3)
        self.assertIn('box.classList.add("hidden"); ctr.classList.add("notx")', self.s3)        # không có tiếng nói: ẩn khung chữ, sóng âm cao hơn
        self.assertIn("e.shiftKey && P3.anchor != null", self.s3)                              # Shift + bấm nối dài
        self.assertIn("Đặt In ở đây", self.s3)
        self.assertIn("Đặt Out ở đây", self.s3)
        self.assertIn("d.has_row", self.s3)
        self.assertIn(".p3-ln.now", self.css)

    def test_khong_goi_ghi_davinci_ngoai_hop_xac_nhan_co_san(self):
        for bad in ("inout_write(", "api().apply", "SetMarkInOut", "append_starred", "api().move("):
            self.assertNotIn(bad, self.s3, bad)
        self.assertIn("await ask(", self.pl[self.pl.index("async function plWrite"):][:900])    # nút Ghi vẫn phải qua hộp xác nhận

    def test_id_khong_trung_va_nguon_goi_y_hien_o_cot_phai(self):
        ids = re.findall(r'\bid="([^"]+)"', self.html)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("P3_SRC", self.s3)
        self.assertIn("theo lời nói", self.s3)
        self.assertIn("theo quy tắc bin", self.s3)
        self.assertIn('id="p3Pad"', self.html)                                                 # ô đệm (mặc định 0,3 s)


if __name__ == "__main__":
    unittest.main()
