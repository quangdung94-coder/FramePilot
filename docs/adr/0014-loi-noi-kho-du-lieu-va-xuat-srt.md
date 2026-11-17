# ADR-0014: Lời nói (bước 4): chép lời cả bin vào một kho SQLite cho mỗi project, xuất SRT theo giai đoạn

- Ngày: 2026-11-17
- Trạng thái: Đã chốt phần A1-A4 (chép lời, kho, bản đồ, xuất SRT). Chưa làm: tầng 2 đọc kỹ, nhập bản dịch về, ghi In/Out vào Media Pool.

## Bối cảnh
Người dựng cần biết trong mỗi clip có ai nói gì, ở đâu, để chọn clip và đoạn dùng mà không phải nghe lại từng file.
Đề bài `docs/de_bai_loi_noi_A.md` (17/11/2026): chép lời mọi file có tiếng của bin đã chọn, lưu MỘT kho cho cả project,
hiện "bản đồ lời nói" để lướt, xuất SRT theo giai đoạn để gửi đi dịch. Ràng buộc: không đụng file gốc, DaVinci chỉ đọc,
không ghi In/Out, chữ chép lời không vào git hay Notion, chạy được qua đêm và chạy tiếp được nếu bị ngắt.

## Các lựa chọn đã cân nhắc
Kho dữ liệu:
1. Một SRT hoặc JSON cho mỗi clip (cách cũ ở kho VideoAI): hàng trăm file nhỏ, khó tìm chữ cả project, khó biết clip nào
   đã chép; lần trước tên file chép lời lệch tên file âm thanh làm sót 6/17 đoạn.
2. Một file JSON lớn cho cả project: ghi lại cả file mỗi khi xong một clip, dễ hỏng nếu mất điện giữa chừng, nạp chậm khi lớn.
3. Một file SQLite cho mỗi project (chọn): ghi từng clip trong một giao dịch (xong hoặc không), tìm chữ và đếm nhanh,
   có sẵn trong Python, không thêm thư viện.

Cách chép:
1. Gom nhiều file một lần gọi Whisper (nạp mô hình một lần): đo 17/11 thấy MẤT CÂU ở file sau (clip cuối còn 1 câu thay vì 3,
   lặp lại hai lần). Bỏ.
2. Chép từng file riêng, hai tiến trình Whisper song song (chọn): khoảng 11 giây mỗi clip nhỏ, GPU 12 GB đủ cho hai bản medium.

## Quyết định
- **Kho:** `<thư mục người dựng chọn>\<tên project>.loinoi.sqlite`, thư mục KHÔNG được nằm trong thư mục mã (panel từ chối).
  Bảng `clips` (khóa = đường dẫn tương đối, UniqueId lưu kèm; ngôn ngữ, độ dài, số dòng, đoạn nói để vẽ thanh màu, số cụm key,
  câu tiêu biểu, mức kéo âm lượng, cờ "có thể sai", kích thước + ngày sửa file, timecode bắt đầu, trạng thái done/silent/error)
  và bảng `lines` (clip, số dòng, giờ bắt đầu + kết thúc TÍNH TỪ ĐẦU FILE, chữ, ngôn ngữ, cụm key, mã nghi bịa).
  Khóa clip không dùng tên file chép lời. Chạy tiếp: clip xong mà file không đổi (cùng kích thước + ngày sửa) thì bỏ qua.
- **Chép:** trích âm thanh ra WAV tạm (xóa ngay) -> kéo lên mức chuẩn (p95 về khoảng -20 dB, tối đa 30 dB, đỉnh không vượt
  0,97; KHÔNG loại file vì tiếng nhỏ) -> silero-vad lọc khoảng lặng -> Const-me Whisper ggml medium + gợi ý từ ngữ lễ cưới
  (chỉ tiếng Việt) -> đổi mốc về file gốc. Whisper Const-me không có chế độ tự nhận ngôn ngữ, nên file nghi là tiếng Anh
  (tỉ lệ từ Anh thông dụng cao) được chép lại bằng `-l en`; người dựng sửa tay từng clip và lựa chọn đó được giữ.
- **Câu nghi bịa:** bốn mã lý do (câu bịa quen thuộc, lặp y câu trước, nằm ngoài đoạn có tiếng, quá ít chữ so với độ dài).
  Clip kéo trên 18 dB hoặc có câu nghi bịa bị cờ "có thể sai".
- **Đối chiếu cuối lượt:** tổng = im lặng + đã chép + lỗi, và số file có tiếng = đã chép + lỗi lúc chép; lệch thì báo "LỆCH".
  Clip có tiếng mà Whisper không ra chữ vẫn tính là đã chép (0 dòng, cờ có thể sai), không bị xếp nhầm vào "im lặng".
- **Giao diện:** tab "4 · Lời nói" tầng 1 (bản đồ) theo demo `design/loi_noi_demo`. "Đặt In / Out" chỉ lưu vào kế hoạch của
  panel (ưu tiên: đặt tay > In/Out đã đặt trong DaVinci > gợi ý theo chữ), KHÔNG ghi vào DaVinci.
- **Xuất SRT (A4):** mỗi giai đoạn một file `NN <tên giai đoạn>.srt`; trong file các clip xếp theo giờ quay, giờ nối tiếp
  liên tục (độ dài cả clip + 1 giây đệm nên không chồng giờ). Mỗi dòng chữ bắt đầu bằng mã `[<mã clip>#<số dòng>]` (mã clip
  = tên file không đuôi, trùng tên thì thêm `@` + 4 ký tự băm của khóa), nên ChatGPT dịch xong vẫn ghép về đúng clip.
  Giờ gốc = giờ SRT - độ lệch của clip; đọc lại kiểm tra độ lệch cùng clip phải đều nhau. Cũng xuất được phần đã chọn
  (Ctrl/Shift + bấm) và SRT riêng một clip (giờ gốc, không nối tiếp). Dòng nghi bịa không xuất, số dòng bỏ được báo.
  File đã có thì không ghi đè (thêm giờ vào tên); thư mục xuất cũng không được nằm trong thư mục mã.

## Hệ quả
- Được: một file kho dễ sao lưu và xóa; chạy ban đêm an toàn (mất điện chỉ mất clip đang chép); tìm chữ cả project;
  vòng xuất rồi đọc lại có kiểm thử (ghép đúng clip và đúng giờ gốc, kể cả khi chữ đã bị dịch).
- Mất: chép từng file nên chậm hơn gom nhóm (ước 1 giờ cho 318 clip, chưa đo trên project thật); SQLite không đọc được bằng
  mắt như SRT; tự nhận ngôn ngữ chỉ là đoán theo chữ.
- Chưa chắc: ngưỡng kéo âm lượng tối đa (5 clip đo chỉ cần +0,7 đến +5,5 dB, chưa có clip tiếng nhỏ); chưa chép thử cả bin
  thật trong DaVinci; tự nhận tiếng Anh chưa thử với clip tiếng Anh thật.
- Việc sau: tầng 2 đọc kỹ từng câu, nhập bản dịch về (đọc lại SRT đã dịch bằng `read_back`, đã có sẵn và có kiểm thử),
  ghi In/Out vào Media Pool (nếu làm phải sao lưu In/Out cũ và có Hoàn tác).
