# ADR-0028: Chữ hiển thị trong panel gọi người dùng là "bạn"

Ngày: 18/11/2026 (đêm). Nhánh doi-ten-framepilot (commit riêng sau ADR-0027). Trạng thái: đã code, chờ người dựng đọc lại.

## Quyết định
Mọi chữ HIỂN THỊ cho người dùng (nút, nhãn, tooltip, chú thích, hộp xác nhận, thông báo lỗi/thành công, trạng thái, trang báo cáo tĩnh của Bước 6) gọi người dùng là "bạn"
thay cho "anh" / "Anh". Đã quét cả các tab (Giai đoạn, Phân loại, In/Out, Lời nói, Thời lượng; phần AI nằm trong Bước 2) và các chuỗi do Python trả về giao diện.

## Cách làm
- Quét có phân biệt: chuỗi Python (ast, bỏ docstring), html/js (bỏ chú thích). 39 chỗ đổi trong 10 file, đọc từng chỗ (đều là đại từ chỉ người dùng) và đọc lại cho tự nhiên:
  "Quy tắc của bạn", "Bạn đặt tay", "chờ bạn duyệt", "Giai đoạn bạn khóa", "Mỗi lần bạn xếp"...
- Test `tests/test_troly_framepilot.py::XungHo` quét lại mỗi lần chạy test: "anh" đứng một mình trong chuỗi hiển thị phải ra 0 chỗ; bộ quét có test riêng
  (bắt "Anh xếp", "của anh"; bỏ qua "ảnh", "nhanh", "thanh", "tiếng Anh").

## Chỗ cố ý GIỮ
- `app/troly_web/step3.js`: `"tiếng Anh"` (nhãn ngôn ngữ English của Whisper), không phải đại từ.
- Chú thích mã và docstring trong app\ vẫn còn chữ "anh" (không hiển thị). ADR, tài liệu nội bộ, CLAUDE.md giữ nguyên theo yêu cầu.
- Tên riêng và dữ liệu thật (tên bin, tên file), từ "ảnh", khóa lưu dữ liệu, tên biến: không đụng.

## Đã kiểm
Panel mở ở 1440x900 qua cầu nối trình duyệt (API thật + DaVinci giả): 5 trang không còn "anh" đứng một mình, không tràn ngang. Chỉ phải thu nút
"Tự phân loại · N clip nhóm X" xuống 12,5 px cho vừa chữ (nút này mới ở ADR-0026, chữ dài hơn khung).

## Chưa kiểm
Panel pywebview thật chưa mở lại sau đợt đổi này; chữ do DaVinci hoặc ffmpeg trả về (không do panel viết) nếu có.
