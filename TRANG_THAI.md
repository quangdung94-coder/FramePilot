# Trạng thái Trợ lý File Quay (cập nhật 17/11/2026, khuya)

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
- Nút "★ Đưa clip sao lên Timeline": chỉ tạo timeline MỚI (ADR-0011); người dựng đã thử trên DaVinci thật, chạy đúng.

## Lời nói A (đề bài docs/de_bai_loi_noi_A.md)
- Xong bước 1 (đo) và bước 2 (kho dữ liệu + chạy cả bin, thử trên bản sao 5 clip: đối chiếu khớp, chạy tiếp đúng). Chưa thử chạy cả bin thật 318 clip trong DaVinci.
- Xong bước 3 của đề bài (giao diện tab "4 · Lời nói" tầng 1: bản đồ, lọc, tìm chữ, cột phải, J gắn sao, kéo mép khung In/Out, Đặt In/Out lưu vào kế hoạch panel; đã đổi nhãn tab: 4 Lời nói, 5 Thời lượng). Đã mở trong cửa sổ pywebview thật (17/11 tối): hiển thị đúng, hộp chọn thư mục chạy được, kho giả 376 clip hiện đủ bản đồ; phím J, kéo mép khung, tìm chữ đã thử ở khung trình duyệt, CHƯA thử bằng tay trong cửa sổ thật. Lưu ý: đã chọn thư mục kho GIẢ cho project đang mở, nhớ chọn lại thư mục kho thật trước khi chép lời.
- Xong mục A4 (xuất SRT): nút "Xuất SRT theo giai đoạn" (mỗi giai đoạn một file, giờ nối tiếp liên tục, mã `[clip#số dòng]` trong dòng chữ), "SRT clip này", "SRT phần đã chọn" (Ctrl/Shift + bấm chọn nhiều clip). Có kiểm thử vòng đủ (xuất, đọc lại kể cả sau khi dịch, ghép đúng clip và giờ gốc). Đã thử ở khung trình duyệt với dữ liệu giả; CHƯA thử trong cửa sổ pywebview thật (hộp chọn thư mục xuất) và chưa xuất từ kho chép lời thật.
- ADR-0014 đã viết (docs/adr/0014-loi-noi-kho-du-lieu-va-xuat-srt.md).
- Việc kế (cần người dựng): chọn thư mục kho THẬT, bấm "Chép lời cả bin" (ước ~1 giờ cho 318 clip), thử xuất SRT; đưa 1-2 clip tiếng nhỏ để chốt mức kéo tối đa. Sau đó: tầng 2 đọc kỹ, nhập bản dịch về (hàm đọc lại đã có).
- Chưa chắc: tự nhận ngôn ngữ vi/en chỉ là đoán theo chữ (Whisper Const-me không có chế độ auto), chưa thử với clip tiếng Anh thật; ngưỡng kéo âm lượng chờ clip tiếng nhỏ.

## Đổi tên giai đoạn / bin con (đề bài 17/11 23:25, đổi kế hoạch 17/11 khuya) - CHỜ NGƯỜI DỰNG THỬ
- Kế hoạch (người dựng chốt): bin chỉ là NHÃN trong panel, bin thật chỉ tạo khi bấm Áp dụng, nên chỉ đổi tên TRONG KẾ HOẠCH của panel: không đổi tên trong Media Pool, không mô hình id, không nâng cấp file project. Chi tiết và lý do: docs/adr/0015.
- Đã sao lưu D:\VideoAI\data	roly\projects sang projects_backup_20261117-232355 (7 file) trước khi làm. Không ghi file project thật khi thử.
- Cách dùng: bấm ĐÚP tên giai đoạn (bước 1 hoặc cột Media Pool bước 2) hoặc tên bin con (cột Media Pool), gõ tên mới, Enter đổi, Esc hoặc bấm ra ngoài thì hủy. Tên rỗng, có ký tự cấm : & / \ * ? " < > |, trùng tên cùng cấp, quá 60 ký tự thì báo lỗi rõ. Nhãn clip đi theo tên mới; phím 1-9 giữ nguyên theo vị trí bin.
- Nếu đã Áp dụng rồi mới đổi tên: hộp xác nhận Áp dụng liệt kê bin cũ trong Media Pool sẽ còn lại RỖNG, Trợ lý không tự xóa.
- Kiểm thử: 114 bài đạt (thêm test_troly_rename, test_troly_rename_api, test_troly_rename_web). Đã thử bằng chuột/phím thật ở khung trình duyệt với Media Pool giả: đổi tên giai đoạn, đổi tên bin con, gõ số và J trong ô sửa không bị coi là phím tắt, tên sai bị chặn, Esc hủy, hộp Áp dụng có nhắc; không lẹm mép ở 1100, 1440, 2560 px.
- CHƯA làm: chụp trong cửa sổ pywebview thật (cửa sổ đang mở là bản cũ, cần đóng và mở lại); menu chuột phải "Đổi tên" (bấm đúp đủ dùng).

