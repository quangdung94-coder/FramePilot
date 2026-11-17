# ADR-0011: Nút "Đưa clip sao lên Timeline" chỉ tạo timeline MỚI, không sửa timeline đang có

- Ngày: 2026-11-17
- Trạng thái: Đã chốt

## Bối cảnh
Trợ lý File Quay v0.2.5 cho gắn sao ★ (phím J) và đưa các clip có sao lên DaVinci. Bản do Antigravity thêm ban đầu chèn
clip thẳng vào timeline ĐANG MỞ (AppendToTimeline). Cách này đã bị đổi: chèn vào timeline đang mở là sửa dữ liệu dựng
của người dựng (có thể đè lên phần đã dựng, khó hoàn tác), trái quy tắc "panel chỉ ghi bin con và timeline mới" của ADR-0009.
Ngoài ra In/Out của từng clip do người dựng tự chỉnh trong DaVinci, panel chỉ gợi ý (`suggest_inout`).

## Các lựa chọn đã cân nhắc
1. Chèn vào timeline đang mở (bản Antigravity): nhanh, nhưng sửa timeline có sẵn, rủi ro mất công dựng.
2. Hỏi người dùng chọn timeline đích: thêm một bước, vẫn có thể sửa nhầm timeline.
3. Luôn tạo timeline MỚI (chọn).

## Quyết định
- `TrolyWorker.do_append_timeline` chỉ tạo timeline mới tên "Rough Cut sao <project> <ngày giờ>" (bỏ ký tự `: & / \ * ? " < > |`),
  bằng `CreateTimelineFromClips`; dự phòng `CreateEmptyTimeline` + `AppendToTimeline` trên timeline vừa tạo đó.
- Không bao giờ sửa, xóa hay chèn vào timeline đã có. Không ghi In/Out (SetMarkInOut) lên clip.
- Thứ tự clip: theo giai đoạn rồi theo giờ quay thật.
- Nếu DaVinci không tạo được timeline thì báo rõ bước nào hỏng, không làm gì khác.

## Hệ quả
- Được: người dựng không bao giờ bị mất hay đổi timeline đang dựng; muốn bỏ chỉ cần xóa timeline mới.
- Mất: bấm nhiều lần sẽ ra nhiều timeline (tên có ngày giờ để phân biệt).
- Người dựng tự chỉnh In/Out trong DaVinci. Chưa làm ghi In/Out; nếu làm sau phải sao lưu In/Out cũ và có Hoàn tác.
