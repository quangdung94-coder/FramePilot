# ADR-0015: Đổi tên giai đoạn và bin con chỉ trong kế hoạch của panel (không đổi tên trong Media Pool, không mô hình id)

- Ngày: 2026-11-17
- Trạng thái: Đã chốt (người dựng đổi kế hoạch 17/11/2026 khuya). Chờ người dựng thử bằng tay.

## Bối cảnh
Mỗi project cưới có bộ giai đoạn và bin con khác nhau; người dựng muốn tự đổi tên (ví dụ "Gia tiên" thành "Lễ nhập gia", "Decor"
thành "Trang trí") ngay trên panel mà nhãn clip đã xếp không mất. Nhãn lưu theo TÊN: `plan["labels"][clip] = {stage, bin}`,
`plan["manual"][clip] = {stage}`, `plan["ui"]["gSub"]`. Nhật ký chuyển `plan["moves"]` ghi đường bin THẬT trong Media Pool.
Kiểm DaVinci Resolve Studio 21.1.1.10 (17/11): đối tượng bin (`Folder`) chỉ có `GetName`, không có hàm đổi tên.

## Các lựa chọn đã cân nhắc
1. Đổi tên cả bin trong Media Pool bằng cách tạo bin mới, chuyển clip, xóa bin cũ rỗng. Đã làm thử rồi gỡ: có thao tác xóa bin,
   nhiều ca lỗi giữa chừng (hai bin trùng, chuyển dở), và không cần thiết.
2. Thêm mã id cho từng giai đoạn/bin, nhãn lưu theo id, nâng cấp file project cũ: thêm một lớp và một bước nâng cấp dữ liệu của
   người dựng, trong khi Media Pool vẫn nhận bin theo tên.
3. Đổi tên trực tiếp trong kế hoạch của panel (chọn).

## Quyết định
- Bin trong panel chỉ là NHÃN. Bin thật trong Media Pool chỉ được tạo khi bấm "Áp dụng". Vì vậy đổi tên chỉ ghi vào kế hoạch,
  KHÔNG gọi gì sang DaVinci, KHÔNG xóa gì, KHÔNG cần mô hình id, KHÔNG đổi định dạng file project (không cần nâng cấp, `.bak` vẫn
  giữ bản trước mỗi lần lưu).
- `troly_core.rename_in_plan` viết lại tên mới ở `stages`, `labels`, `manual`, `ui`. Giữ NGUYÊN `moves` vì nó ghi bin thật còn
  tên cũ, nên Hoàn tác lần Áp dụng cũ vẫn tìm đúng bin. Phím 1–9 theo VỊ TRÍ bin trong giai đoạn, đổi tên không đổi vị trí.
- Hai giai đoạn trùng tên (gặp thật sau "Gợi ý lại"): chỉ đổi nhãn của clip đang thuộc giai đoạn được đổi tên; nếu tên là duy nhất thì
  đổi mọi nhãn, kể cả clip chưa nạp.
- `troly_core.check_new_name`: không rỗng, không ký tự cấm `: & / \ * ? " < > |`, không quá 60 ký tự, không trùng tên khác trong
  cùng cấp (không phân biệt hoa thường); bin "Khác" không đổi tên được. Python báo lỗi rõ, giao diện hiện nguyên văn.
- Giao diện: bấm đúp tên giai đoạn (bước 1 và cột Media Pool) hoặc tên bin con (cột Media Pool) để sửa tại chỗ; Enter đổi, Esc hoặc
  bấm ra ngoài thì hủy; phím trong ô sửa không chạy phím tắt (J, 1–9). Form sửa giai đoạn cũng đi qua đường này khi đổi tên.
- Nếu đã Áp dụng rồi mới đổi tên: lần Áp dụng sau sẽ tạo bin tên mới và chuyển clip sang, bin cũ còn lại RỖNG. Hộp xác nhận Áp dụng
  liệt kê các bin cũ sẽ rỗng (`apply_preview` trả `emptied`) và nhắc Trợ lý không tự xóa bin, người dựng xóa tay nếu không cần.

## Hệ quả
- Được: đổi tên tức thì, không rủi ro cho Media Pool, nhãn không mất, không động tới file project cũ.
- Mất: bin cũ trong Media Pool để lại rỗng cho người dựng xóa tay. Muốn có "đổi tên thật trong Media Pool" thì phải chờ DaVinci có
  hàm đổi tên bin hoặc làm lại phương án tạo bin mới (cần người dựng đồng ý việc xóa bin).
- Chưa làm: menu chuột phải "Đổi tên" (bấm đúp đủ dùng); chưa thử trong cửa sổ pywebview thật.
