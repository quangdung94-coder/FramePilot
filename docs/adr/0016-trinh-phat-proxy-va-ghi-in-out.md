# ADR-0016: Trình phát proxy, đặt In/Out tay và ghi In/Out vào Media Pool

Ngày: 17-18/11/2026. Trạng thái: đã code, CHỜ NGƯỜI DỰNG THỬ.

## Bối cảnh
Bước 2 chỉ có thumbnail tĩnh. Người dựng cần xem clip chạy thật, đặt In/Out ngay lúc lọc source, rồi ghi vào Media Pool để
chỉnh tiếp bằng tay trong DaVinci.

## Quyết định
1. **Trình phát**: thẻ `<video>` của WebView2 phát file proxy qua máy chủ cục bộ `app/troly_play.py`.
   - Chỉ nghe `127.0.0.1`, cổng ngẫu nhiên, hỗ trợ Range (lướt). Mỗi clip một "vé" token ngẫu nhiên -> đường dẫn.
   - Chỉ phát đường dẫn nằm trong `proxy_root` (config.json, KHÔNG ghi cứng trong mã) hoặc thư mục cache `troly_play`.
     Chuẩn hóa + giải liên kết (symlink) trước khi so; kiểm lại lúc phát. Đường dẫn ngoài -> 403/None (có test).
   - Chỉ mở file để ĐỌC; không ghi/đổi tên/xóa trong thư mục proxy.
   - Phương án dự phòng: nếu thẻ video báo lỗi (ProRes/DNx...), `play_info(uid, transcode=True)` gọi ffmpeg tạo mp4 H.264 720p
     nhẹ (keyframe mỗi 12 frame) trong `<data_root>\cache\troly_play\<project>\` (xóa được), chỉ cho clip đang xem.
   - Clip không có proxy: hiện "Chưa có proxy - chỉ xem hình tĩnh", giữ thumbnail.
   - Phím: Space phát/dừng, I / O đặt điểm vào/ra tại vị trí đang xem, mũi tên chỉnh từng frame (Shift = 10) khi con trỏ đang ở
     cột phải. Đọc bằng `event.code`, bỏ qua khi đang gõ ô chữ.
2. **In/Out đặt tay**: lưu trong kế hoạch panel `plan["inout"][đường dẫn tương đối] = [in_s, out_s]` (giây từ đầu file; cùng chỗ
   với nút "Đặt In/Out" của tab Lời nói). **Đặt tay luôn thắng**: hiệu lực = đặt tay > In/Out đang có trong DaVinci > (chỉ hiển
   thị) gợi ý tự động. Gợi ý tự động KHÔNG bao giờ được ghi vào DaVinci. Màu: cam = đã đặt trong DaVinci, cam vằn = đặt tay chưa ghi,
   xanh = gợi ý.
3. **Ghi vào DaVinci** (chỉ khi bấm nút + hộp xác nhận nói rõ số clip; chỉ cho clip có sao hoặc clip đang chọn):
   đọc In/Out cũ -> ghi file sao lưu `<data_root>\troly\inout_backup\<project>_<ngày giờ>.json` (không ghi đè; lỗi ghi thì DỪNG, chưa
   đụng DaVinci) -> `SetMarkInOut(frame_in, frame_out, "all")` từng clip -> đọc lại `GetMarkInOut` đối chiếu. Báo khớp/lỗi/lệch theo
   từng clip, không báo thành công giả. **Hoàn tác** khôi phục đúng bản sao lưu gần nhất (trước đó trống thì `ClearMarkInOut`).
   Chỉ gọi SetMarkInOut/ClearMarkInOut: không xóa clip, không sửa timeline, không đụng file, không render.

## Kết quả đo thật trên DaVinci Resolve Studio 21.1.1.10 (đo 17/11/2026, project thử LV_Ten, clip DG7320, 50 fps, Start TC 00:42:38:24)
- `SetMarkInOut(10, 100, "all")` -> trả `True`; `GetMarkInOut()` -> `{video:{in:10,out:100}, audio:{in:10,out:100}}`.
  => **nhận SỐ FRAME tính từ ĐẦU FILE** (frame 0 = frame đầu clip), KHÔNG cộng Start TC (Start TC quy ra 127 924 frame; nếu cộng thì
  đã đọc lại khác đi).
- `SetMarkInOut("00:42:38:34", "00:42:43:24", "all")` (chuỗi timecode) -> trả `False`, không đổi gì. => phải dùng frame nguyên.
- `SetMarkInOut(127010, 127100)` (vượt 240 frame của clip) -> trả `True` và đọc lại đúng 127010/127100: **DaVinci KHÔNG kiểm vượt
  độ dài**, nên panel tự kẹp trong [0, frames-1] trước khi ghi.
- `ClearMarkInOut("all")` đưa về `{video:{}, audio:{}}` (trạng thái ban đầu của clip). Đo xong đã xóa về đúng trạng thái đầu,
  đối chiếu với bản dump (376 clip trong project thử đều chưa có In/Out; chỉ chạm 1 clip).
- Chuyển đổi hiển thị: timecode file = Start TC + frame (hàm `file_frame_to_tc`); frame ghi = timecode - Start TC (`tc_to_file_frame`).
  Panel lưu giây, ghi `round(giây × fps)`.
- Không bất ngờ so với cách tính đang dùng khi ĐỌC (`mark_in / fps`), nên không phải đổi cách tính.

## Chưa đo được (cần người dựng thử trên máy thật)
- WebView2 có phát được proxy thật trong F:\02_Proxy Media không (định dạng/codec proxy), độ trễ lướt. Lượt tự chạy không có quyền
  thư mục D:/F: trên máy nên CHƯA đo. Đã kiểm thử bằng mp4 H.264 giả trong Chromium: phát, dừng, lướt, I/O, kéo mép, mũi tên đều chạy.
  Nếu proxy là ProRes/DNx và thẻ video báo lỗi thì tự chuyển sang bản xem nhẹ ffmpeg (cũng CHƯA chạy thật). Người dựng thử xong
  điền kết quả vào đây.
- Proxy có thể khác timecode/độ dài bản gốc: panel dùng thời gian tính từ đầu clip (giây), khớp theo đầu file; nếu proxy ngắn/dài
  khác bản gốc thì cần đối chiếu (chưa đo).

## Hệ quả
- config.json cần thêm `"proxy_root": "F:\\02_Proxy Media"` (không đưa lên Git).
- Quy tắc ghi In/Out đã thêm vào CLAUDE.md. Ghi hàng loạt CHỈ do người dựng bấm nút.
