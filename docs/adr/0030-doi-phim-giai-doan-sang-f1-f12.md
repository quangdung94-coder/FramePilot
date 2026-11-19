# ADR-0030: Đổi phím chọn giai đoạn ở Bước 2 từ Shift+số sang F1–F12 (19/11/2026)

## Bối cảnh
Bước 2 dùng Shift+số hàng trên để chọn giai đoạn. Shift+số phụ thuộc bố cục bàn phím và bộ gõ (Unikey/VNI chặn phím số,
Shift+số numpad bị Windows bỏ Shift), nên lúc chạy lúc không. Người dựng yêu cầu đổi sang phím F.

## Quyết định
- F1–F12 = chuyển clip đang chọn sang giai đoạn thứ 1–12, rồi chờ số 1–9 chọn bin con của giai đoạn đó (0 bỏ nhãn, Esc để thôi).
  Phím 1–9 gán bin con giữ nguyên. Shift+số không còn là phím giai đoạn: bấm thì chỉ hiện dòng nhắc phím mới.
- Đọc phím bằng `event.code` (`F1`…`F12`), không dùng `event.key`.
- Chặn mặc định (preventDefault) của F1 (trợ giúp), F5 (tải lại), F11 (toàn màn hình), F12 (công cụ dev) trong cửa sổ panel.
  Khi chạy `--debug` thì F12 do panel chặn; mở công cụ dev bằng chuột phải > Inspect.
- Quá 12 giai đoạn: giai đoạn thứ 13 trở đi không có phím. Giao diện hiện dòng cảnh báo nêu tên các giai đoạn đó và cách dùng
  thay thế (kéo thả vào bin bên trái, chuột phải thumbnail). Bấm F của giai đoạn không tồn tại thì báo trên thanh trạng thái.
- Nhãn trên giao diện: cột Media Pool, dòng nhắc phím, danh sách bên phải, menu chuột phải đều ghi F1…F12.

## Hệ quả
Không đổi dữ liệu kế hoạch. Thay thế phần phím trong ADR-0009 (bổ sung 15/11); phần còn lại của ADR-0009 vẫn đúng.
