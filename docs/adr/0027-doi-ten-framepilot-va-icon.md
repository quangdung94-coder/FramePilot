# ADR-0027: Đổi tên hiển thị thành FramePilot và gắn icon

Ngày: 18/11/2026 (đêm). Nhánh doi-ten-framepilot. Trạng thái: đã code và đã mở cửa sổ pywebview thật để chụp (không có thao tác ghi nào lên DaVinci). Chờ người dựng xem lại.

## Đổi (chỉ chữ hiển thị)
- Tiêu đề cửa sổ pywebview: "FramePilot - <project>". Tiêu đề trang web và chữ trên thanh trên: "FramePilot". Hộp thoại lỗi Windows và lời nhắn tắt máy: "FramePilot".
- Menu DaVinci: file khởi chạy `FramePilot.py` (menu Workspace > Scripts > Utility hiện tên "FramePilot"). Mục tên cũ "VideoAI Trợ lý File Quay" KHÔNG tự xóa:
  `install.py` chỉ nhắc, xóa khi chạy `install.py --remove-old` và chỉ khi file có dấu do install.py tạo (không đụng file của người khác).
  Chưa chạy install.py đêm nay (không tự ghi vào thư mục Scripts của DaVinci); người dựng chạy `install.py` rồi tùy chọn `--remove-old`.
- CLAUDE.md, TRANG_THAI.md, CHANGELOG.md ghi tên mới. Không có file README riêng.

## KHÔNG đổi (đổi sẽ mất dữ liệu cũ)
Tên thư mục kho (TroLyFileQuay), tên repo, khóa lưu trong kế hoạch (plan) và dữ liệu (data_root, thư mục `troly`), tên bin/timeline đang tạo ("Rough Cut sao ..."),
tên các file Python và hàm bên trong (troly_*). Có test kiểm các khóa và tên timeline không dính chữ FramePilot.

## Icon
- `app/assets/framepilot.ico` có sẵn trong repo, đủ cỡ 16, 24, 32, 48, 64, 128, 256 (có test). Không cần tạo lại từ PNG 512 (không có file PNG trong repo).
- Gắn lên cửa sổ: sau sự kiện `shown`, gửi `WM_SETICON` (nhỏ và lớn, theo kích thước hệ thống ở DPI hiện tại) bằng ctypes từ `win.native.Handle`. Lỗi thì bỏ qua (mất icon, không mất chức năng).
- Taskbar: `SetCurrentProcessExplicitAppUserModelID("FramePilot")` (trước là "VideoAI.TroLy") để taskbar tách nhóm riêng và lấy icon từ cửa sổ, không hiện icon Python khi chạy bằng python.exe.

## Đã kiểm trên máy thật
Mở panel thật (cửa sổ pywebview, python.exe, `--project` tên giả) ở màn hình 3840x2160, DPI cửa sổ 144 (= 150%): tiêu đề "FramePilot - ...", `WM_GETICON` trả icon nhỏ và lớn khác 0, taskbar có ô riêng với icon P/F navy xanh ngọc, titlebar có icon 16 px; phóng to điểm ảnh thấy nét rõ ở 32 px (taskbar) và 16 px (titlebar), chữ F mảnh vẫn đọc được.
Panel báo "DaVinci đang mở project khác" (đúng, DaVinci đang mở project khác) và dừng: không đọc hay ghi project thật.

## Chưa chạy thật
- 100% DPI: máy chỉ đang ở 150%, không đổi được; cỡ 16/24/32 trong .ico có sẵn cho 100% nhưng chưa chụp.
- Chạy qua menu DaVinci với tên mới (cần chạy install.py trước).
- Lối tắt/.bat khởi động: repo không có.

## DaVinci tự đặt tên (không đổi được)
Mục trong menu Workspace > Scripts luôn lấy theo tên file (không có icon); tên cửa sổ DaVinci, Workflow Integrations (chưa dùng) do DaVinci quyết định.
