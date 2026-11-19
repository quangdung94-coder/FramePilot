# ADR-0033: Bước 1 chọn mốc giai đoạn bằng thumbnail (19/11/2026)

## Bối cảnh
Người dựng duyệt demo `design/trang1_chon_moc` (demo_trang1.html + ảnh p1_*): tab "1 · Giai đoạn" thành màn hình CHỌN MỐC: bấm một clip rồi bấm F1, F2… để đặt mốc ĐẦU
của giai đoạn, Shift+F1… để đặt mốc CUỐI. Bin con vẫn nhập như cũ. Thay phần giao diện của ADR-0032 (thanh timeline kéo mép, con trỏ đỏ, cắt giai đoạn tại con trỏ,
bin mẹ dạng khung); nguồn dữ liệu timeline và gộp máy theo track của ADR-0032 GIỮ NGUYÊN.

## Quyết định
- **Bố cục** (một màn hình, không cuộn cả trang): cột trái là danh sách giai đoạn (tên, số file, giờ, hai dòng mốc đầu F1… và cuối ⇧F1…), "+ Thêm giai đoạn" (tối đa 9),
  ô Mẫu + "Gợi ý lại", nút "Tạo bin, sang bước 2" ở đáy cột trái. Trên cùng bên phải: timeline thu thấp (thước, mỗi máy một hàng, khối giai đoạn; giai đoạn có mốc đầu
  chưa có mốc cuối vẽ nét đứt; vạch trắng đứt là clip đang chọn). Dưới chia ba khối: cây Media bin, lưới thumbnail theo giờ quay có thanh nhắc phím, Thông tin clip.
- **Phím** đọc bằng `event.code` (F1…F9; Shift giữ = mốc CUỐI). Chặn mốc đầu SAU mốc cuối và mốc cuối TRƯỚC mốc đầu cùng giai đoạn (đỏ). Chưa chọn clip hoặc chưa có giai đoạn: vàng.
  Thành công: xanh. Không làm "bấm F1 hai lần thay Shift+F1". Phím F-số cũ ở Bước 2 (bin con) giữ nguyên.
- **Mốc lưu trong kế hoạch** (`stage["head"]`, `stage["tail"]` = khóa clip). Giờ giai đoạn: đầu = giờ (vị trí) clip đầu, cuối = hết clip cuối.
  Project NHIỀU MÁY (timeline sync): các giai đoạn LIỀN NHAU, cuối = đầu của giai đoạn kế có mốc đầu, không có khoảng trống. Project 1 máy: vẫn có khoảng trống như cũ.
  Giai đoạn mới chưa có giờ và chưa nhận clip nào ("thiếu mốc" khi chưa đủ mốc).
- **Tương thích**: giai đoạn không có khóa `head` (kế hoạch cũ, hoặc đặt giờ tay) giữ nguyên start/end; giao diện hiện clip đầu/cuối suy ra (chữ nghiêng, "tự động").
  Bấm F lần đầu thì chuyển sang mốc, giữ clip suy ra cho đầu hoặc cuối còn lại. "Gợi ý lại" đổi khoảng giờ gợi ý thành mốc (clip).
- **Cây Media bin** hiện bin thật của project; bấm bin để đọc bin đó; máy A, B, C là chữ cái màu dưới bin đang đọc (bấm để lọc lưới).
- Không ghi gì vào Media Pool ở bước này (chỉ đọc). Tạo bin vẫn do logic cũ ("Tạo bin, sang bước 2"), không đổi.

## Đã bỏ khỏi giao diện (ADR-0032 bản đầu)
Zoom, con trỏ đỏ, "Cắt giai đoạn tại con trỏ", bám mép clip, kéo mép giai đoạn, khung bin mẹ trong danh sách giai đoạn (hàm `cut_stage`, `add_event`, `rename_event` còn trong API, chưa có nút).

## Thử
- Test: tests/test_nguon_timeline.py (lớp Marks, KeyFiles). Chạy đủ 556+ test.
- Panel THẬT (pywebview/WebView2) trên BẢN SAO dữ liệu (tools/panel_probe.py, config tạm qua TROLY_CONFIG), nối DaVinci thật chỉ đọc, project 1 máy 2026.10.25 (400 clip):
  bấm phím thật F1, Shift+F1, chặn mốc đầu sau mốc cuối (đỏ), F9 khi chưa có giai đoạn 9 (vàng), Esc bỏ chọn: đều đúng.
- Nhiều máy: thử bằng DaVinci GIẢ có timeline đã sync 3 máy (dữ liệu thử, tools/harness_cam.py --tl) trên giao diện cùng HTML/JS. Project thật 2026.11.14 đang không mở trong DaVinci
  lúc thử nên CHƯA thử nhiều máy thật trên panel pywebview.
