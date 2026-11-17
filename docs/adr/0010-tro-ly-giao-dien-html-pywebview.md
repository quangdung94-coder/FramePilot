# ADR-0010: Giao diện Trợ lý File Quay chuyển sang HTML trong cửa sổ pywebview (WebView2)

- Ngày: 2026-11-15
- Trạng thái: Đã chốt (người dựng duyệt 15/11/2026)

## Bối cảnh
Trợ lý File Quay v0.1.0 (ADR-0009) vẽ bằng CustomTkinter. Người dựng đã duyệt bộ thiết kế demo
`docs/03-design/troly_demo/*.dc.html` (nền #18181B, màu nhấn cam #F2A33A, chữ Inter, thẻ bo góc, lưới thumbnail,
thanh thời gian có tay kéo). Vẽ lại các khối đó bằng Tk rất tốn công và khó giống: Tk không có bo góc, độ trong suốt,
chữ Inter, lưới tự co giãn hay kéo-thả mượt. HTML/CSS làm được thẳng và giống demo.

## Các lựa chọn đã cân nhắc
1. Giữ CustomTkinter và vẽ gần giống demo: tốn công, chỉ giống được khoảng 50-60%.
2. Web app chạy trong trình duyệt + máy chủ cục bộ: phải mở cổng mạng, người dựng mở thêm trình duyệt.
3. Electron: thêm Node.js và khoảng 150 MB, hai ngôn ngữ để bảo trì.
4. pywebview: một cửa sổ Windows dùng WebView2 có sẵn trong Windows 10/11, Python gọi thẳng, không mở cổng mạng (chọn).

## Quyết định
- Cài `pywebview` vào venv dự án (requirements.txt). Cửa sổ `src/panel_troly_web.py` mở `src/troly_web/index.html`
  (+ `style.css`, `app.js`), mở toàn màn hình để vừa mọi tỉ lệ DPI.
- Chức năng nằm trong một lớp Python `src/troly_api.py` (TrolyApi). JavaScript gọi qua `window.pywebview.api.<tên>`.
  Lớp này không import pywebview nên kiểm thử được (tests/test_troly_api.py). Việc chạy nền (đọc DaVinci, áp dụng,
  thumbnail) báo về giao diện qua `window.evaluate_js("onEvent(...)")`. Thumbnail gửi dạng data URI, video không rời máy.
- Giữ nguyên `troly_core.py`, `troly_thumbs.py`, `troly_resolve.py` và quyền ghi DaVinci của ADR-0009: chỉ tạo bin con +
  MoveClips, luôn có hộp xác nhận trước khi ghi và hoàn tác được.
- Bố cục, màu, chữ, nhãn lấy theo demo. Những chỗ khác demo có lý do:
  - Thanh trên bước 1: ô chọn bin nguồn + "Đọc clip" thay cho nút "Quét lại thư mục" (Trợ lý đọc Media Pool, không quét ổ).
  - Cột trái bước 1 thêm ô mẫu sự kiện + "Gợi ý lại", và ô lệch giờ theo máy (chỉ hiện khi có từ 2 máy).
  - Bước 2: cột phải hiện thông tin clip đang chọn và phím tắt của giai đoạn. Thanh In/Out và quy tắc từng bin để trạng thái
    "sắp có" (chưa có chức năng). Hai nút dưới là "Mở trong DaVinci" và "Áp dụng vào Media Pool".
  - Nút "AI gợi ý" có nhưng tắt (chưa có dữ liệu học). Bước 4 chỉ có trạng thái "sắp có".
  - Thêm thanh trạng thái mảnh ở đáy cửa sổ (tiến độ đọc clip, thumbnail, lỗi).
- `panel_troly.py` (CustomTkinter) giữ làm dự phòng tới khi bản HTML chạy ổn. `scripts/install_troly.py` cho menu
  mở bản HTML, máy thiếu pywebview thì tự mở bản dự phòng.
- Chữ Inter tải từ Google Fonts; máy không có mạng thì tự dùng Segoe UI.

## Hệ quả
- Giao diện giống demo nhiều hơn (đã so ảnh chụp ở 1440x900 và 4K 150%), sửa giao diện chỉ cần sửa HTML/CSS.
- Thêm một thư viện (pywebview, kéo theo pythonnet). Cần WebView2 Runtime (có sẵn trên Windows 10/11 cập nhật).
- Có hai bản giao diện cần giữ đồng bộ chức năng cho tới khi bỏ bản CustomTkinter.