## Việc tiếp theo (theo thứ tự)
1. Bước 3 In/Out: thanh In/Out kéo tay (chuột + phím I/O, mũi tên từng frame), sóng âm (waveform từ proxy bằng ffmpeg),
   bảng quy tắc từng bin chỉnh được, trang Bước 3 riêng (hiện dùng chung màn hình Bước 2), trình phát video proxy
   HTML5 ở cột phải. In/Out người dựng đặt tay luôn thắng gợi ý. Đọc In/Out đặt trong Media Pool về panel (đã đọc được).
2. Bước 5 Thời lượng: ô "Video mục tiêu" (10-15 phút), biểu đồ chia tỉ lệ giai đoạn, Min-Max tổng thời lượng từng bin
   (Decor 10-20s, Beauty 20-30s), "Cắt gọt cho vừa", đưa lên timeline MỚI (không sửa timeline cũ).
3. Ý tưởng người dựng đã nêu (chưa thiết kế):
   - Nhiều máy quay (2-4 camera): nghiên cứu layout dễ nhìn (mỗi máy một làn trên thanh thời gian, màu theo máy, lọc theo máy).
     Panel đã có khóa máy quay + ô lệch giờ theo máy, chưa có giao diện.
   - Cho đổi tên bin giai đoạn (đổi theo cả bin trong Media Pool, giữ nhãn clip).
   - Số thứ tự đặt TRƯỚC tên bin thay vì sau (cần người dựng chỉ chỗ đang sai).
   - Sao nhiều mức 1/2/3 như lọc ảnh (phím khác 1-9, ví dụ Alt+1/2/3); lên timeline ưu tiên nhiều sao.
4. AI tự phân loại clip, học từ nhãn người dựng đã xếp.

## Ghi chú kỹ thuật
- Khi sửa logic trong troly_core.py nên thêm test vào tests/ rồi chạy bộ kiểm thử.
- Code sao/In-Out gợi ý ban đầu do Antigravity viết, phần nối giao diện + tạo timeline do Claude viết (15/11).
- Kho Git riêng: https://github.com/quangdung94-coder/TroLyFileQuay (riêng tư). Lịch sử kho riêng bắt đầu ở commit 5e9090c (đã gỡ tên khách; mã cũ 8945cc9 không còn dùng). Lịch sử trước 17/11/2026 nằm ở kho cũ D:\VideoAI\repo (v0.2.5 = commit b13c7fb). Menu DaVinci trỏ vào thư mục này (app\), `install.py --check` đạt.
- Bộ kiểm thử: tests/ (94 bài, `& $py -m unittest discover -s tests -q`; trên Windows đặt PYTHONUTF8=1). ADR trong docs/adr/ (0009, 0010, 0011, 0014).
- Số ADR sắp tới: Bước 3 trang riêng = ADR-0012, Bước 5 chia thời lượng = ADR-0013 (ADR-0011 = timeline mới, ADR-0014 = Lời nói A, đã có).
