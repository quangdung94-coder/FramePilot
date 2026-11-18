# ADR-0019: Trang Bước 3 In/Out riêng: sóng âm và bảng quy tắc gợi ý từng bin

- Ngày: 2026-11-18
- Trạng thái: Đã code và kiểm thử. CHỜ NGƯỜI DỰNG THỬ. Demo và giao diện Bước 3 CHƯA được người dựng duyệt (được miễn duyệt trước cho lượt này; xem sau và có thể yêu cầu sửa bố cục).

## Bối cảnh
Bước 3 trước đây dùng chung màn hình với Bước 2 (cột phải). Cần trang riêng: trình phát proxy lớn, sóng âm, thanh In/Out kéo tay và bảng quy tắc
gợi ý từng bin chỉnh được. Quy tắc tự tính In/Out nâng cao vẫn TẠM HOÃN: bảng chỉ là bộ tham số của gợi ý màu xanh hiện có.

## Quyết định
- **Bảng quy tắc theo project**, lưu `plan["bin_rules"][tên bin] = {min, max, whole}`; dòng `"*"` = "Bin khác". Mỗi bin: giữ tối thiểu, tối đa (giây),
  "trọn câu" (giữ gần hết clip, bỏ tối đa). Mặc định lấy đúng bộ cũ (Decor 3s, Cô dâu/Chú rể/Beauty 4s, Nghi lễ 3 đến 7s, Phỏng vấn trọn câu từ 3s, còn lại 3s);
  bin chưa sửa KHÔNG có khóa nào trong kế hoạch, và kiểm thử so khớp 31 tổ hợp với bảng giá trị của hàm cũ: chưa sửa = gợi ý y hệt.
- Thứ tự áp dụng: bin đã sửa > quy tắc có sẵn khớp từ khóa tên bin > dòng "Bin khác" (chỉ cho bin không khớp quy tắc có sẵn) > mặc định.
- **Kiểm hợp lệ** (`check_bin_rule`): số, lớn hơn 0, tối đa 600 giây, min <= max. Sai thì báo rõ và KHÔNG ghi vào kế hoạch. Giá trị hỏng nằm sẵn trong file bị bỏ qua (dùng mặc định).
- **Kiểu quay (ADR-0018)**: PSC dùng bảng; Truyền thống bỏ qua bảng, chỉ cắt đầu/đuôi, số giây cắt chỉnh được (`plan["trad_trim_s"]`, mặc định 1,5, 0 đến 30).
- **Sóng âm** (`troly_wave.py`): ffmpeg đọc âm thanh từ file PROXY (chỉ đọc, ra stdout, không ghi gì cạnh proxy), 4 kHz mono, 800 cột đỉnh chuẩn hóa 0..100,
  lưu JSON ở `<data_root>\cache\troly_wave\<project>\` (xóa được; hết hạn khi proxy đổi cỡ/giờ sửa). Làm trên luồng nền, mỗi lần một clip, giới hạn 90 giây.
  Clip không có proxy: "Chưa có proxy". Proxy ngoài `proxy_root` bị từ chối. Lỗi ffmpeg/quá giờ/không có tiếng: báo lỗi, thanh In/Out vẫn dùng được.
- **Chỉ ảnh hưởng gợi ý màu xanh.** In/Out đặt tay luôn thắng (kiểm thử: đổi bảng/kiểu quay không đổi In/Out đặt tay); gợi ý không bao giờ được ghi vào DaVinci
  (nút Ghi chỉ ghi In/Out đặt tay; clip chưa đặt tay bị bỏ qua). Nút Ghi In/Out và Hoàn tác dùng lại chức năng ADR-0016 (hộp xác nhận, sao lưu, đọc lại đối chiếu).
- **Giao diện**: trang riêng `page3` (cột trái clip theo bin, giữa trình phát + sóng âm + thanh In/Out, phải bảng quy tắc), bám `design/3_inout`. Trình phát/thanh In/Out
  tái dùng `player.js`; Bước 2 vẫn xem được clip (thumbnail + trình phát) nhưng không còn thanh In/Out.

## Hệ quả
- Được: chỉnh số giây theo bin mà không sửa mã; sóng âm giúp tìm đoạn có tiếng; dữ liệu cũ mở bình thường.
- Mất: sóng âm cần proxy và ffmpeg; PSC vẫn giống mặc định về số (chỉnh bảng nếu muốn khác).
- Chưa làm: quy tắc tự tính In/Out (hoãn); chưa thử trong cửa sổ pywebview thật với DaVinci thật.
