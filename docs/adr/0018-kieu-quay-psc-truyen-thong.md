# ADR-0018: Kiểu quay PSC / Truyền thống theo từng project (bộ tham số của gợi ý In/Out)

- Ngày: 2026-11-18
- Trạng thái: Đã code và kiểm thử. CHỜ NGƯỜI DỰNG THỬ.

## Bối cảnh
Mỗi đám có kiểu quay khác nhau. PSC: clip ngắn, mỗi cảnh chỉ cần khoảng 3 đến 7 giây theo loại bin. Truyền thống: máy quay dài, người dựng muốn
giữ source dài nhất có thể và chỉ bỏ khoảng một đến hai giây đầu và đuôi mỗi clip. Quy tắc tự tính In/Out nâng cao đang TẠM HOÃN, nên đây chỉ là
bộ tham số cho gợi ý màu xanh hiện có (`troly_core.suggest_inout`), không phải thuật toán mới.

## Quyết định
- Công tắc **theo từng project**, lưu trong kế hoạch: `plan["shoot_style"]` ∈ {không có khóa = **chưa chọn**, `"traditional"`, `"psc"`}. Mặc định
  chưa chọn: **không đổi gì** (kiểm thử so với bảng giá trị của hàm trước khi thêm tính năng, 31 tổ hợp độ dài x nhãn bin, khớp từng số).
  File kế hoạch cũ không có khóa nên mở bình thường.
- **Truyền thống:** gợi ý vào = 1,5 giây, ra = hết clip trừ 1,5 giây đuôi, không phân biệt bin. Clip ngắn cắt ít hơn để còn ít nhất 1 giây;
  clip 1 giây không cắt; dưới 1 giây không gợi ý (như cũ).
- **PSC:** dùng đúng bộ tham số hiện có (Decor 3 giây, Cô dâu chú rể 4 giây, Nghi lễ 5 đến 7 giây, Phỏng vấn giữ trọn câu, mặc định vào +1,2 giây giữ
  3 giây). Con số giống bản chưa chọn vì đó chính là quy tắc ngắn 3 đến 7 giây theo bin đã duyệt; PSC chỉ thêm nhãn "PSC ·" vào chữ giải thích. Nếu sau này
  muốn PSC khác mặc định thì chỉnh bảng này, không đụng chỗ khác.
- **Chỉ ảnh hưởng gợi ý màu xanh.** In/Out người dựng đặt tay luôn thắng (đã kiểm thử: đặt tay không đổi khi đổi kiểu), và gợi ý tự động KHÔNG bao giờ được
  ghi vào DaVinci (nút ghi chỉ ghi In/Out đặt tay; kiểm thử clip chưa đặt tay bị bỏ qua dù đã chọn kiểu).
- Giao diện: ô chọn "Kiểu quay: chưa chọn / Truyền thống / PSC" ở thanh trên của bước 2; đổi xong có thông báo rõ. Ở cửa sổ hẹp (dưới 1250 px) nút mờ
  "AI gợi ý" được ẩn để thanh trên không chật.

## Hệ quả
- Được: một công tắc đổi cả bộ gợi ý theo đám, không phải sửa mã; không rủi ro cho dữ liệu cũ.
- Mất: PSC chưa khác bản mặc định về số (chỉ khác nhãn). Truyền thống dùng cắt cố định 1,5 giây (giữa "1 đến 2 giây" đã nêu); người dựng chỉnh được nếu thấy dài/ngắn.
- Chưa làm: lưu kiểu quay làm mặc định theo loại sự kiện; chưa thử trong cửa sổ pywebview thật.
