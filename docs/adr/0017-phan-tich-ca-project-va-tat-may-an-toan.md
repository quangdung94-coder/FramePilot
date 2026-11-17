# ADR-0017: "Phân tích cả project" và tắt máy an toàn

- Ngày: 2026-11-18
- Trạng thái: Đã code và kiểm thử bằng bản giả. CHỜ NGƯỜI DỰNG THỬ bằng tay (chưa tắt máy thật lần nào).

## Bối cảnh
Chép lời cả bin mất khoảng 1 giờ, thumbnail cũng mất thời gian. Người dựng muốn bấm một nút rồi đi ngủ, và tùy chọn để máy tự tắt khi xong.
Tắt máy là thao tác khó đảo ngược và có thể làm mất việc chưa lưu, nên phải an toàn hơn mọi tính năng khác của Trợ lý.

## Quyết định
- Nút **"Phân tích cả project"** (tab Lời nói) chạy lần lượt: chép lời cả bin (tái dùng `SpeechRun`, chạy tiếp được, đối chiếu cuối lượt) rồi chờ
  thumbnail của MỌI clip (thumbnail tự chạy nền sau khi đọc clip, nay được chờ cho xong).
- Ô **"Tắt máy khi xong" mặc định TẮT** (không nhớ giữa các lần mở). Khi tick, hộp xác nhận nói rõ máy sẽ tắt.
- Khi xong và ô được tick: **lưu project DaVinci** (`ProjectManager.SaveProject()` qua luồng DaVinci duy nhất, đòi trả `True`) -> **đếm ngược 2 phút**
  (hiện hộp có nút "Huỷ tắt máy", mỗi giây kiểm Huỷ/Dừng) -> **lưu lại lần cuối** -> lệnh tắt máy (`shutdown /s /t 10`).
- **KHÔNG BAO GIỜ tắt máy nếu:** bị dừng giữa chừng (nút Dừng hoặc đóng cửa sổ), chép lời lỗi hoặc đối chiếu lệch, thumbnail chưa xong hoặc kẹt
  quá 5 phút, có ngoại lệ bất kỳ, lưu project lỗi (cả lần đầu lẫn lần cuối, SaveProject không trả đúng `True`), DaVinci đang mở project khác, hoặc
  người dựng bấm Huỷ. Mọi trường hợp đó chỉ báo lý do trên màn hình.
- **Quyền:** người dựng đã đồng ý (18/11/2026) cho panel gọi `SaveProject`; chỉ trong luồng này và chỉ khi tick tắt máy. Đã ghi vào mục
  "Quy tắc với DaVinci" của `CLAUDE.md`. Không ghi In/Out, không xóa gì, không đụng file quay.
- **Kiến trúc để kiểm thử an toàn:** `troly_batch.AnalyzeAll` là điều phối thuần; chép lời, chờ thumbnail, lưu, lệnh tắt máy và đồng hồ đều được TRUYỀN VÀO.
  Lệnh tắt máy thật `system_shutdown()` từ chối chạy khi biến môi trường `TROLY_NO_SHUTDOWN` được đặt; tệp kiểm thử đặt biến này ngay khi nạp.
  23 bài kiểm thử dùng bản giả (tắt máy, lưu, đồng hồ), gồm: mặc định không tắt, thứ tự lưu -> đếm ngược -> lưu -> tắt, Huỷ, Dừng, đóng cửa sổ,
  chép lời lỗi, thumbnail chưa xong, lưu lỗi đầu/cuối, `SaveProject` trả không phải `True`, ngoại lệ, và worker `do_save_project`.

## Hệ quả
- Được: chạy qua đêm không cần canh; tắt máy chỉ xảy ra khi mọi thứ đã xong và đã lưu.
- Mất/Rủi ro: đây là lần đầu panel gọi SaveProject và lệnh tắt máy thật, CHƯA thử thật. Lệnh `shutdown /s /t 10` còn cho 10 giây để chạy
  `shutdown /a` bằng tay nếu cần. Nếu DaVinci đang hiện hộp thoại chờ (không phản hồi) thì `SaveProject` quá 90 giây sẽ tính là lỗi và không tắt.
- Người dựng thử lần đầu: tick tắt máy với project nhỏ, bấm Huỷ lúc đếm ngược; sau đó mới thử cho tắt thật.
