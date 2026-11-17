"""Đổi tên giai đoạn / bin con (ADR-0015): nhãn không mất, tên sai bị chặn, phím 1-9 theo vị trí, nhật ký chuyển đi theo tên mới.
Dùng tên ví dụ (LV_Ten), không dùng tên khách thật."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import troly_core as tc            # noqa: E402

SRC = "Master/01_footage/01_SELECTED"


def plan():
    p = tc.new_plan("2026.10.17.LV_Ten")
    p["source_bin"] = SRC
    p["stages"] = [tc.make_stage("Gia tiên", 480, 540, ["Decor", "Nghi lễ", "Phỏng vấn"], 0),
                   tc.make_stage("Đón khách", 540, 600, ["Decor", "Khách"], 1)]
    p["labels"] = {"01_footage/A.MP4": {"stage": "Gia tiên", "bin": "Decor"},
                   "01_footage/B.MP4": {"stage": "Gia tiên", "bin": "Nghi lễ"},
                   "01_footage/C.MP4": {"stage": "Đón khách", "bin": "Decor"}}
    p["manual"] = {"01_footage/D.MP4": {"stage": "Gia tiên"}}
    p["moves"] = [{"at": "x", "bin": SRC, "log": [["u1", SRC, SRC + "/01_Gia tiên/Decor"], ["u2", SRC, SRC + "/01_Gia tiên"],
                                                   ["u3", SRC, SRC + "/02_Đón khách/Decor"]]}]
    p["ui"] = {"gStage": 0, "gSub": "Decor"}
    return p


class CheckName(unittest.TestCase):
    def test_hop_le_gon_khoang_trang(self):
        self.assertEqual(tc.check_new_name("  Lễ  nhập gia ", ["Gia tiên"], "Gia tiên"), ("Lễ nhập gia", None))

    def test_rong_ky_tu_cam_trung_ten_dai(self):
        self.assertIsNotNone(tc.check_new_name("   ", [])[1])
        for ch in ':&/\\*?"<>|':
            n, err = tc.check_new_name("Tên%sX" % ch, [])
            self.assertIsNotNone(err, ch)
            self.assertIn(ch, err)
        self.assertIn("Đã có", tc.check_new_name("decor", ["Decor", "Khách"], "Khách")[1])     # không phân biệt hoa thường
        self.assertIsNone(tc.check_new_name("Decor", ["Decor", "Khách"], "Decor")[1])          # giữ nguyên tên mình: không báo trùng
        self.assertIsNotNone(tc.check_new_name("x" * 61, [])[1])


class RenameInPlan(unittest.TestCase):
    def test_doi_ten_giai_doan_nhan_khong_mat(self):
        p = plan()
        old, new = tc.rename_in_plan(p, "stage", 0, "Gia tiên", "Lễ nhập gia")
        self.assertEqual((old, new), (SRC + "/01_Gia tiên", SRC + "/01_Lễ nhập gia"))
        self.assertEqual(p["stages"][0]["name"], "Lễ nhập gia")
        self.assertEqual(p["labels"]["01_footage/A.MP4"], {"stage": "Lễ nhập gia", "bin": "Decor"})
        self.assertEqual(p["labels"]["01_footage/B.MP4"]["stage"], "Lễ nhập gia")
        self.assertEqual(p["labels"]["01_footage/C.MP4"]["stage"], "Đón khách")            # giai đoạn khác không đổi
        self.assertEqual(p["manual"]["01_footage/D.MP4"], {"stage": "Lễ nhập gia"})
        # đường bin đích của clip đã xếp vẫn là bin con cũ của giai đoạn mới
        lab = p["labels"]["01_footage/A.MP4"]
        self.assertEqual(tc.target_folder(0, lab, p["stages"]), ["01_Lễ nhập gia", "Decor"])

    def test_doi_ten_giai_doan_sua_nhat_ky_chuyen(self):
        p = plan()
        tc.rename_in_plan(p, "stage", 0, "Gia tiên", "Lễ nhập gia")
        log = p["moves"][0]["log"]
        self.assertEqual(log[0][2], SRC + "/01_Lễ nhập gia/Decor")
        self.assertEqual(log[1][2], SRC + "/01_Lễ nhập gia")
        self.assertEqual(log[2][2], SRC + "/02_Đón khách/Decor")                          # bin khác giữ nguyên
        self.assertEqual(log[0][1], SRC)

    def test_doi_ten_bin_con_nhan_khong_mat_va_phim_so_theo_vi_tri(self):
        p = plan()
        before = list(p["stages"][0]["bins"])
        old, new = tc.rename_in_plan(p, "bin", 0, "Decor", "Trang trí")
        self.assertEqual((old, new), (SRC + "/01_Gia tiên/Decor", SRC + "/01_Gia tiên/Trang trí"))
        self.assertEqual(p["stages"][0]["bins"], ["Trang trí", "Nghi lễ", "Phỏng vấn", "Khác"])
        self.assertEqual(p["stages"][0]["bins"][1:], before[1:])
        self.assertEqual(p["stages"][0]["bins"].index("Trang trí"), before.index("Decor"))     # phím 1 vẫn là bin đầu
        self.assertEqual(p["labels"]["01_footage/A.MP4"]["bin"], "Trang trí")
        self.assertEqual(p["labels"]["01_footage/C.MP4"]["bin"], "Decor")                  # bin cùng tên ở giai đoạn khác không đổi
        self.assertEqual(p["stages"][1]["bins"][0], "Decor")
        self.assertEqual(p["moves"][0]["log"][0][2], SRC + "/01_Gia tiên/Trang trí")
        self.assertEqual(p["moves"][0]["log"][2][2], SRC + "/02_Đón khách/Decor")
        self.assertEqual(p["ui"]["gSub"], "Trang trí")
        self.assertEqual(tc.target_folder(0, p["labels"]["01_footage/A.MP4"], p["stages"]), ["01_Gia tiên", "Trang trí"])

    def test_hai_giai_doan_trung_ten_chi_doi_clip_thuoc_giai_doan_do(self):
        p = plan()
        p["stages"][1]["name"] = "Gia tiên"                                                # trùng tên với giai đoạn 0
        p["labels"]["01_footage/C.MP4"] = {"stage": "Gia tiên", "bin": "Decor"}            # clip C thuộc giai đoạn 1
        tc.rename_in_plan(p, "stage", 1, "Gia tiên", "Lễ phụ", in_stage_keys={"01_footage/C.MP4"})
        self.assertEqual(p["labels"]["01_footage/C.MP4"]["stage"], "Lễ phụ")
        self.assertEqual(p["labels"]["01_footage/A.MP4"]["stage"], "Gia tiên")             # giai đoạn 0 không bị ảnh hưởng
        self.assertEqual(p["labels"]["01_footage/B.MP4"]["stage"], "Gia tiên")
        self.assertEqual(p["manual"]["01_footage/D.MP4"]["stage"], "Gia tiên")
        self.assertEqual((p["stages"][0]["name"], p["stages"][1]["name"]), ("Gia tiên", "Lễ phụ"))

    def test_doi_roi_doi_lai_tro_ve_nguyen_trang(self):
        p0 = plan()
        p = copy.deepcopy(p0)
        tc.rename_in_plan(p, "stage", 0, "Gia tiên", "Lễ nhập gia")
        tc.rename_in_plan(p, "bin", 0, "Decor", "Trang trí")
        tc.rename_in_plan(p, "bin", 0, "Trang trí", "Decor")
        tc.rename_in_plan(p, "stage", 0, "Lễ nhập gia", "Gia tiên")
        self.assertEqual(p, p0)

    def test_file_project_cu_van_dung_duoc_sau_khi_doi_tuy_ten(self):
        """Định dạng kế hoạch KHÔNG đổi (không cần nâng cấp): lưu, nạp lại, nhãn còn nguyên sau khi đổi tên."""
        import tempfile
        d = tempfile.mkdtemp()
        p = plan()
        tc.save_plan(d, p)
        q = tc.load_plan(d, p["project"])
        tc.rename_in_plan(q, "bin", 0, "Nghi lễ", "Lễ chính")
        tc.save_plan(d, q)
        r = tc.load_plan(d, p["project"])
        self.assertEqual(r["labels"]["01_footage/B.MP4"], {"stage": "Gia tiên", "bin": "Lễ chính"})
        self.assertTrue(os.path.isfile(tc.plan_path(d, p["project"]) + ".bak"))            # bản .bak giữ bản trước


if __name__ == "__main__":
    unittest.main()
