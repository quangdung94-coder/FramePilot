# ADR-0026: "Tự phân loại" chạy luôn ở Bước 2 và Bước 3, bỏ cặp nút trên cùng

Ngày: 18/11/2026 (đêm). Trạng thái: đã code, CHỜ NGƯỜI DỰNG THỬ bằng chuột thật. Demo duyệt: 2 bảng cuối Design canvas
("Bước 2 - Tự phân loại", "Bước 3 - Tự phân loại In/Out").

## Quyết định
1. Bỏ cặp nút "Tự phân loại | AI gợi ý · hộp bên phải" ở thanh trên (cả Bước 2 và 3). Thanh trên còn ô "Kiểu quay".
2. Bước 2: nút **Tự phân loại · N clip nhóm X** nằm đầu hộp bên phải (khung viền cam), gộp hai nút cũ "Chạy lại AI" và "Gợi ý cho cả nhóm".
   Bấm: nếu máy có venv AI thì AI nhúng ảnh nền (làm tiếp phần chưa có), xong thì tự gán nhãn cho cả nhóm; không có venv mà đã có dữ liệu AI thì gán luôn.
   Có thanh tiến độ và "đã chạy a / b". Nút "Nhận hạng 1 cho N clip" (aiTakeAll) và "Tắt gợi ý nhóm" bị bỏ vì ngưỡng thay thế.
3. Chạy chỉ GÁN NHÃN (dấu by="ai_auto", không tính vào dữ liệu AI học, có Hoàn tác từng lần), KHÔNG chuyển clip trong DaVinci. Chuyển clip vẫn là nút
   "Áp dụng vào Media Pool". Giữ phím A/X/1-3, ô "Tự xếp luôn sau khi AI chạy xong".
4. Ngưỡng "tự xếp khi hạng 1 từ N%": kéo thanh hoặc gõ số là ÁP DỤNG NGAY (API mới `ai_auto_apply`, debounce 180 ms cho thanh kéo). Tính từ vector và mô tả đã
   lưu, không gọi lại AI (test khẳng định `_ai_job` vẫn None). Sau khi nhóm đã Tự phân loại (lần này hoặc lần trước), đổi ngưỡng cũng đổi nhãn: lên cao thì clip
   AI xếp có điểm thấp hơn ngưỡng bị gỡ nhãn (về "chờ bạn duyệt"), xuống thấp thì xếp thêm. Nhãn tay (by="nguoi") và nhãn "Nhận" (ai_duyet) không bao giờ bị đụng.
   Nhóm chưa Tự phân loại: kéo ngưỡng chỉ đổi biểu đồ và số, chỉ nhớ ngưỡng, không gán nhãn (an toàn hơn).
5. Biểu đồ 10 cột độ chắc hạng 1 (0-100%) có vạch ngưỡng và hai số "clip tự xếp" / "chờ bạn duyệt" tính tại chỗ khi kéo (API `ai_group_scores`, chỉ đọc).
   Clip dưới ngưỡng: thẻ viền cam đứt và nhãn "chờ bạn duyệt" (bin và % nằm trong tooltip vì thẻ hẹp).
6. Bước 3: bỏ nút "Chạy lại gợi ý (N clip sao)" ở cột trái (chỉ còn cây clip sao). Khung viền cam "Tự phân loại In/Out · N clip sao" nằm ngay dưới
   "Quy tắc gợi ý từng bin" ở cột phải, có thanh tiến độ "đã chạy a / N" và ô "Giữ nguyên clip bạn đã đặt tay (viền cam)" mặc định BẬT. Dùng lại logic
   gợi ý hai mức (ADR-0024: theo lời nói nếu có, không thì theo quy tắc cắt đầu/đuôi từng bin). `inout_suggest_start(keep_manual)`: bật thì bỏ qua clip có
   In/Out đặt tay; mọi clip sao đều đặt tay thì báo rõ lý do thay vì im lặng. Mặc định của API là False (giữ hành vi cũ), giao diện gửi theo ô tick.
7. Chỉ ghi gợi ý màu xanh, không tự ghi In/Out vào DaVinci; In/Out đặt tay (cam) luôn thắng.
8. Nhãn "MỚI · ..." và ô ghi chú gạch đứt của demo KHÔNG đưa vào panel.

## Lỗi bắt được khi làm
`app.js` còn gọi `$("segMode")` sau khi HTML bỏ cặp nút: cả panel đứng ở lần vẽ đầu. Đã sửa và thêm test quét mọi `$("id")` trong các file JS phải có trong HTML
(trừ vài id sinh động). Họ lỗi này giờ bị bắt ở test.

## Chưa chạy thật
Cửa sổ pywebview thật; AI nhúng ảnh thật bằng venv AI với project thật (chỉ thử bằng DaVinci giả + file gợi ý giả); kéo thanh ngưỡng bằng chuột thật
(đã thử qua trình duyệt với API thật và DaVinci giả, gọi hàm kéo bằng mã).
