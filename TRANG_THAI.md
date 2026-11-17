# Trạng thái Trợ lý File Quay (cập nhật 17/11/2026, cuối buổi)

## Đã chạy được
- Bước 1: đọc giờ quay thật, chia giai đoạn bằng thanh thời gian kéo được, mẫu giai đoạn, tạo bin giai đoạn trong
  Media Pool (đã áp dụng thật trên project 17/10: 533 clip, 0,8 giây, 0 lỗi, timeline không đổi).
- Bước 2: lưới thumbnail (proxy + LUT), xếp clip vào bin con:
  - Phím 1-9 = bin con của giai đoạn đang xem; 0 = bỏ nhãn.
  - Shift+số = chuyển clip sang giai đoạn đó rồi CHỜ bấm số bin con (không giới hạn thời gian; Esc hoặc bấm chỗ khác để thôi).
  - Kéo thả thumbnail vào bin, menu chuột phải, Ctrl+A, Shift/Ctrl + bấm chọn nhiều, mũi tên di chuyển, Enter mở trong DaVinci.
  - Bấm bin trong cây Media Pool chỉ để XEM (như mở thư mục con), không đổi nhãn clip.
  - Giai đoạn chọn tay cho từng clip thắng giai đoạn tính theo giờ.
- Panel nhớ project khi tắt/mở lại DaVinci (lưu ngay, bản .bak, khôi phục bước/bin/thu phóng).
- Cột phải: thanh In/Out xem được (cam = đã đặt trong DaVinci, xanh = gợi ý theo nhãn bin: Decor 3s, Beauty 4s,
  Nghi lễ 5-7s, Phỏng vấn giữ trọn câu, mặc định vào +1,2s giữ 3s). Chỉ xem, chưa kéo chỉnh, chưa ghi vào DaVinci.
- Dấu sao ★: phím J gắn/bỏ sao (chọn nhiều thì đặt đồng loạt), nút gắn/bỏ sao ở cột phải, ô lọc "Chỉ clip có sao".

## Đang dở (làm ĐẦU TIÊN)
- Nút "★ Đưa clip sao lên Timeline": lần thử 15/11 báo lỗi "DaVinci không tạo được timeline mới". Đã sửa
  (bỏ ký tự lạ trong tên timeline, thêm cách dự phòng CreateEmptyTimeline + AppendToTimeline, báo lỗi chi tiết)
  nhưng CHƯA thử lại thật. Việc tiếp: người dựng bấm thử; nếu còn lỗi, đọc phần "Chi tiết" trong thông báo để sửa.
  Nghi thêm: CreateTimelineFromClips có thể cần đang ở trang Edit/Media, hoặc clip có sao thuộc nhiều fps khác nhau.

## Việc tiếp theo (theo thứ tự)
1. Xong nút đưa clip sao lên timeline (trên).
2. Bước 3 In/Out: thanh In/Out kéo tay (chuột + phím I/O, mũi tên từng frame), sóng âm (waveform từ proxy bằng ffmpeg),
   bảng quy tắc từng bin chỉnh được, trang Bước 3 riêng (hiện dùng chung màn hình Bước 2), trình phát video proxy
   HTML5 ở cột phải. In/Out người dựng đặt tay luôn thắng gợi ý. Đọc In/Out đặt trong Media Pool về panel (đã đọc được).
3. Bước 4 Thời lượng: ô "Video mục tiêu" (10-15 phút), biểu đồ chia tỉ lệ giai đoạn, Min-Max tổng thời lượng từng bin
   (Decor 10-20s, Beauty 20-30s), "Cắt gọt cho vừa", đưa lên timeline MỚI (không sửa timeline cũ).
4. Ý tưởng người dựng đã nêu (chưa thiết kế):
   - Nhiều máy quay (2-4 camera): nghiên cứu layout dễ nhìn (mỗi máy một làn trên thanh thời gian, màu theo máy, lọc theo máy).
     Panel đã có khóa máy quay + ô lệch giờ theo máy, chưa có giao diện.
   - Cho đổi tên bin giai đoạn (đổi theo cả bin trong Media Pool, giữ nhãn clip).
   - Số thứ tự đặt TRƯỚC tên bin thay vì sau (cần người dựng chỉ chỗ đang sai).
   - Sao nhiều mức 1/2/3 như lọc ảnh (phím khác 1-9, ví dụ Alt+1/2/3); lên timeline ưu tiên nhiều sao.
5. AI tự phân loại clip, học từ nhãn người dựng đã xếp.

## Ghi chú kỹ thuật
- Chưa có bộ kiểm thử trong thư mục này (bộ test cũ nằm ở repo VideoAI, phụ thuộc module cũ). Khi sửa logic trong
  troly_core.py nên viết test mới vào tests/ và chạy `& $py -m unittest discover -s tests -q`.
- Code sao/In-Out gợi ý ban đầu do Antigravity viết, phần nối giao diện + tạo timeline do Claude viết (15/11).
- Các thay đổi v0.2.5 đã commit + push ở kho cũ D:\VideoAIepo (commit b13c7fb; ADR-0011 nằm ở đó). Menu DaVinci đang trỏ vào thư mục này (app\), `install.py --check` đạt.
- Thư mục này chưa phải Git repo. Muốn có lịch sử: `git init`, tạo kho riêng tư trên GitHub, rồi commit lần đầu.
